"""A abertura de um Novo Jogo assistida inteira, sem pular nada (como um jogador vendo pela primeira vez).

    python -I motor/teste_abertura.py --disco motor/out/dev/mgb.cue [--mapa ...] [--saida motor/out/abertura]

Título -> Start -> Novo Jogo -> dificuldade; daí em diante nenhum botão até o personagem ter o controle no Loading
Dock (ou o jogo parar). Grava o tempo do jogo, a fase e uma foto a cada 5 s. Sai com 0 se chegou ao Dock.
"""
import argparse
import json
import sys
from pathlib import Path

MOTOR = Path(__file__).resolve().parent
sys.path[:0] = [str(MOTOR / 'harness'), str(MOTOR)]
from psx import PSX  # noqa: E402
from teste_fases import INTERPRETADA, MAPA, simbolos  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--disco', default=str(MOTOR / 'out' / 'dev' / 'mgb.cue'))
    ap.add_argument('--mapa', default=str(MAPA))
    ap.add_argument('--saida', default=str(MOTOR / 'out' / 'abertura'))
    ap.add_argument('--minutos', type=float, default=12)
    ap.add_argument('--apertar', nargs='*', default=[],
                    help='botões apertados de vez em quando durante a abertura (como alguém tentando pular a cena)')
    ap.add_argument('--tempo-real', action='store_true', help='roda a 60 quadros por segundo de relógio, como o jogar.py')
    ap.add_argument('--opcao', nargs='*', default=[], help='opções extras do núcleo, nome=valor')
    ap.add_argument('--start-em', type=float, help='aperta Start uma vez, N segundos depois de a abertura começar')
    ap.add_argument('--esperar-titulo', type=int, default=0,
                    help='segundos parado na tela de título antes do Start (o MGS passa a demonstração sozinho)')
    a = ap.parse_args()
    saida = Path(a.saida)
    saida.mkdir(parents=True, exist_ok=True)
    sym = simbolos(a.mapa)
    opcoes = dict(INTERPRETADA, pcsx_rearmed_memcard1='shared')
    opcoes.update(dict(x.split('=', 1) for x in a.opcao))
    ps = PSX(str(Path(a.disco).resolve()), opcoes, saves=str(saida / 'saves'))
    if a.tempo_real:
        import time
        rodar = ps.run

        def ps_run(quadros=1, botoes=()):
            for _ in range(quadros):
                rodar(1, botoes)
                ps.prox = getattr(ps, 'prox', time.perf_counter()) + 1 / 59.94
                espera = ps.prox - time.perf_counter()
                if espera > 0:
                    time.sleep(espera)
                else:
                    ps.prox = time.perf_counter()
        ps.run = ps_run
    log = (saida / 'amostras.jsonl').open('w', encoding='utf-8', buffering=1)

    def amostra(rotulo, foto=False):
        ctl = ps.u32(sym['GM_PlayerControl'])
        info = {'rotulo': rotulo, 'quadro': ps.frame, 'fase': ps.cstr(sym['GM_CurrentStageName'], 8),
                'tempo': ps.u32(sym['GV_Time']), 'status': '%08X' % ps.u32(sym['GM_GameStatus']),
                'pausa': ps.u32(sym['GV_PauseLevel']), 'controle': 0x80000000 <= ctl < 0x80200000}
        log.write(json.dumps(info) + '\n')
        if foto:
            ps.shot(str(saida / (rotulo + '.png')), scale=1)
        return info

    if a.esperar_titulo:
        ps.run(60 * a.esperar_titulo)
        amostra('depois_de_esperar', True)
    # Até a abertura começar: Start no título, bolinha no menu e na dificuldade.
    for s in range(120):
        ps.run(60)
        info = amostra('menu_%03d' % s, s % 5 == 0)
        if info['fase'] not in ('title', 'opening', ''):
            break
        if info['fase'] == 'title':
            ps.press(['START'] if s % 2 == 0 else ['CIRCLE'], 2, 4)
    print('começou:', info['fase'], 'no segundo', s, flush=True)
    parado = 0
    ultimo = None
    for s in range(int(a.minutos * 60)):
        if a.apertar and s % 3 == 0:
            ps.press([a.apertar[(s // 3) % len(a.apertar)]], 4, 4)
        if a.start_em is not None and int(a.start_em) == s:
            ps.run(int((a.start_em - s) * 60))
            ps.press(['START'], 4, 4)
            amostra('start_apertado', True)
        ps.run(60)
        info = amostra('t%04d' % s, s % 5 == 0)
        parado = parado + 1 if info['tempo'] == ultimo else 0
        ultimo = info['tempo']
        if info['fase'] == 's00a' and info['controle'] and info['pausa'] == 0:
            print('PASSOU: controle no Loading Dock aos %d s de abertura' % s, flush=True)
            ps.shot(str(saida / 'dock.png'), scale=1)
            return 0
        if parado >= 20:
            print('TRAVOU aos %d s: fase %s, tempo do jogo parado há 20 s, status %s' % (s, info['fase'], info['status']),
                  flush=True)
            ps.shot(str(saida / 'travou.png'), scale=1)
            ps.save_state(str(saida / 'travou.state'))
            return 1
    print('LIMITE sem chegar ao Dock: fase', info['fase'], flush=True)
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
