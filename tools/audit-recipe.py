#!/usr/bin/env python3
"""Audit a format 2 candidate against fresh ELF/source and private inputs.

The receipt is local evidence. No private input names or bytes are printed.
Compiled program files contribute their DERIVE data ranges to the corpus;
their approved program ranges are excluded to avoid scanning literals against
the identical copy in A.BIN itself. Other CD game files and binary generated assets
are scanned in full. The entire stored payload is one contiguous scan range. A nonzero exit never authorizes distribution.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
from recipe_provenance import classify,complete,literal_owner_totals,FORBIDDEN_LITERAL_OWNERS
from recipe_tables import build as build_tables,materialize
from recipe_iso import catalog,boot_blobs,boot_tables
from recipe_elf import Elf
from browser_package import assemble

ROOT=Path(__file__).resolve().parents[1]
POLICY='recipe-no-initialized-data-v5'
AUDIT_SOURCES=['audit-recipe.py','recipe_elf.py','recipe_provenance.py','recipe_types.py',
               'recipe_values.py','recipe_tables.py','recipe_source.py','recipe_dwarf.py','recipe_iso.py','recipe_literal_scan.c']


def keys(value,expected):
    if not isinstance(value,dict)or set(value)!=set(expected.split()):raise ValueError('Unexpected recipe metadata fields')


def digest(path):
    with path.open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


BINARY_CORPUS_DEFINITION={
    'inputs':'Every pinned user disc BIN (all JP tracks and US BIN) and US BIOS; no CUE text',
    'cd':'All cd/ files except case-insensitive .TXT; compiled programs contribute only non-literal provenance ranges',
    'generated':'assets/generated files excluding text; .inc/.h/.json/.c/.txt are text, as are UTF-8 files without binary controls',
    'match':'Every exact 16-byte window; single-byte and two-byte fills included',
    'payload':'One contiguous buffer as stored after the SCSP JSON header; operation, symbol and ownership boundaries ignored'}


def generated_text(path):
    if path.suffix.lower() in ('.inc','.h','.json','.c','.txt'):return True
    data=path.read_bytes()
    try:data.decode('utf-8')
    except UnicodeDecodeError:return False
    return all((byte>=32 and byte!=127)or byte in (9,10,12,13)for byte in data)


def literal_scan_ranges(payload_bytes):
    """Storage adjacency, including across derive/zero target operations."""
    return [(0,payload_bytes)]


def audit(bundle,work):
    work=work.resolve()
    if not work.is_relative_to(ROOT/'build')or work.exists():raise ValueError('Choose a new audit directory under build/')
    work.mkdir(parents=True)
    with bundle.open('rb')as stream:
        if stream.read(8)!=b'SCSP082\n':raise ValueError('Invalid bundle signature')
        count=struct.unpack('<I',stream.read(4))[0]
        if not 0<count<=16*1024*1024:raise ValueError('Invalid header size')
        manifest=json.loads(stream.read(count));payload=stream.read()
    if manifest.get('format')!=2 or manifest.get('version')!='V0.083':raise ValueError('Unsupported recipe')
    keys(manifest,'format version sources derivations ops target construction')
    target=manifest['target']
    keys(target,'bytes sha256 cue cue_sha256')
    if target['bytes']!=759063312:raise ValueError('Accepted image length differs')
    if target['sha256']!='8ef64ccd07739b3e6e00fd424409000b54d629c6470e1f5865cc3cec4d703d86' or target['cue_sha256']!='10f35a87674de372bc4b217a4e877f5321aa683afda91eab18df2df331d04337':raise ValueError('Accepted pins differ')
    if hashlib.sha256(target['cue'].encode()).hexdigest()!=target['cue_sha256']:raise ValueError('CUE bytes differ')
    construction=manifest['construction']
    fields='schema programs metadata tables iso iso_layout boot_blobs data_track firmware linked_symbols elf_sha256 us_iso payload_sha256 literal_ranges'
    if construction.get('schema')==2:fields+=' literal_evidence'
    keys(construction,fields)
    if construction['schema']not in (1,2):raise ValueError('Unsupported construction schema')
    if hashlib.sha256(payload).hexdigest()!=construction['payload_sha256']:raise ValueError('Literal payload checksum failed')
    owners=literal_owner_totals(construction)
    code_objects=[]
    for span in construction['literal_ranges']:
        evidence=span['evidence']
        if isinstance(evidence,int):evidence=construction['literal_evidence'][evidence]
        if span['owner']!='program':continue
        symbol=evidence['provenance'][0]
        if symbol['owner']not in ('compiled-control-table','compiled-function-constant'):continue
        name=symbol['symbol']
        if symbol['owner']=='compiled-function-constant':
            reason='Unnamed instruction constant: certified R_SH_DIR32 references inside the attributed functions; no C data-object initializer'
        elif name.startswith('_CSWTCH.'):
            reason='GCC switch-conversion artifact: compiler-generated symbol containing a dot, not a C variable; source switch/if sites and unit hashes certify code lowering'
        elif name=='<compiler-anonymous-rodata>':
            reason='Anonymous SH LTO control-flow/constant contribution certified by link-map placement and code/source references; all named initialized data objects take precedence and derive'
        else:raise ValueError('Uncertified compiler code constant: '+name)
        code_objects.append(dict(payload_offset=span['offset'],bytes=span['bytes'],file=evidence['file'],
            target_offset=evidence['offset'],symbol=name,owner=symbol['owner'],reason=reason,evidence=symbol['evidence']))
    cache=work/'types';cache.mkdir()
    provenance=classify(ROOT,cache)
    tables=build_tables(ROOT,cache,provenance)
    provenance=complete(ROOT,provenance,tables)
    if tables['failures']or any(row['unresolved_bytes']for row in provenance['programs'].values()):raise ValueError('Fresh provenance is incomplete')
    iso_image=(ROOT/'dist/iso/sonic-cd-saturn-prototype.iso').read_bytes();layout=catalog(iso_image)
    boots=boot_blobs(ROOT,iso_image)
    if construction['boot_blobs']!=boots:raise ValueError('Boot/security blob provenance differs')
    certified=tables['initializers']+tables['copies']+tables['strings']+boot_tables(boots);expected=construction['tables']
    if expected[:len(certified)]!=certified:raise ValueError('Table recipes differ from fresh certification')
    input_pins={(r['role'],r['name']):r for r in manifest['sources']}
    slice_targets=set(provenance['programs'])|set(construction['metadata'])|{'build/browser/image.iso','program/ponesound.bin'}
    for row in expected[len(certified):]:
        common='codec file offset bytes source_offset source_bytes source_sha256 sha256'
        if row['codec']=='input-slice':
            keys(row,common+' role source_name')
            pin=input_pins.get((row['role'],row['source_name']))
            if pin is None or pin['bytes']!=row['source_bytes']or pin['sha256']!=row['source_sha256']:raise ValueError('Unpinned source slice')
        elif row['codec']=='output-slice':keys(row,common+' source')
        elif row['codec']=='table-slice':
            keys(row,common+' source_table')
            if type(row['source_table'])is not int or not 0<=row['source_table']<len(certified):raise ValueError('Uncertified/circular source table')
        else:raise ValueError('Unapproved additional table codec')
        if row['file']not in slice_targets:raise ValueError('Unknown source-slice target')
        if any(type(row[k])is not int or row[k]<0 for k in ('offset','bytes','source_offset','source_bytes')):raise ValueError('Invalid source-slice range')
        materialize(row,ROOT,expected)
    if construction['elf_sha256']!=provenance['elf_sha256']:raise ValueError('Linked program pin differs')
    elf=Elf(ROOT/'build/saturn/sonic-cd-saturn-prototype.elf')
    linked={s['name']:s['value']for s in elf.symbols if s['name']in ('__sector','___end')}
    if construction['linked_symbols']!=linked:raise ValueError('Link contract differs from ELF')
    us_iso=ROOT/'build/retail/sonic.iso'
    if construction['us_iso']!=dict(name=us_iso.name,bytes=us_iso.stat().st_size,sha256=digest(us_iso)):raise ValueError('U.S. data-track contract differs')
    literal_mask=bytearray(len(payload));totals={};literal_ranges=[];used_slices=set()
    def literal(op,owner):
        offset=op['offset'];length=op['length']
        if not isinstance(offset,int)or not isinstance(length,int)or min(offset,length)<0 or offset+length>len(payload):raise ValueError('Literal range exceeds payload')
        if any(literal_mask[offset:offset+length]):raise ValueError('Literal ranges overlap')
        literal_mask[offset:offset+length]=bytes([1])*length
        literal_ranges.append((offset,length,owner))
        totals[owner]=totals.get(owner,0)+length
    def check_operations(row,image,permitted,owner,derive):
        keys(row,'bytes sha256 ops')
        at=0
        for op in row['ops']:
            n=op['length']
            if not isinstance(n,int)or n<0 or at+n>len(image):raise ValueError('Construction bounds failed')
            if op['kind']=='literal':
                keys(op,'kind offset length')
                if not all(permitted[at:at+n]):raise ValueError('Literal lies in a generated or unclassified data range')
                literal(op,owner)
                if payload[op['offset']:op['offset']+n]!=image[at:at+n]:raise ValueError('Literal bytes differ from accepted construction')
            elif op['kind']=='zero':
                keys(op,'kind length')
                if any(image[at:at+n]):raise ValueError('Zero operation overwrites nonzero bytes')
            elif op['kind']=='derive':derive(op,at,n)
            else:raise ValueError('Unknown construction operation')
            at+=n
        if at!=len(image)or row['bytes']!=len(image)or row['sha256']!=hashlib.sha256(image).hexdigest():raise ValueError('Construction extent/checksum mismatch')
    if set(construction['programs'])!=set(provenance['programs']):raise ValueError('Program catalog differs')
    for name,row in construction['programs'].items():
        p=provenance['programs'][name];image=(ROOT/name).read_bytes();permitted=bytearray(len(image))
        for r in p['ranges']:
            if r['kind']=='literal':permitted[r['offset']:r['offset']+r['bytes']]=bytes([1])*r['bytes']
        def table(op,at,n):
            keys(op,'kind table offset length')
            if type(op['table'])is not int or not 0<=op['table']<len(expected)or type(op['offset'])is not int or op['offset']<0:raise ValueError('Invalid table index/range')
            t=expected[op['table']]
            if op['table']>=len(certified):used_slices.add(op['table'])
            if t['file']!=name or t['offset']+op['offset']!=at or op['offset']+n>t['bytes']:raise ValueError('Table range differs from its linked symbol')
            data=materialize(t,ROOT,expected)[op['offset']:op['offset']+n]
            if data!=image[at:at+n]:raise ValueError('Table serialization differs')
        check_operations(row,image,permitted,'program',table)
    if layout!=construction['iso_layout']:raise ValueError('ISO file layout differs')
    permitted=bytearray([1])*len(iso_image);by_offset={}
    for row in layout['files']:
        permitted[row['offset']:row['offset']+row['bytes']]=bytes(row['bytes']);by_offset[row['offset']]=row
    for row in boots:permitted[row['offset']:row['offset']+row['bytes']]=bytes(row['bytes'])
    def source_slice(op,at,n,name,image):
        keys(op,'kind table offset length')
        if type(op['table'])is not int or not 0<=op['table']<len(expected):raise ValueError('Invalid structure source slice')
        row=expected[op['table']]
        if op['table']<len(certified)and row['codec']!='reference-slice':raise ValueError('Invalid structure source table')
        if op['table']>=len(certified):used_slices.add(op['table'])
        if row['file']!=name or row['offset']+op['offset']!=at or op['offset']<0 or op['offset']+n>row['bytes']:raise ValueError('Source slice target differs')
        if materialize(row,ROOT,expected)[op['offset']:op['offset']+n]!=image[at:at+n]:raise ValueError('Source-sliced bytes differ')
    def file(op,at,n):
        if 'table'in op:
            if expected[op['table']]['codec']!='reference-slice'and not all(permitted[at:at+n]):raise ValueError('Structure copy overlaps an ISO file/boot blob')
            source_slice(op,at,n,'build/browser/image.iso',iso_image);return
        keys(op,'kind file offset length')
        if op.get('offset')!=0 or op['file']!=by_offset.get(at)or op['file']['bytes']!=n:raise ValueError('ISO derive operation differs from directory extent')
        path=ROOT/op['file']['source']
        if path.stat().st_size!=n or digest(path)!=op['file']['sha256']:raise ValueError('CD source differs')
    check_operations(construction['iso'],iso_image,permitted,'ISO-structure',file)
    for name,row in construction['metadata'].items():
        if not re.fullmatch(r'cd/[A-Z0-9_]+\.TXT',name):raise ValueError('Unapproved project metadata file')
        data=(ROOT/name).read_bytes()
        check_operations(row,data,bytes([1])*len(data),'project-CD-text',lambda op,at,n:source_slice(op,at,n,name,data))
    firmware=(ROOT/'build/sound-driver/driver.bin').read_bytes()
    if hashlib.sha256(firmware).hexdigest()!='ae1f243ab3b9be9ea66dc86904111c42feb8b9817229678f5433c41b80735c6a':raise ValueError('PoneSound program pin differs')
    def firmware_slice(op,at,n):
        row=expected[op['table']]
        if row['codec']=='output-slice'and row['source']!='assets/generated/sound-driver.bin':raise ValueError('Firmware needs an earlier converter output')
        source_slice(op,at,n,'program/ponesound.bin',firmware)
    check_operations(construction['firmware'],firmware,bytes([1])*len(firmware),'PoneSound-program',firmware_slice)
    if not all(literal_mask):raise ValueError('Unclassified/unused payload bytes')
    if sum(r['bytes']for r in construction['literal_ranges'])!=len(payload):raise ValueError('Literal ownership ledger size differs')
    actual={(a,b,owner)for a,b,owner in literal_ranges}
    ledger=set();used_evidence=set()
    for row in construction['literal_ranges']:
        keys(row,'offset bytes owner evidence');ledger.add((row['offset'],row['bytes'],row['owner']))
        evidence=row['evidence']
        if construction['schema']==2:
            if type(evidence)is not int or not 0<=evidence<len(construction['literal_evidence']):raise ValueError('Invalid literal evidence reference')
            used_evidence.add(evidence)
            evidence=construction['literal_evidence'][evidence]
        if row['owner']=='program':
            keys(evidence,'file offset provenance')
            if evidence['file']not in provenance['programs']or type(evidence['offset'])is not int:raise ValueError('Invalid program literal provenance')
            approved=provenance['programs'][evidence['file']]['symbols']
            # Evidence rows for one symbol have no defined order between runs.
            def canonical(item):
                rows=item.get('evidence')
                if type(rows)is not list:return json.dumps(item,sort_keys=True)
                return json.dumps(dict(item,evidence=sorted(rows,key=lambda row:json.dumps(row,sort_keys=True))),sort_keys=True)
            known={canonical(item)for item in approved}
            if any(canonical(item)not in known or item['kind']!='literal'for item in evidence['provenance']):raise ValueError('Unknown program literal evidence')
        elif row['owner']=='ISO-structure':
            keys(evidence,'source offset bytes')
            if evidence['source']!='tools/recipe_iso.py' or any(type(evidence[k])is not int or evidence[k]<0 for k in ('offset','bytes')):raise ValueError('Invalid ISO structure evidence')
        elif row['owner']=='project-CD-text':
            keys(evidence,'file source')
            if evidence['source']!=evidence['file']:raise ValueError('Invalid CD source evidence')
            if evidence['file']not in construction['metadata']:raise ValueError('Invalid CD text evidence')
        elif row['owner']=='PoneSound-program':
            if evidence!=dict(source='tools/ponesound/driver.c',source_sha256=digest(ROOT/'tools/ponesound/driver.c'),artifact='build/sound-driver/driver.bin'):raise ValueError('Invalid firmware evidence')
        else:raise ValueError('Unapproved literal class')
    if actual!=ledger or len(ledger)!=len(literal_ranges):raise ValueError('Literal ledger differs from verified operations')
    if construction['schema']==2 and used_evidence!=set(range(len(construction['literal_evidence']))):raise ValueError('Unused literal evidence records')
    if used_slices!=set(range(len(certified),len(expected))):raise ValueError('Unused source-slice records')
    jp=(ROOT/'assets/private/sonic-cd-japan.cue').resolve()
    local={('jp',jp.name):jp,('us','sonic.bin'):ROOT/'build/retail/sonic.bin',('us','sonic.cue'):ROOT/'build/retail/sonic.cue',('bios','bios_CD_U.bin'):ROOT/'assets/private/bios_CD_U.bin'}
    for name in re.findall(r'^\s*FILE "([^"\r\n]+)" BINARY\s*$',jp.read_text(encoding='utf-8-sig'),re.M):
        if '/'in name or '\\'in name:raise ValueError('Unsafe JP source path')
        local[('jp',name)]=jp.parent/name
    if {(r['role'],r['name'])for r in manifest['sources']}!=set(local):raise ValueError('Input catalog differs')
    corpus=[]
    for row in manifest['sources']:
        keys(row,'role name bytes sha256')
        path=local[(row['role'],row['name'])]
        if path.stat().st_size!=row['bytes']or digest(path)!=row['sha256']:raise ValueError('Original input pin differs')
        if row['role']=='bios' or path.suffix.lower()=='.bin':corpus.append((0,row['bytes'],path))
    # Final operations must identify only the known generated track, zero
    # pregap, native-compared music or checked user files. No spare metadata
    # fields may carry hidden payloads.
    approved_derived={
        'build/browser/data.raw':construction['data_track'],
        'build/browser/pregap.raw':dict(bytes=150*2352,sha256=hashlib.sha256(bytes(150*2352)).hexdigest())}
    keys(construction['data_track'],'bytes sha256')
    accepted_bin=ROOT/'dist/sonic-cd-saturn-prototype.bin'
    if accepted_bin.stat().st_size!=target['bytes']or digest(accepted_bin)!=target['sha256']:raise ValueError('Native accepted BIN changed')
    data_bytes=len(iso_image)//2048*2352;checksum=hashlib.sha256()
    with accepted_bin.open('rb')as stream:
        remaining=data_bytes
        while remaining:
            block=stream.read(min(1024*1024,remaining));checksum.update(block);remaining-=len(block)
    if construction['data_track']!=dict(bytes=data_bytes,sha256=checksum.hexdigest()):raise ValueError('Data-track pin differs')
    for index in range(41):
        name=f'assets/generated/music{index}.raw';path=ROOT/name
        approved_derived[name]=dict(bytes=path.stat().st_size,sha256=digest(path))
    derivations={}
    for row in manifest['derivations']:
        keys(row,'name bytes sha256')
        if row['name']in derivations or approved_derived.get(row['name'])!={k:row[k]for k in ('bytes','sha256')}:raise ValueError('Invalid final derivation')
        derivations[row['name']]=row
    total=0;final_hash=hashlib.sha256()
    for op in manifest['ops']:
        if op['kind']=='source':
            keys(op,'kind index offset length')
            if type(op['index'])is not int or not 0<=op['index']<len(manifest['sources']):raise ValueError('Invalid final source')
            limit=manifest['sources'][op['index']]['bytes']
        elif op['kind']=='derive':
            keys(op,'kind file offset length')
            if op['file']not in derivations:raise ValueError('Missing final derivation')
            limit=derivations[op['file']]['bytes']
        else:raise ValueError('Unexpected final operation')
        if any(type(op[k])is not int or op[k]<0 for k in ('offset','length'))or op['offset']+op['length']>limit:raise ValueError('Invalid final range')
        total+=op['length']
        remaining=op['length']
        if op['kind']=='derive'and op['file']=='build/browser/pregap.raw':
            final_hash.update(bytes(remaining));continue
        if op['kind']=='source':
            source=manifest['sources'][op['index']];path=local[(source['role'],source['name'])]
        else:path=accepted_bin if op['file']=='build/browser/data.raw'else ROOT/op['file']
        with path.open('rb')as stream:
            stream.seek(op['offset'])
            while remaining:
                block=stream.read(min(1024*1024,remaining))
                if not block:raise ValueError('Final operation source is truncated')
                final_hash.update(block);remaining-=len(block)
    if total!=target['bytes']:raise ValueError('Final operation total differs')
    if final_hash.hexdigest()!=target['sha256']:raise ValueError('Final native-compared recipe bytes differ')
    for file,p in provenance['programs'].items():
        for r in p['ranges']:
            if r['kind']!='literal':corpus.append((r['offset'],r['bytes'],ROOT/file))
    for path in sorted((ROOT/'cd').rglob('*')):
        if path.is_file()and path.relative_to(ROOT).as_posix()not in provenance['programs']and path.suffix.lower()!='.txt':corpus.append((0,path.stat().st_size,path))
    for path in sorted((ROOT/'assets/generated').rglob('*')):
        if path.is_file()and not generated_text(path):corpus.append((0,path.stat().st_size,path))
    corpus_file=work/'corpus.tsv';corpus_file.write_text(''.join(f'{a}\t{b}\t{p}\n'for a,b,p in corpus))
    ranges_file=work/'literal-ranges.tsv';ranges_file.write_text(''.join(f'{a}\t{b}\n'for a,b in literal_scan_ranges(len(payload))))
    scanner=work/'literal-scan'
    subprocess.run(['clang','-O2','-Wall','-Wextra',str(ROOT/'tools/recipe_literal_scan.c'),'-o',str(scanner)],check=True)
    result=subprocess.run([str(scanner),str(bundle.resolve()),str(count+12),str(corpus_file),str(ranges_file),'--all'],capture_output=True,text=True)
    (work/'literal-scan.log').write_text(result.stdout+result.stderr)
    receipt=dict(status='PASS'if result.returncode==0 else'FAIL',bundle_sha256=digest(bundle),literal_bytes=len(payload),
        literal_bytes_by_class=totals,literal_bytes_by_owner=owners,
        forbidden_literal_owner_bytes={owner:owners.get(owner,0)for owner in sorted(FORBIDDEN_LITERAL_OWNERS)},
        corpus_bytes=sum(n for _,n,_ in corpus),corpus_definition=BINARY_CORPUS_DEFINITION,
        corpus_manifest_sha256=digest(corpus_file),literal_scan_ranges=literal_scan_ranges(len(payload)),
        table_recipes=len(expected),
        compiler_code_literal_ranges=code_objects,initialized_data_literals=0,source_data_objects=sum(s['owner']in ('project-source-initializer','dependency-source-initializer')for p in provenance['programs'].values()for s in p['symbols']),initialized_data_statement='initialized data literals: 0',
        unresolved_program_bytes=0,scanner_exit_code=result.returncode,live_reference_fetch_tested=False,
        policy=POLICY,audit_sources={name:digest(ROOT/'tools'/name)for name in AUDIT_SOURCES})
    (work/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(result.stdout.strip())
    print(f"{'PASS'if result.returncode==0 else'FAIL'}: recipe audit; {len(payload)} literal bytes; "+json.dumps(totals,sort_keys=True))
    return 0 if result.returncode==0 else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle',type=Path);parser.add_argument('--work',type=Path,required=True)
    args=parser.parse_args()
    try:raise SystemExit(audit(args.bundle,args.work))
    except (ValueError,KeyError,IndexError,OSError)as error:
        print('FAIL: recipe audit; '+str(error),file=sys.stderr);raise SystemExit(1)
