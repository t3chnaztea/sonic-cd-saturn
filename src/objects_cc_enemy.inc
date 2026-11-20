/* COLI3.C enemy/hazard contact and SUICIDE.C, shared by native CC enemies. */
/* ACTION.C's viewport bounds. Called where the original submits DrawObject;
   the next collision/AI update observes this draw's visibility bit. */
static void cc_object_draw(sprite_status *o){
    o->actflg&=127;
    int16_t x=o->xposi.w.h-scd_act_view_x(),y=o->yposi.w.h;
    int cy=scd_act_view_y();
    if(x+o->sprhsize<0 || x-o->sprhsize>=320)return;
    if((uint16_t)cy<256){if((uint16_t)y>=2048)y-=2048;}
    else if((uint16_t)cy>=1792 && (uint16_t)y<256)y+=2048;
    y-=cy;if(y+o->sprvsize<0 || y-o->sprvsize>=224)return;
    o->actflg|=128;
}
/* Pool phase of a badnik's explosion: it alone makes points and then a flower
   (src/objects_tt_enemies.inc tt_bakuha_step). */
enum{CC_BADNIK_BOOM=0x4342};
static int cc_enemy_contact(unsigned i){
    sprite_status *o=&actwk[i+1],*p=actwk;
    if(!o->colino || !(o->actflg&128) || p->r_no0>=4 || (p->actfree[2]&64))return 0;
    int hw,hh;
    switch(o->colino){
    case 6:case 134:hw=hh=16;break; /* colitbl[(colino&63)-1]; 134: MECASNC.C hari3x */
    case 37:hw=8;hh=12;break;
    case 38:hw=16;hh=8;break;
    case 139:hw=hh=8;break;
    case 135:hw=hh=6;break;
    case 231:hw=32;hh=16;break;
    case 250:hw=40;hh=36;break;
    default:return 0;
    }
    int radius=(int)p->sprvsize-3,left=p->xposi.w.h-8,top=p->yposi.w.h-radius,height=radius*2;
    if(p->patno==57){top+=12;height=20;}
    if(o->xposi.w.h+hw<left || o->xposi.w.h-hw>left+16 ||
       o->yposi.w.h+hh<top || o->yposi.w.h-hh>top+height)return 0;
    if(o->colino==250){if(p->mstno.b.h==2)o->colicnt++;return 1;}
    if(o->colino==231){o->colicnt++;return 1;}
    if(o->colino&128){scd_objects_hurt(o->xposi.w.h);return 1;}
    /* COLI3.C tests animation 2, not just the rolling flag. Invulnerability
       to damage does not prevent an attacking player from defeating an enemy. */
    if(!plpower_a && !plpower_m && !travel_protection && p->mstno.b.h!=2){scd_objects_hurt(o->xposi.w.h);return 1;}
    if(o->colicnt){
        /* COLI3.C:339-342 negates then halves; the Sega CD halves with asr.w
           (rounds down): retail CC3C seq 1275 xspeed 927 -> -464, not -463. */
        p->xspeed.w=(int16_t)((int16_t)-p->xspeed.w>>1);p->yspeed.w=(int16_t)((int16_t)-p->yspeed.w>>1);
        o->colino=0;if(!--o->colicnt)o->cddat|=128;return 1;
    }
    static const unsigned points[]={100,200,500,1000};
    /* COLI3.C: escoretbl[min(emyscorecnt,6)/2], 1000 (x10) from emyscorecnt 32. */
    unsigned chain=(unsigned short)emyscorecnt;emyscorecnt+=2;
    /* Word 33 = score index for the explosion's points popup (Explosion/Main.asm
       ObjExplosion_MakePoints oVar3E; TT's pcolnomal does the same). */
    scd_word_set(o,33,emyscorecnt>=32?10:(chain>=6?6:chain));
    scd_player_points(emyscorecnt>=32?10000:points[(chain>=6?6:chain)/2]);
    stats.defeated++;soundset(150);
    short before_vx=p->xspeed.w,before_vy=p->yspeed.w;
    if(p->yspeed.w<0)p->yspeed.w+=256;
    else if(p->yposi.w.h<o->yposi.w.h)p->yspeed.w=-p->yspeed.w;
    else p->yspeed.w-=256;
    scd_plus_enemy_defeat(i+1,before_vx,before_vy);
    if(pool[i].origin!=65535)consumed[pool[i].origin]=1;
    /* Convert in place: original pcolnomal keeps the actor's slot. */
    pool[i].type=SCD_OBJ_EXPLOSION;pool[i].subtype=1;pool[i].age=0;
    pool[i].state=pool[i].frame=pool[i].cooldown=0;pool[i].phase=CC_BADNIK_BOOM;
    o->actno=SCD_OBJ_EXPLOSION;o->r_no0=0;o->userflag.b.h=1;o->colino=0;
    return 1;
}
static int cc_enemy_suicide(unsigned i){
    sprite_status *o=&actwk[i+1];
    if(good_future && (current_era!=0 || o->userflag.b.h)){
        /* Retail DeleteObject leaves the record's saved-flags bit set, so the
           spawner never reloads it (Object Time Check.asm DestroyOnGoodFuture);
           a record without an entry respawns when the window reaches it. */
        if(pool[i].origin!=65535){
            if(tt_streamed()){if(active_placements[pool[i].origin].flags&TT_SAVED)consumed[pool[i].origin]=1;}
            else deferred_reload[pool[i].origin]=1;
        }
        int x=o->xposi.w.h,y=o->yposi.w.h;remove_slot(i);
        /* SUICIDE.C clears then replaces this actor, including its origin. */
        pool[i]=(slot){.origin=65535,.type=SCD_OBJ_EXPLOSION,.phase=CC_BADNIK_BOOM};
        o->r_no0=o->r_no1=0;scd_word_set(o,33,0);
        o->actno=SCD_OBJ_EXPLOSION;o->xposi.w.h=x;o->yposi.w.h=y;return 1;
    }
    return 0;
}
