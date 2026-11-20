#!/usr/bin/env python3
"""Bind exploratory binaries to their actual local build and runtime inputs."""
import hashlib,json,shlex,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build/ppz-journey'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def verify():
    manifest=json.loads((BUILD/'build-manifest.json').read_text())
    for group in ('inputs','binaries'):
        for name,value in manifest[group].items():
            assert sha(ROOT/name)==value,('stale journey build',name)
    return manifest
def main():
    deps=(BUILD/'dependencies.mk').read_text().replace('\\\n',' ')
    names=set()
    for rule in deps.splitlines():
        if rule.strip():names.update(shlex.split(rule.split(':',1)[1]))
    names.update(['tools/build-ppz-journey.sh','tools/ppz_journey_manifest.py'])
    for suffix in ['0','1','2','3','12A','12B','12C','12D','13C','13D']:
        for kind in ['ppz','collision']:names.add(f'assets/generated/{kind}{suffix}.bin')
    inputs={name:sha(ROOT/name) for name in sorted(names)}
    manifest=dict(inputs=inputs,binaries={f'build/ppz-journey/{name}':sha(BUILD/name) for name in ['native.dylib','sanitized']},
        compiler=subprocess.check_output(['clang','--version'],text=True),
        limits='Source/header/runtime-asset and built-binary identity; not an independent gameplay oracle.')
    (BUILD/'build-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    verify();print('Journey build bound:',len(inputs),'inputs; two binaries')
if __name__=='__main__':main()
