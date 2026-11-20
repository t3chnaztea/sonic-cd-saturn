/* Static sized solids: Tidal Tempest wall1 and Stardust Speedway wall7 / wall73.
 * Included by objects.c beside its other .inc files. That point comes before
 * slot, pool and the solidity helpers are defined, so this file keeps all of
 * its state in the actor record actwk[i+1] and forward-declares the two
 * objects.c routines it calls.
 *
 *   SCD_OBJ_WALL4  R4/WALL1.C   wall1   retail R4 id 52 (every R4 act_tbl).
 *   SCD_OBJ_WALL7  R7/WALL7.C   wall7   retail R7 id 36 (ACT71A.C:63, ACT73.C:62).
 *                  R7/WALL73.C  wall73  retail R7 Act 3 id 43 (ACT73.C:69), selected
 *                                        by subtype bit 7 (WALLS_WALL73). Its own size
 *                                        table and a scripted boss move.
 *
 * All three are one shape. The first call copies patno from the subtype and the
 * half sizes from a table (WALL1.C:117-125, WALL7.C:78-89, WALL73.C:67-78); every
 * call then runs hitchk(pActwk,&actwk[0]) (WALL1.C:135, WALL7.C:92, WALL73.C:84).
 * hitchk (RIDECHK.C:243-288) against an actor with zero speed is what
 * static_solid() implements: width sprhsize+10 (RIDECHK.C:261), height
 * sprvsize+player sprvsize+2 (RIDECHK.C:317), the smaller penetration picks
 * the side (RIDECHK.C:350), side contact needs 5px of vertical overlap
 * (RIDECHK.C:380), top contact only when not rising (RIDECHK.C:486-488).
 *
 * The first call happens in the same frame as the spawn, from the step loop, as
 * in retail, where act_init runs on the first dispatch and falls through to
 * act_move (WALL1.C:127). Until then the actor keeps spawn_from's defaults. */
#define WALLS_WALL73 128
/* Defined further down objects.c. */
static int static_solid(unsigned i);
static void remove_slot(unsigned i);

/* R4/WALL1.C:67-75 tbl0, sprhsize then sprvsize, for patno = subtype 0..6. */
static const uint8_t walls_wall1_size[7][2]={{16,16},{16,16},{32,16},{16,32},{32,32},{64,16},{16,64}};
/* R7/WALL7.C:69-76 wall7_tbl0, subtypes 0..5. */
static const uint8_t walls_wall7_size[6][2]={{12,17},{28,17},{44,17},{60,17},{12,33},{12,49}};
/* R7/WALL73.C:9-16 wall7_tbl0. A different table from WALL7.C's; WALL73.C
   shares only the pattern array (WALL73.C:17 extern pat_wall7). */
static const uint8_t walls_wall73_size[6][2]={{11,16},{32,16},{48,16},{64,16},{11,32},{11,48}};

/* Called once from spawn_from before a slot is taken. Retail indexes its table
   with the raw subtype and never checks it; every retail record stays inside
   (R4 wall1 uses 0..6, R7 wall7 and wall73 use 0..5, all 70 programs checked).
   Reject anything else rather than read past the table. */
static int walls_reject(unsigned type,unsigned sub){
    if(type==SCD_OBJ_WALL4)return sub>6;
    if(type==SCD_OBJ_WALL7)return (sub&~WALLS_WALL73)>5;
    return 0;
}
static const uint8_t *walls_size(unsigned type,unsigned sub,unsigned patno){
    if(type==SCD_OBJ_WALL4)return walls_wall1_size[patno];
    return (sub&WALLS_WALL73)?walls_wall73_size[patno]:walls_wall7_size[patno];
}
/* R7/WALL73.C:97-166 move_blk. Runs only while the Act 3 boss holds bossflag
   bit 7 (set by R7/BOSS_7.C:862, 942 and 963, which the port does not have yet)
   and only for a record with a secondary byte: two of the 56 wall73 records, and
   neither is the one that fills the hole at x=12224. The target Y lives in the
   retail word 23 ((short*)pActwk)[23]. Returns -1 once the actor is gone. */
static int walls_move_blk(unsigned i){
    sprite_status *o=&actwk[i+1];
    if(!(bossflag&128))return 0;                                     /* :101 */
    if(!(int16_t)scd_word_get(o,23)){                                /* :103 */
        int d0=32,d1=512;                                            /* :105-106 */
        if((uint8_t)o->userflag.b.l&128){d0=-d0;d1=-d1;}             /* :107-110 */
        o->yspeed.w=d1;                                              /* :112 */
        scd_word_set(o,23,(uint16_t)(o->yposi.w.h+d0));              /* :113 */
    }
    o->yposi.l+=(int)o->yspeed.w*256;                                /* :116 */
    if((int16_t)scd_word_get(o,23)!=o->yposi.w.h)return 0;           /* :118-120 */
    scd_word_set(o,23,0);                                            /* :121 */
    int8_t step=(int8_t)(((uint8_t)o->userflag.b.l&15)-1);           /* :124 */
    if(!step){
        bossflag&=127;                                               /* :127 */
        if((uint8_t)o->userflag.b.l&64){o->userflag.b.l=0;return 0;} /* :128-132 */
        remove_slot(i);return -1;                                    /* :135-136 frameout */
    }
    o->userflag.b.l=(char)(uint8_t)(((uint8_t)o->userflag.b.l&0xF0)+step); /* :141-142 */
    if((uint8_t)o->userflag.b.l&32)return 0;                         /* :143-144 */
    if((uint8_t)o->userflag.b.l&16){                                 /* :145-150 */
        if(++o->patno==1)o->patno=4;
        o->yposi.w.h-=16;
    }else{                                                           /* :153-157 */
        if(--o->patno==3)o->patno=0;
        o->yposi.w.h+=16;
    }
    const uint8_t *size=walls_wall73_size[o->patno];                 /* :160-162 */
    o->sprhs=o->sprhsize=size[0];o->sprvsize=size[1];
    return 0;
}
static void walls_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    unsigned type=o->actno,sub=(uint8_t)o->userflag.b.h,patno=sub&~WALLS_WALL73;
    if(!o->r_no0){
        o->r_no0+=2;o->actflg|=4;
        /* sprpri: WALL1.C:120 = 1, WALL7.C:82 and WALL73.C:71 = 3. */
        o->sprpri=type==SCD_OBJ_WALL4?1:3;
        o->patno=patno;
        const uint8_t *size=walls_size(type,sub,patno);
        o->sprhs=o->sprhsize=size[0];o->sprvsize=size[1];
    }
    /* WALL73.C:81-83. The colino clear at WALL73.C:84-85 has no port
       counterpart: static_solid() keeps no colino crush record. */
    if(type==SCD_OBJ_WALL7 && (sub&WALLS_WALL73) && o->userflag.b.l && walls_move_blk(i))return;
    static_solid(i);
}
