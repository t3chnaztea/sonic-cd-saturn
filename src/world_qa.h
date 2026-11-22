#ifndef SCD_WORLD_QA_H
#define SCD_WORLD_QA_H
#include <stddef.h>
#include <stdint.h>
int scd_world_probe(const uint8_t *const *packs,const size_t *sizes,const uint8_t *const *collisions);
#endif
