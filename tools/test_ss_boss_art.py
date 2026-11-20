#!/usr/bin/env python3
"""Prove SS3 boss source art against both unmodified retail race programs.

This is an art fixture, not a controller route. Only Sonic's position, motion,
flags and rings are held. Boss actors, mappings, PLCs and palettes run normally.
Follow behind Metal Sonic to expose electricity, then pass the finish to expose
his debris. Verify every source pose against live resident tiles when its actor
first appears, plus each live pose throughout the race and PLC transitions.
"""
import hashlib
import json
import struct
from pathlib import Path

from boss_retail_capture import boot, live_actors
from convert_assets import ROOT
from extract_mmd import ISO, SS_BOSS_KIND, disc_files, stardust_speedway_boss
from zone_object_source import read_tiles

OUT = ROOT/'build/ss-boss-art'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(name):
    folder = ROOT/f'build/zone-object-source/{name}-boss'
    source = json.loads((folder/'source.json').read_text())
    expected = (folder/'vram.bin').read_bytes()
    objects = {o['retail_id']:o for o in source['objects']}
    patch = bytes.fromhex(source['palette_patch']['words'])
    core, engine, main, program = boot(name)
    assert hashlib.sha256(program).hexdigest() == source['program_sha256']
    seen = {}; poses = {}; tiles_checked = 0; observations = 0; palette_frames = 0
    phases = {}; live_sets = set(); first_tiles = {}; phase_frames = []
    for frame in range(1,4301):
        player = bytearray(core.work_read(engine['objPlayerSlot'],64))
        x = 3100 if frame < 1000 else min(16048,3100+(frame-1000)*12)
        metal = next((a for _,a in live_actors(core,engine,{47})),None)
        if metal is not None and 1000 <= frame < 1800:
            x = struct.unpack_from('>h',metal,8)[0]-64
        struct.pack_into('>hHhHhhh',player,8,x,0,460,0,0,0,0)
        player[engine['oFlags']] = 2; player[engine['oAnim']] = 0
        core.work_write(engine['objPlayerSlot'],player)
        core.work_write(main['rings'],struct.pack('>H',50))
        core.pad = 0;core.run();core.host.chunks.clear()
        live = live_actors(core,engine,set(objects))
        vram = core.swapped(core.vram,0,65536)
        signature = hashlib.sha256(vram[0x300*32:0x530*32]).hexdigest()
        if live and signature not in phases:
            phases[signature] = frame
        live_sets.add(tuple(sorted({a[0] for _,a in live})))
        if any(a[0] == 44 and a[engine['oRoutine']] for _,a in live):
            palette = core.work_read(engine['palette']+32,12)
            assert palette == patch, (name,frame,'boss palette entries16-21',palette.hex(),patch.hex())
            palette_frames += 1
        for _,actor in live:
            oid = actor[0]; record = objects[oid]
            tile,address = struct.unpack_from('>HI',actor,2)
            if not address:continue  # Newly allocated child, before its initializer.
            if oid == 46 and address != record['address']:
                # BOSS_7.C egg7beam smoke switches to common bakupat/$680.
                assert tile == 0x680, (name,frame,'beam alternate',hex(tile),hex(address))
                continue
            assert address == record['address'] and tile & 0x7fff == record['tile'], (name,frame,oid,hex(tile),hex(address))
            pose = actor[0x1a]
            assert pose < len(record['frames']), (name,frame,oid,pose)
            poses.setdefault(oid,set()).add(pose)
            if oid not in seen:
                seen[oid] = dict(frame=frame,mapping=address,tile=tile)
                check_tiles = read_tiles(record)
                first_tiles[oid] = len(check_tiles)
            else:
                check_tiles = read_tiles(dict(record,frames=[record['frames'][pose]]))
            for at in check_tiles:
                assert vram[at:at+32] == expected[at:at+32], (name,frame,oid,pose,hex(at//32),'tile mismatch')
            tiles_checked += len(check_tiles);observations += 1
    assert set(seen) == set(SS_BOSS_KIND), (name,'unseen actor',set(SS_BOSS_KIND)-set(seen))
    assert palette_frames > 1000 and observations > 1000
    return dict(passed=True,status='passed',program=name,program_sha256=source['program_sha256'],
                source_sha256=digest(folder/'source.json'),vram_sha256=digest(folder/'vram.bin'),
                frames=4300,actor_observations=observations,tiles_checked=tiles_checked,
                palette_frames=palette_frames,palette_patch=source['palette_patch'],
                actors=seen,observed_poses={k:sorted(v) for k,v in poses.items()},
                all_source_pose_tiles=first_tiles,plc_vram_phases=phases,
                live_actor_sets=sorted(live_sets),hardware_tested=False)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    path = OUT/'report.json'
    report = dict(passed=False,status='pending',programs={},hardware_tested=False,
                  inputs={p:digest(ROOT/p) for p in ('tools/test_ss_boss_art.py','tools/extract_mmd.py',
                          'tools/boss_retail_capture.py','tools/zone_object_source.py',
                          '.deps/soniccd/src/R7/BOSS_7.C','.deps/soniccd/src/R7/COL7C.C',
                          '.deps/soniccd/src/R7/COL7D.C')})
    path.write_text(json.dumps(report,indent=2)+'\n')
    try:
        extraction = {};stardust_speedway_boss(disc_files(ISO.read_bytes()),extraction)
        report['extraction'] = extraction
        for name in ('R73C','R73D'):
            report['programs'][name] = check(name)
            path.write_text(json.dumps(report,indent=2)+'\n')
            print(name,report['programs'][name]['actor_observations'],'live actor observations',flush=True)
        report.update(passed=True,status='passed')
    except BaseException as error:
        report.update(status='interrupted' if isinstance(error,KeyboardInterrupt) else 'failed',error=str(error))
        raise
    finally:
        path.write_text(json.dumps(report,indent=2)+'\n')
    print('PASS: SS3 boss kinds 240-246 match retail mappings, PLC tiles and six-color palette in both futures')


if __name__ == '__main__':main()
