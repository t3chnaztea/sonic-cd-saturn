#!/usr/bin/env python3
"""Compare the browser timer model to compiled original DEV41A source."""
import argparse
from pathlib import Path
import tt_terrain_assets as terrain
from terrain_schedule import TidalSchedule


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    out=args.out.resolve()
    if not out.is_relative_to(terrain.ROOT/'build') or out.exists():
        parser.error('Choose a new directory under build/')
    out.mkdir(parents=True)
    terrain.BUILD=out
    native=terrain.oracle()
    model=TidalSchedule(terrain.SOURCE.read_text())
    total=0
    for x,y in [(0,0),(639,351),(640,0),(0,352),(-1,-1)]:
        native.init();model.init()
        for frame in range(1400):
            native.step(x,y);model.step(x,y)
            for start in terrain.SLOTS:
                for offset in range(16):
                    index=start+offset
                    if native.tile(index)!=model.tile(index):
                        raise AssertionError((x,y,frame,index))
                    total+=1
    print(f'PASS: browser terrain schedule; {total} tile values match compiled DEV41A')


if __name__=='__main__':main()
