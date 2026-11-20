#!/usr/bin/env python3
"""Real SS spring child allocator regression against native and virtual slot invariants."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
# Output volume: SCD_OUTPUT_VOLUME if set, else the mount point that holds the repo.
VOLUME = Path(os.environ.get('SCD_OUTPUT_VOLUME') or next(p for p in (ROOT, *ROOT.parents) if os.path.ismount(p)))
OUT = ROOT / 'build/ss-spring-allocator'


def guard():
    assert os.path.ismount(VOLUME), 'output volume unmounted'
    subprocess.run(['df', '-k', VOLUME], check=True, stdout=subprocess.DEVNULL)
    assert shutil.disk_usage(VOLUME).free >= 100 * 1024**3, 'output volume below 100 GiB'


def run(command, name):
    guard()
    with (OUT / name).open('w') as log:
        proc = subprocess.Popen(['nice', '-n', '20', *map(str, command)], cwd=ROOT,
                                env={**os.environ, 'TMPDIR': str(OUT / 'tmp')},
                                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        deadline = time.monotonic() + 180
        try:
            while proc.poll() is None:
                guard()
                assert time.monotonic() < deadline, 'allocator test timeout'
                time.sleep(1)
        except BaseException:
            import signal
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait()
            raise
    return proc.returncode


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    guard()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'tmp').mkdir(exist_ok=True)
    inputs = [p for folder in ('src', 'build/probe-source') for p in (ROOT / folder).glob('*')
              if p.suffix in ('.c', '.h', '.H', '.inc')]
    inputs += list((ROOT / 'assets/generated').glob('*.inc'))
    inputs += [Path(__file__).resolve(), ROOT / 'tools/ss_spring_allocator_test.c',
               ROOT / 'tools/ring_allocator_boss_test.c']
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in sorted(set(inputs))}
    report = dict(status='pending', inputs=hashes,
                  compiler=subprocess.check_output(['clang', '--version'], text=True))
    report_path = OUT / 'report.json'
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    try:
        flags = ['clang', '-std=gnu11', '-O1', '-g', '-fsigned-char', '-fwrapv',
                 '-fno-strict-aliasing', '-Wno-parentheses', '-Wno-unused-value',
                 '-Isrc', '-Iassets/generated', '-Ibuild/probe-source', '-DR1', '-DR11A',
                 '-fsanitize=address,undefined', '-fno-sanitize-recover=all']
        sources = ['tools/ss_spring_allocator_test.c', 'tools/ring_allocator_boss_test.c',
                   'src/act.c', 'src/player.c', 'src/sonic_animation.c', 'src/stage.c', 'src/water.c']
        sources += [f'build/probe-source/{n}.c' for n in
                    ('interaction', 'player', 'dircol', 'fcol', 'etc', 'equ', 'movement')]
        command = flags + sources + ['-o', str(OUT / 'test')]
        report['command'] = command
        assert run(command, 'compile.log') == 0, 'compile.log'
        assert run([OUT / 'test'], 'passed.log') == 0, 'passed.log'
        assert hashes == {p: sha(ROOT / p) for p in hashes}, 'inputs changed during test'
        report.update(status='passed', 
                      artifacts={p.name: sha(p) for p in OUT.iterdir()
                                 if p.is_file() and p.name not in ('report.json', 'runner.log')})
        print((OUT / 'passed.log').read_text().strip())
    except BaseException as error:
        report.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed', error=str(error))
        raise
    finally:
        report_path.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
