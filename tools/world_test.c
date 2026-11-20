#include "world_qa.h"
#include "camera_v.h"
#include "world.h"
#include "act.h"
#include "EQU.H"
#include "ETC.H"
#include "scd_objects.h"
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include "objects.inc"
/* Palmtree Panic streams through the retail Object Spawner, which follows the
   camera window; these host loops move only the player, so keep the camera on him. */
static void follow(void){scd_player_state p=scd_player_get();int x=p.x/65536-160,y=p.y/65536-112;scd_act_camera(x<0?0:x,y<0?0:y);}
static uint8_t data[4][300000],collision[4][9472];
int main(void){
    const uint8_t *packs[4],*collisions[4];size_t sizes[4];
    for(unsigned era=0;era<4;era++){
        char path[100];snprintf(path,sizeof(path),"assets/generated/ppz%u.bin",era);FILE *f=fopen(path,"rb");if(!f)return 2;
        sizes[era]=fread(data[era],1,sizeof(data[era]),f);fclose(f);packs[era]=data[era];
        snprintf(path,sizeof(path),"assets/generated/collision%u.bin",era);f=fopen(path,"rb");if(!f || fread(collision[era],1,9472,f)!=9472)return 2;fclose(f);collisions[era]=collision[era];
    }
    int result=scd_world_probe(packs,sizes,collisions);
    printf("World QA probe: %s (%d)\n",result?"FAIL":"PASS",result);if(result)return 1;
    /* Reproduce controller fixture's four neutral ticks before holding Right.
       Landing artwork surrounds a passage; verify movement can leave it. */
    stage_t stages[4];for(unsigned era=0;era<4;era++)if(stage_open(&stages[era],packs[era],sizes[era]))return 2;
    if(scd_player_init(&stages[1],collisions[1],9472,1))return 2;
    scd_objects_reset(1,0);scd_player_place(3040,768,1536,0,0);follow();
    scd_world_reset(1);scd_world_activate(1);
    int destination=-1;unsigned departure_ticks=0;
    for(unsigned tick=0;tick<1000 && destination<0;tick++){
        scd_player_step(tick<4?0:SCD_RIGHT);follow();
        destination=scd_world_step(scd_player_get());departure_ticks=tick+1;
    }
    printf("Arrival route: departure %u ticks, destination %d\n",departure_ticks,destination);
    if(destination!=0 || scd_player_arrive(&stages[0],collisions[0],9472,0) || !scd_player_arrival_clear())return 1;
    int arrival_x=scd_player_get().x/65536,arrival_y=scd_player_get().y/65536;
    unsigned jumped=0;
    for(unsigned tick=0;tick<240;tick++){
        scd_player_step(tick<30?SCD_RIGHT:tick<60?(SCD_LEFT|SCD_JUMP):SCD_LEFT);follow();
        scd_player_state p=scd_player_get();if(p.resets || p.routine>=4)return 1;
        if(p.y/65536<arrival_y-24)jumped=1;
    }
    if(!jumped || scd_player_get().x/65536>=arrival_x)return 1;
    printf("Arrival movement: PASS (clear landing, jump and departure, 240 ticks)\n");
    if(scd_player_init(&stages[0],collisions[0],9472,0))return 2;
    unsigned ramp_ticks=0,launches=0,exits=0;int old_ramp=0;follow();
    for(unsigned tick=0;tick<900;tick++){
        scd_player_step(SCD_RIGHT);follow();scd_player_state p=scd_player_get();
        ramp_ticks+=p.ramp;if(p.vy==-3072)launches++;
        if(old_ramp && !p.ramp && p.vx>0 && p.vy<-2048)exits++;old_ramp=p.ramp;
        if(p.resets || p.routine>=4)return 1;
    }
    if(!ramp_ticks || !launches || exits!=1 || scd_player_get().x/65536<2400)return 1;
    printf("Ramp route: ticks=%u launches=%u exits=%u resets=%u\n",ramp_ticks,launches,exits,scd_player_get().resets);
    for(unsigned route=0;route<4;route++){
        unsigned era=route==0?1:route==1?0:route==2?3:0;int x=route==1?4187:1456,y=route==1?96:450;
        if(scd_player_init(&stages[era],collisions[era],9472,era))return 2;
        scd_player_place(x,y,0,0,2);follow();scd_player_inventory(5,1);follow();
        unsigned rides=0;
        for(unsigned n=0;n<180;n++){
            scd_player_step(0);follow();scd_player_state p=scd_player_get();rides+=!!scd_objects_standing_type();
            if(p.resets || p.routine>=4)return 1;
        }
        if(rides<100)return 1;
        if(route==2){
            scd_object_view views[96];unsigned count=scd_objects_views(views,96);
            for(unsigned j=0;j<count;j++)if(views[j].type==SCD_OBJ_FLOAT_BLOCK && views[j].x==1456 && views[j].y==524)return 1;
            scd_player_place(2300,96,0,0,2);follow();scd_objects_step(2300,96);
            scd_player_place(1456,450,0,0,2);follow();scd_objects_step(1456,450);
            count=scd_objects_views(views,96);unsigned reloaded=0;
            for(unsigned j=0;j<count;j++)if(views[j].type==SCD_OBJ_FLOAT_BLOCK && views[j].x==1456 && views[j].y==524)reloaded++;
            if(reloaded!=1)return 1;
        }
        if(route!=2){scd_player_step(SCD_JUMP|SCD_RIGHT);follow();if(scd_objects_standing_type() || scd_player_get().vy>=0)return 1;}
        printf("Original placement route %u: PASS (%u rider ticks, safe landing%s)\n",route,rides,route==2?"":" and jump-off");
    }
    /* A clock longer than five minutes must cap the checkpoint without
       rewinding the independent simulation frame on travel or death. */
    if(scd_player_init(&stages[0],collisions[0],9472,0))return 2;
    scd_objects_reset(0,0);
    /* Hold Up for two updates every 6000: three minutes in the waiting pose
       would make Sonic give up (PLAYER.C bye_chk). The first Up update only
       arms scr_cnt (PLAYER.C:687-690); the second shows the look-up pose,
       which resets the count. */
    for(unsigned n=0;n<18060;n++)scd_player_step(n%6000>=5998?SCD_UP:0);follow();
    if(scd_player_get().elapsed!=18060 || !scd_player_checkpoint_activate(2) || scd_player_checkpoint().elapsed!=18000)return 1;
    if(scd_player_arrive(&stages[1],collisions[1],9472,1) || scd_player_get().elapsed!=18000 || scd_player_get().frame!=18060)return 1;
    printf("Checkpoint clock: PASS (five-minute cap, simulation frame continuous)\n");
    /* Drive every original checkpoint with source placement streaming. */
    const int checkpoint_xy[3][2]={{2760,744},{5200,153},{8680,616}};
    for(unsigned k=0;k<3;k++){
        if(scd_player_init(&stages[0],collisions[0],9472,0))return 2;
        int x=checkpoint_xy[k][0],y=checkpoint_xy[k][1];
        scd_player_place(x,y,0,0,2);follow();scd_objects_step(x,y);
        if(scd_player_checkpoint().id!=k+2)return 1;
        scd_objects_respawn();scd_player_place(x,y-80,0,0,2);follow();scd_objects_step(x,y-80);
        scd_object_view views[96];unsigned n=scd_objects_views(views,96),active=0;
        for(unsigned j=0;j<n;j++)if(views[j].type==SCD_OBJ_CHECKPOINT && views[j].subtype==k+2 && views[j].frame>=2)active++;
        if(active!=1)return 1;
    }
    printf("Original checkpoints: PASS (all three activate and reload active)\n");
    /* Every source wall record, including both future variants. */
    const int walls[][4]={{1,3584,488,5},{1,3616,488,6},{1,3648,488,7},{2,8592,936,4},{2,8728,936,1},{2,8760,936,3},{3,8592,936,4},{3,8728,936,1},{3,8760,936,3},{0,8672,696,1},{0,8704,696,3}};
    for(unsigned k=0;k<sizeof(walls)/sizeof(*walls);k++){
        unsigned era=walls[k][0];int x=walls[k][1],y=walls[k][2];
        if(scd_player_init(&stages[era],collisions[era],9472,era))return 2;
        scd_player_place(x,y,0,0,6);follow();actwk[0].mstno.b.h=2;actwk[0].xspeed.w=1536;
        scd_objects_step(x,y);if(!scd_objects_get().broken)return 1;
        scd_player_place(x,y-120,0,0,2);follow();
        for(unsigned n=0;n<120;n++)scd_objects_step(x,y-120);
        scd_object_view v[96];unsigned count=scd_objects_views(v,96);
        for(unsigned n=0;n<count;n++)if(v[n].type==SCD_OBJ_WALL && v[n].x==x && v[n].frame<8)return 1;
        scd_player_place(x+800,y,0,0,2);follow();scd_objects_step(x+800,y);
        scd_player_place(x,y-120,0,0,2);follow();scd_objects_step(x,y-120);
        count=scd_objects_views(v,96);unsigned restored=0;
        for(unsigned n=0;n<count;n++)if(v[n].type==SCD_OBJ_WALL && v[n].x==x && v[n].y==y && v[n].frame==walls[k][3])restored++;
        /* Breakable Wall/Main.asm leaves the saved-flags spawned bit set, so the
           streamed record never loads again (objects.c wall break, retail PPZ2B). */
        if(restored)return 1;
    }
    printf("Original walls: PASS (all records/eras break, stay absent nearby and after return)\n");
    for(unsigned route=0;route<2;route++){
        unsigned era=route?0:1;int x=route?8590:3550,y=route?660:489;
        if(scd_player_init(&stages[era],collisions[era],9472,era))return 2;
        scd_player_place(x,y,0,0,2);follow();scd_player_inventory(5,1);follow();
        for(unsigned n=0;n<600;n++){
            unsigned buttons=n<150?SCD_RIGHT:n<210?SCD_DOWN|(n<154?SCD_JUMP:0):SCD_RIGHT;
            scd_player_step(buttons);follow();
            scd_player_state p=scd_player_get();
            if(p.resets || p.routine>=4){fprintf(stderr,"Wall route %u frame %u x=%d y=%d routine=%u resets=%u broken=%u\n",route,n,p.x/65536,p.y/65536,p.routine,p.resets,scd_objects_get().broken);return 1;}
            if(n==149 && (scd_objects_get().broken || p.x/65536!=(route?8646:3558)))return 1;
            if(n==599 && (scd_objects_get().broken!=(route?2:3) || p.x/65536<=(route?8730:3674)))return 1;
        }
        printf("Wall controller host %u: PASS (ordinary side stop, charge/roll, original barrier crossed)\n",route);
    }
    for(unsigned era=0;era<4;era++){
        if(scd_player_init(&stages[era],collisions[era],9472,era))return 2;
        scd_player_place(9800,era?710:450,1536,0,0);follow();scd_player_inventory(23,1);
        int camera_y=scd_camera_v_begin(0,0,era,scd_player_get().y/65536,scd_player_get().resets),camera_x=scd_camera_h();unsigned stop_time=0,phase=0;
        for(unsigned n=0;n<1400 && scd_act_get().phase!=SCD_ACT_DONE;n++){
            scd_act_camera(camera_x,camera_y);scd_player_step(SCD_RIGHT);follow();
            scd_player_state p=scd_player_get();scd_act_state a=scd_act_get();
            if(p.routine>=4 || p.resets){fprintf(stderr,"Finish route era=%u tick=%u failed routine=%u x=%d y=%d\n",era,n,p.routine,p.x/65536,p.y/65536);return 1;}
            if(a.phase && !phase)stop_time=p.elapsed;
            if(a.phase && p.elapsed!=stop_time)return 1;
            if(a.phase!=phase){printf("Finish era=%u tick=%u phase=%u x=%d y=%d score=%u bonus=%u/%u\n",era,n,a.phase,p.x/65536,p.y/65536,p.score,a.time_bonus,a.ring_bonus);phase=a.phase;}
            if(!a.phase){camera_y=scd_camera_v_follow(p.y/65536,p.resets);camera_x=scd_camera_h();if(camera_x>10391)camera_x=10391;}
        }
        if(scd_act_get().phase!=SCD_ACT_DONE || scd_player_get().score!=52300 || scd_player_get().lives!=4 || scd_act_get().good_future!=(era==2))return 1;
        printf("Original finish route era %u: PASS (clock freeze, source phases, 52300 points, extra life)\n",era);
    }
    unsigned monitor_records=0;
    for(unsigned era=0;era<4;era++)for(unsigned n=0;n<sizeof(placements)/sizeof(*placements);n++){
        const scd_placement *m=&placements[n];unsigned bit=era==0?2:era==1?1:4;
        if(m->type!=SCD_OBJ_TIMEPOST || m->subtype>=8 || !(m->eras&bit))continue;
        if(scd_player_init(&stages[era],collisions[era],9472,era))return 2;
        scd_objects_travel_protection(1);
        scd_object_view v[96];unsigned count=0,shell=0;
        /* An original enemy may occupy the same contact rectangle and bounce
           Sonic before the monitor (e.g. Past Anton at 4490,712). Retry the
           isolated downward contact after that enemy has been defeated. */
        for(unsigned attempt=0;attempt<4 && !shell;attempt++){
            scd_player_place(m->x,m->y-20,0,0,6);follow();actwk[0].mstno.b.h=2;actwk[0].yspeed.w=256;
            scd_objects_step(m->x,m->y-24);count=scd_objects_views(v,96);
            for(unsigned j=0;j<count;j++)if(v[j].type==25 && v[j].x==m->x && v[j].y==m->y && v[j].frame==11)shell++;
        }
        if(shell!=1){fprintf(stderr,"Original monitor did not break era=%u x=%d y=%d subtype=%u\n",era,m->x,m->y,m->subtype);return 1;}
        scd_player_place(m->x+800,m->y,0,0,2);follow();scd_objects_step(m->x+800,m->y);
        scd_player_place(m->x,m->y-120,0,0,2);follow();scd_objects_step(m->x,m->y-120);
        count=scd_objects_views(v,96);shell=0;
        for(unsigned j=0;j<count;j++)if(v[j].type==25 && v[j].x==m->x && v[j].y==m->y && v[j].frame==11)shell++;
        if(shell!=1){fprintf(stderr,"Monitor shell reload mismatch era=%u x=%d y=%d shell=%u count=%u\n",era,m->x,m->y,shell,count);return 1;}
        scd_objects_respawn();scd_objects_step(m->x,m->y-120);count=scd_objects_views(v,96);unsigned intact=0;
        for(unsigned j=0;j<count;j++)if(v[j].type==25 && v[j].x==m->x && v[j].y==m->y && v[j].frame!=11)intact++;
        if(intact!=1){fprintf(stderr,"Monitor life reset mismatch era=%u x=%d y=%d intact=%u count=%u\n",era,m->x,m->y,intact,count);return 1;}monitor_records++;
    }
    printf("Original monitors: PASS (%u era/placement instances break, reload shells, restore after life loss)\n",monitor_records);
    unsigned collapse_records=0;
    for(unsigned era=0;era<4;era++)for(unsigned n=0;n<sizeof(placements)/sizeof(*placements);n++){
        const scd_placement *m=&placements[n];unsigned bit=era==0?2:era==1?1:4;
        if(m->type!=SCD_OBJ_COLLAPSE || !(m->eras&bit))continue;
        if(scd_player_init(&stages[era],collisions[era],9472,era))return 2;
        scd_objects_travel_protection(1);scd_player_place(m->x,m->y-140,0,0,2);follow();scd_objects_step(m->x,m->y-140);
        unsigned actor=0;for(unsigned i=1;i<=96;i++)if(actwk[i].actno==32 && actwk[i].xposi.w.h==m->x && actwk[i].yposi.w.h==m->y){actor=i;break;}
        if(!actor){fprintf(stderr,"Collapse missing era=%u x=%d y=%d\n",era,m->x,m->y);return 1;}
        int top=m->y-actwk[actor].sprvsize-19;
        unsigned before=scd_objects_get().collapsed;
        scd_player_place(m->x,top,0,0,2);follow();scd_objects_step(m->x,top);
        if(scd_objects_get().collapsed!=before+1){fprintf(stderr,"Collapse contact failed era=%u x=%d y=%d top=%d player=%d flags=%u\n",era,m->x,m->y,top,actwk[0].yposi.w.h,actwk[0].cddat);return 1;}
        scd_player_place(m->x,m->y-140,0,0,2);follow();
        for(unsigned tick=0;tick<250;tick++)scd_objects_step(m->x,m->y-140);
        scd_object_view v[96];unsigned count=scd_objects_views(v,96);
        for(unsigned j=0;j<count;j++)if(v[j].type==32 && v[j].x==m->x && v[j].y==m->y){fprintf(stderr,"Collapse reloaded while nearby\n");return 1;}
        scd_player_place(m->x+800,m->y-140,0,0,2);follow();scd_objects_step(m->x+800,m->y-140);
        scd_player_place(m->x,m->y-140,0,0,2);follow();scd_objects_step(m->x,m->y-140);count=scd_objects_views(v,96);unsigned restored=0;
        for(unsigned j=0;j<count;j++)if(v[j].type==32 && v[j].x==m->x && v[j].y==m->y)restored++;
        /* Collapsing Platform/Main.asm: a saved record stays marked spawned and
           never loads again (objects.c, as the Breakable Wall). */
        if(restored){fprintf(stderr,"Collapse reloaded after return era=%u x=%d y=%d count=%u\n",era,m->x,m->y,restored);return 1;}
        scd_objects_respawn();scd_objects_step(m->x,m->y-140);count=scd_objects_views(v,96);restored=0;
        for(unsigned j=0;j<count;j++)if(v[j].type==32 && v[j].x==m->x && v[j].y==m->y)restored++;
        if(restored!=1)return 1;
        collapse_records++;
    }
    if(collapse_records!=21)return 1;
    printf("Original collapsing platforms: PASS (%u era/placement contacts, delayed deletion, leave/return and life-reset reload)\n",collapse_records);
    unsigned tunnel_records=0;
    for(unsigned era=0;era<4;era++)for(unsigned n=0;n<sizeof(placements)/sizeof(*placements);n++){
        const scd_placement *m=&placements[n];if(m->type!=SCD_OBJ_TUNNEL || !(m->eras&(1u<<(era==0?1:era==1?0:2))))continue;
        if(scd_player_init(&stages[era],collisions[era],9472,era))return 2;
        scd_player_place(m->x,m->y,0,0,2);follow();scd_objects_step(m->x,m->y);
        if(scd_player_get().control!=(m->secondary?193:129))return 1;
        unsigned ticks=0;while(scd_player_get().control && ticks<1000){scd_player_step(0);follow();ticks++;}
        scd_player_state p=scd_player_get();
        printf("Original tunnel era=%u path=%u ticks=%u exit=%d,%d control=%u\n",era,m->subtype,ticks,p.x/65536,p.y/65536,p.control);
        if(ticks!=(m->subtype?125:177) || p.x/65536!=(m->subtype?4400:5888) || p.y/65536!=(m->subtype?456:752) || p.resets || p.routine!=2)return 1;
        if(!m->subtype){
            scd_object_view v[96];unsigned count=scd_objects_views(v,96),revealed=0;
            for(unsigned j=0;j<count;j++)revealed+=v[j].type==SCD_OBJ_SONIC_HOLE;
            if(revealed!=1)return 1;
            /* Source bit-6 reveal state persists through unloading and era
               return; our existing life reset clears all saved object flags. */
            scd_player_place(7000,100,0,0,2);follow();scd_objects_step(7000,100);
            scd_player_place(5872,100,0,0,2);follow();scd_objects_step(5872,100);
            count=scd_objects_views(v,96);revealed=0;
            for(unsigned j=0;j<count;j++)revealed+=v[j].type==SCD_OBJ_SONIC_HOLE;
            if(revealed!=1)return 1;
            scd_objects_change_era(era^1);scd_objects_change_era(era);scd_objects_step(5872,100);
            count=scd_objects_views(v,96);revealed=0;
            for(unsigned j=0;j<count;j++)revealed+=v[j].type==SCD_OBJ_SONIC_HOLE;
            if(revealed!=1)return 1;
            scd_objects_respawn();scd_objects_step(5872,100);count=scd_objects_views(v,96);
            for(unsigned j=0;j<count;j++)if(v[j].type==SCD_OBJ_SONIC_HOLE)return 1;
        }
        tunnel_records++;
    }
    if(tunnel_records!=4)return 1;
    printf("Original tunnels: PASS (four era/placement routes, both visibility modes, hole reveal/unload/era-return/life-reset)\n");
    unsigned disc_records=0;
    for(unsigned era=0;era<4;era++)for(unsigned n=0;n<sizeof(placements)/sizeof(*placements);n++){
        const scd_placement *m=&placements[n];if(m->type!=SCD_OBJ_DISC || !(m->eras&(1u<<(era==0?1:era==1?0:2))))continue;
        if(scd_player_init(&stages[era],collisions[era],9472,era))return 2;
        scd_player_place(m->x+8,m->y-27,0,0,2);follow();swdata.w=0;scd_objects_step(m->x+8,m->y-27);
        if(scd_player_get().control!=1){fprintf(stderr,"Disc capture failed era=%u at=%d,%d flags=%u routine=%u standing=%u\n",era,m->x,m->y,scd_player_get().flags,scd_player_get().routine,scd_objects_standing_type());return 1;}
        for(unsigned tick=0;tick<32;tick++){
            scd_player_step(0);follow();
            if(scd_player_get().control!=1 || scd_player_get().animation!=45 || scd_player_get().disc_frame>=6){fprintf(stderr,"Disc rotation failed era=%u x=%d tick=%u\n",era,m->x,tick);return 1;}
        }
        scd_player_step(SCD_JUMP);follow();
        if(scd_player_get().control || scd_player_get().vy!=-1664 || scd_player_get().animation!=2)return 1;
        scd_player_step(SCD_JUMP);follow();if(scd_objects_standing_type())return 1;
        disc_records++;
    }
    if(disc_records!=17)return 1;
    printf("Original spinning discs: PASS (%u era/placement instances, rotation and jump release with nearby objects loaded)\n",disc_records);
    unsigned flap_records=0,vertical_records=0,wheel_records=0;
    for(unsigned era=0;era<4;era++)for(unsigned n=0;n<sizeof(placements)/sizeof(*placements);n++){
        const scd_placement *m=&placements[n];
        if(!(m->eras&(1u<<(era==0?1:era==1?0:2))) || (m->type!=SCD_OBJ_DOOR && m->type!=SCD_OBJ_DOOR_V && m->type!=SCD_OBJ_MOVING_SPRING))continue;
        if(scd_player_init(&stages[era],collisions[era],9472,era))return 2;
        swdata.w=0;
        if(m->type==SCD_OBJ_DOOR){
            scd_player_place(m->x,m->y,0,0,2);follow();actwk[0].yspeed.w=-256;scd_objects_step(m->x,m->y);
            if(scd_objects_get().doors_opened!=1){fprintf(stderr,"Original flap failed era=%u at=%d,%d\n",era,m->x,m->y);return 1;}
            scd_player_place(m->x,m->y-100,0,0,2);follow();
            for(unsigned tick=1;tick<=12;tick++){
                scd_objects_step(m->x,m->y-100);scd_object_view v[96];unsigned count=scd_objects_views(v,96),found=0;
                for(unsigned j=0;j<count;j++)if(v[j].type==m->type && v[j].x==m->x && v[j].y==m->y){found++;if(v[j].frame!=(tick>=3 && tick<=11))return 1;}
                if(found!=1)return 1;
            }
            flap_records++;
        }else if(m->type==SCD_OBJ_DOOR_V){
            scd_player_place(m->x-40,m->y,0,0,2);follow();scd_objects_step(m->x-40,m->y);
            if(scd_objects_get().doors_opened!=1)return 1;
            scd_player_place(m->x+30,m->y,0,0,2);follow();
            for(unsigned tick=1;tick<=32;tick++){
                scd_objects_step(m->x+30,m->y);scd_object_view v[96];unsigned count=scd_objects_views(v,96),found=0;
                for(unsigned j=0;j<count;j++)if(v[j].type==m->type && v[j].x==m->x && v[j].y==m->y){found++;if(v[j].frame!=(tick<32))return 1;}
                if(found!=1)return 1;
            }
            vertical_records++;
        }else{
            scd_player_place(m->x,100,0,0,2);follow();scd_objects_step(m->x,100);
            unsigned actor=0;
            for(unsigned j=1;j<=96;j++)if(actwk[j].actno==SCD_OBJ_MOVING_SPRING && actwk[j].xposi.w.h==m->x)actor=j;
            if(!actor)return 1;
            int low=m->x,high=m->x;
            for(unsigned tick=0;tick<600;tick++){
                scd_objects_step(m->x,100);
                if(actwk[actor].xposi.w.h<low)low=actwk[actor].xposi.w.h;
                if(actwk[actor].xposi.w.h>high)high=actwk[actor].xposi.w.h;
                if(actwk[actor].actno!=SCD_OBJ_MOVING_SPRING || !scd_objects_get().attached)return 1;
            }
            printf("Moving spring era=%u home=%d,%d range=%d..%d final=%d,%d reversals=%u\n",era,m->x,m->y,low,high,actwk[actor].xposi.w.h,actwk[actor].yposi.w.h,scd_objects_get().wheel_reversals);
            if(low>=m->x || high<=m->x || !scd_objects_get().wheel_reversals)return 1;
            /* Force the current carrier far from home: streaming follows the
               source home coordinate and must remove attached actors too. */
            actwk[actor].xposi.w.h=m->x+2000;
            scd_player_place(m->x+2000,100,0,0,2);follow();scd_objects_step(m->x+2000,100);
            for(unsigned j=1;j<=96;j++)if(actwk[j].actno==SCD_OBJ_MOVING_SPRING)return 1;
            if(scd_objects_get().attached)return 1;
            scd_player_place(m->x,100,0,0,2);follow();scd_objects_step(m->x,100);
            if(!scd_objects_get().attached)return 1;
            scd_objects_respawn();if(scd_objects_get().attached)return 1;
            wheel_records++;
        }
    }
    if(flap_records!=11 || vertical_records!=3 || wheel_records!=4)return 1;
    printf("Original doors and moving springs: PASS (%u flaps, %u vertical doors, %u moving springs; timing, paths and attached cleanup)\n",flap_records,vertical_records,wheel_records);
    unsigned tag_records=0,scenery_records=0,shadow_records=0;
    for(unsigned era=0;era<4;era++)for(unsigned n=0;n<sizeof(placements)/sizeof(*placements);n++){
        const scd_placement *m=&placements[n];
        if(!(m->eras&(1u<<(era==0?1:era==1?0:2))) || (m->type!=SCD_OBJ_SPIN_TAG && m->type!=SCD_OBJ_SCENERY && m->type!=SCD_OBJ_LOG_SHADOW))continue;
        if(scd_player_init(&stages[era],collisions[era],9472,era))return 2;
        scd_player_place(m->x,m->y,0,0,2);follow();swdata.w=0;debugflag.w=0;scd_objects_step(m->x,m->y);
        if(m->type==SCD_OBJ_SPIN_TAG){
            if(!scd_objects_get().tag_contacts || !(scd_player_get().flags&4) || (m->subtype?actwk[0].yspeed.w!=3328:actwk[0].xspeed.w!=2560)){
                fprintf(stderr,"Original tag failed era=%u at=%d,%d flags=%u vx=%d vy=%d contacts=%u\n",era,m->x,m->y,scd_player_get().flags,actwk[0].xspeed.w,actwk[0].yspeed.w,scd_objects_get().tag_contacts);return 1;
            }
            tag_records++;
        }else{
            scd_object_view v[96];unsigned count=scd_objects_views(v,96),found=0;
            for(unsigned j=0;j<count;j++)if(v[j].type==m->type && v[j].x==m->x && v[j].y==m->y){found++;if(v[j].frame!=m->subtype || v[j].flags!=m->flags)return 1;}
            if(found!=1)return 1;
            scd_player_place(m->x+800,100,0,0,2);follow();scd_objects_step(m->x+800,100);
            count=scd_objects_views(v,96);
            for(unsigned j=0;j<count;j++)if(v[j].type==m->type && v[j].x==m->x && v[j].y==m->y)return 1;
            scd_player_place(m->x,100,0,0,2);follow();scd_objects_step(m->x,100);
            count=scd_objects_views(v,96);found=0;
            for(unsigned j=0;j<count;j++)if(v[j].type==m->type && v[j].x==m->x && v[j].y==m->y)found++;
            if(found!=1)return 1;
            if(m->type==SCD_OBJ_SCENERY)scenery_records++;else shadow_records++;
        }
    }
    if(tag_records!=9 || scenery_records!=11 || shadow_records!=12)return 1;
    printf("Original tags and scenery: PASS (%u speed tags, %u scenery, %u log shadows; actual era placements and reload)\n",tag_records,scenery_records,shadow_records);
    /* All original animal placements, before and after projector completion. */
    unsigned animal_cases=0;
    for(unsigned era=0;era<4;era++)for(unsigned released=0;released<2;released++){
        if(scd_player_init(&stages[era],collisions[era],9472,era))return 2;
        if(released){
            scd_player_place(500,100,0,0,2);follow();scd_objects_spawn(SCD_OBJ_PROJECTOR,500,400,0,0);scd_objects_step(500,100);
            scd_player_place(500,374,0,0,6);follow();actwk[0].mstno.b.h=2;scd_objects_step(500,374);
            scd_player_place(500,100,0,0,2);follow();for(unsigned t=0;t<101;t++)scd_objects_step(500,100);
            if(!scd_objects_projector_destroyed())return 1;
        }
        unsigned count=0,bit=era==0?2:era==1?1:4;
        for(unsigned j=0;j<sizeof(placements)/sizeof(*placements);j++){
            const scd_placement *e=&placements[j];if(e->type!=SCD_OBJ_ANIMAL || !(e->eras&bit))continue;
            /* A fresh load at this spot (the spawner re-initialises on the camera). */
            scd_objects_respawn();scd_player_place(e->x,64,0,0,2);follow();scd_objects_step(e->x,64);
            unsigned actor=0;for(unsigned i=1;i<=96;i++)if(actwk[i].actno==SCD_OBJ_ANIMAL && actwk[i].xposi.w.h==e->x && actwk[i].yposi.w.h==e->y && (uint8_t)actwk[i].userflag.b.h==e->subtype){actor=i;break;}
            if((era!=3)!=!!actor)return 1;
            if(actor){
                scd_objects_step(e->x,64);unsigned enabled=era==2 || released;
                scd_object_view v[96];unsigned n=scd_objects_views(v,96),visible=0;
                for(unsigned i=0;i<n;i++)if(v[i].type==SCD_OBJ_ANIMAL && v[i].subtype==e->subtype && v[i].x==actwk[actor].xposi.w.h && v[i].y==actwk[actor].yposi.w.h)visible++;
                if(!!visible!=enabled)return 1;
                if(!enabled && (actwk[actor].xposi.w.h!=e->x || actwk[actor].yposi.w.h!=e->y))return 1;
            }
            count++;animal_cases++;
        }
        if(count!=(era==0?13:era==1?26:25))return 1;
    }
    printf("Original animals: PASS (%u era/presence cases; dormant, released, Good Future and suppressed Bad Future)\n",animal_cases);
    /* Original projector with normal placement streaming: controller jump and
       completion, then unload/re-entry. */
    if(scd_player_init(&stages[1],collisions[1],9472,1))return 2;
    scd_player_place(5776,740,0,0,0);follow();
    for(unsigned tick=0;tick<300;tick++){
        unsigned buttons=0;
        if(tick>=40 && tick<65)buttons|=SCD_JUMP;
        scd_player_step(buttons);follow();
        if(scd_player_get().routine>=4 || scd_player_get().resets)return 1;
    }
    if(!scd_objects_projector_destroyed())return 1;
    scd_objects_respawn();scd_player_place(5776,650,0,0,2);follow();scd_objects_step(5776,650);
    for(unsigned i=1;i<=96;i++)if(actwk[i].actno==SCD_OBJ_PROJECTOR)return 1;
    printf("Original projector: PASS (controller jump, 12 explosions, persistent release and respawn suppression)\n");
    if(scd_player_init(&stages[1],collisions[1],9472,1))return 2;
    scd_player_place(5776,650,0,0,2);follow();scd_objects_step(5776,650);if(scd_objects_get().holograms!=4)return 1;
    scd_player_place(7000,64,0,0,2);follow();scd_objects_step(7000,64);if(scd_objects_get().holograms)return 1;
    for(unsigned i=1;i<=96;i++)if(actwk[i].actno==SCD_OBJ_PROJECTOR)return 1;
    scd_player_place(5776,650,0,0,2);follow();scd_objects_step(5776,650);if(scd_objects_get().holograms!=4)return 1;
    scd_player_place(5776,760,0,0,6);follow();actwk[0].mstno.b.h=2;scd_objects_step(5776,760);if(scd_objects_get().projector_hits!=1)return 1;
    scd_player_place(7000,64,0,0,2);follow();
    for(unsigned tick=1;tick<=101;tick++){
        scd_objects_step(7000,64);if(scd_objects_projector_destroyed()!=(tick==101))return 1;
    }
    if(scd_objects_get().projector_explosions!=12 || scd_objects_get().holograms)return 1;
    printf("Original projector streaming: PASS (child cleanup, re-entry and completion beyond unloading range)\n");

    /* Animation uses the original six-tick cursor through object-age wrap. */
    scd_objects_reset(0,0);scd_player_place(80,100,0,0,2);follow();swdata.w=0;scd_objects_spawn(SCD_OBJ_DISC,500,400,0,0);
    for(unsigned tick=0;tick<65542;tick++){
        scd_objects_step(80,100);
        if(tick>=65530){scd_object_view v[1];if(scd_objects_views(v,1)!=1 || v[0].frame!=(tick/2)%3)return 1;}
    }
    printf("Disc animation: PASS (source six-tick period through 16-bit age wrap)\n");
    if(scd_player_init(&stages[0],collisions[0],9472,0))return 2;
    scd_objects_reset(0,0);scd_objects_spawn(SCD_OBJ_AMY,9664,488,0,0);scd_player_place(9646,522,0,0,1);follow();
    unsigned hold_ticks=0,amy_jumped=0;
    for(unsigned tick=0;tick<800;tick++){
        scd_player_step(tick>=620 && tick<645?SCD_JUMP:0);follow();
        scd_player_state p=scd_player_get();if(p.routine>=4 || p.resets)return 1;
        if(p.control&1)hold_ticks++;
        if(tick>=620 && !p.control && p.vy<0)amy_jumped=1;
        if(tick<5 || tick==619 || tick==620)printf("Amy controller host: tick=%u x=%d y=%d control=%u pose=%d amy=%d,%d routine=%u grabs=%u\n",tick,p.x/65536,p.y/65536,p.control,scd_objects_amy_idle_frame(),actwk[1].xposi.w.h,actwk[1].yposi.w.h,actwk[1].r_no0,scd_objects_get().amy_grabs);
    }
    if(hold_ticks<600 || !amy_jumped || !scd_objects_get().amy_grabs)return 1;
    printf("Amy controller host: PASS (hold=%u, fresh jump release, idle and hearts)\n",hold_ticks);

    /* Batch ring allocation must still select the same lowest free slots,
       including holes, exhausted pools, both velocity tiers and the 32 cap. */
    static const unsigned ring_counts[]={1,2,15,16,31,32,40};
    unsigned ring_cases=0;
    for(unsigned occupied=0;occupied<=SCD_OBJECT_CAPACITY;occupied++)
    for(unsigned fragmented=0;fragmented<2;fragmented++)
    for(unsigned trial=0;trial<sizeof(ring_counts)/sizeof(*ring_counts);trial++){
        assert(!scd_player_init(&stages[1],collisions[1],9472,1));
        scd_objects_reset(1,0);scd_player_place(80,488,0,0,2);follow();
        for(unsigned i=0;i<occupied;i++)assert(scd_objects_spawn(SCD_OBJ_RING,
            fragmented && i%3==0?80:1000,488,0,0)==(int)i);
        if(fragmented)scd_objects_step(80,488); /* Collect interleaved slots. */
        unsigned empty[96],free_count=0;
        for(unsigned i=0;i<96;i++)if(!actwk[i+1].actno)empty[free_count++]=i;
        unsigned rings=ring_counts[trial],expected=rings<32?rings:32;
        if(expected>free_count)expected=free_count;
        scd_player_inventory(rings,0);
        scd_object_stats before=scd_objects_get();scd_objects_hurt(100);
        scd_object_stats after=scd_objects_get();
        assert(after.lost==expected && after.active==before.active+expected);
        assert(after.spawned==before.spawned+expected && after.hits==before.hits+1);
        assert(after.dropped==before.dropped+(free_count<(rings<32?rings:32)));
        assert(!scd_player_get().rings);
        for(unsigned n=0;n<expected;n++){
            sprite_status *r=actwk+empty[n]+1;short sn,cs;
            sinset(136+(n/2%8)*16,&sn,&cs);int scale=n<16?4:2;
            assert(r->actno==SCD_OBJ_LOST_RING && r->xposi.l==80*65536 && r->yposi.l==488*65536);
            assert(r->xspeed.w==sn*scale*(n&1?-1:1) && r->yspeed.w==cs*scale);
            assert(r->sprhsize==8 && r->sprvsize==8 && r->actflg==132);
        }
        ring_cases++;
    }
    printf("Ring scatter allocation: PASS (%u dense/fragmented/full-pool cases; original slots, counts and velocities)\n",ring_cases);
    return 0;
}
