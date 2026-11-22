#!/usr/bin/env python3
"""Verify actual R5 hold/redraw profile records, not player threshold crossings.

Enable SCD_FRAME_PROFILE in src/frame_profile.h for an instrumented build and
run tools/test_qq_route.py --act 2 --era A (and C) --require-r5-dispatch.
Restore profiling to 0 and rebuild before candidate QA. Word 30 carries the
actual draw_stage operation. Both target VBlank stamps and profile sequence
numbers must prove that the redraw follows its hold in the next frame.
The emulator's CC route frame numbers are a different clock and are not used.
"""
import argparse
from pathlib import Path

FRAME_LIMIT = 49_355
MARGIN = 2_000
MAX_WORK = FRAME_LIMIT - MARGIN
MAGIC = 0x52350000


def profile_rows(text):
    rows = []
    for line in text.splitlines():
        if line.startswith('Frame profile:'):
            row = list(map(int, line.split(':', 1)[1].split()))
            assert len(row) == 32, 'profile needs all 32 words, including R5 marker'
            rows.append(row)
    assert rows, 'missing instrumented Frame profile records'
    assert all(b[0] == a[0] + 1 for a, b in zip(rows, rows[1:])), 'missing/duplicate profile records'
    return rows


def verify(text):
    profiles = profile_rows(text)
    pending = None
    measured = []
    for row in profiles:
        marker = row[30]
        if marker & 0xffff0000 != MAGIC:
            assert pending is None, 'hold was not followed by a redraw in the next profile'
            continue
        assert marker in (MAGIC | 1, MAGIC | 2, MAGIC | 6), f'unknown R5 marker {marker:#x}'
        if marker == MAGIC | 1:
            assert pending is None, 'second hold before completing the first redraw'
            pending = row
            continue
        assert pending is not None, 'redraw without an observed hold'
        assert marker == MAGIC | 6, 'redraw did not complete slave work'
        assert row[0] == pending[0] + 1, 'redraw is not the next profile'
        assert row[2] == pending[2] + 1, 'redraw is not the next target VBlank'
        # Guard the 16-bit FRT spans against an unnoticed long/wrapped frame.
        stamps = [row[2], *row[12:21]]
        assert all(a <= b for a, b in zip(stamps, stamps[1:])), 'non-monotonic VBlank stamps'
        assert stamps[-1] - stamps[0] <= 1, 'redraw spans multiple refreshes'
        work = sum(row[6:12])
        assert work <= MAX_WORK, f'R5 redraw profile {row[0]} work {work} > {MAX_WORK}'
        measured.append(dict(hold_profile=pending[0], redraw_profile=row[0],
                             hold_vblank=pending[2], redraw_vblank=row[2], work=work,
                             margin=FRAME_LIMIT-work))
        pending = None
    assert pending is None, 'log ended before the redraw completed'
    assert measured, 'no actual R5 hold/redraw markers; old threshold-only evidence is insufficient'
    return measured


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    args = parser.parse_args()
    measured = verify(args.log.read_text())
    for item in measured:
        print(f"R5 target VBlank {item['hold_vblank']} -> {item['redraw_vblank']}: "
              f"post-reset={item['work']} margin={item['margin']}")
    print(f'PASS: QQ2 switch margin: {len(measured)} actual slave redraws, '
          f'max post-reset {max(r["work"] for r in measured)} <= {MAX_WORK}')


if __name__ == '__main__':
    main()
