#!/usr/bin/env python3
"""CD++ preset player gate (docs/CDPP-PRESET-SPEC.md section 7), host only.

0. The SCDSATURNCF codec (tools/test_cdpp_settings.c): damaged or unknown = Classic.
1. Guard: tools/player_trace.c linked WITH src/player_plus.c and the preset at 0
   must equal the same trace linked without it (tools/test-player.sh's build),
   byte for byte. Classic traces are never regenerated here.
2. CD++ traces: tools/test_cdpp_trace.c rows must equal
   tests/routes/cdpp/traces/cdpp-trace.txt. --regenerate rewrites that file from
   the script (never by hand).
3. Feature checks on the rows: spin dash release speeds, rev decay, small-Sonic
   dash, air cap off vs Classic, air roll once per airtime, homing onto a badnik.
Does not prove Saturn behavior (tools/test_cdpp_routes.py) or hardware.
"""
import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/cdpp-player'
REFERENCE = ROOT / 'tests/routes/cdpp/traces/cdpp-trace.txt'
COMMON = ['-std=gnu11', '-O1', '-g', '-fsigned-char', '-fwrapv', '-fno-strict-aliasing', '-Wno-parentheses',
          '-Wno-unused-value', '-Isrc', '-Iassets/generated', '-Ibuild/probe-source', '-DR1', '-DR11A',
          '-fsanitize=address,undefined', '-fno-sanitize-recover=all']
NATIVE = ['tools/player_slot_model.c', 'src/act.c', 'src/player.c', 'src/sonic_animation.c', 'src/stage.c',
          'src/player_replay.c', 'src/objects.c', 'src/camera_v.c']
ORIGINAL = [f'build/probe-source/{n}.c' for n in ('interaction', 'player', 'dircol', 'fcol', 'etc', 'equ', 'movement')]


def run(cmd, **kw):
    return subprocess.run(list(map(str, cmd)), cwd=ROOT, check=True, **kw)


def build(name, sources):
    exe = OUT / name
    r = subprocess.run(list(map(str, ['clang', *COMMON, *sources, *NATIVE, *ORIGINAL, '-o', exe])), cwd=ROOT,
                       capture_output=True, text=True)
    if r.returncode:
        errors = [l for l in r.stderr.splitlines() if 'error' in l or 'ld:' in l or 'symbol' in l]
        sys.exit(f'FAIL: CD++ host build {name}:\n' + '\n'.join(errors[:20]))
    return exe


def sha(data):
    return hashlib.sha256(data).hexdigest()[:16]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--regenerate', action='store_true', help='rewrite the CD++ reference traces')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    run(['python3', 'tools/prepare_probe.py'])
    run(['python3', 'tools/prepare_player.py'], stdout=subprocess.DEVNULL)

    # 0. Settings file codec (missing/damaged/unknown = Classic).
    codec = OUT / 'settings_test'
    run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-g', '-Isrc', '-fsanitize=address,undefined',
         '-fno-sanitize-recover=all', 'tools/test_cdpp_settings.c', 'src/save.c', '-o', codec])
    settings = run([codec], capture_output=True, text=True).stdout.strip()
    guards = run([build('f4_contract', ['tools/test_cdpp_f4_contract.c'])],
                 capture_output=True, text=True).stdout.strip()

    # 1. Guard: preset code linked but off == compiled out.
    classic = run([build('trace_without_plus', ['tools/player_trace.c'])], capture_output=True).stdout
    linked = run([build('trace_with_plus', ['tools/player_trace.c', 'src/player_plus.c'])], capture_output=True).stdout
    if classic != linked:
        sys.exit('FAIL: CD++ guard: player_trace with src/player_plus.c (flags 0) differs from the build without it')

    # 2. CD++ traces.
    trace = run([build('cdpp_trace', ['tools/test_cdpp_trace.c', 'src/player_plus.c'])], capture_output=True).stdout
    if args.regenerate:
        REFERENCE.parent.mkdir(parents=True, exist_ok=True)
        REFERENCE.write_bytes(trace)
    elif not REFERENCE.exists() or REFERENCE.read_bytes() != trace:
        (OUT / 'cdpp-trace.txt').write_bytes(trace)
        sys.exit(f'FAIL: CD++ traces differ from {REFERENCE.relative_to(ROOT)} (new rows: build/cdpp-player/cdpp-trace.txt)')

    rows = {}
    for line in trace.decode().splitlines():
        f = line.split()
        rows.setdefault(f[0], []).append(dict(frame=int(f[1]), x=int(f[2]), y=int(f[3]), vx=int(f[4]), vy=int(f[5]),
                                              speed=int(f[6]), flags=int(f[7], 16), anim=int(f[8]),
                                              charge=int(f[9]), score=int(f[10])))

    def release(name):
        """Ground speed on the first update after the charge (rolling, moving)."""
        r = rows[name]
        charged = [i for i, s in enumerate(r) if s['flags'] & 4 and s['speed'] == 0 and not s['flags'] & 2]
        assert charged, (name, 'no charge')
        after = r[charged[-1] + 1]
        return abs(after['speed']), r[charged[-1]]['frame'] - r[charged[0]]['frame'] + 1

    found = {}
    # F1: 8 px/f + floor(spinrev)/2 (SPG). One press: 2048. Two: 2048 + 1*128 after decay.
    found['dash-0'] = release('dash-0')[0]
    found['dash-1'] = release('dash-1')[0]
    found['dash-4'] = release('dash-4')[0]
    found['dash-decay'] = release('dash-decay')[0]
    assert found['dash-0'] == 2048, found
    assert found['dash-1'] == 2048 + 128, found
    # Five presses one update apart: rev 0, 512, 993, 1444, 1868 (each update
    # first loses rev/32), two more decays to 1754: 2048 + 6*128.
    assert found['dash-4'] == 2816, found
    found['dash-max'] = release('dash-max')[0]
    assert found['dash-max'] == 3072, found
    assert 2048 <= found['dash-decay'] < found['dash-4'], found
    # Classic CD dash: the charge counter runs (actfree[0]) and no S2 rev pose holds speed 0.
    assert any(s['charge'] for s in rows['dash-classic']), 'Classic CD dash charge missing'
    assert not any(s['charge'] for s in rows['dash-4']), 'F1 used the CD dash charge'
    # F5: small Sonic gets the S2 dash only with MINIDASH.
    found['minidash'] = release('minidash')[0]
    assert found['minidash'] == 2048 + 128, found
    assert any(s['charge'] for s in rows['minidash-f1-only']), 'F1 alone changed small Sonic'
    # F2: Right held at 12 px/f in the air. Classic clamps to 6 px/f; CD++ keeps more.
    off, capped = rows['aircap-off'], rows['aircap-classic']
    found['aircap-off-vx'] = off[10]['vx']
    found['aircap-classic-vx'] = capped[10]['vx']
    assert capped[0]['vx'] <= 1536 and found['aircap-off-vx'] > 1536, found
    assert max(s['vx'] for s in rows['aircap-accel']) == 1536, 'F2 no longer accelerates to the cap'
    # F3: one curl per airtime; Classic stays uncurled.
    roll = rows['airroll']
    curled = [s['frame'] for s in roll if s['flags'] & 6 == 6]
    assert curled and curled[0] == 6, ('air roll', curled[:3])
    assert not any(s['flags'] & 6 == 6 for s in rows['airroll-classic']), 'Classic curled in the air'
    spring = rows['spring-roll']
    assert any(s['flags'] & 6 == 6 for s in spring), 'no air roll after the spring'
    found['airroll-frame'] = curled[0]
    # F4: homing destroys the badnik (score), Classic falls past it.
    found['homing-score'] = rows['homing'][-1]['score']
    found['homing-classic-score'] = rows['homing-classic'][-1]['score']
    assert found['homing-score'] > found['homing-classic-score'], found
    dash = rows['homing-dash']
    assert dash[4]['vx'] == 2048 and rows['homing'][4]['vx'] != 0, 'air dash / homing aim'
    # F4 yields to object control: a spring launch is not re-aimed at the badnik, and
    # an object impulse that keeps Sonic balled (set after update 5) stands at update 6.
    sp = rows['homing-spring']
    assert any(s['vy'] <= -3000 for s in sp) and min(s['y'] for s in sp) < 300, 'spring launch was re-aimed'
    imp = rows['homing-impulse']
    assert imp[6]['vx'] == -1536 and imp[6]['vy'] < -1900, ('homing overrode the impulse', imp[6])
    found['homing-impulse-vx'] = imp[6]['vx']
    for name in ('homing-rearm-10', 'homing-rearm-31'):
        r = rows[name]
        assert r[17]['score'] == 100 and r[18]['score'] == 100, (name, 'first defeat missing', r[17:19])
        assert r[18]['vx'] > 0 and r[18]['vy'] > 0, (name, 'second target was not acquired', r[18])
        assert r[-1]['score'] == 300 and r[18]['flags'] & 6 == 6, (name, 'second defeat/airtime missing', r[-1])
    no_edge = rows['homing-rearm-no-edge']
    assert no_edge[17]['score'] == 100 and no_edge[18]['vy'] < 0, ('second attack started without a press', no_edge[17:19])
    later_impulse = rows['homing-rearm-impulse']
    assert later_impulse[17]['score'] == 100 and later_impulse[18]['vx'] == -1536, (
        'defeat rearmed after a later object impulse', later_impulse[17:19])
    found['homing-rearm-flags'] = '10/31'
    print(f'PASS: CD++ player traces: guard identical ({len(classic.splitlines())} Classic rows, sha {sha(classic)}); '
          f'{len(trace.splitlines())} CD++ rows in {len(rows)} cases match '
          f'{REFERENCE.relative_to(ROOT)}{" (regenerated)" if args.regenerate else ""}; {settings}; '
          f'{guards}; '
          + ', '.join(f'{k}={v}' for k, v in found.items()))


if __name__ == '__main__':
    main()
