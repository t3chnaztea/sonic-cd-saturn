#!/usr/bin/env python3
"""Replace audited 16-byte coincidences with exact input/output slice recipes.

This does not waive provenance or the literal scan. It creates another private
candidate that must pass a new independent audit. No residual or encoded game
payload is added. The old candidate and all original inputs remain read only.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import shutil
from recipe_tables import materialize
from recipe_provenance import literal_owner_totals

ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def repair_once(bundle,audit_dir,out,check_binding=True):
    args=argparse.Namespace(bundle=bundle,audit=audit_dir,out=out)
    out=out.resolve()
    if not out.is_relative_to(ROOT/'build')or out.exists():raise ValueError('Choose a new candidate directory under build/')
    receipt=json.loads((args.audit/'receipt.json').read_text())
    if check_binding and receipt['bundle_sha256']!=digest(args.bundle):raise ValueError('Audit belongs to another candidate')
    data=args.bundle.read_bytes();size=struct.unpack_from('<I',data,8)[0]
    manifest=json.loads(data[12:12+size]);payload=data[12+size:]
    construction=manifest['construction'];out.mkdir(parents=True)
    scanner=out/'literal-scan'
    subprocess.run(['clang','-O2','-Wall','-Wextra',str(ROOT/'tools/recipe_literal_scan.c'),'-o',str(scanner)],check=True)
    ranges=out/'contiguous-ranges.tsv';ranges.write_text(f'0\t{len(payload)}\n')
    with (out/'matches.log').open('x')as log:
        result=subprocess.run([str(scanner),str(args.bundle.resolve()),str(12+size),
            str((args.audit/'corpus.tsv').resolve()),str(ranges),'--all'],stdout=log,stderr=log)
    if result.returncode not in (0,1):raise ValueError('Complete literal scan failed')
    corpus=[]
    for line in (args.audit/'corpus.tsv').read_text().splitlines():
        offset,count,path=line.split('\t',2);corpus.append((int(offset),int(count),Path(path)))
    jp=(ROOT/'assets/private/sonic-cd-japan.cue').resolve()
    inputs={}
    for row in manifest['sources']:
        path=jp.parent/row['name']if row['role']=='jp'else ROOT/('build/retail'if row['role']=='us'else'assets/private')/row['name']
        inputs[path.resolve()]=row
    pins={};patterns={}
    for match in re.finditer(r'literal=(\d+) corpus=(\d+) offset=(\d+)',(out/'matches.log').read_text()):
        position,index,offset=map(int,match.groups());_,_,path=corpus[index-1];path=path.resolve()
        pattern=payload[position:position+16]
        with path.open('rb')as stream:stream.seek(offset);actual=stream.read(16)
        if pattern!=actual or len(pattern)!=16:raise ValueError('Literal witness changed')
        if path not in pins:pins[path]=(path.stat().st_size,digest(path))
        count,checksum=pins[path];original=inputs.get(path)
        if original:
            source=dict(codec='input-slice',role=original['role'],source_name=original['name'])
        else:
            try:name=path.relative_to(ROOT).as_posix()
            except ValueError:raise ValueError('Witness is outside the approved source corpus')from None
            if re.fullmatch(r'cd/(?:A|ZTR[01345678])\.BIN',name):
                # Reconstruct the witness from its converter tables. Never
                # read an unfinished program, including a program's own data.
                choices=[]
                for n in range(16):
                    base=next(((i,t)for i,t in enumerate(construction['tables'])if t['codec']in ('initializer','copy','cstring','source-text-string')
                        and t['file']==name and t['offset']<=offset+n<t['offset']+t['bytes']),None)
                    if base:
                        i,t=base;choices.append((dict(codec='table-slice',source_table=i,
                            source_bytes=t['bytes'],source_sha256=t['sha256']),offset+n-t['offset']))
                    elif pattern[n]==0:choices.append((dict(codec='zero'),n))
                    else:raise ValueError('Program witness has no certified table producer')
                patterns.setdefault(pattern,choices);continue
            if not name.startswith(('assets/generated/','cd/')):continue
            source=dict(codec='output-slice',source=name)
        source.update(source_bytes=count,source_sha256=checksum)
        patterns.setdefault(pattern,[(source,offset+n)for n in range(16)])
    assignments=[None]*len(payload);occurrences=0
    for pattern,choices in patterns.items():
        # A scan witness can cross adjacent ownership records. Rewrite every
        # occurrence, including those seams; each target operation retains its
        # own source proof and is checked again by the independent audit.
        at=payload.find(pattern)
        while at>=0:
            occurrences+=1
            for n in range(16):
                if assignments[at+n]is None:assignments[at+n]=choices[n]
            at=payload.find(pattern,at+1)
    old_ledger=construction['literal_ranges'];new_payload=bytearray();new_ledger=[];added=0
    def rewrite(row,name):
        nonlocal added
        new_ops=[];target=0
        for op in row['ops']:
            if op['kind']!='literal':new_ops.append(op);target+=op['length'];continue
            start,end=op['offset'],op['offset']+op['length'];at=start
            owner=next(r for r in old_ledger if r['offset']==start and r['bytes']==op['length'])
            while at<end:
                assignment=assignments[at];stop=at+1
                while stop<end:
                    following=assignments[stop]
                    if assignment is None:
                        if following is not None:break
                    elif following is None or following[0]!=assignment[0]or following[1]!=assignment[1]+stop-at:break
                    stop+=1
                chunk=payload[at:stop]
                if assignment is None:
                    offset=len(new_payload);new_payload.extend(chunk)
                    new_ops.append(dict(kind='literal',offset=offset,length=len(chunk)))
                    new_ledger.append(dict(offset=offset,bytes=len(chunk),owner=owner['owner'],evidence=owner['evidence']))
                else:
                    source,source_offset=assignment
                    if source['codec']=='zero':
                        new_ops.append(dict(kind='zero',length=len(chunk)));added+=len(chunk);at=stop;continue
                    if name=='program/ponesound.bin'and source['codec']=='output-slice'and source['source']!='assets/generated/sound-driver.bin':
                        raise ValueError('Firmware witness must be available before its converter')
                    table=dict(source,file=name,offset=target+at-start,bytes=len(chunk),source_offset=source_offset,
                        sha256=hashlib.sha256(chunk).hexdigest())
                    if materialize(table,ROOT,construction['tables'])!=chunk:raise ValueError('Source-copy proof failed')
                    index=len(construction['tables']);construction['tables'].append(table)
                    new_ops.append(dict(kind='derive',table=index,offset=0,length=len(chunk)));added+=len(chunk)
                at=stop
            target+=op['length']
        row['ops']=new_ops
    for name,row in construction['programs'].items():rewrite(row,name)
    rewrite(construction['iso'],'build/browser/image.iso')
    for name,row in construction['metadata'].items():rewrite(row,name)
    rewrite(construction['firmware'],'program/ponesound.bin')
    construction['payload_sha256']=hashlib.sha256(new_payload).hexdigest();construction['literal_ranges']=new_ledger
    # A split operation inherits its original ownership proof. Store that
    # proof once, rather than repeating hundreds of symbol records for every
    # small source slice. Only the evidence references are deduplicated.
    old_evidence=construction.get('literal_evidence',[]);evidence=[];evidence_ids={}
    for row in new_ledger:
        item=old_evidence[row['evidence']]if isinstance(row['evidence'],int)else row['evidence']
        key=json.dumps(item,sort_keys=True,separators=(',',':'))
        if key not in evidence_ids:evidence_ids[key]=len(evidence);evidence.append(item)
        row['evidence']=evidence_ids[key]
    construction['schema']=2;construction['literal_evidence']=evidence
    header=json.dumps(manifest,separators=(',',':'),ensure_ascii=True).encode()
    (out/'header-stats.json').write_text(json.dumps(dict(bytes=len(header),literal_ranges=len(new_ledger),
        evidence_records=len(evidence),table_recipes=len(construction['tables'])))+'\n')
    if len(header)>16*1024*1024:raise ValueError('Header exceeds browser cap')
    (out/'recipe.scsp').write_bytes(b'SCSP082\n'+struct.pack('<I',len(header))+header+new_payload)
    (out/'construction.json').write_text(json.dumps(construction,separators=(',',':'))+'\n');(out/'literals.bin').write_bytes(new_payload)
    totals={}
    for row in new_ledger:totals[row['owner']]=totals.get(row['owner'],0)+row['bytes']
    result=dict(status='candidate-audit-required',bundle_sha256=digest(out/'recipe.scsp'),
        literal_bytes=len(new_payload),literal_bytes_by_class=totals,source_copied_bytes=added,
        literal_bytes_by_owner=literal_owner_totals(construction),
        source_patterns=len(patterns),matched_payload_windows=occurrences,matched_runs=len(re.findall(r'literal=\d+', (out/'matches.log').read_text())),
        scan_view='entire contiguous stored payload',table_recipes=len(construction['tables']),public_distribution=False)
    final_ranges=out/'literal-ranges.tsv';final_ranges.write_text(f'0\t{len(new_payload)}\n')
    verified=subprocess.run([str(scanner),str(out/'recipe.scsp'),str(12+len(header)),
        str((args.audit/'corpus.tsv').resolve()),str(final_ranges),'--all'],capture_output=True,text=True)
    (out/'verification.log').write_text(verified.stdout+verified.stderr)
    if verified.returncode not in (0,1):raise ValueError('Compacted payload scan failed')
    result['remaining_patterns']=len(re.findall(r'literal=\d+',verified.stdout))
    (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle',type=Path);parser.add_argument('--audit',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args();out=args.out.resolve()
    if not out.is_relative_to(ROOT/'build')or out.exists():raise ValueError('Choose a new candidate directory under build/')
    out.mkdir(parents=True);bundle=args.bundle;passes=[]
    for index in range(1,17):
        directory=out/f'pass-{index}'
        result=repair_once(bundle,args.audit,directory,check_binding=index==1);passes.append(result)
        if not result['remaining_patterns']:break
        if not result['source_copied_bytes']:raise ValueError('Contiguous source repair made no progress')
        bundle=directory/'recipe.scsp'
    else:raise ValueError('Contiguous source repair exceeded 16 passes; candidate not distributable')
    for name in ('recipe.scsp','construction.json','literals.bin','literal-ranges.tsv','header-stats.json','verification.log'):
        shutil.copyfile(directory/name,out/name)
    result=dict(result,source_copied_bytes=sum(row['source_copied_bytes']for row in passes),
        matched_runs=sum(row['matched_runs']for row in passes),matched_payload_windows=sum(row['matched_payload_windows']for row in passes),source_patterns=sum(row['source_patterns']for row in passes),
        repair_passes=len(passes))
    (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
