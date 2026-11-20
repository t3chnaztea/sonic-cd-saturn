/* Per-update original oracle on a real host route. Link with objects.c built
   with -Dscd_objects_step=native_objects_step: every native object update
   near the player is repeated from the same before-state by the compiled
   original for3/frdr3 + RIDECHK.C, and the platforms, rider owner and player
   position are compared. Diagnostic only: other actors that touch the player
   in the same update are not modelled. */
#include "EQU.H"
#include "scd_objects.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
void for3(sprite_status*);void frdr3(sprite_status*);
void native_objects_step(int old_x,int old_y);
__attribute__((weak)) int actwkchk(sprite_status **out){for(unsigned i=108;i<128;i++)if(!actwk[i].actno){*out=&actwk[i];actwk[i].actflg=132;return 0;}return -1;}
__attribute__((weak)) int frameout_s(sprite_status *o){(void)o;return 0;}
__attribute__((weak)) void frameout(sprite_status *o){memset(o,0,sizeof(*o));}
__attribute__((weak)) int actwkchk2(sprite_status *o,sprite_status **out){for(o++;o<actwk+128;o++)if(!o->actno){*out=o;return 0;}return -1;}
__attribute__((weak)) short playdamageset(sprite_status *p,sprite_status *o){(void)p;(void)o;abort();}
__attribute__((weak)) short pcolplay(sprite_status *p,sprite_status *o){(void)p;(void)o;abort();}
__attribute__((weak)) short pcolnomal(sprite_status *p,sprite_status *o){(void)p;(void)o;abort();}
__attribute__((weak)) short pcolspecial(sprite_status *p,sprite_status *o){(void)p;(void)o;abort();}
__attribute__((weak)) short pcolitem(sprite_status *p,sprite_status *o){(void)p;(void)o;abort();}
__attribute__((weak)) void actionsub(sprite_status *o){if(o->actno)o->actflg|=128;}
__attribute__((weak)) void tr3_fout(sprite_status *o){(void)o;}
static unsigned probe_updates,probe_compared,probe_mismatch;
static unsigned map_id(unsigned id,const unsigned *idx,unsigned n){for(unsigned k=0;k<n;k++)if(id==idx[k])return 100+k;return id;}
static unsigned unmap_id(unsigned id,const unsigned *idx,unsigned n){return id>=100 && id<100+n?idx[id-100]:id;}
void scd_objects_step(int old_x,int old_y){
    static sprite_status before[97],after[97];
    memcpy(before,actwk,sizeof(before));
    native_objects_step(old_x,old_y);
    probe_updates++;
    unsigned idx[8],n=0;
    for(unsigned i=1;i<97 && n<8;i++)
        if((before[i].actno==SCD_OBJ_FOR3 || before[i].actno==SCD_OBJ_FRDR3) && before[i].r_no0 &&
           abs(before[i].xposi.w.h-before[0].xposi.w.h)<96 && abs(before[i].yposi.w.h-before[0].yposi.w.h)<96)idx[n++]=i;
    if(!n)return;
    memcpy(after,actwk,sizeof(after));
    sprite_status saved[28];memcpy(saved,actwk+100,sizeof(saved));
    actwk[0]=before[0];
    actwk[0].actfree[19]=(unsigned char)map_id(actwk[0].actfree[19],idx,n);
    actwk[0].colino=(unsigned char)map_id(actwk[0].colino,idx,n);
    for(unsigned k=0;k<n;k++){actwk[100+k]=before[idx[k]];actwk[100+k].actflg=after[idx[k]].actflg;}
    /* Map ride/push ids held by the platforms themselves only via the player. */
    for(unsigned k=0;k<n;k++)if(actwk[100+k].actno==SCD_OBJ_FOR3)for3(&actwk[100+k]);else frdr3(&actwk[100+k]);
    sprite_status player=actwk[0];
    player.actfree[19]=(unsigned char)unmap_id(player.actfree[19],idx,n);
    player.colino=(unsigned char)unmap_id(player.colino,idx,n);
    int bad=player.actfree[19]!=after[0].actfree[19] || (player.cddat&8)!=(after[0].cddat&8) ||
            player.yposi.l!=after[0].yposi.l || player.xposi.l!=after[0].xposi.l;
    for(unsigned k=0;k<n;k++){
        const sprite_status *a=&after[idx[k]],*b=&actwk[100+k];
        if(a->xposi.l!=b->xposi.l || a->yposi.l!=b->yposi.l || a->cddat!=b->cddat || a->r_no0!=b->r_no0 ||
           memcmp(a->actfree,b->actfree,sizeof(a->actfree)))bad=1;
    }
    probe_compared++;
    if(bad && probe_mismatch++<12){
        fprintf(stderr,"RIDE PROBE mismatch update=%u player before xy=%d,%d rider=%u | native xy=%d.%04x,%d.%04x rider=%u cddat=%u | original xy=%d.%04x,%d.%04x rider=%u cddat=%u\n",
                probe_updates,before[0].xposi.w.h,before[0].yposi.w.h,before[0].actfree[19],
                after[0].xposi.w.h,after[0].xposi.w.l,after[0].yposi.w.h,after[0].yposi.w.l,after[0].actfree[19],after[0].cddat,
                player.xposi.w.h,player.xposi.w.l,player.yposi.w.h,player.yposi.w.l,player.actfree[19],player.cddat);
        for(unsigned k=0;k<n;k++)fprintf(stderr,"  slot %u type %u native xy=%d,%d cddat=%u r=%u | original xy=%d,%d cddat=%u r=%u\n",
                idx[k],after[idx[k]].actno,after[idx[k]].xposi.w.h,after[idx[k]].yposi.w.h,after[idx[k]].cddat,after[idx[k]].r_no0,
                actwk[100+k].xposi.w.h,actwk[100+k].yposi.w.h,actwk[100+k].cddat,actwk[100+k].r_no0);
    }
    memcpy(actwk,after,sizeof(after));memcpy(actwk+100,saved,sizeof(saved));
}
__attribute__((destructor)) static void probe_summary(void){
    fprintf(stderr,"RIDE PROBE summary: updates=%u compared=%u mismatches=%u\n",probe_updates,probe_compared,probe_mismatch);
}
