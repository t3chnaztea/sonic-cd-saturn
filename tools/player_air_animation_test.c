/* Observe the real player adapter before animation, not a copied selector. */
#include <assert.h>
#include <stdio.h>
#include "EQU.H"
#include "scd_player.h"
#include "scd_objects.h"
#include "sonic_animation.h"
static unsigned selected,calls;
void scd_player_animation_audit(const scd_sonic_animation *before,
    const scd_sonic_animation *after,int16_t speed,uint8_t angle,uint8_t flags,uint8_t control){
    (void)after;(void)speed;(void)angle;(void)flags;(void)control;
    selected=before->animation;calls++;
}
int main(void){
    static stage_t stage;
    static unsigned char data[300000],collision[9472];
    FILE *f=fopen("assets/generated/ppz0.bin","rb");assert(f);
    size_t n=fread(data,1,sizeof(data),f);assert(feof(f));fclose(f);
    assert(!stage_open(&stage,data,n));
    f=fopen("assets/generated/collision0.bin","rb");assert(f);
    assert(fread(collision,1,sizeof(collision),f)==sizeof(collision));fclose(f);
    assert(!scd_player_init(&stage,collision,sizeof(collision),0));
    static const int velocities[]={-4096,-1,0,1,4096};
    for(unsigned animation=0;animation<60;animation++)
    for(unsigned v=0;v<5;v++)for(unsigned wind=0;wind<2;wind++)
    for(unsigned roll=0;roll<2;roll++)for(unsigned controlled=0;controlled<2;controlled++){
        scd_objects_reset(0,0);scd_player_place(500,100,0,0,2|roll*4);
        /* PLAYER.C:260 holds the previous animation when the current is on and
           the selection is 0, so a wind case needs a valid previous id. */
        actwk[0].mstno.b.h=animation;actwk[0].mstno.b.l=wind?animation:-1;
        actwk[0].actfree[2]=controlled;watercoliflag=wind;
        scd_player_velocity(0,velocities[v]);unsigned before=calls;
        scd_player_step(0);assert(calls==before+1);
        printf("selection %u %d %u %u %u %u\n",animation,velocities[v],wind,roll,controlled,selected);
    }
    /* PLAYER.C:260: current on + animation 0 selects the previous id. */
    scd_objects_reset(0,0);scd_player_place(500,100,0,0,2);
    actwk[0].mstno.b.h=0;actwk[0].mstno.b.l=5;watercoliflag=1;
    scd_player_velocity(0,0);scd_player_step(0);assert(selected==5);
    watercoliflag=0;
    /* Normal controller spring contact must leave animation 16 on ascent,
       switch exactly at nonnegative pre-update velocity, and then land. */
    scd_objects_reset(0,0);scd_player_place(80,488,0,0,2);
    assert(scd_objects_spawn(SCD_OBJ_SPRING,80,508,0,0)==0);
    for(unsigned tick=0;tick<150;tick++){
        scd_player_state before=scd_player_get();scd_player_step(0);
        scd_player_state after=scd_player_get();
        printf("spring %u %d %u %u %u %u %u %d %d\n",tick,before.vy,before.flags,
            before.animation,selected,after.animation,after.mapping,after.x,after.y);
    }
}
