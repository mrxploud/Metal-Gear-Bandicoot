"""Salvar no cartão de memória: Novo Jogo, Loading Dock, rádio para a Mei Ling (140.96) e salvar.

    python -I motor/teste_salvar.py --disco motor/out/dev/mgb.m3u

O cartão fica num arquivo do próprio núcleo (pcsx_rearmed_memcard1 = shared): o teste usa uma pasta de saves
própria, começa com o cartão vazio e confere que apareceu um save do MGS no diretório do cartão.
Fotos em motor/out/salvar/.
"""
import argparse
import shutil
import sys
from pathlib import Path

MOTOR = Path(__file__).resolve().parent
sys.path[:0] = [str(MOTOR / 'harness'), str(MOTOR)]
import psx  # noqa: E402
from teste_fases import INTERPRETADA, MAPA, simbolos  # noqa: E402


def saves_no_cartao(cartao):
    """Nomes dos saves no diretório do cartão (blocos 1-15 em uso como primeiro bloco: 0x51)."""
    if not cartao.exists():
        return []
    d = cartao.read_bytes()
    return [d[i * 128 + 10:i * 128 + 30].split(bytes(1))[0].decode('ascii', 'replace')
            for i in range(1, 16) if d[i * 128] == 0x51]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--disco', default=str(MOTOR / 'out' / 'dev' / 'mgb.m3u'))
    ap.add_argument('--saida', default=str(MOTOR / 'out' / 'salvar'))
    ap.add_argument('--mapa', default=str(MAPA), help='mapa do executável do disco (o original: obj/asm.map)')
    a = ap.parse_args()
    saida = Path(a.saida)
    shutil.rmtree(saida, ignore_errors=True)
    saves = saida / 'saves'
    saves.mkdir(parents=True)
    sym = simbolos(a.mapa)
    # O núcleo grava o cartão compartilhado na pasta de saves do frontend: aqui, uma pasta só do teste.
    ps = psx.PSX(str(Path(a.disco).resolve()), dict(INTERPRETADA, pcsx_rearmed_memcard1='shared'), saves=str(saves))
    cartao = saves / 'pcsx-card1.mcd'

    def foto(nome):
        ps.shot(str(saida / (nome + '.png')), scale=1)

    # Título -> Novo Jogo -> dificuldade -> abertura -> Dock (START e bolinha de vez em quando).
    for s in range(120):
        ps.run(60)
        fase = ps.cstr(sym['GM_CurrentStageName'], 8)
        ctl = ps.u32(sym['GM_PlayerControl'])
        if fase == 's00a' and 0x80000000 <= ctl < 0x80200000:
            break
        ps.press(['START'] if s % 2 == 0 else ['CIRCLE'], 2, 4)
    else:
        print('não chegou ao Dock')
        return 1
    foto('dock')
    # A primeira ligação do Campbell (ela apresenta a Mei Ling): espera começar, avança o texto com bolinha
    # e espera o rádio fechar de vez.
    for s in range(120):
        ps.run(30)
        if ps.u32(sym['GV_PauseLevel']):
            break
    foto('campbell')
    livre = 0
    for s in range(1200):
        if ps.u32(sym['GV_PauseLevel']) == 0:
            livre += 1
            if livre >= 6:
                break
            ps.run(30)
            continue
        livre = 0
        ps.press(['CIRCLE'], 2, 12)
        ps.run(16)
    foto('dock_livre')
    ps.run(60)
    # Rádio: SELECT abre; a frequência começa em 140.85; a Mei Ling (salvar) é 140.96.
    for tentativa in range(5):
        ps.press(['SELECT'], 8, 8)
        ps.run(90)
        if ps.u32(sym['GV_PauseLevel']):
            break
    foto('radio_aberto')
    for _ in range(11):
        ps.press(['RIGHT'], 4, 10)
    ps.run(20)
    foto('radio_14096')
    ps.press(['CIRCLE'], 4, 8)
    salvou_em = None
    for s in range(400):
        ps.run(30)
        if s % 4 == 0:
            ps.press(['CIRCLE'], 4, 8)
        if s % 10 == 0:
            foto('mei_ling_%03d' % s)
        if salvou_em is None and saves_no_cartao(cartao):
            salvou_em = s
            foto('salvou')
        if salvou_em is not None and s > salvou_em + 20:
            break
    nomes = saves_no_cartao(cartao)
    print('saves no cartão:', nomes)
    return 0 if nomes else 1


if __name__ == '__main__':
    raise SystemExit(main())
