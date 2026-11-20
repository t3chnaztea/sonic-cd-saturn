/* Host check of src/ending.h against IPX.asm GameDone (CD Initial Program/IPX.asm:301-330):
     cmpi.b #%01111111,gameGoodFutures / beq GoodEnding
     cmpi.b #%01111111,gameTimeStones  / beq GoodEnding
     BadEnding: endingID 0
   Every pair of byte values, plus the four named cases.
   clang -std=gnu11 -Wall -Wextra -Werror -Isrc tools/ending_test.c -o build/ending_test */
#include <stdio.h>
#include <string.h>
#include "ending.h"

static int ipx_good(unsigned char futures,unsigned char stones){return futures==0x7F || stones==0x7F;}

int main(void){
    unsigned bad=0;
    for(unsigned f=0;f<256;f++)for(unsigned s=0;s<256;s++)
        if(!!scd_ending_good(f,s)!=ipx_good((unsigned char)f,(unsigned char)s))bad++;
    const struct{const char *name;unsigned futures,stones;int good;}cases[]={
        {"7 good futures",0x7F,0,1},{"7 time stones",0,0x7F,1},{"neither (6 + 6)",0x3F,0x3F,0},{"both",0x7F,0x7F,1}};
    for(unsigned i=0;i<4;i++)if(scd_ending_good(cases[i].futures,cases[i].stones)!=cases[i].good){printf("FAIL: %s\n",cases[i].name);bad++;}
    if(strcmp(scd_ending_message(1),"YOU'RE TOO COOL!") || strcmp(scd_ending_message(0),"TRY AGAIN"))bad++;
    printf("%s: ending choice %u mismatches over 65536 pairs and 4 named cases\n",bad?"FAIL":"PASS",bad);
    return bad!=0;
}
