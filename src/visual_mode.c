/* Visual Mode (Visual Mode/Main.asm, the retail VM____.MMD; IPX.asm VisualMode 1123-1200).
   Front-end overlay code (fe_ names, src/saturn.x .zone_R0), reached only through
   fe_frontend_zone_ops (src/frontend.c). The Mega Drive H40 screen maps one to one onto
   VDP2: plane A (the background) on NBG1; the five option sprites, which sit on 8-pixel
   cells and never overlap, on NBG0 above it; the Nemesis art as 4-bit cells at the
   Mega Drive tile numbers; the palette in CRAM lines 0-3 (cd/VISMODE.BIN,
   tools/visual_mode_assets.py). VDP1 stays hidden. The menu program runs again after
   every movie, as RunMMD(SCMD_VISMODE) does. */
#include <yaul.h>
#include <string.h>
#include "audio.h"
#include "cd_root.h"
#include "stage.h"
#include "frontend.h"
#include "fmv_fe_names.h"
#include "fmv_stm.h"
#include "visual_mode.h"

/* cd/VISMODE.BIN goes where the movies go (stage packs PPZ0-PPZ2, scd_low_packs_lost). */
enum {FE_VM_LOAD=0x00200000, FE_VM_MAX=0xC000, FE_VM_TILES_AT=134};
/* A movie that fails (fmv_play < 0) plays again (IPX.asm: loop while mmdReturnCode is
   negative); a file that is missing fails every time, so the port stops after three. */
enum {FE_VM_TRIES=3};
extern volatile uint32_t scd_trace_mailbox[];

/* Harness view (tools/test_frontend_emulator.py visual-mode): phase 1 loading, 2 fade in,
   3 menu, 4 fade out, 5 movie, 6 "Thank You", 0 left for the title. */
static struct {
    uint32_t phase,frames,sel,menus,fade_in,fade_out,movie,result,thanks;
} fe_vm __attribute__((section(".data.fe_vm")));
/* Program variables (Main.asm): ctrlHold/ctrlTap, buttonFlags, menuSelection, palette. */
static struct {
    uint8_t hold,tap,flags,shown;
    int16_t sel;
    uint16_t palette[64],target[64];
    const uint8_t *layer;
} fe_vm_ram __attribute__((section(".data.fe_vm_ram")));

static uint16_t fe_vm_be16(const uint8_t *p){return (uint16_t)(p[0]<<8|p[1]);}

/* V-INT: the palette (DMA68K palette) and the option sprites (DMA68K sprites), shown
   from the last frame's values; then ReadController (tapped = pressed now, not before). */
static void fe_vm_frame(void){
    vdp2_sync();vdp2_sync_wait();scd_audio_update();
    volatile uint16_t *cram=(volatile uint16_t *)VDP2_CRAM_MODE_0_OFFSET(0,0,0);
    for(unsigned i=0;i<64;i++)cram[i]=(uint16_t)(0x8000|fmv_md_to_rgb555(fe_vm_ram.palette[i]));
    /* Register 7: background color line 0 color 0. */
    vdp2_scrn_back_color_set(VDP2_VRAM_ADDR(3,0x1bffe),(rgb1555_t){.raw=cram[0]});
    /* ObjExit..ObjPencilTest: tile $2461 (line 1) when selected, $461 otherwise. The sprite
       table stays empty until the first MainLoop frame. Option n owns rows 14+2n, 15+2n. */
    volatile uint32_t *out=(volatile uint32_t *)VDP2_VRAM_ADDR(0,0x10000);
    if(fe_vm_ram.layer)for(unsigned y=14;y<24;y++)for(unsigned x=0;x<40;x++){
        uint16_t w=fe_vm_be16(fe_vm_ram.layer+(y*40+x)*2);
        if(!w)continue;
        if((int)(y/2-7)==fe_vm_ram.sel)w|=0x2000;
        out[y*64+x]=fe_vm_ram.shown?stage_saturn_pnd(w,0):0;
    }
    smpc_peripheral_digital_t pad;smpc_peripheral_process();smpc_peripheral_digital_port(1,&pad);
    /* Yaul's pressed is the current level; Mega Drive bits U D L R B C A Start. */
    const uint8_t now=(uint8_t)((pad.pressed.button.up?SCD_PAD_UP:0)|(pad.pressed.button.down?SCD_PAD_DOWN:0)|
        (pad.pressed.button.left?SCD_PAD_LEFT:0)|(pad.pressed.button.right?SCD_PAD_RIGHT:0)|
        (pad.pressed.button.b?SCD_PAD_B:0)|(pad.pressed.button.c?SCD_PAD_C:0)|
        (pad.pressed.button.a?SCD_PAD_A:0)|(pad.pressed.button.start?SCD_PAD_START:0));
    fe_vm_ram.tap=now&(uint8_t)~fe_vm_ram.hold;fe_vm_ram.hold=now;
    fe_vm.frames++;fe_vm.sel=(uint32_t)fe_vm_ram.sel;
    /* 'FEND', the frame, screen 3 | hold << 8 | selection << 16 (as src/frontend_view.inc). */
    scd_trace_mailbox[0]=0x46454e44;scd_trace_mailbox[1]=fe_vm.frames;
    scd_trace_mailbox[2]=SCD_FE_VISUAL|(uint32_t)fe_vm_ram.hold<<8|(uint32_t)fe_vm_ram.sel<<16;
}

/* FadeColorFromBlack: blue, then green, then red, one Mega Drive step each frame. */
static uint16_t fe_vm_from_black(uint16_t c,uint16_t target){
    if(c==target)return c;
    if((uint16_t)(c+0x200)<=target)return (uint16_t)(c+0x200);
    if((uint16_t)(c+0x20)<=target)return (uint16_t)(c+0x20);
    return (uint16_t)(c+2);
}
/* FadeColorToBlack: red, then green, then blue. */
static uint16_t fe_vm_to_black(uint16_t c){
    if(c&0xE)return (uint16_t)(c-2);
    if(c&0xE0)return (uint16_t)(c-0x20);
    if(c&0xE00)return (uint16_t)(c-0x200);
    return c;
}

/* UpdateSelection: Start, A, B or C picks the selection; Up or Right moves up and Down
   or Left down when the button is released, wrapping over the five options. */
static int fe_vm_update(void){
    const uint8_t tap=fe_vm_ram.tap,hold=fe_vm_ram.hold;
    if(tap&(SCD_PAD_START|SCD_PAD_A|SCD_PAD_B|SCD_PAD_C))return 1;
    static const uint8_t fe_vm_dirs[4]={SCD_PAD_UP,SCD_PAD_DOWN,SCD_PAD_RIGHT,SCD_PAD_LEFT};
    for(unsigned i=0;i<4;i++){
        const uint8_t bit=fe_vm_dirs[i];
        if(hold&bit){fe_vm_ram.flags|=bit;continue;}
        if(!(fe_vm_ram.flags&bit))continue;
        fe_vm_ram.flags&=(uint8_t)~bit;
        if(i&1){if(++fe_vm_ram.sel>4)fe_vm_ram.sel=0;}
        else if(--fe_vm_ram.sel<0)fe_vm_ram.sel=4;
    }
    return 0;
}

/* One run of the menu program; returns menuSelection, or -1 without cd/VISMODE.BIN. */
static int fe_vm_menu(void){
    fe_vm.phase=1;
    uint8_t *data=(uint8_t *)FE_VM_LOAD;
    const cdfs_filelist_t *root=scd_cd_root_read();int loaded=-1;
    scd_low_packs_lost=1;
    for(unsigned i=0;i<root->entries_count;i++)
        if(!strcmp(root->entries[i].name,"VISMODE.BIN") && root->entries[i].size<=FE_VM_MAX)
            loaded=cd_block_sectors_read(root->entries[i].starting_fad,data,root->entries[i].size);
    if(loaded || memcmp(data,"VMS1",4))return -1;
    const unsigned tiles=fe_vm_be16(data+4);
    const uint8_t *pal=data+6,*art=data+FE_VM_TILES_AT,*plane=art+tiles*32;
    /* Start: clear the variables; ctrlData $8000 (a held Start is not a tap). */
    memset(&fe_vm_ram,0,sizeof(fe_vm_ram));
    fe_vm_ram.hold=SCD_PAD_START;fe_vm_ram.layer=plane+1120*2;
    vdp2_scrn_display_set(0);
    for(unsigned i=0;i<8;i++)vdp2_sprite_priority_set(i,0);
    const vdp2_vram_usage_t usage={0};vdp2_vram_usage_set(&usage);
    vdp2_vram_cycp_t cycles;memset(&cycles,0xff,sizeof(cycles));
    cycles.pt[0].t0=cycles.pt[0].t1=VDP2_VRAM_CYCP_PNDR_NBG0;cycles.pt[0].t2=cycles.pt[0].t3=VDP2_VRAM_CYCP_PNDR_NBG1;
    cycles.pt[0].t4=VDP2_VRAM_CYCP_CHPNDR_NBG0;cycles.pt[0].t5=VDP2_VRAM_CYCP_CHPNDR_NBG1;
    vdp2_vram_cycp_set(&cycles);
    /* InitMD: VRAM and CRAM cleared; DrawBackground and LoadArt: tiles 1.. and $461.. */
    memset((void *)VDP2_VRAM_ADDR(0,0),0,0x18000);
    memcpy((void *)VDP2_VRAM_ADDR(0,0),art,tiles*32);
    for(unsigned i=0;i<2;i++){
        vdp2_scrn_t screen=i?VDP2_SCRN_NBG1:VDP2_SCRN_NBG0;
        const vdp2_scrn_cell_format_t fmt={.scroll_screen=screen,.ccc=VDP2_SCRN_CCC_PALETTE_16,.char_size=VDP2_SCRN_CHAR_SIZE_1X1,.pnd_size=2,.aux_mode=0,
            .plane_size=VDP2_SCRN_PLANE_SIZE_1X1,.cpd_base=VDP2_VRAM_ADDR(0,0),.palette_base=VDP2_CRAM_MODE_0_OFFSET(0,0,0)};
        vdp2_vram_t base=VDP2_VRAM_ADDR(0,i?0x14000:0x10000);
        const vdp2_scrn_normal_map_t map={.plane_a=base,.plane_b=base,.plane_c=base,.plane_d=base};
        vdp2_scrn_cell_format_set(&fmt,&map);
        /* Sprites over plane A: NBG0 wins at equal priority (no plane A tile is high). */
        vdp2_scrn_priority_set(screen,2);
        vdp2_scrn_sf_set(screen,VDP2_SCRN_SF_MODE_1,VDP2_SCRN_SF_TYPE_CELL_PRIORITY,VDP2_SCRN_SF_CODE_A);
        const vdp2_scrn_ls_format_t ls={.scroll_screen=screen};vdp2_scrn_ls_set(&ls);
        vdp2_scrn_scroll_x_set(screen,0);vdp2_scrn_scroll_y_set(screen,0);
    }
    volatile uint32_t *out=(volatile uint32_t *)VDP2_VRAM_ADDR(0,0x14000);
    for(unsigned y=0;y<28;y++)for(unsigned x=0;x<40;x++)out[y*64+x]=stage_saturn_pnd(fe_vm_be16(plane+(y*40+x)*2),0);
    for(unsigned i=0;i<64;i++)fe_vm_ram.target[i]=fe_vm_be16(pal+i*2);
    /* Display on with the palette black, then FadeFromBlack: 22 frames. */
    vdp2_scrn_display_set(VDP2_SCRN_DISPTP_NBG0|VDP2_SCRN_DISPTP_NBG1);
    fe_vm.phase=2;
    for(unsigned step=0;step<22;step++){
        fe_vm_frame();
        for(unsigned i=0;i<64;i++)fe_vm_ram.palette[i]=fe_vm_from_black(fe_vm_ram.palette[i],fe_vm_ram.target[i]);
        fe_vm.fade_in++;
    }
    /* MainLoop: UpdateSelection, UpdateObjects, VSync. */
    fe_vm.phase=3;fe_vm.menus++;
    while(!fe_vm_update()){fe_vm_ram.shown=1;fe_vm_frame();}
    /* .Exit: FadeToBlack (22 frames), the sprites as they were. */
    fe_vm.phase=4;
    for(unsigned step=0;step<22;step++){
        fe_vm_frame();
        for(unsigned i=0;i<64;i++)fe_vm_ram.palette[i]=fe_vm_to_black(fe_vm_ram.palette[i]);
        fe_vm.fade_out++;
    }
    vdp2_scrn_display_set(0);
    return fe_vm_ram.sel;
}

/* Sound Test Image.asm (NISI.MMD, DUMMY0-3.MMD): IPX.asm SoundTest exits 2-6. Art at
   tile 0, the map on plane B (NBG1 here; plane A stays tile 0, blank), the palette;
   PrepFadeFromWhite, one frame, FadeFromWhite; then VSync until Start is held;
   FadeToBlack. cd/SECRET<n>.BIN from tools/secret_images_assets.py. Harness phases
   7 fade in, 8 shown, 9 fade out; fe_vm.movie holds n. */
enum {FE_SI_TILES_AT=134,FE_SI_MAX=0x6000};
/* Functions.asm FadeFromWhite .FadeColorChannel: the channel at bit `shift` + 1 becomes
   the larger of its target and the fade intensity; the other channels stay. */
static uint16_t fe_si_from_white(uint16_t c,uint16_t target,unsigned intensity,unsigned shift){
    unsigned want=(unsigned)(target>>shift)&0xE;if(want<intensity)want=intensity;
    return (uint16_t)((c&~(0xE<<shift))|(want<<shift));
}
/* FadeToBlack .FadeColorChannel: the channel less the intensity, floored at 0. */
static uint16_t fe_si_to_black(uint16_t c,unsigned intensity,unsigned shift){
    int v=(int)((c>>shift)&0xE)-(int)intensity;if(v<0)v=0;
    return (uint16_t)((c&~(0xE<<shift))|((unsigned)v<<shift));
}
int fe_secret_image(unsigned n){
    static const char fe_si_names[5][12]={"SECRET1.BIN","SECRET2.BIN","SECRET3.BIN","SECRET4.BIN","SECRET5.BIN"};
    if(n<1 || n>5)return -1;
    memset(&fe_vm,0,sizeof(fe_vm));fe_vm.phase=7;fe_vm.movie=n;
    uint8_t *data=(uint8_t *)FE_VM_LOAD;
    const cdfs_filelist_t *root=scd_cd_root_read();int loaded=-1;
    scd_low_packs_lost=1;
    for(unsigned i=0;i<root->entries_count;i++)
        if(!strcmp(root->entries[i].name,fe_si_names[n-1]) && root->entries[i].size<=FE_SI_MAX)
            loaded=cd_block_sectors_read(root->entries[i].starting_fad,data,root->entries[i].size);
    if(loaded || memcmp(data,"SEC1",4)){fe_vm.phase=0;return -1;}
    /* The music each picture plays, started after its file loads, as SPX.asm does
       (SPCmd_LoadFunIsInf and the rest): boss, Metallic Madness Present, D.A. Garden,
       final boss, Palmtree Panic Good Future. The CD block cannot play CD-DA and read
       data at once (src/audio.c). */
    if(n==1)scd_audio_music(8);
    else if(n==2)scd_audio_stage(6,0);
    else if(n==3)scd_audio_music(13);
    else if(n==4)scd_audio_music(10);
    else scd_audio_stage(0,2);
    const unsigned tiles=fe_vm_be16(data+4);
    const uint8_t *pal=data+6,*art=data+FE_SI_TILES_AT,*plane=art+tiles*32;
    /* Start: variables cleared (ctrlHold 0 until the first V-INT reads the pad). */
    memset(&fe_vm_ram,0,sizeof(fe_vm_ram));
    vdp2_scrn_display_set(0);
    for(unsigned i=0;i<8;i++)vdp2_sprite_priority_set(i,0);
    const vdp2_vram_usage_t usage={0};vdp2_vram_usage_set(&usage);
    vdp2_vram_cycp_t cycles;memset(&cycles,0xff,sizeof(cycles));
    cycles.pt[0].t0=cycles.pt[0].t1=VDP2_VRAM_CYCP_PNDR_NBG1;cycles.pt[0].t4=VDP2_VRAM_CYCP_CHPNDR_NBG1;
    vdp2_vram_cycp_set(&cycles);
    memset((void *)VDP2_VRAM_ADDR(0,0),0,0x18000);
    memcpy((void *)VDP2_VRAM_ADDR(0,0),art,tiles*32);
    const vdp2_scrn_cell_format_t fmt={.scroll_screen=VDP2_SCRN_NBG1,.ccc=VDP2_SCRN_CCC_PALETTE_16,.char_size=VDP2_SCRN_CHAR_SIZE_1X1,.pnd_size=2,.aux_mode=0,
        .plane_size=VDP2_SCRN_PLANE_SIZE_1X1,.cpd_base=VDP2_VRAM_ADDR(0,0),.palette_base=VDP2_CRAM_MODE_0_OFFSET(0,0,0)};
    const vdp2_vram_t base=VDP2_VRAM_ADDR(0,0x14000);
    const vdp2_scrn_normal_map_t map={.plane_a=base,.plane_b=base,.plane_c=base,.plane_d=base};
    vdp2_scrn_cell_format_set(&fmt,&map);
    vdp2_scrn_priority_set(VDP2_SCRN_NBG1,2);
    const vdp2_scrn_ls_format_t ls={.scroll_screen=VDP2_SCRN_NBG1};vdp2_scrn_ls_set(&ls);
    vdp2_scrn_scroll_x_set(VDP2_SCRN_NBG1,0);vdp2_scrn_scroll_y_set(VDP2_SCRN_NBG1,0);
    volatile uint32_t *out=(volatile uint32_t *)VDP2_VRAM_ADDR(0,0x14000);
    for(unsigned y=0;y<28;y++)for(unsigned x=0;x<40;x++)out[y*64+x]=stage_saturn_pnd(fe_vm_be16(plane+(y*40+x)*2),0);
    /* PrepFadeFromWhite: the target palette aside, the palette white; one VSync. */
    for(unsigned i=0;i<64;i++){fe_vm_ram.target[i]=fe_vm_be16(pal+i*2);fe_vm_ram.palette[i]=0xEEE;}
    vdp2_scrn_display_set(VDP2_SCRN_DISPTP_NBG1);
    fe_vm_frame();
    /* FadeFromWhite: red, green, blue, intensity $E down to 0, one VSync per step. */
    for(unsigned shift=0;shift<=8;shift+=4)for(unsigned k=0;k<8;k++){
        for(unsigned i=0;i<64;i++)fe_vm_ram.palette[i]=fe_si_from_white(fe_vm_ram.palette[i],fe_vm_ram.target[i],14-2*k,shift);
        fe_vm_frame();fe_vm.fade_in++;
    }
    /* .Loop: VSync until ctrlHold has Start. */
    fe_vm.phase=8;
    do fe_vm_frame();while(!(fe_vm_ram.hold&SCD_PAD_START));
    /* FadeToBlack: red, green, blue, intensity 0 up to $E, one VSync per step. */
    fe_vm.phase=9;
    for(unsigned shift=0;shift<=8;shift+=4)for(unsigned k=0;k<8;k++){
        for(unsigned i=0;i<64;i++)fe_vm_ram.palette[i]=fe_si_to_black(fe_vm_ram.palette[i],2*k,shift);
        fe_vm_frame();fe_vm.fade_out++;
    }
    vdp2_scrn_display_set(0);
    vdp2_sprite_priority_set(0,4);vdp2_sprite_priority_set(1,7);
    fe_vm.phase=0;
    return 0;
}

/* The credits lane's "Thank You" screen replaces this. */
__attribute__((weak,noinline)) void fe_vm_thanks(void){}

void fe_visual_mode(void){
    /* The title's CD-DA track ends with the title program; Visual Mode plays none. */
    scd_audio_stop_music();
    memset(&fe_vm,0,sizeof(fe_vm));
    for(;;){
        const int sel=fe_vm_menu();
        if(sel<=0)break;
        /* .FMVs: 1 opening, 2 good ending, 3 bad ending, 4 pencil test (fmv_id_t sel-1). */
        fe_vm.phase=5;fe_vm.movie=(uint32_t)sel;
        int r;unsigned tries=0;
        do r=fe_frontend_movie((unsigned)sel-1u);while(r<0 && ++tries<FE_VM_TRIES);
        fe_vm.result=(uint32_t)r;
        if(sel==2){fe_vm.phase=6;fe_vm.thanks++;fe_vm_thanks();}
    }
    fe_vm.phase=0;
    vdp2_sprite_priority_set(0,4);vdp2_sprite_priority_set(1,7);
}
