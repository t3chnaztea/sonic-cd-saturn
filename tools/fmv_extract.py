#!/usr/bin/env python3
"""Extract the Sonic CD STM movie streams and check the host STM decoder.

Input is the user's private disc image, read the same way extract_mmd.py reads
it: build/retail/sonic.iso, the Mode 1 data track that prepare_audio.py
extracts from assets/private/sonic-cd.chd. Output goes to build/fmv/ only:
the STM files byte for byte, ENDING.MMD (the ending's Main CPU program, used
for its packet dispatch and plane map), PTEST.MMD (the pencil test's Main CPU
program: border, fade and maps; tools/fmv_convert.py ptest_program), a manifest
with hashes and rates, and parity results. Nothing here is committed or copied
to cd/.

--verify builds src/fmv_stm.c as a host program (tools/fmv_stm_host.c) and
compares it with:
  1. a Python model of the Main CPU path. Opening: FMV/Main (Opening).asm,
     frame sections DMA'd to the two VRAM buffers, the DrawFMVTilemaps plane
     map, the H-scroll buffer switch, and the backdrop through the blank border
     tile. Ending: the same, plus ENDING.MMD's packet tags (checked in its
     code) and its 15 x 10 plane A map for "15" packets. Pencil test
     (PTEST.STM, SP.asm ReadMuteFMVSectors: 5-sector banks, no PCM): PTEST.MMD's
     two tile DMAs and its 21 x 14 plane A map, every bank;
  2. the RF5C164 copy loop of FMV/Sub (Opening).asm (8 banks x $FFF bytes);
  3. the disassembly's MakeSTM inputs for OPN.STM: FMV/Data/Opening.gif
     (every frame, exact RGB) and the region WAV (every PCM byte).
"""
import argparse
import hashlib
import json
import pathlib
import struct
import subprocess
import sys
import wave

from extract_mmd import disc_files

ROOT = pathlib.Path(__file__).resolve().parents[1]
ISO = ROOT / 'build/retail/sonic.iso'
# The project plays the Japanese soundtrack (JAPANESE-MUSIC.md): the movies' PCM comes
# from the Japanese disc by default. --iso picks another 2048-byte data track image.
JAPAN_CUE = ROOT / 'assets/private/sonic-cd-japan.cue'
OUT = ROOT / 'build/fmv'
from scd_source import SRC as SCD_SRC
FMV_SRC = SCD_SRC / 'FMV'
STREAMS = {'OPN.STM': 'opening', 'GOODEND.STM': 'ending', 'BADEND.STM': 'ending',
           'PTEST.STM': 'mute'}
MUTE_BANK, MUTE_FRAME = 5 * 2048, 32 + 294 * 32     # SP.asm ReadMuteFMVSectors; PTEST.MMD

SECTOR = 2048
CYCLE_SECTORS, PCM_SECTORS = 75, 16
CYCLE = CYCLE_SECTORS * SECTOR
GFX_BYTES = (CYCLE_SECTORS - PCM_SECTORS) * SECTOR
HEADER = 16
FRAMES_PER_CYCLE = 8
SECTIONS = [0x12C0, 0x12C0, 0x1280]            # LoadFrameSect / LoadFrameSect3
FRAME = 32 + sum(SECTIONS)
ANIM_FRAME, ANIM_FRAMES = 32 + 4800, 15
BUFFER_VRAM = {1: [0x0200, 0x14C0, 0x2780], 2: [0x3A00, 0x4CC0, 0x5F80]}
PLANE_A = 0xC000
MAP_ORIGIN = {1: (0xC608, 0x10), 2: (0xC688, 0x1D0)}   # DrawFMVTilemaps
HSCROLL = {1: 0, 2: 0x200}                                # VInt_DisplayBuf1/2
TAGS = {b'08': 'video', b'SR': 'still', b'15': 'anim', b'NO': 'hold', b'RS': 'resume',
        b'\0\0': 'empty'}
MD_LEVELS = [0, 52, 87, 116, 144, 172, 206, 255]
CD_1X = 75 * SECTOR                                       # bytes per second
SATURN_2X = 2 * CD_1X


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def fnv(data, h=2166136261):
    for b in data:
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return h


def packets(stm, kind):
    """(type, gfx offset, frame count) per packet, as the Main CPU sees it."""
    out = []
    for c in range((len(stm) + CYCLE - 1) // CYCLE):
        at = c * CYCLE + PCM_SECTORS * SECTOR
        avail = max(0, min(GFX_BYTES, len(stm) - at))
        if kind == 'mute':
            break
        if kind == 'opening':
            kind_c, gfx = 'video', at
        elif avail < HEADER:
            out.append(('empty', len(stm), 0))
            continue
        else:
            kind_c, gfx = TAGS.get(stm[at:at + 2], 'unknown'), at + HEADER
            avail -= HEADER
        frames = {'video': min(FRAMES_PER_CYCLE, avail // FRAME),
                  'anim': min(ANIM_FRAMES, avail // ANIM_FRAME)}.get(kind_c, 0)
        out.append((kind_c, gfx, frames))
    if kind == 'mute':
        for c in range((len(stm) + MUTE_BANK - 1) // MUTE_BANK):
            avail = max(0, min(MUTE_BANK, len(stm) - c * MUTE_BANK) - HEADER)
            out.append(('mute', c * MUTE_BANK + HEADER, int(avail >= MUTE_FRAME)))
    return out


def model_video(stm, gfx, slot):
    """One "08" frame as FMV/Main (Opening).asm puts it on screen."""
    at = gfx + slot * FRAME
    palette = struct.unpack('>16H', stm[at:at + 32])
    vram = bytearray(0x10000)
    # frameCount restarts at 0 for every Word RAM bank; even counts load
    # buffer 2 (FrameRead_Sect1: btst #0,frameCount+1 / beq).
    buf = 2 if slot % 2 == 0 else 1
    src = at + 32
    for dest, length in zip(BUFFER_VRAM[buf], SECTIONS):
        vram[dest:dest + length] = stm[src:src + length]
        src += length
    for b in (1, 2):
        addr, tile = MAP_ORIGIN[b]
        for row in range(14):
            for col in range(32):
                struct.pack_into('>H', vram, addr + row * 0x100 + col * 2, tile)
                tile += 1
    words = bytearray()
    for y in range(48, 160):                      # picture rows 6-19
        for x in range(32, 288):                  # picture columns 4-35
            px = (x - HSCROLL[buf]) % 1024
            entry = struct.unpack_from('>H', vram, PLANE_A + (y >> 3) * 0x100 + (px >> 3) * 2)[0]
            byte = vram[(entry & 0x7FF) * 32 + (y & 7) * 4 + ((px & 7) >> 1)]
            index = byte & 15 if px & 1 else byte >> 4
            # Index 0 is transparent; plane B holds blank border tile $3E8
            # there, so the backdrop (register 7 = line 0 color 0) shows.
            words += struct.pack('>H', palette[index])
    return bytes(words)


def model_anim(stm, gfx, slot, anim_map):
    """One "15" frame: palette + 150 tiles at VRAM $0200 through ENDING.MMD's map."""
    at = gfx + slot * ANIM_FRAME
    palette = struct.unpack('>16H', stm[at:at + 32])
    vram = bytearray(0x10000)
    vram[0x200:0x200 + 4800] = stm[at + 32:at + ANIM_FRAME]
    words = bytearray()
    for y in range(80):
        for x in range(120):
            tile = anim_map[(y >> 3) * 32 + (x >> 3)] & 0x7FF
            byte = vram[tile * 32 + (y & 7) * 4 + ((x & 7) >> 1)]
            words += struct.pack('>H', palette[byte & 15 if x & 1 else byte >> 4])
    return bytes(words)


def model_mute(stm, gfx, slot=0):
    """One PTEST.STM bank as PTEST.MMD puts it in plane A: palette, then DMAs of
    2400 and 2304 words to VRAM $0200/$14C0 and 21 x 14 names from tile $10 at
    $C712. Index 0 renders as palette[0] here, as fmv_frame_render_md does; on
    screen plane B shows through it (tools/fmv_retail.py ptest checks that)."""
    palette = struct.unpack('>16H', stm[gfx:gfx + 32])
    vram = bytearray(0x10000)
    vram[0x0200:0x0200 + 4800] = stm[gfx + 32:gfx + 32 + 4800]
    vram[0x14C0:0x14C0 + 4608] = stm[gfx + 32 + 4800:gfx + 32 + 9408]
    for row in range(14):
        for col in range(21):
            struct.pack_into('>H', vram, 0xC712 + row * 0x100 + col * 2, 0x10 + row * 21 + col)
    words = bytearray()
    for y in range(56, 168):
        for x in range(72, 240):
            entry = struct.unpack_from('>H', vram, PLANE_A + (y >> 3) * 0x100 + (x >> 3) * 2)[0]
            byte = vram[(entry & 0x7FF) * 32 + (y & 7) * 4 + ((x & 7) >> 1)]
            words += struct.pack('>H', palette[byte & 15 if x & 1 else byte >> 4])
    return bytes(words)


def build_host():
    exe = OUT / 'fmv_stm_host'
    subprocess.run(['cc', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror', '-o', str(exe),
                    str(ROOT / 'tools/fmv_stm_host.c'), str(ROOT / 'src/fmv_stm.c')], check=True)
    return exe


def host_digest(exe, path, kind):
    types, frames, pcm = {}, {}, {}
    for line in subprocess.run([str(exe), 'digest', str(path), kind], check=True,
                               capture_output=True, text=True).stdout.splitlines():
        f = line.split()
        if f[0] == 'packet':
            types[int(f[1])] = (f[2], int(f[3]))
        elif f[0] == 'frame':
            frames[(int(f[1]), int(f[2]))] = f[3]
        elif f[0] == 'pcm':
            pcm[int(f[1])] = f[2]
    return types, frames, pcm


def pcm_hw(b):
    """RF5C164 sign-magnitude: bit 7 set = positive."""
    return (b & 127) if b & 128 else -(b & 127)


def ending_program(files):
    """ENDING.MMD: check its tag dispatch and return the "15" plane map."""
    mmd = files['ENDING.MMD']
    for tag in TAGS:
        if tag != b'\0\0':
            assert b'\x0c\x50' + tag in mmd, f'cmpi.w #{tag!r},(a0) not in ENDING.MMD'
    # The map is drawn 32 x 14 at plane A $C608 (VDP command $46080003).
    assert mmd.count(bytes.fromhex('203c46080003')) == 2
    # Found by content: the U.S. program has it at $C06, the Japanese one at $C3C.
    expect = [0x10 + r * 15 + c if r < 10 and c < 15 else 0 for r in range(14) for c in range(32)]
    want = struct.pack('>448H', *expect)
    assert mmd.count(want) == 1, 'ENDING.MMD "15" map (15 x 10 row-major) not found once'
    anim_map = struct.unpack_from('>448H', mmd, mmd.index(want))
    return anim_map, sha256(mmd)


def verify(name, stm, kind, exe, region, samples, anim_map):
    report = {}
    types, frames, pcm = host_digest(exe, OUT / name, kind)
    model = packets(stm, kind)
    report['packet_types'] = {}
    for kind_c, _, n in model:
        report['packet_types'][kind_c] = report['packet_types'].get(kind_c, 0) + 1
    report['packet_type_mismatches'] = [c for c, (k, _, n) in enumerate(model) if types.get(c) != (k, n)]
    all_frames = [(c, i) for c, (k, _, n) in enumerate(model) for i in range(n)]
    report['frames'] = len(all_frames)
    report['host_frames'] = len(frames)
    if samples == 0:
        picks = all_frames
    else:
        step = max(1, len(all_frames) // samples)
        picks = all_frames[::step] + [all_frames[-1]]
        # Always include the first frame after every packet type change.
        prev = None
        for c, (k, _, n) in enumerate(model):
            if k != prev and n:
                picks.append((c, 0))
            prev = k
        picks = sorted(set(picks))
    bad = []
    for c, i in picks:
        k, gfx, _ = model[c]
        if k == 'mute':
            words = model_mute(stm, gfx)
        else:
            words = model_video(stm, gfx, i) if k == 'video' else model_anim(stm, gfx, i, anim_map)
        if '%08x' % fnv(words) != frames.get((c, i)):
            bad.append([c, i])
    report['model_frames_checked'] = len(picks)
    report['model_frame_mismatches'] = bad
    pbad = []
    for c, value in pcm.items():
        raw = stm[c * CYCLE:c * CYCLE + 8 * 0xFFF]
        if '%08x' % fnv(bytes(pcm_hw(b) & 0xFF for b in raw)) != value:
            pbad.append(c)
    report['pcm_packets_checked'] = len(pcm)
    report['pcm_packet_mismatches'] = pbad
    report['pcm_ff_bytes'] = sum(stm[c * CYCLE:c * CYCLE + PCM_SECTORS * SECTOR].count(0xFF)
                                 for c in range(len(pcm)))
    if kind == 'mute':
        report['pcm_expected'] = 0      # no PCM part: the host reports none
        ok_pcm = not pcm
    else:
        ok_pcm = True
    ok = (not bad and not pbad and not report['packet_type_mismatches'] and
          report['pcm_ff_bytes'] == 0 and len(frames) == len(all_frames) and
          'unknown' not in report['packet_types'] and ok_pcm)
    if name == 'OPN.STM':
        report['makestm'] = makestm_parity(stm, exe, region, all_frames)
        ok = ok and report['makestm']['ok']
    report['ok'] = ok
    return report


def makestm_parity(stm, exe, region, all_frames):
    from PIL import Image
    out = {}
    gif = FMV_SRC / 'Data/Opening.gif'
    im = Image.open(gif)
    out['gif_sha256'] = sha256(gif.read_bytes())
    out['gif_frames'] = getattr(im, 'n_frames', 1)
    bad = []
    ppm = OUT / 'parity.ppm'
    for n, (c, i) in enumerate(all_frames[:out['gif_frames']]):
        im.seek(n)
        subprocess.run([str(exe), 'ppm', str(OUT / 'OPN.STM'), 'opening', str(c), str(i), str(ppm)], check=True)
        if ppm.read_bytes().split(b'\n', 3)[3] != im.convert('RGB').tobytes():
            bad.append(n)
    ppm.unlink(missing_ok=True)
    out['gif_frame_mismatches'] = bad
    wav_name = 'Opening (USA).wav' if region == 'U' else 'Opening (Japan, Europe).wav'
    path = FMV_SRC / 'Data' / wav_name
    with wave.open(str(path)) as w:
        assert (w.getnchannels(), w.getsampwidth()) == (1, 1)
        ref = w.readframes(w.getnframes())
        out['wav'] = {'file': wav_name, 'sha256': sha256(path.read_bytes()),
                      'rate': w.getframerate(), 'samples': len(ref)}
    # MakeSTM writes unsigned u >= 128 as $80|(u-128) and u < 128 as 127-u.
    mismatch = 0
    for c in range(len(ref) // 32768):
        raw = stm[c * CYCLE:c * CYCLE + 32768]
        for x, y in zip(raw, ref[c * 32768:(c + 1) * 32768]):
            if (128 + (x & 127) if x & 128 else 127 - x) != y:
                mismatch += 1
    out['wav']['packets'] = len(ref) // 32768
    out['wav']['byte_mismatches'] = mismatch
    out['ok'] = not bad and mismatch == 0 and out['gif_frames'] == len(all_frames)
    return out


def rates(stm, kind):
    size = len(stm)
    info = {'bytes': size, 'sectors': (size + SECTOR - 1) // SECTOR, 'seconds_at_1x': size / CD_1X,
            'stream_bytes_per_second': CD_1X, 'saturn_2x_bytes_per_second': SATURN_2X,
            'saturn_2x_headroom': 1 - CD_1X / SATURN_2X}
    if kind == 'mute':
        info['frames'] = sum(n for _, _, n in packets(stm, kind))
        info['mute_bank_bytes'] = MUTE_BANK
        info['mute_frame_bytes'] = MUTE_FRAME
        info['banks_per_second_at_1x'] = CD_1X / MUTE_BANK          # 15 fps
    elif kind:
        model = packets(stm, kind)
        info['frames'] = sum(n for _, _, n in model)
        info['video_frame_bytes'] = FRAME
        info['video_stream_bytes_per_frame'] = CD_1X / FRAMES_PER_CYCLE     # 8 fps
        info['anim_frame_bytes'] = ANIM_FRAME
        info['anim_stream_bytes_per_frame'] = CD_1X / ANIM_FRAMES          # 15 fps
        info['pcm_bytes_per_packet'] = PCM_SECTORS * SECTOR
        info['pcm_bytes_played_per_packet'] = 8 * 0xFFF
        info['gfx_bytes_per_packet'] = GFX_BYTES
        info['gfx_bytes_used_per_video_packet'] = FRAMES_PER_CYCLE * FRAME + (HEADER if kind == 'ending' else 0)
        info['gfx_bytes_used_per_anim_packet'] = ANIM_FRAMES * ANIM_FRAME + HEADER
    return info


def cue_data_track(cue):
    """Track 1 (MODE1/2352) of a CUE/BIN set as 2048-byte user data sectors."""
    cue = cue.resolve()
    lines = [l.strip() for l in cue.read_text().splitlines()]
    assert len(lines) >= 3 and lines[1].startswith('FILE "') and lines[2] == 'TRACK 01 MODE1/2352', \
        f'{cue}: track 1 is not MODE1/2352'
    raw = (cue.parent / lines[1].split('"')[1]).read_bytes()
    assert len(raw) % 2352 == 0, 'track 1 is not whole 2352-byte sectors'
    return b''.join(raw[i + 16:i + 16 + SECTOR] for i in range(0, len(raw), 2352))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--iso', type=pathlib.Path, help='2048-byte data track image (default: the Japanese disc)')
    ap.add_argument('--cue', type=pathlib.Path, default=JAPAN_CUE, help='CUE/BIN disc read when --iso is not given')
    ap.add_argument('--verify', action='store_true', help='run decoder parity checks')
    ap.add_argument('--samples', type=int, default=48,
                    help='model frames per stream to check (0 = every frame)')
    args = ap.parse_args()
    if args.iso:
        if not args.iso.exists():
            sys.exit(f'{args.iso} missing: run tools/prepare_audio.py with the private CHD first')
        iso, source = args.iso.read_bytes(), args.iso
    else:
        if not args.cue.exists():
            sys.exit(f'{args.cue} missing: link the Japanese disc (JAPANESE-MUSIC.md) or pass --iso')
        iso, source = cue_data_track(args.cue), args.cue.resolve()
    region = chr(iso[0x1F0])
    files = disc_files(iso)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'ENDING.MMD').write_bytes(files['ENDING.MMD'])
    (OUT / 'PTEST.MMD').write_bytes(files['PTEST.MMD'])
    anim_map, ending_sha = ending_program(files)
    manifest = {'iso': str(source), 'iso_sha256': sha256(iso), 'region': region,
                'ending_mmd_sha256': ending_sha,
                'ptest_mmd_sha256': sha256(files['PTEST.MMD']),
                'tool_sha256': sha256(pathlib.Path(__file__).read_bytes()),
                'decoder_sha256': sha256((ROOT / 'src/fmv_stm.c').read_bytes() +
                                         (ROOT / 'src/fmv_stm.h').read_bytes() +
                                         (ROOT / 'tools/fmv_stm_host.c').read_bytes()),
                'streams': {}}
    exe = build_host() if args.verify else None
    ok = True
    for name, kind in STREAMS.items():
        data = files[name]
        (OUT / name).write_bytes(data)
        entry = {'sha256': sha256(data), 'kind': kind, **rates(data, kind)}
        if exe and kind:
            entry['parity'] = verify(name, data, kind, exe, region, args.samples, anim_map)
            ok = ok and entry['parity']['ok']
        manifest['streams'][name] = entry
        line = f"{name}: {len(data)} bytes, {entry['seconds_at_1x']:.1f} s at 1x"
        if 'frames' in entry:
            line += f", {entry['frames']} frames"
        if 'parity' in entry:
            p = entry['parity']
            line += (f", packets {p['packet_types']}, model {p['model_frames_checked']} frames"
                     f" {len(p['model_frame_mismatches'])} bad, pcm {p['pcm_packets_checked']} packets"
                     f" {len(p['pcm_packet_mismatches'])} bad")
            if 'makestm' in p:
                m = p['makestm']
                line += (f", gif {m['gif_frames']} frames {len(m['gif_frame_mismatches'])} bad"
                         f", wav {m['wav']['samples']} bytes {m['wav']['byte_mismatches']} bad")
        print(line)
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n')
    print(f'{"PASS" if ok else "FAIL"}: fmv_extract region {region}, manifest build/fmv/manifest.json')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
