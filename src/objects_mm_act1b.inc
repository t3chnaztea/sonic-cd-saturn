/* Metallic Madness (R8) Acts 1-2: R8/HACHI8.C (the bee with its chained
   ball), OKUSIESO.C (the launch seesaw: body, ball and platform) and
   HAGURUMA.C (the invisible gear zone that drives the player). Line-for-
   line ports on the PC scratch layout (objects_mm_common.inc). Children
   reuse their parent's type and are told apart as the original does:
   HACHI8 by userflag.b.l (0 body, >0 chain link, <0 ball: -1 long, -2
   short), OKUSIESO by actfree[20] (1 ball, 2 platform).
   Quirks kept:
   - HACHI8 reloads its bob timer by writing ((int*)o)[13] = word 25: the
     long store also clears word 27, the sine phase, on every turn.
   - HACHI8's ball keeps its chain links' actor numbers in actfree[8..17]
     and positions whatever sits in those actors, live or not.
   - OKUSIESO's ball tests yspeed == 57344, which a short never equals, so
     its second pattern step never happens.
   - HAGURUMA never draws; it forces the player's mspeed while grounded in
     its box and sets the player's actfree[14] (the PC's gear flag, which
     native player.c does not read yet). */
extern void sinset(unsigned char,short*,short*);
extern short time_stop;

/* ---- HACHI8.C: bee (body), its chain links (kusari) and ball ----------- */
static void hachi8_kusari_move(sprite_status *o){
    if(actwk[(uint16_t)mm_w(o,33)&127].actno!=SCD_OBJ_R8_HACHI8){tp_frameout(o);return;}
    tp_draw(o);
}
static void hachi8_body_move(sprite_status *o){
    static const uint8_t p00[]={2,0,1,255};
    static const uint8_t *const pchg[]={p00};
    o->xposi.l+=tp_l(o,0);
    if(mm_ws(o,26,mm_w(o,26)-1)<0){
        mm_ls(o,13,mm_w(o,25));tp_lset(o,0,(int)(0u-(uint32_t)tp_l(o,0)));o->actflg^=1;o->cddat^=1;
    }
    o->yposi.w.h=mm_w(o,31);o->yposi.w.l=0;
    mm_ws(o,27,mm_w(o,27)+mm_w(o,28));
    unsigned short d0=(unsigned short)(mm_w(o,27)>>8);
    short sn,cs;sinset((unsigned char)d0,&sn,&cs);
    int d=(int)((uint32_t)(uint16_t)sn<<16);d>>=mm_w(o,29);
    o->yposi.l+=d;
    tp_patchg(o,pchg);tp_draw(o);tp_frameout_s00(o,mm_w(o,30));
}
static void hachi8_child(sprite_status *o,sprite_status *a,int8_t role){
    a->actflg=o->actflg;a->sproffset=o->sproffset;a->userflag.b.h=o->userflag.b.h;a->userflag.b.l=role;
    tp_setactno(a,o->actno);a->xposi.w.h=o->xposi.w.h;a->yposi.w.h=o->yposi.w.h;
}
static void hachi8_ball_move(sprite_status *o){
    mm_ws(o,24,mm_w(o,24)+mm_w(o,25));
    mm_ws(o,23,mm_w(o,23)+mm_w(o,24));
    if((mm_w(o,25)>=0 && (uint16_t)mm_w(o,24)<16384 && (uint16_t)mm_w(o,23)>=16384) ||
       (mm_w(o,25)<0 && (uint16_t)mm_w(o,24)>=16384 && (uint16_t)mm_w(o,23)<16384))mm_ws(o,25,-mm_w(o,25));
    short d6=mm_w(o,26);const sprite_status *b=&actwk[(uint16_t)mm_w(o,33)&127];
    int d5=b->yposi.l+786432,d4=b->xposi.l;
    short sn,cs;sinset((unsigned char)(short)(mm_w(o,23)>>8),&sn,&cs);
    int d3=(int)((uint32_t)(uint16_t)sn<<16)>>5,d2=(int)((uint32_t)(uint16_t)cs<<16)>>5;
    for(short i=0;i<=d6;i++){
        d5+=d3;d4+=d2;
        sprite_status *k=&actwk[o->actfree[i+8]&127];
        k->yposi.l=d5;k->xposi.l=d4;
    }
    d5+=d3;d4+=d2;o->yposi.l=d5;o->xposi.l=d4;
    hachi8_kusari_move(o);
}
static void hachi8_act(sprite_status *o){
    int8_t role=(int8_t)o->userflag.b.l;
    if(!role){
        if(mm_enemy_suicide(o))return;
        if(o->r_no0){hachi8_body_move(o);return;}
        o->r_no0+=2;o->actflg|=4;o->sprpri=3;o->sprhs=o->sprhsize=o->sprvsize=16;o->colino=46;o->sproffset=9301;
        mm_ws(o,30,o->xposi.w.h);mm_ws(o,31,o->yposi.w.h);mm_ws(o,26,0);
        if(!o->userflag.b.h){tp_lset(o,0,-65536);mm_ws(o,25,128);mm_ws(o,28,1024);mm_ws(o,29,3);}
        else{tp_lset(o,0,-32768);mm_ws(o,25,256);mm_ws(o,28,768);mm_ws(o,29,4);}
        sprite_status *a;
        if(tp_actwkchk2(o,&a)){tp_frameout(o);return;}
        mm_ws(o,32,(uint16_t)mm_index(a));mm_ws(a,33,(uint16_t)mm_index(o));hachi8_child(o,a,-1);
        if(o->userflag.b.h){hachi8_body_move(o);return;}
        if(tp_actwkchk2(o,&a)){tp_frameout(o);return;}
        mm_ws(o,33,(uint16_t)mm_index(a));mm_ws(a,33,(uint16_t)mm_index(o));hachi8_child(o,a,-2);
        return;
    }
    if(role>0){
        /* kusari: a chain link */
        if(!o->r_no0){o->r_no0+=2;o->sprhs=o->sprhsize=o->sprvsize=8;o->sprpri=3;o->patno=2;}
        hachi8_kusari_move(o);return;
    }
    /* ball */
    if(o->r_no0){hachi8_ball_move(o);return;}
    o->r_no0+=2;o->sprhs=o->sprhsize=o->sprvsize=12;o->sprpri=2;o->patno=3;o->colino=175;
    if(role==-1){mm_ws(o,23,2048);mm_ws(o,25,8);mm_ws(o,26,9);}
    else{mm_ws(o,23,4096);mm_ws(o,25,8);mm_ws(o,26,3);}
    short d6=mm_w(o,26);
    for(short i=0;i<=d6;i++){
        sprite_status *a;
        if(tp_actwkchk2(o,&a)){tp_frameout(o);return;}
        o->actfree[i+8]=(uint8_t)mm_index(a);mm_ws(a,33,mm_w(o,33));
        a->actflg=o->actflg;a->sproffset=o->sproffset;a->userflag.b.h=o->userflag.b.h;a->userflag.b.l=1;
        tp_setactno(a,o->actno);a->xposi.w.h=o->xposi.w.h;a->yposi.w.h=o->yposi.w.h;
    }
    hachi8_ball_move(o);
}

/* ---- OKUSIESO.C: the seesaw that throws a spiked ball ------------------ */
static void okusieso_sub(sprite_status *o,sprite_status *a,unsigned role){
    a->r_no0=2;a->actflg|=4;a->yspeed.w=0;a->actfree[20]=(uint8_t)role;
    a->xposi.l=o->xposi.l;a->yposi.l=o->yposi.l;mm_ws(a,29,o->yposi.w.h);
    if(role==2)a->yposi.w.h=(uint16_t)a->yposi.w.h+65492;
    mm_ws(a,27,(uint8_t)mm_index(o));tp_setactno(a,o->actno);
}
static void okusieso_ball(sprite_status *o){
    if(!time_stop){
        sprite_status *m=&actwk[(uint16_t)mm_w(o,27)&127];
        if(m->actfree[20]&16){
            if(!(o->actfree[20]&64)){o->yspeed.w=-12288;o->actfree[20]|=64;}
            else{
                o->yspeed.w+=256;
                if(o->yspeed.w>=0 && (uint16_t)(o->yposi.w.h-mm_w(o,29))<=8){
                    o->yposi.w.h=mm_w(o,29)+4;m->actfree[20]|=8;o->actfree[20]|=8;m->patno=4;o->yspeed.w=0;
                }else if(!o->yspeed.w){++o->patno;o->colino=164;o->sprpri=4;}
                /* yspeed.w == 57344: never true for a short. */
            }
        }
    }
    o->yposi.l+=(int)o->yspeed.w<<6;
}
static void okusieso_dai(sprite_status *o){
    static const uint8_t speed_tbl[5]={0,8,16,8,0};
    static const short ofs_tbl[5]={-44,-28,-12,12,28};
    if(time_stop)return;
    sprite_status *m=&actwk[(uint16_t)mm_w(o,27)&127],*p=&actwk[0];
    if(!(m->actfree[20]&16)){if(tp_ride_on_chk(o,p))m->actfree[20]|=16;}
    else m->actfree[20]|=16;
    o->yposi.w.h=mm_w(o,29)+ofs_tbl[m->patno];
    o->yspeed.w=(short)((unsigned short)speed_tbl[m->patno]<<8);
    m->actfree[20]&=251;
    if(tp_ride_on_chk(o,p))m->actfree[20]|=4;
}
static void okusieso_act(sprite_status *o){
    static const uint8_t patno_tbl[4]={3,2,1,2};
    if(!o->r_no0){
        o->r_no0+=2;o->actflg|=4;o->sproffset=928;o->sprpri=5;o->patno=0;o->sprhsize=40;o->sprvsize=56;
        o->actfree[6]=1;o->actfree[20]=0;
        sprite_status *a;
        if(!tp_actwkchk2(o,&a)){
            a->sproffset=17312;a->sprpri=6;a->patno=5;a->sprhsize=a->sprvsize=16;okusieso_sub(o,a,1);
            if(!tp_actwkchk2(o,&a)){a->sproffset=928;a->sprpri=3;a->patno=8;a->sprhsize=40;a->sprvsize=12;okusieso_sub(o,a,2);}
        }
    }else if(o->actfree[20]&8){
    }else if(o->actfree[20]&1)okusieso_ball(o);
    else if(o->actfree[20]&2)okusieso_dai(o);
    else if((o->actfree[20]&16) && !time_stop){
        o->yspeed.w=0;
        if(!(o->actfree[20]&64)){
            if((int8_t)--o->actfree[6]<0){o->actfree[7]=5;o->actfree[20]|=64;++o->patno;}
        }else if(!(o->actfree[20]&32)){
            if((int8_t)--o->actfree[7]<0){
                ++o->patno;o->actfree[7]=5;
                if(o->patno>=4){o->actfree[20]|=32;o->actfree[6]=0;o->actfree[7]=10;}
            }
        }else if(o->actfree[20]&4){
            if(o->patno!=4){++o->patno;o->actfree[7]=10;}
        }else if((int8_t)--o->actfree[7]<0){
            short d=(int8_t)++o->actfree[6];
            if(d==4){o->actfree[6]=0;d=0;}
            o->patno=patno_tbl[d];o->actfree[7]=10;
        }
    }
    tp_draw(o);
    short d0=o->xposi.w.h&-128,d1=(short)(tp_scra_h()-128)&-128;
    if((unsigned short)(d0-d1)>640)tp_frameout(o);
}

/* ---- HAGURUMA.C: gear zone (never drawn) ------------------------------- */
static void haguruma_act(sprite_status *o){
    sprite_status *p=&actwk[0];
    if(!o->r_no0){
        o->r_no0+=2;o->actflg|=4;mm_ws(o,27,o->xposi.w.h);mm_ws(o,26,o->yposi.w.h);
        o->actfree[10]=24;o->actfree[14]=72;
        if(o->userflag.b.h&15){o->actfree[10]=16;o->actfree[14]=48;}
        mm_ws(o,29,(short)(((int8_t)o->userflag.b.h)&-16)*8);
        o->direc.b.h=(char)((o->cddat<<6)&192);
    }
    unsigned short c=(unsigned short)(p->xposi.w.h-mm_w(o,27)+(short)o->actfree[14]);
    int inside=0;
    if(c<(unsigned short)(o->actfree[14]*2)){
        c=(unsigned short)(p->yposi.w.h-mm_w(o,26)+(short)o->actfree[14]);
        if(c<(unsigned short)(o->actfree[14]*2)){
            if(p->cddat&2)o->actfree[16]=0;
            else inside=1;
        }else if(o->actfree[16])p->actfree[14]=o->actfree[16]=0;
    }else if(o->actfree[16])p->actfree[14]=o->actfree[16]=0;
    if(inside){
        if(!o->actfree[16]){
            o->actfree[16]=1;
            if(!(p->cddat&4))p->mstno.b.h=0;
            p->cddat&=223;p->mstno.b.l=1;p->actfree[14]=1;
        }
        if(mm_w(o,29)<0){
            if(p->mspeed.w>-1024)p->mspeed.w=-1024;
            else if(p->mspeed.w<-3840)p->mspeed.w=-3840;
        }else{
            if(p->mspeed.w<1024)p->mspeed.w=1024;
            else if(p->mspeed.w>3840)p->mspeed.w=3840;
        }
    }
    tp_frameout_s(o);
}
