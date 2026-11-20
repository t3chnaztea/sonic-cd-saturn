/* Compiled R3/FRIEND3.C p_move/p_rev against the native ground animal. */
#include "EQU.H"
#include "scd_objects.h"
#include "scd_player.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
void source_friend_step(sprite_status*);
void actionsub(sprite_status *o){(void)o;}
void frameout_s(sprite_status *o){(void)o;}
static unsigned char stage_bytes[300000],collision[9472];
static stage_t stage;
static void require(int okay,unsigned frame,const char *why){
    if(!okay){fprintf(stderr,"FAIL frame %u: %s\n",frame,why);exit(1);}
}
static size_t read_file(const char *name,void *out,size_t cap){
    FILE *f=fopen(name,"rb");require(f!=NULL,0,name);
    size_t n=fread(out,1,cap,f);require(!ferror(f) && (n<cap || fgetc(f)==EOF),0,name);
    fclose(f);return n;
}
int main(void){
    size_t bytes=read_file("assets/generated/cc31C.bin",stage_bytes,sizeof(stage_bytes));
    require(!stage_open(&stage,stage_bytes,bytes),0,"stage opens");
    bytes=read_file("assets/generated/cccollision31C.bin",collision,sizeof(collision));
    scd_player_zone(1);scd_objects_zone(1);scd_player_act(0);scd_objects_act(0);
    require(!scd_player_init(&stage,collision,bytes,2),0,"player initializes");
    scd_objects_reset(2,0);
    require(scd_objects_spawn(SCD_OBJ_FRIEND3,1904,888,1,0)==0,0,"ground animal spawns");
    scd_objects_step(0,0);
    actwk[100]=actwk[1];
    *((int*)(void*)(actwk[100].actfree+2))=65536;
    *((int*)(void*)(actwk[100].actfree+6))=-0x40000;
    unsigned bounces=0,reversals=0;
    for(unsigned frame=1;frame<=900;frame++){
        unsigned previous=actwk[100].r_no0;
        source_friend_step(&actwk[100]);
        if(previous==6)reversals++;
        else if(actwk[100].r_no0>previous)bounces++;
        scd_objects_step(0,0);
        sprite_status *native=&actwk[1],*original=&actwk[100];
        require(native->xposi.l==original->xposi.l,frame,"X position");
        require(native->yposi.l==original->yposi.l,frame,"Y position");
        require(native->r_no0==original->r_no0,frame,"routine and reversal timing");
        require(native->patno==original->patno,frame,"pose");
        require(native->sprvsize==original->sprvsize,frame,"collision height");
        require((native->actflg&1)==(original->actflg&1),frame,"horizontal flip");
    }
    require(bounces>=2 && reversals>=1,900,"two contacts and reversal exercised");
    printf("R3 ground animal: 900 source/native updates, %u contacts, %u reversals match\n",bounces,reversals);
}
