#!/usr/bin/env python3
"""Isolated R8 source-cast parity fixture. Not retail CPU or Saturn evidence.

Both variants use an explicit standalone extension of the shared frontend. Comparisons establish
BOSS_8/COLI8/COL8C-D/EMIE8 scratch translation, not retail CPU or Saturn correctness.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
# Output volume: SCD_OUTPUT_VOLUME if set, else the mount point that holds the repo.
VOLUME = Path(os.environ.get('SCD_OUTPUT_VOLUME') or next(p for p in (ROOT, *ROOT.parents) if os.path.ismount(p)))
OUT = ROOT / 'build/boss8-qa'
FLAGS = ['-std=gnu11', '-O1', '-g', '-fsigned-char', '-fwrapv', '-fno-strict-aliasing',
         '-Wno-parentheses', '-Wno-unused-value', '-Werror=implicit-function-declaration',
         '-Wno-tautological-constant-out-of-range-compare', '-fsanitize=address,undefined',
         '-fno-sanitize-recover=all', '-DR1', '-DR11A']


def main():
    assert os.path.ismount(VOLUME), 'output volume unmounted'
    assert ROOT.is_relative_to(VOLUME), 'outputs must stay on the output volume'
    assert shutil.disk_usage(VOLUME).free >= 100 * 1024**3, 'keep 100 GiB free'
    try:
        os.nice(20)
    except PermissionError:
        pass
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'tmp').mkdir(exist_ok=True)
    os.environ['TMPDIR'] = str(OUT / 'tmp')
    sources = list((ROOT/'src').glob('*')) + list((ROOT/'tools').glob('*.py')) + [ROOT/'tools/boss8_test.c', ROOT/'tools/prepare_boss8_fixture.py']
    sources += list((ROOT/'.deps/soniccd/src/R8').glob('*')) + list((ROOT/'.deps/soniccd/src').glob('*'))
    def hashes(paths):
        return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths)) if p.is_file()}
    report = dict(inputs=hashes(sources),status='pending',passed=False,scope='Original R8 boss/ending sourcecast parity through explicit standalone dispatch; no production integration, retail CPU or Saturn claim',flags=FLAGS,cases=[])
    report['ending_scope']='Actor takeover/control outputs and ending request only; scripted positions do not consume swdata; no actual ending playback claim.'
    path = OUT / 'report.json'
    def save():
        path.write_text(json.dumps(report, indent=2) + '\n')
    save()
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    def run(args, name):
        assert os.path.ismount(VOLUME), 'output volume unmounted'
        assert shutil.disk_usage(VOLUME).free >= 100 * 1024**3, 'keep 100 GiB free'
        with (OUT / name).open('w') as log:
            with subprocess.Popen(args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                  start_new_session=True) as job:
                try:
                    while True:
                        try:
                            code=job.wait(timeout=1)
                            if code:raise subprocess.CalledProcessError(code,args)
                            break
                        except subprocess.TimeoutExpired:
                            assert os.path.ismount(VOLUME), 'output volume unmounted; stopping job'
                            assert shutil.disk_usage(VOLUME).free >= 100*1024**3, 'free-space floor; stopping job'
                finally:
                    if job.poll() is None:
                        os.killpg(job.pid,signal.SIGTERM)
                        try:job.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            os.killpg(job.pid,signal.SIGKILL);job.wait()
    try:
        report['compiler'] = subprocess.check_output(['clang', '--version'], text=True)
        for script in ('prepare_probe.py', 'prepare_player.py', 'prepare_boss.py', 'prepare_boss_r8.py'):
            run([sys.executable, 'tools/' + script], script + '.log')
        for side in ('native', 'reference'):
            folder = 'build/probe-source' if side == 'native' else 'build/player-reference'
            compile_sources = ['tools/boss8_test.c', 'src/boss.c', 'src/boss_r8.c'] + [folder + '/' + f for f in ('boss_1.c', 'boss_8.c', 'ending_8.c', 'etc.c', 'equ.c')] + ['build/player-reference/carry.c']
            command = ['clang'] + FLAGS + ['-Isrc', '-I' + folder]
            if side == 'reference':
                command += ['-DSCD_BOSS_REFERENCE']
            run(command + compile_sources + ['-o', str(OUT / side)], side + '-compile.log')
            for era in ('good', 'bad'):
                run([str(OUT/side),era],f'{side}-{era}.log')
        for era in ('good','bad'):
            a=(OUT/f'native-{era}.log').read_bytes();b=(OUT/f'reference-{era}.log').read_bytes()
            assert a==b,(era,'trace mismatch')
            report['cases'].append(dict(era=era,passed=True,trace_sha256=hashlib.sha256(a).hexdigest(),updates=len(a.splitlines())-3,summary=a.decode().splitlines()[-3],ending=a.decode().splitlines()[-2]))
        good=(OUT/'native-good.log').read_text().splitlines()[:-3]
        bad=(OUT/'native-bad.log').read_text().splitlines()[:-3]
        palette_difference=next((i for i,(a,b) in enumerate(zip(good,bad)) if a.split()[14]!=b.split()[14]),None)
        assert palette_difference is not None, 'Future-specific palette paths were not distinguished'
        report['first_future_palette_difference']=palette_difference
        assert hashes(sources) == report['inputs'], 'source inputs changed during run'
        report.update(status='passed', passed=True)
    except KeyboardInterrupt:
        report.update(status='interrupted', error='signal or keyboard interrupt')
    except Exception as exc:
        report.update(status='failed', error=str(exc))
    finally:
        generated = list((ROOT/'build/probe-source').glob('*')) + list((ROOT/'build/player-reference').glob('*'))
        report['generated_inputs'] = hashes(generated + list(OUT.glob('*.c')))
        report['binaries'] = hashes([OUT/'native',OUT/'reference'])
        save()
    detail='; '.join(f"{case['era']} {case['updates']} updates" for case in report['cases'])
    print(('PASS: boss8 sourcecast parity; '+detail+'; four hits, escape and EMIE8 ending request outputs; ' if report['passed'] else 'FAIL: boss8 ') + str(path))
    return 0 if report['passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
