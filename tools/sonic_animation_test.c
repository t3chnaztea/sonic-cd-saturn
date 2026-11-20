#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "sonic_animation.h"
#include "sonic_art.h"
static unsigned read_word(const unsigned char *p){return (unsigned)p[0]<<8|p[1];}
int main(void){
    _Static_assert(sizeof(scd_sonic_animation)==6,"animation record layout");
    FILE *f=fopen("build/sonic-animation/retail-cases.bin","rb");assert(f);
    unsigned char row[17];unsigned count=0;
    for(;;){
        size_t n=fread(row,1,sizeof(row),f);if(!n){assert(feof(f));break;}assert(n==sizeof(row));
        scd_sonic_animation s;memcpy(&s,row,6);
        assert(!scd_sonic_animate(&s,(int16_t)read_word(row+6),row[8],row[9],row[10]));
        assert(!memcmp(&s,row+11,6));count++;
    }
    fclose(f);assert(count>100000);
    for(unsigned id=60;id<256;id++){
        scd_sonic_animation s={(uint8_t)id,0,0,0,0,0},before=s;
        assert(scd_sonic_animate(&s,0,0,0,0)==-1);assert(!memcmp(&s,&before,sizeof(s)));
    }
    for(unsigned id=0;id<60;id++){
        scd_sonic_animation s={(uint8_t)id,(uint8_t)id,255,0,0,0},before=s;
        assert(scd_sonic_animate(&s,0,0,0,0)==-1);assert(!memcmp(&s,&before,sizeof(s)));
    }
    f=fopen("assets/generated/sonic-source.bin","rb");assert(f);assert(!fseek(f,0,SEEK_END));
    long size=ftell(f);assert(size>0);rewind(f);unsigned char *data=malloc((size_t)size);assert(data);
    assert(fread(data,1,(size_t)size,f)==(size_t)size);fclose(f);
    scd_sonic_art art;assert(!scd_sonic_art_open(&art,data,(size_t)size));
    struct {uint16_t before,pixels[1024],after;} guarded={.before=0x1357,.after=0x2468};
    f=fopen("build/sonic-animation/expected-frames.bin","rb");assert(f);
    unsigned char expected[8192];unsigned opaque=0;
    for(unsigned frame=0;frame<SCD_SONIC_FRAME_COUNT;frame++){
        assert(fread(expected,1,sizeof(expected),f)==sizeof(expected));
        assert(!scd_sonic_art_decode(&art,frame,guarded.pixels));
        assert(guarded.before==0x1357 && guarded.after==0x2468);
        for(unsigned i=0;i<4096;i++){
            unsigned index=guarded.pixels[i/4]>>((3-(i&3))*4)&15;
            unsigned color=scd_sonic_art_color(&art,index);
            assert(color==read_word(expected+i*2));opaque+=index!=0;
        }
    }
    assert(fgetc(f)==EOF);fclose(f);
    assert(scd_sonic_art_decode(&art,SCD_SONIC_FRAME_COUNT,guarded.pixels)==-1);
    for(size_t n=0;n<(size_t)size;n++)assert(scd_sonic_art_open(&art,data,n)==-1);
    assert(!scd_sonic_art_open(&art,data,(size_t)size));
    scd_sonic_art broken=art;broken.size[0]=0;
    assert(scd_sonic_art_decode(&broken,1,guarded.pixels)==-1);
    broken=art;broken.size[1]=SCD_SONIC_FRAME_COUNT*2;
    assert(scd_sonic_art_decode(&broken,1,guarded.pixels)==-1);
    broken=art;broken.size[2]=SCD_SONIC_FRAME_COUNT*2;
    assert(scd_sonic_art_decode(&broken,1,guarded.pixels)==-1);
    free(data);
    printf("Sanitized Sonic animation: %u exact retail cases; all 198 poses, 811008 pixels (%u opaque); invalid states/truncated packs rejected\n",count,opaque);
}
