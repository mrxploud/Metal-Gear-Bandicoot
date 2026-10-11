"""O disco do Crash 3 inteiro na memória: entradas únicas, em que fases aparecem, e a tabela do script do Crash.

Ler as 46 fases leva poucos segundos (no Crash 3 quase nenhuma página vem comprimida), então não há cache.
A mesma entrada (mesmo nome) pode ter versões diferentes em fases diferentes; guardamos todas e a mais comum
vem primeiro.
"""
import hashlib
import struct

import numpy as np

from . import formatos as fmt
from . import formatos3 as fmt3
from . import nsf

TIPOS = {1, 2, 5, 11, 12}


class Falsa:
    """Imita crashlib.nsf.Entrada para quem só precisa de nome e itens."""
    __slots__ = ('nome', 'itens', 'tipo')

    def __init__(self, nome, itens, tipo):
        self.nome, self.itens, self.tipo = nome, itens, tipo


class Banco3:
    def __init__(self):
        self.versoes = {}            # nome -> [{'h', 'tipo', 'itens', 'fases'}]
        self.por_fase = {}           # '0A' -> [(nome, tipo)]
        self._tgeo = {}

    def ler_disco(self, disco, fases=None, diga=None):
        for chave, (_lba, tam, caminho) in sorted(disco.arquivos().items()):
            if not chave.endswith('.NSF'):
                continue
            fase = chave[-6:-4]
            if fases and fase not in fases:
                continue
            nomes = []
            for e in nsf.entradas(disco.ler(chave)):
                nomes.append((e.nome, e.tipo))
                if e.tipo not in TIPOS:
                    continue
                h = hashlib.md5(b''.join(e.itens)).digest()
                vers = self.versoes.setdefault(e.nome, [])
                for v in vers:
                    if v['h'] == h:
                        v['fases'].append(fase)
                        break
                else:
                    vers.append({'h': h, 'tipo': e.tipo, 'itens': [bytes(i) for i in e.itens], 'fases': [fase]})
            self.por_fase[fase] = nomes
            if diga:
                diga(f'  {caminho}: {tam // 1024} KB, {len(nomes)} entradas')
        for vers in self.versoes.values():
            vers.sort(key=lambda v: -len(v['fases']))

    def tem(self, nome, tipo=None):
        v = self.versoes.get(nome)
        return bool(v) and (tipo is None or v[0]['tipo'] == tipo)

    def entrada(self, nome, versao=0):
        v = self.versoes[nome][versao]
        return Falsa(nome, v['itens'], v['tipo'])

    def fases(self, nome):
        return sorted({f for v in self.versoes.get(nome, ()) for f in v['fases']})

    def tgeo(self, nome):
        if nome not in self._tgeo:
            self._tgeo[nome] = fmt3.Tgeo3(self.entrada(nome))
        return self._tgeo[nome]

    def svtx(self, nome):
        return fmt3.Svtx3(self.entrada(nome))

    # -- a tabela de animações de um script GOOL --------------------------------------------------------
    def tabela(self, codigo):
        """Junta todas as versões do script: [{indice, anim, modelos, toca, interpola, fases}] na ordem da tabela."""
        tab = {}
        for v in self.versoes.get(codigo, ()):
            if len(v['itens']) < 6:
                continue
            for g in grupos_de_quadros(v['itens'][5]):
                if g['tipo'] != 'vtx' or not self.tem(g['anim'], 1):
                    continue
                t = tab.setdefault((g['pos'], g['anim']), {
                    'indice': g['pos'] // 20, 'pos': g['pos'], 'anim': g['anim'], 'modelos': [], 'toca': g['quadros'],
                    'interpola': bool(g['lerp']), 'fases': set()})
                if g['modelo'] not in t['modelos'] and self.tem(g['modelo'], 2):
                    t['modelos'].append(g['modelo'])
                t['fases'].update(v['fases'])
        return [dict(t, fases=sorted(t['fases'])) for _k, t in sorted(tab.items())]


def grupos_de_quadros(item):
    """A tabela de "grupos de quadros" (item 5) de um script GOOL do Crash 3. Conferido com o GOOLEntryLoader
    e os *Group2/3 do CrashEdit."""
    saida = []
    i = 0
    while i + 2 < len(item):
        ini = i
        tipo, n = struct.unpack_from('<hh', item, i)
        if tipo == 1:                                       # animação de vértices: 20 bytes
            lerp, num, modelo, eid = struct.unpack_from('<iiII', item, i + 4)
            saida.append({'pos': ini, 'tipo': 'vtx', 'quadros': n, 'lerp': lerp, 'num': num,
                          'modelo': nsf.nome_do_eid(modelo), 'anim': nsf.nome_do_eid(eid)})
            i += 20
        elif tipo == 2:                                     # sprites: 16 bytes por quadro
            eid, = struct.unpack_from('<I', item, i + 4)
            saida.append({'pos': ini, 'tipo': 'sprite', 'quadros': n, 'pagina': nsf.nome_do_eid(eid),
                          'dados': item[i + 8:i + 8 + 16 * n]})
            i += 8 + 16 * n
        elif tipo == 3:                                     # fonte: 20 bytes por letra
            eid, = struct.unpack_from('<I', item, i + 4)
            saida.append({'pos': ini, 'tipo': 'fonte', 'quadros': n, 'pagina': nsf.nome_do_eid(eid)})
            i += 8 + 20 * n
        elif tipo == 4:                                     # textos
            i += 12
            textos = []
            for _ in range(n):
                fim = item.index(b'\0', i)
                textos.append(item[i:fim].decode('latin-1'))
                i = fim + 1
            i = (i + 3) & ~3
            saida.append({'pos': ini, 'tipo': 'texto', 'quadros': n, 'textos': textos})
        elif tipo == 5:                                     # imagem em partes: 24 bytes por parte
            eid, partes = struct.unpack_from('<Ii', item, i + 4)
            saida.append({'pos': ini, 'tipo': 'imagem', 'quadros': n, 'pagina': nsf.nome_do_eid(eid)})
            i += 12 + 24 * partes * n
        else:
            saida.append({'pos': ini, 'tipo': f'?{tipo}'})
            i += 4
    return saida


# ------------------------------------------------------------------------------------------------------
# Texturas e desenho (para as prévias)
# ------------------------------------------------------------------------------------------------------
class Paginas:
    """As páginas de textura decodificadas com cada paleta pedida (uma imagem RGBA por página + paleta)."""

    def __init__(self, banco):
        self.banco = banco
        self.imagens = {}

    def dados(self, nome):
        return self.banco.versoes[nome][0]['itens'][0] if self.banco.tem(nome, 5) else None

    def imagem(self, nome, modo, clut_x, clut_y):
        chave = (nome, modo, clut_x, clut_y)
        if chave not in self.imagens:
            dados = self.dados(nome)
            if dados is None:
                self.imagens[chave] = None
            else:
                bruto = np.frombuffer(dados, np.uint8).reshape(128, 512)
                if modo == 0:
                    idx = np.empty((128, 1024), np.uint8)
                    idx[:, 0::2] = bruto & 0xF
                    idx[:, 1::2] = bruto >> 4
                elif modo == 1:
                    idx = bruto
                else:
                    idx = None
                if idx is not None:
                    pal = np.array([fmt.cor_ps1(p) for p in fmt.paleta(dados, clut_x, clut_y, modo)], np.uint8)
                    self.imagens[chave] = pal[idx]
                else:
                    palavras = np.frombuffer(dados, '<u2').reshape(128, 256)
                    self.imagens[chave] = np.array([fmt.cor_ps1(int(p)) for p in palavras.ravel()],
                                                   np.uint8).reshape(128, 256, 4)
        return self.imagens[chave]


def para_desenhar(tgeo, paginas, quadro_de_textura=0):
    """A lista de triângulos de um Tgeo3 no formato de crashlib.raster.desenhar (cores por canto)."""
    lista = []
    for t in tgeo.triangulos:
        tex = tgeo.textura_do_triangulo(t, quadro_de_textura)
        cores = [tgeo.cores[i][:3] for i in t['cor']]
        d = {'v': t['v'], 'mistura': None}
        img = None
        if tex is not None and tex.pagina < len(tgeo.paginas):
            img = paginas.imagem(nsf.nome_do_eid(tgeo.paginas[tex.pagina]), tex.modo_de_cor, tex.clut_x, tex.clut_y)
        if img is not None:
            uv = tex.uvs()
            d['textura'] = img
            d['uvs'] = [(uv[k][0] + 0.5, uv[k][1] + 0.5) for k in t['cantos']]
            d['rgbs'] = cores                               # com textura, 128 = a cor da textura sem mudar
            d['mistura'] = None if tex.mistura == 3 else tex.mistura
        else:
            d['rgbs'] = [tuple(min(255, c * 2) for c in cor) for cor in cores]
        lista.append(d)
    return lista
