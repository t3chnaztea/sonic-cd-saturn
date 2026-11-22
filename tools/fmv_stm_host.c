/* Host driver for src/fmv_stm.c (never linked into the Saturn build).
 *   fmv_stm_host digest STM KIND               packet list, frame and PCM FNV-1a hashes
 *   fmv_stm_host ppm STM KIND PACKET FRAME OUT one picture as a binary PPM (MD DAC levels)
 *   fmv_stm_host wav STM OUT                   PCM as 8-bit unsigned mono WAV
 * KIND is "opening", "ending" or "mute" (PTEST.STM: PACKET is the 5-sector bank,
 * FRAME 0). ANIM frames render as their 120 x 80 window, MUTE ones as 168 x 112.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../src/fmv_stm.h"

static uint8_t *load(const char *path, size_t *size)
{
    FILE *f = fopen(path, "rb");
    if (!f) { perror(path); exit(1); }
    fseek(f, 0, SEEK_END);
    *size = (size_t)ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t *data = malloc(*size ? *size : 1);
    if (!data || fread(data, 1, *size, f) != *size) { fprintf(stderr, "read %s\n", path); exit(1); }
    fclose(f);
    return data;
}

static uint32_t fnv(uint32_t h, const void *p, size_t n)
{
    const uint8_t *b = p;
    while (n--) { h ^= *b++; h *= 16777619u; }
    return h;
}

static void le32(FILE *f, uint32_t v) { uint8_t b[4] = {v, v >> 8, v >> 16, v >> 24}; fwrite(b, 1, 4, f); }
static void le16(FILE *f, uint16_t v) { uint8_t b[2] = {v, v >> 8}; fwrite(b, 1, 2, f); }

static const char *type_name[] = {"video", "still", "anim", "hold", "resume", "empty", "unknown", "mute"};

int main(int argc, char **argv)
{
    if (argc < 3) { fprintf(stderr, "usage: %s digest|ppm|wav STM ...\n", argv[0]); return 2; }
    size_t size;
    uint8_t *stm = load(argv[2], &size);
    static uint16_t md[FMV_WIDTH * FMV_HEIGHT];
    static int8_t pcm[FMV_PCM_CYCLE_BYTES];
    fmv_stream_kind_t kind = FMV_STREAM_OPENING;
    if (argc > 3 && !strcmp(argv[3], "ending"))
        kind = FMV_STREAM_ENDING;
    else if (argc > 3 && !strcmp(argv[3], "mute"))
        kind = FMV_STREAM_MUTE;
    fmv_packet_t packet;
    fmv_frame_t frame;

    if (!strcmp(argv[1], "digest") && argc == 4) {
        unsigned packets = fmv_stm_kind_packet_count(size, kind);
        printf("size %zu packets %u\n", size, packets);
        for (unsigned c = 0; c < packets; c++) {
            fmv_stm_packet(stm, size, kind, c, &packet);
            printf("packet %u %s %u\n", c, type_name[packet.type], packet.frames);
            for (unsigned i = 0; i < packet.frames; i++) {
                fmv_packet_frame(&packet, i, &frame);
                fmv_frame_render_md(&frame, md);
                /* Hash big-endian MD words so Python can reproduce it. */
                uint32_t h = 2166136261u;
                for (unsigned p = 0; p < frame.tiles_w * frame.tiles_h * 64u; p++) {
                    uint8_t w[2] = {md[p] >> 8, md[p] & 255};
                    h = fnv(h, w, 2);
                }
                printf("frame %u %u %08x\n", c, i, h);
            }
            if (kind != FMV_STREAM_MUTE && !fmv_stm_pcm(stm, size, c, pcm))
                printf("pcm %u %08x\n", c, fnv(2166136261u, pcm, sizeof pcm));
        }
        return 0;
    }
    if (!strcmp(argv[1], "ppm") && argc == 7) {
        unsigned c = (unsigned)atoi(argv[4]);
        if (fmv_stm_packet(stm, size, kind, c, &packet) ||
            fmv_packet_frame(&packet, (unsigned)atoi(argv[5]), &frame)) {
            fprintf(stderr, "no frame\n");
            return 1;
        }
        fmv_frame_render_md(&frame, md);
        FILE *f = fopen(argv[6], "wb");
        if (!f) { perror(argv[6]); return 1; }
        fprintf(f, "P6\n%u %u\n255\n", frame.tiles_w * 8u, frame.tiles_h * 8u);
        for (unsigned p = 0; p < frame.tiles_w * frame.tiles_h * 64u; p++) {
            uint8_t rgb[3];
            fmv_md_to_rgb888(md[p], rgb);
            fwrite(rgb, 1, 3, f);
        }
        fclose(f);
        return 0;
    }
    if (!strcmp(argv[1], "wav") && argc == 4) {
        unsigned packets = fmv_stm_packet_count(size), n = 0;
        FILE *f = fopen(argv[3], "wb");
        if (!f) { perror(argv[3]); return 1; }
        uint32_t rate = (uint32_t)(((uint64_t)FMV_PCM_RATE_NUM + FMV_PCM_RATE_DEN / 2) / FMV_PCM_RATE_DEN);
        fwrite("RIFF\0\0\0\0WAVEfmt ", 1, 16, f);
        le32(f, 16); le16(f, 1); le16(f, 1); le32(f, rate); le32(f, rate); le16(f, 1); le16(f, 8);
        fwrite("data\0\0\0\0", 1, 8, f);
        for (unsigned c = 0; c < packets; c++) {
            if (fmv_stm_pcm(stm, size, c, pcm)) break;
            for (unsigned i = 0; i < FMV_PCM_CYCLE_BYTES; i++) fputc(pcm[i] + 128, f);
            n += FMV_PCM_CYCLE_BYTES;
        }
        fseek(f, 4, SEEK_SET); le32(f, 36 + n);
        fseek(f, 40, SEEK_SET); le32(f, n);
        fclose(f);
        return 0;
    }
    fprintf(stderr, "bad arguments\n");
    return 2;
}
