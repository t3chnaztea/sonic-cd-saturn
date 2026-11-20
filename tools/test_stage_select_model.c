/* Pure native tests. Compile stage_select.c with SCD_STAGE_SELECT_HOST.
   No actual game, generated assets or hardware; Root must authorize execution. */
#include <stdio.h>
#include <string.h>
#include "stage_select.h"
static unsigned checks,failures;
#define CHECK(c) do{checks++;if(!(c)){failures++;fprintf(stderr,"FAIL: StageSelect model line%u\n",(unsigned)__LINE__);}}while(0)
static void be32(unsigned char *p,unsigned v){p[0]=v>>24;p[1]=v>>16;p[2]=v>>8;p[3]=v;}
static unsigned crc(const unsigned char *p,unsigned n){unsigned c=~0u;while(n--){c^=*p++;for(unsigned i=0;i<8;i++)c=(c>>1)^(0xedb88320u&(0u-(c&1)));}return ~c;}
static void seal(unsigned char *p){be32(p+24,crc(p+32,7600));}
static void valid(unsigned char *p){memset(p,0,8192);memcpy(p,"STG1",4);be32(p+4,7632);be32(p+8,1);be32(p+12,1120);be32(p+16,1120);be32(p+20,74);be32(p+28,64);seal(p);}
int main(void){
    unsigned seen[7][3][4]={0},kinds[5]={0};
    for(unsigned i=0;i<74;i++){
        fe_stage_select_choice c=fe_stage_select_choices[i];CHECK(c.kind<5);if(c.kind>=5)continue;kinds[c.kind]++;
        if(c.kind==FE_SEL_NORMAL){CHECK(c.zone<7 && c.act<3 && c.era<4);if(c.zone<7 && c.act<3 && c.era<4)CHECK(++seen[c.zone][c.act][c.era]==1);}
    }
    CHECK(kinds[0]==70 && kinds[1]==1 && kinds[2]==1 && kinds[3]==1 && kinds[4]==1);
    CHECK(fe_stage_select_choices[8].kind==FE_SEL_WARP);CHECK(fe_stage_select_choices[9].kind==FE_SEL_OPENING);CHECK(fe_stage_select_choices[10].kind==FE_SEL_COMMING);CHECK(fe_stage_select_choices[73].kind==FE_SEL_SPEDEMO);
    const unsigned extra[]={8,9,10,73};for(unsigned i=0;i<4;i++){fe_stage_select_choice c=fe_stage_select_choices[extra[i]];CHECK(c.zone==0 && c.act==0 && c.era==1);}
    for(unsigned z=0;z<7;z++)for(unsigned a=0;a<3;a++)for(unsigned e=0;e<4;e++)CHECK(seen[z][a][e]==(unsigned)(a<2 || e>=2));
    fe_stage_select_state state={0};fe_stage_select_input(&state,1);
    for(unsigned i=0;i<7;i++){fe_stage_select_move(&state);CHECK(state.selection==0);}
    fe_stage_select_move(&state);CHECK(state.selection==73);
    fe_stage_select_input(&state,2);for(unsigned i=0;i<8;i++)fe_stage_select_move(&state);CHECK(state.selection==0);
    fe_stage_select_input(&state,3);for(unsigned i=0;i<8;i++)fe_stage_select_move(&state);CHECK(state.selection==0);
    state.selection=73;for(unsigned i=0;i<8;i++)fe_stage_select_move(&state);CHECK(state.selection==73);
    state.selection=0;state.delay=65535;fe_stage_select_input(&state,2);fe_stage_select_move(&state);CHECK(state.delay==0 && state.selection==1);
    state=(fe_stage_select_state){0};fe_stage_select_input(&state,2);for(unsigned i=0;i<74*8;i++)fe_stage_select_move(&state);CHECK(state.selection==0);
    fe_stage_select_input(&state,1);for(unsigned i=0;i<74*8;i++)fe_stage_select_move(&state);CHECK(state.selection==0);
    for(unsigned hold=0;hold<256;hold++)CHECK(fe_stage_select_input(&state,hold)==!!(hold&0xf0));
    /* Fresh accept uses the newly read hold. Movement used the previous frame. */
    state=(fe_stage_select_state){0};for(unsigned i=0;i<7;i++)fe_stage_select_move(&state);fe_stage_select_move(&state);CHECK(!state.selection);CHECK(fe_stage_select_input(&state,0x12));CHECK(!state.selection);
    unsigned char pack[8192],copy[8192];valid(pack);CHECK(fe_stage_select_pack_valid(pack,sizeof(pack)));
    CHECK(!fe_stage_select_pack_valid(NULL,sizeof(pack)));CHECK(!fe_stage_select_pack_valid(pack,31));CHECK(!fe_stage_select_pack_valid(pack,8191));CHECK(!fe_stage_select_pack_valid(pack,0x14800));
    const unsigned offsets[]={0,4,8,12,16,20,24,28,7632};
    for(unsigned i=0;i<sizeof(offsets)/sizeof(offsets[0]);i++){memcpy(copy,pack,sizeof(copy));copy[offsets[i]]^=1;CHECK(!fe_stage_select_pack_valid(copy,sizeof(copy)));}
    memcpy(copy,pack,sizeof(copy));copy[160]=1;seal(copy);CHECK(!fe_stage_select_pack_valid(copy,sizeof(copy)));
    memcpy(copy,pack,sizeof(copy));copy[32]=0x10;seal(copy);CHECK(!fe_stage_select_pack_valid(copy,sizeof(copy)));
    memcpy(copy,pack,sizeof(copy));copy[193]=1;seal(copy);CHECK(!fe_stage_select_pack_valid(copy,sizeof(copy)));
    printf("%s: StageSelect model/74table/pack %u checks; screen/audio not exercised\n",failures?"FAIL":"PASS",checks);return failures?1:0;
}
