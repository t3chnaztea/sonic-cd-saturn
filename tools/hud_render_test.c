/* Exercise the production HUD command builder with bounded VDP1 stand-ins.
   The Python checker independently renders original mappings, not this list. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "world.h"
typedef struct {int32_t cmd_xa,cmd_ya;uint32_t width,height,offset;} vdp1_cmdt_t;
typedef struct {unsigned color_mode;bool end_code_disable;} vdp1_cmdt_draw_mode_t;
enum {VDP1_CMDT_CM_RGB_32768=5};
static unsigned char vram[0x10000];
#define VDP1_VRAM(at) (vram+(at))
static struct {vdp1_cmdt_t cmdts[64];} commands;
static typeof(commands) *sprite_commands=&commands;
static scd_player_state player;
static unsigned era;
static scd_world_state world;
scd_world_state scd_world_get(void){return world;}
static void vdp1_cmdt_normal_sprite_set(vdp1_cmdt_t *c){assert(c>=commands.cmdts && c<commands.cmdts+64);}
static void vdp1_cmdt_draw_mode_set(vdp1_cmdt_t *c,vdp1_cmdt_draw_mode_t m){(void)c;assert(m.color_mode==5 && m.end_code_disable);}
static void vdp1_cmdt_char_size_set(vdp1_cmdt_t *c,unsigned w,unsigned h){assert(w && !(w&7) && h);c->width=w;c->height=h;}
static void vdp1_cmdt_char_base_set(vdp1_cmdt_t *c,const void *p){
    c->offset=(uint32_t)((const unsigned char *)p-vram);
    assert(!(c->offset&7) && c->offset>=0x8000 && c->offset+c->width*c->height*2<=sizeof(vram));
}
#include "hud_view.inc"
uint8_t hud_original[HUD_ORIGINAL_BYTES];
static void word(uint32_t v){for(int shift=24;shift>=0;shift-=8)assert(putchar((v>>shift)&255)!=EOF);}
int main(void){
    FILE *art=fopen("assets/generated/hud-original.bin","rb");assert(art);
    assert(fread(hud_original,1,sizeof(hud_original),art)==sizeof(hud_original));assert(fgetc(art)==EOF);fclose(art);
    hud_original_upload();assert(!memcmp(vram+0x8000,hud_original,sizeof(hud_original)));
    unsigned score,rings,ticks,lives,frame,vint,reset,step;
    int direction;unsigned travel;
    while(scanf("%u %u %u %u %u %u %u %d %u %u %u",&score,&rings,&ticks,&lives,&era,&frame,&vint,&direction,&travel,&reset,&step)==11){
        assert(era<4 && rings<=999 && lives<=255 && direction>=-1 && direction<=1);
        player.score=score;player.rings=rings;player.elapsed=ticks;player.lives=lives;player.frame=frame;
        world.direction=direction;world.ticks=travel;
        if(reset)gameplay_hud_reset();
        if(step)gameplay_hud_step(vint);
        memset(&commands,0,sizeof(commands));unsigned count=0;gameplay_hud(&count);assert(count<64);
        word(count);
        for(unsigned n=0;n<count;n++){
            const vdp1_cmdt_t *c=commands.cmdts+n;
            word((uint32_t)c->cmd_xa);word((uint32_t)c->cmd_ya);word(c->width);word(c->height);word(c->offset-0x8000);
        }
    }
    assert(feof(stdin));return 0;
}
