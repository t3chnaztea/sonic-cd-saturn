/* R4 TONBO.C / YAGO.C / AMENBO.C / TAGAMEB4.C versus the native actors.
   Build with -DTT_KIND=SCD_OBJ_x -DTT_ORIGINAL=name (tools/test-tt-actors.sh). */
#include "tt_actor_fixture.h"
void TT_ORIGINAL(sprite_status*);
static unsigned states[16],flips;
/* Original actor indices 100..127 become native 1..28. */
static void index_word(sprite_status *o,unsigned w){
    unsigned v=scd_word_get(o,w);if(v>=100 && v<128)scd_word_set(o,w,v-99);
}
static void normalize(sprite_status *o){
    if(TT_KIND!=SCD_OBJ_TAGAMEB)return;
    if(o->userflag.b.h&128)index_word(o,33);
    else if(!o->userflag.b.h && o->r_no0){index_word(o,26);index_word(o,27);index_word(o,28);}
}
static void run(sprite_status p,int follow){
    if(follow)camera_on(actwk[1].xposi.w.h,actwk[1].yposi.w.h);
    unsigned flag=actwk[1].actflg&1;
    tick(p);
    if(actwk[1].actno==TT_KIND){states[actwk[1].r_no0/2&15]++;if((actwk[1].actflg&1)!=flag)flips++;}
    for(unsigned n=0;n<28;n++)if(!actwk[n+1].actno && actwk[n+100].actno==SCD_OBJ_EXPLOSION)memset(actwk+n+100,0,sizeof(*actwk));
}
int main(void){
    test_kind=TT_KIND;original_actor=TT_ORIGINAL;normalize_original=normalize;
    fixture_name=TT_NAME;
    static const int sides[5][2]={{-900,0},{-60,-8},{70,-8},{-150,40},{150,-120}};
    for(unsigned act=0;act<(TT_KIND==SCD_OBJ_TONBO?3u:2u);act++)for(unsigned era=0;era<4;era++){
        if(act==2 && era<2)continue; /* Act 3 exists only as the two Futures. */
        load(act,era);
        for(unsigned sub=0;sub<2;sub++)for(unsigned flags=0;flags<2;flags++)
        for(unsigned section=0;section<10;section++)for(unsigned side=0;side<5;side++){
            int x=400+section*1100,y=200+(section*337)%1200;
            setup(era,sub,flags,x,y);waterposi=y+8;
            for(frame=0;frame<420;frame++){
                sprite_status p=player(actwk[1].xposi.w.h+sides[side][0],actwk[1].yposi.w.h+sides[side][1],side==1?1:side==2?8:0);
                if(side==0)p.yposi.w.h=y;
                run(p,1);
                if(actwk[1].actno!=TT_KIND)break;
            }
        }
        /* COLI4 contact grid: every relative position around the body,
           rolling/standing/invulnerable/small hitbox, both vertical speeds. */
        for(unsigned sub=0;sub<2;sub++)for(int dx=-40;dx<=40;dx+=2)for(int dy=-44;dy<=44;dy+=2)
        for(unsigned mode=0;mode<16;mode++){
            setup(era,sub,0,3000,600);waterposi=608;frame=0;
            run(player(2000,600,0),1);
            frame=1;run(player(actwk[1].xposi.w.h+dx,actwk[1].yposi.w.h+dy,mode),1);contacts++;
        }
        /* Shield off with rings and with none. */
        for(unsigned rings=0;rings<2;rings++){
            setup(era,0,0,3000,600);waterposi=608;frame=0;run(player(2000,600,0),1);
            plpower_b=0;plring=rings*5;
            frame=1;run(player(actwk[1].xposi.w.h,actwk[1].yposi.w.h,0),1);contacts++;
        }
    }
    /* Allocation failure: the parent's child requests find no free actor. */
    for(unsigned free_slots=0;free_slots<1;free_slots++){
        load(0,0);setup(0,0,0,3000,600);waterposi=608;
        for(unsigned n=1+free_slots;n<28;n++){int r=scd_objects_spawn(SCD_OBJ_RING,15000,100,0,0);REQUIRE(r>=0);actwk[100+r].actno=SCD_OBJ_RING;}
        /* Slot 31 (actor 32) holds the water-surface wave (GAME4.C:635). */
        for(unsigned n=28;n<SCD_OBJECT_CAPACITY;n++)if(n!=31)REQUIRE(scd_objects_spawn(SCD_OBJ_RING,15000,100,0,0)==(int)n);
        REQUIRE(actwk[32].actno==SCD_OBJ_WAVE);
        for(frame=0;frame<400;frame++)run(player(actwk[1].xposi.w.h+(frame&64?-60:60),actwk[1].yposi.w.h,0),1);
    }
    unsigned used=0;for(unsigned n=0;n<16;n++)if(states[n])used++;
    REQUIRE(used>=(TT_KIND==SCD_OBJ_TONBO?1u:3u) && flips && contacts && defeats);
    printf("PASS: %s %u assertions; %u updates; %u contact updates; %u child compares; %u defeats; %u states; %u turns\n",TT_NAME,checks,updates,contacts,children,defeats,used,flips);
    return 0;
}
