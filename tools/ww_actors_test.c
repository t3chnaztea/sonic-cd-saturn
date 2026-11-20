/* Compiled R6 originals versus objects_ww_*.inc. Two complete actor worlds
   (retail actwk[] layout and native pool + actwk[]) run the same player
   through the same updates; every live actor, the player, the score, the
   shield, player hits, colrevflag, the projector and generator flags and the
   drawn-sprite set must match after each update. Retail actwkchk starts at
   actwk[32], so both worlds hold inert fillers in actors 2-31 and children
   land in the same actor indices. tools/test-ww-actors.sh builds it. */
#include "EQU.H"
#include "scd_objects.h"
#include "scd_actor.h"
#include "scd_player.h"
#include "act.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "ww_orig.h"
#include "placements.h"

uint64_t scd_objects_ww_palette(uint16_t*,uint64_t*);
void sub_sync(short r){(void)r;}
/* LOADER2.C divdevset is an empty stub natively too. */
void divdevset(int p){(void)p;}
/* PLAYSUB.C's bakuha is linked but not dispatched by this fixture. */
void baku_init(sprite_status *o){(void)o;}
static unsigned char ring_seen[128];static unsigned ring_spawns;
/* COL6A/B clchgcnt[3] drives both worlds: the fixture cycles it (tick). */
unsigned scd_r6_palette_count(unsigned s){return clchgcnt[s];}
size_t scd_ww_host_size(void);void scd_ww_host_save(void*);void scd_ww_host_load(const void*);int scd_ww_host_good_future(void);
#define X(f,id) void f(sprite_status*);
#include "ported.h"
#undef X
void playdamagechk(sprite_status*,sprite_status*);short playdieset(sprite_status*);short pcol(sprite_status*);
short emycol_d(sprite_status*);
void *ww_ptr[4][128];

static unsigned orbits,orbit_jumps,checks,cases,ticks,contacts,rides,releases,spawns,removals,draws,hits,kills,belt_flips,shots,captures,breaks,colis;
static unsigned per_type[256];static uint32_t states[256];
static unsigned retail_point_spawns,retail_point_checks,retail_flower_checks;
static unsigned cur_case;static int cur_frame;static const char *phase="";
static sprite_status last_input;
#define REQUIRE(v) do{checks++;if(!(v)){fprintf(stderr,"input xy=%d,%d r=%u mst=%u cddat=%u ys=%d xs=%d af2=%u w26=%u\n",last_input.xposi.w.h,last_input.yposi.w.h,last_input.r_no0,last_input.mstno.b.h,last_input.cddat,last_input.yspeed.w,last_input.xspeed.w,last_input.actfree[2],(unsigned)scd_word_get(&last_input,26));fprintf(stderr,"FAIL case %u type %u sub %u act %u era %u (%s) frame %d line %d: %s\n",cur_case,placements[cur_case].type,placements[cur_case].sub,placements[cur_case].act,placements[cur_case].era,phase,cur_frame,__LINE__,#v);exit(1);}}while(0)

/* ---- retail helpers (ACTION.C, ACTSET.C, SCORE.C, COLI6.C) ---- */
static unsigned char drawn[128];static unsigned original_hits;
void actionsub(sprite_status *o){
    /* A cleared actor draws nothing; its slot may be refilled later in
       the same update by an actor that does not draw until the next one. */
    o->actflg&=127;if(!o->actno)return;
    drawn[o-actwk]=1;
    int16_t x=o->xposi.w.h-scd_act_view_x(),y=o->yposi.w.h;
    int cy=scd_act_view_y();
    if(x+o->sprhsize<0 || x-o->sprhsize>=320)return;
    if((uint16_t)cy<256){if((uint16_t)y>=2048)y-=2048;}
    else if((uint16_t)cy>=1792 && (uint16_t)y<256)y+=2048;
    y-=cy;if(y+o->sprvsize<0 || y-o->sprvsize>=224)return;
    o->actflg|=128;
}
void frameout(sprite_status *o){memset(o,0,sizeof(*o));}
/* Retail searches to actwk[127]; the native pool ends at actor
   SCD_OBJECT_CAPACITY (96). Both worlds use the native bound so a dense
   scene (gas ice shards) fails alike instead of diverging. */
int actwkchk(sprite_status **pp){
    for(int i=32;i<=SCD_OBJECT_CAPACITY;i++)if(!actwk[i].actno){*pp=&actwk[i];return 0;}
    return -1;
}
int actwkchk2(sprite_status *o,sprite_status **pp){
    for(sprite_status *n=o+1;n<=&actwk[SCD_OBJECT_CAPACITY];n++)if(!n->actno){*pp=n;return 0;}
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
/* COLI6.C playdamageset without the lost-ring actor: the fixture keeps no
   rings, so the native hurt path creates none either. */
short playdamageset(sprite_status *p,sprite_status *o){original_hits++;p->actfree[0]=0;p->actfree[2]&=231;((short*)p)[33]=0;
    if(plpower_b || plring || debugflag.w){playdamagechk(p,o);return -1;}return playdieset(p);}

static void (*const routines[256])(sprite_status*)={
#define X(f,id) [id]=f,
#include "ported.h"
#undef X
};
static int r6(unsigned t){return t<256 && routines[t];}
/* PLAYSUB.C tensuu_set/tensuu0 and SCORE.C ten_init/ten_move. The PC R6
   actor set omits IDs 24/28/31, so use the retail routines' observable
   spawn, position, frame and lifetime here. Other actors still run their
   independently compiled PC originals. */
static void retail_points(sprite_status *o){
    if(!o->r_no1){sprite_status *p;
        if(!actwkchk(&p)){
            p->actno=SCD_OBJ_SCORE;p->xposi.w.h=o->xposi.w.h;
            p->yposi.w.h=o->yposi.w.h;
            p->userflag.b.h=(char)(((uint8_t)scd_word_get(o,33)>>1)|128);
            retail_point_spawns++;
        }
    }
}
static void retail_common_actor(sprite_status *o){
    if(o->actno==SCD_OBJ_EXPLOSION){
        if(!o->r_no0){retail_points(o);o->r_no0=2;o->colino=0;}
        /* TBL1.C bakuchg has five frames at four ticks each, then $FC;
           baku_die converts a killed enemy to a flower on the next tick. */
        if(++o->actfree[23]>21){
            if(o->r_no1)frameout(o);
            else{o->actno=SCD_OBJ_FLOWER;o->r_no0=0;}
        }
    }else if(o->actno==SCD_OBJ_SCORE){
        if(!o->r_no0){o->r_no0=2;o->actflg=4;
            o->patno=o->userflag.b.h&127;o->actfree[0]=24;}
        if(!--o->actfree[0])frameout(o);
        else o->yposi.w.h-=2;
    }else if(o->actno==SCD_OBJ_FLOWER){
        /* PLAYSUB.C flow_init/flow_move0: a badnik flower falls two pixels
           per update until the retail floor probe finds the ground. */
        if(!o->r_no0){o->r_no0=2;o->sprvsize=0;}
        if(o->r_no0==2){short d=emycol_d(o);
            if(d<0){o->yposi.w.h+=d;o->r_no0=4;o->sprvsize=48;}
            else o->yposi.w.h+=2;
        }
    }
}
static void orig_tick(void){
    for(int k=1;k<128;k++){
        if(r6(actwk[k].actno))routines[actwk[k].actno](&actwk[k]);
        else if(actwk[k].actno==SCD_OBJ_EXPLOSION || actwk[k].actno==SCD_OBJ_SCORE || actwk[k].actno==SCD_OBJ_FLOWER)
            retail_common_actor(&actwk[k]);
    }
}

/* ---- the two worlds ---- */
typedef struct{sprite_status a[128];unsigned char fw[766],colrev,proj,gen;short emy;void *ptr[4][128];PALETTEENTRY pal[2][64];unsigned char st6,sw[32];short gt;int ranum;}oworld;
typedef struct{sprite_status a[128];unsigned char colrev,proj;uint8_t *state;}nworld;
static size_t state_size;
static void nw_alloc(nworld *w){w->state=malloc(state_size);}
static void nw_copy(nworld *d,const nworld *s){uint8_t *st=d->state;memcpy(d,s,sizeof(*d));d->state=st;memcpy(st,s->state,state_size);}
static oworld O,O0;static nworld N,N0;
static int ww_views(void){
    static scd_object_view v[256];unsigned n=scd_objects_views(v,256),c=0;
    for(unsigned i=0;i<n;i++)if(r6(v[i].type))c++;
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
static int trace_actor=-1;
static void compare(void){
    if(trace_actor>0 && (O.a[trace_actor].actno || N.a[trace_actor].actno)){const sprite_status *a=&O.a[trace_actor],*b=&N.a[trace_actor];
        fprintf(stderr,"%s %d o:%u r%u y%d.%d af",phase,cur_frame,a->actno,a->r_no0,a->yposi.w.h,(uint16_t)a->yposi.w.l);for(int q=0;q<24;q++)fprintf(stderr," %02x",a->actfree[q]);
        fprintf(stderr," | n:%u r%u y%d.%d af",b->actno,b->r_no0,b->yposi.w.h,(uint16_t)b->yposi.w.l);for(int q=0;q<24;q++)fprintf(stderr," %02x",b->actfree[q]);fprintf(stderr,"\n");}
    if(memcmp(&O.a[0],&N.a[0],sizeof(sprite_status)))player_diff(&O.a[0],&N.a[0]);
    REQUIRE(!memcmp(&O.a[0],&N.a[0],sizeof(sprite_status)));
    for(int k=1;k<128;k++){
        if(k>=2 && k<32)continue;
        sprite_status *a=&O.a[k],*b=&N.a[k];
        /* The independently sourced ID 24/28/31 path checks slot, position,
           score frame, and lifetime. PC R6 has no compiled routine for it. */
        if(a->actno==SCD_OBJ_SCORE || b->actno==SCD_OBJ_SCORE){
            retail_point_checks++;
            REQUIRE(a->actno==b->actno);
            REQUIRE(a->xposi.w.h==b->xposi.w.h);
            REQUIRE(a->yposi.w.h==b->yposi.w.h);
            REQUIRE(a->userflag.b.h==b->userflag.b.h);
            continue;
        }
        if(a->actno==SCD_OBJ_EXPLOSION && b->actno==SCD_OBJ_EXPLOSION)continue;
        if(a->actno==SCD_OBJ_FLOWER || b->actno==SCD_OBJ_FLOWER){
            retail_flower_checks++;
            if(a->actno!=b->actno || a->xposi.w.h!=b->xposi.w.h || a->yposi.w.h!=b->yposi.w.h)
                fprintf(stderr,"flower slot %d original %u (%d,%d) r%u native %u (%d,%d) r%u\n",k,a->actno,a->xposi.w.h,a->yposi.w.h,a->r_no0,b->actno,b->xposi.w.h,b->yposi.w.h,b->r_no0);
            REQUIRE(a->actno==b->actno);
            REQUIRE(a->xposi.w.h==b->xposi.w.h);
            REQUIRE(a->yposi.w.h==b->yposi.w.h);
            continue;
        }
        /* Flyrings (actor 17): the native lost ring runs them; the retail one
           is checked at its spawn (position, speeds) and then left idle. */
        if(a->actno!=SCD_OBJ_LOST_RING)ring_seen[k]=0;
        if(a->actno==SCD_OBJ_LOST_RING && !ring_seen[k]){ring_seen[k]=1;ring_spawns++;REQUIRE(b->actno==SCD_OBJ_LOST_RING);
            if(a->xposi.w.h!=b->xposi.w.h || a->yposi.w.h!=b->yposi.w.h || a->xspeed.w!=b->xspeed.w || a->yspeed.w!=b->yspeed.w)fprintf(stderr,"ring %d original %d,%d %d,%d native %d,%d %d,%d ranum %d\n",k,a->xposi.w.h,a->yposi.w.h,a->xspeed.w,a->yspeed.w,b->xposi.w.h,b->yposi.w.h,b->xspeed.w,b->yspeed.w,O.ranum);
            /* A ring spawned into a later slot already took its first native
               lost-ring step (as the retail flyring would); undo that step. */
            {short ys=b->yspeed.w-24;int32_t x0=b->xposi.l-(int32_t)b->xspeed.w*256,y0=b->yposi.l-(int32_t)ys*256;
             int now=a->xposi.w.h==b->xposi.w.h && a->yposi.w.h==b->yposi.w.h && a->xspeed.w==b->xspeed.w && a->yspeed.w==b->yspeed.w;
             int back=a->xposi.w.h==(short)(x0>>16) && a->yposi.w.h==(short)(y0>>16) && a->xspeed.w==b->xspeed.w && a->yspeed.w==ys;
             REQUIRE(now || back);}continue;}
        if(a->actno==SCD_OBJ_LOST_RING && !b->actno){memset(a,0,sizeof(*a));ring_seen[k]=0;continue;}
        if(b->actno==SCD_OBJ_LOST_RING && (a->actno==SCD_OBJ_LOST_RING || !a->actno))continue;
        if(b->actno==SCD_OBJ_EXPLOSION && (a->actno==SCD_OBJ_EXPLOSION || !a->actno))continue;
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
/* A switch the fixture holds pressed in both worlds (-1: none). */
static int forced_switch=-1;
static void tick(sprite_status player,unsigned char shield){
    /* A routing shooter (r_no0 4/6) owns the player: shootermove set
       mspeed 2048 and PLAYER6 leaves it alone until the route ends, while
       shooterspdset divides by it. A fresh fixture player keeps the last
       update's mspeed, so neither world divides by a speed the game never has. */
    for(int k=32;k<128;k++)if(O.a[k].actno==SCD_OBJ_R6_SHOOT6 && O.a[k].r_no0>=4){player.mspeed.w=O.a[0].mspeed.w;break;}
    if(O.a[1].actno==SCD_OBJ_R6_SHOOT6 && O.a[1].r_no0>=4)player.mspeed.w=O.a[0].mspeed.w;
    last_input=player;
    /* The flashing-floor counter: 0..119, so 60 and 90 both occur. */
    clchgcnt[3]=(unsigned char)(ticks%120);
    int vx=scd_act_view_x();
    scd_player_progress p0=scd_player_progress_get();
    /* retail */
    memcpy(actwk,O.a,sizeof(O.a));actwk[0]=player;memcpy(flagwork,O.fw,766);
    colrevflag=O.colrev;projector_flag=O.proj;generate_flag=O.gen;emyscorecnt=O.emy;
    memcpy(ww_ptr,O.ptr,sizeof(ww_ptr));lpcolorwk=O.pal[0];lpcolorwk2=O.pal[1];st6clrchg=O.st6;gametimer.w=O.gt+1;ranum=O.ranum;memcpy(switchflag,O.sw,32);if(forced_switch>=0)switchflag[forced_switch]|=128;
    scra_h_posit.w.h=(short)vx;memset(drawn,0,sizeof(drawn));original_hits=0;plpower_b=shield;plring=0;
    if(!(player.cddat&2))emyscorecnt=0;
    /* PLAYER6.C runs COLI6.C pcol before the object pass. */
    if(player.r_no0<4){sprite_status before=actwk[0];pcol(actwk);if(memcmp(&before,&actwk[0],sizeof(before)))colis++;}
    orig_tick();
    memcpy(O.a,actwk,sizeof(O.a));memcpy(O.fw,flagwork,766);O.colrev=colrevflag;O.proj=projector_flag;O.gen=generate_flag;O.emy=emyscorecnt;
    memcpy(O.ptr,ww_ptr,sizeof(ww_ptr));O.st6=st6clrchg;O.gt=gametimer.w;memcpy(O.sw,switchflag,32);O.ranum=ranum;
    scd_player_progress po=scd_player_progress_get();unsigned char oshield=plpower_b;unsigned ohits=original_hits;
    int odrawn=0;for(int k=1;k<128;k++)if(drawn[k] && r6(O.a[k].actno))odrawn++;
    /* native */
    scd_player_progress_set(p0);plpower_b=shield;plring=0;
    memcpy(actwk,N.a,sizeof(N.a));actwk[0]=player;colrevflag=N.colrev;projector_flag=N.proj;scd_ww_host_load(N.state);if(forced_switch>=0)switchflag[forced_switch]|=128;
    unsigned h0=scd_objects_get().hits;
    /* COLI6: native ww_enemy_scan runs inside scd_objects_step. */
    scd_objects_step(player.xposi.w.h,player.yposi.w.h);
    unsigned nhits=scd_objects_get().hits-h0;
    int ndrawn=ww_views();
    memcpy(N.a,actwk,sizeof(N.a));N.colrev=colrevflag;N.proj=projector_flag;scd_ww_host_save(N.state);
    ticks++;
    for(int k=1;k<128;k++)if(r6(O.a[k].actno))states[O.a[k].actno]|=1u<<((O.a[k].r_no0/2)&31);
    for(int k=32;k<128;k++){if(O.a[k].actno && !nw_live[k])spawns++;if(!O.a[k].actno && nw_live[k])removals++;nw_live[k]=O.a[k].actno!=0;}
    if(odrawn!=ndrawn){fprintf(stderr,"drawn original %d native %d\n",odrawn,ndrawn);
        for(int k=1;k<128;k++)if(drawn[k] && r6(O.a[k].actno))fprintf(stderr," o%d:%u(%d,%d)r%u",k,O.a[k].actno,O.a[k].xposi.w.h,O.a[k].yposi.w.h,O.a[k].r_no0);
        static scd_object_view v[256];unsigned n=scd_objects_views(v,256);fprintf(stderr,"\n");
        for(unsigned q=0;q<n;q++)if(r6(v[q].type))fprintf(stderr," n:%u(%d,%d)",v[q].type,v[q].x,v[q].y);fprintf(stderr,"\n");}
    if(ohits!=nhits)fprintf(stderr,"hits original %u native %u\n",ohits,nhits);
    if(O.a[0].mstno.b.h==45 && (O.a[0].actfree[2]&1))orbits++;
    if(last_input.mstno.b.h==45 && (last_input.actfree[2]&1) && !(O.a[0].actfree[2]&1) && (O.a[0].cddat&2))orbit_jumps++;
    compare();REQUIRE(odrawn==ndrawn);draws+=odrawn;
    REQUIRE(ohits==nhits);hits+=ohits;
    REQUIRE(plpower_b==oshield);REQUIRE(scd_player_progress_get().score==po.score);
    REQUIRE(O.st6==st6clrchg);REQUIRE(O.gt==gametimer.w);REQUIRE(!memcmp(O.sw,switchflag,32));
    {uint16_t w[128]={0};uint64_t fs=0,s=scd_objects_ww_palette(w,&fs);
     for(unsigned b=0;b<2;b++)for(unsigned n=0;n<64;n++){const PALETTEENTRY *e=&O.pal[b][n];
        unsigned set=(b?fs:s)>>n&1,word=(e->peRed>>4)|e->peGreen|(e->peBlue<<4);
        if(set!=e->peFlags || (set && word!=w[b*64+n]))fprintf(stderr,"palette %u entry %u original %u/%#x native %u/%#x\n",b,n,e->peFlags,word,set,w[b*64+n]);
        REQUIRE(set==e->peFlags);if(set)REQUIRE(word==w[b*64+n]);}}
    REQUIRE(O.colrev==N.colrev);REQUIRE(!O.proj==!N.proj);REQUIRE(!O.gen==!scd_ww_host_good_future());
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
    char path[128];snprintf(path,sizeof(path),"assets/generated/ww6%u%c.bin",act,'A'+era);
    size_t n=read_file(path,data,sizeof(data));REQUIRE(!stage_open(&stage,data,n));
    snprintf(path,sizeof(path),"assets/generated/wwcollision6%u%c.bin",act,'A'+era);
    size_t c=read_file(path,collision,sizeof(collision));
    scd_player_zone(4);scd_objects_zone(4);scd_player_act(act-1);scd_objects_act(act-1);
    REQUIRE(!scd_player_init(&stage,collision,c,era));
    loaded_act=act;loaded_era=era;
}
extern unsigned char ww_era;
static void setup(unsigned i){
    ww_era=placements[i].era;
    load(placements[i].act,placements[i].era);
    unsigned era=placements[i].era;
    scd_objects_reset(era,0);editmode.w=0;stageno.b.l=placements[i].act-1;stageno.b.h=0;
    memset(flagwork,0,sizeof(flagwork));
    int x=placements[i].x,y=placements[i].y;
    scd_act_camera(x-160,y-112);
    REQUIRE(scd_objects_spawn(placements[i].type,x,y,placements[i].sub,placements[i].flags)==0);
    actwk[1].userflag.b.l=placements[i].sec;
    for(int k=0;k<30;k++)REQUIRE(scd_objects_spawn(SCD_OBJ_LOG_SHADOW,x,y,era<2?0:1,0)==k+1);
    memcpy(N.a,actwk,sizeof(N.a));N.colrev=0;N.proj=0;scd_ww_host_save(N.state);
    memcpy(O.a,actwk,sizeof(O.a));memset(O.fw,0,766);O.colrev=0;O.proj=0;O.gen=generate_flag;O.emy=0;
    memset(O.ptr,0,sizeof(O.ptr));memset(O.pal,0,sizeof(O.pal));O.st6=0;O.gt=gametimer.w;memset(O.sw,0,32);O.ranum=ranum;
    for(int k=2;k<32;k++){memset(&O.a[k],0,sizeof(O.a[k]));O.a[k].actno=250;}
    memset(nw_live,0,sizeof(nw_live));
}
static sprite_status parked(void){sprite_status p=make_player(0,0,8,0,0);p.xposi.w.h=scd_act_view_x()+8;p.yposi.w.h=scd_act_view_y()+8;return p;}
static void follow_camera(int x,int y){scd_act_camera(x-160,y-112);}
/* Required r_no0/2 state bits per routine (tools/test-ww-actors.sh grows it).
   No mask may name a state past the routine's own table: SHOOT6.C gas has
   7 states (0x7E: init moves on in its first update), catapalt 5 (0x1E);
   TOGEBL6A/B/D togeball_main and togeball_opt both leave state 0 in the
   update they start, and their children spawn after actor 1, so 0x2. */
static uint32_t ww_reach(unsigned t){
    switch(t){
    case SCD_OBJ_R6_BATTA:return 0xE;
    case SCD_OBJ_R6_HACHI6:return 0x3FC;
    case SCD_OBJ_R6_SEMI:return 0x7E;
    case SCD_OBJ_R6_MINOMUSI:return 0x1FE;
    case SCD_OBJ_R6_BEEM6:return 6;
    case SCD_OBJ_R6_DAIR6:return 2;
    case SCD_OBJ_R6_KDAI6:return 2;
    case SCD_OBJ_R6_TOBIDAI6:return 0xE;
    case SCD_OBJ_R6_BLOCK6:return 0x3FF;
    case SCD_OBJ_R6_SEESAW6:return 7;
    case SCD_OBJ_R6_PISTON6:return 2;
    case SCD_OBJ_R6_SW6:return 2;
    case SCD_OBJ_R6_TOBIRA6:return 0xE;
    case SCD_OBJ_R6_UDBLK6:return 0x1E;
    case SCD_OBJ_R6_OPTBR6:return 0x1E;
    case SCD_OBJ_R6_EGGZ6:return 0x1E;
    case SCD_OBJ_R6_MEGAMI:return 0xE;
    case SCD_OBJ_R6_GAS:return 0x7E;
    case SCD_OBJ_R6_CATAPALT:return 0x1E;
    case SCD_OBJ_R6_SHOOT6:return 0xE;
    case SCD_OBJ_R6_TOGEBALL6:return 2;
    case SCD_OBJ_R6_ET6:return 0xE;
    case SCD_OBJ_R6_MOVIE6:return 0x1E;
    case SCD_OBJ_R6_FRIEND6:return 0x1F;
    default:return 1;
    }
}
int main(void){
    if(getenv("WW_TRACE"))trace_actor=atoi(getenv("WW_TRACE"));
    state_size=scd_ww_host_size();nw_alloc(&N);nw_alloc(&N0);
    unsigned count=sizeof(placements)/sizeof(*placements);
    /* WW_ONLY=<routine>: run only that routine's placements (triage). */
    static const struct{unsigned type;const char *name;}only_names[]={
#define X(f,id) {id,#f},
#include "ported.h"
#undef X
    };
    int only=-1;const char *only_env=getenv("WW_ONLY");
    if(only_env){for(unsigned n=0;n<sizeof(only_names)/sizeof(*only_names);n++)if(!strcmp(only_names[n].name,only_env))only=(int)only_names[n].type;REQUIRE(only>=0);}
    for(unsigned i=0;i<count;i++){
        if(only>=0 && placements[i].type!=(unsigned)only)continue;
        int dup=0;
        for(unsigned j=0;j<i && !dup;j++)dup=placements[j].act==placements[i].act && placements[j].era==placements[i].era &&
            placements[j].type==placements[i].type && placements[j].sub==placements[i].sub && placements[j].flags==placements[i].flags && placements[j].sec==placements[i].sec;
        if(dup)continue;
        cur_case=i;cases++;per_type[placements[i].type]++;
        /* Phase 1: motion with the player parked in the viewport corner. */
        phase="motion";setup(i);
        for(cur_frame=0;cur_frame<600;cur_frame++)tick(parked(),1);
        /* Phase 1b: long motion with the player out of every sight range
           (patrol timers of 512-1024 updates). */
        phase="far";setup(i);
        for(cur_frame=0;cur_frame<1400;cur_frame++){
            sprite_status *o=&N.a[1];
            if(!o->actno || o->actno==SCD_OBJ_EXPLOSION)break;
            follow_camera(o->xposi.w.h,o->yposi.w.h);
            tick(make_player(o->xposi.w.h,o->yposi.w.h-400<16?o->yposi.w.h+400:o->yposi.w.h-400,8,0,0),1);
        }
        /* Phase 1c: the player walks through the actor from left to right
           (doors, blocks that rise in front of the player), with any switch
           of the subtype's number held pressed for the first half. */
        for(unsigned sw=0;sw<2;sw++){
            phase=sw?"walk-switch":"walk";setup(i);
            int x0=placements[i].x,y0=placements[i].y;
            for(cur_frame=0;cur_frame<600;cur_frame++){
                forced_switch=sw && cur_frame<300?placements[i].sub&15:-1;
                int px=x0-250+cur_frame;
                follow_camera(px,y0);
                tick(make_player(px,y0,0,256,0),1);
            }
            forced_switch=-1;
        }
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
                    if(!r6(base.actno))continue;
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
            /* Pad input for held/orbit routines: left, right, then a jump. */
            {unsigned f=cur_frame%150;swdata1.w=f>=40 && f<70?0x400:f>=70 && f<100?0x800:f==120?0x10:0;}
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
        swdata1.w=0;
        phase="frameout";
        scd_act_camera(scd_act_view_x()+2000,scd_act_view_y());
        for(cur_frame=0;cur_frame<3;cur_frame++)tick(parked(),1);
        /* EGG6 breaks on colicnt (a rolling pcolspecial 56 touch); raise it
           once in both worlds and run the explosion and bomb sequence. */
        if(placements[i].type==SCD_OBJ_R6_EGGZ6){
            phase="break";setup(i);
            for(cur_frame=0;cur_frame<400;cur_frame++){
                if(cur_frame==20 && O.a[1].actno==placements[i].type){O.a[1].colicnt=N.a[1].colicnt=1;breaks++;}
                follow_camera(placements[i].x,placements[i].y);
                tick(make_player(placements[i].x-120,placements[i].y,0,0,0),1);
            }
        }
    }
    static const struct{unsigned type;const char *name;}names[]={
#define X(f,id) {id,#f},
#include "ported.h"
#undef X
    };
    /* Every routine state (r_no0/2 bit) seen after an update, per routine. Init
       states that fall through to the next routine in the same update
       never show; children that stay at 0 do. */
    for(unsigned n=0;n<sizeof(names)/sizeof(*names);n++){
        if(only>=0 && names[n].type!=(unsigned)only)continue;
        if(!per_type[names[n].type])fprintf(stderr,"no case for %s\n",names[n].name);
        REQUIRE(per_type[names[n].type]);
        uint32_t need=ww_reach(names[n].type),got=states[names[n].type];
        if((got&need)!=need)fprintf(stderr,"%s reached states %#x of %#x\n",names[n].name,got,need);
    }
    for(unsigned n=0;n<sizeof(names)/sizeof(*names);n++)if(only<0 || names[n].type==(unsigned)only)REQUIRE((states[names[n].type]&ww_reach(names[n].type))==ww_reach(names[n].type));
    if(only<0){REQUIRE(hits>0);REQUIRE(colis>0);REQUIRE(retail_point_spawns>0);REQUIRE(retail_point_checks>0);REQUIRE(retail_flower_checks>0);}
    printf("PASS: ww actors %u assertions; %u cases; %u ticks; %u contact ticks; %u ridden; %u releases; %u child spawns; %u removals; %u draws; %u hits; %u kills; %u belt flips; %u shooter captures; %u forced breaks; COLI6 %u player contacts; %u pole orbits, %u orbit jumps; %u flyrings; retail points %u spawns/%u checks, flowers %u checks\n",
           checks,cases,ticks,contacts,rides,releases,spawns,removals,draws,hits,kills,belt_flips,captures,breaks,colis,orbits,orbit_jumps,ring_spawns,retail_point_spawns,retail_point_checks,retail_flower_checks);
    return 0;
}
