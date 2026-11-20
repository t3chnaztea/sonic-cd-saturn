# V0.052 — original shield and star effects

Focused checks pass; not complete-zone or physical-console acceptance.
BIN SHA-256:
`963f403847bc276f594b7eb89ea9429b3e44fc401f0edd4daa3a71dd272ea048`.

- Replaced provisional shield/invincibility/time-star frame formulas with the
  nine original scripts, including transparent frames, reverse animation,
  history phases, suppression/resumption and original initialization delay.
- Effects advance once per simulation update and join the original priority-1
  draw group. Their position history is captured before touch/object movement;
  monitor grants do not initialize a reserved actor before its next turn.
- Retained all earlier title, TV icon, camera, sprite composition and Sonic
  animation fixes. Physics, progression and audio rules are unchanged.

All 28 fast gates and focused target gates pass. The actor matches 36,948
isolated original CPU updates; actual Saturn telemetry matches another 10,186
CPU actor executions across 23,638 updates. All 47 script/pose pairs are covered.
310 pictures verify 158,569 effect texels and their overlaps with one another
and Sonic. Camera culling matches 13,211 original calls; runtime/culling cases
pass address/undefined-behavior sanitizers.

Main and recorded three-act gameplay remain exact across 32,916 states.
Title, world, special-stage return, music/effects and diagnostics pass. Opening,
standalone Act 1 and the three-act sequence retain zero measured missed
refreshes. All four audio/CD files match console-confirmed V0.040.

Limits: effect pictures exclude HUD bands and transparent background holes.
Wider ordinary-actor overlaps, source-identical time-travel scheduling, arrival
shield persistence, all-era routes and physical-console testing remain open.
The unidentified platform report is not closed by these effect checks.

The card is unchanged; V0.044 remains the last console-tested build. No new
level or CD++ gameplay change is included, and no recurring job was installed.
See POWERUP-VISUAL.md for the exact evidence and remaining boundaries.
