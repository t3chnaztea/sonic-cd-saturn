# Original time-travel arrival and hurt display

V0.053 replaces the whole-actor copy at arrival with the original saved-state
boundary. This is a correction to Classic behavior, not a CD++ option.

## State boundary

The untouched original `SaveTimeWarpData` / `LoadTimeWarpData` routines save
integer X/Y coordinates, ground/X/Y velocities, flags, rings, ring-life flags
and clock (capped at five minutes), plus camera/bounds/water data. They do not
save the actor's subpixels, angle, animation, render/path flags, collision
scratch, object ownership, charge or hurt timer. `Level/Main` clears the object
pool and power-ups; `LoadPlayer` sets 120 updates of hurt protection for saved
spawns. `ObjSonic_Init` supplies fresh rendering and collision defaults.

The port now restores only the applicable saved actor fields after its normal
initialization. It clears standing/underwater flags, power-ups and stale actor
state; keeps ring/life/score progression and the existing capped clock; and
sets the original arrival protection. Rolling flags remain saved, but the
fresh actor uses the original initializer's normal-sized collision defaults.

`tools/test_player_arrival.py` executes those five retail code segments without
patching any instruction. It compares the real native adapter, under address
and undefined-behavior sanitizers, in 2,048 cases across all four eras, all 256
flag values and all eight shield/invincibility/shoes combinations. Fixtures
have deliberately dirty animations, subpixels, angles and scratch fields.
Native/retail mapping pointers are excluded because they are not portable
addresses. The hurt scratch word is explicitly converted from PC little-endian
storage into original big-endian field order.

The same test compiles the archived V0.052 player source as a negative control:
all 2,048 cases fail. The archived source hash must match its immutable candidate
manifest; this does not substitute a reimplementation of the old arrival code.

## Hurt flashing and ordering

The original display routine decrements the incoming hurt timer and bases
flashing on that timer's bit 2. The old renderer used the global simulation
frame instead. The new display decision is captured before touch/ordinary
object updates, so a late hurt/control change does not retroactively hide an
already-submitted sprite. Hurt/dead routines retain their direct drawing path.
Pause/read-only queries do not advance the timer or the captured decision.

An additional 2,080 real-player cases match the untouched original display
prelude: eight global clock phases, hidden-control states, timers 0..127,
511 and 65535. Animation-order tests separately verify late collision changes.
The world probe now checks every protected update, rejection of hits while
protected, and damage on expiration rather than expecting immediate damage
after arrival. This probe runs on the host and in the Saturn world test.

`tools/check_arrival_regression.py` binds the original proofs and old-code
rejection to two actual target hurt/landing routes. It checks 1,200 renderer
visibility decisions against their corresponding physics/presentation traces,
including two complete 120-update protection countdowns. It also retains exact
comparison of the unrelated main and three-act gameplay routes with V0.052.
Target visibility telemetry is not an independent hidden-frame pixel oracle.

## Remaining travel audit

This does **not** establish complete original time-travel behavior. Native
travel still runs after ordinary objects rather than inside Sonic before
movement. The exact save frame, camera/bounds restoration, checkpoint reload
clock/first-update timing and original landing relocation need further audit.
V0.054 adds the missing checkpoint spawn protection; see CHECKPOINT-FIDELITY.md.
The existing
native collision-clear landing search remains unchanged. Tests use clear
coordinates for the state comparison; an existing separate route checks that
the relocated destination can be exited. All-era natural travel routes and
physical-console confirmation remain required. V0.052 remains preserved.
