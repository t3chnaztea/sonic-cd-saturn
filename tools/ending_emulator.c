/* Game ending route in Beetle Saturn (tools/test_ending_emulator.py drives it).
 *
 *   ending_emulator core.dylib game.cue bios-dir out-dir trace-mailbox world-mailbox act-fade
 *
 * Backup RAM comes from SCD_BACKUP_INPUT (a crafted Metallic Madness Act 3 save).
 * The title's Continue starts that act; after 120 gameplay updates the harness sets
 * act_fade to 1, which is what src/main.c does when EMIE8 ends the game
 * (scd_boss8_game_end). Then it watches the ending through the world mailbox [137]
 * (src/main.c) and the movie mailbox in low work RAM (FMV_LWRAM_STATE,
 * src/fmv_saturn.h) until the title screen is back, and writes ending.json plus
 * screenshots. Emulator evidence only. */
#include <libretro.h>
#include <dlfcn.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

static unsigned pixel_format,frame,button_mask;
static const char *system_dir,*output_dir;
static void *pixels;static size_t pixels_capacity,last_pitch;static unsigned last_width,last_height;static int have_video;
static uint64_t audio_energy;static uint64_t audio_samples;

/* Backup RAM in and out (as tools/save_replay.h: Beetle's BackupRAM stays valid
   through retro_deinit and is written back on exit). */
static uint8_t *backup_bytes;static size_t backup_size;
static void backup_flush(void){
    const char *path=getenv("SCD_BACKUP_OUTPUT");if(!path || !backup_bytes)return;
    FILE *f=fopen(path,"wb");if(!f || fwrite(backup_bytes,1,backup_size,f)!=backup_size || fclose(f)){perror(path);_Exit(2);}
}
static int backup_open(void *(*data)(unsigned),size_t (*size)(unsigned)){
    backup_bytes=data(RETRO_MEMORY_SAVE_RAM);backup_size=size(RETRO_MEMORY_SAVE_RAM);
    const char *path=getenv("SCD_BACKUP_INPUT");
    if(!path)return 0;
    if(!backup_bytes || backup_size!=32768){fprintf(stderr,"Expected 32 KiB internal backup RAM\n");return -1;}
    FILE *f=fopen(path,"rb");if(!f){perror(path);return -1;}
    if(fread(backup_bytes,1,backup_size,f)!=backup_size || fgetc(f)!=EOF){fclose(f);return -1;}
    fclose(f);atexit(backup_flush);return 0;
}

static void logger(enum retro_log_level level,const char *fmt,...){(void)level;va_list a;va_start(a,fmt);vfprintf(stderr,fmt,a);va_end(a);}
static bool environment(unsigned command,void *data){
    switch(command){
    case RETRO_ENVIRONMENT_GET_SYSTEM_DIRECTORY:
    case RETRO_ENVIRONMENT_GET_SAVE_DIRECTORY:*(const char **)data=system_dir;return true;
    case RETRO_ENVIRONMENT_GET_LOG_INTERFACE:((struct retro_log_callback *)data)->log=logger;return true;
    case RETRO_ENVIRONMENT_SET_PIXEL_FORMAT:pixel_format=*(unsigned *)data;return pixel_format<=2;
    case RETRO_ENVIRONMENT_GET_CAN_DUPE:*(bool *)data=true;return true;
    case RETRO_ENVIRONMENT_GET_VARIABLE_UPDATE:*(bool *)data=false;return true;
    case RETRO_ENVIRONMENT_GET_CORE_OPTIONS_VERSION:*(unsigned *)data=0;return true;
    case RETRO_ENVIRONMENT_GET_VARIABLE:{
        struct retro_variable *v=data;
        if(!strcmp(v->key,"beetle_saturn_region")){v->value="North America";return true;}
        if(!strcmp(v->key,"beetle_saturn_cart")){v->value="None";return true;}
        if(strstr(v->key,"jit")){v->value="disabled";return true;}
        v->value=NULL;return false;
    }
    case RETRO_ENVIRONMENT_SET_VARIABLES:
    case RETRO_ENVIRONMENT_SET_INPUT_DESCRIPTORS:
    case RETRO_ENVIRONMENT_SET_CONTROLLER_INFO:
    case RETRO_ENVIRONMENT_SET_SUPPORT_NO_GAME:
    case RETRO_ENVIRONMENT_SET_PERFORMANCE_LEVEL:
    case RETRO_ENVIRONMENT_SET_GEOMETRY:
    case RETRO_ENVIRONMENT_SET_SYSTEM_AV_INFO:return true;
    default:return false;
    }
}
static void video(const void *data,unsigned width,unsigned height,size_t pitch){
    if(!data || data==RETRO_HW_FRAME_BUFFER_VALID)return;
    if(pitch*height>pixels_capacity){pixels_capacity=pitch*height;pixels=realloc(pixels,pixels_capacity);if(!pixels)abort();}
    memcpy(pixels,data,pitch*height);last_width=width;last_height=height;last_pitch=pitch;have_video=1;
}
static void audio_sample(int16_t l,int16_t r){audio_energy+=(uint64_t)((int32_t)l*l)+(uint64_t)((int32_t)r*r);audio_samples+=2;}
static void audio(int16_t l,int16_t r){audio_sample(l,r);}
static size_t audio_batch(const int16_t *d,size_t n){for(size_t i=0;i<n;i++)audio_sample(d[i*2],d[i*2+1]);return n;}
static void input_poll(void){}
static int16_t input_state(unsigned port,unsigned device,unsigned index,unsigned id){
    (void)index;if(port || device!=RETRO_DEVICE_JOYPAD || id>=16)return 0;return (button_mask>>id)&1;
}
static uint32_t ram_word(const uint8_t *ram,size_t offset){
    /* Beetle exposes native-endian 16-bit words; Saturn bytes are big endian. */
    uint16_t high,low;memcpy(&high,ram+offset,2);memcpy(&low,ram+offset+2,2);return ((uint32_t)high<<16)|low;
}
static void ram_put_word(uint8_t *ram,size_t offset,uint32_t value){
    uint16_t high=(uint16_t)(value>>16),low=(uint16_t)value;memcpy(ram+offset,&high,2);memcpy(ram+offset+2,&low,2);
}
/* Screenshot as PPM; returns the FNV-1a hash and the share of non-black pixels (per mille). */
static uint64_t screenshot(const char *name,unsigned *lit){
    char path[4096];snprintf(path,sizeof(path),"%s/%s.ppm",output_dir,name);
    FILE *f=fopen(path,"wb");if(!f){perror(path);exit(2);}
    fprintf(f,"P6\n%u %u\n255\n",last_width,last_height);
    uint64_t hash=1469598103934665603ULL;unsigned nonblack=0;
    for(unsigned y=0;y<last_height;y++)for(unsigned x=0;x<last_width;x++){
        const uint8_t *p=(const uint8_t *)pixels+y*last_pitch;unsigned r,g,b;
        if(pixel_format==RETRO_PIXEL_FORMAT_XRGB8888){uint32_t v;memcpy(&v,p+x*4,4);r=(v>>16)&255;g=(v>>8)&255;b=v&255;}
        else{uint16_t v;memcpy(&v,p+x*2,2);
            if(pixel_format==RETRO_PIXEL_FORMAT_RGB565){r=(v>>11)*255/31;g=((v>>5)&63)*255/63;}
            else{r=((v>>10)&31)*255/31;g=((v>>5)&31)*255/31;}
            b=(v&31)*255/31;}
        unsigned char rgb[]={r,g,b};fwrite(rgb,1,3,f);nonblack+=(r|g|b)!=0;
        for(unsigned i=0;i<3;i++){hash^=rgb[i];hash*=1099511628211ULL;}
    }
    fclose(f);
    if(lit)*lit=last_width && last_height?(unsigned)((uint64_t)nonblack*1000/(last_width*last_height)):0;
    return hash;
}

/* Run-length pad script from tools/special_retail.py ("stage|results v pad" lines). */
static unsigned win_pads[2][16000];
static int load_win_pads(const char *path){
    FILE *file=fopen(path,"r");if(!file){perror(path);return 1;}
    char phase[16];unsigned v,pad,last[2]={0,0},value[2]={0,0};
    while(fscanf(file,"%15s %u %u",phase,&v,&pad)==3){
        unsigned results=!strcmp(phase,"results");if(v>=16000){fclose(file);return 1;}
        for(unsigned i=last[results];i<v;i++)win_pads[results][i]=value[results];
        last[results]=v;value[results]=pad;
    }
    for(unsigned p=0;p<2;p++)for(unsigned i=last[p];i<16000;i++)win_pads[p][i]=value[p];
    fclose(file);return 0;
}
static unsigned win_mask(unsigned md){
    /* Mega Drive B is Saturn B (libretro A); Start and the D-pad map directly. */
    return (md&1?1u<<RETRO_DEVICE_ID_JOYPAD_UP:0)|(md&2?1u<<RETRO_DEVICE_ID_JOYPAD_DOWN:0)|(md&4?1u<<RETRO_DEVICE_ID_JOYPAD_LEFT:0)|
        (md&8?1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT:0)|(md&16?1u<<RETRO_DEVICE_ID_JOYPAD_A:0)|(md&128?1u<<RETRO_DEVICE_ID_JOYPAD_START:0);
}
#define TRACE_TITLE 0x5449544cu   /* 'TITL' */
#define TRACE_GAME 0x53434432u    /* 'SCD2' */
#define FMV_PLAYING 0x464D5650u
#define FMV_DONE 0x464D5644u
#define FMV_BOX 0x43000u          /* FMV_LWRAM_STATE 0x00243000 in the core's RAM view */

int main(int argc,char **argv){
    if(argc!=8){fprintf(stderr,"usage: ending_emulator core.dylib game.cue bios-dir out-dir trace world act-fade\n");return 2;}
    system_dir=argv[3];output_dir=argv[4];
    void *core=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);if(!core){fprintf(stderr,"%s\n",dlerror());return 2;}
#define LOAD(name) __typeof__(&name) p_##name=(__typeof__(&name))dlsym(core,#name);if(!p_##name)abort()
    LOAD(retro_init);LOAD(retro_deinit);LOAD(retro_load_game);LOAD(retro_unload_game);LOAD(retro_run);
    LOAD(retro_set_environment);LOAD(retro_set_video_refresh);LOAD(retro_set_audio_sample);LOAD(retro_set_audio_sample_batch);
    LOAD(retro_set_input_poll);LOAD(retro_set_input_state);LOAD(retro_get_memory_data);LOAD(retro_get_memory_size);
    p_retro_set_environment(environment);p_retro_set_video_refresh(video);
    p_retro_set_audio_sample(audio);p_retro_set_audio_sample_batch(audio_batch);
    p_retro_set_input_poll(input_poll);p_retro_set_input_state(input_state);p_retro_init();
    struct retro_game_info game={.path=argv[2]};
    if(!p_retro_load_game(&game)){fprintf(stderr,"Game load failed\n");return 2;}
    if(backup_open(p_retro_get_memory_data,p_retro_get_memory_size))return 2;
    const size_t trace=0x100000+(strtoul(argv[5],NULL,16)&0xfffff);
    const size_t world=0x100000+(strtoul(argv[6],NULL,16)&0xfffff);
    const size_t fade=0x100000+(strtoul(argv[7],NULL,16)&0xfffff);
    for(unsigned boot=0;boot<200;boot++)p_retro_run();

    /* Stones mode (SCD_STONES: hex addresses special_mode,time_stones,fade_white,era,stage_act).
       SCD_STONES_KIND=ring: from PPZ Act 1 the big ring fixture (Start+C+Left), a jump into
       the big ring and the retail Special Stage 1 win route (SCD_SPECIAL_GAME mailbox,
       SCD_WIN_PAD file, as tools/emulator_test.c bigring mode). SCD_STONES_KIND=end: the act
       ends at once (act_fade=1). Then the harness records the next act's start. */
    /* SCD_OBJ_GOOD: objects.c good_future, the flag past generators and badniks read. */
    const size_t obj_good=getenv("SCD_OBJ_GOOD")?0x100000+(strtoul(getenv("SCD_OBJ_GOOD"),NULL,16)&0xfffff):0;
    size_t sym[5]={0};int stones_mode=0,ring_mode=0;size_t game_box=0;
    if(getenv("SCD_STONES")){
        const char *t=getenv("SCD_STONES");
        for(unsigned i=0;i<5;i++){char *end;sym[i]=0x100000+(strtoul(t,&end,16)&0xfffff);if(*end!=(i<4?',':0)){fprintf(stderr,"bad SCD_STONES\n");return 2;}t=end+1;}
        stones_mode=1;ring_mode=getenv("SCD_STONES_KIND") && !strcmp(getenv("SCD_STONES_KIND"),"ring");
        if(ring_mode){
            if(!getenv("SCD_SPECIAL_GAME") || !getenv("SCD_WIN_PAD"))return 2;
            game_box=0x100000+(strtoul(getenv("SCD_SPECIAL_GAME"),NULL,16)&0xfffff);
            if(load_win_pads(getenv("SCD_WIN_PAD")))return 2;
        }
    }
    enum {S_MODE=0,S_STONES,S_WHITE,S_ERA,S_ACT};
    unsigned obj_good_before=99,good_before=0,special_frames=0,return_frame=0,white_seen=0,stones_before=0,return_act_before=0,ring_frames=0,jump=0,white_frame=0;
    enum {TITLE,GAME,ENDING,BACK,SPECIAL,RETURNED} phase=TITLE;
    unsigned gameplay=0,zone=99,act=99,fade_frame=0,movie_start=0,movie_end=0,title_frame=0,title_seen_after=0;
    uint32_t record=0,last_record=0,fmv[16]={0},peak_shown=0,max_steps=0,first_roll_frame=0,end_screen_frame=0;
    uint64_t movie_energy_start=0,movie_samples_start=0,movie_energy=0,movie_samples=0;
    unsigned shots=0,last_lit=0,title_lit=0,end_tail=0;char shot_log[8192];size_t shot_len=0;
    #define SHOT(label) do{unsigned lit;uint64_t h=screenshot(label,&lit);last_lit=lit;shot_len+=(size_t)snprintf(shot_log+shot_len,sizeof(shot_log)-shot_len,"%s{\"name\":\"%s\",\"frame\":%u,\"hash\":\"%016llx\",\"lit_per_mille\":%u}",shots++?",":"",label,frame,(unsigned long long)h,lit);}while(0)
    int took_video=0,took_roll=0,took_end=0;
    for(frame=0;frame<40000;frame++){
        uint8_t *ram=p_retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM);
        uint32_t magic=ram_word(ram,trace),state=ram_word(ram,trace+8);
        record=ram_word(ram,world+137*4);
        for(unsigned i=0;i<16;i++)fmv[i]=ram_word(ram,FMV_BOX+i*4);
        button_mask=0;
        if(phase==TITLE){
            if(magic==TRACE_GAME){phase=GAME;}
            else if(magic==TRACE_TITLE){
                unsigned selection=(state>>16)&255;
                if((state&255)==2 && !selection && frame%8<4)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_START;
                /* Continue is menu entry 2; libretro B is Saturn A (select). */
                else if((state&256) && frame%8<4)button_mask=1u<<(selection<2?RETRO_DEVICE_ID_JOYPAD_RIGHT:selection>2?RETRO_DEVICE_ID_JOYPAD_LEFT:RETRO_DEVICE_ID_JOYPAD_B);
            }
        }
        if(phase==GAME){
            zone=ram_word(ram,world+142*4);act=ram_word(ram,world+134*4);
            if(magic==TRACE_GAME && ++gameplay==120){
                if(!stones_mode && (zone!=6 || act!=2)){fprintf(stderr,"Continue did not start Metallic Madness Act 3 (zone %u act %u)\n",zone,act);return 2;}
                SHOT("mm3");
                /* src/main.c: scd_boss8_game_end() && !act_fade -> act_fade=1. */
                if(ram_word(ram,fade)!=0){fprintf(stderr,"act_fade busy\n");return 2;}
                if(stones_mode){
                    stones_before=ram_word(ram,sym[S_STONES]);return_act_before=act;good_before=ram_word(ram,world+6*4);obj_good_before=obj_good?ram_word(ram,obj_good):99;fade_frame=frame;phase=SPECIAL;
                    if(!ring_mode)ram_put_word(ram,fade,1);
                }else{ram_put_word(ram,fade,1);fade_frame=frame;phase=ENDING;}
            }
        }
        if(phase==SPECIAL && ring_mode){
            ring_frames++;
            if(ring_frames<5)button_mask=(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_R)|(1u<<RETRO_DEVICE_ID_JOYPAD_LEFT);
            else if(ram_word(ram,game_box)==0x5353474d && ram_word(ram,game_box+108)){
                /* Special Stage 1: the retail win route's pad script, by special-stage V-INT. */
                /* Lead 2 V-INTs, as tools/emulator_test.c game_lead. */
                unsigned v=ram_word(ram,game_box+4)+2,results=ram_word(ram,game_box+8)>=5;
                button_mask=win_mask(win_pads[results][v<16000?v:15999]);
            }else if(!special_frames){
                /* Past the goal post and the signpost, under the big ring (X 10608): jump in. */
                unsigned x=ram_word(ram,world+52),flags=ram_word(ram,world+64);
                if(x<10585)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT;
                else if(x>=10640)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_LEFT;
                if(jump){jump--;button_mask|=1u<<RETRO_DEVICE_ID_JOYPAD_B;}
                else if(x>=10585 && x<10640 && !(flags&2))jump=20;
            }
            if(ram_word(ram,sym[S_MODE]))special_frames++;
            if(special_frames==600)SHOT("special");
            if(special_frames && !ram_word(ram,sym[S_MODE])){phase=RETURNED;return_frame=frame;}
            if(ring_frames>20000){fprintf(stderr,"special stage did not return\n");break;}
        }
        if(phase==SPECIAL && !ring_mode && ram_word(ram,sym[S_ACT])!=return_act_before){phase=RETURNED;return_frame=frame;}
        if(phase==RETURNED){
            /* The next act may take many frames to load; the fade starts after it. */
            if(ram_word(ram,sym[S_WHITE])){if(!white_seen++){white_frame=frame;SHOT("return-fade");}}
            if(magic==TRACE_GAME && white_frame && frame-white_frame==300){SHOT("return");break;}
            if(!ring_mode && magic==TRACE_GAME && !white_seen && frame-return_frame==1200){SHOT("return");break;}
            if(frame-return_frame>3000){fprintf(stderr,"next act did not settle\n");break;}
        }
        if(phase==ENDING){
            if(!movie_start && fmv[1]==FMV_PLAYING){movie_start=frame;movie_energy_start=audio_energy;movie_samples_start=audio_samples;}
            if(fmv[1]==FMV_PLAYING){
                if(fmv[5]>peak_shown)peak_shown=fmv[5];
                if(fmv[12]>max_steps){if(!first_roll_frame)first_roll_frame=frame;max_steps=fmv[12];end_screen_frame=frame;}
                if(!took_video && fmv[5]>=200 && have_video){SHOT("movie");took_video=1;}
                if(!took_roll && fmv[12]>=2400 && have_video){SHOT("staff-roll");took_roll=1;}
            }
            /* The end screen: the roll has not stepped for 3 s (RS, job 11). */
            if(fmv[1]==FMV_PLAYING && took_roll && !took_end && frame-end_screen_frame==180){SHOT("end-screen");took_end=1;}
            /* Then every 4 s until the movie ends: RS can follow the roll by several seconds. */
            if(fmv[1]==FMV_PLAYING && took_end && (frame-end_screen_frame)%120==0 && end_tail<40){
                char label[32];snprintf(label,sizeof(label),"end-%02u",end_tail++);SHOT(label);
            }
            /* The "PRESENTED BY SEGA" card after the stream (src/fmv_saturn.h FMV_CARD_PICTURE,
               phase 4 holding): the Japanese ENDING.MMD holds it until Start. */
            if(fmv[1]==FMV_PLAYING && (fmv[3]>>16)==0xCA04u && (fmv[3]&0xFFFFu)>=60 && frame%8<4)
                button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_START;
            if(movie_start && !movie_end && fmv[1]==FMV_DONE){movie_end=frame;movie_energy=audio_energy-movie_energy_start;movie_samples=audio_samples-movie_samples_start;}
            if(record&0x80000000u){phase=BACK;title_frame=frame;}
            if(record)last_record=record;
        }
        if(phase==BACK && magic==TRACE_TITLE){
            ++title_seen_after;
            if(title_seen_after==120)SHOT("title-120");
            if(title_seen_after==600){SHOT("title");title_lit=last_lit;break;}
        }
        p_retro_run();
    }
    char path[4096];snprintf(path,sizeof(path),"%s/ending.json",output_dir);
    FILE *f=fopen(path,"w");if(!f){perror(path);return 2;}
    if(stones_mode){
        uint8_t *ram=p_retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM);
        fprintf(f,"{\"phase\":%d,\"frames\":%u,\"zone\":%u,\"act_before\":%u,\"stones_before\":%u,\"world_good_future_before\":%u,\"objects_good_future_before\":%u,\"objects_good_future\":%u,\"special_frames\":%u,"
                  "\"return_frame\":%u,\"white_frame\":%u,\"white_frames\":%u,\"stage_act\":%u,\"era\":%u,\"time_stones\":%u,\"world_good_future\":%u,\"shots\":[%s]}\n",
                (int)phase,frame,zone,return_act_before,stones_before,good_before,obj_good_before,obj_good?ram_word(ram,obj_good):99,special_frames,return_frame,white_frame,white_seen,
                ram_word(ram,sym[S_ACT]),ram_word(ram,sym[S_ERA]),ram_word(ram,sym[S_STONES]),ram_word(ram,world+6*4),shot_log);
        fclose(f);p_retro_unload_game();p_retro_deinit();
        return phase==RETURNED && frame-return_frame<=3000?0:1;
    }
    fprintf(f,"{\"phase\":%d,\"frames\":%u,\"zone\":%u,\"act\":%u,\"fade_frame\":%u,\"movie_start\":%u,\"movie_end\":%u,"
              "\"title_frame\":%u,\"title_after\":%u,\"title_lit_per_mille\":%u,\"record\":%u,\"last_record\":%u,\"fmv\":[",
            (int)phase,frame,zone,act,fade_frame,movie_start,movie_end,title_frame,title_seen_after,title_lit,record,last_record);
    for(unsigned i=0;i<16;i++)fprintf(f,"%s%u",i?",":"",fmv[i]);
    fprintf(f,"],\"peak_shown\":%u,\"roll_steps\":%u,\"movie_audio_rms\":%.1f,\"shots\":[%s]}\n",
            peak_shown,max_steps,movie_samples?__builtin_sqrt((double)movie_energy/(double)movie_samples):0.0,shot_log);
    fclose(f);
    p_retro_unload_game();p_retro_deinit();
    return phase==BACK && title_seen_after>=600?0:1;
}
