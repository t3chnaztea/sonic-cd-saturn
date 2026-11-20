# V0.052 — original power-up visual state

The native shield, four invincibility stars and four time-travel stars now use
the original actor state machine and share the priority-1 sprite queue. They
advance in simulation, not in rendering. V0.052 is a focused candidate, not
full-zone or physical-console acceptance. Native gameplay/travel scheduling and
power-up persistence are unchanged; the limitations below remain open.

## Implemented and independently verified

`src/powerup_visual.c` / `.h` implement the nine original actor animations:
shield, four invincibility stars and four time-travel stars. Actor state includes
initialization, cursor/timer, mapping, flips, private history phase, priority,
suppression/resumption and deletion. The context supplies the 64-position ring,
current player flags, power-up ownership and shared art-selection byte.

`tools/powerup_assets.py` assembles the source animation table and requires an
exact match inside untouched retail `R11A__.MMD` before generating C data.
`tools/test_powerup_visual.py` executes the original actor dispatcher at
`0x2063f6` up to its original `DrawObject` boundary (`0x203af2`) or return.
It compares every represented native actor field and the shared art byte,
including the original animation routine's effects. No retail code is patched.
The reusable `retail_reference` helper also checks actual Saturn telemetry.

Current evidence: **36,948 complete original CPU/native updates**, including
9,312 updates in a mixed nine-reserved-slot timeline; all 47 used animation/pose
pairs; 600-update script timelines, flips, pause/resume, deletions, global art
suppression and record-buffer wrap. Every case is replayed under address and
undefined-behavior sanitizers. Inactive/invalid native states are also checked.
Files: `build/powerup-visual/report.json`, `retail-cases.bin`, `sanitized.log`;
execution log: `build/powerup-visual-final.log`. The new check is in `qa-loop.py`.

The initializer's first update submits nothing. Time-star scripts include
transparent frame 0 and a reverse leg; the replaced always-visible
`(player.frame+n)%5` formula could not reproduce either. Each star's six-update
history phase freezes while suppressed. Shield flips change with the original
animation update, not unconditionally on every rendering call. Re-granting an
existing power-up does not reset its original actor cursor or private phase.

## Implemented integration boundary

Effect state is no longer derived from `shield_age`, `1320-invincible` or global
frames. `sprite_draw` only consumes state; pause/redraw cannot advance it.

1. `scd_player_effects` captures the position-record point before object collision
   and moving supports, then captures the effect context after Sonic's touch
   response but before ordinary object updates. Source `ObjSonic_Main` records
   before animation / `Player_ObjCollide`; hurt and dead modes also record.
   A post-`scd_objects_step` position is not automatically equivalent.
2. Reserved source slots are shield 6, invincibility 8..11 and time stars 12..15;
   ordinary objects begin afterward. Sonic-created time stars initialize in
   that same actor pass. Monitor grants occur after the reserved slots and
   initialize on the following pass. Re-grants write ID/animation only.
3. The adapter preserves simulation cadence, suppression, removal and scene resets.
   Time-warp gameplay is currently scheduled in `main.c` after native objects;
   the adapter uses that existing travel state. This is an explicit limitation,
   not proof of source-identical overall time-warp gameplay scheduling.
4. Submitted effects merge at priority 1, before ordinary actors in reserved
   submission order. The complete group reverses for VDP1 painter order. Mapping
   0 is transparent; frames 1..7 use `OBJECT_BASE_205`, 8..12 use `OBJECT_BASE_3`.
5. Target snapshots and independent source-pixel sequences cover all nine
   scripts, including blank frames and overlap with Sonic/other effect slots.
   Arbitrary priority-0 scenery and equal-priority ordinary-actor overlaps still
   need additional target fixtures. Host checks cover suppression/recollection.

## Integration evidence

- `build/powerup-runtime/report.json`: real-player, ASAN/UBSAN checks distinguish
  the pre-touch history and post-touch/pre-object context. An actual rising
  monitor item grants on tick 33, creates the reserved slot late, initializes
  next pass and first draws one pass later. Recollection, suppression/resumption
  and reset are checked. Repeated read-only snapshots cannot advance state.
- `build/powerup-runtime/culling-report.json`: 13,211 untouched original
  `DrawObject` calls match the native width-16/zero-Y-radius camera culling,
  including signed bounds and vertical wrap. Cases are replayed with sanitizers.
- `dist/powerup-target-report.json`: 23,638 actual Saturn updates / 10,186 retail
  actor executions; all 47 script/pose pairs. Player/travel context and late
  grant events are captured inputs, not an assertion of original gameplay.
- `dist/powerup-render-report.json`: 310 pictures; 158,569 opaque effect texels,
  189,038 Sonic texels, 12,093 effect/effect and 29,714 effect/Sonic overlap
  texels. Original mapping/art bytes compose the expected pixels independently
  of the generated textures. Source-transparent frames retain Sonic coverage.

Pixel scope is y=56..183, outside the HUD. The first checker mistakenly included
RINGS at y=50 and reported its white digits as star mismatches; the corrected
boundary explicitly excludes that HUD band. No opaque effect/effect or
effect/Sonic overlap texels within the band are skipped. There is no claim of
transparent-background, all foreground overlaps, or hardware coverage here.
The source-pixel check saw zero foreground-covered effect texels in these
particular sequences. General foreground/Sonic camera checks remain separate.

Both target checks now run as part of `test-world-emulator.sh`; the runtime and
isolated original actor proofs are in the 28-gate fast loop.

## Related behavior to audit separately

Original `Level/Main.asm` clears shield/invincibility/shoes/time-warp flags during
level initialization. V0.052 still restored shield/whole actor state on arrival;
V0.053 corrects that saved-state boundary with a separate original-CPU proof.
See ARRIVAL-FIDELITY.md. Overall travel scheduling, the exact save frame and
camera/terrain relocation remain separate open audits.
