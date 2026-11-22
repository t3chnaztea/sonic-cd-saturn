#!/usr/bin/env python3
"""Controller input for an SCD_ACT_PAD_RECORD re-recording run from a host
route script (tools/cc_campaign_search.c "COUNT PAD" lines, PPZ mode pA:E).

The host applies script pad i at update i+4 (two observations of libretro
delay after the load update); a reference row r (1-based update) therefore
carries native buttons of pad r-4. The 16 state words are placeholders:
SCD_ACT_PAD_RECORD ignores them and the run's own output becomes the new
strict reference (as tools/shift_act_reference.py does for V0.057)."""
import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('script');parser.add_argument('updates',type=int,help='host tally sequence');parser.add_argument('output')
parser.add_argument('--base',type=int,default=63,help='reference sequence of update 0 (Act 2 debug entry: 63)')
a=parser.parse_args()
pads=[]
for line in open(a.script):
    n,p=map(int,line.split());pads+= [p]*n
native=lambda p:(1 if p&16 else 0)|(2 if p&32 else 0)|(4 if p&64 else 0)|(8 if p&128 else 0)|(16 if p&1 else 0)
with open(a.output,'w') as f:
    for r in range(1,a.updates+1):
        b=native(pads[r-4]) if 0<=r-4<len(pads) else 0
        # Word 6 is the simulation update count (act_pad_load checks it); the rest are placeholders.
        words=["00000000"]*16;words[6]=f"{r:08x}"
        f.write(f"{a.base+r} {b} "+" ".join(words)+"\n")
