#include "cc_enemy_test_fixture.h"
void tentou(sprite_status*);
void bakuha(sprite_status*);
void tensuu_set(sprite_status *o){REQUIRE(o->r_no1==1);}
static unsigned states[6],bomb_states[5],explosions,transitions;
static sprite_status firing_parent;
static unsigned firing_era,current_era;
static void setlong(sprite_status *o,unsigned byte,int value){memcpy(o->actfree+byte,&value,4);}
static void ten_tick(sprite_status before){
    unsigned previous=actwk[1].r_no0;
    sprite_status prior=actwk[1];unsigned projectiles=scd_objects_get().projectiles;
    tick(before);
    if(!firing_parent.actno && scd_objects_get().projectiles>projectiles){firing_parent=prior;firing_era=current_era;}
    if(actwk[1].actno==SCD_OBJ_TENTOU){
        unsigned state=actwk[1].r_no0/2;
        if(actwk[1].userflag.b.h>0){REQUIRE(state<5);bomb_states[state]++;}
        else{REQUIRE(state<6);states[state]++;}
        if(previous!=actwk[1].r_no0)transitions++;
    }
    if(actwk[1].actno==SCD_OBJ_EXPLOSION){
        explosions++;
        if(actwk[100].r_no1==1)compare(actwk+1,actwk+100);
        /* The conversion update still submits the bomb's existing pose. */
        if(actwk[100].r_no1==1 && actwk[100].colino==139){
            compare(actwk+1,actwk+100);
            scd_object_view v;REQUIRE(scd_objects_views(&v,1)==1);
            REQUIRE(v.type==SCD_OBJ_TENTOU && v.frame==actwk[100].patno && scd_ppz_priority(v)==2);
        }
    }
}
int main(void){
    test_kind=SCD_OBJ_TENTOU;original_actor=tentou;original_bomb_effect=bakuha;
    const unsigned subs[]={0,255,128,1,127};
    for(unsigned era=0;era<4;era++){
        current_era=era;
        load(era);
        /* Real original maps: multiple floor profiles, gaps and walls, both
           directions, every subtype class and every orientation. */
        for(unsigned sub=0;sub<5;sub++)for(unsigned flip=0;flip<4;flip++)
        for(unsigned direction=0;direction<2;direction++)for(unsigned section=0;section<12;section++){
            setup(era,subs[sub],flip);
            actwk[1].xposi.w.h=actwk[100].xposi.w.h=256+section*960;
            actwk[1].yposi.w.h=actwk[100].yposi.w.h=128+(section%4)*320;
            for(frame=0;frame<400;frame++){
                ten_tick(player(actwk[1].xposi.w.h+(direction?64:-64),actwk[1].yposi.w.h,16));
                if(actwk[1].actno!=test_kind)break;
            }
        }
        if(era==2)continue;
        /* Terrain branch boundaries from every parent state, including the
           original SUB adjustment during fall and ADD during lateral motion. */
        for(unsigned state=2;state<=10;state+=2)for(unsigned damaged=0;damaged<2;damaged++)
        for(unsigned x=512;x<12000;x+=97)for(unsigned y=256;y<1536;y+=43){
            setup(era,damaged?255:0,0);
            for(unsigned n=0;n<2;n++){
                sprite_status *o=actwk+(n?100:1);o->r_no0=state;o->xposi.w.h=x;o->yposi.w.h=y;
                o->sprhsize=o->sprvsize=14;o->sprpri=1;o->sproffset=42090;
                o->actfree[21]=damaged?0:255;
                setlong(o,0,x&1?-49152:49152);setlong(o,4,y&1?-12288:12288);setlong(o,8,o->yposi.l);
                scd_word_set(o,29,x%256);
            }
            frame=0;ten_tick(player(x+81,y+81,16));
        }
        /* Original COLI3 body 6 is 16x16; bomb 139 is 8x8 and cannot be
           defeated by spin/invincibility. Include both player hitbox sizes. */
        for(unsigned bomb=0;bomb<2;bomb++)for(int dx=-26;dx<=26;dx++)
        for(int dy=-36;dy<=36;dy++)for(unsigned mode=0;mode<32;mode++){
            setup(era,bomb?1:0,0);frame=0;ten_tick(player(200,100,0));
            actwk[1].r_no0=actwk[100].r_no0=bomb?4:8;
            scd_word_set(actwk+1,23,120);scd_word_set(actwk+100,23,120);
            frame=1;ten_tick(player(actwk[1].xposi.w.h+dx,actwk[1].yposi.w.h+dy,mode));contacts++;
        }
        /* Bomb contact flag, exact wait/blink boundaries and conversion. */
        for(unsigned state=2;state<=8;state+=2)for(unsigned timer=1;timer<=121;timer++)for(unsigned hit=0;hit<2;hit++){
            setup(era,1,0);frame=0;ten_tick(player(200,100,0));
            actwk[1].r_no0=actwk[100].r_no0=state;actwk[1].colicnt=actwk[100].colicnt=hit;
            scd_word_set(actwk+1,23,timer);scd_word_set(actwk+100,23,timer);
            frame=1;ten_tick(player(200,100,0));
        }
        /* Follow a whole bomb countdown, terminal animation frame and removal. */
        setup(era,1,0);frame=0;ten_tick(player(200,100,0));
        actwk[1].r_no0=actwk[100].r_no0=4;
        scd_word_set(actwk+1,23,120);scd_word_set(actwk+100,23,120);
        for(frame=1;frame<=264;frame++)ten_tick(player(200,100,0));
        REQUIRE(!actwk[1].actno);
        /* The conversion still has the old collision byte until baku_init
           runs, so the next pre-object collision scan must see the bomb. */
        setup(era,1,0);frame=0;ten_tick(player(200,100,0));
        actwk[1].r_no0=actwk[100].r_no0=8;frame=1;ten_tick(player(200,100,0));
        frame=2;ten_tick(player(actwk[1].xposi.w.h,actwk[1].yposi.w.h,0));
    }
    for(unsigned n=1;n<6;n++)REQUIRE(states[n]);
    for(unsigned n=1;n<5;n++)REQUIRE(bomb_states[n]);
    REQUIRE(explosions && transitions && sparkles);
    REQUIRE(firing_parent.actno);
    load(firing_era);setup(firing_era,0,0);actwk[1]=actwk[100]=firing_parent;fail_alloc=1;
    for(unsigned i=1;i<96;i++)REQUIRE(scd_objects_spawn(SCD_OBJ_RING,15000,100,0,0)==(int)i);
    actwk[0]=player(200,100,16);tentou(actwk+100);scd_objects_step(200,100);
    compare(actwk+1,actwk+100);REQUIRE(!scd_objects_get().projectiles);fail_alloc=0;
    /* After an earlier lost ring leaves the map, the bomb waits until the next
       update before appearing or colliding. */
    scd_objects_reset(firing_era,0);actwk[0]=player(200,100,0);
    REQUIRE(scd_objects_spawn(SCD_OBJ_LOST_RING,16383,100,0,0)==0);actwk[1].xspeed.w=256;
    REQUIRE(scd_objects_spawn(SCD_OBJ_TENTOU,1000,800,0,0)==1);actwk[2]=firing_parent;
    scd_objects_step(200,100);REQUIRE(actwk[1].actno==SCD_OBJ_TENTOU && !actwk[1].r_no0 && !actwk[1].colino);
    scd_object_view v[96];REQUIRE(scd_objects_views(v,96)==1);
    scd_objects_step(200,100);REQUIRE(actwk[1].r_no0 && scd_objects_views(v,96)==2);
    /* Mixed enemy families must share one ordered collision scan. */
    load(0);setup(0,0,0);REQUIRE(scd_objects_spawn(SCD_OBJ_GA,1000,800,0,0)==1);
    actwk[1].r_no0=8;actwk[1].colino=6;actwk[2].r_no0=8;actwk[2].colino=38;
    actwk[2].mstno.b.h=2;scd_word_set(actwk+2,23,65);
    actwk[0]=player(1000,800,1);scd_objects_step(1000,800);
    REQUIRE(actwk[1].actno==SCD_OBJ_EXPLOSION && actwk[2].actno==SCD_OBJ_GA && scd_objects_get().defeated==1);
    printf("Tentou original comparison: %u assertions, %u updates, %u contacts, %u bomb updates, %u transitions, %u explosion observations\n",checks,updates,contacts,sparkles,transitions,explosions);
    return 0;
}
