/* Compiled R4 originals versus objects_tt_platforms.inc. Two complete actor
   worlds (retail actwk[] layout and native pool + actwk[]) run the same
   player through the same ticks; every live actor, the player and the
   drawn-sprite set must match after each tick. Retail actwkchk starts at
   actwk[32], so both worlds hold inert fillers in actors 2-31 and children
   land in the same actor indices. tools/test-tt-platforms.sh builds it. */
#include "EQU.H"
#include "scd_objects.h"
#include "scd_player.h"
#include "act.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "placements.h"

size_t scd_tp_state_size(void);
extern int scd_tp_inert_children;
void scd_tp_state_save(uint8_t*);
void scd_tp_state_load(const uint8_t*);
void udblk4(sprite_status*);void lrblk4(sprite_status*);void rblk4(sprite_status*);void escal4(sprite_status*);
void brunko4(sprite_status*);void renketu4(sprite_status*);void kuzure4(sprite_status*);void daid4(sprite_status*);
void baneiwa(sprite_status*);void sw4(sprite_status*);void swblkr4(sprite_status*);void switchr4(sprite_status*);
void swgun4(sprite_status*);void ring4(sprite_status*);void tensu4(sprite_status*);void tobira4(sprite_status*);
void tobiras4(sprite_status*);void walls(sprite_status*);void wall42(sprite_status*);void tekkyu(sprite_status*);
void tekkyu4(sprite_status*);void tekkyu1(sprite_status*);void harir4(sprite_status*);
void playdamagechk(sprite_status*,sprite_status*);short playdieset(sprite_status*);short pcol(sprite_status*);
void plairset(void){abort();}
static sprite_status coli_before;static unsigned coli_player,coli_actor;

static unsigned checks,cases,ticks,contacts,rides,releases,pushes,spawns,removals,draws,spike_compares,spike_linked,spike_contacts,spike_hits;
static unsigned cur_case;static int cur_frame;static const char *phase="";
#define REQUIRE(v) do{checks++;if(!(v)){fprintf(stderr,"FAIL case %u (%s) frame %d line %d: %s\n",cur_case,phase,cur_frame,__LINE__,#v);exit(1);}}while(0)

/* ---- retail helpers (ACTION.C, ACTSET.C, SCORE.C, RING.C) ---- */
static unsigned char drawn[128];
void actionsub(sprite_status *o){
    drawn[o-actwk]=1;
    o->actflg&=127;
    int16_t x=o->xposi.w.h-scd_act_view_x(),y=o->yposi.w.h;
    int cy=scd_act_view_y();
    if(x+o->sprhsize<0 || x-o->sprhsize>=320)return;
    if((uint16_t)cy<256){if((uint16_t)y>=2048)y-=2048;}
    else if((uint16_t)cy>=1792 && (uint16_t)y<256)y+=2048;
    y-=cy;if(y+o->sprvsize<0 || y-o->sprvsize>=224)return;
    o->actflg|=128;
}
void frameout(sprite_status *o){memset(o,0,sizeof(*o));}
int actwkchk(sprite_status **pp){
    for(int i=32;i<128;i++)if(!actwk[i].actno){*pp=&actwk[i];return 0;}
    return -1;
}
int actwkchk2(sprite_status *o,sprite_status **pp){
    for(sprite_status *n=o+1;n<=&actwk[127];n++)if(!n->actno){*pp=n;return 0;}
    return -1;
}
int frameout_s0(sprite_status *o){
    unsigned short index=o->cdsts;
    if(index){
        index*=3;short t=time_flag&127;
        if(time_flag&128){t-=time_item;if(t<0)t=0;else if(t>=3)t=2;}
        flagwork[index+t]&=127;
    }
    frameout(o);return -1;
}
int frameout_s00(sprite_status *o,short x){
    if(o->actflg&128){if(!(time_flag&128))return 0;}
    else{
        x&=-128;short h=scra_h_posit.w.h;h-=128;h&=-128;x-=h;
        if((unsigned short)x<=640 && !(time_flag&128))return 0;
    }
    return frameout_s0(o);
}
int frameout_s(sprite_status *o){return frameout_s00(o,o->xposi.w.h);}
void scoreup(unsigned int n){(void)n;}
/* src/water.c is not linked here; awa children stay inert. */
__attribute__((weak)) void water_air_refill(void){}
void ringgetsub(void){}
/* COLI4.C playdamageset without the lost-ring actor (tools/tt_actor_fixture.h). */
short playdamageset(sprite_status *p,sprite_status *o){if(plpower_b || plring){playdamagechk(p,o);return -1;}return playdieset(p);}

/* R4 act number <-> native type. */
static const struct{unsigned char r4,type;}actmap[]={
    {32,SCD_OBJ_AWA},{34,SCD_OBJ_HARIR4},{35,SCD_OBJ_UDBLK4},{36,SCD_OBJ_LRBLK4},{37,SCD_OBJ_TOBIRAS4},{38,SCD_OBJ_ESCAL4},
    {39,SCD_OBJ_SW4},{40,SCD_OBJ_TOBIRA4},{41,SCD_OBJ_BRUNKO4},{48,SCD_OBJ_SWBLKR4},{49,SCD_OBJ_SWITCHR4},{51,SCD_OBJ_WALLS},
    {54,SCD_OBJ_TEKKYU},{55,SCD_OBJ_TEKKYU1},{56,SCD_OBJ_TEKKYU4},{57,SCD_OBJ_KUZURE4},{61,SCD_OBJ_RBLK4},{62,SCD_OBJ_RENKETU4},
    {63,SCD_OBJ_SWGUN4},{64,SCD_OBJ_RING4},{65,SCD_OBJ_TENSU4},{70,SCD_OBJ_WALL42},{72,SCD_OBJ_BANEIWA},{73,SCD_OBJ_DAID4},
    {200,SCD_OBJ_LOG_SHADOW}};
static unsigned r4_of(unsigned type){for(unsigned i=0;i<sizeof(actmap)/sizeof(*actmap);i++)if(actmap[i].type==type)return actmap[i].r4;return 0;}
static void orig_tick(void){
    for(int k=1;k<128;k++){
        sprite_status *o=&actwk[k];
        switch(o->actno){
        case 35:udblk4(o);break;case 36:lrblk4(o);break;case 37:tobiras4(o);break;case 38:escal4(o);break;
        case 39:sw4(o);break;case 40:tobira4(o);break;case 41:brunko4(o);break;case 48:swblkr4(o);break;
        case 49:switchr4(o);break;case 51:walls(o);break;case 54:tekkyu(o);break;case 55:tekkyu1(o);break;
        case 56:tekkyu4(o);break;case 57:kuzure4(o);break;case 61:rblk4(o);break;case 62:renketu4(o);break;
        case 63:swgun4(o);break;case 64:ring4(o);break;case 65:tensu4(o);break;case 70:wall42(o);break;
        case 72:baneiwa(o);break;case 73:daid4(o);break;case 34:harir4(o);break;
        }
    }
}

/* ---- the two worlds ---- */
typedef struct{sprite_status a[128];unsigned char sw[32],fw[766];}oworld;
typedef struct{sprite_status a[128];unsigned char sw[32];uint8_t *state;}nworld;
static size_t state_size;
static void nw_alloc(nworld *w){w->state=malloc(state_size);}
static void nw_copy(nworld *d,const nworld *s){uint8_t *st=d->state;memcpy(d,s,sizeof(*d));d->state=st;memcpy(st,s->state,state_size);}
static oworld O,O0;static nworld N,N0;
static int tt_views(void){
    static scd_object_view v[256];unsigned n=scd_objects_views(v,256),c=0;
    for(unsigned i=0;i<n;i++)if(r4_of(v[i].type) && v[i].type!=SCD_OBJ_LOG_SHADOW && v[i].type!=SCD_OBJ_AWA)c++;
    return (int)c;
}
static void player_diff(const sprite_status *a,const sprite_status *b){
    const unsigned char *x=(const void*)a,*y=(const void*)b;
    for(unsigned i=0;i<sizeof(*a);i++)if(x[i]!=y[i])fprintf(stderr,"player byte %u original %u native %u\n",i,x[i],y[i]);
    fprintf(stderr,"player original xy=%d,%d cddat=%u ride=%u colino=%u native xy=%d,%d cddat=%u ride=%u colino=%u case type %u sub %u\n",
        a->xposi.w.h,a->yposi.w.h,a->cddat,a->actfree[19],a->colino,b->xposi.w.h,b->yposi.w.h,b->cddat,b->actfree[19],b->colino,placements[cur_case].type,placements[cur_case].sub);
}
static void compare(void){
    if(memcmp(&O.a[0],&N.a[0],sizeof(sprite_status)))player_diff(&O.a[0],&N.a[0]);
    REQUIRE(!memcmp(&O.a[0],&N.a[0],sizeof(sprite_status)));
    REQUIRE(!memcmp(O.sw,N.sw,32));
    for(int k=1;k<128;k++){
        if(k>=2 && k<32)continue;
        if(k==32 && N.a[32].actno==SCD_OBJ_WAVE && O.a[32].actno==250)continue;
        sprite_status *a=&O.a[k],*b=&N.a[k];
        if(a->actno!=r4_of(b->actno) || (!a->actno)!=(!b->actno))
            fprintf(stderr,"actor %d: original actno %u native %u (r4 %u)\n",k,a->actno,b->actno,r4_of(b->actno));
        REQUIRE(a->actno==r4_of(b->actno) && (!a->actno)==(!b->actno));
        if(!a->actno)continue;
        /* awa children belong to the water port: compare their spawn fields only.
           harir4 children (UDBLK4 spikes, SWGUN4 drops) run HARIR4.C live. */
        if(a->actno==34){spike_compares++;if(a->actfree[10]|a->actfree[11])spike_linked++;}
        if(a->actno==32){REQUIRE(a->yposi.w.h==b->yposi.w.h && !memcmp(a->actfree,b->actfree,sizeof(a->actfree)));REQUIRE(a->xposi.w.h==b->xposi.w.h);continue;}
#define F(f) if(a->f!=b->f){fprintf(stderr,"actor %d type %u field %s original %ld native %ld\n",k,a->actno,#f,(long)a->f,(long)b->f);REQUIRE(a->f==b->f);}
        F(r_no0)F(r_no1)F(actflg)F(cddat)F(xposi.l)F(yposi.l)F(xspeed.w)F(yspeed.w)F(sprhsize)F(sprvsize)F(sprhs)
        F(sprpri)F(patno)F(userflag.w)F(colino)F(mstno.w)F(patcnt)F(pattim)F(sproffset)F(direc.w)F(mspeed.w)
#undef F
        if(memcmp(a->actfree,b->actfree,sizeof(a->actfree)))for(unsigned i=0;i<sizeof(a->actfree);i++)
            if(a->actfree[i]!=b->actfree[i])fprintf(stderr,"actor %d type %u actfree[%u] original %u native %u\n",k,a->actno,i,a->actfree[i],b->actfree[i]);
        REQUIRE(!memcmp(a->actfree,b->actfree,sizeof(a->actfree)));
    }
}
static unsigned char nw_live[128];
static void tick(sprite_status player,int remove_awa){
    int vx=scd_act_view_x();
    /* retail */
    memcpy(actwk,O.a,sizeof(O.a));actwk[0]=player;memcpy(switchflag,O.sw,32);memcpy(flagwork,O.fw,766);
    scra_h_posit.w.h=(short)vx;pltime.b.b3=(char)(scd_player_get().elapsed/60%60);
    memset(drawn,0,sizeof(drawn));
    /* PLAYER.C runs COLI4.C pcol before the object pass. */
    if(!(player.cddat&2))emyscorecnt=0;
    if(player.r_no0<4){coli_before=actwk[0];pcol(actwk);if(memcmp(&coli_before,&actwk[0],sizeof(coli_before)))coli_player++;}
    for(int k=1;k<128;k++)if(actwk[k].colino!=O.a[k].colino || actwk[k].r_no0!=O.a[k].r_no0 || actwk[k].colicnt!=O.a[k].colicnt)coli_actor++;
    orig_tick();
    memcpy(O.a,actwk,sizeof(O.a));memcpy(O.sw,switchflag,32);memcpy(O.fw,flagwork,766);
    int odrawn=0;for(int k=1;k<128;k++)if(drawn[k] && O.a[k].actno && O.a[k].actno!=32)odrawn++;
    /* native */
    memcpy(actwk,N.a,sizeof(N.a));actwk[0]=player;memcpy(switchflag,N.sw,32);scd_tp_state_load(N.state);
    /* COLI4: native tt_enemy_scan runs inside scd_objects_step. */
    scd_objects_step(player.xposi.w.h,player.yposi.w.h);
    int ndrawn=tt_views();
    memcpy(N.a,actwk,sizeof(N.a));memcpy(N.sw,switchflag,32);scd_tp_state_save(N.state);
    ticks++;
    for(int k=32;k<128;k++){if(O.a[k].actno && !nw_live[k])spawns++;if(!O.a[k].actno && nw_live[k])removals++;nw_live[k]=O.a[k].actno!=0;}
    if(odrawn!=ndrawn)fprintf(stderr,"drawn original %d native %d\n",odrawn,ndrawn);
    compare();REQUIRE(odrawn==ndrawn);draws+=odrawn;
    if(O.a[0].cddat&32)pushes++;
    if(remove_awa)(void)0;
}
static sprite_status make_player(int x,int y,unsigned mode,int xs,unsigned actor){
    sprite_status p={0};p.actno=1;p.r_no0=mode==3?6:2;
    p.xposi.w.h=x;p.yposi.w.h=y;p.sprvsize=mode==2?14:19;p.sprhs=9;p.sprhsize=9;
    p.cddat=mode==2?6:2;p.yspeed.w=mode==1?-300:mode==8?0:300;p.xspeed.w=xs;p.mspeed.w=xs;
    if(mode==4)p.actfree[2]=64;
    if(mode==5)p.mstno.b.h=23;
    if(mode==6)p.mstno.b.h=43;
    if(mode==7){p.cddat=8;p.actfree[19]=actor;p.yspeed.w=0;}
    return p;
}
static stage_t stage;static unsigned char data[400000],collision[16384];
static size_t read_file(const char *name,unsigned char *buf,size_t cap){FILE *f=fopen(name,"rb");REQUIRE(f);size_t n=fread(buf,1,cap,f);fclose(f);return n;}
static unsigned loaded_act=99,loaded_era=99;
static void load(unsigned act,unsigned era){
    if(act==loaded_act && era==loaded_era)return;
    char path[128];snprintf(path,sizeof(path),"assets/generated/tt4%u%c.bin",act,'A'+era);
    size_t n=read_file(path,data,sizeof(data));REQUIRE(!stage_open(&stage,data,n));
    snprintf(path,sizeof(path),"assets/generated/ttcollision4%u%c.bin",act,'A'+era);
    size_t c=read_file(path,collision,sizeof(collision));
    scd_player_zone(2);scd_objects_zone(2);scd_player_act(act-1);scd_objects_act(act-1);
    REQUIRE(!scd_player_init(&stage,collision,c,era));
    loaded_act=act;loaded_era=era;
}
static void setup(unsigned i){
    load(placements[i].act,placements[i].era);
    unsigned era=placements[i].era;
    {extern unsigned scd_tt_wave_slot;scd_tt_wave_slot=31;} /* identity actor mapping (objects_tt_wave.inc) */
    scd_objects_reset(era,0);editmode.w=0;chibi_flag=0;
    memset(switchflag,0,32);memset(flagwork,0,sizeof(flagwork));
    int x=placements[i].x,y=placements[i].y;
    scd_act_camera(x-160,y-112);
    REQUIRE(scd_objects_spawn(placements[i].type,x,y,placements[i].sub,placements[i].flags&3)==0); /* bits 4-5: layout spawner metadata (tools/object_layouts.py) */
    actwk[1].userflag.b.l=placements[i].sec;
    for(int k=0;k<30;k++)REQUIRE(scd_objects_spawn(SCD_OBJ_LOG_SHADOW,x,y,era<2?0:1,0)==k+1);
    memcpy(N.a,actwk,sizeof(N.a));memset(N.sw,0,32);scd_tp_state_save(N.state);
    memcpy(O.a,actwk,sizeof(O.a));memset(O.sw,0,32);memset(O.fw,0,766);
    O.a[1].actno=r4_of(placements[i].type);
    for(int k=2;k<32;k++){memset(&O.a[k],0,sizeof(O.a[k]));O.a[k].actno=200;}
    /* GAME4.C:635 puts the water-surface wave in actwk[32] (native
       objects_tt_wave.inc; tools/tt_wave_test.c compares it): occupy it here. */
    if(N.a[32].actno==SCD_OBJ_WAVE){memset(&O.a[32],0,sizeof(O.a[32]));O.a[32].actno=250;}
    memset(nw_live,0,sizeof(nw_live));
}
static sprite_status parked(void){sprite_status p=make_player(0,0,8,0,0);p.xposi.w.h=scd_act_view_x()+8;p.yposi.w.h=scd_act_view_y()+8;return p;}
int main(void){
    state_size=scd_tp_state_size();scd_tp_inert_children=2;nw_alloc(&N);nw_alloc(&N0);
    unsigned count=sizeof(placements)/sizeof(*placements);
    /* One case per distinct routine configuration and terrain era. */
    for(unsigned i=0;i<count;i++){
        int dup=0;
        for(unsigned j=0;j<i && !dup;j++)dup=placements[j].act==placements[i].act && placements[j].era==placements[i].era &&
            placements[j].type==placements[i].type && placements[j].sub==placements[i].sub && placements[j].flags==placements[i].flags && placements[j].sec==placements[i].sec;
        if(dup)continue;
        cur_case=i;cases++;
        /* Phase 1: motion with the player parked in the viewport corner,
           switch flags raised and dropped part way through. */
        phase="motion";setup(i);
        for(cur_frame=0;cur_frame<700;cur_frame++){
            if(cur_frame==250){memset(O.sw,0xE0,32);memset(N.sw,0xE0,32);}
            if(cur_frame==450){memset(O.sw,0,32);memset(N.sw,0,32);}
            tick(parked(),0);
        }
        /* Phase 2: one-tick contacts around every solid piece, from three phases. */
        phase="contact";setup(i);
        for(cur_frame=0;cur_frame<=240;cur_frame++){
            if(cur_frame==1 || cur_frame==90 || cur_frame==240){
                memcpy(&O0,&O,sizeof(O));nw_copy(&N0,&N);
                for(int k=1;k<128;k++){
                    if(k>=2 && k<32)continue;
                    sprite_status base=O0.a[k];
                    if(!base.actno || base.actno==32 || !base.sprhsize)continue;
                    int hs=base.sprhsize+12,vs=base.sprvsize+24;
                    static const int xs[3]={512,0,-512};
                    for(int dx=-hs;dx<=hs;dx+=3)for(int dy=-vs;dy<=vs;dy+=3){
                        static const unsigned modes[]={0,1,2,7,8,3,6};
                        for(unsigned m=0;m<sizeof(modes)/sizeof(*modes);m++){
                            if(m>=5 && (dx+dy)%2)continue;
                            memcpy(&O,&O0,sizeof(O));nw_copy(&N,&N0);
                            sprite_status p=make_player(base.xposi.w.h+dx,base.yposi.w.h+dy,modes[m],xs[(unsigned)(dx+dy+300)%3],k);
                            if(modes[m]==7){O.a[k].cddat|=8;N.a[k].cddat|=8;}
                            tick(p,0);contacts++;
                            if(base.actno==34){spike_contacts++;if(O.a[0].r_no0>=4 || O.a[0].yspeed.w!=p.yspeed.w)spike_hits++;}
                            if(O.a[0].cddat&8)rides++;
                            else if(modes[m]==7)releases++;
                        }
                    }
                }
                memcpy(&O,&O0,sizeof(O));nw_copy(&N,&N0);
            }
            tick(parked(),0);
        }
        /* Phase 3: a carried player, released every 90 updates, then the
           viewport leaves so frameout runs. */
        phase="ride";setup(i);
        sprite_status p=parked();int riding=0;
        for(cur_frame=0;cur_frame<400;cur_frame++){
            sprite_status *o=&N.a[1];
            if(!o->actno)break;
            if(cur_frame%90<60){
                if(!riding || !(p.cddat&8)){p=make_player(o->xposi.w.h,o->yposi.w.h-o->sprvsize-19,0,0,0);}
                else{p.yspeed.w=0;}
                riding=1;
            }else{p=parked();riding=0;}
            int was=p.cddat&8;
            tick(p,0);p=N.a[0];
            if(p.cddat&8)rides++;
            if(was && !(p.cddat&8))releases++;
        }
        phase="frameout";
        scd_act_camera(scd_act_view_x()+2000,scd_act_view_y());
        for(cur_frame=0;cur_frame<3;cur_frame++)tick(parked(),0);
    }
    REQUIRE(cases>=40);REQUIRE(rides>1000);REQUIRE(releases>1000);REQUIRE(spawns>50);
    REQUIRE(spike_linked>1000);REQUIRE(coli_player>100000);REQUIRE(spike_contacts>1000);REQUIRE(spike_hits>100);
    printf("PASS: %u assertions; %u cases; %u ticks; %u contact ticks; %u ridden; %u releases; %u pushes; %u child spawns; %u removals; %u draws; harir4 %u compares (%u ride-linked), %u contacts, %u hits; COLI4 %u player / %u actor contacts\n",
           checks,cases,ticks,contacts,rides,releases,pushes,spawns,removals,draws,spike_compares,spike_linked,spike_contacts,spike_hits,coli_player,coli_actor);
}
