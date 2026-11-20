/* Quartz Quadrant Act 3 boss services: the actor table and the palette work
 * area that the generated BOSS_5.C/COLI5.C (tools/prepare_boss_r5.py) write.
 * The PC services they share with the other bosses are in src/boss.c. */
#include "BOSS5_ZONE.H"
#include "EQU.H"
#include "BOSS_5.H"
#include "boss_zone.h"
#include <stddef.h>
#include <stdint.h>
#include <string.h>

/* ACT53.C act_tbl[actno-1] for the actors BOSS_5.C spawns and the layout's two. The
   boss code runs from the R5 overlay (BOSS5_ZONE.H); src/boss.c reaches it only
   through r5_boss_zone_ops. */
static void (*z5_boss_routine(unsigned id))(sprite_status *){
    switch(id){
    case 32:return egg5hibana;case 33:return egg5hari;case 34:return egg5belt;case 35:return egg5bakuha;
    case 50:return egg5;case 51:return egg5meca1;case 52:return egg5meca2;case 53:return egg5meca3;
    case 54:return egg5pipe;case 55:return egg5catch;case 56:return egg5bomb;case 57:return egg5bomb2;
    default:return NULL;
    }
}
short boss5_pcol(sprite_status *p); /* COLI5.C pcol (generated boss_5.c) */
const scd_boss_zone_ops r5_boss_zone_ops={.routine=z5_boss_routine,.pcol=boss5_pcol};
/* BOSS_5.C set_belt_col writes lpcolorwk[42..44] (line 2, colours 10-12): the
   belt's scrolling stripes. The work area keeps them for the renderer; it is
   shared with src/boss_r6.c (one definition wins at link time). */
__attribute__((weak)) PALETTEENTRY scd_boss_colorwk[64];
#define colorwk scd_boss_colorwk
const PALETTEENTRY *scd_boss5_belt_colors(void){return &colorwk[42];}
/* The belt's colours as CRAM words (line 2, colours 10-12; the eight PC channel
   levels expanded to RGB555, as tools/convert_assets.py palette). 0 until the belt
   has written them since the last reset. */
int scd_boss5_belt_palette(uint16_t out[3]){
    if(!colorwk[42].peFlags)return 0;
    for(unsigned i=0;i<3;i++){
        const PALETTEENTRY *e=&colorwk[42+i];
        out[i]=(uint16_t)(0x8000u|(e->peRed>>5)*31/7|((e->peGreen>>5)*31/7)<<5|((e->peBlue>>5)*31/7)<<10);
    }
    return 1;
}
void scd_boss5_reset(void){memset(colorwk,0,sizeof(colorwk));lpcolorwk=colorwk;}
