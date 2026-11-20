/* Wacky Workbench gimmicks: R6/DAIR6.C, KDAI6.C, TOBIDAI6.C, BLOCK6.C,
   SEESAW6.C, PISTON6.C, TOBIRA6.C, UDBLK6.C, SW6.C, TRAP_R6.C (optbr6) and
   EGG6.C (eggz6). Line-for-line ports on the PC scratch layout; ridechk,
   hitchk and ride_on_clr are the tp_* RIDECHK port. */

/* ---- DAIR6.C: platform swinging on the game timer ----------------------- */
static short dair6_sub2(sprite_status *o){
    short sn,cs;sinset(gametimer.w&255,&sn,&cs);
    sn=(short)(sn+sn+sn+sn)>>4;o->actfree[16]++;return sn;
}
static void dair6_x(sprite_status *o,short d0){
    int32_t wk=o->xposi.l;o->xposi.w.h=d0+qq_w(o,29);
    o->xspeed.w=(short)((o->xposi.l-wk)>>8);
}
static void dair6_act(sprite_status *o){
    if(!o->r_no0){
        o->actflg|=4;o->sprpri=1;o->sproffset=17384;qq_ws(o,29,o->xposi.w.h);qq_ws(o,27,o->yposi.w.h);
        o->sprvsize=12;o->sprhsize=24;o->r_no0+=2;
    }
    if(o->r_no0==2)switch(o->userflag.b.h){
    case 0:dair6_x(o,dair6_sub2(o));tp_ridechk(o,&actwk[0]);break;
    case 1:dair6_x(o,-dair6_sub2(o));tp_ridechk(o,&actwk[0]);break;
    case 2:o->yposi.w.h=-dair6_sub2(o)+qq_w(o,27);tp_ridechk(o,&actwk[0]);break;
    case 3:o->yposi.w.h=dair6_sub2(o)+qq_w(o,27);tp_ridechk(o,&actwk[0]);break;
    }
    tp_draw(o);tp_frameout_s00(o,qq_w(o,29));
}

/* ---- KDAI6.C: moving platform with a spinning pole the player orbits ---- */
static short kdai6_sub2(sprite_status *o){
    short sn,cs;sinset(gametimer.w&255,&sn,&cs);
    sn+=sn;sn+=sn;sn>>=4;o->actfree[16]++;return sn;
}
static void kdai6_act(sprite_status *o){
    static const uint8_t k0[]={9,0,1,2,3,4,5,255};static const uint8_t *const pchg[]={k0};
    sprite_status *p=&actwk[0];
    if(!o->r_no0){
        o->actflg|=4;o->sprpri=1;o->sproffset=17258;qq_ws(o,29,o->xposi.w.h);qq_ws(o,27,o->yposi.w.h);
        o->sprvsize=12;o->sprhsize=16;o->r_no0+=2;
    }else{
        /* dai6_move */
        int32_t xs=o->xposi.l;
        switch(o->userflag.b.h){
        case 0:o->xposi.w.h=kdai6_sub2(o)+qq_w(o,29);o->xspeed.w=(short)((o->xposi.l-xs)>>8);break;
        case 1:o->xposi.w.h=-kdai6_sub2(o)+qq_w(o,29);o->xspeed.w=(short)((o->xposi.l-xs)>>8);break;
        case 2:o->yposi.w.h=-kdai6_sub2(o)+qq_w(o,27);break;
        case 3:o->yposi.w.h=kdai6_sub2(o)+qq_w(o,27);break;
        }
        tp_patchg(o,pchg);
        /* kdai6_ridechk returns ridechk's result (the PC function falls off
           its end with it in d0). */
        if(tp_ridechk(o,p)){
            p->cddat|=1;p->actflg=(p->actflg&252)|1;
            if(!(p->actfree[2]&1)){
                p->mstno.b.h=45;p->actfree[1]=0;short d0=p->xposi.w.h-o->xposi.w.h;
                if(d0<0){d0=-d0;p->actfree[1]=128;}
                p->actfree[15]=(uint8_t)d0;
            }
            p->actfree[2]|=1;
            if(p->r_no0<6){
                /* kaiten_play */
                static const uint8_t tbl[16]={0,0,0,1,1,2,2,2,3,3,3,4,4,5,5,5};
                short sn,cs;p->actfree[1]+=4;sinset(p->actfree[1],&sn,&cs);
                int32_t l=(int32_t)(uint16_t)p->actfree[15]*cs;l>>=8;
                p->xposi.w.h=o->xposi.w.h+(short)l;
                uint8_t d1=p->actfree[1];p->patcnt=tbl[(d1&240)>>4];
                if(!(d1&63))p->actfree[15]++;
                swdata.w=swdata1.w;if(p->actno!=1)swdata.w=swdata2.w;
                /* k_move */
                if(p->xposi.w.h-o->xposi.w.h<0){
                    if(swdata.b.h&4)p->actfree[15]++;
                    else if(swdata.b.h&8){p->actfree[15]--;if((int8_t)p->actfree[15]<0)p->actfree[15]=0;}
                }else{
                    if(swdata.b.h&8)p->actfree[15]++;
                    else if(swdata.b.h&4){p->actfree[15]--;if((int8_t)p->actfree[15]<0)p->actfree[15]=0;}
                }
                /* jumpchk_d */
                if(swdata.b.l&112){
                    p->actfree[2]=0;
                    sinset((uint8_t)(p->direc.b.h-64),&sn,&cs);
                    p->xspeed.w+=(short)((cs*1664)>>8);p->yspeed.w+=(short)((sn*1664)>>8);
                    p->cddat=(p->cddat|2)&223;p->actfree[18]=1;p->actfree[14]=0;
                    if(chibi_flag){p->sprvsize=10;p->sprhs=5;}else{p->sprvsize=19;p->sprhs=9;}
                    if(p->cddat&4)p->cddat|=16;
                    else{
                        if(chibi_flag){p->sprvsize=10;p->sprhs=5;}else{p->sprvsize=14;p->sprhs=7;p->yposi.w.h+=5;}
                        p->cddat|=4;p->mstno.b.h=2;
                    }
                }
            }
        }
    }
    tp_draw(o);tp_frameout_s00(o,qq_w(o,29));
}

/* ---- TOBIDAI6.C: spring floor launched by the flashing-floor cycle ------ */
/* COL6A/B clchgcnt[3] (src/background_r6.c scd_r6_palette_count(3)); the
   weak default keeps host tools without the stage palette linking. */
__attribute__((weak)) unsigned scd_r6_palette_count(unsigned script){(void)script;return 0;}
__attribute__((weak)) unsigned scd_r6_sparks_active(void){return 0;}
static int ww_yuka_chk(void){
    unsigned tf=qq_time_flag();
    if(tf<2){unsigned char d0=60;if(tf)d0+=30;if((unsigned char)scd_r6_palette_count(3)==d0)return -1;}
    return 0;
}
static void ww_yuka_ridechk(sprite_status *o){
    sprite_status *p=&actwk[0];short d0=p->yspeed.w;
    if(d0<0 && -d0>1536)return;
    o->actfree[4]=o->yspeed.w?4:0;o->sprvsize+=o->actfree[4];
    /* chk */
    qq_ws(o,26,p->yspeed.w);
    if((p->cddat&8) && !(p->cddat&2))p->yspeed.w=0;
    if(tp_ride_on_chk(o,p)){
        if(p->r_no0>=6)p->yspeed.w=0;
        else{p->yposi.l=o->yposi.l;p->yposi.w.h-=(short)p->sprvsize+16;p->yspeed.w=o->yspeed.w>=0?0:o->yspeed.w;}
    }else p->yspeed.w=qq_w(o,26);
    o->sprvsize-=o->actfree[4];
}
static void tobidai6_speedset(sprite_status *o){
    short d0=o->yspeed.w+qq_w(o,33);if(d0>=1536)d0=1536;
    o->yspeed.w=d0;o->yposi.l+=d0<<8;
}
static void tobidai6_act(sprite_status *o){
    switch(o->r_no0){
    case 0:o->r_no0+=2;o->actflg|=4;o->sprpri=3;o->sproffset=17384;o->sprvsize=16;o->sprhsize=32;/* fall through */
    case 2:
        if(!ww_yuka_chk()){o->yspeed.w=-1536;qq_ws(o,33,16);o->r_no0+=2;}
        ww_yuka_ridechk(o);break;
    case 4:{
        tobidai6_speedset(o);
        if(emycol_u(o)<0)o->yspeed.w=0;
        if(emycol_d(o)<0){
            if(!ww_yuka_chk()){
                o->yspeed.w=-1536;qq_ws(o,33,16);
                /* Retail ObjBouncePlatform_Bounced returns to Solid even when
                   the platform is off screen; PC TOBIDAI6.C falls through to
                   its weak landed bounce in that case. */
                if(o->actflg&128)soundset(180);
                ww_yuka_ridechk(o);break;
            }
            o->yspeed.w=-384;qq_ws(o,33,16);o->r_no0+=2;
        }
        ww_yuka_ridechk(o);break;
    }
    case 6:
        tobidai6_speedset(o);
        if(o->yspeed.w>=0 && emycol_d(o)<0){o->yspeed.w=0;qq_ws(o,33,0);o->r_no0-=4;}
        ww_yuka_ridechk(o);break;
    }
    tp_draw(o);tp_frameout_s(o);
}

/* ---- BLOCK6.C: a block that splits into a train of sliding blocks ------- */
/* The parent spawns slaves (userflag.b.h -1) that walk one direction list
   (tbl0[subtype][step]) entry each: 0 up, 1 right, 2 down, 3 left, -1 ends.
   The PC keeps each list pointer in ((char**)o)[12]; here it is an offset
   into block6_pool kept per actor in ww_block_list (host snapshots save it). */
static const signed char block6_pool[]={0,0,0,-1,1,1,1,-1,2,2,2,-1,3,3,3,-1,0,0,1,-1,1,0,1,-1,2,2,1,-1,3,3,3,-1,0,0,-1,2,2,-1,1,1,0,-1,2,3,3,-1,3,0,3,-1,0,1,0,-1};
static const uint8_t block6_tbl0[5][4]={{0,4,8,12},{16,20,24,28},{32,35,32,35},{12,8,4,0},{38,42,46,50}};
static int16_t ww_block_list[128];
static void block6_act(sprite_status *o);

static unsigned char block6_set_slave(sprite_status *o){
    int16_t list=ww_block_list[qq_index(o)];
    if(block6_pool[list]<0)return 1;
    sprite_status *n;
    if(tp_actwkchk(&n))return 1;
    n->actflg=o->actflg;n->sproffset=o->sproffset;n->xposi.l=o->xposi.l;n->yposi.l=o->yposi.l;
    n->xspeed.w=o->xspeed.w;n->yspeed.w=o->yspeed.w;n->mspeed.w=o->mspeed.w;n->sprhsize=o->sprhsize;n->sprvsize=o->sprvsize;
    n->sprhs=o->sprhs;n->sprpri=(char)(o->sprpri+1);n->patno=o->patno;n->mstno.w=o->mstno.w;n->patcnt=o->patcnt;n->pattim=o->pattim;
    n->pattimm=o->pattimm;n->colino=o->colino;n->colicnt=o->colicnt;n->cddat=o->cddat;n->cdsts=o->cdsts;n->r_no0=0;n->r_no1=o->r_no1;
    n->direc.w=o->direc.w;n->userflag.w=o->userflag.w;qq_ws(n,23,qq_w(o,23));n->userflag.b.h=-1;qq_ws(n,29,qq_index(o));
    ww_block_list[qq_index(n)]=list+1;tp_setactno(n,o->actno);
    return 0;
}
static void block6_act(sprite_status *o){
    sprite_status *p=&actwk[0];
    if((int8_t)o->userflag.b.h<0){
        sprite_status *m=&actwk[(uint16_t)qq_w(o,23)];
        if(m->actno!=SCD_OBJ_R6_BLOCK6 || o->userflag.b.l!=m->userflag.b.l){tp_frameout(o);return;}
        switch(o->r_no0){
        case 0:{
            o->r_no0+=2;qq_ws(o,26,63);qq_ls(o,15,0);qq_ls(o,16,0);
            switch(block6_pool[ww_block_list[qq_index(o)]-1]){
            case 0:qq_ls(o,16,-32768);break;
            case 1:qq_ls(o,15,32768);break;
            case 2:qq_ls(o,16,32768);break;
            case 3:qq_ls(o,15,-32768);break;
            }
            if(m->userflag.b.h==2){short v=qq_l(o,16)>=0?1:-1;qq_ws(o,28,v);o->yspeed.w=v;}
        }   /* fall through */
        case 2:o->xposi.l+=qq_l(o,15);o->yposi.l+=qq_l(o,16);if(qq_ws(o,26,qq_w(o,26)-1)<0)o->r_no0+=2;break;
        /* Snake Blocks/Main.asm StartWait and StartWait2 fall through to
           Wait/Wait2, so the new timer loses one tick immediately. */
        case 4:o->r_no0+=2;o->yspeed.w=0;qq_ws(o,26,m->userflag.b.h!=2?30:0);
            /* fall through */
        case 6:
            if(qq_ws(o,26,qq_w(o,26)-1)>=0)break;
            o->r_no0+=2;
            if(!block6_set_slave(o))break;
            o->r_no0+=2;m->actfree[10]=255;break;
        case 8:break;
        case 10:o->r_no0+=2;qq_ws(o,26,63);o->yspeed.w=-qq_w(o,28);
            /* Snake Blocks/Main.asm StartMoveBack falls through to MoveBack. */
            /* fall through */
        case 12:o->xposi.l-=qq_l(o,15);o->yposi.l-=qq_l(o,16);if(qq_ws(o,26,qq_w(o,26)-1)<0)o->r_no0+=2;break;
        case 14:o->r_no0+=2;o->yspeed.w=0;qq_ws(o,26,m->userflag.b.h!=2?30:0);
            /* fall through */
        case 16:{
            if(qq_ws(o,26,qq_w(o,26)-1)>=0)break;
            sprite_status *c=&actwk[(uint16_t)qq_w(o,29)];
            if((int8_t)c->userflag.b.h<0)c->r_no0+=2;
            o->r_no0+=2;break;
        }
        case 18:
            if(tp_hitchk(o,p))tp_ride_on_clr(o,p);
            tp_frameout(o);return;
        }
        tp_hitchk(o,p);tp_draw(o);return;
    }
    if(!o->r_no0){
        o->r_no0+=2;o->actflg|=4;o->sprpri=1;o->sprhs=o->sprhsize=o->sprvsize=16;
        qq_ws(o,23,qq_index(o));o->actfree[10]=255;qq_ws(o,27,0);
        /* Snake Blocks/Main.asm Main_Init falls through to Main. */
    }
    if(o->actfree[10]){
        o->actfree[10]=0;
        ww_block_list[qq_index(o)]=block6_tbl0[o->userflag.b.h][(uint16_t)qq_w(o,27)/2];
        if((uint16_t)qq_ws(o,27,qq_w(o,27)+2)>=8)qq_ws(o,27,0);
        /* The PC still runs hitchk on the cleared actor. */
        if(block6_set_slave(o)){tp_frameout(o);tp_hitchk(o,p);return;}
    }
    tp_hitchk(o,p);tp_draw(o);tp_frameout_s(o);
}

/* ---- SEESAW6.C: seesaw with two end plates ------------------------------ */
/* The plates are slaves (userflag.b.h -1) the seesaw moves and draws; they
   only check that their seesaw still exists. [23] is the up plate, [24] the
   down one. The seesaw clears the plates' drawn flag at its update since
   only its actionsub calls list them. */
static const uint8_t seesaw6_p0[]={2,0,1,255};
static const uint8_t seesaw6_p1[]={2,1,2,3,255};
static const uint8_t seesaw6_p2[]={2,2,3,255};
static const uint8_t seesaw6_p3[]={2,4,5,255};
static const uint8_t seesaw6_p4[]={2,4,5,6,7,255};
static const uint8_t seesaw6_p5[]={2,6,7,255};
static const uint8_t *const seesaw6_pchg[]={seesaw6_p0,seesaw6_p1,seesaw6_p2,seesaw6_p3,seesaw6_p4,seesaw6_p5};
static void seesaw6_draw(sprite_status *s){tp_draw(s);}
static int seesaw6_slave(sprite_status *o,sprite_status *s,int dx,int dy){
    s->actflg=o->actflg;s->sprpri=o->sprpri;s->sproffset=o->sproffset;
    s->xposi.w.h=o->xposi.w.h+dx;s->yposi.w.h=o->yposi.w.h+dy;s->userflag.b.h=-1;s->sprhs=s->sprhsize=16;s->sprvsize=8;s->patno=9;
    qq_ws(s,23,qq_index(o));qq_ws(o,25,120);tp_setactno(s,o->actno);return 0;
}
static void seesaw6_act(sprite_status *o){
    sprite_status *p=&actwk[0];
    if(o->userflag.b.h){
        if(actwk[(uint16_t)qq_w(o,23)].actno!=SCD_OBJ_R6_SEESAW6)tp_frameout(o);
        return;
    }
    for(unsigned n=23;n<=24;n++){unsigned k=(uint16_t)qq_w(o,n);if(k && k<=SCD_OBJECT_CAPACITY && pool[k-1].type==SCD_OBJ_R6_SEESAW6 && actwk[k].userflag.b.h)pool[k-1].sink=0;}
    switch(o->r_no0){
    case 0:{
        o->r_no0+=2;o->actflg|=4;o->sprpri=3;o->sprhs=o->sprhsize=o->sprvsize=24;o->sproffset=952;
        sprite_status *s;
        if(tp_actwkchk(&s)){tp_frameout(o);return;}
        seesaw6_slave(o,s,-40,-24);qq_ws(o,23,qq_index(s));
        if(tp_actwkchk(&s)){tp_frameout(o);return;}
        seesaw6_slave(o,s,40,24);qq_ws(o,24,qq_index(s));s->actflg|=1;s->cddat|=1;
        break;
    }
    case 2:{
        if(!o->yspeed.w){
            /* m_stay */
            if(qq_w(o,25)>=0){
                qq_ws(o,25,qq_w(o,25)-1);
                if(qq_w(o,25)<0){o->yspeed.w=256;o->mstno.b.h++;}
                else if(qq_w(o,25)==60)o->mstno.b.h++;
            }
        }else{
            /* m_fall */
            sprite_status *su=&actwk[(uint16_t)qq_w(o,23)],*sd=&actwk[(uint16_t)qq_w(o,24)];
            short v=(signed char)o->yspeed.b.h;
            o->yposi.w.h+=v;su->yposi.w.h+=v;sd->yposi.w.h+=v;
            short d0=sd->sprhsize;if(sd->xposi.w.h>=o->xposi.w.h)d0=-d0;
            d0+=o->xposi.w.h;
            short d1=emycol_d2(sd,d0);
            if(d1<=0){o->yposi.w.h+=d1;su->yposi.w.h+=d1;sd->yposi.w.h+=d1;o->yspeed.w=0;}
        }
        sprite_status *sd=&actwk[(uint16_t)qq_w(o,24)];tp_ridechk(sd,p);seesaw6_draw(sd);
        sprite_status *su=&actwk[(uint16_t)qq_w(o,23)];
        su->actfree[21]=tp_ridechk(su,p)?255:0;seesaw6_draw(su);
        if(!su->actfree[21])tp_patchg(o,seesaw6_pchg);
        else{o->r_no0=4;qq_ws(o,25,3);o->patno=8;}
        break;
    }
    case 4:{
        sprite_status *sd=&actwk[(uint16_t)qq_w(o,24)];
        sd->yposi.w.h-=24;o->yposi.w.h-=12;
        if(qq_ws(o,25,qq_w(o,25)-1)<0){
            o->r_no0=2;o->yspeed.w=0;qq_ws(o,25,120);
            short d=qq_w(o,24);qq_ws(o,24,qq_w(o,23));qq_ws(o,23,d);
            o->mstno.b.h=o->mstno.b.h>2?0:3;o->mstno.b.l=-1;
        }
        seesaw6_draw(sd);seesaw6_draw(&actwk[(uint16_t)qq_w(o,23)]);
        break;
    }
    }
    tp_draw(o);tp_frameout_s(o);
}

/* ---- PISTON6.C: piston platform with two solid side walls ---------------- */
/* The side walls are children of the same type (userflag.b.h -1) following
   the piston by ((short*)o)[28]. */
static void piston6_act(sprite_status *o){
    sprite_status *p=&actwk[0];
    if((int8_t)o->userflag.b.h<0){
        sprite_status *m=&actwk[(uint16_t)qq_w(o,28)];
        if(m->actno!=SCD_OBJ_R6_PISTON6){tp_frameout(o);return;}
        o->yposi.w.h=m->yposi.w.h;tp_hitchk(o,p);tp_draw(o);return;
    }
    if(!o->r_no0){
        o->r_no0+=2;o->actflg|=4;o->sproffset=832;o->sprvsize=40;o->sprhsize=32;qq_ws(o,29,o->xposi.w.h);qq_ws(o,27,o->yposi.w.h);
        /* Retail ObjPiston_Init allocates the left wall first. */
        for(int d=-32;d<=32;d+=64){
            sprite_status *a;
            if(tp_actwkchk(&a))continue;
            qq_ws(a,28,qq_index(o));a->userflag.b.h=-1;a->xposi.w.h=o->xposi.w.h+d;a->yposi.w.h=o->yposi.w.h;
            a->actflg|=4;a->sprvsize=40;a->patno=1;tp_setactno(a,SCD_OBJ_R6_PISTON6);
        }
    }
    /* piston6_sub */
    if(!o->actfree[16] || !--o->actfree[16]){
        if(o->actfree[18]){
            /* Retail subq.b/bcc resets only when zero underflows. */
            if(o->actfree[17]--==0){o->actfree[17]=o->actfree[18]=0;o->actfree[16]=60;}
        }else{
            o->actfree[17]+=8;
            if(o->actfree[17]>=80){o->actfree[17]=80;o->actfree[18]=1;o->actfree[16]=60;}
        }
    }
    o->yposi.w.h=-(short)o->actfree[17]+qq_w(o,27);
    if((!o->actfree[18] || o->actfree[16]) && o->actfree[17]>=33)tp_ride_on_clr(o,p);
    else tp_ridechk(o,p);
    tp_draw(o);tp_frameout_s(o);
}

/* ---- SW6.C: floor switch ------------------------------------------------- */
/* ((short*)o)[33] reads actfree[20] | actfree[21]<<8 (this update's and the
   last update's press): 255 on a press, 0xFF00 on a release. */
extern unsigned char bchg(unsigned char,unsigned char);
static void sw6_act(sprite_status *o){
    if(!o->r_no0){
        o->r_no0+=2;o->actflg|=4;o->sprpri=1;o->sprhs=o->sprhsize=16;o->sproffset=922;o->sprvsize=8;
        o->actfree[18]=o->userflag.b.h;qq_ws(o,33,0);
    }
    unsigned char n=o->actfree[18];
    o->actfree[21]=o->actfree[20];
    if(tp_hitchk(o,&actwk[0])){o->actfree[20]=255;switchflag[n]|=128;switchflag[n]|=64;}
    else{o->actfree[20]=0;switchflag[n]&=127;}
    if((uint16_t)qq_w(o,33)==255){
        if(o->actflg&128)soundset(191);
        switchflag[n]=bchg(5,switchflag[n]);actwk[0].yposi.w.h+=8;o->yposi.w.h+=4;o->patno++;o->sprvsize-=4;
    }
    if((uint16_t)qq_w(o,33)==65280){actwk[0].yposi.w.h-=8;o->yposi.w.h-=4;o->patno--;o->sprvsize+=4;}
    tp_draw(o);tp_frameout_s(o);
}

/* ---- TOBIRA6.C: door opened by a switch (switchflag[subtype & 15]) ------- */
/* Act 3 uses the wide door (stageno.b.l 2 = objects_act 2). actfree[16] is
   the opening height, actfree[18] set while closing. */
static void tobira6_cnt(sprite_status *o){
    if(o->actfree[18]){o->actfree[16]-=4;if((signed char)o->actfree[16]<0)o->actfree[16]=0;}
    else{o->actfree[16]+=4;if(o->actfree[16]>=64)o->actfree[16]=64;}
    o->yposi.w.h=-(short)o->actfree[16]+qq_w(o,27);
}
static void tobira6_move(sprite_status *o){
    if(switchflag[o->actfree[6]]&128)o->actfree[18]=0;
    qq_ws(o,30,actwk[0].xposi.w.h);qq_ws(o,33,actwk[0].yposi.w.h);
    tobira6_cnt(o);tp_ride_on_chk(o,&actwk[0]);
    if(o->actfree[16]==64)o->r_no0+=2;
}
static void tobira6_act(sprite_status *o){
    switch(o->r_no0){
    case 0:
        o->r_no0+=2;o->actflg|=4;o->sprpri=3;qq_ws(o,27,o->yposi.w.h);o->sproffset=928;o->sprvsize=32;o->sprhsize=8;
        if(objects_act==2){o->sproffset=816;o->sprhsize=32;o->patno=1;}
        o->actfree[6]=o->userflag.b.h&15;o->actfree[18]=255;
        tobira6_move(o);break;
    case 2:tobira6_move(o);break;
    case 4:{
        sprite_status *p=&actwk[0];short d0=o->xposi.w.h-qq_w(o,30);
        if(d0<0){d0=p->sprhs+p->xposi.w.h-o->xposi.w.h;if(d0>=0)break;d0=-d0;if(d0<(short)o->sprhsize)break;}
        else{d0=-p->sprhs+p->xposi.w.h-o->xposi.w.h;if(d0<0)break;if(d0<(short)o->sprhsize)break;}
        o->r_no0+=2;break;
    }
    case 6:
        o->actfree[18]=255;tobira6_cnt(o);
        if(!o->actfree[16])o->r_no0=2;
        tp_ride_on_chk(o,&actwk[0]);break;
    }
    tp_draw(o);tp_frameout_s(o);
}

/* ---- UDBLK6.C: block that rises in front of the player, then sinks ------ */
static void udblk6_movecnt(sprite_status *o){
    static const short mv1[6]={64,8,0,64,-8,512},mv2[6]={64,-8,0,64,8,-512};
    const short *a2=o->actfree[18]?mv2:mv1;
    if(!o->actfree[16]){
        short d0=o->actfree[17]*3;
        o->actfree[16]=(char)a2[d0];qq_ws(o,33,a2[d0+1]);qq_ws(o,26,a2[d0+2]);
    }else{
        o->yposi.l+=o->yspeed.w<<8;o->yspeed.w+=qq_w(o,33);
        if(!--o->actfree[16])o->actfree[17]++;
    }
}
static void udblk6_act(sprite_status *o){
    sprite_status *p=&actwk[0];
    switch(o->r_no0){
    case 0:o->r_no0+=2;o->actflg|=4;o->sprpri=3;o->sproffset=17640;o->sprvsize=80;o->sprhsize=48;qq_ws(o,27,o->yposi.w.h);/* fall through */
    case 2:{
        short d0=o->yposi.w.h-p->yposi.w.h;if(d0<0)d0=-d0;
        if(d0<192){d0=o->xposi.w.h-p->xposi.w.h;if(d0>=0 && d0<136){o->actfree[18]=0;qq_ws(o,31,0);o->r_no0+=2;}}
        tp_ride_on_chk(o,p);break;
    }
    case 4:o->actfree[18]=0;udblk6_movecnt(o);if(o->actfree[17]==2)o->r_no0+=2;tp_ride_on_chk(o,p);break;
    case 6:{
        short d0=o->yposi.w.h-p->yposi.w.h;if(d0<0)d0=-d0;
        if(d0<192){d0=p->xposi.w.h-o->xposi.w.h;if(d0>=136){qq_ws(o,31,0);o->r_no0+=2;}}
        tp_ride_on_chk(o,p);break;
    }
    case 8:o->actfree[18]=1;udblk6_movecnt(o);if(o->actfree[17]==2)o->r_no0=2;tp_ride_on_chk(o,p);break;
    }
    tp_draw(o);tp_frameout_s(o);
}

/* ---- TRAP_R6.C optbr6: shutter that opens as the player nears ------------ */
static void optbr6_ride(sprite_status *o){if(!o->patno)tp_ride_on_chk(o,&actwk[0]);}
static void optbr6_cnt(sprite_status *o){
    o->actfree[16]+=64;
    if((signed char)o->actfree[16]>=0)return;
    if(!o->actfree[18])o->patno++;
    else if(o->patno>0)o->patno--;
}
static void optbr6_act(sprite_status *o){
    sprite_status *p=&actwk[0];
    switch(o->r_no0){
    case 0:
        o->r_no0+=2;o->actflg|=4;o->sprpri=3;o->sproffset=17424;o->sprhsize=4;o->sprvsize=32;
        if(o->userflag.b.h){o->actflg|=1;o->cddat|=1;}
        /* fall through: optbr6_init calls optbr6_chk1 */
    case 2:{
        short d0=o->yposi.w.h-p->yposi.w.h;if(d0<0)d0=-d0;
        if(d0<64){
            d0=o->userflag.b.h?p->xposi.w.h-o->xposi.w.h:o->xposi.w.h-p->xposi.w.h;
            if(d0>=0 && d0<64){qq_ws(o,31,0);o->r_no0+=2;if(o->actflg&128)soundset(164);}
        }
        optbr6_ride(o);break;
    }
    case 4:o->actfree[18]=0;optbr6_cnt(o);if(o->patno==3)o->r_no0+=2;optbr6_ride(o);break;
    case 6:{
        short d0=o->yposi.w.h-p->yposi.w.h;if(d0<0)d0=-d0;
        if(d0<64){
            d0=o->userflag.b.h?o->xposi.w.h-p->xposi.w.h:p->xposi.w.h-o->xposi.w.h;
            if(d0>=64){qq_ws(o,31,0);o->r_no0+=2;soundset(164);}
        }
        optbr6_ride(o);break;
    }
    case 8:o->actfree[18]=1;optbr6_cnt(o);if(!o->patno)o->r_no0=2;optbr6_ride(o);break;
    }
    tp_draw(o);tp_frameout_s(o);
}

/* ---- EGG6.C eggz6: Eggman's machine; rolling hits break it ------------- */
/* Broken, it sets off explosions from tbl0 (frame, dx, dy), then drops the
   tbl1 bombs (children of the same type, userflag.b.h -1). The PC keeps its
   tbl0 cursor in ((char**)o)[12]; here it is an offset in ww_block_list. */
static const signed char eggz6_tbl0[]={1,0,0,5,-18,-10,10,-10,10,15,0,-10,20,-10,-10,25,13,-10,30,-10,20,35,13,-10,40,-10,10,-1},eggz6_tbl1[]={-24,-64,-8,64,8,0,24,-128,40,-128,56,64,72,64,88,-128,104,64,120,-64,-1};
/* A new actor 24 with r_no1 1 (no score), as the PC's actwkchk leaves it. */
static void ww_new_explosion(sprite_status *a,short x,short y){
    unsigned i=tp_slot(a);
    pool[i]=(slot){.origin=65535,.type=SCD_OBJ_EXPLOSION,.subtype=4,.home_x=x,.home_y=y};
    a->actno=SCD_OBJ_EXPLOSION;a->r_no1=1;a->xposi.w.h=x;a->yposi.w.h=y;
}
static void eggz6_act(sprite_status *o){
    sprite_status *p=&actwk[0];
    if(o->userflag.b.h){
        static const uint8_t b0[]={1,0,1,255};static const uint8_t *const pchg[]={b0};
        switch(o->r_no0){
        case 0:o->r_no0+=2;o->actflg|=4;o->sprpri=3;o->sprvsize=o->sprhs=o->sprhsize=6;o->colino=183;tp_lset(o,0,0);break;
        case 2:
            o->yposi.l+=tp_l(o,0);tp_lset(o,0,tp_l(o,0)+1024);
            if(o->yposi.w.h>=qq_w(o,25))o->r_no0+=2;
            tp_patchg(o,pchg);break;
        case 4:qq_explode(o);o->r_no0=0;o->r_no1=1;soundset(158);return;
        }
        tp_draw(o);return;
    }
    switch(o->r_no0){
    case 0:
        if(good_future){tp_frameout(o);return;}
        o->r_no0+=2;o->actflg|=4;o->sprpri=3;o->sprhs=o->sprhsize=20;o->sprvsize=28;o->colino=248;
        ww_block_list[qq_index(o)]=0;break;
    case 2:
        if(o->colicnt){o->colino=o->colicnt=0;o->r_no0+=2;if(tp_hitchk(o,p))tp_ride_on_clr(o,p);}
        else tp_hitchk(o,p);
        break;
    case 4:{
        int16_t at=ww_block_list[qq_index(o)];signed char d=eggz6_tbl0[at++];
        if(d<0){o->r_no0+=2;o->patno=1;o->actfree[21]=60;break;}
        if(d!=(signed char)++o->actfree[21])break;
        short x=eggz6_tbl0[at++],y=eggz6_tbl0[at++];ww_block_list[qq_index(o)]=at;
        sprite_status *a;
        if(tp_actwkchk(&a))break;
        ww_new_explosion(a,o->xposi.w.h+x,o->yposi.w.h+y);soundset(158);
        break;
    }
    case 6:if(!--o->actfree[21])o->r_no0+=2;break;
    case 8:
        for(unsigned k=0;eggz6_tbl1[k]!=-1;k+=2){
            sprite_status *a;
            if(tp_actwkchk(&a))break;
            a->userflag.b.h=-1;a->xposi.w.h=o->xposi.w.h+eggz6_tbl1[k];a->yposi.w.h=o->yposi.w.h+eggz6_tbl1[k+1]-160;
            qq_ws(a,25,o->yposi.w.h+38);tp_setactno(a,o->actno);
        }
        tp_frameout(o);return;
    }
    tp_draw(o);if(o->r_no0<=2)tp_frameout_s(o);
}
