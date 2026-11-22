/* Stardust Speedway Act 3 boss services (the Metal Sonic race): the actor
 * table, the palette work areas and the art kinds for the generated
 * BOSS_7.C/COLI7.C (tools/prepare_boss_r7.py). The PC services they share
 * with the other bosses are in src/boss.c. */
#include "BOSS7_ZONE.H"
#include "EQU.H"
#include "boss_zone.h"
#include "scd_boss.h"
#include "BOSS_7.H"
#include <stddef.h>
#include <stdint.h>
#include <string.h>

/* ACT73.C act_tbl[actno-1] for egg7 (the layout's), the actors it spawns and hahen73. */
static void (*z7_boss_routine(unsigned id))(sprite_status *){
    switch(id){
    case 44:return egg7;case 45:return egg7jet;case 46:return egg7beam;case 47:return msnc;
    case 48:return msnc_ele;case 49:return msnc_bara;case 55:return hahen73;default:return NULL;
    }
}
short boss7_pcol(sprite_status *);
const scd_boss_zone_ops r7_boss_zone_ops={.routine=z7_boss_routine,.pcol=boss7_pcol};
/* BOSS_7.C emie7clrset writes Amy's colours into lpcolorwk[16..31] and
   lpcolorwk3[16..31] (line 1 and its fade copy) when egg7 leaves. lpcolorwk is
   shared with src/boss_r5.c and src/boss_r6.c (one definition wins at link time). */
__attribute__((weak)) PALETTEENTRY scd_boss_colorwk[64];
static PALETTEENTRY colorwk3[64];
/* Amy's line 1 once egg7_goal3 has run: 1 and the 16 PC colours, else 0. */
int scd_boss7_amy_colors(const PALETTEENTRY **line){*line=&scd_boss_colorwk[16];return scd_boss_colorwk[16].peFlags!=0;}
void scd_boss7_statics(void);
void scd_boss7_reset(void){
    memset(scd_boss_colorwk,0,sizeof(scd_boss_colorwk));memset(colorwk3,0,sizeof(colorwk3));
    lpcolorwk=scd_boss_colorwk;lpcolorwk3=colorwk3;
    scd_boss7_statics();
}
/* Zone art kind (tools/extract_mmd.py SS_BOSS_KIND) of a BOSS_7.C actor, 0 for none:
   240 egg7, 241 egg7jet, 242 egg7beam, 243 msnc, 244 msnc_ele, 245 msnc_bara,
   246 hahen73; egg7beam's smoke and msnc_lose's blast (bakupat) are the common
   explosion frames. */
#ifdef SCD_BOSS_REFERENCE
#include "BOSS7_PATTERNS.H"
#define PAT(name) SCD_PATTERN7_##name
#else
extern sprite_pattern *bakupat[];
#define PAT(name) name
#endif
unsigned scd_boss7_kind(const sprite_status *p){
    switch(p->actno){
    case 44:return 240;case 45:return 241;
    case 46:return p->patbase==PAT(bakupat)?24u:242;
    case 47:return 243;case 48:return 244;case 49:return 245;case 55:return 246;
    default:return 0;
    }
}

/* COL7C/D.C bosscolor, 3-bit channels expanded as the stage palettes. */
static const uint16_t boss7_colors[2][6]={{0x9084,0xc41f,0x81bf,0x83ff,0xffff,0x83e0},{0x9084,0xc41f,0x81bf,0x83ff,0xffff,0x83e0}};
void scd_boss7_palette(uint16_t *line,unsigned bad,int restore){
    if(restore)return;
    const PALETTEENTRY *amy;
    if(scd_boss7_amy_colors(&amy)){
        for(unsigned i=0;i<16;i++)line[i]=0x8000|(amy[i].peRed/32*31/7)|((amy[i].peGreen/32*31/7)<<5)|((amy[i].peBlue/32*31/7)<<10);
    }else if(scd_boss_palette()==SCD_BOSS_PALETTE_BOSS7)memcpy(line,boss7_colors[!!bad],sizeof(boss7_colors[0]));
}
