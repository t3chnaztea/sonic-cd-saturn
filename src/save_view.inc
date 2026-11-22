#include "player_plus.h"
/* RAM DATA uses the existing HUD alphabet. The retail title/menu art and
   navigation are unchanged; Continue availability follows verified storage. */
static void save_panel_begin(unsigned mode){
    save_panel=mode;
    gameplay_clear_wait();vdp1_sync_wait();vdp1_sync_interval_set(-1);
    hud_original_upload();act_fade_offset(0);vdp2_scrn_display_set(0);
    vdp2_scrn_back_color_set(VDP2_VRAM_ADDR(3,0x1bffe),(rgb1555_t){.raw=0x8000});
    vdp2_tvmd_display_set();
}
/* MODE row (docs/CDPP-PRESET-SPEC.md section 6): Left or Right switches Classic
   and the CD++ preset and writes SCDSATURNCF at once. The panel loop in main.c
   keeps A/C/Start and B; the row reads the pad this loop already processed
   (Yaul's held is the press edge). The next act start reads the setting. */
static int save_mode_status=-1;
static void save_mode_input(void){
    smpc_peripheral_digital_t pad;smpc_peripheral_digital_port(1,&pad);
    if(!pad.held.button.left && !pad.held.button.right)return;
    scd_preset_flags=scd_preset_flags?0:SCD_PLUS_PRESET;
    scd_settings settings={scd_preset_flags?1:0,scd_preset_flags};
    input_ready=0;save_mode_status=scd_settings_store(&settings);input_ready=1;
    scd_plus_publish();
}
static void save_panel_draw(void){
    unsigned count=2;char text[40];
    if(save_panel==1)save_mode_input();
    hud_panel(&count,16,24,288,184,0x8800);
    hud_text(&count,128,36,"RAM DATA");
    if(save_panel==2){
        hud_text(&count,40,72,"START A NEW GAME?");
        hud_text(&count,40,96,"REPLACES SAVED PROGRESS");
        hud_text(&count,40,144,"A CONFIRM    B CANCEL");
    }else{
        snprintf(text,sizeof(text),"MODE %-7s  LEFT RIGHT%s",scd_preset_flags?"CD++":"CLASSIC",save_mode_status>0?" NOT SAVED":"");
        hud_text(&count,32,46,text);
        hud_text(&count,32,60,scd_save_message(save_state.status));
        if(save_state.valid){
            const scd_save_progress *p=&save_state.saved;
            hud_text(&count,32,84,LS_ZONES[p->zone]);
            snprintf(text,sizeof(text),"ACT %u  %s",p->act+1,p->completed?"CLEARED":names[p->era]);hud_text(&count,32,100,text);
            unsigned stones=0;for(unsigned i=0;i<7;i++)stones+=(p->time_stones>>i)&1;
            snprintf(text,sizeof(text),"TIME STONES %u/7",stones);hud_text(&count,32,116,text);
            snprintf(text,sizeof(text),"GOOD ACTS %c %c",p->good_acts&1?'1':'-',p->good_acts&2?'2':'-');
            hud_text(&count,32,132,text);
            memcpy(text,"GOOD ZONES ",11);
            for(unsigned i=0;i<7;i++)text[11+i]=p->good_zones&(1u<<i)?'1'+i:'-';
            text[18]=0;hud_text(&count,32,148,text);
        }else hud_text(&count,32,100,"CONTINUE NOT AVAILABLE");
        if(save_state.dirty)hud_text(&count,32,164,"LATEST PROGRESS NOT SAVED");
        hud_text(&count,32,184,save_state.dirty?"A RETRY SAVE    B BACK":"A CHECK RAM     B BACK");
    }
    memset(sprite_commands->cmdts+count,0,sizeof(vdp1_cmdt_t));
    vdp1_cmdt_end_set(sprite_commands->cmdts+count);sprite_commands->count=count+1;
    gameplay_clear_wait();vdp1_sync_cmdt_list_put(sprite_commands,0);vdp1_sync_render();
    while(!vdp1_transfer_status_get().cef) {}
    vdp1_sync();
}
static void continue_game(void){
    scd_save_progress p=save_state.saved;
    /* Starting an act always resets position, score, rings and lives. */
    /* IPX.asm ReadSaveData: stones, good futures and svSpecStage are in place before
       the act loads, so LevelStart's all-stones good future applies to its first load. */
    new_game_at(p.zone,p.act,p.era,&p);
    save_session=1;
    /* A pending checkpoint belongs to the previous session; Continue chooses
       the verified checkpoint explicitly, so an old retry cannot replace it. */
    save_state.dirty=0;save_publish();
}
