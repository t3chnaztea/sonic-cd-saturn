#ifndef SCD_STAGE_SELECT_H
#define SCD_STAGE_SELECT_H
#include <stdint.h>
enum { FE_SEL_NORMAL,FE_SEL_WARP,FE_SEL_OPENING,FE_SEL_COMMING,FE_SEL_SPEDEMO };
enum { FE_SEL_COUNT=74,FE_SEL_FAILED=74 };
/* zone/act are original zoneAct bytes; era is native0Present/1Past/2Good/3Bad.
   Every extra row preserves original zoneAct0,TIME_PAST0,goodFuture0 as0/0/1. */
typedef struct { uint8_t kind,zone,act,era; } fe_stage_select_choice;
extern const fe_stage_select_choice fe_stage_select_choices[FE_SEL_COUNT];
typedef struct { uint16_t selection,delay;uint8_t hold,accepted; } fe_stage_select_state;
void fe_stage_select_move(fe_stage_select_state *s);
int fe_stage_select_input(fe_stage_select_state *s,unsigned hold);
/* FEND screen5; result0none/1missing/2invalid/3selected. phase matches Staff Times. */
typedef struct { uint32_t phase,frames,selection,delay,load_ok,result,fade_in,fade_out,pack_bytes,tiles,held; } fe_stage_select_status;
extern volatile fe_stage_select_status fe_stage_select_qa;
/* Exact original ordinal0..73, or74 on safe load/validation failure. */
int fe_stage_select_pack_valid(const uint8_t *data,unsigned bytes);
unsigned fe_stage_select(void);
#endif
