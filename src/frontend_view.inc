#include "stage_select.h"
#include "player_plus.h"
/* Front-end screens (src/frontend.h): Time Attack and the sound test. Their logic is
   fe_ overlay code; this resident glue draws with the HUD alphabet the way the
   level select and RAM DATA panels do, and starts or ends Time Attack runs.
   Included by src/main.c after save_view.inc. */
static unsigned frontend_screen,frontend_count;
static unsigned frontend_last_pad;
void scd_frontend_text(int x,int y,const char *text){
    /* sprite_init allocates 189+SCD_OBJECT_CAPACITY commands; keep the end slot. */
    if(frontend_count+strlen(text)+1>=189+SCD_OBJECT_CAPACITY)return;
    hud_text(&frontend_count,x,y,text);
}
void scd_frontend_panel(int x,int y,int width,int height,uint16_t color){
    if(frontend_count+2>=189+SCD_OBJECT_CAPACITY)return;
    hud_panel(&frontend_count,x,y,width,height,color);
}
/* The front-end overlay must be in place before any fe_ call. */
static const scd_frontend_ops *frontend_ops(void){
    scd_frontend_overlay_load();
    return scd_zone_code_ready(SCD_ZONE_FRONTEND)?scd_frontend_ops_get():NULL;
}
static void frontend_begin(unsigned screen){
    const scd_frontend_ops *ops=frontend_ops();
    if(!ops){title_begin(1);return;}
    gameplay_clear_wait();vdp1_sync_wait();vdp1_sync_interval_set(-1);
    hud_original_upload();act_fade_offset(0);vdp2_scrn_display_set(0);
    vdp2_scrn_back_color_set(VDP2_VRAM_ADDR(3,0x1bffe),(rgb1555_t){.raw=0x8000});
    vdp2_tvmd_display_set();
    frontend_screen=screen;frontend_last_pad=0xFF;
    ops->enter(screen);
}
static unsigned frontend_pad(const smpc_peripheral_digital_t *pad){
    /* Yaul's pressed is the current level (see the title branch in main()). */
    return (pad->pressed.button.up?SCD_PAD_UP:0)|(pad->pressed.button.down?SCD_PAD_DOWN:0)|
        (pad->pressed.button.left?SCD_PAD_LEFT:0)|(pad->pressed.button.right?SCD_PAD_RIGHT:0)|
        (pad->pressed.button.b?SCD_PAD_B:0)|(pad->pressed.button.c?SCD_PAD_C:0)|
        (pad->pressed.button.a?SCD_PAD_A:0)|(pad->pressed.button.start?SCD_PAD_START:0);
}
/* IPX.asm TimeAttack .Selections and StageSels: acts 1 and 2 in the present,
   act 3 in the good future (R13C...R83C). */
static void time_attack_start(void){
    unsigned entry=scd_ta.entry;
    scd_ta.mode=1;scd_ta.aborted=0;scd_ta.pending=0;scd_ta.frames=0;scd_ta.seen=0;
    if(entry>=SCD_TA_ACTS){
        /* Special stage column: IPX.asm TimeAttack_SS (src/special_modes.h). */
        frontend_screen=0;
        if(!scd_special_ta_start(entry-SCD_TA_ACTS+1))return;
        scd_ta.mode=0;scd_ta.aborted=1;scd_ta.pending=1;frontend_begin(SCD_FE_TIME_ATTACK);return;
    }
    frontend_screen=0;
    new_game_at(entry/3,entry%3,entry%3==2?2:0,NULL);
    /* Level/Main.asm:51: one life in Time Attack. */
    scd_player_progress progress=scd_player_progress_get();progress.lives=1;scd_player_progress_set(progress);
    save_session=0;
}
/* The run's fade-out ended (act clear, game over or a pause exit): record the
   clock (IPX.asm:1236 timeAttackTime) and return to the menu. */
static void time_attack_finish(int cleared){
    scd_ta.frames=scd_player_get().elapsed;scd_ta.aborted=!cleared;
    scd_ta.mode=0;scd_ta.pending=1;
    act_fade=0;fade_white=0;paused=0;
    frontend_begin(SCD_FE_TIME_ATTACK);
}
/* One front-end frame; returns 0 when the screen has handed control elsewhere. */
/* Root owns normal single-program and remaining extra-scene lifecycles.
   Deliberately no fallback implementation: this prepared integration is blocked
   until WARP and COMMING have faithful presenters, not public placeholders. */
static void stage_select_scene_start(fe_stage_select_choice choice,unsigned previous_hold);
static void stage_select_start(unsigned selected){
    const scd_frontend_ops *ops=frontend_ops();
    fe_stage_select_choice choice;unsigned previous_hold;
    if(!ops || !ops->stage_select_snapshot(selected,&choice,&previous_hold)){
        title_begin(1);return;
    }
    stage_select_scene_start(choice,previous_hold);
}
static void frontend_frame(const smpc_peripheral_digital_t *pad){
    const scd_frontend_ops *ops=frontend_ops();
    if(!ops){frontend_screen=0;title_begin(1);return;}
    unsigned hold=frontend_pad(pad),tap=hold&~frontend_last_pad;frontend_last_pad=hold;
    frontend_count=2;
    unsigned result=ops->step(hold,tap);
    if(result==SCD_FE_CONTINUE){
        /* 'FEND', the screen and the pad, so a harness can see the menu. */
        scd_trace_mailbox[0]=0x46454e44;scd_trace_mailbox[1]=frames;scd_trace_mailbox[2]=frontend_screen|hold<<8;
        memset(sprite_commands->cmdts+frontend_count,0,sizeof(vdp1_cmdt_t));
        vdp1_cmdt_end_set(sprite_commands->cmdts+frontend_count);sprite_commands->count=frontend_count+1;
        gameplay_clear_wait();
        sonic_texture_wait();vdp1_sync_cmdt_list_put(sprite_commands,0);vdp1_sync_render();
        while(!vdp1_transfer_status_get().cef) {}
        vdp1_sync();
        frames++;sync_frame();
        return;
    }
    unsigned screen=frontend_screen;frontend_screen=0;
    if(result==SCD_FE_TA_START)time_attack_start();
    else if((result&255)==SCD_FE_STAGE_SELECT_CHOICE)stage_select_start(result>>8);
    /* Visual Mode after a movie: its screen again (the display was off). */
    else if(result==SCD_FE_REDRAW)frontend_begin(screen);
    /* Sound test 07/07/07 (SoundTest_SpecStg8): Special Stage 8, temporary and secret
       (IPX.asm:1065); it returns to the title. */
    else if(result==SCD_FE_SPECIAL8){if(scd_special_ss8_start())title_begin(1);}
    else title_begin(1);
}
/* Zone attract demos (IPX.asm Demo: R11A, R43C, R82A). cd/DEMOS.BIN holds the retail
   input (tools/prepare_demos.py): 0x800 pad words each, hold << 8 | tap, read into the
   title pack region, which title_begin(1) reads again afterwards. ReadControllers
   (Level/Functions (General).asm) takes one word per V-INT from the program's first
   frame, so retail uses word levelFrames + 22 (R11A) or + 41 (R43C, R82A) at each
   update, from Sonic's first unlocked update (R11A 148: ctrlLocked clears during 147; R43C and R82A have no title
   card and start where tools/retail_demo_probe.py measures them). The native card
   holds controls longer, so the words start at that first unlocked update. The demo
   returns to the title when the words run out (demoDataIndex $800,
   Level/Main.asm:405), on Start (.IsDemo) or on a game over. */
static unsigned demo_slot,demo_frame,demo_started;
static const struct {uint8_t zone,act,era;uint16_t first,x,y;} demo_levels[3]={
    {0,0,0,148+22,0,0},{2,2,2,1+41,976,940},{6,1,0,1+41,6947,1484}};
static int frontend_demo_start(unsigned n){
    /* fe_demo_load (src/frontend.c) has read cd/DEMOS.BIN. */
    if(n>=3)return -1;
    frontend_screen=0;
    /* Retail input: the demo runs Classic whatever MODE says (title_begin ends the hold). */
    scd_plus_classic_hold(1);
    new_game_at(demo_levels[n].zone,demo_levels[n].act,demo_levels[n].era,NULL);
    if(demo_levels[n].x){
        scd_title_card_stop();
        scd_player_place(demo_levels[n].x,demo_levels[n].y,0,0,0);player=scd_player_get();
        /* The level loaded its objects around the spawn camera; the demo program
           starts at this camera, so the spawner starts again here (retail DEMO82A:
           the BEAM at 7033,1415 is live at levelFrames 1 and fires at 2). */
        scd_objects_respawn();
        camera_y=scd_camera_v_begin(stage_zone,stage_act,era,player.y/65536,player.resets);camera_x=scd_camera_h();
        /* The water follows the start camera (tools/tt_route_search.c TT_ROUTE_PLACE). */
        water_camera(camera_x,camera_y);water_reset(stage_zone,stage_act,era);
    }
    save_session=0;demo_slot=n+1;demo_frame=demo_started=0;
    return 0;
}
/* SCD_* buttons for this update from the held byte (Mega Drive U D L R B C A). */
static unsigned frontend_demo_buttons(void){
    /* Words wait while the card locks controls or the act fades in (no update runs). */
    if(scd_title_card_locked() || act_fade)return 0;
    if(!demo_started){
        demo_started=1;demo_frame=demo_levels[demo_slot-1].first;
        /* Without a card, retail's first update is ObjSonic_Init: it reads word `first`
           and moves nothing; the next update reads first + 1. */
        if(demo_levels[demo_slot-1].x){demo_frame++;return 0;}
    }
    const uint8_t *data=STAGE_PACK_DATA(PACK_TITLE)+(demo_slot-1)*0x1000u+demo_frame*2u;
    unsigned hold=data[0];demo_frame++;
    return (hold&1?SCD_UP:0)|(hold&2?SCD_DOWN:0)|(hold&4?SCD_LEFT:0)|(hold&8?SCD_RIGHT:0)|(hold&0x70?SCD_JUMP:0);
}
