#include "cc_enemy_test_fixture.h"
#include "act.h"
int main(void){
    const unsigned subs[]={0,255,128,1,127};
    for(unsigned era=0;era<4;era++){
        load(era);
        for(unsigned sub=0;sub<5;sub++)for(unsigned flip=0;flip<4;flip++)for(unsigned direction=0;direction<2;direction++){
            setup(era,subs[sub],flip);
            for(frame=0;frame<(era==2 && sub<3?1:1200);frame++)tick(player(direction?1500:500,100,0));
        }
        if(era==2)continue;
        /* Collision is checked against the PRE-movement pose, including the
           initially intangible emergence phase and both real hitbox sizes. */
        for(unsigned state=4;state<=8;state+=2)
        for(int dx=-26;dx<=26;dx++)for(int dy=-34;dy<=34;dy++)for(unsigned mode=0;mode<32;mode++){
            setup(era,0,0);frame=0;tick(player(200,100,0));
            actwk[1].r_no0=actwk[100].r_no0=state;
            actwk[1].colino=actwk[100].colino=state==4?0:state==6?37:38;
            actwk[1].mstno.b.h=actwk[100].mstno.b.h=state==8?2:state==6?1:0;
            frame=1;tick(player(1000+dx,800+dy,mode));contacts++;
        }
    }
    /* A full pool skips particle allocation without extending the cycle. */
    load(0);setup(0,0,0);fail_alloc=1;
    for(unsigned i=1;i<96;i++)REQUIRE(scd_objects_spawn(SCD_OBJ_RING,2000,100,0,0)==(int)i);
    for(frame=0;frame<400;frame++){
        actwk[0]=player(200,100,0);ga(actwk+100);scd_objects_step(200,100);compare(actwk+1,actwk+100);
    }
    fail_alloc=0;
    /* Only the first overlapping enemy may collide in a simulation update. */
    setup(0,0,0);REQUIRE(scd_objects_spawn(SCD_OBJ_GA,1000,800,0,0)==1);actwk[101]=actwk[2];
    for(unsigned n=0;n<2;n++){
        actwk[n+1].r_no0=actwk[n+100].r_no0=8;actwk[n+1].colino=actwk[n+100].colino=38;
        scd_word_set(actwk+n+1,23,65);scd_word_set(actwk+n+100,23,65);
        actwk[n+1].mstno.b.h=actwk[n+100].mstno.b.h=2;
    }
    frame=0;tick(player(1000,800,1));REQUIRE(actwk[2].actno==SCD_OBJ_GA);
    frame=1;tick(player(1000,800,1));REQUIRE(scd_objects_get().defeated==2);
    for(unsigned power=0;power<3;power++)for(unsigned hp=0;hp<3;hp++)for(unsigned immune=0;immune<2;immune++){
        setup(0,0,0);frame=0;tick(player(200,100,0));
        actwk[1].r_no0=actwk[100].r_no0=8;actwk[1].colino=actwk[100].colino=38;
        actwk[1].colicnt=actwk[100].colicnt=hp;
        actwk[1].mstno.b.h=actwk[100].mstno.b.h=2;
        plpower_a=power==1;plpower_m=power==2;
        sprite_status p=player(1000,800,immune?8:0);p.xspeed.w=p.yspeed.w=-32768;
        frame=1;tick(p);
    }
    /* A sparkle can occupy a newly free slot BEFORE its parent. It must not
       draw its uninitialized ring frame before that slot's next dispatch. */
    scd_objects_reset(0,0);actwk[0]=player(200,100,0);
    REQUIRE(scd_objects_spawn(SCD_OBJ_RING,200,100,0,0)==0);
    REQUIRE(scd_objects_spawn(SCD_OBJ_GA,1000,800,0,0)==1);
    for(frame=0;frame<300;frame++){
        /* The ring is collected in pcol (cc_touch_arbitrate). */
        scd_objects_collision_begin();scd_objects_collision_end();scd_objects_step(200,100);
        if(actwk[1].actno==SCD_OBJ_GA)break;
    }
    REQUIRE(frame<300 && !actwk[1].r_no0 && actwk[1].userflag.b.h==1);
    scd_object_view views[96];REQUIRE(scd_objects_views(views,96)==1);
    scd_objects_step(200,100);REQUIRE(scd_objects_views(views,96)==2 && actwk[1].patno==4);
    /* Destroy-on-Good-Future cannot refill the pool with another explosion
       every update while the same placement remains in the load window. */
    scd_placement placement={1000,800,SCD_OBJ_GA,0,0,7,0};
    scd_objects_layout(&placement,1);scd_objects_reset(2,1);actwk[0]=player(1000,100,0);
    scd_act_camera(840,0); /* retail Object Spawner: the camera window streams */
    for(frame=0;frame<60;frame++)scd_objects_step(1000,100);
    /* PLAYSUB.C bakuha: the suicide explosion leaves its points popup (gone
       after 24 updates) and a flower that never frames out. */
    REQUIRE(scd_objects_get().active==1 && scd_objects_get().spawned==2 && actwk[1].actno==SCD_OBJ_FLOWER);
    actwk[0].xposi.w.h=3000;scd_act_camera(2840,0);scd_objects_step(3000,100);
    actwk[0].xposi.w.h=1000;scd_act_camera(840,0);scd_objects_step(1000,100);
    REQUIRE(scd_objects_get().active==2 && scd_objects_get().spawned==3 && actwk[2].actno==SCD_OBJ_EXPLOSION);
    scd_objects_layout(NULL,0);
    printf("GA original comparison: %u assertions, %u updates, %u contact cases, %u particle updates, %u defeat/suicide observations\n",checks,updates,contacts,sparkles,defeats);
    return 0;
}
