#!/usr/bin/env python3
"""Copy approved local runtimes into a new, hash-pinned vendor directory.

No downloads or runtime execution. Game/BIOS inputs are never copied.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def diagnostic_ranges(data):
    if data[:8]!=b'\0asm\1\0\0\0':raise ValueError('Invalid WASM runtime')
    at=8;ranges=[]
    while at<len(data):
        kind=data[at];at+=1;size=0;shift=0
        while True:
            value=data[at];at+=1;size|=(value&127)<<shift;shift+=7
            if shift>35:raise ValueError('Invalid WASM section length')
            if not value&128:break
        if at+size>len(data):raise ValueError('Truncated WASM section')
        if kind in (0,11):ranges.append((at,at+size))
        at+=size
    return ranges


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',required=True,type=Path)
    args=parser.parse_args();out=ROOT/'web/patcher/vendor'
    if out.exists():raise ValueError('Vendor destination must be new')
    py=ROOT/'.deps/pyodide-spike-0.27.7/extracted/pyodide'
    ff=ROOT/'.deps/ffmpeg-core-spike-0.12.10/extracted/package'
    jobs=[]
    for name in ['pyodide.js','pyodide.mjs','pyodide.asm.js','pyodide.asm.wasm','python_stdlib.zip','pyodide-lock.json','pillow-10.2.0-cp312-cp312-pyodide_2024_0_wasm32.whl']:
        jobs.append((py/name,'pyodide/'+name,'MPL-2.0'if name.startswith('pyodide')else'PSF-2.0'if name=='python_stdlib.zip'else'HPND','Pyodide 0.27.7'))
    for name in ['ffmpeg-core.js','ffmpeg-core.wasm']:
        jobs.append((ff/'dist/umd'/name,'ffmpeg/'+name,'GPL-2.0-or-later','@ffmpeg/core 0.12.10'))
    for name in ['genesis','sonic','fmv','iso']:
        for suffix in ['js','wasm']:
            jobs.append((args.runtime/(name+'.'+suffix),'native/'+name+'.'+suffix,
                'LicenseRef-Genesis-Plus-GX'if name=='genesis'else'GPL-2.0-or-later'if name=='iso'else'MIT','Emscripten 4.0.10'))
    files=[];contents=[]
    # Validate all sources before creating the destination.
    for source,name,license,origin in jobs:
        data=source.read_bytes()
        upstream=hashlib.sha256(data).hexdigest()
        pattern=rb'/Users/[A-Za-z0-9._-]+|/Volumes/(?!Untitled\b)[A-Za-z0-9._-]+'
        matches=len(re.findall(pattern,data))
        if matches:
            if not name.endswith(('.wasm','.js','.mjs')):raise ValueError('Private path in an unsupported runtime format: '+name)
            if name.endswith('.wasm'):
                ranges=diagnostic_ranges(data)
                if any(not any(start<=match.start()and match.end()<=end for start,end in ranges)for match in re.finditer(pattern,data)):
                    raise ValueError('Path match outside WASM data/custom sections')
            # Diagnostic source paths are NUL-terminated data. Preserve byte
            # lengths so WASM sections, relocations and memory offsets remain
            # intact. Do not touch executable instructions or copyrights.
            data=re.sub(pattern,lambda m:b'/build/'+b'_'*(len(m[0])-7),data)
        contents.append(data)
        files.append(dict(path='web/patcher/vendor/'+name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),license=license,origin=origin,
                          upstream_sha256=upstream,redacted_build_path_prefixes=matches))
    out.mkdir()
    for (source,name,_,_),row,data in zip(jobs,files,contents):
        target=out/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        if hashlib.sha256(target.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('Runtime copy changed')
    notices=out/'licenses';notices.mkdir()
    for source,name in [(ROOT/'.deps/genesis-plus-gx/LICENSE.txt','Genesis-Plus-GX.txt'),(ROOT/'.deps/beetle-saturn/COPYING','Beetle-Saturn.txt')]:
        if source.is_file():shutil.copyfile(source,notices/name)
    wheel=py/'pillow-10.2.0-cp312-cp312-pyodide_2024_0_wasm32.whl'
    with zipfile.ZipFile(wheel)as archive:
        (notices/'Pillow.txt').write_bytes(archive.read('pillow-10.2.0.dist-info/licenses/LICENSE'))
    for path in sorted(notices.iterdir()):
        files.append(dict(path=path.relative_to(ROOT).as_posix(),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),license='upstream-notice',origin='local pinned source'))
    lock=dict(schema=1,files=files,archives=[dict(name='pyodide-0.27.7',sha256='08dd7f4fc4710110ea0fe2a7daa95bdf76001e596545267bc16dd760436ea755'),dict(name='ffmpeg-core-0.12.10',sha256='d00089ce82e1bdf637ddbe42e0c3d41a1ba8cf4c9e825e7fa4d0bb970e844bd4'),dict(name='emsdk-4.0.10',sha256='2497b55ddbba9bf9be2d18cfca3e973d40a0cfaa8d18f6caacb882a65b2faf1c')])
    (out/'runtime-lock.json').write_text(json.dumps(lock,indent=2)+'\n')
    print(f'PASS: pinned patcher runtimes; {len(files)} files; {sum(r["bytes"]for r in files)} bytes')


if __name__=='__main__':main()
