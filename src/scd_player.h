#ifndef SCD_PLAYER_H
#define SCD_PLAYER_H
#include "stage.h"
enum { SCD_UP=1, SCD_DOWN=2, SCD_LEFT=4, SCD_RIGHT=8, SCD_JUMP=16 };
typedef struct {
    int32_t x,y;
    int16_t vx,vy,speed;
    uint8_t flags,angle,animation,path,charge;
    uint16_t lock;
    uint32_t frame,resets,elapsed,score;
    uint16_t rings,hurt;
    uint8_t routine,shield,lives,ramp,game_over,control,disc_angle,disc_radius,disc_frame;
    /* Displayed mapping/flip state is distinct from the next script cursor. */
    uint8_t mapping,render_flags,animation_previous,animation_cursor,animation_timer;
    /* Source display decision captured before touch/ordinary object updates. */
    uint8_t display_hidden;
    /* actwk[0].sprpri: 2 in play; 0 after death/time over (COLI3.C:556,
       PLAYER.C:37). 2 before the source init (r_no0 0) has run. */
    uint8_t priority;
    /* actwk[0].sproffset bit 15: in front of high-priority plane cells
       (ACTION.C:322). Set when dying (COLI3.C:555) or drowning. */
    uint8_t high;
} scd_player_state;
typedef struct {int16_t x,y;uint32_t elapsed;uint8_t id;} scd_checkpoint;
scd_checkpoint scd_player_checkpoint(void);
int scd_player_checkpoint_activate(unsigned id);
int scd_player_init(const stage_t *stage,const uint8_t *collision,size_t size,unsigned era);
/* Level start: placed actors run one update before Sonic's first ObjSonic_Main. */
void scd_player_objects_lead(void);
void scd_player_objects_lead_run(void);
void scd_player_step(unsigned buttons);
typedef struct {uint16_t invincible,shoes,shield_age;uint8_t ring_lives;} scd_powerup_state;
scd_powerup_state scd_player_powerups(void);
/* Read-only presentation samples at the original record and reserved-object
   boundaries, before ordinary objects can carry Sonic or grant an item. */
typedef struct {
    int16_t record_x,record_y,x,y;
    uint32_t resets;
    uint8_t flags,shield,invincible,record,valid;
} scd_player_effect_sample;
scd_player_effect_sample scd_player_effects(void);
void scd_player_powerup(unsigned kind);
void scd_player_rings(unsigned count);
void scd_player_rings_lost(void);
uint32_t scd_player_level_frames(void);
int scd_player_music_event(void);
void scd_player_finish(void);
/* Level End ObjCapsule: a hit stops the level clock only. */
void scd_player_stop_clock(void);
/* Temporary title/control lock; independent of the permanent end-of-act stop. */
void scd_player_hold_clock(int held);
/* Monitor item 5 sets timeStopTimer, which nothing in the retail program decrements. */
int scd_player_time_stop(void);
/* ObjBigRing: controls lock to Right until the act ends. */
void scd_player_force_right(int active);
void scd_player_points(unsigned points);
unsigned scd_player_arrival_adjusted(void);
int scd_player_arrival_clear(void);
int scd_player_arrive(const stage_t *stage,const uint8_t *collision,size_t size,unsigned era);
/* Time warp: SaveTimeWarpData at timeWarpTimer 210 (src/world.c), read by scd_player_arrive. */
void scd_player_warp_save(void);
int scd_player_warp_saved(void);
void scd_player_warp_clear(void);
scd_player_state scd_player_get(void);
void scd_player_velocity(int x,int y);
void scd_player_place(int x,int y,int speed,unsigned angle,unsigned flags);
void scd_player_inventory(unsigned rings,unsigned shield);
void scd_player_audio_set(void (*sink)(short));
/* Act index (0 = Act 1, 1 = Act 2) used by the next scd_player_place. */
/* The retail round index that GAME.C's da_tbl is subscripted by, which is what
   stageno.b.h carries and what scroll_limits.h is indexed by:
   0 Palmtree Panic, 1 Collision Chaos, 2 Tidal Tempest, 3 Quartz Quadrant,
   4 Wacky Workbench, 5 Stardust Speedway, 6 Metallic Madness. */
void scd_player_zone(unsigned zone);
void scd_player_act(unsigned act);
/* Score, lives and the next extra-life score carried into the next act. */
typedef struct {uint32_t score,next_life;uint8_t lives;} scd_player_progress;
scd_player_progress scd_player_progress_get(void);
void scd_player_progress_set(scd_player_progress progress);
#endif
