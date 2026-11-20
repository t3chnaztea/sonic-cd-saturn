#!/usr/bin/env python3
"""Verify era chain lengths, same-tick initialization and orbit math in retail."""
import hashlib,json,re,struct
from pathlib import Path
from convert_assets import ROOT
from extract_mmd import disc_files,ORIGIN
from retail_span import disc_span


def verify():
    files=disc_files((ROOT/'build/retail/sonic.iso').read_bytes())
    etc=(ROOT/'build/probe-source/etc.c').read_text()
    values=list(map(int,re.findall(r'\d+',etc.split('sintable[320]')[1].split('{')[1].split('}')[0])))
    sine=disc_span('R31A__.MMD',0x782,24,'b4e3dfd37237376d2b0c2ce6eea6898bfceefeb62e094a1f84401e1a655abc5e')+struct.pack('>320H',*values)
    allocator=disc_span('R31A__.MMD',0x7b12,32,'f6fa59b5ca908c67d77c5427b398e0acbe1be6afe80d693ee95f525722362d40')
    programs={}
    for act in (1,2,3):
        for era in ('CD' if act==3 else 'ABCD'):
            name=f'R3{act}{era}';p=files[name+'__.MMD'];count={'A':3,'B':2,'C':4,'D':4}[era]
            hits=[m.start() for m in re.finditer(re.escape(bytes.fromhex('317c03bd0002')),p)]
            assert len(hits)==2,(name,hits)
            tile,childtile=hits
            assert p.count(sine)==p.count(allocator)==1,name
            alloc=ORIGIN+p.index(allocator);sin=ORIGIN+p.index(sine)
            init=disc_span('R31A__.MMD',0xbd48,28,'aebb1f5ad1f7f0e7471077c63979a72034b650dec59279892f76c634373f0b11')
            assert p[tile-36:tile-8]==init,name
            assert p[tile+6:tile+22]==disc_span('R31A__.MMD',0xbd72,16,'f3ef99ece3ae0efb9d9d59e58766bbf60885fc590b51999552e538c3ef23b78c'),name
            first=tile+22;failed=first+count*42+2
            for n in range(count):
                pos=first+n*42
                expected=bytes.fromhex('4eb9')+struct.pack('>I',alloc)+bytes.fromhex('6600')+struct.pack('>h',failed-(pos+8))
                expected+=bytes.fromhex('3348003e3149')+struct.pack('>H',46+2*n)
                expected+=disc_span('R31A__.MMD',0xbd94,24,'ffe862811070444ca6bf977bc61c1d8b853eaa30f7a9d9610cd0db8ebd6bfbd5')
                assert p[pos:pos+42]==expected,(name,n,'ordered allocation')
            move=failed+6
            assert p[failed-2:failed]==bytes.fromhex('6006') and p[failed:failed+2]==bytes.fromhex('4ef9'),name
            # The successful initializer branches over failure directly into
            # motion. The PC reconstruction omits this initial motion call.
            expected=disc_span('R31A__.MMD',0xbe08,16,'6c80a36a9915b9ecf3af517bc2a5b4d9016b1f06ae0d664b5ff70931f0abbdb4')+struct.pack('>I',sin)
            expected+=disc_span('R31A__.MMD',0xbe1c,28,'3f8b8c5304b60d446b8f43c4f5c2c8b6c75070f9200c6c0bd1402ace3c63a5f0')
            for n in range(count):
                expected+=bytes.fromhex('3268')+struct.pack('>H',46+2*n)+disc_span('R31A__.MMD',0xbe3c,12,'92c1bba9389179efd8f943b47115a2046cb9f8df0fcf11950da98e45b2257de8')
                expected+=bytes.fromhex(['d1a9002ed3a9002a','d5a9002ed7a9002a','d1a9002ed3a9002ad5a9002ed7a9002a','d9a9002edba9002a'][n])
            expected+=bytes.fromhex('4e75')
            assert p[move:move+len(expected)]==expected,(name,'fixed-point orbit')
            assert p[childtile+6:childtile+26]==disc_span('R31A__.MMD',0xbeda,20,'78ac810391cf76727e2b5609bb8aec3e486aa9a422fcc60cebf7b0e29fa16f09'),name
            parentcheck=disc_span('R31A__.MMD',0xbea0,14,'d315972fea80198f4c4ba1473081d8f4f9b1aabdb283be4530963df2bed28637')
            assert p.count(parentcheck)==1,name
            programs[name]=dict(program_sha256=hashlib.sha256(p).hexdigest(),balls=count,
                initializer=ORIGIN+tile-36,move=ORIGIN+move,allocator=alloc,sine=sin,
                child_parent_offset=62,init_moves_immediately=True,
                orbit_sha256=hashlib.sha256(expected).hexdigest())
    result=dict(passed=True,programs=programs,allocator_bytes=allocator.hex(),
                sine_bytes_sha256=hashlib.sha256(sine).hexdigest(),
                tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                limits='Exact console allocation, immediate init motion, sine table, orbit instructions and child lookup; not a full original-machine playthrough.')
    out=ROOT/'build/cc1/togeball';out.mkdir(parents=True,exist_ok=True)
    (out/'retail.json').write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':print('Verified original rotating spike balls in',len(verify()['programs']),'programs')
