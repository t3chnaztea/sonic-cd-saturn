#!/usr/bin/env python3
"""Keep stored route scripts on the PLC 2 title-card unlock (src/title_card.c).

Since commit 2300257 the native title card holds controls through the
original's PLC 2 wait: T - 2 more updates than before (tools/title_card_plc.py,
plc2_batches). A script searched on the earlier native unlock reaches its
route pads that many updates early; prepending that many neutral pads ("W 0",
the lead tools/retail_parity.py used to add) replays it exactly as its old
retail-aligned run. A script searched on the current unlock needs no lead.

tests/routes/unlock-lead.json records every script below with its lead and
the SHA-256 of its content in the current convention.

  --check            exit 1 if a script is unregistered, changed since it was
                     registered, or a file in a route folder is not listed.
  --apply            register every changed script: a script whose current
                     content was committed before the cutover (not a
                     descendant of CUTOVER) gets its lead prepended; one
                     committed on top of it is taken as is. Uncommitted
                     changes are refused (commit first, or --register).
  --register PATH..  take these scripts as already in the current convention
                     (e.g. a search run on the current unlock).
  --lead PATH..      prepend the lead to these scripts and register them.

Multi-act recordings are listed in EXCLUDED with the reason; pS/pJ are
regenerated from their legs by tools/ppz_chain_scripts.py.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from title_card_plc import native_wait

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / 'tests/routes'
MANIFEST = ROUTES / 'unlock-lead.json'
CUTOVER = '2300257'
ERA = 'ABCD'
EXCLUDED = {
    'ppz/pS.txt': 'chained from p0A + p1A + p2D.found by tools/ppz_chain_scripts.py',
    'ppz/pJ.txt': 'chained from pJ0 + pJ1 + p2C by tools/ppz_chain_scripts.py',
    'ww/ww3D-report.json': 'host route evidence, not a controller script',
}
for _name in ('act1-return', 'future-return', 'good-results', 'past-return', 'present-future', 'special-entry'):
    EXCLUDED[f'ppz/natural-{_name}.pads'] = ('Saturn per-frame journey recording across act starts; '
                                             'needs a lead at each title card (not migrated)')


def scripts():
    """{relative path: (native zone, 0-based act, era index)} for every single-card script."""
    out = {}
    windows = [(a, e) for a in range(3) for e in (ERA[2:] if a == 2 else ERA)]
    for a, e in windows:
        ei = ERA.index(e)
        out[f'ppz/p{a}{e}.txt'] = (0, a, ei)
        out[f'cc/cc{a + 1}{e}.script'] = (1, a, ei)
        out[f'tt/tt{a + 1}{e}.txt'] = (2, a, ei)
        out[f'qq/qq{a + 1}{e}.txt'] = (3, a, ei)
        out[f'ww/ww{a + 1}{e}.txt'] = (4, a, ei)
    for a in range(2):
        for pair in ('AB', 'AD', 'BA', 'CA', 'DA'):
            out[f'tt/travel/tt{a + 1}{pair}.txt'] = (2, a, ERA.index(pair[0]))
            out[f'cc/travel/cc{a + 1}{pair}.txt'] = (1, a, ERA.index(pair[0]))
            out[f'qq/travel/qq{a + 1}{pair}.txt'] = (3, a, ERA.index(pair[0]))
            out[f'ppz/travel/ppz{a + 1}{pair}.txt'] = (0, a, ERA.index(pair[0]))
        out[f'tt/campaign/tt{a + 1}-good.txt'] = (2, a, 0)
        out[f'qq/campaign/qq{a + 1}-good.txt'] = (3, a, 0)
    # Big-ring special-stage entries (tools/test_special_entry.py), searched on
    # the current unlock: 50+ rings and the big ring instead of the sign.
    out.update({'cc/special-entry-cc1A.pads': (1, 0, 0), 'tt/special-entry-tt1A.pads': (2, 0, 0),
                'qq/special-entry-qq1A.pads': (3, 0, 0), 'ww/special-entry-ww1B.pads': (4, 0, 1)})
    out.update({
        'ppz/p2D.found.txt': (0, 2, 3), 'ppz/p0A.seq.txt': (0, 0, 0), 'ppz/p1B.nohit.txt': (0, 1, 1),
        'ppz/p1C.era.txt': (0, 1, 2), 'ppz/p1D.era.txt': (0, 1, 3),
        'ppz/pJ0.txt': (0, 0, 0), 'ppz/pJ1.txt': (0, 1, 0),
        'cc/cc2C-seed24.script': (1, 1, 2),
        'cc/cc2C-seed28.script': (1, 1, 2),     # host/Saturn regression: TT-overlay explosion tables split it at seq 5542
        'cc/generator.script': (1, 0, 1),       # cc_campaign_search mode 0@B: CC1 Past entry
        'cc/campaign-cc1.script': (1, 0, 0),    # mode 0: CC1 Present
        'cc/campaign-good.script': (1, 2, 2),   # CC3 Good Future after the continue
        'cc/campaign-bad.script': (1, 2, 3),
    })
    return {p: v for p, v in out.items() if (ROUTES / p).is_file()}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True)


def committed_after_cutover(path):
    """True when the commit that set this file's current content descends from CUTOVER."""
    rel = str(path.relative_to(ROOT))
    if git('diff', '--quiet', 'HEAD', '--', rel).returncode:
        return None  # uncommitted change
    commit = git('log', '-1', '--format=%H', '--', rel).stdout.strip()
    return git('merge-base', '--is-ancestor', CUTOVER, commit).returncode == 0


def lead(path, w):
    path.write_text(f'{w} 0\n' + path.read_text())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--check', action='store_true')
    g.add_argument('--apply', action='store_true')
    g.add_argument('--register', nargs='+', metavar='PATH')
    g.add_argument('--lead', nargs='+', metavar='PATH')
    a = ap.parse_args()
    known = scripts()
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.is_file() else {}

    def wait(rel):
        return native_wait(*known[rel])

    def record(rel):
        manifest[rel] = dict(lead=wait(rel), sha256=sha(ROUTES / rel))

    if a.register or a.lead:
        for p in a.register or a.lead:
            rel = str(Path(p).resolve().relative_to(ROUTES.resolve()))
            assert rel in known, f'{rel}: not a listed route script'
            if a.lead:
                lead(ROUTES / rel, wait(rel))
            record(rel)
    elif a.apply:
        for rel in sorted(known):
            path = ROUTES / rel
            if manifest.get(rel, {}).get('sha256') == sha(path):
                continue
            after = committed_after_cutover(path)
            if after is None:
                sys.exit(f'FAIL: {rel} has uncommitted changes; commit it, or use --register / --lead')
            if not after:
                lead(path, wait(rel))
                print(f'lead {wait(rel)}: {rel}')
            else:
                print(f'current: {rel}')
            record(rel)
    if not a.check:
        MANIFEST.write_text(json.dumps(dict(sorted(manifest.items())), indent=1) + '\n')
    bad = []
    for rel in sorted(known):
        entry = manifest.get(rel)
        if not entry:
            bad.append(f'{rel}: unregistered')
        elif entry['sha256'] != sha(ROUTES / rel):
            bad.append(f'{rel}: changed since registered (lead {entry["lead"]})')
        elif entry['lead'] != wait(rel):
            bad.append(f'{rel}: registered lead {entry["lead"]} != table {wait(rel)}')
    folders = {'ppz', 'cc', 'tt', 'qq', 'ww', 'tt/travel', 'cc/travel', 'qq/travel', 'ppz/travel', 'tt/campaign', 'qq/campaign'}
    for f in sorted(ROUTES.rglob('*')):
        rel = str(f.relative_to(ROUTES))
        if f.is_file() and not f.name.startswith('.') and str(Path(rel).parent) in folders and rel not in known and rel not in EXCLUDED:
            bad.append(f'{rel}: not listed in tools/route_unlock_lead.py')
    if bad:
        print('FAIL: route scripts off the PLC 2 unlock convention (tools/route_unlock_lead.py --apply):')
        print('\n'.join('  ' + b for b in bad))
        return 1
    print(f'PASS: {len(known)} route scripts on the PLC 2 title-card unlock; {len(EXCLUDED)} excluded')
    return 0


if __name__ == '__main__':
    sys.exit(main())
