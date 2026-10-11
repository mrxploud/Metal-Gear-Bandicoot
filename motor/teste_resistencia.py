"""Teste de resistência: N segundos de botões aleatórios no Dock, medindo memória e travamentos.

    python -I motor/teste_resistencia.py --estado motor/out/<teste>/dock.state [--segundos 180]
"""
import argparse
import os
import random
import sys

MOTOR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(MOTOR, 'harness'))
from psx import PSX  # noqa: E402
import diag  # noqa: E402
from PIL import Image  # noqa: E402

ACOES = [['LEFT'], ['RIGHT'], ['UP'], ['DOWN'], ['UP', 'LEFT'], ['DOWN', 'RIGHT'], ['CIRCLE'], ['CROSS'], [], ['SQUARE'], ['SQUARE', 'LEFT'],
         ['TRIANGLE']]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--estado', required=True)
    ap.add_argument('--segundos', type=int, default=180)
    ap.add_argument('--semente', type=int, default=7)
    a = ap.parse_args()
    ps = PSX(os.path.join(MOTOR, 'out', 'dev', 'mgb.cue'))
    ps.load_state(a.estado)
    random.seed(a.semente)
    pior = {'residente_livre': 999, 'pacotes0': 999, 'pacotes1': 999, 'normal': 999}
    t0 = ps.u32(diag.sym('GV_Time'))
    fotos = []
    for seg in range(a.segundos):
        for _ in range(4):
            ps.run(15, random.choice(ACOES))
        m = diag.memoria(ps)
        for k in pior:
            v = m[k] if k == 'residente_livre' else m[k][1]
            pior[k] = min(pior[k], v)
        if seg % 30 == 29:
            fotos.append(Image.fromarray(ps.image()))
    dt = ps.u32(diag.sym('GV_Time')) - t0
    print('menor memória livre (KB; pacotes e normal = maior bloco):', pior)
    print('relógio do jogo andou %d vsyncs em %d s (esperado ~%d)' % (dt, a.segundos, a.segundos * 60))
    print('quadros do Crash sem memória:', ps.s32(diag.sym('crash_dbg_nomem')))
    folha = Image.new('RGB', (320 * len(fotos), 240))
    for i, f in enumerate(fotos):
        folha.paste(f, (i * 320, 0))
    folha.save(os.path.join(os.path.dirname(a.estado), 'resistencia.png'))


if __name__ == '__main__':
    main()
