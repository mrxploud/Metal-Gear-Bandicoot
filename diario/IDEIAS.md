# Ideias

| Ideia | De quem | Status |
|---|---|---|
| Crash se esconde na caixa dele (madeira) em vez da caixa de papelão | **yuvi3000** (Reddit, 2018) | F3 |
| Jogar com o Crash no MGS | ByteMirage | o projeto |
| Guarda chuta a caixa (o jogo já tem `boxkeri.c`) e ela é TNT: 3, 2, 1, bum | C1 | F3/F4 |
| Caixa "?" que solta Wumpa quando o guarda chuta | C1 | F5 |
| Soco vira o giro do Crash, derrubando todo mundo em volta | C1 | F4 |
| Ração vira Wumpa | C1 | F5 |
| Morte com o "Whoa!" do Crash; Game Over "CRASH? CRAAASH!" | C1 | F4/F5 |
| Aku Aku como item (colete ou camuflagem) | C1 | F5 |
| Rastejar com a animação de morte "achatado" (o Crash 1 não sabe rastejar) | C1 | F2 |
| Tela de título com o nome do desenho: "METAL GEAR BANDICOOT - WUMPA FRUIT EATER" | desenho de u/Max_Comix | F5 |
| Cada jeito de morrer do MGS escolhe a morte do Crash que combina: granada/Claymore → `WILLY_TNT` (sobram os olhos e os sapatos); piso elétrico → `WILLY_SHOCK`; tiro → o anjinho (`WILLY_KILLED`); fogo → `WILLY_FIRE` | C2 (as animações existem no script do Crash, `WillC.gooc`) | F4 |
| Agachar do Snake usa `WILLY_DUCK`: o Crash 1 TEM animação de abaixar, 14 quadros | C2 | F2 |
| No vídeo: dentro dos arquivos do jogo o Crash se chama **"Willy"** (Willy the Wombat, o nome de desenvolvimento); todas as animações dele são `WILLY_*` | C2, lido no `goocdump` do ManDude | vídeo |
| **O "!" do guarda vira "Woah!"** (a marca de alerta e o som) | usuário apagado do Reddit (2018), 37 votos | F4, prioridade |
| Guardas dizendo "Woah! Whose footprints are these?!", "Woah! What was that noise?", "WOAH! THERE HE IS" | **ZXE102R** (Reddit) | F4/F5: legenda/voz |
| Guardas viram os assistentes de laboratório do Cortex (mesmo desenhista do Crash, em cima do esqueleto do guarda) | usuário apagado do Reddit | F5, ambicioso |
| A caixa de ferro com **"!"** do Crash (`BOX_ACTION1`) existe e saiu do disco. O "!" do alerta do MGS e o "!" da caixa do Crash são o mesmo símbolo: dá para o alerta do guarda ser a caixa "!" aparecendo em cima da cabeça dele | C2 (vendo as prévias) | F4/F5 |
| O "Woah!" do Crash nunca sai igual: o jogo sorteia o tom entre 3.6 e 4.4 a cada vez. Copiar isso no alerta dos guardas (ideia dos comentários do Reddit) | C2, lido no `goolstdlib.gooc` do ManDude | F4 |
| No vídeo: até o Crash 1 sofria com memória. O script dele confere se há espaço e carrega do CD as animações da morte só na hora de morrer | C2, `WillC.gooc` linhas 1448 a 1500 | vídeo |
| No vídeo: para achar o "Woah!" sem ter ouvidos, passamos os sons pelo Whisper. No "Woah!" ele ouviu "Wow"; no som do pulo, "Thanks for watching!"; no Aku Aku, "What have I got?" | C2, `crash_assets/out/snd/whisper.json` | vídeo |
| No vídeo: o nome interno do assistente de laboratório é LABASS, e o do Crash é Willy | C2 | vídeo |
| O assistente de laboratório mede 1523 quando o Crash mede 1000: já sai da altura de um guarda | C2 | F5 |
| No vídeo: a corrida do Crash é só meio passo. A Naughty Dog guardou uma perna e espelhou a outra para economizar memória. 30 anos depois, o mesmo truque salva a memória do Crash dentro do MGS | C2, `WillC.gooc` (`playanim_nm` / `playanim_m`) | vídeo, F2 |
| No vídeo: "compressão errada" como piada visual: com diferença de 4 bits pura o Crash corre de pernas fechadas, porque os pés não conseguem acompanhar | C2, `diario/img/20261011_0105_...` coluna D | vídeo |
| No rádio, o rosto do Snake vira o rosto do Crash | C1 (vendo a chamada do Campbell) | F5 |
| Game Over: "CRASH? CRASH!? CRAAAASH!" (texto) e o "Whoa!" na morte | C1 | F4/F5 |
| A Wumpa sobe de tom a cada fruta seguida (no Crash: tom 4.0 + 0,2 por fruta contada). Se a ração virar Wumpa, comer várias seguidas pode fazer o mesmo "plim plim plim" subindo | C2, `FruiC.gooc` `Fruit_Goto_Hud` | F5 |
| Caixa de arma vira a caixa do Aku Aku: o Crash não usa arma, então pega máscara. Cada máscara absorve um golpe; a 2ª é dourada; a 3ª vai para o rosto dele e dá invencibilidade (regra do Crash 1, `DoctC.gooc`) | ByteMirage (a ideia); C2 (a regra, lida no script) | F5 |
| No vídeo: o modelo do Crash tem 2 vértices que não pertencem a triângulo nenhum. Um deles é o ponto do rosto onde a máscara do Aku Aku se encaixa quando ele fica invencível | C2, `DoctC.gooc` `getvert(vvec, collider, 0.0)` | vídeo |
| No vídeo: "1 metro" no script do Crash é exatamente o lado de uma caixa (400 unidades). O Crash mede 1,91 m | C2 | vídeo |
| A caixa "?" chutada solta Wumpa (ou Aku Aku) | C1 | depois do Crash 3 |
| Bazuca de Wumpa do Crash 3 no lugar das armas do MGS | C2 | levar ao ByteMirage |
| **A dança da vitória do Crash** saiu do disco do Warped inteira (93 quadros-chave, 3 partes). Tocar quando a fase termina, ou quando o último guarda cai | C2 (achada nas prévias: `C3_DANCA_1/2/3`) | levar ao ByteMirage |
| Morte por explosão (a TNT chutada já explode): **somem o Crash e ficam só os olhos e os tênis caindo** (`C3_MORTE_OLHOS_E_TENIS`, 5 KB) | C2 | teste 5 ou 6 |
| GAME OVER com o **anjinho**: "CRASH? CRAAASH!" enquanto ele sobe de asas e auréola (`C3_MORTE_ANJO`) | C2 + a ideia do Game Over do C1 | levar ao ByteMirage |
| Morte "só as pernas": a calça e os tênis saem andando sozinhos (`C3_SO_AS_PERNAS_ANDANDO`, 93 vértices) | C2 | piada rara, sorteada |
| Parado há muito tempo, o Crash coça a cabeça e depois **brinca de ioiô** (o Snake fuma; o Crash joga ioiô) | C2 (`C3_COCA_A_CABECA`, `C3_IOIO`) | se couber, lido do CD |
| O Crash tem **64 caras** (cada triângulo do rosto escolhe 1 de 64 texturas). Usar a de susto quando o guarda grita "WOAH!" e a de olho fechado para piscar | C2, `out_c3/previews/caras.png` | depois do teste 5 |
| O jogo começa dentro d'água no Dock, e o Warped tem o **Crash de mergulhador** (cilindro e pé de pato, modelo `CS1eG`). Nadar no MGS podia ser ele | C2 | levar ao ByteMirage |
| Na beira da passarela do Dock, o Crash se equilibra rodando os braços (`C3_BEIRADA`) antes de cair na água | C2 | depois |
| No vídeo: no terceiro jogo, dois anos depois, o Crash **ainda se chama Willy** nos arquivos (`WillC`), e o giro ainda é "Willy Blow" | C2 | vídeo |
| No vídeo: o Crash 3 guarda só **metade** dos quadros da animação (15 por segundo) e inventa os outros fazendo a média; e cada quadro vem em "diferenças de poucos bits" em relação ao vértice vizinho. É por isso que ele tem MENOS vértices que o Crash 1 e ocupa menos | C2, formato lido no CrashEdit (CBHacks) | vídeo |
| No vídeo: a "desculpa" do ByteMirage: como o Crash 1 não engatinha, trocamos de jogo no meio do projeto. Antes disso existiu um "andar agachado" improvisado com as pernas da corrida coladas num corpo abaixado (`crash_assets/improvisos/`) | ByteMirage (a decisão), C2 (os improvisos) | vídeo |
| Correção: a "bazuca de Wumpa" da linha de cima ainda não foi achada no disco (o modelo que eu achei que era são as pernas) | C2 | procurar |
| **Bazuca de Wumpa: achada.** Com a arma do MGS equipada, o Crash vira os dois modelos do Warped (tronco com a bazuca no ombro + pernas). A bala da SOCOM vira uma Wumpa (o C1 já disse que trocar o desenho da bala é barato) | C2 (modelos `Cgt0G` + `Cgb0G`), C1 (a bala) | levar ao ByteMirage |
| No vídeo: "o Crash cortado ao meio". Primeiro apareceram só as pernas andando (achamos que era uma morte); depois o tronco com a bazuca, guardado no script das frutas | C2 | vídeo |
| No vídeo: a caixa do Crash 1 não tem a parte de trás. Em 1996 ninguém ia ver; em 2026, dentro do Metal Gear, a câmera deu a volta e o ByteMirage viu | ByteMirage (achou jogando), C2 (mediu) | vídeo |
| No vídeo: a lição que o C2 anotou duas vezes ("nome não é prova, prévia é") ganhou um terceiro degrau: **prévia também não é prova, medida é**. O engatinhar parecia um laço na folha de contato | C2 | vídeo |
| Caixa do Aku Aku no lugar das caixas de item, e a 3ª máscara dá invencibilidade com "toque da morte" (encostar no guarda derruba) | **ByteMirage** (pedido do teste 5) | teste 6 |
