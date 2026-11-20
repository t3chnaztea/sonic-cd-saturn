#!/usr/bin/env python3
"""Collision Chaos music and sound effect requests: original vs native (host, table-driven).

Music: the PC reconstruction's GAME.C da_tbl row for round 3, BOSS_3.C, GOAL.C and
ITEM.C sub_sync requests map through LOADER2.C sub_sync to retail CD tracks; the
native cue for each (src/music_routes.h, src/boss.c, src/player.c, src/audio.c)
must select the same track of the Japanese disc (tools/prepare_japanese_music.py).
Effects: for every ported R3 actor family, the set of soundset() ids and PCM
sub_sync() ids in the original source must equal the ids the native actor
requests, and each id needs a captured sample (tools/prepare_audio.py). Known
gaps are listed with their reason; the test fails if the gap list changes.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PC = ROOT / 'build/audit/source/src'
TMP = ROOT / 'build/cc-audio'


def src(path):
    return re.sub(r'/\*.*?\*/', '', (ROOT / path).read_text(encoding='latin1'), flags=re.S)


def ids(text, call):
    return {int(n) for n in re.findall(rf'\b{call}\((\d+)\)', text)}


def loader_track(request):
    """LOADER2.C sub_sync: the CD track (or ('wave', n)) a request plays."""
    text = src('build/audit/source/src/LOADER2.C')
    for line in ('if (ReqNo >= 118 && ReqNo < 129)', 'WaveRequest(ReqNo - 43)', 'CDPlay(ReqNo - 12)',
                 'if ((ReqNo >= 15 && ReqNo <= 34) || (ReqNo >= 48 && ReqNo < 55))', 'CDPlay(ReqNo - 79)',
                 'else if (ReqNo >= 102 && ReqNo < 113)'):
        assert line in text, f'LOADER2.C sub_sync changed: {line}'
    if 118 <= request < 129:
        return ('wave', request - 43)
    if 15 <= request <= 34 or 48 <= request < 55:
        return request - 12
    if 102 <= request < 113:
        return request - 79
    raise AssertionError(f'no CD track for request {request}')


def music():
    game = src('build/audit/source/src/GAME.C')
    table = re.search(r'da_tbl\[7\]\[4\] = \{(.*?)\};', game, re.S)[1]
    rows = [list(map(int, r)) for r in re.findall(r'\{\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\s*\}', table)]
    assert 'if (wD0 == 2)' in game and 'wD0 += generate_flag' in game
    past, present, bad, good = rows[1]  # time_flag 0 past, 1 present, 2 future (+generate_flag)
    boss3 = src('build/audit/source/src/R3/BOSS_3.C')
    assert 'sub_sync(103)' in boss3 and 'if (!generate_flag) sub_sync(20)' in boss3 and 'else sub_sync(19)' in boss3
    assert (bad, good) == (20, 19), 'BOSS_3.C returns to the da_tbl future tracks'
    assert 'sub_sync(107)' in src('build/audit/source/src/GOAL.C')
    item = src('build/audit/source/src/ITEM.C')
    assert 'sub_sync(108)' in item and 'sub_sync(109)' in item
    # Japanese disc tracks per native (zone, cue) slot.
    jp = (ROOT / 'tools/prepare_japanese_music.py').read_text()
    assert 'enumerate((3,None,4,5,28,29,30,32,24,26))' in jp and 'first = 3+zone*3' in jp and '(first,None,first+1,first+2)' in jp
    fixed = (3, None, 4, 5, 28, 29, 30, 32, 24, 26)
    retail = {slot: number for slot, number in enumerate(fixed)}
    for zone in range(1, 7):
        first = 3 + zone * 3
        for era, number in enumerate((first, None, first + 1, first + 2)):
            retail[10 + (zone - 1) * 4 + era] = number
    TMP.mkdir(parents=True, exist_ok=True)
    (TMP / 'slots.c').write_text('#include <stdio.h>\n#include "music_routes.h"\nint main(void){for(unsigned c=0;c<10;c++)printf("%u %u\\n",c,scd_music_slot(1,c));return 0;}\n')
    subprocess.run(['clang', '-Isrc', str(TMP / 'slots.c'), '-o', str(TMP / 'slots')], cwd=ROOT, check=True)
    slot = {int(a): int(b) for a, b in (l.split() for l in subprocess.check_output([str(TMP / 'slots')], text=True).splitlines())}
    # Native cue sources.
    boss = src('src/boss.c'); main = src('src/main.c'); player = src('src/player.c'); audio = src('src/audio.c')
    assert 'if(request==103)music_request=SCD_BOSS_MUSIC_BOSS' in boss
    # Each linked boss returns to its zone track; later rounds may add requests.
    zone_return = re.search(r'else if\((.*?)\)music_request=SCD_BOSS_MUSIC_ZONE;', boss, re.S)
    assert zone_return and {19, 20, 22, 23, 25, 26, 28, 29} <= {
        int(v) for v in re.findall(r'request==(\d+)', zone_return[1])}
    assert 'if(boss_music==SCD_BOSS_MUSIC_BOSS)scd_audio_music(8);else if(boss_music==SCD_BOSS_MUSIC_ZONE)scd_audio_music(era);' in main
    assert 'void scd_audio_results(void){scd_audio_era(4);}' in audio
    assert 'plpower_m=1;music_event=6' in player and 'plpower_s=1;' in player and 'music_event=5' in player
    rows_out = [
        ('present', present, 0), ('good future', good, 2), ('bad future', bad, 3),
        ('boss (BOSS_3.C egg3dai_s jaba_s_chk)', 103, 8), ('results (GOAL.C)', 107, 4),
        ('speed shoes (ITEM.C)', 108, 5), ('invincible (ITEM.C)', 109, 6),
        ('after boss, good (BOSS_3.C sub_sync 19)', 19, 2), ('after boss, bad (sub_sync 20)', 20, 3)]
    failures = []
    for name, request, cue in rows_out:
        want, have = loader_track(request), retail[slot[cue]]
        print(f'music {name:42} sub_sync {request:3} -> track {want:>3}   native cue {cue} slot {slot[cue]:2} -> track {have}')
        if want != have:
            failures.append(f'music {name}: original track {want}, native {have}')
    # Past: the PC plays CD track 37; the Sega CD plays the zone's Past song from the
    # PCM driver (SNCBNK3B.BIN), which the native past cue (no CD track) also uses.
    print(f'music past: PC sub_sync {past} -> PC track {loader_track(past)}; Sega CD/native: PCM driver (slot {slot[1]}, no CD track)')
    if retail[slot[1]] is not None:
        failures.append('music past: native past cue selects a CD track')
    return failures


# family: (original files, native files, ids the native adds from shared code (reason))
FAMILIES = {
    'banpa (bumper rail)': (['R3/BANPA.C'], ['src/objects_banpa.inc'], {}),
    'bobin (pinball bumper)': (['R3/BOBIN.C'], ['src/objects_bobin.inc'], {171: 'RIDECHK.C ride_on_clr stops the PCM loop'}),
    'ene_kama (mantis)': (['R3/KAMA.C'], ['src/objects_kama.inc'], {}),
    'tentou (ladybird)': (['R3/TENTOU.C'], ['src/objects_tentou.inc'], {}),
    'pocket (pinball pocket)': (['R3/POCKET.C'], ['src/objects_pocket.inc'], {}),
    'et (generator)': (['R3/ET3.C'], ['src/objects_cc_generator.inc'], {}),
    'mecasnc/emie3/hari3x (Metal Sonic race)': (['R3/MECASNC.C'], ['src/objects_mecasnc3.inc'], {}),
    'movie (projector)': (['R3/MOVIE3.C'], ['src/objects.c'], None),  # shared file: subset check
    'traps (for3, harir3, frdr3, trapdr3, getdair3, gandair3, drumr3)': (['R3/TRAP_R3.C'], ['src/objects_cc_traps.inc', 'src/objects_for3.inc', 'src/objects_drumr3.inc'], {}),
    'ga (walker)': (['R3/GA3.C'], ['src/objects_ga.inc'], {}),
    'togeball': (['R3/TOGEBL3A.C', 'R3/TOGEBL3B.C', 'R3/TOGEBL3D.C'], ['src/objects_togeball.inc'], {}),
    'sikake33': (['R3/SIKAKE33.C'], ['src/objects_sikake33.inc'], {}),
    # 150 pcolnomal enemy defeat; 147 playdieset, the shared native death (PLAYER.C via interaction.c).
    'COLI3 touch (enemy defeat, death)': (['R3/COLI3.C'], ['src/objects_cc_enemy.inc', 'build/probe-source/interaction.c'], None),
    'boss (BOSS_3.C, GATE.C)': (['R3/BOSS_3.C', 'R3/GATE.C'], ['build/probe-source/boss_3.c'], None),
    'terrain bumper blocks (PLAYSP3.C, BOBINB.C)': (['R3/PLAYSP3.C', 'R3/BOBINB.C'], ['build/probe-source/playsp3.c'], None),
}
# Original requests the native build cannot play in Collision Chaos, with the reason.
# Changing this set (fixing one, or finding another) must update the table.
KNOWN_GAPS = {}
UNPORTED = {}


def effects():
    # What Collision Chaos plays for each request: its bank (SFXZ1.PCM) first, then the
    # resident effects (src/audio.c), from tools/prepare_audio.py's report.
    samples = json.loads((ROOT / 'build/feedback-source.json').read_text())['samples']
    resolved = {}
    for bank in ('SFX.PCM', 'SFXZ1.PCM'):
        resolved.update({s['id']: s['name'] for s in samples if bank in s['banks']})
    captured = set(resolved)
    wrong_bank = set()
    # Round-specific request: CC's harir3 plays FM $B7, not Palmtree Panic's PCM giggle.
    if resolved.get(183) != 'spike-fm':
        wrong_bank.add(183)
    failures, gaps = [], set()
    for tool in ('tools/prepare_boss_r3.py', 'tools/prepare_playsp3.py'):
        subprocess.run([sys.executable, tool], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    for name, (originals, natives, extra) in FAMILIES.items():
        text = ''.join(src(f'build/audit/source/src/{f}') for f in originals)
        # BOBIN.C passes its PCM request through a variable: d0 = 127; sub_sync(d0).
        pcm = ids(text, 'sub_sync') | {int(n) for n in re.findall(r'd0 = (\d+);\s*sub_sync\(d0\)', text)}
        want = ids(text, 'soundset') | {n for n in pcm if 118 <= n < 129 or n == 146}
        native_text = ''.join(src(f) for f in natives)
        # Generated original code keeps its sub_sync PCM requests (src/boss.c maps 146 to 1146).
        have = ids(native_text, 'soundset') | {n for n in ids(native_text, 'sub_sync') if 118 <= n < 129 or n == 146}
        if extra is None:
            missing, surplus = want - have, set()
        else:
            missing, surplus = want - have, have - want - set(extra)
        print(f'sfx {name:60} original {sorted(want)} native {sorted(have & want)}{" +" + str(sorted(extra)) if extra else ""}')
        if missing or surplus:
            failures.append(f'sfx {name}: original-only {sorted(missing)}, native-only {sorted(surplus)}')
        for n in want:
            request = 1000 + n if n == 146 else n
            if request not in captured or request in wrong_bank:
                gaps.add((name, n))
    if gaps != set(KNOWN_GAPS):
        failures.append(f'sample gaps changed: now {sorted(gaps)}, table {sorted(KNOWN_GAPS)}')
    for (name, n), why in sorted(KNOWN_GAPS.items()):
        print(f'gap {name}: {n}: {why}')
    for path, why in UNPORTED.items():
        print(f'unported {path}: {why}')
    return failures


def main():
    failures = music() + effects()
    for f in failures:
        print('FAIL', f)
    print(('PASS' if not failures else 'FAIL') + f': Collision Chaos audio table ({len(FAMILIES)} actor families, 9 music routes, {len(KNOWN_GAPS)} known sample gaps)')
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
