#!/usr/bin/env python
"""Quanto dá para encolher as animações do Crash, e quanto cada jeito estraga (pedido do C1, MGB #11).

    python -I estudo_compressao.py            escreve ESTUDO_COMPRESSAO.md e as imagens de comparação

Lê só a entrega (out/model.json + out/cru/*.bin). Tudo é medido em "passos": 1 passo = 1 unidade do byte de
posição do disco. Para o Crash, 1 passo = 6,135 unidades do contrato = 0,61% da altura dele.
Nada aqui muda a entrega; é só medição.
"""
import json
import os
import struct
import sys
import zlib

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import numpy as np                                             # noqa: E402
from PIL import Image, ImageDraw                               # noqa: E402

from crashlib import raster                                    # noqa: E402
import ver                                                     # noqa: E402

PRIORIDADE_1 = ['WILLY_STANCE1', 'WILLY_WALK', 'WILLY_DUCK', 'WILLY_FLAT', 'WILLY_BLOW', 'WILLY_SPIN_END',
                'WILLY_KILLED_1']
MORTE_COMPLETA = ['WILLY_KILLED_2', 'WILLY_KILLED_3', 'WILLY_KILLED_4']
EM_LACO = {'WILLY_BLOW'}        # só o giro volta do último quadro para o primeiro (loopseek no script)

# O que o script do Crash (WillC.gooc) realmente toca de cada animação. Ver a seção 0 do relatório.
CONJUNTO_ENXUTO = {
    'WILLY_STANCE1': [11, 12],              # 11 = a pose de descanso; 12 = piscar
    'WILLY_WALK': list(range(10)),          # meio passo; a outra metade é a mesma, espelhada
    'WILLY_DUCK': list(range(9)),           # 0 a 7 descendo, 8 = abaixado
    'WILLY_FLAT': list(range(5)),           # 0 a 4 = até ficar achatado no chão
    'WILLY_BLOW': list(range(8)),
    'WILLY_SPIN_END': list(range(6)),
    'WILLY_KILLED_1': list(range(6)),
}


def carregar(entrega, nome):
    a = next(x for x in entrega.m['animacoes'] if x['nome'] == nome)
    q, n = a['quadros'], a['vertices']
    with open(os.path.join(entrega.pasta, a['cru']['arquivo']), 'rb') as f:
        cru = f.read()
    passos = np.empty((q, n, 3), np.int32)
    normais = np.empty((q, n, 3), np.int8)
    pos = 0
    for i in range(q):
        ox, oy, oz, _ = struct.unpack_from('<3hH', cru, pos)
        bloco = np.frombuffer(cru, np.uint8, n * 6, pos + 8).reshape(n, 6)
        passos[i] = bloco[:, :3].astype(np.int32) + np.array([ox, oy, oz])
        normais[i] = bloco[:, 3:].view(np.int8)
        pos += 8 + n * 6
    return a, passos, normais


# ---------------------------------------------------------------------------------------------- os métodos
def metade_com_interpolacao(p, passo, em_laco):
    """Guarda 1 quadro a cada `passo` e interpola os outros em linha reta."""
    q = len(p)
    chaves = list(range(0, q, passo))
    if not em_laco and chaves[-1] != q - 1:
        chaves.append(q - 1)                         # animação que para no fim precisa do último quadro exato
    rec = np.empty_like(p, dtype=np.float64)
    for i in range(q):
        antes = max(k for k in chaves if k <= i)
        depois = [k for k in chaves if k > i]
        if depois:
            prox, dist = depois[0], depois[0] - antes
        elif em_laco:
            prox, dist = 0, q - antes
        else:
            prox, dist = antes, 1
        t = (i - antes) / dist
        rec[i] = p[antes] * (1 - t) + p[prox] * t
    return np.round(rec).astype(np.int32), len(chaves)


def metade_sem_interpolacao(p, passo):
    """Guarda 1 quadro a cada `passo` e repete (a animação roda a 15 quadros por segundo)."""
    q = len(p)
    rec = np.stack([p[(i // passo) * passo] for i in range(q)])
    return rec, (q + passo - 1) // passo


def delta_4_bits(p, escala_por_quadro):
    """1º quadro inteiro; depois, por componente, a diferença para o quadro reconstruído anterior em 4 bits.

    escala_por_quadro=False: diferença pura, de -8 a +7 passos; o que passar disso fica para trás (atraso).
    escala_por_quadro=True: cada quadro escolhe um deslocamento s e guarda diferença / 2^s (erro até 2^(s-1)).
    """
    rec = np.empty_like(p)
    rec[0] = p[0]
    escalas = [0]
    for i in range(1, len(p)):
        d = p[i] - rec[i - 1]
        melhor = None
        for s in (range(0, 6) if escala_por_quadro else (0,)):
            cod = np.clip(np.round(d / (1 << s)), -8, 7).astype(np.int32)
            cand = rec[i - 1] + cod * (1 << s)
            erro = int(np.abs(cand - p[i]).max())
            if melhor is None or erro < melhor[0]:
                melhor = (erro, s, cand)
        rec[i] = melhor[2]
        escalas.append(melhor[1])
    return rec, escalas


def delta_sem_perda(p):
    """Diferenças entre quadros: quantos bytes dá com zlib, e com 4 bits + escape (um decodificador de 20 linhas)."""
    d = np.diff(p, axis=0)
    fora = int(((d < -7) | (d > 7)).sum())                          # o código -8 vira "escape": segue 1 byte inteiro
    n_comp = d.size
    escape = p[0].size + (n_comp + 1) // 2 + fora
    bruto = np.clip(p - p.min(), 0, 255).astype(np.uint8).tobytes()
    dz = len(zlib.compress(np.clip(d, -128, 127).astype(np.int8).tobytes(), 9)) + p[0].size
    return escape, dz, len(zlib.compress(bruto, 9)), fora / n_comp


def menos_bits(p, bits):
    """Posição com menos bits: joga fora os (8 - bits) bits de baixo de cada componente."""
    passo = 1 << (8 - bits)
    base = p.min(axis=(0, 1))
    return ((p - base + passo // 2) // passo) * passo + base


def seis_bits_mais_delta(p, bits=6):
    """Primeiro arredonda cada coordenada para `bits` bits (erro fixo e pequeno); depois guarda as diferenças
    entre quadros em 4 bits com escape. Depois do arredondamento não se perde mais nada."""
    passo = 1 << (8 - bits)
    base = p.min(axis=(0, 1))
    q = (p - base + passo // 2) // passo
    rec = q * passo + base
    d = np.diff(q, axis=0)
    fora = int(((d < -7) | (d > 7)).sum())
    n_bytes = (q[0].size * bits + 7) // 8 + (d.size + 1) // 2 + fora + 3
    return rec, n_bytes


def pca(lista, r):
    """Todas as animações de um modelo como média + r poses-base (cada quadro vira r números)."""
    x = np.concatenate([p.reshape(len(p), -1) for p in lista]).astype(np.float64)
    media = x.mean(0)
    u, s, vt = np.linalg.svd(x - media, full_matrices=False)
    rec = media + (u[:, :r] * s[:r]) @ vt[:r]
    return float(np.abs(np.round(rec) - x).max()), float(np.sqrt(((rec - x) ** 2).mean()))


# ------------------------------------------------------------------------------------------------ relatório
def principal():
    sys.stdout.reconfigure(encoding='utf-8')
    entrega = ver.Entrega(os.path.join(AQUI, 'out'))
    k = next(x for x in entrega.m['animacoes'] if x['nome'] == 'WILLY_STANCE1')['cru']['k'][0]
    dados = {nome: carregar(entrega, nome) for nome in PRIORIDADE_1 + MORTE_COMPLETA}
    L = ['# Estudo: quanto dá para encolher as animações do Crash', '',
         'Pedido do C1 (MGB #11): no PS1 sobram uns 26 KB + 65 KB, e a prioridade 1 em 3 bytes por vértice dá ~87 KB.',
         'Gerado por `estudo_compressao.py`, lendo só a entrega (`out/cru/`). Nada aqui muda a entrega.', '',
         f'**Unidade: passo.** 1 passo = 1 unidade do byte de posição do disco = {k:.3f} unidades do contrato = '
         f'{k / 10:.2f}% da altura do Crash.',
         'Na foto da F1 o Crash tem uns 45 pixels de altura na tela do MGS, então **1 passo é menos de um terço de '
         'pixel**, e um erro de 3 passos é 1 pixel. Num close em que ele ocupe 150 pixels, 1 passo vira 1 pixel.', '']

    L += ['## 0. Antes de comprimir: o que o jogo do Crash realmente toca', '',
          'Lido no script dele (`repos/goocdump/Crash 1/NTSC-J/WillC.gooc`). Isto economiza mais que qualquer compressão:', '',
          '- **`WILLY_WALK` é só MEIO passo.** O jogo toca os quadros 0 a 9 normais e depois os mesmos 0 a 9 '
          '**espelhados** (`playanim_nm` e depois `playanim_m`, que inverte a escala em X). O Crash é simétrico, então '
          'a perna esquerda é a direita no espelho. Para o C1: correr = 0..9 com X normal, 0..9 com X negado (e o '
          'sentido dos triângulos invertido junto). **Não dá para interpolar do quadro 9 para o 0**: são malhas espelhadas.',
          '- **`WILLY_STANCE1` não é um laço de 13 quadros.** A pose de descanso é o **quadro 11**, parado. De vez em '
          'quando ele pisca: 12, 11, 12, 11 (0,1 s cada). Os quadros 0 a 10 são ele olhando em volta e virando para o '
          'outro lado (o script espelha o X antes), com o quadro 5 parado por 1 s. O parado básico são **2 quadros**.',
          '- **`WILLY_DUCK`**: 0 a 7 descendo, 8 parado por 1 s, e 9 a 13 em vaivém enquanto continua abaixado.',
          '- **`WILLY_FLAT`**: 0 a 3 caindo, **4 parado por 1,3 s (achatado no chão)**, 5 a 12 descolando como papel. '
          'Para rastejar basta 0 a 4.',
          '- **`WILLY_BLOW`**: laço de 0 a 7. É o único que volta do último quadro para o primeiro.', '']

    # 1. quanto as coisas se mexem
    L += ['## 1. O que há para comprimir', '',
          '| Animação | Quadros | Vértices | 3 B/vért. | Maior salto entre quadros | Diferenças que cabem em 4 bits (-7 a +7) |',
          '|---|---|---|---|---|---|']
    tot3 = 0
    for nome in PRIORIDADE_1 + MORTE_COMPLETA:
        a, p, _ = dados[nome]
        d = np.abs(np.diff(p, axis=0))
        b3 = p.size
        tot3 += b3 if nome in PRIORIDADE_1 else 0
        L.append(f'| `{nome}` | {len(p)} | {p.shape[1]} | {b3:,} | {int(d.max())} passos | {100 * (d <= 7).mean():.1f}% |'.replace(',', '.'))
    L += ['', f'Prioridade 1 em 3 bytes por vértice: **{tot3:,} bytes**.'.replace(',', '.'), '']

    # 2. tabela de métodos
    L += ['## 2. Cada jeito de encolher: bytes e pior erro (em passos)', '',
          'Cada célula é `bytes / pior erro`. Erro 0 = idêntico ao disco.', '',
          '| Animação | A. metade dos quadros, repetindo | B. metade + interpolação | C. um terço + interpolação | '
          'D. diferença 4 bits pura | E. diferença 4 bits com escala | F. B + E juntos | G. 4 bits + escape (sem perda) | '
          'H. zlib nas diferenças (sem perda) |', '|---|---|---|---|---|---|---|---|---|']
    soma = {c: [0, 0] for c in 'ABCDEFGH'}
    piores = {}
    for nome in PRIORIDADE_1 + MORTE_COMPLETA:
        a, p, _ = dados[nome]
        q, n = p.shape[0], p.shape[1]
        laco = nome in EM_LACO
        celulas = {}
        ra, ka = metade_sem_interpolacao(p, 2)
        celulas['A'] = (ka * n * 3, int(np.abs(ra - p).max()), ra)
        rb, kb = metade_com_interpolacao(p, 2, laco)
        celulas['B'] = (kb * n * 3, int(np.abs(rb - p).max()), rb)
        rc, kc = metade_com_interpolacao(p, 3, laco)
        celulas['C'] = (kc * n * 3, int(np.abs(rc - p).max()), rc)
        rd, _ = delta_4_bits(p, False)
        celulas['D'] = (n * 3 + (q - 1) * (n * 3 + 1) // 2, int(np.abs(rd - p).max()), rd)
        re_, esc = delta_4_bits(p, True)
        celulas['E'] = (n * 3 + (q - 1) * ((n * 3 + 1) // 2 + 1), int(np.abs(re_ - p).max()), re_)
        # F: metade dos quadros, e as chaves em diferença de 4 bits com escala; o resto interpolado
        chaves = list(range(0, q, 2))
        if not laco and chaves[-1] != q - 1:
            chaves.append(q - 1)
        rk, _ = delta_4_bits(p[chaves], True)
        cheio = np.empty_like(p)
        for i in range(q):
            antes = max(j for j, c in enumerate(chaves) if c <= i)
            if chaves[antes] == i:
                cheio[i] = rk[antes]
            else:
                depois = antes + 1 if antes + 1 < len(chaves) else (0 if laco else antes)
                dist = (chaves[depois] - chaves[antes]) if depois > antes else (q - chaves[antes])
                t = (i - chaves[antes]) / max(dist, 1)
                cheio[i] = np.round(rk[antes] * (1 - t) + rk[depois] * t)
        celulas['F'] = (n * 3 + (len(chaves) - 1) * ((n * 3 + 1) // 2 + 1), int(np.abs(cheio - p).max()), cheio)
        esc_b, dz, _bz, _fr = delta_sem_perda(p)
        celulas['G'] = (esc_b, 0, p)
        celulas['H'] = (dz, 0, p)
        piores[nome] = celulas
        linha = f'| `{nome}` |'
        for c in 'ABCDEFGH':
            b, e, _ = celulas[c]
            linha += f' {b:,} / {e} |'.replace(',', '.')
            if nome in PRIORIDADE_1:
                soma[c][0] += b
                soma[c][1] = max(soma[c][1], e)
        L.append(linha)
    linha = '| **prioridade 1, total** |'
    for c in 'ABCDEFGH':
        linha += f' **{soma[c][0]:,}** / {soma[c][1]} |'.replace(',', '.')
    L += [linha, '',
          'Como ler o erro de A: é o quanto o quadro repetido difere do quadro certo, ou seja, o tranco de rodar a 15 '
          'quadros por segundo; não é deformação. Em B e C o erro é deformação de verdade no quadro interpolado.',
          'Em D (4 bits sem escala) o erro é atraso: o vértice que anda mais de 7 passos num quadro fica para trás.', '']

    # 3. menos bits por coordenada
    L += ['## 3. Menos bits por coordenada (em vez de mexer no tempo)', '',
          '| Bits por coordenada | Bytes por vértice por quadro | Pior erro | Prioridade 1 |', '|---|---|---|---|']
    for bits in (8, 7, 6, 5):
        erro = max(int(np.abs(menos_bits(dados[nm][1], bits) - dados[nm][1]).max()) for nm in PRIORIDADE_1)
        tot = sum((dados[nm][1].size * bits + 7) // 8 for nm in PRIORIDADE_1)
        L.append(f'| {bits} | {3 * bits / 8:.2f} | {erro} passos | {tot:,} |'.replace(',', '.'))
    L += ['', 'Com 5 bits cada coordenada tem 32 posições: 5 + 5 + 5 = 15 bits, **2 bytes por vértice**, sem decodificar nada '
          '(é um `>>` e um `&`).', '']

    # 4. poses-base
    L += ['## 4. Poses-base (todas as animações do `WillG` como média + r poses; cada quadro vira r números)', '',
          '| r | Bytes (média e poses em int8, mais os números por quadro) | Pior erro | Erro médio |', '|---|---|---|---|']
    do_willg = [dados[nm][1] for nm in PRIORIDADE_1 if nm != 'WILLY_BLOW']
    n_quadros = sum(len(p) for p in do_willg)
    n = do_willg[0].shape[1]
    for r in (4, 8, 12, 16, 24):
        pior, medio = pca(do_willg, r)
        L.append(f'| {r} | {(r + 1) * n * 3 + n_quadros * r * 2:,} | {pior:.0f} passos | {medio:.2f} |'.replace(',', '.'))
    L += ['', f'({n_quadros} quadros do `WillG`; o `BLOW` fica de fora porque é outro modelo.) Custa caro no PS1: r '
          'multiplicações por coordenada por quadro. Só vale se o resto não couber.', '']

    # 5. o conjunto enxuto
    L += ['## 5. O conjunto enxuto (seção 0) com cada jeito de guardar', '',
          '| Animação | Quadros usados | 3 B/vért. | 6 bits por coordenada (erro até 2) | 5+5+5 bits = 2 B/vért. (erro até 4) | '
          'E. diferença 4 bits com escala | **6 bits + diferença 4 bits com escape** |', '|---|---|---|---|---|---|---|']
    tot = [0, 0, 0, 0, 0]
    err = [0, 0, 0, 0, 0]
    for nome, quais in CONJUNTO_ENXUTO.items():
        _, p_todo, _ = dados[nome]
        p = p_todo[quais]
        q, n = p.shape[0], p.shape[1]
        b3 = p.size
        b6 = (p.size * 6 + 7) // 8
        e6 = int(np.abs(menos_bits(p, 6) - p).max())
        b5 = q * n * 2
        e5 = int(np.abs(menos_bits(p, 5) - p).max())
        re_, _ = delta_4_bits(p, True)
        be = n * 3 + (q - 1) * ((n * 3 + 1) // 2 + 1)
        ee = int(np.abs(re_ - p).max())
        rq, bq = seis_bits_mais_delta(p, 6)
        eq = int(np.abs(rq - p).max())
        for i, (b, e) in enumerate(((b3, 0), (b6, e6), (b5, e5), (be, ee), (bq, eq))):
            tot[i] += b
            err[i] = max(err[i], e)
        faixa = f'{quais[0]} a {quais[-1]}' if len(quais) > 2 else ' e '.join(map(str, quais))
        L.append(f'| `{nome}` | {faixa} ({q}) | {b3:,} | {b6:,} / {e6} | {b5:,} / {e5} | {be:,} / {ee} | **{bq:,}** / {eq} |'.replace(',', '.'))
    L.append('| **total** | | ' + ' | '.join(f'**{t:,}** / {e}'.replace(',', '.') for t, e in zip(tot, err)) + ' |')
    L += ['', 'Somar a isto, uma vez só: os triângulos e materiais dos dois modelos e as normais do 1º quadro (que o C1 já usa).', '']

    with open(os.path.join(AQUI, 'ESTUDO_COMPRESSAO.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')

    # imagens: original x métodos, no pior quadro de cada um, em tamanho grande e no tamanho da tela do MGS
    os.makedirs(os.path.join(AQUI, 'estudo'), exist_ok=True)
    for nome in ('WILLY_WALK', 'WILLY_KILLED_1', 'WILLY_FLAT'):
        a, p, nor = dados[nome]
        tris = entrega.triangulos(a['modelo'])
        kk = np.array(a['cru']['k'])
        chao = a['cru']['chao']

        def contrato(x):
            v = x.astype(np.float64) * kk
            v[:, 1] -= chao
            return v
        todos = contrato(p.reshape(-1, 3))
        centro = (todos.min(0) + todos.max(0)) / 2
        raio = float(np.linalg.norm(todos - centro, axis=1).max())
        colunas = [('original', p)] + [(f'{c}: erro {piores[nome][c][1]}', piores[nome][c][2]) for c in 'ABDEF']
        pior_quadro = int(np.argmax([np.abs(piores[nome]['B'][2][i] - p[i]).max() for i in range(len(p))]))
        grandes, pequenos = [], []
        for _, rec in colunas:
            img = raster.desenhar(contrato(rec[pior_quadro]), nor[pior_quadro].astype(np.float64), tris, 220, 35, 10, (centro, raio))
            grandes.append(img)
            mini = raster.desenhar(contrato(rec[pior_quadro]), nor[pior_quadro].astype(np.float64), tris, 56, 35, 10, (centro, raio), amostras=1)
            pequenos.append(mini.resize((220, 220), Image.NEAREST))
        folha = Image.new('RGBA', (220 * len(colunas), 480), (24, 24, 32, 255))
        d = ImageDraw.Draw(folha)
        d.text((4, 2), f'{nome}, quadro {pior_quadro} (o pior da interpolação). Em cima: grande. Embaixo: no tamanho '
               'da tela do MGS (56 px), ampliado.', fill=(255, 255, 255, 255))
        for i, (titulo, _) in enumerate(colunas):
            folha.alpha_composite(grandes[i], (i * 220, 20))
            folha.alpha_composite(pequenos[i], (i * 220, 250))
            d.text((i * 220 + 4, 236), titulo, fill=(255, 220, 120, 255))
        folha.save(os.path.join(AQUI, 'estudo', f'comparacao_{nome}.png'))
    print('\n'.join(L))


if __name__ == '__main__':
    principal()
