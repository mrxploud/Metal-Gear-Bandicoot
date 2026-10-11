"""Teste do pulo no robô (pedido do ByteMirage depois do teste 8): X pula, X no ar = pulo duplo, correndo + X,
derrapada + X = pulo longo, giro no ar, e o agachar de segurar (R1 solto levanta). Mede, quadro a quadro, a altura
dos pés (crash_no_ar), a animação do Crash e a posição do Snake, e monta uma folha de fotos.

    python -I motor/teste_pulo.py --estado motor/out/<teste>/dock.state [--nome pulo]
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw

MOTOR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(MOTOR, 'harness'))
sys.path.insert(0, MOTOR)
from psx import PSX  # noqa: E402
from teste_dock import simbolos  # noqa: E402

NOMES = {}


def nomes_anims():
    h = os.path.join(os.path.dirname(MOTOR), 'repos', 'mgs_reversing', 'source', 'crash', 'crash_data.h')
    for linha in open(h, encoding='ascii'):
        p = linha.split()
        if len(p) == 3 and p[0] == '#define' and p[1].startswith('CRASH_A_'):
            NOMES[int(p[2])] = p[1][8:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--estado', required=True)
    ap.add_argument('--disco', default=os.path.join(MOTOR, 'out', 'dev', 'mgb.cue'))
    ap.add_argument('--nome', default='pulo')
    a = ap.parse_args()
    nomes_anims()
    pasta = os.path.join(MOTOR, 'out', a.nome)
    os.makedirs(pasta, exist_ok=True)
    sym = simbolos()
    ps = PSX(a.disco)
    fotos = []

    def ctrl():
        return ps.u32(sym['GM_PlayerControl'])

    def estado():
        c = ctrl()
        return {'x': ps.s16(c), 'y': ps.s16(c + 2), 'z': ps.s16(c + 4), 'ar': ps.s32(sym['crash_no_ar']),
                'anim': NOMES.get(ps.s32(sym['crash_dbg_anim']), '?'), 'q': ps.s32(sym['crash_dbg_frame']),
                'acao': ps.s32(sym['crash_dbg_action'])}

    def foto(legenda):
        im = Image.fromarray(ps.image())
        d = ImageDraw.Draw(im)
        d.text((4, 4), legenda, fill=(255, 255, 0))
        fotos.append(im)

    def comeca(titulo, aberto=True):
        ps.load_state(a.estado)
        ps.run(10)
        if aberto:
            # corredor aberto do Dock, longe das paredes da saída da água e fora da vista dos guardas
            c = ctrl()
            ps.w16(c, -5750)
            ps.w16(c + 4, -8000)
        ps.run(40)
        print('\n==', titulo)

    def segue(n, botoes=(), fotos_em=(), legenda=''):
        """n quadros do jogo (2 vsyncs cada), imprimindo o estado; devolve a maior altura"""
        maior = 0
        for i in range(n):
            ps.run(2, list(botoes(i)) if callable(botoes) else list(botoes))
            e = estado()
            maior = max(maior, e['ar'])
            print('  %2d  ar %5d  %-16s q %3d  acao %3d  pos (%6d, %6d, %6d)' % (i, e['ar'], e['anim'], e['q'], e['acao'],
                                                                                 e['x'], e['y'], e['z']))
            if i in fotos_em:
                foto('%s %d: %s ar %d' % (legenda, i, e['anim'], e['ar']))
        return maior

    comeca('pulo tocado (X por 1 quadro)')
    x0 = estado()
    h = segue(26, lambda i: ['CROSS'] if i == 0 else [], fotos_em=(2, 8, 14), legenda='toque')
    print('  altura maxima %d' % h)

    comeca('pulo segurado (X o tempo todo)')
    h = segue(30, ['CROSS'], fotos_em=(10,), legenda='segurado')
    print('  altura maxima %d' % h)

    comeca('pulo duplo (X, solta, X no quadro 9)')
    h = segue(40, lambda i: ['CROSS'] if i in (0, 1, 2, 3, 9, 10, 11, 12, 13, 14) else [],
              fotos_em=(11, 14, 18, 22), legenda='duplo')
    print('  altura maxima %d' % h)

    comeca('correndo + X (para cima o tempo todo)')
    segue(12, ['UP'])
    e0 = estado()
    h = segue(26, lambda i: ['UP', 'CROSS'] if i < 6 else ['UP'], fotos_em=(6,), legenda='correndo')
    e1 = estado()
    print('  altura maxima %d, andou %d em z' % (h, e1['z'] - e0['z']))

    comeca('derrapada (correr + R1) e X no meio = pulo longo')
    segue(12, ['UP'])
    e0 = estado()
    h = segue(34, lambda i: ['UP', 'R1'] if i in (0, 1) else (['UP', 'CROSS'] if 4 <= i < 10 else ['UP']),
              fotos_em=(3, 8), legenda='longo')
    e1 = estado()
    print('  altura maxima %d, andou %d em z' % (h, e1['z'] - e0['z']))

    comeca('giro no ar (X, bolinha no quadro 5)')
    segue(30, lambda i: ['CROSS'] if i < 3 else (['CIRCLE'] if i in (5, 6) else []), fotos_em=(8,), legenda='giro')

    comeca('agachar segurando o R1 e soltar')
    segue(14, ['R1'], fotos_em=(12,), legenda='R1')
    segue(10, [], fotos_em=(8,), legenda='soltou')

    comeca('engatinhar (R1 + cima) e soltar')
    segue(24, ['R1', 'UP'], fotos_em=(22,), legenda='engatinha')
    segue(24, [], fotos_em=(6, 22), legenda='soltou')

    comeca('derrapada sem pulo: solta tudo (antes ficava agachado)')
    segue(12, ['UP'])
    segue(30, lambda i: ['UP', 'R1'] if i in (0, 1) else [], fotos_em=(24,), legenda='derrapou')

    if fotos:
        colunas = 4
        linhas = (len(fotos) + colunas - 1) // colunas
        folha = Image.new('RGB', (320 * colunas, 240 * linhas))
        for i, f in enumerate(fotos):
            folha.paste(f.resize((320, 240)), ((i % colunas) * 320, (i // colunas) * 240))
        folha.save(os.path.join(pasta, 'pulo.png'))
        print('\nfolha em', os.path.join(pasta, 'pulo.png'))


if __name__ == '__main__':
    main()
