#!/usr/bin/env python3
"""Reproduce the reviewed PoneSound firmware. No target execution or downloads.

Run under the existing guarded build workflow. Tool overrides name the exact
accepted local tools; their byte hashes remain mandatory. A different compiler
requires a separate producer review, not relaxed firmware/ABI checks.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from qa_limits import atomic_json
from ponesound.elf_check import check_elf

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'tools/ponesound'
OUT=ROOT/'build/sound-driver'
EXPECTED_RAW='ae1f243ab3b9be9ea66dc86904111c42feb8b9817229678f5433c41b80735c6a'
SOURCE_SHA='e54d13c8d30a89577fc77077c378b7c8ccdcabd9827369c3193fa1878c2e16e2'
LINKER_SHA='e78aeef39a95fcfe9af02140694e0fdcd049ec8eb304cb84189fa120f6ccf85c'
TOOLS={'compiler':'7463e8c6f2d4cff4cda1cc7f227b25e9ec9344abe5de190516d78c4cdaa3738a',
       'nm':'964eeb0d4358162678cfbb07abaaacecc465618c040011ab265c3a0969ed8f38',
       'objcopy':'cb288ef1bd2e724e2850e58224987742fca4cd71db03859044663ed95c17087c'}
FLAGS=['-O2','-fno-use-linker-plugin','-std=gnu99','-Wall','-Wno-char-subscripts',
       '-nodefaultlibs','-nostdlib','-mc68000','-mno-align-int','-mno-strict-align']

def require(ok,why):
    if not ok:raise ValueError(why)

def sha(path):
    with Path(path).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()

def regular(path):
    require(path.is_file()and not path.is_symlink(),'Missing/nonregular input: '+str(path))
    return sha(path)

def recipes(tools,work):
    return [('compile',[str(tools['compiler']),str(DATA/'driver.c'),*FLAGS,'-T',str(DATA/'driver.ld'),'-o',str(work/'driver.elf')],180),
            ('undefined',[str(tools['nm']),'-u',str(work/'driver.elf')],30),
            ('objcopy',[str(tools['objcopy']),'-O','binary',str(work/'driver.elf'),str(work/'driver.bin')],30)]

def validate_image(elf,raw,contract):
    metadata=check_elf(elf,contract)
    require(metadata['flags']==0x01000000 and metadata['aligned_end']==0xbd60,'Reviewed CPU/workspace layout changed')
    require(len(raw)==8740 and hashlib.sha256(raw).hexdigest()==EXPECTED_RAW,'Firmware bytes differ from reviewed ae1 image')
    require(metadata['flat_image_bytes']==len(raw)and metadata['flat_image_sha256']==EXPECTED_RAW,'ELF/objcopy image differs')
    return metadata

def cached(report,inputs,contract):
    if report.get('status')!='passed'or report.get('inputs')!=inputs:return False
    if type(report.get('outputs'))is not dict or set(report['outputs'])!={'driver.elf','driver.bin'}:return False
    try:
        for name,record in report['outputs'].items():
            p=OUT/name
            if not p.is_file()or p.is_symlink()or p.stat().st_size!=record['bytes']or sha(p)!=record['sha256']:return False
        validate_image((OUT/'driver.elf').read_bytes(),(OUT/'driver.bin').read_bytes(),contract)
    except (OSError,KeyError,ValueError,TypeError):return False
    return True

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler',type=Path,default=Path(os.environ.get('SCD_M68K_CC',ROOT/'build/private-toolchains/m68k-gcc-13.4.0/bin/m68k-elf-gcc')))
    parser.add_argument('--nm',type=Path,default=Path(os.environ.get('SCD_M68K_NM',ROOT/'.deps/build-binutils-m68k/binutils/nm-new')))
    parser.add_argument('--objcopy',type=Path,default=Path(os.environ.get('SCD_M68K_OBJCOPY',ROOT/'.deps/build-binutils-m68k/binutils/objcopy')))
    args=parser.parse_args();tools={k:getattr(args,k).absolute()for k in TOOLS}
    for name,p in tools.items():require(regular(p)==TOOLS[name],'Unreviewed '+name+'; provide the accepted local tool')
    source_paths=[Path(__file__),ROOT/'tools/qa_limits.py',DATA/'driver.c',DATA/'driver.ld',DATA/'elf_check.py',DATA/'contract.json',DATA/'__init__.py']
    sources={str(p):regular(p)for p in source_paths}
    require(sources[str(DATA/'driver.c')]==SOURCE_SHA and sources[str(DATA/'driver.ld')]==LINKER_SHA,'Reviewed firmware source/linker changed')
    env={k:os.environ[k]for k in ('PATH','TMPDIR','SDKROOT')if k in os.environ}
    env.update(LANG='C',LC_ALL='C',TZ='UTC')
    inputs=dict(sources=sources,tools={k:dict(path=str(p),sha256=TOOLS[k])for k,p in tools.items()},flags=FLAGS,environment={k:v for k,v in env.items()if k!='TMPDIR'},OS=list(os.uname()),python=sys.version)
    contract=json.loads((DATA/'contract.json').read_text())
    require(not OUT.is_symlink(),'Unsafe output directory');OUT.mkdir(parents=True,exist_ok=True)
    prior=OUT/'report.json'
    if prior.is_file():
        try:old=json.loads(prior.read_text())
        except (OSError,ValueError):old={}
        if cached(old,inputs,contract):print('PASS: reviewed PoneSound driver ae1 validated from matching producer cache');return
    report=dict(status='pending',inputs=inputs,execution_environment=env,target_executed=False,retail_payload=False)
    atomic_json(prior,report)
    try:
        work=Path(tempfile.mkdtemp(prefix='produce-',dir=OUT));report['work']=str(work);report['commands']=[];atomic_json(prior,report)
        for name,command,timeout in recipes(tools,work):
            stdout=work/(name+'.stdout.log');stderr=work/(name+'.stderr.log')
            with stdout.open('xb')as out,stderr.open('xb')as err:
                result=subprocess.run(['/usr/bin/nice','-n','20',*command],cwd=ROOT,env=env,stdout=out,stderr=err,timeout=timeout)
            record=dict(name=name,argv=command,exit=result.returncode,stdout=dict(path=str(stdout),sha256=sha(stdout)),stderr=dict(path=str(stderr),sha256=sha(stderr)))
            report['commands'].append(record);atomic_json(prior,report)
            require(type(result.returncode)is int and result.returncode==0,'Driver '+name+' failed; see retained logs')
            if name=='undefined':require(not stdout.read_bytes().strip(),'Unresolved helpers; no libgcc or source fallback permitted')
        elf=(work/'driver.elf').read_bytes();raw=(work/'driver.bin').read_bytes();metadata=validate_image(elf,raw,contract)
        require({str(p):regular(p)for p in source_paths}==sources,'Producer sources changed')
        require(all(regular(p)==TOOLS[k]for k,p in tools.items()),'Producer tools changed')
        for name in ['driver.elf','driver.bin']:
            with (work/name).open('r+b')as f:os.fsync(f.fileno())
            os.replace(work/name,OUT/name)
        descriptor=os.open(OUT,os.O_RDONLY)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)
        outputs={name:dict(bytes=(OUT/name).stat().st_size,sha256=sha(OUT/name))for name in ['driver.elf','driver.bin']}
        report.update(status='passed',outputs=outputs,ELF=metadata,finished_utc=dt.datetime.now(dt.timezone.utc).isoformat())
        atomic_json(prior,report);print('PASS: reviewed PoneSound driver ae1 rebuilt; vectors/ABI/workspace/undefined checks passed')
    except BaseException as error:
        report.update(status='interrupted'if isinstance(error,(KeyboardInterrupt,SystemExit))else'failed',error=repr(error))
        try:atomic_json(prior,report)
        except BaseException as secondary:error.add_note('Driver report persistence failed: '+repr(secondary))
        raise

if __name__=='__main__':main()
