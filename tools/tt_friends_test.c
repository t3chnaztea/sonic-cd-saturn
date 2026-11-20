/* R4 MOVIE4.C + FRIEND4.C, ET4.C and AWA.C versus the native actors.
   Build with -DTT_KIND=SCD_OBJ_x -DTT_ORIGINAL=name [-DTT_KIND2 -DTT_ORIGINAL2]. */
#include "tt_actor_fixture.h"
void TT_ORIGINAL(sprite_status*);
#ifdef TT_ORIGINAL2
void TT_ORIGINAL2(sprite_status*);
#endif
static unsigned states[16],blasts,breaks;
static void index_word(sprite_status *o,unsigned w){
    unsigned v=scd_word_get(o,w);if(v>=100 && v<128)scd_word_set(o,w,v-99);
}
/* The original event cursor lives in ((char**)o)[12] (a side table here). */
static void normalize(sprite_status *o){
    if(o->actno==SCD_OBJ_MOVIE4 && o->userflag.b.h)index_word(o,33);
    if(o->actno==SCD_OBJ_FRIEND4 && (o->userflag.b.h&128))index_word(o,33);
}
static void (*real_original)(sprite_status*);
static void mapped_original(sprite_status *o){
    if(actwk[0].actfree[19]>=1 && actwk[0].actfree[19]<=28)actwk[0].actfree[19]+=99;
    if(actwk[0].colino>=1 && actwk[0].colino<=28)actwk[0].colino+=99;
    real_original(o);
    if(actwk[0].actfree[19]>=100 && actwk[0].actfree[19]<128)actwk[0].actfree[19]-=99;
    if(actwk[0].colino>=100 && actwk[0].colino<128)actwk[0].colino-=99;
}
static void run(sprite_status p){
    camera_on(actwk[1].xposi.w.h,actwk[1].yposi.w.h);
    unsigned before=0;for(unsigned n=1;n<29;n++)if(actwk[n].actno==SCD_OBJ_EXPLOSION)before++;
    tick(p);
    if(actwk[1].actno==TT_KIND)states[actwk[1].r_no0/2&15]++;
    unsigned after=0;for(unsigned n=1;n<29;n++)if(actwk[n].actno==SCD_OBJ_EXPLOSION)after++;
    if(after>before)blasts+=after-before;
    for(unsigned n=0;n<28;n++)if(!actwk[n+1].actno && actwk[n+100].actno==SCD_OBJ_EXPLOSION)memset(actwk+n+100,0,sizeof(*actwk));
}
int main(void){
    test_kind=TT_KIND;real_original=TT_ORIGINAL;original_actor=mapped_original;normalize_original=normalize;
#ifdef TT_ORIGINAL2
    test_kind2=TT_KIND2;original_actor2=TT_ORIGINAL2;
#endif
    fixture_name=TT_NAME;
    for(unsigned act=0;act<3;act++)for(unsigned era=0;era<4;era++){
        if(act==2 && era<2)continue;
        load(act,era);
        for(unsigned sub=0;sub<(TT_KIND==SCD_OBJ_AWA?6u:2u);sub++)for(unsigned section=0;section<6;section++){
            int x=600+section*1500,y=300+(section*389)%1000;
            unsigned usub=TT_KIND==SCD_OBJ_AWA?(sub<3?sub:128+sub):sub;
            waterposi=waterposi_m=y+(TT_KIND==SCD_OBJ_AWA?-120:60);
            setup(era,usub,section&1,x,y);
            for(frame=0;frame<700;frame++){
                /* Approach, then roll into or ride over the actor. */
                int px=actwk[1].xposi.w.h+(frame<150?-500:(int)(frame%80)-40),py=actwk[1].yposi.w.h+(int)(frame%40)-20;
                unsigned mode=frame%3==0?1:0;
                if(TT_KIND==SCD_OBJ_AWA){px=actwk[1].xposi.w.h+(int)(frame%24)-12;py=waterposi+16+(int)(frame%30);mode=frame&32?32:0;}
                sprite_status p=player(px,py,mode);
                if(TT_KIND==SCD_OBJ_AWA)p.cddat|=64;
                run(p);
                if(actwk[1].actno!=TT_KIND){
                    if(TT_KIND!=SCD_OBJ_AWA)break;
                }
                if(TT_KIND==SCD_OBJ_ET4 && actwk[1].patno==7)breaks++;
            }
        }
    }
    unsigned used=0;for(unsigned n=0;n<16;n++)if(states[n])used++;
    REQUIRE(used>=(TT_KIND==SCD_OBJ_FRIEND4?1u:3u) && updates);
    if(TT_KIND!=SCD_OBJ_FRIEND4 && TT_KIND!=SCD_OBJ_AWA)REQUIRE(blasts);
    if(TT_KIND==SCD_OBJ_AWA)REQUIRE(air_original);
    printf("PASS: %s %u assertions; %u updates; %u child compares; %u explosions; %u air refills; %u states\n",TT_NAME,checks,updates,children,blasts,air_original,used);
    return 0;
}
