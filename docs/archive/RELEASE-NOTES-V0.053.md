# V0.053 — original travel arrival and protection flashing

Focused checks pass; not complete-zone or physical-console acceptance.
BIN SHA-256:
`df0e79f8d93b0061f25bca6111827dc7c7bcf243fa8fc8e0663e927f699f7bbd`.

- Time travel now restores only the original saved actor fields into a fresh
  actor. Power-ups, stale animations, subpixels, angle/path and ownership scratch
  no longer incorrectly carry across. Rings and progression remain preserved.
- Arrival now grants the original 120-update protection. Sonic's flashing uses
  the incoming hurt timer rather than the global frame phase; late collision
  changes do not retroactively hide that update's submitted sprite.
- Earlier title/TV/camera/Sonic/effect fixes remain intact. Audio/CD code is
  identical to the console-confirmed V0.040 implementation.

All 29 fast gates pass. Untouched retail CPU routines verify 2,048 native arrival
cases and 2,080 display decisions under sanitizers; the archived old adapter
fails every arrival case. Two actual Saturn hurt/landing routes verify 1,200
display decisions, two full protection countdowns and 64 incorrect old flash
decisions. This telemetry is not independent hidden-background pixel coverage.

All 32,916 unrelated main/three-act gameplay states remain exact versus V0.052.
The 195 Sonic and 310 effect source-picture checks, world/camera, title,
special-stage return and audio/diagnostic gates pass on the same BIN. Opening,
standalone Act 1 and all three sequence acts retain zero measured missed
refreshes. V0.052 remains preserved as the previous candidate.

Still open: original travel/save-frame scheduling, camera restoration, landing
relocation, checkpoint spawn protection, broader PPZ routes and hardware testing.
The existing collision-clear landing search is unchanged. No new level/CD++
behavior or recurring job was added. The card is unchanged; V0.044 remains the
last console-tested build. See ARRIVAL-FIDELITY.md for evidence and limits.
