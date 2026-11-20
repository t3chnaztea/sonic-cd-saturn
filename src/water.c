/* Tidal Tempest water. See water.h for the original routines and frame order.
   Slot 0 is a private sprite_status standing for actwk[7] (the plawa master
   PLAYER.C plwaterchk installs). Bubbles, numbers and the splash take dynamic
   slots the way actwkchk (ACTSET.C; retail FindObjSlot R41C__.MMD $7A8A from
   $FFD800 = actwk[32]) hands them out: in the game build the shared object
   pool (src/objects.c water_pool_alloc), so they interleave with the level's
   actors in retail slot order; without it (tools/water_test.c) private slots
   1... Raw PC word accesses
   ((short*)p)[n] address actfree[2n-46] with PC (little-endian) byte order, the
   order the compiled-original fixture reproduces on the host. */
#include "EQU.H"
#include "ACTION.H"
#include "ETC.H"
#include "PLAYER.H"
#include "water.h"
#include "water_data.h"
#include <string.h>

extern void soundset(short);

static unsigned active,cur_act,cur_era;
static sprite_status slot[WATER_OBJECT_CAPACITY];
static water_object view[WATER_OBJECT_CAPACITY];
/* This update's actionsub queue in call (slot) order. */
static sprite_status *queued[WATER_OBJECT_CAPACITY+128];
static unsigned queued_count;
static void (*bgm_sink)(short);

void water_bgm_sink_set(void (*sink)(short)){bgm_sink=sink;}
int water_active(void){return active;}
void water_camera(int x,int y){scra_h_posit.w.h=(short)x;scra_v_posit.w.h=(short)y;}

/* ((short*)p)[n], PC byte order, independent of the target's endianness. */
static int word_at(const sprite_status *p,unsigned n){
    const unsigned char *b=p->actfree+2*n-46;return (short)(b[0]|b[1]<<8);
}
static void word_set(sprite_status *p,unsigned n,int v){
    unsigned char *b=p->actfree+2*n-46;b[0]=(unsigned char)v;b[1]=(unsigned char)(v>>8);
}
enum{W_DEATH=24,W_BASEX=26,W_SPAWN=29,W_SECOND=30,W_DELAY=31};

/* Level Random on the shared ranum seed. */
static int water_random(void){
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
    ranum=(int)d1;return (int)d0;
}

/* The shared dynamic object pool, when linked (src/objects.c): 0 with a free
   cleared actor (the lowest free slot, as FindObjSlot), -1 when full; -2 means
   no pool (the private slots below stand in). water_pool_free releases it. */
__attribute__((weak)) int water_pool_alloc(sprite_status **actor){(void)actor;return -2;}
__attribute__((weak)) void water_pool_free(sprite_status *p){(void)p;}
static int is_private(const sprite_status *p){return p>=slot && p<slot+WATER_OBJECT_CAPACITY;}
/* ACTSET.C actwkchk. */
static sprite_status *slot_new(void){
    sprite_status *p;int r=water_pool_alloc(&p);
    if(r==0)return p;
    if(r==-1)return 0;
    for(unsigned i=1;i<WATER_OBJECT_CAPACITY;i++)if(!slot[i].actno)return &slot[i];
    return 0;
}
static void frameout_slot(sprite_status *p){if(is_private(p))memset(p,0,sizeof(*p));else water_pool_free(p);}
int water_slot_live(unsigned i){return i && i<WATER_OBJECT_CAPACITY && slot[i].actno;}
/* src/boss.c vslot_sync reads the slots' actno fields directly. */
const sprite_status *water_slot_table(void);
const sprite_status *water_slot_table(void){return slot;}
/* ACTION.C actionsub: clear the drawn bit, queue when on screen. */
static void actionsub_slot(sprite_status *p){
    p->actflg&=127;
    if(p->actflg&12){
        short hsiz=p->sprhsize,xpos=(short)(p->xposi.w.h-scra_h_posit.w.h);
        if(xpos+hsiz<0 || xpos-hsiz>=320)return;
        short vsiz=p->sprvsize,ypos=p->yposi.w.h;
        if((unsigned short)scra_v_posit.w.h<256){if((unsigned short)ypos>=2048)ypos-=2048;}
        else if((unsigned short)scra_v_posit.w.h>=1792){if((unsigned short)ypos<256)ypos+=2048;}
        ypos-=scra_v_posit.w.h;
        if(ypos+vsiz<0 || ypos-vsiz>=224)return;
    }
    if(queued_count<sizeof(queued)/sizeof(queued[0]))queued[queued_count++]=p;
}
/* PLAYSUB4.C patchg. */
static void patchg_slot(sprite_status *p,const uint8_t *const *scripts){
    if(p->mstno.b.h!=p->mstno.b.l){p->mstno.b.l=p->mstno.b.h;p->patcnt=p->pattim=0;}
    if((signed char)--p->pattim>=0)return;
    const uint8_t *s=scripts[p->mstno.b.h];
    unsigned char n=0;while(s[n]<250)++n;
    p->pattim=s[n]!=252?(s[0]<=0?1:s[0]):s[0];
    n=s[p->patcnt+1];
    if(n<128){
    set:
        p->patno=n&31;n>>=5;n^=p->cddat;n&=3;p->actflg=(p->actflg&252)|n;++p->patcnt;return;
    }
    switch(n){
    case 255:p->patcnt=0;n=s[1];goto set;
    case 254:n=s[p->patcnt+2];p->patcnt-=n;n=s[p->patcnt+1];goto set;
    case 253:p->mstno.b.h=s[p->patcnt+2];break;
    case 252:p->r_no0+=2;break;
    case 251:p->patcnt=p->r_no1=0;break;
    case 250:p->r_no1+=2;break;
    }
}

/* R4/GAME4.C water1chk..water3chk, watercntsub, watercnt. */
static void water1chk(void){
    short d1;
    if(!(time_flag&127))return;
    if((time_flag&127)==1){d1=640;if((unsigned short)actwk[0].xposi.w.h>=1504)d1=608;}
    else{
        d1=464;
        if(actwk[0].xposi.w.h>=2336){d1=272;if(actwk[0].xposi.w.h>=6528){d1=576;waterspeed=3;}}
    }
    watermoveposi=d1;
}
static void water2chk(void){
    short d1=(short)(scra_v_posit.w.h+232);
    if(actwk[0].xposi.w.h<512){waterposi_m=watermoveposi=d1;return;}
    if(actwk[0].yposi.w.h>=1536 && actwk[0].yposi.w.h<1728 && actwk[0].xposi.w.h<672){waterposi_m=watermoveposi=d1;return;}
    if(!(time_flag&127)){waterposi_m=watermoveposi=1456;return;}
    if((time_flag&127)==1){
        d1=1328;
        if(actwk[0].xposi.w.h>=3072){
            d1=1920;
            if(actwk[0].xposi.w.h>=3520){
                d1=1280;
                if(actwk[0].xposi.w.h<4992){
                    if(actwk[0].yposi.w.h>=1024)return;
                    d1=960;if(actwk[0].xposi.w.h<4352)return;
                }
            }
        }
    } else {
        d1=1296;
        if(actwk[0].xposi.w.h>=1024){d1=912;if(actwk[0].xposi.w.h>=5632){d1=1040;if(actwk[0].xposi.w.h>=6400)d1=1280;}}
    }
    watermoveposi=d1;
}
static void water3chk(void){
    short d1=(short)(scra_v_posit.w.h+232);
    if(actwk[0].xposi.w.h<1984)waterposi_m=d1;
    else{d1=1168;if(actwk[0].xposi.w.h>=2800){waterspeed=2;d1=1472;}}
    watermoveposi=d1;
}
static void watercntsub(void){
    static void (*const tbl[3])(void)={water1chk,water2chk,water3chk};
    tbl[stageno.b.l]();
    unsigned short d1=waterspeed;
    if(watermoveposi!=waterposi_m){if(watermoveposi<waterposi_m)d1=(unsigned short)-d1;waterposi_m=(short)(waterposi_m+d1);}
}
static void watercnt(void){
    if(!pauseflag.b.h){
        short d0,d1;
        if(actwk[0].r_no0<6)watercntsub();
        waterflag=0;sysdirec+=2;sinset(sysdirec,&d0,&d1);
        waterposi=(short)((short)(signed char)((unsigned short)d0>>6)+waterposi_m);
        d0=(short)(waterposi-scra_v_posit.w.h);
        if((unsigned short)waterposi<(unsigned short)scra_v_posit.w.h && d0<0){hintposi.b.l=(unsigned char)-33;waterflag=1;}
        if((unsigned short)d0>=223)d0=223;
        hintposi.b.l=(unsigned char)d0;
    }
}

void water_reset(unsigned zone,unsigned act,unsigned era){
    active=zone==2;cur_act=act<3?act:0;cur_era=era&3;
    memset(slot,0,sizeof(slot));queued_count=0;
    /* Other zones keep their own use of the shared globals untouched. */
    if(!active)return;
    /* GAME4.C game_init */
    waterposi=waterposi_m=watermoveposi=0;waterspeed=0;water_flag=waterflag=waterflag2=0;
    watercoliflag=0;waterstop=0;mizuflag=0;waterdirec.w=0;sysdirec=0;gametimer.w=0;ranum=0;
    scroll_start.w=0;hintposi.b.l=223;
    stageno.b.h=2;stageno.b.l=cur_act;
    unsigned start=water_position_table[(time_flag&127)+stageno.b.l*4];
    waterposi=waterposi_m=watermoveposi=(short)start;
    water_flag=0;waterflag=0;waterspeed=1;
    /* Retail phase (tools/water_retail_phase.py): the sway angle is 0 through
       game_init and the level loop advances it three times before Sonic's first
       update, so it reads 8 after that update. PC GAME4.C's game_init leaves 2. */
    sysdirec=4;
    watercnt();
    pl_air=30;
}
void water_tick(void){if(active)++gametimer.w;}

/* PLAYSUB4.C plairset. */
void water_air_refill(void){
    if(!active)return;
    if(pl_air<13){
        short d0=130;
        if(stageno.w==259)d0=134;
        if(plpower_m)d0=135;
        if(bossstart)d0=140;
        if(bgm_sink)bgm_sink(d0);
    }
    pl_air=30;slot[0].actfree[8]=0;
}

/* PLAYER.C plwaterchk. Slot 0 plays actwk[7]. */
void water_player_check(void){
    if(!active || stageno.b.h!=2)return;
    if(stageno.b.l==1 && actwk[0].xposi.w.h<200)return;
    if(waterposi<actwk[0].yposi.w.h){
        if(actwk[0].cddat&64)return;
        actwk[0].cddat|=64;water_air_refill();
        slot[0].actno=33;slot[0].userflag.b.h=129;
        plmaxspdwk=768;pladdspdwk=6;plretspdwk=64;
        /* Retail plwaterchk (R41D__.MMD $4376-$437E): asr.w, rounding toward
           minus infinity (the PC "/ 2", "/ 4" truncate). */
        actwk[0].xspeed.w>>=1;actwk[0].yspeed.w>>=2;
        if(actwk[0].yspeed.w==0)return;
    } else {
        if(actwk[0].yspeed.w>0)return;
        if(!(actwk[0].cddat&64))return;
        actwk[0].cddat&=191;
        plmaxspdwk=1536;pladdspdwk=12;plretspdwk=128;
        actwk[0].yspeed.w*=2;
        if(actwk[0].yspeed.w==0)return;
        if(actwk[0].yspeed.w<-4096)actwk[0].yspeed.w=-4096;
    }
    sprite_status *p=slot_new();if(!p)return;
    p->actno=11;p->xposi.w.h=actwk[0].xposi.w.h;
}

/* PLAYSUB4.C plawamaster_jump2 / _jump / _jump0. */
static void master_jump2(sprite_status *m){
    word_set(m,W_DELAY,(unsigned short)water_random()&15);
    sprite_status *n=slot_new();
    if(!n)return;
    n->actno=33;n->xposi.w.h=actwk[0].xposi.w.h;
    short d0=6;
    if(actwk[0].cddat&1){d0=-d0;n->direc.b.h=64;}
    n->xposi.w.h+=d0;n->yposi.w.h=actwk[0].yposi.w.h;n->userflag.b.h=6;
    if((unsigned short)word_at(m,W_DEATH)){
        word_set(m,W_DELAY,(unsigned short)word_at(m,W_DELAY)&7);
        n->yposi.w.h=(short)(actwk[0].yposi.w.h-12);
        n->direc.b.h=(unsigned char)water_random();
        if(!(gametimer.w&3))n->userflag.b.h=14;
    } else if(m->actfree[12]&128){
        n->sproffset=8192;
        if(!(water_random()&3)){
            if(m->actfree[12]&64)goto done;
            m->actfree[12]|=64;n->userflag.b.h=(unsigned char)((unsigned short)pl_air>>1);word_set(n,W_SECOND,28);
        }
        if(!m->actfree[10]){
            if(m->actfree[12]&64)goto done;
            m->actfree[12]|=64;n->userflag.b.h=(unsigned char)(pl_air>>1);word_set(n,W_SECOND,28);
        }
    }
done:
    if(--m->actfree[10]&128)word_set(m,W_SPAWN,0);
}
static void master_jump(sprite_status *m){
    if(!word_at(m,W_SPAWN))return;
    int d=word_at(m,W_DELAY)-1;word_set(m,W_DELAY,d);
    if((short)d>=0)return;
    master_jump2(m);
}
/* PLAYSUB4.C plawamaster. */
static void plawamaster(sprite_status *m){
    if(!(unsigned short)word_at(m,W_DEATH)){
        if(actwk[0].r_no0>=6)return;
        if(!(actwk[0].cddat&64))return;
        int s=word_at(m,W_SECOND)-1;word_set(m,W_SECOND,s);
        if((short)s>=0){master_jump(m);return;}
        word_set(m,W_SECOND,59);word_set(m,W_SPAWN,1);
        m->actfree[10]=(unsigned char)(water_random()&1);
        if(pl_air!=25 && pl_air!=20 && pl_air!=15 && pl_air<13){
            if(!(gametimer.b.l&32))soundset(223);
            if(--m->actfree[8]&128){m->actfree[8]=m->actfree[9];m->actfree[12]|=128;}
        }
        if(--pl_air>=0){master_jump2(m);return;}
        water_air_refill();
        actwk[0].actfree[2]=129;soundset(182);
        m->actfree[10]=10;word_set(m,W_SPAWN,1);word_set(m,W_DEATH,120);
        jumpcolsub();
        actwk[0].mstno.b.h=23;actwk[0].cddat|=2;actwk[0].sproffset|=32768;actwk[0].sprpri=0;
        actwk[0].yspeed.w=0;actwk[0].xspeed.w=0;actwk[0].mspeed.w=0;
        scroll_start.b.h=1;
        return;
    }
    int t=word_at(m,W_DEATH)-1;word_set(m,W_DEATH,t);
    if(!(unsigned short)t){actwk[0].r_no0=6;return;}
    speedset2(&actwk[0]);actwk[0].yspeed.w+=16;
    master_jump(m);
}

/* PLAYSUB4.C plawa children. */
static void plawamove3(sprite_status *p);
static void plawasub(sprite_status *p){
    if(word_at(p,W_SECOND)){
        int t=word_at(p,W_SECOND)-1;word_set(p,W_SECOND,t);
        if(!(short)t && p->mstno.b.h<7){
            word_set(p,W_SECOND,15);p->yspeed.w=0;p->actflg=129;
            p->xposi.w.h=(short)(p->xposi.w.h-scra_h_posit.w.h+128);
            p->yposi.w.h=(short)(p->yposi.w.h-scra_v_posit.w.h+128);
            p->r_no0=12;
        }
    }
}
static void plawamove2(sprite_status *p){
    if(waterposi>=p->yposi.w.h){
        p->r_no0=6;p->mstno.b.h+=7;if(p->mstno.b.h>15)p->mstno.b.h=15;
        plawamove3(p);return;
    }
    if(watercoliflag)word_set(p,W_BASEX,word_at(p,W_BASEX)+4);
    p->xposi.w.h=(short)((short)water_awasintbl[(p->direc.b.h++ +1)&127]+word_at(p,W_BASEX));
    plawasub(p);speedset2(p);
    if(p->actflg&128)actionsub_slot(p);else frameout_slot(p);
}
static void plawamove(sprite_status *p){patchg_slot(p,water_plawachg);plawamove2(p);}
static void plawamove3(sprite_status *p){plawasub(p);patchg_slot(p,water_plawachg);actionsub_slot(p);}
static void plawamove5(sprite_status *p){
    if(pl_air>12){frameout_slot(p);return;}
    int t=word_at(p,W_SECOND)-1;word_set(p,W_SECOND,t);
    if(!(short)t){
        p->r_no0=14;p->mstno.b.h+=7;if(p->mstno.b.h>15)p->mstno.b.h=15;
        plawamove3(p);return;
    }
    patchg_slot(p,water_plawachg);
    if(p->actflg&128)actionsub_slot(p);else frameout_slot(p);
}
static void plawainit(sprite_status *p){
    p->r_no0+=2;p->sproffset|=33930;p->actflg=132;p->sprhsize=16;p->sprpri=1;
    if(p->userflag.b.h&128){
        p->r_no0+=8;p->sproffset|=1162;p->actfree[9]=p->userflag.b.h&127;plawamaster(p);
    } else {
        p->mstno.b.h=p->userflag.b.h;word_set(p,W_BASEX,p->xposi.w.h);p->yspeed.w=-136;plawamove(p);
    }
}
static void plawa(sprite_status *p){
    switch(p->r_no0/2){
    case 0:plawainit(p);break;
    case 1:plawamove(p);break;
    case 2:plawamove2(p);break;
    case 3:case 7:plawamove3(p);break;
    case 4:case 8:frameout_slot(p);break;
    case 5:plawamaster(p);break;
    case 6:plawamove5(p);break;
    }
}
/* PLAYSUB4.C exit2: the entry/exit splash. */
static void exit2(sprite_status *p){
    switch(p->r_no0){
    case 0:
        p->r_no0+=2;p->actflg=4;p->sprpri=1;p->sproffset=664;p->mstno.b.h=p->userflag.b.h;
        soundset(p->userflag.b.h<2?162:161);
        /* fall through */
    case 2:
        p->yposi.w.h=waterposi;p->yposi.w.h+=4;patchg_slot(p,water_exit2chg);actionsub_slot(p);break;
    case 4:frameout_slot(p);break;
    }
}

static void water_object_run(sprite_status *p){if(p->actno==33)plawa(p);else if(p->actno==11)exit2(p);}
void water_objects_step(void){
    if(!active)return;
    queued_count=0;
    for(unsigned i=0;i<WATER_OBJECT_CAPACITY;i++)water_object_run(&slot[i]);
}
/* A pooled bubble or splash, at its slot's turn in the object loop. */
void water_pool_run(sprite_status *p){if(active)water_object_run(p);}
static int queued_live(const sprite_status *p){return p->actno==33 || p->actno==11;}
void water_objects_visible(void){
    if(!active)return;
    for(unsigned i=0;i<queued_count;i++)if(queued_live(queued[i]))queued[i]->actflg|=128;
}

/* R4/GAME4.C watercoli: currents, acts 1 and 2. */
void water_currents(void){
    if(!active)return;
    if(actwk[0].mstno.b.h==43)return;
    if(actwk[0].actfree[2]&1)return;
    if(!actwk[0].actno)return;
    if(editmode.w)return;
    if(stageno.b.l>=2)return;
    const int16_t *t=water_coli_tables[water_coli_index[cur_act][cur_era]];
    for(int i=0;t[i]>=0;i+=7){
        if(actwk[0].xposi.w.h<t[i])continue;
        if(actwk[0].xposi.w.h>=t[i+2])continue;
        if(actwk[0].yposi.w.h<t[i+1])continue;
        if(actwk[0].yposi.w.h>=t[i+3])continue;
        /* PC byte order of the flag word: [0] low byte (switch), [1] high (kind). */
        unsigned sw=(unsigned short)t[i+6]&255,kind=(unsigned short)t[i+6]>>8;
        if(kind==1 && !(switchflag[sw]&64))return;
        if(actwk[0].r_no0>=4){watercoliflag=0;return;}
        watercoliflag=1;actwk[0].actfree[18]=0;
        actwk[0].xspeed.w=t[i+4];actwk[0].yspeed.w=t[i+5];
        actwk[0].mstno.b.h=15;actwk[0].cddat|=2;
        if(kind==2 && (switchflag[sw]&32)){actwk[0].xspeed.w*=-1;actwk[0].yspeed.w*=-1;}
        if(swdata.b.h&1)--actwk[0].yposi.w.h;
        if(swdata.b.h&2)++actwk[0].yposi.w.h;
        if(swdata.b.h&4)--actwk[0].xposi.w.h;
        if(swdata.b.h&8)++actwk[0].xposi.w.h;
        return;
    }
    if(!watercoliflag)return;
    actwk[0].mstno.b.h=0;watercoliflag=0;
}

void water_level_step(void){if(active)watercnt();}

/* The H-INT line is hintposi (the surface row). Retail R41A/B/D frames
   (tools/water_retail.py --line) show the H-INT's waterPalette DMA spanning
   rows hint+1..hint+2 (entries switch in order, mixed rows) and the water
   palette complete from row hint+3; the Saturn switches whole banks at that
   row. waterflag marks water over the whole screen (hintposi is 223 then). */
unsigned water_screen_line(void){
    if(!active)return 224;
    if(waterflag)return 0;
    unsigned line=(unsigned char)hintposi.b.l+3u; /* b.l is a signed char; rows 128-223 are valid */
    return line>=224?224:line;
}
const uint16_t *water_palette(void){return water_palettes[cur_era];}

unsigned water_sprites(water_sprite *out,unsigned capacity){
    unsigned n=0;
    if(!active)return 0;
    for(unsigned i=0;i<queued_count && n<capacity;i++){
        const sprite_status *p=queued[i];
        if(!queued_live(p))continue;
        int x=p->xposi.w.h,y=p->yposi.w.h;
        if(p->actflg&12){
            x-=scra_h_posit.w.h;
            if((unsigned short)scra_v_posit.w.h<256){if((unsigned short)y>=2048)y-=2048;}
            else if((unsigned short)scra_v_posit.w.h>=1792){if((unsigned short)y<256)y+=2048;}
            y-=scra_v_posit.w.h;
        } else {x-=128;y-=128;}
        out[n++]=(water_sprite){(int16_t)x,(int16_t)y,p->patno,(uint8_t)(p->sproffset>>13&3),(uint8_t)(p->actflg&3),(uint8_t)(p->actno==11)};
    }
    return n;
}

const water_object *water_objects(void){
    for(unsigned i=0;i<WATER_OBJECT_CAPACITY;i++){
        const sprite_status *p=&slot[i];water_object *v=&view[i];
        v->used=p->actno!=0;v->actno=p->actno;v->r_no0=p->r_no0;v->actflg=p->actflg;v->mstno=p->mstno.b.h;
        v->patno=p->patno;v->patcnt=p->patcnt;v->pattim=p->pattim;v->userflag=p->userflag.b.h;v->direc=p->direc.b.h;
        v->sproffset=p->sproffset;v->x=p->xposi.l;v->y=p->yposi.l;v->yspeed=p->yspeed.w;
        memcpy(v->actfree,p->actfree,22);
    }
    return view;
}
