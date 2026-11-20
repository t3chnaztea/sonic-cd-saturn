#!/usr/bin/env python3
"""Compare native Collision Chaos line scroll with symbolic execution of SCR31A-D, SCR32A-D and SCR33C-D.C."""
import argparse
import ctypes as C
import json
import struct
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/scroll'))
sys.path.insert(0,str(ROOT/'tools/scroll/R3'))
import extract  # noqa: E402
import sym as S  # noqa: E402
from cfront import RETAIL  # noqa: E402


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full',action='store_true',help='compare every reachable camera window')
    parser.add_argument('--act',type=int,choices=(1,2,3),default=1)
    parser.add_argument('--retail-only',action='store_true',help='compare the saved retail CPU fixtures first')
    args=parser.parse_args()
    letters='CD' if args.act==3 else 'ABCD'
    out=ROOT/f'build/cc{args.act}/scroll-native';out.mkdir(parents=True,exist_ok=True)
    libpath=out/'native.dylib'
    subprocess.run(['clang','-std=c11','-O2','-fwrapv','-Wall','-Wextra','-Werror','-Isrc',
                    '-dynamiclib','src/background_r3.c','-o',str(libpath)],cwd=ROOT,check=True)
    native=C.CDLL(str(libpath))
    native.scd_r3_lines_layers.argtypes=[C.c_uint,C.c_int,C.POINTER(C.c_int32),C.c_int,C.c_int,C.c_uint,
                                         C.POINTER(C.c_int32),C.POINTER(C.c_int32),C.c_uint]
    comparisons=windows=retail_authority=0
    background=(C.c_int32*224)();foreground=(C.c_int32*224)()
    original_scan=extract.scan_windows

    def compare(R,model,ir,tables):
        nonlocal comparisons,windows,retail_authority
        era=ord(Path(R.name).stem[-1])-ord('A')+4*(args.act-1)
        reachable=sorted(y for y in R.reachable if y<ir['buffer_lines'])
        if not args.full:
            probes={0,1,7,8,9,31,32,55,56,57,60,63,64,68,79,80,87,95,96,
                    480,481,482,487,488,527,528,532,536}
            reachable=[y for y in reachable if y in probes]
        for frame in extract.SCAN_FRAMES:
            phase=extract.phase_for_frame(R,frame)
            envs={x:extract.word_env(model,tables,x,frame) for x in extract.SCAN_X}
            for top in reachable:
                lines,machine=R.window(top,phase)
                camera_y=R.camera_for[top] if R.camera_for is not None else top
                for x in extract.SCAN_X:
                    layers=(C.c_int32*4)(12*x*256,24*x*256,16*x*256,0)
                    native.scd_r3_lines_layers(era,x,layers,camera_y,top,frame,background,foreground,224)
                    env=envs[x]
                    for i,low in enumerate(lines):
                        expected=(-S.evaluate(low,env))&511
                        actual=(background[i]>>16)&511
                        if actual!=expected:
                            # The reconstructed SCR31B.C says 24 lines in one
                            # branch, while the retail CPU capture proves both
                            # water bands are 32 lines. Captures below are the
                            # authority for exactly these eight lines per band.
                            y=top+i
                            if args.act==1 and ((era==1 and any(s+24<=y<s+32 for s in (64,528))) or
                                                (era==0 and (y<48 or 632<=y<704))):
                                retail_authority+=1
                                continue
                            # SCR32A/C and SCR33C.C say the ten-entry ramp at world rows
                            # 624-703 starts at m=0 with a <<11 step. Retail CPU
                            # captures prove m=(entry-77)*1024 (as SCR31C), and
                            # 32-line SCR32B water bands. Retail fixtures below
                            # are the authority for exactly these lines.
                            if ((era in (2,4,6,10) and 624<=y<704) or
                                (era==5 and any(s+24<=y<s+32 for s in (64,528)))):
                                retail_authority+=1
                                continue
                            raise AssertionError((R.name,'background',top,x,frame,i,actual,expected))
                        comparisons+=1
                    windows+=1
        return {}

    extract.scan_windows=compare
    try:
        if not args.retail_only:
            for era in letters:extract.derive(RETAIL/'R3'/f'SCR3{args.act}{era}.C',scan=True)
    finally:
        extract.scan_windows=original_scan
    # The symbolic extractor intentionally models the background word only.
    # Compare both words against CPU-produced retail captures, including the
    # foreground sine deformation near the bottom of the act.
    speeds={'A':49152,'B':32768,'C':49152,'D':49152}
    captures=0
    for letter in letters:
        era='ABCD'.index(letter)
        base=ROOT/f'build/cc{args.act}/scroll-retail'/f'R3{args.act}{letter}'
        report=json.loads((base/'report.json').read_text())
        for sample in report['samples']:
            index=sample['index'];after=(base/f'{index:03}-deform-after.bin').read_bytes()
            acc=struct.unpack_from('>I',after)[0];assert acc%speeds[letter]==0
            frame=acc//speeds[letter]
            actual=sample['actual_16_16'];x=actual['cameraX']>>16;camera_y=actual['cameraY']>>16;top=actual['cameraBgY']>>16
            layers=(C.c_int32*4)(actual['cameraBgX'],actual['cameraBg2X'],actual['cameraBg3X'],
                                  65535 if sample['scroll_x_diff_8_8']<0 else 0)
            native.scd_r3_lines_layers(era+4*(args.act-1),x,layers,camera_y,top,frame,background,foreground,224)
            source=(base/f'{index:03}-hscroll.bin').read_bytes()
            for i in range(224):
                fg,bg=struct.unpack_from('>hh',source,i*4)
                expected_bg=(-bg)&511;expected_fg=(-fg)&511
                got_bg=(background[i]>>16)&511;got_fg=(foreground[i]>>16)&511
                if (got_bg,got_fg)!=(expected_bg,expected_fg):
                    raise AssertionError((f'R3{args.act}{letter}','capture',index,frame,i,(got_bg,got_fg),(expected_bg,expected_fg)))
                comparisons+=2
            captures+=1
    scope='all reachable' if args.full else 'boundary/correction'
    print(f'CC{args.act} scroll: {comparisons} original/native line words across {windows} {scope} windows and {captures} retail captures pass'
          +(f'; {retail_authority} source lines deferred to retail captures' if retail_authority else ''))


if __name__=='__main__':main()
