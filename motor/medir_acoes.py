"""Mede, quadro a quadro, a ação do Snake (índice no snake.oar), a animação do Crash e a posição, em cenários de
botões: é o que decide qual animação do Crash toca e mostra onde ela quebra.

    python -I motor/medir_acoes.py [--disco motor/out/teste5/mgb.cue] [--so engatinhar] [--fotos]
"""
import argparse
import os
import sys

MOTOR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(MOTOR, 'harness'))
sys.path.insert(0, MOTOR)
from psx import PSX  # noqa: E402
from teste_dock import ligar_no_dock, simbolos  # noqa: E402

# cenários: lista de (botões, quadros). Do começo do Dock, a esquerda (oeste) é chão aberto.
CENARIOS = {
    'engatinhar': [(['CROSS'], 4), ([], 20), (['LEFT'], 120), ([], 20)],
    'engatinhar_X_segurado': [(['CROSS'], 30), (['CROSS', 'LEFT'], 120), (['CROSS'], 20)],
    'correr_e_X': [(['LEFT'], 30), (['LEFT', 'CROSS'], 4), (['LEFT'], 60), ([], 30)],
    'correr_e_X_solta': [(['LEFT'], 30), (['LEFT', 'CROSS'], 4), ([], 60)],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--disco', default=os.path.join(MOTOR, 'out', 'teste5', 'mgb.cue'))
    ap.add_argument('--nome', default='acoes')
    ap.add_argument('--so', help='rodar só este cenário')
    ap.add_argument('--fotos', action='store_true', help='uma foto a cada 4 quadros')
    a = ap.parse_args()

    pasta = os.path.join(MOTOR, 'out', a.nome)
    os.makedirs(pasta, exist_ok=True)
    sym = simbolos()
    ps = PSX(a.disco)
    ligar_no_dock(ps)
    inicio = ps.save_state()
    quadro_sym = sym.get('crash_dbg_frame')

    for nome, passos in CENARIOS.items():
        if a.so and nome != a.so:
            continue
        ps.load_state(inicio)
        print('== %s' % nome)
        q = 0
        for botoes, n in passos:
            for _ in range(n):
                ps.run(1, botoes)
                q += 1
                ac, an = ps.s32(sym['crash_dbg_action']), ps.s32(sym['crash_dbg_anim'])
                fr = ps.s32(quadro_sym) if quadro_sym else -1
                x, z = ps.s16(sym['GM_PlayerPosition']), ps.s16(sym['GM_PlayerPosition'] + 4)
                print('  %3d [%-11s] ação %3d  anim %2d  quadro %2d  pos (%6d, %6d)'
                      % (q, '+'.join(botoes) or '-', ac, an, fr, x, z))
                if a.fotos and q % 4 == 0:
                    ps.shot(os.path.join(pasta, '%s_%03d.png' % (nome, q)), scale=1)


if __name__ == '__main__':
    main()
