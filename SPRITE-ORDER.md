# V0.051 — original actor draw priority

Focused candidate validation passes. No physical-console claim. BIN SHA-256:
`8e21f5b6346d74a6d6a05936e132f6c42b279fa825f4e55c4e4fe11207e15209`.

## Correction

The prior renderer split a few special actors into pre-player loops, then drew
most ordinary actors after Sonic. That reversed the original overlap for, among
others, monitors and the projector. It also drew equal-priority actors in forward
native slot order, giving later actors precedence rather than earlier ones.

`src/sprite_order.h` merges Sonic, visible native actors and boss parts into eight
priority buckets. Lower source priority is closer to the viewer. The Mega Drive
retains the first opaque sprite pixel, whereas Saturn VDP1's painter overwrites
earlier pixels. The native queue therefore emits priorities 7 through 0 and
reverses submission order inside each bucket. It uses linked byte indices, not
copies or a comparison sort of full VDP1 commands.

`scd_ppz_priority` derives ordinary priorities from original initializers. This
includes state-dependent checkpoint orbs, capsule seeds, Tamabboh missiles,
holographic animals and front/rear ramp plants. Boss parts retain their original
`actionsub` priorities and call order. Sonic uses priority 2.

## Independent checks

- `tools/test_sprite_order.py` executes the untouched retail `DrawOtherObject`
  68000 routine 39,881 times across 512 deterministic lists. It reads the original
  queue memory, reverses the resulting SAT order and compares every native index.
- `tools/sprite_priority_reference.py` parses original assembly initializers and
  the original swing source independently of the native table: 159,744 metadata
  cases across 39 object kinds. Hashes identify the exact reference files.
- Sanitized tests cover native capacity, malformed inputs and output guards.
- The monitor oracle now composes the source Sonic pose in front of the source
  TV. It still checks every opaque TV texel, including the overlap, across 100
  captured frames. The projector oracle similarly merges original actor/Sonic
  pixels and foreground priority, enforcing original actor priority groups.
- Current target checks pass 83,300 monitor texels / 2,100 Sonic-overlap texels,
  six projector/animal pictures, all three Amy captures and the existing world
  checks. Two projector captures each include five Sonic-overlap texels.
- `tools/check_sprite_order_regression.py` rejects all five immutable V0.050 TV
  pictures and the old projector picture at actual pixel mismatches, using
  current source poses. It verifies all 32,916 main/three-act gameplay states
  and controller inputs remain exact, including animation state.
- All 26 fast gates, the main target replay with 195 source-pixel pictures,
  exact recorded three-act sequence, special-stage win/return and title pass.
  The sequence has zero missed refreshes over 8,060 / 5,192 / 2,861 intervals.
- Final music/effects, isolated audio diagnostics and standalone Act 1 pass.
  Opening and standalone Act 1 have zero late intervals over 1,800 and 8,060.
  All four audio/CD implementation files still match hardware-confirmed V0.040.

## Deliberate limits

This does not emulate the original 63-actor per-priority overflow or hardware
sprite-per-line limits. All admitted native actors are retained. The current
native actor-slot lifecycle is not proven identical to original allocation.
Within-priority ordering is tested against the original queue algorithm for
given submissions, not claimed to prove every original dynamic allocation.

Generated shield, invincibility and time-travel trail effects remain outside
this merged actor queue; their ordering still needs a separate audit. HUD,
title-card and results layers remain overlays. Broader overlap routes, all-era
coverage, original rendering edge cases and console acceptance remain open.

Next source-backed follow-up: `_Objects/Powerup/Main.asm` initializes the shield,
invincibility and time-travel star actor at priority 1. Current effects are
generated after ordinary actors, so their overlap with priority-0 scenery and
equal-priority actors needs its own fixtures and submission-lifecycle audit.

No physics, collision, camera, audio or gameplay-rule change is intended.
The previous V0.050 candidate and raw traces remain preserved for comparison.
