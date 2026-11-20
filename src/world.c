/* PPZ1 travel thresholds and gating from Sonic/Main.asm ObjSonic_TimeWarp. */
#include "world.h"
#include "act.h"
static scd_world_state state;
static unsigned current_act,current_zone;
void scd_world_act(unsigned act){current_act=act;}
void scd_world_zone(unsigned zone){current_zone=zone;}
void scd_world_reset(unsigned era){scd_player_warp_clear();state=(scd_world_state){.era=era,.destination=-1,.good_future=era==2};}
/* ObjTimePost_Main writes direction after Sonic has run; it never resets an
   active timer. Callers deliver contacts after this update's world step. */
void scd_world_activate(int direction){if(!scd_act_get().goal && state.ticks<210 && (direction==-1 || direction==1)){state.direction=direction;}}
void scd_world_generator_destroyed(void){state.good_future=1;}
scd_world_state scd_world_get(void){return state;}
/* src/title_card.c: the loaded program picks the card's PLC 2 wait. */
int scd_title_card_program(unsigned *zone,unsigned *act,unsigned *era){*zone=current_zone;*act=current_act;*era=state.era;return 1;}
void scd_world_arrived(unsigned era){scd_player_warp_clear();state.era=era;state.direction=0;state.ticks=0;state.destination=-1;state.transitions++;}
static void cancel(void){scd_player_warp_clear();if(state.direction)state.cancelled++;state.direction=0;state.ticks=0;state.destination=-1;}
void scd_world_abort(void){cancel();}
int scd_world_step_vblanks(scd_player_state p,unsigned elapsed){
    /* VInt_Level advances timeWarpTimer once per VBlank, including VBlanks
       where the level does not finish a gameplay update. */
    if(!elapsed)elapsed=1;
    if(scd_act_get().goal){cancel();return -1;}
    /* Hurt and death (oRoutine 4+) do not run ObjSonic_TimeWarp, and only the
       goal, level start and the slow-speed stop clear timeWarpDir (the HUD
       sign stays); VInt_Level keeps counting a running timer. */
    if(p.routine>=4){if(state.ticks)state.ticks+=elapsed;return -1;}
    /* ObjSonic_TimeWarp: only PPZ Act 1 past/future stop warping before X $900. */
    if(!current_zone && !current_act && state.era!=0 && p.x/65536<0x900){cancel();return -1;}
    /* A charge returns before the 230 test, but VInt_Level (Level/Main.asm:974)
       keeps counting a running timer: the warp waits for the release. */
    if(p.charge){if(state.ticks)state.ticks+=elapsed;return -1;}
    if(!state.direction)return -1;
    int speed=p.speed<0?-(int)p.speed:p.speed;
    if(!scd_act_get().goal && state.ticks<210 && speed<0x600){if(state.ticks>=90)cancel();else state.ticks=0;return -1;}
    if(!state.ticks)state.ticks=1;
    if(state.ticks>=210 && state.destination<0){
        int time=state.era==1?0:state.era==0?1:2;
        time+=state.direction;if(time<0)time=0;if(time>2)time=2;
        state.destination=time==0?1:time==1?0:state.good_future?2:3;
        /* ObjSonic_TimeWarp's SaveTimeWarpData at the same 210 test, before
           the next update moves Sonic (retail PPZ1C: the camera stops and the
           discs despawn on that update). */
        scd_player_warp_save();
    }
    if(state.ticks>=230)return state.destination;
    state.ticks+=elapsed;return -1;
}
int scd_world_step(scd_player_state p){return scd_world_step_vblanks(p,1);}
