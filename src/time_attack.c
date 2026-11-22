/* Time Attack records (src/time_attack.h). Code and tables are fe_ symbols: they
   run from the front-end overlay (src/saturn.x .zone_R0). */
#include "time_attack.h"
#include "player_plus.h"
#include <string.h>

/* scd_ta is defined in src/player.c, which every Saturn and host build links. */

/* ATTACK.MMD act-total thresholds (0xff2cd6-0xff2d1a): with timeAttackUnlock 21,
   cmpi.l #K,total / bge sets titleFlags bit 1 below 0x001E1505 (30'21"05), bit 2
   below 0x00192E0C (25'46"12) and bit 3 below 0x00251B39 (37'27"57). The total
   is minutes, seconds and centiseconds (see fe_ta_act_total). */
#define FE_TA_LIMIT(m,s,c) ((uint32_t)(m)*6000u+(uint32_t)(s)*100u+(uint32_t)(c))
static const uint32_t fe_ta_limits[3]={FE_TA_LIMIT(30,21,5),FE_TA_LIMIT(25,46,12),FE_TA_LIMIT(37,27,57)};
static const uint8_t fe_ta_limit_bits[3]={SCD_TA_FLAG_SPECIAL,SCD_TA_FLAG_VISUAL,SCD_TA_FLAG_DAGARDEN};

static uint32_t fe_ta_get32(const uint8_t *p){return (uint32_t)p[0]<<24|(uint32_t)p[1]<<16|(uint32_t)p[2]<<8|p[3];}
static void fe_ta_put32(uint8_t *p,uint32_t v){p[0]=v>>24;p[1]=v>>16;p[2]=v>>8;p[3]=v;}
static uint32_t fe_ta_crc(const uint8_t *p,unsigned n){
    uint32_t crc=~0u;
    while(n--){crc^=*p++;for(unsigned b=0;b<8;b++)crc=(crc>>1)^(0xedb88320u & (0u-(crc&1)));}
    return ~crc;
}
void fe_ta_records_default(scd_ta_records *r){
    memset(r,0,sizeof(*r));
    for(unsigned e=0;e<SCD_TA_ENTRIES;e++)for(unsigned k=0;k<SCD_TA_RANKS;k++){
        r->time[e][k]=SCD_TA_DEFAULT_TIME;memset(r->name[e][k],0x0B,3);
    }
    r->default_name[0]=0x23;r->default_name[1]=0x19;r->default_name[2]=0x1F;
}
void fe_ta_records_encode(uint8_t d[SCD_TA_FILE_BYTES],const scd_ta_records *r){fe_ta_records_encode_gen(d,r,0);}
void fe_ta_records_encode_gen(uint8_t d[SCD_TA_FILE_BYTES],const scd_ta_records *r,uint32_t generation){
    generation&=0xFFFFFFu;
    memset(d,0,SCD_TA_FILE_BYTES);memcpy(d,"SCDT",4);d[4]=generation?2:1;d[6]=SCD_TA_FILE_BYTES>>8;d[7]=SCD_TA_FILE_BYTES&255;
    d[13]=(uint8_t)(generation>>16);d[14]=(uint8_t)(generation>>8);d[15]=(uint8_t)generation;
    d[8]=r->unlock;d[9]=r->title_flags;memcpy(d+10,r->default_name,3);
    for(unsigned e=0;e<SCD_TA_ENTRIES;e++)for(unsigned k=0;k<SCD_TA_RANKS;k++){
        unsigned i=e*SCD_TA_RANKS+k;
        fe_ta_put32(d+16+i*4,r->time[e][k]);memcpy(d+352+i*4,r->name[e][k],3);
    }
    fe_ta_put32(d+688,fe_ta_crc(d,688));
}
static int fe_ta_code_valid(uint8_t c){return c<=0x24;}
int fe_ta_records_decode(const uint8_t d[SCD_TA_FILE_BYTES],scd_ta_records *out){uint32_t g;return fe_ta_records_decode_gen(d,out,&g);}
int fe_ta_records_decode_gen(const uint8_t d[SCD_TA_FILE_BYTES],scd_ta_records *out,uint32_t *generation){
    const uint32_t gen=(uint32_t)d[13]<<16|(uint32_t)d[14]<<8|d[15];
    if(memcmp(d,"SCDT",4) || d[4]<1 || d[4]>2 || (d[4]==1)!=(gen==0) || d[5] || d[6]!=(SCD_TA_FILE_BYTES>>8) || d[7]!=(SCD_TA_FILE_BYTES&255) ||
       fe_ta_crc(d,688)!=fe_ta_get32(d+688))return 0;
    scd_ta_records r;memset(&r,0,sizeof(r));
    r.unlock=d[8];r.title_flags=d[9];memcpy(r.default_name,d+10,3);
    if(r.unlock>SCD_TA_ACTS)return 0;
    for(unsigned i=0;i<3;i++)if(!fe_ta_code_valid(r.default_name[i]))return 0;
    for(unsigned e=0;e<SCD_TA_ENTRIES;e++)for(unsigned k=0;k<SCD_TA_RANKS;k++){
        unsigned i=e*SCD_TA_RANKS+k;
        r.time[e][k]=fe_ta_get32(d+16+i*4);memcpy(r.name[e][k],d+352+i*4,3);
        if(r.time[e][k]>SCD_TA_MAX_TIME || d[352+i*4+3])return 0;
        if(k && r.time[e][k]<r.time[e][k-1])return 0;
        for(unsigned c=0;c<3;c++)if(!fe_ta_code_valid(r.name[e][k][c]))return 0;
    }
    *out=r;*generation=gen;return 1;
}
int fe_ta_record_insert(scd_ta_records *r,unsigned entry,uint32_t frames){
    if(entry>=SCD_TA_ENTRIES)return -1;
    if(frames>SCD_TA_MAX_TIME)frames=SCD_TA_MAX_TIME;
    unsigned i=0;
    while(i<SCD_TA_RANKS && r->time[entry][i]<frames)i++;
    if(i==SCD_TA_RANKS)return -1;
    for(unsigned j=SCD_TA_RANKS-1;j>i;j--){
        r->time[entry][j]=r->time[entry][j-1];memcpy(r->name[entry][j],r->name[entry][j-1],3);
    }
    r->time[entry][i]=frames;
    static const uint8_t fe_ta_aaa[3]={0x0B,0x0B,0x0B};
    if(!memcmp(r->name[entry][i],fe_ta_aaa,3))memcpy(r->name[entry][i],r->default_name,3);
    return (int)i;
}
uint32_t fe_ta_act_total(const scd_ta_records *r){
    /* ATTACK.MMD 0xff2d5c turns each first place's frames into centiseconds
       (x100/60, truncated); 0xff2d78 then adds them with carries at 100 and 60. */
    uint32_t total=0;
    for(unsigned e=0;e<SCD_TA_ACTS;e++){
        uint32_t f=r->time[e][0];
        total+=f/3600*6000+f/60%60*100+f%60*100/60;
    }
    return total;
}
unsigned fe_ta_unlocks_update(scd_ta_records *r){
    if(r->unlock<SCD_TA_ACTS)return 0;
    uint32_t total=fe_ta_act_total(r);unsigned before=r->title_flags;
    for(unsigned i=0;i<3;i++)if(total<fe_ta_limits[i])r->title_flags|=fe_ta_limit_bits[i];
    return r->title_flags&~before;
}
void fe_ta_progress_unlock(scd_ta_records *r,unsigned zones_cleared){
    if(zones_cleared>7)zones_cleared=7;
    unsigned acts=zones_cleared*3;
    if(acts>r->unlock)r->unlock=(uint8_t)acts;
    if(r->unlock)r->title_flags|=SCD_TA_FLAG_TIME_ATTACK;
}
void fe_ta_time_text(char out[9],uint32_t frames){
    if(frames>SCD_TA_MAX_TIME)frames=SCD_TA_MAX_TIME;
    unsigned m=frames/3600,s=frames/60%60,c=frames%60*100/60;
    /* Retail shows M'SS"CC; the HUD alphabet has ':' but no quote marks. */
    out[0]=(char)('0'+m);out[1]=':';out[2]=(char)('0'+s/10);out[3]=(char)('0'+s%10);
    out[4]=':';out[5]=(char)('0'+c/10);out[6]=(char)('0'+c%10);out[7]=0;out[8]=0;
}
char fe_ta_name_char(uint8_t code){
    if(code<10)return (char)('0'+code);
    if(code>=0x0B && code<=0x24)return (char)('A'+code-0x0B);
    return ' ';
}
/* CD++ times never replace Classic records: the preset has its own table
   (docs/CDPP-PRESET-SPEC.md section 6). Named arrays keep the strings in
   .rodata.fe_* (the R0 overlay). */
/* src/player_plus.c defines the setting; host record tests link this weak 0. */
__attribute__((weak)) uint8_t scd_preset_flags;
static const char fe_ta_file_classic[12]="SCDSATURNTA",fe_ta_file_plus[12]="SCDSATURNTP";
static const char fe_ta_file_classic_b[12]="SCDSATURNTB",fe_ta_file_plus_b[12]="SCDSATURNTQ";
const char *fe_ta_file_name(void){return scd_preset_flags?fe_ta_file_plus:fe_ta_file_classic;}
const char *fe_ta_pair_name(unsigned preset,unsigned index){
    return preset?(index?fe_ta_file_plus_b:fe_ta_file_plus):(index?fe_ta_file_classic_b:fe_ta_file_classic);
}
static int fe_ta_device_error(int rc){return rc && rc!=5 && rc!=8;}
/* File buffers: front-end overlay data (.data.fe_*, as FE_DATA in src/frontend.c),
   not resident .bss. Only the fe_ overlay code below touches them. */
#if defined(__sh__)
#define FE_TA_DATA(name) __attribute__((section(".data." #name))) name
#else
#define FE_TA_DATA(name) name
#endif
static uint8_t FE_TA_DATA(fe_ta_load_buffer)[SCD_TA_FILE_BYTES];
static uint8_t FE_TA_DATA(fe_ta_store_data)[SCD_TA_FILE_BYTES];
static uint8_t FE_TA_DATA(fe_ta_store_readback)[SCD_TA_FILE_BYTES];
int fe_ta_records_load(const fe_ta_io *io,unsigned preset,scd_ta_records *r,fe_ta_file_state *st){
    memset(st,0,sizeof(*st));st->current=-1;
    fe_ta_records_default(r);
    int error=0;
    for(unsigned i=0;i<2;i++){
        int rc=io->read(fe_ta_pair_name(preset,i),fe_ta_load_buffer,SCD_TA_FILE_BYTES);
        if(rc==5)continue;
        st->present|=(uint8_t)(1u<<i);
        if(fe_ta_device_error(rc)){st->unreadable|=(uint8_t)(1u<<i);if(!error)error=rc;continue;}
        scd_ta_records rec;uint32_t gen;
        if(rc || !fe_ta_records_decode_gen(fe_ta_load_buffer,&rec,&gen))continue;
        /* The newer generation (24-bit serial order); a tie keeps index 0. */
        const uint32_t delta=(gen-st->generation)&0xFFFFFFu;
        if(st->current<0 || (delta && delta<0x800000u)){*r=rec;st->generation=gen;st->current=(int8_t)i;}
    }
    if(st->current>=0)return 0;
    return error?error:st->present?8:5;
}
int fe_ta_records_store(const fe_ta_io *io,unsigned preset,const scd_ta_records *r,fe_ta_file_state *st){
    uint8_t *const data=fe_ta_store_data,*const readback=fe_ta_store_readback;
    if(st->unreadable)return 9;
    const unsigned target=st->current>=0?1u-(unsigned)st->current:0u,old=1u-target;
    uint32_t gen=(st->generation+1u)&0xFFFFFFu;if(!gen)gen=1;
    fe_ta_records_encode_gen(data,r,gen);
    /* No room for the other file must leave the current verified records
       intact. Return BIOS 4 so the caller reports failure and can retry. */
    int rc=io->write(fe_ta_pair_name(preset,target),data,SCD_TA_FILE_BYTES);
    if(rc)return rc;
    st->present|=(uint8_t)(1u<<target);
    rc=io->read(fe_ta_pair_name(preset,target),readback,SCD_TA_FILE_BYTES);
    if(rc)return rc;
    if(memcmp(data,readback,SCD_TA_FILE_BYTES))return 8;
    st->current=(int8_t)target;st->generation=gen;
    /* The new file verified: the older one goes. If that fails, both stay and
       the next load takes the newer generation. */
    if((st->present>>old&1) && !io->remove(fe_ta_pair_name(preset,old)))st->present&=(uint8_t)~(1u<<old);
    return 0;
}
