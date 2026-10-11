# Estudo: quanto dá para encolher as animações do Crash

Pedido do C1 (MGB #11): no PS1 sobram uns 26 KB + 65 KB, e a prioridade 1 em 3 bytes por vértice dá ~87 KB.
Gerado por `estudo_compressao.py`, lendo só a entrega (`out/cru/`). Nada aqui muda a entrega.

**Unidade: passo.** 1 passo = 1 unidade do byte de posição do disco = 6.135 unidades do contrato = 0.61% da altura do Crash.
Na foto da F1 o Crash tem uns 45 pixels de altura na tela do MGS, então **1 passo é menos de um terço de pixel**, e um erro de 3 passos é 1 pixel. Num close em que ele ocupe 150 pixels, 1 passo vira 1 pixel.

## 0. Antes de comprimir: o que o jogo do Crash realmente toca

Lido no script dele (`repos/goocdump/Crash 1/NTSC-J/WillC.gooc`). Isto economiza mais que qualquer compressão:

- **`WILLY_WALK` é só MEIO passo.** O jogo toca os quadros 0 a 9 normais e depois os mesmos 0 a 9 **espelhados** (`playanim_nm` e depois `playanim_m`, que inverte a escala em X). O Crash é simétrico, então a perna esquerda é a direita no espelho. Para o C1: correr = 0..9 com X normal, 0..9 com X negado (e o sentido dos triângulos invertido junto). **Não dá para interpolar do quadro 9 para o 0**: são malhas espelhadas.
- **`WILLY_STANCE1` não é um laço de 13 quadros.** A pose de descanso é o **quadro 11**, parado. De vez em quando ele pisca: 12, 11, 12, 11 (0,1 s cada). Os quadros 0 a 10 são ele olhando em volta e virando para o outro lado (o script espelha o X antes), com o quadro 5 parado por 1 s. O parado básico são **2 quadros**.
- **`WILLY_DUCK`**: 0 a 7 descendo, 8 parado por 1 s, e 9 a 13 em vaivém enquanto continua abaixado.
- **`WILLY_FLAT`**: 0 a 3 caindo, **4 parado por 1,3 s (achatado no chão)**, 5 a 12 descolando como papel. Para rastejar basta 0 a 4.
- **`WILLY_BLOW`**: laço de 0 a 7. É o único que volta do último quadro para o primeiro.

## 1. O que há para comprimir

| Animação | Quadros | Vértices | 3 B/vért. | Maior salto entre quadros | Diferenças que cabem em 4 bits (-7 a +7) |
|---|---|---|---|---|---|
| `WILLY_STANCE1` | 13 | 381 | 14.859 | 16 passos | 96.3% |
| `WILLY_WALK` | 10 | 381 | 11.430 | 45 passos | 77.7% |
| `WILLY_DUCK` | 14 | 381 | 16.002 | 38 passos | 93.8% |
| `WILLY_FLAT` | 13 | 381 | 14.859 | 106 passos | 69.2% |
| `WILLY_BLOW` | 8 | 470 | 11.280 | 6 passos | 100.0% |
| `WILLY_SPIN_END` | 6 | 381 | 6.858 | 73 passos | 50.0% |
| `WILLY_KILLED_1` | 6 | 381 | 6.858 | 40 passos | 63.1% |
| `WILLY_KILLED_2` | 20 | 381 | 22.860 | 47 passos | 79.8% |
| `WILLY_KILLED_3` | 10 | 381 | 11.430 | 45 passos | 85.0% |
| `WILLY_KILLED_4` | 8 | 381 | 9.144 | 33 passos | 93.4% |

Prioridade 1 em 3 bytes por vértice: **82.146 bytes**.

## 2. Cada jeito de encolher: bytes e pior erro (em passos)

Cada célula é `bytes / pior erro`. Erro 0 = idêntico ao disco.

| Animação | A. metade dos quadros, repetindo | B. metade + interpolação | C. um terço + interpolação | D. diferença 4 bits pura | E. diferença 4 bits com escala | F. B + E juntos | G. 4 bits + escape (sem perda) | H. zlib nas diferenças (sem perda) |
|---|---|---|---|---|---|---|---|---|
| `WILLY_STANCE1` | 8.001 / 16 | 8.001 / 6 | 5.715 / 9 | 8.007 / 14 | 8.019 / 1 | 4.581 / 7 | 8.502 / 0 | 6.187 / 0 |
| `WILLY_WALK` | 5.715 / 45 | 6.858 / 17 | 4.572 / 33 | 6.291 / 91 | 6.300 / 4 | 4.008 / 19 | 8.583 / 0 | 7.186 / 0 |
| `WILLY_DUCK` | 8.001 / 38 | 9.144 / 14 | 6.858 / 22 | 8.579 / 74 | 8.592 / 4 | 5.154 / 15 | 9.491 / 0 | 6.315 / 0 |
| `WILLY_FLAT` | 8.001 / 106 | 8.001 / 33 | 5.715 / 50 | 8.007 / 161 | 8.019 / 8 | 4.581 / 39 | 12.231 / 0 | 7.829 / 0 |
| `WILLY_BLOW` | 5.640 / 5 | 5.640 / 14 | 4.230 / 14 | 6.348 / 0 | 6.352 / 0 | 3.528 / 15 | 6.345 / 0 | 4.455 / 0 |
| `WILLY_SPIN_END` | 3.429 / 73 | 4.572 / 37 | 3.429 / 57 | 4.003 / 114 | 4.008 / 8 | 2.862 / 40 | 6.861 / 0 | 5.275 / 0 |
| `WILLY_KILLED_1` | 3.429 / 34 | 4.572 / 12 | 3.429 / 23 | 4.003 / 76 | 4.008 / 4 | 2.862 / 17 | 6.110 / 0 | 4.948 / 0 |
| `WILLY_KILLED_2` | 11.430 / 47 | 12.573 / 14 | 9.144 / 25 | 12.011 / 86 | 12.030 / 4 | 6.873 / 17 | 16.385 / 0 | 14.012 / 0 |
| `WILLY_KILLED_3` | 5.715 / 45 | 6.858 / 15 | 4.572 / 26 | 6.291 / 79 | 6.300 / 4 | 4.008 / 17 | 7.828 / 0 | 6.641 / 0 |
| `WILLY_KILLED_4` | 4.572 / 27 | 5.715 / 8 | 4.572 / 14 | 5.147 / 58 | 5.154 / 2 | 3.435 / 10 | 5.672 / 0 | 3.983 / 0 |
| **prioridade 1, total** | **42.216** / 106 | **46.788** / 37 | **33.948** / 57 | **45.238** / 161 | **45.298** / 8 | **27.576** / 40 | **58.123** / 0 | **42.195** / 0 |

Como ler o erro de A: é o quanto o quadro repetido difere do quadro certo, ou seja, o tranco de rodar a 15 quadros por segundo; não é deformação. Em B e C o erro é deformação de verdade no quadro interpolado.
Em D (4 bits sem escala) o erro é atraso: o vértice que anda mais de 7 passos num quadro fica para trás.

## 3. Menos bits por coordenada (em vez de mexer no tempo)

| Bits por coordenada | Bytes por vértice por quadro | Pior erro | Prioridade 1 |
|---|---|---|---|
| 8 | 3.00 | 0 passos | 82.146 |
| 7 | 2.62 | 1 passos | 71.880 |
| 6 | 2.25 | 2 passos | 61.613 |
| 5 | 1.88 | 4 passos | 51.344 |

Com 5 bits cada coordenada tem 32 posições: 5 + 5 + 5 = 15 bits, **2 bytes por vértice**, sem decodificar nada (é um `>>` e um `&`).

## 4. Poses-base (todas as animações do `WillG` como média + r poses; cada quadro vira r números)

| r | Bytes (média e poses em int8, mais os números por quadro) | Pior erro | Erro médio |
|---|---|---|---|
| 4 | 6.211 | 109 passos | 8.25 |
| 8 | 11.279 | 57 passos | 4.08 |
| 12 | 16.347 | 45 passos | 2.06 |
| 16 | 21.415 | 32 passos | 1.07 |
| 24 | 31.551 | 8 passos | 0.48 |

(62 quadros do `WillG`; o `BLOW` fica de fora porque é outro modelo.) Custa caro no PS1: r multiplicações por coordenada por quadro. Só vale se o resto não couber.

## 5. O conjunto enxuto (seção 0) com cada jeito de guardar

| Animação | Quadros usados | 3 B/vért. | 6 bits por coordenada (erro até 2) | 5+5+5 bits = 2 B/vért. (erro até 4) | E. diferença 4 bits com escala | **6 bits + diferença 4 bits com escape** |
|---|---|---|---|---|---|---|
| `WILLY_STANCE1` | 11 e 12 (2) | 2.286 | 1.715 / 2 | 1.524 / 4 | 1.716 / 1 | **1.433** / 2 |
| `WILLY_WALK` | 0 a 9 (10) | 11.430 | 8.573 / 2 | 7.620 / 4 | 6.300 / 4 | **6.059** / 2 |
| `WILLY_DUCK` | 0 a 8 (9) | 10.287 | 7.716 / 2 | 6.858 / 4 | 5.727 / 4 | **5.449** / 2 |
| `WILLY_FLAT` | 0 a 4 (5) | 5.715 | 4.287 / 2 | 3.810 / 4 | 3.435 / 8 | **4.217** / 2 |
| `WILLY_BLOW` | 0 a 7 (8) | 11.280 | 8.460 / 2 | 7.520 / 4 | 6.352 / 0 | **5.996** / 2 |
| `WILLY_SPIN_END` | 0 a 5 (6) | 6.858 | 5.144 / 2 | 4.572 / 4 | 4.008 / 8 | **4.116** / 2 |
| `WILLY_KILLED_1` | 0 a 5 (6) | 6.858 | 5.144 / 2 | 4.572 / 4 | 4.008 / 4 | **3.746** / 2 |
| **total** | | **54.714** / 0 | **41.039** / 2 | **36.476** / 4 | **31.546** / 8 | **31.016** / 2 |

Somar a isto, uma vez só: os triângulos e materiais dos dois modelos e as normais do 1º quadro (que o C1 já usa).

