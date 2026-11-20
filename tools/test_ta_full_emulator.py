#!/usr/bin/env python3
"""Emulator gate: full backup RAM preserves the last Time Attack record.

Usage: python3 tools/test_ta_full_emulator.py
Runs the ta-run case of tools/test_frontend_emulator.py (its fixtures and harness),
then fills backup RAM so a second 692-byte record file cannot fit. A new run must
report a save failure, retain its result in memory, and leave the entire backup
image unchanged. A separate process must reload the previous record. The native
record test observes BIOS code 4; this target gate observes the menu failure state.
Writes build/frontend-qa/ta-full/report.json. Exit 0 only on PASS.
"""
import atexit, hashlib, json, os, re, struct, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "build/frontend-qa/ta-full/report.json"
REPORT.parent.mkdir(parents=True, exist_ok=True)
report = dict(status="pending", passed=False, hardware_tested=False,
              script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


def write_report():
    REPORT.write_text(json.dumps(report, indent=2) + "\n")


def unfinished():
    if report["status"] == "pending":
        report.update(status="interrupted", error="process exited before a terminal result")
        write_report()


write_report()
atexit.register(unfinished)
sys.argv = [sys.argv[0], "ta-run"]
try:
    import test_frontend_emulator as fe  # noqa: E402  (runs ta-run on import)
except BaseException as error:
    report.update(status="interrupted" if isinstance(error, KeyboardInterrupt) else "failed",
                  error=repr(error))
    write_report()
    raise
report.update(disc_sha256=fe.report["disc_sha256"], elf_sha256=fe.report["elf_sha256"],
              inputs={**fe.report["inputs"],
                      "src/time_attack.h": hashlib.sha256((ROOT / "src/time_attack.h").read_bytes()).hexdigest()})
write_report()
# Existing product state: 2 means a failed record write (frontend.c). No code-only
# QA instrumentation is needed. The native test directly checks returned code 4.
fe.SYMS += ",tastate=" + fe.SYMBOLS["_fe_ta_state"]
fe.SYMS += ",tamenu=" + fe.SYMBOLS["_fe_ta_menu"]
fe.SYMS += ",tafiles=" + fe.SYMBOLS["_fe_ta_files"]
fe.SYMS += ",tapreset=" + fe.SYMBOLS["_fe_ta_preset"]


def fail(name, message, out=""):
    report.update(status="failed", error=message)
    write_report()
    fe.fail(name, message, out)

BLOCKS, BLOCK = 512, 64
FILLER = "QAFILLER000"


def chain(image, first):
    """A file's blocks: its directory block, then the 2-byte list that follows the
    directory entry (0-terminated), read across the blocks it names."""
    blocks, idx, off = [first], 0, 34
    while True:
        if off == BLOCK:
            idx += 1
            off = 4
        entry = image[blocks[idx] * BLOCK + off] << 8 | image[blocks[idx] * BLOCK + off + 1]
        off += 2
        if entry == 0:
            return blocks
        blocks.append(entry)


def used_blocks(image):
    """Blocks in use: 0-1 (format) and every file's chain."""
    used = {0, 1}
    for b in range(2, BLOCKS):
        if image[b * BLOCK] & 0x80:
            used.update(chain(image, b))
    return used


def file_blocks_needed(size):
    """Blocks for a file: a 30-byte first block after the header, 60 bytes per
    further block, a 2-byte list entry per further block and a 0 terminator."""
    n = 1
    while 30 + 60 * (n - 1) < size + 2 * (n - 1) + 2:
        n += 1
    return n


def add_filler(image, blocks):
    """A BIOS-layout file over the given free blocks (first one holds the directory)."""
    first, rest = blocks[0], blocks[1:]
    size = 30 + 60 * len(rest) - 2 * len(rest) - 2
    stream = b"".join(struct.pack(">H", b) for b in rest) + b"\0\0" + bytes([0x5A]) * size
    image[first * BLOCK:(first + 1) * BLOCK] = bytes(BLOCK)
    image[first * BLOCK:first * BLOCK + 4] = b"\x80\0\0\0"
    image[first * BLOCK + 4:first * BLOCK + 15] = FILLER.encode()
    image[first * BLOCK + 16:first * BLOCK + 26] = b"QA FILLER\0"
    image[first * BLOCK + 30:first * BLOCK + 34] = struct.pack(">I", size)
    pos = 0
    for i, b in enumerate(blocks):
        start = 34 if i == 0 else 4
        if i:
            image[b * BLOCK:(b + 1) * BLOCK] = bytes(BLOCK)
        chunk = stream[pos:pos + BLOCK - start]
        image[b * BLOCK + start:b * BLOCK + start + len(chunk)] = chunk
        pos += len(chunk)
    assert pos == len(stream)
    return size


src = fe.state["ta-run"]
image = bytearray(src.read_bytes())
name, d = fe.ta_current(image)
if name != "SCDSATURNTB" or fe.read_file(image, "SCDSATURNTA") is not None:
    fail("ta-full", f"ta-run left {name}")
before = fe.ta_decode(d)
need = file_blocks_needed(fe.TA_FILE)
free = [b for b in range(2, BLOCKS) if b not in used_blocks(image)]
keep = need // 2
filler_size = add_filler(image, free[:len(free) - keep])
if fe.read_file(image, FILLER) != bytes([0x5A]) * filler_size:
    fail("ta-full", "filler does not parse back")
left = BLOCKS - len(used_blocks(image))
if left >= need:
    fail("ta-full", f"{left} blocks free, a record file needs {need}")
fixture = fe.OUT / "fixture-ta-full.bin"
fixture.write_bytes(image)

script = fe.ta_enter("ta-full") + "tap A\ntap RIGHT\ntap A\nuntil SCD2 900\npeek ta0 ta 0 3\n" + \
    f"route {fe.route_updates('tests/routes/ppz/p0A.seq.txt', 'p0A.updates')} 20000\n" + \
    "until FEND 3000\nrun 30\npeek ta1 ta 0 3\ntap A\ntap A\ntap A\ntap A\nrun 30\n" + \
    "peek rec rec 0 3\npeekb failed tastate 0 1\nshot ta-full-failed\n"
rc, out, peeks, backup = fe.run("ta-full", script, fixture, timeout=1800)
if rc:
    fail("ta-full", f"harness status {rc}", out)
after_image = backup.read_bytes()
if fe.read_file(after_image, "SCDSATURNTA") is not None or fe.read_file(after_image, "SCDSATURNTB") != d:
    fail("ta-full", "the current record changed or its companion was created", out)
after = fe.ta_decode(fe.read_file(after_image, "SCDSATURNTB"))
frames2 = peeks["ta1"][1]
if peeks["ta0"][0] >> 24 != 1 or peeks["ta0"][0] >> 16 & 255 != 0:
    fail("ta-full", f"wrong run mode/entry: {peeks['ta0']}", out)
if peeks["ta1"][0] >> 8 & 255 or not 0 < frames2 < 18000:
    fail("ta-full", f"run did not complete: {peeks['ta1']}", out)
want = sorted(before["times"][:3] + [frames2])[:3]
if want == before["times"][:3] or peeks["rec"] != want:
    fail("ta-full", f"in-memory times {peeks['rec']} (want {want})", out)
if peeks["failed"] != [2]:
    fail("ta-full", f"save failure not reported: {peeks['failed']}", out)
if after != before or after_image != bytes(image):
    fail("ta-full", "full-storage failure changed the backup image or decoded record", out)
if fe.read_file(after_image, FILLER) != bytes([0x5A]) * filler_size:
    fail("ta-full", "the filler file changed")
if fe.read_file(after_image, "SCDSATURN00") != fe.read_file(image, "SCDSATURN00"):
    fail("ta-full", "the progress record changed")
# A fresh emulator process gets the exported backup RAM, not a save state.
rc, cold_out, cold_peeks, cold_backup = fe.run(
    "ta-full-reload", fe.ta_enter("ta-full-reload") +
    "tap A\nrun 20\npeek rec rec 0 3\npeekb loaded tastate 0 1\n", backup)
if rc:
    fail("ta-full", f"cold-load harness status {rc}", cold_out)
if cold_peeks["rec"] != before["times"][:3] or cold_peeks["loaded"] != [1]:
    fail("ta-full", f"cold load did not restore old records: {cold_peeks}", cold_out)
if cold_backup.read_bytes() != after_image:
    fail("ta-full", "cold-load changed the backup image", cold_out)

# Keep the existing full-failure/cold-old-record proof above. These new runs stop
# before final-initials confirmation so the failed result stays in the same menu.
filler_blocks = free[:len(free) - keep]
freed_image = bytearray(image)
for block in filler_blocks:
    freed_image[block * BLOCK:(block + 1) * BLOCK] = bytes(BLOCK)
if fe.read_file(freed_image, FILLER) is not None or BLOCKS - len(used_blocks(freed_image)) < need:
    fail("ta-full-retry", "freed fixture did not remove exactly the filler capacity")
if fe.read_file(freed_image, name) != d:
    fail("ta-full-retry", "freed fixture changed the verified old record")
if any(freed_image[b * BLOCK:(b + 1) * BLOCK] != image[b * BLOCK:(b + 1) * BLOCK]
       for b in range(BLOCKS) if b not in filler_blocks):
    fail("ta-full-retry", "freed fixture changed bytes outside the filler")
freed_fixture = fe.OUT / "fixture-ta-retry-freed.bin"
freed_fixture.write_bytes(freed_image)
old_directory = next(b for b in range(2, BLOCKS)
                     if image[b * BLOCK] & 0x80 and image[b * BLOCK + 4:b * BLOCK + 15] == name.encode())
protected_blocks = used_blocks(image) - set(filler_blocks) - set(chain(image, old_directory))


def retry_same_result(case, replacement, succeeds):
    script = fe.ta_enter(case) + "tap A\ntap RIGHT\ntap A\nuntil SCD2 900\npeek retry_start ta 0 3\n" + \
        f"route {fe.route_updates('tests/routes/ppz/p0A.seq.txt', 'p0A.updates')} 20000\n" + \
        "until FEND 3000\nrun 30\npeek retry_result ta 0 3\npeek retry_rec rec 0 3\n" + \
        "peekb retry_records rec 0 593\npeekb retry_failed tastate 0 1\npeekb retry_menu_failed tamenu 0 9\n" + \
        "peekb retry_bank tapreset 0 1\npeek retry_generation tafiles 0 1\npeekb retry_pair tafiles 4 3\n" + \
        "tap A\ntap A\ntap A\npeekb retry_final_menu tamenu 0 9\nbackup_retry\n" + \
        "peek retry_same_run ta 0 3\npeekb retry_same_records rec 0 593\n" + \
        "tap A\nrun 30\npeek retry_done_run ta 0 3\npeek retry_saved_rec rec 0 3\n" + \
        "peekb retry_saved_records rec 0 593\npeekb retry_saved_state tastate 0 1\n" + \
        "peekb retry_saved_menu tamenu 0 9\npeek retry_saved_generation tafiles 0 1\n" + \
        "peekb retry_saved_pair tafiles 4 3\nshot ta-retry-result\n"
    previous = os.environ.get("SCD_BACKUP_RETRY_INPUT")
    os.environ["SCD_BACKUP_RETRY_INPUT"] = str(replacement)
    try:
        rc, output, observed, saved = fe.run(case, script, fixture, timeout=1800)
    finally:
        if previous is None:
            os.environ.pop("SCD_BACKUP_RETRY_INPUT", None)
        else:
            os.environ["SCD_BACKUP_RETRY_INPUT"] = previous
    if rc:
        fail(case, f"retry harness status {rc}", output)
    witness = re.findall(r"^frame=(\d+) backup_retry bytes=32768 before_unchanged=1 changed=([01])$", output, re.M)
    if len(witness) != 1 or int(witness[0][1]) != int(succeeds):
        fail(case, "missing, repeated or wrong retry-fixture witness", output)
    routes = re.findall(r"^frame=\d+ route \S+ updates=(\d+) of (\d+) mismatches=(\d+) ended=([01])$", output, re.M)
    if len(routes) != 1:
        fail(case, "missing or repeated controller-route observation", output)
    mode = observed["retry_start"][0]
    result = observed["retry_result"]
    result_time = result[1]
    expected_times = sorted(before["times"][:3] + [result_time])[:3]
    menu = observed["retry_menu_failed"]
    final_menu = observed["retry_final_menu"]
    if mode >> 24 != 1 or mode >> 16 & 255 or result[0] >> 8 & 255 or not 0 < result_time < 18000:
        fail(case, "retry origin was not a completed ranked PPZ1A run", output)
    if observed["retry_failed"] != [2] or observed["retry_bank"] != [0] or menu[1] != 4 or menu[5] != 0:
        fail(case, "initial automatic commit did not fail in the Classic record menu", output)
    if observed["retry_rec"] != expected_times or expected_times == before["times"][:3]:
        fail(case, "failed result was not retained in memory", output)
    if final_menu[1] != 5 or final_menu[5] != 2 or final_menu[4] != menu[4] or final_menu[8] != menu[8]:
        fail(case, "fixture was not applied at the same result's final initial", output)
    live = observed["retry_records"]
    if len(live) != 593 or observed["retry_same_records"] != live or observed["retry_saved_records"] != live:
        fail(case, "retry changed the retained record data", output)
    if observed["retry_same_run"][:2] != result[:2] or observed["retry_done_run"][:2] != result[:2]:
        fail(case, "a later run replaced the retained result", output)
    if observed["retry_generation"] != [before["generation"]] or observed["retry_pair"] != [1, 2, 0]:
        fail(case, "failed write adopted a new file or generation", output)
    saved_image = saved.read_bytes()
    expected_generation = ((before["generation"] + 1) & 0xFFFFFF) or 1
    if observed["retry_saved_menu"][1] != 3:
        fail(case, "final initials confirmation did not return to the start column", output)
    if not succeeds:
        if observed["retry_saved_state"] != [2] or observed["retry_saved_generation"] != [before["generation"]] or \
           observed["retry_saved_pair"] != [1, 2, 0] or saved_image != bytes(image):
            fail(case, "still-full control did not preserve failure and old backup", output)
    else:
        current_name, current_data = fe.ta_current(saved_image)
        decoded = fe.ta_decode(current_data)
        if observed["retry_saved_state"] != [1] or observed["retry_saved_generation"] != [expected_generation] or \
           observed["retry_saved_pair"] != [0, 1, 0] or current_name != "SCDSATURNTA" or \
           fe.read_file(saved_image, "SCDSATURNTB") is not None or decoded["generation"] != expected_generation:
            fail(case, "retry did not verify/adopt the peer and remove the old copy", output)
        raw_live = bytes(live)
        live_times = list(struct.unpack(">84I", raw_live[:336]))
        live_names = [raw_live[336 + i * 3:339 + i * 3] for i in range(84)]
        if decoded["times"] != live_times or decoded["names"] != live_names or \
           current_data[10:13] != raw_live[588:591] or decoded["unlock"] != raw_live[591] or decoded["flags"] != raw_live[592]:
            fail(case, "verified peer differs from the same retained in-memory records", output)
        if any(saved_image[b * BLOCK:(b + 1) * BLOCK] != image[b * BLOCK:(b + 1) * BLOCK]
               for b in protected_blocks):
            fail(case, "retry changed unrelated files or format blocks", output)
        rc, cold_output, cold, cold_saved = fe.run(case + "-cold", fe.ta_enter(case + "-cold") +
            "tap A\nrun 20\npeek rec rec 0 3\npeekb loaded tastate 0 1\n" +
            "peek generation tafiles 0 1\npeekb pair tafiles 4 3\n", saved)
        if rc or cold["rec"] != expected_times or cold["loaded"] != [1] or \
           cold["generation"] != [expected_generation] or cold["pair"] != [0, 1, 0] or cold_saved.read_bytes() != saved_image:
            fail(case, "fresh process did not load the newly verified same-result retry", cold_output)
    return dict(case=case, passed=True, space_available=succeeds, result_frames=result_time,
                retained_times=expected_times, fixture_before_unchanged=True,
                state=observed["retry_saved_state"][0], generation=observed["retry_saved_generation"][0],
                backup_sha256=hashlib.sha256(saved_image).hexdigest(), protected_blocks=len(protected_blocks),
                route=dict(zip(("updates", "total", "mismatches", "ended"), map(int, routes[0]))),
                route_limit="Counts retained; nonzero button differences do not establish exact recorded-input replay.",
                fixture_limit="Test reload of SAVE_RAM filler capacity; not user file deletion or work-RAM mutation.",
                cold_new_record_loaded=succeeds)


report["same_result_retries"] = []
for retry_case, retry_fixture, succeeds in [("ta-full-retry-still-full", fixture, False),
                                           ("ta-full-retry-after-space", freed_fixture, True)]:
    report["same_result_retries"].append(retry_same_result(retry_case, retry_fixture, succeeds))
    write_report()
detail = dict(free_blocks=left, record_blocks=need, generation=after["generation"],
              in_memory_times=peeks["rec"], preserved_times=after["times"][:3],
              cold_loaded_times=cold_peeks["rec"], failure_state=2,
              backup_sha256=hashlib.sha256(after_image).hexdigest(),
              target_observation="menu failure state2; native test observes I/O code4",
              disc=fe.report["disc_sha256"][:16])
report.update(status="passed", passed=True, **detail)
write_report()
print("PASS: ta-full: " + ", ".join(f"{k}={v}" for k, v in detail.items()))
