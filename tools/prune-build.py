#!/usr/bin/env python3
"""Prune build/: keep the newest --keep hardware-v* dirs; delete older hardware-v*, stale version-stamped top-level dirs, and dated dirs older than --days, unless referenced.

Dry run by default. Pass --apply to delete.

Candidates (nothing else is ever touched):
  * build/hardware-v<X.YYY>[suffix] dirs. The --keep newest versions stay.
    Suffixed dirs (hardware-v0.014-pre-memory-note) belong to their version.
  * Dated scratch dirs (name holds YYYYMMDD or YYYY-MM-DD) up to depth 3
    under build/, older than --days by name date (fallback: mtime).
    The outermost dated dir is the candidate; its children are not scanned.
  * Stale versioned scratch: top-level non-hardware dirs whose name holds a
    version stamp (v0NN, vNNN, v0.NNN; newest stamp wins) older than the
    oldest kept hardware-v version. Version-free dirs are never touched.

Any candidate referenced as build/<path> in a live text source is kept.
Sources: root *.md, docs/*.md, hardware-results/*.json, tests/**, tools/**,
Makefile, dist/*.json. ARCHIVE_TIER files (docs/archive/**, superseded
PLAN.md) count only with --include-archive.
"""

import argparse
import datetime as dt
import os
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor

REPO = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BUILD = "build"
MAX_TEXT = 2 * 1024 * 1024
MAX_DEPTH = 3
LIST_CAP = 40

HW_RE = re.compile(r"^hardware-v(\d+)\.(\d+)")
DATE_RE = re.compile(r"(?<!\d)(20\d{2})-?([01]\d)-?([0-3]\d)(?!\d)")
REF_RE = re.compile(rb"(?<![A-Za-z0-9_.\-])build/[A-Za-z0-9_.+\-/]+")
VER_RE = re.compile(r"(?<![A-Za-z0-9])v(?:0\.(\d{3})|(\d{3}))(?![0-9])")
SELF = os.path.join("tools", "prune-build.py")
# References from these count only with --include-archive (history, not live).
# Entries ending in "/" are directory prefixes.
ARCHIVE_TIER = ("docs/archive/", "PLAN.md")


def is_archive_tier(path):
    p = os.path.normpath(path).replace(os.sep, "/")
    return any(p.startswith(a) if a.endswith("/") else p == a for a in ARCHIVE_TIER)


def name_version(name):
    vs = [(0, int(a or b)) for a, b in VER_RE.findall(name)]
    return max(vs) if vs else None


def gb(n):
    return n / 1e9


def tree_size(path):
    """Disk usage in bytes. Never follows symlinks."""
    total = 0
    stack = [path]
    while stack:
        p = stack.pop()
        try:
            with os.scandir(p) as it:
                for e in it:
                    try:
                        st = e.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    total += st.st_blocks * 512
                    if e.is_dir(follow_symlinks=False):
                        stack.append(e.path)
        except OSError:
            pass
    return total


def name_date(name):
    for m in DATE_RE.finditer(name):
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue
    return None


def has_date_stamp(name):
    return DATE_RE.search(name) is not None


def source_files(include_archive):
    out = []

    def add_glob(d, exts, recursive):
        if not os.path.isdir(d):
            return
        if recursive:
            for root, dirs, files in os.walk(d, followlinks=False):
                if not include_archive and os.path.normpath(root).startswith(os.path.join("docs", "archive")):
                    dirs[:] = []
                    continue
                dirs.sort()
                for f in sorted(files):
                    if exts is None or f.endswith(exts):
                        out.append(os.path.join(root, f))
        else:
            for f in sorted(os.listdir(d)):
                p = os.path.join(d, f)
                if os.path.isfile(p) and (exts is None or f.endswith(exts)):
                    out.append(p)

    # NEXT-SESSION.md first so it is the credited reference when it applies.
    if os.path.isfile("NEXT-SESSION.md"):
        out.append("NEXT-SESSION.md")
    for f in sorted(os.listdir(".")):
        if f.endswith(".md") and f != "NEXT-SESSION.md" and os.path.isfile(f):
            out.append(f)
    if os.path.isfile("Makefile"):
        out.append("Makefile")
    add_glob("docs", (".md",), False)
    if include_archive:
        add_glob(os.path.join("docs", "archive"), None, True)
        for a in ARCHIVE_TIER:
            if not a.endswith("/") and os.path.isfile(a) and a not in out:
                out.append(a)
    add_glob("hardware-results", (".json",), False)
    add_glob("dist", (".json",), False)
    add_glob("tests", None, True)
    add_glob("tools", None, True)
    return [p for p in out if os.path.normpath(p) != SELF
            and (include_archive or not is_archive_tier(p))]


def scan_refs(files):
    """Return {referenced build path: first file}."""
    refs = {}
    for path in files:
        try:
            if os.path.islink(path) or os.path.getsize(path) > MAX_TEXT:
                continue
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError:
            continue
        if b"\0" in data[:8192]:
            continue
        for m in REF_RE.finditer(data):
            ref = m.group(0).decode("ascii", "ignore").rstrip("./-")
            ref = os.path.normpath(ref)
            if ref not in refs:
                refs[ref] = path
    return refs


def find_candidates(oldest_kept):
    """Return list of dicts: path, kind, version, date."""
    cands = []
    now = time.time()
    for e in sorted(os.scandir(BUILD), key=lambda x: x.name):
        if e.is_symlink() or not e.is_dir(follow_symlinks=False):
            continue
        m = HW_RE.match(e.name)
        if m:
            cands.append({"path": e.path, "kind": "hw",
                          "version": (int(m.group(1)), int(m.group(2)))})

    def walk(d, depth):
        try:
            entries = sorted(os.scandir(d), key=lambda x: x.name)
        except OSError:
            return
        for e in entries:
            if e.is_symlink() or not e.is_dir(follow_symlinks=False):
                continue
            if depth == 1 and HW_RE.match(e.name):
                continue
            if depth == 1 and oldest_kept is not None:
                v = name_version(e.name)
                if v is not None and v < oldest_kept:
                    cands.append({"path": e.path, "kind": "versioned", "version": v})
                    continue
            if has_date_stamp(e.name):
                d0 = name_date(e.name)
                if d0 is not None:
                    age = (dt.date.today() - d0).days
                else:
                    age = (now - e.stat(follow_symlinks=False).st_mtime) / 86400
                cands.append({"path": e.path, "kind": "dated", "age": age})
            elif depth < MAX_DEPTH:
                walk(e.path, depth + 1)

    walk(BUILD, 1)
    return cands


def main():
    head, _, rest = __doc__.partition("\n")
    ap = argparse.ArgumentParser(description=head, epilog=rest,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="delete (default: dry run)")
    ap.add_argument("--keep", type=int, default=10, help="newest hardware-v versions to keep")
    ap.add_argument("--days", type=int, default=14, help="dated dir age threshold")
    ap.add_argument("--include-archive", action="store_true",
                    help="count docs/archive/** as references")
    ap.add_argument("--verbose", action="store_true", help="list every candidate")
    args = ap.parse_args()

    if os.path.realpath(os.getcwd()) != REPO:
        print(f"refusing: run from repo root ({REPO})", file=sys.stderr)
        return 0
    if os.path.islink(BUILD) or not os.path.isdir(BUILD):
        print("refusing: build/ missing or a symlink", file=sys.stderr)
        return 0
    build_real = os.path.realpath(BUILD)

    t0 = time.time()
    files = source_files(args.include_archive)
    refs = scan_refs(files)
    hw_versions = sorted({(int(m.group(1)), int(m.group(2)))
                          for n in os.listdir(BUILD)
                          for m in [HW_RE.match(n)]
                          if m and not os.path.islink(os.path.join(BUILD, n))},
                         reverse=True)
    recent = set(hw_versions[:max(args.keep, 0)])
    oldest_kept = min(recent) if recent else None
    cands = find_candidates(oldest_kept)
    by_path = {os.path.normpath(c["path"]): c for c in cands}

    # Mark referenced candidates: walk each ref's prefixes.
    for ref, src in refs.items():
        parts = ref.split("/")
        for i in range(2, len(parts) + 1):
            c = by_path.get("/".join(parts[:i]))
            if c is not None and "ref" not in c:
                c["ref"] = src

    for c in cands:
        if c["kind"] == "hw" and c["version"] in recent:
            c["cat"] = "kept-recent"
        elif "ref" in c:
            c["cat"] = "kept-referenced"
        elif c["kind"] == "dated" and c["age"] <= args.days:
            c["cat"] = "kept-young"
        else:
            c["cat"] = "delete"

    with ThreadPoolExecutor(max_workers=8) as ex:
        for c, size in zip(cands, ex.map(lambda c: tree_size(c["path"]), cands)):
            c["size"] = size

    order = ["kept-recent", "kept-referenced", "kept-young", "delete"]
    mode = "APPLY" if args.apply else "DRY RUN"
    arch = "with docs/archive" if args.include_archive else "without docs/archive"
    print(f"prune-build {mode} ({arch}); keep={args.keep} days={args.days}; "
          f"oldest kept hw v{oldest_kept[0] if oldest_kept else 0}.{oldest_kept[1] if oldest_kept else 0:03d}; "
          f"{len(files)} sources, {len(refs)} build refs, {time.time() - t0:.1f}s")
    for cat in order:
        sel = [c for c in cands if c["cat"] == cat]
        n = {k: sum(1 for c in sel if c["kind"] == k) for k in ("hw", "versioned", "dated")}
        print(f"  {cat:16s} {len(sel):5d} dirs (hw {n['hw']:3d}, versioned {n['versioned']:4d}, "
              f"dated {n['dated']:4d}) {gb(sum(c['size'] for c in sel)):8.2f} GB")

    prot = {}
    for c in cands:
        if c["cat"] == "kept-referenced":
            prot.setdefault(c["ref"], [0, 0])
            prot[c["ref"]][0] += c["size"]
            prot[c["ref"]][1] += 1
    if prot:
        print("  top referencing files (GB protected, dirs):")
        for src, (size, n) in sorted(prot.items(), key=lambda kv: -kv[1][0])[:5]:
            print(f"    {gb(size):7.2f} GB {n:4d}  {src}")

    rows = sorted(cands, key=lambda c: (order.index(c["cat"]), -c["size"]))
    cap = None if args.verbose else LIST_CAP
    print("  entries:" + ("" if args.verbose else f" (first {LIST_CAP}; --verbose for all)"))
    for c in rows[:cap]:
        extra = f"  <- {c['ref']}" if c["cat"] == "kept-referenced" else ""
        print(f"    {c['cat']:16s} {gb(c['size']):7.2f} GB  {c['path']}{extra}")

    if args.apply:
        freed = 0
        for c in cands:
            if c["cat"] != "delete":
                continue
            p = c["path"]
            real = os.path.realpath(p)
            if os.path.islink(p) or not real.startswith(build_real + os.sep):
                print(f"  skip (unsafe path): {p}", file=sys.stderr)
                continue
            try:
                shutil.rmtree(p)
                freed += c["size"]
            except OSError as exc:
                print(f"  failed: {p}: {exc}", file=sys.stderr)
        print(f"  deleted: {gb(freed):.2f} GB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
