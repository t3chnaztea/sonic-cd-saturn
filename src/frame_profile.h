#ifndef SCD_FRAME_PROFILE_H
#define SCD_FRAME_PROFILE_H
/* Diagnostic-only switch. Restore 0 before a candidate build. Changing this
   header rebuilds main.c; no stale command-line compiler flag is involved. */
#define SCD_FRAME_PROFILE 0
#if SCD_FRAME_PROFILE
/* Header: magic, published sequence, record stride, reserved. Each record:
   sequence, player frame, starting VBlank, nine FRT durations, nine ending
   VBlanks, camera X/Y, sprite command count (low half; the high half is
   the previous update's slack: FRT from its end to the next VBlank-in, the
   vdp2_sync deadline, or 0xffff unless exactly one VBlank-in followed it); words 24..27 are sprite
   construction, clear wait, command transfer and draw completion durations.
   In WW, word 29 packs HUD ticks in the high half and ring-spawn ticks low;
   word 30 packs Sonic texture ticks high and ring-command ticks low.
   In R5, word 30 instead marks 0x52350001 for a switch hold or 0x52350006
   for a full redraw with completed slave work.
   FRT is CPU/8, 16 bits. VBlank stamps expose intervals that might wrap;
   do not interpret long loading frames as unwrapped CPU measurements. */
volatile uint32_t scd_frame_profile[4+64*32];
static uint32_t profile_values[32],profile_sequence;
static uint16_t profile_previous,profile_end,profile_slack=0xffff;
static volatile uint16_t profile_vbin_frt;
static volatile uint32_t profile_vbin_count;
static uint32_t profile_end_count;
static int profile_audio_vblank;
void ponesound_vblank_rq(void *work);
void scd_vdp1_overrun_sample(void);
/* Replaces the audio VBlank-in callback (src/audio.c) and chains to it. */
static void profile_vblank_in(void *work){
    profile_vbin_frt=cpu_frt_count_get();profile_vbin_count++;
    scd_vdp1_overrun_sample();
    if(profile_audio_vblank)ponesound_vblank_rq(work);
}
static void profile_vblank_install(int audio){
    profile_audio_vblank=audio;vdp_sync_vblank_in_set(profile_vblank_in,NULL);
}
static uint16_t profile_sprite_previous;
static void profile_sprite_begin(void){profile_sprite_previous=cpu_frt_count_get();}
static void profile_sprite_mark(unsigned phase){
    uint16_t now=cpu_frt_count_get();
    profile_values[24+phase]=(uint16_t)(now-profile_sprite_previous);
    profile_sprite_previous=now;
}
static void profile_begin(void){
    profile_previous=cpu_frt_count_get();
    profile_slack=profile_vbin_count-profile_end_count==1?(uint16_t)(profile_vbin_frt-profile_end):0xffff;
    profile_values[2]=vblank_ticks;
}
static void profile_mark(unsigned phase){
    uint16_t now=cpu_frt_count_get();
    profile_values[3+phase]=(uint16_t)(now-profile_previous);
    profile_values[12+phase]=vblank_ticks;
    profile_previous=now;
}
static void profile_draw_reset(void){
    cpu_frt_count_set(0);profile_previous=0;
}
static void profile_commit(void){
    profile_end=cpu_frt_count_get();profile_end_count=profile_vbin_count;
    profile_values[0]=++profile_sequence;profile_values[1]=player.frame;
    profile_values[21]=camera_x;profile_values[22]=camera_y;
    profile_values[23]=(uint32_t)profile_slack<<16|(uint16_t)sprite_commands->count;
    volatile uint32_t *out=scd_frame_profile+4+(profile_sequence%64)*32;
    for(unsigned i=1;i<32;i++)out[i]=profile_values[i];
    out[0]=profile_sequence;scd_frame_profile[2]=32;
    scd_frame_profile[0]=0x46505246;scd_frame_profile[1]=profile_sequence;
}
#else
#define profile_begin() ((void)0)
#define profile_sprite_begin() ((void)0)
#define profile_sprite_mark(phase) ((void)0)
#define profile_mark(phase) ((void)0)
#define profile_draw_reset() cpu_frt_count_set(0)
#define profile_commit() ((void)0)
#define profile_vblank_install(audio) ((void)(audio))
#endif
#endif
