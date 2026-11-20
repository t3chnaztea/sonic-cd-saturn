#!/usr/bin/env python3
"""Word LZ codec for zone object art (ZAR3 era arenas, src/zone_object_view.inc).

Big-endian u16 tokens over big-endian u16 words:
  0x0000|n  (n 1..16383)  repeat the next word n times
  0x4000|n  (n 1..16383)  n literal words follow
  0x8000|n  (n 1..32767)  then u16 d: copy n words starting d words back
                          (d >= 1; overlapping copies repeat, as in LZ77);
                          d == 0 keeps the n words already at the destination
                          (a bank packed against a resident base, pack(base=))
Composited poses repeat whole piece rows at other offsets; back references
store them once.
"""
import struct

MIN_MATCH = 3


def pack(data, base=None):
    assert len(data) % 2 == 0
    w = [v for v, in struct.iter_unpack('>H', data)]
    b = [v for v, in struct.iter_unpack('>H', base)] if base is not None else []
    n = len(w); out = bytearray(); lits = []; i = 0
    heads = {}

    def flush():
        while lits:
            chunk = lits[:16383]; del lits[:16383]
            out.extend(struct.pack('>H', 0x4000 | len(chunk))); out.extend(struct.pack(f'>{len(chunk)}H', *chunk))

    def insert(k):
        if k+MIN_MATCH <= n:heads.setdefault(tuple(w[k:k+MIN_MATCH]), []).append(k)

    while i < n:
        keep = 0
        while i+keep < min(n, len(b)) and w[i+keep] == b[i+keep] and keep < 32767:keep += 1
        if keep >= 2:
            flush(); out.extend(struct.pack('>HH', 0x8000 | keep, 0))
            for k in range(i, i+keep):insert(k)
            i += keep; continue
        run = 1
        while i+run < n and w[i+run] == w[i] and run < 16383:run += 1
        best, dist = 0, 0
        if i+MIN_MATCH <= n:
            for j in reversed(heads.get(tuple(w[i:i+MIN_MATCH]), [])[-64:]):
                if i-j > 65535:break
                length = 0
                while i+length < n and w[j+length] == w[i+length] and length < 32767:length += 1
                if length > best:best, dist = length, i-j
        if run >= 3 and run >= best:
            flush(); out.extend(struct.pack('>HH', run, w[i]))
            for k in range(i, i+run):insert(k)
            i += run
        elif best >= MIN_MATCH:
            flush(); out.extend(struct.pack('>HH', 0x8000 | best, dist))
            for k in range(i, i+best):insert(k)
            i += best
        else:
            lits.append(w[i]); insert(i); i += 1
    flush()
    return bytes(out)


def unpack(data, words, base=None):
    out = []; r = 0
    b = [v for v, in struct.iter_unpack('>H', base)] if base is not None else []
    while r < len(data):
        code, = struct.unpack_from('>H', data, r); r += 2
        if code & 0x8000:
            d, = struct.unpack_from('>H', data, r); r += 2
            if d == 0:
                k = code & 0x7fff; assert len(out)+k <= len(b); out.extend(b[len(out):len(out)+k]); continue
            assert 1 <= d <= len(out)
            for _ in range(code & 0x7fff):out.append(out[-d])
        elif code & 0x4000:
            k = code & 0x3fff; out.extend(struct.unpack_from(f'>{k}H', data, r)); r += 2*k
        else:
            v, = struct.unpack_from('>H', data, r); r += 2; out.extend([v]*code)
    assert len(out) == words
    return struct.pack(f'>{words}H', *out)


def bank_raw(pack, index):
    """Raw words of R83's fight (entry 0) or Amy (entry 1) bank. The Amy bank is
    packed over the fight bank (tools/zone_object_assets.py pack_era base)."""
    at, = struct.unpack_from('>I', pack, 4+index*4)
    count, raw_size, packed_size = struct.unpack_from('>III', pack, at)
    packed_at = at+12+48*count
    base = bank_raw(pack, 0) if index == 1 else None
    return unpack(pack[packed_at:packed_at+packed_size], raw_size//2, base)
