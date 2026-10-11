"""Passeio por todas as fases do disco: carrega cada uma a partir do Loading Dock e confere se ela roda.

Para cada fase do STAGE.DIR, o robô parte do mesmo estado salvo no Dock e faz o que o comando "load" dos
scripts do jogo faz: escreve o nome da fase, o código dela e o pedido de carga. Depois espera a fase carregar,
anda com o personagem e guarda fotos e a memória livre. Cada fase roda num processo separado (uma queda do
emulador não derruba o passeio), com a CPU interpretada (o recompilador do PCSX ReARMed cai sozinho em d01a).

    python -I motor/teste_fases.py --disco motor/out/dev/mgb.cue [--fases s00a s01a ...] [--processos 6]

Saída em motor/out/fases/: uma pasta por fase e resumo.json; folha.png junta a última foto de cada uma.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

MOTOR = Path(__file__).resolve().parent
FUSAO = MOTOR.parent
MAPA = FUSAO / 'repos' / 'mgs_reversing' / 'obj_dev' / 'asm.map'
# CPU interpretada: o recompilador (lightrec) do PCSX ReARMed derruba o emulador na cena d01a da fusão.
INTERPRETADA = {'pcsx_rearmed_drc': 'disabled'}
# Sem módulo .bin (só dados) ou só menus de depuração: não são lugares do jogo.
FORA = {'init', 'init_ve', 'init_tux', 'select', 'select1', 'select2', 'select3', 'select4', 'selectd', 'sound'}


def str_code(nome):
    """GV_StrCode do MGS (source/libgv/strcode.c)."""
    i = 0
    for c in nome.encode('ascii'):
        i = ((i << 5) | (i >> 11)) & 0xFFFF
        i = (i + c) & 0xFFFF
    return i


def simbolos(mapa):
    sym = {}
    for linha in Path(mapa).read_text(encoding='latin-1').splitlines():
        m = re.match(r'\s+([0-9A-F]{8})\s+(\S+)\s*$', linha)
        if m:
            sym.setdefault(m[2], int(m[1], 16))
    return sym


def fases_do_disco(stage_dir):
    """Nomes das fases (as que têm módulo de código) de um STAGE.DIR."""
    sys.path.insert(0, str(MOTOR))
    import relocar
    return sorted(f for f in relocar.extrair_modulos(stage_dir) if f not in FORA)


def memoria(ps, sym):
    """KB livres (total, maior bloco) em pacotes e memória normal; None enquanto a área está zerada (carga)."""
    r = {'residente_livre': (ps.u32(sym['GV_ResidentMemoryBottom']) - sym['_bss_orgend']) // 1024}
    base, tam = sym['MemorySystems'], 16 + 512 * 8
    for i, nome in enumerate(['pacotes0', 'pacotes1', 'normal']):
        a = base + i * tam
        n = ps.u32(a + 12)
        if not 0 < n <= 512:
            r[nome] = None
            continue
        livre = maior = 0
        for u in range(n):
            ini, ptr, prox = ps.u32(a + 16 + u * 8), ps.u32(a + 20 + u * 8), ps.u32(a + 16 + (u + 1) * 8)
            if ptr == 0:
                livre += prox - ini
                maior = max(maior, prox - ini)
        r[nome] = (livre // 1024, maior // 1024)
    return r


def worker(a):
    sys.path[:0] = [str(MOTOR / 'harness'), str(MOTOR)]
    from psx import PSX
    sym = simbolos(a.mapa)
    pasta = Path(a.saida) / a.fase
    pasta.mkdir(parents=True, exist_ok=True)
    log = (pasta / 'amostras.jsonl').open('w', encoding='utf-8', buffering=1)
    ps = PSX(str(Path(a.disco).resolve()), INTERPRETADA)
    ps.load_state(str(Path(a.estado).resolve()))
    ps.run(2)

    def amostra(rotulo, foto=False):
        ctl = ps.u32(sym['GM_PlayerControl'])
        info = {'rotulo': rotulo, 'quadro': ps.frame, 'fase': ps.cstr(sym['GM_CurrentStageName'], 8),
                'tempo': ps.u32(sym['GV_Time']), 'controle': ctl,
                'pos': [ps.s16(ctl + k) for k in (0, 2, 4)] if 0x80000000 <= ctl < 0x80200000 else None,
                'status': ps.u32(sym['GM_GameStatus']), 'pausa': ps.u32(sym['GV_PauseLevel']),
                'memoria': memoria(ps, sym)}
        log.write(json.dumps(info) + '\n')
        if foto:
            ps.shot(str(pasta / (rotulo + '.png')), scale=1)
        return info

    nome = a.fase.encode('ascii') + bytes(8 - len(a.fase))
    ps.write(sym['GM_CurrentStageName'], nome)
    ps.w16(sym['area_id'], str_code(a.fase))
    ps.w32(sym['GM_LoadRequest'], 1)
    amostras, vistas, parado, ultimo_tempo = [], [], 0, None
    resultado = {'fase': a.fase, 'andou': False, 'tem_personagem': False}
    controle_desde = None
    for meio in range(a.segundos * 2):
        ps.run(30)
        info = amostra('t%03d' % meio, meio % 10 == 9)
        amostras.append(info)
        if not vistas or vistas[-1] != info['fase']:
            vistas.append(info['fase'])
        parado = parado + 1 if info['tempo'] == ultimo_tempo else 0
        ultimo_tempo = info['tempo']
        if info['pos']:
            controle_desde = meio if controle_desde is None else controle_desde
        else:
            controle_desde = None
        if controle_desde is not None and meio - controle_desde >= 4 and not resultado['tem_personagem']:
            # O personagem está no controle há 2 s: anda em quatro direções.
            resultado['tem_personagem'] = True
            antes = amostra('antes_de_andar', True)
            for direcao in ('UP', 'LEFT', 'DOWN', 'RIGHT'):
                ps.run(40, [direcao])
            depois = amostra('depois_de_andar', True)
            resultado['andou'] = bool(depois['pos'] and antes['pos'] != depois['pos'])
            resultado['andou_na_fase'] = depois['fase']
    validas = [s for s in amostras if s['pos'] and s['pausa'] == 0]  # jogando (sem rádio, pausa ou cena)
    resultado['fases_vistas'] = vistas
    resultado['carregou'] = a.fase in vistas[1:] or any(s['memoria']['normal'] and s['memoria']['normal'][0] for s in amostras)
    resultado['travou'] = parado >= 12
    resultado['tempo_parado_s'] = parado / 2
    def menor(chave):
        v = [x for x in (s['memoria'][chave] for s in validas) if x]
        return min(m[0] for m in v) if v else None
    resultado['menor_livre_kb'] = {'pacotes': min([x for x in (menor('pacotes0'), menor('pacotes1')) if x is not None] or [None]),
                                   'normal': menor('normal'),
                                   'residente_mais_modulo': min(s['memoria']['residente_livre'] for s in amostras)}
    ps.shot(str(pasta / 'ultima.png'), scale=1)
    (pasta / 'resultado.json').write_text(json.dumps(resultado, indent=2), encoding='utf-8')
    ps.close()
    return 0


def rodar(fase, a):
    cmd = [sys.executable, '-I', str(Path(__file__).resolve()), '--worker', '--fase', fase, '--disco', a.disco,
           '--estado', a.estado, '--mapa', a.mapa, '--saida', a.saida, '--segundos', str(a.segundos)]
    inicio = time.time()
    try:
        r = subprocess.run(cmd, timeout=a.timeout, capture_output=True, text=True)
        codigo = r.returncode
    except subprocess.TimeoutExpired:
        codigo = 'tempo esgotado'
    arq = Path(a.saida) / fase / 'resultado.json'
    res = json.loads(arq.read_text(encoding='utf-8')) if arq.exists() and codigo == 0 else {'fase': fase}
    res['saida_do_processo'] = codigo
    res['segundos_reais'] = round(time.time() - inicio, 1)
    return res


def passou(r):
    """O emulador não caiu, a fase (ou a que o script dela chamou) carregou e o jogo não congelou."""
    return r.get('saida_do_processo') == 0 and r.get('carregou') and not r.get('travou')


def folha(saida, resultados):
    from PIL import Image, ImageDraw
    fotos = []
    for r in resultados:
        p = Path(saida) / r['fase'] / 'ultima.png'
        if p.exists():
            fotos.append((r, Image.open(p).convert('RGB').resize((160, 120))))
    if not fotos:
        return
    col = 10
    img = Image.new('RGB', (col * 160, ((len(fotos) + col - 1) // col) * 136), 'black')
    d = ImageDraw.Draw(img)
    for i, (r, f) in enumerate(fotos):
        x, y = (i % col) * 160, (i // col) * 136
        img.paste(f, (x, y + 16))
        ok = passou(r)
        d.text((x + 2, y + 2), '%s %s%s' % (r['fase'], 'ok' if ok else 'FALHA',
                                             ' anda' if r.get('andou') else ''), fill=(0, 255, 0) if ok else (255, 64, 64))
    img.save(Path(saida) / 'folha.png')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--disco', default=str(MOTOR / 'out' / 'dev' / 'mgb.cue'))
    ap.add_argument('--estado', help='estado salvo no Loading Dock com este mesmo disco (sem ele, liga o jogo)')
    ap.add_argument('--mapa', default=str(MAPA))
    ap.add_argument('--boot-quadros', type=int, help='parte do jogo recém-ligado (N quadros) em vez do Dock')
    ap.add_argument('--stage-dir', help='STAGE.DIR com a lista de fases (padrão: o montado ao lado do .cue)')
    ap.add_argument('--saida', default=str(MOTOR / 'out' / 'fases'))
    ap.add_argument('--fases', nargs='*')
    ap.add_argument('--segundos', type=int, default=60, help='quanto tempo de jogo observar cada fase')
    ap.add_argument('--processos', type=int, default=6)
    ap.add_argument('--timeout', type=int, default=300)
    ap.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    ap.add_argument('--fase', help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.worker:
        return worker(a)
    if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    Path(a.saida).mkdir(parents=True, exist_ok=True)
    if not a.estado:
        sys.path[:0] = [str(MOTOR / 'harness'), str(MOTOR)]
        from psx import PSX
        from teste_dock import ligar_no_dock
        ps = PSX(str(Path(a.disco).resolve()), INTERPRETADA)
        if a.boot_quadros:
            ps.run(a.boot_quadros)  # jogo recém-ligado (título ou seletor), sem progresso
        else:
            ligar_no_dock(ps)
        a.estado = str(Path(a.saida) / 'inicio.state')
        ps.save_state(a.estado)
        ps.close()
    fases = a.fases or fases_do_disco(a.stage_dir or str(a.disco)[:-4] + '_STAGE.DIR')
    print('%d fases, %d processos' % (len(fases), a.processos), flush=True)
    with ThreadPoolExecutor(a.processos) as ex:
        resultados = []
        for r in ex.map(lambda f: rodar(f, a), fases):
            resultados.append(r)
            print('%-7s %-5s %s personagem=%s anda=%s travou=%s processo=%s memória=%s (%ss)' % (
                r['fase'], 'ok' if passou(r) else 'FALHA', '>'.join(r.get('fases_vistas', [])),
                r.get('tem_personagem'), r.get('andou'), r.get('travou'), r.get('saida_do_processo'),
                r.get('menor_livre_kb'), r.get('segundos_reais')), flush=True)
    (Path(a.saida) / 'resumo.json').write_text(json.dumps(resultados, indent=2), encoding='utf-8')
    folha(a.saida, resultados)
    falhas = [r['fase'] for r in resultados if not passou(r)]
    print('falharam: %s' % (' '.join(falhas) or 'nenhuma'))
    return 1 if falhas else 0


if __name__ == '__main__':
    raise SystemExit(main())
