#!/usr/bin/env python3
"""Retail vertical camera oracle (QA only; private disc in build/retail).

Plays a pad script ("COUNT PAD" lines; host bits 128 Right, 64 Left, 32 Down,
16 Up, 1 Jump) in a retail round program in the Sega CD core, one pad per level
update (levelFrames), and records after every update: cameraY (16.16), Sonic's
Y (16.16), oFlags, ground velocity (oVar14), oRoutine, topBound, bottomBound and
camYCenter. tools/camera_retail_test.c then feeds each row's player state and
bounds to the native scroll_v (src/camera_v.c) and requires the retail camera.
With HOUTPUT it also records, per update, cameraX (16.16), Sonic's X (16.16),
oPlayerCtrl, ground velocity, oFlags, oRoutine, leftBound, rightBound and
camXCenter for tools/camera_h_retail_test.c (scroll_h and PLAYER.C scr_h).

usage: camera_retail.py PROGRAM SCRIPT OUTPUT [UPDATES [HOUTPUT]]   e.g. R11A
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import special_retail as sr
from extract_mmd import disc_files

ZONES = {1: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5, 8: 6}


def main():
    name, script, output = sys.argv[1], sys.argv[2], sys.argv[3]
    limit = int(sys.argv[4]) if len(sys.argv) > 4 else 800
    houtput = sys.argv[5] if len(sys.argv) > 5 else None
    hrows = []
    pads = []
    for line in open(script):
        n, pad = map(int, line.split())
        pads += [pad] * n
    rnd, act, era = int(name[1]), int(name[2]), name[3]
    main_vars, _, _, commands = sr.layout()
    engine, _ = sr.rs_symbols((sr.SRC/'Level/_Definitions.inc').read_text(), {'WORKRAM': 0xff0000}, 0xffffff)
    ipx = (sr.RETAIL/'IPX___.MMD').read_bytes()
    origin = struct.unpack_from('>I', ipx, 2)[0]
    code = ipx[0x100:0x1100]
    run_mmd, _ = sr.find(code, '2f0833c000a12010', origin)
    bram, _ = sr.find(code, '303c(....)6100(....)4a00670808f90000%08x' % main_vars['saveDisabled'], origin)
    stub_at, _ = sr.find(code, '13fc000000a1201313fc000000a1201a08f9000000a1201b70..6100....4e75', origin)
    program = disc_files((sr.RETAIL/'sonic.iso').read_bytes())[name + '__.MMD']
    vinterrupt = struct.unpack_from('>I', program, 16)[0]
    zone_time = {'A': 1, 'B': 0, 'C': 2, 'D': 2}[era]
    stub = struct.pack('>HHI', 0x13fc, 3, main_vars['lives'])
    stub += struct.pack('>HHI', 0x13fc, zone_time, main_vars['timeZone'])
    stub += struct.pack('>HHI', 0x13fc, 1 if era == 'C' else 0, main_vars['goodFuture'])
    stub += struct.pack('>HHI', 0x33fc, ZONES[rnd] << 8 | (act - 1), main_vars['zoneAct'])
    stub += struct.pack('>HII', 0x23fc, 5000, main_vars['nextLifeScore'])
    stub += struct.pack('>HHHIH', 0x303c, commands['SCMD_' + name], 0x4eb9, run_mmd, 0x60fe)
    patches = [(bram, code[bram-origin:bram-origin+8], struct.pack('>HIH', 0x4ef9, stub_at, 0x4e71)),
               (stub_at, code[stub_at-origin:stub_at-origin+len(stub)], stub)]
    core = sr.Core()
    patched = False
    last = None
    rows = []
    word = lambda n, off=0: struct.unpack('>h', core.work_read(engine[n] + off, 2))[0]
    for _ in range(limit * 4 + 4000):
        index = len(rows)
        want = pads[index] if index < len(pads) else 0
        core.pad = (8 if want & 128 else 0) | (4 if want & 64 else 0) | (2 if want & 32 else 0) | \
                   (1 if want & 16 else 0) | (16 if want & 1 else 0)
        core.run()
        core.host.chunks.clear()
        if not patched and all(core.work_read(at, len(old)) == old for at, old, _ in patches):
            for at, _, new in patches:
                core.work_write(at, new)
            patched = True
        if not patched or core.work_read(0xfffd08, 4) != struct.pack('>I', vinterrupt):
            continue
        now = word('levelFrames') if 'levelFrames' in engine else struct.unpack('>h', core.work_read(main_vars['levelFrames'], 2))[0]
        if now == last:
            continue
        last = now
        sonic = core.work_read(engine['objPlayerSlot'], 64)
        camera = struct.unpack('>i', core.work_read(engine['cameraY'], 4))[0]
        y = struct.unpack_from('>i', sonic, 12)[0]
        rows.append((now, camera, y, sonic[0x22], struct.unpack_from('>h', sonic, 0x14)[0], sonic[0x24],
                     word('topBound'), word('bottomBound'), word('camYCenter'), want))
        hrows.append((now, struct.unpack('>i', core.work_read(engine['cameraX'], 4))[0],
                      struct.unpack_from('>i', sonic, 8)[0], sonic[0x2c], struct.unpack_from('>h', sonic, 0x14)[0],
                      sonic[0x22], sonic[0x24], word('leftBound'), word('rightBound'), word('camXCenter'), want))
        if len(rows) >= limit:
            break
    with open(output, 'w') as f:
        for r in rows:
            f.write(' '.join(map(str, r)) + '\n')
    if houtput:
        with open(houtput, 'w') as f:
            for r in hrows:
                f.write(' '.join(map(str, r)) + '\n')
    print(f'{name}: {len(rows)} updates')


if __name__ == '__main__':
    main()
