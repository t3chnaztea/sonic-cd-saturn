/* Metallic Madness (R8) Act 1 gimmicks and badniks: R8/DAI8.C (appearing
   platforms), NOKOGIRI.C (the extending saw and its bar), KUZURE8.C
   (crumbling ledges and their falling parts), PROPERA8.C (the propeller
   walker and its blades) and KABUTO8.C (the beetle and its horn).
   Line-for-line ports on the PC scratch layout (objects_mm_common.inc).
   Children reuse their parent's type; the original tells them apart by
   subtype (userflag.b.h < 0: DAI8, PROPERA8) or by the secondary byte
   (userflag.b.l: NOKOGIRI and KUZURE8 nonzero, KABUTO8 negative).
   Quirks kept (the original's, see build/handover/ssobjects.md):
   - When a spawn fails the originals frame the actor out and still run the
     rest of the update on the cleared actor; the ports stop instead (only
     reachable with the actor table full).
   - DAI8's pattern scripts end with 0, not a >= 250 terminator: patchg's
     end search reads past the table (the PC reads the next array). Only
     the first byte (0) matters then (pattim 1); the port and the fixture
     both terminate the scripts with 255, which gives the same pattim.
   - DAI8 act_init reads its table by subtype 0-2; other subtypes read an
     uninitialised pointer (no placement uses one).
   - NOKOGIRI's init falls into act_open: the saw moves one step and its
     timer counts once in the update it starts. */
extern short emycol_d(sprite_status*);

/* ---- DAI8.C: platforms that appear and vanish on a timer --------------- */
static const uint8_t dai8_p00[]={0,5,5,5,5,5,4,4,4,5,5,5,5,5,4,4,4,3,3,3,3,3,2,2,2,3,3,3,3,3,2,2,2,1,1,1,1,1,7,7,7,1,1,1,1,1,0,255};
static const uint8_t dai8_p01[]={0,1,1,1,1,1,7,7,7,1,1,1,1,1,2,2,2,3,3,3,3,3,2,2,2,3,3,3,3,3,4,4,4,5,5,5,5,5,4,4,
    4,5,5,5,5,5,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,
    6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,5,5,5,5,5,4,4,4,5,5,5,5,5,4,4,4,3,3,3,3,3,2,2,2,3,3,3,3,3,2,2,2,1,1,
    1,1,1,7,7,7,1,1,1,1,1,0,255};
static const uint8_t *const dai8_pchg[]={dai8_p00,dai8_p01};
static void dai8_init_sub(const sprite_status *o,sprite_status *a){
    a->actflg|=4;a->sprpri=3;a->sprhs=a->sprhsize=a->sprvsize=16;a->sproffset=920;a->patno=6;a->r_no0=2;
    mm_ws(a,25,o->xposi.w.h);mm_ws(a,26,o->yposi.w.h);
}
/* Returns 0 when the platform framed itself out. */
static int dai8_init(sprite_status *o){
    static const short tbl00[2]={60,0},tbl01[5]={60,1,60,32,0},tbl02[8]={90,2,180,32,16,270,64,32};
    unsigned s=(uint8_t)o->userflag.b.h;
    const short *t=s==1?tbl01:s==2?tbl02:tbl00;
    mm_ws(o,23,*t++);dai8_init_sub(o,o);
    short n=*t++;
    for(short k=0;k<n;k++){
        sprite_status *a;
        if(tp_actwkchk(&a)){tp_frameout(o);return 0;}
        mm_ws(a,24,(uint16_t)mm_index(o));a->userflag.b.h=-1;tp_setactno(a,o->actno);
        mm_ws(a,23,*t++);a->xposi.w.h=o->xposi.w.h+*t++;a->yposi.w.h=o->yposi.w.h+*t++;
        dai8_init_sub(o,a);
    }
    return 1;
}
static void dai8_act(sprite_status *o){
    sprite_status *p=&actwk[0];
    if((int8_t)o->userflag.b.h<0){
        const sprite_status *m=&actwk[(uint16_t)mm_w(o,24)&127];
        if(m->actno!=SCD_OBJ_R8_DAI8 || mm_w(o,25)!=mm_w(m,25) || mm_w(o,26)!=mm_w(m,26)){tp_frameout(o);return;}
    }
    switch(o->r_no0){
    case 0:if(!dai8_init(o))return;break;
    case 2:if(!mm_ws(o,23,mm_w(o,23)-1))o->r_no0+=2;break;
    case 4:tp_patchg(o,dai8_pchg);if(!o->patno){mm_ws(o,23,120);o->r_no0+=2;}break;
    case 6:
        o->actfree[21]=tp_ridechk(o,p)?255:0;
        if(mm_ws(o,23,mm_w(o,23)-1))break;
        o->mstno.w=511;o->r_no0+=2;
        if(o->actfree[21])tp_ride_on_clr(o,p);
        break;
    case 8:tp_patchg(o,dai8_pchg);if(!o->patno){mm_ws(o,23,120);o->r_no0-=2;}break;
    }
    tp_draw(o);
    if((int8_t)o->userflag.b.h>=0)tp_frameout_s00(o,mm_w(o,25));
}

/* ---- NOKOGIRI.C: the saw that slides out of the wall -------------------- */
static void nokogiri_sound(sprite_status *o){
    if(!(o->actflg&128))return;
    if(!(mm_ws(o,30,mm_w(o,30)+1)&31))soundset(177);
}
/* Returns 0 when the saw framed itself out. */
static int nokogiri_init(sprite_status *o){
    unsigned char s=(unsigned char)o->userflag.b.h;
    mm_ws(o,29,o->xposi.w.h);o->actflg|=4;o->sprpri=3;o->sproffset=17174;o->colino=169;o->sprhsize=o->sprvsize=80;
    mm_ls(o,12,65536);mm_ls(o,13,65536);
    if(s&1){mm_ls(o,12,-mm_l(o,12));o->actflg|=1;o->cddat|=1;}
    if(s&2){mm_ls(o,13,-mm_l(o,13));o->actflg|=2;o->cddat|=2;}
    mm_ws(o,23,60);o->r_no0=8;
    if(s&128){o->mstno.b.h=9;o->r_no0=4;}
    sprite_status *a;
    /* Retail nokogiri init (R83C $20E5CE) takes the bar with actwkchk
       ($207534, the first free slot from 32); NOKOGIRI.C:155 reads actwkchk2
       (retail MM3C: the bar of the saw at 865,216 is in slot 32). */
    if(tp_actwkchk(&a)){tp_frameout(o);return 0;}
    mm_ws(o,31,(uint16_t)mm_index(a));mm_ws(a,23,(uint16_t)mm_index(o));
    a->actflg=o->actflg;a->sproffset=o->sproffset;a->userflag.b.h=o->userflag.b.h;a->userflag.b.l=-1;
    tp_setactno(a,o->actno);
    a->sprpri=o->sprpri-1;a->xposi.w.h=o->xposi.w.h;a->yposi.w.h=o->yposi.w.h+1;
    if(s&128){
        short d0=80,d1=79;
        if(s&1)d0=-(d0-1);
        if(s&2)d1=-(d1-1);
        a->xposi.w.h-=d0;a->yposi.w.h-=d1;
    }else{
        if(s&1){--a->yposi.w.h;++a->xposi.w.h;}
        if(s&2){--a->yposi.w.h;--a->xposi.w.h;}
    }
    return 1;
}
static void nokogiri_act(sprite_status *o){
    static const uint8_t p0[]={1,0,1,255},p1[]={1,2,3,255},p2[]={1,4,5,255},p3[]={1,6,7,255},p4[]={1,8,9,255},
        p5[]={1,10,11,255},p6[]={1,12,13,255},p7[]={1,14,15,255},p8[]={1,16,17,255};
    static const uint8_t *const pchg[10]={p0,p1,p2,p3,p4,p5,p6,p7,p8,p8};
    if(o->userflag.b.l){
        /* bar: the arm behind the saw */
        const sprite_status *m=&actwk[(uint16_t)mm_w(o,23)&127];
        if(m->actno!=SCD_OBJ_R8_NOKOGIRI){tp_frameout(o);return;}
        if(o->r_no0){tp_draw(o);return;}
        o->r_no0+=2;o->actflg|=4;o->sprhsize=o->sprvsize=32;
        return;
    }
    switch(o->r_no0){
    case 0:if(!nokogiri_init(o))return;
        /* fall through: act_init runs act_open */
    case 2:
        if(!mm_ws(o,23,mm_w(o,23)-1)){
            ++o->mstno.b.h;mm_ws(o,23,9);
            if(!mm_ws(o,28,mm_w(o,28)-1)){o->r_no0+=2;mm_ws(o,23,60);}
        }
        o->xposi.l+=mm_l(o,12);o->yposi.l+=mm_l(o,13);nokogiri_sound(o);break;
    case 4:
        if(!mm_ws(o,23,mm_w(o,23)-1)){o->r_no0+=2;mm_ws(o,28,9);mm_ws(o,23,1);}
        nokogiri_sound(o);break;
    case 6:
        if(!mm_ws(o,23,mm_w(o,23)-1)){
            --o->mstno.b.h;mm_ws(o,23,9);
            if(!mm_ws(o,28,mm_w(o,28)-1)){o->r_no0+=2;mm_ws(o,23,60);}
        }
        o->xposi.l-=mm_l(o,12);o->yposi.l-=mm_l(o,13);nokogiri_sound(o);break;
    case 8:
        if(!mm_ws(o,23,mm_w(o,23)-1)){o->r_no0-=6;mm_ws(o,28,9);mm_ws(o,23,1);}
        nokogiri_sound(o);break;
    }
    tp_patchg(o,pchg);tp_draw(o);tp_frameout_s00(o,mm_w(o,29));
}

/* ---- KUZURE8.C: ledges that crumble from the far end ------------------- */
static void kuzure8_part(sprite_status *o,const sprite_status *m,short dy,short dx,short wait,unsigned char pat){
    o->actflg=m->actflg;o->sproffset=m->sproffset;o->xposi.w.h=m->xposi.w.h;o->yposi.w.h=m->yposi.w.h;
    o->userflag.b.l=-1;tp_setactno(o,m->actno);
    o->yposi.w.h+=dy;o->xposi.w.h+=dx;mm_ws(o,23,wait);o->patno=pat;
}
static void kuzure8_act(sprite_status *o){
    sprite_status *p=&actwk[0];
    if(o->userflag.b.l){
        /* parts */
        switch(o->r_no0){
        case 0:o->r_no0+=2;o->sprpri=3;o->sprhs=o->sprhsize=o->sprvsize=8;tp_draw(o);break;
        case 2:{short t=mm_w(o,23);mm_ws(o,23,t-1);if(t<=0)o->r_no0+=2;tp_draw(o);break;}
        case 4:{
            if(!(o->actflg&128)){tp_frameout(o);return;}
            int d=mm_l(o,12)+16384;if(d>1441792)d=1441792;
            mm_ls(o,12,d);o->yposi.l+=d;tp_draw(o);break;
        }
        }
        return;
    }
    switch(o->r_no0){
    case 0:{
        o->actflg|=4;o->sprvsize=17;o->sproffset=objects_act!=2?17624:17274;
        int8_t d0=(int8_t)o->userflag.b.h;if(d0<0)d0=(int8_t)-d0;
        int8_t d1=d0;--d0;o->patno=(uint8_t)d0;d1=(int8_t)(d1<<3);o->sprhs=o->sprhsize=(uint8_t)d1;
        d0=3;d1=2;
        if((int8_t)o->userflag.b.h<0){d0=1;d1=8;}
        o->sprpri=(uint8_t)d0;o->r_no0=(uint8_t)d1;
        break;
    }
    case 2:
        if(tp_ridechk(o,p)){
            /* cdsts = 0: the ledge no longer reloads */
            o->r_no0+=2;tp_noreload(o);mm_ws(o,23,8);mm_ws(o,24,p->xspeed.w<0?-8:8);soundset(163);
        }
        tp_draw(o);tp_frameout_s(o);break;
    case 4:
        tp_ridechk(o,p);
        if(mm_ws(o,23,mm_w(o,23)-1)<0)o->r_no0+=2;
        tp_draw(o);break;
    case 6:{
        short d3=(short)(((int)o->userflag.b.h-1)<<3);
        if(mm_w(o,24)>=0)d3=-d3;
        sprite_status *a;
        if(!tp_actwkchk(&a)){
            kuzure8_part(a,o,-8,d3,4,8);
            if(!tp_actwkchk(&a))kuzure8_part(a,o,8,d3,0,9);
        }
        if(tp_ridechk(o,p))tp_ride_on_clr(o,p);
        --o->userflag.b.h;
        if((int8_t)o->userflag.b.h<=0){tp_frameout(o);return;}
        o->r_no0-=2;--o->patno;o->sprhs-=8;o->sprhsize-=8;mm_ws(o,23,7);o->xposi.w.h+=mm_w(o,24);
        tp_ridechk(o,p);tp_draw(o);break;
    }
    case 8:tp_hitchk(o,p);tp_draw(o);tp_frameout_s(o);break;
    }
}

/* ---- PROPERA8.C: the propeller walker and its two blades --------------- */
static void propera_blade_init(sprite_status *a){a->actflg|=4;a->sproffset=874;a->sprpri=3;a->sprhs=a->sprhsize=32;a->sprvsize=28;}
static void propera_act(sprite_status *o){
    static const uint8_t p00[]={10,0,1,255},p01[]={2,0,1,2,3,4,5,255};
    static const uint8_t *const pchg[]={p00},*const pchg1[]={p01};
    if(!o->userflag.b.h){
        switch(o->r_no0){
        case 0:{
            mm_ws(o,26,o->xposi.w.h);o->r_no0+=2;o->actflg|=4;o->sprpri=4;o->sproffset=874;mm_ws(o,23,128);mm_ls(o,12,65536);
            o->sprhs=o->sprhsize=8;o->sprvsize=46;
            sprite_status *a1,*a2;
            if(tp_actwkchk2(o,&a1)){tp_frameout(o);return;}
            mm_ws(a1,33,(uint16_t)mm_index(o));a1->userflag.b.h=1;tp_setactno(a1,o->actno);a2=a1;
            if(tp_actwkchk2(o,&a1)){tp_frameout(o);return;}
            mm_ws(a1,33,(uint16_t)mm_index(o));a1->userflag.b.h=-1;tp_setactno(a1,o->actno);
            mm_ws(a1,32,-44);mm_ws(a2,32,20);a2->actflg|=2;a2->cddat|=2;
            propera_blade_init(a1);propera_blade_init(a2);mm_ws(a2,33,(uint16_t)mm_index(o));
            break;
        }
        case 2:{
            ++o->yposi.w.h;short d=emycol_d(o);
            if(d<0){o->yposi.w.h+=d;o->r_no0+=2;}
            break;
        }
        case 4:
            o->xposi.l+=mm_l(o,12);o->yposi.w.h+=emycol_d(o);
            if(!mm_ws(o,23,mm_w(o,23)-1)){mm_ls(o,12,(int)(0u-(uint32_t)mm_l(o,12)));mm_ws(o,23,128);}
            break;
        }
        tp_patchg(o,pchg);tp_draw(o);tp_frameout_s00(o,mm_w(o,26));
        return;
    }
    /* blades: r_no0 2/4 closing, 6/8 closed, 10/12 opening, 14/16 open */
    const sprite_status *m=&actwk[(uint16_t)mm_w(o,33)&127];
    if(m->actno!=SCD_OBJ_R8_PROPERA){tp_frameout(o);return;}
    switch(o->r_no0){
    case 0:
        if((int8_t)o->userflag.b.h<0){o->r_no0=10;goto open;}
        o->r_no0=2;goto close;
    case 2:close:
        o->patno=6;mm_ws(o,23,5);o->colino=0;o->r_no0+=2;
        /* fall through: b_close1 */
    case 4:
        if(mm_ws(o,23,mm_w(o,23)-1))break;
        o->r_no0+=2;
        /* fall through: b_closed */
    case 6:
        o->patno=7;mm_ws(o,23,73);o->r_no0+=2;
        /* fall through: b_closed1 */
    case 8:
        if(mm_ws(o,23,mm_w(o,23)-1))break;
        o->r_no0+=2;
        /* fall through: b_open */
    case 10:open:
        o->patno=6;mm_ws(o,23,5);o->r_no0+=2;
        /* fall through: retail b_open ($20CE52 in R81B) runs into b_open1
           ($20CE62); PROPERA8.C:249-254 lost that call. */
    case 12:
        if(mm_ws(o,23,mm_w(o,23)-1))break;
        o->r_no0+=2;
        /* fall through: b_opend */
    case 14:
        o->mstno.w=255;mm_ws(o,23,73);o->colino=168;o->colicnt=0;o->r_no0+=2;
        /* fall through: retail b_opend ($20CE72) runs into b_opend1 ($20CE88);
           PROPERA8.C:262-269 lost that call. */
    case 16:
        if(mm_ws(o,23,mm_w(o,23)-1)){tp_patchg(o,pchg1);break;}
        o->r_no0-=14;goto close;
    }
    o->xposi.w.h=m->xposi.w.h;o->yposi.w.h=m->yposi.w.h+mm_w(o,32);
    tp_draw(o);
}

/* ---- KABUTO8.C: the beetle and its horn -------------------------------- */
static void kabuto_act(sprite_status *o){
    static const uint8_t p00[]={2,0,1,255},p01[]={2,2,3,255};
    static const uint8_t *const pchg[]={p00,p01};
    if((int8_t)o->userflag.b.l>=0){
        if(mm_enemy_suicide(o))return;
        switch(o->r_no0){
        case 0:{
            mm_ws(o,26,o->xposi.w.h);o->actflg|=4;o->sprpri=4;o->sprhsize=24;o->sprvsize=14;o->colino=42;mm_ls(o,12,-20480);o->r_no0+=2;
            sprite_status *n;
            if(tp_actwkchk2(o,&n)){tp_frameout(o);return;}
            n->userflag.b.h=o->userflag.b.h;n->userflag.b.l=-1;tp_setactno(n,o->actno);
            n->xposi.w.h=o->xposi.w.h;n->yposi.w.h=o->yposi.w.h;mm_ws(n,33,(uint16_t)mm_index(o));
            if(o->userflag.b.l){o->actflg|=1;o->cddat|=1;n->actflg|=1;n->cddat|=1;}
        }   /* fall through: a_init calls a_fall */
        case 2:{
            o->yposi.l+=65536;short c=emycol_d(o);
            if(c<0){o->yposi.w.h+=c;o->r_no0+=2;}
            break;
        }
        case 4:
            if((o->actflg&128) && !(mm_ws(o,27,mm_w(o,27)+1)&31))soundset(177);
            o->xposi.l+=mm_l(o,12);o->yposi.w.h+=emycol_d(o);
            if(mm_ws(o,23,mm_w(o,23)-1)<0){mm_ws(o,23,409);mm_ls(o,12,(int)(0u-(uint32_t)mm_l(o,12)));}
            break;
        }
        tp_draw(o);tp_frameout_s00(o,mm_w(o,26));
        return;
    }
    /* horn */
    if(!o->r_no0){o->r_no0+=2;o->actflg|=4;o->sprpri=3;o->sprhsize=12;o->sprvsize=16;o->colino=171;tp_draw(o);return;}
    const sprite_status *b=&actwk[(uint16_t)mm_w(o,33)&127];
    if(b->actno!=SCD_OBJ_R8_KABUTO){tp_frameout(o);return;}
    int pose=0;
    if(o->userflag.b.h)pose=1;
    else if(mm_ws(o,23,mm_w(o,23)-1)<0){mm_ws(o,23,60);o->mstno.b.h^=1;pose=1;}
    if(pose){
        mm_ws(o,24,-25);mm_ws(o,25,0);
        if(o->mstno.b.h){mm_ws(o,24,-19);mm_ws(o,25,-15);}
        if(o->actflg&1)mm_ws(o,24,-mm_w(o,24));
    }
    o->xposi.w.h=b->xposi.w.h+mm_w(o,24);o->yposi.w.h=b->yposi.w.h+mm_w(o,25);
    tp_patchg(o,pchg);tp_draw(o);
}
