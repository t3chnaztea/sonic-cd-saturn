/* Compiled R3/SIKAKE33.C (ROLLPLAT.C, LIGHT.C, STOPPER.C, PLAYSUB.C patchg,
   RIDECHK.C) versus the native Collision Chaos Act 3 actor.

   The original runs in its own copy of actwk. Its actwkchk stub takes the
   lowest free actor, the native pool's order, so link words compare
   directly. Its actionsub stub is empty: the visibility bit the retail
   sprite pass would publish is copied from the native actor before each
   original update. Spawns follow the retail Object Spawner walk (objects.c
   tt_stream) and frameout_s the FRAMEOUT_S camera window, tested before
   dispatch as the native loop does. 200 runs per subtype keep the stopper
   open/close coverage now that hidden-camera holds frame the kaitenban out. */
#include "EQU.H"
#include "scd_objects.h"
#include "scd_player.h"
#include "sprite_order.h"
#include "act.h"
#include "scd_actor.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
void sikake33(sprite_status*);
#define SLOTS (SCD_OBJECT_CAPACITY+1)
#define RETAIL_ID 54
static unsigned checks,frames,era,seed,frame,sub;
static unsigned lights,opens,closes,launches,rides,orphans,hidden,respawns;
#define REQUIRE(v) do{checks++;if(!(v)){fprintf(stderr,"FAIL era %c sub %u seed %u frame %u line %d: %s\n","ABCD"[era],sub,seed,frame,__LINE__,#v);exit(1);}}while(0)
static sprite_status original[SLOTS],native[SLOTS];
void actionsub(sprite_status *o){(void)o;}
/* Native remove_slot releases a player standing on the removed actor
   (objects.c release_rider), a port-wide rule for every deleted object. */
void frameout(sprite_status *o){
    sprite_status *p=&actwk[0];
    if((p->cddat&8) && p->actfree[19]==(unsigned)(o-actwk)){
        p->cddat=(p->cddat&~8)|2;p->actfree[19]=0;p->actfree[14]=0;p->actfree[0]=0;
    }
    memset(o,0,sizeof(*o));
}
int frameout_s(sprite_status *o){(void)o;return 0;}
int actwkchk(sprite_status **out){
    for(unsigned i=1;i<SLOTS;i++)if(!actwk[i].actno){memset(&actwk[i],0,sizeof(actwk[i]));*out=&actwk[i];return 0;}
    return -1;
}
static unsigned char data[300000],collision[9472];
static stage_t stage;
static size_t read_file(const char *name,unsigned char *buf,size_t cap){FILE *f=fopen(name,"rb");REQUIRE(f);size_t n=fread(buf,1,cap,f);fclose(f);return n;}
static void load(void){
    char path[128];snprintf(path,sizeof(path),"assets/generated/cc33%c.bin","ABCD"[era]);
    size_t n=read_file(path,data,sizeof(data));REQUIRE(!stage_open(&stage,data,n));
    snprintf(path,sizeof(path),"assets/generated/cccollision33%c.bin","ABCD"[era]);
    REQUIRE(read_file(path,collision,sizeof(collision))==sizeof(collision));
    scd_player_zone(1);scd_objects_zone(1);scd_player_act(2);scd_objects_act(2);
}
static unsigned rng(void){seed=seed*1103515245u+12345u;return (seed>>16)&32767;}
static void compare(void){
    for(unsigned i=1;i<SLOTS;i++){
        sprite_status *a=&actwk[i],*b=&original[i];
        REQUIRE((a->actno==SCD_OBJ_SIKAKE33)==(b->actno==RETAIL_ID));
        REQUIRE(a->actno==SCD_OBJ_SIKAKE33 || !a->actno);
        if(!b->actno)continue;
        if(memcmp(a->actfree,b->actfree,sizeof(a->actfree)))for(unsigned k=0;k<sizeof(a->actfree);k++)
            if(a->actfree[k]!=b->actfree[k])fprintf(stderr,"slot %u actfree[%u] native=%u original=%u\n",i,k,a->actfree[k],b->actfree[k]);
#define FIELD(f) REQUIRE(a->f==b->f)
        FIELD(xposi.l);FIELD(yposi.l);FIELD(xspeed.w);FIELD(yspeed.w);FIELD(userflag.w);
        FIELD(r_no0);FIELD(r_no1);FIELD(cddat);FIELD(sprhsize);FIELD(sprvsize);FIELD(sprpri);
        FIELD(patno);FIELD(mstno.w);FIELD(patcnt);FIELD(pattim);
        REQUIRE((a->actflg&127)==(b->actflg&127));
        REQUIRE(!memcmp(a->actfree,b->actfree,sizeof(a->actfree)));
#undef FIELD
    }
}
/* objects.c tt_stream (SpawnObjects_Init/Forward/Backward) for a layout
   holding only the record at X 896. Returns 1 when it spawns the record. */
static int sp_ready,sp_right,sp_left;static short sp_prev;
static int spawner_walk(short view){
    const short x=896;short chunk=(short)(view&-128);
    if(!sp_ready){
        sp_ready=1;short d6=(short)(view-128);if(d6<0)d6=0;d6&=-128;
        sp_right=(unsigned short)x<(unsigned short)d6;
        d6-=128;sp_left=d6>=0 && (unsigned short)x<(unsigned short)d6;sp_prev=-1;
    }
    if(chunk==sp_prev)return 0;
    int spawn=0;
    if(chunk>sp_prev){
        sp_prev=chunk;short limit=(short)(chunk+640);
        if(!sp_right && (unsigned short)x<(unsigned short)limit){spawn=1;sp_right=1;}
        short d6=(short)(chunk-128);
        if(d6>=0 && !sp_left && (unsigned short)x<(unsigned short)d6)sp_left=1;
    }else{
        sp_prev=chunk;short d6=(short)(chunk-128);
        if(d6>=0 && sp_left && !(x<=d6)){spawn=1;sp_left=0;}
        d6=(short)(chunk+640);
        if(sp_right && !(x<d6))sp_right=0;
    }
    return spawn;
}
/* One update of both implementations from the same player input. */
static void tick(sprite_status player){
    int old_x=actwk[0].xposi.w.h,old_y=actwk[0].yposi.w.h;
    memcpy(native,actwk,sizeof(native));
    memcpy(actwk,original,sizeof(original));actwk[0]=player;
    for(unsigned i=1;i<SLOTS;i++)if(actwk[i].actno==RETAIL_ID)
        actwk[i].actflg=(actwk[i].actflg&127)|(native[i].actflg&128);
    /* Level/Object Spawner.asm for the one record (objects.c tt_stream): a
       cleared actor with the record's id, position and subtype. */
    if(spawner_walk((short)scd_act_view_x())){
        for(unsigned i=1;i<SLOTS;i++)if(!actwk[i].actno){
            sprite_status *o=&actwk[i];memset(o,0,sizeof(*o));o->actno=RETAIL_ID;
            o->xposi.w.h=896;o->yposi.w.h=1104;o->userflag.b.h=(char)sub;
            o->actflg=native[i].actflg&128;respawns++;break;
        }
    }
    unsigned before_r[SLOTS];for(unsigned i=0;i<SLOTS;i++)before_r[i]=actwk[i].r_no0;
    for(unsigned i=1;i<SLOTS;i++)if(actwk[i].actno==RETAIL_ID){
        /* ROLLPLAT.C frameout_s (FRAMEOUT_S): the kaitenban's X column leaves
           [chunk(camera-128), +640]; the native loop tests it before dispatch. */
        if((int8_t)actwk[i].userflag.b.h<0){
            short h=(short)((scd_act_view_x()-128)&-128);
            if((unsigned short)(short)((actwk[i].xposi.w.h&-128)-h)>640){frameout(&actwk[i]);continue;}
        }
        int was_stopper=(int8_t)actwk[i].userflag.b.h>0,live_parent=actwk[scd_word_get(&actwk[i],29)].actno==RETAIL_ID;
        sikake33(&actwk[i]);
        if(was_stopper && !live_parent)orphans++;
    }
    sprite_status expected=actwk[0];
    for(unsigned i=1;i<SLOTS;i++){
        sprite_status *o=&actwk[i];if(o->actno!=RETAIL_ID)continue;
        if(!before_r[i] && !o->userflag.b.h)lights++;
        if(before_r[i]!=8 && o->r_no0==8){if(o->mstno.b.h)closes++;else opens++;}
    }
    memcpy(original,actwk,sizeof(original));
    memcpy(actwk,native,sizeof(native));actwk[0]=player;
    gametimer.w++;
    scd_objects_step(old_x,old_y);
    if(memcmp(&actwk[0],&expected,sizeof(expected)))fprintf(stderr,"player expected xy=%d,%d ys=%d flags=%u ride=%u r=%u actual xy=%d,%d ys=%d flags=%u ride=%u r=%u\n",
        expected.xposi.w.h,expected.yposi.w.h,expected.yspeed.w,expected.cddat,expected.actfree[19],expected.r_no0,
        actwk[0].xposi.w.h,actwk[0].yposi.w.h,actwk[0].yspeed.w,actwk[0].cddat,actwk[0].actfree[19],actwk[0].r_no0);
    REQUIRE(!memcmp(&actwk[0],&expected,sizeof(expected)));
    compare();
    if(player.yspeed.w!=-1024 && actwk[0].yspeed.w==-1024)launches++;
    if(actwk[0].cddat&8)rides++;
    frames++;
}
/* Player modes from the drum fixture: standing, upward, rolling, hurt,
   object control, spin dash, twirl, riding, still. */
static void player_mode(sprite_status *p,unsigned mode){
    p->r_no0=mode==3?4+2*(rng()&1):2;p->sprvsize=mode==2?14:19;p->sprhs=9;
    p->cddat=(p->cddat&8)|(mode==2?6:2);
    p->yspeed.w=mode==1?-(int)(rng()%1200)-1:mode==8?0:(int)(rng()%1200);
    p->xspeed.w=(int16_t)((int)(rng()%1025)-512);
    p->actfree[2]=mode==4?64:0;p->mstno.b.h=mode==5?23:mode==6?43:0;
    if(mode==7){p->cddat|=8;p->yspeed.w=0;}
}
int main(void){
    for(era=2;era<4;era++){
        load();
        static const uint8_t subs[2]={254,255};
        for(unsigned s=0;s<2;s++)for(unsigned run=0;run<200;run++){
            sub=subs[s];seed=run*977u+era*31u+s;
            REQUIRE(!scd_player_init(&stage,collision,sizeof(collision),era));
            chibi_flag=0;editmode.w=0;
            static scd_placement layout[1];
            layout[0]=(scd_placement){896,1104,SCD_OBJ_SIKAKE33,(uint8_t)sub,0,7,0};
            scd_objects_layout(layout,1);scd_objects_reset(era,1);sp_ready=0;
            memset(original,0,sizeof(original));
            sprite_status p=actwk[0];
            unsigned region=0,hold=0,mode=0;int dx=0,dy=0;
            for(frame=0;frame<3000;frame++){
                if(!hold){
                    hold=1+rng()%(rng()&1?12:170);
                    unsigned r=rng()%32;
                    region=r<10?0:r<21?1:r<29?2:r<31?3:4;
                    dx=(int)(rng()%45)-22;dy=(int)(rng()%45)-22;mode=rng()%9;
                    if(region==2){dx=(int)(rng()%71)-35;dy=(int)(rng()%40)-34;}
                    if(rng()%9==0){scd_act_camera(rng()&1?2200:-200,1080);hidden++;}else scd_act_camera(736,1080);
                }
                hold--;
                p=actwk[0];player_mode(&p,mode);
                if(region==0){p.xposi.w.h=896+dx;p.yposi.w.h=1104+dy;}
                else if(region==1){p.xposi.w.h=896+(dx<0?-60:60);p.yposi.w.h=1104+dy;}
                else if(region==2){p.xposi.w.h=896+dx;p.yposi.w.h=1272-8-p.sprvsize+dy;}
                else if(region==3){p.xposi.w.h=896+dx/2;p.yposi.w.h=1104+(dy<0?-30:30);}
                else {p.xposi.w.h=1700;p.yposi.w.h=1100;}
                tick(p);
            }
        }
    }
    REQUIRE(lights>500 && opens>100 && closes>100 && launches>100 && orphans>10 && respawns>10);
    printf("PASS: %u assertions; %u updates; %u lights; %u opens; %u closes; %u launches; %u ridden; %u orphan deletions; %u respawns; %u hidden-camera holds across eras C/D and subtypes 254/255\n",
           checks,frames,lights,opens,closes,launches,rides,orphans,respawns,hidden);
}
