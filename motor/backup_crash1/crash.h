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

#endif /* _CRASH_H_ */
