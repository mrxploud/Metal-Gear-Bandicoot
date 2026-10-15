# Metal Gear Bandicoot (English)

![Crash Bandicoot in the Loading Dock opening shot of Metal Gear Solid](docs/img/00_capa.png)

**A fusion of two PlayStation games: Crash Bandicoot, playable inside _Metal Gear Solid_, hiding in his box,
spinning into guards and firing Wumpa fruit from a bazooka. Now with two-player split-screen co-op.**

A project by **[mrxploud](https://github.com/mrxploud)** (ByteMirage), made together with Claude.
The full story, with every bug along the way, is in the [Portuguese README](README.md).

[**Discord**](https://discord.com/invite/4H5hGwVnPn) · [**YouTube (English): ByteMirage Experiments**](https://www.youtube.com/@ByteMirageExperiments) · [**YouTube (Portuguese): ByteMirage**](https://www.youtube.com/@ByteMirage) · [**Download (.zip)**](https://github.com/mrxploud/Metal-Gear-Bandicoot/archive/refs/heads/main.zip)

## What it is

Both games were opened up from the inside. Metal Gear Solid is rebuilt from its decompilation, with new code in it;
Crash is pulled out of his own disc, vertex by vertex, and drawn in Snake's place. You play the whole game, both discs,
from the title screen.

## What's new: the expansion

- **Two players.** Press Start on controller 2 and **Crash 2** (blue, so nobody gets lost) joins. Close together you
  share the full screen; when Crash 2 walks off camera, the screen splits.
- **Climbing.** The tops of boxes, containers and fences are floor now.
- **TNT hurts everyone:** guards, both Crashes and any TNT nearby.
- **The guards see Crash 2**, yell "WOAH!" and open fire.
- **30 frames per second with two players** (Metal Gear Solid's maximum).
- **Crash 2 respects the level:** same walls as Crash 1, floats in water, picks up items.
- To fit all of this into the PlayStation's 2 MB, Crash's death animations now live on the CD. 96 bytes left.

## How to play

You need your own copies of the games. **No games, BIOS or discs are distributed here.**

| Game | Code |
|---|---|
| Metal Gear Solid: Integral, disc 1 (Japan) | SLPM-86247 |
| Metal Gear Solid: Integral, disc 2 (Japan) | SLPM-86248 |
| Crash Bandicoot 3: Warped (Europe) | SCES-01420 |
| Crash Bandicoot (USA) | SCUS-94900 |

Tested only on **Windows 11** with **Python 3.12**. In short: install the requirements, clone the Metal Gear Solid
decompilation and apply our patch, extract Crash from his discs, build, and assemble the new discs. Every command is in
the step-by-step guide of the Portuguese README: [**Como rodar**](README.md#como-rodar) (the commands are the same in
any language). Then double-click **`JOGAR.bat`**. The discs it builds also run in any PlayStation emulator.

## Controls

| Keyboard | Controller | In game |
|---|---|---|
| arrows | d-pad / stick | walk and run |
| Z | A | jump (press again in the air: double jump) |
| X | B | Crash's spin |
| A | X | hold: bazooka; release: fire a Wumpa |
| W | RB | crouch / crawl / slide |
| S | Y | first person |
| Enter | Start | pause |
| Backspace | Back | radio (save with Mei Ling, 140.96) |

**Player 2 (blue Crash):** a second controller, or on the keyboard **F2** join / **F3** leave, **I J K L** move,
**U** jump, **O** spin. Triangle on controller 2 brings Crash 2 back next to Crash 1.

## Credits and notes

The full list is in [`CREDITOS.md`](CREDITOS.md) (Portuguese).

- **Idea, direction and testing:** [mrxploud](https://github.com/mrxploud) (ByteMirage).
- **Investigation and code:** Claude, by Anthropic, through [Claude Code](https://claude.com/claude-code), directed by mrxploud.
- **The inspiration:** the "Metal Gear Bandicoot: Wumpa Fruit Eater" drawing by **u/Max_Comix**, plus **yuvi3000** and
  **ZXE102R** in the comments.
- **[FoxdieTeam](https://github.com/FoxdieTeam):** [mgs_reversing](https://github.com/FoxdieTeam/mgs_reversing), the
  Metal Gear Solid: Integral decompilation, and [psyq_sdk](https://github.com/FoxdieTeam/psyq_sdk).
- **[CBHacks](https://github.com/cbhacks)** ([CrashEdit](https://github.com/cbhacks/CrashEdit)),
  **[wurlyfox](https://github.com/wurlyfox)** ([c1](https://github.com/wurlyfox/c1)) and
  **[ManDude](https://github.com/ManDude)** ([goocdump](https://github.com/ManDude/goocdump)): the Crash formats.
- **[Matteo842](https://github.com/Matteo842)** ([CrashBandicoot-Launcher](https://github.com/Matteo842/CrashBandicoot-Launcher))
  and **[BlackLabelHQ](https://github.com/BlackLabelHQ)** ([RecompOne](https://github.com/BlackLabelHQ/RecompOne)).
- Emulation by the libretro [PCSX ReARMed](https://github.com/libretro/pcsx_rearmed) core; discs rebuilt with
  [mkpsxiso](https://github.com/Lameguy64/mkpsxiso). Neither is distributed here.
- _Metal Gear Solid_ © Konami. _Crash Bandicoot_ © Sony Interactive Entertainment / Naughty Dog / Activision.
  Fan project, non-profit, not affiliated with those companies. Screenshots show the original games for illustration only.
