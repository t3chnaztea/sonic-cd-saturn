/* Cross-target semantic QA probe. Runs only in explicit diagnostic mode. */
#include "EQU.H"
#include "PLAYER.H"
#include "scd_actor.h"
#include "world.h"
#include "act.h"
#include "background.h"
#include "scd_objects.h"
#include "world_qa.h"
static const uint8_t *const *qa_collision;
static stage_t stages[4];
static int qa_error;
volatile uint32_t scd_world_probe_iteration;
#define CHECK(test) do {if(!(test))return __LINE__;}while(0)
/* SH-2 GCC reserves a different aggregate-return temporary for each field-only
   scd_player_get() expression. Hundreds of such expressions exhaust the small
   diagnostic stack as the player record grows. One non-recursive snapshot
   retains the same read-only observations without those simultaneous slots. */
static const scd_player_state *__attribute__((noinline)) qa_player(void){
    static scd_player_state snapshot;snapshot=scd_player_get();return &snapshot;
}
static void init(unsigned era){if(scd_player_init(&stages[era],qa_collision[era],9472,era))qa_error=1;scd_objects_reset(era,0);scd_player_place(80,488,0,0,2);}
static scd_object_view view(unsigned id){scd_object_view a[96];unsigned n=scd_objects_views(a,96);for(unsigned i=0;i<n;i++)if(a[i].type==id)return a[i];qa_error=1;return (scd_object_view){0};}
static int __attribute__((noinline)) world_probe(const uint8_t *const *packs,const size_t *sizes,const uint8_t *const *collisions){
    qa_collision=collisions;qa_error=0;
    scd_world_zone(0);scd_world_act(0);
    for(unsigned era=0;era<4;era++)CHECK(!stage_open(&stages[era],packs[era],sizes[era]));
    unsigned species[]={34,61,62,63,64};unsigned cases=0;
    for(unsigned k=0;k<5;k++)for(unsigned damaged=0;damaged<2;damaged++){
        unsigned type=species[k],sub=damaged?(type==34?2:1):0;
        init(1);CHECK(scd_objects_spawn(type,500,400,sub,0)>=0);
        int minx=500,maxx=500,miny=400,maxy=400;
        for(unsigned tick=0;tick<360;tick++){
            scd_objects_step(80,488);scd_object_view o=view(type);
            if(o.x<minx)minx=o.x;if(o.x>maxx)maxx=o.x;if(o.y<miny)miny=o.y;if(o.y>maxy)maxy=o.y;
            CHECK(o.x>=372 && o.x<=628);CHECK(o.frame<(type==34?6:type==61?10:type==62?6:type==63?4:14));
        }
        if(type==61 || type==62)CHECK(minx<490 && maxx<=628);
        if(type==62 || type==64)CHECK(miny<390);
        /* Attack and hurt each use an independently reset encounter. */
        for(unsigned attack=0;attack<2;attack++){
            init(1);scd_player_inventory(1,0);scd_player_place(500,488,0,0,attack?6:2);
            CHECK(scd_objects_spawn(type,500,488,sub,0)>=0);
            /* Player_ObjCollide reads the previous update: Tagataga touches from
               the update after it rises in state 1 (objects.c touch_arbitrate). */
            if(type==64)for(unsigned n=0;n<92;n++)scd_objects_step(500,488);
            scd_objects_step(500,488);
            if(attack){CHECK(scd_objects_get().defeated==1);CHECK(qa_player()->routine==2);}
            else CHECK(scd_objects_get().hits==1);
        }
        cases++;
    }
    init(2);for(unsigned k=0;k<5;k++)CHECK(scd_objects_spawn(species[k],500,400,0,0)<0);
    init(1);scd_player_place(520,488,0,0,2);scd_player_inventory(5,1);scd_objects_spawn(34,500,493,0,0);
    for(unsigned n=0;n<100;n++)scd_objects_step(520,488);
    CHECK(scd_objects_get().projectiles==2);
    scd_player_place(3000,488,0,0,2);for(unsigned n=0;n<250;n++)scd_objects_step(3000,488);
    scd_object_view a[96];unsigned total=scd_objects_views(a,96);for(unsigned i=0;i<total;i++)CHECK(!(a[i].type==34 && a[i].subtype==1));
    for(unsigned era=0;era<4;era++)for(int direction=-1;direction<=1;direction+=2){
        scd_world_reset(era);scd_world_activate(direction);scd_player_state p={.x=3000*65536,.speed=1536,.routine=2};int dest=-1;
        for(unsigned n=0;n<229;n++)CHECK(scd_world_step(p)==-1);
        dest=scd_world_step(p);CHECK(dest>=0 && dest<4);
        unsigned expected=era==1?(direction<0?1:0):era==0?(direction<0?1:3):(direction<0?0:era);
        CHECK((unsigned)dest==expected);scd_world_arrived(dest);CHECK(scd_world_get().transitions==1 && !scd_world_get().direction);cases++;
    }
    scd_player_state p={.x=3000*65536,.speed=1536,.routine=2};
    scd_world_reset(0);scd_world_activate(-1);for(unsigned n=0;n<80;n++)scd_world_step(p);p.speed=0;scd_world_step(p);CHECK(!scd_world_get().ticks && scd_world_get().direction==-1);
    p.speed=1536;for(unsigned n=0;n<100;n++)scd_world_step(p);p.speed=0;scd_world_step(p);CHECK(!scd_world_get().direction && scd_world_get().cancelled==1);
    p.speed=1536;scd_world_reset(0);scd_world_activate(1);
    for(unsigned n=0;n<30;n++)scd_world_step_vblanks(p,3);
    CHECK(scd_world_get().ticks==91);
    p.speed=0;scd_world_step_vblanks(p,1);CHECK(!scd_world_get().direction);
    p.speed=1536;scd_world_reset(0);scd_world_activate(1);
    for(unsigned n=0;n<53;n++)scd_world_step_vblanks(p,4);
    CHECK(scd_world_get().ticks==213 && scd_world_get().destination<0);
    scd_world_step_vblanks(p,1);CHECK(scd_world_get().destination==3);
    scd_world_reset(0);scd_world_generator_destroyed();scd_world_activate(1);p.speed=1536;for(unsigned n=0;n<230;n++)scd_world_step(p);CHECK(scd_world_step(p)==2);
    scd_world_reset(1);scd_world_activate(1);p.x=1000*65536;scd_world_step(p);CHECK(!scd_world_get().direction);
    /* ObjSonic_TimeWarp: the X $900 stop applies to PPZ Act 1 only; Act 2 past warps there. */
    scd_world_act(1);scd_world_reset(1);scd_world_activate(1);scd_world_step(p);CHECK(scd_world_get().direction==1 && scd_world_get().ticks==2);
    for(unsigned n=0;n<229;n++)scd_world_step(p);CHECK(scd_world_step(p)==0);scd_world_act(0);
    /* The console compares the full zoneAct word with zero, not just its
       act byte. Check both sides of the ramp boundary in every zone/era,
       then return to PPZ so this also exercises resetting the zone context. */
    for(unsigned zone=0;zone<7;zone++)for(unsigned act=0;act<2;act++)
        for(unsigned e=0;e<4;e++)for(int x=2303;x<=2304;x++){
            scd_world_zone(zone);scd_world_act(act);scd_world_reset(e);scd_world_activate(1);
            p.x=x*65536;p.speed=1536;CHECK(scd_world_step(p)==-1);
            int blocked=!zone && !act && e!=0 && x<2304;
            CHECK(scd_world_get().direction==(blocked?0:1));
            CHECK(scd_world_get().ticks==(blocked?0:2));
            if(!blocked){for(unsigned n=0;n<229;n++)scd_world_step(p);CHECK(scd_world_step(p)>=0);}
        }
    scd_world_zone(0);scd_world_act(0);scd_world_reset(1);scd_world_activate(1);
    p.x=2303*65536;scd_world_step(p);CHECK(!scd_world_get().direction);
    init(0);scd_player_inventory(23,1);scd_player_place(3000,400,1536,0,6);CHECK(!scd_player_arrive(&stages[1],qa_collision[1],9472,1));scd_player_state landed=scd_player_get();CHECK(landed.speed==1536 && landed.rings==23 && !landed.shield && landed.hurt==120);
    CHECK(scd_player_arrival_adjusted()>0 && scd_player_arrival_clear());
    CHECK(scd_player_level_frames()==0); /* the arrival program starts its own palette clock */
    init(0);scd_player_place(3000,64,1536,0,6);CHECK(!scd_player_arrive(&stages[1],qa_collision[1],9472,1));
    CHECK(qa_player()->x==3000*65536 && qa_player()->y==64*65536 && !scd_player_arrival_adjusted());
    init(1);scd_player_place(500,488,0,0,6);scd_objects_spawn(SCD_OBJ_GENERATOR,500,500,0,0);scd_objects_step(500,488);
    CHECK(scd_objects_generator()==1 && scd_objects_generator()==0);
    scd_objects_change_era(3);CHECK(scd_objects_spawn(63,500,488,0,0)<0);
    init(1);scd_player_place(500,488,0,0,0);scd_player_inventory(5,0);scd_objects_travel_protection(1);scd_objects_spawn(63,500,488,0,0);scd_objects_step(500,488);
    CHECK(scd_objects_get().defeated==1 && qa_player()->rings==5);
    init(1);scd_player_place(500,488,0,0,0);scd_objects_spawn(25,500,488,9,0);scd_objects_step(500,488);CHECK(scd_objects_timepost()==1);scd_objects_step(500,488);CHECK(!scd_objects_timepost());
    scd_world_reset(0);scd_world_activate(1);scd_world_abort();CHECK(scd_world_get().cancelled==1 && !scd_world_get().direction);
    CHECK(scd_background_y(1,800,3000)==100);CHECK(scd_background_y(0,800,3000)==640);
    CHECK(scd_background_x(1,1600,80,0)==200);CHECK(scd_background_x(1,1600,160,0)==300);
    CHECK(scd_background_x(2,1600,160,0)==400);CHECK(scd_background_x(0,1600,608,0)==800);
    CHECK(scd_background_x(1,1600,0,60)==260);
    uint16_t pal0[64],pal1[64];scd_background_palette(0,0,stages[0].part[5],pal0);scd_background_palette(0,9,stages[0].part[5],pal1);CHECK(pal0[49]!=pal1[49]);
    /* Ramp detection uses the original layout chunk list in chk11. */
    init(0);
    for(unsigned chunk=0;chunk<5;chunk++){
        const unsigned ids[]={6,7,8,73,76};int found=0;
        for(unsigned n=0;n<512;n++)if(stages[0].part[3][n]==ids[chunk]){
            scd_player_place((n%64)*256+128,(n/64)*256+128,0,0,2);chk11();CHECK(qa_player()->ramp);found=1;break;
        }CHECK(found);
    }
    /* Leaving a ramp upwards beyond -8px/tick gains a facing-dependent boost. */
    for(unsigned left=0;left<2;left++){
        scd_player_place(80,64,0,0,left|2);actwk[0].actfree[2]=2;actwk[0].yspeed.w=-2049;chk11();
        CHECK(!qa_player()->ramp);CHECK(qa_player()->vx==(left?-1536:1536));
    }
    scd_player_place(80,64,0,0,2);actwk[0].actfree[2]=2;actwk[0].yspeed.w=-2048;chk11();CHECK(!qa_player()->vx);
    for(unsigned airborne=0;airborne<2;airborne++)for(int direction=-1;direction<=1;direction+=2){
        init(0);scd_player_place(500,488,0,0,airborne?2:0);actwk[0].yspeed.w=direction*256;
        CHECK(scd_objects_spawn(SCD_OBJ_RAMP,500,488,0,0)>=0);scd_objects_step(500,488);
        CHECK(qa_player()->vy==direction*(airborne?256:3072));
        if(!airborne){actwk[0].cddat|=2;actwk[0].yspeed.w=direction*128;scd_objects_step(500,488);CHECK(qa_player()->vy==direction*3072);}
    }
    init(0);scd_player_place(500,488,0,0,2);actwk[0].actfree[2]=2;
    CHECK(!scd_player_arrive(&stages[1],qa_collision[1],9472,1));CHECK(!qa_player()->ramp);
    init(0);scd_player_place(505,488,0,0,2);actwk[0].xspeed.w=-256;
    CHECK(scd_objects_spawn(SCD_OBJ_RAMP,512,488,129,0)>=0);scd_objects_step(505,488);
    CHECK(qa_player()->x==512*65536 && !qa_player()->vx && qa_player()->animation==55);
    CHECK(!scd_objects_views(a,96));
    /* Booster perspective clamp and mirrored plant movement. */
    init(0);scd_player_place(704,488,0,0,2);actwk[0].actfree[2]=2;
    scd_objects_spawn(SCD_OBJ_RAMP,500,488,0,0);scd_objects_step(704,488);
    CHECK(view(SCD_OBJ_RAMP).x==570 && view(SCD_OBJ_RAMP).frame==3);
    actwk[0].xposi.w.h=752;scd_objects_step(752,488);CHECK(view(SCD_OBJ_RAMP).x==500);
    init(0);scd_player_place(608,488,0,0,2);actwk[0].actfree[2]=2;
    scd_objects_spawn(SCD_OBJ_RAMP_PLANT,576,488,0,0);scd_objects_step(608,488);CHECK(view(SCD_OBJ_RAMP_PLANT).x==624);
    actwk[0].xposi.w.h=416;scd_objects_step(416,488);CHECK(view(SCD_OBJ_RAMP_PLANT).x==529);
    scd_background_scroll scroll;scd_background_reset(&scroll,100);
    scd_background_step(&scroll,0,101,384,1);CHECK(scroll.ramp==384);
    scd_background_step(&scroll,0,101,384,1);CHECK(scroll.ramp==384);
    scd_background_step(&scroll,0,102,384,0);CHECK(scroll.ramp==384);
    scd_background_step(&scroll,1,103,384,1);CHECK(scroll.ramp==384);
    CHECK(scd_background_raster_x(0,1600,0,0,scroll.ramp)==201);
    CHECK(scd_background_raster_x(0,1600,500,0,scroll.ramp)==303);
    CHECK(scd_background_raster_x(0,1600,608,0,scroll.ramp)==801);
    CHECK(scd_background_raster_x(0,1600,752,0,scroll.ramp)==1200);
    scd_background_step(&scroll,0,102,-512,1);CHECK(scroll.ramp==-128);
    CHECK(scd_background_raster_x(0,1600,0,0,scroll.ramp)==199);
    scd_background_reset(&scroll,0);CHECK(!scroll.ramp);
    /* Floating blocks share real terrain with all four era rules. */
    for(unsigned era=0;era<4;era++){
        init(era);scd_player_place(500,96,0,0,2);
        int block=scd_objects_spawn(SCD_OBJ_FLOAT_BLOCK,500,128,0,0);CHECK(block>=0);
        scd_objects_step(500,96);CHECK((qa_player()->flags&10)==8);CHECK(actwk[0].actfree[19]==block+1);
        CHECK(qa_player()->y==97*65536);
        if(era<2){
            for(unsigned n=0;n<30;n++)scd_player_step(0);
            CHECK(view(SCD_OBJ_FLOAT_BLOCK).frame==5);CHECK(qa_player()->y==97*65536);
            CHECK((qa_player()->flags&10)==8);
            scd_player_step(SCD_JUMP);CHECK((qa_player()->flags&10)==2 && qa_player()->vy<0);
            if(!era){for(unsigned n=0;n<30;n++)scd_objects_step(500,97);CHECK(view(SCD_OBJ_FLOAT_BLOCK).frame==0);}
        }else{
            for(unsigned n=0;n<31;n++)scd_player_step(0);
            CHECK(view(SCD_OBJ_FLOAT_BLOCK).y==192);CHECK(qa_player()->y==159*65536);
            actwk[0].xposi.w.h=600;
            for(unsigned n=0;n<100;n++)scd_objects_step(600,159);
            CHECK(!(qa_player()->flags&8));CHECK(!scd_objects_get().active);
        }
    }
    init(1);scd_player_place(500,128,0,0,2);actwk[0].yspeed.w=-256;
    scd_objects_spawn(SCD_OBJ_FLOAT_BLOCK,500,128,0,0);scd_objects_step(500,128);CHECK(!(qa_player()->flags&8));
    /* First landing restores the rolling radius; hurt landings recover. */
    init(1);scd_player_place(500,102,0,0,6);actwk[0].r_no0=4;actwk[0].yspeed.w=256;
    scd_objects_spawn(SCD_OBJ_FLOAT_BLOCK,500,128,0,0);scd_objects_step(500,102);
    CHECK((qa_player()->flags&14)==8 && qa_player()->routine==2 && qa_player()->hurt==120);
    CHECK(actwk[0].sprvsize==19 && qa_player()->y==97*65536);
    scd_objects_clear_live();CHECK(!(qa_player()->flags&8));
    CHECK(scd_objects_spawn(SCD_OBJ_RING,500,128,0,0)==0);scd_objects_validate_rider();CHECK(!actwk[0].actfree[19]);
    /* Walking off and appearance cancellation must not retain an object slot. */
    init(0);scd_player_place(500,96,0,0,2);scd_objects_spawn(SCD_OBJ_FLOAT_BLOCK,500,128,0,0);
    scd_objects_step(500,96);scd_objects_step(500,97);CHECK(view(SCD_OBJ_FLOAT_BLOCK).frame==1);
    actwk[0].xposi.w.h=522;scd_objects_step(500,97);CHECK(!(qa_player()->flags&8));
    scd_objects_step(522,97);CHECK(!view(SCD_OBJ_FLOAT_BLOCK).frame);
    /* Source subtypes: vertical/horizontal/diagonal oscillation, sink, timed
       fall, and one-shot quarter-cycle move. Riders follow without input. */
    for(unsigned mode=0;mode<=3;mode++){
        init(1);scd_player_place(500,228,0,0,2);
        /* The platform initialises on its first update (no SolidObject yet). */
        CHECK(scd_objects_spawn(SCD_OBJ_PLATFORM,500,256,(mode<<4)|5,0)>=0);scd_player_step(0);
        int minx=500,maxx=500,miny=256,maxy=256;
        for(unsigned tick=0;tick<256;tick++){
            scd_player_step(0);scd_object_view o=view(SCD_OBJ_PLATFORM);
            if(o.x<minx)minx=o.x;if(o.x>maxx)maxx=o.x;if(o.y<miny)miny=o.y;if(o.y>maxy)maxy=o.y;
            CHECK((qa_player()->flags&10)==8);CHECK(qa_player()->x/65536==o.x);
            CHECK(qa_player()->y/65536==o.y-27);
        }
        if(mode)CHECK(minx==452 && maxx==548);else CHECK(minx==500 && maxx==500);
        if(mode!=1)CHECK(miny==208 && maxy==304);else CHECK(miny==256 && maxy==260);
        scd_player_step(SCD_JUMP);CHECK(!(qa_player()->flags&8) && qa_player()->vy<0);
    }
    init(1);scd_player_place(500,228,0,0,2);scd_objects_spawn(SCD_OBJ_PLATFORM,500,256,0x40,0);
    for(unsigned n=0;n<16;n++)scd_player_step(0);CHECK(view(SCD_OBJ_PLATFORM).y==260);
    actwk[0].xposi.w.h=600;for(unsigned n=0;n<16;n++)scd_objects_step(600,233);CHECK(view(SCD_OBJ_PLATFORM).y==256 && !(qa_player()->flags&8));
    init(1);scd_player_place(500,228,0,0,2);scd_objects_spawn(SCD_OBJ_PLATFORM,500,256,0x5d,0);
    for(unsigned n=0;n<30;n++)scd_player_step(0);CHECK(view(SCD_OBJ_PLATFORM).y==260);
    for(unsigned n=0;n<30;n++)scd_player_step(0);CHECK(view(SCD_OBJ_PLATFORM).y>330 && qa_player()->flags&8);
    CHECK(actwk[1].yspeed.w==1024);
    scd_objects_clear_live();CHECK(!(qa_player()->flags&8));
    init(1);scd_player_place(500,228,0,0,2);scd_objects_spawn(SCD_OBJ_PLATFORM,500,256,0x6d,0);
    for(unsigned n=0;n<80;n++)scd_player_step(0);CHECK(view(SCD_OBJ_PLATFORM).y==165);
    int stopped=view(SCD_OBJ_PLATFORM).y;for(unsigned n=0;n<60;n++)scd_player_step(0);CHECK(view(SCD_OBJ_PLATFORM).y==stopped);
    CHECK(scd_objects_spawn(SCD_OBJ_PLATFORM,500,256,0x70,0)<0);
    init(3);scd_objects_reset(3,1);scd_player_place(1456,450,0,0,2);scd_player_inventory(5,1);
    for(unsigned n=0;n<200;n++)scd_player_step(0);
    total=scd_objects_views(a,96);
    for(unsigned n=0;n<total;n++)CHECK(!(a[n].type==SCD_OBJ_FLOAT_BLOCK && a[n].x==1456 && a[n].y==524));
    /* The retail Object Spawner streams by the camera window. */
    scd_player_place(2300,96,0,0,2);scd_act_camera(2140,0);scd_objects_step(2300,96);
    scd_player_place(1456,450,0,0,2);scd_act_camera(1296,338);scd_objects_step(1456,450);
    total=scd_objects_views(a,96);unsigned reloaded=0;
    for(unsigned n=0;n<total;n++)if(a[n].type==SCD_OBJ_FLOAT_BLOCK && a[n].x==1456 && a[n].y==524)reloaded++;
    CHECK(reloaded==1);
    /* Checkpoints: original collision boundary, one orbit, monotonic IDs,
       saved clock, clean death reload, cross-era persistence and game over. */
    init(0);scd_player_place(500,96,0,0,2);
    CHECK(scd_objects_spawn(SCD_OBJ_CHECKPOINT,521,96,2,0)>=0);
    scd_objects_step(500,96);CHECK(!scd_player_checkpoint().id);
    actwk[0].xposi.w.h=501;scd_objects_step(501,96);CHECK(scd_player_checkpoint().id==2);
    CHECK(scd_player_checkpoint().x==501 && scd_player_checkpoint().y==96);
    for(unsigned n=0;n<31;n++)scd_objects_step(501,96);
    total=scd_objects_views(a,96);CHECK(total==2 && a[0].frame==0 && a[1].frame==2 && a[1].y==64);
    CHECK(!scd_player_checkpoint_activate(1) && !scd_player_checkpoint_activate(2));
    scd_objects_clear_live();scd_objects_spawn(SCD_OBJ_CHECKPOINT,521,96,2,0);
    total=scd_objects_views(a,96);CHECK(total==2 && a[1].frame==2);
    for(unsigned n=0;n<4;n++)scd_objects_step(501,96);
    total=scd_objects_views(a,96);CHECK(a[1].frame==3);
    init(0);scd_player_place(2760,710,0,0,2);
    for(unsigned n=0;n<90;n++)scd_player_step(0);
    CHECK(scd_player_checkpoint_activate(2));scd_checkpoint saved=scd_player_checkpoint();
    CHECK(saved.elapsed==90);
    for(unsigned n=0;n<30;n++)scd_player_step(0);
    scd_player_inventory(0,0);scd_objects_hurt(2700);
    CHECK(qa_player()->routine==6);unsigned before=qa_player()->frame;
    for(unsigned n=0;n<600 && !qa_player()->resets;n++)scd_player_step(0);
    CHECK(qa_player()->resets==1 && qa_player()->lives==2);
    /* GAME.C game_init on the restart clears clchgtim/clchgcnt: the palette
       clock restarts at 0 while player_frame keeps counting. */
    CHECK(scd_player_level_frames()==0 && qa_player()->frame>before);
    /* Original LoadCheckpointData + first HUD tick drops the saved fraction:
       1:30 ticks (90) becomes exactly one second (60). */
    CHECK(qa_player()->elapsed==60 && qa_player()->frame>before);
    CHECK(qa_player()->x/65536==saved.x && qa_player()->y/65536==saved.y);
    CHECK(scd_objects_get().deaths==1 && !qa_player()->rings && !qa_player()->shield);
    CHECK(qa_player()->hurt==120);
    scd_objects_hurt(qa_player()->x/65536-10);CHECK(qa_player()->routine==2);
    CHECK(!scd_player_arrive(&stages[1],qa_collision[1],9472,1));
    CHECK(scd_player_checkpoint().id==2 && !scd_player_checkpoint_activate(3));
    /* LoadPlayer grants 120 updates of protection after time travel. Test the
       entire countdown without movement/streamed hazards before testing death. */
    scd_objects_reset(1,0);actwk[0].actfree[2]=1;
    scd_player_inventory(0,0);scd_objects_hurt(qa_player()->x/65536-10);
    CHECK(qa_player()->routine==2 && qa_player()->hurt==120);
    for(unsigned n=0;n<119;n++){
        scd_player_step(0);CHECK(qa_player()->hurt==119-n);
        scd_objects_hurt(qa_player()->x/65536-10);CHECK(qa_player()->routine==2);
    }
    scd_player_step(0);CHECK(!qa_player()->hurt);actwk[0].actfree[2]=0;
    scd_objects_hurt(qa_player()->x/65536-10);CHECK(qa_player()->routine==6);
    for(unsigned n=0;n<600 && qa_player()->resets==1;n++)scd_player_step(0);
    CHECK(qa_player()->resets==2 && qa_player()->lives==1);
    CHECK(qa_player()->x/65536==stages[1].start_x && !qa_player()->elapsed);
    CHECK(scd_player_checkpoint().id==2);
    scd_player_inventory(0,0);scd_objects_hurt(0);
    for(unsigned n=0;n<1000;n++)scd_player_step(0);
    CHECK(qa_player()->game_over && !qa_player()->lives && qa_player()->routine==8 && qa_player()->resets==2);
    init(0);CHECK(!scd_player_checkpoint().id && !qa_player()->game_over && qa_player()->lives==3);
    /* A pit with rings still loses a life; the clock never wraps to a replay frame. */
    scd_player_place(500,2041,0,0,2);scd_player_inventory(10,1);scd_player_step(0);
    CHECK(qa_player()->routine==6 && scd_objects_get().deaths==1);
    for(unsigned n=0;n<600 && !qa_player()->resets;n++)scd_player_step(0);
    CHECK(qa_player()->resets==1 && qa_player()->lives==2 && !qa_player()->rings && !qa_player()->shield);
    /* Damage knockback falling out of the map takes the same death path. */
    init(1);scd_player_inventory(1,0);scd_objects_hurt(0);
    actwk[0].yposi.w.h=2045;actwk[0].yspeed.w=1024;scd_player_step(0);
    CHECK(qa_player()->routine==6 && scd_objects_get().deaths==1);
    /* Original placement consumption is cleared on life loss. */
    init(1);scd_objects_reset(1,1);scd_player_place(256,400,0,0,2);scd_objects_step(256,400);
    total=scd_objects_views(a,96);int ringx=-1,ringy=0;
    for(unsigned n=0;n<total;n++)if(a[n].type==SCD_OBJ_RING){ringx=a[n].x;ringy=a[n].y;break;}
    CHECK(ringx>=0);scd_player_place(ringx,ringy,0,0,2);scd_objects_step(ringx,ringy);CHECK(scd_objects_get().collected);
    scd_objects_respawn();scd_player_place(ringx,ringy-80,0,0,2);scd_objects_step(ringx,ringy-80);
    total=scd_objects_views(a,96);unsigned ring_back=0;
    for(unsigned n=0;n<total;n++)if(a[n].type==SCD_OBJ_RING && a[n].x==ringx && a[n].y==ringy)ring_back++;
    CHECK(ring_back==1);
    /* Ring/Main.asm Ani_Ring draws mapping 4,5,6,7 for six updates each.
       Both placed and lost rings keep their actor slot until $FC deletes it. */
    for(unsigned lost=0;lost<2;lost++){
        init(1);CHECK(scd_objects_spawn(lost?SCD_OBJ_LOST_RING:SCD_OBJ_RING,500,400,0,0)==0);
        if(lost){for(unsigned tick=0;tick<63;tick++)scd_objects_step(80,488);
            actwk[1].xposi.w.h=500;actwk[1].yposi.w.h=400;actwk[1].xspeed.w=actwk[1].yspeed.w=0;}
        scd_player_place(500,400,0,0,2);scd_objects_step(500,400);
        CHECK(scd_objects_get().collected==1 && scd_objects_get().active==1);
        CHECK(view(lost?SCD_OBJ_LOST_RING:SCD_OBJ_RING).frame==4);
        scd_player_place(80,488,0,0,2);
        for(unsigned tick=1;tick<24;tick++){
            scd_objects_step(80,488);
            CHECK(scd_objects_get().active==1);
            CHECK(view(lost?SCD_OBJ_LOST_RING:SCD_OBJ_RING).frame==4+tick/6);
        }
        scd_objects_step(80,488);CHECK(!scd_objects_get().active);
    }
    /* Level/Main.asm UpdateGlobalAnims: one ring clock for every placed ring,
       cleared at level start; update L shows ((L+6)/8)&3 (retail R11A,
       tools/test_anim_phase_retail.py). A ring spawned 13 updates later spins
       in phase with the first. */
    init(1);
    for(unsigned u=1;u<=40;u++){
        if(u==1)CHECK(scd_objects_spawn(SCD_OBJ_RING,500,400,0,0)>=0);
        if(u==14)CHECK(scd_objects_spawn(SCD_OBJ_RING,540,400,0,0)>=0);
        scd_objects_step(80,488);
        scd_object_view a[96];unsigned n=scd_objects_views(a,96),rings=0;
        for(unsigned k=0;k<n;k++)if(a[k].type==SCD_OBJ_RING){rings++;CHECK(a[k].frame==((u+6)/8)%4);}
        CHECK(rings==(u<14?1u:2u));
    }
    /* Each spill sets ringLossAnimTimer 255; after the objects, while it runs,
       accum += timer and every lost ring shows accum >> 9 & 3 the next update. */
    init(1);scd_player_inventory(10,0);
    {unsigned timer=0,accum=0,shown=0,seen=0;
    for(unsigned u=1;u<=80;u++){
        if(u==6){scd_objects_hurt(60);timer=255;}
        scd_objects_step(80,488);
        scd_object_view a[96];unsigned n=scd_objects_views(a,96);
        for(unsigned k=0;k<n;k++)if(a[k].type==SCD_OBJ_LOST_RING && a[k].frame<4){seen++;CHECK(a[k].frame==shown);}
        if(timer){accum=(accum+timer)&0xffff;shown=(accum>>9)&3;timer--;}
    }
    CHECK(seen>100);}
    /* Ani_Monitor runs only while the preceding draw left the monitor on
       screen (retail R11A, tools/test_anim_phase_retail.py): mapping 0 until
       the first animated update, then two updates per frame; an off-screen
       monitor holds its phase. */
    {static const uint8_t seq[]={10,1,1,8,1,1,9,1,1};
    init(1);scd_act_camera(0,380);CHECK(scd_objects_spawn(SCD_OBJ_TIMEPOST,200,488,1,0)>=0);CHECK(scd_objects_spawn(SCD_OBJ_TIMEPOST,6000,488,1,0)>=0);
    for(unsigned u=1;u<=40;u++){
        scd_objects_step(80,488);
        scd_object_view a[96];unsigned n=scd_objects_views(a,96),near=0,far=0;
        for(unsigned k=0;k<n;k++)if(a[k].type==SCD_OBJ_TIMEPOST){
            if(a[k].x==200){near++;CHECK(a[k].frame==(u==1?0:seq[((u-2)/2)%9]));}
            else if(a[k].x==6000){far++;CHECK(a[k].frame==0);}
        }
        CHECK(near==1 && far<=1);
    }}
    /* Stationary source solidity: standing, side blocking, underside,
       releasing a rider/push reference, and attack-only wall destruction. */
    init(1);scd_player_place(500,211,0,0,2);scd_objects_spawn(SCD_OBJ_WALL,500,256,1,0);
    scd_objects_step(500,211);CHECK(scd_objects_standing_type()==SCD_OBJ_WALL && qa_player()->y/65536==213);
    scd_player_step(SCD_JUMP);CHECK(!(qa_player()->flags&8));
    init(1);scd_player_place(480,256,0,0,0);scd_objects_spawn(SCD_OBJ_WALL,500,256,1,0);actwk[0].xspeed.w=512;
    scd_objects_step(480,256);CHECK(!scd_objects_get().broken && qa_player()->x/65536==474 && !qa_player()->vx && qa_player()->flags&32);
    scd_objects_clear_live();CHECK(!(qa_player()->flags&32));
    init(1);scd_player_place(500,290,0,0,2);actwk[0].yspeed.w=-512;scd_objects_spawn(SCD_OBJ_WALL,500,256,1,0);
    scd_objects_step(500,290);CHECK(qa_player()->y/65536==301 && !qa_player()->vy && !scd_objects_get().broken);
    static const uint8_t wall_frames[8][6]={{8,9,8,12,13,12},{8,9,8,10,11,10},{10,11,10,10,11,10},{10,11,10,12,13,12},{9,8,9,13,12,13},{9,8,9,11,10,11},{11,10,11,11,10,11},{11,10,11,13,12,13}};
    for(unsigned sub=0;sub<8;sub++)for(unsigned facing=0;facing<2;facing++){
        init(1);scd_player_place(500,256,0,0,6);actwk[0].mstno.b.h=2;actwk[0].xspeed.w=facing?-1537:1537;
        CHECK(scd_objects_spawn(SCD_OBJ_WALL,500,256,sub,0)>=0);scd_objects_step(500,256);
        CHECK(scd_objects_get().broken==1 && scd_objects_get().debris==6 && scd_objects_get().active==6);
        CHECK(qa_player()->vx==(facing?-769:768));
        total=scd_objects_views(a,96);CHECK(total==6);
        for(unsigned n=0;n<6;n++)CHECK(a[n].frame==wall_frames[sub][n]);
        CHECK(a[0].x==(facing?494:489) && a[0].y==238);
        CHECK(a[1].x==(facing?495:488) && a[1].y==256);
        CHECK(a[5].x==(facing?510:505) && a[5].y==273);
        for(unsigned n=0;n<100;n++)scd_objects_step(500,256);
        CHECK(!scd_objects_get().debris && !scd_objects_get().active && scd_objects_get().broken==1);
    }
    init(1);scd_player_place(500,256,0,0,6);actwk[0].mstno.b.h=2;actwk[0].xspeed.w=1024;
    scd_objects_spawn(SCD_OBJ_WALL,500,256,0,0);
    for(unsigned n=1;n<96;n++)CHECK(scd_objects_spawn(SCD_OBJ_RING,2000+n,1000,0,0)>=0);
    scd_objects_step(500,256);CHECK(scd_objects_get().broken==1 && scd_objects_get().debris==1 && scd_objects_get().active==96 && qa_player()->vx==512);
    CHECK(scd_objects_spawn(SCD_OBJ_WALL,500,256,8,0)<0);
    /* Upright spikes block sides safely; the top stays solid during protection
       and hurts once protection expires. Inverted $83 contact is independent. */
    init(1);scd_player_place(480,256,0,0,0);actwk[0].xspeed.w=512;scd_objects_spawn(SCD_OBJ_SPIKES,500,256,0,0);
    scd_objects_step(480,256);CHECK(qa_player()->x/65536==474 && !scd_objects_get().hits && !qa_player()->vx);
    init(1);scd_player_place(500,227,0,0,2);scd_objects_spawn(SCD_OBJ_SPIKES,500,256,0,0);
    scd_objects_travel_protection(1);scd_objects_step(500,227);
    CHECK(scd_objects_standing_type()==SCD_OBJ_SPIKES && qa_player()->y/65536==229 && !scd_objects_get().hits);
    scd_objects_travel_protection(0);scd_objects_step(500,229);CHECK(scd_objects_get().deaths==1 && qa_player()->routine==6);
    init(1);scd_player_place(500,227,0,0,2);scd_objects_spawn(SCD_OBJ_SPIKES,500,256,0,0);plpower_m=1;
    scd_objects_step(500,227);CHECK(scd_objects_standing_type()==SCD_OBJ_SPIKES && !scd_objects_get().hits);
    plpower_m=0;scd_word_set(&actwk[0],26,2);scd_objects_step(500,229);CHECK(!scd_objects_get().hits);
    scd_word_set(&actwk[0],26,0);scd_objects_step(500,229);CHECK(scd_objects_get().deaths==1);
    init(1);scd_player_place(500,285,0,0,2);actwk[0].yspeed.w=-512;scd_objects_spawn(SCD_OBJ_SPIKES,500,256,0,2);
    scd_objects_step(500,285);CHECK(scd_objects_get().deaths==1);
    init(1);scd_player_place(500,227,0,0,2);scd_objects_spawn(SCD_OBJ_SPIKES,500,256,0,2);scd_objects_travel_protection(1);
    scd_objects_step(500,227);CHECK(scd_objects_standing_type()==SCD_OBJ_SPIKES && !scd_objects_get().hits);
    /* Goal/signpost boundaries and source finish/tally sequencing. */
    init(0);scd_act_camera(9800,350);scd_player_place(9983,480,0,0,2);
    CHECK(!scd_act_goal(9984,480));actwk[0].xposi.w.h=9984;actwk[0].yposi.w.h=608;
    CHECK(!scd_act_goal(9984,480));actwk[0].yposi.w.h=352;
    CHECK(scd_act_goal(9984,480) && scd_act_get().left==9800);
    scd_world_reset(0);scd_world_activate(1);CHECK(!scd_world_get().direction);
    actwk[0].xposi.w.h=9700;scd_player_step(0);CHECK(qa_player()->x/65536==9816);
    init(0);scd_act_camera(10391,350);scd_player_place(10552,496,0,0,2);scd_player_inventory(23,1);
    CHECK(!scd_act_sign(10552,496,0));actwk[0].xposi.w.h=10553;plpower_m=plpower_s=1;
    CHECK(scd_act_sign(10552,496,0));CHECK(!plpower_m && !plpower_s && scd_act_get().timer==120);
    scd_player_state finish_player=scd_player_get();
    for(unsigned n=0;n<119;n++)scd_act_step(finish_player);
    CHECK(scd_act_get().phase==SCD_ACT_SPIN && scd_act_get().timer==1);
    scd_act_step(finish_player);CHECK(scd_act_get().phase==SCD_ACT_DELAY && scd_act_get().timer==60 && scd_act_sign_frame()==3);
    for(unsigned n=0;n<60;n++)scd_act_step(finish_player);
    CHECK(scd_act_get().phase==SCD_ACT_EXIT && scd_act_get().timer==16 && scd_act_music() && !scd_act_music());
    CHECK(scd_act_get().time_bonus==50000 && scd_act_get().ring_bonus==2300 && scd_act_get().total_bonus==52300);
    for(unsigned n=0;n<20;n++)scd_act_step(finish_player);
    CHECK(scd_act_get().phase==SCD_ACT_EXIT);
    finish_player.x=10727*65536;scd_act_step(finish_player);CHECK(scd_act_get().phase==SCD_ACT_EXIT);
    finish_player.x=10728*65536;scd_act_step(finish_player);CHECK(scd_act_get().phase==SCD_ACT_SLIDE && scd_act_get().timer==480);
    for(unsigned n=0;n<36;n++)scd_act_step(finish_player);
    CHECK(scd_act_get().phase==SCD_ACT_SLIDE && scd_act_get().slide==36 && scd_act_get().timer==444);
    scd_act_step(finish_player);CHECK(scd_act_get().phase==SCD_ACT_TALLY);
    scd_act_step(finish_player);CHECK(qa_player()->score==200 && scd_act_get().time_bonus==49900 && scd_act_get().ring_bonus==2200);
    for(unsigned n=0;n<499;n++)scd_act_step(finish_player);
    CHECK(!scd_act_get().time_bonus && !scd_act_get().ring_bonus && qa_player()->score==52300 && qa_player()->lives==4 && scd_act_get().timer==45);
    for(unsigned n=0;n<45;n++)scd_act_step(finish_player);CHECK(scd_act_get().phase==SCD_ACT_TALLY);
    scd_act_step(finish_player);CHECK(scd_act_get().phase==SCD_ACT_DONE);
    for(unsigned n=0;n<10;n++)scd_act_step(finish_player);CHECK(qa_player()->score==52300 && qa_player()->lives==4);
    CHECK(scd_act_time_bonus(1799)==50000 && scd_act_time_bonus(1800)==10000 && scd_act_time_bonus(17999)==500 && !scd_act_time_bonus(18000));
    init(0);scd_player_place(10553,496,0,0,2);scd_act_camera(10391,350);scd_player_inventory(999,0);
    CHECK(scd_act_sign(10552,496,1));
    unsigned elapsed_before=qa_player()->elapsed;
    for(unsigned n=0;n<180;n++)scd_player_step(0);
    CHECK(scd_act_get().good_future && scd_act_get().ring_bonus==99900 && qa_player()->elapsed==elapsed_before);
    init(0);scd_player_points(50000);CHECK(qa_player()->score==50000 && qa_player()->lives==4);
    CHECK(!scd_player_arrive(&stages[1],qa_collision[1],9472,1));
    scd_player_points(1);CHECK(qa_player()->lives==4);scd_player_points(49999);CHECK(qa_player()->lives==5);
    init(0);CHECK(!scd_act_get().phase && !qa_player()->score && qa_player()->lives==3);
    scd_player_step(0);CHECK(qa_player()->elapsed==1);
    CHECK(!qa_error);return 0;
}
static int __attribute__((noinline)) monitor_probe(void){
    /* Source monitor collision, delayed item grant, static shell, ring lives,
       and USA power-up timers. No item is granted when the original pool
       allocation fails. */
    for(unsigned kind=0;kind<5;kind++){
        init(1);scd_player_place(500,488,0,0,6);actwk[0].mstno.b.h=2;actwk[0].yspeed.w=512;
        CHECK(scd_objects_spawn(SCD_OBJ_TIMEPOST,500,510,kind,0)>=0);
        scd_objects_step(500,484);CHECK(view(SCD_OBJ_TIMEPOST).frame==11 && actwk[0].yspeed.w==-512);
        CHECK(qa_player()->rings==0 && qa_player()->lives==3 && !qa_player()->shield && !plpower_m && !plpower_s);
        for(unsigned n=0;n<31;n++)scd_objects_step(500,488);
        CHECK(qa_player()->rings==0 && qa_player()->lives==3 && !qa_player()->shield && !plpower_m && !plpower_s);
        scd_objects_step(500,488);
        CHECK(qa_player()->lives==(kind==0?4:3));CHECK(qa_player()->rings==(kind==1?10:0));
        CHECK(qa_player()->shield==(kind==2));CHECK(!!plpower_m==(kind==3));CHECK(!!plpower_s==(kind==4));
        unsigned lives=qa_player()->lives,rings=qa_player()->rings;
        for(unsigned n=0;n<40;n++)scd_objects_step(500,488);
        CHECK(scd_objects_get().active==1 && qa_player()->lives==lives && qa_player()->rings==rings);
    }
    init(1);scd_player_place(477,488,256,0,0);CHECK(scd_objects_spawn(SCD_OBJ_TIMEPOST,500,488,1,0)>=0);
    /* SolidObject width $F+10 (Monitor and Time Post/Main.asm:113): pushed to 500-25. */
    scd_objects_step(476,488);CHECK(qa_player()->x/65536==475 && !qa_player()->vx && view(SCD_OBJ_TIMEPOST).frame!=11);
    init(1);scd_player_place(500,512,0,0,6);actwk[0].mstno.b.h=2;actwk[0].yspeed.w=-512;
    int mon=scd_objects_spawn(SCD_OBJ_TIMEPOST,500,488,1,0);CHECK(mon>=0);scd_objects_step(500,516);
    /* Sonic touches in slot 0 before the monitor updates, so its -$180 bounce
       already carries one $38 gravity step. */
    CHECK(actwk[0].yspeed.w==512 && actwk[mon+1].yspeed.w==-384+56 && view(SCD_OBJ_TIMEPOST).frame!=11);
    scd_objects_step(500,512);CHECK(actwk[mon+1].yposi.w.h<488);
    init(1);scd_player_place(500,488,0,0,6);actwk[0].mstno.b.h=2;actwk[0].yspeed.w=512;
    CHECK(scd_objects_spawn(SCD_OBJ_TIMEPOST,500,510,0,0)>=0);
    for(unsigned n=1;n<SCD_OBJECT_CAPACITY;n++)CHECK(scd_objects_spawn(SCD_OBJ_BOULDER,800,1800,0,0)>=0);
    scd_objects_step(500,484);CHECK(view(SCD_OBJ_TIMEPOST).frame==11 && scd_objects_get().dropped==2 && qa_player()->lives==3);
    init(1);scd_player_inventory(99,0);scd_player_rings(1);CHECK(qa_player()->lives==4 && qa_player()->rings==100);
    scd_player_rings(99);CHECK(qa_player()->lives==4);scd_player_rings(1);CHECK(qa_player()->lives==5);
    scd_player_rings(10);CHECK(qa_player()->lives==5);
    CHECK(!scd_player_arrive(&stages[0],qa_collision[0],9472,0));scd_player_rings(1);CHECK(qa_player()->lives==5);
    scd_player_rings_lost();scd_player_inventory(99,0);scd_player_rings(1);CHECK(qa_player()->lives==6);
    init(1);scd_player_powerup(3);CHECK(scd_player_powerups().invincible==1320 && scd_player_music_event()==6);
    scd_objects_hurt(100);CHECK(!scd_objects_get().hits);
    for(unsigned n=0;n<1319;n++)scd_player_step(0);
    CHECK(plpower_m && scd_player_powerups().invincible==1);scd_player_step(0);CHECK(!plpower_m && scd_player_music_event()==0);
    init(1);scd_player_powerup(4);CHECK(plmaxspdwk==3072 && pladdspdwk==24 && scd_player_music_event()==5);
    for(unsigned n=0;n<1319;n++)scd_player_step(0);
    CHECK(plpower_s && scd_player_powerups().shoes==1);scd_player_step(0);CHECK(!plpower_s && plmaxspdwk==1536 && pladdspdwk==12 && scd_player_music_event()==0);
    init(1);scd_player_powerup(3);for(unsigned n=0;n<100;n++)scd_player_step(0);scd_player_powerup(4);scd_player_music_event();
    for(unsigned n=0;n<1220;n++)scd_player_step(0);CHECK(!plpower_m && plpower_s && scd_player_music_event()==-1);
    for(unsigned n=0;n<100;n++)scd_player_step(0);CHECK(!plpower_s && scd_player_music_event()==0);
    init(1);scd_player_powerup(3);scd_player_powerup(4);scd_player_finish();CHECK(!plpower_m && !plpower_s && !scd_player_powerups().invincible && !scd_player_powerups().shoes);
    init(1);scd_player_powerup(3);scd_player_powerup(4);CHECK(!scd_player_arrive(&stages[0],qa_collision[0],9472,0));CHECK(!plpower_m && !plpower_s);
    init(1);scd_player_place(500,488,0,0,2);CHECK(scd_objects_spawn(SCD_OBJ_TIMEPOST,500,488,8,0)>=0);
    scd_objects_step(500,488);CHECK(scd_objects_timepost()==-1);unsigned spin_frames=0;
    for(unsigned n=0;n<60;n++){scd_objects_step(500,488);spin_frames|=1u<<view(SCD_OBJ_TIMEPOST).frame;}
    CHECK((spin_frames&0x33)==0x33 && view(SCD_OBJ_TIMEPOST).frame==1 && !scd_objects_timepost());
    /* Level End ObjBigRing: hidden and untouchable below 50 rings; a touch moves Sonic to the view
       X + 336, stops him, sets specialStage once and spawns the flash, which deletes itself after
       its eight frames; with time stone 1 held the ring deletes itself. */
    scd_object_view rings[96];
    init(0);scd_player_inventory(49,0);scd_player_place(500,488,0,0,2);CHECK(scd_objects_spawn(SCD_OBJ_BIG_RING,500,488,0,0)>=0);
    scd_objects_step(500,488);CHECK(!scd_objects_big_ring_touched() && !scd_objects_views(rings,96));
    init(0);scd_player_inventory(50,0);scd_player_place(560,488,0,0,2);CHECK(scd_objects_spawn(SCD_OBJ_BIG_RING,500,488,0,0)>=0);
    scd_objects_step(560,488);CHECK(!scd_objects_big_ring_touched() && scd_objects_views(rings,96)==1 && rings[0].type==SCD_OBJ_BIG_RING);
    scd_player_place(500,488,512,0,2);actwk[0].xspeed.w=512;scd_objects_step(500,488);
    CHECK(scd_objects_big_ring_touched() && scd_objects_big_ring() && !scd_objects_big_ring());
    CHECK(qa_player()->x/65536==336 && !qa_player()->vx && !qa_player()->speed);
    CHECK(scd_objects_views(rings,96)==1 && rings[0].subtype==1);
    for(unsigned n=0;n<30;n++)scd_objects_step(336,488);
    CHECK(!scd_objects_views(rings,96) && scd_objects_get().active==1);
    /* Level End/Main.asm:352-360: only all seven stones (%1111111) delete the
       ring; stone 1 alone (any partial set) keeps it for the next stage. */
    scd_objects_time_stones(1);init(0);scd_player_inventory(50,0);CHECK(scd_objects_spawn(SCD_OBJ_BIG_RING,500,488,0,0)>=0);
    scd_objects_step(80,488);CHECK(scd_objects_get().active==1);
    scd_objects_time_stones(0x7f);init(0);scd_player_inventory(50,0);CHECK(scd_objects_spawn(SCD_OBJ_BIG_RING,500,488,0,0)>=0);
    scd_objects_step(80,488);CHECK(!scd_objects_get().active);scd_objects_time_stones(0);
    CHECK(!qa_error);return 0;
}
static unsigned collapse_sounds;
static void collapse_sound(short request){if(request==163)collapse_sounds++;}
static int __attribute__((noinline)) collapse_probe(void){
    scd_player_audio_set(collapse_sound);
    /* Collapsing platforms: independently transcribed source dimensions,
       frame groups and timing. No player integration during piece checks. */
    for(unsigned era=0;era<4;era++)for(unsigned variant=0;variant<8;variant++){
        static const unsigned subs[]={0,16,17,192,224,193,194,197};unsigned sub=subs[variant];
        if((sub==17 || sub==194 || sub==197) && era!=1)continue;
        init(era);collapse_sounds=0;int radius=(sub&128)?(sub==194 || sub==197?34:18):(sub==17?26:34);
        CHECK(scd_objects_spawn(SCD_OBJ_COLLAPSE,500,400,sub,0)==0);
        CHECK(actwk[1].sprvsize==radius);
        scd_player_place(500,400-radius-19,256,0,2);actwk[0].xspeed.w=256;
        scd_objects_step(500,400-radius-19);
        unsigned expected=sub==17?12:!(sub&128)?18:sub==197?10:sub==194?9:6;
        CHECK(scd_objects_get().collapsed==1 && scd_objects_get().collapse_pieces==expected && collapse_sounds==1);
        CHECK(scd_objects_get().active==expected && !actwk[1].actno);
        scd_object_view pieces[96];CHECK(scd_objects_views(pieces,96)==expected);
        unsigned base=era==0?190:era==1?211:228;
        if(!(sub&128)){
            CHECK(pieces[0].y==(sub==17?416:424));
            CHECK(pieces[0].x==(sub==17?524:500));
            CHECK(pieces[0].frame==base+(sub==17?1:0));
            CHECK(pieces[expected-1].y==(sub==17?384:376));
            CHECK(pieces[expected-1].x==((sub&16)?(sub==17?476:468):532));
            CHECK(pieces[expected-1].frame==base+6);
            CHECK(pieces[0].flags==!!(sub&16));
        }else{
            int left=sub==197?428:sub==194?436:460,right=sub==197?572:sub==194?564:540;
            CHECK(pieces[0].x==(sub==224?right:left) && pieces[expected-1].x==(sub==224?left:right));
            CHECK(pieces[0].y==400 && !pieces[0].flags);
            if(sub==194 || sub==197)CHECK(pieces[0].frame==219 && pieces[expected-1].frame==220);
        }
        /* A distant player cannot keep delayed pieces standing. All pieces
           eventually exceed the source's player-relative +512 deletion line. */
        scd_player_place(80,200,0,0,2);
        for(unsigned tick=0;tick<250;tick++)scd_objects_step(80,200);
        CHECK(!scd_objects_get().active && !scd_objects_standing_type() && collapse_sounds==1);
    }
    /* Every occupied multi-row cell retains its original delay and exact
       16.16 integration, including the two skipped bottom cells. */
    for(unsigned flip=0;flip<2;flip++){
        static const uint8_t columns[]={2,3,4,0,1,2,3,4,0,1,2,3,4,0,1,2,3,4};
        static const uint8_t rows[]={0,0,0,1,1,1,1,1,2,2,2,2,2,3,3,3,3,3};
        init(0);scd_player_place(500,347,0,0,2);CHECK(scd_objects_spawn(SCD_OBJ_COLLAPSE,500,400,flip?16:0,0)==0);scd_objects_step(500,347);
        scd_player_place(80,1000,0,0,2);
        for(unsigned tick=0;tick<=60;tick++){
            if(tick)scd_objects_step(80,1000);
            for(unsigned piece=0;piece<18;piece++){
                int delay=9+columns[piece]*12+rows[piece]*5;
                int falls=(int)tick-delay+1;if(falls<0)falls=0;
                int32_t expected=(424-rows[piece]*16)*65536+falls*0x20000+falls*(falls-1)/2*0x4000;
                CHECK(actwk[piece+2].yposi.l==expected);
                CHECK(actwk[piece+2].xposi.w.h==500+(flip?-1:1)*(-32+columns[piece]*16));
            }
        }
    }
    /* Source single-row starts at nine ticks, adds twelve per column,
       and integrates 2.0 then 2.25 pixels/tick after the delay. */
    init(0);scd_player_place(460,363,0,0,2);CHECK(scd_objects_spawn(SCD_OBJ_COLLAPSE,500,400,192,0)==0);
    /* The first update initialises the platform; Sonic lands on the next. */
    scd_objects_step(460,363);scd_objects_step(460,363);CHECK(scd_objects_standing_type()==SCD_OBJ_COLLAPSE);
    for(unsigned n=0;n<6;n++)scd_objects_step(460,363); /* the delay counts from the spawn update */
    CHECK(scd_objects_standing_type()==SCD_OBJ_COLLAPSE && actwk[2].yposi.l==400*65536);
    scd_objects_step(460,363);CHECK(!scd_objects_standing_type() && (actwk[0].cddat&2));
    scd_objects_step(460,363);CHECK(actwk[2].yposi.l==402*65536);
    scd_objects_step(460,363);CHECK(actwk[2].yposi.l==404*65536+16384);
    CHECK(actwk[3].yposi.l==400*65536);
    /* Both speed signs and bit-5 reversal choose the falling end. */
    for(unsigned sub=128;sub<=224;sub+=32)for(int speed=-256;speed<=256;speed+=256){
        init(0);CHECK(scd_objects_spawn(SCD_OBJ_COLLAPSE,500,400,sub,0)==0);scd_player_place(500,363,speed,0,2);actwk[0].xspeed.w=speed;scd_objects_step(500,363);
        int reverse=(sub&64)?((sub&32)?-speed:speed)<0:!!(sub&32);
        CHECK(view(SCD_OBJ_COLLAPSE).x==(reverse?540:460));
    }
    /* A newly allocated slot before the parent in the scheduler starts its
       delay next tick; slots after the parent start during the breakup tick. */
    init(0);CHECK(scd_objects_spawn(SCD_OBJ_EXPLOSION,80,200,0,0)==0);CHECK(scd_objects_spawn(SCD_OBJ_COLLAPSE,500,400,192,0)==1);
    for(unsigned n=0;n<21;n++)scd_objects_step(80,488);
    CHECK(!actwk[1].actno);scd_player_place(500,363,0,0,2);scd_objects_step(500,363);CHECK(actwk[1].actno==32 && !actwk[2].actno);
    scd_player_place(80,1000,0,0,2);
    for(unsigned n=0;n<9;n++)scd_objects_step(80,1000);
    CHECK(actwk[1].yposi.l==400*65536);scd_objects_step(80,1000);CHECK(actwk[1].yposi.l==402*65536);
    /* Full/partial pool never retains the parent or creates extra pieces. */
    for(unsigned spaces=0;spaces<3;spaces++){
        init(0);scd_player_place(500,363,0,0,2);CHECK(scd_objects_spawn(SCD_OBJ_COLLAPSE,500,400,192,0)==0);
        for(unsigned n=1;n<96-spaces;n++)CHECK(scd_objects_spawn(SCD_OBJ_BOULDER,80,400,0,0)>=0);
        scd_objects_step(500,363);CHECK(scd_objects_get().collapsed==1 && scd_objects_get().collapse_pieces==spaces && scd_objects_get().dropped==1);
        CHECK(!actwk[1].actno && !scd_objects_standing_type());
    }
    /* Upward passage cannot trigger collapse; clearing/reusing a slot must
       not leave Sonic attached to an unrelated actor. */
    init(0);scd_player_place(500,363,0,0,2);actwk[0].yspeed.w=-256;CHECK(scd_objects_spawn(SCD_OBJ_COLLAPSE,500,400,192,0)==0);scd_objects_step(500,363);
    CHECK(!scd_objects_get().collapsed && scd_objects_get().active==1);
    scd_player_place(460,363,0,0,2);scd_objects_step(460,363);scd_objects_step(460,363);CHECK(scd_objects_standing_type()==SCD_OBJ_COLLAPSE); /* lands on the second update */
    scd_objects_clear_live();CHECK(!scd_objects_standing_type());CHECK(scd_objects_spawn(SCD_OBJ_BOULDER,80,400,0,0)==0);
    CHECK(!scd_objects_standing_type());
    CHECK(!qa_error);return 0;
}

static unsigned tunnel_sounds;
static void tunnel_sound(short request){if(request==145)tunnel_sounds++;}
static uint32_t tunnel_trace(uint32_t hash){
    sprite_status *p=&actwk[0];uint32_t words[]={(uint32_t)p->xposi.l,(uint32_t)p->yposi.l,(uint16_t)p->xspeed.w,(uint16_t)p->yspeed.w,p->actfree[2]};
    for(unsigned i=0;i<5;i++){hash^=words[i];hash*=16777619u;}return hash;
}
static int __attribute__((noinline)) tunnel_probe(void){
    static const int starts[3][2]={{5104,240},{3848,416},{5680,656}};
    static const int ends[3][2]={{5888,752},{4400,456},{6096,616}};
    /* Frozen segment-expansion reference fingerprints: original points,
       rational slopes truncated toward zero, five words per emitted tick. */
    static const uint32_t expected[]={1713986740u,1982024553u,2692119162u};
    static const unsigned duration[]={178,87,91};
    scd_player_audio_set(tunnel_sound);
    for(unsigned path=0;path<3;path++)for(unsigned high=0;high<2;high++){
        init(path==0?0:2);tunnel_sounds=0;
        CHECK(scd_objects_spawn(SCD_OBJ_TUNNEL,starts[path][0],starts[path][1],path+high*128,0)==0);
        actwk[1].userflag.b.l=path==0;
        scd_player_place(starts[path][0],starts[path][1],0,0,2);
        actwk[0].xposi.l+=0x1234;actwk[0].yposi.l+=0x5678;
        scd_objects_step(starts[path][0],starts[path][1]);
        CHECK(qa_player()->control==(path==0?193:129) && tunnel_sounds==1);
        uint32_t hash=tunnel_trace(2166136261u);unsigned ticks=1;
        /* Input cannot perturb path movement; clocks and powers keep ticking. */
        scd_player_powerup(3);
        while(qa_player()->control && ticks<1000){
            scd_player_step((ticks&1)?SCD_LEFT|SCD_DOWN|SCD_JUMP:SCD_RIGHT|SCD_UP);
            hash=tunnel_trace(hash);ticks++;
        }
        CHECK(ticks==duration[path] && hash==expected[path]);
        CHECK(qa_player()->x/65536==ends[path][0] && qa_player()->y/65536==ends[path][1]);
        CHECK(qa_player()->elapsed==ticks-1 && scd_player_powerups().invincible==1320-(ticks-1));
        CHECK(!qa_player()->control && tunnel_sounds==2 && !qa_player()->resets);
        scd_object_view views[1];CHECK(!scd_objects_views(views,1));
    }
    /* Half-open entry bounds, existing ownership and hurt recovery. */
    for(int axis=0;axis<2;axis++)for(int d=-17;d<=16;d++){
        init(2);CHECK(scd_objects_spawn(SCD_OBJ_TUNNEL,3848,416,1,0)==0);
        scd_player_place(3848+(axis?0:d),416+(axis?d:0),0,0,2);scd_objects_step(3848,416);
        CHECK(!!qa_player()->control==(d>=-16 && d<16));
    }
    for(unsigned control=1;control<=128;control*=2){
        init(2);scd_objects_spawn(SCD_OBJ_TUNNEL,3848,416,1,0);scd_player_place(3848,416,0,0,2);actwk[0].actfree[2]=control;
        scd_objects_step(3848,416);CHECK(qa_player()->control==control && !actwk[0].mspeed.w);
    }
    init(2);scd_objects_spawn(SCD_OBJ_TUNNEL,3848,416,1,0);scd_player_place(3848,416,0,0,2);actwk[0].r_no0=4;
    scd_objects_step(3848,416);CHECK(qa_player()->routine==2 && qa_player()->hurt==120 && qa_player()->control==129);
    scd_player_step(0);CHECK(qa_player()->hurt==119);
    /* Path1's initial point equals the entrance: calculate zero duration,
       then snap/advance on the next tick without vertical integration. */
    CHECK(qa_player()->vy==4096 && qa_player()->x/65536==3848 && qa_player()->y/65536==416);
    scd_player_step(0);CHECK(qa_player()->vx==4096 && qa_player()->vy==0 && qa_player()->y/65536==416);
    for(unsigned operation=0;operation<6;operation++){
        init(0);scd_objects_spawn(SCD_OBJ_TUNNEL,5104,240,0,0);actwk[1].userflag.b.l=1;
        scd_player_place(5104,240,0,0,2);scd_objects_step(5104,240);CHECK(qa_player()->control==193);
        if(operation==0)scd_objects_clear_live();
        else if(operation==1)scd_objects_reset(1,0);
        else if(operation==2)scd_objects_change_era(1);
        else if(operation==3){actwk[0].r_no0=6;scd_objects_step(5104,240);}
        else if(operation==4)scd_player_place(80,100,0,0,2);
        else scd_objects_death_record();
        CHECK(!qa_player()->control);
    }
    /* SaveTimeWarpData stores position/velocity/flags, not object control.
       Arrival must not restore a lock from the discarded object pool. */
    for(unsigned era=0;era<4;era++){
        init(era);scd_objects_spawn(SCD_OBJ_TUNNEL,3000,64,0,0);actwk[1].userflag.b.l=1;
        scd_player_place(3000,64,0,0,2);scd_objects_step(3000,64);CHECK(qa_player()->control==193);
        unsigned destination=(era+1)&3;
        CHECK(!scd_player_arrive(&stages[destination],qa_collision[destination],9472,destination));
        CHECK(!qa_player()->control && scd_player_arrival_clear());
        int32_t y=qa_player()->y;scd_player_step(0);scd_player_step(0);
        CHECK(qa_player()->y!=y && !qa_player()->control);
    }
    /* Invisible SolidObject exclusion and high-bit contact suppression. */
    init(0);scd_objects_spawn(SCD_OBJ_TUNNEL,5104,240,0,0);actwk[1].userflag.b.l=1;
    scd_player_place(5104,240,0,0,2);scd_objects_step(5104,240);
    scd_objects_spawn(SCD_OBJ_RING,5104,240,0,0);scd_objects_spawn(SCD_OBJ_SPIKES,5104,260,0,0);
    scd_objects_hurt(5100);scd_player_step(0);
    CHECK(!qa_player()->rings && qa_player()->routine==2 && qa_player()->x/65536==5104 && qa_player()->y/65536==240);
    CHECK(scd_objects_spawn(SCD_OBJ_TUNNEL,500,400,3,0)<0);
    CHECK(!qa_error);return 0;
}

static unsigned disc_sounds;
static void disc_sound(short request){if(request==160)disc_sounds++;}
static int __attribute__((noinline)) disc_probe(void){
    scd_player_audio_set(disc_sound);
    /* Frozen source cosine positions, starting 16 pixels right of center.
       Every eight updates grows the radius, after that tick's X is chosen. */
    static const int8_t x_offsets[32]={15,14,13,11,8,6,3,0,-4,-7,-10,-13,-15,-16,-17,-17,-18,-17,-15,-13,-10,-7,-4,0,3,7,10,13,15,17,18,19};
    static const uint8_t poses[16]={0,0,0,1,1,2,2,2,3,3,3,4,4,5,5,5};
    for(unsigned facing=0;facing<2;facing++){
        init(0);swdata.w=0;disc_sounds=0;CHECK(scd_objects_spawn(SCD_OBJ_DISC,500,400,0,0)==0);
        scd_player_place(516,373,0,0,2|facing);actwk[0].xposi.l+=0x4567;actwk[0].yposi.l+=0x1234;
        for(unsigned n=0;n<32;n++){
            if(!n)scd_objects_step(516,373);else scd_player_step(0);
            scd_player_state p=scd_player_get();unsigned angle=((n+1)*8)&255;
            CHECK(p.control==1 && p.animation==45 && scd_objects_standing_type()==SCD_OBJ_DISC);
            CHECK(p.x==(500+x_offsets[n])*65536+0x4567 && p.y==373*65536+0x1234);
            CHECK(p.disc_angle==angle && p.disc_radius==16+(n+1)/8 && p.disc_frame==poses[angle>>4]);
            CHECK((p.flags&1)==facing && p.vy==0 && !disc_sounds);
            CHECK(view(SCD_OBJ_DISC).frame==(n/2)%3);
        }
    }
    /* Entry from the left begins at angle 128 and keeps fraction bits. */
    init(0);swdata.w=0;scd_objects_spawn(SCD_OBJ_DISC,500,400,0,0);scd_player_place(484,373,0,0,2);
    scd_objects_step(484,373);CHECK(qa_player()->disc_angle==136 && qa_player()->x/65536==484 && qa_player()->disc_radius==16);
    /* Centerward input clamps radius at zero; outward input wins when both
       directions are held, and radius arithmetic wraps as a source byte. */
    for(unsigned side=0;side<2;side++)for(unsigned input=0;input<4;input++){
        init(0);swdata.w=0;scd_objects_spawn(SCD_OBJ_DISC,500,400,0,0);scd_player_place(side?484:516,373,0,0,2);
        scd_objects_step(500,373);unsigned buttons=(input&1?SCD_LEFT:0)|(input&2?SCD_RIGHT:0);
        scd_player_step(buttons);
        unsigned outward=side?SCD_LEFT:SCD_RIGHT,inward=side?SCD_RIGHT:SCD_LEFT;
        unsigned expected=16+(!!(buttons&outward)?1:(buttons&inward)?-1:0);
        CHECK(qa_player()->disc_radius==expected);
    }
    init(0);swdata.w=0;scd_objects_spawn(SCD_OBJ_DISC,500,400,0,0);scd_player_place(500,373,0,0,2);scd_objects_step(500,373);
    scd_player_step(SCD_LEFT);CHECK(!qa_player()->disc_radius);
    actwk[0].actfree[15]=255;actwk[0].actfree[1]=56;scd_objects_step(500,373);CHECK(!qa_player()->disc_radius);
    /* Jump uses floor angle, not rotation angle. Existing support is cleared
       by the next frame's standard airborne rider validation. */
    for(unsigned angle=0;angle<256;angle+=64)for(unsigned water=0;water<2;water++){
        init(0);swdata.w=0;disc_sounds=0;scd_objects_spawn(SCD_OBJ_DISC,500,400,0,0);scd_player_place(508,373,0,0,2);
        scd_objects_step(508,373);actwk[0].direc.b.h=angle;actwk[0].xspeed.w=100;if(water)actwk[1].cddat|=64;
        scd_player_step(SCD_JUMP);scd_player_state p=scd_player_get();int impulse=water?896:1664;
        CHECK(!p.control && p.animation==2 && (p.flags&14)==14 && actwk[0].actfree[18]==1);
        CHECK(p.vx==100+(angle==64?impulse:angle==192?-impulse:0));
        CHECK(p.vy==(angle==0?-impulse:angle==128?impulse:0) && p.y/65536==378);
        CHECK(actwk[0].sprvsize==14 && actwk[0].sprhs==7 && disc_sounds==1);
        scd_objects_validate_rider();CHECK(!scd_objects_standing_type());
    }
    /* Natural radius growth eventually carries Sonic off the support. */
    init(0);swdata.w=0;scd_objects_spawn(SCD_OBJ_DISC,500,400,0,0);scd_player_place(516,373,0,0,2);scd_objects_step(516,373);
    unsigned ticks=1;while(qa_player()->control && ticks<300){scd_player_step(0);ticks++;}
    CHECK(ticks<300 && ticks>32 && !scd_objects_standing_type());
    CHECK(qa_player()->animation==45);
    /* Release happens AFTER this update's player animation. On the next
       unrolled descending update, ObjSonic_MdAir resets to animation 0. */
    scd_player_step(0);scd_player_step(0);
    CHECK(qa_player()->animation==0 && qa_player()->mapping>=51 && qa_player()->mapping<=56 && !qa_player()->control);
    /* Safe upward passage and ordinary side blocking. */
    init(0);swdata.w=0;scd_objects_spawn(SCD_OBJ_DISC,500,400,0,0);scd_player_place(500,420,0,0,2);actwk[0].yspeed.w=-256;
    scd_objects_step(500,421);CHECK(qa_player()->y/65536==420 && qa_player()->vy==-256 && !qa_player()->control);
    scd_player_place(478,400,0,0,2);actwk[0].xspeed.w=256;scd_objects_step(477,400);
    CHECK(qa_player()->x/65536==474 && !qa_player()->vx && !qa_player()->control);
    /* Invisible tunnel ownership is neither captured nor released by a disc. */
    init(0);swdata.w=0;scd_objects_spawn(SCD_OBJ_TUNNEL,500,373,0,0);actwk[1].userflag.b.l=1;scd_objects_spawn(SCD_OBJ_DISC,500,400,0,0);
    scd_player_place(500,373,0,0,2);scd_objects_step(500,373);CHECK(qa_player()->control==193 && !scd_objects_standing_type());
    /* Overlapping-disc transfer preserves angle/radius, as StandOnObject does. */
    init(0);swdata.w=0;scd_objects_spawn(SCD_OBJ_DISC,500,400,0,0);scd_objects_spawn(SCD_OBJ_DISC,504,400,0,0);
    scd_player_place(508,373,0,0,2);scd_objects_step(508,373);CHECK(qa_player()->disc_angle==16 && qa_player()->disc_radius==8 && actwk[0].actfree[19]==2);
    for(unsigned op=0;op<5;op++){
        init(0);swdata.w=0;scd_objects_spawn(SCD_OBJ_DISC,500,400,0,0);scd_player_place(508,373,0,0,2);scd_objects_step(508,373);CHECK(qa_player()->control==1);
        if(op==0)scd_objects_clear_live();else if(op==1)scd_objects_reset(1,0);else if(op==2)scd_objects_change_era(1);else if(op==3)scd_player_place(80,100,0,0,2);else scd_objects_death_record();
        CHECK(!qa_player()->control);
    }
    CHECK(!qa_error);return 0;
}

static unsigned door_sounds;
static void door_sound(short request){if(request==164)door_sounds++;}
static int __attribute__((noinline)) door_spring_probe(void){
    scd_player_audio_set(door_sound);
    /* Original flap test uses Sonic's center, half-open bounds and strictly
       negative vertical speed. The two placed subtypes differ only in width. */
    for(unsigned sub=1;sub<=2;sub++)for(unsigned edge=0;edge<9;edge++){
        int width=sub==2?24:44;
        int dx[]={-width-1,-width,width-1,width,0,0,0,0,0};
        int dy[]={0,0,0,0,-9,-8,7,8,0};
        init(0);swdata.w=0;door_sounds=0;
        CHECK(scd_objects_spawn(SCD_OBJ_DOOR,500,400,sub,0)==0);
        scd_player_place(500+dx[edge],400+dy[edge],0,0,2);actwk[0].yspeed.w=edge==8?0:-256;
        scd_objects_step(500+dx[edge],400+dy[edge]);
        CHECK(scd_objects_get().doors_opened==(edge==1 || edge==2 || edge==5 || edge==6));
        CHECK(!door_sounds && !view(SCD_OBJ_DOOR).frame);
    }
    init(0);swdata.w=0;scd_objects_spawn(SCD_OBJ_DOOR,500,400,1,0);
    scd_player_place(500,400,0,0,2);actwk[0].yspeed.w=-256;scd_objects_step(500,400);
    scd_player_place(500,373,0,0,2);actwk[0].yspeed.w=256;
    for(unsigned tick=1;tick<=12;tick++){
        scd_objects_step(500,373);
        CHECK(view(SCD_OBJ_DOOR).frame==(tick>=3 && tick<=11));
        CHECK(!scd_objects_standing_type());
    }
    scd_objects_step(500,373);CHECK(scd_objects_standing_type()==SCD_OBJ_DOOR);
    /* Vertical doors open only from the left, at |dy|<32. Frame and sound
       change on entry; the 8-bit timer closes exactly 32 subsequent ticks. */
    for(unsigned edge=0;edge<8;edge++){
        int dx[]={-49,-48,-47,0,1,-30,-30,-30};
        int dy[]={0,0,0,0,0,-32,-31,32};
        init(0);swdata.w=0;door_sounds=0;scd_objects_spawn(SCD_OBJ_DOOR_V,500,400,0,0);
        scd_player_place(500+dx[edge],400+dy[edge],0,0,2);
        scd_objects_step(500+dx[edge],400+dy[edge]);
        unsigned open=edge==2 || edge==3 || edge==6;
        CHECK(scd_objects_get().doors_opened==open && view(SCD_OBJ_DOOR_V).frame==open && door_sounds==open);
    }
    init(0);swdata.w=0;door_sounds=0;scd_objects_spawn(SCD_OBJ_DOOR_V,500,400,0,0);
    scd_player_place(490,400,256,0,0);actwk[0].xspeed.w=256;scd_objects_step(490,400);
    CHECK(qa_player()->x/65536==486 && !qa_player()->vx && door_sounds==1);
    for(unsigned tick=1;tick<=32;tick++){
        scd_player_place(490,400,256,0,2);actwk[0].xspeed.w=256;scd_objects_step(490,400);
        CHECK(qa_player()->x/65536==490 && qa_player()->vx==256);
        CHECK(view(SCD_OBJ_DOOR_V).frame==(tick<32) && door_sounds==1);
    }
    scd_objects_step(490,400);CHECK(door_sounds==2 && qa_player()->x/65536==486);
    init(0);swdata.w=0;door_sounds=0;scd_objects_spawn(SCD_OBJ_DOOR_V,500,400,0,0);
    actwk[1].actflg&=~128;scd_player_place(470,400,0,0,2);scd_objects_step(470,400);
    CHECK(scd_objects_get().doors_opened==1 && !door_sounds && !view(SCD_OBJ_DOOR_V).frame);
    actwk[1].actflg|=128;scd_objects_step(470,400);
    CHECK(!door_sounds && !view(SCD_OBJ_DOOR_V).frame);
    /* The carrier consumes a second slot. Exhaustion deletes the parent;
       one remaining slot succeeds, and clear/era replacement removes both. */
    for(unsigned available=0;available<2;available++){
        init(2);swdata.w=0;scd_player_place(7034,100,0,0,2);
        for(unsigned n=0;n<95-available;n++)CHECK(scd_objects_spawn(SCD_OBJ_RING,0,0,0,0)>=0);
        CHECK(scd_objects_spawn(SCD_OBJ_MOVING_SPRING,7034,614,0,0)==(int)(95-available));
        scd_objects_step(7034,100);
        CHECK(scd_objects_get().active==(available?96:95) && scd_objects_get().attached==available);
        scd_objects_clear_live();CHECK(!scd_objects_get().active && !scd_objects_get().attached);
        CHECK(scd_objects_spawn(SCD_OBJ_RING,500,400,0,0)==0);
        scd_objects_change_era(3);CHECK(!scd_objects_get().active);
    }
    /* A child in an earlier slot copies the previous parent position; a
       later child copies the just-updated position. Fractions are untouched. */
    for(unsigned earlier=0;earlier<2;earlier++){
        init(2);swdata.w=0;scd_player_place(7034,100,0,0,2);
        /* A lost ring leaving the map frees slot 0 before the carrier
           allocates its child. A collected ring now keeps its slot during
           the original 24-update sparkle. */
        if(earlier){CHECK(scd_objects_spawn(SCD_OBJ_LOST_RING,16383,100,0,0)==0);actwk[1].xspeed.w=256;}
        CHECK(scd_objects_spawn(SCD_OBJ_MOVING_SPRING,7034,614,0,0)==(int)earlier);
        unsigned carrier=earlier+1,child=earlier?1:2;
        scd_objects_step(7034,100);CHECK(scd_objects_get().attached==1);
        actwk[child].xposi.w.l=0x1234;actwk[child].yposi.w.l=0x5678;
        unsigned visible_ticks=0,visible=0;
        /* A spring acts only while its last update left it on screen
           (SPRING.C:399-404): give the probe a view of the carrier. */
        scd_act_camera(7034-160,614-112);
        for(unsigned tick=0;tick<360;tick++){
            int oldx=actwk[carrier].xposi.w.h,oldy=actwk[carrier].yposi.w.h;
            scd_objects_step(7034,100);
            CHECK(actwk[child].xposi.w.h==(earlier?oldx:actwk[carrier].xposi.w.h));
            CHECK(actwk[child].yposi.w.h==(earlier?oldy:actwk[carrier].yposi.w.h)-16);
            CHECK(actwk[child].xposi.w.l==0x1234 && actwk[child].yposi.w.l==0x5678);
            scd_object_view a[2];unsigned n=scd_objects_views(a,2);
            for(unsigned k=0;k<n;k++)if(a[k].type==SCD_OBJ_MOVING_SPRING){
                if(!visible){visible=1;visible_ticks=0;}
                CHECK(a[k].frame==(visible_ticks/9)%2);visible_ticks++;
            }
        }
        CHECK(visible && visible_ticks>300 && scd_objects_get().wheel_reversals>0);
        /* Descending onto the attached red spring uses the existing -4096
           impulse; the carrier never substitutes its own collision box. */
        int x=actwk[child].xposi.w.h,y=actwk[child].yposi.w.h;
        scd_player_place(x,y-27,0,0,2);actwk[0].yspeed.w=256;scd_objects_step(x,y-27);
        CHECK(scd_objects_get().springs==1 && qa_player()->vy==-4096);
        scd_objects_respawn();CHECK(!scd_objects_get().active && !scd_objects_get().attached);
    }
    /* Subtypes 0-2 are valid doors (434241c, retail R12A subtype 0); 3 is not. */
    init(0);
    CHECK(scd_objects_spawn(SCD_OBJ_DOOR,500,400,3,0)<0);
    CHECK(scd_objects_spawn(SCD_OBJ_DOOR_V,500,400,1,0)<0);
    CHECK(scd_objects_spawn(SCD_OBJ_MOVING_SPRING,500,400,1,0)<0);
    CHECK(!qa_error);return 0;
}

static int __attribute__((noinline)) tag_scenery_probe(void){
    /* Fixed input/output cases include the signed-word minimum, cap edges,
       ceiling quadrants and zero's positive direction. */
    static const int speeds[]={-32768,-4096,-3328,-2561,-2560,-2559,-1,0,1,2559,2560,2561,3328,4096,32767};
    for(unsigned sub=0;sub<2;sub++)for(unsigned angle=0;angle<256;angle+=16)for(unsigned n=0;n<sizeof(speeds)/sizeof(*speeds);n++){
        init(0);swdata.w=0;debugflag.w=0;scd_objects_spawn(SCD_OBJ_SPIN_TAG,500,400,sub,0);
        scd_player_place(500,400,77,angle,0);actwk[0].xspeed.w=sub?123:speeds[n];actwk[0].yspeed.w=sub?speeds[n]:456;
        actwk[0].xposi.w.l=0x1234;actwk[0].yposi.w.l=0x5678;
        scd_objects_step(500,400);
        int cap=sub?3328:2560,speed=speeds[n],expected=speed;
        if(speed>-cap && speed<cap)expected=speed<0?-cap:cap;
        int ground=(!sub && ((angle+32)&192)==128)?-expected:expected;
        CHECK(actwk[0].xspeed.w==(sub?123:expected) && actwk[0].yspeed.w==(sub?expected:456));
        CHECK((uint16_t)actwk[0].mspeed.w==(uint16_t)ground);
        CHECK(actwk[0].cddat==(sub?6:4) && actwk[0].sprvsize==14 && actwk[0].sprhs==7 && actwk[0].mstno.b.h==2);
        CHECK(actwk[0].xposi.w.h==500 && actwk[0].yposi.w.h==405 && actwk[0].xposi.w.l==0x1234 && actwk[0].yposi.w.l==0x5678);
        scd_objects_step(500,405);CHECK(actwk[0].yposi.w.h==405 && scd_objects_get().tag_contacts==2);
        scd_object_view v[1];CHECK(!scd_objects_views(v,1));
    }
    for(unsigned axis=0;axis<2;axis++)for(int d=-41;d<=40;d++){
        init(0);debugflag.w=0;scd_objects_spawn(SCD_OBJ_SPIN_TAG,500,400,0,0);
        scd_player_place(500+(axis?0:d),400+(axis?d:0),0,0,2);scd_objects_step(500,400);
        CHECK(scd_objects_get().tag_contacts==(d>=-40 && d<40));
    }
    for(unsigned excluded=0;excluded<3;excluded++){
        init(0);debugflag.w=excluded==0;scd_objects_spawn(SCD_OBJ_SPIN_TAG,500,400,0,0);scd_player_place(500,400,0,0,2);
        if(excluded==1)actwk[0].mstno.b.h=43;
        if(excluded==2)actwk[0].r_no0=6;
        scd_objects_step(500,400);CHECK(!scd_objects_get().tag_contacts && !actwk[0].xspeed.w);
    }
    debugflag.w=0;
    /* Already rolling preserves animation, radii and Y, including while
       another object owns control. Hurt routine 4 is not an exclusion. */
    init(0);scd_objects_spawn(SCD_OBJ_SPIN_TAG,500,400,1,0);scd_player_place(500,400,0,0,4);
    actwk[0].r_no0=4;actwk[0].actfree[2]=129;actwk[0].mstno.b.h=16;actwk[0].sprvsize=12;
    scd_objects_step(500,400);CHECK(actwk[0].r_no0==4 && actwk[0].actfree[2]==129 && actwk[0].mstno.b.h==16 && actwk[0].sprvsize==12 && actwk[0].yposi.w.h==400);
    for(unsigned sub=2;sub<=4;sub++)for(unsigned sign=0;sign<2;sign++)for(unsigned input=0;input<16;input++){
        init(0);swdata.b.h=input;scd_objects_spawn(SCD_OBJ_SPIN_TAG,500,400,sub,0);scd_player_place(500,400,77,0,0);
        actwk[0].xspeed.w=sign?-123:123;actwk[0].yspeed.w=sign?-456:456;
        scd_objects_step(500,400);
        unsigned launch=sub==4?(!sign && (input&1)):((sub==2?sign:!sign) && (input&12));
        int vx=sub!=4 && launch?((input&8)?3328:-3328):(sign?-123:123);
        int vy=sub==4 && launch?-2560:(sign?-456:456);
        CHECK(actwk[0].xspeed.w==vx && actwk[0].yspeed.w==vy);
        CHECK(actwk[0].mspeed.w==(launch?(sub==4?vy:vx):77));
        CHECK(actwk[0].cddat==(launch && sub!=2?6:4) && actwk[0].yposi.w.h==405);
    }
    /* Independent source reference: tools/tunnel_tag_reference.py. Tags do
       not exclude path-controlled Sonic; their GVel changes segment timing. */
    for(unsigned fractional=0;fractional<2;fractional++){
        init(2);swdata.w=0;scd_objects_spawn(SCD_OBJ_TUNNEL,3848,416,1,0);scd_objects_spawn(SCD_OBJ_SPIN_TAG,3872,416,0,0);
        scd_player_place(3848,416,0,0,2);if(fractional){actwk[0].xposi.w.l=0x1234;actwk[0].yposi.w.l=0x5678;}
        scd_objects_step(3848,416);uint32_t hash=tunnel_trace(2166136261u);unsigned ticks=1;
        while(qa_player()->control && ticks<1000){scd_player_step(0);hash=tunnel_trace(hash);ticks++;}
        CHECK(ticks==126 && hash==(fractional?1403366504u:3068042808u));
        CHECK(scd_objects_get().tag_contacts==9 && qa_player()->x/65536==4400 && qa_player()->y/65536==456);
    }
    for(unsigned era=0;era<4;era++){
        init(era);swdata.w=0;scd_player_place(500,400,0,0,2);
        CHECK(scd_objects_spawn(SCD_OBJ_LOG_SHADOW,500,400,era<2?0:1,0)==0);
        if(era)CHECK(scd_objects_spawn(SCD_OBJ_SCENERY,500,400,era==1?0:2,0)==1);
        for(unsigned tick=0;tick<90;tick++)scd_objects_step(500,400);
        scd_object_view shadow=view(SCD_OBJ_LOG_SHADOW);CHECK(shadow.x==500 && shadow.y==400 && shadow.frame==(era<2?0:1));
        CHECK(qa_player()->x/65536==500 && qa_player()->y/65536==400 && !scd_objects_standing_type() && !scd_objects_get().hits);
        if(era){scd_object_view scene=view(SCD_OBJ_SCENERY);CHECK(scene.x==500 && scene.y==400 && scene.frame==(era==1?0:2));}
        scd_objects_change_era(era^1);CHECK(!scd_objects_get().active);
    }
    init(0);CHECK(scd_objects_spawn(SCD_OBJ_SCENERY,500,400,0,0)<0);CHECK(scd_objects_spawn(SCD_OBJ_LOG_SHADOW,500,400,1,0)<0);CHECK(scd_objects_spawn(SCD_OBJ_SPIN_TAG,500,400,5,0)<0);
    init(1);CHECK(scd_objects_spawn(SCD_OBJ_SCENERY,500,400,2,0)<0);
    init(2);CHECK(scd_objects_spawn(SCD_OBJ_SCENERY,500,400,0,0)<0);CHECK(scd_objects_spawn(SCD_OBJ_LOG_SHADOW,500,400,0,0)<0);
    CHECK(!qa_error);return 0;
}

static unsigned projector_sounds;
static void projector_audio(short sound){if(sound==158)projector_sounds++;}
static unsigned animal_draw(unsigned actor){
    scd_object_view a[96];unsigned n=scd_objects_views(a,96);
    for(unsigned j=0;j<n;j++)if(a[j].type==SCD_OBJ_ANIMAL && a[j].x==actwk[actor].xposi.w.h && a[j].y==actwk[actor].yposi.w.h)return 1;
    return 0;
}
static int __attribute__((noinline)) projector_probe(void){
    /* Independent 1,024-tick source traces, including initialization, exact
       fractional words and the hologram's no-draw endpoint ticks. */
    for(unsigned holo=0;holo<2;holo++)for(unsigned frac=0;frac<2;frac++){
        init(holo?1:2);swdata.w=0;debugflag.w=0;
        unsigned actor;
        if(holo){
            scd_objects_spawn(SCD_OBJ_PROJECTOR,588,424,0,0);scd_objects_step(80,488);
            actor=4;CHECK(actwk[actor].actno==SCD_OBJ_ANIMAL && actwk[actor].xposi.w.h==500 && actwk[actor].yposi.w.h==400);
        }else{scd_objects_spawn(SCD_OBJ_ANIMAL,500,400,0,0);actor=1;scd_objects_step(80,488);}
        if(frac){actwk[actor].xposi.w.l=0x1234;actwk[actor].yposi.w.l=0x5678;}
        uint32_t hash=2166136261u;
        for(unsigned tick=0;tick<1024;tick++){
            if(tick)scd_objects_step(80,488);
            sprite_status *o=&actwk[actor];
            uint32_t words[]={(uint32_t)o->xposi.l,(uint32_t)o->yposi.l,(uint8_t)o->direc.b.h,(uint8_t)o->direc.b.l,o->actflg&1,o->patno,animal_draw(actor),o->patcnt,o->pattim};
            for(unsigned j=0;j<sizeof(words)/sizeof(*words);j++){hash^=words[j];hash*=16777619u;}
        }
        CHECK(hash==(holo?(frac?3079872635u:1246799027u):(frac?1746721573u:1532420965u)));
    }
    /* No score, recoil or invincibility shortcut: FB requires animation 2.
       Check the source 18x17 box at both inclusive contact boundaries. */
    for(unsigned axis=0;axis<2;axis++)for(int edge=-1;edge<=1;edge++)for(int sign=-1;sign<=1;sign+=2){
        init(1);scd_objects_spawn(SCD_OBJ_PROJECTOR,500,400,0,0);scd_objects_step(80,488);
        int x=500+(axis?0:sign*(26+edge)),y=400+(axis?sign*(28+edge):0);
        scd_player_place(x,y,0,0,6);actwk[0].mstno.b.h=2;actwk[0].sprvsize=14;actwk[0].xspeed.w=0;actwk[0].yspeed.w=0;
        scd_objects_step(x,y);CHECK(scd_objects_get().projector_hits==(edge<=0));CHECK(!qa_player()->score && !scd_objects_generator());
    }
    for(unsigned excluded=0;excluded<6;excluded++){
        init(1);scd_objects_spawn(SCD_OBJ_PROJECTOR,500,400,0,0);scd_objects_step(80,488);scd_player_place(500,400,0,0,6);actwk[0].mstno.b.h=2;
        if(excluded==0)actwk[0].mstno.b.h=0;
        if(excluded==1)actwk[0].r_no0=4;
        if(excluded==2)actwk[0].r_no0=6;
        if(excluded==3)actwk[0].actfree[2]=128;
        if(excluded==4)debugflag.w=1;
        if(excluded==5)actwk[1].actflg&=~128;
        plpower_m=1;scd_objects_step(500,400);CHECK(!scd_objects_get().projector_hits);debugflag.w=0;
    }
    /* Dormant animals keep their slots. Projector completion makes them
       initialize, then draw; completion survives respawn and era changes. */
    init(1);scd_player_audio_set(projector_audio);projector_sounds=0;
    CHECK(scd_objects_spawn(SCD_OBJ_ANIMAL,420,300,0,0)==0);
    CHECK(scd_objects_spawn(SCD_OBJ_ANIMAL,420,360,1,0)==1);
    for(unsigned tick=0;tick<90;tick++)scd_objects_step(80,488);
    CHECK(scd_objects_get().active==2 && !scd_objects_get().animals && !scd_objects_views((scd_object_view[96]){{0}},96));
    CHECK(scd_objects_spawn(SCD_OBJ_PROJECTOR,500,400,0,0)==2);scd_objects_step(80,488);
    CHECK(scd_objects_get().holograms==4 && scd_objects_get().attached==0);
    scd_player_place(500,374,0,0,6);actwk[0].mstno.b.h=2;
    scd_objects_step(500,374);CHECK(scd_objects_get().projector_hits==1 && !projector_sounds && view(SCD_OBJ_PROJECTOR).frame==0);
    scd_player_place(80,488,0,0,2);
    static const unsigned events[]={1,5,10,15,20,22,25,28,30,32,35,40};unsigned expected=0;
    for(unsigned tick=1;tick<=101;tick++){
        scd_objects_step(80,488);
        if(expected<12 && tick==events[expected])expected++;
        CHECK(projector_sounds==expected && scd_objects_get().projector_explosions==expected);
        CHECK(scd_objects_projector_destroyed()==(tick==101));
        CHECK(!scd_objects_get().holograms && !scd_objects_generator());
        if(tick<101)CHECK(view(SCD_OBJ_PROJECTOR).frame==1);
    }
    CHECK(scd_objects_get().active==2 && !scd_objects_get().animals);
    scd_objects_step(80,488);CHECK(!scd_objects_get().animals);
    scd_objects_step(80,488);CHECK(scd_objects_get().animals==2);
    scd_objects_respawn();CHECK(scd_objects_projector_destroyed() && !scd_objects_get().active);
    for(unsigned era=0;era<4;era++){
        scd_objects_change_era(era);CHECK(scd_objects_projector_destroyed());
        scd_objects_spawn(SCD_OBJ_ANIMAL,500,400,0,0);scd_objects_step(80,488);scd_objects_step(80,488);
        CHECK(scd_objects_get().animals==(era<2));
    }
    scd_objects_reset(1,0);CHECK(!scd_objects_projector_destroyed());
    /* Each of four initialization failures deletes every partially-created
       child. Refilling immediately must not attach or delete unrelated slots. */
    for(unsigned free=0;free<4;free++){
        init(1);scd_objects_spawn(SCD_OBJ_PROJECTOR,500,400,0,0);
        for(unsigned n=0;n<95-free;n++)CHECK(scd_objects_spawn(SCD_OBJ_BOULDER,1500,400,0,0)>0);
        scd_objects_step(80,488);CHECK(scd_objects_get().active==95-free && !scd_objects_get().holograms && !actwk[1].actno);
        CHECK(scd_objects_spawn(SCD_OBJ_BOULDER,1500,400,0,0)==0);scd_objects_step(80,488);CHECK(actwk[1].actno==SCD_OBJ_BOULDER && !scd_objects_projector_destroyed());
    }
    /* Destruction script advances even when every explosion allocation fails.
       The four child slots become free on the first broken tick, then refill. */
    init(1);scd_player_audio_set(projector_audio);projector_sounds=0;
    scd_objects_spawn(SCD_OBJ_PROJECTOR,500,400,0,0);scd_objects_step(80,488);
    scd_player_place(500,374,0,0,6);actwk[0].mstno.b.h=2;scd_objects_step(500,374);scd_player_place(80,488,0,0,2);
    while(scd_objects_get().active<96)CHECK(scd_objects_spawn(SCD_OBJ_BOULDER,1500,400,0,0)>=0);
    scd_objects_step(80,488);CHECK(!projector_sounds && !scd_objects_get().holograms);
    while(scd_objects_get().active<96)CHECK(scd_objects_spawn(SCD_OBJ_BOULDER,1500,400,0,0)>=0);
    for(unsigned tick=2;tick<=101;tick++)scd_objects_step(80,488);
    CHECK(scd_objects_projector_destroyed() && !projector_sounds && !scd_objects_get().projector_explosions && scd_objects_get().active==95);
    /* Ground animals use signed 16.16 movement and reverse only at a negative
       floor distance, retaining low position words during the floor snap. */
    init(2);scd_objects_spawn(SCD_OBJ_ANIMAL,500,100,1,0);actwk[1].xposi.w.l=0x1234;actwk[1].yposi.w.l=0x5678;
    scd_objects_step(80,488);
    for(unsigned tick=1;tick<=16;tick++){
        scd_objects_step(80,488);
        CHECK(actwk[1].xposi.l==(500+(int)tick)*65536+0x1234);
        CHECK(actwk[1].yposi.l==100*65536+0x5678-262144*(int)tick+8192*(int)(tick*(tick-1)/2));
        CHECK(view(SCD_OBJ_ANIMAL).frame==0);
    }
    /* Lower child slots are visited before their parent. Initialization and
       the final hologram draw therefore each differ by one scheduler tick. */
    init(1);scd_player_place(500,400,0,0,2);
    for(unsigned n=0;n<4;n++)CHECK(scd_objects_spawn(SCD_OBJ_RING,500,400,0,0)==(int)n);
    CHECK(scd_objects_spawn(SCD_OBJ_PROJECTOR,500,400,0,0)==4);scd_objects_step(500,400);
    CHECK(scd_objects_get().collected==4 && scd_objects_get().holograms==4);
    scd_object_view order_views[96];unsigned order_count=scd_objects_views(order_views,96);
    CHECK(order_count==7);
    CHECK(order_views[0].type==SCD_OBJ_RING && order_views[0].frame==4);
    scd_player_place(80,488,0,0,2);scd_objects_step(80,488);CHECK(scd_objects_views(order_views,96)==9 && order_views[0].frame==4);
    scd_objects_step(80,488);CHECK(scd_objects_views(order_views,96)==9);
    scd_player_place(500,374,0,0,6);actwk[0].mstno.b.h=2;scd_objects_step(500,374);CHECK(scd_objects_get().projector_hits==1);
    scd_player_place(80,488,0,0,2);scd_objects_step(80,488);
    /* Ring sparkle slots place all four children after the parent, so they
       see state 3 and leave on this update rather than the next one. */
    CHECK(!scd_objects_get().holograms);
    CHECK(actwk[5].patno==1);
    scd_objects_step(80,488);CHECK(!scd_objects_get().holograms);
    scd_objects_clear_live();CHECK(!scd_objects_get().active);
    /* Verify ground reversals and preserved fractional X against real floor
       collision. Every reversal makes the following step change X direction. */
    init(2);scd_objects_spawn(SCD_OBJ_ANIMAL,52,486,1,0);scd_objects_step(80,488);
    unsigned reversals=0,old_flip=0;int old_x=52,direction=1;
    for(unsigned tick=0;tick<240;tick++){
        scd_objects_step(80,488);scd_object_view ground=view(SCD_OBJ_ANIMAL);
        CHECK(ground.x-old_x==direction);old_x=ground.x;
        if((ground.flags&1)!=old_flip){reversals++;old_flip=ground.flags&1;direction=-direction;}
        CHECK(ground.frame<=1);
    }
    CHECK(reversals>=3);
    CHECK(scd_objects_spawn(SCD_OBJ_ANIMAL,500,400,2,0)<0 && scd_objects_spawn(SCD_OBJ_PROJECTOR,500,400,2,0)<0);
    scd_player_audio_set(NULL);CHECK(!qa_error);return 0;
}

#include "amy_qa.inc"

/* Keep diagnostic groups sequential so their large local fixture arrays and
   returned state snapshots do not share one giant SH-2 stack frame. */
volatile uint32_t scd_world_probe_phase;
int scd_world_probe(const uint8_t *const *packs,const size_t *sizes,const uint8_t *const *collisions){
    scd_world_probe_iteration=0;scd_world_probe_phase=1;int error=world_probe(packs,sizes,collisions);if(error)return error;
    scd_world_probe_phase=2;error=monitor_probe();if(error)return error;
    scd_world_probe_phase=3;error=collapse_probe();scd_player_audio_set(NULL);if(error)return error;
    scd_world_probe_phase=4;error=tunnel_probe();scd_player_audio_set(NULL);if(error)return error;
    scd_world_probe_phase=5;error=disc_probe();scd_player_audio_set(NULL);if(error)return error;
    scd_world_probe_phase=6;error=door_spring_probe();scd_player_audio_set(NULL);if(error)return error;
    scd_world_probe_phase=7;error=tag_scenery_probe();scd_player_audio_set(NULL);if(error)return error;
    scd_world_probe_phase=8;error=projector_probe();scd_player_audio_set(NULL);if(error)return error;
    scd_world_probe_phase=9;error=amy_probe();scd_player_audio_set(NULL);if(error)return error;
    scd_world_probe_phase=10;return 0;
}
