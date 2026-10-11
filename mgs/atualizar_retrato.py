#!/usr/bin/env python3
"""Tira o retrato do lado MGS para o repositório: o que nós mudamos na descompilação do Metal Gear Solid.

    python -I mgs/atualizar_retrato.py

O trabalho de verdade acontece em repos/mgs_reversing (um clone do FoxdieTeam/mgs_reversing, que não vai para o
nosso repositório). Este script só LÊ de lá e grava aqui:

  mgs/metal-gear-bandicoot.patch   as mudanças nos arquivos que já existiam no mgs_reversing
  mgs/source/crash/                os arquivos novos (o ator que desenha o Crash)
  mgs/BASE.txt                     em cima de qual commit do mgs_reversing o patch se aplica

NUNCA copia source/crash/crash_data.c nem crash_data.h: esses dois são gerados por motor/empacotar_crash3.py a
partir do disco do Crash (modelo, animações, texturas e sons do jogo) e não podem ser publicados.
"""
import os
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
FUSAO = os.path.dirname(AQUI)
REPO = os.path.join(FUSAO, 'repos', 'mgs_reversing')
GERADOS = ('crash_data.c', 'crash_data.h')            # dados do jogo: nunca publicar


def git(*args):
    r = subprocess.run(['git', '-C', REPO, *args], capture_output=True)
    if r.returncode:
        sys.exit(f'git {" ".join(args)}: {r.stderr.decode("utf-8", "replace")}')
    return r.stdout


def principal():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if not os.path.isdir(os.path.join(REPO, '.git')):
        sys.exit(f'não achei o clone do mgs_reversing em {REPO}')
    base = git('merge-base', 'HEAD', 'origin/HEAD').decode().strip()
    origem = git('remote', 'get-url', 'origin').decode().strip()
    ramo = git('rev-parse', '--abbrev-ref', 'HEAD').decode().strip()
    patch = git('diff', '--binary', base)             # arquivos rastreados: commits nossos + o que está sem commit
    with open(os.path.join(AQUI, 'metal-gear-bandicoot.patch'), 'wb') as f:
        f.write(patch.replace(b'\r\n', b'\n'))
    mudados = git('diff', '--name-only', base).decode().split()
    novos = [n for n in git('ls-files', '--others', '--exclude-standard').decode().split()
             if os.path.basename(n) not in GERADOS]
    destino = os.path.join(AQUI, 'source')
    if os.path.isdir(destino):
        shutil.rmtree(destino)
    for n in novos:
        alvo = os.path.join(AQUI, *n.split('/'))
        os.makedirs(os.path.dirname(alvo), exist_ok=True)
        with open(os.path.join(REPO, *n.split('/')), 'rb') as f:
            dados = f.read()
        with open(alvo, 'wb') as f:
            f.write(dados.replace(b'\r\n', b'\n'))
    with open(os.path.join(AQUI, 'BASE.txt'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(f'repositorio: {origem}\ncommit: {base}\nramo local: {ramo}\n'
                f'arquivos mudados: {len(mudados)}\narquivos novos: {len(novos)}\n')
    print(f'base {base[:10]} ({origem})')
    print(f'{len(mudados)} arquivos mudados -> metal-gear-bandicoot.patch ({len(patch)} bytes)')
    for n in mudados:
        print('   M', n)
    for n in novos:
        print('   +', n)
    print('fora do retrato (dados gerados do jogo):', ', '.join(GERADOS))


if __name__ == '__main__':
    principal()
