#!/usr/bin/env python3
"""Require a complete Act 2 era route, every replay word, and original results pixels."""
import argparse
import hashlib
import json
import re
from pathlib import Path

from results_pixels import draw, maps, art, colors, number_art, verify_pixels
from title_card_plc import native_wait

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('era', type=int, choices=[1, 2, 3], nargs='?', default=1)
parser.add_argument('folder', type=Path, nargs='?')
args = parser.parse_args()
era = args.era
era_name = {1: 'Past', 2: 'Good Future', 3: 'Bad Future'}[era]
folder = args.folder or ROOT / ('build/act2-' + {1:'past', 2:'good', 3:'bad'}[era] + '-qa')
log = (folder / 'results.log').read_text()
assert f'Act 2 era route: era={era} ' in log
target = re.search(r'Full Act 2 era: states=(\d+) elapsed=(\d+) score=(\d+) bonus=(\d+) lives=(\d+) checkpoint=(\d+) sections=5 frames=(\d+)', log)
assert target, f'missing completed {era_name} route'
states, elapsed, score, bonus, lives, checkpoint, frames = map(int, target.groups())
host = re.search(r'Full act host/Saturn match: (\d+) states, (\d+) words; elapsed=(\d+) score=(\d+) bonus=(\d+) lives=(\d+) hurt_ticks=(\d+) ramp_ticks=(\d+) checkpoint=(\d+)', (folder / 'host-results.log').read_text())
assert host, 'missing sanitized complete replay'
values = list(map(int, host.groups()))
# The Saturn holds its act clock through the title card. tools/act_test.c has
# no stage loading and models one 130-update card, which matches the Saturn for
# Present, Past and Act 3 but not the Future eras: measured first accepted
# input is update 131, 128 and 117 for Past, Good Future and Bad Future. That
# spread predates V0.057, which shifted all three by the same two updates
# (129/126/115 before). So the host runs no card in the Future eras and its
# clock gains exactly the updates the Saturn held. Every other value, and all
# state words, must still match exactly. Pin the offset so a change in the
# Saturn's card length breaks this gate loudly. See NEXT-SESSION.md.
# Since the card latches its PLC 2 wait at slide-out for the program loaded
# then (src/title_card.c), the reloaded Future's wait adds to the hold
# (tools/title_card_plc.py native_wait; the host route masks the same updates,
# tools/cc_campaign_search.c ppz_future_masked).
CARD_HOLD = {1: 0, 2: 127 + native_wait(0, 1, 2), 3: 116 + native_wait(0, 1, 3)}
assert values[:2] == [states, states * 16], 'state count differs from the target'
assert values[3:6] == [score, bonus, lives], 'score, bonus or lives differ from the target'
assert values[2] - elapsed == CARD_HOLD[era], (
    f'{era_name} host/target act clock gap {values[2] - elapsed}, expected {CARD_HOLD[era]}')
# Checkpoints are Present-only (scd_player_checkpoint_activate); this route retains all lives.
assert checkpoint == values[-1] == 0 and lives == 3
if era in (1, 2):
    assert values[6] == 0, f'{era_name} reference route unexpectedly took damage'
rows = [line.split() for line in (folder / 'player-target-trace.txt').read_text().splitlines()]
assert len(rows) == states
assert int(rows[0][8], 16) == 1, 'route must include the first simulation update'
captures = {}
for name in ['act2-spawn', 'act2-section1', 'act2-section2', 'act2-section3', 'act2-section4', 'act2-signpost', 'act2-complete']:
    raw = (folder / f'{name}.ppm').read_bytes()
    header, data = raw.split(b'255\n', 1)
    assert header == b'P6\n330 224\n' and len(data) == 330 * 224 * 3
    assert len(set(data[i:i+3] for i in range(0, len(data), 3))) >= 16
    captures[name] = hashlib.sha256(raw).hexdigest()
complete = (folder / 'act2-complete.ppm').read_bytes().split(b'255\n', 1)[1]
from hud_pixels import verify as verify_hud
rings = int(rows[-1][10], 16) >> 16
hud_pixels = verify_hud((folder/'act2-complete.ppm').read_bytes(), score, rings, elapsed, lives, era, check_rings=rings != 0)
pixels = 0
for index, width in ([(10, 256), (13, 224)] if era == 2 else [(0, 144), (3, 208)]):
    pixels += verify_pixels(complete, draw(maps[index], art, colors, width), width, 160, 76)
pixels += verify_pixels(complete, draw(bytes([8]) + maps[1][1:41], art, colors, 256), 256, 112, 144)
for value, digits, x, y in [(score, 7, 184, 112), (0, 5, 200, 136), (0, 5, 200, 160)]:
    for n, digit in enumerate(str(value).rjust(digits)):
        if digit != ' ':
            pixels += verify_pixels(complete, draw(bytes([1, 0, 1, 0, int(digit)*2, 252]), number_art, colors, 8), 8, x+4+n*8, y)
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
report = dict(passed=True, era=era, states=states, semantic_words=states*16, elapsed_ticks=elapsed,
              score=score, bonus=bonus, lives=lives, checkpoint=checkpoint, hurt_ticks=values[6],
              emulator_frames=frames, result_pixels=pixels, original_hud_pixels=hud_pixels,
              hud_ring_label_checked=rings != 0, captures=captures,
              start=f'Act 2 {era_name} ordinary spawn via Start+C then X; trace begins at update 1',
              host_sanitizers=['address', 'undefined behavior'],
              controller_route=(folder/'route.txt').read_text().strip(),
              route_sha256=sha(folder/'route.txt'),
              trace_sha256=sha(folder/'player-target-trace.txt'),
              disc_sha256=sha(ROOT/'dist/sonic-cd-saturn-prototype.bin'),
              stage_sha256=sha(ROOT/f'assets/generated/ppz12{chr(65+era)}.bin'),
              tool_hashes={name: sha(ROOT/'tools'/name) for name in ['emulator_test.c', 'act_pad_replay.h', 'act_test.c', 'run-act2-era.sh', 'test-act2-era-emulator.sh', 'check_act2_era.py', 'hud_pixels.py']},
              hardware_tested=False,
              limits=f'One controller route in {era_name}. Host replay shares the native core; it does not establish retail-console parity or hardware acceptance.')
(folder/'report.json').write_text(json.dumps(report, indent=2)+'\n')
print(f'Act 2 {era_name} passed: {states} states / {states*16} words; {pixels} source result pixels; score {score}')
