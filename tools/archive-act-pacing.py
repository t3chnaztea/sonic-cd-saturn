#!/usr/bin/env python3
"""Preserve five completed measurements without mutating a hardware candidate."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
from act_pacing import measure

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('output', type=Path)
parser.add_argument('--references', type=Path, required=True)
parser.add_argument('--candidate', type=Path, required=True)
args = parser.parse_args()
assert not args.output.exists(), 'never overwrite an evidence archive'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
disc = sha(ROOT/'dist/sonic-cd-saturn-prototype.bin')
assert sha(args.candidate/'sonic-cd-saturn-prototype.bin') == disc
routes = [('act2-qa', 'dist/act2-report.json'),
          ('act2-past-qa', 'build/act2-past-qa/report.json'),
          ('act2-good-qa', 'build/act2-good-qa/report.json'),
          ('act2-bad-qa', 'build/act2-bad-qa/report.json'),
          ('act3-qa', 'dist/act3-report.json')]
files = {}
summary = {}
for name, route_path in routes:
    folder = ROOT/'build'/name
    pacing = json.loads((folder/'pacing-report.json').read_text())
    route = json.loads((ROOT/route_path).read_text())
    assert pacing['measurement_complete'] and pacing['route_gate_passed']
    assert not pacing.get('instrumented_frame_profile', False), 'do not archive a profiler build as acceptance evidence'
    assert route['passed'] and pacing['disc_sha256'] == route['disc_sha256'] == disc
    assert pacing['route_report_sha256'] == sha(ROOT/route_path)
    for filename, key in [('results.log', 'log_sha256'), ('player-target-trace.txt', 'trace_sha256')]:
        assert pacing[key] == sha(folder/filename)
    measured = measure((folder/'results.log').read_text(), (folder/'player-target-trace.txt').read_text())
    assert all(pacing[key] == value for key, value in measured.items())
    reference = args.references/name/'player-target-trace.txt'
    assert pacing['reference_trace_sha256'] == sha(reference)
    words = lambda path: [line.split()[1:] for line in path.read_text().splitlines()]
    assert words(reference) == words(folder/'player-target-trace.txt')
    assert route['original_hud_pixels'] > 0 and route['hud_ring_label_checked']
    files[f'{name}/reference-trace.txt'] = reference
    files[f'{name}/route-report.json'] = ROOT/route_path
    for path in folder.iterdir():
        if path.name in ('results.log', 'core.log', 'player-target-trace.txt', 'host-results.log',
                         'pacing-report.json', 'route.txt') or path.suffix == '.ppm':
            files[f'{name}/{path.name}'] = path
    summary[name] = dict(states=pacing['states'], intervals=pacing['intervals'],
                         vblanks=pacing['vblanks'], late=pacing['late'],
                         max_gap=pacing['max_gap'], gaps=pacing['gaps'],
                         original_hud_pixels=route['original_hud_pixels'])
for name in ['emulator_test.c', 'act_pad_replay.h', 'act_pacing.py', 'archive-act-pacing.py',
             'test_act_pacing.py', 'act_pad_replay_test.c', 'test-act-pacing.sh',
             'test-act2-era-emulator.sh', 'run-act2-era.sh', 'test-act2-emulator.sh',
             'test-act3-emulator.sh', 'check_act2_era.py', 'check_act2.py', 'check_act3.py',
             'hud_pixels.py', 'act_test.c']:
    files[f'tools/{name}'] = ROOT/'tools'/name
files['emulator_test'] = ROOT/'build/emulator_test'
manifest = dict(purpose='Expanded route timing and HUD evidence; not a new release',
                disc_sha256=disc, candidate=str(args.candidate.resolve()),
                hardware_tested=False, full_zone_qa_passed=False,
                routes=summary, files={name: sha(path) for name, path in files.items()})
args.output.mkdir(parents=True)
for name, path in files.items():
    target = args.output/name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    assert sha(target) == manifest['files'][name], ('archive copy mismatch', name)
(args.output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
print(f'Archived {len(files)} hash-verified files at {args.output}; no candidate changed')
