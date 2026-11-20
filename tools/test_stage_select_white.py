#!/usr/bin/env python3
"""Compile the actual Main WHITE helper against the held original-loop oracle."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

from qa_limits import atomic_json, cooldown, cooldown_seconds

ROOT = Path(__file__).resolve().parents[1]
PASS = "PASS: stage-select white helper: 1507328 exact comparisons; MSB, 8 anchors and wrong-order negative"


def code_context(text):
    """Mask C comments and literals without changing source offsets."""
    masked = list(text)
    pos, state, escaped = 0, "code", False
    while pos < len(text):
        c, pair = text[pos], text[pos:pos + 2]
        if state == "code":
            if pair in ("//", "/*"):
                state = "line" if pair == "//" else "block"
                masked[pos:pos + 2] = "  "
                pos += 2
                continue
            if c in ('"', "'"):
                state, escaped = c, False
                masked[pos] = " "
        elif state == "line":
            if c == "\n":
                state = "code"
            else:
                masked[pos] = " "
        elif state == "block":
            if pair == "*/":
                masked[pos:pos + 2] = "  "
                state = "code"
                pos += 2
                continue
            if c != "\n":
                masked[pos] = " "
        else:
            if c != "\n":
                masked[pos] = " "
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == state:
                state = "code"
        pos += 1
    return "".join(masked)


def extract_helper(text):
    signature = r"\bstatic\s+uint16_t\s+stage_select_level_white\s*\(\s*uint16_t\s+color\s*,\s*unsigned\s+steps\s*\)\s*\{"
    matches = list(re.finditer(signature, code_context(text)))
    if len(matches) != 1:
        raise ValueError("Expected one actual Main WHITE helper definition")
    start, pos = matches[0].start(), matches[0].end()
    depth, state = 1, "code"
    while pos < len(text):
        c, pair = text[pos], text[pos:pos + 2]
        if state == "line":
            if c == "\n":
                state = "code"
        elif state == "block":
            if pair == "*/":
                state = "code"
                pos += 1
        elif state in ('"', "'"):
            if c == "\\":
                pos += 1
            elif c == state:
                state = "code"
        elif pair in ("//", "/*"):
            state = "line" if pair == "//" else "block"
            pos += 1
        elif c in ('"', "'"):
            state = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start:pos + 1] + "\n"
        pos += 1
    raise ValueError("Unclosed actual Main WHITE helper")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "src/main.c")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cc", default="clang")
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    fixture = ROOT / "tools/test_stage_select_white.c"
    raw, fixture_raw = source.read_bytes(), fixture.read_bytes()
    digest = lambda data: hashlib.sha256(data).hexdigest()
    helper = extract_helper(raw.decode())
    compiler = shutil.which(args.cc)
    if compiler is None:
        raise ValueError("Native C compiler is unavailable")
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    if args.output is None:
        out = Path(tempfile.mkdtemp(prefix="stage-select-white-", dir=build))
    else:
        out = args.output.resolve()
        if not out.is_relative_to(build.resolve()):
            raise ValueError("Private test output must be under this checkout's build directory")
        out.mkdir(parents=True, exist_ok=False)
    include = out / "stage_select_white_actual.inc"
    include.write_text(helper)
    executable = out / "white-helper"
    command = ["/usr/bin/nice", "-n", "20", compiler, "-std=gnu11", "-O1", "-g",
               "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
               "-Wall", "-Wextra", "-Werror",
               '-DSCD_WHITE_ACTUAL_INCLUDE="' + str(include) + '"',
               str(fixture), "-o", str(executable)]
    report = dict(status="pending", source=str(source), source_sha256=digest(raw),
                  fixture_sha256=digest(fixture_raw), helper_sha256=digest(helper.encode()),
                  compiler=compiler, commands=[], comparisons=1507328,
                  target_cadence_accepted=False, hardware_accepted=False)
    save = lambda: atomic_json(out / "report.json", report)
    save()
    try:
        env = dict(os.environ, ASAN_OPTIONS="detect_leaks=0")
        previous = None
        for name, argv in (("compile", command),
                           ("run", ["/usr/bin/nice", "-n", "20", str(executable)])):
            cooldown(previous, max(120, cooldown_seconds()))
            if source.read_bytes() != raw or fixture.read_bytes() != fixture_raw or include.read_bytes() != helper.encode():
                raise ValueError("Test source changed")
            record = dict(name=name, argv=argv, status="pending")
            report["commands"].append(record)
            save()
            with (out / (name + ".log")).open("w") as stream:
                result = subprocess.run(argv, stdout=stream, stderr=subprocess.STDOUT,
                                        env=env, timeout=120, check=False)
            previous = time.monotonic()
            record.update(exit_code=result.returncode,
                          status="passed" if result.returncode == 0 else "failed")
            save()
            if result.returncode:
                raise RuntimeError(name + " failed; see " + str(out / (name + ".log")))
        if source.read_bytes() != raw or fixture.read_bytes() != fixture_raw or include.read_bytes() != helper.encode():
            raise ValueError("Test source changed")
        if (out / "run.log").read_text().strip() != PASS:
            raise ValueError("Conformance result differs")
        report["status"] = "passed"
        save()
        print(PASS)
    except BaseException as error:
        report.update(status="interrupted" if isinstance(error, (KeyboardInterrupt, SystemExit)) else "failed",
                      error=repr(error))
        try:
            save()
        except BaseException as secondary:
            error.add_note("Report checkpoint failed: " + repr(secondary))
        raise


if __name__ == "__main__":
    main()
