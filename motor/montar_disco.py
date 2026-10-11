"""Monta os discos do Metal Gear Bandicoot: os discos 1 e 2 originais do MGS Integral com o nosso executável no lugar
do SLPM_862.47/48 (o mesmo arquivo nos dois discos) e o código de cada fase ajustado a ele.

    python -I motor/montar_disco.py --disco discs/<mgs_integral_d1>.cue [--exe <_mgsi.exe>]
    python -I motor/montar_disco.py --numero 2 --disco discs/<mgs_integral_d2>.cue --saida motor/out/mgb_d2

Na primeira vez extrai o disco original para motor/disco_mgs/ (só leitura depois disso). A saída é
motor/out/mgb.bin + mgb.cue, que abre em qualquer emulador (DuckStation, PCSX-Redux) e no robô de testes.
"""
import argparse
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

MOTOR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, MOTOR)
from overlays import carregar_modulos, modulos_da_fusao, substituir_modulos

FUSAO = os.path.dirname(MOTOR)
TOOLS = os.path.join(MOTOR, 'tools', 'mkpsxiso', 'mkpsxiso-2.30-win64')
DUMP, MK = os.path.join(TOOLS, 'dumpsxiso.exe'), os.path.join(TOOLS, 'mkpsxiso.exe')
EXE_PADRAO = os.path.join(FUSAO, 'repos', 'mgs_reversing', 'obj_dev', '_mgsi.exe')
EXTRAIDO = os.path.join(MOTOR, 'disco_mgs')
NOMES_EXE = {1: 'SLPM_862.47', 2: 'SLPM_862.48'}


def bin_do_cue(cue):
    pasta = os.path.dirname(os.path.abspath(cue))
    with open(cue, encoding='latin-1') as f:
        m = re.search(r'FILE\s+"([^"]+)"', f.read())
    if not m:
        sys.exit('não achei FILE no %s' % cue)
    return os.path.join(pasta, m.group(1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--disco', required=True, help='.cue ou .bin do MGS Integral disco 1 (SLPM-86247) ou 2 (SLPM-86248)')
    ap.add_argument('--numero', type=int, choices=(1, 2), default=1, help='qual disco do Integral é o --disco')
    ap.add_argument('--exe', default=EXE_PADRAO)
    ap.add_argument('--saida', default=os.path.join(MOTOR, 'out', 'mgb'))
    ap.add_argument('--relocar', nargs='*', default=[],
                    help='fases que usam o módulo original relocado mesmo tendo a versão compilada')
    ap.add_argument('--so-extrair', action='store_true',
                    help='só extrai o disco original para motor/disco_mgs/ (o empacotador precisa do BRF.DAT dele)')
    a = ap.parse_args()

    origem = bin_do_cue(a.disco) if a.disco.lower().endswith('.cue') else a.disco
    os.makedirs(os.path.dirname(os.path.abspath(a.saida)), exist_ok=True)
    NOME_EXE = NOMES_EXE[a.numero]
    PASTA = 'MGSI_D%d' % a.numero
    xml_original = os.path.join(EXTRAIDO, 'mgsi_d%d.xml' % a.numero)
    if not os.path.exists(xml_original):
        os.makedirs(EXTRAIDO, exist_ok=True)
        print('extraindo o disco original (uma vez só)...')
        subprocess.run([DUMP, os.path.abspath(origem), '-x', os.path.join(EXTRAIDO, PASTA),
                        '-s', xml_original], check=True, cwd=EXTRAIDO)
    if not os.path.exists(os.path.join(EXTRAIDO, PASTA, 'MGS', NOME_EXE)):
        sys.exit('%s não é o disco %d do MGS Integral (falta MGS/%s)' % (a.disco, a.numero, NOME_EXE))
    if a.so_extrair:
        print('extraído em', EXTRAIDO)
        return

    arvore = ET.parse(xml_original)
    raiz = arvore.getroot()
    alvo = [e for e in raiz.iter('file') if e.get('name') == NOME_EXE]
    if len(alvo) != 1:
        sys.exit('esperava 1 entrada %s no xml, achei %d' % (NOME_EXE, len(alvo)))
    pasta_mgs = [d for d in raiz.iter('dir') if d.get('name') == 'MGS']
    if len(pasta_mgs) != 1:
        sys.exit('esperava 1 pasta MGS no xml')
    pasta_mgs = pasta_mgs[0]

    # Teste 10: nenhum arquivo do MGS muda de setor no disco (precaução: o jogo acha os arquivos pelo diretório, mas
    # os dados de cena e de voz são lidos aos pedaços e qualquer diferença do disco original vira suspeita). O
    # SLPM_862.47/48 e o BRF.DAT ficam os originais, o STAGE.DIR novo é completado até o tamanho do original, e o que
    # é nosso entra em dois arquivos novos depois do último do MGS: MGB.DAT (dados do Crash) e MGB.EXE (o nosso
    # executável, que o SYSTEM.CNF passa a carregar). Só o DUMMY3M.DAT (enchimento do fim do disco) anda.
    with open(os.path.join(EXTRAIDO, PASTA, 'SYSTEM.CNF'), 'rb') as f:
        cnf = f.read()
    if NOME_EXE.encode() not in cnf:
        sys.exit('SYSTEM.CNF sem %s' % NOME_EXE)
    copia_cnf = os.path.abspath(a.saida + '_SYSTEM.CNF')
    with open(copia_cnf, 'wb') as f:
        f.write(cnf.replace(NOME_EXE.encode(), b'MGB.EXE'))
    [e for e in raiz.iter('file') if e.get('name') == 'SYSTEM.CNF'][0].set('source', copia_cnf)
    data = alvo[0].get('date')
    novos = [('MGB.EXE', os.path.abspath(a.exe))]

    # Os módulos de fase precisam usar os endereços do mesmo executável. Os
    # originais do CD apontam para o código do MGS sem as alterações da fusão.
    if carregar_modulos(a.exe) is not None:
        stages = [e for e in raiz.iter('file') if e.get('name') == 'STAGE.DIR']
        if len(stages) != 1:
            sys.exit('esperava 1 entrada STAGE.DIR no xml')
        original = os.path.join(EXTRAIDO, PASTA, 'MGS', 'STAGE.DIR')
        try:
            modulos, tipo = modulos_da_fusao(a.exe, original, os.path.join(EXTRAIDO, PASTA, 'MGS', NOME_EXE),
                                              a.relocar)
        except ValueError as e:
            sys.exit(str(e))
        copia_stage = os.path.abspath(a.saida + '_STAGE.DIR')
        os.makedirs(os.path.dirname(copia_stage), exist_ok=True)
        with open(original, 'rb') as f:
            dados_original = f.read()
        dados_stage = substituir_modulos(dados_original, modulos)
        if len(dados_stage) > len(dados_original):
            sys.exit('o STAGE.DIR novo (%d bytes) passou do original (%d): os arquivos depois dele mudariam de '
                     'setor' % (len(dados_stage), len(dados_original)))
        with open(copia_stage, 'wb') as f:
            f.write(dados_stage + bytes(len(dados_original) - len(dados_stage)))
        stages[0].set('source', copia_stage)
        relocados = sorted(f for f, o in tipo.items() if o == 'relocado')
        maior = max(modulos, key=lambda f: len(modulos[f]))
        print('fases: %d compiladas, %d relocadas do original (%s); maior módulo: %s, %d bytes' % (
            len(tipo) - len(relocados), len(relocados), ' '.join(relocados), maior, len(modulos[maior])))

    # Metal Gear Bandicoot: texturas, paletas e sons do Crash vão no MGS/MGB.DAT (o jogo lê uma vez por fase,
    # manda para a VRAM e a SPU e libera a RAM). O empacotador gera motor/out/crash_cd.bin.
    blob = os.path.join(MOTOR, 'out', 'crash_cd.bin')
    if not os.path.exists(blob):
        sys.exit('falta motor/out/crash_cd.bin: rode o motor/empacotar_crash3.py antes')
    novos.insert(0, ('MGB.DAT', blob))
    ultimo = list(pasta_mgs).index([e for e in pasta_mgs if e.tag == 'file'][-1])
    for i, (nome, fonte) in enumerate(novos):
        e = ET.Element('file', {'name': nome, 'type': 'data', 'source': fonte})
        if data:
            e.set('date', data)
        e.tail = pasta_mgs[ultimo].tail
        pasta_mgs.insert(ultimo + 1 + i, e)

    # caminhos relativos do xml original passam a valer a partir da pasta da extração
    for e in raiz.iter('file'):
        src = e.get('source')
        if src and e is not alvo[0] and not os.path.isabs(src):
            e.set('source', os.path.join(EXTRAIDO, src))
    for d in raiz.iter('directory_tree'):
        src = d.get('srcdir')
        if src and not os.path.isabs(src):
            d.set('srcdir', os.path.join(EXTRAIDO, src))
    os.makedirs(os.path.dirname(a.saida), exist_ok=True)
    raiz.set('image_name', a.saida + '.bin')
    raiz.set('cue_sheet', a.saida + '.cue')
    xml_novo = a.saida + '.xml'
    arvore.write(xml_novo, encoding='utf-8', xml_declaration=True)

    subprocess.run([MK, '-y', xml_novo], check=True)
    mudaram = conferir_setores(origem_bin=origem, novo_bin=a.saida + '.bin')
    if mudaram:
        sys.exit('arquivos do MGS mudaram de setor no disco novo: ' + ', '.join(mudaram))
    print('pronto:', a.saida + '.cue', '(todos os arquivos do MGS nos setores do disco original)')
    escrever_para_o_jogador(a.saida, a.exe, a.numero)


def setores_iso(caminho):
    """{caminho: (setor inicial, bytes)} dos arquivos de uma imagem .bin (2352 bytes por setor, modo 2)."""
    import struct
    saida = {}
    with open(caminho, 'rb') as f:
        def setor(n):
            f.seek(n * 2352 + 24)
            return f.read(2048)

        def listar(lba, tam, prefixo):
            dados = b''.join(setor(lba + i) for i in range((tam + 2047) // 2048))
            i = 0
            while i < len(dados):
                n = dados[i]
                if n == 0:
                    i = (i // 2048 + 1) * 2048
                    continue
                rec = dados[i:i + n]
                nome = rec[33:33 + rec[32]].decode('ascii', 'replace').split(';')[0]
                if nome not in ('\x00', '\x01'):
                    l2, t2 = struct.unpack_from('<I', rec, 2)[0], struct.unpack_from('<I', rec, 10)[0]
                    if rec[25] & 2:
                        listar(l2, t2, prefixo + nome + '/')
                    else:
                        saida[prefixo + nome] = (l2, t2)
                i += n

        raiz = setor(16)[156:156 + 34]
        listar(struct.unpack_from('<I', raiz, 2)[0], struct.unpack_from('<I', raiz, 10)[0], '')
    return saida


def conferir_setores(origem_bin, novo_bin):
    """Arquivos do disco original que não começam no mesmo setor no disco novo (o enchimento DUMMY3M pode andar)."""
    antes, depois = setores_iso(origem_bin), setores_iso(novo_bin)
    return [nome for nome, (lba, _) in antes.items()
            if nome != 'DUMMY3M.DAT' and depois.get(nome, (None,))[0] != lba]


def escrever_para_o_jogador(saida, exe, numero):
    """Ao lado do disco: o endereço do nome da fase (o jogar.py troca de disco sozinho na tela "change") e,
    com os dois discos montados lado a lado (mgb.cue e mgb_d2.cue), a lista mgb.m3u que abre os dois."""
    import json
    mapa = os.path.join(os.path.dirname(os.path.abspath(exe)), 'asm.map')
    if os.path.exists(mapa):
        with open(mapa, encoding='latin-1') as f:
            texto = f.read()
        info = {'disco': numero}
        for nome in ('GM_CurrentStageName', 'MGB_SeletorDeFases'):
            m = re.search(r'^\s+([0-9A-F]{8})\s+%s\s*$' % nome, texto, re.M)
            if m:
                info[nome] = '0x' + m.group(1)
        with open(saida + '.json', 'w', encoding='utf-8') as f:
            json.dump(info, f, indent=1)
    base = saida[:-3] if numero == 2 and saida.endswith('_d2') else saida
    if os.path.exists(base + '.cue') and os.path.exists(base + '_d2.cue'):
        with open(base + '.m3u', 'w', encoding='utf-8') as f:
            f.write('%s.cue\n%s_d2.cue\n' % ((os.path.basename(base),) * 2))
        print('os dois discos:', base + '.m3u')


if __name__ == '__main__':
    main()
