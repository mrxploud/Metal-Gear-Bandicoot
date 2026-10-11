#!/usr/bin/env python3
"""Uma imagem só com as animações principais do Crash 3, para o ByteMirage ver e escolher. Lê só a entrega.

    python -I mostruario3.py [saida.png]
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from crashlib import raster                                   # noqa: E402
from ver3 import Entrega                                      # noqa: E402

LINHAS = [
    ('C3_PARADO', 'Parado', 30), ('C3_CORRER', 'Correr', 60), ('C3_AGACHAR', 'Agachar', 40),
    ('C3_ENGATINHAR', 'ENGATINHAR', 60), ('C3_DERRAPADA', 'DERRAPADA', 70), ('C3_GIRO_LEVE', 'O giro', 20),
    ('C3_BAZUCA_SACA', 'Bazuca de Wumpa (só o tronco)', 40), ('C3_BAZUCA_PERNAS_ANDANDO', '...e as pernas', 50),
    ('C3_CAI_DE_CARA', 'Morte: cai de cara', 60), ('C3_MORTE_OLHOS_E_TENIS', 'Morte: olhos e tênis', 30),
    ('C3_MORTE_ANJO', 'Morte: anjinho', 30), ('C3_DANCA_1', 'A dança da vitória', 20), ('C3_IOIO', 'Parado: ioiô', 30),
]


def fonte(tam):
    for nome in ('arialbd.ttf', 'arial.ttf', 'DejaVuSans-Bold.ttf'):
        try:
            return ImageFont.truetype(nome, tam)
        except OSError:
            pass
    return ImageFont.load_default()


def principal():
    e = Entrega(os.path.join(AQUI, 'out_c3'))
    n, tam, margem = 9, 132, 250
    folha = Image.new('RGBA', (margem + n * tam, 56 + len(LINHAS) * tam), (24, 24, 32, 255))
    d = ImageDraw.Draw(folha)
    d.text((12, 12), 'Crash Bandicoot 3 (Warped), tirado do disco do ByteMirage: o novo corpo do Metal Gear Bandicoot',
           fill=(255, 200, 60, 255), font=fonte(22))
    for r, (nome, rotulo, guinada) in enumerate(LINHAS):
        a = e.anims[nome]
        pos = e.posicoes(a)
        tris = e.triangulos(a['modelo'])
        todos = pos.reshape(-1, 3)
        centro = (todos.min(0) + todos.max(0)) / 2
        raio = float(np.linalg.norm(todos - centro, axis=1).max()) or 1.0
        k = len(pos)
        idx = list(range(k)) if k <= n else [round(i * (k - 1) / (n - 1)) for i in range(n)]
        y = 56 + r * tam
        for c, i in enumerate(idx):
            folha.alpha_composite(raster.desenhar(pos[i], None, tris, tam, guinada, 10, (centro, raio), amostras=2),
                                  (margem + c * tam, y))
        d.text((12, y + 36), rotulo, fill=(255, 255, 255, 255), font=fonte(18))
        d.text((12, y + 62), f'{a["quadros"]} quadros-chave no disco\no jogo toca {a["toca"]}  ·  {a["origem_no_disco"]}',
               fill=(170, 170, 185, 255), font=fonte(13))
    saida = sys.argv[1] if len(sys.argv) > 1 else os.path.join(AQUI, 'out_c3', 'previews', 'para_o_bytemirage.png')
    folha.convert('RGB').save(saida)
    print('salvo', saida)


if __name__ == '__main__':
    principal()
