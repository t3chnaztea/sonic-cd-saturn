/* Stardust Speedway (R7) actor dispatch: ACT71A.C / ACT73.C act_tbl routines
   ported in objects_ss_{common,act3,chgban,gimmick,enemies,story}.inc, reached through ss_zone_ops (zone
   5, src/scd_objects.h scd_zone_ops). Spawns start as the retail loader
   leaves them (actflg holds only the flip bits); an actor is listed in
   scd_objects_views only on updates it called actionsub (pool sink).
   ss_enemy_scan (COLI7 pcol) is the zone's pre-motion scan. */
#include "objects_ss_common.inc"
#include "objects_ss_act3.inc"
#include "objects_ss_chgban.inc"
#include "objects_ss_gimmick.inc"
#include "objects_ss_enemies.inc"
#include "objects_ss_story.inc"
static int ss_type(unsigned t){
    return t==SCD_OBJ_R7_EMIE7 || t==SCD_OBJ_R7_HEART7 || t==SCD_OBJ_R7_HARI73 || t==SCD_OBJ_R7_WALL73 || t==SCD_OBJ_R7_GAITOU73 ||
           t==SCD_OBJ_R7_CHGBAN || t==SCD_OBJ_R7_SPRING_R || t==SCD_OBJ_R7_GUN7 || t==SCD_OBJ_R7_HIBANA7 ||
           t==SCD_OBJ_R7_SLIGHT7 || t==SCD_OBJ_R7_CHGWALL7 || t==SCD_OBJ_R7_TEKKYU7 || t==SCD_OBJ_R7_TEKKYU7J ||
           t==SCD_OBJ_R7_HOTARU7 || t==SCD_OBJ_R7_KABASIRA || t==SCD_OBJ_R7_KANABUN || t==SCD_OBJ_R7_DANGO7 || t==SCD_OBJ_R7_BRANKO7 ||
           t==SCD_OBJ_R7_FRIEND7 || t==SCD_OBJ_R7_ET7 || t==SCD_OBJ_R7_MOVIE7;
}
/* Actors whose COLI7 collision numbers the native pcol scan owns. */
static int ss_contact_type(unsigned t){return t==SCD_OBJ_R7_EMIE7 || t==SCD_OBJ_R7_TEKKYU7 || t==SCD_OBJ_R7_TEKKYU7J ||
    t==SCD_OBJ_R7_HOTARU7 || t==SCD_OBJ_R7_KABASIRA || t==SCD_OBJ_R7_KANABUN || t==SCD_OBJ_R7_DANGO7 || t==SCD_OBJ_R7_BRANKO7 || t==SCD_OBJ_R7_ET7 || t==SCD_OBJ_R7_MOVIE7;}
static void ss_reset(void){ss_amy_palette_restore=0;sr_prio_sav=0;gametimer.w=0;prio_flag=0;}
/* GAME.C increments the level frame before the action pass. */
static void ss_scan(void){++gametimer.w;ss_enemy_scan();}
static int ss_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    switch(pool[i].type){
    case SCD_OBJ_R7_EMIE7:emie7_act(o);break;
    case SCD_OBJ_R7_HEART7:heart7_act(o);break;
    case SCD_OBJ_R7_HARI73:hari73_act(o);break;
    case SCD_OBJ_R7_WALL73:wall73_act(o);break;
    case SCD_OBJ_R7_GAITOU73:gaitou73_act(o);break;
    case SCD_OBJ_R7_CHGBAN:chgban_act(o);break;
    case SCD_OBJ_R7_SPRING_R:spring_r_act(o);break;
    case SCD_OBJ_R7_GUN7:gun7_act(o);break;
    case SCD_OBJ_R7_HIBANA7:hibana7_act(o);break;
    case SCD_OBJ_R7_SLIGHT7:slight7_act(o);break;
    case SCD_OBJ_R7_CHGWALL7:chgwall7_act(o);break;
    case SCD_OBJ_R7_TEKKYU7:tekkyu7_act(o);break;
    case SCD_OBJ_R7_TEKKYU7J:tekkyu7j_act(o);break;
    case SCD_OBJ_R7_HOTARU7:hotaru7_act(o);break;
    case SCD_OBJ_R7_KABASIRA:kabasira_act(o);break;
    case SCD_OBJ_R7_KANABUN:kanabun_act(o);break;
    case SCD_OBJ_R7_DANGO7:dango7_act(o);break;
    case SCD_OBJ_R7_BRANKO7:branko7_act(o);break;
    case SCD_OBJ_R7_FRIEND7:friend7_act(o);break;
    case SCD_OBJ_R7_ET7:et7_act(o);break;
    case SCD_OBJ_R7_MOVIE7:movie7_act(o);break;
    default:return 0;
    }
    return 1;
}
static int ss_reject(unsigned type,unsigned sub){(void)sub;return !ss_type(type);}
static void ss_init(unsigned i){sprite_status *o=&actwk[i+1];o->actflg=pool[i].flags;o->sprhsize=o->sprvsize=0;}
static void ss_zone_step(unsigned i){pool[i].sink=0;ss_step(i);}
static int ss_view(unsigned i,scd_object_view *v){
    if(!pool[i].sink)return 0;
    const sprite_status *o=&actwk[i+1];unsigned t=pool[i].type,view=0;
    if(t==SCD_OBJ_R7_CHGBAN)view=o->sproffset&0x8000?0:1;
    else if(t==SCD_OBJ_R7_HOTARU7)view=(uint8_t)o->userflag.b.l==254?254:(o->userflag.b.h&1);
    else if(t==SCD_OBJ_R7_KANABUN || t==SCD_OBJ_R7_DANGO7)view=o->userflag.b.h?1:0;
    else if(t==SCD_OBJ_R7_FRIEND7)view=(o->userflag.b.h&127)?1:0;
    else if(t==SCD_OBJ_R7_TEKKYU7J && o->userflag.b.l)view=255;
    else if(t==SCD_OBJ_R7_SLIGHT7)view=o->userflag.b.l&8?1:0;
    else if(t==SCD_OBJ_R7_SPRING_R && (o->r_no0==4 || o->r_no0==6)){
        /* CHGBAN.C spr_r_set: diagonal on even master poses, horizontal
           on odd poses 1/5, vertical on odd poses 3/7. */
        unsigned master=(unsigned)tp_l(o,0);
        unsigned pose=master<=SCD_OBJECT_CAPACITY?actwk[master].patcnt:0;
        view=o->sproffset==1266?3:pose&2?2:1;
    }
    v->subtype=(uint8_t)view;
    v->flags=(uint8_t)((o->actflg&3)|((o->sprpri&7)<<5));
    return 1;
}
static const scd_zone_ops ss_zone_ops={.reject=ss_reject,.init=ss_init,.step=ss_zone_step,.view=ss_view,
    .contact=ss_contact_type,.scan=ss_scan,.reset=ss_reset};
