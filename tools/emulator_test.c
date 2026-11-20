/* Minimal libretro test host: no UI, synthetic gamepad input, PPM evidence.
 * Compile against the pinned Beetle Saturn libretro.h. */
#include <libretro.h>
#include <dlfcn.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "act_pad_replay.h"
#include "cc_pad_replay.h"

static const char *system_dir,*output_dir;
static unsigned pixel_format,frame;
static unsigned button_mask;
static bool act3_only,bigring_only,title_only,zones_only;
static unsigned bigring_touch,bigring_tally,bigring_tally_score,bigring_game,bigring_stage,bigring_results,bigring_returned,bigring_jump;
static unsigned act3_restart_frame,act2_backup,act2_run,act2_inplace,act2_inplace_x,act2_inplace_y,act3_end,act3_boss_pos,act3_boss_status,act3_hold,act3_rest,act3_fight,act3_beaten;
static bool travel_only,eras_only,sequence_only,audio_only,diagnostic_only,world_only,act_only,act2_only,special_only,game_only,packfail_only;
static unsigned act2_turned,act2_travel,act2_arrived,act2_swing_prev,act2_base,act2_force,act2_swing,act2_entry,act2_slow,act2_jump,act2_anchor,act_warp,act_x,act_y,act_flags,act_era,act_target_era=~0u,act_route_ready=1,act2_windows[16][5],act2_window_count,act2_dash,act2_dash_timer;
static int act_vx;
static unsigned act_era_switch_base,future_block_fixture,future_block_start,future_block_checked;
static unsigned ramp_update,ramp_climb,saw_warp,saw_arrival,world_pass,ramp_seen,ramp_exit,ramp_scroll,platform_x,world_wait,checkpoint_seen,checkpoint_dead,checkpoint_return,checkpoint_x,checkpoint_time,wall_burst[2],wall_pass[2];
static unsigned monitor_wait,monitor_pass[5],monitor_music[5],monitor_return[5],monitor_route;
static uint64_t monitor_energy[5];
static unsigned act_elapsed,act_done,act_sign,act_clock,act_sections,act_sequence;
static unsigned act_pacing_count,act_pacing_blanks,act_pacing_late,act_pacing_max;
static int act_pad_record;
static unsigned level_select_frame;
static unsigned act_start=601,act_period=120,act_hold=24,act_right=2;
static unsigned finish_seen[2][7],finish_clock[2],finish_pass[2],finish_music[2],finish_stopped[2],finish_route,finish_wait;
static uint64_t finish_energy[2];
static uint64_t probe_energy[3],probe_count[3];
static unsigned sound_track,paused_fad,paused_fad_end;
static uint64_t music_energy[4],music_count[4],pause_nonzero;
static unsigned repeats[4],music_peak[4];
static char *keys[256],*values[256];
static unsigned option_count;
static const void *last_video;
static unsigned last_width,last_height;
static size_t last_pitch;
static unsigned char *pixels;
static size_t pixels_capacity;
/* RGB pixels in the displayed VDP1 buffer were drawn one video frame before
   the live VDP2 CRAM sample. Indexed priority pixels use current CRAM instead.
   Keep both observations; never select a palette by matching screenshot RGB. */
static uint16_t (*zone_read_cram)(uint32_t);
static uint16_t zone_video_cram[64],zone_sprite_cram[64];
static unsigned zone_cram_frames;
static FILE *audio_file,*preview_file;
static unsigned long audio_samples,audio_nonzero,game_audio_nonzero;
static unsigned audio_peak,raw_charge,raw_dash_speed;
static int zone_music_bucket=-1;
static uint64_t zone_music_energy[5],zone_music_samples[5];
static unsigned zone_music_peak[5];
/* Optional observed CC route waypoints select pad input only. */
static unsigned route_points(const char *name,unsigned points[16]){
    const char *text=getenv(name);unsigned count=0;
    while(text && *text){
        char *end;unsigned long x=strtoul(text,&end,10);
        if(end==text || x>16383 || count==16 || (*end && *end!=',')){
            fprintf(stderr,"Invalid CC route waypoint list: %s\n",name);exit(2);
        }
        if(x)points[count++]=(unsigned)x;
        text=*end?end+1:end;
    }
    return count;
}
static int route_near(const unsigned *points,unsigned count,unsigned x,unsigned radius){
    for(unsigned i=0;i<count;i++)if(x+radius>=points[i] && x<=points[i]+radius)return 1;
    return 0;
}
static void record_audio(int16_t l,int16_t r) {
    if(zone_music_bucket>=0){
        unsigned b=(unsigned)zone_music_bucket;int v[2]={l,r};
        for(unsigned k=0;k<2;k++){unsigned a=v[k]<0?-v[k]:v[k];zone_music_energy[b]+=(int64_t)v[k]*v[k];zone_music_samples[b]++;if(a>zone_music_peak[b])zone_music_peak[b]=a;}
    }
    if(world_only && monitor_route>=3 && monitor_route<5 && (sound_track==7 || sound_track==8))monitor_energy[monitor_route]+=(int64_t)l*l+(int64_t)r*r;
    if(world_only && sound_track==6 && finish_route<2)finish_energy[finish_route]+=(int64_t)l*l+(int64_t)r*r;
    if(diagnostic_only) {
        int bucket=frame>=1120 && frame<1160?0:frame>=1260 && frame<1280?1:frame>=1460 && frame<1500?2:-1;
        if(bucket>=0){probe_energy[bucket]+=(int64_t)l*l+(int64_t)r*r;probe_count[bucket]+=2;}
    }
    if(audio_only && frame>=900) {
        if(frame>=1260 && frame<1440)pause_nonzero+=(l!=0)+(r!=0);
        if(sound_track>=2 && sound_track<=5 && !(frame>=1170 && frame<1570)) {
            unsigned i=sound_track-2;int v[2]={l,r};
            for(unsigned j=0;j<2;j++) {unsigned a=v[j]<0?-v[j]:v[j];music_energy[i]+=(int64_t)v[j]*v[j];music_count[i]++;if(a>music_peak[i])music_peak[i]=a;}
        }
    }
    if(frame<620 || !audio_file)return;
    int16_t pair[2]={l,r};if(frame>=860 && frame<950)fwrite(pair,sizeof(int16_t),2,preview_file);fwrite(pair,sizeof(int16_t),2,audio_file);audio_samples+=2;
    for(unsigned i=0;i<2;i++){int v=pair[i];unsigned a=v<0?-v:v;if(a>audio_peak)audio_peak=a;if(a){audio_nonzero++;if(frame>=2000)game_audio_nonzero++;}}
}

static void logger(enum retro_log_level level,const char *fmt,...) {
    (void)level;
    va_list args;va_start(args,fmt);vfprintf(stderr,fmt,args);va_end(args);
}
static bool environment(unsigned command,void *data) {
    switch(command) {
    case RETRO_ENVIRONMENT_GET_SYSTEM_DIRECTORY:
    case RETRO_ENVIRONMENT_GET_SAVE_DIRECTORY:
        *(const char **)data=system_dir;return true;
    case RETRO_ENVIRONMENT_GET_LOG_INTERFACE:
        ((struct retro_log_callback *)data)->log=logger;return true;
    case RETRO_ENVIRONMENT_SET_PIXEL_FORMAT:
        pixel_format=*(unsigned *)data;return pixel_format<=2;
    case RETRO_ENVIRONMENT_GET_CAN_DUPE:
        *(bool *)data=true;return true;
    case RETRO_ENVIRONMENT_GET_VARIABLE_UPDATE:
        *(bool *)data=false;return true;
    case RETRO_ENVIRONMENT_GET_CORE_OPTIONS_VERSION:
        *(unsigned *)data=0;return true;
    case RETRO_ENVIRONMENT_SET_VARIABLES: {
        const struct retro_variable *v=data;
        for(;v->key && option_count<256;v++) {
            keys[option_count]=strdup(v->key);
            const char *start=strstr(v->value,"; ");
            values[option_count]=strdup(start?start+2:v->value);
            char *end=strchr(values[option_count],'|');if(end)*end=0;
            option_count++;
        }
        return true;
    }
    case RETRO_ENVIRONMENT_GET_VARIABLE: {
        struct retro_variable *v=data;
        if(!strcmp(v->key,"beetle_saturn_region")) {v->value="North America";return true;}
        if(!strcmp(v->key,"beetle_saturn_cart")) {v->value="None";return true;}
        if(strstr(v->key,"jit")) {v->value="disabled";return true;}
        for(unsigned i=0;i<option_count;i++) if(!strcmp(v->key,keys[i])) {v->value=values[i];return true;}
        v->value=NULL;return false;
    }
    case RETRO_ENVIRONMENT_SET_INPUT_DESCRIPTORS:
    case RETRO_ENVIRONMENT_SET_CONTROLLER_INFO:
    case RETRO_ENVIRONMENT_SET_SUPPORT_NO_GAME:
    case RETRO_ENVIRONMENT_SET_PERFORMANCE_LEVEL:
    case RETRO_ENVIRONMENT_SET_GEOMETRY:
    case RETRO_ENVIRONMENT_SET_SYSTEM_AV_INFO:return true;
    default:return false;
    }
}
static void video(const void *data,unsigned width,unsigned height,size_t pitch) {
    if(!data || data==RETRO_HW_FRAME_BUFFER_VALID)return;
    if(zone_read_cram){
        memcpy(zone_sprite_cram,zone_video_cram,sizeof(zone_sprite_cram));
        for(unsigned c=0;c<64;c++)zone_video_cram[c]=zone_read_cram(0x100000+c*2);
        zone_cram_frames++;
    }
    if(pitch*height>pixels_capacity) {pixels_capacity=pitch*height;pixels=realloc(pixels,pixels_capacity);if(!pixels)abort();}
    memcpy(pixels,data,pitch*height);
    last_video=pixels;last_width=width;last_height=height;last_pitch=pitch;
}
static void audio(int16_t l,int16_t r) {record_audio(l,r);}
static size_t audio_batch(const int16_t *data,size_t frames) {for(size_t i=0;i<frames;i++)record_audio(data[i*2],data[i*2+1]);return frames;}
static void input_poll(void) {}
static int16_t input_state(unsigned port,unsigned device,unsigned index,unsigned id) {
    (void)index;
    if(port || device!=RETRO_DEVICE_JOYPAD || id>=16)return 0;
    return (button_mask>>id)&1;
}
/* Special stage game routes: run-length pad scripts from tools/special_retail.py.
   SCD_SPECIAL_ROUTE_NAMES lists them (default "timeout,win"); a name ending in
   -ss<n> selects stage n in the floor inspection (X) before B starts it. */
enum {GAME_ROUTES=9};
static unsigned game_pads[GAME_ROUTES][2][16000],game_route_count,game_route_stage[GAME_ROUTES],game_route_win[GAME_ROUTES],game_default_routes;
static void game_load_pads(const char *folder){
    static char names[512];const char *list=getenv("SCD_SPECIAL_ROUTE_NAMES");
    game_default_routes=!list;snprintf(names,sizeof(names),"%s",list?list:"timeout,win");
    char *routes[GAME_ROUTES];game_route_count=0;
    for(char *name=strtok(names,",");name && game_route_count<GAME_ROUTES;name=strtok(NULL,",")){
        const char *stage=strstr(name,"-ss");
        game_route_stage[game_route_count]=stage?(unsigned)atoi(stage+3):1;game_route_win[game_route_count]=!strncmp(name,"win",3);
        routes[game_route_count++]=name;
    }
    if(game_route_count<1){fprintf(stderr,"no special game routes\n");exit(2);}
    for(unsigned r=0;r<game_route_count;r++){
        char path[4096];snprintf(path,sizeof(path),"%s/%s.pad",folder,routes[r]);
        FILE *file=fopen(path,"r");if(!file){perror(path);exit(2);}
        char phase[16];unsigned v,pad,last[2]={0,0},value[2]={0,0};
        while(fscanf(file,"%15s %u %u",phase,&v,&pad)==3){
            unsigned results=!strcmp(phase,"results");if(v>=16000){fprintf(stderr,"pad script too long\n");exit(2);}
            for(unsigned i=last[results];i<v;i++)game_pads[r][results][i]=value[results];
            last[results]=v;value[results]=pad;
        }
        for(unsigned p=0;p<2;p++)for(unsigned i=last[p];i<16000;i++)game_pads[r][p][i]=value[p];
        fclose(file);
    }
}
static unsigned game_retro_mask(unsigned md){
    /* Mega Drive B is Saturn B (libretro A); Start and the D-pad map directly. */
    /* Mega Drive A and C are Saturn A and C (libretro B and R). */
    return (md&1?1u<<RETRO_DEVICE_ID_JOYPAD_UP:0)|(md&2?1u<<RETRO_DEVICE_ID_JOYPAD_DOWN:0)|(md&4?1u<<RETRO_DEVICE_ID_JOYPAD_LEFT:0)|
        (md&8?1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT:0)|(md&16?1u<<RETRO_DEVICE_ID_JOYPAD_A:0)|(md&32?1u<<RETRO_DEVICE_ID_JOYPAD_R:0)|
        (md&64?1u<<RETRO_DEVICE_ID_JOYPAD_B:0)|(md&128?1u<<RETRO_DEVICE_ID_JOYPAD_START:0);
}
/* FNV-1a over Saturn big-endian bytes at a low or high Work RAM address; 0 when unmapped. */
static uint32_t game_hash(const uint8_t *ram,size_t size,uint32_t address,unsigned bytes){
    address&=0x0fffffff;
    size_t base=(address&0x0ff00000)==0x00200000?0:(address&0x0ff00000)==0x06000000?0x100000:size;
    if(base+(address&0xfffff)+bytes>size || base==size)return 0;
    uint32_t h=2166136261u;
    for(unsigned i=0;i<bytes;i++){
        size_t o=base+(address&0xfffff)+i;uint16_t w;memcpy(&w,ram+(o&~(size_t)1),2);
        h=(h^(o&1?w&255:w>>8))*16777619u;
    }
    return h;
}
/* zlib CRC-32 over Saturn big-endian bytes at a low or high Work RAM address; 0 when unmapped. */
static uint32_t game_crc32(const uint8_t *ram,size_t size,uint32_t address,unsigned bytes){
    static uint32_t table[256];
    if(!table[1])for(unsigned i=0;i<256;i++){uint32_t c=i;for(unsigned k=0;k<8;k++)c=c&1?0xedb88320u^(c>>1):c>>1;table[i]=c;}
    address&=0x0fffffff;
    size_t base=(address&0x0ff00000)==0x00200000?0:(address&0x0ff00000)==0x06000000?0x100000:size;
    if(base==size || base+(address&0xfffff)+bytes>size)return 0;
    uint32_t c=0xffffffffu;
    for(unsigned i=0;i<bytes;i++){
        size_t o=base+(address&0xfffff)+i;uint16_t w;memcpy(&w,ram+(o&~(size_t)1),2);
        c=table[(c^(o&1?w&255:w>>8))&255]^(c>>8);
    }
    return ~c;
}
/* CRC-32 of the Mega Drive picture as Genesis Plus GX RGB565 words (little endian):
   each Saturn channel is one of eight original levels (c*31/7). */
static FILE *title_pixels;
static uint32_t game_crc(unsigned x0,unsigned width,unsigned y0,unsigned y1,bool *valid){
    static uint32_t table[256];
    if(!table[1])for(unsigned i=0;i<256;i++){uint32_t c=i;for(unsigned k=0;k<8;k++)c=c&1?0xedb88320u^(c>>1):c>>1;table[i]=c;}
    static const int level[32]={0,-1,-1,-1,1,-1,-1,-1,2,-1,-1,-1,-1,3,-1,-1,-1,4,-1,-1,-1,-1,5,-1,-1,-1,6,-1,-1,-1,-1,7};
    uint32_t crc=0xffffffffu;*valid=true;
    for(unsigned y=y0;y<y1;y++)for(unsigned x=x0;x<x0+width;x++){
        const uint8_t *p=(const uint8_t *)last_video+y*last_pitch;unsigned r,g,b;
        if(pixel_format==RETRO_PIXEL_FORMAT_XRGB8888){uint32_t value;memcpy(&value,p+x*4,4);r=(value>>19)&31;g=(value>>11)&31;b=(value>>3)&31;}
        else{uint16_t value;memcpy(&value,p+x*2,2);r=pixel_format==RETRO_PIXEL_FORMAT_RGB565?value>>11:(value>>10)&31;g=pixel_format==RETRO_PIXEL_FORMAT_RGB565?((value>>5)&63)>>1:(value>>5)&31;b=value&31;}
        int lr=level[r],lg=level[g],lb=level[b];
        if(lr<0 || lg<0 || lb<0){*valid=false;lr=lg=lb=0;}
        unsigned r4=lr*2,g4=lg*2,b4=lb*2,word=r4<<12|(r4>>3)<<11|g4<<7|(g4>>2)<<5|b4<<1|b4>>3;
        uint8_t bytes[2]={word&255,word>>8};
        if(title_pixels)fwrite(bytes,1,2,title_pixels);
        for(unsigned i=0;i<2;i++)crc=table[(crc^bytes[i])&255]^(crc>>8);
    }
    return ~crc;
}
/* World mailbox [50] (Sonic's screen position, src/main.c) for the capture log;
   set when SCD_WORLD_MAILBOX is given. */
static void *(*shot_data)(unsigned);static size_t (*shot_size)(unsigned);static size_t shot_box,shot_trace;
/* Sonic's screen position at the latest and the previous gameplay update (the
   trace sequence advanced): the picture on screen is drawn from the previous. */
static uint32_t shot_seq,shot_now,shot_prev;
static void (*shot_run)(void);
/* QA-only Sonic texture check (QA_SONIC_VIEW = address of scd_sonic_view_mailbox,
   QA_SONIC_FRAMES = the SONFRM pack file): after each frame whose texture-miss
   counter ([14]) advanced, the slot at [9] in VDP1 VRAM must hold exactly the
   1024 texture words src/sonic_frames.c decodes for mapping [3] (the upload,
   CPU copy or DMA, reached VRAM before the frame ended). */
#include "../src/sonic_frames.c"
static size_t tex_box;static uint32_t tex_misses;static scd_sonic_frames tex_frames;static int tex_ready;
static unsigned long tex_checked,tex_bad;static uint16_t (*tex_vdp1)(uint32_t);
static void tex_report(void){if(tex_ready)printf("Sonic texture check: misses=%lu mismatches=%lu\n",tex_checked,tex_bad);}
static void tex_track(void){
    if(!tex_ready)return;
    const uint8_t *ram=shot_data(RETRO_MEMORY_SYSTEM_RAM);size_t size=shot_size(RETRO_MEMORY_SYSTEM_RAM);
    if(!ram || tex_box+72>size)return;
    uint32_t w[16];for(unsigned i=0;i<16;i++){uint16_t h,l;memcpy(&h,ram+tex_box+i*4,2);memcpy(&l,ram+tex_box+i*4+2,2);w[i]=((uint32_t)h<<16)|l;}
    if(w[0]!=0x534F4E56 || w[14]==tex_misses)return;
    tex_misses=w[14];
    uint16_t want[1040];if(scd_sonic_frames_decode(&tex_frames,w[3],want))return;
    unsigned bad=0;for(unsigned i=0;i<1024;i++)if(tex_vdp1(w[9]+i*2)!=want[i])bad++;
    tex_checked++;
    if(bad){if(tex_bad<5)fprintf(stderr,"Sonic texture mismatch: frame %u mapping %u slot %05x words %u\n",frame,w[3],w[9],bad);tex_bad++;}
}
static void shot_track(void);
static void shot_checked_run(void){shot_run();shot_track();tex_track();}
static void shot_track(void){
    const uint8_t *ram=shot_data(RETRO_MEMORY_SYSTEM_RAM);size_t size=shot_size(RETRO_MEMORY_SYSTEM_RAM);
    if(!ram || shot_box+204>size || !shot_trace || shot_trace+8>size)return;
    uint32_t seq,now;
    {uint16_t h,l;memcpy(&h,ram+shot_trace+4,2);memcpy(&l,ram+shot_trace+6,2);seq=((uint32_t)h<<16)|l;}
    {uint16_t h,l;memcpy(&h,ram+shot_box+200,2);memcpy(&l,ram+shot_box+202,2);now=((uint32_t)h<<16)|l;}
    if(seq!=shot_seq){shot_seq=seq;shot_prev=shot_now;shot_now=now;}
}
static uint64_t shot_hash;
/* One pixel of the last frame as 8-bit RGB (screenshot()'s conversion). */
static void frame_rgb(unsigned x,unsigned y,unsigned char rgb[3]){
    const uint8_t *p=(const uint8_t *)last_video+y*last_pitch;unsigned r,g,b;
    if(pixel_format==RETRO_PIXEL_FORMAT_XRGB8888){uint32_t value;memcpy(&value,p+x*4,4);r=(value>>16)&255;g=(value>>8)&255;b=value&255;}
    else{
        uint16_t value;memcpy(&value,p+x*2,2);
        if(pixel_format==RETRO_PIXEL_FORMAT_RGB565){r=(value>>11)*255/31;g=((value>>5)&63)*255/63;}
        else{r=((value>>10)&31)*255/31;g=((value>>5)&31)*255/31;}
        b=(value&31)*255/31;
    }
    rgb[0]=(unsigned char)r;rgb[1]=(unsigned char)g;rgb[2]=(unsigned char)b;
}
static void screenshot(const char *name) {
    if(!last_video) {fprintf(stderr,"no video at frame %u\n",frame);exit(2);}
    char path[4096];snprintf(path,sizeof(path),"%s/%s.ppm",output_dir,name);
    FILE *file=fopen(path,"wb");if(!file){perror(path);exit(2);}
    fprintf(file,"P6\n%u %u\n255\n",last_width,last_height);
    uint64_t hash=1469598103934665603ULL;
    for(unsigned y=0;y<last_height;y++)for(unsigned x=0;x<last_width;x++) {
        const uint8_t *p=(const uint8_t *)last_video+y*last_pitch;
        unsigned r,g,b;
        if(pixel_format==RETRO_PIXEL_FORMAT_XRGB8888) {
            uint32_t value;memcpy(&value,p+x*4,4);r=(value>>16)&255;g=(value>>8)&255;b=value&255;
        } else {
            uint16_t value;memcpy(&value,p+x*2,2);
            if(pixel_format==RETRO_PIXEL_FORMAT_RGB565) {r=(value>>11)*255/31;g=((value>>5)&63)*255/63;}
            else {r=((value>>10)&31)*255/31;g=((value>>5)&31)*255/31;}
            b=(value&31)*255/31;
        }
        unsigned char rgb[]={r,g,b};fwrite(rgb,1,3,file);
        for(unsigned i=0;i<3;i++){hash^=rgb[i];hash*=1099511628211ULL;}
    }
    fclose(file);shot_hash=hash;printf("%s frame=%u %ux%u hash=%016llx\n",name,frame,last_width,last_height,(unsigned long long)hash);
    if(shot_box){
        const uint8_t *ram=shot_data(RETRO_MEMORY_SYSTEM_RAM);
        if(ram && shot_box+204<=shot_size(RETRO_MEMORY_SYSTEM_RAM)){
            const uint8_t *w=ram+shot_box+200;uint16_t hi,lo;memcpy(&hi,w,2);memcpy(&lo,w+2,2);
            printf("Screen Sonic: %s screen=%d,%d drawn=%d,%d\n",name,(int16_t)hi,(int16_t)lo,(int16_t)(shot_prev>>16),(int16_t)shot_prev);
        }
    }
    fflush(stdout);
}

static uint32_t ram_word(const uint8_t *ram,size_t offset) {
    /* Beetle exposes native-endian 16-bit words; Saturn bytes are big endian. */
    uint16_t high,low;memcpy(&high,ram+offset,2);memcpy(&low,ram+offset+2,2);
    return ((uint32_t)high<<16)|low;
}
static void ram_put_word(uint8_t *ram,size_t offset,uint32_t value){
    uint16_t high=value>>16,low=value;memcpy(ram+offset,&high,2);memcpy(ram+offset+2,&low,2);
}
#include "save_replay.h"
/* A fixture can publish its first sprite while TV display-enable is still
   crossing the loading boundary. Allow exactly one additional field only
   for an entirely black initial picture; preserve the original snapshot
   and all exact source-pixel assertions. This is not a steady-state lag. */
static int video_black(void){
    if(!last_video)return 0;
    for(unsigned y=0;y<last_height;y++){
        const uint8_t *row=(const uint8_t *)last_video+y*last_pitch;
        for(unsigned x=0;x<last_width;x++){
            if(pixel_format==RETRO_PIXEL_FORMAT_XRGB8888){uint32_t v;memcpy(&v,row+x*4,4);if(v&0xffffff)return 0;}
            else {uint16_t v;memcpy(&v,row+x*2,2);if(v&(pixel_format==RETRO_PIXEL_FORMAT_RGB565?0xffff:0x7fff))return 0;}
        }
    }
    return 1;
}
static unsigned boot_wait,world_stalled,world_last_phase,world_last_iteration;
static unsigned collapse_seen[4],collapse_pass[4],collapse_intact[4],collapse_wait;
static unsigned tunnel_seen[4],tunnel_pass[4],tunnel_exit[4],tunnel_wait;
static int tag_camera[2][3][2];
static unsigned amy_wait,amy_hold,amy_jump,amy_due[3],amy_snapshot[3][76];
static unsigned projector_wait,projector_pass[4],projector_due[6],projector_done,projector_hit;
static unsigned projector_snapshot[6][76],projector_sonic[6][18];
static unsigned scenery_wait,scenery_pass[11],scenery_due[11],scenery_xy[11],scenery_player[11];
static unsigned scenery_sonic[11][18];
static unsigned door_wait,door_frames[5],door_due[5][2],door_xy[5][2],door_action[5];
static unsigned door_enable_wait[5],scenery_enable_wait[11];
static unsigned disc_seen[3],disc_exit[3],disc_pass[3],disc_poses[3],disc_wait,disc_pose_due[3][6];
/* Route areas "x0-x1/y0-y1[d|l|w|r|j|T|R|D|p],..." (see main). */
static void load_route(const char *p){
    unsigned a,b,c,d;int used;act2_window_count=0;
    while(p && act2_window_count<16 && sscanf(p,"%u-%u/%u-%u%n",&a,&b,&c,&d,&used)==4){unsigned *w=act2_windows[act2_window_count++];w[0]=a;w[1]=b;w[2]=c;w[3]=d;p+=used;w[4]=*p=='d'?1:*p=='l'?2:*p=='w'?3:*p=='r'?4:*p=='j'?5:*p=='T'?6:*p=='R'?7:*p=='D'?8:*p=='p'?9:0;if(w[4])p++;if(*p==',')p++;}
}
#include "journey_replay.h"
/* SCD_ZONES_CPU: print both SH-2s' PC, PR, R15, SR and R0-R14 from a save state
   (Mednafen chunks "SH2-M"/"SH2-S": variables "R", "PC", "CtrlRegs", "SysRegs").
   The wram.bin it writes is RETRO_MEMORY_SYSTEM_RAM as Beetle exposes it: low
   work RAM then high work RAM (0x06000000 at offset 0x100000), in native-endian
   16-bit words, so Saturn byte A sits at offset A^1 on a little-endian host. */
static const uint8_t *state_var(const uint8_t *state,size_t bytes,const char *chunk,const char *name,uint32_t *size){
    for(size_t at=0;at+36<bytes;at++){
        if(memcmp(state+at,chunk,strlen(chunk)+1))continue;
        uint32_t length;memcpy(&length,state+at+32,4);
        const uint8_t *p=state+at+36,*end=p+length;
        if(end>state+bytes)return NULL;
        while(p<end){
            unsigned n=*p;uint32_t s;memcpy(&s,p+1+n,4);
            if(n==strlen(name) && !memcmp(p+1,name,n)){*size=s;return p+5+n;}
            p+=5+n+s;
        }
    }
    return NULL;
}
static void cpu_dump(const char *label,const uint8_t *state,size_t bytes){
    const char *chunks[]={"SH2-M","SH2-S"};
    for(unsigned c=0;c<2;c++){
        uint32_t s;const uint8_t *r=state_var(state,bytes,chunks[c],"R",&s),*pc=state_var(state,bytes,chunks[c],"PC",&s),
            *ctrl=state_var(state,bytes,chunks[c],"CtrlRegs",&s),*sys=state_var(state,bytes,chunks[c],"SysRegs",&s);
        if(!r || !pc || !ctrl || !sys){printf("%s %s: registers not found\n",label,chunks[c]);continue;}
        uint32_t R[16],PC,CR[3],SR3[3];memcpy(R,r,64);memcpy(&PC,pc,4);memcpy(CR,ctrl,12);memcpy(SR3,sys,12);
        printf("%s %s PC=%08x PR=%08x SR=%08x VBR=%08x R15=%08x",label,chunks[c],PC,SR3[2],CR[0],CR[2],R[15]);
        for(unsigned i=0;i<15;i++)printf(" R%u=%08x",i,R[i]);
        printf("\n");
    }
    fflush(stdout);
}
/* QA-only NBG0 map check (QA_NBG0_MAPS = address of main.c's WRAM maps[0],
   SCD_WORLD_MAILBOX for the camera): after every emulated frame on which the
   camera tile position (world - screen position of Sonic, mailbox[13]/[18] and
   [50]) is the same as on the previous frame, the 42x30 visible cells of the
   NBG0 pattern-name table in VDP2 VRAM (0x10000, 64x64 ring of 32-bit PNDs)
   must equal WRAM maps[0]: row uploads (main.c foreground_rows) left no stale
   row, and block writes reached VRAM. Counts print at exit. */
/* VDP DMA guard (src/vdp_dma_guard.h): every run fails if the game ever had to
   copy directly because Yaul's 16-entry DMA queue was full, and reports the
   peak queue count. The address comes from the linked ELF (SCD_ELF overrides). */
static void (*dma_run)(void);
static void *(*dma_data)(unsigned);static size_t (*dma_size)(unsigned);
static size_t dma_stats,dma_trace,dma_table_state;static uint32_t dma_peak;
static void dma_report(void){if(dma_stats)printf("VDP DMA queue: peak=%u direct=0\n",dma_peak);}
static void dma_checked_run(void){
    dma_run();
    const uint8_t *ram=dma_data(RETRO_MEMORY_SYSTEM_RAM);size_t size=dma_size(RETRO_MEMORY_SYSTEM_RAM);
    if(!ram || dma_stats+8>size)return;
    uint32_t peak=ram_word(ram,dma_stats),direct=ram_word(ram,dma_stats+4);
    /* Before the program runs, RAM holds zeros, then the unloaded image. Arm once the trace
       mailbox (argv[5]) carries a program magic (four upper-case letters: TITL, LSEL,
       SCD2, ...), which the program writes only after it cleared its BSS. */
    static int armed;
    if(!armed){
        uint32_t magic=dma_trace && dma_trace+4<=size?ram_word(ram,dma_trace):0;int letters=1;
        for(unsigned k=0;k<4;k++){unsigned c=magic>>(8*k)&255;letters&=c>='A' && c<='Z';}
        armed=letters && peak<=16 && !direct;if(!armed)return;
    }
    if(peak>dma_peak)dma_peak=peak;
    /* SCD_DMA_LOG_MIN=N: list the frame's SCU indirect table (Yaul vdp_sync __state word 4,
       entries len,dst,src up to the END bit) whenever it holds N or more transfers. */
    if(dma_table_state && getenv("SCD_DMA_LOG_MIN")){
        static unsigned long frame;frame++;
        uint32_t table=ram_word(ram,dma_table_state+16);size_t t=0x100000+(table&0xfffff);
        if((table>>20)==0x060 && t+192<=size){
            unsigned n=0;uint32_t e[16][3];
            for(;n<16;n++){for(unsigned k=0;k<3;k++)e[n][k]=ram_word(ram,t+12*n+4*k);if(e[n][2]&0x80000000u){n++;break;}}
            static uint32_t last[16][3];static unsigned last_n;
            if(n>=strtoul(getenv("SCD_DMA_LOG_MIN"),NULL,10) && (n!=last_n || memcmp(last,e,sizeof(e[0])*n))){
                printf("DMA table frame=%lu n=%u:",frame,n);
                for(unsigned k=0;k<n;k++)printf(" [%u %08x<-%08x]",e[k][0],e[k][1],e[k][2]&0x7fffffffu);
                printf("\n");memcpy(last,e,sizeof(e[0])*n);last_n=n;}
        }
    }
    if(direct){fprintf(stderr,"VDP DMA queue overflow: %u direct copies (queue full), peak=%u\n",direct,dma_peak);
        printf("VDP DMA queue: peak=%u direct=%u FAIL\n",dma_peak,direct);fflush(stdout);dma_stats=0;exit(2);}
}
static void dma_attach(void){
    const char *elf=getenv("SCD_ELF");char command[4200];
    snprintf(command,sizeof(command),".toolchain/bin/sh-elf-nm '%s' 2>/dev/null",elf?elf:"build/saturn/sonic-cd-saturn-prototype.elf");
    FILE *nm=popen(command,"r");if(!nm)return;
    char line[512];unsigned long address=0;
    while(fgets(line,sizeof(line),nm)){char name[400];unsigned long a;char kind;
        if(sscanf(line,"%lx %c %399s",&a,&kind,name)==3 && !strncmp(name,"_scd_vdp_dma_stats",18) && (name[18]==0 || name[18]=='.'))address=a;}
    pclose(nm);
    if(address)dma_stats=0x100000+(address&0xfffff);
    /* Yaul's vdp_sync state (a 0x18-byte __state.lto_priv.N; word 4 = the DMA indirect table). */
    snprintf(command,sizeof(command),".toolchain/bin/sh-elf-nm -S '%s' 2>/dev/null",elf?elf:"build/saturn/sonic-cd-saturn-prototype.elf");
    nm=popen(command,"r");if(!nm)return;
    while(fgets(line,sizeof(line),nm)){char name[400];unsigned long a,z;char kind;
        if(sscanf(line,"%lx %lx %c %399s",&a,&z,&kind,name)==4 && z==0x18 && !strncmp(name,"__state.lto_priv.",17))dma_table_state=0x100000+(a&0xfffff);}
    pclose(nm);
}
/* SCD_CPU_AT=f1,f2,...: at those host frames (counted from boot) print both SH-2s'
   registers, the trace mailbox's first 4 words and write wram-<frame>.bin (any mode). */
static void (*cpu_at_run)(void);static size_t (*cpu_at_ssize)(void);static bool (*cpu_at_ser)(void *,size_t);
static void *(*cpu_at_data)(unsigned);static size_t (*cpu_at_size)(unsigned);static size_t cpu_at_trace;static unsigned long cpu_at_frame;
static void cpu_dump(const char *label,const uint8_t *state,size_t bytes);
static void cpu_at_checked_run(void){
    cpu_at_run();cpu_at_frame++;
    const char *list=getenv("SCD_CPU_AT");char buffer[256];snprintf(buffer,sizeof(buffer),",%s,",list);char key[32];snprintf(key,sizeof(key),",%lu,",cpu_at_frame);
    if(!strstr(buffer,key))return;
    size_t bytes=cpu_at_ssize();void *state=malloc(bytes);
    char label[64];snprintf(label,sizeof(label),"CPU_AT frame=%lu",cpu_at_frame);
    if(state && cpu_at_ser(state,bytes))cpu_dump(label,state,bytes);free(state);
    const uint8_t *ram=cpu_at_data(RETRO_MEMORY_SYSTEM_RAM);size_t size=cpu_at_size(RETRO_MEMORY_SYSTEM_RAM);
    if(ram && cpu_at_trace && cpu_at_trace+16<=size)printf("%s trace=%08x %08x %08x %08x\n",label,ram_word(ram,cpu_at_trace),ram_word(ram,cpu_at_trace+4),ram_word(ram,cpu_at_trace+8),ram_word(ram,cpu_at_trace+12));
    if(ram){char path[4096];snprintf(path,sizeof(path),"%s/wram-%lu.bin",output_dir,cpu_at_frame);FILE *f=fopen(path,"wb");if(f){fwrite(ram,1,size,f);fclose(f);}}
    fflush(stdout);
}
static void (*nbg0_run)(void);
static void *(*nbg0_data)(unsigned);static size_t (*nbg0_size)(unsigned);
static uint16_t (*nbg0_vdp2)(uint32_t);
static size_t nbg0_maps,nbg0_box,nbg0_trace;static uint32_t nbg0_seq;static int nbg0_tx=-1,nbg0_ty=-1;
static unsigned long nbg0_frames,nbg0_cells,nbg0_bad,nbg0_bad_frames;
static void nbg0_report(void){if(nbg0_run)printf("NBG0 map check: frames=%lu cells=%lu mismatches=%lu bad_frames=%lu\n",nbg0_frames,nbg0_cells,nbg0_bad,nbg0_bad_frames);}
static uint32_t ram_word(const uint8_t *ram,size_t offset);
static void nbg0_checked_run(void){
    nbg0_run();
    const uint8_t *ram=nbg0_data(RETRO_MEMORY_SYSTEM_RAM);size_t size=nbg0_size(RETRO_MEMORY_SYSTEM_RAM);
    if(!ram || nbg0_box+204>size || nbg0_maps+16384>size)return;
    /* Gameplay frames only: the trace sequence (src/main.c, one per gameplay
       update) advanced. Results, tallies, loads and transitions leave VRAM
       and the mailbox camera decoupled. */
    if(nbg0_trace && nbg0_trace+8<=size){uint32_t seq=ram_word(ram,nbg0_trace+4);int moved=seq!=nbg0_seq;nbg0_seq=seq;if(!moved){nbg0_tx=-1;return;}}
    uint32_t center=ram_word(ram,nbg0_box+200);
    int cx=(int)ram_word(ram,nbg0_box+52)-(int16_t)(center>>16),cy=(int)ram_word(ram,nbg0_box+72)-(int16_t)center;
    if(!ram_word(ram,nbg0_box+52)||cx<0||cy<0||cx>16384||cy>4096){nbg0_tx=-1;return;}
    int tx=cx/8,ty=cy/8,stable=tx==nbg0_tx&&ty==nbg0_ty;nbg0_tx=tx;nbg0_ty=ty;
    if(!stable)return;
    /* Gameplay only: the stage map in WRAM is non-empty where Sonic is. */
    uint32_t any=0;
    for(int wy=ty;wy<ty+30 && !any;wy++)for(int wx=tx;wx<tx+42;wx++)any|=ram_word(ram,nbg0_maps+(((unsigned)wy&63)*64+((unsigned)wx&63))*4);
    if(!any)return;
    nbg0_frames++;unsigned bad=0;
    for(int wy=ty;wy<ty+30;wy++)for(int wx=tx;wx<tx+42;wx++){
        unsigned cell=((unsigned)wy&63)*64+((unsigned)wx&63);
        uint32_t want=ram_word(ram,nbg0_maps+cell*4);
        uint32_t got=((uint32_t)nbg0_vdp2(0x10000+cell*4)<<16)|nbg0_vdp2(0x10000+cell*4+2);
        nbg0_cells++;
        if(got!=want){if(!bad && nbg0_bad_frames<10)fprintf(stderr,"NBG0 map mismatch: frame %u camera %d,%d cell %d,%d vram %08x wram %08x\n",frame,cx,cy,wx,wy,got,want);bad++;nbg0_bad++;}
    }
    if(bad)nbg0_bad_frames++;
}
/* Optional R3 target transfer check. The independent SCR31-33 oracle checks
   the WRAM values; this checks that both 224-line tables reach VDP2 VRAM on
   the gameplay update that published them. */
static void (*r3_scroll_run)(void);
static void *(*r3_scroll_data)(unsigned);static size_t (*r3_scroll_size)(unsigned);
static uint16_t (*r3_scroll_read16)(uint32_t);
static size_t r3_scroll_box,r3_scroll_bg,r3_scroll_fg,r3_scroll_map,r3_fg_map;
static uint32_t r3_scroll_seq,r3_scroll_hash;
static unsigned long r3_scroll_calls,r3_scroll_ready,r3_scroll_zone,r3_scroll_nonzero,r3_scroll_frames,r3_scroll_words,r3_scroll_active,r3_scroll_changes,r3_scroll_bad;
static unsigned long r3_map_frames,r3_map_cells,r3_map_active,r3_map_bad;
static unsigned long r3_fg_frames,r3_fg_cells,r3_fg_active,r3_fg_bad;
static void r3_scroll_report(void){if(r3_scroll_run){printf("R3 line-scroll transfer: calls=%lu ready=%lu zone=%lu seq=%lu frames=%lu words=%lu active=%lu changes=%lu mismatches=%lu\n",r3_scroll_calls,r3_scroll_ready,r3_scroll_zone,r3_scroll_nonzero,r3_scroll_frames,r3_scroll_words,r3_scroll_active,r3_scroll_changes,r3_scroll_bad);if(r3_scroll_map)printf("R3 BG map transfer: frames=%lu cells=%lu active=%lu mismatches=%lu\n",r3_map_frames,r3_map_cells,r3_map_active,r3_map_bad);if(r3_fg_map)printf("R3 FG map transfer: frames=%lu cells=%lu active=%lu mismatches=%lu\n",r3_fg_frames,r3_fg_cells,r3_fg_active,r3_fg_bad);}}
static void r3_scroll_checked_run(void){
    r3_scroll_run();
    r3_scroll_calls++;
    const uint8_t *ram=r3_scroll_data(RETRO_MEMORY_SYSTEM_RAM);size_t size=r3_scroll_size(RETRO_MEMORY_SYSTEM_RAM);
    if(!ram || r3_scroll_box+143*4>size || r3_scroll_bg+224*4>size || r3_scroll_fg+224*4>size)return;
    r3_scroll_ready++;
    uint32_t seq=ram_word(ram,r3_scroll_box+56*4),zone=ram_word(ram,r3_scroll_box+142*4);
    if(zone==1)r3_scroll_zone++;
    if(seq)r3_scroll_nonzero++;
    if(seq==r3_scroll_seq || !seq || zone!=1)return;
    r3_scroll_seq=seq;r3_scroll_frames++;uint32_t hash=2166136261u;
    for(unsigned i=0;i<224;i++){
        uint32_t bg=((uint32_t)r3_scroll_read16(0x34000+i*4)<<16)|r3_scroll_read16(0x34002+i*4);
        uint32_t fg=((uint32_t)r3_scroll_read16(0x14000+i*4)<<16)|r3_scroll_read16(0x14002+i*4);
        uint32_t want_bg=ram_word(ram,r3_scroll_bg+i*4),want_fg=ram_word(ram,r3_scroll_fg+i*4);
        hash=(hash^want_bg)*16777619u;hash=(hash^want_fg)*16777619u;
        r3_scroll_active+=(want_bg!=0)+(want_fg!=0);
        r3_scroll_words+=2;
        if(bg!=want_bg || fg!=want_fg){
            r3_scroll_bad++;
            fprintf(stderr,"R3 line-scroll mismatch: seq=%u line=%u bg=%08x/%08x fg=%08x/%08x\n",
                    seq,i,bg,want_bg,fg,want_fg);
            exit(2);
        }
    }
    if(r3_scroll_frames==1 || hash!=r3_scroll_hash)r3_scroll_changes++;
    r3_scroll_hash=hash;
    if(r3_scroll_map && r3_scroll_map+4096*4<=size && !(r3_scroll_frames%16)){
        r3_map_frames++;
        for(unsigned cell=0;cell<4096;cell++){
            uint32_t got=((uint32_t)r3_scroll_read16(0x30000+cell*4)<<16)|r3_scroll_read16(0x30002+cell*4);
            uint32_t want=ram_word(ram,r3_scroll_map+cell*4);
            r3_map_cells++;r3_map_active+=want!=0;
            if(got!=want){r3_map_bad++;fprintf(stderr,"R3 BG map mismatch: seq=%u cell=%u vram=%08x wram=%08x\n",seq,cell,got,want);exit(2);}
        }
    }
    if(r3_fg_map && r3_fg_map+4096*4<=size && !(r3_scroll_frames%16)){
        r3_fg_frames++;
        for(unsigned cell=0;cell<4096;cell++){
            uint32_t got=((uint32_t)r3_scroll_read16(0x10000+cell*4)<<16)|r3_scroll_read16(0x10002+cell*4);
            uint32_t want=ram_word(ram,r3_fg_map+cell*4);
            r3_fg_cells++;r3_fg_active+=want!=0;
            if(got!=want){r3_fg_bad++;fprintf(stderr,"R3 FG map mismatch: seq=%u cell=%u vram=%08x wram=%08x\n",seq,cell,got,want);exit(2);}
        }
    }
}
/* Every failing exit names its source line on stderr, so no exit 2 is silent
   (a fixture limit once failed with no message). */
static int exit2(int line){fprintf(stderr,"emulator_test: exit 2 at tools/emulator_test.c:%d\n",line);return 2;}
int main(int argc,char **argv) {
    if(argc!=7 && argc!=8) {fprintf(stderr,"Usage: emulator_test core.dylib game.cue bios-directory output-directory mailbox-address audio-mailbox-address [audio]\n");return exit2(__LINE__);}
    const int pacing_only=argc==8 && !strcmp(argv[7],"pacing");
    const int journey_only=argc==8 && !strcmp(argv[7],"journey");
    system_dir=argv[3];output_dir=argv[4];diagnostic_only=argc==8 && !strcmp(argv[7],"diagnostic");world_only=argc==8 && !strcmp(argv[7],"world");act_only=argc==8 && !strcmp(argv[7],"act");special_only=argc==8 && !strcmp(argv[7],"special");game_only=argc==8 && !strcmp(argv[7],"specialgame");packfail_only=argc==8 && !strcmp(argv[7],"packfail");act2_only=argc==8 && !strcmp(argv[7],"act2");sequence_only=argc==8 && !strcmp(argv[7],"sequence");eras_only=argc==8 && !strcmp(argv[7],"act2eras");travel_only=argc==8 && !strcmp(argv[7],"act2travel");act_only=act_only || sequence_only;act3_only=argc==8 && !strcmp(argv[7],"act3");act2_only=act2_only || act3_only;bigring_only=argc==8 && !strcmp(argv[7],"bigring");title_only=argc==8 && !strcmp(argv[7],"title");zones_only=argc==8 && !strcmp(argv[7],"zones");audio_only=argc==8 && !title_only && !zones_only && !travel_only && !eras_only && !diagnostic_only && !world_only && !act_only && !act2_only && !special_only && !game_only && !packfail_only && !bigring_only;
    if(journey_only)audio_only=0;
    /* SCD_ACT2_ROUTE: "x0-x1/y0-y1[d|D|R|l|w|r|j|p|T],..." player areas where the act2 route does
       not jump; with T it holds Right until X x1, then Left; with j a grounded player jumps; with l it holds Left; with w it brakes, waits for the swing
       platform at its left end and walks on; with r it rides until the
       platform reaches its right end; with d, a grounded player backs up 96 pixels left, stops and
       spin dashes right (Down, Down+B, Down held, release). D stops and spin dashes in place;
       R backs up 400 pixels then runs right; p alternates Jump every 20 updates. */
    /* SCD_ACT2_TRAVEL=1: the act2 route keeps running through a charged time warp and
       stops 60 frames after arriving in the destination era. */
    act2_travel=act2_only && getenv("SCD_ACT2_TRAVEL") && atoi(getenv("SCD_ACT2_TRAVEL"));
    if(act2_only || sequence_only)load_route(getenv("SCD_ACT2_ROUTE"));
    if(act2_only && !act3_only){const char *value=getenv("SCD_ACT_ERA");if(value){char *end;unsigned long target=strtoul(value,&end,10);if(!*value || *end || target<1 || target>3)return exit2(__LINE__);act_target_era=(unsigned)target;act_route_ready=0;}}
    if(act_only || act2_only){const char *value=getenv("SCD_ACT_START");if(value)act_start=strtoul(value,NULL,10);value=getenv("SCD_ACT_RIGHT");if(value)act_right=strtoul(value,NULL,10);}
    /* SCD_ACT_PAD_RECORD=1: feed the reference controller input but do not
       compare the accepted buttons or the 16 words, so a reference can be
       re-recorded after a deliberate timing change. It prints its own banner;
       a checker that requires the strict banner cannot accept this run. */
    act_pad_record=getenv("SCD_ACT_PAD_RECORD") && atoi(getenv("SCD_ACT_PAD_RECORD"));
    level_select_frame=getenv("SCD_LEVEL_SELECT")?(unsigned)strtoul(getenv("SCD_LEVEL_SELECT"),NULL,10):0;
    if(getenv("SCD_ACT_PAD_TRACE")){
        if(!(act_only || act2_only) || sequence_only || act2_travel || act_pad_load(getenv("SCD_ACT_PAD_TRACE")))return exit2(__LINE__);
        if(act_pad_record)printf("Re-recording act input from %u reference states; accepted buttons and 16-word state are NOT compared\n",act_pad_count);
        else printf("Recorded act input: %u states; exact controller and 16-word reference required\n",act_pad_count);
    } else if(act_pad_record && !getenv("SCD_SEQUENCE_PAD_DIR"))return exit2(__LINE__);
    const char *sequence_pad_dir=getenv("SCD_SEQUENCE_PAD_DIR");
    if(sequence_pad_dir){
        if(!sequence_only || getenv("SCD_ACT_PAD_TRACE"))return exit2(__LINE__);
        /* Validate every stage before boot, then start with Act 1. */
        for(unsigned act=0;act<3;act++)if(act_pad_load_sequence(sequence_pad_dir,act))return exit2(__LINE__);
        if(act_pad_load_sequence(sequence_pad_dir,0))return exit2(__LINE__);
        /* SCD_ACT_PAD_RECORD=1 here feeds script-derived input (tools/act_reference_from_script.py)
           without comparing; tools/act_test.c then replays each act's own trace strictly. */
        if(act_pad_record)printf("Re-recording sequence input: Act 1 %u states; accepted buttons and 16-word state are NOT compared\n",act_pad_count);
        else printf("Recorded sequence input: Act 1 %u states; exact controller and 16-word reference required\n",act_pad_count);
    }
    const char *special_address=getenv("SCD_SPECIAL_MAILBOX");
    if(special_only && !special_address)return exit2(__LINE__);
    size_t special_mailbox=special_address?0x100000+(strtoul(special_address,NULL,16)&0xfffff):0;
    unsigned special_captures=0,special_return=0,special_nested=0,special_bench_count=0,special_bench_wait=0,special_live=0;
    const char *bench_address=getenv("SCD_SPECIAL_BENCHMARK");
    size_t bench_mailbox=bench_address?0x100000+(strtoul(bench_address,NULL,16)&0xfffff):0;
    if(special_only && !bench_address)return exit2(__LINE__);
    const char *sonic_address=getenv("SCD_SPECIAL_SONIC");
    size_t sonic_mailbox=sonic_address?0x100000+(strtoul(sonic_address,NULL,16)&0xfffff):0;
    if(special_only && !sonic_address)return exit2(__LINE__);
    unsigned sonic_captures=0,effect_captures=0,ufo_captures=0,contact_count=0;
    const char *contact_address=getenv("SCD_SPECIAL_CONTACTS");
    if(special_only && !contact_address)return exit2(__LINE__);
    size_t contact_mailbox=contact_address?0x100000+(strtoul(contact_address,NULL,16)&0xfffff):0;
    const char *floor_address=getenv("SCD_FLOOR_MAILBOX");
    size_t floor_mailbox=floor_address?0x100000+(strtoul(floor_address,NULL,16)&0xfffff):0;
    const char *world_address=getenv("SCD_WORLD_MAILBOX");
    const char *sonic_view_address=getenv("SCD_SONIC_VIEW");
    const char *effect_address=getenv("SCD_EFFECT_MAILBOX");
    size_t effect_at=effect_address?0x100000+(strtoul(effect_address,NULL,16)&0xfffff):0;
    FILE *effect_file=NULL;
    unsigned effect_previous=~0u,effect_fixture=~0u,effect_due=0,effect_snapshot[57],effect_sonic[18],effect_count=0,effect_travel_count=0;
    if(effect_address){char path[4096];snprintf(path,sizeof(path),"%s/effect-target-trace.txt",output_dir);effect_file=fopen(path,"w");if(!effect_file)return exit2(__LINE__);}
    const char *player_visual_address=getenv("SCD_PLAYER_VISUAL_TRACE");
    size_t player_visual_at=player_visual_address?0x100000+(strtoul(player_visual_address,NULL,16)&0xfffff):0;
    FILE *player_visual_file=NULL;
    if(player_visual_address){char path[4096];snprintf(path,sizeof(path),"%s/player-visual-trace.txt",output_dir);player_visual_file=fopen(path,"w");if(!player_visual_file)return exit2(__LINE__);}
    size_t sonic_view_at=sonic_view_address?0x100000+(strtoul(sonic_view_address,NULL,16)&0xfffff):0;
    unsigned sonic_view_due=0,sonic_view_snapshot[18],sonic_view_count=0,sonic_view_serial=0;
    bool sonic_view_seen[4][198][4]={{{false}}};
    if((world_only || act_only || act2_only) && !world_address)return exit2(__LINE__);
    const char *iteration_address=getenv("SCD_WORLD_ITERATION");
    size_t iteration_mailbox=iteration_address?0x100000+(strtoul(iteration_address,NULL,16)&0xfffff):0;
    const char *progress_address=getenv("SCD_WORLD_PROGRESS");
    size_t progress_mailbox=progress_address?0x100000+(strtoul(progress_address,NULL,16)&0xfffff):0;
    size_t world_mailbox=world_address?0x100000+(strtoul(world_address,NULL,16)&0xfffff):0;
    size_t audio_mailbox=0x100000+(strtoul(argv[6],NULL,16)&0xfffff);
    size_t mailbox=0x100000+(strtoul(argv[5],NULL,16)&0xfffff);
    const char *act_profile=getenv("SCD_FRAME_PROFILE");unsigned act_profile_seq=0;
    size_t act_profile_at=act_profile?0x100000+(strtoul(act_profile,NULL,16)&0xfffff):0;
    char trace_path[4096];snprintf(trace_path,sizeof(trace_path),"%s/player-target-trace.txt",output_dir);
    FILE *trace=fopen(trace_path,"w");if(!trace){perror(trace_path);return exit2(__LINE__);}
    char audio_path[4096];snprintf(audio_path,sizeof(audio_path),"%s/audio.raw",output_dir);
    audio_file=fopen(audio_path,"wb");if(!audio_file)return exit2(__LINE__);
    snprintf(audio_path,sizeof(audio_path),"%s/feedback-preview.raw",output_dir);preview_file=fopen(audio_path,"wb");if(!preview_file)return exit2(__LINE__);
    unsigned trace_count=0,last_sequence=0,last_progress=0,last_tick=0;bool seen[28][600]={{false}};
    void *core=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);if(!core){fprintf(stderr,"%s\n",dlerror());return exit2(__LINE__);}
    if(getenv("SCD_ZONE_ART_MAILBOX")){
        zone_read_cram=dlsym(core,"VDP2_Read16_DB");if(!zone_read_cram)return exit2(__LINE__);
    }
#define LOAD(name) __typeof__(&name) p_##name=(__typeof__(&name))dlsym(core,#name);if(!p_##name)abort()
    LOAD(retro_set_environment);LOAD(retro_set_video_refresh);LOAD(retro_set_audio_sample);
    LOAD(retro_set_audio_sample_batch);LOAD(retro_set_input_poll);LOAD(retro_set_input_state);
    LOAD(retro_get_memory_data);LOAD(retro_get_memory_size);
    LOAD(retro_serialize_size);LOAD(retro_serialize);
    LOAD(retro_init);LOAD(retro_load_game);LOAD(retro_run);LOAD(retro_unload_game);LOAD(retro_deinit);
    if(getenv("SCD_CPU_AT")){cpu_at_run=p_retro_run;p_retro_run=cpu_at_checked_run;cpu_at_ssize=p_retro_serialize_size;cpu_at_ser=p_retro_serialize;
        cpu_at_data=(void *(*)(unsigned))p_retro_get_memory_data;cpu_at_size=(size_t (*)(unsigned))p_retro_get_memory_size;if(argc>5)cpu_at_trace=0x100000+(strtoul(argv[5],NULL,16)&0xfffff);}
    dma_attach();if(dma_stats && argc>5)dma_trace=0x100000+(strtoul(argv[5],NULL,16)&0xfffff);if(dma_stats){dma_data=(void *(*)(unsigned))p_retro_get_memory_data;dma_size=(size_t (*)(unsigned))p_retro_get_memory_size;dma_run=p_retro_run;p_retro_run=dma_checked_run;atexit(dma_report);}
    if(getenv("QA_NBG0_MAPS") && getenv("SCD_WORLD_MAILBOX")){
        nbg0_vdp2=(uint16_t (*)(uint32_t))dlsym(core,"VDP2_Read16_DB");if(!nbg0_vdp2)return exit2(__LINE__);
        {unsigned long m=strtoul(getenv("QA_NBG0_MAPS"),NULL,16)&0x0fffffff;nbg0_maps=((m&0x0ff00000)==0x00200000?0:0x100000)+(m&0xfffff);}
        nbg0_box=0x100000+(strtoul(getenv("SCD_WORLD_MAILBOX"),NULL,16)&0xfffff);
        nbg0_data=(void *(*)(unsigned))p_retro_get_memory_data;nbg0_size=(size_t (*)(unsigned))p_retro_get_memory_size;
        if(argc>5)nbg0_trace=0x100000+(strtoul(argv[5],NULL,16)&0xfffff);
        nbg0_run=p_retro_run;p_retro_run=nbg0_checked_run;atexit(nbg0_report);
    }
    if(getenv("QA_R3_SCROLL_BG") && getenv("QA_R3_SCROLL_FG") && getenv("SCD_WORLD_MAILBOX")){
        r3_scroll_read16=(uint16_t (*)(uint32_t))dlsym(core,"VDP2_Read16_DB");if(!r3_scroll_read16)return exit2(__LINE__);
        r3_scroll_box=0x100000+(strtoul(getenv("SCD_WORLD_MAILBOX"),NULL,16)&0xfffff);
        r3_scroll_bg=0x100000+(strtoul(getenv("QA_R3_SCROLL_BG"),NULL,16)&0xfffff);
        r3_scroll_fg=0x100000+(strtoul(getenv("QA_R3_SCROLL_FG"),NULL,16)&0xfffff);
        if(getenv("QA_R3_BG_MAP"))r3_scroll_map=0x100000+(strtoul(getenv("QA_R3_BG_MAP"),NULL,16)&0xfffff);
        if(getenv("QA_R3_FG_MAP"))r3_fg_map=0x100000+(strtoul(getenv("QA_R3_FG_MAP"),NULL,16)&0xfffff);
        r3_scroll_data=(void *(*)(unsigned))p_retro_get_memory_data;r3_scroll_size=(size_t (*)(unsigned))p_retro_get_memory_size;
        r3_scroll_run=p_retro_run;p_retro_run=r3_scroll_checked_run;atexit(r3_scroll_report);
    }
    if(getenv("SCD_WORLD_MAILBOX")){
        shot_box=0x100000+(strtoul(getenv("SCD_WORLD_MAILBOX"),NULL,16)&0xfffff);
        if(argc>5)shot_trace=0x100000+(strtoul(argv[5],NULL,16)&0xfffff);
        shot_data=(void *(*)(unsigned))p_retro_get_memory_data;shot_size=(size_t (*)(unsigned))p_retro_get_memory_size;
        shot_run=p_retro_run;p_retro_run=shot_checked_run;
        if(getenv("QA_SONIC_VIEW") && getenv("QA_SONIC_FRAMES")){
            static uint8_t pack[0x18000];FILE *fp=fopen(getenv("QA_SONIC_FRAMES"),"rb");if(!fp)return 2;
            size_t n=fread(pack,1,sizeof(pack),fp);fclose(fp);
            if(scd_sonic_frames_open(&tex_frames,pack,n))return 2;
            tex_vdp1=(uint16_t (*)(uint32_t))dlsym(core,"VDP1_Read16_DB");if(!tex_vdp1)return 2;
            tex_box=0x100000+(strtoul(getenv("QA_SONIC_VIEW"),NULL,16)&0xfffff);tex_ready=1;atexit(tex_report);
        }
    }
    p_retro_set_environment(environment);p_retro_set_video_refresh(video);
    p_retro_set_audio_sample(audio);p_retro_set_audio_sample_batch(audio_batch);
    p_retro_set_input_poll(input_poll);p_retro_set_input_state(input_state);p_retro_init();
    struct retro_game_info game={.path=argv[2]};
    if(!p_retro_load_game(&game)){fprintf(stderr,"Game load failed\n");return exit2(__LINE__);}
    if(backup_open(p_retro_get_memory_data,p_retro_get_memory_size))return exit2(__LINE__);
    /* Allow the explicit driver-ready handshake to complete before controls. */
    for(unsigned boot=0;boot<200;boot++)p_retro_run();
    if(argc==8 && !strcmp(argv[7],"save")){
        int result=save_run(mailbox,p_retro_get_memory_data,p_retro_get_memory_size,p_retro_run);
        p_retro_unload_game();p_retro_deinit();return result;
    }
    /* Archived BINs do not carry their ELF. Locate the live title trace header,
       not code literals, to compare pacing without rebuilding the old release. */
    if(pacing_only){
        unsigned found=0;
        for(unsigned wait=0;wait<3000 && !found;wait++){
            const uint8_t *ram=p_retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM);
            size_t size=p_retro_get_memory_size(RETRO_MEMORY_SYSTEM_RAM);
            if(ram)for(size_t at=0x100000;at+16<size;at+=4){
                if(ram_word(ram,at)==0x5449544c && ram_word(ram,at+4)>0 && ram_word(ram,at+4)<4000 &&
                   (ram_word(ram,at+8)&0xff)==2 && ram_word(ram,at+12)==0){mailbox=at;found++;}
            }
            if(found>1){fprintf(stderr,"Ambiguous archived trace header\n");return exit2(__LINE__);}
            if(!found)p_retro_run();
        }
        if(!found){fprintf(stderr,"Archived trace header not found\n");return exit2(__LINE__);}
        printf("Pacing trace address: %08x\n",(unsigned)(0x06000000+mailbox-0x100000));
    }
    /* packfail: a disc without one stage pack must stop on the CD stage data error screen. */
    if(packfail_only){
        const char *packs=getenv("SCD_STAGE_PACKS");if(!packs)return exit2(__LINE__);
        for(unsigned f=0;f<3000;f++)p_retro_run();
        const uint8_t *ram=p_retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM);if(!ram)return exit2(__LINE__);
        size_t at=0x100000+(strtoul(packs,NULL,16)&0xfffff);frame=3200;
        printf("Stage packs: magic=%08x vblanks=%u bytes=%u error=%u\n",ram_word(ram,at),ram_word(ram,at+4),ram_word(ram,at+8),ram_word(ram,at+12));
        screenshot("stage-load-failure");
        p_retro_unload_game();p_retro_deinit();return 0;
    }
    /* The game boots into the title screen, which publishes 'TITL', its vintCounter and
       titleMode | menu selectable<<8 | menuSel<<16 in the trace mailbox (src/title_view.inc).
       Start (pressed and released until the menu opens) opens the menu and B selects NEW GAME;
       every other script begins once the trace mailbox shows gameplay. */
    /* Attract runs (SCD_SPECIAL_ATTRACT) stay on the title until it times out. */
    if(!title_only && !zones_only && !(game_only && getenv("SCD_SPECIAL_ATTRACT"))){
        unsigned seen=0,n=0;
        for(;;n++){
            const uint8_t *ram=p_retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM);
            uint32_t magic=ram && mailbox+12<=p_retro_get_memory_size(RETRO_MEMORY_SYSTEM_RAM)?ram_word(ram,mailbox):0;
            if(magic==0x53434432 && seen)break;
            if(n>20000){fprintf(stderr,"Title screen did not hand over\n");return exit2(__LINE__);}
            button_mask=0;
            if(magic==0x5449544c){
                unsigned state=ram_word(ram,mailbox+8);seen=1;
                if((state&255)==2 && !(state>>16&255) && n%8<4)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_START;
                else if((state&256) && n%8<4)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_A;
            }
            p_retro_run();
        }
        button_mask=0;printf("Title screen: New Game selected; gameplay after %u frames\n",n);fflush(stdout);
    }
    if(pacing_only){
        unsigned previous=0,seq=0,intervals=0,blanks=0,late=0,max_gap=0,sim=0;
        const char *profile=getenv("SCD_FRAME_PROFILE");unsigned profile_seq=0;
        size_t profile_at=profile?0x100000+(strtoul(profile,NULL,16)&0xfffff):0;
        for(unsigned f=0;f<4000 && intervals<1800;f++){
            const uint8_t *ram=p_retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM);
            unsigned latest=ram_word(ram,mailbox+4);
            if(profile && ram_word(ram,profile_at)==0x46505246){
                unsigned n=ram_word(ram,profile_at+4);
                if(n-profile_seq>64 || ram_word(ram,profile_at+8)!=32)return exit2(__LINE__);
                while(profile_seq<n){
                    size_t at=profile_at+(4+(++profile_seq%64)*32)*4;
                    if(ram_word(ram,at)!=profile_seq)return exit2(__LINE__);
                    printf("Frame profile:");for(unsigned i=0;i<24;i++)printf(" %u",ram_word(ram,at+i*4));printf("\n");
                }
            }
            if(latest-seq>64){fprintf(stderr,"Pacing trace overflow\n");return exit2(__LINE__);}
            while(seq<latest){size_t r=mailbox+(24+(++seq%64)*21)*4;
                if(ram_word(ram,r)!=seq || ram_word(ram,r+4)!=0xffffffffu)return exit2(__LINE__);
                unsigned tick=ram_word(ram,r+80);sim=ram_word(ram,r+36);
                if(previous){if(tick<=previous)return exit2(__LINE__);unsigned gap=tick-previous;intervals++;blanks+=gap;late+=gap>1;if(gap>max_gap)max_gap=gap;if(gap>1)printf("Pacing gap: simulation=%u vblanks=%u\n",sim,gap);}
                previous=tick;
            }
            button_mask=sim>=2?1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT:0;
            if(sim>=601 && (sim-601)%120<24)button_mask|=1u<<RETRO_DEVICE_ID_JOYPAD_B;
            p_retro_run();
        }
        printf("Pacing comparison: intervals=%u vblanks=%u late=%u max_gap=%u simulation=%u\n",intervals,blanks,late,max_gap,sim);
        if(profile && profile_seq<1800){fprintf(stderr,"Missing frame profile records\n");return exit2(__LINE__);}
        p_retro_unload_game();p_retro_deinit();return intervals>=1800?0:2;
    }
    /* zones: enter one zone through the level select (hold A+B+C and press Start
       on the title, Right once per zone, Start), then hold Right for 900 updates.
       SCD_ZONE picks the zone. It proves the zone's terrain and its object layout
       both load from the CD: the zone mailbox must name the zone and objects must
       spawn from the layout that stage_packs_load hands to the object code. */
    if(zones_only){
        const char *zone_text=getenv("SCD_ZONE");
        if(!zone_text || !world_mailbox)return exit2(__LINE__);
        const char *object_fault_text=getenv("SCD_OBJECTS_OVERLAY_FAULT");
        size_t object_fault_at=object_fault_text?0x100000+(strtoul(object_fault_text,NULL,16)&0xfffff):0;
        const char *bg_slave_text=getenv("SCD_BG_SLAVE_MAILBOX");
        size_t bg_slave_at=bg_slave_text?0x100000+(strtoul(bg_slave_text,NULL,16)&0xfffff):0;
        const char *r5_event_text=getenv("SCD_R5_EVENT_MAILBOX");
        size_t r5_event_at=r5_event_text?0x100000+(strtoul(r5_event_text,NULL,16)&0xfffff):0;
        unsigned want=(unsigned)strtoul(zone_text,NULL,10),seen=0,phase=0,wait=0,go=0,play=0,max_active=0,max_x=0;
        unsigned want_act=getenv("SCD_ZONE_ACT")?(unsigned)strtoul(getenv("SCD_ZONE_ACT"),NULL,10):0;
        unsigned want_era=getenv("SCD_ZONE_ERA")?(unsigned)strtoul(getenv("SCD_ZONE_ERA"),NULL,10):0;
        const char *art_text=getenv("SCD_ZONE_ART_MAILBOX");
        size_t art_at=art_text?0x100000+(strtoul(art_text,NULL,16)&0xfffff):0;
        const char *palette_text=getenv("SCD_PALETTE_FRAME");
        size_t palette_at=palette_text?0x100000+(strtoul(palette_text,NULL,16)&0xfffff):0;
        unsigned art_case=0,art_wait=0,art_captures=0,art_start=0;
        int zone_music=getenv("SCD_ZONE_MUSIC")!=NULL;
        unsigned music_pause_fad=0,music_previous_fad=0,music_loop=0;
        unsigned loop_frames=getenv("SCD_ZONE_MUSIC_LOOP_FRAMES")?strtoul(getenv("SCD_ZONE_MUSIC_LOOP_FRAMES"),NULL,10):0;
        /* Exploratory CC controller route. This only operates the pad after
           level selection; it never writes gameplay memory or skips actors. */
        unsigned route_retreat=getenv("SCD_ZONE_ROUTE_RETREAT")?strtoul(getenv("SCD_ZONE_ROUTE_RETREAT"),NULL,10):0;
        unsigned route_limit=getenv("SCD_ZONE_ROUTE_UPDATES")?strtoul(getenv("SCD_ZONE_ROUTE_UPDATES"),NULL,10):10000;
        unsigned route_seq=~0u,route_updates=0,route_stuck=0,route_jumps=0,route_hold=0,route_back=0,route_buttons=0,route_last_x=0;
        unsigned route_ridden=0,route_late=0,route_last_frame=0,route_stage=~0u,route_transitions=0;
        unsigned route_runup=0;
        /* R5's diagnostic ledger resets with each load_era(), as its live
           scroll state correctly must. Retain the requested route's most
           recent observation so a following Act-3 handoff cannot replace
           Act 2's evidence in the final report. */
        uint32_t route_r5_events[9],route_r5_trace[9],route_bg_slave[10];
        unsigned route_r5_seen=0,route_r5_trace_seen=0,route_bg_slave_seen=0;
        int route_r5_trace_enabled=getenv("SCD_R5_EVENT_TRACE")!=NULL;
        int route_local=getenv("SCD_ZONE_ROUTE_LOCAL")!=NULL;
        unsigned route_backjump_at[16],route_backjump_count=route_points("SCD_ZONE_ROUTE_BACKJUMP_AT",route_backjump_at);
        unsigned route_jump_at[16],route_jump_count=route_points("SCD_ZONE_ROUTE_JUMP_AT",route_jump_at);
        const char *route_pad_path=getenv("SCD_ZONE_PAD_TRACE");
        unsigned route_pad_tail=getenv("SCD_ZONE_PAD_TAIL")?strtoul(getenv("SCD_ZONE_PAD_TAIL"),NULL,10):0;
        const char *route_save=getenv("SCD_SAVE_MAILBOX");
        size_t route_save_at=route_save?0x100000+(strtoul(route_save,NULL,16)&0xfffff):0;
        unsigned route_generator_sequence=0,route_arrival_sequence=0,route_arrival_count=0;
        if(route_pad_tail>600 || (route_pad_tail && !route_pad_path))return exit2(__LINE__);
        if(route_pad_path && (cc_pad_load(route_pad_path) || !route_retreat || route_limit!=cc_pad_count+route_pad_tail))return exit2(__LINE__);
        int route_backjump=0;
        if(route_retreat>300 || route_limit>48000 || !route_limit)return exit2(__LINE__);
        if(want>6 || want_act>2 || want_era>3 || (want_act==2 && want_era<2))return exit2(__LINE__);
        int route_profile_all=act_profile && getenv("FRAME_PROFILE_ALL")!=NULL;
        int route_frame_hashes=getenv("ROUTE_FRAME_HASHES")!=NULL;
        size_t water_at=getenv("WATER_MAILBOX")?0x100000+(strtoul(getenv("WATER_MAILBOX"),NULL,16)&0xfffff):0;unsigned water_handled=0;
        for(frame=0;frame<60000;frame++){
            const uint8_t *ram=p_retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM);size_t size=p_retro_get_memory_size(RETRO_MEMORY_SYSTEM_RAM);
            /* Big ring and special stage (main.c world mailbox [140] stones, [141]
               touched<<16|special mode<<8|return act): one line per change, with
               curSpecStage when SCD_SPECIAL_STAGE_ADDR names special_cur_stage. */
            if(world_mailbox && world_mailbox+568<=size){
                static unsigned last_special=~0u,last_stones=~0u,last_stage=~0u,last_game=~0u;static long stage_at=-2,game_at=-2;
                if(stage_at==-2){const char *v=getenv("SCD_SPECIAL_STAGE_ADDR");stage_at=v?(long)(0x100000+(strtoul(v,NULL,16)&0xfffff)):-1;}
                /* SCD_SPECIAL_GAME (_scd_special_game_mailbox): [0] 'SSGM', [27] game active. */
                if(game_at==-2){const char *v=getenv("SCD_SPECIAL_GAME");game_at=v?(long)(0x100000+(strtoul(v,NULL,16)&0xfffff)):-1;}
                unsigned special=ram_word(ram,world_mailbox+564),stones=ram_word(ram,world_mailbox+560),stage=stage_at>=0?ram_word(ram,(size_t)stage_at):0;
                unsigned game=game_at>=0 && (size_t)game_at+160<=size && ram_word(ram,(size_t)game_at)==0x5353474d && ram_word(ram,(size_t)game_at+27*4);
                if(special!=last_special || stones!=last_stones || stage!=last_stage || game!=last_game){
                    printf("CC special: %u %u %u %u %u %u %u\n",frame,special>>16,(special>>8)&255,special&255,stones,stage,game);
                    last_special=special;last_stones=stones;last_stage=stage;last_game=game;
                }
            }
            /* Diagnostic only (SCD_FRAME_PROFILE build): every frame-profile
               record of the whole route, for tools/frame_headroom.py. */
            if(route_profile_all && act_profile_at+(4+64*32)*4<=size && ram_word(ram,act_profile_at)==0x46505246){
                unsigned latest=ram_word(ram,act_profile_at+4);
                if(!act_profile_seq && latest>64)act_profile_seq=latest-64;
                if(latest-act_profile_seq>64 || ram_word(ram,act_profile_at+8)!=32){fprintf(stderr,"Route profile overflow/stride mismatch\n");return exit2(__LINE__);}
                while(act_profile_seq<latest){
                    size_t at=act_profile_at+(4+(++act_profile_seq%64)*32)*4;
                    if(ram_word(ram,at)!=act_profile_seq)return exit2(__LINE__);
                    printf("Frame profile:");for(unsigned i=0;i<32;i++)printf(" %u",ram_word(ram,at+i*4));printf("\n");
                }
            }
            /* Diagnostic only: FNV-1a of every presented frame, so two builds
               can be compared frame by frame over a whole route. */
            if(route_frame_hashes && last_video){
                uint64_t hash=1469598103934665603ULL;unsigned bytes=pixel_format==RETRO_PIXEL_FORMAT_XRGB8888?4:2;
                for(unsigned y=0;y<last_height;y++){const uint8_t *p=(const uint8_t *)last_video+y*last_pitch;
                    for(unsigned i=0;i<last_width*bytes;i++){hash^=p[i];hash*=1099511628211ULL;}}
                printf("Frame hash: %u %ux%u %016llx\n",frame,last_width,last_height,(unsigned long long)hash);
                const char *shots=getenv("ROUTE_SHOT_FRAMES");
                for(const char *at=shots;at && *at;){
                    char *next;unsigned long want_frame=strtoul(at,&next,10);
                    if(next==at)break;
                    if(want_frame==frame){char name[40];snprintf(name,sizeof(name),"route-frame-%u",frame);screenshot(name);}
                    at=*next==','?next+1:next;
                }
            }
            /* Diagnostic only: src/water_raster.h's mailbox when its handler
               ran (armed line, timer compare, handler count, VCNT). */
            if(water_at && water_at+32<=size && ram_word(ram,water_at)==0x57415452 && ram_word(ram,water_at+16)!=water_handled){
                water_handled=ram_word(ram,water_at+16);
                printf("Water line: %u armed=%u compare=%u handlers=%u switch_vcnt=%u\n",frame,ram_word(ram,water_at+8),
                       ram_word(ram,water_at+12),water_handled,ram_word(ram,water_at+20));
            }
            if(object_fault_at && object_fault_at+16<=size && ram_word(ram,object_fault_at)==0x5a4f4e45){
                fprintf(stderr,"Zone overlay fault: callsite=%u objects_zone=%u code_zone=%u\n",
                        ram_word(ram,object_fault_at+12),ram_word(ram,object_fault_at+4),ram_word(ram,object_fault_at+8));
                return exit2(__LINE__);
            }
            if(act_profile){
                if(act_profile_at+(4+64*32)*4>size)return exit2(__LINE__);
                if(ram_word(ram,act_profile_at)==0x46505246){
                    unsigned latest=ram_word(ram,act_profile_at+4);
                    if(latest-act_profile_seq>64 || ram_word(ram,act_profile_at+8)!=32)return exit2(__LINE__);
                    while(act_profile_seq<latest){
                        size_t at=act_profile_at+(4+(++act_profile_seq%64)*32)*4;
                        if(ram_word(ram,at)!=act_profile_seq)return exit2(__LINE__);
                        printf("Frame profile:");for(unsigned i=0;i<32;i++)printf(" %u",ram_word(ram,at+i*4));printf("\n");
                    }
                }
            }
            uint32_t magic=ram && mailbox+12<=size?ram_word(ram,mailbox):0;
            button_mask=0;
            /* Wait for title mode 2, the finished title with its menu, as the
               generic title handler does; the intro before it ignores the pad. */
            if(phase==0 && magic==0x5449544c && (ram_word(ram,mailbox+8)&255)==2 && ++seen>=60){phase=1;wait=frame;}
            if(phase==1){
                /* Saturn A+B+C (libretro B+A+R) held, then Start pressed while they stay held. */
                unsigned abc=(1u<<RETRO_DEVICE_ID_JOYPAD_B)|(1u<<RETRO_DEVICE_ID_JOYPAD_A)|(1u<<RETRO_DEVICE_ID_JOYPAD_R);
                button_mask=abc|(frame>=wait+4 && frame<wait+8?1u<<RETRO_DEVICE_ID_JOYPAD_START:0);
                if(frame>=wait+12){phase=2;wait=frame;}
            }else if(phase==2){
                /* The menu publishes 'LSEL' and zone|act<<8|era<<16 (src/main.c). Press
                   Right, four frames on and eight off, until it reports the wanted
                   zone, then Start. */
                if(magic==0x4c53454c){
                    unsigned sel=ram_word(ram,mailbox+8);
                    unsigned row=sel>>24,target_row=(sel&255)!=want?0:((sel>>8)&255)!=want_act?1:2;
                    int selected=(sel&0xffffff)==(want|want_act<<8|want_era<<16);
                    if(!go && !selected){
                        if((frame-wait)%12<4)button_mask=1u<<(row!=target_row?RETRO_DEVICE_ID_JOYPAD_DOWN:RETRO_DEVICE_ID_JOYPAD_RIGHT);
                    }
                    else if(!go){go=frame+20;char name[40];snprintf(name,sizeof(name),"zones-select-%u",want);screenshot(name);}
                    if(frame==wait+20)screenshot("zones-level-select");
                }
                if(go && frame>=go && frame<go+4)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_START;
                if(magic==0x53434432 && go && frame>go){phase=3;play=frame;}
                if(frame>wait+3600){fprintf(stderr,"Zone %u: stuck in the level select (trace magic %08x, selection %08x, go %u)\n",want,magic,ram_word(ram,mailbox+8),go);return exit2(__LINE__);}
            }else if(phase==3 && getenv("SCD_QQ_LIFECYCLE")){
                /* Fixture coverage of slave ownership; not a natural route.
                   X cycles eras via load_era; Start+Right+C uses the existing
                   one-life game-over fixture, then the real title renderer. */
                static unsigned lc_state,lc_at,lc_changes,lc_expected,lc_title_at,lc_title_tick;
                const char *kind=getenv("SCD_QQ_LIFECYCLE");
                size_t ready=0x100000+(strtoul(getenv("SCD_QQ_SLAVE_READY"),NULL,16)&0xfffff);
                size_t title=0x100000+(strtoul(getenv("SCD_TITLE_MAILBOX"),NULL,16)&0xfffff);
                if(ready+4>size || title+12>size || world_mailbox+572>size || want!=3 || want_act)return exit2(__LINE__);
                unsigned t=frame-play,z=ram_word(ram,world_mailbox+568),e=ram_word(ram,world_mailbox+8);
                if(!lc_state && t>=120){
                    if(z!=3 || e!=0 || ram_word(ram,ready)!=1){fprintf(stderr,"QQ lifecycle: initial owner/era invalid\n");return exit2(__LINE__);}
                    lc_state=1;lc_at=frame;lc_expected=1;
                }
                if(!strcmp(kind,"title")){
                    if(lc_state==1 && frame<lc_at+4)button_mask=(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT)|(1u<<RETRO_DEVICE_ID_JOYPAD_R);
                    if(lc_state && ram_word(ram,title)==0x5449544c && (ram_word(ram,title+8)&255)==2){
                        if(ram_word(ram,ready)){fprintf(stderr,"QQ lifecycle: background slave still owned at title\n");return exit2(__LINE__);}
                        if(!lc_title_at){lc_title_at=frame;lc_title_tick=ram_word(ram,title+4);}
                        if(frame>=lc_title_at+120 && ram_word(ram,title+4)>lc_title_tick){
                            screenshot("qq-title-return");printf("QQ lifecycle passed: title bg_ready=0 advancing_frames=120\n");
                            p_retro_unload_game();p_retro_deinit();return 0;
                        }
                    }
                }else if(!strcmp(kind,"era")){
                    if(lc_state==1){
                        if(frame<lc_at+4)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_Y; /* Saturn X */
                        if(e==lc_expected && ram_word(ram,ready)==1 && frame>=lc_at+60){
                            printf("QQ lifecycle era: %u era=%u bg_ready=1\n",++lc_changes,e);
                            if(lc_changes==8){screenshot("qq-era-reloaded");printf("QQ lifecycle passed: era reloads=8 bg_ready=1\n");p_retro_unload_game();p_retro_deinit();return 0;}
                            lc_expected=(e+1)&3;lc_at=frame+30;lc_state=2;
                        }
                    }else if(lc_state==2 && frame>=lc_at)lc_state=1;
                }else return exit2(__LINE__);
                if(t>6000){fprintf(stderr,"QQ lifecycle: timed out state=%u changes=%u era=%u ready=%u\n",lc_state,lc_changes,e,ram_word(ram,ready));return exit2(__LINE__);}
            }else if(phase==3 && getenv("SCD_WATER_MAILBOX")){
                /* Tidal Tempest water line (tools/test_water_emulator.py). A fixture: it
                   holds Sonic (actwk[0]) above, below and deep under the water and only
                   reads the rest. Each case captures consecutive frames with the water
                   raster mailbox (src/water_raster.h) and CRAM banks 0 and 1. */
                static unsigned wt_case,wt_since,wt_shots;
                size_t actor=0x100000+(strtoul(getenv("SCD_WATER_ACTWK"),NULL,16)&0xfffff);
                size_t box=0x100000+(strtoul(getenv("SCD_WATER_MAILBOX"),NULL,16)&0xfffff);
                size_t level=0x100000+(strtoul(getenv("SCD_WATER_LEVEL"),NULL,16)&0xfffff);
                unsigned wx=getenv("SCD_WATER_X")?(unsigned)strtoul(getenv("SCD_WATER_X"),NULL,10):700;
                static const int depth[3]={-60,50,400};
                if(actor+68>size || box+32>size || level+2>size || (level&1))return exit2(__LINE__);
                uint16_t (*read_vdp2)(uint32_t)=dlsym(core,"VDP2_Read16_DB");if(!read_vdp2)return exit2(__LINE__);
                unsigned t=frame-play;uint8_t *w=(uint8_t *)ram;button_mask=0;
                uint16_t water;memcpy(&water,w+level,2);
                if(wt_case<3 && t>=300){
                    uint16_t v=(uint16_t)wx;memcpy(w+actor+8,&v,2);v=0;memcpy(w+actor+10,&v,2);
                    v=(uint16_t)((int16_t)water+depth[wt_case]);memcpy(w+actor+12,&v,2);v=0;memcpy(w+actor+14,&v,2);
                    memcpy(w+actor+16,&v,2);memcpy(w+actor+18,&v,2);memcpy(w+actor+20,&v,2);
                    if(!wt_since)wt_since=t;
                    if(t-wt_since>=90){
                        char name[40];snprintf(name,sizeof(name),"water-%u-%02u",wt_case,wt_shots);screenshot(name);
                        printf("Water frame: %u %u water=%d latch=%u line=%u t0=%u isr=%u vcnt=%u full=%u enabled=%u\n",wt_case,wt_shots,(int16_t)water,
                            ram_word(ram,box+4),ram_word(ram,box+8),ram_word(ram,box+12),ram_word(ram,box+16),ram_word(ram,box+20),ram_word(ram,box+24),ram_word(ram,box+28));
                        if(!wt_shots){
                            printf("Water CRAM: %u",wt_case);for(unsigned c=0;c<64;c++)printf(" %04x",read_vdp2(0x100000+c*2));
                            for(unsigned c=0;c<64;c++)printf(" %04x",read_vdp2(0x100200+c*2));putchar('\n');
                        }
                        if(++wt_shots==30){wt_case++;wt_shots=0;wt_since=0;}
                    }
                }
                if(wt_case==3){printf("Water probe done\n");p_retro_unload_game();p_retro_deinit();return 0;}
                if(t>6000){fprintf(stderr,"Water probe: timed out in case %u\n",wt_case);return exit2(__LINE__);}
            }else if(phase==3 && getenv("SCD_CC_SPECIAL_ACTWK")){
                /* Collision Chaos special stage and return (tools/test_cc_special_bank.py). A
                   fixture: it places Sonic past Act 1's goal post (11200) and then on the big
                   ring (12176,1328, CC1 layout) with 50 rings, then only reads: the special stage must load its effect bank
                   (2) and the return to Act 2 must load Collision Chaos's (1) again. */
                static unsigned sp_stage,sp_special,sp_return,sp_resume_sequence;
                size_t actor=0x100000+(strtoul(getenv("SCD_CC_SPECIAL_ACTWK"),NULL,16)&0xfffff);
                size_t rings=0x100000+(strtoul(getenv("SCD_CC_SPECIAL_RINGS"),NULL,16)&0xfffff);
                size_t bank_at=0x100000+(strtoul(getenv("SCD_SFX_BANK_MAILBOX"),NULL,16)&0xfffff);
                if(world_mailbox+572>size || actor+68>size || bank_at+16>size || rings+2>size)return exit2(__LINE__);
                unsigned t=frame-play,zone=ram_word(ram,world_mailbox+568),act=ram_word(ram,world_mailbox+536);
                int bank=(int)ram_word(ram,bank_at+12)-1;unsigned loads=ram_word(ram,bank_at+4);
                int qq=want==3;
                size_t qq_ready=qq?0x100000+(strtoul(getenv("SCD_QQ_SLAVE_READY"),NULL,16)&0xfffff):0;
                if(qq && qq_ready+4>size)return exit2(__LINE__);
                uint8_t *w=(uint8_t *)ram;button_mask=0;
                if(t%60==0 || t==430 || t==470)printf("CC special: t=%u stage=%u zone=%u act=%u bank=%d loads=%u last_load_vblanks=%u x=%u y=%u\n",t,sp_stage,zone,act,bank,loads,ram_word(ram,bank_at+8),ram_word(ram,world_mailbox+52),ram_word(ram,world_mailbox+72));
                if(t==400 || t==470 || t==900 || t==2900)screenshot(t==400?"cc-special-goal":t==470?"cc-special-ring":t==900?"cc-special-after":"cc-special-late");
                if(sp_stage==0 && t>=300){
                    if(qq && ram_word(ram,qq_ready)!=1){fprintf(stderr,"QQ special: missing initial background owner\n");return exit2(__LINE__);}
                    sp_stage=1;
                }
                if(sp_stage==1){
                    /* The goal post (11200,1412) ends the act first; the big ring is past it. */
                    uint16_t v;unsigned ring_phase=t>=420;
                    /* ObjBigRing moves Sonic and locks him to Right on a touch: hold only briefly. */
                    if(t<480){
                    /* QQ positions: original R5/Z51ACT.C, goal 11064,948;
                       big ring 11168,864. The fixture stays near the goal
                       until the sign is touched, then enters the real ring. */
                    v=qq?(ring_phase?11168:11096):(ring_phase?12176:11232);memcpy(w+actor+8,&v,2);v=0;memcpy(w+actor+10,&v,2);v=qq?(ring_phase?864:936):(ring_phase?1328:1400);memcpy(w+actor+12,&v,2);v=0;memcpy(w+actor+14,&v,2);
                    memcpy(w+actor+16,&v,2);memcpy(w+actor+18,&v,2);memcpy(w+actor+20,&v,2);
                    v=50;memcpy(w+(rings&~(size_t)1),&v,2);
                    }
                    if(bank==2){
                        if(qq && ram_word(ram,qq_ready)){fprintf(stderr,"QQ special: background owner not released\n");return exit2(__LINE__);}
                        sp_special=t;sp_stage=2;screenshot("cc-special-entered");
                    }
                    if(t>3000){fprintf(stderr,"CC special: never entered the special stage (bank %d)\n",bank);return exit2(__LINE__);}
                }else if(sp_stage==2){
                    if(qq && bank==4 && zone==want && act==1 && ram_word(ram,qq_ready)==1 && !sp_resume_sequence)
                        sp_resume_sequence=ram_word(ram,mailbox+4);
                    if(bank==(qq?4:1) && zone==want && act==1 && (!qq || (ram_word(ram,qq_ready)==1 && sp_resume_sequence && ram_word(ram,mailbox+4)>=sp_resume_sequence+120))){sp_return=t;screenshot("cc-special-returned");
                        printf("CC special probe passed: special_bank_at=%u returned_at=%u zone=%u act=%u bank=%d loads=%u last_load_vblanks=%u\n",sp_special,sp_return,zone,act,bank,loads,ram_word(ram,bank_at+8));
                        p_retro_unload_game();p_retro_deinit();return 0;}
                    if(t>sp_special+20000){fprintf(stderr,"CC special: no return with the CC bank (zone %u act %u bank %d)\n",zone,act,bank);return exit2(__LINE__);}
                }
            }else if(phase==3 && getenv("SCD_TT3_BOSS_ACTWK")){
                /* Tidal Tempest Act 3 boss probe (tools/test_tt3_boss_emulator.py). A fixture,
                   not a route: it writes Sonic's position and roll state (actwk[0]) and only
                   reads the rest. egg4air (BOSS_4.C) must spawn and take its four hits
                   (status: colicnt 5 -> 1 -> 0), dive, bossflag must reach 4 at the exit
                   (2112,1360), egg4 (BOSS_4_2.C, status bit 17) must spawn, take its hit
                   (r_no0 18), escape, and the capsule, results and next zone follow. */
                static unsigned tt_stage,tt_since,tt_spawn,tt_hits,tt_last=5,tt_dive,tt_flag,tt_egg,tt_egg_hit,tt_defeat,tt_capsule,tt_boss_music;
                size_t actor=0x100000+(strtoul(getenv("SCD_TT3_BOSS_ACTWK"),NULL,16)&0xfffff);
                size_t flag_at=0x100000+(strtoul(getenv("SCD_TT3_BOSS_FLAG"),NULL,16)&0xfffff);
                if(world_mailbox+572>size || actor+68>size)return exit2(__LINE__);
                unsigned t=frame-play,zone=ram_word(ram,world_mailbox+568),act=ram_word(ram,world_mailbox+536);
                unsigned position=ram_word(ram,world_mailbox+552),status=ram_word(ram,world_mailbox+556);
                unsigned bossflag=ram_word(ram,flag_at&~3u)>>(8*(3-(flag_at&3)))&255;
                int bx=(int16_t)(position>>16),by=(int16_t)position;unsigned routine=(status>>8)&255,left=status&255,egg=(status>>17)&1;
                uint8_t *w=(uint8_t *)ram;
                #define PUT16(off,v) do{uint16_t v16=(uint16_t)(v);memcpy(w+actor+(off),&v16,2);}while(0)
                #define PUT8(off,v) do{uint16_t v16;size_t a=actor+(off);memcpy(&v16,w+(a&~(size_t)1),2);v16=(a&1)?(uint16_t)((v16&0xff00)|((v)&255)):(uint16_t)((v16&255)|((v)<<8));memcpy(w+(a&~(size_t)1),&v16,2);}while(0)
                #define HOLD(x,y,roll) do{PUT16(8,x);PUT16(10,0);PUT16(12,y);PUT16(14,0);PUT16(16,0);PUT16(18,(roll)?256:0);PUT16(20,0);PUT8(35,(roll)?6:2);PUT8(28,(roll)?2:0);}while(0)
                button_mask=0;
                /* 50 rings every update: a stray touch drops rings instead of ending the fixture. */
                {size_t rings=0x100000+(strtoul(getenv("SCD_TT3_RINGS"),NULL,16)&0xfffff);if(rings+2<=size){uint16_t v=50;memcpy(w+(rings&~(size_t)1),&v,2);}}
                if(zone!=want && tt_stage<6){fprintf(stderr,"TT3 boss: zone %u left early at update %u (stage %u)\n",zone,t,tt_stage);return exit2(__LINE__);}
                if(ram_word(ram,audio_mailbox+12)==ram_word(ram,audio_mailbox+20) && egg && !tt_boss_music)tt_boss_music=ram_word(ram,audio_mailbox+12);
                if(t%600==0){char name[32];snprintf(name,sizeof(name),"tt3-t%05u",t);screenshot(name);}
                if(t%30==0)printf("TT3 boss: t=%u stage=%u status=%08x boss=%d,%d bossflag=%u zone=%u act=%u music=%u\n",t,tt_stage,status,bx,by,bossflag,zone,act,ram_word(ram,audio_mailbox+12));
                if(getenv("SCD_TT3_DEBUG") && t>=480 && t<=620){
                    printf("TT3 slots t=%u:",t);
                    for(unsigned s=97;s<128;s++){size_t a=actor+s*68;unsigned id=w[a^1];if(id)printf(" %u:%u/r%u.%u/c%u.%u/p%u/m%u",s,id,w[(a+37)^1],w[(a+38)^1],w[(a+33)^1],w[(a+34)^1],w[(a+26)^1],w[(a+28)^1]);}
                    printf("\n");}
                if(getenv("SCD_TT3_DEBUG") && (t==530 || t==545 || t==560)){
                    size_t bytes=p_retro_serialize_size();void *state=malloc(bytes);
                    if(state && p_retro_serialize(state,bytes)){char label[40];snprintf(label,sizeof(label),"TT3 cpu t=%u",t);cpu_dump(label,state,bytes);}
                    if(t==560){char path[4096];snprintf(path,sizeof(path),"%s/wram.bin",output_dir);FILE *file=fopen(path,"wb");if(file){fwrite(ram,1,size,file);fclose(file);}}
                    free(state);}
                if(getenv("SCD_TT3_DEBUG") && t>=500 && t<=760)printf("TT3 run t=%u boss=%08x status=%08x sonic=%d,%d pframe=%u screen=%08x rno=%02x%02x rings=%u\n",t,position,status,(int16_t)(ram_word(ram,actor+8)>>16),(int16_t)(ram_word(ram,actor+12)>>16),ram_word(ram,world_mailbox+56*4),ram_word(ram,world_mailbox+50*4),w[(actor+36)^1],w[(actor+37)^1],ram_word(ram,world_mailbox+32*4));
                if(getenv("SCD_TT3_DEBUG") && t>=395 && t<=460)printf("TT3 dbg t=%u mst=%02x%02x cddat=%02x r_no0=%02x x=%d y=%d status=%08x\n",t,w[(actor+28)^1],w[(actor+29)^1],w[(actor+35)^1],w[(actor+36)^1],(int16_t)ram_word(ram,actor+8)>>16,(int16_t)(ram_word(ram,actor+12)>>16),status);
                if(tt_stage==0 && t>=300){tt_stage=1;tt_since=t;}
                if(tt_stage==1){
                    /* Past X 1144 (egg4air_04) beside the submarine's start (1232,852). */
                    HOLD(1150,852,0);
                    if(status && !tt_spawn){tt_spawn=t;screenshot("tt3-boss-spawn");}
                    if(tt_spawn && t>=tt_spawn+60){tt_stage=2;tt_since=t;}
                    if(t>tt_since+900){fprintf(stderr,"TT3 boss: egg4air never spawned\n");return exit2(__LINE__);}
                }else if(tt_stage==2){
                    if(status && (left?left:1)<tt_last){tt_hits+=tt_last-(left?left:1);tt_last=left?left:1;char name[32];snprintf(name,sizeof(name),"tt3-boss-hit-%u",tt_hits);screenshot(name);
                        printf("TT3 boss hit %u at t=%u audio_sample=%lu\n",tt_hits,t,(unsigned long)audio_samples);}
                    /* Trail about 60 pixels behind along the sub's own path (its route runs through
                       open corridors; a held Sonic inside terrain is crushed). egg4air_03 only moves
                       while Sonic is within 144 once it has been far. */
                    static int16_t trail[1024][2];static unsigned trail_n;
                    if(status){trail[trail_n%1024][0]=(int16_t)bx;trail[trail_n%1024][1]=(int16_t)by;trail_n++;}
                    static int fx=1150,fy=852; /* the start spot until the trail is 60 long */
                    /* The act wraps vertically at 2048 (SCR43C/D.C scrv_down_ch): egg4air's
                       escape runs 2176 -> 128, so compare Y modulo 2048 and hold Sonic behind it
                       on the sub's side of the wrap. */
                    for(unsigned k=1;k<1024 && k<trail_n;k++){const int16_t *q=trail[(trail_n-1-k)%1024];int dx=q[0]-bx,dy=((q[1]-by)%2048+3072)%2048-1024;
                        if(dx*dx+dy*dy>=3600 && dx*dx+dy*dy<20000){fx=q[0];fy=by+dy<0?by+dy+2048:by+dy;break;}}
                    if(status && left && t%45==0)HOLD(bx,by-20,1);else if(status)HOLD(fx,fy,0);
                    if(!status){tt_dive=t;tt_stage=3;tt_since=t;screenshot("tt3-boss-dive");}
                    if(getenv("SCD_TT3_DEBUG") && t>800 && tt_stage==2){fprintf(stderr,"TT3 boss: debug stop, %u of 4 hits, status %08x\n",tt_hits,status);return exit2(__LINE__);}
                    if(t>tt_since+9000){fprintf(stderr,"TT3 boss: %u of 4 hits, status %08x\n",tt_hits,status);return exit2(__LINE__);}
                }else if(tt_stage==3){
                    HOLD(2120,1370,0);
                    if(bossflag==4){tt_flag=t;tt_stage=4;tt_since=t;}
                    if(t>tt_since+600){fprintf(stderr,"TT3 boss: bossflag=%u at the exit\n",bossflag);return exit2(__LINE__);}
                }else if(tt_stage==4){
                    /* Into the arena (egg4 at 2736,1312 loads; egg4_scrset past X 2640). */
                    if(egg && !tt_egg){tt_egg=t;screenshot("tt3-egg4");}
                    if(egg && routine>=12 && routine<18 && t%40==0)HOLD(bx,by,1);else HOLD(2650,1440,0);
                    if(egg && routine>=18 && !tt_egg_hit){tt_egg_hit=t;screenshot("tt3-egg4-hit");printf("TT3 boss egg4 hit at t=%u audio_sample=%lu\n",t,(unsigned long)audio_samples);}
                    if(tt_egg_hit && !status){tt_defeat=t;tt_stage=5;tt_since=t;screenshot("tt3-boss-defeated");}
                    if(t>tt_since+6000){fprintf(stderr,"TT3 boss: egg4 status %08x\n",status);return exit2(__LINE__);}
                }else if(tt_stage==5){
                    /* The capsule (GOAL.C gene) stands at 3632,1352: land on it rolling. */
                    unsigned d=t-tt_since;
                    if(d<200 && d%40==0)HOLD(3632,1312,1);
                    if(d==200){tt_capsule=t;screenshot("tt3-capsule");}
                    if(d>200){tt_stage=6;tt_since=t;}
                }else if(tt_stage==6){
                    if(t==tt_since+600)screenshot("tt3-results");
                    if(zone!=want && act==0){
                        printf("TT3 boss probe passed: zone=%u era=%u spawn=%u hits=%u dive=%u bossflag_at=%u egg4=%u egg4_hit=%u defeated=%u capsule=%u next_zone=%u act=%u at=%u boss_music=%u\n",
                            want,want_era,tt_spawn,tt_hits,tt_dive,tt_flag,tt_egg,tt_egg_hit,tt_defeat,tt_capsule,zone,act,t,tt_boss_music);
                        screenshot("tt3-next-zone");
                        p_retro_unload_game();p_retro_deinit();return 0;
                    }
                    if(t>tt_since+4000){fprintf(stderr,"TT3 boss: no next zone after the capsule (zone %u act %u)\n",zone,act);return exit2(__LINE__);}
                }
                #undef HOLD
                #undef PUT8
                #undef PUT16
            }else if(phase==3 && getenv("SCD_WW3_BOSS_ACTWK")){
                /* R63C/D boss entry fixture. Move Sonic near the retail boss
                   placement, then read the linked BOSS_6.C actors and state. */
                static unsigned ww_entered,ww_attack,ww_hover,ww_retreat,ww_event,ww_meca,ww_doors,ww_plc_last_age;
                size_t actor=0x100000+(strtoul(getenv("SCD_WW3_BOSS_ACTWK"),NULL,16)&0xfffff);
                size_t flag_at=0x100000+(strtoul(getenv("SCD_WW3_BOSS_FLAG"),NULL,16)&0xfffff);
                if(world_mailbox+572>size || actor+128*68>size || flag_at>=size)return exit2(__LINE__);
                unsigned t=frame-play,zone=ram_word(ram,world_mailbox+568),act=ram_word(ram,world_mailbox+536);
                unsigned status=ram_word(ram,world_mailbox+556),routine=(status>>8)&255;
                unsigned bossflag=ram_word(ram,flag_at&~3u)>>(8*(3-(flag_at&3)))&255;
                uint8_t *w=(uint8_t *)ram;
                unsigned doors=0,meca=0,boss=0,timer=0;
                for(unsigned s=97;s<128;s++){
                    unsigned id=w[(actor+s*68)^1];
                    doors+=id==62;meca+=id==53 || id==54 || id==55;boss+=id==52;
                    if(id==52)timer=(unsigned)w[(actor+s*68+46)^1]|(unsigned)w[(actor+s*68+47)^1]<<8;
                }
                if(getenv("SCD_WW3_BOSS_FULL")){
                    /* The retail fight fixture: actwk[0] is driven; all boss actors run
                       from the linked R6 overlay. Native sprite_status is 68 bytes. */
                    static unsigned full_started,full_hits,full_last_hit,full_top,full_dead,full_escape,full_capsule,full_capsule_seen,full_capsule_x,full_capsule_y,full_last_phase=~0u,full_event_at[3];
                    unsigned floor=0,colino=0,bx=0,by=0,hit=0;
                    size_t boss_at=0;
                    for(unsigned s=97;s<128;s++)if(w[(actor+s*68)^1]==52){boss_at=actor+s*68;break;}
                    if(boss_at){
                        floor=w[(boss_at+49)^1];hit=w[(boss_at+61)^1];colino=w[(boss_at+33)^1];
                        /* xposi/yposi high words are the first native word of each union. */
                        {uint16_t v;memcpy(&v,w+boss_at+8,2);bx=v;memcpy(&v,w+boss_at+12,2);by=v;}
                    }
                    if(boss && routine>=2)full_started=1;
                    if(hit>full_last_hit)full_hits++;
                    full_last_hit=hit;
                    if(floor==3 && !full_top)full_top=t;
                    if(routine>=12 && !full_dead)full_dead=t;
                    if(routine>=18 && !full_escape)full_escape=t;
                    unsigned phase=(routine<<8)|floor;
                    if(phase!=full_last_phase){
                        printf("WW3 full: t=%u routine=%u floor=%u hits=%u boss=%u,%u colino=%u flag=%u status=%08x\n",
                               t,routine,floor,full_hits,bx,by,colino,bossflag,status);
                        if(routine==10 && (floor==1 || floor==2))full_event_at[floor]=t;
                        full_last_phase=phase;
                    }
                    for(unsigned level=1;level<=2;level++)if(full_event_at[level] && t==full_event_at[level]+200){
                        size_t bottom_at=0x100000+(strtoul(getenv("SCD_WW3_BOTTOM"),NULL,16)&0xfffff);
                        uint16_t bottom;if(bottom_at+2>size)return exit2(__LINE__);memcpy(&bottom,w+bottom_at,2);
                        printf("WW3 scroll: floor=%u bottom=%u\n",level,bottom);
                    }
                    if(full_escape && !full_capsule_seen)for(unsigned s=1;s<97;s++)if(w[(actor+s*68)^1]==21){
                        uint16_t cx,cy;memcpy(&cx,w+actor+s*68+8,2);memcpy(&cy,w+actor+s*68+12,2);
                        printf("WW3 full: live capsule at=%u x=%u y=%u slot=%u\n",t,cx,cy,s);
                        full_capsule_seen=1;full_capsule_x=cx;full_capsule_y=cy;break;
                    }
                    unsigned actphase=ram_word(ram,world_mailbox+104),goal=ram_word(ram,world_mailbox+124);
                    if(actphase && !full_capsule){full_capsule=t;printf("WW3 full: capsule at=%u phase=%u goal=%u\n",t,actphase,goal);screenshot("ww3-capsule");}
                    if(zone==5 && act==0 && full_hits>=4 && full_top && full_dead && full_escape && full_capsule){
                        printf("WW3 full probe passed: era=%u hits=%u top=%u dead=%u escape=%u capsule=%u next_zone=%u act=%u at=%u\n",
                               want_era,full_hits,full_top,full_dead,full_escape,full_capsule,zone,act,t);
                        screenshot("ww3-next-zone");p_retro_unload_game();p_retro_deinit();return 0;
                    }
                    if(zone!=4 || act!=2){fprintf(stderr,"WW3 full: left R63 early, zone=%u act=%u t=%u\n",zone,act,t);return exit2(__LINE__);}
                    button_mask=0;
                    #define WW_FPUT16(off,x) do{uint16_t v=(uint16_t)(x);memcpy(w+actor+(off),&v,2);}while(0)
                    #define WW_FPUT8(off,x) do{size_t a=actor+(off);w[a^1]=(uint8_t)(x);}while(0)
                    #define WW_FHOLD(x,y,roll) do{WW_FPUT16(8,x);WW_FPUT16(10,0);WW_FPUT16(12,y);WW_FPUT16(14,0);WW_FPUT16(16,0);WW_FPUT16(18,(roll)?256:0);WW_FPUT16(20,0);WW_FPUT8(35,(roll)?6:2);WW_FPUT8(28,(roll)?2:0);WW_FPUT16(52,120);}while(0)
                    {size_t rings=0x100000+(strtoul(getenv("SCD_WW3_RINGS"),NULL,16)&0xfffff);uint16_t v=50;if(rings+2>size)return exit2(__LINE__);memcpy(w+(rings&~(size_t)1),&v,2);}
                    if(t<120)WW_FHOLD(2480+t*3,1660,0);
                    else if(!full_started)WW_FHOLD(2700,1660,0);
                    else if(boss_at && routine<12){
                        unsigned y=floor==0?1660:floor==1?1148:636;
                        int hittable=colino && (routine==6 || (floor==3 && routine==10));
                        if(hittable && floor==3)WW_FHOLD(bx,by-20,1);
                        else if(hittable && t%40==0)WW_FHOLD(bx,by-20,1);
                        else if(hittable && t%40>=36)WW_FHOLD(bx-80,by,0);
                        else WW_FHOLD(2700,y,0);
                    }else if(boss_at && routine<16)WW_FHOLD(2700,636,0);
                    else if(full_capsule_seen && !full_capsule)WW_FHOLD(full_capsule_x,full_capsule_y-40,1);
                    else if(full_escape && t>=full_escape+120 && t<full_escape+500 && t%40==0)WW_FHOLD(3888,600,1);
                    else WW_FHOLD(t%2?3100:3090,636,0);
                    #undef WW_FHOLD
                    #undef WW_FPUT8
                    #undef WW_FPUT16
                    if(full_escape==t)screenshot("ww3-boss-escape");
                    if(t>8000){fprintf(stderr,"WW3 full: incomplete hits=%u top=%u dead=%u escape=%u capsule=%u phase=%u goal=%u\n",full_hits,full_top,full_dead,full_escape,full_capsule,actphase,goal);return exit2(__LINE__);}
                }else{
                if(zone!=4 || act!=2){fprintf(stderr,"WW3 boss: left R63 early, zone=%u act=%u t=%u\n",zone,act,t);return exit2(__LINE__);}
                if(t>=120){
                    uint16_t v;
                    #define WW_PUT16(off,x) do{v=(uint16_t)(x);memcpy(w+actor+(off),&v,2);}while(0)
                    WW_PUT16(8,2700);WW_PUT16(10,0);WW_PUT16(12,1408);WW_PUT16(14,0);
                    WW_PUT16(16,0);WW_PUT16(18,0);WW_PUT16(20,0);
                    WW_PUT16(52,120); /* Fixture protection while held inside the arena. */
                    #undef WW_PUT16
                }
                if(getenv("SCD_WW3_PLC_BITMAPS")){
                    size_t age_at=0x100000+(strtoul(getenv("SCD_WW3_PLC_AGE"),NULL,16)&0xfffff);
                    size_t applied_at=0x100000+(strtoul(getenv("SCD_WW3_PLC_APPLIED"),NULL,16)&0xfffff);
                    if(age_at+4>size || applied_at+4>size)return exit2(__LINE__);
                    unsigned age=ram_word(ram,age_at),applied=ram_word(ram,applied_at);
                    if(applied && applied!=ww_plc_last_age && applied<=(want_era==3?105u:106u)){
                        uint16_t (*read_vdp1)(uint32_t)=dlsym(core,"VDP1_Read16_DB");
                        if(!read_vdp1 || age!=applied || applied!=ww_plc_last_age+1)return exit2(__LINE__);
                        uint64_t hash=UINT64_C(14695981039346656037);
                        const char *item=getenv("SCD_WW3_PLC_BITMAPS");
                        while(*item){
                            char *next;unsigned offset=(unsigned)strtoul(item,&next,16);
                            if(next==item || *next!=':')return exit2(__LINE__);
                            item=next+1;unsigned bytes=(unsigned)strtoul(item,&next,16);
                            if(next==item || (bytes&1) || offset+bytes>0xf000)return exit2(__LINE__);
                            for(unsigned i=0;i<bytes;i+=2){
                                unsigned word=read_vdp1(0x71000u+offset+i);
                                hash=(hash^(word>>8))*UINT64_C(1099511628211);
                                hash=(hash^(word&255))*UINT64_C(1099511628211);
                            }
                            item=*next==','?next+1:next;
                            if(*next && *next!=',')return exit2(__LINE__);
                        }
                        printf("WW3 PLC: age=%u hash=%016llx\n",applied,(unsigned long long)hash);
                        ww_plc_last_age=applied;
                    }
                }
                if(bossflag%16==6 && !ww_entered){ww_entered=t;screenshot("ww3-boss-entry");}
                if(boss && routine==4 && !ww_attack){ww_attack=t;screenshot("ww3-boss-first-attack");}
                if(boss && routine==6 && !ww_hover)ww_hover=t;
                if(boss && routine==8 && !ww_retreat)ww_retreat=t;
                if(boss && routine==10 && !ww_event)ww_event=t;
                if(meca>ww_meca)ww_meca=meca;
                if(doors>ww_doors)ww_doors=doors;
                if(t%60==0 || (t>=120 && t<=140))printf("WW3 boss: t=%u px=%u py=%u player_frame=%u player_routine=%u boss=%u doors=%u meca=%u routine=%u timer=%u flag=%u status=%08x\n",t,ram_word(ram,world_mailbox+52),ram_word(ram,world_mailbox+72),ram_word(ram,world_mailbox+224),ram_word(ram,world_mailbox+88)>>16,boss,doors,meca,routine,timer,bossflag,status);
                if(ww_entered && ww_attack && ww_hover && ww_retreat && ww_event && ww_meca>=3 && ww_doors==6){
                    printf("WW3 boss probe passed: era=%u entry=%u attack=%u hover=%u retreat=%u event=%u meca=%u doors=%u\n",
                           want_era,ww_entered,ww_attack,ww_hover,ww_retreat,ww_event,ww_meca,ww_doors);
                    screenshot("ww3-boss-first-event");p_retro_unload_game();p_retro_deinit();return 0;
                }
                if(t>1200){fprintf(stderr,"WW3 boss: entry sequence incomplete at t=%u, entry=%u attack=%u event=%u doors=%u meca=%u\n",
                    t,ww_entered,ww_attack,ww_event,ww_doors,ww_meca);return exit2(__LINE__);}
                }
            }else if(phase==3 && getenv("SCD_QQ3_BOSS_ACTWK")){
                /* Quartz Quadrant Act 3 boss probe (tools/test_qq3_boss_emulator.py). A
                   fixture, not a route: it writes Sonic's position and roll state (actwk[0])
                   to reach and hit the machine, then drives the pad; the rest is read only.
                   BOSS_5.C: egg5meca1 (51) spawns egg5meca2 (52, colino 62, colicnt 2) and
                   egg5 (50). Two hits clear meca2's colino and it lowers onto the belt; the
                   belt speed (egg5belt +54, driven by Sonic's run, capped at 1488) grinds
                   meca2's +66 counter from 2400 to 0, which sets egg5 actfree[2] bit 4 and
                   egg5 escapes. The capsule (3888,640), results and Wacky Workbench Act 1
                   follow. Actor fields are TYPES.H SH-2 offsets; actfree words are the PC
                   little-endian pairs (src/scd_actor.h). */
                static unsigned qq_stage,qq_since,qq_spawn,qq_hits,qq_down,qq_grind_start,qq_grind_end,qq_defeat,qq_capsule,qq_boss_music;
                size_t actor=0x100000+(strtoul(getenv("SCD_QQ3_BOSS_ACTWK"),NULL,16)&0xfffff);
                size_t flag_at=0x100000+(strtoul(getenv("SCD_QQ3_BOSS_FLAG"),NULL,16)&0xfffff);
                if(world_mailbox+572>size || actor+128*68>size)return exit2(__LINE__);
                unsigned t=frame-play,zone=ram_word(ram,world_mailbox+568),act=ram_word(ram,world_mailbox+536);
                unsigned bossflag=ram_word(ram,flag_at&~3u)>>(8*(3-(flag_at&3)))&255;
                uint8_t *w=(uint8_t *)ram;
                #define PUT16(off,v) do{uint16_t v16=(uint16_t)(v);memcpy(w+actor+(off),&v16,2);}while(0)
                #define PUT8(off,v) do{uint16_t v16;size_t a=actor+(off);memcpy(&v16,w+(a&~(size_t)1),2);v16=(a&1)?(uint16_t)((v16&0xff00)|((v)&255)):(uint16_t)((v16&255)|((v)<<8));memcpy(w+(a&~(size_t)1),&v16,2);}while(0)
                #define HOLD(x,y,roll) do{PUT16(8,x);PUT16(10,0);PUT16(12,y);PUT16(14,0);PUT16(16,0);PUT16(18,(roll)?256:0);PUT16(20,0);PUT8(35,(roll)?6:2);PUT8(28,(roll)?2:0);}while(0)
                #define QQ_SLOT(id) ({size_t found_=0;for(unsigned s_=97;s_<128 && !found_;s_++)if(w[(actor+s_*68)^1]==(id))found_=actor+s_*68;found_;})
                #define QQ_B(a,off) ((unsigned)w[((a)+(off))^1])
                #define QQ_W(a,off) ({uint16_t v16_;memcpy(&v16_,w+(a)+(off),2);(int16_t)v16_;})
                #define QQ_PC(a,off) ((int16_t)(QQ_B(a,off)|QQ_B(a,(off)+1)<<8))
                button_mask=0;
                {size_t rings=0x100000+(strtoul(getenv("SCD_QQ3_RINGS"),NULL,16)&0xfffff);if(rings+2<=size){uint16_t v=50;memcpy(w+(rings&~(size_t)1),&v,2);}}
                size_t meca2=QQ_SLOT(52),egg5=QQ_SLOT(50);
                unsigned m_colino=meca2?QQ_B(meca2,33):0,m_colicnt=meca2?QQ_B(meca2,34):0,m_routine=meca2?QQ_B(meca2,37):0;
                int mx=meca2?QQ_W(meca2,8):0,my=meca2?QQ_W(meca2,12):0,grind=meca2?QQ_PC(meca2,66):0;
                unsigned escaped=egg5 && (QQ_B(egg5,48)&4);
                if(zone!=want && qq_stage<5){fprintf(stderr,"QQ3 boss: zone %u left early at update %u (stage %u)\n",zone,t,qq_stage);return exit2(__LINE__);}
                if(ram_word(ram,audio_mailbox+12)==ram_word(ram,audio_mailbox+20) && meca2 && !qq_boss_music)qq_boss_music=ram_word(ram,audio_mailbox+12);
                if(t%600==0){char name[32];snprintf(name,sizeof(name),"qq3-t%05u",t);screenshot(name);}
                if(t%30==0)printf("QQ3 boss: t=%u stage=%u meca2=%d,%d colino=%u colicnt=%u r_no0=%u grind=%d egg5=%u escaped=%u bossflag=%u zone=%u act=%u music=%u\n",
                    t,qq_stage,mx,my,m_colino,m_colicnt,m_routine,grind,egg5?1u:0u,escaped,bossflag,zone,act,ram_word(ram,audio_mailbox+12));
                if(qq_stage==0 && t>=300){qq_stage=1;qq_since=t;}
                if(qq_stage==1){
                    /* Past X 3424 (egg5meca1_scrset: bossstart) below egg5meca1's layout spot (3536,552). */
                    HOLD(3432,640,0);
                    if(meca2 && !qq_spawn){qq_spawn=t;screenshot("qq3-boss-spawn");}
                    if(qq_spawn && t>=qq_spawn+60){qq_stage=2;qq_since=t;}
                    if(t>qq_since+900){fprintf(stderr,"QQ3 boss: egg5meca2 never spawned\n");return exit2(__LINE__);}
                }else if(qq_stage==2){
                    unsigned hits=m_colino?2-(m_colicnt>2?2:m_colicnt):2;
                    if(meca2 && hits>qq_hits){qq_hits=hits;char name[32];snprintf(name,sizeof(name),"qq3-boss-hit-%u",qq_hits);screenshot(name);
                        printf("QQ3 boss hit %u at t=%u audio_sample=%lu\n",qq_hits,t,(unsigned long)audio_samples);}
                    /* Roll into the machine every 45 updates; stand clear between hits. */
                    if(meca2 && m_colino && t%45==0)HOLD(mx,my,1);else if(m_colino)HOLD(3432,640,0);
                    if(meca2 && !m_colino && m_routine>=4){qq_down=t;qq_stage=3;qq_since=t;HOLD(3440,640,0);screenshot("qq3-boss-lowered");}
                    if(!meca2){fprintf(stderr,"QQ3 boss: egg5meca2 vanished before its hits\n");return exit2(__LINE__);}
                    if(t>qq_since+6000){fprintf(stderr,"QQ3 boss: %u of 2 hits, colino %u colicnt %u\n",qq_hits,m_colino,m_colicnt);return exit2(__LINE__);}
                }else if(qq_stage==3){
                    /* On the belt: hold Right (pad input only) so Sonic's run drives the belt. */
                    button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT;
                    if(meca2 && grind<2400 && !qq_grind_start)qq_grind_start=t;
                    if(meca2)qq_grind_end=(unsigned)(grind<0?0:grind);
                    if(escaped){qq_defeat=t;qq_stage=4;qq_since=t;screenshot("qq3-boss-defeated");}
                    if(t>qq_since+12000){fprintf(stderr,"QQ3 boss: belt grind stalled at %d\n",grind);return exit2(__LINE__);}
                }else if(qq_stage==4){
                    /* The capsule (GOAL.C gene) stands at 3888,640: land on it rolling. */
                    unsigned d=t-qq_since;
                    if(d>=300 && d<500 && d%40==0)HOLD(3888,600,1);
                    if(d==500){qq_capsule=t;screenshot("qq3-capsule");}
                    if(d>500){qq_stage=5;qq_since=t;}
                }else if(qq_stage==5){
                    if(t==qq_since+600)screenshot("qq3-results");
                    if(zone!=want && act==0){
                        printf("QQ3 boss probe passed: zone=%u era=%u spawn=%u hits=%u lowered=%u grind_start=%u grind_left=%u defeated=%u capsule=%u next_zone=%u act=%u at=%u boss_music=%u\n",
                            want,want_era,qq_spawn,qq_hits,qq_down,qq_grind_start,qq_grind_end,qq_defeat,qq_capsule,zone,act,t,qq_boss_music);
                        screenshot("qq3-next-zone");
                        p_retro_unload_game();p_retro_deinit();return 0;
                    }
                    if(t>qq_since+4000){fprintf(stderr,"QQ3 boss: no next zone after the capsule (zone %u act %u)\n",zone,act);return exit2(__LINE__);}
                }
                #undef QQ_PC
                #undef QQ_W
                #undef QQ_B
                #undef QQ_SLOT
                #undef HOLD
                #undef PUT8
                #undef PUT16
            }else if(phase==3 && getenv("SCD_CC3_BOSS_ACTWK")){
                /* Collision Chaos Act 3 boss probe (tools/test_cc3_boss_emulator.py). A
                   fixture, not a route: it writes Sonic's position and roll state
                   (actwk[0], TYPES.H SH-2 offsets) to reach the boss, then only reads.
                   It requires the boss to spawn, take its three BOSS_3.C hits, raise
                   bossflag at the shaft top, then the capsule, results and next zone. */
                static unsigned cc3_stage,cc3_hits,cc3_since,cc3_spawn,cc3_defeat,cc3_flag,cc3_capsule,cc3_last_status,cc3_boss_music;
                size_t actor=0x100000+(strtoul(getenv("SCD_CC3_BOSS_ACTWK"),NULL,16)&0xfffff);
                size_t flag_at=0x100000+(strtoul(getenv("SCD_CC3_BOSS_FLAG"),NULL,16)&0xfffff);
                if(world_mailbox+572>size || actor+68>size)return exit2(__LINE__);
                unsigned t=frame-play,zone=ram_word(ram,world_mailbox+568),act=ram_word(ram,world_mailbox+536);
                unsigned position=ram_word(ram,world_mailbox+552),status=ram_word(ram,world_mailbox+556);
                unsigned bossflag=ram_word(ram,flag_at&~3u)>>(8*(3-(flag_at&3)))&255;
                int bx=(int16_t)(position>>16),by=(int16_t)position;
                uint8_t *w=(uint8_t *)ram;
                #define PUT16(off,v) do{uint16_t v16=(uint16_t)(v);memcpy(w+actor+(off),&v16,2);}while(0)
                #define PUT8(off,v) do{uint16_t v16;size_t a=actor+(off);memcpy(&v16,w+(a&~(size_t)1),2);v16=(a&1)?(uint16_t)((v16&0xff00)|((v)&255)):(uint16_t)((v16&255)|((v)<<8));memcpy(w+(a&~(size_t)1),&v16,2);}while(0)
                #define HOLD(x,y,roll) do{PUT16(8,x);PUT16(10,0);PUT16(12,y);PUT16(14,0);PUT16(16,0);PUT16(18,(roll)?256:0);PUT16(20,0);PUT8(35,(roll)?6:2);PUT8(28,(roll)?2:0);}while(0)
                button_mask=0;
                if(getenv("SCD_CC3_MUTE")){size_t m=0x100000+(strtoul(getenv("SCD_CC3_MUTE"),NULL,16)&0xfffff);if(m+4<=size)ram_put_word(w,m,172);}
                if(zone!=want && cc3_stage<5){fprintf(stderr,"CC3 boss: zone %u left early at update %u (stage %u)\n",zone,t,cc3_stage);return exit2(__LINE__);}
                if(ram_word(ram,audio_mailbox+12)==ram_word(ram,audio_mailbox+20) && status && !cc3_boss_music && cc3_stage>=1)cc3_boss_music=ram_word(ram,audio_mailbox+12);
                if(t%30==0)printf("CC3 boss: t=%u stage=%u status=%08x boss=%d,%d bossflag=%u zone=%u act=%u music=%u\n",t,cc3_stage,status,bx,by,bossflag,zone,act,ram_word(ram,audio_mailbox+12));
                if(cc3_stage==0 && t>=300){cc3_stage=1;cc3_since=t;}
                if(cc3_stage==1){
                    HOLD(900,560,0);
                    if(status && !cc3_spawn){cc3_spawn=t;screenshot("cc3-boss-spawn");}
                    if(cc3_spawn && t>=cc3_spawn+120){cc3_stage=2;cc3_since=t;}
                    if(t>cc3_since+900){fprintf(stderr,"CC3 boss: egg3dai_l never spawned\n");return exit2(__LINE__);}
                }else if(cc3_stage==2){
                    unsigned phase_hits=status&255;
                    if(phase_hits!=cc3_hits){cc3_hits=phase_hits;char name[32];snprintf(name,sizeof(name),"cc3-boss-hit-%u",cc3_hits);screenshot(name);
                        printf("CC3 boss hit %u at t=%u audio_sample=%lu\n",cc3_hits,t,(unsigned long)audio_samples);}
                    /* Wait 64 lines under the lift so the camera keeps it in view (actionsub marks it drawn). */
                    if(((status>>8)&255)==4 && t%60==0 && status)HOLD(bx,by-24,1);else HOLD(900,status?by+64:560,0);
                    if(cc3_hits==3 && ((status>>8)&255)>=8){cc3_stage=3;cc3_since=t;}
                    if(t>cc3_since+3600){fprintf(stderr,"CC3 boss: %u of 3 hits\n",cc3_hits);return exit2(__LINE__);}
                }else if(cc3_stage==3){
                    unsigned d=t-cc3_since;
                    if(d<120)HOLD(896,420,0);else if(d<240)HOLD(896,350,0);else HOLD(896,260,0);
                    if(bossflag==3 && !cc3_flag)cc3_flag=t;
                    if(cc3_flag && !status){cc3_defeat=t;screenshot("cc3-boss-defeated");cc3_stage=4;cc3_since=t;}
                    if(d>1200){fprintf(stderr,"CC3 boss: bossflag=%u status=%08x after the shaft\n",bossflag,status);return exit2(__LINE__);}
                }else if(cc3_stage==4){
                    /* The capsule (GOAL.C gene) stands at 1336,224: land on it rolling. */
                    unsigned d=t-cc3_since;
                    if(d<200 && d%40==0)HOLD(1336,184,1);
                    if(d==200){cc3_capsule=t;screenshot("cc3-capsule");}
                    if(d>200){cc3_stage=5;cc3_since=t;}
                }else if(cc3_stage==5){
                    if(t==cc3_since+600)screenshot("cc3-results");
                    if(zone!=want && act==0){
                        printf("CC3 boss probe passed: zone=%u era=%u spawn=%u hits=%u bossflag_at=%u defeated=%u capsule=%u next_zone=%u act=%u at=%u boss_music=%u\n",
                            want,want_era,cc3_spawn,cc3_hits,cc3_flag,cc3_defeat,cc3_capsule,zone,act,t,cc3_boss_music);
                        screenshot("cc3-next-zone");
                        p_retro_unload_game();p_retro_deinit();return 0;
                    }
                    if(t>cc3_since+4000){fprintf(stderr,"CC3 boss: no next zone after the capsule (zone %u act %u)\n",zone,act);return exit2(__LINE__);}
                }
                cc3_last_status=status;(void)cc3_last_status;
                #undef HOLD
                #undef PUT8
                #undef PUT16
            }else if(phase==3){
                if(world_mailbox+572>size){fprintf(stderr,"world mailbox out of range\n");return exit2(__LINE__);}
                unsigned zone=ram_word(ram,world_mailbox+568),active=ram_word(ram,world_mailbox+40),x=ram_word(ram,world_mailbox+52);
                /* A replayed pad trace may end the zone: its neutral tail then observes
                   the ordinary handoff into the next zone (tools/test_cc3_route.py). */
                if(zone!=want && frame>play+240 && !(route_pad_path && route_updates>=cc_pad_count)){fprintf(stderr,"Zone %u requested, zone %u loaded\n",want,zone);return exit2(__LINE__);}
                if(active>max_active)max_active=active;
                if(x>max_x)max_x=x;
                if(zone_music){
                    unsigned elapsed=frame-play,part=elapsed/1200,t=elapsed%1200;
                    if(part>3){part=3;t=elapsed-3600;}
                    unsigned expected=want?12+(want-1)*4+part:2+part;
                    unsigned requested=ram_word(ram,audio_mailbox+12),actual=ram_word(ram,audio_mailbox+20);
                    unsigned state=ram_word(ram,audio_mailbox+16),paused=ram_word(ram,audio_mailbox+8),fad=ram_word(ram,audio_mailbox+24);
                    zone_music_bucket=-1;button_mask=0;
                    if(part && t<4)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_Y;
                    if((t>=620 && t<624)||(t>=860 && t<864))button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_START;
                    if(t>=300 && t<600){
                        if(requested!=expected || actual!=expected || state!=3 || paused || ram_word(ram,world_mailbox+8)!=part){fprintf(stderr,"Wrong zone music: zone=%u era=%u requested=%u actual=%u state=%u paused=%u\n",want,part,requested,actual,state,paused);return exit2(__LINE__);}
                        zone_music_bucket=(int)part;
                    }
                    if(t==720){if(!paused)return exit2(__LINE__);music_pause_fad=fad;}
                    if(t>=720 && t<820)zone_music_bucket=4;
                    if(t==820 && (!paused || fad!=music_pause_fad))return exit2(__LINE__);
                    if(t==1050 && (paused || state!=3 || actual!=expected || fad<=music_pause_fad))return exit2(__LINE__);
                    if(part==3 && t>=1050){
                        if(music_previous_fad && fad+100<music_previous_fad && actual==expected && state==3)music_loop=1;
                        music_previous_fad=fad;
                    }
                    if(elapsed>=4800+loop_frames){
                        for(unsigned e=0;e<4;e++){
                            uint64_t n=zone_music_samples[e],mean=n?zone_music_energy[e]/n:0;
                            printf("Zone music: zone=%u era=%u track=%u samples=%llu mean_square=%llu peak=%u\n",want,e,want?12+(want-1)*4+e:e+2,(unsigned long long)n,(unsigned long long)mean,zone_music_peak[e]);
                            if(n<88200 || mean<10000 || zone_music_peak[e]>=32767)return exit2(__LINE__);
                        }
                        if(zone_music_energy[4] || zone_music_samples[4]<88200 || (loop_frames && !music_loop))return exit2(__LINE__);
                        printf("Zone music passed: zone=%u pause_resume=4 loop=%u\n",want,music_loop);
                        p_retro_unload_game();p_retro_deinit();return 0;
                    }
                    p_retro_run();continue;
                }
                if(art_at && !route_pad_path){
                    if(art_at+96>size){fprintf(stderr,"Zone art fixture bad mailbox\n");return exit2(__LINE__);}
                    button_mask=0;
                    if(frame>play+160){
                        unsigned generator_art=getenv("SCD_CC_GENERATOR_ART")!=NULL;
                        /* SCD_PPZ_OBJECT_ART=N: Palmtree Panic object atlas frames 0..N-1
                           (no zone art pack; src/zone_object_view.inc request 0xa7). */
                        const char *ppz_art=getenv("SCD_PPZ_OBJECT_ART");
                        /* SCD_ZONE_ART_FIGHT=1/2: R83C/D's fight/Amy bank first (request 0xa8/0xa9). */
                        static int fight_loaded;
                        /* The Amy bank is packed over the fight bank (PLC 5 follows PLC 4):
                           request 0xa8 first, then 0xa9. */
                        if(getenv("SCD_ZONE_ART_FIGHT") && !fight_loaded){
                            static unsigned fight_step=1;
                            unsigned target=(unsigned)atoi(getenv("SCD_ZONE_ART_FIGHT"));
                            uint32_t bank=(0xa7u+fight_step)<<24;
                            ram_put_word((uint8_t*)ram,art_at+36,bank);
                            if(ram_word(ram,art_at+40)==bank){if(fight_step<target)fight_step++;else fight_loaded=1;}
                            p_retro_run();continue;
                        }
                        unsigned count=ppz_art?(unsigned)atoi(ppz_art):generator_art?(want_era==1?6:2):ram_word(ram,art_at+20);
                        /* Up to SCD_ZONE_ART_MAX_FRAMES (512) records; the index's high byte
                           rides in request bits 16-23 (src/zone_object_view.inc). */
                        if(ram_word(ram,art_at)!=0x5a415254 || !count || count>512 ||
                           ram_word(ram,art_at+8)!=want || ram_word(ram,art_at+12)!=want_act || ram_word(ram,art_at+16)!=want_era)return exit2(__LINE__);
                        /* Four flips per frame need six updates per capture.
                           Allow eight each plus setup; larger art packs must
                           not exhaust the old fixed 3,000-update budget. */
                        /* Budget from the first answered capture, not from boot:
                           level entry time does not scale with count. The first
                           answer keeps the old fixed 3,000-update bound. */
                        if(!art_captures)art_start=frame;
                        if(frame>play+3000 && !art_captures)art_start=0;
                        if(!art_start || frame>art_start+40+count*4*8){fprintf(stderr,"Zone art fixture timeout: case=%u count=%u\n",art_case,count);return exit2(__LINE__);}
                        if(art_case==count*4){
                            uint16_t (*read_vdp1)(uint32_t)=dlsym(core,"VDP1_Read16_DB");if(!read_vdp1)return exit2(__LINE__);
                            char path[1024];snprintf(path,sizeof(path),"%s/zone-art-vdp1.bin",output_dir);
                            FILE *dump=fopen(path,"wb");if(!dump)return exit2(__LINE__);
                            for(unsigned word=0;word<0x40000;word++){uint16_t value=read_vdp1(word*2);fputc(value>>8,dump);fputc(value&255,dump);}
                            if(fclose(dump))return exit2(__LINE__);
                            printf("Zone art passed: zone=%u act=%u era=%u frames=%u captures=%u updates=%u\n",want,want_act,want_era,count,art_captures,ram_word(ram,mailbox+4));
                            p_retro_unload_game();p_retro_deinit();return 0;
                        }
                        unsigned request=(ppz_art?0xa7000000u:generator_art?0xa6000000u:0xa5000000u)|((art_case%4)<<8)|((art_case/4)&255)|(((art_case/4)>>8)<<16);
                        ram_put_word((uint8_t*)ram,art_at+36,request);
                        if(ram_word(ram,art_at+40)==request && ++art_wait>=5){
                            char name[40];snprintf(name,sizeof(name),"zone-art-%03u",art_case);screenshot(name);
                            printf("Zone art sprite: %u",art_case);
                            for(unsigned k=0;k<8;k++)printf(" %u",ram_word(ram,art_at+64+k*4));putchar('\n');
                            /* High-priority zone CLUT entries index CRAM 128..191.
                               Check the actual live alias, including palette DMA. */
                            uint16_t (*read_zone_vdp2)(uint32_t)=dlsym(core,"VDP2_Read16_DB");
                            if(!read_zone_vdp2)return exit2(__LINE__);
                            /* Palmtree Panic has no zone CLUTs on that alias (its high-priority
                               atlas CLUTs use the 0x4050 block; tools/check_object_vram.py). */
                            if(!ppz_art){
                                for(unsigned c=0;c<64;c++)if(read_zone_vdp2(0x100000+c*2)!=read_zone_vdp2(0x100100+c*2))return exit2(__LINE__);
                                printf("Zone priority palette: %u matched=64\n",art_case);
                            }
                            /* Live CRAM at the capture: cycled colours (TT water) differ
                               from the stage file (tools/check_zone_object_target.py). */
                            printf("Zone cram: %u",art_case);for(unsigned c=0;c<64;c++)printf(" %04x",read_zone_vdp2(0x100000+c*2));putchar('\n');
                            if(zone_cram_frames<2)return exit2(__LINE__);
                            printf("Zone sprite cram: %u",art_case);for(unsigned c=0;c<64;c++)printf(" %04x",zone_sprite_cram[c]);putchar('\n');
                            if(palette_at){
                                uint16_t (*read_vdp2)(uint32_t)=dlsym(core,"VDP2_Read16_DB");
                                if(!read_vdp2 || palette_at+4>size)return exit2(__LINE__);
                                printf("Zone palette: %u %u",art_case,ram_word(ram,palette_at));
                                for(unsigned c=0;c<64;c++)printf(" %04x",read_vdp2(0x100000+c*2));
                                putchar('\n');
                            }
                            art_case++;art_captures++;art_wait=0;
                        }
                    }
                    p_retro_run();continue;
                }
                if(route_retreat){
                    unsigned sequence=ram_word(ram,mailbox+4),flags=ram_word(ram,world_mailbox+64);
                    if(sequence!=route_seq){
                        if(route_updates && sequence!=route_seq+1){fprintf(stderr,"CC route lost a gameplay observation\n");return exit2(__LINE__);}
                        unsigned act=ram_word(ram,world_mailbox+536),era=ram_word(ram,world_mailbox+8);
                        unsigned stage=zone|(act<<8)|(era<<16);
                        if(route_updates && stage!=route_stage){route_transitions++;route_stuck=route_jumps=route_hold=route_back=route_runup=0;route_last_x=x;}
                        else if(route_updates && frame-route_last_frame>1)route_late++;
                        route_stage=stage;
                        route_last_frame=frame;route_seq=sequence;route_updates++;
                        if(zone==want && act==want_act && era==want_era &&
                           r5_event_at && r5_event_at+40<=size && ram_word(ram,r5_event_at)==0x52354556){
                            for(unsigned n=0;n<9;n++)route_r5_events[n]=ram_word(ram,r5_event_at+4+n*4);
                            route_r5_seen=1;
                            if(route_r5_trace_enabled&&(!route_r5_trace_seen||
                               route_r5_trace[0]!=route_r5_events[0]||route_r5_trace[5]!=route_r5_events[5]||
                               route_r5_trace[6]!=route_r5_events[6]||route_r5_trace[7]!=route_r5_events[7]||
                               route_r5_trace[8]!=route_r5_events[8])){
                                printf("CC r5 event trace: %u",sequence);
                                for(unsigned n=0;n<9;n++)printf(" %u",route_r5_events[n]);
                                putchar('\n');memcpy(route_r5_trace,route_r5_events,sizeof(route_r5_events));route_r5_trace_seen=1;
                            }
                        }
                        if(zone==want && act==want_act && era==want_era && bg_slave_at && bg_slave_at+44<=size){
                            /* SCD_BG_SLAVE_FORCE_TIMEOUT: word 10 makes the master skip the slave
                               notification (src/main.c), so every R5 redraw takes the timeout path. */
                            if(getenv("SCD_BG_SLAVE_FORCE_TIMEOUT"))ram_put_word((uint8_t *)ram,bg_slave_at+40,1);
                            for(unsigned n=0;n<10;n++)route_bg_slave[n]=ram_word(ram,bg_slave_at+n*4);
                            route_bg_slave_seen=1;
                        }
                        if(route_local){
                            /* Measure current movement, not distance from an
                               old high-water mark after a deliberate retreat. */
                            if(x>route_last_x+1 || x+1<route_last_x || route_back || route_runup)route_stuck=0;
                            else route_stuck++;
                            route_last_x=x;
                        }else if(x>route_last_x+1){route_stuck=0;route_last_x=x;}else route_stuck++;
                        route_buttons=1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT;
                        if(route_stuck>=30 && !(flags&2) && !route_back && !route_runup){
                            static const unsigned holds[]={1,20,10};
                            route_hold=holds[route_jumps%3];route_jumps++;route_stuck=0;
                            if(route_jumps%4==0){
                                route_back=route_retreat;route_hold=0;
                                route_backjump=route_near(route_backjump_at,route_backjump_count,x,64);
                            }
                        }
                        /* Optional observed takeoff point, still ordinary pad
                           input. Release outside the held-jump interval. */
                        if(route_jump_count && !route_hold && !route_back && !route_runup && !(flags&3) &&
                           route_near(route_jump_at,route_jump_count,x,16))route_hold=20;
                        if(route_back){
                            route_buttons=1u<<RETRO_DEVICE_ID_JOYPAD_LEFT;
                            /* Brake before jumping back toward an earlier
                               ledge, then turn right for a fresh approach. */
                            if(route_local && route_backjump && route_retreat>10 && route_back==route_retreat-10)route_hold=20;
                            if(route_local && route_hold){route_buttons|=1u<<RETRO_DEVICE_ID_JOYPAD_B;route_hold--;}
                            if(!--route_back){if(route_local)route_runup=20;else route_hold=20;}
                        }
                        else if(route_runup){if(!--route_runup)route_hold=20;}
                        else if(route_hold){route_buttons|=1u<<RETRO_DEVICE_ID_JOYPAD_B;route_hold--;}
                        if(route_pad_path){
                            if(route_updates<=cc_pad_count){
                                const cc_pad_state *expected=&cc_pad_states[route_updates-1];
                                /* The trace words (Sonic's x/y at this update, written before
                                   the sequence is published) stay consistent when an update
                                   overruns its vblank; the world mailbox fills after drawing. */
                                unsigned x=(uint32_t)((int32_t)ram_word(ram,mailbox+16)/65536);int y=(int32_t)ram_word(ram,mailbox+20)/65536; /* player.x/65536 truncation, as the host */
                                if(expected->sequence!=sequence || expected->x!=(int)x || expected->y!=y){
                                    fprintf(stderr,"CC pad mismatch: sequence=%u actual=%u,%d expected=%d,%d\n",sequence,x,y,expected->x,expected->y);
                                    if(getenv("SCD_TRACE_ACTWK")){size_t at=0x100000+(strtoul(getenv("SCD_TRACE_ACTWK"),NULL,16)&0xfffff);uint16_t h[12];memcpy(h,ram+at,sizeof(h));
                                        fprintf(stderr,"CC mismatch actwk: x=%04x.%04x y=%04x.%04x frame=%u",h[4],h[5],h[6],h[7],frame);
                                        if(getenv("SCD_TRACE_WORDS")){char copy[256];snprintf(copy,sizeof(copy),"%s",getenv("SCD_TRACE_WORDS"));
                                            for(char *s=strtok(copy,",");s;s=strtok(NULL,",")){size_t o=0x100000+(strtoul(s,NULL,16)&0xfffff);uint16_t v;memcpy(&v,ram+o,2);fprintf(stderr," %s=%d",s,(int16_t)v);}}
                                        fprintf(stderr,"\n");}
                                    return exit2(__LINE__);
                                }
                                route_buttons=expected->pad;
                            }else{
                                /* An explicit neutral tail observes the ordinary act
                                   transition after the recorded tally. No RAM writes. */
                                route_buttons=0;
                            }
                            unsigned warp=ram_word(ram,world_mailbox+28);
                            printf("CC warp: %u %u\n",sequence,warp);
                            printf("CC music: %u %u %u %u\n",sequence,ram_word(ram,audio_mailbox+12),ram_word(ram,audio_mailbox+20),ram_word(ram,audio_mailbox+16));
                            printf("CC results: %u %u %u %u\n",sequence,ram_word(ram,world_mailbox+104),ram_word(ram,world_mailbox+120),ram_word(ram,world_mailbox+128));
                            if(route_save){
                                if(route_save_at+48>size || ram_word(ram,route_save_at)!=0x53415645)return exit2(__LINE__);
                                printf("CC save: %u",sequence);for(unsigned n=1;n<10;n++)printf(" %u",ram_word(ram,route_save_at+n*4));putchar('\n');
                            }
                            if(warp==240){
                                char name[48];snprintf(name,sizeof(name),"cc-warp-departure-%u",route_arrival_count+1);screenshot(name);
                            }
                            unsigned arrivals=ram_word(ram,world_mailbox+16);
                            if(arrivals!=route_arrival_count){route_arrival_sequence=arrivals>route_arrival_count?sequence:0;route_arrival_count=arrivals;}
                            if(ram_word(ram,world_mailbox+12)==220){
                                char name[48];snprintf(name,sizeof(name),"cc-warp-white-%u",route_arrival_count+1);screenshot(name);
                            }
                            if(route_arrival_sequence && sequence==route_arrival_sequence+30){
                                char name[48];snprintf(name,sizeof(name),"cc-warp-arrival-%u",route_arrival_count);screenshot(name);
                            }
                            if(art_at && art_at+(16+96*8)*4<=size){
                                unsigned count=ram_word(ram,art_at+7*4);if(count>96)return exit2(__LINE__);
                                for(unsigned n=0;n<count;n++){
                                    size_t record=art_at+(16+n*8)*4;
                                    if(ram_word(ram,record)==86)printf("CC generator sprite: %u %u\n",sequence,ram_word(ram,record+4));
                                }
                            }
                            if(!route_generator_sequence && ram_word(ram,world_mailbox+24)){
                                route_generator_sequence=sequence;screenshot("cc-generator-hit");
                            }
                            if(route_generator_sequence && sequence==route_generator_sequence+60)screenshot("cc-generator-broken");
                        }
                        unsigned standing=ram_word(ram,world_mailbox+68);
                        if(standing==72)route_ridden++;
                        /* Diagnostic: SCD_TRACE_ACTWK=<_actwk hex> SCD_TRACE_RANGE=FIRST:LAST dumps
                           Sonic's actor (x/y 16.16, xspeed, mspeed, cddat, r_no0) plus the
                           optional SCD_TRACE_WORDS=<hex>,... 16-bit globals per observation. */
                        {static long actwk_addr=-1,first,last;static char words[256];
                         if(actwk_addr<0){const char *a=getenv("SCD_TRACE_ACTWK"),*r=getenv("SCD_TRACE_RANGE"),*w=getenv("SCD_TRACE_WORDS");
                            actwk_addr=a?(long)(0x100000+(strtoul(a,NULL,16)&0xfffff)):0;first=r?strtol(r,NULL,10):0;last=r&&strchr(r,':')?strtol(strchr(r,':')+1,NULL,10):0;
                            snprintf(words,sizeof(words),"%s",w?w:"");}
                         if(actwk_addr && (long)sequence>=first && (long)sequence<=last){
                            uint16_t h[34];memcpy(h,ram+actwk_addr,sizeof(h));
                            printf("CC actwk: %u x=%04x.%04x y=%04x.%04x xspeed=%d yspeed=%d mspeed=%d cddat=%u r_no0=%u",sequence,h[4],h[5],h[6],h[7],(int16_t)h[8],(int16_t)h[9],(int16_t)h[10],h[17]&255,h[18]&255);
                            char copy[256];snprintf(copy,sizeof(copy),"%s",words);
                            for(char *s=strtok(copy,",");s;s=strtok(NULL,",")){size_t o=0x100000+(strtoul(s,NULL,16)&0xfffff);uint16_t v;memcpy(&v,ram+o,2);printf(" %s=%d",s,(int16_t)v);}
                            printf("\n");}}
                        /* Diagnostic: with SCD_TRACE_ACTWK, SCD_ZONE_ACTORS=FIRST:LAST:FILE dumps
                           every field of each live actor slot (TYPES.H SH-2 offsets) in
                           tools/cc_campaign_search.c's CC_ROUTE_ACTORS column order. */
                        {static FILE *ad;static long af=-2,al;if(af==-2){const char *v=getenv("SCD_ZONE_ACTORS");af=-1;
                            if(v && getenv("SCD_TRACE_ACTWK") && strchr(v,':') && strchr(strchr(v,':')+1,':')){af=atol(v);al=atol(strchr(v,':')+1);ad=fopen(strchr(strchr(v,':')+1,':')+1,"w");}}
                         if(ad && (long)sequence>=af && (long)sequence<=al){
                            size_t base=0x100000+(strtoul(getenv("SCD_TRACE_ACTWK"),NULL,16)&0xfffff);
                            for(unsigned k=0;k<128;k++){uint16_t w[34];memcpy(w,ram+base+k*68,sizeof(w));
#define AB(o) ((unsigned)((w[(o)/2]>>(((o)&1)?0:8))&255))
                                if(!AB(0))continue;
                                fprintf(ad,"%u %u %02x %02x %04x %04x.%04x %04x.%04x %04x %04x %04x %02x %02x %02x %02x %02x %04x %02x %02x %02x %02x %02x %02x %02x %02x %02x %04x %04x %02x%02x ",
                                        sequence,k,AB(0),AB(1),w[1],w[4],w[5],w[6],w[7],w[8],w[9],w[10],AB(22),AB(23),AB(24),AB(25),AB(26),w[14],
                                        AB(30),AB(31),AB(32),AB(33),AB(34),AB(35),AB(36),AB(37),AB(38),w[20],w[21],AB(44),AB(45));
                                for(unsigned b=0;b<22;b++)fprintf(ad,"%02x",AB(46+b));
#undef AB
                                fputc('\n',ad);}
                            fflush(ad);}}
                        printf("CC route: %u %u %u %u %u %u %u %u %u %u %u %u\n",sequence,frame,(uint32_t)((int32_t)ram_word(ram,mailbox+16)/65536),(uint32_t)((int32_t)ram_word(ram,mailbox+20)/65536),flags,standing,ram_word(ram,world_mailbox+84),ram_word(ram,mailbox+88),route_buttons,zone,act,era);
                        /* SCD_ZONE_ROUTE_ART_MISS=KEYS,COUNTS (src/main.c scd_art_miss_mailbox and
                           scd_art_miss_counts): each new key with the update that first drew it,
                           and every 300 updates the counts (tools/test_art_misses.py). */
                        {const char *am=getenv("SCD_ZONE_ROUTE_ART_MISS");static unsigned am_seen;
                         if(am && strchr(am,',')){size_t keys=0x100000+(strtoul(am,NULL,16)&0xfffff),counts=0x100000+(strtoul(strchr(am,',')+1,NULL,16)&0xfffff);
                             unsigned n=ram_word(ram,keys)&255;
                             for(;am_seen<n && am_seen<16;am_seen++)printf("Art miss new: %u %08x\n",sequence,ram_word(ram,keys+4+am_seen*4));
                             if(sequence%300==0 || (ram_word(ram,keys)&256)){printf("Art miss counts: %u %u",sequence,ram_word(ram,keys));
                                 for(unsigned j=0;j<n;j++){uint16_t c;memcpy(&c,ram+counts+j*2,2);printf(" %08x:%u",ram_word(ram,keys+4+j*4),(unsigned)c);} /* native-endian words */
                                 printf("\n");}}}
                        /* Optional comma list of route updates to capture (route-<update>.ppm). */
                        {const char *shots=getenv("SCD_ZONE_ROUTE_SHOTS");
                         for(const char *s=shots;s && *s;){char *e;unsigned long n=strtoul(s,&e,10);if(e==s)break;
                             if(n==sequence){char name[32];snprintf(name,sizeof(name),"route-%u",sequence);screenshot(name);
                                 /* SCD_ZONE_ROUTE_PEEK=ADDR:WORDS prints that many work-RAM longs per shot. */
                                 const char *peek=getenv("SCD_ZONE_ROUTE_PEEK");
                                 /* A comma separates regions (ADDR:WORDS,ADDR:WORDS). */
                                 if(peek){printf("Route peek: %u",sequence);
                                     for(const char *q=peek;*q;){char *c;size_t at=0x100000+(strtoul(q,&c,16)&0xfffff);unsigned words=1;
                                         if(*c==':')words=strtoul(c+1,&c,10);
                                         for(unsigned w=0;w<words && at+w*4+4<=size;w++)printf(" %08x",ram_word(ram,at+w*4));
                                         printf(" |");q=*c==','?c+1:c;if(c==q && *c!=',')break;}
                                     printf("\n");}}
                             s=*e==','?e+1:e;}}
                        const char *profile_at=getenv("PPZ_PROFILE_AT");
                        if(act_profile && profile_at){
                            long target=strtol(profile_at,NULL,10);
                            const char *span_text=getenv("PPZ_PROFILE_SPAN");long span=span_text?strtol(span_text,NULL,10):3;
                            if((long)sequence>=target-span && (long)sequence<=target+span){
                                size_t at=0x100000+(strtoul(act_profile,NULL,16)&0xfffff);
                                if(at+4*4+64*32*4<=size && ram_word(ram,at)==0x46505246){
                                    unsigned published=ram_word(ram,at+4);
                                    size_t rec=at+(4+(published%64)*32)*4;
                                    printf("CC profile: route=%u published=%u player=%u start=%u",sequence,published,ram_word(ram,rec+4),ram_word(ram,rec+8));
                                    for(unsigned phase=0;phase<9;phase++)printf(" p%u=%u",phase,ram_word(ram,rec+(3+phase)*4));
                                    for(unsigned phase=0;phase<4;phase++)printf(" s%u=%u",phase,ram_word(ram,rec+(24+phase)*4));
                                    for(unsigned slot=0;slot<4;slot++)printf(" x%u=%u",slot,ram_word(ram,rec+(28+slot)*4));
                                    printf(" camera=%u,%u sprites=%u\n",ram_word(ram,rec+21*4),ram_word(ram,rec+22*4),ram_word(ram,rec+23*4));
                                }
                            }
                        }
                        printf("CC future: %u %u %u %u %u\n",sequence,ram_word(ram,world_mailbox+24),ram_word(ram,world_mailbox+12),ram_word(ram,world_mailbox+16),ram_word(ram,world_mailbox+116));
                        if(route_updates%600==0){char name[48];snprintf(name,sizeof(name),"cc-route-%05u",route_updates);screenshot(name);fflush(stdout);}
                        if(route_updates>=route_limit){
                            screenshot("cc-route-end");
                            printf("CC route ended: updates=%u max_x=%u platform_ridden=%u late_intervals=%u transitions=%u zone=%u act=%u era=%u\n",route_updates,max_x,route_ridden,route_late,route_transitions,zone,act,era);
                            if(route_bg_slave_seen)printf("CC bg slave: %u %u %u %u %u %u %u %u %d %u\n",route_bg_slave[0],route_bg_slave[1],route_bg_slave[2],route_bg_slave[3],route_bg_slave[4],route_bg_slave[5],route_bg_slave[6],route_bg_slave[7],(int32_t)route_bg_slave[8],route_bg_slave[9]);
                            else if(bg_slave_at && bg_slave_at+40<=size)printf("CC bg slave: %u %u %u %u %u %u %u %u %d %u\n",ram_word(ram,bg_slave_at),ram_word(ram,bg_slave_at+4),ram_word(ram,bg_slave_at+8),ram_word(ram,bg_slave_at+12),ram_word(ram,bg_slave_at+16),ram_word(ram,bg_slave_at+20),ram_word(ram,bg_slave_at+24),ram_word(ram,bg_slave_at+28),(int32_t)ram_word(ram,bg_slave_at+32),ram_word(ram,bg_slave_at+36));
                            if(world_mailbox && world_mailbox+576<=size)printf("CC vdp1 overruns: %u\n",ram_word(ram,world_mailbox+572));
                            if(route_r5_seen)printf("CC r5 events: %u %u %u %u %u %u %u %u %u\n",route_r5_events[0],route_r5_events[1],route_r5_events[2],route_r5_events[3],route_r5_events[4],route_r5_events[5],route_r5_events[6],route_r5_events[7],route_r5_events[8]);
                            else if(r5_event_at && r5_event_at+40<=size && ram_word(ram,r5_event_at)==0x52354556)printf("CC r5 events: %u %u %u %u %u %u %u %u %u\n",ram_word(ram,r5_event_at+4),ram_word(ram,r5_event_at+8),ram_word(ram,r5_event_at+12),ram_word(ram,r5_event_at+16),ram_word(ram,r5_event_at+20),ram_word(ram,r5_event_at+24),ram_word(ram,r5_event_at+28),ram_word(ram,r5_event_at+32),ram_word(ram,r5_event_at+36));
                            p_retro_unload_game();p_retro_deinit();return 0;
                        }
                    }
                    /* SCD_STALL_CPU=1: when player.frame (world mailbox [56]) stops changing for
                       300 frames, print both SH-2s' registers and write wram.bin once. */
                    if(getenv("SCD_STALL_CPU")){
                        static unsigned stall_last=~0u,stall_since,stall_done;
                        const uint8_t *sram=p_retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM);size_t ssize=p_retro_get_memory_size(RETRO_MEMORY_SYSTEM_RAM);
                        unsigned pf=sram && world_mailbox+57*4<=ssize?ram_word(sram,world_mailbox+56*4):0;
                        if(pf!=stall_last){stall_last=pf;stall_since=frame;}
                        else if(!stall_done && frame>stall_since+300 && pf){
                            stall_done=1;size_t bytes=p_retro_serialize_size();void *state=malloc(bytes);
                            if(state && p_retro_serialize(state,bytes)){char label[48];snprintf(label,sizeof(label),"STALL cpu pframe=%u",pf);cpu_dump(label,state,bytes);}
                            free(state);char path[4096];snprintf(path,sizeof(path),"%s/wram.bin",output_dir);
                            FILE *file=fopen(path,"wb");if(file){fwrite(sram,1,ssize,file);fclose(file);}
                        }
                    }
                    button_mask=route_buttons;p_retro_run();continue;
                }
                button_mask=frame>play+200?1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT:0;
                if(frame==play+300){char name[40];snprintf(name,sizeof(name),"zones-%u-start",want);screenshot(name);}
                /* SCD_ZONES_TRACE: player state and a capture every 60 frames. */
                if(getenv("SCD_ZONES_CPU") && ((frame-play)%97==0 || (frame-play>=600 && frame-play<606))){
                    size_t bytes=p_retro_serialize_size();void *state=malloc(bytes);
                    if(state && p_retro_serialize(state,bytes)){char label[40];snprintf(label,sizeof(label),"cpu t=%u",frame-play);cpu_dump(label,state,bytes);}
                    if(state && frame-play==600){
                        char path[4096];snprintf(path,sizeof(path),"%s/wram.bin",output_dir);
                        FILE *file=fopen(path,"wb");if(file){fwrite(ram,1,size,file);fclose(file);}
                        snprintf(path,sizeof(path),"%s/zone.state",output_dir);
                        file=fopen(path,"wb");if(file){fwrite(state,1,bytes,file);fclose(file);}
                    }
                    free(state);
                }
                if(getenv("SCD_ZONES_TRACE") && (frame-play)%60==0){
                    char name[40];snprintf(name,sizeof(name),"zones-%u-t%04u",want,frame-play);screenshot(name);
                    printf("t=%u seq=%u x=%u y=%u flags=%x routine/lives=%08x active=%u\n",frame-play,ram_word(ram,mailbox+4),x,ram_word(ram,world_mailbox+72),
                        ram_word(ram,world_mailbox+64),ram_word(ram,world_mailbox+88),active);fflush(stdout);
                }
                if(frame>=play+1100){
                    char name[40];snprintf(name,sizeof(name),"zones-%u-run",want);screenshot(name);
                    /* Gameplay updates since entry. A frozen game (the zone
                       object freeze stopped at 1) fails even with objects
                       spawned; a 240-frame time warp still leaves over 600. */
                    unsigned updates=ram_word(ram,mailbox+4);
                    printf("Zone %u: loaded zone %u, most active objects %u, max x %u, %u updates, entered after %u frames\n",want,zone,max_active,max_x,updates,play);
                    if(getenv("SCD_SFX_BANK_MAILBOX")){size_t at=0x100000+(strtoul(getenv("SCD_SFX_BANK_MAILBOX"),NULL,16)&0xfffff);
                        if(at+16<=size)printf("SFX bank: magic %08x loads %u last_load_vblanks %u bank %d\n",ram_word(ram,at),ram_word(ram,at+4),ram_word(ram,at+8),(int)ram_word(ram,at+12)-1);}
                    if(updates<300)fprintf(stderr,"Zone %u: only %u gameplay updates in 1100 frames\n",want,updates);
                    p_retro_unload_game();p_retro_deinit();
                    return zone==want && max_active>0 && updates>=300?0:2;
                }
            }
            p_retro_run();
        }
        {
            const uint8_t *ram=p_retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM);
            size_t size=p_retro_get_memory_size(RETRO_MEMORY_SYSTEM_RAM);
            unsigned magic=ram && mailbox+12<=size?ram_word(ram,mailbox):0;
            unsigned sequence=ram && mailbox+8<=size?ram_word(ram,mailbox+4):0;
            unsigned zone=ram && world_mailbox+572<=size?ram_word(ram,world_mailbox+568):0;
            unsigned act=ram && world_mailbox+572<=size?ram_word(ram,world_mailbox+536):0;
            unsigned era=ram && world_mailbox+572<=size?ram_word(ram,world_mailbox+8):0;
            unsigned x=ram && world_mailbox+572<=size?ram_word(ram,world_mailbox+52):0;
            unsigned y=ram && world_mailbox+572<=size?ram_word(ram,world_mailbox+72):0;
            unsigned active=ram && world_mailbox+572<=size?ram_word(ram,world_mailbox+40):0;
            unsigned overlay=ram && object_fault_at && object_fault_at+4<=size?ram_word(ram,object_fault_at):0;
            fprintf(stderr,"Zone %u: zones timeout frame=%u phase=%u magic=%08x play=%u seq=%u route_updates=%u last_update_frame=%u zone=%u act=%u era=%u x=%u y=%u active=%u overlay=%08x\n",
                    want,frame,phase,magic,play,sequence,route_updates,route_last_frame,zone,act,era,x,y,active,overlay);
            const char *art_text=getenv("SCD_ZONE_ART_MAILBOX");
            if(art_text && ram){
                size_t art=0x100000+(strtoul(art_text,NULL,16)&0xfffff);
                if(art+16*4<=size)fprintf(stderr,"Zone art at timeout: magic=%08x miss=%08x type=%u subtype=%u frame=%u xy=%08x\n",
                    ram_word(ram,art),ram_word(ram,art+11*4),ram_word(ram,art+12*4),
                    ram_word(ram,art+13*4),ram_word(ram,art+14*4),ram_word(ram,art+15*4));
            }
        }
        return exit2(__LINE__);
    }
    if(journey_only){int result=journey_run(mailbox,world_mailbox,trace,p_retro_get_memory_data,p_retro_get_memory_size,p_retro_run);p_retro_unload_game();p_retro_deinit();return result;}
    /* title: replay a retail title pad script (tools/title_retail.py) by vintCounter and record the
       title mailbox, CRC32s of the program's Mega Drive state and of the picture every frame. */
    if(title_only){
        const char *address=getenv("SCD_TITLE_MAILBOX"),*routes=getenv("SCD_TITLE_ROUTES"),*lead_text=getenv("SCD_TITLE_PAD_LEAD"),*shots=getenv("SCD_TITLE_SHOTS");
        if(!address || !routes)return exit2(__LINE__);
        size_t box=0x100000+(strtoul(address,NULL,16)&0xfffff);unsigned lead=lead_text?strtoul(lead_text,NULL,10):1;
        static unsigned pads[4000];char path[4096];snprintf(path,sizeof(path),"%s/newgame.pad",routes);
        FILE *file=fopen(path,"r");if(!file){perror(path);return exit2(__LINE__);}
        unsigned v,pad,last=0,value=0;
        while(fscanf(file,"%u %u",&v,&pad)==2){if(v>=4000)return exit2(__LINE__);for(unsigned i=last;i<v;i++)pads[i]=value;last=v;value=pad;}
        for(unsigned i=last;i<4000;i++)pads[i]=value;
        fclose(file);
        unsigned wanted[64],wanted_count=0,shot_at[64]={0};
        for(const char *p=shots;p && *p && wanted_count<64;){wanted[wanted_count++]=strtoul(p,(char **)&p,10);if(*p==',')p++;}
        snprintf(path,sizeof(path),"%s/title-frames.txt",output_dir);FILE *rows=fopen(path,"w");if(!rows)return exit2(__LINE__);
        snprintf(path,sizeof(path),"%s/title-pixels.bin",output_dir);FILE *pixels=fopen(path,"wb");if(!pixels)return exit2(__LINE__);
        unsigned seen=0,done_frame=0,act1_frame=0,previous_v=~0u;
        /* SCD_TITLE_REENTRY=base:bytes (hex): after the game-over return, play
           NEW GAME again and require the VDP1 object atlas at the second Act 1
           entry to equal the first (the title must not clobber it). */
        const char *reentry=getenv("SCD_TITLE_REENTRY");unsigned atlas_base=0,atlas_bytes=0,entry=0,act1_base=0;
        static uint16_t atlas_first[0x30000];uint16_t (*vdp1_read)(uint32_t)=NULL;
        if(reentry){
            atlas_base=strtoul(reentry,(char **)&reentry,16);if(*reentry==':')atlas_bytes=strtoul(reentry+1,NULL,16);
            vdp1_read=(uint16_t (*)(uint32_t))dlsym(core,"VDP1_Read16_DB");
            if(!vdp1_read || !atlas_bytes || atlas_bytes/2>sizeof(atlas_first)/2)return exit2(__LINE__);
        }
        for(frame=0;frame<18000;frame++){
            const uint8_t *ram=p_retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM);size_t size=p_retro_get_memory_size(RETRO_MEMORY_SYSTEM_RAM);
            int title=ram && box+112<=size && ram_word(ram,box)==0x5449544c;
            button_mask=0;
            if(act1_frame && frame>=act1_frame+60 && frame<act1_frame+64)button_mask=(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT)|(1u<<RETRO_DEVICE_ID_JOYPAD_R);
            else if(title && !done_frame){
                unsigned md=pads[ram_word(ram,box+4)+lead<4000?ram_word(ram,box+4)+lead:3999];
                button_mask=(md&1?1u<<RETRO_DEVICE_ID_JOYPAD_UP:0)|(md&2?1u<<RETRO_DEVICE_ID_JOYPAD_DOWN:0)|(md&4?1u<<RETRO_DEVICE_ID_JOYPAD_LEFT:0)|(md&8?1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT:0)|
                    (md&16?1u<<RETRO_DEVICE_ID_JOYPAD_A:0)|(md&32?1u<<RETRO_DEVICE_ID_JOYPAD_R:0)|(md&64?1u<<RETRO_DEVICE_ID_JOYPAD_B:0)|(md&128?1u<<RETRO_DEVICE_ID_JOYPAD_START:0);
            }
            p_retro_run();
            ram=p_retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM);size=p_retro_get_memory_size(RETRO_MEMORY_SYSTEM_RAM);
            title=ram && box+112<=size && ram_word(ram,box)==0x5449544c;
            for(unsigned i=0;i<wanted_count;i++)if(shot_at[i] && shot_at[i]==frame){char name[32];snprintf(name,sizeof(name),"title-v%u",wanted[i]);screenshot(name);shot_at[i]=~0u;}
            /* SCD_TITLE_FRAMES: extra diagnostic captures at listed emulator frames. */
            for(const char *p=getenv("SCD_TITLE_FRAMES");p && *p;){unsigned f=strtoul(p,(char **)&p,10);if(*p==',')p++;if(f==frame){char name[32];snprintf(name,sizeof(name),"frame-%u",f);screenshot(name);}}
            if(done_frame){
                /* Act 1 after NEW GAME; then the game over fixture (Start+Right+C: one life, no rings,
                   hurt) must fade out and run the title screen again. */
                /* The trace sequence never resets, so the second entry counts its 60 frames
                   from the first gameplay sequence it publishes. */
                if(entry && !act1_frame && !act1_base && ram && mailbox+8<=size && ram_word(ram,mailbox)==0x53434432)act1_base=ram_word(ram,mailbox+4);
                if(!act1_frame && ram && mailbox+8<=size && ram_word(ram,mailbox)==0x53434432 && ram_word(ram,mailbox+4)>=act1_base+60){
                    act1_frame=frame;screenshot(entry?"title-act1-second":"title-act1");
                    printf("Title: handed over after %u frames; Act 1 running %u frames later\n",done_frame,frame-done_frame);fflush(stdout);
                    if(reentry){
                        unsigned bad=0,first=0;
                        for(unsigned i=0;i<atlas_bytes/2;i++){uint16_t w=vdp1_read(atlas_base+i*2);if(!entry)atlas_first[i]=w;else if(w!=atlas_first[i]){if(!bad)first=i;bad++;}}
                        /* Keep the first entry's picture for the masked compare below. */
                        static unsigned char act1_rgb[352*256*3];static unsigned act1_w,act1_h;
                        if(!entry){
                            act1_w=last_width;act1_h=last_height;
                            if(act1_w>352 || act1_h>256)return exit2(__LINE__);
                            for(unsigned y=0;y<act1_h;y++)for(unsigned x=0;x<act1_w;x++)frame_rgb(x,y,act1_rgb+(y*act1_w+x)*3);
                        }
                        if(entry){
                            /* The same act at the same act frame: Sonic, the title card and the HUD must
                               match, except the zero-rings flash of the RINGS label (x 22-59, y 41-50).
                               That toggles on a global V-INT phase (src/hud_animation.h, ObjHUD), so a
                               different load time before the second entry can show the other colour.
                               Inside the box a difference must be exactly yellow (248,248,0) against red
                               (248,32,0); anything else there is a HUD defect. */
                            unsigned diff=0,flash=0;
                            if(last_width!=act1_w || last_height!=act1_h){fprintf(stderr,"Re-entry: Act 1 picture size differs\n");return exit2(__LINE__);}
                            for(unsigned y=0;y<act1_h;y++)for(unsigned x=0;x<act1_w;x++){
                                unsigned char now[3];frame_rgb(x,y,now);const unsigned char *was=act1_rgb+(y*act1_w+x)*3;
                                if(!memcmp(now,was,3))continue;
                                const int yellow_now=now[0]==248 && now[1]==248 && now[2]==0,red_now=now[0]==248 && now[1]==32 && now[2]==0;
                                const int yellow_was=was[0]==248 && was[1]==248 && was[2]==0,red_was=was[0]==248 && was[1]==32 && was[2]==0;
                                if(x>=22 && x<=59 && y>=41 && y<=50 && ((yellow_now && red_was) || (red_now && yellow_was))){flash++;continue;}
                                if(!diff)fprintf(stderr,"Re-entry: Act 1 picture differs at %u,%u (%u,%u,%u was %u,%u,%u)\n",x,y,now[0],now[1],now[2],was[0],was[1],was[2]);
                                diff++;
                            }
                            if(diff){fprintf(stderr,"Re-entry: Act 1 picture differs from the first entry in %u pixels\n",diff);return exit2(__LINE__);}
                            printf("Re-entry: Act 1 picture equal to the first entry (%u RINGS-flash pixels masked)\n",flash);
                            printf("Re-entry: object atlas %u/%u words equal to the first entry\n",atlas_bytes/2-bad,atlas_bytes/2);
                            if(bad){fprintf(stderr,"Object atlas differs at VDP1 %05x\n",atlas_base+first*2);return exit2(__LINE__);}
                            fclose(rows);fclose(pixels);p_retro_unload_game();p_retro_deinit();return 0;
                        }
                    }
                }
                if(act1_frame && frame==act1_frame+360)screenshot("title-gameover");
                if(act1_frame && title && ram_word(ram,box+4)>=150){
                    screenshot(entry?"title-return-second":"title-return");
                    printf("Game over: title screen returned %u frames after the fixture\n",frame-act1_frame-60);
                    if(reentry && !entry){entry=1;done_frame=act1_frame=seen=0;previous_v=~0u;continue;}
                    fclose(rows);fclose(pixels);p_retro_unload_game();p_retro_deinit();return 0;
                }
                if(act1_frame && frame>act1_frame+3000){fprintf(stderr,"Game over did not return to the title screen\n");return exit2(__LINE__);}
                continue;
            }
            if(!title){
                if(seen)done_frame=frame;
                continue;
            }
            seen=1;
            /* Mailbox words (src/title_view.inc): [1] v, [2] state, [3] timer, [4] routine, [5] camera Y, [6] pad,
               [7] lag, [8] state address, [11] exit code, [14..18] offsets of vram, cram, hscroll, sat, palette. */
            v=ram_word(ram,box+4);
            if(v==120 && previous_v!=120){
                size_t bytes=p_retro_serialize_size();void *state=malloc(bytes);
                if(!state || !p_retro_serialize(state,bytes)){fprintf(stderr,"Title state capture failed\n");return exit2(__LINE__);}
                char path[1024];snprintf(path,sizeof(path),"%s/title-v120.state",output_dir);
                FILE *file=fopen(path,"wb");if(!file)return exit2(__LINE__);
                if(fwrite(state,1,bytes,file)!=bytes || fclose(file)){fprintf(stderr,"Title state write failed\n");return exit2(__LINE__);}
                free(state);
            }
            if(getenv("SCD_TITLE_UPLOADS") && v>=75 && v<=90)
                printf("Title textures: frame=%u v=%u uploads=%u sprites=%u present_blanks=%u\n",frame,v,ram_word(ram,box+48),ram_word(ram,box+52),ram_word(ram,box+104));
            uint32_t base=ram_word(ram,box+32),vram=base+ram_word(ram,box+56);
            if(v!=previous_v)for(unsigned i=0;i<wanted_count;i++)if(wanted[i]==v && !shot_at[i])shot_at[i]=frame+2;
            previous_v=v;
            bool valid;title_pixels=pixels;uint32_t picture=game_crc(5,320,0,224,&valid);title_pixels=NULL;
            fprintf(rows,"%u %u %08x %u %u %u %u %u %u %08x %08x %08x %08x %08x %08x %08x %08x %08x %u %u %u %u\n",frame,v,ram_word(ram,box+8),ram_word(ram,box+12),ram_word(ram,box+16),
                ram_word(ram,box+20),ram_word(ram,box+24),ram_word(ram,box+28),ram_word(ram,box+44),
                game_crc32(ram,size,base+ram_word(ram,box+60),128),game_crc32(ram,size,base+ram_word(ram,box+64),896),game_crc32(ram,size,base+ram_word(ram,box+68),640),
                game_crc32(ram,size,base+ram_word(ram,box+72),128),game_crc32(ram,size,vram+0xC000,0x1000),game_crc32(ram,size,vram+0xE000,0x1000),
                game_crc32(ram,size,vram,0xC000),game_crc32(ram,size,vram+0x20,0x6000),picture,valid,ram_word(ram,box+96),ram_word(ram,box+100),ram_word(ram,box+104));
        }
        fprintf(stderr,"Title route did not hand over\n");return exit2(__LINE__);
    }
    /* Ordinary rendering/audio/fixture scripts begin after actual gameplay is
       ready. The act route must retain every first-spawn trace record instead. */
    if(!act_only && !(game_only && getenv("SCD_SPECIAL_ATTRACT"))){
        for(;;){
            const uint8_t *ram=p_retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM);
            if(ram && mailbox+8<=p_retro_get_memory_size(RETRO_MEMORY_SYSTEM_RAM) && ram_word(ram,mailbox)==0x53434432 && ram_word(ram,mailbox+4)>=2)break;
            if(++boot_wait>1800){fprintf(stderr,"Gameplay readiness timed out\n");return exit2(__LINE__);}
            p_retro_run();
        }
    }
    printf("Boot warmup frames: %u\n",200+boot_wait);fflush(stdout);
    /* CD stage packs read at boot (src/stage_packs.h): VBlanks spent, bytes and failed pack. */
    {const char *packs=getenv("SCD_STAGE_PACKS");const uint8_t *ram=p_retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM);
     if(packs && ram){size_t at=0x100000+(strtoul(packs,NULL,16)&0xfffff);printf("Stage packs: magic=%08x vblanks=%u bytes=%u error=%u\n",ram_word(ram,at),ram_word(ram,at+4),ram_word(ram,at+8),ram_word(ram,at+12));}}
    unsigned game_route=0,game_start=1300,game_done[GAME_ROUTES]={0},game_seen_active=0,game_lead=2,game_records=0;size_t game_mailbox=0;
    if(bigring_only && !world_address)return exit2(__LINE__);
    if(game_only || bigring_only){const char *value=getenv("SCD_SPECIAL_GAME");const char *routes=getenv("SCD_SPECIAL_ROUTES");if(!value || !routes)return exit2(__LINE__);game_mailbox=0x100000+(strtoul(value,NULL,16)&0xfffff);game_load_pads(routes);value=getenv("SCD_SPECIAL_PAD_LEAD");if(value)game_lead=strtoul(value,NULL,10);}
    /* act2eras: Start+C loads Act 2 Present, then X (libretro Y) cycles to the past, good
       future and bad future; each era is captured 240 frames after its load. */
    /* act2travel: Start+C loads Act 2 Present, Start+C again places the travel fixture on
       the room floor. SCD_ACT2_TRAVEL_CASE=past walks left over the past post into the
       tube; future walks right over both posts, then left. Right is held after that. */
    if(travel_only){
        const char *which=getenv("SCD_ACT2_TRAVEL_CASE");int future=which && !strcmp(which,"future");
        unsigned cutscene=0,arrival=0;
        for(frame=0;frame<4000;frame++){
            button_mask=0;
            if(frame>=60 && frame<64)button_mask=(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_R);
            if(frame>=600 && frame<604)button_mask=(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_R);
            unsigned t=frame>=760?frame-760:0;
            if(frame>=760){
                if(future)button_mask=t<30?1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT:t<150?1u<<RETRO_DEVICE_ID_JOYPAD_LEFT:1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT;
                else button_mask=t<120?1u<<RETRO_DEVICE_ID_JOYPAD_LEFT:1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT;
            }
            p_retro_run();
            const uint8_t *ram=p_retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM);
            if(!ram || world_mailbox+548>p_retro_get_memory_size(RETRO_MEMORY_SYSTEM_RAM))return exit2(__LINE__);
            unsigned warp=ram_word(ram,world_mailbox+28),transitions=ram_word(ram,world_mailbox+16);
            if(getenv("SCD_ACT2_TRAVEL_DEBUG") && frame>=560 && frame%40==0)fprintf(stderr,"travel frame=%u x=%u y=%u ticks=%u warp=%u era=%u act=%u seq=%u routine=%x buttons=%u flags=%x\n",frame,ram_word(ram,world_mailbox+52),ram_word(ram,world_mailbox+72),ram_word(ram,world_mailbox+12),warp,ram_word(ram,world_mailbox+8),ram_word(ram,world_mailbox+536),ram_word(ram,mailbox+4),ram_word(ram,world_mailbox+88),ram_word(ram,mailbox+88),ram_word(ram,world_mailbox+64));
            if(getenv("SCD_ACT2_TRAVEL_DEBUG") && frame==700)screenshot("act2-travel-fixture");
            if(frame>=760 && warp && warp<180 && !cutscene){cutscene=frame;screenshot(future?"act2-travel-future-cutscene":"act2-travel-past-cutscene");}
            if(cutscene && transitions==1 && !arrival)arrival=frame;
            if(arrival && frame==arrival+60){
                screenshot(future?"act2-travel-future-arrival":"act2-travel-past-arrival");
                printf("Act 2 travel: case=%s era=%u transitions=%u x=%u y=%u rings=%u\n",future?"future":"past",ram_word(ram,world_mailbox+8),transitions,ram_word(ram,world_mailbox+52),ram_word(ram,world_mailbox+72),ram_word(ram,world_mailbox+128));
                p_retro_unload_game();p_retro_deinit();return 0;
            }
        }
        fprintf(stderr,"Act 2 travel did not arrive (cutscene=%u)\n",cutscene);return exit2(__LINE__);
    }
    if(eras_only){
        for(frame=0;frame<1500;frame++){
            button_mask=frame>=60 && frame<64?(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_R):0;
            if((frame>=400 && frame<404) || (frame>=740 && frame<744) || (frame>=1080 && frame<1084))button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_Y;
            p_retro_run();
            if(frame==340 || frame==680 || frame==1020 || frame==1360){char name[32];snprintf(name,sizeof(name),"act2-era-%u",frame==340?0:frame==680?1:frame==1020?2:3);screenshot(name);}
        }
        p_retro_unload_game();p_retro_deinit();return 0;
    }
    for(frame=0;frame<(bigring_only?9000u:game_only?(getenv("SCD_SPECIAL_FRAMES")?(unsigned)strtoul(getenv("SCD_SPECIAL_FRAMES"),NULL,10):game_default_routes?16500u:10000u*game_route_count):special_only?17200u:eras_only?1500u:sequence_only?26000u:act_only?12000u:act3_only?16000u:act2_only?15000u:world_only?25700u:diagnostic_only?1700u:audio_only?22000u:21000u);frame++) {
        button_mask=0;
        /* Saturn A/B map to libretro B/A (Beetle input.c input_map_pad). */
        if(frame>=640 && frame<850)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT;
        if(frame>=810 && frame<835)button_mask|=1u<<RETRO_DEVICE_ID_JOYPAD_B;
        if(frame>=850 && frame<854)button_mask=(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_Y);
        if(frame>=865 && frame<930)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_DOWN;
        if(frame>=865 && frame<869)button_mask|=1u<<RETRO_DEVICE_ID_JOYPAD_B;
        if(frame>=950 && frame<954)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_L; /* Z: camera */
        if(frame>=1900 && frame<1904)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_R2; /* R: replay */
        if(frame>=1000 && frame<1120)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT;
        if((frame>=1150 && frame<1154) || (frame>=1250 && frame<1254) || (frame>=1350 && frame<1354))button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_Y;
        if(frame>=1450 && frame<1454)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_X;
        if(frame>=1700 && frame<1704)button_mask=(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_Y); /* Start+X: reset */
        if(audio_only) {
            button_mask=0;
            if((frame>=1200 && frame<1204) || (frame>=1500 && frame<1504))button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_START;
            if((frame>=14500 && frame<14504) || (frame>=15100 && frame<15104) || (frame>=15700 && frame<15704))button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_Y;
            /* Break the idle pose before PLAYER.C bye_chk's 10800-update idle exit
               (a game over that plays the game over song); Down crouches silently. */
            if(frame>=8000 && frame<8004)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_DOWN;
        }
        if(diagnostic_only) {
            button_mask=0;
            if((frame>=1000 && frame<1004) || (frame>=1600 && frame<1604))button_mask=(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_L);
            if(frame>=1100 && frame<1104)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_B;
            if(frame>=1250 && frame<1254)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_A;
            if(frame>=1400 && frame<1404)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_R;
        }
        if(world_only){
            button_mask=0;
            if(frame>=1000 && frame<3004 && (frame-1000)%400<4)button_mask=(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_L2);
            if(frame>=3004)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT;
            if(frame>=4700)button_mask=0;
            if((frame>=4700 && frame<4704) || (frame>=5000 && frame<5004) || (frame>=5400 && frame<5404) || (frame>=5900 && frame<5904))button_mask=(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_L2);
            if((frame>=4870 && frame<4880) || (frame>=5270 && frame<5280) || (frame>=6070 && frame<6080))button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_B;
            if(frame>=6070 && frame<6200)button_mask|=1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT;
            if(frame>=6300 && frame<6304)button_mask=(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_L2);
            if(frame>=6304 && frame<7200 && !checkpoint_dead)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT;
            if(frame>=7200 && frame<8800){
                unsigned base=frame<8000?7200:8000,tick=frame-base;
                if(tick<4)button_mask=(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_L2);
                else if(tick<150 || tick>=210)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT;
                else button_mask=(1u<<RETRO_DEVICE_ID_JOYPAD_DOWN)|(tick<154?1u<<RETRO_DEVICE_ID_JOYPAD_B:0);
            }
            if(frame>=8800){
                unsigned tick=frame-(frame<10000?8800:10000);
                button_mask=tick<4?(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_L2):1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT;
                if(frame>=11100)button_mask=frame<11104?1u<<RETRO_DEVICE_ID_JOYPAD_START:0;
            }
            if(frame>=11200){
                unsigned base=frame<11600?11200:frame<12000?11600:frame<12400?12000:frame<14000?12400:14000,tick=frame-base;
                button_mask=tick<4?(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_L2):tick>=90 && tick<120?1u<<RETRO_DEVICE_ID_JOYPAD_B:0;
            }
            if(frame>=15600){
                unsigned tick=(frame-15600)%300;
                button_mask=tick<4?(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_L2):0;
            }
            if(frame>=18000){
                unsigned route=(frame-18000)/300,tick=(frame-18000)%300;
                button_mask=tick<4?(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_L2):0;
                if(route<2 && tick>=100 && tick<120)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_B;
            }
            if(frame>=18900){
                unsigned route=(frame-18900)/300,tick=(frame-18900)%300;
                button_mask=tick<4?(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_L2):0;
                if(route==2 && tick>=4 && tick<70)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT;
            }
            if(frame>=20400){
                unsigned tick=(frame-20400)%300;
                button_mask=tick<4?(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_L2):0;
            }
            if(frame>=23700){
                unsigned route=(frame-23700)/300,tick=(frame-23700)%300;
                button_mask=tick<4?(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_L2):0;
                if(route==0 && tick>=44 && tick<69)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_B;
            }
            if(frame>=24900){
                unsigned tick=frame-24900;
                button_mask=tick<4?(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_L2):0;
                if(tick>=624 && tick<649)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_B;
            }
            if(frame>=3700 && frame<3704)button_mask=(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_L2);
        }
        /* SCD_LEVEL_SELECT=<frame>: on the title, hold Saturn A+B+C (libretro
           B+A+R) and press Start to open the level select, capture it, move one
           row right to change the act, capture again, then start that act.
           Verification hook for the level select, not a gate. */
        if(level_select_frame){
            unsigned t0=level_select_frame;
            if(frame>=t0 && frame<t0+4)
                button_mask=(1u<<RETRO_DEVICE_ID_JOYPAD_B)|(1u<<RETRO_DEVICE_ID_JOYPAD_A)|
                            (1u<<RETRO_DEVICE_ID_JOYPAD_R)|(1u<<RETRO_DEVICE_ID_JOYPAD_START);
            else if(frame>=t0+60 && frame<t0+64)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT;
            else if(frame>=t0+120 && frame<t0+124)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_START;
            else button_mask=0;
            if(frame==t0-60)screenshot("level-select-before");
            if(frame==t0+5)screenshot("level-select-at");
            if(frame==t0+40)screenshot("level-select");
            if(frame==t0+100)screenshot("level-select-act2");
            if(frame==t0+400)screenshot("level-select-started");
        }
        /* act2: Start+C (libretro R) loads Act 2 Present; the route starts at its spawn. */
        /* act3: Start+Up+C loads Act 3 in the bad future. */
        if(act2_only && !act2_entry)button_mask=frame>=60 && frame<64?(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_R)|(act3_only?1u<<RETRO_DEVICE_ID_JOYPAD_UP:0):0;
        if(act_only || act2_entry){
            button_mask=act_elapsed>=act_right?1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT:0;
            int jump=act_elapsed>=act_start && (act_elapsed-act_start)%act_period<act_hold;
            /* act2 jumps only when stuck: grounded within 4 pixels of one X for 30 updates, then B for 20. */
            if(act2_only){
                jump=0;
                if(act2_jump){act2_jump--;jump=1;}
                else if(!(act_flags&2) && act_x+4>=act2_anchor && act_x<=act2_anchor+4){if(++act2_slow>=30){act2_slow=0;act2_jump=20;jump=1;}}
                else {act2_slow=0;act2_anchor=act_x;}
            }
            for(unsigned w=0;act2_only && w<act2_window_count;w++)if(act_x>=act2_windows[w][0] && act_x<act2_windows[w][1] && act_y>=act2_windows[w][2] && act_y<act2_windows[w][3]){
                jump=0;
                if(act2_windows[w][4]==1 && !act2_dash && !(act_flags&2)){act2_dash=1;act2_dash_timer=act2_windows[w][0]-96;}
                if(act2_windows[w][4]==2 && !act2_dash)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_LEFT;
                unsigned px=act2_swing>>16;
                /* Brake from a run, walk to 20 pixels before the ledge end, then step on while
                   the platform returns to its left end (or rests there). */
                if(act2_windows[w][4]==3 && !act2_dash){
                    if(act_vx>256 && !(act_flags&2))button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_LEFT;
                    else if(act_x+20<act2_windows[w][1])button_mask=act_vx<128?1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT:0;
                    else button_mask=px && px<=act2_windows[w][1]+48 && px<=(act2_swing_prev>>16)?1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT:0;
                }
                if(act2_windows[w][4]==5 && !act2_dash && !(act_flags&2) && !act2_force)act2_force=20;
                /* p: release Jump for half of each 40-update period, including while
                   riding a spinning disc, so a new press can release its control. */
                if(act2_windows[w][4]==9 && !act2_dash)jump=act_elapsed%40<20;
                /* R: a grounded player walks back 400 pixels, then runs right without jumping. */
                if(act2_windows[w][4]==7 && !act2_dash && !(act_flags&2)){act2_dash=4;act2_dash_timer=act2_windows[w][0]>400?act2_windows[w][0]-400:0;act2_run=0;}
                /* D: a grounded player waits to stop, turns right and spin dashes in place. */
                if(act2_windows[w][4]==8 && !act2_dash && !(act_flags&2)){act2_dash=6;act2_run=0;act2_inplace=1;act2_inplace_x=act2_windows[w][1];act2_inplace_y=act2_windows[w][3];}
                if(act2_windows[w][4]==6 && !act2_dash){if(!act2_turned && act_x<act2_windows[w][1])button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT;else{act2_turned=1;button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_LEFT;}}
                if(act2_windows[w][4]==4 && !act2_dash)button_mask=px>=act2_windows[w][1]-36?1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT:0;
            }
            /* act3 boss (mailbox 138/139): while Robotnik fights (egg1 routine 4), walk under him and
               jump; B is held for 16 updates and released for 4 before the next jump
               (V0.073 physics: 20/10 lost every ring at the boss; scan of hold 12-30,
               rest 4-20, window 8-40 on BIN dc05d1ee: 12/4 and 16/4 finish).
               SCD_ACT3_HOLD/REST/WINDOW override. */
            if(act3_only && act3_boss_status>>16 && ((act3_boss_status>>8)&255)==4){
                int dx=(int)(act3_boss_pos>>16)-(int)act_x;
                jump=0;act2_slow=0;act2_anchor=act_x;
                button_mask=dx>12?1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT:dx<-12?1u<<RETRO_DEVICE_ID_JOYPAD_LEFT:0;
                static int knob=-1,hold=16,rest=4,window=24;
                if(knob<0){knob=1;const char *v;if((v=getenv("SCD_ACT3_HOLD")))hold=atoi(v);if((v=getenv("SCD_ACT3_REST")))rest=atoi(v);if((v=getenv("SCD_ACT3_WINDOW")))window=atoi(v);}
                if(act3_hold){act3_hold--;jump=1;if(!act3_hold)act3_rest=(unsigned)rest;}
                else if(act3_rest)act3_rest--;
                else if(!(act_flags&2) && dx>=-window && dx<=window){act3_hold=(unsigned)hold;jump=1;}
            }
            if(act2_only && act2_force && !act2_dash){act2_force--;jump=1;}
            /* Backing up gives up after 180 updates (a blocked route, such as a fall into Act 3's capsule pit). */
            if(act2_dash==1){button_mask=act_x>act2_dash_timer?1u<<RETRO_DEVICE_ID_JOYPAD_LEFT:0;if(act_x<=act2_dash_timer){act2_dash=2;}else if(++act2_backup>180){act2_dash=0;act2_backup=0;button_mask=0;}}
            if(act2_dash!=1)act2_backup=0;
            if(act2_dash==4){button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_LEFT;jump=0;if(act_x<=act2_dash_timer || ++act2_run>300){act2_dash=5;act2_run=0;}}
            else if(act2_dash==5){button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT;jump=0;if(++act2_run>360){act2_dash=0;act2_run=0;}}
            else if(act2_dash==6){
                jump=0;button_mask=0;
                if(act_vx || (act_flags&2)){if(++act2_run>240){act2_dash=0;act2_run=0;}}
                else if(act_flags&1)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT;
                else {act2_dash=3;act2_dash_timer=0;act2_run=0;}
            }
            else if(act2_dash==2){button_mask=0;if(!act_vx && !(act_flags&2)){act2_dash=3;act2_dash_timer=0;}}
            else if(act2_dash==3){
                unsigned t=act2_dash_timer++;button_mask=t<50?1u<<RETRO_DEVICE_ID_JOYPAD_DOWN:1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT;
                if(t>=2 && t<6)button_mask|=1u<<RETRO_DEVICE_ID_JOYPAD_B;
                if(t>=230)act2_dash=0;
                /* An in-place dash (D) ends once it carries Sonic 64 pixels past its area. */
                if(act2_inplace && t>=60 && (act_x>act2_inplace_x+64 || act_y>act2_inplace_y+64))act2_dash=0;
                if(!act2_dash)act2_inplace=0;
                jump=0;
            }
            if(jump)button_mask|=1u<<RETRO_DEVICE_ID_JOYPAD_B;
            /* Start the full-era route from the ordinary Act 2 debug entry, then use
               the existing X control to reload the requested source era. One-frame
               pulses avoid cycling through multiple eras in main.c. */
            if(!act3_only && act_target_era<=3 && act_era!=act_target_era){
                /* Pulse on a grid anchored to the Act 2 Present load (act2_entry), not
                   the absolute frame. main.c's X handler reloads the era without
                   restarting the title card, so the Past and Good Future updates that
                   run before the target era loads come off the target era's card. On
                   the absolute grid that count followed CD load time mod 16: 7dbf5c5
                   cut the Act 2 pack load from 144 to 130 VBlanks and moved the Good
                   Future's first input from update 128 to 129. Phase 13 is the V0.057
                   alignment (entry 211, pulses 224/240/256) that CARD_HOLD {0,127,116}
                   and all three routes were recorded with. */
                /* Later pulses are aligned to gameplay updates, not frames: each
                   fires on the reset-update record of the era the previous pulse
                   loaded, a fixed number of updates later. The intermediate eras then spend a fixed number of card
                   updates whatever their CD load time. On the frame grid that count
                   followed load time and moved the Future eras' first input (V0.058:
                   Good 128 -> 131, Bad 117 -> 121), which stopped Sonic at their
                   speed-dependent walls. The first pulse stays on the entry grid; it
                   lands before any Present update. */
                static unsigned era_pulses,era_pulse_base,era_reset;
                /* Updates to wait after each loaded era's reset update. Fixed
                   per era so the references keep their recorded first inputs:
                   Past +1 gives the Good Future 128, the Good Future +9 gives
                   the Bad Future 117 (V0.058 routes and CARD_HOLD 127/116). */
                static const unsigned era_delay[4]={0,1,9,0};
                const uint8_t *ram=p_retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM);
                if(!ram)return exit2(__LINE__);
                unsigned now=ram_word(ram,mailbox+4);int fire=0;
                if(!era_pulses)fire=(frame-act2_entry)%16==13;
                else{
                    if(now-era_pulse_base>64){fprintf(stderr,"Era pulse trace overflow\n");return exit2(__LINE__);}
                    if(!era_reset)for(unsigned n=era_pulse_base+1;n<=now;n++){
                        size_t r=mailbox+(24+(n%64)*21)*4;
                        if(ram_word(ram,r)==n && ram_word(ram,r+36)==1)era_reset=n;
                    }
                    fire=era_reset && now>=era_reset+era_delay[era_pulses];
                }
                if(era_pulses>=act_target_era)fire=0;
                button_mask=fire?1u<<RETRO_DEVICE_ID_JOYPAD_Y:0;
                if(fire){
                    era_pulses++;era_pulse_base=now;era_reset=0;
                    if(era_pulses==act_target_era)act_era_switch_base=now;
                    printf("Act 2 era pulse %u at update %u frame %u\n",era_pulses,now,frame);
                }
            }
            /* A charging time warp (world ticks) makes the act2 route coast so it stays in the Present. */
            if(act2_only && !act2_travel && act_warp && !act2_dash)
                button_mask=act_target_era<=3?(act_vx>0?1u<<RETRO_DEVICE_ID_JOYPAD_LEFT:act_vx<0?1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT:0):0;
            /* After the Act 3 tally the next zone loads on its own, so the route
               stops driving the pad and simply watches the zone change. */
            if(act3_end)button_mask=0;
        }
        /* Hold the next simulation update's recorded pad across any extra
           VBlanks. A faster renderer must not shorten a jump or advance the
           route driver's counters. Debug entry/era selection still use pads. */
        if(act_pad_count && (act_only || act2_entry) && act_route_ready && !act3_end){
            /* SMPC's VBlank-out poll is consumed one update later. */
            unsigned next=act_elapsed+1;
            button_mask=next<act_pad_count?act_pad_mask(act_pad_states[next].buttons):0;
        }
        if(special_only){
            button_mask=0;
            if(frame>=1000 && frame<1004)button_mask=(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_A);
            if(frame>=1000 && frame<7400){
                unsigned stage=(frame-1000)/800,tick=(frame-1000)%800;
                if(stage && tick<32)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_Y;
                if(tick>=240 && tick<272)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT;
                if(tick>=450 && tick<600)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_B;
                if((tick>=620 && tick<652) || (tick>=720 && tick<752))button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_R;
            }
            if(frame>=10600 && frame<10632)button_mask=(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_A);
            if(frame>=10800 && frame<10832)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_X;
            if(frame>=10900 && frame<11000)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_LEFT;
            if((frame>=11000 && frame<11032) || (frame>=11200 && frame<11232) || (frame>=11400 && frame<11432) || (frame>=11600 && frame<11632) || (frame>=11680 && frame<11712))button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_L;
            if(frame>=11232 && frame<11400)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT;
            if(frame>=11632 && frame<11772)button_mask|=1u<<RETRO_DEVICE_ID_JOYPAD_B;
            if(frame>=11900 && frame<11932)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_START;
            if(frame>=12200 && frame<12232)button_mask=(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_A);
            if(frame>=12400 && frame<12432)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_X;
            if(frame>=12600 && frame<15800 && (frame-12600)%400<32)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_L2;
            if(frame>=12600 && frame<15800){unsigned tick=(frame-12600)%400;if((tick>=48 && tick<80) || (tick>=160 && tick<192))button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_L;}
            /* Up+L: seeded UFO hit; Down+L: time UFO. Z freezes at +36 and +150. */
            if(frame>=15800 && frame<16600){
                unsigned ufo=(frame-15800)/400,tick=(frame-15800)%400;
                if(tick<32)button_mask=(1u<<RETRO_DEVICE_ID_JOYPAD_L2)|(1u<<(ufo?RETRO_DEVICE_ID_JOYPAD_DOWN:RETRO_DEVICE_ID_JOYPAD_UP));
                if((tick>=36 && tick<68) || (tick>=100 && tick<132) || (tick>=150 && tick<182) || (tick>=240 && tick<272))button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_L;
            }
            if(frame>=16600 && frame<16632)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_START;
            if(frame>=7500 && frame<7532)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_START;
            if(frame>=7600 && frame<7900)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT;
            if(frame>=9600 && frame<9632)button_mask=(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_A);
            if(frame>=9900 && frame<9932)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_R2;
            if(frame>=10300 && frame<10332)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_START;
            if(frame>=8050 && frame<8054)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_X;
            if(frame>=8800 && frame<8804)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_L;
            if((frame>=8150 && frame<8182) || (frame>=8900 && frame<8932))button_mask=(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_A);
            if((frame>=8500 && frame<8532) || (frame>=9250 && frame<9282))button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_START;
        }
        if(game_only){
            button_mask=0;
            const uint8_t *ram=p_retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM);
            /* SCD_SPECIAL_ATTRACT: no presses; the title times out into the attract demos (IPX.asm Demo).
               SCD_SPECIAL_ATTRACT=x or y holds Saturn X or Y there: the debug entry for
               Special Stage 8 or Time Attack (src/special_modes.c). */
            const char *attract_value=getenv("SCD_SPECIAL_ATTRACT");const int attract=attract_value!=NULL;
            if(attract && game_route<game_route_count){
                if(!strcmp(attract_value,"x"))button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_Y;
                if(!strcmp(attract_value,"y"))button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_X;
            }
            /* SCD_SPECIAL_ATTRACT=st: the sound test secret (Menu/Main.asm ObjMenu_SoundTestCheat
               Down Down Down Left Right A on the press-start screen, then Sound Test.asm FM 07,
               PCM 07, DA 07 and Start), the real Special Stage 8 entry. Timing as
               tools/test_frontend_emulator.py sound-test-ss8: 8 frames per selection step. */
            if(attract && !strcmp(attract_value,"st") && game_route<game_route_count && ram){
                enum {U=1u<<RETRO_DEVICE_ID_JOYPAD_UP,D=1u<<RETRO_DEVICE_ID_JOYPAD_DOWN,L=1u<<RETRO_DEVICE_ID_JOYPAD_LEFT,
                      R=1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT,A=1u<<RETRO_DEVICE_ID_JOYPAD_B,S=1u<<RETRO_DEVICE_ID_JOYPAD_START};
                static const unsigned code[][2]={{D,4},{0,4},{D,4},{0,4},{D,4},{0,4},{L,4},{0,4},{R,4},{0,4},{A,4},{0,4}};
                static const unsigned pick[][2]={{D,56},{0,4},{R,8},{0,4},{D,56},{0,4},{R,8},{0,4},{D,56},{0,4},{S,2}};
                static unsigned st_phase,st_start;
                uint32_t magic=mailbox+4<=p_retro_get_memory_size(RETRO_MEMORY_SYSTEM_RAM)?ram_word(ram,mailbox):0;
                if(st_phase==0 && magic==0x5449544c){st_phase=1;st_start=frame+240;}
                if(st_phase==2 && magic==0x46454e44){st_phase=3;st_start=frame+20;}
                const unsigned (*steps)[2]=st_phase==1?code:st_phase==3?pick:NULL;unsigned count=st_phase==1?12:11;
                button_mask=0;
                if(steps && frame>=st_start){
                    unsigned at=frame-st_start,i=0;
                    while(i<count && at>=steps[i][1]){at-=steps[i][1];i++;}
                    if(i<count)button_mask=steps[i][0];else st_phase++;
                }
            }
            if(frame>=1000 && frame<1004 && !attract)button_mask=(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_A);
            /* X steps the inspection to the next stage (four frames each, 200 apart), then B (L+B for win routes) starts it. */
            unsigned steps=game_route<game_route_count?game_route_stage[game_route]-1:0;
            if(!attract && game_route<game_route_count && frame>=game_start && frame<game_start+200*steps && (frame-game_start)%200<4)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_Y; /* Saturn X */
            /* SCD_SPECIAL_MODE_POKE "addr=value,...": test-only Work RAM words written just before B,
               e.g. special_game_mode=5 and special_game_mode_stage=8 for the Stage 8 entry (IPX.asm) the disc has no menu for. */
            const char *poke=getenv("SCD_SPECIAL_MODE_POKE");
            if(poke && ram && !attract && game_route<game_route_count && frame==game_start+200*steps-1){
                for(const char *at=poke;*at;){
                    char *end;unsigned long address=strtoul(at,&end,16),value=*end=='='?strtoul(end+1,&end,16):0;
                    size_t offset=0x100000+(address&0xfffff);
                    if((address&0x0ff00000)!=0x06000000 || offset+4>p_retro_get_memory_size(RETRO_MEMORY_SYSTEM_RAM))return exit2(__LINE__);
                    ram_put_word((uint8_t *)ram,offset,(uint32_t)value);printf("Special mode poke: %08lx=%lx\n",address,value);
                    at=*end==','?end+1:end;if(at==end && *end)return exit2(__LINE__);
                }
            }
            if(!attract && game_route<game_route_count && frame>=game_start+200*steps && frame<game_start+200*steps+2)button_mask=(1u<<RETRO_DEVICE_ID_JOYPAD_A)|(game_route_win[game_route]?1u<<RETRO_DEVICE_ID_JOYPAD_L2:0);
            if(ram && game_mailbox+160<=p_retro_get_memory_size(RETRO_MEMORY_SYSTEM_RAM) && ram_word(ram,game_mailbox)==0x5353474d && ram_word(ram,game_mailbox+108)){
                unsigned v=ram_word(ram,game_mailbox+4),results=ram_word(ram,game_mailbox+8)>=5,index=v+game_lead;
                button_mask=game_retro_mask(game_pads[game_route<game_route_count?game_route:game_route_count-1][results][index<16000?index:15999]);
            }
            /* SCD_SPECIAL_AFTER "frames,start": after the last route, hold Start from frame
               <start> for 30 frames (the Stage 8 credits read ctrlHold). */
            unsigned after[2];
            if(game_route==game_route_count && game_route && getenv("SCD_SPECIAL_AFTER") && sscanf(getenv("SCD_SPECIAL_AFTER"),"%u,%u",after,after+1)==2 &&
               frame>=game_done[game_route_count-1]+after[1] && frame<game_done[game_route_count-1]+after[1]+30)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_START;
        }
        if(bigring_only){
            button_mask=0;
            const uint8_t *ram=p_retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM);size_t ram_size=p_retro_get_memory_size(RETRO_MEMORY_SYSTEM_RAM);
            /* Explicit save QA only: the normal debug fixture disables saves.
               Re-enable the session after fixture entry, then earn the stone
               through the existing controller route and real return flow. */
            if(frame==68 && getenv("SCD_SAVE_FIXTURE_SESSION")){
                size_t at=0x100000+(strtoul(getenv("SCD_SAVE_FIXTURE_SESSION"),NULL,16)&0xfffff);
                if(at+4>ram_size)return exit2(__LINE__);
                ram_put_word((uint8_t *)ram,at,1);
                printf("Save QA: enabled persistence after the explicit big-ring fixture\n");
            }
            /* Start+Left+C: the big ring fixture before the Act 1 goal post with 50 rings. */
            if(frame>=60 && frame<64)button_mask=(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_R)|(1u<<RETRO_DEVICE_ID_JOYPAD_LEFT);
            else if(ram && frame>=64 && world_mailbox+568<=ram_size && game_mailbox+160<=ram_size){
                if(ram_word(ram,game_mailbox)==0x5353474d && ram_word(ram,game_mailbox+108)){
                    /* Special Stage 1: the retail win route's pad script. */
                    unsigned v=ram_word(ram,game_mailbox+4),results=ram_word(ram,game_mailbox+8)>=5,index=v+game_lead;
                    button_mask=game_retro_mask(game_pads[1][results][index<16000?index:15999]);
                }else if(!bigring_touch && !bigring_returned){
                    /* Run past the goal post and the signpost, stop under the big ring (X 10608) and jump into it. */
                    unsigned x=ram_word(ram,world_mailbox+52),flags=ram_word(ram,world_mailbox+64);
                    if(x<10585)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT;
                    else if(x>=10640)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_LEFT;
                    if(bigring_jump){bigring_jump--;button_mask|=1u<<RETRO_DEVICE_ID_JOYPAD_B;}
                    else if(x>=10585 && x<10640 && !(flags&2))bigring_jump=20;
                }
            }
        }
        p_retro_run();
        const uint8_t *sound_ram=p_retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM);
        size_t sound_size=p_retro_get_memory_size(RETRO_MEMORY_SYSTEM_RAM);
        if(!sound_ram || audio_mailbox+48>sound_size)return exit2(__LINE__);
        if(world_only && effect_file){
            if(effect_at+57*4>sound_size || !sonic_view_address || world_mailbox+80>sound_size)return exit2(__LINE__);
            if(effect_due==frame && effect_due){
                char name[48];snprintf(name,sizeof(name),"powerup-native-%u",effect_count++);screenshot(name);
                printf("Powerup pixels: %s",name);for(unsigned n=0;n<57;n++)printf(" %u",effect_snapshot[n]);putchar('\n');
                printf("Powerup Sonic: %s",name);for(unsigned n=0;n<18;n++)printf(" %u",effect_sonic[n]);putchar('\n');effect_due=0;
            }
            if(ram_word(sound_ram,effect_at)==0x504f5756){
                unsigned update=ram_word(sound_ram,effect_at+4),fixture=ram_word(sound_ram,world_mailbox+76);
                if(update!=effect_previous || fixture!=effect_fixture){
                    fprintf(effect_file,"%u",fixture);for(unsigned n=0;n<57;n++)fprintf(effect_file," %u",ram_word(sound_ram,effect_at+n*4));fputc('\n',effect_file);
                    unsigned travel=ram_word(sound_ram,effect_at+32)&255;
                    bool monitor=(fixture==19 || fixture==20) && update>=125 && update<235;
                    bool stars=travel && effect_travel_count<90 && !ram_word(sound_ram,world_mailbox+28);
                    if(!effect_due && (monitor || stars) && ram_word(sound_ram,sonic_view_at)==0x534F4E56 &&
                       ram_word(sound_ram,effect_at+36)==ram_word(sound_ram,sonic_view_at+8)){
                        for(unsigned n=0;n<57;n++)effect_snapshot[n]=ram_word(sound_ram,effect_at+n*4);
                        for(unsigned n=0;n<18;n++)effect_sonic[n]=ram_word(sound_ram,sonic_view_at+n*4);
                        effect_due=frame+1;if(stars)effect_travel_count++;
                    }
                }
                effect_previous=update;effect_fixture=fixture;
            }
        }
        /* One field after the submitted pose, matching the camera/Amy capture
           convention. Only replay fixtures without overlapping stage actors;
           their opaque Sonic pixels are checked against original source art. */
        if(sonic_view_address){
            if(sonic_view_at+72>sound_size)return exit2(__LINE__);
            if(sonic_view_due && sonic_view_due==frame){
                char name[48];snprintf(name,sizeof(name),"sonic-native-%u",sonic_view_count++);screenshot(name);
                printf("Sonic native: %s",name);for(unsigned i=0;i<18;i++)printf(" %u",sonic_view_snapshot[i]);putchar('\n');
                sonic_view_due=0;
            }
            unsigned serial=ram_word(sound_ram,sonic_view_at+4),mapping=ram_word(sound_ram,sonic_view_at+12);
            unsigned era=ram_word(sound_ram,sonic_view_at+44),flip=ram_word(sound_ram,sonic_view_at+16)&3;
            unsigned test=ram_word(sound_ram,sonic_view_at+64),hidden=ram_word(sound_ram,sonic_view_at+52);
            unsigned simulation=ram_word(sound_ram,sonic_view_at+8);
            if((test==16 || test==23) && serial!=sonic_view_serial &&
               ram_word(sound_ram,sonic_view_at)==0x534F4E56 && ram_word(sound_ram,mailbox+8)==test &&
               ram_word(sound_ram,mailbox+40)==simulation){
                printf("Sonic display:");for(unsigned i=0;i<18;i++)printf(" %u",ram_word(sound_ram,sonic_view_at+i*4));putchar('\n');
            }
            /* Yellow spring: consecutive ascent/apex/descent pictures, well
               above the only spawned actor. Red spring apex is offscreen. */
            bool air_sample=test==9 && simulation>=32 && simulation<=64;
            if(!sonic_view_due && ram_word(sound_ram,sonic_view_at)==0x534F4E56 && serial!=sonic_view_serial &&
               era<4 && mapping>0 && mapping<198 && !hidden &&
               ((test<8 && !sonic_view_seen[era][mapping][flip]) || air_sample)){
                for(unsigned i=0;i<18;i++)sonic_view_snapshot[i]=ram_word(sound_ram,sonic_view_at+i*4);
                sonic_view_seen[era][mapping][flip]=true;sonic_view_due=frame+1;
            }
            /* QA_DEATH_AT=test:tick with QA_ACTWK=&actwk: at that replay
               update, move Sonic below the map for one update so the native
               bottom check calls the source playdieset (sproffset bit 15,
               sprpri 0), restore his Y, then picture each dying pose. */
            static unsigned death_test=~0u,death_tick,death_state,death_count,death_due,death_snapshot[18];static uint32_t death_y;static size_t death_at;
            if(death_test==~0u && getenv("QA_DEATH_AT") && getenv("QA_ACTWK")){
                if(sscanf(getenv("QA_DEATH_AT"),"%u:%u",&death_test,&death_tick)!=2)return exit2(__LINE__);
                death_at=0x100000+(strtoul(getenv("QA_ACTWK"),NULL,16)&0xfffff)+12;
            }
            if(death_test!=~0u && ram_word(sound_ram,sonic_view_at)==0x534F4E56){
                if(death_due && death_due==frame){
                    char name[48];snprintf(name,sizeof(name),"dying-%u",death_count++);screenshot(name);
                    printf("Dying Sonic: %s",name);for(unsigned i=0;i<18;i++)printf(" %u",death_snapshot[i]);putchar('\n');fflush(stdout);
                    death_due=0;if(death_count==48)exit(0);
                }
                if(!death_state && test==death_test && simulation==death_tick){
                    death_y=ram_word(sound_ram,death_at);ram_put_word((uint8_t *)sound_ram,death_at,2041u<<16);death_state=1;
                    printf("Death probe: frame=%u test=%u tick=%u y=%u\n",frame,test,simulation,death_y);
                }else if(death_state==1 && simulation>death_tick){
                    ram_put_word((uint8_t *)sound_ram,death_at,death_y);death_state=2;
                }else if(death_state==2 && !death_due && serial!=sonic_view_serial && !hidden){
                    for(unsigned i=0;i<18;i++)death_snapshot[i]=ram_word(sound_ram,sonic_view_at+i*4);
                    death_due=frame+1;
                }
            }
            sonic_view_serial=serial;
        }
        if(act_profile && (act_only || act2_only)){
            if(act_profile_at+(4+64*32)*4>sound_size)return exit2(__LINE__);
            if(ram_word(sound_ram,act_profile_at)==0x46505246){
                unsigned latest=ram_word(sound_ram,act_profile_at+4);
                if(latest-act_profile_seq>64 || ram_word(sound_ram,act_profile_at+8)!=32){fprintf(stderr,"Act profile overflow/stride mismatch\n");return exit2(__LINE__);}
                while(act_profile_seq<latest){
                    size_t at=act_profile_at+(4+(++act_profile_seq%64)*32)*4;
                    if(ram_word(sound_ram,at)!=act_profile_seq)return exit2(__LINE__);
                    printf("Frame profile:");for(unsigned i=0;i<32;i++)printf(" %u",ram_word(sound_ram,at+i*4));printf("\n");
                }
            }
        }
        if(bigring_only){
            if(frame<64)continue;
            if(world_mailbox+568>sound_size || game_mailbox+160>sound_size)return exit2(__LINE__);
            unsigned special=ram_word(sound_ram,world_mailbox+564),phase=ram_word(sound_ram,world_mailbox+104),act=ram_word(sound_ram,world_mailbox+536);
            bool game=ram_word(sound_ram,game_mailbox)==0x5353474d && ram_word(sound_ram,game_mailbox+108);
            if(!bigring_touch && (special>>16)){bigring_touch=frame;printf("Big ring touched: frame=%u x=%u rings=%u\n",frame,ram_word(sound_ram,world_mailbox+52),ram_word(sound_ram,world_mailbox+128));}
            if(bigring_touch && frame==bigring_touch+4)screenshot("bigring-touch");
            if(phase==6 && !bigring_tally && !bigring_game){bigring_tally=frame;bigring_tally_score=ram_word(sound_ram,world_mailbox+116);screenshot("bigring-tally");}
            if(game){
                bigring_game=1;unsigned v=ram_word(sound_ram,game_mailbox+4),stage=ram_word(sound_ram,game_mailbox+8);
                if(v>=240 && !bigring_stage){bigring_stage=frame;screenshot("bigring-special");}
                if(stage>=6 && !bigring_results)bigring_results=frame;
                if(bigring_results && frame==bigring_results+10)screenshot("bigring-results");
            }
            if(bigring_game && !game && !((special>>8)&255) && act==1 && !bigring_returned)bigring_returned=frame;
            if(bigring_returned && frame==bigring_returned+400){
                screenshot("bigring-act2");
                printf("Big ring: touched=%u tally_score=%u stones=%u act=%u era=%u score=%u lives=%u rings=%u frames=%u\n",bigring_touch,bigring_tally_score,ram_word(sound_ram,world_mailbox+560),act,ram_word(sound_ram,world_mailbox+8),ram_word(sound_ram,world_mailbox+116),(ram_word(sound_ram,world_mailbox+88)>>8)&255,ram_word(sound_ram,world_mailbox+128),frame);
                p_retro_unload_game();p_retro_deinit();return 0;
            }
            continue;
        }
        if(game_only){
            if(game_mailbox+160>sound_size)return exit2(__LINE__);
            /* Attract runs: the title state every 1000 frames ('TITL', vint, mode|menu|sel|done). */
            if(getenv("SCD_SPECIAL_ATTRACT") && frame%1000==0 && mailbox+12<=sound_size)
                printf("Attract state: %u %08x %u %08x active=%u\n",frame,ram_word(sound_ram,mailbox),ram_word(sound_ram,mailbox+4),ram_word(sound_ram,mailbox+8),ram_word(sound_ram,game_mailbox+108));
            unsigned active=ram_word(sound_ram,game_mailbox)==0x5353474d && ram_word(sound_ram,game_mailbox+108);
            if(active && game_route<game_route_count){
                /* SCD_SPECIAL_READBACK "addr,addr,...": Work RAM words read once the run is active
                   (the mode and stage that actually started), printed for the gate to assert. */
                if(!game_seen_active && getenv("SCD_SPECIAL_READBACK")){
                    printf("Special mode readback: %u",game_route);
                    for(const char *at=getenv("SCD_SPECIAL_READBACK");*at;){
                        char *end;unsigned long address=strtoul(at,&end,16);size_t offset=0x100000+(address&0xfffff);
                        if((address&0x0ff00000)!=0x06000000 || offset+4>sound_size || end==at)return exit2(__LINE__);
                        printf(" %08lx=%u",address,ram_word(sound_ram,offset));at=*end==','?end+1:end;
                    }
                    putchar('\n');
                }
                game_seen_active=1;bool valid32,valid40;
                uint32_t crc32=game_crc(37,256,0,224,&valid32),crc40=game_crc(5,320,0,224,&valid40);
                /* H32 rows 0..127 and 128..223: the floor rows are VDP1, the rows above mostly VDP2. */
                bool valid_split;uint32_t crc_top=game_crc(37,256,0,128,&valid_split),crc_floor=game_crc(37,256,128,224,&valid_split);
                /* Rows 24..223: everything below the HUD digit rows. */
                uint32_t crc_below_hud=game_crc(37,256,24,224,&valid_split);
                printf("Special game: %u %u",game_route,frame);
                /* [7..10]: CRAM, plane A/B and H-scroll addresses; [29]: shown draw list ([34] entries). */
                static const unsigned hashed[40]={[7]=128,[8]=4096,[9]=4096,[10]=896,[29]=8};
                for(unsigned i=0;i<40;i++){
                    uint32_t value=ram_word(sound_ram,game_mailbox+i*4);
                    if(hashed[i])value=game_hash(sound_ram,sound_size,value,hashed[i]*(i==29?ram_word(sound_ram,game_mailbox+136):1));
                    printf(" %u",value);
                }
                printf(" %08x %u %08x %u %u %u %u %u %08x %08x %08x\n",crc32,valid32,crc40,valid40,last_width,ram_word(sound_ram,audio_mailbox+12),ram_word(sound_ram,audio_mailbox+8),ram_word(sound_ram,audio_mailbox+20),crc_top,crc_floor,crc_below_hud);
                game_records++;
                unsigned v=ram_word(sound_ram,game_mailbox+4),phase=ram_word(sound_ram,game_mailbox+8);
                static const unsigned shots[][3]={{0,2,321},{0,3,930},{0,4,5190},{0,5,30},{0,6,300},{1,2,1500},{1,2,3060},{1,6,39},{1,7,44},{1,7,50}};
                for(unsigned s=0;s<sizeof(shots)/sizeof(shots[0]);s++)if(game_default_routes && shots[s][0]==game_route && shots[s][1]==phase && shots[s][2]==v){
                    char name[64];snprintf(name,sizeof(name),"special-game-%u-%u-%u-%u",game_route,phase,v,frame);screenshot(name);
                }
                /* SCD_SPECIAL_SHOTS: extra "route,first V-INT,last V-INT" stage captures for timing checks. */
                unsigned extra[3];
                if(getenv("SCD_SPECIAL_SHOTS") && sscanf(getenv("SCD_SPECIAL_SHOTS"),"%u,%u,%u",extra,extra+1,extra+2)==3 && extra[0]==game_route && phase<5 && v>=extra[1] && v<=extra[2]){
                    char name[64];snprintf(name,sizeof(name),"special-timing-%u-%u-%u",game_route,v,frame);screenshot(name);
                }
            }
            if(!active && game_seen_active && game_route<game_route_count){
                game_done[game_route]=frame;game_seen_active=0;game_route++;game_start=frame+300;
                printf("Special game route done: %u %u vint=%u phase=%u error=%u job=%08x slave_rows=%u\n",game_route-1,frame,ram_word(sound_ram,game_mailbox+4),ram_word(sound_ram,game_mailbox+8),ram_word(sound_ram,game_mailbox+104),ram_word(sound_ram,game_mailbox+152),ram_word(sound_ram,game_mailbox+156));
            }
            unsigned after_run[2];const int after_set=getenv("SCD_SPECIAL_AFTER") && sscanf(getenv("SCD_SPECIAL_AFTER"),"%u,%u",after_run,after_run+1)==2;
            if(after_set && game_route==game_route_count && game_route){
                /* After the last route: the picture and the title mailbox every frame. */
                bool valid40;uint32_t crc40=game_crc(5,320,0,224,&valid40);
                printf("After: %u %08x %u %u %08x\n",frame-game_done[game_route_count-1],crc40,valid40,last_width,mailbox+4<=sound_size?ram_word(sound_ram,mailbox):0);
                const unsigned rel=frame-game_done[game_route_count-1];
                if(rel==60 || rel==200 || rel==400 || rel==800){char name[32];snprintf(name,sizeof(name),"after-%u",rel);screenshot(name);}
                if(frame>game_done[game_route_count-1]+after_run[0])break;
            }
            else if(game_route==game_route_count && frame>game_done[game_route_count-1]+120)break;
            if(getenv("SCD_SPECIAL_STOP") && frame>=strtoul(getenv("SCD_SPECIAL_STOP"),NULL,10))break;
            continue;
        }
        if(special_only){
            if(special_mailbox+128>sound_size || bench_mailbox+(8+8*20)*4>sound_size)return exit2(__LINE__);
            if(contact_mailbox+(8+8*79)*4>sound_size)return exit2(__LINE__);
            unsigned contacts=ram_word(sound_ram,contact_mailbox+4);
            if(contacts-contact_count>8){fprintf(stderr,"Special contact trace overflow\n");return exit2(__LINE__);}
            while(contact_count<contacts){
                unsigned sequence=++contact_count;size_t address=contact_mailbox+(8+(sequence%8)*79)*4;
                if(ram_word(sound_ram,address)!=sequence)return exit2(__LINE__);
                printf("Special contact state:");for(unsigned i=0;i<79;i++)printf(" %u",ram_word(sound_ram,address+i*4));putchar('\n');
            }
            if(frame>=9900 && frame<10500){
                unsigned count=ram_word(sound_ram,bench_mailbox+4);
                if(count-special_bench_count>8){fprintf(stderr,"Special benchmark trace overflow\n");return exit2(__LINE__);}
                while(special_bench_count<count){
                    unsigned sequence=++special_bench_count;size_t address=bench_mailbox+(8+(sequence%8)*20)*4;
                    if(ram_word(sound_ram,address)!=sequence)return exit2(__LINE__);
                    printf("Special benchmark:");for(unsigned i=0;i<20;i++)printf(" %u",ram_word(sound_ram,address+i*4));putchar('\n');
                }
                if(frame==10100 && (!ram_word(sound_ram,bench_mailbox+12) || count!=1632)){
                    if(ram_word(sound_ram,bench_mailbox+8) || ++special_bench_wait>18000){fprintf(stderr,"Special benchmark incomplete count=%u\n",count);return exit2(__LINE__);}
                    frame--;continue;
                }
            }
            if(frame>=1000 && frame<7400){
                unsigned stage=(frame-1000)/800+1,tick=(frame-1000)%800;
                if(tick==780){
                    unsigned updates=ram_word(sound_ram,special_mailbox+112),minimum=ram_word(sound_ram,special_mailbox+116),maximum=ram_word(sound_ram,special_mailbox+120);
                    if(ram_word(sound_ram,special_mailbox+100) || updates<5 || minimum<3 || maximum>120 || ram_word(sound_ram,special_mailbox+96)!=updates){fprintf(stderr,"Special live animation cadence failed stage=%u updates=%u min=%u max=%u\n",stage,updates,minimum,maximum);return exit2(__LINE__);}
                    printf("Special live animation: %u %u %u %u\n",stage,updates,minimum,maximum);special_live++;
                    printf("Special snapshot: %u 3",stage);for(unsigned i=0;i<24;i++)printf(" %u",ram_word(sound_ram,special_mailbox+i*4));putchar('\n');
                    char name[40];snprintf(name,sizeof(name),"special-%u-3",stage);screenshot(name);special_captures++;
                }
                if(tick==200 || tick==380 || tick==540){
                    unsigned words[24];for(unsigned i=0;i<24;i++)words[i]=ram_word(sound_ram,special_mailbox+i*4);
                    if(words[0]!=0x53504543 || words[1] || words[2]!=stage || !words[15]){fprintf(stderr,"Special load/render failed stage=%u magic=%x error=%u actual=%u active=%u\n",stage,words[0],words[1],words[2],words[15]);return exit2(__LINE__);}
                    unsigned capture=tick==200?0:tick==380?1:2;
                    printf("Special snapshot: %u %u",stage,capture);for(unsigned i=0;i<24;i++)printf(" %u",words[i]);putchar('\n');
                    char name[40];snprintf(name,sizeof(name),"special-%u-%u",stage,capture);screenshot(name);special_captures++;
                }
            }
            if(frame>=12600 && frame<15800 && (frame-12600)%400==128){
                unsigned fixture=(frame-12600)/400+1;
                if(ram_word(sound_ram,sonic_mailbox+4)!=1 || !ram_word(sound_ram,sonic_mailbox+120)){fprintf(stderr,"Special effect capture not frozen\n");return exit2(__LINE__);}
                printf("Special effect snapshot: %u",fixture);for(unsigned i=0;i<32;i++)printf(" %u",ram_word(sound_ram,sonic_mailbox+i*4));
                for(unsigned i=0;i<32;i++)printf(" %u",ram_word(sound_ram,special_mailbox+i*4));putchar('\n');
                char name[40];snprintf(name,sizeof(name),"special-effect-%u",fixture);screenshot(name);effect_captures++;
            }
            if(frame>=15800 && frame<16600 && ((frame-15800)%400==60 || (frame-15800)%400==180)){
                unsigned ufo=(frame-15800)/400,capture=(frame-15800)%400==60?0:1;
                if(ram_word(sound_ram,sonic_mailbox+4)!=1 || !ram_word(sound_ram,sonic_mailbox+120) || ram_word(sound_ram,special_mailbox+4)){fprintf(stderr,"Special UFO capture not frozen or failed\n");return exit2(__LINE__);}
                printf("Special UFO snapshot: %u %u",ufo,capture);for(unsigned i=0;i<32;i++)printf(" %u",ram_word(sound_ram,sonic_mailbox+i*4));
                for(unsigned i=0;i<32;i++)printf(" %u",ram_word(sound_ram,special_mailbox+i*4));putchar('\n');
                char name[40];snprintf(name,sizeof(name),"special-ufo-%u-%u",ufo,capture);screenshot(name);ufo_captures++;
            }
            if(frame==11100 || frame==11500 || frame==11840){
                if(sonic_mailbox+128>sound_size || ram_word(sound_ram,sonic_mailbox)!=0x534e4943 || ram_word(sound_ram,sonic_mailbox+4)!=1 || !ram_word(sound_ram,sonic_mailbox+120)){fprintf(stderr,"Sonic motion view not frozen\n");return exit2(__LINE__);}
                printf("Special Sonic snapshot: %u",sonic_captures);for(unsigned i=0;i<32;i++)printf(" %u",ram_word(sound_ram,sonic_mailbox+i*4));
                for(unsigned i=0;i<32;i++)printf(" %u",ram_word(sound_ram,special_mailbox+i*4));putchar('\n');
                char name[40];snprintf(name,sizeof(name),"special-sonic-%u",sonic_captures++);screenshot(name);
            }
            if((frame==12050 || frame==16800) && (ram_word(sound_ram,sonic_mailbox+4) || ram_word(sound_ram,special_mailbox+60) || ram_word(sound_ram,special_mailbox+92))){fprintf(stderr,"Sonic view return failed\n");return exit2(__LINE__);}
            if(frame==8400 || frame==9150){
                unsigned expected=frame==8400?1:2;
                if(ram_word(sound_ram,special_mailbox)!=0x53504543 || ram_word(sound_ram,special_mailbox+4) || ram_word(sound_ram,special_mailbox+76)!=expected || !ram_word(sound_ram,special_mailbox+60)){fprintf(stderr,"Special nested diagnostic entry failed frame=%u magic=%x error=%u flags=%u expected=%u active=%u\n",frame,ram_word(sound_ram,special_mailbox),ram_word(sound_ram,special_mailbox+4),ram_word(sound_ram,special_mailbox+76),expected,ram_word(sound_ram,special_mailbox+60));for(unsigned i=16;i<24;i++)fprintf(stderr," mb%u=%x",i,ram_word(sound_ram,special_mailbox+i*4));fputc(10,stderr);return exit2(__LINE__);}
                special_nested++;
            }
            if(frame==7950 || frame==8700 || frame==9450 || frame==10450){
                if(ram_word(sound_ram,special_mailbox+60) || ram_word(sound_ram,special_mailbox+92) || ram_word(sound_ram,audio_mailbox+8) || ram_word(sound_ram,audio_mailbox+16)!=3){fprintf(stderr,"Special return failed active=%u paused=%u state=%u\n",ram_word(sound_ram,special_mailbox+60),ram_word(sound_ram,audio_mailbox+8),ram_word(sound_ram,audio_mailbox+16));return exit2(__LINE__);}
                unsigned sequence=ram_word(sound_ram,mailbox+4);if(sequence<=special_return)return exit2(__LINE__);
                special_return=sequence;if(frame==7950)screenshot("special-return");
            }
            continue;
        }
        /* Act 2 is loaded once its act index is set and the world mailbox shows the reset act state (a long load can be observed mid-iteration). */
        if(act2_only && !act2_entry && world_mailbox+544<=sound_size && ram_word(sound_ram,world_mailbox+536)==(act3_only?2u:1u) && !ram_word(sound_ram,world_mailbox+104) && !ram_word(sound_ram,world_mailbox+120)){
            act2_entry=frame;act_sequence=act2_base=ram_word(sound_ram,world_mailbox+540);last_tick=0;
        }
        /* sequence: no gameplay records are read between the Act 1 tally and the Act 2 load. */
        if(sequence_only && act2_only && !act2_entry)continue;
        if(act_only || act2_entry){
            if(world_mailbox+128>sound_size || mailbox+(24+64*21)*4>sound_size)return exit2(__LINE__);
            if(ram_word(sound_ram,mailbox)==0x53434432){
                unsigned sequence=ram_word(sound_ram,mailbox+4);
                if(!act_route_ready){
                    act_era=ram_word(sound_ram,world_mailbox+8);
                    if(act_era!=act_target_era)continue;
                    /* World and trace mailboxes commit at different points. Find the
                       first reset update after our final X pulse, including it even
                       when the world mailbox becomes visible one frame later. */
                    if(sequence-act_era_switch_base>64){fprintf(stderr,"Era entry trace overflow\n");return exit2(__LINE__);}
                    unsigned first=0;
                    for(unsigned n=act_era_switch_base+1;n<=sequence;n++){
                        size_t r=mailbox+(24+(n%64)*21)*4;
                        if(ram_word(sound_ram,r)==n && ram_word(sound_ram,r+36)==1)first=n;
                    }
                    if(!first)continue;
                    /* Discard the short Present prefix used only to reach the existing
                       era-cycle control. The accepted trace starts at the requested
                       era's untouched spawn. */
                    act_route_ready=1;act_sequence=act2_base=first-1;last_tick=0;
                    act2_turned=act2_force=act2_slow=act2_jump=act2_anchor=act2_dash=act2_dash_timer=0;
                    printf("Act 2 era route: era=%u base=%u; entry=Start+C then X\n",act_era,act2_base);
                }
                /* After the Act 3 tally no further records belong to the act trace. */
                if(!act3_end && sequence-act_sequence>64){fprintf(stderr,"Act trace overflow\n");return exit2(__LINE__);}
                while(!act3_end && act_sequence!=sequence){
                    unsigned expected=++act_sequence;size_t record=mailbox+(24+(expected%64)*21)*4;
                    if(ram_word(sound_ram,record)!=expected || ram_word(sound_ram,record+4)!=0xffffffffu || ram_word(sound_ram,record+76)){fprintf(stderr,"Act trace invalid\n");return exit2(__LINE__);}
                    unsigned tick=ram_word(sound_ram,record+80);if(tick<=last_tick){fprintf(stderr,"Act multiple updates per VBlank\n");return exit2(__LINE__);}
                    if(act_pad_count && !act_pad_record){
                        unsigned sim=ram_word(sound_ram,record+36);
                        if(!sim || sim>act_pad_count || ram_word(sound_ram,record+8)!=act_pad_states[sim-1].buttons){fprintf(stderr,"Recorded act controller mismatch at simulation %u: actual=%u\n",sim,ram_word(sound_ram,record+8));return exit2(__LINE__);}
                        for(unsigned i=0;i<16;i++)if(ram_word(sound_ram,record+12+i*4)!=act_pad_states[sim-1].words[i]){
                            fprintf(stderr,"Recorded act state mismatch at simulation %u word %u: %08x != %08x\n",sim,i,ram_word(sound_ram,record+12+i*4),act_pad_states[sim-1].words[i]);return exit2(__LINE__);
                        }
                    }
                    if(last_tick){unsigned gap=tick-last_tick;act_pacing_count++;act_pacing_blanks+=gap;if(gap>1)act_pacing_late++;if(gap>act_pacing_max)act_pacing_max=gap;}last_tick=tick;
                    /* Read all timing context from this committed trace record, never
                       from the separately published world mailbox. This lets the
                       offline checker bind every interval to the replayed state. */
                    printf("Act timing: sequence=%u simulation=%u vblank=%u x=%u y=%u objects=%u\n",
                           expected,ram_word(sound_ram,record+36),tick,
                           ram_word(sound_ram,record+12),ram_word(sound_ram,record+16),
                           ram_word(sound_ram,record+60)>>16);
                    unsigned buttons=ram_word(sound_ram,record+8);fprintf(trace,"%u %u",expected,buttons);
                    if(act_target_era<=3 && expected==act2_base+1 && ram_word(sound_ram,record+36)!=1){fprintf(stderr,"Era route missed the first spawn update\n");return exit2(__LINE__);}
                    for(unsigned i=0;i<16;i++)fprintf(trace," %08x",ram_word(sound_ram,record+12+i*4));fputc('\n',trace);
                    act_elapsed=ram_word(sound_ram,record+36);
                    if(ram_word(sound_ram,record+40) || (ram_word(sound_ram,record+48)>>24)>=6){fprintf(stderr,"Act route died/reset\n");return exit2(__LINE__);}
                }
                unsigned phase=ram_word(sound_ram,world_mailbox+104),elapsed=ram_word(sound_ram,world_mailbox+92),x=ram_word(sound_ram,world_mailbox+52);act_x=x;act_y=ram_word(sound_ram,world_mailbox+72);act_flags=ram_word(sound_ram,world_mailbox+64);act_warp=ram_word(sound_ram,world_mailbox+12);act_era=ram_word(sound_ram,world_mailbox+8);act2_swing_prev=act2_swing;act2_swing=world_mailbox+548<=sound_size?ram_word(sound_ram,world_mailbox+544):0;act_vx=(int16_t)(ram_word(sound_ram,world_mailbox+188)>>16);
                if(act2_travel){
                    unsigned transitions=ram_word(sound_ram,world_mailbox+16),warp=ram_word(sound_ram,world_mailbox+28);
                    if(warp && warp<180 && !act2_arrived){screenshot("act2-travel-cutscene");act2_arrived=1;}
                    if(transitions==1 && act2_arrived==1){act2_arrived=frame;}
                    if(act2_arrived>1 && frame==act2_arrived+60){
                        screenshot("act2-travel-arrival");
                        printf("Act 2 travel: era=%u transitions=%u x=%u y=%u elapsed=%u states=%u\n",ram_word(sound_ram,world_mailbox+8),transitions,x,act_y,act_elapsed,act_sequence-act2_base);
                        p_retro_unload_game();p_retro_deinit();return 0;
                    }
                }
                else if(!act3_only && (ram_word(sound_ram,world_mailbox+8)!=(act_target_era<=3?act_target_era:0) || ram_word(sound_ram,world_mailbox+12)>=210 || ram_word(sound_ram,world_mailbox+16))){fprintf(stderr,"Act route left era %u\n",act_target_era<=3?act_target_era:0);return exit2(__LINE__);}
                if(act3_only){
                    act3_boss_pos=ram_word(sound_ram,world_mailbox+552);act3_boss_status=ram_word(sound_ram,world_mailbox+556);
                    unsigned routine=(act3_boss_status>>8)&255;
                    if(act3_boss_status>>16 && routine==4 && !act3_fight)act3_fight=frame;
                    if(act3_fight && frame==act3_fight+240)screenshot("act3-boss");
                    if(act3_boss_status>>16 && routine==6 && !act3_beaten){act3_beaten=frame;screenshot("act3-boss-defeated");}
                }
                if(act3_only && getenv("SCD_ACT3_DEBUG") && !(frame%120))printf("act3 frame=%u elapsed=%u x=%u y=%u phase=%u boss=%08x status=%08x flags=%u\n",frame,act_elapsed,x,act_y,phase,ram_word(sound_ram,world_mailbox+552),ram_word(sound_ram,world_mailbox+556),act_flags);
                if(act3_end){
                    /* Act 3 ends the zone, and the zone after it loads carrying the
                       score and lives. Palmtree Panic is zone 0, so the next one is
                       zone 1, Collision Chaos, at its Act 1 (act index 0). */
                    if(world_mailbox+572>sound_size)return exit2(__LINE__);
                    unsigned zone=ram_word(sound_ram,world_mailbox+568),act=ram_word(sound_ram,world_mailbox+536);
                    unsigned shown=ram_word(sound_ram,world_mailbox+548);
                    if(act3_end==1 && shown){fprintf(stderr,"Act 3 ended on the end screen instead of advancing to the next zone\n");return exit2(__LINE__);}
                    if(act3_end==1 && zone==1 && act==0){
                        if(!act3_restart_frame)act3_restart_frame=frame;
                        /* Let the title card and the fade settle before the capture. */
                        if(frame>=act3_restart_frame+150){
                            screenshot("act3-next-zone");
                            printf("Act 3 end: advanced to zone %u act %u after %u frames\n",zone,act+1,act3_restart_frame-act_done);
                            p_retro_unload_game();p_retro_deinit();return 0;
                        }
                    }
                    if(frame>act_done+1800){fprintf(stderr,"Act 3 did not reach the next zone: zone=%u act=%u\n",zone,act);return exit2(__LINE__);}
                    continue;
                }
                if(act2_only && getenv("SCD_ACT2_SHOT") && act_elapsed==strtoul(getenv("SCD_ACT2_SHOT"),NULL,10)){char name[32];snprintf(name,sizeof(name),"act2-debug-%u",act_elapsed);screenshot(name);}
                if(!act_sections && act_elapsed>=10){screenshot(act3_only?"act3-spawn":act2_only?"act2-spawn":"act-spawn");act_sections=1;}
                unsigned thresholds[]={2400,3800,5800,8900},thresholds3[]={800,1600,2400,2900};const char *names[]={"act-ramp-clear","act-middle","act-lower-route","act-late-route"},*names2[]={"act2-section1","act2-section2","act2-section3","act2-section4"},*names3[]={"act3-section1","act3-section2","act3-section3","act3-arena"};
                if(act_sections>=1 && act_sections<=4 && x>=(act3_only?thresholds3:thresholds)[act_sections-1]){screenshot(act3_only?names3[act_sections-1]:act2_only?names2[act_sections-1]:names[act_sections-1]);act_sections++;}
                if(phase && !act_sign){act_sign=frame;act_clock=elapsed;screenshot(act3_only?"act3-capsule":act2_only?"act2-signpost":"act-signpost");}
                if(phase && elapsed!=act_clock){fprintf(stderr,"Act clock changed after sign\n");return exit2(__LINE__);}
                if(phase==6 && !act_done)act_done=frame;
                /* The original fades to black on the update after the tally ends. */
                if(act_done && frame==act_done){
                    if(act_pad_count && !act_pad_record && act_elapsed!=act_pad_count){fprintf(stderr,"Recorded act ended before all reference states\n");return exit2(__LINE__);}
                    if(act_pad_record)printf("Re-recorded act length: %u simulation updates from %u reference states\n",act_elapsed,act_pad_count);
                    screenshot(act3_only?"act3-complete":act2_only?"act2-complete":"act-complete");
                    printf("Act pacing: intervals=%u vblanks=%u late=%u max_gap=%u\n",act_pacing_count,act_pacing_blanks,act_pacing_late,act_pacing_max);
                    printf("%s: states=%u elapsed=%u score=%u bonus=%u lives=%u checkpoint=%u sections=%u frames=%u\n",act3_only?"Full Act 3":act2_only?(act_target_era<=3?"Full Act 2 era":"Full Act 2 Present"):"Full Present act",act_sequence-act2_base,elapsed,ram_word(sound_ram,world_mailbox+116),ram_word(sound_ram,world_mailbox+120),(ram_word(sound_ram,world_mailbox+88)>>8)&255,ram_word(sound_ram,world_mailbox+80),act_sections,frame+201);
                    fflush(stdout);
                    if(sequence_only && !act2_only){
                        if(sequence_pad_dir && act_pad_load_sequence(sequence_pad_dir,1))return exit2(__LINE__);
                        /* sequence: the Act 1 tally leads to the fade and Act 2; its trace and captures continue under act2 names. */
                        fclose(trace);snprintf(trace_path,sizeof(trace_path),"%s/act2-target-trace.txt",output_dir);
                        trace=fopen(trace_path,"w");if(!trace)return exit2(__LINE__);
                        act_only=false;act2_only=true;act_sections=act_sign=act_done=act_clock=act_elapsed=0;
                        act_pacing_count=act_pacing_blanks=act_pacing_late=act_pacing_max=0;
                        continue;
                    }
                    if(sequence_only && !act3_only){
                        if(sequence_pad_dir && act_pad_load_sequence(sequence_pad_dir,2))return exit2(__LINE__);
                        /* sequence: the Act 2 tally leads to Act 3 in the future that goodFutureFlags selects
                           (the bad future on a present-only run); SCD_ACT3_ROUTE holds its route areas. */
                        fclose(trace);snprintf(trace_path,sizeof(trace_path),"%s/act3-target-trace.txt",output_dir);
                        trace=fopen(trace_path,"w");if(!trace)return exit2(__LINE__);
                        act3_only=true;act2_entry=0;act_sections=act_sign=act_done=act_clock=act_elapsed=0;
                        act_pacing_count=act_pacing_blanks=act_pacing_late=act_pacing_max=0;
                        act2_dash=act2_force=act2_jump=act2_slow=act2_turned=0;load_route(getenv("SCD_ACT3_ROUTE"));
                        continue;
                    }
                    if(act3_only){act3_end=1;continue;}
                    if(getenv("SCD_SAVE_WAIT_NEXT")){
                        const char *address=getenv("SCD_SAVE_MAILBOX");if(!address)return exit2(__LINE__);
                        size_t at=0x100000+(strtoul(address,NULL,16)&0xfffff);
                        if(at+48>sound_size)return exit2(__LINE__);
                        button_mask=0;for(unsigned wait=0;wait<400;wait++)p_retro_run();
                        save_report(p_retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM),at,mailbox);
                    }
                    break;
                }
            }
            continue;
        }
        if(world_only){
            if(world_mailbox+152>sound_size)return exit2(__LINE__);
            if(frame>=1004 && ram_word(sound_ram,world_mailbox)!=0x574f524c){
                unsigned phase=progress_mailbox?ram_word(sound_ram,progress_mailbox):0,iteration=iteration_mailbox?ram_word(sound_ram,iteration_mailbox):0;
                if(phase!=world_last_phase || iteration!=world_last_iteration){world_stalled=0;world_last_phase=phase;world_last_iteration=iteration;}else world_stalled++;
                /* The 35,400-update Amy clock probe reports real progress.
                   Retain a stall deadline and an absolute bounded deadline. */
                if(++world_wait>12000 || world_stalled>1800 || iteration>35400){screenshot("world-probe-timeout");fprintf(stderr,"World probe completion timed out: status=%08x error=%u phase=%u iteration=%u stalled=%u\n",ram_word(sound_ram,world_mailbox),ram_word(sound_ram,world_mailbox+4),phase,iteration,world_stalled);return exit2(__LINE__);}
                if(!(world_wait%600))printf("World probe progress: frames=%u phase=%u iteration=%u\n",world_wait,phase,iteration);
                frame--;continue;
            }
            if(frame>=1100){
                if(ram_word(sound_ram,world_mailbox)!=0x574f524c || ram_word(sound_ram,world_mailbox+4)){fprintf(stderr,"Target world probe failed at source line %u\n",ram_word(sound_ram,world_mailbox+4));return exit2(__LINE__);}
                world_pass=1;
            }
            if(frame>=1000 && frame<3000 && (frame-1000)%400==80){const char *names[]={"enemy-anton","enemy-patabata","enemy-mosqui","enemy-tamabboh","enemy-tagataga"};screenshot(names[(frame-1000)/400]);}
            if(ram_word(sound_ram,world_mailbox+28) && ram_word(sound_ram,world_mailbox+28)<180){if(!saw_warp)screenshot("travel-cutscene");saw_warp=1;}
            if(frame>3000 && ram_word(sound_ram,world_mailbox+16)==1){if(!saw_arrival)saw_arrival=frame;if(frame==saw_arrival+20)screenshot("travel-arrival");}
            if(frame==3600 && (ram_word(sound_ram,world_mailbox+8)!=0 || !saw_arrival)){fprintf(stderr,"Travel did not arrive: era=%u ticks=%u transitions=%u cancelled=%u\n",ram_word(sound_ram,world_mailbox+8),ram_word(sound_ram,world_mailbox+12),ram_word(sound_ram,world_mailbox+16),ram_word(sound_ram,world_mailbox+20));return exit2(__LINE__);}
            if(frame>=3704){
                if(ram_word(sound_ram,world_mailbox+44)){
                    /* The climb capture follows the entry by 60 gameplay updates; CD seeks can delay VBlanks. */
                    if(!ramp_seen){ramp_seen=frame;ramp_update=ram_word(sound_ram,mailbox+4);screenshot("ramp-entry");}
                    if(!ramp_climb && ram_word(sound_ram,mailbox+4)>=ramp_update+60){ramp_climb=frame;screenshot("ramp-climb");printf("Ramp backdrop/display: %08x\n",ram_word(sound_ram,world_mailbox+60));}
                } else if(ramp_seen && !ramp_exit){ramp_exit=frame;screenshot("ramp-exit");}
                if(ram_word(sound_ram,world_mailbox+48))ramp_scroll=1;
                if(frame==4699 && (!ramp_seen || !ramp_exit || !ramp_scroll || ram_word(sound_ram,world_mailbox+52)<2400)){
                    fprintf(stderr,"Ramp route failed: entry=%u exit=%u scroll=%u x=%u\n",ramp_seen,ramp_exit,ramp_scroll,ram_word(sound_ram,world_mailbox+52));return exit2(__LINE__);
                }
            }
            /* Future floating block: aligned to gameplay updates after the demo
               switch (Start+L2 at frame 5400), not to a frame. The switch's load
               time varies; the block's 2 px/update fall does not. */
            if(frame>=5404 && !future_block_checked){
                unsigned update=ram_word(sound_ram,mailbox+4),fixture=ram_word(sound_ram,world_mailbox+76);
                if(frame==5404)future_block_fixture=fixture;
                if(!future_block_start && fixture!=future_block_fixture)future_block_start=update;
                if(future_block_start && update<future_block_start+80)
                    printf("Future block probe: frame=%u update=%u y=%u rider=%u\n",frame,update,ram_word(sound_ram,world_mailbox+72),ram_word(sound_ram,world_mailbox+68));
                /* SCD_FUTURE_BLOCK_AT (negative control only): check this many
                   updates after the switch; 0 sees the unfallen block (y 450). */
                unsigned check_at=getenv("SCD_FUTURE_BLOCK_AT")?(unsigned)strtoul(getenv("SCD_FUTURE_BLOCK_AT"),NULL,10):60;
                if(future_block_start && update>=future_block_start+check_at){
                    future_block_checked=1;
                    if(ram_word(sound_ram,world_mailbox+68)!=18 || !(ram_word(sound_ram,world_mailbox+64)&8)){
                        fprintf(stderr,"Original placement rider missing on the Future block: type %u flags %u\n",ram_word(sound_ram,world_mailbox+68),ram_word(sound_ram,world_mailbox+64));return exit2(__LINE__);
                    }
                    if(ram_word(sound_ram,world_mailbox+72)<=550){fprintf(stderr,"Future block did not fall (update %u after the switch, y %u)\n",update-future_block_start,ram_word(sound_ram,world_mailbox+72));return exit2(__LINE__);}
                    screenshot("float-future");
                }
                if(frame>=5700 && !future_block_checked){fprintf(stderr,"Future block fixture never started\n");return exit2(__LINE__);}
            }
            if(frame==4800 || frame==5100 || frame==5200 || frame==6000){
                unsigned expected=(frame==5100 || frame==5200)?33:18;
                if(ram_word(sound_ram,world_mailbox+68)!=expected || !(ram_word(sound_ram,world_mailbox+64)&8)){
                    fprintf(stderr,"Original placement rider missing at frame %u: type %u flags %u\n",frame,ram_word(sound_ram,world_mailbox+68),ram_word(sound_ram,world_mailbox+64));return exit2(__LINE__);
                }
                if(frame==5100)platform_x=ram_word(sound_ram,world_mailbox+52);
                if(frame==5200 && ram_word(sound_ram,world_mailbox+52)==platform_x){fprintf(stderr,"Platform did not carry Sonic\n");return exit2(__LINE__);}
                screenshot(frame==4800?"float-past":frame==5100?"platform-ride":frame==5200?"platform-carried":"float-present");
            }
            if(frame==4880 || frame==5280 || frame==6080){
                if(ram_word(sound_ram,world_mailbox+68) || (ram_word(sound_ram,world_mailbox+64)&8)){fprintf(stderr,"Jump retained standing reference at frame %u\n",frame);return exit2(__LINE__);}
                screenshot(frame==4880?"float-jump":frame==5280?"platform-jump":"float-present-jump");
            }
            if(frame==6120)screenshot("float-vanished");
            if(frame>=6304 && frame<7200){
                unsigned id=ram_word(sound_ram,world_mailbox+80),resets=ram_word(sound_ram,world_mailbox+84),life=ram_word(sound_ram,world_mailbox+88);
                if(sonic_view_address && ram_word(sound_ram,world_mailbox+76)==12 &&
                   ram_word(sound_ram,sonic_view_at)==0x534f4e56 &&
                   ram_word(sound_ram,sonic_view_at+8)==ram_word(sound_ram,mailbox+40) &&
                   ram_word(sound_ram,world_mailbox+224)==ram_word(sound_ram,mailbox+40)){
                    printf("Checkpoint state: %u %u",frame,resets);
                    for(unsigned n=0;n<16;n++)printf(" %u",ram_word(sound_ram,mailbox+16+n*4));
                    for(unsigned n=0;n<18;n++)printf(" %u",ram_word(sound_ram,sonic_view_at+n*4));putchar('\n');
                    printf("Checkpoint clock: frame=%u simulation=%u id=%u resets=%u elapsed=%u score=%u rings=%u lives=%u\n",
                        frame,ram_word(sound_ram,world_mailbox+224),id,resets,ram_word(sound_ram,world_mailbox+92),
                        ram_word(sound_ram,world_mailbox+116),ram_word(sound_ram,world_mailbox+128),(life>>8)&255);
                }
                if(id && !checkpoint_seen){checkpoint_seen=frame;checkpoint_x=ram_word(sound_ram,world_mailbox+52);checkpoint_time=ram_word(sound_ram,world_mailbox+92);screenshot("checkpoint-activate");}
                if((life>>16)==6 && !checkpoint_dead){checkpoint_dead=frame;screenshot("checkpoint-death");}
                if(resets && !checkpoint_return){
                    checkpoint_return=frame;
                    if(id!=2 || (life&0xff00)!=0x200 || ram_word(sound_ram,world_mailbox+52)!=checkpoint_x || ram_word(sound_ram,world_mailbox+92)!=checkpoint_time/60*60){fprintf(stderr,"Checkpoint restore mismatch: id=%u life=%x x=%u/%u time=%u/%u\n",id,life,ram_word(sound_ram,world_mailbox+52),checkpoint_x,ram_word(sound_ram,world_mailbox+92),checkpoint_time/60*60);return exit2(__LINE__);}
                }
                if(checkpoint_return && frame==checkpoint_return+3)screenshot("checkpoint-respawn");
                if(checkpoint_return && frame==checkpoint_return+20)screenshot("checkpoint-restored");
                if(frame==7199 && (!checkpoint_seen || !checkpoint_dead || !checkpoint_return)){fprintf(stderr,"Checkpoint route incomplete: %u %u %u, x=%u y=%u life=%x\n",checkpoint_seen,checkpoint_dead,checkpoint_return,ram_word(sound_ram,world_mailbox+52),ram_word(sound_ram,world_mailbox+72),life);return exit2(__LINE__);}
            }
            if(frame>=7204 && frame<8800){
                unsigned route=frame>=8000,base=route?8000:7200,tick=frame-base;
                unsigned broken=ram_word(sound_ram,world_mailbox+96),debris=ram_word(sound_ram,world_mailbox+100),x=ram_word(sound_ram,world_mailbox+52);
                if(tick==140){
                    if(broken || x!=(route?8646u:3558u)){fprintf(stderr,"Wall side collision failed: route=%u x=%u broken=%u\n",route,x,broken);return exit2(__LINE__);}
                    screenshot(route?"wall-present-solid":"wall-past-solid");
                }
                if(debris && !wall_burst[route])wall_burst[route]=frame;
                if(wall_burst[route] && frame==wall_burst[route]+8)screenshot(route?"wall-present-break":"wall-past-break");
                if(tick==600){
                    if(broken!=(route?2u:3u) || !wall_burst[route] || x<=(route?8730u:3674u) || ram_word(sound_ram,world_mailbox+84)){
                        fprintf(stderr,"Original wall route failed: route=%u x=%u broken=%u debris=%u\n",route,x,broken,debris);return exit2(__LINE__);
                    }
                    wall_pass[route]=1;screenshot(route?"wall-present-passed":"wall-past-passed");
                }
            }
            if(frame>=8804 && frame<11100 && !(frame>=10000 && frame<10004)){
                unsigned expected_fixture=frame>=10000?16:15;
                if(ram_word(sound_ram,world_mailbox+76)!=expected_fixture){
                    sound_track=0;
                    if(++finish_wait>1800){fprintf(stderr,"Finish fixture load timed out\n");return exit2(__LINE__);}
                    frame--;continue;
                }
                unsigned route=frame>=10000,phase=ram_word(sound_ram,world_mailbox+104),elapsed=ram_word(sound_ram,world_mailbox+92);
                unsigned score=ram_word(sound_ram,world_mailbox+116),life=ram_word(sound_ram,world_mailbox+88);
                finish_route=route;sound_track=ram_word(sound_ram,audio_mailbox+16)==3?ram_word(sound_ram,audio_mailbox+20):0;
                if(sound_track==6){finish_music[route]=1;if(ram_word(sound_ram,audio_mailbox+28)){fprintf(stderr,"Results music repeats\n");return exit2(__LINE__);}}
                else if(finish_music[route])finish_stopped[route]=1;
                if(phase>6 || (life>>16)>=4 || ram_word(sound_ram,world_mailbox+84)){fprintf(stderr,"Finish route hurt/reset\n");return exit2(__LINE__);}
                if(phase && !finish_seen[route][phase]){
                    finish_seen[route][phase]=frame;
                    if(phase==1){finish_clock[route]=elapsed;screenshot(route?"finish-good-sign":"finish-present-sign");}

                }
                if(phase && elapsed!=finish_clock[route]){fprintf(stderr,"Finish clock changed frame=%u route=%u phase=%u elapsed=%u expected=%u seen=%u fixture=%u x=%u\n",frame,route,phase,elapsed,finish_clock[route],finish_seen[route][1],ram_word(sound_ram,world_mailbox+76),ram_word(sound_ram,world_mailbox+52));return exit2(__LINE__);}
                if(finish_seen[route][1] && frame==finish_seen[route][1]+30)screenshot(route?"finish-good-spin":"finish-present-spin");
                if(finish_seen[route][6] && frame==finish_seen[route][6]+3)screenshot(route?"finish-good-done":"finish-present-done");
                if(finish_seen[route][5] && frame==finish_seen[route][5]+60)screenshot(route?"finish-good-tally":"finish-present-tally");
                if(phase==6){
                    if(score!=52300 || (life&0xff00)!=0x400 || ram_word(sound_ram,world_mailbox+108) || ram_word(sound_ram,world_mailbox+112) || ram_word(sound_ram,world_mailbox+120)!=52300){fprintf(stderr,"Finish totals wrong: score=%u life=%x\n",score,life);return exit2(__LINE__);}
                    finish_pass[route]=1;
                }
            }
            if(frame>=15604 && frame<16800){
                unsigned route=(frame-15600)/300,tick=(frame-15600)%300;
                unsigned expected_fixture=22+route;
                if(ram_word(sound_ram,world_mailbox+76)!=expected_fixture){if(++collapse_wait>1800){fprintf(stderr,"Collapse fixture timed out\n");return exit2(__LINE__);}frame--;continue;}
                unsigned state=ram_word(sound_ram,world_mailbox+144),live=ram_word(sound_ram,world_mailbox+148);
                char name[40];
                if(tick==10){
                    if(state || live){fprintf(stderr,"Collapse triggered before intact sample: %u %x\n",route,state);return exit2(__LINE__);}
                    snprintf(name,sizeof(name),"collapse-%u-intact",route);screenshot(name);collapse_intact[route]=1;
                }
                if((state>>16) && !collapse_seen[route]){
                    unsigned expected=route==1?10:route==2?6:18;
                    if(state!=(0x10000u|expected) || live!=expected){fprintf(stderr,"Collapse piece count wrong: %u %x %u\n",route,state,live);return exit2(__LINE__);}
                    collapse_seen[route]=frame;
                }
                if(collapse_seen[route] && frame==collapse_seen[route]+20){snprintf(name,sizeof(name),"collapse-%u-break",route);screenshot(name);}
                if(tick==280){
                    if(!collapse_seen[route] || live || state>>16!=1 || ram_word(sound_ram,world_mailbox+68)==32){fprintf(stderr,"Collapse lifecycle failed: %u %x %u\n",route,state,live);return exit2(__LINE__);}
                    snprintf(name,sizeof(name),"collapse-%u-fallen",route);screenshot(name);collapse_pass[route]=1;
                }
            }
            if(frame>=16804 && frame<18000){
                unsigned route=(frame-16800)/300,tick=(frame-16800)%300;
                unsigned expected_fixture=26+route;
                if(ram_word(sound_ram,world_mailbox+76)!=expected_fixture){if(++tunnel_wait>1800){fprintf(stderr,"Tunnel fixture timed out\n");return exit2(__LINE__);}frame--;continue;}
                unsigned control=ram_word(sound_ram,world_mailbox+152);
                unsigned x=ram_word(sound_ram,world_mailbox+52),y=ram_word(sound_ram,world_mailbox+72);
                if(control){
                    if(control!=(route<2?193u:129u) || tunnel_pass[route]){fprintf(stderr,"Tunnel control flags wrong: %u %u\n",route,control);return exit2(__LINE__);}
                    tunnel_seen[route]=1;
                }else if(tunnel_seen[route] && !tunnel_pass[route]){
                    if(x!=(route<2?5888u:4400u) || y!=(route<2?752u:456u)){fprintf(stderr,"Tunnel exit wrong: %u %u,%u\n",route,x,y);return exit2(__LINE__);}
                    tunnel_exit[route]=frame;tunnel_pass[route]=1;
                }
                if(tunnel_exit[route] && frame==tunnel_exit[route]+3){char name[40];snprintf(name,sizeof(name),"tunnel-%u-exit",route);screenshot(name);}
                if(tick==20){
                    if(!control){fprintf(stderr,"Tunnel never captured player\n");return exit2(__LINE__);}
                    char name[40];snprintf(name,sizeof(name),"tunnel-%u-moving",route);screenshot(name);
                    unsigned center=ram_word(sound_ram,world_mailbox+200);
                    printf("Tunnel presentation: route=%u screen=%d,%d\n",route,(int16_t)(center>>16),(int16_t)center);
                }
                if(tick==250 && !tunnel_pass[route]){fprintf(stderr,"Tunnel did not release player\n");return exit2(__LINE__);}
            }
            if(frame>=18004 && frame<18900){
                unsigned route=(frame-18000)/300,tick=(frame-18000)%300;
                unsigned expected_fixture=30+route;
                if(ram_word(sound_ram,world_mailbox+76)!=expected_fixture){if(++disc_wait>1800){fprintf(stderr,"Disc fixture timed out\n");return exit2(__LINE__);}frame--;continue;}
                unsigned control=ram_word(sound_ram,world_mailbox+152),pose=ram_word(sound_ram,world_mailbox+156)&255;
                unsigned standing=ram_word(sound_ram,world_mailbox+68),life=ram_word(sound_ram,world_mailbox+88);
                if(control){
                    if(control!=1 || standing!=9 || pose>=6 || (life>>16)>=4){fprintf(stderr,"Invalid controlled disc state %u %u %u %u\n",route,control,standing,pose);return exit2(__LINE__);}
                    if(!disc_seen[route])disc_seen[route]=frame;
                    /* patcnt is the object's NEXT pose. Capture each original
                       mapping when the player dispatcher actually displays it,
                       never relabel the first contact's old walking picture. */
                    static const unsigned disc_maps[6]={26,27,28,31,29,30};
                    if(!sonic_view_address || ram_word(sound_ram,sonic_view_at)!=0x534F4E56)return exit2(__LINE__);
                    unsigned shown=ram_word(sound_ram,sonic_view_at+12);
                    for(unsigned p=0;p<6;p++)if(shown==disc_maps[p] && !(disc_poses[route]&(1u<<p))){
                        disc_pose_due[route][p]=frame+1;disc_poses[route]|=1u<<p;
                        printf("Disc submitted: route=%u pose=%u frame=%u",route,p,frame);for(unsigned k=0;k<18;k++)printf(" %u",ram_word(sound_ram,sonic_view_at+k*4));putchar('\n');
                    }
                }else if(disc_seen[route] && !disc_exit[route]){
                    if(disc_poses[route]!=63 || (route<2 && (tick<100 || tick>105)) || (route==2 && tick<100)){fprintf(stderr,"Disc released incorrectly: route=%u tick=%u poses=%x\n",route,tick,disc_poses[route]);return exit2(__LINE__);}
                    disc_exit[route]=frame;
                }
                for(unsigned captured=0;captured<6;captured++)if(disc_pose_due[route][captured]==frame){
                    char name[48];snprintf(name,sizeof(name),"disc-%u-pose-%u",route,captured);screenshot(name);
                    printf("Disc photographed: route=%u pose=%u frame=%u",route,captured,frame);for(unsigned k=0;k<18;k++)printf(" %u",ram_word(sound_ram,sonic_view_at+k*4));putchar('\n');
                    if(route==0 && captured==0){
                        size_t bytes=p_retro_serialize_size();void *state=malloc(bytes);if(!state || !p_retro_serialize(state,bytes))return exit2(__LINE__);
                        char path[4096];snprintf(path,sizeof(path),"%s/disc-native.state",output_dir);FILE *file=fopen(path,"wb");
                        if(!file || fwrite(state,1,bytes,file)!=bytes || fclose(file))return exit2(__LINE__);free(state);
                    }
                }
                if(disc_exit[route] && frame==disc_exit[route]+3){
                    char name[40];snprintf(name,sizeof(name),"disc-%u-release",route);screenshot(name);printf("Disc release pose: route=%u pose=%u\n",route,pose);
                    if(standing==9){fprintf(stderr,"Disc retained rider after release\n");return exit2(__LINE__);}
                    disc_pass[route]=1;
                }
                if(tick==280 && !disc_pass[route]){fprintf(stderr,"Disc fixture did not finish\n");return exit2(__LINE__);}
            }
            if(frame>=18904 && frame<20400){
                unsigned route=(frame-18900)/300,tick=(frame-18900)%300;
                unsigned expected_fixture=33+route;
                if(ram_word(sound_ram,world_mailbox+76)!=expected_fixture){if(++door_wait>1800){fprintf(stderr,"Door/spring fixture timed out\n");return exit2(__LINE__);}frame--;continue;}
                unsigned state=ram_word(sound_ram,world_mailbox+160),xy=ram_word(sound_ram,world_mailbox+164);
                unsigned action=ram_word(sound_ram,world_mailbox+(route<3?172:180));
                if(action)door_action[route]=1;
                if(state!=0xffffffff){
                    unsigned type=route<2?13:route==2?53:15,pose=state&255;
                    if(state>>8!=type || pose>1){fprintf(stderr,"Invalid door/spring state %u %u\n",route,state);return exit2(__LINE__);}
                    if(!(door_frames[route]&(1u<<pose))){door_frames[route]|=1u<<pose;door_due[route][pose]=frame+1;door_xy[route][pose]=xy;}
                }
                for(unsigned pose=0;pose<2;pose++)if(door_due[route][pose]==frame){
                    if(!pose && !door_enable_wait[route] && video_black()){
                        door_enable_wait[route]=1;door_due[route][pose]++;
                        printf("Initial display enable: door route=%u wait=1\n",route);continue;
                    }
                    char name[40];snprintf(name,sizeof(name),"door-spring-%u-frame-%u",route,pose);screenshot(name);
                    printf("Door/spring pixels: route=%u pose=%u x=%d y=%d\n",route,pose,(int16_t)(door_xy[route][pose]>>16),(int16_t)door_xy[route][pose]);
                }
                if(tick==280 && (door_frames[route]!=3 || !door_action[route])){fprintf(stderr,"Door/spring route failed: route=%u frames=%u action=%u x=%u y=%u\n",route,door_frames[route],door_action[route],ram_word(sound_ram,world_mailbox+52),ram_word(sound_ram,world_mailbox+72));return exit2(__LINE__);}
            }
            if(frame>=24904){
                unsigned tick=frame-24900;
                if(ram_word(sound_ram,world_mailbox+76)!=0){if(++amy_wait>1800){fprintf(stderr,"Amy fixture timed out\n");return exit2(__LINE__);}frame--;continue;}
                unsigned control=ram_word(sound_ram,world_mailbox+152),grabs=ram_word(sound_ram,world_mailbox+520);
                if(control&1)amy_hold++;
                if(tick>=624 && !control && (int16_t)ram_word(sound_ram,world_mailbox+188)<0)amy_jump=1;
                if((ram_word(sound_ram,world_mailbox+88)>>16)>=4 || ram_word(sound_ram,world_mailbox+84)){fprintf(stderr,"Amy fixture hurt/reset\n");return exit2(__LINE__);}
                int capture=tick==32?0:tick==334?1:tick==440?2:-1;
                if(capture>=0){
                    if(!(control&1) || !grabs || !ram_word(sound_ram,world_mailbox+528)){fprintf(stderr,"Amy did not hold/palette at %u\n",tick);return exit2(__LINE__);}
                    unsigned *snap=amy_snapshot[capture];snap[0]=ram_word(sound_ram,world_mailbox+8);snap[1]=ram_word(sound_ram,world_mailbox+224);snap[2]=ram_word(sound_ram,world_mailbox+228);
                    if(snap[2]>24)return exit2(__LINE__);
                    for(unsigned n=0;n<snap[2]*3;n++)snap[3+n]=ram_word(sound_ram,world_mailbox+(58+n)*4);
                    amy_due[capture]=frame+1;
                }
                for(unsigned c=0;c<3;c++)if(amy_due[c]==frame){
                    unsigned *snap=amy_snapshot[c];char name[32];snprintf(name,sizeof(name),"amy-hold-%u",c);screenshot(name);
                    printf("Amy pixels: capture=%u era=%u clock=%u count=%u\n",c,snap[0],snap[1],snap[2]);
                    for(unsigned n=0;n<snap[2];n++)printf("Amy sprite: capture=%u data=%u world=%u screen=%u\n",c,snap[3+n*3],snap[4+n*3],snap[5+n*3]);
                }
                if(tick==790){if(amy_hold<600 || !amy_jump || !grabs){fprintf(stderr,"Amy controller failed hold=%u jump=%u grabs=%u\n",amy_hold,amy_jump,grabs);return exit2(__LINE__);}printf("Amy controller: hold=%u jump=%u grabs=%u hearts=%u\n",amy_hold,amy_jump,grabs,ram_word(sound_ram,world_mailbox+524));}
            }
            if(frame>=23704 && frame<24900){
                unsigned route=(frame-23700)/300,tick=(frame-23700)%300;
                if(ram_word(sound_ram,world_mailbox+76)!=(49+route)){
                    if(projector_wait%300==0)fprintf(stderr,"Projector wait: route=%u fixture=%u simulation=%u world=%u,%u\n",route,ram_word(sound_ram,world_mailbox+76),ram_word(sound_ram,world_mailbox+224),ram_word(sound_ram,world_mailbox+52),ram_word(sound_ram,world_mailbox+72));
                    if(++projector_wait>1800){
                        screenshot("projector-timeout");
                        size_t bytes=p_retro_serialize_size();void *state=malloc(bytes);
                        if(!state || !p_retro_serialize(state,bytes))return exit2(__LINE__);
                        char path[1024];snprintf(path,sizeof(path),"%s/projector-timeout.state",output_dir);
                        FILE *file=fopen(path,"wb");if(!file)return exit2(__LINE__);
                        if(fwrite(state,1,bytes,file)!=bytes || fclose(file))return exit2(__LINE__);
                        free(state);
                        uint32_t *cpu=dlsym(core,"CPU");if(cpu)fprintf(stderr,"SH2 PC=%08x SP=%08x SR=%08x\n",cpu[16],cpu[15],cpu[17]);
                        fprintf(stderr,"Projector/animal fixture timed out\n");return exit2(__LINE__);
                    }frame--;continue;
                }
                unsigned done=ram_word(sound_ram,world_mailbox+204),hits=ram_word(sound_ram,world_mailbox+208),explosions=ram_word(sound_ram,world_mailbox+212),holo=ram_word(sound_ram,world_mailbox+216),animals=ram_word(sound_ram,world_mailbox+220);
                if(route==0){
                    if(hits && !projector_hit){projector_hit=tick;printf("Projector controller hit: tick=%u\n",tick);}
                    if(done && !projector_done){
                        projector_done=tick;
                        if(!projector_hit || tick-projector_hit!=101 || explosions!=12 || holo){fprintf(stderr,"Projector destruction timing failed: hit=%u done=%u explosions=%u holo=%u\n",projector_hit,tick,explosions,holo);return exit2(__LINE__);}
                        printf("Projector controller complete: tick=%u explosions=%u\n",tick,explosions);
                    }
                    if(tick==20 && (holo!=4 || animals || hits)){fprintf(stderr,"Projector initial presence failed\n");return exit2(__LINE__);}
                }
                /* The first two captures follow the fixture clock (18 and 30), which starts a
                   variable number of frames after the fixture ID appears. */
                unsigned clock=ram_word(sound_ram,world_mailbox+224);
                int capture=route==0?(clock==18 && !projector_due[0]?0:clock==30 && !projector_due[1]?1:projector_hit && tick==projector_hit+8?2:projector_done && tick==projector_done+10?3:-1):route==1 && tick==12?4:route==2 && tick==12?5:-1;
                if(capture>=0){
                    if(route==0 && capture==3 && animals!=2){fprintf(stderr,"Projector animal release failed\n");return exit2(__LINE__);}
                    unsigned *snapshot=projector_snapshot[capture];
                    snapshot[0]=ram_word(sound_ram,world_mailbox+8);snapshot[1]=ram_word(sound_ram,world_mailbox+224);snapshot[2]=ram_word(sound_ram,world_mailbox+228);
                    if(snapshot[2]>24)return exit2(__LINE__);
                    for(unsigned n=0;n<snapshot[2]*3;n++)snapshot[3+n]=ram_word(sound_ram,world_mailbox+(58+n)*4);
                    if(!sonic_view_address || ram_word(sound_ram,sonic_view_at)!=0x534F4E56)return exit2(__LINE__);
                    for(unsigned n=0;n<18;n++)projector_sonic[capture][n]=ram_word(sound_ram,sonic_view_at+n*4);
                    projector_due[capture]=frame+1;
                }
                for(unsigned c=0;c<6;c++)if(projector_due[c]==frame){
                    unsigned *snapshot=projector_snapshot[c];char name[40];snprintf(name,sizeof(name),"projector-animal-%u",c);screenshot(name);
                    printf("Projector pixels: capture=%u era=%u clock=%u count=%u\n",c,snapshot[0],snapshot[1],snapshot[2]);
                    for(unsigned n=0;n<snapshot[2];n++)printf("Projector sprite: capture=%u data=%u world=%u screen=%u\n",c,snapshot[3+n*3],snapshot[4+n*3],snapshot[5+n*3]);
                    printf("Projector Sonic: capture=%u",c);
                    for(unsigned n=0;n<18;n++)printf(" %u",projector_sonic[c][n]);
                    printf("\n");
                }
                if(tick==280){
                    if((route==0 && (!done || animals!=2 || holo || explosions!=12)) || ((route==1 || route==2) && animals!=1) || (route==3 && (animals || ram_word(sound_ram,world_mailbox+40)))){fprintf(stderr,"Projector/animal route failed: route=%u done=%u animals=%u holo=%u explosions=%u\n",route,done,animals,holo,explosions);return exit2(__LINE__);}
                    projector_pass[route]=1;
                }
            }
            if(frame>=20404 && frame<23700){
                unsigned route=(frame-20400)/300,tick=(frame-20400)%300;
                unsigned expected_fixture=38+route;
                if(ram_word(sound_ram,world_mailbox+76)!=expected_fixture){if(++scenery_wait>1800){fprintf(stderr,"Tag/scenery fixture timed out\n");return exit2(__LINE__);}frame--;continue;}
                if(route<2){
                    unsigned center=ram_word(sound_ram,world_mailbox+200);
                    printf("Camera sample: route=%u tick=%u simulation=%u world=%d,%d screen=%d,%d flags=%u\n",route,tick,
                        ram_word(sound_ram,world_mailbox+224),(int)ram_word(sound_ram,world_mailbox+52),
                        (int)ram_word(sound_ram,world_mailbox+72),(int16_t)(center>>16),(int16_t)center,
                        ram_word(sound_ram,world_mailbox+64));
                    tag_camera[route][2][0]=tag_camera[route][1][0];tag_camera[route][2][1]=tag_camera[route][1][1];
                    tag_camera[route][1][0]=tag_camera[route][0][0];tag_camera[route][1][1]=tag_camera[route][0][1];
                    tag_camera[route][0][0]=(int)ram_word(sound_ram,world_mailbox+52)-(int16_t)(center>>16);
                    tag_camera[route][0][1]=(int)ram_word(sound_ram,world_mailbox+72)-(int16_t)center;
                }
                if(!scenery_due[route] && !scenery_pass[route]){
                    if(route<2){
                        unsigned contacts=ram_word(sound_ram,world_mailbox+184),velocity=ram_word(sound_ram,world_mailbox+188),flags=ram_word(sound_ram,world_mailbox+64);
                        int speed=route?(int16_t)velocity:(int16_t)(velocity>>16);
                        if(contacts){
                            if(speed!=(route?3328:2560) || !(flags&4) || ram_word(sound_ram,world_mailbox+196)!=2){fprintf(stderr,"Tag velocity/roll mismatch: route=%u speed=%d flags=%u\n",route,speed,flags);return exit2(__LINE__);}
                            scenery_due[route]=frame+2;
                            printf("Tag activation: route=%u velocity=%d contacts=%u\n",route,speed,contacts);
                            unsigned center=ram_word(sound_ram,world_mailbox+200);
                            printf("Tag camera: route=%u x=%d y=%d\n",route,(int)ram_word(sound_ram,world_mailbox+52)-(int16_t)(center>>16),(int)ram_word(sound_ram,world_mailbox+72)-(int16_t)center);
                        }
                    }else{
                        unsigned state=ram_word(sound_ram,world_mailbox+160),type=route>=6 && route<=9?50:51;
                        unsigned pose=route==4 || route==5?1:route==7?1:route==8 || route==9?2:0;
                        /* The fixture index is written before sprite_draw records the feature object; a
                           frame sampled between the two reads no object (all ones). */
                        if(state==0xffffffffu && tick<30)continue;
                        /* Likewise a sample can still hold the previous route's feature object. */
                        unsigned previous_type=route-1>=6 && route-1<=9?50:51,previous_pose=route-1==4 || route-1==5?1:route-1==7?1:route-1==8 || route-1==9?2:0;
                        if(tick<30 && route>2 && state==(previous_type<<8|previous_pose))continue;
                        if(state!=(type<<8|pose)){fprintf(stderr,"Scenery frame mismatch: route=%u state=%u\n",route,state);return exit2(__LINE__);}
                        if(route==10){
                            if(!sonic_view_address)return exit2(__LINE__);
                            if(ram_word(sound_ram,sonic_view_at)!=0x534F4E56 || ram_word(sound_ram,sonic_view_at+8)!=ram_word(sound_ram,world_mailbox+224))continue;
                            for(unsigned k=0;k<18;k++)scenery_sonic[route][k]=ram_word(sound_ram,sonic_view_at+k*4);
                        }
                        scenery_xy[route]=ram_word(sound_ram,world_mailbox+164);scenery_player[route]=ram_word(sound_ram,world_mailbox+200);scenery_due[route]=frame+1;
                    }
                }
                if(route<2 && scenery_due[route] && frame>=scenery_due[route] && frame<scenery_due[route]+16){
                    char name[64];snprintf(name,sizeof(name),"camera-%u-tick-%u",route,tick);screenshot(name);
                    if(frame==scenery_due[route]){
                        size_t bytes=p_retro_serialize_size();void *state=malloc(bytes);
                        if(!state || !p_retro_serialize(state,bytes)){fprintf(stderr,"Camera state capture failed\n");return exit2(__LINE__);}
                        char path[1024];snprintf(path,sizeof(path),"%s/%s.state",output_dir,name);
                        FILE *file=fopen(path,"wb");if(!file)return exit2(__LINE__);
                        if(fwrite(state,1,bytes,file)!=bytes || fclose(file)){fprintf(stderr,"Camera state write failed\n");return exit2(__LINE__);}
                        free(state);
                    }
                }
                if(scenery_due[route]==frame){
                    if(route>=2 && !scenery_enable_wait[route] && video_black()){
                        scenery_enable_wait[route]=1;scenery_due[route]++;
                        printf("Initial display enable: scenery route=%u wait=1\n",route);continue;
                    }
                    char name[40];snprintf(name,sizeof(name),"tag-scenery-%u",route);screenshot(name);scenery_pass[route]=1;
                    if(route<2)for(unsigned lag=0;lag<3;lag++)printf("Tag presentation: route=%u lag=%u camera=%d,%d\n",route,lag,tag_camera[route][lag][0],tag_camera[route][lag][1]);
                    if(route>=2)printf("Scenery pixels: route=%u x=%d y=%d player=%d,%d\n",route,(int16_t)(scenery_xy[route]>>16),(int16_t)scenery_xy[route],(int16_t)(scenery_player[route]>>16),(int16_t)scenery_player[route]);
                    if(route==10){printf("Scenery Sonic:");for(unsigned k=0;k<18;k++)printf(" %u",scenery_sonic[route][k]);putchar('\n');}
                }
                if(tick==280 && !scenery_pass[route]){fprintf(stderr,"Tag/scenery fixture did not complete %u\n",route);return exit2(__LINE__);}
            }
            if(frame>=11204 && frame<15600){
                unsigned route=frame<11600?0:frame<12000?1:frame<12400?2:frame<14000?3:4;
                unsigned base=route<3?11200+route*400:route==3?12400:14000,tick=frame-base;
                if(tick>=4){
                    unsigned expected_fixture=17+route;
                    if(ram_word(sound_ram,world_mailbox+76)!=expected_fixture){if(++monitor_wait>1800){fprintf(stderr,"Monitor fixture timed out\n");return exit2(__LINE__);}frame--;continue;}
                    monitor_route=route;sound_track=ram_word(sound_ram,audio_mailbox+16)==3?ram_word(sound_ram,audio_mailbox+20):0;
                    unsigned state=ram_word(sound_ram,world_mailbox+136),power=ram_word(sound_ram,world_mailbox+132);
                    if(tick>=58 && tick<80){
                        unsigned art=ram_word(sound_ram,world_mailbox+160),xy=ram_word(sound_ram,world_mailbox+164);
                        printf("Monitor pixels: route=%u tick=%u art=%u x=%d y=%d\n",route,tick,art,(int16_t)(xy>>16),(int16_t)xy);
                        if(!sonic_view_address || ram_word(sound_ram,sonic_view_at)!=0x534F4E56)return exit2(__LINE__);
                        printf("Monitor Sonic: route=%u tick=%u",route,tick);
                        for(unsigned k=0;k<18;k++)printf(" %u",ram_word(sound_ram,sonic_view_at+k*4));putchar('\n');
                        if(tick>=60){char name[48];snprintf(name,sizeof(name),"monitor-%u-pose-%u",route,tick);screenshot(name);}
                    }
                    if((ram_word(sound_ram,world_mailbox+88)>>16)>=4 || ram_word(sound_ram,world_mailbox+84)){fprintf(stderr,"Monitor fixture hurt/reset\n");return exit2(__LINE__);}
                    if(tick==70){
                        if(route==0){
                            uint16_t (*read_vdp1)(uint32_t)=dlsym(core,"VDP1_Read16_DB");
                            if(!read_vdp1){fprintf(stderr,"Missing VDP1 readback symbol\n");return exit2(__LINE__);}
                            char path[1024];snprintf(path,sizeof(path),"%s/monitor-vdp1.bin",output_dir);
                            FILE *dump=fopen(path,"wb");if(!dump)return exit2(__LINE__);
                            for(unsigned word=0;word<0x40000;word++){uint16_t value=read_vdp1(word*2);fputc(value>>8,dump);fputc(value&255,dump);}
                            if(fclose(dump))return exit2(__LINE__);
                        }
                        if(state || ram_word(sound_ram,world_mailbox+68)!=25){fprintf(stderr,"Monitor did not support Sonic route=%u state=%x standing=%u\n",route,state,ram_word(sound_ram,world_mailbox+68));return exit2(__LINE__);}
                        char name[40];snprintf(name,sizeof(name),"monitor-%u-intact",route);screenshot(name);
                    }
                    if(route==2 && tick==222)screenshot("monitor-shield-visible");
                    if(tick==220){
                        if(state!=0x10001 || ((ram_word(sound_ram,world_mailbox+88)>>8)&255)!=(route==0?4u:3u) || ram_word(sound_ram,world_mailbox+128)!=(route==1?10u:0u) || ram_word(sound_ram,world_mailbox+140)!=(route==2)){
                            fprintf(stderr,"Monitor grant mismatch route=%u state=%x power=%x rings=%u life=%x shield=%u\n",route,state,power,ram_word(sound_ram,world_mailbox+128),ram_word(sound_ram,world_mailbox+88),ram_word(sound_ram,world_mailbox+140));return exit2(__LINE__);
                        }
                        if((route==3 && !(power>>16)) || (route==4 && !(power&65535)))return exit2(__LINE__);
                        monitor_pass[route]=1;char name[40];snprintf(name,sizeof(name),"monitor-%u-granted",route);screenshot(name);
                    }
                    if(route>=3){
                        if(sound_track==(route==3?8u:7u)){monitor_music[route]=1;if(ram_word(sound_ram,audio_mailbox+28)){fprintf(stderr,"Power-up music repeats\n");return exit2(__LINE__);}}
                        if(monitor_music[route] && !power && sound_track==3)monitor_return[route]=1;
                        if(tick==1580){
                            if(!monitor_return[route] || !monitor_energy[route]){fprintf(stderr,"Power-up expiration/music restore failed route=%u power=%x track=%u return=%u energy=%llu\n",route,power,sound_track,monitor_return[route],(unsigned long long)monitor_energy[route]);return exit2(__LINE__);}
                            char name[40];snprintf(name,sizeof(name),"monitor-%u-expired",route);screenshot(name);
                        }
                    }
                }
            }
            if(frame==11130){
                if(ram_word(sound_ram,world_mailbox+8) || ram_word(sound_ram,world_mailbox+104) || ram_word(sound_ram,world_mailbox+116) || ram_word(sound_ram,world_mailbox+124) || (ram_word(sound_ram,world_mailbox+88)&0xff00)!=0x300){fprintf(stderr,"Finish replay failed\n");return exit2(__LINE__);}
                screenshot("finish-replay");
            }
            continue;
        }
        if(frame==1000) {
            if(ram_word(sound_ram,audio_mailbox)!=1 || ram_word(sound_ram,audio_mailbox+4)!=1 || ram_word(sound_ram,audio_mailbox+32)!=1 || ram_word(sound_ram,audio_mailbox+36)!=1){fprintf(stderr,"Sound bank/TOC validation failed\n");return exit2(__LINE__);}
            printf("Original sound bank and seven audio tracks loaded\n");
        }
        unsigned actual=ram_word(sound_ram,audio_mailbox+20),state=ram_word(sound_ram,audio_mailbox+16);
        sound_track=state==3?actual:0;
        if(diagnostic_only) {
            if(frame==1080)screenshot("audio-diagnostics");
            if(frame==1660 && (state!=3 || ram_word(sound_ram,audio_mailbox+8)))return exit2(__LINE__);
            continue;
        }
        if(audio_only) {
            if(sound_track>=2 && sound_track<=5) {
                unsigned count=ram_word(sound_ram,audio_mailbox+28);
                if(count>repeats[sound_track-2])repeats[sound_track-2]=count;
            }
            if(frame==1300)paused_fad=ram_word(sound_ram,audio_mailbox+24);
            if(frame==1400)paused_fad_end=ram_word(sound_ram,audio_mailbox+24);
            if(frame==1000 || frame==14600 || frame==15200 || frame==15800) {
                unsigned expected=frame==1000?2:frame==14600?3:frame==15200?4:5;
                if(actual!=expected || state!=3){fprintf(stderr,"Wrong music track %u, state %u at frame %u\n",actual,state,frame);return exit2(__LINE__);}
            }
            continue;
        }
        if(frame==805)screenshot("player-walk");
        if(frame==825)screenshot("player-jump");
        if(frame==923)screenshot("controller-dash-ready");
        if(frame==938)screenshot("controller-dash-release");
        if(frame==999)screenshot("present");
        if(frame==1130)screenshot("camera-right");
        if(frame==1220)screenshot("past");
        if(frame==1320)screenshot("good-future");
        if(frame==1420)screenshot("bad-future");
        if(frame==1550 || frame==1680){
            if(!floor_mailbox || !sound_ram || floor_mailbox+16>p_retro_get_memory_size(RETRO_MEMORY_SYSTEM_RAM) || ram_word(sound_ram,floor_mailbox)!=0x464c4f52 || ram_word(sound_ram,floor_mailbox+4) || ram_word(sound_ram,floor_mailbox+8)!=3336674757u || ram_word(sound_ram,floor_mailbox+12)!=65536){fprintf(stderr,"Decoded floor VRAM verification failed\n");return exit2(__LINE__);}
            printf("Floor VRAM: frame=%u words=65536 errors=0 hash=3336674757\n",frame);
        }
        if(frame==1550)screenshot("floor");
        if(frame==1680)screenshot("floor-motion");
        if(frame==1800)screenshot("floor-return");
        const uint8_t *ram=p_retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM);
        size_t ram_size=p_retro_get_memory_size(RETRO_MEMORY_SYSTEM_RAM);
        if(!ram || mailbox+(24+64*21)*4>ram_size){fprintf(stderr,"RAM mailbox unavailable\n");return exit2(__LINE__);}
        if(ram_word(ram,mailbox)==0x53434432) {
            unsigned sequence=ram_word(ram,mailbox+4);
            if(frame>=870 && frame<930) {unsigned charge=(ram_word(ram,mailbox+32)>>8)&255;if(charge>raw_charge)raw_charge=charge;}
            if(frame>=930 && frame<950) {int speed=(int16_t)(ram_word(ram,mailbox+28)>>16);unsigned magnitude=speed<0?-speed:speed;if(magnitude>raw_dash_speed)raw_dash_speed=magnitude;}
            if(sequence-last_sequence>64){fprintf(stderr,"Trace buffer overrun\n");return exit2(__LINE__);}
            while(last_sequence!=sequence) {
                unsigned expected=++last_sequence;last_progress=frame;
                size_t record=mailbox+(24+(expected%64)*21)*4;
                if(ram_word(ram,record)!=expected){fprintf(stderr,"Trace sequence mismatch\n");return exit2(__LINE__);}
                unsigned tick=ram_word(ram,record+80);
                if(tick<=last_tick){fprintf(stderr,"Multiple player updates in one VBlank\n");return exit2(__LINE__);}
                last_tick=tick;
                unsigned test=ram_word(ram,record+4),step=ram_word(ram,record+8);
                if(ram_word(ram,record+76)){fprintf(stderr,"CORE:FAIL\n");return exit2(__LINE__);}
                if(test<28 && step<600) {
                    if(seen[test][step]){fprintf(stderr,"Duplicate target frame\n");return exit2(__LINE__);}
                    seen[test][step]=true;trace_count++;
                    fprintf(trace,"%u %u",test,step);
                    if(player_visual_file){
                        size_t at=player_visual_at+(expected%64)*12;
                        if(at+12>ram_size || ram_word(ram,at)!=expected){fprintf(stderr,"Player visual trace mismatch\n");return exit2(__LINE__);}
                        fprintf(player_visual_file,"%u %u %08x %08x\n",test,step,ram_word(ram,at+4),ram_word(ram,at+8));
                    }
                    for(unsigned i=0;i<16;i++)fprintf(trace," %08x",ram_word(ram,record+12+i*4));
                    fputc('\n',trace);
                    if(test==4 && step==80)screenshot("player-charge");
                    if(test==7 && step==56)screenshot("player-loop");
                    if(test==8 && step==4)screenshot("spring-up");
                    if(test==10 && step==4)screenshot("spring-side");
                    if(test==13 && step==4)screenshot("spring-diagonal");
                    if(test==14 && step==8)screenshot("player-hurt");
                    if(test==15 && step==8)screenshot("player-death");
                    if(test==17 && step==8)screenshot("object-layout");
                    if(test==26 && step==60)screenshot("controller-crouch");
                    if(step==599){printf("Replay %u captured: %u states\n",test,trace_count);fflush(stdout);}
                }
            }
        }
        if(trace_count && frame-last_progress>300) {screenshot("stalled");uint32_t *cpu=dlsym(core,"CPU");if(cpu)fprintf(stderr,"SH2 PC=%08x SP=%08x SR=%08x audio=%08x\n",cpu[16],cpu[15],cpu[17],ram_word(ram,mailbox+92));fprintf(stderr,"Mailbox stopped after %u states at frame %u\n",trace_count,frame);break;}
        if(trace_count==16800)break;
    }
    fclose(trace);fclose(audio_file);fclose(preview_file);if(player_visual_file)fclose(player_visual_file);if(effect_file && fclose(effect_file))return exit2(__LINE__);
    if(act_only || act2_only){int passed=act_done && act_sign && act_sections==5;if(!passed)screenshot("act-route-incomplete");p_retro_unload_game();p_retro_deinit();return passed?0:2;}
    if(world_only){
        printf("Target world probe: %u; cutscene: %u; arrival: %u; frames: %u\n",world_pass,saw_warp,!!saw_arrival,25900+boot_wait+world_wait+finish_wait+monitor_wait+collapse_wait+tunnel_wait+disc_wait+door_wait+scenery_wait+projector_wait+amy_wait);
        for(unsigned n=0;n<4;n++)if(!collapse_pass[n] || !collapse_intact[n] || !tunnel_pass[n])return exit2(__LINE__);
        for(unsigned n=0;n<3;n++)if(!disc_pass[n])return exit2(__LINE__);
        for(unsigned n=0;n<5;n++)if(door_frames[n]!=3 || !door_action[n])return exit2(__LINE__);
        for(unsigned n=0;n<11;n++)if(!scenery_pass[n])return exit2(__LINE__);
        for(unsigned n=0;n<4;n++)if(!projector_pass[n])return exit2(__LINE__);
        if(amy_hold<600 || !amy_jump)return exit2(__LINE__);
        printf("Projector and animal controller routes: timed destruction, release and future presence passed\n");
        printf("Tag and scenery routes: two speed tags, eight era-art scenes and Sonic overlap passed\n");
        printf("Door and moving-spring routes: five fixtures, both frames and activation passed\n");
        printf("Spinning disc controller routes: all six poses, two jumps and natural release passed\n");
        printf("Tunnel controller routes: four eras, original loaded paths, visibility flags and exact exits passed\n");
        printf("Collapsing platform controller routes: four eras, intact/break/fall and rider release passed\n");
        printf("Original platform controller routes: PASS\n");
        for(unsigned route=0;route<2;route++){
            if(!finish_pass[route] || !finish_music[route] || !finish_stopped[route] || !finish_energy[route]){fprintf(stderr,"Finish route missing evidence: route=%u pass=%u music=%u stopped=%u energy=%llu\n",route,finish_pass[route],finish_music[route],finish_stopped[route],(unsigned long long)finish_energy[route]);return exit2(__LINE__);}
            for(unsigned phase=1;phase<=6;phase++)if(!finish_seen[route][phase])return exit2(__LINE__);
            if(finish_seen[route][2]-finish_seen[route][1]!=120 || finish_seen[route][3]-finish_seen[route][2]!=60 || finish_seen[route][5]-finish_seen[route][4]!=37){fprintf(stderr,"Finish timing mismatch\n");return exit2(__LINE__);}
        }
        printf("Original finish controller routes: present=1 good=1 score=52300 music=6 replay=1\n");
        for(unsigned n=0;n<5;n++)if(!monitor_pass[n])return exit2(__LINE__);
        printf("Monitor controller routes: five grants, power-up music and expiration passed\n");
        printf("Original wall controller routes: past=%u present=%u\n",wall_pass[0],wall_pass[1]);
        printf("Checkpoint controller route: activation=%u death=%u respawn=%u x=%u time=%u\n",checkpoint_seen,checkpoint_dead,checkpoint_return,checkpoint_x,checkpoint_time);
        printf("Ramp route: entry=%u exit=%u scroll=%u\n",ramp_seen,ramp_exit,ramp_scroll);
        p_retro_unload_game();p_retro_deinit();return world_pass && saw_warp && saw_arrival?0:2;
    }
    if(game_only){
        unsigned all_done=1;printf("Special game routes: done=");
        for(unsigned r=0;r<game_route_count;r++){printf(r?",%u":"%u",game_done[r]);all_done&=game_done[r]!=0;}
        printf(" records=%u\n",game_records);
        p_retro_unload_game();p_retro_deinit();return all_done?0:2;
    }
    if(special_only){
        const uint8_t *ram=p_retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM);
        printf("Special motion probe: %u %u\n",ram_word(ram,bench_mailbox+20),ram_word(ram,bench_mailbox+24));
        printf("Special effect asset:");for(unsigned i=2;i<5;i++)printf(" %u",ram_word(p_retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM),contact_mailbox+i*4));putchar('\n');
        printf("Special ufo asset:");for(unsigned i=5;i<8;i++)printf(" %u",ram_word(p_retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM),contact_mailbox+i*4));putchar('\n');
        printf("Special inspection: captures=%u resumed_sequence=%u nested_returns=%u benchmark_cases=%u\n",special_captures,special_return,special_nested,special_bench_count);
        p_retro_unload_game();p_retro_deinit();return special_captures==32 && special_return>100 && special_nested==2 && special_live==8 && sonic_captures==3 && effect_captures==8 && ufo_captures==4 && special_bench_count==1632?0:2;
    }
    if(diagnostic_only) {
        for(unsigned i=0;i<3;i++) {
            unsigned long long mean=probe_count[i]?probe_energy[i]/probe_count[i]:0;
            printf("Audio probe %u: mean_square=%llu\n",i,mean);
            if(mean<10000)return exit2(__LINE__);
        }
        printf("Direct SCSP tone, driver ring, CD music and diagnostic exit passed\n");
        p_retro_unload_game();p_retro_deinit();return 0;
    }
    if(audio_only) {
        for(unsigned i=0;i<4;i++) {
            printf("Music track %u: samples=%llu mean_square=%llu peak=%u repeats=%u\n",i+2,(unsigned long long)music_count[i],(unsigned long long)(music_count[i]?music_energy[i]/music_count[i]:0),music_peak[i],repeats[i]);
            if(music_count[i]<88200 || music_energy[i]/music_count[i]<10000 || music_peak[i]>=32767)return exit2(__LINE__);
        }
        printf("Pause: nonzero=%llu FAD=%u->%u\n",(unsigned long long)pause_nonzero,paused_fad,paused_fad_end);
        if(pause_nonzero || !paused_fad || paused_fad!=paused_fad_end || !repeats[0] || !repeats[3])return exit2(__LINE__);
        printf("Music era switching, pause/resume, present repeat after resume, and final-track repeat passed\n");
        p_retro_unload_game();p_retro_deinit();return 0;
    }
    printf("Audio samples: %lu; nonzero: %lu; peak: %u\n",audio_samples,audio_nonzero,audio_peak);
    printf("Post-boot nonzero game audio samples: %lu\n",game_audio_nonzero);
    printf("Controller dash charge: %u; release speed: %u\n",raw_charge,raw_dash_speed);
    if(game_audio_nonzero<1000 || raw_charge!=45 || raw_dash_speed<3000){fprintf(stderr,"Feedback/controller check failed\n");return exit2(__LINE__);}
    if(trace_count!=16800){fprintf(stderr,"Incomplete SH-2 trace: %u/16800\n",trace_count);return exit2(__LINE__);}
    printf("Emulator frames: %u; SH-2 replay states: %u\n",frame+1,trace_count);
    p_retro_unload_game();p_retro_deinit();
    return 0;
}
