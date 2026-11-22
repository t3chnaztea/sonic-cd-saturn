"""Bind the completed sanitizer runtime proof to its exact source and log."""
import hashlib,json
from convert_assets import ROOT
out=ROOT/'build/powerup-runtime'
log=(out/'sanitized.log').read_text()
assert 'late real monitor grant at 33' in log and '13211 retail cases passed with sanitizers' in log
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
report=dict(passed=True,late_grant_tick=33,culling_cases=13211,sanitizers='address and undefined behavior',
    log_sha256=sha(out/'sanitized.log'),culling_report_sha256=sha(out/'culling-report.json'),
    source_sha256={name:sha(ROOT/name) for name in ['src/player.c','src/scd_player.h','src/powerup_visual.c',
        'src/powerup_visual.h','src/powerup_runtime.c','src/powerup_runtime.h','src/objects.c','src/sonic_animation.c',
        'tools/powerup_runtime_test.c','tools/test-powerup-runtime.sh','tools/powerup_runtime_report.py']})
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
