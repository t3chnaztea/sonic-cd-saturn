#!/usr/bin/env python3
"""Private CMG1 from the independently decoded original COME module.
Import is inert. CLI needs separate guarded asset admission. No retail code ships.
"""
import argparse
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path
from stage_select_assets import sha,verify_inputs
ROOT=Path(__file__).resolve().parents[1]
PROGRAM_SHA='78dd650016ff9a0f8226dcc79a0ee90791b7d8fdbbb8d60497ca1d0bdbee3792'

def save_failure(report,error,save):
    report.update(status='interrupted' if isinstance(error,KeyboardInterrupt) else 'failed',error=repr(error))
    try: save()
    except BaseException as secondary:
        report['failure_save_error']=repr(secondary)
        try: print('FAIL: Coming report save: '+repr(secondary),file=sys.stderr)
        except BaseException: pass

def decode_program(program,nemesis):
    if len(program)!=8952 or sha(program)!=PROGRAM_SHA: raise ValueError('unreviewed COME program')
    if struct.unpack_from('>IHI',program,2)!=(0xff2000,3071,0xff2000): raise ValueError('COME header')
    regs=bytes([4,52,48,0,7,80,0,0,0,0,0,0,129,41,0,2,3,0,0])
    if program[0x2a4:0x2b7]!=regs or program[0x276:0x27a]!=bytes.fromhex('01400000') or program[0x18e:0x194]!=bytes.fromhex('31fc03fffa42'): raise ValueError('COME H40/scroll/timer context')
    palette=program[0x2b8:0x2d8];art=nemesis(program[0x2d8:0x7dc])
    maps=[program[at:at+1792] for at in (0x7dc,0xedc,0x15dc)]
    return palette,art,maps

def make_pack(palette,art,parts):
    if len(palette)!=32 or len(art)!=4800 or any(art[:32]) or len(parts)!=3 or any(len(x)!=1792 for x in parts): raise ValueError('COME asset shape')
    if any(v&~0xeee for v in struct.unpack('>16H',palette)): raise ValueError('COME palette')
    plane=[0]*4096
    for column,part in enumerate(parts):
        words=struct.unpack('>896H',part)
        if any((w&2047)>=150 or (w&0x6000) for w in words): raise ValueError('COME map tile/palette')
        for y in range(28):plane[y*128+column*32:y*128+column*32+32]=words[y*32:y*32+32]
    payload=palette+bytes(96)+art+struct.pack('>4096H',*plane)
    logical=32+len(payload)
    if logical!=13152: raise ValueError('COME logical size')
    blob=b'CMG1'+struct.pack('>7I',logical,150,4096,320,1023,zlib.crc32(payload),64)+payload
    return blob+bytes(-len(blob)%2048)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ROOT/'cd/COMING.BIN');p.add_argument('--report',type=Path,default=ROOT/'build/coming-assets/report.json');a=p.parse_args()
    from extract_mmd import disc_files,ISO
    from convert_assets import nemesis
    from scd_source import SRC
    paths=[Path(__file__),ROOT/'tools/stage_select_assets.py',ROOT/'tools/staff_times_assets.py',ROOT/'tools/extract_mmd.py',ROOT/'tools/convert_assets.py',ROOT/'tools/scd_source.py',SRC/'CD System Program/SPX.asm',SRC/'CD Initial Program/IPX.asm',SRC/'Title Screen/Secrets/Stage Select.asm']
    pins={str(p):sha(p.read_bytes()) for p in paths}
    report=dict(status='pending',inputs=pins,python=sys.version,zlib=zlib.ZLIB_VERSION,scope='private CMG1 data only; no target pixel/audio acceptance')
    a.report.parent.mkdir(parents=True,exist_ok=True)
    def save():a.report.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        disc=ISO.read_bytes();pins[str(ISO)]=sha(disc);report['disc_sha256']=pins[str(ISO)];save()
        program=disc_files(disc)['COME__.MMD'];report['program_sha256']=sha(program)
        palette,art,parts=decode_program(program,nemesis);blob=make_pack(palette,art,parts)
        verify_inputs(pins,required=(ISO,));a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(blob)
        report.update(status='passed',output=str(a.output),output_sha256=sha(blob),bytes=len(blob),tiles=150,plane=[128,32],source_banner=[96,28],initial_scroll=320,timer=1023,source_physical_payload=8696,source_unprovided_tail=3592,retail_program_included=False)
        save();print('PASS: Coming private exact-original CMG1 pack')
    except BaseException as error:
        save_failure(report,error,save);raise
if __name__=='__main__':main()
