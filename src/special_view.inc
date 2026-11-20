#include "special_player.h"
#include "special_sprite.h"
#include "special_contacts.h"
#include "special_effects_runtime.h"
#include "special_stage.h"
/* Inspection of actual source floors. Low WRAM is free after audio_init has
   copied the PCM bank to SCSP. This is not the special-stage game state. */
static scd_special_stage special_stage;
static scd_special_camera special_camera;
static scd_special_line special_lines[96];
static int special_mode,special_dirty;
static scd_special_camera special_previous;
static scd_special_animation special_animation;
static scd_special_player special_air_player;
static unsigned special_air_arc;
static unsigned special_animation_vblank;
static int special_animating;
static uint8_t special_pixels[24576] __aligned(16);
static void *const special_cache=(void *)0x00240000;
volatile uint32_t scd_special_mailbox[32];
static volatile uint32_t special_job[2] __uncached;
static int special_slave_ready,special_benchmark_active;
volatile uint32_t scd_special_benchmark[8+8*20];
static void special_slave_render(void){
    unsigned generation=special_job[0];
    cpu_cache_purge();cpu_cache_repl_enable(CPU_CACHE_TYPE_I|CPU_CACHE_TYPE_D);
    for(unsigned row=1;row<96;row+=2)scd_special_render_rows(special_cache,(const uint16_t *)maps,special_lines+row,special_pixels+row*256,256,1);
    special_job[1]=generation;
}
static void special_slave_stop(void){
    special_benchmark_active=0;
    if(!special_slave_ready)return;
    input_ready=0;cpu_dual_slave_clear();smpc_smc_sshoff_call();input_ready=1;
    special_slave_ready=0;scd_special_mailbox[23]=0;
}
static void special_slave_start(void){
    if(special_slave_ready)return;
    special_job[0]=special_job[1]=0;
    input_ready=0;cpu_dual_comm_mode_set(CPU_DUAL_ENTRY_POLLING);cpu_dual_slave_set(special_slave_render);input_ready=1;
    special_slave_ready=1;scd_special_mailbox[23]=1;
}
static unsigned special_word(const uint8_t *p){return (p[0]<<8)|p[1];}
static uint32_t special_hash(const uint8_t *p,unsigned n){
    uint32_t h=2166136261u;while(n--)h=(h^*p++)*16777619u;return h;
}
#include "special_sonic_view.inc"
#include "special_game_view.inc"
static void special_load(unsigned id){
    /* The special-stage renderer installs its own slave entry. */
    bg_slave_stop();
    /* The special stage effects bank (tools/prepare_audio.py); the zone bank returns with load_era. */
    scd_audio_bank(2);
    /* Preserve the separate special-stage presentation pipeline. */
    gameplay_clear_wait();vdp1_sync_wait();vdp1_sync_interval_set(0);
    uint8_t *data=(uint8_t *)0x00200000;
    char name[12];
    scd_special_mailbox[0]=0x53504c44;scd_special_mailbox[1]=1;
    memset(&special_stage,0,sizeof(special_stage));memset(&special_sonic_art,0,sizeof(special_sonic_art));memset(&special_effect_art,0,sizeof(special_effect_art));
    memset(&special_ufo_art,0,sizeof(special_ufo_art));special_ufo_paths_size=0;memset(&special_main_pack,0,sizeof(special_main_pack));
    special_sonic_mode=0;special_contact_case=0;scd_special_sonic_mailbox[1]=0;
    snprintf(name,sizeof(name),"SP%u.BIN",id);
    /* One Main CPU program pack per stage (LoadSSnData); stage 8 has none. */
    char main_name[12];snprintf(main_name,sizeof(main_name),"SSM%u.BIN",id);
    scd_audio_pause(1);
    const cdfs_filelist_t *root=scd_cd_root_read();
    const cdfs_filelist_entry_t *entries=root->entries;
    for(unsigned i=0;i<root->entries_count;i++){
        if(!strcmp(entries[i].name,"SSONIC.BIN") && entries[i].size>=40 && entries[i].size<=0x10000){
            void *art=(void *)0x00220000;
            if(!cd_block_sectors_read(entries[i].starting_fad,art,entries[i].size) && !scd_special_art_open(&special_sonic_art,art,entries[i].size) && special_sonic_art.animations==45){
                scd_special_sonic_mailbox[27]=special_hash(art,entries[i].size);
                memcpy((void *)VDP1_VRAM(0xb020),special_sonic_art.data+special_sonic_art.palette_offset,32);
            }
        }
        if(!strcmp(entries[i].name,"SFX.BIN") && entries[i].size>=40 && entries[i].size<=0x10000){
            void *art=(void *)0x00230000;
            if(!cd_block_sectors_read(entries[i].starting_fad,art,entries[i].size) && !scd_special_art_open(&special_effect_art,art,entries[i].size) && special_effect_art.animations==8){
                unsigned bytes=special_effect_art.length-special_effect_art.texture_offset;
                memcpy((void *)VDP1_VRAM(0xbc00),special_effect_art.data+special_effect_art.texture_offset,bytes);
                memcpy((void *)VDP1_VRAM(0xb040),special_effect_art.data+special_effect_art.palette_offset,128);
                scd_special_contact_trace[2]=special_hash(art,entries[i].size);
                scd_special_contact_trace[3]=special_hash((const uint8_t *)VDP1_VRAM(0xbc00),bytes);
                scd_special_contact_trace[4]=special_hash((const uint8_t *)VDP1_VRAM(0xb040),128);
            }
        }
        if(!strcmp(entries[i].name,"UFX.BIN") && entries[i].size>=40 && entries[i].size<=0x10000){
            void *art=(void *)0x002C0000;
            if(!cd_block_sectors_read(entries[i].starting_fad,art,entries[i].size) && !scd_special_art_open(&special_ufo_art,art,entries[i].size) && special_ufo_art.animations==36){
                unsigned bytes=special_ufo_art.length-special_ufo_art.texture_offset;
                /* UFO/shadow/explosion/time-stone art follows ordinary object art. */
                assert(OBJECT_ATLAS_BASE+OBJECT_ART_BYTES<=0x76800 && 0x76800+bytes<=0x80000);
                memcpy((void *)VDP1_VRAM(0x76800),special_ufo_art.data+special_ufo_art.texture_offset,bytes);
                scd_special_contact_trace[5]=special_hash(art,entries[i].size);
                scd_special_contact_trace[6]=special_hash((const uint8_t *)VDP1_VRAM(0x76800),bytes);
            }
        }
        if(!strcmp(entries[i].name,"UFP.BIN") && entries[i].size>=408 && entries[i].size<=0x1000){
            void *paths=(void *)0x002D0000;scd_special_ufo_paths check;
            if(!cd_block_sectors_read(entries[i].starting_fad,paths,entries[i].size) && !scd_special_ufo_paths_open(&check,paths,entries[i].size)){
                special_ufo_paths_size=entries[i].size;scd_special_contact_trace[7]=special_hash(paths,entries[i].size);
            }
        }
        if(!strcmp(entries[i].name,main_name) && entries[i].size>=100 && entries[i].size<=0x10000){
            void *pack=(void *)0x002E0000;
            if(!cd_block_sectors_read(entries[i].starting_fad,pack,entries[i].size) && !scd_special_main_open(&special_main_pack,pack,entries[i].size))scd_special_game_mailbox[33]=special_hash(pack,entries[i].size);
        }
        if(strcmp(entries[i].name,name) || entries[i].size<72 || entries[i].size>0x20000)continue;
        if(cd_block_sectors_read(entries[i].starting_fad,data,entries[i].size)==0 && !scd_special_open(&special_stage,data,entries[i].size)){
            scd_special_mailbox[1]=0;
            scd_special_mailbox[12]=special_hash(data,entries[i].size);
        }
    }
    if(!special_sonic_art.data || special_sonic_art.animations!=45){memset(&special_sonic_art,0,sizeof(special_sonic_art));scd_special_mailbox[1]=4;}
    if(!special_effect_art.data || special_effect_art.animations!=8){memset(&special_effect_art,0,sizeof(special_effect_art));scd_special_mailbox[1]=5;}
    if(!special_ufo_art.data || special_ufo_art.animations!=36 || !special_ufo_paths_size){memset(&special_ufo_art,0,sizeof(special_ufo_art));special_ufo_paths_size=0;scd_special_mailbox[1]=6;}
    if(special_stage.stage){
        if(!scd_special_cache(&special_stage,special_cache,0x80000)){scd_special_mailbox[1]=2;special_stage.stage=0;}
    }
    if(special_stage.stage){
        memcpy(maps,special_cache,32768);
        const uint8_t *p=special_stage.part[4];
        special_camera=(scd_special_camera){special_word(p),special_word(p+2),352,128,special_word(p+4)};
        memcpy((void *)VDP1_VRAM(0xb000),special_stage.part[3],32);
        if(special_sonic_art.data)special_sonic_reset();
    }
    special_animation=(scd_special_animation){0,0,0};special_animating=0;special_animation_vblank=vblank_ticks;
    for(unsigned i=24;i<32;i++)scd_special_mailbox[i]=0;scd_special_mailbox[29]=0xffffffffu;
    special_slave_start();
    special_mode=1;special_dirty=1;scd_special_mailbox[2]=id;
    vdp2_scrn_display_set(VDP2_SCRN_DISPTP_NBG3);
    vdp2_scrn_back_color_set(VDP2_VRAM_ADDR(3,0x1bffe),RGB1555(1,0,0,0));
}
static void special_draw(smpc_peripheral_digital_t pad){
    if(special_game_active){special_game_frame(pad);return;}
    if(pad.held.button.r && !special_benchmark_active){
        memset((void *)scd_special_benchmark,0,sizeof(scd_special_benchmark));
        special_load(1); /* Restore the source map after live animation. */
        special_air_arc=0;memset(&special_air_player,0,sizeof(special_air_player));
        unsigned motion_count;scd_special_benchmark[5]=scd_special_player_probe(&motion_count);scd_special_benchmark[6]=motion_count;
        scd_special_benchmark[0]=0x5353424d;special_benchmark_active=1;
    }
    int benchmark=special_benchmark_active;
    if(benchmark){
        unsigned n=scd_special_benchmark[1],id=n>=1088?1:n>=896?1+(n-896)/24:n<560?1:2+(n-560)/48;
        unsigned k=n<512?n:n<560?n-512:(n-560)%48;
        if(scd_special_mailbox[2]!=id || n==896 || n==1088 || n==1328)special_load(id);
        if(special_stage.stage){
            const uint8_t *p=special_stage.part[4];const int heights[]={352,432,624};
            special_camera=(scd_special_camera){special_word(p),special_word(p+2),n<512?352:heights[k/16],128,n<512?k:(k%16)*32};
            if(n>=896 && n<1088){
                unsigned offset=special_word(special_stage.part[5]);
                int x=(offset/2%128)*32+16-192,y=(offset/2/128)*32+16;
                if(x<832)x=832;if(x>3264)x=3264;if(y<832)y=832;if(y>3264)y=3264;
                special_camera=(scd_special_camera){x,y,352,128,128};
                scd_special_animate(&special_stage,&special_animation,(uint8_t *)special_stage.part[1],special_cache,(uint16_t *)maps);
            }
            if(n>=1088 && n<1328){
                if(n==1088 || special_air_player.routine==1){
                    if(n!=1088)special_air_arc++;
                    special_air_player=(scd_special_player){.x=1344u<<16,.y=1312u<<16,.yaw=128u<<16,.sprite_y=344u<<16,.z=352,.speed=0xa00,.top_speed=0xa00,.routine=1,.jump_timer=special_air_arc==4?20:0};
                    if(special_air_arc<2)scd_special_player_jump(&special_air_player,0x10,0);else if(special_air_arc<5)scd_special_player_spring(&special_air_player);else scd_special_player_fan(&special_air_player);
                }
                scd_special_player_air(&special_air_player,special_air_arc==1 || special_air_arc==3?0x10:0,0);
                special_camera=(scd_special_camera){1344,1312,special_air_player.z,128,128};
            }
            if(n>=1328){
                special_camera=(scd_special_camera){1344,1312,352,128,128};
                if(special_sonic_art.data)special_sonic_fixture(n-1328);else scd_special_mailbox[1]=4;
            }
            special_dirty=1;
        }
    }else{
    if(pad.held.button.b && !special_sonic_mode){if(special_game_begin(pad.pressed.button.l?4000:0,5000,3,0))special_load(1);else{special_game_frame(pad);return;}}
    if(pad.held.button.x)special_load(scd_special_mailbox[2]%8+1);
    if(pad.held.button.y && special_sonic_art.data){
        special_sonic_mode=!special_sonic_mode;if(special_sonic_mode){special_contact_case=0;special_sonic_reset();special_contact_record(0,0);}special_animating=0;special_dirty=1;
    }
    if(special_sonic_mode)special_sonic_update(pad);
    else {
    if(pad.held.button.c){special_animating=!special_animating;special_animation_vblank=vblank_ticks;special_dirty=1;}
    if(special_animating && special_stage.stage && vblank_ticks-special_animation_vblank>=SCD_SPECIAL_UPDATE_VBLANKS){
        unsigned elapsed=vblank_ticks-special_animation_vblank;
        if(elapsed<scd_special_mailbox[29])scd_special_mailbox[29]=elapsed;
        if(elapsed>scd_special_mailbox[30])scd_special_mailbox[30]=elapsed;
        scd_special_mailbox[28]++;special_animation_vblank=vblank_ticks;
        scd_special_animate(&special_stage,&special_animation,(uint8_t *)special_stage.part[1],special_cache,(uint16_t *)maps);
        special_dirty=1;
    }
    if(pad.pressed.button.left)special_camera.yaw=(special_camera.yaw-2)&511;
    if(pad.pressed.button.right)special_camera.yaw=(special_camera.yaw+2)&511;
    int step=pad.pressed.button.up?8:pad.pressed.button.down?-8:0;
    special_camera.x+=step*scd_special_sine(special_camera.yaw)/256;
    special_camera.y-=step*scd_special_sine(special_camera.yaw+128)/256;
    if(special_camera.x<832)special_camera.x=832;if(special_camera.x>3264)special_camera.x=3264;
    if(special_camera.y<832)special_camera.y=832;if(special_camera.y>3264)special_camera.y=3264;
    special_camera.z=pad.pressed.button.a?624:352;
    }
    }
    int changed=special_dirty || memcmp(&special_camera,&special_previous,sizeof(special_camera));
    if(changed){
    special_previous=special_camera;special_dirty=0;
    uint8_t *pixels=special_pixels;
    volatile cpu_ioregs_t *cpu=(volatile cpu_ioregs_t *)CPU_IOREG_BASE;
    unsigned previous_ccr=cpu->ccr;
    cpu_cache_purge();cpu_cache_repl_enable(CPU_CACHE_TYPE_I|CPU_CACHE_TYPE_D);
    unsigned previous_tcr=cpu->tcr;cpu->tcr=(previous_tcr&~3)|CPU_FRT_CLOCK_DIV_128;
    scd_special_mailbox[16]=previous_ccr;
    unsigned start=vblank_ticks;cpu_frt_count_set(0);
    if(special_stage.stage && !scd_special_trace(special_lines,special_camera)){
        scd_special_mailbox[17]=cpu_frt_count_get();
        unsigned generation=special_job[0]+1;special_job[0]=generation;cpu_dual_slave_notify();
        for(unsigned row=0;row<96;row+=2)scd_special_render_rows(special_cache,(const uint16_t *)maps,special_lines+row,pixels+row*256,256,1);
        scd_special_mailbox[20]=cpu_frt_count_get();
        /* A slave just powered on by special_slave_start may still be in its
           entry code; repeat the notification once per VBlank until it answers. */
        for(unsigned notified=vblank_ticks;special_job[1]!=generation && vblank_ticks-start<30;)
            if(vblank_ticks!=notified){notified=vblank_ticks;cpu_dual_slave_notify();}
        if(special_job[1]!=generation){special_slave_stop();scd_special_mailbox[1]=3;special_stage.stage=0;}
        cpu_cache_area_purge(pixels,24576);
        scd_special_mailbox[21]=generation;scd_special_mailbox[22]=special_job[1];
        scd_special_mailbox[18]=cpu_frt_count_get();
        volatile uint16_t *texture=(volatile uint16_t *)VDP1_VRAM(0x8000);
        for(unsigned i=0;i<6144;i++){
            uint32_t four=((const uint32_t *)pixels)[i];
            uint32_t pairs=(four&0x000f000fu)|((four&0x0f000f00u)>>4);
            texture[i]=(uint16_t)(pairs|(pairs>>8));
        }
        scd_special_mailbox[8]=cpu_frt_count_get();scd_special_mailbox[9]=vblank_ticks-start;
        if(benchmark || (!special_animating && (!special_sonic_mode || special_sonic_frozen))){
        scd_special_mailbox[10]=special_hash((const uint8_t *)special_lines,sizeof(special_lines));
        scd_special_mailbox[11]=special_hash(pixels,24576);
        scd_special_mailbox[13]=special_hash((const uint8_t *)VDP1_VRAM(0x8000),12288);
        }
        scd_special_mailbox[14]=scd_special_stamp_type(&special_stage,special_camera.x,special_camera.y,NULL);
        scd_special_mailbox[0]=0x53504543;
    }
    cpu->tcr=previous_tcr;cpu->ccr=previous_ccr;
    }
    scd_special_mailbox[3]=special_camera.x;scd_special_mailbox[4]=special_camera.y;
    scd_special_mailbox[5]=special_camera.z;scd_special_mailbox[6]=special_camera.yaw;
    scd_special_mailbox[24]=special_animation.delay;scd_special_mailbox[25]=special_animating;
    scd_special_mailbox[26]=special_animation_vblank;scd_special_mailbox[27]=vblank_ticks;
    scd_special_mailbox[7]++;scd_special_mailbox[15]=1;
    vdp1_cmdt_t *sonic_cmd=sprite_commands->cmdts+4;
    unsigned sonic_commands=special_sonic_draw(sonic_cmd);
    if(benchmark){
        unsigned sequence=scd_special_benchmark[1]+1;
        volatile uint32_t *record=scd_special_benchmark+8+(sequence%8)*20;
        record[1]=scd_special_mailbox[2];record[2]=special_camera.x;record[3]=special_camera.y;record[4]=special_camera.z;record[5]=special_camera.yaw;
        record[6]=scd_special_mailbox[10];record[7]=scd_special_mailbox[11];record[8]=scd_special_mailbox[13];record[9]=scd_special_mailbox[8];record[10]=scd_special_mailbox[18]-scd_special_mailbox[17];record[11]=scd_special_mailbox[1];
        record[12]=special_animation.fan;record[13]=special_animation.hazard;record[14]=special_animation.delay;
        record[15]=special_stage.stage?special_hash(special_stage.part[1],32768):0;
        record[16]=sonic_commands?special_sonic_pose.index:0xffffffffu;record[17]=sonic_commands?special_sonic_pose.flip:0;
        record[18]=sonic_commands?scd_special_sonic_mailbox[26]:0;record[19]=sonic_commands?special_hash((const uint8_t *)&sonic_cmd->cmd_xa,4):0;
        if(record[9]>scd_special_benchmark[4])scd_special_benchmark[4]=record[9];
        scd_special_benchmark[2]+=record[11]!=0;record[0]=sequence;scd_special_benchmark[1]=sequence;
        if(sequence==1632 || record[11]){special_benchmark_active=0;scd_special_benchmark[3]=1;}
    }
    vdp1_cmdt_t *cmd=sprite_commands->cmdts+2;memset(cmd,0,sizeof(*cmd));
    vdp1_cmdt_normal_sprite_set(cmd);
    const vdp1_cmdt_draw_mode_t mode={.color_mode=VDP1_CMDT_CM_CLUT_16,.end_code_disable=true};
    vdp1_cmdt_draw_mode_set(cmd,mode);vdp1_cmdt_char_size_set(cmd,256,96);
    vdp1_cmdt_char_base_set(cmd,VDP1_VRAM(0x8000));cmd->cmd_colr=0xb000/8;cmd->cmd_xa=32;cmd->cmd_ya=128;
    if(!special_stage.stage)vdp1_cmdt_jump_skip_next(cmd);
    /* The original H32 screen is 256 pixels wide; clip sprites to it. */
    vdp1_cmdt_t *clip=cmd+1;memset(clip,0,sizeof(*clip));vdp1_cmdt_user_clip_coord_set(clip);vdp1_cmdt_vtx_user_clip_coord_set(clip,INT16_VEC2(32,0),INT16_VEC2(287,223));
    vdp1_cmdt_end_set(cmd+2+sonic_commands);sprite_commands->count=5+sonic_commands;
    vdp1_sync_cmdt_list_put(sprite_commands,0);vdp1_sync_render();vdp1_sync();
    int show_status=benchmark || (!special_animating && (!special_sonic_mode || special_sonic_frozen)) || (special_sonic_mode && special_sonic_steps%20==0) || (special_animating && special_animation.delay%20==0);
    if(changed && show_status){
        dbgio_printf("\x1b[H\x1b[2J%s",special_stage.stage?"":"CD ASSET LOAD FAILED");
        dbgio_flush();
    }
}
