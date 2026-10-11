# crash_assets: o lado Crash da fusão (Claude 2)

Aqui mora o programa que **tira o Crash do disco dele** e entrega para o lado MGS (Claude 1, `motor/`) no formato
combinado no quadro (`MGB_board.md`, contrato v1). Nada é redesenhado à mão: modelo, animações, cores, texturas e
sons são os bytes do disco, convertidos.

## Crash 3 (Warped): é o Crash da fusão desde 11/10/2026

Decisão do ByteMirage (11/10, 08:26): o Crash 1 não engatinha nem derrapa, então **o Crash jogável passa a ser o do
Crash Bandicoot 3**. Disco: `discs\Crash Bandicoot 3 - Warped (Europe Australia) (EnFrDeEsIt)\` (**SCES-01420**).

```
python -I extrair3.py --disco "..\discs\<pasta do Warped>\<...>.cue"
python -I extrair3.py --disco <...> --sem-previas     só os dados: 6 segundos
python -I ver3.py --conferir                          confere a entrega inteira SEM abrir o disco
python -I ver3.py C3_ENGATINHAR                       desenha uma animação lendo só a entrega
```

- A entrega fica em **`out_c3/`** (a `out/` do Crash 1 não é tocada): 292 animações, 3.305 quadros-chave, 90 modelos, 394 sons.
  Mesmo contrato da `out/`, com os acréscimos do Crash 3 (cor por canto, chaves/toca/interpola, `k` por eixo,
  `comprimido/`). O que muda está explicado no `model.json` (`conversao`, `cores`, `interpolacao`) e no MGB #27.
- `TABELA_SNAKE_CRASH3.md` (v4): o que tocar em cada estado do Snake. `out_c3/CATALOGO.md`: tudo, com GIF.
- `nomes_c3.json`: os apelidos `C3_*`. **São nossos**, dados olhando as prévias, com grau de certeza. O Crash 3 não
  tem os scripts descompilados com nome; a entrada no disco é o nome de verdade.
- `crashlib/formatos3.py` (modelo em fita de triângulos, quadro em fila de bits) e `crashlib/banco3.py` (o disco
  inteiro na memória, a tabela de animações de cada script, as páginas de textura).

O que o disco do Warped ensinou:
1. o contêiner (NSF) é o mesmo do Crash 1 e o leitor antigo serviu sem mudar; o que mudou foi o modelo e a animação;
2. o disco guarda **metade dos quadros** (15 por segundo) e o jogo interpola; e cada quadro é uma fila de bits com a
   diferença de cada vértice para o anterior (14 bits por vértice em vez de 24);
3. nos modelos **sem** compressão (caixas, Aku Aku) os 3 bytes vêm na ordem x, z, y; na fila comprimida, x, y, z;
4. o sentido dos triângulos vem ao contrário do Crash 1 (a entrega já sai igual à do Crash 1);
5. cada quadro traz 4 pontos fora da malha: o nº 1 é o rosto (encaixe do Aku Aku), os outros são a raiz no chão;
6. no Windows, `CdsiV` e `CdSiV` são o mesmo arquivo: nomes que só diferem em maiúscula ganham sufixo;
7. nome não é prova: o modelo que parecia ser a bazuca (`Cgb0G`) são só as pernas. A bazuca existe: o jogo corta o
   Crash ao meio (`Cgt0G` = tronco com a bazuca, `Cgb0G` = pernas) para ele mirar andando;
8. **prévia também não é prova** (teste 5 do ByteMirage): o engatinhar parecia laço e é **meio ciclo espelhado**; o
   "engatinhar parado" é a transição de agachado para de quatro. Por isso o `extrair3.py` agora **mede** como cada
   animação emenda (`laco` e `como_tocar` no `model.json`);
9. a caixa do Crash 1 não tem a face de trás (a câmera nunca a via); as do Warped têm as 6. E no Warped a "?", a do
   Aku Aku e a da vida são a mesma caixa de madeira (`BN10G`) com outra "cara" (1 de 8 texturas);
10. os sons do Warped têm os mesmos nomes do Crash 1 (`arg0A` = o "Woah!", `spn0A`, `WD10A`...): `out_c3/snd/`.

De onde veio o formato: **CrashEdit, do CBHacks** (ver `../CREDITOS.md`), lido no GitHub; nada foi copiado.

## Estado do Crash 1 (11/10/2026)

- **Rodou no disco de verdade** (SCUS-94900, 44 fases, 2 minutos). A entrega está em `out/`: 78 animações, 982
  quadros, 34 modelos, 58 paletas, 53 sons.
- O que saiu: o Crash (50 animações, inclusive montado no javali), todas as caixas (madeira, "?", TNT com a
  contagem, ferro, "!", a do Aku Aku...), o Aku Aku, a sombra, a Wumpa (sprite de 14 quadros) e o assistente de
  laboratório.
- `ver.py` desenha qualquer animação lendo **só** a entrega (sem o disco): é a prova de que os arquivos se bastam.
- O "Woah!" é a entrada de som `arg0A` (ver `TABELA_SNAKE_CRASH.md`, seção Sons).
- `testes/teste_sintetico.py` (o CD de mentira) continua passando: 27 de 27.

O que o disco ensinou que a documentação não dizia (os três tropeços estão em `../diario/BUGS.md`):
1. o campo "quantidade de materiais" do modelo conta palavras de 4 bytes, não materiais;
2. a tabela de retângulos de textura usa (99, 99) como "este canto não existe";
3. o giro não é a animação `FLIP`; é a `BLOW`, com modelo próprio.

**Improvisos (11/10, a pedido do ByteMirage):** o Crash 1 não tem andar agachado nem derrapada; eles entraram na
série no Crash 2. `improvisos.py` monta os dois com quadros do Crash 1 e grava em `out/` com o prefixo `IMPROVISO_` e
`"improviso": true` no `model.json`. São montagem nossa, não animação original, e é assim que devem ser descritos no
README final e no vídeo. Rodar `improvisos.py --entregar` depois de cada `extrair.py` (que recria o `model.json`).

## Como rodar

```
python -I extrair.py --disco "..\discs\<Crash Bandicoot (USA)>.cue"
python -I extrair.py --disco <...> --so-indice          só cataloga o que existe no disco (rápido)
python -I extrair.py --disco <...> --fases 03,05        só algumas fases (2 últimos caracteres do nome do .NSF)
python -I testes/teste_sintetico.py <pasta_temporaria>  o teste sem disco
```

Precisa de Python 3.12 com `numpy` e `Pillow` (já estão na máquina). O disco esperado é o **americano,
SCUS-94900**, em `.cue`+`.bin` (ou `.bin`/`.img`/`.iso`). **Não lê `.chd`.**

## O que sai em `out/`

| Arquivo | O que é |
|---|---|
| `indice.json` | tudo o que existe no disco: nome, tipo, em quantas fases aparece |
| `model.json` | modelos (triângulos + materiais), animações, conversão aplicada, **orçamento de memória** |
| `anim_<NOME>.bin` | `int16` [quadro][vértice][x,y,z], depois `int8` [quadro][vértice][nx,ny,nz] |
| `tex/pagina_*.bin` | as páginas de textura originais (64 KB cada, como estão na VRAM do Crash) |
| `tex/atlas_4bits.bin/.png` | só os retângulos usados, reempacotados, na profundidade original, com as paletas no json |
| `sprites/` | quadros de sprite recortados (a Wumpa é sprite, não modelo) |
| `snd/*.vag` + `*.wav` | o ADPCM original do SPU e um WAV para conferir. No `.vag`, os bytes do disco começam no **byte 64** (48 de cabeçalho + 16 de zeros do formato); o dado do Crash já traz o próprio bloco inicial de zeros e o terminador |
| `cru/<NOME>.bin` | a mesma animação nos 6 bytes por vértice do disco (2/3 do tamanho); a fórmula está no `model.json` |
| `previews/<grupo>/` | folha de contato e GIF de cada animação: **material do vídeo** |
| `CATALOGO.md` | a lista de animações com as prévias |

Coordenadas (contrato v1): pés em y=0, Y para cima, frente +Z, e o Crash parado (`WILLY_STANCE1`, quadro 0) mede
**exatamente 1000** de altura. O fator usado fica em `model.json` → `conversao.escala_original`.

Conferido nas prévias reais: sem trocar nem inverter eixo nenhum o Crash já sai de frente para +Z, e o texto "TNT"
da caixa sai legível (não está espelhado). Os triângulos estão em sentido horário vistos de fora. O `config.json`
(`{"ordem": [0, 1, 2], "eixos": [1, 1, 1]}`) existe para trocar eixos, mas não foi preciso.

## Como o Crash é guardado (o que aprendemos lendo, antes de ter o disco)

- O disco tem um arquivo `.NSF` por fase. Um NSF é uma fila de páginas de 64 KB, algumas comprimidas.
- O modelo (`TGEO`) é uma lista de triângulos; cada triângulo aponta para uma cor ou um pedaço de textura.
- A animação (`SVTX`) **não tem esqueleto**: cada quadro traz todos os vértices de novo, 6 bytes por vértice
  (x, y, z e a normal). É por isso que o Crash estica e amassa daquele jeito, e é por isso que ele não cabe no
  formato de boneco articulado do Snake.
- Dentro do jogo o Crash se chama **Willy** (de Willy the Wombat, o nome de desenvolvimento). Todas as animações
  dele são `WILLY_*`, e as do Aku Aku são `WITCH_DOCTOR`.

## De onde veio cada conhecimento (créditos, ver `../CREDITOS.md`)

| O quê | De quem |
|---|---|
| Formatos NSF, TGEO, SVTX, texturas, a conta do vértice | **wurlyfox**, [c1](https://github.com/wurlyfox/c1) (`src/ns.h`, `src/formats/`, `src/pc/gfx/soft.c`, `tex.c`) |
| A tabela `uv_map` de 600 retângulos de textura | lida em tempo de execução de `repos/c1/src/gfx.c` (não copiada para cá) |
| Nomes das animações e dos sons | **ManDude**, [goocdump](https://github.com/ManDude/goocdump) (`Crash 1/NTSC-J/*.gooc`) |

## Arquivos

```
extrair3.py            o programa do Crash 3 (Warped) -> out_c3/
ver3.py                confere e desenha a entrega do Crash 3 sem o disco; tem o decodificador de referência
nomes_c3.json          os apelidos C3_* (nossos) das animações do Crash 3
TABELA_SNAKE_CRASH3.md que animação do Crash 3 toca em cada estado do Snake (M-15, v4)
extrair.py             o programa do Crash 1 -> out/
ver.py                 desenha uma animação lendo só a entrega (frente, lado, costas, todos os quadros)
ouvir_sons.py          passa os sons pelo Whisper do estúdio de vídeo para descobrir qual é qual
improvisos.py          monta movimentos que o Crash 1 NÃO tem (andar agachado, derrapada) com quadros dele; `--entregar` grava em out/
estudo_compressao.py   mede quanto cada jeito de encolher as animações estraga (gera ESTUDO_COMPRESSAO.md)
crashlib/disco.py      lê arquivos de dentro de uma imagem de CD (ISO 9660, setores de 2352 ou 2048)
crashlib/nsf.py        páginas, descompressão, entradas, nomes (EID)
crashlib/formatos.py   TGEO, SVTX, texturas, som (Crash 1)
crashlib/formatos3.py  TGEO e SVTX do Crash 3 (fita de triângulos, fila de bits)
crashlib/banco3.py     o disco do Crash 3 na memória: entradas, tabela do script, páginas de textura
crashlib/raster.py     o desenhista das prévias (triângulos com z-buffer, em numpy)
testes/                o teste com o CD de mentira
TABELA_SNAKE_CRASH.md  que animação do Crash toca em cada estado do Snake (M-09, v2, com o disco aberto)
out/                   a entrega (20 MB; não publicar: é conteúdo do jogo)
```
