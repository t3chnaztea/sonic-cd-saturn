#!/usr/bin/env python3
"""CD++ preset Saturn gates (docs/CDPP-PRESET-SPEC.md sections 6-7) on the built disc.

Cases (no argument: all):
  toggle   From an empty backup RAM, the title menu reaches RAM DATA; Right on its
           MODE row writes SCDSATURNCF = CD++ (flags 31). A cold boot of that
           backup reads the setting (save mailbox slot 11 bits 8-15 = 31); the
           same backup with a damaged file, and an empty one, boot Classic (0).
  routes   tests/routes/cdpp/*.txt pad scripts, one per move. Each is replayed on
           the native host twice: with the preset (expected positions) and Classic
           (to show the preset changes the run). The Saturn harness boots the CD++
           backup from 'toggle', enters the act from the level select, replays the
           pad and must match every CD++ host position; slot 11 must read 31 in
           gameplay. A per-move check on the host rows names the evidence.
Reports: build/cdpp-qa/report.json (disc sha256, inputs, per-case results).
Emulator evidence only: no hardware result.
"""
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/cdpp-qa'
DISC = ROOT / 'dist/sonic-cd-saturn-prototype.bin'
CUE = ROOT / 'dist/sonic-cd-saturn-prototype.cue'
ELF = ROOT / 'build/saturn/sonic-cd-saturn-prototype.elf'
CORE = ROOT / '.deps/beetle-saturn/mednafen_saturn_libretro.dylib'
ROUTES = ROOT / 'tests/routes/cdpp'
TAIL = 120
PRESET = 31


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


report = {'status': 'pending', 'passed': False, 'cases': {}, 'hardware_tested': False}


def save():
    (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n')


def fail(case, message):
    report['cases'][case] = {'passed': False, 'error': message}
    report['status'] = 'failed'
    save()
    sys.exit(f'FAIL: CD++ {case}: {message}')


# ---- Backup RAM files (Sega BUP layout, as tools/test_frontend_emulator.py) ----
def file_blocks(image, name):
    for b in range(2, 512):
        blk = image[b * 64:(b + 1) * 64]
        if blk[4:15] == name.encode() and blk[0] & 0x80:
            return b, struct.unpack('>I', blk[30:34])[0]
    return None, 0


def file_spans(image, name):
    first, size = file_blocks(image, name)
    if first is None:
        return None, 0
    payload, chain, idx, off = [], [first], 0, 34
    while True:
        if off == 64:
            idx += 1
            off = 4
        payload.append(chain[idx] * 64 + off)
        off += 1
        if len(payload) % 2 == 0:
            entry = image[payload[-2]] << 8 | image[payload[-1]]
            if entry == 0:
                break
            chain.append(entry)
    data = []
    while len(data) < size:
        if off == 64:
            idx += 1
            off = 4
        data.append(chain[idx] * 64 + off)
        off += 1
    return data, size


def read_file(image, name):
    offs, _ = file_spans(image, name)
    return None if offs is None else bytes(image[o] for o in offs)


def settings_record(preset, flags):
    d = b'SCDC' + bytes([1, 16, preset, flags]) + bytes(4)
    return d + struct.pack('>I', zlib.crc32(d))


# ---- Harnesses ----
def symbols():
    listing = subprocess.check_output([str(ROOT / '.toolchain/bin/sh-elf-nm'), str(ELF)], text=True)
    out = {}
    for row in listing.splitlines():
        p = row.split()
        if len(p) == 3:
            out[re.sub(r'\.lto_priv\.\d+$', '', p[2])] = p[0]
    return out


def frontend(name, script, syms, backup_in=None):
    folder = OUT / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'script.txt').write_text(script)
    env = {k: v for k, v in os.environ.items() if not k.startswith('SCD_')}
    env.update(SCD_SYMS=','.join(f'{k}={syms[v]}' for k, v in
                                 [('trace', '_scd_trace_mailbox'), ('world', '_scd_world_mailbox'), ('save', '_scd_save_mailbox')]),
               SCD_BACKUP_OUTPUT=str(folder / 'backup.bin'))
    if backup_in:
        env['SCD_BACKUP_INPUT'] = str(backup_in)
    args = [OUT / 'frontend_emulator_test', CORE, CUE, ROOT / 'assets/private', folder, folder / 'script.txt']
    with (folder / 'core.log').open('w') as err:
        r = subprocess.run(['nice', '-n', '20', *map(str, args)], env=env, cwd=ROOT, stdout=subprocess.PIPE,
                           stderr=err, text=True, timeout=900)
    (folder / 'results.log').write_text(r.stdout)
    peeks = {}
    for line in r.stdout.splitlines():
        m = re.match(r'frame=\d+ peek (\S+)((?: [0-9a-f]{8})+)$', line)
        if m:
            peeks[m.group(1)] = [int(x, 16) for x in m.group(2).split()]
    if r.returncode:
        fail(name, f'frontend harness status {r.returncode}')
    return peeks, folder / 'backup.bin'


TITLE = 'run 200\nuntil TITL 3000\nrun 240\nhold START 4\nrun 90\n'


def case_toggle(syms):
    # Find RAM DATA in the empty-backup menu (save mailbox word 10 = panel mode 1).
    for rights in range(4):
        script = TITLE + 'hold RIGHT 4\nrun 60\n' * rights + 'tap A\nrun 60\npeek before save 0 12\n' + \
            'tap RIGHT\nrun 30\npeek after save 0 12\nshot ram-data-cdpp\ntap B\nrun 120\n'
        peeks, backup = frontend(f'toggle-{rights}', script, syms)
        if peeks.get('before', [0] * 12)[10] == 1:
            break
    else:
        fail('toggle', 'RAM DATA panel not reached')
    before, after = peeks['before'], peeks['after']
    image = bytearray(backup.read_bytes())
    stored = read_file(image, 'SCDSATURNCF')
    if before[11] >> 8 & 255 != 0:
        fail('toggle', f'empty backup booted with setting {before[11]:#x}')
    if after[11] >> 8 & 255 != PRESET or stored != settings_record(1, PRESET):
        fail('toggle', f'MODE row: slot 11 {after[11]:#x}, file {stored!r}')
    cdpp = OUT / 'backup-cdpp.bin'
    cdpp.write_bytes(image)
    # Cold boot of the written backup, of a damaged copy, and of a missing file.
    damaged = bytearray(image)
    offs, _ = file_spans(damaged, 'SCDSATURNCF')
    damaged[offs[15]] ^= 0xff
    (OUT / 'backup-damaged.bin').write_bytes(damaged)
    boot = TITLE + 'peek boot save 0 12\n'
    results = {}
    for label, path in (('cdpp', cdpp), ('damaged', OUT / 'backup-damaged.bin'), ('empty', None)):
        p, _ = frontend(f'boot-{label}', boot, syms, path)
        results[label] = p['boot'][11] >> 8 & 255
    if results != {'cdpp': PRESET, 'damaged': 0, 'empty': 0}:
        fail('toggle', f'cold boot settings {results}')
    report['cases']['toggle'] = {'passed': True, 'menu_rights': rights, 'slot11_before': before[11],
                                 'slot11_after': after[11], 'file': stored.hex(), 'cold_boot': results,
                                 'backup_sha256': sha(cdpp)}
    save()
    return f'toggle: RAM DATA MODE writes SCDSATURNCF {stored[:8].hex()}..; cold boot CD++={results["cdpp"]}, ' \
           f'damaged={results["damaged"]}, missing={results["empty"]}'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cases = sys.argv[1:] or ['toggle', 'routes']
    report.update(disc_sha256=sha(DISC), elf_sha256=sha(ELF),
                  inputs={p: sha(ROOT / p) for p in ['tools/test_cdpp_routes.py', 'src/player_plus.c', 'src/player.c',
                                                     'src/save.c', 'src/save_saturn.c', 'src/save_view.inc']})
    save()
    subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-I.deps/beetle-saturn/libretro-common/include',
                    'tools/frontend_emulator_test.c', '-o', str(OUT / 'frontend_emulator_test')], cwd=ROOT, check=True)
    syms = symbols()
    lines = []
    if 'toggle' in cases or 'routes' in cases:
        lines.append(case_toggle(syms))
    if 'routes' in cases:
        lines += case_routes(syms)
    report.update(status='passed', passed=True)
    save()
    print('PASS: CD++ Saturn gates; ' + '; '.join(lines))


# ---- Routes ----
PPZ_NATIVE = ['src/title_card.c', 'src/world.c', 'src/act.c', 'src/player.c', 'src/camera_v.c',
              'src/sonic_animation.c', 'src/stage.c', 'src/boss.c', 'src/boss_r3.c', 'src/objects.c']
PPZ_ORIGINAL = ['boss_1', 'boss_3', 'playsp3', 'interaction', 'player', 'dircol', 'fcol', 'etc', 'equ', 'movement']
MM_NATIVE = ['src/title_card.c', 'src/world.c', 'src/act.c', 'src/player.c', 'src/camera_v.c', 'src/sonic_animation.c',
             'src/stage.c', 'src/boss.c', 'src/boss_r3.c', 'src/boss_r4.c', 'src/boss_r5.c', 'src/objects.c', 'src/water.c',
             'src/boss_r8.c']
MM_ORIGINAL = ['boss_1', 'boss_3', 'boss_4', 'boss_5', 'playsp3', 'interaction', 'player', 'dircol', 'fcol', 'etc', 'equ',
               'movement', 'boss_8', 'ending_8']
# name: (zone, act, era, setting flags, feature bit). The contrast host runs the same
# pad with flags & ~bit. minidash plays the stored Classic MM2A route to its shrink
# beam (sequence 4539, x 7036) with only MINIDASH set: before the shrink every
# update is Classic, so the Classic route still holds; then a small spin dash.
ROUTE_TABLE = {
    'spindash': ('ppz', 0, 'A', PRESET, 1),
    'aircap': ('ppz', 0, 'A', PRESET, 2),
    'airroll': ('ppz', 0, 'A', PRESET, 4),
    'homing': ('ppz', 0, 'A', PRESET, 8),
    'minidash': ('mm', 1, 'A', 16, 16),
}


def host(zone, flags):
    exe = OUT / 'hosts' / f'{zone}-{flags}'
    exe.parent.mkdir(parents=True, exist_ok=True)
    native, original, source, extra = ((PPZ_NATIVE, PPZ_ORIGINAL, 'tools/cc_campaign_search.c', []) if zone == 'ppz' else
                                       (MM_NATIVE, MM_ORIGINAL, 'tools/qq_route_search.c', ['-DROUTE_MM']))
    sources = [source, *native, 'src/player_plus.c', *[f'build/probe-source/{n}.c' for n in original]]
    stamp = hashlib.sha256(b''.join((ROOT / s).read_bytes() for s in sources) + str(flags).encode()).hexdigest()
    stamp_file = exe.parent / f'{exe.name}.sha'
    if not (exe.exists() and stamp_file.exists() and stamp_file.read_text() == stamp):
        subprocess.run(['nice', '-n', '20', 'clang', '-std=gnu11', '-O2', '-fsigned-char', '-fwrapv', '-fno-strict-aliasing',
                        '-Wno-parentheses', '-Wno-unused-value', '-Isrc', '-Iassets/generated', '-Ibuild/probe-source',
                        '-DR1', '-DR11A', f'-DSCD_PLUS_HOST_FLAGS={flags}', *extra, *sources, '-o', str(exe)],
                       cwd=ROOT, check=True, stderr=subprocess.DEVNULL)
        stamp_file.write_text(stamp)
    return exe


def replay(name, zone, act, era, flags, script, trace=False, objects=False):
    """Host replay: rows 'sequence pad x y' (trace: + 0 0 yspeed cddat mspeed xspeed xsub ysub angle)."""
    folder = OUT / 'routes' / name
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / f'host-{flags}{"-trace" if trace else ""}.txt'
    length = sum(int(l.split()[0]) for l in script.read_text().splitlines() if l.strip())
    env = {k: v for k, v in os.environ.items() if not k.startswith(('PPZ_', 'QQ_', 'CC_'))}
    if trace:
        env['PPZ_ROUTE_TRACE' if zone == 'ppz' else 'QQ_ROUTE_TRACE'] = '1'
    if objects:  # live actor slots per update (cc_campaign_search PPZ_ROUTE_OBJECTS)
        env['PPZ_ROUTE_OBJECTS'] = f'0:{length + 2}:{folder / f"objects-{flags}.txt"}'
    mode = f'p{act}:{era}' if zone == 'ppz' else f'{act}:{era}'
    with (folder / f'host-{flags}.log').open('w') as log:
        r = subprocess.run([str(host(zone, flags)), 'replay', mode, str(script), str(length), str(out)], cwd=ROOT, env=env,
                           stdout=log, stderr=log)
    rows = [list(map(int, l.split())) for l in out.read_text().splitlines()]
    # 1 is "Route incomplete" (no tally): these routes end mid-act. 3 is a death.
    if r.returncode not in (0, 1):
        fail('routes', f'{name}: host replay (flags {flags}) status {r.returncode}')
    return r.returncode, rows, out


def explosions(name, flags):
    """Actor slots that became an explosion (actno 24) in the host objects dump."""
    seen = set()
    for line in (OUT / 'routes' / name / f'objects-{flags}.txt').read_text().splitlines():
        f = line.split()
        if f[1] != 'camera' and f[2] == '24':
            seen.add(f[1])
    return len(seen)


def evidence(name, rows):
    """Per-move evidence from Saturn 'CC route' rows (seq, vblank, x, y, flags, ..., buttons at 8)."""
    moves = [(b[2] - a[2], b[3] - a[3], b[4], b[8]) for a, b in zip(rows, rows[1:])]
    if name in ('spindash', 'minidash'):
        # Ball on the ground at rest while Down is held, then rolling at >= 8 px/update.
        held = [i for i, (dx, dy, f, pad) in enumerate(moves) if f & 6 == 4 and dx == 0 and dy == 0 and pad & 32]
        assert held, 'no spin dash charge'
        burst = max(abs(m[0]) for m in moves[held[-1] + 1:held[-1] + 8])
        assert burst >= 8, ('release speed', burst)
        return dict(charge_updates=len(held), release_px=burst)
    if name == 'aircap':
        fast = [m for m in moves if m[2] & 2 and m[3] & (64 | 128) and abs(m[0]) > 6]
        assert fast, 'no airborne update above 6 px with a direction held'
        return dict(airborne_fast_updates=len(fast), max_air_px=max(abs(m[0]) for m in fast))
    if name == 'airroll':
        # The row after a jump press shows it (the harness samples before the update).
        curls = [rows[i + 1][0] for i in range(3, len(rows) - 1)
                 if rows[i][4] & 6 == 2 and rows[i + 1][4] & 6 == 6 and any(r[8] & 1 for r in rows[i - 3:i + 1])]
        assert curls, 'no air curl'
        return dict(air_curl_at=curls)
    return {}


def case_routes(syms):
    lines = []
    # Settings with MINIDASH only, written into the toggle's backup file.
    image = bytearray((OUT / 'backup-cdpp.bin').read_bytes())
    offs, size = file_spans(image, 'SCDSATURNCF')
    for o, v in zip(offs, settings_record(1, 16)):
        image[o] = v
    (OUT / 'backup-cdpp16.bin').write_bytes(image)
    exe = OUT / 'emulator'
    subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-I.deps/beetle-saturn/libretro-common/include',
                    'tools/emulator_test.c', '-o', str(exe)], cwd=ROOT, check=True)
    save_at = int(syms['_scd_save_mailbox'], 16)
    world_at = int(syms['_scd_world_mailbox'], 16)
    for name, (zone, act, era, flags, bit) in ROUTE_TABLE.items():
        script = ROUTES / f'{name}.txt'
        backup = OUT / ('backup-cdpp.bin' if flags == PRESET else f'backup-cdpp{flags}.bin')
        homing = name == 'homing'
        _, rows, pad = replay(name, zone, act, era, flags, script, objects=homing)
        _, contrast, _ = replay(name, zone, act, era, flags & ~bit, script, objects=homing)
        replay(name, zone, act, era, flags, script, trace=True)
        diverge = next((r[0] for r, c in zip(rows, contrast) if r[2:4] != c[2:4]), None)
        if diverge is None and len(contrast) == len(rows):
            fail('routes', f'{name}: the route does not use the move (flags {flags & ~bit} replay is identical)')
        folder = OUT / 'routes' / name
        last = rows[-1][0]
        env = {k: v for k, v in os.environ.items() if not k.startswith('SCD_')}
        env.update(SCD_ZONE='0' if zone == 'ppz' else '6', SCD_ZONE_ACT=str(act), SCD_ZONE_ERA=str('ABCD'.index(era)),
                   SCD_WORLD_MAILBOX=syms['_scd_world_mailbox'], SCD_ZONE_PAD_TRACE=str(pad),
                   SCD_ZONE_ROUTE_RETREAT='100', SCD_ZONE_ROUTE_UPDATES=str(len(rows) + TAIL),
                   SCD_ZONE_PAD_TAIL=str(TAIL), SCD_BACKUP_INPUT=str(backup),
                   SCD_ZONE_ROUTE_SHOTS=f'{rows[0][0] + 1},{last}',
                   SCD_ZONE_ROUTE_PEEK=f'{save_at + 44:x}:1,{world_at + 32:x}:1,{int(syms["_chibi_flag"], 16) & ~3:x}:1')
        command = [exe, CORE, CUE, ROOT / 'assets/private', folder, syms['_scd_trace_mailbox'],
                   syms['_scd_audio_mailbox'], 'zones']
        with (folder / 'results.log').open('w') as stdout, (folder / 'core.log').open('w') as stderr:
            result = subprocess.run(['nice', '-n', '20', *map(str, command)], cwd=ROOT, env=env, stdout=stdout,
                                    stderr=stderr, timeout=1800)
        core = (folder / 'core.log').read_text()
        mismatch = re.search(r'CC pad mismatch: .*', core)
        if result.returncode:
            fail('routes', f'{name}: ' + (mismatch[0] if mismatch else f'emulator exit {result.returncode}'))
        log = (folder / 'results.log').read_text()
        saturn = [list(map(int, l.split(': ', 1)[1].split())) for l in log.splitlines() if l.startswith('CC route: ')]
        for r in saturn:
            r[3] -= (r[3] >= 1 << 31) << 32
        assert len(saturn) == len(rows) + TAIL, (name, 'observation count', len(saturn))
        for s, h in zip(saturn, rows):
            assert [s[0], s[8], s[2], s[3]] == h, (name, 'position', s, h)
        peeks = [l.split(': ', 1)[1].split() for l in log.splitlines() if l.startswith('Route peek: ')]
        assert len(peeks) == 2, (name, 'peeks', peeks)
        slot11 = [int(p[1], 16) for p in peeks]
        defeated = int(peeks[-1][3], 16)
        chibi_word = int(syms['_chibi_flag'], 16)
        chibi = [int(p[5], 16) >> (8 * (3 - (chibi_word & 3))) & 255 for p in peeks]
        assert all(s & 255 == flags and s >> 8 & 255 == flags for s in slot11), (name, 'slot 11', slot11)
        found = evidence(name, saturn)
        if homing:
            host_kills, contrast_kills = explosions(name, flags), explosions(name, flags & ~bit)
            assert defeated >= 1 and host_kills > contrast_kills, ('homing defeated', defeated, host_kills, contrast_kills)
            found.update(defeated=defeated, contrast_defeated=contrast_kills)
        if name == 'minidash':
            assert chibi[-1] == 1, ('small Sonic at the end', chibi)
            found['small'] = chibi[-1]
        report['cases'][f'route-{name}'] = dict(passed=True, positions=len(rows), flags=flags, contrast_flags=flags & ~bit,
                                                contrast_diverges_at=diverge, slot11=slot11, script_sha256=sha(script),
                                                pad_sha256=sha(pad), **found)
        save()
        lines.append(f'{name}: {len(rows)} positions match (flags {flags}), contrast {flags & ~bit} diverges at {diverge}, '
                     + ', '.join(f'{k}={v}' for k, v in found.items()))
    return lines


if __name__ == '__main__':
    main()
