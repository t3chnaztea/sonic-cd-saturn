#!/usr/bin/env python3
"""Fill the PENDING evidence fields of a release-notes draft from a passing full QA run.

  python3 tools/fill_release_notes.py --root ../sonic-cd-saturn-rc \\
      --qa build/qa-loops/<stamp>/report.json [--run-label run01] [--notes RELEASE-NOTES-V0.078.md]

--root is the tree that ran the QA (its Makefile, qa report and zone matrix).
The notes file (default: RELEASE-NOTES-V<version>.md in this tree) is rewritten
in place. Every value comes from the reports; the script stops when the QA or
the matrix did not pass, the BINs differ, the matrix tree was dirty, or a
PENDING marker is left over.
"""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
ZONES = (('PPZ', 'ppz'), ('CC', 'cc'), ('TT', 'tt'), ('QQ', 'qq'), ('WW', 'ww'), ('SS', 'ss'), ('MM', 'mm'))
GATES = ('retail', 'routes', 'art', 'travel', 'campaign')


def count(entries):
    return f"{sum(e.get('status') == 'pass' for e in entries.values())}/{len(entries)}"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--qa', type=Path, required=True, help='qa-loop report, relative to --root')
    parser.add_argument('--run-label', help='e.g. run01 (default: the qa-loops folder name)')
    parser.add_argument('--notes', type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    make = (root/'Makefile').read_text()
    version = re.search(r'^IP_VERSION:= V(\d+\.\d+)$', make, re.M)[1]
    date = re.search(r'^IP_RELEASE_DATE:= (\d{8})$', make, re.M)[1]
    notes = args.notes or ROOT/f'RELEASE-NOTES-V{version}.md'
    qa_path = args.qa if args.qa.is_absolute() else root/args.qa
    qa = json.loads(qa_path.read_text())
    assert qa.get('passed') is True and qa.get('mode') == 'full' and qa.get('status') == 'passed', 'QA did not pass'
    disc = qa['disc_sha256']
    matrix_rel = qa['zone_gates_report']
    matrix = json.loads((root/matrix_rel).read_text())
    assert matrix.get('passed') is True and matrix.get('bin_sha256') == matrix.get('bin_sha256_end') == disc, 'matrix BIN or status'
    assert matrix.get('git_dirty') is False, 'matrix ran on a dirty tree'
    commit = matrix['git_head'][:7]
    minutes = sum(s.get('seconds', 0) for s in qa['steps']) / 60
    label = args.run_label or qa_path.parent.name
    qa_rel = qa_path.relative_to(root) if qa_path.is_relative_to(root) else qa_path
    results = matrix['results']

    text = notes.read_text()

    def put(old, new):
        nonlocal text
        assert text.count(old) == 1, ('template line changed', old)
        text = text.replace(old, new)

    put('DRAFT: every PENDING field is filled from the passing full QA run on the\n'
        'final BIN. Do not package this draft.\n\n', '')
    put('BIN SHA-256: `PENDING`', f'BIN SHA-256: `{disc}`')
    put(f'Source: commit `PENDING`, Makefile V{version} / PENDING, clean tree.',
        f'Source: commit `{commit}`, Makefile V{version} / {date}, clean tree.')
    put('Full QA runNN passed PENDING commands on this one BIN (PENDING min):',
        f'Full QA {label} passed {len(qa["steps"])}/{len(qa["steps"])} commands on this one BIN ({minutes:.1f} min):')
    put('`build/qa-loops/PENDING/report.json`.', f'`{qa_rel}`.')
    put('Zone gates on the same BIN (`build/zone-gates/PENDING/report.json`):',
        f'Zone gates on the same BIN (`{matrix_rel}`):')
    for label_zone, zone in ZONES:
        row = re.search(rf'^\| {label_zone} \|.*$', text, re.M)
        assert row, ('table row', label_zone)
        cells = [count(results[zone][gate]) for gate in GATES]
        text = text.replace(row[0], f'| {label_zone} | ' + ' | '.join(cells) + ' |')
    sp = results.get('sp', {}).get('special')
    assert sp, 'matrix has no special-stage cases'
    put('Special-stage and front-end gates on the same BIN (zone `sp`, 42 cases):\nPENDING.',
        f'Special-stage and front-end gates on the same BIN (zone `sp`, {len(sp)} cases):\n{count(sp)} pass.')
    put('The BIN hash must be unchanged at the end of the zone gates.',
        'The BIN hash was unchanged at the end of the zone gates.')
    assert 'PENDING' not in text, 'PENDING left in the notes'
    notes.write_text(text)
    print(f'Filled {notes.name}: BIN {disc[:12]}, commit {commit}, {len(qa["steps"])} steps, {minutes:.1f} min, sp {count(sp)}')


if __name__ == '__main__':
    sys.exit(main())
