/* Wacky Workbench (R6) deformation from SCR61A-D, SCR62A-D and SCR63C/D.C.
   Rows come from the checked scroll IR (tools/scroll/R6/ir) through
   src/background_r6_tables.inc; the line walk is zonescrsetsub0. */
#include <stdint.h>
#include "background_r6.h"

typedef struct { uint8_t op, layer; int16_t k; int32_t p, m, frac; } r6_row;
typedef struct { const char *name; uint16_t entries; const r6_row *rows; const uint8_t *wrttbl; } r6_program;
#include "background_r6_tables.inc"

static const r6_program *r6_program_at(unsigned id){return id<12&&r6_programs[id].rows?&r6_programs[id]:0;}
/* Table-free (other zones call it; the programs live in the R6 zone overlay):
   ids 0-7 and 10-11. tools/test_r6_scroll.py checks it against r6_programs. */
int scd_r6_valid(unsigned id){return id<12&&(0xcffu>>id&1u);}

void scd_r6_layers_reset(int x,int32_t *l){
    unsigned u=(uint16_t)x;
    l[0]=(int32_t)((u>>4)*3)<<16;l[1]=(int32_t)(u>>1)<<16;l[2]=(int32_t)(u>>2)<<16;l[3]=0;
}
void scd_r6_layers_step(int dx,int32_t *l){
    int32_t hz=(int32_t)(int16_t)(dx*256); /* scra_hz, 8.8 */
    l[0]=(int32_t)((uint32_t)l[0]+(uint32_t)(hz*48));
    l[1]=(int32_t)((uint32_t)l[1]+((uint32_t)hz<<7));
    l[2]=(int32_t)((uint32_t)l[2]+((uint32_t)hz<<6));
    /* Retail R61B/R62B scroll() leaves hz*48's partial d3 = hz*32 in the
       register z81aline then loads scrb into with move.w: its high word is
       the radwk fraction the C reads uninitialised. */
    l[3]=(int32_t)(((uint32_t)(hz*32)>>16)&65535u);
}

/* Layer 0 is the camera; 1-3 are scrb/scrc/scrz words (w.h). */
static int r6_layer_x(unsigned i,int x,const int32_t *layers){
    if(!i)return (int16_t)x;
    if(layers)return (int16_t)(layers[i-1]>>16);
    static const int16_t C[4]={0,48,128,64};
    int32_t v=C[i]*x;return (int16_t)(v>=0?v/256:-((-v+255)/256));
}
/* hscrollwork entry as a background X (the table holds its negation). Past
   the entries scroll() writes, hscrollwork keeps 0. */
static int r6_row_x(const r6_program *p,unsigned entry,int x,const int32_t *layers){
    if(entry>=p->entries)return 0;
    const r6_row *r=&p->rows[entry];
    int from=r6_layer_x(r->layer,x,layers);
    if(r->op==1)return from;
    int32_t d=(int16_t)((int16_t)x-from); /* sub.w */
    if(r->op==2){
        /* z6?aline, as retail 68000 code (R61C 0x2ab4): muls.w (256 - cos) by
           the word difference, lsr.l #8, add.w. The C's (unsigned short)
           narrowing in SCR61C/62A/62C/62D/63D is not what retail runs. */
        return from+(int32_t)((uint32_t)((int32_t)r->k*d)>>8);
    }
    /* z81aline, as retail 68000 code (R61B 0x2a98): sub.w, ext.l, asl #7,
       divu.w #17 (overflow leaves the dividend), ext.l, asl #9; radwk is
       scrb:fraction and steps once per entry pair. The C's signed divide
       and uninitialised fraction differ from retail. */
    uint32_t n=(uint32_t)(int32_t)(int16_t)d<<7,u=n/17u;
    int32_t q=(int16_t)(uint16_t)(u>65535u?n:u);
    uint32_t frac=layers?(uint32_t)layers[3]&65535u:0u;
    uint32_t acc=((uint32_t)(uint16_t)from<<16)+frac+(uint32_t)r->m*(uint32_t)q;
    return (int16_t)(acc>>16);
}

int scd_r6_background_y(unsigned id,int camera_y){
    if(!r6_program_at(id))return camera_y/8;
    return (int)((unsigned)(uint16_t)camera_y>>2); /* scroll: scrollb_v((u16)scra_v >> 2) */
}
int scd_r6_raster_x(unsigned id,int x,const int32_t *layers,int y){
    const r6_program *p=r6_program_at(id);if(!p)return x/8;
    return r6_row_x(p,((unsigned)(uint16_t)y>>3)&127,x,layers);
}
void scd_r6_lines_layers(unsigned id,int x,const int32_t *layers,int top,
                         int32_t *background,int32_t *foreground,unsigned count){
    const r6_program *p=r6_program_at(id);if(!p)return;
    /* zonescrsetsub0(scrb_v, 29, ..): 30 rows from hscrollwork[(bgy & 1016) >> 3],
       the first from line bgy & 7; the walk does not re-mask the row. */
    unsigned entry=((unsigned)(uint16_t)top&1016u)>>3,v=(unsigned)top&7u;
    int value=r6_row_x(p,entry++,x,layers);
    if(count>232)count=232;
    for(unsigned n=0;n<count;n++){
        background[n]=(int32_t)(value&511)*65536;
        if(foreground)foreground[n]=(int32_t)(x&511)*65536;
        if(++v==8){v=0;value=r6_row_x(p,entry++,x,layers);}
    }
}

/* The plane row a BG line shows is drawn by one layer: scrollwrtb reads
   z81awrttbl[y/16 + 1] (0 draws x 0 over all 512 pixels; 2/4/6 around
   scrb/scrc/scrz). Rows past the table (y >= 768) are never on screen. */
int scd_r6_row_layer(unsigned id,int y){
    const r6_program *p=r6_program_at(id);if(!p)return -1;
    unsigned i=((unsigned)(uint16_t)y/16)+1;if(i>48)i=48;
    return p->wrttbl[i]/2;
}
int scd_r6_row_start(unsigned id,int x,const int32_t *layers,int y){
    int layer=scd_r6_row_layer(id,y);
    if(layer<=0)return 0;
    int bx=r6_layer_x((unsigned)layer,x,layers);
    return (bx>=0?bx/8:-((-bx+7)/8))-11;
}

/* Level state for background.c: scrbinit on reset, one scroll() layer step
   per simulation update from the camera X delta. */
static struct { int32_t l[4]; int x; } r6_state;
void scd_r6_reset(int x){scd_r6_layers_reset(x,r6_state.l);r6_state.x=x;}
void scd_r6_step(int x){scd_r6_layers_step(x-r6_state.x,r6_state.l);r6_state.x=x;}
const int32_t *scd_r6_layers(void){return r6_state.l;}

/* COL6A-D clchgctr/colchg6a/clchg_sub0 (src/background_r6_palette.inc): four
   scripts, one call per simulation update; the timers and written entries
   persist, so frame counts calls (0 = none) and a smaller frame or another
   era restarts them. Act 3 script 3 (the flashing floor, entry 49) takes
   col6a3col_stop while BOSS_6.C sets bossflag bit 5. */
#include "background_r6_palette.inc"
static struct { int era; unsigned tick; unsigned boss; uint8_t tim[4],cnt[4],set[64]; uint16_t color[64]; } r6_pal={-1,0,0,{0},{0},{0},{0}};
static unsigned r6_palette_title_phase;
void scd_r6_palette_title_phase_set(unsigned phase){
    /* The retail VInt advances COL6 before the first playable object pass.
       The level timer phase is measured at that pass, one palette call later. */
    r6_palette_title_phase=phase+1;r6_pal.era=-1;r6_pal.tick=0;
}
void scd_r6_set_bossflag(unsigned bossflag){r6_pal.boss=bossflag;}
unsigned scd_r6_cg_change(unsigned id,unsigned bossflag){
    if((id==10 || id==11) && (bossflag&64))bossflag=(bossflag&~64u)|128u;
    r6_pal.boss=bossflag;
    return bossflag;
}
unsigned scd_r6_palette_count(unsigned script){return script<4?r6_pal.cnt[script]:0;}
static void r6_clchg(unsigned n,const uint8_t *s,const uint16_t *colors){
    uint8_t *t=&r6_pal.tim[n],*c=&r6_pal.cnt[n];
    if((int8_t)--*t>=0)return;
    unsigned index=s[0]&63;
    if(++*c>=s[1])*c=0;
    *t=s[2+*c*2];
    r6_pal.color[index]=colors[s[3+*c*2]];r6_pal.set[index]=1;
}
void scd_r6_palette(unsigned id,unsigned frame,uint16_t *out){
    if(!r6_program_at(id))return;
    frame+=r6_palette_title_phase;
    int era=(int)(id&3);
    if(r6_pal.era!=era||frame<r6_pal.tick){
        for(unsigned i=0;i<64;i++)r6_pal.set[i]=0;
        for(unsigned i=0;i<4;i++)r6_pal.tim[i]=r6_pal.cnt[i]=0;
        r6_pal.era=era;r6_pal.tick=0;
    }
    const r6_pal_set *p=&r6_pal_sets[era];
    while(r6_pal.tick<frame){
        for(unsigned n=0;n<4;n++)
            r6_clchg(n,p->call[n].script,n==3&&p->stop&&(r6_pal.boss&32)?p->stop:p->call[n].colors);
        r6_pal.tick++;
    }
    for(unsigned i=0;i<64;i++)if(r6_pal.set[i])out[i]=r6_pal.color[i];
}

/* Retail UpdateAnimTiles (assets/generated/ww_terrain.inc, parsed from each
   R6 MMD by tools/ww_terrain_assets.py): once at level setup and once per
   level vblank. Timers and frames persist, so the calls replay one per tick
   (tick 0 = the setup call); a smaller tick or another program restarts
   them. frame packs every block's shown art so any change rewrites them. */
#include "background.h"
/* Saturn builds (Makefile SCD_REQUIRE_ZONE_TERRAIN) never drop the zone art silently. */
#if defined(SCD_REQUIRE_ZONE_TERRAIN) && !__has_include("ww_terrain.inc")
#error "assets/generated/ww_terrain.inc is missing (tools/build.sh: background_tables.py --terrain)"
#endif
#if __has_include("ww_terrain.inc")
#include "ww_terrain.inc"
static struct { int id; unsigned calls; uint8_t tim[6],cnt[6],shown[3]; } ww_st={-1,0,{0},{0},{0}};
unsigned scd_r6_sparks_active(void){return ww_st.cnt[2];}
static unsigned r6_bossflag_bits(void){return r6_pal.boss;}
static void r6_bossflag_write(unsigned v){r6_pal.boss=v;}
unsigned scd_r6_bossflag(void){return r6_bossflag_bits();}
/* One const/script helper: 1 when it fires (frame in *f). */
static int ww_fire(const ww_anim_call *c,unsigned slot,unsigned *f){
    if((int8_t)--ww_st.tim[slot]>=0)return 0;
    unsigned n=ww_st.cnt[slot]+1u;
    if(!c->script){ww_st.tim[slot]=c->tim;if(n>=c->frames)n=0;ww_st.cnt[slot]=(uint8_t)n;*f=n;return 1;}
    if(n>=c->count)n=0;
    ww_st.cnt[slot]=(uint8_t)n;ww_st.tim[slot]=c->pairs[n*2];*f=c->pairs[n*2+1];
    return 1;
}
static void ww_tick(const ww_anim_program *p){
    for(unsigned i=0;i<p->calls;i++){
        if(p->gate==1&&i==1){ /* R61C/R62C: frame2 toggles every 90/30 ticks; 0 clears call 1's block */
            if((int8_t)--ww_st.tim[2]<0){ww_st.cnt[2]^=1;ww_st.tim[2]=ww_st.cnt[2]?30:90;}
            if(!ww_st.cnt[2]){ww_st.shown[1]=15;return;} /* off: zeroes DMAed over the block */
        }
        unsigned f;
        if(!ww_fire(&p->call[i],i,&f))continue;
        if(p->gate==2&&!i){ /* R63C/R63D: BOSS_6.C bit 6 clears the block; bit 7 sends it elsewhere */
            unsigned b=r6_bossflag_bits();
            if(b&64){r6_bossflag_write((b&~64u)|128u);ww_st.shown[0]=15;continue;}
            if(b&128)continue;
        }
        ww_st.shown[i]=(uint8_t)f;
    }
}
static const uint8_t ww_clear[256];
unsigned scd_r6_tile_cycle(unsigned id,unsigned tick,scd_tile_write *out){
    if(id>=12)return 0;
    const ww_anim_program *p=&ww_anim[id];
    if(!p->calls)return 0;
    if(ww_st.id!=(int)id||tick+1<ww_st.calls||!ww_st.calls){
        for(unsigned s=0;s<6;s++)ww_st.tim[s]=ww_st.cnt[s]=0;
        for(unsigned s=0;s<3;s++)ww_st.shown[s]=0;
        ww_st.id=(int)id;ww_st.calls=0;
    }
    while(ww_st.calls<=tick){ww_tick(p);ww_st.calls++;}
    unsigned code=0;
    for(unsigned i=0;i<p->calls;i++)code|=(unsigned)ww_st.shown[i]<<(4*i);
    for(unsigned i=0;i<p->calls;i++){
        const ww_anim_call *c=&p->call[i];unsigned s=ww_st.shown[i];
        out[i]=(scd_tile_write){c->cell,c->tiles,s==15?ww_clear:c->art+s*c->tiles*32u,code};
    }
    return p->calls;
}
#else
unsigned scd_r6_tile_cycle(unsigned id,unsigned tick,scd_tile_write *out){(void)id;(void)tick;(void)out;return 0;}
unsigned scd_r6_sparks_active(void){return 0;}
unsigned scd_r6_bossflag(void){return r6_pal.boss;}
#endif
