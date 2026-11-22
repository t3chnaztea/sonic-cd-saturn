/* Metallic Madness (R8) actor dispatch: ACT81A.C / ACT82A.C / ACT83.C
   act_tbl routines ported in objects_mm_{common,act1,act1b,story,trap,act2,act3,hota8,enemies}.inc, reached through
   mm_zone_ops (zone 6, src/scd_objects.h scd_zone_ops). Spawns start as the
   retail loader leaves them (actflg holds only the flip bits); an actor is
   listed in scd_objects_views only on updates it called actionsub (pool
   sink). mm_enemy_scan (COLI8 pcol) is the zone's pre-motion scan. */
#include "objects_mm_common.inc"
#include "objects_mm_act1.inc"
#include "objects_mm_act1b.inc"
#include "objects_mm_story.inc"
#include "objects_mm_trap.inc"
#include "objects_mm_act2.inc"
#include "objects_mm_act3.inc"
#include "objects_mm_hota8.inc"
#include "objects_mm_enemies.inc"
#include "objects_mm_remaining.inc"
static int mm_type(unsigned t){
    return t==SCD_OBJ_R8_SCARAB || t==SCD_OBJ_R8_BIGBOM || t==SCD_OBJ_R8_GATER8 || t==SCD_OBJ_R8_ANAR8 || t==SCD_OBJ_R8_DAI8 || t==SCD_OBJ_R8_NOKOGIRI || t==SCD_OBJ_R8_KUZURE8 || t==SCD_OBJ_R8_PROPERA || t==SCD_OBJ_R8_KABUTO ||
           t==SCD_OBJ_R8_HACHI8 || t==SCD_OBJ_R8_OKUSIESO || t==SCD_OBJ_R8_HAGURUMA || t==SCD_OBJ_R8_FRIEND8 || t==SCD_OBJ_R8_ET8 ||
           t==SCD_OBJ_R8_TOGEDAIR8 || t==SCD_OBJ_R8_KOMA8 || t==SCD_OBJ_R8_FUTAGOR8 || t==SCD_OBJ_R8_TOGEITA || t==SCD_OBJ_R8_SPRING8 ||
           t==SCD_OBJ_R8_SW8 || t==SCD_OBJ_R8_TOBIRA || t==SCD_OBJ_R8_PIPE8 || t==SCD_OBJ_R8_SHOOTER || t==SCD_OBJ_R8_SHUT || t==SCD_OBJ_R8_KAITEN ||
           t==SCD_OBJ_R8_BEAM || t==SCD_OBJ_R8_CHIBI_COLI || t==SCD_OBJ_R8_JETTOGE || t==SCD_OBJ_R8_KONBEA83 || t==SCD_OBJ_R8_HOTARU8 || t==SCD_OBJ_R8_DANGO8 || t==SCD_OBJ_R8_LEGMECA;
}
/* Actors whose COLI8 collision numbers the native pcol scan owns. */
static int mm_contact_type(unsigned t){return t==SCD_OBJ_R8_SCARAB || t==SCD_OBJ_R8_BIGBOM || t==SCD_OBJ_R8_NOKOGIRI || t==SCD_OBJ_R8_PROPERA || t==SCD_OBJ_R8_KABUTO ||
    t==SCD_OBJ_R8_HACHI8 || t==SCD_OBJ_R8_OKUSIESO || t==SCD_OBJ_R8_ET8 ||
    t==SCD_OBJ_R8_TOGEDAIR8 || t==SCD_OBJ_R8_TOGEITA || t==SCD_OBJ_R8_JETTOGE || t==SCD_OBJ_R8_HOTARU8 || t==SCD_OBJ_R8_DANGO8;}
/* GAME.C clears these at every stage start (HOTA8C/D.C sets shut_flag, BEAM.C
   toggles chibi_flag, COLI8.C pcolitem reads prio_flag). */
extern unsigned char chibi_flag;
static void mm_reset(void){memset(mm_drawn_by_other,0,sizeof(mm_drawn_by_other));memset(mm_room_palette,0,sizeof(mm_room_palette));mm_room_palette_dirty=0;
    shut_flag=0;chibi_flag=0;prio_flag=0;gametimer.w=0;} /* GAME.C:738 */
static int mm_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    switch(pool[i].type){
    case SCD_OBJ_R8_SCARAB:mm_sc_scarab(o);break;
    case SCD_OBJ_R8_BIGBOM:mm_bb_bigbom(o);break;
    case SCD_OBJ_R8_GATER8:mm_gater8(o);break;
    case SCD_OBJ_R8_ANAR8:mm_an_anar8(o);break;
    case SCD_OBJ_R8_DAI8:dai8_act(o);break;
    case SCD_OBJ_R8_NOKOGIRI:nokogiri_act(o);break;
    case SCD_OBJ_R8_KUZURE8:kuzure8_act(o);break;
    case SCD_OBJ_R8_PROPERA:propera_act(o);break;
    case SCD_OBJ_R8_KABUTO:kabuto_act(o);break;
    case SCD_OBJ_R8_HACHI8:hachi8_act(o);break;
    case SCD_OBJ_R8_OKUSIESO:okusieso_act(o);break;
    case SCD_OBJ_R8_HAGURUMA:haguruma_act(o);break;
    case SCD_OBJ_R8_FRIEND8:friend8_act(o);break;
    case SCD_OBJ_R8_ET8:et8_act(o);break;
    case SCD_OBJ_R8_TOGEDAIR8:togedair8_act(o);break;
    case SCD_OBJ_R8_KOMA8:koma8_act(o);break;
    case SCD_OBJ_R8_FUTAGOR8:futagor8_act(o);break;
    case SCD_OBJ_R8_TOGEITA:togeita_act(o);break;
    case SCD_OBJ_R8_SPRING8:spring8_act(o);break;
    case SCD_OBJ_R8_SW8:sw8_act(o);break;
    case SCD_OBJ_R8_TOBIRA:tobira_act(o);break;
    case SCD_OBJ_R8_PIPE8:pipe8_act(o);break;
    case SCD_OBJ_R8_SHOOTER:shooter_act(o);break;
    case SCD_OBJ_R8_SHUT:shut_act(o);break;
    case SCD_OBJ_R8_KAITEN:kaiten_act(o);break;
    case SCD_OBJ_R8_BEAM:beam_act(o);break;
    case SCD_OBJ_R8_CHIBI_COLI:chibi_coli_act(o);break;
    case SCD_OBJ_R8_JETTOGE:jettoge_act(o);break;
    case SCD_OBJ_R8_KONBEA83:konbea83_act(o);break;
    case SCD_OBJ_R8_HOTARU8:hota8_act(o);break;
    case SCD_OBJ_R8_DANGO8:dango8_act(o);break;
    case SCD_OBJ_R8_LEGMECA:legmeca_act(o);break;
    default:return 0;
    }
    return 1;
}
static int mm_reject(unsigned type,unsigned sub){(void)sub;return !mm_type(type);}
static void mm_init(unsigned i){sprite_status *o=&actwk[i+1];o->actflg=pool[i].flags;o->sprhsize=o->sprvsize=0;}
/* An actor another one drew earlier in this update (mm_draw_other) keeps
   that draw through its own update. */
static void mm_zone_step(unsigned i){
    if(mm_drawn_by_other[i])mm_drawn_by_other[i]=0;else pool[i].sink=0;
    mm_step(i);
}
/* The pattern table the original initializer picks (art kind type|view<<8,
   tools/zone_object_source.py r8_specs): R8 sources choose it from the
   userflag bytes, which the native actors keep. */
static unsigned mm_view_table(unsigned t,const sprite_status *o){
    unsigned h=(uint8_t)o->userflag.b.h,l=(uint8_t)o->userflag.b.l;
    switch(t){
    case SCD_OBJ_R8_TOGEDAIR8:return h==248?2:h>=128?1:0; /* TRAP_R8x: tokusyu, harir8, togedair8 */
    case SCD_OBJ_R8_NOKOGIRI:return l==255;               /* NOKOGIRI.C bar */
    case SCD_OBJ_R8_PROPERA:return h!=0;                  /* PROPERA8.C propera1 */
    case SCD_OBJ_R8_KABUTO:return l>=128;                 /* KABUTO8.C kabuto1 (tuno) */
    case SCD_OBJ_R8_SCARAB:return h==2;                   /* SCARAB.C itempat */
    case SCD_OBJ_R8_HACHI8:return h!=0;                   /* HACHI8.C pat_hachi8_b */
    case SCD_OBJ_R8_FRIEND8:return (h&127)!=0;            /* FRIEND8.C sheep: pat_friend1 */
    case SCD_OBJ_R8_TOBIRA:{                              /* TOBIRA.C pat_tobira0-2; m_init's */
        unsigned m=(uint16_t)mm_w(o,23)&127;              /* second half copies its master's  */
        if(m)h=(uint8_t)actwk[m].userflag.b.h;            /* table (PC word 23 links them).   */
        return h<=2?h:0;
    }
    case SCD_OBJ_R8_DANGO8:return h!=0;                   /* DANGO8.C pat_dango_b */
    case SCD_OBJ_R8_BIGBOM:return h/2;                    /* BIGBOM8.C bigbom1-4: pat_bigbom, pat1-3 */
    /* SPRING.C spring (retail actor 10): spring/90/45 by bits 2-3, colour by bit 1. */
    case SCD_OBJ_R8_SPRING8:return (h&2?1:0)|(h&4?2:h&8?4:0);
    default:return 0;
    }
}
static int mm_view(unsigned i,scd_object_view *v){
    if(!pool[i].sink)return 0;
    v->subtype=(uint8_t)mm_view_table(pool[i].type,&actwk[i+1]);
    v->flags=(uint8_t)((actwk[i+1].actflg&3)|((actwk[i+1].sprpri&7)<<5));
    return 1;
}
static void mm_konbea(unsigned i,int spawn){if(spawn)konbea_spawn(i);else konbea_step(i);}
/* RING.C flyringinit (R8 overlay): the spill timer, then the other rings,
   each in the lowest free slot at this point of the object pass (actwkchk);
   the retail slot is claimed at the call. */
static void mm_ring_spill(unsigned i){
    sprite_status *o=&actwk[i+1];
    mm_spill_timer=255;pool[i].phase=0;
    for(unsigned n=1,first=0;n<mm_spill_rings;n++){
        int index=spawn_lost_ring(o->xposi.w.h,o->yposi.w.h,first);
        if(index<0)break;
        first=(unsigned)index+1;lost_ring_velocity(&actwk[index+1],n);stats.lost++;
        actwk[index+1].userflag.b.l=o->userflag.b.l; /* RING.C:406 */
        /* One full sync, then only the new ring has changed: up to 31 full
           walks made the spill update late (MM2 campaign update 12347). */
        if(n==1)scd_boss_slot_sync();else scd_boss_slot_sync_one((unsigned)index+1);
    }
    mm_spill_rings=0;
}
static const scd_zone_ops mm_zone_ops={.reject=mm_reject,.init=mm_init,.step=mm_zone_step,.view=mm_view,
    .contact=mm_contact_type,.scan=mm_enemy_scan,.reset=mm_reset,.konbea=mm_konbea,.ring_spill=mm_ring_spill};
