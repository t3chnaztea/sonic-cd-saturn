# Original sprite-piece order — V0.048

Development BIN: `95224d40113a0fe4730e6faab86674050c17867c5d4c838b4dd94d1a43bb3eaf`.
Host composition checks and all focused same-BIN runtime gates pass. This is
not hardware acceptance or complete visual-fidelity coverage.

## Evidence and correction

`Level/Object Functions.asm` `DrawSprite` walks each five-byte mapping record
in order and increments the SAT link. All four flip branches retain that order.
The pinned reference renderer's `make_lut_obj` preserves an earlier opaque
sprite pixel, irrespective of the later piece's priority bit. PC `ACTION.C`
`spatset` likewise traverses its source piece list in increasing link order.
The legacy converter painted later pieces over earlier ones. V0.045 corrected
only monitor callers; V0.048 makes first-piece-front the normal policy.

The old V0.047 generated artwork is preserved at
`build/composition-v047-baseline`. Its audit independently finds **33 remaining
incorrect compositions / 5,032 pixels**. The new test fails that build at
object frame 24 (`negative-test.log`); the old snapshots were not replaced.

| Object group | Global frames corrected | Corrected pixels |
| --- | --- | ---: |
| Anton | 24–27 | 82 |
| Mosqui | 37 | 8 |
| Pata-Bata | 43 | 18 |
| Taga-Taga | 44, 45, 48, 49, 51, 52, 55, 56 | 778 |
| Robot generator | 79–85 | 2,176 |
| 3D ramp booster | 98, 103–106 | 1,692 |
| Amy | 299–301 | 151 |
| Boss | 342, 351–353 | 127 |

The audit's old `source_context` field was only the converter's last `path`
local, not guaranteed source provenance: boss entries therefore displayed
"Springboard" there. Frame/catalog IDs correctly identify them as boss frames.
The current audit labels that variable `selection_context` and records catalog
IDs. Actual extracted boss maps/tiles and other consumed source files are
hash-bound in the independent report; no Springboard change is claimed.

## Independent checks

`sprite_composition.source_sprite` walks every destination pixel and then
searches the original piece list, stopping at the first opaque texel. It does
not call the production piece painter. Synthetic checks protect transparency,
opaque black, sprite-list priority, column-major tile order, both piece flips
and truncated-art rejection.

`audit_sprite_composition.capture` invokes the real converter in an isolated
temporary output tree to obtain its selected source inputs. It never rewrites
the working assets. Its output must reproduce the working generated artifacts
byte-for-byte. This verifies composition independently, not every animation or
mapping-selection decision.

`test_sprite_composition.py` verifies **391 compositions / 1,515,328 pixels**:
382 object frames and nine title-card frames. It independently decodes packed
4bpp textures and CLUTs, including transparent pixels and crop origins. The ten
Sonic-derived frames bypass this object painter and remain covered elsewhere.
All 30 existing object tests pass. Historical first-183-frame checks still
require unchanged hashes except known corrections, where the old hash must
match an independently reconstructed legacy image and the new image must match
the original first-opaque-piece rule.

A separate full before/after comparison of all **392 object frames** confirms
exactly the 33 / 5,032 changes above. Widths, heights, crop origins, canvas sizes,
vertical shifts, palette banks and priority assignments are unchanged for
every frame. All 391 selected mappings have uniform palette/priority bits
within each composition; the boss's mixed-palette body is already split.

Decoded object storage grows from 345,344 to **348,288 bytes**, still within
the reserved object arena and below the special-stage UFO texture boundary.
Existing 32-byte texture/CLUT alignment assertions remain enforced.

## Target and acceptance boundary

The world checker requires the independent source report and its 127 consumed
input hashes to match current files, then binds it to the full target object
VRAM readback. The candidate packager requires that same source/world evidence;
stale generated assets, source data or reports cannot silently pass packaging.

This proves selected source compositions and their loaded texture bytes when
the target gate passes. Existing world routes also exercise motion, foreground
priority, Amy, monitors and other objects. It does **not** prove every corrected
animation frame is exposed in a gameplay screenshot, every cross-object
occlusion or real-console presentation. Keep those coverage/hardware limits
open rather than equating texture correctness with complete PPZ acceptance.

The final world check verifies all **348,288 target object bytes** and keeps
the camera coherence checks unchanged (16 pictures / 3,451 spring, 92,064
terrain and 107,520 clear pixels). Amy's pixel checker now permanently uses the
independent compositor, not the production painter. All three target captures
pass; the preserved V0.047 capture fails at (161,134), where it draws black
instead of the original pink. Each new capture changes exactly 15 pixels.
The world report and package also bind the Amy checker/source hashes and
preserve its three screenshots. Evidence:
`build/world-v048-independent-final.log`, `build/composition-v048-amy-negative.log`.

All 22 fast gates pass (`build/qa-loops/20260920-004935-825759/report.json`).
The 16,800-state main replay, audio/isolated diagnostics, 823 title V-INTs and
1,196 pictures, full sequence/Act 1, big-ring return and opening pacing pass on
the same uninstrumented BIN. All three sequence trace files are byte-identical
to V0.047: 16,116 states, with zero missed refreshes in 8,060 / 5,192 / 2,861
intervals. No gameplay or audio source change was made for this correction.

Reproduce host checks:

```sh
python3 tools/test_sprite_composition.py
python3 tools/test_objects.py
python3 tools/audit_sprite_composition.py build/new-composition-audit.json
```

The audit refuses to overwrite an existing report. Same-BIN runtime logs use
`build/*-v048.log`. V0.047 candidate and its source archive remain untouched;
no card/Desktop deployment or scheduled job was performed.
