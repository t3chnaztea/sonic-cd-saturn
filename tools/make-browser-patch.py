#!/usr/bin/env python3
"""Create a PRIVATE local SCSP bundle from owned JP tracks and an accepted BIN.

Never distribute the result. Literal ranges include converted game data.
No game build is run. The supplied accepted BIN and CUE are read only.
"""
import argparse
import hashlib
import json
import mmap
import os
from pathlib import Path
import re
import struct
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SECTOR = 2352


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def make(cue, target, target_cue, out):
    cue = cue.resolve(strict=True)
    out = out.resolve()
    if not out.is_relative_to(ROOT / 'build'):
        raise ValueError('Private bundles must stay under the ignored build directory')
    if out.exists():
        raise ValueError('Output already exists; choose a new private bundle path')
    names = re.findall(r'^\s*FILE "([^"\r\n]+)" BINARY\s*$', cue.read_text(encoding='utf-8-sig'), re.M)
    if not names or len(set(names)) != len(names) or any('/' in n or '\\' in n or n in ('.', '..') for n in names):
        raise ValueError('Expected a split Japanese BINARY CUE with unique local filenames')
    paths = [cue.parent / n for n in names]
    handles, maps, index = [], [], {}
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        for i, path in enumerate(paths):
            f = path.open('rb'); handles.append(f)
            data = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ); maps.append(data)
            if len(data) % SECTOR:
                raise ValueError('Source BIN is not sector aligned')
            for offset in range(0, len(data), SECTOR):
                sector = data[offset:offset + SECTOR]
                if sector == bytes(SECTOR):
                    continue
                index.setdefault(hashlib.sha256(sector).digest(), (i, offset))
        ops = []
        def add(kind, offset, length, source=None):
            if ops and ops[-1]['kind'] == kind and ops[-1].get('index') == source and ops[-1]['offset'] + ops[-1]['length'] == offset:
                ops[-1]['length'] += length
            else:
                row = dict(kind=kind, offset=offset, length=length)
                if source is not None: row['index'] = source
                ops.append(row)
        with target.open('rb') as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as data, tempfile.TemporaryFile(dir=out.parent) as literals:
            for offset in range(0, len(data), SECTOR):
                sector = data[offset:offset + SECTOR]
                match = None
                if ops and ops[-1]['kind'] == 'source':
                    prev = ops[-1]; pos = prev['offset'] + prev['length']
                    if maps[prev['index']][pos:pos + len(sector)] == sector:
                        match = prev['index'], pos
                if match is None: match = index.get(hashlib.sha256(sector).digest())
                if match is not None and maps[match[0]][match[1]:match[1] + len(sector)] == sector:
                    add('source', match[1], len(sector), match[0])
                else:
                    pos = literals.tell(); literals.write(sector); add('literal', pos, len(sector))
            used = sorted({row['index'] for row in ops if row['kind'] == 'source'})
            remap = {old: new for new, old in enumerate(used)}
            for row in ops:
                if row['kind'] == 'source': row['index'] = remap[row['index']]
            metadata = dict(format=1, version='V0.082', private=True,
                sources=[dict(name=paths[i].name, bytes=paths[i].stat().st_size, sha256=sha(paths[i])) for i in used],
                target=dict(bytes=len(data), sha256=sha(target), cue=target_cue.read_text(), cue_sha256=sha(target_cue)), ops=ops)
            header = json.dumps(metadata, separators=(',', ':'), ensure_ascii=True).encode()
            if len(header) > 16 * 1024 * 1024: raise ValueError('Patch header exceeds browser limit')
            literal_bytes = literals.tell(); literals.seek(0)
            with out.open('xb') as dest:
                dest.write(b'SCSP082\n' + struct.pack('<I', len(header)) + header)
                while chunk := literals.read(4 * 1024 * 1024): dest.write(chunk)
                dest.flush(); os.fsync(dest.fileno())
        receipt = dict(status='created-private', bundle=out.name, bundle_bytes=out.stat().st_size,
            bundle_sha256=sha(out), source_files=len(used), operations=len(ops),
            literal_bytes=literal_bytes, copied_bytes=target.stat().st_size - literal_bytes,
            target_sha256=metadata['target']['sha256'], public_distribution=False)
        out.with_suffix('.receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt, indent=2))
    finally:
        for data in maps: data.close()
        for handle in handles: handle.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cue', type=Path, default=ROOT / 'assets/private/sonic-cd-japan.cue')
    ap.add_argument('--target', type=Path, default=ROOT / 'dist/sonic-cd-saturn-prototype.bin')
    ap.add_argument('--target-cue', type=Path, default=ROOT / 'dist/sonic-cd-saturn-prototype.cue')
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    make(args.cue, args.target, args.target_cue, args.out)


if __name__ == '__main__': main()
