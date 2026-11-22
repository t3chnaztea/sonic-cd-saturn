"""Optional limits and durable metadata for local QA sessions."""
import fcntl
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import time


def _limit(requested, name, environ):
    if isinstance(requested, bool) or not isinstance(requested, int) or requested < 1:
        raise ValueError("requested workers must be a positive integer")
    values = os.environ if environ is None else environ
    raw = values.get(name)
    if raw is None:
        return requested
    if not isinstance(raw, str) or not re.fullmatch(r"[0-9]+", raw.strip()):
        raise ValueError(name + " must be a positive integer")
    cap = int(raw)
    if cap < 1:
        raise ValueError(name + " must be a positive integer")
    return min(requested, cap)


def worker_limit(requested, *, environ=None):
    return _limit(requested, "SCD_QA_MAX_WORKERS", environ)


def emulator_limit(requested, *, environ=None):
    return _limit(requested, "SCD_QA_MAX_EMULATORS", environ)


def _seconds(value):
    try:
        seconds = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("cooldown must be finite and nonnegative") from error
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError("cooldown must be finite and nonnegative")
    return seconds


def cooldown_seconds(*, environ=None):
    values = os.environ if environ is None else environ
    return _seconds(values.get("SCD_QA_COOLDOWN_SECONDS", "0"))


def cooldown(last_finished, seconds=None, *, clock=None, sleep=None):
    """Wait from the previous completion; the first job needs no delay."""
    delay = cooldown_seconds() if seconds is None else _seconds(seconds)
    if last_finished is None:
        return 0.0
    try:
        previous = float(last_finished)
    except (TypeError, ValueError) as error:
        raise ValueError("last completion must be finite") from error
    if not math.isfinite(previous):
        raise ValueError("last completion must be finite")
    clock = time.monotonic if clock is None else clock
    sleep = time.sleep if sleep is None else sleep
    started = clock()
    deadline = previous + delay
    if not math.isfinite(deadline):
        raise ValueError("cooldown deadline must be finite")
    while True:
        now = clock()
        if not math.isfinite(now):
            raise ValueError("cooldown clock must be finite")
        remaining = deadline - now
        if remaining <= 0:
            return max(0.0, now - started)
        sleep(min(remaining, 1.0))


def _sync_file(descriptor):
    os.fsync(descriptor)
    if sys.platform == "darwin":
        fcntl.fcntl(descriptor, fcntl.F_FULLFSYNC)


def atomic_json(path, value):
    """Replace JSON durably in an existing directory; create no ancestors."""
    path = Path(path)
    payload = json.dumps(value, indent=2, allow_nan=False) + "\n"
    descriptor, temporary = tempfile.mkstemp(
        prefix="." + path.name + ".", suffix=".tmp", dir=path.parent)
    published = False
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            _sync_file(stream.fileno())
            os.replace(temporary, path)
            published = True
            parent = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
            # Flush the rename metadata as well as the already-synced contents.
            _sync_file(stream.fileno())
    finally:
        if not published:
            primary = sys.exc_info()[1]
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            except OSError as cleanup_error:
                if primary is None:
                    raise
                primary.add_note("temporary cleanup failed: " + repr(cleanup_error))
