# V0.083 prerelease

Console acceptance is pending. This audio prerelease passed software validation.

## Audio repair

Opening movie startup now writes the SCSP control register explicitly with
512 KB sound RAM, 16-bit DAC output and full master volume. The previous
read/modify/write read a write-only register. It could clear the memory mode
required by the running sound driver and the movie PCM ring.

The new host test rejects the previous startup. It verifies six initial
register values and forbids control-register reads. Emulator PCM checks pass
for cold gameplay, early movie skip and natural completion. Isolated jump and
ring effects keep their baseline output. The opening PCM has no clipping.
The emulator stores the memory-mode bit but does not model its effect on RAM.
A console check is required to confirm the reported silence and later audio
corruption are resolved.

Music is reduced by 20% (-1.94 dB) independently of effects and master volume.
Isolated output measurements against the original found music about 2 dB
too high relative to jump and ring effects. The original fade law and its
timing are unchanged. A comparison of 88,200 channel samples in the pinned
SCSP interpreter preserves the law state and gain witness. Maximum rounding
difference from the expected output is one sample unit.

## Validation

Focused audio tests: PCM/skip/completion and DSP/control host checks pass.
Isolated gain comparison: music RMS ratio0.7998; jump/ring PCM byte-identical.
Fast QA: passed all 171 checks with zero failures. 43 validated results were reused.
Final full regression: passed all 215 checks with zero failures. 63 validated results were reused.
The zone and special-stage matrix passed all 347 windows. It reused 322 validated results.
These are 100% of the declared release inventories, not 100% of possible game paths.
Recipe audit: passed; zero initialized-data literals and zero scan matches.
Final prepared-site audit: passed; zero unexplained matches.
Actual Chrome conversion: passed. Downloaded BIN/CUE match the candidate hashes.
Chrome presentation check: V0.083 receipt filename and metadata pass.
All conversion inputs remain identical to the accepted browser reconstruction.

## Console check

Compare cold gameplay with an opening skipped early and an opening played to
completion. Check movie sound, jump and ring effects, music/effects balance,
pause/resume, and a subsequent zone transition.

Only source and audited patcher materials may be published. No game image,
BIOS, extracted art or audio is included.

## Tested output hashes

Build label: `V0.083 / 20261123`. These identify the software-tested candidate.
The final full regression passed. Browser reconstruction matched these hashes.

- BIN: `8ef64ccd07739b3e6e00fd424409000b54d629c6470e1f5865cc3cec4d703d86`
- CUE: `10f35a87674de372bc4b217a4e877f5321aa683afda91eab18df2df331d04337`
- ISO: `4bdaec86eab0bcf86526d159c010eeea3a50257e8c56146db393df9150a346ad`

The soundtrack remains Japanese. U.S. soundtrack selection is deferred.
