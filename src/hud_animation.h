#ifndef SCD_HUD_ANIMATION_H
#define SCD_HUD_ANIMATION_H
#include <stdint.h>
/* ObjHUD_Main (.Rings): collecting a ring clears the palette bit. At zero
   rings, only an object update on a multiple-of-16 V-INT toggles it. This is
   stateful; selecting a color from the simulation frame loses the phase after
   collecting/losing rings, pausing, or a missed refresh. */
static inline uint8_t scd_hud_ring_step(uint8_t red, uint32_t vint, unsigned rings) {
    if(rings)return 0;
    return red ^ ((vint&15u)==0);
}
#endif
