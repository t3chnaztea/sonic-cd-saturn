#!/usr/bin/env python3
"""The staff roll, the end screen and the "PRESENTED BY SEGA" card on the Saturn
against the retail ending program, for both endings, and the picture times of both
endings and the opening.

  python3 tools/test_credits_roll_emulator.py [--out DIR] [good|bad|opening ...]

The Saturn side plays GOODEND.FMV / BADEND.FMV from the title through the test entry
in src/main.c (scd_credits_mailbox "ENDG"/"ENDB", src/credits_saturn.h) in the pinned
Beetle Saturn core (tools/credits_emulator.c) and holds Start 4 frames once the card has
held CARD_PRESS V-blanks. The retail side is tools/credits_roll_retail.py with the same
press: the user's US disc, or with --jp the local test disc carrying the Japanese
ending files, whichever region build/fmv (the disc's movies) holds.
Checks, per ending:
  roll   every Saturn frame of the roll (staff-roll step 1 up to retail job 11): the
         right half of the picture (x 160-319: the roll) equals the retail frame of
         that step (retail frame = first V-scroll frame - 3 + step, +-1 for the
         sub-line steps that leave the picture unchanged);
  end    from the last movie picture to the program's end the Saturn's distinct
         pictures equal the retail ones in order (the end screen, its fade out, the
         card's fade in, hold and fade out, black);
  hold   the card holds as many frames as retail (+-2: pad sampling);
  start  the last picture shows as many frames before the card's first change as
         retail (+-CARD_DELAY_SLACK: the Saturn's 59.83 Hz field against 59.92).
Per ending and for the opening ("OPNG": OPEN_M.MMD with OPN.STM on retail):
  times  every distinct whole-screen picture both machines show (the opening: every
         OPN.STM frame no other frame repeats, by its VRAM tiles on retail and the
         player's picture index on the Saturn), at its first frame on each: its time
         from the movie's start (the median offset of the first START_PICTURES
         pictures) on the Saturn, in Mega Drive frames (59.9227 Hz against the
         Saturn's 59.826 Hz fields), within PICTURE_SLACK of retail's. Not compared:
         a retail picture that changed while the Main CPU waited on the Sub CPU's
         packet handover (the oracle's sub_wait: a retail stall the Saturn has no
         counterpart for).
Writes <out>/report.json, marked pending, then passed or failed.
"""
import argparse, hashlib, json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / '.deps/beetle-saturn/mednafen_saturn_libretro.dylib'
DISC = ROOT / 'dist/sonic-cd-saturn-prototype.cue'
ELF = ROOT / 'build/saturn/sonic-cd-saturn-prototype.elf'
CARD_PRESS = 120
CARD_DELAY_SLACK = 1
REQUEST = {'good': '454E4447', 'bad': '454E4442', 'opening': '4F504E47'}
MD_HZ, SATURN_HZ = 59.9227, 26874100 / 4 / 427 / 263
START_PICTURES = 100
PICTURE_SLACK = 2.0   # +-1 frame, plus one: each machine rounds a change up to its own next V-blank


def picture_times(sat, rows, blank=None):
    """sat: (frame, crc) per Saturn frame of the movie; rows: the retail oracle's rows.
    Returns (pictures compared, worst offset in frames, its Saturn frame, anchor)."""
    def firsts(seq):
        seen = {}
        for f, c in seq:
            seen.setdefault(c, f)
        return seen
    s_first, r_first = firsts(sat), firsts((r['frame'], r['pixels']) for r in rows)
    # Not a retail picture whose change waited on the Sub CPU's packet handover (the Main
    # CPU polls $A1200F in the 4 frames before it; the Saturn has no such wait).
    waits = {r['frame'] for r in rows if r.get('sub_wait')}
    r_first = {c: f for c, f in r_first.items() if not waits & set(range(f - 4, f))}
    # Not the screen before the movie (black on both).
    blank = blank if blank is not None else {sat[0][1], rows[0]['pixels']}
    pairs = sorted((f, r_first[c]) for c, f in s_first.items() if c in r_first and c not in blank)
    if len(pairs) < START_PICTURES:
        return len(pairs), None, None, None
    ratio = MD_HZ / SATURN_HZ
    s0, r0 = pairs[0]
    offsets = [(r - r0) - (f - s0) * ratio for f, r in pairs]
    anchor = sorted(offsets[:START_PICTURES])[START_PICTURES // 2]
    worst = max(range(len(pairs)), key=lambda i: abs(offsets[i] - anchor))
    return len(pairs), round(offsets[worst] - anchor, 2), pairs[worst][0], round(anchor, 2)


def check_times(result, sat, rows, blank=None):
    n, worst, at, anchor = picture_times(sat, rows, blank)
    result.update(timed_pictures=n, worst_picture_offset=worst, worst_picture_saturn_frame=at, start_anchor=anchor)
    if worst is None:
        result['failures'].append(f'only {n} pictures in common with retail')
    elif abs(worst) > PICTURE_SLACK:
        result['failures'].append(f'picture at Saturn frame {at} is {worst} frames from its retail time')
CARD = 0xCA000000


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def symbol(name):
    out = subprocess.check_output([ROOT / '.toolchain/bin/sh-elf-nm', ELF], text=True)
    hits = [line.split()[0] for line in out.splitlines() if line.split()[-1] == name]
    assert len(hits) == 1, (name, hits)
    return hits[0]


def collapse(seq):
    out = []
    for x in seq:
        if not out or out[-1] != x:
            out.append(x)
    return out


def run_case(name, out, driver, jp):
    cdir = out / name
    cdir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, SCD_SYMS=f"trace={symbol('_scd_trace_mailbox')},credits={symbol('_scd_credits_mailbox')}",
               SCD_REQUEST=REQUEST[name], SCD_CARD_PRESS=str(CARD_PRESS))
    log = cdir / 'driver.log'
    with log.open('w') as f:
        code = subprocess.run(['nice', '-n', '20', str(driver), str(CORE), str(DISC), str(ROOT / 'assets/private'), str(cdir)],
                              cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT, timeout=3600).returncode
    lines = [line.split() for line in log.read_text().splitlines()]
    sat = [(int(r[1]), int(r[2]), int(r[3]), r[4], r[5]) for r in lines if r and r[0] == 'm']
    result = {'driver_exit': code, 'saturn_frames': len(sat), 'failures': []}
    if code or not sat:
        result['failures'].append(f'driver exit {code}, {len(sat)} frames')
        return result
    tag = name + ('-jp' if jp else '')
    args = ['python3', 'tools/credits_roll_retail.py', name, '--card-press', str(CARD_PRESS)] + (['--jp'] if jp else [])
    subprocess.run(args, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    rows = [json.loads(line) for line in (ROOT / 'build/credits/roll' / f'{tag}.jsonl').open()]
    if name == 'opening':
        # The opening's screen is 330 x 240 on the Saturn: pictures by identity instead,
        # the Saturn's shown picture (mailbox [3]) against the retail VRAM tiles of the
        # same OPN.STM frame (every frame of every packet, in order).
        sys.path.insert(0, str(ROOT / 'tools'))
        import fmv_extract as fx, zlib
        stm = (ROOT / 'build/fmv/OPN.STM').read_bytes()
        tiles = [zlib.crc32(stm[gfx + i * fx.FRAME + 32:gfx + i * fx.FRAME + 32 + 14336])
                 for kind, gfx, n in fx.packets(stm, 'opening') for i in range(n)]
        # Only pictures whose tiles no other frame repeats (not the black ones).
        index = {'%08x' % c: k for k, c in enumerate(tiles) if tiles.count(c) == 1}
        retail = [{'frame': r['frame'], 'pixels': index.get(r['video_tiles'], -1)} for r in rows]
        unique = set(index.values())
        check_times(result, [(f, pic if pic in unique and pic else -1) for f, _, pic, _, _ in sat], retail, blank={-1})
        return result
    check_times(result, [(f, crc) for f, _, pic, crc, _ in sat if pic < CARD], rows)
    vscroll = [int(r['vsram'][6:8] + r['vsram'][4:6], 16) for r in rows]
    base = next(i for i, v in enumerate(vscroll) if v) - 3
    # Roll: up to job 11 (RS), which clears CRAM; the video resumes after it, on each
    # machine's own clock.
    blobs = json.loads((ROOT / 'build/credits/roll' / f'{tag}-blobs.json').read_text())
    rs = next(i for i in range(base + 100, len(rows)) if not any(bytes.fromhex(blobs[rows[i]['cram']])))
    steps = min(max(s for _, s, _, _, _ in sat), rs - base)
    bad = [(f, s) for f, s, pic, _, right in sat if 1 <= s < steps and pic < CARD and
           not any(0 <= base + s + d < len(rows) and rows[base + s + d]['right'] == right for d in (-1, 0, 1))]
    roll_frames = sum(1 for _, s, pic, _, _ in sat if 1 <= s < steps and pic < CARD)
    result.update(roll_steps=steps, roll_frames=roll_frames, roll_mismatches=len(bad), roll_first=bad[:5],
                  retail_roll_base=base)
    if bad:
        result['failures'].append(f'{len(bad)} of {roll_frames} roll frames differ (first: Saturn frame {bad[0][0]}, step {bad[0][1]})')
    # End screen to the end of the program.
    first_card = next(i for i, x in enumerate(sat) if x[2] >= CARD)
    last_picture = sat[first_card - 1][3]
    tail = [x[3] for x in sat[first_card - 1:]]
    retail_last = max(i for i, r in enumerate(rows) if r['pixels'] == last_picture and i < len(rows) - 30)
    retail_first = retail_last
    while retail_first > 0 and rows[retail_first - 1]['pixels'] == last_picture:
        retail_first -= 1
    retail_tail = [r['pixels'] for r in rows[retail_first:len(rows) - 30]]
    s_seq, r_seq = collapse(tail), collapse(retail_tail)
    result.update(end_pictures=len(s_seq), retail_end_pictures=len(r_seq))
    if s_seq != r_seq:
        i = next((k for k, (a, b) in enumerate(zip(s_seq, r_seq)) if a != b), min(len(s_seq), len(r_seq)))
        result['failures'].append(f'end/card pictures differ at {i}: Saturn {s_seq[i:i + 3]}, retail {r_seq[i:i + 3]}')
    # Hold and start.
    hold_picture = max(set(retail_tail), key=retail_tail.count)
    s_hold, r_hold = tail.count(hold_picture), retail_tail.count(hold_picture)
    # Frames the last movie picture shows before the card's first change.
    crcs = [x[3] for x in sat]
    change = first_card - 1 + next(i for i, x in enumerate(tail) if x != last_picture)
    start = change
    while start > 0 and crcs[start - 1] == last_picture:
        start -= 1
    s_delay = change - start
    r_delay = next(i for i, x in enumerate(retail_tail) if x != last_picture)
    result.update(card_hold=s_hold, retail_card_hold=r_hold, last_picture_frames=s_delay, retail_last_picture_frames=r_delay)
    if abs(s_hold - r_hold) > 2:
        result['failures'].append(f'card held {s_hold} frames, retail {r_hold}')
    if abs(s_delay - r_delay) > CARD_DELAY_SLACK:
        result['failures'].append(f'the end screen shows {s_delay} frames before the card, retail {r_delay}')
    if not any(r and r[0] == 'done' and r[2] == '1' for r in lines):
        result['failures'].append('the title did not return')
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, default=ROOT / 'build/credits/roll-emulator')
    ap.add_argument('cases', nargs='*', default=['good', 'bad', 'opening'])
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    region = json.loads((ROOT / 'build/fmv/manifest.json').read_text()).get('region')
    jp = region == 'J'
    inputs = {str(p.relative_to(ROOT)): sha(p) for p in [ELF, DISC.with_suffix('.bin'), ROOT / 'cd/GOODEND.FMV',
              ROOT / 'cd/BADEND.FMV', ROOT / 'cd/OPN.FMV', ROOT / 'tools/credits_emulator.c', ROOT / 'tools/credits_roll_retail.py',
              ROOT / 'tools/test_credits_roll_emulator.py', ROOT / 'src/fmv_saturn.c']}
    report = {'status': 'pending', 'passed': False, 'region': region, 'inputs': inputs, 'cases': {},
              'scope': 'emulator only (Beetle Saturn vs Genesis Plus GX); not a hardware result'}
    path = out / 'report.json'
    path.write_text(json.dumps(report, indent=1) + '\n')
    try:
        driver = out / 'credits_emulator'
        subprocess.run(['clang', '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-I.deps/beetle-saturn/libretro-common/include', 'tools/credits_emulator.c', '-o', driver],
                       cwd=ROOT, check=True)
        for name in args.cases:
            report['cases'][name] = run_case(name, out, driver, jp)
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
    summary = ', '.join((f"{n} {c.get('roll_frames', 0)} roll frames, {c.get('end_pictures', 0)} end pictures, "
                         if n != 'opening' else f"{n} ") +
                        f"{c.get('timed_pictures', 0)} pictures timed (worst {c.get('worst_picture_offset')} frames)"
                        for n, c in report['cases'].items())
    print(f"{'PASS' if report['passed'] else 'FAIL'}: credits roll emulator ({region}) {summary} vs retail; report {path}")
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
