#!/usr/bin/env python3
"""Check WW3's live PLC 19 tile pacing and every packed entry-pose update."""
import hashlib
import json
import struct

from boss_retail_capture import boot
from convert_assets import ROOT
from zone_object_assets import SOURCE, per_piece, source_frames, source_parts
import zone_art_lz


def progressed(entry, fight, age, first):
    vram = bytearray(entry)
    for tile, count, begin in ((0x300, 236, first),
                               (0x3ec, 84, first+79),
                               (0x440, 24, first+107)):
        n = max(0, min(count, (age-begin+1)*3))
        lo = tile*32
        vram[lo:lo+n*32] = fight[lo:lo+n*32]
    return vram


def check_pack(name, entry, fight):
    era = 'ABCD'.index(name[-1])
    pack = (ROOT/'assets/generated/zone-art-63.bin').read_bytes()
    at = struct.unpack_from('>I', pack, 4+era*4)[0]
    count, raw_size, packed_size = struct.unpack_from('>III', pack, at)
    record_at = at+12
    raw = bytearray(zone_art_lz.unpack(pack[record_at+count*48:record_at+count*48+packed_size], raw_size//2))
    patch = record_at+count*48+packed_size
    assert pack[patch:patch+4] == b'W6PT'
    end_age, reserved = struct.unpack_from('>HH', pack, patch+4)
    assert end_age == (105 if name.endswith('D') else 106) and reserved == 0
    ends = struct.unpack_from(f'>{end_age+1}I', pack, patch+8)
    assert ends[0] == 0
    body = patch+8+4*(end_age+1)
    assert body+ends[-1] <= len(pack)
    source = json.loads((SOURCE/(name+'-boss-entry')/'source.json').read_text())
    objects = {o['kind']:o for o in source['objects']}
    records = []
    parts = {}
    for i in range(count):
        kind, frame, offset, width, height, left, top, *refs = struct.unpack_from('>HHIHHhh16H', pack, record_at+i*48)
        if kind not in objects:continue
        part = parts.get((kind,frame), 0);parts[(kind,frame)] = part+1
        records.append((kind,frame,part,offset&65535,width,height,left,top,refs))
    assert {r[0] for r in records} == {496,497,498,499} and len(records) >= 22
    first = 21 if name.endswith('D') else 22
    pixels_checked = 0
    for age in range(end_age+1):
        if age:
            pos, stop = body+ends[age-1], body+ends[age]
            while pos < stop:
                word, n = struct.unpack_from('>HH', pack, pos);pos += 4
                assert n and (word+n)*2 <= raw_size and pos+n*2 <= stop
                raw[word*2:(word+n)*2] = pack[pos:pos+n*2];pos += n*2
            assert pos == stop
        vram = progressed(entry, fight, age, first)
        for kind, frame, part, offset, width, height, left, top, refs in records:
            obj = objects[kind]
            pose = list(obj.get('frame_ids') or range(len(obj['frames']))).index(frame)
            one = dict(obj, frames=[obj['frames'][pose]])
            pieces = next(source_parts(one, vram)) if per_piece(6,obj) else [next(source_frames(one, vram))]
            x,y,w,h,expected = pieces[part]
            assert (x,y,w,h)==(left,top,width,height)
            bitmap = raw[offset:offset+w*h//2]
            actual = bytes(0 if color==0 else refs[color]+1 for b in bitmap for color in (b>>4,b&15))
            assert actual == expected, (name,age,kind,frame,part)
            pixels_checked += len(expected)
    return pixels_checked, len(records), end_age, ends[-1]


def check_live(name, entry, fight):
    core, engine, _, program = boot(name)
    source = json.loads((SOURCE/(name+'-boss-entry')/'source.json').read_text())
    assert hashlib.sha256(program).hexdigest() == source['program_sha256']
    first = 21 if name.endswith('D') else 22
    started = None; checked = 0
    for t in range(1, 290):
        player = bytearray(core.work_read(engine['objPlayerSlot'],64))
        struct.pack_into('>hHhHhhh', player, 8, 2700,0,1660,0,0,0,0)
        player[engine['oFlags']]=2;player[engine['oAnim']]=0
        core.work_write(engine['objPlayerSlot'], player);core.pad=0
        core.run();core.host.chunks.clear()
        if core.work_read(0xfff7aa,1)[0]&31==6 and started is None:started=t
        if started is None:continue
        age=t-started+1
        expected=progressed(entry,fight,age,first)
        live=core.swapped(core.vram,0,65536)
        for tile,count in ((0x300,236),(0x3ec,84),(0x440,24)):
            lo=tile*32;hi=lo+count*32
            assert expected[lo:hi]==live[lo:hi],(name,age,hex(tile))
        checked+=1
    return checked


def main():
    for name in ('R63C','R63D'):
        entry=(SOURCE/(name+'-boss-entry')/'vram.bin').read_bytes()
        fight=(SOURCE/(name+'-boss')/'vram.bin').read_bytes()
        pixels,records,ages,bytes_=check_pack(name,entry,fight)
        live=check_live(name,entry,fight)
        print(f'{name}: {records} mutable records, {ages} updates, {pixels} exact sprite pixels, {bytes_} patch bytes, {live} live retail frames')
    print('PASS: WW3 PLC 19 entry sprites match every retail tile write in both futures')


if __name__=='__main__':main()
