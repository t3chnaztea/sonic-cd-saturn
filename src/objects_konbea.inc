/* R8/KONBEA.C konbea: the Metallic Madness Act 1 flip and conveyor platforms.
 * Retail id 42: act_tbl[41] is &konbea in R8/ACT81A.C:72, and KONBEA.C:616
 * checks actno 42. Port type SCD_OBJ_KONBEA. Placed in R81A-D only (R83 links
 * its own R8/KONBEA83.C, which this file does not port).
 *
 * The placement subtype (byte b -> userflag.b.h, ACTSET.C:361) picks the
 * routine set at KONBEA.C:611:
 *   0      a_*: one stationary platform. Top-solid (ridechk) for 120 updates,
 *          then a 23-update flip (a_move) with no collision at all.
 *   other  b_* (move_version): five platforms 89 path steps apart on the
 *          446-point loop konbea8tbl around the placement. Top-solid while
 *          at path index 115..343, rolling with no collision at 344..114.
 * R81A-D use subtype 0 (records 7,8,129,130,167,168,170,179,180,233,236-238)
 * and subtype 1 (records 162,183,228,241,261), always with secondary 0.
 *
 * State lives in the actor, as in the retail routine, so this file needs no
 * port slot fields. Retail scratch words map through scd_word_get (actfree
 * byte = word*2-46, little-endian as on the PC):
 *   word 23     parent actwk index                KONBEA.C:614,669,795,845
 *   a: word 24  timer; words 25/26 home x/y        KONBEA.C:656,691-692,701,717
 *   b: words 24/25 home x/y; 28 path index;        KONBEA.C:868-869,947,956
 *      29 roll timer                               KONBEA.C:899,920
 *   actfree[20] set while Sonic rides               KONBEA.C:712-714,891-893
 * A child carries userflag.b.l = 255 (KONBEA.C:671,847). */

/* Defined later in src/objects.c. */
static int top_solid(unsigned i);
static void release_rider(unsigned actor);
static void remove_slot(unsigned i);

/* KONBEA.C:21-468, (x,y) offsets from home, 446 pairs. */
static const int8_t konbea8tbl[892]={
    0,26,-1,25,-2,25,-3,24,-4,24,-5,23,-6,23,-7,22,-8,22,-9,21,-10,21,-11,20,
    -12,20,-13,19,-14,19,-15,18,-16,18,-17,17,-18,17,-19,16,-20,16,-21,15,-22,15,-23,14,
    -24,14,-25,13,-26,13,-27,12,-28,12,-29,11,-30,11,-31,10,-32,10,-33,9,-34,9,-35,8,
    -36,8,-37,7,-38,7,-39,6,-40,6,-41,5,-42,5,-43,4,-44,4,-45,3,-46,3,-47,2,
    -48,2,-49,1,-50,1,-51,0,-52,0,-53,-1,-54,-1,-55,-2,-56,-2,-57,-3,-58,-3,-59,-4,
    -60,-4,-61,-5,-62,-5,-63,-6,-64,-6,-65,-7,-66,-7,-67,-8,-68,-8,-69,-9,-70,-9,-71,-10,
    -72,-10,-73,-11,-74,-11,-75,-12,-76,-12,-77,-13,-78,-13,-79,-14,-80,-14,-81,-15,-82,-15,-83,-16,
    -84,-16,-85,-17,-86,-17,-87,-18,-88,-18,-89,-19,-90,-19,-91,-20,-92,-21,-93,-22,-94,-23,-95,-24,
    -96,-25,-97,-26,-98,-27,-99,-28,-99,-29,-100,-30,-100,-31,-100,-32,-101,-33,-101,-34,-101,-35,-102,-36,
    -102,-37,-102,-38,-102,-39,-102,-40,-102,-41,-102,-42,-102,-43,-102,-44,-102,-45,-101,-46,-101,-47,-101,-48,
    -100,-49,-100,-50,-100,-51,-99,-52,-98,-53,-98,-54,-97,-55,-96,-56,-95,-57,-94,-58,-93,-59,-92,-60,
    -91,-60,-90,-61,-89,-61,-88,-61,-87,-62,-86,-62,-85,-62,-84,-63,-83,-63,-82,-63,-81,-63,-80,-63,
    -79,-63,-78,-63,-77,-63,-76,-63,-75,-63,-74,-63,-73,-63,-72,-62,-71,-62,-70,-62,-69,-61,-68,-61,
    -67,-60,-66,-60,-65,-59,-64,-59,-63,-58,-62,-58,-61,-57,-60,-57,-59,-56,-58,-56,-57,-55,-56,-55,
    -55,-54,-54,-54,-53,-53,-52,-53,-51,-52,-50,-52,-49,-51,-48,-51,-47,-50,-46,-50,-45,-49,-44,-49,
    -43,-48,-42,-48,-41,-47,-40,-47,-39,-46,-38,-46,-37,-45,-36,-45,-35,-44,-34,-44,-33,-43,-32,-43,
    -31,-42,-30,-42,-29,-41,-28,-41,-27,-40,-26,-40,-25,-39,-24,-39,-23,-38,-22,-38,-21,-37,-20,-37,
    -19,-36,-18,-36,-17,-35,-16,-35,-15,-34,-14,-34,-13,-33,-12,-33,-11,-32,-10,-32,-9,-31,-8,-31,
    -7,-30,-6,-30,-5,-29,-4,-29,-3,-28,-2,-28,-1,-27,0,-26,1,-25,2,-25,3,-24,4,-24,
    5,-23,6,-23,7,-22,8,-22,9,-21,10,-21,11,-20,12,-20,13,-19,14,-19,15,-18,16,-18,
    17,-17,18,-17,19,-16,20,-16,21,-15,22,-15,23,-14,24,-14,25,-13,26,-13,27,-12,28,-12,
    29,-11,30,-11,31,-10,32,-10,33,-9,34,-9,35,-8,36,-8,37,-7,38,-7,39,-6,40,-6,
    41,-5,42,-5,43,-4,44,-4,45,-3,46,-3,47,-2,48,-2,49,-1,50,-1,51,0,52,0,
    53,1,54,1,55,2,56,2,57,3,58,3,59,4,60,4,61,5,62,5,63,6,64,6,
    65,7,66,7,67,8,68,8,69,9,70,9,71,10,72,10,73,11,74,11,75,12,76,12,
    77,13,78,13,79,14,80,14,81,15,82,15,83,16,84,16,85,17,86,17,87,18,88,18,
    89,19,90,19,91,20,92,21,93,22,94,23,95,24,96,25,97,26,98,27,99,28,99,29,
    100,30,100,31,100,32,101,33,101,34,101,35,102,36,102,37,102,38,102,39,102,40,102,41,
    102,42,102,43,102,44,102,45,101,46,101,47,101,48,100,49,100,50,100,51,99,52,98,53,
    98,54,97,55,96,56,95,57,94,58,93,59,92,60,91,60,90,61,89,61,88,61,87,62,
    86,62,85,62,84,63,83,63,82,63,81,63,80,63,79,63,78,63,77,63,76,63,75,63,
    74,63,73,63,72,62,71,62,70,62,69,61,68,61,67,60,66,60,65,59,64,59,63,58,
    62,58,61,57,60,57,59,56,58,56,57,55,56,55,55,54,54,54,53,53,52,53,51,52,
    50,52,49,51,48,51,47,50,46,50,45,49,44,49,43,48,42,48,41,47,40,47,39,46,
    38,46,37,45,36,45,35,44,34,44,33,43,32,43,31,42,30,42,29,41,28,41,27,40,
    26,40,25,39,24,39,23,38,22,38,21,37,20,37,19,36,18,36,17,35,16,35,15,34,
    14,34,13,33,12,33,11,32,10,32,9,31,8,31,7,30,6,30,5,29,4,29,3,28,
    2,28,1,27
};
/* KONBEA.C:469-474 a_tbl0: first timer, extra segment count, then per segment
   timer, x offset, y offset. a_stop overwrites every timer with 120. */
static const int16_t konbea_a_tbl_00[2]={60,0};
static const int16_t konbea_a_tbl_01[5]={60,1,60,32,0};
static const int16_t *const konbea_a_tbl0[2]={konbea_a_tbl_00,konbea_a_tbl_01};
/* KONBEA.C:475 pchg_00: two updates per pattern, flip ends on pattern 0. */
static const uint8_t konbea_pchg_00[14]={1,1,2,3,4,5,6,1,2,3,4,5,0,255};

/* spawn_from setup: the size every konbea init_sub gives an actor
   (KONBEA.C:686-688 and 863-865). Routine 0 runs the init on the first step. */
static void konbea_spawn(unsigned i){
    sprite_status *o=&actwk[i+1];
    o->r_no0=0;o->sprpri=3;o->sprhs=o->sprhsize=16;o->sprvsize=5;
}
/* PLAYSUB.C:24-82 patchg with pchg[mstno.b.h], which is pchg_00 for the only
   mstno this routine uses (KONBEA.C:476,719). pchg_00 has only codes < 128
   and the 255 loop. */
static void konbea_patchg(sprite_status *o){
    const uint8_t *script=konbea_pchg_00;
    if(o->mstno.b.h!=o->mstno.b.l){o->mstno.b.l=o->mstno.b.h;o->patcnt=o->pattim=0;}
    if((signed char)--o->pattim>=0)return;
    /* PLAYSUB.C:39: the script ends in 255 and starts with 1, so the reload is 1. */
    o->pattim=script[0];
    unsigned pat=script[o->patcnt+1];
    if(pat>=128){o->patcnt=0;pat=script[1];}
    o->patno=pat&31;
    o->actflg=(o->actflg&~3)|(((pat>>5)^o->cddat)&3);
    o->patcnt++;
}
/* KONBEA.C:683-693 a_init_sub. */
static void konbea_a_init_sub(const sprite_status *parent,sprite_status *n){
    n->r_no0=2;n->actflg|=4;n->sprpri=3;n->sprhs=n->sprhsize=16;n->sprvsize=5;
    scd_word_set(n,25,(uint16_t)parent->xposi.w.h);scd_word_set(n,26,(uint16_t)parent->yposi.w.h);
}
/* KONBEA.C:650-677 a_init. Returns 1 when the actor was deleted. */
static int konbea_a_init(unsigned i){
    sprite_status *o=&actwk[i+1];
    unsigned sec=(uint8_t)o->userflag.b.l;
    /* Only a placement with secondary 0 reaches here: KONBEA.C:613 sends any
       non-zero secondary through the child check, whose word 23 is still 0
       and names Sonic, so it frames out. Guard the table read anyway. */
    if(sec>1){remove_slot(i);return 1;}
    const int16_t *t=konbea_a_tbl0[sec];
    scd_word_set(o,24,(uint16_t)*t++);
    konbea_a_init_sub(o,o);
    for(int n=*t++-1;n>=0;n--){
        int c=scd_objects_spawn(SCD_OBJ_KONBEA,o->xposi.w.h,o->yposi.w.h,(uint8_t)o->userflag.b.h,0);
        if(c<0){remove_slot(i);return 1;}
        sprite_status *a=&actwk[c+1];
        scd_word_set(a,23,i+1);
        a->userflag.b.h=o->userflag.b.h;a->userflag.b.l=-1;
        scd_word_set(a,24,(uint16_t)*t++);
        a->xposi.w.h=o->xposi.w.h+*t++;
        a->yposi.w.h=o->yposi.w.h+*t++;
        konbea_a_init_sub(o,a);
    }
    return 0;
}
/* KONBEA.C:860-870 b_init_sub. */
static void konbea_b_init_sub(const sprite_status *parent,sprite_status *n){
    n->r_no0=2;n->actflg|=4;n->sprpri=3;n->sprhs=n->sprhsize=16;n->sprvsize=5;
    scd_word_set(n,24,(uint16_t)parent->xposi.w.h);scd_word_set(n,25,(uint16_t)parent->yposi.w.h);
}
/* KONBEA.C:827-854 b_init: the parent starts at path index 0 and four
   children at 89, 178, 267 and 356. A failed allocation calls frameout_s,
   which only deletes an actor outside the view; the port's stream does that. */
static void konbea_b_init(unsigned i){
    sprite_status *o=&actwk[i+1];
    konbea_b_init_sub(o,o);
    unsigned wk1=89,wk2=89;
    for(int lp=3;lp>=0;lp--){
        int c=scd_objects_spawn(SCD_OBJ_KONBEA,o->xposi.w.h,o->yposi.w.h,(uint8_t)o->userflag.b.h,0);
        if(c<0)return;
        sprite_status *a=&actwk[c+1];
        scd_word_set(a,23,i+1);
        a->userflag.b.h=o->userflag.b.h;a->userflag.b.l=-1;
        a->xposi.w.h=o->xposi.w.h;a->yposi.w.h=o->yposi.w.h;
        scd_word_set(a,28,wk2);wk2+=wk1;
        konbea_b_init_sub(o,a);
    }
}
/* KONBEA.C:942-961 b_move. The PC adds 65536 to the int at actfree[8]; on
   the little-endian PC its high half is word 28, the path index. */
static void konbea_b_move(sprite_status *o){
    int16_t xsav=o->xposi.w.h;
    const int8_t *t=&konbea8tbl[scd_word_get(o,28)*2];
    int16_t x=(int16_t)((int16_t)scd_word_get(o,24)+t[0]),y=(int16_t)((int16_t)scd_word_get(o,25)+t[1]);
    o->xposi.w.h=x;o->yposi.w.h=y;
    o->xspeed.w=(int16_t)((x-xsav)<<8);
    uint32_t cursor=scd_word_get(o,27)|((uint32_t)scd_word_get(o,28)<<16);
    cursor+=65536;
    if(cursor>=29229056u)cursor=0;
    scd_word_set(o,27,cursor&65535);scd_word_set(o,28,cursor>>16);
}
/* KONBEA.C:710-730 a_stop1. */
static void konbea_a_stop1(unsigned i){
    sprite_status *o=&actwk[i+1];
    o->actfree[20]=top_solid(i)?255:0;
    uint16_t timer=(uint16_t)(scd_word_get(o,24)-1);scd_word_set(o,24,timer);
    if(!timer){
        o->sprvsize=16;o->mstno.w=255;o->r_no0+=2;
        if(o->actfree[20])release_rider(i+1);
    }
}
/* KONBEA.C:887-909 b_stop1. */
static void konbea_b_stop1(unsigned i){
    sprite_status *o=&actwk[i+1];
    konbea_b_move(o);
    o->actfree[20]=top_solid(i)?255:0;
    if(scd_word_get(o,28)==344){
        o->r_no0+=2;o->sprvsize=16;scd_word_set(o,29,216);
        if(o->actfree[20])release_rider(i+1);
    }
}
/* KONBEA.C:608-644 konbea and 791-821 move_version. actionsub only draws;
   the parent's frameout_s00 is the port's stream (children, userflag.b.l
   bit 7, never frame out on their own). */
static void konbea_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    unsigned moving=(uint8_t)o->userflag.b.h!=0,home=moving?24:25;
    if(o->userflag.b.l){
        /* KONBEA.C:613-628 / 794-810: a child dies with its parent. */
        unsigned parent=scd_word_get(o,23);
        const sprite_status *m=parent<=SCD_OBJECT_CAPACITY?&actwk[parent]:0;
        if(!m || m->actno!=SCD_OBJ_KONBEA || scd_word_get(o,home)!=scd_word_get(m,home) || scd_word_get(o,home+1)!=scd_word_get(m,home+1)){remove_slot(i);return;}
    }
    if(!moving){
        switch(o->r_no0){
        case 0:konbea_a_init(i);return;
        /* KONBEA.C:699-704 a_stop. */
        case 2:o->sprvsize=5;scd_word_set(o,24,120);o->r_no0+=2;konbea_a_stop1(i);return;
        case 4:konbea_a_stop1(i);return;
        /* KONBEA.C:736-744 a_move. */
        case 6:konbea_patchg(o);if(!o->patno)o->r_no0=2;return;
        default:return;
        }
    }
    switch(o->r_no0){
    case 0:konbea_b_init(i);return;
    /* KONBEA.C:876-880 b_stop. */
    case 2:o->sprvsize=5;o->r_no0+=2;konbea_b_stop1(i);return;
    case 4:konbea_b_stop1(i);return;
    case 6:{
        /* KONBEA.C:915-936 b_roll: patno.patcnt steps by half a pattern and wraps after 5. */
        konbea_b_move(o);
        int16_t timer=(int16_t)(scd_word_get(o,29)-1);scd_word_set(o,29,(uint16_t)timer);
        if(timer<0){o->patno=0;o->r_no0=2;return;}
        uint16_t pattern=(uint16_t)(((unsigned)o->patno<<8)|o->patcnt);
        pattern+=128;
        if((int16_t)pattern>1280)pattern=0;
        o->patno=pattern>>8;o->patcnt=pattern&255;
        return;
    }
    default:return;
    }
}
