/* Stardust Speedway (R7) deformation, as the retail R71A-R73D scroll() runs:
   fills and chains into hscrollwork, then the zonescrsetsub0 line walk (with
   the R71B/R72B per-line wave). Programs come from the retail code through
   src/background_r7_tables.inc (tools/background_r7_assets.py). */
#include <stdint.h>
#include "background_r7.h"

/* op 0 fill (A = layer, n = count); 1 chain, 2 chain with add.w d2,d2 */
typedef struct { uint8_t op, A, B, s1; uint16_t D; uint8_t s2, pre, n, span; const uint8_t *counts; } r7_op;
typedef struct { uint8_t mul, shifts; int16_t K; } r7_init;
typedef struct {
    const char *name; uint8_t nops; const r7_op *ops; int16_t rate[3]; r7_init init[3];
    uint8_t bgy0, bgy1; uint16_t wave; const uint8_t *wrttbl; int16_t frac;  /* d3 = hz * frac after the layer steps */
} r7_program;
#include "background_r7_tables.inc"

static const r7_program *r7_at(unsigned id){return id<24&&r78_programs[id].ops?&r78_programs[id]:0;}
/* Table-free (other zones call it): ids 0-7, 10-11 (R7) and 12-19, 22-23 (R8).
   tools/test_r7_scroll.py checks it against r78_programs. */
int scd_r7_valid(unsigned id){return id<24&&(0xcffcffu>>id&1u);}

void scd_r7_layers_reset(unsigned id,int x,int32_t *l){
    const r7_program *p=r7_at(id);if(!p)return;
    for(unsigned i=0;i<3;i++){
        int16_t v=0,sx=(int16_t)x;
        for(unsigned k=0;k<8;k++)if(p->init[i].shifts>>k&1)v=(int16_t)(v+(sx>>k));
        l[i]=(int32_t)((uint32_t)(uint16_t)(int16_t)(v*p->init[i].mul+p->init[i].K)<<16);
    }
    l[3]=0;
}
static int32_t r7_forced=0x7fffffff;
void scd_r7_force_hz(int32_t hz){r7_forced=hz;}
void scd_r7_layers_step(unsigned id,int dx,int32_t *l){
    const r7_program *p=r7_at(id);if(!p)return;
    int32_t hz=r7_forced!=0x7fffffff?(int16_t)r7_forced:(int16_t)(dx*256); /* scra_hz, 8.8 */
    for(unsigned i=0;i<3;i++)l[i]=(int32_t)((uint32_t)l[i]+(uint32_t)(hz*p->rate[i]));
    /* the layer steps leave d3 = hz * frac (hz*32 in most programs); the
       first chain loads its base into d3's low word only */
    l[3]=(int32_t)((((uint32_t)hz*(uint32_t)(int32_t)p->frac)>>16)&65535u);
}

int scd_r7_background_y(unsigned id,int camera_y){
    const r7_program *p=r7_at(id);if(!p)return camera_y/8;
    unsigned y=(uint16_t)camera_y;
    if(!p->bgy0)return (int)(int16_t)y;
    return (int)(uint16_t)((y>>p->bgy0)+(y>>p->bgy1));
}

static int16_t r7_word(unsigned layer,int x,const int32_t *l){
    return layer?(l?(int16_t)(l[layer-1]>>16):0):(int16_t)x;
}
/* hscrollwork as retail leaves it after this scroll(): values are background
   X (the table holds their negation); entries scroll() never writes keep 0. */
static unsigned r7_build(const r7_program *p,int x,const int32_t *l,int16_t *work){
    unsigned pos=0;uint32_t carry=l?(uint32_t)l[3]&65535u:0u;
    for(unsigned i=0;i<128;i++)work[i]=0;
    for(unsigned o=0;o<p->nops;o++){
        const r7_op *op=&p->ops[o];
        if(!op->op){int16_t v=r7_word(op->A,x,l);for(unsigned k=0;k<op->n&&pos<128;k++)work[pos++]=v;continue;}
        int16_t a=r7_word(op->A,x,l),b=r7_word(op->B,x,l);
        if(op->op==2)b=(int16_t)(b*2);
        uint32_t n=(uint32_t)(int32_t)(int16_t)(b-a)<<op->s1,u=n/op->D; /* divu.w: overflow keeps the dividend */
        uint32_t step=(uint32_t)(int32_t)(int16_t)(uint16_t)(u>65535u?n:u)<<op->s2;
        uint32_t d3=carry<<16|(uint16_t)a; /* register d3: fraction:integer */
        if(op->pre)d3=((d3<<16|d3>>16)+step),d3=d3<<16|d3>>16;
        unsigned at=op->span?pos+op->span:pos;
        for(unsigned k=op->n;k--;){
            for(unsigned c=0;c<=op->counts[k];c++){
                if(op->span){if(at>pos&&--at<128)work[at]=(int16_t)d3;}
                else if(pos<128)work[pos++]=(int16_t)d3;
            }
            d3=d3<<16|d3>>16;d3+=step;d3=d3<<16|d3>>16;
        }
        if(op->span)pos+=op->span;
        carry=d3>>16;
    }
    return pos;
}

void scd_r7_lines_layers(unsigned id,int x,const int32_t *l,int top,unsigned waterdirec,
                         int32_t *background,int32_t *foreground,unsigned count){
    const r7_program *p=r7_at(id);if(!p)return;
    int16_t work[128];r7_build(p,x,l,work);
    unsigned row=((unsigned)(uint16_t)top&1016u)>>3,v=(unsigned)top&7u,n=0;
    uint8_t phase=(uint8_t)((waterdirec+128u)>>8); /* addi.w #$80 first; the high byte */
    int32_t fg=(int32_t)((unsigned)x&511u)*65536;
    if(count>232)count=232;
    for(unsigned r=0;n<count;r++){
        /* R71B/R72B: from the first full row that ends at or past the threshold
           (cmpi.w #thr,d4 with d4 already the next row's start), every
           remaining line is -(scrz + (u16)sin(phase + 2k) >> 5) */
        if(r&&p->wave&&(((unsigned)(uint16_t)top&~7u)+8u*r+8u&65535u)>=p->wave){ /* d4 = the row's end */
            for(unsigned k=0;n<count;k++,n++){
                uint16_t s=(uint16_t)r78_sine[(uint8_t)(phase+2*k)];
                background[n]=(int32_t)(((unsigned)(s>>5)+(unsigned)(uint16_t)r7_word(3,x,l))&511u)*65536;
                if(foreground)foreground[n]=fg;
            }
            break;
        }
        int16_t value=row<128?work[row]:0;row++;
        for(;v<8&&n<count;v++,n++){background[n]=(int32_t)((unsigned)value&511u)*65536;if(foreground)foreground[n]=fg;}
        v=0;
    }
}
int scd_r7_raster_x(unsigned id,int x,const int32_t *l,int y){
    const r7_program *p=r7_at(id);if(!p)return x/8;
    int16_t work[128];r7_build(p,x,l,work);
    return work[((unsigned)(uint16_t)y>>3)&127];
}

/* scrollwrtb reads z81awrttbl[y/16 + 1] (0 draws x 0 over all 512 pixels;
   2/4/6 around scrb/scrc/scrz). */
int scd_r7_row_layer(unsigned id,int y){
    const r7_program *p=r7_at(id);if(!p)return -1;
    unsigned i=((unsigned)(uint16_t)y/16)+1;if(i>64)i=64;
    return p->wrttbl[i]/2;
}
int scd_r7_row_start(unsigned id,int x,const int32_t *l,int y){
    int layer=scd_r7_row_layer(id,y);
    if(layer<=0||!l)return 0;
    int bx=r7_word((unsigned)layer,x,l);
    return (bx>=0?bx/8:-((-bx+7)/8))-11;
}

static struct { unsigned id; int32_t l[4]; int x; unsigned water; } r7_state;
/* scd_background_reset does not know the program: an unknown id (~0u)
   records the camera, and the first step runs scrbinit from it. */
void scd_r7_reset(unsigned id,int x){r7_state.id=id;scd_r7_layers_reset(id,x,r7_state.l);r7_state.x=x;r7_state.water=0;}
void scd_r7_step(unsigned id,int x){
    if(id!=r7_state.id)scd_r7_reset(id,r7_state.x);
    scd_r7_layers_step(id,x-r7_state.x,r7_state.l);r7_state.x=x;r7_state.water+=128u;
}
const int32_t *scd_r7_layers(void){return r7_state.l;}
/* The level's layers for program id: after a reset that did not know the
   program, the first use runs scrbinit from the recorded camera. */
const int32_t *scd_r7_layers_for(unsigned id){if(id!=r7_state.id)scd_r7_reset(id,r7_state.x);return r7_state.l;}
unsigned scd_r7_waterdirec(void){return r7_state.water-128u;}

/* COL7A/COL7D clchgctr (src/background_r7_palette.inc): up to seven
   scripts, one timer/frame slot each, one call per simulation update;
   COL7B/COL7C have none. frame counts calls; a smaller frame or another
   era restarts them. */
#include "background_r7_palette.inc"
static struct { int era; unsigned tick; uint8_t tim[8],cnt[8],set[64]; uint16_t color[64]; } r7_pal={-1,0,{0},{0},{0},{0}};
void scd_r7_palette(unsigned id,unsigned frame,uint16_t *out){
    if(id>=12||!r7_at(id))return; /* COL7 only; Metallic Madness has its own */
    int era=(int)(id&3);
    const r7_pal_set *p=&r7_pal_sets[era];
    if(r7_pal.era!=era||frame<r7_pal.tick){
        for(unsigned i=0;i<64;i++)r7_pal.set[i]=0;
        for(unsigned i=0;i<8;i++)r7_pal.tim[i]=r7_pal.cnt[i]=0;
        r7_pal.era=era;r7_pal.tick=0;
    }
    while(r7_pal.tick<frame){
        for(unsigned n=0;n<p->calls;n++){
            const uint8_t *s=p->call[n].act23&&id>=4?p->call[n].act23:p->call[n].script;
            if((int8_t)--r7_pal.tim[n]>=0)continue;
            unsigned c=r7_pal.cnt[n]+1u;if(c>=s[1])c=0;
            r7_pal.cnt[n]=(uint8_t)c;r7_pal.tim[n]=s[2+c*2];
            r7_pal.color[s[0]&63]=p->call[n].colors[s[3+c*2]];r7_pal.set[s[0]&63]=1;
        }
        r7_pal.tick++;
    }
    for(unsigned i=0;i<64;i++)if(r7_pal.set[i])out[i]=r7_pal.color[i];
}

/* Metallic Madness COL8A-D colchg8x (src/background_r8_palette.inc): slots
   0-2 always, 3-5 by act; one call per simulation update. */
#include "background_r8_palette.inc"
static struct { int key; unsigned tick; uint8_t tim[8],cnt[8],set[64]; uint16_t color[64]; } r8_pal={-1,0,{0},{0},{0},{0}};
void scd_r8_palette(unsigned id,unsigned frame,uint16_t *out){
    if(id>=12||!r7_at(id+12))return;
    const r8_pal_set *p=&r8_pal_sets[id&3][id/4<3?id/4:2];
    if(r8_pal.key!=(int)id||frame<r8_pal.tick){
        for(unsigned i=0;i<64;i++)r8_pal.set[i]=0;
        for(unsigned i=0;i<8;i++)r8_pal.tim[i]=r8_pal.cnt[i]=0;
        r8_pal.key=(int)id;r8_pal.tick=0;
    }
    while(r8_pal.tick<frame){
        for(unsigned n=0;n<p->calls;n++){
            const uint8_t *s=p->call[n].script;
            if((int8_t)--r8_pal.tim[n]>=0)continue;
            unsigned c=r8_pal.cnt[n]+1u;if(c>=s[1])c=0;
            r8_pal.cnt[n]=(uint8_t)c;r8_pal.tim[n]=s[2+c*2];
            r8_pal.color[s[0]&63]=p->call[n].colors[s[3+c*2]];r8_pal.set[s[0]&63]=1;
        }
        r8_pal.tick++;
    }
    for(unsigned i=0;i<64;i++)if(r8_pal.set[i])out[i]=r8_pal.color[i];
}

/* The entries scd_r8_palette can change for this program (sprite CLUT refresh,
   src/zone_object_view.inc zone_cycle_build). */
uint64_t scd_r8_palette_entries(unsigned id){
    if(id>=12||!r7_at(id+12))return 0;
    const r8_pal_set *p=&r8_pal_sets[id&3][id/4<3?id/4:2];
    uint64_t m=0;
    for(unsigned n=0;n<p->calls;n++)m|=1ull<<(p->call[n].script[0]&63);
    return m;
}

/* Metallic Madness UpdateAnimTiles (assets/generated/mm_terrain.inc from
   tools/mm_terrain_assets.py): up to five const/script calls, no gates. */
#include "background.h"
/* Saturn builds (Makefile SCD_REQUIRE_ZONE_TERRAIN) never drop the zone art silently. */
#if defined(SCD_REQUIRE_ZONE_TERRAIN) && !__has_include("mm_terrain.inc")
#error "assets/generated/mm_terrain.inc is missing (tools/build.sh: background_tables.py --terrain)"
#endif
#if __has_include("mm_terrain.inc")
#include "mm_terrain.inc"
static struct { int id; unsigned calls; uint8_t tim[6],cnt[6],shown[5]; } mm_st={-1,0,{0},{0},{0}};
unsigned scd_r8_tile_cycle(unsigned id,unsigned tick,scd_tile_write *out){
    if(id>=12||!mm_anim[id].calls)return 0;
    const mm_anim_program *p=&mm_anim[id];
    if(mm_st.id!=(int)id||tick+1<mm_st.calls||!mm_st.calls){
        for(unsigned s=0;s<6;s++)mm_st.tim[s]=mm_st.cnt[s]=0;
        for(unsigned s=0;s<5;s++)mm_st.shown[s]=0;
        mm_st.id=(int)id;mm_st.calls=0;
    }
    while(mm_st.calls<=tick){
        for(unsigned i=0;i<p->calls;i++){
            const mm_anim_call *c=&p->call[i];
            if((int8_t)--mm_st.tim[i]>=0)continue;
            unsigned n=mm_st.cnt[i]+1u;
            if(!c->script){mm_st.tim[i]=c->tim;if(n>=c->frames)n=0;mm_st.cnt[i]=(uint8_t)n;mm_st.shown[i]=(uint8_t)n;}
            else{if(n>=c->count)n=0;mm_st.cnt[i]=(uint8_t)n;mm_st.tim[i]=c->pairs[n*2];mm_st.shown[i]=c->pairs[n*2+1];}
        }
        mm_st.calls++;
    }
    unsigned code=0;
    for(unsigned i=0;i<p->calls;i++)code|=(unsigned)mm_st.shown[i]<<(4*i);
    for(unsigned i=0;i<p->calls;i++){
        const mm_anim_call *c=&p->call[i];
        out[i]=(scd_tile_write){c->cell,c->tiles,c->art+mm_st.shown[i]*c->tiles*32u,code};
    }
    return p->calls;
}
#else
unsigned scd_r8_tile_cycle(unsigned id,unsigned tick,scd_tile_write *out){(void)id;(void)tick;(void)out;return 0;}
#endif
