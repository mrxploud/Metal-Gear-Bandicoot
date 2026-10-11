"""Diagnóstico do MGS dentro do robô: símbolos do executável, memória livre, estado do Crash."""
import os
import re

FUSAO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAPA = os.path.join(FUSAO, 'repos', 'mgs_reversing', 'obj_dev', 'asm.map')
_sym = None


def sym(nome=None):
    global _sym
    if _sym is None:
        _sym = {}
        for linha in open(MAPA, encoding='latin-1'):
            m = re.match(r'\s+([0-9A-F]{8})\s+(\S+)\s*$', linha)
            if m:
                _sym[m.group(2)] = int(m.group(1), 16)
    return _sym if nome is None else _sym[nome]


def memoria(ps):
    """KB livres: entre o executável e os dados residentes da fase, e em cada área do GV."""
    s = sym()
    r = {'residente_livre': (ps.u32(s['GV_ResidentMemoryBottom']) - s['_bss_orgend']) // 1024}
    base, tam = s['MemorySystems'], 16 + 512 * 8
    for i, nome in enumerate(['pacotes0', 'pacotes1', 'normal']):
        a = base + i * tam
        n = ps.u32(a + 12)
        livre = maior = 0
        for u in range(n):
            ini, ptr, prox = ps.u32(a + 16 + u * 8), ps.u32(a + 20 + u * 8), ps.u32(a + 16 + (u + 1) * 8)
            if ptr == 0:
                livre += prox - ini
                maior = max(maior, prox - ini)
        r[nome] = (livre // 1024, maior // 1024)
    return r


def crash(ps):
    s = sym()
    return {k: ps.s32(s['crash_' + k]) for k in ('last_count', 'dbg_action', 'dbg_action2') if 'crash_' + k in s}


def item(ps):
    return ps.s16(sym('linkvarbuf') + 15 * 2)


def equipar_item(ps, alvo, estado=None, max_toques=14):
    """Abre o menu de itens (L2) e anda para a esquerda até o item `alvo` (2, 3, 4 = caixas A, B, C).
    Se `estado` for dado, recomeça dele a cada tentativa. Devolve o número de toques ou None."""
    for n in range(1, max_toques + 1):
        if estado:
            ps.load_state(estado)
            ps.run(30)
        ps.hold(['L2'], 20)
        for _ in range(n):
            ps.hold(['L2', 'LEFT'], 3)
            ps.hold(['L2'], 8)
        ps.run(40)
        if item(ps) == alvo:
            return n
    return None
