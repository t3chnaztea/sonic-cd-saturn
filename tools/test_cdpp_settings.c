/* Settings file codec (src/save.c scd_settings_*, "SCDSATURNCF"): round trips,
   and every damaged or unknown record decodes as Classic (preset 0, flags 0). */
#include "save.h"
#include <stdio.h>
#include <string.h>
#define CHECK(c,...) do{if(!(c)){fprintf(stderr,"FAIL: CD++ settings: " __VA_ARGS__);fputc('\n',stderr);return 1;}}while(0)
static int classic(const uint8_t d[SCD_SETTINGS_BYTES]){scd_settings s={9,9};return !scd_settings_decode(d,&s) && !s.preset && !s.flags;}
int main(void){
    uint8_t d[SCD_SETTINGS_BYTES],e[SCD_SETTINGS_BYTES];scd_settings s;unsigned rejected=0;
    for(unsigned flags=0;flags<32;flags++){
        scd_settings in={flags?1:0,(uint8_t)flags};scd_settings_encode(d,&in);
        CHECK(scd_settings_decode(d,&s) && s.preset==in.preset && s.flags==in.flags,"round trip %u",flags);
    }
    scd_settings cdpp={1,31};scd_settings_encode(d,&cdpp);
    CHECK(!memcmp(d,"SCDC\x01\x10\x01\x1f\0\0\0\0",12),"layout");
    for(unsigned bit=0;bit<SCD_SETTINGS_BYTES*8;bit++){memcpy(e,d,sizeof(e));e[bit/8]^=(uint8_t)(1u<<bit%8);CHECK(classic(e),"bit flip %u",bit);rejected++;}
    memset(e,0,sizeof(e));CHECK(classic(e),"blank");rejected++;
    /* Valid CRCs on records the codec must refuse: version 2, preset 2, flag 32, Classic with flags. */
    const uint8_t bad[4][4]={{2,16,1,31},{1,16,2,31},{1,16,1,32},{1,16,0,1}};
    for(unsigned i=0;i<4;i++){
        memcpy(e,d,sizeof(e));memcpy(e+4,bad[i],4);
        uint32_t crc=~0u;for(unsigned n=0;n<12;n++){crc^=e[n];for(unsigned b=0;b<8;b++)crc=(crc>>1)^(0xedb88320u&(0u-(crc&1)));}
        crc=~crc;e[12]=crc>>24;e[13]=crc>>16;e[14]=crc>>8;e[15]=crc;
        CHECK(classic(e),"unknown record %u",i);rejected++;
    }
    printf("CD++ settings codec: 32 round trips, %u damaged or unknown records read as Classic\n",rejected);
    return 0;
}
