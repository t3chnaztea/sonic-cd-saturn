#!/usr/bin/env python3
"""Capture original zone-object mappings and loaded VRAM from retail.

Boot the selected retail level through the existing IPX entry fixture, then
insert a zero-subtype actor in a free dynamic slot. Its unmodified initializer
chooses the era/act-specific map and tile base. No mapping addresses or art
offsets are guessed from the PC sprite IDs. This is an asset fixture, not a
claim of a gameplay route. Each invocation uses a fresh emulator process.
"""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

import special_retail as sr
from extract_mmd import disc_files, ORIGIN
from retail_span import disc_span
from convert_assets import nemesis

FAMILIES = {3: [(29, 29, 3), (30, 30, 3), (72, 35, 1), (73, 32, 4), (74, 33, 1), (75, 34, 2), (76, 38, 1), (77, 39, 7), (78, 45, 6), (178, 45, 6), (278, 45, 8), (79, 46, 3), (179, 46, 3), (279, 46, 2), (80, 36, 8), (180, 36, 8), (81, 37, 6), (82, 42, 1), (83, 44, 1), (183, 44, 1), (184, 47, 4), (84, 47, 2), (85, 28, 6), (87, 40, 12)], 4: [(67, 52, 7)], 5: [(69, 48, 6)],
            7: [(68, 36, 6)], 8: [(71, 52, 2)]}
ROUNDS = (1, 3, 4, 5, 6, 7, 8)


def dependencies():
    from native import IS_BROWSER, runtime_inputs
    paths=['tools/special_retail.py','tools/retail_capture.py','tools/extract_mmd.py','tools/convert_assets.py',
           'sources.lock.json','.deps/scddisasm/src/Level/_Definitions.inc',
           '.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib','build/retail/IPX___.MMD']
    if IS_BROWSER:
        paths.remove('.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib')
        paths += [str(p.relative_to(sr.ROOT)) for p in runtime_inputs(sr.ROOT)]
    return {p:hashlib.sha256((sr.ROOT/p).read_bytes()).hexdigest() for p in paths}


# Child subtypes the native R4 actors give their views (r4enemies/r4platforms
# view contract): 255 = child with userflag -1, amenbo shots 254 (e set) / 255
# (b set, captured from a placed-style subtype 1 parent), tekkyu 255 = chain.
# sw4 0 = the switch brunko4 (subtype 16) spawns with userflag & 15; kuzure4 0 =
# its falling pieces; tekkyu4 0 = its spawned parts (view subtype from the child's
# userflag at its first run, src/objects_zone_ops.inc).
R4_CHILDREN = {97: (0, 1, 255), 122: (255,), 117: (255, 1), 105: (0, 1), 96: (0, 1), 101: (0, 1), 99: (0,), 107: (0,), 108: (0,)}
# Children whose userflag (their view subtype) differs from the placed parent's,
# by parent subtype (R4/UDBLK4.C type1/6/9_init and type9_move, LRBLK4.C
# type1/8_init; udblk4/lrblk4_act route userflag 0 and 7 to type1).
R4_SPAWNS = {106: {0: (1,), 6: (9,), 9: (10, 11)}, 113: {0: (1,), 7: (1,), 8: (4,)}}
# Poses an era can show, where the rest of the table reads art no section PLC of
# that program loads. ET4.C m_init: patno = 2*!generate_flag + (time_flag==0)
# and only the Past animates, so the Present shows poses 0 and 2 (PLC 4/6).
R4_ERA_POSES = {(127, 'A'): [0, 2]}
# Views that reuse another capture: (type, view subtype) -> (type, captured subtype).
R4_ALIASES = {(105, 254): (105, 0), (105, 255): (105, 1), (94, 128): (94, 0), (94, 129): (94, 1)}
# Children with their own port type and act_tbl routine, captured when their
# parent is placed in the era: switchr4 (swblkr4), ring4 and tensu4 (swgun4).
R4_OWN_CHILDREN = {129: ('switchr4', 115), 130: ('ring4', 111), 131: ('tensu4', 111)}


def r4_specs(name):
    """Tidal Tempest rows, derived rather than typed: every (zone type,
    subtype) the act's translated layout places in this era
    (tools/object_layouts.py), plus the child subtypes of R4_CHILDREN, with the
    retail id this program's own act_tbl gives the routine. Rows are (kind, id,
    None, subtype): kind = type | subtype<<8, so the original initializer picks
    the pattern table the subtype selects; the pose count is read from the
    captured table. friend4 has its own fixture; wall1 keeps its single row."""
    import object_layouts as L
    act, era = int(name[2]), name[3]
    tables = L.act_tables()
    table = tables[L.table_for(tables, 4, act, era)]
    names = L.port_names(4)
    entries, _ = L.all_layouts()[(4, act)]
    placed = {}
    for e in entries:
        if e[5] & L.ERA_BIT[era] and e[2] in names and e[2] != 94:
            placed.setdefault(e[2], set()).add(0 if e[2] == 67 else e[3])
    for kind, subs in R4_CHILDREN.items():
        if kind in placed:placed[kind] |= set(subs)
    for kind, spawns in R4_SPAWNS.items():
        if kind in placed:placed[kind] |= {c for p in placed[kind] for c in spawns.get(p, ())}
    rows = [(kind | sub << 8, table.index(names[kind])+1, R4_ERA_POSES.get((kind, era)), sub) for kind in sorted(placed) for sub in sorted(placed[kind])]
    for kind, (routine, parent) in R4_OWN_CHILDREN.items():
        if parent in placed and routine in table:rows.append((kind, table.index(routine)+1, None, 0))
    # GAME4.C:635 installs the water-surface wave (PLAYSUB4.C) in every program.
    if 'wave' in table:rows.append((133, table.index('wave')+1, None, 0))
    # PLAYSUB4.C plawa (breath bubbles and countdown numbers) draws with AWA.C's
    # table (sproffset 33930) in every program; Act 3 places no awa master.
    if 'awa' in table and 95 not in placed:rows.append((95 | 128 << 8, table.index('awa')+1, None, 128))
    # PLAYSUB4.C exit2, the water entry/exit splash plwaterchk spawns (id 11):
    # exit2pat at sproffset 664, drawn as SCD_OBJ_PLAWA. Acts 1-2 only: R43C
    # with it needs 62,272 B of the 61,440 B VDP1 zone art region.
    if 'exit2' in table and act < 3:rows.append((132, table.index('exit2')+1, None, 0))
    return rows


# Quartz Quadrant (R5): zone-local types 136-154 (src/scd_objects.h). A view
# subtype names the pattern table the original chose (src/objects_qq.inc
# qq_view): 0 for one-table routines; denden/sasori/kumo pick their b table
# for a non-zero subtype (1); their children carry the table their parent
# spawns (R5_CHILDREN, captured by R5Watch). shooter (150) draws nothing and kowasi (154) is
# never placed. friend5 (152) has its own fixture.
R5_TWO_TABLES = {136, 137, 139}
# ET5.C m_init/m_wait as ET4.C: the Present shows poses 0 and 2 only (R4_ERA_POSES).
R5_ERA_POSES = {(153, 'A'): [0, 2]}
R5_NO_ART = {150, 152, 154}
R5_ENEMIES = {136, 137, 138, 139}
# Children with their own pattern table, spawned by the original parents
# during the fixture (R5Watch) and keyed by their subtype bytes (oSubtype =
# userflag.b.h, oSubtype2 = userflag.b.l): denden's spark and kumo's web
# shot (b.h -1), sasori's tail (b.l 1) and shot (b.l -1). Values: view
# subtype and the pose count of that table in the R5 source.
R5_CHILDREN = {136: {(255, None): (255, 1)}, 137: {(None, 1): (254, 2), (None, 255): (253, 2)}, 139: {(255, None): (255, 2)}}


def r5_view_sub(kind, sub):
    return (1 if sub else 0) if kind in R5_TWO_TABLES else 0


def r5_specs(name):
    """Quartz Quadrant rows, derived like r4_specs: every zone type the act's
    translated layout places in this era, once per view subtype, injected
    with a placed raw subtype that selects that table. dair5 keeps its
    FAMILIES row."""
    import object_layouts as L
    act, era = int(name[2]), name[3]
    tables = L.act_tables()
    table = tables[L.table_for(tables, 5, act, era)]
    names = L.port_names(5)
    entries, _ = L.all_layouts()[(5, act)]
    placed = {}
    for e in entries:
        # The Good Future program: SUICIDE.C enemy_suicide removes the four
        # R5 enemies (136-139) on their first update; they never draw.
        if era == 'C' and e[2] in R5_ENEMIES:continue
        if e[5] & L.ERA_BIT[era] and 136 <= e[2] <= 154 and e[2] not in R5_NO_ART:
            view = r5_view_sub(e[2], e[3])
            placed.setdefault((e[2], view), e[3])
            placed[(e[2], view)] = min(placed[(e[2], view)], e[3])
    rows = [row for row in FAMILIES[5] if any(e[5] & L.ERA_BIT[era] and e[2] == row[0] for e in entries)]
    rows += [(kind | view << 8, table.index(names[kind])+1, R5_ERA_POSES.get((kind, era)) if not view else None, raw) for (kind, view), raw in sorted(placed.items())]
    return rows


# Wacky Workbench (R6): zone-local types 136-160 (src/scd_objects.h). BATTA,
# HACHI6, SEMI and MINOMUSI pick pat_*_e for subtype 0 and pat_*_b otherwise;
# FRIEND6 picks pat_friend1 (pecky) when subtype&127. Children with their own
# table: HACHI6 tama, EGG6 bomb and TOGEBALL's orbiting balls (userflag.b.h
# -1, view 255) and SEMI's bomb (userflag.b.l -1, view 254). shooter (156)
# never calls actionsub. The four enemies remove themselves in the Good
# Future (SUICIDE.C enemy_suicide), as in R5.
R6_TWO_TABLES = {142, 143, 144, 145, 157}
R6_ERA_POSES = {(158, 'A'): [0, 2]}  # ET6.C m_init, as ET4/ET5
R6_NO_ART = {155, 156}  # megami and shooter never call actionsub
R6_ENEMIES = {142, 143, 144, 145}
R6_CHILDREN = {143: [(255, 255, 0)], 152: [(255, 255, 0)], 160: [(255, 255, 0)], 144: [(254, 0, 255)]}


def r6_specs(name):
    """Wacky Workbench rows, derived like r5_specs. Rows are (kind, id, poses,
    subtype[, subtype2]) with kind = type|view<<8; the native lookup falls back
    to the plain type for a subtype that shares its table."""
    import object_layouts as L
    act, era = int(name[2]), name[3]
    tables = L.act_tables()
    table = tables[L.table_for(tables, 6, act, era)]
    names = L.port_names(6)
    entries, _ = L.all_layouts()[(6, act)]
    placed = {}
    for e in entries:
        if era == 'C' and e[2] in R6_ENEMIES:continue
        # SUICIDE.C friend_suicide: the Bad Future always removes animals.
        # EGG6.C act_init frames eggz6 out once generate_flag is set.
        if (era == 'D' and e[2] == 157) or (era == 'C' and e[2] == 152):continue
        if e[5] & L.ERA_BIT[era] and 136 <= e[2] <= 160 and e[2] not in R6_NO_ART:
            view = (1 if (e[3]&127 if e[2] == 157 else e[3]) else 0) if e[2] in R6_TWO_TABLES else 0
            # Past/Present animals live only once the projector is gone;
            # subtype bit 7 skips friend_suicide and keeps the same table.
            raw = e[3] | 128 if e[2] == 157 and era != 'C' else e[3]
            placed[(e[2], view)] = min(placed.get((e[2], view), 255), raw)
    rows = [(kind | view << 8, table.index(names[kind])+1, R6_ERA_POSES.get((kind, era)) if not view else None, raw)
            for (kind, view), raw in sorted(placed.items())]
    for kind in sorted({k for k, _ in placed}):
        for view, sub, sub2 in R6_CHILDREN.get(kind, ()):
            rows.append((kind | view << 8, table.index(names[kind])+1, None, sub, sub2))
    return rows


def table_frames(program, address):
    """Every pose of a mapping table: word offsets precede the first
    mapping, so the smallest offset / 2 is the number of entries."""
    offset = address-ORIGIN
    count = struct.unpack_from('>H', program, offset)[0]//2
    i = 1
    while i < count:
        count = min(count, max(1, struct.unpack_from('>H', program, offset+2*i)[0]//2))
        i += 1
    assert 1 <= count <= 64, (hex(address), count)
    frames = []
    for f in range(count):
        pos = offset+struct.unpack_from('>H', program, offset+f*2)[0]
        mapping = program[pos:pos+1+5*program[pos]]
        assert 0 <= mapping[0] <= 32 and len(mapping) == 1+5*mapping[0]
        frames.append(mapping.hex())
    return frames


class R5Watch:
    """Runs the original parents after injection until each R5_CHILDREN table
    they own has appeared: the player (kept invulnerable) stands 40 px left
    of sasori, then of kumo, which is set down on the floor a walker found
    (the fixture point can be over a pit). Up to 900 updates."""
    def __init__(self, families):
        # Keep a B-table parent too: R51D has SASORI only as kind 393, and
        # its tail is still a live child table.
        self.ids = {row[1]: row[0] & 255 for row in families if row[0] & 255 in R5_CHILDREN}
        # A Bad Future may place SASORI's B-table body only (kind 393), so
        # there is no subtype-zero parent from which its optional shot can be
        # induced.  Its tail still appears after the body reaches the floor.
        # Do not wait forever for that impossible shot: the tail is the table
        # this program can actually draw.  Other child tables remain required.
        parent_views = {row[0] for row in families if row[0] & 255 in R5_CHILDREN}
        self.need = {(kind, key) for oid, kind in self.ids.items() for key in R5_CHILDREN[kind]
                     if not (kind == 137 and key == (None, 255) and 137 not in parent_views)}
        self.seen = {}; self.floor = None; self.moved = False
    def find(self, core, engine, kind):
        oid = next((o for o, k in self.ids.items() if k == kind), None)
        for at in range(engine['dynObjects'], engine['objectsEnd'], 64):
            a = core.work_read(at, 64)
            # The R51D SASORI body has subtype 1.  It still creates its tail;
            # accepting the program's selected body table lets R5Watch observe
            # that child instead of requiring a nonexistent subtype-zero body.
            if oid is not None and a[0] == oid and not a[engine['oSubtype']+1]:return at, a
        return None, None
    def __call__(self, core, engine, t):
        for at in range(engine['dynObjects'], engine['objectsEnd'], 64):
            a = core.work_read(at, 64)
            kind = self.ids.get(a[0])
            if kind is None:continue
            for (h, l), view in R5_CHILDREN[kind].items():
                if (h is None or a[engine['oSubtype']] == h) and (l is None or a[engine['oSubtype']+1] == l) and (kind, (h, l)) not in self.seen:
                    self.seen[(kind, (h, l))] = (a[0], a)
        if self.need <= set(self.seen) or t >= 900:return True
        if self.floor is None:
            for kind in (136, 137, 138):
                _, a = self.find(core, engine, kind)
                if a is not None and a[engine['oRoutine']] >= 4:self.floor = struct.unpack_from('>hxxh', a, 8);break
        # Grounding SASORI creates its tail (low subtype 1); only its
        # subtype-zero body can later fire the low-subtype 255 shot.  Capture
        # the tail first so a B-table-only program does not starve it.
        target = 137 if any(kind == 137 and key not in self.seen for kind, key in self.need) else 139
        at, a = self.find(core, engine, target)
        if at is None:return False
        if target == 139 and not self.moved and self.floor:
            a = bytearray(a); struct.pack_into('>II', a, 8, self.floor[0]*65536, (self.floor[1]-24)*65536); a[16:20] = bytes(4)
            core.work_write(at, a); self.moved = True
        x, y = struct.unpack_from('>hxxh', a, 8)
        p = bytearray(core.work_read(engine['objPlayerSlot'], 64)); p[0x30:0x32] = struct.pack('>H', 120)
        struct.pack_into('>II', p, 8, (x-40)*65536, (self.floor[1] if target == 139 and self.floor else y)*65536); p[16:22] = bytes(6)
        core.work_write(engine['objPlayerSlot'], p)
        return False
    def records(self, program):
        out = []
        for (kind, key), (oid, a) in sorted(self.seen.items(), key=lambda s: R5_CHILDREN[s[0][0]][s[0][1]][0]):
            view, poses = R5_CHILDREN[kind][key]
            tile, address = struct.unpack_from('>HI', a, 2)
            frames = table_frames(program, address)
            assert len(frames) == poses, (kind, view, len(frames), poses)
            out.append(dict(kind=kind | view << 8, retail_id=oid, tile=tile, address=address, actor=a.hex(), frames=frames))
        missing = sorted(R5_CHILDREN[k][key][0] | k << 8 for k, key in self.need - set(self.seen))
        return out, missing


def specs(name):
    rnd, act = int(name[1]), int(name[2])
    if rnd == 4:
        return r4_specs(name)
    if rnd == 5:
        return r5_specs(name)
    if rnd == 6:
        return r6_specs(name)
    if rnd == 7:
        return r7_specs(name)
    rows = list(FAMILIES.get(rnd, []))
    if rnd == 8:
        rows += r8_specs(name)
    if rnd == 3:
        # No getdair3/gandair3 placements or children in Act 2; Act 3 only
        # uses bumpers, flippers and harir3. Unused families may share their
        # tile addresses with entirely different art in those programs.
        allowed = {29,30,73} if act == 3 else {29,30,72,73,74,75,78,178,278,79,179,279,80,180,81,82,83,183,84,184,85,87} if act == 2 else {r[0] for r in rows}-{87}
        rows = [row for row in rows if row[0] in allowed]
    if rnd == 7 and act == 3:
        rows.append((168, 43, 6))  # wall73: same port type, subtype bit 7
    if rnd == 8 and act == 1:
        rows.append((70, 42, 7))
    if rnd == 8 and act == 3:
        rows.append((29, 29, 3))  # bobin: R83C/D place bumpers (userflag 67/192/195)
    return rows


def r7_specs(name):
    """R7 ACT/layout-derived actor families; keep WALL7's global kind 68.

    Native view variants match the original table selectors, not movement
    subtypes. Parent-spawned families are included when their parent exists.
    """
    import object_layouts as L
    act, era = int(name[2]), name[3]
    tables = L.act_tables()
    table = tables[L.table_for(tables, 7, act, era)]
    names = L.port_names(7)
    entries, _ = L.all_layouts()[(7, act)]
    placed = {}
    for e in entries:
        kind, sub, sub2 = e[2:5]
        if not e[5] & L.ERA_BIT[era] or not (kind == 68 or 136 <= kind <= 156):continue
        if era == 'C' and kind in (149, 150, 151, 152):continue
        if era == 'D' and kind == 154:continue
        view = (sub & 1 if kind == 149 else int(bool(sub)) if kind in (151,152)
                else int(bool(sub & 127)) if kind == 154 else 0)
        if kind == 154:continue  # separate fixture captures init before parent-linked animation
        placed.setdefault((kind, view), (sub, sub2))
    rows = [(kind | view << 8, table.index(names[kind])+1,
             [0, 2] if kind == 155 and era == 'A' else None, *raw)
            for (kind, view), raw in sorted(placed.items())]
    if (142, 0) in placed:
        # CHGBAN.C spr_r_set uses these shared SPRING.C tables unchanged.
        rows += [(142 | view << 8, table.index('spring')+1, 3, raw, 0)
                 for view, raw in ((1,4),(2,0),(3,8))]
    if (143, 0) in placed:rows.append((144, table.index('hibana')+1, None, 0, 0))
    if any(k == 149 for k, _ in placed):rows.append((149 | 254 << 8, table.index('hotaru7')+1, 3, 0, 254))
    if (136, 0) in placed:rows.append((137, table.index('heart7')+1, None, 0, 0))
    if (147, 0) in placed:rows.append((147 | 255 << 8, table.index('tekkyu7j')+1, None, 0, 255))
    return rows


# src/objects_mm.inc mm_view_table: the R8 pattern table the original picks
# from the userflag bytes (b.h, b.l). Keep both in step.
def r8_view(kind, h, l):
    return {157: 2 if h == 248 else 1 if h >= 128 else 0, 159: int(l == 255), 161: int(h != 0),
            165: int(l >= 128), 164: int(h == 2), 167: int(h != 0), 168: int(bool(h & 127)),
            176: h if h <= 2 else 0, 177: int(h != 0), 174: h//2,
            188: (1 if h & 2 else 0) | (2 if h & 4 else 4 if h & 8 else 0)}.get(kind, 0)


# Parent-spawned R8 tables: (kind, view) of the parent -> rows (view, b.h, b.l)
# of the child. None takes the parent's byte. Rows marked 'child' are captured
# from the actor the injected parent spawned (it checks its parent's slot).
R8_CHILDREN = {(159, 0): [(1, None, 255)], (161, 0): [(1, 1, 0)], (165, 0): [(1, None, 255)]}


def r8_specs(name):
    """R8 ACT/layout-derived actor families (zone-local kinds 157-188): one
    row per placed (kind, view) with its smallest placed userflag bytes, the
    original initializer picking the table (r8_view), plus parent-spawned
    tables (R8_CHILDREN). Pose counts come from the captured table. The global
    konbea (70) and piston (71) keep their FAMILIES rows."""
    import object_layouts as L
    act, era = int(name[2]), name[3]
    tables = L.act_tables()
    table = tables[L.table_for(tables, 8, act, era)]
    names = L.port_names(8)
    entries, _ = L.all_layouts()[(8, act)]
    placed = {}
    for e in entries:
        kind, sub, sub2 = e[2], e[3], e[6] if len(e) == 7 else 0  # e[4] is the flags byte
        if not e[5] & L.ERA_BIT[era] or not 157 <= kind <= 188:continue
        key = (kind, r8_view(kind, sub, sub2))
        placed[key] = min(placed.get(key, (sub, sub2)), (sub, sub2))
    # Placed scarab (userflag >= 3) and bigbom (0) are invisible controllers:
    # SCARAB.C enemy() draws userflag 0/1, BIGBOM8.C bigbom1-4 userflag 2-8.
    rows = [(kind | view << 8, table.index(names[kind])+1, None, *raw) for (kind, view), raw in sorted(placed.items()) if kind not in (164, 174)]
    if (164, 0) in placed:
        # SCARAB.C: the placed controller (userflag >= 3, invisible; row kind
        # 164|7<<8) waits for Sonic within 640 px, then c_make spawns the enemy
        # (userflag.b.h & 1, b.l -1 with bit 4) and, for b.l bit 7 or > 7, the
        # item (userflag 2). Both check the controller's slot, so both are taken
        # from the controller's own spawns.
        h, l = min((e[3], e[6]) for e in entries if e[2] == 164 and e[5] & L.ERA_BIT[era] and len(e) == 7 and (e[6] & 128 or e[6] > 7)) \
            if any(e[2] == 164 and e[5] & L.ERA_BIT[era] and len(e) == 7 and (e[6] & 128 or e[6] > 7) for e in entries) else placed[(164, 0)]
        rows.append((164 | 7 << 8, table.index(names[164])+1, None, h, l))
        rows.append((164, table.index(names[164])+1, None, h & 1, 255 if h & 16 else 0, 'child'))
        # The item draws ITEM.C's itempat (20 poses) through itemchg[userflag.b.l],
        # and only b.l bit 7 or > 7 spawns it. R81 places b.l 1 and 10: retail
        # runs pose 0 only for 10 (objects_mm_remaining.inc mm_sc_itemchg10).
        if l & 128 or l > 7:
            assert {e[6] for e in entries if e[2] == 164 and len(e) == 7 and (e[6] & 128 or e[6] > 7)} == {10}, 'scarab item scripts'
            rows.append((164 | 1 << 8, table.index(names[164])+1, [0], 2, l, 'child'))
    if (174, 0) in placed:
        # The controller (m_move0) spawns bigbom1 (userflag 2) at once; inject it too.
        rows += [(174, table.index(names[174])+1, None, *placed[(174, 0)])]
        rows += [(174 | v << 8, table.index(names[174])+1, None, 2*v, placed[(174, 0)][1], 'child') for v in (1, 2, 3, 4)]
    # KOMA8.C and TRAP_R8x.C togedair8 carry SPRING.C springs (retail actor 10,
    # native SCD_OBJ_R8_SPRING8): koma8's userflag & 15; togedair8's own when
    # it is neither 1 nor negative (src/objects_mm_trap.inc mm_spring_child).
    springs = {e[3] & 15 for e in entries if e[2] == 162 and e[5] & L.ERA_BIT[era]}
    springs |= {e[3] for e in entries if e[2] == 157 and e[5] & L.ERA_BIT[era] and e[3] != 1 and e[3] < 128}
    for h in sorted(springs):
        view = r8_view(188, h, 0)
        if not any(r[0] == 188 | view << 8 for r in rows):
            rows.append((188 | view << 8, table.index('spring')+1, None, h, 0))
    # HOTA8C/D.C's room (hotaru8 userflag -2) opens a TOBIRA it spawns with userflag 0.
    if any(k == 183 for k, _ in placed) and not any(r[0] == 176 for r in rows):
        rows.append((176, table.index(names[176])+1, None, 0, 0))
    for (kind, view), raw in sorted(placed.items()):
        for child, h, l in R8_CHILDREN.get((kind, view), ()):
            rows.append((kind | child << 8, table.index(names[kind])+1, None,
                         raw[0] if h is None else h, raw[1] if l is None else l, 'child'))
    return rows


def plc_banks(program):
    """Every (plc index, art address, VRAM destination, art) of a program's PLC
    table, located through the engine's own LoadPLC instructions."""
    tables = {struct.unpack('>I', m[1])[0] for m in re.finditer(
        rb'\x43\xf9(....)\xd0\x40\x30\x31\x00\x00\x43\xf1\x00\x00', program, re.S)}
    assert len(tables) == 1, ('PLC table', tables)
    table = tables.pop()-ORIGIN
    banks = []
    for index in range(struct.unpack_from('>H', program, table)[0]//2):
        offset = table+struct.unpack_from('>H', program, table+2*index)[0]
        for entry in range(struct.unpack_from('>h', program, offset)[0]+1):
            address, dest = struct.unpack_from('>IH', program, offset+2+6*entry)
            banks.append((index, address, dest, nemesis(program[address-ORIGIN:])))
    return banks


def mapping_span(record):
    """VRAM byte range [lo, hi) the record's mappings read."""
    base = (record['tile']&2047)*32; lo, hi = 1<<20, 0
    for encoded in record['frames']:
        mapping = bytes.fromhex(encoded)
        for piece in range(mapping[0]):
            _, size, word, _ = struct.unpack_from('>bBHb', mapping, 1+piece*5)
            at = base+(word&2047)*32
            lo = min(lo, at); hi = max(hi, at+32*(((size>>2)&3)+1)*((size&3)+1))
    return lo, hi


def verify_tiles(program, record, vram, banks=None):
    """Every 8x8 tile each mapping piece reads lies in some original PLC bank
    whose art VRAM holds at its destination. A family can read several banks
    (R4 harid4, daid4). Returns the sorted (plc, destination) pairs used."""
    banks = [(i, dest, dest+len(art)) for i, _, dest, art in (banks or plc_banks(program)) if vram[dest:dest+len(art)] == art]
    base = (record['tile']&2047)*32; used = set()
    for encoded in record['frames']:
        mapping = bytes.fromhex(encoded)
        for piece in range(mapping[0]):
            _, size, word, _ = struct.unpack_from('>bBHb', mapping, 1+piece*5)
            at = base+(word&2047)*32
            for tile in range(at, at+32*(((size>>2)&3)+1)*((size&3)+1), 32):
                hit = next(((i, dest) for i, dest, end in banks if dest <= tile%65536 and tile%65536+32 <= end), None)
                assert hit, ('tile outside every resident PLC bank', record['kind'], hex(tile))
                used.add(hit)
    return sorted(used)


def verify_tile_bytes(program, record, vram, banks=None):
    """R5: every 8x8 tile each mapping piece reads holds, in VRAM, the bytes
    some original PLC bank writes at that address. A bank may be partly
    overwritten by a later section list (R52B: sasori's tail and shot read the
    rest of PLC 1 past the body bank of PLC 2). Returns the (plc, destination)
    pairs used."""
    banks = banks or plc_banks(program); used = set()
    for tile in sorted(read_tiles(record)):
        t = tile%65536
        hit = next(((i, dest) for i, _, dest, art in banks if dest <= t and t+32 <= dest+len(art) and art[t-dest:t-dest+32] == vram[t:t+32]), None)
        assert hit, ('tile holds no original PLC bytes', record['kind'], hex(tile))
        used.add(hit)
    return sorted(used)


# R8 families whose own section PLC starts at their tile base but overlaps an
# earlier bank there: the opening VRAM holds the other bank's bytes, which
# verify_tile_bytes accepts. HACHI8.C's bee (tile $455) is PLC 6/8/12/14 at
# $8AA0, where R81A/B/D's opening VRAM holds PLC 2 (retail MM1A/B: a yellow
# bee on a black chain; the opening bytes drew it blue/grey).
R8_OWN_BANK = (167,)
# (program, kind): the same rule for one program. R82A's ET8 (169, tile $2FE):
# the fixture VRAM holds PLC 2's $6000 bank over $6000-$6180, where retail draws
# PLC 4/8's own $5FC0 bank (tools/check_mm2a_et8_vram.py: MM2A retail VRAM with
# the generator on screen equals the overlay on all 23 tiles).
R8_OWN_BANK_AT = {('R82A', 169)}


def own_bank(program, record):
    """The one non end-of-act PLC bank that starts at the record's tile base."""
    base = (record['tile']&2047)*32
    own = {art for i, _, dest, art in plc_banks(program) if dest == base and i not in END_OF_ACT_PLCS}
    return (base, next(iter(own))) if len(own) == 1 else None


# PLCLists slots that replace object art at the end of an act (scddisasm
# Level/Palmtree Panic/Data (Act 1 Past).asm: 16 PLC_Results, 18 PLC_Signpost).
END_OF_ACT_PLCS = (16, 18)


def read_tiles(record):
    """VRAM byte addresses of every 8x8 tile the record's mappings read."""
    base = (record['tile']&2047)*32; tiles = set()
    for encoded in record['frames']:
        mapping = bytes.fromhex(encoded)
        for piece in range(mapping[0]):
            _, size, word, _ = struct.unpack_from('>bBHb', mapping, 1+piece*5)
            at = base+(word&2047)*32
            tiles.update(range(at, at+32*(((size>>2)&3)+1)*((size&3)+1), 32))
    return tiles


def plc_overlay(program, record, vram, anchor=None):
    """A VRAM copy with each tile this record reads taken from the original
    PLC banks that hold it (section/camera lists; never the results or
    signpost lists). None when a tile has no such bank or the banks disagree.
    Returns (vram, {tile address: [plc, ...]})."""
    base = (record['tile']&2047)*32
    banks = [(i, dest, art) for i, _, dest, art in plc_banks(program) if i not in END_OF_ACT_PLCS]
    out = bytearray(vram); used = {}
    tiles = set()
    for encoded in record['frames']:
        mapping = bytes.fromhex(encoded)
        for piece in range(mapping[0]):
            _, size, word, _ = struct.unpack_from('>bBHb', mapping, 1+piece*5)
            at = base+(word&2047)*32
            tiles.update(range(at, at+32*(((size>>2)&3)+1)*((size&3)+1), 32))
    # Prefer the one section list whose bank holds every pose (R4 Past et4:
    # PLC 5/8 loads the generator where other lists load the animals).
    whole = {(dest, art) for _, dest, art in banks if tiles and all(dest <= t and t+32 <= dest+len(art) for t in tiles)}
    # R5 children read further into their parent's bank: keep only the banks
    # that also hold the parent's resident tiles as VRAM has them (R52B
    # sasori shot: PLC 4/6 extend the body bank, PLC 1 is other art there).
    if anchor:
        whole = {(dest, art) for dest, art in whole if all(dest <= a and a+32 <= dest+len(art) and art[a-dest:a-dest+32] == vram[a:a+32] for a in anchor)}
    if len({art for _, art in whole}) == 1:
        dest, art = next(iter(whole))
        out[dest:dest+len(art)] = art
        return bytes(out), {'bank': hex(dest), 'plcs': sorted(i for i, d, a in banks if (d, a) == (dest, art))}
    for encoded in record['frames']:
        mapping = bytes.fromhex(encoded)
        for piece in range(mapping[0]):
            _, size, word, _ = struct.unpack_from('>bBHb', mapping, 1+piece*5)
            at = base+(word&2047)*32
            for tile in range(at, at+32*(((size>>2)&3)+1)*((size&3)+1), 32):
                cover = [(i, art[tile-dest:tile-dest+32]) for i, dest, art in banks if dest <= tile and tile+32 <= dest+len(art)]
                if not cover or len({data for _, data in cover}) != 1:return None
                out[tile:tile+32] = cover[0][1]; used[tile] = sorted({i for i, _ in cover})
    return bytes(out), {hex(t): used[t] for t in sorted(used)}


def verify_cc_banks(program, records, vram):
    """Check every CPU-loaded CC object bank against original PLC entries.

    Present starts with the shared 16-tile spike bank. CC's own mappings need
    the 32-tile bank loaded by Section Art Load.asm after leaving that section.
    Locate the PLC table through the engine's actual LoadPLC instructions;
    neither a PC sprite number nor a guessed compressed-art address is used.
    """
    tables = {struct.unpack('>I', m[1])[0] for m in re.finditer(
        rb'\x43\xf9(....)\xd0\x40\x30\x31\x00\x00\x43\xf1\x00\x00', program, re.S)}
    assert len(tables) == 1, ('PLC table', tables)
    table = tables.pop()-ORIGIN
    table_size = struct.unpack_from('>H', program, table)[0]
    assert table_size % 2 == 0 and 2 <= table_size <= 64
    banks = []
    for index in range(table_size//2):
        offset = table+struct.unpack_from('>H', program, table+2*index)[0]
        count = struct.unpack_from('>h', program, offset)[0]+1
        assert 0 <= count <= 64
        for entry in range(count):
            address, dest = struct.unpack_from('>IH', program, offset+2+6*entry)
            assert ORIGIN <= address < ORIGIN+len(program)
            art = nemesis(program[address-ORIGIN:])
            banks.append((index,address,dest,art))
    verified = {}
    for record in records:
        destination = (record['tile']&2047)*32
        needed = 0
        for encoded in record['frames']:
            mapping = bytes.fromhex(encoded)
            for piece in range(mapping[0]):
                _,size,word,_ = struct.unpack_from('>bBHb',mapping,1+piece*5)
                needed = max(needed,32*((word&2047)+(((size>>2)&3)+1)*((size&3)+1)))
        matches = [dict(plc=index,address=address,destination=dest,mapping_offset=destination-dest,size=len(art),sha256=hashlib.sha256(art).hexdigest())
                   for index,address,dest,art in banks if dest<=destination and destination+needed<=dest+len(art)
                   and vram[dest:dest+len(art)]==art]
        assert matches, ('CC object mapping lacks its full original PLC bank',record['kind'],hex(destination),needed)
        verified[record['kind']] = matches
    return verified


def capture(name, out, objects=None, camera_x=None, player_y=400, keep_good_future=False, projector_destroyed=False, watch=None, actor_y_offset=0):
    # Act 2's drum tiles are supplied by a later section PLC. At X=6400 the
    # complete drum bank and every earlier CC2 family coexist in original VRAM.
    if camera_x is None:camera_x=6400 if name.startswith('R32') else 2048
    families=specs(name) if objects is None else objects
    if watch is None and objects is None and name.startswith('R5'):watch = R5Watch(families)
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
                    [('lives', 3), ('timeZone', {'A': 1, 'B': 0, 'C': 2, 'D': 2}[era]),
                     ('goodFuture', int(era == 'C'))]+([('projDestroyed', 1)] if projector_destroyed else []))
    stub += struct.pack('>HHI', 0x33fc, zone << 8 | act, main['zoneAct'])
    stub += struct.pack('>HII', 0x23fc, 5000, main['nextLifeScore'])
    stub += struct.pack('>HHHIH', 0x303c, commands['SCMD_'+name], 0x4eb9, run, 0x60fe)
    assert len(stub) <= 64
    patches = [(bram, code[bram-origin:bram-origin+8], struct.pack('>HIH', 0x4ef9, stub_at, 0x4e71)),
               (stub_at, code[stub_at-origin:stub_at-origin+len(stub)], stub)]
    core = sr.Core(); patched = seen = False; release = 0; injected = []
    queue_ready = 0; injected_release = None; snaps = None
    for frame in range(10000):
        core.pad = 0; core.run(); core.host.chunks.clear()
        if not patched and all(core.work_read(at, len(old)) == old for at, old, _ in patches):
            for at, _, new in patches: core.work_write(at, new)
            patched = True
        if not patched or core.work_read(0xfffd08, 4) != struct.pack('>I', vint): continue
        card = core.work_read(engine['objTtlCardSlot'], 64)
        if card[0] == 0x3c: seen = True
        if seen and not core.work_read(engine['ctrlLocked'], 1)[0] and not card[0]: release += 1
        # Let the original section-art loader select the main CC1 bank. The
        # opening Present section uses common spikes with different mappings.
        # Hold an explicit camera/player fixture while its queued PLCs finish.
        cc = name.startswith('R3')
        # R4 objects (ET4 among them) queue their own PLCs at init as well.
        waitq = cc or name.startswith(('R4', 'R5', 'R6', 'R7', 'R8'))
        cc_main = cc and act < 2
        if cc_main and release >= 30:
            core.work_write(engine['cameraX'], struct.pack('>I', camera_x*65536))
            player = bytearray(core.work_read(engine['objPlayerSlot'], 64))
            struct.pack_into('>II', player, 8, (camera_x+160)*65536, player_y*65536)
            player[16:22] = bytes(6)
            player[engine['oFlags']] = 2
            player[engine['oRoutine']] = 2
            player[0x2c] = 0
            player[0x30:0x32] = struct.pack('>H', 120)
            core.work_write(engine['objPlayerSlot'], player)
        queue_empty = not any(core.work_read(engine['plcBuffer'],96)+core.work_read(engine['plcTileCount'],2))
        queue_ready = queue_ready+1 if queue_empty else 0
        # The art fixture includes enemies even in Good Future. Disable only
        # their destruction flag after the actual era's banks are loaded.
        if cc_main and release >= 64 and not keep_good_future:
            core.work_write(main['goodFuture'], b'\0'+core.work_read(main['goodFuture']+1,1))
        if not injected and release >= (64 if cc_main else 30) and (not waitq or queue_ready >= 2 or (not cc and release >= 300)):
            x = struct.unpack('>h', core.work_read(engine['cameraX'], 2))[0]+224
            y = struct.unpack('>h', core.work_read(engine['cameraY'], 2))[0]+112
            free = [at for at in range(engine['dynObjects'], engine['objectsEnd'], 64)
                    if not core.work_read(at, 1)[0]]
            # Chains allocate only after their parent. Leave the remaining free
            # slots after the injected group for their original initializers.
            selected = free[:len(families)] if cc or name.startswith(('R4', 'R5', 'R6', 'R7', 'R8')) else free[-len(families):]
            assert len(free) >= len(families)+(16 if cc_main else 0), (name,'free actor slots')
            for row, at in zip(families, selected):
                kind, oid, count = row[:3]
                actor = bytearray(64); actor[0] = oid
                actor[engine['oSubtype']] = row[3] if len(row) > 3 else (128+(kind==189) if kind in (89,189) and era!='C' else
                    255 if kind in (178,179,180,183,184) else 128 if kind == 85 else
                    254 if kind == 293 else 1 if kind in (278,279,189,193) else 0)
                if len(row) > 4:actor[engine['oSubtype']+1] = row[4]
                # EGG6.C bomb_fall dies at its floor word (retail $2e; PC word 25).
                # Held 80 px above the fixture row, clear of the player's touch.
                bomb = kind == 152 | 255 << 8 and name.startswith('R6')
                if bomb:struct.pack_into('>h', actor, 0x2e, y+512)
                struct.pack_into('>H', actor, 8, x); struct.pack_into('>H', actor, 12, (y-80 if bomb else y)+actor_y_offset)
                if cc and kind == 81:
                    # Original blade wait loads its parent's signed low-word
                    # address from $30, then checks parent actor ID $24.
                    assert disc_span('R31A__.MMD',0xd304,12,'4dcab9d9242d2de6f8f8dfd4495ac46e176094bf334e5da528ee9441e8b19108') in program
                    parent = next(p for k,_,_,p in injected if k == 80)
                    struct.pack_into('>H', actor, 0x30, parent & 65535)
                    struct.pack_into('>H', actor, 0x2c, 64)
                if cc and kind == 183:
                    # Original TOGEBALL child follows its parent's signed
                    # low-word pointer at $3e, independent of its orbit data.
                    assert disc_span('R31A__.MMD',0xbea0,14,'d315972fea80198f4c4ba1473081d8f4f9b1aabdb283be4530963df2bed28637') in program
                    parent = next(p for k,_,_,p in injected if k == 83)
                    struct.pack_into('>H', actor, 0x3e, parent & 65535)
                if cc and kind == 84:
                    # Pocket lid uses its parent's signed low-word address.
                    assert disc_span('R31A__.MMD',0xb8e8,14,'ce6ed1a583d62a55fc6254123838cb20e2168e2d370e3c1fab4a2f7524a266ef') in program
                    parent = next(p for k,_,_,p in injected if k == 184)
                    struct.pack_into('>H', actor, 0x2e, parent & 65535)
                if cc and kind in (93,193):
                    # SIKAKE33 light/stopper: movea.w $36(a0),a1 then
                    # cmpi.b #$36,(a1); without a kaitenban parent they
                    # delete themselves before their mapping can be read.
                    assert disc_span('R33C__.MMD',0xa674,10,'e8c3a61dc82bde23956da3e91c45e4d40d6984dc97e009375253fe828d556f1f') in program
                    parent = next(p for k,_,_,p in injected if k == 293)
                    struct.pack_into('>H', actor, 0x36, parent & 65535)
                core.work_write(at, actor); injected.append((kind, oid, count, at))
            injected_release = release
        capture_delay=1 if families and all(row[0] in (89,189,94,350,152,408,664,154,410) for row in families) else 2
        if injected_release is not None and release >= injected_release+capture_delay and (not waitq or queue_ready >= 2 or (not cc and release >= 300)):
            # The R3 projector deliberately queues its own art at init. Wait
            # for that PLC as well as the stage PLC before reading its tiles.
            assert len(injected) == len(families)
            # The injected actors are read at the capture delay; a watch
            # (children spawned later by the original parents) may keep the
            # fixture running before VRAM is read.
            if snaps is None:snaps = {i[3]: core.work_read(i[3], 64) for i in injected}
            if watch is not None and not watch(core, engine, release-injected_release):continue
            records = []; missing = []
            for row, at in zip(families, [i[3] for i in injected]):
                kind, oid, count = row[:3]
                actor = snaps[at]
                tile, address = struct.unpack_from('>HI', actor, 2)
                if name.startswith('R7') and kind in (149,405) and not address:
                    # HOTARU7's invisible controller spawns the b_init fireflies.
                    for slot in range(engine['dynObjects'], engine['objectsEnd'], 64):
                        other = core.work_read(slot, 64)
                        if other[0] == oid and bool(other[engine['oSubtype']]) == bool(kind >> 8) and other[engine['oSubtype']+1] == 255:
                            t, a = struct.unpack_from('>HI', other, 2)
                            if ORIGIN <= a < ORIGIN+len(program):
                                actor, tile, address = other, t, a
                                break
                if name.startswith('R7') and kind in (149,405) and not address:
                    # Confirmed retail b_init: subtype test selects the e/b
                    # PC-relative mapping, then stores A1 into oMap. The
                    # controller may not spawn its visible children until near Sonic.
                    hits = list(re.finditer(rb'\x4a\x28\x00\x28\x66.\x43\xfa(..)\x45\xfa..\x20\x3c\xff\xff\x00\x00\x60.\x43\xfa(..)\x45\xfa..\x20\x3c\xff\xff\x80\x00', program, re.S))
                    assert len(hits) == 1, (name, 'hotaru7 b_init selectors', len(hits))
                    hit=hits[0];group=2 if kind>>8 else 1
                    address=ORIGIN+hit.start(group)+struct.unpack('>h',hit[group])[0]
                    count=5
                    actor=bytes([oid])+actor[1:2]+struct.pack('>HI',tile,address)+actor[8:]
                if name.startswith('R7') and kind == 149 | 254 << 8:
                    # HOTARU7.C c_init: priority 2, 12px radii, collision 180,
                    # then pat_tama. b_make_c inherits the firefly tile base.
                    hits = re.findall(rb'\x11\x7c\x00\xb4\x00\x20\x21\x7c(....)\x00\x04', program, re.S)
                    assert len(hits) == 1, (name, 'hotaru7 c_init mapping', hits)
                    parent = next(snaps[i[3]] for i in injected if i[0] in (149,405))
                    tile, address = struct.unpack_from('>H',parent,2)[0], struct.unpack('>I', hits[0])[0]
                    actor = bytes([oid])+actor[1:2]+struct.pack('>HI',tile,address)+actor[8:]
                if name.startswith('R8') and kind == 164 | 1 << 8 and not (actor[0] == oid and ORIGIN <= address < ORIGIN+len(program)):
                    # SCARAB.C iteminit (userflag 2) frames out unless it is on screen
                    # at its first update. Read its exact stores: sprvsize 14, sprhs 14,
                    # patbase itempat, sproffset 1448, actflg 4, sprpri 2.
                    hits = re.findall(rb'\x11\x7c\x00\x0e\x00\x16\x11\x7c\x00\x0e\x00\x17\x21\x7c(....)\x00\x04\x31\x7c\x05\xa8\x00\x02\x11\x7c\x00\x04\x00\x01\x11\x7c\x00\x02\x00\x18', program, re.S)
                    assert len(hits) == 1, (name, 'scarab iteminit', hits)
                    tile, address = 1448, struct.unpack('>I', hits[0])[0]
                    actor = bytes([oid])+actor[1:2]+struct.pack('>HI',tile,address)+actor[8:]
                if name.startswith('R73') and kind == 138:
                    # HARI73.C init frames out unless Metal Sonic is behind it.
                    # Read its exact tile+mapping stores before that prerequisite.
                    hits = re.findall(rb'\x31\x7c\x04\xfc\x00\x02\x21\x7c(....)\x00\x04', program, re.S)
                    assert len(hits) == 1, (name, 'hari73 init mapping', hits)
                    tile, address, count = 1276, struct.unpack('>I',hits[0])[0], 2
                    actor = bytes([oid])+actor[1:2]+struct.pack('>HI',tile,address)+actor[8:]
                if name == 'R73D' and kind == 136 and not actor[0]:
                    # EMIE7.C relocates Amy to the far goal in Bad Future and
                    # immediately culls the fixture. HEART7 uses the same table.
                    heart = next(snaps[i[3]] for i in injected if i[0] == 137)
                    address = struct.unpack_from('>I',heart,4)[0];tile=41931
                    assert ORIGIN <= address < ORIGIN+len(program)
                    actor = bytes([oid])+actor[1:2]+struct.pack('>HI',tile,address)+actor[8:]
                if kind&255 == 126 and actor[0] != oid:
                    # UKIDAI.C a_init frames itself out unless the water script
                    # stands at 1920 or 1504, which GAME4.C rewrites each frame
                    # from the player's X. Its sproffset and patbase are
                    # immediates of that same a_init (move.w #$350,2(a0);
                    # move.l #pat_ukidai,4(a0)), read from the program.
                    hits = re.findall(rb'\x31\x7c(..)\x00\x02\x21\x7c(....)\x00\x04\x31\x68\x00\x08\x00\x36\x0c\x78\x07\x80', program, re.S)
                    assert len(hits) == 1, (name, 'ukidai a_init', hits)
                    tile, address = struct.unpack('>H', hits[0][0])[0], struct.unpack('>I', hits[0][1])[0]
                    actor = bytes([oid])+actor[1:2]+struct.pack('>HI', tile, address)+actor[8:]
                if count is None and len(row) > 3 and (255 in row[3:5] or row[5:6] == ('child',)) and not (actor[0] == oid and ORIGIN <= address < ORIGIN+len(program)):
                    # A child (userflag -1) checks its parent's slot and actno and
                    # frames itself out alone. Take one the injected parent spawned.
                    for slot in range(engine['dynObjects'], engine['objectsEnd'], 64):
                        other = core.work_read(slot, 64)
                        if other[0] == oid and other[engine['oSubtype']:engine['oSubtype']+len(row[3:5])] == bytes(row[3:5]) and other is not actor:
                            t, a = struct.unpack_from('>HI', other, 2)
                            if ORIGIN <= a < ORIGIN+len(program):
                                actor, tile, address = other, t, a
                                break
                if kind == 143 | 255 << 8 and name.startswith('R6') and not (actor[0] == oid and ORIGIN <= address < ORIGIN+len(program)):
                    # HACHI6.C act_shot2 fires tama only near the player. Its
                    # table is that spawn's immediate (move.b #-1,$28(a1);
                    # move.b 1(a0),1(a1); move.w 2(a0),2(a1); move.l #pat_tama,
                    # 4(a1)); its tile is the parent's sproffset.
                    hits = re.findall(rb'\x13\x7c\x00\xff\x00\x28\x13\x68\x00\x01\x00\x01\x33\x68\x00\x02\x00\x02\x23\x7c(....)\x00\x04', program, re.S)
                    parent = next(snaps[i[3]] for i in injected if i[0] & 255 == 143 and i[0] >> 8 in (0, 1))
                    assert len(hits) == 1 and parent[0] == oid, (name, 'hachi6 tama spawn', hits)
                    tile, address = struct.unpack_from('>H', parent, 2)[0], struct.unpack('>I', hits[0])[0]
                    actor = bytes([oid])+actor[1:2]+struct.pack('>HI', tile, address)+actor[8:]
                if count is None and not (actor[0] == oid and ORIGIN <= address < ORIGIN+len(program)):
                    # An R4 routine that has not chosen its mapping by the
                    # capture frame (or deleted itself) is reported, not guessed.
                    missing.append(dict(kind=kind, retail_id=oid, actor=actor.hex()))
                    continue
                assert actor[0] == oid and ORIGIN <= address < ORIGIN+len(program), (name, oid, actor.hex())
                offset = address-ORIGIN
                frames = []
                auto = count is None
                if count is None:
                    # R4 rows derive the pose count from the mapping table
                    # itself: word offsets precede the first mapping, so the
                    # smallest offset / 2 is the number of entries.
                    count = struct.unpack_from('>H', program, offset)[0]//2
                    i = 1
                    while i < count:
                        count = min(count, max(1, struct.unpack_from('>H', program, offset+2*i)[0]//2))
                        i += 1
                    assert 1 <= count <= 64, (name, kind, count)
                poses=list(range(count)) if isinstance(count,int) else count
                for f in poses:
                    pos = offset+struct.unpack_from('>H', program, offset+f*2)[0]
                    # DrawObjects: subq.b #1 then bmi, so a count byte of $81+
                    # draws no piece (R6 gaspat pose 7 is $FF). Kept as empty.
                    mapping = b'\0' if program[pos] > 128 else program[pos:pos+1+5*program[pos]]
                    assert 0 <= mapping[0] <= 32 and len(mapping) == 1+5*mapping[0]
                    # The launcher's two flash-off poses are zero-piece lists
                    # in the Sega CD binary, not missing or unloaded tiles.
                    assert mapping[0] or auto or (kind == 77 and f in (5, 6)) or (kind == 184 and f == 0) or (kind == 84 and f == 1) or (kind == 86 and f == 7) or (kind == 87 and f == 10) or (kind == 88 and f == 1) or (kind in (89,94,154) and f == 2) or (kind in (189,350,410) and f == 2) or (kind == 90 and f in (8,9,13)) or (kind == 92 and f == 14), (name, kind, f)
                    frames.append(mapping.hex())
                if kind == 153 and name.startswith('R6'):
                    # SHOOT6.C ice_set/ice_sub0 give the ice poses 8-11 of gaspat
                    # their own base (retail move.w #ice,2(a1); PC source leaves
                    # 0). One record holds both: poses 0-7 are rebased from the
                    # gas base onto the ice base, piece pixels unchanged.
                    ice = {struct.unpack('>H', m)[0] for m in re.findall(rb'\x33\x7c(..)\x00\x02\x23\x7c'+re.escape(struct.pack('>I', address))+rb'\x00\x04', program, re.S)}
                    assert len(ice) == 1 and len(frames) == 12 and not (tile|next(iter(ice))) & 0xf800, (name, 'gas ice base', ice)
                    ice = ice.pop(); delta = tile-ice; rebased = []
                    for encoded in frames[:8]:
                        m = bytearray(bytes.fromhex(encoded))
                        for i in range(m[0]):
                            word = struct.unpack_from('>H', m, 3+5*i)[0]
                            assert (word & 2047)+delta+ice < 2048
                            struct.pack_into('>H', m, 3+5*i, word+delta)
                        rebased.append(m.hex())
                    frames = rebased+frames[8:]; tile = ice
                records.append(dict(kind=kind, retail_id=oid, tile=tile, address=address,
                                    actor=actor.hex(), frames=frames))
                if not isinstance(count,int):records[-1]['frame_ids']=poses
            if name.startswith('R7'):
                # CHGBAN.C chgban_move toggles sproffset bit 15 with prio_flag.
                # The mapping/tile index does not change; the live CRAM alias does.
                board = next((r for r in records if r['kind'] == 141), None)
                if board:
                    assert board['tile'] & 0x8000
                    records.append(dict(board,kind=141|1<<8,tile=board['tile']&0x7fff,
                                        variant_source='CHGBAN.C chgban_move priority-clear state'))
            out.mkdir(parents=True, exist_ok=True)
            vram = core.swapped(core.vram, 0, 65536)
            (out/'vram.bin').write_bytes(vram)
            report = dict(program=name, frame=frame, objects=records,
                          **({'uncaptured': missing} if missing else {}),
                          dependencies=dependencies(),
                          program_sha256=hashlib.sha256(program).hexdigest(),
                          vram_sha256=hashlib.sha256(vram).hexdigest(),
                          tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
            if cc:
                report['plc_queue_empty_frames'] = queue_ready
                report['fixture'] = dict(camera_x=camera_x if cc_main else None,
                    player_x=camera_x+160 if cc_main else None, player_y=player_y if cc_main else None,
                    release_inject=injected_release, release_capture=release,
                    section=core.work_read(main['sectionID'], 1)[0],
                    enemy_destruction_disabled=cc_main and not keep_good_future,
                    object_plcs=verify_cc_banks(program, records, vram))
            if watch is not None and hasattr(watch, 'records'):
                children, unseen = watch.records(program); records += children
                if unseen:missing += [dict(kind=k, child=True) for k in unseen]
            if name.startswith(('R4', 'R5', 'R6', 'R7', 'R8')):
                # Each captured mapping must read tiles an original PLC bank put
                # in VRAM. A family that fails is listed, not silently packed.
                report['object_plcs'] = {}; report['plc_unverified'] = []
                banks = plc_banks(program)
                check = verify_tile_bytes if name.startswith(('R5', 'R6', 'R7', 'R8')) else verify_tiles
                for record in records:
                    try:report['object_plcs'][record['kind']] = check(program, record, vram, banks)
                    except AssertionError:report['plc_unverified'].append(record['kind'])
                if name.startswith('R8'):
                    for record in records:
                        own = own_bank(program, record) if record['kind']&255 in R8_OWN_BANK or (name, record['kind']) in R8_OWN_BANK_AT else None
                        if own and vram[own[0]:own[0]+len(own[1])] != own[1] and record['kind'] not in report['plc_unverified']:
                            report['plc_unverified'].append(record['kind'])
                # A family whose bank is not resident yet is packed from a
                # sibling source whose VRAM holds that original bank.
                late = [];plc_vram = vram;banks = {}
                for record in records:
                    if record['kind'] not in report['plc_unverified']:continue
                    parent = next((r for r in records if r['kind'] == record['kind'] & 255 and r['kind'] not in report['plc_unverified']), None)
                    anchor = sorted(read_tiles(parent)) if parent and name.startswith('R5') and record['kind'] > 255 else None
                    own = own_bank(program, record) if name.startswith('R8') and (record['kind']&255 in R8_OWN_BANK or (name, record['kind']) in R8_OWN_BANK_AT) else None
                    if own:
                        v = bytearray(plc_vram); v[own[0]:own[0]+len(own[1])] = own[1]
                        overlay = (bytes(v), {'bank': hex(own[0]), 'plcs': sorted(i for i, _, d, a in plc_banks(program) if d == own[0] and a == own[1])})
                    else:overlay = plc_overlay(program, record, plc_vram, anchor)
                    if overlay is None:continue
                    plc_vram, banks[record['kind']] = overlay; late.append(record)
                side = out.parent/(out.name+'-plc')
                if late:
                    side.mkdir(exist_ok=True); (side/'vram.bin').write_bytes(plc_vram)
                    (side/'source.json').write_text(json.dumps(dict(program=name, objects=late, plc_overlay=banks,
                        vram_sha256=hashlib.sha256(plc_vram).hexdigest(), tool_sha256=report['tool_sha256']), indent=2)+'\n')
                    report['plc_overlay'] = sorted(banks)
                elif (side/'source.json').exists():
                    (side/'source.json').unlink(); (side/'vram.bin').unlink()
            (out/'source.json').write_text(json.dumps(report, indent=2)+'\n')
            print(name, [(r['kind'], hex(r['tile']), len(r['frames'])) for r in records])
            return
    raise RuntimeError(f'{name}: retail object fixture never completed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('program')
    parser.add_argument('--fixture',choices=('main','friend','movie','mecasnc','sikake'),default='main')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    fixture=args.fixture
    name=args.program
    kwargs={}
    if fixture=='friend' and name.startswith('R4'):
        # FRIEND4.C m_init: subtype bit 0 picks pat_friend1 (3 poses each);
        # bit 7 skips friend_suicide outside the Good Future. Kind 94|1<<8.
        top=0 if name.endswith('C') else 128
        kwargs.update(objects=[(94,47,3,top),(350,47,3,top+1)],keep_good_future=name.endswith('C'))
    elif fixture=='friend' and name.startswith('R5'):
        # FRIEND5.C: subtype&127 picks Ricky, bit 7 the projector's animals
        # (pat_friend0 Flicky both ways, pat_friend1 placed Ricky, pat_friend2
        # the projector's Ricky; view subtypes 0/1/2). Placed animals live in
        # the Past/Present once the projector is destroyed, and in the Good
        # Future; the Bad Future removes them (friend_suicide).
        assert not name.endswith('D')
        kwargs.update(objects=[(152,45,None,128),(152|1<<8,45,None,1),(152|2<<8,45,None,129)],projector_destroyed=True)
    elif fixture=='friend' and name.startswith('R7'):
        assert not name.endswith('D')
        kwargs.update(objects=[(154,40,3,128),(410,40,5,129)],keep_good_future=name.endswith('C'))
    elif fixture=='friend':
        kwargs.update(objects=[(89,57,3),(189,57,5)],keep_good_future=name.endswith('C'))
    elif fixture=='movie':
        assert name in ('R31B','R32B')
        kwargs.update(objects=[(88,56,6)],camera_x=6900 if name=='R31B' else 5200,
                      player_y=500 if name=='R31B' else 1172)
    elif fixture=='mecasnc':
        # ACT31A ids 48/49/50 share MECASNC.C and MSNCCG.C.  Capture the
        # breakable hazards, Mecha Sonic and Amy from the only program that
        # dispatches these routines; their children reuse the latter two maps.
        assert name=='R31A'
        kwargs.update(objects=[(91,48,15),(92,49,16),(90,50,14)],camera_x=640,
                      player_y=1004)
    elif fixture=='sikake':
        # ACT33C id 54 is SIKAKE33.C: subtype <0 kaitenban (ROLLPLAT.C), 0
        # light (LIGHT.C), otherwise stopper (STOPPER.C). The kaitenban is
        # injected first; its children follow it and point back at it.
        assert name in ('R33C','R33D')
        kwargs.update(objects=[(293,54,4),(93,54,1),(193,54,3)])
    capture(name,args.out or sr.ROOT/'build/zone-object-source'/(name if fixture=='main' else name+'-'+fixture),**kwargs)
