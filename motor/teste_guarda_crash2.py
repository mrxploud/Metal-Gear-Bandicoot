"""O guarda do Loading Dock vê o Crash 2 (jogador 2), grita "WOAH!" e atira nele, gravando o clipe.

    motor/.venv/Scripts/python.exe -I motor/teste_guarda_crash2.py [--estado X.state] [--nome guarda_ve_crash2]

Liga o disco de trabalho (motor/out/dev) e entra no Dock pelo seletor partindo do boot (um estado salvo antes da
compilação guarda o código antigo). Aperta START no controle 2, observa os guardas por 2 s e escolhe um que anda no
mesmo andar; põe o Crash 2 no caminho dele, alguns passos à frente, e o Crash 1 onde o guarda estava (atrás dele).
Depois só espera, gravando: o guarda tem de escolher o Crash 2 (crash_guarda_alvo), gritar o "WOAH!"
(crash2_dbg_woah), tocar o alerta e acertar o Crash 2 (crash2_dbg_vida cai) até ele cair (ou --segundos).
Saída em motor/out/guarda_crash2/ (estados, fotos, folha, log.json) e o clipe no clips/ do projeto mgb-expansao.
"""
import argparse
import json
import math
import os
import sys

MOTOR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, MOTOR)
from teste_coop import Coop, FUSAO  # noqa: E402

# WatcherWork (source/enemy/enemy.h): o CONTROL fica em +0x20
W_INDICE, W_FACEDIR, W_ANGULO, W_LONGE, W_VE = 0xB78, 0xB8C, 0xB8E, 0xB90, 0xB92


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--disco', default=os.path.join(MOTOR, 'out', 'dev', 'mgb.cue'))
    ap.add_argument('--mapa', default=os.path.join(FUSAO, 'repos', 'mgs_reversing', 'obj_dev', 'asm.map'))
    ap.add_argument('--estado', help='começa de um estado salvo no Dock (do mesmo disco e compilação)')
    ap.add_argument('--saida', default=os.path.join(MOTOR, 'out', 'guarda_crash2'))
    ap.add_argument('--nome', default='guarda_ve_crash2')
    ap.add_argument('--segundos', type=int, default=30)
    ap.add_argument('--inverso', action='store_true',
                    help='o Crash 1 na frente do guarda e o Crash 2 atrás: o guarda tem de ver e atirar no Crash 1')
    a = ap.parse_args()
    t = Coop(a.disco, a.mapa, a.saida)
    rec, ps, S = t.rec, t.ps, t.S
    if a.estado:
        ps.load_state(a.estado)
        rec.passo((), 2)
    else:
        if not t.fase(2):
            print('FALHOU: o Dock não carregou')
            return 1
        ps.save_state(os.path.join(a.saida, 'dock.state'))
    if not t.entra2():
        print('FALHOU: o Crash 2 não entrou')
        return 1
    ps.save_state(os.path.join(a.saida, 'coop_dock.state'))

    def guardas():
        n = ps.u32(S['GM_N_WhereList'])
        meus = {ps.u32(S['GM_PlayerControl']), ps.u32(S['crash2_control'])}
        out = {}
        for i in range(1, min(n, 96)):
            c = ps.u32(S['GM_WhereList'] + 4 * i)
            if 0x80000000 <= c < 0x80200000 and c not in meus:
                w = c - 0x20
                out[c] = dict(pos=[ps.s16(c + k) for k in (0, 2, 4)], indice=(ps.u8(w + W_INDICE) ^ 0x80) - 0x80,
                              olha=ps.s16(w + W_FACEDIR) & 0xFFF, angulo=ps.s16(w + W_ANGULO),
                              longe=ps.s16(w + W_LONGE), ve=ps.s16(w + W_VE))
        return out

    g0 = guardas()
    rec.passo((), 60)
    g1 = guardas()
    p1 = rec.onde()
    print('crash 1', p1, 'guardas', json.dumps({hex(c): g for c, g in g1.items()}), flush=True)
    cand = []
    for c, g in g1.items():
        if c not in g0 or not 0 <= g['indice'] < 8:
            continue
        a0, b = g0[c]['pos'], g['pos']
        vx, vz = (b[0] - a0[0]) / 30.0, (b[2] - a0[2]) / 30.0   # por quadro do jogo (60 vsync = 30 quadros)
        cand.append((abs(b[1] - p1[1]) > 1500, -math.hypot(vx, vz), c, a0, b, vx, vz))
    if not cand:
        print('FALHOU: nenhum guarda no Dock')
        return 1
    cand.sort()   # no mesmo andar do Crash 1 primeiro; entre eles, o que anda mais
    _, _, c, atras, agora, vx, vz = cand[0]
    g = g1[c]
    # pela direção em que ele olha (GV_VecDir2: x = sen, z = cos), na linha da patrulha: 2,2 m à frente e atrás.
    # (Até o teste 13 era "onde ele estava há 2 s" para trás e a velocidade para a frente; no teste 14, com o jogo a 30
    # quadros, o guarda já voltava na patrulha e o Crash 1 caiu em cima dele: guarda vê quem está a menos de 0,5 m.)
    d = g['olha'] * 2 * math.pi / 4096
    frente = (int(agora[0] + math.sin(d) * 2200), agora[1], int(agora[2] + math.cos(d) * 2200))
    atras = (int(agora[0] - math.sin(d) * 2200), agora[1], int(agora[2] - math.cos(d) * 2200))
    lugar1, lugar2 = (frente, atras) if a.inverso else (atras, frente)
    print('guarda', hex(c), g, 'crash 1 em', lugar1, 'crash 2 em', lugar2, flush=True)

    rec.ir(int(lugar1[0]), int(lugar1[2]), int(lugar1[1]))
    c2 = ps.u32(S['crash2_control'])
    ps.w16(c2, int(lugar2[0]))
    ps.w16(c2 + 2, int(lugar2[1]))
    ps.w16(c2 + 4, int(lugar2[2]))
    rec.passo((), 4)
    ps.save_state(os.path.join(a.saida, 'antes.state'))

    log = []
    vida_ini = ps.s32(S['crash2_dbg_vida'])
    woah_ini = ps.s32(S['crash2_dbg_woah'])
    woah1_ini = ps.s32(S['crash_dbg_woah'])

    def amostra(rot):
        gs = guardas()
        x = t.info(rot)
        x.update(guarda=gs.get(c), alvo=[ps.u8(S['crash_guarda_alvo'] + i) for i in range(8)],
                 woah2=ps.s32(S['crash2_dbg_woah']) - woah_ini, woah=ps.s32(S['crash_dbg_woah']) - woah1_ini,
                 alerta=ps.s32(S['GM_AlertMode']), nivel=ps.s32(S['GM_AlertLevel']))
        log.append(x)
        print(json.dumps({k: x[k] for k in ('rot', 'p1', 'p2', 'vida2', 'st', 'alvo', 'woah', 'woah2', 'alerta',
                                            'guarda')}), flush=True)
        return x

    def crash1_ferido(x):
        return int(x['st'], 16) & 0x800100 != 0   # PLAYER_DAMAGED ou a invencibilidade depois do golpe

    rec.start()
    rec.mark('o Crash 1 na frente do guarda, o Crash 2 atrás' if a.inverso else
             'o Crash 2 na frente do guarda, o Crash 1 atrás')
    amostra('inicio')
    viu = acertou = morreu = voltou = None
    vida_morto = []   # vida do Crash 2 enquanto morto: não pode cair (o corpo não segura bala)
    for meio in range(a.segundos * 2):
        rec.passo((), 30)
        x = amostra('t%02d' % meio)
        if a.inverso:
            # o de sempre: o guarda vê o Crash 1 (o "WOAH!" conta no crash_dbg_woah) e atira nele
            if viu is None and x['woah'] > 0:
                viu = meio
                rec.mark('WOAH! (o guarda viu o Crash 1)')
                rec.foto(os.path.join(a.saida, 'woah_inverso.png'))
            if acertou is None and crash1_ferido(x):
                acertou = meio
                rec.mark('o tiro acertou o Crash 1')
                rec.foto(os.path.join(a.saida, 'tiro_inverso.png'))
            if acertou is not None and meio - acertou >= 6:
                break
            continue
        if viu is None and x['woah2'] > 0:
            viu = meio
            rec.mark('WOAH! (o guarda viu o Crash 2)')
            rec.foto(os.path.join(a.saida, 'woah.png'))
        if acertou is None and x['vida2'] is not None and x['vida2'] < vida_ini:
            acertou = meio
            rec.mark('o tiro acertou o Crash 2')
            rec.foto(os.path.join(a.saida, 'tiro.png'))
        if morreu is None and x['vida2'] is not None and x['vida2'] <= 0:
            morreu = meio
            rec.mark('o Crash 2 cai')
        if morreu is not None and voltou is None:
            vida_morto.append(x['vida2'])
        if voltou is None and morreu is not None and x['vida2'] == vida_ini:
            voltou = meio
            rec.mark('o Crash 2 volta para perto do Crash 1')
        if morreu is not None and (meio - morreu >= 14 or voltou is not None and meio - voltou >= 3):
            break   # a morte (vem do CD) e a volta (90 quadros do jogo; com a tela dividida, ~4,5 s)
    rec.stop()
    suf = '_inverso' if a.inverso else ''
    rec.foto(os.path.join(a.saida, 'fim%s.png' % suf))
    rec.sheet(os.path.join(a.saida, 'folha%s.png' % suf), cada=15, colunas=10)
    ps.save_state(os.path.join(a.saida, 'fim%s.state' % suf))
    resultado = dict(guarda=hex(c), viu_em_s=None if viu is None else (viu + 1) / 2,
                     acertou_em_s=None if acertou is None else (acertou + 1) / 2,
                     caiu_em_s=None if morreu is None else (morreu + 1) / 2,
                     voltou_em_s=None if voltou is None else (voltou + 1) / 2, vida_morto=sorted(set(vida_morto)),
                     crash1_ferido_em_s=next(((i + 1) / 2 for i, x in enumerate(log[1:]) if crash1_ferido(x)), None),
                     # (sem a amostra 'inicio': 2 quadros depois do teletransporte o guarda ainda não pensou)
                     guarda_procurou_crash2=any(x['alvo'][g['indice']] for x in log[1:]),
                     vida2=[vida_ini, log[-1]['vida2']], woah=log[-1]['woah'], woah2=log[-1]['woah2'],
                     alerta=log[-1]['alerta'])
    print('RESULTADO', json.dumps(resultado), flush=True)
    json.dump(dict(resultado=resultado, log=log),
              open(os.path.join(a.saida, 'log_inverso.json' if a.inverso else 'log.json'), 'w'), indent=0)
    rec.save(a.nome, descricao=('Com o Crash 2 atrás, o guarda do Loading Dock vê o Crash 1 e atira nele, como antes'
                                if a.inverso else 'O guarda do Loading Dock vê o Crash 2, grita WOAH! e atira nele')
             + ' (motor/teste_guarda_crash2.py)')
    return 0 if viu is not None and acertou is not None else 2


if __name__ == '__main__':
    sys.exit(main())
