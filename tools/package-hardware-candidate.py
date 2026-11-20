#!/usr/bin/env python3
"""Preserve a focused diagnostic candidate; NEVER label it a full-QA release."""
import argparse,hashlib,json,re,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];DIST=ROOT/'dist';NAME='sonic-cd-saturn-prototype'
version=re.search(r'^IP_VERSION:= V(\d+\.\d+)$',(ROOT/'Makefile').read_text(),re.M)[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--build-log',type=Path,required=True,help='Log from building the candidate BIN')
parser.add_argument('--pacing-dir',type=Path,help='Directory containing the matching pacing report and log')
parser.add_argument('--journey-dir',type=Path,help='Verified, uninstrumented complete Good Future journey directory')
args=parser.parse_args()
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
target=ROOT/'build'/f'hardware-candidate-v{version}-01'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
disc=digest(DIST/f'{NAME}.bin')
symbols=subprocess.check_output([str(ROOT/'.toolchain/bin/sh-elf-nm'),str(ROOT/'build/saturn'/f'{NAME}.elf')],text=True)
assert '_scd_frame_profile' not in symbols,'Disable temporary frame profiling and rebuild before packaging'
reports=['emulator-report.json','player-report.json','audio-report.json','audio-diagnostic-report.json','act-report.json','title-report.json']
for name in reports:
    data=json.loads((DIST/name).read_text());assert data['disc_sha256']==disc,('Stale report',name)
    if name=='player-report.json':assert data['target_matches_host']
    if name=='act-report.json':assert data['passed'] and data['original_hud_pixels']>1000
    if name=='title-report.json':
        assert data['passed'] and not data['state_mismatches'] and data['vints']==823
        assert data['pictures']['mismatched_pixels']==0
    if name=='emulator-report.json':assert data['automated_scene_checks']=='pass'
    if name=='audio-report.json':
        assert data['pause_silent'] and data['resume_and_present_repeat'] and data['bad_future_track_repeat']
        assert data['effect_mix_mean_square_difference']>0 and all(t['mean_square']>10000 for t in data['tracks'])
    if name=='audio-diagnostic-report.json':
        assert data['driver_ready_and_sound_ram_checksum']=='pass' and data['exit_resumes_music']
        assert len(data['probes'])==3 and all(energy>=10000 for energy in data['probes'].values())
build=json.loads((DIST/'build-report.json').read_text())
for suffix in ('bin','cue'):
    path=DIST/f'{NAME}.{suffix}';assert digest(path)==build['files'][path.name]['sha256']
assert f'V{version}'.encode() in (DIST/f'{NAME}.bin').read_bytes()[:2352*32]
files={f'{NAME}.{suffix}':DIST/f'{NAME}.{suffix}' for suffix in ('bin','cue')}
files.update({name:DIST/name for name in reports+['build-report.json']})
if (ROOT/'src/sonic_view.inc').exists():
    for name in ['player-visual-report.json','sonic-render-report.json']:
        report=json.loads((DIST/name).read_text())
        assert report['passed'] and report['disc_sha256']==disc,('Stale Sonic integration evidence',name)
        for path,expected in report.get('source_sha256',{}).items():
            assert digest(ROOT/path)==expected,('Stale Sonic source',path)
        for path,expected in report.get('trace_sha256',{}).items():
            assert digest(ROOT/path)==expected,('Stale Sonic state trace',path)
            files['sonic-'+Path(path).name]=ROOT/path
        for capture in report.get('captures',[]):
            path=ROOT/'build/emulator-qa'/(capture['name']+'.ppm')
            assert digest(path)==capture['sha256'],('Changed Sonic picture',path)
            files[path.name]=path
        files[name]=DIST/name
    audit=ROOT/'build/player-animation/report.json';data=json.loads(audit.read_text())
    assert data['passed'] and sum(r['calls'] for r in data['routes'].values())>=85000
    for name,expected in data['source_sha256'].items():assert digest(ROOT/name)==expected,('Stale player animation audit',name)
    files['player-animation-audit.json']=audit
    for name,record in data['routes'].items():
        path=audit.parent/(name+'.bin');assert digest(path)==record['sha256']
        files['player-animation-'+name+'.bin']=path
    pack=ROOT/'build/sonic-animation/frame-pack-report.json';data=json.loads(pack.read_text())
    assert data['passed'] and data['frames']==198 and data['pixels']==811008
    assert digest(ROOT/'assets/generated/sonic-frames.bin')==data['pack_sha256']
    for name,expected in data['source_sha256'].items():assert digest(ROOT/name)==expected,('Stale frame pack evidence',name)
    files['sonic-frame-pack-report.json']=pack
if (ROOT/'tools/test_player_air_animation.py').exists():
    proof=ROOT/'build/player-air-animation/report.json';data=json.loads(proof.read_text())
    assert data['passed'] and data['cases']==2400 and data['spring_apex_transitions']==[73]
    for name,expected in data['source_sha256'].items():assert digest(ROOT/name)==expected,('Stale air selection evidence',name)
    assert digest(ROOT/'.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib')==data['core_sha256']
    raw=proof.parent/'native.log';assert digest(raw)==data['log_sha256']
    files['player-air-animation-report.json']=proof;files['player-air-animation.log']=raw
    motion=json.loads((DIST/'sonic-render-report.json').read_text())['spring_motion']
    assert motion['consecutive_pictures']==33 and len(motion['transition_frames'])==1
    comparison=DIST/'air-regression-report.json';data=json.loads(comparison.read_text())
    assert data['passed'] and data['disc_sha256']==disc
    assert digest(ROOT/'tools/check_air_regression.py')==data['checker_sha256']
    assert all(r['all_other_bits_identical'] for r in data['routes'].values())
    for name,expected in data['evidence_sha256'].items():
        path=ROOT/name;assert digest(path)==expected,('Stale air regression trace',name)
        files['air-regression-'+name.replace('/','-')]=path
    files['air-regression-report.json']=comparison
if (ROOT/'src/title_vram.h').exists():
    title=json.loads((DIST/'title-report.json').read_text())
    assert not title['vdp2_cycle_schedule']['errors']
    state=ROOT/'build/title-qa/title-v120.state'
    assert digest(state)==title['vdp2_state_sha256']
    assert digest(ROOT/'.deps/beetle-saturn/mednafen_saturn_libretro.dylib')==title['emulator_core_sha256']
    for name,expected in title['vdp2_check_source_sha256'].items():
        assert digest(ROOT/name)==expected,('Stale title hardware-cycle evidence',name)
    files['title-v120.state']=state
if (ROOT/'src/sprite_order.h').exists():
    proof=ROOT/'build/sprite-order/report.json';data=json.loads(proof.read_text())
    assert data['passed'] and data['cases']==512 and data['retail_calls']==39881 and data['priority_cases']==180224
    for name,expected in (data['source_sha256']|data['priority_source_sha256']).items():
        assert digest(ROOT/name)==expected,('Stale sprite-order evidence',name)
    assert digest(ROOT/'.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib')==data['core_sha256']
    raw=proof.parent/'retail-cases.bin';assert digest(raw)==data['cases_sha256']
    files['sprite-order-report.json']=proof;files['sprite-order-retail-cases.bin']=raw
    files['sprite-order-sanitized.log']=proof.parent/'sanitized.log'
    comparison=DIST/'sprite-order-regression-report.json';data=json.loads(comparison.read_text())
    assert data['passed'] and data['disc_sha256']==disc and len(data['rejected_old_pictures'])==6
    assert sum(data['exact_gameplay_states'].values())==32916
    for name,expected in data['source_sha256'].items():
        assert digest(ROOT/name)==expected,('Stale sprite-order regression checker',name)
    for name,expected in data['evidence_sha256'].items():
        path=ROOT/name;assert digest(path)==expected,('Stale sprite-order regression evidence',name)
        files['sprite-order-regression-'+name.replace('/','-')]=path
    files['sprite-order-regression-report.json']=comparison
if (ROOT/'src/powerup_runtime.c').exists():
    proof=ROOT/'build/powerup-visual/report.json';data=json.loads(proof.read_text())
    assert data['passed'] and data['cases']==36948 and len(data['frames'])==47
    for name,expected in data['source_sha256'].items():assert digest(ROOT/name)==expected,('Stale effect actor proof',name)
    raw=proof.parent/'retail-cases.bin';assert digest(raw)==data['cases_sha256']
    files['powerup-visual-report.json']=proof;files['powerup-visual-cases.bin']=raw
    files['powerup-visual-sanitized.log']=proof.parent/'sanitized.log'
    folder=ROOT/'build/powerup-runtime'
    for name in ['report.json','culling-report.json']:
        data=json.loads((folder/name).read_text());assert data['passed']
        for path,expected in data['source_sha256'].items():assert digest(ROOT/path)==expected,('Stale effect integration proof',path)
        if name=='report.json':
            assert data['culling_cases']==13211 and data['late_grant_tick']==33
            assert digest(folder/'sanitized.log')==data['log_sha256']
            assert digest(folder/'culling-report.json')==data['culling_report_sha256']
        else:
            assert data['cases']==13211 and digest(folder/'culling-retail-cases.bin')==data['cases_sha256']
        files['powerup-runtime-'+name]=folder/name
    for name in ['sanitized.log','culling-retail-cases.bin']:files['powerup-runtime-'+name]=folder/name
    for name in ['powerup-target-report.json','powerup-render-report.json']:
        data=json.loads((DIST/name).read_text());assert data['passed'] and data['disc_sha256']==disc
        for path,expected in data['source_sha256'].items():assert digest(ROOT/path)==expected,('Stale target effect source',path)
        if name=='powerup-target-report.json':
            # Faster rendering can capture one extra active shield update at a
            # fixture boundary. Re-execute the untouched retail oracle and
            # require the entire existing report, not an old aggregate count.
            from check_powerup_target import verify as verify_effect_target
            verified=json.loads(json.dumps(verify_effect_target()))
            assert data==verified,'Power-up proof differs on fresh original-code verification'
            assert data['rows']==23638 and data['original_cpu_calls']>=10000 and len(data['animation_mapping_pairs'])==47
            path=ROOT/'build/world-qa/effect-target-trace.txt';assert digest(path)==data['trace_sha256'];files[path.name]=path
        else:
            assert len(data['captures'])==310 and data['counts']['effect_overlap']>0 and data['counts']['sonic_overlap']>0
            for path,expected in data['original_sha256'].items():assert digest(ROOT/'.deps/scddisasm/src/Level'/path)==expected
            for capture in data['captures']:
                path=ROOT/'build/world-qa'/(capture['name']+'.ppm');assert digest(path)==capture['sha256'];files[path.name]=path
        files[name]=DIST/name
if (ROOT/'tools/test_player_arrival.py').exists():
    folder=ROOT/'build/player-arrival'
    current=json.loads((folder/'current-report.json').read_text())
    assert current['passed'] and current['cases']==2048 and current['display_cases']==2080 and not current['mismatches']
    for name in ['current','v052-original']:
        data=json.loads((folder/(name+'-report.json')).read_text())
        for path,expected in data['source_sha256'].items():assert digest(ROOT/path)==expected,('Stale arrival proof',path)
        assert digest(ROOT/'.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib')==data['core_sha256']
        assert digest(folder/(name+'.log'))==data['log_sha256']
        for suffix in ['-report.json','.log']:files['arrival-'+name+suffix]=folder/(name+suffix)
    proof=DIST/'arrival-regression-report.json';data=json.loads(proof.read_text())
    assert data['passed'] and data['disc_sha256']==disc and data['rejected_v052_arrivals']==2048
    assert data['target_display_states']==1200 and data['full_protection_countdowns']==2
    assert sum(data['exact_unrelated_gameplay_states'].values())==32916
    for name,expected in data['source_sha256'].items():assert digest(ROOT/name)==expected,('Stale target arrival proof',name)
    for name,expected in data['evidence_sha256'].items():
        path=ROOT/name;assert digest(path)==expected,('Stale arrival negative/target evidence',name)
        # The full baseline source archive is retained locally; the proof pins
        # its hash, while the exact old player source is included below.
        if not name.endswith('.tar.gz'):files['arrival-'+name.replace('/','-')]=path
    files['arrival-v052-player.c']=folder/'v052-source/src/player.c'
    files['arrival-regression-report.json']=proof
if (ROOT/'tools/test_player_checkpoint.py').exists():
    folder=ROOT/'build/player-checkpoint'
    proof=DIST/'checkpoint-regression-report.json';data=json.loads(proof.read_text())
    assert data['passed'] and data['disc_sha256']==disc and data['rejected_v053_checkpoints']==255
    assert data['host_cases']==259 and data['host_protected_updates']==30600 and data['target_countdown_states']==121
    assert sum(data['exact_unrelated_gameplay_states'].values())==32916
    for name,expected in data['source_sha256'].items():assert digest(ROOT/name)==expected,('Stale checkpoint source',name)
    for name,expected in data['evidence_sha256'].items():
        path=ROOT/name;assert digest(path)==expected,('Stale checkpoint evidence',name)
        if not name.endswith('.tar.gz'):files['checkpoint-'+name.replace('/','-')]=path
    files['checkpoint-v053-player.c']=folder/'v053-source/src/player.c'
    files['checkpoint-regression-report.json']=proof
# Preserve extra zone evidence only if it actually describes this candidate.
if (ROOT/'tools/test_checkpoint_clock.py').exists():
    proof=DIST/'checkpoint-clock-report.json';data=json.loads(proof.read_text())
    assert data['passed'] and data['disc_sha256']==disc
    assert data['host_cases']==1444 and data['host_states']==174724 and data['rejected_v055_cases']==1180
    assert data['target_clock_states']==121 and data['target_route_states']>=800
    assert data['saved_ticks']%60 and data['restored_ticks']==data['saved_ticks']//60*60
    assert len(data['pictures'])==2 and sum(p['pixels'] for p in data['pictures'].values())>=2600
    for name,expected in data['source_sha256'].items():assert digest(ROOT/name)==expected,('Stale checkpoint clock source',name)
    for name,expected in data['evidence_sha256'].items():
        path=ROOT/name;assert digest(path)==expected,('Stale checkpoint clock evidence',name)
        if not name.endswith('.tar.gz'):files['checkpoint-clock-'+name.replace('/','-')]=path
    files['checkpoint-clock-v055-player.c']=ROOT/'build/checkpoint-clock/v055-source/src/player.c'
    files['checkpoint-clock-report.json']=proof
world=DIST/'world-report.json'
if (ROOT/'src/gameplay_video.inc').exists():
    assert world.exists(),'Camera pipeline requires a current world report'
    assert json.loads(world.read_text()).get('disc_sha256')==disc,'Stale world/camera report'
if world.exists():
    data=json.loads(world.read_text())
    if data.get('disc_sha256')==disc:
        assert data['target_semantic_probe']=='pass'
        files[world.name]=world
        if (ROOT/'src/sprite_order.h').exists():
            ordering=data['sprite_order']
            assert ordering['report_sha256']==digest(ROOT/'build/sprite-order/report.json')
            assert ordering['monitor_overlap_pixels']>0
            for name,expected in ordering['source_sha256'].items():
                assert digest(ROOT/name)==expected,('Stale target ordering evidence',name)
        # Preserve the checked world pictures, not just their hashes. In
        # particular these include the six actual Sonic disc poses and the
        # source-verified Sonic/scenery overlap introduced with V0.049.
        for name,expected in data['captures'].items():
            path=ROOT/'build/world-qa'/(name+'.ppm')
            assert digest(path)==expected,('Changed world capture',name)
            files[path.name]=path
        if (ROOT/'tools/sprite_composition.py').exists():
            for name,expected in data['amy_verification_sources'].items():
                assert digest(ROOT/name)==expected,('Stale independent Amy evidence',name)
            for n in range(3):
                name=f'amy-hold-{n}.ppm';path=ROOT/'build/world-qa'/name
                assert digest(path)==data['captures'][name[:-4]],('Changed Amy capture',name)
                files[name]=path
            proof=ROOT/'build/sprite-composition-report.json'
            assert digest(proof)==data['sprite_composition']['report_sha256'],'Stale composition/world evidence'
            composition=json.loads(proof.read_text());assert composition['passed'] and composition['compositions']==403 and composition['object_frames']==394
            for name,expected in (composition['source_sha256']|composition['source_input_sha256']).items():
                assert digest(ROOT/name)==expected,('Stale source composition',name)
            for name,expected in composition['artifact_sha256'].items():
                assert digest(ROOT/'assets/generated'/name)==expected,('Stale composition artifact',name)
            files['sprite-composition-report.json']=proof
        if 'object_vram' in data:
            vram=ROOT/'build/world-qa/monitor-vdp1.bin'
            assert digest(vram)==data['object_vram_capture_sha256']
            for name,expected in data['monitor_verification_sources'].items():
                assert digest(ROOT/name)==expected,('Stale monitor evidence',name)
            files['monitor-vdp1.bin']=vram
        if (ROOT/'src/gameplay_video.inc').exists():
            camera=data['camera_coherence']
            assert camera['captures']==16 and camera['moving_captures']>=5
            assert camera['sprite_pixels']>=2000 and camera['clear_pixels']>=16000
            assert digest(ROOT/'build/world-qa/results.log')==camera['log_sha256']
            assert digest(ROOT/'.deps/beetle-saturn/mednafen_saturn_libretro.dylib')==camera['core_sha256']
            for name,expected in camera['source_sha256'].items():
                assert digest(ROOT/name)==expected,('Stale camera evidence',name)
            for name,expected in camera['evidence_sha256'].items():
                path=ROOT/'build/world-qa'/name;assert digest(path)==expected
                files[name]=path
            files['camera-world-results.log']=ROOT/'build/world-qa/results.log'
for name in ['act2-report.json','act3-report.json','sequence-report.json','bigring-report.json']:
    path=DIST/name
    if path.exists():
        data=json.loads(path.read_text())
        if data.get('disc_sha256')==disc:
            assert data['passed'];files[name]=path
            if name=='sequence-report.json' and 'pacing' in data:
                folder=ROOT/'build/sequence-qa'
                assert digest(folder/'results.log')==data['pacing_log_sha256']
                assert all(p['late']==0 for p in data['pacing'].values())
                for n,trace in [(1,'player-target-trace.txt'),(2,'act2-target-trace.txt'),(3,'act3-target-trace.txt')]:
                    assert digest(folder/trace)==data[f'act{n}_trace_sha256']
                    files['sequence-'+trace]=folder/trace
                for evidence in ['results.log','host-act1.log','host-act2.log','host-act3.log']:
                    files['sequence-'+evidence]=folder/evidence
if (ROOT/'src/arrival_camera.h').exists():
    assert args.journey_dir,'Arrival warmup candidate requires full Good Future journey evidence'
    folder=args.journey_dir if args.journey_dir.is_absolute() else ROOT/args.journey_dir
    proof=folder/'report.json';journey=json.loads(proof.read_text())
    assert journey['passed'] and journey['disc_sha256']==disc and not journey['instrumented_frame_profile']
    assert journey['states']==26029 and journey['words']==416464 and journey['progression_samples']==26029
    assert journey['generators']==2 and journey['good_flags']==3 and journey['act']==3 and journey['era']==2
    assert journey['zone_exit']['prototype'] and journey['zone_exit']['title']
    assert journey['pacing']['zero_late'] and journey['pacing']['intervals']==26023 and journey['pacing']['max_gap']==1
    for name,expected in journey['source_sha256'].items():assert digest(ROOT/name)==expected,('Stale journey source',name)
    for group in ['inputs','binaries']:
        for name,expected in journey['build_manifest'][group].items():assert digest(ROOT/name)==expected,('Stale journey build',name)
    for name,expected in journey['evidence_sha256'].items():
        path=ROOT/name;assert digest(path)==expected,('Changed journey evidence',name)
        files['journey-'+name.replace('/','-')]=path
    pixels=folder/'source-results-report.json';data=json.loads(pixels.read_text())
    assert data['passed'] and data['disc_sha256']==disc and data['negative_hud_mutation_rejected']
    assert sum(data[k] for k in ['hud_pixels','title_pixels','label_pixels','digit_pixels'])==7722
    for name,expected in (data['source_sha256']|data['evidence_sha256']).items():assert digest(ROOT/name)==expected,('Stale journey pixels',name)
    files['journey-report.json']=proof;files['journey-source-results-report.json']=pixels
    files['PPZ-JOURNEY-COVERAGE.md']=ROOT/'PPZ-JOURNEY-COVERAGE.md'
    files['object-stream-sanitized.log']=ROOT/'build/object-stream-v055.log'
    files['arrival-camera-sanitized.log']=ROOT/'build/arrival-camera-v055.log'
# Bind supplemental timing evidence to the actual trace/log, not just a version
# label. Older per-route folders are deliberately excluded from a newer disc.
for label,folder,report_name in [
    ('act1-timing',ROOT/'build/act-qa','pacing-report.json'),
    ('act2-timing',ROOT/'build/act2-qa','pacing-report.json'),
    ('past-ring-loss',ROOT/'build'/f'act2-past-stress-v{version.split(".")[1]}','report.json')]:
    report=folder/report_name
    if not report.exists():continue
    data=json.loads(report.read_text())
    if data.get('disc_sha256')!=disc:continue
    assert data.get('passed') or (data.get('measurement_complete') and data.get('route_gate_passed'))
    assert data['late']==0,('Route pacing regression',label)
    assert not data.get('instrumented_frame_profile',False)
    assert data['log_sha256']==digest(folder/'results.log')
    assert data['trace_sha256']==digest(folder/'player-target-trace.txt')
    files[label+'-report.json']=report
    for name in ['results.log','player-target-trace.txt','host-results.log']:
        files[label+'-'+name]=folder/name
files['READ-ME-FIRST.md']=ROOT/'HARDWARE-ACCEPTANCE.md'
assert f'V{version}' in files['READ-ME-FIRST.md'].read_text().splitlines()[0],'Hardware README version is stale'
for name in ['TITLE-HARDWARE-CYCLES.md','VISUAL-CORRECTNESS-V0.045.md','CAMERA-PRESENTATION.md','SPRITE-COMPOSITION.md','SPRITE-ORDER.md','SONIC-ANIMATION.md','AIR-ANIMATION.md','POWERUP-VISUAL.md','ARRIVAL-FIDELITY.md','CHECKPOINT-FIDELITY.md',f'RELEASE-NOTES-V{version}.md']:
    if (ROOT/name).exists():files[name]=ROOT/name
hud_report=ROOT/'build/hud-render/report.json'
if (ROOT/'src/hud_animation.h').exists():
    data=json.loads(hud_report.read_text());assert data['passed'] and data['cases']>=1088
    for name,expected in data['source_sha256'].items():assert digest(ROOT/name)==expected,('Stale HUD renderer evidence',name)
    for name,expected in data['original_art_sha256'].items():assert digest(ROOT/name)==expected,('Stale HUD source artwork',name)
    assert digest(ROOT/'.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib')==data['core_sha256']
    for name,expected in data['evidence_sha256'].items():
        path=hud_report.parent/name;assert digest(path)==expected,('Changed HUD evidence',name)
        files['hud-render-'+name]=path
    files['hud-render-report.json']=hud_report
    files['HUD-FIDELITY.md']=ROOT/'HUD-FIDELITY.md'
pacing=args.pacing_dir or ROOT/'build'/f'pacing-v{version.split(".")[1]}-qa'
if not pacing.is_absolute():pacing=ROOT/pacing
if (pacing/'report.json').exists():
    measurement=json.loads((pacing/'report.json').read_text())
    assert measurement['measurement_complete'] and measurement['disc_sha256']==disc
    assert measurement['late']==0,'Opening pacing regression'
    assert not measurement.get('instrumented_frame_profile',False)
    assert measurement['log_sha256']==digest(pacing/'results.log')
    files['pacing-report.json']=pacing/'report.json'
    files['pacing-results.log']=pacing/'results.log'
    files['PERFORMANCE.md']=ROOT/'PERFORMANCE.md'
else:
    for name in ['pacing-v037-detail.log',f'pacing-v{version.split(".")[1]}-final.log']:
        files[name]=ROOT/'build'/name
build_log=args.build_log if args.build_log.is_absolute() else ROOT/args.build_log
files[build_log.name]=build_log
if (ROOT/'src/cd_status.h').exists():
    files['cd-command-source-report.json']=ROOT/'build/cd-block/source-report.json'
fast=sorted((ROOT/'build/qa-loops').glob('*/report.json'))
fast=[p for p in fast if json.loads(p.read_text()).get('mode')=='fast'][-1]
assert json.loads(fast.read_text())['passed'];files['host-fast-report.json']=fast
sources={}
for name in ['tools/checkpoint_clock_test.c','tools/test_checkpoint_clock.py','tools/check_checkpoint_clock_target.py']:
    if (ROOT/name).exists():sources[name]=digest(ROOT/name)
for name in ['src/arrival_camera.h','tools/arrival_camera_test.c','tools/test-arrival-camera.sh',
             'tools/object_stream_test.c','tools/test-object-stream.sh','tools/ppz_journey.c',
             'tools/ppz_journey.py','tools/ppz_journey_manifest.py','tools/build-ppz-journey.sh',
             'tools/journey_replay.h','tools/check_ppz_journey.py','tools/check_journey_results.py',
             'tools/test-ppz-journey.sh']:
    if (ROOT/name).exists():sources[name]=digest(ROOT/name)
for name in ['tools/player_checkpoint_test.c','tools/test_player_checkpoint.py','tools/check_checkpoint_regression.py']:
    if (ROOT/name).exists():sources[name]=digest(ROOT/name)
for name in ['tools/player_arrival_test.c','tools/test_player_arrival.py','tools/check_arrival_regression.py']:
    if (ROOT/name).exists():sources[name]=digest(ROOT/name)
for name in ['src/powerup_visual.c','src/powerup_visual.h','src/powerup_runtime.c','src/powerup_runtime.h',
             'tools/powerup_assets.py','tools/test_powerup_visual.py','tools/powerup_visual_test.c',
             'tools/powerup_runtime_test.c','tools/test-powerup-runtime.sh','tools/powerup_runtime_report.py',
             'tools/test_powerup_culling.py','tools/check_powerup_target.py','tools/check_powerup_pixels.py',
             'tools/test-world-emulator.sh','assets/generated/powerup-animation.inc']:
    if (ROOT/name).exists():sources[name]=digest(ROOT/name)
for name in ['src/sprite_order.h','src/boss.c','src/scd_boss.h','tools/sprite_order_test.c',
             'tools/test_sprite_order.py','tools/sprite_priority_reference.py','tools/projector_pixels.py',
             'tools/check_sprite_order_regression.py']:
    if (ROOT/name).exists():sources[name]=digest(ROOT/name)
for name in ['tools/player_air_animation_test.c','tools/test_player_air_animation.py','tools/check_air_regression.py']:
    if (ROOT/name).exists():sources[name]=digest(ROOT/name)
for name in ['tools/package-hardware-candidate.py','tools/test-player.sh','tools/test-world.sh',
             'tools/test-spring-contacts.sh','tools/test-swing.sh','tools/test-act-emulator.sh',
             'tools/test-act2-emulator.sh','tools/test-act2-era-emulator.sh','tools/test-act3-emulator.sh',
             'tools/test-sequence-emulator.sh','tools/test-past-ring-loss.sh']:
    if (ROOT/name).exists():sources[name]=digest(ROOT/name)
for name in ['src/player.c','src/scd_player.h','src/sonic_animation.c','src/sonic_animation.h','src/sonic_art.c','src/sonic_art.h',
             'src/sonic_frames.c','src/sonic_frames.h','src/sonic_view.inc','src/stage_packs.h','src/world_qa.c','src/amy_qa.inc',
             'tools/build.sh','tools/sonic_animation_assets.py','tools/sonic_frame_assets.py','tools/test_sonic_animation.py',
             'tools/test_player_animation.py','tools/player_animation_audit.c','tools/player_animation_order_test.c',
             'tools/sonic_view_test.c','tools/test-sonic-view.sh','tools/check_player_visual.py','tools/check_sonic_pixels.py']:
    sources[name]=digest(ROOT/name)
for name in ['Makefile','src/audio.c','src/audio.h','src/sound_bus.h','src/main.c','src/hud_view.inc','src/title_view.inc','src/title_scale.h','tools/prepare_feedback.py','tools/hud_assets.py','tools/title_assets.py','tools/check_title.py','tools/test_hud.py','tools/title_scale_test.c','tools/qa-loop.py']:
    sources[name]=digest(ROOT/name)
for name in ['src/cd_status.h','tools/prepare_cd_block.py','tools/cd_status_test.c','tools/cd_block_mock.h']:
    if (ROOT/name).exists():sources[name]=digest(ROOT/name)
for name in ['src/background.c','src/background.h','src/background_cache.h','tools/background_lines_test.c','tools/background_cache_test.c','tools/test-background-cache.sh','tools/test-pacing.sh','tools/check_pacing.py']:
    if (ROOT/name).exists():sources[name]=digest(ROOT/name)
for name in ['src/foreground_cache.h','src/frame_profile.h','tools/foreground_cache_test.c','tools/test-foreground-cache.sh']:
    if (ROOT/name).exists():sources[name]=digest(ROOT/name)
for name in ['src/player_replay.c','src/player_replay.h','tools/act_test.c','tools/title_prewarm_test.c','tools/test-title-scale.sh','tools/check_audio.py','tools/check_emulator.py','tools/emulator_test.c','tools/act_pad_replay.h','tools/act_pacing.py']:
    sources[name]=digest(ROOT/name)
for name in ['src/hud_animation.h','tools/hud_render_test.c','tools/test_hud_render.py']:
    sources[name]=digest(ROOT/name)
for name in ['src/title_vram.h','tools/vdp2_title_cycles.py','tools/test_title_cycles.py','tools/convert_objects.py','tools/monitor_pixels.py','tools/test_objects.py','tools/check_object_vram.py','tools/check_world.py']:
    if (ROOT/name).exists():sources[name]=digest(ROOT/name)
for name in ['src/gameplay_video.inc','src/special_view.inc','tools/camera_pixels.py','tools/test_camera_pixels.py','tools/terrain_pixels.py','tools/hud_pixels.py','tools/check_sequence.py']:
    if (ROOT/name).exists():sources[name]=digest(ROOT/name)
for name in ['src/objects.c','tools/world_test.c','tools/replay-sequence.sh','tools/check_sequence_replay.py','tools/test_sequence_replay.py']:
    sources[name]=digest(ROOT/name)
for name in ['tools/sprite_composition.py','tools/audit_sprite_composition.py','tools/test_sprite_composition.py','tools/amy_pixels.py']:
    if (ROOT/name).exists():sources[name]=digest(ROOT/name)
manifest={'version':version,'purpose':'Hardware diagnosis only; not a full-QA release','disc_sha256':disc,
    'hardware_sound_confirmed':False,'full_qa_passed':False,
    'title_visual_passed':json.loads((DIST/'title-report.json').read_text())['passed'],
    'files':{name:digest(path) for name,path in files.items()},'source_sha256':sources}
# Refuse to overwrite or reuse an existing versioned candidate directory.
target.mkdir(exist_ok=False)
for name,path in files.items():
    shutil.copyfile(path,target/name);assert digest(target/name)==manifest['files'][name]
(target/'candidate-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(target);print('BIN SHA256:',disc)
run_prune()
