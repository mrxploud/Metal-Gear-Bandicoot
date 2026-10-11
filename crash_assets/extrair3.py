#!/usr/bin/env python3
"""Tira o Crash do disco do CRASH BANDICOOT 3 (Warped) e entrega para o lado MGS.

    python -I extrair3.py --disco "<Crash Bandicoot 3 ... .cue>"
    python -I extrair3.py --disco <...> --sem-previas        só os dados (segundos)
    python -I extrair3.py --disco <...> --so Cr10V,CCw1V     só estas animações (para testar)

Sai em out_c3/ no MESMO contrato da entrega do Crash 1 (MGB_board, v1.1), com os acréscimos que o formato do
Crash 3 pede (v1.2, combinados em MGB #25/#26):
  - cor por canto de triângulo (`cores` + `cores_dos_cantos`), sem normais (`"normais": false`);
  - por animação: quadros-chave no disco, quantos quadros o script toca e se interpola;
  - k por eixo (a escala do modelo do Crash 3 não é igual em x, y e z);
  - `comprimido/`: os quadros como estão no disco, para quem quiser portar o decodificador.

Formatos: CrashEdit (CBHacks). Nomes das animações: nossos (nomes_c3.json). Créditos em ../CREDITOS.md.
"""
import argparse
import json
import os
import struct
import sys
import time

import numpy as np
from PIL import Image

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

from crashlib import banco3, nsf, raster                      # noqa: E402
from crashlib import formatos as fmt                          # noqa: E402
from crashlib.disco import Disco                              # noqa: E402

ALTURA_ALVO = 1000.0
REFERENCIA = ('Cr10V', 'Cr10G', 0)        # animação, modelo, quadro: o Crash parado mede 1000
FPS = 30                                  # quadros TOCADOS por segundo (as chaves no disco estão a 15)
SERIAIS = {'SCES_014.20': 'Crash Bandicoot 3: Warped (Europa/Austrália, PAL)',
           'SCUS_942.44': 'Crash Bandicoot: Warped (EUA)', 'SCPS_100.73': 'Crash Bandicoot 3 (Japão)'}

# script GOOL -> grupo. O grupo do Crash depende do modelo (ver grupo_de).
SCRIPTS = [('WillC', None), ('BoxsC', 'caixas'), ('DoctC', 'aku'), ('ShadC', 'sombra'), ('FruiC', 'frutas'),
           ('PartC', 'particulas')]
MODELOS_DO_GIRO = {'WiBlG', 'WiBcG'}
MODELOS_DE_MORTE = {'Cda0G', 'WF10G', 'CE10G'}
MODELOS_DA_BAZUCA = {'Cgt0G', 'Cgb0G'}    # o Crash cortado ao meio: tronco com a bazuca + pernas


def diga(*a):
    print(*a, flush=True)


if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')          # o console do Windows é cp1252 e quebra os acentos


def grupo_de(script, grupo, modelo):
    if modelo in MODELOS_DA_BAZUCA:
        return 'bazuca'
    if grupo:
        return grupo
    if modelo == REFERENCIA[1]:
        return 'crash'
    if modelo in MODELOS_DO_GIRO:
        return 'giro'
    if modelo in MODELOS_DE_MORTE:
        return 'mortes'
    return 'crash_outros'                  # mergulho, moto, jet ski, avião, cenas: modelos próprios


# ------------------------------------------------------------------------------------------------------
# Geometria: dos bytes do quadro para o espaço do contrato
# ------------------------------------------------------------------------------------------------------
class Conversao:
    """pos = (byte + origem / 32) * 8 * escala_tgeo * fator. Pés em y = 0, Y para cima, frente +Z."""

    def __init__(self):
        self.fator = 1.0

    def calibrar(self, banco):
        anim, modelo, quadro = REFERENCIA
        g = banco.tgeo(modelo)
        p = self.cru(banco.svtx(anim).quadros[quadro], g)
        self.fator = ALTURA_ALVO / float(p[:, 1].max() - p[:, 1].min())
        self.chao_da_referencia = float(p[:, 1].min()) * self.fator
        return self.fator

    @staticmethod
    def cru(quadro, tgeo):
        return np.array(quadro.posicoes(tgeo), np.float64) * np.array(tgeo.escala, np.float64)

    def posicoes(self, quadro, tgeo):
        return self.cru(quadro, tgeo) * self.fator

    def ponto_de_bytes(self, b, quadro, tgeo):
        o = np.array(quadro.origem, np.float64) / 4.0
        return ((np.array(b, np.float64) * 8.0 + o) * np.array(tgeo.escala, np.float64) * self.fator).round(1).tolist()

    def k(self, tgeo):
        return [8.0 * e * self.fator for e in tgeo.escala]

    def descricao(self):
        return {
            'formula': 'pos = (byte * 8 + origem_do_quadro / 4) * escala_tgeo * fator   (por eixo)',
            'no_cru': 'pos = (o + byte) * k,  com o = origem / 32 (sempre inteiro) e k = 8 * escala_tgeo * fator. '
                      'ATENÇÃO: k é diferente em x, y e z (no Crash 1 era um só).',
            'fonte': 'CrashEdit: Frame.MakeVertices (verts *= 8 no Crash 3) + AnimationRenderer.RenderFrame '
                     '((v + offset / 4) * scale)',
            'ordem_dos_eixos': [0, 1, 2], 'sinais': [1, 1, 1], 'chao': 0.0, 'escala_original': self.fator,
            'altura_do_crash_parado': ALTURA_ALVO, 'referencia': f'{REFERENCIA[0]} quadro {REFERENCIA[2]} ({REFERENCIA[1]})',
            'nota': 'y = 0 é o chão do próprio jogo (a origem do quadro). Parado, o ponto mais baixo fica em 0; '
                    'correndo e engatinhando a sola desce até ~5% da altura abaixo de 0 em alguns quadros. '
                    'Sem trocar nem inverter eixo nenhum o Crash sai de frente para +Z.',
        }


# ------------------------------------------------------------------------------------------------------
# Texturas: páginas originais + atlas compacto (igual à entrega do Crash 1)
# ------------------------------------------------------------------------------------------------------
class Texturas:
    def __init__(self, banco):
        self.banco = banco
        self.paginas = banco3.Paginas(banco)
        self.usadas = {}             # nome da página -> bytes
        self.regioes = {}            # (pagina, modo, clut_x, clut_y, x, y, l, a) -> id

    def registrar(self, tgeo, tex):
        """Devolve (id da região, [(u, v)] * 3 relativos ao retângulo, imagem da página) ou (None, None, None)."""
        if tex.pagina >= len(tgeo.paginas):
            return None, None, None
        nome = nsf.nome_do_eid(tgeo.paginas[tex.pagina])
        dados = self.paginas.dados(nome)
        if dados is None:
            return None, None, None
        self.usadas[nome] = dados
        uv = tex.uvs()
        x0, y0 = min(p[0] for p in uv), min(p[1] for p in uv)
        larg = max(p[0] for p in uv) - x0 + 1
        alt = max(p[1] for p in uv) - y0 + 1
        chave = (nome, tex.modo_de_cor, tex.clut_x, tex.clut_y, x0, y0, larg, alt)
        if chave not in self.regioes:
            self.regioes[chave] = len(self.regioes)
        img = self.paginas.imagem(nome, tex.modo_de_cor, tex.clut_x, tex.clut_y)
        return self.regioes[chave], [(u - x0, v - y0) for u, v in uv], img

    def registrar_retangulo(self, nome, modo, clut_x, clut_y, x0, y0, larg, alt):
        """Para sprites: um retângulo inteiro da página. Devolve (id da região, imagem RGBA do recorte) ou (None, None)."""
        dados = self.paginas.dados(nome)
        if dados is None:
            return None, None
        self.usadas[nome] = dados
        chave = (nome, modo, clut_x, clut_y, x0, y0, larg, alt)
        if chave not in self.regioes:
            self.regioes[chave] = len(self.regioes)
        img = self.paginas.imagem(nome, modo, clut_x, clut_y)
        return self.regioes[chave], img[y0:y0 + alt, x0:x0 + larg]

    def exportar(self, pasta):
        os.makedirs(pasta, exist_ok=True)
        for nome, dados in self.usadas.items():
            with open(os.path.join(pasta, f'pagina_{nome}.bin'), 'wb') as f:
                f.write(dados)
        cluts, lista_cluts = {}, []
        for (nome, modo, cx, cy, *_r) in self.regioes:
            if modo < 2 and (nome, modo, cx, cy) not in cluts:
                cluts[(nome, modo, cx, cy)] = len(lista_cluts)
                lista_cluts.append({'id': len(lista_cluts), 'pagina': nome, 'bits': (4, 8)[modo], 'clut_x': cx,
                                    'clut_y': cy,
                                    'cores_ps1': [f'{p:04x}' for p in fmt.paleta(self.usadas[nome], cx, cy, modo)]})
        regioes, atlas = [None] * len(self.regioes), {}
        for bits, modo, larg_atlas in ((4, 0, 256), (8, 1, 256), (16, 2, 128)):
            itens = sorted((k for k in self.regioes if k[1] == modo), key=lambda k: (-k[7], -k[6]))
            if not itens:
                continue
            x = y = prateleira = 0
            vagas = []
            for k in itens:
                l, a = k[6], k[7]
                if x + l > larg_atlas:
                    x, y, prateleira = 0, y + prateleira, 0
                vagas.append((k, x, y))
                x += l
                prateleira = max(prateleira, a)
            alt_atlas = y + prateleira
            indices = np.zeros((alt_atlas, larg_atlas), np.uint16)
            previa = np.zeros((alt_atlas, larg_atlas, 4), np.uint8)
            for k, ax, ay in vagas:
                nome, _, cx, cy, x0, y0, l, a = k
                dados = self.usadas[nome]
                for yy in range(a):
                    for xx in range(l):
                        indices[ay + yy, ax + xx] = fmt.indice_do_pixel(dados, x0 + xx, y0 + yy, modo)
                img = self.paginas.imagem(nome, modo, cx, cy)
                if img is not None:
                    previa[ay:ay + a, ax:ax + l] = img[y0:y0 + a, x0:x0 + l]
                regioes[self.regioes[k]] = {
                    'id': self.regioes[k], 'bits': bits, 'atlas': f'atlas_{bits}bits', 'x': ax, 'y': ay, 'l': l, 'a': a,
                    'clut': cluts.get((nome, modo, cx, cy)), 'origem': {'pagina': nome, 'x': x0, 'y': y0}}
            Image.fromarray(previa, 'RGBA').save(os.path.join(pasta, f'atlas_{bits}bits.png'))
            if bits == 4:
                cru = (indices[:, 0::2] | (indices[:, 1::2] << 4)).astype(np.uint8).tobytes()
            elif bits == 8:
                cru = indices.astype(np.uint8).tobytes()
            else:
                cru = indices.astype('<u2').tobytes()
            with open(os.path.join(pasta, f'atlas_{bits}bits.bin'), 'wb') as f:
                f.write(cru)
            atlas[f'atlas_{bits}bits'] = {
                'bits': bits, 'largura_px': larg_atlas, 'altura_px': alt_atlas,
                'largura_vram': larg_atlas * bits // 16, 'bytes': len(cru),
                'formato': 'índices de paleta linha a linha, como na VRAM do PS1' if bits < 16 else 'cores de 15 bits'}
        return {'atlas': atlas, 'regioes': regioes, 'cluts': lista_cluts, 'paginas_originais': sorted(self.usadas)}, cluts


class Modelo:
    """Um TGEO do Crash 3 no formato do contrato. O sentido dos triângulos é o da entrega do Crash 1
    (horário visto de fora): a ordem do CrashEdit é a contrária, então trocamos o 2º com o 3º canto."""

    def __init__(self, tgeo, texturas, face=0):
        self.tgeo = tgeo
        self.n = tgeo.n_vertices - tgeo.n_especiais
        self.materiais, indice = [], {}
        self.triangulos, self.cantos, self.para_desenhar = [], [], []
        self.regioes, self.animados = set(), 0
        ordem = (0, 2, 1)
        for t in tgeo.triangulos:
            v = tuple(t['v'][i] for i in ordem)
            cores = tuple(t['cor'][i] for i in ordem)
            tex = tgeo.textura_do_triangulo(t, face)
            regiao = uvs = img = None
            if tex is not None:
                regiao, uv_rel, img = texturas.registrar(tgeo, tex)
                if regiao is not None:
                    por_canto = [uv_rel[k] for k in t['cantos']]          # canto de textura de cada vértice
                    uvs = [list(por_canto[i]) for i in ordem]
                    self.regioes.add(regiao)
            mistura = tex.mistura if (tex is not None and regiao is not None) else 3
            chave = (regiao, tuple(map(tuple, uvs)) if uvs else None, mistura, t['sem_descarte'])
            if chave not in indice:
                indice[chave] = len(self.materiais)
                self.materiais.append({
                    'rgb': [128, 128, 128], 'liso': True, 'textura': regiao, 'uv': uvs, 'clut': None,
                    'modo_de_mistura': mistura, 'bits': tex.bits_por_pixel() if regiao is not None else 0,
                    'sem_descarte_de_costas': bool(t['sem_descarte']), 'chave_clut': None})
                if regiao is not None:
                    self.materiais[-1]['chave_clut'] = (nsf.nome_do_eid(tgeo.paginas[tex.pagina]), tex.modo_de_cor,
                                                        tex.clut_x, tex.clut_y)
            if t['animada']:
                self.animados += 1
            self.triangulos.append([v[0], v[1], v[2], indice[chave]])
            self.cantos.append(list(cores))
            d = {'v': v, 'mistura': None if mistura == 3 else mistura}
            rgb = [tgeo.cores[i][:3] for i in cores]
            if img is not None:
                uvp = tex.uvs()
                por_canto = [uvp[k] for k in t['cantos']]
                d['textura'] = img
                d['uvs'] = [(por_canto[i][0] + 0.5, por_canto[i][1] + 0.5) for i in ordem]
                d['rgbs'] = rgb
            else:
                d['rgbs'] = [tuple(min(255, c * 2) for c in cor) for cor in rgb]
            self.para_desenhar.append(d)

    def json(self, grupo, cluts, regioes_json, arquivo):
        mats = []
        for m in self.materiais:
            m = dict(m)
            chave = m.pop('chave_clut')
            m['clut'] = cluts.get(chave) if chave else None
            mats.append(m)
        usados = {i for t in self.triangulos for i in t[:3]}
        regs = sorted(self.regioes)
        g = self.tgeo
        return {
            'grupo': grupo, 'vertices': self.n, 'vertices_especiais': g.n_especiais,
            'vertices_soltos': sorted(set(range(self.n)) - usados),
            'triangulos': self.triangulos, 'cores_dos_cantos': self.cantos,
            'cores': [list(c[:3]) for c in g.cores], 'materiais': mats,
            'escala_tgeo': list(g.escala), 'n_triangulos': len(self.triangulos),
            'n_texturizados': sum(1 for t in self.triangulos if self.materiais[t[3]]['textura'] is not None),
            'n_semitransparentes': sum(1 for t in self.triangulos if self.materiais[t[3]]['modo_de_mistura'] != 3),
            'n_sem_descarte': sum(1 for t in self.triangulos if self.materiais[t[3]]['sem_descarte_de_costas']),
            'n_textura_animada': self.animados,
            'comprimido': ({'bases': f'comprimido/{arquivo}.bases.bin', 'bits_por_quadro': g.bits_por_quadro(),
                            'bytes_da_fila': (g.bits_por_quadro() + 31) // 32 * 4} if g.comprimido else None),
            'texturas_do_modelo': {
                'regioes': regs, 'cluts': sorted({regioes_json[r]['clut'] for r in regs if regioes_json[r]['clut'] is not None}),
                'area_px': sum(regioes_json[r]['l'] * regioes_json[r]['a'] for r in regs),
                'bytes_na_vram': sum(regioes_json[r]['l'] * regioes_json[r]['a'] * regioes_json[r]['bits'] // 8 for r in regs)},
        }


# ------------------------------------------------------------------------------------------------------
# Exportar as animações de um script
# ------------------------------------------------------------------------------------------------------
def sem_colisao(nomes_possiveis):
    """O Windows não distingue maiúsculas de minúsculas em nome de arquivo, e o Crash 3 tem entradas que só
    diferem nisso (CdsiV e CdSiV, BS10V e Bs10V...). Quem colide ganha um sufixo com o desenho das maiúsculas
    (1 = maiúscula), que não depende da ordem: CdSiV -> CdSiV_10101, CdsiV -> CdsiV_10001."""
    por_minuscula = {}
    for n in nomes_possiveis:
        por_minuscula.setdefault(n.lower(), set()).add(n)
    seguro = {}
    for grupo in por_minuscula.values():
        for n in grupo:
            seguro[n] = n if len(grupo) == 1 else n + '_' + ''.join('1' if c.isupper() else '0' for c in n)
    return seguro


def forma(a, b):
    """Diferença entre duas FORMAS (cada ponto ao mais próximo da outra), sem depender de qual vértice é qual."""
    dd = np.linalg.norm(a[:, None, :] - b[None, :, :], axis=2)
    return float((dd.min(1).mean() + dd.min(0).mean()) / 2)


def classificar_laco(pos):
    """Como a animação emenda no fim, medido nas chaves (unidades do contrato, média por vértice).
    fechado = a última chave volta para perto da primeira; meio_ciclo_espelhado = a última é o espelho (x -> -x) da
    primeira, como a corrida do Crash 1: toca-se normal e depois espelhado; aberto = toca uma vez."""
    k = len(pos)
    if k < 3:
        return {'tipo': 'curta'}
    dist = [float(np.linalg.norm(pos[i] - pos[0], axis=1).mean()) for i in range(k)]
    passo = max(float(np.linalg.norm(pos[i] - pos[i + 1], axis=1).mean()) for i in range(k - 1))
    f_igual = forma(pos[-1], pos[0])
    f_esp = forma(pos[-1], pos[0] * np.array([-1.0, 1.0, 1.0]))
    f_passo = max(forma(pos[0], pos[1]), forma(pos[-2], pos[-1]))
    if dist[-1] <= 1.25 * passo and dist[-1] <= 0.4 * max(dist):
        tipo = 'fechado'
    elif f_esp <= 1.25 * f_passo and f_esp < 0.5 * f_igual:
        tipo = 'meio_ciclo_espelhado'
    else:
        tipo = 'aberto'
    return {'tipo': tipo, 'ultima_x_primeira': round(dist[-1], 1), 'maior_afastamento_da_primeira': round(max(dist), 1),
            'maior_passo': round(passo, 1), 'forma_ultima_x_primeira': round(f_igual, 1),
            'forma_ultima_x_espelho_da_primeira': round(f_esp, 1)}


def exportar(banco, texturas, conv, nomes, saida, args, relatorio, modelos):
    so = set(args.so.split(',')) if args.so else None
    por_modelo = nomes.get('_por_modelo', {})
    feitos, trabalhos = set(), []
    for script, grupo_fixo in SCRIPTS:
        for t in banco.tabela(script):
            anim = t['anim']
            if so and anim not in so:
                continue
            for modelo_nome in t['modelos']:
                if (anim, modelo_nome) in feitos:
                    continue
                feitos.add((anim, modelo_nome))
                tgeo = banco.tgeo(modelo_nome)
                if any(q.n_vertices != tgeo.n_vertices for q in banco.svtx(anim).quadros):
                    continue                                   # o par animação/modelo desta fase não é este
                if anim in nomes:
                    info, origem = list(nomes[anim]), 'anim'
                elif modelo_nome in por_modelo:
                    info, origem = list(por_modelo[modelo_nome]), 'modelo'
                else:
                    info, origem = [anim, '', None], 'anim'
                info += [None] * (4 - len(info))
                trabalhos.append({'script': script, 'grupo_fixo': grupo_fixo, 't': t, 'modelo': modelo_nome, 'cara': 0,
                                  'chave_modelo': modelo_nome, 'nome': info[0], 'descricao': info[1],
                                  'certeza': info[2], 'como_tocar': info[3], 'origem_do_nome': origem})
    vistos = {}
    for tr in trabalhos:                 # nome repetido: a mesma animação em dois modelos, ou um modelo com duas
        vistos[tr['nome']] = vistos.get(tr['nome'], 0) + 1
        if vistos[tr['nome']] > 1:
            tr['nome'] += '_' + (tr['t']['anim'] if tr['origem_do_nome'] == 'modelo' else tr['modelo'])
    for v in nomes.get('_variantes', []):  # o mesmo modelo com outra "cara" (a caixa de madeira tem 8)
        base = next((tr for tr in trabalhos if tr['modelo'] == v['modelo'] and tr['t']['anim'] == v['anim']), None)
        if base:
            trabalhos.append(dict(base, cara=v['cara'], chave_modelo=f"{v['modelo']}_cara{v['cara']}", nome=v['nome'],
                                  descricao=v['descricao'], certeza='alta', como_tocar=None))
    seguro = sem_colisao([tr['nome'] for tr in trabalhos])
    modelo_seguro = sem_colisao(sorted({tr['modelo'] for tr in trabalhos}))
    relatorio['arquivos_dos_modelos'] = modelo_seguro
    if True:
        for tr in trabalhos:
            if True:
                script, grupo_fixo, t, modelo_nome = tr['script'], tr['grupo_fixo'], tr['t'], tr['modelo']
                anim = t['anim']
                nome = seguro[tr['nome']]
                tgeo = banco.tgeo(modelo_nome)
                sv = banco.svtx(anim)
                n = tgeo.n_vertices - tgeo.n_especiais
                grupo = grupo_de(script, grupo_fixo, modelo_nome)
                descricao, certeza = tr['descricao'], tr['certeza']
                chave_modelo = tr['chave_modelo']
                if chave_modelo not in modelos:
                    modelos[chave_modelo] = (Modelo(tgeo, texturas, tr['cara']), grupo, modelo_seguro[modelo_nome],
                                             modelo_nome, tr['cara'])
                modelo = modelos[chave_modelo][0]
                try:
                    brutos = [q.bytes_dos_vertices(tgeo) for q in sv.quadros]
                except ValueError as e:
                    relatorio['animacoes'].append({'nome': nome, 'grupo': grupo, 'origem_no_disco': anim,
                                                   'ausente': str(e)})
                    continue
                if any(len(b) != n for b in brutos) or max(max(tr[:3]) for tr in modelo.triangulos) >= n:
                    relatorio['animacoes'].append({'nome': nome, 'grupo': grupo, 'origem_no_disco': anim,
                                                   'ausente': 'o quadro e o modelo discordam no número de vértices'})
                    continue
                pos = np.stack([conv.posicoes(q, tgeo) for q in sv.quadros])
                if np.abs(pos).max() > 32767:
                    relatorio['animacoes'].append({'nome': nome, 'grupo': grupo, 'origem_no_disco': anim,
                                                   'ausente': 'coordenadas não cabem em int16'})
                    continue
                k_quadros = len(sv.quadros)
                arquivo = f'anim_{nome}.bin'
                with open(os.path.join(saida, arquivo), 'wb') as f:
                    f.write(np.round(pos).astype('<i2').tobytes())
                    f.write(bytes(k_quadros * n * 3))            # normais: o Crash 3 não tem (zeros)
                with open(os.path.join(saida, 'cru', f'{nome}.bin'), 'wb') as f:
                    for q, b in zip(sv.quadros, brutos):
                        f.write(struct.pack('<3hH', q.origem[0] // 32, q.origem[1] // 32, q.origem[2] // 32, n))
                        f.write(b''.join(bytes(v) + b'\0\0\0' for v in b))
                with open(os.path.join(saida, 'comprimido', f'{nome}.bin'), 'wb') as f:
                    f.write(struct.pack('<4sHH', b'C3AN', k_quadros, tgeo.n_vertices))
                    for q in sv.quadros:
                        f.write(struct.pack('<H', len(q.item)) + q.item)
                bases = os.path.join(saida, 'comprimido', f'{modelo_seguro[modelo_nome]}.bases.bin')
                if tgeo.comprimido and not os.path.exists(bases):
                    with open(bases, 'wb') as f:
                        f.write(tgeo.bases_bruto)
                laco = classificar_laco(pos)
                toca = t['toca']
                registro = {
                    'nome': nome, 'grupo': grupo, 'origem_no_disco': anim, 'descricao': descricao,
                    'certeza_do_nome': certeza, 'script': script, 'indice_no_script': t['indice'],
                    'arquivo': arquivo, 'modelo': chave_modelo, 'quadros': k_quadros, 'vertices': n,
                    'toca': toca, 'interpola': t['interpola'], 'fps': FPS,
                    'fps_das_chaves': FPS // 2 if t['interpola'] else FPS,
                    'laco': laco, 'como_tocar': tr['como_tocar'],
                    'ultima_chave_igual_a_primeira': laco['tipo'] == 'fechado',
                    'bytes': k_quadros * n * 9,
                    'cru': {'arquivo': f'cru/{nome}.bin', 'bytes': k_quadros * (8 + n * 6),
                            'por_quadro': 'int16 ox, oy, oz; uint16 n; depois n vezes {uint8 x, y, z; int8 0, 0, 0} '
                                          '(já na ordem x, y, z do contrato, também nos modelos sem compressão)',
                            'k': [round(v, 6) for v in conv.k(tgeo)], 'chao': 0.0,
                            'formula': 'pos[eixo] = (o[eixo] + byte[eixo]) * k[eixo]   (dá o anim_<NOME>.bin antes de arredondar)'},
                    'comprimido': {'arquivo': f'comprimido/{nome}.bin',
                                   'bytes_no_disco': sum(len(q.item) for q in sv.quadros),
                                   'bytes_por_quadro': len(sv.quadros[0].item)},
                    'fases': t['fases'][:6], 'n_fases': len(t['fases']),
                    'por_quadro': [{'caixa': [np.round(p.min(0), 1).tolist(), np.round(p.max(0), 1).tolist()],
                                    'raiz': conv.ponto_de_bytes((0, 0, 0), q, tgeo),
                                    'especiais': [conv.ponto_de_bytes(e, q, tgeo) for e in q.especiais],
                                    'colisao_bruta': [list(c) for c in q.colisoes]} for p, q in zip(pos, sv.quadros)]}
                pasta = os.path.join(saida, 'previews', grupo)
                ja_tem = all(os.path.exists(os.path.join(pasta, f'{nome}.{ext}')) for ext in ('png', 'gif'))
                if ja_tem and (args.previas_novas or args.sem_previas):
                    registro['previa'] = f'previews/{grupo}/{nome}.png'
                    registro['gif'] = f'previews/{grupo}/{nome}.gif'
                elif not args.sem_previas:
                    os.makedirs(pasta, exist_ok=True)
                    todos = pos.reshape(-1, 3)
                    centro = (todos.min(0) + todos.max(0)) / 2
                    raio = float(np.linalg.norm(todos - centro, axis=1).max()) or 1.0
                    imgs = [raster.desenhar(pos[i], None, modelo.para_desenhar, args.tamanho, args.guinada, 12,
                                            (centro, raio), amostras=2) for i in range(k_quadros)]
                    raster.folha_de_contato(imgs, min(len(imgs), 8),
                                            legenda=f'{nome}  [{anim} / {modelo_nome}]  {k_quadros} chaves, toca {toca}').save(
                        os.path.join(pasta, f'{nome}.png'))
                    raster.salvar_gif(imgs, os.path.join(pasta, f'{nome}.gif'), registro['fps_das_chaves'])
                    registro['previa'] = f'previews/{grupo}/{nome}.png'
                    registro['gif'] = f'previews/{grupo}/{nome}.gif'
                relatorio['animacoes'].append(registro)
                diga(f'  {grupo:13} {nome:28} [{anim}] {k_quadros:3} chaves (toca {toca:3}), {n:4} vértices, {modelo_nome}')


GRUPOS_COM_REDUCAO = ('crash', 'giro', 'bazuca', 'mortes', 'caixas', 'aku', 'frutas', 'sombra')


# script, qual grupo de sprite da tabela (0 = o primeiro), grupo, nome
SPRITES = [('FruiC', 0, 'frutas', 'C3_WUMPA', 'a Wumpa girando (é a fruta que a bazuca atira)')]


def exportar_sprites(banco, texturas, saida):
    """Os sprites dos scripts (16 bytes por quadro: cor, 4 cantos de textura, paleta, modo). Registra cada quadro
    como região do atlas e grava um PNG para ver. Formato conferido no SpriteTexture2 do CrashEdit."""
    lista = []
    for script, qual, grupo, nome, descricao in SPRITES:
        if not banco.tem(script, 11) or len(banco.versoes[script][0]['itens']) < 6:
            continue
        grupos = [g for g in banco3.grupos_de_quadros(banco.versoes[script][0]['itens'][5]) if g['tipo'] == 'sprite']
        if qual >= len(grupos):
            continue
        g = grupos[qual]
        pasta = os.path.join(saida, 'sprites', grupo)
        os.makedirs(pasta, exist_ok=True)
        quadros = []
        for i in range(g['quadros']):
            p1, p2, p3, p4 = struct.unpack_from('<4I', g['dados'], i * 16)
            uv = [(p2 & 255, (p2 >> 8) & 255), (p3 & 255, (p3 >> 8) & 255), (p4 & 255, (p4 >> 8) & 255),
                  ((p4 >> 16) & 255, (p4 >> 24) & 255)]
            modo, seg = (p3 >> 23) & 3, (p3 >> 16) & 3
            ox = (1 << (2 - modo)) * 64 * seg if modo < 3 else 0
            x0, y0 = min(u for u, _ in uv) + ox, min(v for _, v in uv)
            larg, alt = max(u for u, _ in uv) + ox - x0 + 1, max(v for _, v in uv) - y0 + 1
            regiao, img = texturas.registrar_retangulo(g['pagina'], modo, (p2 >> 16) & 15, (p2 >> 22) & 127, x0, y0, larg, alt)
            if regiao is None:
                continue
            arquivo = f'{nome}_{i:02d}.png'
            Image.fromarray(img, 'RGBA').save(os.path.join(pasta, arquivo))
            quadros.append({'arquivo': f'sprites/{grupo}/{arquivo}', 'regiao': regiao, 'l': larg, 'a': alt,
                            'bits': (4, 8, 16, 16)[modo], 'rgb': [p1 & 255, (p1 >> 8) & 255, (p1 >> 16) & 255],
                            'semitransparente': bool((p1 >> 25) & 1), 'soma': bool((p3 >> 21) & 1)})
        if quadros:
            lista.append({'nome': nome, 'descricao': descricao, 'grupo': grupo, 'script': script, 'pagina': g['pagina'],
                          'quadros': quadros})
    return lista


def paleta_de_16(cores, k):
    """k cores para representar a lista de cores DISTINTAS `cores` (N, 3): k-médias em que cada cor distinta pesa
    igual, não cada pixel. Assim uma pena azul pequena não some engolida pelo fundo de madeira (ideia do Claude 1,
    MGB #37, depois de o corte mediano comer o azul do Aku Aku). Determinístico."""
    cores = np.unique(np.asarray(cores, np.float64), axis=0)
    if len(cores) <= k:
        return np.vstack([cores, np.zeros((k - len(cores), 3))])
    rng = np.random.default_rng(0)
    centros = [cores[rng.integers(len(cores))]]
    for _ in range(k - 1):                                    # sementes bem espalhadas: a mais longe das já escolhidas
        d = np.min([((cores - c) ** 2).sum(1) for c in centros], axis=0)
        centros.append(cores[int(d.argmax())])
    centros = np.array(centros)
    for _ in range(60):
        d = ((cores[:, None, :] - centros[None, :, :]) ** 2).sum(2)
        dono = d.argmin(1)
        novos = np.array([cores[dono == j].mean(0) if (dono == j).any() else centros[j] for j in range(k)])
        if np.allclose(novos, centros):
            break
        centros = novos
    return centros


def reduzir_imagens(imagens):
    """Lista de imagens RGBA -> (lista de índices 0..15, 16 cores do PS1). Uma paleta só para todas. Se houver
    pixel transparente, o índice 0 é o transparente (cor 0x0000) e sobram 15 cores."""
    tudo = np.concatenate([im.reshape(-1, 4) for im in imagens])
    opaco = tudo[tudo[:, 3] > 0][:, :3]
    transparente = bool((tudo[:, 3] == 0).any())
    k = 15 if transparente else 16
    centros = paleta_de_16(opaco, k)
    cinco = np.clip(np.round(centros / 255.0 * 31), 0, 31).astype(np.int64)          # o PS1 tem 5 bits por canal
    rgb = (cinco * 255 // 31).astype(np.float64)
    ps1 = [int(c[0]) | (int(c[1]) << 5) | (int(c[2]) << 10) for c in cinco]
    ps1 = [v if v else 0x8000 for v in ps1]                                           # preto opaco
    desloc = 1 if transparente else 0
    indices, erro, n = [], 0.0, 0
    for im in imagens:
        px = im[:, :, :3].astype(np.float64)
        d = ((px[:, :, None, :] - rgb[None, None, :, :]) ** 2).sum(3)
        idx = d.argmin(2)
        visivel = im[:, :, 3] > 0
        erro += float(np.abs(px - rgb[idx])[visivel].sum())
        n += int(visivel.sum()) * 3
        idx = np.where(visivel, idx + desloc, 0).astype(np.uint8)
        indices.append(idx)
    cores = ([0] if transparente else []) + ps1
    return indices, cores, (erro / n if n else 0.0), transparente


def gravar_4_bits(caminho, indices):
    with open(caminho, 'wb') as f:
        for idx in indices:
            a, l = idx.shape
            larg = (l + 1) // 2 * 2
            cheio = np.zeros((a, larg), np.uint8)
            cheio[:, :l] = idx
            f.write((cheio[:, 0::2] | (cheio[:, 1::2] << 4)).astype(np.uint8).tobytes())


def antes_depois(caminho, imagens, indices, cores):
    pal = np.array([fmt.cor_ps1(c) for c in cores], np.uint8)
    l = sum(im.shape[1] + 2 for im in imagens)
    a = max(im.shape[0] for im in imagens)
    folha = Image.new('RGBA', (l, a * 2 + 2), (60, 60, 80, 255))
    x = 0
    for im, idx in zip(imagens, indices):
        folha.alpha_composite(Image.fromarray(im, 'RGBA'), (x, 0))
        folha.alpha_composite(Image.fromarray(pal[idx], 'RGBA'), (x, a + 2))
        x += im.shape[1] + 2
    folha.resize((folha.width * 4, folha.height * 4), Image.NEAREST).save(caminho)


def reduzir_para_4_bits(relatorio, saida):
    """OPCIONAL, e é mexida nossa (não é dado do disco): algumas texturas vêm em 8 bits (256 cores), como a cara
    do Aku Aku na caixa e a Wumpa. Para quem só tem atlas de 4 bits, grava uma versão de 16 cores de cada região de
    8 bits usada pelos grupos principais, e de cada sprite (uma paleta só para todos os quadros do sprite)."""
    tex = relatorio['texturas']
    regs, cluts = tex['regioes'], tex['cluts']
    if 'atlas_8bits' not in tex['atlas']:
        return {}
    info = tex['atlas']['atlas_8bits']
    atlas = np.fromfile(os.path.join(saida, 'tex', 'atlas_8bits.bin'), np.uint8).reshape(info['altura_px'], info['largura_px'])
    pasta = os.path.join(saida, 'tex', 'reduzidas')
    os.makedirs(pasta, exist_ok=True)

    def imagem(r):
        reg = regs[r]
        idx = atlas[reg['y']:reg['y'] + reg['a'], reg['x']:reg['x'] + reg['l']]
        return np.array([fmt.cor_ps1(int(h, 16)) for h in cluts[reg['clut']]['cores_ps1']], np.uint8)[idx]

    saida_json = {}
    usadas = sorted({r for md in relatorio['modelos'].values() if md['grupo'] in GRUPOS_COM_REDUCAO
                     for r in md['texturas_do_modelo']['regioes'] if regs[r]['bits'] == 8})
    for r in usadas:
        im = imagem(r)
        indices, cores, erro, transp = reduzir_imagens([im])
        gravar_4_bits(os.path.join(pasta, f'regiao_{r}_4bits.bin'), indices)
        antes_depois(os.path.join(pasta, f'regiao_{r}_antes_depois.png'), [im], indices, cores)
        saida_json[str(r)] = {'arquivo': f'tex/reduzidas/regiao_{r}_4bits.bin', 'l': regs[r]['l'], 'a': regs[r]['a'],
                              'cores_ps1': [f'{c:04x}' for c in cores], 'indice_0_transparente': transp,
                              'erro_medio_por_canal': round(erro, 2),
                              'previa': f'tex/reduzidas/regiao_{r}_antes_depois.png',
                              'modelos': sorted(n for n, md in relatorio['modelos'].items()
                                                if r in md['texturas_do_modelo']['regioes'])}
    for sp in relatorio.get('sprites', []):
        if not all(q['bits'] == 8 for q in sp['quadros']):
            continue
        ims = [imagem(q['regiao']) for q in sp['quadros']]
        indices, cores, erro, transp = reduzir_imagens(ims)
        gravar_4_bits(os.path.join(pasta, f'{sp["nome"]}_4bits.bin'), indices)
        antes_depois(os.path.join(pasta, f'{sp["nome"]}_antes_depois.png'), ims, indices, cores)
        sp['reducao_4bits'] = {
            'arquivo': f'tex/reduzidas/{sp["nome"]}_4bits.bin', 'quadros': len(ims),
            'l': sp['quadros'][0]['l'], 'a': sp['quadros'][0]['a'],
            'formato': 'os quadros um depois do outro; cada um a linhas de l/2 bytes, 2 pixels por byte, o da esquerda '
                       'no nibble baixo (igual ao atlas de 4 bits)',
            'cores_ps1': [f'{c:04x}' for c in cores], 'indice_0_transparente': transp,
            'erro_medio_por_canal': round(erro, 2), 'previa': f'tex/reduzidas/{sp["nome"]}_antes_depois.png',
            'nota': 'redução NOSSA de 256 para 16 cores; o dado do disco são as regiões de 8 bits'}
    return saida_json


TAXA_DOS_SONS = 11025          # o tom 4.0 do script = 0x400 no SPU (medido no Crash 1; os nomes são os mesmos)


def exportar_sons(banco, saida, refazer_wav):
    """Todos os sons (entradas ADIO): o ADPCM original do SPU embrulhado em .vag + um .wav para ouvir."""
    pasta = os.path.join(saida, 'snd')
    os.makedirs(pasta, exist_ok=True)
    nomes = sorted(n for n, v in banco.versoes.items() if v[0]['tipo'] == 12)
    seguro = sem_colisao(nomes)
    lista = []
    for nome in nomes:
        adpcm = banco.versoes[nome][0]['itens'][0]
        arq = seguro[nome]
        with open(os.path.join(pasta, f'{arq}.vag'), 'wb') as f:
            f.write(fmt.vag(adpcm, nome, TAXA_DOS_SONS))
        caminho_wav = os.path.join(pasta, f'{arq}.wav')
        if refazer_wav or not os.path.exists(caminho_wav):
            with open(caminho_wav, 'wb') as f:
                f.write(fmt.wav(fmt.adpcm_para_pcm(adpcm), TAXA_DOS_SONS))
        lista.append({'nome': nome, 'vag': f'snd/{arq}.vag', 'wav': f'snd/{arq}.wav', 'bytes_adpcm': len(adpcm),
                      'segundos_presumidos': round(len(adpcm) / 16 * 28 / TAXA_DOS_SONS, 2),
                      'n_fases': len(banco.fases(nome)), 'versoes_no_disco': len(banco.versoes[nome])})
    return lista


def exportar_caras(banco, texturas, conv, saida):
    """As 64 caras do Crash: cada triângulo de textura animada do Cr10G escolhe 1 de 64 texturas."""
    anim, modelo_nome, quadro = REFERENCIA
    tgeo = banco.tgeo(modelo_nome)
    pos = conv.posicoes(banco.svtx(anim).quadros[quadro], tgeo)
    rosto = np.array(banco.svtx(anim).quadros[quadro].especiais[1], np.float64)      # o ponto de encaixe do rosto
    rosto = (rosto * 8 + np.array(banco.svtx(anim).quadros[quadro].origem) / 4) * np.array(tgeo.escala) * conv.fator
    centro = rosto + np.array([0.0, 60.0, -180.0])
    raio = 330.0
    imgs = []
    for face in range(64):
        m = Modelo(tgeo, Texturas(banco), face)
        imgs.append(raster.desenhar(pos, None, m.para_desenhar, 96, 15, 5, (centro, raio), amostras=3))
    raster.folha_de_contato(imgs, 8, legenda='As 64 caras do Crash 3 (quadro de textura 0 a 63, da esquerda para a '
                                             'direita, de cima para baixo)').save(os.path.join(saida, 'previews', 'caras.png'))


def catalogo_md(relatorio, caminho):
    linhas = ['# Catálogo do que saiu do disco do Crash 3 (Warped)', '',
              f'Disco: {relatorio["disco"]["serial"]} · gerado por `extrair3.py` · formatos: CrashEdit (CBHacks).', '',
              'O script do Crash ainda se chama **WillC** (Willy) no terceiro jogo. O disco guarda os quadros-chave a 15 '
              'por segundo; o jogo interpola e toca a 30 (colunas "chaves" e "toca").',
              'Os apelidos (`C3_*`) são nossos, dados olhando as prévias (`nomes_c3.json`); o nome de verdade é o da '
              'entrada.', '']
    ordem = ['crash', 'giro', 'bazuca', 'mortes', 'caixas', 'aku', 'frutas', 'sombra', 'particulas', 'crash_outros']
    grupos = sorted({a['grupo'] for a in relatorio['animacoes']},
                    key=lambda g: (ordem.index(g) if g in ordem else len(ordem), g))
    for grupo in grupos:
        linhas += [f'## {grupo}', '', '| Animação | Entrada | Modelo | Chaves | Toca | Vértices | Bytes no disco | Fases | Prévia |',
                   '|---|---|---|---|---|---|---|---|---|']
        for a in relatorio['animacoes']:
            if a['grupo'] != grupo:
                continue
            if 'ausente' in a:
                linhas.append(f'| `{a["nome"]}` | {a["origem_no_disco"]} | | | | | | | não exportada: {a["ausente"]} |')
                continue
            previa = f'![{a["nome"]}]({a["gif"]})' if 'gif' in a else ''
            desc = f'<br>{a["descricao"]}' if a.get('descricao') else ''
            tipo = {'fechado': ' · laço', 'meio_ciclo_espelhado': ' · MEIO CICLO (espelhar)'}.get(a['laco']['tipo'], '')
            linhas.append(f'| `{a["nome"]}`{desc} | {a["origem_no_disco"]} | {a["modelo"]} | {a["quadros"]} | '
                          f'{a["toca"]}{"" if a["interpola"] else " (sem interpolar)"}{tipo} | {a["vertices"]} | '
                          f'{a["comprimido"]["bytes_no_disco"]} | {a["n_fases"]} | {previa} |')
        linhas.append('')
    with open(caminho, 'w', encoding='utf-8') as f:
        f.write('\n'.join(linhas))


def principal():
    ap = argparse.ArgumentParser(description='Extrai o Crash do disco do Crash Bandicoot 3 (Warped).')
    ap.add_argument('--disco', required=True, help='imagem do disco (.cue, .bin, .img ou .iso)')
    ap.add_argument('--saida', default=os.path.join(AQUI, 'out_c3'))
    ap.add_argument('--so', help='só estas animações (nomes de entrada, separados por vírgula)')
    ap.add_argument('--sem-previas', action='store_true')
    ap.add_argument('--previas-novas', action='store_true',
                    help='só desenha as prévias que ainda não existem (os dados são sempre regravados)')
    ap.add_argument('--tamanho', type=int, default=128, help='lado de cada quadro de prévia, em pixels')
    ap.add_argument('--guinada', type=float, default=30, help='ângulo da câmera das prévias, em graus')
    args = ap.parse_args()
    t0 = time.time()
    saida = args.saida
    for sub in ('', 'cru', 'comprimido', 'tex', 'previews'):
        os.makedirs(os.path.join(saida, sub), exist_ok=True)

    disco = Disco(args.disco)
    serial = disco.serial_ps1()
    diga(f'Disco: {serial} ({SERIAIS.get(serial, "serial que eu não conheço: confira se é o Crash 3")})')
    banco = banco3.Banco3()
    banco.ler_disco(disco)
    diga(f'{len(banco.por_fase)} fases, {len(banco.versoes)} entradas diferentes ({time.time() - t0:.0f} s)')
    with open(os.path.join(saida, 'indice.json'), 'w', encoding='utf-8') as f:
        json.dump({n: {'tipo': nsf.NOME_DO_TIPO.get(v[0]['tipo'], v[0]['tipo']), 'versoes': len(v),
                       'fases': len(banco.fases(n)), 'itens': [len(i) for i in v[0]['itens']][:8]}
                   for n, v in sorted(banco.versoes.items())}, f, ensure_ascii=False, indent=0)

    with open(os.path.join(AQUI, 'nomes_c3.json'), encoding='utf-8') as f:
        nomes = json.load(f)
    conv = Conversao()
    conv.calibrar(banco)
    texturas = Texturas(banco)
    relatorio = {'contrato': 'MGB_board.md v1.1 + acréscimos do Crash 3 (v1.2: MGB #25/#26)',
                 'disco': {'serial': serial, 'jogo': SERIAIS.get(serial), 'fases_lidas': len(banco.por_fase)},
                 'normais': False, 'animacoes': [], 'modelos': {}}
    modelos = {}
    exportar(banco, texturas, conv, nomes, saida, args, relatorio, modelos)
    relatorio['sprites'] = exportar_sprites(banco, texturas, saida)
    tex_json, cluts = texturas.exportar(os.path.join(saida, 'tex'))
    for nome, (m, grupo, arquivo, no_disco, cara) in modelos.items():
        relatorio['modelos'][nome] = dict(m.json(grupo, cluts, tex_json['regioes'], arquivo),
                                          modelo_no_disco=no_disco, cara=cara)
    relatorio['texturas'] = tex_json
    relatorio['conversao'] = conv.descricao()
    relatorio['sentido_dos_triangulos'] = ('horário visto de fora, igual à entrega do Crash 1 (conferido pelo z-buffer: '
                                           'todo triângulo visível tem a mesma orientação na tela)')
    relatorio['cores'] = ('`cores` são os bytes do modelo (0..255). Cada triângulo tem uma cor por canto '
                          '(`cores_dos_cantos`, na mesma ordem de `triangulos`), inclusive os com textura. No Crash 3 '
                          'não há luz por normal: o sombreado já está pintado nestas cores. Nas prévias usei 2 x cor nos '
                          'triângulos sem textura e textura x cor / 128 nos com textura (128 = neutro do PS1); o valor '
                          '185 aparece como "claro cheio". O material traz rgb 128 e liso = true só para não quebrar '
                          'quem lê o contrato do Crash 1.')
    relatorio['textura_animada'] = ('Os triângulos de textura animada do Cr10G (olhos, sobrancelhas, boca) escolhem 1 de '
                                    '64 texturas: são as 64 caras do Crash (previews/caras.png). A entrega usa a cara 0 '
                                    '(olhos abertos, boca normal).')
    relatorio['modo_de_mistura'] = '3 = opaco; 0 = média com o fundo; 1 = soma; 2 = subtrai do fundo'
    relatorio['formato_anim'] = ('anim_<NOME>.bin = int16 little-endian [quadro][vértice][x,y,z] seguido de int8 '
                                 '[quadro][vértice][3] de ZEROS (o Crash 3 não tem normal; o bloco fica para o leiaute '
                                 'ser igual ao do Crash 1)')
    relatorio['bazuca'] = ('O Crash com a bazuca são dois modelos: pernas (Cgb0G, grupo bazuca) e tronco (Cgt0G). O tronco é '
                           'desenhado na CINTURA das pernas: posição = especiais[0] da chave atual das pernas + vértice do '
                           'tronco (medido e desenhado: com a mesma raiz o tronco afunda nas pernas). Pares, pelo nome no '
                           'disco: Cgt0V/Cgb0V = o tiro (em cima/embaixo), CgT0V/CgB0V = sacar. Mira = chave 0 do '
                           'C3_BAZUCA_TIRO, parada. A Wumpa nasce em especiais[2] do tronco e vai para +Z.')
    relatorio['laco'] = ('por animação, `laco.tipo`: "fechado" (depois do último quadro tocado volta ao 0), '
                         '"meio_ciclo_espelhado" (tocar os quadros normais e depois os mesmos com x -> -x e o descarte '
                         'de costas invertido; a última chave é o espelho da primeira), "aberto" (toca uma vez) ou '
                         '"curta" (1 ou 2 chaves). É MEDIDO nas chaves, não vem do script do jogo. `como_tocar`, '
                         'quando existe, explica as emendas (também medidas).')
    relatorio['interpolacao'] = ('`quadros` = quadros-chave no disco; `toca` = quantos quadros o script toca; se '
                                 '`interpola`, o quadro tocado f usa a chave f/2 quando f é par e a média das chaves '
                                 '(f-1)/2 e (f+1)/2 quando é ímpar. toca = 2*chaves - 1 mostra todas as chaves; '
                                 'toca = 2*chaves - 2 para antes da última (laço: ver ultima_chave_igual_a_primeira).')
    exportados = [a for a in relatorio['animacoes'] if 'ausente' not in a]
    por_grupo = {}
    for a in exportados:
        g = por_grupo.setdefault(a['grupo'], {'animacoes': 0, 'chaves': 0, 'bytes_no_disco': 0, 'bytes_cru': 0})
        g['animacoes'] += 1
        g['chaves'] += a['quadros']
        g['bytes_no_disco'] += a['comprimido']['bytes_no_disco']
        g['bytes_cru'] += a['cru']['bytes']
    relatorio['orcamento'] = {
        'animacoes': len(exportados), 'chaves': sum(a['quadros'] for a in exportados), 'por_grupo': por_grupo,
        'modelos': {n: {'vertices': m['vertices'], 'triangulos': m['n_triangulos'], 'texturizados': m['n_texturizados'],
                        'cores': len(m['cores']), 'bytes_vram': m['texturas_do_modelo']['bytes_na_vram']}
                    for n, m in relatorio['modelos'].items()},
        'texturas': tex_json['atlas'], 'cluts': len(tex_json['cluts'])}
    relatorio['texturas']['reducoes_para_4bits'] = reduzir_para_4_bits(relatorio, saida)
    relatorio['texturas']['reducoes_nota'] = ('OPCIONAL e NOSSO: cada região de 8 bits usada pelos grupos principais também '
                                              'sai reduzida para 16 cores (k-médias com cada cor distinta pesando igual, '
                                              'sem pontilhado; os sprites usam uma paleta só para todos os quadros), no formato '
                                              'do atlas de 4 bits (2 pixels por byte, o da esquerda no nibble baixo). A '
                                              'textura original é a região de 8 bits + CLUT de 256 cores. Se usar a '
                                              'reduzida, dizer no README: não é o dado do disco.')
    if not args.so:
        relatorio['sons'] = exportar_sons(banco, saida, not args.previas_novas and not args.sem_previas)
        relatorio['sons_nota'] = ('snd/<NOME>.vag = ADPCM original do SPU com cabeçalho VAG (os bytes do disco começam no '
                                  'byte 64, como na entrega do Crash 1); .wav só para ouvir. Taxa presumida 11025 Hz. Os '
                                  'nomes são os do disco e batem com os do Crash 1: arg0A = o "Woah!" (outra gravação), '
                                  'spn0A = giro, WD10A/WD20A = Aku Aku, tnt0A, Ttb0A, brk0A, frt0A, jmp0A, 1up0A, yip0A.')
    with open(os.path.join(saida, 'model.json'), 'w', encoding='utf-8') as f:
        json.dump(relatorio, f, ensure_ascii=False)
    catalogo_md(relatorio, os.path.join(saida, 'CATALOGO.md'))
    caras = os.path.join(saida, 'previews', 'caras.png')
    if not args.sem_previas and not args.so and not (args.previas_novas and os.path.exists(caras)):
        exportar_caras(banco, texturas, conv, saida)
    diga(f'\n{len(exportados)} animações, {relatorio["orcamento"]["chaves"]} quadros-chave, {len(modelos)} modelos, '
         f'{len(tex_json["regioes"])} regiões de textura, {len(tex_json["cluts"])} paletas. {time.time() - t0:.0f} s')
    diga(f'Entrega em {saida}')


if __name__ == '__main__':
    principal()
