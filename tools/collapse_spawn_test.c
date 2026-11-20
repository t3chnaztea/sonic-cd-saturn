/* Collapsing-platform break: slot-equivalence fixture for the batched spawner
   in src/objects.c. Built twice by tools/test-collapse-spawn.sh: once with
   SCD_COLLAPSE_FULL_SCAN (the from-slot-0 scans and the full spawn_from chain)
   and once with the resumed scans plus SCD_OBJECTS_VERIFY asserts. Every PPZ
   Act 1 and Act 2 collapse placement in every era is broken over a pool that
   earlier streaming and extra ring spawns left fragmented; each case prints the
   slot indices of the new pieces and a hash of every actor and view. The two
   builds must print identical lines. */
#include "act.h"
#include "EQU.H"
#include "scd_objects.h"
#include "scd_player.h"
#include "stage.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "objects.inc"
#include "objects2.inc"

static unsigned char data[400000],collision[9472];
static uint32_t fnv(uint32_t h,const void *p,size_t n){const uint8_t *b=p;while(n--)h=(h^*b++)*16777619u;return h;}
static uint32_t state_hash(void){
    uint32_t h=2166136261u;
    h=fnv(h,actwk,sizeof(sprite_status)*97);
    scd_object_view v[SCD_OBJECT_CAPACITY];unsigned n=scd_objects_views(v,SCD_OBJECT_CAPACITY);
    h=fnv(h,&n,sizeof n);h=fnv(h,v,sizeof(*v)*n);
    return h;
}
static int load(const char *stage_path,const char *collision_path,stage_t *stage,unsigned era){
    FILE *f=fopen(stage_path,"rb");if(!f)return -1;size_t n=fread(data,1,sizeof(data),f);fclose(f);
    f=fopen(collision_path,"rb");if(!f || fread(collision,1,sizeof(collision),f)!=sizeof(collision))return -1;fclose(f);
    if(stage_open(stage,data,n))return -1;
    return scd_player_init(stage,collision,sizeof(collision),era);
}
int main(void){
    unsigned cases=0,pieces=0;
    for(unsigned act=0;act<2;act++)for(unsigned era=0;era<4;era++){
        char sp[80],cp[80],op[80];
        if(act){snprintf(sp,80,"assets/generated/ppz12%c.bin",'A'+era);snprintf(cp,80,"assets/generated/collision12%c.bin",'A'+era);}
        else{snprintf(sp,80,"assets/generated/ppz%u.bin",era);snprintf(cp,80,"assets/generated/collision%u.bin",era);}
        snprintf(op,80,"assets/generated/objects12%c.bin",'A'+era);
        /* Collapse positions: Act 1 from the generated placements (era bits),
           Act 2 from placements_act2 (objects2.inc). */
        int xs[256],ys[256];unsigned count=0;
        if(!act){unsigned bit=era==0?2:era==1?1:4;
            for(unsigned n=0;n<sizeof(placements)/sizeof(*placements) && count<256;n++)
                if(placements[n].type==SCD_OBJ_COLLAPSE && (placements[n].eras&bit)){xs[count]=placements[n].x;ys[count++]=placements[n].y;}}
        else{unsigned bit=era==0?2:era==1?1:4;(void)op;
            for(unsigned n=0;n<sizeof(placements_act2)/sizeof(*placements_act2) && count<256;n++)
                if(placements_act2[n].type==SCD_OBJ_COLLAPSE && (placements_act2[n].eras&bit)){xs[count]=placements_act2[n].x;ys[count++]=placements_act2[n].y;}}
        for(unsigned k=0;k<count;k++){
            stage_t stage;scd_player_act(act);scd_objects_act(act);
            if(load(sp,cp,&stage,era))return 2;
            scd_objects_travel_protection(1);
            int x=xs[k],y=ys[k];
            /* Stream in and out around the platform to leave holes in the pool,
               then add a case-dependent number of rings near it. */
            /* PPZ streams through the retail Object Spawner: the camera window
               (centred on the player here) loads and frames out placements. */
            for(int dx=-2400;dx<=0;dx+=400){scd_player_place(x+dx,y-140,0,0,2);scd_act_camera(x+dx-160,y-252);scd_objects_step(x+dx,y-140);}
            scd_player_place(x+700,y-140,0,0,2);scd_act_camera(x+540,y-252);scd_objects_step(x+700,y-140);
            scd_player_place(x,y-140,0,0,2);scd_act_camera(x-160,y-252);scd_objects_step(x,y-140);
            for(unsigned j=0;j<(k*7+era*3)%29;j++)scd_objects_spawn(SCD_OBJ_RING,x-300+(int)((j*37)%600),y-260,0,0);
            scd_objects_step(x,y-140);
            unsigned actor=0;for(unsigned i=1;i<=SCD_OBJECT_CAPACITY;i++)if(actwk[i].actno==SCD_OBJ_COLLAPSE && actwk[i].xposi.w.h==x && actwk[i].yposi.w.h==y){actor=i;break;}
            if(!actor)continue;
            int top=y-actwk[actor].sprvsize-19;
            uint8_t before[SCD_OBJECT_CAPACITY];for(unsigned i=0;i<SCD_OBJECT_CAPACITY;i++)before[i]=actwk[i+1].actno;
            unsigned collapsed=scd_objects_get().collapsed;
            scd_player_place(x,top,0,0,2);scd_objects_step(x,top);
            if(scd_objects_get().collapsed!=collapsed+1)continue;
            char slots[512];int w=0;slots[0]=0;unsigned made=0;
            for(unsigned i=0;i<SCD_OBJECT_CAPACITY;i++)if(actwk[i+1].actno==SCD_OBJ_COLLAPSE && before[i]!=SCD_OBJ_COLLAPSE){w+=snprintf(slots+w,sizeof(slots)-w,"%u,",i);made++;}
            uint32_t h1=state_hash();
            for(unsigned t=0;t<40;t++)scd_objects_step(x,top);
            printf("case act=%u era=%u x=%d y=%d pieces=%u slots=%s hash=%08x after=%08x\n",act+1,era,x,y,made,slots,h1,state_hash());
            cases++;pieces+=made;
        }
    }
    printf("collapse breaks: %u cases, %u pieces\n",cases,pieces);
    return cases?0:1;
}
