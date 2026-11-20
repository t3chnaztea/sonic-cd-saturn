#ifndef SCD_TIME_ATTACK_H
#define SCD_TIME_ATTACK_H
#include <stdint.h>
/* Time Attack (IPX.asm TimeAttack 1214-1290, ATTACK.MMD; PC TITLE/TA/TA.C).
   Records follow the retail Backup RAM layout ("Backup RAM.inc" svTmAtkTimes..
   svTmAtkDefName, "Backup RAM/Initial Data.asm"): 21 acts (7 zones x 3) then the
   7 special stages, 3 ranks each. A time is the retail level clock in frames
   (Level/_Objects/HUD and Points/Main.asm: minutes, seconds, 60 frames).
   A name is 3 retail initials codes: 0-9 digits, $0B-$24 A-Z
   (default "AAA" $0B0B0B, the player default "YOU" $23191F). */
enum {
    SCD_TA_ACTS=21, SCD_TA_SPECIALS=7, SCD_TA_ENTRIES=SCD_TA_ACTS+SCD_TA_SPECIALS, SCD_TA_RANKS=3,
    /* Initial Data.asm: every time is $00050000, 5'00"00. */
    SCD_TA_DEFAULT_TIME=5*60*60,
    /* The level clock caps at 9'59"59 (HUD and Points/Main.asm:261). */
    SCD_TA_MAX_TIME=9*3600+59*60+59,
    SCD_TA_FILE_BYTES=692
};
typedef struct {
    uint32_t time[SCD_TA_ENTRIES][SCD_TA_RANKS];
    uint8_t name[SCD_TA_ENTRIES][SCD_TA_RANKS][3];
    uint8_t default_name[3];
    /* IPX.asm timeAttackUnlock (acts unlocked: 3 per cleared zone) and titleFlags. */
    uint8_t unlock,title_flags;
} scd_ta_records;
/* Title flags (Menu/Main.asm:75-110, IPX.asm:180-181). */
enum { SCD_TA_FLAG_SPECIAL=1u<<1, SCD_TA_FLAG_VISUAL=1u<<2, SCD_TA_FLAG_DAGARDEN=1u<<3,
       SCD_TA_FLAG_TIME_ATTACK=1u<<5 };
void fe_ta_records_default(scd_ta_records *r);
/* "SCDT" v1, big endian: 0 magic, 4 version, 5 reserved, 6 size (16-bit), 8 unlock,
   9 title flags, 10 default name, 13..15 zero, 16 times (28x3 x 32-bit frames),
   352 names (28x3 x 3 codes + 0), 688 CRC32 of bytes 0..687. v2 (the file pair
   below) is the same with a non-zero 24-bit generation in bytes 13..15. */
void fe_ta_records_encode(uint8_t data[SCD_TA_FILE_BYTES],const scd_ta_records *r);
int fe_ta_records_decode(const uint8_t data[SCD_TA_FILE_BYTES],scd_ta_records *r);
/* v2 encode (generation 1..0xFFFFFF); decode of v1 (generation 0) or v2. */
void fe_ta_records_encode_gen(uint8_t data[SCD_TA_FILE_BYTES],const scd_ta_records *r,uint32_t generation);
int fe_ta_records_decode_gen(const uint8_t data[SCD_TA_FILE_BYTES],scd_ta_records *r,uint32_t *generation);
/* The records survive a torn write: each preset has two file names (Classic
   "SCDSATURNTA"/"SCDSATURNTB", CD++ "SCDSATURNTP"/"SCDSATURNTQ"). A store writes
   the name that does not hold the current records with the next generation,
   reads it back, and only then deletes the older file, so one file stays in
   use once a store completes. When the other name does not fit (BIOS 4), the
   store returns the error and preserves the current records. A single v1
   "SCDSATURNTA" or "SCDSATURNTP" (from earlier builds) loads as generation 0.
   I/O codes are the Saturn BIOS ones (0 success, 4 no room, 5 missing,
   8 damaged, others device errors). */
typedef struct {
    int (*read)(const char name[12],uint8_t *data,uint32_t size);
    int (*write)(const char name[12],const uint8_t *data,uint32_t size);
    int (*remove)(const char name[12]);
} fe_ta_io;
typedef struct {
    uint32_t generation;   /* of the current records (0 for v1 or none) */
    int8_t current;        /* pair index holding them, -1 for none */
    uint8_t present;       /* bit per pair index: a file exists (valid or not) */
    uint8_t unreadable;    /* bit per pair index: its read failed with a device error */
} fe_ta_file_state;
const char *fe_ta_pair_name(unsigned preset,unsigned index);
/* *r: the newest valid records, defaults without one. Returns 0 (found), 5 (no
   file), 8 (only damaged files) or the device error. */
int fe_ta_records_load(const fe_ta_io *io,unsigned preset,scd_ta_records *r,fe_ta_file_state *st);
/* Returns 0 once the new file reads back equal; otherwise the I/O code (4 when
   the other file does not fit: current records and state stay unchanged; 9 when a
   file was unreadable at load: its records may be newer, so nothing is written). */
int fe_ta_records_store(const fe_ta_io *io,unsigned preset,const scd_ta_records *r,fe_ta_file_state *st);
/* The Saturn backup RAM (src/save_saturn.c). */
extern const fe_ta_io fe_ta_saturn_io;
/* Inserts a finished run (TA.C game_init 487-541): the first rank whose time is
   >= the new time takes it, lower ranks shift down, and a default "AAA" name at
   that rank becomes the default player name. Returns the rank or -1. */
int fe_ta_record_insert(scd_ta_records *r,unsigned entry,uint32_t frames);
/* Sum of the 21 first-place act times in centiseconds (ATTACK.MMD 0xff2c74-0xff2cd0). */
uint32_t fe_ta_act_total(const scd_ta_records *r);
/* Sets title flags bits 1-3 from the act total once every act is unlocked
   (ATTACK.MMD; TA.C SpecialPlayChk 159). Returns the newly set bits. */
unsigned fe_ta_unlocks_update(scd_ta_records *r);
/* Raises the unlock to the zone the progress save reached (IPX.asm
   UnlockTimeAttackLevel after each zone, 638). Sets bit 5 once one zone is clear. */
void fe_ta_progress_unlock(scd_ta_records *r,unsigned zones_cleared);
/* Formats frames as M:SS:CC, the retail M'SS"CC (centiseconds = frames*100/60). */
void fe_ta_time_text(char out[9],uint32_t frames);
char fe_ta_name_char(uint8_t code);
/* The records file: "SCDSATURNTA" in Classic, "SCDSATURNTP" with the CD++ preset on. */
const char *fe_ta_file_name(void);
/* Resident state that survives the zone overlay replacing the front end. */
typedef struct {
    uint8_t mode;       /* IPX timeAttackMode: 1 while a Time Attack run plays */
    uint8_t entry;      /* record entry 0..27 of the run */
    uint8_t aborted;    /* the run ended without a time (death, pause exit) */
    uint8_t pending;    /* a finished run waits for the menu */
    uint32_t frames;    /* IPX timeAttackTime */
    /* Menu cursor kept across a run (TA.C lpKeepWork ta_Menu1/ta_Round/ta_Zone). */
    uint8_t column_special,round,act;
    /* Drawn this run (QA: tools/test_frontend_emulator.py ta-objects): 1 time post,
       2 1UP monitor, 4 Amy, 8 big ring. src/main.c sets it; a run start clears it. */
    uint8_t seen;
    /* Zones the progress save has cleared (set at the title; the unlock follows it). */
    uint8_t zones_cleared;
} scd_ta_resident;
extern scd_ta_resident scd_ta;
#endif
