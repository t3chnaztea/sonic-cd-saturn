/* Konbea (retail R8 id 42, R8/KONBEA.C; port type SCD_OBJ_KONBEA) on the host.
 *
 * 1. Parity: the retail KONBEA.C runs beside src/objects_konbea.inc and every
 *    actor word must match on every update, for subtype 0 and 1 (the two the
 *    R81 placements use), a flipped copy, and the dead secondary-1 path.
 * 2. Focused: the port player on the real R81A terrain. Subtype 0 carries
 *    Sonic at y = top - 19 for exactly 120 updates, drops him for the 23-update
 *    flip, never blocks from the side and lets a jump pass up through it.
 *    Subtype 1 carries him the full top run of konbea8tbl and drops him at
 *    path index 344.
 * 3. Stall: R81A-D walked like tools/zone_walk_test.c, with the era-matching
 *    id 42 (konbea) and id 10 (spring) records of build/auto-extract/8/
 *    objects81?.bin spawned once Sonic is inside the port's stream radius.
 *    The pit's way out is konbea -> the step to its LEFT -> the step's spring.
 *    The stock walker (one-update Jump tap, Right only) and a held-Jump walker
 *    are reported but cannot take a leftward exit; the gate is a walker that
 *    holds Jump while rising and steers Left for a jump that starts on a
 *    konbea. It must pass x=501 with konbea and spring, and must NOT pass with
 *    either one alone.
 *
 * Build (the retail file indexes actor words as 32-bit PC offsets; address
 * them through actfree, as tools/test-swing.sh does for BRANKO1.C):
 *   M=.; T=<scratch dir>
 *   python3 - "$M" > "$T/konbea_pc.c" <<'EOF'
 *   import re,sys
 *   src=sys.argv[1]+'/build/audit/source/src'
 *   k=open(src+'/R8/KONBEA.C').read()
 *   k=k.replace('#include "../','#include "').replace('#include "KONBEA.H"\n','void konbea(sprite_status* pActwk);\n')
 *   k=re.sub(r'\(\((unsigned short|short)\*\)(\w+)\)\[(\d+)\]',lambda m:f'(*({m[1]}*)((char*)({m[2]})->actfree+{2*int(m[3])-46}))',k)
 *   assert '*)pActwk)[' not in k and '*)pNewact)[' not in k and '*)pMainwk)[' not in k
 *   p=open(src+'/PLAYSUB.C').read();b=p[p.index('void patchg(sprite_status* patchgwk'):]
 *   sys.stdout.write(k+'\n'+b[:b.index('\n}')+2]+'\n')
 *   EOF
 *   clang -std=gnu11 -O1 -g -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value \
 *    -Isrc -I$M/assets/generated -I$M/build/probe-source -DR1 -DR11A -fsanitize=address,undefined -fno-sanitize-recover=all \
 *    tools/object_konbea_test.c "$T/konbea_pc.c" src/title_card.c src/player_replay.c src/world.c src/act.c src/player.c \
 *    src/sonic_animation.c src/stage.c src/objects.c $M/build/probe-source/{interaction,player,dircol,fcol,etc,equ,movement}.c \
 *    -o "$T/object_konbea_test"
 *   "$T/object_konbea_test"
 */
#include "EQU.H"
#include "scd_actor.h"
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
#ifndef SCD_MAIN
#define SCD_MAIN "."
#endif
extern short scralim_left,scralim_right,scralim_down,scra_vline;

/* ---- The retail routine and the few services it calls. ------------------ */
void konbea(sprite_status *pActwk);
/* Native pool actors are actwk[1..96]; the retail copy lives above them. */
#define ORACLE_FIRST 100
int actwkchk(sprite_status **pp){
    for(unsigned i=ORACLE_FIRST;i<128;i++)if(!actwk[i].actno){*pp=&actwk[i];return 0;}
    return -1;
}
void actionsub(sprite_status *p){(void)p;}
void frameout(sprite_status *p){memset(p,0,sizeof(*p));}
int frameout_s00(sprite_status *p,short x){(void)p;(void)x;return 0;}
int frameout_s(sprite_status *p){(void)p;return 0;}
/* Sonic is parked out of reach (routine 6) on both sides of the parity run. */
short ridechk(sprite_status *a,sprite_status *p){(void)a;(void)p;return 0;}
short ride_on_clr(sprite_status *a,sprite_status *p){(void)a;(void)p;return 0;}

static int failures;
#define CHECK(cond,...) do{if(!(cond)){failures++;printf("FAIL %s:%d: ",__FILE__,__LINE__);printf(__VA_ARGS__);printf("\n");}}while(0)

/* R8/KONBEA.C:21-468, re-read here from the retail file for the expectations. */
static int8_t path[892];
static void load_path(void){
    FILE *f=fopen(SCD_MAIN "/build/audit/source/src/R8/KONBEA.C","r");
    if(!f){fprintf(stderr,"missing KONBEA.C\n");exit(2);}
    static char text[65536];size_t n=fread(text,1,sizeof(text)-1,f);fclose(f);text[n]=0;
    char *s=strstr(text,"char konbea8tbl[892] = {");if(!s)exit(2);s=strchr(s,'{')+1;
    for(unsigned i=0;i<892;i++){s+=strcspn(s,"-0123456789");path[i]=(int8_t)strtol(s,&s,10);}
}

/* ---- 1. Parity with the retail routine. --------------------------------- */
static unsigned word(const sprite_status *o,unsigned w){return scd_word_get(o,w);}
static int parity(unsigned sub,unsigned sec,unsigned flags,unsigned updates){
    /* KONBEA.C runs only in R8 (zone 6), through mm_zone_ops.konbea. */
    scd_objects_zone(6);
    scd_objects_reset(0,0);
    memset(&actwk[0],0,sizeof(actwk[0]));memset(&actwk[ORACLE_FIRST],0,sizeof(actwk[0])*(128-ORACLE_FIRST));
    actwk[0].actno=1;actwk[0].xposi.w.h=600;actwk[0].yposi.w.h=100;actwk[0].r_no0=6;
    const int x=1000,y=900;
    int index=scd_objects_spawn(SCD_OBJ_KONBEA,x,y,sub,flags);
    if(index!=0){printf("FAIL parity: spawn slot %d\n",index);return 1;}
    actwk[1].userflag.b.l=(char)sec; /* stream() writes the secondary after spawn_from */
    sprite_status *r=&actwk[ORACLE_FIRST];
    /* ACTSET.C:325-362: position, flip in actflg and cddat, subtype, secondary. */
    r->actno=42;r->xposi.w.h=x;r->yposi.w.h=y;r->actflg=flags;r->cddat=flags;r->userflag.b.h=sub;r->userflag.b.l=(char)sec;
    unsigned max_actors=0;
    for(unsigned u=1;u<=updates;u++){
        for(unsigned i=ORACLE_FIRST;i<128;i++)if(actwk[i].actno==42)konbea(&actwk[i]);
        scd_objects_step(600,100);
        unsigned actors=0;
        for(unsigned k=0;k<128-ORACLE_FIRST;k++){
            const sprite_status *a=&actwk[ORACLE_FIRST+k],*b=&actwk[1+k];
            int live_a=a->actno==42,live_b=b->actno==SCD_OBJ_KONBEA;
            if(live_a!=live_b){printf("FAIL parity sub=%u sec=%u flags=%u update=%u actor %u: retail %s, port %s\n",sub,sec,flags,u,k,live_a?"live":"gone",live_b?"live":"gone");return 1;}
            if(!live_a)continue;
            actors++;
            unsigned pa=word(a,23),pb=word(b,23);
            uint32_t ra[]={(uint16_t)a->xposi.w.h,(uint16_t)a->yposi.w.h,(uint16_t)a->xspeed.w,a->patno,a->patcnt,a->pattim,(uint16_t)a->mstno.w,a->r_no0,a->sprhsize,a->sprvsize,a->sprhs,a->sprpri,a->actflg&3,a->actfree[20],(uint8_t)a->userflag.b.h,(uint8_t)a->userflag.b.l,pa?pa-ORACLE_FIRST+1:0,word(a,24),word(a,25),word(a,26),word(a,27),word(a,28),word(a,29)};
            uint32_t rb[]={(uint16_t)b->xposi.w.h,(uint16_t)b->yposi.w.h,(uint16_t)b->xspeed.w,b->patno,b->patcnt,b->pattim,(uint16_t)b->mstno.w,b->r_no0,b->sprhsize,b->sprvsize,b->sprhs,b->sprpri,b->actflg&3,b->actfree[20],(uint8_t)b->userflag.b.h,(uint8_t)b->userflag.b.l,pb,word(b,24),word(b,25),word(b,26),word(b,27),word(b,28),word(b,29)};
            static const char *names[]={"x","y","xspeed","patno","patcnt","pattim","mstno","r_no0","sprhsize","sprvsize","sprhs","sprpri","actflg&3","actfree20","sub","sec","parent","w24","w25","w26","w27","w28","w29"};
            for(unsigned f=0;f<sizeof(ra)/sizeof(*ra);f++)if(ra[f]!=rb[f]){
                printf("FAIL parity sub=%u sec=%u flags=%u update=%u actor %u %s: retail %u port %u\n",sub,sec,flags,u,k,names[f],(unsigned)ra[f],(unsigned)rb[f]);return 1;
            }
        }
        if(actors>max_actors)max_actors=actors;
    }
    printf("parity sub=%u sec=%u flags=%u: %u updates, up to %u actors, every word equal to R8/KONBEA.C\n",sub,sec,flags,updates,max_actors);
    return 0;
}

/* ---- Stage helpers. ----------------------------------------------------- */
static uint8_t stage_data[300000],collision[9472];
static stage_t stage;
static size_t slurp(const char *path,uint8_t *out,size_t cap){
    FILE *f=fopen(path,"rb");if(!f){fprintf(stderr,"missing %s\n",path);exit(2);}
    size_t n=fread(out,1,cap,f);fclose(f);return n;
}
static void load_stage(char letter,unsigned era,int title_card){
    char a[160],b[160];
    snprintf(a,sizeof(a),SCD_MAIN "/assets/generated/mm81%c.bin",letter);
    snprintf(b,sizeof(b),SCD_MAIN "/assets/generated/mmcollision81%c.bin",letter);
    size_t size=slurp(a,stage_data,sizeof(stage_data));
    if(slurp(b,collision,sizeof(collision))!=sizeof(collision)){fprintf(stderr,"collision size\n");exit(2);}
    if(stage_open(&stage,stage_data,size)){fprintf(stderr,"stage_open %s\n",a);exit(2);}
    /* R8 is zone 6; Act 1 is act 0. */
    scd_player_zone(6);scd_objects_zone(6);
    scd_player_act(0);scd_objects_act(0);scd_world_act(0);
    if(scd_player_init(&stage,collision,sizeof(collision),era)){fprintf(stderr,"player init\n");exit(2);}
    scd_world_reset(era);
    if(title_card)scd_title_card_start(0);
}
static sprite_status *actor(int index){return &actwk[index+1];}
static int px(void){return actwk[0].xposi.w.h;}
static int py(void){return actwk[0].yposi.w.h;}
static int riding(int index){return (actwk[0].cddat&8) && actwk[0].actfree[19]==index+1;}

/* ---- 2a. Subtype 0: stand, flip, fall; top-solid only. ------------------ */
static void focused_flip(void){
    load_stage('A',0,0);
    /* The lower pit record, objects81A.bin record 8. */
    const int ox=487,oy=1916,stand=oy-5-19;
    int k=scd_objects_spawn(SCD_OBJ_KONBEA,ox,oy,0,0);CHECK(k>=0,"spawn");
    scd_player_place(ox,1850,0,0,2);
    int landed=0,release=0,stood=0,bad_y=0;
    static const uint8_t flip[23]={1,1,2,2,3,3,4,4,5,5,6,6,1,1,2,2,3,3,4,4,5,5,0};
    int flip_ok=1,solid_again=0;
    for(int u=1;u<=150;u++){
        scd_player_step(0);
        sprite_status *o=actor(k);
        if(riding(k)){if(!landed)landed=u;stood++;if(py()!=stand)bad_y++;}
        if(landed && !release && !riding(k) && u>landed)release=u;
        if(u>=122 && u<=144 && o->patno!=flip[u-122])flip_ok=0;
        if(u==144 && o->r_no0!=2)flip_ok=0;
        if(u==145)solid_again=o->r_no0==4 && o->sprvsize==5;
        if(u>=122 && u<=144 && riding(k))flip_ok=0;
    }
    printf("sub 0 at (%d,%d): landed update %d at y=%d (expected %d), stood %d updates, released update %d, y after flip %d\n",ox,oy,landed,stand,stand,stood,release,py());
    CHECK(landed>0 && landed<=40,"Sonic never landed on the platform");
    CHECK(!bad_y,"standing y off %d times",bad_y);
    /* KONBEA.C:701,717,723: a_stop sets 120 on update 2 and a_stop1 counts it to 0
       on update 121, carrying Sonic once more (ridechk) and then dropping him. */
    CHECK(release==121,"released on update %d, retail drops the rider on update 121",release);
    CHECK(stood==121-landed,"stood %d updates",stood);
    CHECK(flip_ok,"a_move pattern sequence / no collision while flipping");
    CHECK(solid_again,"a_stop did not restore sprvsize 5 on update 145");
    CHECK(py()>stand+40 && !(actwk[0].cddat&2),"Sonic did not fall to the pit floor (y=%d)",py());

    /* Jump from the pit floor: rise through the platform, land on its top. */
    load_stage('A',0,0);
    k=scd_objects_spawn(SCD_OBJ_KONBEA,ox,oy,0,0);
    scd_player_place(495,1955,0,0,2);
    for(int u=0;u<30;u++)scd_player_step(0);
    int floor_y=py(),min_y=py();landed=0;
    CHECK(!(actwk[0].cddat&2) && !riding(k),"not standing on the pit floor before the jump (y=%d)",floor_y);
    for(int u=0;u<80;u++){
        scd_player_step(u==0 || actwk[0].yspeed.w<0?SCD_JUMP:0);
        if(py()<min_y)min_y=py();
        if(!landed && riding(k))landed=u+1;
    }
    printf("sub 0 jump from floor y=%d: rose to y=%d through the platform, landed after %d updates at y=%d\n",floor_y,min_y,landed,py());
    CHECK(min_y<stand-20,"the platform blocked the rising jump (min y %d)",min_y);
    CHECK(landed && riding(k) && py()==stand,"did not land on top (y=%d)",py());

    /* Side approach: top-solid only (ridechk sets r_no1 = 1, so hit_x and hit_yu
       end in hit_e, RIDECHK.C:221,374-375,559-560). The R81A floor is flat at
       y=1676 over x=300..384. The platform sits level with Sonic's centre and
       6px above it: neither may stop him or pick him up. */
    for(int lift=0;lift<=6;lift+=6){
        load_stage('A',0,0);
        scd_player_place(300,1676,0x500,0,0);
        const int ox=340,oy=1676-lift;
        k=scd_objects_spawn(SCD_OBJ_KONBEA,ox,oy,0,0);
        int passed=0,stalls=0,prev=px(),rode=0;
        for(int u=1;u<=30 && !passed;u++){
            scd_player_step(SCD_RIGHT);
            if(px()>=ox+16+10)passed=u;
            if(px()<=prev)stalls++;
            if(riding(k))rode++;
            prev=px();
        }
        printf("sub 0 side approach, platform %dpx above Sonic's centre: cleared x=%d after %d updates, %d updates without progress, %d on top\n",lift,ox+26,passed,stalls,rode);
        CHECK(passed && !stalls && !rode,"a subtype 0 platform stopped or lifted Sonic from the side");
    }
}

/* ---- 2b. Subtype 1: carried along the top run, dropped at index 344. ---- */
static int path_clear(int hx,int hy){
    for(unsigned idx=100;idx<360;idx++){
        scd_player_place(hx+path[idx*2],hy+path[idx*2+1]-24,0,0,2);
        if(!scd_player_arrival_clear())return 0;
    }
    for(unsigned idx=344;idx<446+115;idx++){ /* the fall below the rolling run */
        scd_player_place(hx+path[(idx%446)*2],hy+path[(idx%446)*2+1]+40,0,0,2);
        if(!scd_player_arrival_clear())return 0;
    }
    return 1;
}
static void focused_conveyor(void){
    load_stage('A',0,0);
    int hx=-1,hy=-1;
    for(int y=200;y<1600 && hx<0;y+=40)for(int x=1200;x<7400 && hx<0;x+=40)if(path_clear(x,y)){hx=x;hy=y;}
    CHECK(hx>=0,"no terrain-free area for the conveyor");
    if(hx<0)return;
    load_stage('A',0,0);
    scd_player_place(hx,hy-300,0,0,2);
    int k=scd_objects_spawn(SCD_OBJ_KONBEA,hx,hy,1,0);
    actwk[0].r_no0=6; /* park Sonic for the init update */
    scd_objects_step(px(),py());
    /* KONBEA.C:835-851: four children at path index 89, 178, 267, 356. */
    int child=-1,count=0;
    for(int i=0;i<SCD_OBJECT_CAPACITY;i++)if(actwk[i+1].actno==SCD_OBJ_KONBEA){
        count++;if(i!=k && word(&actwk[i+1],28)==179)child=i;
    }
    printf("sub 1 at (%d,%d): %d actors after init\n",hx,hy,count);
    CHECK(count==5,"expected parent + 4 children, got %d",count);
    if(child<0){CHECK(0,"no child at path index 178");return;}
    sprite_status *o=actor(child);
    CHECK(o->xposi.w.h==hx+path[178*2] && o->yposi.w.h==hy+path[178*2+1],"child not at konbea8tbl[178]");
    /* Drop Sonic 2px above that platform. */
    scd_player_place(o->xposi.w.h,o->yposi.w.h-24-2,0,0,2);
    int landed=0,land_x=0,land_y=0,land_ox=0,release=0,bad=0,land_idx=0,release_x=0,release_y=0,release_idx=0;
    for(int u=2;u<=420;u++){
        scd_player_step(0);
        if(riding(child)){
            if(!landed){landed=u;land_x=px();land_y=py();land_ox=o->xposi.w.h;land_idx=(int)word(o,28)-1;}
            if(py()!=o->yposi.w.h-24 || px()-land_x!=o->xposi.w.h-land_ox)bad++;
        }else if(landed && !release){
            /* The last ridechk carried Sonic onto this update's position, then ride_on_clr. */
            release=u;release_x=px();release_y=py();release_idx=(int)word(o,28)-1;
            if(o->r_no0!=6 || release_x-land_x!=o->xposi.w.h-land_ox)bad++;
        }
        if(release && u>release && riding(child))bad++;
    }
    int carried_x=release_x-land_x,carried_y=release_y-land_y;
    int expect_x=path[343*2]-path[land_idx*2],expect_y=path[343*2+1]-path[land_idx*2+1];
    printf("sub 1 ride: landed update %d at path index %d, released update %d at index %d, carried %d px right and %d px down (expected %d and %d)\n",
           landed,land_idx,release,release_idx,carried_x,carried_y,expect_x,expect_y);
    CHECK(landed==2,"landed on update %d",landed);
    CHECK(!bad,"%d updates off the platform top or out of step with it",bad);
    /* The child showed index 178 on update 1, so index 343 on update 166, where
       b_stop1 sees word 28 = 344 and starts b_roll (KONBEA.C:896-903). */
    CHECK(release==166 && release_idx==343,"released on update %d at index %d (expected 166 at 343)",release,release_idx);
    CHECK(carried_x==expect_x && carried_y==expect_y,"carried (%d,%d), expected (%d,%d)",carried_x,carried_y,expect_x,expect_y);
    CHECK(o->r_no0==2 || o->r_no0==4 || o->r_no0==6,"routine %u",o->r_no0);
}

/* ---- 3. The sealed R81 pit, with the retail placements. -----------------
 * R81A-D share the pit: floor y=1983 at x=470..511, a step at y=1823 over
 * x=396..468 carrying retail record 6 (id 10 spring, subtype 2, x=440 y=1816),
 * and terrain at y=1695 on both sides above (x<=384 and x>=504). From the pit
 * floor or the upper konbea the only way up is the step and its spring, which
 * lies to the LEFT of a right-only walker. */
enum { WITH_KONBEA=1, WITH_SPRING=2 };
enum { TAP, HELD, HELD_ESCAPE };
typedef struct {int x,y;unsigned type,sub,sec,flags;int spawned;} record;
static unsigned load_records(char letter,unsigned era,unsigned with,record *out,unsigned cap){
    char name[160];snprintf(name,sizeof(name),SCD_MAIN "/build/auto-extract/8/objects81%c.bin",letter);
    static uint8_t bin[8192];size_t n=slurp(name,bin,sizeof(bin));
    unsigned era_bit=1u<<(era==0?1:era==1?0:2),count=0;
    /* ACTSET.C:275-362: x, y (bits 14-15 flip), a (bit 7 one-shot, id), b subtype, c>>5 eras, d secondary.
       R8/ACT81A.C act_tbl: id 42 = konbea, id 10 = spring (the port's SCD_OBJ_SPRING). */
    for(size_t i=0;i+8<=n && count<cap;i+=8){
        unsigned x=(bin[i]<<8)|bin[i+1],y=(bin[i+2]<<8)|bin[i+3],id=bin[i+4]&127,b=bin[i+5],c=bin[i+6],d=bin[i+7];
        unsigned type=id==42 && (with&WITH_KONBEA)?SCD_OBJ_KONBEA:id==10 && (with&WITH_SPRING)?SCD_OBJ_SPRING:0;
        if(!type || !((c>>5)&era_bit))continue;
        out[count++]=(record){(int)x,(int)(y&4095),type,b,d,(y>>14)&3,0};
    }
    return count;
}
/* tools/zone_walk_test.c's loop. TAP is the stock walker (Jump for one update).
   HELD keeps Jump down while Sonic rises. HELD_ESCAPE also steers Left for a
   jump that starts on a konbea, until Sonic lands again. */
static int walk(char letter,unsigned era,unsigned policy,unsigned with){
    load_stage(letter,era,1);
    record records[128];unsigned n=load_records(letter,era,with,records,128);
    scd_player_state p=scd_player_get();
    int max_x=p.x/65536,last_x=max_x,deaths=0,holding=0,left=0,escape_at=-1;
    unsigned stuck=0,jumps=0,updates,live=0,rides=0,left_jumps=0,springs=0;
    for(updates=0;updates<20000;updates++){
        /* src/objects.c stream(): a placement spawns inside 480 px of Sonic. */
        for(unsigned r=0;r<n;r++)if(!records[r].spawned && abs(records[r].x-px())<=480){
            int index=scd_objects_spawn(records[r].type,records[r].x,records[r].y,records[r].sub,records[r].flags);
            if(index>=0){actwk[index+1].userflag.b.l=(char)records[r].sec;records[r].spawned=1;live++;}
        }
        /* A left-steered jump ends when Sonic lands; he then walks right again. */
        if(left && !(p.flags&2)){left=0;stuck=0;}
        unsigned buttons=SCD_RIGHT;
        if(stuck>=30 && !(p.flags&2)){
            if(policy==HELD_ESCAPE && scd_objects_standing_type()==SCD_OBJ_KONBEA){left=1;left_jumps++;}
            buttons|=SCD_JUMP;jumps++;stuck=0;holding=policy!=TAP;
        }else if(holding && (p.flags&2) && p.vy<0)buttons|=SCD_JUMP;
        else holding=0;
        if(left)buttons=(buttons&~SCD_RIGHT)|SCD_LEFT;
        scd_player_hold_clock(scd_title_card_locked());
        /* The game's camera follows Sonic; MM springs act only on screen
           (SPRING.C:399-404), so centre a view on him. */
        {void scd_act_camera(int,int);scd_player_state c=scd_player_get();scd_act_camera(c.x/65536-160,c.y/65536-112);}
        scd_player_step(scd_title_card_locked()?0:buttons);
        scd_title_card_step();
        if(scd_objects_standing_type()==SCD_OBJ_KONBEA)rides++;
        p=scd_player_get();
        if(p.vy<=-2560)springs++; /* a jump starts at -1664; spring subtype 2 gives -2560 */
        int x=p.x/65536;
        if(x>last_x+1){stuck=0;last_x=x;}else stuck++;
        if(x>max_x){max_x=x;if(x>501 && escape_at<0)escape_at=(int)updates;}
        if(p.resets>(unsigned)deaths)deaths=(int)p.resets;
        if(x>=scralim_right)break;
    }
    printf("  R81%c era %u %-11s %-13s max_x=%-5d past 501 at update %-5d jumps %-4u left-steered %-3u spring-launch updates %-3u konbea-ride updates %-5u spawned %u deaths %d\n",
           letter,era,policy==TAP?"tapped":policy==HELD?"held":"held+escape",with==(WITH_KONBEA|WITH_SPRING)?"konbea+spring":with==WITH_KONBEA?"konbea":with==WITH_SPRING?"spring":"no objects",
           max_x,escape_at,jumps,left_jumps,springs,rides,live,deaths);
    return max_x;
}

int main(void){
    load_path();
    printf("== parity with R8/KONBEA.C\n");
    failures+=parity(0,0,0,1200);
    failures+=parity(1,0,0,1200);
    failures+=parity(0,0,1,400);
    failures+=parity(1,0,1,1000);
    failures+=parity(0,1,0,20);
    failures+=parity(1,1,0,20);
    printf("== focused, port player on R81A terrain\n");
    focused_flip();
    focused_conveyor();
    printf("== stall: the sealed pit at x=501 (R81A-D)\n");
    const int stall=501;
    for(unsigned era=0;era<4;era++){
        char letter=(char)('A'+era);
        int none=walk(letter,era,TAP,0);
        walk(letter,era,TAP,WITH_KONBEA);
        walk(letter,era,HELD,WITH_KONBEA);
        walk(letter,era,HELD,WITH_KONBEA|WITH_SPRING);
        int spring_only=walk(letter,era,HELD_ESCAPE,WITH_SPRING);
        int konbea_only=walk(letter,era,HELD_ESCAPE,WITH_KONBEA);
        int both=walk(letter,era,HELD_ESCAPE,WITH_KONBEA|WITH_SPRING);
        /* a2863fb (GetLevelBlock's blank base, retail R81C $2013C6) lets
           Sonic press up to 2 px further into the step (501-503). */
        CHECK(none>=stall && none<=stall+2,"R81%c: the stall moved (x=%d without objects)",letter,none);
        /* The pit floor is 160px under the step: nothing climbs out without konbea. */
        CHECK(spring_only<=stall+2,"R81%c escaped with the spring alone (x=%d)",letter,spring_only);
        CHECK(konbea_only<=stall+2,"R81%c escaped without the spring (x=%d)",letter,konbea_only);
        CHECK(both>stall+2,"R81%c still sealed with konbea and the spring (x=%d)",letter,both);
    }
    if(failures){printf("FAILED: %d checks\n",failures);return 1;}
    printf("PASS\n");
    return 0;
}
