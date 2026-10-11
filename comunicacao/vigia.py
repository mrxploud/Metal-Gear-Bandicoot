"""Vigia do inbox (padrão exit-to-wake do Vigianesx), com o estado guardado fora do repo.

    python -I vigia.py <inbox.md> <arquivo_de_estado> [poll_segundos]

Bloqueia até o inbox ter conteúdo diferente do último processado e então sai (exit 0),
imprimindo só o trecho novo. Primeira execução adota o conteúdo atual como já lido.
"""
import os
import sys
import time


def read(path):
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            return f.read().replace('\r\n', '\n')
    except FileNotFoundError:
        return ''


def main():
    inbox, state = sys.argv[1], sys.argv[2]
    poll = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0
    if not os.path.exists(state):
        with open(state, 'w', encoding='utf-8') as f:
            f.write(read(inbox))
    seen = read(state)
    while True:
        now = read(inbox)
        if now != seen and now.strip():
            with open(state, 'w', encoding='utf-8') as f:
                f.write(now)
            new = now[len(seen):] if now.startswith(seen) else now
            sys.stdout.reconfigure(encoding='utf-8')
            print('[vigia] inbox mudou:\n' + new)
            return
        time.sleep(poll)


if __name__ == '__main__':
    main()
