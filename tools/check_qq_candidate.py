#!/usr/bin/env python3
"""Audit V0.066's final-hash QQ gates and stage their evidence for local bundling.

This only reads tests and copies local evidence. It never runs an emulator or
writes the SD card. Missing, partial, stale or mismatched evidence is fatal.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
from check_qq_switch_margin import verify as verify_margin
from candidate_identity import capture
from power_guard import ROOT, digest

# These tools never participate in full QA or profile generation. Their own
# packaging checks run now; changing them does not invalidate game evidence.
PACKAGING_ONLY={'tools/check_qq_candidate.py','tools/bundle.py','tools/preserve-release.py'}


def audit(full_run, profile):
    disc = digest(ROOT/'dist/sonic-cd-saturn-prototype.bin')
    core = digest(ROOT/'.deps/beetle-saturn/mednafen_saturn_libretro.dylib')
    assert '#define SCD_FRAME_PROFILE 0' in (ROOT/'src/frame_profile.h').read_text()
    evidence = set()
    def add(path):
        path = Path(path).resolve();assert path.is_relative_to(ROOT) and path.is_file(), path
        evidence.add(path);return path
    def read(path):
        return json.loads(add(ROOT/path).read_text())
    def hashes(mapping):
        for name, expected in mapping.items(): assert digest(ROOT/name) == expected, ('changed input', name)
    def bound(path, key='disc_sha256'):
        report = read(path)
        assert report.get('passed') and report.get(key) == disc, ('missing/stale pass', str(path))
        hashes(report.get('inputs', {}));hashes(report.get('source_sha256', {}))
        if 'core_sha256' in report: assert report['core_sha256'] == core, ('stale core', str(path))
        return report
    guardian = read(full_run)
    assert guardian['status'] == 'passed' and guardian['passed'] and guardian['disc_sha256'] == disc
    assert not set(guardian['changed_inputs'])-PACKAGING_ONLY, 'full run changed inputs'
    hashes({n:h for n,h in guardian['input_sha256'].items() if n not in PACKAGING_ONLY})
    qa = bound('dist/qa-report.json')
    assert qa['mode'] == 'full' and qa['steps'] and all(s['exit_code']==0 for s in qa['steps'])
    assert 'tools/qa-loop.py full' in ' '.join(guardian['command']), 'guardian did not run full QA'
    run_log=add(ROOT/Path(full_run).parent/'command.log')
    passes=re.findall(r'^PASS: (.+/report.json)$',run_log.read_text(),re.M)
    assert passes and digest(add(Path(passes[-1])))==digest(ROOT/'dist/qa-report.json'), 'full-QA PASS is not bound to this run'
    for name,h in qa['report_hashes'].items(): assert digest(ROOT/'dist'/name)==h, ('changed full-QA report',name)
    player = read('dist/player-report.json')
    assert player['target_matches_host'] and player['disc_sha256']==disc, 'original-physics regression not verified'
    bound('build/save-matrix/report.json');bound('build/save-progression/report.json')

    def route(path, act, era, zone, continuation=False):
        r = bound(path)
        assert r['act']==act and r['era']==era and r['matched_positions']==r['positions']>0
        assert r['respawns']==0 and not r['late_gameplay_intervals']
        want = [zone, act, 0] if act==1 else [zone, 2, 3] if act==2 else [zone+1, 0, 0]
        assert len(r['stage_transitions'])==1 and r['stage_transitions'][0]['after']==want
        folder = Path(path).parent
        assert digest(ROOT/folder/'controller.txt')==r['pad_sha256']
        assert digest(ROOT/folder/'script.txt')==r['script_sha256']
        for name in ['controller.txt','script.txt','results.log']: add(ROOT/folder/name)
        if continuation:
            assert digest(ROOT/r['entry_backup'])==r['entry_backup_sha256']
            assert digest(ROOT/folder/'backup-after.bin')==r['backup_after_sha256']
            if act==3: assert r['cold_continue_mailbox'], 'cold Continue missing'
        return r

    for act in (1,2,3):
        for era in ('ABCD' if act<3 else 'CD'):
            r=route(f'build/qq{act}/controller/{era}/report.json',act,era,3)
            if act==2 and era in 'AC':
                e,s=r['r5_events'],r['bg_slave_counters']
                count=e['enkei_changes'];assert count>0
                assert e['transition_holds']==e['transition_full_redraws']==count
                assert s['attempts']==s['entries']==s['completions']==count
                assert s['eligibility_fallbacks']==s['full_redraw_slave_unavailable']==0
    boss=bound('build/qq3-boss/report.json','image_sha256')
    assert set(boss['runs'])=={'C','D'} and all(r['passed'] and r['exit_code']==0 for r in boss['runs'].values())
    for era in 'CD':
        log=add(ROOT/f'build/qq3-boss/{era}/results.log')
        assert digest(log)==boss['runs'][era]['log_sha256']
    lifecycle=bound('build/qq-lifecycle/report.json')
    assert set(lifecycle['cases'])=={'era','title','special'}
    for case,r in lifecycle['cases'].items():
        assert r['passed'] and r['status']=='passed'
        p=add(ROOT/f'build/qq-lifecycle/{case}/results.log');assert digest(p)==r['log_sha256']

    # Require every earned link on this disc, not just a final old checkpoint.
    previous=None
    for prefix,zone in [('tt',2),('qq',3)]:
        for act,era in [(1,'A'),(2,'A'),(3,'D')]:
            path=f'build/{prefix}{act}/controller/continue/{era}/report.json'
            r=route(path,act,era,zone,True)
            if previous is not None: assert r['entry_backup_sha256']==previous, ('broken Continue link',path)
            previous=r['backup_after_sha256']
    profile=Path(profile)
    p=read(profile/'report.json')
    assert p['passed'] and p['status']=='passed' and p['candidate_rebuilt'] and p['source_profile_restored']
    assert not set(p['changed_inputs'])-PACKAGING_ONLY
    # Profiling precedes final full QA. Its normal rebuild and the final disc
    # may have different ISO dates; every other byte of the ISO, audio and
    # executable must match. Final route/full-QA gates above still use exact hashes.
    assert p['candidate_payload_identical']
    assert p['candidate_identity_before']==p['candidate_identity_after']==capture(ROOT)
    hashes({n:h for n,h in p['input_sha256'].items() if n not in PACKAGING_ONLY});assert set(p['eras'])=={'A','C'}
    for era,e in p['eras'].items():
        log=add(ROOT/profile/era/'results.log');assert digest(log)==e['log_sha256']
        route_report=add(ROOT/profile/era/'report.json');assert digest(route_report)==e['route_report_sha256']
        r=json.loads(route_report.read_text());assert r['passed'] and r['disc_sha256']==p['instrumented_disc_sha256']
        measured=verify_margin(log.read_text());assert measured==e['measurements']
        assert len(measured)==r['r5_events']['transition_full_redraws']
    return disc,evidence


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full-run',type=Path,required=True)
    parser.add_argument('--profile',type=Path,required=True)
    args=parser.parse_args()
    target=ROOT/'dist/qq-acceptance.json'
    report=dict(passed=False,status='pending',hardware_tested=False,full_run=str(args.full_run),profile=str(args.profile))
    target.write_text(json.dumps(report,indent=2)+'\n')
    try:
        disc,evidence=audit(args.full_run,args.profile)
        folder=ROOT/'dist/qq-evidence';folder.mkdir(exist_ok=True)
        files={}
        for source in sorted(evidence):
            name='__'.join(source.relative_to(ROOT).parts)
            dest=folder/name;shutil.copyfile(source,dest)
            assert digest(dest)==digest(source)
            files[str(dest.relative_to(ROOT/'dist'))]=digest(dest)
        report.update(passed=True,status='passed',disc_sha256=disc,evidence=files,
                      source_sha256={p:digest(ROOT/p) for p in ['tools/check_qq_candidate.py','tools/check_qq_switch_margin.py','tools/candidate_identity.py']},
                      limits='Emulator/host evidence only. Hardware acceptance remains pending. Lifecycle transitions use documented fixtures.')
    except BaseException as error:
        report.update(status='failed',error=repr(error));raise
    finally:target.write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS: V0.066 candidate gates; {len(files)} evidence files staged; {disc}')


if __name__=='__main__':main()
