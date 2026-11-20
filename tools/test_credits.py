#!/usr/bin/env python3
"""Credits ("Thank You" screen) host parity: src/credits.c against the PC
TITLE/THANKS sources, frame for frame, over every scenario in
tools/credits_test.c.

Steps:
  1. tools/credits_assets.py: tables from the PC source, checked against the
     retail THANKS_M.MMD on the user-supplied disc.
  2. Prepare the 11 THANKS files (plus TYPES.H and the COMMON headers) in
     build/credits/reference.  Only includes, the PC actor-offset casts
     (byte 62 -> free[4]) and two signed left shifts (ETC_M.C random) change.
  3. Build both sides with ASan/UBSan, run each scenario, compare the logs.
  4. Compile src/credits.c for SH-2.
  5. The Sega CD mode (SCD_CREDITS_SEGA_CD) against the retail THANKS_M.MMD run in the
     pinned Genesis Plus GX core (tools/credits_retail.py): with no input (fade in to
     the end timer's fade out, the whole program) and with Start (press at retail frame
     1500, the quit taken on call 1378). Every call's sprite table (linked entries),
     colours and name tiles must equal the retail VDP state at frame 124 + call, and
     its 64 actors the retail work RAM ($FF9200) at frame 123 + call; the last picture
     must show in the frame the retail program returns in.
Writes build/credits/report.json.
"""
import json, os, pathlib, re, struct, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / '.deps/soniccd/src'
OUT = ROOT / 'build/credits'
REF = OUT / 'reference/src'
THANKS = ['ACT.C', 'ACT.H', 'BM_M.C', 'BM_M.H', 'CHRSET.C', 'CHRSET.H', 'DATA_SP.C', 'ETC_M.C', 'ETC_M.H',
          'FADE.C', 'FADE.H', 'GAME.C', 'GAME.H', 'IO.C', 'IO.H', 'SPM.C', 'SPM.H', 'SPRMOVE.C', 'SPRMOVE.H',
          'THANKS_TYPES.H']
REWRITES = [  # (file, pattern, replacement, expected count)
    ('SPRMOVE.C', r'\(\(char\*\)pActwk\)\[62\]', '((signed char*)pActwk->free)[4]', 9),
    ('SPRMOVE.C', r'\(\(short\*\)pActwk\)\[31\]', '(*(short*)&pActwk->free[4])', 5),
    ('ETC_M.C', r'd1\.l <<= (\d);', r'd1.l = (int)((unsigned)d1.l << \1);', 2),
]
ACTOR_FIELDS = ['act_no', 'exe_no', 'x', 'y', 'x_speed', 'y_speed', 'x_accel', 'y_accel', 'x_offset', 'y_offset',
                'sin_cnt', 'tm_cnt', 'spr_timer', 'pat_no', 'cgbase', 'pattern', 'spr_flg', 'act_flg', 'end_x',
                'end_y', 'x_wide', 'y_wide'] + [f'free{i}' for i in range(8)]
TIMERS = ['end_timer', 'heart_tm', 'animal_timer', 'posetimer', 'coltimer', 'colorno', 'coltimer2', 'colorno2',
          'prg_mode', 'swdata1', 'animal_flg', 'poseno', 'quit_flg', 'ranum', 'greatest']
SAN = ['-fsanitize=address,undefined', '-fno-sanitize-recover=all']


def label(i):
    for name, size in [('actor', 66 * 30), ('pribuf', 256), ('sprite', 320), ('overflow', 1), ('palette', 192),
                       ('sounds', 9), ('actset_tm', 8), ('timers', 15), ('plane', 4096)]:
        if i < size:
            if name == 'actor':
                return f'actwk[{i // 30}].{ACTOR_FIELDS[i % 30]}'
            if name == 'timers':
                return TIMERS[i]
            if name == 'sprite':
                return f'sprite[{i // 4}].{"x y index flags".split()[i % 4]}'
            return f'{name}[{i}]'
        i -= size
    return f'extra[{i}]'


def prepare():
    for sub in ('', 'TITLE/COMMON', 'TITLE/THANKS'):
        (REF / sub).mkdir(parents=True, exist_ok=True)
    files = [('TYPES.H', 'TYPES.H'), ('IMPFUNCS.H', 'IMPFUNCS.H')]
    files += [(f'TITLE/COMMON/{p.name}', f'TITLE/COMMON/{p.name}') for p in (UPSTREAM / 'TITLE/COMMON').glob('*.H')]
    files += [(f'TITLE/THANKS/{n}', f'TITLE/THANKS/{n}') for n in THANKS]
    for src, dst in files:
        content = (UPSTREAM / src).read_text()
        content = re.sub(r'(#include\s+"[^"]+)"', lambda m: m[1].replace('\\', '/') + '"', content)
        content = content.replace('  union {\n    sprite_data spra[20];\n    sprite_data spr[];\n  };',
                                  '  sprite_data spra[20];')
        for name, pattern, replacement, expected in REWRITES:
            if src.endswith(name):
                content, count = re.subn(pattern, replacement, content)
                if count != expected:
                    raise SystemExit(f'{name}: {count} rewrites of {pattern}, expected {expected}')
        (REF / dst).write_text(content)


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=ROOT, check=True, **kw)


def build():
    thanks = REF / 'TITLE/THANKS'
    common = ['clang', '-std=gnu11', '-O1', '-g', '-fsigned-char', '-fno-strict-aliasing'] + SAN
    inc = ['-Isrc', '-Iassets/generated', '-Itools', f'-I{thanks}']
    objects = []
    ref_flags = ['-fwrapv', '-w', '-Drandom=thanks_random', '-Disdigit=thanks_isdigit', '-Disupper=thanks_isupper',
                 '-Dsign=thanks_sign']
    (OUT / 'obj').mkdir(parents=True, exist_ok=True)
    for source in [thanks / n for n in THANKS if n.endswith('.C')] + [ROOT / 'tools/credits_reference.c']:
        obj = OUT / 'obj' / (source.stem.lower() + '.o')
        run(common + ref_flags + inc + ['-x', 'c', '-c', str(source), '-o', str(obj)])
        objects.append(str(obj))
    run(common + ['-Wall', '-Wextra', '-Werror', '-DSCD_CREDITS_REFERENCE'] + inc +
        ['tools/credits_test.c'] + objects + ['-o', str(OUT / 'credits_reference')])
    run(['clang', '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror', '-Wconversion', '-Wno-sign-conversion'] + SAN +
        inc + ['tools/credits_test.c', 'src/credits.c', '-o', str(OUT / 'credits_native')])
    sh2 = ROOT / '.toolchain/bin/sh-elf-gcc'
    if sh2.exists():
        run([str(sh2), '-std=gnu11', '-m2', '-mb', '-O2', '-Wall', '-Wextra', '-Werror', '-ffreestanding',
             '-Isrc', '-Iassets/generated', '-c', 'src/credits.c', '-o', str(OUT / 'credits.sh2.o')])
        size = subprocess.check_output([str(ROOT / '.toolchain/bin/sh-elf-size'), str(OUT / 'credits.sh2.o')], text=True)
        return size.splitlines()[-1].split()[:4]
    return None


def first_difference(scenario, frame):
    dumps = []
    for side in ('native', 'reference'):
        out = subprocess.check_output([str(OUT / f'credits_{side}'), str(scenario), 'dump', str(frame)], text=True)
        dumps.append([int(line.split()[1]) for line in out.splitlines()])
    return [(label(i), a, b) for i, (a, b) in enumerate(zip(*dumps)) if a != b][:16]


RETAIL_CASES = {'timer': None, 'start': 1500}   # retail Start frame; the quit is call 1378
FIRST_SHOWN, FIRST_RAM = 124, 123              # retail frames of call 0's picture and state


def retail_chain(sat):
    """Linked sprite table entries from link 0: Y (10 bits), size, attribute, X (9 bits)."""
    out, link = [], 0
    for _ in range(80):
        y, size_link, attr, x = struct.unpack_from('>HHHH', sat, link * 8)
        out.append((y & 0x3FF, size_link >> 8 & 15, attr, x & 0x1FF))
        link = size_link & 0x7F
        if not link:
            break
    return tuple(out)


def actor_words(data):
    """An actor in the retail layout; PAT_ADR and the words past free[] are not compared."""
    w = list(struct.unpack('>32H', data))
    w[21] = w[22] = w[30] = w[31] = 0
    return w


def sega_cd_case(name, press):
    args = ['python3', 'tools/credits_retail.py', '--frames', '11200', '--tag', f'host-{name}']
    if press is not None:
        args += ['--press', str(press)]
    run(args, stdout=subprocess.DEVNULL)
    rows = [json.loads(line) for line in (OUT / 'retail' / f'host-{name}.jsonl').open()]
    blobs = json.loads((OUT / 'retail' / f'host-{name}-blobs.json').read_text())
    quit_call = -1 if press is None else press - 122
    out = subprocess.run([str(OUT / 'credits_native'), 'md', str(len(rows)), str(quit_call)], cwd=ROOT,
                         env=dict(os.environ, CREDITS_MD_ACTORS='1'), capture_output=True, text=True, check=True).stdout
    md = [line.split() for line in out.splitlines() if line.startswith('md ')]
    actors = [line.split()[2:] for line in out.splitlines() if line.startswith('act ')]
    bad = {'sprites': [], 'colours': [], 'names': [], 'actors': []}
    for call, (fields, acts) in enumerate(zip(md, actors)):
        if FIRST_SHOWN + call >= len(rows):
            bad['sprites'].append(call)
            continue
        shown, state = rows[FIRST_SHOWN + call], rows[FIRST_RAM + call]
        sat = bytes.fromhex(fields[3]) if fields[3] != '-' else b''
        chain = tuple((y & 0x3FF, sl >> 8 & 15, a, x & 0x1FF) for y, sl, a, x in struct.iter_unpack('>HHHH', sat))
        retail = retail_chain(bytes.fromhex(blobs[shown['sat']]))
        # No sprites: the retail table is one blank entry.
        if chain != retail and not (not chain and retail == ((0, 0, 0, 0),)):
            bad['sprites'].append(call)
        if bytes.fromhex(fields[4]) != bytes.fromhex(blobs[shown['cram']]):
            bad['colours'].append(call)
        plane = struct.unpack('>2048H', bytes.fromhex(blobs[shown['plane_a']]))
        names = struct.unpack('>24H', bytes.fromhex(fields[5]))
        if any(names[k] and names[k] != plane[(12 + k // 6) * 64 + 17 + k % 6] for k in range(24)):
            bad['names'].append(call)
        ram = bytes.fromhex(blobs[state['actors']])
        for i in range(64):
            r, n = actor_words(ram[i * 64:i * 64 + 64]), actor_words(bytes.fromhex(acts[i]))
            # free[4..5]: the PC's little-endian short; its byte alias is the 68000's high byte.
            if r[28] == ((n[28] >> 8) | (n[28] & 255) << 8) & 0xFFFF:
                n[28] = r[28]
            if r != n:
                bad['actors'].append(call)
                break
    ended = bool(md) and md[-1][2] == '-1'
    # tools/credits_retail.py stops 30 frames after the program returned to IPX, in the
    # frame that shows its last fade step.
    returned = len(rows) - 30
    last_shown = FIRST_SHOWN + len(md) - 1
    result = {'calls': len(md), 'retail_frames': len(rows), 'quit_call': quit_call,
              **{k: len(v) for k, v in bad.items()}, 'first': {k: v[:4] for k, v in bad.items() if v}}
    failures = [f'{name}: {len(v)} calls differ in {k} (first {v[0]})' for k, v in bad.items() if v]
    if not ended or last_shown != returned:
        failures.append(f'{name}: last picture at retail frame {last_shown}, the program returned at {returned}')
    return result, failures


def main():
    run(['python3', 'tools/credits_assets.py'])
    assets = json.loads((OUT / 'assets-report.json').read_text())
    prepare()
    sh2_size = build()
    count = int(subprocess.check_output([str(OUT / 'credits_native')], text=True))
    report = {'scenarios': [], 'retail_tables': assets.get('retail_match'), 'sh2_size_text_data_bss_dec': sh2_size}
    coverage, frames_total = {}, 0
    for scenario in range(count):
        native = subprocess.run([str(OUT / 'credits_native'), str(scenario)], cwd=ROOT, capture_output=True, text=True, check=True)
        reference = subprocess.run([str(OUT / 'credits_reference'), str(scenario)], cwd=ROOT, capture_output=True, text=True, check=True)
        (OUT / f'native-{scenario}.log').write_text(native.stdout)
        (OUT / f'reference-{scenario}.log').write_text(reference.stdout)
        if native.stdout != reference.stdout:
            a, b = native.stdout.splitlines(), reference.stdout.splitlines()
            line = next(i for i, (x, y) in enumerate(zip(a + [''], b + [''])) if x != y)
            frame = int((a[line] if line < len(a) else b[line]).split()[0]) if line < min(len(a), len(b)) else line
            print(f'FAIL: credits parity scenario {scenario} frame {frame}')
            for item in first_difference(scenario, frame):
                print('  %s native=%d reference=%d' % item)
            report['passed'] = False
            (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
            return 1
        summary = native.stdout.splitlines()[-1]
        frames = int(re.search(r'frames=(\d+)', summary)[1])
        frames_total += frames
        report['scenarios'].append(summary)
        for act, exe, n in re.findall(r'coverage (\d+) (\d+) (\d+)', native.stderr):
            coverage.setdefault(int(act), set()).add(int(exe))
    names = {1: 'sonic', 2: 'amy', 3: 'metal', 4: 'flicky', 5: 'pocky', 6: 'ricky', 7: 'heart', 8: 'inco',
             9: 'hato', 10: 'sheep', 11: 'pecky'}
    report['coverage'] = {names[a]: sorted(e) for a, e in sorted(coverage.items())}
    report['frames'] = frames_total
    missing = [names[a] for a in names if a not in coverage]
    report['sega_cd'], sega_failures = {}, []
    if assets.get('retail_match') is not None:
        for name, press in RETAIL_CASES.items():
            report['sega_cd'][name], failures = sega_cd_case(name, press)
            sega_failures += failures
    else:
        sega_failures.append('no retail disc: the Sega CD mode was not compared')
    report['passed'] = not missing and assets.get('retail_match') is not False and not sega_failures
    (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    for a in (1, 2, 3):
        print(f'{names[a]} states seen: {sorted(coverage.get(a, ()))}')
    if missing:
        print('FAIL: credits parity: actors never spawned:', missing)
        return 1
    if sega_failures:
        for f in sega_failures:
            print('  ' + f)
        print('FAIL: credits Sega CD mode differs from the retail THANKS_M.MMD run')
        return 1
    calls = sum(c['calls'] for c in report['sega_cd'].values())
    print(f'PASS: credits parity {count} scenarios, {frames_total} frames identical; '
          f'retail tables {assets.get("retail_match")}; Sega CD mode = retail THANKS_M.MMD on {calls} calls '
          f'(sprites, colours, names, actors); SH-2 {sh2_size}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
