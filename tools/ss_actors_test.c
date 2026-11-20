/* Compiled R7 originals versus objects_ss_*.inc. Two complete actor worlds
   (retail actwk[] layout and native pool + actwk[]) run the same player
   through the same updates; every live actor, the player, the score, the
   shield, player hits, bossflag, the auto-control and clock globals, Amy's
   goal and sound requests and the drawn-sprite set must match after each
   update. Retail actwkchk scans its object region. The fixture relocates its
   first object to actor1, holds inert fillers in actors2-31, and keeps
   children at32+. Allocation includes1 once the root actor frees it.
   HARI73 needs Metal Sonic (actor 47): both worlds hold a scripted stand-in
   at actor 100 that runs at the spikes; WALL73 moves once bossflag bit 7 is
   set (BOSS_7.C door_open), which the fixture does at update 30.
   tools/test-ss-actors.sh builds it. */
#include "EQU.H"
#include "scd_objects.h"
#include "scd_actor.h"
#include "scd_player.h"
#include "act.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "ss_ids.h"
#include "ss_orig.h"
#include "placements.h"

size_t scd_ss_host_size(void);void scd_ss_host_save(void*);void scd_ss_host_load(const void*);int scd_ss_host_good_future(void);
void emie7(sprite_status*);void heart7(sprite_status*);void hari73(sprite_status*);void wall73(sprite_status*);void gaitou73(sprite_status*);
void chgban(sprite_status*);void spring_r(sprite_status*);void gun7(sprite_status*);void hibana(sprite_status*);
void slight7(sprite_status*);void chgwall7(sprite_status*);void tekkyu7(sprite_status*);void tekkyu7j(sprite_status*);
void hotaru7(sprite_status*);void kabasira(sprite_status*);void kanabun(sprite_status*);void dango(sprite_status*);
void *ss_ptr0[128],*ss_ptr4[128],*ss_ptr8[128];char *ss_cur12[128];
void friend(sprite_status*);void et(sprite_status*);void movie(sprite_status*);
/* LOADER2 divdevset (art upload) is an empty stub in the PC source. */
void divdevset(int n){(void)n;}
void scd_ss_host_projector(int);
void branko7(sprite_status*);
void bakuha(sprite_status*);void flower(sprite_status*);void ss_original_points(sprite_status*);
void playdamagechk(sprite_status*,sprite_status*);short playdieset(sprite_status*);short pcol(sprite_status*);
/* Retail data and services the originals link against. */
PALETTEENTRY gamecolor[64];static PALETTEENTRY colorwk[64];
sprite_pattern *pat_wall7[8],*springpat2[4],*spring90pat2[4],*spring45pat2[4];
/* SPRING.C springchg. */
static unsigned char springchg0[12]={0,0,1,1,2,2,2,2,2,2,1,252};unsigned char *springchg[1]={springchg0};
static unsigned goals,syncs;
/* GOAL.C goal_move2, the actor side (objects_ss_act3.inc em7_goal_move2 is its
   native twin): the clear actor, music and bonuses are src/act.c's. */
void goal_move2(sprite_status *o){
    char t=(char)(o->actfree[0]-1);o->actfree[0]=(unsigned char)t;if(t)return;
    plautoflag|=1;swdata.w=stageno.w==1282?0:2056;o->actfree[0]=180;o->r_no0+=2;goals++;
}
void scd_objects_ss_goal(void){goals++;}
void sub_sync(short n){syncs=syncs*31+(unsigned short)n;}
/* BOSS_7.C hari_spdadd (add_spd2) on the PC scratch words. */
void hari_spdadd(sprite_status *o){
    short *w=(short*)((char*)o->actfree-46);
    o->xspeed.w+=w[26];o->yspeed.w+=w[27];
    o->xposi.l+=(int)o->xspeed.w<<8;o->yposi.l+=(int)o->yspeed.w<<8;
}

static unsigned checks,cases,ticks,contacts,rides,releases,spawns,removals,draws,hits,kills,colis,smashes,wall_moves,amy_grabs,amy_goals;
static unsigned lifecycle_checks[256];
static unsigned per_type[256],live_ticks[256];static uint32_t states[256];
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
    for(int i=1;i<128;i++)if(!actwk[i].actno){*pp=&actwk[i];return 0;}
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
/* COLI7.C playdamageset without the lost-ring actor: the fixture keeps no
   rings, so the native hurt path creates none either. */
/* COLI7 keeps scanning after a hurt (only pcolitem's -1 stops it), so a
   second contact in the same update reaches a player playdieset already
   killed: it repeats the same death state. Native scd_objects_hurt ignores a
   dead player, so only live-player hits count. */
short playdamageset(sprite_status *p,sprite_status *o){if(p->r_no0>=4)return playdieset(p);original_hits++;if(plpower_b || plring){playdamagechk(p,o);return -1;}return playdieset(p);}

static void (*const routines[256])(sprite_status*)={
    [SCD_OBJ_R7_EMIE7]=emie7,[SCD_OBJ_R7_HEART7]=heart7,[SCD_OBJ_R7_HARI73]=hari73,[SCD_OBJ_R7_WALL73]=wall73,[SCD_OBJ_R7_GAITOU73]=gaitou73,
    [SCD_OBJ_R7_CHGBAN]=chgban,[SCD_OBJ_R7_SPRING_R]=spring_r,[SCD_OBJ_R7_GUN7]=gun7,[SCD_OBJ_R7_HIBANA7]=hibana,
    [SCD_OBJ_R7_SLIGHT7]=slight7,[SCD_OBJ_R7_CHGWALL7]=chgwall7,[SCD_OBJ_R7_TEKKYU7]=tekkyu7,[SCD_OBJ_R7_TEKKYU7J]=tekkyu7j,
    [SCD_OBJ_R7_HOTARU7]=hotaru7,[SCD_OBJ_R7_KABASIRA]=kabasira,[SCD_OBJ_R7_KANABUN]=kanabun,[SCD_OBJ_R7_DANGO7]=dango,[SCD_OBJ_R7_BRANKO7]=branko7,
    [SCD_OBJ_R7_FRIEND7]=friend,[SCD_OBJ_R7_ET7]=et,[SCD_OBJ_R7_MOVIE7]=movie};
static int r7(unsigned t){return t<256 && routines[t];}
/* Run original PLAYSUB and SCORE children in the same actor-slot pass. */
static void orig_tick(void){
    for(int k=1;k<128;k++){
        if(r7(actwk[k].actno))routines[actwk[k].actno](&actwk[k]);
        else if(actwk[k].actno==SCD_OBJ_EXPLOSION)bakuha(&actwk[k]);
        else if(actwk[k].actno==SCD_OBJ_FLOWER)flower(&actwk[k]);
        else if(actwk[k].actno==SCD_OBJ_SCORE)ss_original_points(&actwk[k]);
    }
}

/* ---- the two worlds ---- */
typedef struct{sprite_status a[128];unsigned char fw[766],boss,autof,timef,prio,proj,gen;short emy;unsigned short sw;unsigned goals,syncs;void *p0[128],*p4[128],*p8[128];char *c12[128];}oworld;
typedef struct{sprite_status a[128];unsigned char boss,autof,timef,prio,proj;short emy;unsigned short sw;unsigned goals,syncs;uint8_t *state;}nworld;
static size_t state_size;
static void nw_alloc(nworld *w){w->state=malloc(state_size);}
static void nw_copy(nworld *d,const nworld *s){uint8_t *st=d->state;memcpy(d,s,sizeof(*d));d->state=st;memcpy(st,s->state,state_size);}
static oworld O,O0;static nworld N,N0;
static int ss_views(void){
    static scd_object_view v[256];unsigned n=scd_objects_views(v,256),c=0;
    for(unsigned i=0;i<n;i++)if(r7(v[i].type))c++;
    /* Compare the actual production view with original PLAYSUB state. A
       newly allocated seed has no draw until its first flower dispatch. */
    for(unsigned i=0;i<n;i++)if(v[i].type==SCD_OBJ_FLOWER){
        unsigned matched=0;
        for(unsigned k=1;k<128;k++){
            const sprite_status *o=&O.a[k];
            if(o->actno==SCD_OBJ_FLOWER && o->r_no0 && o->xposi.w.h==v[i].x && o->yposi.w.h==v[i].y &&
               o->patno==v[i].frame && ((o->sproffset>>15)&1)==v[i].subtype &&
               ((o->actflg&3)|((o->sprpri&7)<<5))==v[i].flags)matched++;
        }
        REQUIRE(matched>0);
    }
    for(unsigned k=1;k<128;k++)if(O.a[k].actno==SCD_OBJ_FLOWER && O.a[k].r_no0){
        unsigned matched=0;
        for(unsigned i=0;i<n;i++)if(v[i].type==SCD_OBJ_FLOWER && v[i].x==O.a[k].xposi.w.h && v[i].y==O.a[k].yposi.w.h && v[i].frame==O.a[k].patno)matched++;
        REQUIRE(matched>0);
    }
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
        if(a->actno!=b->actno)fprintf(stderr,"actor %d: original actno %u native %u\n",k,a->actno,b->actno);
        REQUIRE(a->actno==b->actno);
        if(!a->actno)continue;
        if(a->actno==SCD_OBJ_EXPLOSION || a->actno==SCD_OBJ_FLOWER || a->actno==SCD_OBJ_SCORE)lifecycle_checks[a->actno]++;
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
    /* HARI73's Metal Sonic stand-in runs right at 4 pixels an update. */
    if(O.a[100].actno==47){O.a[100].xposi.w.h+=4;N.a[100].xposi.w.h+=4;}
    /* BOSS_7.C door_open sets bossflag bit 7 when the race starts. */
    if(cur_frame==30 && (!strcmp(phase,"motion") || !strcmp(phase,"follow"))){O.boss|=128;N.boss|=128;}
    short wall_y=O.a[1].yposi.w.h;
    int vx=scd_act_view_x();
    scd_player_progress p0=scd_player_progress_get();
    /* retail */
    memcpy(actwk,O.a,sizeof(O.a));actwk[0]=player;memcpy(flagwork,O.fw,766);
    bossflag=O.boss;plautoflag=O.autof;pltime_f=O.timef;swdata.w=O.sw;goals=O.goals;syncs=O.syncs;emyscorecnt=O.emy;prio_flag=O.prio;
    generate_flag=O.gen;projector_flag=O.proj;memcpy(ss_cur12,O.c12,sizeof(ss_cur12));lpcolorwk=colorwk;gametimer.w=(unsigned short)(ticks+1); /* GAME.C increments before actions. */
    {unsigned e=placements[cur_case].era;time_flag=e==0?1:e==1?0:2;}stageno.b.h=5;stageno.b.l=(unsigned char)(placements[cur_case].act-1);
    memcpy(ss_ptr0,O.p0,sizeof(ss_ptr0));memcpy(ss_ptr4,O.p4,sizeof(ss_ptr4));memcpy(ss_ptr8,O.p8,sizeof(ss_ptr8));
    scra_h_posit.w.h=(short)vx;scra_v_posit.w.h=(short)scd_act_view_y();memset(drawn,0,sizeof(drawn));original_hits=0;plpower_b=shield;plring=0;
    if(!(player.cddat&2))emyscorecnt=0;
    /* PLAYER.C runs COLI7.C pcol before the object pass. */
    if(player.r_no0<4){sprite_status before=actwk[0];pcol(actwk);if(memcmp(&before,&actwk[0],sizeof(before)))colis++;}
    orig_tick();
    memcpy(O.a,actwk,sizeof(O.a));memcpy(O.fw,flagwork,766);O.emy=emyscorecnt;
    O.boss=bossflag;O.autof=plautoflag;O.timef=pltime_f;O.sw=swdata.w;O.goals=goals;O.syncs=syncs;O.prio=prio_flag;
    O.proj=projector_flag;O.gen=generate_flag;memcpy(O.c12,ss_cur12,sizeof(ss_cur12));
    memcpy(O.p0,ss_ptr0,sizeof(ss_ptr0));memcpy(O.p4,ss_ptr4,sizeof(ss_ptr4));memcpy(O.p8,ss_ptr8,sizeof(ss_ptr8));
    scd_player_progress po=scd_player_progress_get();
    if(getenv("SS_DEBUG") && po.score!=p0.score)fprintf(stderr,"%s f%d orig +%u emy %d pl cddat %u mst %u\n",phase,cur_frame,(unsigned)(po.score-p0.score),O.emy,player.cddat,player.mstno.b.h);unsigned char oshield=plpower_b;unsigned ohits=original_hits;
    int odrawn=0;for(int k=1;k<128;k++)if(drawn[k] && r7(O.a[k].actno))odrawn++;
    /* native */
    scd_player_progress_set(p0);plpower_b=shield;plring=0;
    memcpy(actwk,N.a,sizeof(N.a));actwk[0]=player;scd_ss_host_load(N.state);
    bossflag=N.boss;plautoflag=N.autof;pltime_f=N.timef;swdata.w=N.sw;goals=N.goals;syncs=N.syncs;prio_flag=N.prio;projector_flag=N.proj;gametimer.w=(unsigned short)ticks;
    emyscorecnt=N.emy;if(!(player.cddat&2))emyscorecnt=0;
    unsigned h0=scd_objects_get().hits;
    /* COLI7: native ss_enemy_scan runs inside scd_objects_step. */
    scd_objects_step(player.xposi.w.h,player.yposi.w.h);
    unsigned nhits=scd_objects_get().hits-h0;
    {unsigned scd_ss_host_chain(void);if(getenv("SS_DEBUG") && !strcmp(phase,"follow") && cur_frame>=225 && cur_frame<=325)fprintf(stderr,"f%d in cddat %u emy %d chain %u\n",cur_frame,player.cddat,O.emy,scd_ss_host_chain());}
    if(getenv("SS_DEBUG") && scd_player_progress_get().score!=p0.score)fprintf(stderr,"%s f%d native +%u\n",phase,cur_frame,(unsigned)(scd_player_progress_get().score-p0.score));
    int ndrawn=ss_views();
    memcpy(N.a,actwk,sizeof(N.a));scd_ss_host_save(N.state);
    N.boss=bossflag;N.autof=plautoflag;N.timef=pltime_f;N.sw=swdata.w;N.goals=goals;N.syncs=syncs;N.prio=prio_flag;N.emy=emyscorecnt;N.proj=projector_flag;
    ticks++;
    for(int k=1;k<128;k++)if(r7(O.a[k].actno))states[O.a[k].actno]|=1u<<((O.a[k].r_no0/2)&31);
    {unsigned seen[256]={0};for(int k=1;k<128;k++)if(r7(O.a[k].actno) && !seen[O.a[k].actno]++)live_ticks[O.a[k].actno]++;}
    for(int k=32;k<128;k++)if(O.a[k].actno==SCD_OBJ_R7_HARI73 && O.a[k].r_no0==4){smashes++;break;}
    if(O.a[1].actno==SCD_OBJ_R7_WALL73 && O.a[1].yposi.w.h!=wall_y)wall_moves++;
    if(O.a[1].actno==SCD_OBJ_R7_EMIE7 && O.a[1].r_no0==10)amy_grabs++;
    if(O.goals)amy_goals++;
    for(int k=32;k<128;k++){if(O.a[k].actno && !nw_live[k])spawns++;if(!O.a[k].actno && nw_live[k])removals++;nw_live[k]=O.a[k].actno!=0;}
    if(odrawn!=ndrawn)fprintf(stderr,"drawn original %d native %d\n",odrawn,ndrawn);
    if(ohits!=nhits)fprintf(stderr,"hits original %u native %u\n",ohits,nhits);
    compare();REQUIRE(odrawn==ndrawn);draws+=odrawn;
    REQUIRE(ohits==nhits);hits+=ohits;
    if(scd_player_progress_get().score!=po.score)fprintf(stderr,"score original %u native %u\n",(unsigned)po.score,(unsigned)scd_player_progress_get().score);
    if(scd_player_progress_get().score!=po.score)for(int k=1;k<128;k++)if(O.a[k].actno||N.a[k].actno)fprintf(stderr," k%d o%u/%u n%u/%u pos %d,%d col %u\n",k,O.a[k].actno,O.a[k].r_no0,N.a[k].actno,N.a[k].r_no0,O.a[k].xposi.w.h,O.a[k].yposi.w.h,O.a[k].colino);
    REQUIRE(plpower_b==oshield);REQUIRE(scd_player_progress_get().score==po.score);
    REQUIRE(O.boss==N.boss);REQUIRE(O.autof==N.autof);REQUIRE(O.timef==N.timef);REQUIRE(O.sw==N.sw);
    REQUIRE(O.goals==N.goals);REQUIRE(O.syncs==N.syncs);REQUIRE(O.prio==N.prio);
    REQUIRE(O.proj==N.proj);REQUIRE(!O.gen==!scd_ss_host_good_future());
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
    char path[128];snprintf(path,sizeof(path),"assets/generated/ss7%u%c.bin",act,'A'+era);
    size_t n=read_file(path,data,sizeof(data));REQUIRE(!stage_open(&stage,data,n));
    snprintf(path,sizeof(path),"assets/generated/sscollision7%u%c.bin",act,'A'+era);
    size_t c=read_file(path,collision,sizeof(collision));
    scd_player_zone(5);scd_objects_zone(5);scd_player_act(act-1);scd_objects_act(act-1);
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
    /* HARI73's Metal Sonic stand-in: 300 to the left, running at it (tick). */
    if(placements[i].type==SCD_OBJ_R7_HARI73){
        sprite_status *m=&actwk[100];memset(m,0,sizeof(*m));
        m->actno=47;m->sprhsize=20;m->sprvsize=24;m->xposi.w.h=x-300;m->yposi.w.h=y;
    }
    memcpy(N.a,actwk,sizeof(N.a));scd_ss_host_save(N.state);
    memcpy(O.a,actwk,sizeof(O.a));memset(O.fw,0,766);O.emy=0;
    memset(O.p0,0,sizeof(O.p0));memset(O.p4,0,sizeof(O.p4));memset(O.p8,0,sizeof(O.p8));
    N.emy=0;O.prio=N.prio=0;O.boss=N.boss=0;O.autof=N.autof=0;O.timef=N.timef=1;O.sw=N.sw=0;O.goals=N.goals=0;O.syncs=N.syncs=0;
    O.proj=N.proj=0;O.gen=era==2;memset(O.c12,0,sizeof(O.c12));
    for(int k=2;k<32;k++){memset(&O.a[k],0,sizeof(O.a[k]));O.a[k].actno=250;}
    memset(nw_live,0,sizeof(nw_live));
}
static sprite_status parked(void){sprite_status p=make_player(0,0,8,0,0);p.xposi.w.h=scd_act_view_x()+8;p.yposi.w.h=scd_act_view_y()+8;return p;}
static void follow_camera(int x,int y){scd_act_camera(x-160,y-112);}
int main(void){
    state_size=scd_ss_host_size();nw_alloc(&N);nw_alloc(&N0);
    unsigned count=sizeof(placements)/sizeof(*placements);
    for(unsigned i=0;i<count;i++){
        int dup=0;
        for(unsigned j=0;j<i && !dup;j++)dup=placements[j].act==placements[i].act && placements[j].era==placements[i].era &&
            placements[j].type==placements[i].type && placements[j].sub==placements[i].sub && placements[j].flags==placements[i].flags && placements[j].sec==placements[i].sec;
        if(dup)continue;
        /* SS_ONLY=<type>: run one routine's cases (debugging). */
        if(getenv("SS_ONLY") && placements[i].type!=(unsigned)atoi(getenv("SS_ONLY")))continue;
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
                    if(!r7(base.actno))continue;
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
                                                    }
                    }
                }
                memcpy(&O,&O0,sizeof(O));nw_copy(&N,&N0);
            }
            tick(parked(),1);
        }
        /* Phase 4: a followed player: set on top of the actor, then carried
           by whatever the actor does to it, reset every 150 updates; the
           camera follows the player. */
        phase="follow";setup(i);
        sprite_status p=parked();
        for(cur_frame=0;cur_frame<600;cur_frame++){
            sprite_status *o=&N.a[1];
            if(!o->actno)break;
            if(cur_frame%150==0 || p.r_no0>=4 || p.xposi.w.h<16 || p.yposi.w.h<16)
                p=make_player(o->xposi.w.h,o->yposi.w.h-o->sprvsize-19,cur_frame%300?9:8,0,0);
            follow_camera(p.xposi.w.h,p.yposi.w.h);
            int was=p.cddat&8;
            tick(p,1);p=N.a[0];
            if(p.cddat&8)rides++;
            if(was && !(p.cddat&8))releases++;
            if(!(p.actfree[2]&128) && !(p.cddat&8))p.yposi.w.h+=2;
        }
        /* Phase 5 (Amy): the player walks up to her standing, then runs past:
           dakicheck's grab (r_no0 10), the 600-update countdown to goal_move2
           and, with Sonic in the air, Amy's jump (r_no0 14/16). */
        if(placements[i].type==SCD_OBJ_R7_EMIE7){
            for(int air=0;air<2;air++){
            phase=air?"amy air":"amy";setup(i);
            for(cur_frame=0;cur_frame<900;cur_frame++){
                sprite_status *o=&N.a[1];
                if(!o->actno)break;
                follow_camera(o->xposi.w.h,o->yposi.w.h);
                /* A rolling touch first (main_attack counts it), then Sonic
                   stands 20 away facing away from her, from alternating sides
                   (retail dakicheck grabs Sonic from behind). */
                int side=(cur_frame/150)&1;
                sprite_status q=cur_frame<60?make_player(o->xposi.w.h,o->yposi.w.h,9,0,0):
                    make_player(o->xposi.w.h+(side?-20:20),o->yposi.w.h+2,8,0,0);
                if(cur_frame>=60){q.cddat=side?1:0;q.xspeed.w=0;q.yspeed.w=0;}
                /* Sonic in the air: dakicheck makes Amy jump (tobii). */
                if(air && cur_frame>=60)q.cddat|=2;
                tick(q,1);
            }
            }
        }
        /* Phase 6 (animals, Present/Past): the projector already destroyed
           (MOVIE7 m1wait sets projector_flag), so friend_suicide lets them run. */
        if(placements[i].type==SCD_OBJ_R7_FRIEND7 && placements[i].era<2){
            phase="freed";setup(i);
            scd_ss_host_load(N.state);scd_ss_host_projector(1);scd_ss_host_save(N.state);O.proj=N.proj=255;
            for(cur_frame=0;cur_frame<600;cur_frame++){
                sprite_status *o=&N.a[1];
                if(o->actno)follow_camera(o->xposi.w.h,o->yposi.w.h);
                tick(parked(),1);
            }
        }
        phase="frameout";
        scd_act_camera(scd_act_view_x()+2000,scd_act_view_y());
        for(cur_frame=0;cur_frame<3;cur_frame++)tick(parked(),1);
    }
    static const struct{unsigned type;const char *name;uint32_t need;}names[]={
        {SCD_OBJ_R7_EMIE7,"emie7",0x1E7},{SCD_OBJ_R7_HEART7,"heart7",0x2},{SCD_OBJ_R7_HARI73,"hari73",0x6},
        {SCD_OBJ_R7_WALL73,"wall73",0x2},{SCD_OBJ_R7_GAITOU73,"gaitou73",0x6},
        {SCD_OBJ_R7_CHGBAN,"chgban",0xE},{SCD_OBJ_R7_SPRING_R,"spring_r",0x7E},{SCD_OBJ_R7_GUN7,"gun7",0xE},{SCD_OBJ_R7_HIBANA7,"hibana",0x2},
        {SCD_OBJ_R7_SLIGHT7,"slight7",0x2},{SCD_OBJ_R7_CHGWALL7,"chgwall7",0x2},{SCD_OBJ_R7_TEKKYU7,"tekkyu7",0x6},{SCD_OBJ_R7_TEKKYU7J,"tekkyu7j",0xE},
        {SCD_OBJ_R7_HOTARU7,"hotaru7",0x7FE},{SCD_OBJ_R7_KABASIRA,"kabasira",0x2},{SCD_OBJ_R7_KANABUN,"kanabun",0x2},{SCD_OBJ_R7_DANGO7,"dango",0x7FFE},{SCD_OBJ_R7_BRANKO7,"branko7",0x2},
        {SCD_OBJ_R7_FRIEND7,"friend7",0x1E},{SCD_OBJ_R7_ET7,"et7",0xE},{SCD_OBJ_R7_MOVIE7,"movie7",0x1E}};
    int ok=1;
    for(unsigned n=0;n<sizeof(names)/sizeof(*names);n++){
        uint32_t got=states[names[n].type],need=names[n].need;
        int pass=(got&need)==need && (per_type[names[n].type] || names[n].type==SCD_OBJ_R7_HEART7 || names[n].type==SCD_OBJ_R7_HIBANA7);
        printf("%s: ss %s %u cases; states %#x of %#x; %u ticks with it live\n",pass?"PASS":"FAIL",names[n].name,per_type[names[n].type],got,need,live_ticks[names[n].type]);
        ok&=pass;
    }
    REQUIRE(lifecycle_checks[SCD_OBJ_EXPLOSION]>0);REQUIRE(lifecycle_checks[SCD_OBJ_FLOWER]>0);REQUIRE(lifecycle_checks[SCD_OBJ_SCORE]>0);
    printf("PASS: original PLAYSUB lifecycle checks: explosions %u, flowers %u, points %u\n",lifecycle_checks[SCD_OBJ_EXPLOSION],lifecycle_checks[SCD_OBJ_FLOWER],lifecycle_checks[SCD_OBJ_SCORE]);
    REQUIRE(ok);REQUIRE(smashes>0);REQUIRE(wall_moves>0);REQUIRE(amy_grabs>0);REQUIRE(amy_goals>0);
    printf("PASS: ss actors %u assertions; %u cases; %u ticks; %u contact ticks; %u ridden; %u releases; %u child spawns; %u removals; %u draws; %u hits; %u kills; %u metal smashes; %u wall moves; %u amy grabs; %u amy goals; COLI7 %u player contacts\n",
           checks,cases,ticks,contacts,rides,releases,spawns,removals,draws,hits,kills,smashes,wall_moves,amy_grabs,amy_goals,colis);
    return 0;
}
