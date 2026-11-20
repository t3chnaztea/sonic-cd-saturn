/* Read-only CC controller route. Columns: observation sequence, libretro pad
   mask, expected integer X, expected integer Y. Never writes game memory. */
#define CC_PAD_MAX 48000
typedef struct {unsigned sequence,pad;int x,y;} cc_pad_state;
static cc_pad_state cc_pad_states[CC_PAD_MAX];
static unsigned cc_pad_count;
static int cc_pad_load(const char *path){
    FILE *f=fopen(path,"r");if(!f){perror(path);return -1;}
    char line[160];cc_pad_count=0;
    while(fgets(line,sizeof(line),f)){
        cc_pad_state r;char extra;
        if(cc_pad_count==CC_PAD_MAX || !strchr(line,'\n') ||
           sscanf(line,"%u %u %d %d %c",&r.sequence,&r.pad,&r.x,&r.y,&extra)!=4 ||
           r.sequence!=cc_pad_count+2 || (r.pad&~(1u|16u|32u|64u|128u)) ||
           (r.pad&192)==192 || (r.pad&48)==48 || r.x<0 || r.x>=16384 || r.y < -1024 || r.y>2048+256){
            /* y up to 2304: a wrapping map (TT2) or a fall through a camera wrap
               (TT3) runs past 2048 until PLAYER.C limitchk (scralim_down + 224).
               MM has no top bound: retail MM2C rises to y -272. */
            fprintf(stderr,"Invalid CC pad row %u\n",cc_pad_count+1);fclose(f);return -1;
        }
        cc_pad_states[cc_pad_count++]=r;
    }
    int failed=ferror(f) || !cc_pad_count;fclose(f);return failed?-1:0;
}
