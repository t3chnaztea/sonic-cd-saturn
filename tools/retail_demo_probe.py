#!/usr/bin/env python3
"""Record Sonic per update in the retail attract demos (Sega CD core).

IPX.asm Demo_R11A, Demo_R43C and Demo_R82A (957-999) set zoneAct, timeZone and
goodFuture and RunMMD the demo program, which plays its own input (demoMode,
Level/Functions (General).asm ReadControllers). Like tools/retail_probe.py, an
IPX RAM stub does the same and calls RunMMD; no pad is pressed. One row per
level update: levelFrames x y ctrlLocked demoDataIndex moveLock($3E) status routine groundSpeed.

usage: retail_demo_probe.py R11A|R43C|R82A OUTPUT [UPDATES]
"""
import struct
import sys

sys.path.insert(0, 'tools')
import special_retail as sr
from extract_mmd import disc_files

DEMOS = {'R11A': (0x000, 1, 0), 'R43C': (0x202, 2, 1), 'R82A': (0x601, 1, 0)}  # zoneAct, timeZone, goodFuture


def main():
    name, output = sys.argv[1], sys.argv[2]
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 2100
    zone_act, time_zone, good = DEMOS[name]
    main_vars, _, _, commands = sr.layout()
    engine, _ = sr.rs_symbols((sr.SRC/'Level/_Definitions.inc').read_text(), {'WORKRAM': 0xff0000}, 0xffffff)
    ipx = (sr.RETAIL/'IPX___.MMD').read_bytes()
    origin = struct.unpack_from('>I', ipx, 2)[0]
    code = ipx[0x100:0x1100]
    run_mmd, _ = sr.find(code, '2f0833c000a12010', origin)
    bram, _ = sr.find(code, '303c(....)6100(....)4a00670808f90000%08x' % main_vars['saveDisabled'], origin)
    stub_at, _ = sr.find(code, '13fc000000a1201313fc000000a1201a08f9000000a1201b70..6100....4e75', origin)
    program = disc_files((sr.RETAIL/'sonic.iso').read_bytes())['DEMO%s.MMD' % name[1:]]
    vinterrupt = struct.unpack_from('>I', program, 16)[0]
    stub = struct.pack('>HHI', 0x13fc, 3, main_vars['lives'])
    stub += struct.pack('>HHI', 0x13fc, time_zone, main_vars['timeZone'])
    stub += struct.pack('>HHI', 0x13fc, good, main_vars['goodFuture'])
    stub += struct.pack('>HHI', 0x33fc, zone_act, main_vars['zoneAct'])
    stub += struct.pack('>HHHIH', 0x303c, commands['SCMD_%sDEMO' % name], 0x4eb9, run_mmd, 0x60fe)
    patches = [(bram, code[bram-origin:bram-origin+8], struct.pack('>HIH', 0x4ef9, stub_at, 0x4e71)),
               (stub_at, code[stub_at-origin:stub_at-origin+len(stub)], stub)]
    core = sr.Core()
    word = lambda a: struct.unpack('>H', core.work_read(a, 2))[0]
    patched, last, rows = False, None, []
    for _ in range(limit * 3 + 4000):
        core.pad = 0
        core.run()
        core.host.chunks.clear()
        if not patched and all(core.work_read(at, len(old)) == old for at, old, _ in patches):
            for at, _, new in patches:
                core.work_write(at, new)
            patched = True
        if not patched or struct.unpack('>I', core.work_read(0xfffd08, 4))[0] != vinterrupt:
            if rows:
                break  # the demo program has returned
            continue
        now = word(main_vars['levelFrames'])
        if now == last:
            continue
        last = now
        sonic = core.work_read(engine['objPlayerSlot'], 64)
        x, y = struct.unpack_from('>hxxhxx', sonic, 8)
        rows.append((now, x, y, core.work_read(engine['ctrlLocked'], 1)[0], word(engine['demoDataIndex']),
                     struct.unpack_from('>H', sonic, 0x3e)[0], sonic[0x22], sonic[0x24], struct.unpack_from('>h', sonic, 0x14)[0]))
        if len(rows) >= limit:
            break
    with open(output, 'w') as f:
        f.write(''.join('%d %d %d %d %d %d %d %d %d\n' % r for r in rows))
    print('retail demo', name, 'rows', len(rows), 'last', rows[-1] if rows else None)


if __name__ == '__main__':
    main()
