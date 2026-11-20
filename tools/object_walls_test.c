/* Host acceptance test for the static sized solids in src/objects_walls.inc:
 * SCD_OBJ_WALL4 (R4/WALL1.C wall1) and SCD_OBJ_WALL7 (R7/WALL7.C wall7, and
 * R7/WALL73.C wall73 when subtype bit 7 is set).
 *
 * 1. Focused: every subtype the retail data uses, spawned at a known place on
 *    Tidal Tempest Act 2 Present terrain. The player is driven into each side,
 *    dropped onto the top and jumped into the bottom, and must stop exactly
 *    where RIDECHK.C hitchk puts him. wall73's scripted move (WALL73.C
 *    move_blk) must carry a standing player with the block.
 * 2. Stall: the retail placements of these objects, read from
 *    build/auto-extract/<round>/objects<round><act><era>.bin, are spawned into
 *    the six routes they seal (R42A-D stall at x=661, R73C/D fall at x=12790)
 *    and the walker must now get past the stall. Each route runs the stock
 *    walker (Jump pressed for one frame, as tools/zone_walk_test.c does) and a
 *    variant that holds Jump while Sonic rises. R73 also runs with its start
 *    gate opened the way the unported R7 boss opens it, and a control run
 *    without the record that fills the hole, which must still fall.
 *
 * Build and run from the repository root. ROOT is the checkout that holds the
 * gitignored assets/generated, build/probe-source and build/auto-extract:
 *   ROOT=/path/to/sonic-cd-saturn
 *   clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value \
 *    -Isrc -I$ROOT/assets/generated -I$ROOT/build/probe-source -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all \
 *    tools/object_walls_test.c src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c src/sonic_animation.c src/stage.c src/objects.c \
 *    $ROOT/build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c -o build/object_walls_test
 *   build/object_walls_test $ROOT
 * Exit status 0 only when the focused test passes and every stall route
 * clears with at least one walker. */
#include "EQU.H"
#include "player_replay.h"
#include "scd_objects.h"
#include "scd_player.h"
#include "act.h"
#include "world.h"
#include "title_card.h"
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
extern short scralim_left,scralim_right,scralim_down,scra_vline;

static const char *root=".";
static uint8_t data[300000],collision[9472],layout[16384];
static stage_t stage;
static unsigned failures;
#define CHECK(cond,...) do{if(!(cond)){failures++;printf("FAIL %s:%d: ",__FILE__,__LINE__);printf(__VA_ARGS__);printf("\n");}}while(0)

static size_t slurp(const char *name,uint8_t *out,size_t cap){
    char path[512];snprintf(path,sizeof path,"%s/%s",root,name);
    FILE *f=fopen(path,"rb");if(!f){fprintf(stderr,"missing %s\n",path);exit(2);}
    size_t n=fread(out,1,cap,f);fclose(f);return n;
}
/* The retail size tables, restated here so the test checks the port against
   the source rather than against itself. */
static const uint8_t wall1_size[7][2]={{16,16},{16,16},{32,16},{16,32},{32,32},{64,16},{16,64}};  /* R4/WALL1.C:67-75 */
static const uint8_t wall7_size[6][2]={{12,17},{28,17},{44,17},{60,17},{12,33},{12,49}};          /* R7/WALL7.C:69-76 */
static const uint8_t wall73_size[6][2]={{11,16},{32,16},{48,16},{64,16},{11,32},{11,48}};         /* R7/WALL73.C:9-16 */
#define WALL73 128
typedef struct {unsigned type,sub;const uint8_t *size;const char *name;} kind;
static kind kinds[19];
static unsigned kind_count;
static void kinds_init(void){
    for(unsigned s=0;s<7;s++)kinds[kind_count++]=(kind){SCD_OBJ_WALL4,s,wall1_size[s],"wall1"};
    for(unsigned s=0;s<6;s++)kinds[kind_count++]=(kind){SCD_OBJ_WALL7,s,wall7_size[s],"wall7"};
    for(unsigned s=0;s<6;s++)kinds[kind_count++]=(kind){SCD_OBJ_WALL7,s|WALL73,wall73_size[s],"wall73"};
}

static void open_stage(const char *pack,const char *coll,unsigned zone,unsigned era,unsigned act){
    size_t size=slurp(pack,data,sizeof data);
    if(slurp(coll,collision,sizeof collision)!=sizeof collision){fprintf(stderr,"collision size %s\n",coll);exit(2);}
    if(stage_open(&stage,data,size)){fprintf(stderr,"stage_open rejected %s\n",pack);exit(2);}
    scd_player_zone(zone);scd_objects_zone(zone);
    scd_player_act(act);scd_objects_act(act);scd_world_act(act);
    if(scd_player_init(&stage,collision,sizeof collision,era)){fprintf(stderr,"player init\n");exit(2);}
    scd_world_reset(era);
}
static int px(void){return scd_player_get().x>>16;}
static int py(void){return scd_player_get().y>>16;}
static void steps(unsigned n,unsigned buttons){for(unsigned k=0;k<n;k++)scd_player_step(buttons);}

/* ---------------------------------------------------------------- focused */
/* Tidal Tempest Act 2 Present. Sonic stands at the retail start y=1260
   (report.json R42A start 80,1260) on the room floor that spans x=16..255,
   so the floor surface is y=1260+19. The shaft x=256..511 holds no solid
   pixel at any height, so an object placed there is the only thing Sonic
   can touch. */
#define STAND 1260
#define FLOOR (STAND+19)
#define SHAFT_X 384
static void fixture(void){
    open_stage("assets/generated/tt42A.bin","assets/generated/ttcollision42A.bin",2,0,1);
    steps(8,0);
}
static int spawn(const kind *k,int x,int y){
    int i=scd_objects_spawn(k->type,x,y,k->sub,0);
    CHECK(i>=0,"%s sub %u did not spawn",k->name,k->sub&127);
    return i;
}
/* These actor routines publish patno/actflg, unlike PPZ's slot.frame. Losing
   that boundary made every new sprite render frame zero, even when its
   collision and animation state were correct. Exercise actual updates. */
static void rendered_frames(void){
    static const unsigned cases[][2]={{67,5},{68,5},{68,133},{69,7},{70,0},{71,1}};
    unsigned poses=0;
    for(unsigned c=0;c<sizeof(cases)/sizeof(*cases);c++)for(unsigned flip=0;flip<4;flip++){
        fixture();
        /* KONBEA (70) is R8-only: production reaches it through mm_zone_ops (zone 6). */
        if(cases[c][0]==70)scd_objects_zone(6);
        int slot=scd_objects_spawn(cases[c][0],200,1100,cases[c][1],flip);
        CHECK(slot>=0,"render fixture allocation");if(slot<0)continue;
        for(unsigned tick=0;tick<360;tick++){
            steps(1,0);scd_object_view views[96];unsigned count=scd_objects_views(views,96),seen=0;
            sprite_status *actor=&actwk[slot+1];
            for(unsigned i=0;i<count;i++)if(views[i].type==cases[c][0]){
                CHECK(views[i].frame==actor->patno && views[i].flags==(actor->actflg&3),
                    "type %u tick %u: rendered frame/flip %u/%u, actor %u/%u",cases[c][0],tick,
                    views[i].frame,views[i].flags,actor->patno,actor->actflg&3);
                if(cases[c][0]==70)poses|=1u<<views[i].frame;
                seen++;
            }
            CHECK(seen==1,"type %u: missing or duplicate rendered actor",cases[c][0]);
        }
    }
    CHECK(poses==127,"konbea flip animation did not render all seven patterns: %x",poses);
}
static void focused(void){
    fixture();
    int standing=py();
    CHECK(standing==STAND && !(scd_player_get().flags&2),"fixture: Sonic stands at y=%d, want %d",standing,STAND);
    /* Out-of-table subtypes never allocate. */
    CHECK(scd_objects_spawn(SCD_OBJ_WALL4,200,1000,7,0)<0,"wall1 subtype 7 spawned");
    CHECK(scd_objects_spawn(SCD_OBJ_WALL7,200,1000,6,0)<0,"wall7 subtype 6 spawned");
    CHECK(scd_objects_spawn(SCD_OBJ_WALL7,200,1000,6|WALL73,0)<0,"wall73 subtype 6 spawned");
    for(unsigned n=0;n<kind_count;n++){
        const kind *k=&kinds[n];unsigned sub=k->sub&127;int hw=k->size[0],hh=k->size[1];
        /* Sizes and pattern after the first call (WALL1.C:123-125). */
        fixture();
        int i=spawn(k,200,FLOOR-hh);steps(1,0);
        sprite_status *o=&actwk[i+1];
        CHECK(o->sprhsize==hw && o->sprhs==hw && o->sprvsize==hh && o->patno==sub,
              "%s sub %u: size %ux%u hs %u patno %u, want %dx%d patno %u",k->name,sub,o->sprhsize,o->sprvsize,o->sprhs,o->patno,hw,hh,sub);
        /* Run in from the left along the floor: stopped at ox-(hw+10) (RIDECHK.C:261,385). */
        steps(150,SCD_RIGHT);
        scd_player_state p=scd_player_get();
        CHECK(px()==200-hw-10 && p.vx==0 && py()==STAND && (p.flags&32) && !(p.flags&8) && !p.resets,
              "%s sub %u left side: x=%d y=%d vx=%d flags=%02x, want x=%d y=%d pushing",k->name,sub,px(),py(),p.vx,p.flags,200-hw-10,STAND);
        /* Run in from the right: never past ox+(hw+10). The range test is
           asymmetric (RIDECHK.C:262-270: dx+width must be in [0,2*width)), so
           at exactly ox+width Sonic is outside it and creeps back in by
           sub-pixels each frame before the next push. Check the whole second
           half of the run, not one frame's speed. */
        fixture();
        scd_player_place(236,STAND,0,0,0);steps(4,0);
        i=spawn(k,100,FLOOR-hh);
        steps(75,SCD_LEFT);
        int least=px(),most=px();
        for(unsigned f=0;f<75;f++){scd_player_step(SCD_LEFT);if(px()<least)least=px();if(px()>most)most=px();}
        p=scd_player_get();
        CHECK(least==100+hw+10 && most==100+hw+10 && py()==STAND && p.vx>-64 && p.vx<=0 && !p.resets,
              "%s sub %u right side: x %d..%d y=%d vx=%d, want x=%d",k->name,sub,least,most,py(),p.vx,100+hw+10);
        /* Drop onto the top in the empty shaft: lands at oy-hh-19 (RIDECHK.C:490-491)
           and a static wall carries a standing player 0 px. */
        fixture();
        int oy=1500;i=spawn(k,SHAFT_X,oy);steps(1,0);
        scd_player_place(SHAFT_X,oy-hh-120,0,0,2);
        steps(90,0);p=scd_player_get();
        int land_x=px(),land_y=py();
        CHECK(land_y==oy-hh-19 && (p.flags&8) && !(p.flags&2) && scd_objects_standing_type()==k->type,
              "%s sub %u top: y=%d flags=%02x standing type %u, want y=%d on the wall",k->name,sub,land_y,p.flags,scd_objects_standing_type(),oy-hh-19);
        steps(60,0);
        CHECK(px()==land_x && py()==land_y && (scd_player_get().flags&8),"%s sub %u: a static wall moved its rider to (%d,%d) from (%d,%d)",k->name,sub,px(),py(),land_x,land_y);
        /* Jump into the bottom: stopped at oy+hh+19+2 with Y speed 0 (RIDECHK.C:611-612). */
        fixture();
        i=spawn(k,SHAFT_X,oy);steps(1,0);
        scd_player_place(SHAFT_X,oy+hh+21+40,0,0,2);scd_player_velocity(0,-1536);
        int hit=-1;
        for(unsigned f=0;f<40 && hit<0;f++){scd_player_step(0);if(scd_player_get().vy==0)hit=py();}
        CHECK(hit==oy+hh+19+2,"%s sub %u bottom: stopped at y=%d, want %d",k->name,sub,hit,oy+hh+19+2);
        (void)o;
    }
    /* wall73 move_blk (WALL73.C:97-166) with the retail secondary byte 0xC2 of
       objects73C.bin x=3184 y=448 subtype 4: two 32px rises at 2px a frame, and
       a shrink from patno 4 to patno 0 (bottom kept) between them. Only the R7
       boss sets bossflag bit 7 in retail; the test sets it by hand. */
    {
        const kind *k=&kinds[7+6+4];
        fixture();bossflag=0;
        int oy=1500,i=spawn(k,SHAFT_X,oy);sprite_status *o=&actwk[i+1];
        o->userflag.b.l=(char)0xC2;steps(1,0);
        scd_player_place(SHAFT_X,oy-32-19-60,0,0,2);steps(60,0);
        CHECK(py()==oy-32-19 && (scd_player_get().flags&8),"wall73 carry: not standing before the move (y=%d)",py());
        bossflag|=128;
        int start=py(),carried=1;
        for(unsigned f=1;f<=15;f++){
            scd_player_step(0);
            if(o->yposi.w.h!=oy-2*(int)f || py()!=o->yposi.w.h-32-19-2 || !(scd_player_get().flags&8))carried=0;
        }
        CHECK(carried,"wall73 carry: rider lost during the first rise (block y=%d, Sonic y=%d)",o->yposi.w.h,py());
        CHECK(start-py()==30+2,"wall73 carry: carried %d px over 15 frames, want 32 (30 of block travel plus the 2px yspeed carry of RIDECHK.C:514-515)",start-py());
        scd_player_step(0);
        CHECK(o->yposi.w.h==oy-32+16 && o->patno==0 && o->sprhsize==11 && o->sprvsize==16 && (uint8_t)o->userflag.b.l==0xC1,
              "wall73 carry: after the first rise block y=%d patno %u size %ux%u sec %02x, want y=%d patno 0 size 11x16 sec C1",
              o->yposi.w.h,o->patno,o->sprhsize,o->sprvsize,(uint8_t)o->userflag.b.l,oy-16);
        steps(40,0);
        CHECK(o->yposi.w.h==oy-48 && o->patno==0 && o->userflag.b.l==0 && !(bossflag&128),
              "wall73 carry: end block y=%d patno %u sec %02x bossflag %02x, want y=%d patno 0 sec 0 bit 7 clear",o->yposi.w.h,o->patno,(uint8_t)o->userflag.b.l,bossflag,oy-48);
        CHECK(py()==oy-48-16-19-2 && (scd_player_get().flags&8),"wall73 carry: Sonic ends at y=%d, want %d on the block",py(),oy-48-16-19-2);
        bossflag=0;
    }
}

/* ---------------------------------------------------------------- stall */
typedef struct {int16_t x,y;uint8_t type,sub,flags,secondary;} record;
static record records[128];
static unsigned record_count;
/* ACTSET.C record: x u16, y u16 (bits 14-15 flip), id (bit 7 one-shot,
   bits 0-6 = act_tbl index + 1, ACTION.C:53), subtype, era mask in bits 5-7
   (bit 0 Past, bit 1 Present, bit 2 Future), secondary. */
static void load_records(const char *program,unsigned round,unsigned act,unsigned era){
    char name[128];snprintf(name,sizeof name,"build/auto-extract/%u/objects%s.bin",round,program);
    size_t n=slurp(name,layout,sizeof layout);record_count=0;
    unsigned mask=era==0?2:era==1?1:4;
    for(size_t at=0;at+8<=n;at+=8){
        const uint8_t *r=layout+at;unsigned x=(r[0]<<8)|r[1],y=(r[2]<<8)|r[3],id=r[4]&127,sub=r[5],eras=r[6]>>5,sec=r[7];
        if(x==65535)break;
        if(!(eras&mask))continue;
        unsigned type=0;
        /* R4: every act_tbl has wall1 at index 51 (ACT42A.C:89, ACT42B.C:81, ACT42C.C). */
        if(round==4 && id==52){type=SCD_OBJ_WALL4;}
        /* R7: wall7 is id 36 in ACT71A.C:63 and ACT73.C:62; wall73 is id 43 only in ACT73.C:69. */
        if(round==7 && id==36){type=SCD_OBJ_WALL7;}
        if(round==7 && act==2 && id==43){type=SCD_OBJ_WALL7;sub|=WALL73;}
        if(!type)continue;
        if(record_count<sizeof records/sizeof *records)records[record_count++]=(record){x,y&0x3fff,type,sub,y>>14,sec};
    }
}
/* The retail loader keeps an object live only near the camera; stream() in
   objects.c spawns placements within 480px of Sonic. Do the same here, so a
   scripted wall at the far end of the act is not live, and moving, while the
   start gate runs its script. A wall is kept once loaded. */
static uint8_t loaded[sizeof records/sizeof *records];
static int skip_x=-1,skip_y=-1;  /* one record left out, for the control run */
static void load_near(int x){
    for(unsigned n=0;n<record_count;n++){
        const record *r=&records[n];
        if(loaded[n] || r->x-x>480 || x-r->x>480 || (r->x==skip_x && r->y==skip_y))continue;
        int i=scd_objects_spawn(r->type,r->x,r->y,r->sub,r->flags);
        loaded[n]=1;
        if(i>=0)actwk[i+1].userflag.b.l=(char)r->secondary;
        else {printf("  spawn failed: type %u at (%d,%d)\n",r->type,r->x,r->y);failures++;}
    }
}
typedef struct {int max_x,min_y,max_y,end_x,end_y,deaths,fell,door;unsigned updates,jumps;} walk;
/* tools/zone_walk_test.c's loop. hold=0 is the stock walker (one-frame Jump
   tap); hold=1 keeps Jump down while Sonic rises. mode 0 spawns nothing,
   mode 1 the retail placements, mode 2 also opens the R7 Act 3 start gate the
   way R7/BOSS_7.C:857-871 door_open does (bossflag |= 128, line 862) once
   Sonic is within 160px of it; the port has no R7 boss to do it. mode 3 is
   mode 2 without the one record that should fill the stall (the control).
   Placements are loaded again after a life is lost. */
static walk run(const char *pack,const char *coll,unsigned zone,unsigned era,unsigned act,int mode,int hold,int door_x){
    open_stage(pack,coll,zone,era,act);bossflag=0;
    memset(loaded,0,sizeof loaded);
    scd_title_card_start(act);
    scd_player_state p=scd_player_get();
    walk w={p.x>>16,p.y>>16,p.y>>16,0,0,0,0,0,0,0};
    if(mode)load_near(p.x>>16);
    unsigned stuck=0,held=0,resets=0;int last_x=w.max_x;
    for(;w.updates<20000;w.updates++){
        unsigned buttons=SCD_RIGHT;
        if(held && (p.flags&2) && p.vy<0)buttons|=SCD_JUMP;else held=0;
        if(stuck>=30 && !(p.flags&2)){buttons|=SCD_JUMP;w.jumps++;stuck=0;held=hold;}
        scd_player_hold_clock(scd_title_card_locked());
        scd_player_step(scd_title_card_locked()?0:buttons);
        scd_title_card_step();
        p=scd_player_get();
        int x=p.x>>16,y=p.y>>16;
        if(mode>=2 && door_x && !w.door && x>=door_x-160){bossflag|=128;w.door=1;}
        if(x>last_x+1){stuck=0;last_x=x;}else stuck++;
        if(x>w.max_x)w.max_x=x;
        if(y<w.min_y)w.min_y=y;if(y>w.max_y)w.max_y=y;
        /* PLAYER.C limitchk: below scralim_down+224 is a fall death in every zone. */
        if(y>scralim_down+224)w.fell=1;
        if(p.resets>resets){resets=p.resets;w.deaths=(int)resets;memset(loaded,0,sizeof loaded);}
        if(mode)load_near(x);
        if(x>=scralim_right)break;
    }
    w.fell|=w.max_y>2040;w.end_x=p.x>>16;w.end_y=p.y>>16;
    bossflag=0;
    return w;
}
typedef struct {const char *program;unsigned round,act,era,zone;const char *prefix;int stall_x,door_x,key_x,key_y;} route;
/* door_x: R7 Act 3's start gate, objects73C.bin/73D.bin wall73 subtype 4 at
   (3184,448) with secondary 0xC2. move_blk lifts it 32px, shrinks it to
   subtype 0 and lifts it 32px more (WALL73.C:103-162).
   key: the record the stall report names, wall73 subtype 3 at (12224,496),
   a 128x32 solid whose top is y=480 (WALL73.C:9-16 entry 3 = 64,16). */
static const route routes[]={
    {"42A",4,1,0,2,"tt",661,0,0,0},{"42B",4,1,1,2,"tt",661,0,0,0},{"42C",4,1,2,2,"tt",661,0,0,0},{"42D",4,1,3,2,"tt",661,0,0,0},
    {"73C",7,2,2,5,"ss",12790,3184,12224,496},{"73D",7,2,3,5,"ss",12790,3184,12224,496},
};
static unsigned stall(void){
    unsigned cleared=0;
    static const char *const modes[]={"no objects","objects","objects+door","control"};
    for(unsigned n=0;n<sizeof routes/sizeof *routes;n++){
        const route *r=&routes[n];char pack[128],coll[128];
        snprintf(pack,sizeof pack,"assets/generated/%s%s.bin",r->prefix,r->program);
        snprintf(coll,sizeof coll,"assets/generated/%scollision%s.bin",r->prefix,r->program);
        load_records(r->program,r->round,r->act,r->era);
        printf("R%s: %u placements of this family active in this era\n",r->program,record_count);
        for(unsigned k=0;k<record_count;k++)printf("  %s sub %u at (%d,%d)%s\n",records[k].type==SCD_OBJ_WALL4?"wall1":(records[k].sub&WALL73)?"wall73":"wall7",
            records[k].sub&127,records[k].x,records[k].y,records[k].secondary?" (scripted by BOSS_7 bossflag)":"");
        int passed=0;
        for(int mode=0;mode<(r->key_x?4:r->door_x?3:2);mode++)for(int hold=0;hold<2;hold++){
            if(mode==3){skip_x=r->key_x;skip_y=r->key_y;}
            walk w=run(pack,coll,r->zone,r->era,r->act,mode,hold,r->door_x);
            skip_x=skip_y=-1;
            int past=w.max_x>r->stall_x && !w.fell;
            printf("  %-12s %-9s max_x=%5d  end (%5d,%4d)  y %4d..%4d  deaths %d  jumps %3u%s  -> %s\n",modes[mode],hold?"held jump":"tap jump",
                   w.max_x,w.end_x,w.end_y,w.min_y,w.max_y,w.deaths,w.jumps,w.fell?"  FELL OUT":"",past?"past the stall":"stalled");
            if(mode==3)CHECK(!past && w.fell,"R%s control: without (%d,%d) Sonic should fall out, max_x=%d",r->program,r->key_x,r->key_y,w.max_x);
            else if(mode && past)passed=1;
        }
        printf("  R%s stall x=%d: %s\n",r->program,r->stall_x,passed?"CLEARED":"NOT CLEARED");
        /* Only the routes with a keyed wall73 are the walls' to clear. R42A-D stay
           sealed with every wall1 record in place: the only way out of their shaft
           lands in a bay with no exit, and whatever lifts Sonic out in retail is not
           wall1 (the Past records the catalogue cited are id 61, rblk4). They are
           walked and reported so a change in them shows, but they do not gate. */
        if(r->key_x)cleared+=passed;
        else if(passed)printf("  R%s now clears: revisit the note above\n",r->program);
    }
    return cleared;
}
int main(int argc,char **argv){
#ifdef SCD_ASSET_ROOT
    root=SCD_ASSET_ROOT;
#endif
    if(argc>1)root=argv[1];
    kinds_init();
    focused();
    rendered_frames();
    printf("focused: %u kinds (wall1 0-6, wall7 0-5, wall73 0-5) x left/right/top/bottom, plus the wall73 carry: %s\n",kind_count,failures?"FAIL":"PASS");
    unsigned focused_failures=failures;
    unsigned cleared=stall();
    unsigned total=0;for(unsigned n=0;n<sizeof routes/sizeof *routes;n++)total+=routes[n].key_x!=0;
    printf("stall: %u of %u keyed wall73 routes cleared (R42A-D reported, not gated)\n",cleared,total);
    return focused_failures || failures!=focused_failures || cleared!=total;
}
