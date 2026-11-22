"""Validate the Past damage/ring-loss stress route; never replaces the no-damage route gate.

The route is script-driven (tools/test-past-ring-loss.sh): the Saturn takes the
scripted buttons and records its own trace; tools/act_test.c must then match
all 16 state words at every update. The stress itself is required, not echoed:
the act reaches its tally, Sonic is hurt, one update loses at least 30 rings,
the host and Saturn act clocks agree, and no update is late."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from act_pacing import measure
from hud_pixels import verify

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('folder', type=Path)
args = parser.parse_args()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
trace = args.folder/'player-target-trace.txt'
rows = [line.split()[1:] for line in trace.read_text().splitlines()]
log = (args.folder/'results.log').read_text()
assert 'Frame profile:' not in log
assert 'Re-recording act input from' in log, 'missing scripted input run'
report = measure(log, trace.read_text())
host = re.search(r'Full act host/Saturn match: (\d+) states, (\d+) words; elapsed=(\d+) score=(\d+) bonus=(\d+) lives=(\d+) hurt_ticks=(\d+) ramp_ticks=(\d+) checkpoint=(\d+)',
                 (args.folder/'host-results.log').read_text())
assert host, 'host did not match every Saturn state through the tally'
states, words, elapsed, score, bonus, lives, hurt, ramp, checkpoint = map(int, host.groups())
target = re.search(r'Full Act 2 era: states=(\d+) elapsed=(\d+) score=(\d+) bonus=(\d+) lives=(\d+) checkpoint=(\d+) sections=5 frames=\d+', log)
assert target, 'Saturn did not complete the Act 2 Past'
t_states, target_elapsed, t_score, t_bonus, t_lives, t_checkpoint = map(int, target.groups())
tally = re.search(r'host tally (\d+)', (args.folder/'route.txt').read_text())
assert tally and states == t_states == report['states'] == int(tally[1]) and words == states*16, 'state count'
assert (score, bonus, lives, checkpoint) == (t_score, t_bonus, t_lives, t_checkpoint), 'score/bonus/lives/checkpoint differ'
# The act timer is not one of the sixteen compared words: require equal clocks.
assert elapsed == target_elapsed, ('host/Saturn act clock', elapsed, target_elapsed)
# The stress: damage taken and a large scatter in a single update (word 8 = rings<<16|hurt).
ring_counts = [int(r[9], 16) >> 16 for r in rows]
largest_loss = max([a-b for a, b in zip(ring_counts, ring_counts[1:])] or [0])
assert hurt > 0, 'route took no damage'
assert largest_loss >= 30, ('largest ring loss in one update', largest_loss)
assert checkpoint == 0 and lives >= 1
# Every update must land within its refresh: a late interval fails the stress.
assert report['late'] == 0, ('late intervals', report['late'])
rings = ring_counts[-1]
hud = verify((args.folder/'act2-complete.ppm').read_bytes(), score, rings, target_elapsed, lives, 1, check_rings=rings != 0)
root = Path(__file__).resolve().parents[1]
report.update(passed=True, purpose='Past damage/ring-loss stress route; separate from the no-damage reference gate',
              disc_sha256=sha(root/'dist/sonic-cd-saturn-prototype.bin'), script_sha256=sha(args.folder/'script.txt'),
              trace_sha256=sha(trace), log_sha256=sha(args.folder/'results.log'), original_hud_pixels=hud,
              hurt_ticks=hurt, largest_ring_loss=largest_loss, lives=lives, score=score,
              host_sanitizers=['address', 'undefined behavior'], host_elapsed=elapsed, target_elapsed=target_elapsed,
              host_target_clock_agrees=True, hardware_tested=False, full_zone_qa_passed=False)
(args.folder/'report.json').write_text(json.dumps(report, indent=2)+'\n')
print(f'Past ring-loss stress: {states} exact states; {hurt} hurt ticks; {largest_loss} rings lost in one update; {report["late"]} late intervals')
