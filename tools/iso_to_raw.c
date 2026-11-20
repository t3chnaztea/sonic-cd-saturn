/* Host-only disc packaging helper. Links the pinned Beetle/cdrdao LEC encoder.
 * The encoder is GPL-2.0-or-later; this helper uses the same license.
 * It is not linked into the Saturn executable. */
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include "lec.h"

int main(int argc, char **argv) {
    const int check = argc == 4 && !strcmp(argv[1], "--check-data");
    if (argc != 3 && !check) {
        fprintf(stderr, "Usage: iso_to_raw [--check-data] INPUT.iso OUTPUT.bin\n");
        return 1;
    }
    FILE *in = fopen(argv[check ? 2 : 1], "rb");
    if (!in) { perror("input"); return 1; }
    FILE *out = fopen(argv[check ? 3 : 2], check ? "rb" : "wb");
    if (!out) { perror("output"); fclose(in); return 1; }
    uint8_t sector[2352] = {0}, actual[2352];
    uint32_t address = 150;
    size_t count;
    int mismatch = 0, error = 0;
    lec_tables_init();
    while ((count = fread(sector + 16, 1, 2048, in)) != 0) {
        if (count != 2048) { fprintf(stderr, "Partial ISO sector\n"); error = 1; break; }
        lec_encode_mode1_sector(address++, sector);
        if (check) {
            const size_t got = fread(actual, 1, sizeof(actual), out);
            if (ferror(out)) { perror("existing BIN read"); error = 1; break; }
            if (got != sizeof(actual) || memcmp(sector, actual, sizeof(actual))) mismatch = 1;
            /* Continue through the ISO after a mismatch; a later I/O error
             * must not be mistaken for permission to rebuild an image. */
        } else if (fwrite(sector, 1, sizeof(sector), out) != sizeof(sector)) {
            perror("write"); error = 1; break;
        }
    }
    if (ferror(in)) { perror("read"); error = 1; }
    if (fclose(in)) { perror("input close"); error = 1; }
    if (fclose(out)) { perror("output close"); error = 1; }
    /* Check only the data-track prefix. Python checks audio/pregap/EOF. */
    return error ? 1 : mismatch ? 2 : 0;
}
