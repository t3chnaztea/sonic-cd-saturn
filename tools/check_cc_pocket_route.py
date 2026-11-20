#!/usr/bin/env python3
"""Verify an ordinary Bad Future controller route actually uses a pocket."""
import hashlib
import json
import struct
import argparse
from pathlib import Path

from convert_assets import ROOT


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--routes',type=Path,default=Path('build/cc1/pocket-final-routes-validation'))
    parser.add_argument('--out',type=Path,default=Path('build/cc1/pocket-final-route-proof.json'))
    args=parser.parse_args()
    folder=ROOT/args.routes
    proof=json.loads((folder/'report.json').read_text())
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    assert proof['four_era_routes_passed']
    assert proof['disc_sha256']==sha(ROOT/'dist/sonic-cd-saturn-prototype.bin')
    for path,digest in proof['artifacts'].items():assert sha(ROOT/path)==digest
    log=folder/'D/results.log'
    rows=[list(map(int,line.split(': ',1)[1].split())) for line in log.read_text().splitlines() if line.startswith('CC route: ')]
    layout=ROOT/'assets/generated/ccobj31.bin'
    pockets={(x,y-16) for x,y,kind,sub,flags,eras,secondary in struct.iter_unpack('>hhBBBBBx',layout.read_bytes())
             if kind==84 and sub&128 and eras&4}
    captures=[]
    for i in range(2,len(rows)-126):
        entry=rows[i];xy=tuple(entry[2:4])
        if xy not in pockets or rows[i-1][2:4]==entry[2:4] or entry[9:]!=[1,0,3]:continue
        hold=rows[i:i+125];exit_rows=rows[i+125:i+127]
        if not all(tuple(r[2:4])==xy for r in hold):continue
        assert rows[i-2][3]<rows[i-1][3]<entry[3], 'descending entry'
        assert xy[0]-24<=rows[i-1][2]<xy[0]+24, 'original capture width'
        assert all(r[4]==6 and r[6]==0 and r[8]==128 for r in hold+exit_rows), 'rolling, no respawn, Right only'
        assert [r[3] for r in exit_rows]==[xy[1]-8,xy[1]-16], 'automatic upward release'
        assert all(b[1]-a[1]==1 for a,b in zip(hold+exit_rows,(hold+exit_rows)[1:])), 'one refresh per update'
        captures.append(dict(placement=[xy[0],xy[1]+16],capture_sequence=entry[0],
            release_sequence=hold[-1][0],stationary_observations=125,
            first_two_released_y=[r[3] for r in exit_rows],pad='Right, without Jump'))
    assert captures, 'route did not exercise a pocket'
    report=dict(passed=True,disc_sha256=proof['disc_sha256'],captures=captures,
        inputs={str(p.relative_to(ROOT)):sha(p) for p in [folder/'report.json',log,layout,Path(__file__)]},
        limits='Ordinary controller-driven capture/hold/automatic release at a real Bad Future placement. This log does not expose score, sound output or the hidden-control byte; those have separate source/native checks.')
    (ROOT/args.out).write_text(json.dumps(report,indent=2)+'\n')
    print('Verified',len(captures),'ordinary Bad Future pocket capture/release sequence')


if __name__=='__main__':main()
