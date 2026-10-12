"""Reproduz Dock -> elevador -> d00a/d01a -> Heliporto no robô do PS1.

O trajeto usa teleporte e o item stealth somente para evitar os guardas antes
do elevador. Depois de embarcar, deixa as cutscenes e a troca de fase naturais.
Estados salvos só podem ser usados com o disco/mapa da mesma compilação.

    motor/.venv/Scripts/python.exe -I motor/teste_transicao.py \
        --disco motor/out/teste9/mgb.cue --mapa motor/out/transicao9/teste9.map

Executa o core em subprocesso com timeout porque uma falha nativa pode impedir
o retorno de retro_run. O JSONL e ultimo.state/RAM preservam o último checkpoint.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

MOTOR = Path(__file__).resolve().parent
ROOT = MOTOR.parent


def novo_jogo(ps, symbols):
    """Como um jogador: título, Novo Jogo, dificuldade, abertura e a primeira ligação do Campbell no Dock."""
    for second in range(150):
        ps.run(60)
        control = ps.u32(symbols["GM_PlayerControl"])
        if ps.cstr(symbols["GM_CurrentStageName"], 8) == "s00a" and 0x80000000 <= control < 0x80200000:
            break
        if second % 3 == 0:
            ps.press(["START"], 2, 4)
        elif second % 3 == 1:
            ps.press(["CIRCLE"], 2, 4)
    else:
        raise RuntimeError("Novo Jogo não chegou ao Dock")
    for _ in range(120):
        ps.run(30)
        if ps.u32(symbols["GV_PauseLevel"]):
            break
    livre = 0
    for _ in range(1200):
        if ps.u32(symbols["GV_PauseLevel"]) == 0:
            livre += 1
            if livre >= 6:
                return
            ps.run(30)
            continue
        livre = 0
        ps.press(["CIRCLE"], 2, 12)
        ps.run(16)


def worker(args):
    sys.path[:0] = [str(MOTOR / "harness"), str(MOTOR)]
    from psx import PSX
    from teste_dock import ligar_no_dock
    from teste_fases import INTERPRETADA
    import diag

    symbols = {}
    for line in Path(args.mapa).read_text(encoding="latin-1").splitlines():
        match = re.match(r"\s+([0-9A-F]{8})\s+(\S+)\s*$", line)
        if match:
            symbols[match[2]] = int(match[1], 16)
    diag._sym = symbols
    output = Path(args.saida).resolve()
    output.mkdir(parents=True, exist_ok=True)
    trace = (output / "amostras.jsonl").open("w", encoding="utf-8", buffering=1)
    core_log = (output / "core.log").open("w", encoding="utf-8", buffering=1)
    opcoes = dict(INTERPRETADA) if args.interpretador else {}
    saves = None
    if args.novo_jogo:
        # Com cartão de memória (um só do teste): sem cartão o título do MGS para num aviso.
        opcoes['pcsx_rearmed_memcard1'] = 'shared'
        saves = str(output / "saves")
    ps = PSX(str(Path(args.disco).resolve()), opcoes, saves=saves)
    log_count = 0
    last_stage = None
    stage_counts = {}

    def sample(label, picture=False):
        nonlocal log_count, last_stage
        control = ps.u32(symbols["GM_PlayerControl"])
        stage = ps.cstr(symbols["GM_CurrentStageName"], 8)
        info = {
            "label": label,
            "frame": ps.frame,
            "time": ps.u32(symbols["GV_Time"]),
            "stage": stage,
            "control": hex(control),
            "position": [ps.s16(control + offset) for offset in (0, 2, 4)],
            "status": hex(ps.u32(symbols["GM_GameStatus"])),
            "player_status": hex(ps.u32(symbols["GM_PlayerStatus"])),
            "pause": ps.u32(symbols["GV_PauseLevel"]),
            "memory": diag.memoria(ps),
            "image_sha256": hashlib.sha256(ps.image().tobytes()).hexdigest(),
        }
        trace.write(json.dumps(info) + "\n")
        (output / "ultimo.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
        (output / "ultimo.ram").write_bytes(ps.snapshot().tobytes())
        ps.save_state(str(output / "ultimo.state"))
        for line in ps.log_lines[log_count:]:
            core_log.write(line + "\n")
        log_count = len(ps.log_lines)
        if stage != last_stage:
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
            name = "%s_%d" % (stage, stage_counts[stage])
            ps.save_state(str(output / (name + ".state")))
            ps.shot(str(output / (name + ".png")))
            last_stage = stage
            picture = True
        if picture:
            ps.shot(str(output / (label + ".png")))
            print(json.dumps(info), flush=True)
        return info

    if args.estado:
        ps.load_state(str(Path(args.estado).resolve()))
        ps.run(1)
        sample("estado_carregado", True)
    else:
        if args.novo_jogo:
            novo_jogo(ps, symbols)
        else:
            ligar_no_dock(ps)
        sample("dock", True)
        ps.save_state(str(output / "dock.state"))
        if args.girar:
            # Sons do Crash antes do elevador (o giro toca o som dele). Até o teste 10 eles paravam o relógio do
            # driver de som do MGS: o som do jogo sumia e a cena do elevador travava.
            import numpy as np
            ps.core.audio = []

            def volume(segundos):
                ps.run(60 * segundos)
                a = np.frombuffer(b"".join(ps.core.audio), dtype=np.int16)
                ps.core.audio.clear()
                return int(np.abs(a).max()) if len(a) else 0
            antes = volume(4)
            for _ in range(args.girar):
                ps.press(["CIRCLE"], 4, 40)
            ps.run(60 * 6)          # o som do próprio giro e o eco passam; o que sobra é o som do jogo
            ps.core.audio.clear()
            depois = volume(6)
            ps.core.audio = None
            print("som do jogo: antes dos giros %d, depois %d" % (antes, depois), flush=True)
            if depois < antes // 4:
                raise RuntimeError("o som do jogo sumiu depois dos sons do Crash")
        control = ps.u32(symbols["GM_PlayerControl"])
        ps.w16(control, 0)
        ps.w16(control + 4, -26000)
        # Item 10: stealth. Basta equipar; o próprio jogo faz o efeito.
        ps.w16(symbols["linkvarbuf"] + 47 * 2, 1)
        ps.w16(symbols["linkvarbuf"] + 15 * 2, 10)
        for second in range(150):
            ps.run(60, ["UP"])
            sample("portao_%03d" % second, second % 15 == 0)
        ps.run(5)
        ps.run(24, ["RIGHT"])
        ps.run(5)
        sample("entrada_elevador", True)
        for second in range(30):
            ps.run(60, ["UP"])
            info = sample("elevador_%03d" % second, second % 3 == 0)
            if info["stage"] != "s00a":
                break
        else:
            raise RuntimeError("O trajeto não saiu do Dock no limite de 30 segundos")

    for second in range(args.segundos):
        ps.run(60)
        info = sample("cutscene_%03d" % second, second % 5 == 0)
        if info["stage"] == "s01a":
            # Não basta detectar o nome no início do carregamento: confirma
            # que há personagem e que o jogo avança com comandos no Heliporto.
            ps.run(120)
            ready = sample("heliporto", True)
            # A chegada leva mais de 3 minutos sem o jogador no controle: rádio do Campbell e da Mei Ling (~70 s),
            # a câmera passeando com fala (~35 s) e o rádio do Campbell e do Miller (~80 s). O robô espera até 5 min,
            # avançando o rádio com bolinha e tentando andar nos intervalos (antes desistia aos ~90 s).
            moved = ready
            for _ in range(150):
                if ps.u32(symbols["GV_PauseLevel"]):
                    ps.press(["CIRCLE"], 2, 118)
                    continue
                ps.run(30, ["UP"])
                ps.run(90)
                moved = sample("heliporto_movimento", False)
                if moved["position"] != ready["position"]:
                    break
            sample("heliporto_fim", True)
            if ready["position"] == moved["position"]:
                raise RuntimeError("Chegou ao Heliporto, mas o personagem não andou em 5 minutos")
            print("PASSOU: elevador, cutscenes e movimento no Heliporto", flush=True)
            ps.close()
            return 0
    sample("limite_atingido", True)
    ps.close()
    print("FALHOU: limite sem chegar ao Heliporto", flush=True)
    return 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disco", default=str(MOTOR / "out/teste9/mgb.cue"))
    parser.add_argument("--mapa", default=str(ROOT / "repos/mgs_reversing/obj_dev/asm.map"))
    parser.add_argument("--saida", default=str(MOTOR / "out/transicao9"))
    parser.add_argument("--estado", help="retoma uma cutscene já salva em vez de fazer o trajeto")
    parser.add_argument("--segundos", type=int, default=300)
    parser.add_argument("--timeout", type=int, default=180, help="limite real do subprocesso")
    parser.add_argument("--girar", type=int, default=0, help="giros do Crash (com som) no Dock antes do elevador")
    parser.add_argument("--novo-jogo", action="store_true",
                        help="chega ao Dock pelo título (Novo Jogo), como um jogador, em vez do seletor de fases")
    parser.add_argument("--interpretador", action="store_true",
                        help="CPU interpretada em vez do recompilador (lightrec) do PCSX ReARMed")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        return worker(args)
    output = Path(args.saida).resolve()
    output.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-I", str(Path(__file__).resolve()), *sys.argv[1:], "--worker"]
    try:
        result = subprocess.run(command, timeout=args.timeout)
        code = result.returncode
    except subprocess.TimeoutExpired:
        code = 124
        print("TIMEOUT: o core não concluiu dentro do limite real", flush=True)
    (output / "resultado.json").write_text(json.dumps({"exit_code": code, "command": command}, indent=2), encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
