#include "save.h"
#include "special_progress.h"
#include <string.h>
static uint32_t get32(const uint8_t *p){return (uint32_t)p[0]<<24|(uint32_t)p[1]<<16|(uint32_t)p[2]<<8|p[3];}
static void put32(uint8_t *p,uint32_t v){p[0]=v>>24;p[1]=v>>16;p[2]=v>>8;p[3]=v;}
static uint32_t checksum(const uint8_t *p,unsigned n){
    uint32_t crc=~0u;
    while(n--){crc^=*p++;for(unsigned b=0;b<8;b++)crc=(crc>>1)^(0xedb88320u & (0u-(crc&1)));}
    return ~crc;
}
int scd_save_progress_valid(const scd_save_progress *p){
    return p->zone<7 && p->act<3 && (p->act==2?(p->era==2 || p->era==3):p->era==0) &&
        p->time_stones<128 && p->good_acts<4 && p->good_zones<128 && p->completed<2 && p->spec_stage<SCD_SPECIAL_STAGES &&
        (!p->completed || (p->zone==6 && p->act==2));
}
void scd_save_encode(uint8_t d[SCD_SAVE_BYTES],const scd_save_progress *p,uint32_t generation){
    memset(d,0,SCD_SAVE_BYTES);memcpy(d,"SCDS",4);d[4]=2;d[5]=SCD_SAVE_BYTES;
    put32(d+8,generation);d[12]=p->zone;d[13]=p->act;d[14]=p->era;d[15]=p->time_stones;
    d[16]=p->good_acts;d[17]=p->good_zones;d[18]=p->completed;d[19]=p->spec_stage;put32(d+28,checksum(d,28));
}
int scd_save_decode(const uint8_t d[SCD_SAVE_BYTES],scd_save_progress *p,uint32_t *generation){
    if(memcmp(d,"SCDS",4) || d[4]<1 || d[4]>2 || d[5]!=SCD_SAVE_BYTES || d[6] || d[7] ||
       !get32(d+8) || checksum(d,28)!=get32(d+28))return 0;
    /* v1 reserved bytes 19..27; v2 uses byte 19 for spec_stage. */
    for(unsigned i=d[4]==1?19:20;i<28;i++)if(d[i])return 0;
    scd_save_progress v={d[12],d[13],d[14],d[15],d[16],d[17],d[18],
        d[4]==1?scd_special_stage_from_stones(d[15]):d[19]};
    if(!scd_save_progress_valid(&v))return 0;
    *p=v;*generation=get32(d+8);return 1;
}
static scd_save_status error_status(int code){
    switch(code){
    case 0:return SCD_SAVE_OK;
    case 1:return SCD_SAVE_UNAVAILABLE;
    case 2:return SCD_SAVE_UNFORMATTED;
    case 3:return SCD_SAVE_PROTECTED;
    case 4:return SCD_SAVE_FULL;
    case 8:return SCD_SAVE_CORRUPT;
    default:return SCD_SAVE_IO_ERROR;
    }
}
/* A read that failed for a reason other than a missing (5) or damaged (8) file. */
static int device_error(int rc){return rc && rc!=5 && rc!=8;}
/* Reads one slot into s: 0 missing, 1 present (bad or adopted). A device error
   marks the slot unread. A valid record replaces s->saved when it is newer. */
static unsigned scan_slot(scd_save *s,unsigned i,unsigned *bad){
    uint8_t data[SCD_SAVE_BYTES];scd_save_progress p;uint32_t gen;
    int rc=s->backend.read(s->backend.context,i,data);
    if(device_error(rc)){s->unread|=1u<<i;*bad=1;return 1;}
    s->unread&=~(1u<<i);
    if(rc==5)return 0;
    if(rc || !scd_save_decode(data,&p,&gen)){*bad=1;return 1;}
    uint32_t delta=gen-s->generation;
    if(!s->valid || (delta && delta<0x80000000u)){
        s->valid=1;s->slot=i;s->saved=p;s->generation=gen;
    }
    return 1;
}
void scd_save_open(scd_save *s,scd_save_backend backend){
    memset(s,0,sizeof(*s));s->backend=backend;
    int rc=backend.status(backend.context);
    if(rc){s->status=error_status(rc);return;}
    unsigned bad=0;
    for(unsigned i=0;i<2;i++)if(scan_slot(s,i,&bad))s->any=1;
    s->status=s->valid?(bad?SCD_SAVE_RECOVERED:SCD_SAVE_OK):(bad?SCD_SAVE_CORRUPT:SCD_SAVE_EMPTY);
}
scd_save_status scd_save_commit(scd_save *s,scd_save_progress progress){
    if(!scd_save_progress_valid(&progress))return s->status=SCD_SAVE_IO_ERROR;
    s->pending=progress;s->dirty=1;
    return scd_save_retry(s);
}
scd_save_status scd_save_retry(scd_save *s){
    if(!s->dirty)return s->status;
    int rc=s->backend.status(s->backend.context);
    if(rc)return s->status=error_status(rc);
    /* A slot unreadable at open may hold the newest generation: read it again,
       and write nothing while its generation stays unknown. */
    if(s->unread){
        unsigned bad=0;
        for(unsigned i=0;i<2;i++)if(s->unread>>i&1)scan_slot(s,i,&bad);
        if(s->unread)return s->status=SCD_SAVE_IO_ERROR;
    }
    uint32_t gen=s->generation+1;if(!gen)gen=1;
    unsigned slot=s->valid?1-s->slot:0;
    uint8_t data[SCD_SAVE_BYTES],readback[SCD_SAVE_BYTES];
    scd_save_encode(data,&s->pending,gen);
    rc=s->backend.write(s->backend.context,slot,data);
    if(rc)return s->status=error_status(rc);
    rc=s->backend.read(s->backend.context,slot,readback);
    if(rc || memcmp(data,readback,sizeof(data)))return s->status=rc?error_status(rc):SCD_SAVE_IO_ERROR;
    s->saved=s->pending;s->generation=gen;s->slot=slot;s->valid=s->any=1;s->dirty=0;
    return s->status=SCD_SAVE_OK;
}
const char *scd_save_message(scd_save_status status){
    static const char *const messages[]={"PROGRESS SAVED","NO SAVED GAME","OLDER SAVE RECOVERED",
        "SAVE DATA DAMAGED","BACKUP RAM UNAVAILABLE","BACKUP RAM NOT FORMATTED","BACKUP RAM FULL",
        "SAVE WRITE PROTECTED","SAVE COULD NOT BE VERIFIED"};
    return messages[status<=SCD_SAVE_IO_ERROR?status:SCD_SAVE_IO_ERROR];
}
void scd_settings_encode(uint8_t d[SCD_SETTINGS_BYTES],const scd_settings *s){
    memset(d,0,SCD_SETTINGS_BYTES);memcpy(d,"SCDC",4);d[4]=1;d[5]=SCD_SETTINGS_BYTES;
    d[6]=s->preset;d[7]=s->flags;put32(d+12,checksum(d,12));
}
int scd_settings_decode(const uint8_t d[SCD_SETTINGS_BYTES],scd_settings *s){
    *s=(scd_settings){0,0};
    if(memcmp(d,"SCDC",4) || d[4]!=1 || d[5]!=SCD_SETTINGS_BYTES || d[8] || d[9] || d[10] || d[11] ||
       checksum(d,12)!=get32(d+12) || d[6]>1 || (d[7]&~31u) || (!d[6])!=(!d[7]))return 0;
    s->preset=d[6];s->flags=d[7];return 1;
}
