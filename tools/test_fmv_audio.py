#!/usr/bin/env python3
"""Controller-only opening PCM and subsequent SFX/gameplay regression.

Run under a mount/deadline guard. One emulator at a time. Each route cold-boots
the supplied image. The sound-test cheat selects isolated jump and ring effects
before entering normal gameplay. This supplements the MEM4MB host gate; Beetle
does not emulate that memory-mode failure. No console acceptance is implied.
"""
import argparse
import array
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def pcm(path):
    data = Path(path).read_bytes()
    samples = array.array('h', data)
    assert len(samples) >= 44100, 'PCM recording is too short'
    peak = max(map(abs, samples))
    assert peak > 200, 'PCM is silent or nearly silent'
    clipped = sum(abs(v) >= 32767 for v in samples)
    assert clipped / len(samples) < .001, 'PCM clips'
    return dict(sha256=hashlib.sha256(data).hexdigest(), samples=len(samples),
                rms=math.sqrt(sum(v*v for v in samples)/len(samples)),
                peak=peak, clipped=clipped)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--cue', type=Path, default=ROOT/'dist/sonic-cd-saturn-prototype.cue')
    parser.add_argument('--elf', type=Path, default=ROOT/'build/saturn/sonic-cd-saturn-prototype.elf')
    parser.add_argument('--effect-reference', type=Path, required=True, help='Preserved isolated jump/ring baseline directory')
    args = parser.parse_args()
    out = args.out.resolve()
    assert out.is_relative_to(ROOT/'build') and not out.exists()
    out.mkdir(parents=True)
    core = ROOT/'.deps/beetle-saturn/mednafen_saturn_libretro.dylib'
    report = dict(status='pending', hardware_tested=False, routes={}, inputs={
        str(p.relative_to(ROOT)): sha(p) for p in [Path(__file__), ROOT/'tools/frontend_emulator_test.c',
        ROOT/'src/fmv_saturn.c', ROOT/'src/audio.c', core, args.elf, args.cue]})
    # The build's generated CUE has a single FILE. Refuse an ambiguous binding.
    files = re.findall(r'^FILE "([^"]+)" BINARY$', args.cue.read_text(), re.M)
    assert len(files) == 1, 'Expected single-file candidate CUE'
    report['disc_sha256'] = sha(args.cue.parent/files[0])
    report['effect_reference'] = {name: pcm(args.effect_reference/(name+'.raw')) for name in ('effect_jump','effect_ring')}
    opening_samples = json.loads((ROOT/'build/fmv/convert.json').read_text())['files']['OPN.FMV']['pcm_samples']
    report['inputs']['build/fmv/convert.json'] = sha(ROOT/'build/fmv/convert.json')
    def save():
        (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    save()
    try:
        harness = out/'frontend_emulator_test'
        subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                        '-I.deps/beetle-saturn/libretro-common/include', 'tools/frontend_emulator_test.c',
                        '-o', str(harness)], cwd=ROOT, check=True)
        nm = subprocess.check_output([str(ROOT/'.toolchain/bin/sh-elf-nm'), str(args.elf)], text=True)
        symbols = {r.split()[2]: r.split()[0] for r in nm.splitlines() if len(r.split()) == 3}
        syms = 'trace='+symbols['_scd_trace_mailbox']+',st='+symbols['_fe_st']+',fmv=20243000'
        title = 'run 200\nuntil TITL 3000\nrun 240\n'
        sound = ('tap DOWN\ntap DOWN\ntap DOWN\ntap LEFT\ntap RIGHT\ntap A\nuntil FEND 900\nrun 20\n'
                 'hold DOWN 16\nrun 4\npeekb jump_selection st 0 10\nhold A 4\ncapture effect_jump 120\n'
                 'hold DOWN 24\nrun 4\npeekb ring_selection st 0 10\nhold A 4\ncapture effect_ring 120\n'
                 'tap START\nuntil TITL 900\nrun 240\nhold START 4\nrun 90\ntap A\nuntil SCD2 2400\n'
                 'run 120\ncapture gameplay 180\nfail_unless_magic SCD2\n')
        movies = dict(control='', skip='run 2260\npeek movie_before fmv 0 14\ncapture opening 180\npeek movie_after fmv 0 14\nhold START 4\nuntil TITL 1800\npeek movie_return fmv 0 14\nrun 240\n',
                      natural='run 2260\npeek movie_before fmv 0 14\ncapture opening 180\npeek movie_after fmv 0 14\nuntil TITL 12000\npeek movie_return fmv 0 14\nrun 240\n')
        for i, (name, movie) in enumerate(movies.items()):
            if i:
                time.sleep(60)
            folder = out/name
            folder.mkdir()
            script = folder/'script.txt'
            script.write_text(title+movie+sound)
            env = os.environ.copy()
            env.pop('SCD_BACKUP_INPUT', None)
            env.update(SCD_SYMS=syms, SCD_BACKUP_OUTPUT=str(folder/'backup.bin'))
            with (folder/'core.log').open('w') as err, (folder/'results.log').open('w') as log:
                r = subprocess.run(['nice', '-n', '20', str(harness), str(core), str(args.cue.resolve()),
                                    str(ROOT/'assets/private'), str(folder), str(script)],
                                   cwd=ROOT, env=env, stdout=log, stderr=err, timeout=900)
            assert r.returncode == 0, f'{name}: harness failed: {r.returncode}'
            log = (folder/'results.log').read_text()
            selections = {key: [int(v,16) for v in values.split()] for key,values in
                          re.findall(r'peekb (\w+)([ 0-9a-f]+)\n',log)}
            assert selections['jump_selection'][:2] == [0,2], 'Wrong jump selection'
            assert selections['ring_selection'][:2] == [0,5], 'Wrong ring selection'
            row = {p.stem: pcm(p) for p in folder.glob('*.raw')}
            assert {'effect_jump','effect_ring','gameplay'} <= row.keys()
            for effect in ('effect_jump','effect_ring'):
                reference = report['effect_reference'][effect]
                ratio = row[effect]['rms']/reference['rms']
                assert .95 <= ratio <= 1.05, f'{name}: {effect} differs from isolated reference: {ratio}'
                assert abs(row[effect]['peak']-reference['peak']) <= max(2, reference['peak']*.02)
                row[effect]['reference_rms_ratio'] = ratio
            if name != 'control':
                assert 'opening' in row
                peeks = {key: [int(v,16) for v in values.split()] for key,values in
                         re.findall(r'peek (\w+)([ 0-9a-f]+)\n',log)}
                before, after, returned = (peeks['movie_'+p] for p in ('before','after','return'))
                assert 0 < before[4] < after[4] < opening_samples, 'Capture was not during opening playback'
                assert 0 < before[5] < after[5], 'Opening pictures did not advance'
                assert before[8] < after[8] and not after[13] and not returned[13], 'Opening stalled or had a CD error'
                if name == 'skip':
                    assert after[4] <= returned[4] < opening_samples//2, 'Opening was not skipped early'
                else:
                    assert returned[4] >= opening_samples, 'Opening did not complete naturally'
                row['movie_state'] = dict(before=before[3:14],after=after[3:14],returned=returned[3:14])
                for effect in ('effect_jump', 'effect_ring'):
                    ratio = row[effect]['rms']/report['routes']['control'][effect]['rms']
                    assert .95 <= ratio <= 1.05, f'{name}: altered {effect} output: {ratio}'
                    row[effect]['cold_rms_ratio'] = ratio
            report['routes'][name] = row
            save()
            print(f'PASS: FMV audio {name}: isolated jump/ring and subsequent gameplay audible; no clipping', flush=True)
        report['status'] = 'passed'
        save()
        print('PASS: FMV PCM, early skip, natural completion and post-movie effects/gameplay')
    except BaseException as error:
        report.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed', error=repr(error))
        save()
        raise


if __name__ == '__main__':
    main()
