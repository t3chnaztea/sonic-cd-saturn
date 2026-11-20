/* Original TRAP_R3.C for3 + unmodified RIDECHK.C geometry vs native actors. */
#include "EQU.H"
#include "scd_actor.h"
#include "scd_objects.h"
#include "scd_player.h"
#include "sprite_order.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
void for3(sprite_status*);
void actionsub(sprite_status *o){(void)o;}
void tr3_fout(sprite_status *o){(void)o;}
static unsigned checks,updates,contacts,subtype,frame,ridden,lifts;
#define REQUIRE(v) do{checks++;if(!(v)){fprintf(stderr,"FAIL sub %u frame %u line %d: %s\n",subtype,frame,__LINE__,#v);exit(1);}}while(0)
static unsigned char data[300000],collision[9472];
static stage_t stage;
static size_t read_file(const char *name,unsigned char *buf,size_t cap){FILE *f=fopen(name,"rb");REQUIRE(f);size_t n=fread(buf,1,cap,f);fclose(f);return n;}
static void load(unsigned era){
    char path[128];snprintf(path,sizeof(path),"assets/generated/cc31%c.bin",'A'+era);
    size_t n=read_file(path,data,sizeof(data));REQUIRE(!stage_open(&stage,data,n));
    snprintf(path,sizeof(path),"assets/generated/cccollision31%c.bin",'A'+era);
    REQUIRE(read_file(path,collision,sizeof(collision))==sizeof(collision));
    scd_player_zone(1);scd_objects_zone(1);scd_player_act(0);scd_objects_act(0);
    REQUIRE(!scd_player_init(&stage,collision,sizeof(collision),era));
}
static void compare(sprite_status *a,sprite_status *b){
#define FIELD(f) REQUIRE(a->f==b->f)
    FIELD(xposi.l);FIELD(yposi.l);FIELD(xspeed.w);FIELD(yspeed.w);FIELD(r_no0);FIELD(r_no1);
    FIELD(actflg);FIELD(cddat);FIELD(sprhsize);FIELD(sprvsize);FIELD(sprpri);FIELD(patno);
    REQUIRE(!memcmp(a->actfree,b->actfree,sizeof(a->actfree)));
#undef FIELD
}
static void tick(sprite_status before){
    actwk[0]=before;if(actwk[0].actfree[19]==1)actwk[0].actfree[19]=100;
    if(actwk[0].colino==1)actwk[0].colino=100;
    for3(&actwk[100]);sprite_status expected=actwk[0];
    if(expected.actfree[19]==100)expected.actfree[19]=1;
    if(expected.colino==100)expected.colino=1;
    actwk[0]=before;scd_objects_step(before.xposi.w.h,before.yposi.w.h);
    compare(&actwk[1],&actwk[100]);REQUIRE(!memcmp(&actwk[0],&expected,sizeof(before)));
    scd_object_view v;REQUIRE(scd_objects_views(&v,1)==1);
    REQUIRE(v.type==SCD_OBJ_FOR3 && !v.frame && v.flags==(actwk[100].actflg&3));
    REQUIRE(scd_ppz_priority(v)==actwk[100].sprpri);updates++;
    if(actwk[0].cddat&8)ridden++;
}
static sprite_status player(int x,int y,unsigned mode){
    sprite_status p={0};p.actno=1;p.r_no0=mode==3?4:2;p.xposi.w.h=x;p.yposi.w.h=y;
    p.sprvsize=mode==2?14:19;p.sprhs=9;p.cddat=mode==2?6:2;
    p.yspeed.w=mode==1?-300:300;p.xspeed.w=512;return p;
}
static void setup(unsigned era,unsigned flags){
    scd_objects_reset(era,0);memset(actwk,0,sizeof(*actwk));editmode.w=0;chibi_flag=0;
    REQUIRE(scd_objects_spawn(SCD_OBJ_FOR3,1000,800,subtype,flags)==0);
    actwk[100]=actwk[1];
}
int main(void){
    for(unsigned era=0;era<4;era++){
        load(era);
        for(subtype=0;subtype<8;subtype++)for(unsigned flags=0;flags<4;flags++){
            setup(era,flags);
            for(frame=0;frame<1200;frame++){
                /* Alternate riding, airborne departure, and no contact. Every
                   phase boundary, settling angle and triggered lift completes. */
                sprite_status p=player(actwk[1].xposi.w.h,actwk[1].yposi.w.h-35,0);
                if(frame%240>=160)p.xposi.w.h-=100;
                else if(frame){p.cddat=actwk[0].cddat;p.actfree[19]=actwk[0].actfree[19];p.yspeed.w=0;}
                tick(p);
            }
            if(subtype>=5){REQUIRE(actwk[1].actfree[16]==4);lifts++;}
        }
        for(subtype=0;subtype<8;subtype++)for(int dx=-43;dx<=43;dx++)
        for(int dy=-40;dy<=40;dy++)for(unsigned mode=0;mode<4;mode++){
            setup(era,0);frame=0;tick(player(200,100,0));
            frame=1;tick(player(1000+dx,800+dy,mode));contacts++;
        }
    }
    scd_objects_reset(0,0);REQUIRE(scd_objects_spawn(SCD_OBJ_FOR3,1000,800,8,0)==-1);
    REQUIRE(ridden>10000);REQUIRE(lifts==48);
    printf("PASS: %u assertions; %u original/native updates; %u contact cases; %u ridden updates; %u completed lifts\n",checks,updates,contacts,ridden,lifts);
}
