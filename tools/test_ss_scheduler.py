#!/usr/bin/env python3
"""Compare the actual SS3 selector and boss allocator against their original scans."""
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
OUT = ROOT / 'build/ss-scheduler'


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
    # Compile the current production selector, not a manually copied model.
    source = (ROOT / 'src/objects.c').read_text()
    start = '            unsigned key=~0u;i=SCD_OBJECT_CAPACITY;'
    end = '            if(i==SCD_OBJECT_CAPACITY)break;'
    assert source.count(start) == source.count(end) == 1
    selector = source.split(start, 1)[1].split(end, 1)[0]
    selector = start + selector
    (OUT / 'selector.inc').write_text(selector)
    resync = 'if(!k)k=scd_boss_retail_slot(j+1);'
    assert selector.count(resync) == 1
    (OUT / 'selector-negative.inc').write_text(selector.replace(resync, ''))
    inputs = [p for folder in ('src', 'build/probe-source') for p in (ROOT / folder).glob('*')
              if p.suffix in ('.c', '.h', '.H', '.inc')]
    inputs += list((ROOT / 'assets/generated').glob('*.inc'))
    inputs += [Path(__file__).resolve(), ROOT / 'tools/ss_scheduler_test.c', ROOT / 'tools/ss_scheduler_boss_test.c', OUT / 'selector.inc', OUT / 'selector-negative.inc']
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in sorted(set(inputs))}
    report = dict(status='pending', inputs=hashes,
                  compiler=subprocess.check_output(['clang', '--version'], text=True))
    report_path = OUT / 'report.json'
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    try:
        flags = ['clang', '-std=gnu11', '-O1', '-g', '-fsigned-char', '-fwrapv',
                 '-fno-strict-aliasing', '-Wno-parentheses', '-Wno-unused-value',
                 '-Isrc', '-Iassets/generated', '-Ibuild/probe-source', '-I' + str(OUT), '-DR1', '-DR11A',
                 '-fsanitize=address,undefined', '-fno-sanitize-recover=all']
        sources = ['tools/ss_scheduler_test.c', 'tools/ss_scheduler_boss_test.c',
                   'src/act.c', 'src/player.c', 'src/sonic_animation.c', 'src/stage.c', 'src/water.c']
        sources += [f'build/probe-source/{n}.c' for n in
                    ('interaction', 'player', 'dircol', 'fcol', 'etc', 'equ', 'movement')]
        command = flags + sources + ['-o', str(OUT / 'test')]
        report['command'] = command
        assert run(command, 'compile.log') == 0, 'compile.log'
        assert run([OUT / 'test'], 'passed.log') == 0, 'passed.log'
        # Negative controls must execute and fail their intended assertion.
        negative = flags + ['-DNEG_NO_RESYNC'] + sources + ['-o', str(OUT / 'negative-map')]
        assert run(negative, 'negative-map-compile.log') == 0
        assert run([OUT / 'negative-map'], 'negative-map.log') != 0
        assert 'a==b' in (OUT / 'negative-map.log').read_text()
        boss = (ROOT / 'src/boss.c').read_text()
        anchor = '(round_no==7 && boss_interleaved)?boss_interleave_first:32'
        assert boss.count(anchor) == 1
        unsafe = OUT / 'unsafe-boss.c'
        unsafe.write_text(boss.replace(anchor, 'round_no==7?SCD_BOSS_FIRST_SLOT:32'))
        negative = flags + [f'-DBOSS_SOURCE="{unsafe}"'] + sources + ['-o', str(OUT / 'negative-boss')]
        assert run(negative, 'negative-boss-compile.log') == 0
        assert run([OUT / 'negative-boss'], 'negative-boss.log') != 0
        assert 'boss scenario 6 differs' in (OUT / 'negative-boss.log').read_text()
        assert hashes == {p: sha(ROOT / p) for p in hashes}, 'inputs changed during test'
        report.update(status='passed',
                      artifacts={p.name: sha(p) for p in OUT.iterdir()
                                 if p.is_file() and p.name not in ('report.json', 'runner.log')})
        print((OUT / 'passed.log').read_text().strip())
        print('PASS: negative controls reject omitted resync and unsafe lower-boss exclusion')
    except BaseException as error:
        report.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed', error=str(error))
        raise
    finally:
        report_path.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
