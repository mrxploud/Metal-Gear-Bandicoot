"""O Crash 2 e o cenário do Loading Dock: a água do tanque e os itens no chão (achados do ByteMirage no teste 14).

    motor/.venv/Scripts/python.exe -I motor/teste_crash2_cenario.py --estado <coop no Dock> [--disco ...] [--mapa ...]

(1) Água: o Crash 2 é posto em cima do tanque fundo do começo do Dock (onde, no teste 14, ele afundou até o fundo, a
    4 m, e ficou andando por baixo do cais). Tem de boiar: os pés no máximo 70 cm abaixo da superfície, não no fundo.
    Depois pula (X) para ver se sai da água.
(2) Item: o Crash 2 é posto em cima de cada item do Dock (as caixas do Aku Aku no lugar das rações); tem de pegar
    (o contador de máscaras crash_aku sobe, ou o item some da lista).
(3) Paredes: as que seguram o Snake e, até o teste 14, não seguravam o Crash 2 (seg_flag dele era 2, o do Snake é 1).
    O Crash 2 é empurrado contra cada uma, dos dois lados; não pode passar.
Grava o clipe no clips/ do mgb-expansao (classe Coop) e salva fotos em <saida>.
"""
import argparse
import json
import math
import os
import struct
import sys

MOTOR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, MOTOR)
from teste_coop import Coop, FUSAO  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--estado', required=True)
    ap.add_argument('--disco', default=os.path.join(MOTOR, 'out', 'dev', 'mgb.cue'))
    ap.add_argument('--mapa', default=os.path.join(FUSAO, 'repos', 'mgs_reversing', 'obj_dev', 'asm.map'))
    ap.add_argument('--saida', default=os.path.join(MOTOR, 'out', 'cenario'))
    ap.add_argument('--nome', default='crash2_agua_e_item')
    a = ap.parse_args()
    t = Coop(a.disco, a.mapa, a.saida)
    rec, ps, S = t.rec, t.ps, t.S
    ps.load_state(a.estado)
    rec.passo((), 2)
    ps.w16(S['linkvarbuf'] + 47 * 2, 1)       # stealth: os guardas não atrapalham
    ps.w16(S['linkvarbuf'] + 15 * 2, 10)
    c2 = ps.u32(S['crash2_control'])
    res = {}

    def pos2():
        c = ps.u32(S['crash2_control'])
        return [ps.s16(c + k) for k in (0, 2, 4)], ps.s16(c + 120)

    def poe(x, y, z):
        c = ps.u32(S['crash2_control'])
        ps.w16(c, x)
        ps.w16(c + 2, y)
        ps.w16(c + 4, z)

    base = ps.save_state()
    rec.start()
    # (1) a água: a caixa de água do Dock (wt_area) vai de x -15000 a 9625, z -8750 a 8750, superfície em -1400.
    # Procura um ponto de água funda (chão do tanque abaixo de -2500) pondo o Crash 2 com os pés na superfície.
    fundo = None
    for x in range(-14000, 9001, 1500):
        for z in range(-8000, 8001, 1500):
            ps.load_state(base)
            poe(x, -1400 + 1100, z)
            for _ in range(8):
                ps.run(1, [], [])
            p, chao = pos2()
            if chao < -2500:
                fundo = (x, z)
                break
        if fundo:
            break
    ps.load_state(base)
    rec.passo((), 2)
    res['ponto_fundo'] = fundo
    rec.mark('o Crash 2 cai no tanque fundo em %s' % (fundo,))
    poe(fundo[0], -1400 + 1100, fundo[1])
    ys = []
    for i in range(12):
        rec.passo((), 15)
        p, chao = pos2()
        ys.append(dict(t=round((i + 1) / 4, 2), pos=p, pes=p[1] - 1100, chao=chao))
    rec.foto(os.path.join(a.saida, 'agua.png'))
    rec.mark('X: pula para fora')
    rec.passo((), 4, botoes2=['CROSS'])
    rec.passo((), 20)
    p, chao = pos2()
    res['agua'] = dict(amostras=ys, depois_do_pulo=dict(pos=p, pes=p[1] - 1100), pes_min=min(y['pes'] for y in ys),
                       chao=ys[-1]['chao'])
    print(json.dumps(res['agua']), flush=True)

    # (2) os itens: os CONTROL da lista de onde-está que não são guardas nem os Crashes ficam a ~500 do chão
    n = ps.u32(S['GM_N_WhereList'])
    meus = {ps.u32(S['GM_PlayerControl']), ps.u32(S['crash2_control'])}
    itens = []
    for i in range(1, min(n, 96)):
        c = ps.u32(S['GM_WhereList'] + 4 * i)
        if 0x80000000 <= c < 0x80200000 and c not in meus:
            idx = ps.u8(c - 0x20 + 0xB78)
            p = [ps.s16(c + k) for k in (0, 2, 4)]
            if p[1] < 900 and idx not in range(8):   # guarda tem índice 0..7 e anda a ~1080 de altura
                itens.append((c, p))
    res['itens'] = []
    for c, p in itens:
        aku0 = ps.s32(S['crash_aku'])
        rec.mark('o Crash 2 em cima do item em %s' % p)
        c2 = ps.u32(S['crash2_control'])
        ps.w16(c2, p[0])
        ps.w16(c2 + 2, p[1] + 1100)
        ps.w16(c2 + 4, p[2])
        rec.passo((), 60)
        ainda = any(ps.u32(S['GM_WhereList'] + 4 * i) == c for i in range(1, min(ps.u32(S['GM_N_WhereList']), 96)))
        r = dict(item=p, aku_antes=aku0, aku_depois=ps.s32(S['crash_aku']), item_ainda_na_lista=ainda)
        res['itens'].append(r)
        print(json.dumps(r), flush=True)
    rec.foto(os.path.join(a.saida, 'item.png'))

    # (3) as paredes que seguram o Snake e, até o teste 14, não seguravam o Crash 2 (flag com o bit 2 e sem o bit 1:
    # o Crash 2 usava seg_flag 2, o Snake usa 1). O Crash 2 é empurrado contra cada uma, dos dois lados.
    ps.load_state(base)
    rec.passo((), 2)
    c1 = ps.u32(S['GM_PlayerControl'])
    hzd = ps.u32(ps.u32(c1 + 0x2C) + 8)
    grp = ps.u32(hzd + 4)
    n, walls, flags = ps.s16(grp + 2), ps.u32(grp + 8), ps.u32(grp + 20)
    raw, fl = ps.read(walls, 16 * n), ps.read(flags, n)
    alvo = []
    for i in range(n):
        x1, z1, y1, h1, x2, z2, y2, h2 = struct.unpack_from('<8h', raw, 16 * i)
        L = math.hypot(x2 - x1, z2 - z1)
        if (fl[i] & 2) and not (fl[i] & 1) and L >= 600:
            alvo.append(dict(i=i, x1=x1, z1=z1, x2=x2, z2=z2, baixo=min(y1, y2), topo=min(y1 + h1, y2 + h2),
                             L=L, flag=fl[i]))
    # o direcional do controle 2 é relativo à câmera: mede para onde cada direção leva no mundo
    ang = {}
    for d in ('UP', 'DOWN', 'LEFT', 'RIGHT'):
        ps.load_state(base)
        p0, _ = pos2()
        for _ in range(20):
            ps.run(1, [], [d])
        p1, _ = pos2()
        ang[d] = math.atan2(p1[0] - p0[0], p1[2] - p0[2])
    combos = {('UP',): ang['UP'], ('DOWN',): ang['DOWN'], ('LEFT',): ang['LEFT'], ('RIGHT',): ang['RIGHT']}
    for v, h_ in (('UP', 'LEFT'), ('UP', 'RIGHT'), ('DOWN', 'LEFT'), ('DOWN', 'RIGHT')):
        combos[(v, h_)] = math.atan2(math.sin(ang[v]) + math.sin(ang[h_]), math.cos(ang[v]) + math.cos(ang[h_]))

    def botao_para(theta):
        return list(min(combos, key=lambda k: abs(math.atan2(math.sin(combos[k] - theta),
                                                              math.cos(combos[k] - theta)))))

    def lado(w, p):
        return (w['x2'] - w['x1']) * (p[2] - w['z1']) - (w['z2'] - w['z1']) * (p[0] - w['x1'])

    res['paredes'] = []
    for w in alvo[:14]:
        mx, mz = (w['x1'] + w['x2']) / 2, (w['z1'] + w['z2']) / 2
        nx, nz = -(w['z2'] - w['z1']) / w['L'], (w['x2'] - w['x1']) / w['L']
        for s in (1, -1):
            ps.load_state(base)
            ini = (int(mx + nx * s * 700), int(mz + nz * s * 700))
            poe(ini[0], 4000, ini[1])
            for _ in range(40):
                ps.run(1, [], [])
            p0, chao = pos2()
            if not (w['baixo'] <= chao + 750 <= w['topo']) or abs(p0[0] - ini[0]) + abs(p0[2] - ini[1]) > 300:
                continue   # a parede não pega na altura dele ali, ou ele não ficou onde foi posto
            b = botao_para(math.atan2(-nx * s, -nz * s))
            for _ in range(60):
                ps.run(1, [], b)
            p1, _ = pos2()
            atravessou = (lado(w, p0) > 0) != (lado(w, p1) > 0)
            r = dict(parede=w['i'], flag=w['flag'], de=p0, para=p1, chao=chao, atravessou=atravessou)
            res['paredes'].append(r)
            print(json.dumps(r), flush=True)
    rec.stop()
    rec.sheet(os.path.join(a.saida, 'folha.png'), cada=15, colunas=10)
    json.dump(res, open(os.path.join(a.saida, 'resultado.json'), 'w'), indent=1)
    boiou = res['agua']['pes_min'] > -2500
    pegou = any(r['aku_depois'] != r['aku_antes'] or not r['item_ainda_na_lista'] for r in res['itens'])
    atravessou = sum(r['atravessou'] for r in res['paredes'])
    print('RESULTADO', json.dumps(dict(boiou=boiou, pes_min=res['agua']['pes_min'], pegou_item=pegou,
                                       itens=len(res['itens']), paredes_testadas=len(res['paredes']),
                                       paredes_atravessadas=atravessou)), flush=True)
    rec.save(a.nome, descricao='O Crash 2 no tanque do Dock e em cima dos itens (motor/teste_crash2_cenario.py)')
    return 0 if boiou and pegou and not atravessou else 2


if __name__ == '__main__':
    sys.exit(main())
