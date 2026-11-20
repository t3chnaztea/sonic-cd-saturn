/* R4 PLAYSUB4.C wave (the water-surface shimmer GAME4.C:635 installs in
   actwk[32], the first dynamic slot) versus src/objects_tt_wave.inc, every
   Tidal Tempest act and era: the native reset must create it in the first
   pool slot (actor 1), era changes must recreate it,
   and each update it must match the compiled original while the camera and
   the water level move. tools/test-tt-actors.sh builds it (name "wave"). */
#include "tt_actor_fixture.h"
void wave(sprite_status*);
int main(void){
    static const unsigned eras[3][4]={{0,1,2,3},{0,1,2,3},{2,3,9,9}};
    unsigned views_seen=0,respawns=0,cases=0;
    for(unsigned act=0;act<3;act++)for(unsigned e=0;e<4 && eras[act][e]!=9;e++){
        unsigned era=eras[act][e];load(act,era);cases++;
        scd_objects_reset(era,0);plpower_b=1;
        REQUIRE(actwk[1].actno==SCD_OBJ_WAVE && !actwk[1].r_no0);
        memset(&actwk[100],0,sizeof(actwk[100]));actwk[100].actno=SCD_OBJ_WAVE;
        for(frame=0;frame<600;frame++){
            if(frame==300){
                /* A time warp reloads the program: GAME4 installs a new wave. */
                scd_objects_change_era(era);respawns++;
                REQUIRE(actwk[1].actno==SCD_OBJ_WAVE && !actwk[1].r_no0);
                memset(&actwk[100],0,sizeof(actwk[100]));actwk[100].actno=SCD_OBJ_WAVE;
            }
            int cx=512+frame*3,cy=900;
            camera_on(cx,cy);
            waterposi=(short)(cy-40+(int)(frame%96)-48);
            actwk[0]=player(cx,cy,0);
            wave(&actwk[100]);
            actwk[0]=player(cx,cy,0);
            scd_objects_step(cx,cy);
            compare(&actwk[1],&actwk[100]);
            scd_object_view v[SCD_OBJECT_CAPACITY];unsigned n=scd_objects_views(v,SCD_OBJECT_CAPACITY);
            int listed=0;
            for(unsigned k=0;k<n;k++)if(v[k].type==SCD_OBJ_WAVE){
                listed=1;REQUIRE(v[k].frame==actwk[1].patno && v[k].x==actwk[1].xposi.w.h && v[k].y==actwk[1].yposi.w.h);
                REQUIRE((v[k].flags>>5)==actwk[100].sprpri && (v[k].flags&3)==(actwk[100].actflg&3));
            }
            REQUIRE(listed);views_seen++;updates++;
        }
    }
    REQUIRE(cases==10 && respawns==10 && views_seen==6000);
    printf("PASS: wave %u assertions; %u act/era cases; %u updates; %u era reloads; view listed every update\n",checks,cases,updates,respawns);
    return 0;
}
