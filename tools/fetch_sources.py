#!/usr/bin/env python3
"""Fetch pinned sources; leave existing work intact and verify versions."""
import argparse
import hashlib
import json
import pathlib
import subprocess
import tarfile
import urllib.request

ROOT=pathlib.Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--emulator',action='store_true')
args=parser.parse_args()
lock=json.loads((ROOT/'sources.lock.json').read_text())
deps=ROOT/'.deps';deps.mkdir(exist_ok=True)
for name,spec in lock.items():
    if name=='archives':continue
    dest=deps/name
    if not dest.exists():
        subprocess.run(['git','init',str(dest)],check=True)
        subprocess.run(['git','-C',str(dest),'remote','add','origin',spec['url']],check=True)
        subprocess.run(['git','-C',str(dest),'fetch','--depth','1','origin',spec['commit']],check=True)
        subprocess.run(['git','-C',str(dest),'checkout','--detach','FETCH_HEAD'],check=True)
    actual=subprocess.check_output(['git','-C',str(dest),'rev-parse','HEAD'],text=True).strip()
    if actual!=spec['commit']:raise SystemExit(f'{name}: existing revision differs from lock; preserved it')
    # Tracked fixes to pinned sources (tools/patches/<name>-*.patch): apply each once,
    # verify it by a reverse check, and keep every other file identical to the lock.
    patched=[]
    for patch in sorted((ROOT/'tools/patches').glob(f'{name}-*.patch')):
        applied=subprocess.run(['git','-C',str(dest),'apply','--reverse','--check',str(patch)],capture_output=True).returncode==0
        if not applied:subprocess.run(['git','-C',str(dest),'apply',str(patch)],check=True)
        subprocess.run(['git','-C',str(dest),'apply','--reverse','--check',str(patch)],check=True)
        patched+=[l[6:] for l in patch.read_text().splitlines() if l.startswith('+++ b/')]
    subprocess.run(['git','-C',str(dest),'diff','--exit-code','HEAD','--','.']+[f':(exclude){f}' for f in patched],check=True)
downloads=deps/'downloads';downloads.mkdir(exist_ok=True)
for spec in lock['archives']:
    dest=downloads/spec['file']
    if not dest.exists():
        if dest.name.startswith('gcc-'):
            url='https://ftp.gnu.org/gnu/gcc/gcc-13.4.0/'+dest.name
        else:url='https://ftp.gnu.org/gnu/binutils/'+dest.name
        temp=dest.with_suffix('.part')
        urllib.request.urlretrieve(url,temp)
        if hashlib.sha256(temp.read_bytes()).hexdigest()!=spec['sha256']:raise SystemExit('Downloaded archive checksum mismatch')
        temp.rename(dest)
    if hashlib.sha256(dest.read_bytes()).hexdigest()!=spec['sha256']:raise SystemExit(f'Archive checksum mismatch: {dest.name}')
    directory=deps/dest.name.removesuffix('.tar.xz')
    if not directory.exists():
        with tarfile.open(dest) as archive:archive.extractall(deps,filter='data')
print('Pinned source revisions and compiler archive checksums verified.')
