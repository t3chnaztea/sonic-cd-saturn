#!/usr/bin/env python3
"""Retail runtime VRAM for MM2A's ET8 (generator, kind 169) against its packed source.

The R82A fixture VRAM holds PLC 2's $6000 bank where retail draws ET8 from
PLC 4/8's bank at its tile base, so tools/zone_object_source.py packs ET8 from
the R82A-plc source with that own bank laid over (R8_OWN_BANK_AT). This boots
the original R82A program, walks Sonic to the placed generator
(MM2 layout, the only type 169 record: x 1352, y 1408, eras A/B), lets section
PLCs load as the camera arrives, waits until the original actor (R82A act_tbl
id 67) is on screen, and compares VRAM with the packed R82A-plc source on every
tile its mappings read. Emulator evidence only, not a hardware result.

    python3 tools/check_mm2a_et8_vram.py
"""
import json
import struct
from pathlib import Path

from capture_cc_scroll import boot
from capture_cc_plane import walk
import zone_object_source as source

ROOT = Path(__file__).resolve().parents[1]
ET8_ID, ET8_X, ET8_Y = 67, 1352, 1408


def main():
    src = ROOT/'build/zone-object-source/R82A-plc'
    report = json.loads((src/'source.json').read_text())
    record, = [o for o in report['objects'] if o['kind'] == 169]
    captured = (src/'vram.bin').read_bytes()
    tiles = sorted({t % 65536 for t in source.read_tiles(record)})
    core, e, frame, _ = boot('A', act=2, rnd=8)
    frame = walk(core, e, frame, ET8_X-160, ET8_Y-96)
    seen = None
    for n in range(600):
        core.pad = 0; core.run(); frame += 1; core.host.chunks.clear()
        for at in range(e['dynObjects'], e['objectsEnd'], 64):
            actor = core.work_read(at, 64)
            if actor[0] == ET8_ID and actor[1] & 0x80 and n >= 120:
                seen = (at, actor)
                break
        if seen:break
    assert seen, 'ET8 never on screen in retail R82A'
    at, actor = seen
    tile, address = struct.unpack_from('>HI', actor, 2)
    assert address == record['address'] and tile & 0x7ff == record['tile'] & 0x7ff, (hex(tile), hex(address), record['address'])
    vram = core.swapped(core.vram, 0, 65536)
    differ = [hex(t) for t in tiles if vram[t:t+32] != captured[t:t+32]]
    x, y = struct.unpack_from('>H', actor, 8)[0], struct.unpack_from('>H', actor, 12)[0]
    out = ROOT/'build/mm2a-et8'; out.mkdir(parents=True, exist_ok=True)
    (out/'report.json').write_text(json.dumps(dict(frame=frame, slot=hex(at), actor_x=x, actor_y=y, tile=hex(tile),
        tiles=len(tiles), first=hex(tiles[0]), last=hex(tiles[-1]+31), differ=differ, passed=not differ), indent=2)+'\n')
    assert not differ, ('retail VRAM differs from the packed R82A-plc source', differ)
    print(f'PASS: MM2A ET8 retail frame {frame}, actor at ({x},{y}) tile {tile:#x}: '
          f'{len(tiles)} tiles {tiles[0]:#x}-{tiles[-1]+31:#x} equal the packed R82A-plc source')


if __name__ == '__main__':
    main()
