/* Game ending: IPX.asm GameDone (CD Initial Program/IPX.asm:301-330). */
#ifndef SCD_ENDING_H
#define SCD_ENDING_H
#include "fmv_saturn.h"

#define SCD_ENDING_ALL 0x7Fu

/* GameDone compares gameGoodFutures (one bit per zone, set when its Act 3 ended in
   the good future) and gameTimeStones with %01111111: either one complete picks the
   good ending (endingID $7F, GOODEND), otherwise the bad one (endingID 0, BADEND). */
static inline int scd_ending_good(unsigned good_futures,unsigned time_stones){
    return (good_futures&0xFFu)==SCD_ENDING_ALL || (time_stones&0xFFu)==SCD_ENDING_ALL;
}

/* ENDING.MMD's last screen, by endingID (retail program $FF2A3E, $FF2AE2; the
   message tiles read "YOU'RE TOO COOL!" and "TRY AGAIN"). Shown on the text card
   when the movie cannot play. */
static inline const char *scd_ending_message(int good){return good?"YOU'RE TOO COOL!":"TRY AGAIN";}

/* Plays the ending movie (GOODEND.FMV or BADEND.FMV: picture, staff roll and end
   screen, src/fmv_saturn.c) from the front-end code overlay (R0), which it loads in place of MM's. Returns 0 when
   it played to its end; negative when it could not: -4 overlay not loaded, -1 file
   missing, -2 disc error, -3 bad format. The movie takes low work RAM up to
   FMV_LWRAM_END, the zone effect bank's tail and the VDP2 setup; the caller
   restores them. Records its progress in the movie mailbox (scd_fmv_mailbox). */
int scd_ending_play(int good);

/* The movie player's front-end overlay entry (fmv_play, src/fmv_saturn.c): the only
   resident reference to it (tools/test_zone_code.py). Call it through a volatile
   pointer after scd_frontend_overlay_load() (src/zone_code.h), as scd_ending_play does;
   the opening and Visual Mode (src/frontend_view.inc) use it too. */
typedef struct {
    int (*play)(fmv_id_t id);
} scd_ending_zone_ops;
extern const scd_ending_zone_ops fe_ending_zone_ops;

#endif
