/* F4 defeat notification guards. The route trace proves the earned second
   attack; these cases set specific object states directly. */
#include "../src/player_plus.c"
#include <assert.h>
#include <stdio.h>

static void ready(void){
    scd_plus_place();
    active=SCD_PLUS_HOMING;
    homing_used=1;homing_left=5;homing_tracked=1;
    target=&actwk[1];target_actno=SCD_OBJ_ANTON;
    actwk[1].actno=SCD_OBJ_ANTON;
    actwk[0].cddat=6;actwk[0].actfree[0]=actwk[0].actfree[2]=0;
    actwk[0].xspeed.w=100;actwk[0].yspeed.w=250;
    homing_vx=100;homing_vy=200;
    swdata.b.l=0;
}

int main(void){
    ready();actwk[0].cddat=4;
    scd_plus_enemy_defeat(1,100,200);
    assert(!homing_defeated && homing_vy==200); /* grounded rolling */

    ready();scd_plus_enemy_defeat(2,100,200);
    assert(!homing_defeated && homing_vy==200); /* wrong victim */

    ready();scd_plus_enemy_defeat(1,100,201);
    assert(!homing_defeated && homing_vy==200); /* earlier impulse */

    ready();actwk[0].actfree[2]=4;
    scd_plus_enemy_defeat(1,100,200);
    assert(!homing_defeated && homing_vy==200); /* object control */

    ready();scd_plus_enemy_defeat(1,100,200);
    assert(homing_defeated && homing_vy==250);
    actwk[0].yspeed.w=300;
    scd_plus_enemy_defeat(1,100,250);
    assert(homing_defeated && homing_vy==250); /* one notification */

    ready();actwk[0].yspeed.w=200;actwk[1].actno=SCD_OBJ_EXPLOSION;
    swdata.b.l=SCD_JUMP;scd_plus_air();
    assert(homing_used && !homing_left && !homing_defeated &&
           actwk[0].xspeed.w==100 && actwk[0].yspeed.w==200); /* no defeat or air dash */

    ready();scd_plus_enemy_defeat(1,100,200);
    actwk[0].actfree[2]=4;actwk[1].actno=SCD_OBJ_EXPLOSION;
    swdata.b.l=SCD_JUMP;scd_plus_air();
    assert(homing_used && !homing_left && !homing_defeated &&
           actwk[0].yspeed.w==250); /* takeover after defeat */

    puts("PASS: F4 defeat notification guards");
    return 0;
}
