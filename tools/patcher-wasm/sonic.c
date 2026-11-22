/* CLI for the existing pure source decoder. Outputs BE colors and pose words. */
#include <stdio.h>
#include <stdlib.h>
#include "sonic_art.h"
int main(int argc, char **argv)
{
    if (argc != 3) return 2;
    FILE *f = fopen(argv[1], "rb"); if (!f) return 3;
    fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f);
    unsigned char *data = malloc(n);
    if (!data || fread(data, 1, n, f) != (size_t)n) return 4;
    fclose(f);
    scd_sonic_art art;
    if (scd_sonic_art_open(&art, data, n)) return 5;
    f = fopen(argv[2], "wb"); if (!f) return 6;
    for (unsigned k = 0; k < 16; k++) {
        uint16_t v = scd_sonic_art_color(&art, k); fputc(v >> 8, f); fputc(v & 255, f);
    }
    uint16_t pixels[1024];
    for (unsigned frame = 0; frame < 198; frame++) {
        if (scd_sonic_art_decode(&art, frame, pixels)) return 7;
        for (unsigned k = 0; k < 1024; k++) { fputc(pixels[k] >> 8, f); fputc(pixels[k] & 255, f); }
    }
    fclose(f); free(data); return 0;
}
