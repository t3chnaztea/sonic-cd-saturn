#!/usr/bin/env python3
"""Play a pad script in a retail act program (Sega CD core).

A diagnostic reference for the native route hosts (tools/tt_route_search.c
and the other zones' searches). Like tools/level_title_retail.py, an explicit
IPX RAM stub seeds fresh-entry globals and calls RunMMD with
R<round><act><era>__.MMD (rounds 1, 3, 4, 5, 6, 7, 8); the level program and its
objects run untouched. After the stub the pad script ("COUNT PAD" lines,
host bits 128 Right, 64 Left, 32 Down, 16 Up, 1 Jump) is applied one pad per
level update, and Sonic's position is written per update:
seq pad x y waterHeight waterHeight2 yspeed status vint_frames (V-INT frames
the update took; retail lag makes the water sway advance 2 per frame),
then mspeed, xspeed, the $3E move-lock word, angle, cameraY, ctrlLocked and
the x and y subpixel words, and levelVIntCounter's low byte. Not an acceptance
test: level-select entry only, no preceding-act progression. Rounds without
water (1, 3, 5) write 0 in both water columns so the column layout is the
same for every round; rounds 4 and 6 read waterHeight as before.

--native-unlock N aligns the builds at control unlock. The native title card
keeps controls locked one update after its PLC 2 request (an accepted
deviation, PLAN.md); retail waits for the queue to drain, 9-22 updates longer.
N is the first native sequence that reads the pad (tt_route_search replay
with TT_ROUTE_TRACE prints "unlock N"). The pad stays neutral while retail
ctrlLocked is set; the first unlocked retail update then gets the pad native
sequence N's player step applied (two requests earlier), and each row gains
a final column: its native sequence (-1 before). Native src/player.c buffers
a simultaneous Down + jump into a spin dash (PLAN.md controls, a deliberate
improvement); retail needs a crouch first, so such a route diverges there.

Diagnostic env dumps are PREFIX_OBJECTS, PREFIX_TERRAIN, PREFIX_SIDE,
PREFIX_CAMERA, PREFIX_LEVEL_FRAMES, PREFIX_ORBIT, PREFIX_INVENTORY and PREFIX_WARP
(timeWarpTimer and timeZone columns) with
PREFIX = --env-prefix (default TT_PROBE).

--follow-warp follows a natural time warp the way IPX.asm RunLevel does: the
stub enters RunLevel's .LevelLoop (RunMMD, then SCMD_WARP and the destination
era's file while timeZone bit 7 is set) with its own R<round><act>A-D command
table, so rows continue in the destination era program (levelFrames restarts
there). Each row then gains a column before the native-sequence column: the
era index (0 Present, 1 Past, 2 Good Future, 3 Bad Future) of the program that
wrote it. --warp-native N:F (with --native-unlock) maps the destination era's
levelFrames F to native sequence N: the update that ends at levelFrames L gets
the pad of native sequence N + L - F, and its row that native sequence.
--warp-native auto[:F] (F default 2) takes N as the last source-era row's
native sequence + 1: the native host arrives at the end of the update that
commits the warp (the source program's last update), and its next update is
Sonic's first in the destination era, where retail ObjSonic_Init (frame 1)
restores the warp state and frame 2 is the first move.

usage: retail_probe.py ACT ERA SCRIPT OUTPUT [UPDATES] [--native-unlock N]
       [--round 1|3|4|5|6|7|8] [--env-prefix PREFIX] [--follow-warp] [--warp-native N:F]
"""
import os
import struct
import sys

sys.path.insert(0, 'tools')
import special_retail as sr
from extract_mmd import disc_files


ZONE = {1: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5, 8: 6}  # zoneAct high byte per round
READS_WATER = (4, 6)  # rounds whose probe rows read waterHeight (6 kept as before)


def main(argv=None, default_round=4):
    args = list(sys.argv[1:] if argv is None else argv)
    round_no = default_round
    if '--round' in args:
        at = args.index('--round')
        round_no = int(args[at + 1])
        del args[at:at + 2]
    assert round_no in ZONE, round_no
    prefix = 'TT_PROBE'
    if '--env-prefix' in args:
        at = args.index('--env-prefix')
        prefix = args[at + 1]
        del args[at:at + 2]
    env = lambda name: os.environ.get(f'{prefix}_{name}')
    native_unlock = None
    if '--native-unlock' in args:
        at = args.index('--native-unlock')
        native_unlock = int(args[at + 1])
        del args[at:at + 2]
    follow_warp = '--follow-warp' in args
    if follow_warp:
        args.remove('--follow-warp')
    warp_native = None
    if '--warp-native' in args:
        at = args.index('--warp-native')
        value = args[at + 1].split(':')
        warp_native = [value[0] if value[0] == 'auto' else int(value[0]), int(value[1]) if len(value) > 1 else 2]
        del args[at:at + 2]
    act, era, script, output = int(args[0]), args[1], args[2], args[3]
    limit = int(args[4]) if len(args) > 4 else 6000
    shift = 0 if native_unlock is None else None  # native sequence - retail row
    seen_locked = False
    pads = []
    for line in open(script):
        n, pad = map(int, line.split())
        pads += [pad] * n
    main_vars, _, _, commands = sr.layout()
    engine, _ = sr.rs_symbols((sr.SRC/'Level/_Definitions.inc').read_text(), {'WORKRAM': 0xff0000}, 0xffffff)
    ipx = (sr.RETAIL/'IPX___.MMD').read_bytes()
    origin = struct.unpack_from('>I', ipx, 2)[0]
    code = ipx[0x100:0x1100]
    run_mmd, _ = sr.find(code, '2f0833c000a12010', origin)
    bram, (command, displacement) = sr.find(code, '303c(....)6100(....)4a00670808f90000%08x' % main_vars['saveDisabled'], origin)
    stub_at, _ = sr.find(code, '13fc000000a1201313fc000000a1201a08f9000000a1201b70..6100....4e75', origin)
    name = f'R{round_no}{act}{era}'
    files = disc_files((sr.RETAIL/'sonic.iso').read_bytes())
    program = files[name + '__.MMD']
    vinterrupt = struct.unpack_from('>I', program, 16)[0]
    start_era = 'ABCD'.index(era)
    if follow_warp:
        # The four era programs share one V-INT vector; the warp cutscene
        # (SCMD_WARP) installs another, which marks the program change.
        assert act in (1, 2), 'acts 1-2 have time travel'
        assert all(struct.unpack_from('>I', files[f'R{round_no}{act}{e}__.MMD'], 16)[0] == vinterrupt for e in 'ABCD')
        level_loop, _ = sr.find(code, '6100....4a39%08x67..08390007%08x' % (main_vars['lives'], main_vars['timeZone']), origin)
    zone_time = {'A': 1, 'B': 0, 'C': 2, 'D': 2}[era]
    stub = struct.pack('>HHI', 0x13fc, 3, main_vars['lives'])
    stub += struct.pack('>HHI', 0x13fc, zone_time, main_vars['timeZone'])
    stub += struct.pack('>HHI', 0x13fc, 1 if era == 'C' else 0, main_vars['goodFuture'])
    stub += struct.pack('>HHI', 0x33fc, (ZONE[round_no] << 8) | (act - 1), main_vars['zoneAct'])
    stub += struct.pack('>HII', 0x23fc, 5000, main_vars['nextLifeScore'])
    if follow_warp:
        # moveq #cmd,d0; lea table(pc),a0; jsr .LevelLoop; bra.s *; table: A B C D
        assert commands['SCMD_' + name] < 128
        stub += struct.pack('>HHHHIH', 0x7000 | commands['SCMD_' + name], 0x41fa, 10, 0x4eb9, level_loop, 0x60fe)
        stub += bytes(commands[f'SCMD_R{round_no}{act}{e}'] for e in 'ABCD')
    else:
        stub += struct.pack('>HHHIH', 0x303c, commands['SCMD_' + name], 0x4eb9, run_mmd, 0x60fe)
    assert len(stub) <= 64
    patches = [(bram, code[bram-origin:bram-origin+8], struct.pack('>HIH', 0x4ef9, stub_at, 0x4e71)),
               (stub_at, code[stub_at-origin:stub_at-origin+len(stub)], stub)]
    core = sr.Core()
    dump_range, dump = None, None
    if env('OBJECTS'):
        first, last_row, path = env('OBJECTS').split(':', 2)
        dump_range, dump = (int(first), int(last_row)), open(path, 'w')
    terrain_range, terrain_dump = None, None
    if env('TERRAIN'):
        first, last_row, path = env('TERRAIN').split(':', 2)
        terrain_range, terrain_dump = (int(first), int(last_row)), open(path, 'w')
    camera_dump = open(env('CAMERA'), 'w') if env('CAMERA') else None
    frames_range, frames_dump, palette_dump, aniart_dump, sprites_dump = None, None, None, None, None
    if env('FRAMES'):
        first, last_row, path = env('FRAMES').split(':', 2)
        frames_range, frames_dump = (int(first), int(last_row)), open(path, 'w')
    patched = False
    last = None
    last_frame = 0
    rows = []
    word = lambda a: struct.unpack('>H', core.work_read(a, 2))[0]
    program_era = start_era
    await_restart = left_level = False
    for frame in range(limit * 3 + 4000):
        update = word(main_vars['levelFrames']) if patched else 0
        # pads[i] is the native row i + 2 request; the native player applies
        # a request two observations later (tt_route_search delayed), so native
        # sequence s steps with pads[s - 4]. Retail applies the pad it is fed on
        # the same update. Without --native-unlock, rows keep the old feed.
        index = (len(rows) - 2 + shift if native_unlock is None else len(rows) - 4 + shift) if shift is not None else -1
        if warp_native and program_era != start_era:
            index = warp_native[0] + word(main_vars['levelFrames']) + 1 - warp_native[1] - 4
        want = pads[index] if 0 <= index < len(pads) else 0
        core.pad = (8 if want & 128 else 0) | (4 if want & 64 else 0) | (2 if want & 32 else 0) | (1 if want & 16 else 0) | (16 if want & 1 else 0)
        core.run()
        core.host.chunks.clear()
        if not patched and all(core.work_read(at, len(old)) == old for at, old, _ in patches):
            for at, _, new in patches:
                core.work_write(at, new)
            patched = True
        vector = struct.unpack('>I', core.work_read(0xfffd08, 4))[0]
        if patched and rows and vector != vinterrupt:
            left_level = follow_warp
        if not patched or vector != vinterrupt:
            continue
        if left_level:
            # IPX RunLevel picked the destination from timeZone and goodFuture.
            zone = core.work_read(main_vars['timeZone'], 1)[0] & 0x7f
            good = core.work_read(main_vars['goodFuture'], 1)[0]
            program_era, last, await_restart, left_level = (1 if zone == 0 else 0 if zone == 1 else 2 if good else 3), None, True, False
            if warp_native and warp_native[0] == 'auto':
                assert native_unlock is not None and rows and rows[-1][-1] >= 0, 'auto warp mapping needs --native-unlock'
                warp_native[0] = rows[-1][-1] + 1
        now = word(main_vars['levelFrames'])
        if await_restart:
            # The destination program clears levelFrames during its init: rows
            # restart at its first update.
            if now != 1:
                continue
            await_restart = False
        if now == last:
            continue
        last = now
        lag, last_frame = frame - last_frame, frame
        sonic = core.work_read(engine['objPlayerSlot'], 64)
        x, y = struct.unpack_from('>hxxhxx', sonic, 8)
        rows.append((now, want, x, y, *((word(engine['waterHeight']), word(engine['waterHeight2'])) if round_no in READS_WATER else (0, 0)), struct.unpack_from('>h', sonic, 0x12)[0], sonic[0x22], lag, struct.unpack_from('>h', sonic, 0x14)[0], struct.unpack_from('>h', sonic, 0x10)[0], struct.unpack_from('>H', sonic, 0x3e)[0], sonic[0x26], word(0xfff704), core.work_read(engine['ctrlLocked'], 1)[0],
                     struct.unpack_from('>H', sonic, 10)[0], struct.unpack_from('>H', sonic, 14)[0],
                     core.work_read(main_vars['levelVIntCounter'] + 3, 1)[0]))
        if env('LEVEL_FRAMES'):
            rows[-1] += (word(main_vars['levelFrames']),)
        if env('ORBIT'):
            rows[-1] += (sonic[0x2b], sonic[0x39], sonic[0x2c])
        if env('INVENTORY'):
            rows[-1] += (word(main_vars['rings']), core.work_read(main_vars['shield'], 1)[0])
        if env('SHOTS') and core.frame:
            # Diagnostic (PREFIX_SHOTS=FIRST:LAST:DIR): the displayed frame of rows FIRST-LAST
            # as DIR/row-<row>.png (match native sequences with the rows' last column).
            first_s, last_s, path_s = env('SHOTS').split(':', 2)
            if int(first_s) <= len(rows) - 1 <= int(last_s):
                sr.png(os.path.join(path_s, 'row-%d.png' % (len(rows) - 1)), core.frame)
        if env('SONIC'):
            # Diagnostic (PREFIX_SONIC=FIRST:LAST:FILE): Sonic's 64-byte slot as hex.
            first_s, last_s, path_s = env('SONIC').split(':', 2)
            if int(first_s) <= len(rows) - 1 <= int(last_s):
                with open(path_s, 'a') as f:
                    f.write('%d %s\n' % (len(rows) - 1, sonic.hex()))
        if env('SLOT'):
            # Diagnostic (PREFIX_SLOT=SLOT:FIRST:LAST:FILE): one actor's 64 bytes as hex.
            slot_s, first_s, last_s, path_s = env('SLOT').split(':', 3)
            if int(first_s) <= len(rows) - 1 <= int(last_s):
                with open(path_s, 'a') as f:
                    f.write('%d %s\n' % (len(rows) - 1, core.work_read(engine['objPlayerSlot'] + 0x40 * int(slot_s), 0x40).hex()))
        if env('WORK'):
            # Diagnostic (PREFIX_WORK=ADDR:LEN:FIRST:LAST:FILE): LEN work-RAM bytes at hex ADDR as hex.
            addr_s, len_s, first_s, last_s, path_s = env('WORK').split(':', 4)
            if int(first_s) <= len(rows) - 1 <= int(last_s):
                with open(path_s, 'a') as f:
                    f.write('%d %s\n' % (len(rows) - 1, core.work_read(int(addr_s, 16), int(len_s)).hex()))
        if env('WARP'):
            rows[-1] += (word(engine['timeWarpTimer']), core.work_read(main_vars['timeZone'], 1)[0])
        if camera_dump:
            camera_dump.write('%d %d %d %d %d %d %d\n' % (len(rows) - 1, word(0xfff700), word(0xfff704), x,
                                                   core.work_read(engine['palCycleSteps'] + 3, 1)[0],
                                                   word(engine['leftBound']), word(engine['rightBound'])))
        if terrain_range and terrain_range[0] <= len(rows) - 1 <= terrain_range[1]:
            # The original floor sensors use x +/- X radius and y + Y radius.
            for sensor_x in (x + sonic[0x17], x - sonic[0x17]):
                for below in (0, 16):
                    sensor_y = y + sonic[0x16] + below
                    layout_offset = ((sensor_y >> 1) & 0x780) + ((sensor_x >> 8) & 0x7f)
                    chunk = core.work_read(engine['levelLayout'] + layout_offset, 1)[0]
                    block = 0
                    collision_id = 0
                    collision_ptr = 0
                    if chunk & 0x7f:
                        block_offset = ((chunk & 0x7f) - 1) * 512 + ((sensor_y >> 4) & 15) * 32 + ((sensor_x >> 4) & 15) * 2
                        block = struct.unpack('>H', core.swapped(core.word, 0x10000 + block_offset, 2))[0]
                        collision_ptr = struct.unpack('>I', core.work_read(engine['collisionPtr'], 4))[0]
                        collision_id = core.swapped(core.word, collision_ptr - 0x200000 + (block & 0x7ff), 1)[0]
                    terrain_dump.write('%d x=%d y=%d radius=%d,%d flags=%d angle=%d stick=%d sensor=%d,%d chunk=%d layout=%d block=%04x collision=%d collision_ptr=%06x\n' %
                                       (len(rows) - 1, x, y, sonic[0x17], sonic[0x16], sonic[0x22], sonic[0x26], sonic[0x38],
                                        sensor_x, sensor_y, chunk, layout_offset, block, collision_id, collision_ptr))
            if env('SIDE'):
                sensor_x, sensor_y = x + 13, y + 8
                layout_offset = ((sensor_y >> 1) & 0x780) + ((sensor_x >> 8) & 0x7f)
                chunk = core.work_read(engine['levelLayout'] + layout_offset, 1)[0]
                block = collision_id = 0
                if chunk & 0x7f:
                    block_offset = ((chunk & 0x7f) - 1) * 512 + ((sensor_y >> 4) & 15) * 32 + ((sensor_x >> 4) & 15) * 2
                    block = struct.unpack('>H', core.swapped(core.word, 0x10000 + block_offset, 2))[0]
                    collision_ptr = struct.unpack('>I', core.work_read(engine['collisionPtr'], 4))[0]
                    collision_id = core.swapped(core.word, collision_ptr - 0x200000 + (block & 0x7ff), 1)[0]
                terrain_dump.write('%d side sensor=%d,%d chunk=%d block=%04x collision=%d\n' %
                                   (len(rows) - 1, sensor_x, sensor_y, chunk, block, collision_id))
        if dump_range and dump_range[0] <= len(rows) - 1 <= dump_range[1]:
            # Diagnostic (PREFIX_OBJECTS=FIRST:LAST:FILE): every live object
            # slot on rows FIRST..LAST: row slot id subtype routine x xsub y ysub xspeed
            # render-flags $3A $3C,
            # and a 'row camera X Y' line.
            objects = core.work_read(engine['objPlayerSlot'], 0x40 * 128)
            label = len(rows) - 1
            dump.write('%d camera %d %d\n' % (label, word(0xfff700), word(0xfff704)))
            for k in range(128):
                o = objects[k * 0x40:(k + 1) * 0x40]
                if o[0]:
                    dump.write('%d %d %d %d %d %d %d %d %d %d %d %d %d\n' % ((label, k, o[0], o[0x28], o[0x24]) + struct.unpack_from('>hHhHh', o, 8)
                                                                  + (o[1],) + struct.unpack_from('>hh', o, 0x3a)))
        if frames_range and frames_range[0] <= len(rows) - 1 <= frames_range[1]:
            # Diagnostic (PREFIX_FRAMES=FIRST:LAST:FILE): animation phase state on rows
            # FIRST..LAST: 'row G levelFrames ringAnimTimer ringAnimFrame
            # ringLossAnimTimer ringLossAnimFrame timeStopTimer cameraX', then per live slot
            # 'row O slot id subtype routine mapFrame animFrame anim animTime render x y subtype2 byte$30'.
            label = len(rows) - 1
            g = core.work_read(main_vars['ringAnimTimer'], 6)
            frames_dump.write('%d G %d %d %d %d %d %d %d\n' % (label, word(main_vars['levelFrames']), g[0], g[1], g[4], g[5], word(main_vars['timeStopTimer']), word(0xfff700)))
            objects = core.work_read(engine['objPlayerSlot'], 0x40 * 128)
            for k in range(128):
                o = objects[k * 0x40:(k + 1) * 0x40]
                if o[0]:
                    frames_dump.write('%d O %d %d %d %d %d %d %d %d %d %d %d %d %d\n' % ((label, k, o[0], o[0x28], o[0x24], o[0x1a], o[0x1b], o[0x1c], o[0x1e], o[1])
                                                                               + struct.unpack_from('>hxxh', o, 8) + (o[0x29], o[0x30])))
        if env('PALETTE'):
            # Diagnostic (PREFIX_PALETTE=FILE): 'row levelFrames timeStopTimer' and the
            # 64-word palette buffer in hex, every row.
            if palette_dump is None:
                palette_dump = open(env('PALETTE'), 'w')
            palette_dump.write('%d %d %d %s\n' % (len(rows) - 1, word(main_vars['levelFrames']), word(main_vars['timeStopTimer']),
                                                 core.work_read(engine['palette'], 128).hex()))
        if env('ANIART'):
            # Diagnostic (PREFIX_ANIART=FILE): 'row levelFrames paused' and the six
            # aniArtFrames then the six aniArtTimers bytes, every row.
            if aniart_dump is None:
                aniart_dump = open(env('ANIART'), 'w')
            aniart_dump.write('%d %d %d %s\n' % (len(rows) - 1, word(main_vars['levelFrames']), core.work_read(engine['paused'], 1)[0],
                                                ' '.join(map(str, core.work_read(engine['aniArtFrames'], 12)))))
        if env('SPRITES'):
            # Diagnostic (PREFIX_SPRITES=FILE): 'row levelFrames' and 'link:tile:x' of
            # each of the 64 sprite-buffer entries, as hex, every row.
            if sprites_dump is None:
                sprites_dump = open(env('SPRITES'), 'w')
            spr = core.work_read(engine['sprites'], 0x200)
            sprites_dump.write('%d %d %s\n' % (len(rows) - 1, word(main_vars['levelFrames']),
                                               ' '.join('%02x:%04x:%d' % (spr[k * 8 + 3], struct.unpack_from('>H', spr, k * 8 + 4)[0], struct.unpack_from('>H', spr, k * 8 + 6)[0]) for k in range(64))))
        if follow_warp:
            rows[-1] += (program_era,)
        if native_unlock is not None and warp_native and program_era != start_era:
            rows[-1] += (warp_native[0] + now - warp_native[1],)
        elif native_unlock is not None:
            if shift is None:
                seen_locked = seen_locked or rows[-1][14] != 0
                if seen_locked and rows[-1][14] == 0:
                    shift = native_unlock - len(rows)  # next row reads the pad
            rows[-1] += (len(rows) - 1 + shift if shift is not None and len(rows) - 1 + shift >= native_unlock else -1,)
        if env('SHOT_SEQS') and core.frame and native_unlock is not None:
            # Diagnostic (PREFIX_SHOT_SEQS=SEQ,SEQ,...:DIR): the displayed frame of the rows
            # whose native-sequence column is listed, as DIR/seq-<seq>.png.
            seqs_s, path_s = env('SHOT_SEQS').split(':', 1)
            if str(rows[-1][-1]) in seqs_s.split(','):
                sr.png(os.path.join(path_s, 'seq-%d.png' % rows[-1][-1]), core.frame)
        if len(rows) >= limit:
            break
    with open(output, 'w') as f:
        for r in rows:
            f.write(' '.join(map(str, r)) + '\n')
    print('retail rows', len(rows), 'last', rows[-1] if rows else None)


if __name__ == '__main__':
    main()
