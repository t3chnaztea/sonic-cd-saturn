#!/usr/bin/env python3
"""Actual transition writes, followed by Continue in separate emulator processes."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/save-progression"
OUT.mkdir(parents=True, exist_ok=True)
nm = subprocess.check_output([ROOT / ".toolchain/bin/sh-elf-nm", ROOT / "build/saturn/sonic-cd-saturn-prototype.elf"], text=True)
symbols = {r.split()[2]: r.split()[0] for r in nm.splitlines() if len(r.split()) == 3}
session = next(v for k, v in symbols.items() if k == "_save_session" or k.startswith("_save_session.lto_priv."))
disc = hashlib.sha256((ROOT / "dist/sonic-cd-saturn-prototype.bin").read_bytes()).hexdigest()
report = dict(passed=False, status="pending", disc_sha256=disc, steps=[], hardware_tested=False,
              inputs={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
                      ["tools/test_save_progression.py", "tools/test-save-emulator.sh", "tools/emulator_test.c",
                       "src/main.c", "src/save.c", "src/save.h", "src/special_progress.h"]},
              core_sha256=hashlib.sha256((ROOT / ".deps/beetle-saturn/mednafen_saturn_libretro.dylib").read_bytes()).hexdigest())
(OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")


def failed(kind, error, traceback):
    report.update(status="interrupted" if issubclass(kind, KeyboardInterrupt) else "failed", error=repr(error))
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    sys.__excepthook__(kind, error, traceback)


sys.excepthook = failed


def run(name, command, **variables):
    env = os.environ.copy()
    for key in ("SCD_BACKUP_INPUT", "SCD_BACKUP_OUTPUT", "SCD_BACKUP_RETRY_INPUT", "SCD_SAVE_FIXTURE_SESSION", "SCD_SAVE_WAIT_NEXT"):
        env.pop(key, None)
    env.update({k: str(v) for k, v in variables.items()})
    with (OUT / f"{name}.log").open("w") as log:
        result = subprocess.run(list(map(str, command)), cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=600)
    report["steps"].append(dict(name=name, command=list(map(str, command)), exit_code=result.returncode))
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    assert result.returncode == 0, name
    print("PASS command", name, flush=True)


def cold(name, source, generation, stage, futures, spec_stage=0):
    folder = OUT / name
    run(name, ["bash", "tools/test-save-emulator.sh", "continue"], SCD_BACKUP_INPUT=source, SCD_SAVE_OUTPUT_DIR=folder.relative_to(ROOT))
    result = json.loads((folder / "save.json").read_text())
    m = result["mailbox"]
    assert m[:7] == [0x53415645, 0, 1, 0, generation, stage, futures | spec_stage << 24], (name, m)
    assert m[7:10] == [stage, futures, 1], (name, m)
    zone, era = stage & 255, stage >> 16 & 255
    track = (12 + (zone - 1) * 4 if zone else 2) + era
    assert result["trace"][23] & 0xFFF == 0x300 | track, (name, "Japanese track", track)
    assert source.read_bytes() == (folder / "backup.bin").read_bytes(), name
    # Live player snapshot: no reset/death, zero rings, three lives.
    trace = result["trace"]
    assert trace[11] == 0 and trace[12] >> 16 == 0 and trace[13] & 0xFF == 3, (name, trace)
    report[name] = result
    print("PASS cold checkpoint", name, flush=True)


run("sequence", ["bash", "tools/test-sequence-emulator.sh"], SCD_BACKUP_OUTPUT=OUT / "sequence.bin")
cold("sequence-cold", OUT / "sequence.bin", 4, 1, 0)
# This established test uses a 50-ring entry fixture. Explicitly re-enable
# saving after that fixture; the stone is then earned with the retail win
# controller route. Ordinary debug sessions remain unable to overwrite saves.
run("special", ["bash", "tools/test-bigring-emulator.sh"], SCD_BACKUP_OUTPUT=OUT / "special.bin", SCD_SAVE_FIXTURE_SESSION=session)
cold("special-cold", OUT / "special.bin", 2, 0x01000100, 0, spec_stage=1)
# Also prove the default fixture cannot advance persistent progress.
run("debug-no-save", ["bash", "tools/test-bigring-emulator.sh"], SCD_BACKUP_OUTPUT=OUT / "debug.bin")
cold("debug-cold", OUT / "debug.bin", 1, 0, 0)

# Make an independent CRC-checked record in the first BIOS-created two-block
# file. Continue from PPZ Act 2, then finish it using the normal route. No
# gameplay memory or controller debug entry is used for this case.
image = bytearray((OUT / "debug.bin").read_bytes())
assert image[132:143] == b"SCDSATURN00" and image[166:170] == b"SCDS"
data = bytearray(b"SCDS\x01\x20\x00\x00" + struct.pack(">I", 20) + bytes([0, 1, 0, 85, 1, 11, 0]) + bytes(9))
data += struct.pack(">I", zlib.crc32(data))
image[166:192], image[196:202] = data[:26], data[26:]
source = OUT / "act2-input.bin"
source.write_bytes(image)
folder = OUT / "act2"
folder.mkdir(exist_ok=True)
# Since the 68k player fixes and camera-X the SCD_ACT2_ROUTE region rules no
# longer finish: the continued Act 2 replays the staged host script (Continue
# starts the act like level select, title card included) as SCD_ACT_PAD_RECORD input.
sys.path.insert(0, str(ROOT / "tools"))
import ppz_chain_scripts
route = ROOT / "tests/routes/ppz/p1A.txt"
pads = ppz_chain_scripts.leg(ppz_chain_scripts.build_host(), "p1:A", "p1A")
subprocess.run(["python3", "tools/act_reference_from_script.py", route, str(len(pads) + 1), folder / "pad-input.txt"], cwd=ROOT, check=True)
run("act2", [ROOT / "build/emulator_test", ROOT / ".deps/beetle-saturn/mednafen_saturn_libretro.dylib",
             ROOT / "dist/sonic-cd-saturn-prototype.cue", ROOT / "assets/private", folder,
             symbols["_scd_trace_mailbox"], symbols["_scd_audio_mailbox"], "act2"],
    SCD_WORLD_MAILBOX=symbols["_scd_world_mailbox"], SCD_SAVE_MAILBOX=symbols["_scd_save_mailbox"],
    SCD_SAVE_WAIT_NEXT=1, SCD_BACKUP_INPUT=source, SCD_BACKUP_OUTPUT=OUT / "act2.bin",
    SCD_ACT_PAD_TRACE=folder / "pad-input.txt", SCD_ACT_PAD_RECORD=1)
state = json.loads((folder / "save.json").read_text())["mailbox"]
assert state[1:9] == [0, 1, 0, 21, 0x55030200, 0x01000B01, 0x55030200, 0x0B01], state
cold("act2-cold", OUT / "act2.bin", 21, 0x55030200, 0x0B01, spec_stage=1)
assert hashlib.sha256((ROOT / "dist/sonic-cd-saturn-prototype.bin").read_bytes()).hexdigest() == disc
report["passed"] = True
report["status"] = "passed"
report["limits"] = "Special entry uses the documented big-ring fixture with explicit test-only session enable; sequence and continued Act 2 use ordinary controller gameplay. Console power-cycle acceptance remains pending."
(OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")
print("Save progression and cold-boot persistence passed")
