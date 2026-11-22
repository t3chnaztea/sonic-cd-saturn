"""Bind diagnostic builds to candidates while excluding only ISO-9660 dates.

Yaul uses --norock and ISO level 1. Reject other volume descriptor types.
All boot bytes, file data, directory names/extents/order and padding stay in
the canonical hash. Only the standard volume and directory date fields differ.
"""
import hashlib
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def normalized_iso_sha256(data):
    assert len(data) % 2048 == 0, 'unaligned ISO'
    normalized = bytearray(data)
    roots = []
    for sector in range(16, len(data) // 2048):
        start = sector * 2048
        descriptor = data[start:start + 2048]
        assert descriptor[1:7] == b'CD001\x01', 'unsupported ISO descriptor'
        kind = descriptor[0]
        if kind == 255:
            break
        assert kind == 1 and not roots, 'expected one primary ISO descriptor, no extensions'
        normalized[start + 813:start + 881] = bytes(68)
        root = start + 156
        assert data[root] == 34, 'unexpected root record'
        normalized[root + 18:root + 25] = bytes(7)
        roots.append((int.from_bytes(data[root + 2:root + 6], 'little'),
                      int.from_bytes(data[root + 10:root + 14], 'little')))
    else:
        raise AssertionError('missing volume terminator')
    assert len(roots) == 1, 'missing primary descriptor'
    visited = set()
    while roots:
        lba, size = roots.pop()
        if (lba, size) in visited:
            continue
        visited.add((lba, size))
        start, end = lba * 2048, lba * 2048 + size
        assert start >= 18 * 2048 and end <= len(data), 'directory outside ISO'
        offset = start
        while offset < end:
            length = data[offset]
            if not length:
                offset = (offset // 2048 + 1) * 2048
                continue
            assert length >= 34 and offset + length <= end, 'invalid directory record'
            assert offset // 2048 == (offset + length - 1) // 2048, 'record crosses sector'
            record = data[offset:offset + length]
            assert 33 + record[32] <= length, 'invalid file identifier'
            normalized[offset + 18:offset + 25] = bytes(7)
            name = record[33:33 + record[32]]
            if record[25] & 2 and name not in (b'\0', b'\1'):
                roots.append((int.from_bytes(record[2:6], 'little'),
                              int.from_bytes(record[10:14], 'little')))
            offset += length
    return sha(normalized)


def capture(root):
    root = Path(root)
    name = 'sonic-cd-saturn-prototype'
    iso = (root / f'dist/iso/{name}.iso').read_bytes()
    binary = root / f'dist/{name}.bin'
    sectors = len(iso) // 2048
    audio = hashlib.sha256()
    with binary.open('rb') as stream:
        for sector in range(sectors):
            raw = stream.read(2352)
            assert len(raw) == 2352 and raw[16:2064] == iso[sector * 2048:(sector + 1) * 2048], 'BIN/ISO mismatch'
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            audio.update(chunk)
    return dict(format=1, normalized_iso_sha256=normalized_iso_sha256(iso),
                iso_bytes=len(iso), raw_bytes=binary.stat().st_size,
                audio_tail_sha256=audio.hexdigest(),
                cue_sha256=sha((root / f'dist/{name}.cue').read_bytes()),
                program_sha256=sha((root / f'build/saturn/{name}.bin').read_bytes()))
