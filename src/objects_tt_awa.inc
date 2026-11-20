/* Tidal Tempest R4/AWA.C: the bubble master (subtype bit 7) and the bubbles
   it releases (actno 32 there, SCD_OBJ_AWA here; subtype 0-2 is the size).
   A large bubble refills air through water_air_refill (PLAYSUB4.C plairset). */
void water_air_refill(void);
/* Sonic's breath bubbles, countdown numbers (PLAYSUB4.C plawa, id 33) and the
   entry splash (exit2, id 11) are dynamic actors in retail: plawamaster
   (R41C__.MMD $62D2), plwaterchk ($43D0) and this file's master ($A86E) all
   take FindObjSlot's ($7A8A) lowest free slot from actwk[32]. They share the
   pool here as SCD_OBJ_PLAWA (actor actno keeps 33/11 for src/water.c), so a
   bubble master's children land in the same slots, and run in the same update
   order, as retail. Only src/water.c allocates them, and only in zone 2. */
__attribute__((weak)) void water_pool_run(sprite_status *p){(void)p;}
int water_pool_alloc(sprite_status **actor){
    for(unsigned i=0;i<SCD_OBJECT_CAPACITY;i++)if(!pool[i].type){
        pool[i]=(slot){.origin=65535,.type=SCD_OBJ_PLAWA,.subtype=255};
        sprite_status *c=&actwk[i+1];memset(c,0,sizeof(*c));
        stats.spawned++;*actor=c;return 0;
    }
    stats.dropped++;return -1;
}
void water_pool_free(sprite_status *p){
    unsigned i=(unsigned)(p-actwk)-1;
    if(i<SCD_OBJECT_CAPACITY && pool[i].type==SCD_OBJ_PLAWA)remove_slot(i);
}
static const uint8_t awachg0[]={14,0,1,2,252},awachg1[]={14,1,2,3,4,252},awachg2[]={14,2,3,4,5,6,252},
    awachg4[]={4,252},awachg5[]={4,6,7,8,252},awachg6[]={15,19,20,21,255};
static const uint8_t *const awachg[7]={awachg0,awachg1,awachg2,awachg4,awachg4,awachg5,awachg6};
/* TBL0.C awasintbl, first half (the index is masked to 127). */
static const int8_t awasintbl[128]={0,0,0,0,0,0,1,1,1,1,1,2,2,2,2,2,2,2,3,3,3,3,3,3,3,3,3,3,3,3,3,3,
    3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,2,2,2,2,2,2,2,1,1,1,1,1,0,0,0,0,0,0,-1,-1,-1,-1,-1,-2,-2,-2,-2,-2,-3,-3,-3,
    -3,-3,-3,-3,-4,-4,-4,-4,-4,-4,-4,-4,-4,-4,-4,-4,-4,-4,-4,-4,-4,-4,-4,-4,-4,-4,-4,-4,-4,-4,-4,-4,-4,-3,-3,-3,
    -3,-3,-3,-3,-2,-2,-2,-2,-2,-1,-1,-1,-1,-1};
/* awafoutchk: a master left behind is deleted outright (frameout, not the
   reloading frameout_s); its placement does not come back. */
static int awa_fout(unsigned i){
    sprite_status *o=&actwk[i+1];
    if(!(o->actflg&128) && (uint16_t)((o->xposi.w.h&65408)-((scd_act_view_x()-128)&65408))>640){ /* R42A $A9AE cmpi.w #640; bhi: unsigned */
        if(pool[i].origin!=65535)consumed[pool[i].origin]=1;
        remove_slot(i);return 1;
    }
    if(waterposi<o->yposi.w.h)cc_object_draw(o);else o->actflg&=127;
    return 0;
}
static void awa_master(unsigned i){
    static const uint8_t awatbl[18]={0,1,0,0,0,0,1,0,0,0,0,1,0,1,0,0,1,0};
    sprite_status *o=&actwk[i+1];
    if(!scd_word_get(o,29)){
        if(waterposi>=o->yposi.w.h || !(o->actflg&128)){awa_fout(i);return;}
        tt_set_word(o,30,tt_word(o,30)-1);
        if(tt_word(o,30)>=0)goto patterns;
        tt_set_word(o,29,1);
        int32_t d1;uint8_t d0;
        do{d1=tt_random();d0=d1&7;}while(d0>=6);
        o->actfree[10]=d0;o->actfree[18]=d1&12;
        if(--o->actfree[8]&128){o->actfree[8]=o->actfree[9];o->actfree[12]|=128;}
    }else{
        tt_set_word(o,30,tt_word(o,30)-1);
        if(tt_word(o,30)>=0)goto patterns;
    }
    tt_set_word(o,30,tt_random()&31);
    if(o->actflg&128){
        int c=tt_child(SCD_OBJ_AWA,0);
        if(c>=0){
            sprite_status *s=&actwk[c+1];
            s->xposi.w.h=o->xposi.w.h+(int16_t)((tt_random()&15)-8);s->yposi.w.h=o->yposi.w.h;
            s->userflag.b.h=awatbl[o->actfree[18]+o->actfree[10]];
            if(o->actfree[12]&128){
                if(!(tt_random()&3)){
                    if(o->actfree[12]&64)goto released;
                    o->actfree[12]|=64;s->userflag.b.h=2;
                }
                if(!o->actfree[10] && !(o->actfree[12]&64)){o->actfree[12]|=64;s->userflag.b.h=2;}
            }
released:   pool[c].subtype=(uint8_t)s->userflag.b.h;
        }
    }
    if(--o->actfree[10]&128){tt_set_word(o,30,tt_word(o,30)+(tt_random()&127)+128);tt_set_word(o,29,0);}
patterns:
    tt_patchg(o,awachg);awa_fout(i);
}
static void awa_rise(unsigned i){
    sprite_status *o=&actwk[i+1],*p=actwk;
    if(waterposi>=o->yposi.w.h){o->r_no0=6;o->mstno.b.h+=3;goto burst;}
    o->xposi.w.h=awasintbl[o->direc.b.h++&127]+tt_word(o,26);
    /* awacoli */
    if(o->actfree[4] && !(p->actfree[2]&128) && o->xposi.w.h-16<p->xposi.w.h && o->xposi.w.h+16>=p->xposi.w.h &&
       o->yposi.w.h<p->yposi.w.h && o->yposi.w.h+16>=p->yposi.w.h){
        water_air_refill();soundset(173);
        p->xspeed.w=p->yspeed.w=p->mspeed.w=0;p->mstno.b.h=21;scd_word_set(p,33,35);p->actfree[18]=0;
        p->cddat&=223;p->cddat&=239;
        if(p->cddat&4){p->cddat&=251;p->sprvsize=19;p->sprhs=9;p->yposi.w.h-=5;}
        o->r_no0=6;o->mstno.b.h+=3;goto burst;
    }
    speedset2(o);
    if(o->actflg&128)cc_object_draw(o);else remove_slot(i);
    return;
burst:
    tt_patchg(o,awachg);
    if(o->actflg&128)cc_object_draw(o);else remove_slot(i);
}
static void awa_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    switch(o->r_no0){
    case 0:
        /* Retail init (R41C__.MMD $A6A0) sets width and priority only; a placed
           master keeps the loader's zero Y radius, which DrawObject ($3AF6)
           uses for its onscreen test. The 16 the native placement default
           left here made the master visible, and start its release timer,
           3 updates early. */
        o->r_no0+=2;o->sproffset=33930;o->actflg=132;o->sprhsize=16;o->sprvsize=0;o->sprpri=1;
        if(o->userflag.b.h&128){
            o->r_no0+=8;o->actfree[8]=o->actfree[9]=o->userflag.b.h&127;o->mstno.b.h=6;awa_master(i);return;
        }
        o->mstno.b.h=o->userflag.b.h;tt_set_word(o,26,o->xposi.w.h);o->yspeed.w=-136;o->direc.b.h=tt_random()&255;
        /* fall through: awamove */
    case 2:
        tt_patchg(o,awachg);if(o->patno==6)o->actfree[4]=1;
        awa_rise(i);return;
    case 4:awa_rise(i);return;
    case 6:
        tt_patchg(o,awachg);
        if(o->actflg&128)cc_object_draw(o);else remove_slot(i);
        return;
    case 8:remove_slot(i);return;
    case 10:awa_master(i);return;
    }
}
