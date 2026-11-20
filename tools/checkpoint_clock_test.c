/* Seed only the saved-time input, then execute actual checkpoint activation,
   death, reload and subsequent player updates. No replacement clock helper. */
#include <stdio.h>
#ifndef SCD_CLOCK_PLAYER
#define SCD_CLOCK_PLAYER "../src/player.c"
#endif
#include SCD_CLOCK_PLAYER
static stage_t stages[4];
static unsigned char data[4][300000],collision[4][9472];
int main(void){
    for(unsigned era=0;era<4;era++){
        char path[100];snprintf(path,sizeof(path),"assets/generated/ppz%u.bin",era);
        FILE *f=fopen(path,"rb");assert(f);size_t n=fread(data[era],1,sizeof(data[era]),f);assert(feof(f));fclose(f);
        assert(!stage_open(stages+era,data[era],n));
        snprintf(path,sizeof(path),"assets/generated/collision%u.bin",era);f=fopen(path,"rb");assert(f);
        assert(fread(collision[era],1,9472,f)==9472);fclose(f);
    }
    unsigned era,ticks,id;
    while(scanf("%u %u %u",&era,&ticks,&id)==3){
        assert(era<4 && id<=255);
        assert(!scd_player_init(stages+era,collision[era],9472,era));scd_objects_reset(era,0);
        scd_player_place(3000,64,0,0,2);elapsed=ticks;
        if(id)assert(scd_player_checkpoint_activate(id));
        unsigned saved=scd_player_checkpoint().elapsed;
        scd_player_place(3000,2041,0,0,2);scd_player_step(0);
        assert(scd_player_get().routine==6);
        for(unsigned n=0;n<700 && !scd_player_get().resets;n++)scd_player_step(0);
        scd_player_state state=scd_player_get();
        assert(state.resets==1 && state.routine==2 && state.lives==2);
        assert(state.hurt==(id?120:0));
        printf("clock %u %u %u %u",era,ticks,id,saved);
        scd_objects_reset(era,0);actwk[0].actfree[2]=1;
        for(unsigned n=0;n<=120;n++){
            printf(" %u",scd_player_get().elapsed);
            if(n<120)scd_player_step(0);
        }
        putchar('\n');
    }
    assert(feof(stdin));return 0;
}
