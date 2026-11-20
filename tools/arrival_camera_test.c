#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include "arrival_camera.h"
static unsigned cases;
int main(void){
    /* Existing per-update native projection is the requirement. Keep the
       comparison expressed independently as clamps rather than helper calls. */
    for(unsigned act=0;act<3;act++)for(int left=0;left<=320;left+=160)
    for(int right=3479;right<=10391;right+=6912)
    for(int line=96;line<=136;line+=40)
    for(int py=-32;py<2100;py+=17)for(int px=-32;px<16500;px+=47){
        int bottom=act==2?784:1808,x,y;
        scd_arrival_camera(px,py,act,left,right,bottom,line,&x,&y);
        int expected_x=px-160,expected_y=py-140-(act==2?line-96:0);
        expected_x=expected_x<0?0:expected_x>16064?16064:expected_x;
        expected_x=expected_x>right?right:expected_x;
        expected_x=expected_x<left?left:expected_x;
        int limit=act?bottom:1824;
        expected_y=expected_y<0?0:expected_y>limit?limit:expected_y;
        assert(x==expected_x && y==expected_y);cases++;
    }
    int x,y;
    scd_arrival_camera(4760,417,0,0,10391,1808,96,&x,&y);assert(x==4600 && y==277);
    scd_arrival_camera(5616,236,1,0,10391,1808,96,&x,&y);assert(x==5456 && y==96);
    scd_arrival_camera(8821,641,1,0,10391,1808,96,&x,&y);assert(x==8661 && y==501);
    printf("Arrival camera: %u native projection/bounds cases and three recorded destinations\n",cases);
    return 0;
}
