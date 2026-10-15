"""Teste de subir nas coisas (o topo de um obstáculo vira chão), gravando no projeto do vídeo.

    motor/.venv/Scripts/python.exe -I motor/teste_subir.py --estado motor/out/coop/fase.state

Parte de um estado no Heliporto (motor/teste_coop.py salva um em motor/out/coop/fase.state) e tenta subir:
1) no bloco baixo perto do heliponto (topo 500, chão 0), com um pulo;
2) no contêiner do lado leste (topo 3250, chão 1500, 1750 de altura), com o pulo duplo;
3) o Crash 2 no mesmo contêiner.
"""
import argparse
import json
import os
import sys

MOTOR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, MOTOR)
from teste_coop import Coop, FUSAO  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--disco', default=os.path.join(MOTOR, 'out', 'dev', 'mgb.cue'))
    ap.add_argument('--mapa', default=os.path.join(FUSAO, 'repos', 'mgs_reversing', 'obj_dev', 'asm.map'))
    ap.add_argument('--estado', default=os.path.join(MOTOR, 'out', 'coop', 'fase.state'))
    ap.add_argument('--saida', default=os.path.join(MOTOR, 'out', 'subir'))
    a = ap.parse_args()
    t = Coop(a.disco, a.mapa, a.saida)
    rec, ps, S = t.rec, t.ps, t.S
    ps.load_state(a.estado)
    rec.passo((), 2)
    # os guardas não veem (stealth): o teste é só de subir
    ps.w16(S['linkvarbuf'] + 47 * 2, 1)
    ps.w16(S['linkvarbuf'] + 15 * 2, 10)
    res = {}

    def tenta(nome, x, z, y, dir_botao, duplo, botoes2=False, para=8):
        rec.ir(x, z, y)
        rec.passo((), 20)
        st = ps.save_state()
        rec.start()
        t.info(nome + ' antes')
        rec.mark(nome)
        b = [dir_botao]
        if botoes2:
            rec.passo((), 10, botoes2=[dir_botao])
            rec.passo((), 14, botoes2=[dir_botao, 'CROSS'])
            if duplo:
                rec.passo((), 4, botoes2=[dir_botao])
                rec.passo((), 14, botoes2=[dir_botao, 'CROSS'])
            rec.passo((), para, botoes2=[dir_botao])
            rec.passo((), 50)
        else:
            rec.passo(b, 10)
            rec.passo(b + ['CROSS'], 14)
            if duplo:
                rec.passo(b, 4)
                rec.passo(b + ['CROSS'], 14)
            rec.passo(b, para)
            rec.passo((), 50)
        x = t.info(nome + ' depois')
        rec.foto(os.path.join(a.saida, nome + '.png'))
        rec.stop()
        rec.sheet(os.path.join(a.saida, nome + '_folha.png'), cada=8, colunas=10)
        rec.save('subir_' + nome, descricao='Crash subindo: ' + nome)
        res[nome] = x
        return st

    tenta('conteiner', 11875, 7300, 2600, 'UP', True, para=14)
    # o Crash 2 entra e tenta o contêiner
    rec.ir(11000, 8200, 2600)
    rec.passo((), 2, botoes2=['START'])
    rec.passo((), 30)
    c2 = ps.u32(S['crash2_control'])
    if 0x80000000 <= c2 < 0x80200000:
        ps.w16(c2, 11875)
        ps.w16(c2 + 4, 7300)
        ps.w16(c2 + 2, 2600)
    rec.passo((), 10)
    tenta('conteiner_crash2', 11000, 8200, 2600, 'UP', True, botoes2=True, para=14)
    json.dump({k: v for k, v in res.items()}, open(os.path.join(a.saida, 'resultado.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
