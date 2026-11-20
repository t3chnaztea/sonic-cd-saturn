/* Runs BOSS_4.C, BOSS_4_2.C, WALL4.C and the COLI4.C touch response through
 * src/boss.c and src/boss_r4.c twice: against build/probe-source (little-endian
 * accessors, the Saturn source) and build/player-reference (original PC casts
 * on the 68-byte PC actor). tools/test-boss.sh requires identical per-update traces.
 * A scripted Sonic passes the layout wall (it drops behind him), starts the
 * chase (X 1144), follows egg4air 100 pixels behind and rolls into it until
 * its four hits are taken, follows it to its dive, walks to the exit (bossflag
 * 4), enters the egg4 arena, pops bubbles, rolls into egg4 and waits for the
 * escape and the scroll reset. */
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
static uint32_t explosions,hurts,points,sounds,airs;
int scd_objects_spawn(unsigned type,int x,int y,unsigned sub,unsigned flags){
    explosions=explosions*31+(uint32_t)(type^x^(y<<16)^sub^flags);return 0;
}
void scd_objects_hurt(int source_x){hurts++;(void)source_x;}
void scd_player_points(unsigned value){points+=value;}
void soundset(short request){sounds=sounds*33+(uint16_t)request;}
void plairset(void){airs++;}

static uint32_t player_hash(void){
    const sprite_status *p=&actwk[0];uint32_t h=2166136261u;
    const int32_t v[]={p->xposi.l,p->yposi.l,p->xspeed.w,p->yspeed.w,p->mspeed.w,p->cddat,p->mstno.w,p->r_no0,p->actfree[18],p->actfree[19]};
    for(unsigned i=0;i<sizeof(v)/sizeof(*v);i++)for(unsigned b=0;b<4;b++)h=(h^((uint32_t)v[i]>>(8*b)&255))*16777619u;
    return h;
}
static sprite_status *find(unsigned id){for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++)if(actwk[i].actno==id)return &actwk[i];return NULL;}
static unsigned count(unsigned id){unsigned n=0;for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++)n+=actwk[i].actno==id;return n;}
static void place(int x,int y,int rolling){
    sprite_status *p=&actwk[0];
    p->xposi.l=x*65536;p->yposi.l=y*65536;p->cddat=rolling?6:0;p->mstno.b.h=rolling?2:0;p->xspeed.w=0;p->yspeed.w=rolling?256:0;
}
/* argv[1] "good": the Good Future (generate_flag set, R43C); otherwise the Bad Future (R43D). */
int main(int argc,char **argv){
    memset(actwk,0,sizeof(actwk));
    generate_flag=argc>1 && !strcmp(argv[1],"good");time_flag=2;
    sprite_status *p=&actwk[0];
    p->actno=1;p->sprvsize=19;p->sprhs=9;place(900,800,0);
    scra_vline=96;scralim_left=0;scralim_right=3479;scralim_down=2048;
    scd_boss_reset();
    scd_boss_create_sub(1056,768,SCD_BOSS_WALL4,4);scd_boss_create_sub(1232,852,SCD_BOSS_EGG4AIR,4);
    unsigned seen[80][16]={{0}},air_hits=0,last_cnt=5,air_gone=0,flag_frame=0,egg_made=0,egg_hit=0,egg_gone=0,
        bubbles=0,popped=0,max_tama=0,gates=0,wall_drop=0,music_boss=0,music_zone=0,bossstart_seen=0,scroll_done=0,last_bubbles=0,pal4=0,capsule=0;
    for(unsigned frame=0;frame<16000;frame++){
        sprite_status *air=find(74),*egg=find(76);
        if(frame<60)place(900+frame*4,800,0);
        else if(frame<120)place(1230,800,0);              /* wall4_sense: 160-191 right of the wall */
        else if(frame<150)place(1150,860,0);              /* egg4air_04: the chase starts */
        else if(air){
            /* Roll into it every 45 updates while it can be hit; otherwise follow 100 behind. */
            if(air->colino && frame%45==0)place(air->xposi.w.h,air->yposi.w.h-20,1);
            else place(air->xposi.w.h+((air->cddat&1)?100:-100),air->yposi.w.h,0);
        }else if(!flag_frame)place(2120,1370,0);          /* egg4airhead_02: bossflag 4 */
        else if(!egg_made && frame<flag_frame+60)place(2300,1400,0);
        else if(!egg_made){scd_boss_create_sub(2736,1312,SCD_BOSS_EGG4,4);egg_made=frame;place(2400,1400,0);}
        else if(egg && egg->r_no0<12)place(2650,1400,0);
        else if(egg && egg->r_no0<18){
            /* Pop a bubble every 40 updates for 10 pops, then roll into egg4. */
            sprite_status *b=NULL;for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128 && !b;i++)if(actwk[i].actno==79 && actwk[i].colino==255)b=&actwk[i];
            if(popped<10 && b && frame%40==0){place(b->xposi.w.h,b->yposi.w.h,1);popped++;}
            else if(popped>=10 && frame%40==0)place(egg->xposi.w.h,egg->yposi.w.h,1);
            else place(2650,1480,0);
        }else place(2650,1480,0);
        actwk[0].actfree[6]=actwk[0].actfree[7]=0;
        scd_boss_camera(p->xposi.w.h-160,p->yposi.w.h-112);
        if((char)p->actfree[2]>=0 && p->mstno.b.h!=43)pcol(p);
        scd_boss_step();
        scd_boss_view views[64];unsigned n=scd_boss_views(views,64);uint32_t drawn=n;
        for(unsigned i=0;i<n;i++)drawn=drawn*16777619u^(uint32_t)(views[i].x^(views[i].y<<12)^(views[i].frame<<24)^views[i].flags^(views[i].kind<<20));
        for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++){unsigned id=actwk[i].actno;if(id && id<80)seen[id][(actwk[i].r_no0/2)&15]=1;}
        air=find(74);egg=find(76);
        if(air && air->colicnt!=last_cnt){if(air->colicnt<last_cnt)air_hits++;last_cnt=air->colicnt;}
        if(frame>150 && !air && !air_gone)air_gone=frame;
        if(bossflag==4 && !flag_frame)flag_frame=frame;
        if(egg && egg->r_no0==18 && !egg_hit)egg_hit=frame;
        if(egg_made && !egg && !egg_gone)egg_gone=frame;
        unsigned b=count(79);if(b>bubbles)bubbles=b;
        unsigned t=count(78);if(t>max_tama)max_tama=t;
        unsigned g=0;for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++)g+=actwk[i].actno==71 && actwk[i].userflag.b.h==1;if(g>gates)gates=g;
        if(flagwork[2+254*3]&1)wall_drop=1;
        if(bossstart==4)bossstart_seen=1;
        if(scd_boss_palette()==SCD_BOSS_PALETTE_BOSS4)pal4=1;
        if(scd_boss_palette()==SCD_BOSS_PALETTE_CAPSULE)capsule=1;
        int music=scd_boss_music();if(music==SCD_BOSS_MUSIC_BOSS)music_boss=frame;if(music==SCD_BOSS_MUSIC_ZONE)music_zone=frame;
        if(egg_gone && !scroll_done && scralim_right==3479 && !bossstart)scroll_done=frame;
        last_bubbles=b;
        printf("%u %08x %08x %08x %08x %08x %u %u %u %d %d %d %d %d %08x %08x\n",frame,scd_boss_hash(),player_hash(),drawn,explosions,sounds,hurts,points,airs,scd_boss_palette(),music,
            bossflag,bossstart,scralim_left<<16^scralim_right,scd_boss_status(),scd_boss_position());
        if(scroll_done && frame>scroll_done+30)break;
    }
    (void)last_bubbles;
    unsigned states=0;for(unsigned i=0;i<80;i++)for(unsigned r=0;r<16;r++)states+=seen[i][r];
    printf("summary air_hits=%u air_gone=%u bossflag_at=%u egg_made=%u egg_hit=%u egg_gone=%u scroll_reset=%u max_bubbles=%u popped=%u air_refills=%u max_tama=%u gates=%u wall_drop=%u "
        "states=%u points=%u hurts=%u boss_music=%u zone_music=%u palette4=%u capsule=%u round=%u\n",
        air_hits,air_gone,flag_frame,egg_made,egg_hit,egg_gone,scroll_done,bubbles,popped,airs,max_tama,gates,wall_drop,states,points,hurts,music_boss,music_zone,pal4,capsule,scd_boss_round());
    printf("era=%s\n",generate_flag?"good":"bad");
    return air_hits==4 && air_gone && flag_frame && egg_hit && egg_gone && scroll_done && bubbles>=16 && airs && gates==2 && wall_drop
        && bossstart_seen && music_boss && music_zone && pal4 && capsule && points && scd_boss_round()==4?0:1;
}
