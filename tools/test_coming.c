/* Native pure model/CMG1 bounds only. No game, audio, hardware or assets. */
#include <stdio.h>
#include <string.h>
#include "coming.h"
static unsigned checks,failures;
#define CHECK(c) do{checks++;if(!(c)){failures++;fprintf(stderr,"FAIL: Coming model line%u\n",(unsigned)__LINE__);}}while(0)
static void be32(unsigned char*p,unsigned v){p[0]=v>>24;p[1]=v>>16;p[2]=v>>8;p[3]=v;}
static unsigned crc(const unsigned char*p,unsigned n){unsigned c=~0u;while(n--){c^=*p++;for(unsigned i=0;i<8;i++)c=(c>>1)^(0xedb88320u&(0u-(c&1)));}return ~c;}
static void seal(unsigned char*p){be32(p+24,crc(p+32,13120));}
static void valid(unsigned char*p){memset(p,0,14336);memcpy(p,"CMG1",4);be32(p+4,13152);be32(p+8,150);be32(p+12,4096);be32(p+16,320);be32(p+20,1023);be32(p+28,64);seal(p);}
int main(void){
    uint16_t colours[64];for(unsigned i=0;i<64;i++)colours[i]=0xeee;
    fe_coming_state s;fe_coming_begin(&s,colours,0);CHECK(s.scroll==320 && s.timer==1023 && s.initial_wait);
    CHECK(!fe_coming_vint(&s,0));CHECK(s.shown_scroll==320 && s.scroll==319 && s.timer==1022);CHECK(!fe_coming_vint(&s,0));CHECK(s.shown_scroll==319);
    const unsigned keys[]={16,32,64,128};
    for(unsigned i=0;i<4;i++){
        unsigned key=keys[i];fe_coming_begin(&s,colours,key);CHECK(!fe_coming_vint(&s,key));CHECK(!fe_coming_vint(&s,key));CHECK(!s.tap);CHECK(!fe_coming_vint(&s,0));CHECK(fe_coming_vint(&s,key));CHECK(s.exit_reason==key);
        CHECK(fe_coming_vint(&s,0));CHECK(fe_coming_vint(&s,0xf0));CHECK(s.exit_reason==key);
        fe_coming_begin(&s,colours,0);CHECK(!fe_coming_vint(&s,key));CHECK(!fe_coming_vint(&s,key));CHECK(!fe_coming_vint(&s,0));CHECK(fe_coming_vint(&s,key));
    }
    fe_coming_begin(&s,colours,0);for(unsigned i=0;i<16;i++)CHECK(!fe_coming_vint(&s,i));CHECK(!s.exit_reason);
    fe_coming_begin(&s,colours,0);for(unsigned i=0;i<1022;i++)CHECK(!fe_coming_vint(&s,0));CHECK(s.timer==1);CHECK(fe_coming_vint(&s,0));CHECK(s.frames==1023 && s.timer==0 && s.exit_reason==0x100 && s.scroll==-703 && s.shown_scroll==-702);
    fe_coming_state tie;fe_coming_begin(&tie,colours,0);for(unsigned i=0;i<1022;i++)fe_coming_vint(&tie,0);CHECK(fe_coming_vint(&tie,128));CHECK(tie.exit_reason==128);
    const unsigned curve[]={7,6,4,1,0,0,0,0};
    for(unsigned step=0;step<24;step++){
        CHECK(fe_coming_fade(&s));for(unsigned ch=0;ch<3;ch++){unsigned expect=ch<step/8?0:ch==step/8?curve[step%8]:7;CHECK((unsigned)((s.palette[1]>>(1+4*ch))&7)==expect);}
        CHECK(fe_coming_vint(&s,0));CHECK(s.scroll==-703 && s.shown_scroll==-703 && s.exit_reason==0x100);
    }
    CHECK(!fe_coming_fade(&s));CHECK(s.fade_step==24 && !s.palette[1]);
    unsigned char p[14336],q[14336];valid(p);CHECK(fe_coming_pack_valid(p,sizeof(p)));CHECK(!fe_coming_pack_valid(NULL,sizeof(p)));CHECK(!fe_coming_pack_valid(p,31));CHECK(!fe_coming_pack_valid(p,14335));CHECK(!fe_coming_pack_valid(p,16384));
    const unsigned header[]={0,4,8,12,16,20,24,28,13152};
    for(unsigned i=0;i<sizeof(header)/sizeof(header[0]);i++){memcpy(q,p,sizeof(q));q[header[i]]^=1;CHECK(!fe_coming_pack_valid(q,sizeof(q)));}
    const unsigned dirty[]={32,65,160,4961,5153,12129};
    for(unsigned i=0;i<sizeof(dirty)/sizeof(dirty[0]);i++){
        memcpy(q,p,sizeof(q));q[dirty[i]]=i==0?0x10:i==1?14:i==3?150:1;seal(q);CHECK(!fe_coming_pack_valid(q,sizeof(q)));
    }
    memcpy(q,p,sizeof(q));q[4960]=0x20;seal(q);CHECK(!fe_coming_pack_valid(q,sizeof(q)));
    printf("%s: Coming source model/CMG1 %u checks; targetpixels/audio not exercised\n",failures?"FAIL":"PASS",checks);return failures?1:0;
}
