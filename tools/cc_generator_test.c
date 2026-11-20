#include "cc_enemy_test_fixture.h"
#include "act.h"
void ref_et(sprite_status*);void main_attack(sprite_status*,sprite_status*);
void bakuha(sprite_status*);void generator_viewport(sprite_status*);int generator_frameout(sprite_status*,short);
void tensuu_set(sprite_status *o){REQUIRE(o->r_no1==1);}
static short special(sprite_status *p,sprite_status *o){REQUIRE(o->colino==250);main_attack(p,o);return -1;}
static int life(sprite_status *o){return generator_frameout(o,o->xposi.w.h);}
static void gen_tick(sprite_status before){
    scd_player_progress score=scd_player_progress_get();unsigned old_good=generate_flag;audio_count=0;
    actwk[0]=before;
    if(actwk[0].actfree[19])actwk[0].actfree[19]+=99;
    if(actwk[0].colino)actwk[0].colino+=99;
    if(before.r_no0<4)pcol(actwk);
    for(unsigned n=100;n<128;n++){
        if(actwk[n].actno==test_kind)ref_et(actwk+n);
        else if(actwk[n].actno==SCD_OBJ_EXPLOSION)bakuha(actwk+n);
    }
    sprite_status expected=actwk[0];
    if(expected.actfree[19]>=100)expected.actfree[19]-=99;
    if(expected.colino>=100)expected.colino-=99;
    scd_player_progress expected_score=scd_player_progress_get();
    short sounds[256];unsigned count=audio_count;memcpy(sounds,audio_log,count*sizeof(short));audio_count=0;
    scd_player_progress_set(score);actwk[0]=before;
    scd_objects_step(before.xposi.w.h,before.yposi.w.h);
    REQUIRE(!memcmp(&actwk[0],&expected,sizeof(before)));
    REQUIRE(scd_objects_generator()==(!old_good && generate_flag));
    REQUIRE(scd_player_progress_get().score==expected_score.score);
    REQUIRE(audio_count==count && !memcmp(audio_log,sounds,count*sizeof(short)));
    for(unsigned n=0;n<28;n++){
        if(actwk[n+1].actno!=actwk[n+100].actno)fprintf(stderr,"slot %u native %u ref %u\n",n,actwk[n+1].actno,actwk[n+100].actno);
        REQUIRE(actwk[n+1].actno==actwk[n+100].actno);
        if(actwk[n+1].actno)compare(actwk+n+1,actwk+n+100);
    }
    updates++;
}
static void begin(unsigned era){
    setup(era,0,0);scd_act_camera(840,688);scra_h_posit.w.h=840;scra_v_posit.w.h=688;
    editmode.w=0;chibi_flag=0;stageno.b.l=0;
}
static void allocation_order(void){
    begin(1);scd_objects_clear_live();memset(actwk+100,0,28*sizeof(*actwk));
    for(unsigned n=0;n<96;n++){
        unsigned kind=n==0?SCD_OBJ_EXPLOSION:n==10?test_kind:SCD_OBJ_RING;
        REQUIRE(scd_objects_spawn(kind,n==10?1000:15000,n==10?800:100,n==0?4:0,0)==(int)n);
    }
    actwk[1].r_no0=4;actwk[1].r_no1=1;
    actwk[11].r_no0=4;scd_word_set(actwk+11,23,0);scd_word_set(actwk+11,24,0);
    for(unsigned n=0;n<28;n++)actwk[n+100]=actwk[n+1];
    gen_tick(player(200,100,16));
    REQUIRE(actwk[1].actno==SCD_OBJ_EXPLOSION && !actwk[1].r_no0 && !actwk[1].actflg);
    gen_tick(player(200,100,16));REQUIRE(actwk[1].r_no0==2);
    /* A full native pool and full reference pool must both advance the event
       pointer despite failing allocation, without playing an explosion. */
    begin(1);gen_tick(player(200,100,16));
    for(unsigned n=1;n<96;n++)REQUIRE(scd_objects_spawn(SCD_OBJ_RING,15000,100,0,0)==(int)n);
    for(unsigned n=1;n<28;n++)actwk[n+100]=actwk[n+1];
    actwk[1].r_no0=actwk[100].r_no0=4;
    scd_word_set(actwk+1,23,0);scd_word_set(actwk+100,23,0);
    gen_tick(player(200,100,16));REQUIRE(scd_word_get(actwk+1,24)==3 && audio_count==0);
}
int main(void){
    test_kind=SCD_OBJ_CC_GENERATOR;parent_priority=4;original_special=special;
    original_draw=generator_viewport;original_frameout=life;zero_original_allocation=1;
    scd_player_audio_set(audio_record);
    for(unsigned era=0;era<4;era++){
        load(era);begin(era);
        for(frame=0;frame<256;frame++)gen_tick(player(200,100,0));
        if(era==1){
            gen_tick(player(1000,actwk[1].yposi.w.h,1));REQUIRE(actwk[1].r_no0==4 && generate_flag);
            for(frame=0;frame<80;frame++)gen_tick(player(200,100,0));
            REQUIRE(actwk[1].r_no0==2 && actwk[1].patno==1 && actwk[1].yposi.w.h==800);
        }
        for(int x=-50;x<=50;x++)for(int y=-58;y<=58;y++)for(unsigned mode=0;mode<8;mode++){
            begin(era);frame=0;gen_tick(player(200,100,0));
            gen_tick(player(1000+x,actwk[1].yposi.w.h+y,mode));contacts++;
        }
    }
    load(1);allocation_order();
    printf("Generator comparison: %u assertions, %u updates, %u contacts\n",checks,updates,contacts);
}
