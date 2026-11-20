#include "cc_enemy_test_fixture.h"
#include "act.h"
void ene_kama(sprite_status*);void tama_kama(sprite_status*);void banpa(sprite_status*);
void original_viewport(sprite_status*);short original_special_contact(sprite_status*,sprite_status*);
void main_attack(sprite_status *p,sprite_status *o){(void)p;(void)o;abort();}
short eggman_chk(sprite_status *p,sprite_status *o,char n){(void)p;(void)o;(void)n;abort();}
int frameout_s00(sprite_status *o,short x){(void)o;(void)x;return 0;}
static unsigned parent_states[7],blade_states[3],reversals,deflections,bumper_contacts;
static void camera(int x,int y){scd_act_camera(x,y);scra_h_posit.w.h=x;scra_v_posit.w.h=y;}
static void observed_tick(sprite_status p){
    unsigned facing=actwk[1].cddat&1;
    tick(p);
    if(actwk[1].actno==SCD_OBJ_KAMA){REQUIRE(actwk[1].r_no0/2<7);parent_states[actwk[1].r_no0/2]++;reversals+=(actwk[1].cddat&1)!=facing;}
    for(unsigned n=1;n<=28;n++)if(actwk[n].actno==SCD_OBJ_KAMA_BLADE){
        REQUIRE(actwk[n].r_no0/2<3);blade_states[actwk[n].r_no0/2]++;deflections+=actwk[n].mstno.b.h==1;
    }
}
static void blades(unsigned era){
    test_kind=test_child_kind=SCD_OBJ_KAMA_BLADE;original_actor=tama_kama;parent_priority=1;
    for(unsigned state=0;state<=4;state+=2)for(unsigned timer=1;timer<=65;timer++)
    for(unsigned direction=0;direction<2;direction++)for(unsigned mode=0;mode<8;mode++){
        setup(era,0,0);camera(840,688);
        for(unsigned n=0;n<2;n++){
            sprite_status *o=actwk+(n?100:1),*parent=actwk+(n?101:2);
            parent->actno=SCD_OBJ_KAMA;parent->r_no0=6;scd_word_set(parent,24,65535);
            o->r_no0=state;o->actfree[4]=direction;o->sprpri=1;o->sprhs=o->sprvsize=4;
            o->sproffset=9202;o->colino=state==4?135:0;o->xspeed.w=direction?768:-768;
            scd_word_set(o,26,n?101:2);scd_word_set(o,24,timer);scd_word_set(o,28,timer);
        }
        sprite_status p=player(mode&1?1000:200,mode&1?800:100,mode&2?1:0);
        if(mode&2)p.cddat|=4;
        plpower_m=!!(mode&4);frame=0;observed_tick(p);
    }
    /* The 56x56 deflection region is wider than the damage hitbox. Boundaries
       are half-open, independent of spin animation or player injury routine. */
    for(int dx=-30;dx<=30;dx++)for(int dy=-30;dy<=30;dy++)for(unsigned mode=0;mode<8;mode++){
        setup(era,0,0);camera(840,688);
        for(unsigned n=0;n<2;n++){
            sprite_status *o=actwk+(n?100:1);o->r_no0=4;o->sprpri=1;o->patno=3;
            o->colino=0;o->xspeed.w=0;scd_word_set(o,28,1);
        }
        sprite_status p=player(1000+dx,800+dy,mode&1?1:0);if(mode&2)p.cddat|=4;
        plpower_m=!!(mode&4);frame=0;observed_tick(p);contacts++;
    }
    /* Waiting blades disappear with their parent; flying blades survive it. */
    for(unsigned state=2;state<=4;state+=2){
        setup(era,0,0);camera(840,688);
        actwk[1].r_no0=actwk[100].r_no0=state;scd_word_set(actwk+1,26,2);scd_word_set(actwk+100,26,101);
        scd_word_set(actwk+1,24,2);scd_word_set(actwk+100,24,2);
        scd_word_set(actwk+1,28,60);scd_word_set(actwk+100,28,60);
        frame=0;observed_tick(player(200,100,16));REQUIRE(!!actwk[1].actno==(state==4));
    }
}
static void scarce_slot(void){
    /* One earlier slot becomes free before the parent dispatch. Only its
       first (64-tick) blade fits, and it must wait for the next update. */
    test_kind=SCD_OBJ_KAMA;test_child_kind=SCD_OBJ_KAMA_BLADE;original_actor=ene_kama;parent_priority=3;
    load(0);setup(0,0,0);scd_objects_reset(0,0);memset(actwk+100,0,28*sizeof(*actwk));camera(840,688);
    REQUIRE(scd_objects_spawn(SCD_OBJ_LOST_RING,16383,100,0,0)==0);actwk[1].xspeed.w=256;
    REQUIRE(scd_objects_spawn(SCD_OBJ_KAMA,1000,800,0,0)==1);
    actwk[2].r_no0=4;actwk[2].sprpri=3;actwk[101]=actwk[2];
    for(unsigned n=2;n<96;n++){
        REQUIRE(scd_objects_spawn(SCD_OBJ_RING,15000,100,0,0)==(int)n);
        if(n<28)actwk[n+100]=actwk[n+1];
    }
    actwk[0]=player(1000,800,16);ene_kama(actwk+101);scd_objects_step(1000,800);
    compare(actwk+2,actwk+101);compare(actwk+1,actwk+100);
    REQUIRE(actwk[1].actno==SCD_OBJ_KAMA_BLADE && !actwk[1].r_no0 && !actwk[1].colino);
    REQUIRE(scd_word_get(actwk+1,24)==64 && scd_objects_get().projectiles==1);
    scd_object_view v[96];unsigned n=scd_objects_views(v,96);
    for(unsigned k=0;k<n;k++)REQUIRE(v[k].type!=SCD_OBJ_KAMA_BLADE);
    tama_kama(actwk+100);ene_kama(actwk+101);scd_objects_step(1000,800);
    compare(actwk+1,actwk+100);compare(actwk+2,actwk+101);
    REQUIRE(actwk[1].r_no0==2 && !actwk[1].colino);
}
int main(void){
    original_draw=original_viewport;original_special=original_special_contact;original_child=tama_kama;
    verify_audio=1;scd_player_audio_set(audio_record);
    for(unsigned era=0;era<4;era++){
        load(era);test_kind=SCD_OBJ_KAMA;test_child_kind=SCD_OBJ_KAMA_BLADE;original_actor=ene_kama;parent_priority=3;
        unsigned subs[]={0,1,255,128};
        for(unsigned sub=0;sub<4;sub++)for(unsigned flip=0;flip<4;flip++)
        for(unsigned section=0;section<12;section++){
            setup(era,subs[sub],flip);
            actwk[1].xposi.w.h=actwk[100].xposi.w.h=256+section*960;
            actwk[1].yposi.w.h=actwk[100].yposi.w.h=256+(section%4)*288;
            for(frame=0;frame<600;frame++){
                camera(actwk[1].xposi.w.h-160,actwk[1].yposi.w.h-112);
                observed_tick(player(actwk[1].xposi.w.h+(frame&128?80:-80),actwk[1].yposi.w.h,16));
                if(actwk[1].actno!=test_kind)break;
            }
        }
        if(era!=2){
            /* Console attack range is |dx|<96 and |dy|<32, unlike the PC
               reconstruction's unrestricted X and 96-pixel Y threshold. */
            for(int dx=-98;dx<=98;dx++)for(int dy=-34;dy<=34;dy++)for(unsigned mode=0;mode<4;mode++){
                setup(era,mode&1?255:0,0);camera(840,688);
                for(unsigned n=0;n<2;n++){
                    sprite_status *o=actwk+(n?100:1);o->r_no0=4;o->sprpri=3;
                    if(mode&2)o->actflg&=127;
                }
                frame=0;observed_tick(player(1000+dx,800+dy,16));
                REQUIRE(scd_objects_get().projectiles==((!(mode&3) && abs(dx)<96 && abs(dy)<32)?2u:0u));
            }
            /* Attack/turn timer boundaries and failed allocation. */
            for(unsigned state=4;state<=12;state+=2)for(unsigned timer=1;timer<=121;timer++)for(unsigned full=0;full<2;full++){
                setup(era,0,0);camera(840,688);
                for(unsigned n=0;n<2;n++){
                    sprite_status *o=actwk+(n?100:1);o->r_no0=state;o->sprpri=3;o->sprhsize=16;o->sprvsize=20;
                    scd_word_set(o,24,timer);
                }
                fail_alloc=full;if(full)for(unsigned n=1;n<96;n++){
                    REQUIRE(scd_objects_spawn(SCD_OBJ_RING,15000,100,0,0)==(int)n);
                    if(n<28)actwk[100+n]=actwk[1+n];
                }
                frame=0;observed_tick(player(1040,800,16));fail_alloc=0;
            }
            /* Body and blade damage contacts, visibility, control lock and
               reduced player bounds all go through compiled COLI3.C. */
            for(int dx=-26;dx<=26;dx++)for(int dy=-36;dy<=36;dy++)for(unsigned mode=0;mode<32;mode++){
                setup(era,255,0);camera(840,688);actwk[1].r_no0=actwk[100].r_no0=12;
                actwk[1].colino=actwk[100].colino=6;actwk[1].sprpri=actwk[100].sprpri=3;
                scd_word_set(actwk+1,24,72);scd_word_set(actwk+100,24,72);
                frame=0;observed_tick(player(1000+dx,800+dy,mode));contacts++;
            }
        }
        blades(era);
        test_kind=SCD_OBJ_BANPA;test_child_kind=0;original_actor=banpa;parent_priority=1;
        for(unsigned sub=0;sub<256;sub++){
            setup(era,sub,sub&3);camera(840,688);
            for(frame=0;frame<400;frame++)observed_tick(player(200,100,16));
        }
        for(int dx=-42;dx<=42;dx++)for(int dy=-35;dy<=35;dy++)for(unsigned mode=0;mode<8;mode++){
            setup(era,0,0);camera(840,688);frame=0;observed_tick(player(200,100,0));
            frame=1;observed_tick(player(1000+dx,800+dy,mode*4));contacts++;bumper_contacts++;
        }
    }
    /* Exact viewport edges and vertical-wrap cases from original ACTION.C. */
    test_kind=SCD_OBJ_BANPA;test_child_kind=0;original_actor=banpa;parent_priority=1;
    for(int cy=0;cy<=2048;cy+=128)for(int x=-34;x<=354;x+=2)for(int y=-18;y<=242;y+=2){
        setup(0,0,0);camera(1000,cy);actwk[1].xposi.w.h=actwk[100].xposi.w.h=1000+x;
        actwk[1].yposi.w.h=actwk[100].yposi.w.h=cy+y;frame=0;observed_tick(player(200,100,16));
    }
    for(unsigned n=1;n<7;n++)REQUIRE(parent_states[n]);for(unsigned n=1;n<3;n++)REQUIRE(blade_states[n]);
    REQUIRE(reversals && deflections && bumper_contacts);
    scarce_slot();
    printf("Kama/Banpa original comparison: %u assertions, %u updates, %u contacts, %u blade updates, %u reversals, %u deflections, %u bumper contacts\n",checks,updates,contacts,sparkles,reversals,deflections,bumper_contacts);
    return 0;
}
