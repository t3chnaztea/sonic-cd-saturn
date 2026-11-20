#!/usr/bin/env python3
"""Check generated HUD textures and bounded signed-PCM feedback assets."""
import hashlib,json,struct,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class FeedbackAssets(unittest.TestCase):
    def test_hud_font(self):
        raw=(ROOT/'assets/generated/hud-font.bin').read_bytes()
        self.assertEqual(len(raw),59*128)
        words=struct.unpack('>3776H',raw)
        self.assertEqual(set(words),{0,65535})
        for c in 'RINGS0123456789TIMELVDASHCY':
            self.assertGreater(sum(words[(ord(c)-32)*64:(ord(c)-31)*64]),0)
    def test_signed_pcm(self):
        data=(ROOT/'assets/generated/feedback.pcm').read_bytes()
        samples=struct.unpack(str(len(data))+'b',data)
        self.assertGreater(max(samples),40);self.assertLess(min(samples),-40)
        self.assertLessEqual(max(map(abs,samples)),100)
        report=json.loads((ROOT/'build/feedback-source.json').read_text())
        self.assertLess(len(data)+report['ram_base'],report['ram_end'])
        self.assertEqual((report['ram_base'],report['ram_end']),(0xe000,0x7f000))
        self.assertEqual(report['bytes'],len(data))
        # 53: Quartz Quadrant's bank adds BOSS_5.C's retail PCM requests 196 ($C4) and 203 ($CB);
        # 54: PLAYER.C bye_chk's voice, sub_sync(121) ($B4), resident.
        self.assertEqual(len(report['samples']),54)
        # Resident effects plus the largest swappable bank (zone or special stage) fit sound RAM.
        self.assertEqual([b['file'] for b in report['banks']],['SFXZ0.PCM','SFXZ1.PCM','SFXSP.PCM','SFXZ2.PCM','SFXZ3.PCM'])
        for b in report['banks']:self.assertLessEqual(report['bank_base']+b['ram_bytes'],report['ram_end'])
    def test_original_music(self):
        report=json.loads((ROOT/'build/feedback-source.json').read_text())
        self.assertTrue(report['music'])
        self.assertEqual(report['music_source']['region'],'Japan')
        self.assertEqual([t["retail_track"] for t in report["tracks"]],[3,None,4,5,28,29,30,32,24,26]+[n for z in range(1,7) for n in (3+z*3,None,4+z*3,5+z*3)]+[25]+[27,31,33,34,35,2])
        self.assertGreater(report['past_capture']['sequencer_repeat_frames'][1],1000)
        for track in report['tracks']:
            self.assertTrue(track['soundtrack'].startswith('Japan'))
            raw=(ROOT/f"assets/generated/music{track['era']}.raw").read_bytes()
            self.assertEqual(len(raw),track['sectors']*2352)
            self.assertEqual(hashlib.sha256(raw).hexdigest(),track['sha256'])
            # Slot 40, the prototype warp (CDDA_WARP), is a 4.2 s jingle.
            self.assertGreater(len(raw),44100*4*(60 if track['era']<4 else 4 if track['era']==40 else 5))
if __name__=='__main__' :unittest.main()
