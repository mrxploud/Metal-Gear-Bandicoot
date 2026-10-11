"""Empacotador do Crash para o MGS: lê a entrega do Claude 2 (crash_assets/out, contrato v1.1) e gera o C que
entra no executável (repos/mgs_reversing/source/crash/crash_data.c e .h).

    python -I motor/empacotar_crash.py            (usa a lista ANIMS abaixo)

Formato gerado (pensado para caber na RAM do PS1):
- modelos: triângulos (3 índices u16 + material u8); materiais r, g, b, flags; textura por material
  (tpage, clut, 3 uv); luz por vértice (0..255) calculada pelas normais do 1º quadro do modelo;
- quadros: origem s16 x3 + 3 bytes por vértice, só os quadros que o script do Crash usa (sem interpolar);
- texturas: só as regiões que os modelos usam, reempacotadas num atlas de 4 bits que vai para a VRAM livre
  (página em x=896, y=256) + as paletas (uma por linha em x=896, y=496...).
No jogo: vértice = sinal * (((origem + byte) * escala) >> 12), e y ganha yofs.
"""
import argparse
import json
import math
import os
import struct

FUSAO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRF_ORIGINAL = os.path.join(FUSAO, 'motor', 'disco_mgs', 'MGSI_D1', 'MGS', 'BRF.DAT')
CD_SAIDA = os.path.join(FUSAO, 'motor', 'out', 'crash_cd.bin')
OUT = os.path.join(FUSAO, 'crash_assets', 'out')
DEST = os.path.join(FUSAO, 'repos', 'mgs_reversing', 'source', 'crash')

# nome no disco -> (nome curto, quadros usados, laço?). Quadros escolhidos pelo script do Crash (WillC.gooc),
# conforme o estudo do Claude 2 (crash_assets/ESTUDO_COMPRESSAO.md): sem interpolação, só os quadros que o jogo usa.
ANIMS = [
    ('WILLY_STANCE1', 'PARADO', [11, 12], 0),        # 11 = descanso, 12 = piscar
    ('WILLY_WALK', 'CORRER', list(range(10)), 1),    # meio passo: o jogo toca normal e depois espelhado em X
    ('WILLY_DUCK', 'AGACHAR', list(range(9)), 0),    # 0..7 descendo, 8 = abaixado
    ('WILLY_FLAT', 'ACHATAR', list(range(5)), 0),    # 0..3 caindo, 4 = achatado
    ('WILLY_BLOW', 'GIRO', list(range(8)), 1),       # o giro (modelo WiBlG)
    ('WILLY_SPIN_END', 'FIM_GIRO', list(range(6)), 0),
    ('WILLY_KILLED_1', 'MORRER', list(range(6)), 0),
]

# caixas do Crash no lugar das caixas de papelão do Snake: caixa A, B e C do MGS (modelo estático, 1 quadro)
CAIXAS = [
    ('BOX_NORMAL', 'MADEIRA'),
    ('BOX_PICKUP', 'PERGUNTA'),
    ('BOX_TNT', 'TNT'),
    ('BOX_TNT1', 'TNT_3'),                 # a contagem da TNT chutada: 3, 2, 1 (só muda a textura da face)
    ('BOX_TNT2', 'TNT_2'),
    ('BOX_TNT3', 'TNT_1'),
]
CAIXA_LADO = 700                           # lado da caixa no MGS (no Crash 1 ela tem 524 com o Crash = 1000)

# o "!" e o "?" dos guardas viram "WOAH!" e "WOAH?" (ideia de um comentário do post, completada pelo ZXE102R)
MARCAS = [('WOAH_B', 'WOAH!'), ('WOAH_Q', 'WOAH?')]
MARCA_L, MARCA_A = 64, 24                  # px de 4 bits
FONTE = r'C:\Windows\Fonts\impact.ttf'

# sons do Crash que vão para a SPU (memória de som): só os essenciais, porque também ocupam a RAM do executável
SONS = [('arg0A', 'WOAH'), ('spn0A', 'GIRO'), ('Ttb0A', 'BIPE')]
SPU_ENDERECO = 0x5E000                     # buraco livre na área de ondas do MGS (medido no Dock: 0x505F0..0x60FFF)

VRAM_TPAGE_X, VRAM_TPAGE_Y = 896, 256     # página de textura de 4 bits (64 palavras = 256 px de largura)
VRAM_CLUT_X, VRAM_CLUT_Y = 896, 480        # paletas: uma por linha (até 32)
ATLAS_LARGURA = 256                        # px de 4 bits

LUZ = (0.35, 0.75, 0.55)
AMBIENTE, DIFUSA = 0.45, 0.55


def ler_cru(caminho):
    d = open(caminho, 'rb').read()
    quadros, off = [], 0
    while off < len(d):
        ox, oy, oz, n = struct.unpack_from('<hhhH', d, off)
        off += 8
        v = d[off:off + n * 6]
        off += n * 6
        xyz = bytes(b for i in range(n) for b in v[i * 6:i * 6 + 3])
        nrm = [struct.unpack_from('<bbb', v, i * 6 + 3) for i in range(n)]
        quadros.append(((ox, oy, oz), xyz, nrm))
    return quadros


def luz_por_vertice(normais):
    L = [c / math.sqrt(sum(x * x for x in LUZ)) for c in LUZ]
    r = []
    for (nx, ny, nz) in normais:
        n = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        d = max(0.0, (nx * L[0] + ny * L[1] + nz * L[2]) / n)
        r.append(min(255, round(255 * (AMBIENTE + DIFUSA * d))))
    return r


def empacotar_regioes(regioes):
    """Prateleiras simples num atlas de ATLAS_LARGURA px: devolve {id: (x, y)} e a altura usada."""
    pos, x, y, alt = {}, 0, 0, 0
    for r in sorted(regioes, key=lambda r: (-r['a'], -r['l'])):
        if x + r['l'] > ATLAS_LARGURA:
            x, y, alt = 0, y + alt, 0
        pos[r['id']] = (x, y)
        x += r['l']
        alt = max(alt, r['a'])
    return pos, y + alt


# paleta das marcas: 0 transparente, 1 contorno escuro, 2..15 do laranja do Crash ao amarelo
PALETA_MARCA = [0x0000, 0x0421] + [0] * 14   # sem o bit 15: opacas mesmo num desenho semitransparente


def _cor15(r, g, b):
    return ((b >> 3) << 10) | ((g >> 3) << 5) | (r >> 3)


for _i in range(14):
    _t = _i / 13.0
    PALETA_MARCA[2 + _i] = _cor15(255, int(90 + 165 * _t), int(20 * _t))


def desenhar_marca(texto):
    """'WOAH!' em Impact, laranja para amarelo (de baixo para cima), contorno escuro: matriz de índices 4 bits."""
    from PIL import Image, ImageDraw, ImageFont
    esc = 4
    L, A = MARCA_L * esc, MARCA_A * esc
    fonte = ImageFont.truetype(FONTE, int(A * 0.95))
    caixa = ImageDraw.Draw(Image.new('L', (1, 1))).textbbox((0, 0), texto, font=fonte)
    tw, th = caixa[2] - caixa[0], caixa[3] - caixa[1]
    fonte = ImageFont.truetype(FONTE, int(A * 0.95 * min(1.0, (L * 0.92) / tw, (A * 0.86) / th)))
    caixa = ImageDraw.Draw(Image.new('L', (1, 1))).textbbox((0, 0), texto, font=fonte)
    tw, th = caixa[2] - caixa[0], caixa[3] - caixa[1]
    pos = ((L - tw) // 2 - caixa[0], (A - th) // 2 - caixa[1])
    miolo = Image.new('L', (L, A), 0)
    ImageDraw.Draw(miolo).text(pos, texto, font=fonte, fill=255)
    contorno = Image.new('L', (L, A), 0)
    ImageDraw.Draw(contorno).text(pos, texto, font=fonte, fill=255, stroke_width=int(esc * 1.6), stroke_fill=255)
    miolo = miolo.resize((MARCA_L, MARCA_A), Image.LANCZOS)
    contorno = contorno.resize((MARCA_L, MARCA_A), Image.LANCZOS)
    m, c = miolo.load(), contorno.load()
    r = []
    for y in range(MARCA_A):
        linha = []
        for x in range(MARCA_L):
            if m[x, y] > 110:
                linha.append(2 + min(13, int(13 * (MARCA_A - 1 - y) / (MARCA_A - 1))))
            elif c[x, y] > 90:
                linha.append(1)
            else:
                linha.append(0)
        r.append(linha)
    return r


def get_tpage(abr, x, y):           # getTPage(tp=0 (4 bits), abr, x, y) da libgpu
    return ((0 & 3) << 7) | ((abr & 3) << 5) | ((y & 0x100) >> 4) | ((x & 0x3FF) >> 6) | ((y & 0x200) << 2)


def get_clut(x, y):
    return (y << 6) | ((x >> 4) & 0x3F)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--altura', type=float, default=1100.0, help='altura do Crash parado em unidades do MGS')
    a = ap.parse_args()

    m = json.load(open(os.path.join(OUT, 'model.json'), encoding='utf-8'))
    anims = {x['nome']: x for x in m['animacoes']}
    regioes = {r['id']: r for r in m['texturas']['regioes']}
    cluts = {c['id']: c for c in m['texturas']['cluts']}
    atlas_cru = open(os.path.join(OUT, 'tex', 'atlas_4bits.bin'), 'rb').read()
    larg_atlas_cru = m['texturas']['atlas']['atlas_4bits']['largura_px']

    # modelos usados, na ordem em que aparecem
    modelos = []
    for nome, _, _, _ in ANIMS:
        if anims[nome]['modelo'] not in modelos:
            modelos.append(anims[nome]['modelo'])

    modelos_caixa = [anims[nome]['modelo'] for nome, _ in CAIXAS]

    # regiões de textura e paletas usadas pelos modelos
    reg_usadas, clut_usadas = [], []
    for mn in modelos + modelos_caixa:
        t = m['modelos'][mn]['texturas_do_modelo']
        reg_usadas += [r for r in t['regioes'] if r not in reg_usadas]
        clut_usadas += [c for c in t['cluts'] if c not in clut_usadas]
    if len(clut_usadas) > 32:
        raise SystemExit('paletas demais: %d' % len(clut_usadas))
    marcas_img = {}
    for i, (mid, texto) in enumerate(MARCAS):
        marcas_img[mid] = desenhar_marca(texto)
        regioes[mid] = {'id': mid, 'bits': 4, 'l': MARCA_L, 'a': MARCA_A, 'x': 0, 'y': 0, 'clut': 'marca'}
        reg_usadas.append(mid)
    pos_reg, alt_atlas = empacotar_regioes([regioes[r] for r in reg_usadas])
    for r in reg_usadas:
        if isinstance(r, str):
            continue
        if regioes[r]['bits'] != 4:
            raise SystemExit('região %d não é de 4 bits' % r)

    # atlas novo (4 bits: 2 px por byte, o da esquerda no nibble baixo)
    atlas = bytearray(ATLAS_LARGURA // 2 * alt_atlas)

    def px_cru(x, y):
        b = atlas_cru[y * (larg_atlas_cru // 2) + x // 2]
        return (b >> 4) if x & 1 else (b & 15)

    for r in reg_usadas:
        rg, (nx, ny) = regioes[r], pos_reg[r]
        for yy in range(rg['a']):
            for xx in range(rg['l']):
                p = marcas_img[r][yy][xx] if isinstance(r, str) else px_cru(rg['x'] + xx, rg['y'] + yy)
                i = (ny + yy) * (ATLAS_LARGURA // 2) + (nx + xx) // 2
                atlas[i] |= (p << 4) if (nx + xx) & 1 else p
    clut_linha = {c: i for i, c in enumerate(clut_usadas)}
    clut_dados = []
    for c in clut_usadas:
        clut_dados += [int(h, 16) for h in cluts[c]['cores_ps1']]
    clut_marca = len(clut_usadas)               # a paleta das marcas vem depois das do Crash
    clut_dados += PALETA_MARCA

    # quadros-chave
    k = chao = None
    keys, tabela = [], []
    for nome, curto, sel, laco in ANIMS:
        info = anims[nome]
        q = ler_cru(os.path.join(OUT, info['cru']['arquivo']))
        if k is None:
            k, chao = info['cru']['k'][0], info['cru']['chao']
        elif abs(info['cru']['k'][0] - k) > 1e-6:
            raise SystemExit('%s tem outra escala (%s)' % (nome, info['cru']['k']))
        tabela.append((curto, modelos.index(info['modelo']), len(keys), len(sel), 1, laco, len(q), nome))
        keys += [(modelos.index(info['modelo']), q[i]) for i in sel]

    fator = a.altura / 1000.0
    escala = round(k * fator * 4096)
    yofs = round(-chao * fator)

    # luz por modelo: normais do 1º quadro do modelo
    luz = {}
    for mi, (o, xyz, nrm) in keys:
        if mi not in luz:
            luz[mi] = luz_por_vertice(nrm)

    def bloco(valores, por_linha=16, ind='    '):
        return '\n'.join(ind + ', '.join(str(v) for v in valores[i:i + por_linha]) + ','
                         for i in range(0, len(valores), por_linha))

    c = ['/* GERADO por motor/empacotar_crash.py. Dados do Crash Bandicoot (SCUS-94900) extraidos pelo Claude 2;',
         '   formatos do c1 (wurlyfox). Nao distribuir. */', '#include "crash_data.h"', '']
    nv_max = nt_max = 0
    for mi, mn in enumerate(modelos):
        md = m['modelos'][mn]
        tris, mats = md['triangulos'], md['materiais']
        nv_max, nt_max = max(nv_max, md['vertices']), max(nt_max, len(tris))
        mat_rgbf, mat_tex = [], []
        for mt in mats:
            f = (1 if mt['liso'] else 0) | (4 if mt['sem_descarte_de_costas'] else 0)
            tp = cl = 0
            uvs = [0, 0, 0]
            if mt['textura'] is not None:
                f |= 2
                abr = mt['modo_de_mistura'] if mt['modo_de_mistura'] in (0, 1, 2) else 0
                if mt['modo_de_mistura'] in (0, 1, 2):
                    f |= 8
                tp = get_tpage(abr, VRAM_TPAGE_X, VRAM_TPAGE_Y)
                cl = get_clut(VRAM_CLUT_X, VRAM_CLUT_Y + clut_linha[mt['clut']])
                bx, by = pos_reg[mt['textura']]
                uvs = [((bx + u) & 255) | (((by + v) & 255) << 8) for (u, v) in mt['uv']]
            mat_rgbf += [mt['rgb'][0], mt['rgb'][1], mt['rgb'][2], f]
            mat_tex += [tp, cl] + uvs
        c.append('static const unsigned short m%d_tris[] = {\n%s\n};' % (mi, bloco([v for t in tris for v in t[:3]])))
        c.append('static const unsigned char m%d_tri_mat[] = {\n%s\n};' % (mi, bloco([t[3] for t in tris])))
        c.append('static const unsigned char m%d_mats[] = {\n%s\n};' % (mi, bloco(mat_rgbf)))
        c.append('static const unsigned short m%d_mat_tex[] = {\n%s\n};' % (mi, bloco(mat_tex, 15)))
        c.append('static const unsigned char m%d_light[] = {\n%s\n};' % (mi, bloco(luz[mi])))
    # caixas: vértices finais em unidades do MGS (base no chão, centro em x/z), textura e brilho por triângulo
    cx_verts, cx_tris, cx_tex, cx_luz = [], [], [], []
    for nome, curto in CAIXAS:
        info = anims[nome]
        md = m['modelos'][info['modelo']]
        (o, xyz, _) = ler_cru(os.path.join(OUT, info['cru']['arquivo']))[0]
        kc, chao_c = info['cru']['k'][0], info['cru']['chao']
        f = CAIXA_LADO / 524.0
        vs = []
        for i in range(md['vertices']):
            x, y, z = ((o[e] + xyz[3 * i + e]) * kc for e in range(3))
            vs.append((round(x * f), round((y - chao_c) * f), round(z * f), 0))
        if len(vs) != 8 or len(md['triangulos']) != 10:
            raise SystemExit('%s: esperava 8 vértices e 10 triângulos' % nome)
        cx_verts += [v for vv in vs for v in vv]
        for (ta, tb, tc, mt_i) in md['triangulos']:
            mt = md['materiais'][mt_i]
            cx_tris += [ta, tb, tc]
            bx, by = pos_reg[mt['textura']]
            cx_tex += [get_tpage(0, VRAM_TPAGE_X, VRAM_TPAGE_Y),
                       get_clut(VRAM_CLUT_X, VRAM_CLUT_Y + clut_linha[mt['clut']])]
            cx_tex += [((bx + u) & 255) | (((by + v) & 255) << 8) for (u, v) in mt['uv']]
            # brilho da face pela normal (de cima mais claro, dos lados médio)
            p0, p1, p2 = vs[ta], vs[tb], vs[tc]
            ux, uy, uz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
            wx, wy, wz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
            nx, ny, nz = uy * wz - uz * wy, uz * wx - ux * wz, ux * wy - uy * wx
            nn = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            L = [cc / math.sqrt(sum(x * x for x in LUZ)) for cc in LUZ]
            d = abs(nx * L[0] + ny * L[1] + nz * L[2]) / nn
            cx_luz.append(min(255, round(255 * (0.55 + 0.45 * d))))
    c.append('const short crash_caixa_verts[CRASH_NCAIXAS * 8 * 4] = {\n%s\n};' % bloco(cx_verts))
    c.append('const unsigned char crash_caixa_tris[CRASH_NCAIXAS * 10 * 3] = {\n%s\n};' % bloco(cx_tris, 15))
    c.append('const unsigned short crash_caixa_tex[CRASH_NCAIXAS * 10 * 5] = {\n%s\n};' % bloco(cx_tex, 15))
    c.append('const unsigned char crash_caixa_luz[CRASH_NCAIXAS * 10] = {\n%s\n};' % bloco(cx_luz, 10))
    # sons: o corpo ADPCM do .vag (do byte 64 em diante, ver MGB #16), completado até múltiplo de 64
    sons_bytes, sons_tab = bytearray(), []
    for nome, curto in SONS:
        corpo = open(os.path.join(OUT, 'snd', nome + '.vag'), 'rb').read()[64:]
        corpo += bytes((-len(corpo)) % 64)
        sons_tab.append((curto, len(sons_bytes), len(corpo), nome))
        sons_bytes += corpo
    c.append('const CRASH_MODEL crash_models[CRASH_NMODELS] = {')
    for mi, mn in enumerate(modelos):
        md = m['modelos'][mn]
        c.append('    { %d, %d, m%d_tris, m%d_tri_mat, m%d_mats, m%d_mat_tex, m%d_light }, /* %s */'
                 % (md['vertices'], len(md['triangulos']), mi, mi, mi, mi, mi, mn))
    c.append('};')

    # quadros em 6 bits por coordenada (estudo do Claude 2): base por quadro e eixo = origem + menor byte;
    # valor = (byte - menor + 2) // 4, então o vértice volta como base + valor * 4 (erro de até 2 passos)
    blob, ofs, pior = bytearray(), [], 0
    for mi, (o, xyz, _) in keys:
        n = len(xyz) // 3
        n4 = (n + 3) // 4 * 4
        if len(blob) & 1:
            blob.append(0)
        ofs.append(len(blob))
        planos, base = [], []
        for eixo in range(3):
            vals = [xyz[3 * i + eixo] for i in range(n)]
            # o vértice 1 do Crash não pertence a triângulo nenhum (fica no canto da caixa do quadro, abaixo dos
            # pés; achado do Claude 2): fica fora da faixa e é cortado, para não gastar precisão
            usados = [v for i, v in enumerate(vals) if not (mi == 0 and i == 1)]
            menor = min(usados)
            q = [max(0, min(63, (v - menor + 2) // 4)) for v in vals]
            pior = max(pior, max(abs(menor + qq * 4 - v) for i, (qq, v) in enumerate(zip(q, vals))
                                 if not (mi == 0 and i == 1)))
            q += [0] * (n4 - n)
            for i in range(0, n4, 4):
                q0, q1, q2, q3 = q[i:i + 4]
                planos += [q0 | ((q1 & 3) << 6), (q1 >> 2) | ((q2 & 15) << 4), (q2 >> 4) | (q3 << 2)]
            base.append(o[eixo] + menor)
        blob += struct.pack('<hhh', *base) + bytes(planos)
    print('6 bits: pior erro %d passos' % pior)
    c.append('const unsigned long crash_key_ofs[CRASH_NKEYS] = {\n%s\n};' % bloco(ofs, 12))
    c.append('const unsigned char crash_keys[%d] = {\n%s\n};' % (len(blob), bloco(list(blob), 24)))
    c.append('const CRASH_ANIM crash_anims[CRASH_NANIMS] = {')
    for curto, mi, primeiro, nk, passo, laco, nq, nome in tabela:
        c.append('    { %d, %d, %d, %d, %d, %d }, /* %s (%s, %d quadros) */' % (mi, nk, passo, laco, nq, primeiro, curto, nome, nq))
    c.append('};')
    # textura e paletas em palavras de 32 bits: o LoadImage manda por DMA e exige alinhamento de 4 bytes
    # dados usados uma vez só (textura, paletas, sons) não ficam no executável: vão para o fim de uma cópia do
    # BRF.DAT no disco (o briefing não é usado no modo dev) e o jogo lê, manda para a VRAM/SPU e libera
    clut_bytes = struct.pack('<%dH' % len(clut_dados), *clut_dados)
    cd = bytearray()
    cd_ofs = {}
    for nome_cd, dados_cd in (('ATLAS', bytes(atlas)), ('CLUTS', clut_bytes), ('SONS', bytes(sons_bytes))):
        cd += bytes((-len(cd)) % 64)
        cd_ofs[nome_cd] = len(cd)
        cd += dados_cd
    os.makedirs(os.path.dirname(CD_SAIDA), exist_ok=True)
    open(CD_SAIDA, 'wb').write(bytes(cd))
    brf_setor = (os.path.getsize(BRF_ORIGINAL) + 2047) // 2048

    h = ['/* GERADO por motor/empacotar_crash.py a partir de crash_assets/out (Claude 2). Nao editar a mao. */',
         '#ifndef CRASH_DATA_H', '#define CRASH_DATA_H', '',
         '#define CRASH_NMODELS %d' % len(modelos), '#define CRASH_NANIMS %d' % len(tabela),
         '#define CRASH_NKEYS %d' % len(keys),
         '#define CRASH_NV_MAX %d' % nv_max, '#define CRASH_NT_MAX %d' % nt_max,
         '#define CRASH_ESCALA %d   /* (origem + byte) * ESCALA >> 12 = unidades do MGS; altura %g */' % (escala, a.altura),
         '#define CRASH_YOFS %d' % yofs, '#define CRASH_CULL (1)', '',
         '#define CRASH_ATLAS_X %d' % VRAM_TPAGE_X, '#define CRASH_ATLAS_Y %d' % VRAM_TPAGE_Y,
         '#define CRASH_ATLAS_W %d   /* em palavras de 16 bits */' % (ATLAS_LARGURA // 4), '#define CRASH_ATLAS_H %d' % alt_atlas,
         '#define CRASH_CLUT_X %d' % VRAM_CLUT_X, '#define CRASH_CLUT_Y %d' % VRAM_CLUT_Y,
         '#define CRASH_NCLUTS %d' % len(clut_usadas), '',
         '#define CRASH_NCAIXAS %d   /* caixa A, B, C do MGS: %s */' % (len(CAIXAS), ', '.join(cu for _, cu in CAIXAS)), '',
         '/* marcas dos guardas (retangulo na VRAM em palavras de 16 bits) e a paleta delas */']
    for mid, _ in MARCAS:
        mx, my = pos_reg[mid]
        h += ['#define CRASH_%s_X %d' % (mid, VRAM_TPAGE_X + mx // 4), '#define CRASH_%s_Y %d' % (mid, VRAM_TPAGE_Y + my),
              '#define CRASH_%s_W %d' % (mid, MARCA_L // 4), '#define CRASH_%s_H %d' % (mid, MARCA_A)]
    h += ['#define CRASH_MARCA_CLUT_Y %d' % (VRAM_CLUT_Y + clut_marca), '',
          '/* sons na SPU: endereco, e para cada som o deslocamento e o tamanho (bytes) */',
          '#define CRASH_SPU_ADDR 0x%X' % SPU_ENDERECO, '#define CRASH_SONS_BYTES %d' % len(sons_bytes), '',
          '/* no CD: fim do BRF.DAT (setor relativo ao arquivo), lido uma vez por fase */',
          '#define CRASH_CD_SETOR %d' % brf_setor, '#define CRASH_CD_BYTES %d' % len(cd),
          '#define CRASH_CD_ATLAS %d' % cd_ofs['ATLAS'], '#define CRASH_CD_CLUTS %d' % cd_ofs['CLUTS'],
          '#define CRASH_CD_SONS %d' % cd_ofs['SONS']]
    for curto, ofs_s, tam_s, nome in sons_tab:
        h += ['#define CRASH_SOM_%s_OFS %d   /* %s */' % (curto, ofs_s, nome), '#define CRASH_SOM_%s_TAM %d' % (curto, tam_s)]
    h += ['',
         '/* material: flags 1 = liso (sem luz), 2 = textura, 4 = sem descarte de costas, 8 = semitransparente */',
         'typedef struct {', '    unsigned short        nverts, ntris;', '    const unsigned short *tris;',
         '    const unsigned char  *tri_mat;', '    const unsigned char  *mats;     /* r, g, b, flags */',
         '    const unsigned short *mat_tex;  /* tpage, clut, uv0, uv1, uv2 */', '    const unsigned char  *light;',
         '} CRASH_MODEL;', '',
         'typedef struct {', '    unsigned char  model, nkeys, step, loop;   /* step: sempre 1 (sem interpolacao) */', '    unsigned short nframes, first;', '} CRASH_ANIM;', '']
    for i, t in enumerate(tabela):
        h.append('#define CRASH_A_%s %d' % (t[0], i))
    h += ['', 'extern const CRASH_MODEL    crash_models[CRASH_NMODELS];',
          'extern const CRASH_ANIM     crash_anims[CRASH_NANIMS];',
          'extern const unsigned long  crash_key_ofs[CRASH_NKEYS];',
          'extern const unsigned char  crash_keys[];',
          'extern const short          crash_caixa_verts[];   /* 8 vertices x (x, y, z, 0) por caixa */',
          'extern const unsigned char  crash_caixa_tris[];    /* 10 triangulos x 3 indices por caixa */',
          'extern const unsigned short crash_caixa_tex[];     /* por triangulo: tpage, clut, uv0, uv1, uv2 */',
          'extern const unsigned char  crash_caixa_luz[];     /* brilho por triangulo */',
          '', '#endif', '']

    os.makedirs(DEST, exist_ok=True)
    open(os.path.join(DEST, 'crash_data.h'), 'w', encoding='ascii', newline='\n').write('\n'.join(h))
    open(os.path.join(DEST, 'crash_data.c'), 'w', encoding='ascii', newline='\n').write('\n'.join(c) + '\n')
    tam_modelos = sum(len(m['modelos'][mn]['triangulos']) * 7 + len(m['modelos'][mn]['materiais']) * 14 +
                      m['modelos'][mn]['vertices'] for mn in modelos)
    print('%d animações, %d quadros-chave: %.1f KB de quadros + %.1f KB de modelos + %.1f KB de textura (atlas %dx%d, %d paletas)'
          % (len(tabela), len(keys), len(blob) / 1024, tam_modelos / 1024, (len(atlas) + 2 * len(clut_dados)) / 1024,
             ATLAS_LARGURA, alt_atlas, len(clut_usadas)))


if __name__ == '__main__':
    main()
