/* PLAYSUB4.C wave: the water-surface shimmer GAME4.C:635 puts in actwk[32]
   at every Tidal Tempest program start (so at each act load, life and time
   travel). It follows the camera, alternating 96 px left and right of centre
   every two updates, two lines below the water level. Never frames out. */
static const uint8_t tt_wave_chg0[]={2,0,1,0,1,0,1,0,1,0,1,0,1,2,3,2,3,2,3,2,3,2,3,2,3,4,5,4,5,4,5,4,5,4,5,4,5,6,7,6,7,6,7,6,7,6,7,6,7,255};
static const uint8_t *const tt_wave_chg[]={tt_wave_chg0};
static void tt_wave_act(sprite_status *o){
    static const short wave_tbl[2]={-96,96};
    if(!o->r_no0){o->actflg|=4;o->sproffset=33408;o->r_no0+=2;}
    if(++o->actfree[0]>=4)o->actfree[0]=0;
    o->xposi.w.h=tp_scra_h()+160+wave_tbl[o->actfree[0]/2];
    o->yposi.w.h=waterposi+2;
    tp_patchg(o,tt_wave_chg);
    tp_draw(o);
}
/* Retail actwk[32] is the first dynamic slot (FindObjSlot, R41C__.MMD $7A8A,
   starts at $FFD800), which is native pool slot 0 (actwk[1]): every later
   allocation then takes the same dynamic slot index as retail (retail TT1C
   rows 2-300: the first placement in actwk[33], the title card pieces in
   actwk[42..49]). The slot is free right after a reset or era change. */
/* Actor fixtures (tools/tt_actor_fixture.h, tools/tt_platforms_test.c) map
   native actwk[k] to the compiled original's actwk[k] and set 31 here, which
   keeps their placed actor in actwk[1] and the wave in actwk[32]. */
unsigned scd_tt_wave_slot;
static void tt_wave_spawn(void){
    unsigned w=scd_tt_wave_slot<SCD_OBJECT_CAPACITY?scd_tt_wave_slot:0;
    if(objects_zone!=2 || pool[w].type)return;
    pool[w]=(slot){.origin=65535,.type=SCD_OBJ_WAVE};
    memset(&actwk[w+1],0,sizeof(actwk[w+1]));actwk[w+1].actno=SCD_OBJ_WAVE;stats.spawned++;
}
/* _Objects/Title Card/Main.asm: the card's eight pieces hold dynamic slots
   from its init until each has slid out (retail TT1C/TT2C rows 1-127). The
   card (reserved actwk[4]) inits in the first RunObjects after
   SpawnObjects_Init and before any dynamic actor runs, so a started card's
   pieces are allocated by the next scd_objects_step right after stream(). */
static uint8_t tt_card_slot[9];
static int tt_card_live(void);
static void tt_card_allocate(void){
    if(!tt_card_pending)return;
    tt_card_pending=0;
    if(tt_card_live())return;
    for(unsigned piece=1;piece<9;piece++){
        tt_card_slot[piece]=0;
        for(unsigned i=0;i<SCD_OBJECT_CAPACITY;i++)if(!pool[i].type){
            pool[i]=(slot){.origin=65535,.type=SCD_OBJ_CARD};
            memset(&actwk[i+1],0,sizeof(actwk[i+1]));actwk[i+1].actno=SCD_OBJ_CARD;stats.spawned++;
            tt_card_slot[piece]=(uint8_t)(i+1);break;
        }
    }
}
static int tt_card_live(void){
    for(unsigned piece=1;piece<9;piece++)if(tt_card_slot[piece] && pool[tt_card_slot[piece]-1u].type==SCD_OBJ_CARD)return 1;
    return 0;
}
/* scd_title_card_prepare (src/main.c, before its load) and the card's start
   both request the pieces; the first request allocates them. Liveness is
   checked when the request is served, not when it is made: a load started
   while the previous card's pieces still hold slots (the Act 2 debug entry
   during the Act 1 card) wipes those slots in scd_objects_reset, and the
   new pieces must still take theirs in the lead update, as they do on the
   host replay (act_test frame 1 object word). */
void scd_title_card_piece(unsigned piece,int alive){
    if(!piece || piece>8)return;
    if(alive)tt_card_pending=1;
    else if(tt_card_slot[piece]){
        unsigned i=tt_card_slot[piece]-1u;tt_card_slot[piece]=0;
        if(pool[i].type==SCD_OBJ_CARD && pool[i].phase!=PPZ_CHECKPOINT_BALL)remove_slot(i);
    }
}
