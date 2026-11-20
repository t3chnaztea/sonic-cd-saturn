/* PPZ1 raster regions from each Scroll (Act 1 ...).asm. Coordinates in pixels. */
#include "zone_r5_names.h"
#include "zone_code.h"
#include "background.h"
#include "background_r3.h"
#include "background_r4.h"
#include "background_r5.h"
#include "background_r6.h"
#include "background_r7.h"
typedef struct {unsigned duration,color;} pal_step;
typedef struct {unsigned index,count;const pal_step *steps;} pal_cycle;
#include "background.inc"
#include "cc2_terrain.inc"
#include "ppz_rows.inc"
/* Background id: zone*12 + act*4 + era.  Within a zone, era is 0-3 and 4 is
   Act 2 Present (SCR12A.C); Act 3 (SCR13C.C/SCR13D.C) scrolls like SCR12C and
   SCR12D with BG Y = camera Y*3/16.
   Only zone 0 has its Scroll (Act ...).asm raster regions transcribed.  A later
   zone would otherwise draw its foreground over Palmtree Panic's parallax, so
   it gets a flat background that tracks the camera at the 1/8 rate every zone
   shares until its own tables are added here. */
#define BG_PER_ZONE 12
/* Collision Chaos Acts 1-2 (ids 12-19) and Act 3 Good/Bad Future (22-23). */
static unsigned bg_cc(unsigned id){return (id>=12&&id<=19)||id==22||id==23;}
/* Tidal Tempest Acts 1-2 (ids 24-31) and Act 3 Good/Bad Future (34-35). */
static unsigned bg_tt(unsigned id){return id>=24&&scd_r4_valid(id-24);}
/* Both zones keep scrb/scrc/scrz as 16.16 layers (scrollb/c/z_h). */
static unsigned bg_layers(unsigned id){return bg_cc(id)||bg_tt(id);}
/* Quartz Quadrant Acts 1-2 (ids 36-43) and Act 3 Good/Bad Future (46-47);
   its layers and enkeino live in src/background_r5.c. */
/* Quartz Quadrant background hooks (r5_background_zone_ops, after background_r5.c). */
struct scd_r5_background_ops {
    int (*background_y)(unsigned id,int y,int player_x);
    void (*lines_layers)(unsigned id,int x,const int32_t *layers,int top,int32_t *back,int32_t *fore,unsigned count);
    int (*map_update)(unsigned id,uint8_t *map,uint8_t *chunks,int *world_rows,int top_row);
    void (*palette)(unsigned id,unsigned frame,uint16_t *out);
    int (*raster_x)(unsigned id,int x,const int32_t *layers,int y);
    void (*reset)(int x);
    int (*row_layer)(unsigned id,int y);
    int (*row_start)(unsigned id,int x,const int32_t *layers,int y);
    void (*step)(unsigned id,int x);
    unsigned (*tile_limit)(unsigned id,unsigned tiles);
    int (*tile_run)(unsigned id,unsigned *first,unsigned *count,const uint8_t **art);
    int (*valid)(unsigned id);
};
/* volatile: the calls stay indirect, as the zone code audit requires (no folding into a
   direct resident->overlay call). */
static const struct scd_r5_background_ops *volatile r5_ops;
static unsigned bg_qq(unsigned id){return id>=36&&scd_zone_code_ready(3)&&r5_ops->valid(id-36);}
static int tt_camera_x,tt_camera_y;
/* Wacky Workbench Acts 1-2 (ids 48-55) and Act 3 Good/Bad Future (58-59). */
static unsigned bg_ww(unsigned id){return id>=48&&scd_r6_valid(id-48);}
unsigned scd_r6_tile_cycle(unsigned id,unsigned tick,scd_tile_write *out);
/* BEEM6 palette writes (src/objects_ww_enemies.inc); hosts without the objects see none. */
__attribute__((weak)) uint64_t scd_objects_ww_palette(uint16_t *out,uint64_t *fade_set){(void)out;(void)fade_set;return 0;}
/* Stardust Speedway Acts 1-2 (ids 60-67) and Act 3 Good/Bad Future (70-71). */
static unsigned bg_ss(unsigned id){return id>=60&&id<72&&scd_r7_valid(id-60);}
/* Metallic Madness Acts 1-2 (ids 72-79) and Act 3 Good/Bad Future (82-83): the same engine, programs 12-23. */
static unsigned bg_mm(unsigned id){return id>=72&&id<84&&scd_r7_valid(id-60);}
unsigned scd_r8_tile_cycle(unsigned id,unsigned tick,scd_tile_write *out);
static unsigned bg_plain(unsigned id){return id>=BG_PER_ZONE&&!bg_cc(id)&&!bg_tt(id)&&!bg_qq(id)&&!bg_ww(id)&&!bg_ss(id)&&!bg_mm(id);}
int scd_background_y(unsigned era,int y,int player_x){
    if(bg_cc(era))return scd_r3_background_y(era-12,y);
    if(bg_tt(era)){tt_camera_y=y;return scd_r4_background_y(era-24,tt_camera_x,y);}
    if(bg_qq(era))return r5_ops->background_y(era-36,y,player_x);
    if(bg_ww(era))return scd_r6_background_y(era-48,y);
    if(bg_ss(era)||bg_mm(era))return scd_r7_background_y(era-60,y);
    if(bg_plain(era))return y/8;
    if((era>=4 && era<=6) || era==10 || era==11)return y*3/16;
    if(era==7)return y/8;
    if(era)return y/8;
    return player_x<0x800 || y<0x1e0?y:0x1e0+(y-0x1e0)/2;
}
/* Palmtree Panic Acts 2/3 draw wrttbl id-0 rows at x 0 over all 512 pixels
   ((y/16)&31 indexes z1?x_wrttbl+1); retail plane B dumps confirm them. */
static int ppz_row_static(unsigned era,int y){
    unsigned i=era>=4&&era<=7?era-4:era==10||era==11?era-4:8;
    return i<8&&ppz_wrttbl[i][(((unsigned)(uint16_t)y/16)&31)+1]==0;
}
int scd_background_static(unsigned era,int y){if(bg_cc(era))return scd_r3_row_layer(era-12,y)==0;if(bg_tt(era))return scd_r4_row_layer(era-24,y)==0;if(bg_qq(era))return r5_ops->row_layer(era-36,y)==0;if(bg_ww(era))return scd_r6_row_layer(era-48,y)==0;if(bg_ss(era)||bg_mm(era))return scd_r7_row_layer(era-60,y)==0;if(era>=4&&era<=11)return ppz_row_static(era,y);if(era>3)return 0;unsigned row=((unsigned)y&2047)/16;return row>=era_bg_row_counts[era] || !era_bg_rows[era][row];}
void scd_background_reset(scd_background_scroll *s,int x){
    s->ramp=0;s->camera_x=x;tt_camera_x=x;
    if(scd_zone_code_ready(3))r5_ops->reset(x);scd_r6_reset(x);scd_r7_reset(~0u,x);
    s->r3_layers[0]=(int32_t)(x/64*3)*65536;
    s->r3_layers[1]=(int32_t)(x/32*3)*65536;
    s->r3_layers[2]=(int32_t)(x/16)*65536;
    s->r3_layers[3]=0;
}
void scd_background_step(scd_background_scroll *s,unsigned era,int x,int velocity,int ramp){
    /* Original d5 is X velocity (8.8) converted to 16.16, accumulated only
       while the camera moves. Keep 8 fractional bits here. */
    if(!era && ramp && x!=s->camera_x)s->ramp=(int32_t)((uint32_t)s->ramp+(uint32_t)velocity);
    if(bg_layers(era)){
        int delta=x-s->camera_x;
        s->r3_layers[0]+=(int32_t)delta*3072;
        s->r3_layers[1]+=(int32_t)delta*6144;
        s->r3_layers[2]+=(int32_t)delta*4096;
        s->r3_layers[3]=delta<0?65535:0;
    }
    if(bg_qq(era))r5_ops->step(era-36,x);
    if(bg_ww(era))scd_r6_step(x);
    if(bg_ss(era)||bg_mm(era))scd_r7_step(era-60,x);
    s->camera_x=x;tt_camera_x=x;
}
int scd_background_x(unsigned era,int x,int y,unsigned frame){return scd_background_raster_x(era,x,y,frame,0);}
int scd_background_raster_x_state(unsigned era,const scd_background_scroll *s,int x,int y,unsigned frame){
    if(bg_cc(era))return scd_r3_raster_x_layers(era-12,x,s?s->r3_layers:0,y,frame);
    if(bg_tt(era))return scd_r4_raster_x(era-24,x,s?s->r3_layers:0,y);
    if(bg_qq(era))return r5_ops->raster_x(era-36,x,0,y);
    if(bg_ww(era))return scd_r6_raster_x(era-48,x,s?scd_r6_layers():0,y);
    if(bg_ss(era)||bg_mm(era))return scd_r7_raster_x(era-60,x,scd_r7_layers_for(era-60),y);
    return scd_background_raster_x(era,x,y,frame,s?s->ramp:0);
}
int scd_background_raster_x(unsigned era,int x,int y,unsigned frame,int32_t ramp){
    if(bg_cc(era))return scd_r3_raster_x(era-12,x,y,frame);
    if(bg_tt(era))return scd_r4_raster_x(era-24,x,0,y);
    if(bg_qq(era))return r5_ops->raster_x(era-36,x,0,y);
    if(bg_ww(era))return scd_r6_raster_x(era-48,x,0,y);
    if(bg_ss(era)||bg_mm(era))return scd_r7_raster_x(era-60,x,scd_r7_layers_for(era-60),y);
    if(bg_plain(era))return x/8;
    y&=2047;
    if(era==4){
        /* SCR12A.C scroll(): hscrollwork rows of 8 lines from BG Y 0, clouds
           at 1, 3/4 and 1/2 pixel per update over x/8, x/8 to 256, x*3/16 to
           288, then a ramp toward the camera X by (x-c)/256 per line. */
        int z=x/8,c=x*3/16;y&=511;
        static const unsigned speed[]={65536,49152,32768};
        if(y<96)return z+(int)((uint64_t)frame*speed[y/32]>>16);
        if(y<256)return z;
        if(y<288)return c;
        return c+(y-288)*(int16_t)(x-c)/256;
    }
    if(era==5){
        /* SCR12B.C: eight cloud speeds for two 8-line rows each, x/8 to 192, then x*3/16. */
        static const unsigned speed[]={65536,57344,49152,40960,32768,24576,20480,16384};
        int z=x/8;y&=511;
        if(y<128)return z+(int)((uint64_t)frame*speed[y/16]>>16);
        return y<192?z:x*3/16;
    }
    if(era==6 || era==10){
        /* SCR12C.C: clouds in 2/4/4/4/2 rows over x*3/32, x*3/32 to 176, x/8 to 192,
           x*3/16 to 256, then the same ramp toward the camera as Act 2 Present. */
        static const unsigned speed[]={65536,57344,49152,40960,32768};
        int z=x*3/32,c=x*3/16;y&=511;
        if(y<128)return z+(int)((uint64_t)frame*speed[y<16?0:y<48?1:y<80?2:y<112?3:4]>>16);
        if(y<176)return z;
        if(y<192)return x/8;
        if(y<256)return c;
        return c+(y-256)*(int16_t)(x-c)/256;
    }
    if(era==7 || era==11){
        /* SCR12D.C: clouds in 4/4/5/1 rows over x*3/32, x*3/32 to 176, x/8 to 192,
           x*3/16 to 240; the source writes no rows below that, which stay at 0. */
        static const unsigned speed[]={65536,49152,32768,16384};
        int z=x*3/32;y&=511;
        if(y<112)return z+(int)((uint64_t)frame*speed[y<32?0:y<64?1:y<104?2:3]>>16);
        if(y<176)return z;
        if(y<192)return x/8;
        return y<240?x*3/16:0;
    }
    era&=3;
    if(era==0){
        int extra=ramp>>8,bush=x/2+extra,mountain=x*3/16+(ramp>>7);
        static const unsigned sizes[]={32,48,48,32,64,64,64,48,32,16};
        static const unsigned speeds[]={65536,57344,49152,40960,32768,24576,18432,16384,10240,8192};
        int end=0;for(unsigned n=0;n<10;n++){end+=sizes[n];if(y<end)return x/8+extra+(int)((uint64_t)frame*speeds[n]>>16);}
        if(y<608)return mountain;
        if(y<640)return bush;
        if(y<864)return bush+((x-bush)*256/224)*(y-640)/256;
        if(y<1088)return bush;
        if(y<1120)return bush;
        if(y<1280)return mountain;
        static const unsigned bottom_sizes[]={16,32,80,32,128,64,48,32,16};
        static const unsigned bottom_speeds[]={8192,16384,32768,49152,65536,49152,32768,16384,8192};
        end=1280;for(unsigned n=0;n<9;n++){end+=bottom_sizes[n];if(y<end)return x/8+extra+(int)((uint64_t)frame*bottom_speeds[n]>>16);}
        if(y<1888)return mountain;
        if(y<1920)return bush;
        return bush+((x-bush)*256/224)*(y-1920)/256;
    }
    unsigned cloud_end=era==1?64:era==2?96:112;
    if((unsigned)y<cloud_end){
        unsigned band=era==1?y/16:era==2?(y<32?0:y<64?1:y<80?2:3):(y<32?0:y<80?1:2);
        static const unsigned speed[]={65536,49152,32768,16384};
        return x/8+(int)((uint64_t)frame*speed[band]>>16);
    }
    if(era==1)return y<144?x/8:y<336?x*3/16:0;
    unsigned mountain_end=era==2?144:176;
    if((unsigned)y<mountain_end)return x/8;
    if((unsigned)y<mountain_end+16)return x*3/16;
    unsigned water=era==2?224:240;
    if((unsigned)y<water)return x/4;
    if(era==3)return 0;
    return x/4+(x-x/4)*(y-water)/256;
}
/* Hardware horizontal-scroll table, in 16.16. Present's flat bands have
   boundaries on 16-line multiples in Act 1 and 32-line multiples in Act 2.
   Evaluate those once per run, retaining every scalar sample on the slopes.
   Runs must stop at band boundaries and at the source coordinate wrap. */
void scd_background_lines(unsigned era,int x,int y,unsigned frame,int32_t ramp,int32_t *out,unsigned count){
    scd_background_lines_pair(era,x,0,y,frame,ramp,out,0,count);
}
void scd_background_lines_pair(unsigned era,int x,int camera_y,int y,unsigned frame,int32_t ramp,int32_t *out,int32_t *foreground,unsigned count){
    if(bg_cc(era)){scd_r3_lines(era-12,x,camera_y,y,frame,out,foreground,count);return;}
    if(bg_tt(era)){scd_r4_lines_layers(era-24,x,0,camera_y,y,frame,out,foreground,count);return;}
    if(bg_qq(era)){r5_ops->lines_layers(era-36,x,0,y,out,foreground,count);return;}
    if(bg_ww(era)){scd_r6_lines_layers(era-48,x,0,y,out,foreground,count);return;}
    if(bg_ss(era)||bg_mm(era)){scd_r7_lines_layers(era-60,x,scd_r7_layers_for(era-60),y,scd_r7_waterdirec(),out,foreground,count);return;}
    while(count){
        unsigned run=1;
        unsigned row=(unsigned)y&2047;
        if(era==0 && (row<640 || (row>=864 && row<1920))){
            run=16-(row&15);
            if(run>count)run=count;
        }else if(era==4 && ((unsigned)y&511)<288){
            run=32-((unsigned)y&31);
            if(run>count)run=count;
        }
        int32_t value=(int32_t)(scd_background_raster_x(era,x,y,frame,ramp)&511)*65536;
        y+=(int)run;count-=run;
        do {*out++=value;if(foreground)*foreground++=(int32_t)(x&511)*65536;}while(--run);
    }
}
void scd_background_lines_state(unsigned era,const scd_background_scroll *s,int x,int camera_y,int y,unsigned frame,int32_t *out,int32_t *foreground,unsigned count){
    if(bg_cc(era)){scd_r3_lines_layers(era-12,x,s?s->r3_layers:0,camera_y,y,frame,out,foreground,count);return;}
    if(bg_tt(era)){scd_r4_lines_layers(era-24,x,s?s->r3_layers:0,camera_y,y,frame,out,foreground,count);return;}
    if(bg_qq(era)){r5_ops->lines_layers(era-36,x,0,y,out,foreground,count);return;}
    if(bg_ww(era)){scd_r6_lines_layers(era-48,x,s?scd_r6_layers():0,y,out,foreground,count);return;}
    if(bg_ss(era)||bg_mm(era)){scd_r7_lines_layers(era-60,x,scd_r7_layers_for(era-60),y,scd_r7_waterdirec(),out,foreground,count);return;}
    scd_background_lines_pair(era,x,camera_y,y,frame,s?s->ramp:0,out,foreground,count);
}
void scd_background_palette(unsigned era,unsigned frame,const uint8_t *base,uint16_t *out){
    for(unsigned i=0;i<64;i++)out[i]=((unsigned)base[i*2]<<8)|base[i*2+1];
    if(bg_tt(era)){scd_r4_palette(era-24,frame,tt_camera_x,tt_camera_y,out);return;}
    if(bg_qq(era)){r5_ops->palette(era-36,frame,out);return;}
    if(bg_ww(era)){
        scd_r6_palette(era-48,frame,out);
        /* BEEM6.C writes lpcolorwk entries (32, 61, 50-52) over the COL6 scripts;
           src/objects_ww_enemies.inc returns them as Mega Drive 0BGR words. The
           lpcolorwk2 fade targets belong to the fade code, not this palette. */
        uint16_t beam[128];uint64_t fade=0,set=scd_objects_ww_palette(beam,&fade);
        for(unsigned i=0;i<64;i++)if(set>>i&1){unsigned w=beam[i];
            out[i]=(uint16_t)(0x8000u|(((w>>1)&7u)*31u/7u)|(((w>>5)&7u)*31u/7u)<<5|(((w>>9)&7u)*31u/7u)<<10);}
        return;
    }
    if(bg_ss(era)){scd_r7_palette(era-60,frame,out);return;}
    if(bg_mm(era)){scd_r8_palette(era-72,frame,out);return;}
    if(bg_cc(era)){
        /* clchgtim/clchgcnt start at zero. The first simulation update writes
           script frame 1; paused/repeated display calls cannot advance it. */
        if(!frame)return;
        unsigned variant=(era-12)&3;
        for(unsigned n=0;n<cc_cycle_counts[variant];n++){
            const pal_cycle *c=&cc_cycles[variant][n];unsigned length=0;
            for(unsigned j=0;j<c->count;j++)length+=c->steps[j].duration;
            unsigned t=(frame-1)%length;
            for(unsigned j=0;j<c->count;j++){
                if(t<c->steps[j].duration){out[c->index]=c->steps[j].color;break;}
                t-=c->steps[j].duration;
            }
        }
        return;
    }
    if(bg_plain(era))return;
    era&=3;
    for(unsigned n=0;n<era_cycle_counts[era];n++){
        const pal_cycle *c=&era_cycles[era][n];unsigned length=0;
        for(unsigned j=0;j<c->count;j++)length+=c->steps[j].duration;
        unsigned t=frame%length;
        for(unsigned j=0;j<c->count;j++){if(t<c->steps[j].duration){out[c->index]=c->steps[j].color;break;}t-=c->steps[j].duration;}
    }
}

/* Saturn builds (Makefile SCD_REQUIRE_ZONE_TERRAIN) never drop the zone art silently. */
#if defined(SCD_REQUIRE_ZONE_TERRAIN) && !__has_include("tt_terrain.inc")
#error "assets/generated/tt_terrain.inc is missing (tools/build.sh: background_tables.py --terrain)"
#endif
#if __has_include("tt_terrain.inc")
#include "tt_terrain.inc"
#define TT_FIRE 1
#endif
/* DEV41A.C cg_change: three 16-tile fire slots on 24-step scripts, run only
   while camera X < 640 and Y < 352 (signed words). Timers persist while the
   camera is away, so the scripts replay one call per tick (tick 0 is the
   level-setup call); a smaller tick restarts them. frame packs all three
   slots' frames so any change rewrites the slots. */
#ifdef TT_FIRE
static unsigned tt_fire_cycle(unsigned tick,scd_tile_write *out){
    static struct { unsigned calls; uint8_t tim[3],cnt[3],frame[3]; } f;
    if(tick+1<f.calls||!f.calls){f.calls=0;for(unsigned s=0;s<3;s++)f.tim[s]=f.cnt[s]=f.frame[s]=0;}
    while(f.calls<=tick){
        f.calls++;
        if((int16_t)tt_camera_x>=640||(int16_t)tt_camera_y>=352)continue;
        for(unsigned s=0;s<3;s++){
            if((int8_t)--f.tim[s]>=0)continue;
            unsigned i=f.cnt[s]+1u;if(i>=24)i=0;
            f.cnt[s]=(uint8_t)i;f.tim[s]=r4_fire_script[s][i*2];f.frame[s]=r4_fire_script[s][i*2+1];
        }
    }
    unsigned code=f.frame[0]|f.frame[1]<<3|f.frame[2]<<6;
    for(unsigned s=0;s<3;s++)out[s]=(scd_tile_write){r4_fire_cell[s],16,r4_fire_art[s][f.frame[s]],code};
    return 3;
}
#endif
unsigned scd_background_tile_cycle(unsigned era,unsigned tick,scd_tile_write *out){
#ifdef TT_FIRE
    if(era==24)return tt_fire_cycle(tick,out);
#endif
    if(bg_ww(era))return scd_r6_tile_cycle(era-48,tick,out);
    if(bg_mm(era))return scd_r8_tile_cycle(era-72,tick,out);
    if(bg_qq(era)){
        unsigned first,count;const uint8_t *art;int band=r5_ops->tile_run(era-36,&first,&count,&art);
        if(band<0)return 0;
        out[0]=(scd_tile_write){(uint16_t)first,(uint16_t)count,art,(unsigned)band};
        return 1;
    }
    if(era<16||era>19)return 0;
    const cc2_tile_cycle *c=&cc2_tile_cycles[era-16];
    if(!c->slots)return 0;
    /* The setup call finds timer 0, so it already advances to frame 1; each
       later fire follows `period` calls (timer reset, then subq/bpl). */
    unsigned frame=(tick/c->period+1)%c->frames;
    for(unsigned s=0;s<c->slots;s++)out[s]=(scd_tile_write){c->cell[s],c->cells[s],cc2_tile_art+c->art[frame][s],frame};
    return c->slots;
}
int scd_background_row_start(unsigned era,const scd_background_scroll *s,int x,int y,unsigned frame){
    if(bg_cc(era))return scd_r3_row_start(era-12,x,s?s->r3_layers:0,y);
    if(bg_tt(era))return scd_r4_row_start(era-24,x,s?s->r3_layers:0,y);
    if(bg_qq(era))return r5_ops->row_start(era-36,x,0,y);
    if(bg_ww(era))return scd_r6_row_start(era-48,x,s?scd_r6_layers():0,y);
    if(bg_ss(era)||bg_mm(era))return scd_r7_row_start(era-60,x,scd_r7_layers_for(era-60),y);
    /* The unmasked row position: the 512-pixel masked line scroll would jump
       sx by 63 tiles at every 4096-pixel camera wrap (v0.047 used this).
       Keep 11 spare columns left, as the original plane does, so lines that
       deform left of the row's first line still show their own tiles. */
    int bx=scd_background_raster_x_state(era,s,x,y,frame);
    return (bx>=0?bx/8:-((-bx+7)/8))-11;
}

/* Tidal Tempest scroll is compiled here so every build and host test that
   compiles background.c carries it without touching their source lists. */
#include "background_r4.c"
/* Quartz Quadrant tables (src/background_r5_tables.inc, _palette.inc and the
   retail-art assets/generated/qq_terrain.inc, ~130 KB) stay out of the
   resident Saturn program: they go to the R5 zone overlay (cd/ZTR5.BIN) under
   the zone-table contract.  Until then only host builds that define
   SCD_ZONE_R5 compile them; everywhere else bg_qq() is false and these stubs
   only satisfy the linker. */
#ifdef SCD_ZONE_R5
#include "background_r5.c"
#else
int scd_r5_valid(unsigned id){(void)id;return 0;}
void scd_r5_reset(int x){(void)x;}
void scd_r5_step(unsigned id,int x){(void)id;(void)x;}
int scd_r5_background_y(unsigned id,int y,int px){(void)id;(void)px;return y/8;}
int scd_r5_raster_x(unsigned id,int x,const int32_t *l,int y){(void)id;(void)l;(void)y;return x/8;}
void scd_r5_lines_layers(unsigned id,int x,const int32_t *l,int top,int32_t *b,int32_t *f,unsigned n){(void)id;(void)x;(void)l;(void)top;(void)b;(void)f;(void)n;}
int scd_r5_row_layer(unsigned id,int y){(void)id;(void)y;return -1;}
int scd_r5_row_start(unsigned id,int x,const int32_t *l,int y){(void)id;(void)x;(void)l;(void)y;return 0;}
void scd_r5_palette(unsigned id,unsigned frame,uint16_t *out){(void)id;(void)frame;(void)out;}
int scd_r5_tile_run(unsigned id,unsigned *first,unsigned *count,const uint8_t **art){(void)id;(void)first;(void)count;(void)art;return -1;}
unsigned scd_r5_tile_limit(unsigned id,unsigned tiles){(void)id;return tiles;}
int scd_r5_map_update(unsigned id,uint8_t *map,uint8_t *chunks,int *rows,int top){(void)id;(void)map;(void)chunks;(void)rows;(void)top;return 0;}
#endif
/* Quartz Quadrant's background runs from the R5 overlay (src/zone_r5_names.h): this file
   reaches it only through r5_background_zone_ops, once src/main.c has loaded cd/ZTR5.BIN
   (bg_qq and the reset check src/zone_code.h). */
static const struct scd_r5_background_ops r5_background_zone_ops={.background_y=scd_r5_background_y,.lines_layers=scd_r5_lines_layers,.map_update=scd_r5_map_update,.palette=scd_r5_palette,.raster_x=scd_r5_raster_x,.reset=scd_r5_reset,.row_layer=scd_r5_row_layer,.row_start=scd_r5_row_start,.step=scd_r5_step,.tile_limit=scd_r5_tile_limit,.tile_run=scd_r5_tile_run,.valid=scd_r5_valid};
static const struct scd_r5_background_ops *volatile r5_ops=&r5_background_zone_ops;
#include "background_r6.c"
#include "background_r7.c"
unsigned scd_background_tile_limit(unsigned era,unsigned tiles){return bg_qq(era)?r5_ops->tile_limit(era-36,tiles):tiles;}
int scd_background_map_update(unsigned era,uint8_t *map,uint8_t *chunks,int *world_rows,int top_row){
    return bg_qq(era)?r5_ops->map_update(era-36,map,chunks,world_rows,top_row):0;
}
