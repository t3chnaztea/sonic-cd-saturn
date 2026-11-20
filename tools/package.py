#!/usr/bin/env python3
"""Produce or byte-verify BIN/CUE without rewriting unchanged disc images."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import package_reuse as reuse

ROOT = Path(__file__).resolve().parents[1]
NAME = "sonic-cd-saturn-prototype"


def main(root=ROOT):
    root = Path(root)
    dist = root / "dist"
    iso = dist / "iso" / f"{NAME}.iso"
    binary, cue = dist / f"{NAME}.bin", dist / f"{NAME}.cue"
    elf = root / "build/saturn" / f"{NAME}.elf"
    feedback = root / "build/feedback-source.json"
    stage_packs = root / "build/stage-packs.json"
    audio = json.loads(feedback.read_text())
    sectors = reuse.iso_sectors(iso)
    music = reuse.audio_inputs(root, audio)
    cue_bytes, tracks, binary_size = reuse.cue_layout(binary.name, sectors, audio["tracks"])
    core = root / ".deps/beetle-saturn"
    encoder = root / "build/iso_to_raw"
    encoder_sources = [root / "tools/iso_to_raw.c", core / "mednafen/cdrom/lec.c",
                       core / "mednafen/cdrom/lec.h"]
    command = ["clang", "-O2", "-Wall", "-Wextra",
               "-I" + str(core / "libretro-common/include"),
               "-I" + str(core / "mednafen/cdrom"),
               *map(str, encoder_sources[:2]), "-o", str(encoder)]
    paths = [iso, feedback, stage_packs, elf, *music, *encoder_sources,
             Path(__file__).resolve(), Path(reuse.__file__).resolve()]
    inputs = {str(path): reuse.digest(path) for path in paths}
    staged = []
    try:
        with (root / "build/package.log").open("w") as log:
            subprocess.run(command, cwd=root, stdout=log, stderr=log, check=True)
            matching_binary = reuse.binary_matches(encoder, iso, binary, tracks, music)
            new_binary = None
            checked_binary = binary
            if not matching_binary:
                new_binary = reuse.temporary(binary)
                staged.append(new_binary)
                subprocess.run([str(encoder), str(iso), str(new_binary)],
                               stdout=log, stderr=log, check=True)
                reuse.append_audio(new_binary, tracks, music)
                if not reuse.binary_matches(encoder, iso, new_binary, tracks, music):
                    raise ValueError("Generated BIN does not match current inputs")
                checked_binary = new_binary
        if checked_binary.stat().st_size != binary_size:
            raise ValueError("Unexpected final BIN length")
        try:
            matching_cue = cue.read_bytes() == cue_bytes
        except FileNotFoundError:
            if not cue.parent.is_dir():
                raise
            matching_cue = False
        size = subprocess.check_output(
            [str(root / ".toolchain/bin/sh-elf-size"), str(elf)], text=True)
        symbols = subprocess.check_output(
            [str(root / ".toolchain/bin/sh-elf-nm"), "-n", str(elf)], text=True)
        ends = [int(line.split()[0], 16) for line in symbols.splitlines()
                if line.split()[-1] == "___end"]
        if len(ends) != 1 or not 0x06004000 <= ends[0] < 0x06100000:
            raise ValueError("Invalid linked end")
        memory = {
            "linked_end": f"0x{ends[0]:08X}",
            "user_heap_capacity_bytes": 0x06100000 - ends[0],
            "note": "Capacity before runtime user allocations; startup and controller tests exercise the allocated command list.",
        }
        files = {
            iso.name: {"bytes": iso.stat().st_size, "sha256": reuse.digest(iso)},
            cue.name: {"bytes": len(cue_bytes), "sha256": hashlib.sha256(cue_bytes).hexdigest()},
            binary.name: {"bytes": binary_size, "sha256": reuse.digest(checked_binary)},
        }
        compiler = subprocess.check_output(["clang", "--version"], text=True)
        report = {
            "memory": memory, "format": "MODE1/2352", "verified_data_sectors": sectors,
            "music_source": audio["music_source"], "size_report": size,
            "hardware_tested": False, "audio_tracks": tracks,
            "stage_packs": json.loads(stage_packs.read_text()), "files": files,
            "packaging": {
                "binary": "verified_reused" if matching_binary else "rebuilt",
                "cue": "verified_reused" if matching_cue else "repaired",
                "inputs": inputs, "encoder_command": command, "compiler": compiler,
                "verification": "current encoded sectors including ECC; current audio, zero pregap, CUE layout and exact EOF",
            },
        }
        changed = [name for name, digest in inputs.items() if reuse.digest(name) != digest]
        if changed:
            raise ValueError("Packaging inputs changed: " + repr(changed))
        changes = []
        if new_binary is not None:
            changes.append((binary, new_binary))
        if not matching_cue:
            temporary = reuse.stage_bytes(cue, cue_bytes)
            staged.append(temporary)
            changes.append((cue, temporary))
        temporary = reuse.stage_bytes(
            dist / "build-report.json",
            (json.dumps(report, indent=2, allow_nan=False) + "\n").encode())
        staged.append(temporary)
        changes.append((dist / "build-report.json", temporary))
        reuse.publish_package(changes)
    finally:
        primary = sys.exc_info()[1]
        for temporary in staged:
            try:
                reuse.cleanup(temporary, primary)
            except OSError as error:
                if primary is None:
                    primary = error
                else:
                    primary.add_note("additional temporary cleanup failed: " + repr(error))
        if primary is not None and sys.exc_info()[1] is None:
            raise primary
    state = "verified without BIN rewrite" if matching_binary else "rebuilt and verified"
    print(f"Verified {sectors} sectors; BIN/CUE {state} in {dist}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
