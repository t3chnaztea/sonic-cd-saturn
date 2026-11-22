#!/usr/bin/env python3
"""Run one local QA command on AC only, with a fixed aware ISO deadline.

Battery or an unreadable power state blocks launch and suspends the entire
owned process tree, including detached sessions. The deadline stays active. No emulator
is launched by this module's self tests. Output directories must be new.
"""
import argparse
import datetime as dt
import ctypes
import errno
import sys
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from qa_limits import atomic_json

ROOT = Path(__file__).resolve().parents[1]


def on_ac():
    try:
        result = subprocess.run(['pmset', '-g', 'batt'], capture_output=True, text=True, timeout=3)
        return result.returncode == 0 and "Now drawing from 'AC Power'" in result.stdout
    except (OSError, subprocess.TimeoutExpired):
        return False


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''): h.update(block)
    return h.hexdigest()


def inputs():
    names = subprocess.check_output(['git', 'ls-files', '-co', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
    names = {n for n in names if n and (n.startswith(('src/', 'tools/', 'tests/')) or n in ('Makefile', 'sources.lock.json'))}
    names.update(['sources.lock.json', '.toolchain/bin/sh-elf-gcc',
                  '.deps/beetle-saturn/mednafen_saturn_libretro.dylib',
                  '.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib'])
    return {n: digest(ROOT/n) for n in sorted(names) if (ROOT/n).is_file()}


# Darwin public SDK sys/proc_info.h: proc_bsdinfo (136 bytes), flavor 3.
# Kernel sec/usec birth identity prevents a recycled PID acquiring ownership.
class _BSDInfo(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in
                ('flags', 'status', 'xstatus', 'pid', 'ppid', 'uid', 'gid',
                 'ruid', 'rgid', 'svuid', 'svgid', 'reserved')] + [
                    ('comm', ctypes.c_char * 16), ('name', ctypes.c_char * 32)] + [
                (name, ctypes.c_uint32) for name in
                ('nfiles', 'pgid', 'pjobc', 'tdev', 'tpgid', 'nice')] + [
                    ('start_sec', ctypes.c_uint64), ('start_usec', ctypes.c_uint64)]


# Darwin SDK sys/proc_info.h: proc_bsdshortinfo, flavor 13 (64 bytes).
class _BSDShortInfo(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in
                ('pid', 'ppid', 'pgid', 'status')] + [
                    ('comm', ctypes.c_char * 16)] + [
                (name, ctypes.c_uint32) for name in
                ('flags', 'uid', 'gid', 'ruid', 'rgid', 'svuid', 'svgid', 'reserved')]


def _darwin_process_query(pid):
    """Return legacy identity plus bounded raw proof, without inferring disappearance."""
    info = _BSDInfo()
    lib = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
    query = lib.proc_pidinfo
    query.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]
    query.restype = ctypes.c_int
    if ctypes.sizeof(info) != 136:
        raise RuntimeError("unsupported Darwin process-info layout")
    # A nonzero argument retains birth identity for exiting/zombie processes.
    ctypes.set_errno(0)
    size = query(pid, 3, 1, ctypes.byref(info), ctypes.sizeof(info))
    error = ctypes.get_errno()
    proof = dict(size=size, errno=error, reported_pid=info.pid, observed_at=time.monotonic())
    if size == 136 and info.pid == pid:
        proof['kind'] = 'readable'
        return dict(birth=(info.start_sec, info.start_usec), ppid=info.ppid, pgid=info.pgid), proof
    proof['kind'] = 'gone_candidate' if size == 0 and error == errno.ESRCH else 'unknown'
    return None, proof


def _process_info(pid):
    if sys.platform == 'darwin':
        return _darwin_process_query(pid)[0]
    # Linux host tests retain the kernel start tick rather than rounded ps time.
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return dict(birth=(int(fields[19]),), ppid=int(fields[1]), pgid=int(fields[2]))
    except (OSError, ValueError, IndexError):
        return None


def _birth(pid):
    info = _process_info(pid)
    return info['birth'] if info is not None else None


def _processes():
    if sys.platform == 'darwin':
        if ctypes.sizeof(ctypes.c_int) != 4 or ctypes.sizeof(_BSDShortInfo) != 64:
            raise RuntimeError('unsupported Darwin discovery layout')
        lib = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
        list_pids = lib.proc_listpids
        list_pids.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_int]
        list_pids.restype = ctypes.c_int
        query = lib.proc_pidinfo
        query.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]
        query.restype = ctypes.c_int
        # One extra slot detects truncation at the process bound.
        pids = (ctypes.c_int * (32768 + 1))()
        capacity = ctypes.sizeof(pids)
        ctypes.set_errno(0)
        size = list_pids(1, 0, pids, capacity)
        if size <= 0 or size > capacity or size % ctypes.sizeof(ctypes.c_int):
            raise RuntimeError('invalid Darwin PID-list byte count')
        if size == capacity:
            raise RuntimeError('process discovery bound exceeded')
        positive = {pid for pid in pids[:size // ctypes.sizeof(ctypes.c_int)] if pid > 0}
        if len(positive) > 32768:
            raise RuntimeError('process discovery bound exceeded')
        table = {}
        for pid in positive:
            info = _BSDShortInfo()
            ctypes.set_errno(0)
            returned = query(pid, 13, 1, ctypes.byref(info), ctypes.sizeof(info))
            if returned != 64 or info.pid != pid:
                # An unreadable listed PID is still possibly live. Never infer its parent.
                table[pid] = (None, None, '?')
            else:
                table[pid] = (info.ppid, info.pgid,
                              'T' if info.status == 4 else 'Z' if info.status == 5 else '?')
        return table
    result = subprocess.run(['ps', '-axo', 'pid=,ppid=,pgid=,state='],
                            capture_output=True, text=True, check=True, timeout=3)
    lines = result.stdout.splitlines()
    if len(lines) > 32768:
        raise RuntimeError('process discovery bound exceeded')
    return {int(p[0]): (int(p[1]), int(p[2]), p[3])
            for line in lines if len(p := line.split()) == 4}


class _OwnedTree:
    """Only observed descendants; session/group changes do not drop ownership."""
    def __init__(self, pid):
        self.root = pid
        birth = _birth(pid)
        if birth is None:
            raise RuntimeError("cannot establish root process identity")
        self.owned = {pid: birth}
        self.table = {}

    def retirement_summary(self):
        # Legacy internal callers can set root/owned/table after __new__.
        if not hasattr(self, '_retired_counts'):
            self._retired_counts = dict(gone=0, reused=0)
            self._retired_recent = []
        return dict(scope='Retired generations omitted; not a full historical PID ledger.',
                    counts=dict(self._retired_counts), recent_limit=16,
                    recent=list(self._retired_recent))

    def _retire(self, pid, birth, reason, proof):
        if self.owned.get(pid) != birth:
            return
        self.retirement_summary()
        del self.owned[pid]
        self._retired_counts[reason] += 1
        self._retired_recent.append(dict(pid=pid, birth=list(birth), reason=reason, **proof))
        del self._retired_recent[:-16]

    def _refresh_darwin(self):
        observations = [(pid, birth, *_darwin_process_query(pid))
                        for pid, birth in list(self.owned.items())]
        gone = [item for item in observations if item[3]['kind'] == 'gone_candidate']
        later = None
        if gone:
            # This complete snapshot follows every candidate's failed raw query.
            list_started = time.monotonic()
            later = _processes()
            list_finished = time.monotonic()
        verified = set()
        for pid, birth, current, proof in observations:
            if current is not None:
                if current['birth'] != birth:
                    self._retire(pid, birth, 'reused',
                                 dict(proof, replacement_birth=list(current['birth'])))
                    continue
                verified.add(pid)
                if pid not in self.table:
                    self.table[pid] = (current['ppid'], current['pgid'], '?')
            elif proof['kind'] == 'gone_candidate' and pid not in later:
                self._retire(pid, birth, 'gone',
                             dict(proof, list_absent=True, list_count=len(later),
                                  list_started=list_started, list_finished=list_finished))
            else:
                row = (later if proof['kind'] == 'gone_candidate' else self.table).get(pid)
                # Unknown identity cannot retire a record. Only known Z is quiescent.
                if row is None or not row[2].startswith('Z'):
                    raise RuntimeError(f'live owned process identity unavailable: {pid} '
                                       f'(size={proof["size"]}, errno={proof["errno"]}, '
                                       f'reported_pid={proof["reported_pid"]})')
        return verified

    def verified(self, pid):
        birth = _birth(pid)
        if birth == self.owned[pid]:
            return True
        if birth is None:
            # A vanished/zombie process needs no suspension. An unreadable
            # identity on a still-live PID is uncertainty, never quiescence.
            current = _processes().get(pid)
            if current is not None and not current[2].startswith('Z'):
                raise RuntimeError(f'live owned process identity unavailable: {pid}')
        return False  # Gone, or a replacement PID whose birth does not match.

    def refresh(self):
        self.table = _processes()
        if sys.platform == 'darwin':
            verified = self._refresh_darwin()
        else:
            verified = {pid for pid, birth in self.owned.items()
                        if pid in self.table and self.verified(pid)}
        children = {}
        for pid, (parent, _, _) in self.table.items():
            children.setdefault(parent, []).append(pid)
        queue = list(verified)
        for parent in queue:
            if not self.verified(parent):
                continue
            for pid in children.get(parent, []):
                if pid in verified:
                    continue
                if sys.platform == 'darwin':
                    current, proof = _darwin_process_query(pid)
                else:
                    current, proof = _process_info(pid), None
                # The topology snapshot can be stale. Adopt only when one
                # kernel query supplies both this birth and the current PPID.
                if current is None or current['ppid'] != parent:
                    continue
                birth = current['birth']
                previous = self.owned.get(pid)
                if previous is not None and previous != birth and sys.platform == 'darwin':
                    self._retire(pid, previous, 'reused',
                                 dict(proof, replacement_birth=list(birth)))
                if pid not in self.owned and len(self.owned) >= 4096:
                    counts = self.retirement_summary()['counts']
                    raise RuntimeError(f'owned descendant bound exceeded '
                                       f'(retained={len(self.owned)}, retired={counts})')
                self.owned[pid] = birth
                if previous != birth:
                    # This generation postdates the snapshot; T/Z may belong to an older one.
                    self.table[pid] = (current['ppid'], current['pgid'], '?')
                verified.add(pid)
                queue.append(pid)
        return verified

    def signal(self, sig):
        # Root first when freezing; children cannot escape after their parents
        # stop. No killpg: a stale/reused group number never grants ownership.
        pids = sorted(self.owned, key=lambda pid: pid != self.root)
        if sig == signal.SIGKILL:
            pids.reverse()
        for pid in pids:
            if not self.verified(pid):
                continue
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass

    def freeze(self):
        for _ in range(4):
            self.refresh()
            before = dict(self.owned)
            self.signal(signal.SIGSTOP)
            live = self.refresh()
            stopped = all(self.table[pid][2].startswith(('T', 'Z')) for pid in live)
            if self.owned == before and stopped:
                return
        raise RuntimeError('owned descendant tree did not stop or quiesce')

    def describe(self):
        return [dict(pid=pid, birth=list(birth), pgid=self.table.get(pid, (0, None, ''))[1])
                for pid, birth in sorted(self.owned.items())]

    def survivors(self):
        live = self.refresh()
        return [pid for pid in live if not self.table[pid][2].startswith('Z')]


def run(command, output, deadline, power=on_ac, poll=1, capture_inputs=True):
    # The caller must provide an existing parent; never recreate a lost mount path.
    output.mkdir(exist_ok=False)
    record = dict(status='waiting_ac', passed=False, command=command,
                  started=dt.datetime.now().astimezone().isoformat(), deadline=deadline.isoformat(),
                  input_sha256={}, events=[])
    proc = None
    owned = None
    paused = False
    requested = []
    old_handlers = {}

    def event(status, reason=None):
        record['status'] = status
        record['events'].append(dict(at=dt.datetime.now().astimezone().isoformat(), status=status, reason=reason))
        save()
        print(status + (': ' + reason if reason else ''), flush=True)

    def save():
        atomic_json(output/'run.json', record)

    def remember():
        if owned is not None:
            description = owned.describe()
            retirement = owned.retirement_summary()
            if (record.get('owned_processes') != description or
                    record.get('ownership_retirement') != retirement):
                record['owned_processes'] = description
                record['ownership_retirement'] = retirement
                save()

    def cleanup_error(operation, error):
        record['cleanup_error'] = f'{operation}: {error!r}'
        record.update(status='interrupted', passed=False)

    def stop():
        if proc is None:
            return
        errors = (OSError, RuntimeError, subprocess.SubprocessError)
        # Quiesce before killing so supervisors cannot spawn an unobserved
        # detached group between discovery and termination. The deadline is hard.
        if owned is not None:
            try:
                owned.freeze()
            except errors as error:
                cleanup_error('freeze', error)
            try:
                owned.signal(signal.SIGKILL)
            except errors as error:
                cleanup_error('signal descendants', error)
            try:
                remember()
            except errors as error:
                cleanup_error('record ownership', error)
        try:
            if proc.poll() is None:
                proc.kill()  # Popen owns this unreaped direct child, never a PGID.
            proc.wait(timeout=5)
        except errors as error:
            cleanup_error('reap supervisor', error)
        if owned is not None:
            try:
                until = time.monotonic() + 2
                remaining = owned.survivors()
                while remaining and time.monotonic() < until:
                    owned.signal(signal.SIGKILL)
                    time.sleep(.02)
                    remaining = owned.survivors()
                record['cleanup_survivors'] = remaining
                if remaining:
                    cleanup_error('verify termination', RuntimeError('owned descendants survived'))
            except errors as error:
                cleanup_error('verify termination', error)

    for sig in (signal.SIGINT, signal.SIGTERM):
        old_handlers[sig] = signal.signal(sig, lambda signum, frame: requested.append(signum))
    try:
        save()
        with (output/'command.log').open('w') as log:
            while True:
                if requested or dt.datetime.now(dt.timezone.utc) >= deadline:
                    stop()
                    event('interrupted', 'stop signal' if requested else 'fixed deadline')
                    break
                ac = power()
                if proc is None:
                    if not ac:
                        time.sleep(poll)
                        continue
                    # Check again immediately before launch; fail closed.
                    if capture_inputs: record['input_sha256'] = inputs()
                    if not power(): continue
                    proc = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                    record['pid'] = proc.pid
                    owned = _OwnedTree(proc.pid)
                    # Stable launch binding survives retirement from current ownership.
                    record['root_identity'] = dict(pid=proc.pid, birth=list(owned.owned[proc.pid]))
                    save()
                    owned.refresh()
                    remember()
                    event('running', 'AC verified before launch')
                if not paused:
                    owned.refresh()
                    remember()
                rc = proc.poll()
                if rc is not None:
                    record['exit_code'] = rc
                    record['passed'] = rc == 0
                    event('passed' if rc == 0 else 'failed')
                    break
                if not ac and not paused:
                    owned.freeze()
                    remember()
                    paused = True
                    event('suspended_battery', 'owned descendants stopped across sessions; deadline remains active')
                elif ac and paused:
                    owned.signal(signal.SIGCONT)
                    paused = False
                    event('running', 'AC restored; existing owned descendants resumed')
                time.sleep(poll)
    except BaseException as error:
        stop()
        event('interrupted', repr(error))
        raise
    finally:
        stop()
        record['finished'] = dt.datetime.now().astimezone().isoformat()
        record['changed_inputs'] = [n for n, h in record['input_sha256'].items()
                                    if not (ROOT/n).is_file() or digest(ROOT/n) != h]
        binary = ROOT/'dist/sonic-cd-saturn-prototype.bin'
        if binary.is_file() and capture_inputs: record['disc_sha256'] = digest(binary)
        save()
        for sig, handler in old_handlers.items(): signal.signal(sig, handler)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deadline', required=True, type=dt.datetime.fromisoformat)
    parser.add_argument('--output', required=True, type=Path,
                        help='new output directory; its parent must already exist')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    assert args.deadline.tzinfo is not None, 'deadline must include a UTC offset'
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    assert command, 'command is required'
    record = run(command, args.output, args.deadline)
    raise SystemExit(0 if record['passed'] else 124 if record['status'] == 'interrupted' else 1)


if __name__ == '__main__': main()
