#!/usr/bin/env python3
"""Palmtree Panic (R1) art gate: original sprite pixels as Saturn draws them, per program.

Counterpart of tools/test_zone_art_emulator.py (tools/check_zone_object_target.py)
for the zone without a zone-art pack. Palmtree Panic objects draw from the
shared object atlas (VDP1 0x1AAC0, src/main.c object_sprite), so the chain is:

1. host: every object frame in assets/generated/object-art.bin equals the
   independent source compositor over the original mappings and art
   (tools/test_sprite_composition.py verify_assets);
2. Saturn: for each program R1<act><era>, level select boots it (emulator
   zones mode, no input). 160 frames into play the harness asks the emulator-
   only fixture (src/zone_object_view.inc request 0xa7) to draw each atlas
   frame alone at screen (160,112), with all four flips, through the gameplay
   object_sprite builder, and screenshots each picture. Every command's
   geometry must equal the source canvas placement, and every canvas pixel
   must equal the original composition: opaque pixels in the original colour
   (stage-palette lines from this program's stage file, or the live line-1
   CRAM after an Amy/boss palette epoch), transparent pixels the back screen;
3. the final VDP1 dump: the atlas equals object-art.bin with this program's
   stage palette in the stage-palette banks (tools/check_object_vram.py
   expected_arena; a bank-1 CLUT may hold the live line-1 palette).

The harness is tools/emulator_test.c (SCD_PPZ_OBJECT_ART). No gameplay RAM
writes. Not hardware acceptance.
"""
import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
from pathlib import Path

from convert_assets import ROOT, OUT
from check_object_vram import expected_arena
from sprite_composition import source_sprite

PROGRAMS = [f'R1{a}{e}' for a in (1, 2, 3) for e in ('CD' if a == 3 else 'ABCD')]
TOKENS = struct.pack('>16H', 0, *[0x8000 | n for n in range(1, 16)])


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stage_file(act, era):
    """assets/generated stage file of one PPZ program (tools/act_test.c naming)."""
    return f'ppz{era}.bin' if act == 0 else f'ppz1{act+1}{"ABCD"[era]}.bin'


def metadata():
    text = (OUT/'object-frames.inc').read_text()
    def array(name): return list(map(int, re.search(name+r'\[\]=\{([^}]+)', text)[1].split(',')))
    count = int(re.search(r'#define OBJECT_FRAME_COUNT (\d+)', text)[1])
    meta = {n: array('object_'+n) for n in ('raw_offsets', 'widths', 'heights', 'tops', 'canvases', 'y_shifts',
                                            'stage_palette', 'high_priority')}
    assert all(len(v) == count for v in meta.values()), 'object-frames.inc array lengths'
    return count, meta


def sources():
    """{atlas frame: composition record} from the converter's own draw calls."""
    from audit_sprite_composition import capture
    records, _, _, _ = capture()
    return {r['frame']: r for r in records if r['kind'] == 'object'}


def rgb(color):
    return bytes(((color & 31)*8, ((color >> 5) & 31)*8, ((color >> 10) & 31)*8))


def check(folder, act, era, count, meta, records):
    log = (folder/'results.log').read_text()
    assert re.search(rf'Zone art passed: zone=0 act={act} era={era} frames={count} captures={count*4} updates=\d+', log), \
        'no completed PPZ object art fixture'
    sprites = {int(c): list(map(int, w.split())) for c, w in re.findall(r'^Zone art sprite: (\d+) ([\d ]+)$', log, re.M)}
    assert set(sprites) == set(range(count*4)), 'missing rendered poses'
    sprite_cram = {int(c): [int(w, 16) for w in words.split()]
                   for c, words in re.findall(r'^Zone sprite cram: (\d+) ([0-9a-f ]+)$', log, re.M)}
    stage = (OUT/stage_file(act, era)).read_bytes()
    at, size = struct.unpack_from('>II', stage, 4+5*8)
    assert size == 128
    palette = struct.unpack_from('>64H', stage, at)
    captures = {}; pixels = 0; live_frames = set(); unsourced = []
    for f in range(count):
        w, h, top, off = meta['widths'][f], meta['heights'][f], meta['tops'][f], meta['raw_offsets'][f]
        canvas, shift = meta['canvases'][f], meta['y_shifts'][f]
        r = records.get(f)
        if r is None:
            unsourced.append(f)
        else:
            assert (r['width'], r['height'], r['y_shift']) == (w, canvas, shift), ('canvas', f)
            index = struct.unpack(f'>{w*canvas}H', source_sprite(r['mapping'], r['art'], TOKENS, w, shift, canvas))
            colour = struct.unpack(f'>{w*canvas}H', r['actual'])
        x0, y0 = 160 - w//2, 112 - 32 - shift
        for flags in range(4):
            case = f*4 + flags
            vtop = canvas - top - h if flags & 2 else top
            assert sprites[case] == [0, f, x0 & 0xffffffff, (y0+vtop) & 0xffffffff, flags, w << 16 | h, 0x1AAC0+off, 2], \
                ('command geometry', f, flags, sprites[case])
            path = folder/f'zone-art-{case:03d}.ppm'
            header, image = path.read_bytes().split(b'255\n', 1)
            assert header == b'P6\n330 224\n'
            captures[path.name] = hashlib.sha256(image).hexdigest()
            if r is None:
                continue
            if meta['high_priority'][f] or not meta['stage_palette'][f]:
                options = [None]  # fixed colours: the composition itself
            else:
                # The art tile's palette line (the object's base tile word, not the
                # mapping pieces): pixel index n reads that line's entry n.
                line = meta['stage_palette'][f]
                options = [palette[16*line:16*line+16]]
                if line == 1:
                    options.append(sprite_cram[case][16:32])
            background = None
            for corner in ((5, 0), (324, 0), (5, 223), (324, 223)):
                cx, cy = corner[0]-5, corner[1]
                if not (x0 <= cx < x0+w and y0 <= cy < y0+canvas):
                    background = image[(cy*330+corner[0])*3:(cy*330+corner[0])*3+3]
                    break
            failure = None
            for k, option in enumerate(options):
                checked = 0
                for cy in range(canvas):
                    sy = y0 + (canvas-1-cy if flags & 2 else cy)
                    if not 0 <= sy < 224: continue
                    for cx in range(w):
                        sx = x0 + (w-1-cx if flags & 1 else cx)
                        if not 0 <= sx < 320: continue
                        n = index[cy*w+cx] & 15
                        if n:
                            want = rgb(colour[cy*w+cx] if option is None else option[n])
                        elif background is None:
                            continue
                        else:
                            want = background
                        at = (sy*330+sx+5)*3
                        if image[at:at+3] != want:
                            failure = ('pixel', f, flags, cx, cy, image[at:at+3].hex(), want.hex(), 'live' if k else 'stage')
                            break
                        checked += 1
                    else:
                        continue
                    break
                else:
                    pixels += checked
                    if k: live_frames.add(f)
                    failure = None
                    break
            assert failure is None, failure
    # The atlas as uploaded (final VDP1 dump).
    expected, layout = expected_arena(stage_file(act, era))
    cram = sprite_cram[count*4-1]
    live, _ = expected_arena(palette=cram)
    vdp1 = (folder/'zone-art-vdp1.bin').read_bytes()
    assert len(vdp1) == 0x80000
    arena = vdp1[0x1AAC0:0x1AAC0+len(expected)]
    clut_frames = {}
    for f, (off, w, h, bank) in enumerate(layout):
        if bank == 1:
            clut_frames.setdefault(off+w*h//2, f)
    live_cluts = set()
    if arena != expected:
        for i in (i for i, (a, b) in enumerate(zip(arena, expected)) if a != b):
            base = next((c for c in clut_frames if c <= i < c+32), None)
            assert base is not None and arena[base:base+32] == live[base:base+32], \
                ('VDP1 object readback', hex(0x1AAC0+i), arena[i], expected[i])
            live_cluts.add(base)
    return dict(passed=True, status='passed', stage=stage_file(act, era), frames=count, captures=count*4,
                source_frames=count-len(unsourced), unsourced_frames=unsourced, source_pixels=pixels,
                live_palette_frames=sorted(live_frames), atlas_bytes=len(expected), live_palette_cluts=len(live_cluts),
                atlas_sha256=hashlib.sha256(arena).hexdigest(), capture_sha256=captures)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('programs', nargs='*', help='R1<act><era> (default: all ten)')
    args = parser.parse_args()
    programs = args.programs or PROGRAMS
    assert all(p in PROGRAMS for p in programs), programs
    from test_sprite_composition import verify_assets
    composition = verify_assets()
    count, meta = metadata()
    records = sources()
    parent = ROOT/'build/ppz-art-qa'; parent.mkdir(parents=True, exist_ok=True)
    exe = parent/'emulator'
    subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-I.deps/beetle-saturn/libretro-common/include',
                    'tools/emulator_test.c', '-o', str(exe)], cwd=ROOT, check=True)
    elf = ROOT/'build/saturn/sonic-cd-saturn-prototype.elf'
    listing = subprocess.check_output([str(ROOT/'.toolchain/bin/sh-elf-nm'), str(elf)], text=True)
    symbols = {l.split()[2]: l.split()[0] for l in listing.splitlines() if len(l.split()) == 3}
    paths = ['tools/test_ppz_art_emulator.py', 'tools/emulator_test.c', 'tools/check_object_vram.py',
             'tools/test_sprite_composition.py', 'tools/sprite_composition.py', 'src/zone_object_view.inc',
             'assets/generated/object-art.bin', 'assets/generated/object-frames.inc',
             'build/saturn/sonic-cd-saturn-prototype.elf', '.deps/beetle-saturn/mednafen_saturn_libretro.dylib']
    report = dict(passed=False, status='pending', programs={}, hardware_tested=False,
                  inputs={p: sha(ROOT/p) for p in paths},
                  disc_sha256=sha(ROOT/'dist/sonic-cd-saturn-prototype.bin'),
                  source_compositions=composition['compositions'], source_object_frames=composition['object_frames'],
                  method='Each atlas frame drawn alone with four flips through object_sprite; every canvas pixel '
                         'compared with the original composition (tools/check_zone_object_target.py bar).')
    (parent/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    for name in programs:
        act, era = int(name[2])-1, 'ABCD'.index(name[3])
        folder = parent/name; folder.mkdir(exist_ok=True)
        for old in folder.glob('zone-art-*'):
            old.unlink()
        env = {k: v for k, v in os.environ.items() if not k.startswith('SCD_')}
        env.update(SCD_ZONE='0', SCD_ZONE_ACT=str(act), SCD_ZONE_ERA=str(era), SCD_PPZ_OBJECT_ART=str(count),
                   SCD_WORLD_MAILBOX=symbols['_scd_world_mailbox'], SCD_ZONE_ART_MAILBOX=symbols['_scd_zone_art_mailbox'])
        command = [str(exe), str(ROOT/'.deps/beetle-saturn/mednafen_saturn_libretro.dylib'),
                   str(ROOT/'dist/sonic-cd-saturn-prototype.cue'), str(ROOT/'assets/private'), str(folder),
                   symbols['_scd_trace_mailbox'], symbols['_scd_audio_mailbox'], 'zones']
        pending = dict(status='pending', program=name)
        (folder/'report.json').write_text(json.dumps(pending, indent=2)+'\n')
        try:
            with (folder/'results.log').open('w') as stdout, (folder/'core.log').open('w') as stderr:
                subprocess.run(command, cwd=ROOT, env=env, stdout=stdout, stderr=stderr, check=True, timeout=3600)
            result = check(folder, act, era, count, meta, records)
            result.update(program=name, disc_sha256=report['disc_sha256'], inputs=report['inputs'])
            (folder/'report.json').write_text(json.dumps(result, indent=2)+'\n')
            report['programs'][name] = {k: v for k, v in result.items() if k != 'capture_sha256'}
        except BaseException as error:
            pending.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed',
                           error=f'{type(error).__name__}: {error}')
            (folder/'report.json').write_text(json.dumps(pending, indent=2)+'\n')
            report.update(status=pending['status'], error=pending['error'], failed_program=name)
            (parent/'report.json').write_text(json.dumps(report, indent=2)+'\n')
            raise
        (parent/'report.json').write_text(json.dumps(report, indent=2)+'\n')
        print(name, 'PASS', f'{result["captures"]} pictures / {result["source_pixels"]} original sprite pixels; '
              f'{result["atlas_bytes"]} atlas bytes', flush=True)
    assert sha(ROOT/'dist/sonic-cd-saturn-prototype.bin') == report['disc_sha256'], 'disc changed during the run'
    report.update(passed=True, status='passed'); (parent/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'PASS: Palmtree Panic art: {len(programs)} programs; {count*4} pictures each; '
          f'{composition["compositions"]} source compositions; disc {report["disc_sha256"][:12]}')


if __name__ == '__main__':
    main()
