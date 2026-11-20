#ifndef SCD_SONIC_FRAMES_H
#define SCD_SONIC_FRAMES_H
#include <stdint.h>
#include <stddef.h>
#include "sonic_art.h"
typedef struct {const uint8_t *data;size_t size;} scd_sonic_frames;
int scd_sonic_frames_open(scd_sonic_frames *out,const uint8_t *data,size_t size);
/* Precomposed original DPLC poses, lossless word RLE. Exactly 1024 texture
   words and 16 common-palette words; global flips remain sprite commands. */
int scd_sonic_frames_decode(const scd_sonic_frames *frames,unsigned id,uint16_t output[1040]);
/* Resumable decode of the same data: begin, then step with a word budget
   until it returns 1 (done) or -1 (corrupt). The output buffer must stay
   untouched by others between steps. */
typedef struct {const scd_sonic_frames *frames;const uint8_t *p,*end;unsigned n,left;uint16_t value;uint8_t literal;} scd_sonic_frames_cursor;
int scd_sonic_frames_begin(const scd_sonic_frames *frames,unsigned id,scd_sonic_frames_cursor *cursor);
int scd_sonic_frames_step(scd_sonic_frames_cursor *cursor,uint16_t output[1040],unsigned budget);
#endif
