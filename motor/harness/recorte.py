"""Acha o Crash na tela (pixels laranja) e recorta ampliado: serve para conferir pose e direção."""
import numpy as np
from PIL import Image


def achar_crash(img):
    a = np.asarray(img).astype(int)
    m = (a[..., 0] > 150) & (a[..., 1] < 110) & (a[..., 2] < 80)
    ys, xs = np.nonzero(m)
    if len(xs) < 5:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def recorte(img, margem=14, escala=4):
    img = img if isinstance(img, Image.Image) else Image.fromarray(img)
    caixa = achar_crash(img)
    if caixa is None:
        return img.resize((img.width * escala // 4, img.height * escala // 4))
    x0, y0, x1, y1 = caixa
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    r = max(x1 - x0, y1 - y0) // 2 + margem
    c = img.crop((cx - r, cy - r, cx + r, cy + r))
    return c.resize((2 * r * escala, 2 * r * escala), Image.NEAREST)


def folha(imgs, lado=240, rotulos=None):
    from PIL import ImageDraw
    out = Image.new('RGB', (lado * len(imgs), lado + 14), (20, 20, 24))
    d = ImageDraw.Draw(out)
    for i, im in enumerate(imgs):
        out.paste(recorte(im).resize((lado, lado), Image.NEAREST), (i * lado, 14))
        if rotulos:
            d.text((i * lado + 4, 1), rotulos[i], fill=(255, 255, 255))
    return out
