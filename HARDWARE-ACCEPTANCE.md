# Hardware acceptance: V0.082 candidate (software regression passed, console test reported working)

## Quick reference

Purpose: the console test handoff. `tools/package-hardware-candidate.py` ships
this file as `READ-ME-FIRST.md` and asserts line 1 names the Makefile
`IP_VERSION`. Update line 1 for every hardware build.

Current state (2026-11-21):

- V0.082 BIN SHA-256 `cb872d149ba3575d9929a1072bb006dd403b97e79dfdfa0a6b4782bf178a3e66`
  (tested game source `49bfd89643b2a77962964a988e87b75a46e9b7a6`).
  Full regression passed215/215; matrix347/347; art70 cases,0 misses.
  Exact evidence and CUE hash: `RELEASE-NOTES-V0.082.md`.
  SAROO folder: `/Volumes/Untitled/SAROO/ISO/Sonic CD Saturn v0.082`.
  BIN/CUE card readback verified on2026-11-20. Transfer receipt:
  `build/release-deployment-v0082-20261120/sd-transfer.json`.
  Console result 2026-11-21: "tested and working on my saturn"
  (`hardware-results/v0.082.json`). The report did not itemize the checklist
  below, so its individual items stay unrecorded.
- V0.079 (BIN `3370c557…32b8`) is the fallback package; V0.078 and earlier
  BINs embed the build machine's home path, so never share them.
- V0.076 (BIN `ba1ffa33…c539`) is also packaged; its console test is open.
- V0.075's local package is lost. Do not rebuild it without the maintainer's approval.
- Last user-confirmed console result: V0.082, 2026-11-21. Before it: V0.065,
  2026-09-26, "Works, no new defects" (`hardware-results/v0.065.json`).
  V0.066–V0.081 remain untested.

Binding rules:

- Emulator success never closes a hardware gate. Only user-confirmed console
  evidence does. Record it in `hardware-results/v<version>.json`.
- Each hardware build gets a new `IP_VERSION`, `IP_RELEASE_DATE` and
  `RELEASE-NOTES-V<version>.md` with its Saturn checklist.
- Every checklist starts by confirming the audio diagnostic version string and
  the exact BIN hash and SAROO folder tested. It ends with "anything worse than
  the prior console-tested build".
- Record build/hash, region/video mode, SAROO firmware and audio connection
  (see "Hardware result record" in `QA-PLAN.md`).
- Sound gate: audible music and effects, simultaneous playback, pause/resume and
  repeated cold boots on the console (rule below).
- Never flash, modify or tape console/cartridge contacts as a speculative fix.

The audio diagnostic panel procedure below remains the reference for audio faults.
Per-version candidate notes and checklists (V0.040–V0.063) are in
[docs/archive/HARDWARE-ACCEPTANCE-HISTORY.md](docs/archive/HARDWARE-ACCEPTANCE-HISTORY.md).

## V0.082 console checklist

1. Test the folder and BIN hash above. Record Saturn model, region/video mode,
   SAROO firmware and audio connection. Confirm V0.082 at boot. If an audio
   fault occurs, record the diagnostic panel's displayed version and fields.
2. Cold-boot twice. Check title/game music, sound effects, simultaneous playback,
   pause/resume, menus and save/load. Do not change the hardware setup to hide a fault.
3. Try the later zones, special stages, time travel, Classic/CD++ setting,
   Time Attack and endings. Record the actual routes played and observed failures.
   Unplayed paths remain untested. Software counts do not fill those gaps.
4. Report anything worse than V0.065, the prior console-tested build. Record
   the result in `hardware-results/v0.082.json` only after the maintainer supplies evidence.

## Audio diagnostic panel (first written for V0.040)

1. Cold-boot the candidate BIN/CUE pair together. Check title music, NEW GAME music, jump and ring effects. Report which, if any, are audible.
2. Confirm the panel says **AUDIO TEST V0.040** after holding Start and pressing Z in gameplay. Test A (independent SCSP tone lasting about 1.5 seconds), B (ring through the 68000 driver), C (CD music), separately. A click/pop alone does not count as the tone working. Start+Z exits and resumes gameplay music. Use a comfortable low listening volume for the tone.
3. Send a photo of the panel and tell us whether A, B and C each make sound. The important fields are DRIVER READY/TIMEOUT; DATA, RAM, CODE; RUN; CD INIT, TOC, TRACK/STATE; CD L/R; and INIT RESPONSE. CODE, DATA and RAM should be 1, CD INIT 0, TOC 1, RUN should advance. CD L/R should be 255/239. MVOL normally reads 0 while the diagnostic panel has paused gameplay; it should rise to 15 while a probe plays. ACK is the driver's live request flag, not a fixed pass value.
4. The bottom line records the last completed 60-update gameplay window: `60 STEPS 60 VB MAX 1` means no missed refreshes in that window. Enter the panel after running the area where the game feels slow; a larger VB count shows misses. This is VBlank-relative, not a measurement of NTSC/PAL wall-clock frequency.
5. Check whether the side strips are gone and whether clouds still flicker. Record console video mode/region, SAROO firmware version and audio connection. If the tone is also silent, compare a known-working game on the same unchanged setup; do not change firmware or hardware to test this candidate.

Sound gate closes only after audible title/gameplay music **and** effects, simultaneous playback, pause/resume and repeated cold boots on the actual console. An emulator pass cannot close it. A click on pause alone does not establish which part of the audio path is failing.
