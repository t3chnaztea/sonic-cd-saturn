#!/usr/bin/env python3
"""Record code and pinned reference inputs for the browser converter runner.

Only hashes, sizes and public paths/URLs are emitted. Reference bytes remain
in .deps/ and are fetched by the user's browser, never copied into the site.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
from urllib.parse import quote
from recipe_elf import generated_input

ROOT=Path(__file__).resolve().parents[1]


def row(path):
    data=(ROOT/path).read_bytes()
    return dict(path=path,bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reads',required=True,type=Path)
    parser.add_argument('--recipe',type=Path,help='Include every source serializer input in the lock')
    args=parser.parse_args()
    reads=json.loads(args.reads.read_text())
    if args.recipe:
        bundle=args.recipe.read_bytes();length=struct.unpack_from('<I',bundle,8)[0]
        construction=json.loads(bundle[12:12+length])['construction']
        for table in construction['tables']:
            reads.extend(table.get('macro_sources',[]))
            if table.get('source'):reads.append(table['source'])
            reads.extend(row['source']for row in table.get('constant_sources',[]))
        reads=sorted(set(reads))
    lock=json.loads((ROOT/'sources.lock.json').read_text())
    tracked=set(subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','tools/','src/'],cwd=ROOT,text=True).splitlines())
    attrs=subprocess.check_output(['git','check-attr','--stdin','export-ignore'],cwd=ROOT,input='\n'.join(tracked),text=True).splitlines()
    internal={a.split(': ')[0]for a in attrs if a.endswith(': set')}
    project={p for p in tracked if p.startswith('tools/')and p.endswith('.py')and not Path(p).name.startswith(('test','qa-','qa_'))}
    project.update(p for p in reads if p in tracked and not p.startswith('.deps/')and not generated_input(p,ROOT))
    project.update(['src/background_r3.c','sources.lock.json','Makefile'])
    # Table recipes read tracked project headers that no converter opens.
    project.update(p for p in tracked if p.startswith('src/')and not generated_input(p,ROOT))
    project-=internal
    # The browser never exports a checkout. Its desktop-only volume defaults
    # also do not belong in the site package.
    project.discard('tools/export-public.py')
    references=[];trees={}
    for path in sorted(set(reads)):
        if not path.startswith('.deps/')or not (ROOT/path).is_file():continue
        parts=Path(path).parts
        if '..'in parts or len(parts)<3:raise ValueError('Unsafe traced reference path')
        dependency=parts[1]
        if dependency=='gcc-13.4.0':
            if path!='.deps/gcc-13.4.0/libgcc/libgcc2.c':raise ValueError('Unapproved compiler source reference')
            # The local release archive supplies this source. Its exact file
            # hash is pinned even if the upstream release tag later moves.
            references.append(dict(row(path),dependency=dependency,release='releases/gcc-13.4.0',
                url='https://raw.githubusercontent.com/gcc-mirror/gcc/releases/gcc-13.4.0/libgcc/libgcc2.c'))
            continue
        spec=lock[dependency]
        if not re.fullmatch(r'[a-f0-9]{40}',spec['commit']):raise ValueError('Unpinned source commit')
        if dependency not in trees:
            listing=subprocess.check_output(['git','-C',str(ROOT/'.deps'/dependency),'ls-tree','-r','-z',spec['commit']])
            trees[dependency]={}
            for item in listing.split(b'\0'):
                if not item:continue
                attributes,name=item.split(b'\t',1);mode,kind,object_id=attributes.split()
                if kind==b'blob':trees[dependency][name.decode()]=object_id.decode()
        relative='/'.join(parts[2:]);data=(ROOT/path).read_bytes()
        object_id=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        if trees[dependency].get(relative)!=object_id:raise ValueError('Reference differs from its pinned Git object: '+path)
        upstream=spec['url'].removesuffix('.git')
        if not upstream.startswith('https://github.com/'):raise ValueError('Unsupported source host')
        url='https://raw.githubusercontent.com/'+upstream.removeprefix('https://github.com/')+'/'+spec['commit']+'/'+quote('/'.join(parts[2:]),safe='/')
        references.append(dict(row(path),url=url,dependency=dependency,commit=spec['commit']))
    commands=[dict(script=m[1],args=m[2].split('#')[0].split('>')[0].strip().split())
        for m in re.finditer(r'^\s*python3 (tools/[^\s]+)([^\n]*)',(ROOT/'tools/build.sh').read_text(),re.M)]
    # src/scroll_limits.h is tracked for the desktop build but holds disc-derived
    # limits, so the site does not ship it. The browser regenerates it after
    # background_tables.py has adapted the reference sources it reads.
    if commands[-1]['script']!='tools/package.py':raise ValueError('Expected package.py as the final command')
    commands.insert(len(commands)-1,dict(script='tools/extract_scroll_limits.py',args=[]))
    # This tracked include used to be copied into the site. Its CC0-derived
    # data must instead be generated before the recipe serializers read it.
    commands.insert(len(commands)-1,dict(script='tools/prepare_mm_remaining.py',args=[]))
    manifest=dict(schema=1,project=[row(p)for p in sorted(project)],references=references,commands=commands,
        commits={name:spec['commit']for name,spec in lock.items()if isinstance(spec,dict)and 'commit'in spec},
        bridge={name:row('web/patcher/'+name)for name in ['native.js','pyfs.js','audio.js']},
        bootstrap=row('web/patcher/py/bootstrap.py'))
    (ROOT/'web/patcher/pipeline-lock.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'PASS: pipeline input lock; {len(project)} code files; {len(references)} pinned reference files; {len(commands)} commands')


if __name__=='__main__':main()
