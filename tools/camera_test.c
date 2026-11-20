/* Vertical camera dedupe fixture: for all seventy programs, src/camera_v.c with the
   shared cv<n>_ texts (build/probe-source/camera_v.c) against that program's own
   unshared copy (build/camera/camera_v_programs.c), over sweeps of player Y/speed,
   flags, ground speed, scra_vline and bounds, including TT2's 2048 wrap. The
   compared state is scra_v_posit, scra_vz, scra_v_count, scrflaga, limmoveflag,
   scrb_v_posit and Sonic's Y (the wrap rewrites it). */
#include "EQU.H"
#include "camera_v.h"
#include <stdio.h>
#include <string.h>

extern void (*const camera_v_programs[70])(void);
extern const unsigned char camera_v_program_key[70][3];
typedef struct{int cam,b,y;short vz;unsigned char count,lim;unsigned short flags;}state;
static state grab(void){return (state){scra_v_posit.l,scrb_v_posit.l,actwk[0].yposi.l,scra_vz,scra_v_count,limmoveflag,scrflaga.w};}
static void put(const state *s){scra_v_posit.l=s->cam;scrb_v_posit.l=s->b;actwk[0].yposi.l=s->y;scra_vz=s->vz;scra_v_count=s->count;limmoveflag=s->lim;scrflaga.w=s->flags;}

int main(void){
    unsigned long checks=0,bad=0,wraps=0;
    static const short vlines[]={96,64,128};
    static const short downs[][2]={{0,1808},{0,784},{48,1296},{0,2048}};
    for(unsigned k=0;k<70;k++){
        unsigned z=camera_v_program_key[k][0],a=camera_v_program_key[k][1],e=camera_v_program_key[k][2];
        scd_camera_v_select(z,a,e);
        for(unsigned d=0;d<4;d++)for(unsigned v=0;v<3;v++)for(unsigned fl=0;fl<8;fl++){
            scralim_up=downs[d][0];scralim_down=downs[d][1];scra_vline=vlines[v];
            state s={.cam=(downs[d][1]-120)<<16,.b=300<<16,.y=(downs[d][1]-40)<<16};
            for(unsigned f=0;f<700;f++){
                /* Sonic falls through the bottom bound and back up, at varying speed */
                int speed=((int)(f%140)-70)*48*(1+(f/140)%3);
                s.y+=speed*256;
                actwk[0].cddat=(unsigned char)((fl&1?2:0)|(fl&2?4:0));
                actwk[0].mspeed.w=(short)(fl&4?(f*37)%4400-2200:(f*13)%900-450);
                actwk[0].r_no0=2;scroll_start.b.h=0;
                put(&s);scd_camera_v_scroll();state n=grab();
                put(&s);camera_v_programs[k]();state o=grab();
                checks++;
                if(memcmp(&n,&o,sizeof(n))){if(!bad)fprintf(stderr,"program %u (%u,%u,%u) vline %d bounds %d..%d update %u: native cam %08x original %08x\n",k,z,a,e,scra_vline,scralim_up,scralim_down,f,n.cam,o.cam);bad++;}
                if(o.y!=s.y && (o.y>>16)!=(s.y>>16))wraps++;
                s=o;
            }
        }
    }
    printf("camera dedupe: %lu updates over 70 programs, %lu wraps, %lu mismatches\n",checks,wraps,bad);
    return bad?1:0;
}
