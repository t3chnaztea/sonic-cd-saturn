#!/usr/bin/env python3
"""Build an scddisasm-layout data tree from the user's retail disc.

  python3 tools/retail_src.py locate    # needs .deps/scddisasm (reference only)
  python3 tools/retail_src.py build     # disc only -> build/retail-src
  python3 tools/retail_src.py verify    # build/retail-src vs .deps/scddisasm
  python3 tools/retail_src.py mixed     # disc files + links for the rest

`locate` takes each binary data file in tools/scddisasm-manifest.json, finds
its bytes inside a file on build/retail/sonic.iso, and records
{disc file, offset, length, sha256} in tools/scddisasm-retail-map.json.
A file whose zero tail is not on the disc (scddisasm pads some collision
indexes) records the located prefix length and the zero pad length.

`build` reads only the disc and the committed map. It slices each entry,
checks its sha256, and writes it at the same relative path under
build/retail-src. A tool run with SCD_DATA_ROOT=build/retail-src then reads
disc bytes instead of downloaded ones. Files that are not mapped yet are
absent, so a tool that still needs one fails loudly.

The map holds offsets and hashes only, no disc bytes.
"""
import hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from extract_mmd import disc_files, ISO

SCD = ROOT / '.deps/scddisasm'
MANIFEST = ROOT / 'tools/scddisasm-manifest.json'
MAP = ROOT / 'tools/scddisasm-retail-map.json'
OUT = ROOT / 'build/retail-src'
MIXED = ROOT / 'build/retail-src-mixed'
BINARY = ('.bin', '.nem', '.kos', '.kosm', '.pal', '.map', '.eni', '.cmp', '.dat', '.pcm', '.raw', '.unc')


def sha(b):
    return hashlib.sha256(b).hexdigest()


def disc():
    return disc_files(ISO.read_bytes())


def locate():
    files = json.loads(MANIFEST.read_text())['files']
    discs = disc()
    order = sorted(discs, key=lambda n: (not n.endswith('.MMD'), n))
    entries, missing, skipped = {}, [], []
    for path, info in files.items():
        if not path.lower().endswith(BINARY):
            skipped.append(path)
            continue
        blob = (SCD / path).read_bytes()
        assert sha(blob) == info['sha256'], f'{path}: scddisasm changed since the manifest'
        body = blob
        pad = 0
        hit = None
        for attempt in (blob, blob.rstrip(b'\0')):
            if not attempt:
                continue
            for name in order:
                i = discs[name].find(attempt)
                if i >= 0:
                    hit = name, i
                    body = attempt
                    pad = len(blob) - len(attempt)
                    break
            if hit:
                break
        if not hit:
            missing.append(path)
            continue
        entries[path] = {'disc': hit[0], 'offset': hit[1], 'length': len(body), 'zero_pad': pad,
                         'sha256': info['sha256']}
    binary = len(files) - len(skipped)
    MAP.write_text(json.dumps({
        'about': 'Where each scddisasm data file the build reads lies on the retail disc (build/retail/sonic.iso). '
                 'Written by tools/retail_src.py locate. Offsets and hashes only.',
        'iso_sha256': sha(ISO.read_bytes()),
        'coverage': {'manifest_files': len(files), 'binary': binary, 'located': len(entries),
                     'binary_not_located': len(missing), 'non_binary': len(skipped)},
        'not_located': missing, 'non_binary': skipped, 'files': entries}, indent=1) + '\n')
    print(f'located {len(entries)}/{binary} binary files ({len(skipped)} non-binary skipped) -> {MAP.relative_to(ROOT)}')


def build(out=OUT):
    data = json.loads(MAP.read_text())
    discs = disc()
    written = 0
    for path, e in data['files'].items():
        blob = discs[e['disc']][e['offset']:e['offset'] + e['length']] + bytes(e['zero_pad'])
        if sha(blob) != e['sha256']:
            raise SystemExit(f'{path}: disc slice does not match the recorded sha256 (different disc?)')
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.read_bytes() != blob:
            target.write_bytes(blob)
        written += 1
    print(f'{written} files from the disc -> {out.relative_to(ROOT)}')
    return data


def build_mixed(out=MIXED):
    """Disc files plus symlinks to scddisasm for every manifest file not yet
    mapped. Running a tool on this tree under tools/scddisasm_audit.py shows
    exactly which scddisasm files it still needs."""
    data = build(out)
    links = 0
    for path in json.loads(MANIFEST.read_text())['files']:
        if path in data['files']:
            continue
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_symlink():
            target.symlink_to(SCD / path)
        links += 1
    print(f'{links} files still linked to .deps/scddisasm')


def verify(out=OUT):
    data = json.loads(MAP.read_text())
    bad = [p for p in data['files'] if (out / p).read_bytes() != (SCD / p).read_bytes()]
    print(f'{len(data["files"]) - len(bad)}/{len(data["files"])} shadow files byte-identical to scddisasm')
    if bad:
        raise SystemExit(f'differ: {bad}')


if __name__ == '__main__':
    cmd = sys.argv[1:] or ['build']
    {'locate': locate, 'build': build, 'mixed': build_mixed, 'verify': verify}[cmd[0]]()
