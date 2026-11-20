# V0.056 — original checkpoint clock restoration

Checkpoint respawns now discard fractional seconds, matching the original
saved-spawn clock boundary. For example, a saved 1:23.50 resumes at 1:23.00.
The five-minute checkpoint cap, stored checkpoint record, fresh starts, lives,
score, protection timer and ordinary per-update clock progression are unchanged.

Independent original-CPU and real native death/reload tests agree across 1,444
cases and 174,724 clock states. The preserved V0.055 source fails 1,180 fractional
cases. Actual Saturn execution verifies the sampled checkpoint's 32 ticks reload
as zero, followed by 120 consecutive correct ticks. Two HUD captures match
2,653 opaque original-art pixels. All 33 fast gates pass.

The full Good Future route still completes both generators, all three acts,
boss/capsule/results and title return. Its 26,029 input/state rows are unchanged
from V0.055, with zero missed refreshes over 26,023 measured intervals and 7,722
source HUD/results pixels verified. Broader regression also passes: all 32,916
prior main/Bad Future sequence gameplay states remain exact; 195 Sonic and 310
effect source pictures, title state/art, arrival/checkpoint/sprite-order proofs,
audio/diagnostics and special-stage return pass. Opening, standalone Act 1 and
the three Bad Future sequence acts have zero measured missed refreshes. All four
audio/CD sources still match hardware-confirmed V0.040. Packaging status is kept
in NEXT-SESSION.md. No physical-console acceptance is claimed.

BIN SHA-256:
`a8a9ce0721fc977a70153b4313a16d2f8a9575cee453ac02a8437f221cecdbe9`.

Palmtree Panic is not finished. Next clock audit: title-card control locking
versus the original HUD tick order. Camera initialization/following, alternate
routes and hardware visual checks remain open. No new zone or audio changes.
