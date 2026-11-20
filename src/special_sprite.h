#ifndef SCD_SPECIAL_SPRITE_H
#define SCD_SPECIAL_SPRITE_H
#include <stddef.h>
#include <stdint.h>
#include "special_player.h"
typedef struct {const uint8_t *data;uint32_t length,animations,poses,entries,animation_offset,entry_offset,pose_offset,palette_offset,texture_offset;} scd_special_art;
typedef struct {uint8_t tilt,animation,frame,time,time_copy,art;} scd_special_sprite;
typedef struct {const uint8_t *pixels;int16_t x,y;uint16_t width,height,flip,index;} scd_special_pose;
int scd_special_art_open(scd_special_art *art,const void *data,size_t size);
void scd_special_sprite_set(scd_special_sprite *sprite,const scd_special_art *art,unsigned animation,int reset);
void scd_special_sprite_tilt(scd_special_sprite *sprite,unsigned held);
void scd_special_sprite_choose(scd_special_sprite *sprite,scd_special_player *player,const scd_special_art *art,int inactive);
int scd_special_sprite_advance(scd_special_sprite *sprite,const scd_special_player *player,const scd_special_art *art,scd_special_pose *pose);
#endif
