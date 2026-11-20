/* Independent ordered subset of scddisasm:
 * Level/Wacky Workbench/Objects/Sonic/Main.asm:857-935 (TimeWarp),
 * Level/_Objects/Monitor and Time Post/Main.asm:138-174 (direction only),
 * Level/Main.asm:971-979 (VINT timer).
 * Compare after each complete Sonic -> post -> VINT turn. Player motion and
 * rendering are deliberately absent; the real world.c owns the tested state.
 */
#include "world.h"
#include "act.h"
#include <assert.h>
#include <stdio.h>

static unsigned turn,native_save_turn,native_saves,goal;
scd_act_state scd_act_get(void){return (scd_act_state){.goal=goal};}
void scd_player_warp_save(void){native_save_turn=turn;native_saves++;}
void scd_player_warp_clear(void){}

typedef struct {unsigned timer,saves,save_turn;int direction,destination;} original;
static int original_turn(original *o,int post,unsigned vints){
    int result=-1;
    /* Sonic precedes the touched post. Test cases maintain >=$600 inertia,
       no charge, no result/death, and never cross both thresholds at once. */
    if(o->direction){
        if(!o->timer)o->timer=1;
        if(o->timer>=230)result=o->destination;
        else if(o->timer>=210 && !o->saves){
            o->destination=o->direction<0?1:3;o->saves++;o->save_turn=turn;
        }
    }
    /* ObjTimePost_Main writes direction. It never clears an active timer. */
    if(post)o->direction=post;
    if(result<0 && o->timer)o->timer+=vints;
    return result;
}
static unsigned run_case(unsigned lag,int second,unsigned contact){
    original o={.destination=-1};native_saves=0;native_save_turn=0;
    scd_world_zone(4);scd_world_act(1);scd_world_reset(0);
    scd_player_state p={.x=3000*65536,.speed=0x600,.routine=2};
    static const unsigned extras[]={12,20,28,31,40,44,52,55,60,64,66,69,76,100};
    for(turn=0;turn<300;turn++){
        int post=turn==0?-1:second && turn==contact?second:0;
        unsigned elapsed=1;
        if(lag==1)for(unsigned i=0;i<sizeof(extras)/sizeof(*extras);i++)if(turn==extras[i])elapsed++;
        if(lag==2)elapsed=1+turn%4;
        int expected=original_turn(&o,post,elapsed);
#ifdef POST_BEFORE_WORLD
        if(post)scd_world_activate(post);
#endif
        int result=scd_world_step_vblanks(p,elapsed);
#ifndef POST_BEFORE_WORLD
        if(post)scd_world_activate(post);
#endif
        scd_world_state n=scd_world_get();
        assert(n.ticks==o.timer && "ordered timer differs");
        assert(n.direction==o.direction && "post direction differs");
        assert(n.destination==o.destination && "saved era differs");
        assert(native_saves==o.saves && "snapshot count differs");
        if(o.saves)assert(native_save_turn==o.save_turn && "snapshot update differs");
        assert(result==expected && "warp commit differs");
        if(result>=0)return native_save_turn;
    }
    assert(!"warp did not commit");return 0;
}
int main(void){
    unsigned normal=run_case(0,0,0),lagged=run_case(1,0,0);
    assert(normal-lagged==14 && "VINT cadence must remain authoritative");
    unsigned cases=2;
    for(unsigned lag=0;lag<2;lag++)for(int direction=-1;direction<=1;direction+=2)
    for(unsigned contact=1;contact<=180;contact+=1){run_case(lag,direction,contact);cases++;}
    run_case(2,0,0);cases++;
    scd_player_state p={.x=3000*65536,.speed=0x600,.routine=2};
    /* Slow Sonic cancels first, then a later post can re-arm the direction.
       Below90 the original keeps the direction while clearing its timer. */
    for(unsigned ticks=20;ticks<=100;ticks+=80){
        scd_world_reset(0);scd_world_activate(-1);
        for(unsigned i=0;i<ticks;i++)scd_world_step(p);
        p.speed=0;scd_world_step(p);p.speed=0x600;
        assert(!scd_world_get().ticks);
        assert(scd_world_get().direction==(ticks<90?-1:0));
        scd_world_activate(1);assert(!scd_world_get().ticks && scd_world_get().direction==1);
        scd_world_step(p);assert(scd_world_get().ticks==2);cases++;
    }
    /* Existing commit/goal suppression must survive the contact-order fix. */
    scd_world_reset(0);scd_world_activate(-1);
    for(unsigned i=0;i<210;i++)scd_world_step(p);
    scd_world_state before=scd_world_get();assert(before.ticks>=210);
    scd_world_activate(1);assert(scd_world_get().direction==-1 && scd_world_get().ticks==before.ticks);cases++;
    goal=1;scd_world_step(p);scd_world_activate(1);
    assert(!scd_world_get().ticks && !scd_world_get().direction);goal=0;cases++;
    /* Hurt (oRoutine 4) skips ObjSonic_TimeWarp: timeWarpDir stays (only the goal,
       level start and the slow-speed stop clear it) and VInt_Level keeps counting. */
    scd_world_activate(-1);scd_world_step(p);p.routine=4;scd_world_step(p);
    assert(scd_world_get().ticks==3 && scd_world_get().direction==-1);cases++;
    assert(cases==728);
    puts("PASS: original Sonic/post/VINT order: 728 boundary cases; 14 extra VINTs advance snapshot by 14 updates");
    return 0;
}
