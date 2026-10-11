"""Validate a relocated development overlay and keep the linker's zeroed BSS."""
import re
import shutil
import sys
from pathlib import Path


def symbols(path):
    return {match[2]: int(match[1], 16)
            for match in re.finditer(r'^\s+([0-9A-F]{8})\s+(\S+)\s*$',
                                     Path(path).read_text(encoding='latin-1'), re.MULTILINE)}


def main():
    source, main_map, stage_map, destination = sys.argv[1:]
    resident = symbols(main_map)
    stage = symbols(stage_map)
    # Every named main symbol must retain its address: extra runtime-library
    # dependencies must never silently relocate the main binary per stage.
    changed = [(name, address, stage.get(name)) for name, address in resident.items()
               if not name.startswith('_overlay') and stage.get(name) != address]
    if changed:
        raise SystemExit('Main/overlay ABI differs: ' + repr(changed[:12]))
    base = resident['_bss_orgend']
    if stage['_StageCharacterEntries'] != base:
        raise SystemExit('Stage character table is not at the overlay load address')
    shutil.copyfile(source, destination)
    print(f'{Path(destination).name}: {Path(source).stat().st_size} bytes at {base:08X}')


if __name__ == '__main__':
    main()
