/* Runs BOSS_7.C (the Metal Sonic race, with egg7_hscr's forced scroll) and the
 * COLI7.C touch response through src/boss.c and src/boss_r7.c twice: against
 * build/probe-source (little-endian accessors, the Saturn source) and
 * build/player-reference (original PC casts on the 68-byte PC actor).
 * tools/test-boss7.py requires identical per-update traces using the production
 * R7 frontend. This does not establish retail CPU or Saturn parity.
 * The Z73ACT.C egg7 (3264,304) on a flat course (floor Y 480). A scripted Sonic
 * walks in (X 3040 starts the demo and the boss track), waits through egg7's
 * pass and Metal Sonic's door demo, then races right: argv[2] "lose" runs at
 * 4 pixels an update, so Metal Sonic attacks, reaches the goal (X 16016) first
 * and egg7's laser catches Sonic (playdieset); otherwise at 9, so Sonic wins,
 * Metal Sonic breaks apart and egg7 leaves (zone track, capsule palette, Amy's
 * colours). Sonic is never killed here: the laser's playdieset calls are counted. */
#include "EQU.H"
#include "scd_boss.h"
#include "scd_objects.h"
#include "scd_player.h"
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

short pcol(sprite_status *p);
/* A flat course: the floor is at Y 480 everywhere. */
short emycol_d(sprite_status *p){return (short)(480-(p->yposi.w.h+p->sprvsize));}
static unsigned deaths;
short playdieset(sprite_status *p){(void)p;deaths++;return -1;}
/* TBL1.C explosion patterns (src/boss_r3.c in the game); only an identity here. */
sprite_pattern *bakupat[7];
static uint32_t explosions,hurts,points,sounds;
int scd_objects_spawn(unsigned type,int x,int y,unsigned sub,unsigned flags){
    explosions=explosions*31+(uint32_t)(type^x^(y<<16)^sub^flags);return 0;
}
void scd_objects_hurt(int source_x){hurts++;(void)source_x;}
void scd_player_points(unsigned value){points+=value;}
static unsigned sound_seen[256];
void soundset(short request){sounds=sounds*33+(uint16_t)request;if((uint16_t)request<256)sound_seen[request]++;}
int scd_boss7_amy_colors(const PALETTEENTRY **line);

static uint32_t player_hash(void){
    const sprite_status *p=&actwk[0];uint32_t h=2166136261u;
    const int32_t v[]={p->xposi.l,p->yposi.l,p->xspeed.w,p->yspeed.w,p->mspeed.w,p->cddat,p->mstno.w,p->r_no0,p->actfree[18],p->actfree[19]};
    for(unsigned i=0;i<sizeof(v)/sizeof(*v);i++)for(unsigned b=0;b<4;b++)h=(h^((uint32_t)v[i]>>(8*b)&255))*16777619u;
    return h;
}
static sprite_status *find(unsigned id){for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++)if(actwk[i].actno==id)return &actwk[i];return NULL;}
static unsigned count(unsigned id){unsigned n=0;for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++)n+=actwk[i].actno==id;return n;}
/* argv[1] "good": the Good Future (generate_flag set, R73C); otherwise the Bad Future (R73D). */
int main(int argc,char **argv){
    memset(actwk,0,sizeof(actwk));
    generate_flag=argc>1 && !strcmp(argv[1],"good");time_flag=2;
    int lose=argc>2 && !strcmp(argv[2],"lose");
    sprite_status *p=&actwk[0];
    p->actno=1;p->sprvsize=19;p->sprhs=9;p->xposi.w.h=2900;p->yposi.w.h=461;
    scra_vline=96;scralim_left=0;scralim_right=16023;scralim_down=1296;
    scd_boss_reset();
    scd_boss_create_sub(3264,304,0,7);
    unsigned seen[64][16]={{0}},demo=0,race=0,result=0,goal_frame=0,egg_gone=0,msnc_lost=0,msnc_won=0,chichi=0,shards=0,jets=0,beams=0,sparks=0,
        smoke=0,forced=0,music_boss=0,music_zone=0,pal7=0,capsule=0,amy=0,min_gap=100000,attacks=0;
    int speed=0,min_left=100000;
    for(unsigned frame=0;frame<8000;frame++){
        sprite_status *egg=find(44),*metal=find(47);
        if(frame<80)speed=2;                                    /* snc_wait: X 3040 */
        else if(!metal || !(metal->actfree[2]&32))speed=0;      /* the demo: wait by the door */
        else speed=lose?4:9;                                     /* the race */
        if(result && p->xposi.w.h>=16100)speed=0;
        p->xposi.w.h+=(short)speed;p->xspeed.w=(short)(speed*256);p->mspeed.w=p->xspeed.w;
        p->yposi.w.h=461;p->yspeed.w=0;p->cddat=0;p->mstno.b.h=0;
        actwk[0].actfree[6]=actwk[0].actfree[7]=0;
        /* The camera follows Sonic inside the forced scroll limits egg7_hscr sets. */
        int cam=p->xposi.w.h-160;if(cam<scralim_left)cam=scralim_left;if(cam>scralim_right-320)cam=scralim_right-320;
        scd_boss_camera(cam,p->yposi.w.h-112);scra_v_posit.w.h=(short)(p->yposi.w.h-112);
        if((char)p->actfree[2]>=0 && p->mstno.b.h!=43)pcol(p);
        scd_boss_step();
        scd_boss_view views[64];unsigned n=scd_boss_views(views,64);uint32_t drawn=n;
        for(unsigned i=0;i<n;i++)drawn=drawn*16777619u^(uint32_t)(views[i].x^(views[i].y<<12)^(views[i].frame<<24)^views[i].flags^(views[i].kind<<20));
        for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++){unsigned id=actwk[i].actno;if(id && id<64)seen[id][(actwk[i].r_no0/2)&15]=1;}
        egg=find(44);metal=find(47);
        if(sound_seen[201] || sound_seen[202] || sound_seen[208])attacks=sound_seen[201]+sound_seen[202]+sound_seen[208];
        if(bossstart==7 && egg && egg->r_no0==4 && !demo)demo=frame;
        if(metal && (metal->actfree[2]&32) && !race)race=frame;
        if(egg && (egg->actfree[15]&15) && !result){result=egg->actfree[15]&15;goal_frame=frame;}
        if(metal && metal->r_no0==18)msnc_lost=1;
        if(metal && metal->r_no0==16)msnc_won=1;
        if(metal && metal->mstno.b.h==12)chichi=1;
        if(goal_frame && !egg && !egg_gone)egg_gone=frame;
        shards+=count(49)>0;jets|=count(45)==2;beams|=count(46)>=4;sparks|=count(48)>0;smoke|=count(55)>0;
        if(egg && (egg->actfree[14]&128))forced=1;
        if(race && !result && egg){unsigned gap=(unsigned)(p->xposi.w.h-egg->xposi.w.h);if(gap<min_gap)min_gap=gap;}
        if(race && scralim_left<min_left)min_left=scralim_left;
        if(scd_boss_palette()==SCD_BOSS_PALETTE_BOSS7)pal7=1;
        if(scd_boss_palette()==SCD_BOSS_PALETTE_CAPSULE)capsule=1;
        const PALETTEENTRY *line;if(scd_boss7_amy_colors(&line))amy=1;
        int music=scd_boss_music();if(music==SCD_BOSS_MUSIC_BOSS)music_boss=frame;if(music==SCD_BOSS_MUSIC_ZONE)music_zone=frame;
        printf("%u %08x %08x %08x %08x %08x %u %u %d %d %d %d %08x %08x %d %d %d\n",frame,scd_boss_hash(),player_hash(),drawn,explosions,sounds,hurts,points,
            scd_boss_palette(),music,bossflag,bossstart,scd_boss_status(),scd_boss_position(),scralim_left,scralim_right,deaths);
        if(egg_gone && frame>egg_gone+120)break;
        if(lose && goal_frame && frame>goal_frame+600)break;
    }
    unsigned states=0;for(unsigned i=0;i<64;i++)for(unsigned r=0;r<16;r++)states+=seen[i][r];
    printf("summary demo=%u race=%u result=%u goal=%u msnc_lost=%u msnc_won=%u chichi=%u egg_gone=%u shards=%u jets=%u beams=%u sparks=%u smoke=%u "
        "forced=%u min_gap=%u attacks=%u pal7=%u capsule=%u amy=%u music_boss=%u music_zone=%u scralim_right=%d states=%u points=%u hurts=%u deaths=%u "
        "sfx187=%u sfx201=%u sfx202=%u sfx208=%u sfx158=%u round=%u\n",
        demo,race,result,goal_frame,msnc_lost,msnc_won,chichi,egg_gone,shards,jets,beams,sparks,smoke,forced,min_gap,attacks,pal7,capsule,amy,
        music_boss,music_zone,scralim_right,states,points,hurts,deaths,sound_seen[187],sound_seen[201],sound_seen[202],sound_seen[208],sound_seen[158],scd_boss_round());
    printf("era=%s%s\n",generate_flag?"good":"bad",lose?" lose":"");
    int common=demo && race && goal_frame && jets && beams && forced && pal7 && music_boss && sound_seen[187];
    int won=result==1 && msnc_lost && shards && egg_gone && capsule && amy && music_zone && scralim_right==16023 && points;
    int lost=result==2 && msnc_won && deaths && sparks && attacks;
    return common && (lose?lost:won)?0:1;
}
