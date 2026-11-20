/* Runs BOSS_8.C, the COL8C/D.C boss palette routines and the COLI8.C touch
 * response through src/boss.c and src/boss_r8.c twice: against
 * build/probe-source (little-endian accessors, the Saturn source) and
 * build/player-reference (original PC casts on the 68-byte PC actor).
 * tools/test-boss8.py requires identical per-update traces.
 * egg8 appears where HOTA8C/D.C's room controller puts it (3840,316). A
 * scripted Sonic walks in (X 3840 closes the arena), waits through the lid
 * opening and fade, then rolls into egg8 or its shell when both can be hit, at
 * most once per 1500 updates (each hit costs a blade and changes egg8's action
 * table; the fourth kills it), and waits for the escape past
 * X 4064. The actual EMIE8 ending then runs. Scripted Sonic positions exercise
 * its right/left/wait/pose controls; this is a service fixture, not a player route. */
#include "EQU.H"
#include "scd_boss.h"
#include "scd_objects.h"
#include "scd_player.h"
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

short pcol(sprite_status *p);
static void fixture_memset(void *p,unsigned char c,int n){memset(p,c,(size_t)n);}
void (*sMemSet)(void *,unsigned char,int)=fixture_memset;
short emycol_d(sprite_status *p){return (short)(464-(p->yposi.w.h+p->sprvsize));}
short playdieset(sprite_status *p){(void)p;return -1;}
static uint32_t explosions,hurts,points,sounds;
int scd_objects_spawn(unsigned type,int x,int y,unsigned sub,unsigned flags){
    explosions=explosions*31+(uint32_t)(type^x^(y<<16)^sub^flags);return 0;
}
void scd_objects_hurt(int source_x){hurts++;(void)source_x;}
void scd_player_points(unsigned value){points+=value;}
static unsigned sound_seen[256];
void soundset(short request){sounds=sounds*33+(uint16_t)request;if((uint16_t)request<256)sound_seen[request]++;}

static uint32_t player_hash(void){
    const sprite_status *p=&actwk[0];uint32_t h=2166136261u;
    const int32_t v[]={p->xposi.l,p->yposi.l,p->xspeed.w,p->yspeed.w,p->mspeed.w,p->cddat,p->mstno.w,p->patcnt,p->r_no0,p->actfree[18],p->actfree[19]};
    for(unsigned i=0;i<sizeof(v)/sizeof(*v);i++)for(unsigned b=0;b<4;b++)h=(h^((uint32_t)v[i]>>(8*b)&255))*16777619u;
    return h;
}
static uint32_t ending_hash(void){
    uint32_t h=2166136261u;
    const unsigned v[]={swdata.w,plautoflag,gameflag.w,time_flag,stageno.w};
    for(unsigned i=0;i<sizeof(v)/sizeof(*v);i++)for(unsigned b=0;b<4;b++)h=(h^((v[i]>>(8*b))&255))*16777619u;
    for(unsigned i=0;i<sizeof(clchgtim);i++)h=(h^clchgtim[i])*16777619u;
    return h;
}
static uint32_t palette_hash(void){
    uint32_t h=2166136261u;
    for(unsigned i=0;i<64;i++){const PALETTEENTRY *e=&lpcolorwk[i];h=(h^(uint32_t)(e->peRed|e->peGreen<<8|e->peBlue<<16|e->peFlags<<24))*16777619u;}
    return h;
}
static sprite_status *find(unsigned id){for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++)if(actwk[i].actno==id)return &actwk[i];return NULL;}
static unsigned count(unsigned id){unsigned n=0;for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++)n+=actwk[i].actno==id;return n;}
static void place(int x,int y,int rolling){
    sprite_status *p=&actwk[0];
    p->xposi.l=x*65536;p->yposi.l=y*65536;p->cddat=rolling?6:0;p->mstno.b.h=rolling?2:0;p->xspeed.w=0;p->yspeed.w=rolling?256:0;
}
/* argv[1] "good": the Good Future (generate_flag set, R83C); otherwise the Bad Future (R83D). */
int main(int argc,char **argv){
    memset(actwk,0,sizeof(actwk));
    generate_flag=argc>1 && !strcmp(argv[1],"good");time_flag=2;
    sprite_status *p=&actwk[0];
    p->actno=1;p->sprvsize=19;p->sprhs=9;place(3600,440,0);
    scra_vline=96;scralim_left=0;scralim_right=3735;scralim_down=784;
    scd_boss_reset();
    scd_boss_create_sub(3840,316,0,8);
    unsigned seen[80][32]={{0}},start=0,open=0,hits=0,last_blades=4,dead=0,escaped=0,amy=0,music_final=0,pal8=0,palette_changes=0,
        hane_fire=0,hane_kill=0,sparks=0,tobi=0,spin=0,last_hit=0,ending=0,amy_controls=0,control_outputs=0,pose_inputs=0,palette_resets=0,takeovers=0;
    uint32_t last_palette=0;
    for(unsigned frame=0;frame<9000;frame++){
        sprite_status *egg=find(63),*shell=find(65);
        sprite_status *emie=find(67);
        unsigned ctrl=emie?emie->actfree[3]:255,routine=emie?emie->r_no0:255;
        unsigned pose_input=0;
        if(escaped && emie){
            /* Script only positions. Do not overwrite Amy's animation takeover. */
            p->xposi.l=(ctrl<2?3984:3952)*65536;p->yposi.l=440*65536;
            if(ctrl==6){
                static const unsigned samples[]={0,15,16,17};
                pose_input=samples[frame&3];p->patcnt=pose_input;
            }
        }
        else if(frame<130)place(3600+frame*2,440,0);                          /* egg8_scrset: X 3840 */
        else if(egg && egg->r_no0<50){
            int hittable=egg->colino && shell && shell->colino && !shell->actfree[18];
            /* One hit per 1500 updates, so each blade count runs its whole action table. */
            if(hittable && frame%60==0 && frame>=last_hit+1500)place(egg->xposi.w.h,egg->yposi.w.h-8,1);
            else place(frame%400<200?3740:3940,440,0);
        }else place(3760,440,0);
        actwk[0].actfree[6]=actwk[0].actfree[7]=0;
        scd_boss_camera(3680,248);scra_v_posit.w.h=248;
        if((char)p->actfree[2]>=0 && p->mstno.b.h!=43)pcol(p);
        /* Poison only the service output that EMIE8_l2 must overwrite. */
        if(routine==14)for(unsigned i=0;i<sizeof(clchgtim);i++)clchgtim[i]=(unsigned char)(i+frame);
        scd_boss_step();
        if(emie){
            assert(plautoflag&1);takeovers++;
            if(ctrl==0){unsigned expected=p->xposi.w.h<3984?2056:1028;assert(swdata.w==expected);control_outputs|=expected==2056?1:2;}
            else if(ctrl==2){unsigned expected=p->xposi.w.h>3952?1028:0;assert(swdata.w==expected);control_outputs|=expected?2:4;}
            else if(ctrl==4 && routine>=6){assert(p->mstno.b.h==5);control_outputs|=8;}
            else if(ctrl==6 && escaped){assert(p->patcnt==(pose_input<16?16:pose_input));pose_inputs|=1u<<(frame&3);}
            if(routine==14){for(unsigned i=0;i<sizeof(clchgtim);i++)assert(clchgtim[i]==127);palette_resets++;}
        }
        scd_boss_view views[64];unsigned n=scd_boss_views(views,64);uint32_t drawn=n;
        for(unsigned i=0;i<n;i++)drawn=drawn*16777619u^(uint32_t)(views[i].x^(views[i].y<<12)^(views[i].frame<<24)^views[i].flags^(views[i].kind<<20));
        for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++){unsigned id=actwk[i].actno;if(id && id<80)seen[id][(actwk[i].r_no0/2)&31]=1;}
        egg=find(63);
        if(bossstart==8 && !start)start=frame;
        if(egg && (egg->actfree[2]&8) && !open)open=frame;
        if(egg && egg->actfree[16]<last_blades){hits+=last_blades-egg->actfree[16];last_blades=egg->actfree[16];last_hit=frame;}
        if(egg && egg->r_no0>=50 && !dead)dead=frame;
        if(egg && egg->r_no0==54 && !escaped)escaped=frame;
        if(count(67))amy=1;
        emie=find(67);if(emie)amy_controls|=1u<<(emie->actfree[3]/2);
        uint32_t pal=palette_hash();if(pal!=last_palette){palette_changes++;last_palette=pal;}
        if(scd_boss_palette()==SCD_BOSS_PALETTE_BOSS8)pal8=1;
        int music=scd_boss_music();if(music==SCD_BOSS_MUSIC_FINAL)music_final=frame;
        printf("%u %08x %08x %08x %08x %08x %u %u %d %d %d %d %08x %08x %08x %u %u %u %08x\n",frame,scd_boss_hash(),player_hash(),drawn,explosions,sounds,hurts,points,
            scd_boss_palette(),music,bossflag,bossstart,scd_boss_status(),scd_boss_position(),pal,swdata.w,plautoflag,p->patcnt,ending_hash());
        if(gameflag.w==2){ending=frame;break;}
    }
    hane_fire=seen[64][3];hane_kill=seen[64][5];sparks=seen[66][1];tobi=seen[63][18]|seen[63][19]|seen[63][20];spin=seen[63][11]|seen[63][12]|seen[63][13];
    unsigned states=0;for(unsigned i=0;i<80;i++)for(unsigned r=0;r<32;r++)states+=seen[i][r];
    printf("summary start=%u open=%u hits=%u dead=%u escaped=%u amy=%u music_final=%u pal8=%u palette_changes=%u hane_fire=%u hane_kill=%u sparks=%u "
        "tobi=%u spin=%u states=%u points=%u hurts=%u sfx172=%u sfx201=%u sfx186=%u sfx180=%u sfx158=%u round=%u\n",
        start,open,hits,dead,escaped,amy,music_final,pal8,palette_changes,hane_fire,hane_kill,sparks,tobi,spin,states,points,hurts,
        sound_seen[172],sound_seen[201],sound_seen[186],sound_seen[180],sound_seen[158],scd_boss_round());
    printf("ending frame=%u gameflag=%u time_flag=%u stageno=%u amy_controls=%u control_outputs=%u pose_inputs=%u palette_resets=%u takeovers=%u\n",ending,gameflag.w,time_flag,stageno.w,amy_controls,control_outputs,pose_inputs,palette_resets,takeovers);
    printf("era=%s\n",generate_flag?"good":"bad");
    return start && open && hits==4 && dead && escaped && amy && music_final && pal8 && palette_changes>20 && hane_kill && sparks && hane_fire && tobi && spin && sound_seen[201] && sound_seen[180] &&
        sound_seen[172]==4 && sound_seen[158] && ending>escaped && gameflag.w==2 && (time_flag&128) && stageno.w==1792 && amy_controls==15 && control_outputs==15 && pose_inputs==15 && palette_resets>0 && takeovers>0?0:1;
}
