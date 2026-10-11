"""Troca de disco: liga os dois discos por um .m3u, leva o jogo à tela de troca (fase "change") e troca.

    python -I motor/teste_troca_disco.py --m3u motor/out/dev/mgb.m3u

O MGS pede o disco 2 nessa tela; o robô abre a tampa, põe o outro disco, fecha e confere que o jogo segue
(o tempo anda e a fase muda). Fotos em motor/out/troca_disco/.
"""
import argparse
import json
import sys
from pathlib import Path

MOTOR = Path(__file__).resolve().parent
sys.path[:0] = [str(MOTOR / 'harness'), str(MOTOR)]
from psx import PSX  # noqa: E402
from teste_dock import pedir_seletor  # noqa: E402
from teste_fases import INTERPRETADA, MAPA, simbolos, str_code  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--m3u', default=str(MOTOR / 'out' / 'dev' / 'mgb.m3u'))
    ap.add_argument('--mapa', default=str(MAPA))
    ap.add_argument('--saida', default=str(MOTOR / 'out' / 'troca_disco'))
    ap.add_argument('--antes', type=int, default=20, help='segundos na tela de troca antes de trocar')
    ap.add_argument('--depois', type=int, default=60, help='segundos observados depois da troca')
    a = ap.parse_args()
    saida = Path(a.saida)
    saida.mkdir(parents=True, exist_ok=True)
    sym = simbolos(a.mapa)
    ps = PSX(str(Path(a.m3u).resolve()), INTERPRETADA)
    print('discos no .m3u:', ps.core.num_disks(), 'atual:', ps.core.disk_index())
    pedir_seletor(ps, sym)  # seletor de fases do modo de desenvolvimento, no lugar do título
    ps.run(1170)
    ps.write(sym['GM_CurrentStageName'], b'change\0\0')
    ps.w16(sym['area_id'], str_code('change'))
    ps.w32(sym['GM_LoadRequest'], 1)
    log = []

    def amostra(rotulo):
        info = {'rotulo': rotulo, 'fase': ps.cstr(sym['GM_CurrentStageName'], 8), 'tempo': ps.u32(sym['GV_Time']),
                'disco': ps.core.disk_index()}
        log.append(info)
        ps.shot(str(saida / (rotulo + '.png')), scale=1)
        print(json.dumps(info), flush=True)
        return info

    for s in range(a.antes):
        ps.run(60)
        amostra('antes_%02d' % s)
    outro = 1 - ps.core.disk_index()
    ps.core.set_tray_open(True)
    ps.run(90)
    amostra('tampa_aberta')
    ps.core.insert_disk(outro)
    ps.run(30)
    ps.core.set_tray_open(False)
    for s in range(a.depois):
        ps.run(60)
        info = amostra('depois_%02d' % s)
        if s % 5 == 1:
            ps.press(['START'], 2, 4)  # "coloque o disco 2 e aperte START"
    (saida / 'amostras.json').write_text(json.dumps(log, indent=1), encoding='utf-8')
    fases = []
    for i in log:
        if not fases or fases[-1] != i['fase']:
            fases.append(i['fase'])
    andou = log[-1]['tempo'] != log[-6]['tempo']
    print('fases:', ' > '.join(fases), '| disco no fim:', log[-1]['disco'], '| tempo andando:', andou)
    return 0 if andou and len(fases) > 1 else 1


if __name__ == '__main__':
    raise SystemExit(main())
