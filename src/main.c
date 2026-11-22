/* Native Saturn terrain/player integration sandbox. */
#include <yaul.h>
#include "vdp_dma_guard.h"
#include "zone_code.h"
#include "frontend.h"
#include "stage_select.h"
#include "time_attack.h"
#include "credits_saturn.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "cd_root.h"
#include "stage.h"
#include "scd_player.h"
#include "sonic_animation.h"
#include "player_replay.h"
#include "scd_objects.h"
#include "audio.h"
#include "world.h"
#include "act.h"
#include "world_qa.h"
#include "background.h"
#include "background_cache.h"
#include "background_r4.h"
#include "background_r6.h"
#include "foreground_cache.h"
#include "special.h"
#include "object-frames.inc"
#include "stage_packs.h"
#include "title_card.h"
#include "title-card.inc"
#include "scd_boss.h"
#include "act3-palettes.inc"
#include "sonic_frames.h"
#include "powerup_runtime.h"
#include "zone_object_art.h"
#include "save.h"
#include "ending.h"
#include "water.h"
#include "water_raster.h"
#include "camera_v.h"

static const struct {const char *file;uint32_t address,capacity;} stage_pack_regions[STAGE_PACK_COUNT]={
#define STAGE_PACK(id,file,address,capacity,source) {file,address,capacity},
    STAGE_PACKS
#undef STAGE_PACK
};
static uint32_t stage_pack_bytes[STAGE_PACK_COUNT];
/* Magic 'SPAK', VBlanks spent, bytes read, failed pack index + 1. */
volatile uint32_t scd_stage_pack_mailbox[4];
volatile uint32_t scd_sfx_bank_mailbox[4];
#define STAGE_PACK_DATA(id) ((const uint8_t *)(uintptr_t)stage_pack_regions[id].address)
#define STAGE_PACK_END(id) (STAGE_PACK_DATA(id)+stage_pack_bytes[id])
#define floor_bitmap STAGE_PACK_DATA(PACK_FLOOR)
#define floor_bitmap_end STAGE_PACK_END(PACK_FLOOR)
#define warp_art STAGE_PACK_DATA(PACK_WARP)
#define sonic_motion STAGE_PACK_DATA(PACK_SONIC_MOTION)
#define sonic_motion_end STAGE_PACK_END(PACK_SONIC_MOTION)
#define object_art STAGE_PACK_DATA(PACK_OBJECT_ART)
#define object_art_end STAGE_PACK_END(PACK_OBJECT_ART)
/* [134] act index, [135] trace sequence when that act was loaded,
   [136] swing platform X<<16|Y of the last drawn frame (0 when none),
   [137] updates shown on the end-of-prototype screen (0 when not shown),
   [138] Robotnik X<<16|Y and [139] boss status (scd_boss_position/scd_boss_status),
   [140] time stones, [141] big ring touched<<16 | special stage active<<8 | act that follows it,
   [142] stage zone, [143] VDP1 overrun V-blanks: VBlank-ins at which VDP1 had not
   finished its list (EDSR CEF clear; scd_vdp1_overrun_sample). Debug only, never drawn.
   Boot, menu and loading frames count too: compare a count against the same
   route's (the QQ2A emulator route reaches gameplay at 414 and adds none there). */
volatile uint32_t scd_world_mailbox[144];
/* From the VBlank-in callback (src/audio.c), after libyaul's own VDP1 VBlank-in work:
   a frame change waits for VBlank-out, so a clear CEF here is the previous list still
   plotting (or one libyaul has just stopped). */
void scd_vdp1_overrun_sample(void){if(!vdp1_transfer_status_get().cef)scd_world_mailbox[143]++;}
volatile uint32_t scd_vdp_dma_stats[2]; /* src/vdp_dma_guard.h */
volatile uint32_t scd_floor_mailbox[4];
static unsigned feature_demo,feature_object;
static vdp1_cmdt_t sonic_command_template;
static int feature_camera_offset;
static unsigned warp_timer;
static int warp_destination;
static scd_powerup_runtime effect_runtime;
/* POWV: update, submissions, record index, camera, two position samples,
   ownership/flags, player frame, art selection, era; then 9 packed actors. */
volatile uint32_t scd_effect_mailbox[12+9*5];
extern uint8_t sonic_bitmap[],hud_font[],title_card_art[],title_card_art_end[];
static const uint8_t *collision_packs[4];
volatile uint32_t scd_trace_mailbox[24+64*21];
/* Separate presentation trace leaves the historical 16-word physics ABI intact. */
volatile uint32_t scd_player_visual_trace[64*3];
static unsigned trace_sequence,replay_test,replay_frame;
static int replay_active,diagnostic_mode,paused,audio_test,input_ready;
static scd_player_state player;
extern int scd_core_probe(void);
static vdp1_cmdt_list_t *sprite_commands;
static int core_result;
static const uint8_t *packs[4];
static size_t sizes[4];
static const char *names[]={"PRESENT","PAST","GOOD FUTURE","BAD FUTURE"};
static stage_t stage;
_Static_assert(sizeof(vdp2_scrn_ls_h_t)==sizeof(int32_t),"horizontal scroll table stride");
static int32_t background_lines[224] __aligned(16);
static int32_t foreground_lines[224] __aligned(16);
static uint16_t animated_palette[64] __aligned(16);
static int previous_amy_palette;
/* Art-miss gate (tools/test_art_misses.py): object draws that reach the common
   atlas's default pose (any type but spikes and the boulder) or miss their zone
   art record. [0] entries (bit 8: more keys than slots), [1..16] type<<16 |
   subtype<<8 | pose; counts per entry (saturating). */
volatile uint32_t scd_art_miss_mailbox[17];
volatile uint16_t scd_art_miss_counts[16];
static void art_miss(unsigned type,unsigned subtype,unsigned frame){
    uint32_t key=(uint32_t)(type&0xffff)<<16|(subtype&255)<<8|(frame&255);
    unsigned n=scd_art_miss_mailbox[0]&255;
    for(unsigned j=0;j<n;j++)if(scd_art_miss_mailbox[1+j]==key){if(scd_art_miss_counts[j]<65535)scd_art_miss_counts[j]++;return;}
    if(n<16){scd_art_miss_mailbox[1+n]=key;scd_art_miss_counts[n]=1;scd_art_miss_mailbox[0]=(scd_art_miss_mailbox[0]&~255u)|(n+1);}
    else scd_art_miss_mailbox[0]|=256;
}
static uint32_t object_clut_epoch=1,object_clut_applied[OBJECT_FRAME_COUNT];
static int bg_row_keys[64],bg_row_world[64];static uint8_t bg_row_periodic[SCD_BACKGROUND_PERIODIC_ROWS];
static uint32_t maps[2][4096] __aligned(16);
static uint32_t coefficients[224] __aligned(16);
static vdp2_scrn_rp_table_t rotation __aligned(16);
static int era, floor_mode, camera_x, camera_y;
static unsigned frames,object_demo=8;
static volatile uint32_t vblank_ticks;
static uint32_t simulation_tick;
static uint32_t world_vblank_previous;
/* GAME5 mapwrtb can redraw all 30 visible R5 rows after enkeichg.  The
   slave owns only the lower half; row metadata remains private to the master
   until that work is complete. */
typedef struct { int row,first,fixed,slot; } bg_slave_row;
typedef struct {
    const stage_t *stage; uint32_t *map; unsigned count,generation,done;
    bg_slave_row row[15];
} bg_slave_job_t;
static bg_slave_job_t bg_slave_job_storage __aligned(16);
#define bg_slave_job ((volatile bg_slave_job_t *)((uintptr_t)&bg_slave_job_storage|0x20000000))
/* QA-visible totals for the QQ mapwrtb split.  Words 0..3 are attempted
   dispatches, entered workers, completed workers, and eligibility fallbacks.
   Words 4..8 record nonzero map_update returns, hold (-1) returns, full
   redraw (64) returns, full redraws skipped because the slave is unavailable,
   and the last nonzero return (as a uint32_t).  Word 9 counts redraws whose
   slave half timed out (the master drew it).  Word 10 is test-only: nonzero
   makes the master skip the notification, so the timeout path runs
   (tools/test_qq_route.py --force-r5-fallback).  Both SH-2s access this through
   the uncached alias, just like the job descriptor. */
volatile uint32_t scd_bg_slave_mailbox[11];
#define bg_slave_mailbox ((volatile uint32_t *)((uintptr_t)scd_bg_slave_mailbox|0x20000000))
static int bg_slave_ready;
static void bg_slave_entry(void){
    unsigned generation=bg_slave_job->generation;
    bg_slave_mailbox[1]++;
    cpu_cache_purge();cpu_cache_repl_enable(CPU_CACHE_TYPE_I|CPU_CACHE_TYPE_D);
    for(unsigned i=0;i<bg_slave_job->count;i++){
        bg_slave_row row=bg_slave_job->row[i];
        scd_background_fill_row_fast(bg_slave_job->stage,bg_slave_job->map+row.slot*64,
            row.row,row.first,row.first+64,row.fixed);
    }
    bg_slave_job->done=generation;
    bg_slave_mailbox[2]++;
}
static void bg_slave_stop(void){
    if(!bg_slave_ready)return;
    input_ready=0;cpu_dual_slave_clear();smpc_smc_sshoff_call();input_ready=1;
    bg_slave_ready=0;
}
static void bg_slave_start(void){
    if(bg_slave_ready)return;
    bg_slave_job->count=bg_slave_job->generation=bg_slave_job->done=0;
    for(unsigned i=0;i<10;i++)bg_slave_mailbox[i]=0;
    input_ready=0;cpu_dual_comm_mode_set(CPU_DUAL_ENTRY_POLLING);cpu_dual_slave_set(bg_slave_entry);input_ready=1;
    bg_slave_ready=1;
}
#include "frame_profile.h"
#if SCD_FRAME_PROFILE
/* Profile words 28-31: sub-spans inside gameplay and sprite build. Slot 0 is
   scd_objects_step, 1 the ring-loss spawn, 2 ring command construction, 3 the sprite view list and draw
   order; word 30 records R5 hold/redraw events instead of a duration.
   src/objects.c calls the hook; host tools link its weak
   no-op. */
static uint16_t profile_span_start[4];
void scd_profile_span(unsigned slot,int begin){
    uint16_t now=cpu_frt_count_get();
    if(begin)profile_span_start[slot&3]=now;
    else profile_values[28+(slot&3)]+=(uint16_t)(now-profile_span_start[slot&3]);
}
#else
void scd_profile_span(unsigned slot,int begin){(void)slot;(void)begin;}
#endif
static unsigned pacing_previous,pacing_sim,pacing_count,pacing_sum,pacing_peak;
static unsigned pacing_window_blanks,pacing_window_max;
static void pacing_record(unsigned sim){
    unsigned gap=simulation_tick-pacing_previous;
    if(sim==pacing_sim+1 && pacing_previous && gap && gap<=10){
        pacing_sum+=gap;if(gap>pacing_peak)pacing_peak=gap;
        if(++pacing_count==60){pacing_window_blanks=pacing_sum;pacing_window_max=pacing_peak;pacing_count=pacing_sum=pacing_peak=0;}
    }else pacing_count=pacing_sum=pacing_peak=0;
    pacing_previous=simulation_tick;pacing_sim=sim;
}
static uint16_t update_ticks;
static int previous_x[2]={-10000,-10000},previous_y[2]={-10000,-10000};

static void input_poll(void *work __unused) { vblank_ticks++;if(input_ready)smpc_peripheral_intback_issue(); }
/* Backup RAM writes (src/save_saturn.c) bracket their SMPC RESDISA/RESENAB with this
   so the VBlank INTBACK above cannot collide with them. Returns the previous state. */
int scd_input_ready_set(int ready){int was=input_ready;input_ready=ready;return was;}
static void sync_frame(void) { vdp2_sync(); vdp2_sync_wait(); }
static unsigned stage_act;
/* Set by a gameplay update; the water frame end runs after the camera. */
static int water_frame;
/* camera_y changed this update: mirror it into scra_v_posit. */
static int camera_v_sync;
/* The retail round index, the same one scd_player_zone takes:
   0 Palmtree Panic, 1 Collision Chaos, 2 Tidal Tempest, 3 Quartz Quadrant,
   4 Wacky Workbench, 5 Stardust Speedway, 6 Metallic Madness.
   Only the CD file differs; the four era regions are shared, so one zone is
   resident at a time. */
static unsigned stage_zone;
/* Indexed by the retail round index, which is what stageno.b.h holds and what
   scroll_limits.h is subscripted by: R1, R3, R4, R5, R6, R7, R8. */
static const char *const LS_ZONES[]={"PALMTREE PANIC","COLLISION CHAOS","TIDAL TEMPEST",
    "QUARTZ QUADRANT","WACKY WORKBENCH","STARDUST SPEEDWAY","METALLIC MADNESS"};
#define LS_ZONE_COUNT 7
/* PC scroll limits, camera line and boss flag (EQU.C). */
extern short scralim_left,scralim_right,scralim_down,scralim_n_left,scralim_n_down,scra_vline;
extern unsigned char bossflag;
extern unsigned char limmoveflag;
/* Level/Main.asm: FadeToBlack/FadeFromBlack run 22 frames with the level frozen.
   act_fade counts 1..22 fading out after the Act 1 tally, then loads Act 2 and
   counts 23..44 fading in. goodFutureFlags keeps one bit per finished act. */
static unsigned act_fade,good_future_flags;
/* One selected RunMMD, separate from the ordinary debug picker/campaign. */
static unsigned stage_select_single_program;
/* Retained resident outcome: 0 none, 1 running, 2 tally, 3 no lives,
   4 timewarp program return, 5 standalone WARP running, 6 COMMING requested,
   7 MM ending return, 8 unclassified fade return (never an accepted tally),
   9 tally with big-ring/special-stage request (no wrapper dispatch),
   10 standalone WARP returned, 11 OPENING returned. */
volatile uint32_t scd_stage_select_scene_qa[4];
/* Set once a QA fixture or demo has placed Sonic; those runs keep the debug reset after the tally. */
static int fixture_run;
/* Updates on the end-of-prototype screen after the Act 3 tally; 0 during play. */
static unsigned prototype_end;
/* IPX.asm GameDone: the ending picked (1 good) and what playing its movie returned. */
static int ending_good,ending_result;
/* Palette cycle frame; monitor item 5 (time stop) freezes it. */
static uint32_t palette_frame;
/* Big ring flow (IPX.asm .SpecialStage): time stones held, the act that follows the special
   stage (0 when the special stage came from the inspection), its results being over, a
   pending entry after the tally and a fade-in from white. */
static unsigned time_stones,special_return_act;
static int special_finished,special_pending,fade_white;
static scd_save save_state;
static unsigned saved_good_zones,save_session;
/* curSpecStage; defined with the special stage view (special_game_view.inc). */
static unsigned special_cur_stage;
/* SAVE: status, valid, dirty, generation, saved stage/stones, saved futures,
   live stage/stones, live futures, session enabled, panel mode. */
volatile uint32_t scd_save_mailbox[12];
static unsigned save_panel;
static void save_publish(void){
    const scd_save_progress *p=&save_state.saved;
    scd_save_mailbox[1]=save_state.status;scd_save_mailbox[2]=save_state.valid;
    scd_save_mailbox[3]=save_state.dirty;scd_save_mailbox[4]=save_state.generation;
    scd_save_mailbox[5]=p->zone|(unsigned)p->act<<8|(unsigned)p->era<<16|(unsigned)p->time_stones<<24;
    scd_save_mailbox[6]=p->good_acts|(unsigned)p->good_zones<<8|(unsigned)p->completed<<16|(unsigned)p->spec_stage<<24;
    scd_save_mailbox[7]=stage_zone|stage_act<<8|(unsigned)era<<16|time_stones<<24;
    scd_save_mailbox[8]=good_future_flags|saved_good_zones<<8;
    scd_save_mailbox[9]=save_session;scd_save_mailbox[10]=save_panel;
    scd_save_mailbox[0]=0x53415645;
}
static void save_checkpoint(unsigned completed){
    if(!save_session)return;
    scd_save_progress p={stage_zone,stage_act,stage_act==2?era:0,time_stones,good_future_flags,saved_good_zones,completed,(uint8_t)special_cur_stage};
    input_ready=0;scd_save_commit(&save_state,p);input_ready=1;save_publish();
}
static void act_fade_offset(int level){
    vdp2_scrn_coff_rgb_t rgb={.r=level,.g=level,.b=level};
    vdp2_scrn_coff_rgb_set(VDP2_SCRN_COFF_A,&rgb);
    const vdp2_scrn_t screens[]={VDP2_SCRN_NBG0,VDP2_SCRN_NBG1,VDP2_SCRN_SPRITE,VDP2_SCRN_BACK};
    for(unsigned i=0;i<4;i++){if(level)vdp2_scrn_coff_set(screens[i],VDP2_SCRN_COFF_A);else vdp2_scrn_coff_unset(screens[i]);}
}
/* src/background.c indexes twelve ids per zone: act*4 + era. */
static unsigned bg_id(void){return stage_zone*12+((unsigned)era|stage_act<<2);}
/* src/camera_v.c hooks: Tidal Tempest background Y follows the original
   scrbinit and scroll()'s scrollb_hv on scrb_v_posit (src/background_r4.h). */
void scd_camera_v_bg_reset(int32_t *scrb,int camera_top){
    if(stage_zone!=2 || !scd_r4_valid(bg_id()-24))return;
    scd_r4_camera_v_reset();scd_r4_scrbinit(scrb,camera_top);
}
void scd_camera_v_bg_scroll(int32_t *scrb,int16_t vz){
    if(stage_zone==2 && scd_r4_valid(bg_id()-24))scd_r4_scroll_v(bg_id()-24,scrb,vz);
}
static const char *stage_pack_file(unsigned id){
    /* tools/title_card_names.py: TCN<retail round>.BIN for zones 0-6. */
    if(id==PACK_CARD_NAME){static char name[]="TCN1.BIN";name[3]="1345678"[stage_zone<7?stage_zone:0];return name;}
#define STAGE_ZONE_PACK(pack,zone,act,file,source) if(id==pack && stage_zone==zone && stage_act==act)return file;
        STAGE_ZONE_PACKS
        ZONE_OBJECT_PACKS
#undef STAGE_ZONE_PACK
    /* src/stage_packs.h SONIC_FRAME_PACKS. */
    if(id==PACK_SONIC_FRAMES && (stage_zone || stage_act==2))return stage_zone==6?"SONFRM8.BIN":stage_zone==2?"SONFRM4.BIN":"SONFRMB.BIN";
    if(!stage_zone){
#define STAGE_ACT_PACK(pack,act,file,source) if(id==pack && stage_act==act)return file;
        STAGE_ACT_PACKS
#undef STAGE_ACT_PACK
    }
    return stage_pack_regions[id].file;
}
/* Zone-only constant tables (src/saturn.x): the running zone's overlay, read from
   the CD into the shared high work RAM range whenever the loaded zone changes. Every zone has an overlay. Palmtree Panic's overlay holds
   its compiled object placements (src/objects.c), read only while it is loaded. */
extern uint8_t __zone_tables_start[],__zone_tables_end[];
static int zone_tables_zone=-1;
/* src/zone_code.h: the zone whose overlay code may run. */
unsigned scd_zone_code_zone=~0u;
static void stage_packs_load(unsigned first,unsigned end);
/* The card's tiles are high priority ($8360), above every plane: its CLUTs
   become palette codes of sprite priority 1, colours in CRAM 96-111 (unused). */
static void title_card_priority(unsigned f){
    static uint16_t colors[16];static unsigned count;
    volatile uint16_t *clut=(volatile uint16_t *)VDP1_VRAM(0x4600+title_card_frames[f].offset+title_card_frames[f].width*title_card_frames[f].height/2);
    for(unsigned c=1;c<16;c++)if(clut[c]&0x8000){
        unsigned n=0;while(n<count && colors[n]!=clut[c])n++;
        if(n==count){assert(count<16);colors[count++]=clut[c];MEMORY_WRITE(16,VDP2_CRAM_MODE_0_OFFSET(0,0,96+n),clut[c]);}
        clut[c]=0x4060+n;
    }
}
/* The zone's title card name (frames 7 and 8 in their fixed VDP1 slots) and
   ObjTitleCard_Data, from TCN<round>.BIN (tools/title_card_names.py). */
static void title_card_name_load(void){
    /* The CD read bypasses the cache, which may hold the previous zone's file. */
    stage_packs_load(PACK_CARD_NAME,PACK_CARD_NAME+1);cpu_cache_purge();
    const uint16_t *p=(const uint16_t *)STAGE_PACK_DATA(PACK_CARD_NAME),*texture=p+40;
    scd_title_card_layout((const uint16_t (*)[4])p);
    for(unsigned k=0;k<2;k++){
        const uint16_t *h=p+32+4*k;unsigned f=7+k,words=(h[0]*h[1]/2+32)/2;
        title_card_frames[f].width=h[0];title_card_frames[f].height=h[1];title_card_frames[f].left=(int16_t)h[2];title_card_frames[f].top=(int16_t)h[3];
        volatile uint16_t *v=(volatile uint16_t *)VDP1_VRAM(0x4600+title_card_frames[f].offset);
        for(unsigned i=0;i<words;i++)v[i]=*texture++;
        title_card_priority(f);
    }
}
/* A stage pack or overlay read: three more attempts after a failed one before the
   caller shows its CD error screen (a console drive can fail a read that the
   emulator never does). Each attempt restarts the read at the file's first sector. */
static int cd_read_retry(uint32_t fad,void *buffer,uint32_t size){
    int ret=-1;
    for(unsigned attempt=0;attempt<4;attempt++)if(!(ret=cd_block_sectors_read(fad,buffer,size)))break;
    return ret;
}
/* Reads one overlay file into the shared range; id becomes scd_zone_code_zone. */
static void overlay_file_load(const cdfs_filelist_t *root,const char *file,unsigned id){
    /* Overlay code is unusable while the range is being replaced. */
    scd_zone_code_zone=~0u;
    if(!file){scd_zone_code_zone=id;return;}
    const uint32_t capacity=(uint32_t)(__zone_tables_end-__zone_tables_start);
    for(unsigned i=0;i<root->entries_count;i++)if(!strcmp(root->entries[i].name,file)){
        uint32_t size=root->entries[i].size;
        if(!size)return;
        if((size+2047)/2048*2048<=capacity && !cd_read_retry(root->entries[i].starting_fad,__zone_tables_start,size)){
            cpu_cache_purge();scd_zone_code_zone=id;return;
        }
        break;
    }
    zone_tables_zone=-1;
    vdp2_tvmd_display_set();dbgio_printf("\x1b[H\x1b[2JCD ZONE TABLE ERROR\n%s",file);dbgio_flush();
    for(;;)sync_frame();
}
static void zone_tables_load(const cdfs_filelist_t *root){
    static const char *const files[]={"ZTR1.BIN","ZTR3.BIN","ZTR4.BIN","ZTR5.BIN","ZTR6.BIN","ZTR7.BIN","ZTR8.BIN"};
    if((int)stage_zone==zone_tables_zone)return;
    zone_tables_zone=(int)stage_zone;
    title_card_name_load();
    overlay_file_load(root,stage_zone<sizeof(files)/sizeof(files[0])?files[stage_zone]:0,stage_zone);
}
/* src/zone_code.h: the front-end overlay (cd/ZTR0.BIN). Its first word must match
   fe_overlay_magic (src/frontend.c) or the range holds another overlay. */
extern const volatile uint32_t fe_overlay_magic;
void scd_frontend_overlay_load(void){
    if(zone_tables_zone==(int)SCD_ZONE_FRONTEND)return;
    zone_tables_zone=(int)SCD_ZONE_FRONTEND;
    overlay_file_load(scd_cd_root_read(),"ZTR0.BIN",SCD_ZONE_FRONTEND);
    if(fe_overlay_magic!=0x46524e54u){
        zone_tables_zone=-1;scd_zone_code_zone=~0u;
        vdp2_tvmd_display_set();dbgio_printf("\x1b[H\x1b[2JCD FRONT END OVERLAY ERROR");dbgio_flush();
        for(;;)sync_frame();
    }
}
/* Reads stage packs [first,end) of the current act from the CD root into their
   low work RAM regions. A missing or oversized pack stops on an error screen. */
static void stage_packs_load(unsigned first,unsigned end){
    unsigned start=vblank_ticks;uint32_t bytes=0;
    const cdfs_filelist_t *root=scd_cd_root_read();
    const cdfs_filelist_entry_t *entries=root->entries;
    /* An act's object layout travels with its terrain. Every path that loads a
       zone's era packs, including the return from the special stage, which
       overwrites this region, therefore brings the matching layout with it. */
    int terrain=first<=PACK_COL3 && end>PACK_PPZ0;
    int extra=stage_zone && terrain && end<=PACK_OBJECTS?2:0;
    /* Sonic's round pose pack (SONIC_FRAME_PACKS) follows the terrain when its file changes. */
    static const char *sonic_frames_file;
    unsigned sonic=terrain && end<=PACK_SONIC_FRAMES;
    for(unsigned n=first;n<end+(unsigned)extra+sonic;n++){
        unsigned id=n<end?n:n==end+(unsigned)extra?PACK_SONIC_FRAMES:n==end?PACK_OBJECTS:PACK_ZONE_ART;
        if(n>=end && id==PACK_SONIC_FRAMES && sonic_frames_file && !strcmp(stage_pack_file(id),sonic_frames_file))continue;
        if(id==PACK_SONIC_FRAMES)sonic_frames_file=stage_pack_file(id);
        int loaded=0;
        for(unsigned i=0;i<root->entries_count;i++)if(!strcmp(entries[i].name,stage_pack_file(id))){
            uint32_t size=entries[i].size;
            loaded=size && (size+2047)/2048*2048<=stage_pack_regions[id].capacity && !cd_read_retry(entries[i].starting_fad,(void *)(uintptr_t)stage_pack_regions[id].address,size);
            if(loaded){stage_pack_bytes[id]=size;bytes+=size;}
            break;
        }
        if(!loaded){
            scd_stage_pack_mailbox[3]=id+1;scd_stage_pack_mailbox[0]=0x5350414b;
            vdp2_tvmd_display_set();dbgio_printf("\x1b[H\x1b[2JCD STAGE DATA ERROR\n%s",stage_pack_file(id));dbgio_flush();
            for(;;)sync_frame();
        }
    }
    if(terrain)zone_tables_load(root);
    if(stage_zone && terrain)scd_objects_layout((const scd_placement *)(uintptr_t)stage_pack_regions[PACK_OBJECTS].address,
        stage_pack_bytes[PACK_OBJECTS]/sizeof(scd_placement));
    scd_stage_pack_mailbox[1]=vblank_ticks-start;scd_stage_pack_mailbox[2]=bytes;scd_stage_pack_mailbox[0]=0x5350414b;
}

static void sprite_unpack(const uint8_t *data,const uint8_t *end,uint16_t *destination,unsigned words,int literals){
    unsigned pixels=0;
    const uint8_t *r=data;
    while(r<end){
        if(end-r<2){assert(false);return;}
        unsigned code=((unsigned)r[0]<<8)|r[1];r+=2;
        unsigned count=literals?(code&32767):code;int literal=literals && (code&32768);
        unsigned bytes=literal?count*2:2;
        if(!count || count>words-pixels || (unsigned)(end-r)<bytes){assert(false);return;}
        for(unsigned i=0;i<count;i++){
            destination[pixels++]=((unsigned)r[0]<<8)|r[1];if(literal)r+=2;
        }
        if(!literal)r+=2;
    }assert(pixels==words);
}
#include "sonic_view.inc"
/* Trimmed ring poses (sprite_draw), after the Sonic slots and before the
   diagnostic atlas at 0x10000. */
#define RING_TEXTURE_BASE (SONIC_TEXTURE_BASE+SONIC_TEXTURE_STRIDE*SONIC_TEXTURE_SLOTS)
#define RING_TEXTURE_HEIGHT 16u
#define RING_TEXTURE_BYTES (16u*RING_TEXTURE_HEIGHT/2)
_Static_assert(RING_TEXTURE_BASE%8==0 && RING_TEXTURE_BASE+4*RING_TEXTURE_BYTES<=0x10000,"ring poses overlap the diagnostic atlas");
static void sprite_init(void) {
    /* 148 HUD/results/Sonic commands, 9 title card pieces, 32 boss parts and the object pool. */
    sprite_commands=vdp1_cmdt_list_alloc(189+SCD_OBJECT_CAPACITY);
    assert(sprite_commands!=NULL);
    sprite_commands->count=4;
    memset(sprite_commands->cmdts,0,sizeof(vdp1_cmdt_t)*(189+SCD_OBJECT_CAPACITY));
    vdp1_cmdt_t *cmd=sprite_commands->cmdts;
    vdp1_cmdt_system_clip_coord_set(cmd);
    vdp1_cmdt_vtx_system_clip_coord_set(cmd,INT16_VEC2(319,223));
    vdp1_cmdt_local_coord_set(cmd+1);
    vdp1_cmdt_vtx_local_coord_set(cmd+1,INT16_VEC2(0,0));
    vdp1_cmdt_distorted_sprite_set(cmd+2);
    const vdp1_cmdt_draw_mode_t mode={.color_mode=VDP1_CMDT_CM_CLUT_16,.end_code_disable=true};
    vdp1_cmdt_draw_mode_set(cmd+2,mode);
    vdp1_cmdt_char_size_set(cmd+2,64,64);
    vdp1_cmdt_char_base_set(cmd+2,VDP1_VRAM(0x10000));
    sonic_command_template=cmd[2];
    vdp1_cmdt_end_set(cmd+3);
    sprite_unpack(sonic_motion,sonic_motion_end,(uint16_t *)VDP1_VRAM(0x10000),21*1040,0);
    assert(0x10000+21*2080<=OBJECT_ATLAS_BASE);
    assert(OBJECT_ATLAS_BASE+OBJECT_ART_BYTES<=0x76800);
    /* The command list stays below 0x2800 in the VDP1 command partition, where the HUD font and title card live. */
    assert((189+SCD_OBJECT_CAPACITY)*32<=0x2800);
    sprite_unpack(object_art,object_art_end,(uint16_t *)VDP1_VRAM(OBJECT_ATLAS_BASE),OBJECT_ART_BYTES/2,1);
    /* Original high-priority common-palette art uses the indexed priority
       bank shared with results/HUD. Convert each shared texture only once. */
    uint16_t result_colors[16]={0};unsigned result_color_count=0;
    for(unsigned f=0;f<OBJECT_FRAME_COUNT;f++)if(object_high_priority[f]){
        assert(object_stage_palette[f]==0);
        int converted=0;for(unsigned g=0;g<f;g++)if(object_high_priority[g] && object_raw_offsets[g]==object_raw_offsets[f]){converted=1;break;}
        if(converted)continue;
        volatile uint16_t *clut=(volatile uint16_t *)VDP1_VRAM(OBJECT_ATLAS_BASE+object_raw_offsets[f]+object_widths[f]*object_heights[f]/2);
        for(unsigned c=1;c<16;c++)if(clut[c]){
            unsigned color=0;while(color<result_color_count && result_colors[color]!=clut[c])color++;
            if(color==result_color_count){assert(result_color_count<16);result_colors[result_color_count++]=clut[c];MEMORY_WRITE(16,VDP2_CRAM_MODE_0_OFFSET(0,0,80+color),clut[c]);}
            clut[c]=0x4050+color;
        }
    }
    for(unsigned i=0;i<59*64;i++)((volatile uint16_t *)VDP1_VRAM(0x2800))[i]=(hud_font[i*2] || hud_font[i*2+1])?0x4040:0;
    /* Title card textures after the HUD font (Level/_Objects/Title Card), below the special
       stage's 0x8000 textures. Object art ends below 0x76800, where the UFO textures start. */
    assert(0x4600+TITLE_CARD_BYTES<=0x8000);
    sprite_unpack(title_card_art,title_card_art_end,(uint16_t *)VDP1_VRAM(0x4600),TITLE_CARD_BYTES/2,1);
    for(unsigned f=0;f<9;f++)title_card_priority(f);
    const uint16_t hud_colors[]={0xffff,0x8800,0x94a5,0x83e0,0x83ff};
    for(unsigned i=0;i<5;i++)MEMORY_WRITE(16,VDP2_CRAM_MODE_0_OFFSET(0,0,64+i),hud_colors[i]);
}

static void hud_text(unsigned *count,int x,int y,const char *text) {
    const vdp1_cmdt_draw_mode_t mode={.color_mode=VDP1_CMDT_CM_RGB_32768,.end_code_disable=true};
    for(;*text;text++,x+=8) {
        unsigned c=(unsigned char)*text;if(c<33 || c>90)continue;
        vdp1_cmdt_t *cmd=sprite_commands->cmdts+(*count)++;
        memset(cmd,0,sizeof(*cmd));vdp1_cmdt_normal_sprite_set(cmd);
        vdp1_cmdt_draw_mode_set(cmd,mode);vdp1_cmdt_char_size_set(cmd,8,8);
        vdp1_cmdt_char_base_set(cmd,VDP1_VRAM(0x2800+(c-32)*128));cmd->cmd_xa=x;cmd->cmd_ya=y;
    }
}
static void hud_panel(unsigned *count,int x,int y,int width,int height,uint16_t color) {
    vdp1_cmdt_t *cmd=sprite_commands->cmdts+(*count)++;
    memset(cmd,0,sizeof(*cmd));vdp1_cmdt_polygon_set(cmd);
    const vdp1_cmdt_draw_mode_t mode={.color_mode=VDP1_CMDT_CM_RGB_32768,.end_code_disable=true};
    vdp1_cmdt_draw_mode_set(cmd,mode);cmd->cmd_colr=0x4040+(color==0x8800?1:color==0x94a5?2:color==0x83e0?3:color==0x83ff?4:0);
    cmd->cmd_xa=cmd->cmd_xd=x;cmd->cmd_xb=cmd->cmd_xc=x+width-1;
    cmd->cmd_ya=cmd->cmd_yb=y;cmd->cmd_yc=cmd->cmd_yd=y+height-1;
}
static void audio_hud(unsigned *count) {
    char text[40];scd_audio_diagnostics d=scd_audio_get_diagnostics();
    hud_panel(count,12,52,296,156,0x8800);
    hud_text(count,20,60,"AUDIO TEST V0.063");
    hud_text(count,20,76,d.ready?"DRIVER READY":"DRIVER TIMEOUT");
    snprintf(text,sizeof(text),"DATA %u RAM %u RUN %u",d.bank,d.copy,d.heartbeat%10000);hud_text(count,20,92,text);
    snprintf(text,sizeof(text),"CD INIT %d TOC %u",d.cd_init,d.toc);hud_text(count,20,108,text);
    snprintf(text,sizeof(text),"TRACK %u STATE %u",d.track,d.state);hud_text(count,20,124,text);
    if(d.master==UINT32_MAX)snprintf(text,sizeof(text),"CODE %u MVOL -- ACK %u",d.driver_copy,d.start);
    else snprintf(text,sizeof(text),"CODE %u MVOL %u ACK %u",d.driver_copy,d.master&15,d.start);
    hud_text(count,20,140,text);
    snprintf(text,sizeof(text),"CD L %u R %u",d.left&255,d.right&255);hud_text(count,20,156,text);
    snprintf(text,sizeof(text),"60 STEPS %u VB MAX %u",pacing_window_blanks,pacing_window_max);hud_text(count,20,172,text);
    snprintf(text,sizeof(text),"INIT RESPONSE %04X",d.init_response);hud_text(count,20,188,text);
}
/* Preserve each canonical sprite origin, including vertical flips. */
static int object_top(unsigned frame,unsigned flags){
    return flags&2?object_canvases[frame]-object_tops[frame]-object_heights[frame]:object_tops[frame];
}
/* MM3 explosion CLUT copies and their line-0 image (src/boss_r8.c
   z8_explosion_cluts), in the VRAM gap below the zone art arena; 2 once live. */
#define MM3_EXPLOSION_CLUTS (SCD_ZONE_ART_BASE-(OBJECT_BASE_45-OBJECT_BASE_24+1)*32u)
_Static_assert(OBJECT_ATLAS_BASE+OBJECT_ART_BYTES<=MM3_EXPLOSION_CLUTS && OBJECT_BASE_45>OBJECT_BASE_24,"MM3 explosion CLUTs overlap the object atlas");
static uint8_t mm3_explosion_state;
static void object_clut_refresh(unsigned frame){
    if(object_stage_palette[frame]!=1 || object_clut_applied[frame]==object_clut_epoch)return;
    volatile uint16_t *clut=(volatile uint16_t *)VDP1_VRAM(OBJECT_ATLAS_BASE+object_raw_offsets[frame]+object_widths[frame]*object_heights[frame]/2);
    clut[0]=0;for(unsigned c=1;c<16;c++)clut[c]=water_raster_active()?0x0090+object_clut_indices[frame][c]:animated_palette[16+object_clut_indices[frame][c]];
    object_clut_applied[frame]=object_clut_epoch;
}
/* A frame's CLUT (VDP1 colour address); MM3 explosions use their copies once live. */
static unsigned object_colr(unsigned frame){
    if(mm3_explosion_state==2 && frame-OBJECT_BASE_24<OBJECT_BASE_45-OBJECT_BASE_24)return (MM3_EXPLOSION_CLUTS+(frame-OBJECT_BASE_24)*32)/8;
    return (OBJECT_ATLAS_BASE+object_raw_offsets[frame]+object_widths[frame]*object_heights[frame]/2)/8;
}
static void object_sprite(unsigned *count,unsigned frame,int x,int y,unsigned flags){
    assert(frame<OBJECT_FRAME_COUNT);
    object_clut_refresh(frame);
    vdp1_cmdt_t *cmd=sprite_commands->cmdts+(*count)++;
    memset(cmd,0,sizeof(*cmd));vdp1_cmdt_normal_sprite_set(cmd);
    const vdp1_cmdt_draw_mode_t mode={.color_mode=VDP1_CMDT_CM_CLUT_16,.end_code_disable=true};
    vdp1_cmdt_draw_mode_set(cmd,mode);vdp1_cmdt_char_size_set(cmd,object_widths[frame],object_heights[frame]);
    vdp1_cmdt_char_base_set(cmd,VDP1_VRAM(OBJECT_ATLAS_BASE+object_raw_offsets[frame]));
    cmd->cmd_colr=object_colr(frame);
    vdp1_cmdt_char_flip_set(cmd,(vdp1_cmdt_char_flip_t)(flags<<4));
    cmd->cmd_xa=x-object_widths[frame]/2;cmd->cmd_ya=y-32-object_y_shifts[frame]+object_top(frame,flags);
}
#include "zone_object_view.inc"
#include "hud_view.inc"
/* Collision Chaos (BOSS_3.C, GATE.C), Tidal Tempest (BOSS_4.C, BOSS_4_2.C, WALL4.C) and
   Quartz Quadrant (BOSS_5.C) boss actors draw from the Act 3 zone art, kinds 240-249
   (tools/extract_mmd.py CC_BOSS_KIND, TT_BOSS_KIND, QQ_BOSS_KIND). A pose is one record,
   or consecutive part records drawn back to front (per-piece families such as egg5). */
static void boss_zone_sprite(unsigned *count,scd_boss_view b,int ox,int oy){
    /* Retail PLC 19 updates the entry textures through update 106 (C) or
       105 (D). Later poses use the complete-fight records. */
    unsigned age=scd_boss6_art_age();
    unsigned entry=stage_zone==4 && b.kind>=240 && b.kind<=243 &&
        age<(era==3?106u:107u);
    if(zone_art_streaming)return;
    const uint8_t *f=zone_art_find(b.kind,entry?1:0,b.frame);
    /* Before BOSS_8.C's fight bank loads, egg8 has no art (retail VRAM holds stage tiles). */
    if(!f && stage_zone==6)return;
    if(!f)abort();
    const uint8_t *end=zone_art.frames+zone_art.count*SCD_ZONE_ART_RECORD;
    unsigned kind=scd_zone_art_u16(f),pose=scd_zone_art_u16(f+2);
    for(;f<end && scd_zone_art_u16(f)==kind && scd_zone_art_u16(f+2)==pose;f+=SCD_ZONE_ART_RECORD){
    if(*count+1>=189+SCD_OBJECT_CAPACITY)return;
    unsigned w=scd_zone_art_u16(f+8),h=scd_zone_art_u16(f+10),offset=scd_zone_art_bitmap(f),clut=scd_zone_art_clut(f);
    int left=scd_zone_art_i16(f+12),top=scd_zone_art_i16(f+14);
    left=b.flags&1?-left-(int)w:left;top=b.flags&2?-top-(int)h:top;
    int x=ox+left,y=oy+top;
    if(x>=320 || x+(int)w<=0 || y>=224 || y+(int)h<=0)continue;
    vdp1_cmdt_t *cmd=sprite_commands->cmdts+(*count)++;
    memset(cmd,0,sizeof(*cmd));vdp1_cmdt_normal_sprite_set(cmd);
    const vdp1_cmdt_draw_mode_t mode={.color_mode=VDP1_CMDT_CM_CLUT_16,.end_code_disable=true};
    vdp1_cmdt_draw_mode_set(cmd,mode);vdp1_cmdt_char_size_set(cmd,w,h);
    vdp1_cmdt_char_base_set(cmd,VDP1_VRAM(SCD_ZONE_ART_BASE+offset));
    cmd->cmd_colr=(SCD_ZONE_ART_BASE+clut)/8;
    vdp1_cmdt_char_flip_set(cmd,(vdp1_cmdt_char_flip_t)((b.flags&3)<<4));
    cmd->cmd_xa=x;cmd->cmd_ya=y;
    }
}
/* colorset2 and genecolor write CRAM line 1; the boss zone art CLUTs copy it.
   -1 after each zone art load, which restores the stage palette colours. */
static int boss_clut_state=-1;
static void boss_zone_cluts(int state){
    /* SS line 1; MM3 lines 1 and 3 (boss, Amy and room fades): every zone sprite follows. */
    static uint16_t ss_line[32];
    unsigned mm=stage_zone==6;
    /* MM: only the changed line 1/3 entries, and each shared CLUT once. */
    uint64_t changed=~0ull;
    if(stage_zone==5 || mm){
        if(boss_clut_state!=-1 && !memcmp(ss_line,animated_palette+16,32) && (!mm || !memcmp(ss_line+16,animated_palette+48,32)))return;
        if(mm && boss_clut_state!=-1){
            changed=0;
            for(unsigned i=0;i<16;i++){if(ss_line[i]!=animated_palette[16+i])changed|=1ull<<(16+i);if(ss_line[16+i]!=animated_palette[48+i])changed|=1ull<<(48+i);}
            /* zone_cycle_cluts already wrote the COL8 cycle entries through its
               slots (unless they overflowed): a cycle tick alone walks no records. */
            if(zone_cycle_count<ZONE_CYCLE_SLOTS)changed&=~zone_cycle_entries;
        }
        memcpy(ss_line,animated_palette+16,32);if(mm)memcpy(ss_line+16,animated_palette+48,32);
        if(!changed){boss_clut_state=state;return;}
    }else if(state==boss_clut_state)return;
    static uint32_t seen[SCD_ZONE_ART_CAPACITY/32/32];
    if(mm)memset(seen,0,sizeof(seen));
    for(unsigned i=0;i<zone_art.count;i++){
        const uint8_t *f=zone_art.frames+i*SCD_ZONE_ART_RECORD;
        unsigned kind=scd_zone_art_u16(f);
        if(stage_zone!=5 && !mm && !((kind>=240 && kind<=253) || (kind>=496 && kind<=499)))continue;
        unsigned at=scd_zone_art_clut(f);
        if(mm){unsigned b=at/32;if(seen[b/32]>>(b%32)&1)continue;seen[b/32]|=1u<<(b%32);}
        volatile uint16_t *clut=(volatile uint16_t *)VDP1_VRAM(SCD_ZONE_ART_BASE+at);
        for(unsigned c=1;c<16;c++){unsigned ref=scd_zone_art_u16(f+16+c*2);if(((ref>=16 && ref<32) || (mm && ref>=48 && ref<64)) && (changed>>ref&1))clut[c]=animated_palette[ref];}
    }
    boss_clut_state=state;
}
/* src/objects_mm_hota8.inc room palette entries and src/boss_r8.c's lpcolorwk. */
const uint8_t (*scd_objects_mm_room_palette(unsigned *dirty))[4];
static void mm3_palette(uint16_t *pal){
    unsigned dirty;const uint8_t (*room)[4]=scd_objects_mm_room_palette(&dirty);(void)dirty;
    for(unsigned i=0;i<64;i++)if(room[i][3])pal[i]=0x8000|(room[i][0]/32*31/7)|((room[i][1]/32*31/7)<<5)|((room[i][2]/32*31/7)<<10);
    scd_boss8_palette(pal);
    r8_explosion_cluts(pal,&mm3_explosion_state,(volatile uint16_t *)VDP1_VRAM(MM3_EXPLOSION_CLUTS),(const volatile uint16_t *)VDP1_VRAM(OBJECT_ATLAS_BASE),
        object_raw_offsets,object_widths,object_heights,OBJECT_BASE_24,OBJECT_BASE_45-OBJECT_BASE_24);
}

static void result_number(unsigned *count,unsigned value,unsigned digits,int x,int y){
    unsigned divisor=1;for(unsigned n=1;n<digits;n++)divisor*=10;
    int nonzero=0;for(unsigned n=0;n<digits;n++){
        unsigned digit=value/divisor;value%=divisor;divisor/=10;
        if(digit || nonzero || n+1==digits){object_sprite(count,OBJECT_BASE_202+digit,x+4+n*8,y,0);nonzero=1;}
    }
}
static void results_draw(unsigned *count){
    scd_act_state result=scd_act_get();if(result.phase<SCD_ACT_SLIDE || result.slide<9)return;
    int title_x=-128+result.slide*8;
    int counter_x=384-(result.slide<34?result.slide:34)*8;
    unsigned base=OBJECT_BASE_201;
    object_sprite(count,base+(result.good_future?3:0),title_x,76,0);
    object_sprite(count,stage_act==2?OBJECT_BASE_212+result.good_future:stage_act?OBJECT_BASE_210+result.good_future:base+(result.good_future?4:1),title_x,76,0);
    object_sprite(count,base+2,counter_x,144,0);
    result_number(count,player.score,7,counter_x+72,112);
    result_number(count,result.time_bonus,5,counter_x+88,160);
    result_number(count,result.ring_bonus,5,counter_x+88,136);
}

static void amy_sprite_record(unsigned frame,unsigned type,unsigned flags,int x,int y){
    if(feature_object!=SCD_OBJ_AMY || scd_world_mailbox[57]>=24)return;
    unsigned record=58+3*scd_world_mailbox[57]++;
    scd_world_mailbox[record]=(frame<<16)|(type<<8)|flags;
    scd_world_mailbox[record+1]=((uint32_t)(uint16_t)(x+camera_x)<<16)|(uint16_t)(y+camera_y);
    scd_world_mailbox[record+2]=((uint32_t)(uint16_t)x<<16)|(uint16_t)y;
}

#include "gameplay_video.inc"
#include "sprite_order.h"
/* Gameplay VDP1 VRAM, in address order; each region ends before the next.
   Title (0x8100-OBJECT_ATLAS_BASE) and special modes (0x8000-0x10000, 0x76800) reuse
   parts of it; load_era() restores the art and sonic_view_reset() starts a
   new Sonic/ring texture generation before gameplay draws again. */
_Static_assert((189+SCD_OBJECT_CAPACITY+1)*32<=0x2800,"command table overlaps the HUD font");
_Static_assert(0x2800+59*64*2<=0x4600,"HUD font overlaps the title card");
_Static_assert(0x4600+TITLE_CARD_BYTES<=0x8000,"title card overlaps the original HUD");
_Static_assert(0x8000+HUD_ORIGINAL_BYTES<=SONIC_TEXTURE_BASE,"original HUD overlaps Sonic");
_Static_assert(RING_TEXTURE_BASE>=SONIC_TEXTURE_BASE+SONIC_TEXTURE_STRIDE*SONIC_TEXTURE_SLOTS,"ring poses overlap Sonic");
_Static_assert(RING_TEXTURE_BASE+4*RING_TEXTURE_BYTES<=0x10000,"ring poses overlap the diagnostic atlas");
_Static_assert(0x10000+21*1040*2<=SONIC_HIGH_LUT && SONIC_HIGH_LUT+32<=OBJECT_ATLAS_BASE,"diagnostic atlas or high Sonic LUT overlaps the object atlas");
_Static_assert(OBJECT_ATLAS_BASE+OBJECT_ART_BYTES<=SCD_ZONE_ART_BASE,"object atlas overlaps the zone art arena");
static int stage_background_by,stage_background_pending;
static void draw_stage_background(int by,int deferred);
static void back_color_commit(void);
/* Shared complete Sonic/trail body from the existing natural warp path. */
static void warp_sonic_trails(unsigned *count,unsigned t){
    int sy=t<21?288-(int)t*8:t<141?120:120-((int)t-141)*8;
    for(unsigned trail=3;trail>0;trail--)object_sprite(count,OBJECT_BASE_200+((t+trail)/3)%5,160,sy+trail*24,0);
    object_sprite(count,OBJECT_BASE_200+(t/3)%5,160,sy,0);
}
static void sprite_draw(void) {
    profile_sprite_begin();
    if(!floor_mode)gameplay_clear_begin();
    scd_world_mailbox[57]=0;
    int static_sprite=floor_mode || diagnostic_mode;
    /* The departure hold covers the entire stage with opaque white. Avoid
       drawing covered actors/HUD behind it: overdraw can miss a refresh. */
    int white_hold=!stage_select_single_program && !static_sprite && !audio_test && !warp_timer && scd_world_get().ticks>=210;
    scd_profile_span(3,1);
    scd_object_view objects[SCD_OBJECT_CAPACITY];
    unsigned total=(static_sprite || audio_test || warp_timer || white_hold)?0:scd_objects_views(objects,SCD_OBJECT_CAPACITY);
    unsigned count=2;
    scd_boss_view boss[32];
    unsigned parts=(!static_sprite && !audio_test && !warp_timer && !white_hold)?scd_boss_views(boss,32):0;
    uint8_t effect_ids[9];unsigned effects=0;
    if(!static_sprite && !audio_test && !warp_timer && !white_hold)
        for(unsigned i=0;i<9;i++)if((effect_runtime.submitted&(1u<<i)) && effect_runtime.actors[i].mapping)effect_ids[effects++]=i;
    uint8_t priorities[SCD_DRAW_CAPACITY],order[SCD_DRAW_CAPACITY];
    /* Player, reserved effects in original slot order, ordinary native actors,
       then boss action calls.
       Boss views arrive back-to-front; reverse them for the queue input. */
    /* Sonic queues at its own sprpri, like any actor: 0 while dying draws it
       in front of priority 0/1 actors (COLI3.C:556, ACTION.C:170). */
    priorities[0]=player.priority;
    for(unsigned i=0;i<effects;i++)priorities[i+1]=effect_runtime.actors[effect_ids[i]].priority;
    /* Every spawnable type has a priority (tools/test_sprite_priority.py
       lists any that does not). A missed type draws at 3 instead of
       aborting inside the frame (the TT1 first-update hang). */
    for(unsigned i=0;i<total;i++){int p=scd_ppz_priority(objects[i]);priorities[1+effects+i]=(uint8_t)(p<0?3:p);}
    for(unsigned i=0;i<total;i++){const scd_object_view *o=&objects[i];
        scd_ta.seen|=o->type==SCD_OBJ_TIMEPOST?(o->subtype>=8?1:o->subtype?0:2):o->type==SCD_OBJ_AMY?4:o->type==SCD_OBJ_BIG_RING?8:0;}
    for(unsigned i=0;i<parts;i++)priorities[1+effects+total+i]=boss[parts-1-i].priority;
    unsigned draws=1+effects+total+parts;
    int ordered=scd_sprite_order(priorities,draws,order);assert(ordered==(int)draws);
    scd_profile_span(3,0);
    if(ordered<0)abort();
    vdp1_cmdt_t *sprite=NULL;
    scd_world_mailbox[40]=0xffffffff;
    scd_zone_art_mailbox[1]=player.frame;scd_zone_art_mailbox[7]=0;
    const vdp1_cmdt_draw_mode_t mode={.color_mode=VDP1_CMDT_CM_RGB_32768,.end_code_disable=true};
    for(unsigned draw=0;draw<draws;draw++){
    unsigned entry=order[draw];
    if(entry && entry<=effects){
        const scd_powerup_visual *e=&effect_runtime.actors[effect_ids[entry-1]];
        int x,y;
        if(scd_powerup_screen(e,camera_x,camera_y,&x,&y))
            object_sprite(&count,e->mapping<8?OBJECT_BASE_205+e->mapping-1:OBJECT_BASE_3+e->mapping-8,x,y,e->sprite_flags&3);
        continue;
    }
    if(entry>effects+total){
        scd_boss_view b=boss[parts-1-(entry-effects-total-1)];
        int x=b.x-camera_x,y=b.y-camera_y;
        if(b.kind==SCD_BOSS_KIND_EXPLOSION){if(x>=-64 && x<=383 && y>=-64 && y<=287)object_sprite(&count,OBJECT_BASE_24+b.frame,x,y,b.flags);}
        else if(b.kind)boss_zone_sprite(&count,b,x,y);
        else if(x>=-64 && x<=383 && y>=-64 && y<=287)object_sprite(&count,OBJECT_BASE_66+b.frame,x,y,b.flags);
        continue;
    }
    if(!entry){
    sprite=sprite_commands->cmdts+count++;*sprite=sonic_command_template;
    sprite->cmd_xa=floor_mode?128:(static_sprite?(int)stage.start_x:player.x/65536)-camera_x-32;
    sprite->cmd_ya=floor_mode?154:(static_sprite?(int)stage.start_y:player.y/65536)-camera_y-32;
    /* The original dispatcher chooses angled mappings AND global flips.
       Do not continuously rotate this already angle-specific artwork. The
       floor/diagnostic scene intentionally retains its fixed legacy pose. */
#if SCD_FRAME_PROFILE
    uint16_t sonic_at=cpu_frt_count_get();
#endif
    unsigned texture=static_sprite?0x10000:sonic_view_texture(player.mapping);
#if SCD_FRAME_PROFILE
    profile_values[30]|=(uint32_t)(uint16_t)(cpu_frt_count_get()-sonic_at)<<16;
#endif
    if(!static_sprite){
        /* Queue the pose the animation's next step would show for decoding
           in this frame's VDP1 wait (sprite_draw); see sonic_view.inc. */
        const scd_sonic_animation state={player.animation,player.animation_previous,player.animation_cursor,
            player.animation_timer,player.mapping,player.render_flags};
        extern unsigned char chibi_flag;
        int next=scd_sonic_animation_next(&state,player.speed,player.angle,player.flags,player.control,chibi_flag);
        if(next>=0)sonic_view_prefetch((unsigned)next);
    }
    vdp1_cmdt_normal_sprite_set(sprite);
    vdp1_cmdt_char_base_set(sprite,VDP1_VRAM(texture));sprite->cmd_colr=(texture+2048)/8;
    if(!static_sprite && player.high)sprite->cmd_colr=sonic_view_high_lut();
    vdp1_cmdt_char_flip_set(sprite,(vdp1_cmdt_char_flip_t)(static_sprite?0:(player.render_flags&3)<<4));
    int hidden=!static_sprite && (warp_timer || white_hold || player.display_hidden);
    if(hidden)sprite->cmd_xa=-100;
    if(!static_sprite){
        scd_sonic_view_mailbox[0]=0;
        scd_sonic_view_mailbox[2]=player.frame;scd_sonic_view_mailbox[3]=player.mapping;
        scd_sonic_view_mailbox[4]=player.render_flags;scd_sonic_view_mailbox[5]=player.x;
        scd_sonic_view_mailbox[6]=player.y;scd_sonic_view_mailbox[7]=camera_x;
        scd_sonic_view_mailbox[8]=camera_y;scd_sonic_view_mailbox[9]=texture;
        scd_sonic_view_mailbox[10]=(player.animation<<24)|(player.animation_previous<<16)|(player.animation_cursor<<8)|player.animation_timer;
        scd_sonic_view_mailbox[11]=era|(stage_act<<8);scd_sonic_view_mailbox[12]=palette_frame;
        scd_sonic_view_mailbox[13]=hidden;
        scd_sonic_view_mailbox[16]=replay_active?replay_test:UINT32_MAX;
        scd_sonic_view_mailbox[17]=(player.path<<16)|player.flags;
        scd_sonic_view_mailbox[1]++;scd_sonic_view_mailbox[0]=0x534F4E56;
        if(!hidden && !warp_timer)amy_sprite_record(player.mapping,1,player.render_flags&3,player.x/65536-camera_x,player.y/65536-camera_y);
    }else scd_sonic_view_mailbox[0]=0;
    continue;
    }
        scd_object_view o=objects[entry-effects-1];int x=o.x-camera_x,y=o.y-camera_y;
        /* Rings (a ring-loss scatter adds 32 at once) take a prebuilt command.
           The atlas stores each ring pose on a 64-pixel canvas whose opaque
           pixels are columns 24-39, and VDP1 time follows the texture area:
           draw a 16-pixel copy of those columns, same rows, CLUT and screen
           position. The copies are rebuilt with the Sonic texture slots, whose
           generation changes whenever title or special modes reuse the VRAM. */
        if((o.type==SCD_OBJ_RING || o.type==SCD_OBJ_LOST_RING) && !o.flags && o.frame<4 && feature_object!=o.type){
            if(x < -32 || x>351 || y < -32 || y>255)continue;
            scd_profile_span(2,1);
            object_clut_refresh(18+o.frame);
            static vdp1_cmdt_t ring_command[4];static uint32_t ring_generation=UINT32_MAX;
            if(ring_generation!=scd_sonic_view_mailbox[15]){
                for(unsigned pose=0;pose<4;pose++){
                    unsigned frame=18+pose,w=object_widths[frame],h=object_heights[frame];
                    assert(w==64 && h<=RING_TEXTURE_HEIGHT);
                    const volatile uint16_t *src=(const volatile uint16_t *)VDP1_VRAM(OBJECT_ATLAS_BASE+object_raw_offsets[frame]);
                    volatile uint16_t *dst=(volatile uint16_t *)VDP1_VRAM(RING_TEXTURE_BASE+pose*RING_TEXTURE_BYTES);
                    for(unsigned row=0;row<h;row++)for(unsigned k=0;k<4;k++)dst[row*4+k]=src[row*16+6+k];
                    vdp1_cmdt_t *cmd=&ring_command[pose];
                    memset(cmd,0,sizeof(*cmd));vdp1_cmdt_normal_sprite_set(cmd);vdp1_cmdt_draw_mode_set(cmd,mode);
                    const vdp1_cmdt_draw_mode_t object_mode={.color_mode=VDP1_CMDT_CM_CLUT_16,.end_code_disable=true};
                    vdp1_cmdt_draw_mode_set(cmd,object_mode);
                    vdp1_cmdt_char_size_set(cmd,16,h);vdp1_cmdt_char_base_set(cmd,VDP1_VRAM(RING_TEXTURE_BASE+pose*RING_TEXTURE_BYTES));
                    cmd->cmd_colr=(OBJECT_ATLAS_BASE+object_raw_offsets[frame]+w*h/2)/8;
                    vdp1_cmdt_char_flip_set(cmd,(vdp1_cmdt_char_flip_t)0);
                    cmd->cmd_xa=24-(int)w/2;cmd->cmd_ya=-32-object_y_shifts[frame]+object_top(frame,0);
                }
                ring_generation=scd_sonic_view_mailbox[15];
            }
            vdp1_cmdt_t *cmd=sprite_commands->cmdts+count++;*cmd=ring_command[o.frame];
            cmd->cmd_xa+=x;cmd->cmd_ya+=y;
            scd_profile_span(2,0);
            continue;
        }
        if(o.type==SCD_OBJ_DRUMR3 && o.frame==10)continue; /* Original zero-piece pose. */
        if((o.type==SCD_OBJ_MOVIE3 && o.frame==1) || (o.type==SCD_OBJ_FRIEND3 && o.frame==2))continue;
        if((o.type==SCD_OBJ_EMIE3 && (o.frame==8 || o.frame==9 || o.frame==13)) || (o.type==SCD_OBJ_MECASNC3 && o.frame==14))continue;
        /* Tidal Tempest actors draw from the R4 ZAR3 pack (kind type|subtype<<8)
           when it holds the pose (zone_object_sprite aborts on a missing one). */
        /* The R4 test's record is passed on: one lookup per actor per frame. A far
           actor draws nothing on either branch (zone_art_far), so it skips the lookup;
           a feature fixture still takes the branch its record selects. */
        const uint8_t *zone_record=NULL;
        if(scd_zone_local(o.type) || (((o.type>=SCD_OBJ_R4_FIRST && o.type<=SCD_OBJ_R4_LAST) || o.type==SCD_OBJ_SCREW_F) && ((o.type!=feature_object && zone_art_far(x,y)) || (zone_record=zone_art_find(o.type,o.subtype,o.frame)))) || o.type==SCD_OBJ_BOBIN || o.type==SCD_OBJ_FRIP || (o.type>=SCD_OBJ_WALL4 && o.type<=SCD_OBJ_CC_POINTS) || (o.type>=SCD_OBJ_DRUMR3 && o.type<=SCD_OBJ_MECASNC3) || o.type==SCD_OBJ_SIKAKE33 ||
           /* Capsule flowers and every CC/TT/QQ/SS/MM (and WW Acts 1-2) seed/growth pose use their own zone art. */
           (o.type==SCD_OBJ_FLOWER && (stage_zone==1 || stage_zone==2 || stage_zone==3 || stage_zone==5 || stage_zone==6 || (stage_zone==4 && stage_act<2)))){zone_object_sprite_record(&count,o,x,y,zone_record);continue;}
        if(o.type==SCD_OBJ_CC_GENERATOR){cc_generator_sprite(&count,o,x,y);continue;}
        if(feature_object && o.type==feature_object){scd_world_mailbox[40]=(o.type<<8)|o.frame;scd_world_mailbox[41]=((uint32_t)(uint16_t)x<<16)|(uint16_t)y;}
        if(feature_object==SCD_OBJ_MOVING_SPRING && o.type==SCD_OBJ_SPRING)scd_world_mailbox[42]=((uint32_t)(uint16_t)x<<16)|(uint16_t)y;
        int margin=(o.type==SCD_OBJ_DISC || o.type==SCD_OBJ_CAPSULE)?64:32;
        if(x < -margin || x>319+margin || y < -margin || y>223+margin)continue;
        if(o.type==SCD_OBJ_SWING && o.frame==1)scd_world_mailbox[136]=((uint32_t)(uint16_t)o.x<<16)|(uint16_t)o.y;
        unsigned frame;
        if(o.type==SCD_OBJ_SPRING)frame=(o.subtype&2?9:0)+(o.subtype&4?3:o.subtype&8?6:0)+o.frame;
        else if(o.type==SCD_OBJ_RING || o.type==SCD_OBJ_LOST_RING)frame=o.frame<4?18+o.frame:OBJECT_RING_SPARKLE_BASE+o.frame-4;
        else if(o.type==SCD_OBJ_AMY)frame=OBJECT_BASE_47+o.frame;
        else if(o.type==SCD_OBJ_AMY_HEART)frame=OBJECT_BASE_48+o.frame-8;
        else if(o.type==SCD_OBJ_LOG_SHADOW)frame=OBJECT_BASE_51+o.frame;
        else if(o.type==SCD_OBJ_PROJECTOR)frame=OBJECT_BASE_46+o.frame;
        else if(o.type==SCD_OBJ_ANIMAL)frame=(o.subtype&128?OBJECT_BASE_208:OBJECT_BASE_36)+((o.subtype&127)?3:0)+o.frame;
        else if(o.type==SCD_OBJ_EXPLOSION && o.subtype==2)frame=OBJECT_BASE_207+o.frame;
        else if(o.type==SCD_OBJ_SCENERY)frame=OBJECT_BASE_50+o.frame;
        else if(o.type==SCD_OBJ_DOOR)frame=OBJECT_BASE_13+o.frame;
        else if(o.type==SCD_OBJ_DOOR_V)frame=OBJECT_BASE_53+o.frame;
        else if(o.type==SCD_OBJ_MOVING_SPRING)frame=OBJECT_BASE_15+o.frame;
        else if(o.type==SCD_OBJ_DISC)frame=OBJECT_BASE_9+o.frame;
        else if(o.type==SCD_OBJ_SONIC_HOLE)frame=OBJECT_BASE_49;
        else if(o.type==SCD_OBJ_GOAL)frame=OBJECT_BASE_22;
        else if(o.type==SCD_OBJ_SIGN)frame=OBJECT_BASE_23+o.frame;
        else if(o.type==SCD_OBJ_WALL)frame=OBJECT_BASE_54+o.frame;
        else if(o.type==SCD_OBJ_CHECKPOINT)frame=OBJECT_BASE_19+o.frame;
        else if(o.type==SCD_OBJ_PLATFORM)frame=OBJECT_BASE_33+o.frame;
        else if(o.type==SCD_OBJ_SWING)frame=OBJECT_BASE_41+o.frame;
        else if(o.type==SCD_OBJ_SPRINGBOARD)frame=OBJECT_BASE_40+o.frame;
        else if(o.type==SCD_OBJ_FLOAT_BLOCK)frame=OBJECT_BASE_18+o.frame;
        else if(o.type==SCD_OBJ_RAMP)frame=OBJECT_BASE_42+o.frame;
        else if(o.type==SCD_OBJ_RAMP_PLANT)frame=OBJECT_BASE_44+o.frame;
        else if(o.type==SCD_OBJ_ANTON)frame=OBJECT_BASE_63+o.frame;
        /* Act 2 collapse frames are numbered from OBJECT_BASE_211 (collapse.inc). */
        else if(o.type==SCD_OBJ_COLLAPSE)frame=(stage_act==1?OBJECT_BASE_211:0)+o.frame;
        else if(o.type==SCD_OBJ_MOSQUI)frame=OBJECT_BASE_61+o.frame;
        else if(o.type==SCD_OBJ_PATABATA)frame=OBJECT_BASE_62+o.frame;
        else if(o.type==SCD_OBJ_TAGATAGA)frame=OBJECT_BASE_64+o.frame;
        else if(o.type==SCD_OBJ_TAMABBOH)frame=OBJECT_BASE_34+o.frame;
        else if(o.type==SCD_OBJ_TIMEPOST)frame=o.subtype<8?OBJECT_BASE_204+o.frame:o.frame<4?OBJECT_BASE_25+o.frame:OBJECT_BASE_203+o.frame-4;
        else if(o.type==SCD_OBJ_MONITOR_ITEM)frame=o.frame>4?OBJECT_BASE_213+o.frame-5:OBJECT_BASE_26+o.frame;
        else if(o.type==SCD_OBJ_CAPSULE)frame=OBJECT_BASE_21+o.frame;
        else if(o.type==SCD_OBJ_BIG_RING)frame=o.subtype?OBJECT_BASE_214+o.frame:OBJECT_BASE_20+o.frame;
        else if(o.type==SCD_OBJ_FLOWER)frame=OBJECT_BASE_31+o.frame;
        /* SCORE.C tenpat / ObjPoints MapSpr_Points (100 ... 10000). */
        else if(o.type==SCD_OBJ_SCORE)frame=OBJECT_BASE_28+(o.frame<6?o.frame:0);
        else if(o.type==SCD_OBJ_GENERATOR)frame=OBJECT_BASE_45+o.frame;
        else if(o.type==SCD_OBJ_EXPLOSION)frame=OBJECT_BASE_24+o.frame;
        else{frame=o.type==SCD_OBJ_SPIKES?22:23;if(o.type!=SCD_OBJ_SPIKES && o.type!=SCD_OBJ_BOULDER)art_miss(o.type,o.subtype,o.frame);}
        if((feature_object==SCD_OBJ_PROJECTOR || feature_object==SCD_OBJ_ANIMAL) && (o.type==SCD_OBJ_PROJECTOR || o.type==SCD_OBJ_ANIMAL || (o.type==SCD_OBJ_EXPLOSION && o.subtype==2)) && scd_world_mailbox[57]<24){
            unsigned record=58+3*scd_world_mailbox[57]++;
            scd_world_mailbox[record]=(frame<<16)|(o.type<<8)|o.flags;
            scd_world_mailbox[record+1]=((uint32_t)(uint16_t)o.x<<16)|(uint16_t)o.y;
            scd_world_mailbox[record+2]=((uint32_t)(uint16_t)x<<16)|(uint16_t)y;
        }
        if(o.type==SCD_OBJ_AMY || o.type==SCD_OBJ_AMY_HEART)amy_sprite_record(frame,o.type,o.flags,x,y);
        vdp1_cmdt_t *cmd=sprite_commands->cmdts+count++;
        memset(cmd,0,sizeof(*cmd));vdp1_cmdt_normal_sprite_set(cmd);vdp1_cmdt_draw_mode_set(cmd,mode);
        assert(frame<OBJECT_FRAME_COUNT);
        object_clut_refresh(frame);
        const vdp1_cmdt_draw_mode_t object_mode={.color_mode=VDP1_CMDT_CM_CLUT_16,.end_code_disable=true};
        vdp1_cmdt_draw_mode_set(cmd,object_mode);
        vdp1_cmdt_char_size_set(cmd,object_widths[frame],object_heights[frame]);vdp1_cmdt_char_base_set(cmd,VDP1_VRAM(OBJECT_ATLAS_BASE+object_raw_offsets[frame]));
        cmd->cmd_colr=object_colr(frame);
        vdp1_cmdt_char_flip_set(cmd,(vdp1_cmdt_char_flip_t)(o.flags<<4));
        cmd->cmd_xa=x-object_widths[frame]/2;cmd->cmd_ya=y-32-object_y_shifts[frame]+object_top(frame,o.flags);
    }
    if(warp_timer){
        sprite->cmd_xa=sprite->cmd_xb=sprite->cmd_xc=sprite->cmd_xd=-100;
        warp_sonic_trails(&count,240-warp_timer);
    } else {
        scd_world_state travel=scd_world_get();
        if(!static_sprite && !audio_test && !white_hold){
            scd_title_card_view card[9];unsigned cards=scd_title_card_views(card,9);
            /* Mega Drive sprites earlier in the list cover later ones (retail ZONE over the
               act emblem); later VDP1 commands cover earlier ones, so draw the pieces backwards. */
            for(unsigned i=cards;i--;){
                const unsigned f=card[i].frame;
                vdp1_cmdt_t *cmd=sprite_commands->cmdts+count++;
                memset(cmd,0,sizeof(*cmd));vdp1_cmdt_normal_sprite_set(cmd);
                const vdp1_cmdt_draw_mode_t mode={.color_mode=VDP1_CMDT_CM_CLUT_16,.end_code_disable=true};
                vdp1_cmdt_draw_mode_set(cmd,mode);vdp1_cmdt_char_size_set(cmd,title_card_frames[f].width,title_card_frames[f].height);
                vdp1_cmdt_char_base_set(cmd,VDP1_VRAM(0x4600+title_card_frames[f].offset));
                cmd->cmd_colr=(0x4600+title_card_frames[f].offset+title_card_frames[f].width*title_card_frames[f].height/2)/8;
                cmd->cmd_xa=card[i].x+title_card_frames[f].left;cmd->cmd_ya=card[i].y+title_card_frames[f].top;
            }
        }
#if SCD_FRAME_PROFILE
        uint16_t hud_at=cpu_frt_count_get();
#endif
        if(audio_test)audio_hud(&count);else if(!static_sprite && !white_hold){gameplay_hud(&count);results_draw(&count);}
#if SCD_FRAME_PROFILE
        profile_values[29]|=(uint32_t)(uint16_t)(cpu_frt_count_get()-hud_at)<<16;
#endif
        if(save_state.dirty && !audio_test && !static_sprite && !white_hold){
            hud_panel(&count,16,164,288,32,0x8800);
            hud_text(&count,24,168,scd_save_message(save_state.status));
            hud_text(&count,24,184,"NOT SAVED - TITLE RAM DATA");
        }
        if(!stage_select_single_program && travel.ticks>=210 && !audio_test)hud_panel(&count,0,0,320,224,0xffff);
    }
    zone_object_probe(&count);
    assert(count<189+SCD_OBJECT_CAPACITY);
    memset(sprite_commands->cmdts+count,0,sizeof(vdp1_cmdt_t));
    vdp1_cmdt_end_set(sprite_commands->cmdts+count);sprite_commands->count=count+1;
    profile_sprite_mark(0);
    if(!floor_mode)gameplay_clear_wait();
    profile_sprite_mark(1);
    sonic_texture_wait();vdp1_sync_cmdt_list_put(sprite_commands,0);
    profile_sprite_mark(2);
    vdp1_sync_render();
    if(stage_background_pending){stage_background_pending=0;draw_stage_background(stage_background_by,1);}
    /* Explicit drawing plus manual swap: an over-budget draw cannot be
       interrupted by an automatic framebuffer change. Publish VDP2 state
       only after this complete sprite picture is ready. */
    /* Idle CPU time while VDP1 draws: decode the queued Sonic pose in
       32-word steps, re-checking the draw end between steps. */
    if(!floor_mode)while(!vdp1_transfer_status_get().cef) {sonic_view_prefetch_step(32);}
    profile_sprite_mark(3);
    vdp1_sync();
}

static void stage_configure(void) {
    const vdp2_vram_usage_t usage={0};
    vdp2_vram_usage_set(&usage);
    vdp2_vram_cycp_t cycles;
    memset(&cycles,0xff,sizeof(cycles));
    for(unsigned i=0;i<2;i++) {
        vdp2_scrn_cell_format_t fmt={
            .scroll_screen=i?VDP2_SCRN_NBG1:VDP2_SCRN_NBG0,
            .ccc=VDP2_SCRN_CCC_PALETTE_16,
            .char_size=VDP2_SCRN_CHAR_SIZE_1X1,
            .pnd_size=2, .aux_mode=0,
            .plane_size=VDP2_SCRN_PLANE_SIZE_1X1,
            .cpd_base=VDP2_VRAM_ADDR(i,0), .palette_base=VDP2_CRAM_MODE_0_OFFSET(0,0,0)
        };
        vdp2_scrn_normal_map_t map={
            .plane_a=VDP2_VRAM_ADDR(i,0x10000),.plane_b=VDP2_VRAM_ADDR(i,0x10000),
            .plane_c=VDP2_VRAM_ADDR(i,0x10000),.plane_d=VDP2_VRAM_ADDR(i,0x10000)
        };
        vdp2_scrn_cell_format_set(&fmt,&map);
        cycles.pt[i].t0=i?VDP2_VRAM_CYCP_PNDR_NBG1:VDP2_VRAM_CYCP_PNDR_NBG0;
        cycles.pt[i].t1=cycles.pt[i].t0;
        cycles.pt[i].t4=i?VDP2_VRAM_CYCP_CHPNDR_NBG1:VDP2_VRAM_CYCP_CHPNDR_NBG0;
        /* Maps with visible plane-B high cells (QQ1A/QQ2A, WW1D/WW2D) share base 4: equal
           priority breaks sprite > NBG0 > NBG1, giving the Mega Drive order B-low < A-low <
           sprite-low < B-high < A-high. Other maps keep 2 (same picture without B-high). */
        vdp2_scrn_priority_set(fmt.scroll_screen,i?(stage_zone==3 || (stage_zone==4 && era==3 && stage_act<2)?4:2):4);
        vdp2_scrn_sf_set(fmt.scroll_screen,VDP2_SCRN_SF_MODE_1,VDP2_SCRN_SF_TYPE_CELL_PRIORITY,VDP2_SCRN_SF_CODE_A);
    }
    {
        const vdp2_scrn_ls_format_t bg={.scroll_screen=VDP2_SCRN_NBG1,.table_base=VDP2_VRAM_ADDR(1,0x14000),.interval=0,.type=VDP2_SCRN_LS_TYPE_HORZ};
        vdp2_scrn_ls_set(&bg);
        const vdp2_scrn_ls_format_t fg=stage_zone==1?
            (vdp2_scrn_ls_format_t){.scroll_screen=VDP2_SCRN_NBG0,.table_base=VDP2_VRAM_ADDR(0,0x14000),.interval=0,.type=VDP2_SCRN_LS_TYPE_HORZ}:
            (vdp2_scrn_ls_format_t){.scroll_screen=VDP2_SCRN_NBG0};
        vdp2_scrn_ls_set(&fg);
    }
    cycles.pt[3].t0=VDP2_VRAM_CYCP_PNDR_NBG3;
    cycles.pt[3].t4=VDP2_VRAM_CYCP_CHPNDR_NBG3;
    vdp2_vram_cycp_set(&cycles);
    vdp2_scrn_display_set(VDP2_SCRN_DISPTP_NBG0 | VDP2_SCRN_DISPTP_NBG1 | VDP2_SCRN_DISPTP_NBG3);
}

static scd_background_scroll background_scroll;
static uint32_t background_frame,background_resets;
static unsigned background_checkpoint;
static int32_t checkpoint_ramp;
static int travel_loading;
static void draw_stage(void);
static unsigned tile_tick,tile_resets;static int tile_frame=-1;static void stage_tile_cycle(int immediate);
/* The art each tile-cycle slot last put in VRAM: a frame change re-uploads only the
   slots whose art changed (both banks), not every animated block. */
static const uint8_t *tile_shown[5];
#include "arrival_camera.h"
static void load_era(void) {
    /* Zone reloads replace the map/chunk buffers and may hand the slave to
       title or special-stage rendering. */
    bg_slave_stop();
    feature_camera_offset=0;
    if(!travel_loading){background_checkpoint=0;checkpoint_ramp=0;}
    /* scd_sfx_bank_mailbox: 'SFXB', bank loads and loaded bank + 1 (src/audio.c); [2] the VBlanks
       the last zone load of a bank took (its CD reads). */
    unsigned bank_start=vblank_ticks;int bank_before=scd_audio_bank_current();
    scd_audio_stage(stage_zone,era);
    if(scd_audio_bank_current()!=bank_before)scd_sfx_bank_mailbox[2]=vblank_ticks-bank_start;
    vdp2_tvmd_display_clear(); sync_frame();
    gameplay_clear_wait();
    vdp1_sync_wait();
    /* Stop automatic drawing/swapping while loading. Each gameplay update
       clears and draws the idle bank before requesting a completed swap. */
    vdp1_sync_interval_set(-1);
    /* Title/special-stage textures share this arena; restore the HUD only
       after leaving automatic drawing with the display disabled. */
    hud_original_upload();
    /* Tidal Tempest water line (src/water_raster.c); before Sonic textures decode. */
    water_raster_enable(stage_zone==2);
    sonic_view_reset();
    if(stage_open(&stage,packs[era],sizes[era])) {
        dbgio_printf("BAD STAGE PACKAGE"); dbgio_flush();
        for(;;) sync_frame();
    }
    /* Tidal Tempest Acts 2 and 3 wrap vertically (SCR42*.C, SCR43C/D.C scrv_down_ch). */
    stage.wrap_y=stage_zone==2 && (stage_act==1 || stage_act==2);
    int loaded=(travel_loading?scd_player_arrive:scd_player_init)(&stage,collision_packs[era],9472,era);
    if(loaded==-2 && travel_loading==1){
        /* No safe landing nearby: restore the departure era and inventory. */
        era=scd_world_get().era;travel_loading=2;load_era();return;
    }
    if(loaded){
        dbgio_printf("BAD COLLISION PACKAGE");dbgio_flush();for(;;)sync_frame();
    }
    scd_player_objects_lead();
    if(travel_loading==2)scd_world_abort();
    else if(travel_loading)scd_world_arrived(era);else scd_world_reset(era);
    /* Level/Main.asm LevelStart: all seven time stones force a good future (Time
       Attack excepted; the port has none), so a future warp lands in the good one. */
    if(time_stones==127)scd_world_generator_destroyed();
    player=scd_player_get();scd_player_music_event();gameplay_hud_reset();
    scd_powerup_runtime_reset(&effect_runtime,player.resets);scd_effect_mailbox[0]=0;
    /* Era layouts have different vertical origins (present starts at Y=1899,
       other eras at Y=488). Begin each graphics view at its own spawn point. */
    /* SCR*.C scr_set/playposiset + game_init scroll(): the original camera. */
    camera_y=scd_camera_v_begin(stage_zone,stage_act,era,player.y/65536,player.resets);
    camera_x=scd_camera_h();
    /* Travel restores Sonic at his destination, not at this era's spawn.
       Warm the actual arrival view before enabling display; warming spawn
       caused a full terrain rebuild on the first resumed gameplay update. */
    if(travel_loading){
        int unused_y;
        scd_arrival_camera(player.x/65536,player.y/65536,stage_act,
            scralim_left,scralim_right,scralim_down,scra_vline,&camera_x,&unused_y);
        scd_camera_h_sync(camera_x);
    }
    scd_background_reset(&background_scroll,camera_x);background_frame=player.frame;background_resets=player.resets;
    /* GAME4.C game_init: the water starts from its table with this camera. */
    water_camera(camera_x,camera_y);water_reset(stage_zone,stage_act,era);
    if(stage_zone==4){
        unsigned phase=travel_loading?0:scd_objects_ww_title_phase(stage_act,era);
        /* R62A/B palette starts at the level frame while its object timer
           keeps the title-card lead; R62C starts both at zero. */
        scd_r6_palette_title_phase_set(stage_act==1 && era<3?0:phase);
    }
    stage_configure();
    previous_x[0]=previous_x[1]=-10000;
    previous_y[0]=previous_y[1]=-10000;
    memset(maps,0,sizeof(maps));
    for(unsigned i=0;i<64;i++){bg_row_keys[i]=-10000;bg_row_world[i]=-10000;}
    scd_background_periodic_rows(&stage,bg_row_periodic);
    for(unsigned i=0;i<2;i++) {
        memcpy((void *)VDP2_VRAM_ADDR(i,0),stage.part[0],stage.size[0]);
        memset((void *)VDP2_VRAM_ADDR(i,0x10000),0,sizeof(maps[0]));
    }
    /* Quartz Quadrant background art past the pack's Nemesis art (the tile
       cycle writes it); the layout may reference it from here on. */
    {unsigned tiles=scd_background_tile_limit(bg_id(),stage.size[0]/32);
     if(tiles*32>stage.size[0]){stage.size[0]=tiles*32;scd_background_periodic_rows(&stage,bg_row_periodic);}}
    tile_tick=0;tile_frame=-1;tile_resets=player.resets;stage_tile_cycle(1);
    memcpy((void *)VDP2_CRAM_MODE_0_OFFSET(0,0,0),stage.part[5],128);
    previous_amy_palette=0;mm3_explosion_state=0;
    for(unsigned f=0;f<OBJECT_FRAME_COUNT;f++)if(object_stage_palette[f]){
        volatile uint16_t *clut=(volatile uint16_t *)VDP1_VRAM(OBJECT_ATLAS_BASE+object_raw_offsets[f]+object_widths[f]*object_heights[f]/2);
        clut[0]=0;
        for(unsigned c=1;c<16;c++){
            unsigned index=16*object_stage_palette[f]+object_clut_indices[f][c];
            /* Tidal Tempest: CRAM alias codes follow the water line (zone_object_view.inc). */
            clut[c]=water_raster_active()?0x0080+index:((unsigned)stage.part[5][index*2]<<8)|stage.part[5][index*2+1];
        }
    }
    object_clut_epoch=1;
    for(unsigned f=0;f<OBJECT_FRAME_COUNT;f++)object_clut_applied[f]=1;
    if(stage_zone)memcpy((void *)VDP2_CRAM_MODE_0_OFFSET(0,0,128),stage.part[5],128);
    water_raster_palette(water_palette());
    zone_object_art_load();boss_clut_state=-1;
    vdp2_scrn_back_color_set(VDP2_VRAM_ADDR(3,0x1bffe),(rgb1555_t){.raw=((unsigned)stage.part[5][64]<<8)|stage.part[5][65]});
    /* Populate and commit both ring maps while the display is still off.
       Otherwise the first simulation update pays for decoding thousands of
       tiles and misses refreshes before the next update. No simulation or
       animation clock advances during this loading work. */
    /* Level/Main.asm: the first level frame (level start, and a time-warp
       arrival, which restarts the level program) runs SpawnObjects/RunObjects
       while Sonic only runs ObjSonic_Init (Sonic/Main.asm:135-155). That object
       update runs here, with the first update's camera and travel state, so
       the first gameplay update does not pay for two object steps (PPZ Act 2
       Past arrival row 8061 and CC1 arrivals 5634/6484: late intervals; QQ2 B:
       update 1 became visible to the route harness). */
    if(travel_loading!=2){
        scd_world_state arrival=scd_world_get();
        scd_objects_travel_protection(!replay_active && arrival.ticks>0);
        scd_act_camera(camera_x,camera_y);scd_boss_camera(camera_x,camera_y);
        scd_player_objects_lead_run();
    }
    /* No sprite_draw follows this draw: write the background now. */
    draw_stage();if(stage_background_pending){stage_background_pending=0;draw_stage_background(stage_background_by,1);}
    sync_frame();back_color_commit();
    vdp2_tvmd_display_set();
    /* sync_frame returns at the DMA/register commit, not necessarily at the
       gameplay update boundary. Finish loading on a fresh VBlank-out so the
       first update has its full budget rather than the tail of a load frame. */
    unsigned loaded_tick=vblank_ticks;
    while(loaded_tick==vblank_ticks) {}
    /* QQ alone has mapwrtb's full N+1 plane redraw.  Do not claim the slave
       until the pack, warm draw and first fresh VBlank have completed. */
    if(stage_zone==3)bg_slave_start();
}

/* Level/Main.asm UpdateAnimTiles (CC2 drums): once at level setup, then from
   VInt_Level on every level vblank, paused loops included. */
static void stage_tile_cycle(int immediate){
    /* Up to 5 writes: R8 (background_r7.c scd_r8_tile_cycle) animates 5 blocks. */
    scd_tile_write w[5];unsigned n=scd_background_tile_cycle(bg_id(),tile_tick,w);
    if(!n||(int)w[0].frame==tile_frame)return;
    /* tile_frame -1 (stage setup) uploads every slot; after that only changed art. R8
       animates 5 blocks: re-sending all 10 bank copies per change overflowed the DMA
       queue (zone 6, 15 requests in one frame). */
    int all=immediate || tile_frame<0;
    tile_frame=(int)w[0].frame;
    unsigned changed[5],k=0;
    for(unsigned s=0;s<n && s<5;s++)if(all || tile_shown[s]!=w[s].art)changed[k++]=s;
    /* Changed slots whose VRAM cells form one run are packed into a staging buffer and
       sent as one DMA per bank (double-buffered: the other buffer may still feed the
       previous VBlank's transfer). */
    static uint8_t stage_art[2][1792] __aligned(4);static unsigned stage_pick;
    if(!immediate && k>=2){
        for(unsigned i=1;i<k;i++)for(unsigned j=i;j && w[changed[j]].cell<w[changed[j-1]].cell;j--){unsigned t=changed[j];changed[j]=changed[j-1];changed[j-1]=t;}
        unsigned bytes=0,run=1;
        for(unsigned i=0;i<k;i++){bytes+=w[changed[i]].cells*32u;if(i && w[changed[i-1]].cell+w[changed[i-1]].cells!=w[changed[i]].cell)run=0;}
        if(run && bytes<=sizeof(stage_art[0])){
            uint8_t *buffer=stage_art[stage_pick^=1];unsigned at=0;
            for(unsigned i=0;i<k;i++){memcpy(buffer+at,w[changed[i]].art,w[changed[i]].cells*32u);at+=w[changed[i]].cells*32u;tile_shown[changed[i]]=w[changed[i]].art;}
            for(unsigned b=0;b<2;b++)vdp_dma_enqueue((void *)VDP2_VRAM_ADDR(b,w[changed[0]].cell*32u),buffer,bytes);
            return;
        }
    }
    for(unsigned i=0;i<k;i++){
        unsigned s=changed[i];
        for(unsigned b=0;b<2;b++){
            void *dst=(void *)VDP2_VRAM_ADDR(b,w[s].cell*32u);
            if(immediate)memcpy(dst,w[s].art,w[s].cells*32u);else vdp_dma_enqueue(dst,w[s].art,w[s].cells*32u);
        }
        tile_shown[s]=w[s].art;
    }
}
/* Upload foreground ring-map rows first..end-1 (world tile rows, wrapped into
   the 64-row plane): one DMA job, or two across the ring's wrap. */
static void foreground_rows(int first,int end){
    if(end<=first)return;
    if(end-first>=64){vdp_dma_enqueue((void *)VDP2_VRAM_ADDR(0,0x10000),maps[0],sizeof(maps[0]));return;}
    unsigned a=(unsigned)first&63,n=(unsigned)(end-first);
    unsigned head=n<64-a?n:64-a;
    vdp_dma_enqueue((void *)VDP2_VRAM_ADDR(0,0x10000+a*64*sizeof(uint32_t)),maps[0]+a*64,head*64*sizeof(uint32_t));
    if(n>head)vdp_dma_enqueue((void *)VDP2_VRAM_ADDR(0,0x10000),maps[0],(n-head)*64*sizeof(uint32_t));
}
/* draw_stage's background line-scroll table and BG row cache for camera
   row `by`. It reads the camera, player and scroll state and writes only the
   BG map, its row keys, the line tables and their DMA jobs, which the
   VBlank-in commit applies in either order. In Tidal Tempest it runs while
   VDP1 draws (sprite_draw), off the update's critical path: the Act 3
   capsule's flower shower otherwise left under 2% of the VBlank-in deadline.
   The R4 line and row functions are pure; other zones keep the inline call. */
static void draw_stage_background(int by,int deferred){
    int dirty_first=0,dirty_last=-1;
    scd_background_lines_state(bg_id(),&background_scroll,camera_x,camera_y,by,player.frame,background_lines,foreground_lines,224);
    /* Keep the evaluator separate from cache maintenance in diagnostic frame
       profiles.  The marks compile away when SCD_FRAME_PROFILE is disabled. */
    if(!deferred)profile_mark(4);
    vdp_dma_enqueue((void *)VDP2_VRAM_ADDR(1,0x14000),background_lines,sizeof(background_lines));
    if(stage_zone==1)vdp_dma_enqueue((void *)VDP2_VRAM_ADDR(0,0x14000),foreground_lines,sizeof(foreground_lines));
    /* SCR51A-52D enkeichg mapset2: the enkeino layout blocks. A negative
       result is the switch frame: GAME5.C leaves the plane to mapwrtb on the
       next frame, so this frame writes no BG rows. */
    int bg_rows=scd_background_map_update(bg_id(),(uint8_t *)stage.part[4],(uint8_t *)stage.part[2],bg_row_world,by/8);
    /* Diagnostic only: distinguish a mapwrtb full redraw from an unavailable
       slave, without changing the cache or dispatch decisions. */
    if(bg_rows){
        bg_slave_mailbox[4]++;
        bg_slave_mailbox[8]=(uint32_t)bg_rows;
        if(bg_rows<0)bg_slave_mailbox[5]++;
        if(bg_rows==SCD_BACKGROUND_R5_FULL_REDRAW_SLOTS)bg_slave_mailbox[6]++;
    }
    if(bg_rows==SCD_BACKGROUND_R5_FULL_REDRAW_SLOTS&&!bg_slave_ready)bg_slave_mailbox[7]++;
    int bg_hold=bg_rows<0;
#if SCD_FRAME_PROFILE
    /* Bind timings to the actual display operation, not Sonic's threshold
       crossing or the emulator's unrelated frame counter. */
    if(stage_zone==3 && ((bg_hold && scd_r5_event_mailbox[9]==2) ||
       (bg_rows==SCD_BACKGROUND_R5_FULL_REDRAW_SLOTS && scd_r5_event_mailbox[9]==3)))
        profile_values[30]=0x52350000u|(bg_hold?1u:2u);
#endif
    /* Only mapwrtb's N+1 full R5 redraw may use the slave.  Plan all rows
       first, start the slave before the master half, then publish cache keys
       after both halves are in memory.  Ordinary cache maintenance remains
       entirely synchronous. */
    if(bg_rows==SCD_BACKGROUND_R5_FULL_REDRAW_SLOTS && bg_slave_ready){
        bg_slave_row rows[30];int split=1;
        bg_slave_mailbox[0]++;
        for(int n=0;n<30;n++){
            int row=by/8+n,fixed=scd_background_static(bg_id(),row*8);
            int sx=fixed?0:scd_background_row_start(bg_id(),&background_scroll,camera_x,row*8,player.frame);
            int cache_row=stage.wrap_y?(row&127):row;
            rows[n]=(bg_slave_row){cache_row,sx,fixed,cache_row&63};
            if(!scd_background_fill_row_fast_eligible(&stage,cache_row,sx,sx+64,fixed))split=0;
        }
        if(split){
            bg_slave_job->stage=&stage;bg_slave_job->map=maps[1];bg_slave_job->count=15;
            for(unsigned n=0;n<15;n++)bg_slave_job->row[n]=rows[15+n];
            unsigned generation=bg_slave_job->generation+1;bg_slave_job->generation=generation;
            /* mapset2 changed the pack chunks on the master.  Flush before
               the slave reads them, and again after it has written its rows. */
            cpu_cache_purge();if(!bg_slave_mailbox[10])cpu_dual_slave_notify();
            for(unsigned n=0;n<15;n++){
                bg_slave_row row=rows[n];
                scd_background_fill_row_fast(&stage,maps[1]+row.slot*64,row.row,row.first,row.first+64,row.fixed);
            }
            /* At most 30 V-blanks, as the special stage waits (src/special_view.inc):
               then the slave is switched off, so it cannot write a row later, and the
               master draws its half. Later redraws run on the master alone. */
            unsigned waited_from=vblank_ticks;
            while(bg_slave_job->done!=generation && vblank_ticks-waited_from<30){}
            if(bg_slave_job->done!=generation){
                bg_slave_stop();bg_slave_mailbox[9]++;
                for(unsigned n=15;n<30;n++){
                    bg_slave_row row=rows[n];
                    scd_background_fill_row_fast(&stage,maps[1]+row.slot*64,row.row,row.first,row.first+64,row.fixed);
                }
            }
#if SCD_FRAME_PROFILE
            profile_values[30]|=4u; /* This same redraw completed both halves. */
#endif
            cpu_cache_purge();
            for(unsigned n=0;n<30;n++){bg_row_world[rows[n].slot]=rows[n].row;bg_row_keys[rows[n].slot]=rows[n].first;}
            dirty_first=by/8;dirty_last=by/8+29;
        }else bg_slave_mailbox[3]++;
    }
    if(dirty_last<0)for(int row=by/8;!bg_hold&&row<by/8+30;row++) {
        int fixed=scd_background_static(bg_id(),row*8);
        int sx=fixed?0:scd_background_row_start(bg_id(),&background_scroll,camera_x,row*8,player.frame);
        /* scrb_v_posit wraps by 1024 with the camera (SCR42 scrv_down_ch &1023) and
           these BG layouts repeat every 1024 lines: key rows mod 128 (a 64-row
           ring multiple) so the wrap keeps the cached rows. */
        int cache_row=stage.wrap_y?(row&127):row;
        if(scd_background_cache_row_periodic(&stage,maps[1],bg_row_world,bg_row_keys,cache_row,sx,fixed,bg_row_periodic)!=0){
            if(dirty_last<0)dirty_first=row;
            dirty_last=row;
        }
    }
    /* Upload the visible span between the first and last changed row. This
       costs at most 30 PND rows and only one DMA enqueue, or two when the
       physical 64-row ring wraps. Many tiny DMA jobs cost more than the
       unchanged rows between independently moving raster bands. */
    if(dirty_last>=0){
        unsigned first=(unsigned)dirty_first&63,last=(unsigned)dirty_last&63;
        if(first<=last){
            vdp_dma_enqueue((void *)VDP2_VRAM_ADDR(1,0x10000+first*64*sizeof(uint32_t)),
                maps[1]+first*64,(last-first+1)*64*sizeof(uint32_t));
        }else{
            vdp_dma_enqueue((void *)VDP2_VRAM_ADDR(1,0x10000+first*64*sizeof(uint32_t)),
                maps[1]+first*64,(64-first)*64*sizeof(uint32_t));
            vdp_dma_enqueue((void *)VDP2_VRAM_ADDR(1,0x10000),maps[1],
                (last+1)*64*sizeof(uint32_t));
        }
    }
}
/* The back screen colour is one VDP2 VRAM word, which libyaul's
   vdp2_scrn_back_color_set writes at once. Written mid-frame, it changed from
   whatever screen line the CPU had reached: a band whose row moved with CPU
   load. Per-frame draws hold it here; the main loop writes it right after
   sync_frame, inside VBLANK with the rest of the frame's VDP2 state. */
static uint16_t back_color_pending;static int back_color_waiting;
static void back_color_defer(uint16_t raw){
    vdp2_scrn_back_color_set(VDP2_VRAM_ADDR(3,0x1bffe),(rgb1555_t){.raw=MEMORY_READ(16,VDP2_VRAM_ADDR(3,0x1bffe))});
    back_color_pending=raw;back_color_waiting=1;
}
static void back_color_commit(void){
    if(back_color_waiting){MEMORY_WRITE(16,VDP2_VRAM_ADDR(3,0x1bffe),back_color_pending);back_color_waiting=0;}
}
static void draw_stage(void) {
    /* VInt_Level's UpdateAnimTiles steps once per level update after the
       setup call (Level/Main.asm:312, 837); a death restart reruns LevelStart,
       which clears aniArtTimers/Frames and makes the setup call again. */
    {if(player.resets!=tile_resets){tile_resets=player.resets;tile_tick=0;tile_frame=-1;}
    else tile_tick++;}
    stage_tile_cycle(0);
    /* Foreground ring map and original independently scrolling BG regions. */
    int x=camera_x,y=camera_y,tx=x/8,ty=y/8,blocks_written=0;
    /* PLAYSP3.C block_wrt (breakable bumpers) and their restore after a death:
       redraw the written blocks' cells inside the viewport, or all of it. */
    {
        extern unsigned scd_player_block_writes(uint16_t (*out)[2],unsigned capacity);
        uint16_t written[64][2];unsigned n=scd_player_block_writes(written,64);
        if(n>64)previous_x[0]=previous_y[0]=-100000;
        else if(n){
            for(unsigned i=0;i<n;i++)for(unsigned c=0;c<4;c++){
                int wx=(written[i][0]>>4)*2+(int)(c&1),wy=(written[i][1]>>4)*2+(int)(c>>1);
                if(wx>=tx && wx<tx+42 && wy>=ty && wy<ty+30)
                    maps[0][((unsigned)wy&63)*64+((unsigned)wx&63)]=stage_saturn_pnd_inline(stage_tile(&stage,0,wx*8,wy*8),0);
            }
            if(tx==previous_x[0] && ty==previous_y[0])foreground_rows(ty,ty+30);
            else blocks_written=1;
        }
    }
    /* Tidal Tempest Acts 2/3 wrap the 2048-line map (SCR42*.C, SCR43C/D.C
       scrv_up_ch / scrv_down_ch): 2048 lines are 256 tile rows, four turns of
       the 64-row ring, so row r and row r±256 share a ring row and hold the
       same tiles. Treat the camera's wrap as the small move it is. */
    if(stage.wrap_y && previous_y[0]>-1000){
        int d=ty-previous_y[0];
        if(d>128 && d<384)previous_y[0]+=256;else if(d<-128 && d>-384)previous_y[0]-=256;
    }
    if(tx!=previous_x[0] || ty!=previous_y[0]) {
        int old_x=previous_x[0],old_y=previous_y[0];
        scd_foreground_cache(&stage,maps[0],tx,ty,old_x,old_y);
        /* scd_foreground_cache writes only rows ty..ty+29: upload those, or only
           the newly exposed rows when the camera moved vertically alone. */
        if(blocks_written || tx!=old_x || ty>=old_y+30 || ty+30<=old_y)foreground_rows(ty,ty+30);
        else if(ty>old_y)foreground_rows(old_y+30,ty+30);
        else foreground_rows(ty,old_y);
        previous_x[0]=tx;previous_y[0]=ty;
    }
    vdp2_scrn_scroll_x_set(VDP2_SCRN_NBG0,stage_zone==1?0:fix16_int32_from(x&511));
    vdp2_scrn_scroll_y_set(VDP2_SCRN_NBG0,fix16_int32_from(y&511));
    profile_mark(3);
    int by=scd_background_y(bg_id(),camera_y,player.x/65536);
    /* TT, SS and MM: the line table and row cache run while VDP1 draws (sprite_draw).
       Their R4 and R7 line/row functions touch only background state. */
    if(stage_zone==2 || stage_zone==5 || stage_zone==6){stage_background_by=by;stage_background_pending=1;}
    else draw_stage_background(by,0);
    profile_mark(5);
    vdp2_scrn_scroll_x_set(VDP2_SCRN_NBG1,0);
    vdp2_scrn_scroll_y_set(VDP2_SCRN_NBG1,fix16_int32_from(by&511));
    /* clchgctr restarts with each level program (death restart, time warp). */
    if(!scd_player_time_stop())palette_frame=scd_player_level_frames();
    scd_background_palette(bg_id(),palette_frame,stage.part[5],animated_palette);
    /* COL4 and COL5 cycles reach non-priority Tidal Tempest and Quartz Quadrant sprites
       (zone_object_view.inc masks). */
    /* Metallic Madness Act 3: HOTA8C/D.C's room fade and the lpcolorwk entries
       BOSS_8.C and EMIE8.C write (COL8C/D colorset2, fades) are live CRAM. */
    if(stage_zone==6 && stage_act==2)mm3_palette(animated_palette);
    if(stage_zone==2 || stage_zone==3 || stage_zone==6)zone_cycle_cluts(animated_palette);
    /* BOSS_1.C colorset2(5), BOSS_3.C colorset2(6)/(5) (boss, flash), BOSS_4_2.C (5), BOSS_5.C (6) and genecolor
       load the boss or capsule palette into line 1. */
    int boss_palette=scd_boss_palette();
    if(boss_palette && stage_zone!=5 && stage_zone!=6)memcpy(animated_palette+16,boss_palette==SCD_BOSS_PALETTE_BOSS?boss_palettes[era==3]:
        boss_palette==SCD_BOSS_PALETTE_BOSS3?boss3_palettes[era==3][0]:boss_palette==SCD_BOSS_PALETTE_FLASH3?boss3_palettes[era==3][1]:
        boss_palette==SCD_BOSS_PALETTE_BOSS4?boss4_palettes[era==3]:boss_palette==SCD_BOSS_PALETTE_BOSS5?boss5_palettes[era==3]:
        boss_palette==SCD_BOSS_PALETTE_BOSS6?boss6_palettes[era==3]:capsule_palette,sizeof(capsule_palette));
    if(stage_zone==5)scd_boss7_palette(animated_palette+16,era==3,scd_objects_ss_palette_restored());
    if(stage_zone==5 || (stage_zone==6 && stage_act==2) || scd_boss_round()>=3 || boss_clut_state>0)boss_zone_cluts(boss_palette);
    boss6_art_apply();
    int amy=scd_objects_amy_palette(animated_palette+16)|boss_palette<<1;
    if(stage_zone==1)zone_cycle_cluts(animated_palette);
    if(amy!=previous_amy_palette){
        object_clut_epoch++;
        previous_amy_palette=amy;
    }
    vdp_dma_enqueue((void *)VDP2_CRAM_MODE_0_OFFSET(0,0,0),animated_palette,sizeof(animated_palette));
    /* Indexed high-priority zone sprites share a live copy of the stage palette. */
    if(stage_zone)vdp_dma_enqueue((void *)VDP2_CRAM_MODE_0_OFFSET(0,0,128),animated_palette,sizeof(animated_palette));
    /* Original Level/Main.asm sets VDP register 7 to palette entry 32. */
    back_color_defer(animated_palette[32]);
}

static void warp_configure(void){
    vdp2_tvmd_display_clear();sync_frame();
    memcpy((void *)VDP2_VRAM_ADDR(1,0),warp_art+128+2240,3232);
    for(unsigned row=0;row<64;row++)for(unsigned col=0;col<64;col++){
        unsigned source=((row%32)%28)*40+(col%40);
        uint16_t tile=((unsigned)warp_art[128+source*2]<<8)|warp_art[129+source*2];
        maps[1][row*64+col]=stage_saturn_pnd(tile,4096);
    }
    memcpy((void *)VDP2_VRAM_ADDR(1,0x10000),maps[1],sizeof(maps[1]));
    memset(background_lines,0,sizeof(background_lines));
    memcpy((void *)VDP2_VRAM_ADDR(1,0x14000),background_lines,sizeof(background_lines));
    vdp2_tvmd_display_set();
}
static void warp_draw(void){
    static const unsigned green[]={0,1,2,3,4,5,6,7,6,5,4,3,2,1};
    for(unsigned i=0;i<64;i++){
        unsigned word=((unsigned)warp_art[i*2]<<8)|warp_art[i*2+1];
        unsigned r=((word>>1)&7)*31/7,g=((word>>5)&7)*31/7,b=((word>>9)&7)*31/7;
        animated_palette[i]=0x8000|r|(g<<5)|(b<<10);
    }
    for(unsigned i=0;i<14;i++){unsigned white=green[(i+(240-warp_timer)/2)%14]*31/7;animated_palette[17+i]=0x8000|white|(31<<5)|(white<<10);}
    vdp_dma_enqueue((void *)VDP2_CRAM_MODE_0_OFFSET(0,0,0),animated_palette,sizeof(animated_palette));
    /* Original Level/Main.asm sets VDP register 7 to palette entry 32. */
    back_color_defer(animated_palette[32]);
    vdp2_scrn_scroll_x_set(VDP2_SCRN_NBG1,0);
    vdp2_scrn_scroll_y_set(VDP2_SCRN_NBG1,fix16_int32_from((warp_timer*4)&255));
}

static void floor_configure(void) {
    vdp2_tvmd_display_clear(); sync_frame();
    gameplay_clear_wait();
    vdp1_sync_wait();vdp1_sync_interval_set(0);
    const vdp2_scrn_bitmap_format_t fmt={
        .scroll_screen=VDP2_SCRN_RBG0,.ccc=VDP2_SCRN_CCC_PALETTE_256,
        .bitmap_size=VDP2_SCRN_BITMAP_SIZE_512X256,
        .palette_base=VDP2_CRAM_MODE_0_OFFSET(0,0,0), .bitmap_base=VDP2_VRAM_ADDR(2,0)
    };
    sprite_unpack(floor_bitmap,floor_bitmap_end,(uint16_t *)VDP2_VRAM_ADDR(2,0),512*256/2,0);
    /* Read back every decoded word from VDP2, independently checking the
       engineering bitmap pattern before enabling its moving projection. */
    const volatile uint16_t *floor_vram=(const volatile uint16_t *)VDP2_VRAM_ADDR(2,0);
    uint32_t floor_hash=2166136261u,floor_errors=0;
    for(unsigned n=0;n<65536;n++){
        uint16_t word=floor_vram[n];unsigned color=1+(((n%256)/8+(n/256)/16)&1);
        if(word!=color*257)floor_errors++;
        floor_hash=(floor_hash^(word>>8))*16777619u;floor_hash=(floor_hash^(word&255))*16777619u;
    }
    scd_floor_mailbox[0]=0x464c4f52;scd_floor_mailbox[1]=floor_errors;scd_floor_mailbox[2]=floor_hash;scd_floor_mailbox[3]=65536;
    volatile rgb1555_t *pal=(volatile rgb1555_t *)VDP2_CRAM_MODE_0_OFFSET(0,0,0);
    pal[1]=RGB1555(1,5,24,22);pal[2]=RGB1555(1,2,7,12);
    memset(&rotation,0,sizeof(rotation));
    rotation.xst=(uint32_t)fix16_int32_from(-160);
    rotation.yst=FIX16(128); rotation.delta_x=FIX16(1);
    rotation.matrix.param.a=FIX16(1);rotation.matrix.param.e=FIX16(1);
    rotation.kx=FIX16(1);rotation.ky=FIX16(1);
    rotation.kast=0;rotation.delta_kast=FIX16(1);
    const vdp2_scrn_rotation_params_t params={
        .rp_mode=VDP2_SCRN_RP_MODE_0,.rp_table=&rotation,.rp_table_base=VDP2_VRAM_ADDR(1,0),
        .coeff_params={.enable=1,.word_size=VDP2_SCRN_COEFF_WORD_SIZE_2,
            .usage=VDP2_SCRN_COEFF_USAGE_KX_KY,.kast_read_enable=0,.xst_read_enable=1,.yst_read_enable=1}
    };
    for(unsigned y=0;y<224;y++) coefficients[y]=y<64?0x80000000u:(64u<<16)/(y-63);
    memcpy((void *)VDP2_VRAM_ADDR(0,0),coefficients,sizeof(coefficients));
    vdp2_scrn_bitmap_format_set(&fmt);
    vdp2_scrn_rotation_rp_mode_set(&params);
    vdp2_scrn_rotation_rp_table_set(&params);
    vdp2_scrn_rotation_coeff_table_set(&params);
    vdp2_scrn_rotation_coeff_params_set(&params);
    vdp2_scrn_rotation_rp_read_set(&params);
    const vdp2_vram_usage_t usage={.a0=VDP2_VRAM_USAGE_TYPE_COEFF_TBL,.b0=VDP2_VRAM_USAGE_TYPE_CPD_BPD};
    vdp2_vram_usage_set(&usage);
    vdp2_scrn_priority_set(VDP2_SCRN_RBG0,3);
    vdp2_scrn_display_set(VDP2_SCRN_DISPTP_RBG0|VDP2_SCRN_DISPTP_NBG3);
    vdp2_tvmd_display_set();
}

#include "special_view.inc"
#include "title_view.inc"
#include "dagarden_view.inc"

/* Act 3 from its ordinary spawn in one future: 2 good, 3 bad (R13C/R13D packs). */
static void act3_load(unsigned future){
    stage_act=2;scd_objects_act(2);scd_player_act(2);scd_world_act(2);
    stage_packs_load(PACK_PPZ2,PACK_PPZ3+1);stage_packs_load(PACK_COL2,PACK_COL3+1);
    for(unsigned i=0;i<4;i++)sizes[i]=stage_pack_bytes[PACK_PPZ0+i];
    era=future;load_era();
}
/* IPX.asm NewGame: Palmtree Panic Act 1 in the present from its start, with three lives, no time
   stones, the title card and a fade from black. Act packs are read again after a later act. */
uint8_t scd_low_packs_lost;
static void new_game(void){
    stage_select_single_program=0;
    int reload=stage_act!=0 || stage_zone!=0 || scd_low_packs_lost;scd_low_packs_lost=0;
    saved_good_zones=0;save_session=1;fixture_run=0;special_cur_stage=0; /* IPX.asm NewGame: curSpecStage=0 */
    prototype_end=0;scd_world_mailbox[137]=0;stage_act=0;stage_zone=0;scd_player_zone(0);scd_objects_zone(0);scd_world_zone(0);good_future_flags=0;time_stones=0;special_pending=0;special_return_act=0;fade_white=0;
    scd_objects_time_stones(0);scd_objects_act(0);scd_player_act(0);scd_world_act(0);
    if(reload)stage_packs_load(PACK_PPZ0,PACK_COL3+1);
    else zone_tables_load(scd_cd_root_read()); /* the title's front-end overlay evicted R1 */
    for(unsigned i=0;i<4;i++)sizes[i]=stage_pack_bytes[PACK_PPZ0+i];
    floor_mode=diagnostic_mode=paused=0;era=0;scd_title_card_prepare();load_era();player=scd_player_get();
    scd_title_card_start(stage_act);act_fade=23;act_fade_offset(-255);
    scd_world_mailbox[135]=trace_sequence;scd_world_mailbox[134]=stage_act;
    save_checkpoint(0);
}
/* The ending card, shown only when the ending movie could not play (src/ending.c):
   ENDING.MMD's last message for endingID, centred (8-pixel font, 320 across). */
static void prototype_end_draw(void){
    unsigned count=2;char text[40];
    const char *message=scd_ending_message(ending_good);
    hud_text(&count,160-(int)strlen(message)*4,100,message);
    snprintf(text,sizeof(text),"SCORE %07lu",(unsigned long)player.score);hud_text(&count,96,148,text);
    if(prototype_end>60)hud_text(&count,116,180,"PRESS START");
    memset(sprite_commands->cmdts+count,0,sizeof(vdp1_cmdt_t));
    vdp1_cmdt_end_set(sprite_commands->cmdts+count);sprite_commands->count=count+1;
    gameplay_clear_wait();
    sonic_texture_wait();vdp1_sync_cmdt_list_put(sprite_commands,0);vdp1_sync_render();
    while(!vdp1_transfer_status_get().cef) {}
    vdp1_sync();
}

/* Level select. The title screen is a verified retail reimplementation checked
   pixel for pixel, so nothing is added to its menu: hold A+B+C on the title and
   press Start, and the title is torn down and replaced. Without the combo the
   title behaves exactly as before. Act 3 exists only in the two futures. */
static int level_select;
static unsigned ls_zone,ls_act,ls_era,ls_row;
/* Zone 0 was the original import and has all three acts. Every other zone has
   exactly the acts its STAGE_ZONE_PACK rows name, so the menu never offers a
   stage whose pack is absent from the disc image. */
static int ls_act_ready(unsigned zone,unsigned act){
    if(!zone)return 1;
    /* Any row for the pair is enough. Act 3 has no PACK_PPZ0 row, because it
       runs in the era 2 and 3 regions only. */
#define STAGE_ZONE_PACK(pack,z,a,file,source) if((z)==zone && (a)==act)return 1;
    STAGE_ZONE_PACKS
#undef STAGE_ZONE_PACK
    return 0;
}
/* The zone that follows this one, or LS_ZONE_COUNT when there is none left.
   A zone whose Act 1 has no packs is skipped, so a partly wired disc still
   walks the zones it does carry. */
static unsigned ls_next_zone(unsigned zone){
    for(unsigned z=zone+1;z<LS_ZONE_COUNT;z++)if(ls_act_ready(z,0))return z;
    return LS_ZONE_COUNT;
}
static int ls_zone_ready(unsigned zone){
    for(unsigned act=0;act<3;act++)if(ls_act_ready(zone,act))return 1;
    return 0;
}
static const char *const LS_ACTS[]={"ACT 1","ACT 2","ACT 3"};
static const char *const LS_ERAS[]={"PRESENT","PAST","GOOD FUTURE","BAD FUTURE"};
static unsigned ls_era_first(unsigned act){return act==2?2:0;}
static void level_select_draw(void){
    unsigned count=2;char text[40];
    hud_panel(&count,32,40,256,152,0x8800);
    hud_text(&count,104,52,"LEVEL SELECT");
    snprintf(text,sizeof(text),"ZONE  %s",LS_ZONES[ls_zone]);hud_text(&count,48,84,text);
    snprintf(text,sizeof(text),"ACT   %s",LS_ACTS[ls_act]);hud_text(&count,48,100,text);
    snprintf(text,sizeof(text),"ERA   %s",LS_ERAS[ls_era]);hud_text(&count,48,116,text);
    hud_text(&count,40,84+(int)ls_row*16,">");
    if(!ls_zone_ready(ls_zone))hud_text(&count,48,128,"TERRAIN NOT IMPORTED YET");
    else if(ls_zone)hud_text(&count,48,128,"ZONE IN DEVELOPMENT");
    hud_text(&count,48,144,"UP/DOWN  PICK ROW");
    hud_text(&count,48,156,"LEFT/RIGHT  CHANGE");
    hud_text(&count,48,168,"START BEGIN    B BACK");
    memset(sprite_commands->cmdts+count,0,sizeof(vdp1_cmdt_t));
    vdp1_cmdt_end_set(sprite_commands->cmdts+count);sprite_commands->count=count+1;
    gameplay_clear_wait();
    sonic_texture_wait();vdp1_sync_cmdt_list_put(sprite_commands,0);vdp1_sync_render();
    while(!vdp1_transfer_status_get().cef) {}
    vdp1_sync();
}
/* Start an arbitrary act/era from its ordinary spawn. new_game() is left alone:
   it is on the verified title path and its pack reload is conditional there. */
/* saved: Continue's progress (src/save_view.inc), applied before the act loads, as
   IPX.asm ReadSaveData runs before LevelStart reads timeStones; NULL starts clean. */
static void new_game_at(unsigned zone,unsigned act,unsigned target_era,const scd_save_progress *saved){
    stage_select_single_program=0;
    save_session=0;saved_good_zones=0;fixture_run=0;special_cur_stage=0;
    prototype_end=0;scd_world_mailbox[137]=0;good_future_flags=0;time_stones=0;
    if(saved){time_stones=saved->time_stones;good_future_flags=saved->good_acts;saved_good_zones=saved->good_zones;special_cur_stage=saved->spec_stage;}
    special_pending=0;special_return_act=0;fade_white=0;stage_act=act;stage_zone=zone;
    scd_player_zone(zone);scd_objects_zone(zone);scd_world_zone(zone);
    scd_objects_time_stones(time_stones);scd_objects_act(act);scd_player_act(act);scd_world_act(act);
    /* Act 3 runs in the good and bad futures only, so a zone has no rows for the
       era 0 and 1 regions there.  Loading them anyway sends stage_pack_file to
       its zone 0 fallback and spends a CD read on data the act never looks at,
       so take the same four regions act3_load() takes. */
    if(act==2){stage_packs_load(PACK_PPZ2,PACK_PPZ3+1);stage_packs_load(PACK_COL2,PACK_COL3+1);}
    else stage_packs_load(PACK_PPZ0,PACK_COL3+1);
    for(unsigned i=0;i<4;i++)sizes[i]=stage_pack_bytes[PACK_PPZ0+i];
    floor_mode=diagnostic_mode=paused=0;era=target_era;scd_title_card_prepare();load_era();player=scd_player_get();
    scd_title_card_start(stage_act);act_fade=23;act_fade_offset(-255);
    scd_world_mailbox[135]=trace_sequence;scd_world_mailbox[134]=stage_act;
}

/* Standalone-only objects translated from Time Warp/Main.asm and Objects.
   Natural warp rendering above deliberately remains unchanged. */
#define STAGE_SELECT_SPARK_BASE 0x10000u
#define STAGE_SELECT_SPARK_STRIDE (48u*48u/2u+32u)
_Static_assert(STAGE_SELECT_SPARK_BASE+5*STAGE_SELECT_SPARK_STRIDE<OBJECT_ATLAS_BASE,"standalone sparkle textures overlap object atlas");
typedef struct {unsigned active,routine,timer,frame,anim_time;int32_t x,y,vy;} fe_ssw_object;
typedef struct {unsigned sparkle,frame;int x,y;} fe_ssw_draw;
/* R0 is already loaded by the selector. Explicit data sections keep zeroed
   scratch in the same overlay; each entry resets it before any use. */
static struct {
    fe_ssw_object sonics[4],sparkles[28];
    fe_ssw_draw draws[60];
    unsigned draw_count,slot,origin;
    uint32_t rng;
    unsigned scroll,deadline,clock;
} fe_ssw_state __attribute__((section(".data.fe_ssw_state")))={0};
/* GCC noipa prevents inlining, cloning or folding across the resident boundary.
   The existing zone_ops dispatch is the only resident reference to R0 code. */
#define FE_SSW_CODE __attribute__((noipa))
/* Source Sparkle/Data/Mappings.asm, verbatim piece fields; first byte is count.
   Canvas48x48 has its source origin at24,48. No retail pixel payload is embedded. */
static const uint8_t fe_ssw_spark_maps[5][21] __attribute__((section(".rodata.fe_ssw_spark_maps")))={
 {4,0xe0,5,0,0x46,0xf0,0xe0,5,8,0x46,0,0xf0,5,0x10,0x46,0xf0,0xf0,5,0x18,0x46,0},
 {4,0xe0,5,0,0x4a,0xf0,0xe0,5,8,0x4a,0,0xf0,5,0x10,0x4a,0xf0,0xf0,5,0x18,0x4a,0},
 {4,0xd0,10,0,0x4e,0xe8,0xd0,10,8,0x4e,0,0xe8,10,0x10,0x4e,0xe8,0xe8,10,0x18,0x4e,0},
 {4,0xe0,5,0,0x57,0xf0,0xe0,5,0,0x5b,0,0xf0,5,0x18,0x5b,0xf0,0xf0,5,0x18,0x57,0},
 {2,0xe8,6,0,0x5f,0xf0,0xe8,6,8,0x5f,0}
};
static FE_SSW_CODE void fe_ssw_spark_upload(void){
    const uint8_t *art=warp_art+128+2240;
    uint8_t pixels[48*48/2];
    for(unsigned frame=0;frame<5;frame++){
        memset(pixels,0,sizeof(pixels));
        const uint8_t *map=fe_ssw_spark_maps[frame];
        /* First source mapping piece wins, exactly like MD sprite links. */
        for(unsigned piece=0;piece<map[0];piece++){
            const uint8_t *m=map+1+piece*5;
            unsigned w=((m[1]>>2)&3)+1,h=(m[1]&3)+1,word=(unsigned)m[2]<<8|m[3];
            int left=(int8_t)m[4]+24,top=(int8_t)m[0]+48;
            for(unsigned y=0;y<h*8;y++)for(unsigned x=0;x<w*8;x++){
                unsigned sx=word&0x800?w*8-1-x:x,sy=word&0x1000?h*8-1-y:y;
                unsigned off=((word&0x7ff)+(sx/8)*h+sy/8)*32+(sy%8)*4+(sx%8)/2;
                assert(off<3232 && left+(int)x>=0 && left+(int)x<48 && top+(int)y>=0 && top+(int)y<48);
                unsigned color=(art[off]>>(sx%2?0:4))&15;
                unsigned dest=(unsigned)(top+y)*48+(unsigned)(left+x),shift=dest%2?0:4;
                if(color && !(pixels[dest/2]>>shift&15))pixels[dest/2]|=color<<shift;
            }
        }
        memcpy((void *)VDP1_VRAM(STAGE_SELECT_SPARK_BASE+frame*STAGE_SELECT_SPARK_STRIDE),pixels,sizeof(pixels));
    }
}
static FE_SSW_CODE uint32_t fe_ssw_random(void){
    uint32_t old=fe_ssw_state.rng?fe_ssw_state.rng:0x2a6d365a;
    uint32_t product=old*41u;
    unsigned sum=((product&0xffff)+(product>>16))&0xffff;
    fe_ssw_state.rng=(uint32_t)sum<<16|(product&0xffff);
    return (old&0xffff0000)|sum;
}
static FE_SSW_CODE void fe_ssw_queue(fe_ssw_object *o,unsigned sparkle){
    if(!--o->anim_time){
        /* DrawObject uses a signed byte: time0 becomes-1, then resets. */
        o->anim_time=sparkle?2:3;o->frame++;
        if(o->frame>=(sparkle?4u:5u))o->frame=0;
    }
    assert(fe_ssw_state.draw_count<60);
    fe_ssw_state.draws[fe_ssw_state.draw_count++]=(fe_ssw_draw){sparkle,o->frame,(int16_t)((uint32_t)o->x>>16)-128,(int16_t)((uint32_t)o->y>>16)-128};
}
static FE_SSW_CODE void fe_ssw_spark_step(unsigned i){
    fe_ssw_object *o=fe_ssw_state.sparkles+i;
    if(!o->active)return;
    if(!o->routine){
        uint32_t random=fe_ssw_random();
        o->vy=random&0x3ffff;o->x=fe_ssw_state.sonics[0].x+((int)(random&31)-16)*65536;
        o->y=fe_ssw_state.sonics[0].y-24*65536;
        o->timer=45;o->routine=1;o->frame=0;o->anim_time=2;
    }
    o->y+=o->vy;
    if(!--o->timer){memset(o,0,sizeof(*o));return;}
    fe_ssw_queue(o,1);
}
static FE_SSW_CODE void fe_ssw_sonic_step(unsigned i){
    fe_ssw_object *o=fe_ssw_state.sonics+i;
    if(!o->active)return;
    if(!o->routine){o->x=288*65536;o->y=416*65536;o->routine=1;o->frame=0;o->anim_time=3;}
    if(o->routine==1){o->y-=8*65536;if(o->y==248*65536){o->routine=2;o->timer=120;}}
    else if(o->routine==2){if(!--o->timer)o->routine=3;}
    else if(o->routine==3){o->y-=8*65536;if(o->y==96*65536)o->routine=4;}
    /* RunSonicTrailObj copies all four animation bytes AFTER the leader draws. */
    if(i){o->frame=fe_ssw_state.sonics[0].frame;o->anim_time=fe_ssw_state.sonics[0].anim_time;}
    fe_ssw_queue(o,0);
}
static FE_SSW_CODE void fe_ssw_objects(void){
    unsigned relative=(vblank_ticks-fe_ssw_state.origin)&0xffff;
    if(!(relative&3)){
        fe_ssw_state.sonics[fe_ssw_state.slot].active=1;
        fe_ssw_state.slot=(fe_ssw_state.slot+1)&3;
        unsigned i=0;while(i<28 && fe_ssw_state.sparkles[i].active)i++;
        /* Source can write into following padding on pool overflow; the bounded
           scene must never reach that condition. Keep an explicit QA failure. */
        assert(i<28);fe_ssw_state.sparkles[i].active=1;
    }
    fe_ssw_state.draw_count=0;
    for(unsigned i=0;i<3;i++)fe_ssw_spark_step(i);
    for(unsigned i=0;i<4;i++)fe_ssw_sonic_step(i);
    /* Preserve the original bug: the25 back passes start at FRONT slot0. */
    for(unsigned i=0;i<25;i++)fe_ssw_spark_step(i);
}
static FE_SSW_CODE void fe_ssw_objects_draw(unsigned *count){
    /* Original first sprite link wins; reverse submission for VDP1 painter order. */
    for(unsigned n=fe_ssw_state.draw_count;n--;){
        fe_ssw_draw d=fe_ssw_state.draws[n];
        if(!d.sparkle){object_sprite(count,OBJECT_BASE_200+d.frame,d.x,d.y,0);continue;}
        unsigned base=STAGE_SELECT_SPARK_BASE+d.frame*STAGE_SELECT_SPARK_STRIDE;
        volatile uint16_t *clut=(volatile uint16_t *)VDP1_VRAM(base+48*48/2);
        clut[0]=0;for(unsigned c=1;c<16;c++)clut[c]=animated_palette[c];
        vdp1_cmdt_t *cmd=sprite_commands->cmdts+(*count)++;
        memset(cmd,0,sizeof(*cmd));vdp1_cmdt_normal_sprite_set(cmd);
        const vdp1_cmdt_draw_mode_t mode={.color_mode=VDP1_CMDT_CM_CLUT_16,.end_code_disable=true};
        vdp1_cmdt_draw_mode_set(cmd,mode);vdp1_cmdt_char_size_set(cmd,48,48);
        vdp1_cmdt_char_base_set(cmd,VDP1_VRAM(base));cmd->cmd_colr=(base+48*48/2)/8;
        cmd->cmd_xa=d.x-24;cmd->cmd_ya=d.y-48;
    }
}
/* Standalone Time Warp/Main.asm owns its timer; it never loads an era.
   Palette fade is the source's 8 red, 8 green, 8 blue channel steps. */
static FE_SSW_CODE uint16_t fe_ssw_white(uint16_t color,unsigned step,int out){
    unsigned result=0x8000;
    for(unsigned channel=0;channel<3;channel++){
        unsigned value=((((color>>(channel*5))&31)*7)+15)/31;
        unsigned local=step>channel*8?step-channel*8:0;
        if(local>8)local=8;
        if(out){value+=local;if(value>7)value=7;}
        else {unsigned threshold=local?8-local:7;if(value<threshold)value=threshold;}
        result|=(value*31/7)<<(channel*5);
    }
    return result;
}
static FE_SSW_CODE unsigned fe_ssw_sync(void){
    scd_audio_update();frames++;sync_frame();
    if(fe_ssw_state.clock){
        unsigned now=vblank_ticks;
        warp_timer=(int32_t)(fe_ssw_state.deadline-now)>0?fe_ssw_state.deadline-now:0;
    }
    smpc_peripheral_digital_t pad;
    smpc_peripheral_process();smpc_peripheral_digital_port(1,&pad);
    return pad.pressed.button.start?SCD_PAD_START:0;
}
static FE_SSW_CODE void fe_ssw_picture(unsigned updates,unsigned fade,int out,
        const uint16_t cluts[5][16]){
    /* Match the resident loop: VDP2-in does not retire VDP1's previous
       variable-mode buffer change. Wait before reusing its list or colors. */
    vdp1_sync_wait();
    /* Original palette cycling runs only in MainLoop, not either fade.
       Restore its target so the natural path's timer-based cycle is not used. */
    for(unsigned c=0;c<64;c++){
        unsigned word=(unsigned)warp_art[c*2]<<8|warp_art[c*2+1];
        animated_palette[c]=0x8000|(((word>>1)&7)*31/7)|
            ((((word>>5)&7)*31/7)<<5)|((((word>>9)&7)*31/7)<<10);
    }
    if(updates){
        static const unsigned green[]={0,1,2,3,4,5,6,7,6,5,4,3,2,1};
        for(unsigned c=0;c<14;c++){
            unsigned white=green[(c+(updates-1)/2)%14]*31/7;
            animated_palette[17+c]=0x8000|white|(31<<5)|(white<<10);
        }
    }
    for(unsigned c=0;c<64;c++)animated_palette[c]=fe_ssw_white(animated_palette[c],fade,out);
    vdp2_scrn_scroll_x_set(VDP2_SCRN_NBG1,0);
    vdp2_scrn_scroll_y_set(VDP2_SCRN_NBG1,fix16_int32_from(-(int)fe_ssw_state.scroll*4));
    fe_ssw_state.scroll++;
    /* Preserve source VSync scroll updates during fades as well as MainLoop. */
    vdp_dma_enqueue((void *)VDP2_CRAM_MODE_0_OFFSET(0,0,0),animated_palette,sizeof(animated_palette));
    back_color_defer(animated_palette[32]);
    for(unsigned f=0;f<5;f++){
        unsigned frame=OBJECT_BASE_200+f;
        volatile uint16_t *clut=(volatile uint16_t *)VDP1_VRAM(OBJECT_ATLAS_BASE+object_raw_offsets[frame]+object_widths[frame]*object_heights[frame]/2);
        for(unsigned c=1;c<16;c++)clut[c]=fe_ssw_white(cluts[f][c],fade,out);
    }
    unsigned count=2;
    if(updates)fe_ssw_objects_draw(&count);
    memset(sprite_commands->cmdts+count,0,sizeof(vdp1_cmdt_t));
    vdp1_cmdt_end_set(sprite_commands->cmdts+count);sprite_commands->count=count+1;
    gameplay_clear_wait();vdp1_sync_cmdt_list_put(sprite_commands,0);vdp1_sync_render();
    while(!vdp1_transfer_status_get().cef){}
    vdp1_sync();
}
static FE_SSW_CODE void fe_ssw_run(unsigned previous_hold){
    uint16_t cluts[5][16];
    assert(zone_tables_zone==(int)SCD_ZONE_FRONTEND && scd_zone_code_ready(SCD_ZONE_FRONTEND));
    memset(&fe_ssw_state,0,sizeof(fe_ssw_state));
    fe_ssw_state.origin=vblank_ticks;fe_ssw_state.slot=0;fe_ssw_state.rng=0;
    fe_ssw_state.draw_count=0;
    memset(fe_ssw_state.sonics,0,sizeof(fe_ssw_state.sonics));
    memset(fe_ssw_state.sparkles,0,sizeof(fe_ssw_state.sparkles));
    bg_slave_stop();water_raster_enable(0);paused=0;
    gameplay_clear_wait();vdp1_sync_wait();vdp1_sync_interval_set(-1);
    vdp2_tvmd_display_clear();act_fade_offset(0);
    stage_packs_load(PACK_WARP,PACK_WARP+1);
    /* Title texture allocator stops below OBJECT_ATLAS_BASE; selector uses
       VDP2 only. Preserve the common atlas and its startup CLUT conversions. */
    for(unsigned f=0;f<5;f++){
        unsigned frame=OBJECT_BASE_200+f;
        const volatile uint16_t *clut=(const volatile uint16_t *)VDP1_VRAM(OBJECT_ATLAS_BASE+object_raw_offsets[frame]+object_widths[frame]*object_heights[frame]/2);
        for(unsigned c=0;c<16;c++)cluts[f][c]=clut[c];
    }
    fe_ssw_spark_upload();
    stage_configure();warp_configure();
    vdp2_tvmd_display_clear();vdp2_scrn_display_set(VDP2_SCRN_DISP_NBG1);
    /* Original busy-waits90 timer VBlanks with display disabled. */
    fe_ssw_state.clock=0;
    unsigned prewait=vblank_ticks;
    while(vblank_ticks-prewait<90)previous_hold=fe_ssw_sync();
    warp_timer=240;fe_ssw_state.deadline=vblank_ticks+240;fe_ssw_state.clock=1;
    scd_audio_warp(1); /* FM_D8 only AFTER prewait. */
    fe_ssw_state.scroll=0;
    fe_ssw_picture(0,0,0,cluts);
    /* PrepFadeFromWhite then one VSync precedes FadeFromWhite. */
    vdp2_tvmd_display_set();previous_hold=fe_ssw_sync();
    for(unsigned fade=1;fade<=24;fade++){
        fe_ssw_picture(0,fade,0,cluts);
        previous_hold=fe_ssw_sync();
    }
    unsigned updates=0;
    do{
        fe_ssw_objects();
        fe_ssw_picture(++updates,24,0,cluts);
        unsigned hold=fe_ssw_sync();
        if((hold&~previous_hold)&SCD_PAD_START)break;
        previous_hold=hold;
    }while(warp_timer);
    /* Source freezes object/palette updates during its24-step exit fade. */
    for(unsigned fade=1;fade<=24;fade++){
        fe_ssw_picture(updates,fade,1,cluts);
        previous_hold=fe_ssw_sync();
    }
    for(unsigned f=0;f<5;f++){
        unsigned frame=OBJECT_BASE_200+f;
        volatile uint16_t *clut=(volatile uint16_t *)VDP1_VRAM(OBJECT_ATLAS_BASE+object_raw_offsets[frame]+object_widths[frame]*object_heights[frame]/2);
        for(unsigned c=0;c<16;c++)clut[c]=cluts[f][c];
    }
    fe_ssw_state.clock=0;warp_timer=0;scd_audio_warp(0);
    scd_stage_select_scene_qa[0]=10;
    assert(zone_tables_zone==(int)SCD_ZONE_FRONTEND && scd_zone_code_ready(SCD_ZONE_FRONTEND));
}
#undef FE_SSW_CODE
/* Kept resident by src/saturn.x's existing *zone_ops* rule. A volatile table
   pointer prevents a direct resident-to-overlay call after LTO. */
typedef struct {void (*run)(unsigned);} stage_select_warp_ops;
static const stage_select_warp_ops fe_ssw_zone_ops
    __attribute__((section(".rodata.fe_ssw_zone_ops")))={fe_ssw_run};
static void stage_select_warp_run(unsigned previous_hold){
    scd_frontend_overlay_load();
    if(!scd_zone_code_ready(SCD_ZONE_FRONTEND)){
        scd_stage_select_scene_qa[0]=13;title_begin(1);return;
    }
    const stage_select_warp_ops *volatile ops=&fe_ssw_zone_ops;
    ops->run(previous_hold);
    /* No suspended R0 frame or further R0 state access when title loads. */
    title_begin(1);
}
/* frontend_begin is supplied below by frontend_view.inc. */
static void frontend_begin(unsigned screen);
/* Level/Palette Fade.asm:273–348. This is per-COLOR red-first filling,
   22VSyncs, distinct from standalone WARP's24global-channel fade. */
static uint16_t stage_select_level_white(uint16_t color,unsigned steps){
    unsigned c[3];
    for(unsigned i=0;i<3;i++)c[i]=((((color>>(i*5))&31)*7)+15)/31;
    /* Fill red, then green, then blue. Distribute the remaining steps once
       per channel instead of repeating the search for every fade step. */
    for(unsigned i=0;i<3;i++){
        unsigned room=7-c[i],add=steps<room?steps:room;
        c[i]+=add;steps-=add;
    }
    return (color&0x8000)|(c[0]*31/7)|((c[1]*31/7)<<5)|((c[2]*31/7)<<10);
}
static int stage_select_level_source_color(uint16_t color){
    return stage_select_level_white(color,0)==color;
}
static int stage_select_level_index_color(unsigned index,const uint16_t normal[512],int water){
    if(index>=512 || !stage_select_level_source_color(normal[index]))return 0;
    return !water || index>=256 || stage_select_level_source_color(normal[index+256]);
}
/* phase1prepare/2fade/3done/4failed; commandcount; snapshotbytes;
   presentedVSyncs; elapsedVBlanks; original return reason. */
volatile uint32_t scd_stage_select_return_qa[6];
typedef struct {unsigned begin,end,offset;} stage_select_fade_range;
typedef struct {
    stage_select_fade_range ranges[189+SCD_OBJECT_CAPACITY];
    uint16_t command_colors[189+SCD_OBJECT_CAPACITY],normal[512],faded[512];
} stage_select_fade_scratch;
static int stage_select_level_white_return(void){
    /* Re-render the frozen actual list; do not resimulate objects, scroll,
       animation, score, PLC callbacks, or natural arrival. */
    unsigned started=0,cadence_start=0;
    unsigned count=sprite_commands->count;
    scd_stage_select_return_qa[0]=1;scd_stage_select_return_qa[1]=count;
    scd_stage_select_return_qa[2]=scd_stage_select_return_qa[3]=scd_stage_select_return_qa[4]=0;
    unsigned used=0;
    assert(count<=189+SCD_OBJECT_CAPACITY);
    stage_select_fade_scratch *scratch=malloc(sizeof(*scratch));
    if(!scratch){scd_stage_select_return_qa[0]=4;scd_stage_select_scene_qa[0]=13;return 0;}
    bg_slave_stop();sonic_texture_wait();gameplay_clear_wait();vdp1_sync_wait();
    act_fade_offset(0);
    for(unsigned n=0;n<count;n++){
        const vdp1_cmdt_t *cmd=sprite_commands->cmdts+n;
        scratch->command_colors[n]=cmd->cmd_colr;
        unsigned kind=cmd->cmd_ctrl&15,mode=(cmd->cmd_pmod>>3)&7,begin=0,bytes=0;
        if(kind<=2 && mode==VDP1_CMDT_CM_CLUT_16){begin=(unsigned)cmd->cmd_colr*8;bytes=32;}
        else if(kind<=2 && mode==VDP1_CMDT_CM_RGB_32768){
            begin=(unsigned)cmd->cmd_srca*8;
            bytes=((cmd->cmd_size>>8)&63)*8*(cmd->cmd_size&255)*2;
        }
        if(bytes){assert(begin+bytes<=0x80000);scratch->ranges[used++]=(stage_select_fade_range){begin,begin+bytes,0};}
    }
    /* Union overlapping/aliased texture/CLUT intervals before any write.
       A shared texture must receive one color transform, not one per sprite. */
    for(unsigned i=1;i<used;i++){
        stage_select_fade_range v=scratch->ranges[i];unsigned j=i;
        while(j && scratch->ranges[j-1].begin>v.begin){scratch->ranges[j]=scratch->ranges[j-1];j--;}scratch->ranges[j]=v;
    }
    unsigned merged=0,total=0;
    for(unsigned i=0;i<used;i++){
        if(merged && scratch->ranges[i].begin<=scratch->ranges[merged-1].end){
            if(scratch->ranges[i].end>scratch->ranges[merged-1].end)scratch->ranges[merged-1].end=scratch->ranges[i].end;
        }else scratch->ranges[merged++]=scratch->ranges[i];
    }
    for(unsigned i=0;i<merged;i++){scratch->ranges[i].offset=total;total+=scratch->ranges[i].end-scratch->ranges[i].begin;}
    scd_stage_select_return_qa[2]=total;
    uint8_t *saved=malloc(total?total:1);
    if(!saved){free(scratch);scd_stage_select_return_qa[0]=4;scd_stage_select_scene_qa[0]=13;return 0;}
    for(unsigned i=0;i<merged;i++)memcpy(saved+scratch->ranges[i].offset,(const void *)VDP1_VRAM(scratch->ranges[i].begin),scratch->ranges[i].end-scratch->ranges[i].begin);
    const volatile uint16_t *cram=(const volatile uint16_t *)VDP2_CRAM_ADDR(0);
    for(unsigned i=0;i<512;i++)scratch->normal[i]=cram[i];
    /* Refuse an active color outside the original3-bit lattice rather than
       silently quantizing a Saturn-only color into an approximate fade. */
    int water=water_raster_active(),source_colors=1;
    for(unsigned i=0;i<64;i++){
        source_colors&=stage_select_level_index_color(i,scratch->normal,water);
        source_colors&=stage_select_level_index_color(128+i,scratch->normal,water);
    }
    for(unsigned i=0;i<merged;i++){
        const uint16_t *colors=(const uint16_t *)(saved+scratch->ranges[i].offset);
        for(unsigned n=0;n<(scratch->ranges[i].end-scratch->ranges[i].begin)/2;n++)if(colors[n])
            source_colors&=(colors[n]&0x8000)?stage_select_level_source_color(colors[n]):stage_select_level_index_color(colors[n]&0x7ff,scratch->normal,water);
    }
    for(unsigned n=0;n<count;n++){
        const vdp1_cmdt_t *cmd=sprite_commands->cmdts+n;
        unsigned kind=cmd->cmd_ctrl&15,mode=(cmd->cmd_pmod>>3)&7;
        if(kind<=6 && (cmd->cmd_pmod&7)){source_colors=0;continue;}
        if(kind>=4 && kind<=6){
            source_colors&=(cmd->cmd_colr&0x8000)?stage_select_level_source_color(cmd->cmd_colr):stage_select_level_index_color(cmd->cmd_colr&0x7ff,scratch->normal,water);
        }else if(kind<=2 && mode!=VDP1_CMDT_CM_CLUT_16 && mode!=VDP1_CMDT_CM_RGB_32768){
            unsigned colors=mode==0?16:mode==2?64:mode==3?128:mode==4?256:0;
            if(!colors){source_colors=0;continue;}
            unsigned bank=(cmd->cmd_colr&0x7ff)&~(colors-1);
            for(unsigned c=0;c<colors;c++)source_colors&=stage_select_level_index_color(bank+c,scratch->normal,water);
        }
    }
    if(!source_colors){free(saved);free(scratch);scd_stage_select_return_qa[0]=4;scd_stage_select_scene_qa[0]=13;return 0;}
    unsigned water_line=scd_water_mailbox[2];
    scd_stage_select_scene_qa[0]=12;scd_stage_select_return_qa[0]=2;int cadence=1;
    started=cadence_start=vblank_ticks;
    for(unsigned step=0;step<22;step++){
        /* Source presents palette, then mutates it for the NEXT VSync.
           Pictures are base, step1,...step21(all white), not step1..22. */
        for(unsigned i=0;i<512;i++)scratch->faded[i]=stage_select_level_source_color(scratch->normal[i])?stage_select_level_white(scratch->normal[i],step):scratch->normal[i];
        vdp_dma_enqueue((void *)VDP2_CRAM_ADDR(0),scratch->faded,sizeof(scratch->faded));
        back_color_defer(scratch->faded[32]);
        for(unsigned i=0;i<merged;i++){
            const uint16_t *from=(const uint16_t *)(saved+scratch->ranges[i].offset);
            volatile uint16_t *to=(volatile uint16_t *)VDP1_VRAM(scratch->ranges[i].begin);
            for(unsigned n=0;n<(scratch->ranges[i].end-scratch->ranges[i].begin)/2;n++)
                to[n]=from[n]&0x8000?stage_select_level_white(from[n],step):from[n];
        }
        for(unsigned n=0;n<count;n++){
            vdp1_cmdt_t *cmd=sprite_commands->cmdts+n;unsigned kind=cmd->cmd_ctrl&15;
            if(kind>=4 && kind<=6 && (scratch->command_colors[n]&0x8000))cmd->cmd_colr=stage_select_level_white(scratch->command_colors[n],step);
        }
        vdp1_sync_cmdt_list_put(sprite_commands,0);vdp1_sync_render();
        while(!vdp1_transfer_status_get().cef){}vdp1_sync();
        scd_audio_update();frames++;sync_frame();back_color_commit();
        water_raster_commit(water_line);water_raster_latch();smpc_peripheral_process();
        unsigned now=vblank_ticks;
        scd_stage_select_return_qa[3]=step+1;scd_stage_select_return_qa[4]=now-started;
        if(now-cadence_start!=1){cadence=0;scd_stage_select_scene_qa[0]=13;break;}
        cadence_start=now;
    }
    /* The new title program disables display first. Restore cached textures
       only behind a disabled display; otherwise CD reads could reveal them. */
    vdp2_tvmd_display_clear();water_raster_enable(0);
    /* TVMD setter changes shadow registers only. Commit the disabled display
       BEFORE restoring live CRAM/VRAM; this wait is outside the22fade pictures. */
    frames++;sync_frame();
    for(unsigned i=0;i<merged;i++)memcpy((void *)VDP1_VRAM(scratch->ranges[i].begin),saved+scratch->ranges[i].offset,scratch->ranges[i].end-scratch->ranges[i].begin);
    free(saved);
    for(unsigned n=0;n<count;n++)sprite_commands->cmdts[n].cmd_colr=scratch->command_colors[n];
    for(unsigned i=0;i<512;i++)MEMORY_WRITE(16,VDP2_CRAM_ADDR(0)+i*2,scratch->normal[i]);
    scd_stage_select_return_qa[0]=cadence?3:4;
    free(scratch);
    return cadence;
}
static void stage_select_scene_finish(unsigned reason){
    scd_stage_select_return_qa[5]=reason;
    int failed=(reason==4 || reason==9) && !stage_select_level_white_return();
    if(failed){vdp2_tvmd_display_clear();frames++;sync_frame();}
    stage_select_single_program=0;
    scd_stage_select_scene_qa[0]=failed?13:reason;
    scd_stage_select_scene_qa[3]=scd_player_get().resets;
    special_pending=special_return_act=0;
    act_fade=fade_white=warp_timer=0;paused=0;save_session=0;
    scd_world_abort();scd_audio_warp(0);
    title_begin(1);
}
static void stage_select_scene_start(fe_stage_select_choice choice,unsigned previous_hold){
    /* The caller copied this tuple out of fe_ overlay data BEFORE any level load. */
    scd_stage_select_scene_qa[1]=choice.kind|(unsigned)choice.zone<<8|
        (unsigned)choice.act<<16|(unsigned)choice.era<<24;
    /* StageSels writes context even for all four standalone programs. */
    stage_zone=choice.zone;stage_act=choice.act;era=choice.era;
    if(choice.kind==FE_SEL_WARP){
        scd_stage_select_scene_qa[0]=5;stage_select_warp_run(previous_hold);return;
    }
    if(choice.kind==FE_SEL_COMMING){
        scd_stage_select_scene_qa[0]=6;frontend_begin(SCD_FE_COMING);return;
    }
    if(choice.kind==FE_SEL_OPENING){
        const scd_frontend_ops *ops=scd_frontend_ops_get();
        ops->movie(0);scd_stage_select_scene_qa[0]=11;title_begin(1);return;
    }
    if(choice.kind==FE_SEL_SPEDEMO){
        if(scd_special_mode_start(1,SCD_SPECIAL_TEMPORARY))title_begin(1);
        return;
    }
    if(choice.kind!=FE_SEL_NORMAL || choice.zone>=7 || choice.act>=3 || choice.era>=4){
        scd_stage_select_scene_qa[0]=0;title_begin(1);return;
    }
    /* IPX ReadSaveData keeps stones, curSpecStage and goodFutures in memory.
       LevelStart initializes score/lives/checkpoint/per-act goodFutureFlags.
       Passing a saved context avoids new_game_at(...,NULL)'s zeroed secrets. */
    scd_save_progress saved={0};
    saved.time_stones=time_stones;saved.spec_stage=special_cur_stage;
    saved.good_zones=saved_good_zones;
    saved.good_acts=0;
    scd_ta.mode=0;
    new_game_at(choice.zone,choice.act,choice.era,&saved);
    stage_select_single_program=1;save_session=0;
    scd_stage_select_scene_qa[0]=1;
    scd_stage_select_scene_qa[2]=time_stones|special_cur_stage<<8|saved_good_zones<<16;
    scd_stage_select_scene_qa[3]=scd_player_get().resets;
}
#include "save_view.inc"
#include "frontend_view.inc"

int main(void) {
    dbgio_init();dbgio_dev_default_init(DBGIO_DEV_VDP2);dbgio_dev_font_load();
    core_result=scd_core_probe();
    scd_save_open(&save_state,scd_save_saturn_init());
    /* IPX ReadSaveData runs once before GameLoop, not at each StageSelect. */
    if(save_state.valid){
        time_stones=save_state.saved.time_stones;
        special_cur_stage=save_state.saved.spec_stage;
        saved_good_zones=save_state.saved.good_zones;
    }
    save_publish();
    scd_audio_init();
    profile_vblank_install(scd_audio_get_diagnostics().ready);
    /* Audio initialization used low work RAM for the sound bank; stage packs follow. */
    stage_packs_load(0,STAGE_PACK_COUNT);
    for(unsigned i=0;i<4;i++){packs[i]=STAGE_PACK_DATA(PACK_PPZ0+i);sizes[i]=stage_pack_bytes[PACK_PPZ0+i];collision_packs[i]=STAGE_PACK_DATA(PACK_COL0+i);}
    input_ready=1;scd_player_audio_set(scd_audio_request);
    sprite_init();
    /* IPX.asm .GameLoop starts with the title screen; the packs were read above. */
    title_begin(0);
    for(;;) {
        /* VDP2 commits at VBlank-in; VDP1 finishes the buffer change at out.
           CD commands can shift work across that boundary. Wait before reusing
           the sprite command buffer or submitting another list. */
        vdp1_sync_wait();
        while(simulation_tick==vblank_ticks) {}
        if(!title_active && !special_mode && !floor_mode)gameplay_clear_begin();
        profile_begin();
        smpc_peripheral_digital_t pad;
        smpc_peripheral_process();smpc_peripheral_digital_port(1,&pad);
        save_publish();
        if(!title_active && !save_panel && !special_mode && (pad.held.button.l || pad.held.button.r ||
           pad.held.button.x || pad.held.button.y ||
           (pad.pressed.button.start && (pad.held.button.b || pad.held.button.c))))save_session=0;
        if(title_active){
            simulation_tick=vblank_ticks;scd_audio_update();
            /* Yaul names these the other way round from how they read: pressed is
               the current level and held is the edge, a button that went down on
               this poll (smpc_peripherals.c: held = (now ^ before) & now). So this
               is Start pressed while A, B and C are already down. */
            if(pad.held.button.start && pad.pressed.button.a && pad.pressed.button.b && pad.pressed.button.c){
                title_end();level_select=1;ls_zone=0;ls_act=0;ls_era=0;ls_row=0;
                /* The menu draws the way gameplay does: clear the idle bank, draw,
                   then wait for the frame to end. That needs gameplay's manual VDP1
                   mode, not the title's automatic one (interval 0), in which the
                   end-of-frame wait never returns. The title also borrows the arena
                   the HUD font lives in, and leaves the fade at black with the display
                   off. So make the same changes load_era() makes before its first
                   gameplay frame. */
                gameplay_clear_wait();vdp1_sync_wait();vdp1_sync_interval_set(-1);
                hud_original_upload();
                act_fade_offset(0);vdp2_scrn_display_set(0);vdp2_scrn_back_color_set(VDP2_VRAM_ADDR(3,0x1bffe),(rgb1555_t){.raw=0x8000});
                vdp2_tvmd_display_set();
                continue;
            }
            /* Emulator test entry (tools/test_credits_emulator.py): the "Thank You" screen or an ending. */
            if(scd_credits_mailbox[0]){title_end();scd_credits_test_entry();title_begin(1);continue;}
            if(title_frame(pad)){frames++;sync_frame();title_commit();continue;}
            unsigned destination=title_end();
            if(destination==1){
                if(save_state.any || save_state.dirty)save_panel_begin(2);else new_game();
            }else if(destination==2 && save_state.valid)continue_game();
            else if(destination==4)save_panel_begin(1);
            else if(destination==3)frontend_begin(SCD_FE_TIME_ATTACK);
            else if(destination==7)frontend_begin(SCD_FE_SOUND_TEST);
            else if(destination==8)frontend_begin(SCD_FE_STAGE_SELECT);
            else if(destination==9)frontend_begin(SCD_FE_STAFF_TIMES);
            else if(destination==6)frontend_begin(SCD_FE_VISUAL);
            else if(destination==5){dagarden_run();title_begin(1);}  /* IPX.asm DAGarden */
            else if(!destination){
                /* IPX.asm Demo: the attract scene (src/special_modes.c); Saturn X or Y held at
                   the time-out is the debug entry for Special Stage 8 or Time Attack. */
                if(special_attract((pad.pressed.button.x?1u:0)|(pad.pressed.button.y?2u:0))){simulation_tick=vblank_ticks;continue;}
                title_begin(1);
            }else title_begin(1);
            continue;
        }
        if(frontend_screen){
            simulation_tick=vblank_ticks;scd_audio_update();
            frontend_frame(&pad);continue;
        }
        if(save_panel){
            simulation_tick=vblank_ticks;scd_audio_update();
            if(pad.held.button.b){save_panel=0;title_begin(1);continue;}
            if(pad.held.button.a || pad.held.button.c || pad.held.button.start){
                if(save_panel==2){save_panel=0;new_game();continue;}
                input_ready=0;
                if(save_state.dirty)scd_save_retry(&save_state);
                else scd_save_open(&save_state,save_state.backend);
                input_ready=1;
            }
            save_panel_draw();frames++;sync_frame();continue;
        }
        if(level_select){
            /* held is Yaul's edge: one menu step per press, not one per frame. */
            simulation_tick=vblank_ticks;scd_audio_update();
            if(pad.held.button.down)ls_row=(ls_row+1)%3;
            if(pad.held.button.up)ls_row=(ls_row+2)%3;
            int step=pad.held.button.right?1:pad.held.button.left?-1:0;
            if(step){
                if(!ls_row){
                    ls_zone=(ls_zone+LS_ZONE_COUNT+step)%LS_ZONE_COUNT;
                    /* Land on an act this zone actually has, lowest first. */
                    if(!ls_act_ready(ls_zone,ls_act)){
                        ls_act=0;
                        while(ls_act<2 && !ls_act_ready(ls_zone,ls_act))ls_act++;
                    }
                    if(ls_era<ls_era_first(ls_act))ls_era=ls_era_first(ls_act);
                } else if(ls_row==1){
                    for(unsigned tries=0;tries<3;tries++){
                        ls_act=(ls_act+3+step)%3;
                        if(ls_act_ready(ls_zone,ls_act))break;
                    }
                    if(ls_era<ls_era_first(ls_act))ls_era=ls_era_first(ls_act);
                } else {
                    unsigned first=ls_era_first(ls_act),span=4-first;
                    ls_era=first+(ls_era-first+span+step)%span;
                }
            }
            if(pad.held.button.b){level_select=0;title_begin(1);continue;}
            if(pad.held.button.start && ls_act_ready(ls_zone,ls_act)){
                level_select=0;new_game_at(ls_zone,ls_act,ls_era,NULL);continue;
            }
            /* 'LSEL', a frame count and the selection, so a harness can see the menu. */
            scd_trace_mailbox[0]=0x4c53454c;scd_trace_mailbox[1]=frames;scd_trace_mailbox[2]=ls_zone|ls_act<<8|ls_era<<16|ls_row<<24;
            level_select_draw();frames++;sync_frame();continue;
        }
        if(prototype_end){
            /* Mailbox 137: updates (low 16 bits), good ending (bit 16), movie tried (17),
               movie result (bits 24-27), back at the title (31). */
            simulation_tick=vblank_ticks;scd_audio_update();
            if(prototype_end==1){
                /* First update after the fade: clear the fade offset and the stage planes. */
                act_fade_offset(0);vdp2_scrn_display_set(0);vdp2_scrn_back_color_set(VDP2_VRAM_ADDR(3,0x1bffe),(rgb1555_t){.raw=0x8000});
                /* IPX.asm GameDone: pick endingID and run its movie, then back to the title. */
                bg_slave_stop();ending_good=scd_ending_good(saved_good_zones,time_stones);ending_result=0;
                scd_world_mailbox[137]=1u|(uint32_t)ending_good<<16|1u<<17;
                ending_result=scd_ending_play(ending_good);
                /* The movie took the sprite priorities and the zone effect bank's tail
                   (low work RAM: every game start reloads its packs). */
                vdp2_sprite_priority_set(0,4);vdp2_sprite_priority_set(1,7);scd_audio_bank(-1);
                if(!ending_result)prototype_end=900;
            }
            const uint32_t ending_record=(uint32_t)ending_good<<16|1u<<17|((uint32_t)ending_result&15u)<<24;
            /* After the movie, or Start (or 15 seconds) on the card, the title screen. */
            if((pad.pressed.button.start && prototype_end>60) || prototype_end>=900){
                scd_world_mailbox[137]=(ending_record&~0xFFFFu)|1u<<31;
                prototype_end=0;good_future_flags=0;time_stones=0;special_cur_stage=0;scd_objects_time_stones(0);
                title_begin(1);
                continue;
            }else{
                ++prototype_end;scd_world_mailbox[137]=(ending_record&~0xFFFFu)|prototype_end;
                prototype_end_draw();frames++;sync_frame();continue;
            }
        }
        if(special_mode && special_finished){
            /* The special stage results are over. The next act starts with the carried score,
               lives and extra-life score (special-stage units are tens of points) and the time
               stones, fading in from white (palClearFlags). */
            const scd_special_main *m=&special_game->main;
            scd_player_progress progress={m->score*10u,m->next_life*10u,m->lives};
            special_finished=0;special_slave_stop();special_mode=0;special_sonic_mode=0;scd_special_sonic_mailbox[1]=0;scd_special_mailbox[15]=0;
            stage_packs_load(0,PACK_OBJECT_ART);stage_packs_load(PACK_SONIC_FRAMES,PACK_SONIC_FRAMES+1);scd_audio_pause(0);
            /* IPX.asm: an attract demo, time attack or stage 8 run returns to the title. */
            if(special_game_mode){
                const unsigned flags=special_game_mode;special_game_mode=0;
                if(flags&SCD_SPECIAL_TIME_ATTACK){
                    /* IPX.asm:1290 TimeAttack_SS loops back to the menu, which records the time. */
                    scd_ta.frames=scd_special_mode_last.frames;scd_ta.aborted=scd_special_mode_last.aborted;scd_ta.mode=0;scd_ta.pending=1;
                    frontend_begin(SCD_FE_TIME_ATTACK);continue;
                }
                /* IPX.asm:1073 SoundTest_SpecStg8: a won secret stage runs SPEEND.MMD. */
                if((flags&SCD_SPECIAL_SECRET) && !scd_special_mode_last.aborted && (scd_frontend_overlay_load(),!scd_special_modes()->credits())){
                    vdp2_sprite_priority_set(0,4);vdp2_sprite_priority_set(1,7);
                }
                title_begin(1);continue;
            }
            time_stones=special_game->time_stones;scd_objects_time_stones(time_stones);
            scd_title_card_prepare();
            if(special_return_act==2)act3_load(good_future_flags==3 || time_stones==127?2:3);
            else{
                stage_act=1;scd_objects_act(1);scd_player_act(1);scd_world_act(1);stage_packs_load(PACK_PPZ0,PACK_COL3+1);
                for(unsigned i=0;i<4;i++)sizes[i]=stage_pack_bytes[PACK_PPZ0+i];
                era=0;load_era();
            }
            special_return_act=0;scd_player_progress_set(progress);player=scd_player_get();
            scd_title_card_start(stage_act);act_fade=23;fade_white=1;act_fade_offset(255);
            scd_world_mailbox[135]=trace_sequence;scd_world_mailbox[134]=stage_act;
            save_checkpoint(0);
            pad.held.button.start=pad.pressed.button.start=0;
        }
        if(special_mode){
            if(pad.held.button.start && !special_game_active){special_slave_stop();special_mode=0;special_sonic_mode=0;scd_special_sonic_mailbox[1]=0;scd_special_mailbox[15]=0;stage_packs_load(0,PACK_OBJECT_ART);stage_packs_load(PACK_SONIC_FRAMES,PACK_SONIC_FRAMES+1);scd_audio_pause(0);load_era();pad.held.button.start=pad.pressed.button.start=0;}
            else {simulation_tick=vblank_ticks;special_draw(pad);frames++;sync_frame();special_game_commit();continue;}
        } else if(!warp_timer && !replay_active && !audio_test && pad.pressed.button.start && pad.held.button.b){
            scd_special_mailbox[19]=floor_mode|(diagnostic_mode<<1)|(paused<<2);floor_mode=diagnostic_mode=paused=0;
            /* B also starts the special game in inspection; the entry press must not. */
            pad.held.button.b=pad.pressed.button.b=0;
            special_load(1);simulation_tick=vblank_ticks;special_draw(pad);frames++;sync_frame();continue;
        }
        if(!warp_timer && !replay_active && !audio_test && !special_mode && !act_fade && stage_act==0 && pad.pressed.button.start && pad.held.button.c && pad.held.button.left) {
            /* Debug entry: Act 1 Present before the goal post with 50 rings, so the big ring appears. */
            floor_mode=diagnostic_mode=paused=0;era=0;load_era();
            scd_player_place(9800,450,1536,0,0);scd_player_inventory(50,0);player=scd_player_get();
            pad.held.button.c=pad.pressed.button.c=pad.held.button.start=0;
            scd_world_mailbox[135]=trace_sequence;scd_world_mailbox[134]=stage_act;
        } else if(!warp_timer && !replay_active && !audio_test && !special_mode && !act_fade && pad.pressed.button.start && pad.held.button.c && pad.held.button.right) {
            /* Debug entry: game over fixture. With one life and no rings Sonic is hurt and dies. */
            scd_player_progress progress=scd_player_progress_get();progress.lives=1;scd_player_progress_set(progress);
            scd_player_inventory(0,0);scd_objects_hurt(player.x/65536);player=scd_player_get();
            pad.held.button.c=pad.pressed.button.c=pad.held.button.start=0;
        } else if(!warp_timer && !replay_active && !audio_test && !special_mode && !act_fade && pad.pressed.button.start && pad.held.button.c && (pad.held.button.up || pad.held.button.down)) {
            /* Debug entry: Act 3 from its ordinary spawn; Up selects the bad future, Down the good future. */
            floor_mode=diagnostic_mode=paused=0;scd_title_card_prepare();act3_load(pad.held.button.down?2:3);player=scd_player_get();
            scd_title_card_start(stage_act);act_fade=23;act_fade_offset(-255);
            pad.held.button.c=pad.pressed.button.c=pad.held.button.start=0;
            scd_world_mailbox[135]=trace_sequence;scd_world_mailbox[134]=stage_act;
        } else if(!warp_timer && !replay_active && !audio_test && !special_mode && !act_fade && stage_act==1 && era==0 && pad.pressed.button.start && pad.held.button.c) {
            /* Act 2 travel fixture: Sonic stands on the room floor just right of the past time
               post (X 5728) above the tube shaft; controller input travels from there. */
            /* The retail spawner streams by camera chunk: a 5665 px jump would fill the
               pool with every record on the way, so the post never loads. Restart the
               spawner (SpawnObjects_Init) at the fixture, with the camera begun there
               as the replay fixtures do, so its first window is the fixture's. */
            scd_world_reset(era);scd_objects_reset(era,1);scd_player_place(5745,619,0,0,0);scd_title_card_start(stage_act);
            player=scd_player_get();camera_y=scd_camera_v_begin(stage_zone,stage_act,era,player.y/65536,player.resets);camera_x=scd_camera_h();
            pad.held.button.c=pad.pressed.button.c=0;pad.held.button.start=0;
            scd_world_mailbox[135]=trace_sequence;
        } else if(!warp_timer && !replay_active && !audio_test && !special_mode && !act_fade && pad.pressed.button.start && pad.held.button.c) {
            /* Debug entry: Act 2 Present from its ordinary spawn. */
            stage_act=1;scd_objects_act(1);scd_player_act(1);scd_world_act(1);stage_packs_load(PACK_PPZ0,PACK_COL3+1);
            for(unsigned i=0;i<4;i++){sizes[i]=stage_pack_bytes[PACK_PPZ0+i];}
            floor_mode=diagnostic_mode=paused=0;era=0;scd_title_card_prepare();load_era();pad.held.button.c=pad.pressed.button.c=0;scd_title_card_start(stage_act);
            act_fade=23;act_fade_offset(-255);
            /* The entry press must not also toggle pause below. */
            pad.held.button.start=0;
            scd_world_mailbox[135]=trace_sequence;scd_world_mailbox[134]=stage_act;
        }
        if(!warp_timer && !replay_active && pad.pressed.button.start && pad.held.button.z) {
            audio_test^=1;scd_audio_test(-1);
        }
        if(!warp_timer && pad.held.button.r && !audio_test) {
            replay_active=1;replay_test=replay_frame=0;diagnostic_mode=floor_mode=paused=0;
            /* Replay tests place Sonic after load_era(): start the camera there, as the
               QA fixtures and playposiset do (camera-X pans at the original's speed). */
            era=scd_replay_era(0);load_era();scd_replay_begin(0);
            player=scd_player_get();camera_y=scd_camera_v_begin(stage_zone,stage_act,era,player.y/65536,player.resets);camera_x=scd_camera_h();
        }
        if(!warp_timer && !replay_active && !audio_test && !(pad.pressed.button.start && pad.held.button.z)) {
            if(pad.held.button.l && pad.pressed.button.start){
                fixture_run=1;
                scd_player_audio_set(NULL);
                if(scd_world_mailbox[0]!=0x574f524c){scd_world_mailbox[0]=0x57414954;scd_world_mailbox[1]=scd_world_probe(packs,sizes,collision_packs);}
                scd_player_audio_set(scd_audio_request);scd_world_mailbox[0]=0x574f524c;
                feature_object=0;floor_mode=diagnostic_mode=paused=0;era=1;load_era();scd_objects_reset(1,0);
                scd_player_place(500,488,0,0,0);scd_player_inventory(5,0);
                unsigned species[]={63,62,61,34,64};
                if(feature_demo<5)scd_objects_spawn(species[feature_demo],560,feature_demo==1 || feature_demo==2?440:493,0,0);
                else if(feature_demo==5){scd_player_place(3040,768,1536,0,0);scd_objects_spawn(SCD_OBJ_TIMEPOST,3040,768,9,0);}
                else if(feature_demo==6){era=0;load_era();}
                else if(feature_demo==52){
                    era=0;load_era();scd_objects_reset(0,0);scd_player_inventory(0,0);
                    feature_object=SCD_OBJ_AMY;scd_objects_spawn(SCD_OBJ_AMY,9664,488,0,0);scd_player_place(9646,522,0,0,1);
                }
                else if(feature_demo>=48){
                    era=feature_demo==48?1:feature_demo==51?3:2;load_era();scd_objects_reset(era,0);scd_player_inventory(0,0);
                    feature_object=feature_demo==48?SCD_OBJ_PROJECTOR:SCD_OBJ_ANIMAL;
                    if(feature_demo==48){
                        scd_objects_spawn(SCD_OBJ_PROJECTOR,5776,786,0,0);
                        /* Two nearby dormant animals isolate release visibility. */
                        scd_objects_spawn(SCD_OBJ_ANIMAL,5688,760,0,0);scd_objects_spawn(SCD_OBJ_ANIMAL,5680,790,1,0);
                        scd_player_place(5776,740,0,0,0);feature_camera_offset=48;
                    }else if(feature_demo==49){scd_objects_spawn(SCD_OBJ_ANIMAL,2210,344,0,0);scd_player_place(2290,344,0,0,2);}
                    else{scd_objects_spawn(SCD_OBJ_ANIMAL,3202,680,1,0);scd_player_place(3122,620,0,0,2);}
                }
                else if(feature_demo>=37){
                    static const int fixtures[11][5]={{0,1912,720,52,0},{0,8912,800,52,1},{0,5448,136,51,0},{1,5440,136,51,0},{2,5448,136,51,1},{3,5448,136,51,1},{1,5432,85,50,0},{1,5540,92,50,1},{2,5491,88,50,2},{3,5491,88,50,2},{0,500,400,51,0}};
                    const int *f=fixtures[feature_demo-37];era=f[0];load_era();scd_objects_reset(era,0);scd_player_inventory(0,0);feature_object=f[3];
                    scd_objects_spawn(f[3],f[1],f[2],f[4],0);
                    /* Original Present placements, outside the vertical tag's
                       player path: fixed-world anchors for camera phase QA.
                       The isolated tag fixture otherwise contains no visible
                       stationary sprites against which to measure drift. */
                    if(feature_demo==38){
                        scd_objects_spawn(SCD_OBJ_SPRING,8816,744,2,0);
                        scd_objects_spawn(SCD_OBJ_SPRING,9072,936,0,0);
                    }
                    scd_player_place(f[1]-(f[3]!=52 && feature_demo!=47?80:0),f[2]-(f[3]!=52 && feature_demo!=47?100:0),0,0,2);
                }
                else if(feature_demo>=32){
                    static const int fixtures[5][5]={{0,2415,792,13,1},{1,6576,296,13,2},{0,2108,552,53,0},{2,7034,614,15,0},{3,7124,740,15,0}};
                    const int *f=fixtures[feature_demo-32];era=f[0];load_era();scd_objects_reset(era,0);scd_player_inventory(0,0);feature_object=f[3];
                    scd_objects_spawn(f[3],f[1],f[2],f[4],0);
                    if(f[3]==13){scd_player_place(f[1],f[2]+12,0,0,2);scd_player_velocity(0,-512);}
                    else if(f[3]==53)scd_player_place(f[1]-60,f[2],0,0,2);
                    else{scd_player_place(f[1],f[2]-70,0,0,2);scd_player_velocity(384,256);feature_camera_offset=64;}
                }
                else if(feature_demo>=29){
                    static const int fixtures[3][3]={{0,4944,904},{2,6640,743},{3,5072,904}};
                    const int *f=fixtures[feature_demo-29];era=f[0];load_era();scd_player_inventory(0,0);
                    scd_player_place(f[1]+8,f[2]-100,0,0,2);
                }
                else if(feature_demo>=25){
                    era=feature_demo-25;load_era();scd_player_inventory(0,0);
                    scd_player_place(era<2?5104:3848,era<2?240:416,0,0,2);
                }
                else if(feature_demo>=21){
                    static const int fixtures[4][4]={{0,3320,544,0},{1,8064,353,197},{2,3920,161,224},{3,4824,288,0}};
                    const int *f=fixtures[feature_demo-21];era=f[0];load_era();scd_objects_reset(era,0);
                    scd_player_place(f[1],f[2]-110,0,0,2);scd_player_inventory(0,0);
                    scd_objects_spawn(SCD_OBJ_COLLAPSE,f[1],f[2],f[3],0);feature_camera_offset=64;
                }
                else if(feature_demo>=16){feature_object=SCD_OBJ_TIMEPOST;scd_player_place(560,410,0,0,2);scd_player_inventory(0,0);scd_objects_spawn(SCD_OBJ_TIMEPOST,560,493,feature_demo-16,0);}
                else if(feature_demo>=14){era=feature_demo==14?0:2;load_era();scd_player_place(9800,feature_demo==14?450:710,1536,0,0);scd_player_inventory(23,1);}
                else if(feature_demo>=12){era=feature_demo==12?1:0;load_era();scd_player_place(feature_demo==12?3550:8590,feature_demo==12?489:660,0,0,2);scd_player_inventory(5,1);}
                else if(feature_demo==11){era=0;load_era();scd_player_place(2700,710,0,0,2);scd_player_inventory(0,0);scd_objects_spawn(SCD_OBJ_ANTON,2840,734,0,0);}
                else {
                    era=feature_demo==7?1:feature_demo==9?3:0;load_era();
                    scd_player_place(feature_demo==8?4187:1456,feature_demo==8?96:450,0,0,2);scd_player_inventory(5,1);
                }
                /* load_era ran its lead object update at the act start; the fixture
                   placed Sonic elsewhere, so the spawner starts again on his camera. */
                scd_objects_spawner_restart();
                feature_demo=(feature_demo+1)%53;
                player=scd_player_get();
                /* QA fixtures place Sonic after load_era(): start the camera there, as
                   playposiset does for a level start (no pan from the old spawn). */
                camera_y=scd_camera_v_begin(stage_zone,stage_act,era,player.y/65536,player.resets);
                camera_x=scd_camera_h();
            } else if(pad.held.button.l) {
                fixture_run=1;
                feature_object=0;floor_mode=diagnostic_mode=paused=0;era=1;load_era();scd_replay_begin(object_demo);
                if(++object_demo>16)object_demo=8;
            }
            if(pad.pressed.button.start && pad.held.button.x) {floor_mode=0;paused=0;load_era();}
            else if(pad.held.button.x) {era=(era+1)&3;floor_mode=0;load_era();}
            if(pad.held.button.y) {floor_mode^=1;if(floor_mode)floor_configure();else load_era();}
            if(pad.held.button.z) {diagnostic_mode^=1;floor_mode=0;load_era();}
            if(pad.held.button.start && !pad.pressed.button.x && !pad.pressed.button.l){
                if((player.routine==8 && !player.lives) || scd_act_get().phase==SCD_ACT_DONE){paused=0;era=stage_act==2?era:0;load_era();}else paused^=1;
            }
            /* Level/Main.asm .CheckReset: in Time Attack, A, B or C while paused ends the run. */
            if(scd_ta.mode && paused && !act_fade && (pad.held.button.a || pad.held.button.b || pad.held.button.c)){paused=0;act_fade=1;}
        }
        unsigned buttons=(pad.pressed.button.up?SCD_UP:0)|(pad.pressed.button.down?SCD_DOWN:0)|
            (pad.pressed.button.left?SCD_LEFT:0)|(pad.pressed.button.right?SCD_RIGHT:0)|
            ((pad.pressed.button.a || pad.pressed.button.b || pad.pressed.button.c)?SCD_JUMP:0);
        /* Attract demo (src/frontend_view.inc): retail input; Start, the end or a game over return to the title. */
        if(demo_slot){
            if(pad.held.button.start || demo_frame>=0x800 || scd_player_get().game_over){demo_slot=0;paused=0;act_fade=0;title_begin(1);continue;}
            buttons=frontend_demo_buttons();paused=0;
        }
        if(replay_active) {
            if(replay_frame==SCD_REPLAY_FRAMES) {
                replay_test++;replay_frame=0;
                if(replay_test==SCD_REPLAY_COUNT){replay_active=0;paused=1;}
                else {era=scd_replay_era(replay_test);load_era();scd_replay_begin(replay_test);
                    player=scd_player_get();camera_y=scd_camera_v_begin(stage_zone,stage_act,era,player.y/65536,player.resets);camera_x=scd_camera_h();}
            }
            if(replay_active)buttons=scd_replay_buttons(replay_test,replay_frame);
        }
        profile_mark(0);
        scd_audio_pause(paused || audio_test);
        if(audio_test) {
            if(pad.held.button.a)scd_audio_test(0);
            if(pad.held.button.b)scd_audio_test(1);
            if(pad.held.button.c)scd_audio_test(2);
        }
        scd_audio_update();
        scd_trace_mailbox[23]=scd_audio_status();
        profile_mark(1);
        simulation_tick=vblank_ticks;
        scd_object_stats frame_objects;int frame_objects_valid=0;
        if(stage_select_single_program && act_fade==1 && special_pending && scd_act_get().phase==SCD_ACT_DONE){
            /* Results sets restart2; LevelStart specialStage returns through WHITE,
               before the ordinary act-fade branch can darken the picture. */
            stage_select_scene_finish(9);continue;
        }
        if(warp_timer){
            if(--warp_timer==0 || pad.held.button.start){
                warp_timer=0;era=warp_destination;scd_audio_warp(0);travel_loading=1;load_era();travel_loading=0;
            }
        } else if(act_fade && !floor_mode && !diagnostic_mode && !audio_test) {
            unsigned step=act_fade<=22?act_fade:act_fade-22;int level=step*36>255?255:(int)step*36;
            act_fade_offset(act_fade<=22?-level:fade_white?255-level:level-255);
            /* IPX StageSelect calls one RunMMD; never its normal RunLevel wrapper.
               Normal deaths with lives stay inside that program (LevelStart). */
            if(act_fade==22 && stage_select_single_program){
                stage_select_scene_finish(scd_player_get().game_over?3:
                    scd_act_get().phase==SCD_ACT_DONE?(special_pending?9:2):
                    stage_zone==6 && stage_act==2 && scd_boss8_game_end()?7:8);continue;
            }
            /* IPX.asm TimeAttack: the level returns to the menu (act clear or no lives). */
            if(act_fade==22 && scd_ta.mode){time_attack_finish(!scd_player_get().game_over && scd_act_get().phase==SCD_ACT_DONE);continue;}
            if(act_fade==22 && scd_player_get().game_over){
                /* Level/Main.asm with no lives left fades out; IPX.asm GameOver returns to the title. */
                act_fade=0;fade_white=0;title_begin(1);continue;
            }
            if(act_fade==22 && special_pending && stage_act<2){
                /* Results/Main.asm with specialStage set: the special stage (stage 1) runs before the
                   next act, starting from the carried progress and time stones. */
                scd_player_progress progress=scd_player_progress_get();
                if(scd_world_get().good_future)good_future_flags|=1u<<stage_act;
                special_pending=0;special_return_act=stage_act+1;
                if(!special_game_begin(progress.score/10u,progress.next_life/10u,progress.lives,time_stones)){
                    act_fade=0;act_fade_offset(0);simulation_tick=vblank_ticks;frames++;sync_frame();continue;
                }
                special_return_act=0;
            }
            if(act_fade==22 && stage_act==2 && ls_next_zone(stage_zone)<LS_ZONE_COUNT){
                /* Act 3 ends the zone. goodFutureFlags are per zone, so they clear
                   here rather than carrying into the next one. The next zone opens
                   on its Act 1 in the present, keeping score, lives, the extra-life
                   score and the time stones. */
                scd_player_progress progress=scd_player_progress_get();
                if(era==2 || good_future_flags==3 || time_stones==127)saved_good_zones|=1u<<stage_zone;
                good_future_flags=0;
                stage_zone=ls_next_zone(stage_zone);stage_act=0;
                scd_player_zone(stage_zone);scd_objects_zone(stage_zone);scd_world_zone(stage_zone);
                scd_objects_act(0);scd_player_act(0);scd_world_act(0);
                stage_packs_load(PACK_PPZ0,PACK_COL3+1);
                for(unsigned i=0;i<4;i++)sizes[i]=stage_pack_bytes[PACK_PPZ0+i];
                era=0;scd_title_card_prepare();load_era();
                scd_player_progress_set(progress);player=scd_player_get();
                scd_title_card_start(stage_act);act_fade_offset(-255);
                scd_world_mailbox[135]=trace_sequence;scd_world_mailbox[134]=stage_act;
                save_checkpoint(0);
            }else if(act_fade==22 && stage_act==2){
                /* The last zone is over. */
                if(era==2 || good_future_flags==3 || time_stones==127)saved_good_zones|=1u<<stage_zone;
                save_checkpoint(1);prototype_end=1;
            }else if(act_fade==22){
                /* ObjResults_NextLevel: the next act starts with the carried score, lives and
                   extra-life score; rings and time restart. Act 2 starts in the present, Act 3 in
                   the good future only when Acts 1 and 2 both ended with a good future. */
                scd_player_progress progress=scd_player_progress_get();
                if(scd_world_get().good_future)good_future_flags|=1u<<stage_act;
                scd_title_card_prepare();
                if(stage_act==1)act3_load(good_future_flags==3 || time_stones==127?2:3);
                else{
                    stage_act=1;scd_objects_act(1);scd_player_act(1);scd_world_act(1);stage_packs_load(PACK_PPZ0,PACK_COL3+1);
                    for(unsigned i=0;i<4;i++)sizes[i]=stage_pack_bytes[PACK_PPZ0+i];
                    era=0;load_era();
                }
                scd_player_progress_set(progress);player=scd_player_get();
                scd_title_card_start(stage_act);act_fade_offset(-255);
                scd_world_mailbox[135]=trace_sequence;scd_world_mailbox[134]=stage_act;
                save_checkpoint(0);
            }
            if(prototype_end)act_fade=0;
            else if(++act_fade>44){act_fade=0;fade_white=0;act_fade_offset(0);}
        } else if(!floor_mode && !diagnostic_mode && !paused && !audio_test) {
            if(replay_active)scd_replay_tick(replay_test,replay_frame);
            scd_world_state travel=scd_world_get();
            scd_objects_travel_protection(!replay_active && travel.ticks>0);
            scd_act_camera(camera_x,camera_y);scd_boss_camera(camera_x,camera_y);
            /* Replay test 17 teleports Sonic 2850 px and back: the camera moves with
               him, as tools/player_trace.c does (after scd_boss_camera, which
               rewrites the scroll position), since the Object Spawner streams by
               the camera window. */
            if(replay_active && replay_test==17 && (replay_frame==40 || replay_frame==80))scd_camera_h_sync(replay_frame==40?2840:0);
            /* VInt HUD and Sonic precede the card in the original update.
               Releasing its lock takes effect on the following update. */
            int title_locked=scd_title_card_locked();
            /* HUD and Points UpdateHUD skips the tick while ctrlLocked, which R83's
               EMIE8.C sets as plautoflag while it steers Sonic (retail MM3D rows
               8355-8677 locked; the Saturn clock ran 0.5 s ahead). */
            unsigned steered;
            scd_player_hold_clock(title_locked || (stage_zone==6 && stage_act==2 && scd_boss8_auto_control(&steered)));
            if(title_locked)buttons=0;
            /* Sonic/Main.asm ObjSonic_TimeWarp: Sonic keeps updating, unseen,
               from timeWarpTimer 210 to the warp at 230 (src/player.c warp_save). */
            /* Metallic Madness Act 3's ending (EMIE8.C) steers Sonic through swdata. */
            {unsigned automatic;if(stage_zone==6 && stage_act==2 && scd_boss8_auto_control(&automatic))buttons=automatic;}
            scd_player_step(buttons);
            water_frame=1;
            scd_title_card_step();
            int music=scd_player_music_event();if(music>=0)scd_audio_era(music?music:era);
            if(scd_objects_big_ring())special_pending=1;
            if(!replay_active && !fixture_run && scd_act_get().phase==SCD_ACT_DONE)act_fade=1;
            /* EMIE8.C ends the game (gameflag 2, stageno $700) after its white flash. */
            if(!replay_active && !fixture_run && stage_zone==6 && stage_act==2 && scd_boss8_game_end() && !act_fade)act_fade=1;
            /* The game over delay (8 seconds with no lives) ends the level. */
            if(!replay_active && !fixture_run && scd_player_get().game_over)act_fade=1;
            if(scd_act_music())scd_audio_results();
            /* LOADER2.C sub_sync from BOSS_1.C: CD track 24 for the boss, then the zone track. */
            int boss_music=scd_boss_music();
            /* SCD_BOSS_MUSIC_FINAL: BOSS_8.C sub_sync(104), CD track 25 (cue 10). */
            if(boss_music==SCD_BOSS_MUSIC_FINAL)scd_audio_music(10);
            if(boss_music==SCD_BOSS_MUSIC_BOSS)scd_audio_music(8);else if(boss_music==SCD_BOSS_MUSIC_ZONE)scd_audio_music(era);
            /* BOSS_8.C's retail LoadPLC(4)/(5): the fight bank (era entry 0), then Amy's (1). */
            {int plc=scd_boss_fight_art();if(plc && stage_zone==6 && stage_act==2)zone_object_art_stream_slot(plc==4?0:1);}
            /* About 7 FRT ticks per word (VDP1 back references): 1536 words fit an update's slack. */
            if(zone_art_streaming)zone_art_stream_step(1536);
            /* _Events.asm LevEvents_PPZ3 (CheckBossStart): while no boss runs, past X $D70 the
               left bound follows Sonic 160 pixels behind, up to the right bound. */
            if(!stage_zone && stage_act==2 && !bossflag && scd_player_get().x/65536>=0xD70){
                int left=scd_player_get().x/65536-160;
                if(left>=scralim_left)scralim_left=left>scralim_right?scralim_right:left;
            }
            /* SCRCHK.C zone33chk: once BOSS_3.C jaba_last sets bossflag, bossclr_scrset(96)
               aims the bottom bound at 96 and locks the left bound 160 pixels behind
               Sonic; scrchk moves the bottom bound 4 lines per update. */
            if(stage_zone==1 && stage_act==2 && bossflag){
                const short target=96;int x=(uint16_t)(scd_player_get().x/65536-160);
                if(abs(target-scralim_down)<4)scralim_down=target;
                if(scralim_left<=(short)x){scralim_left=scralim_right<(short)x?scralim_right:x;}
                if(scralim_down>target){if(target<(uint16_t)camera_y)scralim_down=camera_y&~1;scralim_down-=4;}
                else if(scralim_down<target)scralim_down+=4;
            }
            /* SCRCHK4.C zone42chk: bottom bound 2048 while camera X < 512, else (or once
               Sonic drowns, mstno 43, or dies) 1808, set at once. The C compares X<<16;
               retail R42A/B probes switch exactly at camera X 511/512 (test_r4_scrchk.py). */
            if(stage_zone==2 && stage_act==1){
                scd_player_state p=scd_player_get();
                scralim_down=p.animation!=43&&p.routine<6&&camera_x<512?2048:1808;
            }
            /* SCRCHK4.C zone43chk: past X 2808 bossclr_scrset(1216) aims the bottom bound at
               1216 and locks the left bound 160 pixels behind Sonic; before that, once
               BOSS_4.C egg4airhead_02 sets bossflag, the bottom bound is 1264. scrchk moves
               the bottom bound 4 lines per update, as for Collision Chaos. */
            if(stage_zone==2 && stage_act==2){
                int x=scd_player_get().x/65536;
                if(x>=2808){
                    const short target=1216;short left=(short)(x-160);
                    if(abs(target-scralim_down)<4)scralim_down=target;
                    if(left>=scralim_left)scralim_left=left>scralim_right?scralim_right:left;
                    if(scralim_down>target){if(target<(uint16_t)camera_y)scralim_down=camera_y&~1;scralim_down-=4;}
                    else if(scralim_down<target)scralim_down+=4;
                }else if(bossflag)scralim_down=1264;
            }
            /* SCRCHK.C zone6chk and scrchk: during the WW3 boss, follow the
               floor Sonic occupies. egg6_jisin also moves the bottom limit;
               the original scroll check counters that motion at each floor. */
            if(stage_zone==4 && stage_act==2){
                scd_player_state ww_player=scd_player_get();
                if(!(bossflag&16))scralim_n_down=1808;
                else{
                    int x=ww_player.x/65536,y=ww_player.y/65536;
                    short target=(short)(x>=2976?464:y<=664?464:y<=1176?976:1488);
                    scralim_n_down=target;
                    if(abs(target-scralim_down)<(x>=2976?4:3))scralim_down=target;
                    if(x>=2976){
                        short left=(short)(x-160);
                        if(left>=scralim_left){
                            if(left>scralim_right)left=scralim_right;
                            scralim_left=scralim_n_left=left;
                        }
                    }
                }
                if(scralim_n_down!=scralim_down){
                    if((unsigned short)scralim_n_down<(unsigned short)scralim_down){
                        if((unsigned short)scralim_n_down<(unsigned short)camera_y)scralim_down=(short)(camera_y&~1);
                        scralim_down-=4;
                    }else scralim_down+=(camera_y+8>=scralim_down && (ww_player.flags&2))?16:4;
                    limmoveflag=1;
                }
            }
            /* SCRCHK8.C zone8chk and scrchk: Acts 1-2 aim the bottom bound at 1808, Act 3
               at 784 until bossflag, then hold it at 268 (which also undoes EMIE8.C's
               emie8_jisin each update); scrchk moves it 4 lines per update, 16 when Sonic
               is airborne with the camera at the bound. */
            if(stage_zone==6){
                scd_player_state mm_player=scd_player_get();
                if(stage_act<2)scralim_n_down=1808;
                else if(!bossflag)scralim_n_down=784;
                else scralim_down=scralim_n_down=268;
                short limwk=(short)(scralim_n_down-scralim_down);
                if(limwk>0){scralim_down+=(camera_y+8>=scralim_down && (mm_player.flags&2))?16:4;limmoveflag=1;}
                else if(limwk<0){if(camera_y>scralim_n_down)scralim_down=(short)(camera_y&~1);scralim_down-=4;limmoveflag=1;}
            }
            player=scd_player_get();
            /* A death restart clears travel before the next TimeWarp check. */
            if(player.resets!=background_resets)scd_world_abort();
            gameplay_hud_step(simulation_tick);
            pacing_record(player.frame);
            if(!replay_active){
                if(scd_objects_generator())scd_world_generator_destroyed();
                unsigned elapsed=world_vblank_previous?simulation_tick-world_vblank_previous:1;
                world_vblank_previous=simulation_tick;
                /* A load or pause is not a run of skipped gameplay updates. */
                if(!elapsed || elapsed>4)elapsed=1;
                int destination=scd_world_step_vblanks(player,elapsed);
                int post=scd_objects_timepost();if(post)scd_world_activate(post);
                if(destination>=0){
                    /* LevelStart .SkipFade returns on timewarp+levelRestart;
                       IPX StageSelect has no RunLevel warp/era continuation. */
                    if(stage_select_single_program){stage_select_scene_finish(4);continue;}
                    warp_destination=destination;warp_timer=240;scd_audio_warp(1);warp_configure();
                }
            }
            scd_player_effect_sample effect_sample=scd_player_effects();
            scd_powerup_runtime_step(&effect_runtime,effect_sample,player.shield,
                !!scd_player_powerups().invincible,scd_world_get().ticks>0);
            scd_effect_mailbox[0]=0;
            scd_effect_mailbox[1]=effect_runtime.updates;scd_effect_mailbox[2]=effect_runtime.submitted;
            scd_effect_mailbox[3]=effect_runtime.context.record_index;
            scd_effect_mailbox[6]=((uint32_t)(uint16_t)effect_sample.record_x<<16)|(uint16_t)effect_sample.record_y;
            scd_effect_mailbox[7]=((uint32_t)(uint16_t)effect_sample.x<<16)|(uint16_t)effect_sample.y;
            scd_effect_mailbox[8]=((uint32_t)effect_runtime.context.flags<<24)|(effect_runtime.context.shield<<16)|
                (effect_runtime.context.invincible<<8)|effect_runtime.context.travel;
            scd_effect_mailbox[9]=player.frame;scd_effect_mailbox[10]=effect_runtime.context.powerup;
            scd_effect_mailbox[11]=era;
            for(unsigned i=0;i<9;i++){
                const scd_powerup_visual *e=&effect_runtime.actors[i];unsigned at=12+i*5;
                scd_effect_mailbox[at]=(e->active<<24)|(e->routine<<16)|(e->animation<<8)|e->previous;
                scd_effect_mailbox[at+1]=(e->cursor<<24)|(e->timer<<16)|(e->mapping<<8)|e->sprite_flags;
                scd_effect_mailbox[at+2]=((uint32_t)e->flags<<24)|(e->phase<<16)|(e->priority<<8)|e->width;
                scd_effect_mailbox[at+3]=((uint32_t)(uint16_t)e->x<<16)|(uint16_t)e->y;
                scd_effect_mailbox[at+4]=e->tile;
            }
            uint32_t words[16];scd_replay_words_snapshot(player,words,&frame_objects);frame_objects_valid=1;
            scd_trace_mailbox[0]=0x53434432;
            scd_trace_mailbox[2]=replay_active?replay_test:0xffffffffu;
            scd_trace_mailbox[3]=replay_frame;
            for(unsigned i=0;i<16;i++)scd_trace_mailbox[4+i]=words[i];
            scd_trace_mailbox[20]=core_result;scd_trace_mailbox[21]=era;
            scd_trace_mailbox[22]=buttons;
            unsigned sequence=++trace_sequence;
            uint32_t visual[2];scd_replay_visual_words(player,visual);
            volatile uint32_t *visual_record=scd_player_visual_trace+(sequence%64)*3;
            visual_record[1]=visual[0];visual_record[2]=visual[1];visual_record[0]=sequence;
            volatile uint32_t *record=scd_trace_mailbox+24+(sequence%64)*21;
            record[1]=scd_trace_mailbox[2];record[2]=replay_active?replay_frame:buttons;
            for(unsigned i=0;i<16;i++)record[3+i]=words[i];
            record[19]=core_result;record[20]=simulation_tick;record[0]=sequence;
            scd_trace_mailbox[1]=sequence;
            if(replay_active)replay_frame++;
            /* Act 3: BOSS_1.C raises the camera line (scra_vline) for the boss arena. A touched big
               ring locks the camera (scrollLock). */
            if(!scd_objects_big_ring_touched()){
                /* GAME.C game: scroll() -> scroll_h, scroll_v (src/camera_v.c); a
                   restart reruns playposiset. QA feature fixtures keep their fixed framing. */
                if(feature_camera_offset){camera_x=player.x/65536-160;camera_y=player.y/65536-140+feature_camera_offset-(stage_act==2?scra_vline-96:0);}
                else {camera_y=scd_camera_v_follow(player.y/65536,player.resets);camera_x=scd_camera_h();}
            }
        } else if(floor_mode || diagnostic_mode) {
            int step=pad.pressed.button.a?16:4;
            if(pad.pressed.button.right)camera_x+=step;
            if(pad.pressed.button.left)camera_x-=step;
            if(pad.pressed.button.down)camera_y+=step;
            if(pad.pressed.button.up)camera_y-=step;
        }
        if(camera_x<0)camera_x=0;
        if(camera_x>16064)camera_x=16064;
        if(camera_y<0)camera_y=0;
        /* scr_set clamps the camera to scralim_down in every act.  Act 1 used to
           carry a fixed 1824 here, which is 16 past Palmtree Panic's own limit and
           far past the 784 that Quartz Quadrant and Stardust Speedway ask for. */
        if(camera_y>scralim_down)camera_y=scralim_down;
        camera_v_sync=1;
        if(!floor_mode && !diagnostic_mode){
            scd_act_state result=scd_act_get();
            /* scr_dir_tbl limits; the Act 3 boss and level events move them. */
            if(camera_x>scralim_right)camera_x=scralim_right;
            if(camera_x<scralim_left)camera_x=scralim_left;
            if(result.goal && camera_x<result.left)camera_x=result.left;
            /* Level End's sign sets only leftBound = cameraX (Level End/Main.asm:527):
               Y keeps following and X may still move right to the right bound. The
               capsule and Stardust Speedway goal phases hold the camera. */
            if(result.phase && !result.sign){camera_x=result.camera_x;camera_y=result.camera_y;}
        }
        /* The displayed camera is the original scra_v_posit (goal/fixture locks included). */
        if(camera_v_sync){scd_camera_v_sync(camera_y);scd_camera_h_sync(camera_x);camera_v_sync=0;}
        /* GAME4.C game: scroll(), watercoli, patset, watercnt (Tidal Tempest only). */
        if(water_frame){
            water_camera(camera_x,camera_y);water_currents();water_objects_visible();water_level_step();water_frame=0;
        }
        if(player.resets!=background_resets){
            scd_audio_era(era);scd_background_reset(&background_scroll,camera_x);
            /* GAME.C game_init reloads the level's art on a restart: a death after
               BOSS_8.C's LoadPLC(4)/(5) needs the stage bank back. */
            if(zone_art_bank_loaded){zone_object_art_load();boss_clut_state=-1;}
            if(!era && scd_player_checkpoint().id)background_scroll.ramp=checkpoint_ramp;
            background_resets=player.resets;
        }
        if(scd_player_checkpoint().id!=background_checkpoint){
            background_checkpoint=scd_player_checkpoint().id;checkpoint_ramp=background_scroll.ramp;
        }
        if(player.frame!=background_frame){
            scd_background_step(&background_scroll,bg_id(),camera_x,player.vx,player.ramp);background_frame=player.frame;
        }
        profile_mark(2);profile_draw_reset();
        if(floor_mode) {
            angle_t angle=(angle_t)(camera_x*8);
            fix16_t c=fix16_cos(angle),s=fix16_sin(angle);
            rotation.matrix.param.a=c;rotation.matrix.param.b=(uint32_t)-s;
            rotation.matrix.param.d=s;rotation.matrix.param.e=c;
            rotation.mx=fix16_int32_from(camera_x);rotation.my=fix16_int32_from(camera_y+frames/2);
            vdp_dma_enqueue((void *)VDP2_VRAM_ADDR(1,0),&rotation,sizeof(rotation));
        } else if(warp_timer)warp_draw();else {
            if(stage_zone==4 && stage_act==2 && era>=2)scd_r6_set_bossflag(bossflag);
            draw_stage();
            if(stage_zone==4 && stage_act==2 && era>=2)
                bossflag=(unsigned char)scd_r6_cg_change((unsigned)stage_act*4u+(unsigned)era,bossflag);
        }
        update_ticks=cpu_frt_count_get();
        profile_mark(6);
        if(!floor_mode && !diagnostic_mode)vdp2_scrn_display_set(warp_timer?VDP2_SCRN_DISP_NBG1:VDP2_SCRN_DISPTP_NBG0|VDP2_SCRN_DISPTP_NBG1);
        /* The replay already collected the complete post-update snapshot.
           Rendering/background work does not mutate the object pool. Other
           branches (loading, pause, diagnostics) collect a fresh snapshot. */
        scd_world_state world=scd_world_get();scd_object_stats objects=frame_objects_valid?frame_objects:scd_objects_get();
        scd_world_mailbox[138]=scd_boss_position();scd_world_mailbox[139]=scd_boss_status();
        /* The zone the player is in, so a test harness can see a zone change.
           Slot 140 already carries the time stones, hence the new slot at the end. */
        scd_world_mailbox[142]=stage_zone;
        scd_world_mailbox[140]=time_stones;scd_world_mailbox[141]=((uint32_t)scd_objects_big_ring_touched()<<16)|((uint32_t)special_mode<<8)|special_return_act;
        scd_world_mailbox[130]=objects.amy_grabs;scd_world_mailbox[131]=objects.amy_hearts;scd_world_mailbox[132]=scd_objects_amy_palette(NULL);scd_world_mailbox[133]=(uint32_t)scd_objects_amy_idle_frame();
        scd_world_mailbox[51]=scd_objects_projector_destroyed();scd_world_mailbox[52]=objects.projector_hits;scd_world_mailbox[53]=objects.projector_explosions;scd_world_mailbox[54]=objects.holograms;scd_world_mailbox[55]=objects.animals;scd_world_mailbox[56]=player.frame;
        scd_world_mailbox[46]=objects.tag_contacts;scd_world_mailbox[47]=((uint32_t)(uint16_t)player.vx<<16)|(uint16_t)player.vy;scd_world_mailbox[48]=(uint32_t)player.speed;scd_world_mailbox[49]=player.animation;scd_world_mailbox[50]=((uint32_t)(uint16_t)(player.x/65536-camera_x)<<16)|(uint16_t)(player.y/65536-camera_y);
        scd_world_mailbox[43]=objects.doors_opened;scd_world_mailbox[44]=(objects.wheel_reversals<<16)|objects.attached;scd_world_mailbox[45]=objects.springs;
        scd_act_state result=scd_act_get();scd_world_mailbox[26]=result.phase;scd_world_mailbox[27]=result.time_bonus;scd_world_mailbox[28]=result.ring_bonus;scd_world_mailbox[29]=player.score;scd_world_mailbox[30]=result.total_bonus;scd_world_mailbox[31]=result.goal;
        scd_powerup_state power=scd_player_powerups();scd_world_mailbox[32]=player.rings;scd_world_mailbox[33]=((unsigned)power.invincible<<16)|power.shoes;scd_world_mailbox[34]=((unsigned)objects.monitors<<16)|objects.items;scd_world_mailbox[35]=player.shield;
        scd_world_mailbox[36]=((unsigned)objects.collapsed<<16)|objects.collapse_pieces;scd_world_mailbox[37]=objects.collapse_live;scd_world_mailbox[38]=player.control;scd_world_mailbox[39]=(player.disc_angle<<16)|(player.disc_radius<<8)|player.disc_frame;
        scd_world_mailbox[24]=objects.broken;scd_world_mailbox[25]=objects.debris;
        scd_world_mailbox[20]=scd_player_checkpoint().id;scd_world_mailbox[21]=player.resets;scd_world_mailbox[22]=(player.routine<<16)|(player.lives<<8)|player.game_over;scd_world_mailbox[23]=player.elapsed;
        scd_world_mailbox[2]=world.era;scd_world_mailbox[3]=world.ticks;scd_world_mailbox[4]=world.transitions;
        scd_world_mailbox[5]=world.cancelled;scd_world_mailbox[6]=world.good_future;scd_world_mailbox[7]=warp_timer;
        scd_world_mailbox[8]=objects.defeated;scd_world_mailbox[9]=objects.projectiles;scd_world_mailbox[10]=objects.active;scd_world_mailbox[11]=player.ramp;scd_world_mailbox[12]=(uint32_t)background_scroll.ramp;scd_world_mailbox[13]=(uint32_t)(player.x/65536);scd_world_mailbox[14]=scd_player_arrival_adjusted();scd_world_mailbox[16]=player.flags;scd_world_mailbox[17]=scd_objects_standing_type();scd_world_mailbox[18]=(uint32_t)(player.y/65536);scd_world_mailbox[15]=((uint32_t)MEMORY_READ(16,VDP2_VRAM_ADDR(3,0x1bffe))<<16)|vdp2_scrn_display_get();
        profile_mark(7);sprite_draw();
        scd_effect_mailbox[4]=camera_x;scd_effect_mailbox[5]=camera_y;
        /* Publish fixture identity only after its sprite state/coordinates.
           An emulator VBlank can interrupt between mailbox writes. Publishing
           it earlier lets the checker pair a new fixture with the old sprite. */
        scd_world_mailbox[19]=feature_demo;
        if(effect_runtime.updates)scd_effect_mailbox[0]=0x504f5756;
        profile_mark(8);profile_commit();
#if SCD_FRAME_PROFILE
        for(unsigned i=28;i<32;i++)profile_values[i]=0;
#endif
        water_raster_commit(water_screen_line());
        frames++;sync_frame();
        back_color_commit();
        water_raster_latch();
    }
}
void user_init(void) {
    vdp2_tvmd_display_res_set(VDP2_TVMD_INTERLACE_NONE,VDP2_TVMD_HORZ_NORMAL_A,VDP2_TVMD_VERT_224);
    smpc_peripheral_init();vdp_sync_vblank_out_set(input_poll,NULL);
    cpu_frt_init(CPU_FRT_CLOCK_DIV_8);
    vdp1_env_t env;vdp1_env_default_init(&env);vdp1_env_set(&env);
    vdp2_sprite_priority_set(0,4);vdp2_sprite_priority_set(1,7);
    vdp2_tvmd_display_set();
}
