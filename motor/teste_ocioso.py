"""O jogo ligado e largado na tela de título: o MGS passa sozinho as demonstrações. Nenhum botão.

    python -I motor/teste_ocioso.py --disco motor/out/teste10/mgb.m3u --mapa motor/out/teste10/asm.map

Anota a cada 5 s a fase, o relógio do jogo e o status, e guarda uma foto quando a fase muda. Acusa travamento quando
a imagem não muda por 30 s seguidos (o relógio do jogo anda mesmo com uma demo parada esperando o CD).
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

MOTOR = Path(__file__).resolve().parent
sys.path[:0] = [str(MOTOR / 'harness'), str(MOTOR)]
from psx import PSX  # noqa: E402
from teste_fases import INTERPRETADA, simbolos  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--disco', default=str(MOTOR / 'out' / 'teste10' / 'mgb.m3u'))
    ap.add_argument('--mapa', default=str(MOTOR / 'out' / 'teste10' / 'asm.map'))
    ap.add_argument('--saida', default=str(MOTOR / 'out' / 'ocioso'))
    ap.add_argument('--minutos', type=float, default=12)
    a = ap.parse_args()
    saida = Path(a.saida)
    saida.mkdir(parents=True, exist_ok=True)
    sym = simbolos(a.mapa)
    ps = PSX(str(Path(a.disco).resolve()), dict(INTERPRETADA, pcsx_rearmed_memcard1='shared'), saves=str(saida / 'saves'))
    log = (saida / 'amostras.jsonl').open('w', encoding='utf-8', buffering=1)
    fase_antes, igual, img_antes = None, 0, None
    for s in range(0, int(a.minutos * 60), 5):
        ps.run(300)
        img = hashlib.sha1(ps.image().tobytes()).hexdigest()
        fase = ps.cstr(sym['GM_CurrentStageName'], 8)
        info = {'s': s, 'fase': fase, 'tempo': ps.u32(sym['GV_Time']), 'status': '%08X' % ps.u32(sym['GM_GameStatus'])}
        log.write(json.dumps(info) + '\n')
        if fase != fase_antes:
            print(json.dumps(info), flush=True)
            ps.shot(str(saida / ('%04d_%s.png' % (s, fase))), scale=1)
            fase_antes = fase
        igual = igual + 5 if img == img_antes else 0
        img_antes = img
        if igual >= 30:
            print('TRAVOU aos %d s: %s' % (s, json.dumps(info)), flush=True)
            ps.shot(str(saida / 'travou.png'), scale=1)
            ps.save_state(str(saida / 'travou.state'))
            return 1
    print('OK: %d minutos sem travar' % a.minutos, flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
