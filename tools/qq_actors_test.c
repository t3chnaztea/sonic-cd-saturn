/* Compiled R5 originals versus objects_qq_*.inc. Two complete actor worlds
   (retail actwk[] layout and native pool + actwk[]) run the same player
   through the same updates; every live actor, the player, the score, the
   shield, player hits, colrevflag, the projector and generator flags and the
   drawn-sprite set must match after each update. Retail actwkchk starts at
   actwk[32], so both worlds hold inert fillers in actors 2-31 and children
   land in the same actor indices. tools/test-qq-actors.sh builds it. */
#include "EQU.H"
#include "scd_objects.h"
#include "scd_actor.h"
#include "scd_player.h"
#include "act.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "qq_ids.h"
#include "qq_orig.h"
#include "placements.h"

size_t scd_qq_host_size(void);void scd_qq_host_save(void*);void scd_qq_host_load(const void*);int scd_qq_host_good_future(void);
void denden(sprite_status*);void sasori(sprite_status*);void kemusi(sprite_status*);void kumo(sprite_status*);void iwa5(sprite_status*);
void hari5f(sprite_status*);void harir5(sprite_status*);void iwa5roll(sprite_status*);void kuzure5(sprite_status*);void iwa5wave(sprite_status*);
void buranko5(sprite_status*);void hasira5(sprite_status*);void hashi5(sprite_status*);void beltsw5(sprite_status*);void shooter(sprite_status*);
void movie(sprite_status*);void friend(sprite_status*);void et(sprite_status*);void kowasi(sprite_status*);
void playdamagechk(sprite_status*,sprite_status*);short playdieset(sprite_status*);short pcol(sprite_status*);
void *qq_ptr12[128];short *qq_ptr16[128];char *qq_cur12[128];

static unsigned checks,cases,ticks,contacts,rides,releases,spawns,removals,draws,hits,kills,belt_flips,shots,captures,breaks,colis;
static unsigned per_type[256];static uint32_t states[256];
static unsigned cur_case;static int cur_frame;static const char *phase="";
#define REQUIRE(v) do{checks++;if(!(v)){fprintf(stderr,"FAIL case %u type %u sub %u act %u era %u (%s) frame %d line %d: %s\n",cur_case,placements[cur_case].type,placements[cur_case].sub,placements[cur_case].act,placements[cur_case].era,phase,cur_frame,__LINE__,#v);exit(1);}}while(0)

/* ---- retail helpers (ACTION.C, ACTSET.C, SCORE.C, COLI5.C) ---- */
static sprite_status last_input;
static unsigned char drawn[128];static unsigned original_hits;
void actionsub(sprite_status *o){
    drawn[o-actwk]=1;
    o->actflg&=127;if(!o->actno)return;
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
void scoreup(unsigned int n){scd_player_points(n*10);}
/* COLI5.C playdamageset without the lost-ring actor: the fixture keeps no
   rings, so the native hurt path creates none either. */
short playdamageset(sprite_status *p,sprite_status *o){original_hits++;if(plpower_b || plring){playdamagechk(p,o);return -1;}return playdieset(p);}

static void (*const routines[256])(sprite_status*)={
    [SCD_OBJ_R5_DENDEN]=denden,[SCD_OBJ_R5_SASORI]=sasori,[SCD_OBJ_R5_KEMUSI]=kemusi,[SCD_OBJ_R5_KUMO]=kumo,[SCD_OBJ_R5_IWA5]=iwa5,
    [SCD_OBJ_R5_HARI5F]=hari5f,[SCD_OBJ_R5_HARIR5]=harir5,[SCD_OBJ_R5_IWA5ROLL]=iwa5roll,[SCD_OBJ_R5_KUZURE5]=kuzure5,
    [SCD_OBJ_R5_IWA5WAVE]=iwa5wave,[SCD_OBJ_R5_BURANKO5]=buranko5,[SCD_OBJ_R5_HASIRA5]=hasira5,[SCD_OBJ_R5_HASHI5]=hashi5,
    [SCD_OBJ_R5_BELTSW5]=beltsw5,[SCD_OBJ_R5_SHOOT5]=shooter,[SCD_OBJ_R5_MOVIE5]=movie,[SCD_OBJ_R5_FRIEND5]=friend,
    [SCD_OBJ_R5_ET5]=et,[SCD_OBJ_R5_KOWASI5]=kowasi};
static int r5(unsigned t){return t<256 && routines[t];}
/* Actor 24 (PLAYSUB.C bakuha) is not run here; its baku_init clears colino
   in the update it starts, so pcol never meets it again. */
static void orig_tick(void){
    for(int k=1;k<128;k++){
        if(r5(actwk[k].actno))routines[actwk[k].actno](&actwk[k]);
        else if(actwk[k].actno==SCD_OBJ_EXPLOSION)actwk[k].colino=0;
    }
}

/* ---- the two worlds ---- */
typedef struct{sprite_status a[128];unsigned char fw[766],colrev,proj,gen;short emy;void *p12[128];short *p16[128];char *c12[128];}oworld;
typedef struct{sprite_status a[128];unsigned char colrev,proj;short emy;uint8_t *state;}nworld;
static size_t state_size;
static void nw_alloc(nworld *w){w->state=malloc(state_size);}
static void nw_copy(nworld *d,const nworld *s){uint8_t *st=d->state;memcpy(d,s,sizeof(*d));d->state=st;memcpy(st,s->state,state_size);}
static oworld O,O0;static nworld N,N0;
static int qq_views(void){
    static scd_object_view v[256];unsigned n=scd_objects_views(v,256),c=0;
    for(unsigned i=0;i<n;i++)if(r5(v[i].type))c++;
    return (int)c;
}
static void player_diff(const sprite_status *a,const sprite_status *b){
    const unsigned char *x=(const void*)a,*y=(const void*)b;
    for(unsigned i=0;i<sizeof(*a);i++)if(x[i]!=y[i])fprintf(stderr,"player byte %u original %u native %u\n",i,x[i],y[i]);
    fprintf(stderr,"input xy=%d,%d ys=%d xs=%d r=%u cddat=%u mst=%u\n",last_input.xposi.w.h,last_input.yposi.w.h,last_input.yspeed.w,last_input.xspeed.w,last_input.r_no0,last_input.cddat,last_input.mstno.b.h);
    fprintf(stderr,"player original xy=%d,%d r=%u cddat=%u ride=%u ys=%d native xy=%d,%d r=%u cddat=%u ride=%u ys=%d\n",
        a->xposi.w.h,a->yposi.w.h,a->r_no0,a->cddat,a->actfree[19],a->yspeed.w,b->xposi.w.h,b->yposi.w.h,b->r_no0,b->cddat,b->actfree[19],b->yspeed.w);
    for(int k=1;k<128;k++)if((k<2 || k>=32) && (O.a[k].actno || N.a[k].actno))
        fprintf(stderr,"  actor %d original %u xy=%d,%d r=%u col=%u cnt=%u flg=%u | native %u xy=%d,%d r=%u col=%u cnt=%u flg=%u\n",k,
            O.a[k].actno,O.a[k].xposi.w.h,O.a[k].yposi.w.h,O.a[k].r_no0,O.a[k].colino,O.a[k].colicnt,O.a[k].actflg,
            N.a[k].actno,N.a[k].xposi.w.h,N.a[k].yposi.w.h,N.a[k].r_no0,N.a[k].colino,N.a[k].colicnt,N.a[k].actflg);
}
static void compare(void){
    if(memcmp(&O.a[0],&N.a[0],sizeof(sprite_status)))player_diff(&O.a[0],&N.a[0]);
    REQUIRE(!memcmp(&O.a[0],&N.a[0],sizeof(sprite_status)));
    for(int k=1;k<128;k++){
        if(k>=2 && k<32)continue;
        sprite_status *a=&O.a[k],*b=&N.a[k];
        /* Explosions are actor 24 in both worlds; only the native one runs.
           The retail one is dropped when the native one ends. */
        if(a->actno==SCD_OBJ_EXPLOSION && !b->actno){memset(a,0,sizeof(*a));continue;}
        if(b->actno==SCD_OBJ_EXPLOSION && (a->actno==SCD_OBJ_EXPLOSION || !a->actno))continue;
        /* A badnik's native explosion runs PLAYSUB bakuha (3eee15d): its points
           popup takes a free actor and the explosion becomes a flower in place. */
        if(b->actno==SCD_OBJ_SCORE && !a->actno)continue;
        if(b->actno==SCD_OBJ_FLOWER && (a->actno==SCD_OBJ_EXPLOSION || !a->actno)){memset(a,0,sizeof(*a));continue;}
        if(a->actno!=b->actno)fprintf(stderr,"actor %d: original actno %u native %u\n",k,a->actno,b->actno);
        REQUIRE(a->actno==b->actno);
        if(!a->actno)continue;
#define F(f) if(a->f!=b->f){fprintf(stderr,"actor %d type %u field %s original %ld native %ld\n",k,a->actno,#f,(long)a->f,(long)b->f);REQUIRE(a->f==b->f);}
        F(r_no0)F(r_no1)F(actflg)F(cddat)F(xposi.l)F(yposi.l)F(xspeed.w)F(yspeed.w)F(sprhsize)F(sprvsize)F(sprhs)
        F(sprpri)F(patno)F(userflag.w)F(colino)F(colicnt)F(mstno.w)F(patcnt)F(pattim)F(sproffset)F(direc.w)F(mspeed.w)
#undef F
        if(memcmp(a->actfree,b->actfree,sizeof(a->actfree)))for(unsigned i=0;i<sizeof(a->actfree);i++)
            if(a->actfree[i]!=b->actfree[i])fprintf(stderr,"actor %d type %u actfree[%u] original %u native %u\n",k,a->actno,i,a->actfree[i],b->actfree[i]);
        REQUIRE(!memcmp(a->actfree,b->actfree,sizeof(a->actfree)));
    }
}
static unsigned char nw_live[128];
static void tick(sprite_status player,unsigned char shield){
    last_input=player;
    int vx=scd_act_view_x();
    scd_player_progress p0=scd_player_progress_get();
    /* retail */
    memcpy(actwk,O.a,sizeof(O.a));actwk[0]=player;memcpy(flagwork,O.fw,766);
    colrevflag=O.colrev;projector_flag=O.proj;generate_flag=O.gen;emyscorecnt=O.emy;
    memcpy(qq_ptr12,O.p12,sizeof(qq_ptr12));memcpy(qq_ptr16,O.p16,sizeof(qq_ptr16));memcpy(qq_cur12,O.c12,sizeof(qq_cur12));
    scra_h_posit.w.h=(short)vx;memset(drawn,0,sizeof(drawn));original_hits=0;plpower_b=shield;plring=0;
    /* PLAYER.C runs COLI5.C pcol before the object pass. */
    if(player.r_no0<4){sprite_status before=actwk[0];pcol(actwk);if(memcmp(&before,&actwk[0],sizeof(before)))colis++;}
    orig_tick();
    memcpy(O.a,actwk,sizeof(O.a));memcpy(O.fw,flagwork,766);O.colrev=colrevflag;O.proj=projector_flag;O.gen=generate_flag;O.emy=emyscorecnt;
    memcpy(O.p12,qq_ptr12,sizeof(qq_ptr12));memcpy(O.p16,qq_ptr16,sizeof(qq_ptr16));memcpy(O.c12,qq_cur12,sizeof(qq_cur12));
    scd_player_progress po=scd_player_progress_get();unsigned char oshield=plpower_b;unsigned ohits=original_hits;
    int odrawn=0;for(int k=1;k<128;k++)if(drawn[k] && r5(O.a[k].actno))odrawn++;
    /* native */
    scd_player_progress_set(p0);plpower_b=shield;plring=0;
    memcpy(actwk,N.a,sizeof(N.a));actwk[0]=player;colrevflag=N.colrev;projector_flag=N.proj;emyscorecnt=N.emy;scd_qq_host_load(N.state);
    unsigned h0=scd_objects_get().hits;
    /* COLI5: native qq_enemy_scan runs inside scd_objects_step. */
    scd_objects_step(player.xposi.w.h,player.yposi.w.h);
    unsigned nhits=scd_objects_get().hits-h0;
    int ndrawn=qq_views();
    memcpy(N.a,actwk,sizeof(N.a));N.colrev=colrevflag;N.proj=projector_flag;N.emy=emyscorecnt;scd_qq_host_save(N.state);
    ticks++;
    for(int k=1;k<128;k++)if(r5(O.a[k].actno))states[O.a[k].actno]|=1u<<((O.a[k].r_no0/2)&31);
    for(int k=32;k<128;k++){if(O.a[k].actno && !nw_live[k])spawns++;if(!O.a[k].actno && nw_live[k])removals++;nw_live[k]=O.a[k].actno!=0;}
    if(odrawn!=ndrawn)fprintf(stderr,"drawn original %d native %d\n",odrawn,ndrawn);
    if(ohits!=nhits)fprintf(stderr,"hits original %u native %u\n",ohits,nhits);
    compare();REQUIRE(odrawn==ndrawn);draws+=odrawn;
    REQUIRE(ohits==nhits);hits+=ohits;
    REQUIRE(plpower_b==oshield);REQUIRE(scd_player_progress_get().score==po.score);
    REQUIRE(O.emy==N.emy);REQUIRE(O.colrev==N.colrev);REQUIRE(!O.proj==!N.proj);REQUIRE(!O.gen==!scd_qq_host_good_future());
}
static sprite_status make_player(int x,int y,unsigned mode,int xs,unsigned actor){
    sprite_status p={0};p.actno=1;p.r_no0=mode==3?6:2;
    p.xposi.w.h=x;p.yposi.w.h=y;p.sprvsize=mode==2 || mode==9?14:19;p.sprhs=9;p.sprhsize=9;
    p.cddat=mode==2 || mode==9?6:2;p.yspeed.w=mode==1?-300:mode==8?0:300;p.xspeed.w=xs;p.mspeed.w=xs;
    if(mode==6)p.mstno.b.h=43;
    if(mode==7){p.cddat=8;p.actfree[19]=actor;p.yspeed.w=0;}
    if(mode==9)p.mstno.b.h=2;
    if(mode==10)scd_word_set(&p,26,120);
    return p;
}
static stage_t stage;static unsigned char data[400000],collision[16384];
static size_t read_file(const char *name,unsigned char *buf,size_t cap){FILE *f=fopen(name,"rb");REQUIRE(f);size_t n=fread(buf,1,cap,f);fclose(f);return n;}
static unsigned loaded_act=99,loaded_era=99;
static void load(unsigned act,unsigned era){
    if(act==loaded_act && era==loaded_era)return;
    char path[128];snprintf(path,sizeof(path),"assets/generated/qq5%u%c.bin",act,'A'+era);
    size_t n=read_file(path,data,sizeof(data));REQUIRE(!stage_open(&stage,data,n));
    snprintf(path,sizeof(path),"assets/generated/qqcollision5%u%c.bin",act,'A'+era);
    size_t c=read_file(path,collision,sizeof(collision));
    scd_player_zone(3);scd_objects_zone(3);scd_player_act(act-1);scd_objects_act(act-1);
    REQUIRE(!scd_player_init(&stage,collision,c,era));
    loaded_act=act;loaded_era=era;
}
static void setup(unsigned i){
    load(placements[i].act,placements[i].era);
    unsigned era=placements[i].era;
    scd_objects_reset(era,0);editmode.w=0;
    memset(flagwork,0,sizeof(flagwork));
    int x=placements[i].x,y=placements[i].y;
    scd_act_camera(x-160,y-112);
    REQUIRE(scd_objects_spawn(placements[i].type,x,y,placements[i].sub,placements[i].flags)==0);
    actwk[1].userflag.b.l=placements[i].sec;
    for(int k=0;k<30;k++)REQUIRE(scd_objects_spawn(SCD_OBJ_LOG_SHADOW,x,y,era<2?0:1,0)==k+1);
    memcpy(N.a,actwk,sizeof(N.a));N.colrev=0;N.proj=0;N.emy=0;scd_qq_host_save(N.state);
    memcpy(O.a,actwk,sizeof(O.a));memset(O.fw,0,766);O.colrev=0;O.proj=0;O.gen=generate_flag;O.emy=0;
    memset(O.p12,0,sizeof(O.p12));memset(O.p16,0,sizeof(O.p16));memset(O.c12,0,sizeof(O.c12));
    for(int k=2;k<32;k++){memset(&O.a[k],0,sizeof(O.a[k]));O.a[k].actno=250;}
    memset(nw_live,0,sizeof(nw_live));
}
static sprite_status parked(void){sprite_status p=make_player(0,0,8,0,0);p.xposi.w.h=scd_act_view_x()+8;p.yposi.w.h=scd_act_view_y()+8;return p;}
static void follow_camera(int x,int y){scd_act_camera(x-160,y-112);}
int main(void){
    state_size=scd_qq_host_size();nw_alloc(&N);nw_alloc(&N0);
    unsigned count=sizeof(placements)/sizeof(*placements);
    for(unsigned i=0;i<count;i++){
        int dup=0;
        for(unsigned j=0;j<i && !dup;j++)dup=placements[j].act==placements[i].act && placements[j].era==placements[i].era &&
            placements[j].type==placements[i].type && placements[j].sub==placements[i].sub && placements[j].flags==placements[i].flags && placements[j].sec==placements[i].sec;
        if(dup)continue;
        cur_case=i;cases++;per_type[placements[i].type]++;
        /* Phase 1: motion with the player parked in the viewport corner. */
        phase="motion";setup(i);
        for(cur_frame=0;cur_frame<600;cur_frame++)tick(parked(),1);
        /* Phase 2: the player held beside/above/below the actor while the
           camera follows it: sight checks, shots, sparks, webs. */
        static const int sides[6][2]={{-60,-8},{70,-8},{-150,40},{150,-120},{0,-60},{0,90}};
        for(unsigned side=0;side<6;side++){
            phase="chase";setup(i);
            for(cur_frame=0;cur_frame<300;cur_frame++){
                sprite_status *o=&N.a[1];
                if(!o->actno || o->actno==SCD_OBJ_EXPLOSION)break;
                follow_camera(o->xposi.w.h,o->yposi.w.h);
                tick(make_player(o->xposi.w.h+sides[side][0],o->yposi.w.h+sides[side][1],side&1?8:0,0,0),1);
            }
        }
        /* Phase 3: one-update contacts around every live piece, from three
           points in the motion. */
        phase="contact";setup(i);
        for(cur_frame=0;cur_frame<=240;cur_frame++){
            if(cur_frame==1 || cur_frame==90 || cur_frame==240){
                memcpy(&O0,&O,sizeof(O));nw_copy(&N0,&N);
                for(int k=1;k<128;k++){
                    if(k>=2 && k<32)continue;
                    sprite_status base=O0.a[k];
                    if(!r5(base.actno))continue;
                    int hs=(base.sprhsize?base.sprhsize:8)+12,vs=(base.sprvsize?base.sprvsize:8)+24;
                    static const int xs[3]={512,0,-512};
                    for(int dx=-hs;dx<=hs;dx+=4)for(int dy=-vs;dy<=vs;dy+=4){
                        static const unsigned modes[]={0,1,9,7,8,3,6,10,11};
                        for(unsigned m=0;m<sizeof(modes)/sizeof(*modes);m++){
                            if(m>=5 && (dx+dy)%8)continue;
                            memcpy(&O,&O0,sizeof(O));nw_copy(&N,&N0);
                            sprite_status p=make_player(base.xposi.w.h+dx,base.yposi.w.h+dy,modes[m],xs[(unsigned)(dx+dy+300)%3],k);
                            if(modes[m]==7){O.a[k].cddat|=8;N.a[k].cddat|=8;}
                            unsigned before=O.a[k].actno;
                            tick(p,modes[m]!=11);contacts++;
                            if(O.a[0].cddat&8)rides++;
                            else if(modes[m]==7)releases++;
                            if(before!=SCD_OBJ_EXPLOSION && O.a[k].actno==SCD_OBJ_EXPLOSION)kills++;
                            if(O.a[0].actfree[2]==129)captures++;
                        }
                    }
                }
                memcpy(&O,&O0,sizeof(O));nw_copy(&N,&N0);
            }
            tick(parked(),1);
        }
        /* Phase 4: a followed player: set on top of the actor, then carried
           by whatever the actors do to it (rides, belts, the shooter route),
           reset every 150 updates; the camera follows the player. */
        phase="follow";setup(i);
        sprite_status p=parked();
        for(cur_frame=0;cur_frame<600;cur_frame++){
            sprite_status *o=&N.a[1];
            if(!o->actno)break;
            if(cur_frame%150==0 || p.r_no0>=4 || p.xposi.w.h<16 || p.yposi.w.h<16)
                p=make_player(o->xposi.w.h,o->yposi.w.h-o->sprvsize-19,cur_frame%300?9:8,0,0);
            follow_camera(p.xposi.w.h,p.yposi.w.h);
            int was=p.cddat&8;
            unsigned char colrev=N.colrev;
            tick(p,1);p=N.a[0];
            if(p.cddat&8)rides++;
            if(was && !(p.cddat&8))releases++;
            if(N.colrev!=colrev)belt_flips++;
            if(p.actfree[2]==129)captures++;
            /* No player physics run here: keep the captured player moving
               only by the actor, and a free player drifting down. */
            if(!(p.actfree[2]&128) && !(p.cddat&8))p.yposi.w.h+=2;
        }
        phase="frameout";
        scd_act_camera(scd_act_view_x()+2000,scd_act_view_y());
        for(cur_frame=0;cur_frame<3;cur_frame++)tick(parked(),1);
        /* KOWASI5 (colino 51) and HASIRA5 break on colicnt; COLI5 counts 51
           nowhere, so raise it directly once in both worlds. */
        if(placements[i].type==SCD_OBJ_R5_KOWASI5 || placements[i].type==SCD_OBJ_R5_HASIRA5){
            phase="break";setup(i);
            for(cur_frame=0;cur_frame<200;cur_frame++){
                if(cur_frame==20 && O.a[1].actno==placements[i].type){O.a[1].colicnt=N.a[1].colicnt=1;breaks++;}
                tick(make_player(N.a[1].xposi.w.h-40,N.a[1].yposi.w.h,0,-512,0),1);
            }
        }
    }
    static const struct{unsigned type;const char *name;}names[]={
        {SCD_OBJ_R5_DENDEN,"denden"},{SCD_OBJ_R5_SASORI,"sasori"},{SCD_OBJ_R5_KEMUSI,"kemusi"},{SCD_OBJ_R5_KUMO,"kumo"},{SCD_OBJ_R5_IWA5,"iwa5"},
        {SCD_OBJ_R5_HARI5F,"hari5f"},{SCD_OBJ_R5_HARIR5,"harir5"},{SCD_OBJ_R5_IWA5ROLL,"iwa5roll"},{SCD_OBJ_R5_KUZURE5,"kuzure5"},
        {SCD_OBJ_R5_IWA5WAVE,"iwa5wave"},{SCD_OBJ_R5_BURANKO5,"buranko5"},{SCD_OBJ_R5_HASIRA5,"hasira5"},{SCD_OBJ_R5_HASHI5,"hashi5"},
        {SCD_OBJ_R5_BELTSW5,"beltsw5"},{SCD_OBJ_R5_SHOOT5,"shoot5"},{SCD_OBJ_R5_MOVIE5,"movie5"},{SCD_OBJ_R5_FRIEND5,"friend5"},
        {SCD_OBJ_R5_ET5,"et5"},{SCD_OBJ_R5_KOWASI5,"kowasi5"}};
    /* Every routine state (r_no0/2 bit) seen after an update, per routine. Init
       states that fall through to the next routine in the same update
       never show; children that stay at 0 do. */
    static const struct{unsigned type;uint32_t need;}reach[]={
        {SCD_OBJ_R5_DENDEN,7},{SCD_OBJ_R5_SASORI,0x7FF},{SCD_OBJ_R5_KEMUSI,0x1E},{SCD_OBJ_R5_KUMO,0x7F},{SCD_OBJ_R5_IWA5,7},
        {SCD_OBJ_R5_HARI5F,6},{SCD_OBJ_R5_HARIR5,2},{SCD_OBJ_R5_IWA5ROLL,2},{SCD_OBJ_R5_KUZURE5,0xE},{SCD_OBJ_R5_IWA5WAVE,2},
        {SCD_OBJ_R5_BURANKO5,2},{SCD_OBJ_R5_HASIRA5,6},{SCD_OBJ_R5_HASHI5,6},{SCD_OBJ_R5_BELTSW5,0xE},{SCD_OBJ_R5_SHOOT5,0xF},
        {SCD_OBJ_R5_MOVIE5,0x1E},{SCD_OBJ_R5_FRIEND5,7},{SCD_OBJ_R5_ET5,0xF},{SCD_OBJ_R5_KOWASI5,6}};
    for(unsigned n=0;n<sizeof(names)/sizeof(*names);n++){
        if(!per_type[names[n].type])fprintf(stderr,"no case for %s\n",names[n].name);
        REQUIRE(per_type[names[n].type]);
        uint32_t need=reach[n].need,got=states[names[n].type];
        if((got&need)!=need)fprintf(stderr,"%s reached states %#x of %#x\n",names[n].name,got,need);
    }
    for(unsigned n=0;n<sizeof(names)/sizeof(*names);n++)REQUIRE((states[names[n].type]&reach[n].need)==reach[n].need);
    REQUIRE(cases>=60);REQUIRE(rides>1000);REQUIRE(releases>100);REQUIRE(spawns>100);REQUIRE(kills>100);REQUIRE(hits>100);
    REQUIRE(belt_flips>0);REQUIRE(captures>100);REQUIRE(colis>10000);
    printf("PASS: qq actors %u assertions; %u cases; %u ticks; %u contact ticks; %u ridden; %u releases; %u child spawns; %u removals; %u draws; %u hits; %u kills; %u belt flips; %u shooter captures; %u forced breaks; COLI5 %u player contacts\n",
           checks,cases,ticks,contacts,rides,releases,spawns,removals,draws,hits,kills,belt_flips,captures,breaks,colis);
    return 0;
}
