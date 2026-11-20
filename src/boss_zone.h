#ifndef SCD_BOSS_ZONE_H
#define SCD_BOSS_ZONE_H
/* A boss round's services, from its zone's code overlay (src/saturn.x, heap plan B).
   src/boss.c reaches round 3 (src/boss_r3.c) and round 4 (src/boss_r4.c) boss code
   only through r3_boss_zone_ops and r4_boss_zone_ops, picked by the running round;
   tools/test_zone_code.py rejects any other resident call into an overlay.
   routine: ACT33C.C/ACT43C.C act_tbl[actno-1], NULL for other ids.
   pcol: the round's COLI pcol (PLAYER.C play01). Include EQU.H first. */
typedef struct {
    void (*(*routine)(unsigned id))(sprite_status *);
    short (*pcol)(sprite_status *p);
    /* colorset2: the round's own COL colorset2 (R8 COL8C/D.C fills lpcolorwk/lpcolorwk2), NULL elsewhere. */
    void (*colorset2)(int color);
} scd_boss_zone_ops;
#endif
