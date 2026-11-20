/* Quartz Quadrant (R5) actor dispatch: ACT51A.C / ACT53.C act_tbl routines
   ported in objects_qq_{common,enemies,hazards,platforms,story}.inc, reached
   through qq_zone_ops (zone 3, src/scd_objects.h scd_zone_ops).
   Spawns start as the retail loader leaves them (actflg holds only the flip
   bits); an actor is listed in scd_objects_views only on updates it called
   actionsub (pool sink). qq_enemy_scan (COLI5 pcol) is the zone's
   pre-motion scan; qq_contact_type colinos are masked around the boss scan;
   qq_reset runs at stage reset. No enemy hook: the R5 enemies remove
   themselves through SUICIDE.C enemy_suicide, as retail does. */
#include "objects_qq_common.inc"
#include "objects_qq_enemies.inc"
#include "objects_qq_hazards.inc"
#include "objects_qq_platforms.inc"
#include "objects_qq_story.inc"
static int qq_type(unsigned t){
    return t==SCD_OBJ_R5_DENDEN || t==SCD_OBJ_R5_SASORI || t==SCD_OBJ_R5_KEMUSI || t==SCD_OBJ_R5_KUMO || t==SCD_OBJ_R5_IWA5 ||
           t==SCD_OBJ_R5_HARI5F || t==SCD_OBJ_R5_HARIR5 || t==SCD_OBJ_R5_IWA5ROLL || t==SCD_OBJ_R5_KUZURE5 || t==SCD_OBJ_R5_IWA5WAVE ||
           t==SCD_OBJ_R5_BURANKO5 || t==SCD_OBJ_R5_HASIRA5 || t==SCD_OBJ_R5_HASHI5 || t==SCD_OBJ_R5_BELTSW5 || t==SCD_OBJ_R5_SHOOT5 ||
           t==SCD_OBJ_R5_MOVIE5 || t==SCD_OBJ_R5_FRIEND5 || t==SCD_OBJ_R5_ET5 || t==SCD_OBJ_R5_KOWASI5;
}
/* The shared DAI_RD5 port frames out through frameout_s00 in QQ as well. */
static int qq_windowed(unsigned t){return qq_type(t) || t==SCD_OBJ_DAIR5;}
/* GAME.C starts every round with the belts running forward. */
static void qq_reset(void){colrevflag=0;scd_r5_set_colrev(0);}
static int qq_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    switch(pool[i].type){
    case SCD_OBJ_R5_DENDEN:denden_act(o);break;
    case SCD_OBJ_R5_SASORI:sasori_act(o);break;
    case SCD_OBJ_R5_KEMUSI:kemusi_act(o);break;
    case SCD_OBJ_R5_KUMO:kumo_act(o);break;
    case SCD_OBJ_R5_IWA5:iwa5_act(o);break;
    case SCD_OBJ_R5_HARI5F:hari5f_act(o);break;
    case SCD_OBJ_R5_HARIR5:harir5_act(o);break;
    case SCD_OBJ_R5_IWA5ROLL:iwa5roll_act(o);break;
    case SCD_OBJ_R5_KUZURE5:kuzure5_act(o);break;
    case SCD_OBJ_R5_IWA5WAVE:iwa5wave_act(o);break;
    case SCD_OBJ_R5_BURANKO5:buranko5_act(o);break;
    case SCD_OBJ_R5_HASIRA5:hasira5_act(o);break;
    case SCD_OBJ_R5_HASHI5:hashi5_act(o);break;
    case SCD_OBJ_R5_BELTSW5:beltsw5_act(o);break;
    case SCD_OBJ_R5_SHOOT5:shoot5_act(o);break;
    case SCD_OBJ_R5_MOVIE5:movie5_act(o);break;
    case SCD_OBJ_R5_FRIEND5:friend5_act(o);break;
    case SCD_OBJ_R5_ET5:et5_act(o);break;
    case SCD_OBJ_R5_KOWASI5:kowasi5_act(o);break;
    default:return 0;
    }
    return 1;
}
static int qq_reject(unsigned type,unsigned sub){(void)sub;return !qq_type(type);}
static void qq_init(unsigned i){sprite_status *o=&actwk[i+1];o->actflg=pool[i].flags;o->sprhsize=o->sprvsize=0;}
static void qq_zone_step(unsigned i){pool[i].sink=0;qq_step(i);}
/* The view subtype names the original pattern table (ZAR3 kind
   type|subtype<<8, tools/zone_object_source.py R5_CHILDREN): the pool
   subtype except sasori's tail (254) and shot (253), which keep the body's,
   and the projector's Ricky (2, pat_friend2) versus a placed one (1). */
static int qq_view(unsigned i,scd_object_view *v){
    const sprite_status *o=&actwk[i+1];
    if(!pool[i].sink || pool[i].type==SCD_OBJ_R5_SHOOT5)return 0;
    if(pool[i].type==SCD_OBJ_R5_SASORI && o->userflag.b.l)v->subtype=o->userflag.b.l&128?253:254;
    if(pool[i].type==SCD_OBJ_R5_FRIEND5)v->subtype=!(o->userflag.b.h&127)?0:(o->userflag.b.h&128)?2:1;
    v->flags=(uint8_t)((o->actflg&3)|((o->sprpri&7)<<5));
    return 1;
}
static const scd_zone_ops qq_zone_ops={.reject=qq_reject,.init=qq_init,.step=qq_zone_step,.view=qq_view,
    .contact=qq_contact_type,.scan=qq_enemy_scan,.reset=qq_reset,
    /* R5 actors frame out through FRAMEOUT_S (ACTSET.C frameout_s). */
    .stream_windowed=qq_windowed};
