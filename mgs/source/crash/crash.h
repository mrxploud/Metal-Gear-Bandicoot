#ifndef _CRASH_H_
#define _CRASH_H_

#include "game/game.h"

/* Metal Gear Bandicoot: desenha o Crash no lugar do corpo do Snake */
void *NewCrashBody(OBJECT *body);

/* caixa do Crash no lugar da caixa de papelao: which = 0 (madeira), 1 ("?"), 2 (TNT) */
void *NewCrashCrate(DG_OBJS *box, int which);

/* a caixa chutada pelo guarda (boxkeri.c); a TNT conta 3, 2, 1 e explode */
void *Crash_CrateFly(DG_OBJS *box, int which);
void  Crash_CrateRelease(void *crate);

/* a derrapada (correr + R1): o sna_init.c poe aqui os quadros que faltam a cada quadro do estado de derrapar */
extern int crash_slide;

/* o pulo (X) e o pulo duplo (X no ar): o estado de pular do sna_init.c escreve crash_pulo (1 ou 2) a cada quadro,
 * e crash_no_ar (pes acima do chao) depois de mover o Snake */
extern int crash_pulo;
extern int crash_no_ar;

/* Aku Aku: a racao vira a caixa dele (item.c); pegar = mais uma mascara, a 3a = invencivel com o toque da morte */
void *Crash_ItemCrate(DG_OBJS *box, int dy);
void  Crash_AkuGet(void);
int   Crash_AkuAbsorve(void); /* golpe no Snake: 1 = a mascara absorveu */
extern int crash_aku;         /* mascaras (0..2) */
extern int crash_aku_inv;     /* quadros de invencibilidade que faltam */

/* subir nas coisas: o control.c pergunta se o topo de algum obstaculo vira chao para este CONTROL (o Crash ou o
 * Crash 2); devolve a altura do chao de mentira ou CRASH_SEM_TOPO. pes = altura dos pes, chao = o chao do HZD */
#define CRASH_SEM_TOPO (-32000)
int   Crash_ChaoExtra(CONTROL *ctrl, int pes, int chao);
extern int crash_pulo_no_ar;  /* do impulso ate tocar o chao (sna_init.c) */

/* TNT: o Crash dentro da caixa TNT; X = sai pulando e a caixa fica contando, bolinha = explode na hora */
void  Crash_SaiDaCaixa(int tnt, MATRIX *onde);
void  Crash_TntExplode(MATRIX *onde);

/* jogador 2 (o Crash 2, controle 2) e a tela dividida */
void  Crash2_Fase(void);                 /* o corpo do Crash 1 nasceu numa fase: o Crash 2 volta junto */
int   Crash_TelaDividida(void);          /* 1 = a tela esta dividida neste quadro */
void  Crash_TelaChanl(DG_CHANL *cp, int which); /* chanl.c: o ambiente de desenho da metade deste quadro */
void  Crash_TelaCopia(u_long *ot_fim, void *env2, int which); /* chanl.c: copia a outra metade (fim do quadro) */
void  Crash_TelaCamera(int antes);       /* frame.c: a camera do Crash 2 nos quadros dele (antes/depois de ordenar) */
extern CONTROL *crash2_control;

/* watcher.c, em volta de EnemyActionMain: o guarda (WatcherWork) procura o Crash 2 se ele estiver mais a vista */
void  Crash_GuardaMira(void *guarda);
void  Crash_GuardaVolta(void);

/* wt_area.c, a cada quadro: a caixa da agua da fase (bound[0] e bound[1]); o Crash 2 dentro dela boia */
void  Crash_Agua(SVECTOR *bound);

#endif /* _CRASH_H_ */
