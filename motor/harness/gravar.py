"""Grava um trecho do robô como GIF (recortado no Crash, ampliado) e como PNGs crus por quadro."""
import os
from PIL import Image
from recorte import achar_crash


def gravar_gif(ps, roteiro, caminho, lado=96, escala=3, fixo=None):
    """roteiro: lista de (botoes, quadros). A câmera do recorte segue o Crash (ou usa a caixa 'fixo')."""
    quadros = []
    cx = cy = None
    for botoes, n in roteiro:
        for _ in range(n):
            ps.run(2, botoes)          # o MGS desenha a 30 qps: 1 imagem a cada 2 vsyncs
            img = Image.fromarray(ps.image())
            caixa = fixo or achar_crash(img)
            if caixa:
                nx, ny = (caixa[0] + caixa[2]) // 2, (caixa[1] + caixa[3]) // 2
                cx = nx if cx is None else (cx * 3 + nx) // 4
                cy = ny if cy is None else (cy * 3 + ny) // 4
            if cx is None:
                cx, cy = img.width // 2, img.height // 2
            r = lado // 2
            quadros.append(img.crop((cx - r, cy - r, cx + r, cy + r)).resize((lado * escala, lado * escala), Image.NEAREST))
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    quadros[0].save(caminho, save_all=True, append_images=quadros[1:], duration=33, loop=0)
    return len(quadros)
