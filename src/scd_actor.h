#ifndef SCD_ACTOR_H
#define SCD_ACTOR_H
/* PC scratch words are little-endian bytes, regardless of pointer size/CPU. */
/* Include after EQU.H, whose upstream TYPES.H has no include guard. */
static inline unsigned scd_word_get(const sprite_status *p,unsigned word) {
    unsigned byte=word*2-46;
    return p->actfree[byte]|((unsigned)p->actfree[byte+1]<<8);
}
static inline void scd_word_set(sprite_status *p,unsigned word,unsigned value) {
    unsigned byte=word*2-46;
    p->actfree[byte]=value;p->actfree[byte+1]=value>>8;
}
#endif
