/* Metallic Madness (R8) shared actor helpers: COLI8.C pcol, SUICIDE.C
   enemy_suicide and the scratch accessors the R8 ports use. Included by
   objects_mm.inc, after the TT helpers (objects_tt_ride.inc: tp_* RIDECHK
   port, claim, frameout, patchg).

   Scratch storage keeps the PC reconstruction's little-endian byte layout, as
   the tp_* helpers do, so the compiled originals in tools/test-mm-actors.sh
   compare byte for byte. The accessors take the ORIGINAL indices:
     ((short*)o)[n] -> mm_w(o,n) / mm_ws(o,n,v)   (actfree bytes 2n-46)
     ((int*)o)[n]   -> mm_l(o,n) / mm_ls(o,n,v)   (actfree bytes 4n-46)
     ((char*)o)[n]  -> o->actfree[n-46]
   The chain score is the global emyscorecnt (COLI8 pcolnomal); only the
   player's landing (jumpcolsub) and the objects reset clear it. */
static inline short mm_w(const sprite_status *o,unsigned n){return tp_w(o,2*n-46);}
static inline short mm_ws(sprite_status *o,unsigned n,int v){return tp_wset(o,2*n-46,v);}
static inline int mm_l(const sprite_status *o,unsigned n){return tp_l(o,4*n-46);}
static inline int mm_ls(sprite_status *o,unsigned n,int v){return tp_lset(o,4*n-46,v);}
static inline unsigned mm_index(const sprite_status *o){return (unsigned)(o-actwk);}
/* actwk[((short*)o)[n]]: a stored actor index (0 is the player). */
static inline sprite_status *mm_link(const sprite_status *o,unsigned n){return &actwk[(uint16_t)mm_w(o,n)&127];}
extern short emycol_l(sprite_status*,unsigned char);
/* actionsub on another actor (TOBIRA's slave leaf, LEGMECA's links and
   second leg): that actor's own update runs later and must not clear the
   draw (mm_zone_step keeps a marked slot's sink for that update). */
static uint8_t mm_drawn_by_other[SCD_OBJECT_CAPACITY];
static void mm_draw_other(sprite_status *o){tp_draw(o);unsigned i=tp_slot(o);if(i<SCD_OBJECT_CAPACITY)mm_drawn_by_other[i]=1;}
extern short emycol_r(sprite_status*,unsigned char);

/* SUICIDE.C enemy_suicide. The original clears the actor before its
   visibility test, so no sound plays. */
static int mm_enemy_suicide(sprite_status *o){
    if(!good_future || (current_era==0 && !o->userflag.b.h))return 0;
    unsigned i=tp_slot(o);int x=o->xposi.w.h,y=o->yposi.w.h;
    if(pool[i].origin!=65535)deferred_reload[pool[i].origin]=1;
    remove_slot(i);
    pool[i]=(slot){.origin=65535,.type=SCD_OBJ_EXPLOSION};
    o->actno=SCD_OBJ_EXPLOSION;o->xposi.w.h=x;o->yposi.w.h=y;
    return 1;
}

/* COLI8.C colitbl (rows 34.. differ from COLI7). */
static const uint8_t mm_colitbl[64][2]={
    {20,20},{18,12},{12,16},{4,16},{12,18},{16,16},{6,6},{24,12},{12,16},{16,12},{8,8},{20,16},{20,8},{14,14},{24,24},{40,16},
    {16,24},{8,16},{32,112},{64,32},{128,32},{32,32},{8,8},{4,4},{32,8},{12,12},{8,4},{24,4},{40,4},{4,8},{4,24},{4,40},
    {4,32},{40,36},{12,24},{28,28},{56,6},{16,16},{6,6},{32,4},{28,28},{16,14},{12,16},{16,9},{16,16},{12,14},{8,8},{24,11},
    {16,60},{16,36},{36,16},{24,24},{22,22},{16,16},{24,20},{24,24},{15,32},{32,15},{8,32},{16,32},{28,28},{32,16},{32,8},{0,0}};
static int mm_contact_type(unsigned t);
/* COLI8.C pcolplay/pcole: nothing while the player is carried
   (actfree[2] bit 0), invincible or super; scd_objects_hurt handles the
   blink timer (word 26), shield and rings. */
static void mm_pcolplay(const sprite_status *o){
    if((actwk[0].actfree[2]&1) || plpower_a || plpower_m)return;
    scd_objects_hurt(o->xposi.w.h);
}
/* COLI8.C pcolnomal. */
static void mm_pcolnomal(unsigned i){
    sprite_status *o=&actwk[i+1],*p=actwk;
    if(!plpower_a && !plpower_m && !travel_protection && p->mstno.b.h!=2){mm_pcolplay(o);return;}
    if(o->colicnt){
        p->xspeed.w=(int16_t)((int16_t)-p->xspeed.w/2);p->yspeed.w=(int16_t)((int16_t)-p->yspeed.w/2);
        o->colino=0;if(!--o->colicnt)o->cddat|=128;return;
    }
    o->cddat|=128;
    static const unsigned short escoretbl[4]={10,20,50,100};
    short c=emyscorecnt;emyscorecnt+=2;
    if((unsigned short)c>=6)c=6;
    mm_ws(o,33,c);unsigned score=escoretbl[c/2];
    if((unsigned short)emyscorecnt>=32){score=1000;mm_ws(o,33,10);}
    scd_player_points(score*10u);
    stats.defeated++;soundset(150);
    if(pool[i].origin!=65535)consumed[pool[i].origin]=1;
    /* Convert in place: pcolnomal keeps the actor's slot. */
    pool[i].type=SCD_OBJ_EXPLOSION;pool[i].subtype=1;pool[i].age=0;
    pool[i].state=pool[i].frame=pool[i].cooldown=0;
    o->actno=SCD_OBJ_EXPLOSION;o->r_no0=0;o->userflag.b.h=1;
    short before_vx=p->xspeed.w,before_vy=p->yspeed.w;
    if(p->yspeed.w>=0){if(o->yposi.w.h>p->yposi.w.h)p->yspeed.w=-p->yspeed.w;else p->yspeed.w-=256;}
    else p->yspeed.w+=256;
    scd_plus_enemy_defeat(i+1,before_vx,before_vy);
}
/* COLI8.C pcol: one box from the player's position over every visible actor
   with a collision number, in actor order. The scan stops at the first
   contact of any kind, except a harmful one (colino bit 7) while plpower_m
   is set, which ColliHitChk skips. It does nothing while the player is
   carried (actfree[2] bit 0). */
static void ring_collect(unsigned i);
static void mm_enemy_scan(void){
    sprite_status *p=actwk;
    if(p->r_no0>=4 || (p->actfree[2]&1))return;
    int16_t x=p->xposi.w.h-8,r=p->sprvsize-3,y=p->yposi.w.h-r;
    if(p->patno==57){y+=12;r=10;}
    int16_t h=r*2;
    for(unsigned i=0;i<SCD_OBJECT_CAPACITY;i++){
        sprite_status *o=&actwk[i+1];
        /* RING.C:238-239 and :416-417 (lost rings; stageno 6 keeps userflag.b.l):
           a placed or lost ring is colino 71 once drawn, so it takes part in this scan
           in slot order like any other actor (retail MM1A row 3125 takes ring
           slot 78 and leaves SCARAB slot 82 for a later update). */
        int ring=(pool[i].type==SCD_OBJ_RING || pool[i].type==SCD_OBJ_LOST_RING) && !pool[i].state;
        /* ITEM.C:254 t_item_init gives a time post colino 223 ($DF) unless it
           loads spent (r_no0 6); nothing clears it, so a used post still stops
           this scan (retail MM2B row 7585: post slot 62 before DANGO8 slot 63). */
        int post=pool[i].type==SCD_OBJ_TIMEPOST && pool[i].subtype>=8 && !pool[i].anim;
        unsigned colino=ring?71:post?223:o->colino;
        /* R3/BOBIN.C's bumper (R8 act_tbl 29, colino $D7) too: the generated
           COLI8 pcol sees only actwk[32..127], and native actors start at 1. */
        if(!(o->actflg&128) || !colino || (!ring && !post && pool[i].type!=SCD_OBJ_BOBIN && !mm_contact_type(pool[i].type)))continue;
        unsigned n=(colino&63)-1;
        int16_t w=mm_colitbl[n][0],d=o->xposi.w.h-w;
        if(d<x){if((int16_t)(d-x)+2*w<0)continue;}
        else if((int16_t)(d-x)>16)continue;
        int16_t v=mm_colitbl[n][1],e=o->yposi.w.h-v;
        if(e<y){if((int16_t)(e-y)+2*v<0)continue;}
        else if((int16_t)(e-y)>h)continue;
        unsigned kind=colino&192;
        if(!kind){mm_pcolnomal(i);return;}
        if(kind==128){if(plpower_m)continue;mm_pcolplay(o);return;}
        if(kind==64){
            /* pcolitem: refused when the layer (prio_flag) and the actor's
               userflag.b.l disagree; the scan still stops. */
            if(!prio_flag!=!o->userflag.b.l)return;
            /* RING.C:293 ringget runs on the routine pcolitem advances to. */
            if(ring){if((uint16_t)scd_word_get(p,26)<90)ring_collect(i);return;}
            if((o->colino&63)!=6){if((uint16_t)scd_word_get(p,26)<90)o->r_no0+=2;}
            else if(p->yspeed.w<0){
                if(p->yposi.w.h-16>=o->yposi.w.h){p->yspeed.w=-p->yspeed.w;o->yspeed.w=-384;if(!o->r_no1)o->r_no1+=4;}
            }else if(p->mstno.b.h==2){p->yspeed.w=-p->yspeed.w;o->r_no0+=2;}
            return;
        }
        /* pcolspecial. Boss numbers (60-63 by bossstart) belong to the boss
           scan; a non-boss actor never carries them. */
        unsigned c=colino&63; /* a time post's 223 lives only in the scan */
        switch(c){
        case 45:if(!(p->cddat&4)){mm_pcolnomal(i);break;}
            /* fall through */
        case 23:case 31:case 35:o->colicnt++;break;
        case 6:
            if(p->yspeed.w<0){
                if(p->yposi.w.h-16>=o->yposi.w.h){p->yspeed.w=-p->yspeed.w;o->yspeed.w=-384;if(!o->r_no1)o->r_no1+=4;}
            }else if(p->mstno.b.h==2){p->yspeed.w=-p->yspeed.w;o->r_no0+=2;}
            break;
        case 34:if(p->mstno.b.h==2)o->colicnt++;break;
        case 48:{
            unsigned char side=(int)p->xposi.w.h-(int)o->xposi.w.h<0?255:0;
            if(!((unsigned char)o->userflag.b.l^side))mm_pcolnomal(i);else o->colicnt++;
            break;
        }
        }
        return;
    }
}
