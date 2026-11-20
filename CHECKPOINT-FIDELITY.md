# Checkpoint respawn audit

## V0.056 clock correction — development verification

Saved checkpoint reload now discards fractional ticks. The saved checkpoint
record still retains the capped original ticks; only reload changes. Independent
retail execution and real native death/reload agree in 1,444 cases / 174,724
clock states, including all 60 fractions at second/minute boundaries and the
five-minute cap. Archived V0.055 fails 1,180 fractional cases. Fresh starts in
four eras remain zero and ordinary progression stays one tick per update.

Boundary justification: Level/Main's fade/load VInts do not call UpdateHUD.
The first normal Level_MainLoop VInt calls it before RunObjects. ObjSonic_Init
then returns without movement or decrementing the 120-update hurt timer. The
native reset publication represents that initialized saved-spawn clock boundary,
not the original loader's intermediate invalid seconds byte. The test executes
the untouched Save/Load, LoadPlayer, Init and clock instructions, then compares
120 subsequent ordinary ticks. This is not a full fade/actor/camera equivalence
claim. Actual Saturn clock/HUD verification and packaging status: NEXT-SESSION.md.

Tools: `tools/test_checkpoint_clock.py`, `tools/checkpoint_clock_test.c`,
`tools/check_checkpoint_clock_target.py`. Current and negative reports live in
`build/checkpoint-clock`; the expected old failure is kept, not relabeled green.

## V0.054 protection correction (retained)

V0.054 restores the original saved-spawn protection at checkpoint respawns.
`LoadPlayer` sets the hurt timer to 120 for any nonzero spawn mode, not only
time travel. The checkpoint object saves spawn mode 1; `LoadCheckpointData`
restores it before `LoadPlayer`. Fresh starts do not receive protection.

The native death/reload branch previously reset the actor without restoring
that timer. It now sets 120 only when loading a saved Present checkpoint.
This uses the source-backed hurt countdown and flashing from V0.053. Position,
life loss, score, cleared rings/power-ups, camera and clock rules are unchanged.

## Independent checks

`tools/test_player_checkpoint.py` executes untouched retail checkpoint save,
load, player creation, power-up clear and clock-update instructions. Its native
fixture compiles the actual player/objects code with address and undefined-
behavior sanitizers and goes through death and respawn, not a mock loader.

- 255 checkpoint IDs exercise saved coordinates, clean inventory and protection.
- Each case attempts damage through all 120 protected states, checks every
  decrement/display decision, then verifies damage is accepted after expiry.
- Four no-checkpoint cases cover fresh starts in all eras with no protection.
- The archived V0.053 player fails all 255 checkpoint cases; the four fresh
  starts remain valid. The archived source is pinned to its immutable manifest.

`tools/check_checkpoint_regression.py` binds these proofs to the Saturn
controller route and checks the complete 121-state respawn/countdown boundary.
V0.054 captures 885 route states, respawn at simulation update 264 (capture
frame 6578), and 60 hidden decisions across the 120 countdown updates. The
first harness pass also captured stale prior-fixture state during loading;
the checker rejected it. Capture now requires the published checkpoint fixture
ID as well as matching simulation numbers. The same-BIN rerun passes; the
first raw run remains under `build/world-v054-first-qa`.
This is actor and renderer-decision telemetry, not an independent pixel oracle
for hidden Sonic/background frames. Hardware verification remains required.

## Clock finding — not changed in V0.054

The original saves a clock capped at five minutes. On load it sets frames to
59 and subtracts one from the seconds byte; the first normal HUD tick restores
the saved whole second, dropping fractional frames. At zero seconds that byte
temporarily becomes 255, then wraps to zero. It does not borrow a minute.

The retail CPU checks cover all fractional frames across second/minute edges
and the five-minute cap. Reports retain raw pre-update clock bytes and the
first normal HUD result. Through V0.055, native reload preserved exact saved
ticks; V0.056 corrects the boundary as described above. The protection test
still does **not** double-count its clock observations as clock parity.
Camera/bounds restoration,
fresh actor movement flags and non-Present checkpoint persistence remain open.

The saved foreground camera fields are loaded by LoadCheckpointData, but PPZ1
LevelSizeLoad_StartPos subsequently recomputes camera X/Y from player position
(Y minus $60), then LevelScroll runs. Future camera work must audit that entire
sequence and the era-specific background setup, not merely copy saved X/Y.
