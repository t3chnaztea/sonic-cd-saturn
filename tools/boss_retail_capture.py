#!/usr/bin/env python3
"""Capture the retail Act 3 boss fights and check the Saturn boss art against them.

Boots R43C/R43D (Tidal Tempest) or R53C/R53D (Quartz Quadrant) with the IPX
entry stub of tools/zone_object_source.py and lets the original program run
the fight. The fixture only writes Sonic's position and roll state (as the
Saturn probes in tools/emulator_test.c SCD_TT3/QQ3_BOSS_ACTWK do) and keeps 50
rings; the boss objects, their PLCs and palettes are untouched. It is an art
fixture, not a gameplay route.

A phase is each distinct (set of live boss actor IDs, boss-art VRAM content).
For each phase the tool writes VDP VRAM, CRAM, the sprite attribute table and
the live boss actors to build/boss-retail/<program>/phase-NN/.

It then compares every record of the Saturn boss zone-art sources
(zone_object_assets.source_paths: <program>-boss, -boss2) with the phases in
which the record's retail actor is live: mapping address and tile word, the
VRAM bytes of every 8x8 tile each pose reads, the displayed pose against the
sprite table, and the colours its pixels use (the retail palette buffer)
against the Saturn palette (stage palette, line 1 from boss<round><era>.pal).
Each record must also have rows in the era's Saturn zone-art pack. Writes
build/boss-retail/<program>/report.json; exits 1 on any mismatch. Emulator
evidence only; not a hardware result.

usage: boss_retail_capture.py [PROGRAM ...]   (default R43C R43D R53C R53D)
"""
import ctypes as C
import hashlib
import json
import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import special_retail as sr
from convert_assets import OUT, palette as md_to_rgb555
from extract_mmd import ORIGIN, disc_files
from zone_object_assets import SOURCE, source_paths
from zone_object_source import ROUNDS, dependencies, read_tiles

OUTDIR = sr.ROOT/'build/boss-retail'
PHASE_LIMIT = 40


def boot(name):
    """Yield (core, engine, main) once per frame after the title card has
    released control; as zone_object_source.capture's entry stub."""
    main, _, _, commands = sr.layout()
    engine, _ = sr.rs_symbols((sr.SRC/'Level/_Definitions.inc').read_text(), {'WORKRAM': 0xff0000}, 0xffffff)
    ipx = (sr.RETAIL/'IPX___.MMD').read_bytes()
    origin = struct.unpack_from('>I', ipx, 2)[0]; code = ipx[0x100:0x1100]
    run, _ = sr.find(code, '2f0833c000a12010', origin)
    bram, _ = sr.find(code, '303c(....)6100(....)4a00670808f90000%08x' % main['saveDisabled'], origin)
    stub_at, _ = sr.find(code, '13fc000000a1201313fc000000a1201a08f9000000a1201b70..6100....4e75', origin)
    program = disc_files((sr.RETAIL/'sonic.iso').read_bytes())[name+'__.MMD']
    vint = struct.unpack_from('>I', program, 16)[0]
    zone, act, era = ROUNDS.index(int(name[1])), int(name[2])-1, name[3]
    stub = b''.join(struct.pack('>HHI', 0x13fc, value, main[key]) for key, value in
                    [('lives', 3), ('timeZone', 2), ('goodFuture', int(era == 'C'))])
    stub += struct.pack('>HHI', 0x33fc, zone << 8 | act, main['zoneAct'])
    stub += struct.pack('>HII', 0x23fc, 5000, main['nextLifeScore'])
    stub += struct.pack('>HHHIH', 0x303c, commands['SCMD_'+name], 0x4eb9, run, 0x60fe)
    patches = [(bram, code[bram-origin:bram-origin+8], struct.pack('>HIH', 0x4ef9, stub_at, 0x4e71)),
               (stub_at, code[stub_at-origin:stub_at-origin+len(stub)], stub)]
    core = sr.Core(); patched = seen = False; release = 0
    for _ in range(4000):
        core.run(); core.host.chunks.clear()
        if not patched and all(core.work_read(at, len(old)) == old for at, old, _ in patches):
            for at, _, new in patches: core.work_write(at, new)
            patched = True
        if not patched or core.work_read(0xfffd08, 4) != struct.pack('>I', vint): continue
        card = core.work_read(engine['objTtlCardSlot'], 64)
        if card[0] == 0x3c: seen = True
        if seen and not core.work_read(engine['ctrlLocked'], 1)[0] and not card[0]: release += 1
        if release >= 30: break
    else:
        raise RuntimeError(f'{name}: level never released control')
    return core, engine, main, program


def saturn_records(name):
    """(source folder, record, Saturn source VRAM) of the boss zone-art sources."""
    out = []
    # The QQ3 (R53) boss sources may predate their source_paths entry: take
    # the -boss/-boss2 folders tools/extract_mmd.py wrote as well.
    paths = [p for p in source_paths(name) if p.name.endswith(('-boss', '-boss2'))]
    paths += [p for p in (SOURCE/(name+'-boss'), SOURCE/(name+'-boss2')) if p not in paths and (p/'source.json').exists()]
    for path in paths:
        src = json.loads((path/'source.json').read_text()); vram = (path/'vram.bin').read_bytes()
        out += [(path.name, r, vram) for r in src['objects']]
    return out


def live_actors(core, engine, ids):
    return [(at, core.work_read(at, 64)) for at in range(engine['dynObjects'], engine['objectsEnd'], 64)
            if core.work_read(at, 1)[0] in ids]


def cram_words(core):
    """CRAM as Mega Drive words (special_retail.Retail.snapshot)."""
    return [(v>>6&7)<<9|(v>>3&7)<<5|(v&7)<<1 for v in struct.unpack('<64H', C.string_at(core.cram, 128))]


class Driver:
    """Sonic's position per frame (tools/emulator_test.c boss probes)."""

    def __init__(self, name, core, engine, main):
        self.name, self.core, self.e, self.main = name, core, engine, main
        self.stage, self.since, self.t, self.trail, self.follow = 0, 0, 0, [], None

    def hold(self, x, y, roll):
        e = self.e; p = bytearray(self.core.work_read(e['objPlayerSlot'], 64))
        struct.pack_into('>hHhHhhh', p, 8, x, 0, y, 0, 0, 256 if roll else 0, 0)
        p[e['oFlags']] = 6 if roll else 2
        p[e['oAnim']] = 2 if roll else 0
        self.core.work_write(e['objPlayerSlot'], p)

    def x(self):
        return struct.unpack('>h', self.core.work_read(self.e['objPlayerSlot']+8, 2))[0]

    def actor(self, oid):
        return next((a for _, a in live_actors(self.core, self.e, {oid})), None)

    def step(self):
        """Set this frame's pad and player; False once the fight is over."""
        self.t += 1; t = self.t; c = self.core; e = self.e
        c.pad = 0
        c.work_write(self.main['rings'], struct.pack('>H', 50))
        # Tidal Tempest is under water: keep the air count (Level/Main.asm
        # sets drownTimer to 30) full so Sonic never drowns mid-fight.
        c.work_write(self.main['drownTimer'], struct.pack('>H', 30))
        if self.name.startswith('R5'):return self.step_qq(t)
        return self.step_tt(t)

    def step_qq(self, t):
        meca2 = self.actor(52); egg5 = self.actor(50); e = self.e
        if self.stage == 0:
            # Past X 3424 (bossstart) below egg5meca1's layout spot (3536,552).
            self.hold(3432, 640, 0)
            if meca2 and not self.since:self.since = t
            if self.since and t >= self.since+60:self.stage, self.since = 1, t
            if t > 1500:raise RuntimeError(f'{self.name}: egg5meca2 never spawned')
        elif self.stage == 1:
            if meca2 and meca2[e['oColType']] and t % 45 == 0:
                self.hold(*struct.unpack_from('>h', meca2, 8), *struct.unpack_from('>h', meca2, 12), 1)
            elif meca2 and meca2[e['oColType']]:self.hold(3432, 640, 0)
            if meca2 and not meca2[e['oColType']] and meca2[e['oRoutine']] >= 4:
                self.stage, self.since = 2, t; self.hold(3440, 640, 0)
            if t > self.since+6000:raise RuntimeError(f'{self.name}: egg5meca2 hits stalled')
        elif self.stage == 2:
            self.core.pad = 8  # Right (special_retail.Core pad bit 8) on the belt
            self.seen_egg = getattr(self, 'seen_egg', False) or bool(egg5)
            # egg5 escapes once the belt grind runs out; meca2 stays wrecked.
            if self.seen_egg and not egg5:self.stage, self.since = 3, t
            if t > self.since+15000:raise RuntimeError(f'{self.name}: belt grind stalled')
        elif self.stage == 3:
            d = t-self.since
            # The capsule (GOAL.C gene) at 3888,640: land on it rolling.
            if 120 <= d < 400 and d % 40 == 0:self.hold(3888, 600, 1)
            if d > 900:return False
        return True

    def step_tt(self, t):
        e = self.e; sub = self.actor(74); egg4 = self.actor(76)
        if self.stage == 0:
            # Past X 1144 (egg4air_04) beside the submarine's start (1232,852).
            self.hold(1150, 852, 0)
            if sub and not self.since:self.since = t
            if self.since and t >= self.since+60:self.stage, self.since = 1, t
            if t > 1500:raise RuntimeError(f'{self.name}: egg4air never spawned')
        elif self.stage == 1:
            if sub:
                bx, by = struct.unpack_from('>h', sub, 8)[0], struct.unpack_from('>h', sub, 12)[0]
                self.trail.append((bx, by)); fx, fy = self.follow or (1150, 852)
                for qx, qy in reversed(self.trail[-1024:-1]):
                    dx, dy = qx-bx, ((qy-by) % 2048+3072) % 2048-1024
                    if 3600 <= dx*dx+dy*dy < 20000:
                        fx, fy = qx, by+dy+2048 if by+dy < 0 else by+dy; break
                self.follow = (fx, fy)
                if sub[e['oColType']] and t % 45 == 0:self.hold(bx, by-20, 1)
                else:self.hold(fx, fy, 0)
            else:self.stage, self.since = 2, t
            if t > self.since+12000:raise RuntimeError(f'{self.name}: egg4air hits stalled')
        elif self.stage == 2:
            # The sub's exit (2112,1360), then walk into the egg4 arena: a
            # teleport past X 2640 skips the layout load of egg4 (76).
            self.hold(2120, 1370, 0)
            if t > self.since+60:self.stage, self.since = 3, t
        elif self.stage == 3:
            if t < self.since+10:self.hold(2300, 1440, 0)
            elif self.x() < 2660 and not getattr(self, 'hit_egg', False):self.core.pad = 8  # egg4_scrset: X >= 2640
            elif egg4 and egg4[e['oColType']] and t % 40 == 0:
                self.hold(*struct.unpack_from('>h', egg4, 8), *struct.unpack_from('>h', egg4, 12), 1); self.hit_egg = True
            if egg4:self.seen_egg = True
            if getattr(self, 'seen_egg', False) and not egg4:self.stage, self.since = 4, t
            if t > self.since+8000:raise RuntimeError(f'{self.name}: egg4 stalled')
        elif self.stage == 4:
            d = t-self.since
            if d < 200 and d % 40 == 0:self.hold(3632, 1312, 1)
            if d > 500:return False
        return True


def capture(name, trace=False):
    records = saturn_records(name)
    ids = {r['retail_id'] for _, r, _ in records}
    art = sorted({t % 65536 for _, r, _ in records for t in read_tiles(r)})
    core, engine, main, program = boot(name)
    drive = Driver(name, core, engine, main)
    out = OUTDIR/name; out.mkdir(parents=True, exist_ok=True)
    for old in [*out.glob('phase-*/*'), *out.glob('trace-*.png')]:old.unlink()
    phases = []; seen = set(); steady = Counter(); frame = 0; last_ids, last_at = None, 0
    while drive.step():
        core.run(); core.host.chunks.clear(); frame += 1
        live = live_actors(core, engine, ids)
        vram = core.swapped(core.vram, 0, 65536)
        cram = cram_words(core)
        # The palette buffer, not CRAM: Tidal Tempest's H-INT swaps in the
        # water palette below the water line, so CRAM at V-INT is tinted.
        pal = list(struct.unpack('>64H', core.work_read(engine['palette'], 128)))
        if live:steady[tuple(pal)] += 1
        if trace and frame % 600 == 0 and core.frame:sr.png(out/f"trace-{frame:05d}.png", core.frame)
        if trace and frame % 30 == 0:
            p = core.work_read(engine['objPlayerSlot'], 16)
            print(frame, drive.stage, struct.unpack_from('>hxxhxx', p, 8), core.work_read(engine['bossFlags'], 4).hex(), struct.unpack('>hxxhxx', core.work_read(engine['cameraX'], 8)), [(a[0], a[engine['oRoutine']], a[engine['oColType']], a[engine['oColStatus']], a[engine['oMapFrame']]) for _, a in live])
        key = (frozenset(a[0] for _, a in live), hashlib.sha1(b''.join(vram[t:t+32] for t in art)).hexdigest())
        # Only settled VRAM: no PLC queued or decompressing (zone_object_source).
        busy = any(core.work_read(engine['plcBuffer'], 96)+core.work_read(engine['plcTileCount'], 2))
        # A new art state inside the same actor set counts once per 30 frames
        # (the capsule and results animate tiles every frame).
        ids_now = key[0]
        if busy or not live or key in seen or len(phases) >= PHASE_LIMIT:continue
        if phases and ids_now == last_ids and frame < last_at+30:continue
        seen.add(key); last_ids, last_at = ids_now, frame
        regs = C.string_at(core.reg, 24)
        sat_at = (regs[5] & (0x7e if regs[12] & 1 else 0x7f)) << 9
        sat = vram[sat_at:sat_at+640]
        d = out/f'phase-{len(phases):02d}'; d.mkdir(exist_ok=True)
        (d/'vram.bin').write_bytes(vram); (d/'cram.bin').write_bytes(struct.pack('>64H', *cram)); (d/'palette.bin').write_bytes(struct.pack('>64H', *pal))
        (d/'water-palette.bin').write_bytes(core.work_read(engine['waterPalette'], 128)); (d/'sat.bin').write_bytes(sat)
        if core.frame:sr.png(d/'screen.png', core.frame)
        actors = [dict(slot=f'{at:#x}', id=a[0], render=a[1], tile=struct.unpack_from('>H', a, 2)[0],
                       map=struct.unpack_from('>I', a, 4)[0], x=struct.unpack_from('>h', a, 8)[0], y=struct.unpack_from('>h', a, 12)[0],
                       frame=a[engine['oMapFrame']], routine=a[engine['oRoutine']], col_type=a[engine['oColType']],
                       col_status=a[engine['oColStatus']]) for at, a in live]
        phase = dict(index=len(phases), frame=frame, stage=drive.stage, sat_address=f'{sat_at:#x}',
                     camera=struct.unpack('>hxxhxx', core.work_read(engine['cameraX'], 8)),
                     actors=actors, vram_sha256=hashlib.sha256(vram).hexdigest())
        (d/'phase.json').write_text(json.dumps(phase, indent=1)+'\n')
        phases.append(dict(phase, vram=vram, cram=cram, sat=sat))
        print(name, 'phase', phase['index'], 'frame', frame, 'stage', drive.stage, sorted({a['id'] for a in actors}))
    return records, phases, (list(steady.most_common(1)[0][0]) if steady else None), program, frame


def sat_entries(sat):
    """(y, size, link, word, x) for each linked sprite table entry."""
    out = []; i = 0
    for _ in range(80):
        y, size, link, word, x = struct.unpack_from('>HBBHH', sat, i*8)
        out.append((y & 1023, size & 15, link & 127, word, x & 511))
        if not link & 127:break
        i = link & 127
    return out


def pieces(record, pose):
    m = bytes.fromhex(record['frames'][pose])
    return [struct.unpack_from('>bBHb', m, 1+5*i) for i in range(m[0])]


def retail_pieces(program, address, pose):
    at = address-ORIGIN
    at += struct.unpack_from('>H', program, at+2*pose)[0]
    return [struct.unpack_from('>bBHb', program, at+1+5*i) for i in range(program[at] if program[at] <= 128 else 0)]


def pack_rows(name):
    """{kind: rows} of the Saturn zone-art pack for this program's era
    (row layout as tools/check_zone_object_target.py reads it)."""
    pack = (OUT/f'zone-art-{name[1:3]}.bin').read_bytes()
    at = struct.unpack_from('>I', pack, 4+'ABCD'.index(name[3])*4)[0]
    count = struct.unpack_from('>I', pack, at)[0]; rows_at = at+(4 if pack[:4] == b'ZAR2' else 12)
    return Counter(struct.unpack_from('>H', pack, rows_at+48*i)[0] for i in range(count))


def compare(name, records, phases, steady, program):
    rnd, era = name[1], name[3]
    prefix = {'4': 'tt', '5': 'qq'}[rnd]
    stage = (OUT/f'{prefix}{name[1:]}.bin').read_bytes()
    pal_at, _ = struct.unpack_from('>II', stage, 44)
    saturn_pal = list(struct.unpack_from('>64H', stage, pal_at))
    boss = list(struct.unpack('>16H', md_to_rgb555((OUT/f'boss{rnd}{era}.pal').read_bytes())))
    saturn_pal[16:32] = boss
    result = {}; packed = pack_rows(name)
    for folder, rec, svram in records:
        key = f"{folder}:{rec['kind']}(id {rec['retail_id']})"
        same = [(p, a) for p in phases for a in p['actors'] if a['id'] == rec['retail_id']]
        # Other routines of the same actor ID (R5 id 31: the capsule itself
        # besides its flowers) are listed, not compared.
        live = [(p, a) for p, a in same if a['map'] == rec['address']]
        r = result[key] = dict(poses=len(rec['frames']), pack_rows=packed[rec['kind']], live_phases=sorted({p['index'] for p, _ in live}))
        other = sorted({f"{a['map']:#x}/{a['tile']:#x}" for _, a in same if a['map'] != rec['address']})
        if other:r['other_routines_same_id'] = other
        if not live:
            r['status'] = 'not live in any captured phase'; continue
        r['mapping'] = sorted({f"{a['map']:#x}" for _, a in live}); r['tile_words'] = sorted({f"{a['tile']:#x}" for _, a in live})
        r['mapping_ok'] = all(a['map'] == rec['address'] for _, a in live)
        # Effective piece words (palette line and tile index): the Saturn
        # record's tile + its mapping against the live actor's tile + the
        # retail program's mapping for every pose the actor showed.
        def effective(tile, mapping):
            return [((tile+w) & 0x67ff, size) for _, size, w, _ in mapping]
        word_bad = sorted({(p['index'], a['frame']) for p, a in live if a['frame'] < len(rec['frames']) and
                           effective(rec['tile'], pieces(rec, a['frame'])) != effective(a['tile'], retail_pieces(program, a['map'], a['frame']))})
        r['tile_ok'] = not word_bad
        if word_bad:r['word_mismatch'] = [dict(phase=i, pose=f) for i, f in word_bad][:8]
        # Tile bytes per pose: a pose matches if some live phase holds every tile it reads.
        pose_ok = {}; bad = {}
        for pose in range(len(rec['frames'])):
            tiles = sorted(read_tiles(dict(rec, frames=[rec['frames'][pose]])))
            best = None
            for p in {id(p): p for p, _ in live}.values():
                diff = [t for t in tiles if svram[t % 65536:t % 65536+32] != p['vram'][t % 65536:t % 65536+32]]
                if best is None or len(diff) < len(best[1]):best = (p['index'], diff)
            pose_ok[pose] = not best[1]
            if best[1]:bad[pose] = dict(phase=best[0], tiles=[f'{t // 32 % 2048:#x}' for t in best[1]][:12], count=len(best[1]))
        r['poses_matching'] = sum(pose_ok.values()); r['tile_mismatch'] = bad
        # Displayed poses: the retail mapping frame at capture, its tiles in that
        # phase's VRAM and its pieces in the sprite table.
        shown = []
        for p, a in live:
            if a['frame'] >= len(rec['frames']):
                shown.append(dict(phase=p['index'], pose=a['frame'], error='pose outside the Saturn record')); continue
            tiles = read_tiles(dict(rec, frames=[rec['frames'][a['frame']]]))
            diff = [t for t in tiles if svram[t % 65536:t % 65536+32] != p['vram'][t % 65536:t % 65536+32]]
            # Palette line and tile index (flips follow the render flags).
            words = {w for w, _ in effective(a['tile'], retail_pieces(program, a['map'], a['frame']))}
            sat = {w & 0x67ff for _, _, _, w, _ in sat_entries(p['sat'])}
            shown.append(dict(phase=p['index'], pose=a['frame'], tiles_ok=not diff, in_sat=len(words & sat), pieces=len(words)))
        r['shown'] = shown
        r['shown_ok'] = all(s.get('tiles_ok') for s in shown)
        # Palette: every entry the pixels use, Saturn palette vs the retail
        # palette buffer (the most frequent one while boss actors were live,
        # so hit flashes and fades do not count).
        used = set()
        for pose in range(len(rec['frames'])):
            for _, size, w, _ in pieces(rec, pose):
                word = (rec['tile']+w) & 0xffff; line = (word >> 13) & 3; at = (word & 2047)*32
                n = 32*(((size >> 2) & 3)+1)*((size & 3)+1)
                for b in svram[at:at+n]:
                    for v in (b >> 4, b & 15):
                        if v:used.add(line*16+v)
        retail = list(struct.unpack('>64H', md_to_rgb555(struct.pack('>64H', *steady))))
        pal_bad = sorted(i for i in used if (saturn_pal[i] & 0x7fff) != (retail[i] & 0x7fff))
        r['palette_entries'] = len(used); r['palette_mismatch'] = {f'{i // 16}:{i % 16}': [f'{saturn_pal[i] & 0x7fff:#06x}', f'{retail[i] & 0x7fff:#06x}'] for i in pal_bad}
        r['status'] = 'PASS' if r['pack_rows'] and r['mapping_ok'] and r['tile_ok'] and r['shown_ok'] and not pal_bad and r['poses_matching'] == r['poses'] else 'MISMATCH'
    return result


def main():
    trace = '--trace' in sys.argv
    names = [a for a in sys.argv[1:] if not a.startswith('--')] or ['R43C', 'R43D', 'R53C', 'R53D']
    failed = 0
    for name in names:
        records, phases, steady, program, frames = capture(name, trace)
        result = compare(name, records, phases, steady, program)
        report = dict(program=name, frames=frames, phases=[{k: v for k, v in p.items() if k not in ('vram', 'cram', 'sat')} for p in phases],
                      records=result, program_sha256=hashlib.sha256(program).hexdigest(), dependencies=dependencies(),
                      saturn_sources={f: hashlib.sha256(v).hexdigest() for f, _, v in records},
                      tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        (OUTDIR/name/'report.json').write_text(json.dumps(report, indent=1)+'\n')
        for key, r in result.items():
            print(name, key, r['status'], 'poses', f"{r.get('poses_matching', 0)}/{r['poses']}", 'phases', r['live_phases'],
                  'palette_mismatch', len(r.get('palette_mismatch', {})))
            failed += r['status'] == 'MISMATCH'
    print('PASS:' if not failed else 'FAIL:', f'{failed} boss record(s) differ from the retail fight', ' '.join(names))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
