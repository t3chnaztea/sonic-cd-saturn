#!/usr/bin/env python3
"""Collision Chaos Act 3 boss probe on the Saturn build (both futures).

Runs tools/emulator_test.c zones mode with SCD_CC3_BOSS_ACTWK: the level select
enters R33C or R33D, a fixture places Sonic at the boss (it writes actwk[0]; it
is not a controller route), and the probe requires egg3dai_l to spawn, take
three BOSS_3.C hits, raise bossflag at the shaft top, and the capsule, results
and next-zone handoff to follow. Emulator evidence only; not a hardware result.
"""
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def boss_hit_audio(run, log):
    """The recorded game audio after each hit must contain effect 172 (the CC bank's
    boss hit): its normalized correlation with the bank sample must be at least 0.4
    and 0.15 above the best match in the second before the first hit (CD music
    only; measured 0.23-0.25 against 0.45-0.65 after hits)."""
    import array
    raw = array.array('h', (run / 'audio.raw').read_bytes())
    mono = [(raw[i] + raw[i + 1] + raw[i + 2] + raw[i + 3] + raw[i + 4] + raw[i + 5] + raw[i + 6] + raw[i + 7]) / 8
            for i in range(0, len(raw) - 7, 8)]  # 44.1 kHz stereo -> 11025 Hz mono
    ref = [v for v in array.array('b', (ROOT / 'build/retail/fx172.pcm').read_bytes())]
    ref = ref[next(i for i, v in enumerate(ref) if abs(v) > 1):][:2048]
    norm = sum(v * v for v in ref) ** 0.5

    def best(start, length):
        top = 0.0
        for at in range(max(0, start), min(len(mono) - len(ref), start + length), 4):
            seg = mono[at:at + len(ref)]
            energy = sum(v * v for v in seg) ** 0.5
            if energy:
                top = max(top, abs(sum(a * b for a, b in zip(seg, ref))) / (energy * norm))
        return top
    hits = [int(n) // 8 for n in re.findall(r'^CC3 boss hit \d+ at t=\d+ audio_sample=(\d+)$', log, re.M)]
    if len(hits) != 3:
        return dict(passed=False, hits=len(hits))
    baseline = best(hits[0] - 11025, 11025 - 2048)
    scores = [round(best(h, 5512), 3) for h in hits]
    return dict(passed=all(s >= 0.4 and s - baseline >= 0.15 for s in scores), scores=scores, baseline=round(baseline, 3))


def main():
    out = ROOT / 'build/cc3-boss'
    out.mkdir(parents=True, exist_ok=True)
    exe = out / 'emulator'
    subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-I.deps/beetle-saturn/libretro-common/include',
                    'tools/emulator_test.c', '-o', exe], cwd=ROOT, check=True)
    listing = subprocess.check_output([ROOT / '.toolchain/bin/sh-elf-nm', ROOT / 'build/saturn/sonic-cd-saturn-prototype.elf'], text=True)
    symbols = {r.split()[2]: r.split()[0] for r in listing.splitlines() if len(r.split()) == 3}
    report = {'image_sha256': hashlib.sha256((ROOT / 'dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest(), 'runs': {}}
    ok = True
    # 'C-muted': negative control. The game drops request 172 (src/audio.c
    # scd_audio_test_mute); the boss run must still pass and the hit-sound check must fail.
    for era in ('C', 'D', 'C-muted'):
        run = out / era
        run.mkdir(exist_ok=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith('SCD_')}
        env.update(SCD_ZONE='1', SCD_ZONE_ACT='2', SCD_ZONE_ERA=str('ABCD'.index(era[0])),
                   SCD_WORLD_MAILBOX=symbols['_scd_world_mailbox'], SCD_CC3_BOSS_ACTWK=symbols['_actwk'],
                   SCD_CC3_BOSS_FLAG=symbols['_bossflag'])
        if era == 'C-muted':
            env['SCD_CC3_MUTE'] = symbols['_scd_audio_test_mute']
        command = [exe, ROOT / '.deps/beetle-saturn/mednafen_saturn_libretro.dylib', ROOT / 'dist/sonic-cd-saturn-prototype.cue',
                   ROOT / 'assets/private', run, symbols['_scd_trace_mailbox'], symbols['_scd_audio_mailbox'], 'zones']
        with (run / 'results.log').open('w') as stdout, (run / 'core.log').open('w') as stderr:
            result = subprocess.run(list(map(str, command)), cwd=ROOT, env=env, stdout=stdout, stderr=stderr, timeout=900)
        log = (run / 'results.log').read_text()
        passed = re.search(r'^CC3 boss probe passed: (.*)$', log, re.M)
        failure = [l for l in (run / 'core.log').read_text().splitlines() if l.startswith('CC3 boss')]
        hit_audio = boss_hit_audio(run, log)
        expected = era != 'C-muted'
        report['runs'][era] = dict(exit_code=result.returncode, passed=bool(passed) and result.returncode == 0 and hit_audio['passed'] == expected,
                                   summary=passed[1] if passed else None, failure=failure[-1] if failure else None, boss_hit_audio=hit_audio)
        print(f"R33{era}: boss hit sound (BOSS_3.C soundset 172, expected {'present' if expected else 'absent'}) {hit_audio}")
        ok &= report['runs'][era]['passed']
        print(f"R33{era}: {'PASS' if report['runs'][era]['passed'] else 'FAIL'} {passed[1] if passed else (failure[-1] if failure else 'exit ' + str(result.returncode))}")
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(('PASS' if ok else 'FAIL') + ': CC3 boss emulator probe, build/cc3-boss/report.json')
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
