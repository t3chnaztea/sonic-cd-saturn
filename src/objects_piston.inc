/* Metallic Madness piston: retail R8 act_tbl id 52 (R8/ACT82A.C:86 &piston,
 * the 52nd entry of act_tbl[67]; ACTSET.C actnoset stores record byte a as
 * actno and byte b as userflag.b.h). Ported from R8/PISTON.C.
 *
 * The retail work words live in the same places here: ((short*)wk)[26] is the
 * base Y, [27] the angle 0..1023, [28] the angle step, [29] the radius
 * (PISTON.C:88,97,100,118,131), read through scd_word_get/scd_word_set.
 * actfree[14] is the hold time, actfree[16] the hold counter and actfree[20]
 * bit 7 the holding flag (PISTON.C:133,135,153-164).
 *
 * Subtype bits (userflag.b.h), PISTON.C:94-133:
 *   bits 0-1  act_tbl index: 0 or 2 = init_piston0 (plain oscillating block),
 *             1 = init_piston1 (tall launcher with holds). Retail act_tbl has
 *             three entries, so 3 indexes past it; no R8 record uses 3 and this
 *             port treats it as init_piston0.
 *   bits 2-3  piston0 speed spd_tbl[(b&12)/4]; piston1 speed spd_tbl[(b&4)/4]
 *             and hold time delay_time_tbl[(b&8)/8].
 *   bits 4-5  start angle rad_tbl[(b&48)>>4].
 *   bit  6    radius radius_tbl[(b&64)>>6].
 *   bit  7    launcher speed jump_tbl[(b&128)>>7].
 *
 * Solidity: retail calls ride_on_chk (RIDECHK.C:237, = hitchk with r_no1 0,
 * i.e. hit_v). static_solid in objects.c is the port's translation of hit_v;
 * the part it leaves out is hit_yu1's crush (RIDECHK.C:587-593), added in
 * piston_ride. Rendering (actionsub) and off-screen deletion (frameout_s,
 * PISTON.C:64-65) are the port's scheduler and stream(), not ported here. */
static int static_solid(unsigned i);
extern short playdieset(sprite_status *);

/* PISTON.C:113 spd_tbl. */
static const short piston_spd_tbl[4]={4,8,16,32};

/* PISTON.C:70-136 piston_init, init_piston0, init_piston1. */
static void piston_spawn(sprite_status *o){
    static const short rad_tbl[4]={0,256,512,768};      /* PISTON.C:79 */
    static const short radius_tbl[2]={32,48};           /* PISTON.C:81 */
    static const uint8_t delay_time_tbl[2]={60,90};     /* PISTON.C:126 */
    unsigned sub=(uint8_t)o->userflag.b.h;
    o->actflg|=4;                                       /* PISTON.C:84 */
    o->sprpri=3;                                        /* PISTON.C:87 */
    scd_word_set(o,26,(uint16_t)o->yposi.w.h);          /* PISTON.C:88 */
    o->yspeed.w=o->xspeed.w=0;                          /* PISTON.C:89 */
    scd_word_set(o,27,(uint16_t)rad_tbl[(sub&48)>>4]);  /* PISTON.C:94-97 */
    scd_word_set(o,29,(uint16_t)radius_tbl[(sub&64)>>6]); /* PISTON.C:98-100 */
    /* PISTON.C:101-105 compute a sine offset into a local and discard it. */
    if((sub&3)==1){                                     /* PISTON.C:125-136 */
        o->patno=1;o->sprhsize=32;o->sprvsize=96;
        scd_word_set(o,28,(uint16_t)piston_spd_tbl[(sub&4)/4]);
        o->actfree[14]=delay_time_tbl[(sub&8)/8];
        o->actfree[20]=0;
    }else{                                              /* PISTON.C:115-120 */
        o->patno=0;o->sprhsize=o->sprvsize=32;
        scd_word_set(o,28,(uint16_t)piston_spd_tbl[(sub&12)/4]);
    }
}

/* ride_on_chk for the piston. Returns non-zero when retail ride_on_chk
   returns 1: standing on top (hit_y) or pushed out below (hit_yu0). */
static int piston_ride(unsigned i){
    sprite_status *o=&actwk[i+1],*p=&actwk[0];
    int airborne=p->cddat&2;
    int hit=static_solid(i);
    /* RIDECHK.C:587-593 hit_yu1: a descending object that strikes a grounded
       player from above kills him (playdieset), then hit_yu0 still pushes
       him below the object and zeroes his Y speed (RIDECHK.C:610-612). */
    if(hit==2 && !airborne && o->yspeed.w>0){
        playdieset(p);p->yspeed.w=0;scd_objects_death_record();
    }
    return hit;
}

/* PISTON.C:142-201 piston_move. */
static void piston_step(unsigned i){
    static const short jump_tbl[2]={-4096,-2560};        /* PISTON.C:145-147 */
    sprite_status *o=&actwk[i+1],*p=&actwk[0];
    unsigned sub=(uint8_t)o->userflag.b.h;
    short cal_posi;
    /* PISTON.C:61-66, 83: the spawn update runs piston_init only (r_no0 0 -> 2);
       piston_move starts on the next update. */
    if(!o->r_no0){o->r_no0=2;piston_spawn(o);return;}
    if(o->yspeed.w<0)piston_ride(i);                    /* PISTON.C:149 */
    int32_t stack_yposi=o->yposi.l;                     /* PISTON.C:150 */
    if((sub&3)==1){                                     /* PISTON.C:151 */
        if(o->actfree[20]&128){                         /* PISTON.C:153 */
            cal_posi=o->yposi.w.h;
            if((int8_t)--o->actfree[16]>=0)goto label1; /* PISTON.C:155 */
            o->actfree[20]&=127;
        }else{
            cal_posi=(short)scd_word_get(o,27);         /* PISTON.C:160 */
            if(cal_posi==256 || cal_posi==768){         /* PISTON.C:161-166 */
                o->actfree[20]|=128;
                o->actfree[16]=o->actfree[14];
                cal_posi=o->yposi.w.h;
                goto label1;
            }
        }
    }
    {
        short cal_rad=(short)((short)scd_word_get(o,27)+(short)scd_word_get(o,28)); /* PISTON.C:171 */
        cal_rad&=1023;                                  /* PISTON.C:173 */
        scd_word_set(o,27,(uint16_t)cal_rad);           /* PISTON.C:174 */
        short sin_tmp,cos_tmp;
        sinset((unsigned char)(char)(cal_rad>>2),&sin_tmp,&cos_tmp); /* PISTON.C:175 */
        int sin_data=sin_tmp;                           /* PISTON.C:176-180 */
        sin_data*=(short)scd_word_get(o,29);
        sin_data>>=8;
        sin_data+=(short)scd_word_get(o,26);
        cal_posi=(short)sin_data;
    }
label1:
    o->yposi.w.h=cal_posi;                              /* PISTON.C:182 */
    {
        int32_t cal_yposi=(int32_t)cal_posi*65536-stack_yposi; /* PISTON.C:183 */
        o->yspeed.w=(short)(cal_yposi>>8);              /* PISTON.C:184 */
    }
    if((sub&3)==1 && (short)scd_word_get(o,27)==528){   /* PISTON.C:185-188 */
        if(!piston_ride(i))return;                      /* PISTON.C:190 */
        p->yspeed.w=jump_tbl[(sub&128)>>7];             /* PISTON.C:192-196 */
        p->cddat|=2;
        p->cddat&=247;
        p->mstno.b.h=16;
        o->cddat&=247;
    }
    if(o->yspeed.w>=0)piston_ride(i);                   /* PISTON.C:199-200 */
}
