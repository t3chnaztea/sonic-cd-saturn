#ifndef SCD_SPECIAL_PLAYER_H
#define SCD_SPECIAL_PLAYER_H
#include <stdint.h>
/* Native NTSC special-stage motion. World, yaw and sprite positions retain
   original 16.16 fractions; byte/word state deliberately wraps. */
typedef struct {
    uint32_t x,y,yaw,sprite_y,sprite_velocity;
    uint16_t z,speed,top_speed,shoes,jump_timer,bump_time;
    uint8_t routine,flags,scroll,hurt,stamp_c,stamp_tl,stamp_tr,stamp_br,stamp_bl,orientation;
    uint32_t x_velocity,y_velocity;
} scd_special_player;
void scd_special_player_speed(scd_special_player *p,unsigned held,int inactive);
void scd_special_player_rotate(scd_special_player *p,unsigned held,int inactive);
void scd_special_player_move(scd_special_player *p);
int scd_special_player_jump(scd_special_player *p,unsigned tapped,int inactive);
void scd_special_player_air(scd_special_player *p,unsigned held,int inactive);
void scd_special_player_spring(scd_special_player *p);
void scd_special_player_fan(scd_special_player *p);
uint32_t scd_special_player_probe(unsigned *count);
#endif
