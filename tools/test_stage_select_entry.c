/* Run the real title program against the original press-start cheat contract.
   Compile this same test against old or repaired src/title.c and title.h.
   No asset generation, state placement, executable spawning, or output writes.
   This checks title entry only; the dedicated screen/audio need emulator proof. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "title.h"

typedef struct { unsigned at, pad, held; } pulse;
enum { EXPECT_EXIT, EXPECT_PRESS_START, EXPECT_MENU, EXPECT_NOT_STAGE };
typedef struct {
    const char *name;
    unsigned limit, expectation, exit, saved, flags;
    pulse input[10];
} entry_case;

/* Original Menu/Main.asm:396-436: taps1,2,2,4,8,16. */
static const entry_case cases[]={
    {"stage-select",900,EXPECT_EXIT,8,0,0,{{700,1,4},{708,2,4},{716,2,4},{724,4,4},{732,8,4},{740,16,4}}},
    {"stage-select-unlocked",900,EXPECT_EXIT,8,1,0x2C,{{700,1,4},{708,2,4},{716,2,4},{724,4,4},{732,8,4},{740,16,4}}},
    {"neutral-preserves",900,EXPECT_EXIT,8,0,0,{{700,1,4},{716,2,4},{732,2,4},{748,4,4},{764,8,4},{780,16,4}}},
    {"wrong-tap-resets",900,EXPECT_PRESS_START,0,0,0,{{700,1,4},{708,2,4},{716,64,4},{724,2,4},{732,4,4},{740,8,4},{748,16,4}}},
    {"restart-after-wrong",900,EXPECT_EXIT,8,0,0,{{680,1,4},{688,64,4},{700,1,4},{708,2,4},{716,2,4},{724,4,4},{732,8,4},{740,16,4}}},
    {"extra-button-rejected",900,EXPECT_PRESS_START,0,0,0,{{700,1,4},{708,2,4},{716,2,4},{724,4,4},{732,8,4},{740,48,4}}},
    {"held-down-one-edge",900,EXPECT_PRESS_START,0,0,0,{{700,1,4},{708,2,16},{732,4,4},{740,8,4},{748,16,4}}},
    {"start-priority",900,EXPECT_MENU,0,0,0,{{700,1,4},{708,2,4},{716,2,4},{724,4,4},{732,8,4},{740,144,4}}},
    {"carousel-not-parent",1100,EXPECT_NOT_STAGE,0,0,0,{{700,128,4},{900,1,4},{908,2,4},{916,2,4},{924,4,4},{932,8,4},{940,16,4}}},
    {"sound-test-preserved",900,EXPECT_EXIT,7,0,0,{{700,2,4},{708,2,4},{716,2,4},{724,4,4},{732,8,4},{740,64,4}}},
    {"staff-times-preserved",900,EXPECT_EXIT,9,0,0,{{700,8,4},{708,8,4},{716,1,4},{724,1,4},{732,2,4},{740,32,4}}},
    {"stage-after-partial-staff",900,EXPECT_EXIT,8,0,0,{{680,8,4},{688,8,4},{700,1,4},{708,2,4},{716,2,4},{724,4,4},{732,8,4},{740,16,4}}},
    {"staff-after-partial-stage",900,EXPECT_EXIT,9,0,0,{{680,1,4},{688,2,4},{700,8,4},{708,8,4},{716,1,4},{724,1,4},{732,2,4},{740,32,4}}},
    {"newgame-preserved",900,EXPECT_EXIT,1,0,0,{{700,128,4},{800,64,4}}},
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
        passed=passed && title->exit_flag!=8 && title->exit_code!=8 && title->menu_sel!=0;
    printf("%s: stage-select-entry %s done=%d exit=%u flag=%u menu=%u vint=%u\n",
           passed?"PASS":"FAIL",test->name,done,title->exit_code,title->exit_flag,title->menu_sel,title->vint);
    free(title);
    return passed;
}

int main(int argc,char **argv){
    if(argc<2 || argc>3){fprintf(stderr,"usage: test_stage_select_entry TITLE.BIN [case]\n");return 2;}
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
    if(!selected){fprintf(stderr,"Unknown stage-select entry case\n");return 2;}
    printf("%s: stage-select-entry %u/%u title cases; screen/audio not exercised\n",
           passed==selected?"PASS":"FAIL",passed,selected);
    return passed==selected?0:1;
}
