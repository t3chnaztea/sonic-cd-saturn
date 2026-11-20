/* Special Stage 8 credits (Title Screen/Secrets/Special Stage 8 Credits.asm,
   SPEEND.MMD; IPX.asm SoundTest_SpecStg8 runs it after a won Stage 8).
   Front-end overlay code (fe_ names, src/saturn.x .zone_R0), reached only through
   fe_special_zone_ops.credits (src/special_modes.h). The Mega Drive H40 screen maps
   one to one onto VDP2: plane A (text) on NBG0, plane B (background) on NBG1, the
   Nemesis art as 4-bit cells, the palette in CRAM lines 0-3 (cd/SS8CRED.BIN,
   tools/ss8_credits_assets.py). VDP1 stays hidden. */
#include <yaul.h>
#include <string.h>
#include "audio.h"
#include "cd_root.h"
#include "stage.h"
#include "special_modes.h"
enum {FE_S8C_LOAD=0x002F0000,FE_S8C_MAX=0xA000};
static void fe_s8c_vsync(void){vdp2_sync();vdp2_sync_wait();scd_audio_update();}
static void fe_s8c_cram(const uint16_t *palette){
    volatile uint16_t *cram=(volatile uint16_t *)VDP2_CRAM_MODE_0_OFFSET(0,0,0);
    for(unsigned i=0;i<64;i++){
        unsigned c=palette[i];
        cram[i]=(uint16_t)(0x8000|((c>>1)&7)*31/7|(((c>>5)&7)*31/7)<<5|(((c>>9)&7)*31/7)<<10);
    }
    /* Register 7: background color line 0 color 0. */
    vdp2_scrn_back_color_set(VDP2_VRAM_ADDR(3,0x1bffe),(rgb1555_t){.raw=cram[0]});
}
/* One channel step (Functions.asm .FadeColorChannel): channel units for red, green,
   blue; from white the channel is capped at d0 below the target, to black d0 is
   subtracted with a floor of 0. */
static void fe_s8c_step(uint16_t *palette,const uint16_t *target,unsigned step,int to_black){
    static const uint16_t fe_s8c_unit[3]={1,16,256};
    unsigned u=fe_s8c_unit[step/8],mask=0xe*u,d0=(to_black?2*(step%8):14-2*(step%8))*u;
    for(unsigned i=0;i<64;i++){
        unsigned c=palette[i],channel;
        if(to_black){channel=c&mask;channel=channel>d0?channel-d0:0;}
        else{channel=target[i]&mask;if(channel<d0)channel=d0;}
        palette[i]=(uint16_t)((c&~mask)|channel);
    }
    fe_s8c_cram(palette);fe_s8c_vsync();
}
/* Returns 0 after Start and the fade to black, -1 when the pack is missing. */
__attribute__((noipa)) int fe_ss8_credits_run(void){
    uint8_t *data=(uint8_t *)FE_S8C_LOAD;
    const cdfs_filelist_t *root=scd_cd_root_read();int loaded=-1;
    for(unsigned i=0;i<root->entries_count;i++)
        if(!strcmp(root->entries[i].name,"SS8CRED.BIN") && root->entries[i].size<=FE_S8C_MAX)
            loaded=cd_block_sectors_read(root->entries[i].starting_fad,data,root->entries[i].size);
    if(loaded || memcmp(data,"S8C1",4))return -1;
    const unsigned tiles=(unsigned)data[4]<<8|data[5];
    const uint8_t *pal=data+6,*art=pal+128,*plane_a=art+tiles*32,*plane_b=plane_a+4096;
    vdp2_scrn_display_set(0);
    for(unsigned i=0;i<8;i++)vdp2_sprite_priority_set(i,0);
    const vdp2_vram_usage_t usage={0};vdp2_vram_usage_set(&usage);
    vdp2_vram_cycp_t cycles;memset(&cycles,0xff,sizeof(cycles));
    cycles.pt[0].t0=cycles.pt[0].t1=VDP2_VRAM_CYCP_PNDR_NBG0;cycles.pt[0].t2=cycles.pt[0].t3=VDP2_VRAM_CYCP_PNDR_NBG1;
    cycles.pt[0].t4=VDP2_VRAM_CYCP_CHPNDR_NBG0;cycles.pt[0].t5=VDP2_VRAM_CYCP_CHPNDR_NBG1;
    vdp2_vram_cycp_set(&cycles);
    memset((void *)VDP2_VRAM_ADDR(0,0),0,0x18000);
    memcpy((void *)VDP2_VRAM_ADDR(0,0),art,tiles*32);
    for(unsigned i=0;i<2;i++){
        vdp2_scrn_t screen=i?VDP2_SCRN_NBG1:VDP2_SCRN_NBG0;
        const vdp2_scrn_cell_format_t fmt={.scroll_screen=screen,.ccc=VDP2_SCRN_CCC_PALETTE_16,.char_size=VDP2_SCRN_CHAR_SIZE_1X1,.pnd_size=2,.aux_mode=0,
            .plane_size=VDP2_SCRN_PLANE_SIZE_1X1,.cpd_base=VDP2_VRAM_ADDR(0,0),.palette_base=VDP2_CRAM_MODE_0_OFFSET(0,0,0)};
        vdp2_vram_t base=VDP2_VRAM_ADDR(0,i?0x14000:0x10000);
        const vdp2_scrn_normal_map_t map={.plane_a=base,.plane_b=base,.plane_c=base,.plane_d=base};
        vdp2_scrn_cell_format_set(&fmt,&map);
        /* Equal base priority keeps plane A over plane B; the cell bit raises high tiles. */
        vdp2_scrn_priority_set(screen,2);
        vdp2_scrn_sf_set(screen,VDP2_SCRN_SF_MODE_1,VDP2_SCRN_SF_TYPE_CELL_PRIORITY,VDP2_SCRN_SF_CODE_A);
        const vdp2_scrn_ls_format_t ls={.scroll_screen=screen};vdp2_scrn_ls_set(&ls);
        vdp2_scrn_scroll_x_set(screen,0);vdp2_scrn_scroll_y_set(screen,0);
        const uint8_t *plane=i?plane_b:plane_a;volatile uint32_t *out=(volatile uint32_t *)base;
        for(unsigned n=0;n<2048;n++)out[n]=stage_saturn_pnd((uint16_t)(plane[n*2]<<8|plane[n*2+1]),0);
    }
    /* Start: palette, PrepFadeFromWhite, VSync, FadeFromWhite (24 VSyncs). */
    uint16_t target[64],palette[64];
    for(unsigned i=0;i<64;i++){target[i]=(uint16_t)(pal[i*2]<<8|pal[i*2+1]);palette[i]=0xeee;}
    fe_s8c_cram(palette);
    vdp2_scrn_display_set(VDP2_SCRN_DISPTP_NBG0|VDP2_SCRN_DISPTP_NBG1);fe_s8c_vsync();
    for(unsigned step=0;step<24;step++)fe_s8c_step(palette,target,step,0);
    /* MainLoop: VSync until ctrlHold has Start, then FadeToBlack. */
    for(;;){
        fe_s8c_vsync();
        smpc_peripheral_digital_t pad;smpc_peripheral_process();smpc_peripheral_digital_port(1,&pad);
        if(pad.pressed.button.start)break; /* Yaul's pressed is the current level. */
    }
    for(unsigned step=0;step<24;step++)fe_s8c_step(palette,target,step,1);
    vdp2_scrn_display_set(0);
    return 0;
}
