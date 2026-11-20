/* Test-only observer of the real player's animation call. No substitute
   animation implementation: retail 68000 execution checks the recorded rows. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "sonic_animation.h"
#include "scd_player.h"
unsigned scd_animation_audit_calls;
static FILE *events;
static void close_events(void){assert(!fclose(events));}
void scd_player_animation_audit(const scd_sonic_animation *before,
    const scd_sonic_animation *after,int16_t speed,uint8_t angle,uint8_t flags,uint8_t control){
    if(!events){const char *name=getenv("SCD_ANIMATION_EVENTS");assert(name);events=fopen(name,"wb");assert(events);assert(!atexit(close_events));}
    scd_player_state p=scd_player_get();
    scd_sonic_animation exposed={p.animation,p.animation_previous,p.animation_cursor,
        p.animation_timer,p.mapping,p.render_flags};
    assert(!memcmp(after,&exposed,sizeof(exposed)));
    unsigned char row[17];memcpy(row,before,6);
    row[6]=(uint16_t)speed>>8;row[7]=(uint16_t)speed;row[8]=angle;row[9]=flags;row[10]=control;
    memcpy(row+11,after,6);assert(fwrite(row,1,sizeof(row),events)==sizeof(row));
    scd_animation_audit_calls++;
}
