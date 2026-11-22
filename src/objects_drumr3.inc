/* R3/TRAP_R3.C drumr3. The 18 source table rows are four motion ticks
   each, and motion advances only every tenth game update outside the Past. */
static unsigned drum_frame;
static const int8_t drum_speed[18]={
    1,5,6,8,8,8,6,5,1,-1,-5,-6,-8,-8,-8,-6,-5,-1
};
static const uint8_t drum_height[18]={
    8,8,12,11,11,11,11,8,8,4,4,8,8,8,8,8,8,4
};
static const uint8_t drum_pose[18]={
    0,1,2,3,4,5,6,7,8,9,10,10,10,10,10,10,10,11
};
static const uint8_t drum_priority[12]={5,4,3,2,2,2,3,4,5,6,6,6};
static void drum_cntset(sprite_status *o){
    unsigned phase=o->actfree[17];
    o->actfree[13]=(uint8_t)drum_speed[phase];
    o->sprvsize=drum_height[phase];o->patno=drum_pose[phase];
    o->actfree[16]=4;o->sprpri=drum_priority[o->patno];
}
static void drum_ride(unsigned i){
    sprite_status *o=&actwk[i+1];
    if(!(o->actflg&128))return;
    if(time_flag==0){
        if(o->patno==2)o->sprvsize=8;
        if(o->patno>2 && o->patno<7)o->sprvsize=5;
    }
    cc_ride(i);
}
static void drum_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    if(!o->r_no0){
        o->actflg|=4;o->sprpri=3;o->sprhsize=24;
        scd_word_set(o,27,o->xposi.w.h);scd_word_set(o,26,o->yposi.w.h);
        o->r_no0=2;o->actfree[17]=o->userflag.b.h;
        if(o->userflag.b.h>=2)o->r_no0+=2;
        if(o->userflag.b.h>=6)o->r_no0+=2;
        cc_object_draw(o);return;
    }
    for(;;){
        if(o->r_no0==4)drum_ride(i);
        if(!o->actfree[16]){
            if(o->r_no0!=4)cc_ride_end(i);
            drum_cntset(o);break;
        }
        if(time_flag==0 || drum_frame%10)break;
        o->yspeed.w=(int16_t)scd_word_get(o,29);
        o->yposi.l+=(int32_t)o->yspeed.w*256;
        if(--o->actfree[16])break;
        unsigned phase=++o->actfree[17];
        if(phase<(o->r_no0==2?2u:o->r_no0==4?6u:18u))continue;
        if(o->r_no0==6){
            o->actfree[16]=o->actfree[17]=0;o->r_no0=2;
        }else o->r_no0+=2;
        break;
    }
    cc_object_draw(o);
}
