"""Teste da bazuca de Wumpa no robô: o Crash vira para um guarda, segura o quadrado (saca e mira), solta (atira) e
anda mirando. Folha de perto + o que o jogo conta (estado da bazuca, Wumpas que acertaram).

    python -I motor/teste_bazuca.py [--disco motor/out/dev/mgb.cue] [--saida motor/out/bazuca/folha.png]
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw

MOTOR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(MOTOR, 'harness'))
sys.path.insert(0, MOTOR)
from psx import PSX  # noqa: E402
from teste_dock import ligar_no_dock, simbolos  # noqa: E402
from folha_crash import centro_laranja  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--disco', default=os.path.join(MOTOR, 'out', 'dev', 'mgb.cue'))
    ap.add_argument('--saida', default=os.path.join(MOTOR, 'out', 'bazuca', 'folha.png'))
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.saida), exist_ok=True)
    sym = simbolos()
    ps = PSX(a.disco)
    ligar_no_dock(ps)
    ps.run(30)
    ctrl = ps.u32(sym['GM_PlayerControl'])
    gx, gz = -5750, -16250
    ps.w16(ctrl, gx + 2200)
    ps.w16(ctrl + 4, gz + 100)
    ps.run(10)
    ps.run(3, ['LEFT'])
    ps.run(10)
    seq = [(['SQUARE'], 40), ([], 12), (['SQUARE'], 14), ([], 12), (['SQUARE'], 14), ([], 16),
           (['SQUARE', 'LEFT'], 24), ([], 30)]
    fotos, q, raio = [], 0, 70
    for botoes, n in seq:
        for _ in range(n):
            ps.run(1, botoes)
            q += 1
            if q % 4 == 0:
                img = ps.image()
                c = centro_laranja(img) or (160, 120)
                x0, y0 = max(0, c[0] - raio), max(0, c[1] - raio)
                im = Image.fromarray(img[y0:y0 + 2 * raio, x0:x0 + 2 * raio]).resize((4 * raio, 4 * raio), Image.NEAREST)
                ImageDraw.Draw(im).text((3, 3), 'q%d %s baz %d wumpas %d' % (
                    q, '+'.join(botoes) or '-', ps.s32(sym['crash_dbg_baz']), ps.s32(sym['crash_dbg_wumpa'])),
                    fill=(255, 255, 0))
                fotos.append(im)
    col = 8
    lado = 4 * raio
    folha = Image.new('RGB', (col * lado, lado * ((len(fotos) + col - 1) // col)))
    for i, f in enumerate(fotos):
        folha.paste(f, ((i % col) * lado, (i // col) * lado))
    folha.save(a.saida)
    print('folha:', a.saida, '| wumpas que acertaram:', ps.s32(sym['crash_dbg_wumpa']))


if __name__ == '__main__':
    main()
