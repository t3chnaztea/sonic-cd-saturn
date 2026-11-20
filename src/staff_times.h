#ifndef SCD_STAFF_TIMES_H
#define SCD_STAFF_TIMES_H
#include <stdint.h>
/* Front-end overlay only. Outcome persists until the next entry, including on
   missing/invalid data. A title return alone never proves a successful screen. */
typedef struct {
    uint32_t phase,frames,scroll,load_ok,result,fade_in,fade_out,pack_bytes,tiles,music_started,start_exit;
} fe_staff_times_status;
enum {fe_staff_idle,fe_staff_loading,fe_staff_fading_in,fe_staff_screen,fe_staff_fading_out,fe_staff_finished,fe_staff_failed};
enum {fe_staff_no_result,fe_staff_missing,fe_staff_invalid,fe_staff_start_exit};
extern volatile fe_staff_times_status fe_staff_times_qa;
void fe_staff_times(void);
#endif
