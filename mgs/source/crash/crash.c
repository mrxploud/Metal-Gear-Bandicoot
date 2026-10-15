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
#include "enemy/enemy.h" /* WatcherWork: o guarda que procura o Crash 2 */

/* Os dados do Crash moram no MGS/MGB.DAT desde o teste 10. Antes iam no fim de uma copia do BRF.DAT, o que tirava
 * todos os arquivos seguintes do MGS do lugar no disco; agora cada um fica no setor do disco original (precaucao).
 * O empacotador ainda numera os setores a partir do BRF.DAT; aqui eles viram setores dentro do MGB.DAT. */
#define MGB_SETOR(s) ((s) - CRASH_CD_SETOR)

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
    int      pulo_ant;  /* crash_pulo do quadro anterior (o pulo duplo recomeca a cambalhota) */
} Work;

/* buffers do quadro atual (estaticos: o callback roda dentro do motor) */
static SVECTOR       crash_verts[NV_PAD];
static long          crash_sxy[NV_PAD];
static long          crash_sz[NV_PAD];
static short         crash_head[N_BUCKETS];
static short         crash_next[CRASH_NT_MAX];
/* as duas chaves decodificadas (um byte por eixo) moram nos buffers da tela: a decodificacao termina antes de o
 * DrawModel transformar (economiza 1,8 KB de memoria fixa, para o pulo caber) */
#define crash_kA ((unsigned char *)crash_sz)
#define crash_kB ((unsigned char *)crash_sxy)
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
int crash_pulo;        /* no ar: 1 = pulo, 2 = pulo duplo (o estado de pular do sna_init.c escreve a cada quadro) */
int crash_no_ar;       /* altura dos pes acima do chao num pulo (o sna_init.c escreve depois de mover o Snake) */

#define AKU_INV_TEMPO 600 /* 20 s, como no Warped */

static Work *crash_work;
static int   crash_slide_resto; /* crash_slide lido neste quadro */
static int   crash_boom; /* quadros desde que uma TNT explodiu perto do Crash (morte = sobram olhos e tenis) */

/* o Crash 2 (jogador 2, mais para o fim do arquivo) */
typedef struct _Crash2Work Crash2Work;
static Crash2Work *crash2_work;
static void        Crash2Boom(MATRIX *onde);
static int         Crash2Girando(SVECTOR *perto, int raio);
static void        Crash2Entra(void);
static void        Crash2Pacotes(void);
static void        Crash2Mata(void);
static int         Crash2Morto(void);
static void        Crash2Vida(int vida);
static int         guarda_trocou; /* 1 = o guarda que esta pensando agora procura o Crash 2 (Crash_GuardaMira) */
static int         tela_longe;    /* o Crash 2 saiu da camera do Crash 1: a tela se divide (teste 14) */
int                crash2_dbg_woah; /* (robo) "Woah!" de guarda que procurava o Crash 2 */

void        Crash_Woah(void);
static void PlaySound(int ofs, int pitch, int vol);
static void CdLoadStep(Work *work);
static int  CdLivre(void);
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

/* As mortes moram no CD desde a expansao de 14/10/2026 (o codigo do Crash 2 nao cabia na memoria fixa): um bloco
 * como o da bazuca, lido quando alguem morre. Os indices delas vem depois das animacoes da memoria fixa; enquanto o
 * bloco nao chega, a morte e o susto parado (o Crash 1 fazia igual: carregava a morte do CD na hora de morrer). */
#define CRASH_A_MORRER     (CRASH_NANIMS + CRASH_MT_MORRER)
#define CRASH_A_MORRER_TNT (CRASH_NANIMS + CRASH_MT_MORRER_TNT)
static FONTE fonte_morte;
static int   morte_estado; /* 0 = so no CD, 1 = lendo, 2 = na memoria */
static void *morte_buf;
static int   morte_ocioso;
int          crash_dbg_morte; /* (robo) */

/* a fonte e o indice dentro dela de uma animacao do Crash */
static int AnimFonte(int anim, const FONTE **f)
{
    if (anim >= CRASH_NANIMS)
    {
        if (morte_estado == 2)
        {
            *f = &fonte_morte;
            return anim - CRASH_NANIMS;
        }
        anim = CRASH_A_SUSTO;
    }
    *f = &fonte_crash;
    return anim;
}

/*---------------------------------------------------------------------------*/
/* Quadros-chave do Crash 3: cada vertice = vertice anterior + base fixa + diferenca de poucos bits (o numero de
 * bits e por vertice e eixo, em meio byte, igual em todas as chaves que dividem a tabela). A fila de bits vem em
 * palavras de 32 bits, do bit mais alto para o mais baixo. Sem perda: o mesmo byte por eixo que o Warped guarda. */
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
        b = (bits[i >> 1] >> ((i & 1) << 2)) & 15;
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

/* o modelo e o ponto do rosto do quadro tocado. Os vertices sao decodificados so na hora de desenhar (Callback):
 * desde o Crash 2 dois corpos dividem o mesmo buffer, e o desenho dos dois so acontece depois de todos os atores */
static void LoadFrame(Work *work)
{
    const FONTE      *f;
    const CRASH_ANIM *an = &crash_anims[AnimFonte(work->anim, &f)];
    const short      *ra, *rb;
    int               kA, kB;

    if (f != &fonte_crash)
    {
        work->model = f->anims[work->anim - CRASH_NANIMS].model; /* uma morte (sem ponto do rosto) */
        work->tem_rosto = 0;
        return;
    }
    work->model = an->model;

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
static int crash_tinta; /* 1 = o Crash 2: vermelho e azul trocados nas cores dos cantos (o Crash azul) */

static POLY_GT3 *DrawModel(const CRASH_MODEL *mdl, SVECTOR *verts, int cull, POLY_GT3 *packs, int max, int *count)
{
    POLY_GT3             *p;
    POLY_G3              *g;
    SVECTOR              *in;
    const unsigned short *tri, *tex;
    const unsigned char  *cor, *ca, *cb, *cc;
    int i, t, a, b, c, n, nv, zmin, zmax, zsum, zr, bucket, cross, flags, m;
    int ir = crash_tinta ? 2 : 0, ib = 2 - ir;

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
                setRGB0(p, ca[ir], ca[1], ca[ib]);
                setRGB1(p, cb[ir], cb[1], cb[ib]);
                setRGB2(p, cc[ir], cc[1], cc[ib]);
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
                setRGB0(g, DOBRA(ca[ir]), DOBRA(ca[1]), DOBRA(ca[ib]));
                setRGB1(g, DOBRA(cb[ir]), DOBRA(cb[1]), DOBRA(cb[ib]));
                setRGB2(g, DOBRA(cc[ir]), DOBRA(cc[1]), DOBRA(cc[ib]));
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
    crash_tinta = 0;
    if (work->baz_on && work->baz == 2)
    {
        /* com a bazuca o Warped corta o Crash ao meio: a metade de cima (em cima da cintura das pernas) e as pernas */
        const CRASH_MODEL *mdl = &fonte_baz.models[fonte_baz.anims[work->baz_anim].model];
        int                i, n2;

        DecodeFrame(&fonte_baz, work->baz_anim, work->baz_frame, 0, crash_verts);
        for (i = 0; i < (mdl->nverts + 2) / 3 * 3; i++)
        {
            crash_verts[i].vx += work->baz_cintura.vx;
            crash_verts[i].vy += work->baz_cintura.vy;
            crash_verts[i].vz += work->baz_cintura.vz;
        }
        p = DrawModel(mdl, crash_verts, CRASH_CULL, (POLY_GT3 *)packs, MAX_PACKS, &n);
        DecodeFrame(&fonte_baz, work->baz_pernas, work->baz_pframe, 0, crash_verts);
        p = DrawModel(&fonte_baz.models[fonte_baz.anims[work->baz_pernas].model], crash_verts, CRASH_CULL,
                      p, MAX_PACKS - n, &n2);
        n += n2;
    }
    else
    {
        /* espelhado (meio ciclo do engatinhar), os triangulos viram do avesso */
        const FONTE *f;
        int          a = AnimFonte(work->anim, &f);

        DecodeFrame(f, a, work->frame, work->mirror, crash_verts);
        p = DrawModel(&f->models[f->anims[a].model], crash_verts, work->mirror ? -CRASH_CULL : CRASH_CULL,
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

    crash_tinta = 0;
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
    {
        const FONTE *f;
        int          a = AnimFonte(anim, &f);

        work->frame = reverse ? f->anims[a].toca - 1 : 0;
    }
    work->clock = 0;
}

#define NO_PULO(a) ((a) == CRASH_A_PULO_SAIDA || (a) == CRASH_A_PULO_SUBINDO || (a) == CRASH_A_PULO_CAMBALHOTA)

static void Animate(Work *work)
{
    const CRASH_ANIM *an;
    int               want, action, last, pausa, pulo;

    action = work->body->action;
    want = AnimForAction(work, action);
    crash_slide_resto = crash_slide;
    crash_slide = 0; /* vale so para este quadro: o estado de derrapar escreve de novo no proximo */
    pulo = crash_pulo;
    crash_pulo = 0;  /* idem, o estado de pular */
    pausa = 0;

    /* o pulo do Warped: sai do chao e sobe de bracos para cima (segura a ultima pose ate pousar); o pulo duplo e a
     * cambalhota, que comeca e termina nessa mesma pose. Pousou parado: o pouso; andando, ja sai correndo */
    if (pulo)
    {
        if (pulo == 2 && work->pulo_ant != 2)
        {
            SetAnim(work, CRASH_A_PULO_CAMBALHOTA, 0);
        }
        want = NO_PULO(work->anim) ? work->anim : CRASH_A_PULO_SAIDA;
    }
    else if (NO_PULO(work->anim) && want == CRASH_A_PARADO)
    {
        want = CRASH_A_PULO_POUSO;
    }
    work->pulo_ant = pulo;
    if (want == CRASH_A_PARADO && work->anim == CRASH_A_PULO_POUSO)
    {
        want = CRASH_A_PULO_POUSO; /* termina de se recompor (sai antes se andar) */
    }

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

    {
        const FONTE *f;
        int          a = AnimFonte(work->anim, &f);

        an = &f->anims[a];
    }
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
        else if (work->anim == CRASH_A_AGACHAR || work->anim == CRASH_A_PULO_SAIDA || work->anim == CRASH_A_PULO_POUSO)
        {
            /* agachar segura o agachado; saiu do chao, sobe; pousou, fica parado */
            SetAnim(work, work->anim == CRASH_A_AGACHAR     ? CRASH_A_AGACHADO
                          : work->anim == CRASH_A_PULO_SAIDA ? CRASH_A_PULO_SUBINDO
                                                             : CRASH_A_PARADO, 0);
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

/* o bloco do CD (bazuca, mortes) traz o CRASH_MODEL com deslocamentos no lugar dos ponteiros: soma o endereco */
static void BlocoPrepara(unsigned char *buf, FONTE *fonte, const short **pontos)
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
    fonte->models = (const CRASH_MODEL *)(buf + sizeof(BAZ_CAB));
    fonte->anims = (const CRASH_ANIM *)(buf + cab->ofs_anims);
    fonte->key_ofs = (const unsigned long *)(buf + cab->ofs_key_ofs);
    fonte->keys = (const unsigned long *)(buf + cab->ofs_keys);
    if (pontos)
    {
        *pontos = (const short *)(buf + cab->ofs_pontos);
    }
}

/* le o bloco das mortes quando alguem esta morrendo (o Crash ou o Crash 2); devolve a memoria 10 s depois */
static void MorteAct(Work *work, int precisa)
{
    switch (morte_estado)
    {
    case 0:
        if (precisa && work->cd_state == 4 && work->baz != 1 && CdLivre())
        {
            morte_buf = GV_Malloc(CRASH_CD_BYTES_MORTE);
            if (morte_buf)
            {
                FS_LoadFileRequest(FS_FILE_MGB, MGB_SETOR(CRASH_CD_SETOR_MORTE), CRASH_CD_BYTES_MORTE, morte_buf);
                morte_estado = 1;
            }
        }
        break;
    case 1:
        if (FS_LoadFileSync() <= 0)
        {
            BlocoPrepara(morte_buf, &fonte_morte, NULL);
            morte_estado = 2;
            morte_ocioso = 0;
            crash_dbg_morte++;
        }
        break;
    case 2:
        if (precisa)
        {
            morte_ocioso = 0;
        }
        else if (++morte_ocioso > BAZ_OCIOSO)
        {
            GV_Free(morte_buf);
            morte_buf = NULL;
            morte_estado = 0;
        }
        break;
    }
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
        if (quer && work->cd_state == 4 && morte_estado != 1 && CdLivre())
        {
            work->baz_buf = GV_Malloc(CRASH_CD_BYTES_BAZUCA);
            if (work->baz_buf)
            {
                FS_LoadFileRequest(FS_FILE_MGB, MGB_SETOR(CRASH_CD_SETOR_BAZUCA), CRASH_CD_BYTES_BAZUCA, work->baz_buf);
                work->baz = 1;
            }
        }
        break;
    case 1:
        if (FS_LoadFileSync() <= 0)
        {
            BlocoPrepara(work->baz_buf, &fonte_baz, &baz_pontos);
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
     * ByteMirage viu o Crash flutuando); no pulo, mais a altura dos pes acima do chao */
    work->prim->world = objs->world;
    if (GM_PlayerControl)
    {
        work->prim->world.t[1] = GM_PlayerControl->levels[0] + crash_no_ar;
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
    Crash2Entra();
    MorteAct(work, work->anim >= CRASH_NANIMS || Crash2Morto());
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
    Crash2Pacotes();
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
    if (morte_estado == 1)
    {
        CDBIOS_ForceStop();
    }
    if (morte_buf)
    {
        GV_Free(morte_buf);
        morte_buf = NULL;
    }
    morte_estado = 0;
    if (work->cd_buf)
    {
        if (work->cd_state == 1 || work->cd_state == 3)
        {
            CDBIOS_ForceStop();
        }
        GV_Free(work->cd_buf);
    }
    crash_work = NULL;
    Crash2Mata(); /* o Crash 2 vai junto (e volta com o Crash na proxima fase) */
}

/*---------------------------------------------------------------------------*/
/* Sons do Crash: o ADPCM vai para um buraco livre da memoria de som e toca na voz 20, que o driver do MGS deixa
 * para nos (sd_cli.c: 7 vagas de efeito em vez de 8). Ate o teste 10 era a voz 23, que e o relogio do driver: ela
 * toca silencio em laco e gera a interrupcao da SPU que faz o som do jogo andar. O primeiro som do Crash parava o
 * relogio: a musica e os efeitos sumiam e a proxima cena com fala travava (o elevador do Dock).
 * Tom 0x400 = 11025 Hz; a voz do Crash sorteia de 0x39A a 0x466. */

#define CRASH_VOZ SPU_VOICECH(20)

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
    crash2_dbg_woah += guarda_trocou;
}

/* O leitor de CD e a SPU sao do MGS enquanto uma fala, um radio ou uma demo toca do CD (stream): entre um bloco
 * e outro o leitor fica parado, e o nosso pedido de leitura podia entrar no meio do stream (teste 10: a chegada
 * ao Heliporto, uma demo com fala, nao terminava na fusao). */
static int CdLivre(void)
{
    return CDBIOS_TaskState() == CDBIOS_STATE_IDLE && FS_StreamTaskState() == 0 &&
           !(GM_GameStatus & STATE_VOX_STREAM);
}

/* Texturas, paletas e sons ficam no MGS/MGB.DAT: lidos uma vez por fase para um buffer temporario, mandados para
 * a VRAM e a SPU, e o buffer volta para a memoria. Assim esses 19 KB nao ocupam a RAM do executavel. Sem travar:
 * espera o leitor de CD ficar livre. */
static void CdLoadStep(Work *work)
{
    RECT           rect, pal;
    unsigned char *buf;

    switch (work->cd_state)
    {
    case 0:
    case 2:
        /* dois pedacos (textura + paletas; sons), um de cada vez: o maior bloco livre da memoria normal e ~50 KB */
        if (!CdLivre())
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
            FS_LoadFileRequest(FS_FILE_MGB, MGB_SETOR(CRASH_CD_SETOR), CRASH_CD_BYTES, work->cd_buf);
        }
        else
        {
            FS_LoadFileRequest(FS_FILE_MGB, MGB_SETOR(CRASH_CD_SETOR_SONS), CRASH_CD_BYTES_SONS, work->cd_buf);
        }
        work->cd_state++;
        return;

    case 3:
        if (FS_LoadFileSync() > 0 || !CdLivre())
        {
            return; /* a SPU tambem e do driver enquanto ele toca uma fala do CD */
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

/* A explosao da TNT (pedido do ByteMirage: "que a explosao da TNT causasse dano em todo mundo"): e a explosao do MGS
 * sem lado (fere o Crash, os guardas e o Crash 2), mais forte e maior que a granada (dano 0x100 >> 1 em 1000/2000);
 * TNT perto de outra TNT contando faz ela explodir junto */
BLAST_DATA crash_tnt_blast = { 0x300, 5, 1600, 3200, WP_None };
#define TNT_MAX     6
#define TNT_RAIO    2600 /* perto assim, se o Crash (ou o Crash 2) morrer, foi a TNT: sobram os olhos e os tenis */
#define TNT_CADEIA  3500
#define TNT_GIRO    1000 /* o giro do Crash numa TNT no chao: bum na hora */
static void   *crash_tnts[TNT_MAX];
static MATRIX  crash_crate_onde; /* onde nasce uma caixa sem objeto do MGS (a TNT que o Crash deixa ao pular) */
int            crash_dbg_tnt;    /* (robo) quantas TNT explodiram */

static int Perto(SVECTOR *a, SVECTOR *b, int raio)
{
    int dx = a->vx - b->vx, dz = a->vz - b->vz;

    return dx > -raio && dx < raio && dz > -raio && dz < raio;
}

/* bum: a explosao sem lado do MGS (fere todo mundo), a morte certa do Crash perto dela e a reacao em cadeia */
static void TntBoom(MATRIX *onde)
{
    SVECTOR c;
    int     i;

    c.vx = onde->t[0];
    c.vy = onde->t[1];
    c.vz = onde->t[2];
    if (Perto(&c, &GM_PlayerPosition, TNT_RAIO))
    {
        crash_boom = 45; /* se o Crash morrer agora, foi a TNT */
    }
    Crash2Boom(onde);
    if (GM_PlayerControl)
    {
        GM_CurrentMap = GM_PlayerControl->map->index;
    }
    NewBlast(onde, &crash_tnt_blast);
    crash_dbg_tnt++;
    for (i = 0; i < TNT_MAX; i++)
    {
        CrateWork *o = crash_tnts[i];
        SVECTOR    p;

        if (!o || o->countdown <= 6)
        {
            continue;
        }
        p.vx = o->prim->world.t[0];
        p.vy = o->prim->world.t[1];
        p.vz = o->prim->world.t[2];
        if (Perto(&c, &p, TNT_CADEIA))
        {
            o->countdown = 6 + i * 3; /* uma atras da outra */
        }
    }
}

/* com a caixa TNT vestida, a bolinha (o giro do Crash) explode a caixa com ele dentro */
void Crash_TntExplode(MATRIX *onde)
{
    MATRIX m = *onde;

    if (GM_PlayerControl)
    {
        m.t[1] = GM_PlayerControl->levels[0];
    }
    TntBoom(&m);
    crash_boom = 45;
}

static CrateWork *MakeCrate(DG_OBJS *box, int which, int worn);

/* X dentro da caixa: o Crash sai pulando; a TNT fica no chao contando 3, 2, 1 */
void Crash_SaiDaCaixa(int tnt, MATRIX *onde)
{
    CrateWork *w;

    if (!tnt)
    {
        return;
    }
    crash_crate_onde = *onde;
    if (GM_PlayerControl)
    {
        crash_crate_onde.t[1] = GM_PlayerControl->levels[0];
    }
    w = MakeCrate(NULL, CAIXA_TNT, 0);
    if (w)
    {
        w->countdown = TNT_QUADROS;
    }
}

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
        if (!work->box && work->countdown > 1)
        {
            /* no chao: o giro do Crash (ou do Crash 2) nela explode na hora, como no Crash */
            SVECTOR c;

            c.vx = work->prim->world.t[0];
            c.vy = work->prim->world.t[1];
            c.vz = work->prim->world.t[2];
            if ((crash_work && crash_work->anim == CRASH_A_GIRO && Perto(&c, &GM_PlayerPosition, TNT_GIRO)) ||
                Crash2Girando(&c, TNT_GIRO))
            {
                work->countdown = 1;
            }
        }
        if (work->countdown <= 0)
        {
            TntBoom(&work->prim->world);
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
    int i;

    for (i = 0; i < TNT_MAX; i++)
    {
        if (crash_tnts[i] == work)
        {
            crash_tnts[i] = NULL;
        }
    }
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
    /* box NULL: caixa solta, sem objeto do MGS por baixo (a TNT que o Crash deixa no chao), em crash_crate_onde */
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
    prim->world = worn == 1 ? GM_PlayerBody->objs->world : box ? box->world : crash_crate_onde;
    if (worn == 1 && GM_PlayerControl)
    {
        prim->world.t[1] = GM_PlayerControl->levels[0];
    }
    DG_QueuePrim(prim);
    DG_GroupPrim(prim, GM_CurrentMap);
    if (box)
    {
        box->flag |= DG_FLAG_NODRAW;
    }
    if (which == CAIXA_TNT && worn != 1)
    {
        for (i = 0; i < TNT_MAX; i++)
        {
            if (!crash_tnts[i])
            {
                crash_tnts[i] = work;
                break;
            }
        }
    }
    if (worn == 1)
    {
        crash_dbg_crate = prim;
    }
    return work;
}

/*---------------------------------------------------------------------------*/
/* Subir nas coisas (pedido do ByteMirage: "o Crash pula mas nao consegue subir nas coisas, talvez porque o Snake
 * invisivel nao deixe"). Era quase isso: o Snake testa as paredes sempre na altura do chao + 750, mesmo no ar (o
 * sna_init.c agora testa na altura dos pes durante o pulo). E o MGS nao tem chao em cima dos obstaculos, porque o
 * Snake nunca sobe neles: aqui o topo de um contorno fechado de paredes da mesma altura (caixa, conteiner, grade,
 * o caminhao) vira chao. "Dentro do contorno" = o raio para +x e o raio para +z cruzam, os dois, um numero impar de
 * paredes com esse topo (com um raio so, o Crash flutuava entre duas grades). Topo inclinado (corrimao) nao conta. */

#define TOPO_TOL   64
#define TOPO_PERTO 2500

int        crash_topo = CRASH_SEM_TOPO; /* (robo) o chao de mentira do Crash neste quadro */
static int crash_topo_ant[2] = { CRASH_SEM_TOPO, CRASH_SEM_TOPO };
CONTROL   *crash2_control;              /* o CONTROL do Crash 2 (o control.c pergunta por ele tambem) */
static int crash2_pulando;

/* o raio de (x, z) para +x (eixo 0) ou para +z (eixo 1) cruza a parede? Contas em /4 para caber em 32 bits */
static int Cruza(HZD_SEG *s, int x, int z, int eixo)
{
    int x1, z1, x2, z2, v;

    if (eixo)
    {
        x1 = s->p1.z >> 2;
        z1 = s->p1.x >> 2;
        x2 = s->p2.z >> 2;
        z2 = s->p2.x >> 2;
        v = x;
        x = z;
        z = v;
    }
    else
    {
        x1 = s->p1.x >> 2;
        z1 = s->p1.z >> 2;
        x2 = s->p2.x >> 2;
        z2 = s->p2.z >> 2;
    }
    x >>= 2;
    z >>= 2;
    if ((z1 > z) == (z2 > z))
    {
        return 0;
    }
    v = (x1 - x) * (z2 - z1) + (z - z1) * (x2 - x1);
    return (v > 0) == (z2 > z1);
}

static int TopoDaParede(HZD_SEG *s)
{
    int t1 = s->p1.y + s->p1.h;
    int t2 = s->p2.y + s->p2.h;

    if (t1 - t2 > TOPO_TOL || t2 - t1 > TOPO_TOL)
    {
        return CRASH_SEM_TOPO;
    }
    return (t1 + t2) >> 1;
}

static int Longe(HZD_SEG *s, int x, int z)
{
    return (s->p1.x < x - TOPO_PERTO && s->p2.x < x - TOPO_PERTO) ||
           (s->p1.x > x + TOPO_PERTO && s->p2.x > x + TOPO_PERTO) ||
           (s->p1.z < z - TOPO_PERTO && s->p2.z < z - TOPO_PERTO) ||
           (s->p1.z > z + TOPO_PERTO && s->p2.z > z + TOPO_PERTO);
}

static int TopoDeParede(HZD_HDL *hzd, int seg_flag, int x, int z, int pes, int chao)
{
    HZD_GRP *grp = hzd->grp;
    HZD_SEG *s;
    char    *fl;
    int      cand[4], nc, i, k, t, n0, n1, melhor;

    /* candidatos: topos perto do Crash, acima do chao de verdade e abaixo dos pes (ou quase: ele esta caindo) */
    nc = 0;
    s = grp->walls;
    fl = grp->wallsFlags;
    for (i = grp->n_walls; i > 0; i--, s++, fl++)
    {
        if (*fl & seg_flag)
        {
            continue;
        }
        t = TopoDaParede(s);
        if (t == CRASH_SEM_TOPO || t < chao + 200 || t > pes + 400 || Longe(s, x, z))
        {
            continue;
        }
        for (k = 0; k < nc; k++)
        {
            if (cand[k] - t <= TOPO_TOL && t - cand[k] <= TOPO_TOL)
            {
                break;
            }
        }
        if (k == nc && nc < 4)
        {
            cand[nc++] = t;
        }
    }

    melhor = CRASH_SEM_TOPO;
    for (k = 0; k < nc; k++)
    {
        if (cand[k] <= melhor)
        {
            continue;
        }
        n0 = n1 = 0;
        s = grp->walls;
        fl = grp->wallsFlags;
        for (i = grp->n_walls; i > 0; i--, s++, fl++)
        {
            if (*fl & seg_flag)
            {
                continue;
            }
            t = TopoDaParede(s);
            if (t == CRASH_SEM_TOPO || t - cand[k] > TOPO_TOL || cand[k] - t > TOPO_TOL)
            {
                continue;
            }
            n0 += Cruza(s, x, z, 0);
            n1 += Cruza(s, x, z, 1);
        }
        if ((n0 & 1) && (n1 & 1))
        {
            melhor = cand[k];
        }
    }
    return melhor;
}

int Crash_ChaoExtra(CONTROL *ctrl, int pes, int chao)
{
    int quem, no_ar, t;

    if (ctrl && ctrl == GM_PlayerControl)
    {
        quem = 0;
        no_ar = crash_pulo_no_ar;
    }
    else if (ctrl && ctrl == crash2_control)
    {
        quem = 1;
        no_ar = crash2_pulando;
    }
    else
    {
        return CRASH_SEM_TOPO;
    }
    /* no chao comum (sem pulo e sem estar em cima de nada) nao gasta nada */
    if (!no_ar && crash_topo_ant[quem] == CRASH_SEM_TOPO)
    {
        if (quem == 0)
        {
            crash_topo = CRASH_SEM_TOPO;
        }
        return CRASH_SEM_TOPO;
    }
    t = TopoDeParede(ctrl->map->hzd, ctrl->seg_flag, ctrl->mov.vx, ctrl->mov.vz, pes, chao);
    crash_topo_ant[quem] = t;
    if (quem == 0)
    {
        crash_topo = t;
    }
    return t;
}

/*---------------------------------------------------------------------------*/
/* O Crash 2 (pedido do ByteMirage: multijogador cooperativo com tela dividida). Quem segura o controle 2 aperta
 * START e o Crash 2 (azul, para ninguem se perder) aparece ao lado do Crash; SELECT no controle 2 tira ele. Ele e um
 * ator nosso, nao um segundo Snake: o codigo do Snake depende de dezenas de variaveis globais do jogador, e duas
 * copias dele brigariam por elas. Tem a colisao do MGS (CONTROL), corre, pula (com pulo duplo), gira (derruba
 * guarda), sobe nas coisas, leva tiro e explosao (alvo do lado do jogador: o giro do Crash nao acerta ele), e quando
 * morre volta ao lado do Crash 90 quadros depois. Desde o teste 13 os guardas veem ele (Crash_GuardaMira).
 *
 * A tela dividida: o PS1 nao aguenta desenhar a fase duas vezes por quadro (nem em tempo, nem na memoria de
 * pacotes), entao cada quadro desenha uma metade so. Nos quadros pares, a de cima, com a camera do Crash; nos
 * impares, a de baixo, com a mesma camera levada ate o Crash 2. A outra metade e copiada da tela anterior (uma copia
 * de VRAM no fim da lista de desenho, depois do HUD). Cada metade anda a metade dos quadros. Gambiarra? Talvez.
 * Desde o teste 14 ela so se divide quando o Crash 2 sai da camera do Crash 1 (C2NaCamera); perto, e a tela
 * inteira, na velocidade normal. */

#define C2_VIDA      1024
#define C2_PACKS     300                 /* triangulos por quadro (12 KB por metade da memoria de pacotes) */
#define C2_CORRE     105
#define C2_SALA      6000                /* o Crash 1 mudou de sala e o Crash 2 estava mais longe: volta */
#define C2_BOIA      700                 /* na agua, os pes ficam ate 70 cm abaixo da superficie */

/* a agua: o wt_area.c (a caixa de agua da fase, a mesma que diz se o Snake esta na agua) chama Crash_Agua a cada
 * quadro; com o Crash 2 dentro dela, ele boia na superficie por 2 quadros (o tempo de o proximo aviso chegar) */
static int c2_agua, c2_agua_vida;

void Crash_Agua(SVECTOR *b)
{
    SVECTOR *p;

    if (!crash2_control)
    {
        return;
    }
    p = &crash2_control->mov;
    if (p->vx > b[0].vx && p->vx < b[1].vx && p->vz > b[0].vz && p->vz < b[1].vz &&
        p->vy - crash2_control->height < b[1].vy)
    {
        c2_agua = b[1].vy;
        c2_agua_vida = 2;
    }
}
#define C2_VOLTA     90                  /* quadros morto ate voltar */

struct _Crash2Work
{
    GV_ACT   actor;
    CONTROL  control;
    TARGET  *alvo;      /* onde ele leva os golpes */
    TARGET   golpe;     /* o giro */
    DG_PRIM *prim;
    int      anim, frame, mirror, clock, model;
    int      vel_y;     /* como o field_A2C do Snake: a altura anda o dobro disso por quadro */
    int      pulo_fase; /* 0 = X segurado desde a saida, 1 = soltou (o duplo pode), 2 = duplo usado */
    int      giro;      /* quadros de giro que faltam */
    int      dano;      /* quadros de susto que faltam */
    int      morto;     /* quadros desde que morreu (0 = vivo) */
    int      boom;      /* uma TNT explodiu perto ha pouco */
    int      vida;
};

int                crash2_ativo;    /* o controle 2 entrou (vale de uma fase para a outra) */
int                crash2_dbg_vida; /* (robo) */
int                crash2_dbg_nomem;

static void Crash2Boom(MATRIX *onde)
{
    SVECTOR c;

    if (!crash2_work)
    {
        return;
    }
    c.vx = onde->t[0];
    c.vy = onde->t[1];
    c.vz = onde->t[2];
    if (Perto(&c, &crash2_work->control.mov, TNT_RAIO))
    {
        crash2_work->boom = 45;
    }
}

static int Crash2Girando(SVECTOR *perto, int raio)
{
    return crash2_work && crash2_work->giro > 0 && Perto(perto, &crash2_work->control.mov, raio);
}

static void *Crash2Callback(DG_PRIM *prim, POLY_FT4 *packs, int count)
{
    Crash2Work *w = (Crash2Work *)prim->userdata;
    POLY_GT3   *p;
    int         n;

    if (!packs)
    {
        if (!GV_AllocMemory2(GV_Clock, sizeof(POLY_GT3) * C2_PACKS, &prim->packs[GV_Clock]))
        {
            crash2_dbg_nomem++;
            prim->prim_count = 0;
            return NULL;
        }
        packs = prim->packs[GV_Clock];
    }
    {
        const FONTE *f;
        int          a = AnimFonte(w->anim, &f);

        DecodeFrame(f, a, w->frame, w->mirror, crash_verts);
        crash_tinta = 1;
        p = DrawModel(&f->models[f->anims[a].model], crash_verts, w->mirror ? -CRASH_CULL : CRASH_CULL,
                      (POLY_GT3 *)packs, C2_PACKS, &n);
    }
    crash_tinta = 0;
    prim->prim_count = n;
    return p;
}

static void C2SetAnim(Crash2Work *w, int anim)
{
    if (w->anim == anim)
    {
        return;
    }
    if (anim == CRASH_A_GIRO)
    {
        PlaySound(CRASH_SOM_GIRO_OFS, 0x480, 0x1800);
    }
    else if ((anim == CRASH_A_MORRER || anim == CRASH_A_MORRER_TNT) && crash_cd_ready)
    {
        PlaySound(CRASH_SOM_WOAH_OFS, 0x466, 0x3000); /* o Crash 2 grita um pouco mais fino */
    }
    w->anim = anim;
    w->frame = 0;
    w->mirror = 0;
    w->clock = 0;
}

static void C2Anima(Crash2Work *w, int want)
{
    const CRASH_ANIM *an;
    int               last;

    C2SetAnim(w, want);
    {
        const FONTE *f;
        int          i = AnimFonte(w->anim, &f);

        an = &f->anims[i];
    }
    last = an->toca - 1;
    w->clock += GV_PassageTime;
    while (w->clock >= 2)
    {
        w->clock -= 2;
        if (w->frame < last)
        {
            w->frame++;
        }
        else if (an->loop)
        {
            w->frame = 0;
            if (an->loop == 2)
            {
                w->mirror ^= 1;
            }
        }
        else if (w->anim == CRASH_A_PULO_SAIDA || w->anim == CRASH_A_PULO_POUSO)
        {
            C2SetAnim(w, w->anim == CRASH_A_PULO_SAIDA ? CRASH_A_PULO_SUBINDO : CRASH_A_PARADO);
            an = &crash_anims[w->anim];
            last = an->toca - 1;
        }
    }
    w->model = an->model;
}

/* ao lado do Crash, em pe: o primeiro lado (esquerda, direita, atras, frente) sem parede no caminho; nenhum, junto
 * dele (no primeiro teste, no Heliporto, o Crash 2 nasceu dentro do conteiner na frente do Crash e ficou preso) */
static void C2Volta(Crash2Work *w)
{
    static short lados[4] = { 1024, -1024, 2048, 0 };
    CONTROL     *c = &w->control;
    SVECTOR      lado, de, para;
    int          i;

    if (!GM_PlayerControl)
    {
        return;
    }
    de = GM_PlayerControl->mov;
    /* a linha ate o lugar novo e testada perto do chao: na cintura do Crash (1,1 m) ela passava por cima de caixa e
     * mureta baixa, e o Crash 2 nascia dentro delas (achado do ByteMirage no teste 14) */
    de.vy = GM_PlayerControl->levels[0] + 400;
    lado.vx = lado.vy = lado.vz = 0;
    for (i = 0; i < 4; i++)
    {
        GV_DirVec2(GM_PlayerControl->rot.vy + lados[i], 900, &lado);
        para.vx = de.vx + lado.vx;
        para.vy = de.vy;
        para.vz = de.vz + lado.vz;
        if (!HZD_OnlineHazardCheck(GM_PlayerControl->map->hzd, &de, &para, HZD_CHK_ALL, GM_PlayerControl->seg_flag))
        {
            break;
        }
        lado.vx = lado.vz = 0;
    }
    lado.vx = lado.vx * 7 / 9; /* 700 do Crash: a linha testada foi ate 900 */
    lado.vz = lado.vz * 7 / 9;
    c->mov.vx = GM_PlayerControl->mov.vx + lado.vx;
    c->mov.vy = GM_PlayerControl->levels[0] + c->height + 200;
    c->mov.vz = GM_PlayerControl->mov.vz + lado.vz;
    c->rot = GM_PlayerControl->rot;
    c->turn = c->rot;
    c->levels[0] = GM_PlayerControl->levels[0];
    c->map = GM_PlayerControl->map;
    w->vel_y = 0;
    w->morto = 0;
    w->boom = 0;
    w->dano = 0;
    w->giro = 0;
    w->vida = C2_VIDA;
    w->alvo->vital = C2_VIDA;
    w->alvo->damaged = 0;
    crash_topo_ant[1] = CRASH_SEM_TOPO;
}

/* o giro: derruba os guardas em volta, como o do Crash (sem dano, com o tombo do chute) */
static void C2Golpe(Crash2Work *w)
{
    static SVECTOR tamanho = { 900, 300, 900 };
    SVECTOR        centro, forca;

    GM_SetTarget(&w->golpe, TARGET_POWER, PLAYER_SIDE, &tamanho);
    GV_DirVec2(w->control.rot.vy, 100, &forca);
    GM_SetPowerTarget(&w->golpe, POWER_CONST, 4, 0, 3, &forca);
    centro = w->control.mov;
    centro.vy += 200;
    GM_MoveTarget(&w->golpe, &centro);
    GM_PowerTarget(&w->golpe);
}

/* o Crash 2 aparece na camera do Crash 1 (a da tela inteira)? Dentro de margem/16 da meia tela, contando do centro.
 * A camera do canal 3D leva o mundo para a vista (eye_inv, no GTE, como os guardas fazem); na tela, x * screen / z:
 * a conta compara sem dividir */
static int C2NaCamera(int margem)
{
    DG_CHANL *cp = &DG_Chanls[1];
    SVECTOR   v;
    int       l;

    DG_SetPos(&cp->eye_inv);
    DG_PutVector(&crash2_work->control.mov, &v, 1);
    if (v.vz < 500)
    {
        return 0; /* atras da camera (ou colado nela) */
    }
    l = v.vz * margem;
    if (v.vx < 0)
    {
        v.vx = -v.vx;
    }
    if (v.vy < 0)
    {
        v.vy = -v.vy;
    }
    return v.vx * cp->screen * 32 < FRAME_WIDTH * l && v.vy * cp->screen * 32 < FRAME_HEIGHT * l;
}

static void Crash2Act(Crash2Work *w)
{
    GV_PAD  *pad = &GV_PadData[1];
    CONTROL *c = &w->control;
    int      dir, g, want, boia;
    MATRIX   m;

    if (!GM_PlayerControl || (pad->press & PAD_SELECT) || (GM_PlayerStatus & PLAYER_SECOND_AVAILABLE))
    {
        /* SELECT no controle 2: o Crash 2 sai; na sala do Psycho Mantis o controle 2 e dele */
        if (pad->press & PAD_SELECT)
        {
            crash2_ativo = 0;
        }
        GV_DestroyActor(&w->actor);
        return;
    }
    /* sem coleira (teste 14; ate o 13 eram 12 m): o Crash 2 anda pela area inteira do Crash 1, e as paredes da sala
     * seguram. Volta se cair do mapa, ou se o Crash 1 passar para outra sala (a colisao muda) com ele longe */
    if ((c->map != GM_PlayerControl->map && GV_DiffVec3(&c->mov, &GM_PlayerControl->mov) > C2_SALA) ||
        c->mov.vy < GM_PlayerControl->levels[0] - 8000)
    {
        C2Volta(w);
    }
    c->map = GM_PlayerControl->map; /* a colisao da area em que o Crash esta */
    GM_CurrentMap = c->map->index;
    if (GM_GameStatus < 0)
    {
        DG_InvisiblePrim(w->prim); /* nas cenas do jogo (demo) o Crash 2 some e espera */
        return;
    }
    if (pad->press & PAD_TRIANGLE)
    {
        C2Volta(w); /* triangulo: volta para perto do Crash (preso atras de uma porta, por exemplo) */
    }

    /* golpes recebidos: tiro e explosao */
    if (w->alvo->damaged & TARGET_POWER)
    {
        w->vida = w->alvo->vital;
        w->alvo->damaged = 0;
        w->alvo->damage = 0;
        if (w->vida > 0 && !w->morto)
        {
            w->dano = 18;
        }
    }
    if (w->vida <= 0 && !w->morto)
    {
        w->morto = 1;
    }
    /* morto, o corpo nao leva tiro nem segura a bala que ia no Crash 1 */
    w->alvo->class = w->morto ? TARGET_AVAIL : TARGET_AVAIL | TARGET_POWER | TARGET_SEEK;
    if (w->boom > 0)
    {
        w->boom--;
    }

    c->step.vx = c->step.vz = 0;
    if (w->morto)
    {
        if (++w->morto > C2_VOLTA)
        {
            C2Volta(w);
        }
    }
    else
    {
        /* o direcional ja vem relativo a camera (o MGS soma a origem da camera em pad->dir) */
        dir = pad->dir;
        if (dir >= 0 && w->dano < 10)
        {
            c->turn.vy = dir;
            GV_DirVec2(dir, w->giro > 0 ? 70 : C2_CORRE, &c->step);
        }
        if ((pad->press & PAD_CROSS) && !crash2_pulando)
        {
            w->vel_y = 130;
            w->pulo_fase = 0;
            crash2_pulando = 1;
            C2SetAnim(w, CRASH_A_PULO_SAIDA);
        }
        else if (crash2_pulando)
        {
            if (w->pulo_fase == 0 && !(pad->status & PAD_CROSS))
            {
                w->pulo_fase = 1;
            }
            else if (w->pulo_fase == 1 && (pad->press & PAD_CROSS))
            {
                w->pulo_fase = 2;
                w->vel_y = 110;
                C2SetAnim(w, CRASH_A_PULO_CAMBALHOTA);
            }
        }
        if ((pad->press & PAD_CIRCLE) && w->giro == 0)
        {
            w->giro = 16;
        }
    }
    /* a gravidade do pulo do Crash: segurando o X sobe mais */
    if (w->vel_y > 0)
    {
        g = (pad->status & PAD_CROSS) ? 13 : 32;
    }
    else
    {
        g = 16;
    }
    w->vel_y -= g;
    if (w->vel_y < -150)
    {
        w->vel_y = -150;
    }
    c->step.vy = w->vel_y * 2;
    /* na agua (boiando) as paredes tambem sao testadas na altura dos pes: o chao do tanque esta 4 m abaixo */
    boia = c2_agua_vida > 0;
    if (boia)
    {
        c2_agua_vida--;
    }
    c->hzd_height = (crash2_pulando || boia) ? c->mov.vy - c->height + 350 : c->levels[0] + 750;

    GM_ActControl(c);

    /* o Crash 2 nao mergulha (o Snake nada por baixo das plataformas do Dock; o Crash 2 afundava ate o fundo, a 4 m,
     * e andava por baixo do cais, com a camera dele dentro da estrutura): boia com a agua no peito e pula para fora */
    if (boia && c->mov.vy - c->height < c2_agua - C2_BOIA)
    {
        c->mov.vy = c2_agua - C2_BOIA + c->height;
        c->grounded |= 1;
    }

    if (c->grounded & 1)
    {
        if (w->vel_y <= 0)
        {
            if (crash2_pulando && !w->morto && w->giro == 0)
            {
                C2SetAnim(w, CRASH_A_PULO_POUSO);
            }
            crash2_pulando = 0;
            w->vel_y = 0;
        }
    }
    else if (!crash2_pulando && w->vel_y < -40)
    {
        crash2_pulando = 1; /* saiu de uma beirada: cai como no pulo */
        w->pulo_fase = 2;
    }
    if ((c->grounded & 2) && w->vel_y > 0)
    {
        w->vel_y = 0;
    }

    if (w->giro > 0)
    {
        if ((w->giro & 3) == 0)
        {
            C2Golpe(w);
        }
        w->giro--;
    }
    if (w->dano > 0)
    {
        w->dano--;
    }

    /* o alvo segue o corpo */
    GM_MoveTarget(w->alvo, &c->mov);
    crash2_dbg_vida = w->vida;

    /* a animacao */
    if (w->morto)
    {
        want = (w->anim == CRASH_A_MORRER || w->anim == CRASH_A_MORRER_TNT) ? w->anim
             : w->boom > 0 ? CRASH_A_MORRER_TNT : CRASH_A_MORRER;
    }
    else if (w->dano > 0)
    {
        want = CRASH_A_SUSTO;
    }
    else if (w->giro > 0)
    {
        want = CRASH_A_GIRO;
    }
    else if (crash2_pulando)
    {
        want = NO_PULO(w->anim) ? w->anim : CRASH_A_PULO_SAIDA;
    }
    else if (c->step.vx || c->step.vz)
    {
        want = CRASH_A_CORRER;
    }
    else if (w->anim == CRASH_A_PULO_POUSO)
    {
        want = CRASH_A_PULO_POUSO;
    }
    else
    {
        want = CRASH_A_PARADO;
    }
    C2Anima(w, want);

    /* o corpo: pes no chao (mov e a cintura) */
    RotMatrixYXZ_gte(&c->rot, &m);
    m.t[0] = c->mov.vx;
    m.t[1] = c->mov.vy - c->height;
    m.t[2] = c->mov.vz;
    w->prim->world = m;
    DG_GroupPrim(w->prim, GM_PlayerBody ? GM_PlayerBody->objs->group_id : GM_CurrentMap);
    DG_VisiblePrim(w->prim);
    Crash2Vida(w->morto ? 0 : w->vida);

    /* tela inteira enquanto o Crash 2 aparece na camera do Crash 1; divide quando ele chega a 7/8 da borda e so volta
     * a juntar quando ele esta bem dentro (5/8), para nao ficar piscando na divisa */
    tela_longe = !C2NaCamera(tela_longe ? 10 : 14);
}

/* o radio pega a memoria de pacotes: o Crash 2 devolve os dele, como o Crash */
static void Crash2Pacotes(void)
{
    DG_PRIM *prim;
    int      i;

    if (!crash2_work || !(prim = crash2_work->prim))
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

static int Crash2Morto(void)
{
    return crash2_work && crash2_work->morto;
}

static void Crash2Mata(void)
{
    if (crash2_work)
    {
        GV_DestroyActor(&crash2_work->actor);
    }
}

static void Crash2Die(Crash2Work *w)
{
    int i;

    if (w->prim)
    {
        for (i = 0; i < 2; i++)
        {
            if (w->prim->packs[i])
            {
                GV_FreeMemory2(i, &w->prim->packs[i]);
                w->prim->packs[i] = NULL;
            }
        }
        DG_DequeuePrim(w->prim);
        DG_FreePrim(w->prim);
    }
    if (w->alvo)
    {
        GM_FreeTarget(w->alvo);
    }
    if (crash2_control)
    {
        GM_FreeControl(&w->control);
    }
    crash2_work = NULL;
    crash2_control = NULL;
    crash2_pulando = 0;
}

static void NewCrash2(void)
{
    static SVECTOR tamanho = { 300, 650, 300 };
    Crash2Work    *w;
    DG_PRIM       *prim;

    if (crash2_work || !GM_PlayerControl)
    {
        return;
    }
    w = GV_NewActor(GV_ACTOR_AFTER, sizeof(Crash2Work));
    if (!w)
    {
        return;
    }
    GV_SetNamedActor(&w->actor, Crash2Act, Crash2Die, "crash2");
    crash2_work = w;
    if (GM_InitControl(&w->control, 0, GM_PlayerControl->map->index) < 0)
    {
        GV_DestroyActor(&w->actor);
        return;
    }
    w->control.height = 1100;
    /* BOTH_CHECK: alem de empurrar para fora das paredes perto (o que o MGS faz andando devagar), testa a linha do
     * passo inteiro a cada quadro, como o Snake faz em alguns estados: um empurrao (tiro, explosao) nao atravessa */
    w->control.skip_flag = CTRL_SKIP_TRAP | CTRL_BOTH_CHECK;
    /* as mesmas paredes do Snake (SEGMENT_ATR do sna_init.c). Ate o teste 14 ficava o padrao do GM_InitControl (2, o
     * dos guardas): o Crash 2 atravessava paredes que seguram o Snake e batia em paredes que o Snake ignora */
    w->control.seg_flag = HZD_SEG_NO_COLLIDE;
    crash2_control = &w->control;
    w->alvo = GM_AllocTarget();
    if (!w->alvo)
    {
        GV_DestroyActor(&w->actor);
        return;
    }
    /* SEEK: a bala do guarda so para em alvo com essa marca (sem ela, o tiro atravessava o Crash 2 e acertava o
     * Crash 1 atras do guarda); o lado do jogador nao acerta o Crash 2 (a bala pula o proprio lado) */
    GM_SetTarget(w->alvo, TARGET_AVAIL | TARGET_POWER | TARGET_SEEK, PLAYER_SIDE, &tamanho);
    GM_SetPowerTarget(w->alvo, POWER_DECREASE, -1, C2_VIDA, 0, &DG_ZeroVector);

    prim = DG_MakePrim(DG_PRIM_FREEPACKS | DG_PRIM_POLY_GT3, 1, 0, crash_verts, NULL);
    w->prim = prim;
    if (!prim)
    {
        GV_DestroyActor(&w->actor);
        return;
    }
    prim->packs[0] = NULL;
    prim->packs[1] = NULL;
    prim->prim_count = 0;
    prim->n_prims = 0;
    prim->callback = Crash2Callback;
    prim->userdata = w;
    prim->root = NULL;
    prim->world = DG_ZeroMatrix;
    DG_QueuePrim(prim);
    DG_GroupPrim(prim, GM_CurrentMap);

    w->anim = -1;
    C2SetAnim(w, CRASH_A_PARADO);
    w->model = crash_anims[CRASH_A_PARADO].model;
    C2Volta(w);
}

/* o corpo do Crash 1 chama a cada quadro: START no controle 2 traz o Crash 2 (e ele volta sozinho em cada fase) */
static void Crash2Entra(void)
{
    if (GM_PlayerStatus & PLAYER_SECOND_AVAILABLE)
    {
        return;
    }
    if (!crash2_ativo && (GV_PadData[1].press & PAD_START))
    {
        crash2_ativo = 1;
    }
    if (crash2_ativo && !crash2_work && GM_GameStatus >= 0)
    {
        NewCrash2();
    }
}

/*---------------------------------------------------------------------------*/
/* A tela dividida (ver o comentario do Crash 2). O canal 3D (DG_Chanls[1]) desenha so a metade do quadro; o canal
 * de fundo ganha, no fim da lista, a copia da outra metade (da outra tela) e a linha laranja do meio. */

#define TELA_MEIO 112 /* FRAME_HEIGHT / 2 */

static int     tela_dividida;     /* neste quadro */
static int     tela_estava[2];    /* o ambiente desta tela foi mudado (para devolver o normal) */
static DR_MOVE tela_copia[2];
static TILE    tela_linha[2];
static MATRIX  tela_eye, tela_eye_inv;
int            crash_dbg_tela;    /* (robo) quadros com a tela dividida */

int Crash_TelaDividida(void)
{
    return tela_dividida;
}

void Crash_TelaChanl(DG_CHANL *cp, int which)
{
    DRAWENV  env;
    DR_MOVE *mv;
    int      y;

    if (cp == DG_Chanls)
    {
        /* o canal de fundo vem primeiro: decide o quadro inteiro */
        tela_dividida = crash2_work && tela_longe && GM_GameStatus >= 0 &&
                        !(GM_GameStatus & (STATE_GAME_OVER | STATE_PADDEMO)) &&
                        GV_PauseLevel == 0 && !(GM_PlayerStatus & PLAYER_SECOND_AVAILABLE);
        return;
    }
    if (!tela_dividida)
    {
        if (tela_estava[which])
        {
            /* volta a tela inteira */
            cp->env1[which] = cp->new_env[which];
            cp->clip_rect = cp->new_clip_rect;
            tela_estava[which] = 0;
        }
        return;
    }
    tela_estava[which] = 1;
    crash_dbg_tela++;

    /* tela 0 (quadros pares) = metade de cima, camera do Crash; tela 1 = metade de baixo, camera do Crash 2 */
    y = which ? TELA_MEIO : 0;
    DG_SetDefDrawEnv(&env, which * SCREEN_WIDTH, y, FRAME_WIDTH, TELA_MEIO);
    env.ofs[0] = which * SCREEN_WIDTH + FRAME_WIDTH / 2;
    env.ofs[1] = y + TELA_MEIO / 2;
    SetDrawEnv(&cp->env1[which], &env);
    cp->clip_rect.x = -FRAME_WIDTH / 2;
    cp->clip_rect.y = -TELA_MEIO / 2;
    cp->clip_rect.w = FRAME_WIDTH;
    cp->clip_rect.h = TELA_MEIO;

    /* a outra metade vem da outra tela (desenhada no quadro anterior); copia de VRAM, sem ambiente de desenho */
    mv = &tela_copia[which];
    setlen(mv, 5);
    mv->code[0] = 0x01000000;
    mv->code[1] = 0x80000000;
    mv->code[2] = ((which ? 0 : TELA_MEIO) << 16) | ((1 - which) * SCREEN_WIDTH); /* origem: y, x */
    mv->code[3] = ((which ? 0 : TELA_MEIO) << 16) | (which * SCREEN_WIDTH);       /* destino */
    mv->code[4] = (TELA_MEIO << 16) | FRAME_WIDTH;

    /* a linha do meio, laranja */
    setTile(&tela_linha[which]);
    setXY0(&tela_linha[which], 0, TELA_MEIO - 1);
    setWH(&tela_linha[which], FRAME_WIDTH, 2);
    setRGB0(&tela_linha[which], 255, 120, 0);
}

/* no fim da lista do canal de fundo (depois do HUD, que esta no canal 2): a copia e a linha */
void Crash_TelaCopia(u_long *ot_fim, void *env2, int which)
{
    catPrim(ot_fim, &tela_copia[which]);
    catPrim(&tela_copia[which], &tela_linha[which]);
    catPrim(&tela_linha[which], env2);
}

/* nos quadros do Crash 2 o canal 3D ordena com a camera do Crash levada ate ele (mesmo angulo e distancia); nos dois,
 * a camera abre 30% (com meia altura de tela, os Crashes ficavam encostados nas bordas) */
static short tela_zoom;

void Crash_TelaCamera(int antes)
{
    DG_CHANL *cp = &DG_Chanls[1];
    VECTOR    t;

    if (!tela_dividida || !crash2_work || !GM_PlayerControl)
    {
        return;
    }
    if (antes)
    {
        tela_zoom = cp->screen;
        cp->screen = cp->screen * 7 / 10;
    }
    else
    {
        cp->screen = tela_zoom;
    }
    if (GV_Clock == 0)
    {
        return;
    }
    if (antes)
    {
        tela_eye = cp->eye;
        tela_eye_inv = cp->eye_inv;
        cp->eye.t[0] += crash2_work->control.mov.vx - GM_PlayerControl->mov.vx;
        cp->eye.t[1] += crash2_work->control.mov.vy - GM_PlayerControl->mov.vy;
        cp->eye.t[2] += crash2_work->control.mov.vz - GM_PlayerControl->mov.vz;
        t.vx = -cp->eye.t[0];
        t.vy = -cp->eye.t[1];
        t.vz = -cp->eye.t[2];
        ApplyMatrixLV(&cp->eye_inv, &t, (VECTOR *)cp->eye_inv.t);
    }
    else
    {
        cp->eye = tela_eye;
        cp->eye_inv = tela_eye_inv;
    }
}

/* a vida do Crash 2: uma barra azul no canto da metade dele (so nos quadros dele: a outra metade e copiada) */
static TILE c2_fundo[2], c2_barra[2];

static void Crash2Vida(int vida)
{
    u_long *ot;
    TILE   *f, *b;
    int     y;

    if (tela_dividida)
    {
        if (GV_Clock != 1)
        {
            return;
        }
        y = TELA_MEIO + 10;
    }
    else
    {
        y = 52; /* tela inteira (teste 14): embaixo da vida e do oxigenio do Crash 1 */
    }
    ot = DG_ChanlOTag(1);
    f = &c2_fundo[GV_Clock];
    b = &c2_barra[GV_Clock];
    setTile(f);
    setXY0(f, 14, y);
    setWH(f, 68, 8);
    setRGB0(f, 0, 0, 0);
    setTile(b);
    setXY0(b, 16, y + 2);
    setWH(b, vida > 0 ? 64 * vida / C2_VIDA : 0, 4);
    setRGB0(b, 40, 120, 255);
    addPrim(ot, b);
    addPrim(ot, f);
}

/* Os guardas so procuram o Snake: a visao, a mira, o soco e o tiro deles leem GM_PlayerPosition e GM_PlayerStatus.
 * Enquanto um guarda pensa (watcher.c chama antes e depois de EnemyActionMain), o Crash 2 pode ser o "jogador" dele:
 * a posicao e o estado (em pe, fora da caixa e do duto) sao trocados e devolvidos logo depois. Quem ele procura: o
 * que ja esta vendo; sem ver ninguem, quem esta na frente dele (no angulo da visao) e, empatado, o mais perto (com
 * 1,5 m de folga para nao ficar trocando). Preso no braco do Snake, so o Snake. Nas 33 fases relocadas o codigo do
 * guarda e o de 1999: la ele so ve o Crash 1. Gambiarra? Talvez. */
#define GUARDA_FOLGA 1500

char           crash_guarda_alvo[8]; /* por guarda (indice no comando): 1 = procura o Crash 2 (o robo le) */
static SVECTOR guarda_pos;
static int     guarda_status;

static int NaFrente(WatcherWork *w, SVECTOR *pos)
{
    SVECTOR d;

    GV_SubVec3(pos, &w->control.mov, &d);
    return GV_VecLen3(&d) < 500 || GV_DiffDirAbs(w->vision.facedir, GV_VecDir2(&d)) < w->vision.angle;
}

void Crash_GuardaMira(void *guarda)
{
    WatcherWork *w = guarda;
    char        *alvo = &crash_guarda_alvo[w->field_B78 & 7];
    SVECTOR     *c2;
    int          f1, f2, d1, d2;

    guarda_trocou = 0;
    if (!crash2_work || crash2_work->morto || GM_GameStatus < 0 || w->target->captured)
    {
        *alvo = 0;
        return;
    }
    c2 = &crash2_work->control.mov;
    if (w->vision.field_B92 != 2) /* nao esta vendo quem procura: escolhe de novo */
    {
        f1 = NaFrente(w, &GM_PlayerPosition);
        f2 = NaFrente(w, c2);
        if (f1 != f2)
        {
            *alvo = f2;
        }
        else
        {
            d1 = GV_DiffVec3(&w->control.mov, &GM_PlayerPosition);
            d2 = GV_DiffVec3(&w->control.mov, c2);
            if (*alvo ? d1 + GUARDA_FOLGA < d2 : d2 + GUARDA_FOLGA < d1)
            {
                *alvo ^= 1;
            }
        }
    }
    if (*alvo)
    {
        guarda_pos = GM_PlayerPosition;
        guarda_status = GM_PlayerStatus;
        GM_PlayerPosition = *c2;
        GM_PlayerStatus &= ~(PLAYER_CB_BOX | PLAYER_HIDDEN | PLAYER_INTRUDE | PLAYER_SQUAT | PLAYER_GROUND);
        guarda_trocou = 1;
    }
}

void Crash_GuardaVolta(void)
{
    if (guarda_trocou)
    {
        GM_PlayerPosition = guarda_pos;
        GM_PlayerStatus = guarda_status;
        guarda_trocou = 0;
    }
}

void Crash2_Fase(void)
{
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
