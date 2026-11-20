#!/usr/bin/env python3
"""Tidal Tempest music and sound effect requests: original vs native (host, table-driven).

Music: GAME4.C da_tbl row for round 4 and BOSS_4_2.C's sub_sync requests map
through LOADER2.C to CD tracks; the native cue for each (src/music_routes.h)
must select the same track (Japanese disc: Present 16, Good Future 18, Bad
Future 19; tools/prepare_japanese_music.py). The Past plays the PCM driver.
Drowning: PLAYSUB4.C plairset() calls bgmset(), which DUMMY.C stubs out, so the
original has no drowning-countdown music; plawamaster plays FM 223 (warning)
and 182 (drown). Effects: every soundset() id in an R4 source must resolve in
Tidal Tempest (resident SFX.PCM or its bank SFXZ2.PCM, tools/prepare_audio.py),
and 183 must be the FM spike, not Palmtree Panic's PCM giggle. Native ports
that exist are compared id for id; unported families are listed.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cc_audio import ROOT, src, ids, loader_track

R4 = 'build/audit/source/src/R4'
TMP = ROOT / 'build/tt-audio'

# family: (original files, native type). The R4 ports live in src/objects_tt_*.inc;
# a type no such file handles yet is reported as unported, and a handled type's
# original ids must all be requested somewhere in those files.
FAMILIES = {
    'amenbo': (['AMENBO.C'], 'SCD_OBJ_AMENBO'),
    'awa (bubbles)': (['AWA.C'], 'SCD_OBJ_AWA'),
    'tagameb': (['TAGAMEB4.C'], 'SCD_OBJ_TAGAMEB'),
    'harir4': (['HARIR4.C'], 'SCD_OBJ_HARIR4'),
    'sw4': (['SW4.C'], 'SCD_OBJ_SW4'),
    'rblk4': (['RBLK4.C'], 'SCD_OBJ_RBLK4'),
    'daid4': (['DAID4.C'], 'SCD_OBJ_DAID4'),
    'swgun4': (['SWGUN4.C'], 'SCD_OBJ_SWGUN4'),
    'et4': (['ET4.C'], 'SCD_OBJ_ET4'),
    'kuzure4': (['KUZURE4.C'], 'SCD_OBJ_KUZURE4'),
    'playsub4 (exit, air)': (['PLAYSUB4.C'], None),
    'coli4 (touch, bubble breath)': (['COLI4.C'], None),
    'boss (BOSS_4.C, BOSS_4_2.C)': (['BOSS_4.C', 'BOSS_4_2.C'], None),
}

# Original requests a ported R4 family does not make yet. Fixing one (or finding
# another) must update this table.
KNOWN_GAPS = {}


def music():
    game = src(f'{R4}/GAME4.C')
    table = re.search(r'da_tbl\[7\]\[4\] = \{(.*?)\};', game, re.S)[1]
    rows = [list(map(int, r)) for r in re.findall(r'\{\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\s*\}', table)]
    assert 'if (wD0 == 2)' in game and 'wD0 += generate_flag' in game
    past, present, bad, good = rows[2]
    boss = src(f'{R4}/BOSS_4_2.C')
    assert 'sub_sync(103)' in boss and 'BgmNo = 22' in boss and 'BgmNo = 23' in boss
    assert re.search(r'if \(generate_flag\) \{\s*BgmNo = 22;', boss)
    assert (bad, good) == (23, 22), 'BOSS_4_2.C returns to the da_tbl future tracks'
    # No drowning music: plairset's bgmset is DUMMY.C's empty stub.
    assert re.search(r'void bgmset\(short wD0\) \{\s*wD0 = 0;\s*\}', src('build/audit/source/src/DUMMY.C'))
    playsub = src(f'{R4}/PLAYSUB4.C')
    assert 'bgmset(wD0)' in playsub and 'soundset(223)' in playsub and 'soundset(182)' in playsub
    TMP.mkdir(parents=True, exist_ok=True)
    (TMP / 'slots.c').write_text('#include <stdio.h>\n#include "music_routes.h"\nint main(void){for(unsigned c=0;c<10;c++)printf("%u %u\\n",c,scd_music_slot(2,c));return 0;}\n')
    subprocess.run(['clang', '-Isrc', str(TMP / 'slots.c'), '-o', str(TMP / 'slots')], cwd=ROOT, check=True)
    slot = {int(a): int(b) for a, b in (l.split() for l in subprocess.check_output([str(TMP / 'slots')], text=True).splitlines())}
    jp = (ROOT / 'tools/prepare_japanese_music.py').read_text()
    assert 'enumerate((3,None,4,5,28,29,30,32,24,26))' in jp and 'first = 3+zone*3' in jp and '(first,None,first+1,first+2)' in jp
    retail = dict(enumerate((3, None, 4, 5, 28, 29, 30, 32, 24, 26)))
    for zone in range(1, 7):
        first = 3 + zone * 3
        for era, number in enumerate((first, None, first + 1, first + 2)):
            retail[10 + (zone - 1) * 4 + era] = number
    failures = []
    for name, request, cue in [('present', present, 0), ('good future', good, 2), ('bad future', bad, 3),
                               ('boss (BOSS_4_2.C)', 103, 8), ('after boss, good (BgmNo 22)', 22, 2),
                               ('after boss, bad (BgmNo 23)', 23, 3)]:
        want, have = loader_track(request), retail[slot[cue]]
        print(f'music {name:30} sub_sync {request:3} -> track {want:>3}   native cue {cue} slot {slot[cue]:2} -> track {have}')
        if want != have:
            failures.append(f'music {name}: original track {want}, native {have}')
    print(f'music past: PC sub_sync {past} -> PC track {loader_track(past)}; Sega CD/native: PCM driver (slot {slot[1]})')
    if retail[slot[1]] is not None:
        failures.append('music past: native past cue selects a CD track')
    return failures


def retail_drowning():
    """The Sega CD programs, not the PC port: in every R4 program plairset
    (cmpi.w #12,pl_air; bhi; d0=$82/$86/$87/$8C; jsr bgmset) calls a bare rts,
    and plawamaster plays only FM $DF (223) and $B6 (182). The FM driver's
    SongIndex is empty (scddisasm Sound Drivers/FM/Data.asm), so no track
    exists for a countdown either."""
    sys.path.insert(0, str(ROOT/'tools'))
    from extract_mmd import disc_files, ORIGIN
    disc = disc_files((ROOT/'build/retail/sonic.iso').read_bytes())
    for name in ('R41A', 'R41B', 'R41C', 'R41D', 'R42A', 'R42B', 'R42C', 'R42D', 'R43C', 'R43D'):
        program = disc[name+'__.MMD']
        call = re.findall(rb'\x0c\x79\x00\x0c(....)\x62.\x30\x3c\x00\x82.{30,40}?\x30\x3c\x00\x8c\x4e\xb9(....)\x33\xfc\x00\x1e', program, re.S)
        assert len(call) == 1, (name, 'plairset')
        target = int.from_bytes(call[0][1], 'big')-ORIGIN
        assert program[target:target+2] == b'\x4e\x75', (name, 'bgmset is not an empty function')
        assert re.search(rb'\x30\x3c\x00\xdf\x4e\xb9', program) and re.search(rb'\x30\x3c\x00\xb6\x4e\xb9', program), name
    data = (ROOT/'.deps/scddisasm/src/Sound Drivers/FM/Data.asm').read_text()
    assert re.search(r'SongIndex:\s*\n\s*;', data), 'FM driver song index is no longer empty'
    print('drowning: retail R41A-R43D plairset -> bgmset is rts; FM driver has no songs; countdown = FM 223 + 182 only')
    return []


def effects():
    report = json.loads((ROOT / 'build/feedback-source.json').read_text())
    samples = report['samples']
    assert any(b['file'] == 'SFXZ2.PCM' for b in report['banks'])
    resolved = {}
    for bank in ('SFX.PCM', 'SFXZ2.PCM'):  # bank first in src/audio.c; later wins here
        resolved.update({s['id']: s['name'] for s in samples if bank in s['banks']})
    audio = src('src/audio.c')
    assert 'zone==2?3' in audio, 'src/audio.c must load SFXZ2 (bank 3) for Tidal Tempest'
    failures, unported, gaps = [], [], set()
    # src/water.c holds the air/breath logic PLAYSUB4.C and AWA.C share.
    tt = ''.join(src(str(p.relative_to(ROOT))) for p in sorted((ROOT/'src').glob('objects_tt_*.inc'))+[ROOT/'src/water.c'] if p.exists())
    for name, (originals, native) in FAMILIES.items():
        text = ''.join(src(f'{R4}/{f}') for f in originals)
        want = ids(text, 'soundset') - {171}  # 171 stops the PCM loop (src/audio.c)
        missing = sorted(n for n in want if n not in resolved)
        if 183 in want and resolved.get(183) != 'spike-fm':
            missing.append(183)
        line = f'sfx {name:32} original {sorted(want)}'
        if missing:
            failures.append(f'sfx {name}: no Tidal Tempest sample for {missing}')
        if native and re.search(rf'\b{native}\b', tt):
            have = ids(tt, 'soundset')
            gaps |= {(name, n) for n in want - have}
            line += f' native {sorted(have & want)}'
        elif native:
            unported.append(name)
            line += ' (unported)'
        print(line)
    if gaps != set(KNOWN_GAPS):
        failures.append(f'native gaps changed: now {sorted(gaps)}, table {sorted(KNOWN_GAPS)}')
    for (name, n), why in sorted(KNOWN_GAPS.items()):
        print(f'gap {name}: {n}: {why}')
    if unported:
        print('unported families:', ', '.join(unported))
    return failures


def main():
    failures = music() + retail_drowning() + effects()
    for f in failures:
        print('FAIL', f)
    print(('PASS' if not failures else 'FAIL') + f': Tidal Tempest audio table ({len(FAMILIES)} families, 6 music routes, no drowning music)')
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
