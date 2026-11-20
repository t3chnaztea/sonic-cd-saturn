/* Host-only recorded controller input. Never writes game memory or skips states. */
#include <ctype.h>
#include <errno.h>
#include <limits.h>

#define ACT_PAD_MAX 16000
typedef struct { unsigned buttons; uint32_t words[16]; } act_pad_state;
static act_pad_state act_pad_states[ACT_PAD_MAX];
static unsigned act_pad_count;

static int act_pad_load(const char *path) {
    /* Each act has its own simulation clock and carried-progress snapshot.
       Never append a new stage to a previous stage's reference. */
    act_pad_count=0;
    FILE *input=fopen(path,"r");
    if(!input){perror(path);return -1;}
    char line[512];unsigned previous=0;
    while(fgets(line,sizeof(line),input)){
        uint32_t fields[18];char *cursor=line;
        if(act_pad_count==ACT_PAD_MAX || !strchr(line,'\n'))goto invalid;
        for(unsigned i=0;i<18;i++){
            while(isspace((unsigned char)*cursor))cursor++;
            if(!isxdigit((unsigned char)*cursor))goto invalid;
            char *end;errno=0;unsigned long value=strtoul(cursor,&end,i<2?10:16);
            if(errno || cursor==end || value>UINT32_MAX || (*end && !isspace((unsigned char)*end)))goto invalid;
            fields[i]=(uint32_t)value;cursor=end;
        }
        while(isspace((unsigned char)*cursor))cursor++;
        if(*cursor || fields[1]>31 || fields[8]!=act_pad_count+1 ||
           (act_pad_count && fields[0]!=previous+1))goto invalid;
        previous=fields[0];
        act_pad_states[act_pad_count].buttons=fields[1];
        memcpy(act_pad_states[act_pad_count].words,fields+2,16*sizeof(uint32_t));
        act_pad_count++;
    }
    if(ferror(input) || !act_pad_count || act_pad_states[0].buttons)goto invalid;
    fclose(input);return 0;
invalid:
    fprintf(stderr,"Invalid recorded act trace at row %u: %s\n",act_pad_count+1,path);
    fclose(input);act_pad_count=0;return -1;
}

static int act_pad_load_sequence(const char *directory,unsigned act) {
    static const char *names[]={"player-target-trace.txt","act2-target-trace.txt","act3-target-trace.txt"};
    char path[4096];
    if(act>=3){act_pad_count=0;return -1;}
    int length=snprintf(path,sizeof(path),"%s/%s",directory,names[act]);
    if(length<0 || (size_t)length>=sizeof(path)){act_pad_count=0;return -1;}
    return act_pad_load(path);
}

static unsigned act_pad_mask(unsigned buttons) {
    static const unsigned ids[5]={RETRO_DEVICE_ID_JOYPAD_UP,RETRO_DEVICE_ID_JOYPAD_DOWN,
        RETRO_DEVICE_ID_JOYPAD_LEFT,RETRO_DEVICE_ID_JOYPAD_RIGHT,RETRO_DEVICE_ID_JOYPAD_B};
    unsigned mask=0;
    for(unsigned i=0;i<5;i++)if(buttons&(1u<<i))mask|=1u<<ids[i];
    return mask;
}
