#!/usr/bin/env python
"""Tira o Crash do disco do Crash Bandicoot 1 e entrega no contrato do quadro (MGB_board.md, contrato v1).

    python -I extrair.py --disco "D:\\...\\discs\\Crash Bandicoot (USA).cue"
    python -I extrair.py --pasta <pasta com os .NSF>          (se os arquivos já estiverem fora do disco)

Saída (padrão: crash_assets/out/):
    indice.json            tudo o que existe no disco: nome, tipo, em que fases aparece
    model.json             modelos, materiais, animações, conversão aplicada, orçamento de memória
    anim_<NOME>.bin        int16 [quadro][vértice][x,y,z], depois int8 [quadro][vértice][nx,ny,nz]
    tex/                   páginas originais (.bin, 64 KB), prévias .png e o atlas compacto
    snd/                   .vag (ADPCM original do SPU) e .wav (para conferir)
    previews/              folha de contato e GIF de cada animação (material do vídeo)
    CATALOGO.md            a lista de animações com as prévias

Nada aqui é redesenhado: o modelo, as animações, as cores e as texturas são os bytes do disco, convertidos.
Formatos: c1 (wurlyfox). Nomes das animações e dos sons: goocdump (ManDude).
"""
import argparse
import hashlib
import json
import os
import re
import struct
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import numpy as np                                             # noqa: E402
from PIL import Image                                          # noqa: E402

from crashlib import disco as cd                               # noqa: E402
from crashlib import formatos as fmt                           # noqa: E402
from crashlib import nsf                                       # noqa: E402
from crashlib import raster                                    # noqa: E402

REPOS = os.path.normpath(os.path.join(AQUI, '..', 'repos'))
GOOC = os.path.join(REPOS, 'goocdump', 'Crash 1', 'NTSC-J')
GFX_C = os.path.join(REPOS, 'c1', 'src', 'gfx.c')

# grupo de saída -> executável GOOL (o "programa" do objeto dentro do jogo) de onde vêm os nomes
GRUPOS = {'crash': 'WillC', 'caixas': 'BoxsC', 'aku': 'DoctC', 'sombra': 'ShadC', 'assistente': 'LabAC'}
ALTURA_ALVO = 1000.0                 # contrato v1: o Crash parado mede exatamente 1000 unidades
REFERENCIA = 'WILLY_STANCE1'         # a animação que define a altura e onde ficam os pés
TAXA_DOS_SONS = 11025                # o tom "normal" do script é soundpitch(4.0) = 0x400 no SPU = 11025 Hz;
                                     # a voz do Crash toca em 3.6 a 4.4 sorteado (SoundPitchDefault no goocdump)
FPS = 30                             # o Crash 1 roda a 30 quadros por segundo


def diga(*a):
    print(*a, flush=True)


# ------------------------------------------------------------------------------------------------------
# 1. Abrir o disco e catalogar tudo
# ------------------------------------------------------------------------------------------------------
def fontes(args):
    """Gera (rótulo da fase, bytes do .NSF)."""
    if args.disco:
        d = cd.Disco(args.disco)
        sistema, volume = d.identificacao()
        serial = d.serial_ps1()
        diga(f'disco: {args.disco}\n  sistema "{sistema}", volume "{volume}", serial {serial}')
        if serial != 'SCUS_949.00':
            diga(f'  AVISO: o disco esperado é SCUS_949.00 (Crash Bandicoot, EUA). Este é {serial}.')
        nomes = sorted(c for c in d.arquivos() if c.endswith('.NSF'))
        for nome in nomes:
            rotulo = os.path.splitext(os.path.basename(nome))[0]
            if args.fases and rotulo[-2:].upper() not in args.fases:
                continue
            yield rotulo, d.ler(nome), serial
        d.fechar()
    else:
        for raiz, _, arqs in os.walk(args.pasta):
            for arq in sorted(arqs):
                if arq.upper().endswith('.NSF'):
                    rotulo = os.path.splitext(arq)[0]
                    if args.fases and rotulo[-2:].upper() not in args.fases:
                        continue
                    with open(os.path.join(raiz, arq), 'rb') as f:
                        yield rotulo, f.read(), None


class Banco:
    """Todas as entradas de todas as fases, sem repetição."""

    def __init__(self):
        self.entrada = {}            # nome -> Entrada (a primeira vista)
        self.fases = {}              # nome -> [fases]
        self.versoes = {}            # nome -> {sha1 do conteúdo}
        self.serial = None
        self.n_fases = 0

    def carregar(self, args):
        t0 = time.time()
        for rotulo, dados, serial in fontes(args):
            self.serial = serial or self.serial
            self.n_fases += 1
            n = 0
            try:
                for e in nsf.entradas(dados):
                    n += 1
                    resumo = hashlib.sha1(b''.join(e.itens)).hexdigest()[:12]
                    onde = self.fases.setdefault(e.nome, [])
                    if rotulo not in onde:               # dentro de um .NSF a mesma entrada pode vir duas vezes
                        onde.append(rotulo)
                    self.versoes.setdefault(e.nome, set()).add(resumo)
                    self.entrada.setdefault(e.nome, e)
            except nsf.ErroDeNSF as erro:
                diga(f'  {rotulo}: parou em "{erro}" depois de {n} entradas')
            diga(f'  {rotulo}: {len(dados) / 1e6:5.1f} MB, {n} entradas')
        diga(f'{self.n_fases} fases, {len(self.entrada)} entradas diferentes, {time.time() - t0:.0f} s')

    def tem(self, nome):
        return nome in self.entrada

    def indice(self):
        return {nome: {'tipo': e.nome_do_tipo, 'itens': len(e.itens), 'bytes': sum(map(len, e.itens)),
                       'fases': self.fases[nome], 'versoes': len(self.versoes[nome])}
                for nome, e in sorted(self.entrada.items())}


# ------------------------------------------------------------------------------------------------------
# 2. Os nomes: o que o goocdump diz, e o que o disco diz
# ------------------------------------------------------------------------------------------------------
_RE_ANIM = re.compile(r'#anim\s+(\w+)\s+(?:#iflev\s+\w+\s+\[\w{5}\]\s+#else\s+)?\[([\w!]{5})\](?:\s+#endif)?\s+(\d+)')
_RE_SOM = re.compile(r'\[([\w!]{4}A)\]')


def animacoes_do_gooc(executavel):
    """[(nome, entrada SVTX, quadros)] de um .gooc do goocdump (versão japonesa; os nomes valem para todas)."""
    caminho = os.path.join(GOOC, executavel + '.gooc')
    if not os.path.isfile(caminho):
        caminho = os.path.join(GOOC, executavel + '..gooc')      # o BrioC tem um ponto a mais no repositório
    vistos, saida, sons = set(), [], []
    with open(caminho, encoding='utf-8', errors='replace') as f:
        texto = f.read()
    for nome, eid, quadros in _RE_ANIM.findall(texto):
        if (nome, eid) not in vistos:
            vistos.add((nome, eid))
            saida.append((nome, eid, int(quadros)))
    for som in _RE_SOM.findall(texto):
        if som not in sons:
            sons.append(som)
    return saida, sons


def animacoes_do_gool(entrada, banco):
    """O que o PRÓPRIO disco diz: varre o item 5 do executável GOOL atrás de animações de vértice e de sprite.

    Cada animação começa com {tipo, 0, comprimento, 0}; tipo 1 = vértices (segue o nome do SVTX),
    tipo 2 = sprite (segue a página de textura e `comprimento` texinfos de 8 bytes).
    """
    if len(entrada.itens) < 6:
        return [], []
    blob = entrada.itens[5]
    vertices, sprites = [], []
    for pos in range(0, len(blob) - 7, 4):
        tipo, z1, comprimento, z2 = blob[pos:pos + 4]
        if z1 or z2 or not comprimento:
            continue
        eid, = struct.unpack_from('<I', blob, pos + 4)
        if not eid & 1:
            continue
        nome = nsf.nome_do_eid(eid)
        if tipo == 1 and nome.endswith('V'):
            vertices.append({'palavra': pos // 4, 'svtx': nome, 'quadros': comprimento, 'no_disco': banco.tem(nome)})
        elif tipo == 2 and nome.endswith('T') and pos + 8 + comprimento * 8 <= len(blob):
            quadros = [fmt_sprite(blob, pos + 8 + k * 8, eid) for k in range(comprimento)]
            sprites.append({'palavra': pos // 4, 'pagina': nome, 'quadros': quadros})
    return vertices, sprites


def fmt_sprite(blob, pos, pagina):
    """Um texinfo2 de sprite (cor + região), montado como Material para reaproveitar o cálculo de UV."""
    cor = blob[pos:pos + 4]
    regiao = blob[pos + 4:pos + 8]
    return fmt.Material(cor[:3] + bytes([cor[3] | 0x80]) + struct.pack('<I', pagina) + regiao, 0)


# ------------------------------------------------------------------------------------------------------
# 3. Geometria
# ------------------------------------------------------------------------------------------------------
class Conversao:
    """Dos bytes do SVTX para o espaço do contrato: pés em y=0, Y para cima, frente +Z, Crash = 1000 de altura."""

    def __init__(self, config):
        self.eixos = config.get('eixos', [1, 1, 1])            # sinal de cada eixo; decidido olhando as prévias
        self.troca = config.get('ordem', [0, 1, 2])             # permutação dos eixos
        self.fator = 1.0
        self.chao = 0.0

    def cru(self, quadro, tgeo, n):
        """Vértices com a escala do TGEO aplicada (ponto fixo 4.12), ainda sem normalizar."""
        v = np.array(quadro.vertices(n), np.float64)
        v *= np.array(tgeo.escala, np.float64) / 4096.0
        return v[:, self.troca] * np.array(self.eixos, np.float64)

    def calibrar(self, quadro, tgeo, n):
        v = self.cru(quadro, tgeo, n)
        self.chao = float(v[:, 1].min())
        altura = float(v[:, 1].max()) - self.chao
        self.fator = ALTURA_ALVO / altura
        return altura

    def posicoes(self, quadro, tgeo, n):
        v = self.cru(quadro, tgeo, n)
        v[:, 1] -= self.chao
        return v * self.fator

    def normais(self, quadro, n):
        v = np.array(quadro.normais(n), np.float64)
        return v[:, self.troca] * np.array(self.eixos, np.float64)

    def ponto(self, p, tgeo):
        v = np.array(p, np.float64) * 4.0 * np.array(tgeo.escala, np.float64) / 4096.0
        v = v[self.troca] * np.array(self.eixos, np.float64)
        v[1] -= self.chao
        return (v * self.fator).round(1).tolist()

    def descricao(self):
        return {
            'formula': 'pos = troca(((origem_do_quadro - 128) + byte) * 4 * escala_tgeo / 4096) * sinais; '
                       'pos.y -= chao; pos *= fator',
            'fonte': 'c1 src/pc/gfx/soft.c SwTransformSvtx + SwCalcObjectRotMatrix',
            'ordem_dos_eixos': self.troca, 'sinais': self.eixos, 'chao': self.chao, 'escala_original': self.fator,
            'altura_do_crash_parado': ALTURA_ALVO, 'referencia': REFERENCIA,
            'nota': 'a escala do objeto (GOOL) não entra aqui; no jogo ela multiplica a escala do TGEO',
        }


def retangulo(mat, uv_map, sprite=False):
    """(x, y, largura, altura) do pedaço de textura de um material, em pixels da página.

    Na tabela uv_map do c1, as entradas que só servem para triângulo trazem (99, 99) no quarto canto: é um
    marcador de "não existe", não uma coordenada. Um sprite usa os 4 cantos; um triângulo, os 3 primeiros.
    """
    ppi = 2 << (2 - mat.modo_de_cor)
    ox, oy = (mat.segmento * 32 + mat.desl_x) * ppi, mat.desl_y * 4
    cantos = [p for p in uv_map[mat.uv_idx][:4 if sprite else 3] if p != (99, 99)]
    x0, y0 = min(p[0] for p in cantos), min(p[1] for p in cantos)
    x1, y1 = max(p[0] for p in cantos), max(p[1] for p in cantos)
    return ox + x0, oy + y0, x1 - x0 + 1, y1 - y0 + 1


class Texturas:
    """Guarda as páginas usadas e monta o atlas compacto (só os retângulos que os modelos usam)."""

    def __init__(self, banco, uv_map):
        self.banco, self.uv_map = banco, uv_map
        self.paginas = {}            # nome -> bytes (64 KB)
        self.regioes = {}            # (pagina, modo, clut_x, clut_y, x, y, l, a) -> id
        self.imagens = {}            # (pagina, modo, clut_x, clut_y) -> array RGBA da página inteira

    def pagina(self, eid):
        nome = nsf.nome_do_eid(eid)
        if nome not in self.paginas:
            if not self.banco.tem(nome):
                return None, nome
            self.paginas[nome] = self.banco.entrada[nome].itens[0]
        return self.paginas[nome], nome

    def imagem(self, mat):
        """A página inteira decodificada com a paleta deste material (para a prévia)."""
        dados, nome = self.pagina(mat.pagina)
        if dados is None:
            return None
        chave = (nome, mat.modo_de_cor, mat.clut_x, mat.clut_y)
        if chave not in self.imagens:
            larg = fmt.largura_da_pagina(mat.modo_de_cor)
            bruto = np.frombuffer(dados, np.uint8).reshape(128, 512)
            if mat.modo_de_cor == 0:
                idx = np.empty((128, 1024), np.uint8)
                idx[:, 0::2] = bruto & 0xF
                idx[:, 1::2] = bruto >> 4
            elif mat.modo_de_cor == 1:
                idx = bruto
            else:
                idx = None
            if idx is not None:
                pal = np.array([fmt.cor_ps1(p) for p in fmt.paleta(dados, mat.clut_x, mat.clut_y, mat.modo_de_cor)], np.uint8)
                img = pal[idx]
            else:
                palavras = np.frombuffer(dados, '<u2').reshape(128, 256)
                img = np.array([fmt.cor_ps1(int(p)) for p in palavras.ravel()], np.uint8).reshape(128, 256, 4)
            assert img.shape[1] == larg
            self.imagens[chave] = img
        return self.imagens[chave]

    def registrar(self, mat):
        """Anota o retângulo de textura deste material. Devolve (id da região, uvs relativos ao retângulo)."""
        dados, nome = self.pagina(mat.pagina)
        if dados is None:
            return None, None
        uvs = mat.uvs(self.uv_map)
        x0, y0, larg, alt = retangulo(mat, self.uv_map)
        chave = (nome, mat.modo_de_cor, mat.clut_x, mat.clut_y, x0, y0, larg, alt)
        if chave not in self.regioes:
            self.regioes[chave] = len(self.regioes)
        return self.regioes[chave], [(u - x0, v - y0) for u, v in uvs]

    def exportar(self, pasta):
        """Grava as páginas originais, as prévias e o atlas. Devolve a descrição para o model.json."""
        os.makedirs(pasta, exist_ok=True)
        for nome, dados in self.paginas.items():
            with open(os.path.join(pasta, f'pagina_{nome}.bin'), 'wb') as f:
                f.write(dados)
        for (nome, modo, cx, cy), img in self.imagens.items():
            Image.fromarray(img, 'RGBA').save(os.path.join(pasta, f'pagina_{nome}_m{modo}_clut{cx}_{cy}.png'))
        # paletas: uma por (pagina, modo, clut)
        cluts, lista_cluts = {}, []
        for (nome, modo, cx, cy, *_r) in self.regioes:
            if modo < 2 and (nome, modo, cx, cy) not in cluts:
                cluts[(nome, modo, cx, cy)] = len(lista_cluts)
                lista_cluts.append({'id': len(lista_cluts), 'pagina': nome, 'bits': (4, 8)[modo], 'clut_x': cx, 'clut_y': cy,
                                    'cores_ps1': [f'{p:04x}' for p in fmt.paleta(self.paginas[nome], cx, cy, modo)]})
        # atlas por profundidade de cor, prateleira simples; largura em pixels múltipla de 16 (4 bits) ou 8 (8 bits)
        regioes, atlas = [None] * len(self.regioes), {}
        for bits, modo, larg_atlas in ((4, 0, 256), (8, 1, 256), (16, 2, 128)):
            itens = sorted((k for k in self.regioes if k[1] == modo), key=lambda k: (-k[7], -k[6]))
            if not itens:
                continue
            x = y = prateleira = 0
            vagas = []
            for k in itens:
                l, a = k[6], k[7]
                if x + l > larg_atlas:
                    x, y, prateleira = 0, y + prateleira, 0
                vagas.append((k, x, y))
                x += l
                prateleira = max(prateleira, a)
            alt_atlas = y + prateleira
            indices = np.zeros((alt_atlas, larg_atlas), np.uint16)
            previa = np.zeros((alt_atlas, larg_atlas, 4), np.uint8)
            for k, ax, ay in vagas:
                nome, _, cx, cy, x0, y0, l, a = k
                dados = self.paginas[nome]
                for yy in range(a):
                    for xx in range(l):
                        indices[ay + yy, ax + xx] = fmt.indice_do_pixel(dados, x0 + xx, y0 + yy, modo)
                img = self.imagens.get((nome, modo, cx, cy))
                if img is not None:
                    previa[ay:ay + a, ax:ax + l] = img[y0:y0 + a, x0:x0 + l]
                regioes[self.regioes[k]] = {
                    'id': self.regioes[k], 'bits': bits, 'atlas': f'atlas_{bits}bits', 'x': ax, 'y': ay, 'l': l, 'a': a,
                    'clut': cluts.get((nome, modo, cx, cy)), 'origem': {'pagina': nome, 'x': x0, 'y': y0}}
            Image.fromarray(previa, 'RGBA').save(os.path.join(pasta, f'atlas_{bits}bits.png'))
            # dados crus do atlas no formato da VRAM: 4 bits = 2 pixels por byte (o da esquerda no nibble baixo)
            if bits == 4:
                cru = (indices[:, 0::2] | (indices[:, 1::2] << 4)).astype(np.uint8).tobytes()
            elif bits == 8:
                cru = indices.astype(np.uint8).tobytes()
            else:
                cru = indices.astype('<u2').tobytes()
            with open(os.path.join(pasta, f'atlas_{bits}bits.bin'), 'wb') as f:
                f.write(cru)
            atlas[f'atlas_{bits}bits'] = {
                'bits': bits, 'largura_px': larg_atlas, 'altura_px': alt_atlas,
                'largura_vram': larg_atlas * bits // 16, 'bytes': len(cru),
                'formato': 'índices de paleta linha a linha, como na VRAM do PS1' if bits < 16 else 'cores de 15 bits'}
        return {'atlas': atlas, 'regioes': regioes, 'cluts': lista_cluts,
                'paginas_originais': sorted(self.paginas)}


class Modelo:
    """Um TGEO pronto para exportar: vértices usados, triângulos e materiais sem repetição."""

    def __init__(self, tgeo, texturas):
        self.tgeo = tgeo
        self.n = tgeo.n_vertices_usados
        self.materiais, indice = [], {}
        self.triangulos = []                          # [a, b, c, material]
        self.para_desenhar = []                       # o mesmo, no formato do rasterizador
        self.faltam_paginas = set()
        for a, b, c, palavra, liso in tgeo.triangulos:
            mat = tgeo.materiais_por_palavra.get(palavra)
            if mat is None:
                raise ValueError(f'{tgeo.nome}: triângulo aponta para o material {palavra}, que não existe')
            regiao = uvs = imagem = None
            if mat.texturizado:
                regiao, uvs = texturas.registrar(mat)
                if regiao is None:
                    self.faltam_paginas.add(nsf.nome_do_eid(mat.pagina))
                else:
                    imagem = texturas.imagem(mat)
            chave = (mat.chave(), liso)
            if chave not in indice:
                indice[chave] = len(self.materiais)
                self.materiais.append({
                    'rgb': list(mat.rgb), 'liso': bool(liso), 'textura': regiao, 'uv': uvs,
                    'clut': None, 'modo_de_mistura': mat.mistura,
                    'bits': mat.bits_por_pixel() if mat.texturizado else 0,
                    'sem_descarte_de_costas': bool(mat.sem_descarte)})
            self.triangulos.append([a, b, c, indice[chave]])
            desenho = {'v': (a, b, c), 'rgb': mat.rgb, 'liso': bool(liso),
                       'mistura': None if mat.mistura == 3 else mat.mistura}
            if imagem is not None:
                desenho['textura'] = imagem
                desenho['uvs'] = mat.uvs(texturas.uv_map)
            self.para_desenhar.append(desenho)


# ------------------------------------------------------------------------------------------------------
# 4. Exportar um grupo (crash, caixas, aku...)
# ------------------------------------------------------------------------------------------------------
def exportar_grupo(grupo, lista, banco, texturas, conv, saida, args, relatorio):
    modelos, animacoes = {}, []
    pasta_previas = os.path.join(saida, 'previews', grupo)
    os.makedirs(pasta_previas, exist_ok=True)
    for nome, svtx_nome, quadros_no_script in lista:
        registro = {'nome': nome, 'grupo': grupo, 'origem_no_disco': svtx_nome, 'quadros_no_script': quadros_no_script}
        if not banco.tem(svtx_nome):
            registro['ausente'] = 'a entrada não existe nas fases lidas'
            animacoes.append(registro)
            continue
        entrada = banco.entrada[svtx_nome]
        if entrada.tipo != 1:
            registro['ausente'] = f'entrada do tipo {entrada.nome_do_tipo} (ainda não convertida)'
            animacoes.append(registro)
            continue
        sv = fmt.Svtx(entrada)
        nomes_tgeo = sv.tgeos
        if len(nomes_tgeo) != 1 or not banco.tem(nomes_tgeo[0]):
            registro['ausente'] = f'modelo(s) {nomes_tgeo} não encontrado(s) ou mais de um por animação'
            animacoes.append(registro)
            continue
        nome_tgeo = nomes_tgeo[0]
        if nome_tgeo not in modelos:
            modelos[nome_tgeo] = Modelo(fmt.Tgeo(banco.entrada[nome_tgeo]), texturas)
        modelo = modelos[nome_tgeo]
        n = modelo.n
        curtos = [i for i, q in enumerate(sv.quadros) if q.n_vertices < n]
        if curtos:
            registro['ausente'] = f'quadros {curtos} têm menos vértices que o modelo usa ({n})'
            animacoes.append(registro)
            continue
        pos = np.stack([conv.posicoes(q, modelo.tgeo, n) for q in sv.quadros])
        nor = np.stack([conv.normais(q, n) for q in sv.quadros])
        if np.abs(pos).max() > 32767:
            registro['ausente'] = 'coordenadas não cabem em int16'
            animacoes.append(registro)
            continue
        arquivo = f'anim_{nome}.bin'
        with open(os.path.join(saida, arquivo), 'wb') as f:
            f.write(np.round(pos).astype('<i2').tobytes())
            f.write(np.clip(nor, -128, 127).astype(np.int8).tobytes())
        # a versão compacta: os bytes do disco como estão (3 de posição + 3 de normal por vértice)
        os.makedirs(os.path.join(saida, 'cru'), exist_ok=True)
        with open(os.path.join(saida, 'cru', f'{nome}.bin'), 'wb') as f:
            for q in sv.quadros:
                f.write(struct.pack('<3hH', q.origem[0] - 128, q.origem[1] - 128, q.origem[2] - 128, n))
                f.write(q.bruto[:n * 6])
        k = [conv.fator * 4.0 * e / 4096.0 for e in modelo.tgeo.escala]
        registro['cru'] = {
            'arquivo': f'cru/{nome}.bin', 'bytes': len(sv.quadros) * (8 + n * 6),
            'por_quadro': 'int16 ox, oy, oz; uint16 n; depois n vezes {uint8 x, y, z; int8 nx, ny, nz}',
            'k': [round(v, 6) for v in k], 'chao': round(conv.chao * conv.fator, 3),
            'formula': 'pos = (o + byte) * k; pos.y -= chao   (dá exatamente o anim_<NOME>.bin, antes de arredondar)'}
        registro.update({
            'arquivo': arquivo, 'modelo': nome_tgeo, 'quadros': len(sv.quadros), 'fps': FPS, 'vertices': n,
            'bytes': len(sv.quadros) * n * 9, 'fases': banco.fases[svtx_nome][:6],
            'n_fases': len(banco.fases[svtx_nome]),
            'por_quadro': [{'caixa': [np.round(p.min(0), 1).tolist(), np.round(p.max(0), 1).tolist()],
                            'raiz': conv.ponto([c - 128 for c in q.origem], modelo.tgeo),
                            'colisao_bruta': list(q.colisao)} for p, q in zip(pos, sv.quadros)]})
        if not args.sem_previas:
            centro = (pos.reshape(-1, 3).min(0) + pos.reshape(-1, 3).max(0)) / 2
            raio = float(np.linalg.norm(pos.reshape(-1, 3) - centro, axis=1).max()) or 1.0
            imagens = [raster.desenhar(pos[i], nor[i], modelo.para_desenhar, args.tamanho, args.guinada, 12,
                                       (centro, raio)) for i in range(len(sv.quadros))]
            colunas = min(len(imagens), 8)
            raster.folha_de_contato(imagens, colunas, legenda=f'{nome}  [{svtx_nome}]  {len(imagens)} quadros').save(
                os.path.join(pasta_previas, f'{nome}.png'))
            raster.salvar_gif(imagens, os.path.join(pasta_previas, f'{nome}.gif'), FPS)
            registro['previa'] = f'previews/{grupo}/{nome}.png'
            registro['gif'] = f'previews/{grupo}/{nome}.gif'
        animacoes.append(registro)
        diga(f'  {grupo:7} {nome:28} [{svtx_nome}] {len(sv.quadros):3} quadros, {n:4} vértices, modelo {nome_tgeo}')
    for nome_tgeo, m in modelos.items():
        relatorio['modelos'][nome_tgeo] = {
            'grupo': grupo, 'vertices': m.n, 'triangulos': m.triangulos, 'materiais': m.materiais,
            'escala_tgeo': list(m.tgeo.escala), 'n_triangulos': len(m.triangulos),
            'n_texturizados': sum(1 for t in m.triangulos if m.materiais[t[3]]['textura'] is not None),
            'paginas_que_faltam': sorted(m.faltam_paginas)}
    relatorio['animacoes'] += animacoes


def exportar_sons(nomes, banco, saida):
    pasta = os.path.join(saida, 'snd')
    os.makedirs(pasta, exist_ok=True)
    lista = []
    for nome in nomes:
        if not banco.tem(nome):
            lista.append({'nome': nome, 'ausente': True})
            continue
        adpcm = banco.entrada[nome].itens[0]
        with open(os.path.join(pasta, f'{nome}.vag'), 'wb') as f:
            f.write(fmt.vag(adpcm, nome, TAXA_DOS_SONS))
        pcm = fmt.adpcm_para_pcm(adpcm)
        with open(os.path.join(pasta, f'{nome}.wav'), 'wb') as f:
            f.write(fmt.wav(pcm, TAXA_DOS_SONS))
        lista.append({'nome': nome, 'vag': f'snd/{nome}.vag', 'wav': f'snd/{nome}.wav', 'bytes_adpcm': len(adpcm),
                      'amostras': len(pcm), 'segundos_presumidos': round(len(pcm) / TAXA_DOS_SONS, 2),
                      'n_fases': len(banco.fases[nome])})
    return lista


def exportar_sprites(sprites, texturas, saida, grupo):
    """Recorta cada quadro de sprite (a Wumpa, por exemplo) da página de textura, com a paleta certa."""
    pasta = os.path.join(saida, 'sprites', grupo)
    lista = []
    for s in sprites:
        quadros = []
        for k, mat in enumerate(s['quadros']):
            img = texturas.imagem(mat)
            if img is None:
                continue
            x0, y0, l, a = retangulo(mat, texturas.uv_map, sprite=True)
            os.makedirs(pasta, exist_ok=True)
            arquivo = f'sprite_{s["palavra"]:03d}_{k:02d}.png'
            Image.fromarray(img[y0:y0 + a, x0:x0 + l], 'RGBA').save(os.path.join(pasta, arquivo))
            regiao, _ = texturas.registrar(mat)
            quadros.append({'arquivo': f'sprites/{grupo}/{arquivo}', 'l': l, 'a': a, 'rgb': list(mat.rgb),
                            'regiao': regiao, 'bits': mat.bits_por_pixel()})
        if quadros:
            lista.append({'palavra': s['palavra'], 'pagina': s['pagina'], 'quadros': quadros})
    return lista


# ------------------------------------------------------------------------------------------------------
# 5. Programa
# ------------------------------------------------------------------------------------------------------
def catalogo_md(relatorio, caminho):
    linhas = ['# Catálogo do que saiu do disco do Crash', '',
              f'Disco: {relatorio["disco"]["serial"]} · gerado por `extrair.py` · nomes: goocdump (ManDude); '
              'formatos: c1 (wurlyfox).', '',
              'Dentro do jogo o Crash se chama **Willy** (de Willy the Wombat, o nome dele durante o '
              'desenvolvimento); por isso todas as animações dele são `WILLY_*`.', '']
    for grupo in GRUPOS:
        animacoes = [a for a in relatorio['animacoes'] if a['grupo'] == grupo]
        if not animacoes:
            continue
        linhas += [f'## {grupo}', '', '| Animação | Entrada | Quadros | Vértices | Bytes | Prévia |', '|---|---|---|---|---|---|']
        for a in animacoes:
            if 'ausente' in a:
                linhas.append(f'| `{a["nome"]}` | {a["origem_no_disco"]} | (script: {a["quadros_no_script"]}) | | | '
                              f'não exportada: {a["ausente"]} |')
            else:
                previa = f'![{a["nome"]}]({a["gif"]})' if 'gif' in a else ''
                linhas.append(f'| `{a["nome"]}` | {a["origem_no_disco"]} | {a["quadros"]} | {a["vertices"]} | '
                              f'{a["bytes"]:,} | {previa} |'.replace(',', '.'))
        linhas.append('')
    with open(caminho, 'w', encoding='utf-8') as f:
        f.write('\n'.join(linhas))


def principal():
    ap = argparse.ArgumentParser(description='Extrai o Crash do disco do Crash Bandicoot 1.')
    origem = ap.add_mutually_exclusive_group(required=True)
    origem.add_argument('--disco', help='imagem do disco (.cue, .bin, .img ou .iso)')
    origem.add_argument('--pasta', help='pasta com os arquivos .NSF já fora do disco')
    ap.add_argument('--saida', default=os.path.join(AQUI, 'out'))
    ap.add_argument('--fases', help='só estas fases, pelos 2 últimos caracteres do nome (ex.: 03,05,19)')
    ap.add_argument('--so-indice', action='store_true', help='só cataloga o disco (indice.json) e para')
    ap.add_argument('--sem-previas', action='store_true')
    ap.add_argument('--tamanho', type=int, default=160, help='lado de cada quadro de prévia, em pixels')
    ap.add_argument('--guinada', type=float, default=30, help='ângulo da câmera das prévias, em graus')
    args = ap.parse_args()
    args.fases = {f.strip().upper() for f in args.fases.split(',')} if args.fases else None
    sys.stdout.reconfigure(encoding='utf-8')
    os.makedirs(args.saida, exist_ok=True)

    banco = Banco()
    banco.carregar(args)
    if not banco.entrada:
        diga('nenhuma entrada lida: confira o caminho do disco')
        return 2
    with open(os.path.join(args.saida, 'indice.json'), 'w', encoding='utf-8') as f:
        json.dump(banco.indice(), f, ensure_ascii=False, indent=0)
    por_tipo = {}
    for e in banco.entrada.values():
        por_tipo[e.nome_do_tipo] = por_tipo.get(e.nome_do_tipo, 0) + 1
    diga('por tipo:', ', '.join(f'{k} {v}' for k, v in sorted(por_tipo.items())))
    if args.so_indice:
        return 0

    config = {}
    caminho_config = os.path.join(AQUI, 'config.json')
    if os.path.isfile(caminho_config):
        with open(caminho_config, encoding='utf-8') as f:
            config = json.load(f)
    conv = Conversao(config)
    texturas = Texturas(banco, fmt.carregar_uv_map(GFX_C))
    relatorio = {'contrato': 'MGB_board.md v1', 'disco': {'serial': banco.serial, 'fases_lidas': banco.n_fases},
                 'modelos': {}, 'animacoes': [], 'sons': [], 'sprites': {}, 'conferencia_com_o_disco': {}}

    # o Crash parado define a altura e o chão de tudo
    listas, sons = {}, []
    for grupo, executavel in GRUPOS.items():
        listas[grupo], s = animacoes_do_gooc(executavel)
        sons += [x for x in s if x not in sons]
    ref = next((a for a in listas['crash'] if a[0] == REFERENCIA), None)
    if ref is None or not banco.tem(ref[1]):
        diga(f'não achei {REFERENCIA} nas fases lidas; sem ela não há como fixar a escala')
        return 3
    sv = fmt.Svtx(banco.entrada[ref[1]])
    tg = fmt.Tgeo(banco.entrada[nsf.nome_do_eid(sv.quadros[0].tgeo)])
    altura = conv.calibrar(sv.quadros[0], tg, tg.n_vertices_usados)
    diga(f'{REFERENCIA}: altura original {altura:.1f} -> fator {conv.fator:.4f} (o Crash parado fica com {ALTURA_ALVO:.0f})')

    for grupo in GRUPOS:
        exportar_grupo(grupo, listas[grupo], banco, texturas, conv, args.saida, args, relatorio)
        executavel = GRUPOS[grupo]
        if banco.tem(executavel):
            vertices, sprites = animacoes_do_gool(banco.entrada[executavel], banco)
            do_script = {a[1] for a in listas[grupo]}
            relatorio['conferencia_com_o_disco'][executavel] = {
                'animacoes_no_disco': vertices,
                'no_disco_e_nao_no_script': sorted({v['svtx'] for v in vertices} - do_script),
                'no_script_e_nao_no_disco': sorted(do_script - {v['svtx'] for v in vertices})}
            relatorio['sprites'][grupo] = exportar_sprites(sprites, texturas, args.saida, grupo)
    # a Wumpa mora no executável das frutas
    if banco.tem('FruiC'):
        _, sprites = animacoes_do_gool(banco.entrada['FruiC'], banco)
        relatorio['sprites']['frutas'] = exportar_sprites(sprites, texturas, args.saida, 'frutas')
        _, s = animacoes_do_gooc('FruiC')
        sons += [x for x in s if x not in sons]

    relatorio['sons'] = exportar_sons(sons, banco, args.saida)
    relatorio['texturas'] = texturas.exportar(os.path.join(args.saida, 'tex'))
    for m in relatorio['modelos'].values():               # a paleta de cada material vem da região dele
        usadas = set()
        for mat in m['materiais']:
            if mat['textura'] is not None:
                mat['clut'] = relatorio['texturas']['regioes'][mat['textura']]['clut']
                usadas.add(mat['textura'])
        regs = [relatorio['texturas']['regioes'][r] for r in sorted(usadas)]
        m['texturas_do_modelo'] = {
            'regioes': sorted(usadas), 'cluts': sorted({r['clut'] for r in regs if r['clut'] is not None}),
            'area_px': sum(r['l'] * r['a'] for r in regs),
            'bytes_na_vram': sum(r['l'] * r['a'] * r['bits'] // 8 for r in regs),
            'tamanhos': sorted({f"{r['l']}x{r['a']}@{r['bits']}" for r in regs})}
    relatorio['modo_de_mistura'] = ('3 = opaco; 0 = média com o fundo; 1 = soma; 2 = subtrai do fundo '
                                    '(c1 src/pc/gfx/gl.c). No PS1 só vale para os texels com o bit 15 ligado.')
    relatorio['conversao'] = conv.descricao()
    relatorio['formato_anim'] = ('anim_<NOME>.bin = int16 little-endian [quadro][vértice][x,y,z] seguido de '
                                 'int8 [quadro][vértice][nx,ny,nz]; os vértices são os do modelo da animação')
    feitas = [a for a in relatorio['animacoes'] if 'arquivo' in a]
    relatorio['orcamento'] = {
        'animacoes': len(feitas), 'quadros': sum(a['quadros'] for a in feitas),
        'bytes_das_animacoes': sum(a['bytes'] for a in feitas),
        'bytes_das_animacoes_cruas': sum(a['cru']['bytes'] for a in feitas),
        'por_grupo': {g: sum(a['bytes'] for a in feitas if a['grupo'] == g) for g in GRUPOS},
        'modelos': {n: {'vertices': m['vertices'], 'triangulos': m['n_triangulos'],
                        'texturizados': m['n_texturizados']} for n, m in relatorio['modelos'].items()},
        'texturas': {n: a['bytes'] for n, a in relatorio['texturas']['atlas'].items()},
        'cluts': len(relatorio['texturas']['cluts']),
        'sons_bytes_adpcm': sum(s.get('bytes_adpcm', 0) for s in relatorio['sons'])}
    with open(os.path.join(args.saida, 'model.json'), 'w', encoding='utf-8') as f:
        json.dump(relatorio, f, ensure_ascii=False, indent=1)
    catalogo_md(relatorio, os.path.join(args.saida, 'CATALOGO.md'))
    o = relatorio['orcamento']
    diga(f'\n{o["animacoes"]} animações, {o["quadros"]} quadros, {o["bytes_das_animacoes"] / 1024:.0f} KB; '
         f'{len(relatorio["modelos"])} modelos; {o["cluts"]} paletas; sons {o["sons_bytes_adpcm"] / 1024:.0f} KB')
    ausentes = [a for a in relatorio['animacoes'] if 'ausente' in a]
    if ausentes:
        diga(f'{len(ausentes)} animações do script não foram exportadas (ver model.json):')
        for a in ausentes:
            diga(f'  {a["nome"]} [{a["origem_no_disco"]}]: {a["ausente"]}')
    diga(f'saída em {args.saida}')
    return 0


if __name__ == '__main__':
    sys.exit(principal())
