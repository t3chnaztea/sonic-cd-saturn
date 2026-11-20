#!/usr/bin/env python3
"""Capture the original Sega CD CC1 scroll tables for explicitly recorded camera fixtures.

This is a raster research fixture, not a controller playthrough. It boots the
original program, lets its title card finish, writes camera/player fixture
inputs, then records the actual CPU-produced deformation and scroll buffers.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

import special_retail as sr
from extract_mmd import disc_files
from zone_object_source import dependencies


def boot(era, act=1, rnd=3, settle=30):
    main, _, _, commands = sr.layout()
    engine, _ = sr.rs_symbols((sr.SRC/'Level/_Definitions.inc').read_text(), {'WORKRAM': 0xff0000}, 0xffffff)
    ipx = (sr.RETAIL/'IPX___.MMD').read_bytes()
    origin = struct.unpack_from('>I', ipx, 2)[0]
    code = ipx[0x100:0x1100]
    run, _ = sr.find(code, '2f0833c000a12010', origin)
    bram, _ = sr.find(code, '303c(....)6100(....)4a00670808f90000%08x' % main['saveDisabled'], origin)
    stub_at, _ = sr.find(code, '13fc000000a1201313fc000000a1201a08f9000000a1201b70..6100....4e75', origin)
    name = f'R{rnd}{act}'+era
    program = disc_files((sr.RETAIL/'sonic.iso').read_bytes())[name+'__.MMD']
    vint = struct.unpack_from('>I', program, 16)[0]
    stub = b''.join(struct.pack('>HHI', 0x13fc, value, main[key]) for key, value in
                    [('lives', 3), ('timeZone', {'A': 1, 'B': 0, 'C': 2, 'D': 2}[era]), ('goodFuture', int(era == 'C'))])
    stub += struct.pack('>HHI', 0x33fc, {1: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5, 8: 6}[rnd] << 8 | (act-1), main['zoneAct'])
    stub += struct.pack('>HII', 0x23fc, 5000, main['nextLifeScore'])
    stub += struct.pack('>HHHIH', 0x303c, commands['SCMD_'+name], 0x4eb9, run, 0x60fe)
    assert len(stub) <= 64
    patches = [(bram, code[bram-origin:bram-origin+8], struct.pack('>HIH', 0x4ef9, stub_at, 0x4e71)),
               (stub_at, code[stub_at-origin:stub_at-origin+len(stub)], stub)]
    core = sr.Core()
    patched = seen = False
    release = 0
    for frame in range(10000):
        core.pad = 0
        core.run()
        core.host.chunks.clear()
        if not patched and all(core.work_read(at, len(old)) == old for at, old, _ in patches):
            for at, _, new in patches:
                core.work_write(at, new)
            patched = True
        if not patched or core.work_read(0xfffd08, 4) != struct.pack('>I', vint):
            continue
        card = core.work_read(engine['objTtlCardSlot'], 64)
        if card[0] == 0x3c:
            seen = True
        if seen and not core.work_read(engine['ctrlLocked'], 1)[0] and not card[0]:
            release += 1
        if release == settle:
            return core, engine, frame, program
    raise RuntimeError(name+' did not finish its title card')


def capture(era, out, act=1):
    core, e, frame, program = boot(era, act)
    out.mkdir(parents=True, exist_ok=True)
    keys = ['cameraX', 'cameraY', 'cameraBgX', 'cameraBgY', 'cameraBg2X', 'cameraBg2Y', 'cameraBg3X', 'cameraBg3Y']
    samples = []
    # Include non-divisible X positions to expose interpolation fraction seeds,
    # and the high/low visible windows that the parked scalar IR cannot express.
    fixtures = [(x, y, 0) for x in [0, 1, 31, 255, 1001, 4093, 8191, 11800]
                for y in [0, 240, 360, 600, 1000, 1248, 1296]]
    fixtures += [(x, 360, dx) for x in (255, 1001, 4093) for dx in (-16, -1, 1, 16)]
    for index, (x, y, player_dx) in enumerate(fixtures):
        by = max(0, 536-((1312-y)//2))
        inputs = dict(cameraX=x, cameraY=y, cameraBgX=x*12//256, cameraBgY=by,
                      cameraBg2X=x*24//256, cameraBg2Y=by, cameraBg3X=x*16//256, cameraBg3Y=by)
        player = bytearray(core.work_read(e['objPlayerSlot'], 64))
        struct.pack_into('>I', player, e['oX'], (x+160+player_dx)*65536)
        struct.pack_into('>I', player, e['oY'], (y+96)*65536)
        player[e['oXVel']:e['oXVel']+6] = bytes(6)
        player[e['oFlags']] = 2
        player[e['oRoutine']] = 2
        player[0x2c] = 0  # recorded Sonic control byte; release any previous grab
        player[0x30:0x32] = struct.pack('>H', 120)
        # Section DMA can leave the CPU halfway through scroll() at a video
        # boundary. Settle the new section before measuring a complete update;
        # merely seeing the first accumulator change is insufficient.
        for _ in range(32):
            core.work_write(e['objPlayerSlot'], player)
            for key, value in inputs.items():
                core.work_write(e[key], struct.pack('>I', value*65536))
            core.pad = 0
            core.run()
            frame += 1
            core.host.chunks.clear()
        core.work_write(e['objPlayerSlot'], player)
        for key, value in inputs.items():
            core.work_write(e[key], struct.pack('>I', value*65536))
        before = core.work_read(e['deformBuffer'], 512)
        # Crossing an art section can suspend gameplay for PLC processing.
        # One libretro frame is therefore not proof that scroll() ran. Its
        # first cloud accumulator advances by its original LineSpdTbl[0].
        first = struct.unpack_from('>I', before)[0]
        step = 32768 if era == 'B' else 49152
        for waited in range(1, 121):
            core.pad = 0
            core.run()
            frame += 1
            core.host.chunks.clear()
            after = core.work_read(e['deformBuffer'], 512)
            delta = (struct.unpack_from('>I', after)[0]-first)&0xffffffff
            if delta:
                assert delta == step, ('unexpected original scroll updates', era, index, delta)
                break
        else:
            raise RuntimeError(f'R3{act}{era} fixture {index}: no original scroll update')
        scroll = core.work_read(e['hscroll'], 1024)
        actual = {key: struct.unpack('>i', core.work_read(e[key], 4))[0] for key in keys}
        scroll_dx = struct.unpack('>h', core.work_read(e['scrollXDiff'], 2))[0]
        (out/f'{index:03}-deform-before.bin').write_bytes(before)
        (out/f'{index:03}-deform-after.bin').write_bytes(after)
        (out/f'{index:03}-hscroll.bin').write_bytes(scroll)
        samples.append(dict(index=index, frame=frame, settled_vblanks=32, waited_vblanks=waited, inputs=inputs, actual_16_16=actual,
                            scroll_x_diff_8_8=scroll_dx,
                            player_input=player.hex(), player_output=core.work_read(e['objPlayerSlot'], 64).hex(),
                            before_sha256=hashlib.sha256(before).hexdigest(), after_sha256=hashlib.sha256(after).hexdigest(),
                            scroll_sha256=hashlib.sha256(scroll).hexdigest()))
    report = dict(program=f'R3{act}'+era, program_sha256=hashlib.sha256(program).hexdigest(),
                  tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), dependencies=dependencies(),
                  addresses={key: e[key] for key in keys+['deformBuffer', 'hscroll', 'objPlayerSlot']}, samples=samples,
                  limits='Original CPU output after explicit camera/player fixtures. No claim of gameplay routes or native raster parity.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'R3{act}'+era, len(samples), 'original CPU scroll fixtures', out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('era', choices=list('ABCD'))
    parser.add_argument('--out', type=Path)
    parser.add_argument('--act',type=int,choices=(1,2,3),default=1)
    args = parser.parse_args()
    if args.act == 3 and args.era in 'AB':
        parser.error('Act 3 has only C and D programs')
    capture(args.era, args.out or sr.ROOT/f'build/cc{args.act}/scroll-retail'/(f'R3{args.act}'+args.era),args.act)

if __name__ == '__main__':
    main()
