#!/usr/bin/env python3
"""Replay one new mutated Act 1 prefix per zone and preset on a frozen BIN.

This is a 14-case host/Saturn comparison, not lifecycle or hardware acceptance.
--case ppz1A-0 validates the first case. --resume RUN_DIR runs unfinished cases
against the same snapshots. Each invocation runs one emulator at a time.
"""
import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
ZONES = ('ppz', 'cc', 'tt', 'qq', 'ww', 'ss', 'mm')
REQUIRED = [f'{z}1A-{flags}' for z in ZONES for flags in (0, 31)]
SEED = 8107


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def prefix_rows(path, count):
    rows = []
    with path.open() as stream:
        for line in stream:
            row = [int(v) for v in line.split()]
            if len(row) != 4 or row[0] != len(rows) + 2:
                raise ValueError(f'invalid host trace row {len(rows)}')
            if not (0 <= row[2] < 16384 and -1024 <= row[3] <= 2304):
                raise ValueError('host position outside emulator input range')
            rows.append(row)
            if len(rows) == count:
                return rows
    raise ValueError(f'host prefix too short: {len(rows)}/{count}')


def verify_output(log, expected, zone, flags, shots):
    rows = [[int(v) for v in line.split(': ', 1)[1].split()]
            for line in log.splitlines() if line.startswith('CC route: ')]
    if len(rows) != len(expected) or any(len(r) != 12 for r in rows):
        raise ValueError(f'observation count or columns: {len(rows)}/{len(expected)}')
    for row, want in zip(rows, expected):
        y = row[3] - (1 << 32) if row[3] >= 1 << 31 else row[3]
        if [row[0], row[8], row[2], y] != want:
            raise ValueError(f'position/input mismatch at {want[0]}: {row} vs {want}')
        if row[9:] != [zone, 0, 0]:
            raise ValueError(f'unexpected stage transition at {row[0]}')
        if row[6]:
            raise ValueError(f'unexpected respawn at {row[0]}')
    if any(b[1] - a[1] != 1 for a, b in zip(rows, rows[1:])):
        raise ValueError('late or invalid gameplay observation interval')
    peeks = []
    for line in log.splitlines():
        if line.startswith('Route peek: '):
            parts = line.split(': ', 1)[1].split()
            if len(parts) != 3 or parts[2] != '|':
                raise ValueError('invalid preset peek')
            peeks.append([int(parts[0]), int(parts[1], 16)])
    if [p[0] for p in peeks] != shots:
        raise ValueError(f'missing preset observations: {peeks}')
    if any(value & 65535 != (flags << 8 | flags) for _, value in peeks):
        raise ValueError(f'incorrect active preset: {peeks}')
    endings = [line for line in log.splitlines() if line.startswith('CC route ended: ')]
    if len(endings) != 1 or f'updates={len(expected)} ' not in endings[0]:
        raise ValueError('route end not observed')
    return dict(matched_positions=len(rows), preset_peeks=peeks,
                late_intervals=0, respawns=0, stage_transitions=0)


def symbols(source, elf):
    text = subprocess.check_output([str(source / '.toolchain/bin/sh-elf-nm'), str(elf)], text=True)
    return {re.sub(r'\.lto_priv\.\d+$', '', fields[2]): fields[0]
            for line in text.splitlines() if len(fields := line.split()) == 3}


def snapshot(path, target, manifest):
    before = sha(path)
    shutil.copyfile(path, target)
    if sha(target) != before or sha(path) != before:
        raise ValueError(f'input changed during snapshot: {path}')
    manifest[str(target)] = before


def initialize(source, host_report_path, backup, count):
    if shutil.disk_usage(ROOT).free < 100 * 1024**3:
        raise ValueError('100 GiB free-space reserve unavailable')
    out = ROOT / 'build/qa-campaign-emulator' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    out.mkdir(parents=True)
    report = dict(status='pending', passed=False, coverage_complete=False, hardware_tested=False,
                  scope='14 mutated Act 1 prefixes; no death/arrival/resource acceptance',
                  source_root=str(source), updates=count, seed=SEED, required_cases=REQUIRED,
                  snapshots={}, cases={}, upstream_host_report=str(host_report_path))
    save(out / 'report.json', report)
    try:
        host_report = json.loads(host_report_path.read_text())
        if host_report.get('status') != 'passed' or host_report.get('changed_inputs'):
            raise ValueError('upstream host batch did not pass with stable inputs')
        # Bind gameplay and generated inputs to the host evidence. Tool-only
        # changes do not alter the game's state oracle.
        report['host_gameplay_inputs'] = {}
        for relative, expected in host_report['source_hashes'].items():
            if relative.startswith(('src/', 'assets/generated/', 'build/probe-source/')):
                if sha(source / relative) != expected:
                    raise ValueError(f'host gameplay input changed: {relative}')
                report['host_gameplay_inputs'][relative] = expected
        snapshot(host_report_path, out / 'host-report.json', report['snapshots'])
        snapshot(Path(__file__).resolve(), out / 'runner.py', report['snapshots'])
        snap = out / 'inputs'
        snap.mkdir()
        for relative in ('dist/sonic-cd-saturn-prototype.bin', 'dist/sonic-cd-saturn-prototype.cue',
                         'build/saturn/sonic-cd-saturn-prototype.elf',
                         '.deps/beetle-saturn/mednafen_saturn_libretro.dylib'):
            snapshot(source / relative, snap / Path(relative).name, report['snapshots'])
        if sha(snap / 'sonic-cd-saturn-prototype.bin') != host_report['bin_sha256']:
            raise ValueError('disc differs from host batch reference BIN')
        # Preserve exact BIOS bytes and avoid using main's shared core sidecars.
        bios = snap / 'bios'
        bios.mkdir()
        for name in ('saturn-bios.bin', 'mpr-17933.bin', 'bios_CD_U.bin'):
            path = source / 'assets/private' / name
            if path.is_file():
                snapshot(path, bios / name, report['snapshots'])
        spec = importlib.util.spec_from_file_location('campaign_settings_helpers', source / 'tools/test_cdpp_routes.py')
        helper = importlib.util.module_from_spec(spec)
        old_bytecode = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        try:
            spec.loader.exec_module(helper)
        finally:
            sys.dont_write_bytecode = old_bytecode
        snapshot(source / 'tools/test_cdpp_routes.py', snap / 'settings_helpers.py', report['snapshots'])
        image = backup.read_bytes()
        if len(image) != 32768 or helper.read_file(image, 'SCDSATURNCF') != helper.settings_record(1, 31):
            raise ValueError('backup does not contain the verified CD++ setting')
        snapshot(backup, snap / 'backup-31.bin', report['snapshots'])
        classic = bytearray(image)
        offsets, size = helper.file_spans(classic, 'SCDSATURNCF')
        record = helper.settings_record(0, 0)
        if size != len(record):
            raise ValueError('settings payload size changed')
        for offset, value in zip(offsets, record):
            classic[offset] = value
        (snap / 'backup-0.bin').write_bytes(classic)
        report['snapshots'][str(snap / 'backup-0.bin')] = sha(snap / 'backup-0.bin')
        syms = symbols(source, snap / 'sonic-cd-saturn-prototype.elf')
        report['symbols'] = {name: syms[name] for name in ('_scd_trace_mailbox', '_scd_audio_mailbox',
                                                         '_scd_world_mailbox', '_scd_save_mailbox',
                                                         '_scd_objects_overlay_fault')}
        # Compile the existing harness unchanged. Its relative source includes
        # resolve against the source checkout; retain every direct include.
        includes = ['tools/emulator_test.c', 'tools/act_pad_replay.h', 'tools/cc_pad_replay.h',
                    'tools/save_replay.h', 'tools/journey_replay.h', 'src/sonic_frames.c',
                    '.deps/beetle-saturn/libretro-common/include/libretro.h']
        report['harness_inputs'] = {relative: sha(source / relative) for relative in includes}
        report['compiler'] = subprocess.check_output(['clang', '--version'], text=True)
        command = ['nice', '-n', '20', 'clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                   '-I' + str(source / '.deps/beetle-saturn/libretro-common/include'),
                   str(source / 'tools/emulator_test.c'), '-o', str(out / 'emulator')]
        report['compile_command'] = command
        save(out / 'report.json', report)
        with (out / 'compile.log').open('w') as log:
            subprocess.run(command, stdout=log, stderr=log, check=True, timeout=120)
        report['snapshots'][str(out / 'emulator')] = sha(out / 'emulator')
        (snap / 'hosts').mkdir()
        for name in REQUIRED:
            case, flag_text = name.split('-')
            flags = int(flag_text)
            matches = [entry for entry in host_report['runs']
                       if entry['case'] == case and entry['flags'] == flags and entry['seed'] == SEED]
            if len(matches) != 1 or matches[0]['status'] != 'passed':
                raise ValueError(f'upstream case missing or failed: {name}')
            entry = matches[0]
            mutation = entry['mutation']
            if not mutation['changed_inputs_after_controller_delay'] or mutation['end'] + 2 >= count:
                raise ValueError(f'mutation not covered by selected prefix: {name}')
            folder = out / name
            folder.mkdir()
            upstream = host_report_path.parent / f'{case}-{flags}-{SEED}'
            if sha(upstream / 'pad.txt') != entry['pad_sha256']:
                raise ValueError(f'upstream pad changed: {name}')
            parity_trace = Path(entry['command'][-1] + '.reload-0')
            if sha(parity_trace) != entry['trace_hashes'][0]:
                raise ValueError(f'upstream trace changed: {name}')
            snapshot(upstream / 'pad.txt', folder / 'mutated-pad.txt', report['snapshots'])
            # Retail-parity rows sample the actor after water currents. The
            # Saturn controller mailbox publishes the player before currents.
            # Re-execute the exact same host/pad with TRACE disabled; never
            # mechanically project the 13-column retail trace into this oracle.
            kind = 'cc' if case.startswith(('ppz', 'cc')) else case[:-2]
            host_info = host_report['executables'][f'{kind}-{flags}']
            host_exe = snap / 'hosts' / f'{kind}-{flags}'
            if not host_exe.exists():
                if sha(host_info['path']) != host_info['sha256']:
                    raise ValueError(f'upstream host executable changed: {kind}-{flags}')
                snapshot(Path(host_info['path']), host_exe, report['snapshots'])
                host_exe.chmod(0o755)
            raw_trace = folder / 'controller.rows'
            oracle_command = ['nice', '-n', '20', str(host_exe), 'replay',
                              'p0:A' if case.startswith('ppz') else '0:A',
                              str(folder / 'mutated-pad.txt'), str(count), str(raw_trace)]
            oracle_env = {k: v for k, v in os.environ.items()
                          if not k.startswith(('SCD_', 'PPZ_', 'CC_', 'TT_', 'QQ_'))}
            oracle_env.update(ASAN_OPTIONS='detect_leaks=0', SCD_CAMPAIGN_RELOADS='1')
            with (folder / 'controller-host.log').open('w') as log:
                result = subprocess.run(oracle_command, cwd=source, env=oracle_env,
                                        stdout=log, stderr=log, timeout=120)
            if result.returncode not in (0, 1):
                raise ValueError(f'controller oracle failed for {name}: {result.returncode}')
            raw_trace = Path(str(raw_trace) + '.reload-0')
            rows = prefix_rows(raw_trace, count)
            report['snapshots'][str(raw_trace)] = sha(raw_trace)
            (folder / 'expected.txt').write_text(''.join(' '.join(map(str, row)) + '\n' for row in rows))
            report['snapshots'][str(folder / 'expected.txt')] = sha(folder / 'expected.txt')
            report['cases'][name] = dict(status='pending', passed=False, flags=flags,
                                        mutation=mutation, host_trace_sha256=sha(raw_trace),
                                        upstream_parity_sha256=sha(parity_trace),
                                        controller_oracle_command=oracle_command,
                                        controller_oracle_environment=dict(ASAN_OPTIONS='detect_leaks=0', SCD_CAMPAIGN_RELOADS='1'),
                                        original_recording=entry['original_recording'],
                                        original_sha256=entry['original_sha256'])
        save(out / 'report.json', report)
    except BaseException as exc:
        report.update(status='interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed',
                      error=f'{type(exc).__name__}: {exc}')
        save(out / 'report.json', report)
        raise
    return out, report


def run_case(out, report, name, timeout):
    case = report['cases'][name]
    folder = out / name
    flags = case['flags']
    zone = ZONES.index(name.split('1A-')[0])
    syms = report['symbols']
    snap = out / 'inputs'
    expected = [[int(v) for v in line.split()] for line in (folder / 'expected.txt').read_text().splitlines()]
    shots = sorted(set((expected[0][0], case['mutation']['start'] + 4,
                        case['mutation']['end'] + 4, expected[-1][0])))
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('SCD_', 'PPZ_', 'CC_', 'TT_', 'QQ_'))}
    overrides = dict(SCD_ZONE=str(zone), SCD_ZONE_ACT='0', SCD_ZONE_ERA='0',
                     SCD_WORLD_MAILBOX=syms['_scd_world_mailbox'],
                     SCD_OBJECTS_OVERLAY_FAULT=syms['_scd_objects_overlay_fault'],
                     SCD_ZONE_PAD_TRACE=str(folder / 'expected.txt'), SCD_ZONE_ROUTE_RETREAT='100',
                     SCD_ZONE_ROUTE_UPDATES=str(len(expected)), SCD_ZONE_PAD_TAIL='0',
                     SCD_BACKUP_INPUT=str(snap / f'backup-{flags}.bin'),
                     SCD_BACKUP_OUTPUT=str(folder / 'backup-output.bin'),
                     SCD_ZONE_ROUTE_SHOTS=','.join(map(str, shots)),
                     SCD_ZONE_ROUTE_PEEK=f'{int(syms["_scd_save_mailbox"], 16) + 44:x}:1')
    env.update(overrides)
    command = ['nice', '-n', '20', str(out / 'emulator'),
               str(snap / 'mednafen_saturn_libretro.dylib'), str(snap / 'sonic-cd-saturn-prototype.cue'),
               str(snap / 'bios'), str(folder), syms['_scd_trace_mailbox'], syms['_scd_audio_mailbox'], 'zones']
    case.update(status='running', passed=False, command=command, environment=overrides)
    save(folder / 'report.json', case)
    save(out / 'report.json', report)
    started = time.monotonic()
    try:
        with (folder / 'results.log').open('w') as log, (folder / 'core.log').open('w') as core:
            rc = subprocess.run(command, cwd=folder, env=env, stdout=log, stderr=core, timeout=timeout).returncode
        case['rc'] = rc
        if rc:
            raise ValueError(f'emulator exited {rc}; inspect core.log')
        case.update(verify_output((folder / 'results.log').read_text(), expected, zone, flags, shots))
        case['captures'] = {p.name: sha(p) for p in sorted(folder.glob('*.ppm'))}
        for sequence in shots:
            if not (folder / f'route-{sequence}.ppm').is_file():
                raise ValueError(f'missing capture: route-{sequence}.ppm')
        case.update(status='passed', passed=True)
    except BaseException as exc:
        case.update(status='interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed',
                    error=f'{type(exc).__name__}: {exc}')
        if isinstance(exc, KeyboardInterrupt):
            raise
    finally:
        case['seconds'] = round(time.monotonic() - started, 3)
        if (folder / 'backup-output.bin').is_file():
            case['backup_output_sha256'] = sha(folder / 'backup-output.bin')
        save(folder / 'report.json', case)
        save(out / 'report.json', report)
    print(f'{"PASS" if case["passed"] else "FAIL"}: QA campaign emulator {name}: '
          f'{case.get("matched_positions", 0)} positions; {case.get("error", "preset verified")}', flush=True)
    return case['passed']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--host-report', type=Path)
    parser.add_argument('--backup', type=Path)
    parser.add_argument('--updates', type=int, default=661)
    parser.add_argument('--case', choices=REQUIRED, action='append')
    parser.add_argument('--resume', type=Path)
    parser.add_argument('--timeout', type=int, default=300)
    args = parser.parse_args(argv)
    if args.timeout < 1 or not 10 <= args.updates <= 20000:
        parser.error('invalid limits')
    if args.resume:
        out = args.resume.resolve()
        report = json.loads((out / 'report.json').read_text())
    else:
        if not all((args.source_root, args.host_report, args.backup)):
            parser.error('source-root, host-report and backup are required for a new run')
        out, report = initialize(args.source_root.resolve(), args.host_report.resolve(), args.backup.resolve(), args.updates)
    print(f'Emulator campaign: {out}', flush=True)
    if sha(Path(__file__).resolve()) != sha(out / 'runner.py'):
        raise ValueError('runner changed since snapshot; start a fresh run')
    try:
        for path, expected in report['snapshots'].items():
            if sha(path) != expected:
                raise ValueError(f'snapshot changed: {path}')
        for name in args.case or REQUIRED:
            if report['cases'][name]['status'] == 'passed':
                continue
            if report['cases'][name]['status'] not in ('pending',):
                raise ValueError(f'no automatic retry of failed/interrupted case {name}')
            if not run_case(out, report, name, args.timeout):
                break
    except BaseException as exc:
        report.update(status='interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed',
                      passed=False, error=f'{type(exc).__name__}: {exc}')
        save(out / 'report.json', report)
        raise
    report['changed_snapshots'] = [path for path, expected in report['snapshots'].items() if sha(path) != expected]
    source = Path(report['source_root'])
    report['changed_host_gameplay_inputs'] = [path for path, expected in report['host_gameplay_inputs'].items()
                                            if sha(source / path) != expected]
    report['coverage_complete'] = all(report['cases'][name]['passed'] for name in REQUIRED)
    failed = report['changed_snapshots'] or report['changed_host_gameplay_inputs'] or any(
        c['status'] in ('failed', 'interrupted') for c in report['cases'].values())
    report['status'] = 'failed' if failed else 'passed' if report['coverage_complete'] else 'pending'
    report['passed'] = report['status'] == 'passed'
    save(out / 'report.json', report)
    completed = sum(c['passed'] for c in report['cases'].values())
    print(f'{"FAIL" if failed else "PASS" if report["passed"] else "PARTIAL"}: QA campaign emulator prefixes: '
          f'{completed}/14 cases; report={out / "report.json"}', flush=True)
    return bool(failed)


if __name__ == '__main__':
    sys.exit(main())
