"""Teste da TNT nova, gravando no projeto do vídeo.

    motor/.venv/Scripts/python.exe -I motor/teste_tnt.py [--estado motor/out/coop/fase.state]

1) "deixa": o Crash veste a caixa C (TNT) ao lado de um guarda, aperta X (sai pulando), a TNT conta 3, 2, 1 e explode
   (o guarda deve cair; o Crash, longe, não);
2) "gira": o Crash veste a TNT e gira dentro dela (bolinha): explode na hora com ele junto (morte "sobram os olhos e
   os tênis", lida do CD);
3) "crash2": o Crash 2 parado perto de uma TNT deixada pelo Crash: leva o dano (e morre se estiver no meio).
Os guardas vêm da lista de quem está na fase (GM_WhereList; a posição 0 é o Snake).
"""
import argparse
import json
import os
import sys

MOTOR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, MOTOR)
from teste_coop import Coop, FUSAO  # noqa: E402

IT_BOX3 = 4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--disco', default=os.path.join(MOTOR, 'out', 'dev', 'mgb.cue'))
    ap.add_argument('--mapa', default=os.path.join(FUSAO, 'repos', 'mgs_reversing', 'obj_dev', 'asm.map'))
    ap.add_argument('--estado', default=os.path.join(MOTOR, 'out', 'coop', 'fase.state'))
    ap.add_argument('--saida', default=os.path.join(MOTOR, 'out', 'tnt'))
    ap.add_argument('--casos', nargs='*', default=['deixa', 'gira', 'crash2'])
    a = ap.parse_args()
    t = Coop(a.disco, a.mapa, a.saida)
    rec, ps, S = t.rec, t.ps, t.S
    ps.load_state(a.estado)
    rec.passo((), 2)
    base = ps.save_state()

    def guardas():
        n = ps.u32(S['GM_N_WhereList'])
        out = []
        for i in range(1, min(n, 96)):
            c = ps.u32(S['GM_WhereList'] + 4 * i)
            if 0x80000000 <= c < 0x80200000:
                out.append((c, [ps.s16(c + k) for k in (0, 2, 4)]))
        return out

    def veste_tnt():
        ps.w16(S['linkvarbuf'] + (37 + IT_BOX3) * 2, 1)
        ps.w16(S['linkvarbuf'] + 15 * 2, IT_BOX3)
        rec.passo((), 20)

    res = {}
    for caso in a.casos:
        ps.load_state(base)
        rec.passo((), 2)
        gs = guardas()
        print('guardas', gs, flush=True)
        rec.start()
        t.info(caso + ' inicio')
        if caso == 'deixa' and gs:
            c, (gx, gy, gz) = gs[0]
            rec.ir(gx + 900, gz, gy)       # ao lado do guarda
            rec.passo((), 4)
            veste_tnt()
            rec.mark('veste a TNT ao lado do guarda')
            t.info('vestiu')
            rec.passo(['CROSS'], 4)
            rec.mark('X: sai pulando, a TNT fica contando')
            rec.passo(['RIGHT'], 50)
            rec.passo(['RIGHT', 'CROSS'], 10)
            rec.passo(['RIGHT'], 40)
            for i in range(8):
                rec.passo((), 15)
                t.info('contando %d' % i)
        elif caso == 'gira':
            veste_tnt()
            rec.mark('veste a TNT')
            t.info('vestiu')
            rec.passo(['CIRCLE'], 4)
            rec.mark('gira dentro da TNT: bum')
            for i in range(16):
                rec.passo((), 20)
                t.info('depois %d' % i)
        elif caso == 'crash2':
            rec.passo((), 2, botoes2=['START'])
            rec.passo((), 20)
            veste_tnt()
            rec.mark('Crash 2 ao lado, o Crash veste a TNT')
            rec.passo(['CROSS'], 4)
            rec.passo(['DOWN'], 60)
            rec.mark('o Crash 2 fica perto da TNT')
            for i in range(10):
                rec.passo((), 15)
                t.info('contando %d' % i)
        x = t.info(caso + ' fim')
        rec.foto(os.path.join(a.saida, caso + '.png'))
        rec.stop()
        rec.sheet(os.path.join(a.saida, caso + '_folha.png'), cada=12, colunas=10)
        rec.save('tnt_' + caso, descricao='TNT: ' + caso)
        res[caso] = dict(fim=x, guardas_depois=guardas())
    json.dump(res, open(os.path.join(a.saida, 'resultado.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
