/* Special stage program (src/special_game.c) on VDP1/VDP2, one V-INT per
   frame. Entered with B from the floor inspection for the inspected stage 1-7
   (L+B starts at score 4000 to reach an extra life on the results screen);
   returns to the inspection after the results fade. Mega Drive plane A/B become NBG0/NBG1 cells with
   line scroll; the floor and objects are VDP1 sprites whose CLUTs hold
   palette codes, so CRAM fades and cycles apply to every layer at once. */
#include "special_main.h"
#include "special_game.h"
#include "special_modes.h"
static void special_load(unsigned id);
static void special_game_commit(void);
/* curSpecStage (0-6): the next special stage. Reset by New Game, restored by
   Continue (save v2 spec_stage), advanced by Sub.asm .Exit at each result. */
static unsigned special_cur_stage;
/* IPX.asm mode entries: specStageFlags (bit 0 temporary, 1 time attack, 2 secret)
   and the stage they play; 0 is the normal entry with results. */
static unsigned special_game_mode,special_game_mode_stage;

static scd_special_main_pack special_main_pack;
static int special_game_active,special_game_pending,special_game_results_patterns,special_game_entry_held,special_game_lower_lines;
static unsigned special_game_error,special_game_sequence,special_game_pad;
typedef struct {int32_t update;unsigned count,sprite_y;int visible;scd_special_pose pose;scd_special_draw draws[SCD_SPECIAL_DRAWS];} special_game_sprites;
typedef struct {int32_t update;uint16_t texture[6144];} special_game_image;
/* VDP2 state of one V-INT. VDP1 displays a command list one frame after VDP2
   displays a commit from the same frame, so the stage shows the previous
   V-INT's VDP2 state. The original shows each results V-INT one frame later
   than a stage V-INT, so the results screen shows the current state. */
typedef struct {uint16_t cram[64],hscroll[448],plane[2][2048];uint32_t dirty[2];uint16_t vsram_a;uint8_t display,h40;} special_game_vdp2;
static special_game_sprites special_game_lists[3];
/* Update index of the floor image in VDP1 VRAM; its WRAM slot can be reused. */
static int32_t special_game_uploaded;
/* Low WRAM: AnimateStamps' render-map copy above the UFO paths, then above
   the SSM pack three floor textures, the program state and the shown VDP2 state. */
static uint16_t *const special_game_animated=(uint16_t *)0x002D2000;
/* Then the job's step reciprocals (scd_special_reciprocals), below the SSM pack. */
static uint32_t *const special_game_reciprocals=(uint32_t *)0x002DA000;
static special_game_image *const special_game_images=(special_game_image *)0x002F0000;
static scd_special_game *const special_game=(scd_special_game *)0x002FA000;
static special_game_vdp2 *const special_game_shown=(special_game_vdp2 *)0x002FD000;
_Static_assert(3*sizeof(special_game_image)<=0xA000 && sizeof(scd_special_game)<=0x3000 && sizeof(special_game_vdp2)<=0x3000,"special game low WRAM layout");
volatile uint32_t scd_special_game_mailbox[40];
/* One floor image job per Sub CPU update, in 96 units (special_game_row). The
   slave renders units from the first and the master renders units back from
   the last until the display nears VBlank-in; a unit rendered by both CPUs is
   written identically. Up to
   two updates wait while earlier images render, each with the animated
   stamp cells of its own AnimateStamps, applied to the render map when its
   job starts. */
enum {SPECIAL_GAME_CELLS=64,SPECIAL_GAME_WAITING=1};
typedef struct {int32_t update;scd_special_camera camera;uint16_t values[SPECIAL_GAME_CELLS];} special_game_waiting;
/* busy: slave FRT ticks (CPU clock / 8) spent on units, for the QA headroom report. */
static volatile struct {uint32_t generation,idle,slot,top,bottom,rows,busy;} special_game_job __uncached;
static int32_t special_game_job_update;
static special_game_waiting special_game_queue[SPECIAL_GAME_WAITING];
static unsigned special_game_queued,special_game_cell_count;
static uint16_t special_game_cells[SPECIAL_GAME_CELLS];
/* Row costs and frame work in VDP2 scanlines: last and longest master row, line after the VDP1 list. */
static unsigned special_game_frame_tick,special_game_row_last,special_game_row_lines,special_game_present_line,special_game_late,special_game_forced;
/* A job unit is 8 rows by 32 samples, about one row of work: the stamps of a
   narrow band stay in the data cache from one row to the next, which keeps
   high camera views (spring and fan jumps) within the frame budget. */
static void special_game_row(unsigned unit){
    const unsigned row=(unit>>3)*8,first=(unit&7)*32;
    uint8_t *pixels=special_pixels+row*256+first;
    scd_special_render_span(special_cache,(const uint16_t *)maps,special_lines+row,special_game_reciprocals+row*2,pixels,256,8,first,32);
    uint16_t *texture=special_game_images[special_game_job.slot].texture+row*64+first/4;
    for(unsigned line=0;line<8;line++,pixels+=256,texture+=64)for(unsigned i=0;i<8;i++){
        uint32_t four=((const uint32_t *)pixels)[i];
        uint32_t pairs=(four&0x000f000fu)|((four&0x0f000f00u)>>4);
        texture[i]=(uint16_t)(pairs|(pairs>>8));
    }
}
static void special_game_slave(void){
    cpu_cache_purge();cpu_cache_repl_enable(CPU_CACHE_TYPE_I|CPU_CACHE_TYPE_D);
    for(unsigned row;(row=special_game_job.top)<special_game_job.bottom;special_game_job.top=row+1){
        uint16_t start=cpu_frt_count_get();special_game_row(row);special_game_job.busy+=(uint16_t)(cpu_frt_count_get()-start);special_game_job.rows++;
    }
    special_game_job.idle=special_game_job.generation;
}
static unsigned special_game_line(void){vdp2_tvmd_extern_latch();return vdp2_tvmd_vcount_get();}
static int special_game_job_wait(void){
    unsigned start=vblank_ticks;
    while(special_game_job.idle!=special_game_job.generation && vblank_ticks-start<30){}
    return special_game_job.idle==special_game_job.generation?0:-1;
}
static void special_game_job_start(scd_special_camera camera,int32_t index){
    special_game_image *image=special_game_images+index%3;image->update=-1;
    if(scd_special_trace(special_lines,camera)){memset(image->texture,0,sizeof(image->texture));image->update=index;return;}
    scd_special_reciprocals(special_lines,96,special_game_reciprocals);
    special_game_job.slot=index%3;special_game_job.top=0;special_game_job.bottom=96;special_game_row_last=8;
    special_game_job_update=index;special_game_job.generation++;cpu_dual_slave_notify();
}
/* Master rows of the current job while the display is above VBlank-in (line
   224). Force renders to the end; while plotting also stops once VDP1 has
   fetched the end code. Returns 1 when no image is left to render. */
enum {SPECIAL_GAME_SLICE,SPECIAL_GAME_FORCE,SPECIAL_GAME_WHILE_PLOTTING};
static int special_game_job_render(int mode){
    if(special_game_job_update<0)return 1;
    const int force=mode==SPECIAL_GAME_FORCE;
    volatile cpu_ioregs_t *cpu=(volatile cpu_ioregs_t *)CPU_IOREG_BASE;
    unsigned ccr=cpu->ccr,line=force?0:special_game_line();cpu_cache_repl_enable(CPU_CACHE_TYPE_I|CPU_CACHE_TYPE_D);
    for(unsigned row;(row=special_game_job.bottom)>special_game_job.top;){
        /* Units cost more toward the horizon: allow half again the last master
           unit, or twice it for the first unit of the next 8-row band. Eight
           rows vary more than one, so keep six lines before VBlank-in: a unit
           that ends after it costs the next frame. */
        const unsigned estimate=special_game_row_last+(((row-1)&7)==7?special_game_row_last:special_game_row_last>>1);
        if(!force && line+estimate+6>=224){cpu->ccr=ccr;return 0;}
        if(mode==SPECIAL_GAME_WHILE_PLOTTING && vdp1_transfer_status_get().cef){cpu->ccr=ccr;return 0;}
        special_game_row(row-1);special_game_job.bottom=row-1;
        if(force){special_game_forced++;continue;}
        unsigned next=special_game_line();
        if(next<line){cpu->ccr=ccr;return 0;}
        special_game_row_last=next-line+1;line=next;
        if(special_game_row_last>special_game_row_lines)special_game_row_lines=special_game_row_last;
    }
    cpu->ccr=ccr;
    special_game_image *image=special_game_images+special_game_job.slot;
    cpu_cache_area_purge(image->texture,sizeof(image->texture)); /* Rows packed by the slave. */
    image->update=special_game_job_update;special_game_job_update=-1;
    return 1;
}
/* Starts the oldest waiting job once the slave is idle; force waits for the slave. */
static int special_game_job_advance(int force){
    if(special_game_job_update>=0 || !special_game_queued)return 0;
    if(special_game_job.idle!=special_game_job.generation){
        if(!force)return 0;
        if(special_game_job_wait())return -1;
    }
    const special_game_waiting *next=special_game_queue;
    for(unsigned i=0;i<special_game_cell_count;i++)((uint16_t *)maps)[special_game_cells[i]]=next->values[i];
    special_game_job_start(next->camera,next->update);
    if(--special_game_queued)special_game_queue[0]=special_game_queue[1];
    return 0;
}
static int special_game_image_ready(int32_t update){
    for(unsigned i=0;i<3;i++)if(special_game_images[i].update==update)return 1;
    return 0;
}
/* Finishes the jobs up to one image that must be displayed now. */
static int special_game_job_until(int32_t update){
    while(!special_game_image_ready(update) && (special_game_job_update>=0 || special_game_queued)){
        special_game_job_render(SPECIAL_GAME_FORCE);
        if(!special_game_image_ready(update) && special_game_job_advance(1))return -1;
    }
    return 0;
}
/* End of each frame: master rows before VBlank-in, then a waiting job. Its
   projection and map commit take about 30 lines, so it starts only above line 176. */
static void special_game_job_slice(void){
    for(unsigned jobs=0;jobs<2 && special_game_job_render(SPECIAL_GAME_SLICE);jobs++){
        if(special_game_queued && special_game_line()>=176)return;
        special_game_job_advance(0);
        if(special_game_job_update<0)return;
    }
}
/* Stops the floor job and returns the slave to the inspection. */
static void special_game_release(void){
    special_game_job.bottom=0;special_game_queued=0;
    if(special_slave_ready)special_game_job_wait();
    special_game_job_update=-1;cpu_dual_slave_set(special_slave_render);
}
/* UpdateStage: AnimateStamps, the floor image from the pre-update camera
   (the zeroed graphics variables for update 0), RunObjects and UpdateTimer. */
static int special_game_update(void *context,unsigned held,unsigned tapped){
    (void)context;
    scd_special_player *p=&special_sonic_player;int32_t index=special_game->updates;
    if(special_game_queued==SPECIAL_GAME_WAITING){
        special_game_job_render(SPECIAL_GAME_FORCE);
        if(special_game_job_advance(1)){special_slave_stop();special_game_error=3;return -1;}
    }
    special_game_waiting *waiting=special_game_queue+special_game_queued++;
    waiting->update=index;
    waiting->camera=index?(scd_special_camera){p->x>>16,p->y>>16,p->z,128,p->yaw>>16}:(scd_special_camera){0,0,0,0,0};
    scd_special_animate(&special_stage,&special_animation,(uint8_t *)special_stage.part[1],special_cache,special_game_animated);
    for(unsigned i=0;i<special_game_cell_count;i++)waiting->values[i]=special_game_animated[special_game_cells[i]];
    special_game_job_advance(0);
    if(scd_special_stage_update(&special_stage_state,&special_sonic_world,p,&special_sonic_sprite,&special_sonic_art,&special_ufo_art,&special_effect_art,&special_stage,held,tapped,p->yaw>>16,&special_sonic_pose,&special_sonic_visible)){special_game_error=6;return -1;}
    special_game_sprites *list=special_game_lists+index%3;
    list->update=index;list->count=special_stage_state.draw_count;memcpy(list->draws,special_stage_state.draws,sizeof(list->draws));
    list->pose=special_sonic_pose;list->visible=special_sonic_visible;list->sprite_y=p->sprite_y>>16;
    return 0;
}
static void special_game_patterns(int results){
    const uint8_t *t=special_main_pack.data+special_main_pack.offset[1];
    unsigned count=special_word(t),at=2;
    memset((void *)VDP2_VRAM_ADDR(0,0),0,0x10000);
    for(unsigned i=0;i<count;i++){
        unsigned first=special_word(t+at),tiles=special_word(t+at+2),group=special_word(t+at+4);
        /* Group 0 (Art_HUD, LoadSSnData art) loads at Start; Results replaces VRAM with group 1. */
        if((int)group==results)memcpy((void *)VDP2_VRAM_ADDR(0,first*32),t+at+6,tiles*32);
        at+=6+tiles*32;
    }
    special_game_results_patterns=results;
}
/* score and next_life in special-stage units (tens of display points). */
static int special_game_begin(unsigned score,unsigned next_life,unsigned lives,unsigned time_stones){
    /* IPX.asm .SpecialStage sends curSpecStage; the inspection (B) plays the
       inspected stage (stage 8 has no program pack, so it plays stage 1). */
    unsigned inspected=scd_special_mailbox[2];
    unsigned spec_stage=special_game_mode?special_game_mode_stage:special_return_act?special_cur_stage%7+1:inspected>=1 && inspected<=7?inspected:1;
    special_load(spec_stage);
    if(!special_main_pack.data || !special_stage.stage || !special_sonic_art.data || !special_effect_art.data || !special_ufo_art.data)return -1;
    special_game_cell_count=0;
    for(unsigned part=5;part<7;part++)for(unsigned row=0;row<special_stage.size[part];row+=part==5?10:8){
        if(special_game_cell_count==SPECIAL_GAME_CELLS)return -1;
        special_game_cells[special_game_cell_count++]=special_word(special_stage.part[part]+row)/2;
    }
    vdp2_tvmd_display_clear();sync_frame();
    /* The VDP1 framebuffer still holds the previous mode's picture; plot an
       empty list through two frame changes before the display returns. */
    vdp1_cmdt_t *cmds=sprite_commands->cmdts;memset(cmds+2,0,sizeof(vdp1_cmdt_t));vdp1_cmdt_end_set(cmds+2);sprite_commands->count=3;
    for(unsigned i=0;i<2;i++){vdp1_sync_cmdt_list_put(sprite_commands,0);vdp1_sync_render();vdp1_sync();sync_frame();vdp1_sync_wait();}
    const vdp2_vram_usage_t usage={0};vdp2_vram_usage_set(&usage);
    vdp2_vram_cycp_t cycles;memset(&cycles,0xff,sizeof(cycles));
    cycles.pt[0].t0=cycles.pt[0].t1=VDP2_VRAM_CYCP_PNDR_NBG0;cycles.pt[0].t2=cycles.pt[0].t3=VDP2_VRAM_CYCP_PNDR_NBG1;
    cycles.pt[0].t4=VDP2_VRAM_CYCP_CHPNDR_NBG0;cycles.pt[0].t5=VDP2_VRAM_CYCP_CHPNDR_NBG1;
    cycles.pt[3].t0=VDP2_VRAM_CYCP_PNDR_NBG3;cycles.pt[3].t4=VDP2_VRAM_CYCP_CHPNDR_NBG3;
    vdp2_vram_cycp_set(&cycles);
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
        const vdp2_scrn_ls_format_t ls={.scroll_screen=screen,.table_base=VDP2_VRAM_ADDR(0,i?0x18400:0x18000),.interval=0,.type=VDP2_SCRN_LS_TYPE_HORZ};
        vdp2_scrn_ls_set(&ls);
        vdp2_scrn_scroll_x_set(screen,0);vdp2_scrn_scroll_y_set(screen,0);
        memset((void *)VDP2_VRAM_ADDR(0,i?0x14000:0x10000),0,0x4000);
    }
    special_game_patterns(0);
    /* Floor: plane A low priority (register 0); objects: high priority (register 1). */
    vdp2_sprite_priority_set(0,2);
    volatile uint16_t *clut=(volatile uint16_t *)VDP1_VRAM(0xb000);
    for(unsigned i=0;i<16;i++){clut[i]=i?16+i:0;clut[16+i]=i?0x4000|i:0;}
    for(unsigned line=0;line<4;line++)for(unsigned i=0;i<16;i++)clut[32+line*16+i]=i?0x4000|(line*16+i):0;
    for(unsigned i=0;i<3;i++){special_game_images[i].update=-1;special_game_lists[i].update=-1;}
    special_game_uploaded=-2;special_game_lower_lines=0;
    special_game_error=special_game_late=special_game_forced=special_game_row_lines=special_game_present_line=0;special_game_row_last=8;
    memset((void *)&special_game_job,0,sizeof(special_game_job));special_game_job_update=-1;special_game_queued=0;
    memcpy(special_game_animated,maps,32768);
    cpu_dual_slave_set(special_game_slave);
    special_sonic_world=(scd_special_world){.timer=100,.timer_frames=20,.ufo_count=6};
    /* Main.asm demoData: cd/SSM1.BIN and SSM6.BIN carry it after the pack (tools/special_main_assets.py). */
    if(special_game_mode)scd_special_modes()->begin(&special_sonic_world,special_game_mode,special_main_pack.data+special_main_pack.size);
    if(scd_special_stage_reset(&special_stage_state,&special_sonic_world,(const void *)0x002D0000,special_ufo_paths_size,spec_stage-1)){special_game_release();return -1;}
    special_sonic_sprite=(scd_special_sprite){.tilt=5};
    scd_special_stage_start(&special_stage_state,&special_sonic_world,&special_sonic_player,&special_sonic_sprite);
    special_animation=(scd_special_animation){0,0,0};
    scd_audio_pause(0);scd_audio_era(7);
    scd_special_game *g=special_game;
    if(scd_special_game_start(g,&special_main_pack,&special_sonic_world,&special_sonic_player,special_game_update,NULL,score,next_life,lives,time_stones,spec_stage)){special_game_release();return -1;}
    special_game_vdp2 *s=special_game_shown;
    memcpy(s->cram,g->cram,sizeof(s->cram));memcpy(s->hscroll,g->hscroll,sizeof(s->hscroll));
    memcpy(s->plane[0],g->main.plane_a,sizeof(s->plane[0]));memcpy(s->plane[1],g->main.plane_b,sizeof(s->plane[1]));
    s->dirty[0]=s->dirty[1]=0xffffffffu;g->main.dirty[0]=g->main.dirty[1]=0;
    s->vsram_a=g->vsram_a;s->display=g->display;s->h40=g->h40;
    /* Write every name-table row and scroll line now, with the display off; in
       V-INT 1's VBlank commit they overrun and delay its picture by a frame. */
    special_game_pending=1;special_game_commit();
    special_game_active=special_game_entry_held=1;special_sonic_mode=0;
    vdp2_tvmd_display_set();
    special_game_frame_tick=vblank_ticks;
    return 0;
}
scd_special_mode_result scd_special_mode_last;
__attribute__((noinline)) int scd_special_mode_start(unsigned stage,unsigned flags){
    special_game_mode=flags;special_game_mode_stage=stage;
    if(!special_game_begin(0,0,3,0))return 0;
    special_game_mode=0;return -1;
}
/* Front-end entries (src/special_modes.h). IPX.asm SoundTest_SpecStg8: stage 8,
   temporary and secret; the run returns to the title. */
int scd_special_ss8_start(void){return scd_special_mode_start(8,SCD_SPECIAL_TEMPORARY|SCD_SPECIAL_SECRET);}
/* IPX.asm TimeAttack_SS: special stage n (Time Attack entry 20+n). When it ends, the
   main loop sets scd_ta.frames, aborted and pending and opens the Time Attack menu. */
__attribute__((noinline)) int scd_special_ta_start(unsigned n){
    if(n<1 || n>7)return -1;
    scd_ta.entry=(uint8_t)(SCD_TA_ACTS+n-1);scd_ta.mode=1;scd_ta.aborted=0;scd_ta.pending=0;scd_ta.frames=0;
    if(scd_special_mode_start(n,SCD_SPECIAL_TIME_ATTACK)){scd_ta.mode=0;return -1;}
    return 0;
}
/* Title time-out (IPX.asm Demo): returns 1 when a mode run started. Out of line, so
   the main loop's inlining stays as it was. */
static int frontend_demo_start(unsigned n);  /* zone demos: src/frontend_view.inc */
static __attribute__((noinline)) int special_attract(unsigned held){
    unsigned run=scd_special_modes()->attract(held);
    if(!run)return 0;
    if(run&SCD_ATTRACT_ZONE_DEMO)return !frontend_demo_start(run&3);
    return !(run>>8==SCD_SPECIAL_TIME_ATTACK?scd_special_ta_start(run&15):scd_special_mode_start(run&15,run>>8));
}
static void special_game_end(void){
    /* Main.asm Results: curSpecStage = specStageID (set by the Sub CPU exit). */
    if(special_return_act && special_game->next_stage)special_cur_stage=special_game->next_stage-1u;
    special_game_active=special_game_pending=0;scd_special_game_mailbox[27]=0;
    special_game_release();
    vdp2_sprite_priority_set(0,4);
    for(unsigned i=0;i<2;i++){const vdp2_scrn_ls_format_t ls={.scroll_screen=i?VDP2_SCRN_NBG1:VDP2_SCRN_NBG0};vdp2_scrn_ls_set(&ls);}
    /* From a big ring, gameplay resumes with the next act (src/main.c). */
    if(special_game_mode)scd_special_modes()->finish(special_game,&scd_special_mode_last);
    if(special_return_act || special_game_mode)special_finished=1;else special_load(1);
}
static unsigned special_game_sprite(vdp1_cmdt_t *cmd,const special_game_sprites *list,const scd_special_draw *d){
    if(d->kind!=SCD_SPECIAL_DRAW_SONIC)return special_effect_draw(cmd,d);
    const scd_special_pose *pose=&list->pose;
    if(!list->visible)return 0;
    memcpy((void *)VDP1_VRAM(0xb400),pose->pixels,pose->width*pose->height/2);
    memset(cmd,0,sizeof(*cmd));vdp1_cmdt_normal_sprite_set(cmd);
    const vdp1_cmdt_draw_mode_t mode={.color_mode=VDP1_CMDT_CM_CLUT_16,.end_code_disable=true,.user_clipping_mode=2};
    vdp1_cmdt_draw_mode_set(cmd,mode);vdp1_cmdt_char_size_set(cmd,pose->width,pose->height);
    vdp1_cmdt_char_base_set(cmd,VDP1_VRAM(0xb400));cmd->cmd_colr=0xb020/8;
    vdp1_cmdt_char_flip_set(cmd,(vdp1_cmdt_char_flip_t)(pose->flip<<4));
    cmd->cmd_xa=160+pose->x;cmd->cmd_ya=(int)list->sprite_y-128+pose->y;
    return 1;
}
/* VDP2 memory written right after the VBlank-in commit; then the current V-INT is kept for the next frame. */
static void special_game_commit(void){
    if(!special_game_pending)return;
    special_game_pending=0;scd_special_game *g=special_game;special_game_vdp2 *s=special_game_shown;
    const int results=g->h40;
    const uint16_t *colors=results?g->cram:s->cram,*hscroll=results?g->hscroll:s->hscroll;
    /* Colors first: they are small writes that must land within the vertical
       blank, before the results pattern clear or large name-table updates.
       Register 7 is palette entry 32 on the stage and entry 0 on the results
       screen; the back color lives in VDP2 VRAM. */
    const uint16_t back=colors[results?0:32];
    vdp2_scrn_back_color_set(VDP2_VRAM_ADDR(3,0x1bffe),(rgb1555_t){.raw=(uint16_t)(0x8000|(((back>>1)&7)*31/7)|((((back>>5)&7)*31/7)<<5)|((((back>>9)&7)*31/7)<<10))});
    volatile uint16_t *cram=(volatile uint16_t *)VDP2_CRAM_MODE_0_OFFSET(0,0,0);
    for(unsigned i=0;i<64;i++){
        unsigned c=colors[i],r=((c>>1)&7)*31/7,gr=((c>>5)&7)*31/7,b=((c>>9)&7)*31/7;
        cram[i]=(uint16_t)(0x8000|r|(gr<<5)|(b<<10));
    }
    if(results && !special_game_results_patterns)special_game_patterns(1);
    for(unsigned plane=0;plane<2;plane++){
        uint32_t dirty=results?g->main.dirty[plane]:s->dirty[plane];
        const uint16_t *tiles=results?(plane?g->main.plane_b:g->main.plane_a):s->plane[plane];
        volatile uint32_t *map=(volatile uint32_t *)VDP2_VRAM_ADDR(0,plane?0x14000:0x10000);
        for(unsigned row=0;row<32;row++)if(dirty>>row&1)for(unsigned col=0;col<64;col++){
            /* Plane A rows 16..27 hold the stage image; VDP1 draws that floor. */
            uint16_t tile=!plane && !results && row>=16 && row<28?0:tiles[row*64+col];
            map[row*64+col]=stage_saturn_pnd(tile,0);
        }
        if(!results)s->dirty[plane]=0;
        for(unsigned row=0;row<32;row++)if(g->main.dirty[plane]>>row&1)memcpy(s->plane[plane]+row*64,(plane?g->main.plane_b:g->main.plane_a)+row*64,64*sizeof(uint16_t));
        s->dirty[plane]|=g->main.dirty[plane];g->main.dirty[plane]=0;
    }
    /* Stage lines 128..223 show blank plane A tiles and plane B at scroll 0; write them once. */
    volatile uint32_t *lines[2]={(volatile uint32_t *)VDP2_VRAM_ADDR(0,0x18000),(volatile uint32_t *)VDP2_VRAM_ADDR(0,0x18400)};
    int offset=results?0:32;unsigned count=results || !special_game_lower_lines?224:128;special_game_lower_lines=!results;
    /* Row scroll stages (VDP mode %10) use each 8-line row's first entry. */
    const unsigned row_mask=results || scd_special_main_line_scroll(g->stage)?~0u:~7u;
    for(unsigned line=0;line<count;line++)for(unsigned plane=0;plane<2;plane++)
        lines[plane][line]=(uint32_t)fix16_int32_from((-(int)(int16_t)hscroll[(line&row_mask)*2+plane]-offset)&511);
    memcpy(s->cram,g->cram,sizeof(s->cram));memcpy(s->hscroll,g->hscroll,sizeof(s->hscroll));
    s->vsram_a=g->vsram_a;s->display=g->display;s->h40=g->h40;
}
static void special_game_present(void){
    const scd_special_game *g=special_game;const special_game_vdp2 *s=special_game_shown;
    const int results=g->h40;
    vdp2_scrn_scroll_y_set(VDP2_SCRN_NBG0,fix16_int32_from(results?g->vsram_a:s->vsram_a));
    vdp2_scrn_display_set((results?g->display:s->display)?VDP2_SCRN_DISPTP_NBG0|VDP2_SCRN_DISPTP_NBG1:0);
    special_game_pending=1;
    /* VDP1 plots the previous list from the frame change; vdp1_sync_wait()
       returns at VBlank-out, before a large floor sprite is drawn. Keep the
       command table and textures until the end code is fetched, and render
       floor rows meanwhile. */
    for(unsigned start=vblank_ticks;!vdp1_transfer_status_get().cef && vblank_ticks==start;)
        if(special_game_job_render(SPECIAL_GAME_WHILE_PLOTTING))special_game_job_advance(0);
    unsigned count=2;vdp1_cmdt_t *cmds=sprite_commands->cmdts;
    if(g->display && !g->h40){
        if(g->shown_image>=0 && g->shown_image!=special_game_uploaded){
            if(special_game_job_until(g->shown_image) && !special_game_error){special_slave_stop();special_game_error=3;}
            for(unsigned i=0;i<3;i++)if(special_game_images[i].update==g->shown_image){
                memcpy((void *)VDP1_VRAM(0x8000),special_game_images[i].texture,sizeof(special_game_images[i].texture));special_game_uploaded=g->shown_image;
            }
        }
        if(g->shown_image>=0 && g->shown_image==special_game_uploaded){
            vdp1_cmdt_t *cmd=cmds+count++;memset(cmd,0,sizeof(*cmd));vdp1_cmdt_normal_sprite_set(cmd);
            const vdp1_cmdt_draw_mode_t mode={.color_mode=VDP1_CMDT_CM_CLUT_16,.end_code_disable=true};
            vdp1_cmdt_draw_mode_set(cmd,mode);vdp1_cmdt_char_size_set(cmd,256,96);
            vdp1_cmdt_char_base_set(cmd,VDP1_VRAM(0x8000));cmd->cmd_colr=0xb000/8;cmd->cmd_xa=32;cmd->cmd_ya=128;
        }
        vdp1_cmdt_t *clip=cmds+count++;memset(clip,0,sizeof(*clip));vdp1_cmdt_user_clip_coord_set(clip);vdp1_cmdt_vtx_user_clip_coord_set(clip,INT16_VEC2(32,0),INT16_VEC2(287,223));
        const special_game_sprites *list=NULL;
        for(unsigned i=0;i<3;i++)if(special_game_lists[i].update==g->shown_sprites && g->shown_sprites>=0)list=special_game_lists+i;
        /* MD's earlier SAT entries win overlap; VDP1 draws later commands on top. */
        if(list)for(int i=list->count-1;i>=0;i--)count+=special_game_sprite(cmds+count,list,list->draws+i);
        /* The H32 picture is 256 pixels wide; keep both side borders black. */
        for(unsigned side=0;side<2;side++){
            vdp1_cmdt_t *cmd=cmds+count++;memset(cmd,0,sizeof(*cmd));vdp1_cmdt_polygon_set(cmd);
            const vdp1_cmdt_draw_mode_t mode={.color_mode=VDP1_CMDT_CM_RGB_32768,.end_code_disable=true};
            vdp1_cmdt_draw_mode_set(cmd,mode);cmd->cmd_colr=0x8000;
            cmd->cmd_xa=cmd->cmd_xd=side?288:0;cmd->cmd_xb=cmd->cmd_xc=side?319:31;cmd->cmd_ya=cmd->cmd_yb=0;cmd->cmd_yc=cmd->cmd_yd=223;
        }
    }
    memset(cmds+count,0,sizeof(vdp1_cmdt_t));vdp1_cmdt_end_set(cmds+count);sprite_commands->count=count+1;
    vdp1_sync_cmdt_list_put(sprite_commands,0);vdp1_sync_render();vdp1_sync();
    special_game_present_line=special_game_line();
}
static void special_game_frame(smpc_peripheral_digital_t pad){
    scd_special_game *g=special_game;
    if(vblank_ticks-special_game_frame_tick>1)special_game_late++;
    special_game_frame_tick=vblank_ticks;
    unsigned md=(pad.pressed.button.up?1:0)|(pad.pressed.button.down?2:0)|(pad.pressed.button.left?4:0)|(pad.pressed.button.right?8:0)|
        (pad.pressed.button.b?16:0)|(pad.pressed.button.c?32:0)|(pad.pressed.button.a?64:0)|(pad.pressed.button.start?128:0);
    /* The pad reads as released until the B press that started the stage is released. */
    if(special_game_entry_held && !(md&16))special_game_entry_held=0;
    if(special_game_entry_held)md=0;
    special_game_pad=md;
    int result=scd_special_game_vint(g,md);
    if(result<0 && !special_game_error)special_game_error=7;
    for(unsigned i=0;i<g->fm_count;i++)scd_audio_request(g->fm[i]);
    if(g->music==SCD_SPECIAL_MUSIC_PAUSE)scd_audio_pause(1);
    if(g->music==SCD_SPECIAL_MUSIC_RESUME)scd_audio_pause(0);
    if(g->music==SCD_SPECIAL_MUSIC_RESULTS)scd_audio_results();
    special_game_present();
    volatile uint32_t *mb=scd_special_game_mailbox;
    const scd_special_main *m=&g->main;const scd_special_world *w=&special_sonic_world;
    const special_game_sprites *list=NULL;
    for(unsigned i=0;i<3;i++)if(special_game_lists[i].update==g->shown_sprites && g->shown_sprites>=0)list=special_game_lists+i;
    /* [7..10] and [29] are addresses: tools/emulator_test.c hashes that memory. */
    const uint32_t values[]={g->vint,g->phase,g->routine,(uint32_t)g->updates,(uint32_t)g->shown_image,(uint32_t)g->shown_sprites,
        (uint32_t)(uintptr_t)g->cram,(uint32_t)(uintptr_t)m->plane_a,(uint32_t)(uintptr_t)m->plane_b,(uint32_t)(uintptr_t)g->hscroll,
        g->display|(g->h40<<1),g->vsram_a,m->score,m->lives,w->rings,w->timer,w->ufo_count,m->ring_bonus,m->time_bonus,m->results_timer,m->extra_players,g->paused,g->ctrl,g->time_stones,
        special_game_pad,special_game_error,special_game_active,++special_game_sequence,list?(uint32_t)(uintptr_t)list->draws:0,special_game_late,g->fm_count?g->fm[0]:0,g->music};
    for(unsigned i=0;i<sizeof(values)/sizeof(values[0]);i++)mb[1+i]=values[i];
    mb[34]=list?list->count:0;mb[35]=special_game_row_lines;mb[36]=special_game_present_line;mb[37]=special_game_forced;
    mb[38]=special_game_job.busy;mb[39]=special_game_job.rows;
    mb[0]=0x5353474d;
    if(result || special_game_error)special_game_end();
    else special_game_job_slice();
}
