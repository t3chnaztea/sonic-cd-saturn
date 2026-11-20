/* Exercise allocation bounds, stride padding, wrapping and cache equivalence. */
#include "special.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static void check(const scd_special_stage *stage,const void *cache,const scd_special_line *lines){
    uint8_t reference[96*264],actual[96*264];
    memset(reference,0xa5,sizeof(reference));memset(actual,0xa5,sizeof(actual));
    scd_special_render(stage,lines,reference,264);
    /* Unequal and non-cache-line row counts exercise the dual-CPU split API. */
    scd_special_render_rows(cache,cache,lines,actual,264,31);
    scd_special_render_rows(cache,cache,lines+31,actual+31*264,264,65);
    assert(!memcmp(reference,actual,sizeof(actual)));
    for(unsigned row=0;row<96;row++)for(unsigned col=256;col<264;col++)assert(actual[row*264+col]==0xa5);
    /* Span units: 8-row by 32-sample blocks (the game's floor jobs), then uneven spans. */
    memset(actual,0xa5,sizeof(actual));
    uint32_t reciprocals[96*2];scd_special_reciprocals(lines,96,reciprocals);
    for(unsigned unit=0;unit<96;unit++)scd_special_render_span(cache,cache,lines+(unit>>3)*8,reciprocals+(unit>>3)*16,actual+(unit>>3)*8*264+(unit&7)*32,264,8,(unit&7)*32,32);
    assert(!memcmp(reference,actual,sizeof(actual)));
    memset(actual,0xa5,sizeof(actual));
    for(unsigned row=0;row<96;row+=5){
        unsigned rows=row+5<=96?5:96-row;
        for(unsigned first=0,count=1;first<256;first+=count,count=count*3%61+1){
            if(first+count>256)count=256-first;
            scd_special_render_span(cache,cache,lines+row,NULL,actual+row*264+first,264,rows,first,count);
        }
    }
    assert(!memcmp(reference,actual,sizeof(actual)));
}
int main(void){
    unsigned cases=0,boundary_rows=0;uint32_t random=1;
    for(unsigned id=1;id<=8;id++){
        char path[80];snprintf(path,sizeof(path),"assets/generated/special%u.bin",id);
        FILE *f=fopen(path,"rb");assert(f);assert(!fseek(f,0,SEEK_END));long length=ftell(f);rewind(f);
        uint8_t *data=malloc(length);assert(data && fread(data,1,length,f)==(size_t)length);fclose(f);
        scd_special_stage stage;assert(!scd_special_open(&stage,data,length));
        void *cache=malloc(0x80000);assert(cache);size_t used=scd_special_cache(&stage,cache,0x80000);assert(used);
        void *small=malloc(used-1);assert(small);assert(!scd_special_cache(&stage,small,used-1));free(small);
        void *exact=malloc(used);assert(exact);assert(scd_special_cache(&stage,exact,used)==used);
        scd_special_line lines[96];
        for(unsigned i=0;i<128;i++){
            random=random*1664525u+1013904223u;
            scd_special_camera camera={(int16_t)random,(int16_t)(random>>16),(int16_t)(i%4==3?1204:352+(i%4)*136),128,(int16_t)(i*4)};
            assert(!scd_special_trace(lines,camera));
            check(&stage,exact,lines);
            cases++;
        }
        const unsigned starts[]={0,1,255,256,257,32767,32768,32769,65535};
        const int steps[]={-32768,-16384,-2048,-257,-1,0,1,257,2048,16384,32767};
        unsigned row=0;
        for(unsigned x=0;x<9;x++)for(unsigned y=0;y<9;y++)for(unsigned dx=0;dx<11;dx++)for(unsigned dy=0;dy<11;dy++){
            lines[row++]=(scd_special_line){starts[x],starts[y],steps[dx],steps[dy]};boundary_rows++;
            if(row==96){check(&stage,exact,lines);row=0;}
        }
        if(row)check(&stage,exact,lines);
        scd_special_animation animation={4,6,65530};
        for(unsigned tick=0;tick<64;tick++){
            unsigned writes=scd_special_animate(&stage,&animation,(uint8_t *)stage.part[1],exact,exact);
            assert(writes==stage.size[6]/8+((animation.delay&1)?0:stage.size[5]/10));
            assert(animation.fan<6 && !(animation.fan&1) && animation.hazard<8 && !(animation.hazard&1));
            assert(!scd_special_trace(lines,(scd_special_camera){1280,1280,352,128,tick*8}));
            check(&stage,exact,lines);
        }
        assert(animation.delay==58);
        free(exact);free(cache);free(data);
    }
    printf("Special boundary rows: %u PASS\n",boundary_rows);
    printf("Special ASan/UBSan: %u wrapped cameras, exact/short cache allocations and padded rows PASS\n",cases);
}
