# mgs/: o que nós mudamos no Metal Gear Solid

O Metal Gear Solid desta fusão é o da descompilação [FoxdieTeam/mgs_reversing](https://github.com/FoxdieTeam/mgs_reversing),
recompilado com o Crash dentro. O código do jogo é deles e da Konami e **não está aqui**. Aqui está só a nossa parte:

| Arquivo | O que é |
|---|---|
| `metal-gear-bandicoot.patch` | as mudanças em 12 arquivos que já existiam no `mgs_reversing` |
| `source/crash/crash.c`, `crash.h` | o ator novo: desenha o Crash no lugar do Snake, as caixas, o Aku Aku, a bazuca |
| `BASE.txt` | em cima de qual commit do `mgs_reversing` isso se aplica |
| `atualizar_retrato.py` | regrava esta pasta a partir de `repos/mgs_reversing` (só lê de lá) |

> **Retrato do teste 10 (11/10/2026).** O lado MGS ainda está em andamento; esta pasta é uma cópia do estado em que o
> teste 10 foi montado, e vai ser atualizada.

## Como aplicar

```bash
cd repos
git clone https://github.com/FoxdieTeam/mgs_reversing.git
cd mgs_reversing
git checkout f54dbb2a58adfc2755403296c9ebb653fbec277b
git apply ../../mgs/metal-gear-bandicoot.patch
cp -r ../../mgs/source/crash source/
cp ../../mgs/build/finalize_dev_overlay.py build/
```

Faltam dois arquivos, de propósito: `source/crash/crash_data.c` e `crash_data.h`. Eles carregam o modelo, as animações,
as texturas e os sons **do Crash**, e por isso não podem ser publicados. Quem os gera é `motor/empacotar_crash3.py`, a
partir do que `crash_assets/extrair3.py` e `crash_assets/extrair.py` tiram dos **seus** discos do Crash.

Tudo o que é nosso fica atrás de `#ifdef DEV_EXE`: compilando sem a variante (`python build.py`), o resultado continua
batendo byte a byte com o jogo original. A fusão é a variante `dev_exe` (`python build.py --variant=dev_exe`).

## O que cada mudança faz

| Arquivo | Para quê |
|---|---|
| `source/crash/crash.c` | o ator novo. O corpo do Crash: escolhe a animação pela ação do Snake, descomprime e interpola os quadros do Warped (o engatinhar é meio ciclo, tocado normal e espelhado), desenha com pacotes próprios. As caixas do Crash (vestida, chutada, no lugar da ração). A máscara do Aku Aku e a regra das 3 máscaras. A bazuca (o bloco dela vem do CD para a memória dinâmica na hora de usar; o Crash cortado ao meio) e a Wumpa que ela atira. Textura, paletas e sons lidos do `MGS/MGB.DAT`, um arquivo novo no disco (só quando nenhuma fala do jogo está tocando do CD); os sons tocam na voz 20 da SPU, reservada para o Crash (até o teste 10 era a 23, que é o relógio do driver de som: o primeiro som do Crash calava o jogo) |
| `chara/snake/sna_init.c` | cria o Crash junto com o Snake; o giro acerta em volta do corpo inteiro; a derrapada (um estado novo: no MGS1 correr + X só agachava; o Snake invisível desliza freando e derruba quem estiver na frente); a máscara do Aku Aku absorve o golpe (a vida volta antes de o Snake reagir); com a 3ª máscara, invencível e o toque da morte |
| `equip/box.c`, `enemy/boxkeri.c` | a caixa de papelão vira caixa do Crash; chutada, a TNT conta 3, 2, 1 e explode |
| `anime/effect/mark.c`, `enemy/action.c` | o "!" e o "?" dos guardas viram "WOAH!" e "WOAH?", com o grito do Crash |
| `game/item.c` | as rações viram a caixa do Aku Aku (e o item testa o encosto mesmo com o modelo da ração escondido, que o motor passava a achar fora da tela) |
| `libdg/*`, `libgv/libgv.h`, `equip/jpegcam.c` | bandeira "não desenhar" no motor gráfico (calcula, não desenha: o Snake e a ração continuam existindo); devolução dos pacotes do Crash quando o rádio pega a memória toda; a memória de pacotes cai de 188 para 154 KiB por metade, e esses 68 KiB viram espaço para o Crash no executável (o `jpegcam.c` passa a usar o endereço novo) |
| `build/linker_command_file.txt`, `linker_command_file_preprocess.py` | liga os dois arquivos novos; desde o teste 10 a variante não embute mais os personagens do Loading Dock no executável, e o `mark.c` (o "WOAH!") fica no executável em vez de em cada área |
| `build/build.py`, `build/finalize_dev_overlay.py` (novo) | teste 10: a variante liga o código de cada área contra o nosso executável e confere que nenhum endereço do executável mudou entre os dois; uma cópia corrigida do `asm/safechk.s` (o anti-modchip monta endereços em duas metades sem o ajuste de sinal, o que só funciona no endereço original) |
| `game/chara.c`, `game/gamed.c`, `libfs/cdstage.c` | teste 10: o código de cada área volta a ser carregado do disco, como no jogo original (antes a variante embutia só o do Dock e travava depois do elevador) |
| `sound/sd_cli.c` | teste 11: o MGS fica com 7 vagas de efeito sonoro em vez de 8, e a voz 20 fica para o Crash |
| `game/loader.c` | teste 10: o jogo abre na tela de título de verdade; o seletor de fases só quando alguém escreve 1 em `MGB_SeletorDeFases` logo depois de ligar |
| `libfs/file.cnf`, `libfs/libfs.h` | teste 10: o `MGB.DAT` entra na tabela de arquivos que o jogo procura no disco |
