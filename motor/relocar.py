"""Reloca o módulo original de uma fase do MGS (STAGE.DIR) para o executável da fusão.

Treze fases ainda não têm código-fonte no mgs_reversing (Passagem Subterrânea, telhado da torre, Hind D,
Armazém, REX, Liquid, a fuga de jipe e algumas versões "vermelhas"). O módulo delas no disco foi ligado
ao executável original: chama funções e lê variáveis nos endereços do MGS de 1999, e espera ser carregado
logo depois do fim do executável original (0x800C3208). O executável da fusão é maior (o Crash mora nele)
e tudo mudou de lugar. Este script reescreve cada endereço do módulo:

- J/JAL para funções do executável ou do próprio módulo;
- pares LUI + ADDIU/LW/SW/... (%hi/%lo), inclusive com índice somado (LUI; ADDU; LW);
- acessos relativos ao gp (variáveis pequenas do executável, .sdata/.sbss);
- palavras de 32 bits com endereços (tabelas de funções, tabelas de salto do switch, ponteiros).

Endereços do executável viram "símbolo + deslocamento" pelo mapa do executável original (compilação que bate
com o disco, repos/mgs_reversing/obj/asm.map) e voltam a ser endereço pelo mapa da fusão (obj_dev/asm.map).

    python -I motor/relocar.py --validar     confere com as 30 fases que o linker gera com o mesmo leiaute

Na validação, o módulo original de cada uma dessas fases é relocado e comparado byte a byte com o que o
linker gerou (fora dos bytes não inicializados, que no original são lixo da máquina de quem compilou).
"""
import argparse
import bisect
import json
import re
import struct
import sys
from pathlib import Path

MOTOR = Path(__file__).resolve().parent
FUSAO = MOTOR.parent
MGS = FUSAO / 'repos' / 'mgs_reversing'

EXE_INICIO = 0x80010000
GP = 28
# Registradores que um JAL pode destruir (o resto é salvo pela função chamada).
DESTRUIDOS_NA_CHAMADA = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 24, 25, 31}
CARGAS = {0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26}
GUARDAS = {0x28, 0x29, 0x2A, 0x2B, 0x2E}
COP2_MEM = {0x32, 0x3A}  # LWC2 / SWC2


class ErroRelocacao(Exception):
    pass


def ler_mapa(caminho):
    """Símbolos e seções de um mapa do psylink."""
    texto = Path(caminho).read_text(encoding='latin-1')
    simbolos = {}
    for m in re.finditer(r'^\s+([0-9A-F]{8})\s+(\S+)\s*$', texto, re.M):
        simbolos.setdefault(m[2], int(m[1], 16))
    secoes = {m[3]: (int(m[1], 16), int(m[2], 16) + 1)
              for m in re.finditer(r'^ ([0-9A-F]{8}) ([0-9A-F]{8}) [0-9A-F]{8} [0-9A-F]{8} \w+\s+(\S+)\s*$', texto, re.M)}
    return simbolos, secoes


def gp_do_executavel(exe):
    """O gp é carregado no começo do programa por um par LUI gp / ADDIU gp."""
    dados = Path(exe).read_bytes()[0x800:]
    achados = set()
    for i in range(0, len(dados) - 8, 4):
        w = struct.unpack_from('<I', dados, i)[0]
        if w >> 16 == 0x3C1C:
            w2 = struct.unpack_from('<I', dados, i + 4)[0]
            if w2 >> 16 == 0x279C:
                achados.add(((w & 0xFFFF) << 16) + sext16(w2 & 0xFFFF) & 0xFFFFFFFF)
    if len(achados) != 1:
        raise ErroRelocacao('gp ambíguo em %s: %s' % (exe, sorted(map(hex, achados))))
    return achados.pop()


def sext16(v):
    return v - 0x10000 if v & 0x8000 else v


class Traducao:
    """Endereço do executável/módulo original -> endereço na fusão."""

    def __init__(self, mapa_antigo, mapa_novo, base_antiga, base_nova, tamanho):
        antigos, self.secoes_antigas = mapa_antigo
        self.novos, _ = mapa_novo
        self.base_antiga, self.base_nova, self.tamanho = base_antiga, base_nova, tamanho
        # Só símbolos do executável (os do módulo da fase, no mapa de fase, ficam de fora).
        pares = sorted((a, n) for n, a in antigos.items() if EXE_INICIO <= a < base_antiga)
        self.enderecos = [a for a, _ in pares]
        self.nomes = [n for _, n in pares]
        self.instaveis = []

    def no_modulo(self, a):
        return self.base_antiga <= a <= self.base_antiga + self.tamanho

    def no_executavel(self, a):
        return EXE_INICIO <= a < self.base_antiga

    def relocavel(self, a):
        return self.no_executavel(a) or self.no_modulo(a)

    def __call__(self, a, exato=False):
        if self.no_modulo(a):
            return a - self.base_antiga + self.base_nova
        if not self.no_executavel(a):
            return a
        i = bisect.bisect_right(self.enderecos, a) - 1
        if i < 0:
            raise ErroRelocacao('endereço %08X antes do primeiro símbolo' % a)
        # Vários nomes podem dividir o endereço; usa um que exista no mapa novo.
        j = i
        while j >= 0 and self.enderecos[j] == self.enderecos[i]:
            if self.nomes[j] in self.novos:
                break
            j -= 1
        else:
            j = -1
        if j < 0 or self.enderecos[j] != self.enderecos[i]:
            raise ErroRelocacao('símbolo em %08X (%s) não existe na fusão' % (self.enderecos[i], self.nomes[i]))
        nome, desloc = self.nomes[j], a - self.enderecos[j]
        if exato and desloc:
            raise ErroRelocacao('salto para %08X = %s+%d, não é começo de função' % (a, nome, desloc))
        if desloc:
            # Meio de um símbolo: só é seguro se o vizinho seguinte andou junto.
            k = bisect.bisect_right(self.enderecos, a)
            if k < len(self.nomes):
                prox = self.nomes[k]
                if prox not in self.novos or (self.novos[prox] - self.novos[nome] != self.enderecos[k] - self.enderecos[j]):
                    self.instaveis.append((a, nome, desloc))
        return self.novos[nome] + desloc


def valida(w):
    """Instrução que o compilador da época poderia ter gerado (filtro para achar o fim do código)."""
    op = w >> 26
    if w == 0:
        return True
    if op == 0:
        f = w & 63
        if f in (1, 5, 10, 11, 14, 15, 20, 21, 22, 23, 28, 29, 30, 31, 40, 41, 44, 45, 46, 47) or f >= 48:
            return False
        if f in (8, 9, 12, 13, 17, 19, 24, 25, 26, 27):
            return True  # jr, jalr, syscall, break, mthi, mtlo, mult/div: não escrevem em rd
        if f in (16, 18):  # mfhi/mflo
            return (w >> 11) & 31 != 0
        return (w >> 11) & 31 != 0  # escreve em zero: não é código de compilador
    if op == 1:
        return (w >> 16) & 31 in (0, 1, 16, 17)
    if 0x14 <= op <= 0x1F or op in (0x27, 0x2C, 0x2D, 0x2F) or op >= 0x34 and op not in (0x3A,):
        return False
    if op in (0x10, 0x11, 0x13, 0x30, 0x31, 0x33, 0x38, 0x39, 0x3B):
        return op == 0x10  # só COP0 (e o COP2 abaixo)
    if op in (8, 9, 10, 11, 12, 13, 14, 15) or op in CARGAS:
        if (w >> 16) & 31 == 0:
            return False
        if op == 15 and (w >> 21) & 31:
            return False
    if (op in CARGAS or op in GUARDAS) and (w >> 21) & 31 == 0:
        return False  # endereço absoluto pequeno: é dado (ponteiro), não código
    return True


def faixa_de_codigo(dados, base_antiga):
    """[início, fim) do .text do módulo: começa depois do .data e termina antes do .rdata."""
    n = len(dados) // 4
    w = lambda i: struct.unpack_from('<I', dados, 4 * i)[0]
    prologos = [i for i in range(n) if w(i) >> 16 == 0x27BD and w(i) & 0x8000]
    if not prologos:
        raise ErroRelocacao('nenhuma função no módulo')
    inicio = prologos[0]
    # Volta até o começo de funções folha que fiquem antes do primeiro prólogo e sejam chamadas por JAL.
    fim = inicio
    while fim < n and valida(w(fim)):
        fim += 1
    alvos = set()
    for i in range(inicio, fim):
        if w(i) >> 26 == 3:
            alvo = 0x80000000 | (w(i) & 0x3FFFFFF) << 2
            if base_antiga <= alvo < base_antiga + len(dados):
                alvos.add((alvo - base_antiga) // 4)
    antes = [a for a in alvos if a < inicio]
    if antes:
        novo = min(antes)
        if all(valida(w(i)) for i in range(novo, inicio)):
            inicio = novo
    # O .rdata pode começar com palavras que parecem instruções; o código termina no último "jr ra" + atraso
    # e mais as funções que terminam em salto (cauda) logo depois.
    ultimo = max(i for i in range(inicio, fim) if w(i) == 0x03E00008)
    return 4 * inicio, 4 * fim, 4 * (ultimo + 2)


def efeito(y, vivos):
    """Aplica uma instrução ao conjunto de registradores que guardam a parte alta. Devolve (vivos, é_uso)."""
    op, rs, rt, rd = y >> 26, (y >> 21) & 31, (y >> 16) & 31, (y >> 11) & 31
    escreve, uso = set(), False
    if op == 0:
        f = y & 63
        if f in (0x20, 0x21, 0x25) and (rs in vivos) != (rt in vivos):
            return vivos | {rd}, False  # base + índice: continua "alto"
        if f not in (8, 12, 13, 17, 19, 24, 25, 26, 27):
            escreve.add(rd)
    elif op in (8, 9, 13) and rs in vivos:
        uso = True
        escreve.add(rt)
    elif op in CARGAS or op in GUARDAS or op in COP2_MEM:
        uso = rs in vivos
        if op in CARGAS:
            escreve.add(rt)
    elif op in (8, 9, 10, 11, 12, 13, 14, 15):
        escreve.add(rt)
    elif op in (0x10, 0x12) and rs in (0, 2):  # mfc0/mfc2/cfc2
        escreve.add(rt)
    return vivos - escreve, uso


def sucessores(w, p, base, inicio, fim):
    """Para um desvio/salto em p: (para onde vai depois do atraso, é chamada). None se não é desvio."""
    y = w(p)
    op, rs, rt = y >> 26, (y >> 21) & 31, (y >> 16) & 31
    alvo = p + 4 + 4 * sext16(y & 0xFFFF)
    if op in (4, 5, 6, 7) or (op == 1 and rt in (0, 1)):
        if op == 4 and rs == 0 and rt == 0:
            return [alvo], False  # b
        return [p + 8, alvo], False
    if op == 1 and rt in (16, 17) or op == 3 or (op == 0 and (y & 63) == 9):
        return [p + 8], True
    if op == 2:
        destino = ((base + p) & 0xF0000000 | (y & 0x3FFFFFF) << 2) - base
        return ([destino] if inicio <= destino < fim else []), False
    if op == 0 and (y & 63) == 8:
        # jr ra: fim da função. Outro registrador: o switch; os casos vêm logo depois.
        return ([] if rs == 31 else [p + 8]), False
    return None


def usos_do_hi(w, o, inicio, fim, base):
    """Instruções que usam a parte alta carregada pelo LUI em o, seguindo os dois lados de cada desvio."""
    vivos0 = frozenset({(w(o) >> 16) & 31})
    pilha = []
    anterior = sucessores(w, o - 4, base, inicio, fim) if o - 4 >= inicio else None
    if anterior is not None:  # o LUI está no atraso de um desvio
        destinos, chamada = anterior
        v = vivos0 - DESTRUIDOS_NA_CHAMADA if chamada else vivos0
        pilha += [(d, v) for d in destinos]
    else:
        pilha.append((o + 4, vivos0))
    vistos, usos, passos = set(), set(), 0
    while pilha and passos < 4000:
        p, vivos = pilha.pop()
        while vivos and inicio <= p < fim and (p, vivos) not in vistos and passos < 4000:
            vistos.add((p, vivos))
            passos += 1
            y = w(p)
            desvio = sucessores(w, p, base, inicio, fim)
            vivos, uso = efeito(y, vivos)
            if uso:
                usos.add(p)
            if desvio is None:
                p += 4
                continue
            # o atraso roda antes do desvio
            vivos, uso = efeito(w(p + 4), vivos)
            if uso:
                usos.add(p + 4)
            destinos, chamada = desvio
            if chamada:
                vivos = vivos - DESTRUIDOS_NA_CHAMADA
            vivos = frozenset(vivos)
            if not destinos:
                break
            pilha += [(d, vivos) for d in destinos[1:]]
            p = destinos[0]
        passos += 1
    return usos


def relocar(dados, traduz, gp_antigo, gp_novo):
    """Devolve (módulo relocado, relatório)."""
    dados = bytearray(dados)
    base_a, base_n = traduz.base_antiga, traduz.base_nova
    inicio, fim_valido, fim_jr = faixa_de_codigo(bytes(dados), base_a)
    fim = fim_valido
    rel = {'codigo': [inicio, fim], 'jal': 0, 'hilo': 0, 'gp': 0, 'ponteiros': 0, 'avisos': []}
    w = lambda o: struct.unpack_from('<I', dados, o)[0]
    novo = {}  # deslocamento -> palavra nova

    def troca(o, palavra):
        if o in novo and novo[o] != palavra:
            raise ErroRelocacao('conflito em +%X: %08X x %08X' % (o, novo[o], palavra))
        novo[o] = palavra

    # 1. Saltos.
    for o in range(inicio, fim, 4):
        x = w(o)
        if x >> 26 in (2, 3):
            alvo = ((base_a + o) & 0xF0000000) | (x & 0x3FFFFFF) << 2
            if traduz.relocavel(alvo):
                n = traduz(alvo, exato=True)
                troca(o, (x & 0xFC000000) | (n >> 2) & 0x3FFFFFF)
                rel['jal'] += 1

    # 2. gp: variáveis pequenas do executável.
    for o in range(inicio, fim, 4):
        x = w(o)
        op, rs = x >> 26, (x >> 21) & 31
        if rs == GP and (op in CARGAS or op in GUARDAS or op in COP2_MEM or op == 9):
            a = gp_antigo + sext16(x & 0xFFFF)
            n = traduz(a)
            d = n - gp_novo
            if not -0x8000 <= d < 0x8000:
                raise ErroRelocacao('+%X: %08X longe demais do gp novo' % (o, n))
            troca(o, (x & 0xFFFF0000) | d & 0xFFFF)
            rel['gp'] += 1

    # 3. Pares %hi/%lo.
    usos_de = {}
    for o in range(inicio, fim, 4):
        x = w(o)
        if x >> 26 != 0x0F or (x >> 21) & 31:
            continue
        hi = x & 0xFFFF
        if not (EXE_INICIO >> 16) <= hi <= (base_a + len(dados) + 0x8000) >> 16:
            continue
        usos = sorted(usos_do_hi(w, o, inicio, fim, base_a))
        if not usos:
            rel['avisos'].append('LUI %04X em +%X sem uso' % (hi, o))
            continue
        alvos = []
        for u in usos:
            y = w(u)
            lo = (y & 0xFFFF) if y >> 26 == 13 else sext16(y & 0xFFFF)
            alvos.append((u, y, (hi << 16) + lo & 0xFFFFFFFF))
        if not any(traduz.relocavel(a) for _, _, a in alvos):
            continue
        novos = [(u, y, traduz(a)) for u, y, a in alvos]
        his = {((n + 0x8000) >> 16 if y >> 26 != 13 else n >> 16) for _, y, n in novos}
        if len(his) != 1:
            raise ErroRelocacao('LUI em +%X serve endereços que se separaram: %s' % (
                o, ', '.join('%08X->%08X' % (a, n) for (_, _, a), (_, _, n) in zip(alvos, novos))))
        novo_hi = his.pop()
        troca(o, (x & 0xFFFF0000) | novo_hi)
        for u, y, n in novos:
            lo = n - (novo_hi << 16)
            if not -0x8000 <= lo < (0x10000 if y >> 26 == 13 else 0x8000):
                raise ErroRelocacao('+%X: parte baixa fora do alcance' % u)
            troca(u, (y & 0xFFFF0000) | lo & 0xFFFF)
            usos_de.setdefault(u, set()).add(o)
        rel['hilo'] += 1

    # 4. Palavras com endereço, fora do código (dados, tabelas de salto e o lixo não inicializado).
    for o in list(range(0, inicio, 4)) + list(range(fim, len(dados) - 3, 4)):
        x = w(o)
        if traduz.relocavel(x):
            troca(o, traduz(x))
            rel['ponteiros'] += 1

    for o, palavra in novo.items():
        struct.pack_into('<I', dados, o, palavra)
    if traduz.instaveis:
        rel['avisos'] += ['%08X = %s+%d: vizinhos se moveram' % t for t in traduz.instaveis]
    return bytes(dados), rel


def preparar(mapa_antigo=MGS / 'obj' / 'asm.map', mapa_novo=MGS / 'obj_dev' / 'asm.map',
             exe_antigo=MGS / 'obj' / '_mgsi.exe', exe_novo=MGS / 'obj_dev' / '_mgsi.exe'):
    antigo, novo = ler_mapa(mapa_antigo), ler_mapa(mapa_novo)
    return {
        'antigo': antigo, 'novo': novo,
        'base_antiga': antigo[0]['_bss_orgend'], 'base_nova': novo[0]['_bss_orgend'],
        'gp_antigo': gp_do_executavel(exe_antigo), 'gp_novo': gp_do_executavel(exe_novo),
    }


def relocar_modulo(dados, ctx):
    traduz = Traducao(ctx['antigo'], ctx['novo'], ctx['base_antiga'], ctx['base_nova'], len(dados))
    return relocar(dados, traduz, ctx['gp_antigo'], ctx['gp_novo'])


def extrair_modulos(stage_dir):
    """{fase: bytes do módulo .bin} do STAGE.DIR original."""
    d = Path(stage_dir).read_bytes()
    tabela = struct.unpack_from('<I', d)[0]
    saida = {}
    for pos in range(4, tabela + 4, 12):
        nome, setor = struct.unpack_from('<8sI', d, pos)
        b = setor * 2048
        _, modo, ext, tam = struct.unpack_from('<HBBI', d, b + 4)
        if (modo, ext) == (ord('s'), ord('b')):
            saida[nome.rstrip(b'\0').decode()] = d[b + d[b] * 2048: b + d[b] * 2048 + tam]
    return saida


def validar(stage_dir):
    ctx = preparar()
    originais = extrair_modulos(stage_dir)
    manifesto = json.loads((MGS / 'obj_dev' / 'dev_overlays.json').read_text(encoding='utf-8'))
    total_ruim = 0
    for fase, ent in sorted(manifesto['overlays'].items()):
        ligado = (MGS / 'obj_dev' / ent['file']).read_bytes()
        original = originais[fase]
        if len(ligado) != len(original):
            continue
        zerado = (MGS / 'obj' / (fase + '_lhs.bin')).read_bytes()  # o mesmo leiaute, com zeros no lugar do lixo
        lixo = {i for i in range(len(original)) if original[i] != zerado[i]}
        try:
            relocado, rel = relocar_modulo(original, ctx)
        except ErroRelocacao as e:
            print('%-7s ERRO %s' % (fase, e))
            total_ruim += 1
            continue
        ruins = [i for i in range(0, len(ligado), 4)
                 if relocado[i:i + 4] != ligado[i:i + 4] and not any(j in lixo for j in range(i, i + 4))]
        total_ruim += bool(ruins)
        print('%-7s %s  jal %4d  hi/lo %4d  gp %4d  ponteiros %4d  avisos %d  código %X-%X' % (
            fase, 'OK  ' if not ruins else 'DIF %d' % len(ruins), rel['jal'], rel['hilo'], rel['gp'],
            rel['ponteiros'], len(rel['avisos']), *rel['codigo']))
        for i in ruins[:6]:
            print('        +%05X  original %08X  relocado %08X  linker %08X' % (
                i, *(struct.unpack_from('<I', b, i)[0] for b in (original, relocado, ligado))))
        for a in rel['avisos'][:4]:
            print('        aviso:', a)
    return total_ruim


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--validar', action='store_true')
    ap.add_argument('--stage-dir', default=str(MOTOR / 'disco_mgs' / 'MGSI_D1' / 'MGS' / 'STAGE.DIR'))
    a = ap.parse_args()
    if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    if a.validar:
        sys.exit(1 if validar(a.stage_dir) else 0)
    ap.print_help()


if __name__ == '__main__':
    main()
