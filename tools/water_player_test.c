/* Underwater player motion: src/player.c scd_player_motion / scd_player_hurt_motion
   against the original PLAYER.C play00walk, play00jump, ball00walk, ball00jump and
   play00damage bodies (build/water/player_original.c, renamed ref_*), both over the
   same compiled original helpers (keispd, levermove, jumpchk, jumpmove, fcol...).
   Each update starts both from one saved state on Tidal Tempest 1 Present terrain,
   in and out of water, and compares actwk[0], dirstk and the sound requests. The
   reference stubs the parts the native step runs elsewhere or not at all:
   bye_chk/backto_chk (time travel), limitchk (native bounds), and play00damage's
   playsp, play00damage_sub, playposiwkset, patchgmain, actionsub. */
#include "EQU.H"
#include "ACTION.H"
#include "PLAYER.H"
#include "scd_player.h"
#include "stage.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void scd_player_motion(void);
void scd_player_hurt_motion(void);
void scd_player_statics_reset(void);
void ref_motion(void);
void ref_play00damage(void);

static unsigned char *read_file(const char *name,size_t *size){
    FILE *f=fopen(name,"rb");if(!f){perror(name);exit(2);}
    fseek(f,0,SEEK_END);*size=ftell(f);rewind(f);
    unsigned char *data=malloc(*size);if(!data || fread(data,1,*size,f)!=*size)exit(2);
    fclose(f);return data;
}
static char sounds[64];static unsigned sound_n;
static void sink(short id){if(sound_n<60)sound_n+=snprintf(sounds+sound_n,sizeof(sounds)-sound_n,"%d,",id)>0?0:0;}
typedef struct{sprite_status a;char dir[4];char snd[64];}shot;
static void take(shot *s){memcpy(&s->a,&actwk[0],sizeof(actwk[0]));memcpy(s->dir,dirstk,4);memcpy(s->snd,sounds,64);}
static char sound_log[64];
static void sound_sink(short id){size_t n=strlen(sound_log);if(n<56)snprintf(sound_log+n,sizeof(sound_log)-n,"%d,",id);}

int main(int argc,char **argv){
    int mutate=argc>1 && !strcmp(argv[1],"--mutation-no-40"),mutate32=argc>1 && !strcmp(argv[1],"--mutation-no-32");
    size_t n,cn;unsigned char *data=read_file("assets/generated/tt41A.bin",&n);
    unsigned char *collision=read_file("assets/generated/ttcollision41A.bin",&cn);
    scd_player_zone(2);scd_player_act(0);
    stage_t stage;if(stage_open(&stage,data,n) || scd_player_init(&stage,collision,cn,0))return 2;
    scd_player_audio_set(sound_sink);
    (void)sink;
    unsigned updates=0,mismatches=0,water_updates=0,air=0,ground=0,roll=0,rolljump=0,hurt=0;
    /* Start points along TT1 Present (x, y), each dropped from above the floor. */
    static const int starts[][2]={{570,600},{700,600},{1013,700},{1200,640},{1600,560},{2000,700},{2600,560},{3200,600},{4000,640},{5000,600}};
    static const unsigned pads[]={0,8,4,8|16,4|16,8|2,2,8|32,32,4|2};
    for(unsigned st=0;st<sizeof(starts)/sizeof(starts[0]);st++)for(unsigned wet=0;wet<2;wet++)for(unsigned script=0;script<8;script++){
        scd_player_place(starts[st][0],starts[st][1],0,0,2);
        if(wet){actwk[0].cddat|=64;plmaxspdwk=768;pladdspdwk=6;plretspdwk=128/2;}
        else{plmaxspdwk=1536;pladdspdwk=12;plretspdwk=128;}
        unsigned previous=0;
        for(unsigned f=0;f<400;f++){
            unsigned buttons=pads[(f/((script%4)*9+7)+script)%10];
            /* script 6/7: take a hit every 97 updates (play00damage path) */
            if(script>=6 && f%97==50 && actwk[0].r_no0==2){actwk[0].r_no0=4;actwk[0].yspeed.w=-1024;actwk[0].xspeed.w=512;actwk[0].cddat|=2;}
            if(actwk[0].r_no0==4 && f%97==80){actwk[0].r_no0=2;}
            swdata.b.h=(unsigned char)buttons;swdata.b.l=(unsigned char)(buttons&~previous);previous=buttons;
            sprite_status saved;memcpy(&saved,&actwk[0],sizeof(saved));char dsaved[4];memcpy(dsaved,dirstk,4);
            shot native,ref;memset(&native,0,sizeof(native));memset(&ref,0,sizeof(ref));
            int hurting=actwk[0].r_no0==4;
            scd_player_statics_reset();sound_log[0]=0;
            if(hurting)scd_player_hurt_motion();else scd_player_motion();
            if(mutate && (saved.cddat&64) && (saved.cddat&2) && !hurting)actwk[0].yspeed.w+=40;
            if(mutate32 && (saved.cddat&64) && hurting)actwk[0].yspeed.w+=32;
            memcpy(sounds,sound_log,64);take(&native);
            memcpy(&actwk[0],&saved,sizeof(saved));memcpy(dirstk,dsaved,4);
            scd_player_statics_reset();sound_log[0]=0;
            if(hurting)ref_play00damage();else ref_motion();
            memcpy(sounds,sound_log,64);take(&ref);
            updates++;water_updates+=!!(saved.cddat&64);
            if(hurting)hurt++;else switch(saved.cddat&6){case 0:ground++;break;case 2:air++;break;case 4:roll++;break;default:rolljump++;}
            if(memcmp(&native,&ref,sizeof(native))){
                if(!mismatches++){const unsigned char *A=(const unsigned char*)&native,*B=(const unsigned char*)&ref;unsigned off=0;while(A[off]==B[off])off++;fprintf(stderr,"first differing byte %u (actwk size %zu)\n",off,sizeof(sprite_status));}
                if(mismatches==1)fprintf(stderr,"first mismatch: start %u wet %u script %u update %u cddat %02x r_no0 %u: native y %d.%04x vy %d vx %d / original y %d.%04x vy %d vx %d\n",
                    st,wet,script,f,saved.cddat,saved.r_no0,native.a.yposi.w.h,(unsigned short)native.a.yposi.w.l,native.a.yspeed.w,native.a.xspeed.w,
                    ref.a.yposi.w.h,(unsigned short)ref.a.yposi.w.l,ref.a.yspeed.w,ref.a.xspeed.w);
            }
            /* continue from the original's result */
            if(actwk[0].yposi.w.h>2040 || actwk[0].r_no0>=6)break;
        }
    }
    printf("water player motion: %u updates (%u in water; ground %u, air %u, roll %u, roll-jump %u, hurt %u), %u mismatches\n",
        updates,water_updates,ground,air,roll,rolljump,hurt,mismatches);
    return mismatches?1:0;
}
