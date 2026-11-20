#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#include "background_r3.h"

static uint64_t
clock_ns(void)
{
    struct timespec value;
    if (clock_gettime(CLOCK_MONOTONIC, &value) != 0) {
        perror("clock_gettime");
        exit(2);
    }
    return (uint64_t)value.tv_sec * UINT64_C(1000000000) +
           (uint64_t)value.tv_nsec;
}

static uint64_t
hash_word(uint64_t hash, uint32_t value)
{
    for (unsigned byte = 0; byte < 4; byte++) {
        hash ^= (value >> (byte * 8)) & 0xff;
        hash *= UINT64_C(1099511628211);
    }
    return hash;
}

static void
run_case(unsigned index, int32_t background[224], int32_t foreground[224])
{
    unsigned era = index & 3;
    int x = (int)((index * 977u + era * 131u) % 11000u);
    int top = (int)((index * 37u + era * 53u) & 767u);
    int camera_y = (int)((index * 61u + era * 211u) % 1536u);
    unsigned frame = index * 29u + era * 101u;
    int32_t layers[4] = {
        12 * x * 256,
        24 * x * 256,
        16 * x * 256,
        (index & 8) ? 65535 : 0
    };
    scd_r3_lines_layers(era, x, layers, camera_y, top, frame,
                        background, foreground, 224);
}

int
main(int argc, char **argv)
{
    unsigned iterations = 20000;
    if (argc == 2) {
        char *end = NULL;
        unsigned long parsed = strtoul(argv[1], &end, 10);
        if (!end || *end || parsed == 0 || parsed > 100000000UL) {
            fprintf(stderr, "usage: %s [iterations]\n", argv[0]);
            return 2;
        }
        iterations = (unsigned)parsed;
    } else if (argc != 1) {
        fprintf(stderr, "usage: %s [iterations]\n", argv[0]);
        return 2;
    }

    int32_t background[224], foreground[224];
    uint64_t fingerprint = UINT64_C(1469598103934665603);
    for (unsigned index = 0; index < 256; index++) {
        run_case(index, background, foreground);
        for (unsigned line = 0; line < 224; line++) {
            fingerprint = hash_word(fingerprint, (uint32_t)background[line]);
            fingerprint = hash_word(fingerprint, (uint32_t)foreground[line]);
        }
    }

    volatile uint32_t sink = 0;
    for (unsigned index = 0; index < 256; index++)
        run_case(index, background, foreground);
    uint64_t start = clock_ns();
    for (unsigned index = 0; index < iterations; index++) {
        run_case(index, background, foreground);
        sink ^= (uint32_t)background[(index * 17u) % 224u];
        sink ^= (uint32_t)foreground[(index * 43u) % 224u];
    }
    uint64_t elapsed = clock_ns() - start;
    printf("calls=%u elapsed_ns=%" PRIu64 " ns_per_call=%.3f "
           "fingerprint=%016" PRIx64 " sink=%08" PRIx32 "\n",
           iterations, elapsed, (double)elapsed / iterations,
           fingerprint, sink);
    return 0;
}
