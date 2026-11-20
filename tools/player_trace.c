#include "player_replay.h"
#include "camera_v.h"
#include "act.h"
#include <stdio.h>
#include <stdlib.h>
static unsigned char *read_file(const char *name,size_t *size) {
    FILE *f=fopen(name,"rb");if(!f){perror(name);exit(2);}
    fseek(f,0,SEEK_END);*size=ftell(f);rewind(f);
    unsigned char *data=malloc(*size);if(!data || fread(data,1,*size,f)!=*size)exit(2);
    fclose(f);return data;
}
int main(void) {
    const char *visual_path=getenv("SCD_PLAYER_VISUAL_TRACE_FILE");
    FILE *visual=visual_path?fopen(visual_path,"w"):NULL;if(visual_path && !visual)return 2;
    for(unsigned test=0;test<SCD_REPLAY_COUNT;test++) {
        unsigned era=scd_replay_era(test);char path[128];size_t n,cn;
        snprintf(path,sizeof(path),"assets/generated/ppz%u.bin",era);unsigned char *data=read_file(path,&n);
        snprintf(path,sizeof(path),"assets/generated/collision%u.bin",era);unsigned char *collision=read_file(path,&cn);
        stage_t stage;if(stage_open(&stage,data,n) || scd_player_init(&stage,collision,cn,era))return 2;
        scd_replay_begin(test);
        /* src/main.c replay: the camera begins where the test placed Sonic (SCR*.C playposiset). */
        {scd_player_state p=scd_player_get();int cy=scd_camera_v_begin(0,0,era,p.y/65536,p.resets);scd_act_camera(scd_camera_h(),cy);}
        for(unsigned frame=0;frame<SCD_REPLAY_FRAMES;frame++) {
            scd_replay_tick(test,frame);
            /* Test 17 teleports Sonic 2850 px and back: move the camera with him,
               since the Object Spawner frames objects out by the camera window
               (Level/Object Spawner.asm), not by Sonic. */
            if(test==17 && (frame==40 || frame==80))scd_camera_h_sync(frame==40?2840:0);
            scd_player_step(scd_replay_buttons(test,frame));
            uint32_t words[16];scd_replay_words(scd_player_get(),words);
            if(visual){uint32_t v[2];scd_replay_visual_words(scd_player_get(),v);fprintf(visual,"%u %u %08x %08x\n",test,frame,(unsigned)v[0],(unsigned)v[1]);}
            printf("%u %u",test,frame);
            for(unsigned i=0;i<16;i++)printf(" %08x",(unsigned)words[i]);
            puts("");
            /* src/main.c: GAME.C scroll() after the recorded update; a dead Sonic pins scralim_down.
               The camera reaches act.c as in main.c (the object spawner frames out by it). */
            {scd_player_state p=scd_player_get();int cy=scd_camera_v_follow(p.y/65536,p.resets);scd_act_camera(scd_camera_h(),cy);}
        }
        free(collision);free(data);
    }
    if(visual && fclose(visual))return 2;
    return 0;
}
