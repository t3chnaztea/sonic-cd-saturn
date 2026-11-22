/* Independent exact 16-byte literal-run check. No game data is compiled in.
 * Corpus TSV: file offset, byte length, path, separated by tabs. The scanner
 * indexes the small literal payload, then streams the large private corpus. */
#define _POSIX_C_SOURCE 200809L
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>

typedef struct { uint8_t bytes[16]; uint64_t position; } entry;
static uint64_t fingerprint(const uint8_t *p)
{
    uint64_t v, w; memcpy(&v, p, sizeof v); memcpy(&w, p+8, sizeof w);
    v ^= (w << 17) | (w >> 47);
    v ^= v >> 33; v *= UINT64_C(0xff51afd7ed558ccd);
    v ^= v >> 33; v *= UINT64_C(0xc4ceb9fe1a85ec53);
    return v ^ (v >> 33);
}
int main(int argc, char **argv)
{
    if (argc < 4 || argc > 6 || (argc == 6 && strcmp(argv[5], "--all"))) { fprintf(stderr, "usage: scanner BUNDLE PAYLOAD_OFFSET CORPUS.tsv [LITERAL_RANGES.tsv [--all]]\n"); return 2; }
    int all = argc == 6;
    char *end;
    uint64_t prefix = strtoull(argv[2], &end, 10);
    if (*end) return 2;
    FILE *bundle = fopen(argv[1], "rb"), *list = fopen(argv[3], "r");
    if (!bundle || !list) { perror("audit input"); return 2; }
    if (fseeko(bundle, 0, SEEK_END)) return 2;
    off_t total = ftello(bundle);
    if (total < 0 || prefix > (uint64_t)total || (uint64_t)total-prefix > 16*1024*1024) return 2;
    size_t size = (size_t)((uint64_t)total-prefix), capacity = 1;
    while (capacity < (size ? size*2 : 1)) capacity *= 2;
    entry *table = calloc(capacity, sizeof *table);
    uint8_t *payload = malloc(size ? size : 1), *buffer = malloc(1024*1024+15);
    if (!table || !payload || !buffer) return 2;
    if (fseeko(bundle, (off_t)prefix, SEEK_SET) || fread(payload, 1, size, bundle) != size) return 2;
    FILE *ranges = argc >= 5 ? fopen(argv[4], "r") : NULL;
    if (argc >= 5 && !ranges) return 2;
    uint64_t begin = 0, count = size; char range_line[128];
    do {
        if (ranges) {
            if (!fgets(range_line, sizeof range_line, ranges)) break;
            char extra;
            if (sscanf(range_line, "%" SCNu64 "\t%" SCNu64 " %c", &begin, &count, &extra) != 2 || begin > size || count > size-begin) return 2;
        }
        for (size_t i = (size_t)begin; i+16 <= begin+count; ++i) {
            size_t slot = fingerprint(payload+i) & (capacity-1);
            while (table[slot].position && memcmp(table[slot].bytes, payload+i, 16)) slot = (slot+1)&(capacity-1);
            if (!table[slot].position) { memcpy(table[slot].bytes, payload+i, 16); table[slot].position = i+1; }
        }
    } while (ranges);
    if (ranges) { if (ferror(ranges)) return 2; fclose(ranges); }
    char line[8192]; uint64_t scanned = 0, row = 0, matches = 0;
    while (fgets(line, sizeof line, list)) {
        ++row;
        char *tab = strchr(line, '\t'); if (!tab) return 2; *tab++ = 0;
        uint64_t start = strtoull(line, &end, 10); if (*end) return 2;
        char *filename = strchr(tab, '\t'); if (!filename) return 2; *filename++ = 0;
        uint64_t length = strtoull(tab, &end, 10); if (*end) return 2;
        size_t namesize = strlen(filename);
        if (!namesize || filename[namesize-1] != '\n') return 2;
        filename[namesize-1] = 0;
        FILE *source = fopen(filename, "rb"); if (!source) { perror("corpus input"); return 2; }
        if (fseeko(source, (off_t)start, SEEK_SET)) return 2;
        uint64_t read_total = 0; size_t carry = 0;
        while (read_total < length) {
            size_t count = length-read_total > 1024*1024 ? 1024*1024 : (size_t)(length-read_total);
            size_t got = fread(buffer+carry, 1, count, source);
            if (got != count) { fprintf(stderr, "truncated corpus range\n"); return 2; }
            size_t held = carry+got;
            for (size_t i = 0; i+16 <= held; ++i) {
                size_t slot = fingerprint(buffer+i)&(capacity-1);
                while (table[slot].position) {
                    if (!memcmp(table[slot].bytes, buffer+i, 16)) {
                        if (!(table[slot].position >> 63)) {
                            printf("FAIL: literal-run match; literal=%" PRIu64 " corpus=%" PRIu64 " offset=%" PRIu64 "\n",
                                   table[slot].position-1, row, start+read_total-carry+i);
                            ++matches;
                            table[slot].position |= UINT64_C(1) << 63;
                        }
                        if (!all) return 1;
                        break;
                    }
                    slot = (slot+1)&(capacity-1);
                }
            }
            read_total += got; scanned += got;
            carry = held < 15 ? held : 15;
            memmove(buffer, buffer+held-carry, carry);
        }
        fclose(source);
    }
    if (ferror(list)) return 2;
    printf("%s: literal-run scan; %zu literal bytes; %" PRIu64 " corpus bytes; %" PRIu64 " matches\n", matches ? "FAIL" : "PASS", size, scanned, matches);
    fclose(bundle); fclose(list); free(table); free(payload); free(buffer); return matches ? 1 : 0;
}
