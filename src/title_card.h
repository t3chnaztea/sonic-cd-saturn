#ifndef SCD_TITLE_CARD_H
#define SCD_TITLE_CARD_H
#include <stdint.h>
/* Screen position (VDP sprite coordinates minus 128) and mapping frame. */
typedef struct {int16_t x,y;uint8_t frame;} scd_title_card_view;
/* The zone's ObjTitleCard_Data (8 pieces x y, x, target x, frame<<8|timer). */
void scd_title_card_layout(const uint16_t rows[8][4]);
void scd_title_card_start(unsigned act);
/* Before a load that scd_title_card_start follows: the original card inits in
   the first RunObjects, before the dynamic actors, so its pieces take their
   dynamic slots before the load's first object update (src/main.c runs that
   update inside load_era). No effect on the card itself. */
void scd_title_card_prepare(void);
/* One level update; returns nonzero while controls stay locked. */
int scd_title_card_step(void);
/* Sample before player/HUD work; the later card step affects the next update. */
int scd_title_card_locked(void);
/* Removes the card at once (the R43C and R82A attract demos start without one). */
void scd_title_card_stop(void);
int scd_title_card_active(void);
/* Extra updates the card's PLC 2 wait holds controls for one program
   (native zone, act, era A-D = 0-3); 0 for an unknown program. */
unsigned scd_title_card_plc_wait(unsigned zone,unsigned act,unsigned era);
/* Supplied by src/world.c (weak default in src/title_card.c: no program). */
int scd_title_card_program(unsigned *zone,unsigned *act,unsigned *era);
unsigned scd_title_card_views(scd_title_card_view *views,unsigned capacity);
#endif
