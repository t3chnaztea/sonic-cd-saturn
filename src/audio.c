#include <yaul.h>
#include "ponesound.h"
#include "audio.h"
#include "music_routes.h"
#include "sound_bus.h"
#include "cd_status.h"
#include "cd_root.h"
#include "feedback.inc"
#include "cdda_provider/cdda_envelope_shadow.h"
#include "cdda_provider/timer_c_shadow.h"
#include "cdda_target_qa_shadow.h"
/* The ELF gate bounds all driver code/data/BSS below shared block $C008.
   The port's active PCM descriptors additionally stay below $BC00.
   Samples start at $E000 and stay below the independent diagnostic tone at
   $7F000 (the driver's stack is above that tone). */
_Static_assert(0x408+DRV_SYS_END+sizeof(sysComPara)<=SFX_RAM_BASE,"sound workspace overlaps samples");
_Static_assert(SFX_RAM_BASE+SFX_BYTES<SFX_RAM_END,"sound samples overlap diagnostic tone");
extern uint8_t sound_driver[],sound_driver_end[];
extern sysComPara *m68k_com;
extern int ponesound_driver_copy_ok;
static int driver_ready,driver_copy_ok,copy_ok,cd_init_result;
static unsigned heartbeat,test_ticks,init_response;
static int initialized,bank_ok,toc_ok,music_era=-1,is_paused,playing;
static uint32_t starts[SCD_MUSIC_COUNT],ends[SCD_MUSIC_COUNT],resume_fad;
static unsigned music_zone,music_slot;
/* One swappable effect bank follows the resident effects in sound RAM
   (tools/prepare_audio.py): 0 Palmtree Panic, 1 Collision Chaos, 2 special stage. */
static int sfx_bank=-1,sfx_bank_ok;
/* Zone, special stage and boss music repeat; results, power-ups and the title play once. */
static int music_loop;  /* scd_audio_music_loop: the current song repeats whatever its cue */
static int music_repeats(int era){return music_loop || scd_music_repeats((unsigned)era);}
static cd_block_status_t status;
static unsigned poll_ticks;
static int warp_active;
/* Sound test SCMD_STOPCDDA: stop the CD track; the next cue (the title's) starts again. */
void scd_audio_stop_music(void){if(toc_ok)cd_block_cmd_disk_seek(0xffffff);playing=0;music_era=-1;}
void scd_audio_warp(int active){
    warp_active=active;
    if(active){if(toc_ok)cd_block_cmd_disk_seek(0xffffff);playing=0;scd_audio_request(216);}
    else {music_era=-1;}
}
volatile uint32_t scd_audio_mailbox[12];
/* CDA1 gate: magic,phase,faults,installed,timer,clock,last_rate,resets.
 * Source admission requires sealed nominal, real-negative and independent clock
 * evidence. The public mailbox only reports that admission; it cannot grant it. */
volatile uint32_t scd_audio_cdda_gate[8];
static int cdda_clock_admitted;
enum {
    CDDA_FAULT_DRIVER=1,CDDA_FAULT_INSTALL=2,CDDA_FAULT_TIMER=4,
    CDDA_FAULT_CLOCK_UNADMITTED=8,CDDA_FAULT_RESET=16,
    CDDA_FAULT_APPLY=32,CDDA_FAULT_REQUEST=64
};
static void cdda_gate_fault(unsigned fault){
    scd_audio_cdda_gate[2]|=fault;scd_audio_cdda_gate[1]=4;
}
void scd_audio_cdda_fade(unsigned rate){
    scd_audio_cdda_gate[6]=rate;
    if(!cdda_clock_admitted){cdda_gate_fault(CDDA_FAULT_CLOCK_UNADMITTED);return;}
    if(scd_audio_cdda_gate[2] || !scd_cdda_request_shadow(rate))
        cdda_gate_fault(CDDA_FAULT_REQUEST);
}


void scd_vdp1_overrun_sample(void); /* src/main.c: scd_world_mailbox[143] */
/* VBlank-in: the VDP1 overrun sample, then the sound driver's request when it runs. */
static void audio_vblank_in(void *work){
    scd_vdp1_overrun_sample();
    if(driver_ready)ponesound_vblank_rq(work);
}
void scd_audio_init(void) {
    /* Effects use low WRAM only during loading; the live bank lives in sound RAM. */
    uint8_t *bank=(uint8_t *)0x00200000;
    cd_init_result=cd_block_init();
    init_response=scd_cd_last_response;
    if(cd_init_result==0) {
        const cdfs_filelist_t *root=scd_cd_root_read();
        const cdfs_filelist_entry_t *entries=root->entries;
        for(unsigned i=0;i<root->entries_count;i++) {
            if(strcmp(entries[i].name,"SFX.PCM") || entries[i].size<SFX_BYTES || entries[i].size>SFX_RAM_END-SFX_RAM_BASE)continue;
            if(cd_block_sectors_read(entries[i].starting_fad,bank,entries[i].size)==0) {
                uint32_t hash=2166136261u;
                for(unsigned j=0;j<SFX_BYTES;j++)hash=(hash^bank[j])*16777619u;
                bank_ok=hash==SFX_HASH;
            }
        }
        uint16_t words=0;
        if(cd_block_cmd_toc_get(NULL,&words)==0) {
            uint32_t toc[102]={0};
            for(unsigned i=0;i<words;i++) {
                uint16_t word=MEMORY_READ(16,CD_BLOCK(0));
                if(i<204)toc[i/2]=(toc[i/2]<<16)|word;
            }
            cd_block_cmd_data_transfer_end();
            toc_ok=words==204 && ((toc[100]>>16)&255)==SCD_MUSIC_COUNT+1;
            for(unsigned i=0;i<SCD_MUSIC_COUNT;i++) {
                starts[i]=toc[i+1]&0xffffff;ends[i]=toc[i==SCD_MUSIC_COUNT-1?101:i+2]&0xffffff;
                if((toc[i+1]&0x40000000) || starts[i]<150 || ends[i]<=starts[i])toc_ok=0;
            }
        }
    }
    ponesound_load_driver(sound_driver,sound_driver_end-sound_driver,ADX_MASTER_768);
    driver_copy_ok=ponesound_driver_copy_ok;
    /* 0x7777 is published after initialization, including the coefficient tables. */
    for(unsigned n=0;n<600 && m68k_com->start!=0x7777;n++){vdp2_sync();vdp2_sync_wait();}
    uintptr_t commands=(uintptr_t)m68k_com->pcmCtrl;
    driver_ready=m68k_com->start==0x7777 && commands>=SCSP_RAM(0) && commands+(EFFECT_COUNT+SFX_BANK_EFFECTS)*sizeof(_PCM_CTRL)<SCSP_RAM(0xbc00);
    if(bank_ok && driver_ready)for(unsigned i=0;i<EFFECT_COUNT;i++)
        ponesound_load_8bit_pcm(bank+effect_ranges[i][0],effect_ranges[i][1],i,SFX_RAM_BASE+effect_ranges[i][0],11025);
    if(bank_ok && driver_ready) {
        copy_ok=scd_sound_hash((volatile uint16_t *)SCSP_RAM(SFX_RAM_BASE),SFX_BYTES)==SFX_HASH;
    }
    /* Charge has a rising attack followed by a held FM note. Loop the sustain. */
    if(copy_ok){m68k_com->pcmCtrl[3].LSA=11025;m68k_com->pcmCtrl[3].loopType=PCM_FWD_LOOP;}
    m68k_com->cdda_left_channel_vol_pan=0xff;
    m68k_com->cdda_right_channel_vol_pan=0xef;
    /* CD-DA reaches the SCSP through EXTS0/1, whose levels are slot 16/17 EFSDL/EFPAN
       (ST-077 table 4.31). The driver copies the values above once its main loop
       runs; set them here too so music does not depend on the 68000 starting. */
    MEMORY_WRITE(16,SCSP(0x216),0x00ff);
    MEMORY_WRITE(16,SCSP(0x236),0x00ef);
    ponesound_set_master_volume(15);
    /* External build seals require patched.bin SHA256 ae1f243ab3b9be9ea66dc86904111c42feb8b9817229678f5433c41b80735c6a.
     * Runtime copy/readback and the existing ABI/workspace guards stay in force.
     * FF/EF setup above must precede this sole DSP install. No VBlank/cue yet. */
    scd_audio_cdda_gate[0]=0x43444131;
    if(!driver_ready || !driver_copy_ok || sound_driver_end-sound_driver!=8740)
        cdda_gate_fault(CDDA_FAULT_DRIVER);
    else if(!scd_cdda_envelope_install_shadow())cdda_gate_fault(CDDA_FAULT_INSTALL);
    else {
        scd_audio_cdda_gate[3]=1;scd_audio_cdda_gate[1]=1;
        /* Independently sourced BIOS empty callback; never adopt observed state. */
        if(!scd_cdda_timer_start_shadow((scu_ic_ihr_t)0x0600083c))
            cdda_gate_fault(CDDA_FAULT_TIMER);
        else {
            scd_audio_cdda_gate[4]=1;scd_audio_cdda_gate[1]=2;
            if(!scd_cdda_timer_apply_shadow())cdda_gate_fault(CDDA_FAULT_APPLY);
            else {cdda_clock_admitted=1;scd_audio_cdda_gate[5]=1;scd_audio_cdda_gate[1]=3;}
        }
        scd_cdda_target_snapshot_shadow();
    }
    vdp_sync_vblank_in_set(audio_vblank_in,NULL);initialized=1;
}
static void music_play(uint32_t start,int repeat) {
    if(toc_ok && music_era>=0 && start<ends[music_slot])
        playing=cd_block_cmd_disk_play(repeat?15:0,start,ends[music_slot]-start)==0;
}
static void music_select(unsigned era,int stop_effects) {
    if(!initialized || era>16)return;
    if(stop_effects && copy_ok)for(unsigned i=0;i<EFFECT_COUNT+SFX_BANK_EFFECTS;i++)m68k_com->pcmCtrl[i].sh2_permit=0;
    unsigned slot=scd_music_slot(music_zone,era);
    if(music_era==(int)era && music_slot==slot)return;
    /* A new cue resets784 without resetting the diagnostic TimerC phase.
     * Ordinary looping calls music_play directly and does not enter here. */
    if(!scd_audio_cdda_gate[3] || !scd_audio_cdda_gate[4] || !scd_cdda_reset_shadow()){
        cdda_gate_fault(CDDA_FAULT_RESET);return;
    }
    scd_audio_cdda_gate[7]++;
    music_era=era;music_slot=slot;resume_fad=starts[slot];playing=0;poll_ticks=0;
    if(!is_paused)music_play(starts[slot],music_repeats(era));
}
void scd_audio_era(unsigned era){music_loop=0;music_select(era,1);}
/* LOADER2.C sub_sync music requests from actors (the boss track and the return
   to the zone track) change the CD track only: the original's FM and PCM
   effects keep playing (BOSS_3.C requests 19/20 right after the hit sound). */
void scd_audio_music(unsigned cue){music_loop=0;music_select(cue,0);}
/* D.A. Garden (Sub.asm PlayCDDAMusic, MSCPLAYR): the zone's song for an era cue or any other
   cue, restarted from its start and repeated, without reading the zone's effect bank. */
void scd_audio_music_loop(unsigned zone,unsigned cue){
    if(zone>=7)return;
    music_zone=zone;music_loop=1;music_era=-1;music_select(cue,0);
}
/* Read one bank from the CD straight into sound RAM after the resident effects:
   one transfer (the CD block copies 16-bit words; the file length is even), then
   point the bank's command slots at it. Load with the zone's stage data, before
   music starts: the CD block cannot play and read at once. */
void scd_audio_bank(int bank){
    if(!copy_ok || bank==sfx_bank || bank>=(int)SFX_BANK_COUNT)return;
    for(unsigned i=0;i<SFX_BANK_EFFECTS;i++)m68k_com->pcmCtrl[EFFECT_COUNT+i].sh2_permit=0;
    sfx_bank=-1;sfx_bank_ok=0;
    if(bank<0)return;
    const cdfs_filelist_t *root=scd_cd_root_read();
    for(unsigned i=0;i<root->entries_count;i++){
        const cdfs_filelist_entry_t *e=&root->entries[i];
        uint32_t bytes=sfx_bank_sizes[bank][0];
        if(strcmp(e->name,sfx_bank_files[bank]) || e->size!=bytes || (bytes&1) || SFX_BANK_BASE+bytes>SFX_RAM_END)continue;
        if(cd_block_sectors_read(e->starting_fad,(void *)SCSP_RAM(SFX_BANK_BASE),bytes) ||
           scd_sound_hash((volatile uint16_t *)SCSP_RAM(SFX_BANK_BASE),bytes)!=sfx_bank_sizes[bank][1])break;
        /* All effects are 8-bit 11025 Hz: the resident slot 0 holds the same pitch and pace. */
        for(unsigned k=0;k<sfx_bank_counts[bank];k++){
            volatile _PCM_CTRL *c=&m68k_com->pcmCtrl[EFFECT_COUNT+k];
            uint32_t address=SFX_BANK_BASE+sfx_bank_effects[bank][k].offset;
            c->hiAddrBits=(unsigned short)(address>>16);c->loAddrBits=(unsigned short)(address&0xffff);
            c->pitchword=m68k_com->pcmCtrl[0].pitchword;c->bytes_per_blank=m68k_com->pcmCtrl[0].bytes_per_blank;
            c->playsize=sfx_bank_effects[bank][k].bytes;c->bitDepth=PCM_TYPE_8BIT;c->loopType=0;c->volume=7;c->LSA=0;
        }
        sfx_bank_ok=1;sfx_bank=bank;
        break;
    }
    playing=0;
    extern volatile uint32_t scd_sfx_bank_mailbox[4];
    scd_sfx_bank_mailbox[1]++;scd_sfx_bank_mailbox[3]=(uint32_t)(sfx_bank+1);scd_sfx_bank_mailbox[0]=0x53465842;
}
int scd_audio_bank_current(void){return sfx_bank;}
void scd_audio_stage(unsigned zone,unsigned era){
    if(zone>=7 || era>=4)return;
    scd_audio_bank(zone==0?0:zone==1?1:zone==2?3:zone==3?4:-1); /* SFXZ2 is bank 3, SFXZ3 bank 4 */
    music_zone=zone;scd_audio_era(era);
}
void scd_audio_results(void){scd_audio_era(4);}
void scd_audio_pause(int paused) {
    if(!initialized || paused==is_paused)return;
    is_paused=paused;ponesound_set_master_volume(paused?0:15);
    if(!toc_ok || music_era<0)return;
    if(paused) {
        if(cd_block_cmd_status_get(&status)==0 && status.fad>=starts[music_slot] && status.fad<ends[music_slot])resume_fad=status.fad;
        else resume_fad=starts[music_slot];
        cd_block_cmd_disk_seek(0xffffff);playing=0;
    } else music_play(resume_fad,0);
    poll_ticks=0;
}
void scd_audio_update(void) {
    if(scd_audio_cdda_gate[3])scd_cdda_target_snapshot_shadow();
    if(driver_ready && m68k_com->start==0)heartbeat++;
    if(test_ticks && --test_ticks==0)scd_audio_test(-1);
    if(!initialized || !toc_ok || music_era<0 || ++poll_ticks<30)return;
    poll_ticks=0;
    if(cd_block_cmd_status_get(&status)!=0)return;
    /* After a resumed partial track ends, restore looping over the entire song. */
    if(!is_paused && !warp_active && music_repeats(music_era) &&((!playing) || (status.cd_status&15)==CD_STATUS_PAUSE))music_play(starts[music_slot],1);
}
uint32_t scd_audio_status(void) {
    scd_audio_mailbox[8]=driver_ready;scd_audio_mailbox[9]=copy_ok;
    scd_audio_mailbox[10]=heartbeat;scd_audio_mailbox[11]=m68k_com->start;
    scd_audio_mailbox[0]=bank_ok;scd_audio_mailbox[1]=toc_ok;
    scd_audio_mailbox[2]=is_paused;scd_audio_mailbox[3]=music_era<0?0:music_slot+2;
    scd_audio_mailbox[4]=status.cd_status&15;scd_audio_mailbox[5]=status.track_number;
    scd_audio_mailbox[6]=status.fad;scd_audio_mailbox[7]=status.flag_and_repeat_count&15;
    return status.track_number|((status.cd_status&15)<<8)|((music_era+2)<<16)|
        (is_paused<<20)|(bank_ok<<21)|(toc_ok<<22)|((status.flag_and_repeat_count&15)<<24);
}
/* Emulator negative control only (tools/test_cc3_boss_emulator.py): a request
   number written here is dropped. Nothing in the game writes it. */
volatile uint32_t scd_audio_test_mute;
void scd_audio_request(short request) {
    if(!initialized || !copy_ok || is_paused)return;
    if(scd_audio_test_mute && request==(short)scd_audio_test_mute)return;
    int sample=-1;
    if(request==171){m68k_com->pcmCtrl[3].sh2_permit=0;return;}
    /* Generated beside the PCM ranges: adding an effect cannot shift another
       request onto the wrong sample (big-ring and special cues used to do so). */
    /* The zone bank first: a request can name a different sample per round (183). */
    if(sfx_bank>=0)for(unsigned i=0;i<sfx_bank_counts[sfx_bank];i++)
        if(sfx_bank_effects[sfx_bank][i].request==request){sample=(int)(EFFECT_COUNT+i);break;}
    if(sample<0)for(unsigned i=0;i<EFFECT_COUNT;i++)if(effect_requests[i]==request){sample=(int)i;break;}
    if(sample<0)return;
    if(request==145 || request==147 || request==148 || request==152)m68k_com->pcmCtrl[3].sh2_permit=0;
    /* D7 uses FM6; equal-priority 9F replaces it with FM5/FM6. Verified
       against the retail Z80 headers by tools/cc_pocket_source.py. */
    if(request==159 && sfx_bank>=0)for(unsigned i=0;i<sfx_bank_counts[sfx_bank];i++)
        if(sfx_bank_effects[sfx_bank][i].request==215)m68k_com->pcmCtrl[EFFECT_COUNT+i].sh2_permit=0;
    ponesound_pcm_play(sample,sample==3?PCM_FWD_LOOP:PCM_SEMI,6);
}

scd_audio_diagnostics scd_audio_get_diagnostics(void) {
    return (scd_audio_diagnostics){driver_ready,bank_ok,copy_ok,heartbeat,toc_ok,status.track_number,status.cd_status&15,cd_init_result,
        driver_copy_ok,UINT32_MAX,MEMORY_READ(16,SCSP(0x216)),MEMORY_READ(16,SCSP(0x236)),m68k_com->start,init_response};
}
void scd_audio_test(int kind) {
    volatile uint16_t *slot=(volatile uint16_t *)SCSP(31*32);
    slot[0]=0x1000;test_ticks=0;
    if(toc_ok)cd_block_cmd_disk_seek(0xffffff);
    if(kind<0){ponesound_set_master_volume(is_paused?0:15);return;}
    ponesound_set_master_volume(15);
    if(kind==2){music_play(starts[music_slot],1);return;}
    test_ticks=90;
    if(kind==1){if(copy_ok)ponesound_pcm_play(1,PCM_SEMI,6);return;}
    /* Independent sound-chip probe: no disc data and no 68000 driver commands. */
    volatile uint16_t *wave=(volatile uint16_t *)SCSP_RAM(0x7f000);
    for(unsigned i=0;i<128;i+=2) {
        int a=i<64?-48+(int)i*3/2:48-((int)i-64)*3/2;
        int b=i+1<64?-48+(int)(i+1)*3/2:48-((int)i+1-64)*3/2;
        wave[i/2]=((a&255)<<8)|(b&255);
    }
    for(unsigned i=0;i<16;i++)slot[i]=0;
    slot[3]=128;slot[4]=31;slot[5]=31;slot[11]=0xa000;
    slot[1]=0xf000;
    slot[0]=0x1837; /* Execute key-on, PCM8, forward loop, sound RAM $7F000. */
}
