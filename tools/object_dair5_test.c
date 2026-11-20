/* Host test for the Quartz Quadrant platform dair5 (retail R5 id 48,
 * src/objects_dair5.inc, ported from build/audit/source/src/R5/DAI_RD5.C).
 *
 * Part 1 drives Sonic into each routine the R5 layouts use and checks the
 * retail numbers. Part 2 spawns dair5 at the exact retail placements from
 * build/auto-extract/5/objects<program>.bin and runs the four programs whose
 * walker stalled at x=437 (R51C, R51D, R53C, R53D; R51C/D open since 9a6ac34).
 *
 * Build and run from the repository root, where the generated data lives:
 *
 * M=.
 * clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing \
 *  -Wno-parentheses -Wno-unused-value -Isrc -I$M/assets/generated \
 *  -I$M/build/probe-source -DR1 -DR11A -fsanitize=address,undefined \
 *  -fno-sanitize-recover=all tools/object_dair5_test.c src/title_card.c \
 *  src/player_replay.c src/world.c src/act.c src/player.c \
 *  src/sonic_animation.c src/stage.c src/objects.c \
 *  $M/build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c \
 *  -o /tmp/object_dair5_test && /tmp/object_dair5_test
 */
#include "EQU.H"
#include "DIRCOL.H"
#include "scd_actor.h"
#include "scd_player.h"
#include "scd_objects.h"
#include "act.h"
#include "world.h"
#include "title_card.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
/* The game's camera follows Sonic; springs act only on screen (SPRING.C:
   399-404), so every update first centres a 320x224 view on him. */
void scd_act_camera(int,int);
static void camera_step(unsigned buttons){
    scd_player_state c=scd_player_get();scd_act_camera(c.x/65536-160,c.y/65536-112);
    scd_player_step(buttons);
}
#define scd_player_step camera_step
#ifndef SCD_MAIN_CHECKOUT
#define SCD_MAIN_CHECKOUT "."
#endif
#define STALL_X 437

static int failures;
#define CHECK(cond,...) do{if(!(cond)){failures++;printf("FAIL %s:%d: ",__FILE__,__LINE__);printf(__VA_ARGS__);printf("\n");}}while(0)

static uint8_t data[300000],collision[9472];
static stage_t stage;
static char program[8];
static unsigned zone_act,zone_era;
static size_t slurp(const char *path,uint8_t *out,size_t cap){
    FILE *f=fopen(path,"rb");if(!f){fprintf(stderr,"missing %s\n",path);exit(2);}
    size_t n=fread(out,1,cap,f);fclose(f);return n;
}
/* R5 is zone 3 (scd_player_zone), act is zero based, eras 2/3 are the futures. */
static void load(const char *prog,unsigned act,unsigned era){
    char path[512];snprintf(program,sizeof program,"%s",prog);zone_act=act;zone_era=era;
    snprintf(path,sizeof path,SCD_MAIN_CHECKOUT "/assets/generated/qq%s.bin",prog);size_t n=slurp(path,data,sizeof data);
    snprintf(path,sizeof path,SCD_MAIN_CHECKOUT "/assets/generated/qqcollision%s.bin",prog);
    if(slurp(path,collision,sizeof collision)!=sizeof collision){fprintf(stderr,"collision size\n");exit(2);}
    if(stage_open(&stage,data,n)){fprintf(stderr,"stage_open rejected %s\n",prog);exit(2);}
}
/* The same bring-up tools/zone_walk_test.c performs. */
static void start(int title){
    scd_player_zone(3);scd_objects_zone(3);
    scd_player_act(zone_act);scd_objects_act(zone_act);scd_world_act(zone_act);
    if(scd_player_init(&stage,collision,sizeof collision,zone_era)){fprintf(stderr,"player init\n");exit(2);}
    scd_world_reset(zone_era);
    if(title)scd_title_card_start(zone_act);
}
static void walk_step(unsigned buttons){
    scd_player_hold_clock(scd_title_card_locked());
    scd_player_step(scd_title_card_locked()?0:buttons);
    scd_title_card_step();
}
static sprite_status *actor(int slot){return &actwk[slot+1];}
static int x_of(const sprite_status *o){return o->xposi.w.h;}
static int y_of(const sprite_status *o){return o->yposi.w.h;}
static int px(void){return actwk[0].xposi.w.h;}
static int py(void){return actwk[0].yposi.w.h;}
static int standing_on(int slot){sprite_status *p=&actwk[0];return (p->cddat&8) && p->actfree[19]==slot+1;}
static int spawn(unsigned sub,int x,int y){
    int slot=scd_objects_spawn(SCD_OBJ_DAIR5,x,y,sub,0);
    if(slot<0){printf("FAIL spawn sub %u\n",sub);exit(1);}
    return slot;
}
/* Drop Sonic (airborne, not rolling: radius 19) and step until he stands or
   the budget runs out. Returns the landing update, or -1. */
static int drop_onto(int slot,int x,int y,int budget){
    scd_player_place(x,y,0,0,2);
    for(int u=0;u<budget;u++){scd_player_step(0);if(standing_on(slot))return u;}
    return -1;
}

/* ------------------------------------------------------------------ */
/* Part 1: focused behaviour. R51C Future terrain, open air over x 150..350
   and y 300..620 (flat ground at y=640). */

/* Top-only, width and landing height (ini_tbl DAI_RD5.C:140-166, sprvsize 16
   DAI_RD5.C:203, ridechk DAI_RD5.C:290 with r_no1 = 1). RIDECHK.C hit_v
   (:261-270, :333-353) accepts dx in [-(sprhsize+10), sprhsize+10) and then
   lands only while the vertical overlap is below the distance to the nearer
   edge, so dx = -(sprhsize+10) and dx = sprhsize+10 never land, and a rider
   falling ~4 px per update lands at dx = +-(sprhsize+5). */
static void test_landing_and_width(void){
    static const unsigned subs[3]={0,7,17};static const int widths[3]={16,32,48};
    for(int k=0;k<3;k++){
        int w=widths[k]+10;
        start(0);int s=spawn(subs[k],240,450);
        CHECK(actor(s)->sprhsize==widths[k] && actor(s)->sprvsize==16,"sub %u size %d,%d",subs[k],actor(s)->sprhsize,actor(s)->sprvsize);
        int u=drop_onto(s,240,380,120);
        CHECK(u>=0 && py()==450-16-19,"sub %u lands standing at y=%d (want 415)",subs[k],py());
        CHECK(scd_objects_standing_type()==SCD_OBJ_DAIR5,"standing type %u",scd_objects_standing_type());
        for(int edge=0;edge<4;edge++){
            int x=edge==0?240+w-5:edge==1?240+w:edge==2?240-w+5:240-w,want=edge==0 || edge==2;
            start(0);s=spawn(subs[k],240,450);
            int landed=drop_onto(s,x,380,120)>=0;
            CHECK(landed==want,"sub %u dx=%d landed=%d want %d",subs[k],x-240,landed,want);
        }
        printf("  sub %2u: half width %d, lands at y=%d; lands at dx +-%d, not at dx +-%d\n",subs[k],widths[k],450-35,w-5,w);
    }
}
/* Rising or level contact is ignored: RIDECHK.C hitchk returns hit_e for
   yspeed < 0 when r_no1 == 1, and hit_x / hit_yu return hit_e for r_no1 == 1. */
static void test_top_only(void){
    start(0);int s=spawn(0,240,450);
    scd_player_place(240,520,0,0,2);scd_player_velocity(0,-2560);
    int min_y=py(),landed=-1;
    for(int u=0;u<200 && landed<0;u++){scd_player_step(0);if(py()<min_y)min_y=py();if(standing_on(s))landed=u;}
    CHECK(min_y<450-16-19,"rose through from below: min y %d",min_y);
    CHECK(landed>0 && py()==415,"then landed on top at y=%d",py());
    printf("  from below: rose through to y=%d, landed on top at y=%d\n",min_y,py());
    /* Walking into its side at the same height does not block. */
    start(0);s=spawn(0,300,620);
    scd_player_place(200,620,0,0,0);
    int max_x=px(),blocked=0;
    for(int u=0;u<120;u++){scd_player_step(SCD_RIGHT);if(px()>max_x)max_x=px();if(standing_on(s))blocked=1;}
    CHECK(max_x>300+26+20 && !blocked,"side contact passes: max x %d standing %d",max_x,blocked);
    printf("  side: walked from x=200 through the platform at x=300 to x=%d, never stood on it\n",max_x);
}
/* dodai_sub (DAI_RD5.C:476-502) with accel 4 (DAI_RD5.C:308,327,346): the
   swing spans 95 px for d4 = 48 and 64 px for d4 = 32; bit 7 reverses. */
static void swing_range(unsigned sub,int *lo_x,int *hi_x,int *lo_y,int *hi_y){
    start(0);int s=spawn(sub,240,450);*lo_x=*hi_x=240;*lo_y=*hi_y=450;
    scd_player_place(64,620,0,0,0);
    for(int u=0;u<800;u++){
        scd_player_step(0);sprite_status *o=actor(s);
        if(x_of(o)<*lo_x)*lo_x=x_of(o);if(x_of(o)>*hi_x)*hi_x=x_of(o);
        if(y_of(o)<*lo_y)*lo_y=y_of(o);if(y_of(o)>*hi_y)*hi_y=y_of(o);
    }
}
static void test_swings(void){
    static const struct {unsigned sub;int lx,hx,ly,hy;const char *what;} cases[]={
        {12,240,335,450,450,"type02 x swing 48"},{140,144,240,450,450,"type02 reversed"},
        {3,240,240,450,545,"type03 y swing 48 (R51C/D stall platform)"},{138,240,240,354,450,"type03 reversed (R51A)"},
        {8,240,304,450,450,"type04 x swing 32"},{137,176,240,450,450,"type04 reversed (R51A)"}};
    for(unsigned k=0;k<sizeof cases/sizeof*cases;k++){
        int lx,hx,ly,hy;swing_range(cases[k].sub,&lx,&hx,&ly,&hy);
        CHECK(lx==cases[k].lx && hx==cases[k].hx && ly==cases[k].ly && hy==cases[k].hy,
              "sub %u range x %d..%d y %d..%d",cases[k].sub,lx,hx,ly,hy);
        printf("  sub %3u %-42s x %d..%d  y %d..%d\n",cases[k].sub,cases[k].what,lx,hx,ly,hy);
    }
    /* A rider is carried the full distance: the platform's xspeed goes to the
       player (RIDECHK.C hit_y :492-494, top_solid) and type03 re-seats him. */
    start(0);int s=spawn(12,240,450);
    int u=drop_onto(s,240,410,60);CHECK(u>=0,"landed on sub 12");
    /* Compared in 16.16: both positions gain the same xspeed*256 every update. */
    int32_t offset=actwk[0].xposi.l-actor(s)->xposi.l;int start_x=px(),drift=0,min_x=px(),max_x=px();
    for(int n=0;n<300;n++){scd_player_step(0);if(!standing_on(s) || actwk[0].xposi.l-actor(s)->xposi.l!=offset)drift++;if(px()<min_x)min_x=px();if(px()>max_x)max_x=px();}
    CHECK(!drift && max_x-min_x>=90,"sub 12 carried %d..%d, %d updates off",min_x,max_x,drift);
    printf("  sub  12 rider carried x %d..%d (%d px), 16.16 offset to the platform unchanged for 300 updates (start x %d)\n",min_x,max_x,max_x-min_x,start_x);
    start(0);s=spawn(3,240,450);
    u=drop_onto(s,240,405,60);CHECK(u>=0,"landed on sub 3");
    int off=0,lo=py(),hi=py();
    for(int n=0;n<300;n++){scd_player_step(0);if(!standing_on(s) || py()!=y_of(actor(s))-35)off++;if(py()<lo)lo=py();if(py()>hi)hi=py();}
    CHECK(!off && hi-lo>=90,"sub 3 rider y %d..%d, %d updates off",lo,hi,off);
    printf("  sub   3 rider carried y %d..%d, standing at platform y-35 all 300 updates\n",lo,hi);
}
/* dai5sub (DAI_RD5.C:507-536): 8 steps of 8 on the sine table, /64. */
static void test_sink(void){
    start(0);int s=spawn(0,240,450);
    int u=drop_onto(s,240,380,120);CHECK(u>=0,"landed on sub 0");
    static const int want[9]={450,450,451,452,452,453,453,453,454};
    int got[9];got[0]=y_of(actor(s));
    for(int n=1;n<9;n++){scd_player_step(0);got[n]=y_of(actor(s));}
    for(int n=0;n<9;n++)CHECK(got[n]==want[n],"sink step %d y=%d want %d",n,got[n],want[n]);
    CHECK(py()==454-35,"rider follows the sink: y=%d",py());
    scd_player_place(64,620,0,0,0);
    for(int n=0;n<10;n++)scd_player_step(0);
    CHECK(y_of(actor(s))==450,"returns when left: y=%d",y_of(actor(s)));
    printf("  sub   0 sink while ridden: 450,450,451,452,452,453,453,453,454; back to %d after leaving\n",y_of(actor(s)));
}
/* belttask (DAI_RD5.C:560-594): 0x8000/0x10000/0x20000 by time_flag, negated
   by colrevflag. belt_flag bit 0 (DAI_RD5.C:171-177) is set for sub 18. */
static void test_belt(void){
    static const int32_t want[3]={0x8000,0x10000,0x20000};
    for(int t=0;t<3;t++)for(int rev=0;rev<2;rev++){
        start(0);int s=spawn(18,240,450);
        int u=drop_onto(s,240,380,120);CHECK(u>=0,"landed on belt");
        time_flag=t;colrevflag=rev;
        int bad=0;int32_t delta=0;
        for(int n=0;n<10;n++){int32_t before=actwk[0].xposi.l;scd_player_step(0);delta=actwk[0].xposi.l-before;if(delta!=(rev?-want[t]:want[t]))bad++;}
        CHECK(!bad,"belt time_flag %d rev %d delta %d",t,rev,delta);
        colrevflag=0;
    }
    start(0);int s=spawn(0,240,450);drop_onto(s,240,380,120);
    int32_t before=actwk[0].xposi.l;for(int n=0;n<10;n++)scd_player_step(0);
    CHECK(actwk[0].xposi.l==before,"sub 0 is not a belt");
    printf("  sub  18 belt pushes 0.5/1/2 px per update for time_flag 0/1/2, reversed by colrevflag; sub 0 does not\n");
}
/* type05 (DAI_RD5.C:361-407): 30 updates after landing, then +32 per update
   to 1024 (4 px), sprvsize 16/18/20, gone below the view. */
static void test_fall(void){
    start(0);int s=spawn(6,240,400);
    int land=drop_onto(s,240,330,120);CHECK(land>=0,"landed on sub 6");
    int first_fall=-1,max_speed=0,carried=0,removed=-1,bad_accel=0,prev=0;
    for(int n=1;n<200;n++){
        scd_player_step(0);
        sprite_status *o=actor(s);
        if(o->actno!=SCD_OBJ_DAIR5){removed=n;break;}
        if(o->yspeed.w && first_fall<0)first_fall=n;
        if(first_fall>0 && o->yspeed.w!=(prev+32>1024?prev:prev+32) && prev<1024)bad_accel++;
        if(o->yspeed.w>max_speed)max_speed=o->yspeed.w;
        if(standing_on(s))carried=n;
        /* sprvsize is chosen from the speed before this update's +32 (DAI_RD5.C:382-394). */
        if(first_fall>0)CHECK(o->sprvsize==(prev>=768?20:prev>=512?18:16),"sprvsize %d after speed %d",o->sprvsize,prev);
        prev=o->yspeed.w;
    }
    /* The retail R52A program falls through into the first timer decrement
       when it arms, so the fall begins 30 updates after the landing update. */
    CHECK(first_fall==30,"starts falling %d updates after the landing update (want 30)",first_fall);
    CHECK(!bad_accel && max_speed==1024,"accelerates by 32 to 1024: max %d, %d bad",max_speed,bad_accel);
    CHECK(carried>first_fall && py()==620,"rider carried down, set on the ground: y=%d",py());
    CHECK(removed>0,"removed once below the view");
    printf("  sub   6 fall: waits %d updates, yspeed +32 to %d, rider carried %d updates then set on the ground y=%d, removed at update %d\n",
           first_fall,max_speed,carried,py(),removed);
}
/* type06 (DAI_RD5.C:412-471): 30 updates, sprvsize 14, yspeed -8 per update
   to -768, stop when emycol_u 48 px higher finds the ceiling. R53C Future has
   open air over x=300 from the ceiling at y=31 down to the ground. */
static void test_rise(void){
    load("53C",2,2);start(0);
    int s=spawn(5,300,500);
    int land=drop_onto(s,300,430,120);CHECK(land>=0,"landed on sub 5");
    int first=-1,stop=-1,prev_y=0,min_v=0;
    for(int n=1;n<400;n++){
        prev_y=y_of(actor(s));scd_player_step(0);sprite_status *o=actor(s);
        if(first<0 && o->yspeed.w)first=n;
        if(o->yspeed.w<min_v)min_v=o->yspeed.w;
        if(first>0 && stop<0 && o->actfree[19]==4){stop=n;break;}
    }
    sprite_status *o=actor(s);
    /* type06_00 arms and calls type06_01 in the same update (DAI_RD5.C:426-430),
       so the first decrement is immediate: the rise begins on the 30th update. */
    CHECK(first==30 && stop>first,"rises after %d updates, stops at %d",first,stop);
    CHECK(min_v==-768 && o->yspeed.w==0 && o->sprvsize==16,"speed cap %d, final speed %d, sprvsize %d",min_v,o->yspeed.w,o->sprvsize);
    sprite_status probe={0};probe.xposi.w.h=300;probe.sprvsize=14;
    probe.yposi.w.h=(short)(y_of(o)-48);short at_stop=emycol_u(&probe);
    probe.yposi.w.h=(short)(prev_y-48);short before=emycol_u(&probe);
    CHECK(at_stop<0 && before>=0,"ceiling test at stop %d, one update earlier %d",at_stop,before);
    CHECK(standing_on(s) && actwk[0].r_no0<6,"rider still standing and alive");
    printf("  sub   5 rise: waits %d updates, yspeed -8 to %d, stops at y=%d (ceiling probe %d, previous %d), rider alive at y=%d\n",
           first,min_v,y_of(o),at_stop,before,py());
    load("51C",0,2);
}
/* banesetsub (DAI_RD5.C:182-187, 228-241, 541-555): springs of subtype 2 at
   dx {0} / {-16,16} / {-32,0,32}, dy -24, carried with the platform. */
static void test_springs(void){
    static const unsigned subs[3]={2,14,22};static const int count[3]={1,2,3};
    static const int dx[3][3]={{0},{-16,16},{-32,0,32}};
    for(int k=0;k<3;k++){
        start(0);int s=spawn(subs[k],240,450);
        scd_player_place(64,620,0,0,0);
        for(int n=0;n<120;n++)scd_player_step(0);
        sprite_status *o=actor(s);int found=0,placed=0;
        for(int c=1;c<=SCD_OBJECT_CAPACITY;c++){
            sprite_status *a=&actwk[c];
            if(a->actno!=SCD_OBJ_SPRING || scd_word_get(a,28)!=(unsigned)s+1)continue;
            found++;
            for(int n=0;n<count[k];n++)if(x_of(a)==x_of(o)+dx[k][n] && y_of(a)==y_of(o)-24)placed++;
            CHECK(a->userflag.b.h==2,"spring subtype %d",a->userflag.b.h);
        }
        CHECK(found==count[k] && placed==count[k],"sub %u springs %d placed %d",subs[k],found,placed);
        printf("  sub  %2u: %d spring(s) at dy -24, dx",subs[k],found);for(int n=0;n<count[k];n++)printf(" %d",dx[k][n]);printf(", following the platform at x=%d\n",x_of(o));
    }
    /* Landing on the attached spring launches (subtype 2: -2560, SPRING.C sjumptbl). */
    start(0);int s=spawn(2,240,450);scd_player_step(0);
    scd_player_place(240,450-24-8-19-12,0,0,2);
    int launched=0;for(int n=0;n<40 && !launched;n++){scd_player_step(0);if(actwk[0].yspeed.w<=-2400)launched=actwk[0].yspeed.w;}
    CHECK(launched,"attached spring launches");
    printf("  sub   2 attached spring launches Sonic at yspeed %d\n",launched);
    (void)s;
}

/* Every subtype the R5 layouts place, read from build/auto-extract/5 (the four
   era files of an act are one table with era masks). The expectations are an
   independent transcription of DAI_RD5.C: routine per subtype :256-282,
   sprhsize :140-166, belt_flag :171-177, bane_flag :182-187. */
static int springs_of(int s){
    int n=0;for(int c=1;c<=SCD_OBJECT_CAPACITY;c++)if(actwk[c].actno==SCD_OBJ_SPRING && scd_word_get(&actwk[c],28)==(unsigned)s+1)n++;
    return n;
}
static void test_every_subtype(void){
    static const char routine[]="1223365144332226511322265",belt[]="0100100001010100001001000",bane[]="0010000000000020000000300";
    static const uint8_t width[25]={16,16,16,16,16,16,16,32,32,32,32,32,32,32,32,32,32,48,48,48,48,48,48,48,48};
    static const char *files[3]={"51A","52A","53C"};
    uint8_t used[256]={0};
    for(int f=0;f<3;f++){
        char path[512];snprintf(path,sizeof path,SCD_MAIN_CHECKOUT "/build/auto-extract/5/objects%s.bin",files[f]);
        static uint8_t rec[16384];size_t n=slurp(path,rec,sizeof rec);
        for(size_t k=0;k+8<=n;k+=8){
            if((rec[k]<<8|rec[k+1])==65535)break;
            if((rec[k+4]&127)==48)used[rec[k+5]]=1;
        }
    }
    int tested=0;
    for(unsigned sub=0;sub<256;sub++){
        if(!used[sub])continue;
        unsigned idx=sub&31;int rev=!!(sub&128),cls=routine[idx]-'0';
        CHECK(idx<=24,"layout subtype %u beyond the retail tables",sub);if(idx>24)continue;
        /* Unridden: which way it swings, and its springs. */
        start(0);int s=spawn(sub,240,450);scd_player_place(64,620,0,0,0);
        int lx=240,hx=240,ly=450,hy=450;
        for(int n=0;n<320;n++){scd_player_step(0);sprite_status *o=actor(s);
            if(x_of(o)<lx)lx=x_of(o);if(x_of(o)>hx)hx=x_of(o);if(y_of(o)<ly)ly=y_of(o);if(y_of(o)>hy)hy=y_of(o);}
        /* The 8.8 swing peaks at 95.06 px (d4 48) and 64.0 px (d4 32); a
           reversed swing floors -95.06 to -96. */
        int want_dx=cls==2?(rev?96:95):cls==4?64:0,want_dy=cls==3?(rev?96:95):0;
        int dx=hx-lx,dy=hy-ly;
        CHECK(actor(s)->sprhsize==width[idx],"sub %u sprhsize %d",sub,actor(s)->sprhsize);
        CHECK(dx==want_dx && dy==want_dy,"sub %u swing x %d..%d y %d..%d",sub,lx,hx,ly,hy);
        CHECK(!want_dx || (rev?hx==240:lx==240),"sub %u swings %s",sub,rev?"left":"right");
        CHECK(!want_dy || (rev?hy==450:ly==450),"sub %u swings %s",sub,rev?"up":"down");
        CHECK(springs_of(s)==bane[idx]-'0',"sub %u springs %d",sub,springs_of(s));
        /* Its springs cover the deck: dropping on the centre must launch. */
        if(bane[idx]!='0'){
            start(0);s=spawn(sub,240,450);scd_player_step(0);
            scd_player_place(240,405,0,0,2);int launch=0;
            for(int n=0;n<40 && !launch;n++){scd_player_step(0);if(actwk[0].yspeed.w==-2560)launch=1;}
            CHECK(launch,"sub %u spring launch",sub);tested++;
            printf("  sub %3u: routine type0%d%s, half width %d, swing x %d y %d, springs %d cover the deck and launch at -2560\n",sub,cls,rev?" reversed":"",width[idx],hx-lx,hy-ly,bane[idx]-'0');
            continue;
        }
        /* Ridden: belt push and the fall/rise wait. */
        start(0);s=spawn(sub,240,450);
        int land=drop_onto(s,240,405,60);CHECK(land>=0,"sub %u rideable",sub);
        int32_t rel=actwk[0].xposi.l-actor(s)->xposi.l;int push=0,moved=-1;
        for(int n=1;n<=40;n++){
            scd_player_step(0);
            if(n==10){int32_t now=actwk[0].xposi.l-actor(s)->xposi.l;push=(now-rel)/10;}
            if(moved<0 && actor(s)->yspeed.w)moved=n;
        }
        CHECK(push==(belt[idx]=='1'?0x20000:0),"sub %u belt push %d",sub,push);
        CHECK(moved==(cls==5||cls==6?30:-1),"sub %u starts moving vertically at %d",sub,moved);
        tested++;
        printf("  sub %3u: routine type0%d%s, half width %d, swing x %d y %d, springs %d, belt %s%s\n",sub,cls,rev?" reversed":"",width[idx],
               hx-lx,hy-ly,bane[idx]-'0',push?"2 px/update":"no",cls==5?", falls 30 updates after landing":cls==6?", rises 30 updates after landing":"");
    }
    printf("  %d distinct subtypes from objects51A/52A/53C.bin checked\n",tested);
}

/* ------------------------------------------------------------------ */
/* Part 2: stall routes at the exact retail placements. */
static int spawn_retail(void){
    char path[512];snprintf(path,sizeof path,SCD_MAIN_CHECKOUT "/build/auto-extract/5/objects%s.bin",program);
    static uint8_t rec[16384];size_t n=slurp(path,rec,sizeof rec);
    /* ACTSET.C tm_setchk: time_flag 0 Past = bit 0, 1 Present = bit 1, 2 Future = bit 2. */
    unsigned bit=zone_era==0?2:zone_era==1?1:4;int spawned=0;
    for(size_t k=0;k+8<=n;k+=8){
        unsigned x=rec[k]<<8|rec[k+1],y=rec[k+2]<<8|rec[k+3],id=rec[k+4]&127,sub=rec[k+5],eras=rec[k+6]>>5;
        if(x==65535)break;
        if(id!=48 || !(eras&bit))continue;
        if(scd_objects_spawn(SCD_OBJ_DAIR5,x,y&4095,sub,y>>14)>=0)spawned++;
    }
    return spawned;
}
static uint8_t recorded[6000];static int recorded_len;
/* First update past the stall and Sonic's Y there; last update on a dair5. */
static int cross_update,cross_y,left_platform;
static void note_cross(int u){if(cross_update<0 && px()>STALL_X){cross_update=u;cross_y=py();}}
/* tools/zone_walk_test.c's policy; hold=1 keeps Jump held while rising. */
static int walker(int objects,int hold,int back_off,int jump,int frames){
    start(1);if(objects)spawn_retail();
    scd_player_state p=scd_player_get();int max_x=p.x/65536,last=max_x,holding=0,left=0;unsigned stuck=0;
    for(int u=0;u<frames;u++){
        unsigned b=SCD_RIGHT;
        if(back_off && !scd_title_card_locked() && left<back_off){left++;b=SCD_LEFT;stuck=0;}
        else if(jump && stuck>=30 && !(p.flags&2)){b|=SCD_JUMP;stuck=0;holding=hold;}
        else if(holding && (p.flags&2) && p.vy<0)b|=SCD_JUMP;else holding=0;
        walk_step(b);p=scd_player_get();int x=p.x/65536;
        if(x>last+1){stuck=0;last=x;}else stuck++;
        if(x>max_x)max_x=x;
    }
    return max_x;
}
static sprite_status *ridden(void){
    sprite_status *p=&actwk[0];unsigned a=p->actfree[19];
    return (p->cddat&8) && a && a<=SCD_OBJECT_CAPACITY && actwk[a].actno==SCD_OBJ_DAIR5?&actwk[a]:NULL;
}
/* The platform route a player takes: idle `wait` updates so the sub 3 swing
   is low when he arrives, run right, jump off the quarter pipe (x >= x0) and
   hold Left onto the platform, brake, ride it to y <= top, then a short jump
   right under the overhang into the y 384..447 corridor. Every button is
   recorded for the replay control. */
static int platform_route(int wait,int x0,int top,int hop,int *rode_sub,int *rode_x,int frames){
    start(1);spawn_retail();
    scd_player_state p=scd_player_get();int phase=0,t=0,idle=0,max_x=p.x/65536;
    *rode_sub=-1;*rode_x=-1;recorded_len=0;cross_update=-1;cross_y=0;left_platform=-1;
    for(int u=0;u<frames;u++){
        unsigned b=SCD_RIGHT;
        if(!scd_title_card_locked() && idle<wait){idle++;b=0;}
        if(phase==0 && !(p.flags&2) && p.x/65536>=x0 && !scd_title_card_locked()){phase=1;t=0;}
        if(phase==1){b=(t<8?SCD_RIGHT:SCD_LEFT)|(t<16?SCD_JUMP:0);t++;}
        if(phase==2){
            sprite_status *d=ridden();
            b=p.speed<-64?SCD_RIGHT:p.speed>64?SCD_LEFT:0;
            if(!d)phase=4;
            else{*rode_sub=d->userflag.b.h;*rode_x=scd_word_get(d,29);if(d->yposi.w.h<=top){phase=3;t=0;}}
        }
        if(phase==3){b=SCD_RIGHT|(t<hop?SCD_JUMP:0);t++;}
        if(phase==4)b=SCD_RIGHT;
        walk_step(b);if(recorded_len<(int)sizeof recorded)recorded[recorded_len++]=(uint8_t)b;
        p=scd_player_get();int x=p.x/65536;if(x>max_x)max_x=x;
        if(ridden())left_platform=u;
        note_cross(u);
        if(phase==1 && t>2 && !(p.flags&2))phase=ridden()?2:4;
        if(phase==1 && t>400)phase=4;
    }
    return max_x;
}
static int replay_min_x;
static int replay(int objects){
    start(1);if(objects)spawn_retail();
    /* replay_min_x: the lowest x after first reaching the pipe (x >= 380). */
    int max_x=px(),at_pipe=0;cross_update=-1;cross_y=0;replay_min_x=9999;
    for(int u=0;u<recorded_len;u++){
        walk_step(recorded[u]);if(px()>max_x)max_x=px();note_cross(u);
        if(px()>=380)at_pipe=1;
        if(at_pipe && cross_update<0 && px()<replay_min_x)replay_min_x=px();
    }
    return max_x;
}
/* Highest the feet get over x lo..hi from a jump off the quarter pipe with
   Left held, swept over the take-off point, the jump hold and the delay. */
static int best_feet_over(int lo,int hi){
    int best=9999;
    for(int x0=380;x0<=437;x0++)for(int h=1;h<=16;h+=5)for(int dl=0;dl<=12;dl+=4){
        start(1);spawn_retail();scd_player_state p=scd_player_get();int phase=0,t=0;
        for(int u=0;u<1500;u++){
            unsigned b=SCD_RIGHT;
            if(phase==0 && !(p.flags&2) && p.x/65536>=x0 && !scd_title_card_locked()){phase=1;t=0;}
            if(phase==1){b=(t<dl?SCD_RIGHT:SCD_LEFT)|(t<h?SCD_JUMP:0);t++;}
            walk_step(b);p=scd_player_get();
            int x=p.x/65536,feet=p.y/65536+actwk[0].sprvsize;
            if(phase==1 && x>=lo && x<=hi && feet<best)best=feet;
            if(phase==1 && ((t>2 && !(p.flags&2)) || t>300))break;
        }
    }
    return best;
}
static void stall_routes(void){
    static const struct {const char *prog;unsigned act,era;} routes[4]={{"51C",0,2},{"51D",0,3},{"53C",2,2},{"53D",2,3}};
    for(int r=0;r<4;r++){
        load(routes[r].prog,routes[r].act,routes[r].era);
        start(1);int count=spawn_retail();
        int stock_none=walker(0,0,0,1,6000),stock=walker(1,0,0,1,6000),held_none=walker(0,1,0,1,6000),held=walker(1,1,0,1,6000);
        int backoff_none=walker(0,0,60,0,1200);
        printf("R%s (zone 3 act %u era %u): %d dair5 spawned from objects%s.bin\n",routes[r].prog,routes[r].act,routes[r].era,count,routes[r].prog);
        printf("  stock walker (1-frame Jump), no objects:      max_x=%d\n",stock_none);
        printf("  stock walker (1-frame Jump), retail dair5:    max_x=%d\n",stock);
        printf("  walker holding Jump while rising, no objects: max_x=%d\n",held_none);
        printf("  walker holding Jump while rising, dair5:      max_x=%d\n",held);
        printf("  back off 60 updates, then Right only (no Jump, no objects): max_x=%d\n",backoff_none);
        /* 9a6ac34 (QQ1C belt): GetLevelBlock reads chunk 1's first block on a
           blank chunk, as retail does; the R51C/R51D pocket at x=437 no longer
           holds even the object-free walker, so their stall checks lapse. */
        if(stock_none>STALL_X){
            printf("  no stall: the object-free walker passes x=%d (retail blank-chunk read)\n",STALL_X);
            CHECK(stock>STALL_X,"dair5 does not block the open route (got %d)",stock);
            continue;
        }
        CHECK(stock==STALL_X,"stock walker with dair5 still stalls at %d (got %d)",STALL_X,stock);
        if(r<2){
            int sub=-1,rx=-1;
            /* V0.073: Sonic spawns grounded (ObjSonic_Init); the stall platform
               phase needs a 100-update wait (a scan of 92..100: only 100 rides sub 3). */
            int route=platform_route(100,419,400,6,&sub,&rx,1600);
            int route_cross=cross_update,route_y=cross_y,route_left=left_platform;
            int again=replay(1),again_cross=cross_update;
            int control=replay(0),control_cross=cross_update,control_y=cross_y,control_min=replay_min_x;
            printf("  platform route (wait 100, jump off the pipe at x>=419 holding Left, ride to y<=400, 6-update hop right):\n");
            printf("    rode dair5 sub %d placed at x=%d, left it at update %d, passed x=%d at update %d at y=%d; max_x=%d\n",sub,rx,route_left,STALL_X,route_cross,route_y,route);
            printf("    same %d recorded buttons with dair5: passed at update %d, max_x=%d\n",recorded_len,again_cross,again);
            printf("    same buttons without dair5: no platform to land on, Sonic flies back to x=%d, and the long run back up the pipe passes at update %d at y=%d, max_x=%d\n",control_min,control_cross,control_y,control);
            CHECK(sub==3 && rx==320,"rode the retail sub 3 platform at x=320 (sub %d x %d)",sub,rx);
            CHECK(route>STALL_X+40,"platform route passes the stall: %d",route);
            /* The crossing is the hop off the platform into the y 384..447 corridor. */
            CHECK(route_left>0 && route_cross>route_left && route_cross-route_left<90 && route_y<448,"crossed %d updates after leaving the platform at y=%d",route_cross-route_left,route_y);
            CHECK(again==route && again_cross==route_cross,"replay reproduces the route");
            CHECK(control_cross<0 || control_cross>route_cross,"without dair5 no earlier crossing (%d vs %d)",control_cross,route_cross);
            int pass=0,tries=0;
            for(int wait=84;wait<=108;wait+=4)for(int x0=414;x0<=424;x0+=2)for(int hop=4;hop<=8;hop+=2){
                int s2,x2;tries++;if(platform_route(wait,x0,400,hop,&s2,&x2,1600)>STALL_X+40)pass++;
            }
            printf("    neighbouring parameters: %d of %d also pass\n",pass,tries);
            CHECK(pass>0,"route is not a single point");
        }else{
            /* R53 dair5: sub 0 at (272,400), top y=384; its spring (272,376) tops out at y=368. */
            int best=best_feet_over(272-26,272+25);
            printf("  dair5 sub 0 at (272,400): best feet y over x 246..297 from a quarter-pipe jump = %d, platform top = 384\n",best);
            CHECK(best>384,"R53 platform is out of reach from the stall pocket (best feet %d)",best);
        }
        CHECK(backoff_none>STALL_X,"a back-off run-up alone passes x=%d with no objects (got %d)",STALL_X,backoff_none);
    }
}

int main(void){
    load("51C",0,2);
    printf("Part 1: focused dair5 behaviour (R51C Future terrain unless noted)\n");
    test_landing_and_width();
    test_top_only();
    test_swings();
    test_sink();
    test_belt();
    test_fall();
    test_rise();
    test_springs();
    test_every_subtype();
    printf("Part 2: stall routes, dair5 at the retail placements\n");
    stall_routes();
    if(failures){printf("FAIL: %d check(s)\n",failures);return 1;}
    printf("PASS\n");
    return 0;
}
