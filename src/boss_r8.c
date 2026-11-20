/* Metallic Madness Act 3 boss services: the actor table, the palette work
 * areas and the art kinds for the generated BOSS_8.C/COLI8.C/COL8C/D.C
 * (tools/prepare_boss_r8.py). The PC services they share with the other
 * bosses are in src/boss.c. egg8 itself is spawned by HOTA8C/D.C's room
 * controller (3840,316). egg8_dead spawns Amy (emie8, 67): the generated
 * EMIE8.C (build/probe-source/ending_8.c) ends the game after the flash. */
#include "BOSS8_ZONE.H"
#include "EQU.H"
#include "boss_zone.h"
#include "BOSS_8.H"
#include <stddef.h>
#include <stdint.h>
#include <string.h>

/* ACT83.C act_tbl[actno-1] for egg8, the actors it spawns and Amy (67). */
void emie8(sprite_status *);
static void (*z8_boss_routine(unsigned id))(sprite_status *){
    switch(id){
    case 63:return egg8;case 64:return egg8hane;case 65:return egg8meca;case 66:return egg8hibana;case 67:return emie8;default:return NULL;
    }
}
short boss8_pcol(sprite_status *);
void boss8_colorset2(int);
const scd_boss_zone_ops r8_boss_zone_ops={.routine=z8_boss_routine,.pcol=boss8_pcol,.colorset2=boss8_colorset2};
/* The explosion actor draws on palette line 0 (PLAYSUB.C bakuhawk sproffset
   $8680), which EMIE8.C flash_out8 whitens with the rest of CRAM; the Saturn
   atlas frames hold fixed RGB CLUTs. From the first line-0 change after the
   stage load (state 0 seeds, 1 seeded) the frames draw from `copies`
   (state 2): count CLUTs, then the line-0 image they were last mapped from.
   Each colour moves from its old line-0 entry to that entry's new colour. */
static void z8_explosion_cluts(const uint16_t *pal,uint8_t *state,volatile uint16_t *copies,const volatile uint16_t *atlas,
    const unsigned *offsets,const unsigned *widths,const unsigned char *heights,unsigned first,unsigned count){
    volatile uint16_t *line0=copies+count*16;
    unsigned same=*state!=0;for(unsigned j=0;j<16;j++){if(line0[j]!=pal[j])same=0;}
    if(!*state){for(unsigned j=0;j<16;j++)line0[j]=pal[j];*state=1;return;}
    if(same)return;
    for(unsigned f=0;f<count;f++){
        const volatile uint16_t *from=*state==1?atlas+(offsets[first+f]+widths[first+f]*heights[first+f]/2)/2:copies+f*16;
        for(unsigned c=0;c<16;c++){uint16_t v=from[c];for(unsigned j=1;j<16 && c;j++)if(v==line0[j]){v=pal[j];break;}copies[f*16+c]=v;}
    }
    for(unsigned j=0;j<16;j++)line0[j]=pal[j];
    *state=2;
}
void (*const volatile r8_explosion_cluts)(const uint16_t *,uint8_t *,volatile uint16_t *,const volatile uint16_t *,
    const unsigned *,const unsigned *,const unsigned char *,unsigned,unsigned)=z8_explosion_cluts;
/* colchg_boss8 cycles lpcolorwk[24..27]; fadein_boss8 fades lpcolorwk[16..31]
   (and [48..63] in the Bad Future) toward lpcolorwk2, colorset2(7)'s target.
   lpcolorwk is shared with the other rounds' boss files. */
__attribute__((weak)) PALETTEENTRY scd_boss_colorwk[64];
static PALETTEENTRY colorwk2[64];
/* scd_boss8_palette's lpcolorwk seed (see there). */
/* r8_seed lives in the R8 overlay (src/saturn.x .data.r8_b8_*): only
   scd_boss8_palette (MM3) touches it, and r8_seeded gates every read. */
#if defined(__sh__)
__attribute__((section(".data.r8_b8_seed")))
#endif
static PALETTEENTRY r8_seed[64];static uint64_t r8_written;static int r8_seeded;
void scd_boss8_reset(void){
    /* GAME.C clears plautoflag at every stage start; EMIE8.C sets it. */
    gameflag.w=0;plautoflag=0;
    memset(scd_boss_colorwk,0,sizeof(scd_boss_colorwk));memset(colorwk2,0,sizeof(colorwk2));
    lpcolorwk=scd_boss_colorwk;lpcolorwk2=colorwk2;
    r8_seeded=0;r8_written=0;
}
/* Zone art kind (tools/extract_mmd.py MM_BOSS_KIND) of a BOSS_8.C actor, 0 for none:
   240 egg8, 241-246 egg8hane (egg8hane0_pat1/2/3, egg8hane1_pat, egg8hane2_pat1/2),
   247 egg8meca, 248 egg8hibana. */
#ifdef SCD_BOSS_REFERENCE
#include "BOSS8_PATTERNS.H"
#define PAT(name) SCD_PATTERN8_##name
#else
extern sprite_pattern *egg8hane0_pat1[],*egg8hane0_pat2[],*egg8hane0_pat3[],*egg8hane1_pat[],*egg8hane2_pat1[],*egg8hane2_pat2[];
#define PAT(name) name
#endif
unsigned scd_boss8_kind(const sprite_status *p){
    switch(p->actno){
    case 63:return 240;
    case 64:
        return p->patbase==PAT(egg8hane0_pat1)?241:p->patbase==PAT(egg8hane0_pat2)?242:p->patbase==PAT(egg8hane0_pat3)?243:
            p->patbase==PAT(egg8hane1_pat)?244:p->patbase==PAT(egg8hane2_pat1)?245:246;
    case 65:return 247;case 66:return 248;
    case 67:return 249; /* emie8 (Amy), tools/extract_mmd.py -boss-ending */
    default:return 0;
    }
}
/* EMIE8.C emie8_l2 ends the game: gameflag 2, stageno $700 (after flash_out8). */
int scd_boss8_game_end(void){return gameflag.w==2;}
/* PLAYER.C reads the pad into swdata only while plautoflag is 0: EMIE8.C
   steers Sonic by writing swdata, which the next update's Sonic reads. */
int scd_boss8_auto_control(unsigned *buttons){if(!plautoflag)return 0;*buttons=(uint8_t)swdata.b.h;return 1;}
/* On the original every lpcolorwk entry is live palette. Entries no colorset2
   flagged hold the CRAM colour seeded here, so a write to one (EMIE8.C
   flash_out8 whitens all 64) reaches CRAM, and keeps reaching it, as there. */
void scd_boss8_palette(uint16_t *pal){
    for(unsigned i=0;i<64;i++){
        PALETTEENTRY *e=&scd_boss_colorwk[i];
        if(!e->peFlags && r8_seeded && (e->peRed!=r8_seed[i].peRed || e->peGreen!=r8_seed[i].peGreen || e->peBlue!=r8_seed[i].peBlue))r8_written|=1ull<<i;
        if(e->peFlags || (r8_written>>i&1))pal[i]=0x8000|(e->peRed/32*31/7)|((e->peGreen/32*31/7)<<5)|((e->peBlue/32*31/7)<<10);
        else{
            unsigned c=pal[i];
            e->peRed=(unsigned char)(((c&31)*7+15)/31*32);e->peGreen=(unsigned char)(((c>>5&31)*7+15)/31*32);e->peBlue=(unsigned char)(((c>>10&31)*7+15)/31*32);
        }
        r8_seed[i]=*e;
        /* lpcolorwk2 is the level's fade palette, which holds the zone palette
           (zone83dcolor): fadein_boss8 fades D's black [48..63] back to it. */
        if(!r8_seeded)colorwk2[i]=*e;
    }
    r8_seeded=1;
}
/* IMPFUNCS.H sMemSet, the PC import EMIE8.C clears clchgtim with
   (host fixtures supply their own). */
static void r8_memset(void *p,unsigned char v,int n){memset(p,v,(size_t)n);}
__attribute__((weak)) void (*sMemSet)(void *,unsigned char,int)=r8_memset;
