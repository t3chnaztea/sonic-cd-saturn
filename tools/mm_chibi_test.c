/* Host integration check for the R8 shrink form (chibi_flag) in the native
   player: the compiled PLAYER.C radii, the mini animator through the player
   adapter, a jump and its landing. Runs on Palmtree Panic terrain because
   the player code is zone-agnostic; BEAM.C is the only writer of chibi_flag.
   The animation itself is checked against retail by test_sonic_animation.py. */
#include "player_replay.h"
#include "scd_player.h"
#include "EQU.H"
#include <stdio.h>
#include <stdlib.h>
#define CHECK(c,...) do{if(!(c)){fprintf(stderr,"FAIL: mm chibi: " __VA_ARGS__);fputc('\n',stderr);exit(1);}}while(0)
static unsigned char *read_file(const char *name,size_t *size) {
    FILE *f=fopen(name,"rb");if(!f){perror(name);exit(2);}
    fseek(f,0,SEEK_END);*size=ftell(f);rewind(f);
    unsigned char *data=malloc(*size);if(!data || fread(data,1,*size,f)!=*size)exit(2);
    fclose(f);return data;
}
/* Mini scripts 33-40 and 48 (Animations.asm) use poses 111-126 and 6. */
static int mini_pose(unsigned m){return (m>=111 && m<=126) || m==6;}
int main(void){
    size_t n,cn;unsigned char *data=read_file("assets/generated/ppz1.bin",&n),*collision=read_file("assets/generated/collision1.bin",&cn);
    stage_t stage;CHECK(!stage_open(&stage,data,n) && !scd_player_init(&stage,collision,cn,1),"stage load");
    chibi_flag=1;
    scd_player_place(stage.start_x,stage.start_y,0,0,0);
    CHECK(actwk[0].sprvsize==10 && actwk[0].sprhs==5,"play00init radii %u/%u",actwk[0].sprvsize,actwk[0].sprhs);
    unsigned ground=0,air=0,landed=0,walk=0,run=0,curls=0;int was_air=0,jumping=0;
    for(unsigned frame=0;frame<400;frame++){
        unsigned buttons=SCD_RIGHT|((frame==200)?SCD_JUMP:0);
        scd_player_step(buttons);
        sprite_status *p=&actwk[0];
        int in_air=!!(p->cddat&2);
        if(getenv("MM_CHIBI_TRACE"))fprintf(stderr,"%u x=%d y=%d cddat=%02x r=%u/%u anim=%u pat=%u angle=%u ms=%d\n",frame,p->xposi.w.h,p->yposi.w.h,p->cddat,p->sprvsize,p->sprhs,p->mstno.b.h,p->patno,p->direc.b.h,p->mspeed.w);
        if(!in_air && !(p->cddat&4) && frame>2){
            CHECK(p->sprvsize==10 && p->sprhs==5,"frame %u standing radii %u/%u",frame,p->sprvsize,p->sprhs);
            CHECK(mini_pose(p->patno),"frame %u ground pose %u (animation %u)",frame,p->patno,p->mstno.b.h);
            ground++;walk+=p->patno>=115 && p->patno<=117;run+=p->patno==118 || p->patno==119;
        }
        if(frame==200)jumping=1;
        if(jumping && in_air && (p->cddat&4)){
            CHECK(p->sprvsize==8 && p->sprhs==5,"frame %u jump radii %u/%u",frame,p->sprvsize,p->sprhs);
            CHECK(p->patno>=124 && p->patno<=126,"frame %u jump pose %u",frame,p->patno);
            air++;
        }
        if(jumping && was_air && !in_air){CHECK(p->sprvsize==10,"frame %u landing radius %u",frame,p->sprvsize);landed++;jumping=0;}
        /* .MiniSonicRun curls Sonic on steep ground: rolling bit with 10/5 radii. */
        if(!jumping && (p->cddat&4) && p->sprvsize==10 && p->sprhs==5)curls++;
        was_air=in_air;
    }
    CHECK(ground>100 && air>10 && landed && walk && run && curls,"coverage ground %u air %u landed %u walk %u run %u curls %u",ground,air,landed,walk,run,curls);
    /* A new stage clears the flag before ObjSonic_Init (GAME.C). */
    CHECK(!scd_player_init(&stage,collision,cn,1) && !chibi_flag && actwk[0].sprvsize==19,"stage start keeps chibi");
    printf("PASS: mm chibi host: %u ground updates on mini poses (walk %u, run %u), %u mini roll-jump updates at 8/5, %u landing at 10/5, %u curled updates at 10/5; stage start clears chibi_flag\n",ground,walk,run,air,landed,curls);
    free(collision);free(data);return 0;
}
