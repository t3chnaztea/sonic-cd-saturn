# Japanese soundtrack

The user selected the Japanese soundtrack on September 21, 2026. The build
uses the supplied Japanese disc for music independently of the existing
graphics, gameplay-reference and sound-effect inputs.

Create the private local link once:

```sh
mkdir -p assets/private
ln -s "/path/to/Sonic the Hedgehog CD (Japan).cue" assets/private/sonic-cd-japan.cue
bash tools/build.sh
```

The referenced BIN files must remain alongside the original CUE. The selector
resolves the link before opening relative FILE paths. The link points to
your own dump of the Japanese disc. Private inputs and
extracted tracks are ignored by Git.

`tools/prepare_audio.py` prepares the existing effects and Palmtree Panic Past
track. `tools/prepare_japanese_music.py` then selects all Japanese music. It
validates the Japanese disc header, reads each CUE INDEX 01, excludes stored
pregaps, and copies the 27 supported CD-DA songs without resampling. Seven
Past tracks come from the supplied disc's original `SNCBNK*B.BIN` PCM drivers.
A missing or mismatched source fails the build; packaging requires the full
34-track Japanese music bank.

## Stage routing (V0.059)

These are Saturn disc track numbers. Slots 2–11 retain V0.058's exact bytes;
the remaining zones append their own music.

| Zone | Present | Past | Good Future | Bad Future | Japanese CD-DA source (present/good/bad) |
| --- | --- | --- | --- | --- | --- |
| Palmtree Panic | 2 | 3 | 4 | 5 | 3 / 4 / 5 |
| Collision Chaos | 12 | 13 | 14 | 15 | 6 / 7 / 8 |
| Tidal Tempest | 16 | 17 | 18 | 19 | 9 / 10 / 11 |
| Quartz Quadrant | 20 | 21 | 22 | 23 | 12 / 13 / 14 |
| Wacky Workbench | 24 | 25 | 26 | 27 | 15 / 16 / 17 |
| Stardust Speedway | 28 | 29 | 30 | 31 | 18 / 19 / 20 |
| Metallic Madness | 32 | 33 | 34 | 35 | 21 / 22 / 23 |

Results, speed shoes, invincibility, special stage, boss and title retain
Saturn tracks 6–11, from Japanese retail tracks 28, 29, 30, 32, 24 and 26.
Act 3 selects the applicable future song. Power-up expiry, boss completion,
mode return and travel cancellation restore the current zone's era song.
Changing zones also changes the song when the era number stays the same.

The runtime separates the logical music cue from its disc slot. Stage loads
set the zone explicitly; temporary event songs leave that zone intact.
Playback, pause positions and looping use the resolved disc slot. The full
requested track number is exposed in the audio mailbox; the older packed
status word retains its logical-cue layout so track numbers above 15 cannot
overlap its pause/status bits.

## Past music and verification

Each additional Past bank is captured in the pinned offline Sega CD core,
using the original alternating IRQ3 update cadence. Capture caches bind the
bank, capture code and core by hash. The loop detector compares active
sequencers: the original `HandleTempo` routine increments duration counters
even on stopped channels, which must not extend the musical loop. Palmtree
Panic's established capture remains byte-identical. Output uses the existing
gain and three-second ending fade, with sector padding. Disc seek/restart
looping is not gapless.

`build/feedback-source.json` records the seven driver hashes and repeat
observations, plus each CD-DA source file, INDEX 01 and PCM hash.
`dist/build-report.json` records final track positions. Packaging reads every
track back from the combined BIN and checks its hash.

- `python3 tools/test_japanese_music.py`: CUE boundary cases, original-disc
  bytes, all 28 native zone/era routes, event slots and repeat policy.
- `python3 tools/test_feedback.py`: generated music and effects.
- `python3 tools/test_zone_music.py`: actual Saturn playback and controller
  era switching in all seven zones; silent pause, fixed pause position and
  resume in all 28 cases; final disc track loops after resume.
- Existing audio, title, world/power-up, continuous-zone, big-ring and
  ring-loss stress checks guard event music and gameplay regression.

The bank contains 51.87 minutes of audio. Hardware acceptance remains open.
Music for features that are not yet implemented (such as the ending) is
outside the current runtime's supported cues.
