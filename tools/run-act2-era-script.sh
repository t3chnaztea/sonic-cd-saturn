#!/bin/bash
# Act 2 era route driven by a host route script (tools/cc_campaign_search.c PPZ
# mode). The script becomes SCD_ACT_PAD_TRACE input (tools/act_reference_from_script.py,
# placeholder state words) for an SCD_ACT_PAD_RECORD run: the Saturn takes exactly
# the scripted buttons, and tools/act_test.c then replays the Saturn's own trace
# and must match all 16 words at every update (the strict check).
# usage: tools/run-act2-era-script.sh ERA SCRIPT OUTPUT   (ERA 0 = Present, 1-3)
set -euo pipefail
cd "$(dirname "$0")/.."
era=${1:?era 1-3 required}; script=${2:?route script required}; out=${3:?output directory required}
case "$era" in 0) mode=p1:A;; 1) mode=p1:B;; 2) mode=p1:C;; 3) mode=p1:D;; *) exit 2;; esac
mkdir -p "$out"
clang -std=gnu11 -O2 -fsigned-char -fwrapv -fno-strict-aliasing -Wno-parentheses -Wno-unused-value \
    -Isrc -Iassets/generated -Ibuild/probe-source -DR1 -DR11A tools/cc_campaign_search.c \
    src/{title_card,world,act,player,camera_v,sonic_animation,stage,boss,boss_r3,objects}.c \
    build/probe-source/{boss_1,boss_3,playsp3,interaction,player,dircol,fcol,etc,equ,movement}.c -o build/ppz_route_host
cp "$script" "$out/script.txt"
# The gate enters by the Act 2 debug entry, not level select (PPZ_DIRECT_ENTRY).
PPZ_DIRECT_ENTRY=1 build/ppz_route_host replay "$mode" "$out/script.txt" 40000 "$out/host-route.txt" 2> "$out/host-route.log"
updates=$(sed -n 's/^Tally complete: sequence=\([0-9]*\).*/\1/p' "$out/host-route.log")
test -n "$updates" || { echo "host route did not reach the tally" >&2; exit 1; }
python3 tools/act_reference_from_script.py "$out/script.txt" "$updates" "$out/pad-input.txt"
printf 'script %s sha256 %s host tally %s\n' "$script" "$(shasum -a 256 "$out/script.txt" | cut -d' ' -f1)" "$updates" > "$out/route.txt"
symbol(){ .toolchain/bin/sh-elf-nm build/saturn/sonic-cd-saturn-prototype.elf | awk -v name="$1" '$3 == name {print $1}'; }
export SCD_WORLD_MAILBOX=$(symbol _scd_world_mailbox)
# Era 0 is the Act 2 debug entry's own Present; SCD_ACT_ERA selects 1-3 only.
if [ "$era" = 0 ]; then unset SCD_ACT_ERA; else export SCD_ACT_ERA=$era; fi
export SCD_ACT_PAD_TRACE="$out/pad-input.txt" SCD_ACT_PAD_RECORD=1
unset SCD_ACT2_ROUTE SCD_FRAME_PROFILE SCD_ACT2_TRAVEL SCD_ACT_START SCD_ACT_RIGHT SCD_ACT2_SHOT
build/emulator_test "$PWD/.deps/beetle-saturn/mednafen_saturn_libretro.dylib" "$PWD/dist/sonic-cd-saturn-prototype.cue" "$PWD/assets/private" \
 "$out" "$(symbol _scd_trace_mailbox)" "$(symbol _scd_audio_mailbox)" act2 > "$out/results.log" 2> "$out/core.log"
