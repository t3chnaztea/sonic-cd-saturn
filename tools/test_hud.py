#!/usr/bin/env python3
"""Compare the imported HUD pieces composed as on Saturn with original MD mappings."""
import struct,unittest
from hud_assets import build
from hud_pixels import expected,verify,COLORS

class OriginalHUD(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.groups,cls.blob=build()
    def test_bounds_and_palette_codes(self):
        for records in self.groups.values():
            for x,y,w,h,offset in records:
                self.assertEqual(offset%8,0);self.assertEqual(w%8,0)
                self.assertLessEqual(offset+w*h*2,len(self.blob))
        self.assertLessEqual(len(self.blob),0x8000)
        self.assertTrue(all(v==0 or 0x4001<=v<=0x401f for v in struct.unpack('>'+str(len(self.blob)//2)+'H',self.blob)))
    def test_original_mappings_and_counters(self):
        for era in range(4):
            for score,rings,ticks,lives in [(0,0,0,3),(123456,19,3685,7),(9999999,999,35999,12)]:
                actual={}
                def piece(p,x,y):
                    px,py,w,h,offset=p
                    for j in range(h):
                        for i in range(w):
                            v=struct.unpack_from('>H',self.blob,offset+(j*w+i)*2)[0]
                            if v:
                                c=struct.unpack_from('>H',COLORS,(v&15)*2)[0]
                                actual[x+px+i+5,y+py+j]=bytes(((c&31)*8,(c>>5&31)*8,(c>>10&31)*8))
                def number(value,digits,x,y,leading=False):
                    for i,c in enumerate(str(value).zfill(digits) if leading else str(value).rjust(digits)):
                        if c!=' ':piece(self.groups['digits'][int(c)],x+i*8,y)
                for p in self.groups['labels']+self.groups['rings0']:piece(p,16,8)
                number(score,7,56,8);number(ticks//3600,1,56,24,True)
                number(ticks//60%60,2,72,24,True);number(99 if ticks==35999 else ticks%60*100//60,2,96,24,True)
                number(rings,3,64,40);piece(self.groups['lives'][(1,0,2,2)[era]],16,200)
                piece(self.groups['cross'][0],16,200);number(min(lives,9),1,40,204,True)
                self.assertEqual(actual,expected(score,rings,ticks,lives,era),(era,score,rings,ticks,lives))
    def test_verified_pixel_count_excludes_skipped_label(self):
        pixels=expected(1234,0,5678,3,0)
        rgb=bytearray(330*224*3)
        skipped=0
        for (x,y),color in pixels.items():
            if 40<=y<56 and x<61:skipped+=1
            else:rgb[(y*330+x)*3:(y*330+x+1)*3]=color
        image=b'P6\n330 224\n255\n'+rgb
        self.assertGreater(skipped,0)
        self.assertEqual(verify(image,1234,0,5678,3,0,check_rings=False),len(pixels)-skipped)
        with self.assertRaises(AssertionError):verify(image,1234,0,5678,3,0)
    def test_flashing_ring_label(self):
        for normal,flash in zip(self.groups['rings0'],self.groups['rings1']):
            self.assertEqual(normal[:4],flash[:4]);size=normal[2]*normal[3]*2
            a=struct.unpack('>'+str(size//2)+'H',self.blob[normal[4]:normal[4]+size])
            b=struct.unpack('>'+str(size//2)+'H',self.blob[flash[4]:flash[4]+size])
            self.assertEqual(tuple(v+16 if v else 0 for v in a),b)

if __name__=='__main__':unittest.main()
