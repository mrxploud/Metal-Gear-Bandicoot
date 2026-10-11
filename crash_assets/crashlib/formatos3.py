"""Os formatos do Crash Bandicoot 3 (Warped) que mudaram em relação ao Crash 1.

O contêiner NSF é o mesmo (crashlib/nsf.py lê sem mudança). O que mudou:

TGEO  o modelo. Agora são 5 ou 6 itens: cabeçalho de 80 bytes, a fila de polígonos (uma "fita": cada palavra
      de 32 bits acrescenta UM vértice e fecha um triângulo com vértices anteriores), as cores (por vértice do
      triângulo, não mais por triângulo), as texturas (12 bytes, com os UVs dentro: acabou a tabela de 600
      retângulos do Crash 1), as texturas animadas e, se a animação for comprimida, a "posição-base" de cada
      vértice.
SVTX  a animação. Um item por quadro. Modelos pequenos (caixas, Aku Aku) ainda trazem 3 bytes por vértice, mas
      na ordem x, Z, y. Nos modelos "comprimidos" (o Crash) o quadro NÃO traz bytes: traz uma fila de bits.
      Para cada vértice lê-se uma diferença com sinal em X, Y e Z (cada uma com o número de bits que o MODELO
      manda para aquele vértice), soma-se à posição-base do modelo e ao vértice anterior, e fica-se com 1 byte
      por eixo. Não há normal no quadro: a luz do Crash 3 vem das cores do modelo.

Tudo conferido contra o CrashEdit do CBHacks (github.com/cbhacks/CrashEdit, ramo `deprecate`):
Crash/Formats/Crash Formats/Animation/Frame.cs (LoadNew, MakeVertices), Model/ModelEntry.cs (ConvertIndices),
ModelStruct.cs, ModelPosition.cs, ModelTexture.cs, ModelExtendedTexture.cs e
CrashEdit/Utils/OpenTK Integration/AnimationRenderer.cs (RenderFrame). Os nomes de eixo daqui são os do mundo
(x, y para cima, z); o CrashEdit chama o 2º eixo da fila de "Z" e o 3º de "Y" e destroca na hora de desenhar.
"""
import struct

from .nsf import nome_do_eid

CHAVE_NULA = 0x57
FIM_DA_FITA = 0xFFFFFFFF
EID_NULO = 0x6396347F


# ------------------------------------------------------------------------------------------------------
# TGEO do Crash 2/3
# ------------------------------------------------------------------------------------------------------
class Textura3:
    """12 bytes: os 3 cantos (u, v) em pixels dentro da página, a paleta, o modo de cor e a mistura."""
    __slots__ = ('uv', 'uv4', 'clut_x', 'clut_y', 'segmento', 'mistura', 'modo_de_cor', 'pagina', 'bruto')

    def __init__(self, d, pos):
        b = d[pos:pos + 12]
        self.bruto = bytes(b)
        self.uv = [(b[0], b[1]), (b[4], b[5]), (b[8], b[9])]
        self.uv4 = (b[10], b[11])
        self.clut_x = b[2] & 0xF
        self.clut_y = (b[3] << 2) | ((b[2] >> 6) & 3)
        self.segmento = b[6] & 0xF
        self.mistura = (b[6] >> 5) & 3                 # 0 média, 1 soma, 2 subtrai, 3 opaco
        self.modo_de_cor = ((b[6] >> 7) | ((b[7] << 1) & 2)) & 3    # 0 = 4 bits, 1 = 8 bits, 2 = 16 bits
        self.pagina = (b[7] >> 2) & 0x3F               # índice na lista de páginas do cabeçalho do modelo

    def bits_por_pixel(self):
        return (4, 8, 16, 16)[self.modo_de_cor]

    def uvs(self):
        """Os 3 cantos em pixels da página, já com o deslocamento do segmento (colunas de 64 palavras)."""
        ox = (1 << (2 - self.modo_de_cor)) * 64 * self.segmento
        return [(u + ox, v) for u, v in self.uv]

    def chave(self):
        return self.bruto


class Tgeo3:
    """Modelo do Crash 2/3. `triangulos` = lista de dicts {v: (a, b, c), cor: (ia, ib, ic), tex, animada,
    tipo, subtipo, sem_descarte}, com os vértices já na ordem de desenho do CrashEdit."""

    def __init__(self, entrada):
        it = entrada.itens
        if len(it) not in (5, 6):
            raise ValueError(f'{entrada.nome}: TGEO do Crash 3 tem 5 ou 6 itens, este tem {len(it)}')
        cab = it[0]
        self.nome = entrada.nome
        self.cabecalho = bytes(cab)
        self.escala = struct.unpack_from('<3i', cab, 0)
        self.paginas = list(struct.unpack_from('<8I', cab, 0x0C))
        (n_fita, self.desconhecido_30, n_tex, self.n_vertices, n_cores, self.n_paginas, self.n_poligonos,
         n_anim, self.n_especiais) = struct.unpack_from('<9i', cab, 0x2C)
        self.paginas = self.paginas[:self.n_paginas]
        if len(it[1]) != n_fita * 4 or len(it[2]) != n_cores * 4 or len(it[3]) != n_tex * 12 or \
                len(it[4]) != n_anim * 4:
            raise ValueError(f'{self.nome}: contagens do cabeçalho não batem com os itens')
        self.fita = list(struct.unpack_from(f'<{n_fita}I', it[1], 0))
        self.cores = [tuple(it[2][i * 4:i * 4 + 4]) for i in range(n_cores)]          # (r, g, b, extra)
        self.texturas = [Textura3(it[3], i * 12) for i in range(n_tex)]
        self.animadas = list(struct.unpack_from(f'<{n_anim}i', it[4], 0))
        self.comprimido = len(it) == 6
        self.bases = None
        if self.comprimido:
            n = self.n_vertices - self.n_especiais
            if len(it[5]) != n * 4:
                raise ValueError(f'{self.nome}: {len(it[5])} bytes de posições-base, esperava {n * 4}')
            self.bases_bruto = bytes(it[5])
            self.bases = []
            for w in struct.unpack_from(f'<{n}I', it[5], 0):
                # do bit mais alto para o mais baixo: X (7 bits, vale o dobro), Y (8), Z (8), bits de X, de Y, de Z
                self.bases.append(((w >> 25) & 0x7F, (w >> 17) & 0xFF, (w >> 9) & 0xFF,
                                   (w >> 6) & 7, (w >> 3) & 7, w & 7))
        self._montar_triangulos()

    # -- a fita de polígonos ------------------------------------------------------------------------
    def _montar_triangulos(self):
        itens = []                       # ('cor', c1, c2) ou ('tri', campos...)
        vtx = []
        chaves = {}
        v = -self.n_especiais if self.comprimido else 0
        for w in self.fita:
            if w == FIM_DA_FITA:
                break
            if w & 0xFFFF0000:
                t = {'tex': w & 0xFF, 'animada': bool((w >> 8) & 1), 'cor': (w >> 9) & 0x7F,
                     'chave': (w >> 16) & 0xFF, 'repetido': (w >> 26) & 1, 'bandeira': (w >> 27) & 1,
                     'subtipo': (w >> 28) & 3, 'tipo': (w >> 30) & 3}
                if t['repetido']:
                    vtx.append(chaves[t['chave']])
                else:
                    if t['chave'] != CHAVE_NULA:
                        chaves[t['chave']] = v
                    vtx.append(v)
                    v += 1
                itens.append(t)
            else:
                itens.append({'c1': (w >> 2) & 0x7F, 'c2': (w >> 9) & 0x7F})
        self.n_originais = v + (self.n_especiais if self.comprimido else 0)
        tris = []
        ult_cc_valido = -3
        ult_cc = ult_aa = ult_cor = ult_nao_bb = -1
        cur = 0
        n = len(itens)

        def cor_de(i):
            return itens[i]['cor']

        for i, s in enumerate(itens):
            if 'c1' in s:
                ult_cor = i
                continue
            tipo = s['tipo']
            if tipo == 0:
                ult_aa = cur
                ult_nao_bb = i
                c2 = itens[ult_cor]['c1'] if ult_cor + 1 == i else cor_de(i - 1)
                if ult_cor + 1 == i:
                    c3 = itens[ult_cor]['c2']
                elif ult_cor + 2 == i:
                    c3 = itens[ult_cor]['c1']
                else:
                    c3 = cor_de(i - 2)
                tris.append(self._tri((vtx[cur], vtx[cur - 1], vtx[cur - 2]), (s['cor'], c2, c3), s))
            elif tipo == 1:
                ci = -1
                if ult_cor < ult_nao_bb - 2:
                    ci = cor_de(ult_nao_bb - 2)
                elif ult_cor == ult_nao_bb - 2:
                    ci = itens[ult_cor]['c1']
                elif ult_cor == ult_nao_bb - 1:
                    ci = itens[ult_cor]['c2']
                elif ult_cor > ult_nao_bb - 2:
                    ci = itens[ult_cor]['c2']
                c2 = itens[ult_cor]['c1'] if ult_cor + 1 == i else cor_de(i - 1)
                terceiro = vtx[ult_cc] if ult_cc > ult_aa else vtx[ult_aa - 2]
                tris.append(self._tri((vtx[cur], vtx[cur - 1], terceiro), (s['cor'], c2, ci), s))
            elif tipo == 2:
                if i + 2 < n and ult_cc_valido + 2 < i:
                    ult_cc_valido = i
                    tris.append(self._tri((vtx[cur], vtx[cur + 1], vtx[cur + 2]),
                                          (s['cor'], cor_de(i + 1), cor_de(i + 2)), s))
                ult_cc = cur
                ult_nao_bb = i
            cur += 1
        self.triangulos = tris

    def _tri(self, v, c, s):
        """Aplica a regra de desenho do CrashEdit (RenderFrame): quem vira, e que canto de textura vai em cada vértice."""
        tipo, sub = s['tipo'], s['subtipo']
        sem_descarte = sub in (0, 2)
        vira = ((tipo == 2) != (sub == 3)) and not sem_descarte
        if (tipo != 2 and not vira) or (tipo == 2 and sub == 1):
            cantos = (2, 1, 0)
        else:
            cantos = (0, 1, 2)
        if vira:
            v, c = v[::-1], c[::-1]
        desl = self.n_especiais if self.comprimido else 0
        return {'v': tuple(x + desl for x in v), 'cor': tuple(c), 'tex': s['tex'], 'animada': s['animada'],
                'tipo': tipo, 'subtipo': sub, 'sem_descarte': sem_descarte, 'cantos': cantos}

    def textura_do_triangulo(self, tri, quadro_de_textura=0):
        """Devolve a Textura3 do triângulo, ou None se ele é só cor. (ProcessTextureInfoC2 do CrashEdit.)"""
        idx, animada = tri['tex'], tri['animada']
        if idx == 0 and not animada:
            return None
        t = idx - 1
        if animada:
            t += 1
            if t >= len(self.animadas):
                return None
            a = self.animadas[t]
            desl = a & 0x7FF
            if desl == 0:
                return None
            t = desl - 1
            if a < 0:                                       # campo de "nível de detalhe": fica o mais próximo
                t += (a >> 29) & 3
            else:                                           # "folioscópio": troca de textura com o tempo
                latencia, atraso, mascara = (a >> 26) & 0x1F, (a >> 19) & 0x7F, (a >> 12) & 0x7F
                t += ((quadro_de_textura // (1 + latencia)) + atraso) & mascara
                if (a >> 11) & 1:
                    t += 1
                    a = self.animadas[t]
                    t = (a & 0x7FF) - 1 + ((a >> 29) & 3)
        if t >= len(self.texturas):
            return None
        return self.texturas[t]

    def bits_por_quadro(self):
        return sum(b[3] + b[4] + b[5] + 3 for b in self.bases) if self.bases else 0


# ------------------------------------------------------------------------------------------------------
# SVTX do Crash 3
# ------------------------------------------------------------------------------------------------------
class Quadro3:
    """Um quadro de animação do Crash 3 (cabeçalho de 28 bytes; no Crash 2 são 24 e a ordem é outra)."""
    __slots__ = ('origem', 'desconhecido', 'tgeo', 'n_vertices', 'colisoes', 'tam_cabecalho', 'n_especiais',
                 'especiais', 'dados', 'item')

    def __init__(self, item):
        x, y, z, self.desconhecido, self.tgeo, _res, self.n_vertices, n_col, self.tam_cabecalho = \
            struct.unpack_from('<4hI4i', item, 0)
        self.origem = (x, y, z)
        self.colisoes = [struct.unpack_from('<10i', item, 28 + i * 40) for i in range(n_col)]
        base = 28 + n_col * 40
        self.n_especiais = (self.tam_cabecalho - base) // 3
        # os vértices especiais (pontos de encaixe, fora da malha) vêm sem compressão, na ordem x, Z, y
        self.especiais = [(item[base + i * 3], item[base + i * 3 + 2], item[base + i * 3 + 1])
                          for i in range(self.n_especiais)]
        self.dados = item[base:]
        self.item = bytes(item)

    def bytes_dos_vertices(self, tgeo):
        """[(bx, by, bz)] de 0..255 por vértice, na ordem do modelo. Descomprime se o modelo for comprimido."""
        d = self.dados
        if tgeo.bases is None:
            # sem compressão os 3 bytes vêm na ordem x, Z, y (visto no disco: só assim o "TNT" da caixa fica em
            # pé e legível e o Aku Aku fica de pé). Na fila comprimida a ordem é x, y, z.
            ini = self.n_especiais * 3
            return [(d[ini + i * 3], d[ini + i * 3 + 2], d[ini + i * 3 + 1])
                    for i in range(self.n_vertices - self.n_especiais)]
        # a fila de bits: palavras de 32 bits little-endian, lidas do bit mais alto para o mais baixo
        n_pal = len(d) // 4
        fila = int.from_bytes(b''.join(d[i * 4:i * 4 + 4][::-1] for i in range(n_pal)), 'big')
        total = n_pal * 32
        pos = self.n_especiais * 24
        ax = ay = az = 0
        saida = []

        def ler(bits):
            nonlocal pos
            n = bits + 1                                    # 1 bit de sinal + `bits` de valor
            if pos + n > total:
                raise ValueError('quadro curto demais para o modelo')
            val = (fila >> (total - pos - n)) & ((1 << n) - 1)
            pos += n
            return val - (1 << n) if val >> bits else val

        for bx, by, bz, nx, ny, nz in tgeo.bases:
            if nx == 7:
                ax = 0
            if ny == 7:
                ay = 0
            if nz == 7:
                az = 0
            ax = (ax + ler(nx) + bx * 2) & 0xFF
            ay = (ay + ler(ny) + by) & 0xFF
            az = (az + ler(nz) + bz) & 0xFF
            saida.append((ax, ay, az))
        return saida

    def posicoes(self, tgeo):
        """[(x, y, z)] em unidades do modelo ANTES da escala do TGEO: byte * 8 + origem / 4 (conta do CrashEdit)."""
        ox, oy, oz = (c / 4 for c in self.origem)
        return [(bx * 8 + ox, by * 8 + oy, bz * 8 + oz) for bx, by, bz in self.bytes_dos_vertices(tgeo)]


class Svtx3:
    def __init__(self, entrada):
        self.nome = entrada.nome
        self.quadros = [Quadro3(item) for item in entrada.itens]

    @property
    def tgeos(self):
        return sorted({nome_do_eid(q.tgeo) for q in self.quadros})
