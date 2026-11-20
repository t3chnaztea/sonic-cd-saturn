# Original Sonic animation — V0.049 integration

This work addresses PPZ-GFX-002. V0.049 now links the original
60-script dispatcher to the player actor and renders its original mapping and
flip state. The 21-pose atlas remains only for explicit static diagnostics.
No card deployment or hardware acceptance has occurred. Current final-build
gate status is recorded in NEXT-SESSION.md; do not infer full-zone acceptance
from the component results below.

## Integrated runtime and evidence

- Normal, controlled, hurt and death updates animate at the original point,
  before subsequent object processing. Gone/results freeze do not advance the
  script. Reset clears the actor fields; travel retains them while releasing
  object control. FD transitions update the actual actor, not a renderer clock.
- The disc writes the next script cursor after player processing. Rendering
  now uses the actual mapping, removing the premature cursor-based shortcut.
  The separate Amy idle rendering shortcut is also gone; the actor supplies
  the displayed idle pose. The old Amy idle clock remains diagnostic-only and
  must be retired when its legacy probe/hash observations are migrated.
- Angled source artwork and original H/V flips replace continuous rotation.
  Original priorities place the disc (4) behind Sonic (2), and Amy (1) ahead
  of Sonic with hearts (3) behind. Broader actor priority coverage remains open.
- Actual host player calls: 652 boundary cases, 16,680 replay calls and 67,967
  world-route calls match unmodified retail 68000 execution exactly. Boundary
  tests cover delayed object choices, all six disc mappings, FD transitions,
  results freeze, death-to-gone, placement reset and time travel.
- A separate target presentation trace preserves the existing physics ABI:
  16,800 host/reference/SH-2 states, including 83 mapping IDs, match in mapping,
  render flags, animation IDs, cursor/timer and control. The 16,800-state
  historical gameplay trace is unchanged in the tested replay.
- Sampled gameplay pictures: 162 captures / 49 mappings across all four Act 1
  eras; 99,976 visible Sonic pixels and 1,596 foreground-occluded pixels match
  original mapping/DPLC artwork and path-selected terrain. These eight
  controlled fixtures do not cover every pose or arbitrary actor overlap.

## Streaming and rejected runtime approach

The first integrated version composed DPLC tiles on a cache miss. Preserved
BIN `a2c95e003d3cdc13a4a911823bbf47c9bf45c34d072ae1b311592c7e6e74d1c4`
in `build/v049-runtime-dplc` misses 40 of 1,800 opening refresh intervals. Its
disc pictures also expose late first-pose presentation; it is not a candidate.

`tools/sonic_frame_assets.py` now composes **all 198 original poses** at build
time using the bounded native source decoder, independently checks all 811,008
expanded pixels against the source renderer, and losslessly word-RLE compresses
them. `src/sonic_frames.c` expands that **96,578-byte** indexed pack during play.
The first compressed build restores zero misses over 1,800 opening intervals.
No poses, angle variants or animation timing are reduced to obtain this result.
The final priority-corrected BIN also passes the opening, standalone Act 1 and
recorded three-act sequence with zero missed refreshes; see PERFORMANCE.md.
All focused transition/title/audio/world gates pass on that same BIN.

`PACK_SONIC_FRAMES` occupies `0x002CC000..0x002E4000` (capacity 98,304). Both
special-stage exit paths reload it before gameplay. Eight 2,080-byte texture/
CLUT cache slots occupy `0xB000..0xF100` in VDP1, after the HUD and before the
static diagnostic atlas. Each stage/title/special return invalidates the cache
after the preceding VDP1 list is finished. Uploads occur only while the old
gameplay list is idle; the concurrent clear-only list does not sample textures.
Sanitized streaming checks cover 1,188 all-pose uploads across three simulated
arena-overwrite generations, cache hits, adjacent VRAM guards and malformed/
truncated input. Physical-console bandwidth remains a separate check.

Adding actor presentation fields exposed SH-2 aggregate-return stack growth in
the diagnostic probe (10,252-byte frame). Field-only QA reads now reuse one
non-recursive snapshot, reducing that frame to 4,484 bytes without removing any
assertion. `build/world-animation-timeout.png` retains the initial CPU exception;
the revised target semantic probe gets through all diagnostic groups.

## Verified source and components

- `src/sonic_animation.c`: normal-sized Sonic's original animation dispatcher, with byte/word wrap semantics, state-change resets, timing, FF/FE/FD script control, speed/angle/flip selection, pushing, 3D ramp run/roll, and externally indexed frozen frames. Miniature-Sonic mode is outside this Palmtree Panic component's scope.
- `src/sonic_art.c`: bounded native DPLC/mapping decoder producing one 64×64 4bpp texture and original palette colors. It preserves original piece priority and per-piece flips; global sprite flips remain separate. It rejects invalid frame IDs, out-of-range pieces, truncated data and oversized DPLC loads.
- `tools/sonic_animation_assets.py`: verifies all 60 scripts against both retail R11A bytes and PC PLCHG.C; assembles and verifies the original mapping/DPLC tables and art against the disc. It creates `assets/generated/sonic-animation.inc` and `sonic-source.bin`.
- The source pack is **74,184 bytes**: 69,472 bytes of indexed art (including the original alignment byte), 3,004 mapping bytes, 1,636 DPLC bytes, 32 palette bytes, and a 40-byte header. All **198** mappings fit within a 64×64 frame (overall bounds X −28..24, Y −32..32); at most six pieces and 23 DPLC tiles are used. Mapping palette/priority bits are zero, consistent with the common Sonic palette.

## Independent verification

Run `bash tools/test-sonic-animation.sh`.

The reference is the **unmodified retail R11A ObjSonic_Animate machine code**, located by a verified instruction signature. The pinned Genesis Plus GX 68000 CPU runs it in an isolated flat-memory fixture with normal-size Sonic, an actor record, a return stack and a halt-loop sentinel. No gameplay/BIOS/disc file is modified. The native C dispatcher does not supply the oracle's logic or data. Every call verifies that the retail routine returns and does not change unrelated actor bytes.

**139,264 states match exactly**, including timelines for all 60 animation IDs; all 256 angles; both facings; pushing/ramp combinations; signed speed boundaries (including −32,768); frozen externally selected poses; and deterministic randomized transitions. The animation tests exercise 162 mapping IDs; the independent decoder test separately covers **all 198 poses / 811,008 pixels**, including 93,573 opaque pixels, against original source mapping/DPLC rendering.

The CPU-oracle cases are replayed under AddressSanitizer and UndefinedBehaviorSanitizer. All pixels, output guards, invalid animation/cursor handling and pack truncation checks pass. Both modules also compile for SH-2 with warnings treated as errors (1,424 and 1,149 bytes of text/data respectively in the standalone object-size report). This is compile evidence, not target runtime/performance acceptance.

Evidence: `build/sonic-animation/source-report.json`, `retail-report.json`, `retail-cases.bin`, `sanitized.log`, and `build/sonic-animation-final.log`. Reports identify retail/core/source/pack hashes. The fast QA command list now includes this new gate; the existing V0.042 archive retains its original 16-gate evidence unchanged.

## Original integration checklist and remaining scope

1. Actor state, update order, mapping/flip observability and removal of double
   rotation are implemented with the new independent checks above.
2. Texture ownership and both special-return reloads are implemented; retain
   the same-BIN transition, audio, title, camera and full-sequence gates.
3. Finish target coverage for all required poses and motion sequences, including
   stationary controlled poses, balance, look-up/crouch, skid, spring, hurt/death,
   ramp and wall/ceiling angles. Sampled stills are not exhaustive motion QA.
4. Retire the diagnostic-only Amy clock and expand source-priority overlap
   checks beyond the known disc/heart cases. Validate on Saturn/SAROO.

Remaining actor-dispatch omissions (e.g. idle-event selection) must be audited
separately: a correct interpreter is not proof that gameplay selects every
original animation at the right time. Miniature Sonic is still outside this
Palmtree Panic integration. No other zone work or cron activation occurs here.
