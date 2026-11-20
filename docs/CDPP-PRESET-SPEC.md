# CD++ preset spec

Draft 2026-10-18. Roadmap step 5. Builds on `docs/PARTY2-INVENTORY.md` §1 and §3.
Classic stays the default. Classic is protected by its own traces and routes.

## 1. What Sonic CD++ changes

Sonic CD++ is a Mega-CD patch by qiuu and snkenjoi, v1, released 2009-06-20.
MKAmeX drew the small-Sonic spin dash sprites. Patches exist for US, EU and JP
([Sonic Retro search summary](https://info.sonicretro.org/Sonic_CD_Plus_Plus),
[romhacking.net 1070](https://www.romhacking.net/hacks/1070/),
[Retrostic mirror](https://www.retrostic.com/romhacks/sonic-cd)). The confirmed
change list ([TASVideos submission 6422](https://tasvideos.org/6422S)):

1. Sonic 2-style spin dash (hold Down, press A/B/C to rev).
2. Homing attack, Sonic Megamix style (press a button while balled in the air).
3. Air roll (press a button in mid-air to curl).
4. Air speed cap removed.
5. Mini Sonic can spin dash.

Sources call it "significantly speedier". None lists bugfixes, Super Sonic or
Tails. Sonic Retro and romhacking.net blocked fetches, so the readme was not
read. Homing and air roll frame behavior is unverified.

## 2. Related remaster options (not CD++)

- Sonic CD 2011 (Christian Whitehead, Retro Engine) has a spin dash option:
  original CD or Sonic 2 style. Sonic Retro lists the Sonic 2 style as the
  default. The option also changes camera lead
  ([Sonic Retro 2011](https://info.sonicretro.org/Sonic_CD_(2011)),
  [Sonic Wiki](https://sonic.fandom.com/wiki/Spin_Dash)).
- Sonic Origins kept only the spin dash option for Sonic CD
  ([TCRF Origins/Sonic CD](https://new.tcrf.net/Sonic_Origins/Sonic_CD)).
- Drop dash is a Sonic Mania move. Origins Anniversary Mode retrofits it into
  CD ([Nintendo Life](https://nintendolife.com/reviews/switch-eshop/sonic-origins),
  [TCRF](https://new.tcrf.net/Sonic_Origins/Sonic_CD)). It is not CD++.

## 3. Units and hooks in this codebase

Speeds are 8.8 fixed point: 256 = 1 px/frame. Walk cap `plmaxspdwk` = 1536
(6 px/f), shoes = 3072 (`src/player.c:106,122`).

Hooks:
- `scd_player_step` (`src/player.c:689`): input edge detection
  (`swdata`, lines 712-718), CD dash charge clamp (lines 782-786).
- `scd_player_motion` (`src/player.c:651-687`): air branch (`jumpchk2`,
  `jumpmove`) and ground branch (`jumpchk`, `keispd`, `levermove`, `ballchk`).
- `jumpmove` (`build/probe-source/player.c:494-523`): clamps air `xspeed` to
  ±`plmaxspdwk` whenever Left or Right is held. That clamp is the "air speed cap".
- Never edit generated `build/probe-source/*` for CD++. New code goes in
  `src/player_plus.c`, called from `src/player.c` behind `scd_preset_flags`.

## 4. Candidate features

### F1 Sonic 2 spin dash (CD++ #1, 2011 option)
- Behavior: crouch, each A/B/C press adds 2 to `spinrev` (max 8). `spinrev`
  decays each frame by drag. Release Down launches at `8 + floor(spinrev)/2`
  px/f, 8 to 12 px/f (2048 to 3072 here). Water does not change it
  ([SPG Special Abilities](https://info.sonicretro.org/SPG:Special_Abilities)).
- The CD dash is Down + hold jump, charge 30/45 frames, release jump
  (`src/player.c:782-786`). F1 replaces it in the preset only.
- Sketch: in `player_plus.c`, while ducking on ground with `mspeed==0`,
  consume jump edges into `spinrev` and suppress `jumpchk`. On Down release set
  `mspeed`, `cddat|=4` (roll), roll sound. Rev animation reuses the CD dash
  charge frames first; new rev frames are a later art task. Camera: hold
  `scra_hline` briefly after release; tune by eye.
- Disable `charge_buffer` (`src/player.c:716-718`) when F1 is on.
- Tests: new trace set `traces/cdpp/` with stand-rev-release at 0, 1, 4 presses
  and decay timing. Check PPZ1 and SS1 routes with preset on.
- Risk: medium. Rolling at 12 px/f can tunnel through thin walls. Run each
  zone's route with F1 on before shipping.

### F2 Air speed cap off (CD++ #4)
- Behavior: holding forward in the air no longer pulls `xspeed` down to 6 px/f
  (12 px/f with shoes). Holding forward below the cap still accelerates to it.
- Sketch: a preset copy of the `jumpmove` direction branch that clamps only
  when the pre-input speed was under the cap. Sonic 2 still caps air speed
  ([SCHG](https://info.sonicretro.org/SCHG_How-to:Remove_the_Air_Speed_Cap)),
  so this is CD++ behavior, not S2. Call it from
  `scd_player_motion` in place of `jumpmove()` when the flag is set.
- Tests: trace a ramp launch above 6 px/f with Right held; Classic trace shows
  clamp, CD++ trace keeps speed. Routes: SS (Stardust Speedway) and PPZ ramps.
- Risk: low code risk. Camera can lag at high speed; check `scra_hline` limits.

### F3 Air roll (CD++ #3)
- Behavior: airborne, not balled, A/B/C press sets ball state (`cddat|=4`),
  ball hitbox. Proposed: one use per airtime.
- Sketch: in the air branch before `jumpchk2`, if `(cddat&6)==2` and a fresh
  jump edge and not in a spring/launcher pose (`mstno` checks), set ball,
  `yradius`/`xradius` to ball sizes as `ballset` does.
- Tests: spring-then-roll trace; enemy hit after roll. Routes with springs:
  PPZ1, CC1, WW1.
- Risk: medium. Spring and tube objects set Sonic's state; rolling there can
  break a scripted path. Block air roll while an object owns the player.

### F4 Homing attack (CD++ #2)
- Behavior (Megamix style, unverified frames): in a ball in the air, jump press
  locks to the nearest enemy/monitor ahead in range and flies at it. No target:
  small forward air dash.
- Sketch: object-table scan ahead of Sonic, aim vector, rebound via existing
  touch response.
- Risk: high. Touches object interaction and boss balance. Needs CD++ capture
  under emulation to match its rules.
- Implemented as a best reconstruction. Every homing value is "design" in
  section 5's table. Targets are badniks only (`scd_objects_enemy_type`);
  monitors are not targeted (their broken state is private to
  `src/objects.c`), and boss actors are never badnik types.

### F5 Mini Sonic spin dash (CD++ #5)
- F1 for small Sonic. Implemented with the existing small roll frames (the
  mini animator's curl). New small rev frames remain a later art task; CD++
  art cannot ship.

### F6 Drop dash (Mania/Origins, not CD++)
- Optional "Enhanced" extra. Hold jump in air, land into a roll. Origins
  implements it in CD as a one-frame spin dash on landing
  ([TCRF](https://new.tcrf.net/Sonic_Origins/Sonic_CD)), so it can reuse F1.
  Speeds unverified. Label it Mania-derived, not CD++. Not in MVP.

## 5. Implementation (2026-10-18)

All five CD++ moves are in `src/player_plus.c`, each behind one flag bit.
`src/player.c` calls six hooks; its weak no-op copies make a build without
`player_plus.c` Classic by construction. F6 (drop dash) is out of scope.

Flag bits: `SPINDASH2=1, AIRCAP_OFF=2, AIRROLL=4, HOMING=8, MINIDASH=16`.
CD++ preset = `31` (all five).

Parameters. "SPG" and "S2" values have a public source. "design" values have
none: they are this port's choices, not CD++ parity.

| Move | Parameter | Value | Source |
|---|---|---|---|
| F1/F5 | rev per press | +2 (512), cap 8 (2048) | SPG, S2 Sonic_UpdateSpindash |
| F1/F5 | rev decay per update | rev -= rev/32, before the press | S2 |
| F1/F5 | release speed | 8 + floor(rev)/2 px/f (2048 + 128 steps) | SPG |
| F1/F5 | start | grounded, flat, still, Down only held, jump press | CD dash conditions |
| F1/F5 | sounds | 156 per rev, 145 on release (CD dash sounds) | design |
| F1/F5 | rev pose | roll frames (no new art) | design |
| F1/F5 | camera lag after release | none | design |
| F2 | air control | accelerate to cap; never pull a faster Sonic back | S3K Sonic_ChgJumpDir |
| F3 | allowed poses | falling/walk 0, run 1, spring 16; no object control, no current | design |
| F3 | uses per airtime | 1 | design |
| F3 | sound | none | design |
| F4 | range | 160 px ahead, 64 up, 128 down | design |
| F4 | homing speed | 8 px/f (2048), re-aimed each update | design |
| F4 | homing time | 40 updates at most | design |
| F4 | no target | forward air dash at 8 px/f | design |
| F4 | uses per airtime | 1; a destroyed target allows another | design |
| F4 | sound | 145 | design |
| F4 | object control | an object that takes Sonic over or sets his speed after the player's update (bumper, launcher, spring) ends the attack before it re-aims; the attack stays used | design |
| F4 | line of sight | none: a badnik behind a wall is a target, and Sonic flies into the wall for up to 40 updates (known gap) | design |
| all | attract demos | always Classic (retail input), whatever MODE says | design |

## 6. Toggle and save design

- Storage: BUP file `SCDSATURNCF` (11 chars, BUP name limit), separate from
  `SCDSATURN00/01` and `SCDSATURNTA`. Payload: magic, version, preset byte,
  flags byte, CRC32. Missing, damaged, or unknown version reads as Classic.
- UI: a "MODE: CLASSIC / CD++" row in the RAM Data panel
  (`src/save_view.inc`, native text, no art). A title entry would need new art
  and change the retail menu (`src/title.c:73-75`).
- Runtime: `scd_preset_flags` read at act start only (`scd_player_init`).
  Save mailbox slot 11: the act's flags in bits 0-7, the setting in bits 8-15.
- Progress saves stay preset-neutral. Time Attack keeps a separate CD++
  table so CD++ times never replace Classic records: `fe_ta_file_name()`
  picks `SCDSATURNTP` with the preset on and `SCDSATURNTA` in Classic.
- Implemented: "SCDC" v1, 16 bytes (`src/save.h`). Boot reads it in
  `scd_save_saturn_init`. The RAM Data row reads `MODE CLASSIC  LEFT RIGHT`;
  Left or Right switches it and writes the file at once.

## 7. Test plan

- `tools/test-player.sh` builds with flags forced 0. Classic traces stay
  byte-identical. Add a guard: flags 0 equals a build with `player_plus.c`
  compiled out.
- `tools/test_cdpp_player.py`: the guard above, the settings codec, and 18
  host trace cases against `tests/routes/cdpp/traces/cdpp-trace.txt`
  (`--regenerate` rewrites them). Never regenerate Classic traces for CD++ work.
- `tools/test_cdpp_routes.py`: the RAM Data toggle and cold boots on Saturn,
  then one emulator route per move (`tests/routes/cdpp/*.txt`). Each Saturn
  replay must match every CD++ host position, and the same pad without the
  move's bit must diverge.
- Emulator routes: existing gates run Classic and assert mailbox slot 11 = 0.
  Add CD++ copies of one route per zone and all boss routes. SAROO pass
  required before release notes claim CD++.

## 8. Attribution

- Credit in `README.md` and release notes: "CD++ preset inspired by Sonic CD++
  by qiuu and snkenjoi (2009), small spin dash sprites by MKAmeX
  ([romhacking.net 1070](https://www.romhacking.net/hacks/1070/))."
- No CD++ code, patch data or sprites ship. Moves are native reimplementations
  from public references (SPG).
- Credit the 2011 remaster (Christian Whitehead / Sega) for the spin dash
  option, Sonic Mania for any drop dash.
- No parity claim with CD++ without an emulator capture of the patched game.
- Open: no license text found. Read the romhacking.net readme by hand and
  record any terms here before release.
