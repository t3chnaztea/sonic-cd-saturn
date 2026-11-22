#ifndef SCD_SPECIAL_H
#define SCD_SPECIAL_H
#include <stddef.h>
#include <stdint.h>
#define SCD_SPECIAL_WIDTH 256
#define SCD_SPECIAL_HEIGHT 96
#define SCD_SPECIAL_PARTS 7
#define SCD_SPECIAL_UPDATE_VBLANKS 3
#define SCD_SPECIAL_UPDATES_PER_SECOND 20
/* Original 13.3 row starts and signed 5.11 pixel increments. */
typedef struct {uint16_t x,y;int16_t dx,dy;} scd_special_line;
typedef struct {int16_t x,y,z,pitch,yaw;} scd_special_camera;
typedef struct {uint16_t fan,hazard,delay;} scd_special_animation;
typedef struct {const uint8_t *part[7];uint32_t size[7];unsigned stage;} scd_special_stage;
int scd_special_open(scd_special_stage *stage,const uint8_t *data,size_t size);
int scd_special_sine(unsigned angle);
/* Returns -1 for division by zero. DIVS overflow preserves the original
   destination low word, as consumed by the following word operations. */
int scd_special_trace(scd_special_line lines[96],scd_special_camera camera);
unsigned scd_special_pixel(const scd_special_stage *stage,int x,int y);
int scd_special_stamp_type(const scd_special_stage *stage,int x,int y,unsigned *orientation);
void scd_special_render(const scd_special_stage *stage,const scd_special_line lines[96],uint8_t *pixels,unsigned stride);
/* Build only the stamp orientations used by this map. Cache is aligned to
   uint32_t; indices are native endian, pixels are byte indices. */
size_t scd_special_cache(const scd_special_stage *stage,void *cache,size_t capacity);
void scd_special_render_cached(const void *cache,const scd_special_line lines[96],uint8_t *pixels,unsigned stride);
void scd_special_render_cached_map(const void *cache,const uint16_t *map,const scd_special_line lines[96],uint8_t *pixels,unsigned stride);
void scd_special_render_rows(const void *cache,const uint16_t *map,const scd_special_line *lines,uint8_t *pixels,unsigned stride,unsigned rows);
void scd_special_reciprocals(const scd_special_line *lines,unsigned rows,uint32_t *reciprocals);
void scd_special_render_span(const void *cache,const uint16_t *map,const scd_special_line *lines,const uint32_t *reciprocals,uint8_t *pixels,unsigned stride,unsigned rows,unsigned first,unsigned count);
unsigned scd_special_animate(const scd_special_stage *stage,scd_special_animation *animation,uint8_t *raw_map,const void *cache,uint16_t *cached_map);
#endif
