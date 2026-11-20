#!/usr/bin/env python3
"""The "Thank You" screen on the Saturn against the retail program, picture for picture.

  python3 tools/test_credits_emulator.py [--out DIR] [--quick]

Two runs of the built disc (dist/sonic-cd-saturn-prototype.cue) in the pinned Beetle
Saturn core (tools/credits_emulator.c), each entered from the title through the test
entry in src/main.c (scd_credits_mailbox, src/credits_saturn.h):
  timer  no input: the whole screen, fade in to the 3-minute end timer's fade out;
  start  Start once the picture of call 600 shows: the quit and its fade out.
Each against tools/credits_retail.py's run of THANKS_M.MMD in the pinned Genesis Plus
GX core with the same input (the retail frame of call c is 124 + c; a Start press that
the Saturn takes on call q is the retail press at frame q + 122). Every Saturn frame's
picture, as the Mega Drive colours it shows, must equal the retail frame of the call
it shows (CRC of the RGB565 picture); every call must be shown; the title must return.
--quick runs only the start case.
Writes <out>/report.json, marked pending, then passed or failed.
"""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / '.deps/beetle-saturn/mednafen_saturn_libretro.dylib'
DISC = ROOT / 'dist/sonic-cd-saturn-prototype.cue'
ELF = ROOT / 'build/saturn/sonic-cd-saturn-prototype.elf'
RETAIL_OUT = ROOT / 'build/credits/retail'
FIRST_RETAIL = 124   # retail frame of call 0 (tools/test_credits.py)
CASES = {'start': 600, 'timer': None}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def symbol(name):
    out = subprocess.check_output([ROOT / '.toolchain/bin/sh-elf-nm', ELF], text=True)
    hits = [line.split()[0] for line in out.splitlines() if line.split()[-1] == name]
    assert len(hits) == 1, (name, hits)
    return hits[0]


def retail(tag, press):
    args = ['python3', 'tools/credits_retail.py', '--frames', '11200', '--tag', tag]
    if press is not None:
        args += ['--press', str(press)]
    subprocess.run(args, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    return [json.loads(line) for line in (RETAIL_OUT / f'{tag}.jsonl').open()]


def run_case(name, press_call, out, driver):
    cdir = out / name
    cdir.mkdir(parents=True, exist_ok=True)
    env = {'SCD_SYMS': f"trace={symbol('_scd_trace_mailbox')},credits={symbol('_scd_credits_mailbox')}",
           'SCD_SHOTS': '0,21,300,1200'}
    if press_call is not None:
        env['SCD_PRESS_CALL'] = str(press_call)
    log = cdir / 'driver.log'
    with log.open('w') as f:
        code = subprocess.run(['nice', '-n', '20', str(driver), str(CORE), str(DISC), str(ROOT / 'assets/private'), str(cdir)],
                              cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT, timeout=3600).returncode
    rows = [line.split() for line in log.read_text().splitlines()]
    frames = [(int(r[1]), int(r[2]), int(r[3]), int(r[4]), r[5]) for r in rows if r and r[0] == 'f']
    done = next((r for r in rows if r and r[0] == 'done'), None)
    result = {'driver_exit': code, 'frames': len(frames), 'title_back': bool(done and done[2] == '1'),
              'screen': done[3] if done else None, 'failures': []}
    if code or not frames:
        result['failures'].append(f'driver exit {code}, {len(frames)} frames')
        return result
    calls = [f[1] for f in frames if f[1] >= 0]
    # The phase in a line is the one after the call shown: the call that set the quit
    # flag is the first one shown in phase 2.
    quit_call = min((f[1] for f in frames if f[2] == 2 and f[1] >= 0), default=None) if press_call is not None else None
    retail_rows = retail(f'emu-{name}', None if quit_call is None else quit_call + 122)
    result.update(last_call=max(calls), quit_call=quit_call, retail_frames=len(retail_rows))
    missing = sorted(set(range(max(calls) + 1)) - set(calls))
    repeats = len(calls) - len(set(calls))
    bad = []
    for frame, call, phase, sprites, crc in frames:
        if call < 0:
            continue
        at = FIRST_RETAIL + call
        if at >= len(retail_rows) or retail_rows[at]['pixels'] != crc:
            bad.append((frame, call, crc, retail_rows[at]['pixels'] if at < len(retail_rows) else None))
    # The last call: src/credits.c's Sega CD mode on the host (tools/test_credits.py
    # builds it) with the same quit, whose pictures equal these retail frames there.
    native = subprocess.check_output([str(ROOT / 'build/credits/credits_native'), 'md', '20000',
                                      str(quit_call if quit_call is not None else -1)], cwd=ROOT, text=True)
    native_last = sum(1 for line in native.splitlines() if line.startswith('md ')) - 1
    result.update(compared=len(calls) - len([b for b in bad if b[3] is None]), mismatches=len(bad), first_mismatches=bad[:8],
                  missing_calls=len(missing), first_missing=missing[:8], repeated_pictures=repeats,
                  native_last_call=native_last)
    if bad:
        result['failures'].append(f'{len(bad)} pictures differ from retail (first: Saturn frame {bad[0][0]}, call {bad[0][1]})')
    if missing:
        result['failures'].append(f'{len(missing)} calls never shown (first {missing[0]})')
    if max(calls) != native_last:
        result['failures'].append(f'last call {max(calls)}, src/credits.c on the host {native_last}')
    if not result['title_back']:
        result['failures'].append('the title did not return')
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, default=ROOT / 'build/credits/emulator')
    ap.add_argument('--quick', action='store_true')
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    inputs = {str(p.relative_to(ROOT)): sha(p) for p in [ELF, DISC.with_suffix('.bin'), ROOT / 'cd/THANKS.BIN',
              ROOT / 'tools/credits_emulator.c', ROOT / 'tools/test_credits_emulator.py', ROOT / 'tools/credits_retail.py',
              ROOT / 'src/credits.c', ROOT / 'src/credits_saturn.c']}
    report = {'status': 'pending', 'passed': False, 'inputs': inputs, 'cases': {},
              'scope': 'emulator only (Beetle Saturn vs Genesis Plus GX); not a hardware result'}
    path = out / 'report.json'
    path.write_text(json.dumps(report, indent=1) + '\n')
    try:
        driver = out / 'credits_emulator'
        subprocess.run(['clang', '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-I.deps/beetle-saturn/libretro-common/include', 'tools/credits_emulator.c', '-o', driver],
                       cwd=ROOT, check=True)
        for name, press in CASES.items():
            if args.quick and name != 'start':
                continue
            report['cases'][name] = run_case(name, press, out, driver)
            path.write_text(json.dumps(report, indent=1) + '\n')
    except BaseException as e:
        report['status'] = 'interrupted'
        report['error'] = repr(e)
        path.write_text(json.dumps(report, indent=1) + '\n')
        raise
    failures = [f'{n}: {f}' for n, c in report['cases'].items() for f in c['failures']]
    report['passed'] = not failures
    report['status'] = 'passed' if not failures else 'failed'
    path.write_text(json.dumps(report, indent=1) + '\n')
    for f in failures:
        print('  ' + f)
    summary = ', '.join(f"{n} {c.get('compared', 0)} pictures" for n, c in report['cases'].items())
    print(f"{'PASS' if report['passed'] else 'FAIL'}: credits emulator {summary} vs retail; report {path}")
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
