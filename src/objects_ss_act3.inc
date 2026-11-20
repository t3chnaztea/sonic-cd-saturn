/* Stardust Speedway Act 3 actors: R7/HARI73.C, WALL73.C, GAITOU73.C and
   EMIE7.C (Amy, with heart7 and EMIE7CG.C's animation scripts).
   Line-for-line ports on the PC scratch layout (objects_ss_common.inc);
   hitchk/ride_on_clr are the tp_* RIDECHK port. Children reuse the parent
   type (hari73 pieces, the gaitou73 pole) or their own (heart7). */

/* Act 3's program is R73C (Good Future, generate_flag set) or R73D. */
static int ss_generate(void){return current_era==2;}

/* ---- HARI73.C: spike block that Metal Sonic smashes --------------------- */
/* BOSS_7.C hari_spdadd (add_spd2): the pieces' gravity and motion. */
static void ss_add_spd2(sprite_status *o){
    o->xspeed.w+=ss_w(o,26);o->yspeed.w+=ss_w(o,27);
    o->xposi.l+=(int)o->xspeed.w<<8;o->yposi.l+=(int)o->yspeed.w<<8;
}
/* act_search: the first actor from 2 with actor number n (47, msnc). */
static int ss_act_search(sprite_status **out,unsigned n){
    for(int i=2;i<128;i++)if(actwk[i].actno==n){*out=&actwk[i];return 0;}
    return -1;
}
static void hari73_move(sprite_status *o);
static void hari73_msnc_hit(sprite_status *o){
    static const short spd_tbl[16]={576,-512,6,16,544,-512,0,18,512,-512,6,20,480,-512,10,16};
    soundset(163);
    short d4=-12;
    for(int i=0;i<16;i+=4){
        sprite_status *c;
        if(tp_actwkchk(&c))break;
        tp_setactno(c,SCD_OBJ_R7_HARI73);
        /* ACTSET reserves each child before Frameout releases the parent. */
        scd_boss_slot_sync();
        c->r_no0=4;c->patno=1;c->actflg=4;c->sprpri=5;c->sprhsize=4;c->sprvsize=16;c->sproffset=1276;
        c->xposi.w.h=o->xposi.w.h+d4;c->yposi.w.h=o->yposi.w.h;
        c->xspeed.w=spd_tbl[i];c->yspeed.w=spd_tbl[i+1];ss_ws(c,26,spd_tbl[i+2]);ss_ws(c,27,spd_tbl[i+3]);
        d4+=8;
    }
    if(o->actfree[11])tp_ride_on_clr(o,&actwk[0]);
    /* Retail Frameout clears only this slot. Keep Sonic's push bit until
       his next contact update, rather than remove_slot's generic cleanup. */
    unsigned char pushing=actwk[0].cddat&32;
    tp_frameout(o);actwk[0].cddat|=pushing;
}
static void hari73_move(sprite_status *o){
    if(ss_w(o,23)){
        sprite_status *m=&actwk[ss_w(o,23)];
        short d0=o->xposi.w.h-m->xposi.w.h;
        if(o->xposi.w.h<m->xposi.w.h)d0=-d0;
        if((short)o->sprhsize>d0){hari73_msnc_hit(o);return;}
    }
    if(tp_hitchk(o,&actwk[0])){
        actwk[0].colino=0;o->actfree[11]=0;
        if(actwk[0].cddat&8){
            o->actfree[11]=1;
            if(!plpower_m && actwk[0].r_no0!=4 && !actwk[0].actfree[6]){
                actwk[0].yposi.l-=(int)actwk[0].yspeed.w<<8;
                scd_objects_hurt(o->xposi.w.h);
                tp_ride_on_clr(o,&actwk[0]);
            }
        }
    }
    tp_draw(o);
    tp_frameout_s(o);
}
static void hari73_act(sprite_status *o){
    switch(o->r_no0/2){
    case 0:{
        o->r_no0+=2;o->actflg|=4;o->sprpri=3;o->sproffset=1276;o->sprhs=16;o->sprhsize=16;o->sprvsize=12;
        sprite_status *m;
        if(!ss_act_search(&m,47)){
            ss_ws(o,23,(int)(m-actwk));
            if(o->xposi.w.h-(short)o->sprhsize-m->xposi.w.h-(short)m->sprhsize>=0){hari73_move(o);return;}
        }
        tp_frameout(o);
        return;
    }
    case 1:hari73_move(o);return;
    default:
        ss_add_spd2(o);
        o->actfree[10]=(uint8_t)((o->actfree[10]+1)&3);
        if(o->actfree[10]&2)tp_draw(o);
        tp_frameout_s(o);
        return;
    }
}

/* ---- WALL73.C: the blocks that close behind Metal Sonic's door ---------- */
static const uint8_t wall73_tbl0[12]={11,16,32,16,48,16,64,16,11,32,11,48};
static int wall73_move_blk(sprite_status *o){
    if(!(bossflag&128))return 0;
    if(!ss_w(o,23)){
        short d0=32,d1=512;
        if(o->userflag.b.l&128){d0=-d0;d1=-d1;}
        o->yspeed.w=d1;ss_ws(o,23,o->yposi.w.h+d0);
    }
    o->yposi.l+=(int)o->yspeed.w<<8;
    if(ss_w(o,23)!=o->yposi.w.h)return 0;
    ss_ws(o,23,0);
    char b0=(char)((o->userflag.b.l&15)-1);
    if(!b0){
        bossflag&=127;
        if(o->userflag.b.l&64){o->userflag.b.l=0;return 0;}
        tp_frameout(o);return -1;
    }
    o->userflag.b.l&=-16;o->userflag.b.l+=b0;
    if(o->userflag.b.l&32)return 0;
    if(o->userflag.b.l&16){
        if(++o->patno==1)o->patno=4;
        o->yposi.w.h-=16;
    }else{
        if(--o->patno==3)o->patno=0;
        o->yposi.w.h+=16;
    }
    o->sprhs=o->sprhsize=wall73_tbl0[o->patno*2];o->sprvsize=wall73_tbl0[o->patno*2+1];
    return 0;
}
static void wall73_act(sprite_status *o){
    if(!o->r_no0){
        o->r_no0+=2;o->actflg|=4;o->sprpri=3;o->sproffset=17676;o->patno=o->userflag.b.h;
        o->sprhs=o->sprhsize=wall73_tbl0[o->userflag.b.h*2];o->sprvsize=wall73_tbl0[o->userflag.b.h*2+1];
    }
    if(o->userflag.b.l && wall73_move_blk(o))return;
    if(tp_hitchk(o,&actwk[0]))actwk[0].colino=0;
    tp_draw(o);
    tp_frameout_s(o);
}

/* ---- GAITOU73.C: the street light and its pole (background parallax) --- */
static short gaitou73_get_x(void){
    short h=(short)tp_scra_h();
    short w1=(short)((unsigned int)h/320),w2=(short)((unsigned int)h%320);
    if(w1>48)w1=0;
    w1=(short)((w1+1)*320+256);w2=(short)(w2*256/320);
    return (short)(w1-w2);
}
static void gaitou73_act(sprite_status *o){
    switch(o->r_no0/2){
    case 0:
        o->actflg=4;o->sprpri=0;o->sproffset=17692;
        if(!o->userflag.b.h){
            sprite_status *c;
            if(!tp_actwkchk2(o,&c)){
                tp_setactno(c,SCD_OBJ_R7_GAITOU73);c->userflag.b.h=1;
                if(tp_slot(c)<SCD_OBJECT_CAPACITY)pool[tp_slot(c)].subtype=1;
                ss_ws(c,25,(int)ss_index(o));ss_ws(o,25,(int)ss_index(c));
            }
            o->sprhsize=24;o->sprvsize=12;o->r_no0=2;
        }else{
            o->patno=1;o->sprhsize=8;o->sprvsize=112;o->r_no0=4;
        }
        break;
    case 1:{
        short v=(short)scd_act_view_y();
        ss_ws(o,26,gaitou73_get_x());
        ss_ws(o,27,352-(v-352)/3);
        o->xposi.w.h=ss_w(o,26);o->yposi.w.h=ss_w(o,27);
        if(ss_w(o,27)+12>=v){o->patno=0;o->sprhsize=24;o->sprvsize=12;}
        else{o->yposi.w.h+=348;o->patno=1;o->sprhsize=8;o->sprvsize=112;}
        break;
    }
    default:{
        sprite_status *b=&actwk[ss_w(o,25)];
        o->xposi.w.h=ss_w(b,26);o->yposi.w.h=ss_w(b,27)+124;
        break;
    }
    }
    tp_draw(o);
}

/* ---- EMIE7.C: Amy at the end of the race -------------------------------- */
/* EMIE7CG.C em_pchg: pattern, time pairs ending in -1. */
static const signed char em7_stnd2[]={11,19,12,19,-1},em7_moji[]={3,11,4,11,5,11,4,11,-1},em7_run[]={0,3,1,2,2,3,1,2,-1},
    em7_kiss[]={14,9,-1},em7_moji2[]={6,9,7,9,-1},em7_kyoro[]={11,19,12,19,11,19,12,19,-1},em7_help[]={17,7,18,7,17,7,19,7,-1};
static const signed char *const em7_pchg[7]={em7_stnd2,em7_moji,em7_run,em7_kiss,em7_moji2,em7_kyoro,em7_help};
/* The Amy colours (BOSS_7.C emie7clrset) go back to the level's when Amy
   leaves (EMIE7.C emie7clrsetx(&gamecolor[16])): the renderer reads it. */
static uint8_t ss_amy_palette_restore;
int scd_objects_ss_palette_restored(void){return ss_amy_palette_restore;}
/* GOAL.C goal_move2 (Amy's end of the act): the actor side of it. The
   results start through scd_objects_ss_goal (the clear actor 58, the time
   and ring bonus); src/act.c owns them. */
__attribute__((weak)) void scd_objects_ss_goal(void){scd_act_ss_goal(current_era==2);}
static void em7_goal_move2(sprite_status *o){
    char t=(char)(o->actfree[0]-1);
    o->actfree[0]=(uint8_t)t;
    if(t)return;
    plautoflag|=1;swdata.w=0; /* GOAL.C: stageno.w == 1282 (SS3). */
    o->actfree[0]=180;o->r_no0+=2;
    scd_objects_ss_goal();
}
static void em7_patchg(sprite_status *o){
    if(o->mstno.b.h!=o->mstno.b.l){o->mstno.b.l=o->mstno.b.h;o->patcnt=0;o->pattim=0;}
    if((char)--o->pattim<=0){
        const signed char *d=em7_pchg[(unsigned char)o->mstno.b.l];
        signed char p=d[o->patcnt];
        if(p<0){o->patcnt=0;p=d[0];}
        o->patno=p&31;o->actflg&=252;
        o->actflg|=(o->cddat^((unsigned char)p<<3|(unsigned char)p>>5))&3;
        o->pattim=(unsigned char)d[o->patcnt+1];o->patcnt+=2;
    }
}
static void em7_setdirect(sprite_status *e,sprite_status *s){
    if(e->xposi.w.h<s->xposi.w.h){e->cddat&=254;e->actflg&=254;}
    else{e->cddat|=1;e->actflg|=1;}
}
static void em7_speedsetx(sprite_status *o){o->xposi.l+=(int)o->xspeed.w<<8;}
static void em7_speedsety(sprite_status *o){o->yposi.l+=(int)o->yspeed.w<<8;}
static void em7_heartset(sprite_status *o){
    if(o->actfree[17]+6>255){
        sprite_status *h;
        if(!tp_actwkchk(&h)){
            tp_setactno(h,SCD_OBJ_R7_HEART7);
            short wk=8;
            if(o->cddat&1)wk=-10;
            if(o->actfree[20]&1)wk=-wk;
            h->xposi.w.h=o->xposi.w.h+wk;h->yposi.w.h=o->yposi.w.h-12;
        }
    }
    o->actfree[17]+=6;
}
static void em7_dakicheck(sprite_status *o){
    if(editmode.b.h)return;
    short p1,p2;
    /* Retail R73C $20F1DA: facing right tests SonicX-AmyX. The PC
       EMIE7.C reconstruction reverses this branch. */
    if(!(actwk[0].cddat&1)){p1=actwk[0].xposi.w.h;p2=o->xposi.w.h;}
    else{p1=o->xposi.w.h;p2=actwk[0].xposi.w.h;}
    if(p1<p2)return;
    if((p1-=p2)<8 || p1>=28)return;
    p1=actwk[0].yposi.w.h-o->yposi.w.h;
    if((p1+=8)<0 || p1>=16)return;
    if((actwk[0].cddat&2) || (actwk[0].cddat&4))o->r_no0=14;
    else{
        o->actfree[20]|=129;o->xspeed.w=o->yspeed.w=0;o->patno=7;o->r_no0=10;
        sub_sync(124);
    }
}
static void em7_tobim(sprite_status *o){
    em7_speedsetx(o);em7_speedsety(o);
    if((o->yspeed.w+=64)>=0)o->patno=7;
    if(o->yposi.w.h>=464){
        o->yposi.w.h=464;o->xspeed.w=0;o->yspeed.w=0;
        if((short)o->actfree[16]+16<256){o->actfree[16]+=16;return;}
        o->actfree[16]+=16;o->r_no0=4;
    }
}
static void em7_move1(sprite_status *o){
    em7_heartset(o);em7_setdirect(o,&actwk[0]);
    if(ss_w(o,26)){
        if(!ss_ws(o,26,ss_w(o,26)-1)){
            o->actfree[60-46]=255;pltime_f=0;scd_player_stop_clock();o->actfree[0]=1;
            em7_goal_move2(o);return;
        }
    }
    if(!o->actfree[21] || !(--o->actfree[21])){
        em7_dakicheck(o);
        short len=actwk[0].xposi.w.h-o->xposi.w.h;
        if(len<0)len=-len;
        if(((o->actfree[20]&4) && len<32) || (!actwk[0].xspeed.w && len<10)){
            o->actfree[20]|=4;o->xspeed.w=0;o->mstno.b.h=1;em7_patchg(o);return;
        }
        /* R73D $20F02E clears the wait flag once Sonic is 32px away.
           The PC reconstruction omits this instruction. */
        o->actfree[20]&=(unsigned char)~4;
    }
    short spd=-32;
    if(!(o->cddat&1))spd=-spd;
    spd+=o->xspeed.w;
    short len=spd,maxspd=640;
    if(len<0){len=-len;maxspd=-maxspd;}
    if(len>=640)spd=maxspd;
    o->xspeed.w=spd;
    if(o->xspeed.w<0){
        len=ss_w(o,29);
        len-=ss_generate()?96:128;
        if(len>=o->xposi.w.h){o->xspeed.w=0;o->mstno.b.h=1;em7_patchg(o);return;}
    }
    short scd=emycol_d(o);
    if(scd<7 && scd>=-7)o->yposi.w.h+=scd;
    em7_speedsetx(o);
    o->mstno.b.h=2;em7_patchg(o);
}
static void emie7_act(sprite_status *o){
    switch(o->r_no0/2){
    case 0:
        o->actflg|=4;o->sproffset=41931;o->sprpri=1;o->sprhsize=12;o->sprvsize=16;
        ss_ws(o,29,o->xposi.w.h);o->colino=245;
        if(!ss_generate()){o->xposi.w.h=16195;o->yposi.w.h=427;}
        o->mstno.b.h=6;
        if(o->colicnt){
            int c=tt_child(SCD_OBJ_EXPLOSION,0);
            if(c>=0){
                pool[c].subtype=4;sprite_status *e=&actwk[c+1];e->r_no1=1;
                e->xposi.w.h=o->xposi.w.h;e->yposi.w.h=o->yposi.w.h;pool[c].home_x=e->xposi.w.h;pool[c].home_y=e->yposi.w.h;
                soundset(158);
            }
            actwk[0].yspeed.w=-actwk[0].yspeed.w;
            o->r_no0+=2;ss_ws(o,26,600);
        }else em7_patchg(o);
        break;
    case 1:
        if((signed char)o->actfree[64-46]>=0){
            o->yspeed.w+=16;em7_speedsety(o);
            if(o->yposi.w.h>=464){o->yposi.w.h=464;o->yspeed.w=0;o->actfree[64-46]=255;}
        }else{
            em7_setdirect(o,&actwk[0]);o->actfree[21]=60;o->r_no0+=2;em7_patchg(o);
        }
        break;
    case 2:case 3:em7_move1(o);break;
    case 4:case 8:em7_tobim(o);break;
    case 5:
        em7_heartset(o);plautoflag|=1;swdata.w=0;actwk[0].mstno.b.h=5;em7_setdirect(o,&actwk[0]);
        o->xposi.w.h=actwk[0].cddat&1?actwk[0].xposi.w.h+12:actwk[0].xposi.w.h-12;
        o->yposi.w.h=actwk[0].yposi.w.h;o->patno=14;
        if(!o->actfree[14]){pltime_f=0;scd_player_stop_clock();o->actfree[0]=1;em7_goal_move2(o);}
        break;
    case 6:
        em7_heartset(o);em7_setdirect(o,&actwk[0]);
        o->xposi.w.h=actwk[0].cddat&1?actwk[0].xposi.w.h+12:actwk[0].xposi.w.h-12;
        o->patno=14;
        break;
    case 7:{
        o->patno=6;
        short len=o->xposi.w.h-ss_w(o,29);
        if(len<0)len=-len;
        if(len>=128)o->xspeed.w=0;
        else o->xspeed.w=o->cddat&1?128:-128;
        o->yspeed.w=-768;o->r_no0+=2;
        em7_tobim(o);
        break;
    }
    }
    tp_draw(o);
    tp_frameout_s(o);
    if(o->actno!=SCD_OBJ_R7_EMIE7)ss_amy_palette_restore=1;
}
/* heart7: the hearts over Amy. */
static void heart7_act(sprite_status *o){
    if(!o->r_no0){
        o->r_no0+=2;o->actflg|=4;o->sproffset=971;o->patno=8;o->yspeed.w=-96;o->sprpri=3;
    }
    if(!o->actfree[18]){
        short s,c;sinset((unsigned char)(o->actfree[16]*3),&s,&c);
        o->xspeed.w=s>>2;
    }
    em7_speedsetx(o);em7_speedsety(o);
    if(++o->actfree[16]==20)++o->patno;
    else if(o->actfree[16]==110){++o->patno;o->xspeed.w=o->yspeed.w=0;o->actfree[18]=1;}
    /* frameout: heart7's actionsub/frameout_s then see a cleared actor. */
    else if(o->actfree[16]==120){tp_frameout(o);return;}
    tp_draw(o);
    tp_frameout_s(o);
}
