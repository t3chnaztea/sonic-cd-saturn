/* Native vertical camera (src/camera_v.c over the compiled SCR*.C scroll_v) against
   a retail trace from tools/camera_retail.py. The camera starts from the retail
   camera at the first update; every later update gets that update's retail player
   Y, flags, ground velocity, routine and bounds, and must produce the retail
   cameraY exactly (16.16). usage: camera_retail_test ZONE ACT ERA TRACE */
#include "EQU.H"
#include "camera_v.h"
#include <stdio.h>
#include <stdlib.h>

int main(int argc,char **argv){
    if(argc<5)return 2;
    unsigned zone=atoi(argv[1]),act=atoi(argv[2]),era=atoi(argv[3]);
    FILE *f=fopen(argv[4],"r");if(!f){perror(argv[4]);return 2;}
    scd_camera_v_select(zone,act,era);
    long frame,camera,y;unsigned flags,routine,pad;int gvel,top,bottom,center;
    unsigned rows=0,checked=0,bad=0,exact_int=0;int started=0;
    while(fscanf(f,"%ld %ld %ld %u %d %u %d %d %d %u",&frame,&camera,&y,&flags,&gvel,&routine,&top,&bottom,&center,&pad)==10){
        rows++;
        if(frame<1)continue;
        actwk[0].yposi.l=(int)y;actwk[0].cddat=(unsigned char)flags;actwk[0].mspeed.w=(short)gvel;actwk[0].r_no0=(unsigned char)routine;
        scralim_up=(short)top;scralim_down=(short)bottom;scra_vline=(short)center;
        if(!started){scra_v_posit.l=(int)camera;started=1;continue;}
        scd_camera_v_step();
        checked++;
        if(scra_v_posit.w.h==(short)(camera>>16))exact_int++;
        if(scra_v_posit.l!=(int)camera){
            if(bad<5)fprintf(stderr,"update %ld: native %d.%04x retail %d.%04x (y %ld flags %02x gvel %d vline %d bounds %d..%d)\n",
                frame,scra_v_posit.w.h,(unsigned short)scra_v_posit.w.l,(short)(camera>>16),(unsigned)(camera&0xffff),y>>16,flags,gvel,center,top,bottom);
            bad++;scra_v_posit.l=(int)camera; /* resynchronise and keep checking */
        }
    }
    printf("%s: %u updates checked, %u camera mismatches (%u integer-exact)\n",argv[4],checked,bad,exact_int);
    return bad||!checked?1:0;
}
