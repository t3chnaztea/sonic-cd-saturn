/* Source: Stage Select.asm and IPX.asm StageSels. All target helpers carry fe_.
   Host builds only expose the unchanged selection model/table, never hardware. */
#include "stage_select.h"
const fe_stage_select_choice fe_stage_select_choices[FE_SEL_COUNT]
#ifndef SCD_STAGE_SELECT_HOST
__attribute__((section(".rodata.fe_stage_select_choices")))
#endif
={
    {FE_SEL_NORMAL,0,0,0}, /* 0 1-1-A */
    {FE_SEL_NORMAL,0,0,1}, /* 1 1-1-B */
    {FE_SEL_NORMAL,0,0,2}, /* 2 1-1-C */
    {FE_SEL_NORMAL,0,0,3}, /* 3 1-1-D */
    {FE_SEL_NORMAL,0,1,0}, /* 4 1-2-A */
    {FE_SEL_NORMAL,0,1,1}, /* 5 1-2-B */
    {FE_SEL_NORMAL,0,1,2}, /* 6 1-2-C */
    {FE_SEL_NORMAL,0,1,3}, /* 7 1-2-D */
    {FE_SEL_WARP,0,0,1}, /* 8 WARP */
    {FE_SEL_OPENING,0,0,1}, /* 9 OPENING */
    {FE_SEL_COMMING,0,0,1}, /* 10 COMMING */
    {FE_SEL_NORMAL,1,0,0}, /* 11 3-1-A */
    {FE_SEL_NORMAL,1,0,1}, /* 12 3-1-B */
    {FE_SEL_NORMAL,1,0,2}, /* 13 3-1-C */
    {FE_SEL_NORMAL,1,0,3}, /* 14 3-1-D */
    {FE_SEL_NORMAL,1,1,0}, /* 15 3-2-A */
    {FE_SEL_NORMAL,1,1,1}, /* 16 3-2-B */
    {FE_SEL_NORMAL,1,1,2}, /* 17 3-2-C */
    {FE_SEL_NORMAL,1,1,3}, /* 18 3-2-D */
    {FE_SEL_NORMAL,1,2,2}, /* 19 3-3-C */
    {FE_SEL_NORMAL,1,2,3}, /* 20 3-3-D */
    {FE_SEL_NORMAL,0,2,2}, /* 21 1-3-C */
    {FE_SEL_NORMAL,0,2,3}, /* 22 1-3-D */
    {FE_SEL_NORMAL,2,0,0}, /* 23 4-1-A */
    {FE_SEL_NORMAL,2,0,1}, /* 24 4-1-B */
    {FE_SEL_NORMAL,2,0,2}, /* 25 4-1-C */
    {FE_SEL_NORMAL,2,0,3}, /* 26 4-1-D */
    {FE_SEL_NORMAL,2,1,0}, /* 27 4-2-A */
    {FE_SEL_NORMAL,2,1,1}, /* 28 4-2-B */
    {FE_SEL_NORMAL,2,1,2}, /* 29 4-2-C */
    {FE_SEL_NORMAL,2,1,3}, /* 30 4-2-D */
    {FE_SEL_NORMAL,2,2,2}, /* 31 4-3-C */
    {FE_SEL_NORMAL,2,2,3}, /* 32 4-3-D */
    {FE_SEL_NORMAL,3,0,0}, /* 33 5-1-A */
    {FE_SEL_NORMAL,3,0,1}, /* 34 5-1-B */
    {FE_SEL_NORMAL,3,0,2}, /* 35 5-1-C */
    {FE_SEL_NORMAL,3,0,3}, /* 36 5-1-D */
    {FE_SEL_NORMAL,3,1,0}, /* 37 5-2-A */
    {FE_SEL_NORMAL,3,1,1}, /* 38 5-2-B */
    {FE_SEL_NORMAL,3,1,2}, /* 39 5-2-C */
    {FE_SEL_NORMAL,3,1,3}, /* 40 5-2-D */
    {FE_SEL_NORMAL,3,2,2}, /* 41 5-3-C */
    {FE_SEL_NORMAL,3,2,3}, /* 42 5-3-D */
    {FE_SEL_NORMAL,4,0,0}, /* 43 6-1-A */
    {FE_SEL_NORMAL,4,0,1}, /* 44 6-1-B */
    {FE_SEL_NORMAL,4,0,2}, /* 45 6-1-C */
    {FE_SEL_NORMAL,4,0,3}, /* 46 6-1-D */
    {FE_SEL_NORMAL,4,1,0}, /* 47 6-2-A */
    {FE_SEL_NORMAL,4,1,1}, /* 48 6-2-B */
    {FE_SEL_NORMAL,4,1,2}, /* 49 6-2-C */
    {FE_SEL_NORMAL,4,1,3}, /* 50 6-2-D */
    {FE_SEL_NORMAL,4,2,2}, /* 51 6-3-C */
    {FE_SEL_NORMAL,4,2,3}, /* 52 6-3-D */
    {FE_SEL_NORMAL,5,0,0}, /* 53 7-1-A */
    {FE_SEL_NORMAL,5,0,1}, /* 54 7-1-B */
    {FE_SEL_NORMAL,5,0,2}, /* 55 7-1-C */
    {FE_SEL_NORMAL,5,0,3}, /* 56 7-1-D */
    {FE_SEL_NORMAL,5,1,0}, /* 57 7-2-A */
    {FE_SEL_NORMAL,5,1,1}, /* 58 7-2-B */
    {FE_SEL_NORMAL,5,1,2}, /* 59 7-2-C */
    {FE_SEL_NORMAL,5,1,3}, /* 60 7-2-D */
    {FE_SEL_NORMAL,5,2,2}, /* 61 7-3-C */
    {FE_SEL_NORMAL,5,2,3}, /* 62 7-3-D */
    {FE_SEL_NORMAL,6,0,0}, /* 63 8-1-A */
    {FE_SEL_NORMAL,6,0,1}, /* 64 8-1-B */
    {FE_SEL_NORMAL,6,0,2}, /* 65 8-1-C */
    {FE_SEL_NORMAL,6,0,3}, /* 66 8-1-D */
    {FE_SEL_NORMAL,6,1,0}, /* 67 8-2-A */
    {FE_SEL_NORMAL,6,1,1}, /* 68 8-2-B */
    {FE_SEL_NORMAL,6,1,2}, /* 69 8-2-C */
    {FE_SEL_NORMAL,6,1,3}, /* 70 8-2-D */
    {FE_SEL_NORMAL,6,2,2}, /* 71 8-3-C */
    {FE_SEL_NORMAL,6,2,3}, /* 72 8-3-D */
    {FE_SEL_SPEDEMO,0,0,1}, /* 73 SPEDEMO */
};
/* The loop moves from the PREVIOUS VSync's ctrlHold, draws, VSyncs, then checks
   the newly read hold for acceptance. Up precedes Down, including at wrap. */
void fe_stage_select_move(fe_stage_select_state *s){
    s->delay=(uint16_t)(s->delay+1);
    if(!(s->delay&7)){
        if(s->hold&1)s->selection=s->selection?s->selection-1:FE_SEL_COUNT-1;
        if(s->hold&2)s->selection=s->selection+1==FE_SEL_COUNT?0:s->selection+1;
    }
}
int fe_stage_select_input(fe_stage_select_state *s,unsigned hold){
    s->hold=(uint8_t)hold;s->accepted=(uint8_t)!!(hold&0xF0);return s->accepted;
}
#include <string.h>
enum {fe_sl_load=0x00200000,fe_sl_max=0x14000,fe_sl_header=32,fe_sl_palette=128,fe_sl_bg_words=40*28,fe_sl_text_words=40*28,fe_sl_choice_words=74*20};
static uint16_t fe_sl_be16(const uint8_t *p){return (uint16_t)((unsigned)p[0]<<8|p[1]);}
static uint32_t fe_sl_be32(const uint8_t *p){return (uint32_t)p[0]<<24|(uint32_t)p[1]<<16|(uint32_t)p[2]<<8|p[3];}
static uint32_t fe_sl_crc(const uint8_t *p,unsigned n){uint32_t crc=~0u;while(n--){crc^=*p++;for(unsigned b=0;b<8;b++)crc=(crc>>1)^(0xEDB88320u&(0u-(crc&1)));}return ~crc;}
int fe_stage_select_pack_valid(const uint8_t *p,unsigned file_size){
    if(!p || file_size<fe_sl_header || file_size>fe_sl_max || (file_size&2047) || memcmp(p,"STG1",4))return 0;
    unsigned size=fe_sl_be32(p+4),tiles=fe_sl_be32(p+8);
    if(!tiles || tiles>2048 || fe_sl_be32(p+12)!=fe_sl_bg_words || fe_sl_be32(p+16)!=fe_sl_text_words || fe_sl_be32(p+20)!=74 || fe_sl_be32(p+28)!=64)return 0;
    unsigned expected=fe_sl_header+fe_sl_palette+tiles*32+(fe_sl_bg_words+fe_sl_text_words+fe_sl_choice_words)*2;
    if(size!=expected || size>file_size || file_size-size>=2048 || fe_sl_crc(p+fe_sl_header,size-fe_sl_header)!=fe_sl_be32(p+24))return 0;
    for(unsigned i=size;i<file_size;i++)if(p[i])return 0;
    for(unsigned i=0;i<32;i++)if(p[fe_sl_header+fe_sl_palette+i])return 0;
    for(unsigned i=0;i<64;i++)if(fe_sl_be16(p+fe_sl_header+i*2)&~0xEEE)return 0;
    const uint8_t *maps=p+fe_sl_header+fe_sl_palette+tiles*32;
    for(unsigned i=0;i<fe_sl_bg_words+fe_sl_text_words+fe_sl_choice_words;i++)if((fe_sl_be16(maps+i*2)&2047)>=tiles)return 0;
    return 1;
}
#ifndef SCD_STAGE_SELECT_HOST
#include <yaul.h>
#include <string.h>
#include "frontend.h"
#include "cd_root.h"
#include "audio.h"
#include "stage.h"
#include "fmv_fe_names.h"
#include "fmv_stm.h"
volatile fe_stage_select_status fe_stage_select_qa __attribute__((section(".data.fe_stage_select_qa")));
static struct {uint16_t palette[64],target[64];const uint8_t *choices;fe_stage_select_state state;} fe_sl_ram __attribute__((section(".data.fe_sl_ram")));
static void fe_sl_selection(void){
    volatile uint32_t *map=(volatile uint32_t *)VDP2_VRAM_ADDR(0,0x10000);
    const uint8_t *p=fe_sl_ram.choices+fe_sl_ram.state.selection*40;
    for(unsigned y=0;y<2;y++)for(unsigned x=0;x<10;x++)map[(13+y)*64+14+x]=stage_saturn_pnd(fe_sl_be16(p+(y*10+x)*2),0);
}
static void fe_sl_frame(void){
    vdp2_sync();vdp2_sync_wait();scd_audio_update();
    volatile uint16_t *cram=(volatile uint16_t *)VDP2_CRAM_MODE_0_OFFSET(0,0,0);
    for(unsigned i=0;i<64;i++)cram[i]=(uint16_t)(0x8000|fmv_md_to_rgb555(fe_sl_ram.palette[i]));
    vdp2_scrn_back_color_set(VDP2_VRAM_ADDR(3,0x1bffe),(rgb1555_t){.raw=cram[0]});
    smpc_peripheral_digital_t pad;smpc_peripheral_process();smpc_peripheral_digital_port(1,&pad);
    unsigned hold=(pad.pressed.button.up?1u:0)|(pad.pressed.button.down?2u:0)|(pad.pressed.button.left?4u:0)|(pad.pressed.button.right?8u:0)|
        (pad.pressed.button.b?16u:0)|(pad.pressed.button.c?32u:0)|(pad.pressed.button.a?64u:0)|(pad.pressed.button.start?128u:0);
    fe_stage_select_input(&fe_sl_ram.state,hold);
    fe_stage_select_qa.frames++;fe_stage_select_qa.selection=fe_sl_ram.state.selection;fe_stage_select_qa.delay=fe_sl_ram.state.delay;fe_stage_select_qa.held=hold;
    extern volatile uint32_t scd_trace_mailbox[];
    scd_trace_mailbox[0]=0x46454e44;scd_trace_mailbox[1]=fe_stage_select_qa.frames;scd_trace_mailbox[2]=SCD_FE_STAGE_SELECT|hold<<8;
    scd_trace_mailbox[3]=fe_stage_select_qa.phase;scd_trace_mailbox[4]=fe_stage_select_qa.selection;scd_trace_mailbox[5]=fe_stage_select_qa.result;
}
static unsigned fe_sl_finish(unsigned result){
    vdp2_scrn_display_set(0);vdp2_sprite_priority_set(0,4);vdp2_sprite_priority_set(1,7);
    fe_stage_select_qa.result=result;fe_stage_select_qa.phase=result==3?5:6;
    return result==3?fe_sl_ram.state.selection:FE_SEL_FAILED;
}
unsigned fe_stage_select(void){
    memset((void *)&fe_stage_select_qa,0,sizeof(fe_stage_select_qa));memset(&fe_sl_ram,0,sizeof(fe_sl_ram));fe_stage_select_qa.phase=1;
    scd_audio_stop_music();scd_low_packs_lost=1;
    const cdfs_filelist_t *root=scd_cd_root_read();uint8_t *data=(uint8_t *)fe_sl_load;unsigned size=0,matches=0;int loaded=-1;
    if(root)for(unsigned i=0;i<root->entries_count;i++)if(!strcmp(root->entries[i].name,"STAGESEL.BIN")){
        matches++;size=root->entries[i].size;
        if(size>=fe_sl_header && size<=fe_sl_max && !(size&2047))loaded=cd_block_sectors_read(root->entries[i].starting_fad,data,size);
    }
    if(!matches)return fe_sl_finish(1);
    if(matches!=1 || loaded || !fe_stage_select_pack_valid(data,size))return fe_sl_finish(2);
    unsigned tiles=fe_sl_be32(data+8);const uint8_t *pal=data+fe_sl_header,*art=pal+fe_sl_palette,*bg=art+tiles*32,*text=bg+fe_sl_bg_words*2;
    fe_sl_ram.choices=text+fe_sl_text_words*2;
    fe_stage_select_qa.load_ok=1;fe_stage_select_qa.pack_bytes=size;fe_stage_select_qa.tiles=tiles;
    for(unsigned i=0;i<64;i++)fe_sl_ram.target[i]=fe_sl_be16(pal+i*2);
    vdp2_scrn_display_set(0);for(unsigned i=0;i<8;i++)vdp2_sprite_priority_set(i,0);
    const vdp2_vram_usage_t usage={0};vdp2_vram_usage_set(&usage);
    vdp2_vram_cycp_t cycles;memset(&cycles,0xff,sizeof(cycles));
    cycles.pt[0].t0=cycles.pt[0].t1=VDP2_VRAM_CYCP_PNDR_NBG0;cycles.pt[0].t2=cycles.pt[0].t3=VDP2_VRAM_CYCP_PNDR_NBG1;
    cycles.pt[0].t4=VDP2_VRAM_CYCP_CHPNDR_NBG0;cycles.pt[0].t5=VDP2_VRAM_CYCP_CHPNDR_NBG1;vdp2_vram_cycp_set(&cycles);
    memset((void *)VDP2_VRAM_ADDR(0,0),0,0x18000);memcpy((void *)VDP2_VRAM_ADDR(0,0),art,tiles*32);
    for(unsigned i=0;i<2;i++){
        vdp2_scrn_t screen=i?VDP2_SCRN_NBG1:VDP2_SCRN_NBG0;
        const vdp2_scrn_cell_format_t fmt={.scroll_screen=screen,.ccc=VDP2_SCRN_CCC_PALETTE_16,.char_size=VDP2_SCRN_CHAR_SIZE_1X1,.pnd_size=2,.aux_mode=0,.plane_size=VDP2_SCRN_PLANE_SIZE_1X1,.cpd_base=VDP2_VRAM_ADDR(0,0),.palette_base=VDP2_CRAM_MODE_0_OFFSET(0,0,0)};
        vdp2_vram_t base=VDP2_VRAM_ADDR(0,i?0x14000:0x10000);const vdp2_scrn_normal_map_t map={.plane_a=base,.plane_b=base,.plane_c=base,.plane_d=base};
        vdp2_scrn_cell_format_set(&fmt,&map);vdp2_scrn_priority_set(screen,2);
        vdp2_scrn_sf_set(screen,VDP2_SCRN_SF_MODE_1,VDP2_SCRN_SF_TYPE_CELL_PRIORITY,VDP2_SCRN_SF_CODE_A);
        const vdp2_scrn_ls_format_t ls={.scroll_screen=screen};vdp2_scrn_ls_set(&ls);vdp2_scrn_scroll_x_set(screen,0);vdp2_scrn_scroll_y_set(screen,0);
        vdp2_scrn_reduction_set(screen,VDP2_SCRN_REDUCTION_NONE);vdp2_scrn_reduction_x_set(screen,0x10000);
        volatile uint32_t *p=(volatile uint32_t *)base;const uint8_t *source=i?bg:text;
        for(unsigned y=0;y<28;y++)for(unsigned x=0;x<40;x++)p[y*64+x]=stage_saturn_pnd(fe_sl_be16(source+(y*40+x)*2),0);
    }
    vdp2_scrn_display_set(VDP2_SCRN_DISPTP_NBG0|VDP2_SCRN_DISPTP_NBG1);
    fe_stage_select_qa.phase=2;fe_sl_frame();
    for(int shift=8;shift>=0;shift-=4)for(unsigned k=0;k<8;k++){
        unsigned mask=14u<<shift;
        for(unsigned i=0;i<64;i++){unsigned target=fe_sl_ram.target[i]&mask,cap=2*k<<shift;fe_sl_ram.palette[i]=(uint16_t)((fe_sl_ram.palette[i]&~mask)|(target<cap?target:cap));}
        fe_sl_frame();fe_stage_select_qa.fade_in++;
    }
    fe_stage_select_qa.phase=3;
    do{fe_stage_select_move(&fe_sl_ram.state);fe_sl_selection();fe_sl_frame();}while(!fe_sl_ram.state.accepted);
    fe_stage_select_qa.phase=4;
    for(unsigned shift=0;shift<=8;shift+=4)for(unsigned k=0;k<8;k++){
        unsigned mask=14u<<shift,sub=2*k<<shift;
        for(unsigned i=0;i<64;i++){unsigned v=fe_sl_ram.palette[i]&mask;fe_sl_ram.palette[i]=(uint16_t)((fe_sl_ram.palette[i]&~mask)|(v<sub?0:v-sub));}
        fe_sl_frame();fe_stage_select_qa.fade_out++;
    }
    return fe_sl_finish(3);
}
#endif
