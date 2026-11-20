/* Stardust Speedway (R7) shared actor helpers: COLI7.C pcol and the scratch
   accessors the R7 ports use. Included by objects_ss.inc, after the TT
   helpers (objects_tt_ride.inc: tp_* RIDECHK port, claim, frameout, patchg;
   objects_tt_common.inc: tt_pcolnomal; objects_tt_enemies.inc: tt_child).

   Scratch storage keeps the PC reconstruction's little-endian byte layout, as
   the tp_* helpers do, so the compiled originals in tools/test-ss-actors.sh
   compare byte for byte. The accessors take the ORIGINAL indices:
     ((short*)o)[n] -> ss_w(o,n) / ss_ws(o,n,v)   (actfree bytes 2n-46)
     ((int*)o)[n]   -> ss_l(o,n) / ss_ls(o,n,v)   (actfree bytes 4n-46)
     ((char*)o)[n]  -> o->actfree[n-46] */
static inline short ss_w(const sprite_status *o,unsigned n){return tp_w(o,2*n-46);}
static inline short ss_ws(sprite_status *o,unsigned n,int v){return tp_wset(o,2*n-46,v);}
static inline int ss_l(const sprite_status *o,unsigned n){return tp_l(o,4*n-46);}
static inline int ss_ls(sprite_status *o,unsigned n,int v){return tp_lset(o,4*n-46,v);}
static inline unsigned ss_index(const sprite_status *o){return (unsigned)(o-actwk);}
extern void sub_sync(short);
extern unsigned char plautoflag,pltime_f;

/* COLI7.C colitbl. */
static const uint8_t ss_colitbl[64][2]={
    {20,20},{18,12},{12,16},{4,16},{12,18},{16,16},{6,6},{24,12},{12,16},{16,12},{8,8},{20,16},{20,8},{14,14},{24,24},{40,16},
    {16,24},{8,16},{32,112},{64,32},{128,32},{32,32},{8,8},{4,4},{32,8},{12,12},{8,4},{24,4},{40,4},{4,8},{4,24},{4,40},
    {4,32},{24,24},{12,24},{72,8},{8,12},{16,8},{32,16},{32,16},{40,4},{0,0},{0,0},{16,9},{16,16},{0,0},{16,16},{12,12},
    {5,5},{16,8},{8,16},{8,8},{12,12},{0,0},{0,0},{0,0},{0,0},{40,36},{18,17},{24,12},{20,20},{8,16},{0,0},{0,0}};
static int ss_contact_type(unsigned t);
/* COLI7.C pcolnomal. The chain score is the PC's emyscorecnt, which the
   player's landing (PLAYER.C jumpcolsub, RIDECHK ride_on_set) clears. */
static void ss_pcolnomal(unsigned i){
    sprite_status *o=&actwk[i+1],*p=actwk;
    if(!plpower_a && !plpower_m && !travel_protection && p->mstno.b.h!=2){scd_objects_hurt(o->xposi.w.h);return;}
    if(o->colicnt){
        p->xspeed.w=(int16_t)((int16_t)-p->xspeed.w/2);p->yspeed.w=(int16_t)((int16_t)-p->yspeed.w/2);
        o->colino=0;if(!--o->colicnt)o->cddat|=128;return;
    }
    o->cddat|=128;
    static const unsigned short escoretbl[4]={10,20,50,100};
    short c=emyscorecnt;emyscorecnt+=2;
    if((unsigned short)c>=6)c=6;
    ss_ws(o,33,c);unsigned score=escoretbl[c/2];
    if((unsigned short)emyscorecnt>=32){score=1000;ss_ws(o,33,10);}
    scd_player_points(score*10u);
    stats.defeated++;soundset(150);
    short before_vx=p->xspeed.w,before_vy=p->yspeed.w;
    if(p->yspeed.w>=0){if(p->yposi.w.h<o->yposi.w.h)p->yspeed.w=-p->yspeed.w;else p->yspeed.w-=256;}
    else p->yspeed.w+=256;
    scd_plus_enemy_defeat(i+1,before_vx,before_vy);
    if(pool[i].origin!=65535)consumed[pool[i].origin]=1;
    /* Convert in place: pcolnomal keeps the actor's slot. */
    pool[i].type=SCD_OBJ_EXPLOSION;pool[i].subtype=1;pool[i].age=0;pool[i].phase=CC_BADNIK_BOOM;
    pool[i].state=pool[i].frame=pool[i].cooldown=0;
    o->actno=SCD_OBJ_EXPLOSION;o->r_no0=0;o->userflag.b.h=1;
}
/* COLI7.C pcol: one box from the player's position over every visible actor
   with a collision number, in actor order. As COLI4, only an item contact
   (pcolitem's -1) ends the scan. */
static void ring_collect(unsigned i);
unsigned scd_boss_retail_slot(unsigned actor);
static void ss_enemy_scan(void){
    sprite_status *p=actwk;
    if(p->r_no0>=4)return;
    int16_t x=p->xposi.w.h-8,r=p->sprvsize-3,y=p->yposi.w.h-r;
    if(p->patno==57){y+=12;r=10;}
    int16_t h=r*2;
    /* COLI7 scans retail slots 32..127, including rings. pcolitem ends
       the scan even when the flash timer prevents collection. */
    unsigned order[SCD_OBJECT_CAPACITY],count=0;
    for(unsigned i=0;i<SCD_OBJECT_CAPACITY;i++){
        sprite_status *o=&actwk[i+1];
        int ring=pool[i].type==SCD_OBJ_RING && !pool[i].state;
        if(!(o->actflg&128) || (!ring && (!o->colino || !ss_contact_type(pool[i].type))))continue;
        unsigned at=count++,slot=scd_boss_retail_slot(i+1);
        while(at && scd_boss_retail_slot(order[at-1]+1)>slot){order[at]=order[at-1];--at;}
        order[at]=i;
    }
    for(unsigned k=0;k<count;k++){
        unsigned i=order[k];sprite_status *o=&actwk[i+1];
        int ring=pool[i].type==SCD_OBJ_RING;
        unsigned colino=ring?71:o->colino;
        unsigned n=(colino&63)-1;
        int16_t w=ss_colitbl[n][0],d=o->xposi.w.h-w;
        if(d<x){if((int16_t)(d-x)+2*w<0)continue;}
        else if((int16_t)(d-x)>16)continue;
        int16_t v=ss_colitbl[n][1],e=o->yposi.w.h-v;
        if(e<y){if((int16_t)(e-y)+2*v<0)continue;}
        else if((int16_t)(e-y)>h)continue;
        if(ring){if((uint16_t)scd_word_get(p,26)<90)ring_collect(i);return;}
        unsigned kind=colino&192;
        if(!kind)ss_pcolnomal(i);
        else if(kind==128)scd_objects_hurt(o->xposi.w.h);
        else if(kind==64){
            if((o->colino&63)!=6){if((uint16_t)scd_word_get(p,26)<90)o->r_no0+=2;}
            else if(p->yspeed.w<0){
                if(p->yposi.w.h-16>=o->yposi.w.h){p->yspeed.w=-p->yspeed.w;o->yspeed.w=-384;if(!o->r_no1)o->r_no1+=4;}
            }else if(p->mstno.b.h==2){p->yspeed.w=-p->yspeed.w;o->r_no0+=2;}
            return;
        }else{
            /* pcolspecial: 45/49 are enemies unless the player is rolling
               (then counted), 31/35 count every touch, 53/58/59 (main_attack)
               count a rolling touch. Boss numbers belong to the boss scan. */
            unsigned c=o->colino&63;
            if(c==45 || c==49){if(!(p->cddat&4))ss_pcolnomal(i);else o->colicnt++;}
            else if(c==31 || c==35)o->colicnt++;
            else if((c==53 || c==58 || c==59) && p->mstno.b.h==2)o->colicnt++;
        }
    }
}
