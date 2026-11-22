#ifndef SCD_SAVE_H
#define SCD_SAVE_H
#include <stdint.h>
enum { SCD_SAVE_BYTES=32 };
/* Checkpoints are act starts, not snapshots of a live level.
   Format "SCDS" v2 (32 bytes, big endian): 0 magic, 4 version, 5 size,
   8 generation, 12..18 zone..completed, 19 spec_stage, 20..27 zero, 28 CRC32.
   v2 adds spec_stage (the original's curSpecStage, 0-6, IPX.asm svSpecStage).
   v1 records (byte 4 == 1, bytes 19..27 zero) still load; their spec_stage is
   rebuilt from time_stones (scd_special_stage_from_stones). Commits write v2. */
typedef struct {
    uint8_t zone,act,era,time_stones,good_acts,good_zones,completed,spec_stage;
} scd_save_progress;
typedef enum {
    SCD_SAVE_OK, SCD_SAVE_EMPTY, SCD_SAVE_RECOVERED, SCD_SAVE_CORRUPT,
    SCD_SAVE_UNAVAILABLE, SCD_SAVE_UNFORMATTED, SCD_SAVE_FULL,
    SCD_SAVE_PROTECTED, SCD_SAVE_IO_ERROR
} scd_save_status;
/* Backend codes follow the Saturn BIOS (0 success, 1 absent, 2 unformatted,
   3 protected, 4 full, 5 missing, 7 mismatch, 8 damaged). Read MUST check
   directory length before invoking the BIOS's unbounded BUP_Read. */
typedef struct {
    int (*status)(void *context);
    int (*read)(void *context,unsigned slot,uint8_t data[SCD_SAVE_BYTES]);
    int (*write)(void *context,unsigned slot,const uint8_t data[SCD_SAVE_BYTES]);
    void *context;
} scd_save_backend;
typedef struct {
    scd_save_backend backend;
    scd_save_progress saved,pending;
    uint32_t generation;
    scd_save_status status;
    unsigned valid,any,dirty,slot;
    /* Slots whose last read failed with a device error (bit per slot): their
       generation is unknown, so scd_save_retry reads them again before it
       writes and refuses while one stays unreadable. */
    unsigned unread;
} scd_save;
int scd_save_progress_valid(const scd_save_progress *p);
void scd_save_encode(uint8_t data[SCD_SAVE_BYTES],const scd_save_progress *p,uint32_t generation);
int scd_save_decode(const uint8_t data[SCD_SAVE_BYTES],scd_save_progress *p,uint32_t *generation);
void scd_save_open(scd_save *s,scd_save_backend backend);
scd_save_status scd_save_commit(scd_save *s,scd_save_progress progress);
scd_save_status scd_save_retry(scd_save *s);
const char *scd_save_message(scd_save_status status);
/* Settings file "SCDSATURNCF" (docs/CDPP-PRESET-SPEC.md section 6), apart from
   the progress slots so saves stay preset-neutral. "SCDC" v1, 16 bytes:
   0 magic, 4 version, 5 size, 6 preset (0 Classic, 1 CD++), 7 flags
   (src/player_plus.h bits), 8..11 zero, 12 CRC32 of bytes 0..11. Classic has
   flags 0. A missing, damaged or unknown file decodes as Classic. */
enum { SCD_SETTINGS_BYTES=16 };
typedef struct { uint8_t preset,flags; } scd_settings;
void scd_settings_encode(uint8_t data[SCD_SETTINGS_BYTES],const scd_settings *s);
int scd_settings_decode(const uint8_t data[SCD_SETTINGS_BYTES],scd_settings *s);
/* Saturn-only backend. No automatic formatting or deletion. */
scd_save_backend scd_save_saturn_init(void);
/* Another 11-character backup RAM file of exactly size bytes (BIOS codes as above).
   Call scd_save_saturn_init first. fe_: front-end overlay code (src/saturn.x .zone_R0). */
int fe_save_file_read(const char name[12],uint8_t *data,uint32_t size);
int fe_save_file_write(const char name[12],const uint8_t *data,uint32_t size);
/* Removes one of this game's "SCDSATURNT?" record files (refuses any other name). */
int fe_save_file_remove(const char name[12]);
/* The settings file at boot (scd_save_saturn_init) and from the RAM DATA panel.
   load: BIOS code; *s is Classic unless the file decodes. store: BIOS code. */
int scd_settings_load(scd_settings *s);
int scd_settings_store(const scd_settings *s);
#endif
