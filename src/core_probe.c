#include "TYPES.H"
#include "ACTION.H"
#include <stddef.h>

_Static_assert(sizeof(int)==4 && sizeof(short)==2,"engine integer widths");
_Static_assert(offsetof(sprite_status,xposi)==8,"actor X offset");
_Static_assert(offsetof(sprite_status,actfree)==46,"actor scratch offset");
_Static_assert(sizeof(sprite_status)==68,"actor stride");

/* Run reconstructed game code on the target, with an independent integer
 * reference for positive/negative velocity, gravity and terminal velocity.
 * Returns zero on success. This is not a full player/collision replay. */
int scd_core_probe(void) {
    int_union word;short_union half;
    word.l=0x12345678;half.w=0x1234;
    if(word.w.h!=0x1234 || (unsigned short)word.w.l!=0x5678 ||
       (unsigned char)word.b.b1!=0x12 || (unsigned char)word.b.b4!=0x78 ||
       half.b.h!=0x12 || half.b.l!=0x34)return 1;
    for(int direction=-1;direction<=1;direction+=2) {
        sprite_status actor={0};
        int x=100*65536,y=300*65536,velocity=-2048;
        actor.xposi.l=x;actor.yposi.l=y;
        actor.xspeed.w=direction*384;actor.yspeed.w=velocity;
        for(int frame=0;frame<180;frame++) {
            x+=direction*384*256;y+=velocity*256;
            velocity+=56;if(velocity>4096)velocity=4096;
            speedset(&actor);
            if(actor.xposi.l!=x || actor.yposi.l!=y || actor.yspeed.w!=velocity)return 2;
            if(actor.xposi.w.h!=(short)(x>>16))return 3;
        }
    }
    sprite_status actor={0};actor.actfree[2]=4;actor.yspeed.w=-512;
    speedset(&actor);
    if(actor.yspeed.w!=-512 || actor.yposi.l!=-131072)return 4;
    return 0;
}
