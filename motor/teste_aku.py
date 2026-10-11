"""Teste do Aku Aku no robô: acha as caixas do Aku Aku (as rações do Dock), fotografa, pega as três (1ª, 2ª
máscara, 3ª = invencível) e leva o Crash invencível até um guarda (toque da morte).

    python -I motor/teste_aku.py [--disco motor/out/dev/mgb.cue] [--nome aku]
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw

MOTOR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(MOTOR, 'harness'))
sys.path.insert(0, MOTOR)
from psx import PSX  # noqa: E402
from teste_dock import ligar_no_dock, simbolos  # noqa: E402

GUARDAS = [(-5750, -16250), (4600, -8500)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--disco', default=os.path.join(MOTOR, 'out', 'dev', 'mgb.cue'))
    ap.add_argument('--nome', default='aku')
    a = ap.parse_args()
    pasta = os.path.join(MOTOR, 'out', a.nome)
    os.makedirs(pasta, exist_ok=True)
    sym = simbolos()
    ps = PSX(a.disco)
    ligar_no_dock(ps)
    ps.run(60)

    ctrl = ps.u32(sym['GM_PlayerControl'])
    fotos = []

    def foto(legenda):
        im = Image.fromarray(ps.image())
        d = ImageDraw.Draw(im)
        d.text((4, 228), legenda, fill=(255, 255, 0))
        fotos.append(im)
        print('foto:', legenda)

    def ir(x, z, y=None):
        ps.w16(ctrl + 0, x)
        ps.w16(ctrl + 4, z)
        if y is not None:
            ps.w16(ctrl + 2, y)

    def estado():
        return 'mascaras %d, invencivel %d' % (ps.s32(sym['crash_aku']), ps.s32(sym['crash_aku_inv']))

    caixas = []
    for i in range(4):
        p = ps.u32(sym['crash_dbg_item'] + 4 * i)
        if p:
            t = [ps.s32(p + 20 + 4 * e) for e in range(3)]
            caixas.append(t)
    print('caixas do Aku Aku:', caixas, '| Snake em', [ps.s16(ctrl + 2 * e) for e in range(3)])

    for n, (cx, cy, cz) in enumerate(caixas[:3]):
        ir(cx + 1300, cz, cy + 1104)
        ps.run(40)
        foto('caixa %d em (%d, %d, %d) | %s' % (n + 1, cx, cy, cz, estado()))
        ir(cx, cz, cy + 1104)
        ps.run(30)
        ps.hold(['LEFT'], 6)
        ps.run(60)
        foto('pegou a %d | %s' % (n + 1, estado()))

    # invencível: leva até o guarda e espera encostar
    for gx, gz in GUARDAS:
        ir(gx + 900, gz)
        ps.run(10)
        for k in range(3):
            ps.hold(['LEFT'], 10)
            ps.run(10)
            foto('guarda (%d, %d) %d | %s' % (gx, gz, k, estado()))

    lado = 320
    folha = Image.new('RGB', (lado * 4, 240 * ((len(fotos) + 3) // 4)))
    for i, f in enumerate(fotos):
        folha.paste(f, ((i % 4) * lado, (i // 4) * 240))
    folha.save(os.path.join(pasta, 'folha.png'))
    print('folha:', os.path.join(pasta, 'folha.png'))


if __name__ == '__main__':
    main()
