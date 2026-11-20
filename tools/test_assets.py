#!/usr/bin/env python3
"""Data-format tests with independent known patterns and native geometry code."""
import ctypes
import pathlib
import struct
import subprocess
import unittest
from convert_assets import ROOT, nemesis, palette, layout

class Formats(unittest.TestCase):
    def test_inline_nemesis_and_xor(self):
        # Eight identical rows encoded as inline runs of eight color-3 pixels.
        bits=('111111'+'111'+'0011')*8
        payload=int(bits,2).to_bytes(len(bits)//8,'big')
        self.assertEqual(nemesis(b'\x00\x01\xff'+payload),b'\x33'*32)
        self.assertEqual(nemesis(b'\x80\x01\xff'+payload),(b'\x33'*4+b'\0'*4)*4)
    def test_table_nemesis(self):
        self.assertEqual(nemesis(b'\x00\x01\x85\x71\x00\xff\x00'),b'\x55'*32)
    def test_truncated_bitstream(self):
        with self.assertRaises(ValueError):nemesis(b'\x00\x01\xff')
    def test_floor_bitmap_is_lossless(self):
        import hashlib
        raw=(ROOT/'assets/generated/floor.bin').read_bytes()
        packed=(ROOT/'assets/generated/floor.rle').read_bytes()
        decoded=b''.join(struct.pack('>H',word)*count for count,word in struct.iter_unpack('>HH',packed))
        self.assertEqual(hashlib.sha256(raw).hexdigest(),'e5138fd655dee53e3f5a78f233b9c32184284a07671f5436c28078940fb8640c')
        self.assertEqual(decoded,raw)
        self.assertEqual((len(raw),len(packed)),(131072,32708))
    def test_motion_rle_is_lossless(self):
        raw=(ROOT/'assets/generated/sonic-motion.bin').read_bytes()
        packed=(ROOT/'assets/generated/sonic-motion.rle').read_bytes()
        decoded=b''.join(struct.pack('>H',word)*count for count,word in struct.iter_unpack('>HH',packed))
        self.assertEqual(decoded,raw)
        self.assertEqual(len(raw),21*8192)
        self.assertLess(len(packed),len(raw)//2)
    def test_motion_indexed_colors_are_lossless(self):
        packed=(ROOT/'assets/generated/sonic-motion-indexed.rle').read_bytes()
        data=b''.join(struct.pack('>H',word)*count for count,word in struct.iter_unpack('>HH',packed))
        self.assertEqual(len(data),21*2080)
        decoded=bytearray()
        for frame in range(21):
            pixels=data[frame*2080:frame*2080+2048]
            clut=struct.unpack('>16H',data[frame*2080+2048:(frame+1)*2080])
            self.assertEqual(clut[0],0)
            for byte in pixels:decoded.extend(struct.pack('>HH',clut[byte>>4],clut[byte&15]))
        self.assertEqual(decoded,(ROOT/'assets/generated/sonic-motion.bin').read_bytes())
    def test_palette_channels(self):
        self.assertEqual(palette(bytes.fromhex('000e00e00e000eee')),bytes.fromhex('801f83e0fc00ffff'))
    def test_layout_row_stride(self):
        result=layout(bytes([1,1,1,2,3,4]))
        self.assertEqual(result[:3],b'\1\2\0')
        self.assertEqual(result[64:67],b'\3\4\0')

class Geometry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        output=ROOT/'build/stage-test.dylib'
        subprocess.run(['clang','-dynamiclib','-Wall','-Wextra','-Werror','-Isrc',
                        'src/stage.c','-o',str(output)],cwd=ROOT,check=True)
        cls.lib=ctypes.CDLL(str(output))
        cls.lib.stage_saturn_pnd.argtypes=[ctypes.c_uint16,ctypes.c_uint32]
        cls.lib.stage_saturn_pnd.restype=ctypes.c_uint32
    def test_priority_palette_and_flip_conversion(self):
        self.assertEqual(self.lib.stage_saturn_pnd(0x0003,4096),4099)
        self.assertEqual(self.lib.stage_saturn_pnd(0xF803,0),0xE0030003)
        self.assertEqual(self.lib.stage_saturn_pnd(0x8003,0),0x20000003)
    def test_all_generated_packages(self):
        class Stage(ctypes.Structure):
            _fields_=[('part',ctypes.c_void_p*6),('size',ctypes.c_uint32*6),('x',ctypes.c_uint16),('y',ctypes.c_uint16)]
        self.lib.stage_open.argtypes=[ctypes.POINTER(Stage),ctypes.c_void_p,ctypes.c_size_t]
        self.lib.stage_tile.argtypes=[ctypes.POINTER(Stage),ctypes.c_int,ctypes.c_int,ctypes.c_int]
        self.lib.stage_tile.restype=ctypes.c_uint16
        for path in sorted((ROOT/'assets/generated').glob('ppz*.bin')):
            payload=path.read_bytes();buf=ctypes.create_string_buffer(payload);stage=Stage()
            self.assertEqual(self.lib.stage_open(ctypes.byref(stage),buf,len(payload)),0)
            self.assertEqual(self.lib.stage_open(ctypes.byref(Stage()),buf,55),-1)
            for x,y in [(-1,0),(0,-1),(16384,0),(0,2048)]:
                self.assertEqual(self.lib.stage_tile(ctypes.byref(stage),0,x,y),0)
            # Independent direct chain: layout -> chunk -> block -> tile.
            offsets=[struct.unpack_from('>I',payload,4+i*8)[0] for i in range(6)]
            for background in (0,1):
                for y in range(0,2048,24):
                    for x in range(0,16384,40):
                        chunk=payload[offsets[3+background]+(y//256)*64+x//256]&127
                        expected=0
                        if chunk:
                            block=struct.unpack_from('>H',payload,offsets[2]+(chunk-1)*512+((y//16)%16)*32+((x//16)%16)*2)[0]
                            sx=(x//8)%2 ^ bool(block&0x800);sy=(y//8)%2 ^ bool(block&0x1000)
                            expected=struct.unpack_from('>H',payload,offsets[1]+(block&1023)*8+sy*4+sx*2)[0] ^ (block&0x1800)
                            if (expected&2047)*32>=stage.size[0]:expected=0
                        self.assertEqual(self.lib.stage_tile(ctypes.byref(stage),background,x,y),expected)

if __name__=='__main__':unittest.main()
