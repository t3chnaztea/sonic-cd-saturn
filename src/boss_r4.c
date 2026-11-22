/* Tidal Tempest Act 3 boss services: the actor table, and the layout wall's
 * reload, for the generated BOSS_4.C/BOSS_4_2.C/WALL4.C/COLI4.C
 * (tools/prepare_boss_r4.py). The PC services they share with the other
 * bosses are in src/boss.c. */
#include "BOSS4_ZONE.H"
#include "EQU.H"
#include "BOSS_4.H"
#include "BOSS_4_2.H"
#include "WALL4.H"
#include "ACTSET.H"
#include "scd_boss.h"
#include "boss_zone.h"
#include <stddef.h>
#include <string.h>

/* ACT43C.C act_tbl[actno-1] for the actors BOSS_4.C, BOSS_4_2.C and the layout spawn.
   The boss code runs from the R4 overlay (BOSS4_ZONE.H); src/boss.c reaches it only
   through r4_boss_zone_ops. */
static void (*z4_boss_routine(unsigned id))(sprite_status *){
    switch(id){
    case 71:return wall4;case 74:return egg4air;case 75:return egg4airhead;case 76:return egg4;
    case 77:return egg4meca;case 78:return egg4tama;case 79:return egg4awa;default:return NULL;
    }
}
short boss4_pcol(sprite_status *p); /* COLI4.C pcol (generated boss_4.c) */
const scd_boss_zone_ops r4_boss_zone_ops={.routine=z4_boss_routine,.pcol=boss4_pcol};
/* The layout's wall4 (R43C/R43D: 1056,768). The PC loader gives each layout
   actor its load index in cdsts and marks flagwork[time_flag+cdsts*3] bit 7
   while it is loaded; WALL4.C keeps its lowered state in bit 0 and frameout_s_
   clears bit 7 when it unloads. 254 stays clear of make_gate's cdsts 0 and of
   the end of flagwork (766 bytes). */
#define LAYOUT_CDSTS 254u
static struct {int16_t x,y;uint8_t used,sub;} layout_wall;
static unsigned wall_flag(void){return time_flag+LAYOUT_CDSTS*3u;}
static void wall_load(void){
    sprite_status *p;
    if(actwkchk(&p))return;
    p->actno=71;p->xposi.w.h=layout_wall.x;p->yposi.w.h=layout_wall.y;p->userflag.b.h=layout_wall.sub;p->cdsts=LAYOUT_CDSTS;
    flagwork[wall_flag()]|=128;
}
void scd_boss4_wall(int x,int y,unsigned sub){
    layout_wall.x=(int16_t)x;layout_wall.y=(int16_t)y;layout_wall.sub=(uint8_t)sub;layout_wall.used=1;
    if(!(flagwork[wall_flag()]&128))wall_load();
}
/* The loader's reload: within 480 of Sonic (src/objects.c stream) and not loaded. */
void scd_boss4_stream(void){
    if(!layout_wall.used || (flagwork[wall_flag()]&128))return;
    int d=actwk[0].xposi.w.h-layout_wall.x;
    if(d<=480 && d>=-480)wall_load();
}
/* A new act or a restart reloads the layout; GAME4.C clears flagwork. */
void scd_boss4_reset(void){
    memset(&layout_wall,0,sizeof(layout_wall));
    for(unsigned era=0;era<3;era++){flagwork[era]=0;flagwork[era+LAYOUT_CDSTS*3u]=0;}
}
/* PLAYSUB4.C plairset (COLI4.C: a popped egg4awa bubble gives air) is src/water.c's
   water_air_refill; a build without the water code has no air to refill. */
__attribute__((weak)) void water_air_refill(void){}
__attribute__((weak)) void plairset(void){water_air_refill();}
