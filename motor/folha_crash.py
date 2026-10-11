"""Folha de contato do Crash de perto: roda um cenário de botões no robô e recorta o Crash (achado pela cor
laranja do pelo) quadro a quadro, ampliado. Serve para ver animação quebrada que de longe não aparece.

    python -I motor/folha_crash.py --disco motor/out/dev/mgb.cue --cenario engatinhar --de 60 --ate 124 --saida x.png
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

MOTOR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(MOTOR, 'harness'))
sys.path.insert(0, MOTOR)
from psx import PSX  # noqa: E402
from teste_dock import ligar_no_dock, simbolos  # noqa: E402
from medir_acoes import CENARIOS  # noqa: E402


def centro_laranja(img):
    r, g, b = img[..., 0].astype(int), img[..., 1].astype(int), img[..., 2].astype(int)
    m = (r > 170) & (g > 50) & (g < 160) & (b < 90)
    m[:, int(img.shape[1] * 0.72):] = False          # o radar no canto
    ys, xs = np.nonzero(m)
    if len(xs) < 5:
        return None
    return int(np.median(xs)), int(np.median(ys))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--disco', default=os.path.join(MOTOR, 'out', 'dev', 'mgb.cue'))
    ap.add_argument('--cenario', required=True)
    ap.add_argument('--de', type=int, default=0)
    ap.add_argument('--ate', type=int, default=9999)
    ap.add_argument('--passo', type=int, default=2)
    ap.add_argument('--raio', type=int, default=36)
    ap.add_argument('--zoom', type=int, default=3)
    ap.add_argument('--colunas', type=int, default=8)
    ap.add_argument('--saida', required=True)
    a = ap.parse_args()

    sym = simbolos()
    ps = PSX(a.disco)
    ligar_no_dock(ps)
    recortes, q, ultimo = [], 0, None
    for botoes, n in CENARIOS[a.cenario]:
        for _ in range(n):
            ps.run(1, botoes)
            q += 1
            if a.de <= q <= a.ate and (q - a.de) % a.passo == 0:
                img = ps.image()
                c = centro_laranja(img) or ultimo or (img.shape[1] // 2, img.shape[0] // 2)
                ultimo = c
                x0, y0 = max(0, c[0] - a.raio), max(0, c[1] - a.raio)
                rec = Image.fromarray(img[y0:y0 + 2 * a.raio, x0:x0 + 2 * a.raio])
                rec = rec.resize((2 * a.raio * a.zoom, 2 * a.raio * a.zoom), Image.NEAREST)
                legenda = 'q%d a%d %s f%d' % (q, ps.s32(sym['crash_dbg_action']), ps.s32(sym['crash_dbg_anim']),
                                               ps.s32(sym['crash_dbg_frame']) if 'crash_dbg_frame' in sym else -1)
                recortes.append((rec, legenda))
    lado = 2 * a.raio * a.zoom
    lin = (len(recortes) + a.colunas - 1) // a.colunas
    folha = Image.new('RGB', (a.colunas * lado, lin * (lado + 14)), (20, 20, 20))
    d = ImageDraw.Draw(folha)
    for i, (rec, leg) in enumerate(recortes):
        x, y = (i % a.colunas) * lado, (i // a.colunas) * (lado + 14)
        folha.paste(rec, (x, y + 14))
        d.text((x + 2, y + 1), leg, fill=(255, 255, 0))
    folha.save(a.saida)
    print(a.saida, len(recortes), 'quadros')


if __name__ == '__main__':
    main()
