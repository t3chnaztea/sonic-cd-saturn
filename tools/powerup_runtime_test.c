#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "EQU.H"
#include "scd_objects.h"
#include "powerup_runtime.h"
static stage_t stage;
static unsigned char data[300000],collision[9472];
static scd_powerup_runtime effects;
static int mutate_touch;
short pcol(sprite_status *p){
    if(mutate_touch){
        scd_player_effect_sample sample=scd_player_effects();
        assert(sample.record && !sample.valid);
        assert(sample.record_x==p->xposi.w.h && sample.record_y==p->yposi.w.h);
        p->xposi.w.h+=11;p->yposi.w.h+=7;p->cddat^=1;
    }
    return 0;
}
static void reset(void){
    assert(!scd_player_init(&stage,collision,sizeof(collision),0));
    scd_objects_reset(0,0);scd_player_place(500,100,0,0,2);
    scd_powerup_runtime_reset(&effects,0);assert(!scd_player_effects().valid);
}
static scd_player_effect_sample tick(unsigned travel){
    scd_player_step(0);
    scd_player_effect_sample sample=scd_player_effects();
    scd_powerup_runtime_step(&effects,sample,scd_player_get().shield,
        !!scd_player_powerups().invincible,travel);
    return sample;
}
int main(void){
    FILE *f=fopen("assets/generated/ppz0.bin","rb");assert(f);
    size_t n=fread(data,1,sizeof(data),f);assert(feof(f));fclose(f);assert(!stage_open(&stage,data,n));
    f=fopen("assets/generated/collision0.bin","rb");assert(f);
    assert(fread(collision,1,sizeof(collision),f)==sizeof(collision));fclose(f);
    reset();mutate_touch=1;
    scd_player_effect_sample sample=tick(0);mutate_touch=0;
    assert(sample.valid && sample.x==sample.record_x+11 && sample.y==sample.record_y+7);
    assert(effects.context.history[0][0]==sample.record_x && effects.context.x==sample.x);
    scd_powerup_runtime saved=effects;
    for(unsigned i=0;i<100;i++){assert(scd_player_effects().x==sample.x);assert(!memcmp(&effects,&saved,sizeof(saved)));}
    /* A real rising monitor item grants shield in the ordinary actor pass. */
    reset();actwk[0].actfree[2]=1;
    assert(scd_objects_spawn(SCD_OBJ_MONITOR_ITEM,600,300,2,0)>=0);
    unsigned granted=0;
    for(unsigned i=0;i<40;i++){
        sample=tick(0);
        if(scd_player_get().shield && !granted){
            granted=i+1;assert(!sample.shield && effects.actors[0].active==3);
            assert(!effects.actors[0].routine && !effects.submitted);
        }else if(granted && i+1==granted+1){assert(sample.shield && effects.actors[0].routine==2 && !effects.submitted);}
        else if(granted && i+1==granted+2){assert(effects.actors[0].mapping==1 && effects.submitted==1);}
    }
    assert(granted==33);
    scd_powerup_visual shield=effects.actors[0];
    scd_player_powerup(3);tick(0);
    assert(!memcmp(&shield,&effects.actors[0],sizeof(shield)));
    assert(!(effects.submitted&1) && effects.actors[1].routine==4);
    for(unsigned i=0;i<15;i++)tick(0);
    scd_powerup_visual invincible[4];memcpy(invincible,effects.actors+1,sizeof(invincible));
    for(unsigned i=0;i<20;i++){
        tick(1);assert(!memcmp(invincible,effects.actors+1,sizeof(invincible)));
        assert(!(effects.submitted&31));
    }
    assert(effects.submitted&0x1e0);
    tick(0);assert(!(effects.submitted&0x1e0));
    for(unsigned i=5;i<9;i++)assert(!effects.actors[i].active);
    assert(memcmp(invincible,effects.actors+1,sizeof(invincible)));
    unsigned cursor=effects.actors[1].cursor,phase=effects.actors[1].phase;
    scd_player_powerup(3);tick(0);
    assert(effects.actors[1].phase==(phase+4)%24 && effects.actors[1].cursor>=cursor);
    sample=scd_player_effects();sample.resets++;
    scd_powerup_runtime_step(&effects,sample,1,1,0);
    assert(effects.updates==1 && effects.context.record_index==4 && !effects.submitted);
    for(unsigned i=1;i<64;i++)assert(!effects.context.history[i][0] && !effects.context.history[i][1]);
    printf("Effect scheduler: pre-touch record, pre-object context, late real monitor grant at %u, init delay, suppression/resume, recollection and reset passed\n",granted);
    f=fopen("build/powerup-runtime/culling-retail-cases.bin","rb");assert(f);
    unsigned cases=0;unsigned char record[9];
    while((n=fread(record,1,9,f))){
        assert(n==9);int v[4];
        for(unsigned i=0;i<4;i++)v[i]=(int16_t)((record[2*i]<<8)|record[2*i+1]);
        scd_powerup_visual actor={.x=v[0],.y=v[1],.width=16};
        struct {int before,x,y,after;} output={1234,0,0,5678};
        assert(scd_powerup_screen(&actor,v[2],v[3],&output.x,&output.y)==record[8]);
        assert(output.before==1234 && output.after==5678);cases++;
    }
    assert(feof(f) && cases==13211);fclose(f);
    printf("Effect camera culling: %u retail cases passed with sanitizers\n",cases);
}
