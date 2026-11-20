/* Native-host model of a Quartz Quadrant level-select run of one act and era,
   for Saturn controller-route replays (tools/test_qq_route.py). Forked from
   tools/tt_route_search.c without the water model (Quartz Quadrant has none).
   The per-update order follows src/main.c's gameplay step: camera to the
   actors and boss, title lock, player step, title card, boss music, world
   step, camera. src/main.c applies no Quartz Quadrant scroll-limit checks
   (SCRCHK) today; egg5meca1_scrset (BOSS_5.C) sets the Act 3 arena bounds
   itself. If src/main.c gains a zone-3 scroll check, mirror it in step().
   Only pad input changes a run: no placement, position or velocity writes.

   Goals: Act 1/2 (act index 0/1, any era): the tally, with no warp and no
   death. Act 3 (index 2, C or D): through the boss (two egg5meca2 hits, the
   belt grind of meca2's +66 counter, egg5's escape), the capsule and the
   tally.

   qq_route_search replay ACT:ERA SCRIPT LIMIT OUTPUT
       Replays SCRIPT ("COUNT PAD" lines; bits 128 Right, 64 Left, 32 Down,
       16 Up, 1 Jump; neutral after it) and writes ``sequence pad x y`` rows
       from sequence 2, then prints the tally line.
   qq_route_search search ACT:ERA SEED ITERATIONS OUTSCRIPT [PREFIX]
       Fixed-seed Go-Explore over pad prefixes (after tt_route_search.c): an
       archive of coarse cells keeps the shortest prefix that reached each;
       restoring replays it from a fresh load. The search only chooses input;
       the replay is the evidence. */
#include "scd_player.h"
#include "scd_objects.h"
#include "scd_boss.h"
#include "act.h"
#include "world.h"
#include "title_card.h"
#include "camera_v.h"
#ifdef ROUTE_WW
#include "background_r6.h"
#include "background.h"
extern unsigned scd_r6_tile_cycle(unsigned,unsigned,scd_tile_write *);
#endif
#include "EQU.H"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
extern short scramapad(sprite_status *,short,short);
#include <math.h>
unsigned scd_boss_retail_slot_peek(unsigned actor);

#ifdef ROUTE_MM
/* Metallic Madness (tools/test_qq_route.py --mm). Act 3's goal is the ending:
   BOSS_8.C's egg8 (63) takes its four hits and escapes, EMIE8.C's Amy (67)
   steers Sonic (src/main.c, plautoflag) and ends the game (gameflag 2). */
#define ROUTE_ZONE 6
#define ROUTE_STAGE "mm8"
#define ROUTE_COLLISION "mmcollision8"
#define ROUTE_OBJECTS "mmobj8"
#elif defined(ROUTE_SS)
#define ROUTE_ZONE 5
#define ROUTE_STAGE "ss7"
#define ROUTE_COLLISION "sscollision7"
#define ROUTE_OBJECTS "ssobj7"
#elif defined(ROUTE_WW)
#define ROUTE_ZONE 4
#define ROUTE_STAGE "ww6"
#define ROUTE_COLLISION "wwcollision6"
#define ROUTE_OBJECTS "wwobj6"
#else
#define ROUTE_ZONE 3
#define ROUTE_STAGE "qq5"
#define ROUTE_COLLISION "qqcollision5"
#define ROUTE_OBJECTS "qqobj5"
#endif
extern short scralim_left,scralim_right,scralim_down,scralim_n_left,scralim_n_down,scra_vline;
extern unsigned char bossflag,bossstart,limmoveflag;
static unsigned char data[400000],collision[9472],raw[10240];
static unsigned char pristine[400000],pristine_collision[9472];
static size_t data_size;
static scd_placement placements[1024];
static unsigned placement_count;
static stage_t stage;
static unsigned act,era,dead,done,sequence,buttons,delayed,boss_hits,boss_seen,boss_lowered,escaped;
#ifdef ROUTE_WW
static unsigned ww_last_hit;
#endif
static unsigned unlock_sequence;
#ifdef ROUTE_SS
static unsigned ss_race,ss_result;
#endif
#ifdef ROUTE_MM
/* HOTA8C/D.C: the room controller's routine (0-12) and its live fireflies. */
static unsigned mm_amy,mm_room,mm_flies;
#endif
/* First sequence after the search prefix (QQ_ROUTE_MIN_HIT_RINGS). */
static unsigned search_tail=~0u;
static int grind_left;
static int camera_x,camera_y,row_x,row_y;
static unsigned pads[48000],pad_count;
/* Diagnostic only: replay the retail levelVIntCounter phase for lost-ring
   floor probes. A route using this trace is never a controller-only gate. */
static unsigned char vint_expected[48000];
/* Comparison only (QQ_ROUTE_LAG, tools/retail_parity.py lag_sync): retail
   levelVIntCounter (Level/Main.asm:712) counts V-INT frames, so a lagging
   retail update (a 32-ring HurtPlayer spill, retail QQ3C row 2816) advances it
   once per extra frame; native counts one per update (src/objects.c). */
static unsigned char lag[48000];static unsigned lag_count;
/* Comparison only (QQ_ROUTE_LAG column 10, when present): the retail V-INT
   count of the same row (levelVIntCounter delta). A masked interrupt can
   swallow a V-INT, so a 3-frame update may count 2 (retail QQ1AB 1730). */
static unsigned char vint_lag[48000];static unsigned vint_lag_count;
#ifdef ROUTE_WW
static uint16_t ww_palette[64];
static unsigned ww_tile_tick,ww_title_phase;
#endif
#define PAD_LIMIT 46000
static size_t read_file(const char *name,void *buffer,size_t capacity){
    FILE *f=fopen(name,"rb");if(!f){perror(name);exit(2);}
    size_t n=fread(buffer,1,capacity,f);
    if(ferror(f) || fgetc(f)!=EOF){fprintf(stderr,"Invalid input: %s\n",name);exit(2);}
    fclose(f);return n;
}
static void read_assets(void){
    char path[128];
    snprintf(path,sizeof(path),"assets/generated/" ROUTE_STAGE "%u%c.bin",act+1,"ABCD"[era]);
    data_size=read_file(path,data,sizeof(data));memcpy(pristine,data,data_size);
    snprintf(path,sizeof(path),"assets/generated/" ROUTE_COLLISION "%u%c.bin",act+1,"ABCD"[era]);
    if(read_file(path,collision,sizeof(collision))!=9472)exit(2);
    memcpy(pristine_collision,collision,9472);
    snprintf(path,sizeof(path),"assets/generated/" ROUTE_OBJECTS "%u.bin",act+1);
    size_t bytes=read_file(path,raw,sizeof(raw));
    if(bytes%10)exit(2);
    placement_count=(unsigned)(bytes/10);
    for(unsigned i=0;i<placement_count;i++){
        placements[i].x=(int16_t)(raw[i*10]*256+raw[i*10+1]);
        placements[i].y=(int16_t)(raw[i*10+2]*256+raw[i*10+3]);
        memcpy(&placements[i].type,raw+i*10+4,5);
    }
}
/* BOSS_5.C actors by ACT53.C actno: egg5 (50), egg5meca2 (52). */
static sprite_status *boss_actor(unsigned id){
    for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++)if(actwk[i].actno==id)return &actwk[i];
    return NULL;
}
/* egg5meca2's grind counter: the PC word at +66 (src/scd_actor.h layout). */
static int meca2_grind(const sprite_status *p){return (int16_t)(p->actfree[20]|p->actfree[21]<<8);}
static void boss_track(void){
    if(act!=2)return;
#ifdef ROUTE_MM
    sprite_status *e=boss_actor(63);
    if(e){boss_seen=1;unsigned left=e->actfree[16];if(left<=4 && 4-left>boss_hits)boss_hits=4-left;if(e->r_no0>=54)escaped=1;}
    if(boss_actor(67))mm_amy=1;
    if(scd_boss8_game_end())done=1;
    mm_flies=0;
    for(unsigned i=1;i<=SCD_OBJECT_CAPACITY;i++)if(actwk[i].actno==SCD_OBJ_R8_HOTARU8){
        unsigned h=(uint8_t)actwk[i].userflag.b.h;
        if(h==254 && actwk[i].r_no0>mm_room)mm_room=actwk[i].r_no0;
        if(h<2)mm_flies++;
    }
#elif defined(ROUTE_SS)
    sprite_status *e=boss_actor(44),*m=boss_actor(47);
    if(e)boss_seen=1;
    if(m && (m->actfree[2]&32))ss_race=1;
    if(e && (e->actfree[15]&15))ss_result=e->actfree[15]&15;
    if(ss_result==2)dead=1;
    if(ss_result==1 && !e)escaped=1;
#elif defined(ROUTE_WW)
    sprite_status *b=boss_actor(52);
    if(b){
        if(b->r_no0>=2)boss_seen=1;
        unsigned hits=b->actfree[15];
        if(hits>ww_last_hit)boss_hits++;
        ww_last_hit=hits;
        if(b->actfree[3]>=3)boss_lowered=1;
        if(b->r_no0>=18)escaped=1;
        if(getenv("QQ_TRACE_WW_BOSS")){
            static unsigned previous=~0u;
            unsigned state=(b->r_no0<<16)|(b->actfree[3]<<8)|hits;
            if(state!=previous){
                fprintf(stderr,"WW boss: %u routine=%u floor=%u hit_byte=%u total_hits=%u boss_y=%d sonic_y=%d camera_bottom=%d\n",
                        sequence,b->r_no0,b->actfree[3],hits,boss_hits,b->yposi.w.h,actwk[0].yposi.w.h,scralim_down);
                previous=state;
            }
        }
    }
#else
    sprite_status *m=boss_actor(52),*e=boss_actor(50);
    if(m){
        boss_seen=1;
        unsigned hits=m->colino?2-(m->colicnt>2?2:m->colicnt):2;
        if(hits>boss_hits)boss_hits=hits;
        if(!m->colino && m->r_no0>=4)boss_lowered=1;
        int g=meca2_grind(m);if(g<grind_left)grind_left=g<0?0:g;
    }
    if(e && (e->actfree[2]&4))escaped=1;
#endif
}
static void load(void){
    memcpy(data,pristine,data_size);memcpy(collision,pristine_collision,9472);
    if(stage_open(&stage,data,data_size))exit(2);
    /* Search restores a run by replaying its pads from the initial state.
       BOSS_6.C's debris uses ranum, which must also return to its BSS seed. */
    ranum=0;
#ifdef ROUTE_MM
    mm_amy=mm_room=mm_flies=0;
#endif
#ifdef ROUTE_SS
    ss_race=ss_result=0;
#endif
#ifdef ROUTE_WW
    /* WW's GAME.C increments this global before each actor pass. */
    gametimer.w=0;
#endif
    dead=done=boss_hits=boss_seen=boss_lowered=escaped=unlock_sequence=0;buttons=delayed=0;grind_left=2400;
#ifdef ROUTE_WW
    ww_last_hit=0;
#endif
    memset(vint_expected,255,sizeof(vint_expected));
    if(getenv("QQ_VINT_TRACE")){
        FILE *v=fopen(getenv("QQ_VINT_TRACE"),"r");if(!v){perror("QQ_VINT_TRACE");exit(2);}
        unsigned seq,tick;while(fscanf(v,"%u %u",&seq,&tick)==2)if(seq<48000)vint_expected[seq]=(unsigned char)tick;
        fclose(v);
    }
    scd_boss_reset();
    scd_player_zone(ROUTE_ZONE);scd_player_act(act);scd_objects_zone(ROUTE_ZONE);scd_objects_act(act);
#ifdef ROUTE_WW
    ww_title_phase=scd_objects_ww_title_phase(act,era);
    scd_r6_palette_title_phase_set(act==1 && era<3?0:ww_title_phase);
#endif
    scd_objects_layout(placements,getenv("QQ_ROUTE_NO_OBJECTS")?0:placement_count);
    camera_x=0;camera_y=stage.start_y-140;
    if(scd_player_init(&stage,collision,sizeof(collision),era))exit(2);scd_player_objects_lead();
    camera_y=scd_camera_v_begin(ROUTE_ZONE,act,era,scd_player_get().y/65536,scd_player_get().resets);camera_x=scd_camera_h();
    scd_world_zone(ROUTE_ZONE);scd_world_act(act);scd_world_reset(era);scd_title_card_start(act);
    scd_act_camera(camera_x,camera_y);scd_boss_camera(camera_x,camera_y);
    scd_player_hold_clock(1);scd_player_step(0);scd_title_card_step();
#ifdef ROUTE_WW
    /* main.c runs the setup call and the first draw before sequence 2. The
       Good Future spark gate reads this animated-tile state during play. */
    /* Title-card draws advance R6 art before controls unlock. The object
       timer starts at zero in R61 and R63, independently of those draws. */
    static const uint8_t ww_title_draws[3][4]={{23,27,24,24},{24,25,26,25},{0,0,17,17}};
    scd_tile_write ww_tiles[5];ww_tile_tick=ww_title_draws[act][era];
    scd_r6_tile_cycle(act*4+era,0,ww_tiles);
    scd_r6_tile_cycle(act*4+era,ww_tile_tick,ww_tiles);
    if(getenv("QQ_TIMER_OFFSET"))gametimer.w+=(short)atoi(getenv("QQ_TIMER_OFFSET"));
    scd_r6_palette(act*4+era,0,ww_palette);
#endif
    sequence=1;
    if(getenv("QQ_ROUTE_DEBUG"))fprintf(stderr,"start %d,%d limits l=%d r=%d d=%d\n",scd_player_get().x/65536,scd_player_get().y/65536,scralim_left,scralim_right,scralim_down);
}
/* One src/main.c gameplay update with the pad requested at this observation. */
static void step(unsigned want){
    sequence++;
    /* Parity only (QQ_ROUTE_VINT_AT=SEQ:BYTE): set levelVIntCounter's low byte to
       retail's for update SEQ (src/objects.c lost-ring floor check cadence).
       Applied before the world V-blank baseline so the clock does not jump. */
    {static long at=-2;static unsigned byte;if(at==-2){const char *v=getenv("QQ_ROUTE_VINT_AT");at=v?atol(v):-1;if(v && strchr(v,':'))byte=(unsigned)atoi(strchr(v,':')+1);}
     if(at>=0 && (long)sequence==at)scd_objects_vint_add((byte-scd_objects_vint())&255u);}
    unsigned world_vint_before=scd_objects_vint();
    scd_act_camera(camera_x,camera_y);scd_boss_camera(camera_x,camera_y);
    /* Parity only (QQ_ROUTE_UNLOCK_AT, tools/retail_parity.py): hold controls
       until retail's unlock update, so both builds have run the same number of
       level updates. */
    static long unlock_at=-2;if(unlock_at==-2)unlock_at=getenv("QQ_ROUTE_UNLOCK_AT")?atol(getenv("QQ_ROUTE_UNLOCK_AT")):-1;
    int locked=scd_title_card_locked()||(unlock_at>=0 && (long)sequence<unlock_at);scd_player_hold_clock(locked);
    if(!locked && !unlock_sequence){unlock_sequence=sequence;
        if(getenv("QQ_ROUTE_TRACE"))fprintf(stderr,"unlock %u\n",sequence);}
    scd_objects_travel_protection(scd_world_get().ticks>0);
    int updated=1; /* Sonic keeps updating through the warp fade (src/player.c warp_save). */
    if(updated && sequence<48000 && vint_expected[sequence]!=255)
        scd_objects_vint_add((vint_expected[sequence]-scd_objects_vint()-1u)&3u);
#ifdef ROUTE_MM
    /* src/main.c: EMIE8.C steers Sonic through swdata while plautoflag is set. */
    {unsigned automatic;if(act==2 && scd_boss8_auto_control(&automatic))delayed=automatic;}
#endif
    if(updated)scd_player_step(locked?0:delayed);
    scd_title_card_step();
    (void)scd_player_music_event();
    (void)scd_boss_music();
#ifdef ROUTE_MM
    /* src/main.c's SCRCHK8 port, after Sonic and before camera scroll. */
    {int stage_zone=6,stage_act=(int)act;
    if(stage_zone==6){
        scd_player_state mm_player=scd_player_get();
        if(stage_act<2)scralim_n_down=1808;
        else if(!bossflag)scralim_n_down=784;
        else scralim_down=scralim_n_down=268;
        short limwk=(short)(scralim_n_down-scralim_down);
        if(limwk>0){scralim_down+=(camera_y+8>=scralim_down && (mm_player.flags&2))?16:4;limmoveflag=1;}
        else if(limwk<0){if(camera_y>scralim_n_down)scralim_down=(short)(camera_y&~1);scralim_down-=4;limmoveflag=1;}
    }
    }
#endif
#ifdef ROUTE_WW
    /* src/main.c's WW3 SCRCHK runs after Sonic and before camera scroll.
       It counters egg6_jisin's floor rise while Sonic stays below the boss. */
    if(act==2){
        scd_player_state ww_player=scd_player_get();
        if(!(bossflag&16))scralim_n_down=1808;
        else{
            int wx=ww_player.x/65536,wy=ww_player.y/65536;
            short target=(short)(wx>=2976?464:wy<=664?464:wy<=1176?976:1488);
            scralim_n_down=target;
            if(abs(target-scralim_down)<(wx>=2976?4:3))scralim_down=target;
            if(wx>=2976){
                short left=(short)(wx-160);
                if(left>=scralim_left){
                    if(left>scralim_right)left=scralim_right;
                    scralim_left=scralim_n_left=left;
                }
            }
        }
        if(scralim_n_down!=scralim_down){
            if((unsigned short)scralim_n_down<(unsigned short)scralim_down){
                if((unsigned short)scralim_n_down<(unsigned short)camera_y)scralim_down=(short)(camera_y&~1);
                scralim_down-=4;
            }else scralim_down+=(camera_y+8>=scralim_down && (ww_player.flags&2))?16:4;
            limmoveflag=1;
        }
    }
#endif
    scd_player_state p=scd_player_get();int x=p.x/65536,y=p.y/65536;
    row_x=x;row_y=y;
    if(scd_objects_generator())scd_world_generator_destroyed();
    unsigned world_vblanks=scd_objects_vint()-world_vint_before;
    /* Comparison only (QQ_ROUTE_LAG): RunTimeWarp counts every retail V-INT
       (Level/Main.asm VInt_Finish), lag frames included, as src/main.c counts
       Saturn V-blanks: the retail V-INT count of the row (column 10), else its
       frame count, the row the counter add below uses. */
    if(sequence-2<vint_lag_count && vint_lag[sequence-2]>1 && vint_lag[sequence-2]<8)world_vblanks+=vint_lag[sequence-2]-1u;
    else if(sequence-2>=vint_lag_count && lag_count && sequence-2<lag_count && lag[sequence-2]>1 && lag[sequence-2]<8)world_vblanks+=lag[sequence-2]-1u;
    if(scd_world_step_vblanks(p,world_vblanks)>=0)dead=2;
    int post=scd_objects_timepost();if(post)scd_world_activate(post);
    if(p.resets || p.routine>=6)dead=1;
    /* Search only (QQ_ROUTE_MIN_HIT_RINGS=N): a hit that spills fewer than N
       rings after the search prefix ends the branch (tools/route_margins.py
       rings at a hit), a margin against a ring missed after an engine fix. */
    {static int n=-1;static unsigned held_rings;if(n<0)n=getenv("QQ_ROUTE_MIN_HIT_RINGS")?atoi(getenv("QQ_ROUTE_MIN_HIT_RINGS")):0;
     if(sequence<=2)held_rings=0;
     if(n>0 && sequence>search_tail && (unsigned)plring<held_rings && held_rings<(unsigned)n)dead=1;
     held_rings=(unsigned)plring;}
    if(updated && lag_count && sequence-2<lag_count && lag[sequence-2]>1 && lag[sequence-2]<8)scd_objects_vint_add(lag[sequence-2]-1u);
    if(!scd_objects_big_ring_touched()){camera_y=scd_camera_v_follow(y,p.resets);camera_x=scd_camera_h();}
    if(camera_x<0)camera_x=0;
    if(camera_x>16064)camera_x=16064;
    if(camera_y<0)camera_y=0;
    if(camera_y>scralim_down)camera_y=scralim_down;
    scd_act_state result=scd_act_get();
    if(camera_x>scralim_right)camera_x=scralim_right;
    if(camera_x<scralim_left)camera_x=scralim_left;
    if(result.goal && camera_x<result.left)camera_x=result.left;
    if(result.phase){camera_x=result.camera_x;camera_y=result.camera_y;}
    scd_camera_v_sync(camera_y);scd_camera_h_sync(camera_x);
    {const char *r=getenv("QQ_TRACE");long f=r?strtol(r,NULL,10):0,l=r&&strchr(r,':')?strtol(strchr(r,':')+1,NULL,10):-1;
     if((long)sequence>=f && (long)sequence<=l){sprite_status *s=&actwk[0];
        fprintf(stderr,"QQ actwk: %u x=%04x.%04x y=%04x.%04x xspeed=%d yspeed=%d mspeed=%d angle=%u radius=%u flags=%u render=%u camera=%d,%d limits l=%d r=%d d=%d\n",sequence,
            (uint16_t)s->xposi.w.h,(uint16_t)s->xposi.w.l,(uint16_t)s->yposi.w.h,(uint16_t)s->yposi.w.l,s->xspeed.w,s->yspeed.w,s->mspeed.w,s->direc.b.h,s->sprvsize,s->cddat,s->actflg,camera_x,camera_y,scralim_left,scralim_right,scralim_down);
        /* Diagnostic: the 68k slot bytes $1A-$3F (patno, mstno, timers, cddat,
           routines, direc, userflag, actfree), for retail_probe PREFIX_SONIC. */
        if(getenv("QQ_TRACE_SLOT")){fprintf(stderr,"QQ slot0: %u %02x %02x%02x %02x%02x%02x %02x%02x %02x%02x %02x%02x %04x %04x",sequence,s->patno,s->mstno.b.h,s->mstno.b.l,s->patcnt,s->pattim,s->pattimm,s->colino,s->colicnt,s->cddat,s->cdsts,s->r_no0,s->r_no1,(uint16_t)s->direc.w,(uint16_t)s->userflag.w);
            for(unsigned k=0;k<22;k++)fprintf(stderr,"%s%02x",k?"":" ",s->actfree[k]);fputc('\n',stderr);}
        if(getenv("QQ_TRACE_ORBIT"))fprintf(stderr,"QQ orbit: %u angle=%u dist=%u control=%u\n",sequence,s->actfree[1],s->actfree[15],s->actfree[2]);
        if(getenv("QQ_TRACE_VIEWS")){static scd_object_view v[256];unsigned n=scd_objects_views(v,256);
            for(unsigned k=0;k<n;k++)if(getenv("QQ_TRACE_VIEWS")[0]=='a' || (abs(v[k].x-s->xposi.w.h)<96 && abs(v[k].y-s->yposi.w.h)<96))
                fprintf(stderr,"QQ view: %u type=%u sub=%u x=%d y=%d frame=%u\n",sequence,v[k].type,v[k].subtype,v[k].x,v[k].y,v[k].frame);}
        if(getenv("QQ_TRACE_CHARGE"))fprintf(stderr,"QQ charge: %u charge=%u flags=%u anim=%u\n",sequence,s->actfree[0],s->cddat,s->mstno.b.h);
        if(getenv("QQ_TRACE_INVENTORY"))fprintf(stderr,"QQ inventory: %u rings=%u shield=%u\n",sequence,(unsigned)plring,(unsigned)plpower_b);
        if(getenv("QQ_TRACE_SLOTS"))for(unsigned j=0;j<SCD_OBJECT_CAPACITY;j++)if(actwk[j+1].actno && (getenv("QQ_TRACE_ACTNO")?(!strcmp(getenv("QQ_TRACE_ACTNO"),"all") || actwk[j+1].actno==(unsigned)atoi(getenv("QQ_TRACE_ACTNO"))):(abs(actwk[j+1].xposi.w.h-s->xposi.w.h)<96 && abs(actwk[j+1].yposi.w.h-s->yposi.w.h)<96)))
            fprintf(stderr,"QQ slot: %u slot=%u actno=%u x=%d y=%d r_no0=%u cddat=%u actflg=%u hs=%u vs=%u stand=%u vslot=%u col=%u r1=%u\n",sequence,j+1,actwk[j+1].actno,actwk[j+1].xposi.w.h,actwk[j+1].yposi.w.h,actwk[j+1].r_no0,actwk[j+1].cddat,actwk[j+1].actflg,actwk[j+1].sprhsize,actwk[j+1].sprvsize,s->actfree[19],scd_boss_retail_slot_peek(j+1),actwk[j+1].colino,actwk[j+1].r_no1);
        if(getenv("QQ_TRACE_VLINE"))fprintf(stderr,"QQ vline: %u vline=%d down=%d bossflag=%d bossstart=%d\n",sequence,scra_vline,scralim_down,bossflag,bossstart);
        if(getenv("QQ_TRACE_BOSS"))for(unsigned j=SCD_BOSS_FIRST_SLOT;j<128;j++)if(actwk[j].actno)
            fprintf(stderr,"QQ boss: %u slot=%u vslot=%u actno=%u x=%d.%u y=%d.%u r_no0=%u r_no1=%u col=%u colicnt=%u actflg=%u xs=%d ys=%d hs=%u vs=%u t31=%d t32=%d\n",sequence,j,scd_boss_retail_slot_peek(j),actwk[j].actno,actwk[j].xposi.w.h,actwk[j].xposi.w.l,actwk[j].yposi.w.h,actwk[j].yposi.w.l,actwk[j].r_no0,actwk[j].r_no1,actwk[j].colino,actwk[j].colicnt,actwk[j].actflg,actwk[j].xspeed.w,actwk[j].yspeed.w,actwk[j].sprhsize,actwk[j].sprvsize,(short)(actwk[j].actfree[16]|actwk[j].actfree[17]<<8),(short)(actwk[j].actfree[18]|actwk[j].actfree[19]<<8));
        if(getenv("QQ_TRACE_ACTOR"))for(unsigned j=0;j<SCD_OBJECT_CAPACITY;j++)if(actwk[j+1].actno==SCD_OBJ_R6_BATTA && actwk[j+1].xposi.w.h>2400 && actwk[j+1].xposi.w.h<2600)
            fprintf(stderr,"QQ actor: %u slot=%u x=%d.%u y=%d.%u routine=%u flags=%u col=%u\n",sequence,j+1,actwk[j+1].xposi.w.h,actwk[j+1].xposi.w.l,actwk[j+1].yposi.w.h,actwk[j+1].yposi.w.l,actwk[j+1].r_no0,actwk[j+1].actflg,actwk[j+1].colino);
        if(getenv("QQ_TRACE_TERRAIN"))for(int side=-1;side<=1;side+=2)for(int below=0;below<=16;below+=16){
            int sx=s->xposi.w.h+side*(int)s->sprhs,sy=s->yposi.w.h+(int)s->sprvsize+below;
            unsigned raw_chunk=stage.part[3][(sy>>8)*64+(sx>>8)],chunk=raw_chunk&127,block=0;
            if(chunk){unsigned at=(chunk-1)*512+((sy>>4)&15)*32+((sx>>4)&15)*2;
                block=((unsigned)stage.part[2][at]<<8)|stage.part[2][at+1];}
            unsigned id=collision[block&0x7ff];
            fprintf(stderr,"QQ terrain: %u sensor=%d,%d radius=%u,%u chunk=%u block=%04x collision=%u height=%d angle=%u\n",
                    sequence,sx,sy,s->sprhs,s->sprvsize,raw_chunk,block,id,
                    (int)(signed char)collision[1024+id*16+((block&0x800)?(~sx&15):(sx&15))],collision[9216+id]);
        }
        if(getenv("QQ_TRACE_TERRAIN")){
            int sx=s->xposi.w.h+13,sy=s->yposi.w.h+8;
            unsigned raw_chunk=stage.part[3][(sy>>8)*64+(sx>>8)],chunk=raw_chunk&127,block=0;
            if(chunk){unsigned at=(chunk-1)*512+((sy>>4)&15)*32+((sx>>4)&15)*2;
                block=((unsigned)stage.part[2][at]<<8)|stage.part[2][at+1];}
            unsigned id=collision[block&0x7ff];
            fprintf(stderr,"QQ side: %u sensor=%d,%d chunk=%u block=%04x collision=%u width=%d angle=%u\n",sequence,sx,sy,raw_chunk,block,id,(int)(signed char)collision[5120+id*16+((block&0x1000)?(~sy&15):(sy&15))],collision[9216+id]);
        }
     }}
    boss_track();
    if(result.phase==SCD_ACT_DONE)done=1;
    /* Search only (QQ_ROUTE_GOAL=bigring): the act must end through the big ring
       (Level End/Main.asm ObjBigRing, 50 rings); an ordinary tally fails the run.
       A separate statement keeps the line above, which derived hosts patch. */
    {static int bigring=-1;if(bigring<0){const char *g=getenv("QQ_ROUTE_GOAL");bigring=g && !strcmp(g,"bigring");}
     if(bigring && result.phase==SCD_ACT_DONE && !scd_objects_big_ring_touched()){done=0;dead=1;}}
#ifdef ROUTE_WW
    scd_r6_set_bossflag(bossflag);
    /* src/main.c draw_stage: the COL6 clock is the level program's update count
       (GAME.C game_init clears clchgcnt/clchgtim; Level/Main.asm:210 clears
       cameraX..+$FF, which holds palCycleSteps/Timers), so it restarts on a
       time-warp arrival and a death restart; player frame keeps counting. */
    scd_r6_palette(act*4+era,scd_player_level_frames(),ww_palette);
    scd_tile_write ww_tiles[5];scd_r6_tile_cycle(act*4+era,++ww_tile_tick,ww_tiles);
    bossflag=(unsigned char)scd_r6_cg_change(act*4+era,bossflag);
    const char *spark_range=getenv("QQ_TRACE_SPARKS");
    if(spark_range){unsigned first,last;
        if(sscanf(spark_range,"%u:%u",&first,&last)==2 && sequence>=first && sequence<=last)
            fprintf(stderr,"WW sparks: %u tick=%u active=%u\n",sequence,ww_tile_tick,scd_r6_sparks_active());
    }
#endif
    /* Libretro's pad request is sampled two observations later. */
    delayed=buttons;
    buttons=(want&128?SCD_RIGHT:0)|(want&64?SCD_LEFT:0)|(want&32?SCD_DOWN:0)|(want&16?SCD_UP:0)|(want&1?SCD_JUMP:0);
}
static unsigned rng_state;
static unsigned rng(void){rng_state=rng_state*1103515245u+12345u;return (rng_state>>16)&32767;}
static unsigned boss_stage(void){
    if(act!=2)return 0;
#ifdef ROUTE_MM
    /* Three bits (cell key): room, fireflies, boss, two hits, escape, Amy, end. */
    if(done)return 7;
    if(mm_amy)return 6;
    if(escaped)return 5;
    if(boss_hits>=2)return 4;
    if(boss_seen)return 3;
    return mm_room>=10?2:mm_room>=2?1:0;
#elif defined(ROUTE_SS)
    if(scd_act_get().phase)return 7;
    if(escaped)return 6;
    if(ss_result==1)return 5;
    if(ss_race)return 4;
    return bossstart==7?2:boss_seen?1:0;
#elif defined(ROUTE_WW)
    if(scd_act_get().phase)return 7;
    if(escaped)return 6;
    const sprite_status *b=boss_actor(52);
    if(!b)return boss_seen?1:0;
    /* Repeated contacts on one floor raise boss_hits without winning.
       BOSS_6.C only enters its defeat routine after the floor-3 hit. */
    if(b->r_no0>=12)return 5;
    unsigned floor=b->actfree[3];
    return floor+1+(b->actfree[15]!=0 && floor<3);
#else
    return scd_act_get().goal?7:escaped?6:grind_left<1200?5:boss_lowered?4:boss_hits?1+boss_hits:boss_seen?1:0;
#endif
}
static void macro(void){
    static const unsigned choices[]={128,64,0,1,129,65,32,160,96,33,16,144};
    unsigned pad=choices[rng()%12],len=4+rng()%28;
    /* On the belt (egg5belt): the grind needs a long Right run; offer one. */
    #ifdef ROUTE_SS
    if(act==2 && boss_stage()==2){pad=0;len=60+rng()%180;}
    if(act==2 && boss_stage()==4 && rng()%2){pad=128;len=30+rng()%90;}
    if(act==2 && boss_stage()>=5 && rng()%3==0){pad=0;len=60+rng()%180;}
#else
    /* MM3 too: the finishing MM3C/D routes wait at the arena's right wall
       (x 3984) for egg8's third and fourth passes. */
    if(boss_stage()>=4 && boss_stage()<6 && rng()%2){pad=128;len=30+rng()%90;}
#endif
    /* Retail needs a crouch before a spin dash (native buffers Down + jump
       from a standstill, a deliberate deviation): lead 33 with two Down pads
       so a found route stays comparable with retail. */
    if(pad==33 && (!pad_count || !(pads[pad_count-1]&32)))
        for(unsigned i=0;i<2 && !dead && !done && pad_count<PAD_LIMIT;i++){pads[pad_count++]=32;step(32);}
    if(pad&1){
        unsigned hold=1+rng()%24;
        for(unsigned i=0;i<hold && !dead && !done && pad_count<PAD_LIMIT;i++){pads[pad_count++]=pad;step(pad);}
        pad&=~1u;len=2+rng()%6;
    }
    for(unsigned i=0;i<len && !dead && !done && pad_count<PAD_LIMIT;i++){pads[pad_count++]=pad;step(pad);}
}
typedef struct {uint32_t key;uint8_t *pads;unsigned length,visits,tried;double value;} cell;
static cell *cells;static unsigned cell_count,cell_capacity;
static uint32_t cell_key(void){
    scd_player_state p=scd_player_get();
    unsigned x=(unsigned)(p.x/65536<0?0:p.x/65536>16383?16383:p.x/65536)/32,y=(unsigned)(p.y/65536<0?0:p.y/65536>2047?2047:p.y/65536)/32;
    unsigned grind=(unsigned)(2400-grind_left)/64;
    uint32_t key=x|(y<<9)|(boss_stage()<<15)|((grind&63)<<18)|((uint32_t)(boss_hits&3)<<24);
#ifdef ROUTE_WW
    /* A ring and upward motion are distinct survival paths on R63's spark
       floors. The coarse XY cell otherwise discards both after one visit. */
    unsigned vertical=p.vy<-256?0:p.vy>256?2:1;
    key|=((uint32_t)(plring!=0)<<26)|((uint32_t)vertical<<27);
#endif
#ifdef ROUTE_SS
    /* SS vertical spin tunnels preserve travel direction (PLAYSUB.C ball_r).
       Keep descent and rolling entries instead of replacing them with a
       shorter ascending prefix at the same coarse position. */
    unsigned vertical=p.vy<-256?0:p.vy>256?2:1;
    key|=((uint32_t)vertical<<26)|((uint32_t)((actwk[0].cddat&4)!=0)<<28);
#endif
#ifdef ROUTE_MM
    /* SHUT.C kaiten swaps the player's layer (prio_flag) in place: without
       this bit the shorter pre-swap prefix replaces the swapped state at the
       same coarse position, and MM2's back-layer paths are never kept. */
    key|=(uint32_t)(prio_flag!=0)<<26;
    /* MM3: egg8's routine (63, r_no0) in the grind bits (always 0 in MM).
       Position alone keeps only the earliest arrival at each spot; the
       third and fourth hits need a later attack phase (retail matches the
       host to the death at 6408 when Sonic only waits at the wall). */
    if(act==2){const sprite_status *e=boss_actor(63);if(e)key|=(uint32_t)((e->r_no0/2u)&63u)<<18;}
#endif
#ifdef ROUTE_SS
    if(act==2){
        unsigned amy=0;
        for(unsigned i=1;i<=SCD_OBJECT_CAPACITY;i++)if(actwk[i].actno==SCD_OBJ_R7_EMIE7){
            amy=actwk[i].r_no0;
            /* EMIE7 move1 decrements word26 from600 after the rescue. */
            unsigned timer=actwk[i].actfree[6]|actwk[i].actfree[7]<<8;
            key|=(uint32_t)(timer/80u&7u)<<29;
            break;
        }
        key|=(amy&15)<<18;
        const sprite_status *metal=boss_actor(47);
        if(metal)key|=(uint32_t)(metal->r_no0&15)<<22;
    }
#endif
    /* Search only (QQ_ROUTE_RINGS): ring count buckets of 8 keep ring-rich
       prefixes apart from shorter ones at the same place. */
    {static int rings=-1;if(rings<0)rings=getenv("QQ_ROUTE_RINGS")!=NULL;
     if(rings)key|=(uint32_t)((plring>56?56:plring)/8)<<29;}
    return key;
}
static double cell_value(void){
    scd_player_state p=scd_player_get();int x=p.x/65536;
    double v=boss_stage()*100000.0+boss_hits*20000.0+(2400-grind_left)*30.0+x;
#ifdef ROUTE_MM
    /* The room waits for both fireflies: reward each one gone. */
    if(act==2 && !boss_seen)v+=mm_room*2000.0-mm_flies*10000.0;
    /* R82: the sign (8000,212) and big ring (8087,131) sit at the top of the
       map; x alone leaves the search on the floor below them (2A x~7904 y~1600). */
    if(act==1 && x>=7300)v+=(2048-p.y/65536)*2.0;
    /* Search only (QQ_ROUTE_MM_TOP=BONUS): MM2's sign is reached along the
       top corridor after a backtrack to x ~6350 (the 2026-10-16 MM2D route);
       reward that corridor so the backtrack is kept. */
    {static double top=-1;if(top<0)top=getenv("QQ_ROUTE_MM_TOP")?atof(getenv("QQ_ROUTE_MM_TOP")):0;
     if(act==1 && top>0 && p.y/65536<=300 && x>=6300)v+=top;}
#endif
    /* Search only (QQ_ROUTE_RINGS=W): W per ring held up to 50, and 20000 more
       from 50, the big ring's threshold (Level End/Main.asm ObjBigRing_Main). */
    {static int w=-1;if(w<0)w=getenv("QQ_ROUTE_RINGS")?atoi(getenv("QQ_ROUTE_RINGS")):0;
     if(w)v+=(plring>50?50:plring)*(double)w+(plring>=50?20000.0:0);}
    /* Search only (QQ_ROUTE_BONUS=X0,X1,Y0,Y1,VALUE): reward one box, a
       waypoint for a detour the x-valued archive does not keep. */
    {static int set=-1;static double b[5];
     if(set<0)set=getenv("QQ_ROUTE_BONUS") && sscanf(getenv("QQ_ROUTE_BONUS"),"%lf,%lf,%lf,%lf,%lf",b,b+1,b+2,b+3,b+4)==5;
     int y=p.y/65536;if(set && x>=b[0] && x<=b[1] && y>=b[2] && y<=b[3])v+=b[4];}
#ifdef ROUTE_WW
    /* Keep ringed paths competitive with later boss stages so search can
       explore survival after the third hit. */
    if(boss_stage()>=3 && plring)v+=150000.0;
#endif
#ifdef ROUTE_SS
    if(act==2 && escaped){
        for(unsigned i=1;i<=SCD_OBJECT_CAPACITY;i++)if(actwk[i].actno==SCD_OBJ_R7_EMIE7){
            const sprite_status *a=&actwk[i];
            unsigned timer=a->actfree[6]|a->actfree[7]<<8;
            v+=a->r_no0*2000.0+(600-(timer>600?600:timer))*10.0;
            if(!a->r_no0)v-=abs(x-a->xposi.w.h)*30.0;
            break;
        }
    }
#endif
    /* Before the hits: stay close to egg5meca2 so a rolling hit can land. */
    #ifndef ROUTE_SS
    /* MM skips it: a pull toward egg8 (63) starved the right-wall waits
       that land its later hits (MM3C/D searches stalled at two hits). */
    #ifndef ROUTE_MM
    if(boss_stage()>=1 && boss_stage()<4){const sprite_status *m=boss_actor(52);
        if(m){int bx=m->xposi.w.h,by=m->yposi.w.h,y=p.y/65536;v-=sqrt((double)(x-bx)*(x-bx)+(double)(y-by)*(y-by))*20.0;}}
    #endif
#endif
    return v;
}
static void archive(void){
    if(dead)return;
    uint32_t key=cell_key();
    for(unsigned i=0;i<cell_count;i++)if(cells[i].key==key){
        if(pad_count<cells[i].length){
            cells[i].pads=realloc(cells[i].pads,pad_count?pad_count:1);
            for(unsigned j=0;j<pad_count;j++)cells[i].pads[j]=(uint8_t)pads[j];
            cells[i].length=pad_count;cells[i].value=cell_value();
        }
        return;
    }
    if(cell_count==cell_capacity){cell_capacity=cell_capacity?cell_capacity*2:1024;cells=realloc(cells,sizeof(cell)*cell_capacity);}
    cell *c=&cells[cell_count++];c->key=key;c->length=pad_count;c->visits=0;c->tried=0;c->value=cell_value();
    c->pads=malloc(pad_count?pad_count:1);for(unsigned j=0;j<pad_count;j++)c->pads[j]=(uint8_t)pads[j];
}
static void restore(const cell *c){
    pad_count=0;load();
    for(unsigned j=0;j<c->length;j++){pads[pad_count++]=c->pads[j];step(c->pads[j]);}
#ifdef ROUTE_WW
    if(cell_key()!=c->key){
        fprintf(stderr,"WW route restore mismatch: expected key %u, got %u, length %u, sequence %u\n",c->key,cell_key(),c->length,sequence);
        exit(3);
    }
#endif
}
static void write_script(const char *name){
    FILE *f=fopen(name,"w");if(!f)exit(2);
    for(unsigned i=0;i<pad_count;){
        unsigned j=i;while(j<pad_count && pads[j]==pads[i])j++;
        fprintf(f,"%u %u\n",j-i,pads[i]);i=j;
    }
    fclose(f);
}
static void read_script(const char *name,unsigned limit){
    FILE *f=fopen(name,"r");if(!f){perror(name);exit(2);}
    unsigned n,pad;
    while(fscanf(f,"%u %u",&n,&pad)==2){
        if(pad&~0xf1u)exit(2);
        while(n-- && pad_count<limit)pads[pad_count++]=pad;
    }
    fclose(f);
}
static void found(unsigned it,const char *out){
    write_script(out);
    fprintf(stderr,"search done: iterations=%u cells=%u sequence=%u\n",it,cell_count,sequence);
}
static double explore=0.05;
static int search(unsigned seed,unsigned iterations,const char *out,const char *prefix){
    rng_state=seed;load();
    if(prefix){read_script(prefix,PAD_LIMIT);for(unsigned i=0;i<pad_count && !dead;i++)step(pads[i]);}
    search_tail=sequence;
    if(dead){fprintf(stderr,"prefix died\n");return 2;}
    archive();
    double top=-1e30;
    static double weight[1<<20];
    for(unsigned it=0;it<iterations;it++){
        double best=-1e30;for(unsigned i=0;i<cell_count;i++)if(cells[i].value>best)best=cells[i].value;
        double total=0;
        for(unsigned i=0;i<cell_count && i<(1u<<20);i++){
            /* Frontier cells first; every cell keeps a novelty weight (after
               Go-Explore's count weighting), so a detour can be found. */
            double w=(cells[i].value>=best-200?4.0:cells[i].value>=best-2000?1.0:explore)/sqrt(cells[i].visits+1.0);
            weight[i]=w;total+=w;
        }
        double r=(rng()/32768.0+rng()/1073741824.0)*total;unsigned pick=0;
        for(;pick+1<cell_count && r>weight[pick];pick++)r-=weight[pick];
        cells[pick].visits++;restore(&cells[pick]);
        /* A goal-reached cell first tries a neutral finish: the sign, the
           capsule and the tally need no input. */
        if(scd_act_get().goal && !cells[pick].tried){
            cells[pick].tried=1;
            for(unsigned t=0;t<1500 && !dead && !done && pad_count<PAD_LIMIT;t++){pads[pad_count++]=0;step(0);}
            if(done){found(it,out);return 0;}
            restore(&cells[pick]);
        }
        unsigned macros=4+rng()%24;
        for(unsigned m=0;m<macros && !dead && !done;m++){macro();archive();}
        if(done){found(it,out);return 0;}
        if(best>top || it%2000==0){
            top=best;unsigned b=0;for(unsigned i=0;i<cell_count;i++)if(cells[i].value>cells[b].value)b=i;
            uint32_t k=cells[b].key;
            fprintf(stderr,"it %u cells %u best %.0f x~%u y~%u boss %u len %u\n",it,cell_count,cells[b].value,(k&511)*32,((k>>9)&63)*32,(k>>15)&7,cells[b].length);
            /* Diagnostic (QQ_ROUTE_BEST=PATH): the best cell's prefix as a
               script, for inspecting a stalled frontier; no search effect. */
            if(getenv("QQ_ROUTE_BEST")){FILE *f=fopen(getenv("QQ_ROUTE_BEST"),"w");
                if(f){for(unsigned i=0;i<cells[b].length;){unsigned j=i;while(j<cells[b].length && cells[b].pads[j]==cells[b].pads[i])j++;
                    fprintf(f,"%u %u\n",j-i,cells[b].pads[i]);i=j;}fclose(f);}}
        }
    }
    unsigned b=0;for(unsigned i=0;i<cell_count;i++)if(cells[i].value>cells[b].value)b=i;
    restore(&cells[b]);write_script(out);
    fprintf(stderr,"search end: cells=%u value=%.0f\n",cell_count,cells[b].value);
    return 1;
}
int main(int argc,char **argv){
    if(argc<6 || strlen(argv[2])!=3 || argv[2][1]!=':' || argv[2][0]<'0' || argv[2][0]>'2' || argv[2][2]<'A' || argv[2][2]>'D'){
        fprintf(stderr,"usage: qq_route_search replay ACT:ERA SCRIPT LIMIT OUTPUT | search ACT:ERA SEED ITERATIONS OUTSCRIPT [PREFIX]\n");return 2;
    }
    act=(unsigned)(argv[2][0]-'0');era=(unsigned)(argv[2][2]-'A');
    if(getenv("QQ_ROUTE_LAG")){
        FILE *f=fopen(getenv("QQ_ROUTE_LAG"),"r");char line[256];
        while(f && fgets(line,sizeof line,f) && lag_count<48000){unsigned v[9];unsigned w;int n=sscanf(line,"%u %u %u %u %u %u %u %u %u %u",v,v+1,v+2,v+3,v+4,v+5,v+6,v+7,v+8,&w);if(n>=9){if(n==10 && vint_lag_count==lag_count)vint_lag[vint_lag_count++]=(unsigned char)w;lag[lag_count++]=(unsigned char)v[8];}}
        if(f)fclose(f);
    }
    if(getenv("QQ_ROUTE_EXPLORE"))explore=atof(getenv("QQ_ROUTE_EXPLORE"));
    if(act==2 && era<2)return 2;

#ifdef ROUTE_WW
    /* Act 3 is enabled for controller-only boss route exploration. */
#endif
    read_assets();
    if(!strcmp(argv[1],"search"))return search((unsigned)atoi(argv[3]),(unsigned)atoi(argv[4]),argv[5],argc>6?argv[6]:NULL);
    if(!strcmp(argv[1],"actors")){
        /* Diagnostic: replay SCRIPT for LIMIT updates, list the actors near Sonic. */
        read_script(argv[3],PAD_LIMIT);load();unsigned limit=(unsigned)atoi(argv[4]);
        for(unsigned i=0;i<limit && !dead;i++)step(i<pad_count?pads[i]:0);
        scd_player_state p=scd_player_get();printf("sonic %d,%d dead %u radius %u anim %u render %u block %04x beam %u\n",p.x/65536,p.y/65536,dead,actwk[0].sprvsize,actwk[0].mstno.b.h,actwk[0].actflg,(unsigned short)scramapad(&actwk[0],p.x/65536,p.y/65536),st6clrchg);
        for(unsigned k=1;k<=127;k++){sprite_status *o=&actwk[k];if(!o->actno)continue;
            int dx=o->xposi.w.h-p.x/65536,dy=o->yposi.w.h-p.y/65536;
            if(abs(dx)<400 && abs(dy)<300)printf("actor %u type %u at %d,%d r_no0 %u sub %d size %u,%u flg %02x col %u home_y %d timer %u\n",k,o->actno,o->xposi.w.h,o->yposi.w.h,o->r_no0,o->userflag.b.h,o->sprhsize,o->sprvsize,o->actflg,o->colino,(short)(o->actfree[8]|o->actfree[9]<<8),(unsigned short)gametimer.w);}
        return 0;
    }
    if(strcmp(argv[1],"replay"))return 2;
    unsigned limit=(unsigned)atoi(argv[4]);if(limit<10 || limit>PAD_LIMIT)return 2;
    read_script(argv[3],limit);load();
    FILE *out=fopen(argv[5],"w");if(!out){perror(argv[5]);return 2;}
    unsigned timer_first=0,timer_last=0;
    const char *timer_range=getenv("QQ_TRACE_TIMER");
    if(timer_range)sscanf(timer_range,"%u:%u",&timer_first,&timer_last);
    for(unsigned i=0;i<limit;i++){
        unsigned want=i<pad_count?pads[i]:0;
        step(want);
        scd_player_state p=scd_player_get();
        if(dead){fprintf(stderr,"Route failed at %u x=%d y=%d dead=%u\n",sequence,p.x/65536,p.y/65536,dead);fclose(out);return 3;}
        /* Parity rows (QQ_ROUTE_TRACE) in tools/retail_parity.py's column order:
           tt_route_search's, with the two water columns zero. */
        if(getenv("QQ_ROUTE_TRACE"))fprintf(out,"%u %u %d %d 0 0 %d %u %d %d %u %u %u\n",sequence,want,actwk[0].xposi.w.h,actwk[0].yposi.w.h,actwk[0].yspeed.w,actwk[0].cddat,
                                          actwk[0].mspeed.w,actwk[0].xspeed.w,actwk[0].xposi.w.l,actwk[0].yposi.w.l,actwk[0].direc.b.h);
        else fprintf(out,"%u %u %d %d\n",sequence,want,row_x,row_y);
        if(timer_range && sequence>=timer_first && sequence<=timer_last){
#ifdef ROUTE_WW
            fprintf(stderr,"WW timer: %u %u %d %d palette3=%u\n",sequence,(unsigned short)gametimer.w,row_x,row_y,scd_r6_palette_count(3));
#endif
        }
        if(done){
            fclose(out);
#ifdef ROUTE_SS
            if(act==2){
                fprintf(stderr,"SS race complete: seen=%u race=%u result=%u escaped=%u stationary=%u\n",boss_seen,ss_race,ss_result,escaped,scd_act_stationary_results());
                if(!boss_seen || !ss_race || ss_result!=1 || !escaped || !scd_act_stationary_results())return 4;
            }
#endif
#ifdef ROUTE_WW
            fprintf(stderr,"WW native controls unlock at sequence=%u\n",unlock_sequence);
#endif
#ifdef ROUTE_MM
            if(act==2){
                fprintf(stderr,"MM ending complete: seen=%u hits=%u escaped=%u amy=%u game_end=%d\n",boss_seen,boss_hits,escaped,mm_amy,scd_boss8_game_end());
                if(!boss_seen || boss_hits<4 || !escaped || !mm_amy || !scd_boss8_game_end())return 4;
            }
#endif
            fprintf(stderr,"Big ring: touched=%d rings=%u\n",scd_objects_big_ring_touched(),(unsigned)plring);
            fprintf(stderr,"Tally complete: sequence=%u act=%u era=%u score=%u boss_hits=%u lowered=%u grind_left=%d escaped=%u\n",
                    sequence,act,era,p.score,boss_hits,boss_lowered,grind_left,escaped);
            return 0;
        }
    }
    fclose(out);fprintf(stderr,"Route incomplete\n");return 1;
}
