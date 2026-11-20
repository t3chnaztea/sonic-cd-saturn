#include <libretro.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>
#include "act_pad_replay.h"

static char path[]="/tmp/scd-act-pad-XXXXXX";
static void check(const char *text,int valid){
    FILE *file=fopen(path,"w");assert(file);
    assert(fputs(text,file)>=0);assert(!fclose(file));
    assert((act_pad_load(path)==0)==valid);
}
int main(void){
    int fd=mkstemp(path);assert(fd>=0);close(fd);
    const char *first="40 0 0 0 0 0 0 0 1 0 0 0 0 0 0 0 0 0\n";
    char rows[1024];
    snprintf(rows,sizeof(rows),"%s41 31 0 0 0 0 0 0 2 0 0 0 0 0 0 0 0 0\n",first);
    check(rows,1);assert(act_pad_count==2 && act_pad_states[1].buttons==31);
    check(first,1);assert(act_pad_count==1); /* Successive stages reset. */
    assert(act_pad_load_sequence("/tmp",3)==-1 && !act_pad_count);
    check(rows,1);
    assert(act_pad_mask(0)==0);
    assert(act_pad_mask(31)==((1u<<RETRO_DEVICE_ID_JOYPAD_UP)|(1u<<RETRO_DEVICE_ID_JOYPAD_DOWN)|
           (1u<<RETRO_DEVICE_ID_JOYPAD_LEFT)|(1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT)|(1u<<RETRO_DEVICE_ID_JOYPAD_B)));
    check("",0);
    check("40 0 0 0 0 0 0 0 1 0 0 0 0 0 0 0 0 0",0);
    check("40 0 0 0 0 0 0 0 1 0 0 0 0 0 0 0 0\n",0);
    check("40 0 0 0 0 0 0 0 1 0 0 0 0 0 0 0 0 0 extra\n",0);
    check("40 0 100000000 0 0 0 0 0 1 0 0 0 0 0 0 0 0 0\n",0);
    check("40 0 -1 0 0 0 0 0 1 0 0 0 0 0 0 0 0 0\n",0);
    check("40 32 0 0 0 0 0 0 1 0 0 0 0 0 0 0 0 0\n",0);
    check("40 8 0 0 0 0 0 0 1 0 0 0 0 0 0 0 0 0\n",0);
    snprintf(rows,sizeof(rows),"%s42 0 0 0 0 0 0 0 2 0 0 0 0 0 0 0 0 0\n",first);check(rows,0);
    snprintf(rows,sizeof(rows),"%s41 0 0 0 0 0 0 0 3 0 0 0 0 0 0 0 0 0\n",first);check(rows,0);
    FILE *file=fopen(path,"w");assert(file);
    for(unsigned i=0;i<=ACT_PAD_MAX;i++)fprintf(file,"%u 0 0 0 0 0 0 0 %x 0 0 0 0 0 0 0 0 0\n",i+40,i+1);
    assert(!fclose(file));act_pad_count=0;assert(act_pad_load(path)==-1 && !act_pad_count);
    assert(!unlink(path));
    assert(act_pad_load(path)==-1 && !act_pad_count);
    puts("Recorded act pad: parser bounds, malformed inputs and controller mapping pass");
}
