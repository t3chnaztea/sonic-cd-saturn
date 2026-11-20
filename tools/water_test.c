/* Tidal Tempest water fixture driver. Built twice by tools/test-water.sh:
   -DWATER_ORIGINAL against build/water/original.c (the compiled original
   routines on actwk[7]/actwk[32..]) and against src/water.c. Both builds run
   the same scripted player and camera and print one trace line per frame;
   the script compares the traces byte for byte. */
#include "EQU.H"
#include "ACTION.H"
#include "PLAYER.H"
#include <stdio.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include "water_data.h"

static unsigned frame_no;
/* Trace sink: an FNV-1a hash of every line, plus counts; the lines themselves
   only with WATER_TRACE=1 (tools/test-water.sh reruns that way on a mismatch). */
static uint64_t trace_hash=1469598103934665603ULL;
static unsigned long trace_lines,trace_sounds,trace_bgm,trace_drowns;
static int trace_out;
static void out(const char *format,...){
    char line[512];va_list args;va_start(args,format);int n=vsnprintf(line,sizeof(line),format,args);va_end(args);
    for(int i=0;i<n;i++){trace_hash^=(unsigned char)line[i];trace_hash*=1099511628211ULL;}
    for(int i=0;i<n;i++)trace_lines+=line[i]=='\n';
    if(trace_out)fputs(line,stdout);
}
void soundset(short id){out("F%u sound %d\n",frame_no,id);trace_sounds++;trace_drowns+=id==182;}
static void bgm(short id){out("F%u bgm %d\n",frame_no,id);trace_bgm++;}
#ifdef WATER_ORIGINAL
void bgmset(short id){bgm(id);}
void (*WaveAllStop)(void);
extern short *water_original_table;
extern short water_original_41A[],water_original_41B[],water_original_41C[],water_original_42A[],
    water_original_42B[],water_original_42C[],water_original_43[];
void water_original_game_init(void);
void watercoli(void);void watercnt(void);void plawa(sprite_status*);void exit2(sprite_status*);
static game_info keep;
static void w_reset(unsigned act,unsigned era){
    short *tables[3][4]={{water_original_41A,water_original_41B,water_original_41C,water_original_41C},
        {water_original_42A,water_original_42B,water_original_42C,water_original_42C},
        {water_original_43,water_original_43,water_original_43,water_original_43}};
    lpKeepWork=&keep;water_original_table=tables[act][era];
    memset(&actwk[1],0,sizeof(actwk)-sizeof(actwk[0]));
    stageno.b.h=2;stageno.b.l=act;water_original_game_init();
}
static void w_tick(void){++gametimer.w;}
static void w_player(void){plwaterchk();}
static void w_objects(void){
    for(unsigned i=1;i<128;i++){
        if(actwk[i].actno==33)plawa(&actwk[i]);else if(actwk[i].actno==11)exit2(&actwk[i]);
    }
}
static void w_currents(void){watercoli();}
static void w_visible(void){
    for(unsigned i=0;i<8;i++){
        for(unsigned a=0;a<pbuffer[i].cnt;a++){
            sprite_status *p=pbuffer[i].pActwk[a];if(p->actno && p->patbase)p->actflg|=128;
        }
        pbuffer[i].cnt=0;
    }
}
static void w_level(void){watercnt();}
static void w_refill(void){plairset();}
static const sprite_status *w_object(unsigned i){return i==0?&actwk[7]:&actwk[31+i];}
#else
#include "water.h"
void (*WaveAllStop)(void);
static void w_reset(unsigned act,unsigned era){water_bgm_sink_set(bgm);stageno.b.h=2;stageno.b.l=act;water_reset(2,act,era);}
static void w_tick(void){water_tick();}
static void w_player(void){water_player_check();}
static void w_objects(void){water_objects_step();}
static void w_currents(void){water_currents();}
static void w_visible(void){water_objects_visible();}
static void w_level(void){water_level_step();}
static void w_refill(void){water_air_refill();}
static sprite_status object_copy;
static const sprite_status *w_object(unsigned i){
    const water_object *o=&water_objects()[i];sprite_status *p=&object_copy;memset(p,0,sizeof(*p));
    if(!o->used)return p;
    p->actno=o->actno;p->r_no0=o->r_no0;p->actflg=o->actflg;p->mstno.b.h=o->mstno;p->patno=o->patno;
    p->patcnt=o->patcnt;p->pattim=o->pattim;p->userflag.b.h=o->userflag;p->direc.b.h=o->direc;
    p->sproffset=o->sproffset;p->xposi.l=o->x;p->yposi.l=o->y;p->yspeed.w=o->yspeed;memcpy(p->actfree,o->actfree,22);
    return p;
}
#endif
#define OBJECTS 24

static void trace(void){
    const sprite_status *p=&actwk[0];
    out("F%u p %d.%d %d.%d v %d %d %d c %02x m %d r %d o %02x s %04x/%d w %d %d %d %d h %u f %u k %u a %d cap %d %d %d g %u rn %08x ss %d\n",
        frame_no,p->xposi.w.h,(unsigned short)p->xposi.w.l,p->yposi.w.h,(unsigned short)p->yposi.w.l,
        p->xspeed.w,p->yspeed.w,p->mspeed.w,p->cddat,p->mstno.b.h,p->r_no0,p->actfree[2],p->sproffset,p->sprpri,
        waterposi,waterposi_m,watermoveposi,waterspeed,hintposi.b.l,waterflag,watercoliflag,pl_air,
        plmaxspdwk,pladdspdwk,plretspdwk,gametimer.w,(unsigned)ranum,scroll_start.b.h);
    for(unsigned i=0;i<OBJECTS;i++){
        const sprite_status *o=w_object(i);
        if(!o->actno)continue;
        out("F%u o%u n%u r%u fl%02x m%u pt%u pc%u tm%u u%u d%u so%04x x%d y%d.%04x vy%d af",
            frame_no,i,o->actno,o->r_no0,o->actflg,o->mstno.b.h,o->patno,o->patcnt,o->pattim,
            o->userflag.b.h,o->direc.b.h,o->sproffset,o->xposi.w.h,o->yposi.w.h,(unsigned short)o->yposi.w.l,o->yspeed.w);
        for(unsigned b=0;b<22;b++)out("%02x",o->actfree[b]);
        out("\n");
    }
}

/* Player script: position integrates the speeds like speedset2; the camera
   follows (scroll() stand-in, not under test). */
static int cam_dx=-160,cam_dy=-96,script_move=1;
static void move_player(void){
    if(!script_move)return;
    if(actwk[0].actfree[2]&1)return;   /* drowning: the master moves Sonic */
    if(actwk[0].r_no0>=6)return;
    speedset2(&actwk[0]);
}
static void camera(void){
    scra_h_posit.w.h=(short)(actwk[0].xposi.w.h+cam_dx);
    int y=actwk[0].yposi.w.h+cam_dy;if(y<0)y=0;
    scra_v_posit.w.h=(short)y;
}
static void place(int x,int y,int xs,int ys,unsigned cddat){
    memset(&actwk[0],0,sizeof(actwk[0]));actwk[0].actno=1;actwk[0].r_no0=2;
    actwk[0].xposi.w.h=(short)x;actwk[0].yposi.w.h=(short)y;actwk[0].xspeed.w=(short)xs;actwk[0].yspeed.w=(short)ys;
    actwk[0].cddat=(unsigned char)cddat;actwk[0].sprvsize=19;actwk[0].sprhs=9;
    plmaxspdwk=1536;pladdspdwk=12;plretspdwk=128;
}
static void begin(unsigned act,unsigned era,int x,int y,int xs,int ys,unsigned cddat){
    time_flag=era==0?1:era==1?0:2;
    place(x,y,xs,ys,cddat);camera();
    plpower_m=0;bossstart=0;editmode.w=0;pauseflag.w=0;swdata.w=0;memset(switchflag,0,sizeof(switchflag));
    w_reset(act,era);
    out("S act %u era %u x %d y %d xs %d ys %d c %02x\n",act,era,x,y,xs,ys,cddat);
}
static void step(void){
    frame_no++;
    w_tick();move_player();w_player();w_objects();camera();w_currents();w_visible();w_level();trace();
}

static unsigned scenarios;
int main(int argc,char **argv){
    const char *only=argc>1?argv[1]:"";
    trace_out=getenv("WATER_TRACE")!=NULL;
    /* 1. Water entry and exit across speeds, in all acts and eras. */
    if(!*only || !strcmp(only,"entry"))
    for(unsigned act=0;act<3;act++)for(unsigned era=0;era<4;era++){
        if(act==2 && era<2)continue;
        for(int ys=-5120;ys<=5120;ys+=640)for(int xs=-2048;xs<=2048;xs+=1024){
            begin(act,era,act==1?(xs<0?150:600):act==2?2100:700,0,xs,0,2);
            /* start 40 lines above/below the water, moving across it */
            int start=waterposi+(ys>=0?-40:40);
            actwk[0].yposi.w.h=(short)start;actwk[0].yspeed.w=(short)ys;camera();
            scenarios++;
            for(unsigned f=0;f<90;f++){step();if(f==45)actwk[0].yspeed.w=(short)-actwk[0].yspeed.w;}
        }
    }
    /* 1b. Fast exits from inside the water (springs, currents): the -4096 clamp. */
    if(!*only || !strcmp(only,"entry"))
    for(unsigned era=0;era<4;era++)for(int k=0;k<22;k++){
        static const int extra[4]={-2016,-2047,-2048,-2049};
        int ys=k<18?-9216+k*512:extra[k-18];
        begin(0,era,700,0,0,0,2);scenarios++;
        actwk[0].yposi.w.h=(short)(waterposi+30);camera();
        for(unsigned f=0;f<60;f++){if(f==8)actwk[0].yspeed.w=(short)ys;else if(f<8)actwk[0].yspeed.w=0;step();}
    }
    /* 1c. Act 2's x < 200 guard, at the edge. */
    if(!*only || !strcmp(only,"entry"))
    for(unsigned era=0;era<4;era++)for(int x=198;x<=201;x++){
        /* water2chk keeps the water 232 lines below the camera left of x 512 */
        cam_dy=-220;begin(1,era,x,600,0,0,2);scenarios++;
        for(unsigned f=0;f<30;f++){actwk[0].xspeed.w=0;actwk[0].yspeed.w=f<15?512:-512;cam_dy=f<15?-220:-260;step();}
        cam_dy=-96;
    }
    /* 2. Water level: sweep Sonic across each act (easing, sine, hint line). */
    if(!*only || !strcmp(only,"level"))
    for(unsigned act=0;act<3;act++)for(unsigned era=0;era<4;era++){
        if(act==2 && era<2)continue;
        static const int rows[]={200,700,1100,1300,1600,1800};
        for(unsigned r=0;r<6;r++){
            begin(act,era,64,rows[r],1024,0,0);scenarios++;
            script_move=1;
            for(unsigned f=0;f<2400;f++){actwk[0].yspeed.w=0;actwk[0].xspeed.w=f&256?1536:1024;step();}
        }
    }
    /* 3. Currents: every box of every act 1/2 table, with switch and pad states. */
    if(!*only || !strcmp(only,"currents"))
    for(unsigned act=0;act<2;act++)for(unsigned era=0;era<4;era++){
        const int16_t *t=water_coli_tables[water_coli_index[act][era]];
        for(int i=0;t[i]>=0;i+=7)for(unsigned v=0;v<6;v++){
            int x=(t[i]+t[i+2])/2,y=(t[i+1]+t[i+3])/2;
            begin(act,era,x,y,0,0,v==5?0:2);scenarios++;
            unsigned sw=(unsigned short)t[i+6]&255;
            static const unsigned char flags[6]={0,64,96,32,64,96};
            switchflag[sw]=flags[v];
            if(v==4)actwk[0].r_no0=4;
            for(unsigned f=0;f<40;f++){
                swdata.b.h=(unsigned char)((f*5+v)&15);
                if(v==5 && f==20)actwk[0].mstno.b.h=43;
                step();
            }
        }
    }
    /* 4. Air countdown to drowning and the refill hook at several levels. */
    if(!*only || !strcmp(only,"air")){
        static const int refill_at[]={-1,25,15,12,7,3,0};
        for(unsigned era=0;era<4;era++)for(unsigned r=0;r<9;r++){
            unsigned power=r<7?0:r-6,at=r<7?r:3;
            begin(0,era,900,0,0,0,0);scenarios++;
            actwk[0].yposi.w.h=(short)(waterposi+60);camera();
            int refilled=0;
            plpower_m=power==1;bossstart=power==2;
            for(unsigned f=0;f<2400;f++){
                if(f%97==0)actwk[0].cddat^=1;
                actwk[0].xspeed.w=(f/300)&1?300:-300;actwk[0].yspeed.w=0;
                if(!refilled && refill_at[at]>=0 && pl_air==refill_at[at] && f>60){w_refill();refilled=1;}
                step();
                if(actwk[0].r_no0>=6 && f>2100)break;
            }
        }
        /* leave and re-enter repeatedly: the master persists in its slot */
        for(unsigned era=0;era<4;era++){
            begin(0,era,900,0,0,0,2);scenarios++;
            for(unsigned f=0;f<1500;f++){
                int target=waterposi+((f/150)&1?-50:50);
                actwk[0].yspeed.w=(short)(actwk[0].yposi.w.h<target?600:-600);
                step();
            }
        }
    }
    fprintf(stderr,"water fixture: %u scenarios, %u frames, %lu trace lines, %lu sounds (%lu drowns), %lu bgm restores, hash %016llx\n",scenarios,frame_no,trace_lines,trace_sounds,trace_drowns,trace_bgm,(unsigned long long)trace_hash);
    return 0;
}
