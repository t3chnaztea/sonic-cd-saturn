#ifndef SCD_DAGARDEN_H
#define SCD_DAGARDEN_H
#include <stddef.h>
#include <stdint.h>
/* D.A. Garden (DA Garden/Main.asm, Sub.asm and Objects, USA) advanced one V-INT at a
   time, as src/title.c runs the title. Each call runs the V-INT routine, then the Main
   CPU program up to its next VSync. The Sub CPU program (planet object, music and planet
   data changes, the graphics operation) runs where the Main CPU hands it a command
   (UpdateSubCPU); the ASIC render into the image buffer can run on another processor
   (render_start/render_wait). The Mega Drive state keeps original values: VRAM bytes
   (planet image buffers at 0 and $5800, plane A at $C000, plane B at $E000, sprite table
   at $EC00), CRAM, VSRAM and the plane A H-scroll word. The Main CPU program's own
   lag (frames without a V-INT) comes from scd_dagarden_lag_frames, measured on the
   retail disc (tools/dagarden_retail.py). */
enum {SCD_DG_PARTS=49,SCD_DG_OBJECTS=16,SCD_DG_IMAGE=32*22*32,SCD_DG_TRACKS=32};
typedef struct {const uint8_t *data;uint32_t size,offset[SCD_DG_PARTS],length[SCD_DG_PARTS];} scd_dagarden_pack;
/* Object slot (Main.asm object structure); positions and speeds are 16.16. map is an
   offset into the tables part (0: none). */
typedef struct {
    uint16_t id,routine;
    int32_t x,y,xvel,yvel;
    int16_t xoff,yoff,float_angle;
    uint16_t anim_time,anim_frame,tile,map;
    uint8_t flags,spawn_id;
    int16_t dest_x,dest_y,float_speed,float_amp;
    int8_t timer,timer2;
} scd_dagarden_object;
typedef struct scd_dagarden_s {
    const scd_dagarden_pack *pack;
    /* Mega Drive VDP. */
    uint8_t vram[0x10000];
    uint16_t cram[64],vsram[2],hscroll_a;
    uint8_t display,done;
    /* VRAM written since the view took it: name table rows (plane A, plane B), pattern
       tiles below $E000 (plane A's border tile $6FF is at $DFE0), and every tile for the
       view's sprite textures. */
    uint32_t plane_dirty[2],tile_dirty[56],sprite_dirty[64];
    /* Main CPU variables (Main.asm Variables). */
    uint16_t palette[64],fade[64];
    uint8_t sprites[80*8];
    uint8_t planet_image[SCD_DG_IMAGE];
    scd_dagarden_object objects[SCD_DG_OBJECTS];
    uint16_t sel_routine,sel_id,sel_title,sel_dir;
    uint16_t cycle_timer,cycle_index,volcano_timer,volcano_index,sprite_cycle_timer,sprite_cycle_index;
    int16_t buf_count,routine;
    uint8_t sel_flags,spawn_flags,spawn_id,button_flags,fade_start,fade_len,no_cycle;
    uint16_t spawn_timers[6];
    uint16_t timer,vint,zone;
    uint32_t seed,lag;
    /* Main CPU register d1: its high word reaches several DIVS dividends (UFO, Tails, Eggman). */
    uint32_t d1;
    /* Nemesis art loaded since the last V-INT (decoded plus compressed bytes, for the lag) and its LoadArt ID. */
    uint32_t art_bytes,title_bytes;
    uint8_t art_last;
    uint8_t kos_zone;
    /* GACOMCMDE: controller held and tapped bits (read in V-INT routines 0 and 2). */
    uint8_t hold,tap;
    /* Gate array: Main and Sub CPU communication flags, GACOMCMD8 (track) and GACOMCMDA (time zone). */
    uint8_t main_flags,sub_flags;
    uint16_t cmd_track,cmd_zone;
    /* Main program position (dagarden.c steps), its counter, and the music the Sub CPU
       program last started (index into the track list; 0xFF none; set when it changes). */
    uint16_t step,count;
    uint8_t music,music_changed;
    /* Sub CPU: planet object and graphics operation (Sub.asm). */
    uint8_t planet_routine,planet_flags;
    int16_t planet_angle,planet_x,planet_y,planet_z,scale_dir,angle_dir;
    int32_t angle_speed;
    /* Word RAM: stamps ($0-$A000, stamp n at n*512), the 8x7 stamp map at $20000 (the rest
       of the 128x128 map stays 0), the trace table and the image buffer. */
    uint8_t stamps[0xA000];
    uint16_t stamp_map[7][8];
    uint16_t trace[176*4];
    uint8_t rendered[SCD_DG_IMAGE];
    /* Optional asynchronous rendering, as the Sub CPU does it: RunGfxOperation calls
       render_start after the trace table is written; the Main CPU's GetPlanetImage calls
       render_wait first. Without them the image is rendered at once. */
    void (*render_start)(void *context),(*render_wait)(void *context);
    void *render_context;
    /* Optional: called after the V-INT routine, before the Main CPU program continues (QA). */
    void (*after_vint)(const struct scd_dagarden_s *t);
    /* Stamp pixels (one byte each) for every map cell, refreshed when the cell changes. */
    uint16_t cell_key[7][8];
    uint8_t cells[7][8][1024];
} scd_dagarden;
int scd_dagarden_open(scd_dagarden_pack *pack,const void *data,size_t size);
/* Main.asm Start up to the first VSync (the D.A. Garden track already plays: SPX.asm
   SPCmd_LoadDAGarden starts it before the program). */
int scd_dagarden_start(scd_dagarden *t,const scd_dagarden_pack *pack);
/* pad: Mega Drive buttons (Start, A, C, B, Right, Left, Down, Up from bit 7). Returns 0
   while running and 1 once the program has returned (Start, after the fade). */
int scd_dagarden_vint(scd_dagarden *t,unsigned pad);
/* The graphics operation of the last RunGfxOperation into the rendered image buffer. */
void scd_dagarden_render(scd_dagarden *t);
/* Frames the retail Main CPU program misses before the next V-INT (VInt_Lag). */
unsigned scd_dagarden_lag_frames(const scd_dagarden *t);
/* Music of a D.A. Garden track (Sub.asm PlayCDDAMusic) for scd_audio_music_loop: zone<<4|era
   for a zone song (era 0 present, 2 good future, 3 bad future), else 0x100|music cue. */
unsigned scd_dagarden_track_music(unsigned track);
/* The Saturn build runs D.A. Garden from the front-end overlay (fe_ names, src/saturn.x
   .zone_R0); resident code calls it through this table after scd_frontend_overlay_load(). */
typedef struct {
    int (*open)(scd_dagarden_pack *pack,const void *data,size_t size);
    int (*start)(scd_dagarden *t,const scd_dagarden_pack *pack);
    int (*vint)(scd_dagarden *t,unsigned pad);
    void (*render)(scd_dagarden *t);
    unsigned (*lag_frames)(const scd_dagarden *t);
    unsigned (*track_music)(unsigned track);
} scd_dagarden_ops;
extern const scd_dagarden_ops fe_dagarden_zone_ops;
static inline const scd_dagarden_ops *scd_dagarden_ops_get(void){
    const scd_dagarden_ops *volatile ops=&fe_dagarden_zone_ops;return ops;
}
#endif
