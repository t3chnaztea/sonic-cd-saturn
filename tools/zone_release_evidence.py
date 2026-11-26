"""Validate and stage the complete private release evidence set."""
import hashlib
import json
from pathlib import Path
import re

ZONES = ('ppz', 'cc', 'tt', 'qq', 'ww', 'ss', 'mm')
RELEASE_ZONES = {'0.076': ZONES[:5], '0.077': ZONES[:6], '0.078': ZONES, '0.079': ZONES, '0.080': ZONES, '0.081': ZONES, '0.082': ZONES, '0.083': ZONES}
GATES = ('retail', 'routes', 'art', 'travel', 'campaign')
# Special stages: the pseudo-zone 'sp' carries one gate, 'special', whose cases
# tools/zone-gates.py runs from tests/special/gate-cases.json.
SPECIAL, SPECIAL_GATE = 'sp', 'special'
RELEASE_SPECIAL = {'0.078', '0.079', '0.080', '0.081', '0.082', '0.083'}
SPECIAL_CASES = tuple([f'SP{n}-{kind}' for n in range(1, 9) for kind in ('win', 'timeout', 'hazard')]
                      + [f'BIGRING-{z.upper()}' for z in ZONES]
                      + ['SAVE-progression', 'ENDING-good', 'ENDING-bad', 'STONES-return']
                      # Front end: Time Attack menu, runs, records, unlocks and in-level rules.
                      + ['FRONTEND']
                      # Special-stage modes: attract demos and Time Attack (tools/special_mode_gate.py).
                      + ['DEMO-SS1', 'DEMO-SS6', 'TA-SS1-win', 'TA-SS1-exit', 'SP8-credits']
                      # Every stored route window draws no object without its own art.
                      + ['ART-MISSES'])


def release_version(root):
    version = re.search(r'^IP_VERSION:= V(\d+\.\d+)$', (Path(root)/'Makefile').read_text(), re.M)
    assert version and version[1] in RELEASE_ZONES, 'Unsupported release evidence scope'
    return version[1]


def release_zones(root):
    return RELEASE_ZONES[release_version(root)]


def release_special(root):
    return release_version(root) in RELEASE_SPECIAL


def matrix_command(zones, special=False):
    return ['python3', 'tools/zone-gates.py', '--zones', ','.join([*zones, *([SPECIAL] if special else [])]),
            '--gates', ','.join([*GATES, *([SPECIAL_GATE] if special else [])])]


def canonical_matrix_command(command):
    """Remove only resource/recovery options, never scope or window filters."""
    if not isinstance(command, list) or command[:2] != ['python3', 'tools/zone-gates.py']:
        return None
    result, seen, i = command[:2], set(), 2
    while i < len(command):
        flag = command[i]
        if flag in ('--jobs', '--resume', '--resume-source-report', '--migration'):
            if flag in seen or i+1 >= len(command):
                return None
            if not isinstance(command[i+1], str) or not command[i+1] or command[i+1].startswith('--'):
                return None
            seen.add(flag)
            if flag == '--jobs' and command[i+1] != '1':
                return None
            i += 2
        else:
            result.append(flag)
            i += 1
    return result


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_windows(zones=ZONES, special=False):
    expected = {SPECIAL: {SPECIAL_GATE: set(SPECIAL_CASES)}} if special else {}
    for zone in zones:
        acts = [f'{zone.upper()}{a}{e}' for a, eras in ((1, 'ABCD'), (2, 'ABCD'), (3, 'CD')) for e in eras]
        expected[zone] = {gate: set(acts) for gate in ('retail', 'routes', 'art')}
        if zone == 'mm':
            # BOSS_8.C's fight and Amy banks (tools/test_zone_art_emulator.py R83C-fight/-ending).
            expected[zone]['art'] |= {'MM3C-fight', 'MM3C-ending'}
        expected[zone]['travel'] = {f'{zone.upper()}{a}{pair}' for a in (1, 2)
                                    for pair in ('AB', 'AD', 'BA', 'CA', 'DA')}
        expected[zone]['campaign'] = ({'checkpoint', 'act3-good-bad', 'cc3-continue-C',
                                       'cc3-continue-D', 'generator-continue'} if zone == 'cc'
                                      else {f'{zone.upper()}{a}' for a in (1, 2, 3)})
    return expected


def audit(root, qa, disc_sha, *, staged=False):
    """Return (matrix, [(source, package-relative destination), ...]).

    In staged mode read dist/zone-evidence rather than mutable build outputs.
    Original evidence paths remain in the matrix for traceability.
    """
    root = Path(root).resolve()
    zones, special = release_zones(root), release_special(root)
    assert qa.get('passed') is True and qa.get('mode') == 'full' and qa.get('status') == 'passed', 'Missing full QA pass'
    assert qa.get('disc_sha256') == disc_sha, 'QA BIN mismatch'
    assert any(canonical_matrix_command(s.get('command', [])) == matrix_command(zones, special)
               and type(s.get('exit_code')) is int and s['exit_code'] == 0 for s in qa['steps']), 'Missing full release zone gate'
    original = Path(qa['zone_gates_report'])
    assert not original.is_absolute() and '..' not in original.parts, 'Unsafe matrix path'
    assert original.parts[:2] == ('build', 'zone-gates') and original.name == 'report.json', 'Unexpected matrix path'
    base = original.parent
    destination = Path('zone-evidence/report.json')
    path = root / ('dist' if staged else '') / (destination if staged else original)
    assert digest(path) == qa['zone_gates_report_sha256'], 'Changed zone matrix'
    matrix = json.loads(path.read_text())
    assert matrix.get('passed') is True and matrix.get('status') == 'passed', 'Zone matrix did not pass'
    assert matrix.get('bin_sha256') == matrix.get('bin_sha256_end') == disc_sha, 'Zone matrix BIN mismatch'
    assert matrix.get('failed_gates') == 0, 'Failed zone gates'
    assert matrix.get('zones') == matrix_command(zones, special)[3].split(',') and matrix.get('gates') == matrix_command(zones, special)[5].split(','), 'Incomplete matrix scope'
    assert matrix.get('hardware_tested') is False, 'Matrix must not claim hardware acceptance'
    results = matrix['results']
    expected = expected_windows(zones, special)
    assert set(results) == set(expected), 'Missing or extra zones'
    artifacts = {destination: path}
    children = {}
    for zone, gates in expected.items():
        assert set(results[zone]) == set(gates), ('Missing or extra gates', zone)
        for gate, names in gates.items():
            entries = results[zone][gate]
            assert set(entries) == names, ('Missing or extra windows', zone, gate)
            for name, entry in entries.items():
                assert entry.get('status') == 'pass' and entry.get('returncode') == 0, ('Failed window', name, gate)
                child = None
                for field, folder in (('evidence', 'evidence'), ('log', 'logs')):
                    source = Path(entry[field])
                    assert not source.is_absolute() and '..' not in source.parts, ('Unsafe artifact path', source)
                    relative = source.relative_to(base)
                    assert relative.parts[0] == folder, ('Artifact outside run', source)
                    target = Path('zone-evidence') / relative
                    artifact = root / ('dist' if staged else '') / (target if staged else source)
                    assert artifact.resolve().is_relative_to(root), ('Artifact outside repository', artifact)
                    assert digest(artifact) == entry[field + '_sha256'], ('Changed zone artifact', source)
                    artifacts[target] = artifact
                    if field == 'evidence':
                        child = json.loads(artifact.read_text())
                if gate == 'retail':
                    parity = child['retail_parity']
                    assert parity.get('compared', 0) > 0 and parity.get('contiguous') == parity['compared'], ('Incomplete retail match', name)
                    assert parity.get('contiguous_all_fields') == parity['compared'] and not parity.get('first_field_divergence'), ('Incomplete nine-field retail match', name)
                    tally = re.match(r'Tally complete: sequence=(\d+)', parity.get('native_end') or '')
                    assert tally, ('Retail replay did not finish', name)
                    assert 'retail_restart' in parity and (parity['retail_restart'] is None or parity['retail_restart'] > int(tally[1])), ('Retail restart', name)
                    assert parity.get('retail_updates', 0) > int(tally[1]) + 1, ('Truncated retail window', name)
                    assert child.get('inputs'), ('Missing retail inputs', name)
                else:
                    assert child.get('disc_sha256') == disc_sha, ('Child BIN mismatch', name, gate)
                    assert child.get('passed') is True, ('Child did not pass', name, gate)
                if gate == 'routes':
                    assert child.get('respawns') == 0 and child.get('late_gameplay_intervals') == [], ('Route regression', name)
                children[zone, gate, name] = child
    checkpoint = children['cc', 'campaign', 'checkpoint']
    ppz3 = children['ppz', 'campaign', 'PPZ3']
    assert checkpoint.get('ppz3_report_sha256') == results['ppz']['campaign']['PPZ3']['evidence_sha256'], 'CC checkpoint is not linked to the earned PPZ3 report'
    assert checkpoint.get('backup_sha256') == ppz3.get('backup_after_sha256') and checkpoint.get('backup_sha256'), 'CC checkpoint uses a different PPZ3 save'
    assert checkpoint.get('saved_flags', 0) & 0x100, 'PPZ Good Future flag missing'
    cc = children['cc', 'campaign', 'act3-good-bad']
    assert cc.get('entry_backup_sha256') == checkpoint['backup_sha256'], 'CC campaign uses a different checkpoint'
    links = []
    if 'ss' in zones:
        links += [('ss', 1, 'ww', 'WW3'), ('ss', 2, 'ss', 'SS1'), ('ss', 3, 'ss', 'SS2')]
    if 'mm' in zones:
        links += [('mm', 1, 'ss', 'SS3'), ('mm', 2, 'mm', 'MM1'), ('mm', 3, 'mm', 'MM2')]
    for zone, act, prior_zone, prior_name in links:
        name = f'{zone.upper()}{act}'
        child = children[zone, 'campaign', name]
        prior = children[prior_zone, 'campaign', prior_name]
        prior_hash = results[prior_zone]['campaign'][prior_name]['evidence_sha256']
        assert (child.get('entry_evidence') or {}).get('sha256') == prior_hash, f'{name} is not linked to the earned {prior_name} report'
        backup_hash = prior.get('backup_after_sha256')
        assert backup_hash and child.get('entry_backup_sha256') == backup_hash, f'{name} uses a different {prior_name} save'
    if 'mm' in zones:
        # The last zone ends the game: completed save, ALL ZONES CLEAR, title, cold Continue.
        final = children['mm', 'campaign', 'MM3']
        assert final.get('completed') == 1 and final.get('title_frame'), 'MM3 did not end the game'
    return matrix, [(source, target) for target, source in sorted(artifacts.items())]
