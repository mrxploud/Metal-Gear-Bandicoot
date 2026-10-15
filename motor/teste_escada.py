"""Teste da escadaria do Heliporto (o ByteMirage: "o jogo trava quando subo as escadas para entrar nos dutos").

    motor/.venv/Scripts/python.exe -I motor/teste_escada.py --disco motor/out/teste11/mgb.cue --mapa motor/out/teste11/asm.map --estado <heliporto.state>

A escadaria fica no lado leste (gatilhos "stair"): 1º lance de x 10375 a 11875 (altura 1500 -> 3000), patamar, 2º lance
de x 12125 a 9125 (3000 -> 6000), deque em 6000 e o duto de cima no corredor x -2000..-1000, z < -17500.
Sobe de quatro jeitos (andando, pulando a cada passo, pulo duplo e girando), gravando cada um; marca "TRAVOU" se o
tempo do jogo parar ou o Crash não responder por 10 s.
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
    ap.add_argument('--saida', default=os.path.join(MOTOR, 'out', 'escada'))
    ap.add_argument('--nome', default='escada')
    ap.add_argument('--modos', nargs='*', default=['andando', 'pulando', 'duplo', 'girando'])
    a = ap.parse_args()
    t = Coop(a.disco, a.mapa, a.saida)
    rec, ps, S = t.rec, t.ps, t.S
    ps.load_state(a.estado)
    rec.passo((), 2)
    ps.w16(S['linkvarbuf'] + 47 * 2, 1)   # stealth: os guardas não atrapalham
    ps.w16(S['linkvarbuf'] + 15 * 2, 10)
    base = ps.save_state()
    resultado = {}

    def ate(botoes, cond, extra, max_q=480):
        """anda com `botoes` (+ o modo) até cond(x, y, z); devolve False se não chegou."""
        for i in range(0, max_q, 4):
            b = list(botoes)
            if extra == 'pulando' and (i // 4) % 6 == 0:
                b.append('CROSS')
            elif extra == 'duplo' and (i // 4) % 10 in (0, 3):
                b.append('CROSS')
            elif extra == 'girando' and (i // 4) % 8 == 0:
                b.append('CIRCLE')
            rec.passo(b, 4)
            x, y, z = rec.onde()
            if cond(x, y, z):
                return True
        return False

    for modo in a.modos:
        ps.load_state(base)
        rec.passo((), 2)
        rec.ir(9800, -11500, 1600)
        rec.passo((), 20)
        rec.start()
        t.info(modo + ' pe da escada')
        rec.mark(modo)
        trechos = [('patamar', ['RIGHT'], lambda x, y, z: x > 12400),
                   ('patamar norte', ['UP'], lambda x, y, z: z < -12450),
                   ('topo', ['LEFT'], lambda x, y, z: x < 8600),
                   ('deque', ['UP'], lambda x, y, z: z < -16000)]
        ok = True
        for nome, b, cond in trechos:
            chegou = ate(b, cond, modo)
            x = t.info('%s %s chegou=%s' % (modo, nome, chegou))
            ok = ok and chegou
        # parado 10 s: o jogo continua andando? o Crash responde?
        t0 = ps.u32(S['GV_Time'])
        rec.passo((), 300)
        t1 = ps.u32(S['GV_Time'])
        p0 = rec.onde()
        rec.passo(['DOWN'], 30)
        p1 = rec.onde()
        travou = t1 == t0 or p0 == p1
        x = t.info('%s fim travou=%s' % (modo, travou))
        rec.foto(os.path.join(a.saida, modo + '.png'))
        rec.stop()
        rec.sheet(os.path.join(a.saida, modo + '_folha.png'), cada=30, colunas=10)
        ps.save_state(os.path.join(a.saida, modo + '_fim.state'))
        rec.save('%s_%s' % (a.nome, modo), descricao='escadaria do Heliporto, subindo %s' % modo)
        resultado[modo] = dict(chegou=ok, travou=travou, ultimo=x)
    json.dump(resultado, open(os.path.join(a.saida, 'resultado.json'), 'w'), indent=1)
    print(json.dumps(resultado))


if __name__ == '__main__':
    main()
