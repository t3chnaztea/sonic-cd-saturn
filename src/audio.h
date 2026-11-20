#ifndef SCD_AUDIO_H
#define SCD_AUDIO_H
#include <stdint.h>
/* Logical cues: 0..3 era, 4 results, 5 shoes, 6 invincibility, 7 special,
   8 boss, 9 title, 10 final boss. Era cues use the current stage zone. */
void scd_audio_stage(unsigned zone,unsigned era);
/* Load a swappable effect bank (0 PPZ, 1 CC, 2 special stage, 3 TT; -1 none). */
void scd_audio_bank(int bank);
int scd_audio_bank_current(void);
/* Change the music cue without stopping effects (actor sub_sync requests). */
void scd_audio_music(unsigned cue);
void scd_audio_era(unsigned era);
/* Start a song from its beginning and repeat it (D.A. Garden); no effect bank is loaded. */
void scd_audio_music_loop(unsigned zone,unsigned cue);
void scd_audio_results(void);
void scd_audio_update(void);
uint32_t scd_audio_status(void);
/* diagnostics.master is UINT32_MAX: MVOL is write-only, no readback claim. */
typedef struct {unsigned ready,bank,copy,heartbeat,toc,track,state;int cd_init;unsigned driver_copy,master,left,right,start,init_response;} scd_audio_diagnostics;
scd_audio_diagnostics scd_audio_get_diagnostics(void);
void scd_audio_test(int kind);
void scd_audio_warp(int active);
void scd_audio_stop_music(void);
/* Source rate0x20 fade after independently accepted clock admission; faults latch. */
void scd_audio_cdda_fade(unsigned rate);
extern volatile uint32_t scd_audio_cdda_gate[8];
void scd_audio_init(void);
void scd_audio_request(short request);
void scd_audio_pause(int paused);
#endif
