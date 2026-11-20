#!/usr/bin/env python3
"""Bundle the verified disc, reports, instructions and captures for private testing.

LOCAL USE ONLY. The ZIP this script writes contains SEGA-owned data and must
never be uploaded, attached to a release or shared in any other way. It exists
so the maintainer can test a build on their own hardware.
"""
import hashlib
import json
import os
import pathlib
import re
import shutil
import struct
import sys
import zipfile
import zlib
import wave
FLAG='--local-only-i-will-not-share'
ENV_VAR='SONIC_CD_SATURN_LOCAL_BUNDLE'
ENV_VALUE='i-will-not-share'
WARNING=f"""WARNING: tools/bundle.py makes a PRIVATE, LOCAL-ONLY bundle.
The ZIP contains SEGA-owned data and must NOT be distributed, uploaded,
attached to a GitHub release or shared in any way. It includes:
  - the built BIN/CUE, which carries data and audio from your Sonic CD disc
    and art converted from the scddisasm data files;
  - PNG screenshots of SEGA game art captured from the emulator;
  - a WAV preview rendered from the original sound data;
  - QA reports, traces and logs with retail disc hashes, file offsets and
    memory addresses taken from the original game.
Use it only on hardware you own, with a disc you own."""
if FLAG not in sys.argv[1:] and os.environ.get(ENV_VAR)!=ENV_VALUE:
    print(WARNING,file=sys.stderr)
    raise SystemExit(f'Refusing to run. Pass {FLAG} or set {ENV_VAR}={ENV_VALUE} to confirm local use only.')
print(WARNING,file=sys.stderr)
ROOT=pathlib.Path(__file__).resolve().parents[1]
DIST=ROOT/'dist'
NAME='sonic-cd-saturn-prototype'
sha=hashlib.sha256((DIST/f'{NAME}.bin').read_bytes()).hexdigest()
for filename in ['player-report.json','emulator-report.json','audio-report.json','audio-diagnostic-report.json','world-report.json','act-report.json','act2-report.json','act3-report.json','sequence-report.json','bigring-report.json','title-report.json','special-report.json','special-game-report.json','qa-report.json']:
    report=json.loads((DIST/filename).read_text())
    if report.get('disc_sha256')!=sha:raise SystemExit(f'{filename} is stale; rerun validation')
    if filename=='player-report.json' and not report.get('target_matches_host'):raise SystemExit('Missing SH-2 validation')
qa=json.loads((DIST/'qa-report.json').read_text())
if not qa.get('passed') or qa.get('mode')!='full':raise SystemExit('Missing full QA pass')
qq_files=[]
ppz_files=[]
cc_files=[]
zone_files=[]
if re.search(r'^IP_VERSION:= V0\.0(7[6-9]|80)$',(ROOT/'Makefile').read_text(),re.M):
    from zone_release_evidence import audit as audit_zones
    _,artifacts=audit_zones(ROOT,qa,sha)
    for source,name in artifacts:
        dest=DIST/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,dest);zone_files.append(dest)
    audit_zones(ROOT,qa,sha,staged=True)
if re.search(r'^IP_VERSION:= V0\.066$',(ROOT/'Makefile').read_text(),re.M):
    from check_qq_candidate import audit as audit_qq
    qq=json.loads((DIST/'qq-acceptance.json').read_text())
    assert qq.get('passed') and qq.get('disc_sha256')==sha,'Missing final-hash QQ candidate audit'
    for name,expected in qq['source_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,('Rerun QQ audit after verifier changes',name)
    checked,proof=audit_qq(pathlib.Path(qq['full_run']),pathlib.Path(qq['profile']))
    assert checked==sha
    for name,expected in qq['evidence'].items():
        path=(DIST/name).resolve();assert path.is_relative_to(DIST.resolve())
        assert hashlib.sha256(path.read_bytes()).hexdigest()==expected,('Changed QQ evidence',name)
        qq_files.append(path)
    for source in proof:
        name='qq-evidence/'+'__'.join(source.relative_to(ROOT).parts)
        assert qq['evidence'][name]==hashlib.sha256(source.read_bytes()).hexdigest(),('Stale staged QQ proof',name)
    qq_files.append(DIST/'qq-acceptance.json')
    for name in ['RELEASE-NOTES-V0.066.md','QUARTZ-QUADRANT-PLAN.md']:
        if name.startswith('RELEASE-'):assert 'unreleased draft' not in (ROOT/name).read_text().lower(),'Finalize release notes before bundling'
        shutil.copyfile(ROOT/name,DIST/name);qq_files.append(DIST/name)
if re.search(r'^IP_VERSION:= V0\.067$',(ROOT/'Makefile').read_text(),re.M):
    ppz_dir=DIST/'ppz-evidence';ppz_dir.mkdir(exist_ok=True)
    for act,eras in [(1,'ABCD'),(2,'ABCD'),(3,'CD')]:
        for era in eras:
            route=ROOT/f'build/ppz{act}/controller/{era}'
            report=json.loads((route/'report.json').read_text())
            assert report.get('passed') and report.get('disc_sha256')==sha,('Missing final-hash PPZ route',act,era)
            for name,expected in report['inputs'].items():
                assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,('PPZ verifier input changed',name)
            script=ROOT/report['script_source']
            assert hashlib.sha256(script.read_bytes()).hexdigest()==report['script_sha256'],('PPZ route script changed',act,era)
            for source,name in [(route/'report.json',f'ppz{act}{era}-report.json'),
                                (route/'results.log',f'ppz{act}{era}-results.log'),
                                (script,f'ppz{act}{era}-controller.txt')]:
                dest=ppz_dir/name;shutil.copyfile(source,dest);ppz_files.append(dest)
    for name in ['RELEASE-NOTES-V0.067.md','PALMTREE-PANIC-PLAN.md']:
        dest=DIST/name;shutil.copyfile(ROOT/name,dest);ppz_files.append(dest)
if re.search(r'^IP_VERSION:= V0\.(068|069|070|071|072|073|074)$',(ROOT/'Makefile').read_text(),re.M):
    required=[['python3','tools/test_cc_scroll_target.py'],
              ['python3','tools/test_cc_entry_scene.py'],
              ['python3','tools/test_cc_plane.py']]
    passed_steps={tuple(step['command']) for step in qa['steps'] if step['exit_code']==0}
    for command in required:assert tuple(command) in passed_steps,('Missing CC full-QA gate',command)
    cc_dir=DIST/'cc-evidence';cc_dir.mkdir(exist_ok=True)
    def cc_copy(source,name):
        dest=cc_dir/name;shutil.copyfile(source,dest);cc_files.append(dest)
    def cc_inputs(report,key='inputs'):
        for name,expected in report.get(key,{}).items():
            assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,('CC verifier input changed',name)
    for act,eras in [(1,'ABCD'),(2,'ABCD'),(3,'CD')]:
        for era in eras:
            route=ROOT/f'build/cc{act}/controller/{era}'
            report=json.loads((route/'report.json').read_text())
            assert report.get('passed') and report.get('disc_sha256')==sha,('Missing final-hash CC route',act,era)
            assert report.get('respawns')==0 and not report.get('late_gameplay_intervals'),('CC route defect',act,era)
            cc_inputs(report)
            for source,key in [('script.txt','script_sha256'),('controller.txt','pad_sha256')]:
                assert hashlib.sha256((route/source).read_bytes()).hexdigest()==report[key],('CC route script changed',act,era,source)
            for source,dest in [('report.json','report.json'),('results.log','results.log'),
                                ('script.txt','script.txt'),('controller.txt','controller.txt')]:
                cc_copy(route/source,f'cc{act}{era}-{dest}')
    campaign=json.loads((ROOT/'build/cc2/campaign/report.json').read_text())
    assert campaign.get('passed') and campaign.get('disc_sha256')==sha,'Missing final-hash CC campaign'
    cc_inputs(campaign,'host_inputs')
    cc_copy(ROOT/'build/cc2/campaign/report.json','campaign-report.json')
    for source,dest in [('build/cc-plane/report.json','plane-report.json'),
                        ('build/cc-scroll-target/report.json','scroll-target-report.json'),
                        ('build/cc-entry-scene/report.json','entry-scene-report.json'),
                        ('build/zone-art-qa/report.json','zone-art-report.json')]:
        report=json.loads((ROOT/source).read_text())
        assert report.get('status')=='passed' and report.get('passed',True),'Missing CC evidence: '+source
        if 'disc_sha256' in report:assert report['disc_sha256']==sha,'Stale CC evidence: '+source
        cc_inputs(report,'input_sha256' if 'input_sha256' in report else 'inputs')
        cc_copy(ROOT/source,dest)
    entry=json.loads((ROOT/'build/cc-entry-scene/report.json').read_text())
    scroll=json.loads((ROOT/'build/cc-scroll-target/report.json').read_text())
    assert entry['target_report_sha256']==hashlib.sha256((ROOT/'build/cc-scroll-target/report.json').read_bytes()).hexdigest()
    assert set(entry['programs'])==set(scroll['programs'])=={f'R3{act}{era}' for act,eras in [(1,'ABCD'),(2,'ABCD'),(3,'CD')] for era in eras}
    for name,row in entry['programs'].items():
        source=ROOT/f'build/cc-entry-scene/{name}-original.png'
        target=ROOT/f'build/cc-scroll-target/{name}/zones-1-t0180.ppm'
        moving_source=ROOT/f'build/cc-entry-scene/{name}-moving-original.png'
        moving_target=ROOT/f'build/cc-scroll-target/{name}/zones-1-t0240.ppm'
        assert hashlib.sha256(source.read_bytes()).hexdigest()==row['source_image_sha256']
        assert hashlib.sha256(target.read_bytes()).hexdigest()==row['target_image_sha256']==scroll['programs'][name]['entry_image_sha256']
        assert hashlib.sha256(moving_source.read_bytes()).hexdigest()==row['moving_source_image_sha256']
        assert hashlib.sha256(moving_target.read_bytes()).hexdigest()==row['moving_target_image_sha256']==scroll['programs'][name]['moving_image_sha256']
        cc_copy(source,f'{name}-original.png')
        cc_copy(target,f'{name}-target.ppm')
        cc_copy(moving_source,f'{name}-moving-original.png')
        cc_copy(moving_target,f'{name}-moving-target.ppm')
    if re.search(r'^IP_VERSION:= V0\.(069|070|071|072|073|074)$',(ROOT/'Makefile').read_text(),re.M):
        palette_path=ROOT/'build/cc-emie-palette/final-report.json'
        palette=json.loads(palette_path.read_text())
        assert palette['status']=='passed' and palette['disc_sha256']==sha,'Missing final-hash EMIE3 comparison'
        assert palette['emie_region']['exact_pixels']==palette['emie_region']['pixels']==925
        assert palette['scroll_report_sha256']==hashlib.sha256((ROOT/'build/cc-scroll-target/report.json').read_bytes()).hexdigest()
        cc_inputs(palette)
        for source,expected in [(ROOT/'build/cc-scroll-target/R31A/results.log','results_sha256'),
                                (ROOT/'build/cc-scroll-target/R31A/zones-1-t0360.ppm','target_image_sha256'),
                                (ROOT/'build/cc-emie-palette/R31A-frame360-original.png','source_image_sha256')]:
            assert hashlib.sha256(source.read_bytes()).hexdigest()==palette[expected],('EMIE3 evidence changed',source)
        cc_copy(palette_path,'emie-palette-report.json')
        cc_copy(ROOT/'build/cc-emie-palette/R31A-frame360-original.png','emie-frame360-original.png')
        cc_copy(ROOT/'build/cc-scroll-target/R31A/zones-1-t0360.ppm','emie-frame360-target.ppm')
    version=re.search(r'^IP_VERSION:= (V0\.\d+)$',(ROOT/'Makefile').read_text(),re.M)[1]
    for name in [f'RELEASE-NOTES-{version}.md','COLLISION-CHAOS-PLAN.md']:
        assert 'unreleased draft' not in (ROOT/name).read_text().lower(),'Finalize CC release notes before bundling'
        cc_copy(ROOT/name,name)
for name,digest in qa.get('report_hashes',{}).items():
    if hashlib.sha256((DIST/name).read_bytes()).hexdigest()!=digest:raise SystemExit(f'{name} changed after the QA pass')
act=json.loads((DIST/'act-report.json').read_text())
if not act.get('passed') or hashlib.sha256((ROOT/'build/act-qa/player-target-trace.txt').read_bytes()).hexdigest()!=act['trace_sha256']:raise SystemExit('Act trace changed after validation')
act2=json.loads((DIST/'act2-report.json').read_text())
if not act2.get('passed') or hashlib.sha256((ROOT/'build/act2-qa/player-target-trace.txt').read_bytes()).hexdigest()!=act2['trace_sha256']:raise SystemExit('Act 2 trace changed after validation')
act3=json.loads((DIST/'act3-report.json').read_text())
if not act3.get('passed') or hashlib.sha256((ROOT/'build/act3-qa/player-target-trace.txt').read_bytes()).hexdigest()!=act3['trace_sha256']:raise SystemExit('Act 3 trace changed after validation')
shutil.copyfile(ROOT/'README.md',DIST/'README.md')
shutil.copyfile(ROOT/'sources.lock.json',DIST/'sources.lock.json')
for name in ['QA-PLAN.md','OBJECT-COVERAGE.md','PLAN.md']:shutil.copyfile(ROOT/name,DIST/name)
shutil.copyfile(ROOT/'build/player-source.json',DIST/'player-source.json')
shutil.copyfile(ROOT/'build/object-source.json',DIST/'object-source.json')
shutil.copyfile(ROOT/'build/feedback-source.json',DIST/'feedback-source.json')
shutil.copyfile(ROOT/'build/audit/report.json',DIST/'source-audit.json')
evidence=DIST/'evidence';evidence.mkdir(exist_ok=True)
for source,name in [('build/special-effects-source.json', 'special-effects-source.json'),('build/special-reference/effect-report.json', 'special-effect-report.json'),('build/special-reference/effect-art-report.json', 'special-effect-art-report.json'),('build/special-reference/effect-art-fixtures.json', 'special-effect-art-fixtures.json'),('build/special-reference/effect-dispatch-report.json', 'special-effect-dispatch-report.json'),('build/special-reference/effect-loop-report.json', 'special-effect-loop-report.json'),('build/special-reference/contact-report.json','special-contact-report.json'),('build/special-sonic-source.json','special-sonic-source.json'),('build/special-reference/sprite-report.json','special-sprite-report.json'),('build/special-reference/sprite-fixtures.json','special-sprite-fixtures.json'),('build/special-reference/animation-report.json','special-animation-report.json'),('build/special-reference/animation-fixtures.json','special-animation-fixtures.json'),('build/special-reference/player-report.json','special-player-report.json'),('build/special-reference/air-fixtures.json','special-air-fixtures.json'),('build/special-reference/report.json','special-reference.json'),('build/special-reference/fixtures.json','special-fixtures.json'),('build/special-source.json','special-source.json'),('build/special-qa/results.log','special-results.log'),('build/special-ufo-source.json','special-ufo-source.json'),('build/special-reference/ufo-report.json','special-ufo-report.json'),('build/special-reference/reward-report.json','special-reward-report.json'),('build/special-reference/ufo-art-report.json','special-ufo-art-report.json'),('build/special-reference/ufo-art-fixtures.json','special-ufo-art-fixtures.json'),('build/special-reference/stage-report.json','special-stage-report.json')]:shutil.copyfile(ROOT/source,evidence/name)
shutil.copyfile(ROOT/'tools/object-art-baseline.json',evidence/'object-art-baseline.json')
def chunk(kind,data):
    return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
# Standard-library PNG encoding for emulator RGB captures.
captures={name: ROOT/f'build/emulator-qa/{name}.ppm' for name in json.loads((DIST/'emulator-report.json').read_text())['captures']}
captures['audio-diagnostics']=ROOT/'build/diagnostic-qa/audio-diagnostics.ppm'
for name in json.loads((DIST/'world-report.json').read_text())['captures']:captures[name]=ROOT/f'build/world-qa/{name}.ppm'
for name in json.loads((DIST/'act-report.json').read_text())['captures']:captures[name]=ROOT/f'build/act-qa/{name}.ppm'
for name in act2['captures']:captures[name]=ROOT/(f'build/act2-qa/travel-past/{name}.ppm' if name.startswith('act2-travel') else f'build/act2-qa/{name}.ppm')
for name in act3['captures']:captures[name]=ROOT/f'build/act3-qa/{name}.ppm'
for name in json.loads((DIST/'bigring-report.json').read_text())['captures']:captures[name]=ROOT/f'build/bigring-qa/{name}.ppm'
for name in json.loads((DIST/'title-report.json').read_text())['captures']:captures[name]=ROOT/f'build/title-qa/{name}.ppm'
for name in json.loads((DIST/'sequence-report.json').read_text())['captures']:captures['sequence-'+name]=ROOT/f'build/sequence-qa/{name}.ppm'
for name in [f'special-{stage}-{capture}' for stage in range(1,9) for capture in range(4)]+['special-return']:captures[name]=ROOT/f'build/special-qa/{name}.ppm'
for n in range(1,9):captures[f'special-effect-{n}']=ROOT/f'build/special-qa/special-effect-{n}.ppm'
for n in range(3):captures[f'special-sonic-{n}']=ROOT/f'build/special-qa/special-sonic-{n}.ppm'
for f in range(2):
    for c in range(2):captures[f'special-ufo-{f}-{c}']=ROOT/f'build/special-qa/special-ufo-{f}-{c}.ppm'
# Special Stage 1 program captures named in the hash-bound report.
for key in json.loads((DIST/'special-game-report.json').read_text())['captures']:
    captures[f'special-game-{key}']=sorted((ROOT/'build/special-game-qa').glob(f'special-game-{key}-*.ppm'))[-1]
for name,path in captures.items():
    with path.open('rb') as file:
        assert file.readline()==b'P6\n';width,height=map(int,file.readline().split())
        assert file.readline()==b'255\n';rgb=file.read()
    assert len(rgb)==width*height*3
    filtered=b''.join(b'\0'+rgb[y*width*3:(y+1)*width*3] for y in range(height))
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(filtered,9))+chunk(b'IEND',b'')
    (evidence/f'{name}.png').write_bytes(png)
shutil.copyfile(ROOT/'build/emulator-qa/results.log',evidence/'results.log')
shutil.copyfile(ROOT/'build/special-game-qa/results.log',evidence/'special-game-results.log')
shutil.copyfile(ROOT/'build/audio-qa/results.log',evidence/'audio-results.log')
shutil.copyfile(ROOT/'build/diagnostic-qa/results.log',evidence/'audio-diagnostic-results.log')
shutil.copyfile(ROOT/'build/spring-contact-results.log',evidence/'spring-contact-results.log')
shutil.copyfile(ROOT/'build/world-qa/results.log',evidence/'world-results.log')
for source,name in [('results.log','act-results.log'),('host-results.log','act-host-results.log'),('player-target-trace.txt','act-target-trace.txt')]:shutil.copyfile(ROOT/'build/act-qa'/source,evidence/name)
for source,name in [('results.log','act2-results.log'),('host-results.log','act2-host-results.log'),('player-target-trace.txt','act2-target-trace.txt')]:shutil.copyfile(ROOT/'build/act2-qa'/source,evidence/name)
shutil.copyfile(ROOT/'build/mmd-extract.json',evidence/'mmd-extract.json')
shutil.copyfile(ROOT/'build/bigring-qa/results.log',evidence/'bigring-results.log')
shutil.copyfile(ROOT/'build/title-qa/results.log',evidence/'title-results.log')
shutil.copyfile(ROOT/'build/title-host/report.json',evidence/'title-host-report.json')
for source,name in [('results.log','act3-results.log'),('host-results.log','act3-host-results.log'),('player-target-trace.txt','act3-target-trace.txt')]:shutil.copyfile(ROOT/'build/act3-qa'/source,evidence/name)
for source,name in [('results.log','sequence-results.log'),('host-act1.log','sequence-host-act1.log'),('host-act2.log','sequence-host-act2.log'),('host-act3.log','sequence-host-act3.log')]:shutil.copyfile(ROOT/'build/sequence-qa'/source,evidence/name)
for step in qa['steps']:
    if step['command']==['python3','tools/test_objects.py']:
        shutil.copyfile(ROOT/step['log'],evidence/'object-asset-results.log')
    if step['command']==['bash','tools/test-world.sh']:
        shutil.copyfile(ROOT/step['log'],evidence/'world-host-results.log')
with wave.open(str(evidence/'feedback-preview.wav'),'wb') as wav:
    wav.setnchannels(2);wav.setsampwidth(2);wav.setframerate(44100)
    wav.writeframes((ROOT/'build/emulator-qa/feedback-preview.raw').read_bytes())
for source,name in [('build/player-host-trace.txt','player-host-trace.txt'),('build/player-reference-trace.txt','player-reference-trace.txt'),('build/emulator-qa/player-target-trace.txt','player-target-trace.txt')]:
    shutil.copyfile(ROOT/source,evidence/name)
files=[DIST/f'{NAME}.bin',DIST/f'{NAME}.cue']+[DIST/n for n in ['README.md','QA-PLAN.md','OBJECT-COVERAGE.md','PLAN.md','sources.lock.json','world-report.json','act-report.json','act2-report.json','act3-report.json','sequence-report.json','bigring-report.json','title-report.json','special-report.json','special-game-report.json','qa-report.json','build-report.json','audio-report.json','audio-diagnostic-report.json','emulator-report.json','player-report.json','player-source.json','object-source.json','feedback-source.json','source-audit.json']]
files += [evidence/f'{n}.png' for n in captures]
files += [evidence/n for n in ['act2-results.log','act2-host-results.log','act2-target-trace.txt','mmd-extract.json','act3-results.log','act3-host-results.log','act3-target-trace.txt','bigring-results.log','title-results.log','title-host-report.json','sequence-results.log','sequence-host-act1.log','sequence-host-act2.log','sequence-host-act3.log']]
files += [evidence/n for n in ['special-effects-source.json','special-effect-report.json','special-effect-art-report.json','special-effect-art-fixtures.json','special-effect-dispatch-report.json','special-effect-loop-report.json','special-contact-report.json','special-sonic-source.json','special-sprite-report.json','special-sprite-fixtures.json','special-animation-report.json','special-animation-fixtures.json','special-player-report.json','special-air-fixtures.json','special-reference.json','special-fixtures.json','special-source.json','special-results.log','special-ufo-source.json','special-ufo-report.json','special-reward-report.json','special-ufo-art-report.json','special-ufo-art-fixtures.json','special-stage-report.json','special-game-results.log','object-art-baseline.json','object-asset-results.log','act-results.log','act-host-results.log','act-target-trace.txt','world-host-results.log','world-results.log','results.log','audio-results.log','audio-diagnostic-results.log','spring-contact-results.log','feedback-preview.wav','player-host-trace.txt','player-reference-trace.txt','player-target-trace.txt']]
archive=DIST/f'{NAME}.zip'
files += qq_files
files += ppz_files
files += cc_files
files += zone_files
version=re.search(r'^IP_VERSION:= (V0\.\d+)$',(ROOT/'Makefile').read_text(),re.M)[1]
for source,name in [(ROOT/f'RELEASE-NOTES-{version}.md',f'RELEASE-NOTES-{version}.md'),(ROOT/'HARDWARE-ACCEPTANCE.md','READ-ME-FIRST.md')]:
    assert version in source.read_text().splitlines()[0],('Stale release handoff',source)
    assert 'PENDING' not in source.read_text(),('Unfilled release draft',source)
    shutil.copyfile(source,DIST/name);files.append(DIST/name)
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as zip:
    for path in sorted(files):
        info=zipfile.ZipInfo(str(path.relative_to(DIST)),(2026,9,12,0,0,0))
        info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
        zip.writestr(info,path.read_bytes())
with zipfile.ZipFile(archive) as zip:
    assert zip.testzip() is None
print(f'Verified bundle: {archive.name} ({archive.stat().st_size:,} bytes)')
print('Reminder: this ZIP contains SEGA data. Keep it local. Do not distribute it.',file=sys.stderr)
