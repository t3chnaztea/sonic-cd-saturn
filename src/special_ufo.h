#ifndef SCD_SPECIAL_UFO_H
#define SCD_SPECIAL_UFO_H
#include <stddef.h>
#include <stdint.h>
/* Path offsets replace original PRG pointers; all game values retain their
   original byte/word/16.16 widths. Open once before following a path. */
typedef struct {const uint8_t *data;size_t size;} scd_special_ufo_path;
typedef struct {const uint8_t *data;size_t size;} scd_special_ufo_paths;
typedef struct {
    uint32_t x,y,x_velocity,y_velocity,sprite_x,sprite_y;
    uint16_t path_offset,path_time,z;
    uint8_t id,flags,player_collision,item,unknown;
} scd_special_ufo;
/* Actor fields beyond the primitives: oTimer word, oAnim, oVar52 distance
   animation, oVar53 explode direction, oVar64 draw delay, DrawObject state. */
typedef struct {
    scd_special_ufo u;
    uint16_t timer;
    uint8_t routine,animation,ufo_animation,explode_dir,draw_delay,frame,time,time_copy,art;
} scd_special_ufo_actor;
typedef struct {
    uint32_t x,y,sprite_x,sprite_y;
    uint16_t z;
    uint8_t id,routine,flags,animation,shadow_animation,frame,time,time_copy,art;
} scd_special_shadow;
/* Set3DSpritePos for any object; -1 is the original zero-divisor trap. */
int scd_special_project(uint16_t sonic_x,uint16_t sonic_y,uint16_t x,uint16_t y,uint16_t z,unsigned yaw,uint32_t *sprite_x,uint32_t *sprite_y);
void scd_special_on_screen(uint8_t *flags,uint32_t sprite_x,uint32_t sprite_y);
/* Indices 0..47 are eight stages of six UFOs; 48 is the time UFO. */
int scd_special_ufo_paths_open(scd_special_ufo_paths *paths,const void *data,size_t size);
int scd_special_ufo_path_get(const scd_special_ufo_paths *paths,unsigned index,scd_special_ufo_path *path);
int scd_special_ufo_path_open(scd_special_ufo_path *path,const uint8_t *data,size_t size);
int scd_special_ufo_follow(scd_special_ufo *u,const scd_special_ufo_path *path);
int scd_special_ufo_move(scd_special_ufo *u,const scd_special_ufo_path *path);
/* yaw is the pre-object graphics yaw. Sonic XY is the updated actor position. */
int scd_special_ufo_project(scd_special_ufo *u,uint16_t sonic_x,uint16_t sonic_y,unsigned yaw);
void scd_special_ufo_on_screen(scd_special_ufo *u);
void scd_special_ufo_collision(scd_special_ufo *u,uint16_t sonic_x,uint16_t sonic_y,uint16_t sonic_z,uint8_t sonic_id,uint8_t *sonic_collision);
uint32_t scd_special_ufo_distance(uint16_t x,uint16_t y,uint16_t sonic_x,uint16_t sonic_y);
unsigned scd_special_ufo_animation(uint32_t distance);
#endif
