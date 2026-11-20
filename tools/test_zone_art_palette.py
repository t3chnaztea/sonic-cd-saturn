#!/usr/bin/env python3
"""R7 art palette contracts; optional negative check against an existing capture."""
import argparse
from pathlib import Path
import tempfile
import unittest

from check_zone_object_target import ROOT, check, r7_cycles, retain_palette_latency


class PaletteTests(unittest.TestCase):
    def test_original_col7_color_sets(self):
        # COL7D.C col6a0cnt/col: CRAM39 alternates orange and black.
        self.assertEqual(r7_cycles('D',3)[39], {0x223f,0})
        self.assertEqual(set(r7_cycles('A',1)), {41,62,63})
        self.assertEqual(r7_cycles('B',1), {})
        self.assertEqual(r7_cycles('C',3), {})

    def test_act_alternate(self):
        self.assertEqual(set(r7_cycles('D',1)), {39,45,46,47,49,58})
        for act in (2,3):
            self.assertEqual(set(r7_cycles('D',act)), {39,45,46,47,49,62})
            self.assertEqual(r7_cycles('D',act)[62],r7_cycles('D',1)[58])

    def test_mixed_sample_rejected(self):
        # Two individually legal colors cannot use different timestamps.
        candidates={0,1};colors={0:b'orange',1:b'black'}
        retain_palette_latency(candidates,b'black',colors)
        with self.assertRaisesRegex(AssertionError,'consistent'):
            retain_palette_latency(candidates,b'orange',colors)

    def test_wrong_color_rejected(self):
        with self.assertRaisesRegex(AssertionError,'consistent'):
            retain_palette_latency({0,1},b'wrong',{0:b'orange',1:b'black'})


def negative_capture(folder):
    # The failed case112 pixel is high-priority CRAM39. Change only its RGB
    # bytes to a color outside BOTH samples; keep texture and geometry intact.
    with tempfile.TemporaryDirectory(prefix='art-palette-',dir=ROOT/'build') as temp:
        target=Path(temp)
        for source in folder.iterdir():
            if source.is_file() and source.name!='report.json':
                (target/source.name).symlink_to(source.resolve())
        name='zone-art-112.ppm';image=(folder/name).read_bytes()
        header,pixels=image.split(b'255\n',1);pixels=bytearray(pixels)
        offset=((100+13)*330+136+11+5)*3
        pixels[offset:offset+3]=b'\x01\x02\x03'
        (target/name).unlink();(target/name).write_bytes(header+b'255\n'+pixels)
        try:
            check('R73D',target)
        except AssertionError as error:
            assert 'consistent indexed CRAM' in str(error),error
        else:
            raise AssertionError('wrong screenshot pixel accepted')
    print('PASS: R73D case112 wrong-pixel capture rejected')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--capture',type=Path)
    args=parser.parse_args()
    result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(PaletteTests))
    if not result.wasSuccessful():raise SystemExit(1)
    if args.capture:negative_capture(args.capture)
