/* Wacky Workbench (R6) actor dispatch: Z61ACT.C / Z62ACT.C / Z63ACT.C act_tbl
   routines ported in objects_ww_{common,enemies,...}.inc, reached through
   ww_zone_ops (zone 4, src/scd_objects.h scd_zone_ops). As in objects_qq.inc,
   spawns start as the retail loader leaves them and an actor is listed in
   scd_objects_views only on updates it called actionsub (pool sink).
   ww_enemy_scan (COLI6 pcol) is the zone's pre-motion scan. The R6 enemies
   remove themselves through SUICIDE.C enemy_suicide, as retail does. */
#include "objects_ww_common.inc"
#include "objects_ww_enemies.inc"
#include "objects_ww_gimmicks.inc"
#include "objects_ww_story.inc"
static int ww_type(unsigned t){
    return t==SCD_OBJ_R6_BATTA || t==SCD_OBJ_R6_HACHI6 || t==SCD_OBJ_R6_SEMI || t==SCD_OBJ_R6_MINOMUSI || t==SCD_OBJ_R6_BEEM6 || t==SCD_OBJ_R6_DAIR6 || t==SCD_OBJ_R6_KDAI6 || t==SCD_OBJ_R6_TOBIDAI6 || t==SCD_OBJ_R6_BLOCK6 || t==SCD_OBJ_R6_SEESAW6 || t==SCD_OBJ_R6_PISTON6 || t==SCD_OBJ_R6_SW6 || t==SCD_OBJ_R6_TOBIRA6 || t==SCD_OBJ_R6_UDBLK6 || t==SCD_OBJ_R6_OPTBR6 || t==SCD_OBJ_R6_EGGZ6 ||
           t==SCD_OBJ_R6_MEGAMI || t==SCD_OBJ_R6_GAS || t==SCD_OBJ_R6_CATAPALT || t==SCD_OBJ_R6_SHOOT6 || t==SCD_OBJ_R6_TOGEBALL6 ||
           t==SCD_OBJ_R6_ET6 || t==SCD_OBJ_R6_MOVIE6 || t==SCD_OBJ_R6_FRIEND6;
}
/* COLI6 pcol tests every visible actor with a collision number. */
static int ww_contact_type(unsigned t){return ww_type(t);}
static void ww_reset(void){memset(ww_colorwk,0,sizeof(ww_colorwk));ww_colorset[0]=ww_colorset[1]=0;st6clrchg=0;}
static int ww_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    switch(pool[i].type){
    case SCD_OBJ_R6_BATTA:batta_act(o);break;
    case SCD_OBJ_R6_HACHI6:hachi6_act(o);break;
    case SCD_OBJ_R6_SEMI:semi_act(o);break;
    case SCD_OBJ_R6_MINOMUSI:minomusi_act(o);break;
    case SCD_OBJ_R6_BEEM6:beem6_act(o);break;
    case SCD_OBJ_R6_DAIR6:dair6_act(o);break;
    case SCD_OBJ_R6_KDAI6:kdai6_act(o);break;
    case SCD_OBJ_R6_TOBIDAI6:tobidai6_act(o);break;
    case SCD_OBJ_R6_BLOCK6:block6_act(o);break;
    case SCD_OBJ_R6_SEESAW6:seesaw6_act(o);break;
    case SCD_OBJ_R6_PISTON6:piston6_act(o);break;
    case SCD_OBJ_R6_SW6:sw6_act(o);break;
    case SCD_OBJ_R6_TOBIRA6:tobira6_act(o);break;
    case SCD_OBJ_R6_UDBLK6:udblk6_act(o);break;
    case SCD_OBJ_R6_OPTBR6:optbr6_act(o);break;
    case SCD_OBJ_R6_EGGZ6:eggz6_act(o);break;
    case SCD_OBJ_R6_MEGAMI:megami_act(o);break;
    case SCD_OBJ_R6_GAS:gas_act(o);break;
    case SCD_OBJ_R6_CATAPALT:catapalt_act(o);break;
    case SCD_OBJ_R6_SHOOT6:shoot6_act(o);break;
    case SCD_OBJ_R6_TOGEBALL6:togeball6_act(o);break;
    case SCD_OBJ_R6_ET6:et6_act(o);break;
    case SCD_OBJ_R6_MOVIE6:movie6_act(o);break;
    case SCD_OBJ_R6_FRIEND6:friend6_act(o);break;
    default:return 0;
    }
    return 1;
}
/* Level/Main.asm resets levelFrames at level setup. Every act's object and
   palette scripts start at zero; stage tiles advance separately during
   title-card draws. ObjPlatform_GetOffset reads this frame counter. */
unsigned scd_objects_ww_title_phase(unsigned act,unsigned era){
    if(objects_zone!=4 || act>=3 || era>=4)return 0;
    gametimer.w=0;return 0;
}
/* GAME.C game(): ++gametimer before the action pass (the player then the
   objects); DAIR6/KDAI6 and PLAYER6 read it. src/water.c does the same for TT. */
static void ww_scan(void){++gametimer.w;ww_enemy_scan();}
static int ww_reject(unsigned type,unsigned sub){(void)sub;return !ww_type(type);}
static void ww_init(unsigned i){sprite_status *o=&actwk[i+1];o->actflg=pool[i].flags;o->sprhsize=o->sprvsize=0;}
/* Seesaw plates are drawn only by their seesaw's actionsub calls. */
static void ww_zone_step(unsigned i){if(!(pool[i].type==SCD_OBJ_R6_SEESAW6 && actwk[i+1].userflag.b.h))pool[i].sink=0;ww_step(i);}
static int ww_view(unsigned i,scd_object_view *v){
    if(!pool[i].sink)return 0;
    v->flags=(uint8_t)((actwk[i+1].actflg&3)|((actwk[i+1].sprpri&7)<<5));
    /* Art view for the ZART6 tables (keyed type|view<<8, plain type as the
       fallback): the enemies' e/b tables and FRIEND6 by subtype, children
       with their own table (hachi6
       tama, egg6 bomb, togeball orbit balls: userflag.b.h -1) 255, the
       semi bomb (userflag.b.l -1) 254; every other actor its plain type. */
    const sprite_status *o=&actwk[i+1];unsigned t=pool[i].type,sub=pool[i].subtype&127,view=0;
    if((t==SCD_OBJ_R6_HACHI6 || t==SCD_OBJ_R6_EGGZ6 || t==SCD_OBJ_R6_TOGEBALL6) && (uint8_t)o->userflag.b.h==255)view=255;
    else if(t==SCD_OBJ_R6_SEMI && (uint8_t)o->userflag.b.l==255)view=254;
    /* BATTA/HACHI6/SEMI/MINOMUSI.C take pat_*_b whenever userflag.b.h != 0
       (a projector's 128 included); FRIEND6 drops bit 7. */
    else if(t==SCD_OBJ_R6_MINOMUSI){
        /* Minomusi's silk and spikes inherit oMap from their parent without
           copying oSubtype (scddisasm Minomusi/Main.asm SpawnSilk/Attack). */
        const sprite_status *mapped=o;
        if(o->userflag.b.l){unsigned parent=(uint16_t)qq_w(o,30);
            if(parent<=SCD_OBJECT_CAPACITY && actwk[parent].actno==t)mapped=&actwk[parent];}
        view=mapped->userflag.b.h?1:0;
    }
    else if(t==SCD_OBJ_R6_BATTA || t==SCD_OBJ_R6_HACHI6 || t==SCD_OBJ_R6_SEMI)view=o->userflag.b.h?1:0;
    else if(t==SCD_OBJ_R6_FRIEND6)view=sub?1:0;
    v->subtype=(uint8_t)view;
    return 1;
}
static const scd_zone_ops ww_zone_ops={.reject=ww_reject,.init=ww_init,.step=ww_zone_step,.view=ww_view,
    .contact=ww_contact_type,.scan=ww_scan,.reset=ww_reset,
    /* R6 actors frame out through FRAMEOUT_S (ACTSET.C frameout_s). */
    .stream_windowed=ww_type};
