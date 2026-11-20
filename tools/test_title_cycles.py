#!/usr/bin/env python3
"""Hardware cycle legality, independently of an emulator's rendered pixels."""
import re,unittest
from pathlib import Path
from vdp2_title_cycles import errors,state_sections

def configured():
    source=(Path(__file__).resolve().parents[1]/'src/title_vram.h').read_text()
    def bank(name):
        word=int(re.search(r'#define '+name+r' (0x[0-9A-F]+)u',source)[1],16)
        return [(word>>n)&15 for n in range(28,-1,-4)]
    return [bank('SCD_TITLE_VRAM_A0'),[15]*8,[15]*8,bank('SCD_TITLE_VRAM_B1')]

class TitleCycles(unittest.TestCase):
    def test_current_schedule(self):
        banks=configured();self.assertEqual(errors(banks),[])
        self.assertEqual(banks[0],[0,1,15,15,4,5,15,15])
    def test_old_hardware_violation(self):
        banks=configured();banks[0]=[0,0,1,1,4,5,15,15]
        found=errors(banks)
        self.assertIn('NBG1: PN T2 cannot feed CG T5',found)
        self.assertIn('NBG1: PN T3 cannot feed CG T5',found)
        self.assertTrue(any('expected one PN' in s for s in found))
    def test_missing_and_duplicate_fetches(self):
        for screen,bank,slot in [(0,0,0),(1,0,1),(3,3,0),(4,0,4),(5,0,5),(7,3,4)]:
            with self.subTest(screen=screen):
                b=configured();b[bank][slot]=15;self.assertTrue(errors(b))
                b=configured();b[bank][7]=screen;self.assertTrue(errors(b))
    def test_late_character_fetch_limit(self):
        b=configured();b[0][1]=15;b[0][2]=1
        self.assertEqual(errors(b),['NBG1: PN T2 cannot feed CG T5'])
        b[0][5]=15;b[0][6]=5;self.assertEqual(errors(b),[])
    def test_bad_state_rejected(self):
        for data in [b'',b'MDFNSVST'+bytes(24),b'MDFNSVST'+bytes(12)+(100).to_bytes(4,'little')+bytes(8)]:
            with self.assertRaises((AssertionError,ValueError)):state_sections(data)

if __name__=='__main__':unittest.main()
