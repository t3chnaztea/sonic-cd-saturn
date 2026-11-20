#!/usr/bin/env python3
"""Frame headroom per Saturn route window from SCD_FRAME_PROFILE records.

Diagnostic only. Build with SCD_FRAME_PROFILE 1 (src/frame_profile.h), run the
route tools without --host-only and with FRAME_PROFILE_ALL=1 in the
environment (tools/emulator_test.c then prints every "Frame profile:" record
of the run into results.log), then:

  python3 tools/frame_headroom.py [--json out.json] [WINDOW ...]

WINDOW is PPZ1A .. QQ3D (default: all 40). Restore SCD_FRAME_PROFILE 0 and
rebuild before any acceptance run; profiled logs never prove pacing.

A gameplay update is a record whose player frame advanced and whose nine phase
end stamps stay within one VBlank of its start (loading and fade frames that
span refreshes are skipped; their 16-bit FRT spans can wrap). Cost is the sum
of the nine FRT phase durations (CPU/8 ticks), from the post-VBlank-out wake
to the end of sprite_draw. Slack is measured, not assumed: the next record's
word 23 high half holds the FRT from this update's end to the following
VBlank-in, where libyaul commits vdp2_sync and the DMA queue; an update that
misses it is late. Deadline = cost + slack, the time actually available.

For scale only, one refresh at the 320-pixel mode's 26.8466 MHz CPU clock
(libyaul vdp2_tvmd_display_res_set selects it for VDP2_TVMD_HORZ_NORMAL_A) is
26.8466 MHz / 8 / 59.94 Hz = 55,987 ticks; the 59.7k figure is the 352-pixel
mode's 28.636 MHz clock and does not apply. The VBlank-in deadline comes
before the end of the refresh.
"""
import argparse
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
REFRESH = 55_987
PHASES = ('input', 'audio', 'update', 'fg-map', 'bg-lines', 'bg-cache', 'stage-draw', 'mailbox', 'sprites')
SPANS = ('objects', 'ring-loss', 'ring-cmds', 'view-list')
WINDOWS = [f'{z}{a}{e}' for z in ('PPZ', 'CC', 'TT', 'QQ')
           for a, e in [(1, x) for x in 'ABCD'] + [(2, x) for x in 'ABCD'] + [(3, x) for x in 'CD']]


def log_path(window):
    zone, act, era = window[:-2].lower(), window[-2], window[-1]
    return ROOT/f'build/{zone}{act}/controller/{era}/results.log'


def rows_of(text):
    rows = []
    for line in text.splitlines():
        if line.startswith('Frame profile:'):
            row = list(map(int, line.split(':', 1)[1].split()))
            if len(row) == 32:
                rows.append(row)
    return rows


def analyse(rows):
    updates, skipped = [], 0
    for prev, row, nxt in zip([None] + rows, rows, rows[1:] + [None]):
        if prev is None or row[1] == prev[1]:
            continue
        if row[20] - row[2] > 1:
            skipped += 1
            continue
        slack = nxt[23] >> 16 if nxt is not None and nxt[0] == row[0] + 1 else 0xffff
        updates.append((sum(row[3:12]), None if slack == 0xffff else slack, row))
    if not updates:
        return None
    costs = sorted(u[0] for u in updates)
    cost, slack, worst = max(updates, key=lambda u: u[0])
    timed = [u for u in updates if u[1] is not None]
    deadlines = [c + s for c, s, _ in timed]
    deadline = round(statistics.median(deadlines)) if deadlines else None
    tight = min(timed, key=lambda u: u[1]) if timed else None
    phases = dict(zip(PHASES, worst[3:12]))
    return dict(updates=len(updates), skipped_multi_refresh=skipped, untimed=len(updates) - len(timed),
                worst=cost, worst_slack=slack, p99=costs[min(len(costs) - 1, int(len(costs) * 0.99))],
                mean=round(sum(costs) / len(costs)), deadline_median=deadline,
                deadline_min=min(deadlines) if deadlines else None,
                worst_pct=round(100 * cost / deadline, 1) if deadline else None,
                min_slack=tight[1] if tight else None, min_slack_cost=tight[0] if tight else None,
                over_90=sum(s < 0.1 * (c + s) for c, s, _ in timed),
                over_80=sum(s < 0.2 * (c + s) for c, s, _ in timed),
                worst_profile=worst[0], worst_player_frame=worst[1], worst_camera=[worst[21], worst[22]],
                worst_sprites=worst[23] & 0xffff, worst_phases=phases,
                worst_sprite_sub=dict(zip(('build', 'clear-wait', 'transfer', 'draw-done'), worst[24:28])),
                worst_spans=dict(zip(SPANS, worst[28:32])), top_phase=max(phases, key=phases.get))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('windows', nargs='*', default=WINDOWS)
    ap.add_argument('--json')
    args = ap.parse_args()
    out = {}
    print(f'{"route":6} {"upd":>5} {"worst":>6} {"p99":>6} {"dline":>6} {"%":>5} {"minslk":>6} {">90%":>4} {">80%":>4}  top phase at worst')
    for w in args.windows:
        path = log_path(w)
        res = analyse(rows_of(path.read_text())) if path.exists() else None
        out[w] = res
        if res is None:
            print(f'{w:6} missing profile records ({path.relative_to(ROOT)})')
            continue
        top = res['top_phase']
        print(f'{w:6} {res["updates"]:5} {res["worst"]:6} {res["p99"]:6} {res["deadline_median"]!s:>6} {res["worst_pct"]!s:>5} '
              f'{res["min_slack"]!s:>6} {res["over_90"]:4} {res["over_80"]:4}  {top} {res["worst_phases"][top]} '
              f'objects {res["worst_spans"]["objects"]} (frame {res["worst_player_frame"]}, '
              f'cam {res["worst_camera"][0]},{res["worst_camera"][1]}, {res["worst_sprites"]} cmds)')
    if args.json:
        Path(args.json).write_text(json.dumps(dict(refresh=REFRESH, windows=out), indent=1) + '\n')


if __name__ == '__main__':
    main()
