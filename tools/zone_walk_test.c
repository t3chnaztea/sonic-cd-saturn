/* Walk Sonic right through an imported zone's act on the host.
 * Proves the stage pack, collision and scroll limits agree: Sonic keeps ground
 * contact, makes forward progress and never falls out of the map.
 * With a LAYOUT (an object layout from tools/object_layouts.py) the zone's
 * objects spawn too; without one it is terrain and collision only. */
#include "player_replay.h"
#include "scd_objects.h"
#include "scd_player.h"
#include "act.h"
#include "world.h"
#include "title_card.h"
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
extern short scralim_left,scralim_right,scralim_down,scra_vline;
static uint8_t data[300000],collision[9472],layout_bytes[SCD_PLACEMENT_CAPACITY*10];
static scd_placement layout[SCD_PLACEMENT_CAPACITY];
static size_t slurp(const char *path,uint8_t *out,size_t cap){
    FILE *f=fopen(path,"rb"); if(!f){fprintf(stderr,"missing %s\n",path);exit(2);}
    size_t n=fread(out,1,cap,f); fclose(f); return n;
}
int main(int argc,char **argv){
    if(argc<5 || argc>7){fprintf(stderr,"usage: zone_walk_test STAGE COLLISION ZONE ERA [ACT [LAYOUT]]\n");return 2;}
    unsigned zone=(unsigned)strtoul(argv[3],NULL,10),era=(unsigned)strtoul(argv[4],NULL,10);
    unsigned act=argc==6?(unsigned)strtoul(argv[5],NULL,10):0;
    /* Layout files are big-endian ten-byte records, the Saturn's own layout of
       scd_placement; unpack them field by field for the host. */
    unsigned layout_count=0;
    if(argc==7){
        size_t n=slurp(argv[6],layout_bytes,sizeof layout_bytes);
        if(n%10){fprintf(stderr,"layout size %zu is not a whole number of records\n",n);return 2;}
        for(layout_count=0;layout_count<n/10;layout_count++){
            const uint8_t *r=layout_bytes+layout_count*10;
            layout[layout_count]=(scd_placement){(int16_t)(r[0]<<8|r[1]),(int16_t)(r[2]<<8|r[3]),r[4],r[5],r[6],r[7],r[8]};
        }
    }
    size_t size=slurp(argv[1],data,sizeof data);
    if(slurp(argv[2],collision,sizeof collision)!=sizeof collision){fprintf(stderr,"collision size\n");return 2;}
    stage_t stage;
    if(stage_open(&stage,data,size)){fprintf(stderr,"stage_open rejected %s\n",argv[1]);return 1;}
    scd_player_zone(zone);scd_objects_zone(zone);
    scd_player_act(act);scd_objects_act(act);scd_world_act(act);
    /* scd_player_init resets the objects, so the layout goes in first. */
    if(layout_count)scd_objects_layout(layout,layout_count);
    if(scd_player_init(&stage,collision,sizeof collision,era)){fprintf(stderr,"player init\n");return 1;}
    scd_world_reset(era);
    scd_title_card_start(act);
    scd_player_state p=scd_player_get();
    printf("spawn (%d,%d)  scroll limits left=%d right=%d down=%d\n",
           p.x/65536,p.y/65536,scralim_left,scralim_right,scralim_down);
    int max_x=p.x/65536,min_y=p.y/65536,max_y=p.y/65536,airborne=0,deaths=0;
    unsigned updates=0,stuck=0,jumps=0,hold=0;int last_x=max_x;
    for(;updates<20000;updates++){
        /* Plain Right stalls at the first wall in any Sonic level, so jump when
           progress stops. The jump is variable height: a one-update tap reaches
           about 33 of its 100 pixels, but a full jump also overshoots ledges a
           short hop lands on. So successive stalls cycle the hold through 1, 20
           and 10 updates rather than betting on one. */
        unsigned buttons=SCD_RIGHT;
        static const unsigned holds[]={1,20,10};
        if(stuck>=30 && !(p.flags&2)){hold=holds[jumps%3];jumps++;stuck=0;}
        if(hold){buttons|=SCD_JUMP;hold--;}
        scd_player_hold_clock(scd_title_card_locked());
        scd_player_step(scd_title_card_locked()?0:buttons);
        scd_title_card_step();
        p=scd_player_get();
        int x=p.x/65536,y=p.y/65536;
        if(x>last_x+1){stuck=0;last_x=x;}else stuck++;
        if(x>max_x)max_x=x;
        if(y<min_y)min_y=y; if(y>max_y)max_y=y;
        if(p.flags&2)airborne++;
        if(p.resets>(unsigned)deaths)deaths=(int)p.resets;
        if(x>=scralim_right)break;
    }
    p=scd_player_get();
    printf("after %u updates: x=%d y=%d  max_x=%d  y range %d..%d  airborne %u%%  jumps %u  deaths %d\n",
           updates,p.x/65536,p.y/65536,max_x,min_y,max_y,updates?airborne*100u/updates:0,jumps,deaths);
    if(layout_count){
        scd_object_stats o=scd_objects_get();
        printf("objects: layout %u  spawned %u  springs %u  rings collected %u  unsupported %u\n",
               layout_count,o.spawned,o.springs,o.collected,o.unsupported);
    }
    if(max_y>2040){printf("FAIL: fell out of the map\n");return 1;}
    if(max_x < 1000){printf("FAIL: no forward progress\n");return 1;}
    printf("PASS: terrain and collision carried Sonic to x=%d\n",max_x);
    return 0;
}
