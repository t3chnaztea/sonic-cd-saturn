#!/usr/bin/env python3
"""Build a format 2 candidate under build/. Independent audit is mandatory.

No game build is run. Accepted artifacts are read only. A candidate is never
declared distributable by this tool; audit-recipe.py supplies that decision.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
from recipe_elf import Elf
from recipe_provenance import classify,complete,literal_owner_totals
from recipe_tables import build as build_tables,materialize
from recipe_iso import catalog,structure,boot_blobs,boot_tables

ROOT=Path(__file__).resolve().parents[1]
BIN_SHA='cb872d149ba3575d9929a1072bb006dd403b97e79dfdfa0a6b4782bf178a3e66'
CUE_SHA='10f35a87674de372bc4b217a4e877f5321aa683afda91eab18df2df331d04337'


def digest(path):
    with path.open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def record(path,name=None):
    return dict(name=name or path.name,bytes=path.stat().st_size,sha256=digest(path))


def runs(data):
    """Keep deterministic zero fill out of the literal payload."""
    at=0
    for match in re.finditer(b'\0{16,}',data):
        if match.start()>at:yield at,match.start()-at,False
        yield match.start(),match.end()-match.start(),True;at=match.end()
    if at<len(data):yield at,len(data)-at,False


class Payload:
    def __init__(self):self.data=bytearray();self.ranges=[]
    def add(self,data,owner,evidence):
        ops=[]
        for start,count,zero in runs(data):
            if zero:ops.append(dict(kind='zero',length=count));continue
            offset=len(self.data);self.data.extend(data[start:start+count])
            ops.append(dict(kind='literal',offset=offset,length=count))
            self.ranges.append(dict(offset=offset,bytes=count,owner=owner,evidence=evidence))
        return ops


def program_recipe(root,file,p,tables,payload):
    data=(root/file).read_bytes();covered=[None]*len(data)
    for index,row in enumerate(tables):
        if row['file']!=file:continue
        derived=materialize(row,root)
        if derived!=data[row['offset']:row['offset']+row['bytes']]:raise ValueError('Table recipe changed')
        for at in range(row['bytes']):covered[row['offset']+at]=(index,at)
    allowed=bytearray(len(data))
    for row in p['ranges']:
        allowed[row['offset']:row['offset']+row['bytes']]=bytes([{'literal':1,'derive':2,'unresolved':0}[row['kind']]])*row['bytes']
    ops=[];at=0
    boundaries=sorted({n for s in p['symbols'] for n in (s['offset'],s['offset']+s['bytes'])})
    while at<len(data):
        if covered[at]is not None:
            index,offset=covered[at];end=at+1
            while end<len(data)and covered[end]==(index,offset+end-at):end+=1
            ops.append(dict(kind='derive',table=index,offset=offset,length=end-at));at=end;continue
        end=at+1
        boundary=next((n for n in boundaries if n>at),len(data))
        while end<boundary and end<len(data)and covered[end]is None and allowed[end]==allowed[at]:end+=1
        chunk=data[at:end]
        if not any(chunk):ops.append(dict(kind='zero',length=len(chunk)))
        elif allowed[at]!=1:raise ValueError(f'Unserialized {file} range at {at}, {end-at} bytes')
        else:
            choices=[s for s in p['symbols']if s['kind']=='literal' and s['offset']<=at and end<=s['offset']+s['bytes']]
            if not choices:raise ValueError(f'Literal has no source ownership: {file} at {at}')
            choices.sort(key=lambda s:(s['owner']=='compiled-control-table',s['owner']=='compiled-function-and-pools',s['bytes']))
            ops.extend(payload.add(chunk,'program',dict(file=file,offset=at,provenance=[choices[0]])))
        at=end
    return dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),ops=ops)


def make(out,cache):
    out=out.resolve()
    if not out.is_relative_to(ROOT/'build')or out.exists():raise ValueError('Choose a new output directory under build/')
    target=ROOT/'dist/sonic-cd-saturn-prototype.bin';cue=target.with_suffix('.cue')
    if digest(target)!=BIN_SHA or digest(cue)!=CUE_SHA:raise ValueError('Accepted image pins failed')
    out.mkdir(parents=True);cache.mkdir(parents=True,exist_ok=True)
    provenance=classify(ROOT,cache);tables=build_tables(ROOT,cache,provenance)
    (out/'tables.json').write_text(json.dumps(tables,indent=2)+'\n')
    provenance=complete(ROOT,provenance,tables)
    (out/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    if tables['failures']or any(p['unresolved_bytes']for p in provenance['programs'].values()):
        raise ValueError('Incomplete program certification; see local provenance and table reports')
    image=(ROOT/'dist/iso/sonic-cd-saturn-prototype.iso').read_bytes();boots=boot_blobs(ROOT,image)
    rows=tables['initializers']+tables['copies']+tables['strings'];first_boot=len(rows);rows+=boot_tables(boots);payload=Payload()
    programs={file:program_recipe(ROOT,file,p,rows,payload)for file,p in provenance['programs'].items()}
    layout=catalog(image)
    def structure_ops(start,end):
        ops=[];at=start
        for index,row in enumerate(boots):
            if row['offset']>=end or row['offset']+row['bytes']<=start:continue
            if row['offset']<at or row['offset']+row['bytes']>end:raise ValueError('Boot blob overlaps an ISO file')
            ops.extend(payload.add(image[at:row['offset']],'ISO-structure',dict(source='tools/recipe_iso.py',offset=at,bytes=row['offset']-at)))
            ops.append(dict(kind='derive',table=first_boot+index,offset=0,length=row['bytes']));at=row['offset']+row['bytes']
        ops.extend(payload.add(image[at:end],'ISO-structure',dict(source='tools/recipe_iso.py',offset=at,bytes=end-at)))
        return ops
    native_files={p.relative_to(ROOT).as_posix():p for p in (ROOT/'cd').rglob('*')if p.is_file()}
    if set(native_files)!={r['source']for r in layout['files']}:raise ValueError('ISO and CD file catalog differ')
    metadata={};iso_ops=[];at=0
    for row in sorted(layout['files'],key=lambda r:r['offset']):
        source=ROOT/row['source']
        if source.stat().st_size!=row['bytes']or digest(source)!=row['sha256']:raise ValueError('ISO/CD file mismatch')
        if row['offset']<at:raise ValueError('Overlapping ISO file extents')
        iso_ops.extend(structure_ops(at,row['offset']))
        iso_ops.append(dict(kind='derive',file=row,offset=0,length=row['bytes']))
        at=row['offset']+row['bytes']
        if source.suffix=='.TXT':
            metadata[row['source']]=dict(bytes=row['bytes'],sha256=row['sha256'],
                ops=payload.add(source.read_bytes(),'project-CD-text',dict(file=row['source'],source=row['source'])))
    iso_ops.extend(structure_ops(at,len(image)))
    iso=dict(bytes=len(image),sha256=layout['sha256'],ops=iso_ops)
    sector_count=len(image)//2048;data_count=sector_count*2352
    with target.open('rb')as stream:
        remaining=data_count;checksum=hashlib.sha256()
        while remaining:
            block=stream.read(min(1024*1024,remaining));checksum.update(block);remaining-=len(block)
    data_track=dict(bytes=data_count,sha256=checksum.hexdigest())
    jp=(ROOT/'assets/private/sonic-cd-japan.cue').resolve()
    names=re.findall(r'^\s*FILE "([^"\r\n]+)" BINARY\s*$',jp.read_text(encoding='utf-8-sig'),re.M)
    if not names or any('/'in n or '\\'in n or n in ('.','..')for n in names):raise ValueError('Unsupported JP CUE')
    sources=[dict(record(jp),role='jp')]+[dict(record(jp.parent/n),role='jp')for n in names]
    sources.extend(dict(record(ROOT/p),role=role)for p,role in [('build/retail/sonic.bin','us'),('build/retail/sonic.cue','us'),('assets/private/bios_CD_U.bin','bios')])
    derived=[dict(name='build/browser/data.raw',**data_track),dict(name='build/browser/pregap.raw',bytes=150*2352,sha256=hashlib.sha256(bytes(150*2352)).hexdigest())]
    ops=[dict(kind='derive',file=r['name'],offset=0,length=r['bytes'])for r in derived]
    for index in range(41):
        row=record(ROOT/f'assets/generated/music{index}.raw',f'assets/generated/music{index}.raw')
        source=next((i for i,r in enumerate(sources)if r['role']=='jp'and r['bytes']==row['bytes']and r['sha256']==row['sha256']),None)
        if source is None:
            derived.append(row);ops.append(dict(kind='derive',file=row['name'],offset=0,length=row['bytes']))
        else:ops.append(dict(kind='source',index=source,offset=0,length=row['bytes']))
    elf=Elf(ROOT/'build/saturn/sonic-cd-saturn-prototype.elf')
    symbols={s['name']:s['value']for s in elf.symbols if s['name']in ('__sector','___end')}
    firmware_data=(ROOT/'build/sound-driver/driver.bin').read_bytes()
    firmware=dict(bytes=len(firmware_data),sha256=hashlib.sha256(firmware_data).hexdigest(),
        ops=payload.add(firmware_data,'PoneSound-program',dict(source='tools/ponesound/driver.c',
            source_sha256=digest(ROOT/'tools/ponesound/driver.c'),artifact='build/sound-driver/driver.bin')))
    construction=dict(schema=1,programs=programs,metadata=metadata,tables=rows,iso=iso,
        iso_layout=layout,boot_blobs=boots,data_track=data_track,firmware=firmware,linked_symbols=symbols,elf_sha256=elf.sha256,
        us_iso=record(ROOT/'build/retail/sonic.iso'),
        payload_sha256=hashlib.sha256(payload.data).hexdigest(),literal_ranges=payload.ranges)
    manifest=dict(format=2,version='V0.082',sources=sources,derivations=derived,ops=ops,
        target=dict(bytes=target.stat().st_size,sha256=BIN_SHA,cue=cue.read_text(),cue_sha256=CUE_SHA),construction=construction)
    header=json.dumps(manifest,separators=(',',':'),ensure_ascii=True).encode()
    if len(header)>16*1024*1024:raise ValueError('Header exceeds browser cap')
    (out/'recipe.scsp').write_bytes(b'SCSP082\n'+struct.pack('<I',len(header))+header+payload.data)
    (out/'construction.json').write_text(json.dumps(construction,separators=(',',':'))+'\n')
    (out/'literals.bin').write_bytes(payload.data)
    # Audit and source-copy repair scan this storage buffer, never target ops.
    (out/'literal-ranges.tsv').write_text(f'0\t{len(payload.data)}\n')
    totals={}
    for row in payload.ranges:totals[row['owner']]=totals.get(row['owner'],0)+row['bytes']
    receipt=dict(status='candidate-audit-required',bundle_sha256=digest(out/'recipe.scsp'),
        literal_bytes=len(payload.data),literal_bytes_by_class=totals,table_recipes=len(rows),
        literal_bytes_by_owner=literal_owner_totals(construction),
        scan_view='entire contiguous stored payload',programs=len(programs),data_files=len(layout['files']),public_distribution=False)
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--types-cache',type=Path,default=ROOT/'build/patcher-types-v1')
    args=parser.parse_args();make(args.out,args.types_cache.resolve())
