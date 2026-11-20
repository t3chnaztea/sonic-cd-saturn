#!/usr/bin/env python3
"""Build and measure tagged QQ redraws, then restore the original candidate.

Run under tools/power_guard.py. This tool never packages a hardware release.
An interrupted run restores the source switch but deliberately does not start
a new build during cleanup. Its report then requires a normal rebuild.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess

from check_qq_switch_margin import verify
from candidate_identity import capture
from power_guard import ROOT, digest, inputs, on_ac


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve();out.mkdir(parents=True, exist_ok=False)
    header = ROOT/'src/frame_profile.h'
    original = header.read_bytes()
    assert original.count(b'#define SCD_FRAME_PROFILE 0') == 1, 'profiling must start disabled'
    assert on_ac(), 'profiling requires AC power and an external power guard'
    binary = ROOT/'dist/sonic-cd-saturn-prototype.bin'
    record = dict(status='pending', passed=False, started=dt.datetime.now().astimezone().isoformat(),
                  candidate_before_sha256=digest(binary), input_sha256=inputs(), eras={}, steps=[],
                  source_profile_restored=False, candidate_rebuilt=False)
    record['candidate_identity_before'] = capture(ROOT)
    snapshot = out/'candidate-before'
    record['candidate_snapshot_sha256'] = {}
    for name in ['dist/sonic-cd-saturn-prototype.bin', 'dist/sonic-cd-saturn-prototype.cue',
                 'dist/iso/sonic-cd-saturn-prototype.iso', 'dist/build-report.json',
                 'build/saturn/sonic-cd-saturn-prototype.bin', 'build/saturn/sonic-cd-saturn-prototype.elf']:
        target = snapshot/name;target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT/name, target)
        record['candidate_snapshot_sha256'][name] = digest(target)
    def save(): (out/'report.json').write_text(json.dumps(record, indent=2)+'\n')
    def step(name, command):
        assert on_ac(), 'AC unavailable before profiling step'
        record['steps'].append(dict(name=name, command=command, status='pending'));save()
        with (out/(name+'.log')).open('w') as log:
            result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        record['steps'][-1].update(status='passed' if result.returncode==0 else 'failed', exit_code=result.returncode);save()
        assert result.returncode == 0, (name, result.returncode, str(out/(name+'.log')))
    def interrupted(signum, frame): raise KeyboardInterrupt(f'signal {signum}')
    signal.signal(signal.SIGTERM, interrupted)
    save()
    try:
        header.write_bytes(original.replace(b'#define SCD_FRAME_PROFILE 0', b'#define SCD_FRAME_PROFILE 1'))
        step('instrumented-build', ['bash', 'tools/build.sh'])
        record['instrumented_disc_sha256'] = digest(binary)
        record['instrumented_header_sha256'] = digest(header)
        for era in 'AC':
            step('route-'+era, ['python3', 'tools/test_qq_route.py', '--act', '2', '--era', era, '--require-r5-dispatch'])
            source = ROOT/f'build/qq2/controller/{era}'
            folder = out/era;folder.mkdir()
            for name in ['results.log', 'core.log', 'report.json']: shutil.copyfile(source/name, folder/name)
            route = json.loads((folder/'report.json').read_text())
            assert route['passed'] and route['disc_sha256'] == record['instrumented_disc_sha256']
            measurements = verify((folder/'results.log').read_text())
            assert len(measurements) == route['r5_events']['transition_full_redraws'], 'profile missed an observed redraw'
            record['eras'][era] = dict(measurements=measurements, log_sha256=digest(folder/'results.log'),
                                       route_report_sha256=digest(folder/'report.json'))
            save()
        record['measurements_passed'] = True
    except BaseException as error:
        record.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed', error=repr(error))
        raise
    finally:
        header.write_bytes(original)
        record['source_profile_restored'] = header.read_bytes() == original
        save()
    # Only a successful measurement may start the restoration build. A stop
    # signal/deadline never causes a surprise build during exception cleanup.
    try:
        step('candidate-rebuild', ['bash', 'tools/build.sh'])
        record['candidate_rebuilt'] = True
        record['candidate_after_sha256'] = digest(binary)
        record['candidate_identical'] = record['candidate_after_sha256'] == record['candidate_before_sha256']
        record['candidate_identity_after'] = capture(ROOT)
        assert record['candidate_identity_after'] == record['candidate_identity_before'], 'restored build changed more than ISO dates'
        record['candidate_payload_identical'] = True
        record['changed_inputs'] = [n for n,h in record['input_sha256'].items() if not (ROOT/n).is_file() or digest(ROOT/n)!=h]
        assert not record['changed_inputs'], ('source inputs changed during profiling', record['changed_inputs'])
        record.update(status='passed', passed=True)
    except BaseException as error:
        record.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed', error=repr(error))
        raise
    finally:
        record['finished'] = dt.datetime.now().astimezone().isoformat();save()
    print('PASS: QQ2 A/C actual redraw timing; source restored; candidate rebuilt; '
          f'identical={record["candidate_identical"]}')


if __name__ == '__main__': main()
