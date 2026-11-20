/* Bottom death bound: src/player.c limitchk block vs original PLAYER.C limitchk
   (both extracted verbatim by tools/test-limit.sh), including the mstno 43
   (giving up) path that sets r_no0=6 without playdieset. */
#include "EQU.H"
#include <stdio.h>
static int dies;
short playdieset(sprite_status *p){dies++;p->r_no0=6;return 0;}
static int records;
static void scd_objects_death_record(void){records++;}
static void original(void){
#include "original_limit.inc"
}
static void native(sprite_status *p){
#include "native_limit.inc"
}
int main(void){
    unsigned n=0,bad=0,kills=0;
    for(int down=256;down<=1808;down+=8)for(int y=-300;y<=2100;y++)for(int m=0;m<2;m++)for(int r=2;r<=4;r+=2){
        sprite_status s={0};s.yposi.w.h=y;s.xposi.w.h=600;s.mstno.b.h=m?43:0;s.r_no0=r;
        scralim_down=down;scralim_left=0;scralim_right=10000;
        actwk[0]=s;dies=0;original();sprite_status o=actwk[0];int od=dies;
        actwk[0]=s;dies=0;records=0;native(&actwk[0]);sprite_status v=actwk[0];int vd=dies;
        n++;kills+=o.r_no0==6;
        if(o.r_no0!=v.r_no0 || od!=vd || o.yposi.w.h!=v.yposi.w.h || (v.r_no0==6)!=(records==1)){
            if(bad++<5)printf("down=%d y=%d m=%d r=%d: original r_no0=%d die=%d native r_no0=%d die=%d rec=%d\n",down,y,m?43:0,r,o.r_no0,od,v.r_no0,vd,records);}
    }
    printf("%s: %u cases, %u deaths, %u mismatches\n",bad?"FAIL":"PASS",n,kills,bad);return bad!=0;
}
