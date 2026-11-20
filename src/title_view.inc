#include "player_plus.h"
/* Title screen program (src/title.c) on VDP1/VDP2: one original V-INT per frame, with the
   frames the retail Main CPU program misses (scd_title_lag_frames) shown as repeated
   pictures. Mega Drive plane A/B become NBG0/NBG1 cells with line scroll and cell priority;
   sprites are VDP1 textures cut from the Mega Drive VRAM, whose CLUTs hold palette codes,
   so fades and the water cycle apply to every layer (as in src/special_game_view.inc). */
#include "title.h"
#include "title-parts.inc"
#include "title_scale.h"
#include "title_vram.h"
/* High work RAM while the title runs: the cloud renderer reads and writes it every pixel, and
   low work RAM access is several times slower. */
static scd_title *title_state;
static scd_title_pack title_pack;
static int title_active;
static unsigned title_lag,title_frames,title_sequence,title_last_pad,title_uploads,title_sprites;
/* [0] 'TITL', [1] vintCounter, [2] titleMode | exitFlag<<8 | menuSel<<16 | done<<24, [3] timer,
   [4] pending V-INT routine, [5] clouds camera Y, [6] pad of the last V-INT, [7] lag frames before
   the next V-INT, [8] title state address, [9] frames shown, [10] update sequence, [11] exit code,
   [12] texture uploads, [13] sprites drawn, [14..23] offsets of vram, cram, hscroll, sat, palette,
   fade, hscroll buffer, sprite buffer, cloud image and objects in the state (tools/emulator_test.c
   hashes that memory). */
volatile uint32_t scd_title_mailbox[28];
/* V-INT state written to VDP2 after a later VBlank-in (see title_stages and title_sat). */
typedef struct {uint16_t cram[64],hscroll[448];uint32_t plane_dirty[2],tile_dirty[48];uint8_t display,valid,routine;} title_vdp2;
/* V-INT routine of the V-INT being run, and tiles written one commit late: the Mega Drive VDP is
   still transferring the end of COPYIMG's second half (buffer 1, cell columns 30 and 31, tiles
   361..384) when it draws line 88, so row 11, which always shows buffer 1, changes there a frame
   later (measured on the retail disc). */
static unsigned title_vint_routine;
static uint32_t title_late[48];
/* [1] waits one commit, [0] is written next. With the sprite table held one frame (title_sat), a
   V-INT's VDP1 list and VDP2 memory appear together three frames after it runs; tools/check_title.py
   measures this against the retail pictures. */
static title_vdp2 title_stages[2];
#define title_shown title_stages[0]
typedef struct {uint16_t tile;uint8_t width,height,phase;uint32_t address;} title_texture;
static title_texture title_textures[192];
static unsigned title_texture_count;
static uint32_t title_texture_next;

static void title_capture(void){
    scd_title *t=title_state;title_vdp2 *s=&title_stages[1];
    memcpy(s->cram,t->cram,sizeof(s->cram));memcpy(s->hscroll,t->hscroll,sizeof(s->hscroll));
    for(unsigned i=0;i<2;i++){s->plane_dirty[i]=t->plane_dirty[i];t->plane_dirty[i]=0;}
    for(unsigned i=0;i<48;i++){s->tile_dirty[i]=t->tile_dirty[i];t->tile_dirty[i]=0;}
    s->display=t->display;s->routine=title_vint_routine;s->valid=1;
}
static void title_tiles_write(const scd_title *t,const uint32_t mask[48]){
    for(unsigned word=0;word<48;word++)if(mask[word]){
        unsigned first=word*32,end=first+32;
        while(first<end && !(mask[word]>>(first&31)&1))first++;
        while(end>first && !(mask[word]>>((end-1)&31)&1))end--;
        memcpy((void *)VDP2_VRAM_ADDR(0,first*32),t->vram+first*32,(end-first)*32);
    }
}
/* The slave SH-2 renders each cloud image while the master runs the next V-INTs, as the Sub CPU
   does; [0] requested and [1] finished render. */
static volatile uint32_t title_job[2] __uncached;
static void title_slave(void){
    uint32_t generation=title_job[0];
    cpu_cache_purge();
    scd_title_ops_get()->render(title_state);
    title_job[1]=generation;
}
static void title_render_start(void *context){(void)context;title_job[0]++;cpu_dual_slave_notify();}
static void title_render_wait(void *context){
    (void)context;unsigned start=vblank_ticks;
    while(title_job[1]!=title_job[0] && vblank_ticks-start<60){}
    if(title_job[1]!=title_job[0])scd_title_ops_get()->render(title_state);
    cpu_cache_area_purge(title_state->rendered,sizeof(title_state->rendered));
}
static int title_vint_shown,title_cheat_sound;
/* VDP2 memory right after the VBlank-in commit (colors, line scroll, name table rows, tiles)
   from the previous frame's V-INT; then this frame's V-INT state waits for the next commit. */
static void title_write(void);
static void title_commit(void){
    title_write();
    if(title_stages[1].valid){
        /* Dirty masks accumulate while a lag frame leaves the older stage unwritten. */
        title_vdp2 *older=&title_stages[0],*newer=&title_stages[1];
        memcpy(older->cram,newer->cram,sizeof(older->cram));memcpy(older->hscroll,newer->hscroll,sizeof(older->hscroll));
        for(unsigned i=0;i<2;i++)older->plane_dirty[i]|=newer->plane_dirty[i];
        for(unsigned i=0;i<48;i++)older->tile_dirty[i]|=newer->tile_dirty[i];
        older->display=newer->display;older->routine=newer->routine;older->valid=1;newer->valid=0;
    }
    if(title_vint_shown)title_capture();
    title_vint_shown=0;
}
static void title_write(void){
    const scd_title *t=title_state;title_vdp2 *s=&title_shown;
    title_tiles_write(t,title_late);memset(title_late,0,sizeof(title_late));
    if(!s->valid)return;
    s->valid=0;
    if(s->routine==1)for(unsigned tile=361;tile<=384;tile++)if(s->tile_dirty[tile>>5]>>(tile&31)&1){
        title_late[tile>>5]|=1u<<(tile&31);s->tile_dirty[tile>>5]&=~(1u<<(tile&31));
    }
    const uint16_t back=s->cram[0];
    vdp2_scrn_back_color_set(VDP2_VRAM_ADDR(3,0x1bffe),(rgb1555_t){.raw=(uint16_t)(0x8000|(((back>>1)&7)*31/7)|((((back>>5)&7)*31/7)<<5)|((((back>>9)&7)*31/7)<<10))});
    volatile uint16_t *cram=(volatile uint16_t *)VDP2_CRAM_MODE_0_OFFSET(0,0,0);
    for(unsigned i=0;i<64;i++){
        unsigned c=s->cram[i],r=((c>>1)&7)*31/7,g=((c>>5)&7)*31/7,b=((c>>9)&7)*31/7;
        cram[i]=(uint16_t)(0x8000|r|(g<<5)|(b<<10));
    }
    /* The original H32 image fills the television, not a 256-pixel box in H40.
       Expand it horizontally on Saturn's 320-pixel display. */
    volatile uint32_t *lines[2]={(volatile uint32_t *)VDP2_VRAM_ADDR(0,0x18000),(volatile uint32_t *)VDP2_VRAM_ADDR(0,0x18400)};
    for(unsigned line=0;line<224;line++)for(unsigned plane=0;plane<2;plane++)
        lines[plane][line]=(uint32_t)fix16_int32_from((-(int)s->hscroll[line*2+plane])&511);
    for(unsigned plane=0;plane<2;plane++){
        const uint8_t *table=t->vram+(plane?0xE000:0xC000);
        volatile uint32_t *map=(volatile uint32_t *)VDP2_VRAM_ADDR(0,plane?0x14000:0x10000);
        for(unsigned row=0;row<32;row++)if(s->plane_dirty[plane]>>row&1)for(unsigned col=0;col<64;col++)
            map[row*64+col]=stage_saturn_pnd((uint16_t)(table[(row*64+col)*2]<<8|table[(row*64+col)*2+1]),0);
    }
    title_tiles_write(t,s->tile_dirty);
    memset(s->plane_dirty,0,sizeof(s->plane_dirty));memset(s->tile_dirty,0,sizeof(s->tile_dirty));
}
/* Sprite piece texture: tiles (column-major, as the VDP reads them) copied row-major. */
/* Drops cached textures whose tiles were written since the last picture. */
static void title_textures_check(void){
    scd_title *t=title_state;unsigned kept=0;
    for(unsigned i=0;i<title_texture_count;i++){
        const title_texture *x=title_textures+i;int stale=0;
        for(unsigned n=0;n<(unsigned)x->width*x->height && !stale;n++){unsigned tile=((x->tile&0x7FF)+n)&0x7FF;stale=t->sprite_dirty[tile>>5]>>(tile&31)&1;}
        if(!stale)title_textures[kept++]=*x;
    }
    title_texture_count=kept;memset(t->sprite_dirty,0,sizeof(t->sprite_dirty));
}
/* Pre-expand sprites on the same global 205/256 sampling grid as VDP2. VDP1's
   scaled-sprite rasterizer otherwise uses a separate grid for each piece and
   exposes background pixels along opaque sprite edges. Texture widths are
   padded to eight dots; that padding must remain transparent even when flipped. */
static int __attribute__((optimize("O2"))) title_texture_get(unsigned tile,unsigned width,unsigned height,unsigned phase,unsigned shown_width,uint32_t *address){
    scd_title *t=title_state;
    for(unsigned i=0;i<title_texture_count;i++)if(title_textures[i].tile==tile && title_textures[i].width==width && title_textures[i].height==height && title_textures[i].phase==phase){*address=title_textures[i].address;return 0;}
    unsigned stride=(shown_width+7)&~7u,bytes=stride*height*4;
    if(title_texture_count==sizeof(title_textures)/sizeof(title_textures[0]) || title_texture_next+bytes>OBJECT_ATLAS_BASE){title_texture_count=0;title_texture_next=0x8100;return -1;}
    uint8_t texture[48*32/2] __aligned(4);
    scd_title_expand(texture,t->vram,tile,width,height,(scd_title_scaled_shape){0,shown_width,stride,phase});
    memcpy((void *)VDP1_VRAM(title_texture_next),texture,bytes);
    title_textures[title_texture_count++]=(title_texture){tile,width,height,phase,title_texture_next};
    *address=title_texture_next;title_texture_next+=bytes;title_uploads++;
    return 0;
}
/* These fixed-position poses already exist after Start, before the flash
   reveals them. Expand them during loading, not on their reveal frame. */
static void title_prewarm_mapping(unsigned part,unsigned frame,unsigned tile_base,int x){
    const uint8_t *map=title_pack.data+title_pack.offset[part];
    assert(frame*2+2<=title_pack.length[part]);
    unsigned offset=((unsigned)map[frame*2]<<8)|map[frame*2+1];
    assert(offset<title_pack.length[part]);
    const uint8_t *p=map+offset;unsigned count=*p++;
    assert(offset+1+count*5<=title_pack.length[part]);
    for(unsigned i=0;i<count;i++,p+=5){
        unsigned width=((p[1]>>2)&3)+1,height=(p[1]&3)+1;
        unsigned tile=(((unsigned)p[2]<<8)|p[3])+tile_base;
        scd_title_scaled_shape shape=scd_title_shape(x+(int8_t)p[4],width);
        uint32_t address;
        if(title_texture_get(tile&0x1FFF,width,height,shape.phase,shape.width,&address))return;
    }
}
/* Sprite table and display flag as they stood one frame earlier, so VDP1 matches the VDP2 stages. */
static uint8_t title_sat[640];
static uint8_t title_display;
/* VDP1 list from the sprite table the V-INT before the last frame copied; the VDP draws earlier entries on top. */
static void __attribute__((optimize("O2"))) title_present(void){
    const scd_title *t=title_state;
    uint8_t sat[640];memcpy(sat,title_sat,sizeof(sat));memcpy(title_sat,t->sat,sizeof(title_sat));
    const unsigned display=title_display;title_display=t->display;
    for(unsigned start=vblank_ticks;!vdp1_transfer_status_get().cef && vblank_ticks==start;){}
    unsigned count=2;vdp1_cmdt_t *cmds=sprite_commands->cmdts;title_sprites=0;
    title_textures_check();
    if(display){
        vdp1_cmdt_t *clip=cmds+count++;memset(clip,0,sizeof(*clip));vdp1_cmdt_user_clip_coord_set(clip);vdp1_cmdt_vtx_user_clip_coord_set(clip,INT16_VEC2(0,0),INT16_VEC2(319,223));
        unsigned order[64],n=0,index=0;
        while(n<64){
            order[n++]=index;
            unsigned link=sat[index*8+3]&0x7F;
            if(!link || link>=64)break;
            index=link;
        }
        for(int i=(int)n-1;i>=0;i--){
            const uint8_t *s=sat+order[i]*8;
            unsigned y=((unsigned)s[0]<<8|s[1])&0x1FF,size=s[2],tile=(unsigned)s[4]<<8|s[5],x=((unsigned)s[6]<<8|s[7])&0x1FF;
            unsigned width=((size>>2)&3)+1,height=(size&3)+1;uint32_t address;
            scd_title_scaled_shape shape=scd_title_shape((int)x-128,width);
            if(title_texture_get(tile&0x1FFF,width,height,shape.phase,shape.width,&address))continue;
            vdp1_cmdt_t *cmd=cmds+count++;memset(cmd,0,sizeof(*cmd));vdp1_cmdt_normal_sprite_set(cmd);
            const vdp1_cmdt_draw_mode_t mode={.color_mode=VDP1_CMDT_CM_CLUT_16,.end_code_disable=true,.user_clipping_mode=2};
            vdp1_cmdt_draw_mode_set(cmd,mode);vdp1_cmdt_char_size_set(cmd,shape.stride,height*8);
            vdp1_cmdt_char_base_set(cmd,VDP1_VRAM(address));
            cmd->cmd_colr=(0x8000+((tile>>15&1)*4+(tile>>13&3))*32)/8;
            cmd->cmd_xa=shape.left;cmd->cmd_ya=(int)y-128;title_sprites++;
        }
    }
    memset(cmds+count,0,sizeof(vdp1_cmdt_t));vdp1_cmdt_end_set(cmds+count);sprite_commands->count=count+1;
    vdp1_sync_cmdt_list_put(sprite_commands,0);vdp1_sync_render();vdp1_sync();
    vdp2_scrn_display_set(title_shown.display?VDP2_SCRN_DISPTP_NBG0|VDP2_SCRN_DISPTP_NBG1:0);
}
static void title_publish(void){
    const scd_title *t=title_state;volatile uint32_t *mb=scd_title_mailbox;
    int menu=-1;for(unsigned i=0;i<SCD_TITLE_OBJECTS;i++)if(t->objects[i].active && t->objects[i].kind==5)menu=(int)i;
    const uint32_t values[]={t->vint,t->mode|((uint32_t)t->exit_flag<<8)|((uint32_t)t->menu_sel<<16)|((uint32_t)t->done<<24),t->timer,t->routine,(uint16_t)t->cam_y,title_last_pad,title_lag,
        (uint32_t)(uintptr_t)t,title_frames,++title_sequence,t->exit_code,title_uploads,title_sprites,
        offsetof(scd_title,vram),offsetof(scd_title,cram),offsetof(scd_title,hscroll),offsetof(scd_title,sat),offsetof(scd_title,palette),
        offsetof(scd_title,fade),offsetof(scd_title,hscroll_buffer),offsetof(scd_title,sprites),offsetof(scd_title,clouds_image),offsetof(scd_title,objects)};
    for(unsigned i=0;i<sizeof(values)/sizeof(values[0]);i++)mb[1+i]=values[i];
    mb[0]=0x5449544c;
    /* The trace mailbox tells every emulator gate that the title runs: vintCounter and
       titleMode | menu selectable<<8 | menuSel<<16 | done<<24. */
    scd_trace_mailbox[0]=0x5449544c;scd_trace_mailbox[1]=t->vint;
    scd_trace_mailbox[2]=t->mode|(menu>=0 && t->objects[menu].allow?256u:0)|((uint32_t)t->menu_sel<<16)|((uint32_t)t->done<<24);
}
static void title_begin(int load){
    /* Every return to the title ends an attract demo's Classic hold. */
    scd_plus_classic_hold(0);
    /* Title rendering installs special_slave_render on the same SH-2. */
    bg_slave_stop();
    if(load)stage_packs_load(PACK_TITLE,PACK_TITLE+1);
    title_cheat_sound=0;
    scd_frontend_overlay_load();
    if(!title_state)title_state=malloc(sizeof(scd_title));
    if(!title_state || scd_title_ops_get()->open(&title_pack,STAGE_PACK_DATA(PACK_TITLE),stage_pack_bytes[PACK_TITLE]) || scd_title_ops_get()->start(title_state,&title_pack)){
        vdp2_tvmd_display_set();dbgio_printf("\x1b[H\x1b[2JBAD TITLE PACKAGE");dbgio_flush();for(;;)sync_frame();
    }
    title_state->save_available=save_state.valid;
    title_state->title_flags=scd_zone_code_ready(SCD_ZONE_FRONTEND)?(uint8_t)scd_frontend_ops_get()->title_flags(
        save_state.valid?save_state.saved.zone+(save_state.saved.completed?1u:0u):0):0;
    vdp2_tvmd_display_clear();sync_frame();
    /* Title presentation has its own source-verified pipeline delay. */
    gameplay_clear_wait();vdp1_sync_wait();vdp1_sync_interval_set(0);
    /* Clear the VDP1 framebuffer of the previous mode's picture. */
    vdp1_cmdt_t *cmds=sprite_commands->cmdts;memset(cmds+2,0,sizeof(vdp1_cmdt_t));vdp1_cmdt_end_set(cmds+2);sprite_commands->count=3;
    for(unsigned i=0;i<2;i++){vdp1_sync_cmdt_list_put(sprite_commands,0);vdp1_sync_render();vdp1_sync();sync_frame();vdp1_sync_wait();}
    act_fade_offset(0);
    const vdp2_vram_usage_t usage={0};vdp2_vram_usage_set(&usage);
    vdp2_vram_cycp_t cycles;memset(&cycles,0xff,sizeof(cycles));
    cycles.pt[0].raw=SCD_TITLE_VRAM_A0;
    cycles.pt[3].raw=SCD_TITLE_VRAM_B1;
    vdp2_vram_cycp_set(&cycles);
    memset((void *)VDP2_VRAM_ADDR(0,0),0,0x18800);
    for(unsigned i=0;i<2;i++){
        vdp2_scrn_t screen=i?VDP2_SCRN_NBG1:VDP2_SCRN_NBG0;
        const vdp2_scrn_cell_format_t fmt={.scroll_screen=screen,.ccc=VDP2_SCRN_CCC_PALETTE_16,.char_size=VDP2_SCRN_CHAR_SIZE_1X1,.pnd_size=2,.aux_mode=0,
            .plane_size=VDP2_SCRN_PLANE_SIZE_1X1,.cpd_base=VDP2_VRAM_ADDR(0,0),.palette_base=VDP2_CRAM_MODE_0_OFFSET(0,0,0)};
        vdp2_vram_t base=VDP2_VRAM_ADDR(0,i?0x14000:0x10000);
        const vdp2_scrn_normal_map_t map={.plane_a=base,.plane_b=base,.plane_c=base,.plane_d=base};
        vdp2_scrn_cell_format_set(&fmt,&map);
        /* Equal base priority keeps plane A over plane B; the cell bit raises high tiles; low sprites use register 0. */
        vdp2_scrn_priority_set(screen,2);
        vdp2_scrn_sf_set(screen,VDP2_SCRN_SF_MODE_1,VDP2_SCRN_SF_TYPE_CELL_PRIORITY,VDP2_SCRN_SF_CODE_A);
        const vdp2_scrn_ls_format_t ls={.scroll_screen=screen,.table_base=VDP2_VRAM_ADDR(0,i?0x18400:0x18000),.interval=0,.type=VDP2_SCRN_LS_TYPE_HORZ};
        vdp2_scrn_ls_set(&ls);
        vdp2_scrn_scroll_x_set(screen,0);vdp2_scrn_scroll_y_set(screen,0);
        /* Hardware step has eight fractional bits: nearest step to 256/320. */
        vdp2_scrn_reduction_set(screen,VDP2_SCRN_REDUCTION_NONE);
        vdp2_scrn_reduction_x_set(screen,0x0000CD00);
    }
    vdp2_sprite_priority_set(0,2);
    volatile uint16_t *clut=(volatile uint16_t *)VDP1_VRAM(0x8000);
    for(unsigned high=0;high<2;high++)for(unsigned line=0;line<4;line++)for(unsigned i=0;i<16;i++)clut[(high*4+line)*16+i]=i?(high?0x4000:0)|(line*16+i):0;
    title_texture_count=0;title_texture_next=0x8100;memset(title_sat,0,sizeof(title_sat));title_display=0;
    title_textures_check();
    title_prewarm_mapping(TITLE_PART_MAP_BANNER,0,0xF000/32,127);
    /* Sonic frame 4 and arm frame 9 arrive together: 22 new textures used
       to be expanded on V-INT 82. Their art lies beyond the emblem reload. */
    title_prewarm_mapping(TITLE_PART_MAP_SONIC,4,0x6D00/32,91);
    title_prewarm_mapping(TITLE_PART_MAP_SONIC,9,0x6D00/32,140);
    title_shown.valid=0;memset(title_late,0,sizeof(title_late));title_capture();title_write();title_vint_shown=0;
    vdp2_scrn_display_set(0);vdp2_scrn_back_color_set(VDP2_VRAM_ADDR(3,0x1bffe),(rgb1555_t){.raw=0x8000});
    vdp2_tvmd_display_set();
    title_lag=scd_title_ops_get()->lag_frames(title_state);title_frames=0;title_active=1;
    special_slave_start();title_job[0]=title_job[1]=0;cpu_dual_slave_set(title_slave);
    title_state->render_start=title_render_start;title_state->render_wait=title_render_wait;
    scd_audio_era(9);
}
/* Returns the title's exit code and releases its state. */
static unsigned title_end(void){
    unsigned code=title_state->exit_code;
    title_active=0;special_slave_stop();
    /* The original program has returned. Stop presenting the title before
       replacing its live texture arena or changing its sampling registers. */
    for(unsigned i=0;i<4;i++)scd_trace_mailbox[i]=0;
    scd_title_mailbox[0]=0;
    vdp2_tvmd_display_clear();sync_frame();
    /* Wide title textures borrow Sonic's gameplay arena, but never the object
       atlas. Restore Sonic before the next gameplay command list is submitted. */
    vdp1_sync_wait();
    sprite_unpack(sonic_motion,sonic_motion_end,(uint16_t *)VDP1_VRAM(0x10000),21*1040,0);
    vdp2_sprite_priority_set(0,4);
    for(unsigned i=0;i<2;i++){const vdp2_scrn_ls_format_t ls={.scroll_screen=i?VDP2_SCRN_NBG1:VDP2_SCRN_NBG0};vdp2_scrn_ls_set(&ls);vdp2_scrn_reduction_x_set(ls.scroll_screen,FIX16(1.0));}
    free(title_state);title_state=NULL;
    return code;
}
/* One frame of the title before sync_frame() and title_commit(); returns 0 once the program has returned. */
static int title_frame(smpc_peripheral_digital_t pad){
    scd_title *t=title_state;
    if(title_lag)title_lag--;
    else{
        unsigned md=(pad.pressed.button.up?1:0)|(pad.pressed.button.down?2:0)|(pad.pressed.button.left?4:0)|(pad.pressed.button.right?8:0)|
            (pad.pressed.button.b?16:0)|(pad.pressed.button.c?32:0)|(pad.pressed.button.a?64:0)|(pad.pressed.button.start?128:0);
        title_last_pad=md;title_vint_routine=t->routine;unsigned start=vblank_ticks;
        if(scd_title_ops_get()->vint(t,md)){title_publish();return 0;}
        if((t->exit_flag==7 || t->exit_flag==8 || t->exit_flag==9) && !title_cheat_sound){title_cheat_sound=1;scd_audio_request(149);}
        scd_title_mailbox[24]=vblank_ticks-start;if(vblank_ticks-start>scd_title_mailbox[25])scd_title_mailbox[25]=vblank_ticks-start;
        title_vint_shown=1;title_lag=scd_title_ops_get()->lag_frames(t);
    }
    unsigned start=vblank_ticks;
    title_present();
    scd_title_mailbox[26]=vblank_ticks-start;
    title_frames++;title_publish();
    return 1;
}
