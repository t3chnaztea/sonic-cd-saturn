#include <assert.h>
#include <stdio.h>
#ifndef BOSS_SOURCE
#define BOSS_SOURCE "boss.c"
#endif
#include BOSS_SOURCE
sprite_pattern *egg1arm3_pat2[3];
short scd_pcol_r1(sprite_status *p){(void)p;return 0;}
extern void fixture_pool_create(unsigned);
extern void fixture_pool_replace(unsigned,unsigned);
static unsigned events[1024][5],event_count,cutoff;
static void record(sprite_status *p){
    unsigned i=(unsigned)(p-actwk),mode=p->actfree[0];
    assert(event_count<1024);
    unsigned *e=events[event_count++];e[0]=i;e[1]=vslot_boss[i];e[2]=boss_interleave_after;e[3]=cutoff;e[4]=mode;
    p->actfree[2]++;p->actfree[0]=0;
    sprite_status *n;
    if(mode==1 && !actwkchk(&n))n->actno=44;
    if(mode==2 && !actwkchk2(p,&n))n->actno=44;
    if(mode==3){frameout(&actwk[p->actfree[1]]);if(!actwkchk(&n))n->actno=44;}
    if(mode==4)fixture_pool_create(5);
    if(mode==5)frameout(p);
    if(mode==6||mode==7)fixture_pool_replace(p->actfree[1],mode==7);
}
void (*fixture_routine(unsigned id))(sprite_status*){return id==44?record:NULL;}
void fixture_reset(void){scd_boss_reset();event_count=0;memset(events,0,sizeof(events));}
void fixture_maps(unsigned mode){
    /* Initial-state perturbations only. Both variants receive identical maps. */
    if(mode)vslot_sync();
    if(mode)vslot_ring_tick=scd_objects_vint();
    if(mode==1){vslot_sync();vslot_free(&vslot_pool[2]);}
    if(mode==2){vslot_sync();for(unsigned i=32;i<128;i++)vslot_used[i]=1;vslot_free(&vslot_pool[2]);vslot_used[33]=1;}
    if(mode==3){vslot_sync();uint8_t t=vslot_pool[1];vslot_pool[1]=vslot_pool[3];vslot_pool[3]=t;}
    if(mode==4){vslot_sync();vslot_free(&vslot_pool[35]);boss_reserved[35]=1;vslot_boss[35]=90;vslot_used[90]=1;actwk[35].actno=0;}
    if(mode==5){vslot_sync();vslot_pool[2]=vslot_pool[1];}
}
static void old_before(unsigned upper){
    for(;;){unsigned best=0,key=~0u;
        for(unsigned i=32;i<128;i++){
            if(i<SCD_BOSS_FIRST_SLOT && !boss_reserved[i])continue;
            if(!actwk[i].actno)continue;
            unsigned k=vslot_boss[i]?vslot_boss[i]:128u+i;
            if(k>boss_interleave_after && k<upper && k<key){key=k;best=i;}
        }
        if(!best)break;
        boss_interleave_after=key;
        void (*routine)(sprite_status*)=boss_routine(actwk[best].actno);
        if(routine)routine(&actwk[best]);
    }
}
void fixture_before(unsigned upper,int optimized){cutoff=upper;if(optimized)scd_boss_step_before(upper);else old_before(upper);}
void fixture_boss_setup(unsigned mode){
    scd_boss_set_round(mode==6||mode==7||mode==8?6:7);
    sprite_status *p;unsigned n=(mode>=6&&mode<=8)?34:4;
    for(unsigned i=0;i<n;i++){assert(!actwkchk(&p));p->actno=44;}
    if(mode==1)actwk[98].actfree[0]=2;
    if(mode==2){frameout(&actwk[97]);actwk[99].actfree[0]=1;}
    if(mode==3){actwk[98].actfree[0]=3;actwk[98].actfree[1]=100;}
    if(mode==4){vslot_free(&vslot_boss[98]);actwk[99].actno=250;}
    if(mode==5){actwk[97].actfree[0]=4;actwk[98].actfree[0]=5;}
    if(mode>=6&&mode<=8)scd_boss_set_round(7);
    if(mode==7){scd_boss_reset();scd_boss_set_round(7);assert(!actwkchk(&p));p->actno=44;}
    if(mode==9){vslot_boss[98]=vslot_boss[97];}
    if(mode!=8)scd_boss_step_begin();
}
void fixture_integration_setup(unsigned reuse){
    sprite_status *p;scd_boss_set_round(7);assert(!actwkchk(&p));p->actno=44;
    p->actfree[0]=reuse?7:6;p->actfree[1]=1;
    fixture_pool_create(1);fixture_pool_create(2);scd_boss_step_begin();
}
size_t fixture_dump(void *out){
    unsigned char *p=out;
#define COPY(x) memcpy(p,&(x),sizeof(x));p+=sizeof(x)
    COPY(vslot_pool);COPY(vslot_water);COPY(vslot_boss);COPY(vslot_used);COPY(boss_reserved);COPY(vslot_ring_tick);
    COPY(boss_interleave_after);COPY(boss_interleaved);COPY(round_no);COPY(events);COPY(event_count);
#undef COPY
    return (size_t)(p-(unsigned char*)out);
}
unsigned fixture_event_count(void){return event_count;}
