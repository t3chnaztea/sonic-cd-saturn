/* Bounded native object scheduler. Original spring/damage impulses are linked
 * from generated interaction.c; placement IDs come from the Sega CD version. */
#ifdef SCD_OBJECTS_VERIFY
#include <assert.h>
#endif
#include "time_attack.h"
#include "EQU.H"
#include "player_plus.h"
#include "PLAYER.H"
#include "SPRING.H"
#include "DIRCOL.H"
#include "ETC.H"
#include "scd_actor.h"
#include "scd_objects.h"
#include "scd_player.h"
#include "act.h"
#include <string.h>
#include <stdlib.h>
static int magnitude(int value) {return (int)(value<0?0u-(unsigned)value:(unsigned)value);}
#include "objects.inc"
#include "objects2.inc"
#include "objects3.inc"
#include "scd_boss.h"
#include "zone_r3_names.h"
#include "zone_r4_names.h"
#include "zone_r5_names.h"
#include "zone_r6_names.h"
#include "zone_r7_names.h"
#include "zone_r8_names.h"
#include "zone_code.h"
static unsigned objects_zone;
/* Every entry that may dispatch through zone_ops runs only while the zone's code overlay
   is loaded (src/zone_code.h); a violation stops here instead of jumping into stale code.
   Keep the fault visible to the route harness: abort otherwise looks exactly like an
   unexplained permanent freeze on the console and in the emulator.  The guard itself is
   deliberately retained until the invalid state is diagnosed. */
#ifdef SCD_ZONE_OVERLAY
volatile uint32_t scd_objects_overlay_fault[4];
static void zone_ops_fault(unsigned callsite){
    scd_objects_overlay_fault[1]=objects_zone;
    scd_objects_overlay_fault[2]=scd_zone_code_zone;
    scd_objects_overlay_fault[3]=callsite;
    scd_objects_overlay_fault[0]=0x5a4f4e45; /* 'ZONE', written last */
    cpu_cache_area_purge((void *)scd_objects_overlay_fault,sizeof(scd_objects_overlay_fault));
    abort();
}
#define ZONE_OPS_LOADED(callsite) do{if(zone_ops && !scd_zone_code_ready(objects_zone))zone_ops_fault(callsite);}while(0)
#else
#define ZONE_OPS_LOADED(callsite) do{(void)(callsite);}while(0)
#endif
static const scd_placement *active_placements=placements;
static unsigned objects_act;
/* Act 2 collapsing platforms share one table set for every era (KUZUR12A-D.C). */
#define COLLAPSE_COUNT(era,single) (objects_act?collapse_counts_act2[single]:collapse_counts[era][single])
#define COLLAPSE_SHAPE(era,single,index) (objects_act?&collapse_shapes_act2[single][index]:&collapse_shapes[era][single][index])
#define COLLAPSE_BASE(era,family) (objects_act?collapse_bases_act2[family]:collapse_bases[era][family])
static unsigned active_placement_count=sizeof(placements)/sizeof(*placements);
/* Zones past Palmtree Panic carry no compiled placements. Their layouts are
   translated per act by tools/object_layouts.py, which resolves each retail
   record through that program's own act_tbl, and are loaded from the CD beside
   the act's terrain. scd_objects_layout hands the loaded table in; until it
   does, such a zone spawns nothing rather than misreading Palmtree Panic's ids. */
_Static_assert(sizeof(scd_placement)==10,"object layout files hold ten-byte records");
/* Zone hooks; the table itself follows the zone actor files (objects_zone_ops.inc). Zones
   whose actor code runs from their overlay (heap plan B) are reached only through it. */
static const scd_zone_ops *const zone_ops_table[7];
static const scd_zone_ops *zone_ops;
/* The original round number of the loaded zone (1 PPZ, 3 CC, 4 TT, 5 QQ, ...). */
static unsigned objects_round(void){static const uint8_t rounds[7]={1,3,4,5,6,7,8};return objects_zone<7?rounds[objects_zone]:1;}
void scd_objects_zone(unsigned zone){objects_zone=zone;zone_ops=zone<7?zone_ops_table[zone]:0;}
static uint32_t level_vint;
/* RING.C:420 sys_pattim4 (PPZ Ring/Main.asm:376 ringLossAnimTimer): one spill
   timer for every lost ring, set to 255 by each spill and counted down once
   per update by GAME.C:831-836 syspatchg after the actors ran (GAME.C:636
   clears it); flyringmove (RING.C:469) deletes a ring once it reads 0, so a
   later spill keeps the earlier rings too (retail MM1A spill 658: rings live
   through 912; retail CC2C seed 24: spill 3239, 255 updates). */
static uint8_t mm_spill_timer,mm_spill_rings; /* mm_spill_rings: MM spill size while its first ring waits for flyringinit */
/* Level/Main.asm UpdateGlobalAnims (GAME.C syspatchg), run once per update after
   the objects: ringAnimTimer/Frame ($FF1912/3) step every 8 updates and every
   placed ring copies ringAnimFrame (Ring/Main.asm:226-229, retail R11A $209E96),
   so all rings spin in phase. Each spill sets ringLossAnimTimer to 255 in every
   zone (mm_spill_timer above); while it runs, ringLossAnimAccum += timer and
   ringLossAnimFrame = accum >> 9 & 3, which every lost ring copies
   (Ring/Main.asm:411, R11A $20A074). Level start clears all of them (GAME.C:630-638). */
static uint8_t ring_anim_timer,ring_anim_frame,ring_loss_frame;static uint16_t ring_loss_accum;
static void global_anims_reset(void){ring_anim_timer=ring_anim_frame=ring_loss_frame=mm_spill_timer=0;ring_loss_accum=0;}
void scd_objects_vint_add(unsigned n){level_vint+=n;}
unsigned scd_objects_vint(void){return level_vint;}
void scd_objects_layout(const scd_placement *layout,unsigned count){
    level_vint=0;global_anims_reset();
    if(!objects_zone)return;
    active_placements=layout;
    active_placement_count=count<SCD_PLACEMENT_CAPACITY?count:SCD_PLACEMENT_CAPACITY;
}
void scd_objects_act(unsigned act){
    objects_act=act;
    active_placements=act==2?placements_act3:act?placements_act2:placements;
    active_placement_count=act==2?sizeof(placements_act3)/sizeof(*placements_act3):act?sizeof(placements_act2)/sizeof(*placements_act2):sizeof(placements)/sizeof(*placements);
    if(objects_zone)active_placement_count=0;
}
/* src/boss.c provides these with the Act 3 boss; host tools without it link no-ops. */
__attribute__((weak)) void scd_boss_reset(void){}
__attribute__((weak)) void scd_boss_create(int x,int y){(void)x;(void)y;}
__attribute__((weak)) void scd_boss_create_sub(int x,int y,unsigned subtype,unsigned round){(void)subtype;(void)round;scd_boss_create(x,y);}
__attribute__((weak)) void scd_boss6_door(int x,int y,unsigned kind,unsigned floor){(void)x;(void)y;(void)kind;(void)floor;}
__attribute__((weak)) void scd_boss_step(void){}
__attribute__((weak)) void scd_boss_camera(int x,int y){(void)x;(void)y;}
__attribute__((weak)) uint32_t scd_boss_hash(void){return 0;}
__attribute__((weak)) void scd_boss_palette_set(int state){(void)state;}
__attribute__((weak)) int scd_boss_borrowed_slot(unsigned actor){(void)actor;return 0;}
#ifndef SCD_ZONE_OVERLAY
/* Host object fixtures omit boss.c; the Saturn build gets these services there. */
__attribute__((weak)) void sub_sync(short request){(void)request;}
__attribute__((weak)) void divdevset(int plc){(void)plc;}
#endif
#include "collapse.inc"
#include "tunnels.inc"
#include "projector.inc"
#include "amy.inc"
/* Zone objects ported from the retail source, one family per file. */
#include "objects_walls.inc"
#include "objects_dair5.inc"
#include "objects_konbea.inc"
#include "objects_piston.inc"
extern void soundset(short);
/* Frame-profile sub-spans (src/main.c); host tools link this weak no-op. */
__attribute__((weak)) void scd_profile_span(unsigned slot,int begin){(void)slot;(void)begin;}
extern void playdamagechk(sprite_status *,sprite_status *);
extern short playdieset(sprite_status *);
typedef struct {uint16_t origin,age,cooldown;uint8_t type,subtype,flags,state,frame,sink,parent;int16_t home_x,home_y;uint16_t timer,phase;int32_t debris_vx,debris_vy;uint8_t anim,prev_anim,anim_frame,anim_time;} slot;
/* Slots that may hold a time post: set wherever a slot takes a computed type
   (a superset; touch_arbitrate drops stale bits), so the per-update touch
   scan outside Palmtree Panic visits only these. */
static uint32_t timepost_mask[(SCD_OBJECT_CAPACITY+31)/32];
static inline void pool_typed(unsigned i,unsigned type){if(type==SCD_OBJ_TIMEPOST)timepost_mask[i/32]|=1u<<(i%32);}
static slot pool[SCD_OBJECT_CAPACITY];
/* Boss actors may occupy a free physical pool slot in WW3. The shared retail
   slot table still owns that actwk entry until frameout clears actno. */
static int pool_slot_free(unsigned i){return !pool[i].type && !actwk[i+1].actno && !scd_boss_borrowed_slot(i+1);}
static unsigned control_actor;
static uint8_t amy_palette_active,amy_idle_cursor,amy_idle_timer,amy_idle_pose;
static uint8_t emie_palette_active,emie3_ended;
/* R3/MECASNC.C emie3_clr, mapped through the original video DAC levels. */
static const uint16_t emie_palette[16]={32768,32768,46225,50454,64959,65247,65535,56022,50737,41224,50911,33210,33604,33312,50189,32799};
int scd_objects_amy_palette(uint16_t *colors){
    if(amy_palette_active && colors)memcpy(colors,amy_palette,sizeof(amy_palette));
    else if(emie_palette_active && colors)memcpy(colors,emie_palette,sizeof(emie_palette));
    return amy_palette_active || emie_palette_active;
}
int scd_objects_amy_idle_frame(void){return control_actor && pool[control_actor-1].type==SCD_OBJ_AMY && actwk[0].mstno.b.h==5?(int)amy_idle_pose-1:-1;}
void scd_objects_amy_idle_step(void){
    if(scd_objects_amy_idle_frame()<0)return;
    if((int8_t)--amy_idle_timer>=0)return;
    static const uint8_t poses[]={1,1,1,1,1,1,1,1,1,1,1,1,3,2,2,2,3,4};
    if(amy_idle_cursor==sizeof(poses))amy_idle_cursor-=2;
    amy_idle_pose=poses[amy_idle_cursor++];amy_idle_timer=23;
}
void scd_objects_release_control(void){
    if(control_actor){if(pool[control_actor-1].type==SCD_OBJ_AMY){pool[control_actor-1].state=6;actwk[control_actor].actfree[0]&=~1;}else pool[control_actor-1].state=0;actwk[0].actfree[2]&=~0xC1;control_actor=0;}
}
/* Word aligned: scd_objects_get scans them four bytes at a time. */
static uint8_t consumed[SCD_PLACEMENT_CAPACITY] __attribute__((aligned(4)));
static uint8_t deferred_reload[SCD_PLACEMENT_CAPACITY] __attribute__((aligned(4)));
static unsigned era_bit,load_placements,current_era;
static uint8_t era_consumed[4][SCD_PLACEMENT_CAPACITY];
static int pending_post,pending_generator,good_future,projector_destroyed;
static unsigned time_stones,big_ring_touched,big_ring_pending;
void scd_objects_time_stones(unsigned stones){time_stones=stones;}
int scd_objects_big_ring(void){int pending=big_ring_pending;big_ring_pending=0;return pending;}
int scd_objects_big_ring_touched(void){return big_ring_touched;}
int scd_objects_projector_destroyed(void){return projector_destroyed;}
int scd_objects_generator(void){int g=pending_generator;pending_generator=0;return g;}
static int travel_protection;
static uint8_t collision_mask[SCD_OBJECT_CAPACITY];
void scd_objects_travel_protection(int active){travel_protection=active;}
static int enemy(unsigned t){return t==34 || (t>=61 && t<=64) || (scd_zone_local(t) && zone_ops && zone_ops->enemy && zone_ops->enemy(t));}
/* The CD++ homing attack (src/player_plus.c) targets these types. */
int scd_objects_enemy_type(unsigned type){return enemy(type);}
static int tt_contact_type(unsigned t); /* objects_tt_common.inc */
static int tp_type(unsigned t);static void tp_reset(void); /* objects_tt_ride.inc */
static void tt_wave_spawn(void); /* objects_tt_wave.inc */
static void tt_card_allocate(void);static uint8_t tt_card_pending;
static int cc_touch_arbitrate(void);
static uint8_t ring_loaded[SCD_PLACEMENT_CAPACITY]; /* below, with the Object Spawner */
void scd_objects_collision_begin(void){
    ZONE_OPS_LOADED(1);
    memset(collision_mask,0,sizeof(collision_mask));
    if(objects_zone==1 && cc_touch_arbitrate()){
        for(unsigned i=31;i<SCD_OBJECT_CAPACITY;i++)if(actwk[i+1].colino){collision_mask[i]=actwk[i+1].colino;actwk[i+1].colino=0;}
        return;
    }
    /* harir3_step makes TRAP_R3.C harir3's COLI3 touch test itself (its colitbl
       box: 16 wide for colino 130). Masked here so play01's pcol, which is COLI1
       outside a boss, does not test it again with COLI1's 18 (retail CC1 Good
       Future: the side spike at X 3568 hurts at Sonic X 3592, not 3594).
       MECASNC.C hari3x (colino 134) takes its touch in cc_scan like the CC
       enemies; unmasked, a spike in pool 31+ (CC1A after a ring spill) was hurt
       from here first, before stream() (tools/test-cc-hari3x-mask.sh). */
    for(unsigned i=31;i<SCD_OBJECT_CAPACITY;i++)
        if(((pool[i].type>=SCD_OBJ_GA && pool[i].type<=SCD_OBJ_TOGEBALL) || (objects_zone==6 && pool[i].type==SCD_OBJ_BOBIN) || pool[i].type==SCD_OBJ_CC_GENERATOR || pool[i].type==SCD_OBJ_HARIR3 || pool[i].type==SCD_OBJ_HARI3X || tt_contact_type(pool[i].type) || (scd_zone_local(pool[i].type) && zone_ops && zone_ops->contact && zone_ops->contact(pool[i].type))) && actwk[i+1].colino){
            collision_mask[i]=actwk[i+1].colino;actwk[i+1].colino=0;
        }
}
void scd_objects_collision_end(void){
    for(unsigned i=31;i<SCD_OBJECT_CAPACITY;i++)if(collision_mask[i]){
        actwk[i+1].colino=collision_mask[i];collision_mask[i]=0;
    }
}
int scd_objects_timepost(void){int d=pending_post;pending_post=0;return d;}
/* src/boss.c slot model: Quartz Quadrant checkpoints hold a second retail slot for
   the ball their init spawns (Checkpoint/Main.asm .GenBall). */
int scd_objects_slot_companion(unsigned actor){return objects_zone==3 && actor && actor<=SCD_OBJECT_CAPACITY && pool[actor-1].type==SCD_OBJ_CHECKPOINT;}
static void spawner_restart(void); /* with the Object Spawner state below */
void scd_objects_change_era(unsigned era){
    memcpy(era_consumed[current_era],consumed,sizeof(consumed));
    scd_objects_clear_live();current_era=era&3;era_bit=1u<<(era==0?1:era==1?0:2);
    memcpy(consumed,era_consumed[current_era],sizeof(consumed));pending_post=0;
    /* The arrival program starts with its own cleared ring clocks. */
    global_anims_reset();
    /* SS: GAME.C game_init / LevelStart (retail R71A $2016FE) clears gametimer
       (levelFrames) in the arrival program; ss_reset does it on a restart. */
    if(objects_zone==5)gametimer.w=0;
    /* Time travel loads the other era's level: SpawnObjects_Init runs again on
       the arrival camera (Level/Object Spawner.asm). */
    spawner_restart();
    tt_wave_spawn();
}
static scd_object_stats stats;
static int contact_top,contact_bottom;
int ride_on_chk_s(sprite_status *o,sprite_status *p){(void)o;(void)p;return contact_top;}
int ride_on_chk_s1(sprite_status *o,sprite_status *p){(void)o;(void)p;return contact_top;}
int ride_on_chk_s2(sprite_status *o,sprite_status *p){(void)o;(void)p;return contact_bottom;}
/* One byte per type value. The comparison chain this replaces ran on every
   spawn; the ring-loss scatter spawns twenty objects in a single update.
   tools/test_objects.py checks the table against the original list. */
static const uint8_t supported_types[256]={
    [SCD_OBJ_BIG_RING]=1,[SCD_OBJ_CAPSULE]=1,[SCD_OBJ_FLOWER]=1,[SCD_OBJ_SPRINGBOARD]=1,
    [SCD_OBJ_SWING]=1,[SCD_OBJ_AMY]=1,[SCD_OBJ_AMY_HEART]=1,[SCD_OBJ_ANIMAL]=1,
    [SCD_OBJ_PROJECTOR]=1,[SCD_OBJ_SPIN_TAG]=1,[SCD_OBJ_SCENERY]=1,[SCD_OBJ_LOG_SHADOW]=1,
    [SCD_OBJ_DOOR]=1,[SCD_OBJ_DOOR_V]=1,[SCD_OBJ_MOVING_SPRING]=1,[SCD_OBJ_DISC]=1,
    [SCD_OBJ_SONIC_HOLE]=1,[SCD_OBJ_TUNNEL]=1,[SCD_OBJ_COLLAPSE]=1,[SCD_OBJ_MONITOR_ITEM]=1,
    [SCD_OBJ_GOAL]=1,[SCD_OBJ_SIGN]=1,[SCD_OBJ_WALL]=1,[SCD_OBJ_CHECKPOINT]=1,
    [SCD_OBJ_PLATFORM]=1,[SCD_OBJ_FLOAT_BLOCK]=1,[SCD_OBJ_RAMP]=1,[SCD_OBJ_RAMP_PLANT]=1,
    [SCD_OBJ_TAMABBOH]=1,[SCD_OBJ_MOSQUI]=1,[SCD_OBJ_PATABATA]=1,[SCD_OBJ_ANTON]=1,
    [SCD_OBJ_TAGATAGA]=1,[SCD_OBJ_GENERATOR]=1,[SCD_OBJ_EXPLOSION]=1,[SCD_OBJ_TIMEPOST]=1,
    [SCD_OBJ_SPRING]=1,[SCD_OBJ_RING]=1,[SCD_OBJ_LOST_RING]=1,[SCD_OBJ_BOULDER]=1,
    [SCD_OBJ_SPIKES]=1,[SCD_OBJ_BOBIN]=1,[SCD_OBJ_FRIP]=1,
    [SCD_OBJ_WALL4]=1,[SCD_OBJ_WALL7]=1,[SCD_OBJ_DAIR5]=1,[SCD_OBJ_KONBEA]=1,[SCD_OBJ_PISTON]=1,[SCD_OBJ_FOR3]=1,[SCD_OBJ_HARIR3]=1,[SCD_OBJ_FRDR3]=1,[SCD_OBJ_TRAPDR3]=1,[SCD_OBJ_GETDAIR3]=1,[SCD_OBJ_GANDAIR3]=1,[SCD_OBJ_GA]=1,[SCD_OBJ_TENTOU]=1,[SCD_OBJ_KAMA]=1,[SCD_OBJ_KAMA_BLADE]=1,[SCD_OBJ_BANPA]=1,[SCD_OBJ_TOGEBALL]=1,[SCD_OBJ_POCKET]=1,[SCD_OBJ_CC_POINTS]=1,[SCD_OBJ_CC_GENERATOR]=1,[SCD_OBJ_DRUMR3]=1,[SCD_OBJ_MOVIE3]=1,[SCD_OBJ_FRIEND3]=1,[SCD_OBJ_EMIE3]=1,[SCD_OBJ_HARI3X]=1,[SCD_OBJ_MECASNC3]=1,[SCD_OBJ_SIKAKE33]=1,
    /* Tidal Tempest actors (objects_tt_*.inc). */
    [SCD_OBJ_TONBO]=1,[SCD_OBJ_YAGO]=1,[SCD_OBJ_AMENBO]=1,[SCD_OBJ_TAGAMEB]=1,[SCD_OBJ_HARIR4]=1,[SCD_OBJ_HARID4]=1,
    [SCD_OBJ_SCREW]=1,[SCD_OBJ_SCREW_F]=1,[SCD_OBJ_OSUMIZU]=1,[SCD_OBJ_FUNSUI4]=1,[SCD_OBJ_UKIDAI]=1,[SCD_OBJ_BOU]=1,
    [SCD_OBJ_AWA]=1,[SCD_OBJ_FRIEND4]=1,[SCD_OBJ_MOVIE4]=1,[SCD_OBJ_ET4]=1,
    [SCD_OBJ_SW4]=1,[SCD_OBJ_ESCAL4]=1,[SCD_OBJ_RBLK4]=1,[SCD_OBJ_UDBLK4]=1,[SCD_OBJ_TEKKYU4]=1,[SCD_OBJ_KUZURE4]=1,[SCD_OBJ_TOBIRA4]=1,
    [SCD_OBJ_RENKETU4]=1,[SCD_OBJ_SWGUN4]=1,[SCD_OBJ_BRUNKO4]=1,[SCD_OBJ_LRBLK4]=1,[SCD_OBJ_SWBLKR4]=1,[SCD_OBJ_WALLS]=1,[SCD_OBJ_TEKKYU]=1,
    [SCD_OBJ_TEKKYU1]=1,[SCD_OBJ_TOBIRAS4]=1,[SCD_OBJ_BANEIWA]=1,[SCD_OBJ_DAID4]=1,[SCD_OBJ_WALL42]=1};
static int supported(unsigned type) {
    if(scd_zone_local(type))return zone_ops && zone_ops->step;
    return type<sizeof(supported_types) && supported_types[type];
}

/* Standing references use actor indices (pool slot + 1), as PLAYER.C expects. */
static void release_rider(unsigned actor){
    sprite_status *p=&actwk[0];
    if(actor && actor<=SCD_OBJECT_CAPACITY)actwk[actor].cddat&=~8;
    if((p->cddat&8) && p->actfree[19]==actor){
        p->cddat=(p->cddat&~8)|2;p->actfree[19]=0;p->actfree[14]=0;
        if(actor && actor<=SCD_OBJECT_CAPACITY && control_actor==actor && pool[actor-1].type==SCD_OBJ_DISC && !(p->actfree[2]&64) && p->mstno.b.h!=23){p->actfree[2]&=~1;control_actor=0;}
        /* Object Solid.asm GetOffObject (RIDECHK.C ride_on_clr) only plays the
           charge-stop sound: the peelout/spindash charge timer keeps running
           in the air, and a landing with a 30 left over takes the balance
           stop in PLAYER.C play00walk. */
        if(p->actfree[0])soundset(171);
    }
}
unsigned scd_objects_standing_type(void){
    sprite_status *p=&actwk[0];unsigned actor=p->actfree[19];
    return (p->cddat&8) && actor && actor<=SCD_OBJECT_CAPACITY?pool[actor-1].type:0;
}
void scd_objects_validate_rider(void){
    sprite_status *p=&actwk[0];if(!(p->cddat&8))return;
    unsigned actor=p->actfree[19];
    /* Boss actors keep their rider through RIDECHK.C's own ride_on_clr,
       including WW actors placed in a free physical slot below 97. */
    if(actor<128 && (actor>=SCD_BOSS_FIRST_SLOT || scd_boss_borrowed_slot(actor)) && actwk[actor].actno)return;
    /* An airborne rider stays on a Collision Chaos flipper: BOBIN.C frip_chk
       (R32D $20ACE2) releases him itself, and StandOnObject ($2089DC) returns
       early while his standing bit names the flipper, so he stays airborne on
       its surface (CC2D: a bumper break skips the flipper's update). */
    /* DeleteObject (warp_despawn) leaves Sonic standing on the deleted object. */
    if(scd_player_warp_saved() && actor && actor<=SCD_OBJECT_CAPACITY && !pool[actor-1].type)return;
    /* WW ObjBouncePlatform_Solid returns before its ride check while Sonic
       rises faster than $600. CheckJump leaves the standing bit set, so the
       platform clears it only when the upward speed enters that window. */
    if(actor && actor<=SCD_OBJECT_CAPACITY && pool[actor-1].type==SCD_OBJ_R6_TOBIDAI6 && p->yspeed.w<-1536)return;
    int airborne=(p->cddat&2) && !(actor && actor<=SCD_OBJECT_CAPACITY && pool[actor-1].type==SCD_OBJ_FRIP);
    if(!actor || actor>SCD_OBJECT_CAPACITY || !pool[actor-1].type || p->r_no0>=4 || airborne)release_rider(actor);
}
#include "objects_bobin.inc"
#include "objects_for3.inc"
void scd_boss_slot_after(unsigned child,unsigned parent);
void scd_boss_slot_first(unsigned child);
unsigned scd_boss_retail_slot_peek(unsigned actor);
void scd_boss_slot_after_next(unsigned child,unsigned parent);
void scd_boss_slot_transient(void);
void scd_boss_slot_transient_end(void);
static int spawn_from(unsigned type,int x,int y,unsigned sub,unsigned flags,unsigned first);
#include "objects_cc_traps.inc"
/* ACTSET camera-window streaming for this zone's actors (scd_zone_ops). */
/* Palmtree Panic badniks (Objects/{Anton,Mosqui,Pata-Bata,Taga-Taga,Tamabboh}/
   Main.asm) load on the spawner's camera window (Object Spawner.asm) and frame
   out through CheckObjDespawn2 on their home X. */
static unsigned touch_owner; /* slot+1 that Player_ObjCollide reacts to this update */
static unsigned qq_ring_touched; /* QQ: slot+1 of the ring COLI5 pcol touched this update */
static unsigned ww_ring_touched; /* WW: slot+1 of the ring COLI6 pcol touched this update */
static int ppz_badnik(unsigned type){return objects_zone==0 && (type==34 || (type>=61 && type<=64));}
/* PPZ Objects/Platform/Main.asm frames out on its home X (oVar38) the same way. */
static int ppz_windowed(unsigned type){return ppz_badnik(type) || (objects_zone==0 && type==SCD_OBJ_PLATFORM);}
/* PPZ Player Object Collision.asm Player_ObjCollide: Sonic's box (X-8, 16 wide;
   Y-(Y radius-3), twice that tall; ducking frame $39: 12 lower, 20 tall) against
   ObjColSizes[colType & $3F] (Anton $29: 8x16, Pata-Bata $2A: 16x16, Mosqui $2B:
   12x12, Tamabboh $2C: 16x16 and its shot $2D: 4x4, Taga-Taga $2E: 16x16). */
static int ppz_touch_axis(int o,int r,int a,int span){int d=o-r-a;return d>=0?d<=span:d+2*r>=0;}
static int retail_touch(const sprite_status *p,int ox,int oy,int w,int h){
    int r=(uint8_t)p->sprvsize-3,top=p->yposi.w.h-r;
    if(p->patno==0x39){top+=12;r=10;}
    return ppz_touch_axis(ox,w,p->xposi.w.h-8,16) && ppz_touch_axis(oy,h,top,2*r);
}
static int ppz_touch(const sprite_status *p,const slot *s,int ox,int oy){
    int w=16,h=16;
    if(s->type==SCD_OBJ_ANTON)w=8;
    else if(s->type==SCD_OBJ_MOSQUI)w=h=12;
    else if(s->type==SCD_OBJ_TAMABBOH && s->subtype==1)w=h=4;
    return retail_touch(p,ox,oy,w,h);
}
/* Player_ObjCollide (Player Object Collision.asm, PPZ and WW copies alike)
   runs in Sonic's slot after his movement, scans the objects in slot order
   and returns after the first touched one, so only that object reacts this
   update. Touchable here: monitors ($46, 16x16, until broken), time posts
   ($DF, 4x24; one loaded already activated has no collision, Monitor and Time
   Post/Main.asm ObjTimePost_Init) and the PPZ badniks. Objects still hold
   their previous update's state. */
/* Object Functions.asm DrawObject marks an object onscreen (oSprFlags bit 7)
   when it is within oWidth of the 320-pixel view and oYRadius of the 224-line
   view; Player_ObjCollide skips objects without that bit. Once the time warp
   locks the camera (Sonic/Main.asm ObjSonic_TimeWarp scrollLock), Sonic leaves
   the view and the objects he passes are not touched; Object Solid.asm
   SolidObject gets him off an offscreen object too. */
static int draw_onscreen(const sprite_status *o){
    short camera_y=(short)scd_act_view_y(),x=(short)(o->xposi.w.h-scd_act_view_x()),y=o->yposi.w.h;
    if(x+o->sprhsize<0 || x-o->sprhsize>=320)return 0;
    if((unsigned short)camera_y<0x100){if((unsigned short)y>=0x800)y-=0x800;}
    else if((unsigned short)camera_y>=0x700 && (unsigned short)y<0x100)y+=0x800;
    y-=camera_y;
    return y+o->sprvsize>=0 && y-o->sprvsize<0xE0;
}
static void touch_arbitrate(void){
    touch_owner=0;
    const sprite_status *p=&actwk[0];
    if(p->r_no0>=4 || (p->actfree[2]&128))return;
    const int scroll_locked=scd_player_warp_saved();
    /* Outside Palmtree Panic only time posts take part: visit the slots that
       may hold one, in the same slot order. */
    const int ppz=objects_zone==0,ppz_rings=ppz && load_placements;
    for(unsigned i=0;i<SCD_OBJECT_CAPACITY;i++){
        if(!ppz){
            uint32_t m=timepost_mask[i/32]>>(i%32);
            if(!m){i|=31;continue;}
            while(!(m&1)){m>>=1;i++;}
        }
        const slot *s=&pool[i];int hit;
        if(!ppz && s->type!=SCD_OBJ_TIMEPOST){timepost_mask[i/32]&=~(1u<<(i%32));continue;}
        if(!s->type)continue;
        const sprite_status *o=&actwk[i+1];
        if(scroll_locked && !draw_onscreen(o))continue;
        /* WW: the collision scan skips an object the last draw left off
           screen (actflg bit 7, refreshed for zone-4 posts and monitors each
           update): retail WW1A row 7560 rises past the off-screen monitor at
           7712,656 that the port bounced Sonic off. */
        if(objects_zone==4 && !(o->actflg&128))continue;
        if(s->type==SCD_OBJ_TIMEPOST){
            /* MM posts take COLI8 pcol's slot-order scan (mm_enemy_scan). */
            if(s->subtype>=8){if(s->anim || objects_zone==6)continue;hit=retail_touch(p,o->xposi.w.h,o->yposi.w.h,4,24);}
            else{if(s->state==2)continue;hit=retail_touch(p,o->xposi.w.h,o->yposi.w.h,16,16);}
        }else if(ppz_rings && s->type==SCD_OBJ_RING){
            /* Ring/Main.asm colType $47: ObjColSizes 6x6 (PPZ copy). */
            if(s->state)continue;
            hit=retail_touch(p,o->xposi.w.h,o->yposi.w.h,6,6);
        }else if(ppz_badnik(s->type)){
            if(s->type==SCD_OBJ_TAGATAGA && s->state!=1)continue;
            hit=ppz_touch(p,s,o->xposi.w.h,o->yposi.w.h);
        }else continue;
        if(hit){touch_owner=i+1;return;}
    }
}
static int stream_windowed(unsigned type){return ppz_windowed(type) || (zone_ops && zone_ops->stream_windowed && zone_ops->stream_windowed(type));}
static int tt_chunk_prev,tt_spawn_ready;static unsigned tt_right,tt_left;
static uint8_t tt_ring_pending[SCD_OBJECT_CAPACITY]; /* tt_stream: ObjRing_Init still to run */
static void spawner_restart(void){tt_spawn_ready=0;memset(tt_ring_pending,0,sizeof(tt_ring_pending));memset(ring_loaded,0,sizeof(ring_loaded));}
void scd_objects_spawner_restart(void){spawner_restart();}
static void remove_slot(unsigned i) {
    tt_ring_pending[i]=0;
    if(pool[i].type==SCD_OBJ_AMY)amy_palette_active=0;
    if(pool[i].type==SCD_OBJ_MECASNC3 && !pool[i].subtype){emie_palette_active=0;emie3_ended=1;}
    if(pool[i].type==SCD_OBJ_MOVING_SPRING || cc_trap_parent(pool[i].type) || (pool[i].type==SCD_OBJ_GANDAIR3 && !pool[i].subtype) || ((pool[i].type==SCD_OBJ_PROJECTOR || pool[i].type==SCD_OBJ_MOVIE3) && !pool[i].subtype))for(unsigned child=0;child<SCD_OBJECT_CAPACITY;child++)if(pool[child].type && pool[child].parent==i+1)remove_slot(child);
    if(control_actor==i+1){actwk[0].actfree[2]&=~0xC1;control_actor=0;}
    if((pool[i].type==SCD_OBJ_PROJECTOR || pool[i].type==SCD_OBJ_MOVIE3 || pool[i].type==SCD_OBJ_DOOR_V || pool[i].type==SCD_OBJ_WALL || pool[i].type==SCD_OBJ_SPIKES || (pool[i].type>=SCD_OBJ_HARIR3 && pool[i].type<=SCD_OBJ_GANDAIR3) || (pool[i].type==SCD_OBJ_TIMEPOST && pool[i].subtype<8) || tp_type(pool[i].type) || scd_zone_local(pool[i].type)) && (actwk[i+1].cddat&32))actwk[0].cddat&=~32;
    if(pool[i].origin<SCD_PLACEMENT_CAPACITY && !consumed[pool[i].origin] && stream_windowed(pool[i].type))deferred_reload[pool[i].origin]=1;
    release_rider(i+1);
    memset(&pool[i],0,sizeof(pool[i]));memset(&actwk[i+1],0,sizeof(actwk[i+1]));stats.despawned++;
}
void scd_objects_clear_live(void) {
    memset(deferred_reload,0,sizeof(deferred_reload));
    for(unsigned i=0;i<SCD_OBJECT_CAPACITY;i++)if(pool[i].type)remove_slot(i);
}
void scd_objects_respawn(void){
    scd_objects_clear_live();memset(consumed,0,sizeof(consumed));memset(era_consumed,0,sizeof(era_consumed));tp_reset();
    /* LevelStart's $A00-byte flowerPosBuf clear takes the ring clocks with it. */
    global_anims_reset();
    /* The restart reloads the level, so SpawnObjects_Init runs again on the
       restart camera (Level/Object Spawner.asm), as scd_objects_reset does. */
    spawner_restart();
    ZONE_OPS_LOADED(2);if(zone_ops && zone_ops->reset)zone_ops->reset();
    pending_post=pending_generator=0;travel_protection=0;emyscorecnt=0;scd_boss_reset();big_ring_touched=big_ring_pending=0;
    tt_wave_spawn();
}
void scd_objects_reset(unsigned era,int enabled) {
    if(control_actor){actwk[0].actfree[2]&=~0xC1;control_actor=0;}
    if(actwk[0].cddat&8)release_rider(actwk[0].actfree[19]);
    amy_palette_active=emie_palette_active=emie3_ended=0;amy_idle_cursor=amy_idle_timer=0;amy_idle_pose=1;
    /* Level/Main.asm LevelStart: all seven time stones force goodFuture (no Time Attack here). */
    current_era=era&3;good_future=era==2 || time_stones==0x7f;projector_destroyed=0;travel_protection=0;pending_generator=0;pending_post=0;emyscorecnt=0;memset(era_consumed,0,sizeof(era_consumed));
    /* A loaded level starts a new Level/Main.asm V-INT count in every zone,
       including PPZ, whose stage has no imported object layout call. */
    level_vint=0;mm_spill_timer=mm_spill_rings=0;global_anims_reset();
    memset(deferred_reload,0,sizeof(deferred_reload));memset(pool,0,sizeof(pool));memset(consumed,0,sizeof(consumed));memset(&stats,0,sizeof(stats));scd_boss_reset();big_ring_touched=big_ring_pending=0;
    memset(actwk+1,0,sizeof(actwk[0])*SCD_OBJECT_CAPACITY);
    era_bit=1u<<(era==0?1:era==1?0:2);load_placements=enabled;tp_reset();
    tt_spawn_ready=0;memset(tt_ring_pending,0,sizeof(tt_ring_pending));memset(ring_loaded,0,sizeof(ring_loaded));
    ZONE_OPS_LOADED(3);if(zone_ops && zone_ops->reset)zone_ops->reset();
    tt_wave_spawn();
}
static int spawn_from(unsigned type,int x,int y,unsigned sub,unsigned flags,unsigned first) {
    ZONE_OPS_LOADED(4);
    if(!supported(type)){stats.unsupported++;return -1;}
    if((type==SCD_OBJ_AMY && (current_era!=0 || sub)) || (type==SCD_OBJ_AMY_HEART && sub))return -1;
    if((type==SCD_OBJ_ANIMAL || type==SCD_OBJ_FRIEND3) && (sub&127)>1)return -1;
    if((type==SCD_OBJ_PROJECTOR || type==SCD_OBJ_MOVIE3) && sub!=0 && sub!=1 && sub!=255)return -1;
    if(type==SCD_OBJ_SPIN_TAG && sub>4)return -1;
    if(type==SCD_OBJ_SCENERY && (current_era==0 || (current_era==1?sub>1:sub!=2)))return -1;
    if(type==SCD_OBJ_LOG_SHADOW && sub!=(current_era<2?0:1))return -1;
    /* Spin Tunnel/Main (Door).asm: subtypes 0-2 (2 is narrow; 0 also spawns the
       splash, not modelled). Retail R12A places a subtype 0 door at (6096,679). */
    if(type==SCD_OBJ_DOOR && sub>2)return -1;
    if((type==SCD_OBJ_DOOR_V || type==SCD_OBJ_MOVING_SPRING) && sub)return -1;
    if(type==SCD_OBJ_TUNNEL && (sub&127)>2)return -1;
    if(type==SCD_OBJ_WALL && sub>7)return -1;
    if(type==SCD_OBJ_FOR3 && sub>7)return -1;
    if((type==SCD_OBJ_HARIR3 || type==SCD_OBJ_TRAPDR3) && sub>7)return -1;
    if(type==SCD_OBJ_FRDR3 && sub>3)return -1;
    if(type==SCD_OBJ_GETDAIR3 && (sub&15)>2)return -1;
    if(type==SCD_OBJ_GANDAIR3 && sub>2)return -1;
    if(type==SCD_OBJ_DRUMR3 && sub>17)return -1;
    if(type==SCD_OBJ_HARI3X && sub>3)return -1;
    if(type==SCD_OBJ_EMIE3 && sub!=0 && sub!=128)return -1;
    if(type==SCD_OBJ_MECASNC3 && sub>1)return -1;
    if(walls_reject(type,sub))return -1;
    if(scd_zone_local(type) && zone_ops->reject && zone_ops->reject(type,sub))return -1;
    /* UDBLK4/LRBLK4/TOBIRA4 index tables by subtype; TOBIRAS4 indexes switchflag[32]. */
    if((type==SCD_OBJ_UDBLK4 && sub>11) || (type==SCD_OBJ_LRBLK4 && sub>8) || (type==SCD_OBJ_TOBIRA4 && (sub>>4)>4) || (type==SCD_OBJ_TOBIRAS4 && sub>31))return -1;
    unsigned collapse_era=current_era>1?2:current_era;
    if(type==SCD_OBJ_COLLAPSE && ((sub&15)>=COLLAPSE_COUNT(collapse_era,!!(sub&128)) || ((sub&128) && (sub&16))))return -1;
    if((type==SCD_OBJ_TIMEPOST && sub>9) || (type==SCD_OBJ_MONITOR_ITEM && sub>7))return -1;
    if(type==SCD_OBJ_PLATFORM && ((sub&3)>2 || sub>>4>6))return -1;
    /* Streamed PPZ badniks spawn and run DestroyOnGoodFuture (enemy_step). */
    if(enemy(type) && !(objects_zone==0 && load_placements) && (current_era==2 || (good_future && (current_era!=0 || sub))))return -1;
    if(x<0 || x>=16384 || y<0 || y>=2048 || sub>255 || flags>3)return -1;
    for(unsigned i=first;i<SCD_OBJECT_CAPACITY;i++)if(pool_slot_free(i)) {
        pool[i]=(slot){.origin=65535,.type=type,.subtype=sub,.flags=flags};
        pool_typed(i,type);
        sprite_status *o=&actwk[i+1];memset(o,0,sizeof(*o));
        o->actno=type;o->xposi.l=x*65536;o->yposi.l=y*65536;o->actflg=128|4|flags;o->cddat=flags;
        o->sprhsize=16;o->sprvsize=16;o->userflag.b.h=sub;
        if(type==SCD_OBJ_SPRING) {
            o->sprvsize=8;
            if(sub&4){o->sprhsize=8;o->sprvsize=16;}
            else if(sub&8){o->sprhsize=24;o->sprvsize=12;}
            scd_word_set(o,26,(sub&2)?-2560:-4096);
        }
        slot *s=&pool[i];s->home_x=x;s->home_y=y;
        /* No initializer below applies to a ring, and the ring-loss scatter
           spawns twenty of them in one update. Leave before the type chain. */
        if(type==SCD_OBJ_RING || type==SCD_OBJ_LOST_RING){
            o->sprhsize=o->sprvsize=8;
            /* WW ObjRing_Init starts with oSprFlags=4. DrawObject sets bit 7
               only after the ring's update, for the next pcol scan. */
            if(type==SCD_OBJ_RING && (objects_zone==4 || objects_zone==6))o->actflg&=~128;
            /* A lost ring lives on the spill timer its flyringinit sets. */
            if(type==SCD_OBJ_LOST_RING)mm_spill_timer=255;
            stats.spawned++;return i;
        }
        if(type==SCD_OBJ_COLLAPSE){
            const scd_collapse_shape *shape=COLLAPSE_SHAPE(collapse_era,!!(sub&128),sub&15);
            o->sprhsize=(shape->columns+1)*8;o->sprvsize=(magnitude(shape->rows)+1)*8+2;
            s->frame=COLLAPSE_BASE(collapse_era,!!(sub&128))+(sub&15);
            if(sub&16){s->flags|=1;o->cddat|=1;}
#ifndef SCD_COLLAPSE_FULL_SCAN
            /* No later initializer applies to a collapse piece (type 32). */
            stats.spawned++;return i;
#endif
        }
        if(type==SCD_OBJ_SWING){o->sprhsize=24;o->sprvsize=8;}
        /* ObjSpringBoard_Init: a subtype or X flip selects the flipped routine and animation. */
        if(type==SCD_OBJ_SPRINGBOARD){o->sprhsize=16;o->sprhs=24;o->sprvsize=4;s->state=(sub || (flags&1))?4:2;s->phase=(sub || (flags&1))?4:3;o->actflg&=~1;o->cddat&=~1;s->flags&=~1;s->timer=0;}
        if(type==SCD_OBJ_AMY){o->sprhsize=12;o->sprvsize=16;}
        /* ObjCapsule_Init: width $20, height $18. Seeds and flowers start with Y radius 0. */
        if(type==SCD_OBJ_CAPSULE){o->sprhsize=32;o->sprvsize=24;s->state=2;}
        if(type==SCD_OBJ_FLOWER)o->sprvsize=0;
        /* ObjBigRing_Init: width and height $20. */
        if(type==SCD_OBJ_BIG_RING)o->sprhsize=o->sprvsize=32;
        if(type==SCD_OBJ_ANIMAL || type==SCD_OBJ_FRIEND3)o->sprhsize=o->sprvsize=8;
        if(type==SCD_OBJ_PROJECTOR || type==SCD_OBJ_MOVIE3){o->sprhsize=sub?(sub&128?8:20):12;o->sprvsize=sub?(sub&128?4:24):12;}
        if(type==SCD_OBJ_SCENERY){o->sprvsize=24;s->frame=sub;}
        if(type==SCD_OBJ_LOG_SHADOW)s->frame=sub;
        if(type==SCD_OBJ_DOOR){o->sprhsize=sub==2?24:44;o->sprvsize=8;}
        if(type==SCD_OBJ_DOOR_V){o->sprhsize=4;o->sprvsize=24;}
        if(type==SCD_OBJ_MOVING_SPRING){o->sprhsize=8;o->sprvsize=7;o->xspeed.w=384;}
        if(type==SCD_OBJ_DISC)o->sprvsize=8;
        if(type==SCD_OBJ_WALL){o->sprhsize=16;o->sprvsize=24;s->frame=sub;}
        if(type==SCD_OBJ_KONBEA && zone_ops && zone_ops->konbea)zone_ops->konbea(i,1);
        if(type==SCD_OBJ_SPIKES){o->sprhsize=flags&2?18:16;o->sprvsize=8;}
        /* R4 placement actors start as the loader leaves them: actflg holds only the flip bits. */
        if(tp_type(type)){o->actflg=flags;o->sprhsize=o->sprvsize=0;}
        /* So do the other R4 actors: a Present FRIEND4 never runs its init (SUICIDE.C
           friend_suicide frames it out first), and a stale on-screen bit kept the
           native one alive (retail TT2A drops the friend at 2448,1864 before row 9286). */
        else if(objects_zone==2 && type>=SCD_OBJ_R4_FIRST && type<=SCD_OBJ_R4_LAST)o->actflg=flags;
        if(type==SCD_OBJ_GANDAIR3 || type==SCD_OBJ_KAMA_BLADE || type==SCD_OBJ_POCKET || type==SCD_OBJ_CC_POINTS)o->sprhsize=o->sprvsize=0;
        if(type==SCD_OBJ_EMIE3)o->sprhsize=o->sprvsize=0;
        if(type==SCD_OBJ_MECASNC3)o->sprhsize=o->sprvsize=0;
        if(type==SCD_OBJ_CHECKPOINT){o->sprhsize=8;o->sprvsize=24;s->state=scd_player_checkpoint().id>=sub?2:0;}
        if(type==SCD_OBJ_PLATFORM){static const uint8_t widths[]={16,32,48};o->sprhsize=widths[sub&3];o->sprvsize=8;s->frame=sub&3;}
        if(type==SCD_OBJ_FLOAT_BLOCK){o->sprhsize=o->sprvsize=12;s->frame=era_bit==2?0:5;}
        if(type==SCD_OBJ_RAMP){o->sprhsize=o->sprvsize=32;if(sub&1)s->flags|=1;}
        if(type==SCD_OBJ_RAMP_PLANT)s->frame=sub>=4;
        if(type==SCD_OBJ_GENERATOR){o->sprhsize=34;o->sprvsize=32;s->frame=(good_future?0:2)+(current_era==1);if(current_era==1 && !good_future)o->yposi.w.h-=16;}
        /* Monitor and Time Post/Main.asm:113: monitor oWidth $F (SolidObject width 25). */
        if(type==SCD_OBJ_TIMEPOST){o->sprvsize=sub<8?14:32;o->sprhsize=sub<8?15:14;s->frame=sub<8?0:sub==9?2:0;} /* a monitor's oMapFrame starts 0 until its first animated update */
        if(type==SCD_OBJ_MONITOR_ITEM){s->frame=sub;o->yspeed.w=-768;}
        if(type==SCD_OBJ_DAIR5)s->frame=dair5_spawn(o);
        if(enemy(type)) {
            o->xspeed.w=-(sub?128:256);
            if(type==SCD_OBJ_ANTON){o->sprhsize=24;o->sprvsize=19;}
            if(type==SCD_OBJ_PATABATA)o->xspeed.w=-(sub?64:128);
            if(type==SCD_OBJ_TAMABBOH){o->sprvsize=15;o->xspeed.w=-(sub?80:160);}
            if(type==SCD_OBJ_TAGATAGA){o->sprvsize=22;s->timer=90;s->frame=6+(sub?7:0);}
            if(type==SCD_OBJ_TAMABBOH && sub==1){o->sprhsize=o->sprvsize=8;o->xspeed.w=flags&1?-512:512;o->yspeed.w=-1024;s->state=1;}
        }
        if(scd_zone_local(type) && zone_ops->init)zone_ops->init(i);
        stats.spawned++;return i;
    }
    stats.dropped++;return -1;
}
int scd_objects_spawn(unsigned type,int x,int y,unsigned sub,unsigned flags) {
    return spawn_from(type,x,y,sub,flags,0);
}
/* Ani_Explosion: subtype 0 plays animation 0 (frames 0,5,6,3,4: the fire the
   bosses' actno 24 explosions show); native explosions otherwise play animation 1. */
void scd_objects_explosion_fire(int slot_index){if(slot_index>=0)pool[slot_index].state=1;}
/* spawn_from for the ring-loss scatter: the same lowest free slot at or after
   FIRST and the same slot/actor fields as spawn_from's ring branch, without
   its per-type validation chain (a lost ring passes every check). */
static int spawn_lost_ring(int x,int y,unsigned first){
    if(x<0 || x>=16384 || y<0 || y>=2048)return -1;
    for(unsigned i=first;i<SCD_OBJECT_CAPACITY;i++)if(pool_slot_free(i)){
        slot *s=&pool[i];memset(s,0,sizeof(*s));
        s->origin=65535;s->type=SCD_OBJ_LOST_RING;s->home_x=x;s->home_y=y;
        sprite_status *o=&actwk[i+1];memset(o,0,sizeof(*o));
        o->actno=SCD_OBJ_LOST_RING;o->xposi.l=x*65536;o->yposi.l=y*65536;o->actflg=128|4;
        o->sprhsize=o->sprvsize=8;
        /* COLI8.C:531-540 / RING.C:406,416-417: an MM lost ring carries the
           layer it was spilt on (prio_flag) and starts off screen until drawn. */
        if(objects_zone==6){o->userflag.b.l=prio_flag?1:0;o->actflg=4;}
        stats.spawned++;return (int)i;
    }
    stats.dropped++;return -1;
}
/* Original two mirrored rings per angle, 16 angles across two speeds:
   ring N of a spill (sinset for the eight scatter angles, read once). */
static void lost_ring_velocity(sprite_status *r,unsigned n){
    static short scatter_sin[8],scatter_cos[8];static uint8_t scatter_ready;
    if(!scatter_ready){for(unsigned a=0;a<8;a++)sinset(136+a*16,&scatter_sin[a],&scatter_cos[a]);scatter_ready=1;}
    short s=scatter_sin[n/2%8],c=scatter_cos[n/2%8];int scale=n<16?4:2;
    r->xspeed.w=s*scale*(n&1?-1:1);r->yspeed.w=c*scale;
}
void scd_objects_death_record(void){stats.deaths++;scd_objects_release_control();}
void scd_objects_hurt(int source_x) {
    sprite_status *p=&actwk[0],source={0};source.xposi.w.h=source_x;
    if((p->actfree[2]&128) || p->r_no0>=4 || scd_word_get(p,26) || plpower_m || travel_protection)return;
    stats.hits++;
    if(control_actor && pool[control_actor-1].type==SCD_OBJ_AMY)scd_objects_release_control();
    if(!plpower_b && !plring){playdieset(p);stats.deaths++;return;}
    unsigned rings=plpower_b?0:(unsigned)plring;
    /* Player Object Collision.asm HurtPlayer copies oX/oY into the lost-ring actor
       before Player_ResetOnFloor lifts a rolling player 5 pixels (playdamagechk). */
    int ring_x=p->xposi.w.h,ring_y=p->yposi.w.h;
    playdamagechk(p,&source);
    if(rings) {
        /* Original shield loss does not create the lost-ring actor that
           requests this sound. Keep it tied to actual ring loss. */
        soundset(148);
        plring=0;scd_player_rings_lost();
        /* Original two mirrored rings per angle, 16 angles across two speeds. */
        /* Nothing frees slots inside this batch. The next lowest free slot
           must be after the one just allocated; do not rescan its occupied
           prefix up to 32 times. Keep ordinary spawning and slot order intact. */
        unsigned first=0;scd_profile_span(1,1);
        /* MM (COLI8.C:531-545, RING.C:384-447): HurtPlayer leaves one ring
           actor (actwkchk); its flyringinit, when RunObjects reaches it, sets
           the spill timer and takes the others with actwkchk then, so they can
           reuse slots that frame out earlier in that object pass (retail MM2D
           row 2758: rings in 49 and 50, freed by a shooter and a kabuto after
           Sonic's touch). lost_ring_step spawns them (mm_spill_rings). */
        if(objects_zone==6){mm_spill_rings=(uint8_t)(rings<32?rings:32);rings=1;}
        else mm_spill_timer=255; /* Ring/Main.asm:376 ObjLostRing_Init */
        for(unsigned n=0;n<rings && n<32;n++) {
            int index=spawn_lost_ring(ring_x,ring_y,first);
            if(index<0)break;
            first=(unsigned)index+1;
            lost_ring_velocity(&actwk[index+1],n);stats.lost++;
            if(objects_zone==6)pool[index].phase=2;
        }
        scd_profile_span(1,0);
    }
}
/* Tidal Tempest placements stream as retail ACTSET does (scddisasm
   Level/Object Spawner.asm, the same spawner in R4*__.MMD $770C): the layout is
   in retail record order (x-sorted, tools/object_layouts.py); the spawner runs
   only when the camera's 128 px chunk changes, walking a right pointer forward
   (spawn below chunk+$280) or a left pointer back (spawn above chunk-$80); a
   record with a saved-flags entry (placement flags bit 5) spawns only while its
   flag is clear (alive and destroyed objects keep it). Each placed object frames
   itself out during the object loop (FRAMEOUT_S, ObjRing_Main) instead of a
   player-distance sweep before spawning, so slot reuse follows retail order.
   Ring-group members (flags bit 4) are spawned by their first ring's init
   (Ring/Main.asm ObjRing_Init, FindNextObjSlot after it). Collision Chaos
   uses the same spawner (Level/Object Spawner.asm is shared by every round). */
enum {TT_SAVED=32,TT_RING_MEMBER=16};
/* PPZ ring records' saved-flags bit 7 (Ring/Main.asm): SpawnObject sets it;
   ObjRing_Init clears it again while any ring of the group is uncollected, so
   a group whose rings are all collected still loads once more, and that
   parent deletes itself in its init (ChkDel). */
static uint8_t ring_loaded[SCD_PLACEMENT_CAPACITY];
/* Object Spawner.asm (SpawnObjects, x-sorted layout walk, camera-chunk
   window; shared by every round) for Palmtree Panic, Collision Chaos, Tidal
   Tempest, Quartz Quadrant, Wacky Workbench, Stardust Speedway and Metallic Madness. */
static int tt_streamed(void){return objects_zone<=6 && load_placements;}
/* Live layout records, built once per tt_stream call (a chunk crossing tests
   every record in the new column) and kept current by tt_spawn_record. */
static uint32_t tt_alive_bits[SCD_PLACEMENT_CAPACITY/32];static int tt_alive_valid,tt_streaming;
static int tt_alive(unsigned j){
    if(!tt_streaming){for(unsigned i=0;i<SCD_OBJECT_CAPACITY;i++)if(pool[i].type && pool[i].origin==j)return 1;return 0;}
    if(!tt_alive_valid){
        memset(tt_alive_bits,0,sizeof(tt_alive_bits));tt_alive_valid=1;
        for(unsigned i=0;i<SCD_OBJECT_CAPACITY;i++)if(pool[i].type && pool[i].origin<SCD_PLACEMENT_CAPACITY)tt_alive_bits[pool[i].origin/32]|=1u<<(pool[i].origin%32);
    }
    return j<SCD_PLACEMENT_CAPACITY && (tt_alive_bits[j/32]>>(j%32)&1);
}
/* Time Attack (IPX.asm timeAttackMode, src/time_attack.h): retail deletes time posts
   (Monitor and Time Post/Main.asm:65 ObjTimePostTimeIcon), despawns 1UP monitors
   (:272, subtype 0) and Amy leaves at once (Amy Rose/Main.asm:8); those placements
   do not load. */
static int ta_absent(unsigned type,unsigned sub){
    return scd_ta.mode && ((type==SCD_OBJ_TIMEPOST && (!sub || sub>=8)) || type==SCD_OBJ_AMY || type==SCD_OBJ_AMY_HEART);
}
static void tt_alive_add(unsigned j){if(tt_alive_valid && j<SCD_PLACEMENT_CAPACITY)tt_alive_bits[j/32]|=1u<<(j%32);}
/* Return the located slot plus one so the spawn does not scan its occupied prefix again. */
/* Within one tt_stream call slots only fill, so the search resumes at the last
   free slot found (tt_stream resets the hint; a boss record resets it too). */
static unsigned tt_free_hint;
static int tt_free_slot(void){
    for(unsigned i=tt_streaming?tt_free_hint:0;i<SCD_OBJECT_CAPACITY;i++)if(pool_slot_free(i)){if(tt_streaming)tt_free_hint=i;return (int)i+1;}
    if(tt_streaming)tt_free_hint=SCD_OBJECT_CAPACITY;
    return 0;
}
/* SpawnObject: 0 spawned or skipped (wrong era, flag set), -1 no free slot. */
static int tt_spawn_record(unsigned j){
    const scd_placement *e=&active_placements[j];
    if(e->flags&TT_RING_MEMBER)return 0;
    if(!(e->eras&era_bit))return 0;
    if(ta_absent(e->type,e->subtype))return 0;
    /* ACTSET loads a noact record into the lowest free slot and noact frees
       it at once (ACT81A.C:171 frameout): later loads of the same pass skip
       that slot (retail MM1A 3335). */
    if(objects_zone==6 && e->type==SCD_OBJ_R8_NOACT){scd_boss_slot_transient();tt_free_hint=0;return 0;}
    if(objects_zone==0 && e->type==SCD_OBJ_RING && (e->flags&TT_SAVED)){
        if(ring_loaded[j])return 0;
        int free_slot=tt_free_slot();if(!free_slot)return -1;
        int index=spawn_from(e->type,e->x,e->y,e->subtype,e->flags&3,(unsigned)(free_slot-1));
        if(index<0)return 0;
        ring_loaded[j]=1;pool[index].origin=j;tt_alive_add(j);tt_ring_pending[index]=1;
        return 0;
    }
    /* A broken monitor or a used time post reloads in that state (ITEM.C
       itemget sets flagwork bit 0, item init reads it): retail TT2A row 3885
       respawns both at slots 81-82. A revealed Sonic hole reloads revealed: its
       flagwork bit 6 persists, and frameout clears the spawned bit. */
    /* ObjRing_Init loads every uncollected ring of a group even when its first
       ring was taken (the head then deletes itself, tt_ring_group): retail
       QQ2A row 7554 has members 7048/7072/7096,936 back in slots 55/56/64
       after the head at 7024 was collected and the group framed out. */
    int ring_rest=e->type==SCD_OBJ_RING && consumed[j] && !tt_alive(j);
    for(unsigned k=j+1;ring_rest && k<active_placement_count && (active_placements[k].flags&TT_RING_MEMBER);k++)
        if(tt_alive(k)){ring_rest=0;break;}
    if(ring_rest){
        ring_rest=0;
        for(unsigned k=j+1;k<active_placement_count && (active_placements[k].flags&TT_RING_MEMBER);k++)
            if(!consumed[k] && (active_placements[k].eras&era_bit)){ring_rest=1;break;}
    }
    if(!ring_rest && (e->flags&TT_SAVED) && ((consumed[j] && e->type!=SCD_OBJ_TIMEPOST && e->type!=SCD_OBJ_SONIC_HOLE) || tt_alive(j))){
        /* A taken ring group is still spawned and deletes itself in ObjRing_Init
           (retail QQ3C row 1557: its slot 41 pushed the next group's head to 43). */
        if(e->type==SCD_OBJ_RING && consumed[j] && !tt_alive(j)){
            /* MM: RING.C ringinit deletes a fully taken group head with plain
               frameout (ACTION.C:187), which keeps its flagwork bit 7 set, so
               ACTSET actnoset never loads the record again (retail MM2D row
               7485: no reload of the head at 7056,1395; the next group's member
               takes slot 47). consumed bit 1 marks that first load. */
            if(objects_zone==6){if(consumed[j]&2)return 0;consumed[j]|=2;}
            scd_boss_slot_transient();tt_free_hint=0; /* the sync can release a boss reservation */
        }
        return 0;
    }
    if(e->type==SCD_OBJ_R6_EGG6DOOR || e->type==SCD_OBJ_BOSS)tt_free_hint=0;
    if(e->type==SCD_OBJ_R6_EGG6DOOR && objects_zone==4){if(!consumed[j]){consumed[j]=1;scd_boss6_door(e->x,e->y,e->subtype,e->secondary);}return 0;}
    if(e->type==SCD_OBJ_BOSS){if(!consumed[j]){consumed[j]=1;scd_boss_create_sub(e->x,e->y,e->subtype,objects_round());}return 0;}
    /* PPZ animals in a Future without the Good Future spawn and delete
       themselves on their first update (animal_step). */
    if((e->type==SCD_OBJ_PROJECTOR && projector_destroyed) || (e->type==SCD_OBJ_ANIMAL && !(e->subtype&128) && current_era>=2 && !good_future && objects_zone!=0))return 0;
    if(!ring_rest && !(e->flags&TT_SAVED) && consumed[j] && e->type!=SCD_OBJ_TIMEPOST && e->type!=SCD_OBJ_SONIC_HOLE)return 0;
    int free_slot=tt_free_slot();if(!free_slot)return -1;
    int index=spawn_from(e->type,e->x,e->y,e->subtype,e->flags&3,(unsigned)(free_slot-1));
    if(index<0)return 0;
    pool[index].origin=j;tt_alive_add(j);actwk[index+1].userflag.b.l=e->secondary;
    if(consumed[j] && e->type==SCD_OBJ_TIMEPOST){pool[index].state=2;pool[index].anim=1;pool[index].frame=e->subtype<8?11:(e->subtype==9?3:1);}
    if(consumed[j] && e->type==SCD_OBJ_SONIC_HOLE)pool[index].state=1;
    if(e->type==SCD_OBJ_RING || e->type==SCD_OBJ_RAMP_PLANT)tt_ring_pending[index]=1;
    return 0;
}
/* ObjRing_Init: the group's other rings go to the free slots after the first. */
static int tt_ring_group(unsigned i){
    tt_ring_pending[i]=0;unsigned j=pool[i].origin;
    int ppz_ring=objects_zone==0 && pool[i].type==SCD_OBJ_RING && j<SCD_PLACEMENT_CAPACITY;
    if(ppz_ring){
        int any=!consumed[j];
        for(unsigned k=j+1;k<active_placement_count && (active_placements[k].flags&TT_RING_MEMBER);k++)
            if(!consumed[k] && (active_placements[k].eras&era_bit))any=1;
        if(any)ring_loaded[j]=0;
    }
    /* One slot-model sync per group: spawn_from only adds the member. */
    int synced=0;unsigned first=i+1;
    for(unsigned k=j+1;k<active_placement_count && (active_placements[k].flags&TT_RING_MEMBER);k++){
        const scd_placement *e=&active_placements[k];
        if(consumed[k] || !(e->eras&era_bit))continue;
        int index=spawn_from(e->type,e->x,e->y,e->subtype,e->flags&3,first);
        if(index<0)break;
        pool[index].origin=k;
        if(synced){scd_boss_slot_after_next(index+1,i+1);first=(unsigned)index+1;}
        else{
            scd_boss_slot_after(index+1,i+1);synced=1;
            /* The first sync can release a dead borrowed slot below this member.
               Later members only add actors and adjust virtual slot mappings. */
            first=i+1;
        }
    }
    /* ChkDel: a parent whose own (first) ring was collected deletes itself. */
    if((ppz_ring || pool[i].type==SCD_OBJ_RING) && j<SCD_PLACEMENT_CAPACITY && consumed[j]){remove_slot(i);return 1;}
    return 0;
}
static unsigned tt_ring_home(unsigned j){while(j && (active_placements[j].flags&TT_RING_MEMBER))j--;return j;}
/* Ring-group members are not layout records: the walks use the first ring. */
static int tt_member(unsigned j){return (active_placements[j].flags&TT_RING_MEMBER)!=0;}
static unsigned tt_group_start(unsigned j){while(j && tt_member(j))j--;return j;}
static void tt_stream_body(void){
    short chunk=(short)(scd_act_view_x()&-128);
    if(!tt_spawn_ready){
        /* SpawnObjects_Init */
        tt_spawn_ready=1;short d6=(short)scd_act_view_x()-128;if(d6<0)d6=0;d6&=-128;
        tt_right=0;while(tt_right<active_placement_count && (tt_member(tt_right) || (unsigned short)active_placements[tt_right].x<(unsigned short)d6))tt_right++;
        tt_left=0;d6-=128;
        if(d6>=0)while(tt_left<active_placement_count && (tt_member(tt_left) || (unsigned short)active_placements[tt_left].x<(unsigned short)d6))tt_left++;
        tt_chunk_prev=-1;
    }
    if(chunk==tt_chunk_prev)return;
    if(chunk>tt_chunk_prev){
        tt_chunk_prev=chunk;short limit=(short)(chunk+640);
        while(tt_right<active_placement_count){
            if(tt_member(tt_right)){tt_right++;continue;}
            if((unsigned short)active_placements[tt_right].x>=(unsigned short)limit)break;
            if(tt_spawn_record(tt_right)<0)break;
            tt_right++;
        }
        short d6=(short)(chunk-128);
        if(d6>=0)while(tt_left<active_placement_count && (tt_member(tt_left) || (unsigned short)active_placements[tt_left].x<(unsigned short)d6))tt_left++;
    }else{
        tt_chunk_prev=chunk;short d6=(short)(chunk-128);
        if(d6>=0)while(tt_left>0){
            unsigned k=tt_group_start(tt_left-1);
            if(active_placements[k].x<=d6)break;
            if(tt_spawn_record(k)<0)break;
            tt_left=k;
        }
        d6=(short)(chunk+640);
        while(tt_right>0){
            unsigned k=tt_group_start(tt_right-1);
            if(active_placements[k].x<d6)break;
            tt_right=k;
        }
    }
}
/* The alive bitset and free-slot hint hold only inside one call. */
static void tt_stream(void){
    tt_alive_valid=0;tt_free_hint=0;tt_streaming=1;
    tt_stream_body();
    tt_streaming=0;tt_alive_valid=0;tt_free_hint=0;
}
/* FRAMEOUT_S / ObjRing_Main for the common placed types (the TT ports frame
   themselves out): the column of X (rings: the group's first ring) leaves
   [chunk(camera-128), +640]. */
static int tt_frameout_common(unsigned i){
    slot *s=&pool[i];
    /* SPRING.C:415-419: a spring linked to its Quartz Quadrant platform
       (DAI_RD5.C banesetsub, word 28) frames itself out by its init X
       (word 29, SPRING.C:437); retail QQ3C row 638 drops it with the platform. */
    if(objects_zone==3 && s->type==SCD_OBJ_SPRING && s->origin==65535 && scd_word_get(&actwk[i+1],28)){
        short h=(short)((scd_act_view_x()-128)&-128);
        if((unsigned short)(short)((s->home_x&-128)-h)<=640)return 0;
        remove_slot(i);return 1;
    }
    /* A badnik converted in place keeps its record, but PLAYSUB bakuha and the
       flower it becomes never frame out (retail QQ1B slot 47: the flower from a
       denden killed at X 635 stays through row 1230, Sonic at X 2851). R4
       PLAYSUB4.C bakuha/flower call only actionsub (retail TT2A slot 73: the
       flower at X 1872 stays through row 6685, camera X 2613). */
    if((objects_zone==2 || objects_zone==3 || (objects_zone==4 && objects_act==0) || objects_zone==5 || objects_zone==6) &&
       (s->type==SCD_OBJ_EXPLOSION || s->type==SCD_OBJ_FLOWER) && s->phase)return 0;
    /* MM: GOAL.C:754 goal (the sign post) never frames out: retail R82D
       $20B040 ends in jmp actionsub (retail MM2D keeps it in slot 42 from
       row 6280 while the camera window leaves it at row 7167). */
    if(objects_zone==6 && s->type==SCD_OBJ_SIGN)return 0;
    if(s->origin>=SCD_PLACEMENT_CAPACITY || tp_type(s->type) || scd_zone_local(s->type) || (objects_zone==3 && s->type==SCD_OBJ_DAIR5))return 0;
    /* R4 actors that call frameout_s themselves (TONBO.C, YAGO.C, ... through
       tt_frameout, often on a home X) have no second, generic test: retail
       TT2A keeps the tonbo homed at 2664 while its X is 2786 and the camera
       window's left column is 1920 (R42A slot 65, row 7498). */
    if(objects_zone==2){
        switch(s->type){
        case SCD_OBJ_TONBO:case SCD_OBJ_YAGO:case SCD_OBJ_AMENBO:case SCD_OBJ_TAGAMEB:case SCD_OBJ_HARIR4:case SCD_OBJ_HARID4:
        case SCD_OBJ_SCREW:case SCD_OBJ_OSUMIZU:case SCD_OBJ_FUNSUI4:case SCD_OBJ_UKIDAI:case SCD_OBJ_BOU:
        case SCD_OBJ_FRIEND4:case SCD_OBJ_MOVIE4:case SCD_OBJ_ET4:return 0;
        default:break;
        }
    }
    if(s->type==SCD_OBJ_RING && s->state)return 0;
    /* A hit projector finishes its destruction off screen (the player-distance
       stream exempted it too), so the Good Future release always lands. */
    if(s->type==SCD_OBJ_PROJECTOR && s->state>=2)return 0;
    /* ObjTunnelPath (Tunnel Path/Main.asm) calls CheckObjDespawn only in
       routines below 4 and not while the player is dead or in anim $2B: a
       tunnel carrying the player never frames out. */
    if(s->type==SCD_OBJ_TUNNEL && (s->state || actwk[0].r_no0>=6 || actwk[0].mstno.b.h==43))return 0;
    /* 3D Ramp/Main.asm Obj3DPlant: every piece frames out on oVar2A, the
       layout record's X (the first piece sits 64 to its right). */
    int x=s->type==SCD_OBJ_RING?active_placements[tt_ring_home(s->origin)].x:
          s->type==SCD_OBJ_RAMP_PLANT?active_placements[tt_ring_home(s->origin)].x-64:
          (s->type==SCD_OBJ_SWING || s->type==SCD_OBJ_MOVING_SPRING || (s->type==SCD_OBJ_ANIMAL && !(s->subtype&127)) || ppz_windowed(s->type))?s->home_x:
          /* KONBEA.C:637/819 frameout_s00 on the home X, word 25 (a) or 24
             (b): retail MM1A keeps the moving conveyor at slot 37 (X 4900)
             until camera 5251 (row 4833). Before its init the words are unset. */
          (objects_zone==6 && s->type==SCD_OBJ_KONBEA && actwk[i+1].r_no0)?(int16_t)scd_word_get(&actwk[i+1],(uint8_t)actwk[i+1].userflag.b.h?24:25):actwk[i+1].xposi.w.h;
    short h=(short)((scd_act_view_x()-128)&-128);
    if((unsigned short)(short)((x&-128)-h)<=640)return 0;
    remove_slot(i);return 1;
}
/* Per-update fast path: a native actor (no layout record) frames out here
   only as a Quartz Quadrant platform spring. */
static inline __attribute__((always_inline)) int tt_frameout_fast(unsigned i){
    const slot *s=&pool[i];
    if(s->origin>=SCD_PLACEMENT_CAPACITY && !(objects_zone==3 && s->type==SCD_OBJ_SPRING))return 0;
    return tt_frameout_common(i);
}
static void stream(int x) {
    if(tt_streamed()){tt_stream();return;}
    for(unsigned i=0;i<SCD_OBJECT_CAPACITY;i++)if(pool[i].type && pool[i].origin!=65535 && ppz_windowed(pool[i].type)){
        /* CheckObjDespawn2: the home X chunk leaves [chunk(camera-128), +640]. */
        short h=(short)((scd_act_view_x()-128)&-128);
        if((unsigned short)(short)((pool[i].home_x&-128)-h)>640)remove_slot(i);
    }else if(pool[i].type && pool[i].origin!=65535 && pool[i].type!=SCD_OBJ_TOGEBALL && pool[i].type!=SCD_OBJ_POCKET && pool[i].type!=SCD_OBJ_CC_GENERATOR && !(pool[i].type==SCD_OBJ_PROJECTOR && pool[i].state>=2) && !(pool[i].type==SCD_OBJ_TUNNEL && pool[i].state) && magnitude(((pool[i].type==SCD_OBJ_SWING || pool[i].type==SCD_OBJ_MOVING_SPRING || (pool[i].type==SCD_OBJ_ANIMAL && !(pool[i].subtype&127)))?pool[i].home_x:actwk[i+1].xposi.w.h)-x)>640)remove_slot(i);
    if(!load_placements)return;
    /* Snapshot placement ownership after all removals, including recursive
       child removal. The spawn loop only adds native slots; boss creation
       uses its separate PC actor range. Avoid rescanning every occupied slot
       for each nearby placement, especially on the first arrival update. */
    uint32_t live[(SCD_PLACEMENT_CAPACITY+31)/32]={0};
    for(unsigned i=0;i<SCD_OBJECT_CAPACITY;i++)if(pool[i].type && pool[i].origin<SCD_PLACEMENT_CAPACITY)
        live[pool[i].origin/32]|=1u<<(pool[i].origin%32);
    unsigned first=0;
    for(unsigned j=0;j<active_placement_count;j++) {
        const scd_placement *e=&active_placements[j];
        int distance=magnitude(e->x-x);
        /* The boss parent (egg1; Collision Chaos egg3dai_l/egg3dai_s by subtype)
           spawns once into the PC actor slots (src/boss.c). */
        /* BOSS_6.C egg6door reads both userflag bytes (kind, floor beam bit). */
        if(e->type==SCD_OBJ_R6_EGG6DOOR && objects_zone==4){if(!consumed[j] && (e->eras&era_bit) && distance<=480){consumed[j]=1;scd_boss6_door(e->x,e->y,e->subtype,e->secondary);}continue;}
        if(e->type==SCD_OBJ_BOSS){if(!consumed[j] && (e->eras&era_bit) && distance<=480){consumed[j]=1;scd_boss_create_sub(e->x,e->y,e->subtype,objects_round());}continue;}
        if(distance>640){deferred_reload[j]=0;continue;}
        /* Windowed actors: leaving the window re-arms the placement (checked
           before the deferred flag, or a removed actor never reloads). */
        if(stream_windowed(e->type)){
            short h=(short)scd_act_view_x();h-=128;h&=-128;
            if((unsigned short)(short)((e->x&-128)-h)>640){deferred_reload[j]=0;continue;}
        }
        if(deferred_reload[j])continue;
        /* Windowed actors load on the camera window alone (Object Spawner.asm:
           SpawnObjects_Forward spawns below (camera X & $FF80) + $280), not on a
           player distance. */
        if(distance>480 && !stream_windowed(e->type))continue;
        if((e->type==SCD_OBJ_PROJECTOR && projector_destroyed) || (e->type==SCD_OBJ_ANIMAL && !(e->subtype&128) && current_era>=2 && !good_future))continue;
        if(((current_era==2 || (good_future && (current_era!=0 || e->subtype))) && enemy(e->type)) || (consumed[j] && e->type!=SCD_OBJ_TIMEPOST && e->type!=SCD_OBJ_SONIC_HOLE) || !(e->eras&era_bit))continue;
        if(live[j/32]&(1u<<(j%32)))continue;
        if(ta_absent(e->type,e->subtype))continue;
        /* Windowed zone actors (scd_zone_ops.stream_windowed: TT, QQ) frame
           out (tp_frameout_s, FRAMEOUT_S's ACTSET camera-chunk window) once
           their 128 px chunk is outside [chunk(camera-128), +640]; the +-480 px
           player stream would reload them the next update, every update
           (BANEIWA's init adds a partner each time). Spawn them inside that
           window only; a placed actor removed inside it (remove_slot) waits
           until the window has left it, as ACTSET loads a placement only when
           the window reaches its column. */
        int index=spawn_from(e->type,e->x,e->y,e->subtype,e->flags,first);
        if(index<0)break;pool[index].origin=j;actwk[index+1].userflag.b.l=e->secondary;
        first=(unsigned)index+1;live[j/32]|=1u<<(j%32);
        if(consumed[j] && e->type==SCD_OBJ_SONIC_HOLE)pool[index].state=1;
        if(consumed[j] && e->type==SCD_OBJ_TIMEPOST){pool[index].state=2;pool[index].anim=1;pool[index].frame=e->subtype<8?11:(e->subtype==9?3:1);}
    }
}
/* Fixed-point translations of PPZ1 Objects/{Anton,Mosqui,Pata-Bata,
 * Taga-Taga,Tamabboh}/Main.asm. Collision uses the bounded native frontend. */
/* PPZ badnik explosions (Explosion/Main.asm). Player_TouchEnemy (PPZ Player
   Object Collision.asm) and DestroyOnGoodFuture (Object Time Check.asm) turn
   the badnik's slot into an explosion with oExplodeBadnik clear: its init
   spawns a points object (FindObjSlot, ObjPoints: 24 updates) and its end
   turns the slot into a flower, which never frames out. The badnik's slot runs
   after Sonic's, so the init happens in the update of the kill. */
enum{PPZ_BADNIK_BOOM=0x5050};
static void ppz_badnik_boom(unsigned i,unsigned score,unsigned sub){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1];
    if(s->origin<SCD_PLACEMENT_CAPACITY && (active_placements[s->origin].flags&TT_SAVED))consumed[s->origin]=1;
    *s=(slot){.origin=65535,.type=SCD_OBJ_EXPLOSION,.subtype=(uint8_t)sub,.phase=PPZ_BADNIK_BOOM,.age=1};
    o->actno=SCD_OBJ_EXPLOSION;o->colino=0;o->r_no0=o->r_no1=0;
    unsigned frame=(score>>1)|128;
    for(unsigned k=0;k<SCD_OBJECT_CAPACITY;k++)if(pool_slot_free(k)){
        pool[k]=(slot){.origin=65535,.type=SCD_OBJ_SCORE,.subtype=(uint8_t)frame};
        sprite_status *c=&actwk[k+1];memset(c,0,sizeof(*c));c->actno=SCD_OBJ_SCORE;
        c->xposi.w.h=o->xposi.w.h;c->yposi.w.h=o->yposi.w.h;c->userflag.b.h=(char)frame;
        stats.spawned++;break;
    }
}
static int enemy_step(unsigned i) {
    slot *s=&pool[i];sprite_status *o=&actwk[i+1],*p=&actwk[0];
    /* DestroyOnGoodFuture runs first in each PPZ badnik (not the Tamabboh shot). */
    if(objects_zone==0 && load_placements && ppz_badnik(s->type) && !(s->type==SCD_OBJ_TAMABBOH && s->subtype==1)
       && good_future && (current_era!=0 || s->subtype)){ppz_badnik_boom(i,0,0);return 1;}
    unsigned damaged=!!s->subtype;
    int dx=p->xposi.w.h-o->xposi.w.h,dy=p->yposi.w.h-o->yposi.w.h;
    if(s->type==SCD_OBJ_TAMABBOH && s->subtype==1) {
        /* Tamabboh/Main.asm ObjTamabbohMissile: the spawn update runs Init only;
           Main tests the floor before it moves (retail PPZ1A 10163-10184). */
        if(s->age<=1){s->frame=6;return 0;}
        if(emycol_d(o)<0){remove_slot(i);return 1;}
        o->xposi.l+=(int)o->xspeed.w*256;o->yposi.l+=(int)o->yspeed.w*256;o->yspeed.w+=32;
        s->frame=6+((s->age-2)/3)%4;
        if(magnitude(dx)>320 || magnitude(dy)>224 || o->yposi.w.h<0 || o->yposi.w.h>=2040 || s->age>240){remove_slot(i);return 1;}
        return 0;
    }
    if(s->type==SCD_OBJ_TAGATAGA) {
        /* Taga-Taga/Main.asm: Init2 (the update after landing, or the init
           update) puts it home with collision off and restarts animation 0
           ($59, 6, $FC): the Jump routine, first motion, runs 91 updates later. */
        if(s->state==2){o->yposi.l=s->home_y*65536;s->state=0;s->timer=92;}
        if(!s->state){s->frame=6+damaged*7;if(s->age==1)s->timer=92;if(--s->timer)return 0;s->state=1;soundset(162);o->yspeed.w=damaged?-768:-960;s->phase=0;}
        o->yposi.l+=(int)o->yspeed.w*256;o->yspeed.w+=16;
        static const uint8_t normal[]={0,0,0,1,0,1,2,3,5,5,5,5,4,5,4,5,4,5};
        static const uint8_t broken[]={0,0,0,0,0,0,0,0,2,2,3,3,4,4,4,4,4,4,4,4,4,4,4};
        s->frame=damaged?7+broken[(s->phase/5)%23]:normal[(s->phase/8)%18];s->phase++;
        if(o->yposi.w.h>s->home_y){s->state=2;soundset(162);}
        return 0;
    }
    if(s->type==SCD_OBJ_MOSQUI && s->state) {
        /* Mosqui/Main.asm ObjMosqui_Wait: DespawnObject once the previous
           frame's DrawObjects left it off screen (Object Functions.asm
           DrawObject: oWidth/oYRadius $10 against the camera). */
        if(s->state==3){
            int sx=o->xposi.w.h-scd_act_view_x(),sy=o->yposi.w.h-scd_act_view_y();
            if(!(sx+16>=0 && sx-16<320 && sy+16>=0 && sy-16<224)){remove_slot(i);return 1;}
        }
        /* Ani_Mosqui anim 1 ($E or 6: frames 2, 3, 4, $FC): AnimateObject reaches
           $FC, and the Dive routine, on its 3*wait+1th call. */
        if(s->state==1){unsigned wait=damaged?15:7;s->frame=damaged*5+2+(s->timer<wait*3?s->timer/wait:2);if(++s->timer>wait*3){s->state=2;s->frame=damaged*5+4;}}
        else if(s->state==2){o->yposi.l+=6*65536;short d=emycol_d(o);if(d<=-8){o->yposi.w.h+=d+8;s->state=3;soundset(167);}}
        return 0;
    }
    if(s->type==SCD_OBJ_MOSQUI && dx>=-48 && dx<48 && dy>=-48 && dy<64){s->state=1;s->timer=0;return 0;}
    if(s->type==SCD_OBJ_TAMABBOH && s->state==2) {
        s->frame=damaged?5:2;
        /* Wait1 (one update), then Wait2 holds anim 1 ($3B: 60 updates) until $FC,
           and Fire runs one update later: missiles 62 updates after the stop
           (retail PPZ1A: stop 10101, missiles 10163). Damaged Wait2 holds
           $B (12 updates): Main again 14 updates later (retail PPZ1D 8790-8803). */
        if(++s->timer>=(damaged?14:62)) {
            s->state=1;s->timer=0;s->cooldown=120;
            if(damaged){s->phase=0;return 0;}
            soundset(160);
            for(unsigned side=0;side<2;side++) {
                int child=scd_objects_spawn(SCD_OBJ_TAMABBOH,o->xposi.w.h,o->yposi.w.h-10,1,side);
                if(child>=0)stats.projectiles++;
            }
        }
        return 0;
    }
    /* Anton/Main.asm ObjAnton_Place and Tamabboh ObjTamabboh_Position: one pixel
       down per update until the floor distance is negative, with no snap (Main
       adds it). ObjAnton_Init has no routine step, so the first hit only reaches
       Place, which sinks one more pixel before Main (retail PPZ2B 10727-10729). */
    if((s->type==SCD_OBJ_ANTON || s->type==SCD_OBJ_TAMABBOH) && (!s->state || (s->type==SCD_OBJ_ANTON && s->state==4))) {
        o->yposi.l+=65536;short d=emycol_d(o);
        if(d<0)s->state=s->type==SCD_OBJ_ANTON && !s->state?4:1;
        return 0;
    }
    /* Tamabboh/Main.asm ObjTamabboh_CheckInRange: unsigned (d+$50) < $A0, so the
       box is [-80,80) on both axes (retail PPZ1A 10101 stops at dx -80); only
       subtype 0 checks it (.SkipRange for any other subtype). */
    if(s->type==SCD_OBJ_TAMABBOH && !s->subtype && !damaged && !s->cooldown && dx>=-80 && dx<80 && dy>=-80 && dy<80){s->state=2;s->timer=0;return 0;}
    int32_t previous=o->xposi.l;o->xposi.l+=(int)o->xspeed.w*256;
    int ground=s->type==SCD_OBJ_ANTON || s->type==SCD_OBJ_TAMABBOH;
    short d=ground?emycol_d(o):0;
    if(magnitude(o->xposi.w.h-s->home_x)>=128 || (ground && (d < -7 || d > 7))) {
        /* Tamabboh .TurnAround leaves its animation running. */
        o->xposi.l=previous;o->xspeed.w=-o->xspeed.w;s->flags^=1;o->cddat^=1;if(s->type!=SCD_OBJ_TAMABBOH)s->phase=0;
    } else if(ground)o->yposi.w.h+=d;
    /* Damaged Tamabboh (Animations (Damaged).asm: 16 frames at speed 5, then $FC):
       Main's AnimateObject, after the move, steps to Wait1 on its 97th call
       (retail PPZ1D: Main 8693-8789, Wait1 8790). */
    if(s->type==SCD_OBJ_TAMABBOH && damaged && ++s->phase>=97){s->state=2;s->timer=0;}
    if(s->type==SCD_OBJ_ANTON)s->frame=damaged*2+(s->age/(damaged?8:4))%2;
    if(s->type==SCD_OBJ_TAMABBOH)s->frame=damaged*3+(s->age/(damaged?6:30))%2;
    if(s->type==SCD_OBJ_MOSQUI)s->frame=damaged*5+(s->age/(damaged?5:2))%2;
    if(s->type==SCD_OBJ_PATABATA){short sn,cs;s->phase-=damaged?256:512;sinset(s->phase>>8,&sn,&cs);o->yposi.l=s->home_y*65536+32768+(int)sn*(damaged?4096:8192);static const uint8_t seq[]={0,0,1,2,1};s->frame=damaged*3+seq[(s->age/(damaged?4:8))%5];}
    if(o->xposi.w.h<0 || o->xposi.w.h>=16384 || o->yposi.w.h>=2040){remove_slot(i);return 1;}
    return 0;
}
/* Original PPZ 3D Ramp/Main.asm. Subtype bit 7 is the source's
 * secondary subtype (invisible fall marker); plant subtypes select siblings. */
static void ramp_step(unsigned i){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1],*p=&actwk[0];
    int on_ramp=p->actfree[2]&2,chunk=p->xposi.w.h&255;
    if(s->type==SCD_OBJ_RAMP_PLANT){
        if(s->subtype>=4)return;
        static const int offsets[]={64,128,-64,-128};
        int center=s->home_x-offsets[s->subtype],left=p->xposi.w.h<center;
        if(left)chunk=255-chunk;
        if(chunk>=192)chunk=chunk>=240?0:191;
        o->xposi.w.h=s->home_x+(on_ramp?(left?-chunk/2:chunk/2):0);return;
    }
    if(s->subtype&128){
        if(p->r_no0>=4 || p->mstno.b.h==43)return;
        int dx=o->xposi.w.h-p->xposi.w.h,dy=o->yposi.w.h-p->yposi.w.h;
        if(dx>=-32 && dx<32 && dy>=-64 && dy<64 && p->xspeed.w<0 && dx>=0){
            p->xposi.w.h=o->xposi.w.h;p->xspeed.w=p->mspeed.w=0;
            p->mstno.b.h=55;p->actfree[18]=1;p->actfree[14]=0;p->cddat|=4;
            /* Retail writes these radius/Y fields to the marker itself. */
            o->sprvsize=14;o->sprhs=7;o->yposi.w.h+=5;
        }return;
    }
    if(s->subtype&1)chunk=255-chunk;
    if(chunk>=192)chunk=chunk>=240?0:191;
    if(s->timer){
        unsigned state=on_ramp?1:2;
        if(s->state!=state){s->state=state;s->phase=0;}
        static const uint8_t frames[2][4]={{4,7,5,6},{8,0,9,0}};
        s->frame=frames[state-1][(s->phase++/3)%4];
    }else{s->state=0;s->phase=0;s->frame=on_ramp?chunk/48:0;}
    int shift=(on_ramp || s->timer)?chunk/4+chunk/8:0;
    o->xposi.w.h=s->home_x+((s->subtype&1)?-shift:shift);
    int touching=s->timer || !(p->cddat&2);
    if(s->timer)s->timer--;
    int dx=p->xposi.w.h-o->xposi.w.h,dy=p->yposi.w.h-o->yposi.w.h;
    if(touching && p->r_no0<4 && p->mstno.b.h!=43 && dx>=-32 && dx<32 && dy>=-32 && dy<32){
        if(!s->timer)s->timer=60;
        p->yspeed.w=p->yspeed.w<0?-3072:3072;
    }
}
/* TopSolidObject / StandOnObject from Level/Object Solid.asm. This path
 * is used by the new top-solid objects; existing spring/boulder fixtures retain
 * their established contact frontend. */
static int top_solid(unsigned i){
    sprite_status *o=&actwk[i+1],*p=&actwk[0];
    int dx=p->xposi.w.h-o->xposi.w.h,dy=p->yposi.w.h-o->yposi.w.h;
    int width=o->sprhsize+10,height=o->sprvsize+p->sprvsize+2;
    if((p->actfree[2]&64) || p->r_no0>=6 || (scd_player_warp_saved() && !draw_onscreen(o)) || p->yspeed.w<0 || dx < -width || dx>=width || dy < -height || dy>0 || height+dy>=width-magnitude(dx)){
        release_rider(i+1);return 0;
    }
    if((p->cddat&8) && p->actfree[19]!=i+1){
        unsigned previous=p->actfree[19];
        /* Original StandOnObject transfers support without clearing control. */
        if(pool[i].type==SCD_OBJ_DISC && control_actor==previous && previous && previous<=SCD_OBJECT_CAPACITY && pool[previous-1].type==SCD_OBJ_DISC)actwk[previous].cddat&=~8;
        else release_rider(previous);
    }
    int first=!(o->cddat&8) || !(p->cddat&8) || p->actfree[19]!=i+1;
    p->yposi.w.h=o->yposi.w.h-o->sprvsize-p->sprvsize;
    p->xposi.l+=(int)o->xspeed.w*256;
    /* RIDECHK.C:496-515 hit_y (retail $20806E-$2080AC): dircolm probes the
       wall ahead of the player's own speed, then the object's Y speed lands. */
    if(o->xspeed.w){
        char direction=o->xspeed.w<0?64:-64;short d=dircolm(p,&direction);
        if(d<0)p->xposi.w.h+=o->xspeed.w>0?d:-d;
    }
    p->yposi.l+=(int)o->yspeed.w*256;
    /* Object Solid.asm:396-406 (RIDECHK.C hit_y: dircol_d): Player_CheckFloor
       reads both foot sensors (x +- the X radius), Collision Check.asm:79-104. */
    if(o->yspeed.w>=0){short d0,d1,d3,d=dircol_d(p,&d0,&d1,&d3);if(d<0){p->yposi.w.h+=d;release_rider(i+1);return 0;}}
    else if(emycol_u(p)<0){playdieset(p);stats.deaths++;release_rider(i+1);return 0;}
    if(p->r_no0==4){p->r_no0=2;scd_word_set(p,26,120);}
    p->actfree[18]=0;
    if(first){
        p->cddat&=~16;
        /* RIDECHK.C:145-157: the R8 shrink form keeps its 10/5 radii. */
        if(p->cddat&4){p->cddat&=~4;if(chibi_flag){p->sprvsize=10;p->sprhs=5;p->yposi.w.h-=2;}else{p->sprvsize=19;p->sprhs=9;p->yposi.w.h-=5;}p->mstno.b.h=0;}
        p->mspeed.w=p->xspeed.w;p->direc.b.h=0;p->yspeed.w=0;
    }
    o->cddat|=8;p->cddat=(p->cddat|8)&~2;p->actfree[19]=i+1;
    return 1;
}
/* Stationary SolidObject: the same penetration choice as the original,
 * with top standing/carry shared with platforms. Walls/spikes cannot crush
 * horizontally because their object velocity is zero. */
static int static_solid(unsigned i){
    sprite_status *o=&actwk[i+1],*p=&actwk[0];
    int dx=p->xposi.w.h-o->xposi.w.h,dy=p->yposi.w.h-o->yposi.w.h;
    int width=o->sprhsize+10,height=o->sprvsize+p->sprvsize+2;
    if((p->actfree[2]&64) || p->r_no0>=6 || (scd_player_warp_saved() && !draw_onscreen(o)) || dx < -width || dx>=width || dy < -height || dy>=height){
        /* Object Solid.asm:473-479 .GetOff: StopObjPush forgets the pushed
           object but leaves both push bits; the player's own movement clears
           them (retail TT1B/TT2C monitors: status keeps bit 5). */
        release_rider(i+1);return 0;
    }
    int horizontal=width-magnitude(dx),vertical=height-magnitude(dy);
    if(vertical<horizontal){
        /* Object Solid.asm:329-332: a rolling player gets no top/bottom contact from a monitor. */
        if(pool[i].type==SCD_OBJ_TIMEPOST && (p->cddat&4)){release_rider(i+1);return 0;}
        if(dy<=0)return top_solid(i);
        if(pool[i].type==SCD_OBJ_DISC){release_rider(i+1);return 0;}
        release_rider(i+1);o->cddat&=~32;p->cddat&=~32;
        p->yposi.w.h=o->yposi.w.h+height;p->yspeed.w=0;return 2;
    }
    if(vertical<=4){release_rider(i+1);return 0;}
    release_rider(i+1);
    p->xposi.w.h=o->xposi.w.h+(dx<=0?-width:width);
    if((dx<=0 && p->xspeed.w>0) || (dx>0 && p->xspeed.w<0)){
        if(!(p->cddat&2)){p->cddat|=32;o->cddat|=32;p->mspeed.w=0;}
        p->xspeed.w=0;
    }else{o->cddat&=~32;p->cddat&=~32;}
    return 0;
}
static void spike_step(unsigned i){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1],*p=&actwk[0];
    int dx=p->xposi.w.h-o->xposi.w.h,dy=p->yposi.w.h-o->yposi.w.h;
    if(s->flags&2){
        /* Inverted source collision $83 has 12x16 half extents. */
        int radius=p->sprvsize-3;
        if(dx>=-20 && dx<=20 && dy>=-16-radius && dy<=16+radius)scd_objects_hurt(o->xposi.w.h);
    }
    if(magnitude(dy)>=32){release_rider(i+1);return;}
    if(static_solid(i)==1 && !(s->flags&2))scd_objects_hurt(o->xposi.w.h);
}
static void wall_step(unsigned i){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1],*p=&actwk[0];
    if(!s->state){
        int dx=p->xposi.w.h-o->xposi.w.h,dy=p->yposi.w.h-o->yposi.w.h;
        int radius=p->sprvsize-3;
        if(p->r_no0>=4 || p->mstno.b.h!=2 || dx < -30 || dx>30 || dy < -26-radius || dy>26+radius){static_solid(i);return;}
        static const uint8_t frames[8][6]={{8,9,8,12,13,12},{8,9,8,10,11,10},{10,11,10,10,11,10},{10,11,10,12,13,12},{9,8,9,13,12,13},{9,8,9,11,10,11},{11,10,11,11,10,11},{11,10,11,13,12,13}};
        /* Child offsets are relative to the already-offset parent in source. */
        static const int8_t offsets[6][2]={{-8,-16},{-8,0},{-8,16},{8,-16},{8,0},{8,16}};
        static const int32_t vx[6]={-194180,-252434,-194180,-194180,-223307,-194180};
        static const int32_t vy[6]={-84144,0,84144,-113595,0,113595};
        int x=o->xposi.w.h,y=o->yposi.w.h;unsigned sub=s->subtype,flags=s->flags;
        release_rider(i+1);o->cddat&=~32;p->cddat&=~32;
        p->xspeed.w>>=1;int direction=p->xspeed.w<0?-1:1;
        /* Breakable Wall/Main.asm: the wall and its pieces end in DeleteObject, which
           leaves the record's saved-flags spawned bit set (Object Spawner.asm
           SpawnObject skips it), so a streamed wall never loads again (retail
           PPZ2B 5678 halves no xspeed at x 4000). */
        if(tt_streamed() && s->origin<SCD_PLACEMENT_CAPACITY && (active_placements[s->origin].flags&TT_SAVED))consumed[s->origin]=1;
        else if(s->origin!=65535)deferred_reload[s->origin]=1;
        s->origin=65535;stats.broken++;soundset(176);
        for(unsigned piece=0;piece<6;piece++){
            int child=piece?scd_objects_spawn(SCD_OBJ_WALL,x,y,sub,flags):(int)i;
            if(child<0)break;
            slot *c=&pool[child];sprite_status *a=&actwk[child+1];
            c->state=1;c->frame=frames[sub][piece];c->debris_vx=vx[piece]*direction;c->debris_vy=vy[piece];
            a->xposi.l=(x+offsets[piece][0])*65536;a->yposi.l=(y+offsets[piece][1])*65536;
            a->sprhsize=a->sprvsize=8;
        }
    }
    s->debris_vy+=16384;o->xposi.l+=s->debris_vx;o->yposi.l+=s->debris_vy;
    if(o->yposi.w.h>=p->yposi.w.h+224)remove_slot(i);
}
/* Original collapsing platform breakup. The parent remains allocated while
 * children are found, then disappears even on allocation failure. */
static void collapse_step(unsigned i){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1],*p=&actwk[0];
    if(s->state==2){
        o->yposi.l+=s->debris_vy;s->debris_vy+=0x4000;
        if(o->yposi.w.h-p->yposi.w.h>512)remove_slot(i);
        return;
    }
    if(s->state==1){
        if(!--s->timer)s->state=2;
        /* A piece's first update runs before DrawObject has set its on-screen
           bit, so TopSolidObject (SolidObject: tst.b oSprFlags) gets off. */
        if(s->sink && s->age>1 && top_solid(i) && !s->timer)release_rider(i+1);
        return;
    }
    if(!top_solid(i))return;
    release_rider(i+1);soundset(163);stats.collapsed++;
    unsigned era=current_era>1?2:current_era,sub=s->subtype,single=!!(sub&128);
    const scd_collapse_shape *shape=COLLAPSE_SHAPE(era,single,sub&15);
    int x=o->xposi.w.h,y=o->yposi.w.h,direction=1;
    if(single)direction=(sub&64)?((sub&32)?-p->xspeed.w:p->xspeed.w)<0?-1:1:(sub&32)?-1:1;
    else if(sub&16)direction=-1;
    /* Collapsing Platform/Main.asm: the pieces end in DeleteObject; a saved record
       stays marked spawned and never loads again (as the Breakable Wall). */
    if(tt_streamed() && s->origin<SCD_PLACEMENT_CAPACITY && (active_placements[s->origin].flags&TT_SAVED))consumed[s->origin]=1;
    else if(s->origin!=65535)deferred_reload[s->origin]=1;
    unsigned rows=single?1:shape->rows+1,cols=shape->columns+1;
    /* Nothing frees a slot inside this batch, so the lowest free slot for the
       next piece lies after the previous one: resume both scans there instead
       of walking the occupied prefix of the pool twice per piece (up to 17
       pieces in one update). Slot order is unchanged. */
    unsigned first=0;
    for(unsigned row=0;row<rows;row++)for(unsigned col=0;col<cols;col++){
        /* FindObjSlot runs even for an empty cell; an exhausted pool stops
           the original traversal before reading that cell's frame byte. */
#ifdef SCD_COLLAPSE_FULL_SCAN
        /* Reference (tools/test-collapse-spawn.sh): from-slot-0 scans. */
        unsigned free;for(free=0;free<SCD_OBJECT_CAPACITY && pool[free].type;free++);
        if(free==SCD_OBJECT_CAPACITY){stats.dropped++;goto done;}
        unsigned cell=single?(direction<0?cols-1-col:col):row*cols+col;
        int frame=shape->pieces[cell];if(frame<0)continue;
        int child=scd_objects_spawn(SCD_OBJ_COLLAPSE,x,y,sub,(!single && direction<0)?1:0);
        if(child<0)goto done;
        (void)first;
#else
        unsigned free;for(free=first;free<SCD_OBJECT_CAPACITY && pool[free].type;free++);
#ifdef SCD_OBJECTS_VERIFY
        /* No slot below the resume point was freed inside this batch. */
        {unsigned full;for(full=0;full<SCD_OBJECT_CAPACITY && pool[full].type;full++);assert(full==free);}
#endif
        if(free==SCD_OBJECT_CAPACITY){stats.dropped++;goto done;}
        first=free;
        unsigned cell=single?(direction<0?cols-1-col:col):row*cols+col;
        int frame=shape->pieces[cell];if(frame<0)continue;
        int child=spawn_from(SCD_OBJ_COLLAPSE,x,y,sub,(!single && direction<0)?1:0,free);
        if(child<0)goto done;
#ifdef SCD_OBJECTS_VERIFY
        assert((unsigned)child==free);
#endif
        first=(unsigned)child+1;
#endif
        slot *c=&pool[child];sprite_status *a=&actwk[child+1];
        c->state=1;c->frame=COLLAPSE_BASE(era,single?3:2)+frame;
        c->flags=(!single && direction<0)?1:0;a->cddat=c->flags;
        c->timer=9+col*12+(single?0:row*5);c->debris_vy=0x20000;
        c->sink=single || row==rows-1;
        a->xposi.l=(x+direction*(-(int)shape->columns*8+(int)col*16))*65536;
        a->yposi.l=(y+(single?0:shape->rows*8-(int)row*16))*65536;
        a->sprhsize=8;a->sprvsize=single?(shape->rows+1)*8+2:9;
        stats.collapse_pieces++;
    }
 done:
    remove_slot(i);
}
/* The original spawner advances layout cursors when crossing camera chunks.
 * This frontend scans nearby records each tick, so fallen objects must wait
 * for their spawn area to be left before becoming eligible again. */
static void remove_fallen(unsigned i){
    if(pool[i].origin!=65535)deferred_reload[pool[i].origin]=1;
    remove_slot(i);
}
static void float_step(unsigned i){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1];
    unsigned state=s->state;
    if(state==5){s->state=0;return;}
    /* ObjFloatBlock_TopSolid runs TopSolidObject twice (bsr .Check, then falls
       into .Check): after the first call's landing restores the standing
       radius, the second call's Player_CheckFloor can drop Sonic onto the
       ground (_Objects/Floating Block/Main.asm). */
    top_solid(i);
    int standing=top_solid(i);
    if(!state){
        s->frame=current_era==0?0:5;
        if(current_era==1)return;
        if(!standing)return;
        s->state=current_era==0?2:1;s->phase=0;
        if(current_era==0)return;
    }
    if(s->state==1){
        o->yposi.w.h+=2;
        if(o->yposi.w.h>actwk[0].yposi.w.h+84 || o->yposi.w.h>=2040)remove_fallen(i);
        return;
    }
    if(s->state==2 && !standing){s->state=0;return;}
    if(s->state==3){
        if(!standing){s->state=4;s->phase=0;return;}
        s->frame=5;return;
    }
    static const uint8_t appear[]={1,5,2,5,3,5,4,5},vanish[]={1,0,2,0,3,0,4,0};
    unsigned index=s->phase/3;
    if(index>=8){s->state++;s->phase=0;return;}
    s->frame=(s->state==2?appear:vanish)[index];s->phase++;
}
/* All movement subtypes present in PPZ1's original platform placements. */
static int platform_sink(unsigned i){
    slot *s=&pool[i];int standing=top_solid(i);
    if(standing){if(s->sink<8)s->sink++;}else if(s->sink)s->sink--;
    return standing;
}
static int platform_static(unsigned i){
    actwk[i+1].yposi.w.h=pool[i].home_y+pool[i].sink/2;
    return platform_sink(i);
}
static int platform_osc(slot *s){
    static const unsigned ranges[]={2,3,4,6};short sn,cs;sinset(s->phase&255,&sn,&cs);
    return ((int)sn*ranges[(s->subtype>>2)&3])>>4;
}
static void platform_step(unsigned i){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1];unsigned mode=s->subtype>>4;
    if(mode==4){platform_static(i);return;}
    if(mode==5){
        if(!s->state){if(!platform_static(i))return;s->state=1;s->timer=30;}
        if(s->timer){s->timer--;platform_static(i);return;}
        top_solid(i);o->yposi.l+=(int)o->yspeed.w*256;
        if(o->yspeed.w<1024)o->yspeed.w+=64;
        int camera=actwk[0].yposi.w.h-140;if(camera<0)camera=0;if(camera>1824)camera=1824;
        if(o->yposi.w.h>camera+256)remove_fallen(i);
        return;
    }
    if(mode==6){
        if(!s->state){if(!platform_static(i))return;s->state=1;}
        if(s->state==1){
            if(s->phase>=64){s->home_y=o->yposi.w.h;s->state=2;}
            else{o->yposi.w.h=s->home_y-platform_osc(s);s->phase+=2;top_solid(i);return;}
        }
        platform_static(i);return;
    }
    /* ObjPlatform_Init only initializes; the oscillation starts next update. */
    if(objects_zone==0 && s->age==1)return;
    int32_t previous=o->xposi.l;
    if(mode!=1)s->phase=(s->phase+1)&255;
    int delta=platform_osc(s);
    if(!mode){o->yposi.w.h=s->home_y+delta;top_solid(i);return;}
    o->xposi.w.h=s->home_x+(mode==3?-delta:delta);
    o->yposi.w.h=s->home_y+(mode==1?s->sink/2:delta);
    if(mode==1)s->phase=(s->phase+1)&255;
    o->xspeed.w=(o->xposi.l-previous)/256;
    platform_sink(i);
}
/* Checkpoint/Main.asm ObjCheckpoint_Init: the ball is its own object in the
   first free slot (FindObjSlot), framing itself out on its X (CheckObjDespawn).
   The native checkpoint draws the ball; a title-card-type placeholder holds
   the slot (PPZ, retail Object Spawner path). Tidal Tempest's
   PLAYSUB4.C marker_init takes it the same way (actwkchk, lowest free from
   actwk[32]) and frames it out through frameout_s (retail TT2A row 5989:
   ball in slot 43, the placement in 58). Metallic Madness too (retail
   R83C marker_init calls actwkchk $207534; MM1A 2372: the ball takes
   slot 32 as the propera there frames out, the saw bar 40). */
enum{PPZ_CHECKPOINT_BALL=0x4342+1};
static void checkpoint_step(unsigned i){
    slot *s=&pool[i];sprite_status *p=&actwk[0],*o=&actwk[i+1];
    if((objects_zone==0 || objects_zone==2 || objects_zone==6) && load_placements && s->age==1){
        for(unsigned k=0;k<SCD_OBJECT_CAPACITY;k++)if(pool_slot_free(k)){
            pool[k]=(slot){.origin=65535,.type=SCD_OBJ_CARD,.phase=PPZ_CHECKPOINT_BALL,.home_x=o->xposi.w.h};
            memset(&actwk[k+1],0,sizeof(actwk[k+1]));actwk[k+1].actno=SCD_OBJ_CARD;stats.spawned++;
            if(objects_zone==6)scd_boss_slot_first(k+1);
            break;
        }
    }
    if(!s->state){
        if(scd_player_checkpoint().id>=s->subtype)s->state=2;
        else {
            /* Source collision $E3: 12x24, player half-width 8 / radius-3. */
            int dx=p->xposi.w.h-o->xposi.w.h,dy=p->yposi.w.h-o->yposi.w.h;
            int radius=p->sprvsize-3;
            if(p->mstno.b.h==8){dy+=12;radius=10;}
            if(dx>=-20 && dx<=20 && dy>=-24-radius && dy<=24+radius && scd_player_checkpoint_activate(s->subtype))s->state=1;
        }
    }
    if(s->state==1){s->phase=(s->phase+8)&255;if(!s->phase){s->state=2;s->timer=0;}}
    else if(s->state==2)s->timer++;
}
/* Player_ObjCollide's monitor touch (Collision 0x46: 16x16 plus Sonic's
   8/(radius-3) rectangle). Returns 1 when a rolling hit breaks the monitor. */
static int monitor_touch(unsigned i){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1],*p=&actwk[0];
    if(p->r_no0>=4 || (p->actfree[2]&128))return 0;
    int dx=p->xposi.w.h-o->xposi.w.h,dy=p->yposi.w.h-o->yposi.w.h,radius=p->sprvsize-3;
    if(p->mstno.b.h==8){dy+=12;radius=10;}
    /* Collision 0x46 is 16x16 plus Sonic's 8/(radius-3) rectangle. */
    if(magnitude(dx)<=24 && magnitude(dy)<=16+radius){
        if(touch_owner!=i+1)return 0;
        /* MM: COLI8.C:289 pcolitem refuses an item on the other layer
           (userflag.b.l against prio_flag); the touch is still spent. */
        if(objects_zone==6 && !prio_flag!=!o->userflag.b.l)return 0;
        if(p->yspeed.w<0){
            if(p->yposi.w.h-16>=o->yposi.w.h){p->yspeed.w=-p->yspeed.w;o->yspeed.w=-384;s->state=1;}
        }else if(p->mstno.b.h==2){
            p->yspeed.w=-p->yspeed.w;s->state=2;s->frame=11;stats.monitors++;release_rider(i+1);
            if(o->cddat&32){o->cddat&=~32;p->cddat&=~32;}soundset(150);
            if(s->origin!=65535)consumed[s->origin]=1;
            scd_objects_spawn(SCD_OBJ_MONITOR_ITEM,o->xposi.w.h,o->yposi.w.h,s->subtype,0);
            /* ITEM.C itemget: the explosion gets r_no1=1 (no points, no flower;
               retail TT2A row 981 frees its slot at row 1003). */
            {int e=scd_objects_spawn(SCD_OBJ_EXPLOSION,o->xposi.w.h,o->yposi.w.h,1,0);if(e>=0)actwk[e+1].r_no1=1;}
            return 1;
        }
    }
    return 0;
}
static void monitor_step(unsigned i){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1],*p=&actwk[0];
    if(s->type==SCD_OBJ_MONITOR_ITEM){
        if(!s->state){
            if(o->yspeed.w<0){o->yposi.l+=(int)o->yspeed.w*256;o->yspeed.w+=24;}
            else {scd_player_powerup(s->subtype);stats.items++;s->state=1;s->timer=30;}
        }else if(!--s->timer)remove_slot(i);
        return;
    }
    if(s->state==2)return;
    if(s->subtype>=8){
        if(s->state){
            static const uint8_t spin[]={0,4,5,4,1,4,5,4};
            if(s->timer && !--s->timer){s->state=2;s->frame=s->subtype==9?3:1;}
            else {unsigned f=spin[((60-s->timer)/2)%8];s->frame=f<2?f+(s->subtype==9?2:0):f;}
        }else if(objects_zone==6?(o->colicnt && !(o->colicnt=0) && !prio_flag==!o->userflag.b.l):touch_owner==i+1){
            /* MM: ITEM.C:271-280 t_item_move0 takes COLI8 pcol's count
               (mm_enemy_scan), spends it, and ignores it on the other layer. */
            /* ObjTimePost_Main activates on Player_ObjCollide's touch ($DF,
               4x24; the update's first touched object only). */
            s->state=1;s->timer=60;pending_post=s->subtype==8?-1:1;soundset(s->subtype==8?178:177);
            if(s->origin!=65535)consumed[s->origin]=1;
        }
        return;
    }
    /* Sega CD order: Sonic's Player_ObjCollide (_Objects/Sonic/Main.asm:347)
       runs in his own slot before ObjMonitor_Main's SolidObject (Monitor and
       Time Post/Main.asm), so a rolling hit breaks the monitor before it can
       push him, unless an earlier slot took the update's touch. */
    if(monitor_touch(i))return;
    /* ObjMonitor_Main tests the visibility from the preceding DrawObject
       before calling SolidObject. */
    /* MM: ITEM.C:335-343 ride_on_chk_i (retail R82C $209FA4) skips the solid
       unless the monitor's layer (userflag.b.l) matches the player's prio_flag. */
    if(!s->state && (objects_zone!=4 || (o->actflg&128)) && (objects_zone!=6 || !prio_flag==!o->userflag.b.l))static_solid(i);
    /* Ani_Monitor: blank, icon/icon, static, icon/icon, alternate static,
       icon/icon; two updates per frame. ObjMonitor_Main (ITEM.C itemmove)
       animates only when the preceding DrawObject left the monitor on screen
       and time runs, so the phase holds while it is off screen (retail R11A,
       tools/test_anim_phase_retail.py). The spawn update has not been drawn. */
    static const uint8_t animation[]={10,255,255,8,255,255,9,255,255};
    if(s->age>1 && draw_onscreen(o) && !scd_player_time_stop() && (int8_t)--s->anim_time<0){
        s->anim_time=1;unsigned frame=animation[s->anim_frame];s->frame=frame==255?s->subtype:frame;
        if(++s->anim_frame>=9)s->anim_frame=0;
    }
    if(s->state==1){
        o->yposi.l+=(int)o->yspeed.w*256;o->yspeed.w+=56;
        /* ObjMonitor_Main: ObjMoveGrv, then ObjGetFloorDist every falling update,
           rising too (a bump next to a slope aligns it at once). */
        {short d=emycol_d(o);if(d<0){o->yposi.w.h+=d;o->yspeed.w=0;s->state=0;}}
    }
}
/* Original invisible spin-tunnel tags. PPZ horizontal minimum is 0xA00;
   subtype 1 uses 0xD00 vertically. Subtypes 2..4 retain their input branches. */
static void spin_tag_step(unsigned i){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1],*p=&actwk[0];
    int dx=p->xposi.w.h-o->xposi.w.h,dy=p->yposi.w.h-o->yposi.w.h;
    if(debugflag.w || p->mstno.b.h==43 || p->r_no0>=6 || dx < -40 || dx>=40 || dy < -40 || dy>=40)return;
    stats.tag_contacts++;
    if(!s->subtype){
        /* PLAYSUB.C:872-874: the floor is 2560, raised to 3328 in round index 5,
           Stardust Speedway. stageno.b.h is the retail round index. */
        unsigned floor=stageno.b.h==5?3328:2560;
        int speed=p->xspeed.w;unsigned absolute=magnitude(speed);if(absolute<floor)absolute=floor;
        p->xspeed.w=p->mspeed.w=speed<0?-(int)absolute:(int)absolute;
        if(((p->direc.b.h+32)&192)==128)p->mspeed.w=-p->mspeed.w;
    }else if(s->subtype==1){
        int speed=p->yspeed.w;unsigned absolute=magnitude(speed);if(absolute<3328)absolute=3328;
        p->yspeed.w=p->mspeed.w=speed<0?-(int)absolute:(int)absolute;p->cddat|=2;
    }else if(s->subtype==4){
        if(p->xspeed.w>=0 && (swdata.b.h&1)){p->yspeed.w=p->mspeed.w=-2560;p->cddat|=2;}
    }else if((s->subtype==2?p->yspeed.w<0:p->yspeed.w>=0) && (swdata.b.h&12)){
        p->xspeed.w=p->mspeed.w=(swdata.b.h&8)?3328:-3328;if(s->subtype==3)p->cddat|=2;
    }
    if(!(p->cddat&4)){p->cddat|=4;p->sprvsize=14;p->sprhs=7;p->yposi.w.h+=5;p->mstno.b.h=2;}
}

/* Source horizontal flap and vertical spin-tunnel door state machines. */
static void door_step(unsigned i){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1],*p=&actwk[0];
    if(s->type==SCD_OBJ_DOOR){
        if(s->state==1){
            if(s->timer<10){s->frame=s->timer>=2;s->timer++;}else s->state=2;
            return;
        }
        if(s->state==2){s->state=s->frame=0;return;}
        int dx=p->xposi.w.h-o->xposi.w.h,dy=p->yposi.w.h-o->yposi.w.h;
        if(p->yspeed.w<0 && dx>=-(int)o->sprhsize && dx<o->sprhsize && dy>=-8 && dy<8){
            s->state=1;s->timer=0;stats.doors_opened++;return;
        }
        top_solid(i);return;
    }
    if(s->state){
        s->timer=(s->timer+8)&255;if(!s->timer)s->state=s->frame=0;
        return;
    }
    int dx=o->xposi.w.h-p->xposi.w.h,dy=o->yposi.w.h-p->yposi.w.h;
    if(magnitude(dy)<32 && dx>=0 && dx<48){
        s->state=1;s->timer=0;stats.doors_opened++;
        if(o->actflg&128){s->frame=1;soundset(164);}
    }
    /* Original Main still calls SolidObject on the opening tick. */
    static_solid(i);
}
static void moving_spring_step(unsigned i){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1];
    if(!s->state){
        int child=scd_objects_spawn(SCD_OBJ_SPRING,o->xposi.w.h,o->yposi.w.h,s->subtype,0);
        if(child<0){if(s->origin!=65535)deferred_reload[s->origin]=1;remove_slot(i);return;}
        pool[child].parent=i+1;actwk[child+1].yposi.w.h-=16;s->state=1;
    }
    int floor=emycol_d(o);
    if(s->state==1){
        if(floor<0){o->yposi.w.h+=floor;s->home_y=o->yposi.w.h;s->state=2;}
        else o->yposi.w.h++;
        return;
    }
    o->yposi.w.h+=floor;
    if((uint16_t)(s->home_y-o->yposi.w.h)>=12){o->xspeed.w=-o->xspeed.w;stats.wheel_reversals++;}
    o->xposi.l+=(int)o->xspeed.w*256;o->yposi.l+=(int)o->yspeed.w*256;
    s->frame=s->phase/9;s->phase=(s->phase+1)%18;s->sink=1;
}
/* Existing spring contact frontend, shared by standalone and attached springs.
   Attached position is updated after collision in this actor's scheduler slot. */
static void spring_step(unsigned i,int old_x,int old_y){
    (void)old_x;
    slot *s=&pool[i];sprite_status *o=&actwk[i+1],*p=&actwk[0];
    int carried=(p->cddat&8) && p->actfree[19]==i+1;
    /* SolidObject runs once, on the player's position at the spring's turn. */
    const int entry_x=p->xposi.w.h,entry_y=p->yposi.w.h;
    if(s->parent && (s->parent>SCD_OBJECT_CAPACITY || (pool[s->parent-1].type!=SCD_OBJ_MOVING_SPRING && !cc_trap_parent(pool[s->parent-1].type)))){remove_slot(i);return;}
    /* Original SPRING.C only initializes on its first dispatch. The linked
       trap child is positioned at the end of that tick before it can launch. */
    if(s->parent && cc_trap_parent(pool[s->parent-1].type) && !s->state){s->state=1;goto attached_position;}
    /* ObjSpring_Anim_* and ObjSpring_Reset_* run no solidity after launch.
       Keep attached springs positioned while the animation finishes. */
    if(s->cooldown)goto attached_position;
    /* SPRING.C:399-404 (and Spring/Main.asm:136-137 in R1) runs a spring's
       move routine only while the last actionsub left it on screen (actflg
       bit 7); sdushmove/sjumpmove check it again (:480, :514). Retail MM2D
       row 3482: the side spring at 2944 is off screen (camera 2469) and
       Sonic's 32 px/update dash passes it. */
    if(!(o->actflg&128))goto attached_position;
    /* Object Solid.asm SolidObject only skips a dead player (routine >= 6): a
       hurt player (routine 4) lands on a spring and is launched (retail CC1D
       seq 3451; StandOnObject's frip_stand ends the hurt routine). */
    if(p->r_no0<6 && !(p->actfree[2]&128)){
        int x=p->xposi.w.h,y=p->yposi.w.h,ox=o->xposi.w.h,oy=o->yposi.w.h;
        int hw=o->sprhsize,hh=o->sprvsize,pr=p->sprvsize,dx=x-ox,dy=y-oy;
        if(magnitude(dx)<=hw+10 && magnitude(dy)<=hh+pr+16){
            contact_bottom=magnitude(dx)<hw+8 && p->yspeed.w<0 && old_y-pr>=oy+hh-8 && y-pr<=oy+hh;
            /* RIDECHK.C hitchk -> hit_v -> hit_y (Object Solid.asm SolidObject):
               the box is (half width + 10) x (half heights + 2); the smaller
               penetration picks the axis; from above with yspeed >= 0 the player
               is placed on top (y = oy - half heights) before ride_on_set. */
            contact_top=0;
            {
                int w=hw+10,h=hh+pr+2,hx=dx+w,hy=dy+h;
                if(hx>=0 && hx<2*w && hy>=0 && hy<2*h && (!(s->flags&2) || (s->subtype&8))){
                    int d4=hx<=w?hx:2*w-hx,d5=hy<=h?hy:2*h-hy;
                    if(d5<d4 && hy<=h && (p->yspeed.w>=0 || p->mstno.b.h==43))contact_top=1;
                }
            }
            /* RIDECHK.C hitchk/hit_v/hit_x: a grounded player pushing into the
               side band (half width + 10) sets the push flag, also flush
               against a wall; springs ignore side hits in the air. */
            int width=hw+10,height=hh+pr+2,hx=dx+width,hy=dy+height,side=0;
            if(hx>=0 && hx<2*width && hy>=0 && hy<2*height && !(p->cddat&2)){
                int sx=width<hx?hx-2*width:hx,ex=width<hx?-sx:hx,ey=height<hy?2*height-hy:hy;
                /* hit_v chooses hit_x (ey>=ex); hit_x needs ey>=5, then hit_set
                   (actno 10: colino=0), x -= iHitXs and push_set/push_clr. */
                if(ey>=ex && ey>=5){
                    side=sx>=0?p->xspeed.w>0:p->xspeed.w<0;
                    p->colino=0;p->xposi.w.h-=sx;
                    if(side){p->cddat|=32;p->mspeed.w=0;p->xspeed.w=0;}
                    else p->cddat&=~32;
                }
            }
            o->cddat=(o->cddat&~32)|(side?32:0);
            /* ObjSpring_Main_Side/Down use SolidObject, so Sonic can stand on
               the top in every zone; only the launch faces sideways or down
               (retail CC2D stands on the side spring at 2216,976). */
            if((s->subtype&4) && contact_top){
                p->yposi.w.h=oy-hh-pr;
                frip_stand(i);
            }
            if(!s->cooldown){
                unsigned before=o->r_no0;
                if(s->subtype&4){if(side)sdushmove(o);}
                else if(s->subtype&8){
                    /* SPRING.C sjump3move's ride_on_chk_s: RIDECHK hit_yu
                       (RIDECHK.C:558-616, every round) moves the player out
                       below a flipped spring (actflg bit 1) before the launch
                       (retail R82A $208CCC, MM2A row 5762: 806 -> 808, then -8;
                       retail CC1A row 3642: 553 -> 561, then -8). */
                    if((s->flags&2) && !contact_top){
                        int w=hw+10,h=hh+pr+2,hx=dx+w,hy=dy+h;
                        if(hx>=0 && hx<2*w && hy>h && hy<2*h && 2*h-hy<(hx<=w?hx:2*w-hx)){
                            p->yposi.w.h-=(short)(hy-2*h);p->yspeed.w=0;contact_bottom=1;
                        }
                    }
                    if(side || contact_top || ((s->flags&2) && contact_bottom)){
                    /* ObjSpring_Main_Diag runs the same SolidObject as the up
                       spring: a landing from above stands Sonic on the top
                       (unroll, ground speed from X speed) before the launch. */
                    if(contact_top){p->yposi.w.h=oy-hh-pr;frip_stand(i);}
                    contact_top=1;sjump3move(o);}}
                else if(s->flags&2){
                    /* ObjSpring_Main_Down: BtmSolidObject (Object Solid.asm
                       SolidObject, oSolidType 2) hits from below when the
                       vertical overlap is the smaller one; .HitBottom moves
                       the player out below the box (oY -= d2, d2 < 0) and
                       clears oYVel before .Action's subq.w #8 and launch. */
                    int w=hw+10,h=hh+pr+2,hx=dx+w,hy=dy+h;
                    if(hx>=0 && hx<2*w && hy>h && hy<2*h && 2*h-hy<(hx<=w?hx:2*w-hx)){
                        contact_bottom=1;
                        p->yposi.w.h-=(short)(hy-2*h);p->yspeed.w=0;
                        sjump2move(o);
                    }
                }
                else if(contact_top){
                    /* RIDECHK.C hitchk calls ride_on_set before SPRING.C
                       sjumpmove. It clears the rolling flag and restores the
                       standing radius, even when the spring launches Sonic
                       in the same update. A spin tag later in the actor list
                       can then select the rolling pose again. */
                    p->yposi.w.h=oy-hh-pr;
                    frip_stand(i);sjumpmove(o);
                }
                /* Spring/Main.asm: the launch sets routine 4; Ani_Spring shows 10
                   frames then $FC (11 updates), ObjSpring_Reset_Up runs on the
                   12th and the Main routine can launch again on the 13th. */
                if(o->r_no0!=before){s->cooldown=13;stats.springs++;o->r_no0=0;p->actfree[18]=0;}
            }
        }
    }
    /* Object Solid.asm SolidObject compares horizontal and vertical edge
       distances. A tie takes the horizontal path and drops an existing ride.
       A new landing only runs SolidObject once, so keep its fresh ride until
       the spring's next update. WW1B reaches the tie at Sonic X=856. The
       distances are the ones SolidObject saw on entry, not after this
       update's re-stand: retail CC2D row 6003 (R32D $2091D0 -> $208AB8) keeps
       Sonic at X=6664 because a trapdoor earlier in the slot order had just
       set him on the floor one pixel higher (vertical 1 < horizontal 2). */
    if((s->subtype&4) && carried && (p->cddat&8) && p->actfree[19]==i+1){
        int width=o->sprhsize+10,height=o->sprvsize+p->sprvsize+2;
        int hx=entry_x-o->xposi.w.h+width;
        int hy=entry_y-o->yposi.w.h+height;
        /* A rising player above the spring takes SolidObject's .GetOff too
           (PlayerAbove with oYVel < 0); R51A jumps off the start spring. */
        if(hx<0 || hx>=2*width || hy<0 || hy>=2*height ||
           (hy<=height?hy:2*height-hy)>=(hx<=width?hx:2*width-hx) ||
           (hy<=height && p->yspeed.w<0 && p->mstno.b.h!=43))
            frip_release(i);
    }
attached_position:
    /* SPRING.C:404 actionsub sets the on-screen bit for the next update. */
    o->actflg=(o->actflg&~128)|(draw_onscreen(o)?128:0);
    if(s->parent){
        sprite_status *parent=&actwk[s->parent];
        int dx=cc_trap_parent(pool[s->parent-1].type)?(int8_t)o->actfree[14]:0;
        int dy=cc_trap_parent(pool[s->parent-1].type)?(int8_t)o->actfree[15]:-16;
        o->xposi.w.h=parent->xposi.w.h+dx;o->yposi.w.h=parent->yposi.w.h+dy;
    }else if(objects_zone==3 && s->origin==65535){
        /* SPRING.C:406-412: a spring linked by DAI_RD5.C banesetsub (word 28,
           offsets in bytes 60/61) re-seats itself on its platform after its own
           move, so it collides where the platform was one update earlier
           (retail QQ1BA 617: the launch waits for the spring, not the platform). */
        unsigned link=scd_word_get(o,28);
        if(link && link<=SCD_OBJECT_CAPACITY && actwk[link].actno==SCD_OBJ_DAIR5){
            o->xposi.w.h=(short)(actwk[link].xposi.w.h+(signed char)o->actfree[14]);
            o->yposi.w.h=(short)(actwk[link].yposi.w.h+(signed char)o->actfree[15]);
        }
    }
}

/* Spinning Disc and Sonic's oVar2B/oVar39 rotation bytes. */
static void disc_step(unsigned i){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1],*p=&actwk[0];
    s->frame=s->phase/2;s->phase=(s->phase+1)%6;
    if(static_solid(i)!=1)return;
    if(!(p->actfree[2]&1)){
        p->mstno.b.h=45;p->actfree[1]=p->xposi.w.h<o->xposi.w.h?128:0;
        p->actfree[15]=magnitude(p->xposi.w.h-o->xposi.w.h);
    }
    p->actfree[2]|=1;control_actor=i+1;
    p->actfree[1]+=8;
    short sn,cs;sinset(p->actfree[1],&sn,&cs);
    /* The source logical long shift has the same low word as this signed
       product shift, including negative cosine positions. Keep X fraction. */
    p->xposi.w.h=o->xposi.w.h+((cs*(int)p->actfree[15])>>8);
    static const uint8_t poses[]={0,0,0,1,1,2,2,2,3,3,3,4,4,5,5,5};
    p->patcnt=poses[p->actfree[1]>>4];
    if(!(p->actfree[1]&63))p->actfree[15]++;
    int left=p->xposi.w.h<o->xposi.w.h;
    unsigned outward=left?SCD_LEFT:SCD_RIGHT,inward=left?SCD_RIGHT:SCD_LEFT;
    if(swdata.b.h&outward)p->actfree[15]++;
    else if((swdata.b.h&inward) && p->actfree[15])p->actfree[15]--;
    if(!(swdata.b.l&SCD_JUMP))return;
    p->actfree[2]=0;control_actor=0;
    sinset((uint8_t)(p->direc.b.h-64),&sn,&cs);
    int impulse=(o->cddat&64)?896:1664;
    p->xspeed.w+=(cs*impulse)>>8;p->yspeed.w+=(sn*impulse)>>8;
    p->cddat=(p->cddat|2)&~32;p->actfree[18]=1;p->actfree[14]=0;soundset(160);
    p->sprvsize=19;p->sprhs=9;
    if(!(p->cddat&4)){p->sprvsize=14;p->sprhs=7;p->yposi.w.h+=5;p->cddat|=4;p->mstno.b.h=2;}
    else p->cddat|=16;
}

/* PPZ Tunnel Path: the high byte of the source step word is a signed
 * countdown. Segment snaps replace coordinate words, retaining fractions. */
static void tunnel_speed(slot *s){
    sprite_status *p=&actwk[0];const int16_t *target=tunnel_paths[s->subtype&127][s->phase];
    int dx=target[0]-p->xposi.w.h,dy=target[1]-p->yposi.w.h;
    int speed=p->mspeed.w,duration;
    if(magnitude(dy)>=magnitude(dx)){
        p->yspeed.w=dy<0?-speed:speed;duration=dy*65536/p->yspeed.w;
        p->xspeed.w=dx?dx*65536/duration:0;
    }else{
        p->xspeed.w=dx<0?-speed:speed;duration=dx*65536/p->xspeed.w;
        p->yspeed.w=dy?dy*65536/duration:0;
    }
    s->timer=duration;
}
static void tunnel_step(unsigned i){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1],*p=&actwk[0];
    if(p->r_no0>=6){
        /* Native bounded-pool lifecycle: do not leave ownership on a dead or
           replaced actor. Original tunnel routines stop updating on death. */
        if(control_actor==i+1){p->actfree[2]&=~0xC1;control_actor=0;s->state=0;}
        return;
    }
    if(p->mstno.b.h==43)return;
    if(!s->state){
        int dx=p->xposi.w.h-o->xposi.w.h,dy=p->yposi.w.h-o->yposi.w.h;
        if(dx < -16 || dx>=16 || dy < -16 || dy>=16 || p->actfree[2])return;
        if(p->r_no0==4){p->r_no0=2;scd_word_set(p,26,120);}
        if(p->cddat&8)release_rider(p->actfree[19]);
        control_actor=i+1;p->actfree[2]=o->userflag.b.l?0xC1:0x81;
        p->mstno.b.h=2;p->mspeed.w=4096;p->xspeed.w=p->yspeed.w=0;
        o->cddat&=~32;p->cddat=(p->cddat&~32)|2;p->actfree[18]=0;
        p->xposi.w.h=o->xposi.w.h;p->yposi.w.h=o->yposi.w.h;
        s->phase=0;s->state=1;soundset(145);return;
    }
    if(s->state==1){tunnel_speed(s);s->state=2;soundset(145);return;}
    unsigned step=((s->timer>>8)-1)&255;s->timer=(step<<8)|(s->timer&255);
    if(step<128){p->xposi.l+=(int)p->xspeed.w*256;p->yposi.l+=(int)p->yspeed.w*256;return;}
    const int16_t *target=tunnel_paths[s->subtype&127][s->phase];
    p->xposi.w.h=target[0];p->yposi.w.h=target[1];
    if(++s->phase<tunnel_lengths[s->subtype&127]){tunnel_speed(s);return;}
    p->yposi.w.h&=2047;p->actfree[2]=0;control_actor=0;s->state=0;
}

/* PPZ projector and animal routines. Each child owns a validated actor index;
   normal animals remain dormant in Present/Past until this act's flag is set. */
static int projector_parent(const slot *s){
    unsigned type=(s->type==SCD_OBJ_FRIEND3 || s->type==SCD_OBJ_MOVIE3)?SCD_OBJ_MOVIE3:SCD_OBJ_PROJECTOR;
    return s->parent && s->parent<=SCD_OBJECT_CAPACITY && pool[s->parent-1].type==type && !pool[s->parent-1].subtype && pool[s->parent-1].state<3;
}
static void animal_flip(slot *s,sprite_status *o){o->actflg^=1;o->cddat^=1;s->flags=o->actflg&3;}
static void projector_animate(slot *s,sprite_status *o,unsigned animation){
    if(o->pattim){o->pattim--;return;}
    const uint8_t *script=projector_animations[animation];
    o->pattim=s->type==SCD_OBJ_FRIEND3 && animation==2?3:script[0];
    if(script[1+o->patcnt]==255)o->patcnt=0;
    s->frame=script[1+o->patcnt++];
    if(s->type==SCD_OBJ_FRIEND3 && animation==4 && s->frame==5)s->frame=4;
    o->patno=s->frame;s->flags=o->cddat&3;o->actflg=(o->actflg&~3)|s->flags;
}
static void animal_step(unsigned i){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1];unsigned hologram=s->subtype&128,ground=s->subtype&127;
    s->sink=0;
    if(!hologram){
        if(current_era<2){if(!projector_destroyed)return;}
        else if(!good_future){remove_slot(i);return;}
    }
    if(!s->state){
        s->state=hologram?2:1;o->actflg=4;s->flags=0;
        if(s->type==SCD_OBJ_FRIEND3){
            o->r_no0=ground?(hologram?8:2):(hologram?4:2);
            o->sprvsize=ground?12:8;
        }
        if(!ground){animal_flip(s,o);if(!hologram){o->direc.b.h=1;o->direc.b.l=1;}}
        else if(hologram)animal_flip(s,o);
        else{s->debris_vx=65536;s->debris_vy=-262144;}
        return;
    }
    if(hologram && !projector_parent(s)){remove_slot(i);return;}
    if(!ground){
        short sn,cs;sinset(o->direc.b.h,&sn,&cs);
        o->xposi.w.h=s->home_x+(cs>>(hologram?3:1));o->yposi.w.h=s->home_y+(sn>>(hologram?4:1));
        if(hologram){
            o->direc.b.h+=4;
            if(!(o->direc.b.h&127)){animal_flip(s,o);return;}
        }else{
            unsigned candidate=(o->direc.b.h+(int8_t)o->direc.b.l)&255;
            if(((candidate-1)&255)<127)o->direc.b.h=candidate;
            else{o->direc.b.l=-(int8_t)o->direc.b.l;animal_flip(s,o);}
        }
        projector_animate(s,o,hologram?3:2);
    }else if(hologram)projector_animate(s,o,4);
    else{
        if(s->type==SCD_OBJ_FRIEND3 && s->phase==2){
            s->phase=0;o->r_no0=2;s->debris_vx=-s->debris_vx;
            animal_flip(s,o);s->sink=1;return;
        }
        o->xposi.l+=s->debris_vx;o->yposi.l+=s->debris_vy;s->debris_vy+=8192;
        s->frame=s->debris_vy<0?0:1;o->patno=s->frame;
        short floor=emycol_d(o);
        if(floor<0){
            o->yposi.w.h+=floor;s->debris_vy=-262144;
            if(s->type==SCD_OBJ_FRIEND3){s->phase++;o->r_no0+=2;}
            else{s->debris_vx=-s->debris_vx;animal_flip(s,o);}
        }
    }
    s->sink=1;
}
static void projector_step(unsigned i){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1],*p=&actwk[0];
    if(s->subtype){
        if(!projector_parent(s)){remove_slot(i);return;}
        s->state=s->sink=1;projector_animate(s,o,s->subtype&128?0:1);return;
    }
    if(!s->state){
        if(projector_destroyed){remove_slot(i);return;}
        static const int16_t children[4][4]={{46,-21,-7,255},{46,-88,-4,1},{36,-88,-24,128},{36,-100,4,129}};
        s->state=s->sink=1;
        for(unsigned n=0;n<4;n++){
            const int16_t *c=children[n];unsigned cc=s->type==SCD_OBJ_MOVIE3;
            unsigned type=cc?(n<2?SCD_OBJ_MOVIE3:SCD_OBJ_FRIEND3):(unsigned)c[0];
            int x=o->xposi.w.h+c[1]+(cc && n==3?2:0);
            int y=o->yposi.w.h+c[2]-(cc && n==3?4:0);
            int child=scd_objects_spawn(type,x,y,c[3],0);
            if(child<0){if(s->origin!=65535)deferred_reload[s->origin]=1;remove_slot(i);return;}
            pool[child].parent=i+1;
        }
        /* Sonic's earlier collision pass cannot hit an uninitialized actor. */
        static_solid(i);return;
    }
    if(s->state==1){
        int radius=p->sprvsize-3,cy=p->yposi.w.h;
        if(p->patno==0x39){cy+=22-radius;radius=10;}
        int dx=p->xposi.w.h-o->xposi.w.h,dy=cy-o->yposi.w.h;
        if(!debugflag.w && p->r_no0<4 && !(p->actfree[2]&128) && p->mstno.b.h==2 && (o->actflg&128) && dx>=-26 && dx<=26 && dy>=-17-radius && dy<=17+radius){s->state=2;stats.projector_hits++;}
        static_solid(i);return;
    }
    if(s->state==2){
        s->state=3;s->frame=1;o->patno=1;
        static_solid(i);release_rider(i+1);
        if(o->cddat&32){o->cddat&=~32;p->cddat&=~32;}
    }
    if(s->state==3){
        if(s->phase==12){s->state=4;s->timer=60;return;}
        const int16_t *event=projector_explosions[s->phase];
        if(++s->timer!=(unsigned)event[0])return;
        s->phase++;
        int child=scd_objects_spawn(SCD_OBJ_EXPLOSION,o->xposi.w.h+event[1],o->yposi.w.h+event[2],2,0);
        if(child>=0){stats.projector_explosions++;soundset(158);}
        return;
    }
    if(!--s->timer){projector_destroyed=1;remove_slot(i);}
}

#include "amy_actor.inc"

/* Palmtree Panic/Objects/Springboard/Main.asm. state holds oRoutine (2/4 main, 6/8
   ridden, 10/12 fling), phase the animation, timer oSprBrdFling. */
static int springboard_touch(const sprite_status *o,const sprite_status *p,unsigned box){
    static const int8_t boxes[8][4]={{16,-16,16,-16},{16,-16,4,-4},{9,-9,56,16},{0,-24,4,-4},{0,-24,12,0},{24,0,4,-4},{24,0,12,0},{32,-32,32,-32}};
    if(p->r_no0>=6 || p->yspeed.w<0)return 0;
    const int8_t *b=boxes[box&7];int px=p->xposi.w.h,py=p->yposi.w.h,ox=o->xposi.w.h,oy=o->yposi.w.h;
    int xr=(signed char)p->sprhs,yr=(signed char)p->sprvsize;
    if(px-xr>=ox+b[0] || ox+b[1]>=px+xr || py-yr>=oy+b[2] || oy+b[3]>=py+yr)return 0;
    return 1;
}
static void springboard_step(unsigned i){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1],*p=&actwk[0];
    static const uint8_t scripts[5][16]={{2,0,1,0,2,0,1,0,3,4,3,5,3,4,3,255},{2,0,1,0,2,0,1,0,255},{2,3,4,3,5,3,4,3,255},{0,0,255},{0,3,255}};
    unsigned flipped=s->state==4 || s->state==8 || s->state==12;
    int touched;
    switch(s->state){
    case 2: case 4:
        touched=springboard_touch(o,p,flipped?3:5);o->cddat=(o->cddat&~8)|(touched?8:0);
        if(touched){p->yposi.l=o->yposi.l-((int32_t)(signed char)p->sprvsize<<16);s->state=flipped?12:10;s->phase=flipped?4:3;}
        break;
    case 6: case 8:
        touched=springboard_touch(o,p,flipped?3:5);o->cddat=(o->cddat&~8)|(touched?8:0);
        if(!touched){s->state=flipped?4:2;if(p->cddat&2)s->state=flipped?12:10;if(s->state>=10)s->timer=0x40;}
        break;
    case 10: case 12:
        s->phase=flipped?2:1;
        touched=springboard_touch(o,p,flipped?4:6);o->cddat=(o->cddat&~8)|(touched?8:0);
        if(touched){
            int v=p->yspeed.w+256;if(v>=2560)v=2560;
            p->yspeed.w=-v;s->timer=0x40;
            if(p->cddat&2)p->actfree[18]=0;p->cddat|=2;
            p->cddat&=~32;p->actfree[14]=0;p->sprvsize=19;p->sprhs=9;
            if(!(p->cddat&4)){p->sprvsize=14;p->sprhs=7;p->yposi.w.h+=5;p->cddat|=4;p->mstno.b.h=2;}
            else p->cddat|=16;
        }
        /* oSprBrdFling is a byte: from its initial 0 the first fling lasts 256 updates. */
        s->timer=(uint8_t)(s->timer-1);
        if(!s->timer){s->timer=0x40;s->state=flipped?4:2;s->phase=flipped?4:3;}
        break;
    }
    /* AnimateObject: first byte is the frame duration, $FF restarts the script. */
    const uint8_t *script=scripts[s->phase<5?s->phase:0];
    if(s->age==1 || s->sink!=s->phase){s->sink=s->phase;o->patcnt=0;o->pattim=0;}
    if(o->pattim){o->pattim--;}
    else{o->pattim=script[0];if(script[1+o->patcnt]==255)o->patcnt=0;s->frame=script[1+o->patcnt++];}
}

/* BRANKO1.C: a pivot (radius 0) and subtype&15 pieces at 16-pixel radii swing
 * on one angle word; speed changes by accel until it equals area1, then back to
 * area2. The farthest piece is the platform and carries the player (ridechk
 * with height 8, then 12, then 2 pixels lower). Pieces follow the pivot's
 * angle; the pivot owns the state (timer angle, debris_vx speed, sink turn). */
static void swing_place(unsigned piece,unsigned angle,int x,int y,unsigned radius){
    short sn,cs;sinset(angle>>8,&sn,&cs);
    short r=(short)(signed char)radius<<4;
    unsigned int ls=(unsigned int)(sn*r),lc=(unsigned int)(cs*r);
    sprite_status *o=&actwk[piece+1];
    o->yposi.w.h=(short)((short)((int)lc>>4)>>4)+y;o->xposi.w.h=(short)((short)((int)ls>>4)>>4)+x;
}
static void swing_step(unsigned i){
    slot *s=&pool[i];
    if(s->parent){if(s->parent>SCD_OBJECT_CAPACITY || pool[s->parent-1].type!=SCD_OBJ_SWING)remove_slot(i);return;}
    static const int16_t table[8][4]={{-16384,8,512,-512},{-16384,2,256,-256},{-16384,-2,-256,256},{-24576,3,384,-384},{-32768,-2,-256,256},{-32768,2,256,-256},{-32768,-1,-256,0},{-32768,1,256,0}};
    const int16_t *t=table[(s->subtype&112)>>4];unsigned count=s->subtype&15;
    if(!s->state){
        s->state=1;s->timer=(uint16_t)t[0];s->debris_vx=0;s->sink=0;
        for(unsigned k=count;k>0;k--){
            int c=scd_objects_spawn(SCD_OBJ_SWING,s->home_x,s->home_y,s->subtype,s->flags);if(c<0)break;
            pool[c].parent=i+1;pool[c].phase=k;pool[c].frame=k==count?1:2;pool[c].state=1;
        }
    }
    int16_t speed=(int16_t)s->debris_vx;
    if(!s->sink){speed+=t[1];s->timer+=speed;if(t[2]==speed)s->sink=255;}
    else{speed-=t[1];s->timer+=speed;if(t[3]==speed)s->sink=0;}
    s->debris_vx=speed;
    swing_place(i,s->timer,s->home_x,s->home_y,0);
    for(unsigned c=0;c<SCD_OBJECT_CAPACITY;c++)if(pool[c].type==SCD_OBJ_SWING && pool[c].parent==i+1){
        sprite_status *o=&actwk[c+1],*p=&actwk[0];int32_t x=o->xposi.l,y=o->yposi.l;
        swing_place(c,s->timer,s->home_x,s->home_y,pool[c].phase);
        if(pool[c].phase!=count)continue;
        o->xspeed.w=(o->xposi.l-x)>>8;o->yspeed.w=(o->yposi.l-y)>>8;
        o->sprvsize=8;int riding=top_solid(c);
        if(!riding){o->sprvsize=12;riding=top_solid(c);}
        o->sprvsize=8;
        if(riding && o->yposi.w.h>=p->yposi.w.h)p->yposi.w.h=o->yposi.w.h-o->sprvsize-p->sprvsize+2;
    }
}

/* Object Animate.asm AnimateObject; returns 1 when a $FC flag advances the routine. */
static int animate(slot *s,const uint8_t *script){
    if(s->anim!=s->prev_anim){s->prev_anim=s->anim;s->anim_frame=0;s->anim_time=0;}
    if((int8_t)--s->anim_time>=0)return 0;
    s->anim_time=script[0];
    uint8_t value=script[1+s->anim_frame];
    if(value==252)return 1;
    if(value==255){s->anim_frame=0;value=script[1];}
    s->frame=value&31;s->anim_frame++;return 0;
}
/* Level End/Main.asm ObjCapsule: a rolling hit stops the clock and bounces Sonic;
   120 updates of explosions follow, then the level palette, seven seeds and the
   results 60 updates later. Seeds fall with gravity and become flowers. */
static void capsule_step(unsigned i){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1],*p=&actwk[0];
    static const uint8_t idle[]={1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,1,0,0,1,255};
    static const uint8_t seed[]={2,3,4,5,6,7,8,255};
    if(s->state==10){
        s->anim=1;animate(s,seed);
        int vy=o->yspeed.w;o->xposi.l+=(int)o->xspeed.w*256;o->yspeed.w+=56;
        if(o->yspeed.w>=0x1000)o->yspeed.w=0x1000;
        o->yposi.l+=vy*256;
        if(emycol_d(o)<0){s->type=SCD_OBJ_FLOWER;s->subtype=1;s->state=0;s->anim=s->prev_anim=s->anim_frame=s->anim_time=0;}
        return;
    }
    if(s->state==2){
        animate(s,idle);
        int d1=p->sprhs+32,d0=p->xposi.w.h-o->xposi.w.h+d1;
        if(!(p->cddat&4) || d0<0 || d0>=2*d1)return;
        int e1=p->sprvsize+28,e0=p->yposi.w.h-o->yposi.w.h+e1;
        if(e0<0 || e0>=2*e1)return;
        scd_player_stop_clock();s->frame=2;s->timer=120;s->state=4;
        if(s->origin!=65535)consumed[s->origin]=1;
        p->yspeed.w=(int16_t)(-p->yspeed.w)>>2;
        return;
    }
    if(s->state==4){
        uint8_t t=(uint8_t)(s->timer-1);s->timer=t;
        if((int8_t)t<0){
            static const int16_t velocity[7]={0,-128,128,-256,256,-384,384};
            scd_boss_palette_set(SCD_BOSS_PALETTE_LEVEL);
            /* The seven seeds are created without an intervening dispatch.
               Each uses the next free pool slot, so continue the FindObjSlot
               scan after the slot just assigned. */
            unsigned first=0;
            for(unsigned k=0;k<7;k++){
                int c=spawn_from(SCD_OBJ_CAPSULE,o->xposi.w.h,o->yposi.w.h,1,0,first);if(c<0)break;
                first=(unsigned)c+1;
                pool[c].state=10;actwk[c+1].sprvsize=0;actwk[c+1].yspeed.w=-1536;actwk[c+1].xspeed.w=velocity[k];
            }
            s->state=8;scd_act_capsule(current_era==2);return;
        }
        if(!(t&3)){
            static const int8_t position[8][2]={{0,0},{32,-8},{-32,0},{-24,-8},{24,8},{-16,8},{16,8},{-8,-8}};
            const int8_t *d=position[(t>>2)&7];
            if(scd_objects_spawn(SCD_OBJ_EXPLOSION,o->xposi.w.h+d[0],o->yposi.w.h+d[1],1,0)>=0)soundset(158);
        }
    }
}
/* Level End/Main.asm ObjBigRing (subtype 0) and ObjBigRingFlash (subtype 1). Below 50 rings the
   ring is neither drawn nor touched. A touch sets specialStage, moves Sonic to the view X + 336,
   stops him, locks the controls to Right and spawns the flash, which deletes itself at $FC. */
static void big_ring_step(unsigned i){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1],*p=&actwk[0];
    static const uint8_t spin[]={7,0,1,2,3,255},flash[]={2,0,1,2,3,4,5,6,7,252};
    if(s->subtype){if(animate(s,flash))remove_slot(i);return;}
    /* Level End/Main.asm:352-360 ObjBigRing_Init deletes the ring only once
       all seven stones are held (timeStones == %1111111) or in time attack. */
    if(time_stones==0x7f || scd_ta.mode){if(s->origin!=65535)consumed[s->origin]=1;remove_slot(i);return;}
    if(plring<50)return;
    if(s->state!=4){
        int d1=p->sprhs+16,d0=p->xposi.w.h-o->xposi.w.h+d1,e1=p->sprvsize+32,e0=p->yposi.w.h-o->yposi.w.h+e1;
        if(d0>=0 && d0<2*d1 && e0>=0 && e0<2*e1){
            s->state=4;big_ring_touched=big_ring_pending=1;scd_act_special(1);
            p->xposi.w.h=scd_act_view_x()+336;p->xspeed.w=p->mspeed.w=0;
            scd_player_force_right(1);soundset(175);
            scd_objects_spawn(SCD_OBJ_BIG_RING,o->xposi.w.h,o->yposi.w.h,1,0);
        }
    }
    animate(s,spin);
}
/* Level/_Objects/Flower/Main.asm with subtype 1 (no saved flags): seed, planting,
   growing on palette line 1 and the grown loop. */
static void flower_step(unsigned i){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1];
    static const uint8_t scripts[4][6]={{3,0,1,255},{3,2,3,2,3,252},{1,5,5,4,6,252},{19,6,7,255}};
    switch(s->state){
    case 0:o->sprvsize=0;s->anim=0;s->prev_anim=255;s->state=2;return;
    case 2:{
        short d=emycol_d(o);
        if(d<0){o->yposi.w.h+=d;s->state=4;s->anim=1;o->sprvsize=48;}
        else o->yposi.w.h+=2;
        break;
    }
    case 6:s->anim=2;break;
    case 8:s->anim=3;s->state=4;break;
    default:break;
    }
    if(animate(s,scripts[s->anim]))s->state+=2;
}
#include "objects_cc_enemy.inc"
#include "objects_drumr3.inc"
#include "objects_mecasnc3.inc"
#include "objects_sikake33.inc"
#include "objects_ga.inc"
#include "objects_tentou.inc"
#include "objects_kama.inc"
#include "objects_banpa.inc"
#include "objects_togeball.inc"
#include "objects_pocket.inc"
#include "objects_cc_generator.inc"
#include "objects_tt_common.inc"
void scd_boss_slot_sync(void);
void scd_boss_slot_sync_one(unsigned child);
#include "objects_tt_enemies.inc"
#include "objects_tt_hazards.inc"
#include "objects_tt_friends.inc"
#include "objects_tt_awa.inc"
#include "objects_tt_ride.inc"
#include "objects_tt_platforms.inc"
#include "objects_tt_wave.inc"
#include "objects_zone_ops.inc"
/* Ring/Main.asm Ani_Ring: four poses, six updates each, then $FC deletes it.
   Collection changes routine before the same frame's object draw. */
static const uint8_t ring_sparkle[]={5,4,5,6,7,252};
static void ring_sparkle_step(unsigned i){
    slot *s=&pool[i];
    /* Tidal Tempest slot timing: $FC sets routine 8 and the ring is deleted on
       the next update (retail TT1C dynamic slot 33: sparkle rows 439-462,
       routine 8 at 463, free at 464; retail QQ3C slot 33: routine 8 at row 245,
       free at 246). Zones on the retail Object Spawner (CC, TT, QQ) model the
       slot, PPZ too (retail PPZ1A slot 33: routine 8 at 478, free at 479). */
    if(s->state==2){remove_slot(i);return;}
    if(animate(s,ring_sparkle)){if(tt_streamed())s->state=2;else remove_slot(i);}
}
static void ring_collect(unsigned i){
    slot *s=&pool[i];
    scd_player_rings(1);stats.collected++;
    if(s->origin!=65535)consumed[s->origin]=1;
    s->state=1;s->anim=1;
    /* ObjRing_Collect advances to sparkle; Ani_Ring first runs on the next
       object update, retaining the collected ring's slot for that tick. */
    /* WW collects through this path too (retail WW1A ring slot 37: sparkle
       from row 8430, routine 8 at 8454, free at 8455). */
    if(objects_zone!=5 && objects_zone!=6)ring_sparkle_step(i);
}
/* COLI3.C pcol (retail R31B $207048) scans the actors in slot order and
   returns after the first one Sonic's box touches. Collision Chaos rings
   ($47, 6x6; pcolitem collects only below flash 90) and round bumpers ($D7,
   8x8; pcolspecial counts the hit) take part in that order (the retail slot
   model): retail CC1B row 8287 takes ring slot 52 and leaves bumper slot 59
   for the next update. Returns 1 when one of them is the first touch, so the
   generated pcol reacts to nothing else this update. */
unsigned scd_boss_retail_slot(unsigned actor);
static int cc_touch_arbitrate(void){
    const sprite_status *p=&actwk[0];
    if(p->actfree[2]&64)return 0;
    unsigned best=0,best_slot=~0u;
    for(unsigned i=0;i<SCD_OBJECT_CAPACITY;i++){
        const slot *s=&pool[i];const sprite_status *o=&actwk[i+1];int hit;
        /* RING.C:417 gives a lost ring the same $47 touch; pcol skips it until
           flyringmove's actionsub has drawn it on screen (actflg bit 7). */
        if((s->type==SCD_OBJ_RING || (s->type==SCD_OBJ_LOST_RING && (o->actflg&128))) && !s->state)hit=retail_touch(p,o->xposi.w.h,o->yposi.w.h,6,6);
        else if(s->type==SCD_OBJ_BOBIN && o->colino && (o->actflg&128))hit=retail_touch(p,o->xposi.w.h,o->yposi.w.h,8,8);
        else continue;
        if(!hit)continue;
        unsigned v=scd_boss_retail_slot(i+1);
        if(v<best_slot){best_slot=v;best=i+1;}
    }
    if(!best)return 0;
    if(pool[best-1].type==SCD_OBJ_RING || pool[best-1].type==SCD_OBJ_LOST_RING){if(scd_word_get(&actwk[0],26)<90)ring_collect(best-1);}
    else actwk[best].colicnt++;
    return 1;
}
/* Level/Main.asm:712 levelVIntCounter. Native counts one per gameplay update
   (the deterministic choice also made for watercnt); a parity harness adds
   retail's lag V-INTs (scd_objects_vint_add). */
/* The retail actor slot (src/boss.c's slot model); a build without it uses the pool order. */
__attribute__((weak)) unsigned scd_boss_retail_slot(unsigned actor){return actor+31u;}
__attribute__((weak)) const uint8_t *scd_boss_retail_slot_map(unsigned actor,unsigned *first_key){*first_key=scd_boss_retail_slot(actor);return NULL;}
/* src/boss.c's slot model: SpawnObjects places new records before RunObjects
   deletes anything, so their retail slots are taken right after stream(). */
__attribute__((weak)) void scd_boss_slot_sync(void){}
__attribute__((weak)) void scd_boss_slot_sync_one(unsigned child){(void)child;scd_boss_slot_sync();}
__attribute__((weak)) void scd_boss_step_begin(void){}
__attribute__((weak)) void scd_boss_step_before(unsigned upper){(void)upper;}
__attribute__((weak)) void scd_boss_slot_transient(void){}
__attribute__((weak)) void scd_boss_slot_transient_end(void){}
__attribute__((weak)) void scd_boss_slot_after(unsigned child,unsigned parent){(void)child;(void)parent;}
__attribute__((weak)) void scd_boss_slot_first(unsigned child){(void)child;}
__attribute__((weak)) unsigned scd_boss_retail_slot_peek(unsigned actor){return actor+31u;}
__attribute__((weak)) void scd_boss_slot_after_next(unsigned child,unsigned parent){(void)child;(void)parent;}
static void lost_ring_step(unsigned i,sprite_status *p){
    slot *s=&pool[i];sprite_status *o=&actwk[i+1];
    if(s->state){ring_sparkle_step(i);return;}
    s->frame=ring_loss_frame;
    if(s->phase && zone_ops && zone_ops->ring_spill)zone_ops->ring_spill(i);
    /* Ring/Main.asm:410-434 ObjLostRing_Main: ObjMove, +$18 gravity; while falling,
       the floor check runs only when (levelVIntCounter + d7) & 3 == 0, d7 being
       RunObjects' countdown (OBJCOUNT-1 - slot, Object Functions.asm:12-31); a
       floor hit adds the distance and reflects yvel less its asr #2. The ring
       goes when the spill timer ends or below bottomBound + $E0. */
    o->xposi.l+=(int)o->xspeed.w*256;o->yposi.l+=(int)o->yspeed.w*256;o->yspeed.w+=24;
    /* RING.C:469-476 flyringmove deletes a lost ring only when the spill timer
       ends or it falls below scralim_down + 224; MM keeps one left of x 0 (retail
       MM1A slot 45 at x -1 until 912). */
    if((o->xposi.w.h<0 && objects_zone!=6) || o->xposi.w.h>=16384 || o->yposi.w.h>=2040 || !mm_spill_timer){remove_slot(i);return;}
    if(o->yspeed.w>=0 && o->yposi.w.h>=0 && !((level_vint+127u-scd_boss_retail_slot(i+1))&3)) {
        short d=emycol_d(o);if(d<0){o->yposi.w.h+=d;o->yspeed.w=-(short)(o->yspeed.w-(o->yspeed.w>>2));}
    }
    if(scralim_down+224<o->yposi.w.h){remove_slot(i);return;}
    /* MM: RING.C:417 colino 71 puts the ring in COLI8.C pcol's slot-order scan
       (mm_enemy_scan); flyringmove's actionsub marks it on screen. */
    if(objects_zone==6){o->actflg=(o->actflg&~128)|(draw_onscreen(o)?128:0);return;}
    /* CC: COLI3.C pcol (cc_touch_arbitrate) collects it before this update's
       move, at the position flyringget then holds (retail CC2C seed 24
       update 3400: the ring stops at 5281,1143 as Sonic touches it). */
    if(objects_zone==1){o->actflg=(o->actflg&~128)|(draw_onscreen(o)?128:0);return;}
    /* QQ: RING.C:417 flyringinit gives the lost ring colino 71 ($47), so COLI5
       pcol (qq_enemy_scan) collects it in slot order, one contact per update
       (retail QQ2A 3111). actflg bit 7 is the scan's on-screen test. */
    if(objects_zone==3){o->actflg=(o->actflg&~128)|(draw_onscreen(o)?128:0);if(qq_ring_touched==i+1)ring_collect(i);return;}
    /* The ring's touch ($47) reaches pcolitem, which collects only while the
       player's flash timer (word 26) is below 90: COLI1-8.C pcolitem. */
    if(scd_word_get(p,26)<90 && p->r_no0<4 && !(p->actfree[2]&128) &&
       magnitude(p->xposi.w.h-o->xposi.w.h)<=14 &&
       magnitude(p->yposi.w.h-o->yposi.w.h)<=p->sprvsize+6){
        ring_collect(i);
    }
}
/* Level/Main.asm:402-403: SpawnObjects runs before RunObjects, so a record the
   window reaches takes its slot before Sonic (plwaterchk's splash, slot 0)
   and his breath master (slot 7) allocate (retail TT1C row 2335: wall1 and
   friend4 in dynamic slots 18-19, the breath bubble in 22). Tidal Tempest
   only; other zones keep stream() inside scd_objects_step. */
static uint8_t stream_early;
void scd_objects_spawn_early(void){
    if(!tt_streamed())return;
    stream(actwk[0].xposi.w.h);if(tt_streamed())tt_card_allocate();stream_early=1;
}
/* R3 bob's block writes clobber RunObjects' d7 on the Sega CD (see
   tools/prepare_playsp3.py): the actors after the player skip that update.
   Placed rings keep their native contact pass, the player's ring touch. */
static int run_aborted;
void scd_objects_abort_run(void){run_aborted=1;}
/* Object Spawner.asm CheckObjDespawn2 -> DespawnObjTimeWarp: once
   SaveTimeWarpData has set timeZone bit 7, every object that ends its update
   in CheckObjDespawn deletes itself there (retail PPZ1C row 5057: the spinning
   discs go, the springs, rings and platforms stay). DeleteObject leaves Sonic's
   status alone: on a deleted disc he stays controlled and standing, frozen. */
static int warp_despawns(const slot *s){
    if(objects_zone!=0)return 0;
    switch(s->type){
    case SCD_OBJ_BOULDER:case SCD_OBJ_CHECKPOINT:case SCD_OBJ_GOAL:case SCD_OBJ_SIGN:case SCD_OBJ_TIMEPOST:
    case SCD_OBJ_GENERATOR:case SCD_OBJ_SPIKES:case SCD_OBJ_DOOR:case SCD_OBJ_SPIN_TAG:case SCD_OBJ_DOOR_V:
    case SCD_OBJ_RAMP:case SCD_OBJ_RAMP_PLANT:case SCD_OBJ_AMY:case SCD_OBJ_ANIMAL:case SCD_OBJ_ANTON:
    case SCD_OBJ_WALL:case SCD_OBJ_COLLAPSE:case SCD_OBJ_LOG_SHADOW:case SCD_OBJ_MOSQUI:case SCD_OBJ_PATABATA:
    case SCD_OBJ_PROJECTOR:case SCD_OBJ_SCENERY:case SCD_OBJ_DISC:case SCD_OBJ_SPRINGBOARD:case SCD_OBJ_TAGATAGA:
    case SCD_OBJ_TAMABBOH:return 1;
    /* Tunnel Path/Main.asm: CheckObjDespawn only while not carrying Sonic. */
    case SCD_OBJ_TUNNEL:return !s->state && actwk[0].r_no0<6 && actwk[0].mstno.b.h!=43;
    default:return 0;
    }
}
/* A touched PPZ badnik hurts Sonic (the else branch of its reaction below). */
static int ppz_touch_hurts(unsigned i){
    return (pool[i].type==SCD_OBJ_TAMABBOH && pool[i].subtype==1) || !(plpower_m || travel_protection || (actwk[0].cddat&4));
}
static void warp_despawn(void){
    sprite_status *p=&actwk[0];
    for(unsigned i=0;i<SCD_OBJECT_CAPACITY;i++)if(pool[i].type && warp_despawns(&pool[i])){
        uint8_t control=p->actfree[2],ride=p->actfree[19],ride_timer=p->actfree[14],cddat=p->cddat;
        remove_slot(i);
        p->actfree[2]=control;p->actfree[19]=ride;p->actfree[14]=ride_timer;p->cddat=cddat;
    }
}

/* MM RunObjects order (retail slot order, src/boss.c slot model). The pass
   loop asks for the live pool actor with the lowest retail key above the last
   one run. A full scan per pass is O(n^2) (17 K FRT ticks in MM1A), so the
   scan's keys are cached as key -> actor and reused while no key can have
   changed: no slot-map change (scd_boss_slot_generation), no new actor
   (stats.spawned and tp_claim_generation), every key a mapped slot, and no synchronization during the
   scan itself. Removed actors are skipped. Otherwise the original scan runs
   unchanged, side effects included. MM_ORDER_CHECK (host) re-runs the
   original selection on every cached pick and aborts on any difference. */
#if !defined(__sh__)
#include <stdio.h>
#endif
/* Weak fallbacks for host tests without src/boss.c, like the boss hooks at the
   top of this file; tools/player_slot_model.c models them for test-player.sh.
   A NULL map never validates the cache. */
__attribute__((weak)) unsigned scd_boss_slot_generation(void){return 0;}
__attribute__((weak)) int scd_boss_retail_slot_pure(unsigned actor){(void)actor;return 0;}
__attribute__((weak)) const uint8_t *scd_boss_retail_slot_view(void){return NULL;}
static uint8_t mm_order_owner[128];static unsigned mm_order_gen,mm_order_spawned,mm_order_claimed;static int mm_order_valid;
static unsigned mm_order_pick(int fresh,unsigned after,unsigned *key){
    unsigned gen=scd_boss_slot_generation();
    if(!fresh && mm_order_valid && gen==mm_order_gen && stats.spawned==mm_order_spawned && tp_claim_generation==mm_order_claimed){
        unsigned i=SCD_OBJECT_CAPACITY,k=after+1;
        for(;k<128;k++){unsigned e=mm_order_owner[k];if(e && pool[e-1].type){i=e-1;break;}}
#if !defined(__sh__)
        {static int check=-1;if(check<0)check=getenv("MM_ORDER_CHECK")!=NULL;
        if(check){
            const uint8_t *view=scd_boss_retail_slot_view();unsigned want=SCD_OBJECT_CAPACITY,wkey=~0u;
            for(unsigned j=0;j<SCD_OBJECT_CAPACITY;j++)if(pool[j].type){
                if(!scd_boss_retail_slot_pure(j+1)){fprintf(stderr,"MM order check: cached pick while actor %u would synchronize (vint %u map %u actno %u type %u gen %u cached %u)\n",j+1,scd_objects_vint(),view[j+1],actwk[j+1].actno,pool[j].type,scd_boss_slot_generation(),mm_order_gen);abort();}
                unsigned kk=view[j+1];if(kk>after && kk<wkey){wkey=kk;want=j;}
            }
            if(want!=i || (i<SCD_OBJECT_CAPACITY && wkey!=k)){fprintf(stderr,"MM order check: vint %u after %u cached %u/%u original %u/%u\n",scd_objects_vint(),after,i,k,want,wkey);abort();}
            static unsigned checked;if(!(++checked%100000))fprintf(stderr,"MM order check: %u cached picks identical\n",checked);
        }}
#endif
        *key=k;return i;
    }
    /* The original selection scan, recording every live actor's key. */
    unsigned best=~0u,i=SCD_OBJECT_CAPACITY;int safe=1;
    memset(mm_order_owner,0,sizeof(mm_order_owner));
    const uint8_t *retail_slots=NULL;int first_lookup=1;
    for(unsigned j=0;j<SCD_OBJECT_CAPACITY;j++)if(pool[j].type){
        unsigned k;
        if(first_lookup){retail_slots=scd_boss_retail_slot_map(j+1,&k);first_lookup=0;gen=scd_boss_slot_generation();}
        else{k=retail_slots?retail_slots[j+1]:0;if(!k)k=scd_boss_retail_slot(j+1);}
        if(k>after && k<best){best=k;i=j;}
        if(!retail_slots || retail_slots[j+1]!=k || k>=128 || mm_order_owner[k])safe=0;
        else mm_order_owner[k]=(uint8_t)(j+1);
    }
    unsigned after_gen=scd_boss_slot_generation();
    mm_order_valid=safe && after_gen==gen;mm_order_gen=after_gen;mm_order_spawned=stats.spawned;mm_order_claimed=tp_claim_generation;
    *key=best;return i;
}

void scd_objects_step(int old_x,int old_y) {
    const int aborted=run_aborted;run_aborted=0;
    level_vint++;
    ZONE_OPS_LOADED(5);
    touch_arbitrate();
    scd_profile_span(0,1);
    sprite_status *p=&actwk[0];
    /* Player Object Collision.asm: Player_ObjCollide calls HurtPlayer from
       Sonic's slot 0, before any later slot runs. A platform below the badnik's
       slot then sees Sonic airborne this update and lets him go (Object
       Solid.asm GetOffObject). Retail PPZ1B row 1169: status 2, not 10. */
    if(touch_owner && ppz_badnik(pool[touch_owner-1].type) && ppz_touch_hurts(touch_owner-1))
        scd_objects_hurt(actwk[touch_owner].xposi.w.h);
    if(!stream_early){stream(p->xposi.w.h);if(tt_streamed())tt_card_allocate();else tt_card_pending=0;}
    scd_boss_slot_sync();
    stream_early=0;
    if(objects_zone==1 && objects_act==1)drum_frame=scd_player_get().frame;
    /* The zone's pre-motion player contact scan: COLI3 (CC) stops at the first enemy
       contact, COLI4 (TT) scans every contact actor. */
    if(zone_ops && zone_ops->scan)zone_ops->scan();
    const int ss_race_order=objects_zone==5 && objects_act==2 && !aborted;
    /* MM: RunObjects runs actors in retail slot order (src/boss.c slot model),
       so a child placed below its creator waits for the next update and two
       solids under the player resolve in the original order (retail MM1A
       5355: the piston in slot 76 runs before the KUZURE8 ledge in 77, which
       then takes Sonic). Boss actors keep their own pass. */
    const int mm_order=objects_zone==6 && !aborted;
    unsigned retail_after=0;
    if(ss_race_order)scd_boss_step_begin();
    for(unsigned pass=0;pass<SCD_OBJECT_CAPACITY;pass++) {
        unsigned i=pass;
        if(mm_order){
            unsigned key;i=mm_order_pick(pass==0,retail_after,&key);
            if(i==SCD_OBJECT_CAPACITY)break;
            retail_after=key;
        }else if(ss_race_order){
            /* MM's guarded key cache preserves this same live retail-order
               scan, including invalidation after spawns and slot changes. */
            unsigned key;i=mm_order_pick(pass==0,retail_after,&key);
            if(i==SCD_OBJECT_CAPACITY)break;
            if(ss_race_order)scd_boss_step_before(key);
            retail_after=key;
        }
        slot *s=&pool[i];if(!s->type || (aborted && s->type!=SCD_OBJ_RING))continue;
        if(tt_streamed()){if(tt_frameout_fast(i))continue;if(tt_ring_pending[i] && tt_ring_group(i))continue;}
        sprite_status *o=&actwk[i+1];s->age++;
        if(s->cooldown)s->cooldown--;
        /* Placed rings have no motion or solidity. Keep their existing contact
           and consumption rules, but do not walk the growing gimmick dispatch
           chain for every ring in a dense scene. Lost rings have their own
           immediate motion/contact path for the same reason. */
        if(s->type==SCD_OBJ_RING){
            if(s->state){ring_sparkle_step(i);continue;}
            if(!scd_player_time_stop())s->frame=ring_anim_frame;
            int ring_visible=o->actflg&128;
            /* PPZ: Player_ObjCollide's touch (6x6, the update's first touched
               object only; Palmtree Panic/Player Object Collision.asm).
               Collision Chaos rings are touched in pcol (cc_touch_arbitrate). */
            if(objects_zone==0 && load_placements){if(touch_owner==i+1)ring_collect(i);}
            /* Tidal Tempest: COLI4.C pcol (tt_enemy_scan) picks the ring. */
            else if(objects_zone==2){if(tt_ring_touched==i+1)ring_collect(i);}
            /* Quartz Quadrant: COLI5.C pcol (qq_enemy_scan) picks the ring. */
            else if(objects_zone==3){if(qq_ring_touched==i+1)ring_collect(i);}
            /* Wacky Workbench: COLI6.C pcol (ww_enemy_scan) picks the ring. */
            else if(objects_zone==4){if(ww_ring_touched==i+1)ring_collect(i);}
            /* Other zones: pcol's box (COLI4.C, retail R42A pcol): Sonic's
               16 x 2(radius-3) rectangle against the ring's 6x6 ($47); retail
               TT2A row 2996 leaves a ring 18 below Sonic (radius 14);
               pcolitem collects only below flash 90. */
            /* Metallic Madness: COLI8.C pcol (mm_enemy_scan) picks the ring. */
            else if(objects_zone!=1 && objects_zone!=5 && objects_zone!=6 && (objects_zone!=4 || ring_visible) && scd_word_get(p,26)<90 && p->r_no0<4 && !(p->actfree[2]&128) &&
               retail_touch(p,o->xposi.w.h,o->yposi.w.h,6,6)){
                ring_collect(i);
            }
            if(objects_zone==2 || objects_zone==3 || objects_zone==4 || objects_zone==5 || objects_zone==6)o->actflg=(o->actflg&~128)|(draw_onscreen(o)?128:0);
            continue;
        }
        if(s->type==SCD_OBJ_LOST_RING){lost_ring_step(i,p);continue;}
        if(s->type==SCD_OBJ_PLAWA){water_pool_run(o);continue;}
        if(s->type==SCD_OBJ_BIG_RING){big_ring_step(i);continue;}
        if(s->type==SCD_OBJ_CAPSULE){capsule_step(i);continue;}
        if(s->type==SCD_OBJ_FLOWER){if(tt_retail_flower(i))tt_flower_step(i);else flower_step(i);continue;}
        if(s->type==SCD_OBJ_SCORE){tt_score_step(i);continue;}
        if(s->type==SCD_OBJ_CARD){
            if(s->phase==PPZ_CHECKPOINT_BALL && (objects_zone==2 || objects_zone==6)){tt_frameout(i,s->home_x);continue;}
            if(s->phase==PPZ_CHECKPOINT_BALL){
                short h=(short)((scd_act_view_x()-128)&-128);
                if((unsigned short)(short)((s->home_x&-128)-h)>640)remove_slot(i);
            }
            continue;
        }
        if(s->type==SCD_OBJ_AMY){amy_step(i);continue;}
        if(s->type==SCD_OBJ_AMY_HEART){amy_heart_step(i);continue;}
        /* Object Time Check.asm CheckAnimalPrescence: in a Future without the
           Good Future the animal deletes itself (DeleteObject keeps the
           record's saved bit, so a saved record never reloads). Its slot was
           held from the spawn, as on the Sega CD. */
        if(s->type==SCD_OBJ_ANIMAL && objects_zone==0 && tt_streamed() && !(s->subtype&128) && current_era>=2 && !good_future){
            if(s->origin<SCD_PLACEMENT_CAPACITY && (active_placements[s->origin].flags&TT_SAVED))consumed[s->origin]=1;
            remove_slot(i);continue;
        }
        if(s->type==SCD_OBJ_ANIMAL || s->type==SCD_OBJ_FRIEND3){animal_step(i);continue;}
        if(s->type==SCD_OBJ_PROJECTOR || s->type==SCD_OBJ_MOVIE3){projector_step(i);continue;}
        if(s->type==SCD_OBJ_SPIN_TAG){spin_tag_step(i);continue;}
        if(s->type==SCD_OBJ_SCENERY || s->type==SCD_OBJ_LOG_SHADOW)continue;
        if(s->type==SCD_OBJ_SPRING){spring_step(i,old_x,old_y);continue;}
        if(s->type==SCD_OBJ_MOVING_SPRING){moving_spring_step(i);continue;}
        if(s->type==SCD_OBJ_DOOR || s->type==SCD_OBJ_DOOR_V){door_step(i);continue;}
        if(s->type==SCD_OBJ_DISC){disc_step(i);continue;}
        if(scd_zone_local(s->type)){if(zone_ops->step)zone_ops->step(i);continue;}
        if(s->type==SCD_OBJ_TUNNEL){tunnel_step(i);continue;}
        if(s->type==SCD_OBJ_SONIC_HOLE){
            int dx=p->xposi.w.h-o->xposi.w.h,dy=p->yposi.w.h-o->yposi.w.h;
            if(!s->state && p->actfree[2] && dx>=-32 && dx<32 && dy>=-32 && dy<32){
                s->state=1;if(s->origin!=65535)consumed[s->origin]=1;soundset(163);
            }
            continue;
        }
        if(s->type==SCD_OBJ_TIMEPOST || s->type==SCD_OBJ_MONITOR_ITEM){
            monitor_step(i);
            if((objects_zone==4 || objects_zone==6) && s->type==SCD_OBJ_TIMEPOST)
                o->actflg=(o->actflg&~128)|(draw_onscreen(o)?128:0);
            continue;
        }
        /* MM: the post (retail actor 22, GOAL.C:551-649 mosugu) runs
           mosug_move0 from mosug_init, so every load of it, the first or one
           the spawner brings back, sets scralim_left = scralim_n_left = the
           camera once the player is past it (retail MM1B 8913: the reloaded
           post at 7488 locks the left bound at 7679 and the bound stops Sonic
           at 7695). */
        if(s->type==SCD_OBJ_GOAL && objects_zone==6){
            if(!s->state){
                const sprite_status *pl=&actwk[0];
                unsigned short dy=(unsigned short)(pl->yposi.w.h-o->yposi.w.h+128);
                if(dy<256 && (unsigned short)o->xposi.w.h<(unsigned short)pl->xposi.w.h){
                    s->state=1;scd_act_goal(o->xposi.w.h,o->yposi.w.h);
                    scralim_left=scralim_n_left=(short)scd_act_view_x();
                }
            }
            continue;
        }
        if(s->type==SCD_OBJ_GOAL){if(!s->state)s->state=scd_act_goal(o->xposi.w.h,o->yposi.w.h);continue;}
        if(s->type==SCD_OBJ_SIGN){if(!s->state)s->state=scd_act_sign(o->xposi.w.h,o->yposi.w.h,good_future);s->frame=s->state?scd_act_sign_frame():0;continue;}
        if(s->type==SCD_OBJ_COLLAPSE){collapse_step(i);continue;}
        if(s->type==SCD_OBJ_WALL){wall_step(i);continue;}
        if(s->type==SCD_OBJ_WALL4 || s->type==SCD_OBJ_WALL7){walls_step(i);continue;}
        if(s->type==SCD_OBJ_KONBEA){if(zone_ops && zone_ops->konbea)zone_ops->konbea(i,0);continue;}
        if(s->type==SCD_OBJ_SPIKES){spike_step(i);continue;}
        if(s->type==SCD_OBJ_PISTON){piston_step(i);continue;}
        if(s->type==SCD_OBJ_BOBIN){bobin_step(i);continue;}
        if(s->type==SCD_OBJ_FRIP){frip_step(i);continue;}
        /* Collision Chaos (72-93) and Tidal Tempest (94-135, SCREW_F 65) actors run from
           their zone overlays (src/zone_r3_names.h, zone_r4_names.h), through the zone's
           ops. The ranges stay contiguous, so dense PPZ scenes skip them in one test. */
        if(s->type==SCD_OBJ_SCREW_F || s->type>=SCD_OBJ_FOR3){
            if(zone_ops && zone_ops->actor)zone_ops->actor(i);
            continue;
        }
        if(s->type==SCD_OBJ_CHECKPOINT){checkpoint_step(i);continue;}
        if(s->type==SCD_OBJ_FLOAT_BLOCK){float_step(i);continue;}
        /* _Objects/Boulder/Main.asm ObjBoulder_Main: SolidObject. */
        if(s->type==SCD_OBJ_BOULDER){static_solid(i);continue;}
        if(s->type==SCD_OBJ_PLATFORM){platform_step(i);continue;}
        if(s->type==SCD_OBJ_SWING){swing_step(i);continue;}
        if(s->type==SCD_OBJ_SPRINGBOARD){springboard_step(i);continue;}
        if(s->type==SCD_OBJ_RAMP || s->type==SCD_OBJ_RAMP_PLANT){ramp_step(i);continue;}
        if(s->type==SCD_OBJ_DAIR5){
            dair5_step(i);
            /* R5/DAI_RD5.C:128-129 actionsub (on-screen bit) and frameout_s00
               on the home X: QQ1A respawns the platform each time the camera
               window drops it (R51A row 1168). */
            if(objects_zone==3 && pool[i].type==SCD_OBJ_DAIR5){cc_object_draw(&actwk[i+1]);tp_frameout_s00(&actwk[i+1],(short)pool[i].home_x);}
            continue;
        }
        if(tt_bakuha_type(i)){tt_bakuha_step(i);continue;}
        if(s->type==SCD_OBJ_EXPLOSION && s->subtype==2){
            static const uint8_t frames[]={0,5,6,3,4};
            if(s->age>=22)remove_slot(i);else s->frame=frames[s->age>20?4:(s->age-1)/4];continue;
        }
        if(s->type==SCD_OBJ_EXPLOSION && s->subtype==4){cc_bomb_explosion_step(i);if(o->actno)cc_object_draw(o);continue;}
        if(s->type==SCD_OBJ_EXPLOSION && s->subtype==3){cc_bomb_explosion_step(i);continue;}
        if(s->type==SCD_OBJ_EXPLOSION){
            /* ObjExplosion_Init clears oColType in this same actor update.
               A badnik converted in place keeps its old collision number. */
            /* Ani_Explosion's $FC sets ObjExplosion_Done, which runs on the next
               update (retail QQ3C slot 33: rows 506-526, free at 527; PPZ1A slot 34:
               flower at update 507). A PPZ badnik's explosion becomes a flower. */
            o->colino=0;if(s->age<=20)s->frame=s->state?"\0\5\6\3\4"[(s->age-1)/4]:(s->age-1)/4;
            if(s->age>(tt_streamed()?21u:20u)){
                if(s->phase==PPZ_BADNIK_BOOM){s->type=SCD_OBJ_FLOWER;s->subtype=1;s->state=0;s->phase=0;s->anim=s->prev_anim=s->anim_frame=s->anim_time=0;s->frame=0;o->actno=SCD_OBJ_FLOWER;}
                else remove_slot(i);
            }
            continue;
        }
        if(s->type==SCD_OBJ_GENERATOR){
            if(good_future){s->frame=current_era==1?1:0;o->yposi.w.h=s->home_y;}
            else if(current_era==1){o->yposi.w.h=s->home_y-16+(int)((s->age/8)%8<4?(s->age/8)%4:4-(s->age/8)%4);s->frame=3+(s->age/4)%4;}
        }
        /* PPZ badniks: Sonic's Player_ObjCollide runs in slot 0 before the
           badnik's own routine, so the touch sees its previous state. */
        int pre_x=o->xposi.w.h,pre_y=o->yposi.w.h;unsigned pre_state=s->state;
        if(enemy(s->type)){if(enemy_step(i))continue;}
        if(p->r_no0>=4 || (p->actfree[2]&128))continue;
        int x=p->xposi.w.h,y=p->yposi.w.h,ox=o->xposi.w.h,oy=o->yposi.w.h;
        int hw=o->sprhsize,hh=o->sprvsize,pr=p->sprvsize;
        int dx=x-ox,dy=y-oy;
        if(!ppz_badnik(s->type) && (magnitude(dx)>hw+9 || magnitude(dy)>hh+pr+16))continue;
        if(s->type==SCD_OBJ_GENERATOR && current_era==1 && !good_future && (p->cddat&4) && magnitude(dx)<42 && magnitude(dy)<32+pr) {
            good_future=pending_generator=1;scd_player_points(1500);s->frame=1;soundset(158);
            for(int d=-24;d<=24;d+=24)scd_objects_spawn(SCD_OBJ_EXPLOSION,ox+d,oy,0,0);
            if(p->yspeed.w>0)p->yspeed.w=-p->yspeed.w;
            continue;
        }
        if(s->type==SCD_OBJ_GENERATOR && (current_era!=1 || good_future))continue;
        if(enemy(s->type)) {
            if(s->type==SCD_OBJ_TAGATAGA && (ppz_badnik(s->type)?pre_state!=1:!s->state))continue;
            if(ppz_badnik(s->type)?!ppz_touch(p,s,pre_x,pre_y):(magnitude(dx)>o->sprhsize+8 || magnitude(dy)>o->sprvsize+pr-3))continue;
            /* Player_ObjCollide returns after the first touched object: one
               badnik reaction per update. */
            if(ppz_badnik(s->type) && touch_owner!=i+1)continue;
            if(ppz_badnik(s->type) && ppz_touch_hurts(i))continue; /* hurt in slot 0 above */
            if(s->type==SCD_OBJ_TAMABBOH && s->subtype==1){scd_objects_hurt(ox);continue;}
            if(plpower_m || travel_protection || (p->cddat&4)) {
                /* COLI1.C: escoretbl[min(emyscorecnt,6)/2], 1000 (x10) from emyscorecnt 32. */
                static const unsigned points[]={100,200,500,1000};
                unsigned chain=(unsigned short)emyscorecnt;emyscorecnt+=2;
                scd_player_points(emyscorecnt>=32?10000:points[(chain>=6?6:chain)/2]);
                stats.defeated++;soundset(150);
                short before_vx=p->xspeed.w,before_vy=p->yspeed.w;
                if(p->yspeed.w<0)p->yspeed.w+=256;
                else if(y<oy)p->yspeed.w=-p->yspeed.w;
                else p->yspeed.w-=256;
                scd_plus_enemy_defeat(i+1,before_vx,before_vy);
                if(s->origin!=65535)consumed[s->origin]=1;
                if(objects_zone==0 && load_placements)ppz_badnik_boom(i,emyscorecnt>=32?10:(chain>=6?6:chain),1);
                else {remove_slot(i);scd_objects_spawn(SCD_OBJ_EXPLOSION,ox,oy,0,0);}
            } else scd_objects_hurt(ox);
            continue;
        }
        contact_top=magnitude(dx)<hw+8 && p->yspeed.w>=0 && old_y+pr<=oy-hh+8 && y+pr>=oy-hh;
        contact_bottom=magnitude(dx)<hw+8 && p->yspeed.w<0 && old_y-pr>=oy+hh-8 && y-pr<=oy+hh;
        int side=magnitude(dy)<hh+pr-4 && ((old_x+9<=ox-hw+8 && x+9>=ox-hw && p->xspeed.w>=0) || (old_x-9>=ox+hw-8 && x-9<=ox+hw && p->xspeed.w<=0));
        o->cddat=(o->cddat&~32)|(side?32:0);
        /* Legacy boulder swept contact frontend. */
        if(contact_top) {
            p->yposi.l=(oy-hh-pr)*65536;p->yspeed.w=0;p->direc.b.h=0;
            if(p->cddat&2){p->mspeed.w=p->xspeed.w;jumpcolsub();}
        } else if(contact_bottom) {p->yposi.l=(oy+hh+pr)*65536;if(p->yspeed.w<0)p->yspeed.w=0;}
        else if(side) {p->xposi.l=(x<ox?ox-hw-9:ox+hw+9)*65536;p->xspeed.w=p->mspeed.w=0;}
    }
    if(scd_player_warp_saved())warp_despawn();
    if(mm_spill_timer){ring_loss_accum+=mm_spill_timer;ring_loss_frame=(uint8_t)((ring_loss_accum>>9)&3);mm_spill_timer--;}
    if((int8_t)--ring_anim_timer<0){ring_anim_timer=7;ring_anim_frame=(ring_anim_frame+1)&3;}
    scd_boss_slot_transient_end();
    /* Finish SS3's merged pass; other zones retain their boss pass here. */
    if(!aborted)scd_boss_step();
    scd_profile_span(0,0);
}
/* scd_objects_views' per-type classes, a pure function of the type and
   objects_zone: tt_view_type, tp_type and the types whose view frame is
   s->frame (enemy() stays a call: it consults the zone overlay). The
   comparison chains ran for every pooled actor on every update; with the
   79-flower capsule shower in Tidal Tempest Act 3 they cost about 2,000 FRT
   ticks per update. */
enum {VIEW_TT=1,VIEW_TT_RIDE=2,VIEW_FRAME=4};
static uint8_t view_class[256];static int view_class_zone=-1;
static void view_class_build(void){
    for(unsigned type=0;type<256;type++)
        view_class[type]=(uint8_t)((tt_view_type(type)?VIEW_TT:0)|(tp_type(type)?VIEW_TT_RIDE:0)|
            ((type==SCD_OBJ_SPRINGBOARD || type==SCD_OBJ_SWING || type==SCD_OBJ_AMY || type==SCD_OBJ_AMY_HEART || type==SCD_OBJ_ANIMAL || type==SCD_OBJ_PROJECTOR || type==SCD_OBJ_MOVIE3 || type==SCD_OBJ_FRIEND3 || type==SCD_OBJ_SCENERY || type==SCD_OBJ_LOG_SHADOW || type==SCD_OBJ_DOOR || type==SCD_OBJ_DOOR_V || type==SCD_OBJ_MOVING_SPRING || type==SCD_OBJ_DISC || type==SCD_OBJ_COLLAPSE || type==SCD_OBJ_MONITOR_ITEM || type==SCD_OBJ_SIGN || type==SCD_OBJ_WALL || type==SCD_OBJ_PLATFORM || type==SCD_OBJ_FLOAT_BLOCK || type==SCD_OBJ_RAMP || type==SCD_OBJ_RAMP_PLANT || type==SCD_OBJ_TIMEPOST || type==SCD_OBJ_GENERATOR || type==SCD_OBJ_EXPLOSION)?VIEW_FRAME:0));
    view_class_zone=(int)objects_zone;
}
unsigned scd_objects_views(scd_object_view *views,unsigned capacity) {
    ZONE_OPS_LOADED(6);
    if(view_class_zone!=(int)objects_zone)view_class_build();
    /* Tidal Tempest actors exist only in zone 2: other zones skip the TT
       type helpers entirely (no call per pooled object). */
    const int tt=objects_zone==2;
    unsigned n=0;for(unsigned i=0;i<SCD_OBJECT_CAPACITY && n<capacity;i++)if(pool[i].type) {
        slot *s=&pool[i];sprite_status *o=&actwk[i+1];
        /* The type and its TT classes, read once: every test below is a pure
           function of them, and repeating the comparison chains per test made
           this loop the largest sprite-build cost with 80 actors live. */
        const unsigned type=s->type;
        const unsigned cls=view_class[type];
        const int tt_view=tt && (cls&VIEW_TT),tt_ride=tt && (cls&VIEW_TT_RIDE);
        if(type==SCD_OBJ_CARD)continue;
        /* PLAYSUB4.C breath bubbles and countdown numbers (actno 33), drawn in the
           updates src/water.c queued them: they use AWA.C's pattern table
           (sproffset 33930), packed under SCD_OBJ_AWA. The exit2 splash
           (actno 11, exit2pat at sproffset 664) is packed under SCD_OBJ_PLAWA
           (tools/zone_object_source.py r4_specs). */
        if(type==SCD_OBJ_PLAWA){
            if(o->actno==33 && (o->actflg&128)){
                int x=o->xposi.w.h,y=o->yposi.w.h;
                if(!(o->actflg&12)){x+=scd_act_view_x()-128;y+=scd_act_view_y()-128;}
                views[n++]=(scd_object_view){x,y,SCD_OBJ_AWA,128,(uint8_t)((o->actflg&3)|((o->sprpri&7)<<5)),o->patno};
            }
            /* Acts 1-2 only: Act 3's pack has no exit2 art (VDP1 region full). */
            else if(o->actno==11 && (o->actflg&128) && objects_act<2){
                int x=o->xposi.w.h,y=o->yposi.w.h;
                if(!(o->actflg&12)){x+=scd_act_view_x()-128;y+=scd_act_view_y()-128;}
                views[n++]=(scd_object_view){x,y,SCD_OBJ_PLAWA,0,(uint8_t)((o->actflg&3)|((o->sprpri&7)<<5)),o->patno};
            }
            continue;
        }
        /* ObjExplosion_Done does not draw. */
        if(type==SCD_OBJ_EXPLOSION && s->subtype<2 && s->age>20)continue;
        /* A newly allocated SS or MM seed has not called actionsub yet. */
        if((objects_zone==5 || objects_zone==6) && tt_retail_flower(i) && !o->r_no0)continue;
        /* Badnik flowers draw the art captured from retail (tools/ss_flower_source.py,
           tools/zone_object_assets.py source_paths). */
        /* GA particles allocated before their parent await their first actor
           dispatch; original DrawObject has not submitted them yet. */
        if(((type>=SCD_OBJ_GA && type<=SCD_OBJ_CC_GENERATOR) || (type==SCD_OBJ_MECASNC3 && s->subtype) || type==SCD_OBJ_SIKAKE33 || (type==SCD_OBJ_EXPLOSION && s->subtype==4)) && o->actno==type && !o->r_no0)continue;
        if(tt_view && !o->r_no0 && !(o->userflag.b.h&128))continue;
        /* R4 platforms appear only in updates where they called actionsub. */
        if((tt_ride && !s->sink) || type==255)continue;
        /* Ring views need only their clock pose. Dense ring-loss scenes must
           not walk the growing gimmick visibility and frame dispatch below. */
        if(type==SCD_OBJ_RING || type==SCD_OBJ_LOST_RING){
            unsigned pose=s->frame;
            views[n++]=(scd_object_view){o->xposi.w.h,o->yposi.w.h,type,s->subtype,s->flags,pose};
            continue;
        }
        if(((type==SCD_OBJ_AMY || type==SCD_OBJ_AMY_HEART || type==SCD_OBJ_ANIMAL || type==SCD_OBJ_PROJECTOR || type==SCD_OBJ_MOVIE3 || type==SCD_OBJ_FRIEND3) && !s->sink) || type==SCD_OBJ_SPIN_TAG || (type==SCD_OBJ_MOVING_SPRING && !s->sink) || (type==SCD_OBJ_SONIC_HOLE && !s->state) || type==SCD_OBJ_TUNNEL || (type==SCD_OBJ_CAPSULE && s->state>=6 && s->state!=10) || (type==SCD_OBJ_BIG_RING && !s->subtype && (plring<50 || s->state==4)) || (type==SCD_OBJ_RAMP && (s->subtype&128)))continue;
        if(scd_zone_local(type)){
            scd_object_view v={o->xposi.w.h,o->yposi.w.h,type,s->subtype,(uint8_t)(o->actflg&3),o->patno};
            if(!zone_ops->view || zone_ops->view(i,&v))views[n++]=v;
            continue;
        }
        views[n++]=(scd_object_view){o->xposi.w.h,o->yposi.w.h,type,s->subtype,s->flags,s->cooldown?(s->cooldown>8?1:2):0};
        if(type==SCD_OBJ_BOBIN || type==SCD_OBJ_FRIP || (type>=SCD_OBJ_WALL4 && type<=SCD_OBJ_MECASNC3) || type==SCD_OBJ_SIKAKE33 || (tt_view || tt_ride)){
            views[n-1].frame=o->patno;
            views[n-1].flags=o->actflg&3;
            if(type==SCD_OBJ_DRUMR3 && s->age==1)views[n-1].flags|=16;
            /* TT actors (objects_tt_*.inc) run the retail init, which sets sprpri;
               scd_ppz_priority reads it from flags bits 5-7, as zone-local types. */
            if(tt_view || tt_ride)views[n-1].flags|=(uint8_t)((o->sprpri&7)<<5);
        }
        if(type==SCD_OBJ_CHECKPOINT && n<capacity){
            int x=o->xposi.w.h,y=o->yposi.w.h-32;
            if(s->state==1){short sn,cs;sinset(s->phase,&sn,&cs);x+=(sn*8)>>8;y=o->yposi.w.h-24+((-cs*8)>>8);}
            views[n++]=(scd_object_view){x,y,type,s->subtype,s->flags,s->state==2?2+(s->timer/4)%2:1};
        }
        if(type==SCD_OBJ_CAPSULE || type==SCD_OBJ_FLOWER || type==SCD_OBJ_BIG_RING)views[n-1].frame=s->frame;
        if(tt_retail_flower(i)){
            /* GetLevelBlock sets the live tile priority; flow_move2 changes
               palette line by pose in the retail R7/R8 flower art records. */
            views[n-1].subtype=(o->sproffset>>15)&1;
            views[n-1].flags=(o->actflg&3)|((o->sprpri&7)<<5);
        }
        if((cls&VIEW_FRAME) || enemy(type))views[n-1].frame=s->frame;
    }return n;
}
/* FNV-1a over a zero byte only multiplies by the prime: a run of k zero bytes
   multiplies by prime^k (square and multiply). */
static uint32_t fnv_zero_run(unsigned k){
    uint32_t r=1,base=16777619u;
    for(;k;k>>=1){if(k&1)r*=base;base*=base;}
    return r;
}
typedef uint32_t __attribute__((may_alias)) alias_word;
static uint32_t byte_word(const uint8_t *bytes,unsigned at){return ((const alias_word *)bytes)[at/4];}
/* The placement terms of the object hash, unchanged from the byte loops
     for(j<N) if(j<308 || consumed[j]) mix(consumed[j]);
     for(j<N) if(deferred_reload[j]) mix(j+1);
   with N the PPZ1 placement count (631), but skipping zero words: the byte
   loops cost about 2,000 FRT ticks per update on every route. */
static uint32_t placement_hash(uint32_t h){
    enum {N=sizeof(placements)/sizeof(*placements),ALWAYS=308};
    _Static_assert(N>=ALWAYS && ALWAYS%4==0 && N<=SCD_PLACEMENT_CAPACITY-3,"placement hash bounds");
    unsigned run=0;
    for(unsigned at=0;at<ALWAYS;at+=4){
        if(!byte_word(consumed,at)){run+=4;continue;}
        for(unsigned j=at;j<at+4;j++){
            if(!consumed[j]){run++;continue;}
            h*=fnv_zero_run(run);run=0;h^=consumed[j];h*=16777619u;
        }
    }
    h*=fnv_zero_run(run);
    for(unsigned at=ALWAYS;at<N;at+=4)if(byte_word(consumed,at))
        for(unsigned j=at;j<at+4 && j<N;j++)if(consumed[j]){h^=consumed[j];h*=16777619u;}
    for(unsigned at=0;at<N;at+=4)if(byte_word(deferred_reload,at))
        for(unsigned j=at;j<at+4 && j<N;j++)if(deferred_reload[j]){h^=j+1;h*=16777619u;}
    return h;
}
scd_object_stats scd_objects_get(void) {
    stats.active=stats.debris=stats.collapse_live=stats.attached=stats.holograms=stats.animals=0;uint32_t h=2166136261u;
    for(unsigned i=0;i<SCD_OBJECT_CAPACITY;i++)if(pool[i].type) {
        slot *s=&pool[i];sprite_status *o=&actwk[i+1];stats.active++;if(s->type==SCD_OBJ_WALL && s->state)stats.debris++;
        /* Preserve the exact hash order without a temporary array per actor. */
        h^=i;h*=16777619u;
        h^=s->origin;h*=16777619u;
        h^=s->type;h*=16777619u;
        h^=s->subtype;h*=16777619u;
        h^=s->flags;h*=16777619u;
        h^=s->age;h*=16777619u;
        h^=s->cooldown;h*=16777619u;
        h^=(uint32_t)o->xposi.l;h*=16777619u;
        h^=(uint32_t)o->yposi.l;h*=16777619u;
        h^=(uint16_t)o->xspeed.w;h*=16777619u;
        h^=(uint16_t)o->yspeed.w;h*=16777619u;
        if((s->type==SCD_OBJ_ANIMAL || s->type==SCD_OBJ_FRIEND3) && s->sink && !(s->subtype&128))stats.animals++;
        if(s->parent){if(s->type==SCD_OBJ_SPRING)stats.attached++;else stats.holograms++;h^=s->parent;h*=16777619u;}
        if(s->type==SCD_OBJ_ANIMAL || s->type==SCD_OBJ_PROJECTOR || s->type==SCD_OBJ_MOVIE3 || s->type==SCD_OBJ_FRIEND3){
            uint32_t extra[]={s->state,s->frame,s->sink,s->timer,s->phase,(uint32_t)s->debris_vx,(uint32_t)s->debris_vy,o->direc.w,o->patcnt,o->pattim};
            for(unsigned j=0;j<sizeof(extra)/sizeof(*extra);j++){h^=extra[j];h*=16777619u;}
        }
        if(s->type==SCD_OBJ_DOOR || s->type==SCD_OBJ_DOOR_V || s->type==SCD_OBJ_MOVING_SPRING){
            h^=((uint32_t)s->state<<24)|((uint32_t)s->frame<<16)|s->timer;h*=16777619u;
            h^=((uint32_t)(uint16_t)s->home_y<<16)|s->phase;h*=16777619u;
        }
        if(s->type==SCD_OBJ_AMY || s->type==SCD_OBJ_AMY_HEART){
            uint32_t extra[]={s->state,s->sink,s->frame,(uint16_t)s->home_x,o->mstno.b.h,o->mstno.b.l,o->patcnt,(uint8_t)o->pattim,o->actfree[0],o->actfree[1],o->actfree[2],o->actfree[3]};
            for(unsigned n=0;n<sizeof(extra)/sizeof(*extra);n++){h^=extra[n];h*=16777619u;}
            if(control_actor==i+1){h^=(amy_idle_cursor<<16)|(amy_idle_timer<<8)|amy_idle_pose;h*=16777619u;}
        }
        if(s->type==SCD_OBJ_SONIC_HOLE){h^=s->state;h*=16777619u;}
        if((s->type>=SCD_OBJ_GA && s->type<=SCD_OBJ_MECASNC3) || s->type==SCD_OBJ_SIKAKE33){
            uint32_t extra[]={o->r_no0,o->patno,o->mstno.w,o->patcnt,o->pattim,o->colino,o->colicnt,o->actflg,o->cddat};
            for(unsigned k=0;k<sizeof(extra)/sizeof(*extra);k++){h^=extra[k];h*=16777619u;}
            for(unsigned k=0;k<sizeof(o->actfree);k++){h^=o->actfree[k];h*=16777619u;}
        }
        if(s->type==SCD_OBJ_DISC){
            h^=(s->phase<<8)|s->frame;h*=16777619u;
            if(control_actor==i+1){h^=((uint32_t)actwk[0].actfree[1]<<24)|((uint32_t)actwk[0].actfree[15]<<16)|((uint32_t)actwk[0].patcnt<<8)|actwk[0].actfree[2];h*=16777619u;}
        }
        if(s->type==SCD_OBJ_TUNNEL){
            h^=((uint32_t)s->state<<24)|((uint32_t)s->phase<<16)|s->timer;h*=16777619u;
            h^=((uint32_t)(uint8_t)o->userflag.b.l<<8)|actwk[0].actfree[2];h*=16777619u;
        }
        if(s->type==SCD_OBJ_COLLAPSE){
            if(s->state)stats.collapse_live++;
            h^=((uint32_t)s->state<<24)|((uint32_t)s->frame<<16)|s->timer;h*=16777619u;
            h^=(uint32_t)s->debris_vy;h*=16777619u;
        }
        if(s->type==SCD_OBJ_MONITOR_ITEM || (s->type==SCD_OBJ_TIMEPOST && s->subtype<8)){
            h^=((uint32_t)s->state<<24)|((uint32_t)s->frame<<16)|s->timer;h*=16777619u;
        }
    }
    h=placement_hash(h);
    scd_powerup_state power=scd_player_powerups();
    if(power.invincible || power.shoes || power.ring_lives || plpower_b){
        h^=((uint32_t)power.invincible<<16)|power.shoes;h*=16777619u;
        h^=((uint32_t)power.ring_lives<<16)|(plpower_b?power.shield_age:0);h*=16777619u;
    }
    if(amy_palette_active){h^=0x414d5950u;h*=16777619u;}
    if(projector_destroyed){h^=0x50524f4au;h*=16777619u;}
    if(objects_act==2){h^=scd_boss_hash();h*=16777619u;}
    stats.hash=h;return stats;
}
