/* Runs BOSS_6.C, the COL6C/D.C boss fades and the COLI6.C touch response through
 * src/boss.c and src/boss_r6.c twice: against build/probe-source (little-endian
 * accessors, the Saturn source) and build/player-reference (original PC casts
 * on the 68-byte PC actor). tools/test-boss.sh requires identical per-update traces.
 * The Z63ACT.C layout: egg6boss and the six egg6doors. A scripted Sonic walks in
 * (the entrance door closes behind him, X 2688 starts the fight), stands on the
 * floor the boss works on, rolls into it while it hovers (each hit sends it up),
 * rides the rising floor pieces between events, rolls into it at the top until
 * it falls, waits out the fade and door sequence, then walks right past the
 * capsule line (X 3072). */
#include "EQU.H"
#include "scd_boss.h"
#include "scd_objects.h"
#include "scd_player.h"
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

short pcol(sprite_status *p);
/* Floors at Y 1680, 1168 and 656 (the beam heights plus 8): egg6toge and
   egg6gareki land on the one below them. */
short emycol_d(sprite_status *p){
    int y=p->yposi.w.h+p->sprvsize,floor=y<=656?656:y<=1168?1168:1680;
    return (short)(floor-y);
}
short playdieset(sprite_status *p){(void)p;return -1;}
/* RIDECHK.C's pushes and crush checks see open space. */
short dircolm(sprite_status *p,char *d){(void)p;*d=0;return 64;}
short dircol(sprite_status *p,char *d){(void)p;*d=0;return 64;}
short dircol_d(sprite_status *p,short *d0,short *d1,short *d3){(void)p;*d0=*d1=64;*d3=0;return 64;}
short dircol_u2(sprite_status *p){(void)p;return 64;}
static uint32_t explosions,hurts,points,sounds;
int scd_objects_spawn(unsigned type,int x,int y,unsigned sub,unsigned flags){
    explosions=explosions*31+(uint32_t)(type^x^(y<<16)^sub^flags);return 0;
}
void scd_objects_hurt(int source_x){hurts++;(void)source_x;}
void scd_player_points(unsigned value){points+=value;}
static unsigned sound_seen[256];
void soundset(short request){sounds=sounds*33+(uint16_t)request;if((uint16_t)request<256)sound_seen[request]++;}
int scd_boss6_fade(void);
unsigned scd_boss6_colorsets(void);

static uint32_t player_hash(void){
    const sprite_status *p=&actwk[0];uint32_t h=2166136261u;
    const int32_t v[]={p->xposi.l,p->yposi.l,p->xspeed.w,p->yspeed.w,p->mspeed.w,p->cddat,p->mstno.w,p->r_no0,p->actfree[18],p->actfree[19]};
    for(unsigned i=0;i<sizeof(v)/sizeof(*v);i++)for(unsigned b=0;b<4;b++)h=(h^((uint32_t)v[i]>>(8*b)&255))*16777619u;
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
/* Sonic's standing Y on floor 0 (bottom), 1 and 2 (top). */
static const int floor_y[3]={1660,1148,636};
/* argv[1] "good": the Good Future (generate_flag set, R63C); otherwise the Bad Future (R63D). */
int main(int argc,char **argv){
    memset(actwk,0,sizeof(actwk));
    generate_flag=argc>1 && !strcmp(argv[1],"good");time_flag=2;
    sprite_status *p=&actwk[0];
    p->actno=1;p->sprvsize=19;p->sprhs=9;place(2480,floor_y[0],0);
    scra_vline=96;scralim_left=0;scralim_right=3479;scralim_down=1808;
    scd_boss_reset();
    scd_boss_create_sub(2752,1408,0,6);
    static const short doors[6][4]={{2568,650,128,7},{2567,1162,128,6},{2566,1610,0,5},{2936,1674,129,5},{2937,1162,129,6},{2938,650,1,7}};
    for(unsigned i=0;i<6;i++)scd_boss6_door(doors[i][0],doors[i][1],(unsigned)doors[i][2],(unsigned)doors[i][3]);
    unsigned seen[80][16]={{0}},start_frame=0,hits=0,last_hits=0,top=0,dead=0,dead_done=0,door_closed=0,door_opened=0,
        flash_out=0,flash_in=0,fades=0,music_boss=0,music_zone=0,pal6=0,capsule=0,toge=0,gareki=0,pieces=0,yuka=0,beams=0,blasts=0,max_floor=0;
    uint32_t last_palette=0;
    for(unsigned frame=0;frame<12000;frame++){
        sprite_status *boss=find(52);
        unsigned floor=boss?boss->actfree[3]:3;if(floor>2)floor=2;
        if(frame<100)place(2480+frame*3,floor_y[0],0);                   /* the entrance door closes at X 2656 */
        else if(!start_frame)place(2700,floor_y[0],0);                    /* egg6_start: X 2688 */
        else if(boss && boss->r_no0<12){
            int hittable=boss->colino && (boss->r_no0==6 || (boss->actfree[3]==3 && boss->r_no0==10));
            /* pcol touches only actors drawn last update: the camera reaches the boss first. */
            if(hittable && frame%40==0)place(boss->xposi.w.h,boss->yposi.w.h-20,1);
            else if(hittable && frame%40>=36)place(boss->xposi.w.h-80,boss->yposi.w.h,0);
            else place(2700,floor_y[floor],0);
        }else if(boss && boss->r_no0<16)place(2700,floor_y[2],0);        /* egg6_dead1/2 hold Sonic on the top floor */
        else place(frame%2?3100:3090,floor_y[2],0);                       /* past the capsule line */
        actwk[0].actfree[6]=actwk[0].actfree[7]=0;
        scd_boss_camera(p->xposi.w.h-160,p->yposi.w.h-112);scra_v_posit.w.h=(short)(p->yposi.w.h-112);
        if((char)p->actfree[2]>=0 && p->mstno.b.h!=43)pcol(p);
        scd_boss_step();
        scd_boss_view views[64];unsigned n=scd_boss_views(views,64);uint32_t drawn=n;
        for(unsigned i=0;i<n;i++)drawn=drawn*16777619u^(uint32_t)(views[i].x^(views[i].y<<12)^(views[i].frame<<24)^views[i].flags^(views[i].kind<<20));
        for(unsigned i=0;i<n;i++){
            unsigned k=views[i].kind;toge|=k==244;yuka|=k==247;beams|=k>=251 && k<=253;blasts|=k==250;
        }
        for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++){unsigned id=actwk[i].actno;if(id && id<80)seen[id][(actwk[i].r_no0/2)&15]=1;}
        boss=find(52);
        if(bossstart==6 && !start_frame)start_frame=frame;
        if(boss && boss->actfree[15]!=last_hits){if(boss->actfree[15]>last_hits)hits++;last_hits=boss->actfree[15];}
        if(boss && boss->actfree[3]>max_floor)max_floor=boss->actfree[3];
        if(boss && boss->actfree[3]==3 && !top)top=frame;
        if(boss && boss->r_no0>=12 && !dead)dead=frame;
        if(boss && boss->r_no0>=16 && !dead_done)dead_done=frame;
        for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++)if(actwk[i].actno==62){
            if(actwk[i].userflag.b.h==0 && actwk[i].r_no0==6)door_closed=1;
            if(actwk[i].userflag.b.h==1 && actwk[i].r_no0>=8)door_opened=1;
        }
        int fade=scd_boss6_fade();if(fade==4)flash_out=frame;if(fade==3)flash_in=frame;
        uint32_t pal=palette_hash();if(pal!=last_palette){fades++;last_palette=pal;}
        if(scd_boss_palette()==SCD_BOSS_PALETTE_BOSS6)pal6=1;
        if(scd_boss_palette()==SCD_BOSS_PALETTE_CAPSULE)capsule=1;
        int music=scd_boss_music();if(music==SCD_BOSS_MUSIC_BOSS)music_boss=frame;if(music==SCD_BOSS_MUSIC_ZONE)music_zone=frame;
        printf("%u %08x %08x %08x %08x %08x %u %u %d %d %d %d %08x %08x %08x %d %d\n",frame,scd_boss_hash(),player_hash(),drawn,explosions,sounds,hurts,points,
            scd_boss_palette(),music,bossflag,bossstart,scd_boss_status(),scd_boss_position(),pal,fade,count(56)+count(57)+count(61));
        if(capsule && music_zone && frame>music_zone+120)break;
    }
    /* Debris falls above the camera: egg6gareki falling (r_no0 2) and burst into its pieces (4). */
    gareki=seen[57][1];pieces=seen[57][2];
    unsigned states=0;for(unsigned i=0;i<80;i++)for(unsigned r=0;r<16;r++)states+=seen[i][r];
    printf("summary start=%u hits=%u max_floor=%u top=%u dead=%u dead_done=%u door_closed=%u door_opened=%u flash_out=%u flash_in=%u palette_changes=%u "
        "colorsets=%u pal6=%u capsule=%u music_boss=%u music_zone=%u toge=%u gareki=%u pieces=%u yuka=%u beams=%u blasts=%u states=%u points=%u hurts=%u "
        "sfx172=%u sfx199=%u sfx158=%u sfx180=%u scralim_right=%d round=%u\n",
        start_frame,hits,max_floor,top,dead,dead_done,door_closed,door_opened,flash_out,flash_in,fades,scd_boss6_colorsets(),pal6,capsule,music_boss,music_zone,
        toge,gareki,pieces,yuka,beams,blasts,states,points,hurts,sound_seen[172],sound_seen[199],sound_seen[158],sound_seen[180],scralim_right,scd_boss_round());
    printf("era=%s\n",generate_flag?"good":"bad");
    return start_frame && hits>=4 && max_floor==3 && dead && dead_done && door_closed && door_opened && flash_out && flash_in && fades>10 &&
        pal6 && capsule && music_boss && music_zone && toge && gareki && pieces && yuka && beams && blasts && sound_seen[172] && sound_seen[199] &&
        scralim_right==3479?0:1;
}
