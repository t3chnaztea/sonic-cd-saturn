/* Source Sonic motion/contact inspection with the original object dispatch. */
static scd_special_art special_sonic_art;
static scd_special_player special_sonic_player;
static scd_special_sprite special_sonic_sprite;
static scd_special_pose special_sonic_pose;
static scd_special_world special_sonic_world;
static scd_special_art special_effect_art,special_ufo_art;
static scd_special_stage_state special_stage_state;
static unsigned special_ufo_paths_size;
static unsigned special_sonic_tick,special_sonic_steps,special_sonic_taps,special_contact_case;
static int special_sonic_mode,special_sonic_frozen,special_sonic_visible;

/* Explicit semantic words, independent of SH-2/host structure padding. */
volatile uint32_t scd_special_contact_trace[8+8*79];
static void special_contact_record(unsigned held,unsigned tapped){
    const scd_special_player *p=&special_sonic_player;
    const scd_special_sprite *s=&special_sonic_sprite;
    const scd_special_world *w=&special_sonic_world;
    const uint32_t words[]={
        p->x,p->y,p->yaw,p->sprite_y,p->sprite_velocity,p->z,p->speed,p->top_speed,p->shoes,p->jump_timer,p->bump_time,p->routine,p->flags,p->scroll,
        p->hurt,p->stamp_c,p->stamp_tl,p->stamp_tr,p->stamp_br,p->stamp_bl,p->orientation,p->x_velocity,p->y_velocity,
        s->tilt,s->animation,s->frame,s->time,s->time_copy,s->art,
        w->timer,w->rings,w->splash_timer,
        w->dust[0],w->dust[1],w->dust[2],w->dust[3],w->dust[4],w->dust[5],w->dust[6],w->dust[7],
        w->timer_frames,w->speedup,w->inactive,w->stopped,w->time_attack,w->stage_over,w->ufo_count,w->time_ufo,
        w->sound[0],w->sound[1],w->sound[2],
        w->lost_rings[0],w->lost_rings[1],w->lost_rings[2],w->lost_rings[3],w->lost_rings[4],w->lost_rings[5],w->lost_rings[6],
        w->splash_id,w->splash_routine,w->splash_flags,w->splash_animation,w->splash_frame,w->splash_time,
        w->ring_bonus,w->got_time_stone,w->time_stone[0],w->time_stone[1],w->time_stone[2]};
    unsigned sequence=scd_special_contact_trace[1]+1;
    volatile uint32_t *out=scd_special_contact_trace+8+(sequence%8)*79;
    out[1]=special_stage.stage;out[2]=special_sonic_steps;out[3]=held;out[4]=tapped;out[5]=special_animation.delay;
    for(unsigned i=0;i<69;i++)out[6+i]=words[i];
    out[75]=special_sonic_frozen;out[76]=special_contact_case;
    out[77]=scd_special_effects_hash(&special_stage_state.effects);out[78]=scd_special_stage_hash(&special_stage_state);out[0]=sequence;
    scd_special_contact_trace[0]=0x53435452;scd_special_contact_trace[1]=sequence;
}
volatile uint32_t scd_special_sonic_mailbox[32];
static void special_sonic_reset(void){
    const uint8_t *p=special_stage.part[4];
    special_sonic_player=(scd_special_player){.x=special_word(p)<<16,.y=special_word(p+2)<<16,.yaw=special_word(p+4)<<16,.sprite_y=344u<<16,.z=352,.top_speed=0xa00,.routine=1};
    special_sonic_world=(scd_special_world){.timer=100,.timer_frames=20,.ufo_count=6};
    if(scd_special_stage_reset(&special_stage_state,&special_sonic_world,(const void *)0x002D0000,special_ufo_paths_size,special_stage.stage-1))scd_special_mailbox[1]=6;
    special_sonic_sprite=(scd_special_sprite){.tilt=5};
    scd_special_sprite_set(&special_sonic_sprite,&special_sonic_art,10,1);
    special_sonic_visible=!scd_special_sprite_advance(&special_sonic_sprite,&special_sonic_player,&special_sonic_art,&special_sonic_pose);
    special_sonic_steps=special_sonic_taps=0;special_sonic_tick=vblank_ticks;special_sonic_frozen=0;
}
/* L inspects each real surface in the loaded map; Up+L seeds Sonic airborne
   at UFO 1's first path node, Down+L starts at 19 seconds for the time UFO.
   Rings and fractions are explicit diagnostic seeds; no map tiles change. */
static void special_contact_next(smpc_peripheral_digital_t pad){
    if(pad.pressed.button.up || pad.pressed.button.down){
        special_sonic_reset();special_sonic_mode=1;
        scd_special_player *p=&special_sonic_player;scd_special_ufo_path path;
        if(pad.pressed.button.up){
            special_contact_case=9;
            if(!scd_special_ufo_path_get(&special_stage_state.paths,(special_stage.stage-1)*6,&path)){p->x=special_word(path.data+4)<<16;p->y=special_word(path.data+6)<<16;}
            p->routine=2;p->flags=0x80;p->sprite_y=288u<<16;p->z=0x240;
        }else{special_contact_case=10;special_sonic_world.timer=19;special_sonic_world.timer_frames=1;}
        special_sonic_world.rings=99;special_dirty=1;special_contact_record(0,0);return;
    }
    unsigned kind=special_contact_case%8+1;
    for(unsigned y=848;y<3264;y+=32)for(unsigned x=848;x<3264;x+=32){
        if(scd_special_stamp_type(&special_stage,x,y,0)!=(int)kind)continue;
        special_sonic_reset();special_sonic_mode=1;special_contact_case=kind;
        special_sonic_player.x=(x<<16)|0x1234;special_sonic_player.y=(y<<16)|0x5678;
        special_sonic_player.x_velocity=0x89ab;special_sonic_player.y_velocity=0xcdef;
        special_sonic_world.rings=99;special_dirty=1;special_contact_record(0,0);return;
    }
}
static void special_sonic_fixture(unsigned entry){
    unsigned animation=0;
    for(;animation<special_sonic_art.animations;animation++){
        unsigned count=special_sonic_art.data[special_sonic_art.animation_offset+animation*4];
        if(entry<count)break;entry-=count;
    }
    special_sonic_mode=2;special_sonic_frozen=1;special_sonic_player.flags=2;special_sonic_player.sprite_y=344u<<16;
    scd_special_sprite_set(&special_sonic_sprite,&special_sonic_art,animation,1);special_sonic_sprite.frame=entry;
    special_sonic_visible=!scd_special_sprite_advance(&special_sonic_sprite,&special_sonic_player,&special_sonic_art,&special_sonic_pose);
}
static void special_sonic_update(smpc_peripheral_digital_t pad){
    if(pad.held.button.l){special_contact_next(pad);return;}
    if(pad.held.button.z){special_sonic_frozen=!special_sonic_frozen;special_sonic_tick=vblank_ticks;special_dirty=1;}
    unsigned held=(pad.pressed.button.up?1:0)|(pad.pressed.button.down?2:0)|(pad.pressed.button.left?4:0)|(pad.pressed.button.right?8:0)|(pad.pressed.button.a?16:0)|(pad.pressed.button.b?32:0)|(pad.pressed.button.c?64:0);
    special_sonic_taps|=(pad.held.button.a?16:0)|(pad.held.button.b?32:0)|(pad.held.button.c?64:0);
    if(special_sonic_frozen || vblank_ticks-special_sonic_tick<3)return;
    unsigned interval=vblank_ticks-special_sonic_tick;special_sonic_tick=vblank_ticks;
    scd_special_player *p=&special_sonic_player;
    /* Source starts the floor operation before RunObjects updates Sonic. */
    special_camera=(scd_special_camera){p->x>>16,p->y>>16,p->z,128,p->yaw>>16};
    scd_special_animate(&special_stage,&special_animation,(uint8_t *)special_stage.part[1],special_cache,(uint16_t *)maps);
    if(scd_special_stage_update(&special_stage_state,&special_sonic_world,p,&special_sonic_sprite,&special_sonic_art,&special_ufo_art,&special_effect_art,&special_stage,held,special_sonic_taps,p->yaw>>16,&special_sonic_pose,&special_sonic_visible))scd_special_mailbox[1]=6;
    special_sonic_steps++;special_dirty=1;
    special_contact_record(held,special_sonic_taps);
    /* The inspection currently has no special-stage audio consumer. */
    memset(special_sonic_world.sound,0,sizeof(special_sonic_world.sound));
    scd_special_sonic_mailbox[28]=held;scd_special_sonic_mailbox[29]=special_sonic_taps;scd_special_sonic_mailbox[31]=interval;
    special_sonic_taps=0;
}
static unsigned special_sonic_draw_actor(vdp1_cmdt_t *cmd){
    scd_special_sonic_mailbox[1]=special_sonic_mode;
    if(!special_sonic_mode || !special_sonic_visible)return 0;
    const scd_special_pose *pose=&special_sonic_pose;
    memcpy((void *)VDP1_VRAM(0xb400),pose->pixels,pose->width*pose->height/2);
    memset(cmd,0,sizeof(*cmd));vdp1_cmdt_normal_sprite_set(cmd);
    const vdp1_cmdt_draw_mode_t mode={.color_mode=VDP1_CMDT_CM_CLUT_16,.end_code_disable=true,.user_clipping_mode=2};
    vdp1_cmdt_draw_mode_set(cmd,mode);vdp1_cmdt_char_size_set(cmd,pose->width,pose->height);
    vdp1_cmdt_char_base_set(cmd,VDP1_VRAM(0xb400));cmd->cmd_colr=0xb020/8;
    vdp1_cmdt_char_flip_set(cmd,(vdp1_cmdt_char_flip_t)(pose->flip<<4));
    cmd->cmd_xa=160+pose->x;cmd->cmd_ya=(special_sonic_player.sprite_y>>16)-128+pose->y;
    scd_special_player *p=&special_sonic_player;scd_special_sprite *s=&special_sonic_sprite;
    const uint32_t words[]={p->x,p->y,p->yaw,p->sprite_y,p->sprite_velocity,p->z,p->speed,p->top_speed,p->jump_timer,p->flags,p->routine,s->tilt,s->animation,s->frame,s->time,s->time_copy,s->art,pose->index,pose->flip,(uint32_t)(int32_t)cmd->cmd_xa,(uint32_t)(int32_t)cmd->cmd_ya,pose->width,pose->height};
    for(unsigned i=0;i<23;i++)scd_special_sonic_mailbox[3+i]=words[i];
    scd_special_sonic_mailbox[26]=special_hash((const uint8_t *)VDP1_VRAM(0xb400),pose->width*pose->height/2);
    scd_special_sonic_mailbox[30]=special_sonic_frozen;scd_special_sonic_mailbox[2]=special_sonic_steps;scd_special_sonic_mailbox[0]=0x534e4943;
    return 1;
}
/* SFX textures live at VDP1 0xbc00, UFX at 0x76800; both use the common
   64-color palette at 0xb040 selected by the original tile palette line. */
static unsigned special_effect_draw(vdp1_cmdt_t *cmd,const scd_special_draw *d){
    const scd_special_art *art=d->kind==SCD_SPECIAL_DRAW_SFX?&special_effect_art:&special_ufo_art;
    if(!d->visible || !art->data)return 0;
    scd_special_sprite sprite={.animation=d->animation,.frame=d->frame};
    scd_special_player frozen={.flags=2};scd_special_pose pose;
    if(scd_special_sprite_advance(&sprite,&frozen,art,&pose))return 0;
    memset(cmd,0,sizeof(*cmd));vdp1_cmdt_normal_sprite_set(cmd);
    const vdp1_cmdt_draw_mode_t mode={.color_mode=VDP1_CMDT_CM_CLUT_16,.end_code_disable=true,.user_clipping_mode=2};
    vdp1_cmdt_draw_mode_set(cmd,mode);vdp1_cmdt_char_size_set(cmd,pose.width,pose.height);
    unsigned offset=pose.pixels-art->data-art->texture_offset;
    vdp1_cmdt_char_base_set(cmd,VDP1_VRAM((d->kind==SCD_SPECIAL_DRAW_SFX?0xbc00:0x76800)+offset));cmd->cmd_colr=(0xb040+d->palette*32)/8;
    vdp1_cmdt_char_flip_set(cmd,(vdp1_cmdt_char_flip_t)(pose.flip<<4));
    cmd->cmd_xa=d->x-96+pose.x;cmd->cmd_ya=d->y-128+pose.y;return 1;
}
static unsigned special_sonic_draw(vdp1_cmdt_t *cmd){
    if(!special_sonic_mode){scd_special_sonic_mailbox[1]=0;return 0;}
    if(special_sonic_mode==2 || !special_stage_state.draw_count)return special_sonic_draw_actor(cmd);
    unsigned count=0;
    /* MD's earlier SAT entries win overlap; VDP1 draws later commands on top. */
    for(int i=special_stage_state.draw_count-1;i>=0;i--){
        const scd_special_draw *d=special_stage_state.draws+i;
        count+=d->kind==SCD_SPECIAL_DRAW_SONIC?special_sonic_draw_actor(cmd+count):special_effect_draw(cmd+count,d);
    }
    return count;
}
