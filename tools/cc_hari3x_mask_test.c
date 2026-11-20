/* CC1 Present MECASNC.C hari3x spikes (colino 134) against Sonic's two CC contact
   scans. The generated COLI3 pcol (boss_3.c, player.c's pcol call) scans
   actwk[32..127], that is native pool 31 and up; cc_scan (objects_zone_ops.inc)
   scans every pool actor. A spike in pool 31+ was tested by both, so its hurt
   came from Sonic's pcol, before stream(), instead of cc_scan, after it (where
   HARIR3 and the CC enemies hurt). A 32-ring spill at x 1530-1560 heading left
   puts the CC1A spikes in pool 58-59. Each case puts one spike on Sonic in pool
   P and checks: the pcol window leaves Sonic unhurt, then one objects step
   hurts him exactly once. */
#include <stdio.h>
#include <stdlib.h>
#include "../src/objects.c"
#include "act.h"
short pcol(sprite_status *p); /* src/boss.c: the zone pcol, COLI3 in CC (boss_3.c) */
static unsigned checks;
#define REQUIRE(v) do{checks++;if(!(v)){fprintf(stderr,"FAIL pool %u line %d: %s\n",pool_index,__LINE__,#v);exit(1);}}while(0)
static unsigned pool_index;
static void run(unsigned want){
    scd_objects_zone(1);scd_objects_act(0);memset(actwk,0,sizeof(sprite_status)*128);scd_objects_reset(0,0);
    const int x=1048,y=1008;
    /* Fillers off to the side, so the spike takes pool WANT. */
    for(unsigned n=0;n<want;n++)REQUIRE(scd_objects_spawn(SCD_OBJ_RING,x+400,y,0,0)==(int)n);
    int i=scd_objects_spawn(SCD_OBJ_HARI3X,x,y,2,0);pool_index=(unsigned)i;REQUIRE(i==(int)want);
    sprite_status *o=&actwk[i+1],*p=actwk;
    actwk[0].r_no0=2;actwk[0].sprvsize=19;actwk[0].xposi.w.h=x;actwk[0].yposi.w.h=y-40;
    scd_act_camera(x-160,y-112);
    scd_objects_step(x,y-40);                     /* init: colino 134, sprite pass */
    REQUIRE(o->colino==134 && o->r_no0==2);
    o->actflg|=128;                               /* on screen, as DrawObject leaves it */
    p->r_no0=2;p->sprvsize=19;p->patno=0;p->actfree[2]=0;p->xposi.w.h=x;p->yposi.w.h=y;scd_word_set(p,26,0);
    scd_player_inventory(5,0);
    unsigned hits=stats.hits;
    scd_objects_collision_begin();pcol(p);scd_objects_collision_end();
    REQUIRE(p->r_no0==2 && stats.hits==hits);     /* Sonic's pcol does not test it */
    REQUIRE(o->colino==134);                      /* the mask is restored */
    scd_objects_step(x,y);
    REQUIRE(p->r_no0==4 && stats.hits==hits+1);   /* cc_scan hurts once */
}
int main(void){
    unsigned cases=0;
    for(unsigned want=0;want<64;want+=3){run(want);cases++;}
    run(31);run(58);cases+=2;
    printf("PASS: cc hari3x mask %u cases, %u assertions\n",cases,checks);
    return 0;
}
