/* Game ending dispatch. The movie player lives in the front-end overlay
   (src/fmv_fe_names.h); this resident part is the tables, the calls and the emulator
   test entry for the endings and the "Thank You" screen. */
#include <stdint.h>
#include <yaul.h>

#include "audio.h"
#include "credits_saturn.h"
#include "frontend.h"
#include "fmv_fe_names.h"
#include "fmv_saturn.h"
#include "ending.h"
#include "zone_code.h"

/* The only resident reference to the overlay player (tools/test_zone_code.py). */
const scd_ending_zone_ops fe_ending_zone_ops = {fmv_play};

static int movie_play(fmv_id_t id)
{
    volatile uint32_t *m = scd_fmv_mailbox;
    m[0] = FMV_TEST_REQUEST | (id + 1u);
    m[1] = FMV_MAILBOX_PLAYING;
    int ret = -4;
    /* The front-end overlay replaces MM's: nothing after GameDone runs R8 code, and
       the next stage load reads its zone overlay again. */
    scd_frontend_overlay_load();
    if (scd_zone_code_ready(SCD_ZONE_FRONTEND)) {
        /* A volatile pointer keeps LTO from turning the table read into a direct
           resident call into the overlay. */
        const scd_ending_zone_ops *volatile ops = &fe_ending_zone_ops;
        ret = ops->play(id);
    }
    m[2] = (uint32_t)ret;
    m[1] = FMV_MAILBOX_DONE;
    return ret;
}

int scd_ending_play(int good)
{
    return movie_play(good ? FMV_GOODEND : FMV_BADEND);
}

/* The "Thank You" screen (src/credits_saturn.c), reached the same way. */
const scd_credits_zone_ops fe_credits_zone_ops = {fe_credits_thanks};
volatile uint32_t scd_credits_mailbox[8];

int scd_credits_thanks_play(void)
{
    scd_frontend_overlay_load();
    if (!scd_zone_code_ready(SCD_ZONE_FRONTEND)) return -4;
    const scd_credits_zone_ops *volatile ops = &fe_credits_zone_ops;
    return ops->thanks();
}

/* Emulator test entry at the title (src/main.c): the request in scd_credits_mailbox[0]
   runs the "Thank You" screen or an ending movie (staff roll and end screen), as
   Visual Mode and GameDone do; the main loop then starts the title again. */
void scd_credits_test_entry(void)
{
    uint32_t request = scd_credits_mailbox[0];
    scd_credits_mailbox[0] = 0;
    if (request != SCD_CREDITS_REQUEST && request != SCD_CREDITS_REQUEST_GOODEND && request != SCD_CREDITS_REQUEST_BADEND &&
        request != SCD_CREDITS_REQUEST_OPENING)
        return;
    /* As fe_frontend_movie does from the title (src/frontend.c): the title's CD-DA
       track holds the drive, and its automatic VDP1 mode never ends a frame wait; both
       screens run in the front end's manual mode. */
    scd_audio_stop_music();
    vdp1_sync_wait();
    vdp1_sync_interval_set(-1);
    vdp2_tvmd_display_set();
    if (request == SCD_CREDITS_REQUEST) scd_credits_thanks_play();
    else {
        scd_low_packs_lost = 1;
        if (request == SCD_CREDITS_REQUEST_OPENING) movie_play(FMV_OPENING);
        else scd_ending_play(request == SCD_CREDITS_REQUEST_GOODEND);
        vdp2_sprite_priority_set(0, 4);
        vdp2_sprite_priority_set(1, 7);
        scd_audio_bank(-1);
    }
}
