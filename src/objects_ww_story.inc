/* Wacky Workbench round-specific actors: R6/SHOOT6.C (shooter, gas,
   catapalt, megami), FRIEND6.C, ET6.C, MOVIE6.C, TOGEBL6A/B/D.C. */

/* ---- SHOOT6.C: megami (ring fountain), gas (freezing gas), catapalt and
   the R6 shooter (a pipe route with jump branches). The PC keeps parent
   pointers in ((sprite_status**)o)[12] (here ww_link, the actor index) and
   the route in ((unsigned short**)o)[16] (here the subtype's table). */
extern void sub_sync(short);
static int16_t ww_link[128];
/* BOSS_4.C random() on the shared ranum. */
static int ww_random(void){
    uint32_t d1=ranum?(uint32_t)ranum:711800410u,d0=d1;
    d1=(int32_t)d1<0?(d1*4)|0x80000000u:d1*4;d1+=d0;
    d1=(int32_t)d1<0?(d1*8)|0x80000000u:d1*8;d1+=d0;
    uint16_t d0l=(uint16_t)((uint16_t)d0+(uint16_t)d1);
    d1=d1<<16|d1>>16;d0l=(uint16_t)(d0l+(uint16_t)d1);d1=(d1&0xFFFF0000u)|d0l;d1=d1<<16|d1>>16;
    ranum=(int)d1;return (int)((d0&0xFFFF0000u)|d0l);
}
static const uint8_t ww_gaschg0[]={1,3,7,6,7,253,1},ww_gaschg1[]={1,2,7,4,7,5,7,1,7,2,7,4,7,5,7,1,7,2,7,4,7,5,7,1,7,2,7,4,7,5,7,1,7,2,7,4,7,5,7,1,7,2,7,4,7,5,7,1,7,2,7,4,7,5,7,1,7,2,7,4,7,5,7,1,7,2,7,4,7,5,7,1,7,2,7,4,7,5,7,1,7,2,7,7,4,7,7,5,253,2},ww_gaschg2[]={7,7,7,2,7,7,7,5,7,7,7,7,2,7,7,7,7,5,252};
static const uint8_t *const ww_gaschg[]={ww_gaschg0,ww_gaschg1,ww_gaschg2};
static const signed char ww_gtbl[3][32]={{0,0,10,11,0,0,-1,0,0,0,10,11,0,1,0,0,0,0,10,11,0,0,1,0,0,0,10,11,0,-1,0,0},{0,0,10,11,0,-1,-1,0,0,0,10,11,0,1,-1,0,0,0,10,11,0,0,1,0,0,0,1,11,0,-1,0,0},{0,0,10,11,0,-1,-1,0,0,0,10,11,0,1,-1,0,0,0,10,11,0,1,1,0,0,0,10,11,0,-1,1,0}};
static const signed char ww_ice_tbl0[]={-16,-12,10,9,0,-1,-1,0,-16,12,10,9,2,-1,1,0,16,-12,10,9,1,1,-1,0,16,12,10,9,3,1,1,0,0,-16,15,10,1,0,-1,1,0,16,15,10,3,0,1,1};
static const uint16_t ww_shooterposi_0[]={78,0,0,0,8,32,0,0,72,0,65512,96,0,65464,112,0,65416,96,0,65392,72,0,65384,32,0,65392,0,0,65416,65504,32769,65464,65488,0,65512,65504,32768,0,0,32768,80,65504,0,65416,65432,0};
static const uint16_t ww_shooterposi_1[]={24,0,0,0,48,65520,0,96,0,32768,120,32,32768,200,0,0};
static const uint16_t ww_shooterposi_2[]={150,0,0,0,8,32,0,0,64,0,65512,96,0,65464,112,0,65416,128,0,65392,160,0,65384,192,0,65392,224,32770,65416,256,32770,65464,272,0,65512,256,0,0,224,0,8,192,0,0,160,0,65512,128,0,65464,112,0,65416,96,0,65392,64,0,65384,32,0,65392,0,32769,65416,65504,32769,65464,65488,0,65512,65504,32768,0,0,32768,64,65504,0,65320,65504,0,65352,240,0};
static const uint16_t ww_shooterposi_3[]={30,0,0,32769,24,65504,32769,72,65488,0,120,65504,32768,144,0,32768,208,65504,0,65464,65504,0};
static const uint16_t ww_shooterposi_4[]={78,0,0,32770,24,32,32770,72,48,0,120,32,0,144,0,0,152,65504,0,144,65472,0,120,65440,0,72,65424,0,24,65408,0,0,65376,0,65528,65344,0,0,65312,32769,208,65280,0,65464,65280,0,65496,16,0};
static const uint16_t ww_shooterposi_5[]={60,0,0,0,0,336,0,65432,336,0,65432,512,0,65528,512,0,65480,512,0,65480,808,0,536,808,0,536,880,0,960,880,0};
static const uint16_t ww_shooterposi_6[]={12,0,0,0,56,0,0};
static const uint16_t ww_shooterposi_7[]={18,0,0,0,0,680,0,80,680,0};
static const uint16_t ww_shooterposi_8[]={24,0,0,0,8,0,0,8,65280,0,56,65280,0};
static const uint16_t ww_shooterposi_9[]={24,0,0,0,8,0,0,8,256,0,56,256,0};
static const uint16_t ww_shooterposi_0a[]={24,0,0,0,8,0,0,8,65280,0,56,65280,0};
static const uint16_t ww_shooterposi_0b[]={12,0,0,0,96,0,0};
static const uint16_t ww_shooterposi_0c[]={24,0,0,0,432,0,0,432,256,0,992,256,0};
static const uint16_t ww_shooterposi_0d[]={30,0,0,0,0,680,0,960,680,0,960,424,0,400,424,0};
static const uint16_t ww_shooterposi_0e[]={12,0,0,0,352,0,0};
static const uint16_t ww_shooterposi_0f[]={78,0,0,0,0,696,0,65416,696,0,65416,872,0,65512,872,0,65464,952,0,65368,952,0,65464,952,0,65464,1016,0,24,1016,0,24,1112,0,65480,1112,0,65480,1248,0};
static const uint16_t ww_shooterposi_10[]={42,0,0,0,0,680,0,65416,680,0,65416,856,0,65512,856,0,65464,856,0,65464,1232,0};
static const uint16_t ww_shooterposi_11[]={48,0,0,0,0,520,0,65416,520,0,65416,696,0,65512,696,0,65480,696,0,65480,792,0,592,792,0};
static const uint16_t ww_shooterposi_12[]={12,0,0,0,296,0,0};
static const uint16_t *const ww_shooterpositbl[19]={ww_shooterposi_0,ww_shooterposi_1,ww_shooterposi_2,ww_shooterposi_3,ww_shooterposi_4,ww_shooterposi_5,ww_shooterposi_6,ww_shooterposi_7,ww_shooterposi_8,ww_shooterposi_9,ww_shooterposi_0a,ww_shooterposi_0b,ww_shooterposi_0c,ww_shooterposi_0d,ww_shooterposi_0e,ww_shooterposi_0f,ww_shooterposi_10,ww_shooterposi_11,ww_shooterposi_12};

/* megami: 50 rings, one every 11 updates, once the player stands at it. */
static void megami_act(sprite_status *o){
    switch(o->r_no0){
    case 0:o->r_no0+=2;o->actflg|=4;o->actfree[1]=50;/* fall through */
    case 2:{
        short d=actwk[0].xposi.w.h-o->xposi.w.h+16;if(d<0 || d>=32)break;
        d=actwk[0].yposi.w.h-o->yposi.w.h+32;if(d<0 || d>=64)break;
        o->r_no0+=2;break;
    }
    case 4:{
        if((signed char)--o->actfree[0]>=0)break;
        o->actfree[0]=10;
        if((signed char)--o->actfree[1]<0){o->r_no0+=2;break;}
        /* ring_set: a flyring (actor 17, the lost ring) thrown up. */
        static const short tbl[8]={-256,-128,0,128,256,384,512,640};
        sprite_status *a;
        if(tp_actwkchk(&a))break;
        unsigned i=tp_slot(a);
        a->r_no0+=2;a->mstno.b.h=2;a->xposi.w.h=o->xposi.w.h+24;a->yposi.w.h=o->yposi.w.h-16;a->sproffset=32768;a->sprpri=3;
        a->actflg=4;a->colino=71;a->sprhs=a->sprhsize=a->sprvsize=8;sys_pattim4=255;mm_spill_timer=255;a->yspeed.w=-512;a->xspeed.w=tbl[ww_random()&7];
        a->actno=SCD_OBJ_LOST_RING;pool[i]=(slot){.origin=65535,.type=SCD_OBJ_LOST_RING,.home_x=a->xposi.w.h,.home_y=a->yposi.w.h};
        break;
    }
    case 6:break;
    }
    tp_frameout_s(o);
}
/* gas: the emitter (r_no0 2) puts a cloud (4-6) below itself every 120
   updates; a cloud touching the player freezes it in ice (8-10) that it can
   jump out of; the ice then bursts into shards (12). Actors 5 are all gas. */
static void gas_ice_sub0(sprite_status *o,const signed char *tbl,short loop){
    unsigned index=0;
    for(short i=0;i<=loop;i++){
        sprite_status *a;
        if(tp_actwkchk(&a))break;
        a->r_no0=12;a->actflg|=4;a->xposi.w.h=o->xposi.w.h+tbl[index];a->yposi.w.h=o->yposi.w.h+tbl[index+1];
        a->actfree[6]=tbl[index+2];a->patno=tbl[index+3];a->actflg|=tbl[index+4];a->xspeed.w=tbl[index+5];a->yspeed.w=tbl[index+6];
        a->actfree[7]=tbl[index+7];tp_setactno(a,SCD_OBJ_R6_GAS);index+=8;
    }
}
static void gas_act(sprite_status *o){
    switch(o->r_no0){
    case 0:o->actflg|=4;o->actfree[0]=120;o->r_no0+=2;/* fall through */
    case 2:{
        if(!o->actfree[0] || --o->actfree[0])break;
        sprite_status *a;
        if(tp_actwkchk(&a))break;
        ww_link[qq_index(a)]=(int16_t)qq_index(o);a->sprpri=3;a->actflg|=4;a->sproffset=o->sproffset;
        a->xposi.w.h=o->xposi.w.h;a->yposi.w.h=o->yposi.w.h+36;a->r_no0=4;tp_setactno(a,SCD_OBJ_R6_GAS);
        break;
    }
    case 4:{
        /* gas_coli */
        sprite_status *p=&actwk[0];
        if(o->mstno.b.h==1 && p->mstno.b.h!=43 && !plpower_m && !plpower_a && p->r_no0<4 && !p->actfree[2]){
            short sz=(short)p->sprhs+16,d=p->xposi.w.h-o->xposi.w.h+sz;
            if(d>=0 && d<sz*2){
                sz=(short)p->sprvsize+32;d=p->yposi.w.h-o->yposi.w.h+sz;
                sprite_status *a;
                if(d>=0 && d<sz*2 && !tp_actwkchk(&a)){
                    /* ice_set */
                    p->actfree[2]|=65;ww_link[qq_index(a)]=0;a->actflg|=4;a->xposi.w.h=p->xposi.w.h;a->yposi.w.h=p->yposi.w.h;
                    a->sprhs=a->sprhsize=a->sprvsize=24;a->patno=8;a->r_no0=8;tp_setactno(a,SCD_OBJ_R6_GAS);
                }
            }
        }
        tp_patchg(o,ww_gaschg);break;
    }
    case 6:actwk[ww_link[qq_index(o)]].actfree[0]=120;tp_frameout(o);return;
    case 8:{
        sprite_status *p=&actwk[ww_link[qq_index(o)]];
        o->yspeed.w+=56;o->yposi.l+=o->yspeed.w<<8;
        short c=emycol_d(o);
        if(c<0){sub_sync(146);o->actfree[6]=15;o->yposi.w.h+=c;o->r_no0+=2;}
        p->yposi.l=o->yposi.l;break;
    }
    case 10:{
        sprite_status *p=&actwk[ww_link[qq_index(o)]];
        if(o->actfree[6]){
            o->actfree[6]--;
            if(!(swdata.b.l&112))break;
            p->actfree[2]&=190;p->yspeed.w=-1664;p->sprvsize=14;p->sprhs=7;p->yposi.w.h+=5;p->cddat=(p->cddat|4)&223;p->mstno.b.h=2;
            soundset(146);
        }else{p->actfree[2]&=190;ww_playdamageset(p,o);}
        o->r_no0+=2;o->patno=10;o->actfree[6]=20;o->actfree[7]=2;gas_ice_sub0(o,ww_ice_tbl0,5);
        break;
    }
    case 12:
        if(!--o->actfree[6]){
            if(o->patno!=11)gas_ice_sub0(o,ww_gtbl[o->actfree[7]],3);
            tp_frameout(o);return;
        }
        o->xposi.w.h+=o->xspeed.w;o->yposi.w.h+=o->yspeed.w;break;
    }
    tp_draw(o);tp_frameout_s(o);
}
/* catapalt: a cart the player rides; the cart runs 912 px and returns. Its
   child (actor 4, r_no0 8) is the cart's back wall that follows its parent. */
static void catapalt_act(sprite_status *o){
    sprite_status *p=&actwk[0];
    switch(o->r_no0){
    case 0:{
        o->actflg|=4;qq_ws(o,25,o->xposi.w.h);o->sprhs=o->sprhsize=28;o->sprvsize=4;o->r_no0+=2;
        sprite_status *a;
        if(tp_actwkchk2(o,&a))break;
        a->actflg|=4;a->sprhs=4;a->sprvsize=12;a->patno=1;ww_link[qq_index(a)]=(int16_t)qq_index(o);a->r_no0=8;
        tp_setactno(a,SCD_OBJ_R6_CATAPALT);
    }   /* fall through: cata_init calls cata_wait */
    case 2:
        if(!tp_ridechk(o,p))break;
        p->actfree[2]|=1;p->xposi.w.h=o->xposi.w.h;p->cddat&=254;p->mstno.b.h=58;o->r_no0+=2;o->xspeed.w=3072;break;
    case 4:{
        o->xposi.l+=o->xspeed.w<<8;tp_ridechk(o,p);
        if(swdata1.b.l&112){
            p->actfree[2]&=254;p->yspeed.w=-1664;p->xspeed.w=o->xspeed.w;p->sprvsize=14;p->sprhs=7;p->yposi.w.h+=5;
            /* ObjLauncher_Launch sets rolling, but leaves the air bit clear. */
            p->cddat=(p->cddat|4)&223;p->mstno.b.h=2;soundset(146);
        }
        short end=qq_w(o,25)+912;
        if(end>=o->xposi.w.h)break;
        o->xposi.w.h=end;o->r_no0+=2;
        if(!(o->cddat&8))break;
        p->actfree[2]&=254;p->xspeed.w=o->xspeed.w;p->mstno.b.h=0;p->cddat=(p->cddat|2)&247;
        break;
    }
    case 6:{
        o->xposi.w.h-=4;short home=qq_w(o,25);
        if(home>=o->xposi.w.h){o->xposi.w.h=home;o->r_no0=2;}
        break;
    }
    case 8:{
        sprite_status *m=&actwk[ww_link[qq_index(o)]];
        if(m->r_no0>=4)break;
        o->xposi.w.h=m->xposi.w.h-24;o->yposi.w.h=m->yposi.w.h-16;tp_hitchk(o,p);break;
    }
    }
    tp_draw(o);tp_frameout_s(o);
}
/* shooter (R6): the player is carried through relative waypoints; a
   negative waypoint word is a branch taken while jump is held. */
static void shoot6_spdset(sprite_status *o){
    sprite_status *p=&actwk[0];
    short m0=p->mspeed.w,m1=m0;
    short cx=qq_w(o,29)+o->xposi.w.h-p->xposi.w.h,cy=qq_w(o,30)+o->yposi.w.h-p->yposi.w.h;
    if(cx<0){cx=-cx;m0=-m0;}
    if(cy<0){cy=-cy;m1=-m1;}
    int32_t lx,ly;
    if(cx<=cy){
        ly=(int32_t)((uint32_t)(short)(qq_w(o,30)+o->yposi.w.h-p->yposi.w.h)<<16)/m1;
        lx=(int32_t)((uint32_t)(short)(qq_w(o,29)+o->xposi.w.h-p->xposi.w.h)<<16);
        if(lx)lx/=ly;
        p->xspeed.w=(short)lx;p->yspeed.w=m1;if(ly<0)ly=-ly;
        o->actfree[4]=(uint8_t)(ly>>8);o->actfree[5]=(uint8_t)ly;return;
    }
    lx=(int32_t)((uint32_t)(short)(qq_w(o,29)+o->xposi.w.h-p->xposi.w.h)<<16)/m0;
    ly=(int32_t)((uint32_t)(short)(qq_w(o,30)+o->yposi.w.h-p->yposi.w.h)<<16);
    if(ly)ly/=lx;
    p->yspeed.w=(short)ly;p->xspeed.w=m0;if(lx<0)lx=-lx;
    o->actfree[4]=(uint8_t)(lx>>8);o->actfree[5]=(uint8_t)lx;
}
static void shoot6_act(sprite_status *o){
    sprite_status *p=&actwk[0];
    /* time_flag bit 7 (a time warp in progress) never reaches native actors. */
    if(p->mstno.b.h==43 || p->r_no0>=6)return;
    const uint16_t *tbl=ww_shooterpositbl[(o->userflag.b.h&127)%19];
    switch(o->r_no0){
    case 0:
        o->actflg=4;o->sprpri=1;o->sprhsize=16;o->r_no0+=2;
        o->actfree[16]=tbl[0]>>8;o->actfree[17]=tbl[0]&255;qq_ws(o,29,tbl[1]);qq_ws(o,30,tbl[2]);
        /* fall through: shooterinit calls shootermove */
    case 2:{
        if(p->r_no0>=6)break;
        short c=p->xposi.w.h-o->xposi.w.h+32;if(c>=64 || c<0)break;
        c=p->yposi.w.h-o->yposi.w.h+48;if(c>=96 || c<0)break;
        if(p->actfree[2])break;
        if(p->r_no0==4){p->r_no0-=2;scd_word_set(p,26,120);}
        o->r_no0+=2;p->actfree[2]=129;if(o->userflag.b.l)p->actfree[2]|=64;
        p->mstno.b.h=2;p->mspeed.w=2048;
        if((int8_t)o->userflag.b.h>=0)p->actflg&=191;else p->actflg|=64;
        if(p->r_no0==4)p->r_no0-=2;
        p->xspeed.w=p->yspeed.w=0;o->cddat&=223;p->cddat=(p->cddat&223)|2;
        p->xposi.w.h=o->xposi.w.h;p->yposi.w.h=o->yposi.w.h;o->actfree[8]=0;soundset(145);
        break;
    }
    case 4:p->mstno.b.h=2;shoot6_spdset(o);o->r_no0+=2;soundset(145);break;
    case 6:{
        p->mstno.b.h=2;
        const uint16_t *move=tbl+1;uint8_t mc;
        if((signed char)--o->actfree[4]<0){
            p->xposi.w.h=qq_w(o,29)+o->xposi.w.h;p->yposi.w.h=qq_w(o,30)+o->yposi.w.h;
            mc=o->actfree[16]+6;
            if(mc>=o->actfree[17]){p->yposi.w.h&=2047;o->r_no0=0;p->actfree[2]=0;break;}
            o->actfree[16]=mc;
        }else{
            p->xposi.l+=p->xspeed.w<<8;p->yposi.l+=p->yspeed.w<<8;
            short d=(short)move[o->actfree[16]/2+2];
            if(d>=0 || !(swdata1.b.h&112))break;
            d&=32767;mc=(uint8_t)(o->actfree[17]+(uint8_t)d*6);o->actfree[16]=mc;
        }
        qq_ws(o,29,move[mc/2]);qq_ws(o,30,move[mc/2+1]);shoot6_spdset(o);
        break;
    }
    }
    /* Tunnel Path/Main.asm: the idle routines despawn by camera chunk. */
    if(o->r_no0<4)tp_frameout_s(o);
}

/* ---- TOGEBL6A/B/D.C: spiked-ball chain circling its hub ------------------ */
/* One native type; the program's build decides the chain: Present (A) spawns
   six balls whose third is orphaned (its slot word [27] is overwritten), the
   Past (B) five (the fourth also overwritten), the Futures (D) six. Balls are
   children (userflag.b.h -1) placed at the positions the hub writes into
   their actfree ints. */
static unsigned togeball6_build(void){return current_era==0?0:current_era==1?1:2;}
static void togeball6_act(sprite_status *o){
    static const uint8_t slots[3][6]={{25,26,27,27,28,29},{25,26,27,27,28,0},{25,26,27,28,29,30}};
    unsigned v=togeball6_build();
    if((int8_t)o->userflag.b.h<0){
        if(!o->r_no0){o->r_no0+=2;o->actflg|=4;o->sprpri=1;o->sproffset=1016;o->colino=185;}
        o->xposi.w.h=qq_w(o,24);o->yposi.w.h=qq_w(o,26);
        unsigned m=v==2?o->actfree[20]:(uint16_t)qq_w(o,33);
        if(actwk[m].actno!=SCD_OBJ_R6_TOGEBALL6){tp_frameout(o);return;}
        tp_draw(o);return;
    }
    if(!o->r_no0){
        o->r_no0+=2;o->actflg|=4;o->sprpri=1;o->sprhsize=o->sprvsize=8;o->sproffset=1016;
        qq_ws(o,24,o->userflag.b.h?-256:256);
        for(unsigned n=0;n<6 && slots[v][n];n++){
            sprite_status *a;
            if(tp_actwkchk2(o,&a)){tp_frameout(o);return;}
            qq_ws(a,33,qq_index(o));qq_ws(o,slots[v][n],qq_index(a));
            a->userflag.b.h=-1;a->sprhsize=a->sprvsize=8;tp_setactno(a,o->actno);
        }
    }else{
        qq_ws(o,23,qq_w(o,23)+qq_w(o,24));
        short sn,cs;sinset((uint8_t)(qq_w(o,23)>>8),&sn,&cs);
        int32_t d0=(int32_t)((uint32_t)(uint16_t)sn<<16)>>2,d1=(int32_t)((uint32_t)(uint16_t)cs<<16)>>2;
        int32_t d4=d0,d5=d1;d0>>=1;d1>>=1;int32_t d2=d0,d3=d1;d0>>=1;d1>>=1;
        const int32_t oy[3][6]={{d0,d2,d0+d2,d4,d0+d4,0},{d0,d2,d0+d2,d4,0,0},{d0,d2,d0+d2,d4,d0+d4,d2+d4}};
        const int32_t ox[3][6]={{d1,d3,d1+d3,d5,d1+d5,0},{d1,d3,d1+d3,d5,0,0},{d1,d3,d1+d3,d5,d1+d5,d3+d5}};
        static const uint8_t word[3][6]={{25,26,27,28,29,0},{25,26,27,28,0,0},{25,26,27,28,29,30}};
        if(v==2){sprite_status *a=&actwk[o->actfree[4]];tp_lset(a,4,o->yposi.l+d0);tp_lset(a,0,o->xposi.l+d1);}
        for(unsigned n=0;n<6 && word[v][n];n++){
            sprite_status *a=&actwk[(uint16_t)qq_w(o,word[v][n])];
            tp_lset(a,4,o->yposi.l+oy[v][n]);tp_lset(a,0,o->xposi.l+ox[v][n]);
        }
    }
    tp_draw(o);tp_frameout_s(o);
}

/* ---- ET6.C: the generator (Eggman's time machine) ----------------------- */
/* ET4.C with R6's pattern offsets (tbl0sproffset[((stageno.w+1)<<2)+time_flag],
   stageno.w being the act) and RIDECHK hitchk solidity. A rolling touch
   (colino 250 -> pcolspecial 58) breaks it: generate_flag, 1500 points, then
   tbl0's explosions; it re-inits broken after the wait. */
static const short et6_sproffset[11]={1087,1033,0,0,1108,1024,0,0,0,0,0};
static const signed char et6_tbl0[64]={1,0,0,2,-40,-20,3,28,10,4,18,-18,5,-18,-10,6,8,-8,8,-18,14,10,-10,10,12,30,-10,15,0,-18,18,20,-10,20,-10,18,22,8,23,25,13,-10,26,23,-22,28,-3,-25,30,10,20,32,-10,2,34,30,-8,35,13,-10,40,-10,10,-1};
static void et6_act(sprite_status *o){
    static const uint8_t p0[]={3,3,4,5,6,255};static const uint8_t *const pchg[]={p0};
    sprite_status *p=&actwk[0];unsigned tf=qq_time_flag();
    switch(o->r_no0){
    case 0:{
        o->r_no0+=2;o->actflg|=4;o->sprpri=4;o->sprhs=o->sprhsize=34;o->sprvsize=32;
        unsigned d0=((objects_act+1)<<2)+tf;o->sproffset=d0<11?et6_sproffset[d0]:0;
        qq_ws(o,24,0);qq_ws(o,26,o->yposi.w.h);qq_ws(o,23,4);qq_ws(o,27,1);
        o->patno=(good_future?0:2)+(tf==0);
        if(!good_future && tf==0){o->colino=250;o->yposi.w.h-=16;}
    }   /* fall through: m_init returns to m_wait */
    case 2:
        if(good_future || tf!=0)break;
        qq_ws(o,23,qq_w(o,23)+1);
        if(!((uint16_t)qq_w(o,23)&7))o->yposi.w.h+=(uint16_t)qq_w(o,27);
        if(!((uint16_t)qq_w(o,23)&31))qq_ws(o,27,-qq_w(o,27));
        if(o->colicnt){
            o->colino=0;qq_ws(o,23,0);o->patno=7;o->r_no0+=2;
            good_future=pending_generator=1;scd_player_points(1500);
            if(tp_hitchk(o,p))tp_ride_on_clr(o,p);
            break;
        }
        tp_hitchk(o,p);tp_patchg(o,pchg);break;
    case 4:{
        short a6=qq_w(o,24);signed char d0=et6_tbl0[a6++];
        if(d0<0){o->r_no0+=2;o->actfree[0]=8;break;}
        if(++o->actfree[0]!=(uint8_t)d0)break;
        short d5=et6_tbl0[a6++],d6=et6_tbl0[a6++];qq_ws(o,24,a6);
        sprite_status *a;
        if(tp_actwkchk(&a))break;
        ww_new_explosion(a,o->xposi.w.h+d5,o->yposi.w.h+d6);soundset(158);
        break;
    }
    case 6:
        if(--o->actfree[0])break;
        o->r_no0-=6;o->yposi.w.h=qq_w(o,26);soundset(217);break;
    }
    tp_draw(o);
    if(o->r_no0<=2)tp_frameout_s(o);
}

/* ---- MOVIE6.C: the Metal Sonic projector ---------------------------------- */
/* Children: the lens (userflag.b.h -1) and the screen (1), both of this type,
   and two caged animals of FRIEND6 (userflag.b.h -128, -127), all linked by
   ((short*)o)[33]. A rolling touch (colino 251 -> pcolspecial 59) breaks it;
   tbl0's explosions follow (the PC keeps the cursor in ((char**)o)[12]; here
   an offset in ww_block_list), then projector_flag after 60 updates. */
static const uint8_t movie6_p0[]={0,2,1,3,1,255},movie6_p1[]={0,4,4,1,4,4,1,4,4,1,4,4,1,4,4,1,1,4,4,1,1,4,4,1,1,4,4,1,1,5,5,1,5,5,1,5,5,1,5,5,1,5,5,1,1,5,5,1,1,5,5,1,1,5,5,1,1,255};
static const uint8_t *const movie6_pchg[]={movie6_p0,movie6_p1};
static const signed char movie6_tbl0[]={1,0,0,5,-18,-10,10,-10,10,15,0,-18,20,-10,18,22,8,23,25,13,-10,28,-3,-25,30,10,20,32,-10,2,35,13,-10,40,-10,10,-1};
extern void divdevset(int);
static void movie6_act(sprite_status *o){
    sprite_status *p=&actwk[0];
    if(o->userflag.b.h){
        sprite_status *m=&actwk[(uint16_t)qq_w(o,33)];
        if(m->actno!=SCD_OBJ_R6_MOVIE6 || m->actfree[21]){tp_frameout(o);return;}
        if(!o->r_no0){
            o->r_no0+=2;o->actflg|=4;o->sprpri=4;
            if((int8_t)o->userflag.b.h<0){o->sprhs=o->sprhsize=8;o->sprvsize=4;o->mstno.b.h=0;}
            else{o->sprhs=o->sprhsize=20;o->sprvsize=24;o->mstno.b.h=1;}
        }else{tp_patchg(o,movie6_pchg);tp_draw(o);}
        return;
    }
    switch(o->r_no0){
    case 0:{
        if(projector_destroyed){tp_frameout(o);return;}
        divdevset(5);
        o->r_no0+=2;o->actflg|=4;o->sprpri=4;o->sprhs=o->sprhsize=o->sprvsize=12;o->colino=251;ww_block_list[qq_index(o)]=0;
        static const struct{int8_t dx,dy,sub;uint8_t friend;}kids[4]={{-21,-7,-1,0},{-72,-4,1,0},{-72,-24,-128,1},{-84,7,-127,1}};
        for(unsigned k=0;k<4;k++){
            sprite_status *c;
            if(tp_actwkchk(&c)){tp_frameout(o);return;}
            c->xposi.w.h=o->xposi.w.h+kids[k].dx;c->yposi.w.h=o->yposi.w.h+kids[k].dy;c->userflag.b.h=kids[k].sub;
            qq_ws(c,33,qq_index(o));tp_setactno(c,kids[k].friend?SCD_OBJ_R6_FRIEND6:SCD_OBJ_R6_MOVIE6);
        }
        break;
    }
    case 2:
        if(o->colicnt){o->colino=o->colicnt=0;o->r_no0+=2;}
        tp_hitchk(o,p);break;
    case 4:
        o->r_no0+=2;o->patno=1;o->actfree[21]=255;divdevset(4);
        if(tp_hitchk(o,p))tp_ride_on_clr(o,p);
        /* fall through: m_die calls m_baku */
    case 6:{
        int16_t at=ww_block_list[qq_index(o)];signed char t=movie6_tbl0[at];
        if(t<0){o->r_no0+=2;qq_ws(o,23,60);break;}
        if(++o->actfree[0]!=(uint8_t)t)break;
        short x=movie6_tbl0[at+1],y=movie6_tbl0[at+2];ww_block_list[qq_index(o)]=at+3;
        sprite_status *a;
        if(tp_actwkchk(&a))break;
        ww_new_explosion(a,o->xposi.w.h+x,o->yposi.w.h+y);soundset(158);
        break;
    }
    case 8:
        if(!qq_ws(o,23,qq_w(o,23)-1)){projector_destroyed=1;projector_flag=255;tp_frameout(o);return;}
        break;
    }
    tp_draw(o);
    if(o->r_no0>2)return;
    tp_frameout_s(o);
    if(!o->actno)divdevset(4);
}

/* ---- FRIEND6.C: freed animals (tsubame the swallow, pecky the penguin) --- */
/* userflag.b.h bit 7: caged by MOVIE6 (((short*)o)[33] links the projector).
   tbl0sproffset[((act+1)<<2)+time_flag] runs past its 11 entries in Act 3;
   the PC reads whatever follows, here 0 (as FRIEND5 in objects_qq_story.inc). */
static const uint8_t friend6_p00[]={19,0,1,255},friend6_p01[]={0,0,0,2,0,0,2,1,1,2,2,1,1,2,2,0,0,2,0,0,2,1,1,2,2,1,1,2,2,255},friend6_p10[]={0,3,3,2,3,3,2,3,3,2,3,3,2,3,3,2,2,3,3,2,2,3,3,2,2,3,3,2,2,4,4,2,4,4,2,4,4,2,4,4,2,4,4,2,2,4,4,2,2,4,4,2,2,4,4,2,2,255};
static const uint8_t *const friend6_pchg0[]={friend6_p00,friend6_p01};
static const uint8_t *const friend6_pchg1[]={friend6_p10};
static const unsigned short friend6_sproffsets[11]={1943,986,986,0,1943,986,986,0,0,0,986};
static void friend6_sproffset(sprite_status *o){
    unsigned n=((objects_act+1)<<2)+qq_time_flag();o->sproffset=n<11?friend6_sproffsets[n]:0;
}
static void friend6_roll(sprite_status *o,short d2,short d3){
    short sn,cs;sinset(o->actfree[4],&sn,&cs);cs>>=d2;sn>>=d3;
    o->xposi.w.h=cs+qq_w(o,23);o->yposi.w.h=sn+qq_w(o,24);
}
static int friend6_movie_gone(sprite_status *o){
    sprite_status *m=&actwk[(uint16_t)qq_w(o,33)];
    if(m->actno!=SCD_OBJ_R6_MOVIE6 || m->actfree[21]){tp_frameout(o);return 1;}
    return 0;
}
static void friend6_act(sprite_status *o){
    if(qq_friend_suicide(o))return;
    if(o->userflag.b.h&127){
        /* pecky */
        switch(o->r_no0){
        case 0:
            o->r_no0+=2;o->actflg|=4;o->sprvsize=o->sprhs=o->sprhsize=8;o->sprpri=4;friend6_sproffset(o);
            if((int8_t)o->userflag.b.h<0)o->r_no0=8;
            else{qq_ls(o,12,65536);qq_ls(o,13,-0x40000);}
            return;
        case 2:case 4:{
            o->xposi.l+=qq_l(o,12);o->yposi.l+=qq_l(o,13);qq_ls(o,13,qq_l(o,13)+8192);
            o->patno=qq_l(o,13)<0?0:1;
            short d1=emycol_d(o);
            if(d1<0){o->r_no0+=2;o->yposi.w.h+=d1;qq_ls(o,13,-0x40000);}
            tp_draw(o);tp_frameout_s(o);return;
        }
        case 6:o->r_no0=2;qq_ls(o,12,-qq_l(o,12));o->actflg^=1;o->cddat^=1;tp_draw(o);tp_frameout_s(o);return;
        case 8:if(friend6_movie_gone(o))return;tp_patchg(o,friend6_pchg1);tp_draw(o);return;
        }
        return;
    }
    /* tsubame */
    switch(o->r_no0){
    case 0:
        o->r_no0+=2;o->actflg=4;o->sprvsize=o->sprhs=8;o->sprpri=1;o->sprhsize=8;
        qq_ws(o,23,o->xposi.w.h);qq_ws(o,24,o->yposi.w.h);o->actflg^=1;o->cddat^=1;friend6_sproffset(o);
        if((int8_t)o->userflag.b.h<0){o->r_no0+=2;o->mstno.b.h=1;o->sprpri=3;}
        else{o->sprpri=1;o->sproffset|=32768;o->actfree[4]=1;o->actfree[5]=1;}
        return;
    case 2:{
        friend6_roll(o,1,1);
        signed char d0=(signed char)((signed char)o->actfree[4]+(signed char)o->actfree[5]),d1=(signed char)(d0+126);
        if(d1>=0){d0=(signed char)o->actfree[4];o->actfree[5]=-o->actfree[5];o->actflg^=1;o->cddat^=1;}
        o->actfree[4]=(uint8_t)d0;
        tp_patchg(o,friend6_pchg0);tp_draw(o);tp_frameout_s00(o,qq_w(o,23));return;
    }
    case 4:
        if(friend6_movie_gone(o))return;
        friend6_roll(o,3,4);o->actfree[4]+=4;
        if(!(o->actfree[4]&127)){o->actflg^=1;o->cddat^=1;}
        tp_patchg(o,friend6_pchg0);tp_draw(o);return;
    }
}
