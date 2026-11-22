#!/usr/bin/env python3
"""Private STG1 from exact original Stage Select source/disc. Import is inert.
Generated maps are not an independent whole-image oracle. No retail code ships.
"""
import argparse
import hashlib
import json
import re
import struct
import sys
import zlib
from pathlib import Path
from staff_times_assets import encode_text, vdp_command
ROOT=Path(__file__).resolve().parents[1]
REL='Title Screen/Secrets'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def verify_inputs(pins,required=()):
    if any(str(p) not in pins for p in required): raise ValueError('required input pin missing')
    for path,expected in pins.items():
        with Path(path).open('rb') as file:
            digest=hashlib.file_digest(file,'sha256').hexdigest()
        if digest!=expected: raise ValueError('input changed during conversion: '+path)

def save_failure(report,error,save):
    report.update(status='interrupted' if isinstance(error,KeyboardInterrupt) else 'failed',error=repr(error))
    try: save()
    except BaseException as secondary:
        report['failure_save_error']=repr(secondary)
        try: print('FAIL: StageSelect report save: '+repr(secondary),file=sys.stderr)
        except BaseException: pass

def parse_source(source):
    def font(label):
        block=source.split(label+':',1)[1].split('; -------------------------------------------------------------------------',1)[0].split('.TilesLower:',1)[0]
        values=[int(v,16) for v in re.findall(r'^\s*dc\.b\s+\$([0-9A-Fa-f]+)',block,re.M)]
        if len(values)!=45: raise ValueError('expected45 source glyphs')
        return bytes(values)
    strings=dict(re.findall(r'(TextDat_\w+):\s*TEXTSTR\s+"([^"\n]*)"',source))
    def entries(label,end):
        block=source.split(label+':',1)[1].split(end,1)[0]
        return [(n,int(x),int(y)) for n,x,y in re.findall(r'TEXTPTR\s+(\w+),\s*(\d+),\s*(\d+)',block)]
    clear=entries('Text_Clear','TEXTEND');header=entries('Text_StageSelect','TEXTEND');choices=entries('Text_Selections','Text_SelectionsEnd:')
    if clear!=[('TextDat_Clear',14,13)] or header!=[('TextDat_StageSelect',14,9)] or len(choices)!=74 or len(set(n for n,_,_ in choices))!=74: raise ValueError('source table shape')
    if any((x,y)!=(14,13) for _,x,y in choices): raise ValueError('selection position')
    names=[n for n,_,_ in choices]
    if [(i,strings.get(names[i])) for i in (8,9,10,73)]!=[(8,'WARP'),(9,'OPENING'),(10,'COMMING'),(73,'SPEDEMO')]: raise ValueError('source extra rows')
    if sum(bool(re.fullmatch(r'TextDat_R[1345678][123][ABCD]',n)) for n in names)!=70: raise ValueError('source70 normal rows')
    if strings.get('TextDat_Clear')!='          ' or strings.get('TextDat_StageSelect')!='STAGE SELECT' or any(n not in strings for n in names): raise ValueError('source text')
    if any(len(strings[n])>10 for n in names): raise ValueError('selection width')
    return dict(upper=font('.TilesUpper'),lower=font('.TilesLower'),strings={k:encode_text(v) for k,v in strings.items()},clear=clear,header=header,choices=choices)

def planes(spec):
    header=[0]*(40*28);choices=[]
    def put(plane,width,name,x,y,base):
        text=spec['strings'][name][:-1]
        if x+len(text)>width or (y+1)*width+x+len(text)>len(plane): raise ValueError('text outside plane')
        for n,code in enumerate(text):
            plane[y*width+x+n]=base+spec['upper'][code]
            plane[(y+1)*width+x+n]=base+spec['lower'][code]
    for name,x,y in spec['header']+spec['clear']: put(header,40,name,x,y,0)
    for name,_,_ in spec['choices']:
        choice=[0]*20;put(choice,10,name,0,0,0x6000);choices.extend(choice)
    return struct.pack('>1120H',*header),struct.pack('>1480H',*choices)

def bind_program(program,spec):
    if len(program)<0x100: raise ValueError('short STSEL')
    origin=struct.unpack_from('>I',program,2)[0]
    def table(entry):
        name,x,y=entry;text=spec['strings'][name];at=program.find(text,0x100);matches=[]
        while at>=0:
            candidate=struct.pack('>HIII',0,origin+at-0x100,vdp_command(0xc000+x*2+y*128),vdp_command(0xc000+x*2+(y+1)*128))
            where=program.find(candidate,0x100)
            if where>=0 and program.find(candidate,where+1)<0: matches.append(candidate)
            at=program.find(text,at+1)
        if len(matches)!=1: raise ValueError('nonunique source text/position table '+name)
        return matches[0]
    for group in (spec['clear'],spec['header'],spec['choices']):
        assembled=b''.join(table(e) for e in group)
        at=program.find(assembled,0x100)
        if at<0 or program.find(assembled,at+1)>=0: raise ValueError('source table order differs from STSEL')
    for key in ('upper','lower'):
        if spec[key] not in program[0x100:]: raise ValueError('font absent from STSEL')
    regs=bytes([4,0x34,0x30,0,7,0x78,0,0,0,0,0,0,0x81,0x3d,0,2,1,0,0])
    if regs not in program[0x100:]: raise ValueError('source H40/64x32 registers absent from STSEL')
    return origin

def make_pack(palette,art,background,header,choices):
    if len(palette)!=128 or not art or len(art)%32 or len(art)//32>2048 or any(art[:32]): raise ValueError('palette/art dimensions or blank tile')
    if len(background)!=2240 or len(header)!=2240 or len(choices)!=2960: raise ValueError('map dimensions')
    if any(v&~0xeee for v in struct.unpack('>64H',palette)): raise ValueError('MD palette')
    maps=background+header+choices
    if any((v&2047)>=len(art)//32 for v in struct.unpack('>3720H',maps)): raise ValueError('missing tile')
    payload=palette+art+maps;logical=32+len(payload)
    blob=b'STG1'+struct.pack('>7I',logical,len(art)//32,1120,1120,74,zlib.crc32(payload),64)+payload
    blob+=bytes(-len(blob)%2048)
    if len(blob)>0x14000: raise ValueError('pack exceeds low RAM')
    return blob

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ROOT/'cd/STAGESEL.BIN');p.add_argument('--report',type=Path,default=ROOT/'build/stage-select-assets/report.json');a=p.parse_args()
    # Private data reads only after explicit guarded CLI admission.
    from extract_mmd import disc_files,ISO
    from convert_assets import nemesis
    from scd_source import SRC
    source=SRC/REL/'Stage Select.asm'
    paths=[source,SRC/REL/'_Macros.inc',SRC/REL/'_Variables.inc',SRC/REL/'Functions.asm',SRC/'_Include/MMD.inc',Path(__file__),ROOT/'tools/staff_times_assets.py',ROOT/'tools/convert_assets.py',ROOT/'tools/extract_mmd.py',ROOT/'tools/scd_source.py']
    pins={str(x):sha(x.read_bytes()) for x in paths};report=dict(status='pending',inputs=pins,python=sys.version,zlib=zlib.ZLIB_VERSION,scope='private STG1 source/disc pack; no image/scene acceptance')
    a.report.parent.mkdir(parents=True,exist_ok=True)
    def save(): a.report.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        spec=parse_source(source.read_text());disc=ISO.read_bytes();pins[str(ISO)]=sha(disc);report['disc_sha256']=pins[str(ISO)];save();program=disc_files(disc)['STSEL_.MMD'];report['program_sha256']=sha(program);report['origin']=bind_program(program,spec)
        parts=[]
        for name in ('Palette.bin','Art.nem','Background Mappings (H40).bin'):
            path=SRC/REL/'Data'/name;data=path.read_bytes();pins[str(path)]=sha(data)
            if not data or data not in program[0x100:]: raise ValueError(name+': absent from STSEL')
            parts.append(data)
        header,choices=planes(spec);blob=make_pack(parts[0],nemesis(parts[1]),parts[2],header,choices)
        verify_inputs(pins,required=(ISO,))
        a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(blob);report.update(status='passed',output=str(a.output),output_sha256=sha(blob),bytes=len(blob),records=74);save();print('PASS: StageSelect private source/disc pack74')
    except BaseException as e:
        save_failure(report,e,save);raise
if __name__=='__main__': main()
