/* Quartz Quadrant (R5) deformation from SCR51A-D, SCR52A-D and SCR53C/D.C.
   Rows come from the checked scroll IR (tools/scroll/R5/ir) through
   src/background_r5_tables.inc; the line walk is each scroll()'s render:
   zonescrsetsub0 over 29 rows, or SCR51D/52D/53D's tail ramp below row 40. */
#include <stdint.h>
#include <string.h>
#include "background.h"
#include "background_r5.h"

/* op 1: layer a; op 2: group k of line builder bi. */
typedef struct { uint8_t op, a, bi, k; } r5_row;
/* 68k line builder: d2 = ext.l(to.w - from.w) * mul; divu.w #div,d2; ext.l d2;
   d2 *= scale; G groups from d3 = from.w | fraction << 16. */
typedef struct { uint8_t a, b; uint16_t mul, div, scale; uint8_t G; } r5_builder;
typedef struct {
    uint16_t entries; uint8_t mask, kind, tail, src, post; uint8_t terms[3][2];
    uint8_t nb; r5_builder builder[2];
    const r5_row *rows; const uint8_t *wrttbl;
} r5_body;
typedef struct {
    const char *name; uint8_t seed; uint16_t rate[3]; uint8_t init[3][2][2]; uint16_t enkei[2]; r5_body body[2];
} r5_program;
#include "background_r5_tables.inc"

static const r5_program *r5_program_at(unsigned id){return id<12&&r5_programs[id].name?&r5_programs[id]:0;}
int scd_r5_valid(unsigned id){return r5_program_at(id)!=0;}

enum { R5_EV_ENKEI, R5_EV_COLREV, R5_EV_BOSS };
#define R5_LOG 48
/* enkei/layers: live state; show_*: what this update's scroll() used (the
   frame on screen), kept apart from an enkeichg that ran after it. */
static struct {
    int ready,enkei,show_enkei,hz,show_hz,vy,show_vy,last_cy,skip,px,cx,cy,hx,hy,colrev,boss,base_colrev,base_boss;
    unsigned tick,checked,nlog;
    int32_t layers[3],show[3];
    /* hscrollwork rows the current variant does not write keep what the
       other variant last wrote there (0 after a reset: BSS). */
    int16_t stale[128];
    struct { uint32_t tick; uint8_t kind, value; } log[R5_LOG];
} r5={0};

static void r5_log(uint32_t tick,unsigned kind,int value){
    if(r5.nlog==R5_LOG){ /* keep the newest events */
        for(unsigned i=1;i<R5_LOG;i++)r5.log[i-1]=r5.log[i];
        r5.nlog--;
    }
    r5.log[r5.nlog].tick=tick;r5.log[r5.nlog].kind=(uint8_t)kind;r5.log[r5.nlog].value=(uint8_t)value;r5.nlog++;
}
static void r5_show(void){r5.show_enkei=r5.enkei;r5.show_hz=r5.hz;r5.show_vy=r5.vy;for(unsigned i=0;i<3;i++)r5.show[i]=r5.layers[i];}
/* scrbinit: each layer is a sum of m*((uint16)x >> s), stored in .w.h. */
static void r5_scrbinit(const r5_program *p,int x,int32_t *layers){
    for(unsigned i=0;i<3;i++){
        uint32_t v=0;
        for(unsigned t=0;t<2;t++)v+=(uint32_t)p->init[i][t][1]*((uint32_t)(uint16_t)x>>p->init[i][t][0]);
        layers[i]=(int32_t)((uint32_t)(uint16_t)v<<16);
    }
}
static int r5_enkei_for(const r5_program *p,int player_x){
    if(!p->enkei[0])return 0;
    int16_t px=(int16_t)player_x;
    return px<=(int16_t)p->enkei[0]?0:px<=(int16_t)p->enkei[1]?1:2;
}
static void r5_init(const r5_program *p){
    /* GAME5.C game_init: enkeino = 0, then enkeichg() from the player start. */
    int e=r5.px==-32768?0:r5_enkei_for(p,r5.px);
    r5.enkei=e;r5.skip=0;r5.ready=1;r5.checked=0;r5.hx=r5.cx;r5.hy=r5.cy;
    r5_scrbinit(p,r5.cx,r5.layers);r5_show();
    if(e)r5_log(0,R5_EV_ENKEI,e);
}
/* Saturn builds (Makefile SCD_REQUIRE_ZONE_TERRAIN) never drop the zone art silently. */
#if defined(SCD_REQUIRE_ZONE_TERRAIN) && !__has_include("qq_terrain.inc")
#error "assets/generated/qq_terrain.inc is missing (run python3 tools/qq_terrain_assets.py)"
#endif
/* Layout state persists across frames but never across a zone/era reset. */
#define R5_REDRAW_ROWS SCD_BACKGROUND_R5_FULL_REDRAW_SLOTS
static uint64_t r5_redraw;
#if __has_include("qq_terrain.inc")
#define R5_PROBE_CHUNKS 64
static int r5_applied=-1; /* id*2+odd whose layout the chunks hold */
static uint16_t r5_probe[R5_PROBE_CHUNKS];
#endif
/* QA-visible R5 event ledger.  0 is the magic; 1 actual enkeichg changes;
   2 camera-line deferrals; 3 mapwrtb skip deferrals; 4 latest tick;
   5 show_enkei; 6 live enkei; 7 transition -1 holds; 8 transition 64
   redraws; 9 state (0 none, 1 changed, 2 held, 3 redrawn, 4 unchanged).
   The last three fields associate the required -1 -> 64 pair with an actual
   enkeichg, not merely with level initialization. */
volatile uint32_t scd_r5_event_mailbox[10];
static unsigned r5_event_pending;
#define R5_EVENT_MAGIC 0x52354556u /* 'R5EV' */
static void r5_event_reset(void){
    for(unsigned i=0;i<10;i++)scd_r5_event_mailbox[i]=0;
    scd_r5_event_mailbox[0]=R5_EVENT_MAGIC;
    r5_event_pending=0;
}
void scd_r5_reset(int x){
    r5_redraw=0;
#if __has_include("qq_terrain.inc")
    r5_applied=-1;
#endif
    r5.ready=0;r5.cx=x;r5.tick=0;r5.hz=r5.vy=0;
    for(unsigned i=0;i<128;i++)r5.stale[i]=0;r5.nlog=0;r5.px=-32768;r5.enkei=0;
    r5.base_colrev=r5.colrev;r5.base_boss=r5.boss;
    r5_event_reset();
}
static void r5_keep_rows(const r5_program *p,int from,int to);
void scd_r5_set_enkei(unsigned id,int enkei,int x){
    const r5_program *p=r5_program_at(id);if(!p)return;
    if(r5.ready)r5_keep_rows(p,r5.enkei,enkei);
    r5.ready=1;r5.enkei=enkei;r5.cx=x;r5.skip=0;r5.checked=r5.tick;r5_scrbinit(p,x,r5.layers);r5_show();
}
int scd_r5_enkei(void){return r5.show_enkei;}
const int32_t *scd_r5_layers(void){return r5.show;}
void scd_r5_set_hz(int hz){r5.hz=r5.show_hz=(int16_t)hz;}
void scd_r5_set_colrev(int on){on=on!=0;if(on!=r5.colrev){r5.colrev=on;r5_log(r5.tick+1,R5_EV_COLREV,on);}}
void scd_r5_set_boss(int on){on=on!=0;if(on!=r5.boss){r5.boss=on;r5_log(r5.tick+1,R5_EV_BOSS,on);}}

/* GAME5.C game(): scroll(), clchgctr(), then enkeichg() unless the previous
   frame's enkeichg changed the map (mapwrt_cnt).  enkeichg returns while
   scrflaga.b.h is set (this frame's camera crossed a 16-pixel line); it reads
   the player X the update left, so it runs at the first display call after
   the update (or at the next update when none came). */
static void r5_enkeichg(const r5_program *p){
    int crossed=((r5.hx^r5.cx)&16)||((r5.hy^r5.cy)&16);
    r5.hx=r5.cx;r5.hy=r5.cy;r5.checked=r5.tick;
    scd_r5_event_mailbox[4]=r5.tick;
    if(r5.skip){r5.skip=0;scd_r5_event_mailbox[3]++;return;}
    if(crossed){scd_r5_event_mailbox[2]++;return;}
    if(!p->enkei[0]||r5.px==-32768)return;
    int e=r5_enkei_for(p,r5.px);
    if(e==r5.enkei)return;
    r5_keep_rows(p,r5.enkei,e);
    r5.enkei=e;r5.skip=1;
    r5_scrbinit(p,r5.cx,r5.layers);
    r5_log(r5.tick,R5_EV_ENKEI,e);
    scd_r5_event_mailbox[1]++;r5_event_pending=1;scd_r5_event_mailbox[9]=1;
}
void scd_r5_step(unsigned id,int x){
    const r5_program *p=r5_program_at(id);if(!p)return;
    if(!r5.ready)r5_init(p);
    else if(r5.tick&&r5.checked!=r5.tick)r5_enkeichg(p);
    /* scroll(): scrollz/c/b_h(scra_hz * C), scra_hz = camera delta << 8. */
    int32_t d=(int32_t)(int16_t)(x-r5.cx)*256;
    r5.hz=(int16_t)d;
    for(unsigned i=0;i<3;i++)r5.layers[i]=(int32_t)((uint32_t)r5.layers[i]+(uint32_t)(d*(int32_t)p->rate[i]));
    r5.cx=x;r5.tick++;r5_show();
}

static const r5_body *r5_body_at(const r5_program *p){return &p->body[r5.show_enkei&1];}
int scd_r5_background_y(unsigned id,int camera_y,int player_x){
    const r5_program *p=r5_program_at(id);if(!p)return camera_y/8;
    if(!r5.ready){r5.px=player_x;r5.cy=camera_y;r5_init(p);}
    else if(r5.tick&&r5.checked!=r5.tick){
        r5.vy=r5.show_vy=(int16_t)(camera_y-r5.last_cy);
        r5.px=player_x;r5.cy=camera_y;r5_enkeichg(p);
    }
    r5.last_cy=camera_y;
    const r5_body *b=r5_body_at(p);
    uint32_t v=(uint16_t)camera_y,s=0;
    if(b->src==32)v<<=16;
    for(unsigned i=0;i<3;i++)s+=(uint32_t)b->terms[i][1]*(v>>b->terms[i][0]);
    return (int16_t)(s>>b->post);
}

static int r5_layer(unsigned i,int x,const int32_t *layers){
    if(!i)return (int16_t)x;
    return (int16_t)(layers[i-1]>>16);
}
static const int32_t *r5_layers_or(const r5_program *p,int x,const int32_t *layers,int32_t *tmp){
    if(layers)return layers;
    if(r5.ready)return r5.show;
    r5_scrbinit(p,x,tmp);return tmp;
}
/* The builders' per-group steps and the accumulator fraction each starts
   from: the first gets d3's high word from scroll() (ext.l(scra_hz) << seed),
   each later one the fraction the previous left after its G additions. */
typedef struct { int32_t step[2]; uint32_t frac[2]; } r5_steps;
static void r5_builders(const r5_program *p,const r5_body *b,int x,const int32_t *layers,int hz,r5_steps *st){
    uint32_t frac;
    if(p->seed)frac=(uint32_t)(((int32_t)(int16_t)hz*(1<<p->seed))>>16)&0xffffu;
    else{
        /* SCR51D/52D/53D: d3 = ror.l #8 of scroll_v's camera Y delta when
           it moved the camera; otherwise a register earlier code left (0 here). */
        uint32_t v=(uint32_t)r5.show_vy<<16;
        frac=((v>>8)|(v<<24))>>16;
    }
    for(unsigned i=0;i<b->nb;i++){
        const r5_builder *u=&b->builder[i];
        int32_t dividend=(int32_t)(int16_t)(r5_layer(u->b,x,layers)-r5_layer(u->a,x,layers))*u->mul;
        uint32_t q=(uint32_t)dividend/u->div;
        /* divu.w: a quotient over 16 bits leaves the dividend unchanged */
        int16_t q16=(int16_t)(q>0xffffu?(uint32_t)dividend:q);
        st->step[i]=(int32_t)q16*u->scale;
        st->frac[i]=frac;
        frac=(frac+(uint32_t)st->step[i]*u->G)&0xffffu;
    }
}
static int r5_row_x(const r5_body *b,const r5_steps *st,unsigned entry,int x,const int32_t *layers){
    /* hscrollwork rows past the ones scroll() writes: 0 (tools/scroll/ir.md). */
    if(entry>=b->entries)return entry<128?r5.stale[entry]:0;
    const r5_row *r=&b->rows[entry];
    if(r->op==1)return r5_layer(r->a,x,layers);
    const r5_builder *u=&b->builder[r->bi];
    uint32_t acc=((uint32_t)(uint16_t)r5_layer(u->a,x,layers)<<16)|st->frac[r->bi];
    return (int16_t)((acc+(uint32_t)st->step[r->bi]*r->k)>>16);
}
static void r5_keep_rows(const r5_program *p,int from,int to){
    const r5_body *o=&p->body[from&1],*n=&p->body[to&1];
    if(o==n)return;
    r5_steps st;r5_builders(p,o,r5.cx,r5.show,r5.show_hz,&st);
    for(unsigned r=n->entries;r<o->entries&&r<128;r++)r5.stale[r]=(int16_t)r5_row_x(o,&st,r,r5.cx,r5.show);
}
void scd_r5_set_vy(int dy){r5.vy=r5.show_vy=(int16_t)dy;}
int scd_r5_raster_x(unsigned id,int x,const int32_t *layers,int y){
    const r5_program *p=r5_program_at(id);if(!p)return x/8;
    int32_t tmp[3];layers=r5_layers_or(p,x,layers,tmp);
    const r5_body *b=r5_body_at(p);
    r5_steps st;r5_builders(p,b,x,layers,r5.show_hz,&st);
    unsigned line=(unsigned)(uint16_t)y;
    if(b->kind&&((line>>3)&b->mask)>=40){
        /* tail ramp from row 40 (the window starting above it) */
        int from=r5_layer(b->tail,x,layers);
        int32_t step=(int32_t)(int16_t)(x-from)*256;
        return (int16_t)((((uint32_t)(uint16_t)from<<16)+(uint32_t)(step*(int32_t)((line&(b->mask*8+7))-320)))>>16);
    }
    return r5_row_x(b,&st,(line>>3)&b->mask,x,layers);
}

void scd_r5_lines_layers(unsigned id,int x,const int32_t *layers,int top,
                         int32_t *background,int32_t *foreground,unsigned count){
    const r5_program *p=r5_program_at(id);if(!p)return;
    int32_t tmp[3];layers=r5_layers_or(p,x,layers,tmp);
    const r5_body *b=r5_body_at(p);
    r5_steps st;r5_builders(p,b,x,layers,r5.show_hz,&st);
    unsigned row=((unsigned)(uint16_t)top>>3)&b->mask,j=(unsigned)top&7,rows=29,n=0;
    int32_t fg=(int32_t)(x&511)*65536;
    if(count>232)count=232;
    if(b->kind){
        /* SCR51D/52D/53D: rows down to row 39, then the ramp from scrb. */
        rows=row<=39?(39-row>28?28:39-row)+1:0;
    }
    /* zonescrsetsub0: row `row` from line top&7, then whole rows. */
    for(unsigned r=0;r<rows&&n<count;r++,j=0){
        int v=r5_row_x(b,&st,row+r,x,layers);
        int32_t w=(int32_t)(v&511)*65536;
        for(;j<8&&n<count;j++,n++){background[n]=w;if(foreground)foreground[n]=fg;}
    }
    if(n<count){
        /* Tail ramp: hi(65536*scrb + k*(camera - scrb)*256) per line.  (Programs
           without one never reach here: 29 rows cover 225+ lines.) */
        int from=r5_layer(b->tail?b->tail:1,x,layers);
        uint32_t acc=(uint32_t)(uint16_t)from<<16;
        uint32_t step=(uint32_t)((int32_t)(int16_t)(x-from)*256);
        for(;n<count;n++,acc+=step){
            background[n]=(int32_t)(((int16_t)(acc>>16))&511)*65536;
            if(foreground)foreground[n]=fg;
        }
    }
}

/* The plane row a BG line shows is drawn by one layer: scrollwrtb reads
   z81awrttbl[(y/16)&127 + 1] (z81awrttbl2 while enkeino is odd in SCR51A/52A);
   0 draws x 0 over all 512 pixels, 2/4/6 draw around scrb/scrc/scrz. */
int scd_r5_row_layer(unsigned id,int y){
    const r5_program *p=r5_program_at(id);if(!p)return -1;
    return r5_body_at(p)->wrttbl[(((unsigned)(uint16_t)y/16)&127)+1]/2;
}
int scd_r5_row_start(unsigned id,int x,const int32_t *layers,int y){
    const r5_program *p=r5_program_at(id);if(!p)return 0;
    int layer=scd_r5_row_layer(id,y);
    if(layer<=0)return 0;
    int32_t tmp[3];layers=r5_layers_or(p,x,layers,tmp);
    int bx=r5_layer((unsigned)layer,x,layers);
    return (bx>=0?bx/8:-((-bx+7)/8))-11;
}

/* COL5A-D clchgctr/colchgsub (src/background_r5_palette.inc).  colchgsub
   advances the timer/counter pointers on every call, so each call site owns
   one slot; COL5D's bossflag branch skips its slot.  enkeichg's colorset2
   writes zone5color0/1 into 16-63 after that frame's clchgctr. */
typedef struct { uint8_t adr, tate, yoko, time; const uint16_t *c; } r5_script;
#include "background_r5_palette.inc"
static struct { int id; unsigned tick; uint8_t tim[3],cnt[3],set[64]; uint16_t color[64]; } r5_pal={-1,0,{0},{0},{0},{0}};
static void r5_colchg(unsigned slot,const r5_script *s){
    uint8_t *t=&r5_pal.tim[slot],*n=&r5_pal.cnt[slot];
    if((int8_t)--*t>=0)return;
    *t=s->time;
    unsigned c=*n+1u;if(c>=s->tate)c=0;
    *n=(uint8_t)c;
    for(unsigned i=0;i<s->yoko;i++){r5_pal.color[s->adr+i]=s->c[c*s->yoko+i];r5_pal.set[s->adr+i]=1;}
}
static void r5_clchgctr(unsigned letter,int enkei,int colrev,int boss){
    switch(letter){
    case 0:
        r5_colchg(0,colrev?&r5_A_colchg53:&r5_A_colchg50);
        r5_colchg(1,enkei&1?&r5_A_colchg52:&r5_A_colchg51);
        break;
    case 1:
        r5_colchg(0,colrev?&r5_B_colchg52:&r5_B_colchg50);
        if(!(enkei&1))r5_colchg(1,&r5_B_colchg51);
        break;
    case 2:
        if(!boss)r5_colchg(0,colrev?&r5_C_colchg51:&r5_C_colchg50);
        break;
    default:
        if(!boss)r5_colchg(0,colrev?&r5_D_colchg53:&r5_D_colchg50);
        if(enkei&1){r5_colchg(1,&r5_D_colchg51);r5_colchg(2,&r5_D_colchg52);}
    }
}
static void r5_zone(unsigned letter,int enkei){
    static const uint16_t *const zone[4][2]={{r5_A_zone0,r5_A_zone1},{r5_B_zone0,r5_B_zone1},
                                             {r5_C_zone0,r5_C_zone1},{r5_D_zone0,r5_D_zone1}};
    const uint16_t *z=zone[letter][enkei&1];
    for(unsigned i=0;i<48;i++){r5_pal.color[16+i]=z[i];r5_pal.set[16+i]=1;}
}
void scd_r5_palette(unsigned id,unsigned frame,uint16_t *out){
    if(!r5_program_at(id))return;
    unsigned letter=id&3;
    if(r5_pal.id!=(int)id||frame<r5_pal.tick){
        for(unsigned i=0;i<64;i++)r5_pal.set[i]=0;
        for(unsigned i=0;i<3;i++)r5_pal.tim[i]=r5_pal.cnt[i]=0;
        r5_pal.id=(int)id;r5_pal.tick=0;
        for(unsigned e=0;e<r5.nlog;e++)
            if(r5.log[e].kind==R5_EV_ENKEI&&r5.log[e].tick==0)r5_zone(letter,r5.log[e].value);
    }
    while(r5_pal.tick<frame){
        unsigned f=++r5_pal.tick;
        int enkei=0,colrev=r5.base_colrev,boss=r5.base_boss,after=-1;
        for(unsigned e=0;e<r5.nlog;e++){
            uint32_t t=r5.log[e].tick;
            if(r5.log[e].kind==R5_EV_ENKEI){if(t<f)enkei=r5.log[e].value;else if(t==f)after=r5.log[e].value;}
            else if(t<=f){if(r5.log[e].kind==R5_EV_COLREV)colrev=r5.log[e].value;else boss=r5.log[e].value;}
        }
        r5_clchgctr(letter,enkei,colrev,boss);
        if(after>=0)r5_zone(letter,after);
    }
    for(unsigned i=0;i<64;i++)if(r5_pal.set[i])out[i]=r5_pal.color[i];
}

/* Runtime background art and enkeino layouts (tools/qq_terrain_assets.py ->
   assets/generated/qq_terrain.inc, retail data): enkeichg's ChangeTileBmp run
   and mapset2 blocks, and art the programs load past their Nemesis art. */
#if __has_include("qq_terrain.inc")
typedef struct { uint8_t row, col, v0, v1; } qq_cell;
/* Chunk `host` holds data[0] (the pack's) or, while enkeino is odd, data[1]:
   a chunk past the pack's table that the enkeino layout names. */
typedef struct { uint8_t host; const uint8_t *data[2]; } qq_chunk;
typedef struct { uint16_t first, count, limit; const uint8_t *art[2]; uint16_t ncells; const qq_cell *cells;
                 uint16_t nchunks; const qq_chunk *chunks; } qq_terrain;
#include "qq_terrain.inc"
static const qq_terrain *qq_at(unsigned id){return id<12&&qq_terrain_programs[id].count?&qq_terrain_programs[id]:0;}
#else
typedef struct { uint16_t first, count, limit; const uint8_t *art[2]; uint16_t ncells; const void *cells; } qq_terrain;
static const qq_terrain *qq_at(unsigned id){(void)id;return 0;}
#endif
int scd_r5_tile_run(unsigned id,unsigned *first,unsigned *count,const uint8_t **art){
    const qq_terrain *t=qq_at(id);if(!t)return -1;
    *first=t->first;*count=t->count;*art=t->art[r5.show_enkei&1];
    return r5.show_enkei&1;
}
unsigned scd_r5_tile_limit(unsigned id,unsigned tiles){
    const qq_terrain *t=qq_at(id);
    return t&&t->limit>tiles?t->limit:tiles;
}
const uint8_t *scd_r5_art(unsigned id,int enkei,unsigned tile){
    const qq_terrain *t=qq_at(id);
    if(!t||tile<t->first||tile>=t->first+t->count)return 0;
    return t->art[enkei&1]+(tile-t->first)*32u;
}
int scd_r5_map_cell(unsigned id,int enkei,int row,int col,int value){
#if __has_include("qq_terrain.inc")
    const qq_terrain *t=qq_at(id);
    if(t)for(unsigned i=0;i<t->ncells;i++)
        if(t->cells[i].row==row&&t->cells[i].col==col)return enkei&1?t->cells[i].v1:t->cells[i].v0;
#else
    (void)id;(void)enkei;(void)row;(void)col;
#endif
    return value;
}
const uint8_t *scd_r5_chunk(unsigned id,int enkei,unsigned chunk){
#if __has_include("qq_terrain.inc")
    const qq_terrain *t=qq_at(id);
    if(t)for(unsigned i=0;i<t->nchunks;i++)if(t->chunks[i].host==chunk)return t->chunks[i].data[enkei&1];
#else
    (void)id;(void)enkei;(void)chunk;
#endif
    return 0;
}
int scd_r5_map_update(unsigned id,uint8_t *map,uint8_t *chunks,int *world_rows,int top_row){
    int n=0;
#if __has_include("qq_terrain.inc")
    const qq_terrain *t=qq_at(id);
    if(t&&(t->ncells||t->nchunks)){
        /* enkeichg runs after this display's scroll snapshot.  On its switch
           frame show_enkei still names the layout on screen, while enkei is
           already the next one; wait for the following snapshot rather than
           clearing the event as an unchanged map. */
        if(r5_event_pending==1&&r5.show_enkei!=r5.enkei){
            scd_r5_event_mailbox[5]=r5.show_enkei;scd_r5_event_mailbox[6]=r5.enkei;
            return 0;
        }
        int odd=r5.show_enkei&1,dirty=0;
        for(unsigned i=0;i<t->ncells;i++){
            const qq_cell *c=&t->cells[i];uint8_t v=odd?c->v1:c->v0;
            if(map[c->row*64+c->col]!=v){map[c->row*64+c->col]=v;dirty=1;}
        }
        int key=(int)id*2+odd,held=r5_applied==key;
        for(unsigned i=0;held&&i<t->nchunks;i++){
            const qq_chunk *c=&t->chunks[i];const uint8_t *d=chunks+(c->host-1u)*512u;
            if(i<R5_PROBE_CHUNKS?r5_probe[i]<512&&d[r5_probe[i]]!=c->data[odd][r5_probe[i]]:memcmp(d,c->data[odd],512)!=0)held=0;
        }
        if(!held){
            for(unsigned i=0;i<t->nchunks;i++){
                const qq_chunk *c=&t->chunks[i];uint8_t *d=chunks+(c->host-1u)*512u;
                if(memcmp(d,c->data[odd],512)){memcpy(d,c->data[odd],512);dirty=1;}
                if(i<R5_PROBE_CHUNKS){unsigned k=0;while(k<512&&c->data[0][k]==c->data[1][k])k++;r5_probe[i]=(uint16_t)k;}
            }
            r5_applied=key;
        }
        /* mapset2 rewrites whole 256-pixel block rows: every BG tile row of
           them may change. */
        if(dirty){
            r5_redraw=~0ull;
            if(r5_event_pending==1){r5_event_pending=2;scd_r5_event_mailbox[7]++;scd_r5_event_mailbox[9]=2;}
            scd_r5_event_mailbox[5]=r5.show_enkei;scd_r5_event_mailbox[6]=r5.enkei;
            return -1; /* mapwrtb redraws on the next frame */
        }
        if(r5_event_pending==1){r5_event_pending=0;scd_r5_event_mailbox[9]=4;}
    }
#else
    (void)id;(void)map;(void)chunks;
#endif
    for(int pass=0;pass<2&&r5_redraw&&n<R5_REDRAW_ROWS;pass++)
        for(int r=0;r<(pass?64:30)&&n<R5_REDRAW_ROWS;r++){
            unsigned slot=pass?(unsigned)r:((unsigned)(top_row+r)&63u);
            if(!(r5_redraw>>slot&1))continue;
            r5_redraw&=~(1ull<<slot);world_rows[slot]=-10000;n++;
        }
    if(n==R5_REDRAW_ROWS&&r5_event_pending==2){r5_event_pending=0;scd_r5_event_mailbox[8]++;scd_r5_event_mailbox[9]=3;}
    scd_r5_event_mailbox[5]=r5.show_enkei;scd_r5_event_mailbox[6]=r5.enkei;
    return n;
}
