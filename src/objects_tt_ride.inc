/* Tidal Tempest (R4) shared actor support for the objects_tt_platforms.inc port.
   Included by objects.c after the CC actors (needs pool, remove_slot,
   consumed, cc_object_draw, playdieset and soundset).

   Scratch storage keeps the PC reconstruction's little-endian byte layout
   (scd_actor.h): the R4 programs mix byte, word and long views of the same
   actfree bytes, so every word/long access goes through byte helpers and
   runs identically on SH-2 and on the host fixtures. Offsets passed to
   tp_w/tp_l are actfree byte offsets: ((short*)o)[n] is 2n-46, ((int*)o)[n]
   is 4n-46, ((char*)o)[n] is n-46. */
static inline short tp_w(const sprite_status *o,unsigned b){return (int16_t)(o->actfree[b]|(o->actfree[b+1]<<8));}
static inline unsigned short tp_wu(const sprite_status *o,unsigned b){return (uint16_t)(o->actfree[b]|(o->actfree[b+1]<<8));}
static inline short tp_wset(sprite_status *o,unsigned b,int v){o->actfree[b]=(uint8_t)v;o->actfree[b+1]=(uint8_t)((unsigned)v>>8);return (int16_t)v;}
static inline int tp_l(const sprite_status *o,unsigned b){
    return (int)((uint32_t)o->actfree[b]|((uint32_t)o->actfree[b+1]<<8)|((uint32_t)o->actfree[b+2]<<16)|((uint32_t)o->actfree[b+3]<<24));
}
static inline int tp_lset(sprite_status *o,unsigned b,int v){
    uint32_t u=(uint32_t)v;o->actfree[b]=u;o->actfree[b+1]=u>>8;o->actfree[b+2]=u>>16;o->actfree[b+3]=u>>24;return v;
}
extern void speedset2(sprite_status*);
extern short emycol_d(sprite_status*);
extern short emycol_u(sprite_status*);
extern short scdchk(sprite_status*,short,short,short,short,short,char*);
extern unsigned char switchflag[32];
extern char dirstk[4];
/* WALL42.C keeps its "already opened" bit in flagwork[cdsts*3+time_flag].
   Native placements carry no cdsts; index by placement origin instead
   (slot 0 stands for unplaced actors, cdsts 0 in the original). */
static uint8_t tp_flagwork[(SCD_PLACEMENT_CAPACITY+1)*3];
static void tp_reset(void){memset(tp_flagwork,0,sizeof(tp_flagwork));memset(switchflag,0,32);}
static int tp_type(unsigned t){
    if(objects_zone!=2)return 0;
    return t==SCD_OBJ_SW4 || t==SCD_OBJ_ESCAL4 || t==SCD_OBJ_RBLK4 || t==SCD_OBJ_UDBLK4 || t==SCD_OBJ_TEKKYU4 ||
           t==SCD_OBJ_KUZURE4 || t==SCD_OBJ_TOBIRA4 || t==SCD_OBJ_RENKETU4 || t==SCD_OBJ_SWGUN4 || t==SCD_OBJ_BRUNKO4 ||
           t==SCD_OBJ_LRBLK4 || t==SCD_OBJ_SWBLKR4 || t==SCD_OBJ_WALLS || t==SCD_OBJ_TEKKYU || t==SCD_OBJ_TEKKYU1 ||
           t==SCD_OBJ_TOBIRAS4 || t==SCD_OBJ_BANEIWA || t==SCD_OBJ_DAID4 || t==SCD_OBJ_WALL42 ||
           t==SCD_OBJ_SWITCHR4 || t==SCD_OBJ_RING4 || t==SCD_OBJ_TENSU4;
}
static unsigned tp_slot(const sprite_status *o){return (unsigned)(o-actwk)-1;}
static unsigned tp_origin(const sprite_status *o){
    unsigned i=tp_slot(o);return i<SCD_OBJECT_CAPACITY?pool[i].origin:65535;
}
/* R4 act numbers for RIDECHK.C's numeric actor tests (ACT41A-43C act_tbl
   index + 1): 10 spring, 21 gene, 25 item, 39 sw4, 40 tobira4. */
static unsigned tp_r4no(const sprite_status *o){
    switch(o->actno){
    case SCD_OBJ_SPRING:return 10;
    /* R8 act_tbl entry 10 is SPRING.C's spring too (ACT81A.C): the up spring
       keeps the rider's mspeed (RIDECHK.C ride_on_set; Object Solid.asm:131-136). */
    case SCD_OBJ_R8_SPRING8:return objects_zone==6?10:0;
    /* R8 id 9 is PLAYSP8.C chibi_coli (ACT82A/ACT83.C): RIDECHK hit_yu
       skips a bottom hit on id 9 (retail R82A $208C8A cmpi.b #9), so Sonic
       jumping up into it is not pushed down (retail MM2A row 4801). */
    case SCD_OBJ_R8_CHIBI_COLI:return objects_zone==6?9:0;
    case SCD_OBJ_GENERATOR:return 21;
    case SCD_OBJ_MONITOR_ITEM:return 25;
    case SCD_OBJ_SW4:return 39;
    case SCD_OBJ_TOBIRA4:return 40;
    }
    return 0;
}
/* ACTSET.C actwkchk/actwkchk2: a cleared actor, claimed for the caller.
   Retail searches actwk[32..127]; native actors live in actwk[1..96]. The
   claimed pool slot becomes live when the caller stores an actor number. */
/* Claims can become live before slot synchronization, without stats.spawned.
   Retail-order caches must rebuild after a claim even when the map is stable. */
static unsigned tp_claim_generation;
static int tp_claim(unsigned first,sprite_status **out){
    for(unsigned i=first;i<SCD_OBJECT_CAPACITY;i++)if(!pool[i].type){
        tp_claim_generation++;
        pool[i]=(slot){.origin=65535,.type=255};memset(&actwk[i+1],0,sizeof(actwk[0]));
        *out=&actwk[i+1];return 0;
    }
    return -1;
}
/* MM: the retail slot is taken at the call (scd_boss_slot_first); retail MM3C
   543 puts TOGEITA's three parts in slots 69-71 while 38-40 still hold
   actors that frame out later in that update. QQ too: retail QQ2A 2484,
   KUZURE5 in slot 36 puts its second piece in 39 before it frames out.
   Other zones keep the slot model's first-seen assignment. */
static int tp_actwkchk(sprite_status **out){
    if(tp_claim(0,out))return -1;
    if(objects_zone==6 || objects_zone==3)scd_boss_slot_first((unsigned)(*out-actwk));
    return 0;
}
/* actwkchk2 searches from the caller's retail slot, so the child also takes
   the first free retail slot after the caller's (src/boss.c slot model; retail
   QQ1B: the sasori in slot 67 puts its tail in 69, slot 68 being taken). */
static int tp_actwkchk2(sprite_status *o,sprite_status **out){
    unsigned parent=tp_slot(o);
    if(tp_claim(parent+1,out))return -1;
    scd_boss_slot_after((unsigned)(*out-actwk),parent+1);return 0;
}
#ifdef SCD_HOST_TEST
/* tools/tt_platforms_test.c holds children owned by other ports inert:
   1 awa and harir4, 2 awa only. */
int scd_tp_inert_children;
#endif
static void tp_setactno(sprite_status *o,unsigned type){
    o->actno=type;unsigned i=tp_slot(o);
    if(i<SCD_OBJECT_CAPACITY){pool[i].type=type;pool[i].subtype=o->userflag.b.h;pool_typed(i,type);}
#ifdef SCD_HOST_TEST
    if(scd_tp_inert_children && i<SCD_OBJECT_CAPACITY && ((type==SCD_OBJ_HARIR4 && scd_tp_inert_children<2) || type==SCD_OBJ_AWA))pool[i].type=SCD_OBJ_LOG_SHADOW;
#endif
}
static void tp_copyact(sprite_status *d,const sprite_status *s,size_t n){memcpy(d,s,n);tp_setactno(d,s->actno);}
/* ACTION.C actionsub's visibility bit (DrawObject submission). */
static void tp_draw(sprite_status *o){cc_object_draw(o);unsigned i=tp_slot(o);if(i<SCD_OBJECT_CAPACITY)pool[i].sink=1;}
static short tp_scra_h(void){return (short)scd_act_view_x();}
static unsigned char tp_pltime_b3(void){return (unsigned char)(scd_player_get().elapsed/60%60);}
/* frameout leaves the placement's flagwork bit set: the object does not
   reload. The frameout_s variants clear it first: it reloads on return. */
static void tp_remove(sprite_status *o,int keep){
    unsigned i=tp_slot(o);if(i>=SCD_OBJECT_CAPACITY || !pool[i].type)return;
    /* ACTION.C frameout only clears the slot. A record with a saved-flags
       entry keeps its spawned bit (Object Spawner.asm SpawnObject bset #7)
       and never reloads; one without (layout id bit 7 clear) spawns again
       whenever the spawner walks over it: retail QQ2A reloads the HASIRA5
       pillar (id 43, unsaved) at 6872,912 after its pieces framed out.
       Only the retail spawner walk (tt_stream) has that rule. */
    if(keep && pool[i].origin<SCD_PLACEMENT_CAPACITY && (!tt_streamed() || (active_placements[pool[i].origin].flags&TT_SAVED)))consumed[pool[i].origin]=1;
    remove_slot(i);
}
static void tp_frameout(sprite_status *o){tp_remove(o,1);}
/* KUZURE4.C clears cdsts: the frameout_s variants then leave the bit set. */
static void tp_noreload(sprite_status *o){unsigned n=tp_origin(o);if(n<SCD_PLACEMENT_CAPACITY)consumed[n]=1;}
static unsigned tp_cdsts(const sprite_status *o){unsigned n=tp_origin(o);return n<SCD_PLACEMENT_CAPACITY?n+1:0;}
/* FRAMEOUT_S0 clears the placement's flagwork bit 7: ACTSET reloads it when
   the camera window next reaches its column (retail R41A SW4 2928,1016:
   framed out at level frame 3308, reloaded at 3329). The removal is outside
   that window, so the reload does not wait for the window to leave it. A
   removal inside the window keeps stream()'s deferred reload. */
static int tp_frameout_s0(sprite_status *o){
    unsigned n=tp_origin(o);tp_remove(o,0);
    if((objects_zone==2 || objects_zone==3 || objects_zone==4) && n<SCD_PLACEMENT_CAPACITY){ /* TT, QQ and WW reload after leaving the camera window. */
        short h=tp_scra_h();h-=128;h&=-128;
        if((unsigned short)(short)((active_placements[n].x&-128)-h)>640)deferred_reload[n]=0;
    }
    return -1;
}
static int tp_frameout_s00(sprite_status *o,short xposi){
    if(o->actflg&128){if(!(time_flag&128))return 0;}
    else{
        xposi&=-128;short h=tp_scra_h();h-=128;h&=-128;xposi-=h;
        if((unsigned short)xposi<=640 && !(time_flag&128))return 0;
    }
    return tp_frameout_s0(o);
}
static int tp_frameout_s(sprite_status *o){return tp_frameout_s00(o,o->xposi.w.h);}
static void tp_scoreup(unsigned n){scd_player_points(n*10);} /* SCORE.C keeps score/10 */
static void tp_ringgetsub(void){scd_player_rings(1);}
/* PLAYSUB4.C patchg. */
static void tp_patchg(sprite_status *o,const unsigned char *const *pat_dat){
    if(o->mstno.b.h!=o->mstno.b.l){o->mstno.b.l=o->mstno.b.h;o->patcnt=o->pattim=0;}
    if((int8_t)--o->pattim>=0)return;
    const unsigned char *a=pat_dat[(unsigned char)o->mstno.b.h];
    unsigned n=0;while(a[n]<250)n++;
    /* PLAYSUB.C:24 patchg's 0 -> 1 frame time is the PC's; retail patchg
       (R83D $2059E6: moveb (a1),pattim) keeps 0, one frame per update
       (retail MM1A DAI8 appears in 46 updates for its 46-entry script). */
    o->pattim=a[n]!=252 && objects_zone!=6?(a[0]==0?1:a[0]):a[0];
    unsigned char pat=a[o->patcnt+1];
    if(pat>=128){
        switch(pat){
        case 255:o->patcnt=0;pat=a[1];break;
        case 254:o->patcnt-=a[o->patcnt+2];pat=a[o->patcnt+1];break;
        case 253:o->mstno.b.h=a[o->patcnt+2];return;
        case 252:o->r_no0+=2;return;
        case 251:o->patcnt=o->r_no1=0;return;
        case 250:o->r_no1+=2;return;
        default:return;
        }
    }
    o->patno=pat&31;o->actflg=(o->actflg&252)|(((pat>>5)^o->cddat)&3);o->patcnt++;
}

/* RIDECHK.C, the full routine set (ride_on_clr through hit_clr). Only R4
   actors call these; the CC and PPZ solids keep their specialised ports. */
static short tp_hit_e(sprite_status *a,sprite_status *p);
static short tp_ride_on_clr(sprite_status *a,sprite_status *p){
    if(!(a->cddat&8) || !(p->cddat&8))return -1;
    if((unsigned short)(a-actwk)!=p->actfree[19])return -1;
    if(p->actfree[0])soundset(171);
    p->actfree[14]=0;p->cddat|=2;p->cddat&=247;a->cddat&=247;
    unsigned char f=p->actfree[2];
    if(!(f&64) && p->mstno.b.h!=23)f&=254;
    p->actfree[2]=f;p->actfree[19]=0;
    if(p->mstno.b.h==43)p->cddat&=253;
    return 0;
}
static short tp_ride_on_set(sprite_status *a,sprite_status *p){
    if(p->r_no0==4){p->r_no0-=2;scd_word_set(p,26,120);}
    a->r_no1=0;p->actfree[18]=0;
    unsigned ccr=a->cddat&8;a->cddat|=8;
    if(!ccr){
        if(p->mstno.b.h==43){a->cddat&=247;return tp_ride_on_clr(a,p);}
        p->cddat&=239;ccr=p->cddat&4;p->cddat&=251;
        if(ccr){
            if(chibi_flag){p->sprvsize=10;p->sprhs=5;p->yposi.w.h-=2;}
            else{p->sprvsize=19;p->sprhs=9;p->yposi.w.h-=5;}
            p->mstno.b.h=0;
        }
    }
    ccr=p->cddat&8;p->cddat|=8;
    if(ccr){
        unsigned short n=p->actfree[19];
        if((unsigned short)(a-actwk)==n)return -1;
        actwk[n].cddat&=247;
    }
    p->actfree[19]=(unsigned char)(a-actwk);p->direc.w=0;p->yspeed.w=0;
    if(tp_r4no(a)!=10 || a->r_no0!=2)p->mspeed.w=p->xspeed.w;
    p->cddat&=253;return 0;
}
static void tp_hit_clr(sprite_status *a,sprite_status *p){if(a!=&actwk[(unsigned short)p->colino])p->colino=0;}
static void tp_hit_set(sprite_status *a,sprite_status *p){
    if(tp_r4no(a)==10){p->colino=0;return;}
    short n=(unsigned short)p->colino;
    if(n){
        sprite_status *h=&actwk[n];
        if(h==a)return;
        if(a->xspeed.w==0 && h->xspeed.w==0)return;
        if(p->xposi.w.h>=a->xposi.w.h && p->xposi.w.h>=h->xposi.w.h)return;
        if(tp_r4no(a)==21)return;
        /* R41A only: tobira4 closing on a sw4 does not crush. */
        if(objects_act==0 && current_era==0 && tp_r4no(a)==40 && tp_r4no(h)==39)return;
        if(stageno.w==768 && tp_r4no(a)==39 && tp_r4no(h)==39)return;
        playdieset(p);return;
    }
    p->colino=(unsigned char)(a-actwk);
}
static void tp_side_coli(sprite_status *a,sprite_status *p){
    char d=-64;
    if(a->xspeed.w==0 || tp_r4no(a)==10)return;
    if(a->xspeed.w<0)d=-d;
    if(dircol(p,&d)>=0)return;
    playdieset(p);
}
static short tp_hit_e(sprite_status *a,sprite_status *p){tp_hit_clr(a,p);tp_ride_on_clr(a,p);a->r_no1=0;return 0;}
static short tp_push_set(sprite_status *a,sprite_status *p){
    tp_side_coli(a,p);
    if(!(p->cddat&2)){a->cddat|=32;p->cddat|=32;p->mspeed.w=0;}
    p->xspeed.w=0;return 0;
}
static short tp_push_clr(sprite_status *a,sprite_status *p){
    tp_hit_clr(a,p);tp_side_coli(a,p);a->cddat&=223;p->cddat&=223;return 0;
}
static short tp_hit_yu0(sprite_status *a,sprite_status *p,short ys){
    p->yposi.w.h-=ys;p->yspeed.w=0;tp_hit_clr(a,p);tp_ride_on_clr(a,p);a->r_no1=0;return 1;
}
static short tp_hit_yu1(sprite_status *a,sprite_status *p,short ys){
    if(!(p->cddat&2) && a->yspeed.w>0)playdieset(p);
    return tp_hit_yu0(a,p,ys);
}
static short tp_hit_yu(sprite_status *a,sprite_status *p,short ys){
    if(a->r_no1==1)return tp_hit_e(a,p);
    if(tp_r4no(a)==9)return tp_hit_e(a,p);
    if(tp_r4no(a)!=10)return tp_hit_yu1(a,p,ys);
    if(a->r_no1==2 || (a->actflg&2))return tp_hit_yu0(a,p,ys);
    return tp_hit_e(a,p);
}
static short tp_hit_y(sprite_status *a,sprite_status *p,short ys){
    if(tp_r4no(a)==25 && (p->cddat&4))return tp_hit_e(a,p);
    short v=a->sprvsize;v+=p->sprvsize;
    if(ys<0)return tp_hit_yu(a,p,ys);
    if(p->mstno.b.h!=43 && p->yspeed.w<0)return tp_hit_e(a,p);
    p->yposi.w.h=a->yposi.w.h;p->yposi.w.h-=v;
    p->xposi.l+=(int)a->xspeed.w*256;
    char d=-64;if(a->xspeed.w<0)d=-d;
    if(a->xspeed.w){
        short c=dircolm(p,&d);
        if(c<0){if(a->xspeed.w<0)c*=-1;p->xposi.w.h+=c;}
    }
    p->yposi.l+=(int)a->yspeed.w*256;
    if(tp_r4no(a)!=10){
        if(a->yspeed.w>=0){
            short d0,d1,d3,c=dircol_d(p,&d0,&d1,&d3);
            if(c<0){p->yposi.w.h+=c;return tp_hit_e(a,p);}
        }
        if(a->yspeed.w<0 && dircol_u2(p)<0){playdieset(p);return tp_hit_e(a,p);}
    }
    tp_ride_on_set(a,p);return 1;
}
static short tp_hit_x(sprite_status *a,sprite_status *p,short xs,short d5){
    if(a->r_no1==1)return tp_hit_e(a,p);
    if(tp_r4no(a)==10 && (p->cddat&2))return tp_hit_e(a,p);
    if((unsigned short)d5<5)return tp_hit_e(a,p);
    tp_hit_set(a,p);tp_ride_on_clr(a,p);a->r_no1=0;
    p->xposi.w.h-=xs;
    if(xs>=0)return p->xspeed.w>0?tp_push_set(a,p):tp_push_clr(a,p);
    return p->xspeed.w>=0?tp_push_clr(a,p):tp_push_set(a,p);
}
static short tp_hit_v(sprite_status *a,sprite_status *p,short xs,short hs){
    short w=(tp_r4no(a)==25 && (actwk[0].cddat&4))?-2:2;
    short vs=(short)a->sprvsize+(short)p->sprvsize+w;
    short ys=p->yposi.w.h-a->yposi.w.h;ys+=vs;
    if(ys<0)return tp_hit_e(a,p);
    short d4=vs+vs;if(ys>=d4)return tp_hit_e(a,p);
    d4=xs;
    if(hs<xs){hs+=hs;xs-=hs;d4=-xs;}
    short d5=ys;
    if(vs<ys){vs+=vs;ys-=vs;d5=-ys;}
    if(d5<d4)return tp_hit_y(a,p,ys);
    return tp_hit_x(a,p,xs,d5);
}
static short tp_hitchk(sprite_status *a,sprite_status *p){
    if(p->mstno.b.h==23 || (p->actfree[2]&64) || p->r_no0>=6 || p->actno==0 ||
       !(a->actflg&128) || editmode.b.h!=0)return tp_hit_e(a,p);
    short d1=(short)a->sprhsize+10,d0=p->xposi.w.h-a->xposi.w.h;d0+=d1;
    if(d0<0)return tp_hit_e(a,p);
    short d2=d1;d2+=d2;
    if((unsigned short)d0>=(unsigned short)d2)return tp_hit_e(a,p);
    if(p->mstno.b.h==43)return (a->cddat&8)?tp_hit_v(a,p,d0,d1):tp_hit_e(a,p);
    if(a->r_no1!=1 || p->yspeed.w==0)return tp_hit_v(a,p,d0,d1);
    if(p->yspeed.w<0)return tp_hit_e(a,p);
    return tp_hit_v(a,p,d0,d1);
}
static short tp_ride_on_chk(sprite_status *a,sprite_status *p){return tp_hitchk(a,p);}
static short tp_hitchk_u(sprite_status *a,sprite_status *p){a->r_no1=2;return tp_ride_on_chk(a,p);}
static short tp_ridechk(sprite_status *a,sprite_status *p){a->r_no1=1;return tp_ride_on_chk(a,p);}
#ifdef SCD_HOST_TEST
/* Host fixtures replay one native tick from many saved states. */
size_t scd_tp_state_size(void){return sizeof(pool)+sizeof(consumed)+sizeof(tp_flagwork)+sizeof(stats);}
void scd_tp_state_save(uint8_t *b){
    memcpy(b,pool,sizeof(pool));b+=sizeof(pool);memcpy(b,consumed,sizeof(consumed));b+=sizeof(consumed);
    memcpy(b,tp_flagwork,sizeof(tp_flagwork));b+=sizeof(tp_flagwork);memcpy(b,&stats,sizeof(stats));
}
void scd_tp_state_load(const uint8_t *b){
    memcpy(pool,b,sizeof(pool));b+=sizeof(pool);memcpy(consumed,b,sizeof(consumed));b+=sizeof(consumed);
    memcpy(tp_flagwork,b,sizeof(tp_flagwork));b+=sizeof(tp_flagwork);memcpy(&stats,b,sizeof(stats));
}
#endif
