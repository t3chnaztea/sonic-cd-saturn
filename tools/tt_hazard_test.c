/* R4 HARIR4.C / HARID4.C / SCREW_A.C / SCREW_C.C / OSUMIZU.C / FUNSUI4.C /
   UKIDAI.C / PLAYSUB4.C bou versus the native actors, with RIDECHK.C.
   Build with -DTT_KIND=SCD_OBJ_x -DTT_ORIGINAL=name (tools/test-tt-actors.sh). */
#include "tt_actor_fixture.h"
void TT_ORIGINAL(sprite_status*);
static unsigned states[16],ridden,moved;
static void index_word(sprite_status *o,unsigned w){
    unsigned v=scd_word_get(o,w);if(v>=100 && v<128)scd_word_set(o,w,v-99);
}
static void normalize(sprite_status *o){
    if(TT_KIND==SCD_OBJ_HARID4){if(o->userflag.b.h&128)index_word(o,33);else index_word(o,32);}
}
/* Contact modes as in the CC drum fixture: falling, rising, rolling,
   standing on the actor, spring pose, hurt pose, invulnerable, still. */
static sprite_status contact(int x,int y,unsigned mode,int xs){
    sprite_status p=player(x,y,0);p.xspeed.w=xs;
    switch(mode){
    case 1:p.yspeed.w=-300;break;
    case 2:p.sprvsize=14;p.cddat=6;break;
    case 3:p.cddat=8;p.actfree[19]=1;p.yspeed.w=0;break;
    case 4:p.mstno.b.h=23;break;
    case 5:p.mstno.b.h=43;break;
    case 6:scd_word_set(&p,26,120);break;
    case 7:p.yspeed.w=0;p.cddat=0;break;
    }
    return p;
}
static void run(sprite_status p){
    camera_on(actwk[1].xposi.w.h,actwk[1].yposi.w.h);
    tick(p);
    if(actwk[1].actno==TT_KIND)states[actwk[1].r_no0/2&15]++;
    if(actwk[0].cddat&8)ridden++;
    if(actwk[0].xposi.w.h!=p.xposi.w.h || actwk[0].yposi.w.h!=p.yposi.w.h || actwk[0].mspeed.w!=p.mspeed.w)moved++;
}
/* The fixture's tick compares the player byte-for-byte, so a ride
   reference must match: RIDECHK.C stores the actor index (native 1,
   original 100). Run the original with the reference mapped. */
static void (*real_original)(sprite_status*);
static void mapped_original(sprite_status *o){
    if(actwk[0].actfree[19]==1)actwk[0].actfree[19]=100;
    if(actwk[0].colino==1)actwk[0].colino=100;
    real_original(o);
    if(actwk[0].actfree[19]==100)actwk[0].actfree[19]=1;
    if(actwk[0].colino==100)actwk[0].colino=1;
}
static void water(int level){waterposi=waterposi_m=level;}
int main(void){
    test_kind=TT_KIND;real_original=TT_ORIGINAL;original_actor=mapped_original;normalize_original=normalize;
    fixture_name=TT_NAME;
    static const int xs[3]={512,0,-512};
    unsigned acts=TT_KIND==SCD_OBJ_OSUMIZU || TT_KIND==SCD_OBJ_UKIDAI?1:2;
    for(unsigned act=TT_KIND==SCD_OBJ_OSUMIZU || TT_KIND==SCD_OBJ_UKIDAI?1:0;act<acts+(TT_KIND==SCD_OBJ_OSUMIZU || TT_KIND==SCD_OBJ_UKIDAI);act++)
    for(unsigned era=0;era<4;era++){
        if((TT_KIND==SCD_OBJ_SCREW && era>=2) || (TT_KIND==SCD_OBJ_SCREW_F && era<2))continue;
        load(act,era);
        for(unsigned sub=0;sub<4;sub++)for(unsigned section=0;section<8;section++){
            int x=500+section*1300,y=300+(section*413)%1100;
            memset(switchflag,0,sizeof(switchflag));
            water(TT_KIND==SCD_OBJ_UKIDAI?(section&1?1504:1920):y+(section&2?-80:80));
            watermoveposi=TT_KIND==SCD_OBJ_UKIDAI?(section&2?1504:1920):0;
            waterspeed=section&1;water_flag=section*16;
            unsigned usub=TT_KIND==SCD_OBJ_HARIR4?(unsigned[]){0,1,2,3}[sub]:TT_KIND==SCD_OBJ_SCREW || TT_KIND==SCD_OBJ_SCREW_F?(unsigned[]){0,1,2,131}[sub]:sub&1;
            setup(era,usub,sub>>1&1,x,y);
            actwk[1].userflag.b.l=actwk[100].userflag.b.l=section&1?128:section&7;
            /* Motion with the player away, then walking through. */
            for(frame=0;frame<360;frame++){
                if(frame==100)switchflag[section&7]=1;
                if(TT_KIND==SCD_OBJ_UKIDAI && frame==200){watermoveposi=1504;water(1504);}
                int px=actwk[1].xposi.w.h+(frame<120?-600:frame-240),py=actwk[1].yposi.w.h+(TT_KIND==SCD_OBJ_HARID4?100:0);
                sprite_status p=player(px,py,0);
                if(TT_KIND==SCD_OBJ_BOU){swdata1.b.h=frame&16?1:frame&32?2:0;swdata1.b.l=frame%97==0?16:0;}
                run(p);
                if(actwk[1].actno!=TT_KIND)break;
            }
            if(TT_KIND==SCD_OBJ_SCREW || TT_KIND==SCD_OBJ_SCREW_F)continue;
            /* Contact grid around the body in every player mode. */
            setup(era,usub,0,x,y);actwk[1].userflag.b.l=actwk[100].userflag.b.l=128;
            /* Two updates: the snapshot must carry this position's visibility bit. */
            frame=0;run(player(x-900,y,0));run(player(x-900,y,0));
            sprite_status native=actwk[1],original=actwk[100];
            unsigned hw=actwk[1].sprhsize+14,hh=actwk[1].sprvsize+24;
            /* Every third pixel for small bodies; tall bodies keep about 20 rows. */
            int step=(hw+hh)/12>3?(int)(hw+hh)/12:3;
            for(unsigned v=0;v<3;v++)for(int dx=-(int)hw;dx<=(int)hw;dx+=step)for(int dy=-(int)hh;dy<=(int)hh;dy+=step)
            for(unsigned mode=0;mode<8;mode++){
                actwk[1]=native;actwk[100]=original;
                frame=1;run(contact(actwk[1].xposi.w.h+dx,actwk[1].yposi.w.h+dy,mode,xs[v]));contacts++;
                if(actwk[1].actno!=TT_KIND)break;
            }
        }
    }
    unsigned used=0;for(unsigned n=0;n<16;n++)if(states[n])used++;
    REQUIRE(used>=1 && updates);
    printf("PASS: %s %u assertions; %u updates; %u contact updates; %u child compares; %u player moves; %u ridden; %u states\n",TT_NAME,checks,updates,contacts,children,moved,ridden,used);
    return 0;
}
