# Créditos (lembrete obrigatório)

Pedido do ByteMirage em 10/10/2026: **dar crédito a estas pessoas** no README final, no vídeo e em qualquer
publicação. Ninguém sai desta lista; se descobrirmos mais alguém, entra.

## O projeto
- **Ideia, direção e testes:** mrxploud ([ByteMirage](https://www.youtube.com/@ByteMirage)).
- **Investigação e código:** Claude 1 e Claude 2 (Claude, da Anthropic, pelo Claude Code), sob a direção de mrxploud.

## A inspiração
- **u/Max_Comix**: o desenho "Metal Gear Bandicoot: Wumpa Fruit Eater", postado no r/crashbandicoot em 2018.
  <https://www.reddit.com/r/crashbandicoot/comments/a5ofbf/i_found_this_old_crash_bandicoot_metal_gear_solid/>
- Os comentários do mesmo post (lidos pelo ByteMirage em 11/10/2026, prints no chat):
  - **yuvi3000**: "You could hide under a Crash Bandicoot crate. It's perfect." (a ideia da caixa do Crash)
  - um usuário hoje **apagado**: "Instead of "!" it's "Woah!"" (o alerta dos guardas vira "Woah!")
  - **ZXE102R**: "Woah! Whose footprints are these?! / Woah! What was that noise? / WOAH! THERE HE IS / Honestly we
    need a woah mod for metal gear solid now."
  - um usuário hoje **apagado**: "and a mod to turn bad guys into the lab assistant" (guardas viram os assistentes
    de laboratório do Cortex)
  - **Winter_wrath**: "Would play".

## As bases técnicas
- **FoxdieTeam**: [mgs_reversing](https://github.com/FoxdieTeam/mgs_reversing), a descompilação do Metal Gear Solid
  Integral. É o MGS que compilamos e modificamos. Também o [psyq_sdk](https://github.com/FoxdieTeam/psyq_sdk) usado no build.
- **Matteo842**: [CrashBandicoot-Launcher](https://github.com/Matteo842/CrashBandicoot-Launcher), a recompilação
  do Crash Bandicoot para PC; referência para endereços e funcionamento interno do Crash 1.
- **wurlyfox**: [c1](https://github.com/wurlyfox/c1), o port do motor do Crash 1 para C. Os formatos do modelo e das
  animações do Crash (`SVTX`, `TGEO`, `NSF`) vêm dele. O próprio Crash Launcher diz que não existiria sem o c1.
- **ManDude**: [goocdump](https://github.com/ManDude/goocdump), os scripts GOOL do Crash descompilados (comportamento
  das caixas, inimigos e do próprio Crash).
- **BlackLabelHQ**: [RecompOne](https://github.com/BlackLabelHQ/RecompOne), o recompilador usado pelo Crash Launcher.
- **CBHacks** (wiki e CrashEdit): documentação dos arquivos do Crash.
- **CBHacks**, de novo e com destaque: [CrashEdit](https://github.com/cbhacks/CrashEdit) (ramo `deprecate`). Desde
  11/10/2026 o Crash da fusão é o do **Crash Bandicoot 3 (Warped)**, e **todo o formato dele** (a animação comprimida
  em fila de bits, o modelo em fita de triângulos, as texturas, a tabela de animações do script) foi aprendido lendo o
  código do CrashEdit: `Frame.cs`, `ModelEntry.cs`, `ModelStruct.cs`, `ModelPosition.cs`, `ModelTexture.cs`,
  `ModelExtendedTexture.cs`, `AnimationRenderer.cs`, `GLViewer.cs`, `GOOLEntryLoader.cs` e os `*Group2/3.cs`. Não existe
  descompilação com nomes para o Crash 3; sem o CrashEdit o extrator (`crash_assets/extrair3.py`) não existiria.
  Nenhum código deles foi copiado para o projeto: o leitor foi escrito em Python a partir da leitura.

## Ferramentas (preencher conforme usarmos)
- Emuladores: DuckStation / PCSX-Redux (grumpycoders) / núcleo libretro **PCSX ReARMed** (notaz e equipe libretro).
- [mkpsxiso](https://github.com/Lameguy64/mkpsxiso) (Lameguy64), para reconstruir o disco.

## Os jogos
- *Metal Gear Solid* © Konami. *Crash Bandicoot* © Sony Interactive Entertainment / Naughty Dog / Activision.
- O Crash jogável vem do *Crash Bandicoot 3: Warped* (disco europeu SCES-01420, do ByteMirage); as caixas, o Aku Aku
  e os sons dos testes 1 a 4 vêm do *Crash Bandicoot* 1 (SCUS-94900).
  Projeto de fã, sem fins lucrativos, sem ligação com as empresas. Nenhum jogo, BIOS ou disco é distribuído.
