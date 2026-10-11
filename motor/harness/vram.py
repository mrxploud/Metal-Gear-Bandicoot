"""Lê a VRAM (1024x512, 16 bits) de dentro do estado salvo do PCSX ReARMed.
A posição é achada procurando na memória do estado uma linha da imagem que está na tela."""
import numpy as np


def vram(ps):
    st = ps.save_state()
    img = ps.image().astype(np.uint16)
    for linha in range(40, 200, 7):
        px = img[linha, 0:64]
        if px.std() < 2:
            continue
        v = ((px[:, 2] >> 3) << 10) | ((px[:, 1] >> 3) << 5) | (px[:, 0] >> 3)
        j = st.find(v.astype('<u2').tobytes()[:48])
        if j < 0:
            continue
        # a tela fica em y = linha - 8 (8 linhas de borda) e x = 0 ou 320
        for y0 in (linha - 8, linha - 8 + 0):
            base = j - y0 * 2048
            if base >= 0 and base + 1024 * 512 * 2 <= len(st):
                return np.frombuffer(st[base:base + 1024 * 512 * 2], '<u2').reshape(512, 1024).copy()
    raise RuntimeError('não achei a VRAM no estado')


def textura_4bits(v, x, y, largura_px, altura, clut_x, clut_y):
    """Desenha uma área de 4 bits da VRAM com a paleta em (clut_x, clut_y) como imagem RGB."""
    pal = v[clut_y, clut_x:clut_x + 16]
    palrgb = np.stack([(pal & 31) << 3, ((pal >> 5) & 31) << 3, ((pal >> 10) & 31) << 3], -1).astype(np.uint8)
    w = largura_px // 4
    area = v[y:y + altura, x:x + w]
    idx = np.stack([(area >> (4 * k)) & 15 for k in range(4)], -1).reshape(altura, w * 4)
    return palrgb[idx]
