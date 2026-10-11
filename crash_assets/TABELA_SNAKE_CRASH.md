# Estado do Snake → animação do Crash (M-09, v3)

**v2 = feita com o disco aberto e as prévias na frente** (11/10/2026). Corrige a v1 em três pontos, marcados com
**(corrigido)**. Os acréscimos da revisão do C1 (MGB #7) continuam marcados com **(C1)**.
**v3 = v2 + o que o jogo rodando revelou ao C1 na F2** (MGB #13), marcado com **(no jogo)**.

Fontes: animações e sons do disco SCUS-94900, extraídos por `extrair.py`; a ordem em que o jogo toca cada uma vem
do script do Crash (`repos/goocdump/Crash 1/NTSC-J/WillC.gooc`); os estados do Snake vêm de
`repos/mgs_reversing/source/chara/snake/sna_init.c` (`ACTSTILL`, `ACTMOVE`, `ACTATTACK`, `ACTDAMAGE`).
Prévias: `out/previews/crash/<NOME>.gif`. Os números entre parênteses são o índice do movimento no `snake.oar`.

## Ficar e andar

| Snake | Crash | Como tocar |
|---|---|---|
| parado em pé, sem arma (`stand1_fig` 2, `stand2_fig` 6) e com arma (0, 1, 3, 90...) | `WILLY_STANCE1`, 13 quadros | **não é laço.** No Crash: a pose de descanso é o **quadro 11**, parado; de vez em quando pisca (12, 11, 12, 11, 0,1 s cada). Os quadros 0 a 10 são ele olhando em volta (opcional). O básico são 2 quadros |
| parado muito tempo | `WILLY_STANCE2_1/2` (26+25) e `WILLY_STANCE3_1/2/3` (25+25+20): o Crash entediado | uma vez, depois volta ao laço. Só se couber |
| correr (`run_fig` 12, `run_socom` 10 e os de cada arma) | `WILLY_WALK`, 10 quadros | **os 10 quadros são meio passo.** No Crash: 0 a 9 normal, depois 0 a 9 **espelhado em X** (a outra perna), e repete. Um som de passo a cada metade |
| virar de costas de uma vez | `WILLY_FLIP`, 4 quadros **(corrigido: é o Crash virando de lado, não o giro)** | opcional; no Crash o corpo roda 8° por quadro junto |
| agachar e ficar agachado (`squat_trans` 21, `squat_fig` 16, `squat_socom` 15) | `WILLY_DUCK`, 14 quadros: ele se abaixa e cobre a cabeça | no Crash: quadros 0 a 7 para descer, 8 a 13 em vaivém enquanto fica abaixado |
| deitar e rastejar (`crouch_trans` 20, `crouch_socom` 22, mover deitado) | `WILLY_FLAT`, 13 quadros: achatado como papel, depois descolando do chão | quadros 0 a 4 para achatar; rastejar = parado no quadro 4 deslizando. **É a piada.** |
| nadar debaixo d'água: **ação 24**, da mesma família do rastejar **(no jogo)** | `WILLY_FLAT` parado no quadro 4 | o Crash nada achatado. O C1 viu rodando: ficou ótimo |
| encostado na parede (`caution1` 25, `caution_fig` 26, agachado 31/129) | `WILLY_TERRAIN_STANCE`, 5 quadros, ou o parado | a ver no jogo |
| espiar/bater na parede (40, 41, 88, 89) | meia volta do giro | o som da batida continua sendo o do MGS (atrai o guarda) |

## Quando o Crash não aparece **(C1)**

| Snake | Crash | Como |
|---|---|---|
| dentro da caixa (o `box.c` deixa o Snake invisível e desenha a caixa) | some; quem aparece é a caixa | ao sair da caixa, volta o parado |
| primeira pessoa (Triângulo) | invisível | visibilidade do Crash ligada à do corpo do Snake |
| duto de ar (`stance 3`, `DG_InvisibleObjs`) | invisível | idem |

## Bater e apanhar

| Snake | Crash | Como tocar |
|---|---|---|
| soco, soco, chute (`NoneAttack` 35 a 39) | **`WILLY_BLOW`, 8 quadros, modelo próprio `WiBlG` (corrigido)**: o tornado, com a cabeça dele no meio e anéis translúcidos. Depois `WILLY_SPIN_END`, 6 quadros, ele saindo tonto | no Crash: `BLOW` em laço (quadros 0 a 7) enquanto o código roda o corpo **40° por quadro** (60° no ar) durante **0,4 s**; som `spn0A` em tom 4.0. Depois o corpo volta para a direção de antes |
| estrangular e arremessar | o giro | o guarda sai voando |
| levar dano (`NoneDamage` 63 a 72, 123, 130, 131; com arma também 61, 62, 64, 83) | **na F2: `WILLY_KILLED_1` (no jogo)**, que é o susto dele. Alternativa: `WILLY_SHOCK`, 3 quadros | som `yip0A` (o Whisper ouve "Oh!"). **Nem todo dano muda a ação do Snake** (afogar não muda) **(no jogo)** |
| derrubado / levantando **(C1)** | `WILLY_FLAT` para cair, `WILLY_DUCK` ao contrário para levantar | separa a queda da morte |
| atirar, mirar, jogar granada, plantar C4 | o parado | o Crash não tem animação de arma |
| a arma na mão **(C1)** | nada: ela fica presa na mão do Snake invisível | deve flutuar acima da cabeça do Crash. Fotografar e decidir |

## Morrer

A morte comum do Crash é uma sequência, e é assim que o jogo dele toca (estado `Willy_Death_Spin`):

1. o **"Woah!"** (`arg0A`) e o som do rodopio (`ds10A`, tom 2.88 a 3.33);
2. `WILLY_KILLED_1`, quadros 0 a 5 (leva o susto), e segura o quadro 5 **rodopiando 32,5° por quadro** por 19 quadros;
3. `WILLY_KILLED_2`, quadros 0 a 19 (vai tombando), e segura o 19 inclinando 8° por quadro por 9 quadros;
4. baque (`d1a0A`), `WILLY_KILLED_3` (0 a 9, cai sentado), espera 0,4 s;
5. `WILLY_KILLED_4` (0 a 7), outro baque (`d1b0A`), espera 0,7 s e a tela escurece.

Curiosidade para o vídeo: o próprio Crash 1 **não guarda essa morte na memória**. O script confere se há páginas
livres e carrega `KILLED_2/3/4` do CD na hora de morrer (`LoadAnim`), e descarrega depois. Faltava memória até para eles.

No MGS **a morte é a ação -1** (fim de jogo) **(no jogo)**; na F2 ela toca `WILLY_KILLED_1`.

| Como morreu no MGS | Crash | Quadros |
|---|---|---|
| tiro, soco (o caso comum) | a sequência acima; versão curta = só `KILLED_1` rodopiando | 6 + 20 + 10 + 8 = 44 |
| granada, Claymore, C4, míssil | `WILLY_TNT_1` + `WILLY_TNT_2`, modelo próprio `WT10G` (sobram os olhos e os sapatos) | 23 + 23, só 204 vértices |
| piso elétrico, cerca | `WILLY_SHOCK`, modelo próprio `WS10G` | 3 |
| fogo | `WILLY_FIRE_1..5`, modelo próprio `WF10G` (831 vértices: caro) | 10, 10, 10, 10, 8 |
| esmagado (elevador, porta) | `WILLY_FLAT` inteiro | 13 |

O "Woah!" toca em **todas** as mortes do Crash (`SoundWillyArgument` em Death_Spin, TNT, Fire, Eat, Flat e Fall).

## Itens e caixas (ver `diario/img/20261011_0020_...` e `..._0040_...`)

| MGS | Crash | Entrada |
|---|---|---|
| caixa de papelão A | caixa de madeira | `BOX_NORMAL` [BN10V] |
| caixa de papelão B | a **"?"** **(corrigido: a "?" é `BOX_PICKUP`; `BOX_FRUIT` é a listrada)** | `BOX_PICKUP` [Bp10V] |
| caixa de papelão C | TNT | `BOX_TNT` [BT10V] |
| caixa chutada pelo guarda | a contagem **3, 2, 1** e a explosão | `BOX_TNT3/2/1` [BT40V, BT30V, BT20V], `BOX_EXPLODE` [BE10V], 14 quadros |
| extras prontos | a de ferro, a de ferro com **"!"**, a com a cara do Crash, a do Aku Aku, a de seta, o "C" do checkpoint, o contorno fantasma | `BOX_IRON`, `BOX_ACTION1`, `BOX_LIFE`, `BOX_DOCTOR`, `BOX_SPRING`, `BOX_CONTINUE`, `BOX_GHOST` |
| ração | a Wumpa: sprite de 14 quadros (ela girando) | `out/sprites/frutas/sprite_000_00..13.png` |
| comer a ração | `WILLY_FRUIT`, 11 quadros, modelo próprio `WiFrG` | [WiFrV] |
| colete ou camuflagem | Aku Aku (34 vértices, 27 triângulos) e as penas | `WITCH_DOCTOR` [WD10V], `WITCH_DOCTOR_FEATHER` [WD20V] |
| sombra | `SHADOW`, 10 quadros | [Sha0V] |

Todas as caixas têm 8 vértices e 10 triângulos (sem o fundo), com textura de 32x32 em 4 bits.

## Os guardas como assistentes de laboratório (F5, ideia de um comentário do Reddit)

Saiu do disco, e **não tem textura nenhuma** (só cor por triângulo), o que barateia muito:

| Guarda | Assistente | Quadros / modelo |
|---|---|---|
| patrulhando | `LABASS_WALK` (anda com o braço esticado) | 24, modelo `Ls1FG`: 309 vértices, 526 triângulos |
| começando a andar | `LABASS_START_WALK` | 6, mesmo modelo |
| derrubado, nocauteado | `LABASS_PUSHED` (perde o equilíbrio) | 31, modelo `Ls2FG` |
| jogando granada | `LABASS_VIAL_THROW` (joga o frasco) | 24, modelo `LW1EG`, 340 vértices |
| parado, olhando | `LABASS_VIAL_MIX` (misturando frascos) | 30, mesmo modelo |

Detalhe: dentro do jogo o nome dele é `LABASS`. Só aparece em 3 das 44 fases do disco. Com o Crash medindo 1000, ele mede 1523:
fica da altura de um guarda sem precisar mexer na escala.

## Sons

| Quando | Entrada | Observação |
|---|---|---|
| **alerta do guarda ("!") e morte** | **`arg0A`** | **o "Woah!"**: 3.584 bytes. Só existe um. O script chama em toda morte; o Whisper ouviu "Wow" em três velocidades |
| dano | `yip0A` | 1.040 bytes; "Oh!" |
| giro | `spn0A` | tom 4.0 fixo |
| passos | `fs00A`, `fs10A` (e `fs20A/30A`, `fs60A/70A` em outros pisos) | |
| pulo / pouso | `jmp0A` / `ld00A` | |
| rodopio e baques da morte | `ds10A`, `d1a0A`, `d1b0A` | |
| caixa quebrando / TNT | `brk0A` / `tnt0A` | |
| Wumpa / vida | `frt0A` / `1up0A` | |
| Aku Aku | `WD10A` | o "ooga booga" |
| vitória | `yeh0A` | o Whisper ouviu "Yee-haw!". Só em 6 das 44 fases |

Tom, volume e queda de cada som, como o script do Crash toca (o tom 4.0 do script = 0x400 no SPU = 11025 Hz;
"sorteado" = `SoundPitchDefault()`, de 3.6 a 4.4, ou seja, de 0x39A a 0x466):

| Som | Tom | Volume | Queda (`sounddecay`) | Onde no script |
|---|---|---|---|---|
| `arg0A` (o "Woah!") | sorteado | 0,5 | 0,75 | `WillC` `SoundWillyArgument` |
| `yip0A` (dano) | sorteado | 1,0 | 0,625 | `WillC` `Willy_Hurt` |
| `spn0A` (giro) | 4.0 fixo | 0,25 | 0,625 | `WillC` `AnimWillySpin` |
| `jmp0A` (pulo) | sorteado | 0,1 | 0,25 | `WillC` `SoundWillyJump` |
| passos `fs00A`/`fs10A` | sorteado | 0,1 | 0,3125 | `WillC` `AnimWillyWalk` (um a cada meio passo) |
| `brk0A` (caixa quebrando) | sorteado | 0,35 | 0,625 | `BoxsC` `SoundBoxBreak` |
| `Ttb0A` (bipe da contagem do TNT) | 4.0 fixo | 0,4 e depois 0,8 | | `BoxsC` `TNTBeep` |
| `tnt0A` (explosão) | sorteado | 1,0 | 0,75 | `BoxsC` `PlayTNTSound` |
| `frt0A` (Wumpa) | **4.0 + 0,2 por fruta já contada**: o tom sobe a cada Wumpa seguida | 0,35 | 0,25 | `FruiC` `Fruit_Goto_Hud` |
| `1up0A` (vida) | 4.0 fixo | 0,5 | 0,9375 | `FruiC` |
| `WD10A` (Aku Aku) | 4.0 fixo | 1,0 | 0,9375 | `DoctC` `PlayDoctorSound` |

**Taxa dos sons: 11025 Hz.** No script, o tom normal é `soundpitch(4.0)`, que no chip de som do PS1 é 0x400 = 11025 Hz.
A voz do Crash usa `SoundPitchDefault()` = 3.6 a 4.4 **sorteado a cada vez**: o "Woah!" nunca sai igual (de 9.900 a
12.100 Hz). Vale copiar isso no MGS.

## Prioridade se a memória apertar

Tamanhos na versão compacta (`out/cru/`, os 6 bytes por vértice do disco):

1. **F1/F2**: `STANCE1` 13, `WALK` 10, `DUCK` 14, `FLAT` 13, `BLOW` 8 (+ modelo `WiBlG`), `SPIN_END` 6, `KILLED_1` 6
   = 70 quadros, 161 KB. Com a morte completa (`KILLED_2/3/4`, +38 quadros): 252 KB.
   **Versão enxuta** (só os quadros que o jogo do Crash realmente usa: `STANCE1` 11 e 12, `DUCK` 0 a 8, `FLAT` 0 a 4):
   46 quadros, 55 KB só com as posições, ou 31 KB comprimido sem dar para ver a diferença. Ver `ESTUDO_COMPRESSAO.md`.
2. Depois: `SHOCK`, `TNT_1/2` (baratas: 204 vértices), `FRUIT`.
3. Por último, ou só com 8 MB: `STANCE2/3`, `FIRE_1..5`, as `INTRO`, o assistente.
