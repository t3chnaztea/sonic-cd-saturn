#include "save.h"
#include "special_progress.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef struct {uint8_t slots[2][SCD_SAVE_BYTES];unsigned present[2];int device,fail,torn,reads,read_rc[2],read_fails[2];unsigned writes,cut,cut_bytes;} disk;
static int status(void *ctx){return ((disk *)ctx)->device;}
static int read_slot(void *ctx,unsigned slot,uint8_t *data){
    disk *d=ctx;d->reads++;
    /* A device error on this slot for the next read_fails reads (-1: every read). */
    if(d->read_fails[slot]){if(d->read_fails[slot]>0)d->read_fails[slot]--;return d->read_rc[slot];}
    if(!d->present[slot])return 5;memcpy(data,d->slots[slot],SCD_SAVE_BYTES);return 0;
}
static int write_slot(void *ctx,unsigned slot,const uint8_t *data){
    disk *d=ctx;d->writes++;if(d->fail)return d->fail;d->present[slot]=1;
    memcpy(d->slots[slot],data,d->cut?d->cut_bytes:d->torn?13:SCD_SAVE_BYTES);return 0;
}
static uint32_t crc(const uint8_t *p,unsigned n){
    uint32_t c=~0u;while(n--){c^=*p++;for(unsigned b=0;b<8;b++)c=(c>>1)^(0xedb88320u&(0u-(c&1)));}return ~c;
}
/* Rewrite version/byte and reseal the CRC, as an older or newer build would. */
static void reseal(uint8_t *d,unsigned at,uint8_t value){
    d[at]=value;uint32_t c=crc(d,28);d[28]=c>>24;d[29]=c>>16;d[30]=c>>8;d[31]=c;
}
static scd_save_backend backend(disk *d){return (scd_save_backend){status,read_slot,write_slot,d};}
/* The storage contract preserves the last verified checkpoint until a new
   record has survived write/readback. These faults use the real save service;
   each cold open discards its in-memory generation and pending checkpoint. */
static void fault_tests(void){
    const scd_save_progress old={2,0,0,5,1,3,0,2},next={4,1,0,21,2,15,0,4};
    unsigned cuts=0,verifications=0,unreadable=0,pending=0;
    for(unsigned active=0;active<2;active++)for(unsigned existing=0;existing<2;existing++){
        for(unsigned cut=0;cut<SCD_SAVE_BYTES;cut++){
            disk d={0};scd_save s,boot;uint8_t retained[SCD_SAVE_BYTES],expected[SCD_SAVE_BYTES];
            scd_save_encode(d.slots[active],&old,18);d.present[active]=1;
            if(existing){scd_save_encode(d.slots[1-active],&old,17);d.present[1-active]=1;}
            memcpy(retained,d.slots[active],sizeof(retained));
            scd_save_encode(expected,&next,19);
            /* Every prefix really differs, including the 31-byte prefix. */
            assert(expected[31]!=d.slots[1-active][31]);
            scd_save_open(&s,backend(&d));d.cut=1;d.cut_bytes=cut;
            assert(scd_save_commit(&s,next)==SCD_SAVE_IO_ERROR && s.dirty);
            assert(s.generation==18 && !memcmp(&s.saved,&old,sizeof(old)));
            assert(!memcmp(retained,d.slots[active],sizeof(retained)));
            scd_save_open(&boot,backend(&d));
            assert(boot.valid && boot.generation==18 && boot.slot==active);
            assert(!memcmp(&boot.saved,&old,sizeof(old)));
            d.cut=0;assert(scd_save_retry(&s)==SCD_SAVE_OK && !s.dirty);
            scd_save_open(&boot,backend(&d));
            assert(boot.valid && boot.generation==19 && !memcmp(&boot.saved,&next,sizeof(next)));
            cuts++;
        }
    }
    /* A completed write whose verification read fails must not publish saved
       state. After reboot its valid bytes may legitimately be the newest save. */
    for(unsigned active=0;active<2;active++)for(int rc=1;rc<=8;rc++){
        disk d={0};scd_save s,boot;uint8_t retained[SCD_SAVE_BYTES];
        scd_save_encode(d.slots[active],&old,18);d.present[active]=1;
        memcpy(retained,d.slots[active],sizeof(retained));scd_save_open(&s,backend(&d));
        d.read_rc[1-active]=rc;d.read_fails[1-active]=1;
        assert(scd_save_commit(&s,next)!=SCD_SAVE_OK && s.dirty && s.generation==18);
        assert(!memcmp(&s.saved,&old,sizeof(old)) && !memcmp(retained,d.slots[active],sizeof(retained)));
        scd_save_open(&boot,backend(&d));
        assert(boot.valid && boot.generation==19 && !memcmp(&boot.saved,&next,sizeof(next)));
        assert(scd_save_retry(&s)==SCD_SAVE_OK && !s.dirty);verifications++;
    }
    /* One unreadable slot can be newer OR older than the readable companion.
       Never write while either generation is unknown. Recover before retry. */
    for(unsigned hidden=0;hidden<2;hidden++)for(unsigned newest=0;newest<2;newest++){
        for(int rc=1;rc<=7;rc++){if(rc==5)continue;
            for(unsigned persistent=0;persistent<2;persistent++){
                disk d={0};scd_save s,boot;uint8_t retained[2][SCD_SAVE_BYTES];
                for(unsigned slot=0;slot<2;slot++){
                    scd_save_encode(d.slots[slot],&old,slot==newest?50:49);d.present[slot]=1;
                }
                memcpy(retained,d.slots,sizeof(retained));
                d.read_rc[hidden]=rc;d.read_fails[hidden]=persistent?-1:1;
                scd_save_open(&s,backend(&d));
                assert(s.valid && s.unread==(1u<<hidden));
                scd_save_status st=scd_save_commit(&s,next);
                if(persistent){
                    assert(st==SCD_SAVE_IO_ERROR && s.dirty && !d.writes);
                    assert(!memcmp(retained,d.slots,sizeof(retained)));
                    d.read_fails[hidden]=0;assert(scd_save_retry(&s)==SCD_SAVE_OK);
                }else assert(st==SCD_SAVE_OK);
                assert(s.generation==51 && s.slot==1-newest && !s.dirty);
                assert(!memcmp(retained[newest],d.slots[newest],SCD_SAVE_BYTES));
                scd_save_open(&boot,backend(&d));
                assert(boot.valid && boot.generation==51 && !memcmp(&boot.saved,&next,sizeof(next)));
                unreadable++;
            }
        }
    }
    /* Repeated failed autosaves replace the pending checkpoint, while saved
       progress remains the last verified record. One retry saves the latest. */
    for(unsigned active=0;active<2;active++){
        disk d={0};scd_save s,boot;scd_save_progress latest=next;
        scd_save_encode(d.slots[active],&old,18);d.present[active]=1;
        scd_save_open(&s,backend(&d));
        for(int rc=1;rc<=8;rc++){
            latest.zone=(uint8_t)(rc%7);d.fail=rc;
            assert(scd_save_commit(&s,latest)!=SCD_SAVE_OK && s.dirty && s.generation==18);
            assert(!memcmp(&s.pending,&latest,sizeof(latest)) && !memcmp(&s.saved,&old,sizeof(old)));
            scd_save_open(&boot,backend(&d));assert(boot.generation==18 && !memcmp(&boot.saved,&old,sizeof(old)));
            pending++;
        }
        d.fail=0;assert(scd_save_retry(&s)==SCD_SAVE_OK && !s.dirty);
        scd_save_open(&boot,backend(&d));
        assert(boot.valid && boot.generation==19 && !memcmp(&boot.saved,&latest,sizeof(latest)));
    }
    printf("PASS: save fault injection: %u interrupted prefixes, %u verification-read errors, %u single-unreadable-slot cases, %u pending failures; cold recovery and latest retry verified\n",cuts,verifications,unreadable,pending);
}
int main(void){
    disk d={0};scd_save s,boot;uint8_t wire[SCD_SAVE_BYTES],bad[SCD_SAVE_BYTES];uint32_t gen;
    scd_save_progress p={6,2,2,127,3,127,1,0},out;
    scd_save_encode(wire,&p,0x12345678);assert(scd_save_decode(wire,&out,&gen));
    assert(!memcmp(&p,&out,sizeof(p)) && gen==0x12345678);
    for(unsigned bit=0;bit<SCD_SAVE_BYTES*8;bit++){
        memcpy(bad,wire,sizeof(bad));bad[bit/8]^=1u<<(bit%8);assert(!scd_save_decode(bad,&out,&gen));
    }
    /* Correct checksums do not make invalid versions or stage values safe. */
    for(unsigned field=0;field<sizeof(p);field++){
        scd_save_progress invalid=p;((uint8_t *)&invalid)[field]=255;
        scd_save_encode(bad,&invalid,1);assert(!scd_save_decode(bad,&out,&gen));
    }
    for(unsigned z=0;z<7;z++)for(unsigned a=0;a<3;a++)for(unsigned stone=0;stone<128;stone++){
        scd_save_progress v={z,a,a==2?3:0,stone,3,127,0,0};
        scd_save_encode(wire,&v,1);assert(scd_save_decode(wire,&out,&gen));assert(!memcmp(&v,&out,sizeof(v)));
    }
    /* v2 keeps curSpecStage in byte 19; v1 records (byte 19 zero) still load. */
    for(unsigned stage=0;stage<7;stage++){
        scd_save_progress v={1,0,0,0x15,1,1,0,(uint8_t)stage};
        scd_save_encode(wire,&v,9);assert(wire[4]==2 && wire[19]==stage);
        assert(scd_save_decode(wire,&out,&gen) && !memcmp(&v,&out,sizeof(v)));
    }
    for(unsigned stone=0;stone<128;stone++){
        scd_save_progress v={2,1,0,(uint8_t)stone,1,3,0,0};
        scd_save_encode(wire,&v,5);reseal(wire,4,1);
        assert(scd_save_decode(wire,&out,&gen) && gen==5 && out.time_stones==stone);
        assert(out.spec_stage==scd_special_stage_from_stones((uint8_t)stone) && out.spec_stage<7);
        assert(stone==127 || !(stone>>out.spec_stage&1));
    }
    {   scd_save_progress v={2,1,0,1,1,3,0,3};scd_save_encode(wire,&v,5);
        memcpy(bad,wire,sizeof(bad));reseal(bad,4,1);assert(!scd_save_decode(bad,&out,&gen)); /* v1 reserved byte 19 */
        memcpy(bad,wire,sizeof(bad));reseal(bad,4,3);assert(!scd_save_decode(bad,&out,&gen)); /* unknown version */
        memcpy(bad,wire,sizeof(bad));reseal(bad,20,1);assert(!scd_save_decode(bad,&out,&gen)); /* v2 reserved */
        memcpy(bad,wire,sizeof(bad));reseal(bad,19,7);assert(!scd_save_decode(bad,&out,&gen)); /* stage 8 */
    }
    scd_save_open(&s,backend(&d));assert(!s.valid && s.status==SCD_SAVE_EMPTY && !s.any);
    p=(scd_save_progress){0};assert(scd_save_commit(&s,p)==SCD_SAVE_OK);
    assert(s.valid && s.slot==0 && s.generation==1 && !s.dirty);
    p=(scd_save_progress){2,1,0,85,1,3,0,1};assert(scd_save_commit(&s,p)==SCD_SAVE_OK);
    scd_save_open(&boot,backend(&d));assert(boot.valid && boot.slot==1 && !memcmp(&boot.saved,&p,sizeof(p)));
    for(int failure=1;failure<=8;failure++){
        d.fail=failure;p.zone=3;assert(scd_save_commit(&s,p)!=SCD_SAVE_OK);
        assert(s.dirty && s.saved.zone==2 && s.generation==2);
        scd_save_open(&boot,backend(&d));assert(boot.saved.zone==2);
    }
    d.fail=0;d.torn=1;assert(scd_save_retry(&s)==SCD_SAVE_IO_ERROR);
    scd_save_open(&boot,backend(&d));assert(boot.valid && boot.saved.zone==2 && boot.status==SCD_SAVE_RECOVERED);
    d.torn=0;assert(scd_save_retry(&s)==SCD_SAVE_OK);assert(s.saved.zone==3 && !s.dirty);
    d.slots[s.slot][15]^=1;scd_save_open(&boot,backend(&d));assert(boot.saved.zone==2 && boot.status==SCD_SAVE_RECOVERED);
    d.slots[1-s.slot][15]^=1;scd_save_open(&boot,backend(&d));assert(!boot.valid && boot.any && boot.status==SCD_SAVE_CORRUPT);
    for(int rc=1;rc<=2;rc++){
        int reads=d.reads;d.device=rc;scd_save_open(&boot,backend(&d));assert(!boot.valid && reads==d.reads);
        assert(boot.status==(rc==1?SCD_SAVE_UNAVAILABLE:SCD_SAVE_UNFORMATTED));
    }
    d.device=0;memset(d.present,0,sizeof(d.present));scd_save_open(&s,backend(&d));
    scd_save_encode(d.slots[0],&p,0xffffffff);d.present[0]=1;
    scd_save_open(&s,backend(&d));p.zone=4;assert(scd_save_commit(&s,p)==SCD_SAVE_OK && s.generation==1);
    scd_save_open(&boot,backend(&d));assert(boot.saved.zone==4 && boot.generation==1);
    /* A device error while reading a slot is not an empty or damaged slot: its
       generation is unknown, so a commit must not write a lower one. Slots hold
       generations 50 (slot 0) and 49 (slot 1); both reads fail at open. */
    for(int rc=1;rc<=7;rc++){
        if(rc==5)continue;
        for(int persistent=0;persistent<2;persistent++){
            disk e={0};scd_save_progress old={3,1,0,5,1,7,0,2},newer={4,0,0,5,1,15,0,2};
            scd_save_encode(e.slots[0],&old,50);scd_save_encode(e.slots[1],&old,49);e.present[0]=e.present[1]=1;
            e.read_rc[0]=e.read_rc[1]=rc;e.read_fails[0]=e.read_fails[1]=persistent?-1:1;
            scd_save_open(&s,backend(&e));assert(!s.valid);
            scd_save_status st=scd_save_commit(&s,newer);
            e.read_fails[0]=e.read_fails[1]=0;scd_save_open(&boot,backend(&e));
            if(persistent){
                /* Still unreadable: refuse, keep the checkpoint pending, write nothing. */
                assert(st!=SCD_SAVE_OK && s.dirty);
                assert(boot.valid && boot.generation==50 && boot.saved.zone==3);
            }else{
                /* Readable again at the commit: the next generation, over the older slot. */
                assert(st==SCD_SAVE_OK && s.generation==51 && s.slot==1);
                assert(boot.valid && boot.generation==51 && boot.saved.zone==4);
            }
        }
    }
    fault_tests();
    puts("Save service: CRC bit flips, bounds, 2688 progress records, cold opens, all BIOS errors, torn writes, recovery, retry and generation wrap pass; v2 curSpecStage round trip and v1 upgrade pass; unreadable slots never get a lower generation");
}
