# Como jogar o Metal Gear Bandicoot

**Dois cliques no `JOGAR.bat`** (na pasta principal) ou, no terminal:

```
motor\.venv\Scripts\python.exe -I motor\jogar.py
```

O comando é sempre o mesmo: ele abre sozinho **o teste mais novo** (hoje o **teste 10**, em `motor\out\teste10`), com
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
