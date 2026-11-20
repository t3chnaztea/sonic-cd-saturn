/* Host test for src/time_attack.c: retail defaults, codec, record insertion,
   unlocks. Run by tools/test-time-attack.sh. */
#include "time_attack.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
static int failures;
#define CHECK(c) do{if(!(c)){printf("FAIL: time attack: %s (line %d)\n",#c,__LINE__);failures++;}}while(0)
/* A model backup RAM of named files for the record-file pair. torn: the next
   write stores only that many bytes (power off mid-write: nothing after it
   runs). bad_read: that name's reads fail with a device error. room: when not
   0, the files that fit; a new name past it fails as the BIOS does (4, not
   enough memory) while an existing name still overwrites in place. */
typedef struct {char name[12];uint8_t data[SCD_TA_FILE_BYTES];int present;} mfile;
static mfile files[8];static int write_rc,torn,remove_rc,writes,removes,room;static char bad_read[12];
static mfile *mfind(const char *name,int make){
    for(unsigned i=0;i<8;i++)if(files[i].present && !strcmp(files[i].name,name))return &files[i];
    if(make)for(unsigned i=0;i<8;i++)if(!files[i].present){memset(&files[i],0,sizeof(files[i]));strcpy(files[i].name,name);files[i].present=1;return &files[i];}
    return NULL;
}
static int mread(const char name[12],uint8_t *data,uint32_t size){
    if(bad_read[0] && !strcmp(bad_read,name))return 3;
    mfile *f=mfind(name,0);if(!f)return 5;if(size!=SCD_TA_FILE_BYTES)return 8;memcpy(data,f->data,size);return 0;
}
static int mwrite(const char name[12],const uint8_t *data,uint32_t size){
    writes++;if(write_rc)return write_rc;
    if(room && !mfind(name,0)){int n=0;for(unsigned i=0;i<8;i++)n+=files[i].present;if(n>=room)return 4;}
    mfile *f=mfind(name,1);memcpy(f->data,data,torn?(uint32_t)torn:size);return 0;
}
static int mremove(const char name[12]){removes++;if(remove_rc)return remove_rc;mfile *f=mfind(name,0);if(!f)return 5;f->present=0;return 0;}
static const fe_ta_io mio={mread,mwrite,mremove};
static void mreset(void){memset(files,0,sizeof(files));write_rc=torn=remove_rc=writes=removes=room=0;bad_read[0]=0;}
static void pair_tests(void){
    scd_ta_records a,b,got;fe_ta_file_state st,st2;uint8_t d[SCD_TA_FILE_BYTES];
    fe_ta_records_default(&a);a.time[0][0]=1234;a.unlock=3;
    b=a;b.time[0][0]=1000;b.time[0][1]=1234;
    /* The old single-file scheme: a torn overwrite of the only copy loses every record. */
    mreset();fe_ta_records_encode(mfind("SCDSATURNTA",1)->data,&a);
    torn=300;fe_ta_records_encode(d,&b);mwrite("SCDSATURNTA",d,SCD_TA_FILE_BYTES);torn=0;
    CHECK(fe_ta_records_load(&mio,0,&got,&st)==8 && got.time[0][0]==SCD_TA_DEFAULT_TIME);
    /* An earlier build's single v1 file loads; the next store goes to the other
       name, verifies, then removes the v1 file. */
    mreset();fe_ta_records_encode(mfind("SCDSATURNTA",1)->data,&a);
    CHECK(fe_ta_records_load(&mio,0,&got,&st)==0 && st.current==0 && st.generation==0 && got.time[0][0]==1234);
    CHECK(fe_ta_records_store(&mio,0,&b,&st)==0 && st.current==1 && st.generation==1);
    CHECK(!mfind("SCDSATURNTA",0) && mfind("SCDSATURNTB",0));
    CHECK(fe_ta_records_load(&mio,0,&got,&st2)==0 && st2.current==1 && got.time[0][0]==1000);
    /* A torn store (power off before it verifies) leaves the previous records. */
    torn=300;fe_ta_records_store(&mio,0,&a,&st);torn=0;
    CHECK(mfind("SCDSATURNTA",0) && mfind("SCDSATURNTB",0));
    CHECK(fe_ta_records_load(&mio,0,&got,&st2)==0 && st2.current==1 && got.time[0][0]==1000);
    /* The next store overwrites the torn file, then removes the older one. */
    CHECK(fe_ta_records_store(&mio,0,&a,&st2)==0 && st2.current==0 && st2.generation==2 && !mfind("SCDSATURNTB",0));
    /* A failed write or a read back that differs keeps the older file. */
    write_rc=4;CHECK(fe_ta_records_store(&mio,0,&b,&st2)==4 && st2.current==0);write_rc=0;
    CHECK(fe_ta_records_load(&mio,0,&got,&st2)==0 && got.time[0][0]==1234 && st2.generation==2);
    torn=100;CHECK(fe_ta_records_store(&mio,0,&b,&st2)==8);torn=0;
    CHECK(mfind("SCDSATURNTA",0) && fe_ta_records_load(&mio,0,&got,&st2)==0 && got.time[0][0]==1234);
    /* A device error on either name refuses the store: that file may be newer. */
    strcpy(bad_read,"SCDSATURNTB");writes=0;
    CHECK(fe_ta_records_load(&mio,0,&got,&st2)==0 && st2.unreadable==2);
    CHECK(fe_ta_records_store(&mio,0,&b,&st2)==9 && !writes);
    bad_read[0]=0;
    /* A failed remove leaves both; the load takes the newer generation. */
    CHECK(fe_ta_records_load(&mio,0,&got,&st2)==0);remove_rc=7;
    CHECK(fe_ta_records_store(&mio,0,&b,&st2)==0 && mfind("SCDSATURNTA",0) && mfind("SCDSATURNTB",0));remove_rc=0;
    CHECK(fe_ta_records_load(&mio,0,&got,&st2)==0 && st2.current==1 && got.time[0][0]==1000 && st2.generation==3);
    /* Generation wrap: 0xFFFFFF is older than 1. */
    mreset();fe_ta_records_encode_gen(mfind("SCDSATURNTA",1)->data,&a,0xFFFFFF);
    CHECK(fe_ta_records_load(&mio,0,&got,&st2)==0 && fe_ta_records_store(&mio,0,&b,&st2)==0 && st2.generation==1);
    remove_rc=7;fe_ta_records_encode_gen(mfind("SCDSATURNTA",1)->data,&a,0xFFFFFF);
    CHECK(fe_ta_records_load(&mio,0,&got,&st2)==0 && st2.current==1 && got.time[0][0]==1000);remove_rc=0;
    /* The presets never share a file; nothing at all loads the defaults. */
    mreset();fe_ta_records_encode(mfind("SCDSATURNTA",1)->data,&a);
    CHECK(fe_ta_records_load(&mio,1,&got,&st2)==5 && got.time[0][0]==SCD_TA_DEFAULT_TIME && st2.current<0);
    CHECK(fe_ta_records_store(&mio,1,&b,&st2)==0 && mfind("SCDSATURNTP",0) && mfind("SCDSATURNTA",0));
    /* A first record fits on a one-file device. A replacement needs a second
       file; no room must preserve the old record and return the BIOS error. */
    mreset();room=1;
    CHECK(fe_ta_records_load(&mio,0,&got,&st2)==5 && fe_ta_records_store(&mio,0,&a,&st2)==0 && st2.current==0);
    writes=0;CHECK(fe_ta_records_store(&mio,0,&b,&st2)==4 && writes==1 && st2.current==0 && st2.generation==1);
    CHECK(mfind("SCDSATURNTA",0) && !mfind("SCDSATURNTB",0));
    CHECK(fe_ta_records_load(&mio,0,&got,&st2)==0 && st2.current==0 && st2.generation==1 && got.time[0][0]==1234);
    /* No room and no record file to reuse: the BIOS code returns, nothing changes. */
    mreset();room=1;mfind("OTHERGAME01",1);
    CHECK(fe_ta_records_load(&mio,0,&got,&st2)==5 && fe_ta_records_store(&mio,0,&a,&st2)==4 && st2.current<0 && !mfind("SCDSATURNTA",0));
    /* v2 carries its generation; v1 decodes as generation 0. */
    uint32_t g;fe_ta_records_encode_gen(d,&a,5);CHECK(fe_ta_records_decode_gen(d,&got,&g) && g==5 && d[4]==2);
    fe_ta_records_encode(d,&a);CHECK(fe_ta_records_decode_gen(d,&got,&g) && g==0 && d[4]==1);
}
/* BIOS full before allocation, followed by a would-be torn overwrite of the
   current file. Sweep every partial prefix, including the minimized 16 bytes,
   for each preset/current slot and both legacy/current file generations. */
static void full_storage_tests(void){
    scd_ta_records a,b,got;fe_ta_file_state st,cold,before_state;
    mfile before_files[8];unsigned cases=0,retries=0;
    fe_ta_records_default(&a);a.time[0][0]=1234;a.unlock=3;
    b=a;b.time[0][0]=1000;b.time[0][1]=1234;
    for(unsigned preset=0;preset<2;preset++)for(unsigned slot=0;slot<2;slot++)
    for(unsigned version=0;version<2;version++)for(unsigned n=0;n<SCD_TA_FILE_BYTES;n++){
        /* Exercise the minimized reproducer first so a red run stays short. */
        unsigned prefix=n==0?16:n<=16?n-1:n;
        uint32_t generation=version?7:0;
        mreset();room=1;
        fe_ta_records_encode_gen(mfind(fe_ta_pair_name(preset,slot),1)->data,&a,generation);
        CHECK(fe_ta_records_load(&mio,preset,&got,&st)==0 && st.current==(int)slot && st.generation==generation);
        CHECK(!memcmp(&a,&got,sizeof(a)));
        before_state=st;memcpy(before_files,files,sizeof(files));
        torn=(int)prefix;
        CHECK(fe_ta_records_store(&mio,preset,&b,&st)==4);
        CHECK(writes==1 && removes==0);
        CHECK(!memcmp(before_files,files,sizeof(files)));
        CHECK(!memcmp(&before_state,&st,sizeof(st)));
        torn=0;
        /* Fresh state objects model a cold load without reusing the store state. */
        CHECK(fe_ta_records_load(&mio,preset,&got,&cold)==0);
        CHECK(!memcmp(&a,&got,sizeof(a)) && !memcmp(&before_state,&cold,sizeof(cold)));
        cases++;
        if(failures)return;
        if(n==0){
            /* Retry the same in-memory result after another file's space frees. */
            room=0;writes=removes=0;
            CHECK(fe_ta_records_store(&mio,preset,&b,&st)==0 && writes==1 && removes==1);
            CHECK(st.current==(int)(1-slot) && st.generation==generation+1);
            CHECK(!mfind(fe_ta_pair_name(preset,slot),0));
            CHECK(fe_ta_records_load(&mio,preset,&got,&cold)==0 && !memcmp(&b,&got,sizeof(b)));
            retries++;
            if(failures)return;
        }
    }
    printf("PASS: time attack full storage: %u preserved-prefix cases, %u space-recovery retries; both presets, both slots, v1/v2\n",cases,retries);
}
int main(void){
    scd_ta_records r,back;uint8_t d[SCD_TA_FILE_BYTES];char t[9];
    fe_ta_records_default(&r);
    /* Initial Data.asm: 5'00"00, "AAA", default initials "YOU". */
    CHECK(r.time[0][0]==18000 && r.time[27][2]==18000);
    CHECK(r.name[5][1][0]==0x0B && fe_ta_name_char(r.name[5][1][2])=='A');
    CHECK(fe_ta_name_char(r.default_name[0])=='Y' && fe_ta_name_char(r.default_name[1])=='O' && fe_ta_name_char(r.default_name[2])=='U');
    fe_ta_time_text(t,18000);CHECK(!strcmp(t,"5:00:00"));
    fe_ta_time_text(t,3600+23*60+30);CHECK(!strcmp(t,"1:23:50"));
    fe_ta_time_text(t,99999999);CHECK(!strcmp(t,"9:59:98"));
    /* Insertion: TA.C game_init. */
    CHECK(fe_ta_record_insert(&r,3,20000)==-1);
    CHECK(fe_ta_record_insert(&r,3,5000)==0);
    CHECK(r.time[3][0]==5000 && r.time[3][1]==18000 && fe_ta_name_char(r.name[3][0][0])=='Y');
    r.name[3][0][0]=0x0C;  /* "BOU" */
    CHECK(fe_ta_record_insert(&r,3,6000)==1);
    CHECK(r.time[3][0]==5000 && r.time[3][1]==6000 && r.time[3][2]==18000);
    CHECK(fe_ta_record_insert(&r,3,5000)==0);   /* a tie takes the higher rank */
    CHECK(r.time[3][1]==5000 && r.time[3][2]==6000 && r.name[3][1][0]==0x0C);
    CHECK(fe_ta_record_insert(&r,28,1)==-1);
    /* Codec round trip and rejection. */
    r.unlock=12;r.title_flags=SCD_TA_FLAG_TIME_ATTACK;
    fe_ta_records_encode(d,&r);
    CHECK(fe_ta_records_decode(d,&back) && !memcmp(&back,&r,sizeof(r)));
    for(unsigned i=0;i<SCD_TA_FILE_BYTES;i+=37){uint8_t x[SCD_TA_FILE_BYTES];memcpy(x,d,sizeof(x));x[i]^=0x40;CHECK(!fe_ta_records_decode(x,&back));}
    /* Unlock: progress, then the act-total bits only with all 21 acts. */
    fe_ta_records_default(&r);
    fe_ta_progress_unlock(&r,1);CHECK(r.unlock==3 && (r.title_flags&SCD_TA_FLAG_TIME_ATTACK));
    fe_ta_progress_unlock(&r,0);CHECK(r.unlock==3);
    for(unsigned e=0;e<SCD_TA_ACTS;e++)r.time[e][0]=60*60;   /* 21'00"00 total */
    CHECK(fe_ta_unlocks_update(&r)==0);                         /* only 3 acts open */
    fe_ta_progress_unlock(&r,7);CHECK(r.unlock==21);
    CHECK(fe_ta_unlocks_update(&r)==(SCD_TA_FLAG_SPECIAL|SCD_TA_FLAG_VISUAL|SCD_TA_FLAG_DAGARDEN));
    fe_ta_records_default(&r);r.unlock=21;
    for(unsigned e=0;e<SCD_TA_ACTS;e++)r.time[e][0]=100*60;  /* 35'00"00: only D.A. Garden */
    CHECK(fe_ta_unlocks_update(&r)==SCD_TA_FLAG_DAGARDEN);
    fe_ta_records_default(&r);r.unlock=21;                  /* 105'00"00 */
    CHECK(fe_ta_unlocks_update(&r)==0);
    /* Retail sums centiseconds per act: 21 x 1'26"47 (5207 frames -> 86.78 s, 8678 cs)
       = 30'22"38 sets no bit; one frame in each act's centiseconds matters. */
    fe_ta_records_default(&r);r.unlock=21;
    for(unsigned e=0;e<SCD_TA_ACTS;e++)r.time[e][0]=5207;
    CHECK(fe_ta_act_total(&r)==21u*8678u);
    /* 30'21"05 = 182105 cs. 20 acts of 5204 f (8673 cs) + 5186 f (8643 cs) = 182103: below. */
    for(unsigned e=0;e<SCD_TA_ACTS;e++)r.time[e][0]=e?5204:5186;
    CHECK(fe_ta_act_total(&r)==182103u && (fe_ta_unlocks_update(&r)&SCD_TA_FLAG_SPECIAL));
    /* 20 x 5204 f + 5187 f (8645 cs) = 182105: at the limit, no bit. A frame sum
       (109267 f < 109269) would have set it: the centisecond truncation decides. */
    fe_ta_records_default(&r);r.unlock=21;
    for(unsigned e=0;e<SCD_TA_ACTS;e++)r.time[e][0]=e?5204:5187;
    CHECK(fe_ta_act_total(&r)==182105u && !(fe_ta_unlocks_update(&r)&SCD_TA_FLAG_SPECIAL));
    pair_tests();
    full_storage_tests();
    if(failures)return 1;
    printf("PASS: time attack records: retail defaults, codec (%d B), insertion, unlocks, torn-write-safe file pair, full-storage preservation\n",SCD_TA_FILE_BYTES);
    return 0;
}
