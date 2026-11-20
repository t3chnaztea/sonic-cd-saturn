/* Quartz Quadrant enkeino layout switches through the BG row cache, as
   src/main.c draw_stage drives them: scd_r5_step per update, background Y
   with the player X (camera X + 160), scd_r5_map_update on the pack's own
   layout and chunk table, then the 30 visible rows through the periodic cache.
   Reports the most BG cell writes in one frame outside layout-switch frames
   (must stay within write_limit), the most on a switch frame (one full
   redraw, as the original's mapwrtb), and the most consecutive frames whose
   cached rows differ from a fresh draw of the current layout (stale_limit).

   usage: qq_enkei_replay pack.bin id width height write_limit stale_limit */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "stage.h"
#include "background_cache.h"
#include "background_r5.h"

int main(int argc,char **argv){
    assert(argc==7);
    FILE *f=fopen(argv[1],"rb");assert(f);fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);
    uint8_t *d=malloc((size_t)n);assert(d&&fread(d,1,(size_t)n,f)==(size_t)n);fclose(f);
    stage_t s;assert(!stage_open(&s,d,(size_t)n));
    unsigned id=(unsigned)atoi(argv[2]);int w=atoi(argv[3]),h=atoi(argv[4]);
    unsigned limit=(unsigned)atoi(argv[5]),stale_limit=(unsigned)atoi(argv[6]);
    unsigned tiles=scd_r5_tile_limit(id,s.size[0]/32);if(tiles*32>s.size[0])s.size[0]=tiles*32;
    static uint8_t periodic[SCD_BACKGROUND_PERIODIC_ROWS];scd_background_periodic_rows(&s,periodic);
    static uint32_t map[64*64],fresh[64*64];static int world[64],starts[64],fw[64],fs[64];
    for(int i=0;i<64;i++)world[i]=starts[i]=-10000;
    static int32_t bl[224],fl[224];
    int previous_hold=0;unsigned frames=0,max=0,max_at=0,stale=0,max_stale=0,switches=0,last=0,worst_frame=0,switch_max=0;
    int cx=0,cy=h/2;
    scd_r5_reset(cx);
    /* Out along the act and back, 8 px per update, sweeping vertically. */
    for(int leg=0;leg<2;leg++)for(int step=0;step<=w/8;step++,frames++){
        cx=leg?w-step*8:step*8;
        cy=cy+((frames/180)%2?6:-6)*(frames%3!=0);if(cy<0)cy=0;if(cy>h)cy=h;
        if(frames)scd_r5_step(id,cx);
        int by=scd_r5_background_y(id,cy,cx+160);
        unsigned band=(unsigned)scd_r5_enkei()&1;int switching=frames&&band!=last;switches+=(unsigned)switching;last=band;
        scd_r5_lines_layers(id,cx,0,by,bl,fl,224);
        int hold=scd_r5_map_update(id,(uint8_t *)s.part[4],(uint8_t *)s.part[2],world,by/8)<0;
        /* The first sampled layout is the reset baseline, not a transition. */
        if(frames&&switching!=hold){fprintf(stderr,"QQ enkeino replay: layout switch/hold mismatch\n");return 2;}
        int redrawing=previous_hold;previous_hold=hold;
        unsigned writes=0;
        for(int row=by/8;row<by/8+30;row++){
            int fixed=scd_r5_row_layer(id,row*8)==0,sx=fixed?0:scd_r5_row_start(id,cx,0,row*8);
            if(!hold)writes+=scd_background_cache_row_periodic(&s,map,world,starts,row,sx,fixed,periodic);
            fw[row&63]=-10000;
            scd_background_cache_row(&s,fresh,fw,fs,row,sx,fixed);
        }
        int differs=hold;
        for(int row=by/8;!hold&&row<by/8+30;row++)if(memcmp(map+(row&63)*64,fresh+(row&63)*64,256))differs=1;
        stale=differs?stale+1:0;if(stale>max_stale)max_stale=stale;
        if(redrawing){if(writes>switch_max)switch_max=writes;}
        else if(frames&&writes>max){max=writes;max_at=(unsigned)frames;worst_frame=(unsigned)cx;}
    }
    printf("QQ enkeino replay id %u: %u frames, %u layout switches, max BG writes %u@%u (camera X %u), "
           "switch frames up to %u, longest stale redraw %u frames\n",id,frames,switches,max,max_at,worst_frame,switch_max,max_stale);
    if(max>limit||max_stale>stale_limit){printf("FAIL: over the limits %u writes / %u frames\n",limit,stale_limit);return 1;}
    return 0;
}
