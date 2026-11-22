/* Quartz Quadrant (R5) shared actor helpers: COLI5.C pcol, SUICIDE.C
   enemy_suicide / friend_suicide and the scratch accessors the R5 ports use.
   Included by objects.c after objects_tt_ride.inc (tp_* RIDECHK port, claim,
   frameout and patchg helpers) and objects_tt_common.inc (tt_pcolnomal).

   Scratch storage keeps the PC reconstruction's little-endian byte layout, as
   the tp_* helpers do, so the compiled originals in tools/test-qq-actors.sh
   compare byte for byte. The accessors take the ORIGINAL indices so each
   port line reads against its source line:
     ((short*)o)[n] -> qq_w(o,n) / qq_ws(o,n,v)   (actfree bytes 2n-46)
     ((int*)o)[n]   -> qq_l(o,n) / qq_ls(o,n,v)   (actfree bytes 4n-46)
     *(int*)&o->actfree[b] -> tp_l(o,b) / tp_lset(o,b,v)
     ((char*)o)[n]  -> o->actfree[n-46] */
static inline short qq_w(const sprite_status *o,unsigned n){return tp_w(o,2*n-46);}
static inline short qq_ws(sprite_status *o,unsigned n,int v){return tp_wset(o,2*n-46,v);}
static inline int qq_l(const sprite_status *o,unsigned n){return tp_l(o,4*n-46);}
static inline int qq_ls(sprite_status *o,unsigned n,int v){return tp_lset(o,4*n-46,v);}
/* actwk[((short*)o)[n]]: a stored actor index (0 is the player). */
static inline sprite_status *qq_link(const sprite_status *o,unsigned n){return &actwk[(uint16_t)qq_w(o,n)&127];}
static inline unsigned qq_index(const sprite_status *o){return (unsigned)(o-actwk);}
extern short emycol_d3(sprite_status*,short,short);
/* src/background_r5.c (COL5A-D belt palettes) follows the belt direction.
   Host fixtures link the objects without the background: a no-op then. */
__attribute__((weak)) void scd_r5_set_colrev(int on){(void)on;}
extern short ride_on_chk(sprite_status*,sprite_status*);

/* SUICIDE.C enemy_suicide. Once the generator is broken the enemy becomes an
   explosion in place (the Present keeps undamaged subtype-0 enemies). The
   original clears the actor before its visibility test, so no sound plays. */
static int qq_enemy_suicide(sprite_status *o){
    if(!good_future || (current_era==0 && !o->userflag.b.h))return 0;
    unsigned i=tp_slot(o);int x=o->xposi.w.h,y=o->yposi.w.h;
    unsigned origin=pool[i].origin;
    if(pool[i].origin!=65535)deferred_reload[pool[i].origin]=1;
    remove_slot(i);
    /* DeleteObject clears the actor but leaves its saved placement loaded.
       The explosion and flower keep that ownership until the act ends. */
    if(objects_zone==4 && objects_act==0 && origin<SCD_PLACEMENT_CAPACITY)
        deferred_reload[origin]=0;
    pool[i]=(slot){.origin=objects_zone==4 && objects_act==0?origin:65535,.type=SCD_OBJ_EXPLOSION,.phase=CC_BADNIK_BOOM};
    o->actno=SCD_OBJ_EXPLOSION;o->xposi.w.h=x;o->yposi.w.h=y;
    return 1;
}
/* SUICIDE.C friend_suicide: animals leave the Present/Past when the projector
   still stands and the Bad Future always. */
static int qq_friend_suicide(sprite_status *o){
    if((int8_t)o->userflag.b.h<0)return 0;
    if(current_era<2){if(projector_destroyed)return 0;tp_frameout_s(o);return 1;}
    if(good_future)return 0;
    tp_frameout(o);return 1;
}

/* COLI5.C colitbl. Rows 40..62 differ from COLI4. */
static const uint8_t qq_colitbl[64][2]={
    {20,20},{18,12},{12,16},{4,16},{12,18},{16,16},{6,6},{24,12},{12,16},{16,12},{8,8},{20,16},{20,8},{14,14},{24,24},{40,16},
    {16,24},{8,16},{32,112},{64,32},{128,32},{32,32},{8,8},{4,4},{32,8},{12,12},{8,4},{24,4},{40,4},{4,8},{4,24},{4,40},
    {4,32},{24,24},{12,24},{72,8},{8,12},{16,8},{32,16},{32,16},{0,0},{0,0},{0,0},{0,0},{0,0},{23,48},{16,16},{12,5},
    {20,16},{3,3},{8,8},{8,12},{24,24},{24,16},{12,8},{16,16},{4,16},{40,36},{18,17},{14,24},{8,8},{32,56},{30,32},{0,0}};
/* Actors whose COLI5 collision numbers the native pcol scan owns. */
static int qq_contact_type(unsigned t){
    return t==SCD_OBJ_R5_DENDEN || t==SCD_OBJ_R5_SASORI || t==SCD_OBJ_R5_KEMUSI || t==SCD_OBJ_R5_KUMO ||
           t==SCD_OBJ_R5_IWA5 || t==SCD_OBJ_R5_HARI5F || t==SCD_OBJ_R5_HARIR5 || t==SCD_OBJ_R5_HASIRA5 ||
           t==SCD_OBJ_R5_MOVIE5 || t==SCD_OBJ_R5_ET5 || t==SCD_OBJ_R5_KOWASI5;
}
/* COLI5.C pcol: one box from the player's position over every visible actor
   with a collision number, in actor order. Unlike COLI4 the scan stops at
   the first contact of any kind (ColliHitChk returns non-zero). */
static void qq_enemy_scan(void){
    sprite_status *p=actwk;
    qq_ring_touched=0;
    if(p->r_no0>=4)return;
    int16_t x=p->xposi.w.h-8,r=p->sprvsize-3,y=p->yposi.w.h-r;
    if(p->patno==57){y+=12;r=10;}
    int16_t h=r*2;
    for(unsigned i=0;i<SCD_OBJECT_CAPACITY;i++){
        sprite_status *o=&actwk[i+1];
        /* RING.C rings ($47, 6x6) sit in this scan in slot order like COLI4's:
           the first contact ends it, so one ring at most per update (retail
           QQ2A 7089: one ring of the column, not two). */
        const int ring=(pool[i].type==SCD_OBJ_RING || pool[i].type==SCD_OBJ_LOST_RING) && !pool[i].state;
        if(!(o->actflg&128) || (!ring && (!o->colino || !qq_contact_type(pool[i].type))))continue;
        unsigned n=ring?6:(o->colino&63)-1;
        int16_t w=qq_colitbl[n][0],d=o->xposi.w.h-w;
        if(d<x){if((int16_t)(d-x)+2*w<0)continue;}
        else if((int16_t)(d-x)>16)continue;
        int16_t v=qq_colitbl[n][1],e=o->yposi.w.h-v;
        if(e<y){if((int16_t)(e-y)+2*v<0)continue;}
        else if((int16_t)(e-y)>h)continue;
        if(ring){if(!(p->actfree[2]&128) && (uint16_t)scd_word_get(p,26)<90)qq_ring_touched=i+1;return;}
        unsigned kind=o->colino&192;
        if(!kind)tt_pcolnomal(i);
        else if(kind==128)scd_objects_hurt(o->xposi.w.h);
        else if(kind==64){
            /* pcolitem, as COLI4. */
            if((o->colino&63)!=6){if((uint16_t)scd_word_get(p,26)<90)o->r_no0+=2;}
            else if(p->yspeed.w<0){
                if(p->yposi.w.h-16>=o->yposi.w.h){p->yspeed.w=-p->yspeed.w;o->yspeed.w=-384;if(!o->r_no1)o->r_no1+=4;}
            }else if(p->mstno.b.h==2){p->yspeed.w=-p->yspeed.w;o->r_no0+=2;}
        }else{
            /* pcolspecial: 31/35/55 count every touch; 56 counts and hurts;
               46/58/59/60 (main_attack) count a rolling touch. The boss
               numbers (60..63 by bossstart) belong to the boss scan. */
            unsigned c=o->colino&63;
            if(c==31 || c==35 || c==55)o->colicnt++;
            else if(c==56){o->colicnt++;scd_objects_hurt(o->xposi.w.h);}
            else if((c==46 || c==58 || c==59 || c==60) && p->mstno.b.h==2)o->colicnt++;
        }
        return;
    }
}
