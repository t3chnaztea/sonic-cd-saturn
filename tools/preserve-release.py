#!/usr/bin/env python3
"""Read back a verified local-only bundle and preserve it without replacing older files.

The bundle contains SEGA data (see tools/bundle.py). Keep it and the preserved
copy under build/ on your own machine. Never distribute either.
"""
import hashlib,json,os,pathlib,re,tempfile,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
DIST=ROOT/'dist';NAME='sonic-cd-saturn-prototype'
def digest(data):return hashlib.sha256(data).hexdigest()
def same(path,data):
    assert path.is_file() and path.read_bytes()==data,f'Readback differs: {path}'
def save_new(path,data):
    if path.exists():same(path,data);return
    with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as tmp:
        pending=pathlib.Path(tmp.name);tmp.write(data);tmp.flush();os.fsync(tmp.fileno())
    try:os.link(pending,path) # Atomic creation, never replace a preserved file.
    finally:pending.unlink()
    same(path,data)
def run_prune():
    """Prune build/ after a verified release. SCD_NO_PRUNE=1 skips. Never fails the release."""
    import os,subprocess,sys
    if os.environ.get('SCD_NO_PRUNE')=='1':print('prune-build: skipped (SCD_NO_PRUNE=1)');return
    try:
        r=subprocess.run([sys.executable,str(ROOT/'tools'/'prune-build.py'),'--apply'],cwd=ROOT,capture_output=True,text=True,timeout=3600)
        lines=r.stdout.splitlines()
        print('\n'.join(l for l in lines if not l.startswith('    ') and l.strip()!='entries:' and not l.lstrip().startswith('entries:')))
        if r.returncode!=0:print(f'WARNING: prune-build exited {r.returncode}: {r.stderr.strip()[-500:]}')
        elif r.stderr.strip():print('prune-build warnings:\n'+r.stderr.strip()[-2000:])
    except Exception as exc:print(f'WARNING: prune-build failed; release is unaffected: {exc}')
def main():
    version=re.search(r'^IP_VERSION:= V(\d+\.\d+)$',(ROOT/'Makefile').read_text(),re.M)[1]
    archive=DIST/f'{NAME}.zip';binary=DIST/f'{NAME}.bin';disc_sha=digest(binary.read_bytes())
    qa=json.loads((DIST/'qa-report.json').read_text());assert qa['passed'] and qa['mode']=='full'
    reports=['player-report.json','emulator-report.json','audio-report.json','audio-diagnostic-report.json','world-report.json','act-report.json','act2-report.json','act3-report.json','sequence-report.json','bigring-report.json','title-report.json','special-report.json','special-game-report.json','qa-report.json']
    for name in reports:
        report=json.loads((DIST/name).read_text());assert report['disc_sha256']==disc_sha,f'Stale {name}'
    for name,sha in qa['report_hashes'].items():assert digest((DIST/name).read_bytes())==sha,f'Changed {name}'
    zone_artifacts=[]
    if version in ('0.076','0.077','0.078','0.079','0.080','0.081'):
        from zone_release_evidence import audit as audit_zones
        _,zone_artifacts=audit_zones(ROOT,qa,disc_sha,staged=True)
    build=json.loads((DIST/'build-report.json').read_text())
    for suffix in ['bin','cue']:
        path=DIST/f'{NAME}.{suffix}';assert digest(path.read_bytes())==build['files'][path.name]['sha256']
    assert f'V{version}'.encode() in binary.read_bytes()[:2352*32],'Disc version differs from Makefile'
    for name in ['README.md','PLAN.md','QA-PLAN.md','OBJECT-COVERAGE.md','sources.lock.json']:same(DIST/name,(ROOT/name).read_bytes())
    # These sources are independently regenerated/checked by the functional loop.
    source_pairs={
        'object-art-baseline.json':'tools/object-art-baseline.json',
        'act-target-trace.txt':'build/act-qa/player-target-trace.txt',
        'act2-target-trace.txt':'build/act2-qa/player-target-trace.txt',
        'act3-target-trace.txt':'build/act3-qa/player-target-trace.txt',
        'mmd-extract.json':'build/mmd-extract.json',
        'special-contact-report.json':'build/special-reference/contact-report.json',
        'special-sonic-source.json':'build/special-sonic-source.json',
        'special-effects-source.json':'build/special-effects-source.json',
        'special-source.json':'build/special-source.json',
        'special-results.log':'build/special-qa/results.log',
        'special-ufo-source.json':'build/special-ufo-source.json',
    }
    for name in ['effect-report','effect-art-report','effect-art-fixtures','effect-dispatch-report','effect-loop-report','sprite-report','sprite-fixtures','animation-report','animation-fixtures','player-report','air-fixtures','fixtures','ufo-report','reward-report','ufo-art-report','ufo-art-fixtures','stage-report']:
        source_pairs['special-'+name+'.json']='build/special-reference/'+name+'.json'
    source_pairs['special-reference.json']='build/special-reference/report.json'
    for name,source in source_pairs.items():same(DIST/'evidence'/name,(ROOT/source).read_bytes())
    assert digest((ROOT/'build/act-qa/player-target-trace.txt').read_bytes())==json.loads((DIST/'act-report.json').read_text())['trace_sha256']
    assert digest((ROOT/'build/act2-qa/player-target-trace.txt').read_bytes())==json.loads((DIST/'act2-report.json').read_text())['trace_sha256']
    assert digest((ROOT/'build/act3-qa/player-target-trace.txt').read_bytes())==json.loads((DIST/'act3-report.json').read_text())['trace_sha256']
    tops={};members=0;pngs=0
    with zipfile.ZipFile(archive) as bundle:
        names=bundle.namelist();assert len(names)==len(set(names))
        for name in names:
            path=pathlib.PurePosixPath(name);assert not path.is_absolute() and '..' not in path.parts
            data=bundle.read(name);same(DIST/name,data);members+=1;pngs+=name.endswith('.png')
            if len(path.parts)==1:tops[name]=data
    assert set(reports)<=set(tops)
    assert {str(name) for _,name in zone_artifacts}<=set(names),'Bundle is missing zone evidence'
    cc_summary=None
    if version in ('0.068','0.069','0.070','0.071','0.072'):
        cc=DIST/'cc-evidence'
        entry=json.loads((cc/'entry-scene-report.json').read_text())
        scroll=json.loads((cc/'scroll-target-report.json').read_text())
        assert entry['status']==scroll['status']=='passed'
        assert entry['disc_sha256']==scroll['disc_sha256']==disc_sha
        assert entry['target_report_sha256']==digest((cc/'scroll-target-report.json').read_bytes())
        assert len(entry['programs'])==len(scroll['programs'])==10
        for name,row in entry['programs'].items():
            assert digest((cc/f'{name}-original.png').read_bytes())==row['source_image_sha256']
            assert digest((cc/f'{name}-target.ppm').read_bytes())==row['target_image_sha256']==scroll['programs'][name]['entry_image_sha256']
            assert digest((cc/f'{name}-moving-original.png').read_bytes())==row['moving_source_image_sha256']
            assert digest((cc/f'{name}-moving-target.ppm').read_bytes())==row['moving_target_image_sha256']==scroll['programs'][name]['moving_image_sha256']
            route=json.loads((cc/f'cc{name[2]}{name[3]}-report.json').read_text())
            assert route['passed'] and route['disc_sha256']==disc_sha
            assert digest((cc/f'cc{name[2]}{name[3]}-script.txt').read_bytes())==route['script_sha256']
            assert digest((cc/f'cc{name[2]}{name[3]}-controller.txt').read_bytes())==route['pad_sha256']
        cc_summary={'routes':10,'idle_entry_scenes':10,'moving_entry_scenes':10,
                    'exact_scene_pixels':sum(v['scene']['exact_pixels'] for v in entry['programs'].values()),
                    'scene_pixels':sum(v['scene']['pixels'] for v in entry['programs'].values()),
                    'exact_moving_scene_pixels':sum(v['moving_scene']['exact_pixels'] for v in entry['programs'].values()),
                    'moving_scene_pixels':sum(v['moving_scene']['pixels'] for v in entry['programs'].values())}
        if version in ('0.069','0.070','0.071','0.072'):
            emie=json.loads((cc/'emie-palette-report.json').read_text())
            assert emie['status']=='passed' and emie['disc_sha256']==disc_sha
            assert emie['emie_region']['exact_pixels']==emie['emie_region']['pixels']==925
            assert emie['scroll_report_sha256']==digest((cc/'scroll-target-report.json').read_bytes())
            assert digest((cc/'emie-frame360-original.png').read_bytes())==emie['source_image_sha256']
            assert digest((cc/'emie-frame360-target.ppm').read_bytes())==emie['target_image_sha256']
            cc_summary['emie_frame360_exact_pixels']=925
    tops[archive.name]=archive.read_bytes()
    target=ROOT/'build'/f'hardware-v{version}'
    # Preflight all conflicts before making any preserved copy.
    for name,data in tops.items():
        if (target/name).exists():same(target/name,data)
    target.mkdir(exist_ok=True)
    for name,data in tops.items():save_new(target/name,data)
    previous=sorted((p for p in (ROOT/'build').glob('hardware-v*') if p!=target and re.fullmatch(r'hardware-v\d+\.\d+',p.name)),key=lambda p:tuple(map(int,p.name.split('v')[1].split('.'))))
    prior=None
    if previous:
        prior=previous[-1]
        manifest=ROOT/'build'/f'release-v{int(prior.name.split(".")[-1])}-readback.json'
        if manifest.is_file():
            old_archive=prior/archive.name
            previous_report=json.loads(manifest.read_text())
            assert digest(old_archive.read_bytes())==previous_report['zip_sha256'],'Previous preserved archive changed'
            assert digest((prior/binary.name).read_bytes())==previous_report['disc_sha256'],'Previous preserved disc changed'
            with zipfile.ZipFile(old_archive) as old:
                for name in old.namelist():
                    if len(pathlib.PurePosixPath(name).parts)==1:same(prior/name,old.read(name))
        else:
            old_report=json.loads((prior/'readback.json').read_text())
            archives=list(prior.glob('*.zip'))
            assert old_report['status']=='passed' and len(archives)==1,'Previous private bundle missing'
            old_archive=archives[0]
            assert digest(old_archive.read_bytes())==old_report['archive_sha256'],'Previous private archive changed'
            with zipfile.ZipFile(old_archive) as old:
                assert len(old.namelist())==old_report['members'],'Previous private archive members changed'
                previous_bin=hashlib.sha256()
                with old.open(binary.name) as source:
                    for chunk in iter(lambda:source.read(1024*1024),b''):previous_bin.update(chunk)
                assert previous_bin.hexdigest()==old_report['bin_sha256'],'Previous private BIN changed'
    report={'verified':True,'version':version,'members':members,'pngs':pngs,'disc_bound_reports':len(reports),'preserved_files':len(tops),'disc_bytes':binary.stat().st_size,'disc_sha256':disc_sha,'zip_bytes':archive.stat().st_size,'zip_sha256':digest(tops[archive.name]),'previous_preserved_verified':prior.name if prior else None}
    if cc_summary is not None:report['collision_chaos']=cc_summary
    (ROOT/'build'/f'release-v{int(version.split(".")[1])}-readback.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main();run_prune()
