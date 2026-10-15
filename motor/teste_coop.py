"""Teste do Crash 2 (controle 2) e da tela dividida, gravando tudo no projeto do vídeo (clips/).

    motor/.venv/Scripts/python.exe -I motor/teste_coop.py [--fase 5] [--nome coop_heli] [--estado X.state]

Liga o disco de trabalho (motor/out/dev), escolhe a fase no seletor do modo de desenvolvimento (5 = Heliporto), aperta
START no controle 2 e faz os dois Crashes andarem, pularem e girarem. Salva o estado logo depois de o Crash 2 entrar
(<saida>/coop.state), fotos, folha de contato e o clipe (mp4 + wav + json) no clips/ do projeto PROJETO.

Grava pelo gravador do estúdio de vídeo do ByteMirage (ferramentas/gameplay/gravador_psx.py), que não faz parte deste
repositório: a pasta do estúdio vem da variável ESTUDIO (padrão: "Claude IA video" ao lado da pasta da fusão). Os
robôs que importam Coop (teste_coop14, teste_guarda_crash2, teste_crash2_cenario, teste_paredes_crash2...) também.
"""
import argparse
import json
import os
import sys

MOTOR = os.path.dirname(os.path.abspath(__file__))
FUSAO = os.path.dirname(MOTOR)
ESTUDIO = os.environ.get('ESTUDIO') or os.path.join(os.path.dirname(FUSAO), 'Claude IA video')
os.environ.setdefault('PROJETO', 'mgb-expansao')
sys.path[:0] = [os.path.join(ESTUDIO, 'ferramentas', 'gameplay'), os.path.join(ESTUDIO, 'ferramentas'),
                os.path.join(MOTOR, 'harness'), MOTOR]
from gravador_psx import RecPSX  # noqa: E402

from teste_fases import INTERPRETADA  # noqa: E402  (CPU interpretada, relógio a 100% como no jogar.py)


class Coop:
    def __init__(self, disco, mapa, saida):
        self.rec = RecPSX(disco, mapa, opcoes=INTERPRETADA)
        self.ps, self.S = self.rec.ps, self.rec.sym
        self.saida = saida
        os.makedirs(saida, exist_ok=True)
        self.log = []
        # gravação nunca sobrescreve outra (o primeiro corte do Crash 2 preso no contêiner se perdeu assim):
        # se o nome já existe em clips/, ganha _2, _3...
        import gravador_psx
        salvar = self.rec.save

        def save(nome, *args, **kw):
            livre, n = nome, 2
            while os.path.exists(os.path.join(gravador_psx.CLIPS, livre + '.mp4')):
                livre, n = '%s_%d' % (nome, n), n + 1
            return salvar(livre, *args, **kw)
        self.rec.save = save

    def c2(self):
        """posição do Crash 2 (o CONTROL dele) ou None."""
        if 'crash2_control' not in self.S:
            return None
        c = self.ps.u32(self.S['crash2_control'])
        if not 0x80000000 <= c < 0x80200000:
            return None
        return [self.ps.s16(c + k) for k in (0, 2, 4)]

    def info(self, rot=''):
        ps, S = self.ps, self.S

        def v(nome, f=ps.s32):
            return f(S[nome]) if nome in S else None
        x = dict(rot=rot, q=len(self.rec.video), t=ps.u32(S['GV_Time']), fase=ps.cstr(S['GM_CurrentStageName'], 8),
                 p1=list(self.rec.onde()) if 0x80000000 <= self.rec.ctrl() < 0x80200000 else None, p2=self.c2(),
                 vida2=v('crash2_dbg_vida'), tela=v('crash_dbg_tela'), nomem2=v('crash2_dbg_nomem'),
                 nomem=v('crash_dbg_nomem'), topo=v('crash_topo'), tnt=v('crash_dbg_tnt'), morte=v('crash_dbg_morte'),
                 anim=v('crash_dbg_anim'), act=v('crash_dbg_action'), pausa=ps.u32(S['GV_PauseLevel']),
                 vida=v('GM_SnakeCurrentHealth', ps.s16), st=hex(ps.u32(S['GM_PlayerStatus'])),
                 gs=hex(ps.u32(S['GM_GameStatus'])))
        self.log.append(x)
        print(json.dumps(x), flush=True)
        return x

    def fase(self, indice):
        """Do boot ao controle na fase `indice` do seletor (5 = Heliporto, 2 = Loading Dock, 6 = Tank Hangar)."""
        rec, ps, S = self.rec, self.ps, self.S
        rec.passo((), 30)
        ps.w32(S['MGB_SeletorDeFases'], 1)
        rec.passo((), 1170)
        for _ in range(indice):
            rec.passo(['DOWN'], 2)
            rec.passo((), 8)
        rec.passo((), 5)
        rec.passo(['CIRCLE'], 2)
        for s in range(90):
            rec.passo((), 60)
            c = rec.ctrl()
            if 0x80000000 <= c < 0x80200000 and ps.u32(S['GV_PauseLevel']) == 0 and s > 8:
                return True
        return False

    def entra2(self):
        self.rec.passo((), 2, botoes2=['START'])
        self.rec.passo((), 30)
        return self.c2() is not None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--disco', default=os.path.join(MOTOR, 'out', 'dev', 'mgb.cue'))
    ap.add_argument('--mapa', default=os.path.join(FUSAO, 'repos', 'mgs_reversing', 'obj_dev', 'asm.map'))
    ap.add_argument('--fase', type=int, default=5)
    ap.add_argument('--estado', help='começa de um estado salvo (com o mesmo disco)')
    ap.add_argument('--nome', default='coop_heli')
    ap.add_argument('--saida', default=os.path.join(MOTOR, 'out', 'coop'))
    a = ap.parse_args()
    t = Coop(a.disco, a.mapa, a.saida)
    rec, ps = t.rec, t.ps
    if a.estado:
        ps.load_state(a.estado)
        rec.passo((), 2)
    else:
        if not t.fase(a.fase):
            print('FALHOU: a fase não carregou')
        ps.save_state(os.path.join(a.saida, 'fase.state'))
    rec.start()
    t.info('na fase')
    rec.mark('START no controle 2')
    ok = t.entra2()
    t.info('crash 2 entrou=%s' % ok)
    ps.save_state(os.path.join(a.saida, 'coop.state'))
    rec.foto(os.path.join(a.saida, 'entrou.png'))
    roteiro = [
        ('os dois parados', [], [], 60),
        ('crash 2 anda', [], ['RIGHT'], 45),
        ('crash 1 anda', ['LEFT'], [], 45),
        ('os dois andam', ['UP'], ['UP'], 60),
        ('crash 2 pula', [], ['CROSS'], 20),
        ('crash 2 no ar', [], [], 30),
        ('crash 2 pulo duplo', [], ['CROSS'], 6),
        ('crash 2 cai', [], [], 40),
        ('crash 2 gira', [], ['CIRCLE'], 4),
        ('giro', [], [], 30),
        ('crash 1 pula', ['CROSS'], [], 20),
        ('crash 1 cai', [], [], 40),
        ('afastam', ['DOWN'], ['UP'], 90),
        ('fim', [], [], 30),
    ]
    for rot, b1, b2, n in roteiro:
        rec.mark(rot)
        rec.passo(b1, n, botoes2=b2)
        t.info(rot)
        rec.foto(os.path.join(a.saida, rot.replace(' ', '_') + '.png'))
    rec.stop()
    rec.sheet(os.path.join(a.saida, 'folha.png'), cada=20, colunas=10)
    ps.save_state(os.path.join(a.saida, 'fim.state'))
    json.dump(t.log, open(os.path.join(a.saida, 'log.json'), 'w'), indent=0)
    rec.save(a.nome, descricao='Crash 2 entrando pelo controle 2, tela dividida (motor/teste_coop.py)')


if __name__ == '__main__':
    main()
