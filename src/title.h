#ifndef SCD_TITLE_H
#define SCD_TITLE_H
#include <stddef.h>
#include <stdint.h>
/* Title screen program (Title Screen/Main.asm and Sub.asm, USA) advanced one
   V-INT at a time. Each call runs the V-INT routine, then the Main CPU program
   up to its next VSync; the cloud image is rendered when RenderClouds asks the
   Sub CPU. The Mega Drive state keeps original values: VRAM bytes (tiles, plane
   A at $C000, plane B at $E000), CRAM and H-scroll words and the sprite table
   as the V-INT left them. Cheats, the second controller and demo mode are not
   part of this program. */
enum {SCD_TITLE_PARTS=31,SCD_TITLE_OBJECTS=10,SCD_TITLE_IMAGE=12288,SCD_TITLE_STAMP_SLOTS=32};
typedef struct {const uint8_t *data;uint32_t size,offset[SCD_TITLE_PARTS],length[SCD_TITLE_PARTS];} scd_title_pack;
typedef struct {
    uint8_t active,flags,kind,map,frame;
    uint16_t resume,tile;
    int16_t x,y;
    /* Object variables: delay counters, animation index, menu option, selection flag, arrow side, parent slot. */
    uint8_t delay,index,option,allow,side,parent;
} scd_title_object;
typedef struct {
    const scd_title_pack *pack;
    uint8_t vram[0x10000];
    uint16_t cram[64],hscroll[448];
    uint8_t sat[640];
    uint8_t display,enable_display,done,exit_code,text_loaded,save_available;
    /* titleFlags bits from the Time Attack file (src/time_attack.h): bit 5 adds TIME ATTACK. */
    uint8_t title_flags;
    /* ObjMenu_SoundTestCheat progress (oMenuSndTestIdx). */
    uint8_t sound_test_index;
    /* ObjMenu_BestTimesCheat progress (oMenuBestTmsIdx), independent of sound test. */
    uint8_t best_times_index;
    /* ObjMenu_StageSelCheat progress (oMenuStgSelIdx). */
    uint8_t stage_select_index;
    /* Name table rows (plane A, plane B) and pattern tiles below $C000 written since the view took
       them, and every tile written since the view last checked its sprite textures. */
    uint32_t plane_dirty[2],tile_dirty[48],sprite_dirty[64];
    uint16_t palette[64],fade[64];
    uint8_t fade_start,fade_colors,mode,cycle_frame,cycle_delay,exit_flag,menu_sel,menu_options[8],hold,tap;
    uint16_t vint,timer,routine,step,count;
    uint8_t clouds_image[SCD_TITLE_IMAGE],rendered[SCD_TITLE_IMAGE];
    uint16_t hscroll_buffer[448];
    uint32_t water[64];
    uint8_t sprites[640],sprite_count;
    uint16_t sprite_slot;
    scd_title_object objects[SCD_TITLE_OBJECTS];
    /* Sub CPU graphics operation variables and the stamp cache (32x32 pixels per stamp and orientation). */
    int16_t cam_x,cam_y,cam_z,pitch,yaw;
    uint16_t trace[96*4];
    /* Per image line, the horizontal sampling of the last trace: runs of pixels in one stamp column
       and each pixel's offset in its stamp (the clouds keep the X start and step from image to image). */
    uint16_t sample_x[96],sample_dx[96],run_count[96];
    uint8_t runs[96][256][2],offsets[96][256];
    /* Optional asynchronous rendering, like the Sub CPU: RenderClouds calls render_start after the
       trace table is written, GetCloudsImage calls render_wait before it reads the image. Without
       them the image is rendered at once. scd_title_start clears them. */
    void (*render_start)(void *context),(*render_wait)(void *context);
    void *render_context;
    uint8_t cells[16384],stamp_slots;
    uint8_t stamp_cache[SCD_TITLE_STAMP_SLOTS*1024];
} scd_title;
int scd_title_open(scd_title_pack *pack,const void *data,size_t size);
/* Main.asm Start up to the first VSync. */
int scd_title_start(scd_title *t,const scd_title_pack *pack);
/* pad: Mega Drive buttons (Start, A, C, B, Right, Left, Down, Up from bit 7).
   Returns 0 while running and 1 once returned (exit_code: 1 new game, 2 Continue,
   3 Time Attack, 4 RAM DATA, 7 sound test, 8 stage select, 9 best staff times, 0 attract mode).
   Set save_available after scd_title_start. */
int scd_title_vint(scd_title *t,unsigned pad);
/* The graphics operation of the last RenderClouds request into the rendered image buffer. */
void scd_title_render(scd_title *t);
/* Frames the original Main CPU program misses before the next V-INT (VInt_Lag), as measured on the retail disc. */
unsigned scd_title_lag_frames(const scd_title *t);
/* The Saturn build runs the title from the front-end overlay (src/title_names.h):
   resident code calls it through this table once scd_frontend_overlay_load() is done. */
typedef struct {
    int (*open)(scd_title_pack *pack,const void *data,size_t size);
    int (*start)(scd_title *t,const scd_title_pack *pack);
    int (*vint)(scd_title *t,unsigned pad);
    void (*render)(scd_title *t);
    unsigned (*lag_frames)(const scd_title *t);
} scd_title_ops;
extern const scd_title_ops fe_title_zone_ops;
static inline const scd_title_ops *scd_title_ops_get(void){
    const scd_title_ops *volatile ops=&fe_title_zone_ops;return ops;
}
#endif
