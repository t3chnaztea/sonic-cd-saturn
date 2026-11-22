#!/usr/bin/env python3
"""Shift a recorded act reference by the V0.057 title-card hold.

The card now releases at update 130 and the first input is accepted at 131,
two updates later than V0.056. A reference recorded before that change feeds
its first input while the card still masks the controller. Holding the entry
input for two extra updates keeps the whole route aligned to the player's
motion, which is the same correction build/title-card-clock/v057-route-input
applied to the journey route.

This only builds the controller input for a re-recording run. The 16 state
words it copies are placeholders; SCD_ACT_PAD_RECORD ignores them, and the
run's own output becomes the new strict reference.
"""
import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('reference', type=Path)
parser.add_argument('output', type=Path)
parser.add_argument('--hold', type=int, default=2, help='extra held updates at act entry')
args = parser.parse_args()

rows = [line.split() for line in args.reference.read_text().splitlines()]
assert rows and all(len(r) == 18 for r in rows), 'invalid reference trace'
assert int(rows[0][1]) == 0, 'reference must start with no input'
assert args.hold >= 0
first = int(rows[0][0])
shifted = [list(rows[0]) for _ in range(args.hold)] + [list(r) for r in rows]
for index, row in enumerate(shifted):
    row[0] = str(first + index)   # contiguous diagnostic sequence
    row[8] = f'{index + 1:x}'     # words[6]: the player frame the loader checks
args.output.write_text(''.join(' '.join(r) + '\n' for r in shifted))
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
args.output.with_suffix('.recipe.json').write_text(json.dumps({
    'source': str(args.reference), 'source_sha256': sha(args.reference),
    'output_sha256': sha(args.output),
    'held_updates_inserted_at_entry': args.hold,
    'source_states': len(rows), 'input_states': len(shifted),
    'reason': 'V0.057 holds the controller through update 130; the pre-V0.057 '
              'reference fed its first input at 129. State words here are '
              'placeholders for SCD_ACT_PAD_RECORD only.',
    'is_a_verified_reference': False}, indent=2) + '\n')
print(f'Re-record input: {len(shifted)} states from {len(rows)}; +{args.hold} held at entry')
