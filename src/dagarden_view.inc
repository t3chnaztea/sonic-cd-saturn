/* D.A. Garden (src/dagarden.c) on VDP1/VDP2, included by src/main.c after title_view.inc.
   IPX.asm DAGarden (title menu exit 5): dagarden_run() plays the retail program one original
   V-INT per frame, shows the frames the retail Main CPU program misses
   (scd_dagarden_lag_frames) as repeated pictures, and returns when the program does; the
   caller then restarts the title (IPX.asm returns to the title after RunMMD).
   The Mega Drive state maps as in src/title_view.inc: plane A/B become NBG0/NBG1 cells with
   cell priority, sprites are VDP1 textures cut from the Mega Drive VRAM whose CLUTs hold
   palette codes, and the H32 picture is widened to 320 dots. The slave SH-2 renders the
   planet image (the ASIC's graphics operation) while the master runs the next V-INTs. */
#include "dagarden.h"
extern uint8_t scd_low_packs_lost;
/* [0] 'DAGD', [1] vintCounter, [2] vintRoutine | step<<8 | done<<16, [3] track (trkSelID) |
   track selection flags<<8 | time zone<<16, [4] music the program last started, [5] frames shown,
   [6] lag frames before the next V-INT, [7] state address, [8] update sequence, [9] pad of the
   last V-INT, [10] texture uploads, [11] sprites drawn, [12] planet renders, [13] slave render
   timeouts, [14..19] offsets of vram, cram, palette, objects, planet image and sprites in the
   state, [20] pack bytes read. tools/test_dagarden_emulator.py reads it. */
volatile uint32_t scd_dagarden_mailbox[24];
/* Heap block taken while D.A. Garden runs (the title's state is freed then): the program state,
   its pack table and the VDP2 state of the last V-INT, written after the next VBlank-in
   (dagarden_commit). Resident memory is kept small: the sprite texture cache, the held sprite
   table and the render job are the title view's, which is not running. */
typedef struct {
    scd_dagarden state;
    scd_dagarden_pack pack;
    struct {uint16_t cram[64],hscroll_a,vsram[2];uint32_t plane_dirty[2],tile_dirty[56];uint8_t display,valid;} shown;
} dagarden_block;
_Static_assert(sizeof(dagarden_block)<=sizeof(scd_title),"D.A. Garden must fit the title state's heap block (src/saturn.x)");
static dagarden_block *dagarden;
#define dagarden_state (&dagarden->state)
#define dagarden_pack (dagarden->pack)
#define dagarden_shown (dagarden->shown)
#define dagarden_textures title_textures
#define dagarden_texture_count title_texture_count
#define dagarden_texture_next title_texture_next
#define dagarden_sat title_sat
#define dagarden_display title_display
#define dagarden_job title_job
typedef title_texture dagarden_texture;
static unsigned dagarden_lag,dagarden_frames,dagarden_sequence,dagarden_last_pad,dagarden_uploads,dagarden_sprites,dagarden_renders,dagarden_timeouts;

/* The slave SH-2 renders each planet image while the master runs the next V-INTs, as the
   Sub CPU's ASIC does; [0] requested and [1] finished render. */
static int dagarden_master_only;
static void dagarden_slave(void){
    uint32_t generation=dagarden_job[0];
    /* A repeated notification for a job already done (render_wait) is not run again. */
    if(generation==dagarden_job[1])return;
    cpu_cache_purge();
    scd_dagarden_ops_get()->render(dagarden_state);
    dagarden_job[1]=generation;
}
static void dagarden_render_start(void *context){
    (void)context;dagarden_renders++;dagarden_job[0]++;if(!dagarden_master_only)cpu_dual_slave_notify();
}
static void dagarden_render_wait(void *context){
    (void)context;unsigned start=vblank_ticks,notified=vblank_ticks;
    /* A slave just switched on by special_slave_start may still be in its entry code
       and miss the first notification: repeat it once per V-blank, as the special
       stage does (src/special_view.inc). */
    while(!dagarden_master_only && dagarden_job[1]!=dagarden_job[0] && vblank_ticks-start<60)
        if(vblank_ticks!=notified){notified=vblank_ticks;cpu_dual_slave_notify();}
    if(dagarden_job[1]!=dagarden_job[0]){
        /* The slave is switched off before the master draws, so it cannot still be
           writing the image; the rest of this visit renders on the master. */
        if(!dagarden_master_only){dagarden_timeouts++;special_slave_stop();dagarden_master_only=1;}
        scd_dagarden_ops_get()->render(dagarden_state);dagarden_job[1]=dagarden_job[0];
    }
    cpu_cache_area_purge(dagarden_state->rendered,sizeof(dagarden_state->rendered));
}

/* Takes this V-INT's VDP state for the next commit; dirty masks accumulate over lag frames. */
static void dagarden_capture(void){
    scd_dagarden *t=dagarden_state;
    memcpy(dagarden_shown.cram,t->cram,sizeof(dagarden_shown.cram));
    dagarden_shown.hscroll_a=t->hscroll_a;dagarden_shown.vsram[0]=t->vsram[0];dagarden_shown.vsram[1]=t->vsram[1];
    for(unsigned i=0;i<2;i++){dagarden_shown.plane_dirty[i]|=t->plane_dirty[i];t->plane_dirty[i]=0;}
    for(unsigned i=0;i<56;i++){dagarden_shown.tile_dirty[i]|=t->tile_dirty[i];t->tile_dirty[i]=0;}
    dagarden_shown.display=t->display;dagarden_shown.valid=1;
}
static uint16_t dagarden_color(unsigned c){
    return (uint16_t)(0x8000|(((c>>1)&7)*31/7)|((((c>>5)&7)*31/7)<<5)|((((c>>9)&7)*31/7)<<10));
}
/* After VBlank-in: colors, scroll, name table rows and tiles of the last V-INT. */
static void dagarden_commit(void){
    if(!dagarden_shown.valid)return;
    const scd_dagarden *t=dagarden_state;dagarden_shown.valid=0;
    vdp2_scrn_back_color_set(VDP2_VRAM_ADDR(3,0x1bffe),(rgb1555_t){.raw=dagarden_color(dagarden_shown.cram[0])});
    volatile uint16_t *cram=(volatile uint16_t *)VDP2_CRAM_MODE_0_OFFSET(0,0,0);
    for(unsigned i=0;i<64;i++)cram[i]=dagarden_color(dagarden_shown.cram[i]);
    /* Full-screen scroll: plane A's H-scroll word, plane B's (always 0), VSRAM. The planes are
       256 lines tall on the Mega Drive; the 512-line VDP2 pages repeat rows 0-31 below. */
    volatile uint32_t *lines[2]={(volatile uint32_t *)VDP2_VRAM_ADDR(0,0x18000),(volatile uint32_t *)VDP2_VRAM_ADDR(0,0x18400)};
    const uint32_t xa=(uint32_t)fix16_int32_from((-(int)dagarden_shown.hscroll_a)&511);
    for(unsigned line=0;line<224;line++){lines[0][line]=xa;lines[1][line]=0;}
    vdp2_scrn_scroll_y_set(VDP2_SCRN_NBG0,fix16_int32_from(dagarden_shown.vsram[0]&255));
    vdp2_scrn_scroll_y_set(VDP2_SCRN_NBG1,fix16_int32_from(dagarden_shown.vsram[1]&255));
    for(unsigned plane=0;plane<2;plane++){
        const uint8_t *table=t->vram+(plane?0xE000:0xC000);
        volatile uint32_t *map=(volatile uint32_t *)VDP2_VRAM_ADDR(0,plane?0x14000:0x10000);
        for(unsigned row=0;row<32;row++)if(dagarden_shown.plane_dirty[plane]>>row&1)for(unsigned col=0;col<64;col++){
            uint32_t pnd=stage_saturn_pnd((uint16_t)(table[(row*64+col)*2]<<8|table[(row*64+col)*2+1]),0);
            map[row*64+col]=pnd;map[(row+32)*64+col]=pnd;
        }
    }
    for(unsigned word=0;word<56;word++)if(dagarden_shown.tile_dirty[word]){
        unsigned first=word*32,end=first+32;const uint32_t mask=dagarden_shown.tile_dirty[word];
        while(first<end && !(mask>>(first&31)&1))first++;
        while(end>first && !(mask>>((end-1)&31)&1))end--;
        memcpy((void *)VDP2_VRAM_ADDR(0,first*32),t->vram+first*32,(end-first)*32);
    }
    memset(dagarden_shown.plane_dirty,0,sizeof(dagarden_shown.plane_dirty));memset(dagarden_shown.tile_dirty,0,sizeof(dagarden_shown.tile_dirty));
}
/* Sprite textures: cached until one of their tiles is written. */
static void dagarden_textures_check(void){
    scd_dagarden *t=dagarden_state;unsigned kept=0;
    for(unsigned i=0;i<dagarden_texture_count;i++){
        const dagarden_texture *x=dagarden_textures+i;int stale=0;
        for(unsigned n=0;n<(unsigned)x->width*x->height && !stale;n++){unsigned tile=((x->tile&0x7FF)+n)&0x7FF;stale=t->sprite_dirty[tile>>5]>>(tile&31)&1;}
        if(!stale)dagarden_textures[kept++]=*x;
    }
    dagarden_texture_count=kept;memset(t->sprite_dirty,0,sizeof(t->sprite_dirty));
}
static int __attribute__((optimize("O2"))) dagarden_texture_get(unsigned tile,unsigned width,unsigned height,unsigned phase,unsigned shown_width,uint32_t *address){
    scd_dagarden *t=dagarden_state;
    for(unsigned i=0;i<dagarden_texture_count;i++)if(dagarden_textures[i].tile==tile && dagarden_textures[i].width==width && dagarden_textures[i].height==height && dagarden_textures[i].phase==phase){*address=dagarden_textures[i].address;return 0;}
    unsigned stride=(shown_width+7)&~7u,bytes=stride*height*4;
    if(dagarden_texture_count==sizeof(dagarden_textures)/sizeof(dagarden_textures[0]) || dagarden_texture_next+bytes>OBJECT_ATLAS_BASE){dagarden_texture_count=0;dagarden_texture_next=0x8100;return -1;}
    uint8_t texture[48*32/2] __aligned(4);
    scd_title_expand(texture,t->vram,tile,width,height,(scd_title_scaled_shape){0,shown_width,stride,phase});
    memcpy((void *)VDP1_VRAM(dagarden_texture_next),texture,bytes);
    dagarden_textures[dagarden_texture_count++]=(dagarden_texture){(uint16_t)tile,(uint8_t)width,(uint8_t)height,(uint8_t)phase,dagarden_texture_next};
    *address=dagarden_texture_next;dagarden_texture_next+=bytes;dagarden_uploads++;
    return 0;
}
/* VDP1 list from the sprite table the last V-INT copied (the VDP draws earlier entries on top). */
static void __attribute__((optimize("O2"))) dagarden_present(void){
    const scd_dagarden *t=dagarden_state;
    for(unsigned start=vblank_ticks;!vdp1_transfer_status_get().cef && vblank_ticks==start;){}
    unsigned count=2;vdp1_cmdt_t *cmds=sprite_commands->cmdts;dagarden_sprites=0;
    dagarden_textures_check();
    if(dagarden_display){
        vdp1_cmdt_t *clip=cmds+count++;memset(clip,0,sizeof(*clip));vdp1_cmdt_user_clip_coord_set(clip);vdp1_cmdt_vtx_user_clip_coord_set(clip,INT16_VEC2(0,0),INT16_VEC2(319,223));
        unsigned order[80],n=0,index=0;
        while(n<80){
            order[n++]=index;
            unsigned link=dagarden_sat[index*8+3]&0x7F;
            if(!link || link>=80)break;
            index=link;
        }
        for(int i=(int)n-1;i>=0;i--){
            const uint8_t *s=dagarden_sat+order[i]*8;
            unsigned y=((unsigned)s[0]<<8|s[1])&0x1FF,size=s[2],tile=(unsigned)s[4]<<8|s[5],x=((unsigned)s[6]<<8|s[7])&0x1FF;
            unsigned width=((size>>2)&3)+1,height=(size&3)+1;uint32_t address;
            scd_title_scaled_shape shape=scd_title_shape((int)x-128,width);
            if(dagarden_texture_get(tile&0x1FFF,width,height,shape.phase,shape.width,&address))continue;
            vdp1_cmdt_t *cmd=cmds+count++;memset(cmd,0,sizeof(*cmd));vdp1_cmdt_normal_sprite_set(cmd);
            const vdp1_cmdt_draw_mode_t mode={.color_mode=VDP1_CMDT_CM_CLUT_16,.end_code_disable=true,.user_clipping_mode=2};
            vdp1_cmdt_draw_mode_set(cmd,mode);vdp1_cmdt_char_size_set(cmd,shape.stride,height*8);
            vdp1_cmdt_char_base_set(cmd,VDP1_VRAM(address));
            cmd->cmd_colr=(0x8000+((tile>>15&1)*4+(tile>>13&3))*32)/8;
            cmd->cmd_xa=shape.left;cmd->cmd_ya=(int)y-128;dagarden_sprites++;
        }
    }
    (void)t;
    memset(cmds+count,0,sizeof(vdp1_cmdt_t));vdp1_cmdt_end_set(cmds+count);sprite_commands->count=count+1;
    vdp1_sync_cmdt_list_put(sprite_commands,0);vdp1_sync_render();vdp1_sync();
    vdp2_scrn_display_set(dagarden_display?VDP2_SCRN_DISPTP_NBG0|VDP2_SCRN_DISPTP_NBG1:0);
}
static void dagarden_publish(void){
    const scd_dagarden *t=dagarden_state;volatile uint32_t *mb=scd_dagarden_mailbox;
    const uint32_t values[]={t->vint,(uint16_t)t->routine|((uint32_t)t->step<<8)|((uint32_t)t->done<<16),t->sel_id|((uint32_t)t->sel_flags<<8)|((uint32_t)t->zone<<16),
        t->music,dagarden_frames,dagarden_lag,(uint32_t)(uintptr_t)t,++dagarden_sequence,dagarden_last_pad,dagarden_uploads,dagarden_sprites,dagarden_renders,dagarden_timeouts,
        offsetof(scd_dagarden,vram),offsetof(scd_dagarden,cram),offsetof(scd_dagarden,palette),offsetof(scd_dagarden,objects),offsetof(scd_dagarden,planet_image),offsetof(scd_dagarden,sprites),
        dagarden->pack.size};
    for(unsigned i=0;i<sizeof(values)/sizeof(values[0]);i++)mb[1+i]=values[i];
    mb[0]=0x44414744;
    scd_trace_mailbox[0]=0x44414744;scd_trace_mailbox[1]=t->vint;scd_trace_mailbox[2]=mb[2];
}
/* The music the Sub CPU program started (PlayCDDAMusic, MSCPLAYR): every D.A. Garden track
   starts from its beginning and repeats; no zone effect bank is read. */
static void dagarden_music(unsigned track){
    unsigned m=scd_dagarden_ops_get()->track_music(track);
    if(m&0x100)scd_audio_music_loop(0,m&0xFF);else scd_audio_music_loop(m>>4,m&15);
}
/* cd/DAGARDEN.BIN (tools/dagarden_assets.py) into low work RAM, as the movies use it. */
static const char dagarden_file[]="DAGARDEN.BIN";
static int dagarden_pack_read(void){
    uint8_t *const data=(uint8_t *)0x00200000;const uint32_t capacity=0x48000;
    const cdfs_filelist_t *root=scd_cd_root_read();
    for(unsigned i=0;i<root->entries_count;i++)if(!strcmp(root->entries[i].name,dagarden_file)){
        uint32_t size=root->entries[i].size;
        if(size>capacity)return 0;
        scd_low_packs_lost=1;
        if(cd_block_sectors_read(root->entries[i].starting_fad,data,(size+1)&~1u))return 0;
        cpu_cache_purge();
        return !scd_dagarden_ops_get()->open(&dagarden->pack,data,size);
    }
    return 0;
}
/* Leaves the title's state and presentation (title_end ran) for D.A. Garden's. Returns 0 if
   the overlay or the pack is missing (the caller returns to the title). */
static int dagarden_begin(void){
    bg_slave_stop();
    scd_frontend_overlay_load();
    if(!scd_zone_code_ready(SCD_ZONE_FRONTEND))return 0;
    /* SPX.asm SPCmd_LoadDAGarden starts the D.A. Garden track before the program. */
    scd_audio_stop_music();
    if(!dagarden)dagarden=malloc(sizeof(dagarden_block));
    if(!dagarden)return 0;
    if(!dagarden_pack_read() || scd_dagarden_ops_get()->start(dagarden_state,&dagarden->pack)){free(dagarden);dagarden=NULL;return 0;}
    vdp2_tvmd_display_clear();sync_frame();
    gameplay_clear_wait();vdp1_sync_wait();vdp1_sync_interval_set(0);
    vdp1_cmdt_t *cmds=sprite_commands->cmdts;memset(cmds+2,0,sizeof(vdp1_cmdt_t));vdp1_cmdt_end_set(cmds+2);sprite_commands->count=3;
    for(unsigned i=0;i<2;i++){vdp1_sync_cmdt_list_put(sprite_commands,0);vdp1_sync_render();vdp1_sync();sync_frame();vdp1_sync_wait();}
    act_fade_offset(0);
    const vdp2_vram_usage_t usage={0};vdp2_vram_usage_set(&usage);
    vdp2_vram_cycp_t cycles;memset(&cycles,0xff,sizeof(cycles));
    cycles.pt[0].raw=SCD_TITLE_VRAM_A0;cycles.pt[3].raw=SCD_TITLE_VRAM_B1;
    vdp2_vram_cycp_set(&cycles);
    memset((void *)VDP2_VRAM_ADDR(0,0),0,0x18800);
    for(unsigned i=0;i<2;i++){
        vdp2_scrn_t screen=i?VDP2_SCRN_NBG1:VDP2_SCRN_NBG0;
        const vdp2_scrn_cell_format_t fmt={.scroll_screen=screen,.ccc=VDP2_SCRN_CCC_PALETTE_16,.char_size=VDP2_SCRN_CHAR_SIZE_1X1,.pnd_size=2,.aux_mode=0,
            .plane_size=VDP2_SCRN_PLANE_SIZE_1X1,.cpd_base=VDP2_VRAM_ADDR(0,0),.palette_base=VDP2_CRAM_MODE_0_OFFSET(0,0,0)};
        vdp2_vram_t base=VDP2_VRAM_ADDR(0,i?0x14000:0x10000);
        const vdp2_scrn_normal_map_t map={.plane_a=base,.plane_b=base,.plane_c=base,.plane_d=base};
        vdp2_scrn_cell_format_set(&fmt,&map);
        vdp2_scrn_priority_set(screen,2);
        vdp2_scrn_sf_set(screen,VDP2_SCRN_SF_MODE_1,VDP2_SCRN_SF_TYPE_CELL_PRIORITY,VDP2_SCRN_SF_CODE_A);
        const vdp2_scrn_ls_format_t ls={.scroll_screen=screen,.table_base=VDP2_VRAM_ADDR(0,i?0x18400:0x18000),.interval=0,.type=VDP2_SCRN_LS_TYPE_HORZ};
        vdp2_scrn_ls_set(&ls);
        vdp2_scrn_scroll_x_set(screen,0);vdp2_scrn_scroll_y_set(screen,0);
        vdp2_scrn_reduction_set(screen,VDP2_SCRN_REDUCTION_NONE);
        vdp2_scrn_reduction_x_set(screen,0x0000CD00);
    }
    vdp2_sprite_priority_set(0,2);
    volatile uint16_t *clut=(volatile uint16_t *)VDP1_VRAM(0x8000);
    for(unsigned high=0;high<2;high++)for(unsigned line=0;line<4;line++)for(unsigned i=0;i<16;i++)clut[(high*4+line)*16+i]=i?(high?0x4000:0)|(line*16+i):0;
    dagarden_texture_count=0;dagarden_texture_next=0x8100;memset(dagarden_sat,0,sizeof(dagarden_sat));dagarden_display=0;
    dagarden_textures_check();
    memset(&dagarden_shown,0,sizeof(dagarden_shown));dagarden_capture();dagarden_commit();
    vdp2_scrn_display_set(0);vdp2_scrn_back_color_set(VDP2_VRAM_ADDR(3,0x1bffe),(rgb1555_t){.raw=0x8000});
    vdp2_tvmd_display_set();
    dagarden_lag=scd_dagarden_ops_get()->lag_frames(dagarden_state);dagarden_frames=0;
    dagarden_uploads=dagarden_sprites=dagarden_renders=dagarden_timeouts=0;
    scd_dagarden_mailbox[21]=scd_dagarden_mailbox[22]=0;
    dagarden_master_only=0;special_slave_start();dagarden_job[0]=dagarden_job[1]=0;cpu_dual_slave_set(dagarden_slave);
    dagarden_state->render_start=dagarden_render_start;dagarden_state->render_wait=dagarden_render_wait;
    if(dagarden_state->music_changed){dagarden_state->music_changed=0;dagarden_music(dagarden_state->music);}
    return 1;
}
static void dagarden_end(void){
    special_slave_stop();
    for(unsigned i=0;i<4;i++)scd_trace_mailbox[i]=0;
    scd_dagarden_mailbox[0]=0;
    vdp2_tvmd_display_clear();sync_frame();
    vdp1_sync_wait();
    /* The textures borrowed Sonic's gameplay arena, as the title's do. */
    sprite_unpack(sonic_motion,sonic_motion_end,(uint16_t *)VDP1_VRAM(0x10000),21*1040,0);
    vdp2_sprite_priority_set(0,4);
    for(unsigned i=0;i<2;i++){
        const vdp2_scrn_ls_format_t ls={.scroll_screen=i?VDP2_SCRN_NBG1:VDP2_SCRN_NBG0};vdp2_scrn_ls_set(&ls);
        vdp2_scrn_reduction_x_set(ls.scroll_screen,FIX16(1.0));vdp2_scrn_scroll_y_set(ls.scroll_screen,0);
    }
    free(dagarden);dagarden=NULL;
    scd_audio_stop_music();
}
/* One frame: the next original V-INT unless the retail program would miss this one.
   Returns 0 once the program has returned. */
static int dagarden_frame(smpc_peripheral_digital_t pad){
    scd_dagarden *t=dagarden_state;
    if(dagarden_lag)dagarden_lag--;
    else{
        /* Yaul's pressed is the current level (see the title branch in main()). */
        unsigned md=(pad.pressed.button.up?1:0)|(pad.pressed.button.down?2:0)|(pad.pressed.button.left?4:0)|(pad.pressed.button.right?8:0)|
            (pad.pressed.button.b?16:0)|(pad.pressed.button.c?32:0)|(pad.pressed.button.a?64:0)|(pad.pressed.button.start?128:0);
        dagarden_last_pad=md;
        /* The sprite table the V-INT copies is drawn with the VDP2 state it leaves. */
        if(scd_dagarden_ops_get()->vint(t,md)){dagarden_publish();return 0;}
        memcpy(dagarden_sat,t->vram+0xEC00,sizeof(dagarden_sat));dagarden_display=t->display;
        dagarden_capture();
        if(t->music_changed){t->music_changed=0;dagarden_music(t->music);}
        dagarden_lag=scd_dagarden_ops_get()->lag_frames(t);
    }
    dagarden_present();
    dagarden_frames++;dagarden_publish();
    return 1;
}
/* IPX.asm DAGarden: runs D.A. Garden until it returns. The caller restarts the title. */
static void __attribute__((noinline)) dagarden_run(void){
    if(!dagarden_begin())return;
    simulation_tick=vblank_ticks;  /* loading is not a lost frame */
    for(;;){
        vdp1_sync_wait();
        while(simulation_tick==vblank_ticks){}
        /* Work longer than a frame (the refresh's renders) uses up frames the retail program
           misses anyway; [21] counts frames lost beyond those, [22] V-INT and step of the last. */
        if(vblank_ticks-simulation_tick>1){
            unsigned lost=vblank_ticks-simulation_tick-1,absorbed=lost<dagarden_lag?lost:dagarden_lag;
            dagarden_lag-=absorbed;lost-=absorbed;
            if(lost){scd_dagarden_mailbox[21]+=lost;scd_dagarden_mailbox[22]=dagarden_state->vint|(uint32_t)dagarden_state->step<<16;}
        }
        simulation_tick=vblank_ticks;
        smpc_peripheral_digital_t pad;
        smpc_peripheral_process();smpc_peripheral_digital_port(1,&pad);
        scd_audio_update();scd_audio_status();  /* scd_audio_mailbox for the route */
        if(!dagarden_frame(pad))break;
        frames++;sync_frame();dagarden_commit();
    }
    dagarden_end();
}
