#ifndef SCD_MUSIC_ROUTES_H
#define SCD_MUSIC_ROUTES_H
#define SCD_MUSIC_COUNT 41u
/* Keep the original ten slots stable; append four eras per additional zone.
   Cue 10, the final boss (LOADER2.C sub_sync(104): CD track 25), follows them. */
static inline unsigned scd_music_slot(unsigned zone,unsigned cue){
    return cue==10 ? 34u : cue>=11 ? 24u+cue : cue<4 && zone>0 && zone<7 ? 10+(zone-1)*4+cue : cue;
}
/* Cues 11-16 after it (slots 35-40): Time Attack menu, game over, D.A. Garden, intro,
   ending, prototype warp (Sound.inc CDDA_TMATK..CDDA_ENDING, CDDA_WARP). The Time
   Attack menu and D.A. Garden songs loop. */
static inline int scd_music_repeats(unsigned cue){return cue<4 || cue==7 || cue==8 || cue==10 || cue==11 || cue==13;}
#endif
