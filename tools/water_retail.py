#!/usr/bin/env python3
"""Retail Tidal Tempest water oracle: water palette and water height per act/era.

QA oracle only (needs the private disc in build/retail). Each Tidal Tempest
program boots in the pinned Sega CD core through the IPX RAM stub of
stage_palette_retail.py, with the time zone set for its era. After the title
card releases control the probe records, per level update with no input:
the palette and waterPalette buffers (Level/_Definitions.inc; V-INT DMAs the
latter when waterFullscreen is set and the H-INT handler switches to it at the
water line), waterHeight, waterHeight2, destWaterHeight, waterFullscreen,
vdpReg0A (the H-INT line), cameraY and Sonic's position.

Output: build/water/retail.json. Usage: python3 tools/water_retail.py [PROGRAM...]
"""
import json
import struct
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import special_retail as sr

# Program -> native era index (0 Present, 1 Past, 2 Good Future, 3 Bad Future)
# and Main CPU timeZone (0 past, 1 present, 2 future).
ERAS = {'A': (0, 1), 'B': (1, 0), 'C': (2, 2), 'D': (3, 2)}
PROGRAMS = [f'R4{a}{e}' for a in '12' for e in 'ABCD'] + ['R43C', 'R43D']
FRAMES = 240


def capture(program_name, hold=None):
    from extract_mmd import disc_files
    main_vars, _, _, commands = sr.layout()
    engine, _ = sr.rs_symbols((sr.SRC/'Level/_Definitions.inc').read_text(), {'WORKRAM': 0xff0000}, 0xffffff)
    ipx = (sr.RETAIL/'IPX___.MMD').read_bytes()
    origin = struct.unpack_from('>I', ipx, 2)[0]; code = ipx[0x100:0x1100]
    run_mmd, _ = sr.find(code, '2f0833c000a12010', origin)
    bram, _ = sr.find(code, '303c(....)6100(....)4a00670808f90000%08x' % main_vars['saveDisabled'], origin)
    stub_at, _ = sr.find(code, '13fc000000a1201313fc000000a1201a08f9000000a1201b70..6100....4e75', origin)
    program = disc_files((sr.RETAIL/'sonic.iso').read_bytes())[program_name + '__.MMD']
    vinterrupt = struct.unpack_from('>I', program, 16)[0]
    act = int(program_name[2]) - 1; era, zone_time = ERAS[program_name[3]]
    stub = struct.pack('>HHI', 0x13fc, 3, main_vars['lives'])
    stub += struct.pack('>HHI', 0x13fc, zone_time, main_vars['timeZone'])
    stub += struct.pack('>HHI', 0x13fc, 1 if era == 2 else 0, main_vars['goodFuture'])
    stub += struct.pack('>HHI', 0x33fc, 2 << 8 | act, main_vars['zoneAct'])
    stub += struct.pack('>HII', 0x23fc, 5000, main_vars['nextLifeScore'])
    stub += struct.pack('>HHHIH', 0x303c, commands['SCMD_' + program_name], 0x4eb9, run_mmd, 0x60fe)
    assert len(stub) <= 64
    patches = [(bram, code[bram-origin:bram-origin+8], struct.pack('>HIH', 0x4ef9, stub_at, 0x4e71)),
               (stub_at, code[stub_at-origin:stub_at-origin+len(stub)], stub)]
    core = sr.Core(); patched = False; seen_card = False; released = 0; rows = []; shots = []
    word = lambda name, off=0: struct.unpack('>h', core.work_read(engine[name] + off, 2))[0]
    for _ in range(12000):
        core.pad = 0; core.run(); core.host.chunks.clear()
        if not patched and all(core.work_read(at, len(old)) == old for at, old, _ in patches):
            for at, _, new in patches: core.work_write(at, new)
            patched = True
        if not patched or core.work_read(0xfffd08, 4) != struct.pack('>I', vinterrupt): continue
        card = core.work_read(engine['objTtlCardSlot'], 64)
        if card[0] == 0x3c: seen_card = True
        if not (seen_card and not core.work_read(engine['ctrlLocked'], 1)[0] and not card[0]): continue
        released += 1
        if hold is not None:
            # Fixture: hold Sonic at (x, water + dy) with zero velocity; frames are the evidence.
            water = word('waterHeight')
            core.work_write(engine['objPlayerSlot'] + 8, struct.pack('>h', hold[0]))
            core.work_write(engine['objPlayerSlot'] + 12, struct.pack('>h', water + hold[1]))
            core.work_write(engine['objPlayerSlot'] + 16, b'\0\0\0\0')
            if released >= 60 and released < 90:
                w, h, data = core.frame
                shots.append({'hint': word('vdpReg0A') & 255, 'full': core.work_read(engine['waterFullscreen'], 1)[0],
                              'water': water, 'camera_y': word('cameraY'), 'width': w, 'height': h, 'frame': data.hex()})
            if released == 90:
                return {'program': program_name, 'palette': core.work_read(engine['palette'], 128).hex(),
                        'water_palette': core.work_read(engine['waterPalette'], 128).hex(), 'shots': shots}
            continue
        rows.append({'water': word('waterHeight'), 'water2': word('waterHeight2'),
                     'dest': word('destWaterHeight'), 'full': core.work_read(engine['waterFullscreen'], 1)[0],
                     'hint': word('vdpReg0A') & 255, 'camera_y': word('cameraY'),
                     'x': word('objPlayerSlot', 8), 'y': word('objPlayerSlot', 12)})
        if released == 1:
            palette = core.work_read(engine['palette'], 128).hex()
            water_palette = core.work_read(engine['waterPalette'], 128).hex()
        if released == FRAMES:
            return {'program': program_name, 'act': act, 'era': era, 'palette': palette,
                    'water_palette': water_palette,
                    'water_palette_late': core.work_read(engine['waterPalette'], 128).hex(), 'frames': rows}
    raise RuntimeError(f'{program_name}: level never released control')


def md_rgb565(word, mapping):
    r, g, b = ((word >> s) & 7 for s in (1, 5, 9))
    return mapping(r, g, b)


def line_rows(r, name, dy):
    import itertools
    normal = [int(r['palette'][i:i+4], 16) for i in range(0, 256, 4)]
    wet = [int(r['water_palette'][i:i+4], 16) for i in range(0, 256, 4)]
    first = r['shots'][0]; w, h = first['width'], first['height']
    pixels = lambda shot, y: {int.from_bytes(bytes.fromhex(shot['frame'][(y*w+x)*4:(y*w+x)*4+4]), 'little') for x in range(w)}
    # Calibrate the core's 3-bit to RGB565 mapping on the top rows (normal palette only).
    top = set().union(*(pixels(first, y) for y in range(8)))
    # Genesis Plus GX: 3-bit levels doubled to 4 bits, scaled to 5/6/5 with rounding.
    candidates = {'gx': lambda r, g, b: int(2*r*31/15+.5) << 11 | int(2*g*63/15+.5) << 5 | int(2*b*31/15+.5)}
    best = max(candidates, key=lambda k: len(top & {md_rgb565(c, candidates[k]) for c in normal}))
    conv = candidates[best]
    nset = {md_rgb565(c, conv) for c in normal}; wset = {md_rgb565(c, conv) for c in wet}
    normal_only, water_only = nset - wset, wset - nset
    rows = []
    for shot in r['shots']:
        first_water = last_normal = None
        for y in range(h):
            colours = pixels(shot, y)
            if colours & water_only and first_water is None: first_water = y
            if colours & normal_only: last_normal = y
        rows.append({'hint': shot['hint'], 'full': shot['full'], 'water_minus_camera': shot['water'] - shot['camera_y'],
                     'first_water_row': first_water, 'last_normal_row': last_normal})
    print(f"{name} dy {dy} ({best}, calibrated {len(top & nset)}/{len(top)}):",
          ' '.join(f"h{x['hint']}/w{x['first_water_row']}/n{x['last_normal_row']}" for x in rows[:6]))
    return {'program': name, 'dy': dy, 'mapping': best, 'rows': rows}


def main():
    names = sys.argv[1:] or PROGRAMS
    if names[0] == '--one':
        print(json.dumps(capture(names[1]))); return
    if names[0] == '--line-one':
        print(json.dumps(capture(names[1], (int(names[2]), int(names[3]))))); return
    if names[0] == '--line':
        # Where the retail water palette starts relative to the H-INT line (vdpReg0A).
        out = sr.ROOT/'build/water'; out.mkdir(parents=True, exist_ok=True); report = []
        for name, dy in (('R41A', -60), ('R41A', -100), ('R41B', -60), ('R41D', -80)):
            r = json.loads(subprocess.run([sys.executable, __file__, '--line-one', name, '700', str(dy)], check=True,
                                          capture_output=True, text=True).stdout.splitlines()[-1])
            report.append(line_rows(r, name, dy))
        (out/'retail-line.json').write_text(json.dumps(report, indent=1) + '\n')
        return
    out = sr.ROOT/'build/water'; out.mkdir(parents=True, exist_ok=True); rows = []
    for name in names:
        result = subprocess.run([sys.executable, __file__, '--one', name], check=True, capture_output=True, text=True)
        rows.append(json.loads(result.stdout.splitlines()[-1])); r = rows[-1]; f = r['frames']
        print(f"{name}: water {f[0]['water']}..{f[-1]['water']} hint {f[0]['hint']} camera {f[0]['camera_y']} "
              f"player {f[0]['x']},{f[0]['y']} full {f[0]['full']}")
    (out/'retail.json').write_text(json.dumps(rows, indent=1) + '\n')


if __name__ == '__main__':
    main()
