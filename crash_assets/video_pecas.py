"""Peças do Crash para o vídeo da fusão (lado Crash, Claude 2), lidas SÓ da entrega `out_c3` (sem disco):

  crash_montando/{pontos,arame,tex}_NNN.png   o Cr10G parado girando 360 graus em 3 versões com o MESMO ângulo por
                                              quadro: só os vértices, o arame dos triângulos e com textura
  pernas_andando/NNN.png                      o Cgb0G (a metade de baixo do Crash da bazuca) andando em laço
  anjo/NNN.png                                a morte do Crash no jogo dele (C3_MORTE_ANJO): vira anjinho e sobe

    python -I video_pecas.py [--saida video] [--tamanho 540] [--quadros 72]

Fundo transparente. O vídeo monta as sequências no Remotion (uma imagem por quadro).
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from crashlib import raster  # noqa: E402
from ver3 import Entrega  # noqa: E402


def projetar(v, centro, raio, tamanho, guinada, inclinacao):
    rot = raster.rotacao(guinada, inclinacao)
    cam = (np.asarray(v, np.float64) - centro) @ rot.T
    escala = (tamanho * 0.46) / raio
    return np.stack([tamanho / 2 + cam[:, 0] * escala, tamanho / 2 - cam[:, 1] * escala, cam[:, 2]], 1)


def pontos(v, enquadre, t, g, inc, cor=(255, 154, 107)):
    p = projetar(v, enquadre[0], enquadre[1], t * 2, g, inc)
    im = Image.new('RGBA', (t * 2, t * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    z0, z1 = p[:, 2].min(), p[:, 2].max()
    for x, y, z in p[np.argsort(p[:, 2])]:
        k = (z - z0) / (z1 - z0 + 1e-9)
        r = 3 + 4 * k
        d.ellipse([x - r, y - r, x + r, y + r], fill=(cor[0], cor[1], cor[2], int(110 + 145 * k)))
    return im.resize((t, t), Image.LANCZOS)


def arame(v, tris, enquadre, t, g, inc, cor=(77, 163, 255)):
    p = projetar(v, enquadre[0], enquadre[1], t * 2, g, inc)
    im = Image.new('RGBA', (t * 2, t * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    ordem = sorted(tris, key=lambda tr: float(p[list(tr['v']), 2].mean()))
    z0, z1 = p[:, 2].min(), p[:, 2].max()
    for tr in ordem:
        a, b, c = tr['v']
        k = (float(p[[a, b, c], 2].mean()) - z0) / (z1 - z0 + 1e-9)
        linha = (cor[0], cor[1], cor[2], int(70 + 185 * k))
        d.line([tuple(p[a, :2]), tuple(p[b, :2]), tuple(p[c, :2]), tuple(p[a, :2])], fill=linha, width=2)
    return im.resize((t, t), Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--saida', default=os.path.join(AQUI, 'video'))
    ap.add_argument('--tamanho', type=int, default=540)
    ap.add_argument('--quadros', type=int, default=72)
    ap.add_argument('--so', help='montando, pernas, anjo ou caixa1')
    a = ap.parse_args()
    e = Entrega(os.path.join(AQUI, 'out_c3'))
    t = a.tamanho

    if a.so in (None, 'montando'):
        an = e.anims['C3_PARADO']
        pos = e.posicoes(an)
        tris = e.triangulos(an['modelo'])
        todos = pos.reshape(-1, 3)
        centro = (todos.min(0) + todos.max(0)) / 2
        raio = float(np.linalg.norm(todos - centro, axis=1).max())
        pasta = os.path.join(a.saida, 'crash_montando')
        os.makedirs(pasta, exist_ok=True)
        n = a.quadros
        for i in range(n):
            g = 25 + 360.0 * i / n
            k = i * len(pos) / n                         # o parado respira: uma volta = um ciclo da animação
            k0, fr = int(k) % len(pos), k - int(k)
            v = pos[k0] * (1 - fr) + pos[(k0 + 1) % len(pos)] * fr
            pontos(v, (centro, raio), t, g, 10).save(os.path.join(pasta, 'pontos_%03d.png' % i))
            arame(v, tris, (centro, raio), t, g, 10).save(os.path.join(pasta, 'arame_%03d.png' % i))
            raster.desenhar(v, None, tris, t, g, 10, (centro, raio), amostras=2).save(os.path.join(pasta, 'tex_%03d.png' % i))
        print('crash_montando: %d quadros x 3 em %s (%d vértices, %d triângulos)' % (n, pasta, pos.shape[1], len(tris)))

    if a.so in (None, 'pernas'):
        an = e.anims['C3_BAZUCA_PERNAS_ANDANDO']
        pos = e.posicoes(an)
        tris = e.triangulos(an['modelo'])
        # enquadre do Crash inteiro, para as pernas ficarem do tamanho certo, no chão
        ref = e.posicoes(e.anims['C3_PARADO']).reshape(-1, 3)
        centro = (ref.min(0) + ref.max(0)) / 2
        raio = float(np.linalg.norm(ref - centro, axis=1).max())
        pasta = os.path.join(a.saida, 'pernas_andando')
        os.makedirs(pasta, exist_ok=True)
        n = len(pos) * 4                                 # 4 imagens por chave (o jogo também faz a média entre chaves)
        for i in range(n):
            k = i / 4
            k0, fr = int(k) % len(pos), k - int(k)
            v = pos[k0] * (1 - fr) + pos[(k0 + 1) % len(pos)] * fr
            raster.desenhar(v, None, tris, t, 60, 10, (centro, raio), amostras=2).save(os.path.join(pasta, '%03d.png' % i))
        print('pernas_andando: %d quadros em %s' % (n, pasta))

    if a.so in (None, 'anjo'):
        # a morte do Crash no jogo dele: vira anjinho e sobe (C3_MORTE_ANJO, modelo Cda0G)
        an = e.anims['C3_MORTE_ANJO']
        pos = e.posicoes(an)
        tris = e.triangulos(an['modelo'])
        todos = pos.reshape(-1, 3)
        centro = (todos.min(0) + todos.max(0)) / 2
        raio = float(np.linalg.norm(todos - centro, axis=1).max())
        pasta = os.path.join(a.saida, 'anjo')
        os.makedirs(pasta, exist_ok=True)
        n = (len(pos) - 1) * 2
        for i in range(n):
            k0, fr = i // 2, (i % 2) / 2
            v = pos[k0] * (1 - fr) + pos[k0 + 1] * fr
            raster.desenhar(v, None, tris, t, 20, 8, (centro, raio), amostras=2).save(os.path.join(pasta, '%03d.png' % i))
        print('anjo: %d quadros em %s' % (n, pasta))

    if a.so in (None, 'caixa1'):
        # a caixa de madeira do Crash 1 (BN10G, 10 triângulos) girando, lida da entrega do Crash 1 (`out`), desenhada
        # como o PS1 desenha: só o lado de fora de cada face. Pelas costas não há face: vê-se através dela.
        import ver
        e1 = ver.Entrega(os.path.join(AQUI, 'out'))
        an, pos, nor = e1.animacao('BOX_NORMAL')
        tris = e1.triangulos(an['modelo'])
        v = pos[0]
        centro = (v.min(0) + v.max(0)) / 2
        raio = float(np.linalg.norm(v - centro, axis=1).max())
        pasta = os.path.join(a.saida, 'caixa1')
        os.makedirs(pasta, exist_ok=True)
        n = a.quadros
        vistos = []
        for i in range(n):
            g = 360.0 * i / n
            rot = raster.rotacao(g, 16)
            de_frente = []
            for tr in tris:
                p0, p1, p2 = (v[k] for k in tr['v'])
                nrm = np.cross(p1 - p0, p2 - p0)
                if np.dot(nrm, (p0 + p1 + p2) / 3 - centro) < 0:
                    nrm = -nrm
                if (rot @ nrm)[2] > 0:
                    de_frente.append(tr)
            vistos.append(len(de_frente))
            raster.desenhar(v, nor[0], de_frente, t, g, 16, (centro, raio * 1.15), amostras=2).save(os.path.join(pasta, '%03d.png' % i))
        print('caixa1: %d quadros em %s; triângulos de frente por quadro: min %d, max %d (de %d)' % (n, pasta, min(vistos), max(vistos), len(tris)))


if __name__ == '__main__':
    main()
