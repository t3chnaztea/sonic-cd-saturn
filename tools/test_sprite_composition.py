"""Source-first composition tests, including independent packed-art decode."""
import hashlib
import json
import re
import struct
import unittest
from pathlib import Path

from convert_assets import OUT, ROOT
from sprite_composition import source_sprite, CORRECTED_FRAMES as CORRECTED
from audit_sprite_composition import capture
from test_objects import unpack_texture

MONITORS = dict(zip(range(159,169), [212,92,156,99,100,142,92,100,224,224]))
# Present generator mappings overlap just like their original Past counterparts.
# These frames are also checked against console VRAM captures by the generator
# artwork test; keep their first-piece versus last-piece difference explicit.
WITHERED_GENERATOR = {392: 140, 393: 544}


class SpriteRules(unittest.TestCase):
    def test_first_opaque_not_high_priority_or_last(self):
        colors = struct.pack('>16H', 0,0x8000,*[0x8000+n for n in range(2,16)])
        # Foremost opaque black is not transparent; a transparent texel lets
        # the next piece show. Its priority bit does not change list order.
        art = bytes([0x10] * 32 + [0x22] * 32)
        mapping = bytes([2,224,0,0,0,252,224,0,0x80,1,252])
        actual = source_sprite(mapping, art, colors, 8, 0, 8)
        self.assertEqual(struct.unpack('>64H', actual), tuple([0x8000,0x8002]*32))
        self.assertNotEqual(actual, source_sprite(mapping, art, colors, 8, 0, 8, legacy_last=True))
        with self.assertRaises(AssertionError): source_sprite(mapping, art[:32], colors, 8, 0, 8)

    def test_column_major_tiles_and_piece_flips(self):
        colors = struct.pack('>16H', *[0x8000+n for n in range(16)])
        art = b''.join(bytes([n*17]*32) for n in range(1,5))
        for flags in (0,0x800,0x1000,0x1800):
            mapping = struct.pack('>BbBHb', 1, -32, 5, flags, -8)
            pixels = struct.unpack('>256H', source_sprite(mapping, art, colors, 16, 0, 16))
            for y in range(16):
                for x in range(16):
                    sx,sy=(15-x if flags&0x800 else x),(15-y if flags&0x1000 else y)
                    self.assertEqual(pixels[y*16+x], 0x8001+(sx//8)*2+sy//8)


def verify_assets():
    records, catalog, isolated, inputs = capture()
    assert len(records) == 403  # 397 + the six ObjPoints frames (catalog 28)
    for name, raw in isolated.items(): assert raw == (OUT/name).read_bytes(), name
    metadata = (OUT/'object-frames.inc').read_text()
    def array(name): return list(map(int, re.search(name+r'\[\]=\{([^}]+)',metadata)[1].split(',')))
    widths,heights,tops,offsets,canvases = [array(n) for n in
        ['object_widths','object_heights','object_tops','object_raw_offsets','object_canvases']]
    raw = unpack_texture((OUT/'object-art.bin').read_bytes())
    differences = {}; total_pixels = 0; covered = set(); frame_hashes = {}
    card_raw = unpack_texture((OUT/'title-card-art.bin').read_bytes())
    card_meta = (OUT/'title-card.inc').read_text().split('title_card_frames',1)[1]
    card_layout = [tuple(map(int, row.split(','))) for row in re.findall(r'\{([\d,-]+)\}',card_meta)]
    for r in records:
        args = [r[n] for n in ['mapping','art','colors','width','y_shift','height']]
        first = source_sprite(*args); last = source_sprite(*args, legacy_last=True)
        assert r['actual'] == first, ('source order',r['kind'],r['frame'])
        frame = r['frame']; width = r['width']; height = r['height']
        difference = sum(a!=b for a,b in zip(struct.iter_unpack('>H',first),struct.iter_unpack('>H',last)))
        if r['kind']=='object':
            covered.add(frame)
            if difference: differences[frame]=difference
            assert widths[frame]==width and canvases[frame]==height
            off=offsets[frame]; h=heights[frame]; top=tops[frame]; data=raw
            assert off%32==0 and (off+width*h//2)%32==0
        else:
            off,w,h,_,_=card_layout[frame]; assert (w,h)==(width,height)
            top=0;data=card_raw
        clut=data[off+width*h//2:off+width*h//2+32]
        decoded=b''.join(clut[n*2:n*2+2] for b in data[off:off+width*h//2] for n in (b>>4,b&15))
        canonical=bytes(top*width*2)+decoded+bytes((height-top-h)*width*2)
        assert canonical==first, ('packed source pixels',r['kind'],frame)
        total_pixels+=width*height
        frame_hashes[f"{r['kind']}-{frame}"]=hashlib.sha256(first).hexdigest()
    assert differences == CORRECTED | MONITORS | WITHERED_GENERATOR, ('changed frame set',differences)
    assert covered == set(range(404))-set(range(240,246))-set(range(306,310))
    report=dict(passed=True,compositions=len(records),object_frames=len(covered),
                title_card_frames=len(card_layout),pixels=total_pixels,
                additional_corrected_frames=CORRECTED,additional_corrected_pixels=sum(CORRECTED.values()),
                frame_sha256=frame_hashes,raw_object_bytes=len(raw),source_input_sha256=inputs,
                source_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
                    ['tools/convert_objects.py','tools/sprite_composition.py','tools/audit_sprite_composition.py',
                     'tools/test_sprite_composition.py','.deps/scddisasm/src/Level/Object Functions.asm',
                     '.deps/genesis-plus-gx/core/vdp_render.c']},
                artifact_sha256={name:hashlib.sha256(blob).hexdigest() for name,blob in isolated.items()})
    (ROOT/'build/sprite-composition-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f"Source-first sprites: {len(records)} compositions / {total_pixels} exact pixels; 33 further frames / 5032 pixels corrected")
    return report


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(SpriteRules)
    assert unittest.TextTestRunner().run(suite).wasSuccessful()
    verify_assets()
