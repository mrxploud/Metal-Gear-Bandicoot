"""Metal Gear Bandicoot: janela para jogar o disco da fusão (motor/out/mgb.cue), com som, teclado e controle.

    python -I motor/jogar.py            entra direto no Loading Dock
    python -I motor/jogar.py --menu     para no seletor de fases do modo dev (cima/baixo + bolinha)

Usa o mesmo emulador do robô de testes (PCSX ReARMed, BIOS embutida): não precisa de BIOS de PS1.

Teclado                     Controle (Xbox)        PS1
  setas                       direcional/analógico   direcional
  Z                           A                      X (agachar / deitar)
  X                           B                      bolinha (soco = giro do Crash)
  A                           X                      quadrado (arma)
  S                           Y                      triângulo (primeira pessoa)
  Q / W                       LB / RB                L1 / R1
  E / R                       LT / RT                L2 / R2
  Enter                       Start                  Start (pausa)
  Backspace                   Back                   Select (rádio)
  F5 / F7                     -                      salvar / carregar estado
  F12                         -                      foto (vai para diario/img)
  Esc                         -                      sair
"""
import argparse
import collections
import os
import sys
import threading
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
    """Fila de áudio do emulador tocada pelo SDL (pygame._sdl2.audio)."""

    def __init__(self, taxa):
        from pygame._sdl2.audio import AudioDevice, AUDIO_S16, AUDIO_ALLOW_FORMAT_CHANGE, get_audio_device_names
        nomes = get_audio_device_names(False)
        if not nomes:
            raise RuntimeError('nenhuma saída de som')
        self.fila = collections.deque()
        self.pendente = 0
        self.trava = threading.Lock()
        self.dev = AudioDevice(devicename=nomes[0], iscapture=False, frequency=int(taxa), audioformat=AUDIO_S16,
                               numchannels=2, chunksize=1024, allowed_changes=AUDIO_ALLOW_FORMAT_CHANGE,
                               callback=self._callback)
        self.dev.pause(0)

    def _callback(self, dev, mem):
        n = len(mem)
        out = bytearray(n)
        pos = 0
        with self.trava:
            while pos < n and self.fila:
                bloco = self.fila[0]
                k = min(len(bloco), n - pos)
                out[pos:pos + k] = bloco[:k]
                pos += k
                if k == len(bloco):
                    self.fila.popleft()
                else:
                    self.fila[0] = bloco[k:]
                self.pendente -= k
        mem[:] = bytes(out)

    def empurrar(self, dados, bytes_por_segundo):
        with self.trava:
            if self.pendente > bytes_por_segundo // 5:   # mais de 0,2 s acumulado: joga fora para não atrasar
                self.fila.clear()
                self.pendente = 0
            self.fila.append(dados)
            self.pendente += len(dados)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--disco', default=os.path.join(MOTOR, 'out', 'mgb.cue'))
    ap.add_argument('--menu', action='store_true', help='não entra sozinho no Loading Dock')
    ap.add_argument('--escala', type=int, default=3)
    ap.add_argument('--quadros', type=int, default=0, help='(teste) sai depois de N quadros e salva uma foto')
    a = ap.parse_args()

    pygame.mixer.pre_init(44100, -16, 2, 1024)
    pygame.init()
    pygame.joystick.init()
    controles = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
    tela = pygame.display.set_mode((320 * a.escala, 240 * a.escala))
    pygame.display.set_caption('Metal Gear Bandicoot: Wumpa Fruit Eater')

    ps = PSX(a.disco)
    ps.core.audio = []
    taxa = ps.core.sample_rate or 44100
    try:
        som = Som(taxa)
    except Exception as e:          # sem placa de som: joga mudo
        print('sem som:', e)
        som = None

    automatico = [] if a.menu else ([((), 1200)] + [(['DOWN'], 2), ((), 8)] * 2 + [((), 5), (['CIRCLE'], 2), ((), 2)])
    estado = os.path.join(MOTOR, 'out', 'jogar.state')
    fps = ps.core.fps or 59.94
    proximo = time.perf_counter()
    relogio = pygame.time.Clock()

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                pygame.quit()
                return
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_F5:
                ps.save_state(estado)
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_F7 and os.path.exists(estado):
                ps.load_state(estado)
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
