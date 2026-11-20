#!/usr/bin/env python3
"""Compare each zone's harvested stage palette with the palette retail gameplay shows.

QA oracle only. For every round's Act 1 Present program this boots the retail
disc in the pinned Sega CD core with the IPX RAM stub of level_title_retail.py
(fresh-entry globals, then RunMMD with the program's SCMD_ command), waits for
the title card to release control, and reads the live palette buffer
(Level/_Definitions.inc `palette`) 60 updates later. That buffer is what the
V-INT DMAs to CRAM.

The harvested palette is part 5 of the stage pack (tools/extract_zone_auto.py:
Sonic's PaletteTable entry 3 as line 0, then the level entry palette_id as lines
1-3). Lines 0 and 1, which carry Sonic and the shared objects (rings are tile
$A7AE, line 1), must match exactly. Entries of lines 2 and 3 that differ are
listed, not asserted: at the sampled update they are rotations or blanks of the
zone's cycled colours (the harvest is the table value, before any cycling).

Usage: python3 tools/stage_palette_retail.py [--retail DIR] [PROGRAM...]
"""
import argparse
import json
import struct
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import special_retail as sr
from convert_assets import palette

# Program, zone id (Main CPU `zone`), harvested pack for Act 1 Present.
PROGRAMS = {'R11A': (0, 'ppz0.bin'), 'R31A': (1, 'cc31A.bin'), 'R41A': (2, 'tt41A.bin'),
            'R51A': (3, 'qq51A.bin'), 'R61A': (4, 'ww61A.bin'), 'R71A': (5, 'ss71A.bin'),
            'R81A': (6, 'mm81A.bin')}
SETTLE = 60


def live_palette(program_name, zone):
    """The retail palette buffer SETTLE updates after the title card releases control."""
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
    stub = struct.pack('>HHI', 0x13fc, 3, main_vars['lives'])
    stub += struct.pack('>HHI', 0x13fc, 1, main_vars['timeZone'])
    stub += struct.pack('>HHI', 0x33fc, zone << 8, main_vars['zoneAct'])
    stub += struct.pack('>HII', 0x23fc, 5000, main_vars['nextLifeScore'])
    stub += struct.pack('>HHHIH', 0x303c, commands['SCMD_' + program_name], 0x4eb9, run_mmd, 0x60fe)
    assert len(stub) <= 64
    patches = [(bram, code[bram-origin:bram-origin+8], struct.pack('>HIH', 0x4ef9, stub_at, 0x4e71)),
               (stub_at, code[stub_at-origin:stub_at-origin+len(stub)], stub)]
    core = sr.Core(); patched = False; seen_card = False; released = 0
    for _ in range(9000):
        core.pad = 0; core.run(); core.host.chunks.clear()
        if not patched and all(core.work_read(at, len(old)) == old for at, old, _ in patches):
            for at, _, new in patches: core.work_write(at, new)
            patched = True
        if not patched or core.work_read(0xfffd08, 4) != struct.pack('>I', vinterrupt): continue
        card = core.work_read(engine['objTtlCardSlot'], 64)
        if card[0] == 0x3c: seen_card = True
        if seen_card and not core.work_read(engine['ctrlLocked'], 1)[0] and not card[0]: released += 1
        if released == SETTLE: return core.work_read(engine['palette'], 128)
    raise RuntimeError(f'{program_name}: level never released control')


def compare(program_name, live):
    zone, pack = PROGRAMS[program_name]
    data = (sr.ROOT/'assets/generated'/pack).read_bytes()
    offset, length = struct.unpack_from('>II', data, 4 + 5 * 8)
    harvested = data[offset:offset + length]; converted = palette(live)
    differ = [i for i in range(64) if harvested[i*2:i*2+2] != converted[i*2:i*2+2]]
    md = struct.unpack('>64H', live)
    return {'program': program_name, 'pack': pack, 'lines_0_1_match': not [i for i in differ if i < 32],
            'differing_entries': differ, 'ring_entries_line1': ['%03X' % md[16 + i] for i in (6, 12, 13, 14)],
            'sonic_entries_line0': ['%03X' % md[i] for i in (6, 12, 13, 14)], 'live': live.hex()}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--retail', type=Path, help='extracted retail disc folder (default build/retail)')
    parser.add_argument('--one', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('programs', nargs='*', default=list(PROGRAMS))
    args = parser.parse_args()
    if args.retail: sr.RETAIL = args.retail
    if args.one:
        # The core is process-global, so each program boots in its own process.
        name = args.programs[0]
        print(json.dumps(compare(name, live_palette(name, PROGRAMS[name][0]))))
        return
    rows = []
    for name in args.programs:
        command = [sys.executable, __file__, '--one', name] + (['--retail', str(args.retail)] if args.retail else [])
        rows.append(json.loads(subprocess.run(command, check=True, capture_output=True, text=True).stdout.splitlines()[-1]))
        r = rows[-1]
        print(f"{name} {r['pack']}: lines 0-1 {'match' if r['lines_0_1_match'] else 'DIFFER'}; "
              f"ring line 1 entries 6/12/13/14 {' '.join(r['ring_entries_line1'])}; "
              f"differing line 2-3 entries {r['differing_entries']}")
    out = sr.ROOT/'build/stage-palette-retail.json'
    out.write_text(json.dumps(rows, indent=1) + '\n')
    assert all(r['lines_0_1_match'] for r in rows), 'harvested lines 0-1 differ from retail gameplay'


if __name__ == '__main__':
    main()
