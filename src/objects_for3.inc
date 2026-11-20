/* Collision Chaos platforms, R3/TRAP_R3.C: for3 through for3_rup3.
   Scratch words retain the original offsets; movement and ride checks retain
   their original order (vertical platforms check before moving, horizontal
   platforms after moving). Included after the BOBIN rider helpers. */
static int cc_ride_end(unsigned i){
    sprite_status *o=&actwk[i+1],*p=actwk;
    if(p->colino!=i+1)p->colino=0; /* RIDECHK.C hit_clr */
    frip_release(i);o->r_no1=0;return 0;
}
/* RIDECHK.C ridechk/hitchk/hit_v/hit_y, specialized only for r_no1=1
   and a non-spring/non-monitor platform. Terrain collision and crushing
   still use the original player collision routines. */
static int cc_ride(unsigned i){
    sprite_status *o=&actwk[i+1],*p=actwk;o->r_no1=1;
    if(p->mstno.b.h==23 || (p->actfree[2]&64) || p->r_no0>=6 || !p->actno ||
       !(o->actflg&128) || editmode.b.h)return cc_ride_end(i);
    int width=o->sprhsize+10,dx=(int16_t)(p->xposi.w.h-o->xposi.w.h+width);
    if(dx<0 || dx>=width*2 || (p->mstno.b.h==43 && !(o->cddat&8)))return cc_ride_end(i);
    if(p->mstno.b.h!=43 && p->yspeed.w<0)return cc_ride_end(i);
    int height=o->sprvsize+p->sprvsize+2,dy=(int16_t)(p->yposi.w.h-o->yposi.w.h+height);
    if(dy<0 || dy>=height*2)return cc_ride_end(i);
    int depth_x=dx>width?width*2-dx:dx;
    if(dy>height || dy>=depth_x)return cc_ride_end(i);
    p->yposi.w.h=o->yposi.w.h-o->sprvsize-p->sprvsize;
    p->xposi.l+=(int32_t)o->xspeed.w*256;
    if(o->xspeed.w){
        char direction=o->xspeed.w<0?64:-64;short distance=dircolm(p,&direction);
        if(distance<0)p->xposi.w.h+=o->xspeed.w<0?-distance:distance;
    }
    p->yposi.l+=(int32_t)o->yspeed.w*256;
    if(o->yspeed.w>=0){
        short d0,d1,d3,distance=dircol_d(p,&d0,&d1,&d3);
        if(distance<0){p->yposi.w.h+=distance;return cc_ride_end(i);}
    }else if(dircol_u2(p)<0){playdieset(p);return cc_ride_end(i);}
    frip_stand(i);return 1;
}
static int16_t cc_word(sprite_status *o,unsigned w){return (int16_t)scd_word_get(o,w);}
static void for3_sink(sprite_status *o){
    if(!o->actfree[21])return;
    if(!(o->cddat&8)){if(!o->actfree[20])return;o->actfree[20]-=8;}
    else{if(o->actfree[20]==64)return;o->actfree[20]+=8;}
    short sn,cs;sinset(o->actfree[20],&sn,&cs);
    o->yposi.w.h=cc_word(o,26)+(((int32_t)sn*1024)>>16);
}
static void for3_horizontal(unsigned i){
    sprite_status *o=&actwk[i+1];
    static const uint8_t duration[]={28,8,8,56,8,8,56,8};
    static const int8_t acceleration[]={0,-48,-48,0,48,48,0,-48};
    static const int16_t velocity[]={768,768,0,-768,-768,0,768,768};
    int sign=o->userflag.b.h==1?1:-1;
    for(;;){
        if(!o->actfree[14]){
            unsigned phase=o->actfree[15];o->actfree[21]=1;
            o->actfree[14]=duration[phase];
            scd_word_set(o,29,acceleration[phase]*sign);scd_word_set(o,28,velocity[phase]*sign);
            cc_ride(i);return;
        }
        o->xspeed.w=cc_word(o,28);o->xposi.l+=(int32_t)o->xspeed.w*256;
        scd_word_set(o,28,cc_word(o,28)+cc_word(o,29));
        if(--o->actfree[14]){cc_ride(i);return;}
        if(++o->actfree[15]==8)o->actfree[15]=2;
    }
}
static void for3_vertical(unsigned i){
    sprite_status *o=&actwk[i+1];
    static const uint8_t duration[]={35,8,8,70,8,8,70,8};
    static const int8_t acceleration[]={0,64,64,0,-64,-64,0,64};
    static const int16_t velocity[]={-512,-512,0,512,512,0,-512,-512};
    int sign=o->userflag.b.h==3?1:-1;
    for(;;){
        cc_ride(i);
        if(!o->actfree[14]){
            unsigned phase=o->actfree[15];o->actfree[21]=0;o->actfree[14]=duration[phase];
            scd_word_set(o,29,acceleration[phase]*sign);scd_word_set(o,28,velocity[phase]*sign);return;
        }
        o->yposi.l+=(int32_t)cc_word(o,28)*256;
        scd_word_set(o,28,cc_word(o,28)+cc_word(o,29));o->yspeed.w=scd_word_get(o,28)&0xff00;
        if(--o->actfree[14])return;
        if(++o->actfree[15]==8)o->actfree[15]=2;
    }
}
static void for3_rise(unsigned i){
    sprite_status *o=&actwk[i+1];cc_ride(i);
    if(!o->actfree[16]){
        if(!o->actfree[14]){o->actfree[21]=1;if(cc_ride(i))o->actfree[14]=30;return;}
        if(--o->actfree[14])return;
        o->actfree[21]=0;o->actfree[16]=2;return;
    }
    if(o->actfree[16]!=2)return;
    static const uint8_t duration[3][3]={{16,48,16},{16,69,16},{16,88,16}};
    static const int8_t acceleration[3][3]={{-16,0,16},{-48,0,48},{-64,0,64}};
    static const int16_t velocity[3][3]={{0,-512,-512},{0,-768,-768},{0,-1024,-1024}};
    unsigned sub=o->userflag.b.h-5;
    for(;;){
        if(!o->actfree[14]){
            unsigned phase=o->actfree[15];o->actfree[14]=duration[sub][phase];
            scd_word_set(o,29,acceleration[sub][phase]);scd_word_set(o,28,velocity[sub][phase]);return;
        }
        /* Retail R32A $20CFB6 moves by the whole speed word; only the Y
           velocity riders read is masked (TRAP_R3.C moves by the masked one). */
        scd_word_set(o,28,cc_word(o,28)+cc_word(o,29));o->yspeed.w=scd_word_get(o,28)&0xff00;
        o->yposi.l+=(int32_t)cc_word(o,28)*256;
        if(--o->actfree[14])return;
        if(++o->actfree[15]==3)break;
    }
    o->yspeed.w=0;o->actfree[21]=1;scd_word_set(o,26,o->yposi.w.h);o->actfree[16]=4;
}
static void for3_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    if(!o->r_no0){
        o->actflg|=4;o->sprpri=3;o->sprhsize=32;o->sprvsize=16;
        scd_word_set(o,27,o->xposi.w.h);scd_word_set(o,26,o->yposi.w.h);o->r_no0=2;
    }
    switch(o->userflag.b.h){
    case 0:o->actfree[21]=1;cc_ride(i);break;
    case 1:case 2:for3_horizontal(i);break;
    case 3:case 4:for3_vertical(i);break;
    default:for3_rise(i);break;
    }
    for3_sink(o);
}
