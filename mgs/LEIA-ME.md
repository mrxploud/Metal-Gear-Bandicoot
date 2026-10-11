# mgs/: o que nós mudamos no Metal Gear Solid

O Metal Gear Solid desta fusão é o da descompilação [FoxdieTeam/mgs_reversing](https://github.com/FoxdieTeam/mgs_reversing),
recompilado com o Crash dentro. O código do jogo é deles e da Konami e **não está aqui**. Aqui está só a nossa parte:

| Arquivo | O que é |
|---|---|
| `metal-gear-bandicoot.patch` | as mudanças em 12 arquivos que já existiam no `mgs_reversing` |
| `source/crash/crash.c`, `crash.h` | o ator novo: desenha o Crash no lugar do Snake, as caixas, o Aku Aku, a bazuca |
| `BASE.txt` | em cima de qual commit do `mgs_reversing` isso se aplica |
| `atualizar_retrato.py` | regrava esta pasta a partir de `repos/mgs_reversing` (só lê de lá) |

> **Retrato do teste 8 (11/10/2026).** O lado MGS ainda está em andamento; esta pasta é uma cópia do estado em que os
> testes 6, 7 e 8 foram montados, e vai ser atualizada.

## Como aplicar

```bash
cd repos
git clone https://github.com/FoxdieTeam/mgs_reversing.git
cd mgs_reversing
git checkout f54dbb2a58adfc2755403296c9ebb653fbec277b
git apply ../../mgs/metal-gear-bandicoot.patch
cp -r ../../mgs/source/crash source/
```

Faltam dois arquivos, de propósito: `source/crash/crash_data.c` e `crash_data.h`. Eles carregam o modelo, as animações,
as texturas e os sons **do Crash**, e por isso não podem ser publicados. Quem os gera é `motor/empacotar_crash3.py`, a
partir do que `crash_assets/extrair3.py` e `crash_assets/extrair.py` tiram dos **seus** discos do Crash.

Tudo o que é nosso fica atrás de `#ifdef DEV_EXE`: compilando sem a variante (`python build.py`), o resultado continua
batendo byte a byte com o jogo original. A fusão é a variante `dev_exe` (`python build.py --variant=dev_exe`).

## O que cada mudança faz

| Arquivo | Para quê |
|---|---|
| `source/crash/crash.c` | o corpo do Crash: escolhe a animação pela ação do Snake, descomprime e interpola os quadros, desenha com pacotes próprios |
| `chara/snake/sna_init.c` | o giro acerta em volta do corpo inteiro; a derrapada (um estado novo: no MGS1 correr + X só agachava); a máscara do Aku Aku absorve o golpe |
| `equip/box.c`, `enemy/boxkeri.c` | a caixa de papelão vira caixa do Crash; chutada, a TNT conta 3, 2, 1 e explode |
| `anime/effect/mark.c`, `enemy/action.c` | o "!" e o "?" dos guardas viram "WOAH!" e "WOAH?", com o grito do Crash |
| `game/item.c` | as rações viram a caixa do Aku Aku |
| `libdg/*`, `libgv/libgv.h`, `equip/jpegcam.c` | bandeira "não desenhar" no motor gráfico, devolução dos pacotes do Crash (o rádio pega a memória toda), tamanho da memória de pacotes |
| `build/linker_command_file.txt` | liga os dois arquivos novos |
