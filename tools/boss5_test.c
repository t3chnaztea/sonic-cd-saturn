/* Runs BOSS_5.C and the COLI5.C touch response through src/boss.c and
 * src/boss_r5.c twice: against build/probe-source (little-endian accessors, the
 * Saturn source) and build/player-reference (original PC casts on the 68-byte
 * PC actor). tools/test-boss.sh requires identical per-update traces.
 * A scripted Sonic walks in past the spike wall (egg5hari rises behind him at
 * X 3152), starts the fight (X 3424: boss music, bossstart 5), rolls into the
 * drill (egg5meca2, one hit), then runs right on the conveyor at top speed so
 * the belt winds the drill's counter from 2400 to 0 through its four descents,
 * touching one bomb and stepping clear of the rest (they land and burst), until egg5 flees and the scroll limit and zone track return. */
#include "EQU.H"
#include "scd_boss.h"
#include "scd_objects.h"
#include "scd_player.h"
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

short pcol(sprite_status *p);
/* BOSS_1.C links beside this boss; its floor checks are never reached here. */
short emycol_d(sprite_status *p){(void)p;return 0;}
short playdieset(sprite_status *p){(void)p;return -1;}
/* RIDECHK.C's pushes and crush checks see open space. */
short dircolm(sprite_status *p,char *d){(void)p;*d=0;return 64;}
short dircol(sprite_status *p,char *d){(void)p;*d=0;return 64;}
short dircol_d(sprite_status *p,short *d0,short *d1,short *d3){(void)p;*d0=*d1=64;*d3=0;return 64;}
short dircol_u2(sprite_status *p){(void)p;return 64;}
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
const PALETTEENTRY *scd_boss5_belt_colors(void);

static uint32_t player_hash(void){
    const sprite_status *p=&actwk[0];uint32_t h=2166136261u;
    const int32_t v[]={p->xposi.l,p->yposi.l,p->xspeed.w,p->yspeed.w,p->mspeed.w,p->cddat,p->mstno.w,p->r_no0,p->actfree[18],p->actfree[19]};
    for(unsigned i=0;i<sizeof(v)/sizeof(*v);i++)for(unsigned b=0;b<4;b++)h=(h^((uint32_t)v[i]>>(8*b)&255))*16777619u;
    return h;
}
static sprite_status *find(unsigned id){for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++)if(actwk[i].actno==id)return &actwk[i];return NULL;}
static unsigned count(unsigned id){unsigned n=0;for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++)n+=actwk[i].actno==id;return n;}
/* The drill's PC word 33 (bytes 66-67): the belt counter, 2400 down to 0. */
static int drill_count(const sprite_status *p){return (int16_t)(p->actfree[20]|p->actfree[21]<<8);}
static void place(int x,int y,int rolling,int xspeed){
    sprite_status *p=&actwk[0];
    p->xposi.l=x*65536;p->yposi.l=y*65536;p->cddat=rolling?6:0;p->mstno.b.h=rolling?2:0;p->xspeed.w=(short)xspeed;p->yspeed.w=rolling?256:0;
}
/* argv[1] "good": the Good Future (generate_flag set, R53C); otherwise the Bad Future (R53D). */
int main(int argc,char **argv){
    memset(actwk,0,sizeof(actwk));
    generate_flag=argc>1 && !strcmp(argv[1],"good");time_flag=2;
    sprite_status *p=&actwk[0];
    p->actno=1;p->sprvsize=19;p->sprhs=9;place(3000,700,0,0);
    scra_vline=96;scralim_left=0;scralim_right=3735;scralim_down=800;
    scd_boss_reset();
    scd_boss_create_sub(3088,736,SCD_BOSS_EGG5HARI,5);scd_boss_create_sub(3536,552,SCD_BOSS_EGG5MECA1,5);
    unsigned seen[64][16]={{0}},start_frame=0,drill_hit=0,last_patno=0,descents=0,count_zero=0,egg_gone=0,egg_escape=0,
        wall_top=0,bombs=0,shards=0,bomb_touch=0,sparks=0,blasts=0,music_boss=0,music_zone=0,pal5=0,capsule=0,flag5=0,belt_colors=0;
    int min_count=2400;
    for(unsigned frame=0;frame<9000;frame++){
        sprite_status *drill=find(52),*bomb=find(56);
        if(frame<240)place(3000+frame*2,690,0,512);        /* egg5hari rises behind at X 3152 */
        else if(!start_frame)place(3430,690,0,0);             /* egg5meca1_scrset: X 3424 starts the fight */
        else if(drill && drill->colino && drill->r_no0==2){
            /* Roll into the drill every 40 updates until it takes its hit. */
            if(frame%40==0)place(drill->xposi.w.h-24,drill->yposi.w.h+60,1,0);else place(3420,690,0,0);
        }else if(bomb && bomb->r_no0>=6 && !bomb_touch){place(bomb->xposi.w.h,bomb->yposi.w.h,0,0);bomb_touch=frame;}
        else if(bomb && bomb->r_no0>=6)place(bomb->xposi.w.h-72,690,0,1600);   /* step clear of later bombs: they land and burst */
        else place(3440,690,0,1600);                          /* run right on the belt at top speed */
        actwk[0].actfree[6]=actwk[0].actfree[7]=0;
        scd_boss_camera(3280,560);scra_v_posit.w.h=560;
        if((char)p->actfree[2]>=0 && p->mstno.b.h!=43)pcol(p);
        scd_boss_step();
        scd_boss_view views[64];unsigned n=scd_boss_views(views,64);uint32_t drawn=n;
        for(unsigned i=0;i<n;i++)drawn=drawn*16777619u^(uint32_t)(views[i].x^(views[i].y<<12)^(views[i].frame<<24)^views[i].flags^(views[i].kind<<20));
        for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++){unsigned id=actwk[i].actno;if(id && id<64)seen[id][(actwk[i].r_no0/2)&15]=1;}
        drill=find(52);sprite_status *egg=find(50),*wall=find(33);
        if(bossstart==5 && !start_frame)start_frame=frame;
        if(bossflag==5)flag5=1;
        if(drill && drill->r_no0==4 && !drill_hit)drill_hit=frame;
        if(drill && drill->patno!=last_patno){last_patno=drill->patno;descents++;}
        if(drill && drill_count(drill)<min_count)min_count=drill_count(drill);
        if(drill && drill_count(drill)<=0 && !count_zero)count_zero=frame;
        if(egg && egg->r_no0==4 && !egg_escape)egg_escape=frame;
        if(egg_escape && !egg && !egg_gone)egg_gone=frame;
        if(wall && wall->r_no0==8)wall_top=1;
        unsigned b=count(56)+count(57);if(b>bombs)bombs=b;if(count(57)>shards)shards=count(57);
        sparks+=count(32)>0;blasts+=count(35)>0;
        if(scd_boss_palette()==SCD_BOSS_PALETTE_BOSS5)pal5=1;
        if(scd_boss_palette()==SCD_BOSS_PALETTE_CAPSULE)capsule=1;
        const PALETTEENTRY *belt=scd_boss5_belt_colors();uint32_t colors=0;
        for(unsigned c=0;c<3;c++)colors=colors*16777619u^(uint32_t)(belt[c].peRed|belt[c].peGreen<<8|belt[c].peBlue<<16|belt[c].peFlags<<24);
        if(colors)belt_colors=1;
        int music=scd_boss_music();if(music==SCD_BOSS_MUSIC_BOSS)music_boss=frame;if(music==SCD_BOSS_MUSIC_ZONE)music_zone=frame;
        printf("%u %08x %08x %08x %08x %08x %u %u %d %d %d %d %08x %08x %08x %d\n",frame,scd_boss_hash(),player_hash(),drawn,explosions,sounds,hurts,points,
            scd_boss_palette(),music,bossflag,bossstart,scd_boss_status(),scd_boss_position(),colors,drill?drill_count(drill):-1);
        if(music_zone && frame>music_zone+120)break;
    }
    unsigned states=0;for(unsigned i=0;i<64;i++)for(unsigned r=0;r<16;r++)states+=seen[i][r];
    printf("summary start=%u drill_hit=%u descents=%u min_count=%d count_zero=%u egg_escape=%u egg_gone=%u wall_top=%u bombs=%u shards=%u bomb_touch=%u "
        "sparks=%u blasts=%u flag5=%u pal5=%u capsule=%u belt_colors=%u music_boss=%u music_zone=%u scralim_right=%d vline=%d states=%u points=%u hurts=%u "
        "sfx172=%u sfx180=%u sfx196=%u sfx203=%u sfx158=%u round=%u\n",
        start_frame,drill_hit,descents,min_count,count_zero,egg_escape,egg_gone,wall_top,bombs,shards,bomb_touch,sparks,blasts,flag5,pal5,capsule,belt_colors,
        music_boss,music_zone,scralim_right,scra_vline,states,points,hurts,
        sound_seen[172],sound_seen[180],sound_seen[196],sound_seen[203],sound_seen[158],scd_boss_round());
    printf("era=%s\n",generate_flag?"good":"bad");
    return start_frame && drill_hit && descents>=4 && count_zero && egg_gone && wall_top && bombs && shards==4 && bomb_touch && sparks && blasts && flag5 && pal5 &&
        capsule && belt_colors && music_boss && music_zone && scralim_right==3735 && hurts && sound_seen[196] && sound_seen[203]?0:1;
}
