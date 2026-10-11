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

#endif /* _CRASH_H_ */
