/*
 * Metal Gear Bandicoot: o corpo do Crash desenhado no lugar do Snake.
 *
 * O Snake continua existindo (controle, colisao, motion, armas), mas o modelo dele recebe DG_FLAG_NODRAW:
 * o motor calcula as matrizes e nao desenha. Este ator desenha o Crash (modelo por vertice do Crash 1,
 * dados em crash_data.c) usando a matriz da raiz do Snake, num DG_PRIM com FREEPACKS: o motor deixa a
 * matriz de camera pronta no GTE e chama o nosso callback para montar os triangulos.
 *
 * A animacao do Crash e escolhida pela acao atual do Snake (body->action, indice no snake.oar). Os quadros
 * e o jeito de tocar cada animacao seguem o script do proprio Crash (WillC.gooc), lido pelo Claude 2.
 *
 * Projeto de mrxploud (ByteMirage); codigo do Claude 1. Formatos do Crash: c1 (wurlyfox).
 */
#include "crash.h"
#include "crash_data.h"

#include <sys/types.h>
#include <libgte.h>
#include <libgpu.h>
#include <libspu.h>
#include "mgstype.h"
#include "libgv/libgv.h"
#include "libdg/libdg.h"
#include "game/game.h"
#include "libfs/libfs.h"
#include "bullet/blast.h"

#define N_BUCKETS   64
#define NV_PAD      ((CRASH_NV_MAX + 2) / 3 * 3)
#define NV_BUF      (((CRASH_NV_MAX + 3) & ~3) + 4)
#define MAX_PACKS   440 /* triangulos visiveis por quadro (o resto, o mais longe, fica de fora) */

typedef struct _Work
{
    GV_ACT   actor;
    OBJECT  *body;
    DG_PRIM *prim;
    int      anim;      /* CRASH_A_* */
    int      key;       /* quadro dentro da animacao */
    int      reverse;   /* tocando de tras para frente (levantar) */
    int      mirror;    /* corrida: a segunda metade do passo e espelhada em X */
    int      clock;     /* vsyncs acumulados ate o proximo quadro */
    int      blink;     /* parado: contagem ate a proxima piscada */
    int      model;     /* modelo do quadro carregado */
    int      cd_state;  /* 0 = pedir ao CD, 1 = lendo, 2 = pronto */
    void    *cd_buf;
} Work;

/* buffers do quadro atual (estaticos: o callback roda dentro do motor) */
static SVECTOR crash_verts[NV_BUF];
static long    crash_sxy[NV_PAD];
static long    crash_sz[NV_PAD];
static short   crash_head[N_BUCKETS];
static short   crash_next[CRASH_NT_MAX];

int crash_last_count;  /* triangulos desenhados no ultimo quadro (o robo de testes le) */
int crash_dbg_action;  /* acao atual do Snake (indice no snake.oar) */
int crash_dbg_action2; /* acao sobreposta (parte de cima do corpo) */
int crash_dbg_anim;    /* animacao do Crash em uso */
int crash_dbg_cintura; /* altura da raiz do Snake acima do chao */
int crash_dbg_nomem;   /* quadros sem memoria de pacotes */

static Work *crash_work;

void        Crash_Woah(void);
static void PlaySound(int ofs, int pitch, int vol);
static void CdLoadStep(Work *work);
static int   crash_in_crate; /* 1 enquanto o Snake usa uma caixa: o Crash esta dentro dela */
DG_PRIM     *crash_dbg_crate; /* (robo de testes) */

#define PACKS_SIZE (sizeof(POLY_GT3) * MAX_PACKS)

/*---------------------------------------------------------------------------*/

/* um eixo de um quadro: 4 valores de 6 bits a cada 3 bytes; vertice = base + valor * 4 (unidades do disco) */
static void DecodePlane(const unsigned char *p, int n, int base, short *out, int sign, int ofs)
{
    int i, a, b, c;

    for (i = 0; i < n; i += 4, p += 3, out += 16)
    {
        a = p[0];
        b = p[1];
        c = p[2];
        out[0]  = sign * (((base + ((a & 63) << 2)) * CRASH_ESCALA) >> 12) + ofs;
        out[4]  = sign * (((base + ((((a >> 6) | (b << 2)) & 63) << 2)) * CRASH_ESCALA) >> 12) + ofs;
        out[8]  = sign * (((base + ((((b >> 4) | (c << 4)) & 63) << 2)) * CRASH_ESCALA) >> 12) + ofs;
        out[12] = sign * (((base + ((c >> 2) << 2)) * CRASH_ESCALA) >> 12) + ofs;
    }
}

static void LoadKey(Work *work, int key)
{
    const unsigned char *k = &crash_keys[crash_key_ofs[key]];
    const CRASH_MODEL   *mdl = &crash_models[work->model];
    int                  bx, by, bz, n, plane, i;

    bx = (short)(k[0] | (k[1] << 8));
    by = (short)(k[2] | (k[3] << 8));
    bz = (short)(k[4] | (k[5] << 8));
    k += 6;
    n = mdl->nverts;
    plane = (n + 3) / 4 * 3;
    DecodePlane(k, n, bx, &crash_verts[0].vx, work->mirror ? -1 : 1, 0);
    DecodePlane(k + plane, n, by, &crash_verts[0].vy, 1, CRASH_YOFS);
    DecodePlane(k + plane * 2, n, bz, &crash_verts[0].vz, 1, 0);
    for (i = n; i < NV_PAD; i++)
    {
        crash_verts[i] = crash_verts[0];
    }
}

static void *Callback(DG_PRIM *prim, POLY_FT4 *packs, int count)
{
    Work                 *work = (Work *)prim->userdata;
    const CRASH_MODEL    *mdl = &crash_models[work->model];
    POLY_GT3             *p;
    SVECTOR              *in;
    const unsigned short *tri, *tex;
    const unsigned char  *mat;
    int i, t, a, b, c, n, nv, zmin, zmax, zsum, zr, bucket, cross, cull, flags, la, lb, lc;

    nv = mdl->nverts;

    /* os pacotes somem quando o radio pega a memoria (DG_StopMainChanlSystem); pede de novo, como os modelos */
    if (!packs)
    {
        if (!GV_AllocMemory2(GV_Clock, PACKS_SIZE, &prim->packs[GV_Clock]))
        {
            crash_dbg_nomem++;
            prim->prim_count = 0;
            return NULL;
        }
        packs = prim->packs[GV_Clock];
    }

    /* 1. transforma os vertices (o GTE ja tem a matriz de camera da raiz do Snake) */
    in = crash_verts;
    for (i = 0; i < nv; i += 3, in += 3)
    {
        gte_ldv3c(in);
        gte_rtpt();
        gte_stsxy3(&crash_sxy[i], &crash_sxy[i + 1], &crash_sxy[i + 2]);
        gte_stsz3(&crash_sz[i], &crash_sz[i + 1], &crash_sz[i + 2]);
    }
    zmin = 0xFFFF;
    zmax = 0;
    zsum = 0;
    for (i = 0; i < nv; i++)
    {
        n = crash_sz[i];
        if (n < zmin) zmin = n;
        if (n > zmax) zmax = n;
        zsum += n;
    }
    if (zmin <= 0)
    {
        prim->prim_count = 0; /* atras da camera: nao desenha */
        return packs;
    }
    zr = zmax - zmin + 1;
    cull = work->mirror ? -CRASH_CULL : CRASH_CULL;

    /* 2. descarta as costas e separa os triangulos por profundidade */
    for (i = 0; i < N_BUCKETS; i++)
    {
        crash_head[i] = -1;
    }
    tri = mdl->tris;
    for (t = 0; t < mdl->ntris; t++, tri += 3)
    {
        a = tri[0];
        b = tri[1];
        c = tri[2];
        flags = mdl->mats[mdl->tri_mat[t] * 4 + 3];
        if (!(flags & 4))
        {
            cross = ((short)crash_sxy[b] - (short)crash_sxy[a]) * ((crash_sxy[c] >> 16) - (crash_sxy[a] >> 16)) -
                    ((crash_sxy[b] >> 16) - (crash_sxy[a] >> 16)) * ((short)crash_sxy[c] - (short)crash_sxy[a]);
            if (cross * cull <= 0)
            {
                continue;
            }
        }
        bucket = ((crash_sz[a] + crash_sz[b] + crash_sz[c]) / 3 - zmin) * N_BUCKETS / zr;
        if (bucket < 0) bucket = 0;
        if (bucket >= N_BUCKETS) bucket = N_BUCKETS - 1;
        crash_next[t] = crash_head[bucket];
        crash_head[bucket] = t;
    }

    /* 3. pacotes do mais perto para o mais longe: todos vao para o mesmo degrau da OT e o ultimo inserido e
     *    desenhado primeiro, entao o mais longe fica por baixo. Pacotes com textura (olhos, boca, aneis do
     *    giro) sao POLY_GT3; o resto e POLY_G3 no mesmo espaco de 40 bytes. */
    p = (POLY_GT3 *)packs;
    n = 0;
    zsum /= nv;
    for (i = 0; i < N_BUCKETS; i++)
    {
        for (t = crash_head[i]; t >= 0 && n < MAX_PACKS; t = crash_next[t])
        {
            tri = &mdl->tris[t * 3];
            mat = &mdl->mats[mdl->tri_mat[t] * 4];
            a = tri[0];
            b = tri[1];
            c = tri[2];
            if (mat[3] & 1)
            {
                la = lb = lc = 255;
            }
            else
            {
                la = mdl->light[a];
                lb = mdl->light[b];
                lc = mdl->light[c];
            }
            if (mat[3] & 2)
            {
                tex = &mdl->mat_tex[mdl->tri_mat[t] * 5];
                setPolyGT3(p);
                if (mat[3] & 8)
                {
                    setSemiTrans(p, 1);
                }
                p->tpage = tex[0];
                p->clut = tex[1];
                *(u_short *)&p->u0 = tex[2];
                *(u_short *)&p->u1 = tex[3];
                *(u_short *)&p->u2 = tex[4];
            }
            else
            {
                setPolyG3((POLY_G3 *)p);
            }
            setRGB0(p, (mat[0] * la) >> 8, (mat[1] * la) >> 8, (mat[2] * la) >> 8);
            *(long *)&p->x0 = crash_sxy[a];
            if (mat[3] & 2)
            {
                setRGB1(p, (mat[0] * lb) >> 8, (mat[1] * lb) >> 8, (mat[2] * lb) >> 8);
                setRGB2(p, (mat[0] * lc) >> 8, (mat[1] * lc) >> 8, (mat[2] * lc) >> 8);
                *(long *)&p->x1 = crash_sxy[b];
                *(long *)&p->x2 = crash_sxy[c];
            }
            else
            {
                POLY_G3 *g = (POLY_G3 *)p;
                setRGB1(g, (mat[0] * lb) >> 8, (mat[1] * lb) >> 8, (mat[2] * lb) >> 8);
                setRGB2(g, (mat[0] * lc) >> 8, (mat[1] * lc) >> 8, (mat[2] * lc) >> 8);
                *(long *)&g->x1 = crash_sxy[b];
                *(long *)&g->x2 = crash_sxy[c];
            }
            *(u_short *)p = zsum; /* profundidade para o DG_SortChanl (o byte de tamanho fica intacto) */
            p++;
            n++;
        }
    }
    prim->prim_count = n;
    crash_last_count = n;
    return p;
}

/*---------------------------------------------------------------------------*/

/* acao do Snake (indice no snake.oar, medido no robo de testes) -> animacao do Crash */
static int AnimForAction(int action)
{
    switch (action)
    {
    case 10: case 11: case 12: case 75: case 82: case 92: case 97: case 104: /* andar e correr */
        return CRASH_A_CORRER;
    case 15: case 16: case 21: case 84:                                      /* agachar, levantar */
    case 31: case 129:                                                       /* agachado na parede */
        return CRASH_A_AGACHAR;
    case 19: case 20: case 22: case 23: case 24:                             /* deitar, rastejar, nadar */
        return CRASH_A_ACHATAR;
    case 35: case 36: case 37: case 38: case 39: case 136:                   /* socos e chute: o giro */
    case 40: case 41: case 88: case 89:                                      /* bater na parede */
        return CRASH_A_GIRO;
    case 61: case 62: case 63: case 64: case 65: case 66: case 67: case 68:  /* dano (o Crash 1 so sabe morrer) */
    case 69: case 70: case 71: case 72: case 83: case 123: case 130: case 131:
    case -1:                                                                 /* morto (fim de jogo) */
        return CRASH_A_MORRER;
    }
    return CRASH_A_PARADO;
}

static void SetAnim(Work *work, int anim, int reverse)
{
    if (anim == CRASH_A_MORRER && work->anim != CRASH_A_MORRER)
    {
        Crash_Woah(); /* o Crash morre gritando, como no jogo dele */
    }
    else if (anim == CRASH_A_GIRO && work->anim != CRASH_A_GIRO)
    {
        PlaySound(CRASH_SOM_GIRO_OFS, 0x400, 0x1800);
    }
    work->anim = anim;
    work->reverse = reverse;
    work->key = reverse ? crash_anims[anim].nkeys - 1 : 0;
    work->mirror = 0;
    work->clock = 0;
}

static void Animate(Work *work)
{
    const CRASH_ANIM *an;
    int               want, action, last;

    action = work->body->action;
    want = AnimForAction(action);

    if (want != work->anim && !(work->anim == CRASH_A_FIM_GIRO && want == CRASH_A_PARADO))
    {
        if (work->anim == CRASH_A_GIRO && want != CRASH_A_GIRO)
        {
            SetAnim(work, CRASH_A_FIM_GIRO, 0); /* sair do giro com o fim do giro */
        }
        else if (work->anim != CRASH_A_FIM_GIRO || work->key == crash_anims[CRASH_A_FIM_GIRO].nkeys - 1)
        {
            SetAnim(work, want, action == 84); /* 84 = levantar: o agachar de tras para frente */
        }
    }
    else if (work->anim == CRASH_A_FIM_GIRO && work->key == crash_anims[CRASH_A_FIM_GIRO].nkeys - 1)
    {
        SetAnim(work, want, 0);
    }

    an = &crash_anims[work->anim];
    last = an->nkeys - 1;

    /* o Crash anda a 30 quadros por segundo: um quadro a cada 2 vsyncs */
    work->clock += GV_PassageTime;
    while (work->clock >= 2)
    {
        work->clock -= 2;
        if (work->anim == CRASH_A_PARADO)
        {
            /* descanso = quadro 11 (key 0); piscar = 12, 11, 12, 11, a cada ~4 s */
            if (--work->blink <= 0)
            {
                work->blink = 100 + (GV_Time & 63);
            }
            work->key = (work->blink == 6 || work->blink == 5 || work->blink == 2 || work->blink == 1) ? 1 : 0;
        }
        else if (work->reverse)
        {
            if (work->key > 0) work->key--;
        }
        else if (work->key < last)
        {
            work->key++;
        }
        else if (an->loop)
        {
            work->key = 0;
            if (work->anim == CRASH_A_CORRER)
            {
                work->mirror ^= 1; /* a outra perna */
            }
        }
    }

    work->model = an->model;
    LoadKey(work, an->first + work->key);
    crash_dbg_anim = work->anim;
}

static void Act(Work *work)
{
    DG_OBJS *objs = work->body->objs;

    /* o Crash aparece quando o Snake "apareceria" (primeira pessoa e duto o escondem); dentro da caixa, some */
    if ((objs->flag & DG_FLAG_INVISIBLE) || crash_in_crate)
    {
        DG_InvisiblePrim(work->prim);
    }
    else
    {
        DG_VisiblePrim(work->prim);
    }
    /* a matriz da raiz do Snake fica na cintura (chao + 1100 em pe, 496 agachado, 136 deitado); o Crash tem os
     * pes em y = 0, entao a origem vai para a altura do chao debaixo dele (achado do Claude 2 depois que o
     * ByteMirage viu o Crash flutuando) */
    work->prim->world = objs->world;
    if (GM_PlayerControl)
    {
        work->prim->world.t[1] = GM_PlayerControl->levels[0];
        crash_dbg_cintura = GM_PlayerControl->mov.vy - GM_PlayerControl->levels[0];
    }
    crash_dbg_action = work->body->action;
    crash_dbg_action2 = work->body->action2;
    objs->flag |= DG_FLAG_NODRAW;
    DG_GroupPrim(work->prim, objs->group_id);
    Animate(work);
    if (work->cd_state != 2)
    {
        CdLoadStep(work);
    }
}

void Crash_FreePackets(void)
{
    DG_PRIM *prim;
    int      i;

    if (!crash_work || !(prim = crash_work->prim))
    {
        return;
    }
    for (i = 0; i < 2; i++)
    {
        if (prim->packs[i])
        {
            GV_FreeMemory2(i, &prim->packs[i]);
            prim->packs[i] = NULL;
        }
    }
    prim->prim_count = 0;
}

static void Die(Work *work)
{
    DG_PRIM *prim = work->prim;

    if (prim)
    {
        Crash_FreePackets();
        DG_DequeuePrim(prim);
        DG_FreePrim(prim);
    }
    if (work->cd_buf)
    {
        if (work->cd_state == 1)
        {
            CDBIOS_ForceStop();
        }
        GV_Free(work->cd_buf);
    }
    crash_work = NULL;
}

/*---------------------------------------------------------------------------*/
/* Sons do Crash: o ADPCM vai para um buraco livre da memoria de som e toca na voz 23, que o driver do MGS
 * nao usa (ele mexe nas vozes 0 a 22). Tom 0x400 = 11025 Hz; a voz do Crash sorteia de 0x39A a 0x466. */

#define CRASH_VOZ SPU_VOICECH(23)

extern void AN_SetMarkTextures(u_short b_mark, u_short q_mark);

static int crash_cd_ready; /* texturas e sons ja estao na VRAM/SPU */

static void PlaySound(int ofs, int pitch, int vol)
{
    SpuVoiceAttr attr;

    SpuSetKey(SPU_OFF, CRASH_VOZ);
    attr.mask = SPU_VOICE_VOLL | SPU_VOICE_VOLR | SPU_VOICE_PITCH | SPU_VOICE_WDSA |
                SPU_VOICE_ADSR_AMODE | SPU_VOICE_ADSR_SMODE | SPU_VOICE_ADSR_RMODE |
                SPU_VOICE_ADSR_AR | SPU_VOICE_ADSR_DR | SPU_VOICE_ADSR_SR | SPU_VOICE_ADSR_RR |
                SPU_VOICE_ADSR_SL;
    attr.voice = CRASH_VOZ;
    attr.volume.left = vol;
    attr.volume.right = vol;
    attr.pitch = pitch;
    attr.addr = CRASH_SPU_ADDR + ofs;
    attr.a_mode = SPU_VOICE_LINEARIncN;
    attr.s_mode = SPU_VOICE_LINEARIncN;
    attr.r_mode = SPU_VOICE_LINEARDecN;
    attr.ar = 0;
    attr.dr = 0;
    attr.sr = 0;
    attr.rr = 0;
    attr.sl = 0xF;
    SpuSetVoiceAttr(&attr);
    SpuSetKey(SPU_ON, CRASH_VOZ);
}

int crash_dbg_woah; /* quantas vezes o "Woah!" tocou (robo de testes) */

void Crash_Woah(void)
{
    if (!crash_cd_ready)
    {
        return;
    }
    PlaySound(CRASH_SOM_WOAH_OFS, 0x39A + GV_RandU(0xCD), 0x3000);
    crash_dbg_woah++;
}

/* Texturas, paletas e sons ficam no fim do BRF.DAT (o briefing nao e usado no modo dev): lidos uma vez por
 * fase para um buffer temporario, mandados para a VRAM e a SPU, e o buffer volta para a memoria. Assim
 * esses 19 KB nao ocupam a RAM do executavel. Sem travar: espera o leitor de CD ficar livre. */
static void CdLoadStep(Work *work)
{
    RECT           rect, pal;
    unsigned char *buf;

    switch (work->cd_state)
    {
    case 0:
        if (CDBIOS_TaskState() != CDBIOS_STATE_IDLE)
        {
            return;
        }
        work->cd_buf = GV_Malloc(CRASH_CD_BYTES);
        if (!work->cd_buf)
        {
            return;
        }
        FS_LoadFileRequest(FS_FILE_BRF, CRASH_CD_SETOR, CRASH_CD_BYTES, work->cd_buf);
        work->cd_state = 1;
        return;

    case 1:
        if (FS_LoadFileSync() > 0)
        {
            return;
        }
        buf = work->cd_buf;

        setRECT(&rect, CRASH_ATLAS_X, CRASH_ATLAS_Y, CRASH_ATLAS_W, CRASH_ATLAS_H);
        LoadImage(&rect, (u_long *)(buf + CRASH_CD_ATLAS));
        setRECT(&rect, CRASH_CLUT_X, CRASH_CLUT_Y, 16, CRASH_NCLUTS + 1);
        LoadImage(&rect, (u_long *)(buf + CRASH_CD_CLUTS));
        DrawSync(0);

        /* o "!" e o "?" dos guardas: "WOAH!" e "WOAH?" */
        setRECT(&pal, CRASH_CLUT_X, CRASH_MARCA_CLUT_Y, 16, 1);
        setRECT(&rect, CRASH_WOAH_B_X, CRASH_WOAH_B_Y, CRASH_WOAH_B_W, CRASH_WOAH_B_H);
        DG_SetTexture(GV_StrCode("woah_b"), 0, 0, &rect, &pal, 16);
        setRECT(&rect, CRASH_WOAH_Q_X, CRASH_WOAH_Q_Y, CRASH_WOAH_Q_W, CRASH_WOAH_Q_H);
        DG_SetTexture(GV_StrCode("woah_q"), 0, 0, &rect, &pal, 16);
        AN_SetMarkTextures(GV_StrCode("woah_b"), GV_StrCode("woah_q"));

        SpuSetTransferStartAddr(CRASH_SPU_ADDR);
        SpuWrite(buf + CRASH_CD_SONS, CRASH_SONS_BYTES);
        SpuIsTransferCompleted(SPU_TRANSFER_WAIT);

        GV_Free(work->cd_buf);
        work->cd_buf = NULL;
        work->cd_state = 2;
        crash_cd_ready = 1;
        return;
    }
}

static int GetResources(Work *work, OBJECT *body)
{
    DG_PRIM *prim;

    crash_work = work;
    /* 1 pacote de enfeite: os buffers de verdade vem da memoria de pacotes, como os modelos do motor */
    prim = DG_MakePrim(DG_PRIM_FREEPACKS | DG_PRIM_POLY_GT3, 1, 0, crash_verts, NULL);
    work->prim = prim;
    if (!prim)
    {
        return -1;
    }
    /* os pacotes sao pedidos no primeiro quadro desenhado (Callback) */
    prim->packs[0] = NULL;
    prim->packs[1] = NULL;
    prim->prim_count = 0;
    prim->n_prims = 0;
    prim->callback = Callback;
    prim->userdata = work;
    prim->root = NULL; /* a matriz e copiada a cada quadro no Act, com a origem no chao */
    prim->world = body->objs->world;
    DG_QueuePrim(prim);
    DG_GroupPrim(prim, GM_CurrentMap);

    work->body = body;
    work->blink = 60;
    SetAnim(work, CRASH_A_PARADO, 0);
    work->model = crash_anims[CRASH_A_PARADO].model;
    LoadKey(work, crash_anims[CRASH_A_PARADO].first);
    work->cd_state = 0;
    crash_cd_ready = 0;
    body->objs->flag |= DG_FLAG_NODRAW;
    return 0;
}

/*---------------------------------------------------------------------------*/
/* A caixa do Crash no lugar da caixa de papelao (ideia de yuvi3000, no Reddit): madeira, "?" e TNT */

typedef struct _CrateWork
{
    GV_ACT   actor;
    DG_OBJS *box;      /* o objeto da caixa de papelao (calcula, nao desenha); NULL depois de solta */
    DG_PRIM *prim;
    int      which;
    int      worn;     /* 1 = vestida pelo Snake (segue ele, no chao); 0 = solta (chutada pelo guarda) */
    int      countdown;/* TNT chutada: quadros ate explodir (0 = nao conta) */
    SVECTOR  verts[9]; /* 8 cantos + 1 de enchimento (o GTE transforma de 3 em 3) */
} CrateWork;

#define CAIXA_TNT     2
#define CAIXA_TNT_3   3  /* faces da contagem: 3, 2, 1 */
#define TNT_QUADROS   90 /* 3 segundos, como no Crash */

extern BLAST_DATA blast_data_8009F4B8[8];

/* A caixa e convexa: basta descartar as costas, sem ordenar. (O DG_PRIM_ONESIDE do MGS so funciona com
 * quadrilateros: com triangulos ele repete o 2o vertice no lugar do 3o.) */
static void *CrateCallback(DG_PRIM *prim, POLY_FT4 *packs, int count)
{
    CrateWork            *work = (CrateWork *)prim->userdata;
    POLY_GT3             *p = (POLY_GT3 *)packs;
    const unsigned char  *tri = &crash_caixa_tris[work->which * 10 * 3];
    const unsigned short *tex = &crash_caixa_tex[work->which * 10 * 5];
    const unsigned char  *luz = &crash_caixa_luz[work->which * 10];
    long                  sxy[9], sz[9];
    int                   i, t, a, b, c, n, l, cross;

    for (i = 0; i < 9; i += 3)
    {
        gte_ldv3c(&work->verts[i]);
        gte_rtpt();
        gte_stsxy3(&sxy[i], &sxy[i + 1], &sxy[i + 2]);
        gte_stsz3(&sz[i], &sz[i + 1], &sz[i + 2]);
    }
    n = 0;
    for (t = 0; t < 10; t++, tri += 3, tex += 5)
    {
        a = tri[0];
        b = tri[1];
        c = tri[2];
        if (sz[a] <= 0 || sz[b] <= 0 || sz[c] <= 0)
        {
            continue;
        }
        cross = ((short)sxy[b] - (short)sxy[a]) * ((sxy[c] >> 16) - (sxy[a] >> 16)) -
                ((sxy[b] >> 16) - (sxy[a] >> 16)) * ((short)sxy[c] - (short)sxy[a]);
        if (cross * CRASH_CULL <= 0)
        {
            continue;
        }
        setPolyGT3(p);
        l = (128 * luz[t]) >> 8;
        setRGB0(p, l, l, l);
        setRGB1(p, l, l, l);
        setRGB2(p, l, l, l);
        p->tpage = tex[0];
        p->clut = tex[1];
        *(u_short *)&p->u0 = tex[2];
        *(u_short *)&p->u1 = tex[3];
        *(u_short *)&p->u2 = tex[4];
        *(long *)&p->x0 = sxy[a];
        *(long *)&p->x1 = sxy[b];
        *(long *)&p->x2 = sxy[c];
        *(u_short *)p = (sz[a] + sz[b] + sz[c]) / 3;
        p++;
        n++;
    }
    prim->prim_count = n;
    return p;
}

static void CrateAct(CrateWork *work)
{
    int falta;

    if (work->box)
    {
        if (work->box->flag & DG_FLAG_INVISIBLE)
        {
            DG_InvisiblePrim(work->prim);
        }
        else
        {
            DG_VisiblePrim(work->prim);
        }
        work->box->flag |= DG_FLAG_NODRAW;
        if (!work->worn)
        {
            /* a caixa chutada pelo guarda: segue o objeto do chute, mas deslizando no chao */
            work->prim->world = work->box->world;
            if (GM_PlayerControl)
            {
                work->prim->world.t[1] = GM_PlayerControl->levels[0];
            }
        }
    }
    else
    {
        DG_VisiblePrim(work->prim); /* solta no chao, contando */
    }

    if (work->countdown > 0)
    {
        /* TNT: 3, 2, 1 com o bipe do Crash a cada segundo, e bum */
        falta = work->countdown;
        work->which = CAIXA_TNT_3 + (TNT_QUADROS - falta) / 30;
        if (falta == TNT_QUADROS || falta == 60 || falta == 30)
        {
            PlaySound(CRASH_SOM_BIPE_OFS, 0x400, 0x2C00);
        }
        work->countdown -= GV_PassageTime / 2 ? GV_PassageTime / 2 : 1;
        if (work->countdown <= 0)
        {
            NewBlast(&work->prim->world, &blast_data_8009F4B8[5]);
            GV_DestroyActor(&work->actor);
        }
        return;
    }

    if (work->worn && GM_PlayerBody)
    {
        DG_GroupPrim(work->prim, GM_PlayerBody->objs->group_id);
        work->prim->world = GM_PlayerBody->objs->world;
        if (GM_PlayerControl)
        {
            work->prim->world.t[1] = GM_PlayerControl->levels[0]; /* a caixa fica no chao */
        }
    }
}

static void CrateDie(CrateWork *work)
{
    if (work->prim)
    {
        DG_DequeuePrim(work->prim);
        DG_FreePrim(work->prim);
    }
    if (work->worn)
    {
        crash_in_crate = 0;
    }
    crash_dbg_crate = NULL;
}

static CrateWork *MakeCrate(DG_OBJS *box, int which, int worn);

void *NewCrashCrate(DG_OBJS *box, int which)
{
    CrateWork *work = MakeCrate(box, which, 1);

    if (work)
    {
        crash_in_crate = 1;
    }
    return (void *)work;
}

/* a caixa que voa quando o guarda chuta: segue o objeto do chute; se for TNT, comeca a contar */
void *Crash_CrateFly(DG_OBJS *box, int which)
{
    CrateWork *work = MakeCrate(box, which, 0);

    if (work && which == CAIXA_TNT)
    {
        work->countdown = TNT_QUADROS;
    }
    return (void *)work;
}

/* o chute acabou: a TNT fica no chao contando; as outras somem junto */
void Crash_CrateRelease(void *crate)
{
    CrateWork *work = (CrateWork *)crate;

    if (!work)
    {
        return;
    }
    if (work->countdown > 0)
    {
        work->box = NULL;
    }
    else
    {
        GV_DestroyActor(&work->actor);
    }
}

static CrateWork *MakeCrate(DG_OBJS *box, int which, int worn)
{
    CrateWork   *work;
    DG_PRIM     *prim;
    const short *v;
    int          i;

    if (which < 0 || which >= CRASH_NCAIXAS || !GM_PlayerBody)
    {
        return NULL;
    }
    work = GV_NewActor(GV_ACTOR_AFTER, sizeof(CrateWork));
    if (!work)
    {
        return NULL;
    }
    GV_SetNamedActor(&work->actor, CrateAct, CrateDie, "crash_crate");
    work->box = box;
    work->which = which;
    work->worn = worn;
    for (i = 0; i < 8; i++)
    {
        v = &crash_caixa_verts[(which * 8 + i) * 4];
        work->verts[i].vx = v[0];
        work->verts[i].vy = v[1];
        work->verts[i].vz = v[2];
    }
    work->verts[8] = work->verts[0];

    /* os pacotes (10 x 2) vem junto com o DG_PRIM, da memoria normal: o radio nao mexe neles */
    prim = DG_MakePrim(DG_PRIM_FREEPACKS | DG_PRIM_POLY_GT3, 10, 0, work->verts, NULL);
    work->prim = prim;
    if (!prim)
    {
        GV_DestroyActor(&work->actor);
        return NULL;
    }
    prim->n_prims = 0;
    prim->prim_count = 0;
    prim->callback = CrateCallback;
    prim->userdata = work;
    prim->root = NULL;
    prim->world = worn ? GM_PlayerBody->objs->world : box->world;
    if (worn && GM_PlayerControl)
    {
        prim->world.t[1] = GM_PlayerControl->levels[0];
    }
    DG_QueuePrim(prim);
    DG_GroupPrim(prim, GM_CurrentMap);
    box->flag |= DG_FLAG_NODRAW;
    crash_dbg_crate = prim;
    return work;
}

void *NewCrashBody(OBJECT *body)
{
    Work *work = GV_NewActor(GV_ACTOR_AFTER, sizeof(Work));

    if (work)
    {
        GV_SetNamedActor(&work->actor, Act, Die, "crash.c");
        if (GetResources(work, body) < 0)
        {
            GV_DestroyActor(&work->actor);
            return NULL;
        }
    }
    return (void *)work;
}
