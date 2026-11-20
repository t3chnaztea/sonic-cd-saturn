/* Independent full-row rebuild oracle: every operation must leave all 4096
   PNDs identical, including offscreen cells and wrapping cache slots. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "background_cache.h"
#include "background.h"
static uint32_t actual[4096],expected[4096];
static int rows[64],starts[64];
static unsigned operations;
static void reset(void){
    memset(actual,0xa5,sizeof(actual));memcpy(expected,actual,sizeof(actual));
    for(unsigned i=0;i<64;i++)rows[i]=starts[i]=-10000;
}
static void check(const stage_t *s,int row,int sx,int fixed,int writes){
    for(int col=0;col<64;col++){
        int wx=sx+col;
        expected[((unsigned)row&63)*64+((unsigned)wx&63)]=stage_saturn_pnd(
            stage_tile(s,1,fixed?(wx*8)&511:wx*8,row*8),4096);
    }
    unsigned n=scd_background_cache_row(s,actual,rows,starts,row,sx,fixed);
    assert(writes<0 || n==(unsigned)writes);
    assert(!memcmp(actual,expected,sizeof(actual)));operations++;
}
int main(int argc,char **argv){
    static const unsigned ids[]={0,1,2,3,4,5,6,7,10,11,12,13,14,15,16,17,18,19,22,23};
    assert(argc==(int)(sizeof(ids)/sizeof(ids[0]))+1);
    for(int pack=1;pack<argc;pack++){
        FILE *f=fopen(argv[pack],"rb");assert(f);
        assert(!fseek(f,0,SEEK_END));long size=ftell(f);assert(size>0);rewind(f);
        unsigned char *data=malloc((size_t)size);assert(data);
        assert(fread(data,1,(size_t)size,f)==(size_t)size);fclose(f);
        stage_t s;assert(!stage_open(&s,data,(size_t)size));
        reset();
        for(int row=0;row<256;row++){
            check(&s,row,0,0,64);
            for(int x=1;x<128;x++)check(&s,row,x,0,1);
            check(&s,row,127,0,0);
            for(int x=126;x>=-65;x--)check(&s,row,x,0,1);
            check(&s,row,1900,0,64);check(&s,row,2048,0,64);
            check(&s,row,2047,0,1);check(&s,row,-128,0,64);
            check(&s,row,0,1,64);check(&s,row,0,1,0);
        }
        /* Camera sweeps through each real act/era's independent raster bands,
           cloud animation, ramp offsets, static rows and vertical wrap. */
        reset();
        unsigned id=ids[pack-1];
        for(unsigned frame=0;frame<3000;frame++){
            int x=(int)(frame<1500?frame:3000-frame)*10;
            int cy=(int)(frame*7%1825),by=scd_background_y(id,cy,x);
            for(int row=by/8;row<by/8+30;row++){
                int fixed=scd_background_static(id,row*8);
                int sx=fixed?0:scd_background_raster_x(id,x,row*8,frame,(int)(frame*97%65536))/8;
                check(&s,row,sx,fixed,-1);
            }
        }
        free(data);
    }
    printf("Background cache: %u full-map equivalence checks across %zu packs; one-tile shifts decode one tile, not 64\n",operations,sizeof(ids)/sizeof(ids[0]));
}
