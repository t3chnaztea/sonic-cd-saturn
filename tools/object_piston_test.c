/* Host test for the Metallic Madness piston, SCD_OBJ_PISTON (retail R8 act_tbl
 * id 52, R8/PISTON.C), implemented in src/objects_piston.inc.
 *
 * Build and run from the repository root. Generated data is read from the main
 * checkout (assets/, build/ are not in worktrees):
 *
 *   M=<path to the main checkout>   # "." when run from the main checkout
 *   clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value \
 *     -Isrc -I$M/assets/generated -I$M/build/probe-source -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all \
 *     tools/object_piston_test.c src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c \
 *     src/sonic_animation.c src/stage.c src/objects.c \
 *     $M/build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c -o /tmp/object_piston_test
 *   /tmp/object_piston_test [MAIN_CHECKOUT]
 *
 * Part 1 (focused) runs on a synthetic flat stage: every subtype the retail R8
 * layouts use (0x00 0x04 0x05 0x40 0x44 0x45 0x48), its sizes and tables, its
 * motion, the side block, standing, carry, the launcher and the crush.
 * Part 2 (stall) loads Metallic Madness Act 2 (R82A/C/D), spawns the pistons
 * and springs at the exact retail placements from build/auto-extract, and
 * drives the player through the sealed route past x=501. */
#include "EQU.H"
#include "ETC.H"
#include "scd_actor.h"
#include "scd_objects.h"
#include "scd_player.h"
#include "stage.h"
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

static const char *root="."; /* repo root; argv[1] overrides (main checkout) */
static unsigned failures;
#define CHECK(cond,...) do{if(!(cond)){failures++;printf("FAIL %s:%d: ",__FILE__,__LINE__);printf(__VA_ARGS__);printf("\n");}}while(0)

/* ---------------------------------------------------------------- stages */
static uint8_t flat_chunks[512],flat_map[512],flat_collision[9472];
static stage_t flat;
/* Chunk 1 is 16x16 fully solid blocks; map rows 4..7 use it, so the floor
   surface is y=1024 across the whole act and everything above is open. */
static void flat_init(void){
    for(unsigned b=0;b<256;b++){flat_chunks[b*2]=0x60;flat_chunks[b*2+1]=0x01;}
    memset(flat_map,0,sizeof flat_map);
    for(unsigned row=4;row<8;row++)for(unsigned col=0;col<64;col++)flat_map[row*64+col]=1;
    memset(flat_collision,0,sizeof flat_collision);
    flat_collision[1]=1;
    for(unsigned c=0;c<16;c++){flat_collision[1024+16+c]=16;flat_collision[5120+16+c]=16;}
    memset(&flat,0,sizeof flat);
    flat.part[2]=flat_chunks;flat.size[2]=sizeof flat_chunks;
    flat.part[3]=flat_map;flat.size[3]=sizeof flat_map;
    flat.start_x=64;flat.start_y=1005;
}
static void flat_start(void){
    scd_player_zone(6);scd_objects_zone(6);scd_player_act(1);scd_objects_act(1);
    if(scd_player_init(&flat,flat_collision,sizeof flat_collision,2)){printf("FAIL flat init\n");exit(1);}
}
static sprite_status *piston_actor(int slot){return &actwk[slot+1];}
static int riding(int slot){return (actwk[0].cddat&8) && actwk[0].actfree[19]==slot+1;}

/* ------------------------------------------------ retail reference model */
/* R8/PISTON.C piston_init/piston_move with no player: the Y the retail object
   takes on each update. Written from the source independently of the port. */
typedef struct {short base,rad,spd,radius,y;uint8_t delay,count,hold;unsigned sub;} ref_piston;
static void ref_init(ref_piston *r,unsigned sub,short y){
    static const short rad_tbl[4]={0,256,512,768},radius_tbl[2]={32,48},spd_tbl[4]={4,8,16,32};
    static const uint8_t delay_tbl[2]={60,90};
    memset(r,0,sizeof *r);r->sub=sub;r->base=r->y=y;
    r->rad=rad_tbl[(sub&48)>>4];r->radius=radius_tbl[(sub&64)>>6];
    if((sub&3)==1){r->spd=spd_tbl[(sub&4)/4];r->delay=delay_tbl[(sub&8)/8];}
    else r->spd=spd_tbl[(sub&12)/4];
}
static void ref_step(ref_piston *r){
    if((r->sub&3)==1){
        if(r->hold){if((int8_t)--r->count>=0)return;r->hold=0;}
        else if(r->rad==256 || r->rad==768){r->hold=1;r->count=r->delay;return;}
    }
    r->rad=(r->rad+r->spd)&1023;
    short s,c;sinset((unsigned char)(r->rad>>2),&s,&c);
    r->y=(short)(((int)s*r->radius>>8)+r->base);
}

/* ------------------------------------------------------ part 1: focused */
static const unsigned retail_subtypes[]={0x00,0x04,0x05,0x40,0x44,0x45,0x48};

static void test_tables(void){
    /* Expected values straight from PISTON.C: sprhsize 32 always (:117,:129);
       sprvsize 32 for init_piston0 (:117) and 96 for init_piston1 (:130);
       spd_tbl {4,8,16,32} (:113) indexed by (b&12)/4 or (b&4)/4 (:118,:131);
       radius_tbl {32,48} by bit 6 (:81,:100); delay 60 when bit 3 is clear (:126,:133). */
    static const struct {unsigned sub,v,spd,radius,patno,delay;} want[]={
        {0x00,32, 4,32,0, 0},{0x04,32, 8,32,0, 0},{0x05,96, 8,32,1,60},
        {0x40,32, 4,48,0, 0},{0x44,32, 8,48,0, 0},{0x45,96, 8,48,1,60},{0x48,32,16,48,0,0}};
    for(unsigned n=0;n<sizeof want/sizeof *want;n++){
        flat_start();
        int slot=scd_objects_spawn(SCD_OBJ_PISTON,3000,700,want[n].sub,0);
        CHECK(slot>=0,"subtype %#x did not spawn",want[n].sub);if(slot<0)continue;
        /* PISTON.C:61-66: the first update runs piston_init only. */
        scd_player_step(0);
        sprite_status *o=piston_actor(slot);
        CHECK(o->sprhsize==32 && o->sprvsize==want[n].v,"subtype %#x size %ux%u, want 32x%u",want[n].sub,o->sprhsize,o->sprvsize,want[n].v);
        CHECK((short)scd_word_get(o,28)==(short)want[n].spd,"subtype %#x speed %d want %u",want[n].sub,(short)scd_word_get(o,28),want[n].spd);
        CHECK((short)scd_word_get(o,29)==(short)want[n].radius,"subtype %#x radius %d want %u",want[n].sub,(short)scd_word_get(o,29),want[n].radius);
        CHECK((short)scd_word_get(o,27)==0 && (short)scd_word_get(o,26)==700,"subtype %#x start angle/base",want[n].sub);
        CHECK(o->patno==want[n].patno,"subtype %#x patno %u",want[n].sub,o->patno);
        if(want[n].patno)CHECK(o->actfree[14]==want[n].delay,"subtype %#x delay %u",want[n].sub,o->actfree[14]);
    }
    printf("tables: %u retail subtypes checked\n",(unsigned)(sizeof want/sizeof *want));
}

static void test_motion(void){
    for(unsigned n=0;n<sizeof retail_subtypes/sizeof *retail_subtypes;n++){
        unsigned sub=retail_subtypes[n];
        flat_start();
        int slot=scd_objects_spawn(SCD_OBJ_PISTON,3000,700,sub,0);sprite_status *o=piston_actor(slot);
        ref_piston r;ref_init(&r,sub,700);
        int lo=700,hi=700,mismatch=-1;short ys[1200];
        for(unsigned t=0;t<1200;t++){
            /* PISTON.C:61-66: update 0 runs piston_init only (ec10139). */
            scd_player_step(0);if(t)ref_step(&r);ys[t]=o->yposi.w.h;
            if(o->yposi.w.h!=r.y && mismatch<0)mismatch=(int)t;
            if(o->yposi.w.h<lo)lo=o->yposi.w.h;if(o->yposi.w.h>hi)hi=o->yposi.w.h;
            CHECK(o->xposi.w.h==3000,"subtype %#x moved in x",sub);
        }
        short radius=(sub&64)?48:32;
        CHECK(mismatch<0,"subtype %#x diverges from PISTON.C at update %d",sub,mismatch);
        CHECK(lo==700-radius && hi==700+radius,"subtype %#x y range %d..%d, want %d..%d",sub,lo,hi,700-radius,700+radius);
        /* Period: 1024/speed updates for init_piston0; init_piston1 adds a
           hold at angle 256 and at 768 of 1 + delay updates each (:153-166). */
        unsigned period=(sub&3)==1?1024/8+2*61:1024/(unsigned)((short)scd_word_get(o,28));
        int periodic=1;for(unsigned t=0;t+period<1200;t++)if(ys[t]!=ys[t+period])periodic=0;
        CHECK(periodic,"subtype %#x not periodic over %u updates",sub,period);
        if((sub&3)==1){
            /* The bottom (angle 256) holds for the arrival update, the update
               that sets the hold, and 60 counted updates: 62 updates at base+r. */
            unsigned run=0,best=0;for(unsigned t=0;t<period*2;t++){if(ys[t]==700+radius){if(++run>best)best=run;}else run=0;}
            CHECK(best==62,"subtype %#x bottom hold %u updates, want 62",sub,best);
        }
        printf("motion %#04x: y %d..%d, period %u, matches PISTON.C\n",sub,lo,hi,period);
    }
}

/* Side block: hit_x (RIDECHK.C:385) puts the player at piston x -/+ (32+10).
   PISTON.C runs ride_on_chk before the move only while yspeed<0 (:149) and
   after it only while yspeed>=0 (:199), so on the update the piston turns
   from rest or descent to ascent there is no check at all and a walking
   player may overlap by his own step for that one update. */
static void test_block(void){
    for(unsigned n=0;n<sizeof retail_subtypes/sizeof *retail_subtypes;n++){
        unsigned sub=retail_subtypes[n];
        for(int side=0;side<2;side++){
            flat_start();
            /* Base chosen so the piston's whole travel overlaps a standing
               player (centre y 1004) by more than 4 px vertically. */
            int base=(sub&3)==1?1000:(sub&64)?1004:990;
            int slot=scd_objects_spawn(SCD_OBJ_PISTON,1000,base,sub,0);
            scd_player_place(side?1060:940,1005,0,0,0);
            int want=side?1000+42:1000-42,worst=0,settled=0;
            for(unsigned t=0;t<600;t++){
                scd_player_step(side?SCD_LEFT:SCD_RIGHT);
                int over=side?want-actwk[0].xposi.w.h:actwk[0].xposi.w.h-want;
                if(over>worst)worst=over;
                if(actwk[0].xposi.w.h==want)settled++;
            }
            CHECK(actwk[0].r_no0==2 && !(actwk[0].cddat&2),"subtype %#x %s: player not standing (routine %u)",sub,side?"left":"right",actwk[0].r_no0);
            CHECK(actwk[0].xposi.w.h==want && worst<=1 && settled>=500,"subtype %#x %s: player at %d (overlap %d, %d updates at %d)",sub,side?"left":"right",actwk[0].xposi.w.h,worst,settled,want);
            if(!n || sub==0x45)printf("block %#04x from %s: held at x=%d for %d of 600 updates, max one-update overlap %d px\n",sub,side?"right":"left",want,settled,worst);
            (void)slot;
        }
    }
}

/* Standing and carry. hit_y (RIDECHK.C:490-491,514-515) sets the rider's
   centre to piston y - (sprvsize + 19) and then adds the piston's yspeed.
   PISTON.C calls it after the move while yspeed>=0 (:199-200) and before the
   move, with the previous position and speed, while yspeed<0 (:149); on the
   update the piston turns upward neither call runs. So, per update:
     yspeed>=0            rider y = y - stand + dy
     yspeed<0, was <0     rider y = previous y - stand + previous dy
     yspeed<0, was >=0    rider y unchanged
   and the rider is carried the piston's full travel of 2*radius. */
static void test_ride(void){
    for(unsigned n=0;n<sizeof retail_subtypes/sizeof *retail_subtypes;n++){
        unsigned sub=retail_subtypes[n];
        int tall=(sub&3)==1,radius=(sub&64)?48:32,stand=(tall?96:32)+19,base=tall?900:860;
        flat_start();
        int slot=scd_objects_spawn(SCD_OBJ_PISTON,2000,base,sub,0);sprite_status *o=piston_actor(slot);
        scd_player_place(2000,base-(tall?96:32)-40,0,0,2);
        unsigned t;for(t=0;t<300 && !riding(slot);t++)scd_player_step(0);
        CHECK(riding(slot),"subtype %#x player never landed",sub);
        int x0=actwk[0].xposi.w.h,lost=0,wrong=0,top_y=0,bottom_y=0,bottom_dy=0,prev_y=o->yposi.w.h,prev_v=o->yspeed.w,prev_p=actwk[0].yposi.w.h;
        unsigned span=tall?300:1100;
        for(t=0;t<span;t++){
            scd_player_step(0);
            if(!riding(slot)){lost=1;break;}
            int y=o->yposi.w.h,v=o->yspeed.w,py=actwk[0].yposi.w.h;
            int want=v>=0?y-stand+(v>>8):prev_v<0?prev_y-stand+(prev_v>>8):prev_p;
            if(py!=want && !wrong){wrong=1;CHECK(0,"subtype %#x update %u: rider y %d, want %d (piston y %d yspeed %d, was %d/%d)",sub,t,py,want,y,v,prev_y,prev_v);}
            if(y==base-radius && v==0)top_y=py;
            if(y==base+radius && v>0){bottom_y=py;bottom_dy=v>>8;}
            CHECK(actwk[0].xposi.w.h==x0,"subtype %#x carried sideways",sub);
            prev_y=y;prev_v=v;prev_p=py;
            if(tall && (short)scd_word_get(o,27)>=520)break; /* stop before the launch */
        }
        CHECK(!lost,"subtype %#x player fell off at update %u",sub,t);
        CHECK(bottom_y==base+radius-stand+bottom_dy,"subtype %#x rider y at the bottom %d",sub,bottom_y);
        if(tall){
            /* A launcher throws its rider at angle 528 on the way up, before
               the top; the launch itself is checked in test_launch. */
            printf("ride %#04x: rider y follows PISTON.C/hit_y every update to angle 520, stands at piston y-%d\n",sub,stand);
            continue;
        }
        CHECK(top_y==base-radius-stand,"subtype %#x rider y at the top %d, want %d",sub,top_y,base-radius-stand);
        CHECK(bottom_y && bottom_y-bottom_dy-top_y==2*radius,"subtype %#x carried %d px, want %d",sub,bottom_y-bottom_dy-top_y,2*radius);
        printf("ride %#04x: rider y follows PISTON.C/hit_y every update, stands at piston y-%d, carried %d px\n",sub,stand,bottom_y-bottom_dy-top_y);
    }
}

/* Launcher (b&3==1): at angle 528 a rider gets yspeed jump_tbl[bit 7] = -4096
   for the retail subtypes (PISTON.C:145-147,188-196). */
static void test_launch(void){
    for(unsigned n=0;n<sizeof retail_subtypes/sizeof *retail_subtypes;n++){
        unsigned sub=retail_subtypes[n];
        if((sub&3)!=1)continue;
        flat_start();
        int slot=scd_objects_spawn(SCD_OBJ_PISTON,2600,880,sub,0);sprite_status *o=piston_actor(slot);
        scd_player_place(2600,650,0,0,2);
        unsigned t;for(t=0;t<200 && !riding(slot);t++)scd_player_step(0);
        CHECK(riding(slot),"subtype %#x player never landed",sub);
        int launched=0,launch_y=0,apex=0;
        for(t=0;t<800 && !launched;t++){
            scd_player_step(0);
            if((short)scd_word_get(o,27)==528){
                launched=1;launch_y=actwk[0].yposi.w.h;
                CHECK(actwk[0].yspeed.w==-4096,"subtype %#x launch yspeed %d",sub,actwk[0].yspeed.w);
                CHECK((actwk[0].cddat&2) && !(actwk[0].cddat&8) && !(o->cddat&8),"subtype %#x launch flags %#x",sub,actwk[0].cddat);
                CHECK(actwk[0].mstno.b.h==16,"subtype %#x launch animation %u",sub,actwk[0].mstno.b.h);
            }
        }
        CHECK(launched,"subtype %#x never reached angle 528 with a rider",sub);
        apex=launch_y;for(t=0;t<120;t++){scd_player_step(0);if(actwk[0].yposi.w.h<apex)apex=actwk[0].yposi.w.h;}
        CHECK(launch_y-apex>=500,"subtype %#x launch rose only %d px",sub,launch_y-apex);
        printf("launch %#04x: yspeed -4096 at angle 528, rose %d px\n",sub,launch_y-apex);
    }
}

/* Crush: a descending piston that meets a grounded player from above kills
   him (hit_yu1, RIDECHK.C:587-593). */
static void test_crush(void){
    flat_start();
    int slot=scd_objects_spawn(SCD_OBJ_PISTON,3400,940,0x00,0);sprite_status *o=piston_actor(slot);
    scd_player_place(3400,1005,0,0,0);
    unsigned t,dead=0;int piston_y=0,piston_vy=0;
    for(t=0;t<300;t++){scd_player_step(0);if(actwk[0].r_no0==6){dead=1;piston_y=o->yposi.w.h;piston_vy=o->yspeed.w;break;}}
    CHECK(dead,"grounded player under a descending piston was not crushed");
    CHECK(scd_objects_get().deaths==1,"crush did not record a death");
    printf("crush: player killed at update %u, piston y=%d yspeed=%d\n",t,piston_y,piston_vy);
    /* hit_yu1 only kills a grounded player. Rising into the bottom of the
       same descending piston while airborne pushes him below it with yspeed
       0 (hit_yu0, RIDECHK.C:610-612). This piston hangs high enough that it
       never reaches the floor, so the player only meets it in the air. */
    flat_start();
    slot=scd_objects_spawn(SCD_OBJ_PISTON,3400,800,0x00,0);o=piston_actor(slot);
    scd_player_place(3400,900,0,0,2);scd_player_velocity(0,-2048);
    int bumped=-1,bump_y=0,bump_piston=0;
    for(t=0;t<200;t++){
        scd_player_step(0);
        CHECK(actwk[0].r_no0!=6,"airborne player crushed at update %u",t);
        if(bumped<0 && actwk[0].yspeed.w==0 && (actwk[0].cddat&2)){bumped=(int)t;bump_y=actwk[0].yposi.w.h;bump_piston=o->yposi.w.h;CHECK(o->yposi.w.h>800 && (short)scd_word_get(o,27)<512,"piston was not on its way down at the bump");}
    }
    CHECK(bumped>=0 && bump_y==bump_piston+32+19+2,"airborne bump at update %d: player y %d, piston y %d",bumped,bump_y,bump_piston);
    printf("crush: airborne bump at update %d pushed the player to piston y+53 with no death\n",bumped);
}

/* ------------------------------------------------------- part 2: stall */
static uint8_t stage_data[300000],stage_collision[9472],layout[8192];
static size_t slurp(const char *path,uint8_t *out,size_t cap){
    FILE *f=fopen(path,"rb");if(!f){printf("FAIL missing %s\n",path);exit(2);}
    size_t n=fread(out,1,cap,f);fclose(f);return n;
}
static stage_t act_stage;static size_t layout_size;
static void load_r82(unsigned era){
    char path[512];char letter="ABCD"[era];
    snprintf(path,sizeof path,"%s/assets/generated/mm82%c.bin",root,letter);size_t n=slurp(path,stage_data,sizeof stage_data);
    snprintf(path,sizeof path,"%s/assets/generated/mmcollision82%c.bin",root,letter);
    if(slurp(path,stage_collision,sizeof stage_collision)!=sizeof stage_collision){printf("FAIL collision size\n");exit(2);}
    snprintf(path,sizeof path,"%s/build/auto-extract/8/objects82%c.bin",root,letter);layout_size=slurp(path,layout,sizeof layout);
    if(stage_open(&act_stage,stage_data,n)){printf("FAIL stage_open %s\n",path);exit(2);}
}
typedef struct {int lift,crusher,spawned_pistons,spawned_springs;} r82_objects;
/* Spawn every retail record near the route whose object the port has: piston
   (R8 id 52) and spring (R8 id 10, SPRING.C, already SCD_OBJ_SPRING). Record
   layout per ACTSET.C actnoset/tm_setchk: x, y (bits 14-15 flip, 0-11 y),
   a (bit 7 one-shot, id), b subtype, c>>5 era mask Past/Present/Future, d. */
static r82_objects start_r82(unsigned era,int pistons){
    r82_objects r={-1,-1,0,0};
    scd_player_zone(6);scd_objects_zone(6);scd_player_act(1);scd_objects_act(1);
    if(scd_player_init(&act_stage,stage_collision,sizeof stage_collision,era)){printf("FAIL R82 init\n");exit(1);}
    unsigned bit=era==0?2:era==1?1:4;
    for(size_t k=0;k+8<=layout_size;k+=8){
        unsigned x=layout[k]<<8|layout[k+1],yw=layout[k+2]<<8|layout[k+3],id=layout[k+4]&127,sub=layout[k+5],eras=layout[k+6]>>5;
        if(x==0xffff)break;
        if(x>1000 || !(eras&bit))continue;
        unsigned y=yw&4095,flags=(yw>>14)&3;
        if(id==52 && pistons){
            int slot=scd_objects_spawn(SCD_OBJ_PISTON,x,y,sub,flags);
            if(slot>=0)r.spawned_pistons++;
            if(x==432 && y==1182)r.lift=slot;
            if(x==321 && y==1182)r.crusher=slot;
        }
        if(id==10 && scd_objects_spawn(SCD_OBJ_SPRING,x,y,sub,flags)>=0)r.spawned_springs++;
    }
    return r;
}

/* The stock walker of tools/zone_walk_test.c (Right, one-frame Jump when stuck
   30 updates), optionally holding Jump while rising. */
static int walker(unsigned era,int pistons,int hold){
    start_r82(era,pistons);
    scd_player_state p=scd_player_get();int max_x=p.x>>16,last=max_x,holding=0;unsigned stuck=0;
    for(unsigned u=0;u<20000;u++){
        unsigned b=SCD_RIGHT;
        if(stuck>=30 && !(p.flags&2)){b|=SCD_JUMP;stuck=0;holding=hold;}
        else if(holding && (p.flags&2) && p.vy<0)b|=SCD_JUMP;else holding=0;
        scd_player_step(b);p=scd_player_get();int x=p.x>>16;
        if(x>last+1){stuck=0;last=x;}else stuck++;
        if(x>max_x)max_x=x;
    }
    return max_x;
}

/* Scripted route through the sealed R82 corridor. The column at x=512..527
   is solid from y=752 down to y=1379; the only way over it starts in the
   96 px corridor, rises through the x=416..479 shaft, and climbs to the spring
   on the box to the LEFT. So this is a route script with Left inputs, not the
   Right-only walker. It reads the lift piston's Y only to time its jumps.
     pit        run in, wait at x 380..389 (outside the lift's reach) until the
                lift piston (432,1182) bottoms out, held-jump onto it
     lift       ride it up the shaft; at the top (piston y<=1151) held-jump
                left onto the ledge at y=1024
     box        held-jump left onto the box top at y=928
     spring     walk left to the spring (275,920), hop onto it
     launch     hold Right until clear of the hanging piston (240,580), whose
                underside stops a straight launch, then Left once falling
     run        hold Right: off the gear-shaped terrain at (368,461) or the
                platforms at y=576, over the column onto the ledge at y=752
   Present only: the crusher piston (321,1182) blocks the ledge at x=279; hop
   onto it while it is low and run off its far side. Springs launch the player
   into the shaft or onto the right ledge; both are handled by retries.
   With no lift piston the pit jump fires on a timer instead, so the control
   run makes the same attempts into the empty shaft. */
typedef struct {int max_x,min_y,passed,x,y,updates,deaths;unsigned rides,launches;} route_result;
static route_result route(unsigned era,int pistons){
    r82_objects r=start_r82(era,pistons);
    route_result out={0};int phase=0,timer=0,was_air=0,lift_rider=0;out.min_y=2048;
    for(unsigned u=0;u<12000;u++){
        scd_player_state p=scd_player_get();int x=p.x>>16,y=p.y>>16,air=p.flags&2;
        int landed=was_air && !air;was_air=air;
        int on_lift=r.lift>=0 && riding(r.lift),ly=r.lift>=0?piston_actor(r.lift)->yposi.w.h:0;
        int cy=r.crusher>=0?piston_actor(r.crusher)->yposi.w.h:0;
        if(on_lift && !lift_rider)out.rides++;lift_rider=on_lift;
        unsigned b=0;timer++;
        switch(phase){
        case 0: b=SCD_RIGHT;
            if(on_lift){phase=3;timer=0;}
            else if(x>=360 && !air && y>1230){phase=1;timer=0;}
            else if(x>=470 && !air && y>=1000 && y<=1010){phase=13;timer=0;}
            else if(r.crusher>=0 && x>=265 && x<=285 && !air && y>=1190 && y<=1200){phase=14;timer=0;}
            break;
        case 1: if(on_lift){phase=3;timer=0;break;}
            if(x<380)b=SCD_RIGHT;else if(x>389)b=SCD_LEFT;
            if((r.lift>=0?ly>=1210:timer>30) && !air && x>=380 && x<=389 && timer>2){phase=2;timer=0;}
            break;
        case 2: b=SCD_JUMP|SCD_RIGHT;if(landed){phase=on_lift?3:1;timer=0;}break;
        case 3: if(x<440)b=SCD_RIGHT;else if(x>452)b=SCD_LEFT;
            if(!on_lift && !air && timer>2){phase=0;timer=0;break;}
            if(ly<=1151 && on_lift){phase=4;timer=0;}
            break;
        case 4: b=SCD_JUMP|SCD_LEFT;if(landed){phase=(y>=1000 && y<=1010)?5:0;timer=0;}break;
        case 5: b=SCD_LEFT;if(timer>=3){phase=6;timer=0;}break;
        case 6: b=SCD_JUMP|SCD_LEFT;if(landed){phase=(y>=900 && y<=912)?7:(y>=1000 && y<=1010)?5:0;timer=0;}break;
        /* RIDECHK.C hit_x: the spring's side is solid, so walking left stops
           against it (push flag); hop onto it from there. */
        case 7: b=SCD_LEFT;if(x<=270 || (p.flags&32) || timer>120){phase=8;timer=0;}break;
        case 8: b=SCD_JUMP|SCD_LEFT;if(timer>2){phase=9;timer=0;}break;
        case 9: if(p.vy<-2000){phase=10;timer=0;out.launches++;}if(landed){phase=7;timer=0;}break;
        case 10: if(p.vy<0 && x<292)b=SCD_RIGHT;else if(p.vy>=0)b=SCD_LEFT;
            if(landed){phase=y>880?7:11;timer=0;}
            break;
        case 11: b=SCD_RIGHT;if(landed && y>880){phase=7;timer=0;}break;
        case 13: b=timer<3?0:(SCD_JUMP|SCD_LEFT);
            if(timer>6 && landed){phase=(y>=1000 && y<=1010 && x<=424)?5:0;timer=0;}
            break;
        case 14: if(cy>=1210 && timer>2){phase=15;timer=0;}break;
        case 15: b=SCD_RIGHT|(timer<30?SCD_JUMP:0);if(timer>6 && landed){phase=0;timer=0;}break;
        }
        /* The game's camera follows Sonic; MM springs act only on screen
           (SPRING.C:399-404), so centre a view on him. */
        {void scd_act_camera(int,int);scd_player_state c=scd_player_get();scd_act_camera(c.x/65536-160,c.y/65536-112);}
        scd_player_step(b);
        p=scd_player_get();x=p.x>>16;y=p.y>>16;out.updates=(int)u+1;
        if(x>out.max_x)out.max_x=x;
        if(y<out.min_y)out.min_y=y;
        if(p.resets){out.deaths=(int)p.resets;break;}
        /* Past the column: right of x=527 and above its top at y=752. */
        if(x>=560 && y<=752 && !(p.flags&2)){out.passed=1;break;}
    }
    scd_player_state p=scd_player_get();out.x=p.x>>16;out.y=p.y>>16;
    return out;
}

static void test_stall(void){
    static const unsigned eras[3]={0,2,3};static const char *names[3]={"R82A","R82C","R82D"};
    for(unsigned n=0;n<3;n++){
        load_r82(eras[n]);
        r82_objects spawned=start_r82(eras[n],1);
        int stock=walker(eras[n],1,0),held=walker(eras[n],1,1);
        route_result with=route(eras[n],1),without=route(eras[n],0);
        printf("%s: spawned %d pistons + %d springs at retail placements\n",names[n],spawned.spawned_pistons,spawned.spawned_springs);
        printf("  stock walker (1-frame Jump), pistons spawned: max_x=%d\n",stock);
        printf("  walker holding Jump,         pistons spawned: max_x=%d\n",held);
        printf("  route script, pistons:    %s max_x=%d min_y=%d end (%d,%d) after %d updates, lift rides %u, spring launches %u, deaths %d\n",
               with.passed?"PASS":"stuck",with.max_x,with.min_y,with.x,with.y,with.updates,with.rides,with.launches,with.deaths);
        printf("  route script, no pistons: %s max_x=%d min_y=%d end (%d,%d) after %d updates, spring launches %u, deaths %d\n",
               without.passed?"PASS":"stuck",without.max_x,without.min_y,without.x,without.y,without.updates,without.launches,without.deaths);
        CHECK(with.passed && with.max_x>501 && with.deaths==0,"%s: route did not pass the x=501 stall with the pistons",names[n]);
        CHECK(with.rides>=1,"%s: route never rode the lift piston",names[n]);
        /* The Futures have no Present-only spring (376,1240), so there the
           lift piston is the only way into the shaft. */
        if(eras[n]>=2)CHECK(!without.passed && without.max_x<=501,"%s: passed without the pistons",names[n]);
    }
}

int main(int argc,char **argv){
    if(argc>1)root=argv[1];
    flat_init();
    test_tables();
    test_motion();
    test_block();
    test_ride();
    test_launch();
    test_crush();
    test_stall();
    if(failures){printf("%u failure(s)\n",failures);return 1;}
    printf("PASS: piston focused and stall tests\n");
    return 0;
}
