/* Original Level/_Objects/HUD and Points: screen origin (16,8), lives (16,200).
   This is presentation only: counters and the simulation clock are not changed. */
#include "hud-original.inc"
#include "hud_animation.h"
static uint8_t hud_rings_red;
static uint32_t hud_reset_count;
static void gameplay_hud_reset(void){hud_rings_red=0;hud_reset_count=player.resets;}
static void gameplay_hud_step(uint32_t vint){
    if(hud_reset_count!=player.resets)gameplay_hud_reset();
    hud_rings_red=scd_hud_ring_step(hud_rings_red,vint,player.rings);
}
extern uint8_t hud_original[];
static void hud_original_upload(void){
    assert(0x8000+HUD_ORIGINAL_BYTES<=0x10000);
    memcpy((void *)VDP1_VRAM(0x8000),hud_original,HUD_ORIGINAL_BYTES);
}
static void hud_original_piece(unsigned *count,const hud_piece *p,int x,int y){
    vdp1_cmdt_t *cmd=sprite_commands->cmdts+(*count)++;
    memset(cmd,0,sizeof(*cmd));vdp1_cmdt_normal_sprite_set(cmd);
    const vdp1_cmdt_draw_mode_t mode={.color_mode=VDP1_CMDT_CM_RGB_32768,.end_code_disable=true};
    vdp1_cmdt_draw_mode_set(cmd,mode);vdp1_cmdt_char_size_set(cmd,p->width,p->height);
    vdp1_cmdt_char_base_set(cmd,VDP1_VRAM(0x8000+p->offset));cmd->cmd_xa=x+p->x;cmd->cmd_ya=y+p->y;
}
static void hud_original_number(unsigned *count,unsigned value,unsigned digits,int x,int y,int leading){
    unsigned divisor=1;for(unsigned i=1;i<digits;i++)divisor*=10;
    for(unsigned i=0;i<digits;i++,x+=8){
        unsigned digit=value/divisor%10;
        if(digit || leading || i+1==digits){leading=1;hud_original_piece(count,hud_digits+digit,x,y);}
        divisor/=10;
    }
}
static void gameplay_hud(unsigned *count){
    for(unsigned i=0;i<sizeof(hud_labels)/sizeof(hud_labels[0]);i++)hud_original_piece(count,hud_labels+i,16,8);
    const hud_piece *rings=hud_rings_red?hud_rings1:hud_rings0;
    for(unsigned i=0;i<3;i++)hud_original_piece(count,rings+i,16,8);
    hud_original_number(count,player.score,7,56,8,0);
    unsigned ticks=player.elapsed>35999?35999:player.elapsed;
    hud_original_number(count,ticks/3600,1,56,24,1);
    hud_original_number(count,ticks/60%60,2,72,24,1);
    hud_original_number(count,ticks==35999?99:ticks%60*100/60,2,96,24,1);
    hud_original_number(count,player.rings,3,64,40,0);
    /* Retail timeZone order is Past, Present, Future; the port stores Present first. */
    hud_original_piece(count,hud_lives+(era>1?2:era^1),16,200);
    hud_original_piece(count,hud_cross,16,200);
    hud_original_number(count,player.lives>9?9:player.lives,1,40,204,1);
    scd_world_state travel=scd_world_get();
    if(travel.direction && (travel.ticks<90 || !(player.frame&1))){
        const hud_piece *icon=travel.direction<0?hud_past:hud_future;
        unsigned n=travel.direction<0?sizeof(hud_past)/sizeof(*icon):sizeof(hud_future)/sizeof(*icon);
        for(unsigned i=0;i<n;i++)hud_original_piece(count,icon+i,68,210);
    }
}
