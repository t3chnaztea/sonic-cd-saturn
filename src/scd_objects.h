#ifndef SCD_OBJECTS_H
#define SCD_OBJECTS_H
#include <stdint.h>
#define SCD_OBJECT_CAPACITY 96
#define SCD_PLACEMENT_CAPACITY 1024
enum { SCD_OBJ_AMY=47, SCD_OBJ_AMY_HEART=48, SCD_OBJ_ANIMAL=36, SCD_OBJ_PROJECTOR=46, SCD_OBJ_SPIN_TAG=52, SCD_OBJ_SCENERY=50, SCD_OBJ_LOG_SHADOW=51, SCD_OBJ_DOOR=13, SCD_OBJ_DOOR_V=53, SCD_OBJ_MOVING_SPRING=15, SCD_OBJ_DISC=9, SCD_OBJ_TUNNEL=7, SCD_OBJ_SONIC_HOLE=49, SCD_OBJ_SPRING=10, SCD_OBJ_RING=16, SCD_OBJ_LOST_RING=17,
       SCD_OBJ_BOULDER=27, SCD_OBJ_SPIKES=38, SCD_OBJ_TIMEPOST=25, SCD_OBJ_MONITOR_ITEM=26,
       SCD_OBJ_COLLAPSE=32, SCD_OBJ_GOAL=22, SCD_OBJ_SIGN=23, SCD_OBJ_WALL=54, SCD_OBJ_CHECKPOINT=19, SCD_OBJ_PLATFORM=33, SCD_OBJ_FLOAT_BLOCK=18, SCD_OBJ_RAMP=42, SCD_OBJ_RAMP_PLANT=44, SCD_OBJ_TAMABBOH=34, SCD_OBJ_MOSQUI=61, SCD_OBJ_PATABATA=62,
       SCD_OBJ_ANTON=63, SCD_OBJ_TAGATAGA=64, SCD_OBJ_GENERATOR=45, SCD_OBJ_EXPLOSION=24, SCD_OBJ_SWING=41, SCD_OBJ_SPRINGBOARD=40,
       SCD_OBJ_CAPSULE=21, SCD_OBJ_FLOWER=31, SCD_OBJ_SCORE=28 /* SCORE.C tensuu popup (Tidal Tempest) */, SCD_OBJ_CARD=60 /* title card piece slot (Tidal Tempest) */, SCD_OBJ_BOSS=66, SCD_OBJ_BIG_RING=20,
       /* Zone objects (src/objects_*.inc). CC keeps unused IDs 29/30;
          PLAYER.C needs flipper ID 30. Other families use IDs past PPZ's. */
       SCD_OBJ_BOBIN=29, SCD_OBJ_FRIP=30, SCD_OBJ_WALL4=67, SCD_OBJ_WALL7=68, SCD_OBJ_DAIR5=69, SCD_OBJ_KONBEA=70, SCD_OBJ_PISTON=71, SCD_OBJ_FOR3=72, SCD_OBJ_HARIR3=73, SCD_OBJ_FRDR3=74, SCD_OBJ_TRAPDR3=75, SCD_OBJ_GETDAIR3=76, SCD_OBJ_GANDAIR3=77, SCD_OBJ_GA=78, SCD_OBJ_TENTOU=79, SCD_OBJ_KAMA=80, SCD_OBJ_KAMA_BLADE=81, SCD_OBJ_BANPA=82, SCD_OBJ_TOGEBALL=83, SCD_OBJ_POCKET=84, SCD_OBJ_CC_POINTS=85, SCD_OBJ_CC_GENERATOR=86, SCD_OBJ_DRUMR3=87, SCD_OBJ_MOVIE3=88, SCD_OBJ_FRIEND3=89, SCD_OBJ_EMIE3=90, SCD_OBJ_HARI3X=91, SCD_OBJ_MECASNC3=92, SCD_OBJ_SIKAKE33=93,
       /* Tidal Tempest (R4) placement routines, one id per retail routine
          (tools/object_layouts.py ZONE_TYPES). SCREW is SCREW_A.C (Present and
          Past programs); SCREW_F (65, a free id) is SCREW_C.C (both Futures). */
       SCD_OBJ_FRIEND4=94, SCD_OBJ_AWA=95, SCD_OBJ_TONBO=96, SCD_OBJ_TAGAMEB=97, SCD_OBJ_SCREW=98, SCD_OBJ_SW4=99,
       SCD_OBJ_HARIR4=100, SCD_OBJ_YAGO=101, SCD_OBJ_ESCAL4=102, SCD_OBJ_RBLK4=103, SCD_OBJ_HARID4=104, SCD_OBJ_AMENBO=105,
       SCD_OBJ_UDBLK4=106, SCD_OBJ_TEKKYU4=107, SCD_OBJ_KUZURE4=108, SCD_OBJ_TOBIRA4=109, SCD_OBJ_RENKETU4=110, SCD_OBJ_SWGUN4=111,
       SCD_OBJ_BRUNKO4=112, SCD_OBJ_LRBLK4=113, SCD_OBJ_MOVIE4=114, SCD_OBJ_SWBLKR4=115, SCD_OBJ_WALLS=116, SCD_OBJ_TEKKYU=117,
       SCD_OBJ_TEKKYU1=118, SCD_OBJ_FUNSUI4=119, SCD_OBJ_BOU=120, SCD_OBJ_TOBIRAS4=121, SCD_OBJ_OSUMIZU=122, SCD_OBJ_BANEIWA=123,
       SCD_OBJ_DAID4=124, SCD_OBJ_WALL42=125, SCD_OBJ_UKIDAI=126, SCD_OBJ_ET4=127, SCD_OBJ_SCREW_F=65,
       /* R4 child actors (never placed by a layout). */
       SCD_OBJ_SWITCHR4=129, SCD_OBJ_RING4=130, SCD_OBJ_TENSU4=131, SCD_OBJ_PLAWA=132, SCD_OBJ_WAVE=133, SCD_OBJ_MIZUKIRI=134,
       SCD_OBJ_KOWASI4=135,
       SCD_OBJ_R4_FIRST=SCD_OBJ_FRIEND4, SCD_OBJ_R4_LAST=SCD_OBJ_KOWASI4,
       /* Ids 1-135 are global: one meaning in every zone. 136-254 are
          zone-local: Zones R5-R8 each reuse them for their own actors (placed
          and children), dispatched only through that zone's scd_zone_ops
          (src/objects_zone_ops.inc). 255 stays reserved. Layout records carry
          the full byte (tools/object_layouts.py ZONE_LOCAL). */
       SCD_OBJ_ZONE_LOCAL_FIRST=136, SCD_OBJ_ZONE_LOCAL_LAST=254,
       /* Quartz Quadrant (R5), zone-local; children reuse their parent's id. */
       SCD_OBJ_R5_DENDEN=136, SCD_OBJ_R5_SASORI=137, SCD_OBJ_R5_KEMUSI=138, SCD_OBJ_R5_KUMO=139, SCD_OBJ_R5_IWA5=140, SCD_OBJ_R5_HARI5F=141,
       SCD_OBJ_R5_HARIR5=142, SCD_OBJ_R5_IWA5ROLL=143, SCD_OBJ_R5_KUZURE5=144, SCD_OBJ_R5_IWA5WAVE=145, SCD_OBJ_R5_BURANKO5=146, SCD_OBJ_R5_HASIRA5=147,
       SCD_OBJ_R5_HASHI5=148, SCD_OBJ_R5_BELTSW5=149, SCD_OBJ_R5_SHOOT5=150, SCD_OBJ_R5_MOVIE5=151, SCD_OBJ_R5_FRIEND5=152, SCD_OBJ_R5_ET5=153,
       SCD_OBJ_R5_KOWASI5=154,
       /* Wacky Workbench (R6), zone-local; children reuse their parent's id. */
       SCD_OBJ_R6_EGG6DOOR=136,
       SCD_OBJ_R6_DAIR6=137, SCD_OBJ_R6_BEEM6=138, SCD_OBJ_R6_KDAI6=139, SCD_OBJ_R6_TOBIDAI6=140, SCD_OBJ_R6_BLOCK6=141, SCD_OBJ_R6_BATTA=142,
       SCD_OBJ_R6_HACHI6=143, SCD_OBJ_R6_SEMI=144, SCD_OBJ_R6_MINOMUSI=145, SCD_OBJ_R6_OPTBR6=146, SCD_OBJ_R6_SEESAW6=147, SCD_OBJ_R6_TOBIRA6=148,
       SCD_OBJ_R6_PISTON6=149, SCD_OBJ_R6_SW6=150, SCD_OBJ_R6_UDBLK6=151, SCD_OBJ_R6_EGGZ6=152, SCD_OBJ_R6_GAS=153, SCD_OBJ_R6_CATAPALT=154,
       SCD_OBJ_R6_MEGAMI=155, SCD_OBJ_R6_SHOOT6=156, SCD_OBJ_R6_FRIEND6=157, SCD_OBJ_R6_ET6=158, SCD_OBJ_R6_MOVIE6=159, SCD_OBJ_R6_TOGEBALL6=160,
       /* Stardust Speedway (R7), zone-local, including spawned children. */
       SCD_OBJ_R7_EMIE7=136, SCD_OBJ_R7_HEART7=137, SCD_OBJ_R7_HARI73=138, SCD_OBJ_R7_WALL73=139,
       SCD_OBJ_R7_GAITOU73=140, SCD_OBJ_R7_CHGBAN=141, SCD_OBJ_R7_SPRING_R=142, SCD_OBJ_R7_GUN7=143,
       SCD_OBJ_R7_HIBANA7=144, SCD_OBJ_R7_SLIGHT7=145, SCD_OBJ_R7_TEKKYU7=146, SCD_OBJ_R7_TEKKYU7J=147,
       SCD_OBJ_R7_CHGWALL7=148, SCD_OBJ_R7_HOTARU7=149, SCD_OBJ_R7_KABASIRA=150, SCD_OBJ_R7_KANABUN=151,
       SCD_OBJ_R7_DANGO7=152, SCD_OBJ_R7_BRANKO7=153, SCD_OBJ_R7_FRIEND7=154, SCD_OBJ_R7_ET7=155,
       SCD_OBJ_R7_MOVIE7=156,
       /* Metallic Madness (R8), zone-local, including spawned children. Ids start
          at 157 so no R8 actor shares an id with an SS actor (136-156). */
       SCD_OBJ_R8_TOGEDAIR8=157, SCD_OBJ_R8_DAI8=158, SCD_OBJ_R8_NOKOGIRI=159, SCD_OBJ_R8_KUZURE8=160,
       SCD_OBJ_R8_PROPERA=161, SCD_OBJ_R8_KOMA8=162, SCD_OBJ_R8_FUTAGOR8=163, SCD_OBJ_R8_SCARAB=164,
       SCD_OBJ_R8_KABUTO=165, SCD_OBJ_R8_OKUSIESO=166, SCD_OBJ_R8_HACHI8=167, SCD_OBJ_R8_FRIEND8=168,
       SCD_OBJ_R8_ET8=169, SCD_OBJ_R8_SHOOTER=170, SCD_OBJ_R8_BEAM=171, SCD_OBJ_R8_PIPE8=172,
       SCD_OBJ_R8_HAGURUMA=173, SCD_OBJ_R8_BIGBOM=174, SCD_OBJ_R8_LEGMECA=175, SCD_OBJ_R8_TOBIRA=176,
       SCD_OBJ_R8_DANGO8=177, SCD_OBJ_R8_KAITEN=178, SCD_OBJ_R8_SW8=179, SCD_OBJ_R8_TOGEITA=180,
       SCD_OBJ_R8_GATER8=181, SCD_OBJ_R8_CHIBI_COLI=182, SCD_OBJ_R8_HOTARU8=183, SCD_OBJ_R8_JETTOGE=184,
       SCD_OBJ_R8_SHUT=185, SCD_OBJ_R8_KONBEA83=186, SCD_OBJ_R8_ANAR8=187, SCD_OBJ_R8_SPRING8=188,
       /* An R8 act_tbl noact record (ACT81A.C:171 noact = frameout): it is never
          spawned, but holds a slot through SpawnObjects (tt_spawn_record). */
       SCD_OBJ_R8_NOACT=189 };
typedef struct {int16_t x,y;uint8_t type,subtype,flags,eras,secondary;} scd_placement;
typedef struct {int16_t x,y;uint8_t type,subtype,flags,frame;} scd_object_view;
/* A zone's hooks for its zone-local types (i = pool slot; actor i+1). Every
   pointer may be NULL. objects.c calls them only for zone-local types while
   that zone is loaded, so equal ids in two zones never meet.
   reject: nonzero refuses a spawn (unsupported type, invalid subtype).
   init: after the common slot/actor setup of a spawn. step: once per update.
   view: fills the view's frame/flags (bits 0-1 flip, 5-7 actor priority,
   src/sprite_order.h); returns 0 to hide it this update.
   enemy: the type is destroyed by Good Future / time travel like PPZ enemies.
   contact: the type's colino is masked outside the player contact pass
   (scd_objects_collision_begin), like CC/TT enemies.
   scan: the zone's pre-motion player contact scan (TT: tt_enemy_scan).
   reset: zone state cleared at stage reset and respawn.
   actor: one update of a zone actor with a global id (CC, TT) that the
   resident dispatch does not run itself; its code runs from the zone overlay.
   stream_windowed: the type's placements stream through the ACTSET camera
   window (FRAMEOUT_S frameout; objects.c stream), not the +-480 px player
   window, and one removed inside that window waits for the window to leave it.
   remove_slot clears the player's push bit for every zone-local type.
   A zone without step spawns no zone-local type. */
typedef struct {
    int (*reject)(unsigned type,unsigned subtype);
    void (*init)(unsigned i);
    void (*step)(unsigned i);
    int (*view)(unsigned i,scd_object_view *view);
    int (*enemy)(unsigned type);
    int (*contact)(unsigned type);
    void (*scan)(void);
    void (*reset)(void);
    void (*actor)(unsigned i);
    int (*stream_windowed)(unsigned type);
    /* R8/KONBEA.C (global SCD_OBJ_KONBEA, placed in R81A-D only): spawn
       when spawn is set, else step. Its code lives in the R8 overlay. */
    void (*konbea)(unsigned i,int spawn);
    /* ring_spill: a lost ring's first update while its spill is pending (MM:
       RING.C flyringinit takes the other rings then). */
    void (*ring_spill)(unsigned i);
} scd_zone_ops;
static inline int scd_zone_local(unsigned type){return type>=SCD_OBJ_ZONE_LOCAL_FIRST && type<=SCD_OBJ_ZONE_LOCAL_LAST;}
typedef struct {
    uint16_t active,spawned,despawned,collected,springs,hits,deaths,lost,dropped,unsupported;
    uint32_t hash;
    uint16_t defeated,projectiles,broken,debris,monitors,items,collapsed,collapse_pieces,collapse_live,doors_opened,wheel_reversals,attached,tag_contacts,projector_hits,projector_explosions,holograms,animals,amy_grabs,amy_hearts;
} scd_object_stats;
int scd_objects_amy_palette(uint16_t *colors);
int scd_objects_ss_palette_restored(void);
void scd_objects_amy_idle_step(void);
int scd_objects_amy_idle_frame(void);
void scd_objects_clear_live(void);
void scd_objects_release_control(void);
void scd_objects_respawn(void);
/* SpawnObjects_Init again on the next update's camera (QA fixtures that place
   Sonic away from the level start after load_era's lead update). */
void scd_objects_spawner_restart(void);
void scd_objects_validate_rider(void);
void scd_objects_collision_begin(void);
void scd_objects_collision_end(void);
unsigned scd_objects_standing_type(void);
void scd_objects_reset(unsigned era,int placements);
/* A zone past Palmtree Panic takes its placements from a table loaded with the
   act (tools/object_layouts.py). Call after scd_objects_act; ignored in zone 0. */
void scd_objects_layout(const scd_placement *layout,unsigned count);
/* levelVIntCounter (cleared by scd_objects_layout, +1 per scd_objects_step): extra V-INTs. */
void scd_objects_vint_add(unsigned n);
unsigned scd_objects_vint(void);
/* src/boss.c: the retail actor slot of native actor ACTOR (1-96). */
unsigned scd_boss_retail_slot(unsigned actor);
/* Selects the placement table of an act (0 = Act 1, 1 = Act 2, 2 = Act 3) for later resets. */
/* 0 = Palmtree Panic. A non-zero zone has no imported object layout yet. */
void scd_objects_zone(unsigned zone);
void scd_objects_act(unsigned act);
/* Time stones held (bit per stone). The big ring deletes itself once stone 1 is held:
   this prototype has only Special Stage 1. */
void scd_objects_time_stones(unsigned stones);
/* 1 once after Sonic touched a big ring (the special stage follows the tally). */
int scd_objects_big_ring(void);
int scd_objects_big_ring_touched(void);
void scd_objects_step(int previous_x,int previous_y);
/* Tidal Tempest: SpawnObjects before the player's update (no-op elsewhere). */
void scd_objects_spawn_early(void);
int scd_objects_spawn(unsigned type,int x,int y,unsigned subtype,unsigned flags);
void scd_objects_explosion_fire(int slot_index);
unsigned scd_objects_views(scd_object_view *views,unsigned capacity);
unsigned scd_objects_ww_title_phase(unsigned act,unsigned era);
scd_object_stats scd_objects_get(void);
/* Nonzero for a badnik type (Good Future / time travel destroys it). */
int scd_objects_enemy_type(unsigned type);
void scd_objects_hurt(int source_x);
int scd_objects_timepost(void);
int scd_objects_generator(void);
int scd_objects_projector_destroyed(void);
void scd_objects_travel_protection(int active);
void scd_objects_change_era(unsigned era);
void scd_objects_death_record(void);
#endif
