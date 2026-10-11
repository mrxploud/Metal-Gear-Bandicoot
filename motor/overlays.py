"""Reempacota os módulos recompilados de cada área no STAGE.DIR do MGS.

Preserva os recursos das fases e o disco original. O diretório contém nomes de
8 bytes e posições em setores; cada fase começa por DATACNF e seu módulo .bin.

Cada fase usa o módulo ligado pelo linker contra o executável da fusão, quando
todo o código dela é C. As que não têm fonte, ou que ainda têm funções em
assembly cru (palavras fixas com os endereços de 1999), usam o módulo original
do disco relocado por relocar.py.
"""
import hashlib
import json
import re
import struct
from pathlib import Path

import relocar

SETOR = 2048


def alinhar(tamanho):
    return (tamanho + SETOR - 1) // SETOR * SETOR


def substituir_modulos(dados, modulos):
    """Devolve um STAGE.DIR novo, validando os limites antes de alterar bytes."""
    if len(dados) < SETOR or len(dados) % SETOR:
        raise ValueError('STAGE.DIR deve conter setores completos')
    tabela = struct.unpack_from('<I', dados)[0]
    if tabela == 0 or tabela % 12 or tabela + 4 > SETOR:
        raise ValueError('tabela de fases inválida')
    entradas = []
    for pos in range(4, tabela + 4, 12):
        nome, setor = struct.unpack_from('<8sI', dados, pos)
        nome = nome.rstrip(b'\0').decode('ascii')
        entradas.append((nome, setor * SETOR, pos))
    if len({nome for nome, _, _ in entradas}) != len(entradas):
        raise ValueError('nomes de fases repetidos')
    faltantes = set(modulos) - {nome for nome, _, _ in entradas}
    if faltantes:
        raise ValueError('fases ausentes no disco: ' + ', '.join(sorted(faltantes)))
    # A ordem física pode ser diferente da ordem dos nomes na tabela.
    entradas.sort(key=lambda e: e[1])
    offsets = [inicio for _, inicio, _ in entradas]
    if offsets[0] < SETOR or len(set(offsets)) != len(offsets) or offsets[-1] >= len(dados):
        raise ValueError('posições de fases inválidas')
    saida = bytearray(dados[:offsets[0]])
    for i, (nome, inicio, pos) in enumerate(entradas):
        fim = offsets[i + 1] if i + 1 < len(offsets) else len(dados)
        bloco = bytearray(dados[inicio:fim])
        struct.pack_into('<I', saida, pos + 8, len(saida) // SETOR)
        if nome in modulos:
            setores_cnf, _, setores_fase = struct.unpack_from('<BBH', bloco)
            _, modo, ext, tamanho = struct.unpack_from('<HBBI', bloco, 4)
            cabecalho = setores_cnf * SETOR
            fim_bin = cabecalho + alinhar(tamanho)
            if (setores_cnf == 0 or modo != ord('s') or ext != ord('b') or
                    not tamanho or fim_bin > setores_fase * SETOR or
                    setores_fase * SETOR > len(bloco)):
                raise ValueError(f'{nome}: módulo não é o primeiro bloco .sound/.bin válido')
            novo = bytes(modulos[nome])
            if not novo:
                raise ValueError(f'{nome}: módulo vazio')
            preenchido = novo + bytes(alinhar(len(novo)) - len(novo))
            delta = (len(preenchido) - alinhar(tamanho)) // SETOR
            if not 0 < setores_fase + delta <= 0x7fff:
                raise ValueError(f'{nome}: fase excede o tamanho suportado')
            struct.pack_into('<H', bloco, 2, setores_fase + delta)
            struct.pack_into('<I', bloco, 8, len(novo))
            bloco = bloco[:cabecalho] + preenchido + bloco[fim_bin:]
        saida.extend(bloco)
    return bytes(saida)


def carregar_modulos(exe):
    """Carrega somente módulos pertencentes à mesma compilação do executável."""
    exe = Path(exe)
    manifesto = exe.with_name('dev_overlays.json')
    if not manifesto.exists():
        return None
    info = json.loads(manifesto.read_text(encoding='utf-8'))
    if info.get('format') != 1:
        raise ValueError('versão desconhecida de dev_overlays.json')
    if hashlib.sha256(exe.read_bytes()).hexdigest() != info['exe']['sha256']:
        raise ValueError('executável e dev_overlays.json são de compilações diferentes')
    modulos = {}
    for nome, entrada in info['overlays'].items():
        arquivo = manifesto.parent / entrada['file']
        dados = arquivo.read_bytes()
        if hashlib.sha256(dados).hexdigest() != entrada['sha256']:
            raise ValueError(f'{nome}: módulo diferente do registrado na compilação')
        modulos[nome] = dados
    if not modulos:
        raise ValueError('manifesto sem módulos de fase')
    return modulos


COMENTARIO = re.compile(r'/\*.*?\*/|//[^\n]*', re.S)
# Número com cara de endereço do executável ou de módulo (0x80010000..0x800FFFFF).
ENDERECO = re.compile(r'\b0x800[0-9a-f]{5}(?![0-9a-f])', re.I)


def endereco_fixo(arquivo):
    """O fonte tem função em assembly cru (INCLUDE_ASM) ou um endereço escrito como número?"""
    texto = COMENTARIO.sub('', arquivo.read_text(encoding='latin-1'))
    return 'INCLUDE_ASM' in texto or any(0x80010000 <= int(m, 16) for m in ENDERECO.findall(texto))


def fases_com_asm_fixo(obj_dev):
    """Fases cujo módulo leva código ou dados com endereços de 1999 que o linker não reloca:
    funções INCLUDE_ASM (palavras fixas) e tabelas escritas com o número do endereço,
    como { 0x92bc, (NEWCHARA *)0x800c8654 } na lista de personagens da fase."""
    fonte = Path(obj_dev).parent / 'source'
    fixos = {}
    fases = set()
    for f in Path(obj_dev).glob('linker_command_file_*_lhs.txt'):
        fase = f.name[len('linker_command_file_'):-len('_lhs.txt')]
        incluidos = re.findall(r'include\s+"([^"]+)\.obj",\s*overlay', f.read_text(encoding='latin-1'), re.I)
        for i in incluidos:
            rel = Path(i).as_posix().split('obj_dev/')[-1]
            c = fonte / (rel + '.c')
            if c not in fixos:
                cabecalhos = list(c.parent.glob('*.h')) if c.exists() else []
                fixos[c] = c.exists() and any(endereco_fixo(x) for x in [c] + cabecalhos)
            if fixos[c]:
                fases.add(fase)
                break
    return fases


def saltos_ruins(dados, mapa_fase, texto_exe):
    """Saltos (J/JAL) e funções da tabela de personagens que não caem em código: endereços de 1999."""
    secoes = relocar.ler_mapa(mapa_fase)[1]
    base = secoes['overlay.data'][0]
    texto = secoes['overlay.text']
    dentro = lambda a: texto[0] <= a < texto[1] or texto_exe[0] <= a < texto_exe[1]
    ruins = []
    for o in range(texto[0] - base, texto[1] - base, 4):
        w = struct.unpack_from('<I', dados, o)[0]
        if w >> 26 in (2, 3):
            alvo = ((base + o) & 0xF0000000) | (w & 0x3FFFFFF) << 2
            if not dentro(alvo):
                ruins.append('%08X: salto para %08X' % (base + o, alvo))
    for o in range(0, 0x800, 8):
        classe, funcao = struct.unpack_from('<II', dados, o)
        if classe == 0 and funcao == 0:
            break
        if not dentro(funcao):
            ruins.append('personagem %04X -> %08X' % (classe & 0xFFFF, funcao))
    return ruins


def modulos_da_fusao(exe, stage_dir, exe_original, relocar_tambem=()):
    """{fase: módulo} para todas as fases do STAGE.DIR, e {fase: 'compilado' | 'relocado'}."""
    exe = Path(exe)
    obj = relocar.MGS / 'obj'
    if not (obj / 'asm.map').exists() or not (obj / '_mgsi.exe').exists():
        raise ValueError('falta a compilação original do mgs_reversing (python build.py, sem variante): '
                         'o relocador precisa do mapa do executável de 1999')
    if (obj / '_mgsi.exe').read_bytes() != Path(exe_original).read_bytes():
        raise ValueError('obj/_mgsi.exe não é o executável do disco: rode a compilação original de novo')
    ligados = carregar_modulos(exe) or {}
    fixos = fases_com_asm_fixo(exe.parent)
    ctx = relocar.preparar(mapa_novo=exe.parent / 'asm.map', exe_novo=exe)
    modulos, origem = {}, {}
    texto_exe = relocar.ler_mapa(exe.parent / 'asm.map')[1]['.text']
    for fase, dados in relocar.extrair_modulos(stage_dir).items():
        if fase in ligados and fase not in fixos and fase not in relocar_tambem:
            ruins = saltos_ruins(ligados[fase], exe.parent / ('asm_%s_lhs.map' % fase), texto_exe)
            if ruins:
                raise ValueError('%s: o módulo compilado salta para fora do código: %s' % (fase, ruins[:4]))
            modulos[fase], origem[fase] = ligados[fase], 'compilado'
        else:
            modulos[fase], _ = relocar.relocar_modulo(dados, ctx)
            origem[fase] = 'relocado'
    return modulos, origem
