/* Zone-local actor hooks (src/scd_objects.h scd_zone_ops), indexed by zone:
   0 PPZ, 1 CC, 2 TT, 3 QQ, 4 WW, 5 SS, 6 MM. PPZ/CC/TT use global ids only
   and keep their direct dispatch. Included after every zone actor file, so a
   zone's ops can use the pool and the TT helpers. A zone port includes its
   actor files here and adds its table, e.g.
       #include "objects_qq.inc"          (defines qq_zone_ops)
       [3]=&qq_zone_ops,
   A zone without a table spawns none of its zone-local placements. */
#include "objects_qq.inc"
#include "objects_ww.inc"
#include "objects_ss.inc"
#include "objects_mm.inc"
/* Collision Chaos (zone 1) uses global ids; its actor code runs from the R3 overlay
   (src/zone_r3_names.h), so objects.c reaches it only through this table. */
static void cc_actor(unsigned i){
    switch(pool[i].type){
    case SCD_OBJ_FOR3:for3_step(i);break;
    case SCD_OBJ_HARIR3:harir3_step(i);break;
    case SCD_OBJ_FRDR3:frdr3_step(i);break;
    case SCD_OBJ_TRAPDR3:trapdr3_step(i);break;
    case SCD_OBJ_GETDAIR3:getdair3_step(i);break;
    case SCD_OBJ_GANDAIR3:gandair3_step(i);break;
    case SCD_OBJ_GA:ga_step(i);break;
    case SCD_OBJ_TENTOU:tentou_step(i);break;
    case SCD_OBJ_KAMA:kama_step(i);break;
    case SCD_OBJ_KAMA_BLADE:kama_blade_step(i);break;
    case SCD_OBJ_BANPA:banpa_step(i);break;
    case SCD_OBJ_TOGEBALL:togeball_step(i);break;
    case SCD_OBJ_POCKET:pocket_step(i);break;
    case SCD_OBJ_CC_POINTS:cc_points_step(i);break;
    case SCD_OBJ_CC_GENERATOR:cc_generator_step(i);break;
    case SCD_OBJ_DRUMR3:drum_step(i);break;
    case SCD_OBJ_EMIE3:emie3_step(i);break;
    case SCD_OBJ_HARI3X:hari3x_step(i);break;
    case SCD_OBJ_MECASNC3:mecasnc3_step(i);break;
    case SCD_OBJ_SIKAKE33:sikake33_step(i);break;
    }
}
/* COLI3 scans before object motion and stops at the first enemy contact. */
static void cc_scan(void){
    for(unsigned i=0;i<SCD_OBJECT_CAPACITY;i++){
        if(pool[i].type==SCD_OBJ_HARIR3){if(harir3_touch(i))break;continue;}
        if(((pool[i].type>=SCD_OBJ_GA && pool[i].type<=SCD_OBJ_TOGEBALL) || pool[i].type==SCD_OBJ_CC_GENERATOR || pool[i].type==SCD_OBJ_HARI3X) && cc_enemy_contact(i))break;
    }
}
static const scd_zone_ops r3_zone_ops={.actor=cc_actor,.scan=cc_scan};
/* Tidal Tempest (zone 2) uses global ids; its actor code runs from the R4 overlay
   (src/zone_r4_names.h), so objects.c reaches it only through this table. */
static void tt_actor(unsigned i){
    slot *s=&pool[i];
    switch(s->type){
    case SCD_OBJ_SCREW_F:screw_f_step(i);break;
    case SCD_OBJ_TONBO:tonbo_step(i);break;
    case SCD_OBJ_YAGO:yago_step(i);break;
    case SCD_OBJ_AMENBO:amenbo_step(i);break;
    case SCD_OBJ_TAGAMEB:tagameb_step(i);break;
    case SCD_OBJ_HARIR4:harir4_step(i);break;
    case SCD_OBJ_HARID4:harid4_step(i);break;
    case SCD_OBJ_SCREW:screw_step(i);break;
    case SCD_OBJ_OSUMIZU:osumizu_step(i);break;
    case SCD_OBJ_FUNSUI4:funsui4_step(i);break;
    case SCD_OBJ_UKIDAI:ukidai_step(i);break;
    case SCD_OBJ_BOU:bou_step(i);break;
    case SCD_OBJ_AWA:awa_step(i);break;
    case SCD_OBJ_FRIEND4:friend4_step(i);break;
    case SCD_OBJ_MOVIE4:movie4_step(i);break;
    case SCD_OBJ_ET4:et4_step(i);break;
    case SCD_OBJ_WAVE:s->sink=0;tt_wave_act(&actwk[i+1]);break;
    default:if(tp_type(s->type)){
        /* A spawned child's init reads the userflag its parent stored after
           tp_setactno; its view subtype (the art kind) takes it from there. */
        if(s->origin==65535 && !s->subtype && !actwk[i+1].r_no0)s->subtype=(uint8_t)actwk[i+1].userflag.b.h;
        s->sink=0;tp_step(i);}break;
    }
}
/* R4 actors frame out through FRAMEOUT_S (ACTSET camera window); resident. */
static int tt_stream_windowed(unsigned t){return (t>=SCD_OBJ_R4_FIRST && t<=SCD_OBJ_R4_LAST) || t==SCD_OBJ_SCREW_F;}
static const scd_zone_ops tt_zone_ops={.actor=tt_actor,.scan=tt_enemy_scan,.stream_windowed=tt_stream_windowed};
static const scd_zone_ops *const zone_ops_table[7]={[1]=&r3_zone_ops,[2]=&tt_zone_ops,[3]=&qq_zone_ops,[4]=&ww_zone_ops,[5]=&ss_zone_ops,[6]=&mm_zone_ops};
