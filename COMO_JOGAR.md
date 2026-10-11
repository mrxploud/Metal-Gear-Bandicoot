# Como jogar o Metal Gear Bandicoot

Há oito discos de teste. O mais novo é o **teste 8**: o teste 7 + **a bazuca de Wumpa** (segure **A** no teclado,
quadrado no PS1, e solte para atirar). Os testes 1 a 4 têm o Crash do Crash 1.

```
motor\.venv\Scripts\python.exe -I motor\jogar.py --disco motor\out\teste8\mgb.cue
```

Sem o `--disco`, abre o teste 1 (só as animações). A janela tem som e entra sozinha no **Loading Dock** (leva
uns segundos, com a tela acelerada). Não precisa de BIOS de PS1: o emulador (PCSX ReARMed) tem uma embutida.

Para escolher a fase você mesmo: `--menu` (cima/baixo + bolinha). Só o Loading Dock tem o Crash funcionando.

## Controles

| Teclado | Controle (Xbox) | No PS1 | No jogo |
|---|---|---|---|
| setas | direcional / analógico | direcional | andar e correr |
| Z | A | X | agachar; com direção, deitar e rastejar (o Crash **engatinha**); correndo + Z, ele **derrapa** (e derruba quem estiver na frente; segure o Z para terminar agachado) |
| X | B | bolinha | **o giro do Crash** (derruba os guardas em volta) |
| A | X | quadrado | arma |
| S | Y | triângulo | primeira pessoa |
| Q / W | LB / RB | L1 / R1 | L1 tira/põe o último item |
| E / R | LT / RT | L2 / R2 | menu de itens (segure E e ande com as setas) / menu de armas |
| Enter | Start | Start | pausa |
| Backspace | Back | Select | rádio (Campbell: 140.85) |
| F5 / F7 | | | salvar / carregar estado |
| **F12** | | | **foto: vai direto para `diario/img/`** (para o vídeo) |
| Esc | | | sair |

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

- Tela de título, Game Over "CRASH? CRAAASH!"; a Wumpa ainda não quebra caixa.
- Só o Loading Dock.

## Se der problema

Anote o que estava fazendo e, se puder, aperte **F12** antes (a foto ajuda muito). Bugs engraçados vão para o
vídeo: `diario/BUGS.md`.
