/* Quartz Quadrant hazards: R5/IWA5.C, HARI5F.C, HARIR5.C, IWA5ROLL.C,
   KUZURE5.C and IWA5WAVE.C. Line-for-line ports on the PC scratch layout
   (objects_qq_common.inc); hitchk/ridechk/ride_on_clr are the tp_* RIDECHK
   port. Pieces and children reuse the parent type. */
static unsigned qq_time_flag(void){return current_era==0?1:current_era==1?0:2;}
/* An actor turned into actor 24 in place with r_no1 1 (no score). */
static void qq_explode(sprite_status *o){
    unsigned i=tp_slot(o);
    if(pool[i].origin!=65535)consumed[pool[i].origin]=1;
    pool[i].type=SCD_OBJ_EXPLOSION;pool[i].subtype=4;pool[i].age=0;pool[i].origin=65535;
    pool[i].state=pool[i].frame=pool[i].cooldown=0;pool[i].home_x=o->xposi.w.h;pool[i].home_y=o->yposi.w.h;
    o->actno=SCD_OBJ_EXPLOSION;
}

/* ---- IWA5.C: rock that drops on the player and bursts -------------------- */
static void iwa5_act(sprite_status *o){
    sprite_status *p=&actwk[0];
    if(o->userflag.b.h&128){
        tp_lset(o,4,tp_l(o,4)+16384);o->xposi.l+=tp_l(o,0);o->yposi.l+=tp_l(o,4);
        tp_draw(o);
        if(p->yposi.w.h-o->yposi.w.h<=-224)tp_frameout(o);
        return;
    }
    switch(o->r_no0){
    case 0:
        o->r_no0+=2;o->actflg|=4;o->patno=0;o->sprpri=3;o->sprhs=o->sprhsize=o->sprvsize=16;o->sproffset=17202;
        /* fall through: m_init calls m_wait */
    case 2:
        if(o->userflag.b.h && (unsigned short)(p->yposi.w.h-o->yposi.w.h-8)<88 && (unsigned short)(p->xposi.w.h-o->xposi.w.h+8)<16){
            o->r_no0+=2;o->colino=248;
        }
        tp_hitchk(o,p);
        break;
    case 4:{
        static const struct{short dx,dy;int sx,sy;}tbl0[4]={{-8,-8,-65536,-262144},{8,-8,65536,-262144},{-8,8,-131072,-196608},{8,8,131072,-196608}};
        if(!o->colicnt){
            o->yposi.l+=tp_l(o,4);tp_lset(o,4,tp_l(o,4)+16384);
            if(emycol_d(o)>=0){
                if((short)(p->yposi.w.h-o->yposi.w.h)<=-224){tp_frameout(o);return;}
                break;
            }
        }
        for(unsigned a=0;a<4;a++){
            sprite_status *c;
            if(tp_actwkchk(&c))break;
            c->sprpri=3;c->userflag.b.h=-1;c->sprhs=c->sprhsize=c->sprvsize=8;tp_setactno(c,o->actno);
            c->xposi.w.h=o->xposi.w.h+tbl0[a].dx;c->yposi.w.h=o->yposi.w.h+tbl0[a].dy;c->actflg=o->actflg;c->sproffset=o->sproffset;
            tp_lset(c,0,tbl0[a].sx);tp_lset(c,4,tbl0[a].sy);c->patno=4-a;
        }
        o->r_no0=0;o->r_no1=1;o->colino=0;
        if(o->actflg&128)soundset(158);
        qq_explode(o);
        return;
    }
    }
    tp_draw(o);tp_frameout_s(o);
}

/* ---- HARI5F.C: stalactite spike that falls when passed under ------------- */
static void hari5f_act(sprite_status *o){
    sprite_status *p=&actwk[0];
    switch(o->r_no0){
    case 0:{
        unsigned tf=qq_time_flag();
        o->r_no0+=2;o->actflg|=4;o->sprpri=3;o->sprhs=o->sprhsize=8;o->sprvsize=24;
        o->sproffset=tf==0?17218:tf==1?834:good_future?834:17218;
    }   /* fall through: f_init calls f_wait */
    case 2:
        if((unsigned short)(p->yposi.w.h-o->yposi.w.h-24)<104 && (unsigned short)(p->xposi.w.h-o->xposi.w.h+8)<16){
            o->r_no0+=2;o->colino=185;
        }
        break;
    case 4:{
        if(!(o->actflg&128) && o->yposi.w.h>=p->yposi.w.h){tp_frameout(o);return;}
        short d1=emycol_d3(o,o->xposi.w.h,o->yposi.w.h-(unsigned short)o->sprvsize);
        unsigned char b=255;
        if(d1>=0){b=0;if(o->actfree[21]&128){tp_frameout(o);return;}}
        o->actfree[21]=b;o->yposi.l+=tp_l(o,0);tp_lset(o,0,tp_l(o,0)+16384);
        break;
    }
    }
    tp_draw(o);tp_frameout_s(o);
}

/* ---- HARIR5.C: spikes that rise and sink (bit 2), up/down or sideways ---- */
static void harir5_sub(sprite_status *o){
    if(o->actfree[16] && --o->actfree[16])return;
    if(o->actfree[18]){
        if(o->actfree[17]>=8){o->actfree[17]-=8;return;}
        o->actfree[17]=o->actfree[18]=0;o->actfree[16]=60;
    }else if((o->actfree[17]+=8)>=32){o->actfree[17]=32;o->actfree[18]=1;o->actfree[16]=60;}
}
static void harir5_act(sprite_status *o){
    static const uint8_t sztbl[12]={18,12,0, 18,12,131, 10,14,130, 10,14,130};
    sprite_status *p=&actwk[0];
    if(!o->r_no0){
        o->r_no0+=2;o->actflg|=4;o->sproffset=1099;o->sprpri=3;
        qq_ws(o,29,o->xposi.w.h);qq_ws(o,27,o->yposi.w.h);
        unsigned b=o->userflag.b.h&3;
        o->patno=b;o->sprhsize=sztbl[b*3];o->sprvsize=sztbl[b*3+1];o->colino=sztbl[b*3+2];
    }
    if(o->userflag.b.h&4){
        harir5_sub(o);
        switch(o->userflag.b.h&3){
        case 0:o->yposi.w.h=o->actfree[17]+qq_w(o,27);break;
        case 1:o->yposi.w.h=-o->actfree[17]+qq_w(o,27);break;
        case 2:o->xposi.w.h=-o->actfree[17]+qq_w(o,29);break;
        case 3:o->xposi.w.h=o->actfree[17]+qq_w(o,29);break;
        }
    }
    if(o->patno)tp_hitchk(o,p);
    else if(tp_hitchk(o,p) && (o->cddat&8) && !plpower_a && !plpower_m && p->r_no0<4 && !qq_w(p,26)){
        p->yposi.l-=(int32_t)p->yspeed.w*256;scd_objects_hurt(o->xposi.w.h);
    }
    tp_draw(o);
    if(qq_w(o,28)){
        sprite_status *r=qq_link(o,28);
        o->xposi.w.h=r->xposi.w.h+(int8_t)o->actfree[14];o->yposi.w.h=r->yposi.w.h+(int8_t)o->actfree[15];
    }
    /* The flagwork bit is cleared first: the placement reloads. */
    if((unsigned short)(((unsigned short)qq_w(o,29)&65408)-((unsigned short)(tp_scra_h()-128)&65408))>640)tp_frameout_s0(o);
}

/* ---- IWA5ROLL.C: ring of rocks rolling round a centre -------------------- */
static void iwa5roll_act(sprite_status *o){
    sprite_status *p=&actwk[0];
    if(!o->r_no0){
        static const short tbl[6]={128,1,192,1,256,1};
        unsigned tf=qq_time_flag();
        short d1=tbl[tf*2],a5=tbl[tf*2+1];
        if(o->userflag.b.h)d1=-d1;
        qq_ws(o,29,d1);
        short d3=0,d4=0;sprite_status *c=o;int first=1;
        for(short d6=3;d6>=0;--d6){
            short d5=0;
            if(!first)d3=d4;
            do{
                if(!first && tp_actwkchk(&c))goto done;
                first=0;
                qq_ws(c,23,qq_index(o));c->actflg|=4;c->r_no0=2;c->sprpri=3;c->sprhs=c->sprhsize=c->sprvsize=8;c->sproffset=17152;
                tp_setactno(c,o->actno);c->xposi.w.h=o->xposi.w.h;c->yposi.w.h=o->yposi.w.h;
                qq_ls(c,12,o->xposi.l);qq_ls(c,13,o->yposi.l);qq_ws(c,29,qq_w(o,29));qq_ws(c,28,d3);d3+=2048;
            }while(++d5<=a5);
            d4+=16384;
        }
    done:
        qq_ws(o,23,0);return;
    }
    if(qq_w(o,23) && qq_link(o,23)->actno!=SCD_OBJ_R5_IWA5ROLL){tp_frameout(o);return;}
    qq_ws(o,28,qq_w(o,28)+qq_w(o,29));
    short sn,cs;sinset(o->actfree[11],&sn,&cs);
    int l1=(int)((uint32_t)(uint16_t)cs<<16),l0=(int)((uint32_t)(uint16_t)sn<<16);
    int l5=l1/4+l1/8+qq_l(o,12),l4=l0/4+l0/8+qq_l(o,13),l3=o->xposi.l;
    o->xposi.l=l5;o->yposi.l=l4;
    o->xspeed.w=(short)((l5-l3)>>8);
    short sp=o->xspeed.w;o->xspeed.w=0;o->sprvsize=10;
    int hit=tp_hitchk(o,p)!=0;
    o->xspeed.w=sp;o->sprvsize=8;
    if(hit)tp_hitchk(o,p);
    tp_draw(o);
    if(!qq_w(o,23))tp_frameout_s00(o,qq_w(o,25));
}

/* ---- KUZURE5.C: ledge crumbling from the far end ------------------------- */
static void kuzure5_act(sprite_status *o){
    sprite_status *p=&actwk[0];
    if(o->userflag.b.l){
        switch(o->r_no0){
        case 0:o->r_no0+=2;o->sprpri=3;o->sprhs=o->sprhsize=8;o->sprvsize=8;break;
        case 2:if(qq_ws(o,23,qq_w(o,23)-1)<0)o->r_no0+=2;break;
        case 4:{
            if(!(o->actflg&128)){tp_frameout(o);return;}
            int s=qq_l(o,12)+16384;if(s>1441792)s=1441792;
            qq_ls(o,12,s);o->yposi.l+=s;break;
        }
        }
        tp_draw(o);return;
    }
    switch(o->r_no0){
    case 0:
        o->r_no0+=2;o->actflg=4;o->sprpri=3;o->sprvsize=17;
        o->sproffset=stageno.b.l!=2?17232:17312;
        o->patno=o->userflag.b.h-1;o->sprhs=o->sprhsize=o->userflag.b.h*8;
        /* fall through: main_ini calls main_check */
    case 2:
        if(tp_ridechk(o,p)){
            o->r_no0+=2;tp_noreload(o);qq_ws(o,23,8);qq_ws(o,24,p->xspeed.w>=0?8:-8);soundset(163);
        }
        tp_draw(o);tp_frameout_s(o);return;
    case 4:
        tp_ridechk(o,p);
        if(qq_ws(o,23,qq_w(o,23)-1)<0)o->r_no0+=2;
        tp_draw(o);return;
    case 6:{
        short xw=((short)(int8_t)o->userflag.b.h-1)*8;
        if(qq_w(o,24)>=0)xw=-xw;
        sprite_status *c;
        if(!tp_actwkchk(&c)){
            c->actflg=o->actflg;c->sproffset=o->sproffset;c->xposi.l=o->xposi.l;c->yposi.l=o->yposi.l;
            c->userflag.b.l=-1;tp_setactno(c,o->actno);c->yposi.w.h-=8;c->xposi.w.h+=xw;qq_ws(c,23,4);c->patno=8;
            if(!tp_actwkchk(&c)){
                c->actflg=o->actflg;c->sproffset=o->sproffset;c->xposi.l=o->xposi.l;c->yposi.l=o->yposi.l;
                c->userflag.b.l=-1;tp_setactno(c,o->actno);c->yposi.w.h+=8;c->xposi.w.h+=xw;c->patno=9;
            }
        }
        if(tp_ridechk(o,p))tp_ride_on_clr(o,p);
        if((int8_t)--o->userflag.b.h<=0){tp_frameout(o);return;}
        o->r_no0-=2;--o->patno;o->sprhs-=8;o->sprhsize-=8;qq_ws(o,23,7);o->xposi.w.h+=qq_w(o,24);
        tp_ridechk(o,p);tp_draw(o);return;
    }
    }
}

/* ---- IWA5WAVE.C: pair of rock platforms bobbing on a sine ---------------- */
static void iwa5wave_com(sprite_status *o){
    qq_ws(o,31,o->xspeed.w);o->xspeed.w=0;o->sprvsize=18;
    int ride=tp_ridechk(o,&actwk[0])!=0;
    o->xspeed.w=qq_w(o,31);o->sprvsize=16;
    if(ride)tp_ridechk(o,&actwk[0]);
    tp_draw(o);
}
static void iwa5wave_fields(sprite_status *o,short y){
    o->actflg|=4;o->r_no0=2;o->sprpri=3;o->sprhs=o->sprhsize=32;o->sprvsize=16;o->sproffset=17543;qq_ws(o,29,y);
}
static void iwa5wave_act(sprite_status *o){
    if(!o->r_no0){
        qq_ws(o,24,o->xposi.w.h);
        int l=(int)((uint32_t)(uint16_t)o->xposi.w.h<<16)-0x800000;
        tp_lset(o,4,l);tp_lset(o,8,l+0x1000000);
        short d5=o->xposi.w.h+64,d3=o->userflag.b.h?0:-32768;
        sprite_status *c=o;
        iwa5wave_fields(o,o->yposi.w.h);
        for(short d6=1;;){
            if(d6!=1){
                if(tp_actwkchk(&c))return;
                qq_ws(c,23,qq_index(o));tp_setactno(c,o->actno);tp_lset(c,4,tp_l(o,4));tp_lset(c,8,tp_l(o,8));
                c->yposi.w.h=o->yposi.w.h;iwa5wave_fields(c,o->yposi.w.h);
            }
            c->xposi.w.h=d5;d5-=128;qq_ws(c,30,d3);
            if(!d6--)break;
        }
        return;
    }
    int d0=o->xposi.l,d1=d0-32768;
    if(d1<=tp_l(o,4)){d0=tp_l(o,8);d1=d0;}
    int dx=(d1-d0)>>8;
    o->xposi.l=d1;o->xspeed.w=(unsigned short)dx;
    qq_ws(o,30,qq_w(o,30)+256);
    short sn,cs;sinset((unsigned char)(qq_w(o,30)>>8),&sn,&cs);
    /* Retail R52C $20E47A: CalcSine loads only d1's low word, so swap d1 brings
       the x step's high word (-1 while moving) into the fraction. */
    int l1=(int)((uint32_t)(uint16_t)cs<<16|(uint16_t)((uint32_t)dx>>16))>>2,l0=(l1>>1)+l1+32768;
    o->yposi.w.h=(short)((uint32_t)l0>>16)+qq_w(o,29);
    if(qq_w(o,23)){
        if(qq_link(o,23)->actno==SCD_OBJ_R5_IWA5WAVE){iwa5wave_com(o);return;}
        tp_frameout(o);return;
    }
    iwa5wave_com(o);tp_frameout_s00(o,qq_w(o,24));
}
