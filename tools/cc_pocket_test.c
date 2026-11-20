#include "cc_enemy_test_fixture.h"
#include "act.h"
void ref_pocket(sprite_status*);void ref_points(sprite_status*);
void pocket_viewport(sprite_status*);int pocket_frameout_s00(sprite_status*,short);
static unsigned cycles,edge_cases,lifecycle_cases,allocation_cases,timer_cases,popup_cases;
static int original_life(sprite_status *o){return pocket_frameout_s00(o,o->xposi.w.h);}
static void normalize(sprite_status *o){
    if(o->actno!=SCD_OBJ_POCKET)return;
    unsigned word=o->userflag.b.h<0?24:25,link=scd_word_get(o,word);
    if(link>=100 && link<128)scd_word_set(o,word,link-99);
}
static void camera(int x,int y){scd_act_camera(x,y);scra_h_posit.w.h=x;scra_v_posit.w.h=y;}
static void begin(unsigned era,unsigned sub,unsigned flags){setup(era,sub,flags);camera(840,688);editmode.w=0;}
static void cycle(unsigned era,unsigned flags){
    begin(era,255,flags);
    scd_player_progress initial=scd_player_progress_get();
    for(unsigned run=0;run<6;run++){
        sprite_status p=player(1000,784,0);p.xposi.w.l=12345;p.yposi.w.l=54321;
        frame=0;tick(p);
        if(era==2){REQUIRE(!actwk[1].actno);return;}
        REQUIRE(actwk[1].r_no0==4 && scd_word_get(actwk+1,23)==8);
        REQUIRE(actwk[0].actfree[2]==1 && actwk[0].yspeed.w==-2048);
        unsigned grants=0,hidden=0;
        for(frame=1;frame<300;frame++){
            unsigned oldscore=scd_player_progress_get().score;
            tick(actwk[0]);
            grants+=scd_player_progress_get().score!=oldscore;
            hidden+=!!(actwk[0].actfree[2]&64);
            if(actwk[1].r_no0==2)break;
        }
        REQUIRE(frame==245 && hidden==115);
        REQUIRE(grants==(run<3?2:run==3?1:0));
        REQUIRE(!(actwk[0].actfree[2]&65) && actwk[0].yspeed.w==-2048);
        REQUIRE((uint16_t)actwk[0].xposi.w.l==12345 && (uint16_t)actwk[0].yposi.w.l==54321);
        cycles++;
    }
    REQUIRE(scd_player_progress_get().score-initial.score==700);
}
static void allocation(unsigned era,unsigned state){
    begin(era,255,0);frame=0;tick(player(1000,784,0));
    if(era==2)return;
    for(unsigned n=1;n<96;n++){
        REQUIRE(scd_objects_spawn(SCD_OBJ_RING,15000,100,0,0)==(int)n);
        if(n<28)actwk[100+n]=actwk[1+n];
    }
    actwk[1].r_no0=actwk[100].r_no0=state;
    scd_word_set(actwk+1,23,0);scd_word_set(actwk+100,23,0);
    unsigned old=scd_player_progress_get().score;
    frame=1;tick(actwk[0]);
    if(state==4){REQUIRE(!actwk[1].actno && actwk[0].actfree[2]==1);}
    else{REQUIRE(actwk[1].r_no0==state+2 && scd_player_progress_get().score==old+100);}
    allocation_cases++;
}
static void earlier_allocation(unsigned era){
    if(era==2)return;
    for(unsigned state=4;state<=12;state+=state==4?6:2){
        begin(era,255,0);scd_objects_clear_live();memset(actwk+100,0,28*sizeof(*actwk));
        /* A real expiring point actor frees slot zero before a later pocket
           dispatch. Its replacement must wait until the following update. */
        for(unsigned n=0;n<96;n++){
            unsigned kind=n==0?SCD_OBJ_CC_POINTS:n==10?SCD_OBJ_POCKET:SCD_OBJ_RING;
            REQUIRE(scd_objects_spawn(kind,n==10?1000:15000,n==10?800:100,n==10?255:n==0?128:0,0)==(int)n);
        }
        actwk[1].r_no0=2;actwk[1].actfree[0]=1;
        actwk[11].r_no0=state;scd_word_set(actwk+11,23,0);scd_word_set(actwk+11,26,7);
        actwk[11].actfree[20]=255;
        for(unsigned n=0;n<28;n++)actwk[100+n]=actwk[1+n];
        sprite_status p=player(1000,784,0);p.actfree[2]=1;p.yspeed.w=-2048;
        frame=0;tick(p);
        REQUIRE(actwk[1].actno==(state==4?SCD_OBJ_POCKET:SCD_OBJ_CC_POINTS) && !actwk[1].r_no0);
        REQUIRE(actwk[1].actflg==0 && !actwk[1].sprhsize && !actwk[1].sprvsize);
        frame=1;tick(actwk[0]);REQUIRE(actwk[1].r_no0==2);allocation_cases++;
    }
}
static void timer_edges(unsigned era){
    if(era==2)return;
    /* Both signed wrap boundaries and every low-word value; transitions are
       compared with the independently compiled routines, including expiry. */
    for(unsigned state=4;state<=20;state+=2)for(unsigned timer=0;timer<65536;timer++){
        begin(era,255,0);
        actwk[1].r_no0=actwk[100].r_no0=state;
        scd_word_set(actwk+1,23,timer);scd_word_set(actwk+100,23,timer);
        if(state==18){
            REQUIRE(scd_objects_spawn(SCD_OBJ_POCKET,1000,800,0,0)==1);
            scd_word_set(actwk+2,25,1);actwk[101]=actwk[2];scd_word_set(actwk+101,25,100);
            scd_word_set(actwk+1,24,2);scd_word_set(actwk+100,24,101);
        }
        frame=timer;tick(player(200,100,16));timer_cases++;
    }
}
static void popup_timelines(unsigned era){
    for(unsigned pose=0;pose<6;pose++)for(unsigned flags=0;flags<4;flags++){
        begin(era,255,0);scd_objects_clear_live();memset(actwk+100,0,28*sizeof(*actwk));
        REQUIRE(scd_objects_spawn(SCD_OBJ_CC_POINTS,1000,800,128+pose,flags)==0);
        actwk[100]=actwk[1];
        for(frame=0;frame<24;frame++)tick(player(200,100,16));
        REQUIRE(!actwk[1].actno);popup_cases++;
    }
}
int main(void){
    test_kind=SCD_OBJ_POCKET;test_child_kind=SCD_OBJ_CC_POINTS;parent_priority=0;
    original_actor=ref_pocket;original_child=ref_points;original_draw=pocket_viewport;
    original_frameout=original_life;normalize_original=normalize;zero_original_allocation=1;
    verify_audio=1;scd_player_audio_set(audio_record);
    for(unsigned era=0;era<4;era++){
        load(era);
        for(unsigned flags=0;flags<4;flags++)cycle(era,flags);
        for(int x=-26;x<=25;x++)for(int y=-26;y<=-7;y++)for(unsigned mode=0;mode<8;mode++){
            begin(era,255,mode&3);sprite_status p=player(1000+x,800+y,0);
            p.r_no0=(mode&3)*2;p.yspeed.w=mode&4?-1:0;
            frame=0;tick(p);edge_cases++;
        }
        for(unsigned sub=128;sub<256;sub++){
            begin(era,sub,0);frame=0;tick(player(1000,784,0));
        }
        for(int x=-1024;x<=1024;x++)for(unsigned y=0;y<2;y++){
            begin(era,255,0);camera(1000+x,y?100:688);frame=0;tick(player(200,100,16));lifecycle_cases++;
        }
        begin(era,255,0);editmode.w=1;frame=0;tick(player(1000,784,0));
        REQUIRE(era==2?!actwk[1].actno:actwk[1].r_no0==2);editmode.w=0;
        for(unsigned state=4;state<=12;state+=state==4?6:2)allocation(era,state);
        earlier_allocation(era);
        timer_edges(era);popup_timelines(era);
    }
    printf("Pocket original comparison: %u assertions, %u updates, %u capture edges, %u cycles, %u lifecycle cases, %u allocation cases, %u timer cases, %u popup timelines\n",checks,updates,edge_cases,cycles,lifecycle_cases,allocation_cases,timer_cases,popup_cases);
    return 0;
}
