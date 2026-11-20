/* Tidal Tempest enemies: R4/TONBO.C, YAGO.C, AMENBO.C and TAGAMEB4.C.
   Routine order, scratch offsets and child allocation follow the originals.
   Children (amenbo shots, tagameb spikes) reuse the parent type with
   userflag -1, as the originals do. */

/* actwkchk: lowest free actor, zeroed, carrying only the actor number. */
static int tt_child(unsigned type,unsigned first){
    for(unsigned i=first;i<SCD_OBJECT_CAPACITY;i++)if(!pool[i].type){
        pool[i]=(slot){.origin=65535,.type=type,.subtype=255};pool_typed(i,type);
        sprite_status *c=&actwk[i+1];memset(c,0,sizeof(*c));c->actno=type;
        stats.spawned++;return (int)i;
    }
    stats.dropped++;return -1;
}

/* ---- TONBO.C: dragonfly ------------------------------------------------ */
static void tonbo_step(unsigned i){
    static const uint8_t pchg0[]={2,0,1,255},pchg1[]={4,0,2,255};
    static const uint8_t *const pchg[]={pchg0,pchg1};
    sprite_status *o=&actwk[i+1];
    if(tt_enemy_suicide(i))return;
    if(!o->r_no0){
        o->r_no0=2;o->actflg=4;o->colino=44;o->sprpri=1;o->sprhs=o->sprhsize=28;o->sprvsize=16;o->sproffset=9238;
        tt_set_word(o,33,o->xposi.w.h);tt_set_free_long(o,0,o->yposi.l);
        if(!o->userflag.b.h){tt_set_long(o,13,-65536);tt_set_word(o,28,4);tt_set_word(o,30,256);}
        else{tt_set_long(o,13,-32768);tt_set_word(o,28,1);tt_set_word(o,30,512);}
        tt_set_word(o,29,tt_word(o,30)>>1);
        /* Retail R42A__.MMD $D268-$D2E2: the init falls through into the move,
           so the spawn update already steps X and the sine phase. */
    }
    {
        o->xposi.l+=tt_long(o,13);
        short sn,cs;sinset(o->actfree[4],&sn,&cs);
        o->yposi.l=tt_free_long(o,0)+(((int32_t)((uint32_t)(uint16_t)sn<<16))>>4);
        tt_set_word(o,25,tt_word(o,25)+tt_word(o,28));
        tt_set_word(o,29,tt_word(o,29)-1);
        if(!tt_word(o,29)){
            tt_set_word(o,29,tt_word(o,30));tt_set_long(o,13,-tt_long(o,13));
            o->actflg^=1;o->cddat^=1;
        }
        tt_patchg(o,pchg);
    }
    cc_object_draw(o);tt_frameout(i,tt_word(o,33));
}

/* ---- YAGO.C: hermit crab jet ------------------------------------------- */
static void yago_disp(unsigned i){
    static const uint8_t pat_chg0[]={9,0,1,255};
    static const uint8_t *const pat_chg[]={pat_chg0};
    sprite_status *o=&actwk[i+1];
    tt_patchg(o,pat_chg);cc_object_draw(o);tt_frameout(i,tt_word(o,33));
}
static short yago_wall(sprite_status *o){
    return o->actflg&1?emycol_r(o,o->sprhs):emycol_l(o,(unsigned char)-(char)o->sprhs);
}
static void yago_step(unsigned i){
    sprite_status *o=&actwk[i+1];int damaged=o->userflag.b.h!=0;
    if(tt_enemy_suicide(i))return;
    for(;;)switch(o->r_no0){
    case 0:
        tt_set_word(o,33,o->xposi.w.h);o->r_no0+=2;o->actflg=4;o->colino=47;o->sprpri=1;
        o->sprhsize=24;o->sprvsize=12;o->sproffset=9200;continue;
    case 2:{
        o->yposi.l+=65536;short d=emycol_d(o);
        if(d-5<0){
            o->r_no0+=2;if(damaged)o->yposi.w.h+=d-5;
            tt_set_free_long(o,0,5242880);tt_set_free_long(o,4,-16384);
        }
        yago_disp(i);return;
    }
    case 4:
        tt_set_free_long(o,0,tt_free_long(o,0)-16384);
        if(tt_free_long(o,0)>=0){
            o->xposi.l+=tt_free_long(o,4);
            o->yposi.w.h+=emycol_d(o)-5;
            if(yago_wall(o)-5>=0){
                int16_t t=o->xposi.w.h-actwk[0].xposi.w.h;
                if(o->actflg&1)t=-t;
                /* Retail R41D__.MMD $E25C-$E276: subi #16, subi #64, bcs, so
                   only 16 <= t < 80 is near (YAGO.C's "> 80" is the PC port's
                   reading; retail TT1DA keeps walking at t = 80). */
                if((uint16_t)(t-16)>=64){yago_disp(i);return;}
                o->r_no0+=6;tt_set_word(o,27,7);yago_disp(i);return;
            }
        }
        o->r_no0+=2;tt_set_word(o,27,31);yago_disp(i);return;
    case 6:
        tt_set_word(o,27,tt_word(o,27)-1);
        if(tt_word(o,27)){yago_disp(i);return;}
        o->r_no0+=2;tt_set_word(o,27,31);tt_set_free_long(o,0,5242880);
        tt_set_free_long(o,4,-tt_free_long(o,4));o->actflg^=1;o->cddat^=1;
        yago_disp(i);return;
    case 8:
        tt_set_word(o,27,tt_word(o,27)-1);
        if(!tt_word(o,27))o->r_no0-=4;
        yago_disp(i);return;
    case 10:
        tt_set_word(o,27,tt_word(o,27)-1);
        if(tt_word(o,27)){yago_disp(i);return;}
        o->r_no0+=2;tt_set_word(o,27,31);yago_disp(i);return;
    case 12:
        o->yposi.l+=damaged?10240:8192;
        tt_set_word(o,27,tt_word(o,27)-1);
        if(tt_word(o,27)){yago_disp(i);return;}
        o->r_no0+=2;tt_set_long(o,15,damaged?-65536:-294912);
        if(o->actflg&1)tt_set_long(o,15,-tt_long(o,15));
        tt_set_long(o,14,-98304);yago_disp(i);return;
    case 14:{
        o->xposi.l+=tt_long(o,15);
        short t=yago_wall(o);
        if(!damaged){
            if(t-5>=0){
                o->yposi.l+=tt_long(o,14);
                if(tt_long(o,14)<0)tt_set_long(o,14,tt_long(o,14)+8192);
                if(tt_frameout(i,o->xposi.w.h))return;
                yago_disp(i);return;
            }
            o->r_no0=6;tt_set_word(o,27,31);yago_disp(i);return;
        }
        if(t>=0){
            o->yposi.l+=tt_long(o,14);tt_set_long(o,14,tt_long(o,14)+4096);
            if(tt_long(o,14)>=0 && emycol_d(o)-5<0)o->r_no0=4;
            yago_disp(i);return;
        }
        o->r_no0+=2;tt_set_word(o,27,31);yago_disp(i);return;
    }
    case 16:{
        o->yposi.l+=65536;short t=emycol_d(o)-5;
        if(t>=0){yago_disp(i);return;}
        o->r_no0=6;o->yposi.w.h+=t;tt_set_word(o,27,31);yago_disp(i);return;
    }
    default:return;
    }
}

/* ---- AMENBO.C: pond skater and its shots -------------------------------- */
static const uint8_t amenbo_b0[]={20,0,1,255},amenbo_e0[]={10,0,1,255},amenbo_e1[]={5,2,3,255};
static const uint8_t *const amenbo_pchg_b[]={amenbo_b0};
static const uint8_t *const amenbo_pchg_e[]={amenbo_e0,amenbo_e1};
static void amenbo_tama(unsigned i){
    sprite_status *o=&actwk[i+1];
    tt_set_word(o,32,tt_word(o,32)-1);
    if(tt_word(o,32)>0)return;
    tt_set_word(o,32,120);
    /* act_check: the player within 96 pixels, on the side the skater faces. */
    int16_t t=actwk[0].yposi.w.h-o->yposi.w.h+96;
    if((uint16_t)t>=192)return;
    t=actwk[0].xposi.w.h-o->xposi.w.h;
    uint8_t d1=t<0?255:0,d0=0;t+=96;
    if((uint16_t)t>=192)return;
    if(!(o->actflg&1))d0=255;
    if(d1^d0)return;
    int c=tt_child(pool[i].type,0);if(c<0)return;
    sprite_status *s=&actwk[c+1];
    /* The original also writes the parent index to word 44, past the end
       of the PC actor; nothing reads it. */
    s->userflag.b.h=-1;s->xposi.w.h=o->xposi.w.h;s->yposi.w.h=o->yposi.w.h;
    s->actflg=o->actflg;s->sprpri=o->sprpri+1;s->sproffset=o->sproffset;
    s->sprhs=s->sprhsize=s->sprvsize=4;s->colino=178;
    tt_set_long(s,15,tt_long(o,15));s->mstno.b.h=1;
    tt_set_long(s,12,s->actflg&1?0x20000:-0x20000);
    pool[c].subtype=tt_long(o,15)?254:255;
    if(o->actflg&128)soundset(160);
}
static void amenbo_move0(sprite_status *o){o->xposi.l+=tt_long(o,12);o->yposi.w.h=waterposi-8;}
static void amenbo_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    if(o->userflag.b.h&128){
        o->xposi.l+=tt_long(o,12);
        tt_patchg(o,tt_long(o,15)?amenbo_pchg_e:amenbo_pchg_b);
        cc_object_draw(o);tt_frameout(i,o->xposi.w.h);return;
    }
    if(tt_enemy_suicide(i))return;
    int base=!o->userflag.b.h;
    switch(o->r_no0){
    case 0:
        o->r_no0+=2;o->actflg|=4;o->sprpri=3;o->sproffset=9136;o->sprhs=o->sprhsize=20;o->sprvsize=12;o->colino=49;
        tt_set_word(o,32,120);tt_set_word(o,33,o->xposi.w.h);
        if(base){tt_set_long(o,15,1);tt_set_long(o,13,-1536);tt_set_long(o,14,256);}
        else{tt_set_long(o,15,0);tt_set_long(o,13,-512);tt_set_long(o,14,192);}
        /* fall through: act_init calls act_accel */
    case 2:{
        int32_t d6=tt_long(o,12)+tt_long(o,13),d5=base?-98304:-49152;
        if(d6<=d5){d6=d5;o->r_no0+=2;tt_set_long(o,13,-tt_long(o,13));}
        else if(d6>=-d5){d6=-d5;o->r_no0+=2;tt_set_long(o,13,-tt_long(o,13));}
        tt_set_long(o,12,d6);
        if(base)amenbo_tama(i);
        tt_patchg(o,tt_long(o,15)?amenbo_pchg_e:amenbo_pchg_b);
        amenbo_move0(o);break;
    }
    case 4:{
        int32_t d6=tt_long(o,12)+tt_long(o,14);
        if((tt_long(o,12)<0)!=(d6<0)){o->r_no0+=2;tt_set_long(o,14,-tt_long(o,14));d6=0;tt_set_word(o,23,60);}
        tt_set_long(o,12,d6);
        if(base)amenbo_tama(i);
        amenbo_move0(o);break;
    }
    case 6:
        tt_set_word(o,23,tt_word(o,23)-1);
        if(tt_word(o,23)<=0){o->r_no0+=2;o->actflg^=1;o->cddat^=1;tt_set_word(o,23,60);}
        if(base)amenbo_tama(i);
        amenbo_move0(o);break;
    case 8:
        tt_set_word(o,23,tt_word(o,23)-1);
        if(tt_word(o,23)<=0)o->r_no0=2;
        amenbo_move0(o);break;
    }
    cc_object_draw(o);tt_frameout(i,o->xposi.w.h);
}

/* ---- TAGAMEB4.C: sea turtle and its three spikes ------------------------ */
static void tagameb_init_sub(sprite_status *o,unsigned child){
    sprite_status *c=&actwk[child];
    c->xposi.w.h=o->xposi.w.h;c->yposi.w.h=o->yposi.w.h;c->actflg|=4;c->sproffset=9168;
    c->sprpri=3;c->sprhs=c->sprhsize=c->sprvsize=2;
}
static int tagameb_make_toge(unsigned i){
    sprite_status *o=&actwk[i+1];
    for(unsigned n=0;n<3;n++){
        int c=tt_child(pool[i].type,0);
        if(c<0){remove_slot(i);return 0;}
        sprite_status *s=&actwk[c+1];s->userflag.b.h=-1;s->actfree[19]=o->cdsts;
        tt_set_word(s,33,(uint8_t)(i+1));tt_set_word(o,26+n,(uint8_t)(c+1));
    }
    static const int8_t dx[3]={2,-3,-7},dy[3]={-10,-10,-9};
    for(unsigned n=0;n<3;n++){
        unsigned c=(uint16_t)tt_word(o,26+n);tagameb_init_sub(o,c);
        actwk[c].xposi.w.h+=dx[n];actwk[c].yposi.w.h+=dy[n];
    }
    return 1;
}
static void tagameb_step(unsigned i){
    static const uint8_t pchg0[]={30,0,1,255};
    static const uint8_t *const pchg[]={pchg0};
    sprite_status *o=&actwk[i+1];
    if(o->userflag.b.h&128){
        unsigned parent=(uint16_t)tt_word(o,33);
        if(parent<1 || parent>SCD_OBJECT_CAPACITY || actwk[parent].actno!=pool[i].type || o->actfree[19]!=actwk[parent].cdsts){remove_slot(i);return;}
        if(!o->r_no0){o->r_no0+=2;cc_object_draw(o);return;}
        if(o->r_no0==2){cc_object_draw(o);return;}
        o->xposi.l+=tt_free_long(o,0);o->yposi.l+=tt_free_long(o,4);
        tt_set_free_long(o,0,tt_free_long(o,0)+tt_free_long(o,8));
        tt_set_free_long(o,4,tt_free_long(o,4)+tt_free_long(o,12));
        if(o->yposi.w.h-actwk[0].yposi.w.h>224){remove_slot(i);return;}
        cc_object_draw(o);return;
    }
    if(tt_enemy_suicide(i))return;
    int base=!o->userflag.b.h;
    switch(o->r_no0){
    case 0:
        tt_set_word(o,30,o->xposi.w.h);o->actflg|=4;o->sprpri=3;o->sproffset=9168;o->sprhs=o->sprhsize=20;o->sprvsize=8;
        o->colino=45;o->r_no0+=2;
        if(base){tt_set_long(o,12,-65536);tt_set_word(o,29,200);if(!tagameb_make_toge(i))return;}
        else{tt_set_long(o,12,-32768);tt_set_word(o,29,400);}
        break;
    case 2:{
        /* a_check (R41A__.MMD $DC9C): subi #-56 / subi #56 and subi #40 /
           subi #120, each pair read through the carry of the second subi, so
           Sonic must be 1-56 px above and 40-159 px ahead. TAGAMEB4.C's
           decompiled "- -56 - 56" and "-= 0x28 - 0x78" lose that unsigned test. */
        if(base){
            uint16_t d=(uint16_t)(actwk[0].yposi.w.h-o->yposi.w.h+56);
            if(d<56){
                int16_t x=(int16_t)(actwk[0].xposi.w.h-o->xposi.w.h);if(!(o->actflg&1))x=(int16_t)-x;
                if((uint16_t)(x-40)<120){o->r_no0+=2;tt_set_word(o,23,60);break;}
            }
        }
        int32_t v=tt_long(o,12);o->xposi.l+=v;
        if(base)for(unsigned n=0;n<3;n++)actwk[(uint16_t)tt_word(o,26+n)].xposi.l+=v;
        tt_set_word(o,23,tt_word(o,23)-1);
        if(tt_word(o,23)<0){
            tt_set_word(o,23,tt_word(o,29));tt_set_long(o,12,-tt_long(o,12));o->actflg^=1;o->cddat^=1;
            if(base){
                static const int8_t right[3]={-2,3,7},left[3]={-1,-6,-10};
                for(unsigned n=0;n<3;n++){
                    sprite_status *c=&actwk[(uint16_t)tt_word(o,26+n)];
                    c->xposi.w.h=o->xposi.w.h+(o->actflg&1?left[n]:right[n]);
                }
            }
        }
        tt_patchg(o,pchg);break;
    }
    case 4:
        tt_set_word(o,23,tt_word(o,23)-1);
        if(tt_word(o,23)<0){
            if(o->actflg&128)soundset(179);
            tt_set_word(o,23,60);o->r_no0+=2;
            if(base){
                static const int32_t vx[3]={-0x20000,65536,0x20000};
                for(unsigned n=0;n<3;n++){
                    sprite_status *c=&actwk[(uint16_t)tt_word(o,26+n)];
                    tt_set_free_long(c,0,vx[n]);tt_set_free_long(c,4,-196608);tt_set_free_long(c,8,0);tt_set_free_long(c,12,8192);
                    c->r_no0+=2;
                }
            }
        }
        break;
    case 6:
        tt_set_word(o,23,tt_word(o,23)-1);
        if(tt_word(o,23)<0){
            o->r_no0+=2;tt_set_long(o,12,base?0x40000:98304);
            if(!(o->actflg&1))tt_set_long(o,12,-tt_long(o,12));
        }
        break;
    case 8:o->xposi.l+=tt_long(o,12);break;
    }
    cc_object_draw(o);tt_frameout(i,o->xposi.w.h);
}

/* ---- PLAYSUB4.C bakuha / flower, SCORE.C tensuu --------------------------
   Retail R42C__.MMD: bakuha $6458, tensuu_set $6426 (FindObjSlot $7872, id 28),
   baku_die $64C0, flower $64DA. A Tidal Tempest explosion (actno 24: an enemy
   pcolnomal kill, or a Good Future enemy_suicide) spawns a score popup on its
   first run unless r_no1 is set, animates bakuchg (5 poses x 4 updates, then
   $FC), and the update after that becomes a flower in the same slot. Flowers
   never frame out, so they keep their dynamic slot for the rest of the act;
   the popup keeps one for 24 updates. Native PPZ/CC keep their own explosion. */
enum{TT_RETAIL_FLOWER=0x5446};
/* Quartz Quadrant runs the same PLAYSUB bakuha for a badnik's explosion (a
   COLI5 pcolnomal kill or a Good Future enemy_suicide, marked CC_BADNIK_BOOM):
   retail QQ1B slot 47, a denden killed on row 380, is the explosion to row 400
   and a flower (ID 31) from row 401 for the rest of the act; its points (ID 28)
   hold slot 32 on rows 380-403. Other QQ explosions keep the native path. */
/* R8 also dispatches PLAYSUB.C for every explosion, including ET8 children.
   Confirmed R81A $205C04 initialization and $205C64 deletion/flower branch. */
static int tt_bakuha_type(unsigned i){return (objects_zone==6 || ((objects_zone==2 || objects_zone==1 || (objects_zone==3 && pool[i].phase==CC_BADNIK_BOOM) || ((objects_zone==4 || objects_zone==5) && objects_act<2 && pool[i].phase==CC_BADNIK_BOOM)) && pool[i].subtype<2)) && pool[i].type==SCD_OBJ_EXPLOSION;}
static int tt_retail_flower(unsigned i){return (objects_zone==6 || objects_zone==2 || objects_zone==1 || objects_zone==3 || ((objects_zone==4 || objects_zone==5) && objects_act<2)) && pool[i].type==SCD_OBJ_FLOWER && pool[i].phase==TT_RETAIL_FLOWER;}
/* These two script sets serve CC, TT and QQ (tt_bakuha_type, tt_retail_flower), so
   they must stay resident: a tt_ name would put them in the TT overlay (src/saturn.x
   .rodata.tt_*), and in CC or QQ tt_patchg would scan another zone's tables for an
   end byte (a QQ explosion then ran for ~447 V-blanks per update).
   tools/test_zone_code.py fails a resident->overlay data reference that is not listed.
   TBL1.C bakuchg (retail R42C $1F79E): 0 placed/suicide, 1 enemy kill. */
static const uint8_t shared_bakuchg0[]={3,0,5,6,3,4,252},shared_bakuchg1[]={3,0,1,2,3,4,252};
static const uint8_t *const shared_bakuchg[2]={shared_bakuchg0,shared_bakuchg1};
/* PLAYSUB4.C flowchg. */
static const uint8_t shared_flowchg0[]={3,0,1,255},shared_flowchg1[]={3,2,3,2,3,252},shared_flowchg2[]={1,5,5,4,6,252},shared_flowchg3[]={19,6,7,255};
static const uint8_t *const shared_flowchg[4]={shared_flowchg0,shared_flowchg1,shared_flowchg2,shared_flowchg3};
static void tt_score_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    /* ten_init */
    if(!o->r_no0){o->r_no0=2;o->actflg=4;o->patno=o->userflag.b.h&127;o->actfree[0]=24;pool[i].frame=o->patno;}
    /* ten_move: frameout on the 24th update (the y step after it lands on a
       cleared actor in the original). */
    if(!--o->actfree[0]){remove_slot(i);return;}
    o->yposi.w.h-=2;
    if(objects_zone==5 || objects_zone==6)cc_object_draw(o);
}
static void tt_flower_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    switch(o->r_no0){
    case 0: /* flow_init. flow_sub's flagwork bit 6 (bloomed) is never set by the
               native placement flags; a seed always falls first. */
        o->actflg|=4;o->sprpri=1;o->sprvsize=0;o->sproffset=9943;
        o->mstno.b.h=0;o->mstno.b.l=2;o->r_no0=2;o->sproffset=1751;
        /* fall through: flow_move0 */
    case 2:{
        short d=emycol_d(o);
        if(d<0){o->yposi.w.h+=d;o->r_no0=4;o->mstno.b.h=1;o->sprvsize=48;}
        else o->yposi.w.h+=2;
        break;}
    case 6:o->sproffset=9943;o->mstno.b.h=2;break;   /* flow_move2 */
    case 8:o->mstno.b.h=3;o->r_no0=4;break;          /* flow_move3 */
    default:break;                                   /* 4: flow_move1 */
    }
    tt_patchg(o,shared_flowchg);pool[i].frame=o->patno;
    if(objects_zone==5 || objects_zone==6)cc_object_draw(o);
}
/* CC and WW: only a badnik's explosion (COLI3 kill or SUICIDE.C,
   marked CC_BADNIK_BOOM) has oExplodeBadnik clear, so only it makes points and
   then a flower (Explosion/Main.asm ObjExplosion_MakePoints / _Done); every
   other explosion is deleted when its animation ends (src/objects_cc_enemy.inc). */
static void tt_bakuha_step(unsigned i){
    sprite_status *o=&actwk[i+1];slot *s=&pool[i];
    switch(o->r_no0){
    case 0: /* baku_init */
        if(objects_zone==1)o->r_no1=s->phase!=CC_BADNIK_BOOM;
        o->r_no0+=2;o->actflg|=4;o->sprpri=1;o->sproffset=1664;
        if(objects_zone==5 || objects_zone==6){o->sproffset=34432;if(o->userflag.b.l)o->sproffset&=32767;}
        if(!o->r_no1){ /* tensuu_set: score index (pcolnomal word 33) / 2, bit 7 set */
            unsigned sub=((unsigned)(uint8_t)tt_word(o,33)>>1)|128;
            for(unsigned k=0;k<SCD_OBJECT_CAPACITY;k++)if(!pool[k].type){
                pool[k]=(slot){.origin=65535,.type=SCD_OBJ_SCORE,.subtype=(uint8_t)sub};
                sprite_status *c=&actwk[k+1];memset(c,0,sizeof(*c));c->actno=SCD_OBJ_SCORE;
                c->xposi.w.h=o->xposi.w.h;c->yposi.w.h=o->yposi.w.h;c->userflag.b.h=(char)sub;
                /* ACTSET.C claims the slot before later actors update and free
                   their slots in this object pass. */
                if(objects_zone==4 || objects_zone==5 || objects_zone==6)scd_boss_slot_sync();
                stats.spawned++;break;
            }
        }
        o->colino=0;o->patcnt=o->pattim=0;o->mstno.w=0;if(o->userflag.b.h)o->mstno.b.h=1;
        /* fall through: baku_move */
    case 2:tt_patchg(o,shared_bakuchg);s->frame=o->patno;if(objects_zone==5 || objects_zone==6)cc_object_draw(o);return;
    case 4: /* baku_die */
        if(o->r_no1){remove_slot(i);return;}
        s->type=SCD_OBJ_FLOWER;s->subtype=0;s->phase=TT_RETAIL_FLOWER;s->frame=0;o->actno=SCD_OBJ_FLOWER;o->r_no0=0;
        return;
    }
}
