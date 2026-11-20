/* Real boss allocator in a separate TU so objects.c's weak services resolve
   to production implementations. Only initial state setup is test-owned. */
#include "../src/boss.c"
/* Unused boss rendering/collision services. No boss behavior runs here. */
sprite_pattern *egg1arm3_pat2[3];
void allocator_fixture_reset(void){
    memset(vslot_pool,0,sizeof(vslot_pool));memset(vslot_water,0,sizeof(vslot_water));
    memset(vslot_boss,0,sizeof(vslot_boss));memset(vslot_used,0,sizeof(vslot_used));
    memset(boss_reserved,0,sizeof(boss_reserved));
    vslot_boss_count=boss_reserved_count=0; /* src/boss.c skip counts */
}
void allocator_fixture_dead_borrowed(unsigned actor){
    /* A boss has just framed out. The native slot remains reserved until sync. */
    boss_reserved[actor]=1;vslot_boss[actor]=90;vslot_used[90]=1;
    boss_reserved_count++;vslot_boss_count++;
    actwk[actor].actno=0;
}
short scd_pcol_r1(sprite_status *p){(void)p;return 0;}
