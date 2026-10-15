"""Teste 14: tela inteira com os dois Crashes juntos, divisão quando o Crash 2 sai da câmera, e sem a coleira de 12 m.

    motor/.venv/Scripts/python.exe -I motor/teste_coop14.py [--fase 5] [--nome coop14_heli] [--estado X.state]

Do boot (o estado salvo guarda o código antigo), entra na fase pelo seletor (5 = Heliporto, 2 = Loading Dock), o
Crash 2 entra pelo START do controle 2 e: (1) os dois parados juntos (a tela tem de ficar inteira), (2) o Crash 2 se
afasta numa direção até a parede (a tela tem de dividir; passar dos 12 m sem voltar), (3) volta até o Crash 1 (a tela
tem de juntar de novo). A cada meio segundo: posições, distância, quadros de jogo por segundo e se a tela estava
dividida (crash_dbg_tela anda só nos quadros divididos). Grava o clipe no clips/ do mgb-expansao (classe Coop).
"""
import argparse
import json
import math
import os
import sys

MOTOR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, MOTOR)
from teste_coop import Coop, FUSAO  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--disco', default=os.path.join(MOTOR, 'out', 'dev', 'mgb.cue'))
    ap.add_argument('--mapa', default=os.path.join(FUSAO, 'repos', 'mgs_reversing', 'obj_dev', 'asm.map'))
    ap.add_argument('--fase', type=int, default=5)
    ap.add_argument('--estado', help='começa de um estado salvo na fase (do mesmo disco e compilação)')
    ap.add_argument('--saida', default=os.path.join(MOTOR, 'out', 'coop14'))
    ap.add_argument('--nome', default='coop14_heli')
    ap.add_argument('--direcao', default='RIGHT', help='para onde o Crash 2 se afasta (RIGHT, LEFT, UP, DOWN)')
    ap.add_argument('--longe', type=int, default=14, help='segundos se afastando')
    ap.add_argument('--stealth', action='store_true', help='equipa o stealth (os guardas não veem ninguém)')
    ap.add_argument('--lugar', help='x,z,y: leva o Crash 1 para lá antes de o Crash 2 entrar (o começo do Dock é um '
                                    'corredor apertado: os dois sempre cabem na tela)')
    a = ap.parse_args()
    t = Coop(a.disco, a.mapa, a.saida)
    rec, ps, S = t.rec, t.ps, t.S
    if a.estado:
        ps.load_state(a.estado)
        rec.passo((), 2)
    else:
        if not t.fase(a.fase):
            print('FALHOU: a fase não carregou')
            return 1
        ps.save_state(os.path.join(a.saida, 'fase.state'))
    if a.stealth:
        # o item stealth equipado: os guardas não veem nenhum dos dois (no Dock, o alerta matava os dois no meio do
        # teste da tela)
        ps.w16(S['linkvarbuf'] + 47 * 2, 1)
        ps.w16(S['linkvarbuf'] + 15 * 2, 10)
    if a.lugar:
        rec.ir(*[int(v) for v in a.lugar.split(',')])
        rec.passo((), 30)
    volta = {'UP': 'DOWN', 'DOWN': 'UP', 'LEFT': 'RIGHT', 'RIGHT': 'LEFT'}[a.direcao]
    log = []

    def amostra(rot, b1=(), b2=(), vsyncs=30):
        t0, d0 = ps.u32(S['GV_Time']), ps.u32(S['crash_dbg_tela'])
        rec.passo(b1, vsyncs, botoes2=b2)
        t1, d1 = ps.u32(S['GV_Time']), ps.u32(S['crash_dbg_tela'])
        x = t.info(rot)
        p1, p2 = x['p1'], x['p2']
        x.update(qps=round((t1 - t0) * 60 / vsyncs, 1), dividida=d1 > d0,
                 dist=round(math.hypot(p2[0] - p1[0], p2[2] - p1[2])) if p1 and p2 else None)
        log.append(x)
        print(json.dumps({k: x[k] for k in ('rot', 'p1', 'p2', 'dist', 'dividida', 'qps', 'vida2')}), flush=True)
        return x

    rec.start()
    rec.mark('START no controle 2')
    if not t.entra2():
        print('FALHOU: o Crash 2 não entrou')
        return 1
    ps.save_state(os.path.join(a.saida, 'coop.state'))
    rec.foto(os.path.join(a.saida, 'juntos.png'))
    rec.mark('os dois juntos: tela inteira')
    for i in range(4):
        amostra('juntos %d' % i)
    rec.foto(os.path.join(a.saida, 'juntos_tela_inteira.png'))
    rec.mark('o Crash 2 se afasta')
    dividiu = None
    for i in range(a.longe * 2):
        x = amostra('afasta %d' % i, (), [a.direcao])
        if dividiu is None and x['dividida']:
            dividiu = x['dist']
            rec.mark('a tela divide (%d de distância)' % dividiu)
            rec.foto(os.path.join(a.saida, 'dividiu.png'))
    longe = max((x['dist'] or 0) for x in log)
    rec.foto(os.path.join(a.saida, 'longe.png'))
    ps.save_state(os.path.join(a.saida, 'longe.state'))
    rec.mark('o Crash 2 volta')
    juntou = None
    for i in range(a.longe * 2 + 10):
        x = amostra('volta %d' % i, (), [volta])
        if juntou is None and not x['dividida']:
            juntou = x['dist']
            rec.mark('a tela junta de novo (%d de distância)' % juntou)
            rec.foto(os.path.join(a.saida, 'juntou.png'))
            for k in range(3):
                amostra('junto de novo %d' % k)
            break
    rec.stop()
    rec.sheet(os.path.join(a.saida, 'folha.png'), cada=20, colunas=10)
    ps.save_state(os.path.join(a.saida, 'fim.state'))
    juntos = [x for x in log if x['rot'].startswith('juntos')]
    divididos = [x for x in log if x['dividida']]
    afasta = [x['dist'] for x in log if x['rot'].startswith('afasta') and x['dist'] is not None]
    # a coleira trazia o Crash 2 de volta: a distância despencava enquanto ele se afastava
    puxado = any(b < a_ - 3000 for a_, b in zip(afasta, afasta[1:]))
    resultado = dict(
        fase=log[0]['fase'],
        juntos_tela_inteira=all(not x['dividida'] for x in juntos),
        juntos_qps=min(x['qps'] for x in juntos),
        dividiu_a=dividiu, juntou_a=juntou, mais_longe=longe,
        divididos_qps=min((x['qps'] for x in divididos), default=None),
        puxado_de_volta=puxado)
    print('RESULTADO', json.dumps(resultado), flush=True)
    json.dump(dict(resultado=resultado, log=log), open(os.path.join(a.saida, 'log.json'), 'w'), indent=0)
    rec.save(a.nome, descricao='Teste 14: tela inteira com os dois juntos, divide quando o Crash 2 se afasta, sem a '
                               'coleira de 12 m (motor/teste_coop14.py)')
    ok = resultado['juntos_tela_inteira'] and dividiu is not None and juntou is not None
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
