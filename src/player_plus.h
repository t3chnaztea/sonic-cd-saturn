#ifndef SCD_PLAYER_PLUS_H
#define SCD_PLAYER_PLUS_H
#include <stdint.h>
/* Optional CD++-style preset (docs/CDPP-PRESET-SPEC.md). Classic is 0.
   Each move is one flag bit so it can be tested and toggled alone. */
enum {
    SCD_PLUS_SPINDASH2=1,   /* F1 Sonic 2 spin dash (replaces the CD dash) */
    SCD_PLUS_AIRCAP_OFF=2,  /* F2 no air speed cap */
    SCD_PLUS_AIRROLL=4,     /* F3 air roll */
    SCD_PLUS_HOMING=8,      /* F4 homing attack */
    SCD_PLUS_MINIDASH=16,   /* F5 spin dash for small Sonic (MM shrink beam) */
    SCD_PLUS_ALL=31,
    /* The CD++ preset: every move above. */
    SCD_PLUS_PRESET=SCD_PLUS_ALL
};
/* The setting (settings file SCDSATURNCF, src/save.h). The game reads it at
   act start only (scd_player_init); a missing or damaged file leaves 0. */
extern uint8_t scd_preset_flags;
/* The flags the running act latched. */
unsigned scd_plus_active(void);
/* Save mailbox slot 11: the act's flags in bits 0-7, the setting in bits 8-15. */
void scd_plus_publish(void);
/* Hooks called from src/player.c. src/player.c carries weak no-op copies, so
   a build without this file (tools/test-player.sh) is Classic by construction,
   and with scd_plus_active()==0 every hook below returns 0 and writes nothing. */
/* Attract demos replay retail input, so they always run Classic: while the
   hold is on, an act start latches no CD++ move (the setting itself stays). */
void scd_plus_classic_hold(int on);
void scd_plus_act_start(void);
void scd_plus_place(void);
int scd_plus_charge_buffer_off(void);
int scd_plus_ground(void);
void scd_plus_air(void);
/* After the player's air update: the speed a homing attack expects next update. */
void scd_plus_air_end(void);
/* A tracked enemy's normal defeat bounce occurred after the player update. */
void scd_plus_enemy_defeat(unsigned victim_slot, short before_vx, short before_vy);
int scd_plus_jumpmove(void);
#endif
