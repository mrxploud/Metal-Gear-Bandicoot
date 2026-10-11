# repos/

Esta pasta fica **vazia no repositório**. Aqui moram os clones dos projetos em que a fusão se apoia; cada um tem o
seu próprio repositório e os seus próprios autores (ver [`../CREDITOS.md`](../CREDITOS.md)).

Clone cada um aqui dentro. Entre parênteses, o commit em que tudo foi feito e testado:

```bash
git clone https://github.com/FoxdieTeam/mgs_reversing.git      # f54dbb2a58adfc2755403296c9ebb653fbec277b
git clone https://github.com/FoxdieTeam/psyq_sdk.git           # fec561c5771a981a6090c315cbe338f7967137cd
git clone https://github.com/wurlyfox/c1.git                   # 256fdcef59f15a190290cc19db3fa9a707843b69
git clone https://github.com/ManDude/goocdump.git              # b65b48aa9c44c2ab3de0744345007b9d8aa7fd39
```

| Clone | Para quê |
|---|---|
| `mgs_reversing` | a descompilação do Metal Gear Solid: Integral. É o MGS que compilamos. As nossas mudanças estão em [`../mgs/`](../mgs/) |
| `psyq_sdk` | o compilador e as bibliotecas que o `mgs_reversing` usa para compilar |
| `c1` | só para o Crash 1: o extrator lê a tabela `uv_map` de `c1/src/gfx.c` na hora de rodar (ela não foi copiada para cá) |
| `goocdump` | só para o Crash 1: os nomes das animações e dos sons (`WILLY_*`) |

Dois projetos foram lidos sem clonar: o [CrashEdit](https://github.com/cbhacks/CrashEdit) (todo o formato do Crash 3
veio do código dele) e o [CrashBandicoot-Launcher](https://github.com/Matteo842/CrashBandicoot-Launcher) (referência
do funcionamento interno do Crash 1).
