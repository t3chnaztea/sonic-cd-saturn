/* Replay a recorded frame-profile camera route through draw_stage's BG/FG
   cache work. The periodic BG cache must leave all 4096 PNDs identical to the
   plain cache (itself checked against full rebuilds by background_cache_test)
   on every frame; tile-write counts are the cost proxy for phases 3 and 5. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "background_cache.h"
#include "foreground_cache.h"
#include "background.h"
static uint32_t plain[4096],fast[4096],fgmap[4096];
static int plain_rows[64],plain_starts[64],fast_rows[64],fast_starts[64];
int main(int argc,char **argv){
    assert(argc==4);
    FILE *f=fopen(argv[1],"rb");assert(f);fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);
    unsigned char *d=malloc((size_t)n);assert(d&&fread(d,1,(size_t)n,f)==(size_t)n);fclose(f);
    stage_t s;assert(!stage_open(&s,d,(size_t)n));unsigned id=(unsigned)atoi(argv[2]);
    static uint8_t periodic[SCD_BACKGROUND_PERIODIC_ROWS];scd_background_periodic_rows(&s,periodic);
    unsigned periodic_rows=0;for(int i=0;i<SCD_BACKGROUND_PERIODIC_ROWS;i++)periodic_rows+=periodic[i]>=128;
    for(int i=0;i<64;i++)plain_rows[i]=plain_starts[i]=fast_rows[i]=fast_starts[i]=-10000;
    if(!strcmp(argv[3],"sweep")){
        /* background_cache_test's camera sweep: bands, clouds, ramps, wraps. */
        unsigned ops=0,pw=0,qw=0;
        for(unsigned frame=0;frame<3000;frame++){
            int x=(int)(frame<1500?frame:3000-frame)*10,cy=(int)(frame*7%1825),by=scd_background_y(id,cy,x);
            for(int row=by/8;row<by/8+30;row++){
                int fixed=scd_background_static(id,row*8);
                int sx=fixed?0:scd_background_raster_x(id,x,row*8,frame,(int)(frame*97%65536))/8;
                if(frame&1)sx&=63; /* alternate masked/unmasked starts as draw_stage's two paths do */
                pw+=scd_background_cache_row(&s,plain,plain_rows,plain_starts,row,sx,fixed);
                qw+=scd_background_cache_row_periodic(&s,fast,fast_rows,fast_starts,row,sx,fixed,periodic);
                assert(!memcmp(plain,fast,sizeof plain));ops++;
            }
        }
        printf("%s: %u sweep rows identical; BG writes %u -> %u\n",argv[1],ops,pw,qw);return 0;
    }
    FILE *r=fopen(argv[3],"r");assert(r);
    unsigned frame,cx,cy,frames=0,max_plain=0,max_fast=0,max_fg=0,max_plain_at=0,max_fast_at=0,max_fg_at=0;
    unsigned long total_plain=0,total_fast=0,total_fg=0;int first=1,px=-10000,py=-10000;
    scd_background_scroll sc;static int32_t bl[224],fl[224];char line[512];
    while(fgets(line,sizeof line,r)){
        unsigned v[32];int k=0;char *p=strstr(line,"Frame profile:");if(!p)continue;p+=14;
        while(k<32){char *e;unsigned long x=strtoul(p,&e,10);if(e==p)break;v[k++]=(unsigned)x;p=e;}
        if(k<23)continue;frame=v[1];cx=v[21];cy=v[22];
        if(first){scd_background_reset(&sc,(int)cx);first=0;}else scd_background_step(&sc,id,(int)cx,0,0);
        unsigned fw=scd_foreground_cache(&s,fgmap,(int)cx/8,(int)cy/8,px,py);px=(int)cx/8;py=(int)cy/8;
        int by=scd_background_y(id,(int)cy,0);unsigned pw=0,qw=0;
        scd_background_lines_state(id,&sc,(int)cx,(int)cy,by,frame,bl,fl,224);
        for(int row=by/8;row<by/8+30;row++){
            int fixed=scd_background_static(id,row*8),l=row*8-by;
            int sx=fixed?0:scd_background_row_start(id,&sc,(int)cx,row*8,frame);(void)l;
            pw+=scd_background_cache_row(&s,plain,plain_rows,plain_starts,row,sx,fixed);
            qw+=scd_background_cache_row_periodic(&s,fast,fast_rows,fast_starts,row,sx,fixed,periodic);
        }
        assert(!memcmp(plain,fast,sizeof plain));
        if(getenv("SCD_REPLAY_TRACE")&&(pw>=128||fw>=84))printf("frame %u cam %u,%u: BG %u -> %u, FG %u\n",frame,cx,cy,pw,qw,fw);
        if(frame==0){total_fg+=fw;frames++;continue;} /* level-setup and title-card fills */
        if(pw>max_plain){max_plain=pw;max_plain_at=frame;}
        if(qw>max_fast){max_fast=qw;max_fast_at=frame;}
        if(fw>max_fg){max_fg=fw;max_fg_at=frame;}
        total_plain+=pw;total_fast+=qw;total_fg+=fw;frames++;
    }
    assert(frames);
    printf("CC cache replay: %u frames, %u/%u BG rows periodic over >=128 tiles, identical maps every frame; "
           "after setup: BG writes %lu -> %lu (max %u@%u -> %u@%u); FG writes %lu (max %u@%u)\n",
           frames,periodic_rows,SCD_BACKGROUND_PERIODIC_ROWS,total_plain,total_fast,max_plain,max_plain_at,
           max_fast,max_fast_at,total_fg,max_fg,max_fg_at);
    return 0;
}
