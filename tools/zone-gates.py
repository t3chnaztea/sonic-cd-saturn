#!/usr/bin/env python3
"""Report the release zone exit gates on one BIN, over the existing tools.

Gates (each window is one existing tool run; nothing here re-implements a check):

  retail    whole-window nine-field host/retail match (all contiguous == compared > 0) per
            act/era window, read from the route tool's report.json
            ``retail_parity``, from each tool's --host-only mode (no Saturn
            run). The host route and the retail-aligned replay must both
            reach the tally, and retail must not restart before it.
  routes    the Saturn route harness pass (every position matched, zero
            respawns, zero late intervals, one ordinary handoff), the same
            tools without --host-only (--no-retail where the tool has it).
  art       tools/test_zone_art_emulator.py R<round><act><era> per window
            (SCD_CLUT_CYCLE=1 for TT/QQ like tools/run-{tt,qq}-art-matrix.sh);
            PPZ (no R1 zone-art pack) tools/test_ppz_art_emulator.py R1<act><era>:
            each object atlas frame drawn with four flips, pixels as drawn.
  travel    tools/test_<zone>_travel.py (shared run_travel driver), stored
            tests/routes/<zone>/travel/<zone><act><era><to>.txt scripts (pairs
            AB, AD, BA, CA, DA per act).
  campaign  CC prepare_cc_campaign_checkpoint.py, test_cc_campaign_act3.py,
            test_cc3_route.py --continue, test_cc_campaign_generator.py
            --milestone continue; PPZ/TT/QQ/WW/SS/MM test_<zone>_campaign.py --act 1/2/3
            (MM3 ends the game: completed save, ALL ZONES CLEAR, title, cold Continue).

MM (Metallic Madness) retail/routes windows read tests/routes/mm/mm<act><era>.txt; a
window without a stored route is ``missing`` (a failure) until the route lane stores it.
MM art adds the Act 3 fight and Amy banks (MM3C-fight, MM3C-ending).

Special stages (V0.078): ``--zones sp --gates special`` runs every case in
zone_release_evidence.SPECIAL_CASES (stages 1-8 win/timeout/hazard, big-ring
entry per zone, save progression, both endings, the seven-stone return) with
the command tests/special/gate-cases.json gives it. ``{out}`` in a command is
the case's own folder under the run; the case's report (default
``{out}/report.json``) must say passed on this BIN. A case with no command is
``missing`` and names the lane that owns it. The game-zone gates make no
windows for ``sp``, and ``special`` makes none for a game zone.

A gate with no tool for a zone is ``missing`` and counts as a failure. Windows
that share a tool's build directory (build/<zone><act>/controller, the art
harness, the save-chained campaigns) run serially;
independent groups run concurrently up to --jobs.

Writes build/zone-gates/<YYYYmmdd-HHMMSS>/report.json (BIN sha256, git HEAD,
dirty flag, per zone/gate/window status, counts, evidence) and prints a
summary table. Last line: ``PASS: <report>`` or ``FAIL: <n> gates; <report>``.
Emulator results only; never hardware acceptance.
"""
import argparse
import concurrent.futures as cf
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
from qa_limits import atomic_json, cooldown, cooldown_seconds, worker_limit, emulator_limit, _sync_file
# Batch job: yield the CPU to foreground work (SCD_NICE=0 disables).
try:
    os.nice(int(os.environ.get('SCD_NICE', '20')))
except PermissionError:  # already at the lowest priority
    pass

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / 'dist/sonic-cd-saturn-prototype.bin'
from zone_release_evidence import (ZONES, SPECIAL, SPECIAL_CASES, SPECIAL_GATE, matrix_command,
                                   release_special, release_zones)
GATES = ('retail', 'routes', 'art', 'travel', 'campaign', SPECIAL_GATE)
SPECIAL_REGISTRY = ROOT/'tests/special/gate-cases.json'
ACT_ERAS = [(1, e) for e in 'ABCD'] + [(2, e) for e in 'ABCD'] + [(3, e) for e in 'CD']
ROUND = {'ppz': 1, 'cc': 3, 'tt': 4, 'qq': 5, 'ww': 6, 'ss': 7, 'mm': 8}


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


class Run:
    """One tool invocation, shared by every window that reads it."""
    def __init__(self, key, cmds, group, report=None, env=None, out=None):
        self.key, self.cmds, self.group = key, cmds, group
        self.report, self.env, self.out = report, env or {}, out
        self.done = threading.Event()
        self.result = None


class Window:
    def __init__(self, zone, gate, name, run=None, parse=None, missing=None):
        self.zone, self.gate, self.name = zone, gate, name
        self.run, self.parse, self.missing = run, parse, missing


# ---- parsers: (run result, tool report dict or None) -> (status, counts, note)

def parse_retail(res, rep):
    parity = (rep or {}).get('retail_parity')
    if not parity:
        return 'fail', {}, 'no retail_parity in report (tool exit %s)' % res['returncode']
    counts = {k: parity.get(k) for k in ('compared', 'contiguous', 'matched', 'contiguous_all_fields')}
    div = parity.get('first_field_divergence') or parity.get('first_divergence')
    note = f"first divergence seq {div['sequence']} {div['fields']}" if div else ''
    ok = (bool(parity.get('compared'))
          and parity.get('contiguous') == parity['compared']
          and parity.get('contiguous_all_fields') == parity['compared']
          and not div)
    if not ok and not note:
        note = 'incomplete nine-field retail match'
    # A route that dies or never reaches the tally shortens the compared window;
    # that is not a whole-window match.
    broken = res['returncode'] != 0 or any(
        s in line for line in res['tail'] for s in ('Route failed', 'Route incomplete', 'no tally'))
    if ok and broken:
        ok, note = False, 'host route did not finish: ' + (res['tail'][-1:] or [''])[0][:200]
    # The retail-aligned native replay (lag, unlock and V-INT phase fed from
    # retail) must reach the tally too, and retail must not die and restart
    # before it: either one ends the compared window early.
    end = parity.get('native_end') or ''
    tally = re.match(r'Tally complete: sequence=(\d+)', end)
    restart = parity.get('retail_restart')
    if ok and not tally:
        ok, note = False, 'aligned replay did not finish: ' + end[:200]
    elif ok and 'retail_restart' not in parity:
        ok, note = False, 'retail_parity has no retail_restart field (stale report)'
    elif ok and restart is not None and restart <= int(tally[1]):
        ok, note = False, f'retail restarts at frame {restart}, before the aligned tally at {tally[1]}'
    # Retail rows stop when retail leaves the level (its own tally, a time warp,
    # or a death that has not restarted yet); native s is retail row s + 1.
    elif ok and parity.get('retail_updates') is not None and parity['retail_updates'] <= int(tally[1]) + 1:
        ok, note = False, f'retail rows end at {parity["retail_updates"]}, before the aligned tally at {tally[1]}'
    return ('pass' if ok else 'fail'), counts, note


def parse_routes(res, rep):
    rep = rep or {}
    counts = dict(positions=rep.get('matched_positions', rep.get('positions')), observations=rep.get('observations'),
                  respawns=rep.get('respawns'), late=len(rep.get('late_gameplay_intervals') or []),
                  handoff=rep.get('handoff_sequence'))
    ok = res['returncode'] == 0 and rep.get('passed') is True and rep.get('status') == 'passed'
    note = '' if ok else (rep.get('error') or (res['tail'][-1:] or [''])[0])[:300]
    return ('pass' if ok else 'fail'), counts, note


def parse_generic(res, rep):
    """Exit status plus the tool's report.json ``passed`` when it writes one."""
    counts = {k: v for k, v in (rep or {}).items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    ok = res['returncode'] == 0 and (rep is None or rep.get('passed', True) is not False)
    note = res['pass_line'] or ('' if ok else ((rep or {}).get('error') or (res['tail'][-1:] or [''])[0])[:300])
    return ('pass' if ok else 'fail'), counts, note


# ---- matrix

def build_matrix(zones, gates, run_dir):
    runs, windows = {}, []

    def run(key, cmds, group, **kw):
        if key not in runs:
            runs[key] = Run(key, cmds, group, **kw)
        return runs[key]

    registry = json.loads(SPECIAL_REGISTRY.read_text()) if SPECIAL_REGISTRY.is_file() else {}
    for zone in zones:
        for gate in gates:
            if (zone == SPECIAL) != (gate == SPECIAL_GATE):
                continue
            if gate == SPECIAL_GATE:
                for name in SPECIAL_CASES:
                    case = registry.get(name) or {}
                    if not case.get('command'):
                        windows.append(Window(zone, gate, name, missing=f"pending: {case.get('lane', 'unassigned')}"))
                        continue
                    out = run_dir/'special'/name
                    expand = lambda argv: [a.replace('{out}', str(out)) for a in argv]
                    # 'before': prerequisite commands run first in the same serial run;
                    # 'group': share a serial group with gates that write the same build dirs.
                    cmds = [*map(expand, case.get('before', [])), expand(case['command'])]
                    report = Path(case.get('report', '{out}/report.json').replace('{out}', str(out)))
                    # 'exclusive': the case shares many gates' folders (every route window);
                    # it runs alone after every other group.
                    r = run(('special', name), cmds, '<exclusive>' if case.get('exclusive') else case.get('group', 'special'),
                            report=report if report.is_absolute() else ROOT/report, out=out)
                    windows.append(Window(zone, gate, name, r, parse_generic))
                continue
            if gate in ('retail', 'routes'):
                for act, era in ACT_ERAS:
                    name = f'{zone.upper()}{act}{era}'
                    if zone == 'tt':
                        tool, base, extra, host_only = 'test_tt_route.py', f'build/tt{act}/controller', ['--act', str(act)], True
                    elif zone == 'qq':
                        tool, base, extra, host_only = 'test_qq_route.py', f'build/qq{act}/controller', ['--act', str(act)], True
                    elif zone == 'ww':
                        tool, base, extra, host_only = 'test_qq_route.py', f'build/ww{act}/controller', ['--ww', '--act', str(act)], True
                    elif zone == 'ss':
                        tool, base, extra, host_only = 'test_qq_route.py', f'build/ss{act}/controller', ['--ss', '--act', str(act)], True
                    elif zone == 'mm':
                        if not (ROOT/f'tests/routes/mm/mm{act}{era}.txt').is_file():
                            windows.append(Window(zone, gate, name, missing=f'no stored route tests/routes/mm/mm{act}{era}.txt'))
                            continue
                        tool, base, extra, host_only = 'test_qq_route.py', f'build/mm{act}/controller', ['--mm', '--act', str(act)], True
                    elif zone == 'ppz':
                        tool, base, extra, host_only = 'test_ppz_route.py', f'build/ppz{act}/controller', ['--act', str(act)], True
                    elif act < 3:
                        tool, base, extra, host_only = 'test_cc2_route.py', f'build/cc{act}/controller', ['--act', str(act)], True
                    else:
                        tool, base, extra, host_only = 'test_cc3_route.py', 'build/cc3/controller', [], True
                    cmd = ['python3', f'tools/{tool}', *extra, '--era', era]
                    if gate == 'retail' and host_only:
                        cmd.append('--host-only')
                    elif gate == 'routes' and host_only:
                        cmd.append('--no-retail')
                    r = run(tuple(cmd), [cmd], f'{tool}:{base}', report=ROOT/base/era/'report.json')
                    windows.append(Window(zone, gate, name, r, parse_retail if gate == 'retail' else parse_routes))
            elif gate == 'art':
                if zone == 'ppz':
                    # No R1 zone-art pack: every object atlas frame drawn per program.
                    for act, era in ACT_ERAS:
                        prog = f'R1{act}{era}'
                        cmd = ['python3', 'tools/test_ppz_art_emulator.py', prog]
                        r = run(('art', prog), [cmd], 'art', report=ROOT/'build/ppz-art-qa'/prog/'report.json')
                        windows.append(Window(zone, gate, f'PPZ{act}{era}', r, parse_generic))
                    continue
                banks = [('-fight', 3, 'C'), ('-ending', 3, 'C')] if zone == 'mm' else []
                for suffix, act, era in [('', a, e) for a, e in ACT_ERAS] + banks:
                    prog = f'R{ROUND[zone]}{act}{era}{suffix}'
                    env = {'SCD_CLUT_CYCLE': '1'} if zone in ('tt', 'qq') else {}
                    cmd = ['python3', 'tools/test_zone_art_emulator.py', prog]
                    r = run(('art', prog), [cmd], 'art', report=ROOT/'build/zone-art-qa'/prog/'report.json', env=env)
                    windows.append(Window(zone, gate, f'{zone.upper()}{act}{era}{suffix}', r, parse_generic))
            elif gate == 'travel':
                # Stored natural-travel scripts, the five level-select pairs per act.
                # (tools/ppz_journey.py's natural-*.pads journeys are exploratory by
                # its own docstring, and their multi-card recordings predate the
                # PLC 2 unlock; tools/route_unlock_lead.py EXCLUDED.)
                for act in (1, 2):
                    for pair in ('AB', 'AD', 'BA', 'CA', 'DA'):
                        name = f'{zone.upper()}{act}{pair}'
                        out = run_dir/'travel'/name
                        cmd = ['python3', f'tools/test_{zone}_travel.py', '--output', str(out), '--act', str(act),
                               '--era', pair[0], '--to', pair[1],
                               '--script', f'tests/routes/{zone}/travel/{zone}{act}{pair}.txt']
                        r = run(('travel', name), [cmd], f'travel:{name}', report=out/'report.json', out=out)
                        windows.append(Window(zone, gate, name, r, parse_generic))
            elif gate == 'campaign':
                if zone == 'cc':
                    checkpoint = ROOT/'build/cc1/generator/campaign-checkpoint-report.json'
                    checkpoint_cmd = ['python3', 'tools/prepare_cc_campaign_checkpoint.py']
                    act3_cmd = ['python3', 'tools/test_cc_campaign_act3.py']
                    if 'ppz' in zones:
                        checkpoint_cmd += ['--ppz3-report', str(run_dir/'campaign/PPZ3/report.json')]
                        act3_cmd += ['--checkpoint-report', str(checkpoint)]
                    steps = [('checkpoint', checkpoint_cmd, checkpoint),
                             ('act3-good-bad', act3_cmd, ROOT/'build/cc2/campaign/report.json'),
                             ('cc3-continue-C', ['python3', 'tools/test_cc3_route.py', '--continue', '--era', 'C'],
                              ROOT/'build/cc3/controller/continue/C/report.json'),
                             ('cc3-continue-D', ['python3', 'tools/test_cc3_route.py', '--continue', '--era', 'D'],
                              ROOT/'build/cc3/controller/continue/D/report.json'),
                             ('generator-continue', ['python3', 'tools/test_cc_campaign_generator.py', '--milestone', 'continue'],
                              ROOT/'build/cc1/generator/campaign-generated/report.json')]
                    for name, cmd, rep in steps:
                        r = run(('campaign', 'cc', name), [cmd], 'campaign', report=rep)
                        windows.append(Window(zone, gate, name, r, parse_routes if name.startswith('cc3-continue') else parse_generic))
                else:
                    # PPZ from NEW GAME; TT from CC3, QQ from TT3, WW from QQ3, SS from WW3, MM from SS3.
                    # Keep zone order so each act uses the preceding earned save.
                    for act in (1, 2, 3):
                        out = run_dir/'campaign'/f'{zone.upper()}{act}'
                        cmd = ['python3', f'tools/test_{zone}_campaign.py', '--act', str(act), '--output', str(out)]
                        r = run(('campaign', zone, act), [cmd], 'campaign', report=out/'report.json', out=out)
                        windows.append(Window(zone, gate, f'{zone.upper()}{act}', r, parse_generic))
    return runs, windows


# ---- execution

def execute(run, run_dir, timeout, print_lock, cooling=None, input_check=None):
    slug = '-'.join(str(k) for k in run.key if not str(k).startswith('python3'))
    slug = slug.replace('/', '_').replace('tools_', '').replace('.py', '').replace(' ', '')[:120]
    log_path = run_dir/'logs'/f'{slug}.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if run.out:  # the tool makes its own output folder; its parent must exist
        run.out.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()
    rc, pass_line = 0, ''
    env = dict(os.environ, **run.env)
    with log_path.open('w') as log:
        for cmd in run.cmds:
            if cooling is not None:
                cooldown(cooling['last_finished'],seconds=cooling['seconds'])
            if input_check is not None:input_check()
            log.write('$ ' + ' '.join(cmd) + '\n'); log.flush()
            try:
                rc = subprocess.run(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=timeout).returncode
            except subprocess.TimeoutExpired:
                rc = 124
                log.write(f'zone-gates: timeout after {timeout}s\n')
            if input_check is not None:input_check()
            if cooling is not None:cooling['last_finished']=time.monotonic()
            if rc:
                break
        log.flush();_sync_file(log.fileno())
    lines = log_path.read_text(errors='replace').splitlines()
    pass_line = next((l for l in reversed(lines) if l.startswith('PASS')), '')
    rep, evidence = None, str(log_path.relative_to(ROOT))
    if run.report and run.report.exists() and run.report.stat().st_mtime >= start - 1:
        try:
            rep = json.loads(run.report.read_text())
        except ValueError:
            rep = None
        copy = run_dir/'evidence'/f'{slug}.report.json'
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(run.report, copy)
        evidence = str(copy.relative_to(ROOT))
    tool_report = None
    if rep is not None:
        tool_report = str(run.report.relative_to(ROOT)) if run.report.is_relative_to(ROOT) else str(run.report)
    run.result = dict(returncode=rc, seconds=round(time.time() - start, 1), log=str(log_path.relative_to(ROOT)),
                      evidence=evidence, tool_report=tool_report, pass_line=pass_line, tail=lines[-3:], report=rep)
    with print_lock:
        print(f'  [{run.result["seconds"]:7.1f}s] rc={rc} {" ".join(run.cmds[-1][1:])[:110]}', flush=True)
    run.done.set()


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    scope = matrix_command(release_zones(ROOT), release_special(ROOT))
    parser.add_argument('--zones', default=scope[3], help='comma list of ' + ','.join((*ZONES, SPECIAL)))
    parser.add_argument('--gates', default=scope[5], help='comma list of ' + ','.join(GATES))
    parser.add_argument('--jobs', type=int, default=4, help='concurrent tool groups (default 4)')
    parser.add_argument('--list', action='store_true', help='print the matrix and exit (runs nothing)')
    parser.add_argument('--resume', type=Path, help='continue a matrix, retaining verified completed tool runs')
    parser.add_argument('--resume-source-report', type=Path, help='source QA report for a legacy matrix without an input checkpoint')
    parser.add_argument('--migration', type=Path, help='explicit hash-bound initial orchestration upgrade')
    parser.add_argument('--retail-only', action='store_true', help='same as --gates retail')
    parser.add_argument('--timeout', type=int, default=6 * 3600, help='per tool command, seconds')
    parser.add_argument('--windows', help='comma list of window names to run (e.g. TT1B,TT2D,TT1); default all. '
                                          'A campaign act still needs the previous act\'s save in its run directory')
    args = parser.parse_args()
    try:
        args.jobs=emulator_limit(worker_limit(args.jobs))
        pause_seconds=cooldown_seconds()
    except ValueError as error:
        parser.error(str(error))
    # A cooling interval is global, so cooled batches cannot overlap.
    if pause_seconds:args.jobs=1
    zones = [z.strip().lower() for z in args.zones.split(',') if z.strip()]
    gates = ['retail'] if args.retail_only else [g.strip().lower() for g in args.gates.split(',') if g.strip()]
    for value, allowed in ((zones, (*ZONES, SPECIAL)), (gates, GATES)):
        bad = [v for v in value if v not in allowed]
        if bad:
            parser.error(f'unknown {bad}; choose from {",".join(allowed)}')
    zones = [z for z in (*ZONES, SPECIAL) if z in zones]
    gates = [g for g in GATES if g in gates]
    # Stored routes must carry the PLC 2 title-card unlock lead (fail fast).
    if not args.list:
        lead = subprocess.run([sys.executable, 'tools/route_unlock_lead.py', '--check'], cwd=ROOT, capture_output=True, text=True)
        if lead.returncode:
            sys.exit(lead.stdout + lead.stderr)
    stamp =datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    run_dir = ROOT/'build/zone-gates'/stamp
    prior = None
    resume_path = getattr(args, 'resume', None)
    migration_path = getattr(args, 'migration', None)
    migration = json.loads(migration_path.read_text()) if migration_path else None
    if resume_path:
        resume_path = resume_path.resolve()
        if not resume_path.is_relative_to((ROOT/'build/zone-gates').resolve()) or resume_path.name != 'report.json':
            parser.error('resume report must be under build/zone-gates')
        prior = json.loads(resume_path.read_text())
        if prior.get('zones') != zones or prior.get('gates') != gates or args.windows:
            parser.error('resume must retain the complete original matrix scope')
        run_dir = resume_path.parent
    runs, windows = build_matrix(zones, gates, run_dir)
    if args.windows:
        keep = {n.strip().upper() for n in args.windows.split(',') if n.strip()}
        windows = [w for w in windows if w.name.upper() in keep]
        used = {w.run.key for w in windows if w.run}
        runs = {k: r for k, r in runs.items() if k in used}

    if args.list:
        for w in windows:
            what = 'MISSING: ' + w.missing if w.missing else ' && '.join(' '.join(c) for c in w.run.cmds)
            env = ' '.join(f'{k}={v}' for k, v in (w.run.env if w.run else {}).items())
            print(f'{w.zone:4} {w.gate:9} {w.name:20} {(env + " ") if env else ""}{what}')
        print(f'{len(windows)} windows, {len(runs)} tool runs, {len({r.group for r in runs.values()})} serial groups')
        return

    (ROOT/'build').mkdir(exist_ok=True)
    (ROOT/'build/zone-gates').mkdir(exist_ok=True)
    if not prior:
        run_dir.mkdir(exist_ok=False)
    report_path = run_dir/'report.json'
    bin_sha = sha256(BIN) if BIN.exists() else None
    import qa_resume
    from power_guard import inputs as matrix_inputs
    checkpoint = qa_resume.context(ROOT, matrix_inputs(), BIN)
    bios = qa_resume.bios_inputs(ROOT)
    execution_environment = qa_resume.execution_environment()
    references = qa_resume.preserve_reference_inputs(ROOT,qa_resume.reference_inputs(ROOT))
    if not args.windows:
        qa_resume.verify_canonical_environment(execution_environment)
    migration_record = (dict(path=str(migration_path.resolve()), sha256=qa_resume.digest(migration_path))
                        if migration_path else None)
    if prior:
        if not migration and prior.get('orchestration_migration'):
            migration_record = prior['orchestration_migration']
            saved = qa_resume.local_path(ROOT, migration_record['path'])
            if qa_resume.digest(saved) != migration_record['sha256']:
                parser.error('saved orchestration migration changed')
            migration = json.loads(saved.read_text())
        if prior.get('bin_sha256') != bin_sha:
            parser.error('matrix BIN changed; completed windows cannot be reused')
        source_path = getattr(args, 'resume_source_report', None)
        valid_origin = (qa_resume.compatible(prior, checkpoint, migration, resume_path)
                        if prior.get('checkpoint_context') else
                        qa_resume.legacy_matrix_compatible(resume_path, source_path, checkpoint, migration))
        if not valid_origin:
            parser.error('matrix input/runtime/build checkpoint differs')
        history = run_dir/'resume-history'
        history.mkdir(exist_ok=True)
        history_path = history/(datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.json')
        with history_path.open('xb') as stream:
            stream.write(resume_path.read_bytes())
            stream.flush()
            _sync_file(stream.fileno())
    report = dict(status='pending', bin=str(BIN.relative_to(ROOT)), bin_sha256=bin_sha, git_head=git('rev-parse', 'HEAD'),
                  git_dirty=bool(git('status', '--porcelain', '--untracked-files=no')),
                  started=stamp, zones=zones, gates=gates, jobs=args.jobs, hardware_tested=False,
                  cooldown_seconds=pause_seconds,
                  limits='Emulator and native-host evidence only; not hardware acceptance.', results={})
    report.update(source_sha256=checkpoint['source_sha256'], checkpoint_context=checkpoint,
                   bios_inputs=bios,
                   execution_environment=execution_environment, reference_inputs=references,
                  reused_windows=0, resumed_from=str(history_path.relative_to(ROOT)) if prior else None,
                  resumed_from_sha256=sha256(history_path) if prior else None,
                  orchestration_migration=migration_record)
    report['consumer_input_protocol']=qa_resume.CONSUMER_PROTOCOL
    qa_resume.publish_consumer_context(ROOT,checkpoint)
    cache_candidates = {}
    for w in windows:
        entry = dict(status='missing', note=w.missing) if w.missing else dict(status='pending')
        if prior and w.run:
            old = prior.get('results', {}).get(w.zone, {}).get(w.gate, {}).get(w.name, {})
            if qa_resume.cached_window(ROOT, run_dir, w, old, bin_sha, migration, current_references=references):
                cache_candidates[(w.zone,w.gate,w.name)] = dict(old)
        report['results'].setdefault(w.zone, {}).setdefault(w.gate, {})[w.name] = entry
    lock, print_lock = threading.Lock(), threading.Lock()

    def save():
        with lock:
            atomic_json(report_path,report)
    save()

    def resolve(w):
        res = w.run.result
        status, counts, note = w.parse(res, res['report'])
        child = res['report']
        if child is None:
            status, note = 'fail', 'missing fresh child report'
        elif w.gate != 'retail' and child.get('disc_sha256') != bin_sha:
            status, note = 'fail', 'child report does not match matrix BIN'
        entry = dict(status=status, counts=counts, evidence=res['evidence'], log=res['log'],
                     bios_inputs=bios,
                     execution_environment=execution_environment, reference_inputs=references,
                     returncode=res['returncode'], seconds=res['seconds'],
                     evidence_sha256=sha256(ROOT/res['evidence']), log_sha256=sha256(ROOT/res['log']))
        if hasattr(w.run,'consumer_observation'):
            observation=w.run.consumer_observation[(w.zone,w.gate,w.name)]
            entry['consumer_inputs']=qa_resume.preserve_consumer_inputs(ROOT,observation)
            entry['input_identity_complete']=observation['complete']
            if not qa_resume.consumer_evidence_matches(ROOT,entry,observation,child):
                note='consumer/source-capture evidence binding differs'
                entry.update(status='fail',note=note)
        if res['tool_report']:
            entry['tool_report'] = res['tool_report']
        if note:
            entry['note'] = note
        with lock:
            report['results'][w.zone][w.gate][w.name] = entry
        save()

    groups = {}
    for r in runs.values():
        groups.setdefault(r.group, []).append(r)
    by_run = {}
    for w in windows:
        if w.run:
            by_run.setdefault(w.run.key, []).append(w)

    cooling=dict(last_finished=time.monotonic(),seconds=pause_seconds) if pause_seconds else None

    def run_group(members):
        for r in members:
            executed=False
            try:
                if cooling is not None:
                    cooldown(cooling['last_finished'],seconds=cooling['seconds'])
                qa_resume.verify_execution_inputs(ROOT,bios,execution_environment,references)
                accepted={}
                for w in by_run[r.key]:
                    key=(w.zone,w.gate,w.name)
                    old=cache_candidates.get(key)
                    observed=(qa_resume.consume_cached_window(ROOT,run_dir,w,old,bin_sha,
                        checkpoint,migration) if old is not None else None)
                    if observed is not None and qa_resume.campaign_cache_matches(ROOT,w,old,report['results']):
                        accepted[key]=(old,observed)
                reusable = len(accepted)==len(by_run[r.key])
                if reusable:
                    with lock:
                        for key,(old,observed) in accepted.items():
                            report['results'][key[0]][key[1]][key[2]]=dict(old,
                                reused_from=str(history_path.relative_to(ROOT)),
                                consumer_inputs=qa_resume.preserve_consumer_inputs(ROOT,observed),
                                input_identity_complete=True,
                                consumer_inputs_observation='verified_after_cooling_at_run_group')
                        report['reused_windows'] += len(by_run[r.key])
                    save()
                    print('REUSE zone run: '+str(r.key),flush=True)
                    continue
                # Archive an interrupted private output with a metadata rename.
                # Completed parent campaign saves remain at their original paths.
                if prior and r.out and r.out.exists():
                    archived = r.out.with_name(r.out.name+'.interrupted-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
                    r.out.rename(archived)
                if prior:
                    artifacts = set()
                    for w in by_run[r.key]:
                        old = prior.get('results', {}).get(w.zone, {}).get(w.gate, {}).get(w.name, {})
                        for field in ('log', 'evidence'):
                            if old.get(field):
                                artifacts.add(qa_resume.local_path(ROOT, old[field]))
                    for artifact in artifacts:
                        if artifact.is_relative_to(run_dir) and artifact.exists():
                            artifact.rename(artifact.with_name(artifact.name+'.interrupted-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')))
                for w in by_run[r.key]:
                    report['results'][w.zone][w.gate][w.name] = dict(status='pending')
                save()
                # Finite source-defined missing-output preparations. These are
                # separate from the unchanged canonical matrix command arrays.
                specs=[qa_resume.consumer_spec(ROOT,r.cmds,window=w) for w in by_run[r.key]]
                requested=[]
                allowed=(['python3','tools/test_cc_palette.py'],
                         ['python3','tools/special_route.py'],
                         ['python3','tools/special_route.py','1','2','win-route-ta'],
                         *(qa_resume.fixed_producer_command(p) for p in qa_resume._FIXED_PRODUCERS))
                for command in qa_resume.fixed_setup_commands(ROOT,checkpoint,r.cmds):
                    if command not in requested:requested.append(command)
                for spec in specs:
                    for command in spec['setup']:
                        if command not in allowed:
                            raise ValueError('Unknown consumer setup command')
                        if command not in requested:requested.append(command)
                if any(spec['key'].get('palette_producer') for spec in specs):
                    try:
                        for spec in specs:
                            if spec['key'].get('palette_producer'):
                                qa_resume.palette_producer_join(ROOT,checkpoint,spec['key']['art_program'][3])
                    except (OSError,ValueError,TypeError,KeyError,AssertionError):
                        if ['python3','tools/test_cc_palette.py'] not in requested:
                            requested.append(['python3','tools/test_cc_palette.py'])
                for command in requested:
                    if cooling is not None:
                        cooldown(cooling['last_finished'],seconds=cooling['seconds'])
                    qa_resume.verify_execution_inputs(ROOT,bios,execution_environment,references)
                    retained=qa_resume.preserve_fixed_producer_outputs(ROOT,command)
                    preparation=qa_resume.consumer_inputs(ROOT,qa_resume.consumer_spec(ROOT,[command]),context=checkpoint)
                    if (command==['python3','tools/test_cc_palette.py'] or any(d['command']==command for d in qa_resume._FIXED_PRODUCERS.values())) and not preparation['complete']:
                        raise ValueError('Palette input preparation is incomplete: '+str(preparation['unsupported']))
                    step=dict(command=command,status='running',counts_as_qa=False,retained_outputs=retained)
                    report.setdefault('input_preparations',[]).append(step);save()
                    setup_log=run_dir/'logs'/('input-preparation-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.log')
                    setup_log.parent.mkdir(exist_ok=True)
                    try:
                        with setup_log.open('x') as stream:
                            result=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=args.timeout,
                                env=qa_resume.consumer_environment(checkpoint,command))
                            stream.flush();_sync_file(stream.fileno())
                        step['exit_code']=result.returncode
                        qa_resume.verify_consumer_inputs(ROOT,preparation)
                        if result.returncode==0:
                            step['producer_outputs']=qa_resume.producer_outputs(ROOT,command,context=checkpoint,consumer=preparation,
                                log=dict(path=str(setup_log.relative_to(ROOT)),sha256=sha256(setup_log)),exit_code=result.returncode)
                    except BaseException as error:
                        step.update(status='interrupted' if isinstance(error,KeyboardInterrupt) else 'failed',error=repr(error))
                        if setup_log.exists():
                            step.update(log=str(setup_log.relative_to(ROOT)),log_sha256=sha256(setup_log))
                        save()
                        raise
                    step.update(status='passed' if result.returncode==0 else 'failed',exit_code=result.returncode,
                                log=str(setup_log.relative_to(ROOT)),log_sha256=sha256(setup_log))
                    if cooling is not None:cooling['last_finished']=time.monotonic()
                    save()
                    if result.returncode:raise ValueError('Consumer preparation failed')
                if requested:
                    if any(qa_resume.consumer_spec(ROOT,r.cmds,window=w)['setup'] for w in by_run[r.key]):
                        raise ValueError('Consumer preparation did not produce required inputs')
                r.consumer_observation={(w.zone,w.gate,w.name):qa_resume.consumer_inputs(ROOT,
                    qa_resume.consumer_spec(ROOT,r.cmds,window=w),context=checkpoint) for w in by_run[r.key]}
                if any([reason for reason in observation['unsupported']
                        if reason!=qa_resume._ALTERNATE_SOURCE_LIMIT] for observation in r.consumer_observation.values()):
                    raise ValueError('Known matrix consumer input identity incomplete: '+str(
                        [observation['unsupported'] for observation in r.consumer_observation.values() if not observation['complete']]))
                def check_run_inputs():
                    qa_resume.verify_execution_inputs(ROOT,bios,execution_environment,references)
                    for observed in r.consumer_observation.values():
                        qa_resume.verify_consumer_inputs(ROOT,observed)
                executed=True
                execute(r, run_dir, args.timeout, print_lock, cooling,
                        input_check=check_run_inputs)
                for w in by_run[r.key]:
                    resolve(w)
            except Exception as error:
                with lock:
                    for w in by_run[r.key]:
                        report['results'][w.zone][w.gate][w.name] = dict(
                            status='fail', note=f'{type(error).__name__}: {error}')
                save()
            finally:
                if cooling is not None and executed:cooling['last_finished']=time.monotonic()

    t0 = time.time()
    print(f'zone-gates: {len(windows)} windows, {len(runs)} runs, {len(groups)} groups, jobs {args.jobs}; {run_dir.relative_to(ROOT)}', flush=True)
    interrupted = False
    with cf.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = [pool.submit(run_group, m) for g, m in groups.items() if g != '<exclusive>']
        try:
            for f in cf.as_completed(futures):
                f.result()
            if '<exclusive>' in groups:
                run_group(groups['<exclusive>'])
        except KeyboardInterrupt:
            interrupted = True
            for f in futures:
                f.cancel()
    for w in windows:
        entry = report['results'][w.zone][w.gate][w.name]
        if entry['status'] == 'pending':
            entry.update(status='fail', note='interrupted' if interrupted else 'not run')
    end_sha = sha256(BIN) if BIN.exists() else None
    changed_inputs = matrix_inputs() != checkpoint['source_sha256']
    try:
        qa_resume.verify_execution_inputs(ROOT,bios,execution_environment,references)
        qa_resume.verify_stable_consumer_inputs(ROOT,[entry['consumer_inputs']
            for area in report['results'].values() for entries in area.values()
            for entry in entries.values() if entry.get('consumer_inputs')])
        changed_bios = False
    except Exception as error:
        changed_bios = True
        report['error'] = str(error)
    report['bin_sha256_end'] = end_sha
    report['seconds'] = round(time.time() - t0, 1)

    failed_gates = 0
    rows = []
    for zone in zones:
        for gate in gates:
            entries = report['results'].get(zone, {}).get(gate)
            if not entries:  # --windows left nothing in this gate
                continue
            n = len(entries)
            passed = sum(e['status'] == 'pass' for e in entries.values())
            missing = all(e['status'] == 'missing' for e in entries.values())
            ok = not missing and passed == n and end_sha == bin_sha and not changed_inputs and not changed_bios
            failed_gates += not ok
            bad = [k for k, e in entries.items() if e['status'] != 'pass' and not missing]
            rows.append((zone, gate, 'missing' if missing else f'{passed}/{n}', 'PASS' if ok else 'FAIL', ','.join(bad)))
    report['failed_gates'] = failed_gates
    report['cache_identity_incomplete_windows']=[[zone,gate,name]
        for zone,area in report['results'].items() for gate,entries in area.items()
        for name,entry in entries.items() if entry.get('input_identity_complete') is not True]
    report['status'] = 'interrupted' if interrupted else 'passed' if failed_gates == 0 else 'failed'
    report['passed'] = failed_gates == 0 and not interrupted
    if end_sha != bin_sha:
        report['error'] = 'BIN changed during the run'
    if changed_inputs:
        report['error'] = 'Source/tool inputs changed during the run'
    save()

    print(f'\nBIN {bin_sha} HEAD {report["git_head"][:12]}{" dirty" if report["git_dirty"] else ""} in {report["seconds"]}s')
    print(f'{"zone":5} {"gate":9} {"result":8} {"":5} not passing')
    for zone, gate, result, verdict, bad in rows:
        print(f'{zone:5} {gate:9} {result:8} {verdict:5} {bad}')
    if 'retail' in gates:
        for zone in zones:
            for name, e in report['results'].get(zone, {}).get('retail', {}).items():
                c = e.get('counts') or {}
                if c:
                    print(f'  {name}: {c.get("contiguous")}/{c.get("compared")} contiguous{"  " + e["note"] if e.get("note") else ""}')
    if report.get('error'):
        print('ERROR: ' + report['error'])
    rel = report_path.relative_to(ROOT)
    print(f'PASS: {rel}' if report['passed'] else f'FAIL: {failed_gates} gates; {rel}')
    sys.exit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
