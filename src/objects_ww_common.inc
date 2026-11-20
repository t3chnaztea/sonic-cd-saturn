/* Wacky Workbench (R6) shared actor helpers: COLI6.C pcol and the scratch
   accessors of objects_qq_common.inc (qq_w/qq_ws/qq_l/qq_ls/qq_link, which
   take the ORIGINAL ((short*)o)[n] / ((int*)o)[n] indices), SUICIDE.C
   enemy_suicide (qq_enemy_suicide: the R6 programs link the same SUICIDE.C)
   and the tp_* RIDECHK port. Included after objects_qq.inc. */

/* COLI6.C colitbl. Rows 45..62 differ from COLI5. */
static const uint8_t ww_colitbl[64][2]={
    {20,20},{18,12},{16,16},{4,16},{12,18},{16,16},{6,6},{24,12},{12,16},{16,12},{8,8},{20,16},{20,8},{14,14},{24,24},{40,16},
    {16,24},{8,16},{32,112},{64,32},{128,32},{32,32},{8,8},{4,4},{32,8},{12,12},{8,4},{24,4},{40,4},{4,8},{4,24},{4,40},
    {4,32},{24,24},{12,24},{72,8},{8,12},{16,8},{32,16},{32,16},{0,0},{0,0},{0,0},{0,0},{0,0},{0,0},{8,19},{8,28},
    {24,12},{16,16},{4,4},{8,16},{16,5},{12,12},{8,8},{26,30},{8,8},{40,36},{18,17},{30,48},{60,32},{16,8},{2,12},{0,0}};
static int ww_contact_type(unsigned t);
/* COLI6.C playdamageset, called directly by R6 actors (gas_move4). Unlike
   pcol it tests no invulnerability: it clears actfree[0], actfree[2] bits
   3-4 and word 33, then loses the shield, drops the rings (the native
   lost-ring scatter, reached through scd_objects_hurt when its guards pass;
   a second call in one update finds plring already spent) or kills. */
static void ww_playdamageset(sprite_status *p,sprite_status *o){
    p->actfree[0]=0;p->actfree[2]&=231;scd_word_set(p,33,0);
    if(!plpower_b && plring && !(p->actfree[2]&128) && p->r_no0<4 && !scd_word_get(p,26) && !plpower_m && !travel_protection){
        scd_objects_hurt(o->xposi.w.h);return;
    }
    stats.hits++;
    if(plpower_b || plring || debugflag.w){playdamagechk(p,o);return;}
    playdieset(p);stats.deaths++;
}
/* COLI6.C pcol: one box from the player's position over every visible actor
   with a collision number, in actor order; the first contact of any kind
   ends the scan. A player held by a PLAYER6 shock (actfree[2] bit 6) is not
   tested at all. pcolplay (COLI6) also spares an invincible player. */
static void ww_enemy_scan(void){
    sprite_status *p=actwk;
    ww_ring_touched=0;
    if(p->r_no0>=4 || (p->actfree[2]&64))return;
    int16_t x=p->xposi.w.h-8,r=p->sprvsize-3,y=p->yposi.w.h-r;
    if(p->patno==57){y+=12;r=10;}
    int16_t h=r*2;
    for(unsigned i=0;i<SCD_OBJECT_CAPACITY;i++){
        sprite_status *o=&actwk[i+1];
        /* RING.C rings ($47, 6x6) take part in slot order, as in COLI4/5: the
           first contact ends the scan, so one ring at most per update. */
        const int ring=pool[i].type==SCD_OBJ_RING && !pool[i].state;
        if(!(o->actflg&128) || (!ring && (!o->colino || !ww_contact_type(pool[i].type))))continue;
        unsigned n=ring?6:(o->colino&63)-1;
        int16_t w=ww_colitbl[n][0],d=o->xposi.w.h-w;
        if(d<x){if((int16_t)(d-x)+2*w<0)continue;}
        else if((int16_t)(d-x)>16)continue;
        int16_t v=ww_colitbl[n][1],e=o->yposi.w.h-v;
        if(e<y){if((int16_t)(e-y)+2*v<0)continue;}
        else if((int16_t)(e-y)>h)continue;
        if(ring){if(!(p->actfree[2]&128) && (uint16_t)scd_word_get(p,26)<90)ww_ring_touched=i+1;return;}
        unsigned kind=o->colino&192;
        if(!kind)tt_pcolnomal(i);
        else if(kind==128){if(!plpower_a)scd_objects_hurt(o->xposi.w.h);}
        else if(kind==64){
            if((o->colino&63)!=6){if((uint16_t)scd_word_get(p,26)<90)o->r_no0+=2;}
            else if(p->yspeed.w<0){
                if(p->yposi.w.h-16>=o->yposi.w.h){p->yspeed.w=-p->yspeed.w;o->yspeed.w=-384;if(!o->r_no1)o->r_no1+=4;}
            }else if(p->mstno.b.h==2){p->yspeed.w=-p->yspeed.w;o->r_no0+=2;}
        }else{
            /* pcolspecial: 31/35 count every touch; 56/58/59 (main_attack)
               count a rolling touch; the rest is eggman_chk (boss scan). */
            unsigned c=o->colino&63;
            if(c==31 || c==35)o->colicnt++;
            else if((c==56 || c==58 || c==59) && p->mstno.b.h==2)o->colicnt++;
        }
        return;
    }
}
