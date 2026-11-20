/* Multi-actor oracle: independently compiled TRAP_R3.C + original patchg,
   RIDECHK.C and COLI3.C. Reference slots 100..127 mirror native 1..28. */
#define main traps_main
#include "cc_traps_test.c"
#undef main
void gandair3(sprite_status*);
static unsigned launches,bullets,cycles;
static void gsetup(unsigned era,unsigned sub,unsigned flags){
    kind=SCD_OBJ_GANDAIR3;subtype=sub;setup(era,flags);
    time_flag=era==0?1:era==1?0:2;generate_flag=era==2;
}
static void gtick(sprite_status before){
    actwk[0]=before;
    if(actwk[0].actfree[19])actwk[0].actfree[19]+=99;
    if(actwk[0].colino)actwk[0].colino+=99;
    unsigned char shield=plpower_b;original_hits=0;
    if(actwk[0].r_no0<4)pcol(actwk);
    for(unsigned n=100;n<128;n++)if(actwk[n].actno)gandair3(&actwk[n]);
    sprite_status expected=actwk[0];unsigned char expected_shield=plpower_b;plpower_b=shield;
    if(expected.actfree[19]>=100)expected.actfree[19]-=99;
    if(expected.colino>=100)expected.colino-=99;
    actwk[0]=before;unsigned hits=scd_objects_get().hits;
    scd_objects_step(before.xposi.w.h,before.yposi.w.h);
    REQUIRE(!memcmp(&actwk[0],&expected,sizeof(before)));
    REQUIRE(plpower_b==expected_shield);REQUIRE(scd_objects_get().hits-hits==original_hits);
    for(unsigned n=0;n<28;n++){
        sprite_status *a=&actwk[n+1],*b=&actwk[n+100];
        REQUIRE(a->actno==b->actno);
        if(!a->actno)continue;
        compare(a,b);REQUIRE(a->mstno.w==b->mstno.w);
        REQUIRE(a->patcnt==b->patcnt && a->pattim==b->pattim);
        if(a->userflag.b.h==2)bullets++;
    }
    scd_object_view views[32];unsigned count=scd_objects_views(views,32);
    for(unsigned n=0;n<count;n++){
        REQUIRE(views[n].type==kind);
        unsigned pri=views[n].subtype==0?2:views[n].subtype==1?3:4;
        REQUIRE(scd_ppz_priority(views[n])==pri);
    }
    if(before.yspeed.w!=-1792 && expected.yspeed.w==-1792)launches++;
    updates++;
}
static void lifetime(void){
    scd_objects_layout(NULL,0);scd_objects_reset(0,0);actwk[0]=player(200,100,0);
    /* actwkchk may allocate before the base, unlike the earlier trap family. */
    REQUIRE(scd_objects_spawn(SCD_OBJ_LOST_RING,16383,100,0,0)==0);actwk[1].xspeed.w=256;
    REQUIRE(scd_objects_spawn(SCD_OBJ_GANDAIR3,1000,800,0,0)==1);
    scd_objects_step(200,100);
    REQUIRE(actwk[1].actno==SCD_OBJ_GANDAIR3 && actwk[1].userflag.b.h==1 && !actwk[1].r_no0);
    scd_objects_step(200,100);REQUIRE(actwk[1].r_no0==2);
    scd_objects_clear_live();REQUIRE(!scd_objects_get().active);
    scd_placement placement={1000,800,SCD_OBJ_GANDAIR3,0,0,7,0};
    scd_objects_layout(&placement,1);scd_objects_reset(0,1);actwk[0]=player(1000,700,0);
    scd_act_camera(840,588); /* retail spawner: camera window (cc_traps_test.c) */
    scd_objects_step(1000,700);REQUIRE(scd_objects_get().active==2);
    actwk[0].xposi.w.h=5000;scd_act_camera(4840,588);scd_objects_step(5000,700);REQUIRE(!scd_objects_get().active);
    scd_objects_layout(NULL,0);
    /* Failed allocation retries; it must not duplicate the core once ready. */
    scd_objects_reset(0,0);actwk[0]=player(200,100,0);
    REQUIRE(scd_objects_spawn(SCD_OBJ_GANDAIR3,1000,800,0,0)==0);
    for(unsigned n=1;n<SCD_OBJECT_CAPACITY;n++)REQUIRE(scd_objects_spawn(SCD_OBJ_RING,2000,800,0,0)==(int)n);
    scd_objects_step(200,100);REQUIRE(!actwk[1].r_no0);
    /* COLI3.C pcol collects one ring per update (cc_touch_arbitrate); each
       holds its slot through its sparkle. The base waits while every slot is
       held, and allocates in the update after the first sparkle frees one. */
    unsigned held=0;
    for(;held<400 && !actwk[1].r_no0;held++){
        actwk[0]=player(2000,800,0);
        scd_objects_collision_begin();scd_objects_collision_end();scd_objects_step(2000,800);
    }
    REQUIRE(actwk[1].r_no0==2 && held>24 && held<400 && scd_objects_get().active>=SCD_OBJECT_CAPACITY-1);
    /* The player stays until every ring is collected and has sparkled out. */
    for(unsigned tick=0;tick<SCD_OBJECT_CAPACITY+40;tick++){
        actwk[0]=player(2000,800,0);
        scd_objects_collision_begin();scd_objects_collision_end();scd_objects_step(2000,800);
    }
    actwk[0]=player(200,100,0);scd_objects_step(200,100);
    REQUIRE(actwk[1].r_no0==2 && scd_objects_get().active==2);
    scd_objects_step(200,100);REQUIRE(scd_objects_get().active==2);
}
int main(void){
    for(unsigned era=0;era<4;era++){
        load(era);
        for(unsigned flags=0;flags<4;flags++)for(unsigned sub=0;sub<3;sub++){
            for(unsigned direction=0;direction<(sub==2?2:1);direction++){
                gsetup(era,sub,flags);
                actwk[1].actfree[16]=actwk[100].actfree[16]=sub==2?direction:0;
                for(frame=0;frame<1200;frame++){
                    /* Alternate near/far positions to prove trigger gating and
                       repeated firing/retraction without imposing a rider. */
                    gtick(player(1000+(frame%300<60?140:80),650,0));
                }
            }
        }
        for(unsigned riding=0;riding<2;riding++){
            gsetup(era,1,0);
            for(frame=0;frame<1200;frame++){
                unsigned previous=actwk[1].r_no0;
                sprite_status p=player(1000+(riding?0:100),actwk[1].yposi.w.h-39,0);
                gtick(p);if(previous==8 && actwk[1].r_no0==2)cycles++;
            }
        }
        /* Full solid contacts in each active core phase. */
        for(unsigned state=2;state<=8;state+=2)
        for(int dx=-27;dx<=27;dx++)for(int dy=-43;dy<=43;dy++)for(unsigned mode=0;mode<4;mode++){
            gsetup(era,1,0);frame=0;gtick(player(1200,600,0));
            actwk[1].r_no0=actwk[100].r_no0=state;
            actwk[1].actfree[16]=actwk[100].actfree[16]=state==8?30:0;
            actwk[1].actfree[17]=actwk[100].actfree[17]=state>=4?24:0;
            frame=1;gtick(player(1000+dx,800+dy,mode));contacts++;
        }
        /* COLI3 bullet radius, normal/reduced player boxes and hurt guard. */
        for(int dx=-14;dx<=14;dx++)for(int dy=-26;dy<=26;dy++)for(unsigned mode=0;mode<4;mode++){
            gsetup(era,2,0);frame=0;gtick(player(1200,600,0));
            frame=1;sprite_status p=player(actwk[1].xposi.w.h+dx,800+dy,mode);
            if(mode==2)p.patno=57;
            gtick(p);contacts++;
        }
    }
    load(0);lifetime();REQUIRE(launches>0 && bullets>0 && cycles>0);
    printf("PASS: %u assertions; %u original/native updates; %u contacts; %u launches; %u bullet updates; %u cycles\n",checks,updates,contacts,launches,bullets,cycles);
}
