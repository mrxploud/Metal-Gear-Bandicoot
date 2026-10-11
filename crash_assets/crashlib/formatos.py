"""Os formatos de dentro do NSF que interessam para tirar o Crash do jogo dele.

TGEO  o modelo: triângulos + a tabela de cores/texturas ("texinfo")
SVTX  a animação: um item por quadro, e cada quadro traz TODOS os vértices (x, y, z, normal) em 6 bytes
TPAG  página de textura: 64 KB = 256x128 palavras de VRAM (pixels de 4, 8 ou 16 bits, com as paletas dentro)
ADIO  som: ADPCM do SPU do PlayStation, cru

Tudo conferido contra o c1 de wurlyfox: src/formats/tgeo.h, svtx.h, src/geom.h (colinfo, rgninfo),
src/pc/gfx/soft.c (SwTransformSvtx) e src/pc/gfx/tex.c (TextureNew, TextureCopy).
Atenção: as macros BITFIELDS_nn do c1 declaram os campos de trás para a frente; o primeiro da lista é o bit
mais alto.
"""
import os
import re
import struct

from .nsf import nome_do_eid

TAM_VERTICE = 6
TAM_CABECALHO_QUADRO = 56


# ------------------------------------------------------------------------------------------------------
# uv_map: a tabela de 600 retângulos de textura do Crash 1. Em vez de copiar a tabela, lemos do c1.
# ------------------------------------------------------------------------------------------------------
def carregar_uv_map(caminho_gfx_c):
    """Lê `const quad28_t uv_map[600]` do src/gfx.c do c1. Devolve 600 listas de 4 pontos (u, v)."""
    with open(caminho_gfx_c, encoding='utf-8', errors='replace') as f:
        texto = f.read()
    ini = texto.index('uv_map[600]')
    ini = texto.index('{', ini)
    fim = texto.index('};', ini)
    numeros = [int(n) for n in re.findall(r'-?\d+', texto[ini:fim])]
    if len(numeros) != 600 * 8:
        raise ValueError(f'uv_map: esperava 4800 números, achei {len(numeros)}')
    return [[(numeros[i * 8 + k * 2], numeros[i * 8 + k * 2 + 1]) for k in range(4)] for i in range(600)]


# ------------------------------------------------------------------------------------------------------
# TGEO
# ------------------------------------------------------------------------------------------------------
class Material:
    """Um "texinfo" do TGEO: a cor do triângulo e, se tiver, o pedaço de textura."""
    __slots__ = ('rgb', 'texturizado', 'mistura', 'sem_descarte', 'clut_x', 'clut_y', 'pagina', 'uv_idx',
                 'modo_de_cor', 'segmento', 'desl_x', 'desl_y')

    def __init__(self, dados, pos):
        r, g, b, bits = struct.unpack_from('<4B', dados, pos)
        self.rgb = (r, g, b)
        self.clut_x = bits & 0xF
        self.sem_descarte = (bits >> 4) & 1
        self.mistura = (bits >> 5) & 3
        self.texturizado = bits >> 7
        self.pagina = None
        self.clut_y = self.uv_idx = self.modo_de_cor = self.segmento = self.desl_x = self.desl_y = 0
        if self.texturizado:
            pagina, regiao = struct.unpack_from('<II', dados, pos + 4)
            self.pagina = pagina                      # EID da página de textura
            self.desl_y = regiao & 0x1F
            self.clut_y = (regiao >> 6) & 0x7F
            self.desl_x = (regiao >> 13) & 0x1F
            self.segmento = (regiao >> 18) & 3
            self.modo_de_cor = (regiao >> 20) & 3      # 0 = 4 bits, 1 = 8 bits, 2 = 16 bits
            self.uv_idx = regiao >> 22

    @property
    def tamanho(self):
        return 12 if self.texturizado else 4

    def bits_por_pixel(self):
        return (4, 8, 16, 16)[self.modo_de_cor]

    def uvs(self, uv_map):
        """Os 3 cantos do triângulo, em pixels dentro da página de textura."""
        ppi = 2 << (2 - self.modo_de_cor)
        ox = (self.segmento * 32 + self.desl_x) * ppi
        oy = self.desl_y * 4
        quad = uv_map[self.uv_idx]
        return [(ox + quad[k][0], oy + quad[k][1]) for k in range(3)]

    def chave(self):
        return (self.rgb, self.texturizado, self.mistura, self.sem_descarte, self.clut_x, self.clut_y,
                self.pagina, self.uv_idx, self.modo_de_cor, self.segmento, self.desl_x, self.desl_y)


class Tgeo:
    def __init__(self, entrada):
        cab, pol = entrada.itens[0], entrada.itens[1]
        self.nome = entrada.nome
        n_tri, sx, sy, sz, n_palavras = struct.unpack_from('<IiiiI', cab, 0)
        self.escala = (sx, sy, sz)                    # ponto fixo 4.12, multiplicado pela escala do objeto
        self.materiais_por_palavra = {}                # deslocamento em palavras de 4 bytes -> Material
        # No disco, o campo que o c1 chama de texinfo_count conta PALAVRAS de 4 bytes da tabela, não materiais
        # (um material de cor ocupa 1 palavra, um com textura ocupa 3). Visto no WillG real: 122 palavras, 62 materiais.
        pos, fim = 20, min(len(cab), 20 + n_palavras * 4)
        while pos < fim:
            mat = Material(cab, pos)
            self.materiais_por_palavra[(pos - 20) // 4] = mat
            pos += mat.tamanho
        if pos != fim:
            raise ValueError(f'{self.nome}: a tabela de materiais não fecha ({pos} != {fim})')
        self.triangulos = []                           # (a, b, c, palavra do material, liso)
        for i in range(n_tri):
            a, b, c, w = struct.unpack_from('<4H', pol, i * 8)
            if a % TAM_VERTICE or b % TAM_VERTICE or c % TAM_VERTICE:
                raise ValueError(f'{self.nome}: triângulo {i} aponta para o meio de um vértice')
            self.triangulos.append((a // TAM_VERTICE, b // TAM_VERTICE, c // TAM_VERTICE, w & 0x7FFF, w >> 15))

    @property
    def n_vertices_usados(self):
        return 1 + max(max(t[0], t[1], t[2]) for t in self.triangulos)


# ------------------------------------------------------------------------------------------------------
# SVTX
# ------------------------------------------------------------------------------------------------------
class Quadro:
    __slots__ = ('tgeo', 'origem', 'caixa', 'colisao', 'bruto', 'n_vertices')

    def __init__(self, item):
        (_comprimento, tgeo, x, y, z, bx1, by1, bz1, bx2, by2, bz2, cx, cy, cz) = struct.unpack_from('<I I 3i 6i 3i', item, 0)
        self.tgeo = tgeo
        self.origem = (x, y, z)
        self.caixa = ((bx1, by1, bz1), (bx2, by2, bz2))
        self.colisao = (cx, cy, cz)
        self.bruto = item[TAM_CABECALHO_QUADRO:]
        self.n_vertices = len(self.bruto) // TAM_VERTICE

    def vertices(self, n=None):
        """[(x, y, z)] em unidades do modelo ANTES da escala do TGEO: ((origem - 128) + byte) * 4."""
        n = self.n_vertices if n is None else n
        ox, oy, oz = (c - 128 for c in self.origem)
        b = self.bruto
        return [((ox + b[i * 6]) * 4, (oy + b[i * 6 + 1]) * 4, (oz + b[i * 6 + 2]) * 4) for i in range(n)]

    def normais(self, n=None):
        n = self.n_vertices if n is None else n
        return [struct.unpack_from('<3b', self.bruto, i * 6 + 3) for i in range(n)]


class Svtx:
    def __init__(self, entrada):
        self.nome = entrada.nome
        self.quadros = [Quadro(item) for item in entrada.itens]

    @property
    def tgeos(self):
        return sorted({nome_do_eid(q.tgeo) for q in self.quadros})


# ------------------------------------------------------------------------------------------------------
# Texturas
# ------------------------------------------------------------------------------------------------------
def cor_ps1(p):
    """Palavra de 15 bits do PS1 -> (r, g, b, a) de 8 bits. Preto puro com o bit 15 zerado é transparente."""
    r = (p & 0x1F) * 255 // 31
    g = ((p >> 5) & 0x1F) * 255 // 31
    b = ((p >> 10) & 0x1F) * 255 // 31
    a = 0 if (p & 0x7FFF) == 0 and not (p >> 15) else 255
    return r, g, b, a


def paleta(pagina, clut_x, clut_y, modo_de_cor):
    """As cores cruas (16 ou 256 palavras) do CLUT que mora dentro da própria página de textura."""
    n = 16 if modo_de_cor == 0 else 256
    pos = (clut_x * 16 + clut_y * 256) * 2          # a página tem 256 palavras por linha
    return list(struct.unpack_from(f'<{n}H', pagina, pos))


def indice_do_pixel(pagina, x, y, modo_de_cor):
    """Valor cru do pixel (x, y): índice de paleta em 4/8 bits, ou a própria cor em 16 bits."""
    if modo_de_cor == 0:
        byte = pagina[y * 512 + x // 2]
        return (byte >> 4) & 0xF if x & 1 else byte & 0xF
    if modo_de_cor == 1:
        return pagina[y * 512 + x]
    return struct.unpack_from('<H', pagina, y * 512 + x * 2)[0]


def largura_da_pagina(modo_de_cor):
    return 1024 >> modo_de_cor


# ------------------------------------------------------------------------------------------------------
# Som
# ------------------------------------------------------------------------------------------------------
def vag(adpcm, nome, taxa):
    """Embrulha ADPCM cru do SPU num .VAG (o formato de som do kit do PlayStation)."""
    cab = struct.pack('>4sIIII12x16s', b'VAGp', 0x20, 0, len(adpcm) + 16, taxa, nome.encode('ascii')[:16])
    return cab + b'\x00' * 16 + adpcm


_FILTROS = ((0.0, 0.0), (60 / 64, 0.0), (115 / 64, -52 / 64), (98 / 64, -55 / 64), (122 / 64, -60 / 64))


def adpcm_para_pcm(adpcm):
    """Decodifica o ADPCM do SPU em amostras de 16 bits (para ouvir e conferir; o PS1 toca o original)."""
    saida = []
    s1 = s2 = 0.0
    for bloco in range(0, len(adpcm) - 15, 16):
        cabecalho = adpcm[bloco]
        desloca = cabecalho & 0xF
        filtro = min(cabecalho >> 4, 4)
        f0, f1 = _FILTROS[filtro]
        for i in range(2, 16):
            byte = adpcm[bloco + i]
            for nib in (byte & 0xF, byte >> 4):
                amostra = nib << 12
                if amostra & 0x8000:
                    amostra -= 0x10000
                amostra = (amostra >> desloca) if desloca <= 12 else (amostra >> 9)
                valor = amostra + s1 * f0 + s2 * f1
                valor = max(-32768.0, min(32767.0, valor))
                s2, s1 = s1, valor
                saida.append(int(valor))
        if adpcm[bloco + 1] & 1:                       # bandeira de fim
            break
    return saida


def wav(amostras, taxa):
    dados = struct.pack(f'<{len(amostras)}h', *amostras)
    return (b'RIFF' + struct.pack('<I', 36 + len(dados)) + b'WAVEfmt ' +
            struct.pack('<IHHIIHH', 16, 1, 1, taxa, taxa * 2, 2, 16) + b'data' + struct.pack('<I', len(dados)) + dados)


def existe(caminho):
    return os.path.isfile(caminho)
