#ifndef SCD_CDDA_TARGET_QA_SHADOW_H
#define SCD_CDDA_TARGET_QA_SHADOW_H
#include <stdint.h>
/* Read-only observer. No install/start/request/reset operation is performed. */
extern volatile uint32_t scd_cdda_target_qa_shadow[20];
void scd_cdda_target_snapshot_shadow(void);
#endif
