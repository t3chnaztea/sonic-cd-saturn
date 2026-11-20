/* Native horizontal camera (src/camera_v.c: PLAYER.C scr_h and the compiled SCR*.C
   scroll_h) against a retail trace from tools/camera_retail.py HOUTPUT. The camera
   and camXCenter start from the retail values at the first update. Every later
   update runs scr_h on the previous update's player state (play00move calls it
   before the player moves), then scroll_h on this update's X and bounds, and must
   produce the retail camXCenter and cameraX (16.16) exactly. GAME.C game skips
   scroll() while Sonic is dead (r_no0 >= 6); a restart (the level frame counter
   going back) resynchronises from the retail values, as playposiset does.
   usage: camera_h_retail_test ZONE ACT ERA TRACE */
#include "EQU.H"
#include "camera_v.h"
#include <stdio.h>
#include <stdlib.h>
/* PLAYER.C scr_h, compiled from src/player.c's text (tools/test-camera.sh). */
void scr_h(void);

int main(int argc,char **argv){
    if(argc<5)return 2;
    unsigned zone=atoi(argv[1]),act=atoi(argv[2]),era=atoi(argv[3]);
    FILE *f=fopen(argv[4],"r");if(!f){perror(argv[4]);return 2;}
    scd_camera_v_select(zone,act,era);
    long frame,camera,x;unsigned ctrl,flags,routine,pad;int gvel,left,right,center;
    long px=0,pframe=-1;unsigned pctrl=0,proutine=0;int pgvel=0;
    unsigned checked=0,bad=0,bad_center=0,moved=0,shifted=0;int started=0;
    while(fscanf(f,"%ld %ld %ld %u %d %u %u %d %d %d %u",&frame,&camera,&x,&ctrl,&gvel,&flags,&routine,&left,&right,&center,&pad)==11){
        if(frame<1)continue;
        if(frame<=pframe)started=0;
        pframe=frame;
        if(!started){scra_h_posit.l=(int)camera;scra_hline=(short)center;started=1;}
        else {
            actwk[0].xposi.l=(int)px;actwk[0].actfree[2]=(unsigned char)pctrl;actwk[0].mspeed.w=(short)pgvel;
            if(proutine==2)scr_h();
            if(scra_hline!=(short)center){
                if(bad_center<5)fprintf(stderr,"update %ld: native center %d retail %d (gvel %d ctrl %02x x %ld)\n",frame,scra_hline,center,pgvel,pctrl,px>>16);
                bad_center++;scra_hline=(short)center;
            }
            if(center!=160)shifted++;
            actwk[0].xposi.l=(int)x;scralim_left=(short)left;scralim_right=(short)right;
            int before=scra_h_posit.l;
            if(routine<6)scd_camera_h_step();
            checked++;if(scra_h_posit.l!=before)moved++;
            if(scra_h_posit.l!=(int)camera){
                if(bad<5)fprintf(stderr,"update %ld: native x %d.%04x retail %d.%04x (sonic %ld center %d bounds %d..%d)\n",
                    frame,scra_h_posit.w.h,(unsigned short)scra_h_posit.w.l,(short)(camera>>16),(unsigned)(camera&0xffff),x>>16,center,left,right);
                bad++;scra_h_posit.l=(int)camera;
            }
        }
        px=x;pctrl=ctrl;pgvel=gvel;proutine=routine;
    }
    printf("%s: %u updates checked (%u moved, %u off-centre), %u camera mismatches, %u centre mismatches\n",argv[4],checked,moved,shifted,bad,bad_center);
    return bad||bad_center||!checked||!moved?1:0;
}
