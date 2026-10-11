"""Leitor do contêiner NSF do Crash Bandicoot 1.

Um .NSF é uma fila de páginas de 64 KB. Algumas vêm comprimidas (magia 0x1235) e viram 64 KB ao abrir.
Uma página normal guarda "entradas" (magia 0x100FFFF), e cada entrada é uma lista de itens (blocos de bytes).
Uma página de textura (tipo 1) É a textura: os 64 KB inteiros são um pedaço de 256x128 palavras da VRAM.

Formato conferido contra o c1 de wurlyfox (src/ns.h e NSPageDecompress em src/ns.c).
"""
import struct

MAGIA_PAGINA = 0x1234
MAGIA_COMPRIMIDA = 0x1235
MAGIA_ENTRADA = 0x100FFFF
TAM_PAGINA = 0x10000

ALFABETO = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_!'

# última letra do nome -> tipo da entrada (NSEIDType no c1)
TIPO_PELA_LETRA = {'V': 1, 'G': 2, 'W': 3, 'S': 4, 'T': 5, 'L': 6, 'Z': 7, 'C': 11, 'A': 12, 'M': 13,
                   'N': 14, 'D': 15, 'I': 16, 'P': 17, 'U': 18, 'B': 19, 'X': 20}
NOME_DO_TIPO = {1: 'SVTX', 2: 'TGEO', 3: 'WGEO', 4: 'SLST', 5: 'TPAG', 6: 'LDAT', 7: 'ZDAT', 11: 'GOOL',
                12: 'ADIO', 13: 'MIDI', 14: 'INST', 15: 'IMAG', 16: 'LINK', 17: 'MDAT', 18: 'IPAL',
                19: 'PBAK', 20: 'CVTX'}


class ErroDeNSF(Exception):
    pass


def nome_do_eid(eid):
    """0x........ -> 'WiS1V'. Os EIDs do Crash são 5 caracteres de 6 bits + um bit 1 no fim."""
    if not eid & 1:
        return f'[{eid:X}]'
    eid >>= 1
    letras = []
    for _ in range(5):
        letras.append(ALFABETO[eid & 0x3F])
        eid >>= 6
    return ''.join(reversed(letras))


def eid_do_nome(nome):
    if len(nome) != 5:
        raise ValueError(f'nome de entrada tem 5 caracteres: {nome!r}')
    eid = 0
    for letra in nome:
        eid = (eid << 6) | ALFABETO.index(letra)
    return (eid << 1) | 1


def descomprimir_pagina(dados, pos):
    """Abre a página que começa em dados[pos]. Devolve (64 KB, posição da próxima página)."""
    magia, = struct.unpack_from('<H', dados, pos)
    if magia == MAGIA_PAGINA:
        pagina = dados[pos:pos + TAM_PAGINA]
        if len(pagina) != TAM_PAGINA:
            raise ErroDeNSF(f'página cortada em {pos:#x}')
        return pagina, pos + TAM_PAGINA
    if magia != MAGIA_COMPRIMIDA:
        raise ErroDeNSF(f'magia {magia:#06x} em {pos:#x}: não é página')
    comprimento, pular = struct.unpack_from('<II', dados, pos + 4)
    if comprimento > TAM_PAGINA:
        raise ErroDeNSF(f'página comprimida com comprimento {comprimento:#x} em {pos:#x}')
    src = pos + 12
    saida = bytearray()
    while len(saida) < comprimento:
        prefixo = dados[src]
        src += 1
        if prefixo & 0x80:                       # cópia de trás: 12 bits de distância, 3 de tamanho
            par = (prefixo << 8) | dados[src]
            src += 1
            tamanho = par & 7
            distancia = (par >> 3) & 0xFFF
            tamanho = 64 if tamanho == 7 else tamanho + 3
            if distancia == 0 or distancia > len(saida):
                raise ErroDeNSF(f'cópia inválida (distância {distancia}) em {src:#x}')
            for _ in range(tamanho):             # byte a byte: as cópias podem se sobrepor
                saida.append(saida[-distancia])
        else:                                    # literais
            saida += dados[src:src + prefixo]
            src += prefixo
    src += pular
    resto = TAM_PAGINA - comprimento             # o fim da página vem sem compressão
    saida = saida[:comprimento] + dados[src:src + resto]
    if len(saida) != TAM_PAGINA:
        raise ErroDeNSF(f'página comprimida em {pos:#x} abriu com {len(saida):#x} bytes')
    return bytes(saida), src + resto


def paginas(dados):
    """Gera (índice, bytes de 64 KB) de cada página de um .NSF."""
    pos = 0
    indice = 0
    while pos + 12 <= len(dados):
        pagina, pos = descomprimir_pagina(dados, pos)
        yield indice, pagina
        indice += 1


class Entrada:
    __slots__ = ('eid', 'nome', 'tipo', 'itens', 'pagina', 'tipo_da_pagina')

    def __init__(self, eid, tipo, itens, pagina, tipo_da_pagina):
        self.eid = eid
        self.nome = nome_do_eid(eid)
        self.tipo = tipo
        self.itens = itens
        self.pagina = pagina
        self.tipo_da_pagina = tipo_da_pagina

    @property
    def nome_do_tipo(self):
        return NOME_DO_TIPO.get(self.tipo, f'tipo{self.tipo}')

    def __repr__(self):
        return f'<{self.nome} {self.nome_do_tipo} {len(self.itens)} itens>'


def entradas_da_pagina(indice, pagina):
    magia, tipo_pagina = struct.unpack_from('<HH', pagina, 0)
    if magia != MAGIA_PAGINA:
        raise ErroDeNSF(f'página {indice}: magia {magia:#06x} depois de abrir')
    if tipo_pagina == 1:                         # textura: {magia, tipo, eid, tipo da entrada, soma}
        eid, = struct.unpack_from('<I', pagina, 4)
        yield Entrada(eid, 5, [pagina], indice, 1)
        return
    quantas, = struct.unpack_from('<I', pagina, 8)
    if quantas > 256:
        raise ErroDeNSF(f'página {indice}: {quantas} entradas')
    desloc = struct.unpack_from(f'<{quantas + 1}I', pagina, 16)
    for i in range(quantas):
        ini, fim = desloc[i], desloc[i + 1]
        magia_e, eid, tipo, n_itens = struct.unpack_from('<IIII', pagina, ini)
        if magia_e != MAGIA_ENTRADA:
            raise ErroDeNSF(f'página {indice}, entrada {i}: magia {magia_e:#x}')
        d = struct.unpack_from(f'<{n_itens + 1}I', pagina, ini + 16)
        itens = [pagina[ini + d[k]:ini + d[k + 1]] for k in range(n_itens)]
        yield Entrada(eid, tipo, itens, indice, tipo_pagina)


def entradas(dados):
    """Todas as entradas de um .NSF, na ordem do arquivo."""
    for indice, pagina in paginas(dados):
        yield from entradas_da_pagina(indice, pagina)
