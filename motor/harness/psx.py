"""Robô de testes do PS1: carrega um disco ou executável no PCSX ReARMed (libretro), avança quadro a quadro,
aperta botões, lê e escreve a RAM pelo endereço do jogo (0x80000000...) e salva capturas.

    from psx import PSX
    ps = PSX('discos/mgb.cue')
    ps.run(60)                        # 1 segundo
    ps.press(['START'], 2)            # aperta Start por 2 quadros e solta
    ps.hold(['UP'], 30)               # segura cima por 30 quadros
    ps.u32(0x800ABBA0)                # lê memória
    ps.shot('captura.png')            # salva a tela
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import retro  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
MOTOR = os.path.dirname(AQUI)
CORE = os.path.join(MOTOR, 'tools', 'core', 'pcsx_rearmed_libretro.dll')

RAM_BASE = 0x80000000
RAM_SIZE = 0x200000

# Nomes do controle do PS1 -> botões do RetroPad
PAD = dict(CROSS=retro.B, CIRCLE=retro.A, SQUARE=retro.Y, TRIANGLE=retro.X, START=retro.START,
           SELECT=retro.SELECT, UP=retro.UP, DOWN=retro.DOWN, LEFT=retro.LEFT, RIGHT=retro.RIGHT,
           L1=retro.L, R1=retro.R, L2=retro.L2, R2=retro.R2)

OPCOES = {
    'pcsx_rearmed_drc': 'enabled',
    'pcsx_rearmed_frameskip_type': 'disabled',
    'pcsx_rearmed_show_bios_bootlogo': 'disabled',
    'pcsx_rearmed_gpu_thread_rendering': 'disabled',   # quadro pronto no fim do retro_run
    'pcsx_rearmed_rgb32_output': 'enabled',
}


class PSX:
    def __init__(self, game, options=None, log=False, saves=None):
        """saves: pasta do cartão de memória e afins (padrão motor/saves)."""
        opts = dict(OPCOES)
        opts.update(options or {})
        self.log_lines = []

        def _log(level, msg):
            self.log_lines.append(msg)
            if log:
                print('[core]', msg)

        self.core = retro.Core(CORE, os.path.join(MOTOR, 'sys'), saves or os.path.join(MOTOR, 'saves'), opts, _log)
        self.core.load(game)
        mem = self.core.memory(retro.MEMORY_SYSTEM_RAM)
        if not mem:
            raise RuntimeError('o núcleo não expôs a RAM')
        ptr, size = mem
        import ctypes as C
        self.ram = np.ctypeslib.as_array((C.c_ubyte * size).from_address(ptr))
        self.ram_size = size

    # --- tempo e controle ---------------------------------------------------------------
    @property
    def frame(self):
        return self.core.frames

    def run(self, frames=1, buttons=()):
        self.core.run(frames, [PAD[b] for b in buttons])

    def hold(self, buttons, frames):
        self.run(frames, buttons)

    def press(self, buttons, frames=2, release=2):
        self.run(frames, buttons)
        self.run(release, ())

    # --- memória (little-endian, endereços do jogo) --------------------------------------
    def _off(self, addr, n):
        o = (addr & 0x1FFFFFFF) % self.ram_size
        if o + n > self.ram_size:
            raise IndexError('endereço %08X fora da RAM' % addr)
        return o

    def read(self, addr, n):
        o = self._off(addr, n)
        return bytes(self.ram[o:o + n])

    def write(self, addr, data):
        o = self._off(addr, len(data))
        self.ram[o:o + len(data)] = np.frombuffer(bytes(data), np.uint8)

    def u8(self, a):
        return self.read(a, 1)[0]

    def u16(self, a):
        return int.from_bytes(self.read(a, 2), 'little')

    def s16(self, a):
        return int.from_bytes(self.read(a, 2), 'little', signed=True)

    def u32(self, a):
        return int.from_bytes(self.read(a, 4), 'little')

    def s32(self, a):
        return int.from_bytes(self.read(a, 4), 'little', signed=True)

    def w8(self, a, v):
        self.write(a, bytes([v & 0xFF]))

    def w16(self, a, v):
        self.write(a, (int(v) & 0xFFFF).to_bytes(2, 'little'))

    def w32(self, a, v):
        self.write(a, (int(v) & 0xFFFFFFFF).to_bytes(4, 'little'))

    def snapshot(self):
        return self.ram.copy()

    def cstr(self, a, n=64):
        b = self.read(a, n)
        return b.split(b'\0', 1)[0].decode('latin-1')

    # --- imagem e estado -----------------------------------------------------------------
    def image(self):
        if self.core.frame is None:      # logo depois de carregar um estado ainda não há imagem
            self.run(1)
        return self.core.image()

    def shot(self, path, scale=2):
        from PIL import Image
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        im = Image.fromarray(self.image())
        if scale != 1:
            im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
        im.save(path)
        return path

    def save_state(self, path=None):
        st = self.core.save_state()
        if path:
            with open(path, 'wb') as f:
                f.write(st)
        return st

    def load_state(self, st_or_path):
        if isinstance(st_or_path, str):
            with open(st_or_path, 'rb') as f:
                st_or_path = f.read()
        self.core.load_state(st_or_path)

    def close(self):
        self.core.close()
