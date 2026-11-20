/* Quartz Quadrant platform dair5: retail R5 id 48 (ACT51A.C:81 and ACT53.C:65
 * put &dair5 at act_tbl[47]; ACTION.C:53 dispatches act_tbl[actno-1]).
 * Ported from build/audit/source/src/R5/DAI_RD5.C. Every constant below cites
 * that file as DAI_RD5.C:<line>.
 *
 * State lives in the actor exactly where the retail routine keeps it, so the
 * code reads line for line against the source. The PC build is little
 * endian, so actfree[3] is the high (integer) byte of word 24:
 *   word 24  oscillator position, 8.8     (DAI_RD5.C:485,496)
 *   word 25  oscillator velocity, 8.8     (DAI_RD5.C:482-484)
 *   word 26  oscillator acceleration      (DAI_RD5.C:308,327,346)
 *   word 27  resting Y for the sink       (DAI_RD5.C:202,533)
 *   word 29  placement X                  (DAI_RD5.C:201)
 *   actfree[17] wait timer, [18] swing direction, [19] fall/rise routine,
 *   actfree[20] sink angle, [21] bit 0 belt, bit 7 sink enabled.
 * actfree[14..16] are unused by DAI_RD5.C; the port keeps the actor indices
 * of the springs banesetsub creates there so the platform can carry them.
 *
 * This file is included near the top of src/objects.c, before the pool and
 * the solidity helpers, so it uses only actwk[] and forward declarations. */
static int top_solid(unsigned i);
static void release_rider(unsigned actor);
static void remove_slot(unsigned i);
static void remove_fallen(unsigned i);
void speedset2(sprite_status *pActwk);

/* DAI_RD5.C:140-166 ini_tbl: {patno, sprhsize} per subtype 0..24. */
static const uint8_t dair5_ini_tbl[25][2]={
    {0,16},{1,16},{0,16},{0,16},{1,16},{0,16},{0,16},{2,32},{2,32},{3,32},
    {2,32},{3,32},{2,32},{3,32},{2,32},{2,32},{2,32},{4,48},{5,48},{4,48},
    {4,48},{5,48},{4,48},{4,48},{4,48}};
/* DAI_RD5.C:171-177 belt_flag, first 25 of its 50 bytes (subtype & 31 <= 24).
   Bit 0 makes belttask push a rider; the 64/192 bytes past index 25 are never
   reached by a valid subtype. */
static const uint8_t dair5_belt_flag[25]={
    0,1,0,0,1,0,0,0,0,1, 0,1,0,1,0,0,0,0,1,0, 0,1,0,0,0};
/* DAI_RD5.C:182-187 bane_flag: how many springs banesetsub attaches. */
static const uint8_t dair5_bane_flag[25]={
    0,0,1,0,0,0,0,0,0,0,0,0, 0,0,2,0,0,0,0,0, 0,0,3,0,0};
/* DAI_RD5.C:256-282 dair5_move tbl: which typeNN routine runs per subtype. */
static const uint8_t dair5_routine[25]={
    1,2,2,3,3,6,5,1,4,4,3,3,2,2,2,6,5,1,1,3,2,2,2,6,5};
/* banesetsub offsets per bane_flag value (DAI_RD5.C:228-241). */
static const int8_t dair5_bane_dx[4][3]={{0},{0},{-16,16},{-32,0,32}};

static int16_t dair5_word(const sprite_status *o,unsigned word){return (int16_t)scd_word_get(o,word);}

/* spawn_from setup: dair5_init's sizes and saved words (DAI_RD5.C:190-216).
   The springs and the first dair5_move wait for the first step, as the retail
   init runs them on the actor's first execution (DAI_RD5.C:220-249).
   Returns the display pattern (ini_tbl patno). */
static unsigned dair5_spawn(sprite_status *o){
    unsigned sub=o->userflag.b.h&31;if(sub>24)sub=0;
    o->actflg|=4;                                   /* DAI_RD5.C:190 */
    o->sprpri=3;                                    /* DAI_RD5.C:191 */
    scd_word_set(o,29,(uint16_t)o->xposi.w.h);      /* DAI_RD5.C:201 */
    scd_word_set(o,27,(uint16_t)o->yposi.w.h);      /* DAI_RD5.C:202 */
    o->sprvsize=16;                                 /* DAI_RD5.C:203 */
    o->patno=dair5_ini_tbl[sub][0];                 /* DAI_RD5.C:212 */
    o->sprhsize=dair5_ini_tbl[sub][1];              /* DAI_RD5.C:213 */
    o->actfree[21]=dair5_belt_flag[sub];            /* DAI_RD5.C:216 */
    return o->patno;
}

/* dodai_sub, DAI_RD5.C:476-502: a velocity that accelerates by word 26 toward
   the turning byte d4 and back, a spring oscillation between 0 and ~2*d4. */
static void dair5_dodai_sub(sprite_status *o,unsigned d4){
    int16_t d2=dair5_word(o,26),d0;
    if(o->actfree[18]==0){
        d0=(int16_t)(dair5_word(o,25)+d2);scd_word_set(o,25,(uint16_t)d0);
        scd_word_set(o,24,(uint16_t)(dair5_word(o,24)+d0));
        if(d4<=o->actfree[3])o->actfree[18]=255;
    }else{
        d0=(int16_t)(dair5_word(o,25)-d2);scd_word_set(o,25,(uint16_t)d0);
        scd_word_set(o,24,(uint16_t)(dair5_word(o,24)+d0));
        if(d4>o->actfree[3])o->actfree[18]=0;
    }
}
/* type02/type04 (DAI_RD5.C:304-318, 342-356): horizontal swing, bit 7 reverses. */
static void dair5_swing_x(sprite_status *o,unsigned d4){
    o->actfree[21]|=128;scd_word_set(o,26,4);dair5_dodai_sub(o,d4);
    int16_t d0=dair5_word(o,25);if(o->userflag.b.h&128)d0=(int16_t)-d0;
    o->xspeed.w=d0;o->xposi.l+=(int32_t)d0*256;
}
/* type03 (DAI_RD5.C:323-337): vertical swing of 48, no sink, no yspeed. */
static void dair5_swing_y(sprite_status *o){
    scd_word_set(o,26,4);dair5_dodai_sub(o,48);
    int16_t d0=dair5_word(o,25);if(o->userflag.b.h&128)d0=(int16_t)-d0;
    o->yposi.l+=(int32_t)d0*256;
}
/* type05 (DAI_RD5.C:361-407): wait 30 updates after a rider lands, then fall.
   Returns 1 once the actor has been removed. The retail R5 program falls
   through from the timer set into the countdown (R52A__.MMD file offset
   $CA6E-$CA80: move.b #30,$3B(a0); move.b #1,$3D(a0); tst.b $3B(a0);
   subq.b #1,$3B(a0)), so the first tick lands on the update the rider is
   first seen; DAI_RD5.C's "else" would start one update late. */
static int dair5_fall(unsigned i){
    sprite_status *o=&actwk[i+1];
    if(o->actfree[19]==0){
        o->actfree[21]|=128;
        if(!(o->cddat&8))return 0;
        o->actfree[17]=30;o->actfree[19]=1;
    }
    if(o->actfree[17]){
        if(--o->actfree[17])return 0;
        o->actfree[21]&=127;
    }
    o->sprvsize=16;
    if(o->yspeed.w>=512){o->sprvsize=18;if(o->yspeed.w>=768)o->sprvsize=20;}
    if(o->yspeed.w<1024)o->yspeed.w+=32;
    o->yposi.l+=(int32_t)o->yspeed.w*256;
    /* DAI_RD5.C:399-404 compare with scra_v_posit + 224. The port keeps no
       vertical scroll in the object scheduler, so this uses the gameplay
       camera src/main.c:1227 and :1241 draw with: player Y - 140, clamped
       to 0..scralim_down. */
    int camera=actwk[0].yposi.w.h-140;if(camera>scralim_down)camera=scralim_down;if(camera<0)camera=0;
    if(camera+224<o->yposi.w.h){release_rider(i+1);remove_fallen(i);return 1;}
    return 0;
}
/* type06 (DAI_RD5.C:412-471): wait 30 updates after a rider lands, then rise
   until the ceiling 48 pixels above is reached, then stay. */
static void dair5_rise(sprite_status *o){
    if(o->actfree[19]==0){
        o->actfree[21]|=128;
        if(!(o->cddat&8))return;
        o->actfree[19]+=2;o->actfree[17]=30;
    }
    if(o->actfree[19]!=2)return;
    if(o->actfree[17]){
        if(--o->actfree[17])return;
        o->actfree[21]&=127;o->sprvsize=14;
    }
    int16_t d0=(int16_t)(o->yspeed.w-8);if(d0<-768)d0=-768;
    o->yspeed.w=d0;
    speedset2(o);
    int32_t stk=o->yposi.l;o->yposi.w.h-=48;
    short d1=emycol_u(o);
    o->yposi.l=stk;
    if(d1<0){
        o->sprvsize=16;o->yspeed.w=0;scd_word_set(o,27,(uint16_t)o->yposi.w.h);
        o->actfree[21]|=128;o->actfree[19]+=2;
    }
}
/* dai5sub, DAI_RD5.C:507-536: sink up to 4 pixels while ridden. */
static void dair5_sink(sprite_status *o){
    if(!(o->actfree[21]&128))return;
    if(!(o->cddat&8)){if(o->actfree[20]==0)return;o->actfree[20]-=8;}
    else{if(o->actfree[20]==64)return;o->actfree[20]+=8;}
    short d0,d1;sinset(o->actfree[20],&d0,&d1);
    d0=(short)(((int32_t)d0*1024)>>16);
    o->yposi.w.h=(short)(d0+dair5_word(o,27));
}
/* belttask, DAI_RD5.C:560-594: a belt platform pushes its rider 0.5/1/2
   pixels per update in the Past/Present/Future, reversed by colrevflag. */
static void dair5_belt(unsigned i){
    sprite_status *o=&actwk[i+1],*p=&actwk[0];
    if(!(o->actfree[21]&1) || !(o->cddat&8) || p->actno==0 || !(p->cddat&8) || p->actfree[19]!=i+1)return;
    unsigned char bd1=time_flag;int32_t ld0=32768;
    if(bd1){ld0=65536;--bd1;if(bd1)ld0=0x20000;}
    if(colrevflag)ld0=-ld0;
    p->xposi.l+=ld0;
}
/* A spring made by banesetsub (DAI_RD5.C:541-555) carries the retail link:
   word 28 = parent actor, actfree[14]/[15] = X/Y offset, and SPRING.C:406-412
   re-seats it on the parent every update after its own move (src/objects.c
   spring_step); the platform places them only when it creates them. */
static int dair5_child_of(unsigned child,unsigned actor){
    const sprite_status *c=&actwk[child];
    return c->actno==SCD_OBJ_SPRING && scd_word_get(c,28)==actor;
}
static void dair5_carry_springs(unsigned i){
    sprite_status *o=&actwk[i+1];
    for(unsigned n=14;n<17;n++){
        unsigned child=o->actfree[n];if(!child)continue;
        if(child>SCD_OBJECT_CAPACITY || !dair5_child_of(child,i+1)){o->actfree[n]=0;continue;}
        sprite_status *c=&actwk[child];
        c->xposi.w.h=(short)(o->xposi.w.h+(signed char)c->actfree[14]);
        c->yposi.w.h=(short)(o->yposi.w.h+(signed char)c->actfree[15]);
    }
}
/* A linked spring whose platform is gone (streamed out) has nothing to ride. */
static void dair5_drop_orphans(void){
    for(unsigned c=1;c<=SCD_OBJECT_CAPACITY;c++){
        sprite_status *a=&actwk[c];
        if(a->actno!=SCD_OBJ_SPRING)continue;
        unsigned parent=scd_word_get(a,28);if(!parent)continue;
        const sprite_status *q=parent<=SCD_OBJECT_CAPACITY?&actwk[parent]:NULL;
        if(q && q->actno==SCD_OBJ_DAIR5 && (q->actfree[14]==c || q->actfree[15]==c || q->actfree[16]==c))continue;
        remove_slot(c-1);
    }
}
static void dair5_init_springs(unsigned i){
    sprite_status *o=&actwk[i+1];unsigned bane=dair5_bane_flag[o->userflag.b.h&31];
    for(unsigned n=0;n<bane;n++){
        int child=scd_objects_spawn(SCD_OBJ_SPRING,o->xposi.w.h,o->yposi.w.h,2,0); /* actno 10, userflag 2: DAI_RD5.C:547,553 */
        if(child<0)break;
        sprite_status *c=&actwk[child+1];
        c->actfree[14]=(uint8_t)dair5_bane_dx[bane][n];   /* DAI_RD5.C:550 */
        c->actfree[15]=(uint8_t)-24;                      /* DAI_RD5.C:551 */
        scd_word_set(c,28,i+1);                           /* DAI_RD5.C:552 */
        o->actfree[14+n]=(uint8_t)(child+1);
    }
    dair5_carry_springs(i);
}
/* dair5 / dair5_move (DAI_RD5.C:120-130, 255-291): the subtype routine, then
   the sink, the belt and a top-only ridechk. ridechk sets r_no1 = 1 so
   RIDECHK.C hitchk/hit_x/hit_yu ignore rising, side and bottom contact:
   top_solid is that test. */
static void dair5_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    unsigned sub=o->userflag.b.h&31;
    if(sub>24){remove_slot(i);return;}   /* tables end at 24; no R5 layout uses more */
    dair5_drop_orphans();
    if(o->r_no0==0){o->r_no0=2;dair5_init_springs(i);}   /* DAI_RD5.C:189,220-243 */
    switch(dair5_routine[sub]){
    case 1:o->actfree[21]|=128;break;                    /* type01, DAI_RD5.C:297-299 */
    case 2:dair5_swing_x(o,48);break;                    /* type02 */
    case 3:dair5_swing_y(o);break;                       /* type03 */
    case 4:dair5_swing_x(o,32);break;                    /* type04 */
    case 5:if(dair5_fall(i))return;break;                /* type05 */
    default:dair5_rise(o);break;                         /* type06 */
    }
    dair5_sink(o);
    dair5_belt(i);
    top_solid(i);
}
