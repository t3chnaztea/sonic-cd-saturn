/* Script-driven emulator harness for the front-end screens (title menu, Time Attack,
   sound test, attract demos). tools/test_frontend_emulator.py builds it, resolves the
   symbols and writes the scripts. Host-only: it presses pads and reads memory; it
   never writes game work RAM. Explicit backup fixtures use only SAVE_RAM.

   argv: core cue system_dir output_dir script
   env:  SCD_SYMS "name=hex,name=hex" (high work RAM symbols; "trace" is required)
         SCD_BACKUP_INPUT / SCD_BACKUP_OUTPUT  32 KiB internal backup RAM image
          SCD_BACKUP_RETRY_INPUT  opt-in 32 KiB retry fixture; backup_retry only
   Script, one command per line ('#' comments). Buttons are Saturn names joined by
   '+': UP DOWN LEFT RIGHT A B C X Y Z L R START, or NONE.
     run N                     N frames, no buttons
     hold BUTTONS N            N frames with BUTTONS down
     tap BUTTONS               4 frames down, 4 up
     until MAGIC MAX           run until trace word 0 is MAGIC (4 characters)
     until_word SYM OFF VALUE MAX   run until the 32-bit word at SYM+OFF equals VALUE (hex)
     route FILE MAX            play SCD button bits (src/scd_player.h) per gameplay
                               simulation update from the SCD2 trace, until the trace
                               leaves gameplay or MAX frames
     peek LABEL SYM OFF WORDS  print WORDS 32-bit words at SYM+OFF (aligned down)
     peekb LABEL SYM OFF BYTES print BYTES bytes at SYM+OFF (any alignment)
      backup_retry              one-shot SAVE_RAM fixture at failed TA final initials
     bigring MAX               after the Start+C+Left fixture: steer to the big ring
                               (X 10585-10640, jump when grounded; emulator_test.c
                               bigring) until the trace leaves gameplay or MAX frames
     demotrace FILE MAX        while an attract demo runs (symbol "slot" non-zero), write
                               "demo_frame x y trace_sequence" per demo input word (symbols "frame",
                               "world": x at +52, y at +72), MAX frames at most
     updatetrace FILE MAX      while a demo runs: per gameplay update (SCD2 trace record)
                               "seq sim accepted_buttons demo_frame x y"
     energy LABEL N            run N frames and print the summed |sample| of the audio output
     shot NAME                 write NAME.ppm
     fail_unless_magic MAGIC   stop with status 3 unless the trace shows MAGIC
   Every line prints "frame=<n> <command>" results to stdout. */
#include <libretro.h>
#include <dlfcn.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

static const char *system_dir,*output_dir;
static unsigned pixel_format,frame,button_mask;
static const void *last_video;static unsigned last_width,last_height;static size_t last_pitch;
static uint8_t *pixels;static size_t pixels_capacity;
static void *(*mem_data)(unsigned);static size_t (*mem_size)(unsigned);
static void (*core_run)(void);
static char sym_names[64][48];static uint32_t sym_values[64];static unsigned sym_count;
static unsigned staff_opposite_queries,staff_opposite_enabled,staff_input_logs;
static unsigned staff_input_log_frame[3];
static bool staff_raw_diagnostic(void){
    const char *flag=getenv("SCD_STAFF_OPPOSITE_DIRECTIONS");
    return flag && !strcmp(flag,"1");
}

static void logger(enum retro_log_level level,const char *fmt,...){
    if(level<RETRO_LOG_WARN)return;
    va_list ap;va_start(ap,fmt);vfprintf(stderr,fmt,ap);va_end(ap);
}
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
        if(!strcmp(v->key,"beetle_saturn_opposite_directions")){
            const char *staff_raw=getenv("SCD_STAFF_OPPOSITE_DIRECTIONS");
            if(staff_raw && !strcmp(staff_raw,"1")){
                staff_opposite_queries++;staff_opposite_enabled++;
                fprintf(stderr,"staff_raw_option query=%u key=%s value=enabled\n",staff_opposite_queries,v->key);
                v->value="enabled";return true;
            }
        }
        v->value=NULL;return false;
    }
    case RETRO_ENVIRONMENT_SET_VARIABLES:
    case RETRO_ENVIRONMENT_SET_INPUT_DESCRIPTORS:
    case RETRO_ENVIRONMENT_SET_CONTROLLER_INFO:
    case RETRO_ENVIRONMENT_SET_SUPPORT_NO_GAME:
    case RETRO_ENVIRONMENT_SET_PERFORMANCE_LEVEL:
    case RETRO_ENVIRONMENT_SET_GEOMETRY:return true;
    default:return false;
    }
}
static void video(const void *data,unsigned width,unsigned height,size_t pitch){
    if(!data)return;
    if(pitch*height>pixels_capacity){pixels_capacity=pitch*height;pixels=realloc(pixels,pixels_capacity);if(!pixels)abort();}
    memcpy(pixels,data,pitch*height);last_video=pixels;last_width=width;last_height=height;last_pitch=pitch;
}
/* Audio energy (sum of |sample|) for the "energy" command. */
static uint64_t audio_energy;
static void audio(int16_t l,int16_t r){audio_energy+=(uint64_t)abs(l)+(uint64_t)abs(r);}
static size_t audio_batch(const int16_t *data,size_t frames){for(size_t i=0;i<frames*2;i++)audio_energy+=(uint64_t)abs(data[i]);return frames;}
static void input_poll(void){}
static int16_t input_state(unsigned port,unsigned device,unsigned index,unsigned id){
    if(staff_raw_diagnostic() && staff_input_logs<64 && !port && device==RETRO_DEVICE_JOYPAD &&
       (button_mask&((1u<<RETRO_DEVICE_ID_JOYPAD_UP)|(1u<<RETRO_DEVICE_ID_JOYPAD_DOWN)))==
       ((1u<<RETRO_DEVICE_ID_JOYPAD_UP)|(1u<<RETRO_DEVICE_ID_JOYPAD_DOWN)) &&
       (id==RETRO_DEVICE_ID_JOYPAD_UP || id==RETRO_DEVICE_ID_JOYPAD_DOWN || id==RETRO_DEVICE_ID_JOYPAD_MASK)){
        unsigned at=id==RETRO_DEVICE_ID_JOYPAD_UP?0:id==RETRO_DEVICE_ID_JOYPAD_DOWN?1:2;
        if(staff_input_log_frame[at]!=frame+1){
            staff_input_log_frame[at]=frame+1;staff_input_logs++;
            int value=id<16?(int)((button_mask>>id)&1):0;
            fprintf(stderr,"staff_raw_input frame=%u port=%u device=%u index=%u id=%u mask=%08x value=%d\n",frame,port,device,index,id,button_mask,value);
        }
    }
    (void)index;if(port || device!=RETRO_DEVICE_JOYPAD || id>=16)return 0;
    return (button_mask>>id)&1;
}
/* beetle-saturn input.c: Saturn A=B, B=A, C=R, X=Y, Y=X, Z=L, L=L2, R=R2. */
static unsigned buttons(const char *text){
    static const struct {const char *name;unsigned id;} map[]={
        {"UP",RETRO_DEVICE_ID_JOYPAD_UP},{"DOWN",RETRO_DEVICE_ID_JOYPAD_DOWN},{"LEFT",RETRO_DEVICE_ID_JOYPAD_LEFT},
        {"RIGHT",RETRO_DEVICE_ID_JOYPAD_RIGHT},{"A",RETRO_DEVICE_ID_JOYPAD_B},{"B",RETRO_DEVICE_ID_JOYPAD_A},
        {"C",RETRO_DEVICE_ID_JOYPAD_R},{"X",RETRO_DEVICE_ID_JOYPAD_Y},{"Y",RETRO_DEVICE_ID_JOYPAD_X},
        {"Z",RETRO_DEVICE_ID_JOYPAD_L},{"L",RETRO_DEVICE_ID_JOYPAD_L2},{"R",RETRO_DEVICE_ID_JOYPAD_R2},
        {"START",RETRO_DEVICE_ID_JOYPAD_START}};
    unsigned mask=0;char copy[128];snprintf(copy,sizeof(copy),"%s",text);
    for(char *t=strtok(copy,"+");t;t=strtok(NULL,"+")){
        if(!strcmp(t,"NONE"))continue;
        unsigned i=0;for(;i<sizeof(map)/sizeof(map[0]);i++)if(!strcmp(t,map[i].name)){mask|=1u<<map[i].id;break;}
        if(i==sizeof(map)/sizeof(map[0])){fprintf(stderr,"unknown button %s\n",t);exit(2);}
    }
    return mask;
}
static uint32_t symbol(const char *name){
    for(unsigned i=0;i<sym_count;i++)if(!strcmp(sym_names[i],name))return sym_values[i];
    fprintf(stderr,"unknown symbol %s\n",name);exit(2);
}
static uint32_t word(uint32_t address){
    /* High work RAM (0x06000000) follows low work RAM (0x00200000) in Beetle's system RAM. */
    const uint8_t *ram=mem_data(RETRO_MEMORY_SYSTEM_RAM);size_t at=((address&0x0ff00000)==0x00200000?0:0x100000)+(address&0xfffff);
    if(!ram || at+4>mem_size(RETRO_MEMORY_SYSTEM_RAM)){fprintf(stderr,"bad address %08x\n",address);exit(2);}
    /* Beetle exposes native-endian 16-bit words; Saturn bytes are big endian. */
    uint16_t high,low;memcpy(&high,ram+at,2);memcpy(&low,ram+at+2,2);
    return (uint32_t)high<<16|low;
}
static void step(void){core_run();frame++;}
static uint32_t magic_of(const char *text){
    if(strlen(text)!=4){fprintf(stderr,"magic must be 4 characters\n");exit(2);}
    return (uint32_t)text[0]<<24|(uint32_t)text[1]<<16|(uint32_t)text[2]<<8|(uint8_t)text[3];
}
static void screenshot(const char *name){
    if(!last_video){fprintf(stderr,"no video\n");exit(2);}
    char path[4096];snprintf(path,sizeof(path),"%s/%s.ppm",output_dir,name);
    FILE *file=fopen(path,"wb");if(!file){perror(path);exit(2);}
    fprintf(file,"P6\n%u %u\n255\n",last_width,last_height);
    uint64_t hash=1469598103934665603ULL;
    for(unsigned y=0;y<last_height;y++)for(unsigned x=0;x<last_width;x++){
        const uint8_t *p=(const uint8_t *)last_video+y*last_pitch;unsigned r,g,b;
        if(pixel_format==RETRO_PIXEL_FORMAT_XRGB8888){uint32_t v;memcpy(&v,p+x*4,4);r=(v>>16)&255;g=(v>>8)&255;b=v&255;}
        else{uint16_t v;memcpy(&v,p+x*2,2);
            if(pixel_format==RETRO_PIXEL_FORMAT_RGB565){r=(v>>11)*255/31;g=((v>>5)&63)*255/63;}
            else{r=((v>>10)&31)*255/31;g=((v>>5)&31)*255/31;}
            b=(v&31)*255/31;}
        unsigned char rgb[]={r,g,b};fwrite(rgb,1,3,file);
        for(unsigned i=0;i<3;i++){hash^=rgb[i];hash*=1099511628211ULL;}
    }
    fclose(file);printf("frame=%u shot %s %ux%u hash=%016llx\n",frame,name,last_width,last_height,(unsigned long long)hash);
}
static uint8_t *backup_bytes;static size_t backup_size;
static void backup_flush(void){
    const char *path=getenv("SCD_BACKUP_OUTPUT");if(!path || !backup_bytes)return;
    FILE *f=fopen(path,"wb");if(!f || fwrite(backup_bytes,1,backup_size,f)!=backup_size){perror(path);_Exit(2);}
    fclose(f);
}
static unsigned backup_retry_used;
static int backup_fixture_read(const char *path,uint8_t *bytes){
    FILE *f=fopen(path,"rb");if(!f){perror(path);return 2;}
    size_t count=fread(bytes,1,32768,f);int extra=fgetc(f);
    int bad=count!=32768 || extra!=EOF || ferror(f);
    if(fclose(f))bad=1;
    if(bad){fprintf(stderr,"Expected exact 32 KiB backup fixture: %s\n",path);return 2;}
    return 0;
}
static unsigned backup_observed_byte(uint32_t address){
    return (word(address&~3u)>>(8*(3-(address&3u))))&255u;
}
static int backup_retry_fixture(void){
    const char *source=getenv("SCD_BACKUP_INPUT"),*retry=getenv("SCD_BACKUP_RETRY_INPUT");
    if(backup_retry_used || !source || !*source || !retry || !*retry ||
       !backup_bytes || backup_size!=32768 ||
       mem_data(RETRO_MEMORY_SAVE_RAM)!=backup_bytes || mem_size(RETRO_MEMORY_SAVE_RAM)!=32768){
        fputs("Backup retry fixture is unavailable or already used\n",stderr);return 2;
    }
    /* No work-RAM writes: observe the failed same-result final-initials boundary. */
    uint32_t menu=symbol("tamenu");
    if(word(symbol("trace"))!=magic_of("FEND") ||
       backup_observed_byte(symbol("tastate"))!=2 ||
       backup_observed_byte(menu+1)!=5 || backup_observed_byte(menu+5)!=2){
        fputs("Backup retry requires failed TA final initials\n",stderr);return 2;
    }
    uint8_t *images=malloc(65536);if(!images){fputs("Backup fixture allocation failed\n",stderr);return 2;}
    if(backup_fixture_read(source,images) || backup_fixture_read(retry,images+32768)){
        free(images);return 2;
    }
    if(memcmp(backup_bytes,images,32768)){
        free(images);fputs("Failed TA commit changed the original backup\n",stderr);return 2;
    }
    int changed=memcmp(images,images+32768,32768)!=0;
    backup_retry_used=1;memcpy(backup_bytes,images+32768,32768);free(images);
    if(printf("frame=%u backup_retry bytes=32768 before_unchanged=1 changed=%d\n",frame,changed)<0)return 2;
    return 0;
}
/* One route: SCD_* buttons per simulation update (tests/routes format, one per line). */
static unsigned route_buttons[40000],route_count;
static int run_route(const char *path,unsigned max){
    FILE *f=fopen(path,"r");if(!f){perror(path);return 2;}
    route_count=0;unsigned v;while(route_count<40000 && fscanf(f,"%u",&v)==1)route_buttons[route_count++]=v;
    fclose(f);
    uint32_t trace=symbol("trace");unsigned seq=0,sim=0,mismatch=0,started=0,start=frame;
    for(;frame-start<max;){
        uint32_t magic=word(trace);
        if(magic==0x53434432){
            started=1;
            unsigned latest=word(trace+4);
            while(seq<latest){
                seq++;uint32_t r=trace+(24+(seq%64)*21)*4;
                if(word(r)!=seq)continue;
                sim=word(r+36);
                if(getenv("SCD_ROUTE_DEBUG"))printf("route record seq=%u sim=%u frame=%u actual=%u\n",seq,sim,frame,word(r+8));
                if(sim>=1 && sim<=route_count && word(r+8)!=route_buttons[sim-1]){if(getenv("SCD_ROUTE_DEBUG") && mismatch<3)printf("route mismatch sim=%u frame=%u actual=%u expected=%u\n",sim,frame,word(r+8),route_buttons[sim-1]);mismatch++;}
            }
            /* A pad state set now is accepted by update sim+2 (SMPC poll plus libretro
               input latency; measured: 1300/1300 records match at this offset). */
            unsigned next=sim+1<route_count?route_buttons[sim+1]:0;
            button_mask=(next&1?1u<<RETRO_DEVICE_ID_JOYPAD_UP:0)|(next&2?1u<<RETRO_DEVICE_ID_JOYPAD_DOWN:0)|
                (next&4?1u<<RETRO_DEVICE_ID_JOYPAD_LEFT:0)|(next&8?1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT:0)|
                (next&16?1u<<RETRO_DEVICE_ID_JOYPAD_B:0);
        }else{
            button_mask=0;
            if(started)break;
        }
        step();
    }
    button_mask=0;
    printf("frame=%u route %s updates=%u of %u mismatches=%u ended=%u\n",frame,path,sim,route_count,mismatch,started && word(trace)!=0x53434432);
    return 0;
}
int main(int argc,char **argv){
    if(argc!=6){fprintf(stderr,"usage: core cue system output script\n");return 2;}
    system_dir=argv[3];output_dir=argv[4];
    const char *syms=getenv("SCD_SYMS");if(!syms)return 2;
    {char copy[4096];snprintf(copy,sizeof(copy),"%s",syms);
     for(char *t=strtok(copy,",");t && sym_count<64;t=strtok(NULL,",")){
        char *eq=strchr(t,'=');if(!eq)return 2;*eq=0;
        snprintf(sym_names[sym_count],48,"%s",t);sym_values[sym_count++]=(uint32_t)strtoul(eq+1,NULL,16);
     }}
    void *core=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);if(!core){fprintf(stderr,"%s\n",dlerror());return 2;}
#define LOAD(name) __typeof__(&name) p_##name=(__typeof__(&name))dlsym(core,#name);if(!p_##name)abort()
    LOAD(retro_set_environment);LOAD(retro_set_video_refresh);LOAD(retro_set_audio_sample);
    LOAD(retro_set_audio_sample_batch);LOAD(retro_set_input_poll);LOAD(retro_set_input_state);
    LOAD(retro_get_memory_data);LOAD(retro_get_memory_size);
    LOAD(retro_init);LOAD(retro_load_game);LOAD(retro_run);LOAD(retro_unload_game);LOAD(retro_deinit);
    p_retro_set_environment(environment);p_retro_set_video_refresh(video);
    p_retro_set_audio_sample(audio);p_retro_set_audio_sample_batch(audio_batch);
    p_retro_set_input_poll(input_poll);p_retro_set_input_state(input_state);p_retro_init();
    struct retro_game_info game={.path=argv[2]};
    if(!p_retro_load_game(&game)){fprintf(stderr,"Game load failed\n");return 2;}
    if(staff_raw_diagnostic()){
        _Static_assert(sizeof(bool)==1,"core opposite_directions bool layout");
        const void *opposite=dlsym(core,"opposite_directions");
        uint8_t opposite_value=2;
        if(opposite)memcpy(&opposite_value,opposite,sizeof(opposite_value));
        printf("staff_raw_option phase=after_load frame=%u requested=enabled queries=%u enabled=%u global_present=%u global_value=%u\n",frame,staff_opposite_queries,staff_opposite_enabled,(unsigned)(opposite!=NULL),(unsigned)opposite_value);
        fflush(stdout);
        if(!staff_opposite_queries || staff_opposite_enabled!=staff_opposite_queries){
            fprintf(stderr,"staff_raw_option unsupported: no confirmed enabled query; no game frames run\n");
            p_retro_unload_game();p_retro_deinit();return 4;
        }
        if(!opposite || opposite_value!=1){
            fprintf(stderr,"staff_raw_option unknown: enabled response did not establish the core bool; no game frames run\n");
            p_retro_unload_game();p_retro_deinit();return 5;
        }
    }
    mem_data=p_retro_get_memory_data;mem_size=p_retro_get_memory_size;core_run=p_retro_run;
    backup_bytes=mem_data(RETRO_MEMORY_SAVE_RAM);backup_size=mem_size(RETRO_MEMORY_SAVE_RAM);
    if(getenv("SCD_BACKUP_INPUT") || getenv("SCD_BACKUP_OUTPUT")){
        if(!backup_bytes || backup_size!=32768){fprintf(stderr,"Expected 32 KiB internal backup RAM\n");return 2;}
        const char *path=getenv("SCD_BACKUP_INPUT");
        if(path){FILE *f=fopen(path,"rb");if(!f || fread(backup_bytes,1,backup_size,f)!=backup_size){perror(path);return 2;}fclose(f);}
        atexit(backup_flush);
    }
    FILE *script=fopen(argv[5],"r");if(!script){perror(argv[5]);return 2;}
    char line[512];uint32_t trace=symbol("trace");
    while(fgets(line,sizeof(line),script)){
        char cmd[32]={0},a[256]={0},b[64]={0},c[64]={0},d[64]={0};
        if(line[0]=='#' || sscanf(line,"%31s %255s %63s %63s %63s",cmd,a,b,c,d)<1)continue;
        if(!strcmp(cmd,"run")){button_mask=0;for(unsigned n=strtoul(a,NULL,10);n;n--)step();}
        else if(!strcmp(cmd,"hold")){button_mask=buttons(a);for(unsigned n=strtoul(b,NULL,10);n;n--)step();button_mask=0;}
        else if(!strcmp(cmd,"tap")){button_mask=buttons(a);for(unsigned n=0;n<4;n++)step();button_mask=0;for(unsigned n=0;n<4;n++)step();}
        else if(!strcmp(cmd,"until")){
            uint32_t m=magic_of(a);unsigned max=strtoul(b,NULL,10),start=frame;button_mask=0;
            while(word(trace)!=m){if(frame-start>=max){printf("frame=%u until %s TIMEOUT magic=%08x\n",frame,a,word(trace));return 3;}step();}
            printf("frame=%u until %s after %u\n",frame,a,frame-start);
        }else if(!strcmp(cmd,"until_word")){
            uint32_t at=symbol(a)+(uint32_t)strtoul(b,NULL,0),v=(uint32_t)strtoul(c,NULL,16);unsigned max=strtoul(d,NULL,10),start=frame;button_mask=0;
            while(word(at)!=v){if(frame-start>=max){printf("frame=%u until_word %s+%s TIMEOUT value=%08x\n",frame,a,b,word(at));return 3;}step();}
            printf("frame=%u until_word %s+%s after %u\n",frame,a,b,frame-start);
        }else if(!strcmp(cmd,"bigring")){
            /* 'SSGM' in the special game mailbox: Special Stage 1 is running. */
            uint32_t world=symbol("world"),game=symbol("game");unsigned max=strtoul(a,NULL,10),start=frame,jump=0;
            while(frame-start<max && word(trace)==0x53434432 && word(game)!=0x5353474d){
                unsigned x=word(world+52),flags=word(world+64);button_mask=0;
                if(x<10585)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT;
                else if(x>=10640)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_LEFT;
                if(jump){jump--;button_mask|=1u<<RETRO_DEVICE_ID_JOYPAD_B;}
                else if(x>=10585 && x<10640 && !(flags&2))jump=20;
                step();
            }
            button_mask=0;
            printf("frame=%u bigring after %u magic=%08x special=%08x x=%u\n",frame,frame-start,word(trace),word(game),word(world+52));
        }else if(!strcmp(cmd,"route")){if(run_route(a,strtoul(b,NULL,10)))return 2;}
        else if(!strcmp(cmd,"backup_retry")){if(a[0] || backup_retry_fixture())return 2;}
        else if(!strcmp(cmd,"peek")){
            uint32_t at=symbol(b)+(uint32_t)strtoul(c,NULL,0);unsigned n=strtoul(d,NULL,10);
            printf("frame=%u peek %s",frame,a);for(unsigned i=0;i<n;i++)printf(" %08x",word(at+i*4));printf("\n");
        }else if(!strcmp(cmd,"peekb")){
            uint32_t at=symbol(b)+(uint32_t)strtoul(c,NULL,0);unsigned n=strtoul(d,NULL,10);
            printf("frame=%u peekb %s",frame,a);
            for(unsigned i=0;i<n;i++){uint32_t w=word((at+i)&~3u);printf(" %02x",(w>>(8*(3-((at+i)&3))))&255);}
            printf("\n");
        }else if(!strcmp(cmd,"shot"))screenshot(a);
        else if(!strcmp(cmd,"updatetrace")){
            uint32_t slot=symbol("slot"),fr=symbol("frame"),world=symbol("world");unsigned max=strtoul(b,NULL,10),start=frame,seq=0,rows=0;
            FILE *out=fopen(a,"w");if(!out){perror(a);return 2;}
            button_mask=0;
            while(frame-start<max && !word(slot))step();
            seq=word(trace+4);
            while(frame-start<max && word(slot)){
                unsigned latest=word(trace+4);
                while(seq<latest){seq++;uint32_t r=trace+(24+(seq%64)*21)*4;
                    if(word(r)==seq)fprintf(out,"%u %u %u %u %d %d\n",seq,word(r+36),word(r+8),word(fr),(int)(int16_t)word(world+52),(int)(int16_t)word(world+72));rows++;}
                step();
            }
            fclose(out);printf("frame=%u updatetrace %s rows=%u\n",frame,a,rows);
        }
        else if(!strcmp(cmd,"demotrace")){
            uint32_t slot=symbol("slot"),fr=symbol("frame"),world=symbol("world");unsigned max=strtoul(b,NULL,10),start=frame,last=~0u,rows=0;
            FILE *out=fopen(a,"w");if(!out){perror(a);return 2;}
            button_mask=0;
            while(frame-start<max && !word(slot))step();
            while(frame-start<max && word(slot)){
                unsigned n=word(fr);
                if(n!=last){fprintf(out,"%u %d %d %u\n",n,(int)(int16_t)word(world+52),(int)(int16_t)word(world+72),word(trace+4));last=n;rows++;}
                step();
            }
            fclose(out);printf("frame=%u demotrace %s rows=%u\n",frame,a,rows);
        }
        else if(!strcmp(cmd,"energy")){
            button_mask=0;audio_energy=0;for(unsigned n=strtoul(b,NULL,10);n;n--)step();
            printf("frame=%u energy %s %llu\n",frame,a,(unsigned long long)audio_energy);
        }
        else if(!strcmp(cmd,"fail_unless_magic")){
            if(word(trace)!=magic_of(a)){printf("frame=%u expected %s magic=%08x\n",frame,a,word(trace));return 3;}
        }else{fprintf(stderr,"unknown command %s\n",cmd);return 2;}
        fflush(stdout);
    }
    fclose(script);
    p_retro_unload_game();p_retro_deinit();
    return 0;
}
