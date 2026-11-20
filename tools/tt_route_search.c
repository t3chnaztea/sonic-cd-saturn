/* Native-host model of a Tidal Tempest level-select run of one act and era,
   for Saturn controller-route replays (tools/test_tt_route.py).
   The per-update order follows src/main.c's gameplay step: camera to the
   actors and boss, title lock, player step (water tick, plwaterchk and the
   water objects run inside it), title card, boss music, SCRCHK4.C
   zone42chk/zone43chk bounds, world step, camera, then GAME4.C's
   watercoli/patset/watercnt (water_currents, water_objects_visible,
   water_level_step). Only pad input changes a run: no placement, position
   or velocity writes.

   Goals: Act 1/2 (act index 0/1, any era): the tally, with no warp, no
   death and no drowning. Act 3 (index 2, C or D): through the boss
   (egg4air, egg4), the capsule and the tally.

   tt_route_search replay ACT:ERA SCRIPT LIMIT OUTPUT
       Replays SCRIPT ("COUNT PAD" lines; bits 128 Right, 64 Left, 32 Down,
       16 Up, 1 Jump; neutral after it) and writes ``sequence pad x y`` rows
       from sequence 2, then prints the tally line with the lowest air.
   tt_route_search search ACT:ERA SEED ITERATIONS OUTSCRIPT [PREFIX]
       Fixed-seed Go-Explore over pad prefixes (after cc_campaign_search.c):
       an archive of coarse cells keeps the shortest prefix that reached
       each; restoring replays it from a fresh load. The search only chooses
       input; the replay is the evidence. */
#include "scd_player.h"
#include "scd_objects.h"
unsigned scd_boss_retail_slot_peek(unsigned actor);
#include "scd_boss.h"
#include "act.h"
#include "world.h"
#include "title_card.h"
#include "water.h"
#include "camera_v.h"
#include "EQU.H"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <unistd.h>

extern short scralim_left,scralim_right,scralim_down,scra_vline;
static unsigned char data[400000],collision[9472],raw[10240];
static unsigned char pristine[400000],pristine_collision[9472];
static size_t data_size;
static scd_placement placements[1024];
static unsigned placement_count;
static stage_t stage;
static unsigned act,era,dead,done,sequence,buttons,delayed,drowned,min_air,boss_hits,boss_seen,egg_seen,max_flag;
/* egg4 fight progress for the search value only: shield bubbles popped
   (egg4awa, actno 79, colino 255 -> 0: COLI4.C pcolspecial bossstart 4,
   case 63) and egg4 hit (colicnt 2 -> 1, BOSS_4_2.C egg4_hitchk). */
static unsigned egg_pops,egg_hit;static unsigned char bubble_colino[128];
/* First sequence whose player step reads the pad (title card unlocked);
   tools/tt_retail_probe.py --native-unlock aligns retail to it. */
static unsigned unlock_sequence;
static int camera_x,camera_y,row_x,row_y,trace_x,trace_y;
static unsigned pads[48000],pad_count;
static unsigned char lag[48000];static unsigned lag_count;
/* Comparison only (TT_ROUTE_LAG column 10, when present): the retail V-INT
   count of the same row (levelVIntCounter delta). A masked interrupt can
   swallow a V-INT, so a 3-frame update may count 2 (retail QQ1AB 1730). */
static unsigned char vint_lag[48000];static unsigned vint_lag_count;
#define PAD_LIMIT 46000
static size_t read_file(const char *name,void *buffer,size_t capacity){
    FILE *f=fopen(name,"rb");if(!f){perror(name);exit(2);}
    size_t n=fread(buffer,1,capacity,f);
    if(ferror(f) || fgetc(f)!=EOF){fprintf(stderr,"Invalid input: %s\n",name);exit(2);}
    fclose(f);return n;
}
static void read_assets(void){
    char path[128];
    snprintf(path,sizeof(path),"assets/generated/tt4%u%c.bin",act+1,"ABCD"[era]);
    data_size=read_file(path,data,sizeof(data));memcpy(pristine,data,data_size);
    snprintf(path,sizeof(path),"assets/generated/ttcollision4%u%c.bin",act+1,"ABCD"[era]);
    if(read_file(path,collision,sizeof(collision))!=9472)exit(2);
    memcpy(pristine_collision,collision,9472);
    snprintf(path,sizeof(path),"assets/generated/ttobj4%u.bin",act+1);
    size_t bytes=read_file(path,raw,sizeof(raw));
    if(bytes%10)exit(2);
    placement_count=(unsigned)(bytes/10);
    for(unsigned i=0;i<placement_count;i++){
        placements[i].x=(int16_t)(raw[i*10]*256+raw[i*10+1]);
        placements[i].y=(int16_t)(raw[i*10+2]*256+raw[i*10+3]);
        memcpy(&placements[i].type,raw+i*10+4,5);
    }
}
/* Search only (TT_ROUTE_DUAL=LEAD): a forked mirror replays every pad of the
   search without the retail-aligned settings (TT_ROUTE_UNLOCK_AT, _LAG,
   _VINT_AT) and skips the LEAD neutral pads the aligned prefix leads with, so
   a found script finishes both as the plain host replay and as
   tools/retail_parity.py's aligned replay. A branch the mirror dies on is
   dropped. */
static FILE *dual_out,*dual_in;
/* The mirror's Sonic x at the last archive (-1 without a mirror): the cell key
   and value follow the run that is further behind. */
static int dual_x=-1,dual_y=-1;
/* Lowest air after the search prefix (TT_ROUTE_MIN_AIR applies to it). */
static unsigned tail_from,min_tail;
static void load(void){
    if(dual_out)putc(0xFE,dual_out);
    memcpy(data,pristine,data_size);memcpy(collision,pristine_collision,9472);
    if(stage_open(&stage,data,data_size))exit(2);
    dead=done=drowned=boss_hits=boss_seen=egg_seen=max_flag=0;egg_pops=egg_hit=0;memset(bubble_colino,0,sizeof(bubble_colino));buttons=delayed=0;min_air=30;min_tail=30;
    scd_boss_reset();
    scd_player_zone(2);scd_player_act(act);scd_objects_zone(2);scd_objects_act(act);
    scd_objects_layout(placements,getenv("TT_ROUTE_NO_OBJECTS")?0:placement_count);
    camera_x=0;camera_y=stage.start_y-140;
    water_camera(camera_x,camera_y);
    if(scd_player_init(&stage,collision,sizeof(collision),era))exit(2);scd_player_objects_lead();
    camera_y=scd_camera_v_begin(2,act,era,scd_player_get().y/65536,scd_player_get().resets);camera_x=scd_camera_h();
    water_camera(camera_x,camera_y);water_reset(2,act,era);
    scd_world_zone(2);scd_world_act(act);scd_world_reset(era);scd_title_card_start(act);
    scd_act_camera(camera_x,camera_y);scd_boss_camera(camera_x,camera_y);
    scd_player_hold_clock(1);scd_player_step(0);scd_title_card_step();
    /* src/main.c runs the water step after this first (clock-held) update too
       (water_frame=player_updated): the sway reads 8 after Sonic's first update. */
    water_camera(camera_x,camera_y);water_currents();water_objects_visible();water_level_step();
    sequence=1;unlock_sequence=0;
    if(getenv("TT_ROUTE_DEBUG"))fprintf(stderr,"start %d,%d limits l=%d r=%d d=%d water=%d\n",scd_player_get().x/65536,scd_player_get().y/65536,scralim_left,scralim_right,scralim_down,waterposi);
}
/* One src/main.c gameplay update with the pad requested at this observation. */
static void step(unsigned want){
    if(dual_out)putc((int)want,dual_out);
    sequence++;
    scd_act_camera(camera_x,camera_y);scd_boss_camera(camera_x,camera_y);
    /* Parity only (TT_ROUTE_UNLOCK_AT): hold controls until retail's unlock
       update, so both builds have run the same number of level updates. */
    static long unlock_at=-2;if(unlock_at==-2)unlock_at=getenv("TT_ROUTE_UNLOCK_AT")?atol(getenv("TT_ROUTE_UNLOCK_AT")):-1;
    int locked=scd_title_card_locked()||(unlock_at>=0 && (long)sequence<unlock_at);scd_player_hold_clock(locked);
    if(!locked && !unlock_sequence){unlock_sequence=sequence;
        /* Parity only (TT_ROUTE_SWAY): retail's water sway angle leads at unlock. */
        if(getenv("TT_ROUTE_SWAY"))sysdirec+=(unsigned char)atoi(getenv("TT_ROUTE_SWAY"));
        if(getenv("TT_ROUTE_TRACE"))fprintf(stderr,"unlock %u\n",sequence);}
    /* Parity only (TT_ROUTE_VINT_AT=SEQ:BYTE): set levelVIntCounter's low byte to
       retail's for update SEQ (src/objects.c lost-ring floor check cadence). */
    {static long at=-2;static unsigned byte;if(at==-2){const char *v=getenv("TT_ROUTE_VINT_AT");at=v?atol(v):-1;if(v && strchr(v,':'))byte=(unsigned)atoi(strchr(v,':')+1);}
     if(at>=0 && (long)sequence==at)scd_objects_vint_add((byte-scd_objects_vint())&255u);}
    scd_objects_travel_protection(scd_world_get().ticks>0);
    int updated=1; /* Sonic keeps updating through the warp fade (src/player.c warp_save). */
    if(updated)scd_player_step(locked?0:delayed);
    scd_title_card_step();
    (void)scd_player_music_event();
    (void)scd_boss_music();
    scd_player_state p=scd_player_get();int x=p.x/65536,y=p.y/65536;
    row_x=x;row_y=y;
    /* SCRCHK4.C zone42chk / zone43chk, as src/main.c applies them. */
    if(act==1)scralim_down=p.animation!=43&&p.routine<6&&camera_x<512?2048:1808;
    if(act==2){
        if(x>=2808){
            const short target=1216;short left=(short)(x-160);
            if(abs(target-scralim_down)<4)scralim_down=target;
            if(left>=scralim_left)scralim_left=left>scralim_right?scralim_right:left;
            if(scralim_down>target){if(target<(uint16_t)camera_y)scralim_down=camera_y&~1;scralim_down-=4;}
            else if(scralim_down<target)scralim_down+=4;
        }else if(bossflag)scralim_down=1264;
    }
    if(scd_objects_generator())scd_world_generator_destroyed();
    /* Comparison only (TT_ROUTE_LAG): Level/Main.asm RunTimeWarp advances
       timeWarpTimer in every V-INT, lag frames included (src/main.c passes the
       Saturn V-blank count), so a lagging retail update advances it once per
       V-INT frame, with the same row as the water step below. */
    unsigned world_vblanks=lag_count && sequence-2<lag_count && lag[sequence-2]>1 && lag[sequence-2]<8?lag[sequence-2]:1;
    if(sequence-2<vint_lag_count && vint_lag[sequence-2]>=1 && vint_lag[sequence-2]<8)world_vblanks=vint_lag[sequence-2];
    if(scd_world_step_vblanks(p,world_vblanks)>=0)dead=2;
    int post=scd_objects_timepost();if(post)scd_world_activate(post);
    if(p.resets || p.routine>=6)dead=1;
    /* PLAYSUB4.C plawamaster: air below zero sets actfree[2]=129 and the drowning pose (mstno 23). */
    if(actwk[0].actfree[2]==129 && p.animation==23){drowned=1;dead=1;}
    if((unsigned)pl_air<min_air)min_air=(unsigned)pl_air;
    if(sequence>tail_from && (unsigned)pl_air<min_tail)min_tail=(unsigned)pl_air;
    if(!scd_objects_big_ring_touched()){camera_y=scd_camera_v_follow(y,p.resets);camera_x=scd_camera_h();}
    if(camera_x<0)camera_x=0;
    if(camera_x>16064)camera_x=16064;
    if(camera_y<0)camera_y=0;
    if(camera_y>scralim_down)camera_y=scralim_down;
    scd_act_state result=scd_act_get();
    if(camera_x>scralim_right)camera_x=scralim_right;
    if(camera_x<scralim_left)camera_x=scralim_left;
    if(result.goal && camera_x<result.left)camera_x=result.left;
    if(result.phase){camera_x=result.camera_x;camera_y=result.camera_y;}
    scd_camera_v_sync(camera_y);scd_camera_h_sync(camera_x);
    /* Comparison only (TT_ROUTE_LAG): retail R4 runs watercnt in the level
       V-INT (R42A__.MMD $1FEA, and $1F3A on a lag V-INT), once per V-INT frame,
       not once per update. A lagging retail update therefore advances the sway
       angle 2 and moves waterposi_m toward watermoveposi by waterspeed once per
       extra V-INT frame. */
    if(updated){water_camera(camera_x,camera_y);water_currents();water_objects_visible();
        if(lag_count && sequence-2<lag_count && lag[sequence-2]>1 && lag[sequence-2]<8)
            {for(unsigned k=1;k<lag[sequence-2];k++)water_level_step();scd_objects_vint_add(lag[sequence-2]-1u);}
        water_level_step();}
    /* Parity rows (TT_ROUTE_TRACE) sample after the current's nudge, as the retail
       probe does; controller rows keep src/main.c's pre-current sample. */
    trace_x=actwk[0].xposi.w.h;trace_y=actwk[0].yposi.w.h;
    if(getenv("TT_RNG_TRACE"))fprintf(stderr,"RNG %u %08x\n",sequence,(unsigned)ranum); /* diagnostic: Level Random seed */
    /* Diagnostic: TT_TRACE=FIRST:LAST prints Sonic's actor and the vertical camera. */
    {const char *r=getenv("TT_TRACE");if(r && getenv("TT_TRACE_WATER"))fprintf(stderr,"TT water: %u waterposi=%d waterposi_m=%d sysdirec=%u watermoveposi=%d\n",sequence,waterposi,waterposi_m,(unsigned)(sysdirec&255),watermoveposi);long f=r?strtol(r,NULL,10):0,l=r&&strchr(r,':')?strtol(strchr(r,':')+1,NULL,10):-1;
     if((long)sequence>=f && (long)sequence<=l){sprite_status *s=&actwk[0];
        fprintf(stderr,"TT actwk: %u x=%04x.%04x y=%04x.%04x xspeed=%d yspeed=%d camera_y=%d scra_v=%d scralim_down=%d row=%d,%d\n",sequence,
            (uint16_t)s->xposi.w.h,(uint16_t)s->xposi.w.l,(uint16_t)s->yposi.w.h,(uint16_t)s->yposi.w.l,s->xspeed.w,s->yspeed.w,camera_y,scra_v_posit.w.h,scralim_down,row_x,row_y);
        /* Diagnostic (tools/route_margins.py): rings, shield and air per update. */
        if(getenv("TT_TRACE_INVENTORY"))fprintf(stderr,"TT inventory: %u rings=%u shield=%u air=%d\n",sequence,(unsigned)plring,(unsigned)plpower_b,pl_air);}}
    /* Diagnostic: TT_OBJ_TRACE=FIRST:LAST prints every live actor as tools/tt_retail_probe.py
       TT_PROBE_OBJECTS does: seq slot actno sub r_no0 x xsub y ysub xspeed (retail row = seq + 1). */
    {const char *r=getenv("TT_OBJ_TRACE");long f=r?strtol(r,NULL,10):0,l=r&&strchr(r,':')?strtol(strchr(r,':')+1,NULL,10):-1;
     if((long)sequence>=f && (long)sequence<=l)fprintf(stderr,"LIM %u left=%d right=%d down=%d bossflag=%d bossstart=%d camera_x=%d goal=%d goal_left=%d\n",sequence,scralim_left,scralim_right,scralim_down,bossflag,bossstart,camera_x,scd_act_get().goal,scd_act_get().left);
     if((long)sequence>=f && (long)sequence<=l)for(unsigned k=0;k<128;k++){sprite_status *o=&actwk[k];if(!o->actno)continue;
        fprintf(stderr,"OBJ %u %u %u %u %u %d %u %d %u %d %u\n",sequence,k,o->actno,o->userflag.b.h,o->r_no0,o->xposi.w.h,(uint16_t)o->xposi.w.l,o->yposi.w.h,(uint16_t)o->yposi.w.l,o->xspeed.w,scd_boss_retail_slot_peek(k));}}
    uint32_t status=scd_boss_status();
    if(status){
        boss_seen=1;if(status&(1u<<17))egg_seen=1;
        unsigned left=status&255,hits=left<5?5-left:0;if(!egg_seen && hits>boss_hits)boss_hits=hits;
        if(egg_seen && (left<2 || ((status>>8)&255)>=18))egg_hit=1;
    }
    for(unsigned k=SCD_BOSS_FIRST_SLOT;k<128;k++){
        if(actwk[k].actno!=79){bubble_colino[k]=0;continue;}
        if(bubble_colino[k]==255 && !actwk[k].colino)egg_pops++;
        bubble_colino[k]=actwk[k].colino;
    }
    if(bossflag>max_flag)max_flag=bossflag;
    if(result.phase==SCD_ACT_DONE)done=1;
    /* Search only (TT_ROUTE_GOAL=bigring): the act must end through the big ring
       (Level End/Main.asm ObjBigRing, 50 rings); an ordinary tally fails the run.
       A separate statement keeps the line above, which derived hosts patch. */
    {static int bigring=-1;if(bigring<0){const char *g=getenv("TT_ROUTE_GOAL");bigring=g && !strcmp(g,"bigring");}
     if(bigring && result.phase==SCD_ACT_DONE && !scd_objects_big_ring_touched()){done=0;dead=1;}}
    /* Libretro's pad request is sampled two observations later. */
    delayed=buttons;
    buttons=(want&128?SCD_RIGHT:0)|(want&64?SCD_LEFT:0)|(want&32?SCD_DOWN:0)|(want&16?SCD_UP:0)|(want&1?SCD_JUMP:0);
}
static unsigned rng_state;
static unsigned rng(void){rng_state=rng_state*1103515245u+12345u;return (rng_state>>16)&32767;}
static void macro(void){
    static const unsigned choices[]={128,64,0,1,129,65,32,160,96,33,16,144};
    unsigned pad=choices[rng()%12],len=4+rng()%28;
    /* Down + jump starts with one Down-only update (a crouch) unless Down was
       already held while unlocked: native buffers a simultaneous press into a spin dash (PLAN.md controls) and retail does
       not, so routes stay comparable with tools/tt_retail_probe.py. */
    if(pad==33 && (!pad_count || !(pads[pad_count-1]&32) || !unlock_sequence || sequence<unlock_sequence+3)
       && !dead && !done && pad_count<PAD_LIMIT){pads[pad_count++]=32;step(32);}
    if(pad&1){
        unsigned hold=1+rng()%24;
        for(unsigned i=0;i<hold && !dead && !done && pad_count<PAD_LIMIT;i++){
            /* Locked updates ignore the pad: a Down + jump held across the unlock
               reaches the player as a fresh simultaneous press, so hold Down
               alone until the first unlocked updates have read it. */
            unsigned want=(pad==33 && (!unlock_sequence || sequence<unlock_sequence+4))?32:pad;
            pads[pad_count++]=want;step(want);
        }
        pad&=~1u;len=2+rng()%6;
    }
    for(unsigned i=0;i<len && !dead && !done && pad_count<PAD_LIMIT;i++){pads[pad_count++]=pad;step(pad);}
}
/* Search only (TT_ROUTE_MIN_AIR=N): demand that much air left at every update
   (here and in the TT_ROUTE_DUAL mirror), a margin against retail lag. */
static unsigned air_floor(void){static int f=-1;if(f<0)f=getenv("TT_ROUTE_MIN_AIR")?atoi(getenv("TT_ROUTE_MIN_AIR")):1;return (unsigned)f;}
static unsigned dual_query(int cmd,unsigned *air){
    unsigned v[4]={0,0,30,0};
    if(!dual_out)return 1;
    putc(cmd,dual_out);fflush(dual_out);
    if(fread(v,sizeof v[0],4,dual_in)!=4)exit(2);
    dual_x=(int)(v[3]&65535u);dual_y=(int)(v[3]>>16);
    if(cmd==0xFC && getenv("TT_ROUTE_DUAL_DEBUG"))fprintf(stderr,"dual finish: dead=%u done=%u min_air=%u x=%u\n",v[0],v[1],v[2],v[3]);
    if(air)*air=v[2];
    return cmd==0xFC?(v[1] && !v[0] && v[2]>=air_floor()):!v[0] && v[2]>=air_floor();
}
static void dual_start(void){
    const char *v=getenv("TT_ROUTE_DUAL");if(!v)return;
    int down[2],up[2];if(pipe(down)||pipe(up))exit(2);
    pid_t pid=fork();if(pid<0)exit(2);
    if(!pid){
        close(down[1]);close(up[0]);
        unsigned lead=(unsigned)atoi(v);tail_from=tail_from>lead?tail_from-lead:0;
        unsetenv("TT_ROUTE_UNLOCK_AT");unsetenv("TT_ROUTE_VINT_AT");unsetenv("TT_ROUTE_DUAL");lag_count=0;
        /* The mirror never forwards its own steps (dual_out stays NULL). */
        FILE *in=fdopen(down[0],"rb"),*reply=fdopen(up[1],"wb");
        {
         unsigned count=0;int c;
         while((c=getc(in))!=EOF){
             if(c==0xFE){load();count=0;}
             else if(c==0xFD || c==0xFC){
                 if(c==0xFC)for(unsigned t=0;t<1500 && !dead && !done;t++)step(0);
                 int mx=scd_player_get().x/65536,my=scd_player_get().y/65536;
                 unsigned r[4]={dead,done,min_air>0?min_tail:0,(unsigned)(mx<0?0:mx>65535?65535:mx)|(unsigned)(my<0?0:my>65535?65535:my)<<16};fwrite(r,sizeof r[0],4,reply);fflush(reply);
             }
             else if(count++>=lead && !dead && !done)step((unsigned)c);
         }
         exit(0);}
    }
    close(down[0]);close(up[1]);
    dual_out=fdopen(down[1],"wb");dual_in=fdopen(up[0],"rb");
}
/* Search only (TT_ROUTE_BAN=X0:X1:Y): prune a branch whose Sonic is inside
   X0..X1 below Y, a known dead end (TT1D's flooded lower path at x 6848). */
static int banned(void){
    static int init,x0,x1,y0;
    if(!init){init=1;const char *v=getenv("TT_ROUTE_BAN");if(!v || sscanf(v,"%d:%d:%d",&x0,&x1,&y0)!=3)init=2;}
    if(init==2)return 0;
    scd_player_state p=scd_player_get();int x=p.x/65536,y=p.y/65536;
    return x>=x0 && x<=x1 && y>y0;
}
typedef struct {uint32_t key;uint8_t *pads;unsigned length,visits,tried;double value;} cell;
static cell *cells;static unsigned cell_count,cell_capacity;
static unsigned boss_stage(void){
    if(act!=2)return 0;
    return scd_act_get().goal?7:egg_seen?(scd_boss_status()?6:7):max_flag>=4?5:boss_hits>=4?4:boss_hits?1+boss_hits/2:boss_seen?1:0;
}
static uint32_t cell_key(void){
    scd_player_state p=scd_player_get();
    unsigned x=(unsigned)(p.x/65536<0?0:p.x/65536>16383?16383:p.x/65536)/32,y=(unsigned)(p.y/65536<0?0:p.y/65536>2047?2047:p.y/65536)/32;
    unsigned air=(unsigned)pl_air>20?3:(unsigned)pl_air>12?2:(unsigned)pl_air>6?1:0;
    unsigned pops=egg_pops/2>7?7:egg_pops/2;
    uint32_t mirror=dual_x>=0?((uint32_t)(dual_x>16383?16383:dual_x)/512u)<<27:0;
    /* Search only (TT_ROUTE_RINGS): ring count buckets of 8 (the level routes
       have no mirror, so bits 29-31 are free). */
    static int rings=-1;if(rings<0)rings=getenv("TT_ROUTE_RINGS")!=NULL;
    if(rings)mirror|=(uint32_t)((plring>56?56:plring)/8)<<29;
    return x|(y<<9)|(boss_stage()<<15)|(air<<18)|((uint32_t)(boss_hits&7)<<20)|((uint32_t)pops<<23)|((uint32_t)egg_hit<<26)|mirror;
}
static double cell_value(void){
    scd_player_state p=scd_player_get();int x=p.x/65536;
    double v=boss_stage()*100000.0+boss_hits*20000.0+(dual_x>=0 && dual_x<x && act<2?dual_x:x);
    /* Search only (TT_ROUTE_RINGS=W): W per ring up to 50, 20000 more from 50. */
    {static int w=-1;if(w<0)w=getenv("TT_ROUTE_RINGS")?atoi(getenv("TT_ROUTE_RINGS")):0;
     if(w)v+=(plring>50?50:plring)*(double)w+(plring>=50?20000.0:0);}
    /* The egg4 fight (stage 6): pop shield bubbles (each also refills air),
       stay close to the boss so a rolling hit can land. The value stays inside
       (616384, 700000): above every stage 5 cell (500000 + 5 hits * 20000 + x;
       egg4air reports 5 hits, colicnt 5 -> 0) and below every stage 7 cell. At
       600000 - distance the egg's spawn (the ACTSET right walk reaches its
       record at 2736 near Sonic x 2336) scored below the cells before it. */
    if(boss_stage()==6){uint32_t b=scd_boss_position();int bx=(int16_t)(b>>16),by=(int16_t)b,y=p.y/65536;
        double d=sqrt((double)(x-bx)*(x-bx)+(double)(y-by)*(y-by));
        v=640000.0+egg_hit*30000.0+(egg_pops<15?egg_pops:15)*1500.0-(d<1000.0?d:1000.0)*20.0;}
    /* Prefer states with air left; a low counter ends branches later. */
    if(pl_air<8)v-=(8-pl_air)*400.0;
    /* Search only (TT_ROUTE_UP=K): K x per pixel climbed (2048 - y), for a
       stage that must climb before it can move right. */
    {static double k=-1;if(k<0)k=getenv("TT_ROUTE_UP")?atof(getenv("TT_ROUTE_UP")):0;if(k>0)v+=k*(2048-p.y/65536);}
    /* Search only (TT_ROUTE_DUAL_PULL=K): K x per pixel between Sonic and the
       TT_ROUTE_DUAL mirror, so the plain and retail-aligned runs stay close
       enough that one tail can carry both through a narrow climb. */
    {static double k=-1;if(k<0)k=getenv("TT_ROUTE_DUAL_PULL")?atof(getenv("TT_ROUTE_DUAL_PULL")):0;
     if(k>0 && dual_x>=0){double dx=dual_x-x,dy=dual_y-p.y/65536;v-=k*sqrt(dx*dx+dy*dy);}}
    /* Search only (TT_ROUTE_AIR_WEIGHT=W): W x per unit of air, so a branch
       that waits at a bubble master for a large bubble can lead a long
       flooded stretch. */
    {static double w=-1;if(w<0)w=getenv("TT_ROUTE_AIR_WEIGHT")?atof(getenv("TT_ROUTE_AIR_WEIGHT")):0;v+=w*pl_air;}
    return v;
}
static void archive(void){
    if(dead)return;
    if(min_tail<air_floor() || banned()){dead=1;return;}
    if(dual_out && !dual_query(0xFD,NULL)){dead=1;return;}
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
static void found(unsigned it,const char *out){
    write_script(out);
    fprintf(stderr,"search done: iterations=%u cells=%u sequence=%u min_air=%u\n",it,cell_count,sequence,min_air);
}
static double explore=0.05;
/* A tally tools/test_tt_route.py accepts: air never ran out, and Act 3 has
   four boss hits and the egg. Other tallies do not end the search. */
static int gate_ok(void){return min_air>0 && min_tail>=air_floor() && (act!=2 || (boss_hits>=4 && egg_seen));}
static int search(unsigned seed,unsigned iterations,const char *out,const char *prefix){
    if(prefix){read_script(prefix,PAD_LIMIT);tail_from=pad_count+1;}
    dual_start();rng_state=seed;load();
    for(unsigned i=0;i<pad_count && !dead;i++)step(pads[i]);
    if(dead){fprintf(stderr,"prefix died\n");return 2;}
    archive();
    double top=-1e30;
    static double weight[1<<20];
    for(unsigned it=0;it<iterations;it++){
        double best=-1e30;for(unsigned i=0;i<cell_count;i++)if(cells[i].value>best)best=cells[i].value;
        double total=0;
        for(unsigned i=0;i<cell_count && i<(1u<<20);i++){
            /* Tidal Tempest winds up, down and back: besides the frontier,
               every cell keeps a novelty weight (after Go-Explore's count
               weighting), so a detour through a low x can be found. */
            double w=(cells[i].value>=best-200?4.0:cells[i].value>=best-2000?1.0:explore)/sqrt(cells[i].visits+1.0);
            weight[i]=w;total+=w;
        }
        double r=(rng()/32768.0+rng()/1073741824.0)*total;unsigned pick=0;
        for(;pick+1<cell_count && r>weight[pick];pick++)r-=weight[pick];
        cells[pick].visits++;restore(&cells[pick]);
        /* A goal-reached cell first tries a neutral finish: the sign, the
           capsule and the tally need no input. */
        if(scd_act_get().goal && !cells[pick].tried){
            cells[pick].tried=1;
            for(unsigned t=0;t<1500 && !dead && !done && pad_count<PAD_LIMIT;t++){pads[pad_count++]=0;step(0);}
            if(done && gate_ok() && dual_query(0xFC,NULL)){found(it,out);return 0;}
            done=0;restore(&cells[pick]);
        }
        unsigned macros=4+rng()%24;
        for(unsigned m=0;m<macros && !dead && !done;m++){macro();archive();}
        if(done && gate_ok() && dual_query(0xFC,NULL)){found(it,out);return 0;}
        done=0;
        if(best>top || it%2000==0){
            top=best;unsigned b=0;for(unsigned i=0;i<cell_count;i++)if(cells[i].value>cells[b].value)b=i;
            uint32_t k=cells[b].key;
            fprintf(stderr,"it %u cells %u best %.0f x~%u y~%u boss %u len %u\n",it,cell_count,cells[b].value,(k&511)*32,((k>>9)&63)*32,(k>>15)&7,cells[b].length);
            /* Diagnostic (TT_ROUTE_BEST=FILE): the best cell's pads, for a stalled search. */
            if(getenv("TT_ROUTE_BEST")){FILE *f=fopen(getenv("TT_ROUTE_BEST"),"w");
                for(unsigned i=0;f && i<cells[b].length;){unsigned j=i;while(j<cells[b].length && cells[b].pads[j]==cells[b].pads[i])j++;fprintf(f,"%u %u\n",j-i,cells[b].pads[i]);i=j;}
                if(f)fclose(f);}
        }
    }
    if(getenv("TT_ROUTE_CELLS")){
        FILE *f=fopen(getenv("TT_ROUTE_CELLS"),"w");
        if(f){for(unsigned i=0;i<cell_count;i++)fprintf(f,"%u %u %u\n",(cells[i].key&511)*32,((cells[i].key>>9)&63)*32,(cells[i].key>>18)&3);fclose(f);}
    }
    unsigned b=0;for(unsigned i=0;i<cell_count;i++)if(cells[i].value>cells[b].value)b=i;
    restore(&cells[b]);write_script(out);
    fprintf(stderr,"search end: cells=%u value=%.0f\n",cell_count,cells[b].value);
    return 1;
}
int main(int argc,char **argv){
    if(argc<6 || strlen(argv[2])!=3 || argv[2][1]!=':' || argv[2][0]<'0' || argv[2][0]>'2' || argv[2][2]<'A' || argv[2][2]>'D'){
        fprintf(stderr,"usage: tt_route_search replay ACT:ERA SCRIPT LIMIT OUTPUT | search ACT:ERA SEED ITERATIONS OUTSCRIPT [PREFIX]\n");return 2;
    }
    act=(unsigned)(argv[2][0]-'0');era=(unsigned)(argv[2][2]-'A');
    if(getenv("TT_ROUTE_LAG")){
        FILE *f=fopen(getenv("TT_ROUTE_LAG"),"r");char line[256];
        while(f && fgets(line,sizeof line,f) && lag_count<48000){unsigned v[9];unsigned w;int n=sscanf(line,"%u %u %u %u %u %u %u %u %u %u",v,v+1,v+2,v+3,v+4,v+5,v+6,v+7,v+8,&w);if(n>=9){if(n==10 && vint_lag_count==lag_count)vint_lag[vint_lag_count++]=(unsigned char)w;lag[lag_count++]=(unsigned char)v[8];}}
        if(f)fclose(f);
    }
    if(getenv("TT_ROUTE_EXPLORE"))explore=atof(getenv("TT_ROUTE_EXPLORE"));
    if(act==2 && era<2)return 2;
    read_assets();
    if(!strcmp(argv[1],"search"))return search((unsigned)atoi(argv[3]),(unsigned)atoi(argv[4]),argv[5],argc>6?argv[6]:NULL);
    if(!strcmp(argv[1],"actors")){
        /* Diagnostic: replay SCRIPT for LIMIT updates, list the actors near Sonic. */
        read_script(argv[3],PAD_LIMIT);load();unsigned limit=(unsigned)atoi(argv[4]);
        for(unsigned i=0;i<limit && !dead;i++)step(i<pad_count?pads[i]:0);
        scd_player_state p=scd_player_get();printf("sonic %d,%d dead %u\n",p.x/65536,p.y/65536,dead);
        for(unsigned k=1;k<=96;k++){sprite_status *o=&actwk[k];if(!o->actno)continue;
            int dx=o->xposi.w.h-p.x/65536,dy=o->yposi.w.h-p.y/65536;
            if((abs(dx)<400 && abs(dy)<300) || getenv("TT_ACTORS_ALL"))printf("actor %u type %u at %d,%d r_no0 %u sub %d size %u,%u flg %02x\n",k,o->actno,o->xposi.w.h,o->yposi.w.h,o->r_no0,o->userflag.b.h,o->sprhsize,o->sprvsize,o->actflg);}
        return 0;
    }
    if(!strcmp(argv[1],"probe")){
        /* Diagnostic: from PREFIX, try Right runs of R updates with a Jump
           held J updates after B; report the furthest x and the outcome. */
        unsigned base=0;read_script(argv[3],PAD_LIMIT);base=pad_count;
        static unsigned saved[48000];memcpy(saved,pads,sizeof(unsigned)*base);
        for(unsigned back=0;back<=80;back+=20)for(unsigned b=0;b<60;b+=4)for(unsigned j=4;j<=24;j+=10){
            load();for(unsigned i=0;i<base;i++)step(saved[i]);
            for(unsigned i=0;i<back && !dead;i++)step(64);
            int mx=0,my=0;
            for(unsigned i=0;i<240 && !dead;i++){step(i>=b && i<b+j?129:128);scd_player_state p=scd_player_get();if(p.x/65536>mx){mx=p.x/65536;my=p.y/65536;}}
            printf("back %u jump@%u hold %u: max x %d (y %d) dead %u air %d\n",back,b,j,mx,my,dead,pl_air);
        }
        return 0;
    }
    if(strcmp(argv[1],"replay"))return 2;
    unsigned limit=(unsigned)atoi(argv[4]);if(limit<10 || limit>PAD_LIMIT)return 2;
    read_script(argv[3],limit);load();
    FILE *out=fopen(argv[5],"w");if(!out){perror(argv[5]);return 2;}
    for(unsigned i=0;i<limit;i++){
        unsigned want=i<pad_count?pads[i]:0;
        step(want);
        scd_player_state p=scd_player_get();
        if(dead){fprintf(stderr,"Route failed at %u x=%d y=%d dead=%u drowned=%u air=%d\n",sequence,p.x/65536,p.y/65536,dead,drowned,pl_air);fclose(out);return 3;}
        if(getenv("TT_ROUTE_TRACE"))fprintf(out,"%u %u %d %d %d %d %d %u %d %d %u %u %u\n",sequence,want,trace_x,trace_y,waterposi,waterposi_m,actwk[0].yspeed.w,actwk[0].cddat,
                                          actwk[0].mspeed.w,actwk[0].xspeed.w,actwk[0].xposi.w.l,actwk[0].yposi.w.l,actwk[0].direc.b.h);
        else fprintf(out,"%u %u %d %d\n",sequence,want,row_x,row_y);
        /* Diagnostic: TT_ROUTE_OBJECTS=FIRST:LAST:FILE writes every live slot on
           sequences FIRST..LAST in tools/tt_retail_probe.py's TT_PROBE_OBJECTS
           format, labelled with the aligned retail row (sequence + 1). */
        {static FILE *od;static long of=-1,ol=-1;const char *e=getenv("TT_ROUTE_OBJECTS");
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
            fprintf(stderr,"Tally complete: sequence=%u act=%u era=%u score=%u min_air=%u boss_hits=%u egg=%u\n",
                    sequence,act,era,p.score,min_air,boss_hits,egg_seen);
            return 0;
        }
    }
    fclose(out);fprintf(stderr,"Route incomplete\n");return 1;
}
