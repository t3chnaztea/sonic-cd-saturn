#ifndef SCD_SPRITE_ORDER_H
#define SCD_SPRITE_ORDER_H
#include <stdint.h>
#include "scd_objects.h"
#define SCD_DRAW_CAPACITY 160
/* Input is original submission order, frontmost first within a priority.
   Saturn overwrites earlier pixels: emit priorities 7..0, each in reverse.
   Eight linked buckets avoid sorting/moving full VDP1 commands. */
static inline int scd_sprite_order(const uint8_t *priority,unsigned count,uint8_t *order){
    if(count>SCD_DRAW_CAPACITY)return -1;
    uint8_t heads[8]={255,255,255,255,255,255,255,255},next[SCD_DRAW_CAPACITY];
    for(unsigned i=0;i<count;i++){
        if(priority[i]>=8)return -1;
        next[i]=heads[priority[i]];heads[priority[i]]=(uint8_t)i;
    }
    unsigned n=0;
    for(unsigned p=8;p--;)for(unsigned i=heads[p];i!=255;i=next[i])order[n++]=(uint8_t)i;
    return (int)n;
}
/* PPZ actor priority, distinct from the VDP tile priority bit.
   Source: Level/_Objects and Palmtree Panic/Objects; see SPRITE-ORDER.md.
   Fresh actors start at priority 0 unless initialization sets it. */
static inline int scd_ppz_priority(scd_object_view o){
    switch(o.type){
    case SCD_OBJ_GANDAIR3:return o.subtype==2?4:o.subtype==1?3:2;
    case SCD_OBJ_GA:return 1;
    case SCD_OBJ_TENTOU:return (int8_t)o.subtype>0?2:1;
    case SCD_OBJ_SCENERY:case SCD_OBJ_BIG_RING:return 0;
    case SCD_OBJ_DOOR:case SCD_OBJ_DOOR_V:case SCD_OBJ_FLOAT_BLOCK:
    case SCD_OBJ_RAMP:case SCD_OBJ_WALL:case SCD_OBJ_AMY:
    case SCD_OBJ_EXPLOSION:case SCD_OBJ_FLOWER:return 1;
    case SCD_OBJ_RING:return o.frame>=4 && o.frame<8?1:2;
    case SCD_OBJ_PLATFORM:return 2;
    case SCD_OBJ_LOST_RING:return o.frame>=4 && o.frame<8?1:3;
    case SCD_OBJ_SPIKES:case SCD_OBJ_TIMEPOST:
    case SCD_OBJ_MONITOR_ITEM:case SCD_OBJ_COLLAPSE:case SCD_OBJ_MOSQUI:
    case SCD_OBJ_PATABATA:case SCD_OBJ_TAGATAGA:case SCD_OBJ_SPRINGBOARD:
    case SCD_OBJ_SWING:case SCD_OBJ_AMY_HEART:return 3;
    case SCD_OBJ_DISC:case SCD_OBJ_SPRING:case SCD_OBJ_MOVING_SPRING:
    case SCD_OBJ_BOULDER:case SCD_OBJ_GENERATOR:case SCD_OBJ_PROJECTOR:case SCD_OBJ_MOVIE3:
    case SCD_OBJ_CC_GENERATOR:case SCD_OBJ_ANTON:case SCD_OBJ_GOAL:case SCD_OBJ_SIGN:return 4;
    case SCD_OBJ_TAMABBOH:return o.subtype==1?5:4;
    case SCD_OBJ_CAPSULE:return o.subtype?0:4;
    case SCD_OBJ_ANIMAL:return (o.subtype&128) && !(o.subtype&1)?3:4;
    case SCD_OBJ_FRIEND3:return o.subtype&1?4:o.subtype&128?3:1;
    case SCD_OBJ_RAMP_PLANT:return o.frame?4:0;
    case SCD_OBJ_CHECKPOINT:return o.frame?3:4;
    case SCD_OBJ_LOG_SHADOW:case SCD_OBJ_SONIC_HOLE:return 6;
    /* Zone objects past Palmtree Panic (src/objects_*.inc), from their retail
       sprpri: R4/WALL1.C:120 = 1; R7/WALL7.C:82, R7/WALL73.C:71,
       R5/DAI_RD5.C:191, R8/KONBEA.C:686 and :863, R8/KONBEA83.C:218 and
       R8/PISTON.C:87 = 3. Every type objects.c can spawn and
       scd_objects_views reports needs a case here: -1 makes sprite_draw
       abort, which masks interrupts and freezes the game. */
    case SCD_OBJ_POCKET:case SCD_OBJ_CC_POINTS:return 0;
    case SCD_OBJ_DRUMR3:{static const uint8_t priority[]={5,4,3,2,2,2,3,4,5,6,6,6};return o.flags&16?3:o.frame<12?priority[o.frame]:3;}
    case SCD_OBJ_TOGEBALL:case SCD_OBJ_KAMA_BLADE:case SCD_OBJ_BANPA:case SCD_OBJ_FRIP:case SCD_OBJ_BOBIN:case SCD_OBJ_WALL4:return 1;
    case SCD_OBJ_KAMA:case SCD_OBJ_WALL7:case SCD_OBJ_DAIR5:case SCD_OBJ_KONBEA:case SCD_OBJ_PISTON:case SCD_OBJ_FOR3:case SCD_OBJ_HARIR3:case SCD_OBJ_FRDR3:case SCD_OBJ_TRAPDR3:case SCD_OBJ_GETDAIR3:return 3;
    case SCD_OBJ_EMIE3:return o.subtype?3:1;
    case SCD_OBJ_HARI3X:return 3;
    /* R3/ROLLPLAT.C, LIGHT.C and STOPPER.C act_init: sprpri = 3. */
    case SCD_OBJ_SIKAKE33:return 3;
    case SCD_OBJ_MECASNC3:return o.subtype?3:2;
    /* Tidal Tempest actors (objects_tt_*.inc: tt_view_type, tp_type) and
       zone-local types (136-254) carry the actor's own sprpri in flags bits
       5-7 (src/objects.c scd_objects_views, src/scd_objects.h scd_zone_ops).
       PLAWA (pooled, but drawn by src/water.c, not scd_objects_views),
       MIZUKIRI (PLAYER.C mizuki_set runs in zone 0 only) and KOWASI4 (no R4
       act_tbl entry) are never views: -1. */
    case SCD_OBJ_PLAWA:case SCD_OBJ_MIZUKIRI:case SCD_OBJ_KOWASI4:return -1;
    case SCD_OBJ_SCREW_F:return o.flags>>5;
    default:return scd_zone_local(o.type) || (o.type>=SCD_OBJ_R4_FIRST && o.type<=SCD_OBJ_R4_LAST)?o.flags>>5:-1;
    }
}
#endif
