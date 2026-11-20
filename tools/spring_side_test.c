/* Spring side hit: native spring_step side block (patched) vs RIDECHK.C ride_on_chk, actno 10. */
#include "EQU.H"
#include "RIDECHK.H"
#include <stdio.h>
#include <string.h>
short playdieset(sprite_status *p){(void)p;return 0;}
void soundset(short s){(void)s;}
#include "DIRCOL.H"
short dircol(sprite_status *p,char *d){(void)p;(void)d;return 0;}
short dircolm(sprite_status *p,char *d){(void)p;(void)d;return 0;}
short dircol_d(sprite_status *p,short *a,short *b,short *c){(void)p;*a=*b=*c=0;return 0;}
short dircol_u2(sprite_status *p){(void)p;return 0;}
static void native(sprite_status *o,sprite_status *p){
    int x=p->xposi.w.h,y=p->yposi.w.h,ox=o->xposi.w.h,oy=o->yposi.w.h;
    int hw=o->sprhsize,hh=o->sprvsize,pr=p->sprvsize,dx=x-ox,dy=y-oy;(void)x;(void)y;
#include SPRING_SIDE_BLOCK
}
int main(void){
    unsigned n=0,bad=0,side=0;
    for(int air=0;air<=2;air+=2)for(int xv=-600;xv<=600;xv+=300)for(int dx=-40;dx<=40;dx++)for(int dy=-50;dy<=50;dy++){
        sprite_status o={0},p={0};
        o.actno=10;o.actflg=128;o.sprhsize=16;o.sprvsize=8;o.xposi.w.h=1424;o.yposi.w.h=1144;
        p.actno=1;p.sprvsize=14;p.sprhsize=7;p.xposi.w.h=1424+dx;p.yposi.w.h=1144+dy;p.cddat=air|4;p.xspeed.w=xv;p.mspeed.w=xv;p.colino=0;
        sprite_status po=o,pp=p,no=o,np=p;
        actwk[0]=pp;actwk[1]=po;ride_on_chk(&actwk[1],&actwk[0]);po=actwk[1];pp=actwk[0];
        if(pp.yposi.w.h!=p.yposi.w.h || (pp.cddat&8) || pp.yspeed.w!=p.yspeed.w)continue; /* hit_y (top/bottom) path: native handles separately */
        native(&no,&np);n++;
        if(pp.xposi.w.h!=p.xposi.w.h)side++;
        if(np.xposi.w.h!=pp.xposi.w.h||np.xspeed.w!=pp.xspeed.w||np.mspeed.w!=pp.mspeed.w||(np.cddat&32)!=(pp.cddat&32)||(no.cddat&32)!=(po.cddat&32)||np.colino!=pp.colino){
            if(bad++<8)printf("diff air=%d xv=%d dx=%d dy=%d: pc x=%d xv=%d mv=%d pc=%x oc=%x col=%d | nat x=%d xv=%d mv=%d pc=%x oc=%x col=%d\n",air,xv,dx,dy,pp.xposi.w.h,pp.xspeed.w,pp.mspeed.w,pp.cddat&32,po.cddat&32,pp.colino,np.xposi.w.h,np.xspeed.w,np.mspeed.w,np.cddat&32,no.cddat&32,np.colino);}
    }
    printf("%s: %u cases, %u side hits, %u mismatches\n",bad?"FAIL":"PASS",n,side,bad);return bad!=0;
}
