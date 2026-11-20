#ifndef SCD_CD_STATUS_H
#define SCD_CD_STATUS_H
#include <stdint.h>
/* Sega CD communication interface 7.2.5: CR1 high byte is status;
   its low nibble is an enumeration. CR1 low byte is command report data
   (often CD-ROM flag/repeat count), NEVER error flags. */
static inline int scd_cd_response_error(uint16_t cr1){
    unsigned status=cr1>>8;
    if(status==0xff || (status&0x80))return (int)status;
    unsigned state=status&15;
    switch(state){
    case 0:case 1:case 2:case 3:case 4:case 5:case 8:return 0;
    default:return -(int)state;
    }
}
extern volatile uint16_t scd_cd_last_response;
#endif
