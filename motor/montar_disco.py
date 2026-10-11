"""Monta o disco do Metal Gear Bandicoot: o disco 1 original do MGS Integral com o nosso executável no lugar do
SLPM_862.47 (o processo do README do mgs_reversing, automatizado).

    python -I motor/montar_disco.py --disco discs/<mgs_integral_d1>.cue [--exe <_mgsi.exe>]

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
FUSAO = os.path.dirname(MOTOR)
TOOLS = os.path.join(MOTOR, 'tools', 'mkpsxiso', 'mkpsxiso-2.30-win64')
DUMP, MK = os.path.join(TOOLS, 'dumpsxiso.exe'), os.path.join(TOOLS, 'mkpsxiso.exe')
EXE_PADRAO = os.path.join(FUSAO, 'repos', 'mgs_reversing', 'obj_dev', '_mgsi.exe')
EXTRAIDO = os.path.join(MOTOR, 'disco_mgs')
NOME_EXE = 'SLPM_862.47'


def bin_do_cue(cue):
    pasta = os.path.dirname(os.path.abspath(cue))
    with open(cue, encoding='latin-1') as f:
        m = re.search(r'FILE\s+"([^"]+)"', f.read())
    if not m:
        sys.exit('não achei FILE no %s' % cue)
    return os.path.join(pasta, m.group(1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--disco', required=True, help='.cue ou .bin do MGS Integral disco 1 (SLPM-86247)')
    ap.add_argument('--exe', default=EXE_PADRAO)
    ap.add_argument('--saida', default=os.path.join(MOTOR, 'out', 'mgb'))
    a = ap.parse_args()

    origem = bin_do_cue(a.disco) if a.disco.lower().endswith('.cue') else a.disco
    xml_original = os.path.join(EXTRAIDO, 'mgsi_d1.xml')
    if not os.path.exists(xml_original):
        os.makedirs(EXTRAIDO, exist_ok=True)
        print('extraindo o disco original (uma vez só)...')
        subprocess.run([DUMP, os.path.abspath(origem), '-x', os.path.join(EXTRAIDO, 'MGSI_D1'),
                        '-s', xml_original], check=True, cwd=EXTRAIDO)

    arvore = ET.parse(xml_original)
    raiz = arvore.getroot()
    alvo = [e for e in raiz.iter('file') if e.get('name') == NOME_EXE]
    if len(alvo) != 1:
        sys.exit('esperava 1 entrada %s no xml, achei %d' % (NOME_EXE, len(alvo)))
    alvo[0].set('source', os.path.abspath(a.exe))

    # Metal Gear Bandicoot: texturas, paletas e sons do Crash vão no fim de uma cópia do BRF.DAT (o jogo lê
    # uma vez por fase, manda para a VRAM e a SPU e libera a RAM). O empacotador gera motor/out/crash_cd.bin.
    blob = os.path.join(MOTOR, 'out', 'crash_cd.bin')
    if os.path.exists(blob):
        brf = [e for e in raiz.iter('file') if e.get('name') == 'BRF.DAT']
        if len(brf) != 1:
            sys.exit('esperava 1 entrada BRF.DAT no xml')
        orig = os.path.join(EXTRAIDO, 'MGSI_D1', 'MGS', 'BRF.DAT')
        dados = open(orig, 'rb').read()
        dados += bytes((-len(dados)) % 2048) + open(blob, 'rb').read()
        copia = os.path.join(MOTOR, 'out', 'BRF_MGB.DAT')
        open(copia, 'wb').write(dados)
        brf[0].set('source', copia)

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
    print('pronto:', a.saida + '.cue')


if __name__ == '__main__':
    main()
