/* Collision Chaos Act 3 boss services: the actor table and the PC services
 * that the generated BOSS_3.C/GATE.C/COLI3.C (tools/prepare_boss_r3.py) call
 * beyond those in src/boss.c. */
#include "BOSS3_ZONE.H"
#include "EQU.H"
#include "BOSS_3.H"
#include "GATE.H"
#include "boss_zone.h"
#include <stdint.h>
#include <stddef.h>

/* ACT33C.C act_tbl[actno-1] for the actors BOSS_3.C spawns. The boss code runs
   from the R3 overlay (BOSS3_ZONE.H); src/boss.c reaches it only through
   r3_boss_zone_ops. */
static void (*z3_boss_routine(unsigned id))(sprite_status *){
    switch(id){
    case 48:return egg3dai_s;case 49:return egg3dai_l;case 50:return egg3haguruma;case 51:return egg3;
    case 61:return egg3cannon;case 62:return punchbom;case 63:return gate;default:return NULL;
    }
}
short boss3_pcol(sprite_status *p); /* COLI3.C pcol (generated boss_3.c) */
const scd_boss_zone_ops r3_boss_zone_ops={.routine=z3_boss_routine,.pcol=boss3_pcol};
/* TBL1.C explosion animation (punchbom_bomset). The pattern table is only an
   identity here: the native explosion frames draw it. */
static unsigned char baku_chg0[7]={3,0,5,6,3,4,252},baku_chg1[7]={3,0,1,2,3,4,252};
char *bakuchg[2]={(char *)baku_chg0,(char *)baku_chg1};
sprite_pattern *bakupat[7];
