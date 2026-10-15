# Como jogar o Metal Gear Bandicoot

**Dois cliques no `JOGAR.bat`** (na pasta principal) ou, no terminal (PowerShell), na pasta do projeto:

```powershell
.\JOGAR.bat
```

De outra pasta: `& "<pasta do projeto>\JOGAR.bat"`. Também vale `.\motor\.venv\Scripts\python.exe -I motor\jogar.py`
na pasta do projeto. No PowerShell o `.\` na frente é obrigatório: sem ele aparece "Não foi possível carregar o
módulo 'motor'" (achado do ByteMirage no teste 13).

O comando é sempre o mesmo: ele abre sozinho **o teste mais novo** (hoje o **teste 15**, em `motor\out\teste15`), com
os dois discos. Para abrir um teste antigo: `--disco motor\out\teste9\mgb.cue`. Não precisa de BIOS de PS1: o
emulador (PCSX ReARMed) tem uma embutida.

O jogo abre como o Metal Gear Solid de verdade: abertura, **tela de título, Novo Jogo** (ou carregar do cartão de
memória), escolha da dificuldade e a cena de abertura até o Loading Dock. Atalhos dos testes: `--dock` entra direto
no Loading Dock (como era até o teste 9) e `--menu` para no seletor de fases do modo de desenvolvimento.

- **Salvar**: como no MGS, pelo rádio da Mei Ling (140.96). O cartão de memória fica em `motor\saves\pcsx-card1.mcd`
  e vale para todos os testes, então dá para salvar num teste e continuar no seguinte.
- **Trocar de disco**: quando o jogo pede o disco 2, o programa troca sozinho (o título da janela avisa); é só
  apertar **Start (Enter)**, como pede a tela. **F9** troca à mão.
- **F5 / F7** salvam e carregam o estado na hora (um por teste).

## O que mudou no teste 15: o Crash 2 respeita o cenário

Consertos dos achados do ByteMirage no teste 14 ("ele atravessa a parede", "deixei o jogador 2 dentro da parede", "ele
também não pega caixa"):

- **Paredes**: o Crash 2 usava a regra de parede dos guardas, e não a do Snake. Atravessava paredes que seguram o
  Crash 1 (até a borda da fase) e batia em paredes invisíveis na beira da água que o Crash 1 passa. Agora usa a mesma
  regra do Crash 1. Medido no Loading Dock, empurrando o Crash 2 contra as paredes que mudaram: o teste 14 atravessava
  10 de 10; o 15, nenhuma de 11.
- **Água**: no tanque do começo do Dock o Snake nada e mergulha (o fundo fica a 4 m). O Crash 2 afundava até o fundo e
  ficava andando por baixo do cais, com a câmera dele dentro da estrutura. Agora ele **boia**, com a água no peito; sai
  pulando (X) numa beirada ou com **triângulo** (volta para perto do Crash 1).
- **Itens**: o Crash 2 pega os itens do chão (as caixas do Aku Aku, munição, as caixas A, B e C...). Vão para o mesmo
  inventário do Crash 1, e a máscara do Aku Aku vai para o Crash 1: os dois são um time.

## O que mudou no teste 14: tela inteira com os dois juntos, sem coleira e a 30 quadros

- **A tela só se divide quando precisa.** Com os dois Crashes perto, é a tela inteira, com a câmera do Crash 1. Quando
  o Crash 2 está saindo da tela (chega na beirada, uns 4 a 5 m), ela se divide como antes; quando ele volta para perto (uns
  2,5 m), junta de novo. A barra azul do Crash 2 fica no alto, à esquerda, embaixo da vida do Crash 1.
- **Sem coleira.** Até o teste 13 o Crash 2 era puxado de volta a 12 m do Crash 1. Agora ele anda pela área inteira
  em que o Crash 1 está (no Heliporto chegou a 15 m, até a encosta de neve), e as paredes seguram. Ele só volta se
  cair do mapa, se o Crash 1 passar para outra sala com ele a mais de 6 m, ou com **triângulo** no controle 2. Portas,
  elevadores e a troca de área continuam sendo do Crash 1: o Metal Gear só carrega as salas em volta dele.
- **30 quadros por segundo com os dois.** O `jogar.py` agora acelera o processador emulado (o relógio da CPU do
  PlayStation) de 57% para 100%. Medido no Loading Dock: com os dois Crashes o jogo ficava a 20 quadros por segundo,
  e cada metade da tela dividida mudava só 10 vezes por segundo; agora é 30 juntos e 30 divididos (15 por metade).
  `--cpu 57` volta ao padrão do emulador.
- **60 quadros não dá** sem mexer no jogo inteiro: o Metal Gear espera 2 vsyncs por quadro (30 por segundo) e move
  tudo um passo fixo por quadro. Forçando 60, o jogo inteiro corre o dobro (o Crash, os guardas, os créditos da
  abertura). Gravado em `clips/coop_cpu300_60qps_tudo_rapido` (estúdio, mgb-expansao).

## O que mudou no teste 13: os guardas veem o Crash 2

- **Os guardas enxergam o Crash 2** (no teste 12 só viam o Crash 1): o guarda procura quem está na frente dele; se
  os dois estão, o mais perto. Ao ver o Crash 2 ele grita **"WOAH!"**, toca o alerta e atira nele como faria com o
  Crash 1. Enquanto está vendo um dos dois, não troca. O alerta ainda chama os outros guardas para onde o
  Crash 1 está.
- **O Crash 2 segura bala**: um tiro que ia no Crash 1 para no Crash 2 se ele estiver na frente (e o contrário).
  Morto, o corpo dele não leva nem segura tiro.
- Limite: como os outros truques dos guardas, só vale nas 59 áreas compiladas da fonte (o Loading Dock, o Heliporto,
  o Tank Hangar e as celas, por exemplo). Nas 33 áreas que usam o código original, os guardas só veem o Crash 1.

## O que mudou no teste 12: a expansão (dois jogadores, subir nas coisas, a TNT)

- **Jogador 2, com a tela dividida.** Quem pega o **controle 2** aperta **Start** e o **Crash 2** (azul, para ninguém
  se perder) aparece ao lado do Crash; a tela se divide: em cima o Crash, embaixo o Crash 2, cada um com a sua câmera.
  O Crash 2 corre, pula (com pulo duplo), gira (derruba guarda) e sobe nas coisas; leva tiro e explosão, tem a barra
  de vida azul no canto da metade dele, e quando morre volta ao lado do Crash depois de uns 4 s. **Triângulo** traz ele de
  volta para perto do Crash (se ficar preso atrás de uma porta); **Select** tira ele do jogo. Ele volta sozinho em cada
  fase. Limites: os guardas só enxergam o Crash 1; o Crash 2 não abre portas nem aciona eventos; na sala do Psycho
  Mantis o controle 2 é do Psycho Mantis.
  - No teclado o Crash 2 é **I J K L** (direções), **U** (pular), **O** (girar), **F2** (entrar) e **F3** (sair). Com
    dois controles ligados, o segundo é sempre o do Crash 2.
  - A gambiarra: o PlayStation não aguenta desenhar a fase duas vezes por quadro, então cada quadro desenha uma
    metade só e a outra é copiada da tela anterior. Cada metade anda a 15 quadros por segundo.
- **Consertado: o Crash pulava mas não subia em nada** (achado do ByteMirage). Eram três coisas: o Snake invisível
  testava as paredes na altura do chão mesmo com o Crash no ar; encostando numa caixa o Snake "colava" de costas
  nela (como no MGS) e o X não pulava; e o MGS não tem chão em cima das caixas (o Snake nunca sobe nelas). Agora o
  topo de caixas, contêineres e grades vira chão para os dois Crashes. Exemplo: o contêiner do lado leste do
  Heliporto (precisa do pulo duplo).
- **A TNT fere todo mundo** (pedido do ByteMirage): a explosão é maior que a granada e pega o Crash, o Crash 2 e os
  guardas; uma TNT explode outra que esteja contando perto. **Vestido na caixa C (TNT)**: **X** pula para fora e a
  caixa fica no chão contando 3, 2, 1; **bolinha** (o giro) explode na hora, com o Crash dentro. O giro numa TNT
  contando no chão também explode na hora.
- **As mortes vêm do CD**: para o código do Crash 2 caber nos 2 MB, as duas mortes do Crash saíram da memória fixa e
  são lidas quando alguém morre (como o próprio Crash 1 fazia). No primeiro instante da morte o Crash fica no susto.
- **F11 grava o bug**: os últimos 20 segundos de jogo (vídeo com som), uma foto e o estado vão para
  `diario\clipes\bug_<data>_<teste>_<fase>.*`. Se travar, aperte F11 antes de fechar.
- **Consertado: o `jogar.py` podia fechar sozinho** quando o som acumulava (PC lento, janela presa).
- **Ainda não achado: o travamento subindo a escada para os dutos.** A escadaria do Heliporto, o duto de cima e a fase
  do duto (com o rádio do Miller) não travaram nos testes. Se acontecer de novo: F11 e diga onde foi.

## O que mudou no teste 11: o som do jogo e o elevador de novo

- **Consertado: o som do jogo sumia e o elevador travava de novo** (achado do ByteMirage no teste 10). Os sons do
  Crash tocavam na voz 23 do chip de som, e a voz 23 é o **relógio** do som do Metal Gear: ela toca silêncio em laço e
  cada volta faz o som do jogo andar. O primeiro som do Crash (o giro, o "Woah!", a bazuca) parava esse relógio: a
  música e os efeitos sumiam, e a próxima cena com fala (a do elevador) ficava esperando a voz para sempre. Agora o
  Crash tem a voz dele (a 20) e o Metal Gear fica com 7 vozes de efeito em vez de 8.
- **Consertado: o `jogar.py` não tocava nos alto-falantes.** Ele abria o primeiro dispositivo de som da lista do
  Windows (no seu PC, a saída digital S/PDIF). Agora toca no dispositivo padrão, o mesmo dos outros programas.
- As cenas continuam pulando com **Start (Enter)**, como no MGS.

## O que mudou no teste 10: o jogo inteiro

- **Consertado: o jogo travava depois do elevador do Loading Dock** (achado do ByteMirage no teste 9). O teste 9
  tinha embutido só o código do Loading Dock; a cena do elevador e o Heliporto chamavam personagens que não existiam.
  Agora o código de cada área vem do disco, como no MGS original, ajustado ao executável da fusão.
- **O Crash em todas as áreas, nos dois discos**: as 92 áreas do jogo carregam com ele (Heliporto, Tank Hangar,
  celas, Arsenal, Cânion, a torre de comunicação, a neve, o REX...). Mais o disco 2.
- **Tela de título, Novo Jogo, cartão de memória e troca de disco**, para dar para jogar do começo ao fim.
- **A chegada ao Heliporto é longa**: duas ligações de rádio e uma cena com a câmera passeando, uns 3 minutos sem
  controle. É o jogo, não travou.
- Limites deste teste:
  - Em 33 das 92 áreas o código é o original do MGS, só ajustado ao nosso executável (o projeto de descompilação
    ainda não terminou essas, entre elas Cânion, Torre de Comunicação, laboratório, Psycho Mantis, REX e Liquid). Lá
    os guardas mostram o "!" e o grito de sempre (sem o "WOAH!"), e chutar a caixa é o chute do MGS (sem a TNT
    explodindo). O Crash em si, com o giro, o pulo, a bazuca, o Aku Aku e as caixas, funciona em todas.
  - Em algumas áreas pesadas (Tank Hangar, Armazém B2) o jogo fica um pouco mais lento que o original: desenhar o
    Crash custa processamento.
  - O emulador do `jogar.py` usa a CPU interpretada. A recompilada (`--rapido`) é mais leve, mas fecha o emulador
    na cena do Heliporto.

## Controles

| Teclado | Controle (Xbox) | No PS1 | No jogo |
|---|---|---|---|
| setas | direcional / analógico | direcional | andar e correr |
| Z | A | X | **pular**; no ar, solte e aperte de novo: **pulo duplo** (a cambalhota). Segurando, o pulo vai mais alto |
| W | RB | R1 | **agachar enquanto segurar** (soltou, levanta); com direção, **engatinha**; correndo + W, **derrapa** (e derruba quem estiver na frente); derrapando + Z, **pulo longo** |
| X | B | bolinha | **o giro do Crash** (derruba os guardas em volta) |
| A | X | quadrado | arma |
| S | Y | triângulo | primeira pessoa |
| Q | LB | L1 | tira/põe o último item |
| E / R | LT / RT | L2 / R2 | menu de itens (segure E e ande com as setas) / menu de armas |
| Enter | Start | Start | pausa |
| Backspace | Back | Select | rádio (Campbell: 140.85) |
| F5 / F7 | | | salvar / carregar estado |
| **F11** | | | **bug**: grava os últimos 20 s em vídeo + foto + estado em `diario\clipes` |
| F2 / F3 | Start / Back do 2º | Start / Select do controle 2 | **Crash 2** entra / sai |
| I J K L, U, O | 2º controle | controle 2 | Crash 2: andar, pular, girar (triângulo do 2º controle: volta para perto do Crash) |
| F9 | | | trocar de disco (o programa já troca sozinho quando o jogo pede) |
| **F12** | | | **foto: vai direto para `diario/img/`** (para o vídeo) |
| Esc | | | sair |

## O que mudou no teste 9: o pulo

- **Z pula** (A no controle de Xbox, X no PS1), com o pulo do Warped: sai do chão, sobe de braços para cima e pousa
  agachando e se recompondo. **Segurando o Z ele vai mais alto** (~1,3 vez a altura dele); só tocando, um pulinho.
- **Pulo duplo**: no ar, solte o Z e aperte de novo. É o segundo impulso com **a cambalhota** do Warped.
- **Correndo + Z**: pula para a frente. **Derrapando + Z** (correr, W, e logo Z): o **pulo longo**, levando a
  velocidade da derrapada, como no Crash 3.
- No ar, as setas guiam o Crash; o **X** (bolinha) dá o **giro no ar**.
- A sombra fica no chão enquanto ele sobe, como nos jogos do Crash.
- **Agachar agora é segurando o W** (RB; R1 no PS1). Soltou, ele levanta. Antes era liga/desliga (o X do MGS), e depois
  da derrapada o Crash ficava agachado parado, dando tempo para os guardas chegarem (achado do ByteMirage).
- Limites: ele pula, mas **não sobe em cima de nada** (as paredes do MGS continuam batendo na altura do chão), e o
  pulo não tem som (não achamos o som de pulo no disco do Warped). Levantar depois de engatinhar ainda leva ~0,5 s:
  é a animação do Snake deitado.

## O que mudou no teste 8: a bazuca de Wumpa

- **Segure A** (teclado; X no controle de Xbox; quadrado no PS1): o Crash **saca a bazuca** das costas, com o pulinho
  do Warped, e fica mirando. Dá para **andar mirando** (as pernas andam e o tronco segue mirando para a frente).
- **Solte**: ele atira uma **Wumpa** (com o coice da bazuca e o som do tiro do Warped). A Wumpa voa reto, gira, e o
  guarda que ela acertar leva o golpe e cambaleia (com o "plim" da fruta). Na parede ela some.
- Funciona sem arma equipada (no Dock o Snake não tem arma), parado ou correndo; agachado, engatinhando e dentro da
  caixa, não.
- A primeira vez que você aperta, ele demora um instante: a bazuca vem do CD (ela não cabe na memória fixa do
  PS1). Depois de 10 s guardada, a memória volta para o jogo, e a próxima vez lê de novo.
- Como no Warped, o Crash é **cortado ao meio** quando usa a bazuca: o tronco com a bazuca e as pernas são dois
  modelos diferentes (achado do Claude 2).

## O que mudou no teste 7: o Aku Aku

- **As 3 rações do Loading Dock viraram caixas do Aku Aku** (as do Warped). É só encostar para pegar, como no Crash.
- **1ª caixa**: a máscara aparece e flutua ao lado do Crash. Ela **absorve um tiro** (a vida não cai; o Crash pisca).
- **2ª caixa**: a máscara fica dourada e absorve **dois** tiros.
- **3ª caixa**: a máscara vai para o rosto do Crash e ele fica **invencível por 20 segundos**. Nesse tempo, **guarda
  que encostar nele cai morto** (o toque da morte). Quando acaba, a máscara volta a ser a dourada.
- Onde estão (no lugar das rações): duas do lado direito (leste) do Dock, uma lá em cima perto dos guardas e outra
  mais perto do começo; a terceira fica do lado esquerdo (oeste), no nível de baixo. O radar não mostra.
- A derrapada (correr + Z) também derruba guarda.
- Nota para o README: a cara do Aku Aku na caixa é uma textura de 256 cores no disco; aqui ela foi reduzida para 16
  cores (redução nossa, escolhendo as cores para não perder a pena azul). O resto é o dado do disco.

## O que mudou no teste 6

- **Engatinhar**: não treme mais. O engatinhar do Warped é meio passo (uma mão na frente); agora ele toca a outra
  metade espelhada, como o jogo dele faz. Parado de quatro, ele fica na pose em que parou.
- **Correr + Z**: a derrapada do Crash 3 de verdade. Ele desliza um pedaço para a frente freando, derruba guarda que
  estiver no caminho e se levanta (ou fica agachado, se você continuar segurando o Z). Na água continua o mergulho
  do MGS.
- **A caixa**: tinha um lado faltando (a caixa do Crash 1 não tem a face de trás: a câmera do Crash 1 nunca vê as
  costas de uma caixa). Agora fecha dos quatro lados.

## O que tem desde o teste 5

- **O Crash do Warped** no lugar do Snake, com as animações do próprio Crash 3 (o jogo guarda metade dos quadros e
  faz a média, e o nosso faz igual): parado (respira e olha em volta), correndo, agachado, **engatinhando**,
  **derrapando** (correr + Z), o giro, o susto quando leva tiro e a morte.
- **As caixas do Crash** (ideia do yuvi3000): segure **E** (menu de itens), ande até **C.BOX A, B ou C** e solte.
  A = caixa de madeira, B = caixa "?", C = caixa de TNT. O Crash se esconde dentro dela.
- **"WOAH!"** (ideia de um comentário do post): quando um guarda vê o Crash, aparece **"WOAH!"** em cima da
  cabeça dele, no lugar do "!", e ele grita o "Whoa!" do Crash. O "?" virou **"WOAH?"**.
- **O giro derruba quem estiver em volta** (não só na frente): o guarda sai voando. Tem o som do giro do Crash.
- **A morte** tem o "Whoa!" do Crash antes do GAME OVER.
- **A TNT**: vista a caixa C, fique **parado** no caminho de um guarda e espere. Ele chuta a caixa, ela desliza
  contando 3, 2, 1 e explode (fique longe!). Se ele vir a caixa andando, ele atira em vez de chutar.
- Rádio, primeira pessoa, pausa e menus funcionam.

## Onde estão os guardas

Os guardas ficam na parte de cima (norte) do Loading Dock, depois da área da água onde o jogo começa. O radar no
canto mostra a visão deles.

## O que ainda NÃO tem

- Tela de título própria e o Game Over "CRASH? CRAAASH!" (o título e o Game Over são os do MGS); a Wumpa ainda não
  quebra caixa.
- O "WOAH!", o grito e a TNT nas 33 áreas que usam o código original do MGS (ver o teste 10).

## Se der problema

Anote o que estava fazendo e, se puder, aperte **F12** antes (a foto ajuda muito). Bugs engraçados vão para o
vídeo: `diario/BUGS.md`.
