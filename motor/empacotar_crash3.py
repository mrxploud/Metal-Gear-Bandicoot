"""Empacotador do Crash 3 (Warped) para o MGS: lê a entrega do Claude 2 (crash_assets/out_c3) e as caixas, sons
e marcas que continuam vindo do Crash 1 (crash_assets/out), e gera o C que entra no executável
(repos/mgs_reversing/source/crash/crash_data.c e .h) + o bloco lido do CD (motor/out/crash_cd.bin).

    python -I motor/empacotar_crash3.py [--altura 1100]

Quadros do Crash 3: sem perda, no mesmo espírito do formato do disco do Warped (descrito pelo Claude 2 em
crash_assets/ver3.py): cada vértice = vértice anterior + uma base fixa do modelo + uma diferença com poucos bits
(o número de bits é por vértice e por eixo, igual em todos os quadros do modelo). Cada quadro-chave guarda a
origem (s16 x3 + enchimento) e a fila de bits em palavras de 32 bits, do bit mais alto para o mais baixo.
No jogo: vértice = ((origem + byte) * escala[eixo]) >> 12. O Warped guarda as chaves a 15 qps e toca a 30
fazendo a média de duas vizinhas: o jogo faz o mesmo.
"""
import argparse
import json
import math
import os
import struct

FUSAO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT3 = os.path.join(FUSAO, 'crash_assets', 'out_c3')
OUT1 = os.path.join(FUSAO, 'crash_assets', 'out')
DEST = os.path.join(FUSAO, 'repos', 'mgs_reversing', 'source', 'crash')
BRF_ORIGINAL = os.path.join(FUSAO, 'motor', 'disco_mgs', 'MGSI_D1', 'MGS', 'BRF.DAT')
CD_SAIDA = os.path.join(FUSAO, 'motor', 'out', 'crash_cd.bin')

# nome na entrega -> (nome curto, laço?, levantar até o chão?) -- tabela v4 do Claude 2 (TABELA_SNAKE_CRASH3.md)
# laço 2 = meio ciclo: a última chave é a primeira espelhada (o engatinhar vai de uma mão na frente até a outra),
# então o jogo toca normal e depois espelhado em X, como a corrida do Crash 1 (bug do ByteMirage: "tremia num laço
# quebrado"; medido: chave 8 contra a chave 0 = 206 de distância, contra a chave 0 espelhada = 19)
ANIMS = [
    ('C3_PARADO', 'PARADO', 1, 0),
    ('C3_CORRER', 'CORRER', 1, 0),
    ('C3_AGACHAR', 'AGACHAR', 0, 0),
    ('C3_AGACHADO', 'AGACHADO', 1, 0),
    ('C3_ENGATINHAR', 'ENGATINHAR', 2, 0),
    ('C3_ENGATINHAR_PARADO', 'ENGATINHAR_PARADO', 0, 0),   # de agachado para de quatro: toca uma vez e segura
    ('C3_DERRAPADA', 'DERRAPADA', 0, 0),
    ('C3_GIRO_LEVE', 'GIRO', 1, 0),
    ('C3_BEIRADA_SUSTO', 'SUSTO', 0, 0),             # dano: braços abertos, olho arregalado (a cara do WOAH!)
    ('C3_CAI_DE_CARA', 'MORRER', 0, 1),               # vem de fase de gelo e afunda: sobe pela caixa do quadro
    ('C3_MORTE_OLHOS_E_TENIS', 'MORRER_TNT', 0, 1),   # explosão: sobram os olhos e os tênis
    ('C3_AKU_AKU', 'AKU', 0, 0),                      # a máscara (1 chave), segue o Crash
    ('C3_AKU_AKU_DOURADO', 'AKU_OURO', 0, 0),         # a 2a máscara
    # o pulo (pedido do ByteMirage depois do teste 8): sai do chão, sobe de braços para cima, cambalhota no alto (como
    # no Warped; começa e termina na pose de subir) e o pouso, que termina na pose de parado
    ('C3_PULO_SAIDA', 'PULO_SAIDA', 0, 0),
    ('C3_PULO_SUBINDO', 'PULO_SUBINDO', 0, 0),
    ('C3_PULO_CAMBALHOTA', 'PULO_CAMBALHOTA', 0, 0),
    ('C3_PULO_POUSO', 'PULO_POUSO', 0, 0),
]
# Tabelas de bits por grupo de animações. Cada vértice gasta os bits da maior diferença entre TODAS as chaves que
# dividem a tabela, e a cambalhota (o corpo girando) alargava a tabela do Cr10G inteiro. Sozinha, cada animação
# precisa de bem menos (o parado, 3,4 bits por vértice; a tabela única, 10,9), mas cada tabela a mais custa 1.373 bytes
# (base + bits em meio byte). Grupos achados juntando, de dois em dois, os que mais economizavam: o mesmo Crash, sem
# perda, ~4 KB menor (para o pulo caber na memória). O que não está aqui fica na tabela do próprio modelo.
GRUPO_DE_BITS = {
    'C3_PARADO': 'parado',
    'C3_AGACHAR': 'agachar', 'C3_AGACHADO': 'agachar', 'C3_PULO_POUSO': 'agachar',
    'C3_PULO_SAIDA': 'pulo', 'C3_PULO_SUBINDO': 'pulo', 'C3_PULO_CAMBALHOTA': 'pulo',
}
# o ponto do rosto (especiais[1]) por chave, para a máscara ir para a cara na invencibilidade (MGB #36 do Claude 2:
# medido em todas as animações do Cr10G); no giro (outro modelo) vale o nº 0, em cima da cabeça
ROSTO = {'Cr10G': 1, 'WiBcG': 0}

# caixas do Warped (6 faces; as do Crash 1 não tinham a face de trás, bug C3-8): caixa A, B, C do MGS, a contagem da
# TNT chutada e a do Aku Aku (no lugar das rações). A cara do Aku Aku é de 8 bits no disco: vai reduzida a 16 cores.
CAIXAS = [('C3_CAIXA_MADEIRA', 'MADEIRA'), ('C3_CAIXA_INTERROGACAO', 'PERGUNTA'), ('C3_CAIXA_TNT', 'TNT'),
          ('C3_CAIXA_TNT_3', 'TNT_3'), ('C3_CAIXA_TNT_2', 'TNT_2'), ('C3_CAIXA_TNT_1', 'TNT_1'),
          ('C3_CAIXA_AKU_AKU', 'AKU')]
CAIXA_LADO = 700   # lado no MGS (a do Warped mede 540 com o Crash em 1000)
CAIXA_NT = 12

# a bazuca de Wumpa (pedido 5 do ByteMirage): o Warped corta o Crash ao meio quando ele usa a bazuca (Cgt0G em cima,
# com a bazuca no ombro; Cgb0G, as pernas). Não cabe na RAM fixa: vai num bloco do CD que o jogo lê para a memória
# dinâmica quando o quadrado é apertado, e devolve quando a bazuca fica um tempo guardada
# Nomes medidos pelo Claude 2 (MGB #38): o "TIRO" é o coice (chave 0 = mira, 0 -> 4 = o tiro); o tronco tem a origem
# na cintura e vai em cima do especiais[0] da chave atual das pernas; especiais[2] do tronco é o eixo do cano.
BAZUCA = [('C3_BAZUCA_SACA', 'SACA', 0), ('C3_BAZUCA_TIRO', 'TIRO', 0),
          ('C3_BAZUCA_PERNAS_PARADO', 'PERNAS_PARADO', 1), ('C3_BAZUCA_PERNAS_ANDANDO', 'PERNAS_ANDANDO', 1),
          ('C3_BAZUCA_PERNAS_TIRO', 'PERNAS_TIRO', 0), ('C3_BAZUCA_PERNAS_SACA', 'PERNAS_SACA', 0)]
PONTO = {'Cgt0G': 2, 'Cgb0G': 0}   # por chave: no tronco, o eixo do cano; nas pernas, a cintura


def wumpa_quadros(c3):
    """A Wumpa do Warped (sprite de 14 quadros, 8 bits no disco), reduzida a 16 cores pelo Claude 2 com cada cor
    pesando igual; índice 0 transparente. Devolve ([quadro][y][x], 16 cores PS1)."""
    sp = [x for x in c3.m['sprites'] if x['nome'] == 'C3_WUMPA'][0]['reducao_4bits']
    d = open(os.path.join(OUT3, sp['arquivo']), 'rb').read()
    l, a, n = sp['l'], sp['a'], sp['quadros']
    q = []
    for k in range(n):
        base = k * a * (l // 2)
        q.append([[(d[base + y * (l // 2) + x // 2] >> (4 * (x & 1))) & 15 for x in range(l)] for y in range(a)])
    return q, [int(h, 16) for h in sp['cores_ps1']]


MARCAS = [('WOAH_B', 'WOAH!'), ('WOAH_Q', 'WOAH?')]
MARCA_L, MARCA_A = 64, 24
FONTE = r'C:\Windows\Fonts\impact.ttf'

# (entrega, som, nome curto): os três primeiros do Crash 1 (conferidos no teste 2), os do Aku Aku do Warped
SONS = [('c1', 'arg0A', 'WOAH'), ('c1', 'spn0A', 'GIRO'), ('c1', 'Ttb0A', 'BIPE'),
        ('c3', 'WD10A', 'AKU_PEGA'), ('c3', 'WD20A', 'AKU_PERDE'),
        ('c3', 'Cg10A', 'TIRO'), ('c3', 'frt0A', 'PLIM')]   # Cg10A: o tiro da bazuca (palpite medido do Claude 2)
SPU_ENDERECO = 0x50600   # buraco livre na SPU do Dock: 0x505F0..0x60FFF (medido pelo C1 original)
CLUT_COLUNAS = 2         # paletas em x = 896 e 912, y = 480..511 (até 64)

VRAM_TPAGE_X, VRAM_TPAGE_Y = 896, 256
VRAM_CLUT_X, VRAM_CLUT_Y = 896, 480
ATLAS_LARGURA = 256
LUZ = (0.35, 0.75, 0.55)


def ler_cru(caminho):
    d = open(caminho, 'rb').read()
    quadros, off = [], 0
    while off < len(d):
        ox, oy, oz, n = struct.unpack_from('<hhhH', d, off)
        off += 8
        v = d[off:off + n * 6]
        off += n * 6
        quadros.append(((ox, oy, oz), bytes(b for i in range(n) for b in v[i * 6:i * 6 + 3])))
    return quadros


def s8(v):
    v &= 255
    return v - 256 if v >= 128 else v


def bits_com_sinal(lo, hi):
    """Menor número de bits (com sinal) que guarda todos os valores de lo a hi; 0 se todos forem 0."""
    if lo == 0 and hi == 0:
        return 0
    for b in range(1, 9):
        if -(1 << (b - 1)) <= lo and hi <= (1 << (b - 1)) - 1:
            return b
    raise ValueError


def tabela_do_modelo(quadros, n):
    """Base e bits por vértice e eixo, a partir de todos os quadros do modelo."""
    base, nbits = [], []
    for i in range(n):
        for e in range(3):
            ds = []
            for (_, xyz) in quadros:
                ant = xyz[(i - 1) * 3 + e] if i else 0
                ds.append(s8(xyz[i * 3 + e] - ant))
            b0 = (min(ds) + max(ds)) // 2
            deltas = [s8(d - b0) for d in ds]
            base.append(b0 & 255)
            nbits.append(bits_com_sinal(min(deltas), max(deltas)))
    return base, nbits


def codificar(xyz, n, base, nbits, origem):
    acc_bits, nb = 0, 0
    palavras = []
    for i in range(n):
        for e in range(3):
            ant = xyz[(i - 1) * 3 + e] if i else 0
            b = nbits[i * 3 + e]
            if not b:
                continue
            d = s8(s8(xyz[i * 3 + e] - ant) - s8(base[i * 3 + e]))
            acc_bits = (acc_bits << b) | (d & ((1 << b) - 1))
            nb += b
            while nb >= 32:
                palavras.append((acc_bits >> (nb - 32)) & 0xFFFFFFFF)
                nb -= 32
                acc_bits &= (1 << nb) - 1
    if nb:
        palavras.append((acc_bits << (32 - nb)) & 0xFFFFFFFF)
    # o leitor pode olhar uma palavra adiante: as chaves vêm coladas (ele lê a origem da próxima, sem efeito) e quem
    # junta as chaves põe uma palavra 0 depois da última (FOLGA)
    return struct.pack('<hhhh', origem[0], origem[1], origem[2], 0) + struct.pack('<%dI' % len(palavras), *palavras)


FOLGA = bytes(4)


def meio_byte(nbits):
    """Os bits por vértice e eixo (0..8) em meio byte: dois por byte, o primeiro embaixo."""
    nb = list(nbits) + [0] * (len(nbits) & 1)
    return [nb[i] | (nb[i + 1] << 4) for i in range(0, len(nb), 2)]


def decodificar(rec, n, base, nbits):
    """O mesmo que o C faz (conferência)."""
    rec = rec + FOLGA
    pal = struct.unpack_from('<%dI' % ((len(rec) - 8) // 4), rec, 8)
    w, cur, resto = 0, pal[0], 32
    w = 1
    acc = [0, 0, 0]
    out = []
    for i in range(n):
        for e in range(3):
            b = nbits[i * 3 + e]
            val = 0
            if b:
                if b <= resto:
                    val = (cur >> (resto - b)) & ((1 << b) - 1)
                    resto -= b
                    if resto == 0:
                        cur, w, resto = pal[w], w + 1, 32
                else:
                    alto = cur & ((1 << resto) - 1)
                    falta = b - resto
                    cur, w = pal[w], w + 1
                    val = (alto << falta) | (cur >> (32 - falta))
                    resto = 32 - falta
                if val & (1 << (b - 1)):
                    val -= 1 << b
            acc[e] = (acc[e] + val + base[i * 3 + e]) & 255
            out.append(acc[e])
    return bytes(out)


def empacotar_regioes(regioes):
    pos, x, y, alt = {}, 0, 0, 0
    for r in sorted(regioes, key=lambda r: (-r['a'], -r['l'])):
        if x + r['l'] > ATLAS_LARGURA:
            x, y, alt = 0, y + alt, 0
        pos[r['chave']] = (x, y)
        x += r['l']
        alt = max(alt, r['a'])
    return pos, y + alt


def get_tpage(abr, x, y):
    return ((abr & 3) << 5) | ((y & 0x100) >> 4) | ((x & 0x3FF) >> 6) | ((y & 0x200) << 2)


def get_clut(x, y):
    return (y << 6) | ((x >> 4) & 0x3F)


def _cor15(r, g, b):
    return ((b >> 3) << 10) | ((g >> 3) << 5) | (r >> 3)


PALETA_MARCA = [0x0000, 0x0421] + [_cor15(255, int(90 + 165 * i / 13.0), int(20 * i / 13.0)) for i in range(14)]


def desenhar_marca(texto):
    from PIL import Image, ImageDraw, ImageFont
    esc = 4
    L, A = MARCA_L * esc, MARCA_A * esc
    d0 = ImageDraw.Draw(Image.new('L', (1, 1)))
    fonte = ImageFont.truetype(FONTE, int(A * 0.95))
    c = d0.textbbox((0, 0), texto, font=fonte)
    fonte = ImageFont.truetype(FONTE, int(A * 0.95 * min(1.0, (L * 0.92) / (c[2] - c[0]), (A * 0.86) / (c[3] - c[1]))))
    c = d0.textbbox((0, 0), texto, font=fonte)
    pos = ((L - (c[2] - c[0])) // 2 - c[0], (A - (c[3] - c[1])) // 2 - c[1])
    miolo, contorno = Image.new('L', (L, A), 0), Image.new('L', (L, A), 0)
    ImageDraw.Draw(miolo).text(pos, texto, font=fonte, fill=255)
    ImageDraw.Draw(contorno).text(pos, texto, font=fonte, fill=255, stroke_width=int(esc * 1.6), stroke_fill=255)
    m = miolo.resize((MARCA_L, MARCA_A), Image.LANCZOS).load()
    k = contorno.resize((MARCA_L, MARCA_A), Image.LANCZOS).load()
    return [[(2 + min(13, int(13 * (MARCA_A - 1 - y) / (MARCA_A - 1)))) if m[x, y] > 110 else (1 if k[x, y] > 90 else 0)
             for x in range(MARCA_L)] for y in range(MARCA_A)]


class Fonte:
    """Uma entrega do Claude 2 (out_c3 do Warped ou out do Crash 1): modelos, regiões, paletas e atlas."""

    def __init__(self, pasta, tag):
        self.pasta, self.tag = pasta, tag
        self.m = json.load(open(os.path.join(pasta, 'model.json'), encoding='utf-8'))
        self.anims = {x['nome']: x for x in self.m['animacoes']}
        self.regioes = {r['id']: r for r in self.m['texturas']['regioes']}
        self.cluts = {c['id']: c for c in self.m['texturas']['cluts']}
        self.atlas = open(os.path.join(pasta, 'tex', 'atlas_4bits.bin'), 'rb').read()
        self.larg = self.m['texturas']['atlas']['atlas_4bits']['largura_px']
        self._red = {}

    def px(self, x, y):
        b = self.atlas[y * (self.larg // 2) + x // 2]
        return (b >> 4) if x & 1 else (b & 15)

    def reduzida(self, rid):
        """Região de 8 bits reduzida a 16 cores (k-means com as cores DISTINTAS pesando igual, para não perder as cores
        de pouca área, como a pena azul do Aku Aku). Devolve (pixels [y][x] 0..15, 16 cores PS1)."""
        if rid in self._red:
            return self._red[rid]
        import numpy as np
        t = self.m['texturas']
        rg = self.regioes[rid]
        a8 = open(os.path.join(self.pasta, 'tex', 'atlas_8bits.bin'), 'rb').read()
        w8 = t['atlas']['atlas_8bits']['largura_px']
        pal = [int(h, 16) for h in self.cluts[rg['clut']]['cores_ps1']]
        rgb = np.array([[(v & 31) * 8, ((v >> 5) & 31) * 8, ((v >> 10) & 31) * 8] for v in pal], float)
        idx = np.array([[a8[(rg['y'] + y) * w8 + rg['x'] + x] for x in range(rg['l'])] for y in range(rg['a'])])
        px = rgb[idx].reshape(-1, 3)
        uniq = np.unique(px, axis=0)
        rng = np.random.default_rng(1)
        cent = [uniq[rng.integers(len(uniq))]]
        for _ in range(15):
            d = np.min(((uniq[:, None] - np.array(cent)[None]) ** 2).sum(-1), axis=1)
            cent.append(uniq[np.argmax(d)])
        cent = np.array(cent)
        for _ in range(20):
            lab = np.argmin(((px[:, None] - cent[None]) ** 2).sum(-1), axis=1)
            for k in range(16):
                if (lab == k).any():
                    cent[k] = px[lab == k].mean(0)
        lab = np.argmin(((px[:, None] - cent[None]) ** 2).sum(-1), axis=1)
        cores = []
        for r, g, b in cent:
            v = (int(b) >> 3 << 10) | (int(g) >> 3 << 5) | (int(r) >> 3)
            cores.append(v or 0x0421)                      # 0x0000 seria transparente
        pix = lab.reshape(rg['a'], rg['l']).tolist()
        self._red[rid] = (pix, cores)
        return self._red[rid]


def tabelas_do_modelo(fonte, mn, chaves, tex_do_material):
    """As tabelas de um modelo no formato do CRASH_MODEL: triângulos, material, bandeiras, textura, cores."""
    md = fonte.m['modelos'][mn]
    flags, mtex = [], []
    for mt in md['materiais']:
        f = (4 if mt['sem_descarte_de_costas'] else 0)
        t5 = [0, 0, 0, 0, 0]
        if mt['textura'] is not None:
            f |= 2
            if mt['modo_de_mistura'] in (0, 1, 2):
                f |= 8
            t5 = tex_do_material(fonte, mt)
        flags.append(f)
        mtex += t5
    base, nbits = tabela_do_modelo(chaves, md['vertices'])
    return dict(tris=[v for t in md['triangulos'] for v in t[:3]], tri_mat=[t[3] for t in md['triangulos']],
                flags=flags, mat_tex=mtex, cantos=[v for t in md['cores_dos_cantos'] for v in t],
                cores=[v for cc in md['cores'] for v in cc], base=base, bits=nbits)


def bloco_bazuca(c3, tex_do_material, fator):
    """O bloco da bazuca, lido do CD para a memória dinâmica. Formato (little-endian, alinhado a 4):
    'BAZ2', u16 nmodelos, u16 nanims, u32 ofs_anims, u32 ofs_key_ofs, u32 ofs_keys, u32 nchaves, u32 ofs_pontos;
    nmodelos x {u16 nverts, u16 ntris, s32 escala[3], u32 ofs[8]} = o CRASH_MODEL com deslocamentos no lugar dos
    ponteiros (o jogo soma o endereço do bloco); nanims x CRASH_ANIM (8 bytes); u32 key_ofs[]; as chaves;
    s16 pontos[nchaves][3] (no tronco o eixo do cano, nas pernas a cintura)."""
    mods, quadros = [], {}
    for nome, _, _ in BAZUCA:
        info = c3.anims[nome]
        if info['modelo'] not in mods:
            mods.append(info['modelo'])
        info['_q'] = ler_cru(os.path.join(OUT3, info['cru']['arquivo']))
        quadros.setdefault(info['modelo'], []).extend(info['_q'])
    cab = 28 + 48 * len(mods)
    corpo = bytearray()
    desc = []
    tabs = {}

    def poe(dados):
        corpo.extend(bytes((-(cab + len(corpo))) % 4))
        o = cab + len(corpo)
        corpo.extend(dados)
        return o

    for mn in mods:
        t = tabelas_do_modelo(c3, mn, quadros[mn], tex_do_material)
        tabs[mn] = t
        md = c3.m['modelos'][mn]
        k = [a for a in BAZUCA if c3.anims[a[0]]['modelo'] == mn][0]
        k = c3.anims[k[0]]['cru']['k']
        esc = [round(k[e] * fator * 4096) for e in range(3)]
        ofs = [poe(struct.pack('<%dH' % len(t['tris']), *t['tris'])), poe(bytes(t['tri_mat'])), poe(bytes(t['flags'])),
               poe(struct.pack('<%dH' % len(t['mat_tex']), *t['mat_tex'])), poe(bytes(t['cantos'])),
               poe(bytes(t['cores'])), poe(bytes(t['base'])), poe(bytes(meio_byte(t['bits'])))]
        desc.append(struct.pack('<HHiii8I', md['vertices'], len(md['triangulos']), esc[0], esc[1], esc[2], *ofs))
    chaves, anims = bytearray(), bytearray()
    key_ofs = []
    for nome, curto, laco in BAZUCA:
        info = c3.anims[nome]
        mn = info['modelo']
        n = c3.m['modelos'][mn]['vertices']
        primeiro = len(key_ofs)
        for (o, xyz) in info['_q']:
            rec = codificar(xyz, n, tabs[mn]['base'], tabs[mn]['bits'], o)
            assert decodificar(rec, n, tabs[mn]['base'], tabs[mn]['bits']) == xyz[:n * 3], nome
            key_ofs.append(len(chaves))
            chaves += rec
        anims += struct.pack('<BBBBBxH', mods.index(mn), len(info['_q']), info['toca'],
                             1 if info['interpola'] else 0, laco, primeiro)
    pontos = []
    for nome, _, _ in BAZUCA:
        info = c3.anims[nome]
        for q in info['por_quadro']:
            p = q['especiais'][PONTO[info['modelo']]]
            pontos += [round(p[0] * fator), round(p[1] * fator), round(p[2] * fator)]
    o_anims = poe(bytes(anims))
    o_pontos = poe(struct.pack('<%dh' % len(pontos), *pontos))
    o_kofs = poe(struct.pack('<%dI' % len(key_ofs), *key_ofs))
    o_keys = poe(bytes(chaves) + FOLGA)
    blob = b'BAZ2' + struct.pack('<HHIIIII', len(mods), len(BAZUCA), o_anims, o_kofs, o_keys, len(key_ofs), o_pontos)
    blob += b''.join(desc) + bytes(corpo)
    print('bazuca: %d modelos (%s), %d animações, %d chaves, %.1f KB no CD'
          % (len(mods), ', '.join(mods), len(BAZUCA), len(key_ofs), len(blob) / 1024))
    return blob


def bloco(valores, por_linha=16):
    return '\n'.join('    ' + ', '.join(str(v) for v in valores[i:i + por_linha]) + ','
                     for i in range(0, len(valores), por_linha))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--altura', type=float, default=1100.0, help='altura do Crash parado em unidades do MGS')
    a = ap.parse_args()
    fator = a.altura / 1000.0
    c3, c1 = Fonte(OUT3, 'c3'), Fonte(OUT1, 'c1')

    # modelos do Crash 3 na ordem em que aparecem
    modelos = []
    for nome, _, _, _ in ANIMS:
        if c3.anims[nome]['modelo'] not in modelos:
            modelos.append(c3.anims[nome]['modelo'])
    caixas_mod = [c3.anims[nome]['modelo'] for nome, _ in CAIXAS]
    baz_mod = []
    for nome, _, _ in BAZUCA:
        if c3.anims[nome]['modelo'] not in baz_mod:
            baz_mod.append(c3.anims[nome]['modelo'])

    # regiões e paletas (com o "dono" na chave, porque os ids se repetem entre as duas entregas). Região de 8 bits
    # vira ('c3r', id): reduzida a 16 cores, com paleta própria
    def chave_reg(fonte, rid):
        return ('c3r', rid) if fonte.regioes[rid]['bits'] == 8 else (fonte.tag, rid)

    def chave_clut(fonte, mt):
        return ('c3r', mt['textura']) if fonte.regioes[mt['textura']]['bits'] == 8 else (fonte.tag, mt['clut'])

    regs, cl = [], []
    for fonte, mods in ((c3, modelos + caixas_mod + baz_mod),):
        for mn in mods:
            for mt in fonte.m['modelos'][mn]['materiais']:
                if mt['textura'] is None:
                    continue
                kr, kc = chave_reg(fonte, mt['textura']), chave_clut(fonte, mt)
                if kr not in [x[0] for x in regs]:
                    regs.append((kr, fonte))
                if kc not in [x[0] for x in cl]:
                    cl.append((kc, fonte))
    lista_reg = []
    for (chave, fonte) in regs:
        rg = fonte.regioes[chave[1]]
        if rg['bits'] != 4 and chave[0] != 'c3r':
            raise SystemExit('região %s não é de 4 bits' % (chave,))
        lista_reg.append(dict(rg, chave=chave))
    wumpa_img, wumpa_cores = wumpa_quadros(c3)
    for k in range(len(wumpa_img)):
        lista_reg.append({'chave': ('wumpa', k), 'l': 32, 'a': 32})
    cl.append((('wumpa', 0), None))
    marcas_img = {}
    for mid, texto in MARCAS:
        marcas_img[mid] = desenhar_marca(texto)
        lista_reg.append({'chave': ('marca', mid), 'l': MARCA_L, 'a': MARCA_A})
    pos_reg, alt_atlas = empacotar_regioes(lista_reg)
    if VRAM_TPAGE_Y + alt_atlas > VRAM_CLUT_Y:
        raise SystemExit('atlas alto demais: %d' % alt_atlas)
    atlas = bytearray(ATLAS_LARGURA // 2 * alt_atlas)
    for r in lista_reg:
        nx, ny = pos_reg[r['chave']]
        for yy in range(r['a']):
            for xx in range(r['l']):
                if r['chave'][0] == 'marca':
                    p = marcas_img[r['chave'][1]][yy][xx]
                elif r['chave'][0] == 'wumpa':
                    p = wumpa_img[r['chave'][1]][yy][xx]
                elif r['chave'][0] == 'c3r':
                    p = c3.reduzida(r['chave'][1])[0][yy][xx]
                else:
                    fonte = c3 if r['chave'][0] == 'c3' else c1
                    p = fonte.px(r['x'] + xx, r['y'] + yy)
                i = (ny + yy) * (ATLAS_LARGURA // 2) + (nx + xx) // 2
                atlas[i] |= (p << 4) if (nx + xx) & 1 else p
    clut_linha = {chave: i for i, (chave, _) in enumerate(cl)}
    paletas = []
    for chave, fonte in cl:
        if chave[0] == 'c3r':
            paletas.append(c3.reduzida(chave[1])[1])
        elif chave[0] == 'wumpa':
            paletas.append(wumpa_cores)
        else:
            paletas.append([int(h, 16) for h in fonte.cluts[chave[1]]['cores_ps1']])
    clut_marca = len(cl)
    paletas.append(PALETA_MARCA)
    if len(paletas) > 32 * CLUT_COLUNAS:
        raise SystemExit('paletas demais: %d' % len(paletas))
    # bloco de 16 * CLUT_COLUNAS x 32 palavras na VRAM (x = 896, y = 480): a paleta i fica na coluna i // 32, linha i % 32
    clut_dados = [0] * (16 * CLUT_COLUNAS * 32)
    for i, p in enumerate(paletas):
        for j in range(16):
            clut_dados[(i % 32) * 16 * CLUT_COLUNAS + (i // 32) * 16 + j] = p[j]

    def clut_xy(i):
        return VRAM_CLUT_X + 16 * (i // 32), VRAM_CLUT_Y + i % 32

    def tex_do_material(fonte, mt):
        abr = mt['modo_de_mistura'] if mt['modo_de_mistura'] in (0, 1, 2) else 0
        bx, by = pos_reg[chave_reg(fonte, mt['textura'])]
        return [get_tpage(abr, VRAM_TPAGE_X, VRAM_TPAGE_Y), get_clut(*clut_xy(clut_linha[chave_clut(fonte, mt)]))] + \
               [((bx + u) & 255) | (((by + v) & 255) << 8) for (u, v) in mt['uv']]

    c = ['/* GERADO por motor/empacotar_crash3.py: Crash do Crash Bandicoot 3 (SCES-01420) e caixas/sons do Crash 1',
         '   (SCUS-94900), extraidos pelo Claude 2; formatos do c1/c2 (wurlyfox) e CrashEdit. Nao distribuir. */',
         '#include "crash_data.h"', '']

    # ---- modelos do Crash 3 e quadros-chave ----
    # variantes: a mesma malha com outra tabela de bits (GRUPO_DE_BITS); cada uma vira um CRASH_MODEL
    variantes, chaves_por_var = [], {}
    for nome, curto, laco, levantar in ANIMS:
        info = c3.anims[nome]
        q = ler_cru(os.path.join(OUT3, info['cru']['arquivo']))
        if levantar:
            ky = info['cru']['k'][1]
            for i, (o, xyz) in enumerate(q):
                miny = min((o[1] + xyz[3 * j + 1]) * ky for j in range(len(xyz) // 3))
                if miny < 0:
                    o = (o[0], o[1] + int(math.ceil(-miny / ky)), o[2])
                q[i] = (o, xyz)
        info['_q'] = q
        var = (info['modelo'], GRUPO_DE_BITS.get(nome, ''))
        if var not in variantes:
            variantes.append(var)
            chaves_por_var[var] = []
        chaves_por_var[var] += q

    tabela_mod, malha = {}, {}
    nv_max = nt_max = 0
    for mi, mn in enumerate(modelos):
        md = c3.m['modelos'][mn]
        n = md['vertices']
        k = None
        for nome, _, _, _ in ANIMS:
            if c3.anims[nome]['modelo'] == mn:
                k = c3.anims[nome]['cru']['k']
                break
        malha[mn] = (mi, [round(k[e] * fator * 4096) for e in range(3)])
        tris, mats = md['triangulos'], md['materiais']
        nv_max, nt_max = max(nv_max, n), max(nt_max, len(tris))
        flags, mtex = [], []
        for mt in mats:
            f = (4 if mt['sem_descarte_de_costas'] else 0)
            t5 = [0, 0, 0, 0, 0]
            if mt['textura'] is not None:
                f |= 2
                if mt['modo_de_mistura'] in (0, 1, 2):
                    f |= 8
                t5 = tex_do_material(c3, mt)
            flags.append(f)
            mtex += t5
        cores = md['cores']
        cantos = [v for t in md['cores_dos_cantos'] for v in t]
        c.append('static const unsigned short m%d_tris[] = {\n%s\n};' % (mi, bloco([v for t in tris for v in t[:3]])))
        c.append('static const unsigned char m%d_tri_mat[] = {\n%s\n};' % (mi, bloco([t[3] for t in tris])))
        c.append('static const unsigned char m%d_flags[] = {\n%s\n};' % (mi, bloco(flags)))
        c.append('static const unsigned short m%d_mat_tex[] = {\n%s\n};' % (mi, bloco(mtex, 15)))
        c.append('static const unsigned char m%d_cantos[] = {\n%s\n};' % (mi, bloco(cantos, 18)))
        c.append('static const unsigned char m%d_cores[] = {\n%s\n};' % (mi, bloco([v for cc in cores for v in cc], 18)))
    for vi, var in enumerate(variantes):
        base, nbits = tabela_do_modelo(chaves_por_var[var], c3.m['modelos'][var[0]]['vertices'])
        c.append('static const unsigned char v%d_base[] = {\n%s\n};' % (vi, bloco(base, 18)))
        c.append('static const unsigned char v%d_bits[] = {\n%s\n};' % (vi, bloco(meio_byte(nbits), 18)))
        tabela_mod[var] = (base, nbits, vi)
    c.append('const CRASH_MODEL crash_models[CRASH_NMODELS] = {')
    for vi, (mn, grupo) in enumerate(variantes):
        md = c3.m['modelos'][mn]
        mi, esc = malha[mn]
        c.append('    { %d, %d, { %d, %d, %d }, m%d_tris, m%d_tri_mat, m%d_flags, m%d_mat_tex, m%d_cantos, m%d_cores, '
                 'v%d_base, v%d_bits }, /* %s%s */' % (md['vertices'], len(md['triangulos']), esc[0], esc[1], esc[2],
                                                      mi, mi, mi, mi, mi, mi, vi, vi, mn, ' ' + grupo if grupo else ''))
    c.append('};')

    blob, ofs, tabela = bytearray(), [], []
    for nome, curto, laco, levantar in ANIMS:
        info = c3.anims[nome]
        mn = info['modelo']
        base, nbits, vi = tabela_mod[(mn, GRUPO_DE_BITS.get(nome, ''))]
        n = c3.m['modelos'][mn]['vertices']
        primeiro = len(ofs)
        for (o, xyz) in info['_q']:
            rec = codificar(xyz, n, base, nbits, o)
            assert decodificar(rec, n, base, nbits) == xyz[:n * 3], nome
            ofs.append(len(blob))
            blob += rec
        tabela.append((curto, vi, len(info['_q']), info['toca'], 1 if info['interpola'] else 0, laco, primeiro, nome))
    blob += FOLGA
    # o ponto do rosto por chave (unidades do MGS, no espaço do modelo, como os vértices)
    rosto = []
    for nome, curto, laco, levantar in ANIMS:
        info = c3.anims[nome]
        esp = ROSTO.get(info['modelo'])
        ky = info['cru']['k'][1]
        q0 = ler_cru(os.path.join(OUT3, info['cru']['arquivo']))
        for i, (o, xyz) in enumerate(info['_q']):
            if esp is None or 'por_quadro' not in info:
                rosto += [0, 0, 0]
                continue
            p = info['por_quadro'][i]['especiais'][esp]
            sobe = (o[1] - q0[i][0][1]) * ky             # o que o "levantar até o chão" subiu esta chave
            rosto += [round(p[0] * fator), round((p[1] + sobe) * fator), round(p[2] * fator)]
    c.append('const short crash_rosto[CRASH_NKEYS * 3] = {\n%s\n};' % bloco(rosto, 12))
    c.append('const unsigned long crash_key_ofs[CRASH_NKEYS] = {\n%s\n};' % bloco(ofs, 12))
    palavras = struct.unpack('<%dI' % (len(blob) // 4), bytes(blob))
    c.append('const unsigned long crash_keys[%d] = {\n%s\n};' % (len(palavras), bloco(['0x%08X' % v for v in palavras], 8)))
    c.append('const CRASH_ANIM crash_anims[CRASH_NANIMS] = {')
    for curto, mi, nk, toca, interp, laco, primeiro, nome in tabela:
        c.append('    { %d, %d, %d, %d, %d, %d }, /* %s (%s) */' % (mi, nk, toca, interp, laco, primeiro, curto, nome))
    c.append('};')

    # ---- caixas do Warped (estáticas) ----
    cx_verts, cx_tris, cx_tex, cx_luz = [], [], [], []
    L = [v / math.sqrt(sum(x * x for x in LUZ)) for v in LUZ]
    for nome, curto in CAIXAS:
        info = c3.anims[nome]
        md = c3.m['modelos'][info['modelo']]
        (o, xyz) = ler_cru(os.path.join(OUT3, info['cru']['arquivo']))[0]
        kc, chao_c = info['cru']['k'], info['cru']['chao']
        brutos = [[(o[e] + xyz[3 * i + e]) * kc[e] for e in range(3)] for i in range(md['vertices'])]
        lado = max(v[0] for v in brutos) - min(v[0] for v in brutos)
        f = CAIXA_LADO / lado
        vs = [(round(x * f), round((y - chao_c) * f), round(z * f), 0) for x, y, z in brutos]
        cx_verts += [v for vv in vs for v in vv]
        tris_cx = md['triangulos']
        assert len(tris_cx) == CAIXA_NT and len(vs) == 8, nome
        for (ta, tb, tc, mt_i) in tris_cx:
            cx_tris += [ta, tb, tc]
            cx_tex += tex_do_material(c3, md['materiais'][mt_i])
            p0, p1, p2 = vs[ta], vs[tb], vs[tc]
            ux, uy, uz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
            wx, wy, wz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
            nx, ny, nz = uy * wz - uz * wy, uz * wx - ux * wz, ux * wy - uy * wx
            nn = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            cx_luz.append(min(255, round(255 * (0.55 + 0.45 * abs(nx * L[0] + ny * L[1] + nz * L[2]) / nn))))
    c.append('const short crash_caixa_verts[CRASH_NCAIXAS * 8 * 4] = {\n%s\n};' % bloco(cx_verts))
    c.append('const unsigned char crash_caixa_tris[CRASH_NCAIXAS * CRASH_CAIXA_NT * 3] = {\n%s\n};' % bloco(cx_tris, 15))
    c.append('const unsigned short crash_caixa_tex[CRASH_NCAIXAS * CRASH_CAIXA_NT * 5] = {\n%s\n};' % bloco(cx_tex, 15))
    c.append('const unsigned short crash_wumpa_uv[CRASH_WUMPA_QUADROS] = {\n%s\n};' % bloco(
        [pos_reg[('wumpa', k)][0] | (pos_reg[('wumpa', k)][1] << 8) for k in range(len(wumpa_img))], 14))
    c.append('const unsigned char crash_caixa_luz[CRASH_NCAIXAS * CRASH_CAIXA_NT] = {\n%s\n};' % bloco(cx_luz, 10))

    # ---- o que vai para o CD: textura, paletas, sons ----
    sons_bytes, sons_tab = bytearray(), []
    for tag, nome, curto in SONS:
        corpo = open(os.path.join(OUT1 if tag == 'c1' else OUT3, 'snd', nome + '.vag'), 'rb').read()[64:]
        corpo += bytes((-len(corpo)) % 64)
        sons_tab.append((curto, len(sons_bytes), len(corpo), nome))
        sons_bytes += corpo
    # dois pedaços lidos em separado (o buffer de leitura vem do GV_Malloc, cujo maior bloco livre é ~50 KB):
    # 1) textura + paletas, 2) sons, cada um começando num setor
    baz = bloco_bazuca(c3, tex_do_material, fator)
    cd, cd_ofs = bytearray(), {}
    for nome_cd, dados_cd in (('ATLAS', bytes(atlas)), ('CLUTS', struct.pack('<%dH' % len(clut_dados), *clut_dados)),
                              ('SONS', bytes(sons_bytes)), ('BAZUCA', baz)):
        cd += bytes((-len(cd)) % (2048 if nome_cd in ('SONS', 'BAZUCA') else 64))
        cd_ofs[nome_cd] = len(cd)
        cd += dados_cd
    os.makedirs(os.path.dirname(CD_SAIDA), exist_ok=True)
    open(CD_SAIDA, 'wb').write(bytes(cd))
    brf_setor = (os.path.getsize(BRF_ORIGINAL) + 2047) // 2048

    h = ['/* GERADO por motor/empacotar_crash3.py. Nao editar a mao. */', '#ifndef CRASH_DATA_H', '#define CRASH_DATA_H', '',
         '#define CRASH_NMODELS %d' % len(variantes), '#define CRASH_NANIMS %d' % len(tabela), '#define CRASH_NKEYS %d' % len(ofs),
         '#define CRASH_NV_MAX %d' % nv_max, '#define CRASH_NT_MAX %d' % nt_max, '#define CRASH_CULL (1)', '',
         '#define CRASH_ATLAS_X %d' % VRAM_TPAGE_X, '#define CRASH_ATLAS_Y %d' % VRAM_TPAGE_Y,
         '#define CRASH_ATLAS_W %d' % (ATLAS_LARGURA // 4), '#define CRASH_ATLAS_H %d' % alt_atlas,
         '#define CRASH_CLUT_X %d' % VRAM_CLUT_X, '#define CRASH_CLUT_Y %d' % VRAM_CLUT_Y,
         '#define CRASH_CLUT_W %d   /* bloco de paletas: %d colunas de 16 x 32 linhas */' % (16 * CLUT_COLUNAS, CLUT_COLUNAS),
         '#define CRASH_NCLUTS %d   /* + 1: a das marcas */' % clut_marca,
         '#define CRASH_NCAIXAS %d   /* %s */' % (len(CAIXAS), ', '.join(cu for _, cu in CAIXAS)),
         '#define CRASH_CAIXA_NT %d   /* triangulos por caixa: as 6 faces */' % CAIXA_NT, '']
    for i, (_, curto) in enumerate(CAIXAS):
        h.append('#define CRASH_CX_%s %d' % (curto, i))
    for mid, _ in MARCAS:
        mx, my = pos_reg[('marca', mid)]
        h += ['#define CRASH_%s_X %d' % (mid, VRAM_TPAGE_X + mx // 4), '#define CRASH_%s_Y %d' % (mid, VRAM_TPAGE_Y + my),
              '#define CRASH_%s_W %d' % (mid, MARCA_L // 4), '#define CRASH_%s_H %d' % (mid, MARCA_A)]
    h += ['#define CRASH_MARCA_CLUT_X %d' % clut_xy(clut_marca)[0], '#define CRASH_MARCA_CLUT_Y %d' % clut_xy(clut_marca)[1], '',
          '#define CRASH_SPU_ADDR 0x%X' % SPU_ENDERECO, '#define CRASH_SONS_BYTES %d' % len(sons_bytes)]
    for curto, ofs_s, tam_s, nome in sons_tab:
        h += ['#define CRASH_SOM_%s_OFS %d   /* %s */' % (curto, ofs_s, nome), '#define CRASH_SOM_%s_TAM %d' % (curto, tam_s)]
    h += ['', '/* no CD: fim do BRF.DAT, em dois pedacos (textura + paletas; sons) */',
          '#define CRASH_CD_SETOR %d' % brf_setor, '#define CRASH_CD_BYTES %d   /* textura + paletas */' % cd_ofs['SONS'],
          '#define CRASH_CD_ATLAS %d' % cd_ofs['ATLAS'], '#define CRASH_CD_CLUTS %d' % cd_ofs['CLUTS'],
          '#define CRASH_CD_SETOR_SONS %d' % (brf_setor + cd_ofs['SONS'] // 2048),
          '#define CRASH_CD_BYTES_SONS %d' % len(sons_bytes),
          '#define CRASH_CD_SETOR_BAZUCA %d' % (brf_setor + cd_ofs['BAZUCA'] // 2048),
          '#define CRASH_CD_BYTES_BAZUCA %d   /* lido para a memoria dinamica quando o quadrado e apertado */' % len(baz), '']
    for i, (_, curto, _) in enumerate(BAZUCA):
        h.append('#define CRASH_BZ_%s %d' % (curto, i))
    h += ['#define CRASH_WUMPA_TPAGE %d' % get_tpage(0, VRAM_TPAGE_X, VRAM_TPAGE_Y),
          '#define CRASH_WUMPA_CLUT %d' % get_clut(*clut_xy(clut_linha[('wumpa', 0)])),
          '#define CRASH_WUMPA_QUADROS %d   /* a Wumpa girando: uv de cada quadro em crash_wumpa_uv */' % len(wumpa_img), '',
          '/* material: 2 = textura, 4 = sem descarte de costas, 8 = semitransparente */',
          'typedef struct {', '    unsigned short        nverts, ntris;',
          '    long                  escala[3];  /* (origem + byte) * escala >> 12 */',
          '    const unsigned short *tris;', '    const unsigned char  *tri_mat;', '    const unsigned char  *flags;',
          '    const unsigned short *mat_tex;    /* tpage, clut, uv0, uv1, uv2 */',
          '    const unsigned char  *cantos;     /* 3 indices de cor por triangulo */',
          '    const unsigned char  *cores;      /* r, g, b (a luz ja vem pintada) */',
          '    const unsigned char  *base;       /* por vertice e eixo: soma fixa */',
          '    const unsigned char  *bits;       /* por vertice e eixo: bits da diferenca (com sinal), meio byte cada */',
          '} CRASH_MODEL;', '',
          'typedef struct {', '    unsigned char  model, nkeys, toca, interp, loop;', '    unsigned short first;', '} CRASH_ANIM;', '']
    for i, t in enumerate(tabela):
        h.append('#define CRASH_A_%s %d' % (t[0], i))
    h += ['', 'extern const CRASH_MODEL    crash_models[CRASH_NMODELS];', 'extern const CRASH_ANIM     crash_anims[CRASH_NANIMS];',
          'extern const unsigned long  crash_key_ofs[CRASH_NKEYS];', 'extern const unsigned long  crash_keys[];',
          'extern const short          crash_rosto[];         /* por chave: o ponto do rosto (x, y, z) */',
          'extern const unsigned short crash_wumpa_uv[];      /* u | v << 8 de cada quadro da Wumpa */',
          'extern const short          crash_caixa_verts[];', 'extern const unsigned char  crash_caixa_tris[];',
          'extern const unsigned short crash_caixa_tex[];', 'extern const unsigned char  crash_caixa_luz[];', '', '#endif', '']

    open(os.path.join(DEST, 'crash_data.h'), 'w', encoding='ascii', newline='\n').write('\n'.join(h))
    open(os.path.join(DEST, 'crash_data.c'), 'w', encoding='ascii', newline='\n').write('\n'.join(c) + '\n')
    tam_mod = 0
    for mn in modelos:
        md = c3.m['modelos'][mn]
        tam_mod += len(md['triangulos']) * 10 + len(md['materiais']) * 11 + len(md['cores']) * 3 + md['vertices'] * 6
    print('%d animações, %d chaves: %.1f KB de quadros (sem perda) + %.1f KB de modelos; CD %.1f KB (atlas %dx%d, %d paletas)'
          % (len(tabela), len(ofs), len(blob) / 1024, tam_mod / 1024, len(cd) / 1024, ATLAS_LARGURA, alt_atlas, clut_marca + 1))
    for (mn, grupo), (_, nbits, _) in tabela_mod.items():
        print('  %s%s: %.1f bits por vértice' % (mn, ' ' + grupo if grupo else '', sum(nbits) / (len(nbits) / 3)))


if __name__ == '__main__':
    main()
