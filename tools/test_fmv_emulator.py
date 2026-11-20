#!/usr/bin/env python3
"""Pencil test in the emulator: Visual Mode's PENCIL TEST plays cd/PTEST.FMV as retail does.

  python3 tools/test_fmv_emulator.py [--fixture BACKUP]

Route (tools/frontend_emulator_test.c, the harness of tools/test_frontend_emulator.py):
boot dist/, open the title menu, take VISUAL MODE (the backup fixture holds the
Visual Mode unlock: build/frontend-qa/fixture-total154611.bin, written by
`python3 tools/test_frontend_emulator.py ta-thresholds`), Down x4 from EXIT to
PENCIL TEST (src/visual_mode.c, Main.asm UpdateSelection), A. Start is held for 30 frames mid-movie: PTEST.MMD never reads it.

The retail reference is build/fmv/retail-ptest.json (tools/fmv_retail.py ptest:
the retail PTEST.MMD in the Sega CD core), run here when missing or made from
other inputs. Checks, from the emulator only:
  - every picture retail shows (banks 0-837) is swapped in once, in order, with
    its data in time (src/fmv_saturn.c ptest_play, mailbox and picture log);
  - pacing: each picture's time after picture 0 within 67 ms (4 retail frames)
    of retail's, Saturn fields at 59.826 Hz against Mega Drive V-blanks at
    59.9227 Hz (retail's emulated Sub CPU repeats a bank 3 times; the port does not);
  - absolute: each picture's time from the start within +-1 frame of retail's (plus
    one frame of V-blank rounding), but
    the two after each bank retail repeats;
  - picture 0 is 90 fields after fade step 0, fade-out step 7 64 fields after
    the last picture, the return 8 fields after step 0, as measured on retail;
  - three mid-movie screenshots equal one decoded picture over PTEST.MMD's
    border in Saturn colors (line 1 colour 5 = $0644), whole 320 x 224 screen;
  - back on the Visual Mode menu, drawn as before the movie (the menu program runs
    again, so EXIT is selected, as in the shot before the Down presses).
Writes build/fmv-qa/report.json: pending first, then passed or failed, with the
disc and input hashes. Emulator evidence only; not a hardware result.
"""
import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import fmv_convert  # noqa: E402
import title_menu  # noqa: E402

OUT = ROOT / 'build/fmv-qa'
FMV = ROOT / 'build/fmv'
DISC = ROOT / 'dist/sonic-cd-saturn-prototype.bin'
ELF = ROOT / 'build/saturn/sonic-cd-saturn-prototype.elf'
HARNESS = OUT / 'frontend_emulator_test'
MD_LEVELS = [0, 52, 87, 116, 144, 172, 206, 255]
PICTURES = 838
MD_HZ, SATURN_HZ = 59.9227, 26874100 / 4 / 427 / 263
DRIFT_MS = 67   # 4 retail frames: retail's emulated Sub CPU repeats a bank 3 times (+3 frames each)
TITLE = "run 200\nuntil TITL 3000\nrun 240\n"
OPEN_MENU = "hold START 4\nrun 90\n"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rgb555(md):
    """src/fmv_stm.c fmv_md_to_rgb555 as (r, g, b) 5-bit levels."""
    return tuple((MD_LEVELS[(md >> s) & 7] * 31 + 127) // 255 for s in (1, 5, 9))


def retail_reference():
    path = FMV / 'retail-ptest.json'
    want = {n: sha(p) for n, p in (('PTEST.STM', FMV / 'PTEST.STM'), ('PTEST.MMD', FMV / 'PTEST.MMD'),
                                   ('fmv_retail.py', ROOT / 'tools/fmv_retail.py'))}
    if not path.exists() or json.loads(path.read_text()).get('inputs') != want:
        r = subprocess.run(['nice', '-n', '20', 'python3', 'tools/fmv_retail.py', 'ptest', '--frames', '4200'],
                           cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            raise SystemExit('FAIL: fmv emulator: retail reference (tools/fmv_retail.py ptest) failed\n' + r.stdout[-2000:])
    return json.loads(path.read_text())


def screen(path):
    """PPM screenshot as rows of 5-bit (r, g, b)."""
    data = Path(path).read_bytes()
    head = data.split(b'\n', 3)
    w, h = map(int, head[1].split())
    body = head[3]
    return w, h, [[tuple(c >> 3 for c in body[(y * w + x) * 3:(y * w + x) * 3 + 3]) for x in range(w)] for y in range(h)]


class Expected:
    """The whole 320 x 224 screen PTEST.MMD shows while pictures play."""

    def __init__(self):
        stm = (FMV / 'PTEST.STM').read_bytes()
        prog = fmv_convert.ptest_program((FMV / 'PTEST.MMD').read_bytes())
        self.stm = stm
        fade = struct.unpack('>16H', prog['fade'][7 * 32:8 * 32])
        line1 = list(fade)
        line1[5] = 0x0644               # PTEST.MMD V-int, state 12
        names = struct.unpack('>1120H', prog['border_map'])
        art = prog['border_tiles']
        self.border = []
        for y in range(224):
            row = []
            for x in range(320):
                w = names[(y >> 3) * 40 + (x >> 3)]
                tx = 7 - (x & 7) if w & 0x800 else x & 7
                ty = 7 - (y & 7) if w & 0x1000 else y & 7
                b = art[((w & 0x7FF) - 0x3E8) * 32 + ty * 4 + (tx >> 1)]
                row.append(rgb555(line1[b & 15 if tx & 1 else b >> 4]))   # index 0: back screen = line 1 colour 0
            self.border.append(row)

    def picture(self, k):
        at = k * 5 * 2048 + 16
        pal = struct.unpack('>16H', self.stm[at:at + 32])
        tiles = self.stm[at + 32:at + 32 + 9408]
        rows = [list(r) for r in self.border]
        for y in range(112):
            for x in range(168):
                b = tiles[((y >> 3) * 21 + (x >> 3)) * 32 + (y & 7) * 4 + ((x & 7) >> 1)]
                i = b & 15 if x & 1 else b >> 4
                if i:
                    rows[56 + y][72 + x] = rgb555(pal[i])
        return rows


def origin(shot, border):
    """Offset of the 320 x 224 picture in the harness's frame: where the border matches."""
    w, h, px = shot
    for dy in range(0, h - 223):
        for dx in range(0, w - 319):
            if all(px[dy + y][dx + x] == border[y][x] for y in range(0, 224, 7) for x in range(0, 320, 5)
                   if not (56 <= y < 168 and 72 <= x < 240)):
                return dx, dy
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--fixture', type=Path, default=ROOT / 'build/frontend-qa/fixture-total154611.bin')
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    report = {'status': 'pending', 'passed': False, 'hardware_tested': False, 'disc_sha256': sha(DISC),
              'elf_sha256': sha(ELF), 'fmv_sha256': sha(ROOT / 'cd/PTEST.FMV'),
              'inputs': {n: sha(ROOT / n) for n in ['tools/test_fmv_emulator.py', 'tools/frontend_emulator_test.c',
                                                    'src/fmv_saturn.c', 'src/fmv_stm.c', 'src/frontend.c', 'src/visual_mode.c',
                                                    'tools/fmv_convert.py', 'tools/fmv_retail.py']}}

    def write():
        (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n')

    def fail(message, out=''):
        report.update(status='failed', message=message)
        write()
        print(f'FAIL: fmv emulator pencil test: {message}')
        if out:
            print('\n'.join(out.splitlines()[-8:]))
        return 1

    write()
    if not args.fixture.exists():
        # The fixture comes from the front-end gate's Time Attack threshold case.
        subprocess.run(['python3', 'tools/test_frontend_emulator.py', 'ta-thresholds'], cwd=ROOT,
                       capture_output=True, text=True)
    if not args.fixture.exists():
        return fail(f'{args.fixture} missing: python3 tools/test_frontend_emulator.py ta-thresholds did not write it')
    retail = retail_reference()
    report['retail'] = {k: retail[k] for k in ('pictures_shown', 'last_index', 'fade_step0_frame', 'first_shown_frame',
                                               'last_shown_frame', 'fade_out_step7_frame', 'end_frame',
                                               'screens_checked', 'banks_repeated')}
    subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                    '-I.deps/beetle-saturn/libretro-common/include', 'tools/frontend_emulator_test.c',
                    '-o', str(HARNESS)], cwd=ROOT, check=True)
    nm = subprocess.check_output([str(ROOT / '.toolchain/bin/sh-elf-nm'), str(ELF)], text=True)
    syms = {re.sub(r'\.lto_priv\.\d+$', '', p[2]): p[0] for p in (r.split() for r in nm.splitlines()) if len(p) == 3}

    def harness(folder, script):
        folder.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.pop('SCD_BACKUP_INPUT', None)
        # scd_fmv_mailbox: low work RAM (src/fmv_saturn.h FMV_LWRAM_STATE), cache-through.
        env.update(SCD_SYMS=f"trace={syms['_scd_trace_mailbox']},fmv=20243000,vm={syms['_fe_vm']},rec={syms['_fe_ta_rec']}",
                   SCD_BACKUP_INPUT=str(args.fixture), SCD_BACKUP_OUTPUT=str(folder / 'backup.bin'))
        (folder / 'script.txt').write_text(script)
        args_h = [str(HARNESS), str(ROOT / '.deps/beetle-saturn/mednafen_saturn_libretro.dylib'),
                  str(ROOT / 'dist/sonic-cd-saturn-prototype.cue'), str(ROOT / 'assets/private'), str(folder),
                  str(folder / 'script.txt')]
        with (folder / 'core.log').open('w') as err:
            r = subprocess.run(['nice', '-n', '20'] + args_h, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=err,
                               text=True, timeout=3600)
        (folder / 'results.log').write_text(r.stdout)
        peeks = {}
        for line in r.stdout.splitlines():
            m = re.match(r'frame=\d+ peekb? (\S+)((?: [0-9a-f]{2,8})+)$', line)
            if m:
                peeks[m.group(1)] = [int(x, 16) for x in m.group(2).split()]
        return r.returncode, r.stdout, peeks

    # VISUAL MODE by identity: the fixture's own menu (tools/title_menu.py).
    rc, out, probe = harness(OUT / 'menu-probe', title_menu.PROBE)
    if rc:
        return fail(f'menu probe: harness status {rc}', out)
    try:
        walk, position = title_menu.route(probe, title_menu.VISUAL_MODE)
    except ValueError as e:
        return fail(str(e))
    script = TITLE + OPEN_MENU + walk + "peek sel trace 0 4\ntap A\nuntil FEND 900\n" + \
        "until_word vm 0 00000003 600\nrun 10\npeek vm trace 0 4\nshot menu\ntap DOWN\ntap DOWN\ntap DOWN\ntap DOWN\nrun 10\ntap A\n"
    for n, wait in enumerate((600, 900, 1200)):
        script += f"run {wait}\npeek a{n} fmv 0 16\nshot p{n}\npeek b{n} fmv 0 16\n"
        if n == 0:
            script += "hold START 30\n"
    script += "until_word fmv 48 00000300 4000\nuntil_word vm 0 00000003 600\nrun 10\npeek end fmv 0 16\n" + \
        f"peek log fmv {0x3000} {PICTURES // 2}\npeek back trace 0 4\nshot after\n"
    rc, out, peeks = harness(OUT, script)
    if rc:
        return fail(f'harness status {rc}', out)
    shots = dict(re.findall(r'shot (\w+) \d+x\d+ hash=(\w+)', out))
    if peeks['sel'][2] >> 16 & 255 != position or peeks['vm'][2] & 255 != 3:
        return fail(f"Visual Mode not reached: {peeks['sel']} {peeks['vm']}", out)

    # Mailbox (src/fmv_saturn.h): [3] picture, [5] shown, [7] late fields, [8] fields,
    # [9] largest lateness (FRT ticks), [10] sectors, [11] not ready, [13] CD error.
    end = peeks['end']
    log = [v for w in peeks['log'] for v in (w >> 16, w & 0xFFFF)]
    report['saturn'] = {'pictures_shown': end[5], 'last_picture': end[3], 'fields': end[8], 'late_fields': end[7],
                        'max_late_frt_ticks': end[9], 'sectors_read': end[10], 'not_ready': end[11],
                        'cd_error': end[13], 'first_picture_field': log[0], 'last_picture_field': log[-1]}
    if end[5] != PICTURES or end[3] != PICTURES - 1 or retail['pictures_shown'] != PICTURES or retail['last_index'] != PICTURES - 1:
        return fail(f"pictures: Saturn {end[5]} (last {end[3]}), retail {retail['pictures_shown']}", out)
    if end[11] or end[7] or end[13] or end[10] != PICTURES * 5:
        return fail(f"stream: not ready {end[11]}, late fields {end[7]}, CD error {end[13]}, sectors {end[10]}", out)
    if any(b <= a for a, b in zip(log, log[1:])):
        return fail('picture log not increasing', out)
    # Retail: picture 0 at fade step 0 + 90, fade-out step 7 at last + 64, return at step 7 + 64.
    r_first = retail['first_shown_frame'] - retail['fade_step0_frame']
    r_hold = retail['fade_out_step7_frame'] - retail['last_shown_frame']
    r_end = retail['end_frame'] - retail['fade_out_step7_frame']
    s_end = end[8] - 1 - log[-1]   # fields counted to the return, after the last swap
    report['timing'] = {'retail_first_after_step0': r_first, 'saturn_first_after_step0': log[0],
                        'retail_hold_plus_fade': r_hold + r_end, 'saturn_hold_plus_fade': s_end}
    if (r_first, r_hold, r_end) != (90, 64, 64) or log[0] != r_first or s_end != r_hold + r_end:
        return fail(f"fade timing: retail first {r_first} hold {r_hold} end {r_end}; Saturn first {log[0]} end {s_end}", out)
    # Compare in time: retail counts Mega Drive V-blanks (59.9227 Hz), the Saturn
    # 320-pixel NTSC fields (26.8741 MHz / 4 / 427 / 263 = 59.826 Hz).
    rp = retail['picture_frames']
    drift = [round(((log[k] - log[0]) / SATURN_HZ - (rp[k] - rp[0]) / MD_HZ) * 1000) for k in range(PICTURES)]
    gaps = {}
    for a, b in zip(log, log[1:]):
        gaps[b - a] = gaps.get(b - a, 0) + 1
    report['timing'].update(max_drift_ms=max(drift, key=abs), saturn_gaps={str(k): v for k, v in sorted(gaps.items())},
                            retail_gaps=retail['frames_between_pictures'],
                            saturn_span_s=round((log[-1] - log[0]) / SATURN_HZ, 3),
                            retail_span_s=round((rp[-1] - rp[0]) / MD_HZ, 3))
    if max(abs(d) for d in drift) > DRIFT_MS:
        k = max(range(PICTURES), key=lambda i: abs(drift[i]))
        return fail(f'pacing: picture {k} {drift[k]} ms from retail', out)
    # Absolute: each picture's time from the start (the median offset of the first 100
    # pictures) within +-1 frame of retail's, plus one (each machine rounds a swap up to
    # its own next V-blank: tools/test_credits_roll_emulator.py PICTURE_SLACK), but the
    # two pictures after each bank retail's emulated Sub CPU
    # repeats (retail_reference banks_repeated: [frame, bank]).
    offsets = [(rp[k] - rp[0]) - (log[k] - log[0]) * MD_HZ / SATURN_HZ for k in range(PICTURES)]
    anchor = sorted(offsets[:100])[50]
    skip = {b + d for _, b in retail['banks_repeated'] for d in (1, 2)}
    timed = [k for k in range(PICTURES) if k not in skip]
    worst = max(timed, key=lambda k: abs(offsets[k] - anchor))
    report['timing'].update(picture_offset_worst=round(offsets[worst] - anchor, 2), picture_offset_at=worst,
                            pictures_timed=len(timed), start_anchor=round(anchor, 2))
    if abs(offsets[worst] - anchor) > 2.0:
        return fail(f'picture {worst} is {offsets[worst] - anchor:.2f} frames from its retail time', out)

    # Screens: one of the pictures around the mailbox's picture, exactly.
    exp = Expected()
    checked = []
    for n in range(3):
        shot = screen(OUT / f'p{n}.ppm')
        at = origin(shot, exp.border)
        if at is None:
            return fail(f'shot p{n}: border not found', out)
        dx, dy = at
        lo, hi = peeks[f'a{n}'][3], peeks[f'b{n}'][3]
        hit = None
        for k in range(max(0, lo - 1), min(PICTURES, hi + 2)):
            want = exp.picture(k)
            if all(shot[2][dy + y][dx:dx + 320] == want[y] for y in range(224)):
                hit = k
                break
        if hit is None:
            return fail(f'shot p{n}: no picture {lo}-{hi} matches the screen', out)
        checked.append(hit)
    report['screens'] = {'pictures_matched': checked, 'origin': [dx, dy], 'start_held_after_picture': peeks['b0'][3]}
    if peeks['back'][0] != 0x46454E44 or peeks['back'][2] & 255 != 3 or shots.get('after') != shots.get('menu'):
        return fail(f"no Visual Mode menu after the movie: {peeks['back']} shots {shots}", out)
    report.update(status='passed', passed=True)
    write()
    t = report['timing']
    print(f"PASS: fmv emulator pencil test: {end[5]} pictures as retail (drift <= {abs(t['max_drift_ms'])} ms, "
          f"{t['pictures_timed']} within {abs(t['picture_offset_worst'])} frames of retail, "
          f"first +{log[0]}, hold+fade {s_end}), screens {checked} exact, Start ignored, back to Visual Mode; "
          f"disc {report['disc_sha256'][:16]}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
