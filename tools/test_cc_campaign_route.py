#!/usr/bin/env python3
"""Replay a CC1 campaign pad route from an earned, cold-booted Continue save.

The input is the native host's ``sequence buttons x y`` pad trace. This
verifier does not construct a save, change gameplay RAM, or imply hardware
acceptance. Its derived emulator harness only changes the menu navigation:
Continue replaces the zones harness's level-select entry.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / '.deps/beetle-saturn/mednafen_saturn_libretro.dylib'
DISC = ROOT / 'dist/sonic-cd-saturn-prototype.bin'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def records(log, label):
    return [list(map(int, line.split(': ', 1)[1].split()))
            for line in log.splitlines() if line.startswith(label + ': ')]


def campaign_harness(out, observe, addresses, menu=2):
    """menu: title menu entry to take (2 CONTINUE on a valid save, 1 NEW GAME)."""
    out.mkdir(parents=True, exist_ok=True)
    source = (ROOT / 'tools/emulator_test.c').read_text()
    start = source.index('            /* Wait for title mode 2, the finished title with its menu, as the')
    end = source.index('            }else if(phase==3){', start) + len('            }else if(phase==3){')
    old = source[start:end]
    assert 'zones-select-' in old and 'phase=3;play=frame;' in old
    replacement = '''            /* Campaign replay: use the real title Continue menu. The BIOS
               BackupRAM is loaded before the first frame by backup_open(). */
            if(phase==0){
                if(magic==0x53434432){phase=3;play=frame;}
                else if(magic==0x5449544c){
                    unsigned state=ram_word(ram,mailbox+8);
                    unsigned selection=(state>>16)&255;
                    if((state&255)==2 && !selection && frame%8<4)
                        button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_START;
                    else if(state&256){
                        unsigned target=MENU_TARGET; /* 2 Continue on a valid save, 1 New Game. */
                        if(frame%8<4)button_mask=1u<<(selection<target?
                            RETRO_DEVICE_ID_JOYPAD_RIGHT:selection>target?
                            RETRO_DEVICE_ID_JOYPAD_LEFT:RETRO_DEVICE_ID_JOYPAD_B);
                    }
                }
                if(frame>9000){fprintf(stderr,"Campaign Continue timed out\\n");return 2;}
            }else if(phase==3){'''
    assert source.count(old) == 1
    path = out / 'campaign_emulator.c'
    derived = source[:start] + replacement.replace('MENU_TARGET', str(menu)) + source[end:]
    declaration = 'seen=0,phase=0,wait=0,go=0,play=0'
    assert derived.count(declaration) == 1
    derived = derived.replace(declaration, 'phase=0,play=0')
    if observe:
        mismatch = 'fprintf(stderr,"CC pad mismatch: sequence=%u actual=%u,%d expected=%d,%d\\n",sequence,x,y,expected->x,expected->y);return 2;'
        assert derived.count(mismatch) == 1
        derived = derived.replace(mismatch, mismatch.replace('return 2;', '/* observation only */'))
        route_line = 'printf("CC route: %u %u %u %u %u %u %u %u %u %u %u %u\\n",sequence,frame,x,ram_word(ram,world_mailbox+72),flags,standing,ram_word(ram,world_mailbox+84),ram_word(ram,mailbox+88),route_buttons,zone,act,era);'
        assert derived.count(route_line) == 1
        derived = derived.replace(route_line, route_line +
                                  '\n                        printf("CC velocity: %u %u\\n",sequence,ram_word(ram,world_mailbox+47*4));'
                                  '\n                        printf("CC debug: %u %u %u %u %u %d\\n",sequence,ram_word(ram,mailbox+16*4),ram_word(ram,mailbox+18*4),x-(ram_word(ram,world_mailbox+50*4)>>16),ram_word(ram,world_mailbox+8*4),(int)ram_word(ram,world_mailbox+72)-(int16_t)ram_word(ram,world_mailbox+50*4));'
                                  '\n                        if(sequence==2597 || sequence==2598)for(unsigned slot_i=0;slot_i<96;slot_i++){'
                                  '\n                            size_t p_at=0x100000+0x7e4cc+slot_i*36;'
                                  '\n                            size_t a_at=0x100000+0x5aa5c+(slot_i+1)*68;'
                                  '\n                            if(a_at+20>size || p_at+36>size)return 2;'
                                  '\n                            unsigned slot_type=ram[p_at+7];if(!slot_type)continue;'
                                  '\n                            unsigned origin=ram_word(ram,p_at)>>16;'
                                  '\n                            unsigned age=(uint16_t)ram_word(ram,p_at);'
                                  '\n                            int ax=(int16_t)(ram_word(ram,a_at+8)>>16);'
                                  '\n                            int ay=(int16_t)(ram_word(ram,a_at+12)>>16);'
                                  '\n                            int avx=(int16_t)(ram_word(ram,a_at+16)>>16);'
                                  '\n                            int avy=(int16_t)ram_word(ram,a_at+16);'
                                  '\n                            printf("CC slot: %u %u %u %u %u %d %d %d %d %u %u %u %u\\n",sequence,slot_i,origin,slot_type,age,ax,ay,avx,avy,ram[a_at+32],ram[a_at+36],ram[a_at+0],ram[a_at+34]);'
                                  '\n                        }')
        pool_address = next(int(value, 16) & 0xfffff for key, value in addresses.items()
                            if key == '_pool' or key.startswith('_pool.lto_priv.'))
        actor_address = int(addresses['_actwk'], 16) & 0xfffff
        assert derived.count('0x7e4cc') == derived.count('0x5aa5c') == 1
        derived = derived.replace('0x7e4cc', f'0x{pool_address:x}')
        derived = derived.replace('0x5aa5c', f'0x{actor_address:x}')
    path.write_text(derived)
    exe = out / 'campaign_emulator'
    subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                    '-I.deps/beetle-saturn/libretro-common/include', '-Itools', str(path),
                    '-o', str(exe)], cwd=ROOT, check=True)
    return exe


def symbols():
    listing = subprocess.check_output([ROOT / '.toolchain/bin/sh-elf-nm',
                                      ROOT / 'build/saturn/sonic-cd-saturn-prototype.elf'], text=True)
    return {parts[2]: parts[0] for row in listing.splitlines()
            if len(parts := row.split()) == 3}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pad', type=Path, required=True, help='host trace: sequence buttons x y')
    parser.add_argument('--backup', type=Path,
                        help='override the earned backup named by the checkpoint report')
    parser.add_argument('--checkpoint-report', type=Path,
                        default=ROOT / 'build/cc1/generator/campaign-checkpoint-report.json',
                        help='proof binding the earned backup and disc')
    parser.add_argument('--output', type=Path,
                        default=ROOT / 'build/cc1/generator/campaign-controller-target')
    parser.add_argument('--tail', type=int, default=0, help='neutral observations after trace, at most 600')
    parser.add_argument('--require', choices=['replay', 'past', 'generator', 'present', 'good-future', 'act2', 'continue', 'act3'],
                        default='replay', help='last milestone that must be proven')
    parser.add_argument('--observe', action='store_true',
                        help='diagnostic only: continue after host/target position mismatch')
    parser.add_argument('--act3-era', type=int, choices=(2, 3), default=3,
                        help='act3 only: expected Act 3 future (2 Good needs an Act 2 generator too)')
    parser.add_argument('--allow-late', action='store_true',
                        help='record late gameplay intervals without failing; the report stays unpassed')
    args = parser.parse_args()
    checkpoint_report = args.checkpoint_report.resolve()
    checkpoint = json.loads(checkpoint_report.read_text())
    backup_source = args.backup or Path(checkpoint.get('backup_path', ROOT / 'build/cc1/generator/campaign-sequence.bin'))
    pad, backup, out = (p.resolve() for p in (args.pad, backup_source, args.output))
    assert pad.is_file() and backup.is_file() and len(backup.read_bytes()) == 32768
    assert 0 <= args.tail <= 600
    assert out != ROOT and not out.is_relative_to(ROOT / 'dist')
    out.mkdir(parents=True, exist_ok=True)
    expected = [list(map(int, row.split())) for row in pad.read_text().splitlines()]
    assert len(expected) >= 200 and len(expected) + args.tail <= 48000
    assert all(len(row) == 4 and row[0] == i + 2 and row[1] >= 0
               for i, row in enumerate(expected)), 'pad format or sequence'
    disc_hash = digest(DISC)
    backup_hash = digest(backup)
    assert checkpoint['passed'] and checkpoint['disc_sha256'] == disc_hash
    assert checkpoint['backup_sha256'] == backup_hash
    assert [checkpoint[key] for key in ('generation', 'zone', 'act', 'era')] == [4, 1, 0, 0]
    prior_good_zones = checkpoint.get('saved_flags', 0) & 0x00ffff00
    source_hash = digest(ROOT / 'tools/emulator_test.c')
    addresses = symbols()
    exe = campaign_harness(out, args.observe, addresses)
    env = {k: v for k, v in os.environ.items() if not k.startswith('SCD_')}
    env.update(SCD_ZONE='1', SCD_ZONE_ACT='0', SCD_ZONE_ERA='0',
               SCD_WORLD_MAILBOX=addresses['_scd_world_mailbox'],
               SCD_ZONE_ART_MAILBOX=addresses['_scd_zone_art_mailbox'],
               SCD_ZONE_PAD_TRACE=str(pad), SCD_ZONE_ROUTE_RETREAT='100',
               SCD_ZONE_ROUTE_UPDATES=str(len(expected) + args.tail),
               SCD_ZONE_PAD_TAIL=str(args.tail),
               SCD_SAVE_MAILBOX=addresses['_scd_save_mailbox'],
               SCD_BACKUP_INPUT=str(backup), SCD_BACKUP_OUTPUT=str(out / 'backup-after.bin'))
    command = [exe, CORE, ROOT / 'dist/sonic-cd-saturn-prototype.cue',
               ROOT / 'assets/private', out,
               addresses['_scd_trace_mailbox'], addresses['_scd_audio_mailbox'], 'zones']
    with (out / 'results.log').open('w') as stdout, (out / 'core.log').open('w') as stderr:
        subprocess.run(list(map(str, command)), cwd=ROOT, env=env, stdout=stdout,
                       stderr=stderr, check=True, timeout=900)
    log = (out / 'results.log').read_text()
    rows = records(log, 'CC route')
    future = records(log, 'CC future')
    warps = records(log, 'CC warp')
    music = records(log, 'CC music')
    saves = records(log, 'CC save')
    results = records(log, 'CC results')
    n = len(expected)
    for row in rows:  # Y is printed as an unsigned 32-bit word.
        row[3] -= (row[3] >= 1 << 31) << 32
    assert len(rows) == len(future) == len(warps) == len(music) == len(saves) == len(results) == n + args.tail
    for row, world, warp, tune, save, result in zip(rows, future, warps, music, saves, results):
        assert row[0] == world[0] == warp[0] == tune[0] == save[0] == result[0]
        assert row[9] == 1 and row[6] == 0, ('zone/respawn', row)
    mismatches = [(row[0], row[2:4], reference[2:4]) for row, reference in zip(rows, expected)
                  if [row[0], row[8], row[2], row[3]] != reference]
    assert args.observe or not mismatches, ('host/target pad or position mismatch', mismatches[:1])
    assert rows[0][10:12] == [0, 0], 'Continue must start CC1 Present'
    assert saves[0][2:7] == [1, 0, 4, 1, prior_good_zones], 'expected earned generation-4 CC1 Present save'
    assert saves[0][7:10] == [1, prior_good_zones, 1], 'expected live CC1 campaign save session'
    assert all(tune[1:4] == [12, 12, 3] for tune in music[100:min(300, n)]), 'Japanese Present music'
    assert all(b[0] == a[0] + 1 for a, b in zip(rows, rows[1:])), 'lost observation'
    transitions = [(a, b) for a, b in zip(rows, rows[1:]) if a[9:12] != b[9:12]]
    warp_by_sequence = {row[0]: row[1] for row in warps}
    handoffs = [(a, b) for a, b in zip(rows, rows[1:]) if warp_by_sequence[b[0]] == 240]
    late = [(a[0], b[0], b[1]-a[1]) for a, b in zip(rows, rows[1:])
            if a[9:12] == b[9:12] and warp_by_sequence[b[0]] != 240 and b[1]-a[1] != 1]
    if not args.observe and not args.allow_late:
        assert not late, ('late gameplay interval', late[:1])
    for a, b in transitions:
        if a[10] == b[10]:
            assert b[1] - a[1] >= 240, 'era changed without natural warp cutscene'
    past = any(a[11] == 0 and b[11] == 1 and a[10] == b[10] == 0 for a, b in transitions)
    # Act 1 events only; Act 2 has its own generator flag.
    n1 = next((i for i, row in enumerate(rows) if row[10] != 0), n)
    n1 = min(n1, n)
    generator_at = next((i for i, world in enumerate(future[:n1]) if world[1]), None)
    generator = generator_at is not None
    if generator:
        assert all(world[1] == 0 for world in future[:generator_at])
        assert all(world[1] == 1 for world in future[generator_at:n1])
        assert future[generator_at][4] - future[generator_at - 1][4] == 1500
        assert rows[generator_at][11] == 1, 'generator destroyed outside Past'
    good_arrivals = [(a, b) for a, b in transitions if a[11] == 0 and b[11] == 2
                     and a[10] == b[10] == 0]
    returns = [(a, b) for a, b in transitions if a[11] == 1 and b[11] == 0
               and a[10] == b[10] == 0 and generator and b[0] > rows[generator_at][0]]
    returned = bool(returns)
    if returned:
        assert past and generator and all(world[1] == 1 for world in future[generator_at:n1])
        assert music[returns[0][1][0]-2][1] == 12, 'Present music was not requested on arrival'
    settled = music[returns[0][1][0]-2+100:returns[0][1][0]-2+200] if returned else []
    present = len(settled) == 100 and all(tune[1:4] == [12, 12, 3] for tune in settled)
    act2 = any(a[10] == 0 and b[10] == 1 for a, b in transitions)
    act3_handoffs = [(a, b) for a, b in transitions if a[10] == 1 and b[10] == 2]
    act3 = bool(act3_handoffs)
    if good_arrivals:
        assert present and all(world[1] == 1 for world in future[generator_at:n1])
        assert music[good_arrivals[0][1][0]-2][1] == 14, 'Good Future music not requested on arrival'
    good_music = music[good_arrivals[0][1][0]-2+100:good_arrivals[0][1][0]-2+200] if good_arrivals else []
    good = len(good_music) == 100 and all(tune[1:4] == [14, 14, 3] for tune in good_music)
    if act2:
        stage3 = 0x201 | args.act3_era << 16
        good3 = 3 if args.act3_era == 2 else 1
        assert good and rows[-1][10:12] == ([2, args.act3_era] if act3 else [1, 0])
        assert saves[-1][7:10] == ([stage3, prior_good_zones | good3, 1] if act3 else
                                  [0x101, prior_good_zones | 1, 1]), 'earned Good Future and live save session'
        act_handoff = next((a, b) for a, b in transitions if a[10] == 0 and b[10] == 1)
        assert future[act_handoff[0][0]-2][4] == future[act_handoff[1][0]-2][4]
        assert future[act_handoff[1][0]-2][4] > future[0][4], 'Act 1 score was not carried into Act 2'
        phases = list(dict.fromkeys(result[1] for result in results if result[0] < act_handoff[1][0]))
        assert phases == list(range(7)), 'complete Act 1 sign/tally sequence'
        act2_rows = [i for i, row in enumerate(rows) if row[10] == 1]
        assert all(results[i][3] == 0 for i in act2_rows[:(len(act2_rows) if not act3 else 30)]), 'Act 2 rings reset'
        if not act3:
            assert all(tune[1:4] == [12, 12, 3] for tune in music[-100:]), 'Act 2 Japanese track'
    act3_facts = None
    if act3:
        # Good Future Act 3 needs both acts' generators (original rule).
        a, b = act3_handoffs[0]
        assert len(act3_handoffs) == 1 and b[11] == args.act3_era, ('Act 3 era', b)
        act2_events = [world[1] for world, row in zip(future, rows) if row[10] == 1]
        act2_generator = next((i for i, row in enumerate(rows) if row[10] == 1 and future[i][1]), None)
        if args.act3_era == 3:
            assert not any(act2_events), 'Act 2 future event'
        else:
            assert act2_generator is not None and act2_events[0] == 0, 'Act 2 generator'
            assert rows[act2_generator][11] == 1, 'Act 2 generator destroyed outside Past'
            assert future[act2_generator][4] - future[act2_generator - 1][4] == 1500
            assert all(world[1] for world, row in zip(future[act2_generator:], rows[act2_generator:]) if row[10] == 1)
        before, after = future[a[0]-2][4], future[b[0]-2][4]
        assert before == after, 'score changed across the Act 3 handoff'
        act2_start = future[act3_handoffs[0][0][0]-2][4]
        act2_first = future[next(i for i, row in enumerate(rows) if row[10] == 1)][4]
        assert act2_start > act2_first, 'Act 2 score was not carried into Act 3'
        act3_rows = [i for i, row in enumerate(rows) if row[10] == 2]
        assert all(results[i][3] == 0 for i in act3_rows), 'Act 3 rings reset'
        act2_phases = list(dict.fromkeys(results[i][1] for i in act2_rows))
        assert act2_phases[-7:] == list(range(7)), ('complete Act 2 sign/tally sequence', act2_phases)
        # save mailbox word 6 is saved good-act flags in its low byte and
        # the v2 curSpecStage in its high byte.  The campaign may enter a
        # special stage on its way here, so the cursor is no longer always 0.
        # Preserve and cold-reload that exact cursor below; only its valid
        # range is fixed at this route layer.
        saved_flags=saves[-1][6]
        assert (saves[-1][4:6] == [6, stage3]
                and saved_flags & 0xffffff == (prior_good_zones | good3)
                and saved_flags >> 24 < 7), ('Act 3 checkpoint', saves[-1])
        act3_facts = dict(handoff_sequence=b[0], era=b[11], carried_score=after,
                          act2_generator_sequence=rows[act2_generator][0] if act2_generator is not None else None,
                          act2_tally_phases=act2_phases, save=saves[-1][1:],
                          settled_music=music[-1][1:4], time_stones=saves[-1][7] >> 24)
    milestones = dict(replay=not mismatches, past=past, generator=generator,
                      present=present, good_future=good, act2=act2, act3=act3)
    if args.require == 'act3' and act3 and not args.observe:
        assert digest(out / 'backup-after.bin') != backup_hash, 'backup RAM did not advance'
        cold = out / 'cold-continue'
        env2 = {k: v for k, v in os.environ.items() if not k.startswith('SCD_')}
        env2.update(SCD_BACKUP_INPUT=str(out / 'backup-after.bin'),
                    SCD_SAVE_OUTPUT_DIR=str(cold))
        with (out / 'cold-continue.log').open('w') as output:
            subprocess.run(['bash', 'tools/test-save-emulator.sh', 'continue'], cwd=ROOT,
                           env=env2, stdout=output, stderr=subprocess.STDOUT,
                           check=True, timeout=600)
        saved = json.loads((cold / 'save.json').read_text())
        act3_facts['cold_continue_mailbox'] = saved['mailbox'][:10]
        act3_facts['cold_continue_track'] = saved['trace'][23] & 0xfff
        assert saved['mailbox'][:10] == [0x53415645, 0, 1, 0, 6, stage3, saved_flags,
                                       stage3, prior_good_zones | good3, 1], saved['mailbox'][:10]
        assert (cold / 'backup.bin').read_bytes() == (out / 'backup-after.bin').read_bytes()
    if args.require == 'continue' and act2 and not args.observe:
        assert saves[-1][4:7] == [5, 0x101, prior_good_zones | 1], 'Act 2 checkpoint was not committed to backup RAM'
        assert digest(out / 'backup-after.bin') != backup_hash, 'backup RAM did not advance'
        cold = out / 'cold-continue'
        env2 = {k: v for k, v in os.environ.items() if not k.startswith('SCD_')}
        env2.update(SCD_BACKUP_INPUT=str(out / 'backup-after.bin'),
                    SCD_SAVE_OUTPUT_DIR=str(cold))
        with (out / 'cold-continue.log').open('w') as output:
            subprocess.run(['bash', 'tools/test-save-emulator.sh', 'continue'], cwd=ROOT,
                           env=env2, stdout=output, stderr=subprocess.STDOUT,
                           check=True, timeout=600)
        saved = json.loads((cold / 'save.json').read_text())
        assert saved['mailbox'][:10] == [0x53415645, 0, 1, 0, 5, 0x101, prior_good_zones | 1,
                                       0x101, prior_good_zones | 1, 1]
        assert saved['trace'][23] & 0xfff == 0x30c, 'cold Continue must play Japanese track 12'
        assert (cold / 'backup.bin').read_bytes() == (out / 'backup-after.bin').read_bytes()
        milestones['continue'] = True
    required_observed = milestones.get(args.require.replace('-', '_'), False)
    if not args.observe:
        assert required_observed, f'missing required {args.require} milestone'
    assert digest(DISC) == disc_hash and digest(backup) == backup_hash
    assert digest(ROOT / 'tools/emulator_test.c') == source_hash
    report = dict(passed=not args.observe and not mismatches and required_observed and not late,
                  late_gameplay_detail=late[:16], act3=act3_facts,
                  target_milestone_observed=required_observed,
                  disc_sha256=disc_hash, earned_backup_sha256=backup_hash,
                  pad_sha256=digest(pad), observations=len(rows), matched_positions=n-len(mismatches),
                  neutral_tail_observations=args.tail, present_track_12_settled=present,
                  good_future_track_14_settled=good,
                  position_mismatches=len(mismatches), first_position_mismatch=mismatches[0] if mismatches else None,
                  diagnostic_observation_only=args.observe,
                  milestones=milestones, generator_sequence=rows[generator_at][0] if generator else None,
                  stage_transitions=[dict(sequence=b[0], before=a[9:12], after=b[9:12])
                                     for a, b in transitions],
                  warp_handoffs=[dict(sequence=b[0], vblanks=b[1]-a[1]) for a, b in handoffs],
                  late_gameplay_intervals=len(late),
                  act2_carried_score=future[-1][4] if act2 else None,
                  backup_after_sha256=digest(out / 'backup-after.bin'),
                  hardware_tested=False,
                  limits=('Diagnostic only: host/target positions differ; target event observations are not acceptance.' if mismatches else 'Host/target position and event replay from earned campaign Continue; physical Saturn and independent original-console parity remain separate.'))
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('CC1 campaign replay:', n-len(mismatches), 'of', n, 'matched positions;', milestones)


if __name__ == '__main__':
    main()
