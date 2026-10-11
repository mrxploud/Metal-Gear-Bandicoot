"""Desenhista de prévias: um rasterizador de triângulos pequeno, em numpy, com z-buffer.

Não tenta imitar o PlayStation pixel a pixel. Serve para a gente ENXERGAR o que saiu do disco (conferir o
extrator) e para gerar as imagens e GIFs do diário. Luz simples: ambiente + uma direção, pela normal do vértice.
"""
import math

import numpy as np
from PIL import Image


def rotacao(guinada_graus, inclinacao_graus):
    """Matriz que gira o modelo em torno de Y (guinada) e depois inclina a câmera em torno de X."""
    g, i = math.radians(guinada_graus), math.radians(inclinacao_graus)
    ry = np.array([[math.cos(g), 0, math.sin(g)], [0, 1, 0], [-math.sin(g), 0, math.cos(g)]])
    rx = np.array([[1, 0, 0], [0, math.cos(i), -math.sin(i)], [0, math.sin(i), math.cos(i)]])
    return rx @ ry


class Tela:
    def __init__(self, largura, altura, fundo=(0, 0, 0, 0)):
        self.l, self.a = largura, altura
        self.cor = np.zeros((altura, largura, 4), np.float32)
        self.cor[:] = np.array(fundo, np.float32)
        self.z = np.full((altura, largura), -np.inf, np.float32)

    def triangulo(self, p, cores, textura=None, uvs=None, mistura=None):
        """p: 3x3 (x, y de tela, z maior = mais perto). cores: 3x3 em 0..1 (multiplicam a textura, se houver).

        mistura: None = opaco; 0 = média com o fundo; 1 = soma; 2 = subtrai do fundo (os modos do PS1).
        Triângulo misturado respeita o z-buffer mas não escreve nele (desenhe-os por último, do fundo para a frente).
        """
        x0, x1 = int(max(0, math.floor(p[:, 0].min()))), int(min(self.l - 1, math.ceil(p[:, 0].max())))
        y0, y1 = int(max(0, math.floor(p[:, 1].min()))), int(min(self.a - 1, math.ceil(p[:, 1].max())))
        if x1 < x0 or y1 < y0:
            return
        area = (p[1, 0] - p[0, 0]) * (p[2, 1] - p[0, 1]) - (p[2, 0] - p[0, 0]) * (p[1, 1] - p[0, 1])
        if abs(area) < 1e-9:
            return
        ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
        px, py = xs + 0.5, ys + 0.5
        w0 = ((p[1, 0] - px) * (p[2, 1] - py) - (p[2, 0] - px) * (p[1, 1] - py)) / area
        w1 = ((p[2, 0] - px) * (p[0, 1] - py) - (p[0, 0] - px) * (p[2, 1] - py)) / area
        w2 = 1.0 - w0 - w1
        dentro = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not dentro.any():
            return
        z = w0 * p[0, 2] + w1 * p[1, 2] + w2 * p[2, 2]
        zona = self.z[y0:y1 + 1, x0:x1 + 1]
        dentro &= z > zona
        if not dentro.any():
            return
        rgb = w0[..., None] * cores[0] + w1[..., None] * cores[1] + w2[..., None] * cores[2]
        alfa = np.ones(rgb.shape[:2], np.float32)
        if textura is not None:
            u = w0 * uvs[0][0] + w1 * uvs[1][0] + w2 * uvs[2][0]
            v = w0 * uvs[0][1] + w1 * uvs[1][1] + w2 * uvs[2][1]
            ui = np.clip(u.astype(np.int32), 0, textura.shape[1] - 1)
            vi = np.clip(v.astype(np.int32), 0, textura.shape[0] - 1)
            texel = textura[vi, ui].astype(np.float32) / 255.0
            rgb = texel[..., :3] * rgb * 2.0                 # no PS1, cor 128 = textura sem alteração
            alfa = texel[..., 3]
            dentro &= alfa > 0.5
            if not dentro.any():
                return
        rgb = np.clip(rgb, 0, 1)
        alvo = self.cor[y0:y1 + 1, x0:x1 + 1]
        if mistura is None:
            alvo[dentro, :3] = rgb[dentro]
            alvo[dentro, 3] = 1.0
            zona[dentro] = z[dentro]
            return
        fundo = alvo[dentro, :3]
        forca = rgb[dentro].max(axis=1)
        if mistura == 1:
            alvo[dentro, :3] = np.clip(fundo + rgb[dentro], 0, 1)
            alvo[dentro, 3] = np.maximum(alvo[dentro, 3], forca)
        elif mistura == 2:
            alvo[dentro, :3] = np.clip(fundo - rgb[dentro], 0, 1)
            alvo[dentro, 3] = np.maximum(alvo[dentro, 3], forca * 0.6)       # sobre o nada, vira um véu escuro
        else:
            alvo[dentro, :3] = (fundo + rgb[dentro]) / 2
            alvo[dentro, 3] = np.maximum(alvo[dentro, 3], 0.5)

    def imagem(self, reduzir=1):
        img = Image.fromarray((np.clip(self.cor, 0, 1) * 255).astype(np.uint8), 'RGBA')
        if reduzir > 1:
            img = img.resize((self.l // reduzir, self.a // reduzir), Image.LANCZOS)
        return img


LUZ = np.array([0.35, 0.75, 0.55])
LUZ = LUZ / np.linalg.norm(LUZ)


def desenhar(vertices, normais, triangulos, tamanho=256, guinada=30, inclinacao=12, enquadre=None, amostras=3,
             fundo=(0, 0, 0, 0)):
    """Desenha um quadro.

    vertices   (N, 3) float, Y para cima
    normais    (N, 3) float (qualquer escala) ou None
    triangulos lista de dicts: {'v': (a, b, c), 'rgb': (r, g, b) 0..255, 'liso': bool,
               'textura': array RGBA ou None, 'uvs': [(u, v)] * 3}
               ou, no lugar de 'rgb', 'rgbs': 3 cores (uma por canto), sem luz por cima
    enquadre   (centro xyz, raio): o que cabe na tela; se None, calcula deste quadro
    """
    v = np.asarray(vertices, np.float64)
    if enquadre is None:
        centro = (v.min(0) + v.max(0)) / 2
        raio = float(np.linalg.norm(v - centro, axis=1).max()) or 1.0
    else:
        centro, raio = np.asarray(enquadre[0], np.float64), float(enquadre[1])
    L = tamanho * amostras
    rot = rotacao(guinada, inclinacao)
    cam = (v - centro) @ rot.T
    escala = (L * 0.46) / raio
    tela = np.empty_like(cam)
    tela[:, 0] = L / 2 + cam[:, 0] * escala
    tela[:, 1] = L / 2 - cam[:, 1] * escala
    tela[:, 2] = cam[:, 2]
    if normais is not None:
        n = np.asarray(normais, np.float64)
        comprimento = np.linalg.norm(n, axis=1, keepdims=True)
        comprimento[comprimento == 0] = 1
        n = (n / comprimento) @ rot.T
        luz = 0.55 + 0.6 * np.clip(n @ LUZ, 0, 1)
    else:
        luz = np.ones(len(v))
    t = Tela(L, L, fundo)
    opacos = [tri for tri in triangulos if tri.get('mistura') is None]
    misturados = [tri for tri in triangulos if tri.get('mistura') is not None]
    misturados.sort(key=lambda tri: float(tela[list(tri['v']), 2].mean()))        # do fundo para a frente
    for tri in opacos + misturados:
        a, b, c = tri['v']
        if tri.get('rgbs') is not None:                  # Crash 2/3: uma cor por canto, a luz já vem pintada
            cores = np.array(tri['rgbs'], np.float64) / 255.0
        else:
            base = np.array(tri['rgb'], np.float64) / 255.0
            if tri.get('liso') or normais is None:
                cores = np.array([base, base, base])
            else:
                cores = np.array([base * luz[a], base * luz[b], base * luz[c]])
        t.triangulo(tela[[a, b, c]], cores.astype(np.float32), tri.get('textura'), tri.get('uvs'), tri.get('mistura'))
    return t.imagem(amostras)


def folha_de_contato(imagens, colunas, fundo=(24, 24, 32, 255), legenda=None):
    """Junta os quadros numa imagem só (uma grade), para ver a animação inteira de uma vez."""
    if not imagens:
        raise ValueError('nenhuma imagem')
    l, a = imagens[0].size
    linhas = (len(imagens) + colunas - 1) // colunas
    topo = 14 if legenda else 0
    folha = Image.new('RGBA', (colunas * l, linhas * a + topo), fundo)
    for i, img in enumerate(imagens):
        folha.alpha_composite(img, ((i % colunas) * l, (i // colunas) * a + topo))
    if legenda:
        from PIL import ImageDraw
        ImageDraw.Draw(folha).text((4, 1), legenda, fill=(255, 255, 255, 255))
    return folha


def salvar_gif(imagens, caminho, fps=30, fundo=(24, 24, 32)):
    """GIF animado. O GIF não tem meio-transparente, então colamos sobre um fundo liso."""
    quadros = []
    for img in imagens:
        base = Image.new('RGBA', img.size, fundo + (255,))
        base.alpha_composite(img)
        quadros.append(base.convert('P', palette=Image.ADAPTIVE, colors=255))
    duracao = max(20, round(1000 / fps / 10) * 10)       # o GIF conta em centésimos de segundo
    quadros[0].save(caminho, save_all=True, append_images=quadros[1:], duration=duracao, loop=0, disposal=2)
    return duracao
