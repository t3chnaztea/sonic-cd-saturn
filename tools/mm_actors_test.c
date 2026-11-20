/* Compiled R8 originals versus objects_mm_*.inc. Two complete actor worlds
   (retail actwk[] layout and native pool + actwk[]) run the same player
   through the same updates; every live actor, the player, the score, the
   shield, player hits, bossflag, prio_flag, the projector and generator
   flags and the drawn-sprite set must match after each update. Retail
   actwkchk starts at actwk[32], so both worlds hold inert fillers in actors
   2-31 and children land in the same actor indices.
   tools/test-mm-actors.sh builds it. */
#include "EQU.H"
#include "scd_objects.h"
#include "scd_actor.h"
#include "scd_player.h"
#include "act.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "mm_ids.h"
#include "mm_orig.h"
#include "placements.h"

const uint8_t *scd_mm_host_flagwork(void);
size_t scd_mm_host_size(void);void scd_mm_host_save(void*);void scd_mm_host_load(const void*);int scd_mm_host_good_future(void);
void scarab(sprite_status*);void bigbom(sprite_status*);void anar8_81(sprite_status*);void gater8_82(sprite_status*);
void dai8(sprite_status*);void nokogiri(sprite_status*);void kuzure8(sprite_status*);void propera(sprite_status*);void kabuto(sprite_status*);
void hachi8(sprite_status*);void okusieso(sprite_status*);void haguruma(sprite_status*);void friend(sprite_status*);void et(sprite_status*);
void koma8(sprite_status*);void spring_spr(sprite_status*);void futagor8_81(sprite_status*);
void togedair8_81(sprite_status*);void togedair8_82(sprite_status*);void togedair8_83(sprite_status*);void togeita_82(sprite_status*);void togeita_83(sprite_status*);
/* Each act links its own TRAP_R8x.C (stageno.b.l is the act). */
static void togedair8_any(sprite_status *o){if(!stageno.b.l)togedair8_81(o);else if(stageno.b.l==1)togedair8_82(o);else togedair8_83(o);}
static void togeita_any(sprite_status *o){if(stageno.b.l==1)togeita_82(o);else togeita_83(o);}
/* SHOOT.C's route pointers (PC ((unsigned short**)o)[16]). */
unsigned char *mm_scarab_flag[128];unsigned char **mm_scarab_anim[128];
unsigned short *mm_ptr16[128];sprite_pattern *bariapat[1],*itempat[20];
/* BEAM.C's splash pointer (PC ((sprite_status**)o)[12]). */
sprite_status *mm_ptr12[128];
void dango(sprite_status*);void legmeca(sprite_status*);void hotaru8_c(sprite_status*);void hotaru8_d(sprite_status*);
/* Each future links its own HOTA8x.C. */
static void hotaru8_any(sprite_status *o);
/* egg8: the boss system (both worlds call it; counted per world). */
static unsigned boss_creates;
void scd_boss_create_sub(int x,int y,unsigned sub,unsigned round){if(x!=3840 || y!=316 || sub || round!=8){fprintf(stderr,"boss %d,%d %u %u\n",x,y,sub,round);exit(1);}boss_creates++;}
const uint8_t (*scd_objects_mm_room_palette(unsigned*))[4];
extern short scra_vline;
void beam(sprite_status*);void chibi_coli(sprite_status*);void jettoge(sprite_status*);void konbea83(sprite_status*);
void sw(sprite_status*);void tobira(sprite_status*);void pipe8(sprite_status*);void shooter(sprite_status*);void shut(sprite_status*);void kaiten(sprite_status*);
/* DUMMY.C pa_set; SPRING.C's other routines' pattern tables. */
void pa_set(void){}
sprite_pattern *springpat_spr[4],*springpat2_spr[4],*spring90pat_spr[4],*spring90pat2_spr[4],*spring45pat_spr[4],*spring45pat2_spr[4],*iwapat_spr[1],*komapat_spr[2];
/* Independent original PLAYSUB.C and SCORE.C child dispatch. */
void bakuha(sprite_status*);void flower(sprite_status*);void mm_original_points(sprite_status*);
/* LOADER2 divdevset (art upload) is an empty stub in the PC source. */
void divdevset(int n){(void)n;}
void branko7(sprite_status*);
void playdamagechk(sprite_status*,sprite_status*);short playdieset(sprite_status*);short pcol(sprite_status*);
/* Retail data and services the originals link against. */
PALETTEENTRY gamecolor[64];static PALETTEENTRY colorwk[64];
static unsigned goals,syncs;
void sub_sync(short n){syncs=syncs*31+(unsigned short)n;}

static unsigned lifecycle_calls[256],lifecycle_checks[256],lifecycle_frees[256],slot_reuses,kill_replays;
static unsigned char freed_slots[128];
static unsigned checks,cases,ticks,contacts,rides,releases,spawns,removals,draws,hits,kills,colis;
/* Behaviour coverage: OKUSIESO launches (main actfree[20] bit 4) and ball
   landings (bit 3), HAGURUMA drives (actfree[16]). */
static unsigned seesaw_launch,seesaw_land,gear_drive,layer_swaps,shrinks,boss_rooms,leg_steps;
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
void frameout(sprite_status *o){lifecycle_frees[o->actno]++;freed_slots[o-actwk]=1;memset(o,0,sizeof(*o));}
int actwkchk(sprite_status **pp){
    for(int i=1;i<128;i++)if(!actwk[i].actno){if(freed_slots[i])slot_reuses++;freed_slots[i]=0;*pp=&actwk[i];return 0;}
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
/* COLI8.C playdamageset without the lost-ring actor: the fixture keeps no
   rings, so the native hurt path creates none either. */
/* Only live-player hits count (native scd_objects_hurt ignores a dead
   player). */
short playdamageset(sprite_status *p,sprite_status *o){if(p->r_no0>=4)return playdieset(p);original_hits++;if(plpower_b || plring){playdamagechk(p,o);return -1;}return playdieset(p);}

static void (*const routines[256])(sprite_status*)={
    [SCD_OBJ_R8_SCARAB]=scarab,[SCD_OBJ_R8_BIGBOM]=bigbom,[SCD_OBJ_R8_GATER8]=gater8_82,[SCD_OBJ_R8_ANAR8]=anar8_81,
    [SCD_OBJ_R8_DAI8]=dai8,[SCD_OBJ_R8_NOKOGIRI]=nokogiri,[SCD_OBJ_R8_KUZURE8]=kuzure8,[SCD_OBJ_R8_PROPERA]=propera,[SCD_OBJ_R8_KABUTO]=kabuto,
    [SCD_OBJ_R8_HACHI8]=hachi8,[SCD_OBJ_R8_OKUSIESO]=okusieso,[SCD_OBJ_R8_HAGURUMA]=haguruma,[SCD_OBJ_R8_FRIEND8]=friend,[SCD_OBJ_R8_ET8]=et,
    [SCD_OBJ_R8_TOGEDAIR8]=togedair8_any,[SCD_OBJ_R8_KOMA8]=koma8,[SCD_OBJ_R8_FUTAGOR8]=futagor8_81,[SCD_OBJ_R8_TOGEITA]=togeita_any,[SCD_OBJ_R8_SPRING8]=spring_spr,
    [SCD_OBJ_R8_SW8]=sw,[SCD_OBJ_R8_TOBIRA]=tobira,[SCD_OBJ_R8_PIPE8]=pipe8,[SCD_OBJ_R8_SHOOTER]=shooter,[SCD_OBJ_R8_SHUT]=shut,[SCD_OBJ_R8_KAITEN]=kaiten,
    [SCD_OBJ_R8_BEAM]=beam,[SCD_OBJ_R8_CHIBI_COLI]=chibi_coli,[SCD_OBJ_R8_JETTOGE]=jettoge,[SCD_OBJ_R8_KONBEA83]=konbea83,[SCD_OBJ_R8_HOTARU8]=hotaru8_any,[SCD_OBJ_R8_DANGO8]=dango,[SCD_OBJ_R8_LEGMECA]=legmeca};
static int r8(unsigned t){return t<256 && routines[t];}
static void orig_tick(void){
    for(int k=1;k<128;k++){
        if(r8(actwk[k].actno))routines[actwk[k].actno](&actwk[k]);
        else if(actwk[k].actno==SCD_OBJ_EXPLOSION){lifecycle_calls[SCD_OBJ_EXPLOSION]++;bakuha(&actwk[k]);}
        else if(actwk[k].actno==SCD_OBJ_FLOWER){lifecycle_calls[SCD_OBJ_FLOWER]++;flower(&actwk[k]);}
        else if(actwk[k].actno==SCD_OBJ_SCORE){lifecycle_calls[SCD_OBJ_SCORE]++;mm_original_points(&actwk[k]);}
    }
}

/* ---- the two worlds ---- */
typedef struct{sprite_status a[128];unsigned char freed[128],fw[766],boss,autof,timef,prio,proj,gen,shut,chibi,swf[32];short emy,vline;unsigned short sw;unsigned goals,syncs,bossc;unsigned char *sc_flag[128],**sc_anim[128];unsigned short *p16[128];sprite_status *p12[128];PALETTEENTRY pal[64];}oworld;
typedef struct{sprite_status a[128];unsigned char boss,autof,timef,prio,proj,shut,chibi,swf[32];short emy,vline;unsigned bossc;unsigned short sw;unsigned goals,syncs;uint8_t *state;}nworld;
static size_t state_size;
static void nw_alloc(nworld *w){w->state=malloc(state_size);}
static void nw_copy(nworld *d,const nworld *s){uint8_t *st=d->state;memcpy(d,s,sizeof(*d));d->state=st;memcpy(st,s->state,state_size);}
static oworld O,O0;static nworld N,N0;
static int ss_views(void){
    static scd_object_view v[256];unsigned n=scd_objects_views(v,256),c=0;
    for(unsigned i=0;i<n;i++)if(r8(v[i].type))c++;
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
static void hotaru8_any(sprite_status *o){if(placements[cur_case].era==2)hotaru8_c(o);else hotaru8_d(o);}
static void tick(sprite_status player,unsigned char shield){
    last_input=player;
    int vx=scd_act_view_x();
    scd_player_progress p0=scd_player_progress_get();
    /* retail */
    memcpy(freed_slots,O.freed,sizeof(freed_slots));memcpy(actwk,O.a,sizeof(O.a));actwk[0]=player;memcpy(flagwork,O.fw,766);
    bossflag=O.boss;plautoflag=O.autof;pltime_f=O.timef;swdata.w=O.sw;goals=O.goals;syncs=O.syncs;emyscorecnt=O.emy;prio_flag=O.prio;
    generate_flag=O.gen;projector_flag=O.proj;shut_flag=O.shut;memcpy(switchflag,O.swf,32);memcpy(mm_scarab_flag,O.sc_flag,sizeof(mm_scarab_flag));memcpy(mm_scarab_anim,O.sc_anim,sizeof(mm_scarab_anim));memcpy(mm_ptr16,O.p16,sizeof(mm_ptr16));memcpy(mm_ptr12,O.p12,sizeof(mm_ptr12));chibi_flag=O.chibi;scra_vline=O.vline;boss_creates=O.bossc;memcpy(colorwk,O.pal,sizeof(colorwk));lpcolorwk=colorwk;gametimer.w=(unsigned short)ticks;
    {unsigned e=placements[cur_case].era;time_flag=e==0?1:e==1?0:2;}stageno.b.l=(unsigned char)(placements[cur_case].act-1);
    scra_h_posit.w.h=(short)vx;scra_v_posit.w.h=(short)scd_act_view_y();memset(drawn,0,sizeof(drawn));original_hits=0;plpower_b=shield;plring=0;
    if(!(player.cddat&2))emyscorecnt=0;
    /* PLAYER.C runs COLI8.C pcol before the object pass. */
    if(player.r_no0<4){sprite_status before=actwk[0];pcol(actwk);if(memcmp(&before,&actwk[0],sizeof(before)))colis++;}
    orig_tick();
    memcpy(O.freed,freed_slots,sizeof(freed_slots));memcpy(O.a,actwk,sizeof(O.a));memcpy(O.fw,flagwork,766);O.emy=emyscorecnt;
    O.boss=bossflag;O.autof=plautoflag;O.timef=pltime_f;O.sw=swdata.w;O.goals=goals;O.syncs=syncs;O.prio=prio_flag;
    O.proj=projector_flag;O.gen=generate_flag;O.shut=shut_flag;memcpy(O.swf,switchflag,32);memcpy(O.sc_flag,mm_scarab_flag,sizeof(mm_scarab_flag));memcpy(O.sc_anim,mm_scarab_anim,sizeof(mm_scarab_anim));memcpy(O.p16,mm_ptr16,sizeof(mm_ptr16));memcpy(O.p12,mm_ptr12,sizeof(mm_ptr12));O.chibi=chibi_flag;O.vline=scra_vline;O.bossc=boss_creates;memcpy(O.pal,colorwk,sizeof(colorwk));
    scd_player_progress po=scd_player_progress_get();
    if(getenv("MM_DEBUG") && po.score!=p0.score)fprintf(stderr,"%s f%d orig +%u emy %d pl cddat %u mst %u\n",phase,cur_frame,(unsigned)(po.score-p0.score),O.emy,player.cddat,player.mstno.b.h);unsigned char oshield=plpower_b;unsigned ohits=original_hits;
    int odrawn=0;for(int k=1;k<128;k++)if(drawn[k] && r8(O.a[k].actno))odrawn++;
    /* native */
    scd_player_progress_set(p0);plpower_b=shield;plring=0;
    memcpy(actwk,N.a,sizeof(N.a));actwk[0]=player;scd_mm_host_load(N.state);
    bossflag=N.boss;plautoflag=N.autof;pltime_f=N.timef;swdata.w=N.sw;goals=N.goals;syncs=N.syncs;prio_flag=N.prio;projector_flag=N.proj;shut_flag=N.shut;memcpy(switchflag,N.swf,32);chibi_flag=N.chibi;scra_vline=N.vline;boss_creates=N.bossc;gametimer.w=(unsigned short)ticks;
    emyscorecnt=N.emy;if(!(player.cddat&2))emyscorecnt=0;
    unsigned h0=scd_objects_get().hits;
    /* COLI8: native mm_enemy_scan runs inside scd_objects_step. */
    scd_objects_step(player.xposi.w.h,player.yposi.w.h);
    unsigned nhits=scd_objects_get().hits-h0;
    if(getenv("MM_DEBUG") && scd_player_progress_get().score!=p0.score)fprintf(stderr,"%s f%d native +%u\n",phase,cur_frame,(unsigned)(scd_player_progress_get().score-p0.score));
    int ndrawn=ss_views();
    memcpy(N.a,actwk,sizeof(N.a));scd_mm_host_save(N.state);
    N.boss=bossflag;N.autof=plautoflag;N.timef=pltime_f;N.sw=swdata.w;N.goals=goals;N.syncs=syncs;N.prio=prio_flag;N.emy=emyscorecnt;N.proj=projector_flag;N.shut=shut_flag;memcpy(N.swf,switchflag,32);N.chibi=chibi_flag;N.vline=scra_vline;N.bossc=boss_creates;
    ticks++;
    for(int k=1;k<128;k++)if(r8(O.a[k].actno))states[O.a[k].actno]|=1u<<((O.a[k].r_no0/2)&31);
    {unsigned seen[256]={0};for(int k=1;k<128;k++)if(r8(O.a[k].actno) && !seen[O.a[k].actno]++)live_ticks[O.a[k].actno]++;}
    {static unsigned char last_prio,last_chibi;if(cur_frame && O.prio!=last_prio)layer_swaps++;last_prio=O.prio;if(cur_frame && O.chibi!=last_chibi)shrinks++;last_chibi=O.chibi;}
    for(int k=1;k<128;k++){
        const sprite_status *a=&O.a[k];
        if(a->actno==SCD_OBJ_R8_OKUSIESO && !(a->actfree[20]&3)){if(a->actfree[20]&16)seesaw_launch++;if(a->actfree[20]&8)seesaw_land++;}
        if(a->actno==SCD_OBJ_R8_HAGURUMA && a->actfree[16])gear_drive++;
        if(a->actno==SCD_OBJ_R8_LEGMECA && !a->userflag.b.h && a->actfree[0]>=6)leg_steps++;
    }
    for(int k=32;k<128;k++){if(O.a[k].actno && !nw_live[k])spawns++;if(!O.a[k].actno && nw_live[k])removals++;nw_live[k]=O.a[k].actno!=0;}
    if(odrawn!=ndrawn)fprintf(stderr,"drawn original %d native %d\n",odrawn,ndrawn);
    if(ohits!=nhits)fprintf(stderr,"hits original %u native %u\n",ohits,nhits);
    compare();REQUIRE(odrawn==ndrawn);draws+=odrawn;
    REQUIRE(ohits==nhits);hits+=ohits;
    if(scd_player_progress_get().score!=po.score)fprintf(stderr,"score original %u native %u\n",(unsigned)po.score,(unsigned)scd_player_progress_get().score);
    if(scd_player_progress_get().score!=po.score)for(int k=1;k<128;k++)if(O.a[k].actno||N.a[k].actno)fprintf(stderr," k%d o%u/%u n%u/%u pos %d,%d col %u\n",k,O.a[k].actno,O.a[k].r_no0,N.a[k].actno,N.a[k].r_no0,O.a[k].xposi.w.h,O.a[k].yposi.w.h,O.a[k].colino);
    REQUIRE(plpower_b==oshield);REQUIRE(scd_player_progress_get().score==po.score);
    REQUIRE(O.boss==N.boss);REQUIRE(O.autof==N.autof);REQUIRE(O.timef==N.timef);REQUIRE(O.sw==N.sw);
    REQUIRE(O.syncs==N.syncs);REQUIRE(O.prio==N.prio);
    REQUIRE(!memcmp(O.fw,scd_mm_host_flagwork(),sizeof(O.fw)));
    REQUIRE(O.proj==N.proj);REQUIRE(O.shut==N.shut);REQUIRE(O.chibi==N.chibi);REQUIRE(O.vline==N.vline);REQUIRE(O.bossc==N.bossc);
    {const uint8_t (*np)[4]=scd_objects_mm_room_palette(0);for(int c=49;c<64;c++)if(memcmp(&O.pal[c],np[c],4)){fprintf(stderr,"palette %d\n",c);REQUIRE(0);}}REQUIRE(!memcmp(O.swf,N.swf,32));REQUIRE(!O.gen==!scd_mm_host_good_future());
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
    char path[128];snprintf(path,sizeof(path),"assets/generated/mm8%u%c.bin",act,'A'+era);
    size_t n=read_file(path,data,sizeof(data));REQUIRE(!stage_open(&stage,data,n));
    snprintf(path,sizeof(path),"assets/generated/mmcollision8%u%c.bin",act,'A'+era);
    size_t c=read_file(path,collision,sizeof(collision));
    scd_player_zone(6);scd_objects_zone(6);scd_player_act(act-1);scd_objects_act(act-1);
    REQUIRE(!scd_player_init(&stage,collision,c,era));
    loaded_act=act;loaded_era=era;
}
static void setup(unsigned i){
    load(placements[i].act,placements[i].era);
    unsigned era=placements[i].era;
    scd_objects_reset(era,0);editmode.w=0;memset(freed_slots,0,sizeof(freed_slots));
    memset(flagwork,0,sizeof(flagwork));
    int x=placements[i].x,y=placements[i].y;
    scd_act_camera(x-160,y-112);
    REQUIRE(scd_objects_spawn(placements[i].type,x,y,placements[i].sub,placements[i].flags)==0);
    actwk[1].userflag.b.l=placements[i].sec;
    for(int k=0;k<30;k++)REQUIRE(scd_objects_spawn(SCD_OBJ_LOG_SHADOW,x,y,era<2?0:1,0)==k+1);
    memcpy(N.a,actwk,sizeof(N.a));scd_mm_host_save(N.state);
    memset(O.freed,0,sizeof(O.freed));memcpy(O.a,actwk,sizeof(O.a));memset(O.fw,0,766);O.emy=0;
    N.emy=0;O.prio=N.prio=0;O.boss=N.boss=0;O.autof=N.autof=0;O.timef=N.timef=1;O.sw=N.sw=0;O.goals=N.goals=0;O.syncs=N.syncs=0;
    O.proj=N.proj=0;O.gen=era==2;O.shut=N.shut=0;O.chibi=N.chibi=0;O.vline=N.vline=0;O.bossc=N.bossc=0;memset(O.pal,0,sizeof(O.pal));memset(O.p12,0,sizeof(O.p12));memset(O.swf,0,32);memset(N.swf,0,32);memset(O.p16,0,sizeof(O.p16));bossstart=0;
    for(int k=2;k<32;k++){memset(&O.a[k],0,sizeof(O.a[k]));O.a[k].actno=250;}
    memset(nw_live,0,sizeof(nw_live));
}
static sprite_status parked(void){sprite_status p=make_player(0,0,8,0,0);p.xposi.w.h=scd_act_view_x()+8;p.yposi.w.h=scd_act_view_y()+8;return p;}
static void follow_camera(int x,int y){scd_act_camera(x-160,y-112);}
int main(void){
    state_size=scd_mm_host_size();nw_alloc(&N);nw_alloc(&N0);
    unsigned count=sizeof(placements)/sizeof(*placements);
    for(unsigned i=0;i<count;i++){
        int dup=0;
        for(unsigned j=0;j<i && !dup;j++)dup=placements[j].act==placements[i].act && placements[j].era==placements[i].era &&
            placements[j].type==placements[i].type && placements[j].sub==placements[i].sub && placements[j].flags==placements[i].flags && placements[j].sec==placements[i].sec;
        if(dup)continue;
        /* MM_ONLY=<type>: run one routine's cases (debugging). */
        if(getenv("MM_ONLY") && placements[i].type!=(unsigned)atoi(getenv("MM_ONLY")))continue;
        unsigned replayed_kill=0;
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
                    if(!r8(base.actno))continue;
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
                            if(before!=SCD_OBJ_EXPLOSION && O.a[k].actno==SCD_OBJ_EXPLOSION){
                                kills++;
                                /* Keep the first actual COLI8 kill in each case
                                   alive for 80 more updates: score deletion and
                                   explosion-to-flower cannot hide in one-tick contacts. */
                                if(!replayed_kill++){
                                    kill_replays++;
                                    for(unsigned life=0;life<80;life++)tick(parked(),1);
                                }
                            }
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
            /* A player a shooter holds (actfree[2] bit 0) stays: PLAYER.C keeps
               his mspeed for the ride. */
            if(!(p.actfree[2]&1) && (cur_frame%150==0 || p.r_no0>=4 || p.xposi.w.h<16 || p.yposi.w.h<16))
                p=make_player(o->xposi.w.h,o->yposi.w.h-o->sprvsize-19,cur_frame%300?9:8,0,0);
            follow_camera(p.xposi.w.h,p.yposi.w.h);
            int was=p.cddat&8;
            tick(p,1);p=N.a[0];
            if(p.cddat&8)rides++;
            if(was && !(p.cddat&8))releases++;
            if(!(p.actfree[2]&128) && !(p.cddat&8))p.yposi.w.h+=2;
        }
        /* Phase 5 (R82 traps): the follow run again on the upper layer
           (prio_flag set), which R82's harir8 and tokusyu block read. */
        if(placements[i].type==SCD_OBJ_R8_TOGEDAIR8 && placements[i].act==2){
            phase="prio";setup(i);O.prio=N.prio=1;
            sprite_status q=parked();
            for(cur_frame=0;cur_frame<300;cur_frame++){
                sprite_status *o=&N.a[1];
                if(!o->actno)break;
                if(cur_frame%100==0 || q.r_no0>=4)q=make_player(o->xposi.w.h,o->yposi.w.h-o->sprvsize-19,8,0,0);
                follow_camera(q.xposi.w.h,q.yposi.w.h);
                tick(q,1);q=N.a[0];
                if(!(q.actfree[2]&128) && !(q.cddat&8))q.yposi.w.h+=2;
            }
        }
        /* Phase 6: the switch a pipe shutter listens to is pressed at update
           120 and released at 240 (SW8 sets bit 7, clears it on release). */
        if(placements[i].type==SCD_OBJ_R8_PIPE8){
            phase="switch";setup(i);
            unsigned s=placements[i].sub&31;
            for(cur_frame=0;cur_frame<400;cur_frame++){
                if(cur_frame==120){O.swf[s]|=192;N.swf[s]|=192;}
                if(cur_frame==240){O.swf[s]&=127;N.swf[s]&=127;}
                sprite_status *o=&N.a[1];
                if(!o->actno)break;
                follow_camera(o->xposi.w.h,o->yposi.w.h);
                /* Updates 20-99: the player rises through the shutter (x+24)
                   with the switch still off: it opens and closes behind him. */
                sprite_status r=make_player(o->xposi.w.h-100,o->yposi.w.h,8,0,0);
                if(cur_frame>=20 && cur_frame<100){r=make_player(o->xposi.w.h+24,o->yposi.w.h+60-(cur_frame-20)*3,8,0,0);r.yspeed.w=-768;r.cddat|=2;}
                tick(r,1);
            }
        }
        /* Phase 6b (shoot_s junctions): once the player is held, the pad
           points right, then up (swdata1). */
        if(placements[i].type==SCD_OBJ_R8_SHOOTER && placements[i].sub==128){
            phase="junction";setup(i);
            sprite_status q=parked();
            for(cur_frame=0;cur_frame<300;cur_frame++){
                sprite_status *o=&N.a[1];
                if(!o->actno)break;
                if(cur_frame%100==0 && !(q.actfree[2]&1))q=make_player(o->xposi.w.h,o->yposi.w.h,8,0,0);
                swdata1.w=cur_frame%100>=40?(cur_frame<150?8:1):0;
                follow_camera(q.xposi.w.h,q.yposi.w.h);
                tick(q,1);q=N.a[0];
            }
            swdata1.w=0;
        }
        /* Phase 7: the boss starts (bossstart bit 7): the shutter closes. */
        if(placements[i].type==SCD_OBJ_R8_SHUT){
            phase="boss";setup(i);
            for(cur_frame=0;cur_frame<200;cur_frame++){
                if(cur_frame==20)bossstart=128;
                sprite_status *o=&N.a[1];
                if(!o->actno)break;
                follow_camera(o->xposi.w.h,o->yposi.w.h);
                tick(parked(),1);
            }
            bossstart=0;
            /* shut_move wrote blocks into the shared stage: reload it. */
            loaded_act=99;
        }
        /* Phase 8 (kaiten): stand centred on the floor; once it holds the
           player (mstno 51/52) his turn animation ends after 40 updates
           (mstno 5), as PLAYER.C does. */
        if(placements[i].type==SCD_OBJ_R8_KAITEN){
            phase="kaiten";setup(i);
            sprite_status q=parked();int held=0;
            for(cur_frame=0;cur_frame<600;cur_frame++){
                sprite_status *o=&N.a[1];
                if(!o->actno)break;
                if(cur_frame%200==0){q=make_player(o->xposi.w.h,o->yposi.w.h-o->sprvsize-19,8,0,0);q.yspeed.w=0;held=0;}
                if(q.mstno.b.h==51 || q.mstno.b.h==52){if(++held==40)q.mstno.b.h=5;}
                follow_camera(q.xposi.w.h,q.yposi.w.h);
                tick(q,1);q=N.a[0];
                if(!(q.cddat&8) && !(q.actfree[2]&1))q.yposi.w.h+=1;
            }
        }
        /* Phase 9 (HOTA8 room): the player walks in (x 3120) and rolls into
           each firefly it releases until the room starts the boss. */
        if(placements[i].type==SCD_OBJ_R8_HOTARU8){
            phase="room";setup(i);
            for(cur_frame=0;cur_frame<4000;cur_frame++){
                sprite_status q=make_player(3120,420,8,0,0);
                for(int k=2;k<128;k++){const sprite_status *h=&N.a[k];
                    if(h->actno==SCD_OBJ_R8_HOTARU8 && (int8_t)h->userflag.b.h>=0 && h->colino){q=make_player(h->xposi.w.h,h->yposi.w.h,9,0,0);break;}}
                scd_act_camera(3120-160,400-112);
                tick(q,1);
                if(O.bossc){boss_rooms++;break;}
            }
        }
        phase="frameout";
        scd_act_camera(scd_act_view_x()+2000,scd_act_view_y());
        for(cur_frame=0;cur_frame<3;cur_frame++)tick(parked(),1);
    }
    static const struct{unsigned type;const char *name;uint32_t need;}names[]={
        {SCD_OBJ_R8_SCARAB,"scarab",0x6},{SCD_OBJ_R8_BIGBOM,"bigbom",0xBFE},{SCD_OBJ_R8_GATER8,"gater8",0},{SCD_OBJ_R8_ANAR8,"anar8",0x6},
        {SCD_OBJ_R8_DAI8,"dai8",0x1E},{SCD_OBJ_R8_NOKOGIRI,"nokogiri",0x1E},{SCD_OBJ_R8_KUZURE8,"kuzure8",0x1E},
        {SCD_OBJ_R8_PROPERA,"propera",0x156},{SCD_OBJ_R8_KABUTO,"kabuto",0x6},
        {SCD_OBJ_R8_HACHI8,"hachi8",0x2},{SCD_OBJ_R8_OKUSIESO,"okusieso",0x2},{SCD_OBJ_R8_HAGURUMA,"haguruma",0x2},
        {SCD_OBJ_R8_FRIEND8,"friend8",0x2},{SCD_OBJ_R8_ET8,"et8",0xE},
        {SCD_OBJ_R8_TOGEDAIR8,"togedair8",0x2},{SCD_OBJ_R8_KOMA8,"koma8",0x6},{SCD_OBJ_R8_FUTAGOR8,"futagor8",0x2},{SCD_OBJ_R8_TOGEITA,"togeita",0x6},
        {SCD_OBJ_R8_SPRING8,"spring8",0x6},
        {SCD_OBJ_R8_SW8,"sw8",0x2},{SCD_OBJ_R8_TOBIRA,"tobira",0x1E},{SCD_OBJ_R8_PIPE8,"pipe8",0x7E},{SCD_OBJ_R8_SHOOTER,"shooter",0x5},
        {SCD_OBJ_R8_SHUT,"shut",0x6},{SCD_OBJ_R8_KAITEN,"kaiten",0x36},
        {SCD_OBJ_R8_BEAM,"beam",0x1E},{SCD_OBJ_R8_CHIBI_COLI,"chibi_coli",0x2},{SCD_OBJ_R8_JETTOGE,"jettoge",0x2},{SCD_OBJ_R8_KONBEA83,"konbea83",0xE},{SCD_OBJ_R8_HOTARU8,"hotaru8",0x7F},{SCD_OBJ_R8_DANGO8,"dango8",0x7FFE},{SCD_OBJ_R8_LEGMECA,"legmeca",0x7}};
    int ok=1;
    for(unsigned n=0;n<sizeof(names)/sizeof(*names);n++){
        if(getenv("MM_ONLY") && names[n].type!=(unsigned)atoi(getenv("MM_ONLY")))continue;
        uint32_t got=states[names[n].type],need=names[n].need;
        /* spring8 is only spawned (koma8, togedair8). */
        int pass=(got&need)==need && (per_type[names[n].type] || names[n].type==SCD_OBJ_R8_SPRING8);
        printf("%s: mm %s %u cases; states %#x of %#x; %u ticks with it live\n",pass?"PASS":"FAIL",names[n].name,per_type[names[n].type],got,need,live_ticks[names[n].type]);
        ok&=pass;
    }
    printf("coverage: %u seesaw launch ticks; %u seesaw landed ticks; %u gear drive ticks; %u kaiten layer swaps; %u shrink toggles\n",seesaw_launch,seesaw_land,gear_drive,layer_swaps,shrinks);
    REQUIRE(!per_type[SCD_OBJ_R8_BEAM] || shrinks);
    printf("coverage: %u boss rooms reached egg8 (scd_boss_create_sub(3840,316,0,8))\n",boss_rooms);
    REQUIRE(!per_type[SCD_OBJ_R8_HOTARU8] || boss_rooms);
    printf("coverage: %u legmeca ticks on its second leg\n",leg_steps);REQUIRE(!per_type[SCD_OBJ_R8_LEGMECA] || leg_steps);
    REQUIRE(!per_type[SCD_OBJ_R8_KAITEN] || layer_swaps);
    REQUIRE(!per_type[SCD_OBJ_R8_OKUSIESO] || (seesaw_launch && seesaw_land));REQUIRE(!per_type[SCD_OBJ_R8_HAGURUMA] || gear_drive);
    REQUIRE(ok);
    if(!getenv("MM_ONLY")){REQUIRE(lifecycle_checks[SCD_OBJ_EXPLOSION]>0);REQUIRE(lifecycle_checks[SCD_OBJ_FLOWER]>0);REQUIRE(lifecycle_checks[SCD_OBJ_SCORE]>0);}
    printf("PASS: original MM PLAYSUB dispatch calls explosions %u, flowers %u, points %u; independent slot checks %u/%u/%u\n",lifecycle_calls[24],lifecycle_calls[31],lifecycle_calls[28],lifecycle_checks[24],lifecycle_checks[31],lifecycle_checks[28]);
    printf("PASS: original MM kill lifetime replays %u\n",kill_replays);
    printf("PASS: original MM frees explosions %u, points %u; reused slots %u\n",lifecycle_frees[24],lifecycle_frees[28],slot_reuses);
    if(!getenv("MM_ONLY")){REQUIRE(lifecycle_frees[24]>0);REQUIRE(lifecycle_frees[28]>0);REQUIRE(slot_reuses>0);REQUIRE(kill_replays>0);}
    printf("PASS: mm actors %u assertions; %u cases; %u ticks; %u contact ticks; %u ridden; %u releases; %u child spawns; %u removals; %u draws; %u hits; %u kills; COLI8 %u player contacts\n",
           checks,cases,ticks,contacts,rides,releases,spawns,removals,draws,hits,kills,colis);
    return 0;
}
