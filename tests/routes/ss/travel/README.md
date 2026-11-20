# Stardust Speedway natural-travel controllers

Each `ss<act><from><to>.txt` contains `updates pad` controller runs. Letters
are A Present, B Past, C Good Future, D Bad Future. Each act has A→B, A→D,
B→A, C→A and D→A fixtures. They use time posts and sustained travel speed.
They do not write gameplay RAM or construct time-post state.

Replay one native commitment:

```sh
nice -n 20 python3 tools/test_ss_travel.py --act 1 --era A --to B \
  --script tests/routes/ss/travel/ss1AB.txt --host-only --output build/ss1AB-travel
```

An output directory must be new. Add `--retail-prefix` for the independent
Sega CD source-era comparison. Its report distinguishes a matching prefix,
a gameplay split, and an aligned replay that ends before warp commitment.
Retail VBlank charge timing can change the warp frame or selected era.
This diagnostic does not replace the Saturn arrival gate.

To test the target, omit `--host-only` and provide `--cue` and `--elf` for
the same integrated build. The shared travel driver checks every native
prefix position, one natural era change, the handoff, resumed gameplay,
arrival music, zero respawns and zero late gameplay intervals.

These scripts are host fixtures. Final-BIN SS travel acceptance and the maintainer's
SAROO test remain pending. Evidence is preserved locally under
`build/weekend-20261016/ss-travel/`. Prior five-zone release images are not
SS test candidates.
