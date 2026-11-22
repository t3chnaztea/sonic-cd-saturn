/* Faithful source model from exact original COME__.MMD78dd6500.
   Original-only independent31fullframe proof lives in build/coming_analysis.
   Newtargetscreen/pixels/audio still require native+emulator verification. */
#include "coming.h"
#include <string.h>
void fe_coming_begin(fe_coming_state *s,const uint16_t palette[64],unsigned prior_hold){
    memset(s,0,sizeof(*s));s->scroll=s->shown_scroll=320;s->timer=1023;
    s->previous_hold=(uint8_t)prior_hold;s->initial_wait=1;memcpy(s->palette,palette,sizeof(s->palette));
}
int fe_coming_vint(fe_coming_state *s,unsigned hold){
    s->shown_scroll=s->scroll;s->hold=(uint8_t)hold;s->tap=(uint8_t)((s->hold^s->previous_hold)&s->hold);s->previous_hold=s->hold;
    if(s->timer){s->scroll--;s->timer--;}s->frames++;
    if(s->initial_wait){s->initial_wait=0;return 0;}
    if(!s->exit_reason){if(s->tap&0xf0)s->exit_reason=s->tap&0xf0;else if(!s->timer)s->exit_reason=0x100;}
    return s->exit_reason!=0;
}
int fe_coming_fade(fe_coming_state *s){
    if(s->fade_step>=24)return 0;
    unsigned shift=(s->fade_step/8)*4,sub=2u*(s->fade_step%8)<<shift,mask=14u<<shift;
    for(unsigned i=0;i<64;i++){unsigned v=s->palette[i]&mask;s->palette[i]=(uint16_t)((s->palette[i]&~mask)|(v<sub?0:v-sub));}
    s->fade_step++;return 1;
}
static uint16_t fe_cm_be16(const uint8_t *p){return (uint16_t)((unsigned)p[0]<<8|p[1]);}
static uint32_t fe_cm_be32(const uint8_t *p){return (uint32_t)p[0]<<24|(uint32_t)p[1]<<16|(uint32_t)p[2]<<8|p[3];}
static uint32_t fe_cm_crc(const uint8_t *p,unsigned n){uint32_t c=~0u;while(n--){c^=*p++;for(unsigned i=0;i<8;i++)c=(c>>1)^(0xedb88320u&(0u-(c&1)));}return ~c;}
enum {fe_cm_header=32,fe_cm_palette=128,fe_cm_art=150*32,fe_cm_map=128*32*2,fe_cm_logical=32+128+150*32+128*32*2,fe_cm_load=0x00200000,fe_cm_max=0x14000};
/* CMG1 logicalsize,150tiles,4096mapwords,scroll320,timer1023,CRC32,64colours.
   Palette16..63, tile0 and sourceunused plane cells must remain zero. */
int fe_coming_pack_valid(const uint8_t *p,unsigned bytes){
    if(!p || bytes<fe_cm_header || bytes>fe_cm_max || (bytes&2047) || memcmp(p,"CMG1",4))return 0;
    if(fe_cm_be32(p+4)!=fe_cm_logical || fe_cm_be32(p+8)!=150 || fe_cm_be32(p+12)!=4096 || fe_cm_be32(p+16)!=320 || fe_cm_be32(p+20)!=1023 || fe_cm_be32(p+28)!=64 || fe_cm_logical>bytes || bytes-fe_cm_logical>=2048)return 0;
    if(fe_cm_crc(p+32,fe_cm_logical-32)!=fe_cm_be32(p+24))return 0;
    for(unsigned i=fe_cm_logical;i<bytes;i++)if(p[i])return 0;
    for(unsigned i=0;i<64;i++){unsigned v=fe_cm_be16(p+32+i*2);if((v&~0xeee) || (i>=16 && v))return 0;}
    for(unsigned i=0;i<32;i++)if(p[32+128+i])return 0;
    const uint8_t *map=p+32+128+fe_cm_art;
    for(unsigned y=0;y<32;y++)for(unsigned x=0;x<128;x++){
        unsigned word=fe_cm_be16(map+(y*128+x)*2);
        if((word&2047)>=150 || (word&0x6000) || ((y>=28 || x>=96) && word))return 0;
    }
    return 1;
}
#ifndef SCD_COMING_HOST
#include <yaul.h>
#include "frontend.h"
#include "stage.h"
#include "audio.h"
#include "cd_root.h"
#include "fmv_fe_names.h"
#include "fmv_stm.h"
/* Required Root-owned provider. No weak/no-op/abrupt-stop substitute.
   Must implement original SCMD14 -> FDRCHG,d1=20hex and reset for nextsong.
   This dependency deliberately blocks fullintegration until reviewed. */
extern void scd_audio_cdda_fade(unsigned rate);
volatile fe_coming_status fe_coming_qa __attribute__((section(".data.fe_coming_qa")));
static fe_coming_state fe_cm_state __attribute__((section(".data.fe_cm_state")));
static void fe_cm_frame(void){
    vdp2_scrn_scroll_x_set(VDP2_SCRN_NBG0,fix16_int32_from((0u-(uint32_t)fe_cm_state.scroll)&1023));
    vdp2_sync();vdp2_sync_wait();scd_audio_update();
    volatile uint16_t *cram=(volatile uint16_t *)VDP2_CRAM_MODE_0_OFFSET(0,0,0);
    for(unsigned i=0;i<64;i++)cram[i]=(uint16_t)(0x8000|fmv_md_to_rgb555(fe_cm_state.palette[i]));
    vdp2_scrn_back_color_set(VDP2_VRAM_ADDR(3,0x1bffe),(rgb1555_t){.raw=cram[0]});
    smpc_peripheral_digital_t pad;smpc_peripheral_process();smpc_peripheral_digital_port(1,&pad);
    unsigned hold=(pad.pressed.button.up?1u:0)|(pad.pressed.button.down?2u:0)|(pad.pressed.button.left?4u:0)|(pad.pressed.button.right?8u:0)|
        (pad.pressed.button.b?16u:0)|(pad.pressed.button.c?32u:0)|(pad.pressed.button.a?64u:0)|(pad.pressed.button.start?128u:0);
    unsigned previous=fe_cm_state.previous_hold;fe_coming_vint(&fe_cm_state,hold);
    fe_coming_qa.frames=fe_cm_state.frames;fe_coming_qa.scroll=(uint32_t)fe_cm_state.shown_scroll;fe_coming_qa.timer=fe_cm_state.timer;
    fe_coming_qa.held=fe_cm_state.hold;fe_coming_qa.tap=fe_cm_state.tap;fe_coming_qa.previous_hold=previous;fe_coming_qa.exit_reason=fe_cm_state.exit_reason;
    extern volatile uint32_t scd_trace_mailbox[];
    scd_trace_mailbox[0]=0x46454e44;scd_trace_mailbox[1]=fe_coming_qa.frames;scd_trace_mailbox[2]=SCD_FE_COMING|hold<<8;
    scd_trace_mailbox[3]=fe_coming_qa.phase;scd_trace_mailbox[4]=(uint32_t)fe_cm_state.shown_scroll;scd_trace_mailbox[5]=fe_coming_qa.result;
}
static void fe_cm_finish(unsigned result){
    scd_audio_stop_music();vdp2_scrn_display_set(0);vdp2_sprite_priority_set(0,4);vdp2_sprite_priority_set(1,7);
    fe_coming_qa.result=result;fe_coming_qa.phase=(result==3 || result==4)?5:6;
}
void fe_coming(unsigned prior_hold){
    memset((void *)&fe_coming_qa,0,sizeof(fe_coming_qa));fe_coming_qa.phase=1;scd_audio_stop_music();scd_low_packs_lost=1;
    const cdfs_filelist_t *root=scd_cd_root_read();uint8_t *data=(uint8_t *)fe_cm_load;unsigned bytes=0,matches=0;int loaded=-1;
    if(root)for(unsigned i=0;i<root->entries_count;i++)if(!strcmp(root->entries[i].name,"COMING.BIN")){
        matches++;bytes=root->entries[i].size;
        if(bytes>=fe_cm_header && bytes<=fe_cm_max && !(bytes&2047))loaded=cd_block_sectors_read(root->entries[i].starting_fad,data,bytes);
    }
    if(!matches){fe_cm_finish(1);return;}
    if(matches!=1 || loaded || !fe_coming_pack_valid(data,bytes)){fe_cm_finish(2);return;}
    uint16_t colours[64];for(unsigned i=0;i<64;i++)colours[i]=fe_cm_be16(data+32+i*2);
    fe_coming_begin(&fe_cm_state,colours,prior_hold);fe_coming_qa.load_ok=1;fe_coming_qa.pack_bytes=bytes;fe_coming_qa.tiles=150;
    const uint8_t *art=data+32+128,*source=art+fe_cm_art;
    vdp2_scrn_display_set(0);for(unsigned i=0;i<8;i++)vdp2_sprite_priority_set(i,0);
    const vdp2_vram_usage_t usage={0};vdp2_vram_usage_set(&usage);
    vdp2_vram_cycp_t cycles;memset(&cycles,0xff,sizeof(cycles));cycles.pt[0].t0=cycles.pt[0].t1=VDP2_VRAM_CYCP_PNDR_NBG0;cycles.pt[0].t4=VDP2_VRAM_CYCP_CHPNDR_NBG0;vdp2_vram_cycp_set(&cycles);
    memset((void *)VDP2_VRAM_ADDR(0,0),0,0x18000);memcpy((void *)VDP2_VRAM_ADDR(0,0),art,fe_cm_art);
    const vdp2_scrn_cell_format_t fmt={.scroll_screen=VDP2_SCRN_NBG0,.ccc=VDP2_SCRN_CCC_PALETTE_16,.char_size=VDP2_SCRN_CHAR_SIZE_1X1,.pnd_size=2,.aux_mode=0,.plane_size=VDP2_SCRN_PLANE_SIZE_1X1,.cpd_base=VDP2_VRAM_ADDR(0,0),.palette_base=VDP2_CRAM_MODE_0_OFFSET(0,0,0)};
    vdp2_vram_t a=VDP2_VRAM_ADDR(0,0x10000),b=VDP2_VRAM_ADDR(0,0x14000);const vdp2_scrn_normal_map_t map={.plane_a=a,.plane_b=b,.plane_c=a,.plane_d=b};
    vdp2_scrn_cell_format_set(&fmt,&map);vdp2_scrn_priority_set(VDP2_SCRN_NBG0,2);
    vdp2_scrn_sf_set(VDP2_SCRN_NBG0,VDP2_SCRN_SF_MODE_1,VDP2_SCRN_SF_TYPE_CELL_PRIORITY,VDP2_SCRN_SF_CODE_A);
    const vdp2_scrn_ls_format_t ls={.scroll_screen=VDP2_SCRN_NBG0};vdp2_scrn_ls_set(&ls);vdp2_scrn_scroll_y_set(VDP2_SCRN_NBG0,0);
    vdp2_scrn_reduction_set(VDP2_SCRN_NBG0,VDP2_SCRN_REDUCTION_NONE);vdp2_scrn_reduction_x_set(VDP2_SCRN_NBG0,0x10000);
    for(unsigned y=0;y<32;y++)for(unsigned x=0;x<128;x++){
        volatile uint32_t *dest=(volatile uint32_t *)(x<64?a:b);dest[y*64+(x&63)]=stage_saturn_pnd(fe_cm_be16(source+(y*128+x)*2),0);
    }
    scd_audio_music_loop(0,6);fe_coming_qa.music_started=1;
    vdp2_scrn_display_set(VDP2_SCRN_DISPTP_NBG0);fe_coming_qa.phase=2;fe_cm_frame();
    fe_coming_qa.phase=3;while(!fe_cm_state.exit_reason)fe_cm_frame();
    scd_audio_cdda_fade(0x20);fe_coming_qa.fade_requested=0x20;fe_coming_qa.phase=4;
    while(fe_coming_fade(&fe_cm_state)){fe_cm_frame();fe_coming_qa.fade_out++;}
    fe_cm_finish(fe_cm_state.exit_reason==0x100?4:3);
}
#endif
