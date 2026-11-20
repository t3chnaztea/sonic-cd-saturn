#!/usr/bin/env python3
"""OS-only lifetime monitor. Load before arming; never write a report file."""
import argparse
import datetime as dt
import json
import math
import os
import signal
import subprocess
import sys
import time

from power_guard import _OwnedTree

OS_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
# The volume that holds this checkout. SCD_QA_MOUNT overrides it. A checkout that
# is not on a mounted volume has no mount to watch, and os_health() then fails.
_HERE = os.path.abspath(__file__).split(os.sep)
MOUNT = os.environ.get("SCD_QA_MOUNT") or (
    os.sep.join(_HERE[:3]) if _HERE[1:2] == ["Volumes"] and len(_HERE) > 3 else None)


def emit(record):
    print(json.dumps(record, sort_keys=True), flush=True)


def os_health(allow_battery=False):
    """Read the OS mount table and power state, never the mounted filesystem."""
    try:
        table = subprocess.run(["/sbin/mount"], cwd="/", capture_output=True,
                               text=True, check=True, timeout=3).stdout
    except (OSError, subprocess.SubprocessError):
        return False, "mount_unknown"
    if not MOUNT:
        return False, "mount_unknown"
    if not any(line.partition(" on ")[2].startswith(MOUNT + " (")
               for line in table.splitlines()):
        return False, "mount_missing"
    try:
        power = subprocess.run(["/usr/bin/pmset", "-g", "batt"], cwd="/",
                               capture_output=True, text=True, check=True, timeout=3).stdout
    except (OSError, subprocess.SubprocessError):
        return False, "power_unknown"
    if "Now drawing from 'AC Power'" in power:
        return True, None
    if allow_battery and "Now drawing from 'Battery Power'" in power:
        return True, None
    return False, "battery" if "Now drawing from 'Battery Power'" in power else "power_unknown"


def signal_verified(tree, number, errors):
    """One uncertain identity must not suppress other verified signals."""
    pids = sorted(tree.owned, key=lambda pid: pid != tree.root)
    if number == signal.SIGKILL:
        pids.reverse()
    for pid in pids:
        try:
            if tree.verified(pid):
                os.kill(pid, number)
        except ProcessLookupError:
            pass
        except BaseException as error:
            errors.append(f"{pid} signal: {error!r}")


def stop_owned(trees, reason, settle=2.0, unbound=()):
    """Signal verified ownership without waiting for a U-state parent to stop."""
    errors = []
    for _ in range(3):
        for tree in trees:
            try:
                tree.refresh()
            except BaseException as error:
                errors.append(f"{tree.root} refresh: {error!r}")
            signal_verified(tree, signal.SIGSTOP, errors)
    for tree in trees:
        try:
            tree.refresh()
        except BaseException as error:
            errors.append(f"{tree.root} refresh: {error!r}")
        signal_verified(tree, signal.SIGKILL, errors)
    deadline = time.monotonic() + settle
    while True:
        live, uncertain = [], list(unbound)
        for tree in trees:
            try:
                live.extend(tree.survivors())
            except BaseException as error:
                uncertain.append(tree.root)
                errors.append(f"{tree.root} verify: {error!r}")
        if (not live and not uncertain) or time.monotonic() >= deadline:
            break
        time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))
    pending = bool(live or uncertain)
    return dict(status="pending_termination" if pending else "stopped",
                reason=reason, survivors=sorted(set(live))[:32],
                survivor_count=len(set(live)), uncertain_roots=sorted(set(uncertain))[:32],
                errors=[text[:240] for text in errors[:8]])


def watch(pids, deadline, poll=1.0, settle=2.0, requested=None, allow_battery=False):
    if deadline.tzinfo is None or deadline.utcoffset() is None:
        raise ValueError("deadline must have a UTC offset")
    if not math.isfinite(poll) or poll <= 0 or not math.isfinite(settle) or settle < 0:
        raise ValueError("poll must be positive and settle nonnegative")
    pids = list(dict.fromkeys(pids))
    if not pids or any(isinstance(pid, bool) or not isinstance(pid, int) or
                       pid <= 0 or pid == os.getpid() for pid in pids):
        raise ValueError("roots must be positive PIDs other than the watcher")
    # Keep relative ps resolution and subprocess cwd away from the QA volume.
    os.chdir("/")
    os.environ["PATH"] = OS_PATH
    trees = []
    root_births = {}
    try:
        for pid in pids:
            tree = _OwnedTree(pid)
            root_births[pid] = tuple(tree.owned[pid])
            # Discovery failure leaves this self-stopped root pending for coordinator cleanup.
            tree.refresh()
            if os.getpid() in tree.owned:
                raise ValueError("a root must not own the watcher")
            trees.append(tree)
        if requested:
            return stop_owned(trees, "interrupt", settle)
        if dt.datetime.now(dt.timezone.utc) >= deadline:
            return stop_owned(trees, "deadline", settle)
        healthy, reason = os_health(allow_battery=allow_battery) if allow_battery else os_health()
        if not healthy:
            return stop_owned(trees, reason, settle)
        emit(dict(event="armed", watcher_pid=os.getpid(), roots=pids,
                  identities=[dict(pid=tree.root, birth=list(root_births[tree.root]))
                              for tree in trees], deadline=deadline.isoformat()))
        while True:
            if requested:
                return stop_owned(trees, "interrupt", settle)
            if dt.datetime.now(dt.timezone.utc) >= deadline:
                return stop_owned(trees, "deadline", settle)
            live = [tree.survivors() for tree in trees]
            if not any(live):
                return dict(status="exited", reason="all_roots_exited",
                            survivors=[], survivor_count=0, uncertain_roots=[], errors=[])
            if any((tree.root not in owned or tree.owned.get(tree.root) != root_births[tree.root])
                   and owned for tree, owned in zip(trees, live)):
                return stop_owned(trees, "orphaned_descendants", settle)
            healthy, reason = os_health(allow_battery=allow_battery) if allow_battery else os_health()
            if not healthy:
                return stop_owned(trees, reason, settle)
            time.sleep(poll)
    except KeyboardInterrupt:
        return stop_owned(trees, "interrupt", settle,
                          [pid for pid in pids if pid not in {tree.root for tree in trees}])
    except BaseException as error:
        result = stop_owned(trees, "control_error", settle,
                            [pid for pid in pids if pid not in {tree.root for tree in trees}])
        result["errors"] = ([repr(error)[:240]] + result["errors"])[:8]
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", action="append", required=True, type=int)
    parser.add_argument("--deadline", required=True, type=dt.datetime.fromisoformat)
    parser.add_argument("--poll", type=float, default=1.0)
    parser.add_argument("--settle", type=float, default=2.0)
    parser.add_argument("--allow-battery", action="store_true")
    args = parser.parse_args(argv)
    requested, handlers = [], {}
    for number in (signal.SIGINT, signal.SIGTERM):
        handlers[number] = signal.signal(number, lambda sig, frame: requested.append(sig))
    try:
        result = watch(args.pid, args.deadline, args.poll, args.settle, requested,
                       allow_battery=args.allow_battery)
        # Control signals and verification have already completed before output.
        emit(result)
        return {"exited": 0, "stopped": 1, "pending_termination": 2}[result["status"]]
    except ValueError as error:
        parser.error(str(error))
    finally:
        for number, handler in handlers.items():
            signal.signal(number, handler)


if __name__ == "__main__":
    raise SystemExit(main())
