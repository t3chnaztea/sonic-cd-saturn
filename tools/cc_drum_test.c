/* Compiled R3/TRAP_R3.C drumr3 versus the native Act 2 actor. */
#include "EQU.H"
#include "scd_objects.h"
#include "scd_player.h"
#include "sprite_order.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
void drumr3(sprite_status*);
void actionsub(sprite_status *o){(void)o;}
void tr3_fout(sprite_status *o){(void)o;}
static unsigned checks,updates,subtype,era,frame,contacts,ridden,releases;
static int approach_xspeed=512;
#define REQUIRE(v) do{checks++;if(!(v)){fprintf(stderr,"FAIL era %u sub %u frame %u line %d: %s\n",era,subtype,frame,__LINE__,#v);exit(1);}}while(0)
static unsigned char data[300000],collision[9472];
static stage_t stage;
static size_t read_file(const char *name,unsigned char *buf,size_t cap){FILE *f=fopen(name,"rb");REQUIRE(f);size_t n=fread(buf,1,cap,f);fclose(f);return n;}
static void load(void){
    char path[128];snprintf(path,sizeof(path),"assets/generated/cc32%c.bin",'A'+era);
    size_t n=read_file(path,data,sizeof(data));REQUIRE(!stage_open(&stage,data,n));
    snprintf(path,sizeof(path),"assets/generated/cccollision32%c.bin",'A'+era);
    REQUIRE(read_file(path,collision,sizeof(collision))==sizeof(collision));
    scd_player_zone(1);scd_objects_zone(1);scd_player_act(1);scd_objects_act(1);
}
static void setup(void){
    REQUIRE(!scd_player_init(&stage,collision,sizeof(collision),era));
    scd_objects_reset(era,0);editmode.w=0;chibi_flag=0;
    REQUIRE(scd_objects_spawn(SCD_OBJ_DRUMR3,200,450,subtype,0)==0);
    actwk[100]=actwk[1];
}
static void compare(sprite_status *a,sprite_status *b){
    if(memcmp(a->actfree,b->actfree,sizeof(a->actfree)))for(unsigned i=0;i<sizeof(a->actfree);i++)
        if(a->actfree[i]!=b->actfree[i])fprintf(stderr,"actfree[%u] native=%u original=%u\n",i,a->actfree[i],b->actfree[i]);
#define FIELD(f) REQUIRE(a->f==b->f)
    FIELD(xposi.l);FIELD(yposi.l);FIELD(xspeed.w);FIELD(yspeed.w);
    FIELD(r_no0);FIELD(r_no1);FIELD(cddat);
    FIELD(sprhsize);FIELD(sprvsize);FIELD(sprpri);FIELD(patno);
    REQUIRE(!memcmp(a->actfree,b->actfree,sizeof(a->actfree)));
#undef FIELD
}
static sprite_status contact_player(int x,int y,unsigned mode){
    sprite_status p={0};p.actno=1;p.r_no0=mode==3?6:2;
    p.xposi.w.h=x;p.yposi.w.h=y;p.sprvsize=mode==2?14:19;p.sprhs=9;
    p.cddat=mode==2?6:2;p.yspeed.w=mode==1?-300:mode==8?0:300;p.xspeed.w=(int16_t)approach_xspeed;
    if(mode==4)p.actfree[2]=64;
    if(mode==5)p.mstno.b.h=23;
    if(mode==6)p.mstno.b.h=43;
    if(mode==7){p.cddat=8;p.actfree[19]=1;p.yspeed.w=0;}
    return p;
}
static void contact_tick(sprite_status before){
    actwk[0]=before;
    if(actwk[0].actfree[19]==1)actwk[0].actfree[19]=100;
    if(actwk[0].colino==1)actwk[0].colino=100;
    gametimer.w=(uint16_t)scd_player_get().frame;
    actwk[100].actflg=actwk[1].actflg;
    drumr3(&actwk[100]);sprite_status expected=actwk[0];
    if(expected.actfree[19]==100)expected.actfree[19]=1;
    if(expected.colino==100)expected.colino=1;
    actwk[0]=before;scd_objects_step(before.xposi.w.h,before.yposi.w.h);
    compare(&actwk[1],&actwk[100]);
    if(memcmp(&actwk[0],&expected,sizeof(before)))fprintf(stderr,"player expected xy=%d,%d flags=%u ride=%u actual xy=%d,%d flags=%u ride=%u\n",expected.xposi.w.h,expected.yposi.w.h,expected.cddat,expected.actfree[19],actwk[0].xposi.w.h,actwk[0].yposi.w.h,actwk[0].cddat,actwk[0].actfree[19]);
    REQUIRE(!memcmp(&actwk[0],&expected,sizeof(before)));
    if(actwk[0].cddat&8)ridden++;
    if((before.cddat&8) && !(actwk[0].cddat&8))releases++;
    contacts++;
}
int main(void){
    for(era=0;era<4;era++){
        load();
        for(subtype=0;subtype<18;subtype++){
            setup();
            for(frame=0;frame<900;frame++){
                gametimer.w=(uint16_t)scd_player_get().frame;
                scra_h_posit.w.h=200;
                /* The retail sprite pass would publish last frame's viewport
                   bit before this actor update; the isolated stub does not. */
                actwk[100].actflg=actwk[1].actflg;
                drumr3(&actwk[100]);
                scd_player_step(0);
                compare(&actwk[1],&actwk[100]);
                scd_object_view view;REQUIRE(scd_objects_views(&view,1)==1);
                REQUIRE(view.type==SCD_OBJ_DRUMR3 && view.frame==actwk[100].patno);
                REQUIRE(scd_ppz_priority(view)==actwk[100].sprpri);
                updates++;
            }
        }
        for(subtype=0;subtype<18;subtype++){
            setup();
            contact_tick(contact_player(0,0,0));
            contact_tick(contact_player(0,0,0));
            sprite_status native=actwk[1],original=actwk[100];
            /* Pixel grid, three player X speeds and zero/up/down Y speed includes both horizontal edges and every top/side
               boundary, standing/rolling, upward motion and ride release. */
            static const int xspeeds[3]={512,0,-512};
            for(unsigned v=0;v<3;v++){approach_xspeed=xspeeds[v];
            for(int dx=-35;dx<=35;dx++)for(int dy=-34;dy<=4;dy++)
            for(unsigned mode=0;mode<9;mode++){
                actwk[1]=native;actwk[100]=original;
                actwk[1].actflg|=128;
                if(mode==7)actwk[1].cddat=actwk[100].cddat=8;
                frame=contacts;
                contact_tick(contact_player(200+dx,450+dy,mode));
            }}
            approach_xspeed=512;
            setup();
            for(frame=0;frame<900;frame++){
                sprite_status p=contact_player(200,actwk[1].yposi.w.h-actwk[1].sprvsize-19,0);
                if(frame%90>=60)p.xposi.w.h=100;
                else if(frame){p.cddat=actwk[0].cddat;p.actfree[19]=actwk[0].actfree[19];p.yspeed.w=0;}
                actwk[1].actflg|=128;contact_tick(p);
            }
        }
    }
    REQUIRE(ridden>1000);REQUIRE(releases>1000);
    printf("PASS: %u assertions; %u motion updates; %u contact updates; %u ridden; %u releases across four eras and 18 phase starts\n",checks,updates,contacts,ridden,releases);
}
