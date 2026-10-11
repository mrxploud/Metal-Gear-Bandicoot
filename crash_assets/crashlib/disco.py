"""Lê arquivos de dentro de uma imagem de CD: .cue (+ .bin), .bin, .img ou .iso.

Entende setores "crus" de 2352 bytes (MODE1 e MODE2, que é o do PS1) e setores "cozidos" de 2048.
Só o que o extrator precisa: listar o sistema de arquivos ISO 9660 e ler um arquivo inteiro.
Não entende .chd (formato comprimido): converta para .bin/.cue antes.
"""
import os
import re
import struct

SINCRONIA = b'\x00' + b'\xff' * 10 + b'\x00'


class ErroDeDisco(Exception):
    pass


def _arquivo_da_faixa_de_dados(cue):
    """Devolve o caminho do primeiro FILE de um .cue (a faixa 1, que nos discos de PS1 é a de dados)."""
    pasta = os.path.dirname(os.path.abspath(cue))
    with open(cue, encoding='utf-8', errors='replace') as f:
        for linha in f:
            m = re.match(r'\s*FILE\s+"?(.+?)"?\s+(BINARY|MOTOROLA)\s*$', linha, re.I)
            if m:
                return os.path.join(pasta, m.group(1))
    raise ErroDeDisco(f'{cue}: nenhuma linha FILE "..." BINARY')


class Disco:
    def __init__(self, caminho):
        ext = os.path.splitext(caminho)[1].lower()
        if ext == '.chd':
            raise ErroDeDisco('formato .chd não é lido aqui; converta para .bin/.cue (chdman extractcd)')
        if ext == '.cue':
            caminho = _arquivo_da_faixa_de_dados(caminho)
        self.caminho = caminho
        self.f = open(caminho, 'rb')
        self.tamanho = os.path.getsize(caminho)
        inicio = self.f.read(16)
        if inicio[:12] == SINCRONIA:
            self.setor_bruto = 2352
            modo = inicio[15]
            if modo not in (1, 2):
                raise ErroDeDisco(f'{caminho}: modo de setor {modo} desconhecido')
            self.modo = modo
            self.deslocamento = 16 if modo == 1 else 24   # MODE2 tem 8 bytes de subcabeçalho XA
        else:
            self.setor_bruto = 2048
            self.modo = 0
            self.deslocamento = 0
        self._indice = None

    def fechar(self):
        self.f.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.fechar()

    # -- setores --------------------------------------------------------------------------------
    def setores(self, lba, quantos):
        """Devolve quantos*2048 bytes de dados a partir do setor lba."""
        if self.setor_bruto == 2048:
            self.f.seek(lba * 2048)
            dados = self.f.read(quantos * 2048)
        else:
            self.f.seek(lba * 2352)
            bruto = self.f.read(quantos * 2352)
            d = self.deslocamento
            dados = b''.join(bruto[i + d:i + d + 2048] for i in range(0, len(bruto), 2352))
        if len(dados) != quantos * 2048:
            raise ErroDeDisco(f'setor {lba}+{quantos} fora da imagem ({self.caminho})')
        return dados

    # -- ISO 9660 -------------------------------------------------------------------------------
    def _ler_diretorio(self, lba, tamanho, prefixo, saida, visitados):
        if lba in visitados:
            return
        visitados.add(lba)
        dados = self.setores(lba, (tamanho + 2047) // 2048)
        pos = 0
        while pos < tamanho:
            comprimento = dados[pos]
            if comprimento == 0:                      # registros não atravessam setor
                pos = (pos // 2048 + 1) * 2048
                continue
            reg = dados[pos:pos + comprimento]
            pos += comprimento
            ext_lba, = struct.unpack_from('<I', reg, 2)
            ext_tam, = struct.unpack_from('<I', reg, 10)
            bandeiras = reg[25]
            nome = reg[33:33 + reg[32]]
            if nome in (b'\x00', b'\x01'):            # "." e ".."
                continue
            nome = nome.decode('ascii', errors='replace').split(';')[0]
            caminho = prefixo + nome
            if bandeiras & 2:
                self._ler_diretorio(ext_lba, ext_tam, caminho + '/', saida, visitados)
            else:
                saida[caminho.upper()] = (ext_lba, ext_tam, caminho)

    def arquivos(self):
        """{CAMINHO_EM_MAIÚSCULAS: (lba, tamanho, caminho_original)} de todos os arquivos do disco."""
        if self._indice is None:
            pvd = self.setores(16, 1)
            if pvd[0] != 1 or pvd[1:6] != b'CD001':
                raise ErroDeDisco(f'{self.caminho}: não achei o descritor ISO 9660 no setor 16')
            raiz = pvd[156:190]
            lba, = struct.unpack_from('<I', raiz, 2)
            tam, = struct.unpack_from('<I', raiz, 10)
            saida = {}
            self._ler_diretorio(lba, tam, '', saida, set())
            self._indice = saida
        return self._indice

    def identificacao(self):
        """Identificador do sistema e do volume (para conferir que é o disco certo)."""
        pvd = self.setores(16, 1)
        return pvd[8:40].decode('ascii', 'replace').strip(), pvd[40:72].decode('ascii', 'replace').strip()

    def ler(self, caminho):
        chave = caminho.replace('\\', '/').upper()
        if chave not in self.arquivos():
            raise ErroDeDisco(f'{caminho}: não existe no disco')
        lba, tam, _ = self.arquivos()[chave]
        return self.setores(lba, (tam + 2047) // 2048)[:tam]

    def serial_ps1(self):
        """Lê o SYSTEM.CNF e devolve algo como 'SCUS_949.00' (ou None se não for disco de PS1)."""
        try:
            cnf = self.ler('SYSTEM.CNF').decode('ascii', 'replace')
        except ErroDeDisco:
            return None
        m = re.search(r'cdrom:\\?([A-Z]{4}[_-]\d{3}\.\d{2})', cnf, re.I)
        return m.group(1).upper() if m else None
