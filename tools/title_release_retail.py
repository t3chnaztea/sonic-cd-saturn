#!/usr/bin/env python3
"""Measure when the retail level program releases the title-card control lock.

For each program (e.g. R31A, R42C) an IPX RAM stub seeds fresh-entry globals
and calls RunMMD with that act program, as tools/tt_retail_probe.py does. With
no input, the probe records per level update (levelFrames) the ctrlLocked byte
and whether the PLC queue (plcBuffer/plcTileCount) is still busy. It reports
the first update where ctrlLocked is clear, the last update with a busy PLC
queue before it, and the level update count at which the card routine reached
its wait (the retail card waits for PLC 2 to finish before unlocking).
Writes build/title-release/<program>.json and prints one line per program.

usage: title_release_retail.py PROGRAM [PROGRAM ...]
"""
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, 'tools')
import special_retail as sr
from extract_mmd import disc_files

ROUNDS = (1, 3, 4, 5, 6, 7, 8)
OUT = sr.ROOT/'build/title-release'


def measure(name, disc):
    main_vars, _, _, commands = sr.layout()
    engine, _ = sr.rs_symbols((sr.SRC/'Level/_Definitions.inc').read_text(), {'WORKRAM': 0xff0000}, 0xffffff)
    ipx = (sr.RETAIL/'IPX___.MMD').read_bytes()
    origin = struct.unpack_from('>I', ipx, 2)[0]
    code = ipx[0x100:0x1100]
    run_mmd, _ = sr.find(code, '2f0833c000a12010', origin)
    bram, _ = sr.find(code, '303c(....)6100(....)4a00670808f90000%08x' % main_vars['saveDisabled'], origin)
    stub_at, _ = sr.find(code, '13fc000000a1201313fc000000a1201a08f9000000a1201b70..6100....4e75', origin)
    program = disc[name + '__.MMD']
    vinterrupt = struct.unpack_from('>I', program, 16)[0]
    zone, act, era = ROUNDS.index(int(name[1])), int(name[2]) - 1, name[3]
    stub = struct.pack('>HHI', 0x13fc, 3, main_vars['lives'])
    stub += struct.pack('>HHI', 0x13fc, {'A': 1, 'B': 0, 'C': 2, 'D': 2}[era], main_vars['timeZone'])
    stub += struct.pack('>HHI', 0x13fc, 1 if era == 'C' else 0, main_vars['goodFuture'])
    stub += struct.pack('>HHI', 0x33fc, zone << 8 | act, main_vars['zoneAct'])
    stub += struct.pack('>HII', 0x23fc, 5000, main_vars['nextLifeScore'])
    stub += struct.pack('>HHHIH', 0x303c, commands['SCMD_' + name], 0x4eb9, run_mmd, 0x60fe)
    patches = [(bram, code[bram-origin:bram-origin+8], struct.pack('>HIH', 0x4ef9, stub_at, 0x4e71)),
               (stub_at, code[stub_at-origin:stub_at-origin+len(stub)], stub)]
    core = sr.Core()
    patched = False
    last = None
    rows = []
    word = lambda a: struct.unpack('>H', core.work_read(a, 2))[0]
    for frame in range(8000):
        core.pad = 0
        core.run()
        core.host.chunks.clear()
        if not patched and all(core.work_read(at, len(old)) == old for at, old, _ in patches):
            for at, _, new in patches:
                core.work_write(at, new)
            patched = True
        if not patched or core.work_read(0xfffd08, 4) != struct.pack('>I', vinterrupt):
            continue
        now = word(main_vars['levelFrames'])
        if now == last:
            continue
        last = now
        busy = any(core.work_read(engine['plcBuffer'], 96) + core.work_read(engine['plcTileCount'], 2))
        locked = core.work_read(engine['ctrlLocked'], 1)[0]
        rows.append((now, locked, int(busy), frame))
        if not locked and any(r[1] for r in rows):
            break
    first = next(i for i, r in enumerate(rows) if r[1])
    release = next(u for u, locked, _, _ in rows[first:] if not locked)
    plc_last = max((u for u, _, busy, _ in rows if busy and u < release), default=0)
    report = dict(program=name, release_update=release, last_plc_busy_update=plc_last,
                  rows=rows, program_bytes=len(program))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/f'{name}.json').write_text(json.dumps(report) + '\n')
    return report


def main():
    disc = disc_files((sr.RETAIL/'sonic.iso').read_bytes())
    for name in sys.argv[1:]:
        r = measure(name, disc)
        print(f"{name} release {r['release_update']} last_plc_busy {r['last_plc_busy_update']}")


if __name__ == '__main__':
    main()
