/* Horizontal camera dedupe fixture: for all seventy programs, src/camera_v.c with the
   shared ch<n>_ scroll_h texts (build/probe-source/camera_v_variants.inc) against that
   program's own unshared copy (build/camera/camera_h_programs.c), over sweeps of
   Sonic's X, the PLAYER.C scr_h centre (96..224) and the left/right bounds. The
   compared state is scra_h_posit, scra_hz, scra_h_count and scrflaga. */
#include "EQU.H"
#include "camera_v.h"
#include <stdio.h>
#include <string.h>

extern void (*const camera_h_programs[70])(void);
extern const unsigned char camera_h_program_key[70][3];
typedef struct{int cam;short hz;unsigned char count;unsigned short flags;}state;
static state grab(void){return (state){scra_h_posit.l,scra_hz,scra_h_count,scrflaga.w};}
static void put(const state *s){scra_h_posit.l=s->cam;scra_hz=s->hz;scra_h_count=s->count;scrflaga.w=s->flags;}

int main(void){
    unsigned long checks=0,bad=0,moved=0;
    static const short bounds[][2]={{0,11927},{0,7319},{2808,7319},{512,640}};
    for(unsigned k=0;k<70;k++){
        unsigned z=camera_h_program_key[k][0],a=camera_h_program_key[k][1],e=camera_h_program_key[k][2];
        scd_camera_v_select(z,a,e);
        for(unsigned b=0;b<4;b++)for(unsigned c=0;c<5;c++){
            scralim_left=bounds[b][0];scralim_right=bounds[b][1];scra_hline=(short)(96+c*32);
            state s={.cam=(bounds[b][0]+40)<<16};
            int x=bounds[b][0]+200;
            for(unsigned f=0;f<600;f++){
                /* Sonic runs right, stops, reverses and teleports across the bounds */
                x+=(int)((f%150)<75?(f%13)+1:-(int)(f%11)-1)*(1+(f/150)%3);
                if(f%199==0)x=bounds[b][0]+(int)((f*7919u)%(unsigned)(bounds[b][1]-bounds[b][0]+400))-100;
                actwk[0].xposi.l=x<<16;
                put(&s);scd_camera_h_step();state n=grab();
                put(&s);camera_h_programs[k]();state o=grab();
                checks++;if(o.cam!=s.cam)moved++;
                if(memcmp(&n,&o,sizeof(n))){if(!bad)fprintf(stderr,"program %u (%u,%u,%u) centre %d bounds %d..%d update %u: native %08x original %08x\n",k,z,a,e,scra_hline,scralim_left,scralim_right,f,n.cam,o.cam);bad++;}
                s=o;
            }
        }
    }
    printf("camera-x dedupe: %lu updates over 70 programs, %lu moved, %lu mismatches\n",checks,moved,bad);
    return bad||!moved?1:0;
}
