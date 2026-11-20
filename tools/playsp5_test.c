/* Quartz Quadrant conveyor belts: the compiled R5/PLAYSP5.C belt (renamed
   orig_* by tools/test-playsp5.sh) against src/player.c scd_playsp5 on every
   real Quartz Quadrant map and era. Sonic stands at every 8-pixel position
   of the map with both hitbox sizes, both collision paths, colrevflag on and
   off; each era must find belt blocks, and every result byte must match. */
#include "EQU.H"
#include "scd_player.h"
#include "scd_objects.h"
#include "act.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
void scd_playsp5(void);void orig_belt(void);
static unsigned char data[400000],collision[9472];static stage_t stage;
static unsigned long checks,moved,pushed_back;
/* scddisasm Level/Collision Floor.asm GetLevelBlock .Blank (retail R51C
   $200EFC): a blank layout chunk leaves A1 at LevelChunks, chunk 1's first
   block word, for PLAYSP5's direct read. Inside the map only, like scramapad. */
extern unsigned char mapwka[8][64];short scramapad(sprite_status*,short,short);
short orig_level_block(sprite_status *a,short x,short y){
    int cx=x<0?0:x,cy=y<0?0:y;
    if(cx<16384 && cy<2048 && !mapwka[cy>>8][cx>>8])return (short)((stage.part[2][0]<<8)|stage.part[2][1]);
    return scramapad(a,x,y);
}
static size_t read_file(const char *name,unsigned char *buf,size_t cap){
    FILE *f=fopen(name,"rb");if(!f){fprintf(stderr,"FAIL missing %s\n",name);exit(1);}
    size_t n=fread(buf,1,cap,f);fclose(f);return n;
}
int main(void){
    static const char *const maps[]={"51A","51B","51C","51D","52A","52B","52C","52D","53C","53D"};
    for(unsigned m=0;m<10;m++){
        unsigned act=maps[m][1]-'1',era=maps[m][2]-'A';
        char path[96];static PALETTEENTRY palette[256];lpcolorwk=palette;
        snprintf(path,sizeof(path),"assets/generated/qq%s.bin",maps[m]);
        size_t n=read_file(path,data,sizeof(data));if(stage_open(&stage,data,n)){fprintf(stderr,"FAIL open %s\n",path);return 1;}
        snprintf(path,sizeof(path),"assets/generated/qqcollision%s.bin",maps[m]);
        if(read_file(path,collision,sizeof(collision))!=sizeof(collision)){fprintf(stderr,"FAIL collision %s\n",path);return 1;}
        scd_player_zone(3);scd_objects_zone(3);scd_player_act(act);scd_objects_act(act);
        if(scd_player_init(&stage,collision,sizeof(collision),era)){fprintf(stderr,"FAIL init %s\n",maps[m]);return 1;}
        unsigned long era_moved=0;
        for(unsigned boss=0;boss<2;boss++)for(unsigned mode=0;mode<8;mode++)
        for(int y=0;y<2048;y+=boss?64:8)for(int x=0;x<16384;x+=boss?64:8){
            sprite_status p=actwk[0];
            p.xposi.l=x*65536+0x1234;p.yposi.l=y*65536;
            if(mode&1){p.sprvsize=14;p.sprhs=7;}else{p.sprvsize=19;p.sprhs=9;}
            p.actflg=(p.actflg&~64)|(mode&2?64:0);colrevflag=mode&4?1:0;bossflag=boss;
            actwk[0]=p;orig_belt();sprite_status expected=actwk[0];
            actwk[0]=p;scd_playsp5();checks++;
            if(memcmp(&actwk[0],&expected,sizeof(p))){
                fprintf(stderr,"FAIL %s x %d y %d mode %u boss %u native %d original %d\n",maps[m],x,y,mode,boss,actwk[0].xposi.l,expected.xposi.l);return 1;
            }
            if(expected.xposi.l!=p.xposi.l){moved++;era_moved++;if((expected.xposi.l-p.xposi.l>0)!=((mode&4)==0))pushed_back++;}
        }
        if(!era_moved){fprintf(stderr,"FAIL %s: no belt contact found\n",maps[m]);return 1;}
        bossflag=0;colrevflag=0;
    }
    if(!pushed_back){fprintf(stderr,"FAIL no wall push-back case\n");return 1;}
    printf("PASS: playsp5 belts %lu positions; %lu belt pushes; %lu wall corrections; 10 maps\n",checks,moved,pushed_back);
    return 0;
}
