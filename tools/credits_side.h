/* One side of the credits parity harness: src/credits.c (tools/credits_test.c)
   or the PC TITLE/THANKS sources (tools/credits_reference.c). */
#ifndef CREDITS_SIDE_H
#define CREDITS_SIDE_H
#include <stdint.h>

typedef struct {
    const int16_t *map_a, *map_b;   /* NULL: the map file is absent */
    const char (*names)[4];         /* 84 save-data initials or NULL */
    uint8_t ending_type;
    int seeded;
    int32_t seed;                   /* ranum after game_init */
} credits_side_config;

#define CREDITS_SNAPSHOT_MAX 12000

void side_init(const credits_side_config *config);
int side_frame(uint16_t pad);
/* Flat state in a fixed order shared by both sides; returns the count. */
unsigned side_snapshot(int32_t *out);

#endif
