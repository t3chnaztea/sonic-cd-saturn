#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "sprite_order.h"
int native_order(const uint8_t *priority,unsigned count,uint8_t *order){return scd_sprite_order(priority,count,order);}
int native_priority(unsigned type,unsigned subtype,unsigned frame){
    scd_object_view o={0,0,type,subtype,0,frame};return scd_ppz_priority(o);
}
/* The priority of a view whose flags bits 5-7 carry the actor's sprpri. */
int native_priority_flags(unsigned type,unsigned subtype,unsigned flags){
    scd_object_view o={0,0,type,subtype,flags,0};return scd_ppz_priority(o);
}
#ifdef SCD_ORDER_TEST_MAIN
int main(void){
    FILE *f=fopen("build/sprite-order/retail-cases.bin","rb");assert(f);
    unsigned cases=0;int n;
    uint8_t priorities[SCD_DRAW_CAPACITY],expected[SCD_DRAW_CAPACITY],guard[SCD_DRAW_CAPACITY+2];
    while((n=fgetc(f))!=EOF){
        assert(n<=SCD_DRAW_CAPACITY);
        assert(fread(priorities,1,n,f)==(unsigned)n && fread(expected,1,n,f)==(unsigned)n);
        memset(guard,0xa5,sizeof(guard));assert(native_order(priorities,n,guard+1)==n);
        assert(guard[0]==0xa5 && guard[n+1]==0xa5 && !memcmp(guard+1,expected,n));cases++;
    }
    fclose(f);assert(cases>=500);
    /* Native capacity intentionally does not reproduce the original 63-entry
       per-priority overflow. Every admitted native command remains drawable. */
    for(unsigned p=0;p<8;p++){
        memset(priorities,p,sizeof(priorities));memset(guard,0xa5,sizeof(guard));
        assert(native_order(priorities,SCD_DRAW_CAPACITY,guard+1)==SCD_DRAW_CAPACITY);
        for(unsigned i=0;i<SCD_DRAW_CAPACITY;i++)assert(guard[i+1]==SCD_DRAW_CAPACITY-1-i);
        assert(guard[0]==0xa5 && guard[SCD_DRAW_CAPACITY+1]==0xa5);
    }
    assert(native_order(priorities,SCD_DRAW_CAPACITY+1,guard)==-1);
    priorities[0]=8;assert(native_order(priorities,1,guard)==-1);
    assert(native_priority(255,0,0)==-1);
    printf("Sprite queue: %u retail cases; native capacity, invalid input and guards passed\n",cases);
}
#endif
