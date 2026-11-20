/* Compare every table word with the untouched scalar raster calculation. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "background.h"
static unsigned checks;
static void check(unsigned id,int x,int y,unsigned frame,int32_t ramp,unsigned count){
    int32_t actual[258],expected[258];
    memset(actual,0xa5,sizeof(actual));memcpy(expected,actual,sizeof(actual));
    for(unsigned i=0;i<count;i++)expected[i+1]=(scd_background_raster_x(id,x,y+(int)i,frame,ramp)&511)*65536;
    scd_background_lines(id,x,y,frame,ramp,actual+1,count);
    assert(!memcmp(actual,expected,sizeof(actual)));checks++;
}
int main(void){
    static const unsigned ids[]={0,1,2,3,4,5,6,7,10,11};
    static const int xs[]={0,1,7,8,7996,16064,-1,-16064};
    static const unsigned frames[]={0,1,31,65535,65536,1234567};
    for(unsigned id=0;id<10;id++)for(int y=-1;y<=2049;y++)
        check(ids[id],xs[(unsigned)(y+1)%8],y,frames[(unsigned)(y+1)%6],(y%3-1)*32768,224);
    /* Every start/count around all band boundaries, wrap and partial tables. */
    for(int y=-33;y<545;y++)for(unsigned count=0;count<=256;count++)
        check(4,7996,y,3675,0,count);
    for(int y=-33;y<2081;y++)for(unsigned count=0;count<=256;count++)
        check(0,7996,y,3675,-32768,count);
    uint32_t random=0x14572398;
    for(unsigned i=0;i<20000;i++){
        random=random*1664525u+1013904223u;
        check(ids[i%10],(int)(random%32769)-16384,(int)((random>>10)%4097)-2048,
              random%1000000,(int32_t)(random%131073)-65536,random%257);
    }
    printf("Raster table: %u exact scalar/table comparisons, all ten layouts, boundaries, wraps and guards pass\n",checks);
}
