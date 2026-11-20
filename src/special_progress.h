#ifndef SCD_SPECIAL_PROGRESS_H
#define SCD_SPECIAL_PROGRESS_H
/* Special stage order and ending choice. Pure functions; stage IDs are
   0-based like the original curSpecStage/specStageID, stones and good futures
   are 7-bit masks (bit n = stage or zone n). */
#include <stdint.h>
enum {SCD_SPECIAL_STAGES=7,SCD_ALL_STONES=0x7f,SCD_ALL_GOOD_FUTURES=0x7f};
/* Special Stage/Sub.asm .Exit: search from the stage just played for the next
   stage whose stone is still missing. With all stones held, any next stage. */
static inline uint8_t scd_special_stage_after(unsigned stage,uint8_t stones){
    /* specStageID 7 (stage 8) wraps to stage 0 like the others past 6. */
    unsigned next=stage&7;
    do{next=next+1>=SCD_SPECIAL_STAGES?0:next+1;}while(stones!=SCD_ALL_STONES && (stones>>next&1));
    return (uint8_t)next;
}
/* Sub.asm .StageBeaten then .Exit: the stone for the stage played (if won),
   then the next stage. Returns the new curSpecStage; *stones is updated. */
static inline uint8_t scd_special_stage_exit(unsigned stage,uint8_t *stones,int won){
    if(won)*stones|=(uint8_t)(1u<<(stage%SCD_SPECIAL_STAGES));
    return scd_special_stage_after(stage,*stones);
}
/* Save v1 had no curSpecStage. Reconstruct it: the stage after the highest
   stone held (stones are won in cyclic order from stage 0), else stage 0. */
static inline uint8_t scd_special_stage_from_stones(uint8_t stones){
    stones&=SCD_ALL_STONES;
    if(!stones)return 0;
    unsigned high=6;while(!(stones>>high&1))high--;
    return scd_special_stage_after(high,stones);
}
/* IPX.asm GameDone: the good ending needs all seven good futures or all seven
   time stones; otherwise the bad ending. Returns 1 for good. */
static inline int scd_ending_good(uint8_t good_futures,uint8_t stones){
    return good_futures==SCD_ALL_GOOD_FUTURES || stones==SCD_ALL_STONES;
}
#endif
