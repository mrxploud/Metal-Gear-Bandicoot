#!/usr/bin/env python3
"""Confere e desenha uma animação do Crash 3 lendo SÓ a entrega (out_c3/), sem o disco e sem o crashlib de leitura.

    python -I ver3.py C3_ENGATINHAR                 desenha (frente, lado, costas + todas as chaves)
    python -I ver3.py --conferir                    confere TODAS as animações: cru x anim x comprimido

É a prova de que os arquivos entregues se bastam, e o decodificador daqui (`descomprimir`) é a referência para
portar para C: só soma, deslocamento e máscara. Usa do crashlib apenas o desenhista (raster).
"""
import argparse
import json
import os
import struct
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from crashlib import raster                                  # noqa: E402

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


# ------------------------------------------------------------------------------------------------------
# O decodificador de referência (o que o Crash 3 faz na RAM dele)
# ------------------------------------------------------------------------------------------------------
def descomprimir(item, bases, n_vertices_do_modelo):
    """Um quadro como está no disco -> (origem, [(x, y, z)] bytes da malha, [(x, y, z)] dos especiais).

    item   o quadro: cabeçalho de 28 bytes {int16 ox, oy, oz, ?; u32 0; u32 0; i32 n_vertices; i32 n_colisoes;
           i32 tam_cabecalho}, depois n_colisoes * 40 bytes, depois os vértices especiais (3 bytes cada, ordem
           x, Z, y) e, alinhada em 4 bytes a partir do fim das colisões, a fila de bits.
    bases  o arquivo <MODELO>.bases.bin: uma palavra de 32 bits por vértice da malha. Do bit mais alto para o
           mais baixo: X (7 bits, vale o dobro), Y (8), Z (8), bits de X (3), bits de Y (3), bits de Z (3).
    A fila de bits é lida em palavras de 32 bits little-endian, do bit 31 para o bit 0. Para cada vértice, na
    ordem X, Y, Z: lê (bits + 1) bits como número com sinal (complemento de dois), soma a base e o valor
    acumulado do vértice anterior, e fica com os 8 bits de baixo. Se "bits" for 7, o acumulado daquele eixo
    zera antes (o valor lido passa a ser absoluto).
    """
    ox, oy, oz, _d, _a, _b, n_vert, n_col, tam_cab = struct.unpack_from('<4hII3i', item, 0)
    ini = 28 + n_col * 40
    n_esp = (tam_cab - ini) // 3
    especiais = [(item[ini + i * 3], item[ini + i * 3 + 2], item[ini + i * 3 + 1]) for i in range(n_esp)]
    n = n_vertices_do_modelo - n_esp
    palavras = struct.unpack_from(f'<{(len(item) - ini) // 4}I', item, ini)
    pos = n_esp * 24                                   # em bits, a partir do fim das colisões
    acc = [0, 0, 0]
    saida = []
    for i in range(n):
        w, = struct.unpack_from('<I', bases, i * 4)
        base = ((w >> 25) & 0x7F) * 2, (w >> 17) & 0xFF, (w >> 9) & 0xFF
        nbits = (w >> 6) & 7, (w >> 3) & 7, w & 7
        for e in range(3):
            if nbits[e] == 7:
                acc[e] = 0
            quantos = nbits[e] + 1
            val = 0
            for _ in range(quantos):                   # bit a bit, para ficar igual ao que se escreve em C
                val = (val << 1) | ((palavras[pos >> 5] >> (31 - (pos & 31))) & 1)
                pos += 1
            if val >> nbits[e]:                        # bit de sinal
                val -= 1 << quantos
            acc[e] = (acc[e] + val + base[e]) & 0xFF
        saida.append(tuple(acc))
    return (ox, oy, oz), saida, especiais


def ler_comprimido(caminho):
    with open(caminho, 'rb') as f:
        d = f.read()
    magia, n_quadros, n_vertices = struct.unpack_from('<4sHH', d, 0)
    assert magia == b'C3AN', caminho
    pos, itens = 8, []
    for _ in range(n_quadros):
        tam, = struct.unpack_from('<H', d, pos)
        itens.append(d[pos + 2:pos + 2 + tam])
        pos += 2 + tam
    return n_vertices, itens


def ler_cru(caminho):
    with open(caminho, 'rb') as f:
        d = f.read()
    pos, quadros = 0, []
    while pos < len(d):
        ox, oy, oz, n = struct.unpack_from('<3hH', d, pos)
        b = np.frombuffer(d, np.uint8, n * 6, pos + 8).reshape(n, 6)[:, :3].astype(np.int32)
        quadros.append(((ox, oy, oz), b))
        pos += 8 + n * 6
    return quadros


# ------------------------------------------------------------------------------------------------------
class Entrega:
    def __init__(self, pasta):
        self.pasta = pasta
        with open(os.path.join(pasta, 'model.json'), encoding='utf-8') as f:
            self.m = json.load(f)
        self.anims = {a['nome']: a for a in self.m['animacoes'] if 'ausente' not in a}
        self._atlas = {}

    def posicoes(self, a):
        """Do cru para o espaço do contrato: (o + byte) * k, por eixo."""
        k = np.array(a['cru']['k'])
        return np.stack([(np.array(o) + b) * k for o, b in ler_cru(os.path.join(self.pasta, a['cru']['arquivo']))])

    def conferir(self, a):
        """Devolve uma lista de problemas (vazia = tudo certo)."""
        problemas = []
        md = self.m['modelos'][a['modelo']]
        n, k_q = a['vertices'], a['quadros']
        pos = self.posicoes(a)
        bin_ = np.fromfile(os.path.join(self.pasta, a['arquivo']), '<i2', count=k_q * n * 3).reshape(k_q, n, 3)
        erro = float(np.abs(pos - bin_).max())
        if pos.shape != (k_q, n, 3) or erro > 0.5001:
            problemas.append(f'cru e anim discordam (erro {erro:.3f})')
        if max(max(t[:3]) for t in md['triangulos']) >= n:
            problemas.append('triângulo aponta para vértice que não existe')
        if len(md['cores_dos_cantos']) != len(md['triangulos']):
            problemas.append('cores_dos_cantos não tem o tamanho de triangulos')
        if md['comprimido']:
            with open(os.path.join(self.pasta, md['comprimido']['bases']), 'rb') as f:
                bases = f.read()
            n_total, itens = ler_comprimido(os.path.join(self.pasta, a['comprimido']['arquivo']))
            cru = ler_cru(os.path.join(self.pasta, a['cru']['arquivo']))
            for i, item in enumerate(itens):
                origem, verts, _esp = descomprimir(item, bases, n_total)
                o32 = tuple(c // 32 for c in origem)
                if o32 != cru[i][0] or not np.array_equal(np.array(verts), cru[i][1]):
                    problemas.append(f'quadro {i}: o decodificador de referência não bate com o cru')
                    break
        return problemas

    # -- desenho só com a entrega ------------------------------------------------------------------
    def atlas(self, nome):
        if nome not in self._atlas:
            info = self.m['texturas']['atlas'][nome]
            with open(os.path.join(self.pasta, 'tex', nome + '.bin'), 'rb') as f:
                d = np.frombuffer(f.read(), np.uint8)
            if info['bits'] == 4:
                d = d.reshape(info['altura_px'], info['largura_px'] // 2)
                idx = np.empty((info['altura_px'], info['largura_px']), np.uint8)
                idx[:, 0::2] = d & 0xF
                idx[:, 1::2] = d >> 4
            else:
                idx = d.reshape(info['altura_px'], info['largura_px'])
            self._atlas[nome] = idx
        return self._atlas[nome]

    def textura(self, regiao_id):
        r = self.m['texturas']['regioes'][regiao_id]
        idx = self.atlas(r['atlas'])[r['y']:r['y'] + r['a'], r['x']:r['x'] + r['l']]
        pal = []
        for h in self.m['texturas']['cluts'][r['clut']]['cores_ps1']:
            p = int(h, 16)
            pal.append(((p & 31) * 255 // 31, ((p >> 5) & 31) * 255 // 31, ((p >> 10) & 31) * 255 // 31,
                        0 if (p & 0x7FFF) == 0 and not (p >> 15) else 255))
        return np.array(pal, np.uint8)[idx]

    def triangulos(self, modelo):
        md = self.m['modelos'][modelo]
        cache, lista = {}, []
        for t, cantos in zip(md['triangulos'], md['cores_dos_cantos']):
            mat = md['materiais'][t[3]]
            cores = [md['cores'][i] for i in cantos]
            # a entrega é horária vista de fora; o desenhista não liga para o sentido
            d = {'v': tuple(t[:3]), 'mistura': None if mat['modo_de_mistura'] == 3 else mat['modo_de_mistura']}
            if mat['textura'] is not None:
                if mat['textura'] not in cache:
                    cache[mat['textura']] = self.textura(mat['textura'])
                d['textura'] = cache[mat['textura']]
                d['uvs'] = [(u + 0.5, v + 0.5) for u, v in mat['uv']]
                d['rgbs'] = cores
            else:
                d['rgbs'] = [[min(255, c * 2) for c in cor] for cor in cores]
            lista.append(d)
        return lista


def principal():
    ap = argparse.ArgumentParser(description='Confere e desenha a entrega do Crash 3 sem o disco.')
    ap.add_argument('animacao', nargs='?', default='C3_PARADO')
    ap.add_argument('--entrega', default=os.path.join(AQUI, 'out_c3'))
    ap.add_argument('--conferir', action='store_true', help='confere todas as animações e sai')
    ap.add_argument('--saida', help='arquivo .png (padrão: <entrega>/previews/ver3_<NOME>.png)')
    ap.add_argument('--tamanho', type=int, default=200)
    args = ap.parse_args()
    e = Entrega(args.entrega)
    if args.conferir:
        ruins = comp = 0
        for nome, a in e.anims.items():
            p = e.conferir(a)
            comp += bool(e.m['modelos'][a['modelo']]['comprimido'])
            if p:
                ruins += 1
                print(f'  PROBLEMA {nome}: {"; ".join(p)}')
        print(f'{len(e.anims)} animações conferidas ({comp} delas passaram também pelo decodificador de referência), '
              f'{ruins} com problema.')
        sys.exit(1 if ruins else 0)
    a = e.anims[args.animacao]
    problemas = e.conferir(a)
    print(f'{args.animacao}: {a["quadros"]} chaves, toca {a["toca"]}, modelo {a["modelo"]}, '
          f'{"sem problemas" if not problemas else problemas}')
    pos = e.posicoes(a)
    tris = e.triangulos(a['modelo'])
    todos = pos.reshape(-1, 3)
    centro = (todos.min(0) + todos.max(0)) / 2
    raio = float(np.linalg.norm(todos - centro, axis=1).max()) or 1.0
    t = args.tamanho
    vistas = [raster.desenhar(pos[0], None, tris, t, g, 10, (centro, raio), amostras=2) for g in (0, 90, 180, 270)]
    chaves = [raster.desenhar(p, None, tris, t, 35, 10, (centro, raio), amostras=2) for p in pos]
    largura = max(4, min(len(chaves), 8))
    folha = raster.folha_de_contato(vistas + [vistas[0].copy().point(lambda _p: 0)] * (largura - 4) + chaves, largura,
                                    legenda=f'{args.animacao} lido só de out_c3: frente, lado, costas, outro lado; '
                                            f'depois as {len(chaves)} chaves')
    saida = args.saida or os.path.join(args.entrega, 'previews', f'ver3_{args.animacao}.png')
    folha.save(saida)
    print('salvo', saida)


if __name__ == '__main__':
    principal()
