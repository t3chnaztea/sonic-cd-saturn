/* Compare production QQ/SS boundary events with untouched SCRCHK.C. */
#include "../src/camera_v.c"
#include <stdio.h>
#include <string.h>
void scrchk(void);
typedef struct { short down,target,left,next_left; unsigned char moving; } bounds;
static bounds state(void){return (bounds){scralim_down,scralim_n_down,scralim_left,scralim_n_left,limmoveflag};}
static void restore(bounds s){scralim_down=s.down;scralim_n_down=s.target;scralim_left=s.left;scralim_n_left=s.next_left;limmoveflag=s.moving;}
static unsigned scroll_calls;
static void unexpected_scroll(void){scroll_calls++;}
int main(void){
    unsigned checks=0;
    const short xs[]={0,2351,2352,3519,3520,3599,3600,12000};
    const short bottoms[]={0,285,287,288,289,291,504,528,784,1296,1808};
    const short cameras[]={0,284,288,524,1295,1296,1808};
    for(unsigned zone=3;zone<=5;zone+=2)for(unsigned act=0;act<3;act++)
    for(unsigned x=0;x<sizeof(xs)/sizeof(*xs);x++)for(unsigned b=0;b<sizeof(bottoms)/sizeof(*bottoms);b++)
    for(unsigned c=0;c<sizeof(cameras)/sizeof(*cameras);c++)for(unsigned flags=0;flags<8;flags++){
        memset(&actwk[0],0,sizeof(actwk[0]));stageno.b.h=zone;stageno.b.l=act;
        actwk[0].xposi.w.h=xs[x];actwk[0].cddat=(flags&1)?2:0;actwk[0].mstno.b.h=(flags&2)?43:0;
        bossflag=(flags&4)?1:0;scra_v_posit.w.h=cameras[c];scralim_right=11000;
        bounds initial={bottoms[b],123,0,0,0};restore(initial);scrchk();bounds original=state();
        restore(initial);scd_camera_v_select(zone,act,0);if(zone==3)scrchk_r5();else scrchk_r7();bounds native=state();
        if(native.down!=original.down || native.target!=original.target || native.left!=original.left ||
           native.next_left!=original.next_left || native.moving!=original.moving){
            fprintf(stderr,"FAIL: bounds zone%u act%u x%d bottom%d camera%d flags%u native%d/%d original%d/%d\n",zone,act,xs[x],bottoms[b],cameras[c],flags,native.down,native.target,original.down,original.target);return 1;
        }
        checks++;
    }
    printf("PASS: QQ/SS camera boundaries match original SCRCHK.C in %u cases\n",checks);
    /* GAME.C game, death branch: pin both bounds without running scroll.
       Retain the camera's fractional position as well as its integer Y. */
    unsigned dead_checks=0;
    const unsigned char dead_states[]={6,8,10,255};
    for(unsigned zone=0;zone<6;zone++)for(unsigned act=0;act<3;act++)
    for(unsigned d=0;d<sizeof(dead_states);d++)for(unsigned stopped=0;stopped<2;stopped++)
    for(unsigned c=0;c<sizeof(cameras)/sizeof(*cameras);c++){
        scd_camera_v_select(zone,act,0);scroll_h=scroll_v=unexpected_scroll;scroll_calls=0;
        actwk[0].r_no0=dead_states[d];scroll_start.b.h=stopped;
        scra_v_posit.l=(int)cameras[c]*65536+12345;scra_h_posit.l=12345678;
        scralim_down=-123;scralim_n_down=2345;
        int vertical=scra_v_posit.l,horizontal=scra_h_posit.l;
        int result=scd_camera_v_step();
        if(result!=cameras[c] || scralim_down!=cameras[c] || scralim_n_down!=cameras[c] ||
           scra_v_posit.l!=vertical || scra_h_posit.l!=horizontal || scroll_calls){
            fprintf(stderr,"FAIL: dead camera zone%u act%u state%u stopped%u Y%d bounds%d/%d scroll%u\n",
                    zone,act,dead_states[d],stopped,cameras[c],scralim_down,scralim_n_down,scroll_calls);return 1;
        }
        dead_checks++;
    }
    printf("PASS: dead camera pins both bounds and freezes scroll in %u cases\n",dead_checks);return 0;
}
