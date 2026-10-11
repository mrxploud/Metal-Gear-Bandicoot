#!/usr/bin/env python
"""IMPROVISOS: movimentos que o Crash 1 NÃO tem, montados só com quadros que saíram do disco dele.

    python -I improvisos.py                 gera as prévias em improvisos/ (não mexe na entrega)
    python -I improvisos.py --entregar      além disso grava as animações em out/ no formato do contrato

Pedido do ByteMirage (11/10/2026): andar agachado e derrapada. Conferido no script (`WillC.gooc`) e no disco:
o Crash 1 não tem nenhum dos dois; eles entraram na série no Crash 2. Tudo o que este arquivo produz é
MONTAGEM NOSSA, não animação original, e leva o prefixo IMPROVISO_ para ninguém confundir.

Como é possível: todas as animações "normais" do Crash usam o mesmo modelo (`WillG`, 381 vértices, na mesma
ordem). Então dá para somar, vértice a vértice, o movimento de uma animação em cima da pose de outra.

  IMPROVISO_AGACHADO_ANDANDO   corpo do `WILLY_DUCK` quadro 8 (abaixado, mãos na cabeça) + o vaivém das pernas
                               do `WILLY_WALK`, reduzido. 10 quadros = meio passo, como a corrida: a outra
                               metade é a mesma espelhada em X.
  IMPROVISO_AGACHADO_PARADO    os quadros 9..13 do `WILLY_DUCK` (ele se mexendo abaixado), sem alteração.
  IMPROVISO_DERRAPADA          a pose do `WILLY_KILLED_3` (ele cai sentado, pernas para a frente), girada 90
                               graus para olhar para a frente e descida até encostar no chão. 4 quadros.
"""
import argparse
import json
import math
import os
import struct
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import numpy as np                                             # noqa: E402
from PIL import Image, ImageDraw                               # noqa: E402

from crashlib import raster                                    # noqa: E402
import ver                                                     # noqa: E402

FPS = 30


def carregar(entrega, nome):
    a, pos, nor = entrega.animacao(nome)
    return a, pos, nor


def peso_das_pernas(repouso, abaixado):
    """1 nos pés e nas pernas, 0 no resto, com uma faixa de transição no quadril.

    Pela altura na pose parada só não basta: parado, as MÃOS do Crash também ficam abaixo do quadril. O que separa
    mão de perna é a pose abaixada: nela as mãos estão na cabeça e as pernas continuam embaixo.
    """
    peso = np.clip((430.0 - repouso[:, 1]) / 130.0, 0.0, 1.0)
    peso[abaixado[:, 1] > 450.0] = 0.0
    return peso[:, None]


def agachado_andando(entrega):
    _, duck, duck_n = carregar(entrega, 'WILLY_DUCK')
    _, walk, _ = carregar(entrega, 'WILLY_WALK')
    _, parado, _ = carregar(entrega, 'WILLY_STANCE1')
    base = duck[8].copy()
    w = peso_das_pernas(parado[11], base)
    usados = np.ones(len(base), bool)
    usados[:2] = False                                    # os vértices 0 e 1 do WillG não pertencem a triângulo nenhum
    media = walk.mean(axis=0)
    mais_baixo = walk.min(axis=0)
    quadros = []
    for f in range(len(walk)):
        d = (walk[f] - media) * w * np.array([0.55, 0.0, 0.55])        # vaivém das pernas, para a frente e para trás
        d[:, 1] = ((walk[f] - mais_baixo) * w)[:, 1] * 0.45            # o pé só sobe a partir do chão, nunca afunda
        p = base + d
        p[~usados] = p[2]
        quadros.append(p)
    return np.stack(quadros), np.repeat(duck_n[8][None], len(walk), axis=0)


def agachado_parado(entrega):
    _, duck, duck_n = carregar(entrega, 'WILLY_DUCK')
    return duck[9:14].copy(), duck_n[9:14].copy()


def derrapada(entrega):
    _, k3, k3_n = carregar(entrega, 'WILLY_KILLED_3')
    escolhidos = [3, 5, 7, 9]
    ang = math.radians(90)                                # a animação original está de lado; vira para +Z
    r = np.array([[math.cos(ang), 0, math.sin(ang)], [0, 1, 0], [-math.sin(ang), 0, math.cos(ang)]])
    pos, nor = [], []
    for f in escolhidos:
        p = k3[f] @ r.T
        n = k3_n[f] @ r.T
        usados = np.ones(len(p), bool)
        usados[:2] = False
        p[:, 1] -= p[usados, 1].min()                     # senta no chão
        p[:, 0] -= (p[usados, 0].min() + p[usados, 0].max()) / 2
        p[~usados] = p[2]
        pos.append(p)
        nor.append(n)
    return np.stack(pos), np.stack(nor)


IMPROVISOS = {
    'IMPROVISO_AGACHADO_ANDANDO': (agachado_andando, 'DUCK quadro 8 + pernas do WALK (x0,55); meio passo, espelhar em X na outra metade'),
    'IMPROVISO_AGACHADO_PARADO': (agachado_parado, 'DUCK quadros 9 a 13, sem alteração; tocar em vaivém'),
    'IMPROVISO_DERRAPADA': (derrapada, 'KILLED_3 quadros 3, 5, 7, 9, girado 90 graus e encostado no chão'),
}


def desenhar_folha(nome, descricao, pos, nor, tris, tamanho=150):
    todos = pos.reshape(-1, 3)
    centro = (todos.min(0) + todos.max(0)) / 2
    centro[1] = 520.0
    raio = 760.0
    linhas = []
    for guinada in (35, 90):
        linhas.append([raster.desenhar(pos[i], nor[i], tris, tamanho, guinada, 8, (centro, raio)) for i in range(len(pos))])
    folha = Image.new('RGBA', (tamanho * len(pos), tamanho * 2 + 16), (24, 24, 32, 255))
    d = ImageDraw.Draw(folha)
    d.text((4, 2), f'{nome}: {descricao}', fill=(255, 255, 255, 255))
    for li, linha in enumerate(linhas):
        for i, img in enumerate(linha):
            folha.alpha_composite(img, (i * tamanho, 16 + li * tamanho))
    return folha, linhas[0]


def gravar_na_entrega(entrega, nome, descricao, pos, nor):
    """Grava anim_<NOME>.bin e cru/<NOME>.bin e acrescenta a animação ao model.json, marcada como improviso."""
    ref = next(x for x in entrega.m['animacoes'] if x['nome'] == 'WILLY_STANCE1')
    k = np.array(ref['cru']['k'])
    chao = ref['cru']['chao']
    q, n = pos.shape[0], pos.shape[1]
    with open(os.path.join(entrega.pasta, f'anim_{nome}.bin'), 'wb') as f:
        f.write(np.round(pos).astype('<i2').tobytes())
        f.write(np.clip(np.round(nor), -128, 127).astype(np.int8).tobytes())
    pior = 0.0
    with open(os.path.join(entrega.pasta, 'cru', f'{nome}.bin'), 'wb') as f:
        for i in range(q):
            passos = (pos[i] + np.array([0, chao, 0])) / k
            o = np.floor(passos.min(0)).astype(int)
            b = np.round(passos - o)
            if b.max() > 255:
                raise ValueError(f'{nome} quadro {i}: não cabe em 1 byte por coordenada')
            pior = max(pior, float(np.abs((b + o) * k - np.array([0, chao, 0]) - pos[i]).max()))
            f.write(struct.pack('<3hH', int(o[0]), int(o[1]), int(o[2]), n))
            f.write(np.hstack([b.astype(np.uint8), np.clip(np.round(nor[i]), -128, 127).astype(np.int8).view(np.uint8)]).tobytes())
    registro = {
        'nome': nome, 'grupo': 'crash', 'improviso': True, 'descricao': descricao,
        'origem_no_disco': 'montagem (ver improvisos.py)', 'arquivo': f'anim_{nome}.bin', 'modelo': 'WillG',
        'quadros': q, 'fps': FPS, 'vertices': n, 'bytes': q * n * 9,
        'cru': {'arquivo': f'cru/{nome}.bin', 'bytes': q * (8 + n * 6), 'k': ref['cru']['k'], 'chao': chao,
                'por_quadro': ref['cru']['por_quadro'], 'formula': ref['cru']['formula'],
                'erro_do_arredondamento': round(pior, 2)},
        'previa': f'../improvisos/{nome}.png', 'gif': f'../improvisos/{nome}.gif'}
    entrega.m['animacoes'] = [x for x in entrega.m['animacoes'] if x['nome'] != nome] + [registro]
    return pior


def principal():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entregar', action='store_true', help='grava também em out/ (só depois de o ByteMirage aprovar)')
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    entrega = ver.Entrega(os.path.join(AQUI, 'out'))
    tris = entrega.triangulos('WillG')
    pasta = os.path.join(AQUI, 'improvisos')
    os.makedirs(pasta, exist_ok=True)
    for nome, (funcao, descricao) in IMPROVISOS.items():
        pos, nor = funcao(entrega)
        folha, quadros = desenhar_folha(nome, descricao, pos, nor, tris)
        folha.save(os.path.join(pasta, f'{nome}.png'))
        raster.salvar_gif(quadros + (quadros[-2:0:-1] if 'PARADO' in nome else []), os.path.join(pasta, f'{nome}.gif'), 12)
        linha = f'{nome}: {len(pos)} quadros, y de {pos[:, 2:, 1].min():.0f} a {pos[:, 2:, 1].max():.0f}'
        if args.entregar:
            pior = gravar_na_entrega(entrega, nome, descricao, pos, nor)
            linha += f' | gravado em out/ (erro de arredondamento {pior:.1f} unidades)'
        print(linha)
    if args.entregar:
        with open(os.path.join(entrega.pasta, 'model.json'), 'w', encoding='utf-8') as f:
            json.dump(entrega.m, f, ensure_ascii=False, indent=1)
        print('model.json atualizado (animações marcadas com "improviso": true)')


if __name__ == '__main__':
    sys.exit(principal())
