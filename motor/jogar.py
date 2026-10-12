"""Metal Gear Bandicoot: janela para jogar a fusão, com som, teclado e controle (ou dois cliques no JOGAR.bat).

    python -I motor/jogar.py            abre o teste mais novo (motor/out/testeN) na tela de título: Novo Jogo
    python -I motor/jogar.py --dock     entra direto no Loading Dock (o atalho dos testes)
    python -I motor/jogar.py --menu     para no seletor de fases do modo de desenvolvimento (cima/baixo + bolinha)
    python -I motor/jogar.py --disco motor/out/teste9/mgb.cue    um disco/teste específico

Sem testes em motor/out/testeN (quem baixou do GitHub), abre motor/out/mgb.m3u ou mgb.cue, o que o
motor/montar_disco.py grava. Com os dois discos (o .m3u), quando o jogo pede o outro disco o programa troca
sozinho; é só apertar Start (Enter). F9 troca à mão. O cartão de memória fica em motor/saves/pcsx-card1.mcd e
vale para todos os testes: dá para salvar com a Mei Ling e continuar depois.

Usa o mesmo emulador do robô de testes (PCSX ReARMed, BIOS embutida): não precisa de BIOS de PS1. A CPU é
interpretada: o recompilador do PCSX ReARMed cai na cena do Heliporto (--rapido liga ele mesmo assim).

Teclado                     Controle (Xbox)        PS1
  setas                       direcional/analógico   direcional
  Z                           A                      X (pular; de novo no ar = pulo duplo)
  X                           B                      bolinha (soco = giro do Crash)
  A                           X                      quadrado (arma)
  S                           Y                      triângulo (primeira pessoa)
  Q / W                       LB / RB                L1 / R1 (R1 segurado = agachar / engatinhar)
  E / R                       LT / RT                L2 / R2
  Enter                       Start                  Start (pausa)
  Backspace                   Back                   Select (rádio)
  F5 / F7                     -                      salvar / carregar estado
  F9                          -                      trocar de disco
  F12                         -                      foto (vai para diario/img)
  Esc                         -                      sair
"""
import argparse
import os
import sys
import time

import numpy as np

MOTOR = os.path.dirname(os.path.abspath(__file__))
FUSAO = os.path.dirname(MOTOR)
sys.path.insert(0, os.path.join(MOTOR, 'harness'))
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')

import pygame  # noqa: E402
from psx import PSX, PAD  # noqa: E402
import retro  # noqa: E402

TECLAS = {
    pygame.K_UP: 'UP', pygame.K_DOWN: 'DOWN', pygame.K_LEFT: 'LEFT', pygame.K_RIGHT: 'RIGHT',
    pygame.K_z: 'CROSS', pygame.K_x: 'CIRCLE', pygame.K_a: 'SQUARE', pygame.K_s: 'TRIANGLE',
    pygame.K_q: 'L1', pygame.K_w: 'R1', pygame.K_e: 'L2', pygame.K_r: 'R2',
    pygame.K_RETURN: 'START', pygame.K_BACKSPACE: 'SELECT',
}
BOTOES_CONTROLE = {0: 'CROSS', 1: 'CIRCLE', 2: 'SQUARE', 3: 'TRIANGLE', 4: 'L1', 5: 'R1', 6: 'SELECT', 7: 'START'}


class Som:
    """Áudio do emulador tocado pelo mixer do pygame, que fica no dispositivo de som padrão do Windows.

    Até o teste 10 o programa abria o primeiro dispositivo da lista do SDL, e ele pode ser uma saída sem nada ligado:
    no PC do ByteMirage era o "Áudio Digital (S/PDIF)", e o jogo ficava mudo nos alto-falantes."""

    BLOCO = 0.05    # segundos de som por pedaço entregue ao mixer

    def __init__(self, taxa):
        taxa = int(taxa)
        if pygame.mixer.get_init() != (taxa, -16, 2):
            pygame.mixer.quit()
            pygame.mixer.init(frequency=taxa, size=-16, channels=2, buffer=1024)
        if not pygame.mixer.get_init():
            raise RuntimeError('nenhuma saída de som')
        self.canal = pygame.mixer.Channel(0)
        self.bloco = int(taxa * self.BLOCO) * 4
        self.fila = bytearray()

    def empurrar(self, dados, bytes_por_segundo):
        self.fila += dados
        if len(self.fila) > bytes_por_segundo // 4:   # mais de 0,25 s acumulado: joga fora o mais velho
            del self.fila[:len(self.fila) - bytes_por_segundo // 10]
        # Um pedaço tocando e um na fila do canal: no máximo ~0,1 s de atraso.
        while len(self.fila) >= self.bloco and self.canal.get_queue() is None:
            pedaco = pygame.mixer.Sound(buffer=bytes(self.fila[:self.bloco]))
            del self.fila[:self.bloco]
            if self.canal.get_busy():
                self.canal.queue(pedaco)
            else:
                self.canal.play(pedaco)


def disco_mais_novo():
    """O teste de número mais alto em motor/out/testeN (com os dois discos, o .m3u); sem testes, o que o
    montar_disco.py grava em motor/out/ (quem baixou do GitHub)."""
    out = os.path.join(MOTOR, 'out')
    testes = []
    for nome in os.listdir(out) if os.path.isdir(out) else []:
        if nome.startswith('teste') and nome[5:].isdigit() and os.path.exists(os.path.join(out, nome, 'mgb.cue')):
            testes.append((int(nome[5:]), nome))
    pastas = [os.path.join(out, nome) for _, nome in sorted(testes, reverse=True)] + [out]
    for pasta in pastas:
        for arquivo in ('mgb.m3u', 'mgb.cue'):
            if os.path.exists(os.path.join(pasta, arquivo)):
                return os.path.join(pasta, arquivo)
    return None


def enderecos(disco):
    """Endereços que o montar_disco.py grava ao lado do disco: o nome da fase (para trocar de disco sozinho) e o
    pedido do seletor de fases. Vazio nos testes antigos (até o 9)."""
    import json
    base = os.path.splitext(os.path.abspath(disco))[0]
    for arq in (base + '.json', os.path.join(os.path.dirname(base), 'mgb.json')):
        if os.path.exists(arq):
            with open(arq, encoding='utf-8') as f:
                return {k: int(v, 16) for k, v in json.load(f).items() if isinstance(v, str)}
    return {}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--disco', help='.cue ou .m3u (padrão: o teste mais novo em motor/out/testeN)')
    modo = ap.add_mutually_exclusive_group()
    modo.add_argument('--dock', action='store_true', help='entra direto no Loading Dock')
    modo.add_argument('--menu', action='store_true', help='para no seletor de fases do modo de desenvolvimento')
    ap.add_argument('--rapido', action='store_true', help='CPU recompilada (mais leve, mas cai na cena do Heliporto)')
    ap.add_argument('--escala', type=int, default=3)
    ap.add_argument('--quadros', type=int, default=0, help='(teste) sai depois de N quadros e salva uma foto')
    a = ap.parse_args()
    a.disco = a.disco or disco_mais_novo()
    if not a.disco or not os.path.exists(a.disco):
        print('Não achei o disco da fusão (%s).\nOs discos não vêm no repositório: monte o seu com os passos de '
              '"Como rodar" do README.md (precisa das suas cópias do Metal Gear Solid e do Crash 3).' % a.disco)
        return 1
    pasta = os.path.dirname(os.path.abspath(a.disco))
    nome_teste = os.path.basename(pasta) if os.path.basename(pasta).startswith('teste') else 'fusão'
    print('abrindo', a.disco)

    pygame.mixer.pre_init(44100, -16, 2, 1024)
    pygame.init()
    pygame.joystick.init()
    controles = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
    tela = pygame.display.set_mode((320 * a.escala, 240 * a.escala))

    # Cartão de memória num arquivo do próprio núcleo (motor/saves/pcsx-card1.mcd), o mesmo em todos os testes.
    opcoes = {'pcsx_rearmed_memcard1': 'shared'}
    if not a.rapido:
        opcoes['pcsx_rearmed_drc'] = 'disabled'
    ps = PSX(a.disco, opcoes)
    ps.core.audio = []
    taxa = ps.core.sample_rate or 44100
    try:
        som = Som(taxa)
    except Exception as e:          # sem placa de som: joga mudo
        print('sem som:', e)
        som = None
    discos = ps.core.num_disks()
    end = enderecos(a.disco)
    fase_em = end.get('GM_CurrentStageName')

    def titulo(aviso=''):
        txt = 'Metal Gear Bandicoot: Wumpa Fruit Eater  |  %s' % nome_teste
        if discos > 1:
            txt += '  |  disco %d' % (ps.core.disk_index() + 1)
        pygame.display.set_caption(txt + ('  |  ' + aviso if aviso else ''))

    titulo()
    # Desde o teste 10 o jogo abre no título; o seletor de fases é pedido escrevendo 1 em MGB_SeletorDeFases
    # logo depois de ligar (o executável já está na RAM), antes de o jogo carregar o título.
    pedir_seletor = (a.dock or a.menu) and 'MGB_SeletorDeFases' in end
    if a.dock:
        automatico = [((), 1200)] + [(['DOWN'], 2), ((), 8)] * 2 + [((), 5), (['CIRCLE'], 2), ((), 2)]
    elif a.menu:
        automatico = [((), 1200)]
    else:
        automatico = []
    # Cada disco tem seu próprio estado: builds diferentes mudam os endereços
    # do jogo, e restaurar a RAM de outro teste pode travar a nova versão.
    estado = os.path.join(pasta, 'jogar.state')
    fps = ps.core.fps or 59.94
    proximo = time.perf_counter()
    relogio = pygame.time.Clock()
    troca = []          # passos da troca de disco, cada um com os quadros de espera até o próximo
    trocou_nesta_tela = False

    def trocar_disco():
        if discos > 1 and not troca:
            troca.extend({'acao': acao, 'espera': espera, 'feito': False}
                         for acao, espera in (('abrir', 60), ('por', 30), ('fechar', 0)))

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                pygame.quit()
                return
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_F5:
                ps.save_state(estado)
                with open(estado + '.disco', 'w') as f:
                    f.write(str(ps.core.disk_index()))
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_F7 and os.path.exists(estado):
                if discos > 1 and os.path.exists(estado + '.disco'):
                    with open(estado + '.disco') as f:
                        salvo = int(f.read().strip() or 0)
                    if salvo != ps.core.disk_index():
                        ps.core.set_tray_open(True)
                        ps.core.insert_disk(salvo)
                        ps.core.set_tray_open(False)
                ps.load_state(estado)
                titulo()
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_F9:
                trocar_disco()
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_F12:
                nome = time.strftime('%Y%m%d_%H%M%S') + '_bytemirage_jogando.png'
                ps.shot(os.path.join(FUSAO, 'diario', 'img', nome), scale=3)
            if ev.type == pygame.JOYDEVICEADDED:
                controles = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]

        botoes = set()
        if automatico:
            b, n = automatico[0]
            botoes = set(b)
            automatico[0] = (b, n - 1)
            if n <= 1:
                automatico.pop(0)
        else:
            k = pygame.key.get_pressed()
            botoes = {nome for tecla, nome in TECLAS.items() if k[tecla]}
            for c in controles:
                for i, nome in BOTOES_CONTROLE.items():
                    if i < c.get_numbuttons() and c.get_button(i):
                        botoes.add(nome)
                if c.get_numaxes() >= 2:
                    x, y = c.get_axis(0), c.get_axis(1)
                    if x < -0.5: botoes.add('LEFT')
                    if x > 0.5: botoes.add('RIGHT')
                    if y < -0.5: botoes.add('UP')
                    if y > 0.5: botoes.add('DOWN')
                if c.get_numaxes() >= 6:
                    if c.get_axis(4) > 0.3: botoes.add('L2')
                    if c.get_axis(5) > 0.3: botoes.add('R2')
                if c.get_numhats():
                    hx, hy = c.get_hat(0)
                    if hx < 0: botoes.add('LEFT')
                    if hx > 0: botoes.add('RIGHT')
                    if hy > 0: botoes.add('UP')
                    if hy < 0: botoes.add('DOWN')

        ps.run(1, sorted(botoes))
        if pedir_seletor and ps.frame == 30:
            ps.w32(end['MGB_SeletorDeFases'], 1)
        # Troca de disco: abre a tampa, espera, põe o outro disco e fecha (o jogo pede Start depois).
        if troca:
            passo = troca[0]
            if not passo['feito']:
                if passo['acao'] == 'abrir':
                    ps.core.set_tray_open(True)
                    titulo('trocando de disco...')
                elif passo['acao'] == 'por':
                    ps.core.insert_disk((ps.core.disk_index() + 1) % discos)
                else:
                    ps.core.set_tray_open(False)
                    titulo('disco %d colocado: aperte Start (Enter)' % (ps.core.disk_index() + 1))
                passo['feito'] = True
            elif passo['espera'] > 0:
                passo['espera'] -= 1
            else:
                troca.pop(0)
        # A tela "change" é o MGS pedindo o outro disco: troca sozinho, uma vez por visita.
        if fase_em and discos > 1 and ps.frame % 30 == 0:
            na_troca = ps.cstr(fase_em, 8) == 'change'
            if na_troca and not trocou_nesta_tela and ps.frame > 120:
                trocou_nesta_tela = True
                trocar_disco()
            elif not na_troca and trocou_nesta_tela:
                trocou_nesta_tela = False
                titulo()
        if a.quadros and ps.frame >= a.quadros:
            ps.shot(os.path.join(MOTOR, 'out', 'jogar_teste.png'))
            pygame.quit()
            return
        if ps.core.audio:
            dados = b''.join(ps.core.audio)
            ps.core.audio.clear()
            if som:
                som.empurrar(dados, taxa * 4)

        img = ps.image()
        sup = pygame.surfarray.make_surface(np.ascontiguousarray(img.swapaxes(0, 1)))
        tela.blit(pygame.transform.scale(sup, tela.get_size()), (0, 0))
        pygame.display.flip()

        if automatico:
            continue                 # o caminho até o Dock roda o mais rápido possível
        proximo += 1.0 / fps
        espera = proximo - time.perf_counter()
        if espera > 0:
            time.sleep(espera)
        else:
            proximo = time.perf_counter()
        relogio.tick()


if __name__ == '__main__':
    main()
