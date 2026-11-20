#!/usr/bin/env python3
"""BIOS-backed saves and separate-process cold boots, with isolated RAM images."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import zlib

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/save-matrix"
OUT.mkdir(parents=True, exist_ok=True)
CASES = []
report = {"passed": False, "status": "pending", "cases": CASES,
          "disc_sha256": hashlib.sha256((ROOT / "dist/sonic-cd-saturn-prototype.bin").read_bytes()).hexdigest(),
          "inputs": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
                     ["tools/test_save_matrix.py", "tools/emulator_test.c", "src/save.c", "src/save.h",
                      "src/main.c", "src/special_progress.h"]},
          "core_sha256": hashlib.sha256((ROOT / ".deps/beetle-saturn/mednafen_saturn_libretro.dylib").read_bytes()).hexdigest(),
          "hardware_tested": False}
(OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")
NM = subprocess.check_output([str(ROOT / ".toolchain/bin/sh-elf-nm"), str(ROOT / "build/saturn/sonic-cd-saturn-prototype.elf")], text=True)
SYMBOLS = {row.split()[2]: row.split()[0] for row in NM.splitlines() if len(row.split()) == 3}
subprocess.run(["clang", "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-I.deps/beetle-saturn/libretro-common/include", "tools/emulator_test.c", "-o", str(OUT / "emulator_test")], cwd=ROOT, check=True)


def run(name, action, source=None, expected=None, unchanged=False, retry_input=None):
    folder = OUT / name
    folder.mkdir(exist_ok=True)
    env = os.environ.copy()
    env.pop("SCD_BACKUP_INPUT", None)
    env.pop("SCD_BACKUP_RETRY_INPUT", None)
    env.update(SCD_SAVE_CASE=action, SCD_SAVE_MAILBOX=SYMBOLS["_scd_save_mailbox"], SCD_BACKUP_OUTPUT=str(folder / "backup.bin"))
    if source:
        env["SCD_BACKUP_INPUT"] = str(source)
    if retry_input:
        env["SCD_BACKUP_RETRY_INPUT"] = str(retry_input)
    args = [OUT / "emulator_test", ROOT / ".deps/beetle-saturn/mednafen_saturn_libretro.dylib", ROOT / "dist/sonic-cd-saturn-prototype.cue", ROOT / "assets/private", folder, SYMBOLS["_scd_trace_mailbox"], SYMBOLS["_scd_audio_mailbox"], "save"]
    with (folder / "results.log").open("w") as log, (folder / "core.log").open("w") as err:
        subprocess.run(list(map(str, args)), env=env, cwd=ROOT, stdout=log, stderr=err, check=True, timeout=180)
    result = json.loads((folder / "save.json").read_text())
    mb = result["mailbox"]
    assert mb[0] == 0x53415645, (name, mb)
    for index, value in (expected or {}).items():
        assert mb[index] == value, (name, index, value, mb)
    if action == "continue":
        zone, era = mb[7] & 255, mb[7] >> 16 & 255
        track = (12 + (zone - 1) * 4 if zone else 2) + era
        assert result["trace"][23] & 0xFFF == 0x300 | track, (name, "Japanese track", track, result["trace"][23])
    if unchanged:
        assert source.read_bytes() == (folder / "backup.bin").read_bytes(), name
    result.update(name=name, action=action, passed=True, backup_sha256=hashlib.sha256((folder / "backup.bin").read_bytes()).hexdigest())
    CASES.append(result)
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"PASS {name}: status={mb[1]} valid={mb[2]} dirty={mb[3]} generation={mb[4]}", flush=True)
    return folder / "backup.bin"


def record(zone=0, act=0, era=0, stones=0, acts=0, zones=0, gen=1, spec_stage=None):
    data = bytearray(b"SCDS\x01\x20\x00\x00" + struct.pack(">I", gen) + bytes([zone, act, era, stones, acts, zones, 0]) + bytes(9))
    if spec_stage is not None:
        data[4], data[19] = 2, spec_stage
    return data + struct.pack(">I", zlib.crc32(data))


def insert(image, block, name, data):
    # Clone the actual BIOS-written two-block file, including its directory.
    first, second = bytearray(TEMPLATE[128:192]), bytearray(64)
    assert first[4:15] == b"SCDSATURN00" and first[38:42] == b"SCDS"
    first[4:15] = name.encode()
    first[34:36] = struct.pack(">H", block + 1)
    first[38:64], second[4:10] = data[:26], data[26:]
    image[block * 64:(block + 1) * 64] = first
    image[(block + 1) * 64:(block + 2) * 64] = second


def fixture(name, image):
    path = OUT / f"{name}.bin"
    assert len(image) == 32768
    path.write_bytes(image)
    return path


try:
    run("empty", "boot", expected={1: 1, 2: 0, 3: 0})
    initial = run("new", "new", expected={1: 0, 2: 1, 3: 0, 4: 1, 5: 0, 6: 0, 7: 0, 8: 0, 9: 1})
    TEMPLATE = initial.read_bytes()
    run("cold-continue", "continue", initial, {1: 0, 2: 1, 3: 0, 4: 1, 7: 0, 8: 0, 9: 1}, True)
    empty = bytearray(32768)
    empty[:64] = TEMPLATE[:64]
    # v1 reconstructs the stage after the highest stone, skipping held stones.
    # v2 preserves an explicit cycle position, even when no stones were won.
    for name, fields, wire_stage, saved_stage in [
        ("progress", (4, 1, 0, 85, 1, 11, 7), None, 1),
        ("future", (5, 2, 2, 127, 3, 31, 8), None, 0),
        ("v2-cycle", (3, 1, 0, 0, 0, 0, 9), 5, 5),
    ]:
        image = bytearray(empty)
        insert(image, 2, "SCDSATURN00", record(*fields, spec_stage=wire_stage))
        source = fixture(name, image)
        z, a, e, stones, acts, zones, gen = fields
        packed, futures = z | a << 8 | e << 16 | stones << 24, acts | zones << 8
        saved_flags = futures | saved_stage << 24
        run(name + "-continue", "continue", source, {1: 0, 2: 1, 4: gen, 5: packed, 6: saved_flags, 7: packed, 8: futures, 9: 1}, True)
        run(name + "-ram", "ram", source, {1: 0, 2: 1, 4: gen, 5: packed, 6: saved_flags, 10: 1}, True)
        run(name + "-cancel", "cancel", source, {1: 0, 2: 1, 4: gen, 5: packed, 6: saved_flags, 10: 0}, True)
        replaced = run(name + "-replace", "replace", source, {1: 0, 2: 1, 4: gen + 1, 5: 0, 6: 0, 7: 0, 8: 0})
        run(name + "-replace-cold", "continue", replaced, {1: 0, 2: 1, 4: gen + 1, 7: 0, 8: 0}, True)
    damaged = bytearray(TEMPLATE)
    damaged[128 + 38 + 15] ^= 1
    corrupt = fixture("corrupt", damaged)
    run("corrupt-ram", "ram", corrupt, {1: 3, 2: 0, 10: 1}, True)
    repaired = run("corrupt-replace", "replace", corrupt, {1: 0, 2: 1, 3: 0, 4: 1})
    run("repaired-cold", "continue", repaired, {1: 0, 2: 1, 4: 1}, True)
    oversized = bytearray(TEMPLATE)
    oversized[128 + 30:128 + 34] = struct.pack(">I", 0xFFFFFFFF)
    run("oversized-ram", "ram", fixture("oversized", oversized), {1: 3, 2: 0, 10: 1}, True)
    version = bytearray(record())
    version[4] = 3
    version[28:] = struct.pack(">I", zlib.crc32(version[:28]))
    image = bytearray(empty)
    insert(image, 2, "SCDSATURN00", version)
    run("unsupported-version", "ram", fixture("unsupported-version", image), {1: 3, 2: 0}, True)
    recovered = bytearray(TEMPLATE)
    insert(recovered, 4, "SCDSATURN01", record(2, 1, 0, 17, 1, 1, 2))
    recovered[4 * 64 + 38 + 15] ^= 1
    source = fixture("recovered", recovered)
    run("recovered-ram", "ram", source, {1: 2, 2: 1, 4: 1, 10: 1}, True)
    run("recovered-continue", "continue", source, {1: 2, 2: 1, 4: 1, 7: 0, 8: 0}, True)
    full = bytearray(empty)
    for block in range(2, 512, 2):
        insert(full, block, f"OTHER{block:06}", bytes([block % 256]) * 32)
    source = fixture("full", full)
    run("full-new", "new", source, {1: 6, 2: 0, 3: 1, 7: 0}, True)
    run("full-retry-still-full", "full-retry", source, {1: 6, 2: 0, 3: 1, 10: 1}, True)
    freed = bytearray(full)
    freed[128:256] = bytes(128)
    retried = run("full-retry", "full-retry", source, {1: 0, 2: 1, 3: 0, 4: 1, 10: 1}, retry_input=fixture("freed", freed))
    assert retried.read_bytes()[256:] == full[256:], "Retry changed unrelated saves"
    run("retried-cold", "continue", retried, {1: 0, 2: 1, 4: 1, 7: 0}, True)
    insert(full, 2, "SCDSATURN00", record(2, 1, 0, 17, 1, 1, 2))
    source = fixture("full-saved", full)
    run("full-replace", "replace", source, {1: 6, 2: 1, 3: 1, 4: 2, 5: 0x11000102, 6: 0x05000101, 7: 0}, True)
    run("full-continue", "continue", source, {1: 0, 2: 1, 3: 0, 4: 2, 7: 0x11000102, 8: 257}, True)
    insert(full, 4, "SCDSATURN01", record(gen=1))
    overwritten = run("full-existing-slots", "replace", fixture("full-both", full), {1: 0, 2: 1, 3: 0, 4: 3, 7: 0})
    assert overwritten.read_bytes()[384:] == full[384:], "Overwrite changed unrelated saves"
    # The time attack record pair (src/time_attack.c) only removes its own older copy
    # after a verified store: the title's load and a progress save leave damaged record
    # files (wrong size) and other games' files byte for byte.
    kept = bytearray(empty)
    for block, name in ((6, "SCDSATURNTA"), (8, "SCDSATURNTB"), (10, "SCDSATURNTP"), (12, "SCDSATURNTQ"), (14, "OTHERGAME01"), (16, "SCDSATURNTZ")):
        insert(kept, block, name, bytes([block]) * 32)
    source = fixture("ta-pair-kept", kept)
    written = run("ta-pair-kept", "new", source, {1: 0, 2: 1, 3: 0, 4: 1})
    assert written.read_bytes()[384:] == kept[384:], "A progress save or the title changed the record files or another save"
    source = fixture("unformatted", bytes(32768))
    run("unformatted-ram", "ram", source, {1: 5, 2: 0, 10: 1}, True)
    run("unformatted-new", "new", source, {1: 5, 2: 0, 3: 1}, True)
except Exception:
    report["status"] = "failed"
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    raise
report.update(passed=True, status="passed", scope="BIOS reads/writes, controller menus, fresh-process persistence and fault fixtures; gameplay autosave routes are separate gates")
(OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")
print(f"Save matrix passed: {len(CASES)} cases")
