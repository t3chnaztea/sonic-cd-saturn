# V0.054 — original checkpoint respawn protection

Checkpoint respawns now grant the original 120-update protection window.
Previously the timer was missing after death at a saved checkpoint. Ordinary
fresh starts still have no protection. V0.053's source-based flashing is reused.
No audio, terrain, level layout or checkpoint clock rule is changed.

Host proof: 259 real death/reload cases, all 255 checkpoint IDs, 30,600 protected
states and damage on expiry, plus fresh starts in four eras. Untouched original
code supplies the saved-spawn reference. Archived V0.053 fails every saved
checkpoint case. All 30 fast gates pass. The Saturn route verifies 885 states
and the full 121-state countdown, including 60 hidden decisions. Main replay,
three-act sequence, 195 Sonic and 310 effect source pictures, world/camera,
title, audio/diagnostics and special-stage return pass on the same BIN.
All 32,916 unrelated main/sequence gameplay states remain exact versus V0.053.
Opening, standalone Act 1 and all three sequence acts have zero measured late
intervals. Audio/CD sources remain identical to console-confirmed V0.040.

BIN SHA-256:
`0df96d901b284a1622f89b4bac41c5462ddca7eb9aea943ef02dd2b9cd850f24`.

This is a focused candidate, not complete Palm Tree Panic or console acceptance.
The clock audit identified fractional-second restoration differences, retained
as an explicit separate finding in CHECKPOINT-FIDELITY.md. No card/Desktop copy.
