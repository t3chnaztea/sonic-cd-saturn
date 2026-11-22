/* Tidal Tempest projector, friends and robot generator: R4/MOVIE4.C,
   FRIEND4.C and ET4.C. The originals keep a char* event cursor in
   ((char**)o)[12]; the port keeps its table offset in the slot. */
static unsigned tt_time_flag(void){return current_era==0?1:current_era==1?0:2;}
/* Explosion actors (actno 24, r_no1 1) from the event tables. */
static void tt_blast(int x,int y){
    int c=tt_child(SCD_OBJ_EXPLOSION,0);if(c<0)return;
    pool[c].subtype=4;sprite_status *e=&actwk[c+1];e->r_no1=1;
    e->xposi.w.h=x;e->yposi.w.h=y;pool[c].home_x=x;pool[c].home_y=y;
    soundset(158);
}

/* ---- ET4.C: robot generator -------------------------------------------- */
static void et4_step(unsigned i){
    static const uint8_t p_a[]={3,3,4,5,6,255};
    static const uint8_t *const pchg[]={p_a};
    static const int8_t tbl0[64]={1,0,0,2,-40,-20,3,28,10,4,18,-18,5,-18,-10,6,8,-8,8,-18,14,10,-10,10,
        12,30,-10,15,0,-18,18,20,-10,20,-10,18,22,8,23,25,13,-10,26,23,-22,28,-3,-25,30,10,20,32,-10,2,34,30,-8,35,13,-10,40,-10,10,-1};
    sprite_status *o=&actwk[i+1];
    unsigned tf=tt_time_flag();
    switch(o->r_no0){
    case 0:{
        static const uint16_t sproffsets[3][4]={{1104,1104,0,0},{1104,1104,0,0},{0,0,0,0}};
        o->r_no0+=2;o->actflg|=4;o->sprpri=4;o->sprhs=o->sprhsize=34;o->sprvsize=32;
        o->sproffset=sproffsets[objects_act<3?objects_act:2][tf];pool[i].phase=0;
        tt_set_word(o,26,o->yposi.w.h);tt_set_word(o,23,4);tt_set_word(o,27,1);
        o->patno=(good_future?0:2)+(tf==0);
        if(!good_future && tf==0){o->colino=250;o->yposi.w.h-=16;}
    }   /* fall through: m_init calls m_wait */
    case 2:
        if(good_future || tf!=0)break;
        tt_set_word(o,23,tt_word(o,23)+1);
        if(!(tt_word(o,23)&7))o->yposi.w.h+=tt_word(o,27);
        if(!(tt_word(o,23)&31))tt_set_word(o,27,-tt_word(o,27));
        if(o->colicnt){
            o->colino=o->colicnt=0;tt_set_word(o,23,0);o->patno=7;o->r_no0+=2;
            good_future=pending_generator=1;scd_player_points(1500);
            if(cc_solid(i))frip_release(i);
            break;
        }
        cc_solid(i);tt_patchg(o,pchg);break;
    case 4:{
        unsigned c=pool[i].phase;int t=tbl0[c];
        if(t<0){o->r_no0+=2;o->actfree[0]=8;break;}
        if(++o->actfree[0]==(uint8_t)t){
            pool[i].phase=c+3;tt_blast(o->xposi.w.h+tbl0[c+1],o->yposi.w.h+tbl0[c+2]);
        }
        break;
    }
    case 6:
        if(!--o->actfree[0]){o->r_no0-=6;o->yposi.w.h=tt_word(o,26);soundset(217);}
        break;
    }
    cc_object_draw(o);
    if(o->r_no0<=2)tt_frameout(i,o->xposi.w.h);
}

/* ---- MOVIE4.C: projector and its screens ------------------------------- */
static const uint8_t movie4_pchg00[]={0,2,1,3,1,255};
static const uint8_t movie4_pchg01[]={0,4,4,1,4,4,1,4,4,1,4,4,1,4,4,1,1,4,4,1,1,4,4,1,1,4,4,1,1,5,
    5,1,5,5,1,5,5,1,5,5,1,5,5,1,1,5,5,1,1,5,5,1,1,5,5,1,1,255};
static const uint8_t *const movie4_pchg[]={movie4_pchg00,movie4_pchg01};
static void movie4_die(unsigned i){
    if(pool[i].origin!=65535)consumed[pool[i].origin]=1;
    remove_slot(i);
}
static int movie4_child(unsigned i,unsigned type,int dx,int dy,int8_t sub){
    sprite_status *o=&actwk[i+1];
    int c=tt_child(type,0);if(c<0){movie4_die(i);return 0;}
    sprite_status *s=&actwk[c+1];
    s->xposi.w.h=o->xposi.w.h+dx;s->yposi.w.h=o->yposi.w.h+dy;s->userflag.b.h=sub;pool[c].subtype=(uint8_t)sub;
    tt_set_word(s,33,(uint8_t)(i+1));return 1;
}
static void movie4_step(unsigned i){
    static const int8_t tbl0[37]={1,0,0,5,-18,-10,10,-10,10,15,0,-18,20,-10,18,22,8,23,25,13,-10,28,-3,-25,
        30,10,20,32,-10,2,35,13,-10,40,-10,10,-1};
    sprite_status *o=&actwk[i+1];
    if(o->userflag.b.h){
        unsigned parent=(uint16_t)tt_word(o,33);
        if(actwk[parent].actno!=SCD_OBJ_MOVIE4 || actwk[parent].actfree[21]){remove_slot(i);return;}
        if(!o->r_no0){
            o->r_no0+=2;o->actflg|=4;o->sprpri=4;o->sproffset=944;
            if(o->userflag.b.h&128){o->sprhs=o->sprhsize=8;o->sprvsize=4;o->mstno.b.h=0;}
            else{o->sprhs=o->sprhsize=20;o->sprvsize=24;o->mstno.b.h=1;}
        }
        tt_patchg(o,movie4_pchg);cc_object_draw(o);return;
    }
    switch(o->r_no0){
    case 0:
        if(projector_destroyed){movie4_die(i);return;}
        o->r_no0+=2;o->actflg|=4;o->sprpri=4;o->sprhs=o->sprhsize=o->sprvsize=12;o->colino=251;o->sproffset=944;
        pool[i].phase=0;
        if(!movie4_child(i,SCD_OBJ_MOVIE4,-21,-7,-1) || !movie4_child(i,SCD_OBJ_MOVIE4,-88,-4,1) ||
           !movie4_child(i,SCD_OBJ_FRIEND4,-76,-28,-128) || !movie4_child(i,SCD_OBJ_FRIEND4,-84,-17,-127))return;
        break;
    case 2:
        if(o->colicnt){o->colino=o->colicnt=0;o->r_no0+=2;}
        cc_solid(i);break;
    case 4:
        o->r_no0+=2;o->patno=1;o->actfree[21]=255;
        if(cc_solid(i))frip_release(i);
        break;
    case 6:{
        unsigned c=pool[i].phase;int t=tbl0[c];
        if(t>=0){
            tt_set_word(o,23,(uint16_t)tt_word(o,23)+256);
            if((uint8_t)((uint16_t)tt_word(o,23)>>8)==t){
                pool[i].phase=c+3;tt_blast(o->xposi.w.h+tbl0[c+1],o->yposi.w.h+tbl0[c+2]);
            }
        }else{o->r_no0+=2;tt_set_word(o,23,60);}
        break;
    }
    case 8:
        tt_set_word(o,23,tt_word(o,23)-1);
        if(!tt_word(o,23)){projector_destroyed=1;projector_flag=255;movie4_die(i);return;}
        break;
    }
    cc_object_draw(o);
    if(o->r_no0<=2)tt_frameout(i,o->xposi.w.h);
}

/* ---- FRIEND4.C: freed animals ------------------------------------------ */
static void friend4_step(unsigned i){
    static const uint8_t pchg0[]={0,0,0,2,0,0,2,1,1,2,1,1,2,0,0,2,2,0,0,2,2,1,1,2,2,1,1,2,2,255},pchg1[]={19,0,1,255};
    static const uint8_t *const pchg[]={pchg0,pchg1};
    sprite_status *o=&actwk[i+1];
    /* SUICIDE.C friend_suicide. */
    if(!(o->userflag.b.h&128)){
        if(tt_time_flag()<2){if(!projector_destroyed){tt_frameout(i,o->xposi.w.h);return;}}
        /* SUICIDE.C frameout keeps ACTSET's loaded bit: gone for the act. */
        else if(!good_future){if(pool[i].origin!=65535)consumed[pool[i].origin]=1;remove_slot(i);return;}
    }
    if(o->r_no0&128){
        unsigned parent=(uint16_t)tt_word(o,33);
        if(actwk[parent].actno!=SCD_OBJ_MOVIE4 || actwk[parent].actfree[21]){remove_slot(i);return;}
        short sn,cs;sinset(o->actfree[7],&sn,&cs);
        int16_t dx=(int16_t)((((int32_t)((uint32_t)(uint16_t)cs<<16)>>3)+32768)>>16);
        int16_t dy=(int16_t)((((int32_t)((uint32_t)(uint16_t)sn<<16)>>4)+32768)>>16);
        o->xposi.w.h=tt_word(o,30)+dx;o->yposi.w.h=tt_word(o,25)+dy;
        tt_set_long(o,13,tt_long(o,13)+tt_long(o,14));
        if(!(tt_long(o,13)&32767)){o->actflg^=1;o->cddat^=1;o->sprpri=o->sprpri!=5?5:3;}
        tt_patchg(o,pchg);cc_object_draw(o);return;
    }
    if(o->r_no0){
        o->xposi.l+=tt_free_long(o,0);
        short sn,cs;sinset(o->actfree[7],&sn,&cs);
        int16_t dy=(int16_t)((((int32_t)((uint32_t)(uint16_t)sn<<16)>>3)+32768)>>16);
        o->yposi.w.h=tt_word(o,25)+dy;
        tt_set_long(o,13,tt_long(o,13)+tt_long(o,14));
        if(tt_long(o,13)<0 || tt_long(o,13)>=65536){
            tt_set_long(o,14,-tt_long(o,14));tt_set_free_long(o,0,-tt_free_long(o,0));o->actflg^=1;o->cddat^=1;
        }
        tt_patchg(o,pchg);cc_object_draw(o);tt_frameout(i,o->xposi.w.h);return;
    }
    static const uint16_t tbl0sproffset[11]={1104,1104,1104,0,1104,1104,1104,0,0,0,1104};
    o->actflg|=4;o->sprpri=5;o->sprhs=o->sprhsize=8;o->sprvsize=12;
    /* ((act<<2)+time_flag)<<1 overruns the 11 entries for Act 2 Future
       and Act 3; the PC read past the table. */
    unsigned index=(((objects_act&255)<<2)+tt_time_flag())<<1;
    o->sproffset=index<11?tbl0sproffset[index]:0;
    if(o->userflag.b.h&1)o->sproffset+=8192;
    tt_set_word(o,25,o->yposi.w.h);
    if(o->userflag.b.h&128){
        o->r_no0-=2;o->actflg^=1;o->cddat^=1;tt_set_word(o,30,o->xposi.w.h);tt_set_long(o,14,512);
        if(o->userflag.b.h&1){o->actflg^=1;o->cddat^=1;tt_set_long(o,14,-tt_long(o,14));tt_set_long(o,13,12288);}
    }else{
        o->r_no0+=2;o->mstno.b.h=1;tt_set_free_long(o,0,65536);tt_set_long(o,14,256);
    }
}
