#include "EQU.H"
#include "scd_objects.h"
#include <stdio.h>
#include <string.h>

int main(void) {
    unsigned cases=0;
    for(unsigned shape=0;shape<2;shape++)for(unsigned weak=0;weak<2;weak++)
    for(unsigned flags=0;flags<4;flags++)for(int side=-1;side<=1;side+=2) {
        scd_objects_reset(1,0);
        memset(&actwk[0],0,sizeof(actwk[0]));
        sprite_status *p=&actwk[0];
        int half_width=shape?24:8,impulse=weak?2560:4096;
        p->r_no0=2;p->sprvsize=19;
        p->xposi.w.h=320+side*(half_width+8);p->yposi.w.h=300;
        p->xspeed.w=-side*512;
        scd_objects_spawn(SCD_OBJ_SPRING,320,300,(shape?8:4)|(weak?2:0),flags);
        scd_objects_step(320+side*(half_width+10),300);
        int vx=(shape?impulse*181/256:impulse)*(flags&1?-1:1);
        int vy=shape?impulse*181/256*(flags&2?1:-1):0;
        if(scd_objects_get().springs!=1 || p->xspeed.w!=vx || p->yspeed.w!=vy) {
            fprintf(stderr,"Spring side contact failed: shape=%u weak=%u flags=%u side=%d launches=%u velocity=%d,%d expected=%d,%d\n",
                shape,weak,flags,side,scd_objects_get().springs,p->xspeed.w,p->yspeed.w,vx,vy);
            return 2;
        }
        p->xposi.w.h=320+side*(half_width+8);p->yposi.w.h=300;
        p->xspeed.w=-side*512;p->yspeed.w=0;
        scd_objects_step(320+side*(half_width+10),300);
        /* Retail ObjSpring_Anim_* only animates: a cooling spring cannot
           move or stop Sonic. R71B's adjacent springs expose this at seq2540. */
        if(scd_objects_get().springs!=1 || p->xposi.w.h!=320+side*(half_width+8) ||
           p->yposi.w.h!=300 || p->xspeed.w!=-side*512 || p->yspeed.w!=0){
            fprintf(stderr,"Cooling spring changed contact state: shape=%u weak=%u flags=%u side=%d\n",shape,weak,flags,side);
            return 2;
        }
        cases++;
    }
    /* RIDECHK.C hitchk: the side band is half width + 10, so a player held
       flush against a wall still pushes a spring set 18 pixels away; hit_x
       ignores side hits on a spring while the player is in the air. */
    for(unsigned air=0;air<2;air++) {
        scd_objects_reset(1,0);
        memset(&actwk[0],0,sizeof(actwk[0]));
        sprite_status *p=&actwk[0];
        p->r_no0=2;p->sprvsize=19;p->cddat=air?2:0;
        p->xposi.w.h=302;p->yposi.w.h=300;p->xspeed.w=12;
        scd_objects_spawn(SCD_OBJ_SPRING,320,300,4,1);
        scd_objects_step(302,300);
        if(scd_objects_get().springs!=!air || (!air && p->xspeed.w!=-4096)) {
            fprintf(stderr,"Spring flush contact failed: air=%u launches=%u velocity=%d\n",air,scd_objects_get().springs,p->xspeed.w);
            return 2;
        }
        cases++;
    }
    /* R32D's spring at (848,760) launches through the spin tag at (848,752).
       The original clears the rolling flag on contact, then the tag restores
       animation 2. Without the ride_on_set transition, animation 16 persists. */
    scd_objects_reset(1,0);
    memset(&actwk[0],0,sizeof(actwk[0]));
    sprite_status *p=&actwk[0];
    p->actno=1;p->r_no0=2;p->xposi.w.h=853;p->yposi.w.h=738;
    p->yspeed.w=4096;p->cddat=6;p->sprvsize=14;p->sprhs=7;p->mstno.b.h=2;
    if(scd_objects_spawn(SCD_OBJ_SPRING,848,760,0,0)<0 ||
       scd_objects_spawn(SCD_OBJ_SPIN_TAG,848,752,1,0)<0)return 2;
    scd_objects_step(853,722);
    if(p->yposi.w.h!=746 || p->yspeed.w!=-4096 || p->cddat!=6 ||
       p->sprvsize!=14 || p->mstno.b.h!=2 || scd_objects_get().springs!=1){
        fprintf(stderr,"R32D spring/spin-tag state failed: y=%d vy=%d flags=%u radius=%u animation=%u\n",
                p->yposi.w.h,p->yspeed.w,p->cddat,p->sprvsize,p->mstno.b.h);
        return 2;
    }
    cases++;
    /* R72C seq504: vertical flip changes diagonal launch direction, not
       top solidity (ObjSpring_Main_Diag always calls SolidObject). */
    scd_objects_reset(1,0);memset(&actwk[0],0,sizeof(actwk[0]));
    p=&actwk[0];p->actno=1;p->r_no0=2;p->xposi.w.h=22;p->yposi.w.h=462;
    p->xspeed.w=-2392;p->yspeed.w=112;p->mspeed.w=942;p->cddat=6;
    p->sprvsize=14;p->sprhs=7;p->mstno.b.h=2;
    if(scd_objects_spawn(SCD_OBJ_SPRING,16,464,8,2)<0)return 2;
    scd_objects_step(22,462);
    if(p->xposi.w.h!=14 || p->yposi.w.h!=425 || p->xspeed.w!=2896 ||
       p->yspeed.w!=2896 || p->mspeed.w!=-2392 || p->cddat!=2 || scd_objects_get().springs!=1){
        fprintf(stderr,"Flipped diagonal top contact failed: xy%d,%d velocity%d,%d speed%d flags%u\n",
                p->xposi.w.h,p->yposi.w.h,p->xspeed.w,p->yspeed.w,p->mspeed.w,p->cddat);return 2;
    }
    cases++;
    printf("%u spring side-contact cases passed: both sides, flips, strengths, cooldown, flush and airborne\n",cases);
    return 0;
}
