# HARDWARE-ACCEPTANCE history

Moved verbatim from `HARDWARE-ACCEPTANCE.md` on 2026-10-03. Each section
describes its own checkpoint, not the current card or candidate. Current:
[HARDWARE-ACCEPTANCE.md](../../HARDWARE-ACCEPTANCE.md).

# V0.063 — CC1 campaign candidate with corrected audio label (BUILT; NOT ON CARD)

V0.062 was built, passed full QA and was preserved locally, but its in-game
audio diagnostic still read V0.061. It was not copied to SAROO. V0.063 corrects
that label. BIN SHA-256:
`87a05fe81d831375d6f90794685937f598f8add6f41b2026821ab2d681220812`.
The Japanese-source build passed all 52 fast gates
(`build/qa-loops/20260923-133719-608246/report.json`) and all 80 full gates
on this exact BIN (`build/qa-loops/20260923-130148-685694/report.json`).
The local-only archive is `build/hardware-v0.063/`; no SAROO copy or physical
Saturn result exists yet. See `docs/archive/RELEASE-NOTES-V0.063.md` for campaign evidence.

## V0.063 Saturn checklist

1. Confirm the boot/audio diagnostic identifies V0.063 and Japanese music
   plays. Record the exact BIN hash and SAROO folder tested.
2. Start New Game, clear Palmtree Panic Acts 1–3 and enter Collision Chaos
   Act 1 Present. Cold Continue from that naturally earned checkpoint.
3. Travel to Past, destroy the robot generator and verify the 1,500-point
   award. Return to Present, reach Good Future and finish Act 1. Note music,
   visible scenery, controls and any stalls at each travel transition.
4. Confirm Act 2 begins in Present with the earned Good Future progress and
   carried score. Power-cycle the Saturn, choose Continue and verify the Act 2
   checkpoint, Japanese Present music and Good Future progress survive.
5. Recheck frame pacing, scrolling, audio pause/resume, object art and any
   behavior worse than the prior console-tested build. Record console
   observations; emulator success does not close this gate.

# V0.062 — CC1 campaign Good Future/save candidate (BUILT; NOT ON CARD)

BIN SHA-256:
`2a64e2adfa48104e85a99573b063e2962ee3abe7e92ce0870bb5ad23392a09bb`.
The Japanese-source build and all 80 full QA gates passed on this disc.
The private local full-QA archive is `build/hardware-v0.062/`, readback-checked
with 439 members and 14 disc-bound reports. No SAROO copy or physical Saturn
result exists yet. See `RELEASE-NOTES-V0.062.md` and the current handoff in
`NEXT-SESSION.md` for emulator evidence and open scope.

## V0.062 Saturn checklist after packaging

1. Confirm the boot/audio diagnostic identifies V0.062 and Japanese music
   plays. Record the exact candidate BIN hash and SAROO folder tested.
2. Start New Game, clear Palmtree Panic Acts 1–3 and enter Collision Chaos
   Act 1 Present. Cold Continue from that naturally earned checkpoint.
3. Travel to Past, destroy the robot generator and verify the 1,500-point
   award. Return to Present, reach Good Future and finish Act 1. Note music,
   visible scenery, controls and any stalls at each travel transition.
4. Confirm Act 2 begins in Present with the earned Good Future progress and
   carried score. Power-cycle the Saturn, choose Continue and verify the Act 2
   checkpoint, Japanese Present music and Good Future progress survive.
5. Recheck general frame pacing, scrolling, audio pause/resume, object art and
   any behavior worse than the prior console-tested build. Record the actual
   console observations; emulator success does not close this gate.

# V0.057 — title-card clock and ring-loss pacing candidate (ON THE CARD)

BIN SHA-256:
`064ef17c4ec6905c66f9d1ea33e923c93e691de5d2589fddc4875d12ffb4f2db`.
**Deployed to the verified SAROO card and safely ejected**, as
`SAROO/ISO/Sonic CD Saturn v0.057`, readback-checked. Volume UUID
`<card UUID>`. The other 181 entries are unchanged:
their metadata digest is identical before and after
(`7985de41a7a4c4f457c5e722d3017d69dc3cf854391ea961fcccfabbc9f8a846`). Nothing
was removed. Receipt: `build/card-deployment-v057.json`.
**No hardware result exists yet. This is the first console test of V0.057.**

Two changes from V0.056. The title card now releases on update 130, with the
first input and clock tick on 131; V0.056 accepted input on 129. And losing
twenty rings no longer overruns a refresh: the scatter spawns twenty objects in
one update, and that update went from 51,129 to 47,318 CPU/8 ticks against a
budget of about 49,136. See the V0.057 section of `PERFORMANCE.md`.

The audio diagnostic screen reads `AUDIO TEST V0.057`. Use it to confirm which
build the console booted.

## Short V0.057 Saturn checklist

1. **Take a hit while carrying a lot of rings.** This is the case that dropped
   a frame on V0.056 and the reason for this build. It should not hitch.
2. General responsiveness. The same fix saves about 380 CPU/8 ticks on an
   average frame everywhere, not only on the ring-loss frame.
3. Title card: the clock should start with the card, not before, and the first
   input should not be eaten.
4. Re-run the V0.056 checkpoint checklist below; that behaviour is unchanged.
5. Anything worse than V0.056. That folder is still on the card, so the two can
   be compared back to back on the console.

Gates passed on this exact disc: 34 fast host, 15 emulator target, 2 special
(`build/v057-target-qa.log`, `build/v057-special-qa.log`,
`build/qa-loops/20260920-163735-152573/report.json`). Emulator green is not
hardware green and measures no real console timing. Palmtree Panic only.

**Correction to the V0.056 entry below.** It states no V0.056 card copy was
made. The card in fact held `SAROO/ISO/Sonic CD Saturn v0.056` with BIN
`a8a9ce0721fc...` when this deployment began, dated 20 Sep 09:38, holding a
full dump of the candidate directory rather than a BIN/CUE payload. That folder
was left in place as a fallback. Who made it and when is not recorded here; the
V0.056 text below is preserved unchanged rather than rewritten.

# V0.056 — checkpoint clock restoration candidate

BIN SHA-256:
`a8a9ce0721fc977a70153b4313a16d2f8a9575cee453ac02a8437f221cecdbe9`.
Saved checkpoint time now resumes at the saved whole second, dropping fractions,
as in the original game. Fresh starts, protection and audio are unchanged.
Original/native tests cover 1,444 cases / 174,724 clocks with 1,180 old-code
failures; actual Saturn telemetry covers the reload and 120 following clocks,
plus two source-correct HUD pictures. Good Future progression/pacing remains
unchanged. See NEXT-SESSION.md for final regression and packaging status.

## Short V0.056 Saturn checklist

1. Activate a checkpoint at a fractional time, lose a life and check that the
   saved whole second resumes with fractional time reset, then advances normally.
2. Confirm protection/flashing, two remaining lives after the first death,
   cleared rings/power-ups, and the saved position. Fresh starts stay at zero.
3. Retain V0.055 travel responsiveness, title clouds, TV icons, scrolling,
   audio/pause/resume, Good Future boss/results and special-return checks below.

V0.044 remains the last user-tested/card build. No V0.056 card/Desktop copy.
This is a focused checkpoint correction, not complete clock, camera, zone or
physical-console acceptance. Title-card clock locking is the next source audit.

## Historical V0.055 — time-travel arrival performance candidate

BIN SHA-256:
`b6951d679663e352b94c1b1c49085c1cb87946e72efd254ff4b20e90dc92b378`.
Destination terrain is prepared during loading; object placement no longer
repeatedly searches the same slots. No audio, physics or layout rules change.
Full normal-controller Good Future route passes both generators, boss, capsule,
results and title return with zero misses over 26,023 measured intervals and
all 26,029 gameplay states unchanged. All 32 fast and focused target regressions
pass, including original title/Sonic/effect/HUD pictures, audio and special return.
See docs/archive/RELEASE-NOTES-V0.055.md and PPZ-JOURNEY-COVERAGE.md for evidence boundaries.

## Short V0.055 Saturn checklist

1. Travel to Past in Acts 1 and 2 and back to Present. Check the first visible
   terrain frame and responsiveness after each arrival, especially crowded areas.
2. Destroy both Past generators and finish Act 2: Act 3 should be Good Future.
   Finish its boss/capsule/results and return to title.
3. Retest cloud stripes, TV icons, scrolling alignment, checkpoint flashing,
   shield/star trails, music/effects/pause/resume and special-stage return.
4. Identify any remaining disappearing brick by act/era/location when convenient;
   some Present floating blocks intentionally appear only when stood upon.

V0.044 remains last console-tested/card build. No V0.055 card/Desktop copy.
This is not full-zone or hardware acceptance. Original checkpoint clock/camera,
travel scheduling, alternate routes and broader scene fidelity remain open.

## Historical V0.054 — checkpoint respawn protection candidate

BIN SHA-256:
`0df96d901b284a1622f89b4bac41c5462ddca7eb9aea943ef02dd2b9cd850f24`.
Saved-checkpoint respawns now grant the original 120-update protection window.
Fresh starts remain unprotected. Earlier source-based flashing, arrival state,
title/TV/camera/Sonic and effect fixes remain intact. Clock behavior is unchanged.

All 30 host gates pass, including 259 real death/reload cases, 30,600 protected
states, expiry damage and 255 old-source failures. Main replay, world/effect
source pictures and the three-act sequence pass. The target checkpoint route
verifies 885 states and the full 121-state countdown. Title, audio/diagnostics,
special-stage return, standalone Act 1 and opening pacing also pass on this BIN.
All 32,916 unrelated main/sequence states match V0.053; opening, standalone
Act 1 and all three sequence acts have zero measured late intervals.
The four audio/CD sources match console-confirmed V0.040 byte for byte.

## Short V0.054 Saturn checklist

1. Activate a checkpoint, lose a life and respawn. Check short, regular flashing
   and protection from nearby enemies until the timer ends; then normal damage.
2. Without a checkpoint, lose a life: a fresh start should not gain protection.
3. Retain time-travel power-up clearing, title-cloud/TV icons, vertical scrolling,
   shield/star trails, music/effects and special-stage-return checks.

V0.044 remains the last console-tested/card build. No V0.054 card/Desktop copy.
This is not full-zone or physical-console acceptance. Checkpoint fractional
clock restoration, camera/first movement and broader travel timing remain open.
See CHECKPOINT-FIDELITY.md and docs/archive/RELEASE-NOTES-V0.054.md.

## Historical V0.053 hardware handoff

BIN SHA-256:
`df0e79f8d93b0061f25bca6111827dc7c7bcf243fa8fc8e0663e927f699f7bbd`.
Time travel now restores the original saved actor fields into a fresh actor,
clears power-ups/stale animation, and grants 120 updates of arrival protection.
Sonic's protection flashing follows the hurt timer and original submission
order instead of the global frame counter. Earlier visual fixes are retained.

All 29 host gates and focused same-BIN target gates pass. Original-code checks
cover 2,048 arrivals and 2,080 display decisions; the archived V0.052 adapter
fails all arrival cases. Two target hurt routes verify 1,200 display decisions
and complete protection countdowns. All 32,916 unrelated gameplay states match
V0.052. Measured opening, Act 1 and sequence routes retain zero late intervals.
Title, audio/diagnostics, world/effect pixels and special-stage return pass.
This is **not** full-zone or physical-console acceptance.

## Short V0.053 Saturn checklist

1. Time travel with shield/invincibility/shoes. Power-ups should clear on arrival,
   with a short protected flashing period; watch for a stale pose or attachment.
2. Take damage, land and let protection expire. Check regular flashing,
   pause/resume, and damage only after protection ends.
3. Retain title-cloud, TV icons, shield/star trails, vertical-scroll, springs,
   rotating-disc, music/effects and special-stage-return checks.

V0.044 remains the last console-tested/card build. No V0.053 card/Desktop copy
has been made. Verify card identity before deployment. Overall travel scheduling,
camera/terrain relocation and checkpoint spawn protection remain audit items.
See ARRIVAL-FIDELITY.md and docs/archive/RELEASE-NOTES-V0.053.md.

## Historical V0.052 handoff

BIN SHA-256:
`963f403847bc276f594b7eb89ea9429b3e44fc401f0edd4daa3a71dd272ea048`.
Shield, invincibility and time-travel stars now use original scripts, history
phases, suppression and reserved-slot initialization timing. They join the
priority-1 draw group. Earlier title/TV/camera/Sonic fixes remain intact.

All 28 host gates and focused same-BIN target checks pass. Evidence includes
310 original-source effect pictures, 23,638 target effect updates checked via
10,186 retail CPU actor calls, and 13,211 camera-culling cases. All 32,916 main
and sequence gameplay states remain unchanged. Opening, standalone Act 1 and
all three sequence acts have zero measured missed refreshes. Audio/CD code
still matches console-confirmed V0.040. This is **not** full-zone acceptance.

## Short V0.052 Saturn checklist

1. Break shield and invincibility TVs. Check their original flicker, trails and
   overlap with Sonic; recollect a power-up and try pause/resume.
2. Accelerate into time travel with/without power-ups. Watch star trails, blank
   frames, cancellation and arrival. Report any stale or displaced effect.
3. Retain title-cloud, TV-icon, vertical-scroll, spring-apex/disc, music/effects
   and special-stage-return checks. Note dense-scene slowdown or missing art.

V0.044 remains the last console-tested/card build. No V0.052 card/Desktop copy
has been made. Verify card identity before deployment. Native travel scheduling,
arrival shield persistence and wider effect/ordinary-actor overlaps remain
audit items; see POWERUP-VISUAL.md and docs/archive/RELEASE-NOTES-V0.052.md.

## Historical V0.051 handoff

BIN SHA-256:
`8e21f5b6346d74a6d6a05936e132f6c42b279fa825f4e55c4e4fe11207e15209`.
Original actor priority now governs Sonic, ordinary objects and boss parts,
including Sonic in front of TVs/projectors and reversed equal-priority order.
All earlier monitor/title/camera/composition/animation fixes are retained.

All 26 host gates and focused same-BIN target gates pass. Retail queue/metadata
and source-pixel checks verify selected overlaps; six preserved pre-fix pictures
are rejected. All 32,916 main/three-act gameplay states match V0.050. Opening,
standalone Act 1 and the sequence have zero measured missed refreshes. Title,
audio/diagnostics and special-stage return pass. Audio code matches V0.040.
This is **not** full-zone or physical-console acceptance.

## Short V0.051 Saturn checklist

1. Check Sonic overlapping TVs, enemies, springs, the projector, scenery and
   boss parts; watch for objects incorrectly cutting through one another.
2. Retain the earlier checks: upper title clouds, recognizable TV icons, vertical
   scrolling alignment, spring apex/falling poses and natural disc release.
3. Test music/effects, pause/resume, time travel and special-stage return.
4. Note dense-scene slowdown, missing pieces or other glitches. The unidentified
   brick-platform report and generated-effect priority audit remain open.

V0.044 remains the last console-tested/card build. No V0.051 card/Desktop copy
has been made. Verify the card identity before deployment. See
docs/archive/RELEASE-NOTES-V0.051.md and SPRITE-ORDER.md; wider routes/eras and hardware
confirmation remain required before accepting Palmtree Panic.

## Historical V0.050 handoff

BIN SHA-256:
`1fda1a9804bb02808cd100aa945e4fd66871e6f49795dc934bdf4e0b4c8a13f8`.
This restores the original falling-animation selection after spring ascent and
natural disc release. It retains V0.049's complete original pose pack and the
earlier monitor, title, object composition and camera fixes.

All 25 host gates and focused same-BIN emulator gates pass. The new selection
matches 2,400 retail-code cases; 33 consecutive spring pictures verify the apex
transition. Main replay and the full three-act route retain every input and
non-animation state bit. Opening, standalone Act 1 and the three-act sequence
have zero measured missed refreshes. Music/effects, pause/resume, title, world
and special-stage return checks pass. This is **not** complete-zone or hardware
acceptance. Audio/CD implementation remains identical to hardware-proven V0.040.

## Short V0.050 Saturn checklist

1. Use red/yellow springs: watch the ascent, apex and falling poses. Normal rolled
   jumps must retain their rolling animation. Check smooth motion and effects.
2. Ride a spinning disc until Sonic slides off naturally; confirm he no longer
   stays in the frozen disc pose. Also test deliberate jump-off and all six poses.
3. Retain the visual checks below: upper title clouds, TV icons, vertical-scroll
   alignment, Amy/hearts, source sprite details, travel and special-stage return.
4. Check music/effects and pause/resume. Note any dense-scene slowdown or visual
   glitches; the unidentified brick-platform report is still open.

V0.044 remains the last console-tested/card build. No V0.050 card/Desktop copy
has been made. Validate the mounted card's identity before a future deployment.
See docs/archive/RELEASE-NOTES-V0.050.md and AIR-ANIMATION.md. Broader original behavior,
sprite priorities, PPZ route/era coverage and all full-port milestones remain open.

## Historical V0.049 handoff

BIN SHA-256:
`e505d621b79ae2c374fdb5d3498efcc594ce5597f43beb6e883a0d0b3c8653a4`.
Gameplay now renders all 198 source Sonic poses with the original scripts and
H/V flips, replacing the provisional animation and extra rotation. Disc and
Amy/heart ordering follow their original relative priorities. The earlier
monitor, object-piece, title, camera and pacing corrections are retained.

Focused host/emulator checks pass: 85,299 actual player animation calls match
retail execution, 16,800 target presentation states match host/reference, and
162 sampled Sonic pictures match source pixels. All 198 poses are verified
before lossless compression. World/camera, title, music/effects, isolated audio,
special-stage return and recorded three-act sequence gates pass. Opening,
standalone Act 1 and the three-act sequence have zero measured missed refreshes.
This is **not** full-zone, every-pose motion or physical-console acceptance.

V0.044 remains the last console-tested/card build. The audio/CD implementation
still matches the hardware-confirmed V0.040 baseline. No V0.049 card/Desktop
deployment has occurred. Verify the actual mounted volume and UUID before any
later deployment; preserve old candidates recoverably.

## Short V0.049 Saturn checklist

1. Cold boot; inspect the upper title clouds for stripes/flicker and confirm music.
2. Run, jump, roll, skid and use slopes/loops: watch Sonic's original angled poses,
   flips and smooth animation. Test hurt, death, pause/resume and sound effects.
3. Check the six rotating-disc poses and jump-off, plus Amy's hug/idle/release.
   Watch shoes, heart overlap and any stale Sonic texture after transitions.
4. Check power-up TV icons/grants and stationary sprites during vertical scrolling.
   Inspect enemies, generators, ramps and boss artwork for missing/black details.
5. Test time travel and special-stage return; confirm the animation and audio resume.
   Note any dense-ring slowdown. The unidentified brick-platform report remains
   open; original Present floating blocks intentionally appear on contact.

See docs/archive/RELEASE-NOTES-V0.049.md, SONIC-ANIMATION.md and PERFORMANCE.md. Remaining
work includes actor animation selection, wider priority/route/era coverage and
hardware confirmation. This candidate does not finish Palmtree Panic.

## Historical V0.048 handoff

BIN SHA-256:
`95224d40113a0fe4730e6faab86674050c17867c5d4c838b4dd94d1a43bb3eaf`.
This corrects 33 further enemy/generator/ramp/Amy/boss sprite compositions while
retaining V0.047's camera/pacing fixes and the earlier title/monitor/HUD fixes.
The independent source check covers 391 compositions / 1,515,328 pixels; full
target VRAM readback matches 348,288 object bytes. Amy's corrected pink pixels
also pass independent screenshot checks that reject the old black patches.

All 22 fast gates and focused same-BIN main replay, world/camera, title, audio,
isolated diagnostics, full zone sequence, Act 1, special-stage return and
opening pacing pass. The recorded sequence has 16,116 identical gameplay states
and zero missed refreshes in all acts. This is **not** full-zone or hardware
acceptance, nor a complete-game release. Original Sonic animation integration,
broader routes/eras and other full-port milestones remain unfinished.

V0.044 remains the last console-tested build and the last card deployment.
V0.040 is the hardware-confirmed sound baseline; its audio/CD implementation
remains unchanged. No V0.048 Desktop/card copy has been made. Revalidate the
mounted volume and its UUID before any later authorized deployment.

## Short V0.048 Saturn checklist

1. Cold boot and watch title clouds for stripes/flicker. Confirm title music.
2. Check monitor icons and their grants; test ring/jump effects and pause/resume.
3. Watch stationary sprites against the terrain during vertical scrolling,
   including the bottom edge. Look for floating, flicker or stale trails.
4. Look at enemies, generators, ramp artwork, Amy and boss pieces for missing
   or black details. Confirm responsiveness when many lost rings are present.
5. The reported small brick platform is still unidentified. Original Present
   floating blocks intentionally appear on contact; no blanket visibility
   change was made. A location can be supplied whenever convenient.

See docs/archive/RELEASE-NOTES-V0.048.md, SPRITE-COMPOSITION.md and CAMERA-PRESENTATION.md.
Keep prior candidates recoverable. The V0.047 archive's older general README
still starts with V0.046; its version-specific docs/archive/RELEASE-NOTES-V0.047.md describes
that candidate. That immutable archive is not silently rewritten. Packaging
now rejects a hardware README whose top heading names the wrong version.

## Historical V0.046 handoff

V0.046 retains the monitor icon fix from V0.045 and corrects the title's illegal
VDP2 memory-fetch schedule. BIN SHA-256:
`68621e29aae1a1a7e3e1ced139162243216fc1865dd3d34ed7fd3ff43c4d62cf`.
Twenty fast gates, 1,196 exact title pictures plus captured-register validation,
16,800 replay states, 222 world captures and music/effects/isolated audio probes
pass. Full Act 1 matches 8,061 states, with zero missed refreshes over 8,060
measured intervals; the separate 1,800-interval opening test also has zero.
This is not a full-zone release or a hardware-confirmed fix.

V0.044 is the latest console-tested build: the user reports greatly improved
gameplay, with cloud stripes, black monitors, contact-dependent brick visibility
and possible vertical sprite drift. V0.040 remains the sound-confirmed baseline;
the audio implementation is unchanged. The card was reported remounted and has
not been changed for V0.045/V0.046. Do not infer physical status from old notes.

## Short V0.046 Saturn checklist

1. Cold boot; inspect the title's top-third clouds for vertical stripes and
   flicker. Check full-width background and returning to the title later.
2. Approach power-up TVs. Confirm item pictures appear during their animation,
   including facing/flipped views, and breaking them still grants the item.
3. Run, jump, collect rings and pause/resume: music/effects and responsiveness
   must remain intact. Note whether vertical camera movement separates sprites
   from the ground. Camera drift is still under investigation, not claimed fixed.
4. If convenient, identify a disappearing brick's location/era. Original Present
   floating blocks intentionally appear on contact; the reported object is not
   yet identified, so visibility has not been globally forced.

See `TITLE-HARDWARE-CYCLES.md` and `VISUAL-CORRECTNESS-V0.045.md` for source-backed
changes and test limits. Keep prior versioned candidates recoverable.

## Historical handoffs and V0.040 sound diagnosis

Everything below records earlier checkpoints, not current deployment or scope.

**Card handoff update:** V0.044 is now installed on the verified SAROO card, readback-checked and safely ejected. V0.040 was removed from the card before installation and is recoverable in `build/card-removed-v040-for-v044`. Other games are unchanged. Receipt: `build/card-deployment-v044.json`. Earlier “card unchanged/unmounted” statements below describe the pre-deployment checkpoint; hardware testing of V0.044 remains pending.

**Latest local candidate: V0.044**, BIN `fd18db44c07bc9c296f675049dcc9bbd2e543fac5620231cd5ce918f6129c55c`, in `build/hardware-candidate-v0.044-01`. It corrects the RINGS label's original stateful flash behavior after pickup/loss and pause; see [HUD-FIDELITY.md](HUD-FIDELITY.md). All 19 host gates, 16,800-state gameplay replay, full-width title, original HUD, audio probes/music/pause/resume, complete Act 1, recorded Act 2 Present and its Past travel check pass on this BIN. Opening, full Act 1, dense Act 2 and the separate ring-loss stress route retain zero missed refreshes. The audio/CD/sound-memory implementation hashes equal the hardware-confirmed V0.040 baseline. No new level content or audio implementation is included.

Hardware visual/performance acceptance remains pending. When testing this candidate, check the full-width title and clouds, gameplay responsiveness, original HUD, ring pickup/loss, pause/resume and continuing music/effects. The verified BIN/CUE and short checklist were copied to the Desktop folder named `Sonic CD Saturn v0.044`; see `build/desktop-deployment-v044.json`. The card is currently unmounted and unchanged. V0.040 remains the hardware-confirmed audio baseline. The broader world/zone/special-stage checks below describe V0.043, not an unperformed full-zone V0.044 pass. The immutable candidate's earlier README remains a truthful pre-Desktop-copy snapshot.

**Previous candidate: V0.043**, BIN `7495f8471bf2ab8f6019994c502636fa3deacd7454429c98413c2b03cb4d5b63`, preserved in `build/hardware-candidate-v0.043-01`. Object-snapshot reuse and stage-map loading prewarm remove the remaining measured Act 2 gaps, including the separate ring-loss stress case. Title reveal textures are preloaded, restoring exact original title cadence/pictures after the strict checker caught an intermediate-build stall. All 18 host gates and focused same-BIN emulator/player/audio/title/HUD/world/act/transition checks pass. See [PERFORMANCE.md](PERFORMANCE.md). Neither this candidate nor its performance/title behavior is hardware-confirmed; V0.040 remains the user's working-sound baseline. No card update, full-zone acceptance or new sound implementation is implied.

**Additional V0.042 evidence:** five full recorded routes across Act 2's four eras and Act 3 Bad Future match 24,972 previous target states and pass sanitized replay plus original HUD checks. This also finds remaining timing gaps: one dense Act 2 Present interval and early loading intervals in both Future routes. See `build/expanded-pacing-v042-01/manifest.json` and [PERFORMANCE.md](PERFORMANCE.md). The game BIN, card and hardware acceptance status are unchanged; no full-zone QA pass is claimed.

**V0.042 local test checkpoint:** background row caching and direct foreground-edge updates reduce the measured opening/full Act 1 route from 51 missed refreshes (V0.040), through 2 (V0.041), to zero. Sixteen host gates and the six focused emulator reports pass on the same BIN. This version has not been tested on hardware or copied to the card; V0.040 remains the hardware-confirmed baseline. See [PERFORMANCE.md](PERFORMANCE.md). User-reported graphics glitches, animation fidelity and broader scene/hardware timing remain open; this is not complete-zone acceptance.

The final V0.042 BIN is `50651bef6a17afbab06600ef4b5f19a586cb9e1f74a665db5a95d026b04d12bf`; it additionally passes the world regression with 122 captures after correcting diagnostic fixture-publication ordering. Its audio comparisons use matching BIN/recording hashes. The original diagnostic checklist below describes V0.040 history, not a request to retest the obsolete silent builds.

Latest user result: **"IT WORKED!! SOUND WORKS PERFECTLY!!"** after deployment of the verified V0.040 image. The functional sound blocker is cleared. `hardware-results/v0.040.json` records this subsequent evidence; original candidate/deployment manifests remain truthful pre-test snapshots. No broader hardware visual/performance or full-release QA pass is inferred. Pause/resume, every audio event and repeated boots remain in the Palmtree Panic regression matrix.

The user has now authorized completing Palmtree Panic and then scheduled polishing, with no progression to other zones. See [PALMTREE-PANIC-PLAN.md](PALMTREE-PANIC-PLAN.md). The diagnostic narrative and pre-test criteria below are historical, not a claim that the latest build is still silent.

## Historical diagnosis and pre-test checklist

User's V0.037 result (2026-09-19): title music and all effects are silent; pause makes a click/pop. Title has blank strips at both edges and possibly flickering clouds. Gameplay may be slower. This is hardware evidence of a failure, regardless of earlier emulator passes.

No further level development or menu expansion is allowed until real Saturn/SAROO music and effects work. This candidate is for diagnosis; it is **not a full-QA release or a proven hardware fix**. Preserve V0.037 unchanged.

V0.040 corrects the CD response decoder implicated by the user's hardware photo. It retains V0.039's title fix and the original HUD. Older Desktop/project archives are preserved; old card test folders are removed from SAROO's ISO directory before the next candidate is installed. Hardware music/effects are not yet confirmed.

## Hardware result and targeted V0.040 correction

The supplied photo identifies **AUDIO TEST V0.038**, even though V0.039 had also been supplied. Its audio implementation is identical to V0.039. The user hears the independent A tone but no game sound, B ring or C music. Photo: DRIVER READY, DATA 0, RAM 0, RUN 3350, CD INIT -10, TOC 0, TRACK 0, STATE 0, CODE 1, MVOL 0, ACK 0, CD L 255 / R 239. MVOL 0 is normal with the diagnostic panel idle. The zero pacing window does not measure performance.

This proves the direct SCSP/output path can make sound and that the effects bank and music table were not loaded. It does **not** prove a complete PCM driver path or CD-DA playback works. In `scd_audio_init`, any nonzero `cd_block_init` result skips both SFX.PCM and TOC loading; the later stage loader independently reads the disc, explaining why the level can still run.

The pinned [Yaul CD command source](https://github.com/yaul-org/libyaul/blob/6012f79f237773378c8014e70d8998ad95a38d98/libyaul/scu/bus/a/cs2/cd-block/cd-block_cmds.c) has two defects in `_return_status_check`: it decodes CR1's **low** report byte as status, then bit-tests status **enumerations**. The [Sega status specification](https://docs.exodusemulator.com/Archives/SSDDV1R1E/c/c04/hon/p089.htm) defines the actual status codes. Healthy report words such as `0102`, `01FF` and `030E` return the photographed `-10` under the old checker; a genuine `0A00` fatal status was missed. The photo does not contain raw CR1, so its exact response word remains unknown.

`tools/prepare_cd_block.py` generates a project-local override of the pinned command translation unit without changing the SDK/dependency. `src/cd_status.h` decodes the high status byte and compares the low-nibble code, while retaining WAIT/REJECT and genuine error propagation. The linked SH-2 disassembly confirms the corrected decoder is used by CD initialization. No error is simply ignored, no readiness is forged, and no firmware change is requested.

The sanitized regression compiles the generated command wrappers and the original SDK initialization sequence against a mocked transport. It reproduces the old bug, checks all 65,536 response words, 256 different report bytes through init/play/seek, and verifies real errors stop initialization. A new `INIT RESPONSE` panel field retains the most recent checked response from initialization for follow-up diagnosis. It is not a substitute for an audible hardware test.

## Test on the same console

1. Cold-boot the candidate BIN/CUE pair together. Check title music, NEW GAME music, jump and ring effects. Report which, if any, are audible.
2. Confirm the panel says **AUDIO TEST V0.040** after holding Start and pressing Z in gameplay. Test A (independent SCSP tone lasting about 1.5 seconds), B (ring through the 68000 driver), C (CD music), separately. A click/pop alone does not count as the tone working. Start+Z exits and resumes gameplay music. Use a comfortable low listening volume for the tone.
3. Send a photo of the panel and tell us whether A, B and C each make sound. The important fields are DRIVER READY/TIMEOUT; DATA, RAM, CODE; RUN; CD INIT, TOC, TRACK/STATE; CD L/R; and INIT RESPONSE. CODE, DATA and RAM should be 1, CD INIT 0, TOC 1, RUN should advance. CD L/R should be 255/239. MVOL normally reads 0 while the diagnostic panel has paused gameplay; it should rise to 15 while a probe plays. ACK is the driver's live request flag, not a fixed pass value.
4. The bottom line records the last completed 60-update gameplay window: `60 STEPS 60 VB MAX 1` means no missed refreshes in that window. Enter the panel after running the area where the game feels slow; a larger VB count shows misses. This is VBlank-relative, not a measurement of NTSC/PAL wall-clock frequency.
5. Check whether the side strips are gone and whether clouds still flicker. Record console video mode/region, SAROO firmware version and audio connection. If the tone is also silent, compare a known-working game on the same unchanged setup; do not change firmware or hardware to test this candidate.

Sound gate closes only after audible title/gameplay music **and** effects, simultaneous playback, pause/resume and repeated cold boots on the actual console. An emulator pass cannot close it. A click on pause alone does not establish which part of the audio path is failing.

## Candidate changes

- Word-wide sound RAM copies/readback (including odd PCM boundaries), word-wide SCSP memory-mode and CD-input mixer writes, and volatile master-volume access.
- Stop the sound CPU before download; explicitly set the 512 KB/16-bit-DAC mode; clear the entire 1,024-byte DSP program; verify the driver bytes before restart. Keep the pinned driver ABI and the genuine ready handshake. Do not forge readiness or swap driver binaries blindly.
- Diagnostics separate driver-code readback, effect-bank readback, driver activity, CD status and mixer registers. The direct tone requires neither disc samples nor a driver command.
- Original SCORE/TIME/RINGS digits, labels, life icons and time-post icons replace the prototype text panels/charge bar. Timing and movement constants are unchanged.
- The native 256-pixel title fills the 320-pixel Saturn display. Both sprite textures and backgrounds now sample the same global 205/256 hardware grid. Transparent sprite padding stays transparent when flipped. The enlarged title cache borrows Sonic's texture arena only during the title; display is disabled before texture restoration on exit. Returning to gameplay restores Sonic, normal zoom and HUD textures. Prewarming the banner during loading and optimizing sprite preparation preserve the original animation cadence.

## Measurements and limits

V0.040 focused verification passes on BIN SHA-256 `32e461959d053be26661675c222169d3b558280a0c72aa1666d9242a9ea79fe8`: all 14 fast gates (`build/qa-loops/20260919-165838-949274/report.json`), the 16,800-state gameplay replay, all three isolated audio probes, four-era music/pause/resume/looping, complete existing Act 1 regression (8,061 states and 1,805 exact HUD pixels), and all 1,196 exact full-width title pictures / 823 V-INTs. Pacing remains 1,851 VBlanks for 1,800 updates, 51 misses; full Act 1 remains 8,111 VBlanks for 8,060 intervals, also 51 misses. The emulator diagnostic capture visibly reads V0.040, DATA/RAM/TOC 1, CD INIT 0 and INIT RESPONSE 0000. Hardware audio remains unproven until the user retests.

The identical 1,800-update controller route took 1,860 VBlanks in preserved V0.037 (60 two-refresh intervals) and 1,851 in both V0.038 and V0.039 (51 two-refresh intervals). Misses cluster largely at ticks 216–463. The V0.038 full Act 1 route has 8,060 intervals across 8,111 VBlanks, also 51 misses. This finds real missed refreshes in the emulator, but does not reproduce a candidate slowdown relative to V0.037 or prove console performance. A non-blocking CD status experiment produced the same 51 misses, so it was removed rather than treated as a speed fix.

V0.039 focused checks pass: all 13 fast asset/source/sanitizer gates, the 16,800-state gameplay regression, audio era switching/looping/pause/resume, isolated tone/ring/music probes, source HUD compositions and ASan/UBSan sound-copy tests. The HUD asset test covers all four eras, zero/multi-digit/max counters and flashing ring labels. The ordinary Act 1 route matches 8,061 states / 128,976 words and checks 1,805 final HUD pixels against the original mappings; its 8,060 intervals span 8,111 VBlanks (51 misses). Both the title-to-gameplay capture and full-width title have been visually inspected. The candidate BIN SHA-256 is `d0f5e4139a6f8338e77fadbb0ea8a9d690137f440e341c08b79d9ee3db7f190f`.

**V0.039 passes the stronger full-width title gate:** all 823 retail V-INT states and their cadence match; all 85,729,280 pixels in 1,196 displayed frames equal the retail picture resampled at `floor(x*205/256)`. No adjacent-pixel tolerance is allowed. Both former side strips are included. NEW GAME, gameplay entry and game-over return also pass. The sampling helper passes 32,768 ASan/UBSan cases across origins, sprite sizes, flips, tile wrap and transparent padding. This fixes the measured emulator discrepancy; possible cloud flicker and timing on the real console remain unverified.

Historical V0.038 remains a failing title-visual candidate: 148,947 of 85,729,280 pixels exceeded its one-source-pixel tolerance. A background-only retail-render probe attributed 118,632 of those misses to exposed background under differently sampled sprite edges; sharing the hardware grid resolves the remaining measured differences too. The old candidate and its failing report have not been relabeled or overwritten.

No new full-release QA pass is claimed. Candidate reports bind to the exact BIN hash; historical reports in `dist/` may describe older builds and must not be bundled indiscriminately.

## Source comparisons and rationale

- [Sega SCSP startup specification](https://www.infochunk.com/saturn/segahtml_en/hard/scsp/hon/p01_20.htm): set MEM4MB and 16-bit DAC mode before downloading sound RAM, then release the sound CPU. [SCSP main-interface requirements](https://www.infochunk.com/saturn/segahtml_en/hard/scsp/hon/p03_10.htm) specify word transfers. The word-only changes remove an ambiguity; they are not proof that every previous SH-2 byte access failed (SCU behavior and software shared-memory accesses need separate consideration).
- [PoneSound](https://github.com/ponut64/SCSP_poneSound), local commit `c2b0d3a929d6f4f124fccad5f1e0359f8862c7e2`: inspect `PROJ/main.c` and `jo_cdda_demo/pcmsys.c`. Its initialization clears old slot/DSP state, reserves slots 16/17 for CD audio and uses a driver-published ready state. The current binary remains the pinned Yaul example's 8,732-byte driver; upstream's different binary was not assumed compatible.
- [PoneSound-SRL integration](https://github.com/bimmerlabs/Ponesound-SRL), `f860fd93f9944df0806a463d2d97c8dce05376b1`, `INC/ponesound.hpp`: comparable loading and PCM registration; its fixed delay is not substituted for our actual readiness/readback checks.
- [Mimas Saturn Doom port](https://github.com/mimasengine/mimas), `d8b47307a7561ba3edc8e43d26aeaf56221ddb3c`, `src/i_sound_saturn.cxx`: direct SCSP effects and distinct CDDA/driver modes, explicit master volume and reserved sound RAM. Its CDDA and synthesizer initialization paths have different ownership; do not combine them indiscriminately.
- [Sonic Z-Treme](https://github.com/Maxime-XL2/SONIC-Z-TREME), `cff75451c1616aac1236fc2b44223902b55c706b`, `Projects/SONIC Z-TREME/ZTE/ZT_AUDIO.c`: loads its sound driver/map before sound data; explicitly initializes CD playback, master level and both CDDA level/pan controls. Its proprietary SBL/SGL backend is a comparison, not a drop-in replacement for Yaul/PoneSound.
- [Sega System Library guide, ST-162](https://antime.kapsi.fi/sega/files/ST-162-062094.pdf), section 3.3: CD reports can be sampled without issuing a command. Tested as a pacing hypothesis, then rejected for this candidate because no measured improvement resulted.

These comparisons narrow the investigation to initialization, memory ownership, CPU/driver activity and the shared output path before blaming disc music alone. SAROO firmware or electrical faults have not been established. Do not flash, modify or tape console/cartridge contacts as a speculative fix.
