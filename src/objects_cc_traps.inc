/* Collision Chaos TRAP_R3.C: harir3, frdr3, trapdr3 and getdair3.
   Included after pool, spawn_from/remove_slot declarations and CC rider helpers.
   Parent links use actor indices, not slot indices. */
static void cc_hit_clear(unsigned i){if(actwk[0].colino!=i+1)actwk[0].colino=0;}
static void cc_hit_set(unsigned i){
    sprite_status *o=&actwk[i+1],*p=actwk;
    unsigned other=p->colino;
    if(other){
        if(other==i+1)return;
        sprite_status *q=&actwk[other];
        if(!o->xspeed.w && !q->xspeed.w)return;
        if(p->xposi.w.h>=o->xposi.w.h && p->xposi.w.h>=q->xposi.w.h)return;
        playdieset(p);return;
    }
    p->colino=i+1;
}
static void cc_side_terrain(sprite_status *o){
    if(!o->xspeed.w)return;
    char direction=o->xspeed.w<0?64:-64;
    if(dircol(actwk,&direction)<0)playdieset(actwk);
}
/* RIDECHK.C hitchk for ordinary full solids. The numeric actor exceptions
   in the original apply to springs, monitors and other rounds, not these
   four CC trap families. Top-only getdair3 uses cc_ride instead. */
static int cc_solid(unsigned i){
    sprite_status *o=&actwk[i+1],*p=actwk;
    if(p->mstno.b.h==23 || (p->actfree[2]&64) || p->r_no0>=6 || !p->actno ||
       !(o->actflg&128) || editmode.b.h)return cc_ride_end(i);
    int width=o->sprhsize+10,dx=(int16_t)(p->xposi.w.h-o->xposi.w.h+width);
    if(dx<0 || dx>=width*2 || (p->mstno.b.h==43 && !(o->cddat&8)))return cc_ride_end(i);
    int height=o->sprvsize+p->sprvsize+2,dy=(int16_t)(p->yposi.w.h-o->yposi.w.h+height);
    if(dy<0 || dy>=height*2)return cc_ride_end(i);
    int depth_x=dx,depth_y=dy;
    if(dx>width){dx-=width*2;depth_x=-dx;}
    if(dy>height){dy-=height*2;depth_y=-dy;}
    if(depth_y>=depth_x){
        if(depth_y<5)return cc_ride_end(i);
        cc_hit_set(i);frip_release(i);o->r_no1=0;p->xposi.w.h-=dx;
        if(dx>=0?p->xspeed.w>0:p->xspeed.w<0){
            cc_side_terrain(o);
            if(!(p->cddat&2)){o->cddat|=32;p->cddat|=32;p->mspeed.w=0;}
            p->xspeed.w=0;
        }else{cc_hit_clear(i);cc_side_terrain(o);o->cddat&=~32;p->cddat&=~32;}
        return 0;
    }
    if(dy<0){
        if(!(p->cddat&2) && o->yspeed.w>0)playdieset(p);
        p->yposi.w.h-=dy;p->yspeed.w=0;cc_hit_clear(i);frip_release(i);o->r_no1=0;return 1;
    }
    if(p->mstno.b.h!=43 && p->yspeed.w<0)return cc_ride_end(i);
    p->yposi.w.h=o->yposi.w.h-o->sprvsize-p->sprvsize;
    p->xposi.l+=(int32_t)o->xspeed.w*256;
    if(o->xspeed.w){
        char direction=o->xspeed.w<0?64:-64;short distance=dircolm(p,&direction);
        if(distance<0)p->xposi.w.h+=o->xspeed.w<0?-distance:distance;
    }
    p->yposi.l+=(int32_t)o->yspeed.w*256;
    if(o->yspeed.w>=0){
        short d0,d1,d3,distance=dircol_d(p,&d0,&d1,&d3);
        if(distance<0){p->yposi.w.h+=distance;return cc_ride_end(i);}
    }else if(dircol_u2(p)<0){playdieset(p);return cc_ride_end(i);}
    frip_stand(i);return 1;
}
static int cc_trap_parent(unsigned type){return type==SCD_OBJ_FRDR3 || type==SCD_OBJ_TRAPDR3;}
static int cc_trap_child(unsigned i,unsigned type,unsigned sub,int dx,int dy){
    sprite_status *o=&actwk[i+1];
    /* actwkchk2 searches after the parent, preserving same-tick dispatch. */
    int child=spawn_from(type,o->xposi.w.h,o->yposi.w.h,sub,0,i+1);
    if(child<0)return -1;
    sprite_status *c=&actwk[child+1];pool[child].parent=i+1;
    c->actfree[14]=dx;c->actfree[15]=dy;scd_word_set(c,28,i+1);
    return child;
}
static void harir3_motion(sprite_status *o){
    if(!((uint8_t)o->userflag.b.h&4))return;
    if(o->actfree[16]){
        if(--o->actfree[16])goto position;
        if(o->actflg&128)soundset(183);
    }
    if(o->actfree[18]){
        o->actfree[17]-=8;
        if((int8_t)o->actfree[17]<0){o->actfree[17]=o->actfree[18]=0;o->actfree[16]=60;}
    }else{
        o->actfree[17]+=8;
        if(o->actfree[17]>=32){o->actfree[17]=32;o->actfree[18]=1;o->actfree[16]=60;}
    }
position:
    switch(o->userflag.b.h&3){
    case 0:o->yposi.w.h=cc_word(o,27)+o->actfree[17];break;
    case 1:o->yposi.w.h=cc_word(o,27)-o->actfree[17];break;
    case 2:o->xposi.w.h=cc_word(o,29)-o->actfree[17];break;
    case 3:o->xposi.w.h=cc_word(o,29)+o->actfree[17];break;
    }
}
/* COLI3.C pcol's spike touch. Index 2 is 16x12, index 3 is 12x16; patno 57
   has the original reduced player box. pcol runs in Sonic's update, before
   RunObjects, so cc_scan calls this: a hurt's lost-ring actor then inits and
   moves in that same object pass (retail CC2C seed 24 update 3239: every
   lost ring has taken its first step). */
static int harir3_touch(unsigned i){
    sprite_status *o=&actwk[i+1],*p=actwk;
    if(!o->colino || !(o->actflg&128) || p->r_no0>=4 || (p->actfree[2]&64))return 0;
    int radius=p->sprvsize-3,top=p->yposi.w.h-radius,ph=radius*2;
    if(p->patno==57){top+=12;ph=20;}
    int hw=o->colino==130?16:12,hh=o->colino==130?12:16;
    if(o->xposi.w.h+hw<p->xposi.w.h-8 || o->xposi.w.h-hw>p->xposi.w.h+8 ||
       o->yposi.w.h+hh<top || o->yposi.w.h-hh>top+ph)return 0;
    scd_objects_hurt(o->xposi.w.h);return 1;
}
static void harir3_step(unsigned i){
    sprite_status *o=&actwk[i+1],*p=actwk;
    if(!o->r_no0){
        static const uint8_t sizes[4][3]={{16,8,0},{18,12,131},{12,16,130},{12,16,130}};
        o->r_no0=2;o->actflg|=4;o->sprpri=3;
        scd_word_set(o,29,o->xposi.w.h);scd_word_set(o,27,o->yposi.w.h);
        o->patno=o->userflag.b.h&3;o->sprhsize=sizes[o->patno][0];o->sprvsize=sizes[o->patno][1];o->colino=sizes[o->patno][2];
    }
    harir3_motion(o);
    int contact=cc_solid(i);
    if(!o->patno && contact && (o->cddat&8) && !plpower_a && !plpower_m && p->r_no0<4 && !scd_word_get(p,26)){
        p->yposi.l-=(int32_t)p->yspeed.w*256;scd_objects_hurt(o->xposi.w.h);
    }
    if(pool[i].parent){
        sprite_status *parent=&actwk[pool[i].parent];
        o->xposi.w.h=parent->xposi.w.h+o->actfree[14];o->yposi.w.h=parent->yposi.w.h+o->actfree[15];
    }
}
static void frdr3_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    if(!o->r_no0){
        o->r_no0=2;o->actflg|=4;o->sprpri=3;o->sprhsize=o->sprvsize=16;
        scd_word_set(o,27,o->xposi.w.h);scd_word_set(o,26,o->yposi.w.h);
        if(o->userflag.b.h>=2 && cc_trap_child(i,SCD_OBJ_SPRING,(o->userflag.b.h&1)<<1,0,-22)<0){
            if(pool[i].origin!=65535)deferred_reload[pool[i].origin]=1;
            remove_slot(i);return;
        }
    }
    cc_solid(i);
    if(current_era==1 || o->userflag.b.h==1)return;
    for(;;){
        if(!o->actfree[16]){
            static const int16_t velocity[]={512,0,-512,0};
            o->actfree[16]=64;scd_word_set(o,30,o->actfree[17]<2?-8:8);
            scd_word_set(o,29,velocity[o->actfree[17]]);return;
        }
        scd_word_set(o,29,cc_word(o,29)+cc_word(o,30));o->xspeed.w=cc_word(o,29);o->xposi.l+=(int32_t)o->xspeed.w*256;
        if(--o->actfree[16])return;
        o->actfree[17]=(o->actfree[17]+1)&3;
    }
}
static void trapdr3_step(unsigned i){
    sprite_status *o=&actwk[i+1];unsigned sub=(uint8_t)o->userflag.b.h;
    if(!o->r_no0){
        o->actflg|=4;o->sprpri=3;o->patno=sub>>2;o->sprhsize=16;o->sprvsize=14;
        scd_word_set(o,29,o->xposi.w.h);scd_word_set(o,27,o->yposi.w.h);o->r_no0=2;
        if((sub&3)==1)cc_trap_child(i,SCD_OBJ_HARIR3,2,32,0);
        else if(sub&3)cc_trap_child(i,SCD_OBJ_SPRING,((sub&1)<<1)|4,24,0);
    }
    int dx=(int16_t)(actwk[0].xposi.w.h-(o->xposi.w.h-o->sprhsize));
    if(dx<0){o->actfree[17]+=8;if(o->actfree[17]>=32)o->actfree[17]=32;}
    else if(dx>=80){o->actfree[17]-=8;if((int8_t)o->actfree[17]<0)o->actfree[17]=0;}
    o->yposi.w.h=cc_word(o,27)+((sub&4)?-(int)o->actfree[17]:o->actfree[17]);cc_solid(i);
}
static void getdair3_step(unsigned i){
    sprite_status *o=&actwk[i+1];unsigned sub=(uint8_t)o->userflag.b.h;
    if(!o->r_no0){
        o->actflg|=4;o->sprpri=3;o->sprhsize=28;o->sprvsize=8;
        scd_word_set(o,29,o->xposi.w.h);scd_word_set(o,27,o->yposi.w.h);
        o->actfree[16]=(sub&15)*30;o->r_no0=2;
    }
    if(actwk[0].yposi.w.h<o->yposi.w.h){
        o->actfree[17]-=16;
        if((int8_t)o->actfree[17]<0){
            o->actfree[17]=0;
            if(!(sub&15) && !o->actfree[18]){o->actfree[16]=60;o->actfree[18]=255;}
        }
    }else{
        o->actfree[17]+=16;if(o->actfree[17]>=64){o->actfree[17]=64;o->actfree[16]=8;}
    }
    o->xposi.w.h=cc_word(o,29)+((sub&128)?o->actfree[17]:-(int)o->actfree[17]);cc_ride(i);
}

/* TRAP_R3.C gandair3: stationary base, retracting core and two bullets.
   actwkchk (unlike the earlier traps' actwkchk2) searches every free slot. */
static void gandair3_patchg(sprite_status *o){
    static const uint8_t scripts[5][6]={{2,1,2,255},{2,3,5,255},{2,4,5,255},
                                      {0,3,6,5,6,255},{0,4,6,5,6,255}};
    if(o->mstno.b.h!=o->mstno.b.l){o->mstno.b.l=o->mstno.b.h;o->patcnt=o->pattim=0;}
    if((int8_t)--o->pattim>=0)return;
    const uint8_t *script=scripts[(int)o->mstno.b.h];
    /* Sega CD AnimateObject copies the delay byte unchanged. The PC
       reconstruction's zero-to-one clamp would halve the bullet flash rate.
       All ten original CC programs are checked by cc_gandair_source.py. */
    o->pattim=script[0];
    unsigned pat=script[o->patcnt+1];
    if(pat==255){o->patcnt=0;pat=script[1];}
    o->patno=pat&31;o->actflg=(o->actflg&~3)|(((pat>>5)^o->cddat)&3);o->patcnt++;
}
static int gandair3_fires(void){return current_era==0 || (current_era>=2 && !good_future);}
static void gandair3_bullets(sprite_status *o){
    if(!gandair3_fires())return;
    for(unsigned side=0;side<2;side++){
        int child=spawn_from(SCD_OBJ_GANDAIR3,o->xposi.w.h+(side?24:-24),o->yposi.w.h+8,2,0,0);
        if(child>=0)actwk[child+1].actfree[16]=side;
    }
}
static void gandair3_step(unsigned i){
    sprite_status *o=&actwk[i+1],*p=actwk;
    unsigned sub=(uint8_t)o->userflag.b.h;
    if(sub==0){
        if(!o->r_no0){
            o->actflg|=4;o->sprpri=2;o->sprhsize=16;
            scd_word_set(o,29,o->xposi.w.h);scd_word_set(o,27,o->yposi.w.h);
            int child=spawn_from(SCD_OBJ_GANDAIR3,o->xposi.w.h,o->yposi.w.h+8,1,0,0);
            if(child<0)return; /* Retry next update; original leaves base alive. */
            pool[child].parent=i+1;o->r_no0=2;
        }
        return;
    }
    if(sub==2){
        if(o->colino && (o->actflg&128) && p->r_no0<4 && !(p->actfree[2]&64)){
            int radius=p->sprvsize-3,top=p->yposi.w.h-radius,ph=radius*2;
            if(p->patno==57){top+=12;ph=20;}
            if(o->xposi.w.h+4>=p->xposi.w.h-8 && o->xposi.w.h-4<=p->xposi.w.h+8 &&
               o->yposi.w.h+4>=top && o->yposi.w.h-4<=top+ph)scd_objects_hurt(o->xposi.w.h);
        }
        if(!o->r_no0){
            o->actflg|=4;o->sprpri=4;o->colino=152;scd_word_set(o,29,o->xposi.w.h);
            o->xspeed.w=o->actfree[16]?256:-256;scd_word_set(o,33,o->actfree[16]?16:-16);
            o->mstno.b.h=o->actfree[16]?2:1;o->r_no0=2;gandair3_patchg(o);
        }
        o->xspeed.w+=cc_word(o,33);o->xposi.l+=(int32_t)o->xspeed.w*256;gandair3_patchg(o);
        int dx=(int16_t)(o->xposi.w.h-cc_word(o,29));if(dx<0)dx=-dx;
        if(dx>=64){
            o->colino=0;
            if(!o->actfree[17]){o->mstno.b.h+=2;o->actfree[17]=30;}
            if(!--o->actfree[17]){remove_slot(i);return;}
        }
        return;
    }
    switch(o->r_no0){
    case 0:
        o->actflg|=4;o->sprpri=3;o->sprhsize=16;o->sprvsize=20;
        scd_word_set(o,29,o->xposi.w.h);scd_word_set(o,27,o->yposi.w.h);
        o->patno=1;o->r_no0=2;return;
    case 2:
        if(!o->actfree[16]){
            int dx=(int16_t)(o->xposi.w.h-p->xposi.w.h);if(dx<0)dx=-dx;
            if(dx>=120)break;
            o->actfree[16]=60;
        }
        if(--o->actfree[16]){if(gandair3_fires())gandair3_patchg(o);break;}
        o->actfree[16]=o->actfree[17]=0;o->patno=1;o->r_no0=4;return;
    case 4:
        o->actfree[17]+=8;if(o->actfree[17]>=32)o->actfree[17]=32;
        o->yposi.w.h=cc_word(o,27)-o->actfree[17];
        if(o->actfree[17]!=32)break;
        gandair3_bullets(o);
        if(!cc_solid(i)){o->actfree[16]=8;o->r_no0=6;return;}
        p->yspeed.w=-1792;p->cddat=(p->cddat|2)&~8;p->mstno.b.h=16;o->cddat&=~8;return;
    case 6:
        if(o->actfree[16]){--o->actfree[16];break;}
        o->actfree[17]-=4;if((int8_t)o->actfree[17]<0)o->actfree[16]=0;
        o->yposi.w.h=cc_word(o,27)-o->actfree[17];
        if(!o->actfree[17]){o->actfree[16]=60;o->r_no0=8;}
        break;
    case 8:
        if(!o->actfree[16]){o->r_no0=2;return;}
        --o->actfree[16];break;
    }
    cc_solid(i);
}
