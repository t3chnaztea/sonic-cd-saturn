#!/usr/bin/env python3
"""Front-end emulator gates: Time Attack menu, run, records and unlocks.

Usage: python3 tools/test_frontend_emulator.py CASE [CASE ...]   (no CASE: all)
Cases: ta-hidden ta-menu ta-run ta-pair ta-reload ta-thresholds ta-objects ta-bigring ta-death ta-pause-exit
       sound-test sound-test-ss8 sound-test-images attract-demos attract-demos-cdpp attract-fmv visual-mode visual-mode-movies
       staff-times staff-times-cdpp staff-times-opposing (explicit cases; private output/system/template required)
Each run writes build/frontend-qa/report.json with the disc's sha256 and exits 0
only when every requested case passes. The harness is tools/frontend_emulator_test.c.
"""
import ast, hashlib, json, os, re, struct, subprocess, sys, zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import title_menu  # noqa: E402
STAFF_CASES = ("staff-times", "staff-times-cdpp", "staff-times-opposing")
QA_MOUNT = os.environ.get("SCD_QA_MOUNT") or ("/".join(str(ROOT).split("/")[:3]) if str(ROOT).startswith("/Volumes/") else "")
STAFF_REQUESTED = any(name in sys.argv[1:] for name in STAFF_CASES)
OUT = Path(os.environ.get("SCD_FRONTEND_OUTPUT", str(ROOT / "build/frontend-qa")))
if STAFF_REQUESTED:
    if len(set(sys.argv[1:])) != len(sys.argv[1:]) or any(name not in STAFF_CASES for name in sys.argv[1:]):
        raise SystemExit("Run explicit Staff Times cases separately from legacy cases")
    if "staff-times-opposing" in sys.argv[1:]:
        if sys.argv[1:] != ["staff-times-opposing"] or os.environ.get("SCD_STAFF_OPPOSITE_DIRECTIONS") != "1":
            raise SystemExit("Raw Staff opposing-input supplement requires its single case and explicit flag1")
    elif os.environ.get("SCD_STAFF_OPPOSITE_DIRECTIONS") == "1":
        raise SystemExit("Base Staff journeys require the default neutral core profile")
    if "SCD_FRONTEND_OUTPUT" not in os.environ or OUT.exists() or not OUT.is_absolute() or not QA_MOUNT or not OUT.resolve().is_relative_to(Path(QA_MOUNT)):
        raise SystemExit("Staff Times requires a fresh private SCD_FRONTEND_OUTPUT on the QA volume")
    for key in ("SCD_STAFF_SYSTEM", "SCD_STAFF_TEMPLATE"):
        if key not in os.environ:
            raise SystemExit(f"Staff Times requires pinned private {key}")
    system = Path(os.environ["SCD_STAFF_SYSTEM"])
    if not system.is_dir() or system.resolve() == (ROOT / "assets/private").resolve() or not system.resolve().is_relative_to(ROOT / "build"):
        raise SystemExit("Staff Times requires its private BIOS/system directory under build")
OUT.mkdir(parents=True, exist_ok=True)
DISC = ROOT / "dist/sonic-cd-saturn-prototype.bin"
ELF = ROOT / "build/saturn/sonic-cd-saturn-prototype.elf"
HARNESS = OUT / "frontend_emulator_test"
report = {"status": "pending", "passed": False, "cases": [],
          "disc_sha256": hashlib.sha256(DISC.read_bytes()).hexdigest(),
          "elf_sha256": hashlib.sha256(ELF.read_bytes()).hexdigest(),
          "inputs": {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in
                     ["tools/test_frontend_emulator.py", "tools/frontend_emulator_test.c", "src/frontend.c",
                      "src/time_attack.c", "src/frontend_view.inc", "src/title.c", "src/main.c", "src/visual_mode.c"]},
          "hardware_tested": False}
if STAFF_REQUESTED:
    for name in ("src/staff_times.c", "src/staff_times.h", "src/frontend.h", "src/audio.c", "src/music_routes.h",
                 "tools/test_frontend_preset_switch.py", "tools/qa_limits.py", "cd/STAFFTIM.BIN"):
        report["inputs"][name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()


def write_report():
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")


write_report()
subprocess.run(["clang", "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-I.deps/beetle-saturn/libretro-common/include",
                "tools/frontend_emulator_test.c", "-o", str(HARNESS)], cwd=ROOT, check=True)
if STAFF_REQUESTED:
    import time
    from qa_limits import cooldown
    staff_last_heavy = time.monotonic()
NM = subprocess.check_output([str(ROOT / ".toolchain/bin/sh-elf-nm"), str(ELF)], text=True)
SYMBOLS = {}
for row in NM.splitlines():
    p = row.split()
    if len(p) == 3:
        SYMBOLS[re.sub(r"\.lto_priv\.\d+$", "", p[2])] = p[0]
# src/audio.c status (cd_block_status_t, bss); a function in another file is also _status.
SYMBOLS["_status"] = next(r.split()[0] for r in NM.splitlines() if r.split()[1:] in (["b", "_status"], ["d", "_status"]))
SYMBOLS["fmv"] = "20243000"  # scd_fmv_mailbox, low work RAM (src/fmv_saturn.h FMV_LWRAM_STATE)
SYMS = ",".join(f"{k}={SYMBOLS[v]}" for k, v in
                [("trace", "_scd_trace_mailbox"), ("world", "_scd_world_mailbox"), ("game", "_scd_special_game_mailbox"), ("ta", "_scd_ta"), ("st", "_fe_st"), ("slot", "_demo_slot"), ("frame", "_demo_frame"), ("mslot", "_music_slot"), ("era", "_music_era"), ("cdst", "_status"), ("vm", "_fe_vm"), ("credits", "_scd_credits_mailbox")] + [("fmv", "fmv"), ("rec", "_fe_ta_rec"), ("save", "_scd_save_mailbox")])
if STAFF_REQUESTED:
    SYMS += "," + ",".join(f"{key}={SYMBOLS[name]}" for key, name in (("staff", "_fe_staff_times_qa"), ("mloop", "_music_loop")))
TA_FILE = 692
MAX_TIME = 9 * 3600 + 59 * 60 + 59


def run(name, script, backup_in=None, timeout=900, system_dir=None):
    folder = OUT / name
    folder.mkdir(exist_ok=True)
    (folder / "script.txt").write_text(script)
    env = os.environ.copy()
    env.pop("SCD_BACKUP_INPUT", None)
    env.update(SCD_SYMS=SYMS, SCD_BACKUP_OUTPUT=str(folder / "backup.bin"))
    if backup_in:
        env["SCD_BACKUP_INPUT"] = str(backup_in)
    args = [HARNESS, ROOT / ".deps/beetle-saturn/mednafen_saturn_libretro.dylib", ROOT / "dist/sonic-cd-saturn-prototype.cue",
            system_dir if system_dir is not None else ROOT / "assets/private", folder, folder / "script.txt"]
    with (folder / "core.log").open("w") as err:
        r = subprocess.run(["nice", "-n", "20"] + list(map(str, args)), env=env, cwd=ROOT, stdout=subprocess.PIPE,
                           stderr=err, text=True, timeout=timeout)
    (folder / "results.log").write_text(r.stdout)
    peeks = {}
    for line in r.stdout.splitlines():
        m = re.match(r"frame=\d+ peekb? (\S+)((?: [0-9a-f]{2,8})+)$", line)
        if m:
            peeks[m.group(1)] = [int(x, 16) for x in m.group(2).split()]
    return r.returncode, r.stdout, peeks, folder / "backup.bin"


TITLE = "run 200\nuntil TITL 3000\nrun 240\n"
# Title menu: Start opens it; Right moves to the next option; A selects.
OPEN_MENU = "hold START 4\nrun 90\n"


def pass_case(name, **detail):
    report["cases"].append(dict(name=name, passed=True, **detail))
    write_report()
    print(f"PASS {name}: " + ", ".join(f"{k}={v}" for k, v in detail.items()), flush=True)


def fail(name, message, out=""):
    report["cases"].append(dict(name=name, passed=False, message=message))
    report["status"] = "failed"
    write_report()
    print(f"FAIL: frontend {name}: {message}")
    if out:
        print("\n".join(out.splitlines()[-8:]))
    sys.exit(1)


# ---- Backup RAM fixtures -------------------------------------------------------
def progress_record(zone=0, act=0, era=0, gen=1, completed=0):
    data = bytearray(b"SCDS\x02\x20\x00\x00" + struct.pack(">I", gen) + bytes([zone, act, era, 0, 0, 0, completed, 0]) + bytes(8))
    return data + struct.pack(">I", zlib.crc32(data))


def file_blocks(image, name):
    """Blocks of a BIOS-written file: the directory block, then the data blocks it lists."""
    for b in range(2, 512):
        blk = image[b * 64:(b + 1) * 64]
        if blk[4:15] == name.encode() and blk[0] & 0x80:
            size = struct.unpack(">I", blk[30:34])[0]
            return b, size
    return None, 0


def file_spans(image, name):
    """(offset, length) runs holding the file's data, in order (Sega BUP layout:
    the block list follows the directory entry and ends with 0; data follows the list)."""
    first, size = file_blocks(image, name)
    if first is None:
        return None, 0
    payload = []  # absolute offsets in chain order
    chain = [first]
    idx = 0
    off = 34
    while True:
        if off == 64:
            idx += 1
            if idx >= len(chain):
                raise RuntimeError("block list overruns the chain")
            off = 4
        payload.append(chain[idx] * 64 + off)
        off += 1
        if len(payload) % 2 == 0:
            a, b = payload[-2], payload[-1]
            entry = image[a] << 8 | image[b]
            if entry == 0:
                break
            chain.append(entry)
    data = []
    while len(data) < size:
        if off == 64:
            idx += 1
            off = 4
        data.append(chain[idx] * 64 + off)
        off += 1
    return data, size


def read_file(image, name):
    offs, size = file_spans(image, name)
    return None if offs is None else bytes(image[o] for o in offs)


def write_file(image, name, payload):
    offs, size = file_spans(image, name)
    assert offs is not None and size == len(payload)
    for o, v in zip(offs, payload):
        image[o] = v


def ta_decode(d):
    # "SCDT" v1 (generation 0) or v2 (24-bit generation in bytes 13-15), src/time_attack.h.
    gen = d[13] << 16 | d[14] << 8 | d[15]
    assert d[:4] == b"SCDT" and d[4] in (1, 2) and (d[4] == 1) == (gen == 0), "TA file invalid"
    assert zlib.crc32(d[:688]) == struct.unpack(">I", d[688:692])[0], "TA file CRC"
    times = [struct.unpack(">I", d[16 + i * 4:20 + i * 4])[0] for i in range(84)]
    names = [bytes(d[352 + i * 4:355 + i * 4]) for i in range(84)]
    return {"unlock": d[8], "flags": d[9], "times": times, "names": names, "generation": gen}


TA_PAIR = ("SCDSATURNTA", "SCDSATURNTB")


def ta_current(image):
    """(name, bytes) of the Classic record file with the newer generation (both may exist
    after a power cut between the new file's write and the old one's removal)."""
    best = None
    for name in TA_PAIR:
        d = read_file(image, name)
        if d is None:
            continue
        gen = ta_decode(d)["generation"]
        if best is None or ((gen - best[2]) & 0xFFFFFF) and ((gen - best[2]) & 0xFFFFFF) < 0x800000:
            best = (name, d, gen)
    assert best, "no Classic TA file"
    return best[0], best[1]


def ta_encode(d, times=None, flags=None):
    d = bytearray(d)
    if flags is not None:
        d[9] = flags
    if times:
        for i, t in times.items():
            d[16 + i * 4:20 + i * 4] = struct.pack(">I", t)
    d[688:692] = struct.pack(">I", zlib.crc32(bytes(d[:688])))
    return bytes(d)


def frames(m, s, f):
    return m * 3600 + s * 60 + f


# ---- Cases -------------------------------------------------------------------------
CASES = sys.argv[1:] or ["ta-hidden", "ta-menu", "ta-run", "ta-pair", "ta-reload", "ta-thresholds", "ta-objects", "ta-bigring", "ta-death", "ta-pause-exit", "sound-test", "sound-test-ss8", "sound-test-images", "attract-demos", "attract-demos-cdpp", "attract-fmv", "visual-mode", "visual-mode-movies"]
# QA fixture preparation also requests thresholds alone. Its record must be
# produced in this invocation before the threshold cases read it from state.
if "ta-thresholds" in CASES and "ta-run" not in CASES:
    CASES = ["ta-run", *CASES]
state = {}


def new_game_backup():
    if "new" in state:
        return state["new"]
    rc, out, peeks, backup = run("new-game", TITLE + OPEN_MENU + "tap A\nuntil SCD2 3000\nrun 240\n")
    if rc:
        fail("new-game", f"harness status {rc}", out)
    state["new"] = backup
    return backup


def zone_fixture(zones_cleared):
    image = bytearray(new_game_backup().read_bytes())
    first, size = file_blocks(image, "SCDSATURN00")
    assert first is not None and size == 32, "new game wrote no SCDSATURN00"
    write_file(image, "SCDSATURN00", progress_record(zone=min(zones_cleared, 6), completed=1 if zones_cleared >= 7 else 0,
                                                     act=2 if zones_cleared >= 7 else 0, era=2 if zones_cleared >= 7 else 0))
    path = OUT / f"fixture-zones{zones_cleared}.bin"
    path.write_bytes(image)
    return path


MENU_TRACE = "peek trace trace 0 4\n"


def title_options(name, backup):
    """Opens the title menu and steps Right through it; returns the options seen."""
    script = TITLE + OPEN_MENU + MENU_TRACE.replace("trace trace", "m0 trace")
    for i in range(1, 5):
        script += f"hold RIGHT 4\nrun 60\npeek m{i} trace 0 4\n"
    rc, out, peeks, backup_out = run(name, script, backup)
    if rc:
        fail(name, f"harness status {rc}", out)
    sels = [peeks[f"m{i}"][2] >> 16 & 255 for i in range(5)]
    return sels, backup_out


if "ta-hidden" in CASES:
    sels, _ = title_options("ta-hidden", new_game_backup())
    # Selections: NEW GAME 1, CONTINUE 2, then RAM DATA 3. TIME ATTACK would add a 4th.
    if max(sels) != 3:
        fail("ta-hidden", f"menu reached selection {max(sels)}")
    pass_case("ta-hidden", selections=sels)

if any(c in CASES for c in ("ta-menu", "ta-run", "ta-reload", "ta-objects", "ta-bigring", "ta-death", "ta-pause-exit", "ta-thresholds")):
    fixture = zone_fixture(1)
    sels, written = title_options("ta-unlock", fixture)
    # The title only reads the records (retail writes them with a new record): a cold
    # boot leaves backup RAM byte-identical (tools/test_save_progression.py sequence-cold).
    if written.read_bytes() != fixture.read_bytes():
        fail("ta-unlock", "the title changed backup RAM")
    if max(sels) != 4:   # NEW GAME, CONTINUE, TIME ATTACK, RAM DATA
        fail("ta-unlock", f"menu selections {sels}")
    state["ta-fixture"] = written
    pass_case("ta-unlock", selections=sels, backup="unchanged")

MENU_ROUTES = {}


def menu_enter(name, fixture, option):
    """Title, menu, the cursor moved to option by identity (tools/title_menu.py: the
    fixture's own menu, read once per fixture and option), then 'peek sel'. Returns
    (script, position)."""
    key = (str(fixture), option)
    if key not in MENU_ROUTES:
        rc, out, probe, _ = run(f"{name}-menu", title_menu.PROBE, fixture)
        if rc:
            fail(name, f"menu probe: harness status {rc}", out)
        try:
            MENU_ROUTES[key] = title_menu.route(probe, option)
        except ValueError as e:
            fail(name, str(e))
    walk, position = MENU_ROUTES[key]
    return TITLE + OPEN_MENU + walk + "peek sel trace 0 4\n", position


def ta_enter(name):
    """TIME ATTACK, A: its menu screen."""
    script, position = menu_enter(name, state["ta-fixture"], title_menu.TIME_ATTACK)
    return script + "tap A\nuntil FEND 600\nrun 30\n"

if "ta-menu" in CASES:
    script = ta_enter("ta-menu") + "peek enter trace 0 4\npeek song mslot 0 1\nshot ta-menu\n" + \
        "tap A\ntap RIGHT\nshot ta-start\ntap LEFT\ntap LEFT\ntap A\ntap UP\ntap A\nuntil TITL 900\npeek exit trace 0 4\n"
    rc, out, peeks, _ = run("ta-menu", script, state["ta-fixture"])
    if rc:
        fail("ta-menu", f"harness status {rc}", out)
    if peeks["enter"][0] != 0x46454E44 or peeks["enter"][2] & 255 != 1:
        fail("ta-menu", f"no Time Attack screen: {peeks['enter']}", out)
    if peeks["exit"][0] != 0x5449544C:
        fail("ta-menu", f"EXIT did not return to the title: {peeks['exit']}", out)
    # TA.C game_init CDPlay: the Time Attack song, cue 11 = disc slot 35.
    if peeks["song"][0] != 35:
        fail("ta-menu", f"menu song slot {peeks['song'][0]}, expected 35", out)
    pass_case("ta-menu", selection=peeks["sel"][2] >> 16 & 255, screen="FEND", song_slot=peeks["song"][0], exit="TITL")

def route_updates(script, name):
    """tests/routes "COUNT PAD" lines as SCD buttons per simulation update: the host applies
    script pad i at update i+4 (tools/act_reference_from_script.py)."""
    pads = []
    for line in (ROOT / script).read_text().split("\n"):
        if line.strip():
            n, pad = map(int, line.split())
            pads += [pad] * n
    native = lambda p: (1 if p & 16 else 0) | (2 if p & 32 else 0) | (4 if p & 64 else 0) | (8 if p & 128 else 0) | (16 if p & 1 else 0)
    out = OUT / name
    out.write_text("".join(f"{native(pads[r - 4]) if 0 <= r - 4 < len(pads) else 0}\n" for r in range(1, len(pads) + 5)))
    return out.relative_to(ROOT)


if "ta-run" in CASES:
    # Round 1 (Palmtree Panic), act 1, START; the stored p0A route clears R11.
    script = ta_enter("ta-run") + "tap A\ntap RIGHT\ntap A\nuntil SCD2 900\npeek ta0 ta 0 3\n" + \
        f"route {route_updates('tests/routes/ppz/p0A.seq.txt', 'p0A.updates')} 20000\n" + \
        "peek seen ta 0 3\nuntil FEND 3000\nrun 30\npeek ta1 ta 0 3\npeek rec rec 0 3\nshot ta-record\n" + \
        "tap A\ntap A\ntap A\ntap A\nrun 30\npeek done trace 0 4\nshot ta-saved\n"
    rc, out, peeks, backup = run("ta-run", script, state["ta-fixture"], timeout=1800)
    if rc:
        fail("ta-run", f"harness status {rc}", out)
    route = re.search(r"route \S+ updates=(\d+) of (\d+) mismatches=(\d+)", out)
    ta0, ta1, rec = peeks["ta0"], peeks["ta1"], peeks["rec"]
    mode0, entry0 = ta0[0] >> 24, ta0[0] >> 16 & 255
    aborted1, pending1, frames1 = ta1[0] >> 8 & 255, ta1[0] & 255, ta1[1]
    if mode0 != 1 or entry0 != 0:
        fail("ta-run", f"run state mode={mode0} entry={entry0}", out)
    if aborted1 or not 0 < frames1 < 18000:
        fail("ta-run", f"result aborted={aborted1} frames={frames1}", out)
    image = backup.read_bytes()
    d = ta_decode(ta_current(image)[1])
    if d["times"][0] != frames1 or d["times"][1] != 18000:
        fail("ta-run", f"saved times {d['times'][:3]} != run {frames1}", out)
    state["ta-run"] = backup
    state["ta-seen"] = peeks["seen"][2] & 255
    pass_case("ta-run", frames=frames1, time=f"{frames1 // 3600}'{frames1 // 60 % 60:02}\"{frames1 % 60 * 100 // 60:02}",
              route=route.groups() if route else None, saved_name=d["names"][0].hex())

if "ta-pair" in CASES:
    # The record file pair (src/time_attack.c). ta-run stores twice (the record, then
    # the name), so it ends in SCDSATURNTB, generation 2, with SCDSATURNTA removed. Here
    # that file becomes an earlier build's single v1 SCDSATURNTA (renamed in its
    # directory block); a new record must load it, store generation 1 to SCDSATURNTB
    # and remove SCDSATURNTA, then the name store generation 2 back to SCDSATURNTA and
    # remove SCDSATURNTB. Other files keep their bytes.
    src = state.get("ta-run")
    if not src:
        fail("ta-pair", "needs ta-run")
    image = bytearray(src.read_bytes())
    name, d = ta_current(image)
    if name != "SCDSATURNTB" or ta_decode(d)["generation"] != 2 or read_file(image, "SCDSATURNTA") is not None:
        fail("ta-pair", f"ta-run left {name} generation {ta_decode(d)['generation']}")
    first, _ = file_blocks(image, "SCDSATURNTB")
    image[first * 64 + 4:first * 64 + 15] = b"SCDSATURNTA"
    legacy = bytearray(d)
    legacy[4], legacy[13:16] = 1, b"\0\0\0"
    write_file(image, "SCDSATURNTA", ta_encode(legacy))
    fixture = OUT / "fixture-ta-legacy.bin"
    fixture.write_bytes(image)
    before = ta_decode(read_file(image, "SCDSATURNTA"))
    script = ta_enter("ta-pair") + "tap A\ntap RIGHT\ntap A\nuntil SCD2 900\n" + \
        f"route {route_updates('tests/routes/ppz/p0A.seq.txt', 'p0A.updates')} 20000\n" + \
        "until FEND 3000\nrun 30\npeek ta1 ta 0 3\ntap A\ntap A\ntap A\ntap A\nrun 30\n"
    rc, out, peeks, backup = run("ta-pair", script, fixture, timeout=1800)
    if rc:
        fail("ta-pair", f"harness status {rc}", out)
    after_image = backup.read_bytes()
    frames2 = peeks["ta1"][1]
    if read_file(after_image, "SCDSATURNTB") is not None or read_file(after_image, "SCDSATURNTA") is None:
        fail("ta-pair", "SCDSATURNTB left behind or SCDSATURNTA missing", out)
    after = ta_decode(read_file(after_image, "SCDSATURNTA"))
    want = sorted(before["times"][:3] + [frames2])[:3]
    if after["generation"] != 2 or after["times"][:3] != want or after["times"][3:] != before["times"][3:]:
        fail("ta-pair", f"generation {after['generation']} times {after['times'][:3]} (want {want})", out)
    if read_file(after_image, "SCDSATURN00") != read_file(image, "SCDSATURN00"):
        fail("ta-pair", "the progress record changed")
    pass_case("ta-pair", legacy="v1 SCDSATURNTA loaded", stored="TB generation 1, TA removed; TA generation 2, TB removed",
              times=after["times"][:3])

if "ta-reload" in CASES:
    src = state.get("ta-run")
    if not src:
        fail("ta-reload", "needs ta-run")
    rc, out, peeks, _ = run("ta-reload", ta_enter("ta-reload") + "tap A\nrun 20\npeek rec rec 0 3\n", src)
    if rc:
        fail("ta-reload", f"harness status {rc}", out)
    saved = ta_decode(ta_current(src.read_bytes())[1])["times"][0]
    if peeks["rec"][0] != saved:
        fail("ta-reload", f"menu record {peeks['rec'][0]} != saved {saved}", out)
    pass_case("ta-reload", record=saved)

if "ta-thresholds" in CASES:
    src = state.get("ta-run")
    if not src:
        fail("ta-thresholds", "needs ta-run (its SCDSATURNTA)")
    image = bytearray(src.read_bytes())
    # A completed progress save unlocks all 21 acts (UnlockTimeAttackLevel after each zone).
    write_file(image, "SCDSATURN00", progress_record(zone=6, act=2, era=2, completed=1))
    ta_name, ta = ta_current(image)
    results = []
    # ATTACK.MMD 0xff2cd6-0xff2d1a: centisecond act totals just below and at each limit.
    cs = lambda f: f // 3600 * 6000 + f // 60 % 60 * 100 + f % 60 * 100 // 60
    def acts_for(target, below):
        best = None
        for a in range(1, 30000):
            if 20 * cs(a) > target:
                break
            for b in range(max(1, a - 120), a + 120):
                t = 20 * cs(a) + cs(b)
                # Below: the largest total under the limit. At: the smallest total at or over it.
                if (below and t < target and (best is None or t > best[0])) or \
                   (not below and t >= target and (best is None or t < best[0])):
                    best = (t, a, b)
        return best
    limits = [(30 * 6000 + 21 * 100 + 5, 0x02), (25 * 6000 + 46 * 100 + 12, 0x04), (37 * 6000 + 27 * 100 + 57, 0x08)]
    for limit, bit in limits:
        for below in (True, False):
            total, a, b = acts_for(limit, below)
            times = {e * 3: (a if e else b) for e in range(21)}
            img = bytearray(image)
            write_file(img, ta_name, ta_encode(ta, times=times, flags=0x20))
            path = OUT / f"fixture-total{total}.bin"
            path.write_bytes(img)
            name = f"ta-threshold-{total}"
            # scd_ta_records: unlock at byte 591, title_flags at 592 (src/time_attack.h).
            rc, out, peeks, backup = run(name, TITLE + "run 30\npeek flags rec 588 2\n", path)
            if rc:
                fail("ta-thresholds", f"{name} harness status {rc}", out)
            unlock, flags = peeks["flags"][0] & 255, peeks["flags"][1] >> 24
            if unlock != 21 or bool(flags & bit) != below:
                fail("ta-thresholds", f"total {total} cs: unlock {unlock} flags {flags:#x}, bit {bit:#x} expected {below}")
            if backup.read_bytes() != path.read_bytes():
                fail("ta-thresholds", f"total {total}: the title changed backup RAM")
            results.append((total, hex(flags)))
    pass_case("ta-thresholds", totals=results)

SEEN = {1: "time post", 2: "1UP monitor", 4: "Amy", 8: "big ring"}
if "ta-objects" in CASES:
    if "ta-seen" not in state:
        fail("ta-objects", "needs ta-run")
    # Positive control: the same R11 route from NEW GAME draws them.
    script = TITLE + OPEN_MENU + "tap A\nuntil SCD2 3000\n" + \
        f"route {route_updates('tests/routes/ppz/p0A.seq.txt', 'p0A.updates')} 9400\npeek seen ta 0 3\n"
    rc, out, peeks, _ = run("ta-objects-normal", script)
    if rc:
        fail("ta-objects", f"normal run status {rc}", out)
    normal, ta = peeks["seen"][2] & 255, state["ta-seen"]
    if normal & 7 != 7:
        fail("ta-objects", f"control run drew only {[v for k, v in SEEN.items() if normal & k]}")
    if ta & 15:
        fail("ta-objects", f"Time Attack drew {[v for k, v in SEEN.items() if ta & k]}")
    pass_case("ta-objects", normal=[v for k, v in SEEN.items() if normal & k], time_attack=[v for k, v in SEEN.items() if ta & k])

# Start+C+Left (src/main.c debug fixture): Act 1 Present before the goal post with 50
# rings; the harness steers into the big ring (tools/emulator_test.c bigring).
BIGRING = "run 300\nhold C+LEFT+START 2\nbigring 3000\npeek end trace 0 1\npeek special game 0 1\n"
if "ta-bigring" in CASES:
    rc, out, peeks, _ = run("ta-bigring-normal", TITLE + OPEN_MENU + "tap A\nuntil SCD2 3000\n" + BIGRING)
    if rc:
        fail("ta-bigring", f"normal run status {rc}", out)
    normal = peeks["special"][0]
    rc, out2, peeks2, _ = run("ta-bigring", ta_enter("ta-bigring") + "tap A\ntap RIGHT\ntap A\nuntil SCD2 900\n" + BIGRING, state["ta-fixture"])
    if rc:
        fail("ta-bigring", f"time attack run status {rc}", out2)
    ta, ta_end = peeks2["special"][0], peeks2["end"][0]
    magic = lambda v: v.to_bytes(4, "big").decode("latin-1")
    # Normal play enters Special Stage 1 ('SSGM'); Time Attack has no ring (Level End/Main.asm:358)
    # and the act clear returns to the menu ('FEND').
    if normal != 0x5353474D or ta == 0x5353474D or ta_end != 0x46454E44:
        fail("ta-bigring", f"normal special={magic(normal)!r}; time attack special={magic(ta)!r} end={magic(ta_end)!r}")
    pass_case("ta-bigring", normal="SSGM (special stage)", time_attack=f"no special stage, {magic(ta_end)}")

# Start+C+Right (src/main.c debug fixture) hurts Sonic with no rings: he dies.
KILL = "run 300\nhold C+RIGHT+START 2\n"
if "ta-death" in CASES:
    rc, out, peeks, _ = run("ta-death", ta_enter("ta-death") + "tap A\ntap RIGHT\ntap A\nuntil SCD2 900\n" + KILL + "run 120\npeek tasong mslot 0 1\nuntil FEND 1200\nrun 10\npeek ta ta 0 3\n", state["ta-fixture"])
    if rc:
        fail("ta-death", f"harness status {rc}", out)
    m = [int(x) for x in re.findall(r"until FEND after (\d+)", out)]
    rc2, out2, peeks2, _ = run("ta-death-normal", TITLE + OPEN_MENU + "tap A\nuntil SCD2 3000\n" + KILL + "run 180\npeek song mslot 0 1\nuntil TITL 2400\n")
    if rc2:
        fail("ta-death", f"normal run status {rc2}", out2)
    n = [int(x) for x in re.findall(r"until TITL after (\d+)", out2)]
    ta_wait, normal_wait = m[-1], n[-1]
    aborted = peeks["ta"][0] >> 8 & 255
    # Sonic/Main.asm:2429-2443: 60 frames after the fall in Time Attack, 480 otherwise.
    if not aborted or normal_wait - ta_wait < 400:
        fail("ta-death", f"aborted={aborted} time attack {ta_wait} frames vs normal {normal_wait}")
    # Game Over/Main.asm:66-71: the game over song (cue 12, slot 36) with no lives left,
    # not in Time Attack (Sonic/Main.asm .CapLives loads no game over object there).
    if peeks2["song"][0] != 36 or peeks["tasong"][0] == 36:
        fail("ta-death", f"song slots normal {peeks2['song'][0]} time attack {peeks['tasong'][0]}")
    pass_case("ta-death", time_attack_to_menu=ta_wait, normal_to_title=normal_wait, aborted=aborted, game_over_song=peeks2["song"][0])

if "ta-pause-exit" in CASES:
    rc, out, peeks, _ = run("ta-pause-exit", ta_enter("ta-pause-exit") + "tap A\ntap RIGHT\ntap A\nuntil SCD2 900\nrun 400\ntap START\nrun 20\ntap A\nuntil FEND 300\nrun 10\npeek ta ta 0 3\n", state["ta-fixture"])
    if rc:
        fail("ta-pause-exit", f"harness status {rc}", out)
    if not peeks["ta"][0] >> 8 & 255:
        fail("ta-pause-exit", f"run not marked aborted: {peeks['ta']}")
    pass_case("ta-pause-exit", aborted=1, frames=peeks["ta"][1])

# Sound test: Menu/Main.asm ObjMenu_SoundTestCheat taps on the press-start screen.
SOUND_TEST = TITLE + "tap DOWN\ntap DOWN\ntap DOWN\ntap LEFT\ntap RIGHT\ntap A\nuntil FEND 900\nrun 20\n"
def held(button, steps):
    # UpdateSelection steps on every 8th frame of the delay counter: 8 frames per step.
    # Input reaches the game about 2 frames late: let the last step land before peeking.
    return f"hold {button} {steps * 8}\nrun 4\n" if steps else ""
if "sound-test" in CASES:
    script = SOUND_TEST + "peek enter trace 0 4\npeekb st0 st 0 10\nenergy silent 60\n"
    # FM 05 = FM_RING (request 149, resident bank).
    script += held("DOWN", 5) + "peekb fm st 0 10\ntap A\nenergy fm 60\n"
    # PCM 04 = SCMD_YESSFXT (request 121, resident); PCM 00 = "Future" (not in a resident bank).
    script += held("RIGHT", 1) + "peekb pcm0 st 0 10\ntap A\nenergy pcm0 90\n" + held("DOWN", 4) + "peekb pcm st 0 10\ntap A\nenergy pcm 90\n"
    # DA 00 = Palmtree Panic Present (CD track 2); DA 24 = Time Attack music (no track).
    script += held("RIGHT", 1) + "peekb da0 st 0 10\ntap A\nrun 60\nenergy da 60\n" + held("UP", 10) + "peekb da st 0 10\nshot sound-test\ntap A\nrun 90\nenergy da24 60\n"
    script += "tap START\nuntil TITL 900\n"
    rc, out, peeks, _ = run("sound-test", script)
    if rc:
        fail("sound-test", f"harness status {rc}", out)
    e = {k: int(v) for k, v in re.findall(r"energy (\w+) (\d+)", out)}
    sel = lambda name: tuple(peeks[name][:4])  # type, fm, pcm, da
    if peeks["enter"][2] & 255 != 2 or sel("st0") != (0, 0, 0, 0):
        fail("sound-test", f"entry {peeks['enter']} {sel('st0')}", out)
    if sel("fm") != (0, 5, 0, 0) or sel("pcm") != (1, 5, 4, 0) or sel("da0") != (2, 5, 4, 0) or sel("da") != (2, 5, 4, 24):
        fail("sound-test", f"selections fm={sel('fm')} pcm={sel('pcm')} da0={sel('da0')} da={sel('da')}", out)
    # DA 24: the Time Attack song (Sound.inc CDDA_TMATK, disc slot 35).
    if e["silent"] != 0 or e["fm"] < 10**6 or e["pcm"] < 10**6 or e["da"] < 10**6 or e["da24"] < 10**6:
        fail("sound-test", f"energies {e}", out)
    pass_case("sound-test", energies=e, missing="PCM 00 'Future' silent" if e["pcm0"] < 10**5 else "none")

if "sound-test-ss8" in CASES:
    # CheckEasterEgg: FM 07, PCM 07, DA 07 then Start: the Special Stage 8 message for two seconds.
    script = SOUND_TEST + held("DOWN", 7) + held("RIGHT", 1) + held("DOWN", 7) + held("RIGHT", 1) + held("DOWN", 7) + \
        "peekb sel st 0 10\nhold START 2\nrun 30\npeekb msg st 0 10\nshot ss8-message\nuntil_word game 0 5353474d 600\nrun 60\npeek stage game 0 4\nshot ss8-stage\n"
    rc, out, peeks, _ = run("sound-test-ss8", script)
    if rc:
        fail("sound-test-ss8", f"harness status {rc}", out)
    sel = tuple(peeks["sel"][:4])
    result = peeks["msg"][8]
    if sel != (2, 7, 7, 7) or result != 1:
        fail("sound-test-ss8", f"selection {sel} result {result}", out)
    if peeks["stage"][0] != 0x5353474D:
        fail("sound-test-ss8", f"Special Stage 8 did not start: {peeks['stage']}", out)
    pass_case("sound-test-ss8", selection="07/07/07", message="WELCOME TO SECRET SPECIAL STAGE", launch="SSGM (special stage running)")

if "sound-test-images" in CASES:
    # CheckEasterEgg exits 2-6 (FM, PCM, DA): the five secret pictures (Sound Test Image.asm).
    # Each steady picture against the retail program (tools/secret_images_retail.py), pixel
    # for pixel in Mega Drive colour levels; Start held leaves it, faded, for the title.
    import visual_mode_pixels as vp
    secrets = ROOT / "build/secret-images"
    want = hashlib.sha256((ROOT / "tools/secret_images_retail.py").read_bytes()).hexdigest()
    path = secrets / "retail.json"
    if not path.exists() or json.loads(path.read_text())["inputs"]["secret_images_retail.py"] != want:
        r = subprocess.run(["nice", "-n", "20", sys.executable, "tools/secret_images_retail.py"], cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            fail("sound-test-images", "retail reference (tools/secret_images_retail.py) failed", r.stdout + r.stderr)
    codes = [(46, 12, 25), (42, 3, 1), (40, 12, 11), (42, 4, 21), (44, 11, 9)]
    counts = (80, 17, 34)
    # Boss (cue 8), Metallic Madness Present (zone 6 era 0), D.A. Garden (13), final boss (10),
    # Palmtree Panic Good Future (zone 0 era 2): src/music_routes.h scd_music_slot.
    songs = (8, 30, 37, 34, 2)

    def pick(value, count):
        return held("DOWN", value) if value <= count - value else held("UP", count - value)
    detail = {}
    for n, (fm, pcm, da) in enumerate(codes, 1):
        name = f"sound-test-image{n}"
        script = SOUND_TEST + pick(fm, counts[0]) + held("RIGHT", 1) + pick(pcm, counts[1]) + held("RIGHT", 1) + pick(da, counts[2]) + \
            "peekb sel st 0 10\nhold START 2\nuntil_word vm 0 00000007 900\npeek loading era 0 1\n" + \
            "until_word vm 0 00000008 900\nrun 30\npeek shown vm 0 9\nshot picture\nrun 60\npeek song mslot 0 1\npeek cd cdst 0 3\n" + \
            "hold START 4\nuntil TITL 900\npeek exit vm 0 9\n"
        rc, out, peeks, _ = run(name, script)
        if rc:
            fail("sound-test-images", f"{name}: harness status {rc}", out)
        if tuple(peeks["sel"][1:4]) != (fm, pcm, da):
            fail("sound-test-images", f"{name}: selection {peeks['sel'][:4]}", out)
        shown, ex = peeks["shown"], peeks["exit"]
        if shown[0] != 8 or shown[6] != n or shown[4] != 24 or ex[0] != 0 or ex[5] != 24:
            fail("sound-test-images", f"{name}: shown {shown} exit {ex}", out)
        # SPX.asm: the music starts after the picture's file loads (the CD block cannot play
        # CD-DA and read at once). Stopped (music_era -1) while the picture loads; then its
        # song slot, CD status PLAY (3) within that slot's track.
        song, cd = peeks["song"][0], peeks["cd"]
        if peeks["loading"][0] != 0xFFFFFFFF or song != songs[n - 1] or cd[0] >> 24 & 15 != 3:
            fail("sound-test-images", f"{name}: music during load {peeks['loading']} slot {song} cd {cd}", out)
        # vp.retail() reads vp.RETAIL; put the Visual Mode folder back for the later cases.
        menu_retail, vp.RETAIL = vp.RETAIL, secrets
        try:
            retail = vp.retail(str(n))
        finally:
            vp.RETAIL = menu_retail
        px = vp.saturn(OUT / name / "picture.ppm")
        at = vp.origin(px, retail)
        if at is None:
            fail("sound-test-images", f"{name}: the retail picture is not in the frame")
        bad = vp.differ(px[2], retail, *at)
        if bad:
            fail("sound-test-images", f"{name}: {bad} pixels differ from retail")
        detail[n] = f"{fm:02}/{pcm:02}/{da:02} exact, music slot {song} playing after the load"
    pass_case("sound-test-images", pictures=detail, fades="24 frames in (from white), 24 out", exit="Start held, TITL")

def attract_demos(case, backup=None):
    # IPX.asm Demo cycle at each title time-out: FMV (not run yet), R11A, SS1, R43C, SS6, R82A.
    # Each zone demo's Sonic x/y per update against the retail program (tools/retail_demo_probe.py),
    # rows paired by input word: retail update = word - 1 - 22 (R11A) or - 41 (R43C, R82A).
    folder = OUT / case
    folder.mkdir(exist_ok=True)
    script = "run 200\nuntil TITL 3000\n"
    for name in ("R11A", "R43C", "R82A"):
        # R11A follows the opening movie (Demo id 0) and a second title time-out.
        script += f"demotrace {folder / name}.txt 30000\nuntil TITL 3000\n"
    script += "peek mode save 0 12\n"
    rc, out, peeks, _ = run(case, script, backup, timeout=3600)
    if rc:
        fail(case, f"harness status {rc}", out)
    detail = {}
    for name, off in (("R11A", 22), ("R43C", 41), ("R82A", 41)):
        subprocess.run(["python3", "tools/retail_demo_probe.py", name, str(folder / f"{name}.retail.txt")], cwd=ROOT, check=True,
                       stdout=subprocess.DEVNULL)
        sat = [tuple(map(int, l.split()[:3])) for l in (folder / f"{name}.txt").read_text().splitlines()]
        ret = {int(l.split()[0]): tuple(map(int, l.split()[1:3])) for l in (folder / f"{name}.retail.txt").read_text().splitlines()}
        if len(sat) < 1800 or sat[-1][0] != 0x800:
            fail(case, f"{name} played {len(sat)} rows ending at word {sat[-1][0] if sat else None}", out)
        # The native mailbox truncates negative y toward zero (player.y / 65536); retail floors.
        # The native mailbox truncates negative y toward zero; a level that wraps vertically
        # (TT3, y mod 2048) may report the wrap one update apart.
        near = lambda a, b: a[0] == b[0] and (a[1] == b[1] or (b[1] < 0 and a[1] - b[1] == 1) or (a[1] - b[1]) % 2048 == 0)
        pairs = [(w - 1 - off, (x, y)) for w, x, y in sat if w - 1 - off in ret and w - 1 - off > 0]
        match = sum(1 for u, xy in pairs if near(xy, ret[u]))
        first = next((u for u, xy in pairs if not near(xy, ret[u])), None)
        detail[name] = f"{match}/{len(pairs)} updates equal retail" + (f", first difference at update {first}" if first else "")
        # All three equal retail (R82A since the BEAM Y half-size fix, src/objects_mm_act3.inc).
        if match != len(pairs):
            fail(case, f"{name} differs from retail: {detail[name]}", out)
    return peeks, detail



if "attract-demos" in CASES:
    _, detail = attract_demos("attract-demos")
    pass_case("attract-demos", **detail)

if "attract-demos-cdpp" in CASES:
    # MODE CD++ (SCDSATURNCF flags 31, from tools/test_cdpp_routes.py toggle): the demos replay
    # retail input, so they run Classic (src/player_plus.c scd_plus_classic_hold) and must
    # still equal retail on every update. Save mailbox slot 11 after them: setting 31 in
    # bits 8-15, the act flags the demos latched (0) in bits 0-7.
    cdpp = ROOT / "build/cdpp-qa/backup-cdpp.bin"
    if not cdpp.exists():
        subprocess.run([sys.executable, "tools/test_cdpp_routes.py", "toggle"], cwd=ROOT, capture_output=True)
    if not cdpp.exists():
        fail("attract-demos-cdpp", "needs build/cdpp-qa/backup-cdpp.bin (tools/test_cdpp_routes.py toggle)")
    peeks, detail = attract_demos("attract-demos-cdpp", cdpp)
    mode = peeks["mode"][11]
    if mode >> 8 & 255 != 31 or mode & 255:
        fail("attract-demos-cdpp", f"save mailbox slot 11 {mode:#x}: want setting 31, demo act flags 0")
    pass_case("attract-demos-cdpp", setting="CD++ (31)", demo_flags=mode & 255, **detail)

# scd_fmv_mailbox (src/fmv_saturn.h): [1] 0x504C4159-style state, [5] pictures shown.
if "attract-fmv" in CASES:
    # IPX.asm Demo id 0 (Demo_OpenFMV): the first title time-out plays the opening movie.
    # The title times out after about 1,100 frames; 2,500 frames in, the movie is playing.
    script = "run 200\nuntil TITL 3000\nrun 2500\npeek playing fmv 0 6\nshot opening\nuntil TITL 12000\npeek done fmv 0 6\n"
    rc, out, peeks, _ = run("attract-fmv", script, timeout=3600)
    if rc:
        fail("attract-fmv", f"harness status {rc}", out)
    playing, done = peeks["playing"], peeks["done"]
    if done[5] < 50 or done[5] <= playing[5]:
        fail("attract-fmv", f"movie did not play: playing {playing} done {done}", out)
    pass_case("attract-fmv", pictures_shown=done[5], state=hex(done[1]), back="TITL")

# ---- Visual Mode (src/visual_mode.c; Visual Mode/Main.asm, IPX.asm VisualMode) -----------
# _fe_vm words: 0 phase (1 load, 2 fade in, 3 menu, 4 fade out, 5 movie, 6 "Thank You",
# 0 back to the title), 1 frames, 2 selection, 3 menus run, 4 fade-in frames, 5 fade-out
# frames, 6 last movie (selection), 7 its fmv_play result, 8 "Thank You" calls.
VM_MENU = "until_word vm 0 00000003 600\nrun 10\n"


def vm_enter(name, fixture):
    """VISUAL MODE by identity, A, its menu. Returns (script, title position)."""
    script, position = menu_enter(name, fixture, title_menu.VISUAL_MODE)
    return script + "tap A\nuntil FEND 900\n" + VM_MENU, position


def vm_fixture(name):
    fixture = OUT / "fixture-total154611.bin"   # ta-thresholds: act total under 25'46"12 sets bit 2
    if not fixture.exists():
        subprocess.run([sys.executable, "tools/test_frontend_emulator.py", "ta-thresholds"], cwd=ROOT, capture_output=True)
    if not fixture.exists():
        fail(name, "needs ta-thresholds (its fixture)")
    return fixture


def vm_retail(name):
    """The retail menu screens (tools/visual_mode_retail.py), made again when its inputs changed."""
    import visual_mode_pixels as vp
    path = vp.RETAIL / "retail.json"
    want = hashlib.sha256((ROOT / "tools/visual_mode_retail.py").read_bytes()).hexdigest()
    if not path.exists() or json.loads(path.read_text())["summary"]["inputs"]["visual_mode_retail.py"] != want:
        r = subprocess.run(["nice", "-n", "20", sys.executable, "tools/visual_mode_retail.py"], cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            fail(name, "retail reference (tools/visual_mode_retail.py) failed", r.stdout + r.stderr)
    return vp, json.loads(path.read_text())["summary"]


def vm_screens(name, folder, wanted):
    """Each shot against its retail screen, pixel for pixel in Mega Drive colour levels."""
    vp, _ = vm_retail(name)
    result, at = {}, None
    for shot, screen in wanted:
        retail = vp.retail(screen)
        px = vp.saturn(folder / f"{shot}.ppm")
        at = at or vp.origin(px, retail)
        if at is None:
            fail(name, f"shot {shot}: the retail {screen} screen is not in the frame")
        bad = vp.differ(px[2], retail, *at)
        if bad:
            fail(name, f"shot {shot}: {bad} pixels differ from the retail {screen} screen")
        result[shot] = screen
    return result


if "visual-mode" in CASES:
    fixture = vm_fixture("visual-mode")
    _, retail = vm_retail("visual-mode")
    # The menu after its fade in (EXIT selected), each selection as retail shows it, the
    # wraps, Right as Up and Left as Down; OPENING (Start skips it, retail-legal) and back
    # to the menu, which starts again on EXIT; B on EXIT (B selects, as A, C and Start).
    moves = [("DOWN", "sel1"), ("DOWN", "sel2"), ("DOWN", "sel3"), ("DOWN", "sel4"), ("DOWN", "wrap0"),
             ("UP", "up4"), ("RIGHT", "right3"), ("LEFT", "left4")]
    enter, vm_position = vm_enter("visual-mode", fixture)
    script = enter + "peek in vm 0 9\nshot sel0\n"
    for button, shot in moves:
        script += f"tap {button}\nrun 10\nshot {shot}\n"
    script += "tap UP\ntap UP\ntap UP\nrun 10\npeek opening vm 0 9\ntap A\nuntil_word vm 0 00000005 300\nrun 600\npeek playing fmv 0 6\n" + \
        "hold START 4\nuntil_word vm 12 00000002 900\n" + VM_MENU + "peek back vm 0 9\npeek backtrace trace 0 4\nshot back0\n" + \
        "tap B\nuntil TITL 900\npeek exit vm 0 9\n"
    rc, out, peeks, _ = run("visual-mode", script, fixture, timeout=3600)
    if rc:
        fail("visual-mode", f"harness status {rc}", out)
    if peeks["sel"][2] >> 16 & 255 != vm_position:
        fail("visual-mode", f"title selection {peeks['sel']}, VISUAL MODE at {vm_position}", out)
    vin, op, back, ex = peeks["in"], peeks["opening"], peeks["back"], peeks["exit"]
    if vin[2] != 0 or vin[4] != retail["fade_in_frames"] or op[2] != 1:
        fail("visual-mode", f"menu entry {vin} (retail fade in {retail['fade_in_frames']} frames), before OPENING {op}", out)
    if peeks["playing"][5] < 10:
        fail("visual-mode", f"opening not shown: {peeks['playing']}", out)
    if back[3] != 2 or back[6] != 1 or back[7] != 1 or back[2] != 0 or peeks["backtrace"][0] != 0x46454E44:
        fail("visual-mode", f"no menu after the opening: {back} trace {peeks['backtrace']}", out)
    if ex[0] != 0 or ex[5] != 2 * retail["fade_out_frames"] or ex[3] != 2:
        fail("visual-mode", f"exit {ex} (retail fade out {retail['fade_out_frames']} frames)", out)
    screens = vm_screens("visual-mode", OUT / "visual-mode", [("sel0", "sel0")] + [(m[1], m[1]) for m in moves] + [("back0", "sel0")])
    pass_case("visual-mode", screens=f"{len(screens)} exact against retail VM____.MMD", fade_in=vin[4], fade_out=ex[5] // 2,
              opening_pictures=peeks["playing"][5], opening="Start skip, back to the menu on EXIT", exit="B on EXIT, TITL")

if "visual-mode-movies" in CASES:
    fixture = vm_fixture("visual-mode-movies")
    # GOOD ENDING, BAD ENDING and PENCIL TEST played to their ends (retail skips none of
    # them); after the good ending the "Thank You" hook runs (IPX.asm:1184), then the menu.
    # Each ending ends on ENDING.MMD's "PRESENTED BY SEGA" card, which the Japanese
    # program holds until Start (scd_fmv_mailbox [3] = card phase 4, src/fmv_saturn.h);
    # the "Thank You" screen runs until a button or its 3-minute timer (credits mailbox
    # [1] 'THKP', src/credits_saturn.h).
    card = "until_word fmv 12 CA040000 20000\ntap START\n"
    enter, vm_position = vm_enter("visual-mode-movies", fixture)
    script = enter + "tap DOWN\ntap DOWN\nrun 10\npeek gsel vm 0 9\ntap A\nuntil_word vm 0 00000005 300\n" + \
        card + "until_word credits 4 54484B50 3000\nrun 300\ntap START\n" + \
        "until_word vm 12 00000002 20000\npeek good fmv 0 6\npeek g vm 0 9\n" + VM_MENU + \
        "tap DOWN\ntap DOWN\ntap DOWN\nrun 10\npeek bsel vm 0 9\ntap A\nuntil_word vm 0 00000005 300\n" + card + \
        "until_word vm 12 00000003 20000\npeek bad fmv 0 6\npeek b vm 0 9\n" + VM_MENU + \
        "tap DOWN\ntap DOWN\ntap DOWN\ntap DOWN\nrun 10\npeek psel vm 0 9\ntap A\nuntil_word vm 0 00000005 300\n" + \
        "until_word vm 12 00000004 8000\npeek pencil fmv 0 6\npeek p vm 0 9\n" + VM_MENU + "shot back0\ntap A\nuntil TITL 900\npeek exit vm 0 9\n"
    rc, out, peeks, _ = run("visual-mode-movies", script, fixture, timeout=7200)
    if rc:
        fail("visual-mode-movies", f"harness status {rc}", out)
    detail = {}
    for key, sel in (("good", 2), ("bad", 3), ("pencil", 4)):
        v, f, chosen = peeks[key[0]], peeks[key], peeks[key[0] + "sel"]
        if chosen[2] != sel or v[6] != sel or v[7] != 0 or v[8] != 1 or f[5] < 50:
            fail("visual-mode-movies", f"{key}: selection {chosen} state {v} fmv {f}", out)
        detail[key] = f[5]
    if peeks["exit"][0] != 0 or peeks["exit"][3] != 4:
        fail("visual-mode-movies", f"exit {peeks['exit']}", out)
    vm_screens("visual-mode-movies", OUT / "visual-mode-movies", [("back0", "sel0")])
    pass_case("visual-mode-movies", pictures=detail, thanks_hook="once, after the good ending", back="menu on EXIT (exact), TITL")

STAFF_WORDS = ("phase", "frames", "scroll", "load_ok", "result", "fade_in", "fade_out", "pack_bytes", "tiles", "music_started", "start_exit")
STAFF_MOVES = (("scroll2", "DOWN", 1, 2), ("scroll510", "DOWN", 254, 510),
               ("bottom", "DOWN", 1, 511), ("clamped", "DOWN", 4, 511),
               ("scroll509", "UP", 1, 509), ("scroll1", "UP", 254, 1),
               ("top", "UP", 1, 0), ("up_clamped", "UP", 1, 0),
               ("both_top", "UP+DOWN", 1, 0))


def staff_times_fixture(template, flags):
    """Reuse the existing preset-switch BUP constructors, without importing its runner."""
    if type(flags) is not int or flags not in (0, 31) or len(template) != 32768 or not any(template[:128]):
        raise ValueError("need a pinned functional BIOS format template and flags0/31")
    source = ROOT / "tools/test_frontend_preset_switch.py"
    names = {"add_file", "settings", "records"}
    nodes = [n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name in names]
    if len(nodes) != 3 or {n.name for n in nodes} != names:
        raise ValueError("preset-switch helper contract changed")
    helpers = dict(struct=struct, zlib=zlib)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), helpers)
    image = bytearray(32768); image[:128] = template[:128]
    files = {"SCDSATURN00": progress_record(zone=1), "SCDSATURNCF": helpers["settings"](int(bool(flags)))}
    for name, preset, generation in (("SCDSATURNTA", 0, 2), ("SCDSATURNTB", 0, 1), ("SCDSATURNTP", 1, 2), ("SCDSATURNTQ", 1, 1)):
        files[name] = helpers["records"](preset, generation)
        ta_decode(files[name])
    cursor = 2
    for name, data in files.items():
        cursor = helpers["add_file"](image, name, data, cursor)
        if read_file(image, name) != data:
            raise ValueError("private save fixture did not roundtrip")
    return bytes(image)


def staff_times_script(flags, pack_bytes):
    """Actual title input only. Capture transitions with existing C commands."""
    if type(flags) is not int or flags not in (0, 31) or type(pack_bytes) is not int or not 0 < pack_bytes <= 0x14000 or pack_bytes & 2047:
        raise ValueError("unbound preset/pack size")
    lines = [TITLE, "peek initial_mode save 44 1\n", f"until_word save 44 {flags << 8:08x} 0\n"]
    def assert_word(symbol, offset, value):
        # Existing until_word with MAX0 asserts without advancing another frame.
        lines.append(f"until_word {symbol} {offset} {value:08x} 0\n")
    def assert_qa(phase, scroll, result, outward, exited):
        for offset, value in ((0, phase), (8, scroll), (12, 1), (16, result), (20, 24), (24, outward), (28, pack_bytes), (36, 1), (40, exited)):
            assert_word("staff", offset, value)
    def observe(label, shot=False):
        lines.extend((f"peek {label} staff 0 11\n", f"peek {label}_trace trace 0 6\n"))
        if shot:
            lines.append(f"shot {label}\n")
    def capture(label, button, count, all_shots=False):
        for i in range(count):
            lines.append(f"hold {button} 1\n" if button else "run 1\n")
            observe(f"{label}_{i}", all_shots or i < 8 or i >= count - 8)
    def enter(prefix):
        # Same tested tap timing: first five taps, then four continuous C frames.
        lines.append("tap RIGHT\ntap RIGHT\ntap UP\ntap UP\ntap DOWN\n")
        observe(prefix + "_before_c", True)
        capture(prefix + "_c", "C", 4, True)
        lines.append("until_word staff 0 00000002 900\n")
        observe(prefix + "_fade_start", True)
        capture(prefix + "_fade", None, 60, True)
        lines.append("until_word staff 0 00000003 120\nrun 8\nfail_unless_magic FEND\n")
        observe(prefix, True)
        assert_qa(3, 0, 0, 0, 0)
        lines.append(f"energy {prefix}_energy 30\n")
        for key, symbol in (("song", "mslot"), ("era", "era"), ("loop", "mloop"), ("mode", "save")):
            lines.append(f"peek {prefix}_{key} {symbol} {44 if key == 'mode' else 0} 1\n")
        lines.append(f"peek {prefix}_cd cdst 0 3\n")
        assert_word("mslot", 0, 5); assert_word("era", 0, 5); assert_word("mloop", 0, 1)
        assert_word("save", 44, flags << 8)
    def leave(prefix):
        observe(prefix + "_before_start", True)
        capture(prefix + "_start", "START", 4, True)
        capture(prefix + "_fade", None, 60, True)
        lines.append("until TITL 900\n")
        lines.append(f"energy {prefix}_energy 30\npeek {prefix}_cd cdst 0 3\n")
        observe(prefix)
        assert_qa(5, 0, 3, 24, 1)
        lines.extend((f"peek {prefix}_title trace 0 4\n", f"peek {prefix}_song mslot 0 1\n",
                      f"peek {prefix}_era era 0 1\n", f"peek {prefix}_loop mloop 0 1\n", f"peek {prefix}_mode save 44 1\n"))
        assert_word("mslot", 0, 9); assert_word("era", 0, 9); assert_word("mloop", 0, 0)
        assert_word("save", 44, flags << 8)
    enter("loaded")
    for label, button, count, scroll in STAFF_MOVES:
        capture(label + "_hold", button, count)
        capture(label + "_release", None, 8, True)
        observe(label, True)
        assert_qa(3, scroll, 0, 0, 0)
    leave("ended")
    lines.append("run 240\n")
    enter("reentered")
    leave("ended_again")
    return "".join(lines)


def staff_times_words(peeks, label, count):
    values = peeks.get(label)
    if not isinstance(values, list) or len(values) != count or any(type(v) is not int or not 0 <= v <= 0xffffffff for v in values):
        raise ValueError(f"missing/malformed {label}: expected{count} words")
    return values


def staff_times_observations(peeks, flags, pack_bytes, energies):
    """Fail closed on missing ABI words, input acknowledgments or scene outcomes."""
    def words(label, count):
        return staff_times_words(peeks, label, count)
    def qa(label):
        return dict(zip(STAFF_WORDS, words(label, 11)))
    def same(label, expected):
        got = qa(label)
        if any(got[key] != value for key, value in expected.items()):
            raise ValueError(f"{label}: {got}, expected {expected}")
        return got
    if type(flags) is not int or flags not in (0, 31) or type(pack_bytes) is not int or not 0 < pack_bytes <= 0x14000 or pack_bytes & 2047:
        raise ValueError("unbound preset/pack size")
    loaded = qa("loaded")
    if loaded["frames"] < 25 or not 1 <= loaded["tiles"] <= 2048:
        raise ValueError("invalid loaded frame/tile state")
    base = dict(load_ok=1, fade_in=24, pack_bytes=pack_bytes, tiles=loaded["tiles"], music_started=1)
    screen = dict(base, phase=3, result=0, fade_out=0, start_exit=0)
    acknowledgments = {}
    previous_frames = 0
    for label, scroll in [("loaded", 0)] + [(v[0], v[3]) for v in STAFF_MOVES] + [("reentered", 0)]:
        got = same(label, dict(screen, scroll=scroll))
        tr = words(label + "_trace", 6)
        if tr[0] != 0x46454e44 or tr[2:] != [4, 3, scroll, 0]:
            raise ValueError(f"{label}: no released Staff screen4 {tr}")
        if label != "reentered" and got["frames"] <= previous_frames:
            raise ValueError("Staff frame counter did not advance")
        previous_frames = got["frames"]
    for label in ("loaded", "reentered"):
        if qa(label)["frames"] < 25:
            raise ValueError("Staff frame counter did not include prep/fade")
        if [words(label + key, 1)[0] for key in ("_song", "_era", "_loop")] != [5, 5, 1]:
            raise ValueError("Shoes cue/loop request differs; this is not audible sound proof")
        # Continuous snapshots contain prep plus all24 fade counter values.
        counts = {qa(label + "_fade_start")["fade_in"]}
        counts.update(qa(f"{label}_c_{i}")["fade_in"] for i in range(4))
        counts.update(qa(f"{label}_fade_{i}")["fade_in"] for i in range(60))
        if not set(range(25)) <= counts:
            raise ValueError(f"{label}: incomplete fade-in capture {sorted(counts)}")
    for label, button, count, _ in STAFF_MOVES:
        wanted = {"DOWN": 2, "UP": 1, "UP+DOWN": 3}[button]
        trace = [words(f"{label}_{part}_{i}_trace", 6) for part, size in (("hold", count), ("release", 8)) for i in range(size)]
        if any(t[0] != 0x46454e44 or t[2] & 255 != 4 or t[3] != 3 or t[2] >> 8 not in (0, wanted) for t in trace):
            raise ValueError(f"{label}: unexpected scene/input state")
        if button == "UP+DOWN":
            # Beetle's default opposite_directions=false clears both pad bits.
            # This verifies filtering/stability, not the game's raw both-button order.
            if any(t[2] != 4 or t[4] != 0 for t in trace):
                raise ValueError(f"{label}: expected core-filtered neutral at scroll0")
            acknowledgments[label] = dict(requested_hold=wanted, delivered_hold=0, core_filtered=True,
                                         game_opposing_order_tested=False, observed_samples=len(trace))
        else:
            accepted = [i for i, t in enumerate(trace) if t[2] >> 8 == wanted]
            if not accepted or accepted[0] >= 8 or any(t[2] != 4 for t in trace[-2:]):
                raise ValueError(f"{label}: missing/late held-input acknowledgment or release")
            acknowledgments[label] = dict(first_ack_frame=accepted[0], observed_samples=len(trace))
        if any(b[1] < a[1] or b[1] - a[1] > 1 for a, b in zip(trace, trace[1:])):
            raise ValueError(f"{label}: unknown Staff update cadence")
    for label in ("ended", "ended_again"):
        ended = same(label, dict(base, phase=5, result=3, fade_out=24, start_exit=1, scroll=0))
        before_start = same(label + "_before_start", dict(screen, scroll=0))
        if ended["frames"] < before_start["frames"] + 24:
            raise ValueError("exit frame counter did not include24 fade frames")
        if words(label + "_title", 4)[0] != 0x5449544c or [words(label + key, 1)[0] for key in ("_song", "_era", "_loop")] != [9, 9, 0]:
            raise ValueError("normal title/music state was not restored")
        counts = {qa(label + "_before_start")["fade_out"]}
        counts.update(qa(f"{label}_start_{i}")["fade_out"] for i in range(4))
        counts.update(qa(f"{label}_fade_{i}")["fade_out"] for i in range(60))
        if not set(range(25)) <= counts:
            raise ValueError(f"{label}: incomplete fade-out capture {sorted(counts)}")
    for label in ("initial_mode", "loaded_mode", "ended_mode", "reentered_mode", "ended_again_mode"):
        if words(label, 1)[0] != flags << 8:
            raise ValueError(f"{label}: setting/active preset changed")
    for label in ("loaded", "reentered", "ended", "ended_again"):
        if words(label + "_cd", 3)[0] >> 24 & 15 != 3:
            raise ValueError(f"{label}: CD status is not PLAY")
        energy = energies.get(label + "_energy")
        if type(energy) is not int or energy <= 0:
            raise ValueError(f"{label}: no captured audio output")
    return dict(screen=4, abi_words=11, scroll=[0, 2, 510, 511, 511, 509, 1, 0], fade_in=24, fade_out=24,
                entries=2, exits=2, acknowledgments=acknowledgments, energies=energies,
                output_present=True, pixel_accepted=False, audio_accepted=False)


def staff_times_opposing_script(pack_bytes):
    """Classic-only raw pad supplement. UI code reads no preset setting."""
    if type(pack_bytes) is not int or not 0 < pack_bytes <= 0x14000 or pack_bytes & 2047:
        raise ValueError("unbound pack size")
    lines = [TITLE, "until_word save 44 00000000 0\n",
             "tap RIGHT\ntap RIGHT\ntap UP\ntap UP\ntap DOWN\ntap C\nuntil FEND 900\nuntil_word staff 0 00000003 900\nrun 8\n"]
    def observe(label, shot=False):
        lines.extend((f"peek {label} staff 0 11\n", f"peek {label}_trace trace 0 6\n"))
        if shot: lines.append(f"shot {label}\n")
    def check(phase, scroll, result, fade_out, start_exit):
        for offset, value in ((0, phase), (8, scroll), (12, 1), (16, result), (20, 24), (24, fade_out), (28, pack_bytes), (36, 1), (40, start_exit)):
            lines.append(f"until_word staff {offset} {value:08x} 0\n")
    def both(label, scroll):
        lines.append("hold UP+DOWN 1\n"); observe(label + "_hold_0", True)
        for i in range(8):
            lines.append("run 1\n"); observe(f"{label}_release_{i}", True)
        observe(label, True); check(3, scroll, 0, 0, 0)
    observe("raw_loaded", True); check(3, 0, 0, 0, 0)
    both("raw_top", 0)
    # Ordinary Down is unchanged by the core's opposing-pair option.
    lines.append("hold DOWN 256\nrun 8\n")
    observe("raw_bottom", True); check(3, 511, 0, 0, 0)
    both("raw_bottom_both", 509)
    lines.append("hold START 4\nuntil TITL 900\nrun 30\n")
    observe("raw_ended"); check(5, 509, 3, 24, 1)
    lines.extend(("peek raw_title trace 0 4\n", "peek raw_mode save 44 1\n", "peek raw_song mslot 0 1\n", "peek raw_loop mloop 0 1\n"))
    for symbol, offset, value in (("save", 44, 0), ("mslot", 0, 9), ("mloop", 0, 0)):
        lines.append(f"until_word {symbol} {offset} {value:08x} 0\n")
    return "".join(lines)


def staff_times_opposing_observations(peeks, pack_bytes):
    if type(pack_bytes) is not int or not 0 < pack_bytes <= 0x14000 or pack_bytes & 2047:
        raise ValueError("unbound pack size")
    def words(label, count): return staff_times_words(peeks, label, count)
    def qa(label): return dict(zip(STAFF_WORDS, words(label, 11)))
    loaded = qa("raw_loaded")
    if loaded["frames"] < 25 or not 1 <= loaded["tiles"] <= 2048:
        raise ValueError("invalid raw supplement entry")
    base = dict(load_ok=1, fade_in=24, pack_bytes=pack_bytes, tiles=loaded["tiles"], music_started=1)
    previous_frames = 0
    for label, scroll in (("raw_loaded", 0), ("raw_top", 0), ("raw_bottom", 511), ("raw_bottom_both", 509)):
        state = qa(label); expected = dict(base, phase=3, scroll=scroll, result=0, fade_out=0, start_exit=0)
        if any(state[k] != v for k, v in expected.items()) or words(label + "_trace", 6)[2:] != [4, 3, scroll, 0] or words(label + "_trace", 6)[0] != 0x46454e44:
            raise ValueError(f"{label}: raw supplement checkpoint differs")
        if state["frames"] <= previous_frames: raise ValueError("raw supplement frame counter did not advance")
        previous_frames = state["frames"]
    for label, allowed in (("raw_top", (0,)), ("raw_bottom_both", (511, 509))):
        traces = [words(label + "_hold_0_trace", 6)] + [words(f"{label}_release_{i}_trace", 6) for i in range(8)]
        if any(t[0] != 0x46454e44 or t[2] not in (4, 4 | 3 << 8) or t[3] != 3 or t[4] not in allowed for t in traces):
            raise ValueError(f"{label}: unknown raw direction/scroll state")
        accepted = [i for i, t in enumerate(traces) if t[2] >> 8 == 3]
        if not accepted or accepted[0] >= 8 or any(t[2] != 4 for t in traces[-2:]) or any(b[1] < a[1] or b[1] - a[1] > 1 for a, b in zip(traces, traces[1:])):
            raise ValueError(f"{label}: missing raw both-button acknowledgment/release")
        if traces[-1][1] <= traces[0][1] or any(b[4] > a[4] for a, b in zip(traces, traces[1:])):
            raise ValueError(f"{label}: unknown raw update/scroll sequence")
    ended = qa("raw_ended"); expected = dict(base, phase=5, scroll=509, result=3, fade_out=24, start_exit=1)
    if any(ended[k] != v for k, v in expected.items()) or ended["frames"] < qa("raw_bottom_both")["frames"] + 24:
        raise ValueError("raw supplement did not exit normally")
    if words("raw_title", 4)[0] != 0x5449544c or words("raw_mode", 1) != [0] or words("raw_song", 1) != [9] or words("raw_loop", 1) != [0]:
        raise ValueError("raw supplement title/preset restore differs")
    return dict(preset=0, core_opposite_directions="enabled", raw_both_acknowledged=True, game_opposing_order_tested=True,
                down_then_up={"top0": 0, "bottom511": 509}, entries=1, exits=1,
                preset_scope="Staff UI source has no preset reads;raw supplement Classic only",
                pixel_accepted=False, audio_accepted=False)


for staff_name, staff_flags in (("staff-times", 0), ("staff-times-cdpp", 31)):
    if staff_name in CASES:
        template = Path(os.environ["SCD_STAFF_TEMPLATE"])
        fixture = OUT / f"{staff_name}-input.bin"
        before = staff_times_fixture(template.read_bytes(), staff_flags)
        fixture.write_bytes(before)
        pack_bytes = (ROOT / "cd/STAFFTIM.BIN").stat().st_size
        script = staff_times_script(staff_flags, pack_bytes)
        report.update(phase="cooling", active_case=staff_name)
        write_report()
        cooldown(staff_last_heavy, 120)
        report["phase"] = "emulator"
        write_report()
        rc, output, peeks, backup = run(staff_name, script, fixture, timeout=1800, system_dir=Path(os.environ["SCD_STAFF_SYSTEM"]))
        staff_last_heavy = time.monotonic()
        if rc:
            fail(staff_name, f"harness status {rc}", output)
        try:
            energies = {key: int(value) for key, value in re.findall(r"energy (\w+) (\d+)", output)}
            detail = staff_times_observations(peeks, staff_flags, pack_bytes, energies)
            if backup.read_bytes() != before:
                raise ValueError("32KiB backup changed: progress/settings/both paired TA banks must remain identical")
        except (ValueError, KeyError, OSError) as error:
            fail(staff_name, str(error), output)
        pass_case(staff_name, **detail, preset=staff_flags, backup="all32768 bytes unchanged;progress/settings/four TA files present",
                  template_sha256=hashlib.sha256(template.read_bytes()).hexdigest(), input_backup_sha256=hashlib.sha256(before).hexdigest(),
                  script_sha256=hashlib.sha256(script.encode()).hexdigest(), captures="full raw PPMs;original pixel and audible audio acceptance remain open")

if "staff-times-opposing" in CASES:
    name = "staff-times-opposing"; template = Path(os.environ["SCD_STAFF_TEMPLATE"])
    before = staff_times_fixture(template.read_bytes(), 0); fixture = OUT / f"{name}-input.bin"; fixture.write_bytes(before)
    script = staff_times_opposing_script((ROOT / "cd/STAFFTIM.BIN").stat().st_size)
    report.update(phase="cooling", active_case=name, core_opposite_directions="enabled"); write_report()
    cooldown(staff_last_heavy, 120); report["phase"] = "emulator"; write_report()
    rc, output, peeks, backup = run(name, script, fixture, timeout=1800, system_dir=Path(os.environ["SCD_STAFF_SYSTEM"]))
    if rc: fail(name, f"harness status {rc}", output)
    try:
        detail = staff_times_opposing_observations(peeks, (ROOT / "cd/STAFFTIM.BIN").stat().st_size)
        if backup.read_bytes() != before: raise ValueError("raw supplement changed the32KiB backup")
    except (ValueError, KeyError, OSError) as error: fail(name, str(error), output)
    pass_case(name, **detail, backup="all32768 bytes unchanged", input_backup_sha256=hashlib.sha256(before).hexdigest(),
              script_sha256=hashlib.sha256(script.encode()).hexdigest())

report["status"] = "passed"
report["passed"] = True
write_report()
print(f"PASS: frontend emulator: {', '.join(c['name'] for c in report['cases'])}; disc {report['disc_sha256'][:16]}")
