#!/usr/bin/env python
"""Olha de perto o que o extrair.py entregou: lê SÓ a saída (model.json + anim_*.bin + tex/), não o disco.

    python -I ver.py WILLY_STANCE1 --quadro 0 --guinadas 0,90,180,270 --tamanho 320 --saida vista.png
    python -I ver.py WILLY_WALK --todos --guinadas 0 --saida correr.png

Serve de prova de que a entrega se basta: se esta imagem sai certa, o Claude 1 tem tudo de que precisa nos
arquivos, sem depender de nada que ficou na memória do extrator.
"""
import argparse
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import numpy as np                                             # noqa: E402
from PIL import Image                                          # noqa: E402

from crashlib import formatos as fmt                           # noqa: E402
from crashlib import raster                                    # noqa: E402


class Entrega:
    def __init__(self, pasta):
        self.pasta = pasta
        with open(os.path.join(pasta, 'model.json'), encoding='utf-8') as f:
            self.m = json.load(f)
        self._atlas = {}

    def animacao(self, nome):
        a = next((x for x in self.m['animacoes'] if x['nome'] == nome and 'arquivo' in x), None)
        if a is None:
            raise SystemExit(f'{nome}: não está na entrega')
        q, n = a['quadros'], a['vertices']
        with open(os.path.join(self.pasta, a['arquivo']), 'rb') as f:
            dados = f.read()
        pos = np.frombuffer(dados, '<i2', q * n * 3).reshape(q, n, 3).astype(np.float64)
        nor = np.frombuffer(dados, np.int8, q * n * 3, q * n * 6).reshape(q, n, 3).astype(np.float64)
        return a, pos, nor

    def regiao_rgba(self, rid):
        """Monta a imagem de uma região a partir do atlas cru + a paleta do json (o caminho que o PS1 fará)."""
        if rid not in self._atlas:
            t = self.m['texturas']
            r = t['regioes'][rid]
            info = t['atlas'][r['atlas']]
            with open(os.path.join(self.pasta, 'tex', r['atlas'] + '.bin'), 'rb') as f:
                cru = np.frombuffer(f.read(), np.uint8)
            larg = info['largura_px']
            if r['bits'] == 4:
                linhas = cru.reshape(-1, larg // 2)
                idx = np.empty((linhas.shape[0], larg), np.uint8)
                idx[:, 0::2] = linhas & 0xF
                idx[:, 1::2] = linhas >> 4
            else:
                idx = cru.reshape(-1, larg)
            pal = np.array([fmt.cor_ps1(int(c, 16)) for c in t['cluts'][r['clut']]['cores_ps1']], np.uint8)
            self._atlas[rid] = pal[idx[r['y']:r['y'] + r['a'], r['x']:r['x'] + r['l']]]
        return self._atlas[rid]

    def triangulos(self, nome_modelo):
        mod = self.m['modelos'][nome_modelo]
        saida = []
        for a, b, c, mi in mod['triangulos']:
            mat = mod['materiais'][mi]
            t = {'v': (a, b, c), 'rgb': mat['rgb'], 'liso': mat['liso'],
                 'mistura': None if mat['modo_de_mistura'] == 3 else mat['modo_de_mistura']}
            if mat['textura'] is not None:
                t['textura'] = self.regiao_rgba(mat['textura'])
                t['uvs'] = mat['uv']
            saida.append(t)
        return saida


def principal():
    ap = argparse.ArgumentParser()
    ap.add_argument('animacao')
    ap.add_argument('--entrega', default=os.path.join(AQUI, 'out'))
    ap.add_argument('--quadro', type=int, default=0)
    ap.add_argument('--todos', action='store_true', help='todos os quadros (um por coluna)')
    ap.add_argument('--passo', type=int, default=1, help='com --todos: pula quadros')
    ap.add_argument('--guinadas', default='0,90,180,270')
    ap.add_argument('--inclinacao', type=float, default=10)
    ap.add_argument('--tamanho', type=int, default=256)
    ap.add_argument('--saida', required=True)
    args = ap.parse_args()
    e = Entrega(args.entrega)
    a, pos, nor = e.animacao(args.animacao)
    tris = e.triangulos(a['modelo'])
    centro = (pos.reshape(-1, 3).min(0) + pos.reshape(-1, 3).max(0)) / 2
    raio = float(np.linalg.norm(pos.reshape(-1, 3) - centro, axis=1).max())
    quadros = range(0, a['quadros'], args.passo) if args.todos else [args.quadro]
    guinadas = [float(g) for g in args.guinadas.split(',')]
    imagens = [raster.desenhar(pos[q], nor[q], tris, args.tamanho, g, args.inclinacao, (centro, raio))
               for g in guinadas for q in quadros]
    folha = raster.folha_de_contato(imagens, len(list(quadros)) if args.todos else len(guinadas),
                                    legenda=f'{args.animacao}  guinadas {args.guinadas}  (lido só da entrega)')
    folha.save(args.saida)
    print(f'{args.saida}: {folha.size[0]}x{folha.size[1]}; caixa do quadro 0: '
          f'{np.round(pos[0].min(0)).tolist()} a {np.round(pos[0].max(0)).tolist()}')


if __name__ == '__main__':
    sys.exit(principal())
