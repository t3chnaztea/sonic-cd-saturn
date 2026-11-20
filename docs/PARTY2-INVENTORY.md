# Party 2 inventory: Saturn saves, Sonic CD++, Classic/CD++ toggle

Research date 2026-09-26. Read-only. Repo branch `zones/terrain-all-seven` @ 4081c1d.

## 0. Existing repo notes on CD++

- `PORT-ROADMAP.md:24-27` (step 5): optional, documented CD++-style preset; verify
  the hack's behavior and attribution; implement moves natively; test both presets
  against collision, travel, boss, completion routes; Classic default and
  independently protected; no binary-compatibility claim.
- `PALMTREE-PANIC-PLAN.md:19-20`: CD++ is a stretch goal, "not permission to change
  Classic physics". `ARRIVAL-FIDELITY.md:4`: arrival fix is Classic, not CD++.
- No CD++ spec, feature list, or attribution exists in the repo yet.

## 1. Sonic CD++ (the hack)

Identity: "Sonic CD++" / "Sonic CD Plus Plus", Mega-CD hack, version 1, released
2009-06-20 (page last modified 2016-04-28). Credits: qiuu and snkenjoi (main coding),
MKAmeX (small-Sonic spin dash sprites), Mad Echidna ($100 bounty), Tweaker
(suggestions). Patches exist for US, EU, JP. Authors call it "incomplete".
An optional OST switch puts JP/EU music on the US build.

| # | Change (confirmed) | Class | Cost here |
|---|---|---|---|
| 1 | Sonic 2-style spin dash: hold Down, press A/B/C to charge; replaces CD's own spin dash | physics + sprites | M: new state in player routine, charge/release speed table, rev animation, dust; needs Classic CD dash kept intact |
| 2 | Homing attack (Megamix-style): press A/B/C while airborne in a ball | physics | M-L: target search over object table, lock/launch vector, rebound on hit; touches enemy/monitor/boss interaction |
| 3 | Air roll: airborne and not balled, press A/B/C/Down to curl | physics | S: state flip + hitbox change; must not break spring/launcher routes |
| 4 | Air speed cap removed | physics | S: one clamp path in air movement (`plmaxspdwk` clamps in `build/probe-source/player.c` ~L304-343, 516-523) gated by preset; route/camera risk at high speed |
| 5 | Mini-Sonic can spin dash | physics + sprites | S after #1: small-Sonic rev frames |
| 6 | OST switch (JP/EU music on US) | content/audio | N/A: this port already requires the JP soundtrack (`JAPANESE-MUSIC.md`) |

Not in CD++ (no source found): Super Sonic, time-travel changes, Tails, save
changes, bugfixes. Those belong to the 2011 Christian Whitehead remaster, not
CD++. If wanted, list them as separate "Enhanced" items with their own sources.
No bugfix category entries were confirmed.

Implementation note: player physics compiles from reconstructed original C in
`build/probe-source/{player,movement,...}.c`, fronted by `src/player.c` (494 lines).
CD++ moves must hook as a gated layer (frontend or post-generation patch), never
edit Classic paths in place. Sprite work (rev frames) needs user-supplied or
original-derived art; the CD++ patch art cannot ship in-repo.

Sources:
- LaunchBox DB, "Sonic CD++": https://gamesdb.launchbox-app.com/games/details/92663-sonic-cd
- Retrostic mirror of the romhacking.net entry (credits, v1, dates): https://www.retrostic.com/romhacks/sonic-cd
- Romhacking.net hack 1070 (primary; Cloudflare blocked fetch, seen in search): https://www.romhacking.net/hacks/1070/
- Fan Games 'n' Hacks wiki (search summary; OST switch): https://fan-games-n-hacks.fandom.com/wiki/Sonic_CD_Plus_Plus
- Lost Mania forum thread (regions, "significantly speedier"): https://lostgenerations.freeforums.net/thread/220/sonic-cd-plus
Gap: no first-party readme text was fetched. Verify the spin dash charge values
and homing rules by playing the patched image under emulation before coding.

## 2. Saturn saves: what exists

- `src/save_saturn.c` (63 lines): BIOS BUP backend on the internal device only
  (`BUP_DEVICE_INTERNAL`, partition 0). Two files `SCDSATURN00`/`SCDSATURN01`,
  comment "SONIC CD", 32 bytes each, RTC date, write then `bup_verify`. Correct
  ST-162 config stride; length check before unbounded `BUP_Read`. No auto format
  or delete.
- `src/save.c` (82 lines): format "SCDS" v1, CRC32, generation counter. The two
  files are A/B redundancy (write alternate, keep newest valid), not player slots.
  Status/messages for absent, unformatted, full, protected, damaged, recovered.
- Payload (`src/save.h`): zone, act, era, time_stones, good_acts, good_zones,
  completed. Bytes 19-27 reserved and must be zero (decode rejects nonzero).
- Writes: `save_checkpoint()` at act starts (`src/main.c:179-183`), only when
  `save_session` is set; cheat inputs clear it (`main.c` ~1217-1219).
- Title: New Game (asks via panel if a save exists), Continue (needs valid save),
  RAM Data panel (`save_view.inc`, retry/reopen). Title menu list is built in
  `src/title.c:150-157`; Time Attack, D.A. Garden, Visual Mode entries exist in art
  but `main.c` routes other destinations back to the title.
- Tests: `tools/save_test.c` (host fake disk, torn writes); cold-Continue already
  exercised by `tools/test_tt_route.py:13-17,231-234` and
  `tools/test_cc_campaign_route.py:270-286` via `SCD_BACKUP_INPUT`/mailbox.

## 2b. Missing for full save coverage

| Item | State | Needed |
|---|---|---|
| Stones | Saved (`time_stones` bitmask) | Hardware check only; confirm special-stage return commits |
| Good futures | Saved (`good_acts`, `good_zones`) | Verify against original BURAM layout for good ending |
| Cold Continue | Works in emulator routes (CC, TT) | Extend to all 7 zones; SAROO power-cycle hardware evidence |
| Time Attack records | Absent; menu entry not routed | Mode itself, then per-act best times (21 acts x 3 bytes + initials, ~70-90 B); needs v2 format or a second file |
| Unlock flags (D.A. Garden, Visual Mode, sound test) | Absent | Bits derived from completion/time attack; fits reserved bytes |
| Per-slot saves | Absent (single game; A/B is redundancy) | Original Sonic CD also has one game. Keep one slot for Party 1; multi-slot is optional Party 2 |
| Cartridge backup (external BUP device) | Absent | Device select + UI; SAROO may emulate internal only; low priority |
| Settings (preset, etc.) | Absent | 1 byte in reserved area or settings file |

Format note: any new field breaks v1 decode (reserved bytes must be 0). Plan a
v2 with v1 read-upgrade, or a separate `SCDSATURNCF` settings/records file so the
progress file stays v1 and Classic tests keep their fixtures.

## 3. Toggle design (Classic / CD++)

Where it lives:
- UI: an Options entry off the title menu (`src/title.c` menu list) or inside the
  RAM Data panel (`src/save_view.inc`). Title slot is cleaner; the original has no
  options screen, so keep it out of Classic's menu order unless selected.
- Storage: separate settings file (recommended), not the progress record, so
  saves stay portable across presets and v1 fixtures remain valid.
- Runtime: one global `scd_preset` (0 = Classic) read at act start, not per frame
  mid-act. Each CD++ behavior checks a flag bit (spindash2, homing, airroll,
  aircap_off) so items can be tested and toggled singly.

Keeping Classic default and unaffected:
- Missing/damaged settings file -> Classic. Zero-initialized value = Classic.
- CD++ code sits behind `if(scd_preset)` hooks in `src/player.c` frontend or a
  separate `player_plus.c`; no edits to generated `build/probe-source` Classic code.
- Record preset in the save mailbox (`scd_save_mailbox`, slot 11 is free) so
  emulator tests can assert which preset ran.

How tests pin Classic:
- `tools/test-player.sh` compares host vs reconstructed reference traces byte for
  byte; build the host with preset forced 0 (compile flag or explicit set) so the
  traces stay the Classic gate. Add a separate CD++ trace set, never regenerate
  Classic traces for CD++ work.
- Emulator routes: env var (for example `SCD_PRESET=classic`) or fixture backup
  image without a settings file; assert mailbox preset = 0 at route start.
- Add a guard test: CD++ flags off must produce identical traces to a build with
  the CD++ code compiled out.
- Duplicate collision/travel/boss/completion routes for CD++ per roadmap step 5.
