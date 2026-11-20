/* Tidal Tempest (R4) shared actor helpers: PLAYSUB4.C patchg, COLI4.C pcol,
   SUICIDE.C enemy_suicide, ACTSET.C frameout_s and IO.C random.
   Included after the CC rider helpers (cc_ride, cc_solid, cc_object_draw).
   Scratch words keep the original offsets: ((short*)o)[w] is scd_word w and
   ((int*)o)[n] / *(int*)&actfree[b] are little-endian word pairs, as in the
   compiled PC originals the fixtures compare against. */
static int16_t tt_word(const sprite_status *o,unsigned w){return (int16_t)scd_word_get(o,w);}
static void tt_set_word(sprite_status *o,unsigned w,int v){scd_word_set(o,w,(unsigned)v&65535u);}
/* ((int*)o)[n]: bytes 4n-46, i.e. scd words 2n and 2n+1. */
static int32_t tt_long(const sprite_status *o,unsigned n){
    return (int32_t)((uint32_t)scd_word_get(o,2*n)|((uint32_t)scd_word_get(o,2*n+1)<<16));
}
static void tt_set_long(sprite_status *o,unsigned n,int32_t v){
    scd_word_set(o,2*n,(uint32_t)v&65535u);scd_word_set(o,2*n+1,(uint32_t)v>>16);
}
/* *(int*)&o->actfree[b] for even b. */
static int32_t tt_free_long(const sprite_status *o,unsigned b){
    return (int32_t)((uint32_t)o->actfree[b]|((uint32_t)o->actfree[b+1]<<8)|((uint32_t)o->actfree[b+2]<<16)|((uint32_t)o->actfree[b+3]<<24));
}
static void tt_set_free_long(sprite_status *o,unsigned b,int32_t v){
    uint32_t u=(uint32_t)v;o->actfree[b]=u;o->actfree[b+1]=u>>8;o->actfree[b+2]=u>>16;o->actfree[b+3]=u>>24;
}
/* PLAYSUB4.C patchg, all script codes. */
static void tt_patchg(sprite_status *o,const uint8_t *const *scripts){
    if(o->mstno.b.h!=o->mstno.b.l){o->mstno.b.l=o->mstno.b.h;o->patcnt=o->pattim=0;}
    if((int8_t)--o->pattim>=0)return;
    const uint8_t *s=scripts[o->mstno.b.h];
    unsigned end=0;while(s[end]<250)end++;
    o->pattim=s[end]!=252 && s[0]==0 && objects_zone!=6?1:s[0]; /* MM: retail keeps 0 (tp_patchg) */
    unsigned pat=s[o->patcnt+1];
    if(pat>=128){
        switch(pat){
        case 255:o->patcnt=0;pat=s[1];break;
        case 254:o->patcnt-=s[o->patcnt+2];pat=s[o->patcnt+1];break;
        case 253:o->mstno.b.h=s[o->patcnt+2];return;
        case 252:o->r_no0+=2;return;
        case 251:o->patcnt=o->r_no1=0;return;
        case 250:o->r_no1+=2;return;
        default:return;
        }
    }
    o->patno=pat&31;o->actflg=(o->actflg&252)|(((pat>>5)^o->cddat)&3);o->patcnt++;
}
static int tt_frameout(unsigned i,int x){
    /* ACTSET.C frameout_s00: an actor off screen (actflg bit 7 clear) whose
       column X leaves the camera window frames out; a placement's flagwork
       bit 7 is cleared, so ACTSET respawns it at home when the window next
       reaches its column (retail TT1D Yago: slot 50 respawns at 912 on level
       frame 832). A home column already inside the window waits for the
       window to leave it (stream()'s deferred reload), as ACTSET only loads
       a column the moving window reaches. */
    /* Round 4 only; other zones keep the placement guard. */
    if(objects_zone!=2 && pool[i].origin!=65535)return 0;
    /* frameout_s00 with time_flag bit 7 (the time warp) deletes on screen too. */
    if(scd_player_warp_saved()){remove_slot(i);return 1;}
    if(actwk[i+1].actflg&128)return 0;
    short h=(short)((scd_act_view_x()-128)&-128);
    int16_t d=(int16_t)((x&-128)-h);
    if((uint16_t)d<=640)return 0;
    unsigned n=pool[i].origin;remove_slot(i);
    if(objects_zone==2 && n<SCD_PLACEMENT_CAPACITY && (uint16_t)(int16_t)((active_placements[n].x&-128)-h)>640)deferred_reload[n]=0;
    return 1;
}
/* Level Random on the shared ranum seed. */
static int32_t tt_random(void){
    /* Level/Functions (General).asm:14-33 Random: plain asl.l shifts, then
       d0.w = d1.w (move.w), d0.w += swap(d1).w. The PC IO.C random differs
       (sign-kept shifts, d0.w += d1.w); retail TT seeds follow this chain. */
    uint32_t d1=ranum?(uint32_t)ranum:0x2A6D365Au,d0=d1;
    d1<<=2;d1+=d0;d1<<=3;d1+=d0;
    d0=(d0&0xffff0000u)|(d1&0xffffu);
    d1=d1<<16|d1>>16;
    d0=(d0&0xffff0000u)|((d0+d1)&0xffffu);
    d1=(d1&0xffff0000u)|(d0&0xffffu);
    d1=d1<<16|d1>>16;
    ranum=(int)d1;return (int32_t)d0;
}
/* SUICIDE.C enemy_suicide: Good Future (generator broken) removes the enemy
   into an explosion; the Present keeps undamaged (subtype 0) enemies. */
static int tt_enemy_suicide(unsigned i){
    sprite_status *o=&actwk[i+1];
    if(!good_future || (current_era==0 && !o->userflag.b.h))return 0;
    int x=o->xposi.w.h,y=o->yposi.w.h;
    /* frameout, not frameout_s: a saved-flags record keeps flagwork bit 7, so
       SpawnObject never loads it again (retail TT1C: the Good Future enemy at
       608,1456 suicides on row 1 and is not respawned when the window returns
       at row 2039). Other records reload as before. */
    unsigned n=pool[i].origin;
    if(n<SCD_PLACEMENT_CAPACITY && (active_placements[n].flags&TT_SAVED))consumed[n]=1;
    else if(n!=65535)deferred_reload[n]=1;
    remove_slot(i);
    pool[i]=(slot){.origin=65535,.type=SCD_OBJ_EXPLOSION};
    o->actno=SCD_OBJ_EXPLOSION;o->xposi.w.h=x;o->yposi.w.h=y;
    /* ENEMY_SUICIDE: `if (actflg < 0) soundset(158)` runs after frameout
       zeroed the actor (action.c:187), so the original never plays it. */
    return 1;
}
/* COLI4.C colitbl. */
static const uint8_t tt_colitbl[64][2]={
    {20,20},{18,12},{12,16},{4,16},{12,18},{16,16},{6,6},{24,12},{12,16},{16,12},{8,8},{20,16},{20,8},{14,14},{24,24},{40,16},
    {16,24},{8,16},{32,112},{64,32},{128,32},{32,32},{8,8},{4,4},{32,8},{12,12},{8,4},{24,4},{40,4},{4,8},{4,24},{4,40},
    {4,32},{24,24},{12,24},{72,8},{8,12},{16,8},{32,16},{32,16},{12,12},{0,0},{0,0},{24,8},{20,8},{2,2},{24,12},{14,19},
    {12,8},{4,4},{22,18},{0,0},{0,0},{0,0},{0,0},{0,0},{0,0},{40,36},{18,17},{32,20},{32,24},{3,3},{4,4},{0,0}};
/* Actors whose COLI4 collision numbers the native pcol scan owns. */
static int tt_contact_type(unsigned t){
    /* Tidal Tempest types occur only in zone 2: every other zone's view,
       contact and ride dispatch skips the comparison chain. */
    if(objects_zone!=2)return 0;
    return t==SCD_OBJ_TONBO || t==SCD_OBJ_YAGO || t==SCD_OBJ_AMENBO || t==SCD_OBJ_TAGAMEB || t==SCD_OBJ_HARIR4 || t==SCD_OBJ_HARID4 ||
           t==SCD_OBJ_MOVIE4 || t==SCD_OBJ_ET4 ||
           /* objects_tt_platforms.inc: iron balls (169) and SWGUN4 rings (71). */
           t==SCD_OBJ_TEKKYU || t==SCD_OBJ_TEKKYU1 || t==SCD_OBJ_TEKKYU4 || t==SCD_OBJ_RING4;
}
/* Native TT actors: views carry the original pose (patno) and flip bits. */
static int tt_view_type(unsigned t){
    if(objects_zone!=2)return 0;
    return tt_contact_type(t) || t==SCD_OBJ_SCREW || t==SCD_OBJ_SCREW_F || t==SCD_OBJ_BOU || t==SCD_OBJ_OSUMIZU || t==SCD_OBJ_FUNSUI4 ||
           t==SCD_OBJ_UKIDAI || t==SCD_OBJ_AWA || t==SCD_OBJ_FRIEND4 || t==SCD_OBJ_MOVIE4 || t==SCD_OBJ_ET4 || t==SCD_OBJ_WAVE;
}
/* COLI4.C pcolnomal. */
static void tt_pcolnomal(unsigned i){
    sprite_status *o=&actwk[i+1],*p=actwk;
    if(!plpower_a && !plpower_m && !travel_protection && p->mstno.b.h!=2){scd_objects_hurt(o->xposi.w.h);return;}
    if(o->colicnt){
        /* Retail pcolnomal (R43C__.MMD $7160-$716C): neg.w then asr.w, which
           rounds toward minus infinity (the PC "/ 2" truncates). */
        p->xspeed.w=(int16_t)((int16_t)-p->xspeed.w>>1);p->yspeed.w=(int16_t)((int16_t)-p->yspeed.w>>1);
        o->colino=0;if(!--o->colicnt)o->cddat|=128;return;
    }
    o->cddat|=128;
    /* COLI4.C: word 33 = min(emyscorecnt,6), 10 from emyscorecnt 32. */
    unsigned chain=(unsigned short)emyscorecnt,index=chain>=6?6:chain;emyscorecnt+=2;tt_set_word(o,33,emyscorecnt>=32?10:index);
    static const unsigned points[]={100,200,500,1000};
    scd_player_points(emyscorecnt>=32?10000:points[index/2]);
    stats.defeated++;soundset(150);
    short before_vx=p->xspeed.w,before_vy=p->yspeed.w;
    if(p->yspeed.w>=0){if(p->yposi.w.h<o->yposi.w.h)p->yspeed.w=-p->yspeed.w;else p->yspeed.w-=256;}
    else p->yspeed.w+=256;
    scd_plus_enemy_defeat(i+1,before_vx,before_vy);
    if(pool[i].origin!=65535)consumed[pool[i].origin]=1;
    /* Convert in place: pcolnomal keeps the actor's slot. */
    pool[i].type=SCD_OBJ_EXPLOSION;pool[i].subtype=1;pool[i].age=0;
    pool[i].state=pool[i].frame=pool[i].cooldown=0;pool[i].phase=CC_BADNIK_BOOM;
    o->actno=SCD_OBJ_EXPLOSION;o->r_no0=0;o->userflag.b.h=1;
}
/* COLI4.C pcol: one box from the player's position, every visible actor
   with a collision number, in actor order; the first contact ends the scan. */
static unsigned tt_ring_touched; /* slot+1 of the ring pcol touched this update */
static void tt_enemy_scan(void){
    sprite_status *p=actwk;
    tt_ring_touched=0;
    if(p->r_no0>=4)return;
    int16_t x=p->xposi.w.h-8,r=p->sprvsize-3,y=p->yposi.w.h-r;
    if(p->patno==57){y+=12;r=10;}
    int16_t h=r*2;
    for(unsigned i=0;i<SCD_OBJECT_CAPACITY;i++){
        sprite_status *o=&actwk[i+1];
        /* RING.C rings carry colino $47 (pcolitem) and sit in this scan in
           slot order: the first touched actor ends it, so one ring at most is
           collected per update (retail TT2A row 5919: slot 85's ring waits one
           update behind the ring collected at 5918). */
        const int ring=pool[i].type==SCD_OBJ_RING && !pool[i].state;
        if(!(o->actflg&128) || (!ring && (!o->colino || !tt_contact_type(pool[i].type))))continue;
        unsigned n=ring?6:(o->colino&63)-1;
        int16_t w=tt_colitbl[n][0],d=o->xposi.w.h-w;
        if(d<x){if((int16_t)(d-x)+2*w<0)continue;}
        else if((int16_t)(d-x)>16)continue;
        int16_t v=tt_colitbl[n][1],e=o->yposi.w.h-v;
        if(e<y){if((int16_t)(e-y)+2*v<0)continue;}
        else if((int16_t)(e-y)>h)continue;
        /* Retail pcol (R41D__.MMD $7060-$7232) branches to the class handler
           on the first overlapping actor and each handler ends with rts: one
           contact per update. The PC decompile (COLI4.C pcol) keeps scanning
           after a normal, special or hurt contact. */
        if(ring){if(!(p->actfree[2]&128) && (uint16_t)scd_word_get(p,26)<90)tt_ring_touched=i+1;return;}
        unsigned kind=o->colino&192;
        if(!kind){tt_pcolnomal(i);return;}
        else if(kind==128){scd_objects_hurt(o->xposi.w.h);return;}
        else if(kind==64){
            /* pcolitem: a ring/item collects (r_no0 += 2) unless the player
               was hurt within the last 30 updates; any item hit ends the scan.
               Number 6 (monitor) bounces from below or breaks when rolling. */
            if((o->colino&63)!=6){if((uint16_t)scd_word_get(p,26)<90)o->r_no0+=2;}
            else if(p->yspeed.w<0){
                if(p->yposi.w.h-16>=o->yposi.w.h){p->yspeed.w=-p->yspeed.w;o->yspeed.w=-384;if(!o->r_no1)o->r_no1+=4;}
            }else if(p->mstno.b.h==2){p->yspeed.w=-p->yspeed.w;o->r_no0+=2;}
            return;
        }
        else if(kind==192){
            /* pcolspecial: 31/35 count every touch, 51/58/59 (main_attack)
               count a rolling touch. Boss numbers belong to the boss scan. */
            unsigned c=o->colino&63;
            if(c==31 || c==35)o->colicnt++;
            else if((c==51 || c==58 || c==59) && p->mstno.b.h==2)o->colicnt++;
            return;
        }
    }
}
