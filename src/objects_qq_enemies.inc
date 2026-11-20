/* Quartz Quadrant enemies: R5/DENDEN.C, SASORI.C, KEMUSI.C and KUMO.C.
   Line-for-line ports on the PC scratch layout (objects_qq_common.inc).
   Children reuse the parent type, as the originals do: denden's spark and
   kumo's web shot carry userflag.b.h bit 7, sasori's tail userflag.b.l 1
   and its shot bit 7, kemusi's segments userflag.b.l -1. The pattern base
   (patbase) is implied by the type, subtype and those child flags. */

/* ---- DENDEN.C: snail with an electric antenna ---------------------------- */
static void denden_act(sprite_status *o){
    static const uint8_t p00[]={29,0,1,255},p01[]={29,2,3,255};
    static const uint8_t *const pchg[]={p00,p01};
    if(o->userflag.b.h&128){
        sprite_status *m=qq_link(o,33);
        if(m->actno!=SCD_OBJ_R5_DENDEN || o->userflag.b.l!=m->userflag.b.l){tp_frameout(o);return;}
        o->xposi.w.h=m->xposi.w.h;o->yposi.w.h=m->yposi.w.h-20;
        tp_draw(o);return;
    }
    if(qq_enemy_suicide(o))return;
    switch(o->r_no0){
    case 0:
        qq_ws(o,23,o->xposi.w.h);o->actflg|=4;o->sprpri=3;o->sproffset=9104;
        o->sprhs=o->sprhsize=16;o->sprvsize=15;o->colino=47;qq_ls(o,12,-16384);o->r_no0+=2;
        /* fall through: m_init calls m_fall */
    case 2:{
        o->yposi.l+=65536;short d1=emycol_d(o);
        if(d1<0){o->yposi.w.h+=d1;o->r_no0+=2;}
        break;
    }
    case 4:{
        o->xposi.l+=qq_l(o,12);
        short d0=o->xposi.w.h-qq_w(o,23);if(d0<0)d0=-d0;
        short d1;
        if(d0>=80 || (unsigned short)((d1=emycol_d(o))+7)>=14){
            qq_ls(o,12,-qq_l(o,12));o->actflg^=1;o->cddat^=1;break;
        }
        o->yposi.w.h+=d1;
        if(!o->userflag.b.h){
            sprite_status *p=&actwk[0];
            if((unsigned short)(p->yposi.w.h-o->yposi.w.h+120)<240 && (unsigned short)(p->xposi.w.h-o->xposi.w.h+120)<240){
                sprite_status *c;
                o->mstno.b.h=1;
                if(!qq_w(o,33) && !tp_actwkchk(&c)){
                    c->userflag.b.h=-1;c->userflag.b.l=o->userflag.b.l;tp_setactno(c,o->actno);
                    c->xposi.w.h=o->xposi.w.h;c->yposi.w.h=o->yposi.w.h-20;c->sproffset=o->sproffset;
                    c->colino=176;qq_ws(c,33,qq_index(o));qq_ws(o,33,qq_index(c));
                    if(o->actflg&128)soundset(183);
                }
            }else{
                o->mstno.b.h=0;
                if(qq_w(o,33)){tp_frameout(qq_link(o,33));qq_ws(o,33,0);}
            }
        }
        tp_patchg(o,pchg);
        break;
    }
    }
    tp_draw(o);tp_frameout_s00(o,qq_w(o,23));
}

/* ---- SASORI.C: scorpion with a tail shot --------------------------------- */
static void sasori_init_sub(sprite_status *o,sprite_status *c){
    tp_setactno(c,o->actno);c->xposi.w.h=o->xposi.w.h;c->yposi.w.h=o->yposi.w.h;c->sprpri=o->sprpri;
    qq_ws(c,23,qq_index(o));c->actflg|=4;c->sproffset=9142;
}
static void sasori_tail(sprite_status *o){
    sprite_status *t=qq_link(o,26);
    t->xposi.w.h=o->xposi.w.h+qq_w(o,27);t->yposi.w.h=o->yposi.w.h-16;
}
static void sasori_act(sprite_status *o){
    static const uint8_t pchg00[]={29,0,1,255},tama00[]={1,0,1,255};
    static const uint8_t *const pchg[]={pchg00},*const pchg_tama[]={tama00};
    if(o->userflag.b.l){
        if(qq_link(o,23)->actno!=SCD_OBJ_R5_SASORI){tp_frameout(o);return;}
        if(!(o->userflag.b.l&128)){tp_draw(o);return;}
        o->xposi.l+=qq_l(o,12);tp_patchg(o,pchg_tama);tp_draw(o);tp_frameout_s(o);return;
    }
    if(qq_enemy_suicide(o))return;
    switch(o->r_no0){
    case 0:
        o->r_no0+=2;o->sprpri=3;o->sprhs=o->sprhsize=24;o->sprvsize=12;o->colino=49;
        qq_ws(o,23,o->xposi.w.h);qq_ls(o,12,-65536);qq_ws(o,27,3);
        if(o->userflag.b.h){qq_ls(o,12,-32768);qq_ws(o,27,7);}
        o->actflg|=4;o->sproffset=9142;break;
    case 2:{
        ++o->yposi.w.h;short d1=emycol_d(o);
        if(d1<0){
            sprite_status *c;
            o->yposi.w.h+=d1;o->r_no0+=2;
            if(tp_actwkchk2(o,&c)){tp_frameout(o);return;}
            qq_ws(o,26,qq_index(c));c->userflag.b.l=1;c->sprhs=c->sprhsize=24;c->sprvsize=16;
            c->patno=o->userflag.b.h;sasori_init_sub(o,c);--c->sprpri;
        }
        break;
    }
    case 4:{
        o->xposi.l+=qq_l(o,12);
        short d0=o->xposi.w.h-qq_w(o,23);if(d0<0)d0=-d0;
        short d1;
        if(d0<80 && (unsigned short)((d1=emycol_d(o))+7)<14){
            o->yposi.w.h+=d1;sasori_tail(o);
            sprite_status *p=&actwk[0];
            if((unsigned short)(p->yposi.w.h-o->yposi.w.h+40)>=80)break;
            d0=p->xposi.w.h-o->xposi.w.h;
            if((unsigned short)(d0+80)>=160)break;
            o->r_no0+=2;
            if((d0<0)==(qq_l(o,12)<0))break;
        }
        o->xposi.l-=qq_l(o,12);qq_ls(o,12,-qq_l(o,12));qq_ws(o,27,-qq_w(o,27));
        sprite_status *t=qq_link(o,26);
        o->actflg^=1;t->actflg^=1;o->cddat^=1;t->cddat^=1;
        break;
    }
    case 6:
        o->r_no0+=2;qq_ws(o,28,30);sasori_tail(o);
        /* fall through: body_waita calls body_waita1 */
    case 8:
        if(!qq_ws(o,28,qq_w(o,28)-1)){
            sprite_status *t=qq_link(o,26);
            o->r_no0+=2;t->yposi.w.h-=5;t->xposi.w.h+=qq_l(o,12)>=0?-5:5;
        }
        break;
    case 10:
        o->r_no0+=2;qq_ws(o,28,10);
        /* fall through */
    case 12:
        if(!qq_ws(o,28,qq_w(o,28)-1)){
            sprite_status *c;
            o->r_no0+=2;
            if(!o->userflag.b.h && !tp_actwkchk(&c)){
                c->userflag.b.l=-1;c->sprhs=c->sprhsize=16;c->sprvsize=16;c->colino=178;
                sasori_init_sub(o,c);c->yposi.w.h-=24;
                short d0=-4;int d1=-196608;
                if(qq_l(o,12)>=0){d0=-d0;d1=-d1;}
                c->xposi.w.h+=d0;qq_ls(c,12,d1);
                if(o->actflg&128)soundset(160);
            }
        }
        break;
    case 14:
        o->r_no0+=2;qq_ws(o,28,30);
        /* fall through */
    case 16:
        if(!qq_ws(o,28,qq_w(o,28)-1)){
            sprite_status *t=qq_link(o,26);
            o->r_no0+=2;t->yposi.w.h+=5;t->xposi.w.h-=qq_l(o,12)>=0?-5:5;
        }
        break;
    case 18:
        o->r_no0+=2;qq_ws(o,28,30);
        /* fall through */
    case 20:
        if(!qq_ws(o,28,qq_w(o,28)-1))o->r_no0=4;
        break;
    }
    tp_patchg(o,pchg);tp_draw(o);tp_frameout_s00(o,qq_w(o,23));
}

/* ---- KEMUSI.C: caterpillar of a head and three segments ------------------ */
static void kemusi_com(sprite_status *o,sprite_status *c){
    c->r_no0=2;c->actflg|=4;c->sprpri=3;c->sprhs=c->sprhsize=8;c->sproffset=9214;qq_ws(c,28,o->xposi.w.h);
}
static void kemusi_move1(sprite_status *o);
static void kemusi_step_x(sprite_status *o){if(!(o->actflg&1))--o->xposi.w.h;else ++o->xposi.w.h;}
static void kemusi_move(sprite_status *o){
    o->r_no0+=2;qq_ws(o,23,qq_w(o,23)^3);qq_ws(o,25,qq_w(o,24));qq_ws(o,27,qq_w(o,26));
    if(!o->userflag.b.l)o->patno^=1;
    kemusi_move1(o);
}
static void kemusi_move1(sprite_status *o){
    if(!qq_ws(o,27,qq_w(o,27)-qq_w(o,23))){
        qq_ws(o,27,qq_w(o,26));kemusi_step_x(o);
        short d0=qq_w(o,28)-o->xposi.w.h;if(d0<0)d0=-d0;
        if(d0>=80){o->actflg^=1;o->cddat^=1;kemusi_step_x(o);kemusi_move1(o);return;}
        d0=emycol_d(o);
        if(d0+7>=14){o->actflg^=1;o->cddat^=1;kemusi_step_x(o);kemusi_move1(o);return;}
        o->yposi.w.h+=d0;
    }
    if(!qq_ws(o,25,qq_w(o,25)-1))o->r_no0-=2;
}
static void kemusi_act(sprite_status *o){
    if(!o->userflag.b.l && qq_enemy_suicide(o))return;
    if(o->r_no0 && (qq_link(o,31)->actno!=SCD_OBJ_R5_KEMUSI || qq_link(o,32)->actno!=SCD_OBJ_R5_KEMUSI || qq_link(o,33)->actno!=SCD_OBJ_R5_KEMUSI)){
        tp_frameout(o);return;
    }
    switch(o->r_no0){
    case 0:{
        qq_ws(o,23,3);o->patno=1;o->sprvsize=12;o->colino=51;kemusi_com(o,o);
        qq_ws(o,24,36);qq_ws(o,26,o->userflag.b.h?12:6);
        short x=o->xposi.w.h;unsigned char pat,vs,col;
        if(!o->userflag.b.h){pat=2;vs=11;col=180;}else{pat=3;vs=7;col=51;}
        for(short n=2,w=31;n>=0;--n,++w){
            sprite_status *c;
            if(tp_actwkchk2(o,&c)){tp_frameout(o);return;}
            qq_ws(o,w,qq_index(c));qq_ws(c,23,n);x+=12;c->xposi.w.h=x;c->patno=pat;c->sprvsize=vs;c->colino=col;
            c->userflag.b.h=o->userflag.b.h;c->yposi.w.h=o->yposi.w.h;
            qq_ws(c,24,qq_w(o,24));qq_ws(c,26,qq_w(o,26));c->userflag.b.l=-1;tp_setactno(c,o->actno);kemusi_com(o,c);
        }
        sprite_status *a=qq_link(o,31),*b=qq_link(o,32),*d=qq_link(o,33);
        unsigned io=qq_index(o),ia=qq_index(a),ib=qq_index(b),id=qq_index(d);
        qq_ws(a,31,io);qq_ws(a,32,ib);qq_ws(a,33,id);
        qq_ws(b,31,io);qq_ws(b,32,ia);qq_ws(b,33,id);
        qq_ws(d,31,io);qq_ws(d,32,ia);qq_ws(d,33,ib);
        break;
    }
    case 2:{
        ++o->yposi.w.h;short d1=emycol_d(o);
        if(d1<0){
            o->yposi.w.h+=d1;o->r_no0+=2;
            sprite_status *s=o->userflag.b.l?qq_link(o,31):o;
            qq_ws(s,29,qq_w(s,29)+1);
        }
        break;
    }
    case 4:
        if(!o->userflag.b.l && qq_w(o,29)==4){
            o->r_no0+=2;qq_link(o,31)->r_no0+=2;qq_link(o,32)->r_no0+=2;qq_link(o,33)->r_no0+=2;
            kemusi_move(o);
        }
        break;
    case 6:kemusi_move(o);break;
    case 8:kemusi_move1(o);break;
    }
    tp_draw(o);
    if(!o->userflag.b.l)tp_frameout_s00(o,qq_w(o,28));
}

/* ---- KUMO.C: spider that hops and shoots webs ---------------------------- */
static void kumo_jump1(sprite_status *o){
    qq_ls(o,14,qq_l(o,14)+16384);o->yposi.l+=qq_l(o,14);
    short d1=emycol_d(o);
    if(d1<0){o->yposi.w.h+=d1;o->r_no0+=2;o->patno=1;o->yposi.w.h+=8;}
}
static void kumo_act(sprite_status *o){
    static const uint8_t e00[]={7,1,2,255},b00[]={15,1,2,255},tama00[]={2,0,1,255};
    static const uint8_t *const pchg_e[]={e00},*const pchg_b[]={b00},*const pchg_tama[]={tama00};
    sprite_status *p=&actwk[0];
    if(o->userflag.b.h&128){
        if(!qq_w(o,23)){
            if(!o->colicnt || p->r_no0==4 || p->r_no0==6 || qq_w(p,26)){
                o->colicnt=0;
                o->xposi.l+=qq_l(o,14);tp_patchg(o,pchg_tama);tp_draw(o);tp_frameout_s(o);return;
            }
            o->colicnt=0;qq_ws(o,23,120);
        }
        if(!qq_ws(o,23,qq_w(o,23)-1)){tp_frameout(o);return;}
        o->xposi.w.h=p->xposi.w.h;o->yposi.w.h=p->yposi.w.h;p->xspeed.w=0;p->mspeed.w=0;
        tp_patchg(o,pchg_tama);tp_draw(o);tp_frameout_s(o);return;
    }
    if(qq_enemy_suicide(o))return;
    switch(o->r_no0){
    case 0:
        o->r_no0+=2;o->actflg|=4;o->sprpri=3;o->sproffset=9236;o->sprhs=o->sprhsize=24;o->sprvsize=24;o->colino=53;
        qq_ls(o,13,o->userflag.b.h?-327680:-524288);
        if(o->userflag.b.l){o->actflg|=1;o->cddat|=1;}
        o->r_no0+=2;kumo_jump1(o);break;
    case 2:
        o->r_no0+=2;o->patno=0;o->yposi.w.h-=8;qq_ls(o,14,qq_l(o,13));
        /* fall through */
    case 4:kumo_jump1(o);break;
    case 6:
        o->r_no0+=2;o->colino=54;qq_ws(o,23,180);
        /* fall through */
    case 8:
        /* kumo_check: retail R52B compares (dy + 80) and (dx + 80) unsigned
           (subi/bcc), so only |d| < 80 counts; PC KUMO.C reads them signed. */
        if(!o->userflag.b.h && (unsigned short)(p->yposi.w.h-o->yposi.w.h+80)<160){
            short d0=p->xposi.w.h-o->xposi.w.h;
            if((unsigned short)(d0+80)<160 && (d0<0)==!(o->actflg&1)){
                o->actflg^=1;o->cddat^=1;
                o->r_no0+=2;o->patno=1;qq_ws(o,23,60);break;
            }
        }
        if(!qq_ws(o,23,qq_w(o,23)-1))o->r_no0-=6;
        tp_patchg(o,o->userflag.b.h?pchg_b:pchg_e);
        break;
    case 10:
        if(!qq_ws(o,23,qq_w(o,23)-1))o->r_no0+=2;
        break;
    case 12:{
        sprite_status *c;
        if(!tp_actwkchk(&c)){
            c->userflag.b.h=-1;tp_setactno(c,o->actno);c->xposi.w.h=o->xposi.w.h;c->yposi.w.h=o->yposi.w.h;
            c->actflg=o->actflg;c->sprpri=1;c->sproffset=o->sproffset;c->sprhs=c->sprhsize=12;c->sprvsize=8;c->colino=247;
            short d0=24;int d1=196608;
            if(c->actflg&1){d0=-d0;d1=-d1;}
            c->xposi.w.h+=d0;qq_ls(c,14,d1);
            if(o->actflg&128)soundset(160);
        }
        o->r_no0-=10;break;
    }
    }
    tp_draw(o);tp_frameout_s(o);
}
