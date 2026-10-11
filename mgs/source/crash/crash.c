/*
 * Metal Gear Bandicoot: o corpo do Crash desenhado no lugar do Snake.
 *
 * O Snake continua existindo (controle, colisao, motion, armas), mas o modelo dele recebe DG_FLAG_NODRAW:
 * o motor calcula as matrizes e nao desenha. Este ator desenha o Crash (modelo por vertice do Crash 3 Warped,
 * dados em crash_data.c) usando a matriz da raiz do Snake, num DG_PRIM com FREEPACKS: o motor deixa a
 * matriz de camera pronta no GTE e chama o nosso callback para montar os triangulos.
 *
 * A animacao do Crash e escolhida pela acao atual do Snake (body->action, indice no snake.oar). Os quadros
 * e o jeito de tocar cada animacao seguem o script do proprio Crash (WillC.gooc), lido pelo Claude 2.
 *
 * Projeto de mrxploud (ByteMirage); codigo do Claude 1. Formatos do Crash: c1/c2 (wurlyfox) e CrashEdit.
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
#include "libhzd/libhzd.h"
#include "bullet/blast.h"

#define N_BUCKETS   64
#define NV_PAD      ((CRASH_NV_MAX + 2) / 3 * 3)
#define MAX_PACKS   360 /* triangulos visiveis por quadro (o pior caso medido do Crash 3 foi 330) */
#define DOBRA(c)    ((c) >= 128 ? 255 : (c) * 2)
#define DERRAPADA_BAIXO 4 /* quadro da derrapada em que o Crash desliza (chave 2, a mais baixa) */

typedef struct _Work
{
    GV_ACT   actor;
    OBJECT  *body;
    DG_PRIM *prim;
    int      anim;      /* CRASH_A_* */
    int      frame;     /* quadro tocado dentro da animacao (0 .. toca-1) */
    int      reverse;   /* tocando de tras para frente (levantar) */
    int      mirror;    /* laco de meio ciclo (engatinhar): a segunda metade e espelhada em X */
    int      clock;     /* vsyncs acumulados ate o proximo quadro */
    int      model;     /* modelo do quadro carregado */
    int      cd_state;  /* 0/2 = pedir ao CD (textura; sons), 1/3 = lendo, 4 = pronto */
    void    *cd_buf;
    SVECTOR  rosto;     /* o ponto do rosto no quadro atual (espaco do modelo) */
    int      tem_rosto;
    DG_PRIM *aku;       /* a mascara do Aku Aku */
    int      aku_tipo;  /* animacao carregada na mascara (CRASH_A_AKU ou _OURO), -1 = nenhuma */
    int      aku_on;    /* a mascara ja estava na tela no quadro anterior */
    VECTOR   aku_pos;   /* posicao da mascara no mundo (x 16, para seguir devagar) */
    int      baz;       /* bazuca: 0 = so no CD, 1 = lendo, 2 = na memoria dinamica */
    void    *baz_buf;
    int      baz_on;    /* na mao (quadrado segurado, ou logo depois do tiro) */
    int      baz_fase;  /* 0 = sacando, 1 = mirando (chave 0 do TIRO parada), 2 = atirando (o coice) */
    int      baz_anim;  /* metade de cima: SACA ou TIRO */
    int      baz_frame;
    SVECTOR  baz_cintura; /* onde o tronco se apoia: o ponto da cintura da chave atual das pernas */
    int      baz_pernas;/* metade de baixo: parado ou andando */
    int      baz_pframe;
    int      baz_clock;
    int      baz_depois;/* quadros desde o tiro */
    int      baz_ocioso;/* quadros guardada (a memoria volta depois de BAZ_OCIOSO) */
} Work;

/* buffers do quadro atual (estaticos: o callback roda dentro do motor) */
static SVECTOR       crash_verts[NV_PAD];
static long          crash_sxy[NV_PAD];
static long          crash_sz[NV_PAD];
static short         crash_head[N_BUCKETS];
static short         crash_next[CRASH_NT_MAX];
static unsigned char crash_kA[CRASH_NV_MAX * 3];
static unsigned char crash_kB[CRASH_NV_MAX * 3];
#define AKU_NV_PAD 36
#define AKU_NT     27
static SVECTOR       aku_verts[AKU_NV_PAD];

int crash_last_count;  /* triangulos desenhados no ultimo quadro (o robo de testes le) */
int crash_dbg_action;  /* acao atual do Snake (indice no snake.oar) */
int crash_dbg_action2; /* acao sobreposta (parte de cima do corpo) */
int crash_dbg_anim;    /* animacao do Crash em uso */
int crash_dbg_cintura; /* altura da raiz do Snake acima do chao */
int crash_dbg_nomem;   /* quadros sem memoria de pacotes */
int crash_dbg_frame;   /* quadro da animacao em uso (+100 quando espelhado) */
int crash_slide;       /* derrapada: quadros que faltam (o estado de derrapar do sna_init.c escreve a cada quadro) */
int crash_aku;         /* mascaras do Aku Aku (0, 1 ou 2): cada uma absorve um golpe */
int crash_aku_inv;     /* quadros de invencibilidade que faltam (a 3a mascara); o sna_init.c le */

#define AKU_INV_TEMPO 600 /* 20 s, como no Warped */

static Work *crash_work;
static int   crash_slide_resto; /* crash_slide lido neste quadro */
static int   crash_boom; /* quadros desde que uma TNT explodiu perto do Crash (morte = sobram olhos e tenis) */

void        Crash_Woah(void);
static void PlaySound(int ofs, int pitch, int vol);
static void CdLoadStep(Work *work);
static int   crash_in_crate; /* 1 enquanto o Snake usa uma caixa: o Crash esta dentro dela */
DG_PRIM     *crash_dbg_crate; /* (robo de testes) */

#define PACKS_SIZE (sizeof(POLY_GT3) * MAX_PACKS)

/* de onde vem um modelo: os do Crash ficam no executavel; os da bazuca vem do CD para a memoria dinamica */
typedef struct
{
    const CRASH_MODEL   *models;
    const CRASH_ANIM    *anims;
    const unsigned long *key_ofs;
    const unsigned long *keys;
} FONTE;

static const FONTE fonte_crash = { crash_models, crash_anims, crash_key_ofs, crash_keys };
static FONTE       fonte_baz;

/*---------------------------------------------------------------------------*/
/* Quadros-chave do Crash 3: cada vertice = vertice anterior + base fixa + diferenca de poucos bits (o numero de
 * bits e por vertice e eixo, igual em todo o modelo). A fila de bits vem em palavras de 32 bits, do bit mais
 * alto para o mais baixo. Sem perda: o mesmo byte por eixo que o Warped guarda. */
static void DecodeKey(const FONTE *f, const CRASH_MODEL *mdl, int key, unsigned char *out, short *org)
{
    const unsigned long *k = &f->keys[f->key_ofs[key] >> 2];
    const unsigned char *base = mdl->base;
    const unsigned char *bits = mdl->bits;
    unsigned long        cur, alto;
    int                  resto, b, val, falta, i, n, eixo;
    int                  acc[3];

    org[0] = (short)(k[0] & 0xFFFF);
    org[1] = (short)(k[0] >> 16);
    org[2] = (short)(k[1] & 0xFFFF);
    k += 2;
    cur = *k++;
    resto = 32;
    acc[0] = acc[1] = acc[2] = 0;
    n = mdl->nverts * 3;
    eixo = 0;
    for (i = 0; i < n; i++)
    {
        b = bits[i];
        val = 0;
        if (b)
        {
            if (b <= resto)
            {
                val = (cur >> (resto - b)) & ((1 << b) - 1);
                resto -= b;
                if (resto == 0)
                {
                    cur = *k++;
                    resto = 32;
                }
            }
            else
            {
                alto = cur & ((1 << resto) - 1);
                falta = b - resto;
                cur = *k++;
                val = (alto << falta) | (cur >> (32 - falta));
                resto = 32 - falta;
            }
            if (val & (1 << (b - 1)))
            {
                val -= 1 << b;
            }
        }
        acc[eixo] = (acc[eixo] + val + base[i]) & 255;
        out[i] = acc[eixo];
        if (++eixo == 3)
        {
            eixo = 0;
        }
    }
}

/* uma chave inteira em vertices (a mascara: modelo parado, uma chave so) */
static void LoadKey(int anim, SVECTOR *v, int pad)
{
    const CRASH_ANIM  *an = &crash_anims[anim];
    const CRASH_MODEL *mdl = &crash_models[an->model];
    unsigned char     *a = crash_kA;
    short              o[3];
    int                i;

    DecodeKey(&fonte_crash, mdl, an->first, a, o);
    for (i = 0; i < mdl->nverts; i++, a += 3)
    {
        v[i].vx = ((o[0] + a[0]) * mdl->escala[0]) >> 12;
        v[i].vy = ((o[1] + a[1]) * mdl->escala[1]) >> 12;
        v[i].vz = ((o[2] + a[2]) * mdl->escala[2]) >> 12;
    }
    for (; i < pad; i++)
    {
        v[i] = v[0];
    }
}

/* as chaves do quadro tocado: f/2 (par) ou as duas vizinhas (impar), como o Warped faz a 30 qps */
static void FrameKeys(const CRASH_ANIM *an, int frame, int *pa, int *pb)
{
    int kA, kB;

    if (an->interp)
    {
        kA = frame >> 1;
        kB = (frame & 1) ? kA + 1 : kA;
    }
    else
    {
        kA = kB = frame;
    }
    if (kA >= an->nkeys) kA = an->nkeys - 1;
    if (kB >= an->nkeys) kB = an->loop ? 0 : an->nkeys - 1;
    *pa = kA;
    *pb = kB;
}

/* o quadro tocado em vertices (media das duas chaves vizinhas), completando ate multiplo de 3 para o GTE */
static void DecodeFrame(const FONTE *f, int anim, int frame, int mirror, SVECTOR *v)
{
    const CRASH_ANIM  *an = &f->anims[anim];
    const CRASH_MODEL *mdl = &f->models[an->model];
    short              oA[3], oB[3];
    int                kA, kB, i, n, ex, ey, ez;
    SVECTOR           *v0 = v;
    unsigned char     *a = crash_kA, *b = crash_kB;

    FrameKeys(an, frame, &kA, &kB);
    ex = mirror ? -mdl->escala[0] : mdl->escala[0];
    ey = mdl->escala[1];
    ez = mdl->escala[2];
    n = mdl->nverts;
    DecodeKey(f, mdl, an->first + kA, a, oA);
    if (kB == kA)
    {
        for (i = 0; i < n; i++, v++, a += 3)
        {
            v->vx = ((oA[0] + a[0]) * ex) >> 12;
            v->vy = ((oA[1] + a[1]) * ey) >> 12;
            v->vz = ((oA[2] + a[2]) * ez) >> 12;
        }
    }
    else
    {
        DecodeKey(f, mdl, an->first + kB, b, oB);
        for (i = 0; i < n; i++, v++, a += 3, b += 3)
        {
            v->vx = ((oA[0] + a[0] + oB[0] + b[0]) * ex) >> 13;
            v->vy = ((oA[1] + a[1] + oB[1] + b[1]) * ey) >> 13;
            v->vz = ((oA[2] + a[2] + oB[2] + b[2]) * ez) >> 13;
        }
    }
    for (i = n; i < (n + 2) / 3 * 3; i++)
    {
        v0[i] = v0[0];
    }
}

static void LoadFrame(Work *work)
{
    const CRASH_ANIM *an = &crash_anims[work->anim];
    const short      *ra, *rb;
    int               kA, kB;

    work->model = an->model;
    DecodeFrame(&fonte_crash, work->anim, work->frame, work->mirror, crash_verts);

    /* o rosto (para a mascara na invencibilidade): media das duas chaves, espelhado junto */
    FrameKeys(an, work->frame, &kA, &kB);
    ra = &crash_rosto[(an->first + kA) * 3];
    rb = &crash_rosto[(an->first + kB) * 3];
    work->rosto.vx = (ra[0] + rb[0]) / 2;
    work->rosto.vy = (ra[1] + rb[1]) / 2;
    work->rosto.vz = (ra[2] + rb[2]) / 2;
    if (work->mirror)
    {
        work->rosto.vx = -work->rosto.vx;
    }
    work->tem_rosto = (ra[1] != 0);
}

/* Desenha um modelo do Warped: transforma, descarta as costas, ordena por profundidade e monta os pacotes (o GTE
 * ja tem a matriz de camera do objeto). Serve para o Crash e para a mascara do Aku Aku. */
static POLY_GT3 *DrawModel(const CRASH_MODEL *mdl, SVECTOR *verts, int cull, POLY_GT3 *packs, int max, int *count)
{
    POLY_GT3             *p;
    POLY_G3              *g;
    SVECTOR              *in;
    const unsigned short *tri, *tex;
    const unsigned char  *cor, *ca, *cb, *cc;
    int i, t, a, b, c, n, nv, zmin, zmax, zsum, zr, bucket, cross, flags, m;

    nv = mdl->nverts;
    *count = 0;

    /* 1. transforma os vertices */
    in = verts;
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
        return packs; /* atras da camera: nao desenha */
    }
    zr = zmax - zmin + 1;

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
        if (!(mdl->flags[mdl->tri_mat[t]] & 4))
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
     *    desenhado primeiro, entao o mais longe fica por baixo. A cor vem por canto (a luz do Warped ja vem
     *    pintada nela): sem textura, dobrada (como nas previas do Claude 2); com textura, ela modula. */
    p = packs;
    n = 0;
    zsum /= nv;
    cor = mdl->cores;
    for (i = 0; i < N_BUCKETS; i++)
    {
        for (t = crash_head[i]; t >= 0 && n < max; t = crash_next[t])
        {
            tri = &mdl->tris[t * 3];
            m = mdl->tri_mat[t];
            flags = mdl->flags[m];
            a = tri[0];
            b = tri[1];
            c = tri[2];
            ca = &cor[mdl->cantos[t * 3] * 3];
            cb = &cor[mdl->cantos[t * 3 + 1] * 3];
            cc = &cor[mdl->cantos[t * 3 + 2] * 3];
            if (flags & 2)
            {
                tex = &mdl->mat_tex[m * 5];
                setPolyGT3(p);
                if (flags & 8)
                {
                    setSemiTrans(p, 1);
                }
                p->tpage = tex[0];
                p->clut = tex[1];
                *(u_short *)&p->u0 = tex[2];
                *(u_short *)&p->u1 = tex[3];
                *(u_short *)&p->u2 = tex[4];
                setRGB0(p, ca[0], ca[1], ca[2]);
                setRGB1(p, cb[0], cb[1], cb[2]);
                setRGB2(p, cc[0], cc[1], cc[2]);
                *(long *)&p->x0 = crash_sxy[a];
                *(long *)&p->x1 = crash_sxy[b];
                *(long *)&p->x2 = crash_sxy[c];
            }
            else
            {
                g = (POLY_G3 *)p;
                setPolyG3(g);
                if (flags & 8)
                {
                    setSemiTrans(g, 1);
                }
                setRGB0(g, DOBRA(ca[0]), DOBRA(ca[1]), DOBRA(ca[2]));
                setRGB1(g, DOBRA(cb[0]), DOBRA(cb[1]), DOBRA(cb[2]));
                setRGB2(g, DOBRA(cc[0]), DOBRA(cc[1]), DOBRA(cc[2]));
                *(long *)&g->x0 = crash_sxy[a];
                *(long *)&g->x1 = crash_sxy[b];
                *(long *)&g->x2 = crash_sxy[c];
            }
            *(u_short *)p = zsum; /* profundidade para o DG_SortChanl (o byte de tamanho fica intacto) */
            p++;
            n++;
        }
    }
    *count = n;
    return p;
}

static void *Callback(DG_PRIM *prim, POLY_FT4 *packs, int count)
{
    Work     *work = (Work *)prim->userdata;
    POLY_GT3 *p;
    int       n;

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
    if (work->baz_on && work->baz == 2)
    {
        /* com a bazuca o Warped corta o Crash ao meio: a metade de cima (ja decodificada no Act) e as pernas */
        int n2;

        p = DrawModel(&fonte_baz.models[fonte_baz.anims[work->baz_anim].model], crash_verts, CRASH_CULL,
                      (POLY_GT3 *)packs, MAX_PACKS, &n);
        DecodeFrame(&fonte_baz, work->baz_pernas, work->baz_pframe, 0, crash_verts);
        p = DrawModel(&fonte_baz.models[fonte_baz.anims[work->baz_pernas].model], crash_verts, CRASH_CULL,
                      p, MAX_PACKS - n, &n2);
        n += n2;
    }
    else
    {
        /* espelhado (meio ciclo do engatinhar), os triangulos viram do avesso */
        p = DrawModel(&crash_models[work->model], crash_verts, work->mirror ? -CRASH_CULL : CRASH_CULL,
                      (POLY_GT3 *)packs, MAX_PACKS, &n);
    }
    prim->prim_count = n;
    crash_last_count = n;
    return p;
}

/* a mascara do Aku Aku: 27 triangulos, pacotes vindos junto com o DG_PRIM (memoria normal) */
static void *AkuCallback(DG_PRIM *prim, POLY_FT4 *packs, int count)
{
    Work     *work = (Work *)prim->userdata;
    POLY_GT3 *p;
    int       n;

    p = DrawModel(&crash_models[crash_anims[work->aku_tipo].model], aku_verts, CRASH_CULL, (POLY_GT3 *)packs,
                  AKU_NT, &n);
    prim->prim_count = n;
    return p;
}

/*---------------------------------------------------------------------------*/

/* acao do Snake (indice no snake.oar, medido no robo de testes) -> animacao do Crash (tabela v4 do Claude 2) */
static int AnimForAction(Work *work, int action)
{
    if (crash_slide > 0)
    {
        return CRASH_A_DERRAPADA; /* correr + X (estado novo do Snake, sna_init.c) */
    }
    switch (action)
    {
    case 10: case 11: case 12: case 75: case 82: case 92: case 97: case 104: /* andar e correr */
        return CRASH_A_CORRER;
    case 15: case 16: case 21: case 84:                                      /* agachar, levantar */
    case 31: case 129:                                                       /* agachado na parede */
        return CRASH_A_AGACHAR;
    case 19: case 20: case 22:                                               /* deitando, deitado */
        return CRASH_A_ENGATINHAR_PARADO;
    case 23: case 24:                                                        /* rastejar, nadar */
        return CRASH_A_ENGATINHAR;
    case 35: case 36: case 37: case 38: case 39: case 136:                   /* socos e chute: o giro */
    case 40: case 41: case 88: case 89:                                      /* bater na parede */
        return CRASH_A_GIRO;
    case 61: case 62: case 63: case 64: case 65: case 66: case 67: case 68:  /* dano: o susto do Warped */
    case 69: case 70: case 71: case 72: case 83: case 123: case 130: case 131:
        return CRASH_A_SUSTO;
    }
    return CRASH_A_PARADO;
}

static void SetAnim(Work *work, int anim, int reverse)
{
    if ((anim == CRASH_A_MORRER || anim == CRASH_A_MORRER_TNT) &&
        work->anim != CRASH_A_MORRER && work->anim != CRASH_A_MORRER_TNT)
    {
        Crash_Woah(); /* o Crash morre gritando, como no jogo dele */
    }
    else if (anim == CRASH_A_GIRO && work->anim != CRASH_A_GIRO)
    {
        PlaySound(CRASH_SOM_GIRO_OFS, 0x400, 0x1800);
    }
    work->anim = anim;
    work->reverse = reverse;
    work->mirror = 0;
    work->frame = reverse ? crash_anims[anim].toca - 1 : 0;
    work->clock = 0;
}

static void Animate(Work *work)
{
    const CRASH_ANIM *an;
    int               want, action, last, pausa;

    action = work->body->action;
    want = AnimForAction(work, action);
    crash_slide_resto = crash_slide;
    crash_slide = 0; /* vale so para este quadro: o estado de derrapar escreve de novo no proximo */
    pausa = 0;

    /* sem vida: a morte e para sempre (a acao do Snake muda durante o GAME OVER) */
    if (GM_Vitality <= 0 || action == -1)
    {
        if (work->anim == CRASH_A_MORRER || work->anim == CRASH_A_MORRER_TNT)
        {
            want = work->anim;
        }
        else
        {
            want = crash_boom > 0 ? CRASH_A_MORRER_TNT : CRASH_A_MORRER; /* TNT perto: sobram os olhos e os tenis */
        }
    }
    if (crash_boom > 0)
    {
        crash_boom--;
    }

    /* agachar termina segurando o agachado */
    if (want == CRASH_A_AGACHAR && action != 84 && work->anim == CRASH_A_AGACHADO)
    {
        want = CRASH_A_AGACHADO;
    }
    /* parou de engatinhar: fica de quatro na pose em que estava (a de agachado para de quatro e outra) */
    if (want == CRASH_A_ENGATINHAR_PARADO && work->anim == CRASH_A_ENGATINHAR)
    {
        want = CRASH_A_ENGATINHAR;
        pausa = 1;
    }
    /* a derrapada termina abaixada: dali vai direto para o agachado, ou se levanta (o agachar ao contrario) */
    if (work->anim == CRASH_A_DERRAPADA && want != CRASH_A_DERRAPADA)
    {
        if (want == CRASH_A_AGACHAR)
        {
            want = CRASH_A_AGACHADO;
        }
        else if (want == CRASH_A_PARADO)
        {
            SetAnim(work, CRASH_A_AGACHAR, 1);
        }
    }
    /* levantando (agachar ao contrario): termina de levantar antes de ficar parado */
    if (want == CRASH_A_PARADO && work->anim == CRASH_A_AGACHAR && work->reverse && work->frame > 0)
    {
        want = CRASH_A_AGACHAR;
    }
    if (want != work->anim)
    {
        SetAnim(work, want, action == 84); /* 84 = levantar: o agachar de tras para frente */
    }

    an = &crash_anims[work->anim];
    last = an->toca - 1;

    /* o Warped toca a 30 quadros por segundo: um quadro a cada 2 vsyncs */
    work->clock += GV_PassageTime;
    while (work->clock >= 2)
    {
        work->clock -= 2;
        if (pausa)
        {
            break;
        }
        if (work->reverse)
        {
            if (work->frame > 0) work->frame--;
        }
        else if (work->anim == CRASH_A_DERRAPADA && work->frame == DERRAPADA_BAIXO && crash_slide_resto > 4)
        {
            /* desliza na pose mais baixa; levanta nos ultimos quadros */
        }
        else if (work->frame < last)
        {
            work->frame++;
        }
        else if (an->loop)
        {
            work->frame = 0;
            if (an->loop == 2)
            {
                work->mirror ^= 1; /* meio ciclo: a outra mao (perna) na frente */
            }
        }
        else if (work->anim == CRASH_A_AGACHAR)
        {
            SetAnim(work, CRASH_A_AGACHADO, 0);
            an = &crash_anims[work->anim];
            last = an->toca - 1;
        }
    }

    LoadFrame(work);
    crash_dbg_anim = work->anim;
    crash_dbg_frame = work->frame + (work->mirror ? 100 : 0);
}

static void PlaySound(int ofs, int pitch, int vol);

/* A mascara do Aku Aku (regra do Warped, lida pelo Claude 2 no script DoctC): flutua ao lado do Crash, um pouco atras,
 * a ~1,3 m de altura subindo e descendo, e segue com atraso. Na invencibilidade (3a mascara) vai para o rosto. */
static void AkuAct(Work *work, int visivel)
{
    DG_PRIM *aku = work->aku;
    SVECTOR  alvo_l, alvo;
    int      tipo, rosto;

    if (!aku)
    {
        return;
    }
    if (crash_aku_inv > 0)
    {
        if (--crash_aku_inv == 0)
        {
            crash_aku = 2; /* acabou: volta a dourada, como no Warped */
            PlaySound(CRASH_SOM_AKU_PERDE_OFS, 0x400, 0x2000);
        }
    }
    if (crash_aku == 0 && crash_aku_inv == 0)
    {
        DG_InvisiblePrim(aku);
        work->aku_on = 0;
        return;
    }
    tipo = (crash_aku >= 2 || crash_aku_inv > 0) ? CRASH_A_AKU_OURO : CRASH_A_AKU;
    if (tipo != work->aku_tipo)
    {
        work->aku_tipo = tipo;
        LoadKey(tipo, aku_verts, AKU_NV_PAD);
    }

    rosto = crash_aku_inv > 0 && work->tem_rosto;
    if (rosto)
    {
        alvo_l = work->rosto;
    }
    else
    {
        alvo_l.vx = -560;
        alvo_l.vy = 760 + (rsin(GV_Time * 64) * 170 >> 12);
        alvo_l.vz = -200;
    }
    DG_SetPos(&work->prim->world);
    DG_PutVector(&alvo_l, &alvo, 1);
    if (!work->aku_on || rosto)
    {
        work->aku_pos.vx = alvo.vx << 4;
        work->aku_pos.vy = alvo.vy << 4;
        work->aku_pos.vz = alvo.vz << 4;
    }
    else
    {
        work->aku_pos.vx += ((alvo.vx << 4) - work->aku_pos.vx) / 6;
        work->aku_pos.vy += ((alvo.vy << 4) - work->aku_pos.vy) / 6;
        work->aku_pos.vz += ((alvo.vz << 4) - work->aku_pos.vz) / 6;
    }
    work->aku_on = 1;

    aku->world = work->prim->world;
    aku->world.t[0] = work->aku_pos.vx >> 4;
    aku->world.t[1] = work->aku_pos.vy >> 4;
    aku->world.t[2] = work->aku_pos.vz >> 4;
    DG_GroupPrim(aku, work->body->objs->group_id);
    /* no rosto, some quando o Crash some (primeira pessoa, caixa) e nas mortes sem rosto */
    if (visivel || (!rosto && !(work->body->objs->flag & DG_FLAG_INVISIBLE)))
    {
        DG_VisiblePrim(aku);
    }
    else
    {
        DG_InvisiblePrim(aku);
    }
}

/*---------------------------------------------------------------------------*/
/* A bazuca de Wumpa (pedido do ByteMirage; achada no Warped pelo Claude 2). Sem arma equipada, segurar o quadrado
 * saca a bazuca (o Crash cortado ao meio: tronco mirando, pernas parando ou andando com o Snake) e soltar atira uma
 * Wumpa. Os modelos nao cabem na RAM fixa: vem do CD para a memoria dinamica na primeira vez e voltam depois de
 * BAZ_OCIOSO quadros guardada. */

#define BAZ_OCIOSO   300 /* 10 s */
#define BAZ_DEPOIS   20  /* quadros com a bazuca na mao depois do tiro */
#define WUMPA_VEL    320 /* unidades por quadro */
#define WUMPA_RAIO   110
#define WUMPA_VIDA   40
#define WUMPA_DANO   64

typedef struct
{
    char          magic[4];
    unsigned short nmodels, nanims;
    unsigned long ofs_anims, ofs_key_ofs, ofs_keys, nkeys, ofs_pontos;
} BAZ_CAB;

static const short *baz_pontos; /* por chave: no tronco, o eixo do cano; nas pernas, a cintura (MGB #38) */

/* o ponto da chave do quadro tocado (media das duas chaves vizinhas, como os vertices) */
static void BazPonto(int anim, int frame, SVECTOR *out)
{
    const CRASH_ANIM *an = &fonte_baz.anims[anim];
    const short      *a, *b;
    int               kA, kB;

    FrameKeys(an, frame, &kA, &kB);
    a = &baz_pontos[(an->first + kA) * 3];
    b = &baz_pontos[(an->first + kB) * 3];
    out->vx = (a[0] + b[0]) / 2;
    out->vy = (a[1] + b[1]) / 2;
    out->vz = (a[2] + b[2]) / 2;
}

int crash_dbg_baz;   /* (robo) estado da bazuca: 0, 1, 2 (+10 na mao) */
int crash_dbg_wumpa; /* (robo) quantas Wumpas acertaram alguem */

/* o bloco do CD traz o CRASH_MODEL com deslocamentos no lugar dos ponteiros: soma o endereco do bloco */
static void BazPrepara(unsigned char *buf)
{
    BAZ_CAB     *cab = (BAZ_CAB *)buf;
    CRASH_MODEL *m = (CRASH_MODEL *)(buf + sizeof(BAZ_CAB));
    int          i;

    for (i = 0; i < cab->nmodels; i++, m++)
    {
        m->tris = (const unsigned short *)(buf + (unsigned long)m->tris);
        m->tri_mat = buf + (unsigned long)m->tri_mat;
        m->flags = buf + (unsigned long)m->flags;
        m->mat_tex = (const unsigned short *)(buf + (unsigned long)m->mat_tex);
        m->cantos = buf + (unsigned long)m->cantos;
        m->cores = buf + (unsigned long)m->cores;
        m->base = buf + (unsigned long)m->base;
        m->bits = buf + (unsigned long)m->bits;
    }
    fonte_baz.models = (const CRASH_MODEL *)(buf + sizeof(BAZ_CAB));
    fonte_baz.anims = (const CRASH_ANIM *)(buf + cab->ofs_anims);
    fonte_baz.key_ofs = (const unsigned long *)(buf + cab->ofs_key_ofs);
    fonte_baz.keys = (const unsigned long *)(buf + cab->ofs_keys);
    baz_pontos = (const short *)(buf + cab->ofs_pontos);
}

typedef struct _WumpaWork
{
    GV_ACT   actor;
    DG_PRIM *prim;
    SVECTOR  centro;
    SVECTOR  pos;
    SVECTOR  step;
    MAP     *map;
    TARGET   target;
    int      vida;
    int      quadro;   /* quadro do sprite (a Wumpa gira) */
} WumpaWork;

/* a Wumpa e um sprite virado para a camera (como no Warped) */
static void *WumpaCallback(DG_PRIM *prim, POLY_FT4 *packs, int count)
{
    WumpaWork *work = (WumpaWork *)prim->userdata;
    POLY_FT4  *p = packs;
    long       sxy, sz, h;
    int        x, y, r;

    gte_ldv0(&work->centro);
    gte_rtps();
    gte_stsxy(&sxy);
    gte_stsz(&sz);
    if (sz <= 0)
    {
        prim->prim_count = 0;
        return p;
    }
    gte_ReadGeomScreen(&h);
    r = WUMPA_RAIO * h / sz;
    if (r < 2) r = 2;
    if (r > 80) r = 80;
    x = (short)sxy;
    y = sxy >> 16;
    setPolyFT4(p);
    setRGB0(p, 128, 128, 128);
    p->tpage = CRASH_WUMPA_TPAGE;
    p->clut = CRASH_WUMPA_CLUT;
    setXY4(p, x - r, y - r, x + r, y - r, x - r, y + r, x + r, y + r);
    {
        int u = crash_wumpa_uv[work->quadro] & 255;
        int v = crash_wumpa_uv[work->quadro] >> 8;

        setUV4(p, u, v, u + 31, v, u, v + 31, u + 31, v + 31);
    }
    *(u_short *)p = sz;
    prim->prim_count = 1;
    return p + 1;
}

static void WumpaAct(WumpaWork *work)
{
    SVECTOR to, hit;
    MAP    *map = work->map;

    GM_CurrentMap = map->index;
    to.vx = work->pos.vx + work->step.vx;
    to.vy = work->pos.vy + work->step.vy;
    to.vz = work->pos.vz + work->step.vz;
    if (HZD_OnlineHazardCheck(map->hzd, &work->pos, &to, HZD_CHK_ALL, HZD_SEG_NO_PLAYER))
    {
        GV_DestroyActor(&work->actor); /* bateu na parede */
        return;
    }
    if (GM_OnlineTargetCheck(&work->pos, &to, map->index, &hit, PLAYER_SIDE))
    {
        GM_MoveTarget(&work->target, &hit);
        GM_PowerTarget(&work->target);
        PlaySound(CRASH_SOM_PLIM_OFS, 0x400, 0x3000);
        crash_dbg_wumpa++;
        GV_DestroyActor(&work->actor);
        return;
    }
    work->pos = to;
    if (++work->quadro >= CRASH_WUMPA_QUADROS)
    {
        work->quadro = 0;
    }
    work->prim->world.t[0] = to.vx;
    work->prim->world.t[1] = to.vy;
    work->prim->world.t[2] = to.vz;
    if (--work->vida <= 0)
    {
        GV_DestroyActor(&work->actor);
    }
}

static void WumpaDie(WumpaWork *work)
{
    if (work->prim)
    {
        DG_DequeuePrim(work->prim);
        DG_FreePrim(work->prim);
    }
}

/* atira uma Wumpa da boca da bazuca, para onde o Crash olha */
static void NewWumpa(Work *work)
{
    static SVECTOR frente = { 0, 0, WUMPA_VEL };
    static SVECTOR forca = { 0, 0, 100 };
    static SVECTOR tamanho = { 100, 100, 100 };
    WumpaWork     *w;
    DG_PRIM       *prim;
    SVECTOR        empurra, boca;

    if (!GM_PlayerControl)
    {
        return;
    }
    w = GV_NewActor(GV_ACTOR_AFTER, sizeof(WumpaWork));
    if (!w)
    {
        return;
    }
    GV_SetNamedActor(&w->actor, WumpaAct, WumpaDie, "crash_wumpa");
    /* o eixo do cano na mira (chave 0 do TIRO) + a cintura, um pouco a frente */
    BazPonto(CRASH_BZ_TIRO, 0, &boca);
    boca.vx += work->baz_cintura.vx;
    boca.vy += work->baz_cintura.vy;
    boca.vz += work->baz_cintura.vz + 200;
    DG_SetPos(&work->prim->world);
    DG_PutVector(&boca, &w->pos, 1);
    DG_RotVector(&frente, &w->step, 1);
    DG_RotVector(&forca, &empurra, 1);
    w->map = GM_PlayerControl->map;
    w->vida = WUMPA_VIDA;
    w->centro.vx = w->centro.vy = w->centro.vz = 0;
    GM_SetTarget(&w->target, TARGET_POWER, PLAYER_SIDE, &tamanho);
    GM_SetPowerTarget(&w->target, POWER_ONCE, 4, WUMPA_DANO, 0, &empurra);

    prim = DG_MakePrim(DG_PRIM_FREEPACKS | DG_PRIM_POLY_FT4, 1, 0, &w->centro, NULL);
    w->prim = prim;
    if (!prim)
    {
        GV_DestroyActor(&w->actor);
        return;
    }
    prim->n_prims = 0;
    prim->prim_count = 0;
    prim->callback = WumpaCallback;
    prim->userdata = w;
    prim->root = NULL;
    prim->world = DG_ZeroMatrix;
    prim->world.t[0] = w->pos.vx;
    prim->world.t[1] = w->pos.vy;
    prim->world.t[2] = w->pos.vz;
    DG_QueuePrim(prim);
    DG_GroupPrim(prim, work->body->objs->group_id);
    PlaySound(CRASH_SOM_TIRO_OFS, 0x400, 0x3000);
}

static void BazAct(Work *work, int permitido)
{
    GV_PAD *pad = &GV_PadData[0];
    int     quer = permitido && (pad->status & PAD_SQUARE);
    int     last;

    switch (work->baz)
    {
    case 0:
        /* primeira vez: le o bloco da bazuca do CD (so depois da textura e dos sons da fase) */
        if (quer && work->cd_state == 4 && CDBIOS_TaskState() == CDBIOS_STATE_IDLE)
        {
            work->baz_buf = GV_Malloc(CRASH_CD_BYTES_BAZUCA);
            if (work->baz_buf)
            {
                FS_LoadFileRequest(FS_FILE_BRF, CRASH_CD_SETOR_BAZUCA, CRASH_CD_BYTES_BAZUCA, work->baz_buf);
                work->baz = 1;
            }
        }
        break;
    case 1:
        if (FS_LoadFileSync() <= 0)
        {
            BazPrepara(work->baz_buf);
            work->baz = 2;
            work->baz_ocioso = 0;
        }
        break;
    }
    crash_dbg_baz = work->baz;
    if (work->baz != 2)
    {
        work->baz_on = 0;
        return;
    }

    if (quer && !work->baz_on)
    {
        /* saca: o tronco puxa a bazuca das costas e as pernas dao o pulinho */
        work->baz_on = 1;
        work->baz_fase = 0;
        work->baz_anim = CRASH_BZ_SACA;
        work->baz_frame = 0;
        work->baz_pernas = CRASH_BZ_PERNAS_SACA;
        work->baz_pframe = 0;
        work->baz_clock = 0;
        work->baz_depois = BAZ_DEPOIS;
    }
    if (work->baz_on)
    {
        if (!permitido)
        {
            work->baz_on = 0;
        }
        else if (pad->release & PAD_SQUARE)
        {
            /* soltou o quadrado: o coice (TIRO 0 -> 4) e a Wumpa */
            NewWumpa(work);
            work->baz_fase = 2;
            work->baz_anim = CRASH_BZ_TIRO;
            work->baz_frame = 0;
            if (work->anim != CRASH_A_CORRER)
            {
                work->baz_pernas = CRASH_BZ_PERNAS_TIRO;
                work->baz_pframe = 0;
            }
            work->baz_depois = 0;
        }
        else if (!quer && work->baz_fase == 1 && ++work->baz_depois > BAZ_DEPOIS)
        {
            work->baz_on = 0; /* guarda */
        }
    }
    if (!work->baz_on)
    {
        if (++work->baz_ocioso > BAZ_OCIOSO)
        {
            GV_Free(work->baz_buf); /* devolve a memoria; na proxima vez le de novo do CD */
            work->baz_buf = NULL;
            work->baz = 0;
        }
        return;
    }
    work->baz_ocioso = 0;
    crash_dbg_baz += 10 + work->baz_fase * 10;

    /* as pernas: andando ou paradas com o Snake (menos no pulinho de sacar e no coice parado) */
    if (work->anim == CRASH_A_CORRER)
    {
        last = CRASH_BZ_PERNAS_ANDANDO;
    }
    else if (work->baz_pernas == CRASH_BZ_PERNAS_SACA || work->baz_pernas == CRASH_BZ_PERNAS_TIRO)
    {
        last = work->baz_pernas;
    }
    else
    {
        last = CRASH_BZ_PERNAS_PARADO;
    }
    if (last != work->baz_pernas)
    {
        work->baz_pernas = last;
        work->baz_pframe = 0;
    }

    work->baz_clock += GV_PassageTime;
    while (work->baz_clock >= 2)
    {
        work->baz_clock -= 2;
        if (work->baz_fase != 1 && ++work->baz_frame >= fonte_baz.anims[work->baz_anim].toca)
        {
            /* sacou, ou o coice acabou: mira (a chave 0 do TIRO, parada) */
            work->baz_fase = 1;
            work->baz_anim = CRASH_BZ_TIRO;
            work->baz_frame = 0;
        }
        if (++work->baz_pframe >= fonte_baz.anims[work->baz_pernas].toca)
        {
            if (fonte_baz.anims[work->baz_pernas].loop)
            {
                work->baz_pframe = 0;
            }
            else
            {
                work->baz_pernas = CRASH_BZ_PERNAS_PARADO; /* o pulinho / o coice das pernas acabou */
                work->baz_pframe = 0;
            }
        }
    }

    /* a metade de cima vai para os vertices agora, em cima da cintura das pernas (a origem do tronco e a cintura,
     * achado do Claude 2: com a mesma raiz ele afundava nas pernas); as pernas sao decodificadas no desenho */
    BazPonto(work->baz_pernas, work->baz_pframe, &work->baz_cintura);
    DecodeFrame(&fonte_baz, work->baz_anim, work->baz_frame, 0, crash_verts);
    {
        const CRASH_MODEL *mdl = &fonte_baz.models[fonte_baz.anims[work->baz_anim].model];
        int                i, n = (mdl->nverts + 2) / 3 * 3;

        for (i = 0; i < n; i++)
        {
            crash_verts[i].vx += work->baz_cintura.vx;
            crash_verts[i].vy += work->baz_cintura.vy;
            crash_verts[i].vz += work->baz_cintura.vz;
        }
    }
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
    BazAct(work, GM_Weapon == WP_None && !crash_in_crate && !(objs->flag & DG_FLAG_INVISIBLE) && GM_Vitality > 0 &&
                 (work->anim == CRASH_A_PARADO || work->anim == CRASH_A_CORRER));
    AkuAct(work, !((objs->flag & DG_FLAG_INVISIBLE) || crash_in_crate));
    if (work->cd_state != 4)
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
    if (work->aku)
    {
        DG_DequeuePrim(work->aku);
        DG_FreePrim(work->aku);
    }
    if (work->baz == 1)
    {
        CDBIOS_ForceStop();
    }
    if (work->baz_buf)
    {
        GV_Free(work->baz_buf);
    }
    if (work->cd_buf)
    {
        if (work->cd_state == 1 || work->cd_state == 3)
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

/* pegou uma caixa do Aku Aku (item.c, no lugar da racao): 1a e 2a mascara; a 3a e a invencibilidade */
void Crash_AkuGet(void)
{
    if (crash_aku_inv > 0)
    {
        crash_aku_inv = AKU_INV_TEMPO;
    }
    else if (crash_aku < 2)
    {
        crash_aku++;
    }
    else
    {
        crash_aku_inv = AKU_INV_TEMPO;
    }
    if (crash_cd_ready)
    {
        PlaySound(CRASH_SOM_AKU_PEGA_OFS, crash_aku_inv > 0 ? 0x4C0 : 0x400, 0x3000);
    }
}

/* o Snake levou um golpe (sna_init.c): com mascara, ela absorve (perde uma) e o Snake nao sente */
int Crash_AkuAbsorve(void)
{
    if (crash_aku_inv > 0)
    {
        return 1;
    }
    if (crash_aku > 0)
    {
        crash_aku--;
        if (crash_cd_ready)
        {
            PlaySound(CRASH_SOM_AKU_PERDE_OFS, 0x400, 0x3000);
        }
        return 1;
    }
    return 0;
}

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
    case 2:
        /* dois pedacos (textura + paletas; sons), um de cada vez: o maior bloco livre da memoria normal e ~50 KB */
        if (CDBIOS_TaskState() != CDBIOS_STATE_IDLE)
        {
            return;
        }
        work->cd_buf = GV_Malloc(work->cd_state == 0 ? CRASH_CD_BYTES : CRASH_CD_BYTES_SONS);
        if (!work->cd_buf)
        {
            return;
        }
        if (work->cd_state == 0)
        {
            FS_LoadFileRequest(FS_FILE_BRF, CRASH_CD_SETOR, CRASH_CD_BYTES, work->cd_buf);
        }
        else
        {
            FS_LoadFileRequest(FS_FILE_BRF, CRASH_CD_SETOR_SONS, CRASH_CD_BYTES_SONS, work->cd_buf);
        }
        work->cd_state++;
        return;

    case 3:
        if (FS_LoadFileSync() > 0)
        {
            return;
        }
        SpuSetTransferStartAddr(CRASH_SPU_ADDR);
        SpuWrite(work->cd_buf, CRASH_SONS_BYTES);
        SpuIsTransferCompleted(SPU_TRANSFER_WAIT);
        GV_Free(work->cd_buf);
        work->cd_buf = NULL;
        work->cd_state = 4;
        crash_cd_ready = 1;
        return;

    case 1:
        if (FS_LoadFileSync() > 0)
        {
            return;
        }
        buf = work->cd_buf;

        setRECT(&rect, CRASH_ATLAS_X, CRASH_ATLAS_Y, CRASH_ATLAS_W, CRASH_ATLAS_H);
        LoadImage(&rect, (u_long *)(buf + CRASH_CD_ATLAS));
        setRECT(&rect, CRASH_CLUT_X, CRASH_CLUT_Y, CRASH_CLUT_W, 32);
        LoadImage(&rect, (u_long *)(buf + CRASH_CD_CLUTS));
        DrawSync(0);

        /* o "!" e o "?" dos guardas: "WOAH!" e "WOAH?" */
        setRECT(&pal, CRASH_MARCA_CLUT_X, CRASH_MARCA_CLUT_Y, 16, 1);
        setRECT(&rect, CRASH_WOAH_B_X, CRASH_WOAH_B_Y, CRASH_WOAH_B_W, CRASH_WOAH_B_H);
        DG_SetTexture(GV_StrCode("woah_b"), 0, 0, &rect, &pal, 16);
        setRECT(&rect, CRASH_WOAH_Q_X, CRASH_WOAH_Q_Y, CRASH_WOAH_Q_W, CRASH_WOAH_Q_H);
        DG_SetTexture(GV_StrCode("woah_q"), 0, 0, &rect, &pal, 16);
        AN_SetMarkTextures(GV_StrCode("woah_b"), GV_StrCode("woah_q"));

        GV_Free(work->cd_buf);
        work->cd_buf = NULL;
        work->cd_state = 2;
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

    /* a mascara do Aku Aku (escondida ate pegar a primeira caixa) */
    work->aku = DG_MakePrim(DG_PRIM_FREEPACKS | DG_PRIM_POLY_GT3, AKU_NT, 0, aku_verts, NULL);
    if (work->aku)
    {
        work->aku->n_prims = 0;
        work->aku->prim_count = 0;
        work->aku->callback = AkuCallback;
        work->aku->userdata = work;
        work->aku->root = NULL;
        work->aku->world = body->objs->world;
        DG_QueuePrim(work->aku);
        DG_GroupPrim(work->aku, GM_CurrentMap);
        DG_InvisiblePrim(work->aku);
    }
    work->aku_tipo = -1;
    work->aku_on = 0;

    work->body = body;
    work->anim = -1;
    SetAnim(work, CRASH_A_PARADO, 0);
    LoadFrame(work);
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
    int      worn;     /* 1 = vestida pelo Snake (segue ele, no chao); 0 = solta (chutada); 2 = item no chao */
    int      countdown;/* TNT chutada: quadros ate explodir (0 = nao conta) */
    int      dy;       /* caixa no lugar de item: do item (que flutua) ate o chao */
    SVECTOR  verts[9]; /* 8 cantos + 1 de enchimento (o GTE transforma de 3 em 3) */
} CrateWork;

#define CAIXA_TNT     CRASH_CX_TNT
#define CAIXA_TNT_3   CRASH_CX_TNT_3 /* faces da contagem: 3, 2, 1 */
#define CAIXA_ITEM    2              /* worn = 2: caixa no lugar de um item (racao = caixa do Aku Aku) */
#define ITEM_ESCALA   3476           /* 594 / 700: a caixa no tamanho do Warped (o Crash mede 1100) */
#define TNT_QUADROS   90 /* 3 segundos, como no Crash */

extern BLAST_DATA blast_data_8009F4B8[8];

/* A caixa e convexa: basta descartar as costas, sem ordenar. (O DG_PRIM_ONESIDE do MGS so funciona com
 * quadrilateros: com triangulos ele repete o 2o vertice no lugar do 3o.) */
static void *CrateCallback(DG_PRIM *prim, POLY_FT4 *packs, int count)
{
    CrateWork            *work = (CrateWork *)prim->userdata;
    POLY_GT3             *p = (POLY_GT3 *)packs;
    const unsigned char  *tri = &crash_caixa_tris[work->which * CRASH_CAIXA_NT * 3];
    const unsigned short *tex = &crash_caixa_tex[work->which * CRASH_CAIXA_NT * 5];
    const unsigned char  *luz = &crash_caixa_luz[work->which * CRASH_CAIXA_NT];
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
    for (t = 0; t < CRASH_CAIXA_NT; t++, tri += 3, tex += 5)
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
        if (work->worn == CAIXA_ITEM)
        {
            /* no lugar do item: na posicao dele, sem girar (a caixa do Crash nao gira) */
            work->prim->world = DG_ZeroMatrix;
            work->prim->world.t[0] = work->box->world.t[0];
            work->prim->world.t[1] = work->box->world.t[1] + work->dy;
            work->prim->world.t[2] = work->box->world.t[2];
            return;
        }
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
            int dx = work->prim->world.t[0] - GM_PlayerPosition.vx;
            int dz = work->prim->world.t[2] - GM_PlayerPosition.vz;

            if (dx > -1500 && dx < 1500 && dz > -1500 && dz < 1500)
            {
                crash_boom = 45; /* se o Crash morrer agora, foi a TNT */
            }
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
    if (work->worn == 1)
    {
        crash_in_crate = 0;
        crash_dbg_crate = NULL;
    }
}

static CrateWork *MakeCrate(DG_OBJS *box, int which, int worn);

/* a racao vira a caixa do Aku Aku (pedido do ByteMirage): o item.c chama isto e solta com Crash_CrateRelease */
DG_PRIM *crash_dbg_item[4]; /* (robo de testes) as caixas do Aku Aku da fase */

void *Crash_ItemCrate(DG_OBJS *box, int dy)
{
    CrateWork *work = MakeCrate(box, CRASH_CX_AKU, CAIXA_ITEM);
    int        i;

    if (work)
    {
        work->dy = dy;
        for (i = 0; i < 4; i++)
        {
            if (!crash_dbg_item[i] || i == 3)
            {
                crash_dbg_item[i] = work->prim;
                break;
            }
        }
    }
    return (void *)work;
}

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
    if (work->countdown > 0 && work->worn != CAIXA_ITEM)
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

    if (which < 0 || which >= CRASH_NCAIXAS || (worn == 1 && !GM_PlayerBody))
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
        work->verts[i].vx = worn == CAIXA_ITEM ? (v[0] * ITEM_ESCALA) >> 12 : v[0];
        work->verts[i].vy = worn == CAIXA_ITEM ? (v[1] * ITEM_ESCALA) >> 12 : v[1];
        work->verts[i].vz = worn == CAIXA_ITEM ? (v[2] * ITEM_ESCALA) >> 12 : v[2];
    }
    work->verts[8] = work->verts[0];

    /* os pacotes (12 x 2) vem junto com o DG_PRIM, da memoria normal: o radio nao mexe neles */
    prim = DG_MakePrim(DG_PRIM_FREEPACKS | DG_PRIM_POLY_GT3, CRASH_CAIXA_NT, 0, work->verts, NULL);
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
    prim->world = worn == 1 ? GM_PlayerBody->objs->world : box->world;
    if (worn == 1 && GM_PlayerControl)
    {
        prim->world.t[1] = GM_PlayerControl->levels[0];
    }
    DG_QueuePrim(prim);
    DG_GroupPrim(prim, GM_CurrentMap);
    box->flag |= DG_FLAG_NODRAW;
    if (worn == 1)
    {
        crash_dbg_crate = prim;
    }
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
