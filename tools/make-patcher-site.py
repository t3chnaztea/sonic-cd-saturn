#!/usr/bin/env python3
"""Prepare a local site package from an audited recipe. Does not publish."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
from check_patcher_vendor import verified
from recipe_elf import generated_input

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recipe',required=True,type=Path)
    parser.add_argument('--audit',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args();out=args.out.resolve()
    if not out.is_relative_to(ROOT/'build')or out.exists():raise ValueError('Choose a new site directory under build/')
    audit=json.loads(args.audit.read_text())
    if audit.get('status')!='PASS'or audit.get('scanner_exit_code')!=0 or audit.get('bundle_sha256')!=sha(args.recipe):raise ValueError('Recipe needs a passing hash-bound audit')
    if audit.get('policy')!='recipe-no-initialized-data-v5':raise ValueError('An older audit does not enforce source-only literal ownership')
    source_names={'audit-recipe.py','recipe_elf.py','recipe_provenance.py','recipe_types.py','recipe_values.py','recipe_tables.py','recipe_source.py','recipe_dwarf.py','recipe_iso.py','recipe_literal_scan.c'}
    if set(audit.get('audit_sources',{}))!=source_names or any(sha(ROOT/'tools'/name)!=audit['audit_sources'][name]for name in source_names):
        raise ValueError('Auditor source changed; rerun the recipe audit')
    lock=json.loads((ROOT/'web/patcher/pipeline-lock.json').read_text())
    files={*verified(ROOT),'web/patcher/vendor/runtime-lock.json'}
    files.update('web/patcher/'+name for name in ['index.html','style.css','app.js','worker.js','engine.js','release.js','audio.js','native.js','pyfs.js','pipeline.js','pipeline-lock.json','py/bootstrap.py'])
    for row in lock['project']:
        name=row['path']
        if name.startswith(('/','.'))or '..'in Path(name).parts or not (name.startswith(('src/','tools/'))or name in ('sources.lock.json','Makefile')):raise ValueError('Unsafe browser code input')
        if generated_input(name,ROOT):raise ValueError('Generated game data cannot enter the site code package')
        if (ROOT/name).stat().st_size!=row['bytes']or sha(ROOT/name)!=row['sha256']:raise ValueError('Pipeline code changed; refresh pipeline-lock.json')
        files.add(name)
    for row in [lock['bootstrap'],*lock['bridge'].values()]:
        if (ROOT/row['path']).stat().st_size!=row['bytes']or sha(ROOT/row['path'])!=row['sha256']:raise ValueError('Browser bridge changed; refresh pipeline-lock.json')
    # No fetched reference or native game output is copied. The only binary
    # additions are the named runtimes and the audited recipe itself.
    out.mkdir(parents=True)
    for name in sorted(files):
        source=ROOT/name;target=out/name;target.parent.mkdir(parents=True,exist_ok=True)
        if re.search(rb'/Users/[A-Za-z0-9._-]+|/Volumes/(?!Untitled\b)[A-Za-z0-9._-]+',source.read_bytes()):raise ValueError('Private path in a site file: '+name)
        shutil.copyfile(source,target)
    patcher=out/'web/patcher';shutil.copyfile(args.recipe,patcher/'recipe.scsp')
    (patcher/'recipe-lock.json').write_text(json.dumps(dict(status='PASS',sha256=audit['bundle_sha256'],
        literal_bytes=audit['literal_bytes'],literal_bytes_by_class=audit['literal_bytes_by_class'],
        policy=audit['policy'],audit_sources=audit['audit_sources'],
        live_reference_fetch_tested=False,hardware_tested=False),indent=2)+'\n')
    receipt=dict(status='prepared-local',recipe_sha256=audit['bundle_sha256'],files=len(files)+2,
        site_bytes=sum(p.stat().st_size for p in out.rglob('*')if p.is_file()),published=False)
    (out/'SITE-RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS: local audited site package; '+str(receipt['files'])+' files; not published')


if __name__=='__main__':main()
