#!/usr/bin/env python3
"""Compare the original Collision Chaos planes A/B with native stage tiles in all eras."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = [f'R3{act}{era}' for act in (1, 2, 3)
            for era in ('CD' if act == 3 else 'ABCD')]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    out = ROOT / 'build/cc-plane'
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / 'report.json'
    inputs = ['tools/test_cc_plane.py', 'tools/capture_cc_plane.py',
              'tools/capture_cc_scroll.py', 'tools/special_retail.py',
              'tools/extract_mmd.py', 'src/background.c', 'src/background_r3.c']
    report = dict(status='pending', passed=False, programs={},
                  input_sha256={name: sha(ROOT / name) for name in inputs},
                  limits='Original walked-camera plane A/B cells versus native stage tiles. '
                         'This does not compare Saturn VDP2 plane transfer, sprite priority, '
                         'or a complete rendered scene.')
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    try:
        for name in PROGRAMS:
            log = out / f'{name}.log'
            with log.open('w') as stream:
                subprocess.run(['python3', 'tools/capture_cc_plane.py', name[-1],
                                '--act', name[2]], cwd=ROOT, stdout=stream,
                               stderr=subprocess.STDOUT, check=True, timeout=300)
            path = ROOT / 'build/plane-retail' / name / 'report.json'
            result = json.loads(path.read_text())
            assert result['program'] == name
            samples = result['samples']
            assert len(samples) == 4, (name, len(samples))
            cells = result['totals']['cells']
            foreground_cells = result['totals']['foreground_cells']
            bad = result['totals']['row_layer'] + result['totals']['foreground_mismatches']
            assert cells == foreground_cells == 4 * 224 * 40 and bad == 0, (name, cells, foreground_cells, bad)
            stale = result['totals']['foreground_stale_visible']
            assert stale >= 0 and result['totals']['foreground_active'] > foreground_cells // 10, (name, 'foreground is blank')
            report['programs'][name] = dict(passed=True, cells=cells,
                                            foreground_cells=foreground_cells,
                                            foreground_stale_visible=stale,
                                            foreground_active=result['totals']['foreground_active'],
                                            walked_views=len(samples),
                                            source_program_sha256=result['program_sha256'],
                                            native_pack_sha256=sha(ROOT / 'assets/generated' / f'cc3{name[2:4]}.bin'),
                                            report_sha256=sha(path))
            report_path.write_text(json.dumps(report, indent=2) + '\n')
            print(f'{name}: {cells} plane A and B cells pass', flush=True)
    except BaseException as error:
        report.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed',
                      failed_program=name, error=f'{type(error).__name__}: {error}')
        report_path.write_text(json.dumps(report, indent=2) + '\n')
        raise
    report.update(status='passed', passed=True)
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    print(f'PASS: {report_path}')


if __name__ == '__main__':
    main()
