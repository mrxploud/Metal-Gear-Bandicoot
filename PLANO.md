# Metal Gear Bandicoot: Wumpa Fruit Eater

**O Crash Bandicoot jogável dentro do Metal Gear Solid (PS1).**

Ideia e direção: **mrxploud (ByteMirage)**. Investigação e código: Claude 1 + Claude 2.
Inspiração: o desenho de **u/Max_Comix** no r/crashbandicoot (2018) e os comentários do post: **yuvi3000** sugeriu o Crash
se esconder na caixa dele, e outro usuário, o "Woah!" no lugar do "!" dos guardas.
Créditos completos e obrigatórios: [`CREDITOS.md`](CREDITOS.md).

---

## 1. O que medimos antes de decidir (10/10/2026)

| | Metal Gear Solid Integral | Crash Bandicoot |
|---|---|---|
| Repositório | [FoxdieTeam/mgs_reversing](https://github.com/FoxdieTeam/mgs_reversing) | [Matteo842/CrashBandicoot-Launcher](https://github.com/Matteo842/CrashBandicoot-Launcher) |
| O que é | **descompilação em C**: o executável principal está 100% em C e recompila igual ao original | **recompilação estática** do código MIPS para C# (não é código-fonte legível), com sistema de mods em C# |
| Disco exigido | **SLPM-86247** (Integral, japonês, disco 1) | **SCUS-94900** (americano) |
| Fases jogáveis com código modificado | 64 partes 100% em C, incluindo **Loading Dock, Heliport, Tank Hangar, celas, Armory** | n/a |
| Modo de teste pronto | variante `dev_exe`: embute os atores do **Loading Dock** no executável e abre num seletor de fases | launcher com cheats, voo, seleção de fase |

Achados que definem o plano:

- O código do Snake (`source/chara/snake/sna_init.c`, 8.610 linhas) e da caixa de papelão (`source/equip/box.c`)
  estão em C. Dá para mudar o jogo de verdade, não só por memória.
- A caixa de papelão já troca de textura por código (`EQ_ChangeTexture`, "cb_box11"...). Trocar pela
  **caixa do Crash** é, no mínimo, trocar a textura.
- O motor gráfico do MGS (`libdg`) já desenha triângulos com cor e textura no mundo 3D (`DG_MakePrim` com
  `DG_PRIM_POLY_G3`/`GT3`). É o caminho para desenhar o Crash sem converter ele para o formato de esqueleto do Snake.
- O Crash 1 guarda as animações como **quadros de vértices** (formato `SVTX`: x, y, z e normal em 6 bytes por vértice)
  e o modelo como triângulos (`TGEO`). Os formatos estão documentados no [c1](https://github.com/wurlyfox/c1)
  (`src/formats/svtx.h`, `tgeo.h`), o port do motor do Crash 1 que o próprio Crash Launcher credita.

> **Atualização 11/10/2026 08:26:** a pedido do ByteMirage, o Crash passou a ser o do **Crash Bandicoot 3 (Warped)**
> (o Crash 1 não engatinha nem derrapa). O Claude 2 lê o disco do Warped (SCES-01420); as caixas, os sons e as
> marcas "WOAH!" continuam vindo do Crash 1. Teste 5 em diante.

## 2. A estratégia

Diferente do Sonic Mirage (dois emuladores rodando juntos), aqui os dois jogos são abertos por dentro:

1. **O MGS é o mundo.** Usamos a descompilação para compilar um MGS modificado. O Snake continua existindo
   (controle, colisão, guardas, alerta, câmera, rádio), só que **invisível**: ele vira o corpo do Crash.
2. **O Crash é extraído do disco dele.** Um programa nosso lê os arquivos do Crash 1 (NSF) e tira o modelo,
   as animações, as caixas, a Wumpa, o Aku Aku e os sons. Nada do Crash é redesenhado à mão.
3. **Um ator novo no MGS desenha o Crash** no lugar do Snake, a cada quadro, escolhendo a animação do Crash que
   corresponde ao que o Snake está fazendo (parado, andando, correndo, agachado, socando, tomando dano...).
4. **As mecânicas viram do Crash** onde fizer graça: a caixa vira caixa do Crash, o soco vira o giro, a ração vira
   Wumpa, o grito de morte vira o "Whoa!".

Tudo roda num emulador comum (DuckStation, que já está em `D:\DOWNLOAD\ps1`, ou PCSX-Redux) a partir de um
.cue/.bin reconstruído com o executável novo.

## 3. Fases e marcos

Cada fase termina com algo que o ByteMirage pode testar. Fotos, clipes e bugs de cada fase vão para `diario/`.

| Fase | Entrega | Quem |
|---|---|---|
| **F0 Fundação** | ferramentas compilando o MGS `dev_exe` no Windows; disco reconstruído bootando; robô de testes (emulador por script, capturas, leitura de memória); extrator lendo o disco do Crash | os dois |
| **F1 Crash no Dock** | Snake invisível, o Crash (uma pose) seguindo a posição e a direção dele no Loading Dock. **Primeira foto da fusão.** | C1 desenha, C2 entrega o modelo |
| **F2 Crash anima** | parado, andar, correr, agachar, rastejar, encostar na parede, dano, morte, girar. **Teste 1 do ByteMirage** | os dois |
| **F3 A caixa do Crash** | caixa de papelão vira caixa de madeira do Crash (e a "?" e a TNT); guarda acha a caixa, "!" | C1 motor, C2 texturas |
| **F4 Golpes e sons** | giro derruba guardas em volta; sons do Crash (giro, "Whoa!", Wumpa); pulo (visual primeiro) | os dois |
| **F5 Extras** | Wumpa no lugar da ração; Aku Aku; tela "METAL GEAR BANDICOOT"; Game Over "CRASH? CRAAASH!"; mais fases (Heliport) | os dois |
| **F6 Entrega** | ByteMirage testa e aprova; README no estilo do Sonic Mirage. **Só depois disso, o vídeo.** | os dois |

Ideias de graça (a lista cresce no `diario/IDEIAS.md`):
- **O "!" do guarda vira "Woah!"** (sugestão de um comentário do post, 37 votos; o ZXE102R completou com
  "Woah! Whose footprints are these?!"). Entra na F4 como prioridade: a marca de alerta e o som.
- **Guardas viram assistentes de laboratório do Cortex** (outro comentário). Ambicioso: usa o mesmo desenhista
  do Crash em cima do guarda. F5.
- Guarda chuta a caixa (`boxkeri.c` existe no jogo) e ela é uma TNT: 3, 2, 1...
- O Crash rastejando com a animação de morte "achatado".
- Alerta "!" em cima do guarda quando vê uma caixa de madeira andando.

## 4. Riscos conhecidos

- **Versões exatas dos discos.** Sem SLPM-86247 e SCUS-94900 nada funciona; os endereços só valem para elas.
- **Memória do PS1 (2 MB).** Se o Crash não couber, o plano B é ligar os 8 MB de RAM de desenvolvimento no
  emulador (DuckStation e PCSX-Redux suportam).
- **Só o Loading Dock vem pronto no `dev_exe`.** Outras fases exigem registrar os atores delas (a lista já está
  em C nas fases 100% descompiladas).
- **O Crash 1 não tem animação de rastejar nem de encostar na parede.** Vamos improvisar, e o improviso vira piada.
- **O Integral é japonês.** Vozes em inglês, legendas e rádio em japonês.

## 5. Onde fica cada coisa

```
fusao/
  PLANO.md         este plano
  CREDITOS.md      quem precisa ser creditado (não remover ninguém)
  repos/           clones: mgs_reversing (vai virar o nosso fork, branch metal-gear-bandicoot), c1, CrashBandicoot-Launcher
  discs/           os discos do ByteMirage (nunca publicar)
  crash_assets/    extrator e saída do Crash (Claude 2)
  motor/           ferramentas de build, disco reconstruído, robô de testes (Claude 1)
  diario/          material para o vídeo: fotos, clipes, bugs, ideias, linha do tempo
  comunicacao/     vigia e estado da dupla
```

A conversa entre os dois Claudes fica fora desta pasta, em `vigianesx\conversations\`
(`alpha_inbox.md`, `beta_inbox.md` e o quadro `MGB_board.md`).
