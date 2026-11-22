/* Front-end overlay (src/saturn.x .zone_R0, cd/ZTR0.BIN): title, menus, Time Attack,
   sound test and ending code. Every symbol here carries the fe_ prefix
   (tools/test_zone_code.py); resident code reaches fe_ code only through
   fe_frontend_zone_ops after scd_frontend_overlay_load() (src/main.c, src/zone_code.h).
   Zero-initialised state must sit in .data.fe_* (FE_DATA): .bss stays resident. */
#include <stdint.h>
#include <string.h>
#include "zone_code.h"
#include "frontend.h"
#include "time_attack.h"
#include "player_plus.h"
#include "save.h"
#include <yaul.h>
#include "cd_root.h"
#include "audio.h"
#include "fmv_fe_names.h"
#include "stage_packs.h"
#include "fmv_saturn.h"
#include "visual_mode.h"
#include "staff_times.h"
#include "stage_select.h"
#include "coming.h"

/* FE_DATA(name) for a variable of a named type. An anonymous struct takes the
   attribute after its name instead: after the closing brace it binds to the type. */
#define FE_DATA(name) __attribute__((section(".data." #name))) name

/* "FRNT": scd_frontend_overlay_load checks it after each read. */
const volatile uint32_t fe_overlay_magic=0x46524e54u;

/* ---- Time Attack records file ------------------------------------------------ */
static scd_ta_records FE_DATA(fe_ta_rec);
/* The record file pair of the preset in use (src/time_attack.h). */
static fe_ta_file_state FE_DATA(fe_ta_files);
static uint8_t FE_DATA(fe_ta_preset);
/* 0 not read, 1 read (or defaults), 2 a write failed. */
static uint8_t FE_DATA(fe_ta_state);
static void fe_ta_load(void){
    /* RAM DATA can change the preset without replacing this overlay. */
    if(fe_ta_state && fe_ta_preset==(scd_preset_flags?1:0))return;
    fe_ta_preset=scd_preset_flags?1:0;
    fe_ta_records_load(&fe_ta_saturn_io,fe_ta_preset,&fe_ta_rec,&fe_ta_files);
    fe_ta_progress_unlock(&fe_ta_rec,scd_ta.zones_cleared);
    fe_ta_unlocks_update(&fe_ta_rec);
    fe_ta_state=1;
}
static void fe_ta_commit(void){
    fe_ta_state=fe_ta_records_store(&fe_ta_saturn_io,fe_ta_preset,&fe_ta_rec,&fe_ta_files)?2:1;
}
/* The title only reads: the unlock and flags follow from the progress save and the
   records in memory, and reach backup RAM with the next record (retail writes the
   time attack data only when a run sets a record). A cold boot leaves it unchanged. */
__attribute__((noipa)) static unsigned fe_title_flags(unsigned zones_cleared){
    scd_ta.zones_cleared=(uint8_t)zones_cleared;
    fe_ta_load();
    fe_ta_progress_unlock(&fe_ta_rec,zones_cleared);
    fe_ta_unlocks_update(&fe_ta_rec);
    return fe_ta_rec.title_flags;
}

/* ---- Time Attack menu (PC TITLE/TA/TA.C game(); ATTACK.MMD) -------------------
   Columns follow TA.C gMenu2: 0 zone (round) list with EXIT at round 0, 1 the
   return button, 2 the act selector (zones only), 3 the start button, 4 a new
   record awaiting a press, 5 initials entry. Left on the zone list opens the
   special stage column once SpecialPlayChk passes (titleFlags bit 1). */
static const char fe_ta_zones[7][18]={"PALMTREE PANIC","COLLISION CHAOS","TIDAL TEMPEST",
    "QUARTZ QUADRANT","WACKY WORKBENCH","STARDUST SPEEDWAY","METALLIC MADNESS"};
/* Named arrays keep the text in .rodata.fe_* (string literals would stay resident). */
static const char fe_str0[]="SPECIAL STAGE TIME ATTACK";
static const char fe_str1[]="TIME ATTACK";
static const char fe_str2[]="EXIT";
static const char fe_str3[]=" ZONE";
static const char fe_str4[]="B BACK";
static const char fe_str5[]="STAGE ";
static const char fe_str6[]="SPECIAL STAGE";
static const char fe_str7[]="ACT ";
static const char fe_str8[]="1ST";
static const char fe_str9[]="2ND";
static const char fe_str10[]="3RD";
static const char fe_str11[]="TOTAL ";
static const char fe_str12[]="RETURN";
static const char fe_str13[]="START";
static const char fe_str14[]="NEW RECORD - PRESS A";
static const char fe_str15[]="INITIALS: UP/DOWN  A ON 3RD OK";
static const char fe_str16[]="RECORDS NOT SAVED";

static struct {
    uint8_t special,column,round,act,rank_y,rank_x,key_repeat,blink;
    int8_t rank;
} fe_ta_menu __attribute__((section(".data.fe_ta_menu")));
static unsigned fe_ta_rounds(void){
    if(fe_ta_menu.special)return 7;
    unsigned r=fe_ta_rec.unlock/3;   /* TA.C GetPlayRound: cleared zones, 1..7 */
    return r<1?1:r>7?7:r;
}
static unsigned fe_ta_entry(void){
    return fe_ta_menu.special?SCD_TA_ACTS+fe_ta_menu.round-1u:(fe_ta_menu.round-1u)*3u+fe_ta_menu.act;
}
static void fe_ta_enter(void){
    fe_ta_load();
    /* TA.C game_init CDPlay: the time attack song (Sound.inc CDDA_TMATK, cue 11). */
    scd_audio_music(11);
    if(scd_ta.pending){
        /* Back from a run: TA.C game_init with lpKeepWork ta_time set. */
        fe_ta_menu.special=scd_ta.column_special;fe_ta_menu.round=scd_ta.round;fe_ta_menu.act=scd_ta.act;
        fe_ta_menu.column=3;fe_ta_menu.rank=-1;
        if(!scd_ta.aborted){
            fe_ta_menu.rank=(int8_t)fe_ta_record_insert(&fe_ta_rec,fe_ta_entry(),scd_ta.frames);
            if(fe_ta_menu.rank>=0){
                fe_ta_menu.rank_y=(uint8_t)fe_ta_menu.rank;fe_ta_menu.rank_x=0;fe_ta_menu.column=4;
                fe_ta_unlocks_update(&fe_ta_rec);fe_ta_commit();
            }
        }
        scd_ta.pending=0;
    }else{
        memset(&fe_ta_menu,0,sizeof(fe_ta_menu));
        fe_ta_menu.round=1;fe_ta_menu.rank=-1;
    }
}
/* The HUD alphabet has + - / 0-9 : A-Z only, so a gray bar marks the cursor. */
static void fe_mark(int x,int y,unsigned chars){scd_frontend_panel(x-3,y-2,(int)chars*8+6,12,0x94a5);}
static void fe_ta_draw(void){
    char text[32],t[9];
    scd_frontend_panel(16,24,288,184,0x8800);
    scd_frontend_text(fe_ta_menu.special?60:116,32,fe_ta_menu.special?fe_str0:fe_str1);
    unsigned rounds=fe_ta_rounds();
    /* Zone (or special stage) list: column 0. */
    for(unsigned r=0;r<=rounds;r++){
        int y=52+(int)r*12;
        if(!r){memcpy(text,fe_str2,5);}
        else if(fe_ta_menu.special){memcpy(text,fe_str5,6);text[6]=(char)('0'+r);text[7]=0;}
        else{
            /* Two initials keep the list narrow: the full name heads the records. */
            const char *n=fe_ta_zones[r-1];unsigned k=0;text[k++]=n[0];
            for(const char *q=n;*q;q++)if(*q==' '){text[k++]=q[1];break;}
            memcpy(text+k,fe_str3,6);
        }
        if(r==fe_ta_menu.round && (fe_ta_menu.column || !(fe_ta_menu.blink&16)))fe_mark(32,y,(unsigned)strlen(text));
        scd_frontend_text(32,y,text);
    }
    if(!fe_ta_menu.round){scd_frontend_text(24,196,fe_str4);return;}
    unsigned entry=fe_ta_entry();
    scd_frontend_text(120,52,fe_ta_menu.special?fe_str6:fe_ta_zones[fe_ta_menu.round-1]);
    if(!fe_ta_menu.special){
        memcpy(text,fe_str7,4);text[4]=(char)('1'+fe_ta_menu.act);text[5]=0;
        if(fe_ta_menu.column==2)fe_mark(152,68,5);
        scd_frontend_text(152,68,text);
    }
    static const char *const fe_ta_place[3]={fe_str8,fe_str9,fe_str10};
    for(unsigned k=0;k<SCD_TA_RANKS;k++){
        int y=88+(int)k*14;
        fe_ta_time_text(t,fe_ta_rec.time[entry][k]);
        unsigned n=0;memcpy(text,fe_ta_place[k],3);n=3;text[n++]=' ';
        for(unsigned c=0;t[c];c++)text[n++]=t[c];
        text[n++]=' ';
        for(unsigned c=0;c<3;c++){
            int hide=fe_ta_menu.column==5 && (int)k==fe_ta_menu.rank_y && c==fe_ta_menu.rank_x && (fe_ta_menu.blink&8);
            text[n++]=hide?' ':fe_ta_name_char(fe_ta_rec.name[entry][k][c]);
        }
        text[n]=0;
        if(fe_ta_menu.column>=4 && (int)k==fe_ta_menu.rank_y)fe_mark(120,y,n);
        scd_frontend_text(120,y,text);
    }
    if(!fe_ta_menu.special){
        /* Sum of the 21 first places (TA.C 524-529), up to 209 minutes. */
        uint32_t total=fe_ta_act_total(&fe_ta_rec);  /* centiseconds */
        unsigned m=total/6000,sec=total/100%60,c=total%100;
        memcpy(text,fe_str11,6);
        text[6]=(char)('0'+m/100%10);text[7]=(char)('0'+m/10%10);text[8]=(char)('0'+m%10);
        text[9]=':';text[10]=(char)('0'+sec/10);text[11]=(char)('0'+sec%10);
        text[12]=':';text[13]=(char)('0'+c/10);text[14]=(char)('0'+c%10);text[15]=0;
        scd_frontend_text(120,140,text);
    }
    if(fe_ta_menu.column==1)fe_mark(128,160,6);
    scd_frontend_text(128,160,fe_str12);
    if(fe_ta_menu.column==3)fe_mark(216,160,5);
    scd_frontend_text(216,160,fe_str13);
    if(fe_ta_menu.column==4)scd_frontend_text(72,180,fe_str14);
    else if(fe_ta_menu.column==5)scd_frontend_text(48,180,fe_str15);
    if(fe_ta_state==2)scd_frontend_text(64,196,fe_str16);
}
static unsigned fe_ta_step(unsigned hold,unsigned tap){
    const unsigned confirm=SCD_PAD_A|SCD_PAD_C|SCD_PAD_START;
    fe_ta_menu.blink++;
    switch(fe_ta_menu.column){
    case 0:
        if(tap&confirm){
            if(!fe_ta_menu.round)return SCD_FE_TITLE;
            fe_ta_menu.column=fe_ta_menu.special?1:2;fe_ta_menu.act=0;
        }else if(tap&SCD_PAD_B)return SCD_FE_TITLE;
        else if(tap&SCD_PAD_LEFT){
            if(!fe_ta_menu.special && (fe_ta_rec.title_flags&SCD_TA_FLAG_SPECIAL)){fe_ta_menu.special=1;fe_ta_menu.round=1;}
        }else if(tap&SCD_PAD_RIGHT){
            if(fe_ta_menu.special){fe_ta_menu.special=0;fe_ta_menu.round=1;}
        }else if(tap&SCD_PAD_UP)fe_ta_menu.round=fe_ta_menu.round?fe_ta_menu.round-1:(uint8_t)fe_ta_rounds();
        else if(tap&SCD_PAD_DOWN)fe_ta_menu.round=fe_ta_menu.round>=fe_ta_rounds()?0:fe_ta_menu.round+1;
        break;
    case 4:
        if(tap){fe_ta_menu.column=5;fe_ta_menu.key_repeat=0;}
        break;
    case 5:{
        uint8_t *name=fe_ta_rec.name[fe_ta_entry()][fe_ta_menu.rank_y];
        if(tap&confirm){
            if(fe_ta_menu.rank_x==2){fe_ta_commit();fe_ta_menu.column=3;break;}
            tap|=SCD_PAD_RIGHT;
        }
        if(tap&SCD_PAD_LEFT){if(fe_ta_menu.rank_x)fe_ta_menu.rank_x--;break;}
        if(tap&SCD_PAD_RIGHT){if(fe_ta_menu.rank_x<2)fe_ta_menu.rank_x++;break;}
        /* TA.C 307-336: a press steps at once, a hold repeats every 16 frames;
           0-9 then A-Z, wrapping. */
        if(hold&(SCD_PAD_UP|SCD_PAD_DOWN))fe_ta_menu.key_repeat++;
        if(tap&(SCD_PAD_UP|SCD_PAD_DOWN))fe_ta_menu.key_repeat=16;
        if(fe_ta_menu.key_repeat>15){
            fe_ta_menu.key_repeat=0;
            int c=name[fe_ta_menu.rank_x];
            c+=hold&SCD_PAD_DOWN?1:-1;
            if(c==0x0A)c=hold&SCD_PAD_DOWN?0x0B:9;
            if(c<0)c=0x24;else if(c>0x24)c=0;
            name[fe_ta_menu.rank_x]=(uint8_t)c;
        }
        break;
    }
    default:
        if(fe_ta_menu.column==2 && !fe_ta_menu.special){
            if(tap&SCD_PAD_UP){fe_ta_menu.act=fe_ta_menu.act?fe_ta_menu.act-1:2;break;}
            if(tap&SCD_PAD_DOWN){fe_ta_menu.act=fe_ta_menu.act>=2?0:fe_ta_menu.act+1;break;}
        }
        if(tap&SCD_PAD_B){fe_ta_menu.column=0;break;}
        if(tap&confirm){
            if(fe_ta_menu.column==1){fe_ta_menu.column=0;break;}
            if(fe_ta_menu.column==3){
                scd_ta.entry=(uint8_t)fe_ta_entry();scd_ta.column_special=fe_ta_menu.special;
                scd_ta.round=fe_ta_menu.round;scd_ta.act=fe_ta_menu.act;
                return SCD_FE_TA_START;
            }
            if(fe_ta_menu.column==2){fe_ta_menu.column=3;break;}
        }
        if(tap&SCD_PAD_LEFT){
            if(!fe_ta_menu.special)fe_ta_menu.column=fe_ta_menu.column==2?1:fe_ta_menu.column==3?2:1;
            else if(fe_ta_menu.column==1)fe_ta_menu.column=3;
        }else if(tap&SCD_PAD_RIGHT){
            if(!fe_ta_menu.special)fe_ta_menu.column=fe_ta_menu.column==1?2:3;
            else if(fe_ta_menu.column==3)fe_ta_menu.column=1;
        }
        break;
    }
    fe_ta_draw();
    return SCD_FE_CONTINUE;
}

/* ---- Sound test ("Title Screen/Secrets/Sound Test.asm") -------------------------
   Left/Right pick FM, PCM or DA every 8 frames; Up/Down step the number every 8
   frames (UpdateSelection); A, B or C plays it; Start stops PCM and CD-DA and checks
   the FM/PCM/DA code table (CheckEasterEgg): 07/07/07 opens Special Stage 8. */
/* Sound Test.asm SelectFM .IDs: retail FM IDs, which are the native request numbers. */
static const uint8_t fe_st_fm[80]={144,145,146,147,148,149,150,151,152,153,154,155,155,157,158,159,160,161,162,163,
    164,165,165,167,168,168,170,170,172,173,174,175,176,177,178,179,180,181,182,183,184,185,186,187,188,189,190,191,192,
    193,194,195,195,197,198,199,200,201,202,203,204,205,206,207,208,208,210,211,212,213,214,215,216,217,218,219,220,221,
    222,223};
/* SelectPCM .IDs: ten voice clips (SCMD_FUTURESFXT..BUMPERSFXT, native requests
   117-126) then the Past music of zones 1, 3-8 (SCMD_R1BMUST..R8BMUST). */
enum { FE_ST_FM=80, FE_ST_PCM=17, FE_ST_DA=34 };
/* SelectCDDA .IDs as native music cues: present, good and bad future per zone, then
   boss, final, title, Time Attack, results, shoes, invincible, game over, special,
   D.A. Garden, prototype warp, intro, ending (src/music_routes.h cues; 0xFF: none). */
static const uint8_t fe_st_da[13]={8,10,9,11,4,5,6,12,7,13,16,14,15};
/* CheckEasterEgg .Codes (FM, PCM, DA) for exits 1-6. */
static const uint8_t fe_st_codes[6][3]={{7,7,7},{46,12,25},{42,3,1},{40,12,11},{42,4,21},{44,11,9}};
static struct { uint8_t type,fm,pcm,da,lr_delay,fm_delay,pcm_delay,da_delay,result,result_timer; } fe_st __attribute__((section(".data.fe_st")));
/* The sound test program starts with the CD stopped (the title's track ends with it). */
static void fe_st_enter(void){memset(&fe_st,0,sizeof(fe_st));scd_audio_stop_music();}
static void fe_st_play(void){
    if(fe_st.type==0){scd_audio_request((short)fe_st_fm[fe_st.fm]);return;}
    if(fe_st.type==1){
        if(fe_st.pcm<10){scd_audio_request((short)(117+fe_st.pcm));return;}
        scd_audio_stage(fe_st.pcm-10u,1);return;
    }
    if(fe_st.da<21){static const uint8_t fe_st_era[3]={0,2,3};scd_audio_stage(fe_st.da/3,fe_st_era[fe_st.da%3]);return;}
    uint8_t cue=fe_st_da[fe_st.da-21];
    if(cue!=0xFF)scd_audio_music(cue);
}
static const char fe_st_title[]="SOUND TEST";
static const char fe_st_fm_label[]="FM";
static const char fe_st_pcm_label[]="PCM";
static const char fe_st_da_label[]="DA";
static const char fe_st_help1[]="LEFT/RIGHT  FM PCM DA";
static const char fe_st_help2[]="UP/DOWN  NUMBER  ABC PLAY";
static const char fe_st_help3[]="START  EXIT";
static const char fe_st_ss8[]="WELCOME TO";
static const char fe_st_ss8b[]="SECRET SPECIAL STAGE";
static const char fe_st_none[]="NOT ON THIS DISC";
static void fe_st_number(int x,int y,unsigned n){char t[3]={(char)('0'+n/10%10),(char)('0'+n%10),0};scd_frontend_text(x,y,t);}
static void fe_st_draw(void){
    scd_frontend_panel(16,24,288,184,0x8800);
    scd_frontend_text(120,36,fe_st_title);
    static const char *const fe_st_labels[3]={fe_st_fm_label,fe_st_pcm_label,fe_st_da_label};
    const uint8_t values[3]={fe_st.fm,fe_st.pcm,fe_st.da};
    for(unsigned i=0;i<3;i++){
        int x=56+(int)i*80;
        if(i==fe_st.type)fe_mark(x,72,6);
        scd_frontend_text(x,72,fe_st_labels[i]);fe_st_number(x+32,72,values[i]);
    }
    if(fe_st.type==2 && fe_st.da>=21 && fe_st_da[fe_st.da-21]==0xFF)scd_frontend_text(96,96,fe_st_none);
    if(fe_st.result==1){scd_frontend_text(120,120,fe_st_ss8);scd_frontend_text(80,136,fe_st_ss8b);return;}
    scd_frontend_text(72,152,fe_st_help1);scd_frontend_text(56,166,fe_st_help2);scd_frontend_text(112,180,fe_st_help3);
}
/* UpdateSelection: Up/Down held change the number when the delay counter is a multiple of 8. */
static void fe_st_select(uint8_t *value,uint8_t delay,unsigned count,unsigned hold){
    if(delay&7)return;
    if(hold&SCD_PAD_UP)*value=*value?*value-1:(uint8_t)(count-1);
    if(hold&SCD_PAD_DOWN)*value=*value+1u>=count?0:*value+1;
}
static unsigned fe_st_step(unsigned hold,unsigned tap){
    if(fe_st.result==1){
        /* SoundTest_SpecStg8: the message shows for two seconds, then the warp. */
        if(++fe_st.result_timer>=120){scd_audio_request(0xC8);return SCD_FE_SPECIAL8;}
        fe_st_draw();return SCD_FE_CONTINUE;
    }
    fe_st.lr_delay++;fe_st.fm_delay++;fe_st.pcm_delay++;fe_st.da_delay++;
    if(!(fe_st.lr_delay&7)){
        if(hold&SCD_PAD_LEFT)fe_st.type=fe_st.type?fe_st.type-1:2;
        if(hold&SCD_PAD_RIGHT)fe_st.type=fe_st.type>=2?0:fe_st.type+1;
    }
    if(fe_st.type==0)fe_st_select(&fe_st.fm,fe_st.fm_delay,FE_ST_FM,hold);
    else if(fe_st.type==1)fe_st_select(&fe_st.pcm,fe_st.pcm_delay,FE_ST_PCM,hold);
    else fe_st_select(&fe_st.da,fe_st.da_delay,FE_ST_DA,hold);
    if(tap&(SCD_PAD_A|SCD_PAD_B|SCD_PAD_C))fe_st_play();
    if(hold&SCD_PAD_START){
        scd_audio_stop_music();  /* SCMD_STOPCDDA before CheckEasterEgg */
        /* CheckEasterEgg: 07/07/07 is Special Stage 8 (ring sound, message, warp). */
        for(unsigned i=0;i<6;i++)if(fe_st.fm==fe_st_codes[i][0] && fe_st.pcm==fe_st_codes[i][1] && fe_st.da==fe_st_codes[i][2]){
            if(!i){fe_st.result=1;fe_st.result_timer=0;scd_audio_request(0xA8);fe_st_draw();return SCD_FE_CONTINUE;}
            /* Exits 2-6: the secret pictures (Sound Test Image.asm, src/visual_mode.c),
               each with its music, started there after the picture's file loads.
               Then the title, as after the sound test. */
            fe_secret_image(i);
            scd_audio_stop_music();
            break;
        }
        return SCD_FE_TITLE;
    }
    fe_st_draw();
    return SCD_FE_CONTINUE;
}

/* ---- Attract zone demos -------------------------------------------------------
   cd/DEMOS.BIN (tools/prepare_demos.py): the retail R11A, R43C and R82A input, read
   into the title pack region (TITLE.BIN, PACK_TITLE_ADDRESS, src/stage_packs.h), which
   title_begin(1) reads again after the demo. src/frontend_view.inc plays it. */
static const char fe_demos_file[]="DEMOS.BIN";
int fe_demo_load(void){
    const cdfs_filelist_t *root=scd_cd_root_read();
    for(unsigned i=0;i<root->entries_count;i++)if(!strcmp(root->entries[i].name,fe_demos_file)){
        if(root->entries[i].size!=3*0x1000u ||
           cd_block_sectors_read(root->entries[i].starting_fad,(void *)PACK_TITLE_ADDRESS,3*0x1000u))return 0;
        cpu_cache_purge();return 1;
    }
    return 0;
}

/* ---- Movies (opening in the attract cycle, Visual Mode) -------------------------
   The player (fmv_play, src/fmv_saturn.c) is R0 code too. It takes low work RAM
   0x200000-0x247FFF, the PPZ0-PPZ2 packs (new_game() reloads them), the effect
   bank's tail and the sprite priorities, and leaves the display off. */
int fe_frontend_movie(unsigned id){
    scd_low_packs_lost=1;
    /* The title's CD-DA track holds the drive (retail loads the FMV program after it). */
    scd_audio_stop_music();
    /* id | FE_MOVIE_FROM_TITLE (attract): leave the title's automatic VDP1 mode, in which
       frame waits never return, for gameplay's manual one, and turn the display back on
       (title_end cleared it), as src/main.c does before its level select. Front-end
       screens are in that mode already; setting it again there stalls VDP1. */
    if(id&FE_MOVIE_FROM_TITLE){vdp1_sync_wait();vdp1_sync_interval_set(-1);vdp2_tvmd_display_set();}
    int r=fmv_play((fmv_id_t)(id&0xFF));
    vdp2_sprite_priority_set(0,4);vdp2_sprite_priority_set(1,7);scd_audio_bank(-1);
    return r;
}

/* ---- Visual Mode: src/visual_mode.c (IPX.asm VisualMode, Visual Mode/Main.asm). The
   menu and its movies run there until EXIT, then the title comes back. */
static unsigned fe_vm_step(void){fe_visual_mode();return SCD_FE_TITLE;}

/* ---- Dispatch ----------------------------------------------------------------- */
static uint8_t FE_DATA(fe_screen);
__attribute__((noipa)) static void fe_enter(unsigned screen){
    fe_screen=(uint8_t)screen;
    if(screen==SCD_FE_TIME_ATTACK)fe_ta_enter();
    else if(screen==SCD_FE_SOUND_TEST)fe_st_enter();
}
__attribute__((noipa)) static unsigned fe_step(unsigned hold,unsigned tap){
    if(fe_screen==SCD_FE_TIME_ATTACK)return fe_ta_step(hold,tap);
    if(fe_screen==SCD_FE_SOUND_TEST)return fe_st_step(hold,tap);
    if(fe_screen==SCD_FE_VISUAL)return fe_vm_step();
    if(fe_screen==SCD_FE_STAFF_TIMES){fe_staff_times();return SCD_FE_TITLE;}
    if(fe_screen==SCD_FE_COMING){fe_coming(fe_stage_select_qa.held);return SCD_FE_TITLE;}
    if(fe_screen==SCD_FE_STAGE_SELECT){
        unsigned selected=fe_stage_select();
        if(selected>=FE_SEL_COUNT)return SCD_FE_TITLE;
        return SCD_FE_STAGE_SELECT_CHOICE|selected<<8;
    }
    return SCD_FE_TITLE;
}
/* Read-only handoff. Resident callers never dereference R0 data directly. */
__attribute__((noipa)) static int fe_stage_select_snapshot(unsigned selected,
        fe_stage_select_choice *choice,unsigned *previous_hold){
    if(fe_screen!=SCD_FE_STAGE_SELECT || selected>=FE_SEL_COUNT || !choice || !previous_hold)return 0;
    *choice=fe_stage_select_choices[selected];
    *previous_hold=fe_stage_select_qa.held;
    return 1;
}
/* Resident (src/saturn.x .zone_resident keeps *zone_ops* out of the overlay). */
const scd_frontend_ops fe_frontend_zone_ops={fe_enter,fe_step,fe_title_flags,fe_stage_select_snapshot,fe_frontend_movie};
