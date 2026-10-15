"""O robô anda até um ponto do mapa como um jogador: só com o direcional.

No MGS o direcional é relativo à câmera, e a câmera muda de ângulo de uma área para outra. Então o robô mede o que
cada direção faz (um toque curto e a posição antes e depois) e escolhe, a cada passo, a direção que mais aproxima do
alvo; se parar de avançar, mede de novo.

    from andar import Andador
    a = Andador(ps, sym)               # ps = PSX (ou o RecPSX do estúdio: passe rec.passo como `passo`)
    a.ate(11000, -11500)               # devolve True se chegou (raio 250)
"""
import math

DIRS = {'UP': ['UP'], 'DOWN': ['DOWN'], 'LEFT': ['LEFT'], 'RIGHT': ['RIGHT'],
        'UL': ['UP', 'LEFT'], 'UR': ['UP', 'RIGHT'], 'DL': ['DOWN', 'LEFT'], 'DR': ['DOWN', 'RIGHT']}


class Andador:
    def __init__(self, ps, sym, passo=None, extra=()):
        self.ps, self.sym = ps, sym
        self.passo = passo or (lambda botoes, n: ps.run(n, botoes))
        self.extra = list(extra)          # botões segurados junto (ex.: ['R1'] para engatinhar)
        self.vet = {}

    def pos(self):
        c = self.ps.u32(self.sym['GM_PlayerControl'])
        return self.ps.s16(c), self.ps.s16(c + 2), self.ps.s16(c + 4)

    def calibrar(self):
        self.vet = {}
        for nome in ('UP', 'RIGHT', 'DOWN', 'LEFT'):
            x0, _, z0 = self.pos()
            self.passo(DIRS[nome] + self.extra, 8)
            x1, _, z1 = self.pos()
            self.vet[nome] = (x1 - x0, z1 - z0)
        u, r = self.vet['UP'], self.vet['RIGHT']
        self.vet['UL'] = (u[0] - r[0], u[1] - r[1])
        self.vet['UR'] = (u[0] + r[0], u[1] + r[1])
        self.vet['DL'] = (-u[0] - r[0], -u[1] - r[1])
        self.vet['DR'] = (-u[0] + r[0], -u[1] + r[1])

    def ate(self, x, z, raio=250, max_passos=200, quadros=6, log=None):
        if not self.vet:
            self.calibrar()
        parado = 0
        for i in range(max_passos):
            px, py, pz = self.pos()
            dx, dz = x - px, z - pz
            d = math.hypot(dx, dz)
            if log:
                log((px, py, pz), d)
            if d < raio:
                return True
            melhor, nome = -2, None
            for k, (vx, vz) in self.vet.items():
                n = math.hypot(vx, vz)
                if n < 1:
                    continue
                c = (vx * dx + vz * dz) / (n * d)
                if c > melhor:
                    melhor, nome = c, k
            if nome is None:
                self.calibrar()
                continue
            self.passo(DIRS[nome] + self.extra, quadros if d > 1200 else 3)
            nx, _, nz = self.pos()
            if math.hypot(x - nx, z - nz) > d - 15:
                parado += 1
                if parado >= 3:
                    self.calibrar()
                    parado = 0
            else:
                parado = 0
        return False
