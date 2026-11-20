/* Stardust Speedway enemies: R7/HOTARU7.C (fireflies and their spark
   links), KABASIRA.C (the three-wheel mosquito and its shots), KANABUN.C
   (the beetle) and DANGO7.C (the pill bug). Line-for-line ports on the PC
   scratch layout (objects_ss_common.inc). The originals keep 32-bit PC
   pointers in actfree (HOTARU7's flagwork byte and offset table, the
   pattern scripts); the ports derive them from the actor instead and leave
   those bytes as the fixture's pointer-free originals do. */

/* SUICIDE.C enemy_suicide (as objects_qq_common.inc qq_enemy_suicide). */
static int ss_enemy_suicide(sprite_status *o){
    if(!good_future || (current_era==0 && !o->userflag.b.h))return 0;
    unsigned i=tp_slot(o);int x=o->xposi.w.h,y=o->yposi.w.h;
    unsigned origin=pool[i].origin;
    remove_slot(i);
    /* SUICIDE.C clears the actor, not its saved placement flag. PLAYSUB
       baku_die keeps this slot as a flower for the rest of the act. */
    if(origin<SCD_PLACEMENT_CAPACITY)deferred_reload[origin]=0;
    pool[i]=(slot){.origin=origin,.type=SCD_OBJ_EXPLOSION,.phase=CC_BADNIK_BOOM};
    o->actno=SCD_OBJ_EXPLOSION;o->xposi.w.h=x;o->yposi.w.h=y;
    return 1;
}
extern short emycol_l(sprite_status*,unsigned char);
extern short emycol_r(sprite_status*,unsigned char);
extern short atan_sonic(short,short);

/* ---- HOTARU7.C --------------------------------------------------------- */
static const short ht7_tbl[8]={36,60,8,-68,56,-56,80,16};
static const unsigned char ht7_e00[]={9,1,2,1,2,1,2,1,2,1,2,252},ht7_e01[]={3,4,2,2,2,4,4,2,2,4,4,4,2,252},
    ht7_e02[]={9,3,4,3,4,3,4,3,4,3,4,252},ht7_e03[]={9,3,4,255};
static const unsigned char ht7_b00[]={19,1,2,1,2,1,2,1,2,1,2,252},ht7_b01[]={9,4,2,2,2,4,4,2,2,4,4,4,2,252},
    ht7_b02[]={19,3,4,3,4,3,4,3,4,3,4,252},ht7_b03[]={19,3,4,255};
static const unsigned char *const ht7_pchg_e[4]={ht7_e00,ht7_e01,ht7_e02,ht7_e03};
static const unsigned char *const ht7_pchg_b[4]={ht7_b00,ht7_b01,ht7_b02,ht7_b03};
static const unsigned char ht7_tama0[]={1,0,1,2,255};
static const unsigned char *const ht7_tama[1]={ht7_tama0};
/* The table offset a_init takes from the placement (userflag & 12). */
static uint8_t ht7_table[SCD_OBJECT_CAPACITY];
/* flagwork[time_flag+cdsts*3]: native placements index it by origin (tp_cdsts). */
static uint8_t *ht7_flag(const sprite_status *o){return &tp_flagwork[ss_time_flag()+tp_cdsts(o)*3u];}
static unsigned ht7_area(sprite_status *o,sprite_status *p,unsigned short yp,unsigned short yl,unsigned short xp,unsigned short xl){
    unsigned short len=(unsigned short)((unsigned short)p->yposi.w.h-(unsigned short)o->yposi.w.h-yp);
    if(len>=yl)return 0;
    len=(unsigned short)((unsigned short)p->xposi.w.h-(unsigned short)o->xposi.w.h-xp);
    if(len>=xl)return 0;
    return 1;
}
static void ht7_ini_b(sprite_status *o,sprite_status *n){
    ss_ws(n,23,(int)ss_index(o));tp_setactno(n,o->actno);n->userflag.b.h=o->userflag.b.h;n->userflag.b.l=255;
    n->xposi.w.h=o->xposi.w.h;n->yposi.w.h=o->yposi.w.h;n->sproffset=o->sproffset;n->actfree[12]=(uint8_t)o->cdsts;
}
static void ht7_die_v(sprite_status *o,sprite_status *m){
    if(ss_w(m,28)==(short)ss_index(o))ss_ws(m,28,0);else ss_ws(m,27,0);
}
static void ht7_com1(sprite_status *o){
    tp_draw(o);
    sprite_status *m=&actwk[ss_w(o,23)];
    tp_frameout_s(o);
    if(!o->actno)ht7_die_v(o,m);
}
static void ht7_com(sprite_status *o){tp_patchg(o,o->userflag.b.h?ht7_pchg_b:ht7_pchg_e);ht7_com1(o);}
static void ht7_make_c(sprite_status *o){
    sprite_status *m=&actwk[ss_w(o,23)];
    short i1=ss_w(m,28),i2=ss_w(m,27);
    if(!i1 || !i2)return;
    sprite_status *s1=&actwk[i1],*s2=&actwk[i2];
    if(o!=s1)return;
    if(!(s1->actflg&128) || !(s2->actflg&128))return;
    short xp=s1->xposi.w.h,yp=s1->yposi.w.h,xw=s2->xposi.w.h,yw=s2->yposi.w.h;
    xw=(short)(xw-xp>>2);yw=(short)(yw-yp>>2);yp+=7;
    for(int i=0;i<3;i++){
        sprite_status *n;
        if(tp_actwkchk(&n))return;
        ss_ws(n,24,(int)ss_index(s1));ss_ws(n,23,(int)ss_index(s2));
        tp_setactno(n,s1->actno);n->userflag.b.h=s1->userflag.b.h;n->userflag.b.l=254;n->sproffset=s1->sproffset;
        xp+=xw;yp+=yw;n->xposi.w.h=xp;n->yposi.w.h=yp;
    }
}
static void ht7_b_fix(sprite_status *o){
    o->r_no0+=2;o->sprhs=o->sprhsize=12;o->sprvsize=20;o->colino=51;o->actflg=1;
    o->xposi.w.h=(short)(o->xposi.w.h-tp_scra_h()+128);o->yposi.w.h=(short)(o->yposi.w.h-(short)scd_act_view_y()+128);
    tp_patchg(o,o->userflag.b.h?ht7_pchg_b:ht7_pchg_e);tp_draw(o);
}
static void ht7_b(sprite_status *o){
    switch(o->r_no0/2){
    case 0:
        o->r_no0+=2;o->actflg|=4;o->sprpri=1;o->sprhs=o->sprhsize=20;o->sprvsize=12;o->colino=50;ss_ws(o,24,o->xposi.w.h);
        tp_lset(o,4,o->userflag.b.h?-32768:-65536);
        if(actwk[0].xposi.w.h>=o->xposi.w.h){tp_lset(o,4,-tp_l(o,4));o->actflg^=1;o->cddat^=1;}
        break;
    case 1:{
        o->xposi.l+=tp_l(o,4);
        short x=o->xposi.w.h-ss_w(o,24);
        if(x<0)x=-x;
        if(x>=80){o->xposi.l-=tp_l(o,4);tp_lset(o,4,-tp_l(o,4));o->actflg^=1;o->cddat^=1;}
        if(ht7_area(o,&actwk[0],65480,112,65456,160)){
            sprite_status *m=&actwk[ss_w(o,23)];
            short i=ss_w(m,28);if(i)actwk[i].r_no0=4;
            i=ss_w(m,27);if(i)actwk[i].r_no0=4;
        }
        ht7_com1(o);
        break;
    }
    case 2:{
        sprite_status *m=&actwk[ss_w(o,23)];
        short i=ss_w(m,28);
        if(i){
            sprite_status *s1=&actwk[i];
            if((i=ss_w(m,27))!=0){
                sprite_status *s2=&actwk[i];
                int f1=0,f2=0,sp=tp_l(o,4);if(sp<0)sp=-sp;
                short xw=(short)((s1->xposi.w.h+s2->xposi.w.h>>1)-tp_scra_h());
                if(xw<152){s1->actflg|=1;s2->actflg|=1;s1->cddat|=1;s2->cddat|=1;s1->xposi.l+=sp;s2->xposi.l+=sp;}
                else if(xw>168){s1->actflg&=254;s2->actflg&=254;s1->cddat&=254;s2->cddat&=254;s1->xposi.l-=sp;s2->xposi.l-=sp;}
                else f1=1;
                short yw=(short)((s1->yposi.w.h+s2->yposi.w.h>>1)-(short)scd_act_view_y());
                if(yw<104){s1->yposi.l+=sp;s2->yposi.l+=sp;}
                else if(yw>120){s1->yposi.l-=sp;s2->yposi.l-=sp;}
                else f2=1;
                if(f1 && f2)s1->r_no0=s2->r_no0=6;
                ht7_com1(o);
                break;
            }
        }
        o->r_no0+=2;ht7_b_fix(o);
        break;
    }
    case 3:ht7_b_fix(o);break;
    case 4:tp_patchg(o,o->userflag.b.h?ht7_pchg_b:ht7_pchg_e);tp_draw(o);break;
    case 5:
        o->r_no0+=2;o->mstno.w=511;o->actflg=4;
        o->xposi.w.h=(short)(o->xposi.w.h-128+tp_scra_h());o->yposi.w.h=(short)(o->yposi.w.h-128+(short)scd_act_view_y());
        ht7_com(o);
        break;
    case 6:case 8:ht7_com(o);break;
    case 7:o->r_no0+=2;o->mstno.w=767;if(!o->userflag.b.h)ht7_make_c(o);ht7_com(o);break;
    case 9:o->r_no0+=2;o->mstno.w=1023;ht7_com(o);break;
    default:
        o->yposi.w.h-=2;
        if(!(o->actflg&128) && (long)(actwk[0].yposi.w.h-o->yposi.w.h)>160){
            sprite_status *m=&actwk[ss_w(o,23)];
            tp_frameout(o);ht7_die_v(o,m);return;
        }
        ht7_com(o);
        break;
    }
}
static void hotaru7_act(sprite_status *o){
    switch((signed char)o->userflag.b.l){
    case -1:{
        sprite_status *m=&actwk[ss_w(o,23)];
        if(m->actno!=SCD_OBJ_R7_HOTARU7 || m->cdsts!=o->actfree[12])tp_frameout(o);
        else if(!ss_enemy_suicide(o))ht7_b(o);
        break;
    }
    case -2:{
        sprite_status *b1=&actwk[ss_w(o,24)],*b2=&actwk[ss_w(o,23)];
        if(b1->actno!=SCD_OBJ_R7_HOTARU7 || b2->actno!=SCD_OBJ_R7_HOTARU7 || b1->r_no0!=16 || b2->r_no0!=16)tp_frameout(o);
        else{
            if(!o->r_no0){o->r_no0+=2;o->actflg|=4;o->sprpri=2;o->sprhs=o->sprhsize=12;o->sprvsize=12;o->colino=180;}
            tp_patchg(o,ht7_tama);tp_draw(o);
        }
        break;
    }
    default:
        switch(o->r_no0/2){
        case 0:
            o->r_no0+=2;ht7_table[tp_slot(o)]=(uint8_t)((o->userflag.b.h&12)/2);
            o->userflag.b.h=o->userflag.b.h&1?1:0;
            o->sproffset=objects_act!=2?33885:33568;
            /* fall through: a_init ends in a_wait */
        case 1:
            if(ht7_area(o,&actwk[0],65296,480,65296,480))o->r_no0+=2;
            tp_frameout_s(o);
            break;
        case 2:{
            o->r_no0+=2;
            uint8_t *f=ht7_flag(o);const short *t=&ht7_tbl[ht7_table[tp_slot(o)]];
            sprite_status *n;
            if(!(*f&1)){
                if(tp_actwkchk2(o,&n)){tp_frameout_s0(o);return;}
                ss_ws(o,28,(int)ss_index(n));ht7_ini_b(o,n);n->xposi.w.h+=t[0];n->yposi.w.h+=t[1];
            }
            if(!(*f&2)){
                if(tp_actwkchk2(o,&n)){tp_frameout_s0(o);return;}
                ss_ws(o,27,(int)ss_index(n));ht7_ini_b(o,n);n->xposi.w.h-=t[0];n->yposi.w.h-=t[1];
            }
            break;
        }
        default:{
            uint8_t *f=ht7_flag(o);
            if(!(*f&1)){short i=ss_w(o,28);if(i && actwk[i].actno!=o->actno){*f|=1;ss_ws(o,28,0);}}
            if(!(*f&2)){short i=ss_w(o,27);if(i && actwk[i].actno!=o->actno){*f|=2;ss_ws(o,27,0);}}
            if(*f==131)tp_frameout(o);
            else if(!tp_l(o,8))tp_frameout_s0(o);
            break;
        }
        }
        break;
    }
}

/* ---- KABASIRA.C -------------------------------------------------------- */
static const unsigned char kb_p00[]={15,4,5,6,7,8,9,10,11,10,11,0,1,2,3,4,5,255};
static const unsigned char kb_p01[]={0,4,12,4,12,4,12,4,12,5,12,5,12,5,12,5,12,4,12,4,12,4,12,4,12,5,12,5,12,5,12,5,12,6,12,6,12,6,12,6,
    12,7,12,7,12,7,12,7,12,8,12,8,12,8,12,8,12,9,12,9,12,9,12,9,12,10,12,10,12,10,12,10,12,11,12,11,12,11,12,11,
    12,10,12,10,12,10,12,10,12,11,12,11,12,11,12,11,12,0,12,0,12,0,12,0,12,1,12,1,12,1,12,1,12,2,12,2,12,2,12,2,12,3,12,3,12,3,12,3,12,255};
static const unsigned char kb_p02[]={0,2,12,12,12,2,12,12,12,3,12,12,12,3,12,12,12,4,12,12,12,4,12,12,12,5,12,12,12,5,12,12,12,4,12,12,12,4,12,12,
    12,5,12,12,12,5,12,12,12,6,12,12,12,6,12,12,12,7,12,12,12,7,12,12,12,8,12,12,12,8,12,12,12,9,12,12,12,9,12,12,
    12,10,12,12,12,10,12,12,12,11,12,12,12,11,12,12,12,10,12,12,12,10,12,12,12,11,12,12,12,11,12,12,12,0,12,12,12,0,12,12,12,1,12,12,12,1,12,12,12,255};
static const unsigned char kb_p03[]={0,0,12,12,12,12,12,12,12,1,12,12,12,12,12,12,12,2,12,12,12,12,12,12,12,3,12,12,12,12,12,12,12,4,12,12,12,12,12,12,
    12,5,12,12,12,12,12,12,12,4,12,12,12,12,12,12,12,5,12,12,12,12,12,12,12,6,12,12,12,12,12,12,12,7,12,12,12,12,12,12,
    12,8,12,12,12,12,12,12,12,9,12,12,12,12,12,12,12,10,12,12,12,12,12,12,12,11,12,12,12,12,12,12,12,10,12,12,12,12,12,12,12,11,12,12,12,12,12,12,12,255};
static const unsigned char kb_p04[]={7,4,5,6,7,8,9,10,11,10,11,0,1,2,3,4,5,255};
static const unsigned char kb_p05[]={0,5,12,5,12,4,12,4,12,5,12,5,12,6,12,6,12,7,12,7,12,8,12,8,12,9,12,9,12,10,12,10,12,11,12,11,12,10,12,10,
    12,11,12,11,12,0,12,0,12,1,12,1,12,2,12,2,12,3,12,3,12,4,12,4,12,255};
static const unsigned char kb_p06[]={0,4,12,12,12,5,12,12,12,4,12,12,12,5,12,12,12,6,12,12,12,7,12,12,12,8,12,12,12,9,12,12,12,10,12,12,
    12,11,12,12,12,10,12,12,12,11,12,12,12,0,12,12,12,1,12,12,12,2,12,12,12,3,12,12,12,255};
static const unsigned char kb_p07[]={0,3,12,12,12,4,12,12,12,5,12,12,12,4,12,12,12,5,12,12,12,6,12,12,12,7,12,12,12,8,12,12,12,9,12,12,
    12,10,12,12,12,11,12,12,12,10,12,12,12,11,12,12,12,0,12,12,12,1,12,12,12,2,12,12,12,255};
static const unsigned char kb_p08[]={0,13,12,255};
static const unsigned char *const kb_pchg[9]={kb_p00,kb_p01,kb_p02,kb_p03,kb_p04,kb_p05,kb_p06,kb_p07,kb_p08};
static void kb_init_sub(sprite_status *o){o->r_no0=2;o->actflg|=4;o->sprpri=3;o->sprhs=12;o->sprhsize=12;o->sprvsize=8;o->sproffset=9158;}
static void kb_move(sprite_status *o){
    int_union s,c;s.l=c.l=0;
    if(!o->userflag.b.h && (signed char)o->userflag.b.l>=0){
        if(ss_w(o,31))ss_ws(o,31,ss_w(o,31)-1);
        else{
            short xl,yl;
            yl=actwk[0].yposi.w.h-o->yposi.w.h;
            if((unsigned short)(yl+96)<192){
                xl=actwk[0].xposi.w.h-o->xposi.w.h;
                if((unsigned short)(xl+120)<240){
                    ss_ws(o,31,240);
                    sprite_status *t;
                    if(!tp_actwkchk(&t)){
                        t->mstno.b.h=8;t->userflag.b.l=254;t->colino=241;tp_setactno(t,o->actno);
                        t->xposi.w.h=o->xposi.w.h;t->yposi.w.h=o->yposi.w.h;kb_init_sub(t);
                        sinset((unsigned char)atan_sonic(xl,yl),&s.w.l,&c.w.l);
                        s.l=(int)((unsigned int)s.l>>16&65535|(unsigned int)s.l<<16&0xFFFF0000u);
                        c.l=(int)((unsigned int)c.l>>16&65535|(unsigned int)c.l<<16&0xFFFF0000u);
                        s.l>>=7;c.l>>=7;
                        tp_lset(t,4,s.l);tp_lset(t,0,c.l);
                        if(c.l<0){t->actflg^=1;t->cddat^=1;}
                        if(o->actflg&128)soundset(160);
                    }
                }
            }
        }
    }
    short a=(short)(ss_w(o,27)+ss_w(o,29));ss_ws(o,27,a);a=(short)((unsigned short)a>>8);
    s.l=c.l=0;sinset((unsigned char)a,&s.w.l,&c.w.l);
    s.l=(int)((unsigned int)s.l>>16&65535|(unsigned int)s.l<<16&0xFFFF0000u);s.l>>=4;
    o->xposi.l=s.l+tp_l(o,0);
    a=(short)(ss_w(o,28)+ss_w(o,30));ss_ws(o,28,a);a=(short)((unsigned short)a>>8);
    s.l=c.l=0;sinset((unsigned char)a,&s.w.l,&c.w.l);
    c.l=(int)((unsigned int)c.l>>16&65535|(unsigned int)c.l<<16&0xFFFF0000u);c.l>>=2;
    o->yposi.l=c.l+tp_l(o,4);
}
static void kabasira_act(sprite_status *o){
    if((signed char)o->userflag.b.l<0){
        if((signed char)o->userflag.b.l==-1){
            if(actwk[ss_w(o,33)].actno==SCD_OBJ_R7_KABASIRA)goto label1;
            tp_frameout(o);return;
        }
        o->xposi.l+=tp_l(o,0);o->yposi.l+=tp_l(o,4);
        if(o->colicnt){
            short x=o->xposi.w.h,y=o->yposi.w.h;
            unsigned i=tp_slot(o);
            if(pool[i].origin!=65535)consumed[pool[i].origin]=1;
            pool[i].type=SCD_OBJ_EXPLOSION;pool[i].subtype=4;pool[i].age=0;pool[i].origin=65535;
            pool[i].state=pool[i].frame=pool[i].cooldown=0;pool[i].home_x=x;pool[i].home_y=y;
            memset(o,0,sizeof(*o));o->xposi.w.h=x;o->yposi.w.h=y;o->actno=SCD_OBJ_EXPLOSION;o->r_no1=1;
            soundset(158);
        }else{
            short len=actwk[0].yposi.w.h-o->yposi.w.h;if(len<0)len=-len;
            if(len>224)tp_frameout(o);
            else{tp_patchg(o,kb_pchg);tp_draw(o);tp_frameout_s(o);}
        }
        return;
    }
    if(ss_enemy_suicide(o))return;
label1:
    if(!o->r_no0){
        o->colino=49;ss_ws(o,24,o->xposi.w.h);ss_ws(o,26,o->yposi.w.h);ss_ws(o,23,-32768);ss_ws(o,25,-32768);
        short a1,a2;
        if(!o->userflag.b.h){ss_ws(o,29,512);ss_ws(o,30,256);o->mstno.b.h=4;a1=4096;a2=2048;}
        else{ss_ws(o,29,256);ss_ws(o,30,128);o->mstno.b.h=0;a1=8192;a2=4096;}
        kb_init_sub(o);
        short xa=0,ya=0;unsigned char m=0;
        for(int i=0;i<3;i++){
            sprite_status *n;
            if(tp_actwkchk2(o,&n)){tp_frameout(o);return;}
            ss_ws(n,33,(int)ss_index(o));++m;n->mstno.b.h=(unsigned char)(m+o->mstno.b.h);
            xa-=a1;ya-=a2;ss_ws(n,27,xa);ss_ws(n,28,ya);n->userflag.b.l=255;tp_setactno(n,o->actno);
            n->xposi.w.h=o->xposi.w.h;n->yposi.w.h=o->yposi.w.h;tp_lset(n,0,tp_l(o,0));tp_lset(n,4,tp_l(o,4));
            ss_ws(n,29,ss_w(o,29));ss_ws(n,30,ss_w(o,30));kb_init_sub(n);
        }
    }else kb_move(o);
    tp_patchg(o,kb_pchg);tp_draw(o);tp_frameout_s(o);
}

/* ---- KANABUN.C --------------------------------------------------------- */
static const unsigned char kn_e00[]={1,6,7,6,7,6,7,6,7,4,5,4,5,4,5,4,5,2,3,2,3,2,3,2,3,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,
    1,2,3,2,3,2,3,2,3,4,5,4,5,4,5,4,5,6,7,6,7,6,7,6,7,255};
static const unsigned char kn_b00[]={3,6,7,6,7,6,7,6,7,4,5,4,5,4,5,4,5,2,3,2,3,2,3,2,3,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,
    1,2,3,2,3,2,3,2,3,4,5,4,5,4,5,4,5,6,7,6,7,6,7,6,7,255};
static const unsigned char *const kn_pchg_e[1]={kn_e00},*const kn_pchg_b[1]={kn_b00};
static const char kn_tbl0[4]={47,48,48,0};
static void kanabun_act(sprite_status *o){
    if(ss_enemy_suicide(o))return;
    if(!o->r_no0){
        o->r_no0+=2;o->actflg|=4;o->sprpri=3;o->sproffset=9193;o->sprhs=16;o->sprhsize=16;o->sprvsize=16;
        ss_ws(o,31,o->xposi.w.h);ss_ws(o,26,o->yposi.w.h);ss_ws(o,25,-32768);
        ss_ws(o,28,o->userflag.b.h?-256:-512);ss_ls(o,16,-16384);
    }
    int_union p;int spd;short s,c;
    p.l=spd=o->xposi.l+ss_l(o,16);
    p.l=(int)((unsigned int)p.l>>16&65535|(unsigned int)p.l<<16&0xFFFF0000u);
    if((p.w.l-=ss_w(o,31))<0)p.w.l=-p.w.l;
    if(p.w.l>64){
        ss_ls(o,16,-ss_l(o,16));spd+=ss_l(o,16);o->actflg^=1;o->cddat^=1;ss_ws(o,27,0);o->mstno.w=255;
    }
    o->xposi.l=spd;
    p.w.l=(short)(ss_w(o,27)+ss_w(o,28));ss_ws(o,27,p.w.l);
    p.w.l=(short)((unsigned short)p.w.l>>8);
    sinset((unsigned char)p.w.l,&s,&c);
    p.w.l=s;
    p.l=(int)((unsigned int)p.l>>16&65535|(unsigned int)p.l<<16&0xFFFF0000u);
    p.l>>=2;p.l+=tp_l(o,4);
    o->yposi.l=p.l;
    tp_patchg(o,o->userflag.b.h?kn_pchg_b:kn_pchg_e);
    o->colino=(unsigned char)kn_tbl0[o->patno>>1];
    tp_draw(o);
    tp_frameout_s00(o,ss_w(o,31));
}

/* ---- DANGO7.C ---------------------------------------------------------- */
static const unsigned char dg_e00[]={9,0,1,255},dg_e01[]={0,0,252},dg_e02[]={3,4,4,5,252},dg_e03[]={4,2,3,2,3,2,3,252},dg_e04[]={4,2,3,255},dg_e05[]={4,5,4,4,252};
static const unsigned char dg_b00[]={29,0,1,255},dg_b01[]={59,0,252},dg_b02[]={9,4,4,5,252},dg_b03[]={9,2,3,2,3,2,3,2,3,2,3,2,3,252},dg_b04[]={9,2,3,255},dg_b05[]={9,5,4,4,252};
static const unsigned char *const dg_pchg_e[6]={dg_e00,dg_e01,dg_e02,dg_e03,dg_e04,dg_e05};
static const unsigned char *const dg_pchg_b[6]={dg_b00,dg_b01,dg_b02,dg_b03,dg_b04,dg_b05};
static void dg_patchg(sprite_status *o){tp_patchg(o,tp_l(o,4)==0?dg_pchg_e:dg_pchg_b);}
static void dg_speedset(int nw,int old,sprite_status *o){
    if(o->userflag.b.h)nw=old;
    if(!(o->actflg&1))nw=-nw;
    tp_lset(o,0,nw);
}
static short dg_move(sprite_status *o){
    short t1,t2;
    o->xposi.l+=tp_l(o,0);
    if((long)tp_l(o,0)>=0)t1=emycol_r(o,o->sprhs);
    else t1=emycol_l(o,-(char)o->sprhs);
    if(t1>=0){
        t1=emycol_d(o);t2=(short)(t1+7);
        if((unsigned short)t2<14){o->yposi.w.h+=t1;return -1;}
    }
    o->xposi.l-=tp_l(o,0);
    return 0;
}
static void dango7_act(sprite_status *o){
    if(ss_enemy_suicide(o))return;
    switch(o->r_no0/2){
    case 0:
        o->r_no0+=2;o->actflg=4;o->sprpri=3;o->sprhs=14;o->sprhsize=14;o->sprvsize=9;o->colino=44;
        o->sproffset=ss_time_flag()?9309:9193;
        tp_lset(o,4,o->userflag.b.h?1:0);
        break;
    case 1:{
        o->yposi.l+=65536;
        short d1=emycol_d(o);
        if(d1<0){o->yposi.w.h+=d1;o->r_no0+=2;}
        break;
    }
    case 2:o->r_no0+=2;dg_speedset(24576,4096,o);break;
    case 3:{
        if(!dg_move(o)){tp_lset(o,0,-tp_l(o,0));o->actflg^=1;o->cddat^=1;break;}
        short d0=actwk[0].xposi.w.h-o->xposi.w.h,d1=d0>=0?255:0;
        if((unsigned short)(d0+128)<256){
            d0=(short)(actwk[0].yposi.w.h-o->yposi.w.h+128);
            if((unsigned short)d0<256){
                d0=o->actflg&1?255:0;
                if(!(d0^d1))o->r_no0+=2;
            }
        }
        dg_patchg(o);
        break;
    }
    case 4:o->r_no0+=2;++o->mstno.b.h;break;
    case 5:case 7:case 13:dg_patchg(o);break;
    case 6:o->r_no0+=2;++o->mstno.b.h;o->yposi.w.h-=6;o->sprvsize=16;break;
    case 8:o->r_no0+=2;++o->mstno.b.h;o->yposi.w.h+=3;o->sprvsize=13;o->colino=237;tp_lset(o,0,0);break;
    case 10:o->r_no0+=2;++o->mstno.b.h;dg_speedset(0x40000,65536,o);break;
    case 9:case 11:
        if(!o->colicnt){
            if(dg_move(o))dg_patchg(o);
            else o->r_no0+=2;
        }else{
            short w1=o->xposi.w.h-actwk[0].xposi.w.h,w2=o->yposi.w.h-actwk[0].yposi.w.h,w0=atan_sonic(w1,w2),s,c;
            sinset((unsigned char)(w0&255),&s,&c);
            int l1=c*-1792;l1>>=8;actwk[0].xspeed.w=(unsigned short)(long)l1;
            int l0=s*-1792;l0>>=8;actwk[0].yspeed.w=(unsigned short)(long)l0;
            actwk[0].cddat|=2;actwk[0].cddat&=239;actwk[0].cddat&=223;actwk[0].actfree[18]=0;
            o->colicnt=0;
            w1=(short)(unsigned short)((long)l1&65535);w1=-w1;
            l1=w1;l1<<=8;tp_lset(o,0,l1);o->mstno.b.h=4;o->r_no0=22;
        }
        break;
    case 12:o->r_no0+=2;++o->mstno.b.h;o->yposi.w.h-=3;o->sprvsize=16;o->colino=44;break;
    default:o->r_no0=4;o->mstno.b.h=0;o->yposi.w.h+=6;o->sprvsize=9;break;
    }
    tp_draw(o);
    tp_frameout_s(o);
}
