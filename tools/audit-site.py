#!/usr/bin/env python3
"""Offline, content-based ownership scan of every file in a prepared site.

Only exact upstream hashes in the checkout's pinned runtime lock may skip the
scan. All other files, including recipe JSON and locally built WASM, are scanned.
The recipe payload has no generic-pattern exemptions.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def classify(data):
    """Generic byte properties, independent of filenames and corpus witnesses."""
    if all(data[i]==data[i%2]for i in range(16)):
        return 'fill','Single-byte fill' if len(set(data))==1 else 'Repeating two-byte fill'
    printable=lambda b:32<=b<=126 or b in (9,10,13)
    if all(printable(b)for b in data):return 'ASCII text','Sixteen ASCII text bytes'
    if all(b==0 or printable(b)for b in data)and sum(printable(b)for b in data)>=8:
        return 'ASCII text','ASCII text with NUL padding or separators'
    for width in (1,2,4):
        for order in ('little','big')if width>1 else ('little',):
            values=[int.from_bytes(data[i:i+width],order)for i in range(0,16,width)]
            delta=values[1]-values[0]
            if delta and all(b-a==delta for a,b in zip(values,values[1:])):
                return 'generic run',f'Arithmetic ramp of {width}-byte {order}-endian unsigned integers; step {delta}'
    return 'UNEXPLAINED','No generic byte property or reviewed source explanation'


def audit(site,audit_dir,work,upstream_files=()):
    site=site.resolve();work=work.resolve()
    if not site.is_dir()or not site.is_relative_to(ROOT/'build'):raise ValueError('Use a local built site under build/')
    if not work.is_relative_to(ROOT/'build')or work.exists():raise ValueError('Choose a new work directory under build/')
    prior=json.loads((audit_dir/'receipt.json').read_text());corpus=audit_dir/'corpus.tsv'
    if prior.get('status')!='PASS'or prior.get('policy')!='recipe-no-initialized-data-v5':raise ValueError('A passing contiguous binary-corpus recipe audit is required')
    if digest(corpus)!=prior.get('corpus_manifest_sha256'):raise ValueError('Binary corpus manifest changed')
    work.mkdir(parents=True)
    lock_path=ROOT/'web/patcher/vendor/runtime-lock.json'
    pins={row['path']:row for row in json.loads(lock_path.read_text())['files']}
    upstream={name:row['upstream_sha256']for name,row in pins.items()if row.get('upstream_sha256')}
    originals={}
    for path in upstream_files:
        sha=digest(path)
        if sha not in upstream.values():raise ValueError('Upstream comparison file has no pinned upstream hash')
        originals[sha]=path.read_bytes()
    unchanged_proofs={}

    corpus_rows=[]
    for line in corpus.read_text().splitlines():
        start,count,path=line.split('\t',2);corpus_rows.append((int(start),int(count),Path(path)))
    scanner=work/'literal-scan'
    subprocess.run(['clang','-O2','-Wall','-Wextra',str(ROOT/'tools/recipe_literal_scan.c'),'-o',str(scanner)],check=True)
    files=[];pending=[]
    for path in sorted(site.rglob('*')):
        if path.is_symlink():raise ValueError('Site symlinks are not allowed')
        if not path.is_file():continue
        name=path.relative_to(site).as_posix();sha=digest(path)
        row=dict(file=name,bytes=path.stat().st_size,sha256=sha)
        if upstream.get(name)==sha:row['status']='upstream-identical, not scanned for ownership'
        else:
            row['status']='scanned';pending.append((path,row))
            pin=pins.get(name,{})
            original=originals.get(pin.get('upstream_sha256'))
            if original is not None and sha==pin.get('sha256'):
                data=path.read_bytes()
                if len(data)!=len(original):raise ValueError('Patched runtime changed its upstream byte extent')
                row['upstream_comparison_sha256']=pin['upstream_sha256']
                # This is not a scan exemption. Only individual matching
                # windows unchanged at the same upstream offset can use it.
                unchanged_proofs[name]=(original,pin['upstream_sha256'])
        files.append(row)
    matches=[];batches=[];current=[];size=0
    for path,row in pending:
        if row['bytes']>16*1024*1024:raise ValueError('Unpinned site file exceeds scanner batch limit')
        if size+row['bytes']>16*1024*1024:batches.append(current);current=[];size=0
        current.append((path,row));size+=row['bytes']
    if current:batches.append(current)
    recipe=site/'web/patcher/recipe.scsp'
    if digest(recipe)!=prior['bundle_sha256']:raise ValueError('Site recipe differs from audited recipe')
    recipe_data=recipe.read_bytes()
    if recipe_data[:8]!=b'SCSP082\n':raise ValueError('Bad recipe signature')
    payload_start=12+struct.unpack_from('<I',recipe_data,8)[0]
    for number,batch in enumerate(batches):
        joined=bytearray();ranges=[]
        for path,row in batch:
            data=path.read_bytes();ranges.append((len(joined),len(data)));joined.extend(data)
        query=work/f'query-{number}.bin';query.write_bytes(joined)
        ranges_file=work/f'ranges-{number}.tsv';ranges_file.write_text(''.join(f'{a}\t{b}\n'for a,b in ranges))
        result=subprocess.run([str(scanner),str(query),'0',str(corpus.resolve()),str(ranges_file),'--all'],capture_output=True,text=True)
        (work/f'scan-{number}.log').write_text(result.stdout+result.stderr)
        if result.returncode not in (0,1):raise ValueError('Site scanner failed')
        patterns={}
        for hit in re.finditer(r'literal=(\d+) corpus=(\d+) offset=(\d+)',result.stdout):
            position,index,offset=map(int,hit.groups());pattern=bytes(joined[position:position+16]);source=corpus_rows[index-1][2]
            with source.open('rb')as stream:stream.seek(offset);witness=stream.read(16)
            if witness!=pattern:raise ValueError('Corpus witness changed')
            patterns[pattern]=(source,offset)
        for path,row in batch:
            data=path.read_bytes()
            for pattern,(source,offset)in patterns.items():
                position=data.find(pattern)
                while position>=0:
                    category,explanation=classify(pattern)
                    proof=unchanged_proofs.get(row['file']);source_proof={}
                    if category=='UNEXPLAINED'and proof is not None and proof[0][position:position+16]==pattern:
                        category='generic run'
                        explanation='Unchanged upstream interpreter/code or lookup-data run; exact same offset in the SHA-256-pinned upstream runtime; outside all patched bytes'
                        source_proof=dict(upstream_sha256=proof[1],upstream_offset=position)
                    inside=path==recipe and position+16>payload_start
                    matches.append(dict(file=row['file'],offset=position,hex=pattern.hex(),
                        corpus_file=str(source),corpus_offset=offset,classification=category,
                        explanation=explanation,recipe_literal_payload=inside,**source_proof))
                    position=data.find(pattern,position+1)
    counts=Counter(row['classification']for row in matches)
    payload_matches=sum(row['recipe_literal_payload']for row in matches)
    passed=not counts['UNEXPLAINED']and not payload_matches
    receipt=dict(status='PASS'if passed else'FAIL',policy='site-binary-corpus-v1',
        recipe_sha256=prior['bundle_sha256'],runtime_lock_sha256=digest(lock_path),
        corpus_manifest_sha256=digest(corpus),corpus_definition=prior['corpus_definition'],
        scanned_files=len(pending),upstream_identical_files=len(files)-len(pending),
        matches=len(matches),matches_by_class={name:counts[name]for name in ('fill','ASCII text','generic run','UNEXPLAINED')},recipe_payload_matches=payload_matches,
        audit_sources={name:digest(ROOT/'tools'/name)for name in ('audit-site.py','recipe_literal_scan.c')},
        upstream_proven_matches=sum('upstream_sha256'in row for row in matches),
        files=files,match_records=sorted(matches,key=lambda row:(row['file'],row['offset'])))
    (work/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(f"{'PASS'if passed else'FAIL'}: site ownership audit; {len(pending)} scanned files; {len(files)-len(pending)} upstream-identical; {len(matches)} matches; {counts['UNEXPLAINED']} UNEXPLAINED; {payload_matches} recipe payload matches")
    return 0 if passed else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('site',type=Path);parser.add_argument('--audit',type=Path,required=True);parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--upstream',type=Path,action='append',default=[],help='Local original runtime file; accepted only by pinned upstream SHA-256, never by filename')
    args=parser.parse_args()
    try:raise SystemExit(audit(args.site,args.audit,args.work,args.upstream))
    except (ValueError,OSError,KeyError)as error:raise SystemExit('FAIL: site ownership audit; '+str(error))
