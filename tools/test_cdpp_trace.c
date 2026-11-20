/* CD++ preset player traces (docs/CDPP-PRESET-SPEC.md section 7). Each case
   loads Palmtree Panic (era 1, no object layout, like tools/player_replay.c's
   fixtures), places Sonic, sets scd_preset_flags, latches it as an act start
   does and plays a fixed pad script. One row per update:
       case frame x y vx vy speed flags animation charge score sizes
   tools/test_cdpp_player.sh compares the rows with tests/routes/cdpp/traces/
   and regenerates them only with --regenerate. Host evidence only. */
#include "player_replay.h"
#include "camera_v.h"
#include "act.h"
#include "scd_objects.h"
#include "player_plus.h"
#include "EQU.H"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned char *read_file(const char *name,size_t *size){
    FILE *f=fopen(name,"rb");if(!f){perror(name);exit(2);}
    fseek(f,0,SEEK_END);*size=(size_t)ftell(f);rewind(f);
    unsigned char *data=malloc(*size);if(!data || fread(data,1,*size,f)!=*size)exit(2);
    fclose(f);return data;
}
enum { D=SCD_DOWN, J=SCD_JUMP, R=SCD_RIGHT, L=SCD_LEFT };
/* A pad script: runs of (frames, buttons), 0 frames ends it. */
typedef struct { unsigned frames,buttons; } run_t;
typedef struct {
    const char *name;unsigned flags,chibi;
    int x,y,vx,vy;unsigned place_flags;
    int spawn_type,spawn_x,spawn_y,spawn_subtype;
    run_t pad[24];
    int spawn2_type,spawn2_x,spawn2_y; /* a second object (0: none) */
    /* After update impulse_at (>0), set Sonic's speed as an object pass does (a CC
       bumper or launcher: the ball state stays). */
    unsigned impulse_at;int impulse_vx,impulse_vy;
} case_t;
#define SETTLE {20,0}
/* Spin dash fixtures stand on the replay floor (80,493). */
static const case_t cases[]={
    /* F1: one press = rev 0 = 8 px/f; two presses; five presses (decay keeps them under the cap). */
    {"dash-0",SCD_PLUS_SPINDASH2,0,80,488,0,0,2,-1,0,0,0,{SETTLE,{6,D},{1,D|J},{8,D},{60,0},{0,0}}},
    {"dash-1",SCD_PLUS_SPINDASH2,0,80,488,0,0,2,-1,0,0,0,{SETTLE,{6,D},{1,D|J},{2,D},{1,D|J},{3,D},{60,0},{0,0}}},
    {"dash-4",SCD_PLUS_SPINDASH2,0,80,488,0,0,2,-1,0,0,0,{SETTLE,{6,D},{1,D|J},{1,D},{1,D|J},{1,D},{1,D|J},{1,D},{1,D|J},{1,D},{1,D|J},{2,D},{60,0},{0,0}}},
    /* Eight presses, released straight after the last one: the 8 cap (12 px/f). */
    {"dash-max",SCD_PLUS_SPINDASH2,0,80,488,0,0,2,-1,0,0,0,{SETTLE,{6,D},{1,D|J},{1,D},{1,D|J},{1,D},{1,D|J},{1,D},{1,D|J},{1,D},{1,D|J},{1,D},{1,D|J},{1,D},{1,D|J},{1,D},{1,D|J},{60,0},{0,0}}},
    /* Decay: the same four revs, then Down held 60 updates before release. */
    {"dash-decay",SCD_PLUS_SPINDASH2,0,80,488,0,0,2,-1,0,0,0,{SETTLE,{6,D},{1,D|J},{1,D},{1,D|J},{1,D},{1,D|J},{1,D},{1,D|J},{1,D},{1,D|J},{60,D},{60,0},{0,0}}},
    /* The same five presses with the preset off: the CD dash (Classic). */
    {"dash-classic",0,0,80,488,0,0,2,-1,0,0,0,{SETTLE,{6,D},{1,D|J},{1,D},{1,D|J},{1,D},{1,D|J},{1,D},{1,D|J},{1,D},{1,D|J},{2,D},{60,0},{0,0}}},
    /* F5: small Sonic (chibi_flag, the MM shrink beam). F1 alone keeps the CD dash for him. */
    {"minidash",SCD_PLUS_MINIDASH,1,80,488,0,0,2,-1,0,0,0,{SETTLE,{6,D},{1,D|J},{1,D},{1,D|J},{2,D},{60,0},{0,0}}},
    {"minidash-f1-only",SCD_PLUS_SPINDASH2,1,80,488,0,0,2,-1,0,0,0,{SETTLE,{6,D},{1,D|J},{1,D},{1,D|J},{2,D},{60,0},{0,0}}},
    /* F2: airborne at 12 px/f with Right held. Classic pulls xspeed to 6 px/f. */
    {"aircap-off",SCD_PLUS_AIRCAP_OFF,0,80,300,3072,-1024,2,-1,0,0,0,{{40,R},{0,0}}},
    {"aircap-classic",0,0,80,300,3072,-1024,2,-1,0,0,0,{{40,R},{0,0}}},
    /* F2 still accelerates a slow Sonic up to the cap. */
    {"aircap-accel",SCD_PLUS_AIRCAP_OFF,0,80,100,1024,0,2,-1,0,0,0,{{40,R},{0,0}}},
    /* F3: falling (not balled), a press curls; a second press does not (once per airtime). */
    {"airroll",SCD_PLUS_AIRROLL,0,80,380,0,0,2,-1,0,0,0,{{6,0},{1,J},{4,0},{1,J},{60,0},{0,0}}},
    {"airroll-classic",0,0,80,380,0,0,2,-1,0,0,0,{{6,0},{1,J},{4,0},{1,J},{60,0},{0,0}}},
    /* F3 after a spring (tools/player_replay.c test 8's spring under Sonic). */
    {"spring-roll",SCD_PLUS_AIRROLL,0,80,488,0,0,2,SCD_OBJ_SPRING,80,508,0,{{20,0},{1,J},{60,0},{0,0}}},
    /* F4: balled in the air, a press homes onto the badnik ahead (Anton). */
    {"homing",SCD_PLUS_HOMING|SCD_PLUS_AIRCAP_OFF,0,80,420,0,0,6,SCD_OBJ_ANTON,200,477,0,{{3,0},{1,J},{80,0},{0,0}}},
    {"homing-classic",0,0,80,420,0,0,6,SCD_OBJ_ANTON,200,477,0,{{3,0},{1,J},{80,0},{0,0}}},
    /* F4 yields to object control: a spring in the homing path launches Sonic and
       the homing attack ends there (it must not re-aim the launch at the badnik). */
    {"homing-spring",SCD_PLUS_HOMING|SCD_PLUS_AIRCAP_OFF,0,80,420,0,0,6,SCD_OBJ_SPRING,128,452,0,{{3,0},{1,J},{80,0},{0,0}},SCD_OBJ_ANTON,200,477},
    /* F4 yields to an impulse that keeps Sonic balled: homing onto the Anton, then
       an object sets -6,-8 px/f after update 5; the next updates keep it. */
    {"homing-impulse",SCD_PLUS_HOMING|SCD_PLUS_AIRCAP_OFF,0,80,420,0,0,6,SCD_OBJ_ANTON,200,477,0,{{3,0},{1,J},{40,0},{0,0}},0,0,0,5,-1536,-2048},
    /* After the first Anton's defeat bounce at frame 17, a fresh press at
       frame 18 may acquire the second Anton. The controls omit that edge or
       apply a later independent impulse before it. */
    {"homing-rearm-10",SCD_PLUS_HOMING|SCD_PLUS_AIRCAP_OFF,0,80,420,0,0,6,SCD_OBJ_ANTON,200,477,0,{{3,0},{1,J},{14,0},{1,J},{24,0},{0,0}},SCD_OBJ_ANTON,260,477},
    {"homing-rearm-31",SCD_PLUS_PRESET,0,80,420,0,0,6,SCD_OBJ_ANTON,200,477,0,{{3,0},{1,J},{14,0},{1,J},{24,0},{0,0}},SCD_OBJ_ANTON,260,477},
    {"homing-rearm-no-edge",SCD_PLUS_HOMING|SCD_PLUS_AIRCAP_OFF,0,80,420,0,0,6,SCD_OBJ_ANTON,200,477,0,{{3,0},{1,J},{18,0},{0,0}},SCD_OBJ_ANTON,260,477},
    {"homing-rearm-impulse",SCD_PLUS_HOMING|SCD_PLUS_AIRCAP_OFF,0,80,420,0,0,6,SCD_OBJ_ANTON,200,477,0,{{3,0},{1,J},{14,0},{1,J},{24,0},{0,0}},SCD_OBJ_ANTON,260,477,17,-1536,-2048},
    /* F4 with nothing in range: the forward air dash. */
    {"homing-dash",SCD_PLUS_HOMING|SCD_PLUS_AIRCAP_OFF,0,80,420,0,0,6,-1,0,0,0,{{3,0},{1,J},{60,0},{0,0}}},
    /* The whole preset (flags 31) on the five-press dash, then a jump. */
    {"preset",SCD_PLUS_PRESET,0,80,488,0,0,2,-1,0,0,0,{SETTLE,{6,D},{1,D|J},{1,D},{1,D|J},{1,D},{1,D|J},{2,D},{10,0},{1,J},{30,R},{0,0}}},
};
int main(int argc,char **argv){
    const char *only=argc>1?argv[1]:NULL;
    size_t n,cn;
    unsigned char *data=read_file("assets/generated/ppz1.bin",&n),*collision=read_file("assets/generated/collision1.bin",&cn);
    for(unsigned c=0;c<sizeof(cases)/sizeof(cases[0]);c++){
        const case_t *t=&cases[c];
        if(only && strcmp(only,t->name))continue;
        stage_t stage;
        scd_preset_flags=(uint8_t)t->flags;
        if(stage_open(&stage,data,n) || scd_player_init(&stage,collision,cn,1))return 2;
        if(scd_plus_active()!=t->flags)return 3;
        scd_objects_reset(1,0);
        chibi_flag=(unsigned char)t->chibi;
        scd_player_place(t->x,t->y,0,0,t->place_flags);
        if(t->vx || t->vy)scd_player_velocity(t->vx,t->vy);
        if(t->spawn_type>=0)scd_objects_spawn((unsigned)t->spawn_type,t->spawn_x,t->spawn_y,(unsigned)t->spawn_subtype,0);
        if(t->spawn2_type>0)scd_objects_spawn((unsigned)t->spawn2_type,t->spawn2_x,t->spawn2_y,0,0);
        {scd_player_state p=scd_player_get();int cy=scd_camera_v_begin(0,0,1,p.y/65536,p.resets);scd_act_camera(scd_camera_h(),cy);}
        unsigned frame=0;
        for(const run_t *r=t->pad;r->frames;r++)for(unsigned i=0;i<r->frames;i++,frame++){
            scd_player_step(r->buttons);
            if(t->impulse_at && frame==t->impulse_at){actwk[0].xspeed.w=(short)t->impulse_vx;actwk[0].yspeed.w=(short)t->impulse_vy;}
            scd_player_state p=scd_player_get();
            /* Diagnostic (CDPP_ACTORS=1, stderr): the live actors after each update. */
            if(getenv("CDPP_ACTORS"))for(unsigned i=1;i<128;i++){const sprite_status *q=&actwk[i];
                if(q->actno)fprintf(stderr,"%s %u slot %u actno %u x %d y %d colino %u actflg %02x colicnt %u cddat %02x\n",t->name,frame,
                    i,q->actno,q->xposi.w.h,q->yposi.w.h,q->colino,q->actflg,q->colicnt,q->cddat);}
            printf("%s %u %d %d %d %d %d %02x %u %u %d %u/%u\n",t->name,frame,(int)(p.x>>16),(int)(p.y>>16),
                   p.vx,p.vy,p.speed,(unsigned)p.flags,(unsigned)p.animation,(unsigned)p.charge,(int)p.score,
                   (unsigned)actwk[0].sprvsize,(unsigned)actwk[0].sprhs);
            {int cy=scd_camera_v_follow(p.y/65536,p.resets);scd_act_camera(scd_camera_h(),cy);}
        }
    }
    free(collision);free(data);
    return 0;
}
