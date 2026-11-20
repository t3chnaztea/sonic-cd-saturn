/* Act 2 swing (object 0x29): run the PC reconstruction's BRANKO1.C and the
 * native scheduler side by side and require the same pivot, chain and platform
 * positions every update, for all eight swing tables and 1-6 pieces. */
#include "EQU.H"
#include "scd_objects.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

void branko1(sprite_status *pActwk);
static sprite_status pc[8];
static unsigned pc_count;
int actwkchk(sprite_status **ppActwk){
    if(pc_count>=8)return -1;
    memset(&pc[pc_count],0,sizeof(pc[0]));*ppActwk=&pc[pc_count++];return 0;
}
void actionsub(sprite_status *pActwk){(void)pActwk;}
int frameout_s00(sprite_status *pActwk,short xposi){(void)pActwk;(void)xposi;return 0;}
void pa_set(){}
short ridechk(sprite_status *pActwk,sprite_status *pPlayerwk){(void)pActwk;(void)pPlayerwk;return 0;}

static int compare(const void *a,const void *b){
    const int *x=a,*y=b;return x[0]!=y[0]?x[0]-y[0]:x[1]!=y[1]?x[1]-y[1]:x[2]-y[2];
}
int main(void){
    unsigned cases=0,updates=0;
    for(unsigned table=0;table<8;table++)for(unsigned pieces=1;pieces<=6;pieces++){
        unsigned sub=(table<<4)|pieces;
        scd_objects_reset(0,0);
        memset(&actwk[0],0,sizeof(actwk[0]));
        actwk[0].xposi.w.h=6816;actwk[0].yposi.w.h=100;actwk[0].r_no0=6;
        if(scd_objects_spawn(SCD_OBJ_SWING,6816,392,sub,0)<0)return 2;
        pc_count=0;sprite_status *root;actwkchk(&root);
        root->actno=41;root->xposi.w.h=6816;root->yposi.w.h=392;root->userflag.b.h=sub;
        for(unsigned frame=0;frame<700;frame++){
            /* Source order: the pivot runs, then pieces it created later that update. */
            for(unsigned i=0;i<pc_count;i++)branko1(&pc[i]);
            scd_objects_step(6816,100);
            int expected[8][3],actual[8][3];unsigned n=0,m=0;
            for(unsigned i=0;i<pc_count;i++){expected[n][0]=pc[i].xposi.w.h;expected[n][1]=pc[i].yposi.w.h;expected[n++][2]=pc[i].patno;}
            scd_object_view views[SCD_OBJECT_CAPACITY];unsigned total=scd_objects_views(views,SCD_OBJECT_CAPACITY);
            for(unsigned i=0;i<total && m<8;i++)if(views[i].type==SCD_OBJ_SWING){actual[m][0]=views[i].x;actual[m][1]=views[i].y;actual[m++][2]=views[i].frame;}
            qsort(expected,n,sizeof(expected[0]),compare);qsort(actual,m,sizeof(actual[0]),compare);
            if(n!=m || memcmp(expected,actual,sizeof(expected[0])*n)){
                fprintf(stderr,"Swing mismatch table=%u pieces=%u frame=%u pieces PC=%u native=%u\n",table,pieces,frame,n,m);
                for(unsigned i=0;i<n || i<m;i++)fprintf(stderr,"  PC %d,%d f%d  native %d,%d f%d\n",i<n?expected[i][0]:0,i<n?expected[i][1]:0,i<n?expected[i][2]:0,i<m?actual[i][0]:0,i<m?actual[i][1]:0,i<m?actual[i][2]:0);
                return 1;
            }
            updates++;
        }
        cases++;
    }
    printf("Swing host/PC match: %u cases, %u updates (BRANKO1.C tables 0-7, 1-6 pieces)\n",cases,updates);
    return 0;
}
