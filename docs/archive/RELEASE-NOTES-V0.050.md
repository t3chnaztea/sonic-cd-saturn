# V0.050 — correct falling animation after springs and disc release

Focused validation passes; see NEXT-SESSION.md. This is not a complete-zone
or hardware-accepted release. BIN SHA-256:
`1fda1a9804bb02808cd100aa945e4fd66871e6f49795dc934bdf4e0b4c8a13f8`.

- Restored the original descending-animation selection before gravity: unrolled
  Sonic returns to animation 0 at the apex, instead of remaining in a spring pose.
- Natural spinning-disc release now transitions out of its frozen pose on the
  next unrolled descending update. Jump-off and all six controlled poses remain
  covered. Rolled jumps, object ownership, bubble breathing and wind-tunnel
  exceptions are preserved.
- Added 2,400 real-player cases checked against the untouched retail 68000
  selector, 33 consecutive source-pixel spring pictures, and an old/new replay
  comparison that rejects any non-animation gameplay change.

All 25 host gates pass. Target replay/world/title/audio/isolated diagnostics,
special-return and the complete recorded three-act route pass. Opening, standalone
Act 1 and the sequence have zero missed refreshes. The sequence's
controller inputs and all non-animation state bits match V0.049. Main replay has
605 corrected animation bytes; Act 2 has 152; Acts 1 and 3 have none.
Source-pixel coverage is 195 pictures / 54 mappings, not every gameplay pose.

All four audio/CD implementation files still match hardware-confirmed V0.040.
The card is unchanged; V0.044 remains the latest console-tested build. Further
PPZ animation behavior, sprite priority, route/era coverage and hardware testing
remain open. See AIR-ANIMATION.md for reproduction and verification limits.
