/* Native lifecycle/contact coverage for the linked R3/MECASNC.C scene. */
#include "EQU.H"
#include "scd_objects.h"
#include "scd_player.h"
#include "sprite_order.h"
#include "zone_object_art.h"
#include <stdio.h>
#include <stdlib.h>
static unsigned char stage_bytes[300000],collision[9472],art_bytes[150000];
static stage_t stage;
static void require(int okay,unsigned frame,const char *why){if(!okay){fprintf(stderr,"FAIL frame %u: %s\n",frame,why);exit(1);}}
static size_t read_file(const char *name,void *out,size_t cap){FILE *f=fopen(name,"rb");require(f!=NULL,0,name);size_t n=fread(out,1,cap,f);require(!ferror(f) && (n<cap || fgetc(f)==EOF),0,name);fclose(f);return n;}
int main(void){
    size_t bytes=read_file("assets/generated/cc31A.bin",stage_bytes,sizeof(stage_bytes));require(!stage_open(&stage,stage_bytes,bytes),0,"stage opens");
    bytes=read_file("assets/generated/cccollision31A.bin",collision,sizeof(collision));
    scd_player_zone(1);scd_objects_zone(1);scd_player_act(0);scd_objects_act(0);require(!scd_player_init(&stage,collision,bytes,0),0,"player initializes");scd_objects_reset(0,0);
    require(scd_objects_spawn(SCD_OBJ_EMIE3,640,1004,0,0)>=0,0,"Amy spawns");
    require(scd_objects_spawn(SCD_OBJ_HARI3X,1048,1008,2,0)>=0,0,"hazard 2 spawns");
    require(scd_objects_spawn(SCD_OBJ_HARI3X,1080,1008,3,0)>=0,0,"hazard 3 spawns");
    require(scd_objects_spawn(SCD_OBJ_HARI3X,1106,800,1,0)>=0,0,"ride hazard spawns");
    require(scd_objects_spawn(SCD_OBJ_HARI3X,1176,1008,0,0)>=0,0,"hazard 0 spawns");
    bytes=read_file("assets/generated/zone-art-31.bin",art_bytes,sizeof(art_bytes));scd_zone_art art;require(!scd_zone_art_open(&art,art_bytes,bytes,0),0,"Present art opens");
    unsigned seen_mecha=0,seen_flame=0,seen_heart=0,broken=0,debris=0,ended=0;
    for(unsigned frame=1;frame<=900;frame++){
        actwk[0].xposi.w.h=frame<180?1100:900;actwk[0].yposi.w.h=1000;actwk[0].sprhsize=8;actwk[0].sprvsize=16;actwk[0].actno=1;actwk[0].r_no0=2;
        scra_h_posit.w.h=900;scra_v_posit.w.h=896;scd_objects_step(0,0);
        scd_object_view views[96];unsigned count=scd_objects_views(views,96);
        unsigned linked=0;
        for(unsigned n=0;n<count;n++){
            scd_object_view v=views[n];require(scd_ppz_priority(v)>=0,frame,"every scene actor has priority");
            require(scd_zone_art_find(&art,v.type,v.subtype,v.frame)!=NULL,frame,"every scene pose has original art");
            if(v.type==SCD_OBJ_MECASNC3){if(v.subtype)seen_flame=1;else seen_mecha=1;}
            if(v.type==SCD_OBJ_EMIE3 && v.subtype)seen_heart=1;
            if(v.type==SCD_OBJ_HARI3X && v.frame>=1 && v.frame!=9 && v.frame!=14){debris++;if(v.frame==4 || v.frame==8 || v.frame==13)broken++;}
            if(v.type==SCD_OBJ_EMIE3 || v.type==SCD_OBJ_MECASNC3 || (v.type==SCD_OBJ_HARI3X && v.subtype!=1))linked++;
        }
        if(seen_mecha && !linked){ended=frame;break;}
    }
    require(seen_mecha,900,"Amy creates Mecha Sonic");require(seen_flame,900,"Mecha Sonic creates exhaust");require(seen_heart,900,"Amy creates hearts");
    require(broken && debris,900,"Mecha Sonic breaks hazards into debris");
    require(ended,900,"linked scene removes itself");
    printf("PASS: R3 Amy/Mecha scene completed at frame %u with hearts, exhaust and breakable debris\n",ended);
}
