#include "fmv_fe_names.h"
#include "fmv_stm.h"

/* Mega Drive DAC output levels for 3-bit channels (normal, non-shadow). */
static const uint8_t md_levels[8] = {0, 52, 87, 116, 144, 172, 206, 255};

unsigned fmv_stm_packet_count(size_t size)
{
    return (unsigned)((size + FMV_CYCLE_BYTES - 1) / FMV_CYCLE_BYTES);
}

unsigned fmv_stm_kind_packet_count(size_t size, fmv_stream_kind_t kind)
{
    if (kind == FMV_STREAM_MUTE)
        return (unsigned)((size + FMV_MUTE_BANK_BYTES - 1) / FMV_MUTE_BANK_BYTES);
    return fmv_stm_packet_count(size);
}

static fmv_packet_type_t tag_type(const uint8_t *h)
{
    unsigned tag = (unsigned)h[0] << 8 | h[1];
    switch (tag) {
    case 0x3038: return FMV_PACKET_VIDEO;  /* "08" */
    case 0x5352: return FMV_PACKET_STILL;  /* "SR" */
    case 0x3135: return FMV_PACKET_ANIM;   /* "15" */
    case 0x4E4F: return FMV_PACKET_HOLD;   /* "NO" */
    case 0x5253: return FMV_PACKET_RESUME; /* "RS" */
    case 0x0000: return FMV_PACKET_EMPTY;
    default: return FMV_PACKET_UNKNOWN;
    }
}

int fmv_stm_packet(const uint8_t *stm, size_t size, fmv_stream_kind_t kind,
                   unsigned index, fmv_packet_t *out)
{
    out->frames = 0;
    if (kind == FMV_STREAM_MUTE) {
        /* PTEST.MMD skips the bank's 16-byte header without acting on its tag. */
        size_t at = (size_t)index * FMV_MUTE_BANK_BYTES;
        size_t avail = at < size ? size - at : 0;
        if (avail > FMV_MUTE_BANK_BYTES)
            avail = FMV_MUTE_BANK_BYTES;
        out->type = FMV_PACKET_MUTE;
        out->gfx = stm + (avail > FMV_HEADER_BYTES ? at + FMV_HEADER_BYTES : size);
        out->gfx_bytes = avail > FMV_HEADER_BYTES ? avail - FMV_HEADER_BYTES : 0;
        out->frames = out->gfx_bytes >= FMV_MUTE_FRAME_BYTES;
        return index < fmv_stm_kind_packet_count(size, kind) ? 0 : -1;
    }
    size_t at = (size_t)index * FMV_CYCLE_BYTES + FMV_GFX_OFFSET;
    size_t avail = at < size ? size - at : 0;
    if (avail > FMV_GFX_BYTES)
        avail = FMV_GFX_BYTES;
    if (kind == FMV_STREAM_OPENING) {
        out->type = FMV_PACKET_VIDEO;
        out->gfx = stm + at;
        out->gfx_bytes = avail;
    } else {
        if (avail < FMV_HEADER_BYTES) {
            out->type = FMV_PACKET_EMPTY;
            out->gfx = stm + size;
            out->gfx_bytes = 0;
            return index < fmv_stm_packet_count(size) ? 0 : -1;
        }
        out->type = tag_type(stm + at);
        out->gfx = stm + at + FMV_HEADER_BYTES;
        out->gfx_bytes = avail - FMV_HEADER_BYTES;
    }
    if (out->type == FMV_PACKET_VIDEO) {
        out->frames = (unsigned)(out->gfx_bytes / FMV_FRAME_BYTES);
        if (out->frames > FMV_FRAMES_PER_CYCLE)
            out->frames = FMV_FRAMES_PER_CYCLE;
    } else if (out->type == FMV_PACKET_ANIM) {
        out->frames = (unsigned)(out->gfx_bytes / FMV_ANIM_FRAME_BYTES);
        if (out->frames > FMV_ANIM_FRAMES)
            out->frames = FMV_ANIM_FRAMES;
    }
    return index < fmv_stm_packet_count(size) ? 0 : -1;
}

int fmv_packet_frame(const fmv_packet_t *packet, unsigned index, fmv_frame_t *out)
{
    size_t stride;
    if (index >= packet->frames)
        return -1;
    if (packet->type == FMV_PACKET_VIDEO) {
        stride = FMV_FRAME_BYTES;
        out->tiles_w = FMV_TILES_W;
        out->tiles_h = FMV_TILES_H;
    } else if (packet->type == FMV_PACKET_MUTE) {
        stride = FMV_MUTE_FRAME_BYTES;
        out->tiles_w = FMV_MUTE_TILES_W;
        out->tiles_h = FMV_MUTE_TILES_H;
    } else {
        stride = FMV_ANIM_FRAME_BYTES;
        out->tiles_w = FMV_ANIM_TILES_W;
        out->tiles_h = FMV_ANIM_TILES_H;
    }
    const uint8_t *p = packet->gfx + index * stride;
    for (unsigned i = 0; i < 16; i++)
        out->palette[i] = (uint16_t)(p[i * 2] << 8 | p[i * 2 + 1]);
    out->tiles = p + FMV_PALETTE_BYTES;
    return 0;
}

unsigned fmv_frame_pixel(const fmv_frame_t *frame, unsigned x, unsigned y)
{
    /* All layouts are row-major tile runs (DrawFMVTilemaps; the ENDING.MMD map;
     * PTEST.MMD $FF23C0, 21 tiles a row from tile $10 or $136). */
    unsigned tile = (y >> 3) * frame->tiles_w + (x >> 3);
    uint8_t b = frame->tiles[tile * FMV_TILE_BYTES + (y & 7) * 4 + ((x & 7) >> 1)];
    return (x & 1) ? (b & 15u) : (b >> 4);
}

void fmv_frame_render_md(const fmv_frame_t *frame, uint16_t *out)
{
    /* Index 0 is transparent on plane A; the border plane holds a blank tile
     * there, so the backdrop (line 0 color 0) shows: palette[0] either way. */
    unsigned w = frame->tiles_w * 8u, h = frame->tiles_h * 8u;
    for (unsigned y = 0; y < h; y++)
        for (unsigned x = 0; x < w; x++)
            out[y * w + x] = frame->palette[fmv_frame_pixel(frame, x, y)];
}

uint16_t fmv_md_to_rgb555(uint16_t md)
{
    unsigned r = (md >> 1) & 7, g = (md >> 5) & 7, b = (md >> 9) & 7;
    /* Scale the DAC level, not the code, so ramps match the Sega CD output. */
    unsigned r5 = (md_levels[r] * 31u + 127u) / 255u;
    unsigned g5 = (md_levels[g] * 31u + 127u) / 255u;
    unsigned b5 = (md_levels[b] * 31u + 127u) / 255u;
    return (uint16_t)(b5 << 10 | g5 << 5 | r5);
}

void fmv_md_to_rgb888(uint16_t md, uint8_t rgb[3])
{
    rgb[0] = md_levels[(md >> 1) & 7];
    rgb[1] = md_levels[(md >> 5) & 7];
    rgb[2] = md_levels[(md >> 9) & 7];
}

int fmv_stm_pcm(const uint8_t *stm, size_t size, unsigned packet, int8_t *out)
{
    size_t at = (size_t)packet * FMV_CYCLE_BYTES;
    if (at + FMV_GFX_OFFSET > size)
        return -1;
    /* Sub (Opening).asm .StreamPCM: the source pointer runs on through all
     * 8 banks, $FFF bytes each, so the last 8 bytes of the packet are unused. */
    for (unsigned i = 0; i < FMV_PCM_CYCLE_BYTES; i++)
        out[i] = fmv_pcm_sample(stm[at + i]);
    return 0;
}
