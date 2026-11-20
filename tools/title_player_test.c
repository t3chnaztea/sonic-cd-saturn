/* Real player/objects plus title card, using the Saturn pre-update lock order.
   Emits clock/input observations for comparison with the original CPU fixture. */
#include <assert.h>
#include <stdio.h>
#include "scd_player.h"
#include "scd_objects.h"
#include "world.h"
#include "title_card.h"
static unsigned char data[300000],collision[9472];
int main(void){
    for(unsigned act=0;act<3;act++)for(unsigned era=act==2?2:0;era<4;era++){
        char path[100];
        if(act)snprintf(path,sizeof(path),"assets/generated/ppz1%u%c.bin",act+1,'A'+era);
        else snprintf(path,sizeof(path),"assets/generated/ppz%u.bin",era);
        FILE *f=fopen(path,"rb");assert(f);size_t n=fread(data,1,sizeof(data),f);assert(feof(f));fclose(f);
        stage_t stage;assert(!stage_open(&stage,data,n));
        if(act)snprintf(path,sizeof(path),"assets/generated/collision1%u%c.bin",act+1,'A'+era);
        else snprintf(path,sizeof(path),"assets/generated/collision%u.bin",era);
        f=fopen(path,"rb");assert(f);assert(fread(collision,1,sizeof(collision),f)==sizeof(collision));fclose(f);
        scd_player_act(act);scd_objects_act(act);scd_world_act(act);
        assert(!scd_player_init(&stage,collision,sizeof(collision),era));scd_world_reset(era);
        scd_title_card_start(act);
        for(unsigned tick=1;tick<=240;tick++){
            int locked=scd_title_card_locked();unsigned buttons=locked?0:SCD_RIGHT;
            scd_player_hold_clock(locked);scd_player_step(buttons);scd_title_card_step();
            scd_player_state p=scd_player_get();
            printf("%u %u %u %d %d %u %u %d %d\n",act,era,tick,locked,
                scd_title_card_locked(),p.elapsed,buttons,p.x,p.vx);
        }
        /* A temporary release must never undo a goal/capsule clock stop. */
        unsigned stopped=scd_player_get().elapsed;scd_player_stop_clock();
        for(unsigned i=0;i<8;i++){
            scd_player_hold_clock(i&1);scd_player_step(0);
            assert(scd_player_get().elapsed==stopped);
        }
        /* Initialization must clear both clock locks, even after a held tick. */
        scd_player_hold_clock(1);
        assert(!scd_player_init(&stage,collision,sizeof(collision),era));
        scd_player_step(0);assert(scd_player_get().elapsed==1);
    }
    return 0;
}
