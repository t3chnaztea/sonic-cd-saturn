/* Exports the header-only special_progress.h functions for tools/test_special_progress.py. */
#include "special_progress.h"
uint8_t stage_after(unsigned stage,uint8_t stones){return scd_special_stage_after(stage,stones);}
uint8_t stage_exit(unsigned stage,uint8_t *stones,int won){return scd_special_stage_exit(stage,stones,won);}
uint8_t stage_from_stones(uint8_t stones){return scd_special_stage_from_stones(stones);}
int ending_good(uint8_t good_futures,uint8_t stones){return scd_ending_good(good_futures,stones);}
