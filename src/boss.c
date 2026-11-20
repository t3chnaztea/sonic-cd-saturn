/* Act 3 boss runtime: the PC services that the generated BOSS_1.C/COLI1.C
 * (Palmtree Panic, tools/prepare_boss.py), BOSS_3.C/GATE.C/COLI3.C
 * (Collision Chaos, tools/prepare_boss_r3.py) and BOSS_4.C/BOSS_4_2.C/WALL4.C/
 * COLI4.C (Tidal Tempest, tools/prepare_boss_r4.py) call. The boss routines, their
 * scratch words and the touch classes are the PC code; this file only places
 * actors, lists them for drawing and forwards palette, music and score events. */
#include "EQU.H"
#include "ACTION.H"
#include "BOSS_1.H"
#include "scd_boss.h"
#include "boss_zone.h"
#include "zone_code.h"
#include "scd_objects.h"
#include "scd_player.h"
#include "water.h"
#include <string.h>
#if !defined(__sh__)
#include <stdio.h>
#include <stdlib.h>
#endif
extern void soundset(short);
#ifdef SCD_BOSS_REFERENCE
#include "BOSS_PATTERNS.H"
#define ARM3_SECOND(p) ((p)->patbase==SCD_PATTERN_egg1arm3_pat2)
#else
extern sprite_pattern *egg1arm3_pat2[];
#define ARM3_SECOND(p) ((p)->patbase==egg1arm3_pat2)
#endif
/* scr_dir_tbl: area, left, right, top, bottom, camera line. SCR13C/D.C; the
   Tidal Tempest boss (BOSS_4_2.C egg4_scrreset) reads SCR43C/D.C's. */
short scr_dir_tbl[6]={4,0,3479,0,784,96};
static const short scr_dir_r1[6]={4,0,3479,0,784,96},scr_dir_r4[6]={4,0,3479,0,2048,96},scr_dir_r5[6]={4,0,3735,0,800,96},scr_dir_r6[6]={4,0,3479,0,1808,96},scr_dir_r7[6]={4,0,16023,0,1296,96},scr_dir_r8[6]={4,0,3735,0,784,96};
/* SCR53C/D.C for Quartz Quadrant. */
/* SCR83C/D.C for Metallic Madness. */
static const short *scr_dir_for(unsigned r){return r==8?scr_dir_r8:r==7?scr_dir_r7:r==6?scr_dir_r6:r==5?scr_dir_r5:r==4?scr_dir_r4:scr_dir_r1;}
static int view_x,view_y,palette_state,music_request=SCD_BOSS_MUSIC_NONE;
/* BOSS_8.C egg8's retail LoadPLC(4) (fight bank) and LoadPLC(5) (Amy), which
   tools/prepare_boss_r8.py restores in the generated source. */
static int fight_art_request;
static uint8_t listed[8][32],listed_count[8];
/* The round whose boss is running: 1 (BOSS_1.C), 3 (BOSS_3.C) or 4 (BOSS_4.C). */
static unsigned round_no=1;
static unsigned boss6_art_age;
short scd_pcol_r1(sprite_status *p);
/* Every round's boss code runs from its zone overlay: Palmtree Panic's BOSS_1.C (the
   generated boss_1.c defines r1_boss_zone_ops), and Collision Chaos, Tidal Tempest and
   Quartz Quadrant (src/boss_r3.c, boss_r4.c, boss_r5.c with the generated boss_3.c,
   boss_4.c, boss_5.c). src/boss.c reaches it only through these zone ops
   (src/boss_zone.h); a host tool without a round's files gets its empty weak table. */
__attribute__((weak)) const scd_boss_zone_ops r1_boss_zone_ops={0},r3_boss_zone_ops={0},r4_boss_zone_ops={0},r5_boss_zone_ops={0},r6_boss_zone_ops={0},r7_boss_zone_ops={0},r8_boss_zone_ops={0};
/* A round's ops are usable only while its zone's overlay is loaded (src/zone_code.h):
   round_no stays 1 after a reset in every zone, and scd_boss_step looks routines up
   each update. Rounds 1, 3, 4, 5 are zones 0, 1, 2, 3. */
static const scd_boss_zone_ops *boss_zone(void){
    if(!scd_zone_code_ready(round_no==1?0:round_no-2))return NULL;
    return round_no==1?&r1_boss_zone_ops:round_no==3?&r3_boss_zone_ops:round_no==4?&r4_boss_zone_ops:round_no==5?&r5_boss_zone_ops:round_no==6?&r6_boss_zone_ops:round_no==7?&r7_boss_zone_ops:round_no==8?&r8_boss_zone_ops:NULL;
}
/* src/boss_r5.c: BOSS_5.C's belt colour work area, cleared at every reset. */
__attribute__((weak)) void scd_boss5_reset(void){}
__attribute__((weak)) void scd_boss6_reset(void){}
__attribute__((weak)) void scd_boss7_reset(void){}
__attribute__((weak)) void scd_boss8_reset(void){}
__attribute__((weak)) unsigned scd_boss8_kind(const sprite_status *p){(void)p;return 0;}
__attribute__((weak)) unsigned scd_boss7_kind(const sprite_status *p){(void)p;return 0;}
__attribute__((weak)) unsigned scd_boss6_kind(const sprite_status *p){(void)p;return 0;}
/* Host tests that link boss.c without src/objects.c (tools/test-boss.sh). */
__attribute__((weak)) void scd_objects_explosion_fire(int slot_index){(void)slot_index;}
__attribute__((weak)) void scd_boss4_reset(void){}
/* Standalone boss comparisons link without objects.c; the Saturn build uses
   objects.c's strong V-INT counter for one slot sync per gameplay update. */
__attribute__((weak)) unsigned scd_objects_vint(void){return 0;}
__attribute__((weak)) void scd_boss4_stream(void){}
__attribute__((weak)) void scd_boss4_wall(int x,int y,unsigned sub){(void)x;(void)y;(void)sub;}
/* Zone actors other code spawns into these slots: Collision Chaos's bumper
   break (actor 41, BOBINB.C, generated with PLAYSP3.C). */
__attribute__((weak)) void (*scd_zone_actor(unsigned id))(sprite_status *){(void)id;return NULL;}
/* PLAYER.C play01 calls its round's COLI pcol: COLI1.C, COLI3.C or COLI4.C. */
short pcol(sprite_status *p){const scd_boss_zone_ops *zone=boss_zone();return zone && zone->pcol?zone->pcol(p):scd_pcol_r1(p);}
/* The running round's act_tbl entry for a boss actor; NULL for other ids. */
static void (*boss_routine(unsigned id))(sprite_status *){
    const scd_boss_zone_ops *zone=boss_zone();return zone && zone->routine?zone->routine(id):NULL;
}

/* Retail slot order. The original keeps one actor table: ACTSET.C actwkchk hands
   out the lowest free actor from slot 32 to level objects, the water code's
   bubbles and the boss actors alike, and the level runs actors in slot order.
   A child that actwkchk places below its parent (a free slot left by a bubble
   or a removed object) first runs on the next update, and from then on before
   the parent; one placed above runs in the update that made it. Tidal Tempest's
   egg4 (slot 38 in the retail R43C fight) puts egg4awa bubbles in slots 35-37
   and 40+ this way. The native build keeps three pools (src/objects.c actors
   1-96, src/water.c's dynamic slots, the boss actors from SCD_BOSS_FIRST_SLOT),
   so each live actor also gets the slot the original would have given it:
   native pool and water actors when first seen each update, boss actors at
   actwkchk. Rounds 4 and 5 run their boss actors in that order (scd_boss_step);
   the other rounds keep native slot order. */
__attribute__((weak)) int water_slot_live(unsigned i){(void)i;return 0;}
/* src/water.c's dynamic slot table (NULL without water.c): vslot_sync reads
   each slot's actno directly, as water_slot_live does. */
__attribute__((weak)) const sprite_status *water_slot_table(void){return NULL;}
static uint8_t vslot_pool[SCD_OBJECT_CAPACITY+1],vslot_water[WATER_OBJECT_CAPACITY],vslot_boss[128],vslot_used[128],boss_reserved[128];
/* A retail child the native actor does not create, held for the actor's life:
   the Quartz Quadrant checkpoint's ball (Checkpoint/Main.asm .GenBall,
   FindObjSlot at its init: the lowest free slot; retail QQ2A row 3028 has the
   balls in slots 32 and 38 over posts 33 and 34). objects.c names the actors. */
static uint8_t vslot_companion[SCD_OBJECT_CAPACITY+1],companion_pending[SCD_OBJECT_CAPACITY+1];
/* The init runs in slot order during the object pass, so the ball's lowest free
   slot can be one an actor below the post frees in that pass (retail QQ2A 2792:
   the ring in slot 32 frames out before post 33's init takes 32 for its ball).
   Resolved at the end of the pass: a slot free when the post got its own, or
   freed since and below the post's. */
static uint32_t companion_free[4];static unsigned companion_pending_count;
static void vslot_free(uint8_t *v);
static void companion_request(unsigned i){
    if(companion_pending[i])return;
    for(unsigned s=0;s<128;s++){if(vslot_used[s])companion_free[s/32]&=~(1u<<(s%32));else companion_free[s/32]|=1u<<(s%32);}
    companion_pending[i]=1;companion_pending_count++;
}
static void companion_drop(unsigned i){vslot_free(&vslot_companion[i]);if(companion_pending[i]){companion_pending[i]=0;companion_pending_count--;}}
__attribute__((weak)) int scd_objects_slot_companion(unsigned actor){(void)actor;return 0;}
int scd_boss_borrowed_slot(unsigned actor){return actor<128 && boss_reserved[actor];}
/* Nonzero vslot_boss and boss_reserved entries: vslot_sync skips their scans
   when none exist (most updates of every round). */
static unsigned vslot_boss_count,boss_reserved_count;
static unsigned vslot_ring_tick=~0u;
/* vslot_gen counts every slot-map change: objects.c's MM order cache rebuilds on it. */
static unsigned vslot_gen;
static void vslot_free(uint8_t *v){if(*v){vslot_used[*v]=0;*v=0;vslot_gen++;}}
static uint8_t vslot_new(unsigned from){for(unsigned s=from<32?32:from;s<128;s++)if(!vslot_used[s]){vslot_used[s]=1;vslot_gen++;return (uint8_t)s;}return 0;}
static void boss_slot_free(unsigned i){if(vslot_boss[i]){vslot_free(&vslot_boss[i]);vslot_boss_count--;}}
static void boss_slot_set(unsigned i,uint8_t v){boss_slot_free(i);vslot_boss[i]=v;if(v)vslot_boss_count++;}
static void boss_reserve(unsigned i,int on){if(boss_reserved[i]!=(on?1:0)){boss_reserved[i]=on?1:0;if(on)boss_reserved_count++;else boss_reserved_count--;}}
unsigned scd_boss_slot_generation(void){return vslot_gen;}
/* Frees every dead actor's slot first, then gives the new ones the lowest
   free slots in pool, then water order. Each actor's liveness is read once
   (this runs at least twice per update over 150 actors). */
static void vslot_sync(void){
    uint8_t fresh_pool[SCD_OBJECT_CAPACITY+1],fresh_water[WATER_OBJECT_CAPACITY];
    unsigned pool_new=0,water_new=0;
    /* Pointer walks over the same entries; the reserved test only when a
       slot is reserved, the boss scan only when a boss slot is mapped. */
    {
        const sprite_status *a=&actwk[1];uint8_t *v=&vslot_pool[1];
        for(unsigned i=1;i<=SCD_OBJECT_CAPACITY;i++,a++,v++){
            if(!a->actno || (boss_reserved_count && boss_reserved[i])){if(*v){vslot_free(v);companion_drop(i);}}
            else if(!*v)fresh_pool[pool_new++]=(uint8_t)i;
        }
    }
    {
        const sprite_status *w=water_slot_table();
        for(unsigned i=1;i<WATER_OBJECT_CAPACITY;i++){
            if(!w || !w[i].actno){if(vslot_water[i])vslot_free(&vslot_water[i]);}
            else if(!vslot_water[i])fresh_water[water_new++]=(uint8_t)i;
        }
    }
    if(vslot_boss_count)for(unsigned i=32;i<128;i++)if(vslot_boss[i] && !actwk[i].actno){boss_slot_free(i);boss_reserve(i,0);}
    /* Each fresh actor takes the lowest free slot. Nothing is freed while they
       are assigned, so each search resumes after the previous one (a chunk
       crossing can bring twenty actors at once). */
    unsigned from=32;
    for(unsigned k=0;k<pool_new;k++){uint8_t v=vslot_new(from);vslot_pool[fresh_pool[k]]=v;if(v)from=v+1u;}
    for(unsigned k=0;k<water_new;k++){uint8_t v=vslot_new(from);vslot_water[fresh_water[k]]=v;if(v)from=v+1u;}
    /* The new actors' inits then run and take their children's slots. */
    for(unsigned k=0;k<pool_new;k++){unsigned i=fresh_pool[k];if(vslot_pool[i] && scd_objects_slot_companion(i))companion_request(i);}
}
void scd_boss_slot_sync(void){vslot_sync();}
/* vslot_sync when only actor CHILD can have changed since the previous sync
   (the MM ring spill adds one lost ring per step): the same free or lowest
   free slot from 32 that the full walk would give it. */
void scd_boss_slot_sync_one(unsigned child){
    if(!child || child>SCD_OBJECT_CAPACITY){vslot_sync();return;}
#if !defined(__sh__)
    /* Host check (SLOT_SYNC_CHECK): the full walk must leave the same map. */
    static int check=-1;if(check<0)check=getenv("SLOT_SYNC_CHECK")!=NULL;
    if(check){
        uint8_t p[sizeof vslot_pool],w[sizeof vslot_water],b[sizeof vslot_boss],u[sizeof vslot_used],r[sizeof boss_reserved];
        unsigned g=vslot_gen,bc=vslot_boss_count,rc=boss_reserved_count;
        memcpy(p,vslot_pool,sizeof p);memcpy(w,vslot_water,sizeof w);memcpy(b,vslot_boss,sizeof b);memcpy(u,vslot_used,sizeof u);memcpy(r,boss_reserved,sizeof r);
        vslot_sync();
        uint8_t fp[sizeof p],fw[sizeof w],fb[sizeof b],fu[sizeof u],fr[sizeof r];unsigned fg=vslot_gen,fbc=vslot_boss_count,frc=boss_reserved_count;
        memcpy(fp,vslot_pool,sizeof p);memcpy(fw,vslot_water,sizeof w);memcpy(fb,vslot_boss,sizeof b);memcpy(fu,vslot_used,sizeof u);memcpy(fr,boss_reserved,sizeof r);
        memcpy(vslot_pool,p,sizeof p);memcpy(vslot_water,w,sizeof w);memcpy(vslot_boss,b,sizeof b);memcpy(vslot_used,u,sizeof u);memcpy(boss_reserved,r,sizeof r);
        vslot_gen=g;vslot_boss_count=bc;boss_reserved_count=rc;
        uint8_t *v=&vslot_pool[child];
        if(!actwk[child].actno || (boss_reserved_count && boss_reserved[child])){if(*v){vslot_free(v);companion_drop(child);}}
        else if(!*v){*v=vslot_new(32);if(*v && scd_objects_slot_companion(child))companion_request(child);}
        if(memcmp(fp,vslot_pool,sizeof p)||memcmp(fw,vslot_water,sizeof w)||memcmp(fb,vslot_boss,sizeof b)||memcmp(fu,vslot_used,sizeof u)||
           memcmp(fr,boss_reserved,sizeof r)||fg!=vslot_gen||fbc!=vslot_boss_count||frc!=boss_reserved_count){fprintf(stderr,"Slot sync check: actor %u differs\n",child);abort();}
        static unsigned checked;fprintf(stderr,"Slot sync check: %u identical\n",++checked);
        return;
    }
#endif
    uint8_t *v=&vslot_pool[child];
    if(!actwk[child].actno || (boss_reserved_count && boss_reserved[child])){if(*v){vslot_free(v);companion_drop(child);}}
    else if(!*v){*v=vslot_new(32);if(*v && scd_objects_slot_companion(child))companion_request(child);}
}
/* A record the native spawner skips but the original spawns and deletes in its
   own first update (a ring group whose rings were all taken: ObjRing_Init)
   holds a slot through SpawnObjects. Released at the end of the object pass. */
static uint8_t vslot_transient[16];static unsigned vslot_transient_count;
void scd_boss_slot_transient(void){
    vslot_sync();
    if(vslot_transient_count<16)vslot_transient[vslot_transient_count++]=vslot_new(32);
}
void scd_boss_slot_transient_end(void){
    while(vslot_transient_count)vslot_free(&vslot_transient[--vslot_transient_count]);
    if(companion_pending_count){
        vslot_sync();
        for(unsigned i=1;i<=SCD_OBJECT_CAPACITY && companion_pending_count;i++)if(companion_pending[i]){
            companion_pending[i]=0;companion_pending_count--;
            if(!vslot_pool[i] || vslot_companion[i])continue;
            for(unsigned s=32;s<128;s++)if(!vslot_used[s] && (s<vslot_pool[i] || (companion_free[s/32]>>(s%32)&1))){
                vslot_used[s]=1;vslot_gen++;vslot_companion[i]=(uint8_t)s;break;}
        }
    }
}
/* ObjRing_Init: a group member takes the first free slot after its head. */
void scd_boss_slot_after(unsigned child,unsigned parent){
    if(!child || child>SCD_OBJECT_CAPACITY || !parent || parent>SCD_OBJECT_CAPACITY)return;
    vslot_sync();vslot_free(&vslot_pool[child]);
    vslot_pool[child]=vslot_new(vslot_pool[parent]?vslot_pool[parent]+1u:32u);
}
/* ACTSET.C actwkchk (retail R83C $207534) hands out the lowest free slot from
   32 when it is called: a child gets its retail slot at once, while slots of
   actors that frame out later in the same update are still taken. */
void scd_boss_slot_first(unsigned child){
    if(!child || child>SCD_OBJECT_CAPACITY)return;
    vslot_sync();vslot_free(&vslot_pool[child]);vslot_pool[child]=vslot_new(32);
}
/* The next member of the same group, when the only actor created since the
   previous scd_boss_slot_after is this child: a sync would just give it the
   lowest free slot and the line above would free that again. */
void scd_boss_slot_after_next(unsigned child,unsigned parent){
    if(!child || child>SCD_OBJECT_CAPACITY || !parent || parent>SCD_OBJECT_CAPACITY)return;
    vslot_free(&vslot_pool[child]);
    vslot_pool[child]=vslot_new(vslot_pool[parent]?vslot_pool[parent]+1u:32u);
}
unsigned scd_boss_retail_slot_peek(unsigned actor){return actor<128?(actor<=SCD_OBJECT_CAPACITY && !boss_reserved[actor]?vslot_pool[actor]:actor>=32?vslot_boss[actor]:0):0;}
unsigned scd_boss_retail_slot(unsigned actor){
    if(!actor || actor>SCD_OBJECT_CAPACITY)return actor+31u;
    /* Lost rings query their retail slots up to 32 times per update. The slot
       map is stable after the first sync; a newly created actor has no entry
       and still forces a sync before its first floor check. */
    unsigned tick=scd_objects_vint();
    if(vslot_ring_tick!=tick || !vslot_pool[actor]){vslot_sync();vslot_ring_tick=tick;}
    return vslot_pool[actor]?vslot_pool[actor]:actor+31u;
}
/* A selection pass still performs the first lookup, including its tick/slot
   synchronization. Mapped entries then need no calls; callers must use the
   ordinary lookup for an unmapped actor. This is a live read-only view, not a
   snapshot: a later lookup can synchronize new children and mutate the map. */
/* Host check only (objects.c MM_ORDER_CHECK): 1 when scd_boss_retail_slot(actor)
   would return the mapped slot without synchronizing. */
int scd_boss_retail_slot_pure(unsigned actor){return actor && actor<=SCD_OBJECT_CAPACITY && vslot_ring_tick==scd_objects_vint() && vslot_pool[actor];}
const uint8_t *scd_boss_retail_slot_view(void){return vslot_pool;}
const uint8_t *scd_boss_retail_slot_map(unsigned actor,unsigned *first_key){
    *first_key=scd_boss_retail_slot(actor);return vslot_pool;
}
/* ACTSET.C searches free actors from slot 32; slots 1-96 belong to the native pool. */
int actwkchk(sprite_status **actor){
    vslot_sync();
    uint8_t retail=vslot_new(32);
    if(!retail)return -1;
    for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++)if(!actwk[i].actno){*actor=&actwk[i];boss_slot_set(i,retail);return 0;}
    if(round_no==6)for(unsigned i=32;i<SCD_BOSS_FIRST_SLOT;i++)if(!actwk[i].actno){*actor=&actwk[i];boss_reserve(i,1);boss_slot_set(i,retail);return 0;}
    vslot_used[retail]=0;vslot_gen++;
    return -1;
}
/* ACTSET.C actwkchk2: the first free actor after the caller, up to 127. */
int actwkchk2(sprite_status *p,sprite_status **actor){
    for(sprite_status *q=p+1;q<=&actwk[127];q++)if(!q->actno){
        *actor=q;unsigned i=(unsigned)(q-actwk),caller=(unsigned)(p-actwk);
        if(i>=SCD_BOSS_FIRST_SLOT){vslot_sync();boss_slot_free(i);boss_slot_set(i,vslot_new(caller<128 && vslot_boss[caller]?vslot_boss[caller]+1u:32u));}
        return 0;
    }
    return -1;
}
void frameout(sprite_status *p){
    unsigned i=(unsigned)(p-actwk);
    if(i>=32 && i<128 && (i>=SCD_BOSS_FIRST_SLOT || boss_reserved[i])){boss_slot_free(i);boss_reserve(i,0);}
    memset(p,0,sizeof(*p));
}
/* ACTION.C actionsub, with patset's "drawn" bit 7: actors inside the view join
 * their priority list in call order. */
void actionsub(sprite_status *p){
    p->actflg&=127;
    if(p->actflg&12){
        int x=p->xposi.w.h-view_x,y=p->yposi.w.h-view_y;
        if(x+p->sprhsize<0 || x-p->sprhsize>=320 || y+p->sprvsize<0 || y-p->sprvsize>=224)return;
    }
    unsigned priority=p->sprpri&7;
    if(p->actno && p->patbase && listed_count[priority]<32){
        listed[priority][listed_count[priority]++]=(uint8_t)(p-actwk);p->actflg|=128;
    }
}
void divdevset(int plc){(void)plc;}
/* GAME.C sRandom is the host RNG. Sonic 1's RandomNumber (the Mega Drive
   engine's) stands in, on its own seed. */
static uint32_t random_seed;
static unsigned boss_interleaved,boss_interleave_after;
static unsigned boss_interleave_first=32;
static int boss_random(void){
    uint32_t d1=random_seed?random_seed:0x2A6D365Au,d0=d1;
    d1=(d1<<2)+d0;d1=(d1<<3)+d0;
    d0=(d0&0xFFFF0000u)|(d1&65535u);
    d1=d1<<16|d1>>16;
    d0=(d0&0xFFFF0000u)|((d0+d1)&65535u);
    d1=(d1&0xFFFF0000u)|(d0&65535u);
    random_seed=d1<<16|d1>>16;
    return (int)d0;
}
int (*sRandom)(void)=boss_random;
/* PLAYSUB.C tensuu0: the points actor (28) becomes the native Collision Chaos
   points object, as the pocket's (src/objects_pocket.inc). */
void tensuu0(sprite_status *p,unsigned char uf_data){
    scd_objects_spawn(85u,p->xposi.w.h,p->yposi.w.h,(unsigned)(uf_data|128),0);
}
/* colorset2 into line 1. COL1C/D.C: 5 is the boss palette. COL3C/D.C: 6 is the
 * boss palette (zone3colboss1) and 5 the white flash (zone3colboss0). COL4C/D.C:
 * 5 is boss4color. genecolor loads the capsule's. */
void colorset2(int color){
    if(round_no==8){
        /* COL8C/D.C colorset2: 7-9 load the boss colours, 11 Amy's (EMIE8.C). */
        const scd_boss_zone_ops *zone=boss_zone();if(zone && zone->colorset2)zone->colorset2(color);
        palette_state=color==11?SCD_BOSS_PALETTE_LEVEL:SCD_BOSS_PALETTE_BOSS8;
    }else if(round_no==7)palette_state=color==6?SCD_BOSS_PALETTE_BOSS7:SCD_BOSS_PALETTE_LEVEL;
    else if(round_no==6)palette_state=color==6?SCD_BOSS_PALETTE_BOSS6:SCD_BOSS_PALETTE_LEVEL;
    else if(round_no==5)palette_state=color==6?SCD_BOSS_PALETTE_BOSS5:SCD_BOSS_PALETTE_LEVEL;
    else if(round_no==4)palette_state=color==5?SCD_BOSS_PALETTE_BOSS4:SCD_BOSS_PALETTE_LEVEL;
    else if(round_no==3)palette_state=color==6?SCD_BOSS_PALETTE_BOSS3:color==5?SCD_BOSS_PALETTE_FLASH3:SCD_BOSS_PALETTE_LEVEL;
    else palette_state=color==5?SCD_BOSS_PALETTE_BOSS:SCD_BOSS_PALETTE_LEVEL;
}
void genecolor(void){palette_state=SCD_BOSS_PALETTE_CAPSULE;}
/* LOADER2.C: 103 starts the boss track; BOSS_1.C returns to the zone track with
 * 16/17, BOSS_3.C with 19/20, BOSS_4_2.C with 22/23 and BOSS_5.C with 25/26 (generate_flag). 126 (the leg landing PCM
 * effect) has no sample in this build. */
void sub_sync(short request){
    if(request==104)music_request=SCD_BOSS_MUSIC_FINAL;
    else if(request==103)music_request=SCD_BOSS_MUSIC_BOSS;
    else if(request==16 || request==17 || request==19 || request==20 || request==22 || request==23 || request==25 || request==26 || request==28 || request==29 || request==31 || request==32)music_request=SCD_BOSS_MUSIC_ZONE;
    /* PLAYSP3.C bob: WaveRequest(85), the Collision Chaos bumper-break PCM; the
       native effect id is 1000+request (FM effect 146 is the jump). */
    else if(request==146)soundset(1146);
    /* PLAYER.C bye_chk: WaveRequest(78), "I'm outta here" (PCMS $B4 in SNCBNK3B). */
    else if(request==121)soundset(121);
}
/* SCORE.C score units are tens of display points. */
void scoreup(unsigned int points){scd_player_points(points*10u);}

void scd_boss_reset(void){
    fight_art_request=0;
    for(unsigned i=32;i<SCD_BOSS_FIRST_SLOT;i++)if(boss_reserved[i])memset(&actwk[i],0,sizeof(actwk[i]));
    memset(actwk+SCD_BOSS_FIRST_SLOT,0,sizeof(actwk[0])*(128-SCD_BOSS_FIRST_SLOT));
    memset(boss_reserved,0,sizeof(boss_reserved));boss_reserved_count=0;
    memset(listed_count,0,sizeof(listed_count));
    memset(vslot_pool,0,sizeof(vslot_pool));memset(vslot_companion,0,sizeof(vslot_companion));memset(companion_pending,0,sizeof(companion_pending));companion_pending_count=0;memset(vslot_water,0,sizeof(vslot_water));memset(vslot_boss,0,sizeof(vslot_boss));memset(vslot_used,0,sizeof(vslot_used));vslot_boss_count=0;
    vslot_gen++;
    vslot_ring_tick=~0u;
    bossflag=bossstart=0;palette_state=SCD_BOSS_PALETTE_LEVEL;music_request=SCD_BOSS_MUSIC_NONE;
    round_no=1;boss_interleaved=boss_interleave_after=0;boss_interleave_first=32;boss6_art_age=0;random_seed=0;memcpy(scr_dir_tbl,scr_dir_r1,sizeof(scr_dir_tbl));scd_boss4_reset();scd_boss5_reset();scd_boss6_reset();scd_boss7_reset();scd_boss8_reset();
}
void scd_boss_create(int x,int y){scd_boss_create_sub(x,y,0,1);}
void scd_boss_set_round(unsigned round){
    if(round!=round_no){round_no=round;memcpy(scr_dir_tbl,scr_dir_for(round),sizeof(scr_dir_tbl));}
}
/* tools/object_layouts.py: subtype bit 6 is egg3dai_l (actor 49), bit 5
 * egg3dai_s (48), bit 4 egg4air (74), bit 3 egg4 (76), bit 2 the layout wall4
 * (71; its low bits are WALL4.C's userflag); otherwise egg1 (42). */
/* round is the loaded zone's original round (src/objects.c objects_round);
 * the subtype bits pick the actor within it. */
void scd_boss_create_sub(int x,int y,unsigned subtype,unsigned round){
    unsigned id=round==3?(subtype&SCD_BOSS_EGG3DAI_L?49:subtype&SCD_BOSS_EGG3DAI_S?48:0):
        round==4?(subtype&SCD_BOSS_EGG4AIR?74:subtype&SCD_BOSS_EGG4?76:subtype&SCD_BOSS_WALL4?71:0):
        round==5?(subtype&SCD_BOSS_EGG5MECA1?51:subtype&SCD_BOSS_EGG5HARI?33:0):round==6?52:round==7?44:round==8?63:round==1?42:0;
    if(!id)return;
    scd_boss_set_round(round);
    if(id==71){scd_boss4_wall(x,y,subtype&3);return;}
    sprite_status *p;
    if(actwkchk(&p))return;
    p->actno=id;p->xposi.w.h=x;p->yposi.w.h=y;
}
/* WALL4.C frameout_s_ reads the PC scroll position (scra_h_posit). */
void scd_boss_camera(int x,int y){view_x=x;view_y=y;scra_h_posit.w.h=(short)x;}
/* The boss itself, not WALL4.C's gates or the layout wall. */
/* The spike wall egg5hari (33) is not the boss either. */
static int boss_actor(unsigned id){return id!=71 && !(round_no==5 && id==33) && boss_routine(id)!=NULL;}
/* SS3 interleaves the race and ordinary actors in the original slot order.
 * HARI73 must see Metal's current X when its virtual slot follows his. */
void scd_boss_step_begin(void){
    memset(listed_count,0,sizeof(listed_count));
    vslot_sync();boss_interleaved=1;boss_interleave_after=0;
    /* R7 creates boss owners only in 97..127. Check inherited lower borrowed
       owners once per pass so set_round without reset retains its semantics.
       Only R6 allocation can add a lower reservation; R7 can only free one. */
    boss_interleave_first=32;
    if(round_no==7){
        boss_interleave_first=SCD_BOSS_FIRST_SLOT;
        for(unsigned i=32;i<SCD_BOSS_FIRST_SLOT;i++)if(boss_reserved[i]){
            boss_interleave_first=32;break;
        }
    }
}
void scd_boss_step_before(unsigned upper){
    for(;;){
        unsigned best=0,key=~0u;
        for(unsigned i=(round_no==7 && boss_interleaved)?boss_interleave_first:32;i<128;i++){
            if(i<SCD_BOSS_FIRST_SLOT && !boss_reserved[i])continue;
            if(!actwk[i].actno)continue;
            unsigned k=vslot_boss[i]?vslot_boss[i]:128u+i;
            if(k>boss_interleave_after && k<upper && k<key){key=k;best=i;}
        }
        if(!best)break;
        boss_interleave_after=key;
        void (*routine)(sprite_status *)=boss_routine(actwk[best].actno);
        if(routine)routine(&actwk[best]);
    }
}
void scd_boss_step(void){
    if(!boss_interleaved)memset(listed_count,0,sizeof(listed_count));
    if(round_no==4)scd_boss4_stream();
    vslot_sync();
    /* Quartz Quadrant too: retail R53C puts egg5bomb in slot 32, below its
       egg5catch (41), so the bomb reads the catcher's state one update late. */
    if(boss_interleaved){
        scd_boss_step_before(~0u);boss_interleaved=0;
    }else if(round_no==4 || round_no==5 || round_no==6 || round_no==7 || round_no==8){
        /* Retail slot order: each pass runs the live boss actor with the lowest
           retail slot above the last one run, so an actor placed below the running
           one waits for the next update. Actors without a retail slot (beyond the
           original's 96) run last, in native order. */
        unsigned last=0;
        for(;;){
            unsigned best=0,key=~0u;
            for(unsigned i=32;i<128;i++){
                if(i<SCD_BOSS_FIRST_SLOT && !boss_reserved[i])continue;
                if(!actwk[i].actno)continue;
                unsigned k=vslot_boss[i]?vslot_boss[i]:128u+i;
                if(k>last && k<key){key=k;best=i;}
            }
            if(!best)break;
            last=key;
            unsigned id=actwk[best].actno;
            void (*routine)(sprite_status *)=id==41?scd_zone_actor(id):boss_routine(id);
            if(routine)routine(&actwk[best]);
        }
    }else for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++){
        unsigned id=actwk[i].actno;
        void (*routine)(sprite_status *)=id==41?scd_zone_actor(id):boss_routine(id);
        if(routine)routine(&actwk[i]);
    }
    /* bom_set and arm_bom explosions (actno 24) run as native explosion objects. */
    for(unsigned i=32;i<128;i++)if((i>=SCD_BOSS_FIRST_SLOT || boss_reserved[i]) && actwk[i].actno==24){
        int e=scd_objects_spawn(SCD_OBJ_EXPLOSION,actwk[i].xposi.w.h,actwk[i].yposi.w.h,1,0);
        /* Every boss's actno 24 leaves the subtype (userflag.b.h) 0: ObjExplosion's and
           PLAYSUB bakuha's fire (bakuchg 0), not the enemy-kill smoke. */
        if(e>=0 && !actwk[i].userflag.b.h){actwk[e+1].userflag.b.h=0;scd_objects_explosion_fire(e);}
        /* Every boss's own actno 24 sets r_no1 (BOSS_1/3/5/8 255, BOSS_4 1), so
           PLAYSUB bakuha makes no score and no flower (retail MM3D: Amy gets slot 36
           at row 8354; retail TT3C has no flowers after the fight). R8's bom_set also
           sets userflag.b.l -1, which bakuha's init reads for the priority bit. */
        if(e>=0){actwk[e+1].r_no1=actwk[i].r_no1;actwk[e+1].userflag.b.l=actwk[i].userflag.b.l;}
        memset(&actwk[i],0,sizeof(actwk[i]));
    }
    if(round_no==6 && (bossstart&31)==6 && boss6_art_age<129)boss6_art_age++;
}
unsigned scd_boss6_art_age(void){return boss6_art_age;}
/* Back to front: priority 7 first; within a priority, later calls are further back. */
unsigned scd_boss_views(scd_boss_view *views,unsigned capacity){
    unsigned n=0;
    for(unsigned priority=8;priority--;)for(unsigned k=listed_count[priority];k--;){
        const sprite_status *p=&actwk[listed[priority][k]];
        unsigned frame;
        /* BOBINB.C bumper break (zone art kind 249, every Collision Chaos act). */
        if(p->actno==41){if(n<capacity)views[n++]=(scd_boss_view){p->xposi.w.h,p->yposi.w.h,p->patno,p->actflg&3,priority,249};continue;}
        if(round_no==5){
            /* Zone art kinds (tools/extract_mmd.py QQ_BOSS_KIND): 240 egg5meca1, 241 egg5meca2,
               242 egg5meca3, 243 egg5pipe, 244 egg5, 245 egg5catch, 246 egg5bomb/bomb2,
               247 egg5hibana, 248 egg5hari; egg5bakuha's bakupat uses the common frames and
               egg5belt (34) draws nothing. */
            static const uint16_t kinds5[64]={[32]=247,[33]=248,[35]=SCD_BOSS_KIND_EXPLOSION,[50]=244,[51]=240,[52]=241,[53]=242,[54]=243,[55]=245,[56]=246,[57]=246};
            if(p->actno<64 && kinds5[p->actno] && n<capacity)
                views[n++]=(scd_boss_view){p->xposi.w.h,p->yposi.w.h,p->patno,p->actflg&3,priority,kinds5[p->actno]};
            continue;
        }
        if(round_no==6 || round_no==7 || round_no==8){
            unsigned kind=round_no==8?scd_boss8_kind(p):round_no==7?scd_boss7_kind(p):scd_boss6_kind(p);
            if(kind && n<capacity)views[n++]=(scd_boss_view){p->xposi.w.h,p->yposi.w.h,p->patno,p->actflg&3,priority,(uint16_t)kind};
            continue;
        }
        if(round_no==4){
            /* Zone art kinds (tools/extract_mmd.py TT_BOSS_KIND): 240 egg4air, 241 egg4airhead,
               242 egg4, 243 egg4meca, 244 egg4tama, 245 egg4awa, 246 wall4. */
            static const uint8_t kinds4[80]={[71]=246,[74]=240,[75]=241,[76]=242,[77]=243,[78]=244,[79]=245};
            if(p->actno<80 && kinds4[p->actno] && n<capacity)
                views[n++]=(scd_boss_view){p->xposi.w.h,p->yposi.w.h,p->patno,p->actflg&3,priority,kinds4[p->actno]};
            continue;
        }
        if(round_no==3){
            /* Zone art kinds (tools/extract_mmd.py CC_BOSS_KIND, split_cc_boss): 240
               egg3dai_s, 241-243 egg3dai_l parts, 244 egg3haguruma, 245 egg3, 246 cannon,
               247 punchbom, 248 gate; punchbom's bakupat explosion uses the common frames. */
            static const uint8_t kinds[64]={[48]=240,[50]=244,[51]=245,[61]=246,[62]=247,[63]=248};
            /* A statement, so the else-if chain below binds to its own ifs (a bare
               if here took the kinds[] branch as its else: egg3, egg3dai_s, the
               gear, cannon, punchbom and gate never drew). */
            #define VIEW(dx,f,k) do{if(n<capacity)views[n++]=(scd_boss_view){(int16_t)(p->xposi.w.h+(dx)),p->yposi.w.h,(uint8_t)(f),p->actflg&3,priority,(uint16_t)(k)};}while(0)
            unsigned pose=p->patno;
            if(p->actno==49){
                /* Line 1 layer, platform, then the top piece: the original piece order. */
                if(pose<6)VIEW(0,pose/2,242);
                VIEW(0,pose&1,241);
                if(pose<2)VIEW(0,0,243);
            }else if(p->actno==62 && p->sproffset==1664)VIEW(0,pose,SCD_BOSS_KIND_EXPLOSION);
            else if(p->actno<64 && kinds[p->actno])VIEW(0,pose,kinds[p->actno]);
            #undef VIEW
            continue;
        }
        switch(p->actno){
        case 42:frame=p->patno;break;
        case 43:frame=11;break;
        case 49:frame=(ARM3_SECOND(p)?21:18)+p->patno;break;
        case 50:frame=24;break;
        default:frame=13+p->actno-44;break;
        }
        for(unsigned part=0;part<(p->actno==43?2u:1u) && n<capacity;part++)
            views[n++]=(scd_boss_view){p->xposi.w.h,p->yposi.w.h,(uint8_t)(frame+part),p->actflg&3,priority,0};
    }
    return n;
}
int scd_boss_palette(void){return palette_state;}
void scd_boss_palette_set(int state){palette_state=state;}
int scd_boss_music(void){int request=music_request;music_request=SCD_BOSS_MUSIC_NONE;return request;}
int scd_boss_fight_art(void){int request=fight_art_request;fight_art_request=0;return request;}
void scd_boss8_plc(int plc){if(plc==4 || plc==5)fight_art_request=plc;}
/* The boss's main actor: egg1 (42), Collision Chaos's egg3dai_l (49), or
   Tidal Tempest's egg4air (74) and then egg4 (76). */
static const sprite_status *robotnik(void){
    unsigned id=round_no==3?49:round_no==4?74:round_no==5?52:round_no==6?52:round_no==7?44:round_no==8?63:42;
    for(unsigned pass=0;pass<(round_no==4?2u:1u);pass++,id=76)
        for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++)if(actwk[i].actno==id)return &actwk[i];
    return NULL;
}
uint32_t scd_boss_position(void){const sprite_status *p=robotnik();return p?((uint32_t)(uint16_t)p->xposi.w.h<<16)|(uint16_t)p->yposi.w.h:0;}
/* R1: actfree[1] counts hits. R3: actfree[17] counts egg3dai_l hit phases. R4:
   colicnt, the hits left (COLI4.C pcolnomal counts it down; egg4air 5, egg4 2),
   with bit 17 set once egg4 (76) is the main actor. */
uint32_t scd_boss_status(void){
    const sprite_status *p=robotnik();if(!p)return 0;
    if(round_no==5 || round_no==6 || round_no==7 || round_no==8)return 65536u|((uint32_t)p->r_no0<<8)|p->patno;
    if(round_no==4)return 65536u|(p->actno==76?131072u:0)|((uint32_t)p->r_no0<<8)|p->colicnt;
    return 65536u|((uint32_t)p->r_no0<<8)|p->actfree[round_no==3?17:1];
}
int scd_boss_active(void){for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++)if(boss_actor(actwk[i].actno))return 1;return 0;}
unsigned scd_boss_round(void){return round_no;}
/* A cleared actor hashes as 51 zero bytes, including all 22 scratch bytes.
   Test the complete object, so a dead actor with retained fields still uses
   the ordinary field hash. Padding or an ignored field can only reject this
   shortcut; they cannot change its result. */
typedef uint32_t __attribute__((may_alias)) boss_hash_word;
_Static_assert(sizeof(sprite_status)%sizeof(boss_hash_word)==0 &&
               _Alignof(sprite_status)>=_Alignof(boss_hash_word),"boss hash word alignment");
static int boss_hash_cleared(const sprite_status *p){
    const boss_hash_word *words=(const boss_hash_word *)p;
    for(unsigned j=0;j<sizeof(*p)/sizeof(*words);j++)if(words[j])return 0;
    return 1;
}
/* FNV-1a over every boss actor field except the pattern pointer. */
uint32_t scd_boss_hash(void){
    uint32_t h=2166136261u;
    #define MIX(v,bytes) for(unsigned b=0;b<(bytes);b++)h=(h^(((uint32_t)(v)>>(8*b))&255))*16777619u
    for(unsigned i=SCD_BOSS_FIRST_SLOT;i<128;i++){
        const sprite_status *p=&actwk[i];
        /* 16777619^51 modulo 2^32: the exact 51 zero-byte FNV steps. */
        if(boss_hash_cleared(p)){h*=3910892939u;continue;}
        MIX(p->actno,1);MIX(p->actflg,1);MIX(p->sproffset,2);MIX(p->xposi.l,4);MIX(p->yposi.l,4);
        /* Robotnik uses yspeed as a native word; the parts use PC bytes 16-19 as one
           little-endian long. Hash each as its code reads it so both CPUs agree. */
        if(p->actno==42 || round_no==3){MIX(p->xspeed.w,2);MIX(p->yspeed.w,2);}
        else {const uint8_t *s=(const uint8_t *)&p->xspeed;for(unsigned b=0;b<4;b++)MIX(s[b],1);}
        MIX(p->sprhsize,1);MIX(p->sprvsize,1);MIX(p->sprpri,1);
        MIX(p->patno,1);MIX(p->mstno.w,2);MIX(p->patcnt,1);MIX(p->pattim,1);MIX(p->colino,1);MIX(p->colicnt,1);
        MIX(p->cddat,1);MIX(p->r_no0,1);MIX(p->r_no1,1);
        for(unsigned b=0;b<22;b++)MIX(p->actfree[b],1);
    }
    MIX(bossflag,1);MIX(bossstart,1);MIX(scralim_left,2);MIX(scralim_right,2);MIX(scralim_down,2);MIX(scra_vline,2);MIX(palette_state,1);
    #undef MIX
    return h;
}
