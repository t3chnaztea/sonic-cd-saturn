#include <yaul.h>
#include <bup.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include "save.h"
#include "player_plus.h"
#include "time_attack.h"
/* Sega ST-162 BupConfig is two 16-bit fields. libyaul's enum field has the
   wrong stride. STN-52 additionally requires 2048+30 workspace words. */
typedef struct {uint16_t unit,partitions;} bios_config;
typedef struct {uint32_t library[4096],work[2048+30];} bios_memory;
_Static_assert(sizeof(bios_config)==4,"BIOS configuration stride");
_Static_assert(sizeof(bup_directory_t)==36,"BIOS directory stride");
_Static_assert(offsetof(bup_directory_t,date)==24,"BIOS date offset");
_Static_assert(offsetof(bup_directory_t,data_size)==28,"BIOS size offset");
static bios_memory *memory;
static unsigned connected;
extern bup_stub_t *__bup_stub;
/* src/main.c: clears or restores the VBlank INTBACK gate; returns the previous state. */
int scd_input_ready_set(int ready);
static const char filenames[2][12]={"SCDSATURN00","SCDSATURN01"};
/* Sega's backup guidance: RESET must not cut a backup write. SMPC RESDISA holds
   the button off for the BIOS write, verify and delete calls; RESENAB restores
   it (scd_save_saturn_init leaves it enabled). The VBlank INTBACK (src/main.c
   input_poll) stays off from RESDISA to RESENAB, as for every other SMPC command. */
static int guarded_write(const bup_directory_t *dir,const uint8_t *data){
    const int input=scd_input_ready_set(0);
    smpc_smc_resdisa_call();
    int rc=bup_write(BUP_DEVICE_INTERNAL,(bup_directory_t *)dir,data,BUP_WRITE_MODE_OVERWRITE);
    if(!rc)rc=bup_verify(BUP_DEVICE_INTERNAL,dir->filename,data);
    smpc_smc_resenab_call();
    scd_input_ready_set(input);
    return rc;
}
static int status(void *context){
    (void)context;if(!connected)return 1;
    int rc=bup_partition_select(BUP_DEVICE_INTERNAL,0);if(rc)return rc;
    bup_stat_t st;return bup_status(BUP_DEVICE_INTERNAL,SCD_SAVE_BYTES,&st);
}
static int read_slot(void *context,unsigned slot,uint8_t data[SCD_SAVE_BYTES]){
    (void)context;if(!connected || slot>1)return 1;
    bup_directory_t dir;memset(&dir,0,sizeof(dir));
    int count=bup_dir(BUP_DEVICE_INTERNAL,filenames[slot],1,&dir);
    if(!count)return 5;
    /* Names occupy all 11 characters, so a prefix search cannot select an
       unrelated longer name. Reject odd length BEFORE BIOS copies bytes. */
    if(count!=1 || memcmp(dir.filename,filenames[slot],12) || dir.data_size!=SCD_SAVE_BYTES)return 8;
    return bup_read(BUP_DEVICE_INTERNAL,filenames[slot],data);
}
static int write_slot(void *context,unsigned slot,const uint8_t data[SCD_SAVE_BYTES]){
    (void)context;if(!connected || slot>1)return 1;
    bup_directory_t dir;memset(&dir,0,sizeof(dir));
    memcpy(dir.filename,filenames[slot],12);memcpy(dir.comment,"SONIC CD",9);
    dir.language=BUP_LANG_ENGLISH;dir.data_size=SCD_SAVE_BYTES;
    smpc_time_dec_t rtc;smpc_rtc_time_bcd_from(smpc_rtc_time_get(),&rtc);
    bup_date_t date={.year=rtc.year>=1980 && rtc.year<=2235?rtc.year-1980:0,
        .month=rtc.month>=1 && rtc.month<=12?rtc.month:1,
        .day=rtc.day>=1 && rtc.day<=31?rtc.day:1,.hour=rtc.hours<24?rtc.hours:0,
        .minute=rtc.minutes<60?rtc.minutes:0};
    dir.date=bup_date_set(&date);
    return guarded_write(&dir,data);
}
/* Any other file (Time Attack records "SCDSATURNTA", src/time_attack.h, and the
   settings "SCDSATURNCF"): same rules as the progress slots, with the caller's size.
   Resident, so the settings load at boot; the fe_ names are the overlay's entries. */
static int file_read(const char name[12],uint8_t *data,uint32_t size){
    if(!connected)return 1;
    int rc=bup_partition_select(BUP_DEVICE_INTERNAL,0);if(rc)return rc;
    bup_directory_t dir;memset(&dir,0,sizeof(dir));
    int count=bup_dir(BUP_DEVICE_INTERNAL,name,1,&dir);
    if(!count)return 5;
    if(count!=1 || memcmp(dir.filename,name,12) || dir.data_size!=size)return 8;
    return bup_read(BUP_DEVICE_INTERNAL,name,data);
}
static int file_write(const char name[12],const uint8_t *data,uint32_t size){
    if(!connected)return 1;
    int rc=bup_partition_select(BUP_DEVICE_INTERNAL,0);if(rc)return rc;
    bup_stat_t st;rc=bup_status(BUP_DEVICE_INTERNAL,size,&st);if(rc)return rc;
    bup_directory_t dir;memset(&dir,0,sizeof(dir));
    memcpy(dir.filename,name,12);memcpy(dir.comment,"SONIC CD",9);
    dir.language=BUP_LANG_ENGLISH;dir.data_size=size;
    smpc_time_dec_t rtc;smpc_rtc_time_bcd_from(smpc_rtc_time_get(),&rtc);
    bup_date_t date={.year=rtc.year>=1980 && rtc.year<=2235?rtc.year-1980:0,
        .month=rtc.month>=1 && rtc.month<=12?rtc.month:1,
        .day=rtc.day>=1 && rtc.day<=31?rtc.day:1,.hour=rtc.hours<24?rtc.hours:0,
        .minute=rtc.minutes<60?rtc.minutes:0};
    dir.date=bup_date_set(&date);
    return guarded_write(&dir,data);
}
/* Only this game's own record files: the time attack pair removes its older copy
   after the newer one verified (src/time_attack.c fe_ta_records_store). */
static int file_remove(const char name[12]){
    if(!connected || memcmp(name,"SCDSATURNT",10))return 1;
    int rc=bup_partition_select(BUP_DEVICE_INTERNAL,0);if(rc)return rc;
    bup_directory_t dir;memset(&dir,0,sizeof(dir));
    int count=bup_dir(BUP_DEVICE_INTERNAL,name,1,&dir);
    if(!count)return 5;
    if(count!=1 || memcmp(dir.filename,name,12))return 8;
    const int input=scd_input_ready_set(0);
    smpc_smc_resdisa_call();rc=bup_delete(BUP_DEVICE_INTERNAL,name);smpc_smc_resenab_call();
    scd_input_ready_set(input);
    return rc;
}
int fe_save_file_read(const char name[12],uint8_t *data,uint32_t size){return file_read(name,data,size);}
int fe_save_file_write(const char name[12],const uint8_t *data,uint32_t size){return file_write(name,data,size);}
int fe_save_file_remove(const char name[12]){return file_remove(name);}
const fe_ta_io fe_ta_saturn_io={fe_save_file_read,fe_save_file_write,fe_save_file_remove};
static const char settings_file[12]="SCDSATURNCF";
int scd_settings_load(scd_settings *s){
    uint8_t data[SCD_SETTINGS_BYTES];
    *s=(scd_settings){0,0};
    int rc=file_read(settings_file,data,SCD_SETTINGS_BYTES);
    if(!rc && !scd_settings_decode(data,s))rc=8;
    return rc;
}
int scd_settings_store(const scd_settings *s){
    uint8_t data[SCD_SETTINGS_BYTES];scd_settings_encode(data,s);
    return file_write(settings_file,data,SCD_SETTINGS_BYTES);
}
scd_save_backend scd_save_saturn_init(void){
    if(!memory){
        memory=malloc(sizeof(*memory));
        if(memory){
            bios_config config[3]={{0}};
            typedef void (*init_fn)(void *,void *,bios_config *);
            const int input=scd_input_ready_set(0);
            smpc_smc_resdisa_call();
            ((init_fn)MEMORY_READ(32,0x06000358))(memory->library,memory->work,config);
            __bup_stub=(bup_stub_t *)MEMORY_READ(32,0x06000354);
            connected=config[0].unit==1 && config[0].partitions>0;
            smpc_smc_resenab_call();
            scd_input_ready_set(input);
            /* The CD++ preset setting; anything but a valid file is Classic. */
            scd_settings settings;
            if(!scd_settings_load(&settings) && settings.preset)scd_preset_flags=settings.flags;
            scd_plus_publish();
        }
    }
    return (scd_save_backend){status,read_slot,write_slot,NULL};
}
