/* Exercise real death/reload and the complete checkpoint protection window. */
#include <assert.h>
#include <stdio.h>
#include "EQU.H"
#include "scd_player.h"
#include "scd_objects.h"
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
    for(unsigned n=0;n<259;n++){
        unsigned era=n<255?0:n-255,id=n<255?n+1:0;
        assert(!scd_player_init(stages+era,collision[era],9472,era));scd_objects_reset(era,0);
        scd_player_place(3000,64,0,0,2);actwk[0].actfree[2]=1;
        unsigned ticks=n<120?n:n<240?3540+n-120:n==240?17999:n==241?18000:n==242?18001:35999;
        if(!id)ticks=17;
        for(unsigned t=0;t<ticks;t++)scd_player_step(0);
        if(id)assert(scd_player_checkpoint_activate(id));
        scd_checkpoint saved=scd_player_checkpoint();
        scd_player_points(1230);scd_player_inventory(17,1);scd_player_powerup(3);scd_player_powerup(4);
        scd_player_place(3000,2041,0,0,2);scd_player_step(0);
        assert(scd_player_get().routine==6);
        for(unsigned t=0;t<700 && !scd_player_get().resets;t++)scd_player_step(0);
        scd_player_state s=scd_player_get();scd_powerup_state power=scd_player_powerups();
        assert(s.resets==1 && s.lives==2 && s.routine==2);
        assert(s.score==1230 && !s.rings && !s.shield && !power.invincible && !power.shoes);
        assert(s.x/65536==(id?saved.x:stages[era].start_x) && s.y/65536==(id?saved.y:stages[era].start_y));
        /* This fixture also runs old player sources to prove the protection
           failure. Saved-clock parity has its own old/new retail-CPU gate. */
        if(!id)assert(!s.elapsed);
        unsigned protected=0,expired=0;
        if(id){
            /* Freeze only movement and streaming, not display/timer or damage. */
            scd_objects_reset(era,0);actwk[0].actfree[2]=1;
            for(unsigned t=0;t<120;t++){
                scd_objects_hurt(2990);
                if(scd_player_get().routine!=2)break;
                protected++;
                scd_player_step(0);
                assert(scd_player_get().hurt==119-t);
                assert(scd_player_get().display_hidden==!((120-t)&4));
            }
            if(protected==120){
                actwk[0].actfree[2]=0;scd_objects_hurt(2990);
                expired=scd_player_get().routine==6;
            }
        }
        printf("checkpoint %u %u %u %d %d %u %u %u %u %u %u %u %u %u %u %u\n",
            era,id,ticks,s.x/65536,s.y/65536,s.hurt,s.rings,s.shield,power.invincible,power.shoes,
            s.lives,s.score,s.elapsed,saved.elapsed,protected,expired);
    }
}
