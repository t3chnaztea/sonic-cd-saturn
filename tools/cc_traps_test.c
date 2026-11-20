/* Original TRAP_R3.C traps + RIDECHK.C geometry and COLI3.C hitboxes. */
#include "EQU.H"
#include "scd_actor.h"
#include "scd_objects.h"
#include "scd_player.h"
#include "sprite_order.h"
#include "act.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
void harir3(sprite_status*);void frdr3(sprite_status*);void trapdr3(sprite_status*);void getdair3(sprite_status*);
short pcol(sprite_status*);void playdamagechk(sprite_status*,sprite_status*);short playdieset(sprite_status*);
static unsigned kind,original_hits,fail_alloc;
static void (*routine)(sprite_status*);
int actwkchk(sprite_status **out){if(fail_alloc)return -1;for(unsigned i=100;i<128;i++)if(!actwk[i].actno){*out=&actwk[i];actwk[i].actflg=132;return 0;}return -1;}
int frameout_s(sprite_status *o){(void)o;return 0;}
void frameout(sprite_status *o){memset(o,0,sizeof(*o));}
int actwkchk2(sprite_status *o,sprite_status **out){if(fail_alloc)return -1;for(o++;o<actwk+128;o++)if(!o->actno){*out=o;return 0;}return -1;}
short playdamageset(sprite_status *p,sprite_status *o){original_hits++;if(plpower_b || plring){playdamagechk(p,o);return -1;}return playdieset(p);}
short pcolplay(sprite_status *p,sprite_status *o){return plpower_m || scd_word_get(p,26)?-1:playdamageset(p,o);}
short pcolnomal(sprite_status *p,sprite_status *o){(void)p;(void)o;abort();}
short pcolspecial(sprite_status *p,sprite_status *o){(void)p;(void)o;abort();}
short pcolitem(sprite_status *p,sprite_status *o){(void)p;(void)o;abort();}
void actionsub(sprite_status *o){if(o->actno)o->actflg|=128;}
void tr3_fout(sprite_status *o){(void)o;}
static unsigned checks,updates,contacts,subtype,frame;
#define REQUIRE(v) do{checks++;if(!(v)){fprintf(stderr,"FAIL kind %u sub %u frame %u line %d: %s\n",kind,subtype,frame,__LINE__,#v);exit(1);}}while(0)
static unsigned char data[300000],collision[9472];
static stage_t stage;
static size_t read_file(const char *name,unsigned char *buf,size_t cap){FILE *f=fopen(name,"rb");REQUIRE(f);size_t n=fread(buf,1,cap,f);fclose(f);return n;}
static void load(unsigned era){
    char path[128];snprintf(path,sizeof(path),"assets/generated/cc31%c.bin",'A'+era);
    size_t n=read_file(path,data,sizeof(data));REQUIRE(!stage_open(&stage,data,n));
    snprintf(path,sizeof(path),"assets/generated/cccollision31%c.bin",'A'+era);
    REQUIRE(read_file(path,collision,sizeof(collision))==sizeof(collision));
    scd_player_zone(1);scd_objects_zone(1);scd_player_act(0);scd_objects_act(0);
    REQUIRE(!scd_player_init(&stage,collision,sizeof(collision),era));
}
static void compare(sprite_status *a,sprite_status *b){
#define FIELD(f) REQUIRE(a->f==b->f)
    FIELD(xposi.l);FIELD(yposi.l);FIELD(xspeed.w);FIELD(yspeed.w);FIELD(r_no0);FIELD(r_no1);
    FIELD(actflg);FIELD(cddat);FIELD(sprhsize);FIELD(sprvsize);FIELD(sprpri);FIELD(patno);FIELD(colino);
    REQUIRE(!memcmp(a->actfree,b->actfree,sizeof(a->actfree)));
#undef FIELD
}
static void tick(sprite_status before){
    actwk[0]=before;if(actwk[0].actfree[19])actwk[0].actfree[19]+=99;
    if(actwk[0].colino)actwk[0].colino+=99;
    unsigned char shield=plpower_b;original_hits=0;
    if(actwk[0].r_no0<4)pcol(actwk);
    routine(&actwk[100]);
    if(actwk[101].actno==SCD_OBJ_HARIR3)harir3(&actwk[101]);
    if(actwk[101].actno==SCD_OBJ_SPRING){
        /* SPRING.C lines 406-412: signed child offsets, applied after contact.
           Spring impulses are separately covered by the existing spring gate. */
        actwk[101].xposi.w.h=actwk[100].xposi.w.h+(signed char)actwk[101].actfree[14];
        actwk[101].yposi.w.h=actwk[100].yposi.w.h+(signed char)actwk[101].actfree[15];
    }
    sprite_status expected=actwk[0];unsigned char expected_shield=plpower_b;plpower_b=shield;
    unsigned hits=scd_objects_get().hits;
    if(expected.actfree[19]>=100)expected.actfree[19]-=99;
    if(expected.colino>=100)expected.colino-=99;
    actwk[0]=before;scd_objects_step(before.xposi.w.h,before.yposi.w.h);
    compare(&actwk[1],&actwk[100]);REQUIRE(!memcmp(&actwk[0],&expected,sizeof(before)));
    REQUIRE(plpower_b==expected_shield);REQUIRE(scd_objects_get().hits-hits==original_hits);
    scd_object_view v;REQUIRE(scd_objects_views(&v,1)==1);
    REQUIRE(v.type==kind && v.frame==actwk[100].patno && v.flags==(actwk[100].actflg&3));
    REQUIRE(scd_ppz_priority(v)==actwk[100].sprpri);updates++;
    if(actwk[101].actno){
        REQUIRE(actwk[2].actno==actwk[101].actno);REQUIRE(scd_word_get(&actwk[2],28)==1);
        REQUIRE(actwk[2].xposi.l==actwk[101].xposi.l);REQUIRE(actwk[2].yposi.l==actwk[101].yposi.l);
        REQUIRE(actwk[2].actfree[14]==actwk[101].actfree[14]);REQUIRE(actwk[2].actfree[15]==actwk[101].actfree[15]);
    }
}
static sprite_status player(int x,int y,unsigned mode){
    sprite_status p={0};p.actno=1;p.r_no0=mode==3?4:2;p.xposi.w.h=x;p.yposi.w.h=y;
    p.sprvsize=mode==2?14:19;p.sprhs=9;p.cddat=mode==2?6:2;
    p.yspeed.w=mode==1?-300:300;p.xspeed.w=512;return p;
}
static void setup(unsigned era,unsigned flags){
    scd_objects_reset(era,0);memset(actwk,0,sizeof(*actwk));editmode.w=0;chibi_flag=0;
    memset(actwk+100,0,28*sizeof(*actwk));plpower_m=plpower_a=0;plpower_b=1;plring=0;
    REQUIRE(scd_objects_spawn(kind,1000,800,subtype,flags)==0);
    actwk[100]=actwk[1];
}
static void moving_solids(void){
    kind=SCD_OBJ_FRDR3;subtype=1;routine=frdr3;
    const int velocity[]={-768,-256,0,256,768};
    for(unsigned vx=0;vx<5;vx++)for(unsigned vy=0;vy<5;vy++)
    for(int dx=-27;dx<=27;dx++)for(int dy=-38;dy<=38;dy++)for(unsigned mode=0;mode<4;mode++){
        setup(0,0);frame=0;tick(player(200,100,0));
        actwk[1].xspeed.w=actwk[100].xspeed.w=velocity[vx];
        actwk[1].yspeed.w=actwk[100].yspeed.w=velocity[vy];
        frame=1;tick(player(1000+dx,800+dy,mode));contacts++;
    }
}
static void linked_lifetime(void){
    for(unsigned type=SCD_OBJ_FRDR3;type<=SCD_OBJ_TRAPDR3;type++)for(unsigned sub=1;sub<=3;sub++){
        if(type==SCD_OBJ_FRDR3 && sub==1)continue;
        /* Collection keeps the earlier ring slot for its sparkle. The trap
           child still allocates after its parent during this update. */
        scd_objects_reset(0,0);actwk[0]=player(200,100,0);
        REQUIRE(scd_objects_spawn(SCD_OBJ_RING,200,100,0,0)==0);
        REQUIRE(scd_objects_spawn(type,1000,800,sub,0)==1);
        scd_objects_step(200,100);
        REQUIRE(actwk[1].actno==SCD_OBJ_RING);REQUIRE(actwk[2].actno==type);
        REQUIRE(actwk[3].actno==(type==SCD_OBJ_TRAPDR3 && sub==1?SCD_OBJ_HARIR3:SCD_OBJ_SPRING));
        REQUIRE(scd_word_get(&actwk[3],28)==2);
        scd_objects_clear_live();REQUIRE(scd_objects_get().active==0);
        /* Streaming removal recursively clears the child and rider/push state. */
        scd_placement placement={1000,800,type,sub,0,7,0};
        scd_objects_layout(&placement,1);scd_objects_reset(0,1);actwk[0]=player(1000,700,0);
        /* Collision Chaos streams through the retail Object Spawner: the camera
           window, not the player distance, loads and frames out the record. */
        scd_act_camera(840,588);
        scd_objects_step(1000,700);REQUIRE(scd_objects_get().active==2);
        actwk[1].cddat|=32;actwk[0].cddat|=32;actwk[0].xposi.w.h=5000;
        scd_act_camera(4840,588);scd_objects_step(5000,700);REQUIRE(scd_objects_get().active==0);REQUIRE(!(actwk[0].cddat&32));
        scd_objects_layout(NULL,0);
    }
    /* Allocation failure deletes a spring platform, but leaves a trap floor. */
    for(unsigned type=SCD_OBJ_FRDR3;type<=SCD_OBJ_TRAPDR3;type++){
        scd_objects_reset(0,0);actwk[0]=player(200,100,0);
        for(unsigned n=0;n<SCD_OBJECT_CAPACITY-1;n++)REQUIRE(scd_objects_spawn(SCD_OBJ_RING,2000,800,0,0)==(int)n);
        REQUIRE(scd_objects_spawn(type,1000,800,2,0)==SCD_OBJECT_CAPACITY-1);
        fail_alloc=1;memset(actwk+100,0,28*sizeof(*actwk));actwk[100]=actwk[SCD_OBJECT_CAPACITY];
        if(type==SCD_OBJ_FRDR3)frdr3(&actwk[100]);else trapdr3(&actwk[100]);
        scd_objects_step(200,100);fail_alloc=0;
        REQUIRE(actwk[SCD_OBJECT_CAPACITY].actno==actwk[100].actno);
        REQUIRE(scd_objects_get().active==(type==SCD_OBJ_FRDR3?SCD_OBJECT_CAPACITY-1:SCD_OBJECT_CAPACITY));
    }
    scd_objects_reset(0,0);
}
int main(void){
    void (*routines[])(sprite_status*)={harir3,frdr3,trapdr3,getdair3};
    unsigned types[]={SCD_OBJ_HARIR3,SCD_OBJ_FRDR3,SCD_OBJ_TRAPDR3,SCD_OBJ_GETDAIR3};
    unsigned counts[]={8,4,8,6};
    for(unsigned era=0;era<4;era++){
        load(era);
        for(unsigned family=0;family<4;family++){
            kind=types[family];routine=routines[family];
            for(unsigned s=0;s<counts[family];s++){
                subtype=family==3?(s%3)|((s/3)*128):s;
                for(unsigned flags=0;flags<4;flags++){
                    setup(era,flags);
                    for(frame=0;frame<800;frame++){
                        sprite_status p=player(actwk[1].xposi.w.h+(frame%160<80?-120:120),actwk[1].yposi.w.h+(frame%240<120?-60:60),0);
                        tick(p);
                    }
                }
                /* Avoid child contact in these parent geometry fixtures; child
                   allocation and following are exercised in the long runs. */
                if((kind==SCD_OBJ_FRDR3 && subtype>=2) || (kind==SCD_OBJ_TRAPDR3 && (subtype&3)))continue;
                for(int dx=-43;dx<=43;dx++)for(int dy=-40;dy<=40;dy++)for(unsigned mode=0;mode<4;mode++){
                    setup(era,0);frame=0;tick(player(200,100,0));
                    frame=1;tick(player(1000+dx,800+dy,mode));contacts++;
                }
            }
        }
    }
    load(0);moving_solids();linked_lifetime();
    printf("PASS: %u assertions; %u original/native updates; %u contact cases\n",checks,updates,contacts);
    return 0;
}
