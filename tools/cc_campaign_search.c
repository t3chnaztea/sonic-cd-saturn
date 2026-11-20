/* Native-host model of an ordinary Collision Chaos campaign act that starts in
   the Present (CC1 act index 0 or CC2 act index 1), with natural time travel.
   The per-update order, camera and warp arrival follow
   tools/cc_campaign_generator_route.c, whose recordings replay position-exact
   on Saturn. Only pad input changes the run: no placement, position or
   velocity writes.

   Goals (milestones):
     act 0: Present -> Past warp -> generator destroyed -> Present warp ->
            Good Future warp -> Act 1 tally.
     act 1: Present -> Past warp -> generator destroyed -> Act 2 tally.
   0@B starts CC1 at the Past spawn instead (level select): generator ->
   Present warp -> Good Future warp -> Act 1 tally.
   ACT:ERA (for example 1:C) is instead a plain level-select run of one era:
   no warp at all, goal the tally.
   Any other warp destination or a death ends that branch.

   cc_campaign_search replay ACT SCRIPT LIMIT OUTPUT
       Replays SCRIPT ("COUNT PAD" lines; bits 128 Right, 64 Left, 32 Down,
       16 Up, 1 Jump) and writes ``sequence pad x y`` rows (from sequence 2)
       for the Saturn replay. Stops after the tally update.
   cc_campaign_search search ACT SEED ITERATIONS OUTSCRIPT [PREFIX]
       Fixed-seed Go-Explore over pad prefixes (after tools/cc3_route_host.c):
       an archive of coarse cells (position, milestone, armed post) keeps the
       shortest prefix that reached each; restoring replays it from a fresh
       load. The search only chooses input; replay is the evidence. */
#include "scd_player.h"
#include "camera_v.h"
#include "scd_objects.h"
#include "act.h"
#include "world.h"
#include "title_card.h"
#include "arrival_camera.h"
#include "scd_boss.h"
#include "EQU.H"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

static unsigned char data[4][400000],collision[4][9472],raw[10240];
/* Pristine copies: bumper blocks (PLAYSP3.C block_wrt) rewrite the loaded
   map, so every load restores the stage bytes before starting a run. */
static unsigned char pristine_data[4][400000],pristine_collision[4][9472];
static size_t data_size[4];
static scd_placement placements[1024];
static unsigned placement_count;
static stage_t stages[4];
static int plain=-1,past_start=0;
static unsigned broken_seen;
static unsigned act,era,warps,milestone,generator,dead,done,sequence,buttons,delayed;
static int camera_x,camera_y,generator_x,generator_y,row_x,row_y;
static unsigned pads[40000],pad_count;
/* Parity only (tools/retail_parity.py), shared by the zone step functions with
   their env prefix (CC_ROUTE here): <PREFIX>_UNLOCK_AT=N holds controls until
   retail's unlock update N; <PREFIX>_TRACE prints "unlock N" and makes replay
   write parity rows (parity_row). Read once per process. */
static unsigned unlock_sequence;
static const char *parity_env(const char *prefix,const char *name){
    char key[64];snprintf(key,sizeof(key),"%s_%s",prefix,name);return getenv(key);
}
static int parity_locked(const char *prefix,int locked){
    static long unlock_at=-2;static int trace;
    if(unlock_at==-2){const char *v=parity_env(prefix,"UNLOCK_AT");unlock_at=v?atol(v):-1;trace=parity_env(prefix,"TRACE")!=NULL;}
    if(unlock_at>=0 && (long)sequence<unlock_at)locked=1;
    if(!locked && !unlock_sequence){unlock_sequence=sequence;if(trace)fprintf(stderr,"unlock %u\n",sequence);}
    return locked;
}
/* Parity only (tools/ppz_cc_route_parity.py): <PREFIX>_LAG=FILE holds retail's
   V-INT frames per update (column 9, line s-2 for sequence s, as
   tools/tt_route_search.c reads TT_ROUTE_LAG). Both counters the original
   advances per V-INT rather than per update follow it: levelVIntCounter (the
   lost-ring floor-check phase, Ring/Main.asm:415) and timeWarpTimer
   (Level/Main.asm:971 RunTimeWarp). Without the file every update is one frame. */
static unsigned char parity_lags[40000];static unsigned parity_lag_count;
static void parity_lag_load(const char *name){
    const char *v=getenv(name);FILE *f=v?fopen(v,"r"):NULL;char line[256];
    while(f && fgets(line,sizeof line,f) && parity_lag_count<40000){unsigned w[9];
        if(sscanf(line,"%u %u %u %u %u %u %u %u %u",w,w+1,w+2,w+3,w+4,w+5,w+6,w+7,w+8)==9)parity_lags[parity_lag_count++]=(unsigned char)w[8];}
    if(f)fclose(f);
}
static unsigned parity_lag(void){
    unsigned n=sequence>=2 && sequence-2<parity_lag_count?parity_lags[sequence-2]:1;
    return n>1 && n<8?n:1;
}
/* tools/tt_route_search.c's parity row: seq pad x y water water_m yspeed status
   mspeed xspeed xsub ysub angle (no water in CC/PPZ: 0 0). */
static void parity_row(FILE *out,unsigned want){
    const sprite_status *s=&actwk[0];
    fprintf(out,"%u %u %d %d 0 0 %d %u %d %d %u %u %u\n",sequence,want,s->xposi.w.h,s->yposi.w.h,s->yspeed.w,s->cddat,
            s->mspeed.w,s->xspeed.w,(unsigned)(uint16_t)s->xposi.w.l,(unsigned)(uint16_t)s->yposi.w.l,(unsigned)s->direc.b.h);
}
static int clamp(int n,int low,int high){return n<low?low:n>high?high:n;}
/* Zone 0 (Palmtree Panic): assets ppz{0..3}.bin / ppz12{A..D} / ppz13{C,D} with
   collision{0..3} / collision12{A..D} / collision13{C,D}; objects are the
   built-in PPZ layouts (no placement file). Modes (ACT argument):
     pA:E  plain level-select run of act A (0..2), era E; goal the tally.
     pS    sequence: Act 1 A -> Act 2 A -> Act 3 D, progress carried.
     pJ    journey: Acts 1 and 2 each Present -> Past -> generator -> Present
           -> Good Future -> tally; then Act 3 in the Good Future (C).
     pJ0, pJ1  one journey act alone (its scripts concatenate into pJ).
   --progress=SCORE,LIVES,NEXT_LIFE seeds the first act's progress.
   Per-update order and camera follow tools/act_test.c (PPZ3 LevEvents
   scralim_left, boss camera, Act 1 camera_y bound 1824). */
static unsigned zone=1,ppz_mode,leg,good_flags;
static unsigned ppz_card_seq;static int ppz_direct; /* PPZ_DIRECT_ENTRY (ppz_begin_act) */
/* PPZ_RING_LOSS=N: the tally only counts after one update lost N+ rings
   (tools/check_past_ring_loss.py stress route, tests/routes/ppz/p1B.txt). */
static unsigned ppz_rings,ppz_ring_loss;
static unsigned ppz_loss_goal(void){const char *g=getenv("PPZ_RING_LOSS");return g?(unsigned)atoi(g):0;}
static size_t read_file(const char *name,void *buffer,size_t capacity);
enum {PPZ_PLAIN=1,PPZ_SEQUENCE,PPZ_JOURNEY};
static uint8_t ppz_data[3][4][300000],ppz_collision[3][4][9472];
static stage_t ppz_stages[3][4];
static int have_progress,ppz_single=-1;static scd_player_progress start_progress;
static int ppz_generator_x=-1,ppz_generator_y;
static stage_t *stage_of(unsigned e){return zone?&stages[e]:&ppz_stages[act][e];}
static unsigned char *collision_of(unsigned e){return zone?collision[e]:ppz_collision[act][e];}
static void ppz_read_assets(void){
    for(unsigned a=0;a<3;a++)for(unsigned e=0;e<4;e++){
        if(a==2 && e<2)continue;
        char path[100];
        if(a)snprintf(path,sizeof(path),"assets/generated/ppz1%u%c.bin",a+1,'A'+e);
        else snprintf(path,sizeof(path),"assets/generated/ppz%u.bin",e);
        size_t bytes=read_file(path,ppz_data[a][e],sizeof(ppz_data[a][e]));
        if(stage_open(&ppz_stages[a][e],ppz_data[a][e],bytes))exit(2);
        if(a)snprintf(path,sizeof(path),"assets/generated/collision1%u%c.bin",a+1,'A'+e);
        else snprintf(path,sizeof(path),"assets/generated/collision%u.bin",e);
        if(read_file(path,ppz_collision[a][e],9472)!=9472)exit(2);
    }
}
/* Start one PPZ act in ERA (src/main.c act entry; the title card as act_test.c). */
static void ppz_begin_act(unsigned a,unsigned e){
    act=a;era=e;warps=generator=0;ppz_generator_x=-1;
    scd_player_zone(0);scd_objects_zone(0);scd_world_zone(0);
    scd_objects_act(act);scd_player_act(act);scd_world_act(act);
    if(scd_player_init(stage_of(era),collision_of(era),9472,era))exit(2);scd_player_objects_lead();
    scd_world_reset(era);
    /* src/main.c starts the title card on every level-select act/era entry.
       PPZ_DIRECT_ENTRY=1 models the Act 2 debug entry instead (tools/act_test.c,
       tools/run-act2-era-script.sh): no card in the Futures, and Saturn ignores
       the pad before update 128 (C) / 117 (D). */
    ppz_direct=getenv("PPZ_DIRECT_ENTRY")!=NULL;ppz_card_seq=1;
    if(!ppz_direct || era==0 || act==2 || era==1)scd_title_card_start(act);
    camera_y=scd_camera_v_begin(0,act,era,scd_player_get().y/65536,scd_player_get().resets);camera_x=scd_camera_h();
}
/* The Saturn's Act 2 debug entry runs the Present card and reloads the Future
   during it (src/main.c X); since the card latches its PLC 2 wait at slide-out
   for the program loaded then (src/title_card.c), the Future's wait adds to
   the 128 (C) / 117 (D) updates measured before it. */
static int ppz_future_masked(void){return ppz_direct && act==1 && era>=2 && ppz_card_seq<(era==2?128u:117u)+scd_title_card_plc_wait(0,1,era);}
static unsigned ppz_start_act(void){return ppz_mode==PPZ_PLAIN?act:ppz_single>=0?(unsigned)ppz_single:0;}
static size_t read_file(const char *name,void *buffer,size_t capacity){
    FILE *f=fopen(name,"rb");if(!f){perror(name);exit(2);}
    size_t n=fread(buffer,1,capacity,f);
    if(ferror(f) || fgetc(f)!=EOF){fprintf(stderr,"Invalid input: %s\n",name);exit(2);}
    fclose(f);return n;
}
static void read_assets(void){
    if(!zone){ppz_read_assets();return;}
    for(unsigned e=0;e<4;e++){
        char path[128];snprintf(path,sizeof(path),"assets/generated/cc3%u%c.bin",act+1,"ABCD"[e]);
        size_t bytes=read_file(path,data[e],sizeof(data[e]));if(stage_open(&stages[e],data[e],bytes))exit(2);
        data_size[e]=bytes;memcpy(pristine_data[e],data[e],bytes);
        snprintf(path,sizeof(path),"assets/generated/cccollision3%u%c.bin",act+1,"ABCD"[e]);
        if(read_file(path,collision[e],sizeof(collision[e]))!=9472)exit(2);
        memcpy(pristine_collision[e],collision[e],9472);
    }
    char path[64];snprintf(path,sizeof(path),"assets/generated/ccobj3%u.bin",act+1);
    size_t bytes=read_file(path,raw,sizeof(raw));
    if(bytes%10)exit(2);
    placement_count=(unsigned)(bytes/10);
    for(unsigned i=0;i<placement_count;i++){
        placements[i].x=(int16_t)(raw[i*10]*256+raw[i*10+1]);
        placements[i].y=(int16_t)(raw[i*10+2]*256+raw[i*10+3]);
        memcpy(&placements[i].type,raw+i*10+4,5);
        if(placements[i].type==SCD_OBJ_CC_GENERATOR){generator_x=placements[i].x;generator_y=placements[i].y;}
    }
}
static void ppz_load(void){
    unsigned first=ppz_start_act();
    dead=done=broken_seen=0;milestone=leg=good_flags=0;buttons=delayed=0;ppz_rings=ppz_ring_loss=0;
    scd_objects_time_stones(0);
    ppz_begin_act(first,ppz_mode==PPZ_PLAIN?(unsigned)plain:0);
    if(have_progress)scd_player_progress_set(start_progress);
    scd_act_camera(camera_x,camera_y);scd_boss_camera(camera_x,camera_y);
    scd_player_hold_clock(1);scd_player_step(0);scd_title_card_step();
    sequence=1;
}
static void load(void){
    unlock_sequence=0;
    if(!zone){ppz_load();return;}
    for(unsigned e=0;e<4;e++){
        memcpy(data[e],pristine_data[e],data_size[e]);memcpy(collision[e],pristine_collision[e],9472);
        if(stage_open(&stages[e],data[e],data_size[e]))exit(2);
    }
    era=plain>=0?(unsigned)plain:past_start?1:0;warps=generator=dead=done=broken_seen=0;milestone=past_start?1:0;buttons=delayed=0;
    scd_player_zone(1);scd_player_act(act);scd_objects_zone(1);scd_objects_act(act);
    scd_objects_layout(placements,placement_count);
    if(scd_player_init(&stages[era],collision[era],sizeof(collision[era]),era))exit(2);scd_player_objects_lead();
    scd_world_zone(1);scd_world_act(act);scd_world_reset(era);scd_title_card_start(act);
    camera_y=scd_camera_v_begin(1,act,era,scd_player_get().y/65536,scd_player_get().resets);camera_x=scd_camera_h();
    scd_act_camera(camera_x,camera_y);scd_boss_camera(camera_x,camera_y);scd_player_hold_clock(1);scd_player_step(0);scd_title_card_step();
    sequence=1;
}
/* Journey milestones per act (Acts 1 and 2): 0 Present, 1 Past, 2 generator
   destroyed, 3 Present, 4 Good Future; the tally then ends the act. */
static int ppz_final_leg(void){return ppz_mode==PPZ_PLAIN || act==2 || ppz_single>=0;}
static void ppz_step(unsigned want){
    sequence++;
    scd_world_state travel=scd_world_get();scd_objects_travel_protection(travel.ticks>0);
    scd_act_camera(camera_x,camera_y);scd_boss_camera(camera_x,camera_y);
    /* Parity only (PPZ_ROUTE_UNLOCK_AT, tools/retail_parity.py): hold controls
       until retail's unlock update so both builds have run the same number of
       level updates; PPZ_ROUTE_TRACE prints "unlock N". */
    static long unlock_at=-2;static unsigned unlock_seq;
    if(unlock_at==-2)unlock_at=getenv("PPZ_ROUTE_UNLOCK_AT")?atol(getenv("PPZ_ROUTE_UNLOCK_AT")):-1;
    if(sequence==2)unlock_seq=0;
    int locked=scd_title_card_locked()||(unlock_at>=0 && (long)sequence<unlock_at);scd_player_hold_clock(locked);
    if(!locked && !unlock_seq){unlock_seq=sequence;if(getenv("PPZ_ROUTE_TRACE"))fprintf(stderr,"unlock %u\n",sequence);}
    /* Parity only (PPZ_ROUTE_VINT_AT=SEQ:BYTE): retail levelVIntCounter's low byte
       at update SEQ (src/objects.c lost-ring floor check cadence). */
    {static long at=-2;static unsigned byte;if(at==-2){const char *v=getenv("PPZ_ROUTE_VINT_AT");at=v?atol(v):-1;if(v && strchr(v,':'))byte=(unsigned)atoi(strchr(v,':')+1);}
     if(at>=0 && (long)sequence==at)scd_objects_vint_add((byte-scd_objects_vint())&255u);}
    ppz_card_seq++;
    scd_player_step(locked || ppz_future_masked()?0:delayed);
    scd_title_card_step();
    scd_player_state p=scd_player_get();int x=p.x/65536,y=p.y/65536;
    row_x=x;row_y=y;
    if(p.rings<ppz_rings && ppz_rings-p.rings>ppz_ring_loss)ppz_ring_loss=ppz_rings-p.rings;
    ppz_rings=p.rings;
    /* src/main.c: LevEvents_PPZ3 after the update. */
    if(act==2 && !bossflag && x>=0xD70){int left=x-160;if(left>=scralim_left)scralim_left=left>scralim_right?scralim_right:left;}
    if(ppz_generator_x<0)for(unsigned k=1;k<97;k++)if(actwk[k].actno==SCD_OBJ_GENERATOR){ppz_generator_x=actwk[k].xposi.w.h;ppz_generator_y=actwk[k].yposi.w.h;break;}
    if(scd_objects_generator()){
        if(ppz_mode==PPZ_JOURNEY){if(era!=1 || milestone!=1)dead=1;else milestone=2;}
        generator=sequence;scd_world_generator_destroyed();
    }
    if(scd_objects_big_ring())dead=1; /* No silently skipped special stage. */
    int destination=scd_world_step_vblanks(p,parity_lag());
    int post=scd_objects_timepost();if(post)scd_world_activate(post);
    if(p.resets || p.routine>=6)dead=1;
    /* PPZ_WARP_LIMIT=N (plain routes): a warp charge of N ticks ends the branch.
       timeWarpTimer counts V-INTs, and retail's lag frames reach 230 (the warp)
       while the host, at one tick per update, is still near 190. */
    {static long limit=-2;if(limit==-2)limit=getenv("PPZ_WARP_LIMIT")?atol(getenv("PPZ_WARP_LIMIT")):-1;
     if(limit>=0 && ppz_mode==PPZ_PLAIN && (long)scd_world_get().ticks>=limit)dead=1;}
    /* PPZ_NO_DAMAGE=1: a hit ends the branch (no-damage reference routes). */
    if(p.routine==4 && getenv("PPZ_NO_DAMAGE"))dead=1;
    /* src/main.c order: scd_camera_v_follow runs scroll() (scroll_h, then
       scroll_v); read the horizontal camera after it. */
    camera_y=clamp(scd_camera_v_follow(y,p.resets),0,act?scralim_down:1824);camera_x=clamp(scd_camera_h(),0,16064);
    camera_x=clamp(camera_x,scralim_left,scralim_right);
    scd_act_state result=scd_act_get();
    /* Diagnostic: PPZ_TRACE=FIRST:LAST prints Sonic's actor like emulator_test SCD_TRACE_ACTWK. */
    {const char *r=getenv("PPZ_TRACE");long f=r?strtol(r,NULL,10):0,l=r&&strchr(r,':')?strtol(strchr(r,':')+1,NULL,10):-1;
     if((long)sequence>=f && (long)sequence<=l){sprite_status *s=&actwk[0];
        fprintf(stderr,"PPZ actwk: %u x=%04x.%04x y=%04x.%04x xspeed=%d yspeed=%d mspeed=%d cddat=%u r_no0=%u scra_h=%d left=%d right=%d camera_x=%d goal=%d phase=%d sign_cam=%d\n",sequence,
            (uint16_t)s->xposi.w.h,(uint16_t)s->xposi.w.l,(uint16_t)s->yposi.w.h,(uint16_t)s->yposi.w.l,s->xspeed.w,s->yspeed.w,s->mspeed.w,s->cddat,s->r_no0,
            scra_h_posit.w.h,scralim_left,scralim_right,camera_x,result.goal,result.phase,result.camera_x);}}
    if(result.goal && camera_x<result.left)camera_x=result.left;
    if(result.phase && !result.sign){camera_x=result.camera_x;camera_y=result.camera_y;}
    scd_camera_v_sync(camera_y);scd_camera_h_sync(camera_x);
    delayed=buttons;
    buttons=(want&128?SCD_RIGHT:0)|(want&64?SCD_LEFT:0)|(want&32?SCD_DOWN:0)|(want&16?SCD_UP:0)|(want&1?SCD_JUMP:0);
    if(dead)return;
    if(destination>=0){
        if(ppz_mode!=PPZ_JOURNEY || act==2){dead=1;return;}
        int expected=milestone==0?1:milestone==2?0:milestone==3?2:-1;
        if(destination!=expected){dead=1;return;}
        era=(unsigned)destination;milestone++;warps++;
        if(scd_player_arrive(stage_of(era),collision_of(era),9472,era)){dead=1;return;}scd_player_objects_lead();
        scd_world_arrived(era);
        scd_player_state arrived=scd_player_get();
        scd_arrival_camera(arrived.x/65536,arrived.y/65536,act,scralim_left,scralim_right,scralim_down,scra_vline,&camera_x,&camera_y);
        camera_y=scd_camera_v_begin(0,act,era,arrived.y/65536,arrived.resets);
        delayed=buttons;
        return;
    }
    if(result.phase==SCD_ACT_DONE){
        if(ppz_mode==PPZ_JOURNEY && act<2 && milestone!=4){dead=1;return;}
        /* PPZ_REQUIRE_CHECKPOINT=1: a Present Act 1/2 tally only counts after a checkpoint
           (tools/act_test.c requires one on those gate routes). */
        if(ppz_final_leg() && getenv("PPZ_REQUIRE_CHECKPOINT") && act<2 && era==0 && !scd_player_checkpoint().id){dead=1;return;}
        if(ppz_final_leg() && ppz_ring_loss<ppz_loss_goal()){dead=1;return;}
        if(ppz_final_leg()){done=1;return;}
        /* src/main.c act change: progress carries; the next act starts fresh. */
        scd_player_progress progress=scd_player_progress_get();
        if(scd_world_get().good_future)good_flags|=1u<<act;
        unsigned next=act+1,next_era=next==2?(ppz_mode==PPZ_JOURNEY?2:3):0;
        if(ppz_mode==PPZ_JOURNEY && next==2 && good_flags!=3){dead=1;return;}
        if(getenv("PPZ_LEGS"))fprintf(stderr,"leg %u done at sequence %u score=%u\n",leg,sequence,progress.score);
        leg++;milestone=0;buttons=delayed=0; /* a fresh act: the plain-act scripts concatenate */
        ppz_begin_act(next,next_era);scd_player_progress_set(progress);
        scd_act_camera(camera_x,camera_y);scd_boss_camera(camera_x,camera_y);
        scd_player_hold_clock(1);scd_player_step(0);scd_title_card_step();
    }
}
/* One gameplay update with the pad requested at this observation. */
static void step(unsigned want){
    if(!zone){ppz_step(want);return;}
    sequence++;
    /* As src/main.c: boss.c's actionsub culls the PC actor slots (97+, e.g.
       PLAYSP3.C bobinbreak) by this camera; without it the host left their
       drawn bit clear where the Saturn set it. */
    scd_act_camera(camera_x,camera_y);scd_boss_camera(camera_x,camera_y);
    int locked=parity_locked("CC_ROUTE",scd_title_card_locked());scd_player_hold_clock(locked);
    scd_objects_travel_protection(scd_world_get().ticks>0);
    scd_player_step(locked?0:delayed);
    scd_title_card_step();
    scd_player_state p=scd_player_get();int x=p.x/65536,y=p.y/65536;
    /* The observation records this update's position; a warp arrival
       below belongs to the next observation (as on Saturn). */
    row_x=x;row_y=y;
    camera_y=clamp(scd_camera_v_follow(y,p.resets),0,scralim_down);camera_x=clamp(scd_camera_h(),scralim_left,scralim_right);
    scd_act_state result=scd_act_get();
    if(result.goal && camera_x<result.left)camera_x=result.left;
    if(result.phase && !result.sign){camera_x=result.camera_x;camera_y=result.camera_y;}
    scd_camera_v_sync(camera_y);scd_camera_h_sync(camera_x);
    if(scd_objects_generator()){
        if(generator || era!=1)dead=plain<0;
        generator=sequence;scd_world_generator_destroyed();if(milestone==1)milestone=2;
    }
    int destination=scd_world_step_vblanks(p,parity_lag());
    int post=scd_objects_timepost();if(post)scd_world_activate(post);
    /* 0@B (tools/test_cc_generator_route.py): the broken Past generator must
       be drawn on screen 60+ updates after the hit before leaving the Past. */
    if(past_start && generator && !broken_seen && era==1 && sequence>=generator+60)
        for(unsigned k=1;k<97;k++)if(actwk[k].actno==SCD_OBJ_CC_GENERATOR && actwk[k].patno==1 && (actwk[k].actflg&128))broken_seen=1;
    if(past_start && destination>=0 && milestone==2 && !broken_seen)dead=1;
    if(p.resets || p.routine>=6)dead=1;
    delayed=buttons;
    buttons=(want&128?SCD_RIGHT:0)|(want&64?SCD_LEFT:0)|(want&32?SCD_DOWN:0)|(want&16?SCD_UP:0)|(want&1?SCD_JUMP:0);
    if(result.phase==SCD_ACT_DONE){
        if(plain>=0 || (act==0?milestone==4:milestone==2))done=1;else dead=1;
    }
    /* Search only (CC_ROUTE_GOAL=bigring): a plain route must end through the
       big ring (Level End/Main.asm ObjBigRing, 50 rings). A separate statement
       keeps the block above, which derived hosts patch. */
    {static int bigring=-1;if(bigring<0){const char *g=getenv("CC_ROUTE_GOAL");bigring=g && !strcmp(g,"bigring");}
     if(bigring && plain>=0 && result.phase==SCD_ACT_DONE && !scd_objects_big_ring_touched()){done=0;dead=1;}}
    if(destination>=0 && plain>=0)dead=1;
    if(destination>=0 && !dead){
        int expected=milestone==0?1:(act==0 && milestone==2)?0:(act==0 && milestone==3)?2:-1;
        if(destination!=expected){dead=1;return;}
        era=(unsigned)destination;milestone++;warps++;
        if(scd_player_arrive(stage_of(era),collision_of(era),9472,era))exit(2);scd_player_objects_lead();
        scd_world_arrived(era);
        scd_player_state arrived=scd_player_get();
        scd_arrival_camera(arrived.x/65536,arrived.y/65536,0,scralim_left,scralim_right,scralim_down,scra_vline,&camera_x,&camera_y);
        camera_y=scd_camera_v_begin(1,act,era,arrived.y/65536,arrived.resets);
        /* The cutscene keeps sampling the last pad command. */
        delayed=buttons;
    }
}
static unsigned rng_state;
static unsigned rng(void){rng_state=rng_state*1103515245u+12345u;return (rng_state>>16)&32767;}
static void macro(void){
    static const unsigned choices[]={128,64,0,1,129,65,32,160,96,33};
    unsigned pad=choices[rng()%10],len=4+rng()%28;
    if(pad&1){
        unsigned hold=1+rng()%24;
        /* PPZ: crouch one update before the jump. Native buffers a Down + jump
           pressed together into a spin dash; retail (Sonic/Main.asm) does not,
           so such a route leaves retail parity (tools/retail_parity.py). */
        /* Every zone (search only): retail jumps there too (CC1A row 3812 rolled
           natively from a standstill Down + jump). */
        if(pad==33 && !dead && !done && pad_count<39000){pads[pad_count++]=32;step(32);}
        for(unsigned i=0;i<hold && !dead && !done;i++){pads[pad_count++]=pad;step(pad);}
        pad&=~1u;len=2+rng()%6;
    }
    for(unsigned i=0;i<len && !dead && !done && pad_count<39000;i++){pads[pad_count++]=pad;step(pad);}
}
typedef struct {uint32_t key;uint8_t *pads;unsigned length,visits,tried;double value;} cell;
static cell *cells;static unsigned cell_count,cell_capacity;
static int armed(void){int d=scd_world_get().direction;return d<0?1:d>0?2:0;}
static uint32_t cell_key(void){
    scd_player_state p=scd_player_get();
    if(!zone){unsigned x=(unsigned)clamp(p.x/65536,0,16383)/32,y=(unsigned)clamp(p.y/65536,0,2047)/32;
        return x|(y<<9)|((leg*5+milestone)<<15)|((unsigned)armed()<<20)|((scd_player_checkpoint().id?1u:0u)<<22)
            |(ppz_loss_goal()?((ppz_ring_loss>=ppz_loss_goal())<<23)|((ppz_rings>=ppz_loss_goal())<<24):0u);}
    unsigned x=(unsigned)clamp(p.x/65536,0,16383)/32,y=(unsigned)clamp(p.y/65536,0,2047)/32;
    /* Search only (CC_ROUTE_RINGS): ring count buckets of 8. */
    static int rings=-1;if(rings<0)rings=getenv("CC_ROUTE_RINGS")!=NULL;
    return x|(y<<9)|(milestone<<15)|((unsigned)armed()<<18)|(rings?(uint32_t)((plring>56?56:plring)/8)<<20:0u);
}
static double cell_value(void){
    scd_player_state p=scd_player_get();int x=p.x/65536,y=p.y/65536;
    if(!zone){
        double v=(leg*5+milestone)*100000.0;
        if(getenv("PPZ_REQUIRE_CHECKPOINT") && scd_player_checkpoint().id)v+=50000;
        if(ppz_loss_goal())v+=ppz_ring_loss>=ppz_loss_goal()?50000:300.0*(ppz_rings<ppz_loss_goal()?ppz_rings:ppz_loss_goal());
        if(ppz_mode==PPZ_JOURNEY && act<2){
            int want=milestone==0?1:(milestone==2 || milestone==3)?2:0;
            if(want && armed()==want)v+=20000;
            if(milestone==1 && ppz_generator_x>=0)return v-sqrt((double)(x-ppz_generator_x)*(x-ppz_generator_x)+(double)(y-ppz_generator_y)*(y-ppz_generator_y));
            if(milestone<4)return v+x/8.0;
        }
        return v+x;
    }
    double v=milestone*100000.0;
    /* Arming the post that leads to the next milestone's era is progress. */
    int want=plain>=0?0:milestone==0?1:(act==0 && (milestone==2 || milestone==3))?2:0;
    if(want && armed()==want)v+=20000;
    if(milestone==1)v-=sqrt((double)(x-generator_x)*(x-generator_x)+(double)(y-generator_y)*(y-generator_y));
    if(plain>=0 || (act==0 && milestone==4) || (act==1 && milestone==2))v+=x;
    /* Search only (CC_ROUTE_RINGS=W): W per ring up to 50, 20000 more from 50. */
    {static int w=-1;if(w<0)w=getenv("CC_ROUTE_RINGS")?atoi(getenv("CC_ROUTE_RINGS")):0;
     if(w)v+=(plring>50?50:plring)*(double)w+(plring>=50?20000.0:0);}
    return v;
}
static void archive(void){
    if(dead)return;
    uint32_t key=cell_key();
    for(unsigned i=0;i<cell_count;i++)if(cells[i].key==key){
        if(pad_count<cells[i].length){
            cells[i].pads=realloc(cells[i].pads,pad_count?pad_count:1);
            for(unsigned j=0;j<pad_count;j++)cells[i].pads[j]=(uint8_t)pads[j];
            cells[i].length=pad_count;cells[i].value=cell_value();
        }
        return;
    }
    if(cell_count==cell_capacity){cell_capacity=cell_capacity?cell_capacity*2:1024;cells=realloc(cells,sizeof(cell)*cell_capacity);}
    cell *c=&cells[cell_count++];c->key=key;c->length=pad_count;c->visits=0;c->tried=0;c->value=cell_value();
    c->pads=malloc(pad_count?pad_count:1);for(unsigned j=0;j<pad_count;j++)c->pads[j]=(uint8_t)pads[j];
}
static void restore(const cell *c){
    pad_count=0;load();
    for(unsigned j=0;j<c->length;j++){pads[pad_count++]=c->pads[j];step(c->pads[j]);}
}
static void write_script(const char *name){
    FILE *f=fopen(name,"w");if(!f)exit(2);
    for(unsigned i=0;i<pad_count;){
        unsigned j=i;while(j<pad_count && pads[j]==pads[i])j++;
        fprintf(f,"%u %u\n",j-i,pads[i]);i=j;
    }
    fclose(f);
}
static void read_script(const char *name,unsigned limit){
    FILE *f=fopen(name,"r");if(!f){perror(name);exit(2);}
    unsigned n,pad;
    while(fscanf(f,"%u %u",&n,&pad)==2){
        if(pad&~0xf1u)exit(2);
        while(n-- && pad_count<limit)pads[pad_count++]=pad;
    }
    fclose(f);
}
static int search(unsigned seed,unsigned iterations,const char *out,const char *prefix){
    rng_state=seed;load();
    if(prefix){read_script(prefix,39000);for(unsigned i=0;i<pad_count && !dead;i++)step(pads[i]);}
    if(dead){fprintf(stderr,"prefix died\n");return 2;}
    archive();
    double top=-1e30;
    for(unsigned it=0;it<iterations;it++){
        double best=-1e30;for(unsigned i=0;i<cell_count;i++)if(cells[i].value>best)best=cells[i].value;
        double total=0;static double weight[1<<20];
        for(unsigned i=0;i<cell_count;i++){
            double w=(cells[i].value>=best-200?4.0:cells[i].value>=best-2000?1.0:0.05)/sqrt(cells[i].visits+1.0);
            weight[i]=w;total+=w;
        }
        double r=(rng()/32768.0+rng()/1073741824.0)*total;unsigned pick=0;
        for(;pick+1<cell_count && r>weight[pick];pick++)r-=weight[pick];
        cells[pick].visits++;restore(&cells[pick]);
        /* A cell in the goal milestone first tries finishing with a neutral
           pad: the sign/tally exit needs no input and random macros that
           press Left keep it from completing. */
        int goal=!zone?(ppz_final_leg() && (ppz_mode!=PPZ_JOURNEY || act==2 || milestone==4)):(plain>=0 || (act==0?milestone==4:milestone==2));
        if(goal && !cells[pick].tried){
            cells[pick].tried=1;
            for(unsigned t=0;t<1500 && !dead && !done && pad_count<39000;t++){pads[pad_count++]=0;step(0);}
            if(done){write_script(out);fprintf(stderr,"search done: iterations=%u cells=%u sequence=%u generator=%u\n",it,cell_count,sequence,generator);return 0;}
            restore(&cells[pick]);
        }
        unsigned macros=4+rng()%24;
        for(unsigned m=0;m<macros && !dead && !done;m++){macro();archive();}
        if(done){write_script(out);fprintf(stderr,"search done: iterations=%u cells=%u sequence=%u generator=%u\n",it,cell_count,sequence,generator);return 0;}
        if(best>top || it%2000==0){
            top=best;unsigned b=0;for(unsigned i=0;i<cell_count;i++)if(cells[i].value>cells[b].value)b=i;
            uint32_t k=cells[b].key;
            fprintf(stderr,"it %u cells %u best %.0f x~%u y~%u milestone %u armed %u len %u\n",it,cell_count,cells[b].value,(k&511)*32,((k>>9)&63)*32,(k>>15)&7,(k>>18)&3,cells[b].length);
        }
    }
    unsigned b=0;for(unsigned i=0;i<cell_count;i++)if(cells[i].value>cells[b].value)b=i;
    restore(&cells[b]);write_script(out);
    fprintf(stderr,"search end: cells=%u value=%.0f milestone=%u\n",cell_count,cells[b].value,milestone);
    return 1;
}
int main(int argc,char **argv){
    if(argc<6){fprintf(stderr,"usage: cc_campaign_search replay ACT SCRIPT LIMIT OUTPUT | search ACT SEED ITERATIONS OUTSCRIPT [PREFIX]\n");return 2;}
    for(int i=1;i<argc;i++)if(!strncmp(argv[i],"--progress=",11)){
        unsigned s,l,n;if(sscanf(argv[i]+11,"%u,%u,%u",&s,&l,&n)!=3)return 2;
        start_progress=(scd_player_progress){s,n,(uint8_t)l};have_progress=1;
        for(int j=i;j+1<argc;j++)argv[j]=argv[j+1];argc--;i--;
    }
    if(argv[2][0]=='p'){
        zone=0;const char *m=argv[2]+1;
        if(!strcmp(m,"S"))ppz_mode=PPZ_SEQUENCE;
        else if(!strcmp(m,"J"))ppz_mode=PPZ_JOURNEY;
        else if(m[0]=='J' && (m[1]=='0' || m[1]=='1') && !m[2]){ppz_mode=PPZ_JOURNEY;ppz_single=m[1]-'0';}
        else if(m[0]>='0' && m[0]<='2' && m[1]==':' && m[2]>='A' && m[2]<='D' && !m[3]){
            ppz_mode=PPZ_PLAIN;act=(unsigned)(m[0]-'0');plain=m[2]-'A';if(act==2 && plain<2)return 2;
        }else return 2;
        read_assets();
        goto dispatch;
    }
    act=(unsigned)atoi(argv[2]);if(act>1)return 2;
    if(argv[2][1]==':'){if(argv[2][2]<'A' || argv[2][2]>'D')return 2;plain=argv[2][2]-'A';}
    else if(argv[2][1]=='@'){if(act || strcmp(argv[2]+2,"B"))return 2;past_start=1;}
    read_assets();
dispatch:
    if(!strcmp(argv[1],"search"))return search((unsigned)atoi(argv[3]),(unsigned)atoi(argv[4]),argv[5],argc>6?argv[6]:NULL);
    if(!strcmp(argv[1],"chain")){
        /* Diagnostic: CC1 script, then src/main.c's act 1 -> 2 transition
           calls without a fresh process, then the Act 2 script. */
        read_script(argv[3],40000);load();
        for(unsigned i=0;!done && !dead && i<40000;i++)step(i<pad_count?pads[i]:0);
        if(!done){fprintf(stderr,"chain: CC1 did not finish\n");return 1;}
        scd_player_progress progress=scd_player_progress_get();
        act=1;read_assets();pad_count=0;read_script(argv[4],40000);
        for(unsigned e=0;e<4;e++){memcpy(pristine_data[e],data[e],data_size[e]);}
        era=0;warps=milestone=generator=dead=done=0;buttons=delayed=0;
        scd_objects_act(1);scd_player_act(1);scd_world_act(1);
        scd_objects_layout(placements,placement_count);
        if(scd_player_init(&stages[0],collision[0],sizeof(collision[0]),0))return 2;scd_player_objects_lead();
        scd_world_reset(0);scd_player_progress_set(progress);scd_title_card_start(1);
        camera_y=scd_camera_v_begin(1,act,0,scd_player_get().y/65536,scd_player_get().resets);camera_x=scd_camera_h();
        scd_act_camera(camera_x,camera_y);scd_player_hold_clock(1);scd_player_step(0);scd_title_card_step();
        sequence=1;
        FILE *out=fopen(argv[5],"w");if(!out)return 2;
        for(unsigned i=0;i<pad_count && !dead && !done;i++){
            step(pads[i]);
            fprintf(out,"%u %u %d %d\n",sequence,pads[i],row_x,row_y);
        }
        fclose(out);fprintf(stderr,"chain: act2 dead=%u done=%u sequence=%u\n",dead,done,sequence);return 0;
    }
    if(!strcmp(argv[1],"check")){
        /* Determinism check: two loads in one process must match a fresh one. */
        unsigned limit=(unsigned)atoi(argv[4]);read_script(argv[3],limit);
        static int first[40000][2];unsigned n=pad_count;
        for(unsigned pass=0;pass<2;pass++){
            load();
            for(unsigned i=0;i<n && !dead;i++){
                step(pads[i]);scd_player_state p=scd_player_get();
                if(!pass){first[i][0]=p.x;first[i][1]=p.y;}
                else if(first[i][0]!=p.x || first[i][1]!=p.y){fprintf(stderr,"check: second load differs at update %u\n",i+2);return 1;}
            }
        }
        fprintf(stderr,"check: %u updates identical after reload\n",n);return 0;
    }
    if(strcmp(argv[1],"replay"))return 2;
    unsigned limit=(unsigned)atoi(argv[4]);if(limit<10 || limit>40000)return 2;
    read_script(argv[3],limit);load();
    FILE *out=fopen(argv[5],"w");if(!out){perror(argv[5]);return 2;}
    /* CC_ROUTE_VINT_AT=SEQ:BYTE: PPZ_ROUTE_VINT_AT (ppz_step) for CC. */
    long cc_vint_at=-1;unsigned cc_vint_byte=0;
    {const char *a=zone?getenv("CC_ROUTE_VINT_AT"):NULL;
     if(a && strchr(a,':')){cc_vint_at=atol(a);cc_vint_byte=(unsigned)atoi(strchr(a,':')+1);}}
    parity_lag_load(zone?"CC_ROUTE_LAG":"PPZ_ROUTE_LAG");
    for(unsigned i=0;i<limit;i++){
        unsigned want=i<pad_count?pads[i]:0;
        if(cc_vint_at>=0 && (long)sequence+1==cc_vint_at)scd_objects_vint_add((cc_vint_byte-scd_objects_vint())&255u);
        step(want);
        scd_objects_vint_add(parity_lag()-1u);
        scd_player_state p=scd_player_get();
        if(dead){fprintf(stderr,"Route failed at %u x=%d y=%d era=%u milestone=%u\n",sequence,p.x/65536,p.y/65536,era,milestone);fclose(out);return 3;}
        /* Diagnostic: CC_ROUTE_OBJECTS=FIRST:LAST:FILE dumps live actwk slots
           (seq slot actno userflag r_no0 x xsub y ysub xspeed actflg) like
           tools/retail_probe.py's PREFIX_OBJECTS. */
        {static FILE *od;static long of=-2,ol;if(of==-2){const char *v=parity_env("CC_ROUTE","OBJECTS");of=-1;
            if(v && strchr(v,':') && strchr(strchr(v,':')+1,':')){of=atol(v);ol=atol(strchr(v,':')+1);od=fopen(strchr(strchr(v,':')+1,':')+1,"w");}}
         if(od && (long)sequence>=of && (long)sequence<=ol){
            fprintf(od,"%u camera %d %d\n",sequence,scd_act_view_x(),scd_act_view_y());
            for(unsigned k=0;k<128;k++){const sprite_status *o=&actwk[k];if(!o->actno)continue;
                fprintf(od,"%u %u %u %u %u %d %u %d %u %d %u\n",sequence,k,o->actno,(unsigned)(uint8_t)o->userflag.b.h,o->r_no0,o->xposi.w.h,(unsigned)(uint16_t)o->xposi.w.l,
                        o->yposi.w.h,(unsigned)(uint16_t)o->yposi.w.l,o->xspeed.w,o->actflg);}
            fflush(od);}}
        /* Diagnostic: CC_ROUTE_ACTORS=FIRST:LAST:FILE dumps every field of each
           live slot, in the column order of tools/emulator_test.c's
           SCD_ZONE_ACTORS, so host and Saturn object state diff line by line. */
        {static FILE *ad;static long af=-2,al;if(af==-2){const char *v=parity_env("CC_ROUTE","ACTORS");af=-1;
            if(v && strchr(v,':') && strchr(strchr(v,':')+1,':')){af=atol(v);al=atol(strchr(v,':')+1);ad=fopen(strchr(strchr(v,':')+1,':')+1,"w");}}
         if(ad && (long)sequence>=af && (long)sequence<=al){
            for(unsigned k=0;k<128;k++){const sprite_status *o=&actwk[k];if(!o->actno)continue;
                fprintf(ad,"%u %u %02x %02x %04x %04x.%04x %04x.%04x %04x %04x %04x %02x %02x %02x %02x %02x %04x %02x %02x %02x %02x %02x %02x %02x %02x %02x %04x %04x %02x%02x",
                        sequence,k,o->actno,o->actflg,o->sproffset,(uint16_t)o->xposi.w.h,(uint16_t)o->xposi.w.l,(uint16_t)o->yposi.w.h,(uint16_t)o->yposi.w.l,
                        (uint16_t)o->xspeed.w,(uint16_t)o->yspeed.w,(uint16_t)o->mspeed.w,o->sprhsize,o->sprvsize,o->sprhs,o->sprpri,o->patno,(uint16_t)o->mstno.w,
                        o->patcnt,o->pattim,o->pattimm,o->colino,o->colicnt,o->cddat,o->cdsts,o->r_no0,o->r_no1,(uint16_t)o->direc.w,(uint16_t)o->userflag.w,o->dummy[0],o->dummy[1]);
                fputc(' ',ad);for(unsigned b=0;b<22;b++)fprintf(ad,"%02x",o->actfree[b]);fputc('\n',ad);}
            fflush(ad);}}
        if(zone && parity_env("CC_ROUTE","TRACE"))parity_row(out,want);
        /* PPZ_ROUTE_TRACE: parity rows in tools/tt_route_search.c's column order
           (the two water columns are 0 in Palmtree Panic). */
        else if(!zone && getenv("PPZ_ROUTE_TRACE"))fprintf(out,"%u %u %d %d 0 0 %d %u %d %d %u %u %u\n",sequence,want,actwk[0].xposi.w.h,actwk[0].yposi.w.h,actwk[0].yspeed.w,actwk[0].cddat,
                                                     actwk[0].mspeed.w,actwk[0].xspeed.w,actwk[0].xposi.w.l,actwk[0].yposi.w.l,actwk[0].direc.b.h);
        else fprintf(out,"%u %u %d %d\n",sequence,want,row_x,row_y);
        /* Diagnostic: PPZ_ROUTE_OBJECTS=FIRST:LAST:FILE writes every live slot on
           sequences FIRST..LAST in tools/retail_probe.py's PREFIX_OBJECTS format,
           labelled with the aligned retail row (sequence + 1). */
        {static FILE *od;static long of=-1,ol=-1;const char *e=getenv("PPZ_ROUTE_OBJECTS");
         if(e && !od){of=strtol(e,NULL,10);ol=strtol(strchr(e,':')+1,NULL,10);od=fopen(strchr(strchr(e,':')+1,':')+1,"w");}
         if(od && (long)sequence>=of && (long)sequence<=ol)
             for(unsigned k=0;k<128;k++){sprite_status *o=&actwk[k];if(!o->actno)continue;
                 fprintf(od,"%u %u %u %u %u %d %u %d %u %d %u %d %d\n",sequence+1,k,o->actno,(unsigned)(uint8_t)o->userflag.b.h,o->r_no0,
                         o->xposi.w.h,(unsigned)(uint16_t)o->xposi.w.l,o->yposi.w.h,(unsigned)(uint16_t)o->yposi.w.l,o->xspeed.w,
                         o->actflg,(int16_t)(o->actfree[12]|o->actfree[13]<<8),(int16_t)(o->actfree[14]|o->actfree[15]<<8));}
         if(od && (long)sequence==ol)fflush(od);}
        if(done){
            fclose(out);
            fprintf(stderr,"Big ring: touched=%d rings=%u\n",scd_objects_big_ring_touched(),(unsigned)plring);
            fprintf(stderr,"Tally complete: sequence=%u era=%u good_future=%u generator=%u warps=%u score=%u%s",
                    sequence,era,scd_world_get().good_future,generator,warps,p.score,zone?"\n":"");
            if(!zone)fprintf(stderr," act=%u leg=%u lives=%u good_flags=%u\n",act,leg,scd_player_progress_get().lives,good_flags|(scd_world_get().good_future?1u<<act:0));
            return 0;
        }
    }
    fclose(out);fprintf(stderr,"Route incomplete: milestone=%u\n",milestone);return 1;
}
