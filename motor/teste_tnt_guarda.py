"""TNT x guarda no Loading Dock, gravando: o Crash deixa a TNT onde um guarda vai passar e foge.

    motor/.venv/Scripts/python.exe -I motor/teste_tnt_guarda.py

Liga o disco de trabalho, entra no Dock pelo seletor, mede o passo de cada guarda por 2 s, escolhe o que anda mais
devagar (ou parado) e põe a TNT onde ele vai estar daqui a 3 s. Grava o clipe tnt_guarda_<n> e salva o estado.
"""
import json
import math
import os
import sys

MOTOR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, MOTOR)
from teste_coop import Coop, FUSAO  # noqa: E402

IT_BOX3 = 4


def main():
    saida = os.path.join(MOTOR, 'out', 'tnt_guarda')
    t = Coop(os.path.join(MOTOR, 'out', 'dev', 'mgb.cue'),
             os.path.join(FUSAO, 'repos', 'mgs_reversing', 'obj_dev', 'asm.map'), saida)
    rec, ps, S = t.rec, t.ps, t.S
    estado = os.path.join(saida, 'dock.state')
    if os.path.exists(estado):
        ps.load_state(estado)
        rec.passo((), 2)
    else:
        t.fase(2)
        ps.save_state(estado)
    ps.w16(S['linkvarbuf'] + 47 * 2, 1)   # stealth: o guarda não foge nem atira
    ps.w16(S['linkvarbuf'] + 15 * 2, 10)

    def guardas():
        n = ps.u32(S['GM_N_WhereList'])
        out = {}
        for i in range(1, min(n, 96)):
            c = ps.u32(S['GM_WhereList'] + 4 * i)
            if 0x80000000 <= c < 0x80200000:
                out[c] = [ps.s16(c + k) for k in (0, 2, 4)]
        return out

    g0 = guardas()
    rec.passo((), 60)
    g1 = guardas()
    p1 = rec.onde()
    cand = []
    for c, a in g0.items():
        if c not in g1:
            continue
        b = g1[c]
        vx, vz = (b[0] - a[0]) / 30.0, (b[2] - a[2]) / 30.0   # por quadro do jogo (60 vsync = 30 quadros)
        # onde ele vai estar quando a TNT explodir (3 s + o tempo de vestir e pular, ~1 s)
        alvo = (b[0] + vx * 120, b[1], b[2] + vz * 120)
        cand.append((math.hypot(vx, vz), c, b, alvo))
    cand.sort(key=lambda x: (abs(x[2][1] - p1[1]) > 1500, x[0]))   # no mesmo andar, os mais lentos
    print('guardas', [(hex(c), b, round(v, 1)) for v, c, b, _ in cand], flush=True)
    resultado = []
    base = ps.save_state()
    for n, (v, c, b, alvo) in enumerate(cand[:int(os.environ.get('GUARDAS', 3))]):
        ps.load_state(base)
        rec.passo((), 2)
        ps.w16(S['linkvarbuf'] + 47 * 2, 1)
        ps.w16(S['linkvarbuf'] + 15 * 2, 10)
        rec.ir(int(alvo[0]), int(alvo[2]), int(alvo[1]))
        rec.passo((), 6)
        rec.start()
        rec.mark('o Crash chega com a TNT')
        ps.w16(S['linkvarbuf'] + (37 + IT_BOX3) * 2, 1)
        ps.w16(S['linkvarbuf'] + 15 * 2, IT_BOX3)
        rec.passo((), 24)
        rec.mark('X: pula para fora, a TNT conta')
        rec.passo(['CROSS'], 4)
        # foge para longe do guarda
        gx, gz = b[0], b[2]
        x, _, z = rec.onde()
        dx, dz = x - gx, z - gz
        fuga = ['RIGHT' if dx > 0 else 'LEFT', 'DOWN' if dz > 0 else 'UP']
        rec.passo(fuga, 70)
        for i in range(18):
            rec.passo((), 15)
            t.info('guarda %d contando %d' % (n, i))
        depois = guardas()
        info = t.info('guarda %d fim' % n)
        rec.foto(os.path.join(saida, 'guarda_%d.png' % n))
        rec.stop()
        rec.sheet(os.path.join(saida, 'guarda_%d_folha.png' % n), cada=10, colunas=10)
        rec.save('tnt_guarda_%d' % n, descricao='TNT deixada no caminho de um guarda no Dock')
        resultado.append(dict(guarda=hex(c), antes=b, alvo=alvo, depois=depois.get(c), fim=info))
    json.dump(resultado, open(os.path.join(saida, 'resultado.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
