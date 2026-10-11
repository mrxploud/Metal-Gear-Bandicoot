#!/usr/bin/env python
"""Teste do extrator SEM o disco do Crash: fabrica um CD de mentira e passa ele pelo extrator inteiro.

    python -I testes/teste_sintetico.py <pasta_temporaria>

O CD falso é uma imagem MODE2/2352 (como a do PS1) com ISO 9660, um SYSTEM.CNF e um S0000003.NSF. O NSF tem
uma página normal, uma página de textura COMPRIMIDA (para exercitar a descompressão) e uma página de som.
Dentro dele mora um "Crash" que é um cubo: 8 vértices, 12 triângulos (lisos, com luz e com textura), 4 quadros.

O que este teste prova: que cada leitor entende o que o próprio escritor daqui grava seguindo os headers do c1.
O que ele NÃO prova: que o disco de verdade é igual ao que eu entendi dos headers. Isso só o disco responde.
"""
import json
import os
import struct
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)

from crashlib import disco as cd                               # noqa: E402
from crashlib import formatos as fmt                           # noqa: E402
from crashlib import nsf                                       # noqa: E402

falhas = []


def confere(cond, texto):
    print(('  ok    ' if cond else '  FALHA ') + texto)
    if not cond:
        falhas.append(texto)


# ---------------------------------------------------------------------------------------------- NSF falso
def entrada(nome, tipo, itens):
    cab = struct.pack('<IIII', nsf.MAGIA_ENTRADA, nsf.eid_do_nome(nome), tipo, len(itens))
    pos = 16 + 4 * (len(itens) + 1)
    desloc = []
    for it in itens:
        desloc.append(pos)
        pos += len(it)
    desloc.append(pos)
    return cab + struct.pack(f'<{len(desloc)}I', *desloc) + b''.join(itens)


def pagina_normal(tipo, entradas):
    pos = 16 + 4 * (len(entradas) + 1)
    desloc = []
    for e in entradas:
        desloc.append(pos)
        pos += len(e)
    desloc.append(pos)
    p = struct.pack('<HHIII', nsf.MAGIA_PAGINA, tipo, 1, len(entradas), 0)
    p += struct.pack(f'<{len(desloc)}I', *desloc) + b''.join(entradas)
    assert len(p) <= nsf.TAM_PAGINA
    return p + b'\x00' * (nsf.TAM_PAGINA - len(p))


def comprimir(pagina, comprimento=0xF000, pular=37):
    """Compressor guloso no formato do Crash 1: literais (até 127) e cópias (3 a 9 bytes, ou 64)."""
    saida = bytearray(struct.pack('<HHII', nsf.MAGIA_COMPRIMIDA, 0, comprimento, pular))
    i, literais = 0, bytearray()

    def descarregar():
        nonlocal literais
        while literais:
            saida.append(min(len(literais), 127))
            saida.extend(literais[:127])
            literais = literais[127:]

    while i < comprimento:
        melhor, melhor_d = 0, 0
        for d in (1, 2, 3, 4, 8, 16, 512, 1024, 4095):
            if d > i:
                continue
            n = 0
            while n < 64 and i + n < comprimento and pagina[i + n] == pagina[i + n - d]:
                n += 1
            if n > melhor:
                melhor, melhor_d = n, d
        if melhor >= 3:
            n = 64 if melhor == 64 else min(melhor, 9)
            descarregar()
            par = 0x8000 | (melhor_d << 3) | (7 if n == 64 else n - 3)
            saida += struct.pack('>H', par)
            i += n
        else:
            literais.append(pagina[i])
            i += 1
    descarregar()
    saida += b'\xAA' * pular                         # lixo que o leitor tem de pular
    saida += pagina[comprimento:]                    # o fim da página vem sem compressão
    return bytes(saida)


def pagina_de_textura(nome):
    """256x128 palavras. Linha 0: cabeçalho. Paleta de 16 cores em clut (x=1, y=4). Um xadrez 32x32 em (64, 32)."""
    p = bytearray(nsf.TAM_PAGINA)
    struct.pack_into('<HHIII', p, 0, nsf.MAGIA_PAGINA, 1, nsf.eid_do_nome(nome), 5, 0)
    cores = [0x0000, 0x7FFF, 0x001F, 0x03E0, 0x7C00] + [0x0421 * k for k in range(5, 16)]
    struct.pack_into('<16H', p, (1 * 16 + 4 * 256) * 2, *cores)
    for y in range(32, 64):
        for x in range(64, 96):
            cor = 1 + (((x // 8) + (y // 8)) % 4)
            b = y * 512 + x // 2
            p[b] = (p[b] & 0x0F) | (cor << 4) if x & 1 else (p[b] & 0xF0) | cor
    return bytes(p)


def colinfo(r, g, b):
    return bytes([r, g, b, 0])


def texinfo(r, g, b, pagina, uv_idx, modo, segmento, dx, dy, clut_x, clut_y):
    regiao = dy | (clut_y << 6) | (dx << 13) | (segmento << 18) | (modo << 20) | (uv_idx << 22)
    return bytes([r, g, b, 0x80 | clut_x]) + struct.pack('<II', nsf.eid_do_nome(pagina), regiao)


CUBO = [(x, y, z) for y in (78, 178) for z in (78, 178) for x in (78, 178)]
FACES = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]


def fabricar_nsf():
    # materiais: 4 cores + 1 textura. uv_idx 18 = retângulo 32x32 (linha 3 da tabela = altura 32? ver abaixo)
    mats = [colinfo(230, 120, 30), colinfo(40, 90, 200), colinfo(200, 40, 40), colinfo(240, 220, 160)]
    # uv_map: índice = largura + 5 * altura, com larguras/alturas 4, 8, 16, 32, 64 -> 32x32 é 3 + 5*3 = 18
    tex = texinfo(128, 128, 128, 'WillT', 18, 0, 0, 64 // 8, 32 // 4, 1, 4)
    blob, palavra = b'', []
    for m in mats + [tex]:
        palavra.append(len(blob) // 4)
        blob += m
    cab = struct.pack('<IiiiI', 12, 4096, 4096, 4096, len(blob) // 4) + blob     # conta palavras, como no disco
    pol = b''
    for i, (a, b, c, d) in enumerate(FACES):
        mat = palavra[4] if i == 0 else palavra[i % 4]
        liso = 1 if i == 1 else 0
        for tri in ((a, b, c), (a, c, d)):
            pol += struct.pack('<4H', tri[0] * 6, tri[1] * 6, tri[2] * 6, mat | (liso << 15))
    tgeo = entrada('WillG', 2, [cab, pol])
    quadros = []
    for k in range(4):
        v = b''
        for (x, y, z) in CUBO:
            y2 = y + (k * 6 if y > 128 else 0)                  # o cubo "respira": o topo sobe a cada quadro
            n = (127 if x > 128 else -127, 127 if y > 128 else -127, 127 if z > 128 else -127)
            v += struct.pack('<3B3b', x, y2, z, *n)
        cabq = struct.pack('<II3i6i3i', (56 + len(v)) // 4, nsf.eid_do_nome('WillG'), 0, 0, 0,
                           -200, -200, -200, 200, 200, 200, 0, 0, 0)
        quadros.append(cabq + v)
    svtx = entrada('WiS1V', 1, quadros)
    # executável GOOL: item 5 com uma animação de vértices (4 quadros) e uma de sprite (2 quadros)
    anim_v = bytes([1, 0, 4, 0]) + struct.pack('<I', nsf.eid_do_nome('WiS1V'))
    regiao = (32 // 4) | (4 << 6) | ((64 // 8) << 13) | (18 << 22)
    sprite = bytes([2, 0, 2, 0]) + struct.pack('<I', nsf.eid_do_nome('WillT'))
    sprite += (bytes([128, 128, 128, 1]) + struct.pack('<I', regiao)) * 2
    gool = entrada('WillC', 11, [b'\x00' * 24, b'', b'', b'', b'', anim_v + sprite])
    adpcm = b''
    for bloco in range(40):
        adpcm += bytes([0x0C, 0x02 if bloco < 39 else 0x01]) + bytes((bloco * 7 + i * 13) & 0xFF for i in range(14))
    som = entrada('jmp0A', 12, [adpcm])
    p0 = pagina_normal(0, [tgeo, svtx, gool])
    p1 = pagina_de_textura('WillT')
    p2 = pagina_normal(3, [som])
    return p0 + comprimir(p1) + p2, p1, adpcm


# ----------------------------------------------------------------------------------------------- CD falso
def setor_cru(dados, lba):
    assert len(dados) == 2048
    m, s, f = lba // 4500, (lba // 75) % 60, lba % 75
    return cd.SINCRONIA + bytes([m, s, f, 2]) + bytes([0, 0, 8, 0] * 2) + dados + b'\x00' * 280


def registro(nome, lba, tamanho, pasta=False):
    nome_b = nome.encode('ascii')
    comprimento = 33 + len(nome_b) + (1 - len(nome_b) % 2)
    r = bytearray(comprimento)
    r[0] = comprimento
    struct.pack_into('<I', r, 2, lba)
    struct.pack_into('>I', r, 6, lba)
    struct.pack_into('<I', r, 10, tamanho)
    struct.pack_into('>I', r, 14, tamanho)
    r[25] = 2 if pasta else 0
    r[32] = len(nome_b)
    r[33:33 + len(nome_b)] = nome_b
    return bytes(r)


def fabricar_cd(caminho, arquivo_nsf):
    cnf = b'BOOT = cdrom:\\SCUS_949.00;1\r\nTCB = 4\r\nEVENT = 16\r\nSTACK = 801fff00\r\n'
    n_nsf = (len(arquivo_nsf) + 2047) // 2048
    lba_raiz, lba_s0, lba_cnf, lba_nsf = 18, 19, 20, 21
    setores = {}
    pvd = bytearray(2048)
    pvd[0] = 1
    pvd[1:6] = b'CD001'
    pvd[8:40] = b'PLAYSTATION'.ljust(32)
    pvd[40:72] = b'CRASH_DE_MENTIRA'.ljust(32)
    pvd[156:190] = registro('\x00', lba_raiz, 2048, True)
    setores[16] = bytes(pvd)
    raiz = registro('\x00', lba_raiz, 2048, True) + registro('\x01', lba_raiz, 2048, True)
    raiz += registro('S0', lba_s0, 2048, True) + registro('SYSTEM.CNF;1', lba_cnf, len(cnf))
    setores[lba_raiz] = raiz.ljust(2048, b'\x00')
    s0 = registro('\x00', lba_s0, 2048, True) + registro('\x01', lba_raiz, 2048, True)
    s0 += registro('S0000003.NSF;1', lba_nsf, len(arquivo_nsf))
    setores[lba_s0] = s0.ljust(2048, b'\x00')
    setores[lba_cnf] = cnf.ljust(2048, b'\x00')
    for i in range(n_nsf):
        setores[lba_nsf + i] = arquivo_nsf[i * 2048:(i + 1) * 2048].ljust(2048, b'\x00')
    with open(caminho, 'wb') as f:
        for lba in range(lba_nsf + n_nsf):
            f.write(setor_cru(setores.get(lba, b'\x00' * 2048), lba))
    with open(os.path.splitext(caminho)[0] + '.cue', 'w') as f:
        f.write(f'FILE "{os.path.basename(caminho)}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n')


# ------------------------------------------------------------------------------------------------- testes
def principal():
    sys.stdout.reconfigure(encoding='utf-8')
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    pasta = sys.argv[1]
    os.makedirs(pasta, exist_ok=True)

    print('nomes de entrada')
    for nome in ('WiS1V', 'WillC', 'jmp0A', '!sp0A', 'Dog_C', '1up0A'):
        confere(nsf.nome_do_eid(nsf.eid_do_nome(nome)) == nome, f'{nome} vai e volta')
    confere(nsf.eid_do_nome('WillC') & 1 == 1, 'EID tem o bit 0 ligado')

    print('compressão de página')
    arquivo_nsf, textura, adpcm = fabricar_nsf()
    comprimida = comprimir(textura)
    aberta, fim = nsf.descomprimir_pagina(comprimida, 0)
    confere(aberta == textura, f'página de textura comprimida ({len(comprimida)} bytes) abre idêntica (65536 bytes)')
    confere(fim == len(comprimida), 'a posição da próxima página bate com o fim da comprimida')

    print('CD de mentira')
    bin_ = os.path.join(pasta, 'crash_de_mentira.bin')
    fabricar_cd(bin_, arquivo_nsf)
    with cd.Disco(os.path.splitext(bin_)[0] + '.cue') as d:
        confere(d.setor_bruto == 2352 and d.modo == 2, 'reconhece setor cru MODE2/2352 a partir do .cue')
        confere(d.serial_ps1() == 'SCUS_949.00', f'serial lido do SYSTEM.CNF: {d.serial_ps1()}')
        confere('S0/S0000003.NSF' in d.arquivos(), f'arquivos: {sorted(d.arquivos())}')
        confere(d.ler('S0/S0000003.NSF') == arquivo_nsf, 'o .NSF sai do CD byte a byte igual')

    print('entradas do NSF')
    es = {e.nome: e for e in nsf.entradas(arquivo_nsf)}
    confere(sorted(es) == ['WiS1V', 'WillC', 'WillG', 'WillT', 'jmp0A'], f'entradas: {sorted(es)}')
    confere(es['WillT'].tipo == 5 and es['WillT'].itens[0] == textura, 'página de textura vira entrada TPAG')
    tg = fmt.Tgeo(es['WillG'])
    confere(len(tg.triangulos) == 12 and tg.n_vertices_usados == 8, '12 triângulos, 8 vértices')
    confere(sum(1 for t in tg.triangulos if t[4]) == 2, '2 triângulos lisos (bit 15)')
    texturizados = [tg.materiais_por_palavra[t[3]] for t in tg.triangulos if tg.materiais_por_palavra[t[3]].texturizado]
    confere(len(texturizados) == 2, '2 triângulos com textura')
    uv_map = fmt.carregar_uv_map(os.path.join(RAIZ, '..', 'repos', 'c1', 'src', 'gfx.c'))
    confere(uv_map[18] == [(0, 0), (31, 0), (0, 31), (31, 31)], f'uv_map[18] do c1 = {uv_map[18]}')
    m = texturizados[0]
    confere(m.uvs(uv_map) == [(64, 32), (95, 32), (64, 63)], f'UVs do material: {m.uvs(uv_map)}')
    confere((m.clut_x, m.clut_y, m.modo_de_cor) == (1, 4, 0), 'paleta em (1, 4), 4 bits')
    confere(fmt.paleta(textura, 1, 4, 0)[:5] == [0, 0x7FFF, 0x1F, 0x3E0, 0x7C00], 'paleta lida da própria página')
    confere(fmt.indice_do_pixel(textura, 64, 32, 0) == 1 and fmt.indice_do_pixel(textura, 72, 32, 0) == 2, 'pixels do xadrez')
    sv = fmt.Svtx(es['WiS1V'])
    confere(len(sv.quadros) == 4 and sv.tgeos == ['WillG'], '4 quadros, todos do modelo WillG')
    v = sv.quadros[3].vertices(8)
    confere(v[0] == (-200, -200, -200) and v[7] == (200, 272, 200), f'vértices do quadro 3: {v[0]} ... {v[7]}')
    confere(fmt.adpcm_para_pcm(adpcm).__len__() == 40 * 28, 'ADPCM: 40 blocos = 1120 amostras')

    print('extrator inteiro, do .cue até o model.json')
    saida = os.path.join(pasta, 'out')
    r = subprocess.run([sys.executable, '-I', os.path.join(RAIZ, 'extrair.py'), '--disco',
                        os.path.splitext(bin_)[0] + '.cue', '--saida', saida, '--tamanho', '96'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    print('    ' + r.stdout.strip().replace('\n', '\n    '))
    if r.returncode:
        print(r.stderr)
    confere(r.returncode == 0, 'extrair.py terminou sem erro')
    if r.returncode == 0:
        with open(os.path.join(saida, 'model.json'), encoding='utf-8') as f:
            mj = json.load(f)
        a = next(x for x in mj['animacoes'] if x['nome'] == 'WILLY_STANCE1')
        confere(a.get('quadros') == 4 and a.get('vertices') == 8, 'WILLY_STANCE1: 4 quadros, 8 vértices')
        dados = open(os.path.join(saida, a['arquivo']), 'rb').read()
        confere(len(dados) == 4 * 8 * 9, f'{a["arquivo"]}: {len(dados)} bytes = 4 quadros x 8 vértices x 9')
        pos = struct.unpack_from('<24h', dados, 0)
        ys = pos[1::3]
        confere(min(ys) == 0 and max(ys) == 1000, f'quadro 0: pés em y={min(ys)}, topo em y={max(ys)}')
        ultimo = struct.unpack_from('<24h', dados, 3 * 8 * 6)
        confere(max(ultimo[1::3]) == 1180, f'quadro 3: topo em y={max(ultimo[1::3])} (subiu 72 * 2,5)')
        nor = struct.unpack_from('<24b', dados, 4 * 8 * 6)
        confere(nor[:3] == (-127, -127, -127), f'primeira normal: {nor[:3]}')
        modelo = mj['modelos']['WillG']
        confere(modelo['n_triangulos'] == 12 and modelo['n_texturizados'] == 2, 'modelo: 12 triângulos, 2 com textura')
        mat_tex = next(x for x in modelo['materiais'] if x['textura'] is not None)
        confere(mat_tex['uv'] == [[0, 0], [31, 0], [0, 31]] and mat_tex['clut'] == 0 and mat_tex['bits'] == 4,
                f'material com textura: uv {mat_tex["uv"]}, clut {mat_tex["clut"]}, {mat_tex["bits"]} bits')
        reg = mj['texturas']['regioes'][mat_tex['textura']]
        confere((reg['l'], reg['a']) == (32, 32) and reg['origem'] == {'pagina': 'WillT', 'x': 64, 'y': 32},
                f'região no atlas: {reg["l"]}x{reg["a"]}, veio de {reg["origem"]}')
        confere(mj['texturas']['cluts'][0]['cores_ps1'][:3] == ['0000', '7fff', '001f'], 'paleta exportada em palavras do PS1')
        atlas = open(os.path.join(saida, 'tex', 'atlas_4bits.bin'), 'rb').read()
        confere(atlas[0] == 0x11 and atlas[4] == 0x22, f'atlas de 4 bits: primeiros bytes {atlas[:6].hex()}')
        confere(mj['conferencia_com_o_disco']['WillC']['animacoes_no_disco'][0]['svtx'] == 'WiS1V',
                'o executável GOOL do disco confirma a animação WiS1V')
        confere(len(mj['sprites']['crash']) == 1 and len(mj['sprites']['crash'][0]['quadros']) == 2, 'sprite de 2 quadros recortado')
        som = next(s for s in mj['sons'] if s['nome'] == 'jmp0A')
        confere(som.get('amostras') == 1120, 'som jmp0A exportado (.vag e .wav)')
        vagf = open(os.path.join(saida, 'snd', 'jmp0A.vag'), 'rb').read()
        confere(vagf[:4] == b'VAGp' and vagf[48 + 16:] == adpcm, 'o .vag guarda o ADPCM original intacto')
        for arq in ('previews/crash/WILLY_STANCE1.png', 'previews/crash/WILLY_STANCE1.gif', 'CATALOGO.md', 'indice.json'):
            confere(os.path.isfile(os.path.join(saida, arq)), f'existe {arq}')
        confere(mj['orcamento']['bytes_das_animacoes'] == 288, f'orçamento: {mj["orcamento"]["bytes_das_animacoes"]} bytes de animação')

    print(f'\n{"TUDO CERTO" if not falhas else str(len(falhas)) + " FALHA(S)"}')
    return 1 if falhas else 0


if __name__ == '__main__':
    sys.exit(principal())
