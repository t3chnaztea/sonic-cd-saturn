/* Exact allocation assertions, not a reimplementation of the allocator. */
#include <assert.h>
#include <stdio.h>
#ifndef OBJECTS_SOURCE
#define OBJECTS_SOURCE "../src/objects.c"
#endif
#include OBJECTS_SOURCE
void allocator_fixture_reset(void);
void allocator_fixture_dead_borrowed(unsigned);
unsigned scd_boss_retail_slot_peek(unsigned);
static scd_placement layout[5];
static void reset(void){
    memset(pool,0,sizeof(pool));memset(actwk,0,128*sizeof(*actwk));
    memset(consumed,0,sizeof(consumed));memset(tt_ring_pending,0,sizeof(tt_ring_pending));
    memset(&stats,0,sizeof(stats));allocator_fixture_reset();
    objects_zone=1;objects_act=1;current_era=0;era_bit=1;zone_ops=NULL;
    active_placements=layout;active_placement_count=5;
    for(unsigned j=0;j<5;j++)layout[j]=(scd_placement){.x=100+24*j,.y=300,
        .type=SCD_OBJ_RING,.flags=j?TT_RING_MEMBER:0,.eras=1};
}
static void occupy(unsigned i){
    pool[i]=(slot){.type=SCD_OBJ_RING,.origin=65535};actwk[i+1].actno=SCD_OBJ_RING;
}
static void parent(unsigned i){occupy(i);pool[i].origin=0;tt_ring_pending[i]=1;}
/* Pre-batch source port: all three children use the real full-sync allocator.
   Original/native actor comparisons independently verify actor behavior. */
static void reference_sr_init(sprite_status *o){
    o->r_no0+=2;ss_ws(o,28,o->xposi.w.h);o->actflg|=4;o->sproffset=768;o->sprhs=8;o->sprvsize=8;o->patno=1;
    if(o->userflag.b.h>=2){o->userflag.b.l=o->patcnt=o->userflag.b.h-1;o->userflag.b.h=0;}
    sprite_status *n=o;
    for(int i=0;i<3;i++){
        sprite_status *t=sr_free_after(n);
        if(!t){tp_frameout(o);return;}
        n=t;
    }
    unsigned char r=4;
    for(int i=2;i>=0;i--){
        tp_actwkchk2(o,&n);
        tp_setactno(n,SCD_OBJ_R7_SPRING_R);
        n->actflg|=4;n->xposi.w.h=o->xposi.w.h;ss_ws(n,28,o->xposi.w.h);n->yposi.w.h=o->yposi.w.h;
        if(i==2){n->sproffset=1312;n->sprpri=5;tp_lset(o,0,(int)ss_index(n));}
        else{
            n->sproffset=768;n->sprhs=32;n->sprvsize=32;
            tp_lset(o,i==1?12:16,(int)ss_index(n));
        }
        n->userflag.b.h=o->userflag.b.h;tp_lset(n,0,(int)ss_index(o));n->r_no0=r;
        if(i==2)r+=4;
        r+=2;
    }
    if(!o->userflag.b.l){
        sprite_status *m=sr_link(o,0);
        if(m->r_no0<6 || m->userflag.b.l==2)tp_patchg(o,sr_rchg);
    }
}

static void setup(unsigned parent_slot,unsigned mode){
    reset();objects_zone=5;objects_act=1;
    for(unsigned k=0;k<parent_slot;k++)occupy(k);
    parent(parent_slot);pool[parent_slot].type=SCD_OBJ_R7_SPRING_R;
    actwk[parent_slot+1].actno=SCD_OBJ_R7_SPRING_R;
    if(mode==1)for(unsigned k=parent_slot+2;k<SCD_OBJECT_CAPACITY;k+=3)occupy(k);
    if(mode==2)allocator_fixture_dead_borrowed(parent_slot+3<32?35:parent_slot+3);
    if(mode==3)for(unsigned k=parent_slot+2;k<SCD_OBJECT_CAPACITY;k++)occupy(k);
}
int main(void){
    unsigned cases=0;
    for(unsigned parent_slot=0;parent_slot<80;parent_slot+=7)
    for(unsigned mode=0;mode<4;mode++){
        setup(parent_slot,mode);
        unsigned expected[3],found=0;
        for(unsigned k=parent_slot+1;k<SCD_OBJECT_CAPACITY && found<3;k++)if(!pool[k].type)expected[found++]=k+1;
        sprite_status *o=&actwk[parent_slot+1];sr_init(o);
        slot saved_pool[SCD_OBJECT_CAPACITY];sprite_status saved_actwk[128];unsigned saved_virtual[128];
        memcpy(saved_pool,pool,sizeof(pool));memcpy(saved_actwk,actwk,sizeof(saved_actwk));
        for(unsigned k=0;k<128;k++)saved_virtual[k]=scd_boss_retail_slot_peek(k);
        setup(parent_slot,mode);reference_sr_init(&actwk[parent_slot+1]);
        assert(!memcmp(saved_pool,pool,sizeof(pool)));assert(!memcmp(saved_actwk,actwk,sizeof(saved_actwk)));
        for(unsigned k=0;k<128;k++)assert(saved_virtual[k]==scd_boss_retail_slot_peek(k));
        setup(parent_slot,mode);sr_init(&actwk[parent_slot+1]);
        if(found<3){assert(!pool[parent_slot].type);cases++;continue;}
        assert((unsigned)tp_l(o,0)==expected[0]);
        assert((unsigned)tp_l(o,12)==expected[1]);
        assert((unsigned)tp_l(o,16)==expected[2]);
        unsigned prev=scd_boss_retail_slot_peek(parent_slot+1);
        for(unsigned k=0;k<3;k++){
            unsigned child=expected[k],v=scd_boss_retail_slot_peek(child);
            assert(actwk[child].actno==SCD_OBJ_R7_SPRING_R);
            if(!(v>prev))fprintf(stderr,"parent=%u mode=%u child=%u k=%u v=%u prev=%u\n",parent_slot,mode,child,k,v,prev);assert(v>prev);prev=v;
        }
        cases++;
    }
    printf("PASS: real SS spring allocator: %u parent/fragmented/borrowed/full cases; exact full-sync reference native/virtual maps, fragmented/borrowed slots and failed preflight\n",cases);
    return 0;
}
