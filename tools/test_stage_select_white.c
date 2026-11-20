#include <stdint.h>
#include <stdio.h>

/* Held pre-optimization Main helper. Keep this loop as the independent oracle. */
static uint16_t oracle_white(uint16_t color,unsigned steps){
    unsigned c[3];
    for(unsigned i=0;i<3;i++)c[i]=((((color>>(i*5))&31)*7)+15)/31;
    while(steps--){for(unsigned i=0;i<3;i++)if(c[i]<7){c[i]++;break;}}
    return (color&0x8000)|(c[0]*31/7)|((c[1]*31/7)<<5)|((c[2]*31/7)<<10);
}

#ifndef SCD_WHITE_ACTUAL_INCLUDE
#error "The runner must supply the private include extracted from actual Main."
#endif
#define stage_select_level_white actual_white
#include SCD_WHITE_ACTUAL_INCLUDE
#undef stage_select_level_white

/* The oracle must detect a blue-first implementation. */
static uint16_t wrong_order_white(uint16_t color,unsigned steps){
    unsigned c[3];
    for(unsigned i=0;i<3;i++)c[i]=((((color>>(i*5))&31)*7)+15)/31;
    while(steps--){for(unsigned i=3;i>0;i--)if(c[i-1]<7){c[i-1]++;break;}}
    return (color&0x8000)|(c[0]*31/7)|((c[1]*31/7)<<5)|((c[2]*31/7)<<10);
}

int main(void){
    static const struct {unsigned steps;uint16_t color;} anchors[]={
        {0,0x0000},{1,0x0004},{7,0x001f},{8,0x009f},
        {14,0x03ff},{15,0x13ff},{21,0x7fff},{22,0x7fff}
    };
    for(unsigned i=0;i<sizeof(anchors)/sizeof(anchors[0]);i++){
        if(oracle_white(0,anchors[i].steps)!=anchors[i].color ||
           actual_white(0,anchors[i].steps)!=anchors[i].color){
            fprintf(stderr,"FAIL: independent red-green-blue anchor steps=%u\n",anchors[i].steps);
            return 1;
        }
    }
    if(wrong_order_white(0,1)==oracle_white(0,1)){
        fputs("FAIL: oracle did not reject wrong channel order\n",stderr);
        return 1;
    }
    unsigned compared=0;
    for(unsigned color=0;color<65536;color++){
        for(unsigned steps=0;steps<=22;steps++){
            uint16_t expected=oracle_white((uint16_t)color,steps);
            uint16_t got=actual_white((uint16_t)color,steps);
            if(got!=expected || (got&0x8000)!=(color&0x8000)){
                fprintf(stderr,"FAIL: white helper color=%04x steps=%u expected=%04x actual=%04x\n",
                        color,steps,(unsigned)expected,(unsigned)got);
                return 1;
            }
            compared++;
        }
    }
    if(compared!=1507328u)return 1;
    puts("PASS: stage-select white helper: 1507328 exact comparisons; MSB, 8 anchors and wrong-order negative");
    return 0;
}
