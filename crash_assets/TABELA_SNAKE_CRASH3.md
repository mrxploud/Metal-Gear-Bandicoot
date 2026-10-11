# Estado do Snake → animação do Crash 3 (M-15, v4.1)

**v4.1 (11/10, 10:05), depois do teste 5 do ByteMirage:** corrigidos três "como tocar" que eu tinha escrito olhando a prévia e que causaram bugs (o engatinhar é meio ciclo espelhado; o "engatinhar parado" é uma transição; na derrapada segura-se a chave 2, não a última). Agora cada emenda foi **medida** nas chaves (distância entre poses) e vem no `model.json` em `laco` e `como_tocar`. Entraram as caixas do Warped.

**v4 = a tabela refeita para o Crash do Warped** (11/10/2026, decisão do ByteMirage: "vamos usar o Crash Bandicoot 3",
porque o Crash 1 não agacha andando nem derrapa). A v3, do Crash 1, continua em `TABELA_SNAKE_CRASH.md` (as caixas,
o Aku Aku e os sons de lá seguem valendo até trocarmos pelos do 3).

Fontes: disco **SCES-01420**, extraído por `extrair3.py` para `out_c3/`. Os estados do Snake são os mesmos da v3
(`repos/mgs_reversing/source/chara/snake/sna_init.c`). **Os nomes `C3_*` são apelidos nossos**, dados olhando as
prévias (`nomes_c3.json`): o Crash 3 não tem os scripts com nome como o Crash 1 tinha. A coluna "entrada" é o nome de
verdade no disco. Prévias: `out_c3/previews/<grupo>/<NOME>.gif`.

Como ler "chaves / toca": o disco guarda os quadros-chave a 15 por segundo e o jogo toca a 30, fazendo a média entre
duas chaves vizinhas. `11 / 20` = 11 chaves no disco, o script toca 20 quadros.

## Ficar e andar

| Snake | Crash 3 | Entrada | Chaves / toca | Como tocar |
|---|---|---|---|---|
| parado em pé | `C3_PARADO` | Cr10V | 11 / 20 | laço (a última chave é igual à primeira). Ele respira e balança |
| parado há muito tempo | `C3_COCA_A_CABECA`, depois `C3_IOIO` | CC20V, Cy10V | 10 / 18, 99 / 197 | uma vez e volta ao parado. O ioiô (62 KB no disco) só se sobrar memória, ou lido do CD |
| andar devagar (analógico pouco inclinado) | `C3_ANDAR` | CrW0V | 11 / 20 | laço. Novidade: o Crash 1 só corria |
| correr | `C3_CORRER` | CrR0V | 9 / 17 | laço. **Passo inteiro** (as duas pernas): acabou o espelhamento do Crash 1 |
| virar de costas correndo | `C3_MEIA_VOLTA` | Ct10V | 6 / 11 | opcional |
| agachar | `C3_AGACHAR` e segura `C3_AGACHADO` | CrD1V, CrD2V | 3 / 5, 1 / 1 | levantar = `C3_AGACHAR` ao contrário |
| **deitar e rastejar** (ações 20, 22, 23) | **`C3_ENGATINHAR`** | CCw1V | 9 / 16 | **O pedido do ByteMirage.** **MEIO CICLO**, como a corrida do Crash 1: tocar os 16 quadros normais, depois os mesmos espelhados em x (x → -x, descarte de costas invertido), e repetir. A última chave é o espelho da primeira (medido: 19 de diferença de forma, contra 77 sem espelhar). Sem espelhar dá um tranco de 206 unidades a cada volta |
| parado deitado (ação 22) | `C3_ENGATINHAR`, **parado na chave 0** | CCw1V | | não trocar de animação entre 22 e 23: só parar e andar o quadro |
| agachado → deitado, e a volta | `C3_ENGATINHAR_PARADO` (o nome engana: é a **transição**) | CCw2V | 2 / 3 | uma vez, 0 → 1 ao deitar e 1 → 0 ao levantar. **Nunca em laço**: a chave 0 é o `C3_AGACHADO` e a 1 é a chave 0 do `C3_ENGATINHAR`, 211 unidades uma da outra |
| **correr + X** (no MGS1: 12 → 16 → 20, deita vindo da corrida) | **`C3_DERRAPADA`** | CrS1V | 5 / 8 | chave 0 = entrada; **chaves 1 e 2 = a pose da derrapada** (segurar a 2 enquanto desliza, pés na frente); chaves 3 e 4 = saindo, a 4 já é quase o `C3_AGACHADO`. Não segurar a última |
| nadar debaixo d'água (ação 24) | `C3_ENGATINHAR` por enquanto | | | o Warped tem o Crash de mergulhador (modelo `CS1eG`, 257 vértices, com cilindro e pé de pato): ver "Extras" |
| encostado na parede | `C3_PARADO` | | | a ver no jogo |

## Quando o Crash não aparece

Igual à v3: dentro da caixa, primeira pessoa e duto de ar.

## Bater e apanhar

| Snake | Crash 3 | Entrada | Chaves / toca | Como tocar |
|---|---|---|---|---|
| soco, soco, chute | **`C3_GIRO_LEVE`** (modelo `WiBcG`: 248 vértices, 386 triângulos) ou `C3_GIRO` (`WiBlG`: 435 / 586) | WiBcV / WiBlV | 10 / 10, **sem interpolar** | o tornado com a cabeça dele no meio. Em laço enquanto dura o golpe. As duas versões são iguais à vista; a leve existe no próprio disco (9 fases) |
| leva um tiro / susto (dano) | `C3_BEIRADA_SUSTO` | Ce20V | 2 / 2 | abre os braços de olho arregalado: é a cara do "WOAH!" |
| derrubado e levanta (granada perto, soco do guarda) | `C3_DERRUBADO_LEVANTA` | Cm10V | 14 / 26 | cai sentado de costas, sacode a cabeça, levanta. Uma animação só resolve o cair e o levantar |
| levantar do chão (depois de rastejar ou de ser derrubado) | `C3_LEVANTAR_DO_CHAO` | CfS6V | 7 / 13 | estatelado de barriga → em pé |
| pular de cima de algo / cair | `C3_PULO_SAIDA`, `C3_PULO_SUBINDO`, `C3_PULO_POUSO` | CJS1V, CJU1V, CJL1V | 3 / 4, 7 / 12, 11 / 20 | para quando houver pulo |

## Morrer

No Warped cada jeito de morrer é um **modelo à parte** (o do Crash normal não é usado), e todos são baratos de
guardar porque só entram na hora:

| Como morreu no MGS | Crash 3 | Entrada / modelo | Chaves / toca | Peso |
|---|---|---|---|---|
| tiro, soco (o comum), sem modelo novo | `C3_CAI_DE_CARA` ou `C3_DESMAIA` | Cd1iV, Co1iV / o próprio `Cr10G` | 10 / 18, 12 / 22 | 6,3 KB e 7,5 KB no disco. Atenção: vêm de fases de gelo e afundam ~20% no chão; subir pelo `caixa` de cada quadro |
| granada, Claymore, C4, **TNT chutada** | **`C3_MORTE_OLHOS_E_TENIS`** | CE10V / `CE10G` (122 vértices, 220 triângulos) | 23 / 45 | 5,2 KB. Some tudo, caem os olhos e os tênis |
| fogo, explosão do tanque | `C3_MORTE_CINZAS` | WF10V / `WF10G` (829 vértices, 732 triângulos, uma cor só: preto) | 21 / 40 | 22 KB. Caro |
| o clássico (para o GAME OVER) | `C3_MORTE_ANJO` | Cda0V / `Cda0G` (306 vértices, 568 triângulos, todos translúcidos) | 39 / 77 | 20 KB. O Crash vira anjinho e sobe |

Sugestão para o primeiro teste: morte comum = `C3_CAI_DE_CARA`; morte por explosão (a TNT já explode) =
`C3_MORTE_OLHOS_E_TENIS`. O anjinho no GAME OVER fica como pergunta para o ByteMirage.

## As caixas (as do Warped, com as 6 faces)

A caixa do **Crash 1 não tem a face de trás** (-z): a câmera daquele jogo nunca vê as costas de uma caixa. No MGS a
câmera gira e o buraco aparece (bug 2 do teste 5). As do Warped têm as 6 faces (8 vértices, 12 triângulos, lado 540).

| MGS | Nome | Modelo |
|---|---|---|
| caixa de papelão A | `C3_CAIXA_MADEIRA` | `BN10G` |
| caixa de papelão B | `C3_CAIXA_INTERROGACAO` | `BN10G_cara2` |
| caixa de papelão C | `C3_CAIXA_TNT` | `BT10G` |
| a contagem 3, 2, 1 | `C3_CAIXA_TNT_3`, `_2`, `_1` | `BT40G`, `BT30G`, `BT20G` |
| quebrando | `C3_CAIXA_QUEBRANDO` (12 chaves) | `BE10G` |
| **item no chão = caixa do Aku Aku** (pedido do ByteMirage) | `C3_CAIXA_AKU_AKU` | `BN10G_cara3` |
| vida | `C3_CAIXA_VIDA` (a cara do Crash) | `BN10G_cara1` |
| outras prontas | NITRO, ferro, ferro com "!", verde com "!", seta, listrada, trancada, checkpoint "C", contorno, relógio | `C3_CAIXA_*`, `C3_RELOGIO` |

No Warped, a "?", a do Aku Aku, a da vida e as douradas de tempo são **a mesma caixa de madeira com outra cara**: o
modelo `BN10G` escolhe 1 de 8 texturas. A entrega traz cada cara como um modelo (`BN10G_cara1..6`).
Aku Aku: `C3_AKU_AKU` (`WD10G`), `C3_AKU_AKU_DOURADO` (`WD30G`), `C3_AKU_AKU_PENA` (`WD20G`); sons `WD10A`, `WD20A`
em `out_c3/snd/`. Quando ele vira invencibilidade, a máscara vai para o ponto do rosto (`especiais[1]`).

## A arma: a bazuca de Wumpa (medida em 11/10, 10:35)

No Warped, quando o Crash usa a bazuca, o jogo **corta ele ao meio**: um modelo é o tronco com a bazuca no ombro, o
outro são as pernas (assim ele mira para um lado e anda para o outro). Com a arma do MGS na mão troca-se o `Cr10G`
pelos dois. **O tronco não usa a raiz das pernas:** cada vértice dele é desenhado em `especiais[0]` da chave atual das
pernas (a cintura; parado é (0, 399, -14)) + vértice. Montado assim mede 1073 (o Crash inteiro, 1000).

| Momento | Tronco (`Cgt0G`, 265 vértices, 498 triângulos) | Pernas (`Cgb0G`, 93 vértices, 164 triângulos) |
|---|---|---|
| sacar | `C3_BAZUCA_SACA` (CgT0V, 6 / 11), uma vez | `C3_BAZUCA_PERNAS_SACA` (CgB0V, 5 / 9): o pulinho |
| mirando | **chave 0 do `C3_BAZUCA_TIRO`, parada** | `C3_BAZUCA_PERNAS_PARADO` (Cs3bV, laço) ou `_ANDANDO` (Cs4bV, laço) |
| atirar | `C3_BAZUCA_TIRO` (Cgt0V, 5 / 8), 0 → 4 uma vez: o coice, 356 para trás | `C3_BAZUCA_PERNAS_TIRO` (Cgb0V, 5 / 9) |
| pular | a mira | `C3_BAZUCA_PERNAS_PULO` (Cs6bV, 8 / 15) |

Os pares vêm no nome do disco: `Cgt0V`/`Cgb0V` = tiro em cima/embaixo; `CgT0V`/`CgB0V` = sacar em cima/embaixo.
A fruta do tiro é o sprite da Wumpa (`sprites[0]`, `C3_WUMPA`: 14 quadros de 32 x 32 em 256 cores; há uma redução
nossa para 16 cores). Ela nasce em `especiais[2]` do tronco, no eixo do cano ((-166, 460, 514) na mira, mais a
cintura), e vai para +Z. Sons: `Cg10A` (4.000 bytes; pela forma da onda é o tiro), `Cg20A`, `Cg30A`: são os três que
o script da bazuca cita e existem exatamente nas 15 fases em que a bazuca existe. Não foram ouvidos.

Sozinhas, as pernas andando parecem uma calça fugindo: serve de piada (uma morte rara, por exemplo).

## Extras que o disco do Warped deu de presente

| O quê | Entrada | Para quê |
|---|---|---|
| **a dança da vitória** | `C3_DANCA_1`, `_2`, `_3` (CD10V, CD20V, CD30V; 44 + 44 + 5 chaves, só nas 5 fases de chefe) | fim de fase, ou depois de derrubar o último guarda. 58 KB: ler do CD |
| o ioiô | `C3_IOIO` + `C3_IOIO_OBJETO` | parado há muito tempo |
| se equilibrando | `C3_BEIRADA` (Ce10V, 21 / 40) | na beira da passarela do Dock, antes de cair na água |
| a barrigada | `C3_BARRIGADA_AR_*` + `C3_BARRIGADA_CHAO` | golpe de cima (não há no MGS; ideia) |
| mergulhador | `CS1eG` e as `CS*eV` | nadar no Dock (o jogo começa na água) |
| as 64 caras | `out_c3/previews/caras.png` | piscar, cara de susto no "WOAH!", cara de morto |

## Pontos de encaixe (os 4 "vértices especiais" de cada quadro)

Cada quadro traz, fora da malha, 4 pontos. No `model.json` → `por_quadro[i].especiais`, já no espaço do contrato:
- **nº 1: o rosto.** Parado fica em (0, 673, 294): na frente do focinho. É para lá que o Aku Aku vai quando vira
  invencibilidade (no Crash 1 era o vértice 0 do `WillG`). Acompanha a cabeça em todas as animações.
  **Medido (v4.1):** em todas as chaves das animações do conjunto ele fica entre 68 e 102 unidades da ponta do
  focinho (vértice 145), sempre na frente.
- **nº 0, 2 e 3: não sei o que são.** Parado valem (0, 0, 0) e eu tinha escrito "a raiz no chão"; mas agachado o
  nº 0 vai para (0, 327, 498), na frente do rosto. **Não usar como chão.**
- No giro (`WiBcG`) os pontos são outros: nº 0 = (0, 1129, 0), em cima da cabeça, no eixo; não há "rosto".
- A caixa do Aku Aku (`BN10G_cara3`) é a única peça do conjunto com textura de **8 bits** (a cara da máscara, 32 x 32,
  256 cores). Há uma redução nossa para 16 cores em `out_c3/tex/reduzidas/`, pior que a original.

## Memória (os números que importam para os 2 MB)

| | Crash 1 (hoje, teste 4) | Crash 3 |
|---|---|---|
| vértices | 381 | **305** |
| triângulos | 732 | **574** (53 com textura, 4 translúcidos, 18 sem descarte de costas) |
| cores | uma por triângulo + luz por normal | 90 cores, **uma por canto**, luz já pintada (sem normais) |
| textura na VRAM | | 2.720 bytes (10 retângulos, 6 paletas, tudo em 4 bits) |
| um quadro-chave | 381 x 3 bytes | 305 x 3 = 915 bytes cru, ou **628 bytes como está no disco** (sem perda) |

Conjunto do primeiro teste (parado 11, correr 9, agachar 3 + 1, engatinhar 9 + 2, derrapada 5, cai de cara 10,
giro leve 10 x 248 vértices): **50 chaves do Crash + 10 do giro** = 45,8 KB + 7,4 KB em 3 bytes por vértice, ou
31,4 KB + 5,2 KB no formato comprimido do disco.
