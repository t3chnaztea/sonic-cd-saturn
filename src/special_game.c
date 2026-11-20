/* Special Stage program flow from Main.asm, one V-INT per call. */
#include "special_game.h"
#include "special_modes.h"
#include "special_progress.h"
#include <string.h>
enum {FM_KACHING=0x9a,FM_TALLY=0xbd,FM_SSWARP=0xc8};
static void fm(scd_special_game *g,unsigned id){if(g->fm_count<sizeof(g->fm))g->fm[g->fm_count++]=(uint8_t)id;}
/* Mode runs (IPX.asm temporary, time attack and secret entries) use the front-end
   overlay copy of this file (src/special_modes.c, SCD_SPECIAL_MODES_BUILD), which
   adds the mode code below; the resident copy dispatches to it through this
   volatile pointer, so LTO cannot inline overlay code here. */
#ifndef SCD_SPECIAL_MODES_BUILD
const scd_special_mode_ops *const volatile scd_special_mode_ops_ref=&fe_special_zone_ops;
#endif
/* ReadController: tapped buttons are new presses; Start toggles pause when enabled.
   A mode run's RunDemo may replace the pad. */
static void read_controller(scd_special_game *g,unsigned pad){
#ifdef SCD_SPECIAL_MODES_BUILD
    pad=fe_special_pad(g,pad);
#endif
    unsigned hold=pad&255,tap=(hold^(g->ctrl>>8))&hold;
    g->ctrl=(uint16_t)(hold<<8|tap);
    if((tap&0x80) && (g->paused&0x80))g->paused^=1;
}
/* UpdateStage: the Sub CPU update reads the controller data from the
   previous half loop's V-INT 0/2, before this half loop's V-INT reads again. */
static int sub_update(scd_special_game *g){
    if(g->sub_over)return 0;
    memset(g->world->sound,0,sizeof(g->world->sound));
    int result=g->update(g->context,g->ctrl>>8,g->ctrl&255);
    g->updates++;g->pending_over=g->world->stage_over || g->world->got_time_stone;
    return result;
}
static void get_sub_data(scd_special_game *g){
    g->copied=g->updates-1;g->main.scroll_flags=g->player->scroll;g->player->scroll=0;
    for(unsigned i=0;i<3;i++)if(g->world->sound[i])fm(g,g->world->sound[i]);
}
static int half_loop_start(scd_special_game *g){
    if(g->paused&1){g->saved_ctrl=g->ctrl;g->saved_routine=g->routine;g->routine=7;g->phase=SCD_SPECIAL_GAME_PAUSE;g->music=SCD_SPECIAL_MUSIC_PAUSE;return 0;}
    if(sub_update(g))return -2;
    scd_special_main_scroll(&g->main,g->pack,1,g->sub_over);
    g->routine=g->half&1?2:0;g->sub=0;g->phase=SCD_SPECIAL_GAME_LOOP;
    return 0;
}
#ifndef SCD_SPECIAL_MODES_BUILD
int scd_special_game_start(scd_special_game *g,const scd_special_main_pack *pack,scd_special_world *world,scd_special_player *player,
    scd_special_game_update update,void *context,uint32_t score,uint32_t next_life,uint8_t lives,uint8_t time_stones,uint8_t stage){
    if(!pack || !world || !player || !update || stage<1 || stage>8)return -1;
    memset(g,0,sizeof(*g));g->flags=world->mode&7;
    g->pack=pack;g->world=world;g->player=player;g->update=update;g->context=context;
    g->main.score=score;g->main.next_life=next_life;g->main.lives=lives;g->time_stones=time_stones;g->stage=stage;
    if(scd_special_main_stage(&g->main,pack,stage,world->time_attack))return -1;
    /* stageHScroll1 keeps LoadSS1Data's cleared d1; stageHScroll2 shows columns 32..63. */
    g->stage_scroll[0]=0;g->stage_scroll[1]=0x100;
    g->image[0]=g->image[1]=g->shown_image=g->shown_sprites=-1;
    g->music=SCD_SPECIAL_MUSIC_STAGE;
    if(sub_update(g))return -2;
    get_sub_data(g);
    g->cram_dirty=1;g->routine=0;g->phase=SCD_SPECIAL_GAME_FADE_IN;
    return 0;
}
#endif
/* Sub CPU .StageBeaten/.Exit: retrieved stone bit and the next stage ID. */
static void sub_exit(scd_special_game *g){
    g->next_stage=(uint8_t)(scd_special_stage_exit(g->stage-1u,&g->time_stones,g->world->got_time_stone)+1);
}
/* specStageID: the Sub CPU sets it to the next stage when the stage ends.
   PaletteCycle, CopyHScroll and ShowStageBuffer dispatch on it; the next
   stage's cycle program data is still at its first call. */
static unsigned stage_id(const scd_special_game *g){return g->sub_over?g->next_stage:g->stage;}
/* CopyHScroll for row scroll stages (the VDP H-scroll mode LoadSSnData set). */
static void copy_hscroll(scd_special_game *g){
    unsigned id=stage_id(g);
    if(!g->main.scroll_disable && !g->sub_over && !scd_special_main_line_scroll(id))scd_special_main_copy_hscroll(&g->main,id,g->hscroll);
}
static void exit_stage(scd_special_game *g){
    scd_special_world *w=g->world;
    g->lost=w->ufo_count;g->paused=0;g->main.scroll_disable=1;
    g->exit_rings=w->rings;g->exit_timer=w->timer;
#ifdef SCD_SPECIAL_MODES_BUILD
    if(g->flags&3){fe_special_exit(g);return;} /* Main.asm .Exit without results. */
#endif
    /* Results computes both bonuses before its fade to white. */
    g->main.ring_bonus=(uint32_t)w->rings*20u;g->main.time_bonus=(uint32_t)(uint16_t)w->timer*20u;
    g->routine=6;g->phase=SCD_SPECIAL_GAME_EXIT_FADE;
    scd_special_main_fade(&g->main,0,0);g->step=1;g->cram_dirty=1;
}
int scd_special_game_vint(scd_special_game *g,unsigned pad){
#ifndef SCD_SPECIAL_MODES_BUILD
    if(g->flags)return scd_special_modes()->vint(g,pad);
#endif
    scd_special_main *m=&g->main;
    if(g->phase==SCD_SPECIAL_GAME_DONE)return 1;
    g->fm_count=0;g->music=0;
    /* VInterrupt */
    if(g->cram_dirty){memcpy(g->cram,m->palette,sizeof(g->cram));g->cram_dirty=0;}
    switch(g->routine){
    case 0:case 2:{
        unsigned buffer=g->routine?0:1;
        g->shown_image=g->image[buffer];
        /* ShowStageBuf1/2: DMA per line, or one entry per 8-line row. */
        if(scd_special_main_line_scroll(stage_id(g)))for(unsigned line=128;line<224;line++){g->hscroll[line*2]=g->stage_scroll[buffer];g->hscroll[line*2+1]=0;}
        else for(unsigned line=128;line<224;line+=8)g->hscroll[line*2]=buffer?0x100:0;
        if(scd_special_main_line_scroll(stage_id(g))){if(!m->scroll_disable && !g->sub_over)memcpy(g->hscroll,m->hscroll,256*sizeof(uint16_t));}
        else copy_hscroll(g);
        read_controller(g,pad);
        break;
    }
    case 1:case 3:
#ifdef SCD_SPECIAL_MODES_BUILD
        /* Sub.asm MainLoop ends its update by reading ctrlData live: in temporary
           mode, Start from this half loop's V-INT 0/2 read exits the stage. */
        if((g->flags&1) && (g->ctrl&0x8000))g->pending_over=1;
#endif
        if(g->pending_over && !g->sub_over){g->sub_over=1;sub_exit(g);}
        copy_hscroll(g);
        g->image[g->routine==1?0:1]=g->copied;g->shown_sprites=g->copied;
        if(scd_special_main_cycle(m,g->pack,stage_id(g)))g->cram_dirty=1;
        break;
    case 4:copy_hscroll(g);break;
    case 5:scd_special_main_results_vint(m,g->pack);read_controller(g,pad);break;
    case 7:read_controller(g,pad);break;
    }
    if(g->routine!=5 && m->results_timer)m->results_timer--;
    g->vint++;
    /* Main program until the next VSync */
    switch(g->phase){
    case SCD_SPECIAL_GAME_FADE_IN:
        g->display=1;
        if(g->step<24){scd_special_main_fade(m,1,g->step++);g->cram_dirty=1;return 0;}
        g->paused=0x80;g->demo_active=1; /* Main.asm: demoActive is set after the fade. */
        return half_loop_start(g);
    case SCD_SPECIAL_GAME_PAUSE:
        /* Sub.asm .PauseLoop: in time attack, A, B or C held while paused exits.
           The next stage ID (specStageID) is not used after a time attack exit. */
#ifdef SCD_SPECIAL_MODES_BUILD
        if((g->flags&2) && (g->ctrl&0x7000)){g->ctrl=g->saved_ctrl;g->routine=g->saved_routine;g->sub_over=1;goto exit;}
#endif
        if(g->paused&1)return 0;
        g->ctrl=g->saved_ctrl;g->routine=g->saved_routine;g->music=SCD_SPECIAL_MUSIC_RESUME;
        return half_loop_start(g);
    case SCD_SPECIAL_GAME_LOOP:
        if(g->sub==0){
            scd_special_world *w=g->world;
            scd_special_main_hud(m,g->pack,w->rings,w->ufo_count);
            uint8_t delay=m->stone_delay;scd_special_main_stone_palette(m,g->pack,w->ufo_count);
            if(delay==1 && !m->stone_delay)g->cram_dirty=1;
            scd_special_main_scroll(m,g->pack,2,g->sub_over);
            g->routine=g->half&1?3:1;g->sub=1;return 0;
        }
        if(g->sub==1){
            scd_special_main_timer(m,g->pack,g->world->timer);
            scd_special_main_scroll(m,g->pack,3,g->sub_over);
            g->routine=4;g->sub=2;return 0;
        }
#ifdef SCD_SPECIAL_MODES_BUILD
        if(0)exit:g->sub_over=1;
#endif
        if(g->sub_over){exit_stage(g);return 0;}
        get_sub_data(g);g->half++;
        return half_loop_start(g);
    case SCD_SPECIAL_GAME_EXIT_FADE:
#ifdef SCD_SPECIAL_MODES_BUILD
        if(g->flags&3)return fe_special_fade(g);
#endif
        if(g->step<24){scd_special_main_fade(m,0,g->step++);g->cram_dirty=1;return 0;}
        g->music=SCD_SPECIAL_MUSIC_RESULTS;g->display=0;
        scd_special_main_results(m,g->pack,g->exit_rings,g->exit_timer,g->time_stones);
        g->vint=0;g->routine=5;g->paused=0;g->h40=1;g->vsram_a=0x10;
        memset(g->hscroll,0,sizeof(g->hscroll));g->shown_image=g->shown_sprites=-1;
        g->cram_dirty=1;g->step=0;g->phase=SCD_SPECIAL_GAME_RESULTS_FADE_IN;
        return 0;
    case SCD_SPECIAL_GAME_RESULTS_FADE_IN:
        g->display=1;
        if(g->step<24){scd_special_main_fade(m,1,g->step++);g->cram_dirty=1;return 0;}
        m->results_timer=8*60;m->extra_players=0;g->phase=SCD_SPECIAL_GAME_RESULTS;
        if(scd_special_main_tally(m))fm(g,FM_TALLY);
        return 0;
    case SCD_SPECIAL_GAME_RESULTS:{
        unsigned check=scd_special_main_tally_check(m,g->ctrl&255);
        if(check&1)fm(g,FM_KACHING);
        if(check&2){
            scd_special_main_add_score(m,m->ring_bonus+m->time_bonus);fm(g,FM_SSWARP);
            g->phase=SCD_SPECIAL_GAME_RESULTS_FADE_OUT;scd_special_main_fade(m,0,0);g->step=1;g->cram_dirty=1;
            return 0;
        }
        if(scd_special_main_tally(m))fm(g,FM_TALLY);
        return 0;
    }
    case SCD_SPECIAL_GAME_RESULTS_FADE_OUT:
        if(g->step<24){scd_special_main_fade(m,0,g->step++);g->cram_dirty=1;return 0;}
        g->phase=SCD_SPECIAL_GAME_DONE;return 1;
    }
    return 0;
}
#ifndef SCD_SPECIAL_MODES_BUILD
uint32_t scd_special_game_hash(const scd_special_game *g){
    uint32_t h=scd_special_main_hash(&g->main);
    const uint16_t values[]={g->vint,g->routine,g->ctrl,g->step,g->half,g->phase,g->sub,g->paused,g->display,g->h40,g->cram_dirty,g->sub_over,g->pending_over,
        g->lost,g->next_stage,g->time_stones,(uint16_t)g->updates,(uint16_t)g->copied,(uint16_t)g->image[0],(uint16_t)g->image[1],(uint16_t)g->shown_image,(uint16_t)g->shown_sprites};
    for(unsigned i=0;i<sizeof(values)/sizeof(values[0]);i++){h=(h^(values[i]>>8))*16777619u;h=(h^(values[i]&255))*16777619u;}
    for(unsigned i=0;i<64;i++){h=(h^(g->cram[i]>>8))*16777619u;h=(h^(g->cram[i]&255))*16777619u;}
    for(unsigned i=0;i<448;i++){h=(h^(g->hscroll[i]>>8))*16777619u;h=(h^(g->hscroll[i]&255))*16777619u;}
    return h;
}
#endif
