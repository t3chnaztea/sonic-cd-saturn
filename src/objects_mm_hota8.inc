/* Metallic Madness (R8) Act 3 boss room: R8/HOTA8C.C (Good Future) and
   HOTA8D.C (Bad Future) hotaru8. One routine, told apart by subtype:
   -2 the room controller (placed), 0/1 the fireflies it releases, -1 a
   firefly's beam, -3 a firefly's afterimage.
   The room: once the player passes x 3024 it sets shut_flag, opens a door
   (TOBIRA, actfree[21] trigger) at 3240,464, drops scra_vline by 6 an
   update until it reaches 204 (then bossflag = 8), fades the room palette,
   releases one firefly, then two, and when both are gone fades back, opens
   the door and starts the boss: retail spawns actor 63 (egg8) at 3840,316;
   the port calls scd_boss_create_sub(3840,316,0,8) and frames out.
   Quirks kept:
   - ht8main_move4 stores the second firefly's actor number in
     ((unsigned short*)room)[5]: on the 32-bit PC that is xposi.w.h, so the
     room's x becomes that number (move5 reads it back from there).
   - HOTA8D declares its tables static without initialisers and defines
     clrchgtbl1/clrtblD later: clrchgtbl2 and clrtblC1 stay zero there
     (unused: the D room fades back with colchg2(0) and opens at once).
   - The palette writes go to lpcolorwk 49-50 and 60-63 (C) or 52-63 (D);
     native keeps them in mm_room_palette (scd_objects_mm_room_palette) for
     the renderer (native hook: main.c must apply them in R8 Act 3).
   - Fireflies and their beams never frame out; the room never draws. */
extern short scra_vline;
static const uint8_t mm_clrchgtbl1_c[16]={84,64,72,4,60,5,48,6,36,7,24,8,12,9,0,0};
static const uint8_t mm_clrchgtbl2_c[16]={0,64,12,9,24,8,36,7,48,6,60,5,72,4,84,32};
static const uint8_t mm_clrtblC1_c[48][4]={{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,32,1},{0,0,0,1},{0,0,0,1},{0,0,32,1},{0,0,0,1},{0,0,0,1},{0,0,64,1},{0,0,0,1},{0,0,32,1},{0,0,64,1},{0,0,0,1},{0,0,0,1},{0,0,96,1},{0,0,0,1},{0,0,64,1},{0,0,96,1},{0,0,0,1},{0,0,0,1},{32,32,128,1},{0,0,32,1},{0,0,96,1},{0,0,128,1},{0,0,0,1},{0,0,0,1},{64,64,160,1},{0,0,64,1},{0,0,128,1},{32,0,160,1},{0,0,32,1},{0,0,0,1},{96,96,192,1},{0,0,96,1},{32,0,160,1},{64,32,192,1},{0,0,64,1},{0,0,32,1},{128,128,224,1},{0,32,128,1},{64,32,192,1},{96,64,224,1},{0,0,96,1}};
static const int16_t mm_ht8move2_c[32]={0,0,0,12,12,12,36,36,36,0,0,0,12,12,12,36,36,36,0,0,0,12,12,12,36,36,36,48,60,72,84,-1};
static const uint8_t mm_clrchgtbl1_d[16]={168,64,144,4,120,5,96,6,72,7,48,8,24,9,0,0};
static const uint8_t mm_clrchgtbl2_d[16]={0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0};
static const uint8_t mm_clrtblD_d[108][4]={{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,32,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,32,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,64,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,64,1},{0,0,0,1},{0,0,0,1},{0,32,0,1},{0,96,32,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{0,0,32,1},{0,32,96,1},{0,0,0,1},{0,0,0,1},{32,64,0,1},{0,128,64,1},{0,0,0,1},{0,0,0,1},{0,0,32,1},{0,0,0,1},{0,0,0,1},{0,0,0,1},{32,0,64,1},{32,64,128,1},{0,0,0,1},{0,32,0,1},{32,96,0,1},{0,160,96,1},{0,0,0,1},{0,0,0,1},{0,0,64,1},{0,0,32,1},{0,0,0,1},{0,0,32,1},{32,32,96,1},{32,96,160,1},{0,32,0,1},{0,64,0,1},{32,128,32,1},{0,192,128,1},{0,0,0,1},{0,0,0,1},{0,32,96,1},{0,32,64,1},{0,0,32,1},{0,32,64,1},{32,64,128,1},{32,128,192,1},{32,32,0,1},{32,64,0,1},{64,128,32,1},{32,192,128,1},{0,0,0,1},{0,0,0,1},{0,32,96,1},{0,32,64,1},{0,0,32,1},{32,32,64,1},{64,64,128,1},{64,128,192,1},{64,32,0,1},{64,64,0,1},{96,128,32,1},{64,192,128,1},{32,0,0,1},{0,0,0,1},{0,32,96,1},{0,32,64,1},{32,0,32,1},{64,32,64,1},{96,64,128,1},{96,128,192,1}};
static const int16_t mm_ht8move2_d[32]={0,0,0,24,24,24,72,72,72,0,0,0,24,24,24,72,72,72,0,0,0,24,24,24,72,72,72,96,120,144,168,255};
static uint8_t mm_room_palette[64][4];
static unsigned mm_room_palette_dirty;
/* The Act 3 room palette (entries 49-63) and a nonzero count when it
   changed since the last call. */
const uint8_t (*scd_objects_mm_room_palette(unsigned *dirty))[4]{
    if(dirty)*dirty=mm_room_palette_dirty;
    mm_room_palette_dirty=0;
    return mm_room_palette;
}
static int hota8_d(void){return current_era!=2;}
static void hota8_clrtrn(unsigned n){
    if(hota8_d()){memcpy(mm_room_palette[52],mm_clrtblD_d[n/2],12*4);}
    else{memcpy(mm_room_palette[49],mm_clrtblC1_c[n/2],2*4);memcpy(mm_room_palette[60],mm_clrtblC1_c[n/2+2],4*4);}
    mm_room_palette_dirty++;
}
static void hota8_colchg(sprite_status *o,const uint8_t *chg){
    if(o->actfree[16]==16)return;
    if(o->actfree[17]){--o->actfree[17];return;}
    unsigned char idx=chg[o->actfree[16]];
    o->actfree[17]=chg[o->actfree[16]+1];
    hota8_clrtrn(idx);o->actfree[16]+=2;
}
static void hota8_initx(sprite_status *o,unsigned char pri){
    o->actflg|=4;o->sprpri=pri;mm_ws(o,29,o->xposi.w.h);mm_ws(o,27,o->yposi.w.h);
}
/* ACTSET.C actwkchk from the first actor, as a probe. */
static int mm_any_free(void){for(unsigned i=0;i<SCD_OBJECT_CAPACITY;i++)if(!pool[i].type)return 1;return 0;}
static sprite_status *hota8_spawn(int8_t sub,short x,short y){
    sprite_status *n;
    if(tp_actwkchk(&n))return 0;
    n->userflag.b.h=sub;tp_setactno(n,SCD_OBJ_R8_HOTARU8);n->xposi.w.h=x;n->yposi.w.h=y;
    return n;
}
static const uint8_t hota8_p0[]={1,5,0,5,0,255},hota8_p1[]={0,4,10,10,255},hota8_p2[]={7,11,12,255},hota8_p3[]={3,6,15,255},
    hota8_p4[]={0,4,10,255},hota8_p5[]={7,4,10,255},hota8_p8[]={0,6,10,255},hota8_p9[]={0,9,10,16,10,255};
static const uint8_t *const hota8_pchg[10]={hota8_p0,hota8_p1,hota8_p2,hota8_p3,hota8_p4,hota8_p5,hota8_p8,hota8_p8,hota8_p8,hota8_p9};
static void hota8_room(sprite_status *o){
    sprite_status *p=&actwk[0];
    switch(o->r_no0){
    case 0:{
        hota8_initx(o,1);
        if(p->xposi.w.h<3024)return;
        shut_flag=1;
        sprite_status *d;
        if(tp_actwkchk(&d))return;
        d->yposi.w.h=464;d->xposi.w.h=3240;tp_setactno(d,SCD_OBJ_R8_TOBIRA);
        mm_ws(o,33,(uint16_t)mm_index(d));o->r_no0+=2;
        return;
    }
    case 2:
        if(p->xposi.w.h<3024)return;
        if(scra_vline>=204)bossflag=8;
        scra_vline+=6;
        if(bossflag==8){o->r_no0+=2;o->actfree[16]=o->actfree[17]=0;}
        return;
    case 4:{
        hota8_colchg(o,hota8_d()?mm_clrchgtbl1_d:mm_clrchgtbl1_c);
        if(o->actfree[16]!=16)return;
        o->actfree[16]=o->actfree[17]=0;
        sprite_status *h=hota8_spawn(0,3040,400);
        if(!h)return;
        mm_ws(o,28,(uint16_t)mm_index(h));o->actfree[16]=60;o->r_no0+=2;
        return;
    }
    case 6:{
        if(actwk[(uint16_t)mm_w(o,28)&127].actno==SCD_OBJ_R8_HOTARU8)return;
        hota8_clrtrn(0);
        if(--o->actfree[16])return;
        sprite_status *h=hota8_spawn(1,3040,392);
        if(!h)return;
        mm_ws(o,28,(uint16_t)mm_index(h));o->r_no0+=2;
    }   /* fall through: move3 calls move4 */
    case 8:{
        sprite_status *h=hota8_spawn(0,3200,392);
        if(!h)return;
        o->xposi.w.h=(short)mm_index(h); /* PC ((unsigned short*)room)[5] */
        o->actfree[16]=o->actfree[17]=0;o->r_no0+=2;
        return;
    }
    case 10:
        if(actwk[(uint16_t)mm_w(o,28)&127].actno==SCD_OBJ_R8_HOTARU8)return;
        if(actwk[(uint16_t)o->xposi.w.h&127].actno==SCD_OBJ_R8_HOTARU8)return;
        o->r_no0+=2;return;
    case 12:
        if(hota8_d())hota8_clrtrn(0);
        else{hota8_colchg(o,mm_clrchgtbl2_c);if(o->actfree[16]!=16)return;}
        actwk[(uint16_t)mm_w(o,33)&127].actfree[21]=255;
        if(!mm_any_free())return;
        scd_boss_create_sub(3840,316,0,8);
        tp_frameout(o);
        return;
    }
}
static void hota8_firefly(sprite_status *o){
    sprite_status *p=&actwk[0];
    switch(o->r_no0){
    /* Retail hotaru8_init (R83D $20F404) runs into hotaru8_dspin ($20F41E);
       HOTA8C.C/HOTA8D.C:106-112 lost that, so the spin held one update long. */
    case 0:hota8_initx(o,1);o->sprvsize=o->sprhsize=8;o->r_no0+=2;o->actfree[16]=60;
        /* fall through */
    case 2:
        o->mstno.b.h=4;tp_patchg(o,hota8_pchg);
        if(--o->actfree[16])break;
        o->mstno.b.h=1;o->actfree[1]=o->userflag.b.h;o->r_no0+=2;break;
    case 4:{
        short np=0;int near=0;
        if(o->actfree[1]&1){np=p->xposi.w.h&32760;near=np>=3008 && np<3232;}
        if(near){mm_ws(o,24,np);mm_ws(o,25,344);}
        else{mm_ws(o,24,(gametimer.w&127)+3056);mm_ws(o,25,((p->xposi.w.h*5)&31)+352);}
        o->yspeed.w=0;short sc=mm_w(o,25)-o->yposi.w.h;if(sc)o->yspeed.w=sc*8;
        o->xspeed.w=0;sc=mm_w(o,24)-o->xposi.w.h;if(sc)o->xspeed.w=sc*8;
        ++o->actfree[1];o->actfree[17]=32;o->r_no0+=2;o->colino=0;
        break;
    }
    case 6:
        o->xposi.l+=(int)o->xspeed.w<<8;o->yposi.l+=(int)o->yspeed.w<<8;
        if((o->actfree[17]&3)==3)hota8_spawn(-3,o->xposi.w.h,o->yposi.w.h);
        if(!--o->actfree[17])o->r_no0+=2;
        tp_patchg(o,hota8_pchg);break;
    case 8:{
        o->mstno.b.h=0;tp_patchg(o,hota8_pchg);
        int16_t c=(hota8_d()?mm_ht8move2_d:mm_ht8move2_c)[o->actfree[18]++];
        if(c!=(hota8_d()?255:-1))hota8_clrtrn((unsigned char)c);
        else{o->r_no0+=2;o->actfree[18]=0;}
        break;
    }
    case 10:
        if(!o->actfree[18]){o->actfree[18]=20;o->mstno.b.h=2;o->colino=11;}
        /* Retail hotaru8_move3 (R83C $20F502, R83D $20F58A): addib #$80; bcc,
           a beam every second update; HOTA8C/D.C:212 read += 64. */
        {unsigned v=o->actfree[21]+128u;o->actfree[21]=(uint8_t)v;
         if(v>255){sprite_status *b=hota8_spawn(-1,o->xposi.w.h,o->yposi.w.h);(void)b;}}
        tp_patchg(o,hota8_pchg);
        if(!--o->actfree[18])o->r_no0+=2;
        break;
    case 12:
        if(!o->actfree[18]){o->actfree[18]=16;o->mstno.b.h=0;}
        tp_patchg(o,hota8_pchg);
        if(--o->actfree[18])break;
        o->r_no0=4;o->mstno.b.h=1;hota8_clrtrn(0);break;
    }
    tp_draw(o);
}
static void hota8_act(sprite_status *o){
    int8_t sub=(int8_t)o->userflag.b.h;
    if(sub==-3){
        /* afterimage */
        if(!o->r_no0){hota8_initx(o,4);o->actfree[16]=24;o->mstno.b.h=4;o->r_no0+=2;}
        tp_patchg(o,hota8_pchg);
        if(--o->actfree[16])tp_draw(o);else tp_frameout(o);
        return;
    }
    if(sub==-2){hota8_room(o);return;}
    if(sub==-1){
        /* beam */
        switch(o->r_no0){
        case 0:hota8_initx(o,3);o->r_no0+=2;o->sprvsize=16;o->sprhsize=4;o->colino=152;break;
        case 2:
            o->mstno.b.h=8;o->yposi.w.h+=8;tp_patchg(o,hota8_pchg);
            if(emycol_d(o)<0){o->r_no0+=2;o->actfree[16]=o->actfree[17]=0;}
            break;
        case 4:
            if(!o->actfree[16]){o->actfree[16]=2;o->mstno.b.h=9;if(o->actfree[17])break;}
            tp_patchg(o,hota8_pchg);
            if(--o->actfree[16])break;
            if(++o->actfree[17]>=2){tp_frameout(o);return;}
            break;
        }
        tp_draw(o);return;
    }
    o->userflag.b.h&=127;
    hota8_firefly(o);
}
