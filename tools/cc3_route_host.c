/* Native-host model of a Collision Chaos Act 3 level-select run for one
   future (C or D). The per-update order and camera follow src/main.c's
   gameplay step (title lock, player step, zone33chk scroll limits, world
   step, camera). Only pad input changes the run: no placement, position or
   velocity writes.

   cc3_route_host replay SCRIPT C|D LIMIT OUTPUT [TRACE]
       Replays SCRIPT ("COUNT PAD" lines; PAD bits 128 Right, 64 Left,
       32 Down, 16 Up, 1 Jump; neutral after the script) and writes the
       ``sequence pad x y`` rows tools/test_cc3_route.py compares on Saturn.
   cc3_route_host search C|D SEED ROUNDS OUTSCRIPT [PREFIX]
       Greedy rollout search for a pad script from entry through the boss,
       capsule and tally. Each round forks candidate processes that play
       random pad macros from the current state; the best continues. The
       search only chooses pad input; the replay mode is the evidence. */
#include "scd_player.h"
#include "camera_v.h"
#include "scd_objects.h"
#include "scd_boss.h"
#include "act.h"
#include "world.h"
#include "title_card.h"
#include "EQU.H"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

extern short scralim_left,scralim_right,scralim_down,scra_vline;
static unsigned char data[400000],collision[9472],raw[10240];
static scd_placement placements[1024];
static unsigned pads[40000],pad_count;
static stage_t stage;
static int camera_x,camera_y;
static unsigned buttons,delayed,sequence,max_hits,dead,done,spawned,boss_music,music_hits,first_hit_music;
/* Parity only (tools/retail_parity.py): CC_ROUTE_UNLOCK_AT=N holds controls
   until retail's unlock update N; CC_ROUTE_TRACE prints "unlock N" and makes
   replay write tools/tt_route_search.c's parity rows. */
static unsigned unlock_sequence;static long unlock_at=-2;static int parity_trace;
static size_t read_file(const char *name,void *buffer,size_t capacity){
    FILE *f=fopen(name,"rb");if(!f){perror(name);exit(2);}
    size_t n=fread(buffer,1,capacity,f);
    if(ferror(f) || fgetc(f)!=EOF){fprintf(stderr,"Invalid input: %s\n",name);exit(2);}
    fclose(f);return n;
}
static void load(unsigned era){
    char path[128];
    snprintf(path,sizeof(path),"assets/generated/cc33%c.bin","ABCD"[era]);
    size_t bytes=read_file(path,data,sizeof(data));if(stage_open(&stage,data,bytes))exit(2);
    snprintf(path,sizeof(path),"assets/generated/cccollision33%c.bin","ABCD"[era]);
    if(read_file(path,collision,sizeof(collision))!=9472)exit(2);
    bytes=read_file("assets/generated/ccobj33.bin",raw,sizeof(raw));
    if(bytes%10)exit(2);
    for(unsigned i=0;i<bytes/10;i++){
        placements[i].x=(int16_t)(raw[i*10]*256+raw[i*10+1]);
        placements[i].y=(int16_t)(raw[i*10+2]*256+raw[i*10+3]);
        memcpy(&placements[i].type,raw+i*10+4,5);
    }
    scd_player_zone(1);scd_player_act(2);scd_objects_zone(1);scd_objects_act(2);
    scd_objects_layout(placements,bytes/10);
    if(scd_player_init(&stage,collision,sizeof(collision),era))exit(2);scd_player_objects_lead();
    scd_world_zone(1);scd_world_act(2);scd_world_reset(era);scd_title_card_start(2);
    camera_y=scd_camera_v_begin(1,2,era,scd_player_get().y/65536,scd_player_get().resets);camera_x=scd_camera_h();
    scd_act_camera(camera_x,camera_y);scd_boss_camera(camera_x,camera_y);
    scd_player_hold_clock(1);scd_player_step(0);scd_title_card_step();
    sequence=1;unlock_sequence=0;
    if(unlock_at==-2){const char *v=getenv("CC_ROUTE_UNLOCK_AT");unlock_at=v?atol(v):-1;parity_trace=getenv("CC_ROUTE_TRACE")!=NULL;}
}
/* One src/main.c gameplay update; WANT is the pad requested this update. */
static void step(unsigned want){
    sequence++;
    scd_act_camera(camera_x,camera_y);scd_boss_camera(camera_x,camera_y);
    int locked=scd_title_card_locked()||(unlock_at>=0 && (long)sequence<unlock_at);scd_player_hold_clock(locked);
    if(!locked && !unlock_sequence){unlock_sequence=sequence;if(parity_trace)fprintf(stderr,"unlock %u\n",sequence);}
    scd_objects_travel_protection(scd_world_get().ticks>0);
    scd_player_step(locked?0:delayed);
    scd_title_card_step();
    /* src/main.c consumes the boss music request each update; BOSS_3.C
       jaba_s_chk asks for the boss track (sub_sync 103). Count only hits
       landed while that track is the latest request. */
    int music=scd_boss_music();
    if(music==SCD_BOSS_MUSIC_BOSS)boss_music=1;else if(music==SCD_BOSS_MUSIC_ZONE && boss_music==1)boss_music=2;
    /* SCRCHK.C zone33chk, as src/main.c applies it after bossflag. */
    if(bossflag){
        const short target=96;int x=(uint16_t)(scd_player_get().x/65536-160);
        if(abs(target-scralim_down)<4)scralim_down=target;
        if(scralim_left<=(short)x){scralim_left=scralim_right<(short)x?scralim_right:x;}
        if(scralim_down>target){if(target<(uint16_t)camera_y)scralim_down=camera_y&~1;scralim_down-=4;}
        else if(scralim_down<target)scralim_down+=4;
    }
    scd_player_state p=scd_player_get();int x=p.x/65536,y=p.y/65536;
    if(scd_objects_generator())scd_world_generator_destroyed();
    if(scd_world_step(p)>=0)dead=2;
    int post=scd_objects_timepost();if(post)scd_world_activate(post);
    if(p.resets || p.routine>=6)dead=1;
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
    uint32_t status=scd_boss_status();
    if(status)spawned=1;
    if(status && (status&255)>max_hits){max_hits=status&255;if(max_hits==1)first_hit_music=boss_music==1;if(first_hit_music)music_hits=max_hits;}
    if(result.phase==SCD_ACT_DONE)done=music_hits==3?1:0,dead=music_hits==3?dead:3;
    /* Libretro's pad request is sampled two observations later. */
    delayed=buttons;
    buttons=(want&128?SCD_RIGHT:0)|(want&64?SCD_LEFT:0)|(want&32?SCD_DOWN:0)|(want&16?SCD_UP:0)|(want&1?SCD_JUMP:0);
}
static const sprite_status *egg3dai_l(void){
    for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++)if(actwk[i].actno==49)return &actwk[i];
    return NULL;
}
static unsigned rng_state;
static unsigned rng(void){rng_state=rng_state*1103515245u+12345u;return (rng_state>>16)&32767;}
static void macro(void){
    static const unsigned choices[]={128,64,0,1,129,65,32,160,96,33};
    unsigned pad=choices[rng()%10],len=4+rng()%28;
    if(pad&1){ /* a held jump followed by a release, so the next jump registers */
        unsigned hold=1+rng()%24;
        for(unsigned i=0;i<hold && !dead && !done;i++){pads[pad_count++]=pad;step(pad);}
        pad&=~1u;len=2+rng()%6;
    }
    for(unsigned i=0;i<len && !dead && !done;i++){pads[pad_count++]=pad;step(pad);}
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
    FILE *f=strcmp(name,"-")?fopen(name,"r"):stdin;if(!f){perror(name);exit(2);}
    unsigned n,pad;
    while(fscanf(f,"%u %u",&n,&pad)==2){
        if(pad&~0xf1u)exit(2);
        while(n-- && pad_count<limit)pads[pad_count++]=pad;
    }
    if(f!=stdin)fclose(f);
}
/* Go-Explore over pad prefixes: an archive of coarse cells (position,
   boss phase, hits, gates, bossflag), each keeping the shortest prefix that
   reached it. Restoring a cell replays its prefix from a fresh load; the
   native host runs far faster than real time, so no state snapshots. */
typedef struct {uint32_t key;uint8_t *pads;unsigned length,visits;double value;} cell;
static cell *cells;static unsigned cell_count,cell_capacity;
static uint32_t cell_key(void){
    scd_player_state p=scd_player_get();int x=p.x/65536,y=p.y/65536;
    const sprite_status *b=egg3dai_l();
    unsigned phase=!spawned?0:!b?7:b->r_no0/2;
    unsigned gates=b && b->r_no0>=4?b->actfree[16]:0;
    unsigned lift=0;for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++)if(actwk[i].actno==48 && actwk[i].r_no0>=4)lift=1;
    return (uint32_t)((x/24)&127)|((uint32_t)((y/24)&127)<<7)|(phase<<14)|((music_hits&3)<<17)|((gates&7)<<19)|((uint32_t)(bossflag==3 && music_hits==3)<<22)|((uint32_t)(scd_act_get().goal && music_hits==3)<<23)|((uint32_t)(boss_music!=0)<<24)|((uint32_t)(lift || boss_music)<<25);
}
static double cell_value(uint32_t key){
    double v=((key>>17)&3)*8+((key>>19)&7)*2+((key>>22)&1)*8+((key>>23)&1)*8+(((key>>14)&7)>=2?2:0)+((key>>24)&1)*4+((key>>25)&1)*2;
    /* After bossflag, step toward the capsule at X 1336. */
    if((key>>22)&1){unsigned cx=key&127;v+=cx>39?(cx>55?4:(cx-39)/4.0):0;}
    return v;
}
static void archive(void){
    if(dead)return;
    uint32_t key=cell_key();
    for(unsigned i=0;i<cell_count;i++)if(cells[i].key==key){
        if(pad_count<cells[i].length){
            cells[i].pads=realloc(cells[i].pads,pad_count?pad_count:1);
            for(unsigned j=0;j<pad_count;j++)cells[i].pads[j]=(uint8_t)pads[j];
            cells[i].length=pad_count;
        }
        return;
    }
    if(cell_count==cell_capacity){cell_capacity=cell_capacity?cell_capacity*2:1024;cells=realloc(cells,sizeof(cell)*cell_capacity);}
    cell *c=&cells[cell_count++];c->key=key;c->length=pad_count;c->visits=0;c->value=cell_value(key);
    c->pads=malloc(pad_count?pad_count:1);for(unsigned j=0;j<pad_count;j++)c->pads[j]=(uint8_t)pads[j];
}
static void restore(const cell *c,unsigned era){
    pad_count=0;dead=done=max_hits=spawned=boss_music=music_hits=first_hit_music=0;load(era);
    for(unsigned j=0;j<c->length;j++){pads[pad_count++]=c->pads[j];step(c->pads[j]);}
}
static int search(unsigned era,unsigned seed,unsigned iterations,const char *out,const char *prefix){
    rng_state=seed;
    load(era);
    if(prefix){read_script(prefix,40000);for(unsigned i=0;i<pad_count;i++)step(pads[i]);}
    archive();
    double top=0;
    for(unsigned it=0;it<iterations;it++){
        /* Choose among the highest-value cells, preferring rarely chosen ones. */
        double best_value=0;for(unsigned i=0;i<cell_count;i++)if(cells[i].value>best_value)best_value=cells[i].value;
        double total=0;static double weight[1<<20];
        for(unsigned i=0;i<cell_count;i++){
            double w=(cells[i].value>=best_value-2?4.0:cells[i].value>=best_value-6?1.0:0.1)/sqrt(cells[i].visits+1.0);
            weight[i]=w;total+=w;
        }
        double r=(rng()/32768.0+rng()/1073741824.0)*total;unsigned pick=0;
        for(;pick+1<cell_count && r>weight[pick];pick++)r-=weight[pick];
        cells[pick].visits++;
        restore(&cells[pick],era);
        unsigned macros=4+rng()%24;
        for(unsigned m=0;m<macros && !dead && !done;m++){macro();archive();}
        if(done){write_script(out);fprintf(stderr,"search done: iterations=%u cells=%u sequence=%u\n",it,cell_count,sequence);return 0;}
        if(best_value>top || it%2000==0){
            top=best_value;
            unsigned bestc=0;for(unsigned i=0;i<cell_count;i++)if(cells[i].value>cells[bestc].value)bestc=i;
            uint32_t k=cells[bestc].key;
            fprintf(stderr,"it %u cells %u best value %.0f at x~%u y~%u phase %u hits %u gates %u flag %u len %u\n",it,cell_count,cells[bestc].value,(k&127)*24,((k>>7)&127)*24,(k>>14)&7,(k>>17)&3,(k>>19)&7,(k>>22)&1,cells[bestc].length);
        }
    }
    unsigned bestc=0;for(unsigned i=0;i<cell_count;i++)if(cells[i].value>cells[bestc].value || (cells[i].value==cells[bestc].value && cells[i].length>cells[bestc].length))bestc=i;
    restore(&cells[bestc],era);write_script(out);
    fprintf(stderr,"search end: cells=%u value=%.0f sequence=%u hits=%u bossflag=%u\n",cell_count,cells[bestc].value,sequence,max_hits,bossflag);
    return 1;
}
int main(int argc,char **argv){
    if(argc>=6 && !strcmp(argv[1],"search")){
        unsigned era=(unsigned)(argv[2][0]-'A');if(era<2 || era>3)return 2;
        return search(era,(unsigned)atoi(argv[3]),(unsigned)atoi(argv[4]),argv[5],argc>6?argv[6]:NULL);
    }
    if(argc<6 || argc>7 || strcmp(argv[1],"replay") || (argv[3][0]!='C' && argv[3][0]!='D'))
        {fprintf(stderr,"usage: cc3_route_host replay SCRIPT C|D LIMIT OUTPUT [TRACE] | search C|D SEED ROUNDS OUTSCRIPT [PREFIX]\n");return 2;}
    unsigned era=(unsigned)(argv[3][0]-'A'),limit=(unsigned)atoi(argv[4]);
    if(limit<10 || limit>40000)return 2;
    read_script(argv[2],limit);
    load(era);
    FILE *out=fopen(argv[5],"w");if(!out){perror(argv[5]);return 2;}
    FILE *trace=argc>6?fopen(argv[6],"w"):NULL;
    for(unsigned i=0;i<limit;i++){
        unsigned want=i<pad_count?pads[i]:0;
        step(want);
        scd_player_state p=scd_player_get();int x=p.x/65536,y=p.y/65536;
        if(dead){fprintf(stderr,"Route %s at %u x=%d y=%d\n",dead==1?"died":"warped",sequence,x,y);fclose(out);return 3;}
        /* Diagnostic: CC_ROUTE_OBJECTS=FIRST:LAST:FILE, as tools/cc_campaign_search.c. */
        {static FILE *od;static long of=-2,ol;if(of==-2){const char *v=getenv("CC_ROUTE_OBJECTS");of=-1;
            if(v && strchr(v,':') && strchr(strchr(v,':')+1,':')){of=atol(v);ol=atol(strchr(v,':')+1);od=fopen(strchr(strchr(v,':')+1,':')+1,"w");}}
         if(od && (long)sequence>=of && (long)sequence<=ol){
            fprintf(od,"%u camera %d %d\n",sequence,scd_act_view_x(),scd_act_view_y());
            for(unsigned k=0;k<128;k++){const sprite_status *o=&actwk[k];if(!o->actno)continue;
                fprintf(od,"%u %u %u %u %u %d %u %d %u %d %u\n",sequence,k,o->actno,(unsigned)(uint8_t)o->userflag.b.h,o->r_no0,o->xposi.w.h,(unsigned)(uint16_t)o->xposi.w.l,
                        o->yposi.w.h,(unsigned)(uint16_t)o->yposi.w.l,o->xspeed.w,o->actflg);}
            fflush(od);}}
        if(parity_trace){const sprite_status *s=&actwk[0];
            fprintf(out,"%u %u %d %d 0 0 %d %u %d %d %u %u %u\n",sequence,want,s->xposi.w.h,s->yposi.w.h,s->yspeed.w,s->cddat,
                    s->mspeed.w,s->xspeed.w,(unsigned)(uint16_t)s->xposi.w.l,(unsigned)(uint16_t)s->yposi.w.l,(unsigned)s->direc.b.h);}
        else fprintf(out,"%u %u %d %d\n",sequence,want,x,y);
        if(trace){const sprite_status *b=egg3dai_l();
            fprintf(trace,"%u %u %d %d %u %d %d %u %u %08x %u %u %u %u %u %u %u %u\n",sequence,want,x,y,p.flags,p.vx,p.vy,p.rings,
                    bossflag,scd_boss_status(),b?b->actfree[16]:9,scd_act_get().phase,scd_objects_standing_type(),boss_music,music_hits,p.score,p.angle,p.path);}
        if(done){
            fclose(out);if(trace)fclose(trace);
            fprintf(stderr,"Tally complete: sequence=%u era=%u score=%u rings=%u boss_hits=%u music_hits=%u\n",sequence,era,p.score,p.rings,max_hits,music_hits);
            return 0;
        }
    }
    fclose(out);if(trace)fclose(trace);
    scd_player_state p=scd_player_get();
    fprintf(stderr,"Route incomplete: limit=%u x=%d y=%d hits=%u bossflag=%u\n",limit,p.x/65536,p.y/65536,max_hits,bossflag);
    return 1;
}
