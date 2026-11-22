"""Single-worker conversion bootstrap. User inputs have already been hashed."""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path('/project')


def extract_us_iso(expected):
    source=ROOT/'build/retail/sonic.bin';output=ROOT/'build/retail/sonic.iso'
    if expected['bytes']%2048:raise ValueError('Invalid source data-track contract')
    checksum=hashlib.sha256()
    with source.open('rb')as stream,output.open('wb')as dest:
        for _ in range(expected['bytes']//2048):
            sector=stream.read(2352)
            if len(sector)!=2352 or sector[15]!=1:raise ValueError('Expected a MODE1/2352 U.S. data track')
            data=sector[16:2064];checksum.update(data);dest.write(data)
    if checksum.hexdigest()!=expected['sha256']:raise ValueError('U.S. extracted data-track checksum failed')


def initialize(backend,construction,core_sha):
    os.chdir(ROOT);sys.path.insert(0,str(ROOT/'tools'))
    os.environ.update(SCD_QA_MAX_WORKERS='1',SCD_QA_MAX_EMULATORS='1',SCD_BROWSER_CORE_SHA256=core_sha)
    import native
    native.install(backend)
    extract_us_iso(construction['us_iso'])


def convert(script,arguments):
    import native
    code,stdout,stderr=native._python([script,*arguments],str(ROOT))
    if code:raise RuntimeError(f'{script} failed ({code})\n{stdout[-2000:]}\n{stderr[-2000:]}')
    return stdout[-2000:]


def verify_cd(construction):
    for row in construction['iso_layout']['files']:
        path=ROOT/row['source']
        with path.open('rb')as stream:checksum=hashlib.file_digest(stream,'sha256').hexdigest()
        if path.stat().st_size!=row['bytes']or checksum!=row['sha256']:
            raise ValueError('Converted CD payload checksum failed: '+row['source'])
