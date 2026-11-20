#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "foreground_cache.h"
static uint32_t actual[4096],expected[4096],rng=0x50414c4d;
static unsigned operations;
static int previous_x,previous_y;
static void reset(void){
    memset(actual,0xa5,sizeof(actual));memcpy(expected,actual,sizeof(actual));
    previous_x=previous_y=-10000;
}
static unsigned check(const stage_t *s,int x,int y){
    unsigned count=0;
    /* Independent previous whole-viewport algorithm, not range clipping. */
    if(x!=previous_x || y!=previous_y)
        for(int row=0;row<30;row++)for(int col=0;col<42;col++){
            int wx=x+col,wy=y+row;
            if(wx>=previous_x && wx<previous_x+42 && wy>=previous_y && wy<previous_y+30)continue;
            expected[((unsigned)wy&63)*64+((unsigned)wx&63)]=stage_saturn_pnd(stage_tile(s,0,wx*8,wy*8),0);
            count++;
        }
    unsigned written=scd_foreground_cache(s,actual,x,y,previous_x,previous_y);
    assert(written==count);assert(!memcmp(actual,expected,sizeof(actual)));
    previous_x=x;previous_y=y;operations++;return written;
}
static uint32_t random_word(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
int main(int argc,char **argv){
    assert(argc==21);
    for(int pack=1;pack<argc;pack++){
        FILE *f=fopen(argv[pack],"rb");assert(f);assert(!fseek(f,0,SEEK_END));
        long size=ftell(f);assert(size>0);rewind(f);unsigned char *data=malloc((size_t)size);assert(data);
        assert(fread(data,1,(size_t)size,f)==(size_t)size);fclose(f);
        stage_t s;assert(!stage_open(&s,data,(size_t)size));reset();
        assert(check(&s,0,0)==1260);assert(check(&s,0,0)==0);
        assert(check(&s,1,0)==30);assert(check(&s,1,1)==42);
        assert(check(&s,0,0)==71);
        /* Every delta across both overlap boundaries, at multiple map wraps. */
        for(int origin=0;origin<4;origin++)for(int dy=-32;dy<=32;dy++)for(int dx=-44;dx<=44;dx++){
            int x=origin*63,y=origin*62;
            check(&s,x,y);check(&s,x+dx,y+dy);check(&s,x,y);
        }
        for(unsigned i=0;i<10000;i++){
            int x,y;
            if(i%37==0){x=(int)(random_word()%2112)-64;y=(int)(random_word()%384)-64;}
            else{x=previous_x+(int)(random_word()%9)-4;y=previous_y+(int)(random_word()%9)-4;}
            check(&s,x,y);
        }
        free(data);
    }
    printf("Foreground cache: %u full-map/write-count equivalence checks across 20 packs\n",operations);
}
