#!/usr/bin/env python3
"""Isolated R7 source-cast parity fixture. Not retail CPU or Saturn evidence.

Both variants use the production boss frontend. Comparisons establish
BOSS_7/COLI7 scratch translation, not retail CPU or Saturn correctness.
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
OUT = ROOT / 'build/boss7-qa'
FLAGS = ['-std=gnu11', '-O1', '-g', '-fsigned-char', '-fwrapv', '-fno-strict-aliasing',
         '-Wno-parentheses', '-Wno-unused-value', '-Wno-implicit-function-declaration',
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
    sources = list((ROOT/'src').glob('*')) + list((ROOT/'tools').glob('*.py')) + [ROOT/'tools/boss7_test.c', ROOT/'tools/ss_results_test.c']
    sources += list((ROOT/'.deps/soniccd/src/R7').glob('*')) + list((ROOT/'.deps/soniccd/src').glob('*'))
    def hashes(paths):
        return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths)) if p.is_file()}
    report = dict(inputs=hashes(sources), status='pending', passed=False, scope='original-derived host scratch translation; production shared frontend; no retail or Saturn claim', flags=FLAGS, cases=[], retail_corrections=[dict(function='beam_next', pc_source='R7/BOSS_7.C:1694 xspeed=0', retail='R73C $20C656 confirmed by instruction sequence; $20C676 clr.w18(a0)', correction='yspeed=0 in both adapted native and PC-cast reference; parity validates cast translation, not this shared retail correction')])
    report['retail_corrections'].append(dict(function='msnc_low_move/hight_set_retry',
        retail='R73C $20C00C tests57(A2) after floor helper clobbers A2 at$20CA0C; R73C/D table cursor bytes verified',
        correction='Both cast variants reproduce early AI return: table entries0..3 zero; entries4..13 and miss nonzero. Source parity does not independently validate this shared retail correction.'))
    report['retail_corrections'].append(dict(function='random',
        retail='Level/Functions (General).asm Random uses32-bit shifts and move.w, as corrected for boss6',
        correction='Both cast variants use original RNG rather than IO.C sign-bit preservation and first-word addition.'))
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
            subprocess.run(args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
    try:
        report['compiler'] = subprocess.check_output(['clang', '--version'], text=True)
        for script in ('prepare_probe.py', 'prepare_player.py', 'prepare_boss.py', 'prepare_boss_r7.py'):
            run([sys.executable, 'tools/' + script], script + '.log')
        for side in ('native', 'reference'):
            folder = 'build/probe-source' if side == 'native' else 'build/player-reference'
            compile_sources = ['tools/boss7_test.c', 'src/boss.c', 'src/boss_r7.c'] + [folder + '/' + f for f in ('boss_1.c', 'boss_7.c', 'etc.c', 'equ.c')] + ['build/player-reference/carry.c']
            command = ['clang'] + FLAGS + ['-Isrc', '-I' + folder]
            if side == 'reference':
                command += ['-DSCD_BOSS_REFERENCE']
            run(command + compile_sources + ['-o', str(OUT / side)], side + '-compile.log')
            for era in ('good', 'bad'):
                for outcome in ('win', 'lose'):
                    run([str(OUT / side), era, outcome], f'{side}-{era}-{outcome}.log')
        for era in ('good', 'bad'):
            for outcome in ('win', 'lose'):
                a = (OUT / f'native-{era}-{outcome}.log').read_bytes()
                b = (OUT / f'reference-{era}-{outcome}.log').read_bytes()
                assert a == b, (era, outcome, 'trace mismatch')
                report['cases'].append(dict(era=era, outcome=outcome, passed=True, trace_sha256=hashlib.sha256(a).hexdigest(), updates=len(a.splitlines())-2))
        run(['clang'] + FLAGS + ['-Isrc', 'tools/ss_results_test.c', 'src/act.c', '-o', str(OUT/'results')], 'results-compile.log')
        run([str(OUT/'results')], 'results.log')
        report['results_adapter_passed'] = True
        assert hashes(sources) == report['inputs'], 'source inputs changed during run'
        report.update(status='passed', passed=True)
    except KeyboardInterrupt:
        report.update(status='interrupted', error='signal or keyboard interrupt')
    except Exception as exc:
        report.update(status='failed', error=str(exc))
    finally:
        generated = list((ROOT/'build/probe-source').glob('*')) + list((ROOT/'build/player-reference').glob('*'))
        report['generated_inputs'] = hashes(generated)
        save()
    print(('PASS:' if report['passed'] else 'FAIL:') + ' ' + str(path))
    return 0 if report['passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
