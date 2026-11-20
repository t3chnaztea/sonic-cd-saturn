/* R3 projector children must survive their first update and keep their parent. */
#include "EQU.H"
#include "scd_objects.h"
#include "scd_player.h"
#include "zone_object_art.h"
#include <stdio.h>
#include <stdlib.h>

static unsigned char stage_bytes[300000],collision[9472],art_bytes[120000];
static stage_t stage;
static size_t read_file(const char *path,void *out,size_t capacity){
    FILE *f=fopen(path,"rb");if(!f){perror(path);exit(1);}
    size_t n=fread(out,1,capacity,f);if(ferror(f) || (n==capacity && fgetc(f)!=EOF)){perror(path);exit(1);}
    fclose(f);return n;
}
static void require(int condition,const char *message){if(!condition){fprintf(stderr,"FAIL %s\n",message);exit(1);}}
int main(void){
    for(unsigned act=1;act<=2;act++){
        char path[128];snprintf(path,sizeof(path),"assets/generated/cc3%uB.bin",act);
        size_t bytes=read_file(path,stage_bytes,sizeof(stage_bytes));
        require(!stage_open(&stage,stage_bytes,bytes),"stage opens");
        snprintf(path,sizeof(path),"assets/generated/cccollision3%uB.bin",act);
        bytes=read_file(path,collision,sizeof(collision));
        scd_player_zone(1);scd_objects_zone(1);
        scd_player_act(act-1);scd_objects_act(act-1);
        require(!scd_player_init(&stage,collision,bytes,1),"player initializes");
        scd_objects_reset(1,0);
        int x=act==1?7112:5431,y=act==1?500:1172;
        require(scd_objects_spawn(SCD_OBJ_MOVIE3,x,y,0,0)==0,"projector spawns");
        snprintf(path,sizeof(path),"assets/generated/zone-art-3%u.bin",act);
        bytes=read_file(path,art_bytes,sizeof(art_bytes));
        scd_zone_art art;require(!scd_zone_art_open(&art,art_bytes,bytes,1),"Past art opens");
        for(unsigned tick=1;tick<=3;tick++){
            scd_objects_step(0,0);
            scd_object_stats stats=scd_objects_get();
            require(stats.active==5 && stats.holograms==4,"four children remain attached");
            scd_object_view views[8];unsigned count=scd_objects_views(views,8);
            require(count==(tick==1?3u:5u),"original first-update child draw timing");
            static const int dx[]={0,-21,-88,-88,-98};
            static const int dy[]={0,-7,-4,-24,0};
            if(tick==1)for(unsigned i=0;i<5;i++)
                require(actwk[i+1].xposi.w.h==x+dx[i] && actwk[i+1].yposi.w.h==y+dy[i],
                        "all four original R3 child spawn offsets");
            for(unsigned i=0;i<count;i++){
                if(i<3 || tick==1)require(views[i].x==x+dx[i] && views[i].y==y+dy[i],"original R3 child offsets");
                require(views[i].type==(i<3?SCD_OBJ_MOVIE3:SCD_OBJ_FRIEND3),"original R3 child types");
                require(scd_zone_art_find(&art,views[i].type,views[i].subtype,views[i].frame)!=NULL,"every visible pose has original art");
            }
        }
        printf("CC%u Past projector: four source-positioned children and art remain live\n",act);
    }
}
