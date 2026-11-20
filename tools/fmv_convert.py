#!/usr/bin/env python3
"""Convert the Sonic CD STM movies into the Saturn stream format read by src/fmv_saturn.c.

Inputs are tools/fmv_extract.py outputs from the user's private disc (build/fmv/:
OPN.STM, GOODEND.STM, BADEND.STM, PTEST.STM, ENDING.MMD, PTEST.MMD). Outputs go to
cd/ (not in git): OPN.FMV, GOODEND.FMV, BADEND.FMV and PTEST.FMV. Nothing
SEGA-derived is committed.

Layout (big endian, 2048-byte sectors):
  sector 0      header (FMV_SAT_* in src/fmv_saturn.h); from byte 128 one
                byte per packet: type << 4 | frames, as fmv_extract.packets()
                and src/fmv_stm.c classify it (types: fmv_packet_type_t)
  sectors 1..   ending only: data ENDING.MMD's Main CPU program uses beside the
                stream (palettes, the SR window picture, the credits table,
                the RS end screen); offsets in the header
  then one 75-sector packet per STM packet, same order and pacing as the STM:
    sectors 0-15   PCM chunk p: stream samples [32768p, 32768p + 32768) of the
                   whole movie's PCM, as signed 8-bit (the SCSP format). The STM
                   packet carries 32760 samples (8 x $FFF, FMV/Sub .StreamPCM);
                   the samples are re-chunked so every chunk fills a 32 KB half
                   of the SCSP ring and each packet's CD sectors land in one
                   half without splitting.
    sectors 16-74  the STM packet's graphics sectors, byte for byte.

PTEST.FMV (kind 2, the mute format of SP.asm ReadMuteFMVSectors) has no PCM:
  sector 0      the same header; byte 16 holds 0 (no PCM), bytes 20-23 the
                pictures retail shows (ptest_shown), every table byte is
                FMV_PACKET_MUTE << 4 | 1
  sectors 1..   PTEST.MMD data: the plane B border tiles (VRAM $7D00, tile
                $3E8), its 40 x 28 map (VRAM $A000) and the 8-step fade table
                of palette line 1
  then one 5-sector bank per picture shown, byte for byte from PTEST.STM.
"""
import hashlib
import json
import re
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import fmv_extract  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / 'build/fmv'
OUT = ROOT / 'cd'
SECTOR, CYCLE_SECTORS, PCM_SECTORS = 2048, 75, 16
CYCLE = SECTOR * CYCLE_SECTORS
PCM_PER_PACKET = 8 * 0xFFF
CHUNK = PCM_SECTORS * SECTOR
MAGIC, VERSION = b'SFMV', 1
STREAMS = [('OPN.STM', 'OPN.FMV', 0, 0), ('GOODEND.STM', 'GOODEND.FMV', 1, 0x7F),
           ('BADEND.STM', 'BADEND.FMV', 1, 0), ('PTEST.STM', 'PTEST.FMV', 2, 0)]
MUTE_BANK = 5 * SECTOR

# ENDING.MMD data the player needs, found through the instruction that reads it.
# Builds differ (the Japanese program sits $36 bytes later than the U.S. one, its data
# up to -$266), so each reference is the code just before it plus the instruction with
# its displacement or immediate left open; it must match exactly once.
#   name: (code before, instruction, data size; None = the credits table's own length)
ENDING_REFS = {
    'cram': ('c000000000c00004', 'lea', 128),       # init: 64 CRAM words
    'sr_palette': ('c000', 'lea45', 32),           # SR: palette line 0
    'sr_window': ('9409', 'dma', 4800),            # job 10: DMA source registers $95-$97
    'fade': ('d040', 'movem', 40),                 # RS: line 2 colors 11/15
    'credits': ('c08e', 'lea45', None),            # NO: staff roll rows
    'bad_rows': ('750a000200c00004', 'lea43', 300),   # RS, endingID 0: 5 x 30
    'bad_tiles': ('6708', 'lea43', 864),              # 27 tiles to VRAM $76C0
    'good_rows': ('7518000200c00004', 'lea43', 64),   # RS, endingID $7F: 2 x 16
    'good_tiles': ('000100c00004', 'lea43', 608),     # 19 tiles to VRAM $76C0
}
INSTRUCTIONS = {'lea': rb'\x41\xfa..', 'lea43': rb'\x43\xfa..', 'lea45': rb'\x45\xfa..',
                'movem': rb'\x4c\xbb\x00\x03\x00.', 'dma': rb'\x38\xbc\x95.\x38\xbc\x96.\x38\xbc\x97.'}
ORIGIN = 0xFF1F00   # file offset = Main CPU address - $FF1F00


def ending_ref(mmd, name):
    """File offset and size of one ENDING.MMD data item."""
    before, kind, size = ENDING_REFS[name]
    pattern = re.escape(bytes.fromhex(before)) + INSTRUCTIONS[kind]
    hits = [m.start() + len(before) // 2 for m in re.finditer(pattern, mmd, re.S)]
    assert len(hits) == 1, f'ENDING.MMD {name}: {len(hits)} matches for its reference'
    at = hits[0]
    if kind.startswith('lea'):
        data = at + 2 + struct.unpack_from('>h', mmd, at + 2)[0]
    elif kind == 'movem':
        data = at + 4 + mmd[at + 5]                 # (d8,pc,d0.w): pc = extension word
    else:
        word = mmd[at + 11] << 16 | mmd[at + 7] << 8 | mmd[at + 3]
        data = ((word << 1) & 0xFFFFFF) - ORIGIN
    return data, credits_len(mmd, data) if size is None else size


def roll_speed(mmd):
    """The staff roll's step, 16.16 lines per V-blank: move.l ($C08A).w,d0;
    addi.l #step,d0; move.l d0,($C08A).w (US $9100, Japanese $A000)."""
    hits = re.findall(rb'\x20\x38\xc0\x8a\x06\x80(....)\x21\xc0\xc0\x8a', mmd, re.S)
    assert len(hits) == 1, f'ENDING.MMD roll step: {len(hits)} matches'
    return struct.unpack('>I', hits[0])[0]


def still_tiles(mmd):
    """Tiles the SR packet loads: ENDING.MMD queues DMA jobs (lea $FFFF8000,a2;
    move.w #1,(a2)+; move.l #VDP command,d0; ...; move.w #words,(a2)+) that copy it
    to VRAM from $14C0 on, 180 tiles a frame (US 4 jobs, 720 tiles; Japanese 5.5,
    990). Counted over the jobs whose destinations continue from $14C0."""
    jobs = {}
    for m in re.finditer(rb'\x45\xf8\x80\x00\x34\xfc\x00\x01\x20\x3c(....)\x24\xc0\x24\xc8\x34\xfc(..)', mmd, re.S):
        command, words = struct.unpack('>I', m.group(1))[0], struct.unpack('>H', m.group(2))[0]
        jobs[(command >> 16 & 0x3FFF) | (command & 3) << 14] = words * 2
    at = 0x14C0
    assert at in jobs, 'ENDING.MMD: no SR job to VRAM $14C0'
    while at in jobs:
        at += jobs[at]
    assert (at - 0x14C0) % 32 == 0
    return (at - 0x14C0) // 32


def anim_map_at(mmd):
    """The "15" window map ENDING.MMD draws: 32 x 14 words, 15 x 10 tiles from $10."""
    want = struct.pack('>448H', *[0x10 + r * 15 + c if r < 10 and c < 15 else 0
                                  for r in range(14) for c in range(32)])
    assert mmd.count(want) == 1, 'ENDING.MMD "15" map not found once'
    return mmd.index(want)


def sm_to_signed(b):
    """RF5C164 sign-magnitude (bit 7 set = positive) to two's complement."""
    return (b & 0x7F) if b & 0x80 else (-(b & 0x7F)) & 0xFF


SM_TABLE = bytes(sm_to_signed(b) for b in range(256))


def credits_len(mmd, at):
    start = at
    while True:
        fill = struct.unpack_from('>H', mmd, at)[0]
        at += 2
        if fill == 0xFFFF:
            return at - start
        at += 2
        while struct.unpack_from('>H', mmd, at)[0] != 0xFFFF:
            at += 2
        at += 2


def pc_target(mmd, signature, group=1):
    """Target of the one PC-relative lea in a signature (its displacement is group 1)."""
    hits = list(re.finditer(signature, mmd, re.S))
    assert len(hits) == 1, f'ENDING.MMD card: {len(hits)} matches for {signature!r}'
    m = hits[0]
    return m.start(group) + struct.unpack('>h', m.group(group))[0], m


def card(mmd):
    """The "PRESENTED BY SEGA" card ENDING.MMD shows after the stream ($FFC100): Nemesis
    art to VRAM 0, a map of raw plane A words, 64 colours; then a fade in, a hold
    (US: 600 V-blanks or Start held; Japanese: until Start is held) and a fade out."""
    from convert_assets import nemesis
    art_at, _ = pc_target(mmd, rb'\x23\xfc\x40\x00\x00\x00\x00\xc0\x00\x04\x41\xfa(..)\x61\x00')
    map_at, m = pc_target(mmd, rb'\x43\xfa(..)\x20\x3c(....)\x72(.)\x74(.)')
    command = struct.unpack('>I', m.group(2))[0]
    address = (command >> 16 & 0x3FFF) | (command & 3) << 14
    width, height = m.group(3)[0] + 1, m.group(4)[0] + 1
    assert address >= 0xC000, 'card map outside plane A'
    row, col = (address - 0xC000) // 128, (address - 0xC000) % 128 // 2
    palette_at, _ = pc_target(mmd, rb'\x41\xfa(..)\x43\xf8\xb2\x00\x7e\x1f')
    # US: move.w #600,timer; bsr VSync; tst.w timer (the V-int counts it down).
    hold = re.findall(rb'\x33\xfc(..)\x00\xff..\x61\x00..\x4a\x79\x00\xff', mmd, re.S)
    assert len(hold) <= 1
    # Once the Sub CPU reports the end ($A1200F bit 1): clear CRAM line 0, then
    # clr.w $FA40; move.w #n,d1; bsr VSync; dbf d1: n + 1 V-blanks before the card.
    wait = re.findall(rb'\x42\x78\xfa\x40\x32\x3c(..)\x61\x00', mmd, re.S)
    assert len(wait) == 1, f'ENDING.MMD end wait: {len(wait)} matches'
    tiles = nemesis(mmd[art_at:])
    return {'wait': struct.unpack('>H', wait[0])[0] + 1, 'tiles': tiles, 'map': mmd[map_at:map_at + width * height * 2], 'palette': mmd[palette_at:palette_at + 128],
            'row': row, 'col': col, 'width': width, 'height': height,
            'hold': struct.unpack('>H', hold[0])[0] if hold else 0}


def ending_blob(mmd, ending_id):
    parts = {}
    for name in ENDING_REFS:
        data_at, size = ending_ref(mmd, name)
        parts[name] = mmd[data_at:data_at + size]
    anim_map_at(mmd)   # the window layout the player assumes (fmv_extract.py checks it too)
    c = card(mmd)
    parts.update(card_tiles=c['tiles'], card_map=c['map'], card_palette=c['palette'])
    end = 'good' if ending_id == 0x7F else 'bad'
    order = ['cram', 'sr_palette', 'sr_window', 'fade', 'credits', end + '_rows', end + '_tiles',
             'card_tiles', 'card_map', 'card_palette']
    blob, table = b'', []
    for name in order:
        table.append((len(blob), len(parts[name])))
        blob += parts[name]
        blob += b'\0' * (-len(blob) % 4)
    return blob, table


TYPES = ['video', 'still', 'anim', 'hold', 'resume', 'empty', 'unknown', 'mute']

# PTEST.MMD (Main CPU, origin $FF2000 at file offset $100): code whose behavior the
# Saturn player copies; each must occur exactly once (the palette code twice).
PTEST_CODE = {
    # $FF24D4 VDP registers: H40, plane A $C000, plane B $A000, backdrop line 1
    # color 0 ($87 $10), 128 x 32 planes, H-scroll table $E400.
    'vdp_regs': '800481348230830084058570860087108a008b008c818d398f029003',
    # $FF23C0 plane A maps: 21 x 14 names from tile $10 at $C712 (column 9, row 7)
    # and from tile $136 at $C792 (column 73: the second buffer, H-scroll $200).
    'map_buf1': '7810203c47120003323c0014343c000d',
    'map_buf2': '383c0136203c47920003323c0014343c000d',
    # States 4/6 and 10/12: palette (to $C000; the previous one to $C020, which the
    # V-int copies to line 0), then 2400 + 2304 words to VRAM $0200/$14C0 or $26C0/$3980.
    'dma_buf1a': '203c4200000024c024c834fc0960', 'dma_buf1b': '203c54c0000024c024c834fc0900',
    'dma_buf2a': '203c66c0000024c024c834fc0960', 'dma_buf2b': '203c7980000024c024c834fc0900',
    'palette': '43f8c000264945e900207e0724d951cffffc224b7e0722d851cffffc',
    # V-int: plane A H-scroll $200 when state 6 starts (buffer 2 shown), 0 when
    # state 12 starts (buffer 1), and then line 1 color 5 = $0644.
    'vint_buf2': '0c780006c086661223fc6400000300c000042abc02000000',
    'vint_buf1': '0c78000cc086661e23fc6400000300c000042abc0000000023fcc02a000000c000043abc0644',
    # $FF2100: after the sub's end flag, 61 V-blanks, then $FF2282: fade lines 0 and 1
    # from step 7 to 0, 8 V-blanks a step. $FF2244: fade line 1 in, steps 0-7.
    'end_wait': '4278fa40323c003c6100ffe851c9fffa',
    'fade_out': '31fc0007c08a31fc0008c08c3038c08aeb4843fb002a45f8c04047f8c0207e0f34d136d9',
    'fade_in': '31fc0000c08a31fc0008c08c3038c08aeb4845f8c0407e0f43fb0062',
}


def ptest_program(mmd):
    """The data PTEST.MMD's Main CPU program shows beside the stream."""
    code = mmd.hex()
    for name, pattern in PTEST_CODE.items():
        hits = [m.start() for m in re.finditer(pattern, code) if m.start() % 2 == 0]
        want = 2 if name == 'palette' else 1   # states 4 and 10
        assert len(hits) == want, f'PTEST.MMD {name}: {len(hits)} matches'
    origin = struct.unpack_from('>I', mmd, 2)[0] - 0x100
    # $FF25AE: DMA of the border tiles (length $93/$94, source $95-$97, VRAM $7D00).
    m = list(re.finditer(rb'\x2c\xbc\x93(.)\x94(.)\x2c\xbc\x95(.)\x96(.)\x3c\xbc\x97(.)\x3c\xbc\x7d\x00', mmd, re.S))
    assert len(m) == 1, 'PTEST.MMD border DMA not found once'
    words = m[0].group(2)[0] << 8 | m[0].group(1)[0]
    source = ((m[0].group(5)[0] << 16 | m[0].group(4)[0] << 8 | m[0].group(3)[0]) << 1) & 0xFFFFFF
    art = source - origin
    # $FF25DE: 40 x 28 names to VRAM $A000 from lea (pc).
    m = list(re.finditer(rb'\x20\x3c\x60\x00\x00\x02\x32\x3c\x00\x27\x34\x3c\x00\x1b\x43\xfa(..)', mmd, re.S))
    assert len(m) == 1, 'PTEST.MMD plane B map not found once'
    at = m[0].start() + 14
    plane_b = at + 2 + struct.unpack_from('>h', mmd, at + 2)[0]
    # $FF2256: fade step d0 << 5 into $C040 from lea (d8,pc,d0.w).
    m = list(re.finditer(rb'\x45\xf8\xc0\x40\x7e\x0f\x43\xfb\x00(.)', mmd, re.S))
    assert len(m) == 1, 'PTEST.MMD fade table not found once'
    fade = m[0].start() + 8 + mmd[m[0].start() + 9]
    out = {'border_tiles': mmd[art:art + words * 2], 'border_map': mmd[plane_b:plane_b + 40 * 28 * 2],
           'fade': mmd[fade:fade + 8 * 32]}
    assert len(out['border_tiles']) == 6400 and len(out['border_map']) == 2240 and len(out['fade']) == 256
    names = struct.unpack('>1120H', out['border_map'])
    assert all(0x3E8 <= w & 0x7FF < 0x3E8 + 200 and w & 0x6000 == 0x2000 for w in names), 'border map'
    return out


def ptest_shown(sectors):
    """Banks retail shows. SP.asm FileEngine_LoadMuteFMV .GetSectors counts size / $800 - 1
    sectors, so ReadMuteFMVSectors hands over (sectors - 1) // 5 whole banks; PTEST.MMD shows
    bank n when bank n + 1 starts loading and leaves its loop at the sub's end flag while it
    waits for the next bank, so the last bank handed over is never shown."""
    return (sectors - 1) // 5 - 1


def convert_mute(stm, mmd):
    data = ptest_program(mmd)
    shown = ptest_shown(len(stm) // SECTOR)
    blob, table = b'', []
    for name in ['border_tiles', 'border_map', 'fade']:
        table.append((len(blob), len(data[name])))
        blob += data[name] + b'\0' * (-len(data[name]) % 4)
    header_sectors = 1 + (len(blob) + SECTOR - 1) // SECTOR
    head = bytearray(SECTOR)
    assert shown <= SECTOR - 128
    struct.pack_into('>4sHHIIIIHH', head, 0, MAGIC, VERSION, 2, shown, header_sectors, 0, shown, 0, len(table))
    for i, (off, size) in enumerate(table):
        struct.pack_into('>II', head, 32 + i * 8, SECTOR + off, size)
    for p in range(shown):
        head[128 + p] = TYPES.index('mute') << 4 | 1
    out = bytearray(head) + blob + b'\0' * (header_sectors * SECTOR - SECTOR - len(blob))
    out += stm[:shown * MUTE_BANK]
    return bytes(out), {'packets': shown, 'pictures': shown, 'header_sectors': header_sectors,
                        'resources': len(table)}


def convert(stm, kind, ending_id, mmd):
    packets = (len(stm) + CYCLE - 1) // CYCLE
    model = fmv_extract.packets(stm, 'ending' if kind else 'opening')
    assert len(model) == packets and packets <= SECTOR - 128
    pcm = bytearray()
    for p in range(packets):
        at = p * CYCLE
        if at + CHUNK > len(stm):
            break
        pcm += stm[at:at + PCM_PER_PACKET].translate(SM_TABLE)
    samples = len(pcm)
    pcm += b'\0' * (packets * CHUNK - len(pcm))
    blob, table = (ending_blob(mmd, ending_id) if kind == 1 else (b'', []))
    header_sectors = 1 + (len(blob) + SECTOR - 1) // SECTOR
    head = bytearray(SECTOR)
    struct.pack_into('>4sHHIIIIHH', head, 0, MAGIC, VERSION, kind, packets, header_sectors,
                     PCM_PER_PACKET, samples, ending_id, len(table))
    for i, (off, size) in enumerate(table):
        struct.pack_into('>II', head, 32 + i * 8, SECTOR + off, size)
    if kind == 1:   # FMV_SAT_END_WAIT, FMV_SAT_CARD .. FMV_SAT_CARD_HOLD (src/fmv_saturn.h)
        c = card(mmd)
        struct.pack_into('>H', head, 112, c['wait'])
        struct.pack_into('>BBBBIHH', head, 116, c['row'], c['col'], c['width'], c['height'],
                         roll_speed(mmd), still_tiles(mmd), c['hold'])
    for p, (name, _, frames) in enumerate(model):
        assert name != 'unknown' and frames < 16
        head[128 + p] = TYPES.index(name) << 4 | frames
    out = bytearray(head) + blob + b'\0' * (header_sectors * SECTOR - SECTOR - len(blob))
    for p in range(packets):
        out += pcm[p * CHUNK:(p + 1) * CHUNK]
        gfx = stm[p * CYCLE + CHUNK:(p + 1) * CYCLE]
        out += gfx + b'\0' * (CYCLE - CHUNK - len(gfx))
    info = {'packets': packets, 'pcm_samples': samples, 'header_sectors': header_sectors, 'resources': len(table)}
    if kind == 1:
        c = card(mmd)
        info.update(roll_speed=f'${roll_speed(mmd):X}', still_tiles=still_tiles(mmd),
                    card={k: c[k] for k in ('row', 'col', 'width', 'height', 'hold', 'wait')}, card_tiles=len(c['tiles']) // 32)
    return bytes(out), info


def main():
    manifest = SRC / 'manifest.json'
    if not manifest.exists():
        sys.exit('build/fmv/manifest.json missing: run tools/fmv_extract.py first')
    info = json.loads(manifest.read_text())
    mmd = (SRC / 'ENDING.MMD').read_bytes()
    assert hashlib.sha256(mmd).hexdigest() == info['ending_mmd_sha256']
    if not (SRC / 'PTEST.MMD').exists() or 'ptest_mmd_sha256' not in info:
        sys.exit('build/fmv/PTEST.MMD missing: run tools/fmv_extract.py again')
    ptest_mmd = (SRC / 'PTEST.MMD').read_bytes()
    assert hashlib.sha256(ptest_mmd).hexdigest() == info['ptest_mmd_sha256']
    OUT.mkdir(exist_ok=True)
    report = {'tool_sha256': hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(), 'files': {}}
    for src, dst, kind, ending_id in STREAMS:
        stm = (SRC / src).read_bytes()
        assert hashlib.sha256(stm).hexdigest() == info['streams'][src]['sha256'], src
        if kind == 2:
            data, meta = convert_mute(stm, ptest_mmd)
        else:
            data, meta = convert(stm, kind, ending_id, mmd)
        path = OUT / dst
        if not path.exists() or path.read_bytes() != data:
            path.write_bytes(data)
        meta['sha256'] = hashlib.sha256(data).hexdigest()
        meta['bytes'] = len(data)
        report['files'][dst] = meta
        if kind == 2:
            print(f"{dst}: {meta['pictures']} pictures, no PCM, {len(data)} bytes")
        else:
            print(f"{dst}: {meta['packets']} packets, {meta['pcm_samples']} PCM samples, {len(data)} bytes")
    (SRC / 'convert.json').write_text(json.dumps(report, indent=1) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
