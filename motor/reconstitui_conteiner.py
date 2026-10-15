"""RECONSTITUIÇÃO do primeiro bug do coop (14/10/2026): o Crash 2 nascia 900 à frente do Crash, dentro do contêiner do
Heliporto, e ficava invisível e preso. O clipe original foi sobrescrito; aqui o Crash 2 (versão consertada) é posto
no mesmo ponto (-4605, 19549) e tenta andar. Grava `reconstituicao_crash2_no_conteiner`.

    motor/.venv/Scripts/python.exe -I motor/reconstitui_conteiner.py --estado motor/out/coop12b/fase.state
"""
import argparse
import os
import sys

MOTOR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, MOTOR)
from teste_coop import Coop  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--disco', default=os.path.join(MOTOR, 'out', 'teste12', 'mgb.cue'))
    ap.add_argument('--mapa', default=os.path.join(MOTOR, 'out', 'teste12', 'asm.map'))
    ap.add_argument('--estado', default=os.path.join(MOTOR, 'out', 'coop12b', 'fase.state'))
    a = ap.parse_args()
    t = Coop(a.disco, a.mapa, os.path.join(MOTOR, 'out', 'reconstituicao'))
    rec, ps, S = t.rec, t.ps, t.S
    ps.load_state(a.estado)
    rec.passo((), 2)
    rec.passo((), 2, botoes2=['START'])
    rec.passo((), 10)
    c2 = ps.u32(S['crash2_control'])
    ps.w16(c2, -4605)
    ps.w16(c2 + 4, 19549)
    ps.w16(c2 + 2, 1100)
    rec.start()
    rec.mark('RECONSTITUICAO: o Crash 2 onde nascia no primeiro teste')
    rec.passo((), 60)
    rec.passo((), 60, botoes2=['RIGHT'])
    rec.passo((), 60, botoes2=['UP'])
    rec.passo((), 30, botoes2=['CROSS'])
    rec.passo((), 60)
    t.info('fim')
    rec.foto(os.path.join(t.saida, 'reconstituicao.png'))
    rec.stop()
    rec.save('reconstituicao_crash2_no_conteiner',
             descricao='RECONSTITUIÇÃO (não é a gravação original): o Crash 2 posto onde nascia no 1º teste do coop')


if __name__ == '__main__':
    main()
