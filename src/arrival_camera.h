#ifndef SCD_ARRIVAL_CAMERA_H
#define SCD_ARRIVAL_CAMERA_H
/* Prepare the arriving player's current view while display is disabled.
   This is the native gameplay camera projection/clamping, not a claim that
   the original game restored all of its saved camera/scroll state here. */
static inline void scd_arrival_camera(int player_x,int player_y,unsigned act,
        int left,int right,int bottom,int camera_line,int *x,int *y){
    *x=player_x-160;*y=player_y-140-(act==2?camera_line-96:0);
    if(*x<0)*x=0;
    if(*x>16064)*x=16064;
    if(*y<0)*y=0;
    int limit=act?bottom:1824;
    if(*y>limit)*y=limit;
    if(*x>right)*x=right;
    if(*x<left)*x=left;
}
#endif
