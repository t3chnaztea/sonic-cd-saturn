#!/usr/bin/env python3
"""Camera QA must reject missing, ambiguous and mismatched layer evidence."""
import copy,unittest
from camera_pixels import anchor_match,spring_pixels,springs,verify_coherence
from terrain_pixels import foreground_pixel

class CameraPixels(unittest.TestCase):
    def test_source_anchors(self):
        anchors=springs()
        self.assertIn((8816,744,2,0),anchors)
        self.assertIn((9072,936,0,0),anchors)

    def test_exact_versus_shifted_pixels(self):
        camera=(8752,678);anchor=(8816,744,2,0)
        picture=bytearray(330*224*3)
        for (dx,dy),rgb in spring_pixels(2,0,0).items():
            x,y=8816-camera[0]+dx,744-camera[1]+dy
            terrain=foreground_pixel('Present',8816+dx,744+dy)
            if terrain and terrain[0]:rgb=terrain[1]
            picture[(y*330+x+5)*3:(y*330+x+5)*3+3]=rgb
        self.assertEqual(anchor_match(picture,anchor,camera,camera,0),404)
        self.assertEqual(anchor_match(picture,anchor,(8752,691),camera,0),0)
        picture[(66*330+64+5)*3]^=255
        self.assertEqual(anchor_match(picture,anchor,camera,camera,0),0)

    @staticmethod
    def rows():
        return [{'tick':n,'terrain_camera':(0,n),'terrain_pixels':1001,
                 'history':[(0,n),(0,n-1)],
                 'sprites':[{'anchor':(20,40,0,0),'cameras':[((0,n),[(0,200)])]}]}
                for n in range(16)]

    def test_coherent(self):
        self.assertEqual(verify_coherence(self.rows())['sprite_pixels'],3200)

    def test_missing_shifted_ambiguous_and_static_rejected(self):
        rows=self.rows()
        changes=[lambda r:r[3].update(sprites=[]),
                 lambda r:r[3]['sprites'][0].update(cameras=[((0,2),[(0,200)])]),
                 lambda r:r[3]['sprites'][0]['cameras'].append(((0,2),[(0,200)])),
                 lambda r:r[3].update(tick=9),
                 lambda r:[x.update(history=[x['terrain_camera']]) for x in r],
                 lambda r:r.pop()]
        for change in changes:
            with self.subTest(change=change):
                candidate=copy.deepcopy(rows);change(candidate)
                with self.assertRaises(AssertionError):verify_coherence(candidate)

if __name__=='__main__':unittest.main()
