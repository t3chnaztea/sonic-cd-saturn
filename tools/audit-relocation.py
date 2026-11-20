#!/usr/bin/env python3
"""Inventory location-bearing local artifacts; never rewrite historical evidence.

This reads local files only and generates an ignored audit report. It does not
build, clean, move the project, change dependencies, or change Git configuration.
"""
import collections
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/relocation-audit'


def main():
    roots=[p for p in ['.deps','.toolchain','build','dist','assets','cd','audio-tracks'] if (ROOT/p).exists()]
    result=subprocess.run(['rg','--hidden','--no-ignore','--files-with-matches',
        '--text','--null','--fixed-strings','--glob','!**/.git/**',
        '--glob','!build/relocation-audit/**',str(ROOT),*roots],
        cwd=ROOT,capture_output=True,check=False)
    if result.returncode not in [0,1]:raise RuntimeError(result.stderr.decode())
    paths=sorted(p.decode() for p in result.stdout.split(b'\0') if p)
    links=[];caches=[];archives=[];repos=[]
    for root in roots:
        for directory,dirs,files in os.walk(ROOT/root,followlinks=False):
            if '.git' in dirs:
                repos.append(str(Path(directory).relative_to(ROOT)));dirs.remove('.git')
            for name in dirs+files:
                path=Path(directory)/name
                if path.is_symlink():
                    target=os.readlink(path)
                    links.append(dict(path=str(path.relative_to(ROOT)),target=target,
                        absolute=os.path.isabs(target),inside_repo=path.resolve().is_relative_to(ROOT),
                        exists=path.exists()))
                if name=='CMakeCache.txt':caches.append(str(path.relative_to(ROOT)))
                if root=='build' and name.endswith(('.zip','.tar.gz','.tar.xz','.tar','.7z')):
                    archives.append(str(path.relative_to(ROOT)))
    groups=collections.Counter('/'.join(Path(p).parts[:2]) if p.startswith('.deps/') else Path(p).parts[0] for p in paths)
    report=dict(scanned_root=str(ROOT),path_bearing_files=paths,groups=dict(sorted(groups.items())),
        cmake_caches=sorted(caches),symlinks=links,nested_repos=sorted(repos),
        historical_archives_not_decompressed=sorted(archives),
        limits='Byte scan of current-root spelling in ordinary files, including binaries. Does not unpack compressed historical archives. Those may also contain embedded paths; preserve rather than mutate. Dependency .git internals excluded.')
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'inventory.json').write_text(json.dumps(report,indent=2)+'\n')
    (OUT/'path-bearing-files.txt').write_text('\n'.join(paths)+'\n')
    print(json.dumps(dict(files=len(paths),groups=report['groups'],cmake_caches=caches,
        symlinks=len(links),absolute_links=sum(x['absolute'] for x in links),
        external_links=[x for x in links if not x['inside_repo']],nested_repos=report['nested_repos'],
        compressed_archives=len(archives)),indent=2))


if __name__=='__main__':main()
