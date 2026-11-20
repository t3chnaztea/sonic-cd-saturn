#!/usr/bin/env python3
"""Game ending route in the emulator: IPX.asm GameDone's choice, the movie, the title.

  python3 tools/test_ending_emulator.py [--out DIR] [case ...]   (default: the ending cases)
  python3 tools/test_ending_emulator.py --case good|bad|stones --out DIR

Gate cases (tests/special/gate-cases.json): ENDING-good = stones futures,
ENDING-bad = none, STONES-return = return-act2 return-act3.

Each case boots dist/ with a crafted backup RAM holding a Metallic Madness Act 3
save (the format of tools/test_save_matrix.py, cloned from a BIOS-written file),
takes Continue, and lets tools/ending_emulator.c end the game the way src/main.c
does after EMIE8 (act_fade = 1). It checks, from the emulator only:
  - the ending picked (world mailbox [137] bit 16) against IPX.asm:307-310;
  - the movie played to its end (scd_ending_play result 0, every picture of the
    stream shown but the last packet's, the staff roll stepped, audio not silent);
  - the title screen came back afterwards.
Stones-return cases (IPX.asm .SpecialStage 586-597, Level/Main.asm 22-26,
Results/Main.asm 297-310):
  return-act2: Continue into Palmtree Panic Act 1 holding stones 2-7, take the big
    ring (fixture Start+C+Left, as tools/test-bigring-emulator.sh) and win Special
    Stage 1 with the retail win route: Act 2 must start with all 7 stones, the fade
    from white and the good future forced.
  allstones-act3: Continue into Act 2 holding all 7 stones (the good future is forced
    at its load), end the act: Act 3 must load in the good future.
Writes <out>/report.json (passed, disc_sha256); marks it pending first, then passed,
failed or interrupted. Emulator evidence only; not a hardware result.
"""
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Output volume: SCD_OUTPUT_VOLUME if set, else the mount point that holds the repo.
VOLUME = Path(os.environ.get('SCD_OUTPUT_VOLUME') or next(p for p in (ROOT, *ROOT.parents) if os.path.ismount(p)))
OUT = ROOT / 'build/ending-test'
ELF = ROOT / 'build/saturn/sonic-cd-saturn-prototype.elf'
DISC = ROOT / 'dist/sonic-cd-saturn-prototype.bin'
CORE = ROOT / '.deps/beetle-saturn/mednafen_saturn_libretro.dylib'
FMV_STILL, FMV_VIDEO, FMV_ANIM = 1, 0, 2
# name: (era of Act 3, time stones, good-future zones before MM, expected good ending)
CASES = {
    'stones': (3, 0x7F, 0x00, True),    # all seven stones, no good futures
    'futures': (2, 0x00, 0x3F, True),   # six good futures; MM3 in the good future adds bit 6
    'none': (3, 0x00, 0x00, False),     # no stones, no good futures
}
# name: (act index of the save, next act after the special stage)
STONES = {'return-act2': (0, 0x7E, 'ring', 1), 'allstones-act3': (1, 0x7F, 'end', 2)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def symbols():
    out = subprocess.check_output([ROOT / '.toolchain/bin/sh-elf-nm', ELF], text=True)
    table = {}
    for row in out.splitlines():
        p = row.split()
        if len(p) == 3:
            table[p[2]] = p[0]
    def all_of(name):
        return [v for k, v in table.items() if k == name or k.startswith(name + '.lto_priv.')]
    def find(name):
        hits = all_of(name)
        assert len(hits) == 1, (name, hits)
        return hits[0]
    find.all = all_of
    return find


def pictures(fmv):
    """Pictures the player shows for one stream: every "08"/"15" frame, one per SR, but
    none of the last packet (the stream ends when the Sub CPU takes it; FMV/Sub
    (Ending).asm .Exit, ENDING.MMD $FF20F0)."""
    head = Path(fmv).read_bytes()[:2048]
    assert head[:4] == b'SFMV'
    packets = struct.unpack('>I', head[8:12])[0]
    total = 0
    for b in head[128:128 + packets - 1]:
        kind, frames = b >> 4, b & 15
        total += frames if kind in (FMV_VIDEO, FMV_ANIM) else 1 if kind == FMV_STILL else 0
    return total


def record(zone, act, era, stones, acts, zones, gen=1, spec_stage=0):
    data = bytearray(b'SCDS\x02\x20\x00\x00' + struct.pack('>I', gen) + bytes([zone, act, era, stones, acts, zones, 0, spec_stage]) + bytes(8))
    return data + struct.pack('>I', zlib.crc32(data))


def insert(template, image, block, name, data):
    # Clone the BIOS-written two-block file, directory included (tools/test_save_matrix.py).
    first, second = bytearray(template[128:192]), bytearray(64)
    assert first[4:15] == b'SCDSATURN00' and first[38:42] == b'SCDS'
    first[4:15] = name.encode()
    first[34:36] = struct.pack('>H', block + 1)
    first[38:64], second[4:10] = data[:26], data[26:]
    image[block * 64:(block + 1) * 64] = first
    image[(block + 1) * 64:(block + 2) * 64] = second


def stones_case(name, driver, template, find, trace, world, fade):
    act, stones, kind, next_act = STONES[name]
    cdir = OUT / name
    cdir.mkdir(parents=True, exist_ok=True)
    image = bytearray(32768)
    image[:64] = template[:64]
    insert(template, image, 2, 'SCDSATURN00', record(0, act, 0, stones, 0, 0, spec_stage=0))
    backup = cdir / 'backup-in.bin'
    backup.write_bytes(image)
    era = find('_era')
    held = '%08x' % (int(era, 16) - 4)     # main.c time_stones: the symbol just before era
    assert held in find.all('_time_stones'), 'main.c time_stones moved'
    env = {k: v for k, v in os.environ.items() if not k.startswith('SCD_')}
    env.update(SCD_BACKUP_INPUT=str(backup), SCD_STONES_KIND=kind,
               SCD_STONES=','.join([find('_special_mode'), held, find('_fade_white'), era, find('_stage_act')]),
               SCD_OBJ_GOOD=find('_good_future'))   # objects.c: the only good_future symbol
    if kind == 'ring':
        pad = ROOT / 'build/special-retail/win.pad'
        if not pad.exists():
            subprocess.run(['python3', 'tools/special_retail.py', 'win'], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        env.update(SCD_SPECIAL_GAME=find('_scd_special_game_mailbox'), SCD_WIN_PAD=str(pad))
    with (cdir / 'driver.log').open('w') as log:
        code = subprocess.run([driver, CORE, ROOT / 'dist/sonic-cd-saturn-prototype.cue', ROOT / 'assets/private',
                               cdir, trace, world, fade], cwd=ROOT, env=env, stdout=log,
                              stderr=subprocess.STDOUT, timeout=1800).returncode
    r = json.loads((cdir / 'ending.json').read_text())
    checks = {
        'driver_exit_0': code == 0,
        'continued': r['zone'] == 0 and r['act_before'] == act and r['stones_before'] == stones,
        'next_act': r['stage_act'] == next_act,
        'seven_stones': r['time_stones'] == 0x7F,
    }
    if kind == 'ring':
        checks.update(special_stage_won=r['special_frames'] > 0, fade_from_white=r['white_frames'] > 0,
                      good_future_forced=r['world_good_future'] == 1 and r['era'] == 0,
                      objects_good_future=r['objects_good_future_before'] == 0 and r['objects_good_future'] == 1)
    else:
        # Continue restores the stones before the act loads (IPX.asm ReadSaveData before
        # LevelStart): both flags are forced by that first load, in the present.
        checks.update(good_future_forced_before=r['world_good_future_before'] == 1,
                      objects_forced_at_first_load=r['objects_good_future_before'] == 1,
                      act3_good_future=r['era'] == 2)
    case = dict(name=name, kind='stones-return', act=act, next_act=next_act, result=r, checks=checks,
                passed=all(checks.values()))
    print(f"{'PASS' if case['passed'] else 'FAIL'} {name}: act={r['stage_act']} era={r['era']} stones={r['time_stones']:#x} "
          f"white_frames={r['white_frames']} world_good_future={r['world_good_future_before']}->{r['world_good_future']} "
          f"objects_good_future={r['objects_good_future_before']}->{r['objects_good_future']}", flush=True)
    return case


def main():
    assert ROOT.is_relative_to(VOLUME), 'outputs must stay on the output volume'
    assert shutil.disk_usage(VOLUME).free >= 100 * 1024**3, 'keep 100 GiB free'
    try:
        os.nice(20)
    except PermissionError:
        pass
    global OUT
    args = sys.argv[1:]
    if args[:1] == ['--out']:
        OUT = Path(args[1]).resolve()
        args = args[2:]
    if args[:1] == ['--case']:
        args = {'good': ['stones', 'futures'], 'bad': ['none'], 'stones': list(STONES)}[args[1]] + args[2:]
        if args[-2:-1] == ['--out']:
            OUT = Path(args[-1]).resolve()
            args = args[:-2]
    names = args or list(CASES)
    for n in names:
        assert n in CASES or n in STONES, n
    OUT.mkdir(parents=True, exist_ok=True)
    inputs = {str(p.relative_to(ROOT)): sha(p) for p in [
        ELF, DISC, CORE, ROOT / 'tools/test_ending_emulator.py', ROOT / 'tools/ending_emulator.c',
        ROOT / 'src/ending.c', ROOT / 'src/ending.h', ROOT / 'src/fmv_saturn.c', ROOT / 'src/main.c',
        ROOT / 'cd/GOODEND.FMV', ROOT / 'cd/BADEND.FMV']}
    report = {'status': 'pending', 'passed': False, 'disc_sha256': inputs[str(DISC.relative_to(ROOT))],
              'inputs': inputs, 'cases': [],
              'scope': 'emulator only; ending triggered by act_fade=1 as src/main.c does after EMIE8'}
    path = OUT / 'report.json'
    save = lambda: path.write_text(json.dumps(report, indent=1) + '\n')
    save()
    try:
        driver = OUT / 'ending_emulator'
        subprocess.run(['clang', '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-I.deps/beetle-saturn/libretro-common/include', '-Itools',
                        'tools/ending_emulator.c', '-o', driver], cwd=ROOT, check=True)
        find = symbols()
        trace, world, fade = find('_scd_trace_mailbox'), find('_scd_world_mailbox'), find('_act_fade')
        # A BIOS-written save file to clone (New Game on a blank backup RAM).
        tdir = OUT / 'template'
        env = dict(os.environ, SCD_SAVE_OUTPUT_DIR=str(tdir))
        subprocess.run(['bash', 'tools/test-save-emulator.sh', 'new'], cwd=ROOT, env=env, check=True,
                       stdout=subprocess.DEVNULL, timeout=600)
        template = (tdir / 'backup.bin').read_bytes()
        assert len(template) == 32768
        expected = {True: pictures(ROOT / 'cd/GOODEND.FMV'), False: pictures(ROOT / 'cd/BADEND.FMV')}
        for name in names:
            if name in STONES:
                report['cases'].append(stones_case(name, driver, template, find, trace, world, fade))
                save()
                continue
            era, stones, zones, good = CASES[name]
            cdir = OUT / name
            cdir.mkdir(parents=True, exist_ok=True)
            image = bytearray(32768)
            image[:64] = template[:64]
            insert(template, image, 2, 'SCDSATURN00', record(6, 2, era, stones, 0, zones))
            backup = cdir / 'backup-in.bin'
            backup.write_bytes(image)
            env = {k: v for k, v in os.environ.items() if not k.startswith('SCD_')}
            env.update(SCD_BACKUP_INPUT=str(backup), SCD_BACKUP_OUTPUT=str(cdir / 'backup-out.bin'))
            with (cdir / 'driver.log').open('w') as log:
                code = subprocess.run([driver, CORE, ROOT / 'dist/sonic-cd-saturn-prototype.cue', ROOT / 'assets/private',
                                       cdir, trace, world, fade], cwd=ROOT, env=env, stdout=log,
                                      stderr=subprocess.STDOUT, timeout=3600).returncode
            result = json.loads((cdir / 'ending.json').read_text())
            rec, fmv = result['last_record'], result['fmv']
            checks = {
                'driver_exit_0': code == 0,
                'mm3_continued': result['zone'] == 6 and result['act'] == 2,
                'ending_choice': bool(rec >> 16 & 1) == good,
                'movie_result_0': fmv[1] == 0x464D5644 and fmv[2] == 0,
                'movie_request': fmv[0] == 0x464D5600 | (2 if good else 3),
                'all_pictures_shown': fmv[5] == expected[good],
                'staff_roll_stepped': result['roll_steps'] > 0,
                'movie_audio': result['movie_audio_rms'] > 100,
                'title_after': bool(result['record'] >> 31 & 1) and result['title_after'] >= 600,
                'title_visible': result['title_lit_per_mille'] >= 100,
            }
            case = dict(name=name, era=era, stones=stones, zones=zones, expected_good=good,
                        expected_pictures=expected[good], result=result, checks=checks,
                        passed=all(checks.values()))
            report['cases'].append(case)
            save()
            print(f"{'PASS' if case['passed'] else 'FAIL'} {name}: good={rec >> 16 & 1} shown={fmv[5]}/{expected[good]} "
                  f"late_fields={fmv[7]} not_ready={fmv[11]} roll_steps={result['roll_steps']} "
                  f"rms={result['movie_audio_rms']:.0f} movie_frames={result['movie_end'] - result['movie_start']} "
                  f"title={checks['title_after']} title_lit={result['title_lit_per_mille']}", flush=True)
        report['passed'] = all(c['passed'] for c in report['cases']) and len(report['cases']) == len(names)
        report['status'] = 'passed' if report['passed'] else 'failed'
    except KeyboardInterrupt:
        report['status'] = 'interrupted'
        save()
        raise
    except Exception as error:
        report['status'] = 'failed'
        report['error'] = repr(error)
        save()
        raise
    save()
    print(f"{'PASS' if report['passed'] else 'FAIL'}: ending emulator {len(report['cases'])} case(s), report {path}")
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
