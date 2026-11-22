/* Best Staff Times.asm / Secrets/Functions.asm. Assets are derived by
   tools/staff_times_assets.py; no retail program is executed or shipped here.
   H32 fills320x224 using the existing title source step205/256, origin0.
   Actual original/full Saturn frame comparison remains required; the pack
   model alone cannot prove text-layout or display fidelity.
   All linked symbols carry fe_ and this object must retain VisualMode's no-LTO
   treatment. Root integrates the object/dependency; this module owns no menus. */
#include <yaul.h>
#include <string.h>
#include "staff_times.h"
#include "frontend.h"
#include "cd_root.h"
#include "audio.h"
#include "stage.h"
#include "fmv_fe_names.h"
#include "fmv_stm.h"
enum {fe_st_x_step=0x0000CD00,fe_st_load=0x00200000,fe_st_max=0x14000,fe_st_header=32,fe_st_palette=128,fe_st_bg_words=32*28,fe_st_text_words=32*128};
static const char fe_st_file[]="STAFFTIM.BIN";
static const uint8_t fe_st_magic[4]={'S','T','F','1'};
volatile fe_staff_times_status fe_staff_times_qa __attribute__((section(".data.fe_staff_times_qa")));
static struct {
    uint16_t palette[64],target[64];
    const uint8_t *text;
    uint8_t hold;
} fe_st_ram __attribute__((section(".data.fe_st_ram")));
static uint16_t fe_st_be16(const uint8_t *p){return (uint16_t)((unsigned)p[0]<<8|p[1]);}
static uint32_t fe_st_be32(const uint8_t *p){return (uint32_t)p[0]<<24|(uint32_t)p[1]<<16|(uint32_t)p[2]<<8|p[3];}
static uint32_t fe_st_crc(const uint8_t *p,unsigned n){
    uint32_t crc=~0u;
    while(n--){crc^=*p++;for(unsigned b=0;b<8;b++)crc=(crc>>1)^(0xEDB88320u&(0u-(crc&1)));}
    return ~crc;
}
/* Strict layout: STF1,u32 logical bytes,tiles,bg words,text words,records,CRC32,
   palette words; then64 MD colours, tile bytes,896 BG words,4096 text words.
   Sector padding must be zero. Art never overlaps either VDP2 pattern map. */
static int fe_st_valid(const uint8_t *p,unsigned file_size){
    if(file_size<fe_st_header || file_size>fe_st_max || (file_size&2047) || memcmp(p,fe_st_magic,4))return 0;
    unsigned size=fe_st_be32(p+4),tiles=fe_st_be32(p+8);
    if(!tiles || tiles>2048 || fe_st_be32(p+12)!=fe_st_bg_words || fe_st_be32(p+16)!=fe_st_text_words ||
       fe_st_be32(p+20)!=28 || fe_st_be32(p+28)!=64)return 0;
    unsigned expected=fe_st_header+fe_st_palette+tiles*32+(fe_st_bg_words+fe_st_text_words)*2;
    if(size!=expected || size>file_size || file_size-size>=2048 || fe_st_crc(p+fe_st_header,size-fe_st_header)!=fe_st_be32(p+24))return 0;
    for(unsigned i=size;i<file_size;i++)if(p[i])return 0;
    /* Tile0 is the source space/transparent border, never substitute HUD art. */
    for(unsigned i=0;i<32;i++)if(p[fe_st_header+fe_st_palette+i])return 0;
    for(unsigned i=0;i<64;i++)if(fe_st_be16(p+fe_st_header+i*2)&~0xEEE)return 0;
    const uint8_t *maps=p+fe_st_header+fe_st_palette+tiles*32;
    for(unsigned i=0;i<fe_st_bg_words+fe_st_text_words;i++)if((fe_st_be16(maps+i*2)&2047)>=tiles)return 0;
    return 1;
}
/* Original VInterrupt: publish palette/scroll, then read held input. */
static void fe_st_frame(void){
    vdp2_sync();vdp2_sync_wait();scd_audio_update();
    volatile uint16_t *cram=(volatile uint16_t *)VDP2_CRAM_MODE_0_OFFSET(0,0,0);
    for(unsigned i=0;i<64;i++)cram[i]=(uint16_t)(0x8000|fmv_md_to_rgb555(fe_st_ram.palette[i]));
    vdp2_scrn_back_color_set(VDP2_VRAM_ADDR(3,0x1bffe),(rgb1555_t){.raw=cram[0]});
    volatile uint32_t *map=(volatile uint32_t *)VDP2_VRAM_ADDR(0,0x10000);
    unsigned row=fe_staff_times_qa.scroll>>3;
    for(unsigned y=0;y<29;y++)for(unsigned x=0;x<32;x++)
        map[y*64+x]=stage_saturn_pnd(fe_st_be16(fe_st_ram.text+((row+y)*32+x)*2),0);
    vdp2_scrn_scroll_y_set(VDP2_SCRN_NBG0,fix16_int32_from(fe_staff_times_qa.scroll&7));
    smpc_peripheral_digital_t pad;smpc_peripheral_process();smpc_peripheral_digital_port(1,&pad);
    fe_st_ram.hold=(uint8_t)((pad.pressed.button.up?SCD_PAD_UP:0)|(pad.pressed.button.down?SCD_PAD_DOWN:0)|(pad.pressed.button.start?SCD_PAD_START:0));
    fe_staff_times_qa.frames++;
    extern volatile uint32_t scd_trace_mailbox[];
    scd_trace_mailbox[0]=0x46454e44;scd_trace_mailbox[1]=fe_staff_times_qa.frames;
    scd_trace_mailbox[2]=SCD_FE_STAFF_TIMES|(uint32_t)fe_st_ram.hold<<8;
    scd_trace_mailbox[3]=fe_staff_times_qa.phase;scd_trace_mailbox[4]=fe_staff_times_qa.scroll;scd_trace_mailbox[5]=fe_staff_times_qa.result;
}
static void fe_st_finish(unsigned result){
    scd_audio_stop_music();vdp2_scrn_display_set(0);
    vdp2_sprite_priority_set(0,4);vdp2_sprite_priority_set(1,7);
    fe_staff_times_qa.result=result;
    fe_staff_times_qa.phase=result==fe_staff_start_exit?fe_staff_finished:fe_staff_failed;
}
void fe_staff_times(void){
    memset((void *)&fe_staff_times_qa,0,sizeof(fe_staff_times_qa));
    memset(&fe_st_ram,0,sizeof(fe_st_ram));fe_staff_times_qa.phase=fe_staff_loading;
    scd_audio_stop_music(); /* CD data read must precede repeating Shoes. No bank load. */
    const cdfs_filelist_t *root=scd_cd_root_read();uint8_t *data=(uint8_t *)fe_st_load;
    unsigned size=0,matches=0;int loaded=-1;scd_low_packs_lost=1;
    if(root)for(unsigned i=0;i<root->entries_count;i++)if(!strcmp(root->entries[i].name,fe_st_file)){
        matches++;size=root->entries[i].size;
        if(size>=fe_st_header && size<=fe_st_max && !(size&2047))loaded=cd_block_sectors_read(root->entries[i].starting_fad,data,size);
    }
    if(!matches){fe_st_finish(fe_staff_missing);return;}
    if(matches!=1 || loaded || !fe_st_valid(data,size)){fe_st_finish(fe_staff_invalid);return;}
    unsigned tiles=fe_st_be32(data+8);const uint8_t *pal=data+fe_st_header,*art=pal+fe_st_palette,*bg=art+tiles*32;
    fe_st_ram.text=bg+fe_st_bg_words*2;
    fe_staff_times_qa.load_ok=1;fe_staff_times_qa.pack_bytes=size;fe_staff_times_qa.tiles=tiles;
    for(unsigned i=0;i<64;i++)fe_st_ram.target[i]=fe_st_be16(pal+i*2);
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
        /* title_end resets1: explicitly install the reviewed H32 title grid. */
        vdp2_scrn_reduction_set(screen,VDP2_SCRN_REDUCTION_NONE);vdp2_scrn_reduction_x_set(screen,fe_st_x_step);
    }
    volatile uint32_t *map=(volatile uint32_t *)VDP2_VRAM_ADDR(0,0x14000);
    for(unsigned y=0;y<28;y++)for(unsigned x=0;x<32;x++)map[y*64+x]=stage_saturn_pnd(fe_st_be16(bg+(y*32+x)*2),0);
    scd_audio_music_loop(0,5);fe_staff_times_qa.music_started=1;
    vdp2_scrn_display_set(VDP2_SCRN_DISPTP_NBG0|VDP2_SCRN_DISPTP_NBG1);
    fe_staff_times_qa.phase=fe_staff_fading_in;fe_st_frame(); /* PrepFadeFromBlack VSync. */
    for(int shift=8;shift>=0;shift-=4)for(unsigned k=0;k<8;k++){
        unsigned mask=14u<<shift;
        for(unsigned i=0;i<64;i++){unsigned target=fe_st_ram.target[i]&mask,cap=2*k<<shift;fe_st_ram.palette[i]=(uint16_t)((fe_st_ram.palette[i]&~mask)|(target<cap?target:cap));}
        fe_st_frame();fe_staff_times_qa.fade_in++;
    }
    fe_staff_times_qa.phase=fe_staff_screen;
    do{
        unsigned scroll=fe_staff_times_qa.scroll;
        if(fe_st_ram.hold&SCD_PAD_DOWN){scroll+=2;if(scroll>=512)scroll=511;}
        if(fe_st_ram.hold&SCD_PAD_UP)scroll=scroll<2?0:scroll-2;
        fe_staff_times_qa.scroll=scroll;fe_st_frame();
    }while(!(fe_st_ram.hold&SCD_PAD_START));
    fe_staff_times_qa.start_exit=1;fe_staff_times_qa.phase=fe_staff_fading_out;
    for(unsigned shift=0;shift<=8;shift+=4)for(unsigned k=0;k<8;k++){
        unsigned mask=14u<<shift,sub=2*k<<shift;
        for(unsigned i=0;i<64;i++){unsigned v=fe_st_ram.palette[i]&mask;fe_st_ram.palette[i]=(uint16_t)((fe_st_ram.palette[i]&~mask)|(v<sub?0:v-sub));}
        fe_st_frame();fe_staff_times_qa.fade_out++;
    }
    fe_st_finish(fe_staff_start_exit); /* title_begin(1) reloads its own scene/music. */
}
