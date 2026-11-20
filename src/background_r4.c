/* Tidal Tempest (R4) deformation from SCR41A-D, SCR42A/C and SCR43C/D.C.
   Rows come from the checked scroll IR (tools/scroll/R4/ir) through
   src/background_r4_tables.inc; the line walk is zonescrsetsub0. */
#include <stdint.h>
#include "background_r4.h"

typedef struct { uint8_t op, layer; int16_t k, D; int32_t m; } r4_row;
typedef struct {
    const char *name; uint16_t entries, mask; uint8_t bgy;
    const r4_row *rows; const uint8_t *wrttbl;
} r4_program;
#include "background_r4_tables.inc"

static int r4_surface=32767;
void scd_r4_set_water(int surface){r4_surface=surface;}
int scd_r4_water(void){return r4_surface;}

static const r4_program *r4_program_at(unsigned id){return id<12&&r4_programs[id].rows?&r4_programs[id]:0;}
/* Table-free (other zones call it; the programs live in the R4 zone overlay):
   ids 0-7 and 10-11. tools/test_r4_scroll.py checks it against r4_programs. */
int scd_r4_valid(unsigned id){return id<12&&(0xcffu>>id&1u);}

static int32_t r4_floor_65536(int64_t a){return (int32_t)(a>=0?a>>16:-(((-a)+65535)>>16));}
/* Layer 0 is the camera; 1-3 are scrb/scrc/scrz (16.16, as scrollb/c/z_h). */
static int r4_layer_x(unsigned i,int x,const int32_t *layers){
    if(!i)return x;
    if(layers)return layers[i-1]>>16;
    static const int8_t C[4]={0,12,24,16};
    int32_t v=C[i]*x;return v>=0?v/256:-((-v+255)/256);
}
static int r4_row_x(const r4_program *p,unsigned entry,int x,const int32_t *layers){
    /* hscrollwork past the rows scroll() writes keeps zero (scrbinit clears
       only 30; nothing else writes them). */
    if(entry>=p->entries)return 0;
    const r4_row *r=&p->rows[entry];
    int from=r4_layer_x(r->layer,x,layers);
    if(r->op==1)return from;
    /* z41aline: hi(65536*scrz + m*trunc(128*(camera - scrz)/5)) */
    int32_t q=(int32_t)r->k*(x-from)/r->D; /* 32-bit: no 64-bit divide on SH-2 */
    return from+r4_floor_65536((int64_t)r->m*q);
}

int scd_r4_raster_x(unsigned id,int x,const int32_t *layers,int y){
    const r4_program *p=r4_program_at(id);if(!p)return x/8;
    return r4_row_x(p,((unsigned)(uint16_t)y>>3)&p->mask,x,layers);
}
static struct { int fed; int32_t scrb; } r4_v;
void scd_r4_camera_v_reset(void){r4_v.fed=0;}
void scd_r4_scrbinit(int32_t *scrb,int camera_y){
    /* scrbinit: (unsigned short)scra_v_posit.w.h >> 1, fraction 0 */
    *scrb=(int32_t)(((unsigned)(uint16_t)camera_y>>1)<<16);r4_v.scrb=*scrb;r4_v.fed=1;
}
void scd_r4_scroll_v(unsigned id,int32_t *scrb,int16_t scra_vz){
    if(!r4_program_at(id)||r4_programs[id].bgy)return;
    int32_t v=(int32_t)((uint32_t)*scrb+(uint32_t)(scra_vz*128)); /* scroll: scra_vz << 7 */
    /* scrollb_hv: every program but SCR42A (ids 4-5) stops scrb_v_posit at 0. */
    if(v<0&&id!=4&&id!=5)v=0;
    *scrb=r4_v.scrb=v;r4_v.fed=1;
}
int scd_r4_background_y(unsigned id,int camera_x,int camera_y){
    const r4_program *p=r4_program_at(id);if(!p)return camera_y/8;
    unsigned y=(uint16_t)camera_y;
    if(p->bgy){ /* SCR41A scroll()/scrbinit */
        if(y<512)return (unsigned)(uint16_t)camera_x>=640?512:(int)y;
        return (int)((((int64_t)y-512)*49152+0x2000000)>>16);
    }
    if(r4_v.fed)return (int16_t)(uint16_t)((uint32_t)r4_v.scrb>>16);
    return camera_y<0?0:camera_y>>1;
}

void scd_r4_lines_layers(unsigned id,int x,const int32_t *layers,int camera_y,int top,unsigned frame,
                         int32_t *background,int32_t *foreground,unsigned count){
    const r4_program *p=r4_program_at(id);if(!p)return;
    unsigned offs=((unsigned)top>>3)&p->mask,v=(unsigned)top&7;
    /* waterdirec is read before its +128 of this call. */
    unsigned phase=((uint32_t)(frame-1u)*128u>>8)&255u,index=(phase+(unsigned)top)&255u;
    int16_t avp=(int16_t)camera_y,surface=(int16_t)r4_surface;
    int32_t fg=(int32_t)(x&511)*65536;
    int value=r4_row_x(p,offs++,x,layers),wet=0;
    if(count>232)count=232;
    for(unsigned n=0;n<count;n++){
        /* SCR4*.C reads `avp > waterposi`; 680 retail CPU captures (all ten
           programs) prove the wobble starts on the surface line itself. */
        if(!wet&&avp>=surface)wet=1;
        int bx=wet?value-r4_awasintbl[index]:value;
        background[n]=(int32_t)(bx&511)*65536;
        if(foreground)foreground[n]=fg;
        avp++;index=(index+1)&255u;
        if(++v==8){v=0;value=r4_row_x(p,offs++,x,layers);}
    }
}

/* The plane row a BG line shows is drawn by one layer: SCR41A's scrollwrtb
   reads z81awrttbl[(y/16)&127 + 1] (0 draws x 0 over all 512 pixels, 2/4
   draw around scrb/scrc); the other programs draw every row from scrb. */
int scd_r4_row_layer(unsigned id,int y){
    const r4_program *p=r4_program_at(id);if(!p)return -1;
    return p->wrttbl[(((unsigned)(uint16_t)y/16)&127)+1]/2;
}
int scd_r4_row_start(unsigned id,int x,const int32_t *layers,int y){
    int layer=scd_r4_row_layer(id,y);
    if(layer<=0)return 0;
    int bx=r4_layer_x((unsigned)layer,x,layers);
    return (bx>=0?bx/8:-((-bx+7)/8))-11;
}

/* COL4A-D clchgctr/clchg_sub0 (src/background_r4_palette.inc). Timers and the
   written entries persist, and COL4A switches script sets on camera X/Y, so
   the scripts are replayed one call per simulation update rather than being
   evaluated from the frame number. */
#include "background_r4_palette.inc"
static struct { int id; unsigned tick; uint8_t tim[7],cnt[7],set[64]; uint16_t color[64]; } r4_pal={-1,0,{0},{0},{0},{0}};
static void r4_clchg(const r4_pal_call *c){
    uint8_t *t=&r4_pal.tim[c->timer],*n=&r4_pal.cnt[c->timer];
    if((int8_t)--*t>=0)return;
    const uint8_t *s=c->script;unsigned index=s[0];
    if(++*n>=s[1])*n=0;
    *t=s[2+*n*2];
    r4_pal.color[index]=c->colors[s[3+*n*2]];r4_pal.set[index]=1;
}
static void r4_clchgctr(unsigned id,int x,int y){
    unsigned era=id&3,act=id/4,n;
    if(!era){
        if(act||(uint16_t)x>=640)goto other;
        if((uint16_t)y>=352){
            if(!(r4_pal.tim[4]&128)){ /* colorset2(4): zone4colora into 16-63, once */
                for(n=0;n<48;n++){r4_pal.color[16+n]=r4_zone4colora[n];r4_pal.set[16+n]=1;}
            }
            r4_pal.tim[4]|=128;
            goto other;
        }
        for(n=0;n<r4_pal_start_count;n++)r4_clchg(&r4_pal_start[n]);
        return;
    }
    if(!act)return;
other:
    for(n=0;n<r4_pal_other_count[era];n++)r4_clchg(&r4_pal_other[era][n]);
}
uint64_t scd_r4_palette_entries(unsigned id){
    if(!r4_program_at(id))return 0;
    uint64_t m=0;unsigned era=id&3;
    for(unsigned n=0;n<r4_pal_other_count[era];n++)m|=1ull<<(r4_pal_other[era][n].script[0]&63);
    if(!era)for(unsigned n=0;n<r4_pal_start_count;n++)m|=1ull<<(r4_pal_start[n].script[0]&63);
    return m;
}
void scd_r4_palette(unsigned id,unsigned frame,int camera_x,int camera_y,uint16_t *out){
    if(!r4_program_at(id))return;
    if(r4_pal.id!=(int)id||frame<r4_pal.tick){
        for(unsigned i=0;i<64;i++)r4_pal.set[i]=0;
        for(unsigned i=0;i<7;i++)r4_pal.tim[i]=r4_pal.cnt[i]=0;
        r4_pal.id=(int)id;r4_pal.tick=0;
    }
    while(r4_pal.tick<frame){r4_clchgctr(id,camera_x,camera_y);r4_pal.tick++;}
    for(unsigned i=0;i<64;i++)if(r4_pal.set[i])out[i]=r4_pal.color[i];
}
