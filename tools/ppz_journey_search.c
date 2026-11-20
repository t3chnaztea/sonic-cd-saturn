/* Fixed-seed Go-Explore for the natural PPZ journey routes
   (tests/routes/ppz/natural-*.pads). It links tools/ppz_journey.c, the same
   NEW GAME host model that tools/ppz_journey.py replays, and chooses only
   controller pads (bits 8 Right, 4 Left, 2 Down, 1 Up, 16 Jump); replay through
   tools/ppz_journey.py and tools/test-ppz-journey.sh is the evidence.

   usage: ppz_journey_search GOALS SEED ITERATIONS OUTPADS [PREFIXPADS]
   GOALS is the milestone order, comma separated:
     W<era>  a time warp to era 0..3 (when it is the last goal the route ends
             one update later, after the arrival, as the V0.067 routes did)
     G       a generator destroyed
     T       an Act 1/2 tally (the next act starts)
     R       the Act 3 zone results (phase 6); Act 3 must start in the Good Future
     B       the big ring touched with 50+ rings (ends the route)
   Any other warp destination, generator, tally, big ring, lost life or game
   over ends the branch. Exit 0 writes the route; exit 1 writes the best
   prefix found. Build: tools/build-ppz-journey-search.sh. */
#include "scd_player.h"
#include "scd_objects.h"
#include "world.h"
#include "act.h"
#include "scd_boss.h"
#include "EQU.H"
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int journey_init(void);
int journey_step(unsigned buttons);
const uint32_t *journey_state(void);

static char kind[16];static int target[16];static unsigned goal_count;
static unsigned milestone,dead,done,tail,count,lives0,boss_hits;
static uint8_t pads[40000];
static int time_of(unsigned era){return era==1?0:era==0?1:2;}
/* Direction of the post that leads to the next warp goal (-1 Past, +1 Future). */
static int wanted_direction(void){
    if(milestone>=goal_count || kind[milestone]!='W')return 0;
    int now=time_of(journey_state()[17]),to=time_of((unsigned)target[milestone]);
    return to<now?-1:to>now?1:0;
}
static void load(void){
    if(journey_init())exit(2);
    milestone=dead=done=tail=count=boss_hits=0;lives0=scd_player_get().lives;
}
static void step(unsigned pad){
    pads[count++]=(uint8_t)pad;
    int result=journey_step(pad);const uint32_t *s=journey_state();
    if(tail){done=1;return;}
    char want=milestone<goal_count?kind[milestone]:0;
    if(result==-2){ /* big ring touched */
        if(want=='B' && milestone+1==goal_count && (s[8]>>16)>=50){milestone++;done=1;}else dead=1;
        return;
    }
    scd_player_state p=scd_player_get();
    if(result<0 || p.resets || p.lives<lives0 || p.routine>=6){dead=1;return;}
    if(s[32]){if(want=='G'){milestone++;want=milestone<goal_count?kind[milestone]:0;}else{dead=1;return;}}
    if(s[34]){
        if(want!='T' || (s[16]==2 && s[17]!=2)){dead=1;return;}
        milestone++;want=milestone<goal_count?kind[milestone]:0;
    }
    if(s[35]!=0xffffffffu){
        if(want!='W' || (int)s[35]!=target[milestone]){dead=1;return;}
        milestone++;if(milestone==goal_count)tail=1;
        return;
    }
    /* Act 3 boss hits so far (R1 actfree[1], scd_boss_status) guide the R goal. */
    if(s[16]==2){uint32_t b=scd_boss_status();if(b && (b&255)>boss_hits)boss_hits=b&255;}
    if(want=='R' && s[16]==2 && s[25]==6)milestone++;
    if(milestone==goal_count)done=1;
}
static unsigned rng_state;
static unsigned rng(void){rng_state=rng_state*1103515245u+12345u;return (rng_state>>16)&32767;}
static void macro(void){
    static const unsigned choices[]={8,4,0,16,24,20,2,10,6,18};
    unsigned pad=choices[rng()%10],len=4+rng()%28;
    if(pad&16){
        unsigned hold=1+rng()%24;
        for(unsigned i=0;i<hold && !dead && !done && count<39000;i++)step(pad);
        pad&=~16u;len=2+rng()%6;
    }
    for(unsigned i=0;i<len && !dead && !done && count<39000;i++)step(pad);
}
static int clamp(int n,int low,int high){return n<low?low:n>high?high:n;}
static uint32_t cell_key(void){
    const uint32_t *s=journey_state();int x=(int)s[0]/65536,y=(int)s[1]/65536;
    int d=(int)s[21];unsigned armed=d<0?1:d>0?2:0;
    return (unsigned)clamp(x,0,16383)/32|((unsigned)clamp(y,0,2047)/32)<<9|milestone<<15|armed<<19|((s[8]>>16)>=50)<<21|(boss_hits<15?boss_hits:15)<<22
        |(milestone<goal_count && kind[milestone]=='B'?(s[8]>>16)/5<15?(s[8]>>16)/5:15:0)<<26;
}
static double nearest(unsigned type,int x,int y){
    double best=-1;
    for(unsigned k=1;k<97;k++)if(actwk[k].actno==type){
        double dx=actwk[k].xposi.w.h-x,dy=actwk[k].yposi.w.h-y,d=sqrt(dx*dx+dy*dy);
        if(best<0 || d<best)best=d;
    }
    return best;
}
static double cell_value(void){
    const uint32_t *s=journey_state();int x=(int)s[0]/65536,y=(int)s[1]/65536;
    double v=milestone*100000.0;char want=milestone<goal_count?kind[milestone]:0;
    if(want=='W'){
        int d=(int)s[21],w=wanted_direction();
        if(w && d==w)return v+20000+s[20]*50.0+x/8.0;
        return v+x/8.0;
    }
    if(want=='G'){double d=nearest(SCD_OBJ_GENERATOR,x,y);return d<0?v+x/8.0:v+20000-d;}
    if(want=='B'){
        unsigned rings=s[8]>>16;if(rings<50)return v+rings*200.0+x/16.0;
        double d=nearest(SCD_OBJ_BIG_RING,x,y);return d<0?v+20000+x/8.0:v+40000-d;
    }
    if(want=='R')return v+boss_hits*5000.0+x;
    return v+x;
}
typedef struct {uint32_t key;uint8_t *pads;unsigned length,visits,tried;double value;} cell;
static cell *cells;static unsigned cell_count,cell_capacity;
static void archive(void){
    if(dead)return;
    uint32_t key=cell_key();
    for(unsigned i=0;i<cell_count;i++)if(cells[i].key==key){
        if(count<cells[i].length){
            cells[i].pads=realloc(cells[i].pads,count?count:1);memcpy(cells[i].pads,pads,count);
            cells[i].length=count;cells[i].value=cell_value();
        }
        return;
    }
    if(cell_count==cell_capacity){cell_capacity=cell_capacity?cell_capacity*2:1024;cells=realloc(cells,sizeof(cell)*cell_capacity);}
    cell *c=&cells[cell_count++];c->key=key;c->length=count;c->visits=c->tried=0;c->value=cell_value();
    c->pads=malloc(count?count:1);memcpy(c->pads,pads,count);
}
static void restore(const cell *c){
    load();uint8_t copy[40000];memcpy(copy,c->pads,c->length);
    for(unsigned j=0;j<c->length && !dead && !done;j++)step(copy[j]);
}
static void write_pads(const char *name){
    FILE *f=fopen(name,"w");if(!f)exit(2);
    for(unsigned i=0;i<count;i++)fprintf(f,"%u\n",pads[i]);
    fclose(f);
}
int main(int argc,char **argv){
    if(argc<5){fprintf(stderr,"usage: ppz_journey_search GOALS SEED ITERATIONS OUTPADS [PREFIXPADS]\n");return 2;}
    for(char *g=strtok(argv[1],",");g;g=strtok(NULL,",")){
        if(goal_count==16 || !strchr("WGTRB",g[0]))return 2;
        kind[goal_count]=g[0];target[goal_count]=g[0]=='W'?g[1]-'0':-1;
        if(g[0]=='W' && (target[goal_count]<0 || target[goal_count]>3))return 2;
        goal_count++;
    }
    rng_state=(unsigned)atoi(argv[2]);unsigned iterations=(unsigned)atoi(argv[3]);
    load();
    if(argc>5){
        FILE *f=fopen(argv[5],"r");if(!f){perror(argv[5]);return 2;}
        unsigned pad;while(fscanf(f,"%u",&pad)==1 && !dead && !done){if(pad&~31u)return 2;step(pad);}
        fclose(f);
        if(dead || done){fprintf(stderr,"prefix %s\n",dead?"died":"already finished");return 2;}
    }
    archive();
    for(unsigned it=0;it<iterations;it++){
        double best=-1e30;for(unsigned i=0;i<cell_count;i++)if(cells[i].value>best)best=cells[i].value;
        double total=0;static double weight[1<<20];
        for(unsigned i=0;i<cell_count;i++){
            double w=(cells[i].value>=best-200?4.0:cells[i].value>=best-2000?1.0:0.05)/sqrt(cells[i].visits+1.0);
            weight[i]=w;total+=w;
        }
        double r=(rng()/32768.0+rng()/1073741824.0)*total;unsigned pick=0;
        for(;pick+1<cell_count && r>weight[pick];pick++)r-=weight[pick];
        cells[pick].visits++;restore(&cells[pick]);
        /* Past the sign the tally and results need no input: try a neutral finish first. */
        char want=milestone<goal_count?kind[milestone]:0;
        if(!cells[pick].tried && (tail || ((want=='T' || want=='R') && scd_act_get().goal))){
            cells[pick].tried=1;
            for(unsigned t=0;t<600 && !dead && !done && count<39000;t++)step(0);
            if(done){write_pads(argv[4]);fprintf(stderr,"search done: iterations=%u cells=%u updates=%u\n",it,cell_count,count);return 0;}
            archive();restore(&cells[pick]);
        }
        unsigned macros=4+rng()%24;
        for(unsigned m=0;m<macros && !dead && !done;m++){macro();archive();}
        if(done){write_pads(argv[4]);fprintf(stderr,"search done: iterations=%u cells=%u updates=%u\n",it,cell_count,count);return 0;}
        if(it%500==0){
            unsigned b=0;for(unsigned i=0;i<cell_count;i++)if(cells[i].value>cells[b].value)b=i;
            uint32_t k=cells[b].key;
            fprintf(stderr,"it %u cells %u best %.0f x~%u y~%u milestone %u armed %u len %u\n",it,cell_count,cells[b].value,(k&511)*32,((k>>9)&63)*32,(k>>15)&15,(k>>19)&3,cells[b].length);
        }
    }
    unsigned b=0;for(unsigned i=0;i<cell_count;i++)if(cells[i].value>cells[b].value)b=i;
    restore(&cells[b]);write_pads(argv[4]);
    fprintf(stderr,"search end: cells=%u value=%.0f milestone=%u\n",cell_count,cells[b].value,milestone);
    return 1;
}
