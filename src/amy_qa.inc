/* Cross-target Amy checks use original coordinates and independent frozen
   reference hashes; source data is separately parsed by amy_reference.py. */
static unsigned amy_giggles;
static void amy_audio(short sound){if(sound==183)amy_giggles++;}
static uint32_t amy_hash(uint32_t hash,const uint32_t *words,unsigned n){
    for(unsigned i=0;i<n;i++){hash^=words[i];hash*=16777619u;}return hash;
}
static int amy_ready(void){
    init(0);scd_player_place(9682,488,0,0,0);
    if(scd_objects_spawn(SCD_OBJ_AMY,9664,488,0,0)!=0)return 0;
    scd_objects_step(9682,488);
    actwk[0].yposi.w.h=actwk[1].yposi.w.h;actwk[1].xspeed.w=-16;
    return actwk[1].r_no0==2;
}
static int __attribute__((noinline)) amy_probe(void){
    for(unsigned fractional=0;fractional<2;fractional++){
        init(0);CHECK(scd_objects_spawn(SCD_OBJ_AMY_HEART,500,400,0,0)==0);
        if(fractional){actwk[1].xposi.w.l=0x1234;actwk[1].yposi.w.l=0x5678;}
        uint32_t h=2166136261u;
        for(unsigned tick=1;tick<=120;tick++){
            scd_objects_step(80,488);sprite_status *o=&actwk[1];
            uint32_t words[]={(uint32_t)o->xposi.l,(uint32_t)o->yposi.l,(uint16_t)o->xspeed.w,(uint16_t)o->yspeed.w,o->patno,o->actfree[0],o->actfree[1],!!o->actno};
            h=amy_hash(h,words,8);
            if(tick<120)CHECK(view(SCD_OBJ_AMY_HEART).frame==(tick<20?8:tick<110?9:10));
        }
        CHECK(h==(fractional?1824742068u:86686320u));CHECK(!scd_objects_get().active);
    }
    /* Distant initialization stays active, aligns to floor and emits carry
       events even when allocation fails. */
    init(0);scd_player_place(9480,488,0,0,0);CHECK(scd_objects_spawn(SCD_OBJ_AMY,9664,488,0,0)==0);
    uint32_t h=2166136261u;unsigned emits=0;
    for(unsigned tick=1;tick<=600;tick++){
        scd_objects_step(9480,488);sprite_status *o=&actwk[1];
        uint32_t words[]={o->mstno.b.h,o->patno,o->patcnt,(uint8_t)o->pattim};h=amy_hash(h,words,4);
        CHECK(o->r_no0==0 && scd_objects_amy_palette(NULL));
        if(tick<=256){unsigned expected=(tick*6)/256;CHECK(scd_objects_get().amy_hearts==expected);emits=expected;}
    }
    CHECK(h==401554217u && emits==6);
    uint16_t colors[16];CHECK(scd_objects_amy_palette(colors));
    scd_objects_clear_live();CHECK(!scd_objects_amy_palette(NULL));
    /* Original animation 1, 2 and holding animation 3 have separate scripts
       and independent 600-update fingerprints. */
    for(unsigned animation=1;animation<=3;animation++){
        CHECK(amy_ready());amy_giggles=0;scd_player_audio_set(amy_audio);
        if(animation==3){scd_objects_step(9682,488);CHECK(actwk[1].r_no0==4 && amy_giggles==1 && !(actwk[0].actfree[2]&1));}
        h=2166136261u;
        for(unsigned tick=0;tick<600;tick++){
            if(animation==1){actwk[0].xposi.w.h=actwk[1].xposi.w.h;actwk[0].xspeed.w=0;}
            if(animation==2){actwk[1].xposi.w.h=9664;actwk[1].xspeed.w=-16;actwk[0].xposi.w.h=9682;debugflag.w=1;}
            scd_objects_step(actwk[0].xposi.w.h,actwk[0].yposi.w.h);sprite_status *o=&actwk[1];
            uint32_t words[]={o->mstno.b.h,o->patno,o->patcnt,(uint8_t)o->pattim};h=amy_hash(h,words,4);
        }
        debugflag.w=0;CHECK(h==(animation==1?3022303949u:animation==2?1767625934u:3614301989u));
        if(animation==3){CHECK(actwk[0].actfree[2]&1);CHECK(scd_objects_get().amy_hearts==37);CHECK(amy_giggles==1);}
    }
    CHECK(amy_ready());h=2166136261u;
    for(unsigned tick=0;tick<600;tick++){
        actwk[1].xposi.w.h=9810;actwk[0].xposi.w.h=9910;actwk[1].actfree[0]=128;actwk[1].actfree[1]=3;
        scd_objects_step(9910,488);sprite_status *o=&actwk[1];
        uint32_t words[]={o->mstno.b.h,o->patno,o->patcnt,(uint8_t)o->pattim};h=amy_hash(h,words,4);
    }
    CHECK(h==1650632269u);
    /* Grab box is [12,24) in Sonic's facing direction and [-8,8) in Y. */
    for(unsigned flip=0;flip<2;flip++)for(int dx=11;dx<=24;dx++)for(int dy=-9;dy<=8;dy++){
        CHECK(amy_ready());actwk[0].cddat=flip;
        actwk[0].xposi.w.h=9664+(flip?-dx:dx);actwk[0].yposi.w.h=actwk[1].yposi.w.h+dy;
        actwk[1].xspeed.w=flip?16:-16;scd_objects_step(9664,488);
        CHECK((actwk[1].r_no0==4)==(dx>=12 && dx<24 && dy>=-8 && dy<8));
    }
    for(unsigned excluded=0;excluded<10;excluded++){
        CHECK(amy_ready());sprite_status *p=&actwk[0];
        if(excluded==0)p->cddat|=2;
        if(excluded==1)p->cddat|=4;
        if(excluded==2)scd_word_set(p,26,1);
        if(excluded==3)p->xspeed.w=1664;
        if(excluded==4)p->xspeed.w=-1664;
        if(excluded==5)plpower_b=1;
        if(excluded==6)plpower_m=1;
        if(excluded==7)scd_objects_travel_protection(1);
        if(excluded==8)debugflag.w=1;
        if(excluded==9)p->r_no0=4;
        scd_objects_step(9682,488);CHECK(actwk[1].r_no0==(excluded==8?2:6));
        debugflag.w=0;plpower_m=0;scd_objects_travel_protection(0);
    }
    /* Fresh jump releases all source control bits, retains fractions and
       applies the source impulse without a synthetic second sound. */
    for(unsigned flip=0;flip<2;flip++){
        CHECK(amy_ready());scd_objects_step(9682,488);scd_objects_step(9682,488);
        CHECK(actwk[0].actfree[2]&1);actwk[0].cddat=flip;actwk[0].xposi.w.l=0x1234;actwk[0].yposi.w.l=0x5678;
        int old_y=actwk[0].yposi.w.h;swdata.b.l=SCD_JUMP;scd_objects_step(9682,488);swdata.b.l=0;
        CHECK(!actwk[0].actfree[2] && actwk[0].yspeed.w==-1664 && actwk[0].sprvsize==14 && actwk[0].sprhs==7);
        CHECK(actwk[0].yposi.w.h==old_y+5 && actwk[0].xposi.w.l==0x1234 && actwk[0].yposi.w.l==0x5678);
        CHECK((actwk[0].cddat&6)==6 && actwk[1].r_no0==6);
        actwk[1].yposi.w.h=100;int amy_y=actwk[1].yposi.l;scd_objects_step(9682,488);
        CHECK(actwk[1].r_no0==8 && actwk[1].yspeed.w==-704 && actwk[1].yposi.l==amy_y-768*256);
    }
    CHECK(amy_ready());scd_objects_step(9682,488);scd_objects_step(9682,488);
    for(unsigned tick=0;tick<600;tick++){
        scd_objects_amy_idle_step();
        unsigned cursor=tick/24;unsigned source=cursor<12?1:cursor==12?3:cursor<16?2:((cursor-16)%2?4:3);
        CHECK(scd_objects_amy_idle_frame()==(int)source-1);
    }
    /* Nine-minute-fifty forced release, with the normal player clock. */
    CHECK(amy_ready());scd_objects_step(9682,488);scd_objects_step(9682,488);
    for(unsigned tick=1;tick<=590*60;tick++){
        scd_world_probe_iteration=tick;scd_player_step(0);CHECK(qa_player()->elapsed==tick);
        if(tick<590*60)CHECK(actwk[0].actfree[2]&1);
    }
    CHECK(!actwk[0].actfree[2] && actwk[0].yspeed.w==-1664 && actwk[1].r_no0==2);
    /* Carry is spent even when the actor pool is full. A later free slot
       must wait for the next carry, not emit a deferred heart immediately. */
    init(0);scd_player_place(9480,488,0,0,0);CHECK(scd_objects_spawn(SCD_OBJ_AMY,9664,488,0,0)==0);
    for(unsigned n=1;n<96;n++)CHECK(scd_objects_spawn(SCD_OBJ_RING,500,400,0,0)==(int)n);
    for(unsigned tick=0;tick<256;tick++)scd_objects_step(9480,488);
    CHECK(!scd_objects_get().amy_hearts && scd_objects_get().dropped==6 && !actwk[1].actfree[3]);
    actwk[2].xposi.w.h=9480;actwk[2].yposi.w.h=488;scd_objects_step(9480,488);
    CHECK(actwk[2].actno==SCD_OBJ_RING && !scd_objects_get().amy_hearts);
    for(unsigned tick=258;tick<299;tick++){scd_objects_step(9480,488);CHECK(!scd_objects_get().amy_hearts);}
    CHECK(!actwk[2].actno);
    scd_objects_step(9480,488);CHECK(scd_objects_get().amy_hearts==1 && actwk[2].actno==SCD_OBJ_AMY_HEART);
    /* Ownership exits cannot strand Sonic. Hearts have no parent and survive
       Amy's streaming deletion until their own lifetime/despawn. */
    for(unsigned cleanup=0;cleanup<5;cleanup++){
        CHECK(amy_ready());scd_objects_step(9682,488);scd_objects_step(9682,488);
        CHECK(actwk[0].actfree[2]&1);
        if(cleanup==0)scd_objects_release_control();
        if(cleanup==1){scd_player_inventory(5,0);scd_objects_hurt(9664);}
        if(cleanup==2)scd_objects_clear_live();
        if(cleanup==3){debugflag.w=1;scd_objects_step(9682,488);debugflag.w=0;}
        if(cleanup==4)scd_objects_change_era(1);
        CHECK(!(actwk[0].actfree[2]&1) && scd_objects_amy_idle_frame()<0);
    }
    init(0);scd_objects_reset(0,1);scd_player_place(9480,100,0,0,2);scd_act_camera(9320,0);scd_objects_step(9480,100); /* the retail spawner streams by the camera */
    CHECK(scd_objects_amy_palette(NULL));
    CHECK(scd_objects_spawn(SCD_OBJ_AMY_HEART,9600,400,0,0)>=0);
    scd_player_place(9020,100,0,0,2);scd_act_camera(8860,0);scd_objects_step(9020,100);
    CHECK(!scd_objects_amy_palette(NULL));unsigned surviving=0;
    for(unsigned n=1;n<=96;n++){CHECK(actwk[n].actno!=SCD_OBJ_AMY);if(actwk[n].actno==SCD_OBJ_AMY_HEART)surviving++;}
    CHECK(surviving>=1);
    scd_player_place(9480,100,0,0,2);scd_act_camera(9320,0);scd_objects_step(9480,100);CHECK(scd_objects_amy_palette(NULL));
    CHECK(amy_ready());ta_flag=1;scd_objects_step(9682,488);
    scd_object_view hidden[96];CHECK(!scd_objects_views(hidden,96) && actwk[1].actno==SCD_OBJ_AMY && !scd_objects_amy_palette(NULL));ta_flag=0;
    init(1);CHECK(scd_objects_spawn(SCD_OBJ_AMY,9664,488,0,0)<0);
    init(0);CHECK(scd_objects_spawn(SCD_OBJ_AMY,9664,488,1,0)<0);
    CHECK(scd_objects_spawn(SCD_OBJ_AMY,500,0,0,0)==0);scd_objects_step(80,488);CHECK(!scd_objects_amy_palette(NULL) || actwk[1].yposi.w.h>=0);
    scd_objects_clear_live();scd_player_audio_set(NULL);CHECK(!qa_error);return 0;
}
