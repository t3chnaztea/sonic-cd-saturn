/* Special stage mode entries (IPX.asm, Special Stage/Main.asm and Sub.asm), front-end
   overlay code: see src/special_modes.h. The mode program is src/special_game.c built
   again with SCD_SPECIAL_MODES_BUILD and every function renamed with the fe_ prefix. */
#define SCD_SPECIAL_MODES_BUILD
/* Own copies of the Main CPU program and progress helpers: resident callers keep
   their inlining, and every overlay symbol carries the fe_ prefix. */
#define fm(...) fe_sg_fm(__VA_ARGS__)
#define read_controller(...) fe_sg_read_controller(__VA_ARGS__)
#define sub_update(...) fe_sg_sub_update(__VA_ARGS__)
#define get_sub_data(...) fe_sg_get_sub_data(__VA_ARGS__)
#define half_loop_start(...) fe_sg_half_loop_start(__VA_ARGS__)
#define sub_exit(...) fe_sg_sub_exit(__VA_ARGS__)
#define stage_id(...) fe_sg_stage_id(__VA_ARGS__)
#define copy_hscroll(...) fe_sg_copy_hscroll(__VA_ARGS__)
#define exit_stage(...) fe_sg_exit_stage(__VA_ARGS__)
#define apply_ss1(...) fe_sm_apply_ss1(__VA_ARGS__)
#define apply_ss5(...) fe_sm_apply_ss5(__VA_ARGS__)
#define apply_ss6(...) fe_sm_apply_ss6(__VA_ARGS__)
#define draw_number(...) fe_sm_draw_number(__VA_ARGS__)
#define draw_tilemap(...) fe_sm_draw_tilemap(__VA_ARGS__)
#define draw_tilemaps(...) fe_sm_draw_tilemaps(__VA_ARGS__)
#define fnv(...) fe_sm_fnv(__VA_ARGS__)
#define inc_value(...) fe_sm_inc_value(__VA_ARGS__)
#define longword(...) fe_sm_longword(__VA_ARGS__)
#define prep_fade_from_white(...) fe_sm_prep_fade_from_white(__VA_ARGS__)
#define put_tile(...) fe_sm_put_tile(__VA_ARGS__)
#define results_number(...) fe_sm_results_number(__VA_ARGS__)
#define rol(...) fe_sm_rol(__VA_ARGS__)
#define ror(...) fe_sm_ror(__VA_ARGS__)
#define rows(...) fe_sm_rows(__VA_ARGS__)
#define scroll_speed(...) fe_sm_scroll_speed(__VA_ARGS__)
#define word(...) fe_sm_word(__VA_ARGS__)
#define section(...) fe_sm_section(__VA_ARGS__)
#define scd_special_main_add_score(...) fe_special_main_add_score(__VA_ARGS__)
#define scd_special_main_copy_hscroll(...) fe_special_main_copy_hscroll(__VA_ARGS__)
#define scd_special_main_cycle(...) fe_special_main_cycle(__VA_ARGS__)
#define scd_special_main_fade(...) fe_special_main_fade(__VA_ARGS__)
#define scd_special_main_hash(...) fe_special_main_hash(__VA_ARGS__)
#define scd_special_main_hud(...) fe_special_main_hud(__VA_ARGS__)
#define scd_special_main_open(...) fe_special_main_open(__VA_ARGS__)
#define scd_special_main_results(...) fe_special_main_results(__VA_ARGS__)
#define scd_special_main_results_vint(...) fe_special_main_results_vint(__VA_ARGS__)
#define scd_special_main_scroll(...) fe_special_main_scroll(__VA_ARGS__)
#define scd_special_main_stage(...) fe_special_main_stage(__VA_ARGS__)
#define scd_special_main_stone_palette(...) fe_special_main_stone_palette(__VA_ARGS__)
#define scd_special_main_tally(...) fe_special_main_tally(__VA_ARGS__)
#define scd_special_main_tally_check(...) fe_special_main_tally_check(__VA_ARGS__)
#define scd_special_main_timer(...) fe_special_main_timer(__VA_ARGS__)
#define scd_special_main_line_scroll(...) fe_special_main_line_scroll(__VA_ARGS__)
#define scd_special_stage_after(...) fe_special_stage_after(__VA_ARGS__)
#define scd_special_stage_exit(...) fe_special_stage_exit(__VA_ARGS__)
#define scd_special_stage_from_stones(...) fe_special_stage_from_stones(__VA_ARGS__)
#define scd_ending_good(...) fe_ending_good(__VA_ARGS__)
#define scd_special_game_vint(...) fe_special_game_vint(__VA_ARGS__)
#include "special_modes.h"
#include "frontend.h"
#ifndef SCD_ZONE_OVERLAY
/* Host builds (tools/test_special_game.py) have no front end: no zone demo data. */
int fe_demo_load(void){return 0;}
int fe_frontend_movie(unsigned id){(void)id;return -1;}
#endif
static unsigned fe_special_pad(scd_special_game *g,unsigned pad);
static void fe_special_exit(scd_special_game *g);
static int fe_special_fade(scd_special_game *g);
#include "special_main.c"
#include "special_game.c"
static const uint8_t *fe_demo_data;
static unsigned fe_demo_size,fe_demo_pos;
static uint8_t fe_demo_id,fe_ta_stage;
/* Sub.asm Start: time attack counts up from 0 instead of the 100-second countdown. */
static void fe_special_begin(scd_special_world *w,unsigned flags,const uint8_t *demo){
    w->mode=(uint8_t)flags;w->time_attack=flags>>1&1;if(flags&2)w->timer=0;
    fe_demo_data=demo;fe_demo_size=demo?1024:0;fe_demo_pos=0;
}
/* RunDemo: in temporary mode without the secret flag, demoData replaces the pad until a
   real Start press. demoData is $700 bytes cleared at Start; past the decompressed demo
   it reads as no input. */
static unsigned fe_special_pad(scd_special_game *g,unsigned pad){
    if((g->flags&5)!=1)return pad;
    if(pad&0x80)g->demo_active=0;
    else if(g->demo_active){pad=fe_demo_pos<fe_demo_size?fe_demo_data[fe_demo_pos]:0;fe_demo_pos++;}
    return pad;
}
/* One VSync step: FadeToBlack subtracts 0, 2, .. 14 from each channel in turn; a won
   secret stage uses FadeToWhite. */
static void fe_special_fade_step(scd_special_game *g){
    scd_special_main *m=&g->main;
    if((g->flags&4) && !g->lost)fe_special_main_fade(m,0,g->step);
    else{
        /* Channel units: red, green, blue (SH-2 has no variable shift). */
        static const uint16_t fe_unit[3]={1,16,256};
        unsigned u=fe_unit[g->step/8],mask=0xe*u,d0=2*(g->step%8)*u;
        for(unsigned i=0;i<64;i++){
            unsigned c=m->palette[i],channel=c&mask;
            m->palette[i]=(uint16_t)((c&~mask)|(channel>d0?channel-d0:0));
        }
    }
    g->step++;g->cram_dirty=1;
}
/* Main.asm .Exit without results: time attack keeps the time (exit_timer) and marks a
   win in lives; .MarkDone clears ctrlData; the warp sound plays and the screen fades.
   vintRoutine stays as it was. */
static void fe_special_exit(scd_special_game *g){
    if(g->flags&2)g->main.lives=g->lost?0:1;
    g->ctrl=0;fe_sg_fm(g,FM_SSWARP);
    g->step=0;g->phase=SCD_SPECIAL_GAME_EXIT_FADE;fe_special_fade_step(g);
}
static int fe_special_fade(scd_special_game *g){
    if(g->step<24){fe_special_fade_step(g);return 0;}
    g->phase=SCD_SPECIAL_GAME_DONE;return 1;
}
/* IPX.asm Demo: demoID picks the scene, then advances and wraps after 5: opening FMV,
   R11A, Special Stage 1, R43C, Special Stage 6, R82A. */
static unsigned fe_special_attract(unsigned held){
    if(held&1)return 8|(SCD_SPECIAL_TEMPORARY|SCD_SPECIAL_SECRET)<<8;
    if(held&2){fe_ta_stage=fe_ta_stage%7+1;return fe_ta_stage|SCD_SPECIAL_TIME_ATTACK<<8;}
    unsigned id=fe_demo_id;fe_demo_id=fe_demo_id>=5?0:fe_demo_id+1;
    /* Demo_OpenFMV: the opening movie, then the title again. */
    if(!id){fe_frontend_movie(0|FE_MOVIE_FROM_TITLE);return 0;}
    return id==2?1|SCD_SPECIAL_TEMPORARY<<8:id==4?6|SCD_SPECIAL_TEMPORARY<<8:
        (id&1) && fe_demo_load()?SCD_ATTRACT_ZONE_DEMO|id>>1:0;
}
static void fe_special_finish(const scd_special_game *g,scd_special_mode_result *r){
    uint32_t t=g->exit_timer;
    r->frames=g->flags&2?((t>>16&255)*60+(t>>8&255))*60+(t&255):0;
    r->stage=g->stage;r->flags=g->flags;r->aborted=g->lost!=0;r->pending=1;
}
static int fe_special_vint(scd_special_game *g,unsigned pad){return fe_special_game_vint(g,pad);}
#ifdef SCD_ZONE_OVERLAY
int fe_ss8_credits_run(void);
#define FE_SPECIAL_CREDITS fe_ss8_credits_run
#else
#define FE_SPECIAL_CREDITS 0 /* Host builds: no VDP2. */
#endif
const scd_special_mode_ops fe_special_zone_ops={fe_special_vint,fe_special_begin,fe_special_attract,fe_special_finish,FE_SPECIAL_CREDITS};
