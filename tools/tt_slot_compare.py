#!/usr/bin/env python3
"""Native vs retail Tidal Tempest actor-slot occupancy, per level update.

usage: tt_slot_compare.py [--act N] [--era E ...] [--until ROW] [--limit N] [--json PATH]

Retail FindObjSlot/actwkchk (ACTSET.C:383) hands out the lowest free actor
from actwk[32]; native pool slot i is actwk[i + 1] and stands for retail
actwk[i + 32] (src/objects_tt_wave.inc). A native child lands in the retail
child's slot only while both builds hold the same slots, so this tool lists
every interval in which a retail dynamic slot (32-127) is occupied in one
build and free in the other.

Inputs come from a fresh retail-parity run of the window (tools/test_tt_route.py
--host-only, run first): build/tt<act>/controller/<era>/{parity-script.txt,
retail-lag.rows, retail.rows, report.json, script.txt}. The native side is
that window's host replayed under the same alignment (TT_ROUTE_UNLOCK_AT,
TT_ROUTE_LAG, TT_ROUTE_VINT_AT, as tools/retail_parity.py) with
TT_ROUTE_OBJECTS; the retail side is tools/retail_probe.py with
TT_PROBE_OBJECTS, cached under build/tt-slots/ by script, ISO and tool hashes.
Both dumps label a row with the retail row (native sequence + 1).

Exit status 0 when no interval starts at or before --until (default: the
whole window), 1 otherwise.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ERAS = {1: 'ABCD', 2: 'ABCD', 3: 'CD'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path, offset):
    rows = defaultdict(dict)
    for line in Path(path).read_text().splitlines():
        f = line.split()
        if len(f) < 13 or f[1] == 'camera':
            continue
        slot = int(f[1]) + offset
        if slot >= 32:
            rows[int(f[0])][slot] = (int(f[2]), int(f[3]), int(f[4]), int(f[5]), int(f[7]))
    return rows


def intervals(native, retail, skip=()):
    common = sorted((set(native) & set(retail)) - set(skip))
    open_, out = {}, []
    for row in common:
        a, b = native[row], retail[row]
        cur = {('native', k): a[k] for k in set(a) - set(b)}
        cur.update({('retail', k): b[k] for k in set(b) - set(a)})
        for key in list(open_):
            if key not in cur:
                out.append(dict(first=open_[key][0], last=row - 1, side=key[0], slot=key[1],
                                actor=open_[key][1]))
                del open_[key]
        for key, v in cur.items():
            open_.setdefault(key, (row, v))
    for key, (first, v) in open_.items():
        out.append(dict(first=first, last=common[-1], side=key[0], slot=key[1], actor=v))
    return sorted(out, key=lambda d: (d['first'], d['slot'])), (common[0], common[-1]) if common else (0, 0)


def window(act, era, until):
    src = ROOT / f'build/tt{act}/controller/{era}'
    host = ROOT / f'build/tt{act}/controller/tt_route_search'
    # A Saturn run (zone-gates routes) rewrites report.json without parity, and
    # source edits change the host: refresh the window's host-only parity run.
    subprocess.run(['python3', 'tools/test_tt_route.py', '--act', str(act), '--era', era, '--host-only'],
                   cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    report = json.loads((src / 'report.json').read_text())['retail_parity']
    held, unlock = report['held_unlock'], report['unlock']
    rows = [l.split() for l in (src / 'retail.rows').read_text().splitlines()]
    last = min(until or len(rows), len(rows) - 2)
    out = ROOT / f'build/tt-slots/tt{act}{era}'
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TT_ROUTE_UNLOCK_AT=str(held), TT_ROUTE_LAG=str(src / 'retail-lag.rows'),
               TT_ROUTE_TRACE='1', TT_ROUTE_OBJECTS=f'1:{last}:{out / "native.txt"}')
    if len(rows[held + 1]) > 18:
        env['TT_ROUTE_VINT_AT'] = f'{held}:{(int(rows[held + 1][17]) + 1) & 255}'
    subprocess.run([str(host), 'replay', f'{act - 1}:{era}', str(src / 'parity-script.txt'), str(last + 50),
                    os.devnull], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    key = json.dumps(dict(act=act, era=era, last=last, unlock=unlock, script=sha(src / 'script.txt'),
                          iso=sha(ROOT / 'build/retail/sonic.iso'),
                          tools=[sha(ROOT / 'tools' / n) for n in ('retail_probe.py', 'tt_slot_compare.py')]),
                     sort_keys=True)
    if not ((out / 'retail.key').exists() and (out / 'retail.key').read_text() == key):
        (out / 'retail.key').unlink(missing_ok=True)
        with (out / 'retail.log').open('w') as log:
            subprocess.run(['python3', 'tools/retail_probe.py', str(act), era, str(src / 'script.txt'),
                            str(out / 'retail.rows'), str(last + 2), '--native-unlock', str(unlock), '--round', '4'],
                           cwd=ROOT, env=dict(os.environ, TT_PROBE_OBJECTS=f'1:{last}:{out / "retail.txt"}'),
                           stdout=log, stderr=log, check=True)
        (out / 'retail.key').write_text(key)
    # The probe samples at the end of the V-INT frame in which levelFrames
    # advanced; when that update overran the frame (the next row took more than
    # one V-INT) the sample is mid-update, as tools/retail_parity.py skips.
    probe = [l.split() for l in (out / 'retail.rows').read_text().splitlines()]
    skip = [j for j in range(len(probe) - 1) if int(probe[j + 1][8]) != 1]
    return intervals(load(out / 'native.txt', 31), load(out / 'retail.txt', 0), skip)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--act', type=int, choices=(1, 2, 3), action='append')
    ap.add_argument('--era', action='append')
    ap.add_argument('--until', type=int, help='last retail row to compare (native sequence + 1)')
    ap.add_argument('--limit', type=int, default=10, help='intervals printed per window')
    ap.add_argument('--json', type=Path, help='write every interval here')
    a = ap.parse_args()
    result, bad = {}, 0
    for act in a.act or (1, 2, 3):
        for era in a.era or ERAS[act]:
            if era not in ERAS[act]:
                continue
            found, span = window(act, era, a.until)
            result[f'TT{act}{era}'] = dict(rows=span, intervals=found)
            bad += bool(found)
            print(f'TT{act}{era}: rows {span[0]}-{span[1]}, {len(found)} slot-mismatch intervals'
                  + (f', first at row {found[0]["first"]}' if found else ''))
            for d in found[:a.limit]:
                print(f'  rows {d["first"]}-{d["last"]} slot {d["slot"]} {d["side"]} only: '
                      f'actno {d["actor"][0]} sub {d["actor"][1]} rno {d["actor"][2]} at {d["actor"][3]},{d["actor"][4]}')
    if a.json:
        a.json.write_text(json.dumps(result, indent=1) + '\n')
    print(('PASS' if not bad else 'FAIL') + f': TT slot occupancy, {len(result) - bad}/{len(result)} windows with no mismatch')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
