/* Wacky Workbench Act 3 boss services: the actor table, the layout's doors and
 * the COL6C/D.C palette services that the generated BOSS_6.C/COLI6.C
 * (tools/prepare_boss_r6.py) call beyond those in src/boss.c. */
#include "BOSS6_ZONE.H"
#include "EQU.H"
#include "BOSS_6.H"
#include "boss_zone.h"
#include "scd_boss.h"
#include <stddef.h>
#include <stdint.h>
#include <string.h>

/* ACT63.C act_tbl[actno-1] for the actors BOSS_6.C spawns and the layout's egg6boss/egg6door. */
static void (*z6_boss_routine(unsigned id))(sprite_status *){
    switch(id){
    case 52:return egg6boss;case 53:return egg6meca0;case 54:return egg6meca1;case 55:return egg6meca2;
    case 56:return egg6toge;case 57:return egg6gareki;case 61:return egg6yuka;case 62:return egg6door;
    case 63:return egg6bakuha;case 64:return egg6beam;default:return NULL;
    }
}
short boss6_pcol(sprite_status *p); /* COLI6.C pcol in generated boss_6.c */
const scd_boss_zone_ops r6_boss_zone_ops={.routine=z6_boss_routine,.pcol=boss6_pcol};
/* Z63ACT.C egg6door placements (both futures): userflag.b.h is the door kind
   (bit 7 the beam emitter, bit 0 the right-hand door), userflag.b.l the floor's
   beam bit (5 bottom, 6 middle, 7 top), the bits egg6door_beamer tests in bossstart. */
int actwkchk(sprite_status **actor);
void scd_boss6_door(int x,int y,unsigned kind,unsigned floor){
    sprite_status *p;
    if(actwkchk(&p))return;
    scd_boss_set_round(6);
    p->actno=62;p->xposi.w.h=(short)x;p->yposi.w.h=(short)y;p->userflag.b.h=(unsigned char)kind;p->userflag.b.l=(unsigned char)floor;
}
/* The PC palette work areas: lpcolorwk (shared with src/boss_r5.c; line 1 is
   colorset2's target, 32 and 55-63 fset_boss6's) and lpcolorwk2 (colorset's). */
__attribute__((weak)) PALETTEENTRY scd_boss_colorwk[64];
static PALETTEENTRY colorwk2[64];
static int fade_flag;
static unsigned colorset_calls;
/* COL6C/D.C colorset: colortbl[ColorNo] into lpcolorwk2 (the fade target). Only
   BOSS_6.C's colorset(6) (boss6col, colours 16-31) reaches it here; the native
   palette takes the boss colours from src/boss.c colorset2. */
void colorset(int ColorNo){(void)ColorNo;colorset_calls++;}
/* COL6C/D.C flashout: FadeProc brightens every colour toward white for 22 updates. */
void flashout(void){startcolor=0;colorcnt=63;*lpFadeFlag=4;}
/* COL6C/D.C flashin_boss6: colours 0-47 white, then FadeProc fades them back in. */
void flashin_boss6(void){
    startcolor=0;colorcnt=47;
    PALETTEENTRY *e=&lpcolorwk[startcolor>>1];
    for(short d0=0;d0<=colorcnt;d0++,e++){e->peRed=224;e->peGreen=224;e->peBlue=224;e->peFlags=1;}
    *lpFadeFlag=3;
}
/* FadeProc's request: 4 flash out, 3 flash in, 0 none. The renderer consumes it. */
int scd_boss6_fade(void){int f=fade_flag;fade_flag=0;return f;}
unsigned scd_boss6_colorsets(void){return colorset_calls;}
void scd_boss6_statics(void);
void scd_boss6_reset(void){
    memset(scd_boss_colorwk,0,sizeof(scd_boss_colorwk));memset(colorwk2,0,sizeof(colorwk2));
    lpcolorwk=scd_boss_colorwk;lpcolorwk2=colorwk2;lpFadeFlag=&fade_flag;fade_flag=0;colorset_calls=0;
    scd_boss6_statics();
}
/* Zone art kind (tools/extract_mmd.py WW_BOSS_KIND) of a BOSS_6.C actor, 0 for none:
   240 egg6boss, 241 egg6meca0, 242 egg6meca1, 243 egg6meca2, 244 egg6toge,
   245 egg6gareki, 246 its four pieces (egg6gareki4_pat), 247 egg6yuka, 248 egg6door,
   249 the beam emitters (egg6beamer_pat), 250 egg6bakuha, 251-253 egg6beam
   (egg6beam_pat, egg6beam2_pat, egg6beam3_pat). */
#ifdef SCD_BOSS_REFERENCE
#include "BOSS6_PATTERNS.H"
#define PAT(name) SCD_PATTERN6_##name
#else
extern sprite_pattern *egg6gareki4_pat[],*egg6beamer_pat[],*egg6beam2_pat[],*egg6beam3_pat[];
#define PAT(name) name
#endif
unsigned scd_boss6_kind(const sprite_status *p){
    switch(p->actno){
    case 52:return 240;case 53:return 241;case 54:return 242;case 55:return 243;case 56:return 244;
    case 57:return p->patbase==PAT(egg6gareki4_pat)?246:245;
    case 61:return 247;
    case 62:return p->patbase==PAT(egg6beamer_pat)?249:248;
    case 63:return 250;
    case 64:return p->patbase==PAT(egg6beam3_pat)?253:p->patbase==PAT(egg6beam2_pat)?252:251;
    default:return 0;
    }
}
