# Console checklist: V0.080 hardware-risk tests

**Watch every FMV for stutter.** The movies stream at the default 2x, so the
CD buffer fills and the drive pauses and resumes all movie long (normal CD
block use, but SAROO's handling is untested with these streams). Any stutter,
sound repeat or freeze in a movie is the first thing to report; a 1x stream
build can be made if it happens.

Each test targets behaviour that Beetle
Saturn models differently from a real Saturn with SAROO. Run them on the exact
candidate BIN, in this order, from a cold power-on. For every test record:
pass/fail, the time into the test, what was on screen, and whether the console
needed a reset. A freeze means no input response for 10 seconds or more.

Setup to record once: BIN SHA-256, SAROO firmware version, console region and
video mode, audio connection, and whether the internal backup memory is
nearly full.

## 1. Movies (CD streaming)

The movies stream from the CD at 2x while the sound plays at the Sega CD
rate. Beetle does not model SAROO's pause and resume when the CD buffer is
full, so only the console shows whether the streams play cleanly.

1. Power on and leave the title screen alone until it plays the opening
   movie. Watch it to the end without pressing anything.
2. Open Visual Mode and play every movie to the end, the pencil test
   included. Return to the menu after each one.
3. Finish the game once for each ending, or use the existing ending saves,
   and watch the ending movie and the "PRESENTED BY SEGA" card. On the
   Japanese card, press Start to leave it.

Fail if any of these happen:
- the picture stutters, freezes or runs ahead of the sound;
- the sound repeats or drops out;
- the movie never starts and the screen stays black for more than 10 seconds;
- the movie does not return to the title, the menu or the card.

## 2. Long CD session (overlay and pack loads)

Each zone change, the title, every movie, the credits and D.A. Garden now
read code or data from the CD. A failed read now retries 3 times before the
"CD STAGE DATA ERROR" or "CD ZONE TABLE ERROR" screen.

1. Play for at least 30 minutes through several zones. Include time travel
   in both directions and at least one special stage.
2. Go back to the title at least 5 times. Enter Visual Mode and D.A. Garden
   from the title in between.

Fail on either CD error screen, a hang during loading (black screen for more
than 10 seconds), or a visible pause of more than about 2 seconds at a zone
or title load. Write down the file name the error screen shows.

## 3. Quartz Quadrant Act 2 full background redraw (slave CPU)

The second SH-2 draws half of the background when the far background of
Act 2 changes (GAME5 enkeichg; the stored A route reaches it near X 3611,
Y 842). It now has a 30 V-blank timeout. If it fails, the main CPU draws both
halves after a pause of about half a second.

1. Play QQ Act 2 in Present (A) and in Good Future (C).
2. Cross the point where the far background changes at least 3 times in each
   era (walk back and forth across it).

Fail on a hang, on wrong or garbled background rows after the redraw, or on
a pause of about half a second each time the scenery changes. That pause is
the fallback working; it means the slave missed its job, so report it.

## 4. D.A. Garden entry (slave CPU)

D.A. Garden renders its planet on the second SH-2. The main CPU now repeats
its request every V-blank until the slave answers. After 60 V-blanks the
main CPU takes over for the rest of that visit.

1. Enter D.A. Garden from the title 5 times and stay at least 20 seconds
   each time. Move the planet and change tracks.

Fail on a freeze of about 1 second when entering, a picture that stays
behind for about a second at every move (the fallback taking over), garbled
planet images, or a hang.

## 5. VDP1 load (dense scenes)

The frame-time headroom figures are CPU-only Beetle measurements. VDP1 draw
time on hardware has not been measured. A debug counter
(scd_world_mailbox[143]) now counts V-blanks at which VDP1 had not finished;
it is not shown on screen.

1. Play the busiest scenes: the Metallic Madness Act 2 and Act 3 dense
   sections and the Metallic Madness boss, the Stardust Speedway race, the
   ending credits roll, and D.A. Garden.

Fail on slowdown, sprites that flicker or vanish for a frame, or torn and
partially drawn sprites. Note the scene, the zone, the act and the era.

## Report back

One line per test: number, PASS or FAIL, and a note. Also give the setup
line. Any freeze or error screen: a photo of the screen, if possible.
