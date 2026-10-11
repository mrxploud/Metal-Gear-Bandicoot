"""Teste rápido da fusão: remonta o disco com o executável atual, liga o jogo no robô, escolhe o Loading Dock,
espera a fase carregar e tira fotos. Salva um estado no Dock para os próximos testes.

    python -I motor/teste_dock.py [--sem-disco] [--segundos 12] [--nome teste]
"""
import argparse
import os
import re
import subprocess
import sys

MOTOR = os.path.dirname(os.path.abspath(__file__))
FUSAO = os.path.dirname(MOTOR)
sys.path.insert(0, os.path.join(MOTOR, 'harness'))
from psx import PSX  # noqa: E402

DISCO_MGS = os.path.join(FUSAO, 'discs', 'mgs_d1', 'Metal Gear Solid - Integral (Japan) (En,Ja) (Disc 1).cue')
CUE = os.path.join(MOTOR, "out", "dev", "mgb.cue")
MAPA = os.path.join(FUSAO, 'repos', 'mgs_reversing', 'obj_dev', 'asm.map')


def simbolos():
    sym = {}
    for linha in open(MAPA, encoding='latin-1'):
        m = re.match(r'\s+([0-9A-F]{8})\s+(\S+)\s*$', linha)
        if m:
            sym[m.group(2)] = int(m.group(1), 16)
    return sym


def pedir_seletor(ps, sym=None):
    """Logo depois de ligar: pede o seletor de fases no lugar do título (o executável já está na RAM)."""
    sym = sym or simbolos()
    ps.run(30)
    if 'MGB_SeletorDeFases' in sym:
        ps.w32(sym['MGB_SeletorDeFases'], 1)


def ligar_no_dock(ps, sym=None):
    """Do boot até o controle do Snake no Loading Dock (seletor de fases do dev_exe: TITLE, D00A, S00A).
    Desde o teste 10 o jogo abre no título; o seletor só aparece com MGB_SeletorDeFases = 1 antes do título."""
    pedir_seletor(ps, sym)
    ps.run(1170)
    for _ in range(2):
        ps.press(['DOWN'], 2, 8)
    ps.run(5)
    ps.press(['CIRCLE'], 2, 2)
    ps.run(60 * 9)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sem-disco', action='store_true', help='não remonta o disco')
    ap.add_argument('--segundos', type=int, default=4)
    ap.add_argument('--nome', default='teste')
    a = ap.parse_args()

    if not a.sem_disco:
        subprocess.run([sys.executable, '-I', os.path.join(MOTOR, 'montar_disco.py'), '--disco', DISCO_MGS,
                        '--saida', os.path.join(MOTOR, 'out', 'dev', 'mgb')],
                       check=True, stdout=subprocess.DEVNULL)
    pasta = os.path.join(MOTOR, 'out', a.nome)
    os.makedirs(pasta, exist_ok=True)
    ps = PSX(CUE)
    ligar_no_dock(ps)
    ps.save_state(os.path.join(pasta, 'dock.state'))
    sym = simbolos()
    for s in range(a.segundos):
        ps.run(60)
        ps.shot(os.path.join(pasta, 'dock_%02d.png' % s))
    if 'crash_last_count' in sym:
        print('triangulos do Crash no ultimo quadro:', ps.u32(sym['crash_last_count']))
    print('fotos em', pasta)


if __name__ == '__main__':
    main()
