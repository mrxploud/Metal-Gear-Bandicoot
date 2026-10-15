"""Caça o Crash 2 atravessando parede: ele corre, pula e gira ao acaso enquanto o robô confere cada passo contra as
paredes do mapa (lidas da RAM: HZD do mapa do Crash 1, grupo atual, mais as paredes móveis como portas).

    motor/.venv/Scripts/python.exe -I motor/teste_paredes_crash2.py --estado <coop.state> [--disco ...] [--mapa ...]
        [--segundos 120] [--semente 1] [--nome paredes_heli]

Um cruzamento conta quando o passo de um quadro para o outro corta a linha de uma parede (no chão, x/z) que, na altura
do corpo dele (pés + 400), deveria segurar: a parede vai do chão até acima disso. Teleporte (volta para perto do
Crash 1, morte) não conta: passo maior que 1.500. Cada cruzamento vira uma marca no clipe (gravado no mgb-expansao) e
uma linha em <saida>/cruzamentos.json, com a parede, a posição, a altura e se ele estava no ar.
"""
import argparse
import json
import os
import random
import struct
import sys

MOTOR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, MOTOR)
from teste_coop import Coop, FUSAO  # noqa: E402

DIRECOES = [['UP'], ['DOWN'], ['LEFT'], ['RIGHT'], ['UP', 'LEFT'], ['UP', 'RIGHT'], ['DOWN', 'LEFT'], ['DOWN', 'RIGHT']]


def ok(a):
    return 0x80000000 <= a < 0x80200000


def ler_paredes(ps, mapa_ptr):
    """Paredes do grupo atual do HZD do mapa (HZD_SEG: p1 x,z,y,h e p2 x,z,y,h) e as paredes móveis (d_segs)."""
    hzd = ps.u32(mapa_ptr + 8)
    grp = ps.u32(hzd + 4)
    n = ps.s16(grp + 2)
    walls, flags = ps.u32(grp + 8), ps.u32(grp + 20)
    out = []
    raw = ps.read(walls, 16 * n)
    fl = ps.read(flags, n)
    for i in range(n):
        x1, z1, y1, h1, x2, z2, y2, h2 = struct.unpack_from('<8h', raw, 16 * i)
        out.append(dict(i=i, x1=x1, z1=z1, y1=y1, h1=h1, x2=x2, z2=z2, y2=y2, h2=h2, flag=fl[i], movel=False))
    nd, dsegs, dflag = ps.s16(hzd + 10), ps.u32(hzd + 32), ps.u32(hzd + 36)
    for i in range(max(0, min(nd, 64))):
        p = ps.u32(dsegs + 4 * i)
        if not ok(p):
            continue
        x1, z1, y1, h1, x2, z2, y2, h2 = struct.unpack('<8h', ps.read(p, 16))
        out.append(dict(i=1000 + i, x1=x1, z1=z1, y1=y1, h1=h1, x2=x2, z2=z2, y2=y2, h2=h2,
                        flag=ps.u8(dflag + i) if ok(dflag) else 0, movel=True))
    return out


def cruza(a, b, w):
    """O segmento a->b (x, z) corta a parede w?"""
    def lado(px, pz, qx, qz, rx, rz):
        return (qx - px) * (rz - pz) - (qz - pz) * (rx - px)
    d1 = lado(w['x1'], w['z1'], w['x2'], w['z2'], a[0], a[2])
    d2 = lado(w['x1'], w['z1'], w['x2'], w['z2'], b[0], b[2])
    d3 = lado(a[0], a[2], b[0], b[2], w['x1'], w['z1'])
    d4 = lado(a[0], a[2], b[0], b[2], w['x2'], w['z2'])
    return (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0) and d1 != 0 and d2 != 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--estado', required=True, help='estado salvo com o Crash 2 em jogo (do mesmo disco)')
    ap.add_argument('--disco', default=os.path.join(MOTOR, 'out', 'dev', 'mgb.cue'))
    ap.add_argument('--mapa', default=os.path.join(FUSAO, 'repos', 'mgs_reversing', 'obj_dev', 'asm.map'))
    ap.add_argument('--saida', default=os.path.join(MOTOR, 'out', 'paredes'))
    ap.add_argument('--segundos', type=int, default=120)
    ap.add_argument('--semente', type=int, default=1)
    ap.add_argument('--nome', default='paredes_crash2')
    ap.add_argument('--stealth', action='store_true')
    a = ap.parse_args()
    random.seed(a.semente)
    t = Coop(a.disco, a.mapa, a.saida)
    rec, ps, S = t.rec, t.ps, t.S
    ps.load_state(a.estado)
    rec.passo((), 2)
    if a.stealth:
        ps.w16(S['linkvarbuf'] + 47 * 2, 1)
        ps.w16(S['linkvarbuf'] + 15 * 2, 10)
    c1 = ps.u32(S['GM_PlayerControl'])
    c2 = ps.u32(S['crash2_control'])
    if not ok(c2):
        print('FALHOU: o estado não tem o Crash 2')
        return 1
    paredes = ler_paredes(ps, ps.u32(c1 + 0x2C))
    print('paredes', len(paredes), 'móveis', sum(w['movel'] for w in paredes), flush=True)
    rec.start()
    rec.mark('o Crash 2 corre, pula e gira ao acaso')
    cruzamentos, ant = [], None
    direcao, pulo = random.choice(DIRECOES), 0
    for q in range(a.segundos * 60):
        if q % 45 == 0:
            direcao = random.choice(DIRECOES)
        botoes2 = list(direcao)
        r = random.random()
        if r < 0.02:
            botoes2.append('CROSS')          # pula
            pulo = 18 if random.random() < 0.5 else 0
        elif pulo:
            pulo -= 1
            if pulo == 6:
                botoes2.append('CROSS')      # pulo duplo
        elif r < 0.025:
            botoes2.append('CIRCLE')
        rec.passo((), 1, botoes2=botoes2)
        if q % 600 == 599:
            # o Crash 1 vai atrás de vez em quando (a área inteira, não só onde ele está)
            rec.passo([random.choice(['UP', 'DOWN', 'LEFT', 'RIGHT'])], 40)
        c2 = ps.u32(S['crash2_control'])
        if not ok(c2):
            ant = None
            continue
        pos = [ps.s16(c2 + k) for k in (0, 2, 4)]
        if ant and pos != ant:
            passo = abs(pos[0] - ant[0]) + abs(pos[2] - ant[2])
            if passo < 1500:
                pes = min(pos[1], ant[1]) - 1100      # control.height do Crash 2
                for w in paredes:
                    if w['flag'] & 1:
                        continue                       # o Snake ignora (SEGMENT_ATR = HZD_SEG_NO_COLLIDE)
                    baixo = min(w['y1'], w['y2'])
                    topo = min(w['y1'] + w['h1'], w['y2'] + w['h2'])
                    if not (baixo <= pes + 400 <= topo):
                        continue
                    if cruza(ant, pos, w):
                        ev = dict(quadro=len(rec.video), de=ant, para=pos, pes=pes, parede=w,
                                  no_ar=ps.s32(S['crash2_pulando']) if 'crash2_pulando' in S else None,
                                  p1=[ps.s16(c1 + k) for k in (0, 2, 4)])
                        cruzamentos.append(ev)
                        rec.mark('ATRAVESSOU a parede %d' % w['i'])
                        print(json.dumps(ev), flush=True)
        ant = pos
    rec.stop()
    rec.sheet(os.path.join(a.saida, 'folha.png'), cada=60, colunas=12)
    ps.save_state(os.path.join(a.saida, 'fim.state'))
    json.dump(dict(cruzamentos=cruzamentos, paredes=len(paredes)), open(os.path.join(a.saida, 'cruzamentos.json'), 'w'),
              indent=1)
    print('RESULTADO', json.dumps(dict(cruzamentos=len(cruzamentos), segundos=a.segundos)), flush=True)
    rec.save(a.nome, descricao='O Crash 2 correndo e pulando ao acaso; marcas onde ele atravessa parede '
                               '(motor/teste_paredes_crash2.py)')
    return 0 if not cruzamentos else 2


if __name__ == '__main__':
    sys.exit(main())
