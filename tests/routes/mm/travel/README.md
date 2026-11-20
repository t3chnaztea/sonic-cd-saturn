# Metallic Madness natural-travel controllers

Each `mm<act><from><to>.txt` contains `updates pad` controller runs. Letters
are A Present, B Past, C Good Future, D Bad Future. Each act has A→B, A→D,
B→A, C→A and D→A fixtures. They use time posts and sustained travel speed.
They do not write gameplay RAM or construct time-post state.

The ten scripts were searched on the ROUTE_MM host (`tools/qq_route_search.c`,
seed 51, 100,000 iterations) and saved only after the host replay committed
the warp to the wanted era (`--save-route`).

Replay one native commitment:

```sh
nice -n 20 python3 tools/test_mm_travel.py --act 1 --era A --to B \
  --script tests/routes/mm/travel/mm1AB.txt --host-only --output build/mm1AB-travel
```

Omit `--host-only` to test the target (`dist/` CUE and `build/saturn` ELF of the
same build). The shared travel driver checks every native prefix position, one
natural era change, the handoff, resumed gameplay, arrival music (track 32 +
era), zero respawns and zero late gameplay intervals. The release gate runs all
ten: `python3 tools/zone-gates.py --zones mm --gates travel`.

Emulator evidence only. The maintainer's SAROO test remains the hardware gate.
