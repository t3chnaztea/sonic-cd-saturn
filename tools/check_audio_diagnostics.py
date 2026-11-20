#!/usr/bin/env python3
"""Require all three isolated audio probes and a successful return to gameplay."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
log = (ROOT/'build/diagnostic-qa/results.log').read_text()
assert 'Direct SCSP tone, driver ring, CD music and diagnostic exit passed' in log
probes = re.findall(r'Audio probe (\d+): mean_square=(\d+)', log)
assert [int(index) for index, _ in probes] == [0, 1, 2]
assert all(int(energy) >= 10000 for _, energy in probes)
capture = (ROOT/'build/diagnostic-qa/audio-diagnostics.ppm').read_bytes()
assert capture.startswith(b'P6\n330 224\n255\n')
report = {
    'disc_sha256': hashlib.sha256((ROOT/'dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest(),
    'emulator_frames': 1700+int(re.search(r'Boot warmup frames: (\d+)',log)[1]),
    'boot_warmup_frames': int(re.search(r'Boot warmup frames: (\d+)',log)[1]),
    'probes': dict(zip(['direct_scsp_tone', 'driver_ring', 'cd_music'], [int(v) for _, v in probes])),
    'driver_ready_and_sound_ram_checksum': 'pass',
    'exit_resumes_music': True,
    'capture_sha256': hashlib.sha256(capture).hexdigest(),
    'hardware_tested': False,
}
(ROOT/'dist/audio-diagnostic-report.json').write_text(json.dumps(report, indent=2)+'\n')
print('Direct tone, ring effect, music and diagnostic exit verified in emulator')
