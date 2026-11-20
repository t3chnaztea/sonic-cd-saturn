#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "powerup_visual.h"
int main(void){
    _Static_assert(sizeof(scd_powerup_visual)==18,"actor test ABI");
    _Static_assert(sizeof(scd_powerup_context)==268,"context test ABI");
    FILE *f=fopen("build/powerup-visual/retail-cases.bin","rb");assert(f);
    scd_powerup_visual state,expected;scd_powerup_context context;unsigned cases=0;
    while(fread(&state,sizeof(state),1,f)==1){
        assert(fread(&context,sizeof(context),1,f)==1 && fread(&expected,sizeof(expected),1,f)==1);
        int powerup=fgetc(f),submission=fgetc(f);assert(powerup>=0 && submission>=0);
        assert(scd_powerup_visual_step(&state,&context)==submission);
        assert(!memcmp(&state,&expected,sizeof(state)) && context.powerup==powerup);cases++;
    }
    assert(feof(f) && cases>27000);fclose(f);
    memset(&state,0,sizeof(state));memset(&context,0,sizeof(context));
    assert(scd_powerup_visual_step(&state,&context)==0);
    state.active=3;state.animation=9;assert(scd_powerup_visual_step(&state,&context)==-1);
    state.animation=0;state.routine=8;assert(scd_powerup_visual_step(&state,&context)==-1);
    printf("Power-up visual: %u sanitized retail cases, inactive/invalid states passed\n",cases);
}
