#!/usr/bin/env python3
"""src/scroll_limits.h must still agree with the retail scroll programs.

The header is generated, so the only failure this can report is that somebody
edited it by hand or that the retail sources moved underneath it.
"""
import io,os,re,subprocess,sys,unittest
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEADER=os.path.join(ROOT,'src/scroll_limits.h')
sys.path.insert(0,os.path.join(ROOT,'tools'))
import extract_scroll_limits as gen
def read(path):
    with open(path) as handle:return handle.read()

class ScrollLimits(unittest.TestCase):
    def test_header_matches_the_generator(self):
        before=read(HEADER)
        out=io.StringIO();keep=sys.stdout;sys.stdout=out
        try:gen.main()
        finally:sys.stdout=keep
        after=read(HEADER)
        self.assertEqual(before,after,'src/scroll_limits.h is stale; run tools/extract_scroll_limits.py')

    def test_every_playable_stage_has_a_row(self):
        text=read(HEADER)
        rows=re.findall(r'\{(\d+),(-?\d+),(\d+),(\d+),(\d+),(\d+),(\d+),(\d+),(\d)\}',text)
        self.assertEqual(len(rows),7*3*4,'the table is no longer 7 rounds by 3 acts by 4 eras')
        valid=[r for r in rows if r[8]=='1']
        # Seventy stage programs ship on the disc: ten per round, and the two
        # Act 3 programs are Good Future and Bad Future only.
        self.assertEqual(len(valid),70)
        for round_index in range(7):
            for era in range(4):
                act3=rows[round_index*12+2*4+era]
                self.assertEqual(act3[8],'1' if era>=2 else '0')

    def test_no_row_claims_a_zero_width_stage(self):
        text=read(HEADER)
        for match in re.finditer(r'\{(\d+),(-?\d+),(\d+),(\d+),\d+,\d+,\d+,\d+,1\}',text):
            right,up,down,vline=(int(g) for g in match.groups())
            self.assertGreater(right,1000)
            self.assertGreater(down,0)
            self.assertEqual(vline,96)
            self.assertGreaterEqual(up,0)

if __name__=='__main__':
    unittest.main()
