/* Run the real title program against the original press-start cheat contract.
   Compile this same test against old or repaired src/title.c and title.h.
   No asset generation, state placement, executable spawning, or output writes.
   This checks title entry only; the dedicated screen/audio need emulator proof. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "title.h"

typedef struct { unsigned at, pad, held; } pulse;
enum { EXPECT_EXIT, EXPECT_PRESS_START, EXPECT_MENU, EXPECT_NOT_STAFF };
typedef struct {
    const char *name;
    unsigned limit, expectation, exit, saved, flags;
    pulse input[10];
} entry_case;

/* Original Menu/Main.asm:436-473: exact taps 8,8,1,1,2,32. Neutral is
   allowed; a wrong nonzero tap resets progress. Start keeps its priority. */
static const entry_case cases[]={
    {"staff-times",900,EXPECT_EXIT,9,0,0,
        {{700,8,4},{708,8,4},{716,1,4},{724,1,4},{732,2,4},{740,32,4}}},
    {"staff-times-unlocked",900,EXPECT_EXIT,9,1,0x2C,
        {{700,8,4},{708,8,4},{716,1,4},{724,1,4},{732,2,4},{740,32,4}}},
    {"neutral-preserves-progress",900,EXPECT_EXIT,9,0,0,
        {{700,8,4},{716,8,4},{732,1,4},{748,1,4},{764,2,4},{780,32,4}}},
    {"wrong-tap-resets",900,EXPECT_PRESS_START,0,0,0,
        {{700,8,4},{708,8,4},{716,4,4},{724,1,4},{732,1,4},{740,2,4},{748,32,4}}},
    {"correct-code-after-wrong-tap",900,EXPECT_EXIT,9,0,0,
        {{680,8,4},{688,4,4},{700,8,4},{708,8,4},{716,1,4},{724,1,4},{732,2,4},{740,32,4}}},
    {"extra-button-rejected",900,EXPECT_PRESS_START,0,0,0,
        {{700,8,4},{708,8,4},{716,1,4},{724,1,4},{732,2,4},{740,96,4}}},
    {"held-right-is-one-edge",900,EXPECT_PRESS_START,0,0,0,
        {{700,8,16},{724,1,4},{732,1,4},{740,2,4},{748,32,4}}},
    {"start-opens-menu",900,EXPECT_MENU,0,0,0,
        {{700,8,4},{708,8,4},{716,1,4},{724,1,4},{732,2,4},{740,160,4}}},
    {"opened-menu-is-not-cheat-parent",1100,EXPECT_NOT_STAFF,0,0,0,
        {{700,128,4},{900,8,4},{908,8,4},{916,1,4},{924,1,4},{932,2,4},{940,32,4}}},
    {"sound-test-preserved",900,EXPECT_EXIT,7,0,0,
        {{700,2,4},{708,2,4},{716,2,4},{724,4,4},{732,8,4},{740,64,4}}},
    {"staff-after-partial-sound",900,EXPECT_EXIT,9,0,0,
        {{680,2,4},{700,8,4},{708,8,4},{716,1,4},{724,1,4},{732,2,4},{740,32,4}}},
    {"sound-after-partial-staff",900,EXPECT_EXIT,7,0,0,
        {{680,8,4},{688,8,4},{700,2,4},{708,2,4},{716,2,4},{724,4,4},{732,8,4},{740,64,4}}},
    {"newgame-preserved",900,EXPECT_EXIT,1,0,0,
        {{700,128,4},{800,64,4}}},
    {"timeout-preserved",1300,EXPECT_EXIT,0,0,0,{{0,0,0}}}
};

static unsigned pad_at(const entry_case *test,unsigned vint){
    for(unsigned i=0;i<sizeof(test->input)/sizeof(test->input[0]);i++){
        const pulse *p=test->input+i;
        if(p->held && vint>=p->at && vint-p->at<p->held)return p->pad;
    }
    return 0;
}

static int run_case(const entry_case *test,const scd_title_pack *pack){
    scd_title *title=calloc(1,sizeof(*title));
    if(!title)return 0;
    if(scd_title_start(title,pack)){free(title);return 0;}
    title->save_available=(uint8_t)test->saved;
    title->title_flags=(uint8_t)test->flags;
    int done=0;
    while(!done && title->vint<test->limit)
        done=scd_title_vint(title,pad_at(test,title->vint));
    int passed=title->save_available==test->saved && title->title_flags==test->flags;
    if(test->expectation==EXPECT_EXIT)
        passed=passed && done && title->exit_code==test->exit &&
            (test->exit?title->exit_flag==test->exit:title->exit_flag==0xFF);
    else if(test->expectation==EXPECT_PRESS_START)
        passed=passed && !done && !title->exit_flag && !title->menu_sel;
    else if(test->expectation==EXPECT_MENU)
        passed=passed && !done && !title->exit_flag && title->menu_sel!=0;
    else
        passed=passed && title->exit_flag!=9 && title->exit_code!=9 && title->menu_sel!=0;
    printf("%s: staff-times-entry %s done=%d exit=%u flag=%u menu=%u vint=%u\n",
           passed?"PASS":"FAIL",test->name,done,title->exit_code,title->exit_flag,title->menu_sel,title->vint);
    free(title);
    return passed;
}

int main(int argc,char **argv){
    if(argc<2 || argc>3){fprintf(stderr,"usage: test_staff_times_entry TITLE.BIN [case]\n");return 2;}
    FILE *file=fopen(argv[1],"rb");
    if(!file){perror(argv[1]);return 2;}
    if(fseek(file,0,SEEK_END)){fclose(file);return 2;}
    long length=ftell(file);
    if(length<=0 || fseek(file,0,SEEK_SET)){fclose(file);return 2;}
    uint8_t *data=malloc((size_t)length);
    if(!data){fclose(file);return 2;}
    int read_ok=fread(data,1,(size_t)length,file)==(size_t)length;
    fclose(file);
    scd_title_pack pack;
    if(!read_ok || scd_title_open(&pack,data,(size_t)length)){free(data);return 2;}
    unsigned selected=0,passed=0;
    for(unsigned i=0;i<sizeof(cases)/sizeof(cases[0]);i++){
        if(argc==3 && strcmp(cases[i].name,argv[2]))continue;
        selected++;passed+=(unsigned)run_case(cases+i,&pack);
    }
    free(data);
    if(!selected){fprintf(stderr,"Unknown staff-times entry case\n");return 2;}
    printf("%s: staff-times-entry %u/%u title cases; screen/audio not exercised\n",
           passed==selected?"PASS":"FAIL",passed,selected);
    return passed==selected?0:1;
}
