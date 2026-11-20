/* Enemy chain score: src/objects.c enemy kill scoring vs original R1/COLI1.C
   (both extracted verbatim by tools/test-chain-score.sh). 40 kills in a row,
   then a landing (jumpcolsub clears emyscorecnt) and another run. */
#include <stdio.h>
short emyscorecnt;
static unsigned native_points;
static void scd_player_points(unsigned n){native_points=n;}
static unsigned native_kill(void){
#include "native_kill.inc"
    return native_points;
}
static unsigned short escoretbl[4]={10,20,50,100};
static unsigned original_kill(void){
    short iScoreCntwk,iScoreData;short fake[40]={0};short *pColliAct=fake;(void)pColliAct;
#include "original_kill.inc"
    return (unsigned)iScoreData*10u;
}
int main(void){
    unsigned bad=0,total_n=0,total_o=0;
    for(int run=0;run<2;run++){
        short n_cnt=0,o_cnt=0;
        for(int k=0;k<40;k++){
            emyscorecnt=n_cnt;unsigned a=native_kill();n_cnt=emyscorecnt;
            emyscorecnt=o_cnt;unsigned b=original_kill();o_cnt=emyscorecnt;
            total_n+=a;total_o+=b;
            if(a!=b || n_cnt!=o_cnt){if(bad++<5)printf("kill %d: native %u (cnt %d) original %u (cnt %d)\n",k,a,n_cnt,b,o_cnt);}
        }
    }
    printf("%s: 80 kills, native %u points, original %u points, %u mismatches\n",bad?"FAIL":"PASS",total_n,total_o,bad);
    return bad!=0;
}
