#!/usr/bin/env python3
"""Saturn route shots beside the retail frames of the same level update.

Diagnostic for visual parity (not a pass gate, not a hardware result). A
Saturn route run (tools/test_cc2_route.py, test_cc3_route.py or
test_qq_route.py) leaves cc-route-NNNNN.ppm every 600 route updates in
build/<zone><act>/controller/<era>/; route update N is native sequence N + 1.
This tool picks --count of those shots, plays the window's script.txt in the
retail act program (tools/retail_probe.py --native-unlock, PREFIX_SHOT_SEQS)
and writes build/frame-compare/<zone><act><era>.png: one row per shot,
Saturn, retail, then a
difference map (retail dimmed, differing pixels red). The unlock comes from the cached retail parity key
when its script hash matches, else from the route host's trace.

usage: route_frame_compare.py ZONE ACT ERA [--count 6]   (ZONE cc|qq|ww|ss)
"""
import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUND = {'cc': 3, 'qq': 5, 'ww': 6, 'ss': 7}


def host_argv(zone, act, era, script, rows):
    base = ROOT / f'build/{zone}{act}/controller'
    if zone == 'cc' and act == 3:
        return [base/'host', 'replay', script, era, '20000', rows], 'CC_ROUTE'
    if zone == 'cc':
        return [base/'cc_campaign_search', 'replay', f'{act-1}:{era}', script, '40000', rows], 'CC_ROUTE'
    return [base/'qq_route_search', 'replay', f'{act-1}:{era}', script, '46000', rows], 'QQ_ROUTE'


def unlock_for(zone, act, era, out, script):
    key = out / 'retail.key'
    if key.exists():
        k = json.loads(key.read_text())
        if k.get('script') == hashlib.sha256(script.read_bytes()).hexdigest():
            return k['unlock']
    argv, prefix = host_argv(zone, act, era, script, out / 'frame-compare-trace.rows')
    trace = subprocess.run(argv, cwd=ROOT, env=dict(os.environ, **{prefix + '_TRACE': '1'}), capture_output=True, text=True)
    return int(re.search(r'unlock (\d+)', trace.stderr)[1])


def read_ppm(path):
    data = path.read_bytes()
    _, w, h, _, body = data.split(maxsplit=4)
    return int(w), int(h), body


def read_png(path):
    """RGB PNG with filter 0 rows (special_retail.png's own output)."""
    data, at, idat, w, h = path.read_bytes(), 8, b'', 0, 0
    while at < len(data):
        n, kind = struct.unpack_from('>I4s', data, at)
        body = data[at+8:at+8+n]
        if kind == b'IHDR':
            w, h = struct.unpack_from('>II', body)
        elif kind == b'IDAT':
            idat += body
        at += 12 + n
    raw = zlib.decompress(idat)
    assert all(raw[y*(w*3+1)] == 0 for y in range(h)), 'unexpected PNG filter'
    return w, h, b''.join(raw[y*(w*3+1)+1:(y+1)*(w*3+1)] for y in range(h))


def write_png(path, w, h, rgb):
    rows = b''.join(b'\0' + rgb[y*w*3:(y+1)*w*3] for y in range(h))
    chunk = lambda kind, body: struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) +
                     chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


def far(a, b, i, j):
    return max(abs(a[2][i+c] - b[2][j+c]) for c in range(3)) > 64


def align(a, b):
    """Crop the Saturn frame (330 wide on the core) to the retail frame at the
    offset with the fewest differing samples (5, 0 in practice)."""
    w, h = b[0], b[1]
    score = lambda dx, dy: sum(far(a, b, ((y+dy)*a[0]+x+dx)*3, (y*b[0]+x)*3)
                               for y in range(16, h-16, 6) for x in range(16, w-16, 6))
    dx, dy = min(((dx, dy) for dx in range(0, a[0]-w+4) for dy in range(-2, 3)), key=lambda d: score(*d))
    rgb = b''.join(bytes(a[2][((y+dy)*a[0]+dx)*3:((y+dy)*a[0]+dx+w)*3]) if 0 <= y+dy < a[1] else bytes(w*3)
                   for y in range(h))
    return w, h, rgb


def diff(a, b):
    """Retail dimmed, with pixels that differ by more than 64 in a channel in red."""
    w, h = min(a[0], b[0]), min(a[1], b[1])
    out = bytearray(w * h * 3)
    for y in range(h):
        for x in range(w):
            i, j, k = (y*a[0]+x)*3, (y*b[0]+x)*3, (y*w+x)*3
            if far(a, b, i, j):
                out[k:k+3] = b'\xff\x00\x00'
            else:
                out[k:k+3] = bytes(v // 3 for v in b[2][j:j+3])
    return w, h, bytes(out)


def compose(pairs, path):
    cell_w = max(c[0] for row in pairs for c in row)
    cell_h = max(c[1] for row in pairs for c in row)
    W, H, gap = cell_w * 3 + 8, (cell_h + 4) * len(pairs), 4
    out = bytearray(b'\x40' * (W * H * 3))
    for i, row in enumerate(pairs):
        for j, (w, h, rgb) in enumerate(row):
            for y in range(h):
                at = ((i * (cell_h + gap) + y) * W + j * (cell_w + gap)) * 3
                out[at:at + w*3] = rgb[y*w*3:(y+1)*w*3]
    write_png(path, W, H, bytes(out))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('zone', choices=sorted(ROUND))
    parser.add_argument('act', type=int)
    parser.add_argument('era')
    parser.add_argument('--count', type=int, default=6)
    args = parser.parse_args()
    out = ROOT / f'build/{args.zone}{args.act}/controller/{args.era}'
    script = out / 'script.txt'
    shots = sorted(int(p.stem[9:]) for p in out.glob('cc-route-[0-9]*.ppm'))
    assert shots, f'no Saturn route shots in {out}'
    n = min(args.count, len(shots))
    pick = sorted({shots[round(i * (len(shots) - 1) / max(n - 1, 1))] for i in range(n)})
    seqs = [s + 1 for s in pick]
    unlock = unlock_for(args.zone, args.act, args.era, out, script)
    dest = ROOT / 'build/frame-compare' / f'{args.zone}{args.act}{args.era}'
    dest.mkdir(parents=True, exist_ok=True)
    rows = dest / 'retail.rows'
    with (dest / 'retail.log').open('w') as log:
        subprocess.run([sys.executable, 'tools/retail_probe.py', str(args.act), args.era, str(script), str(rows),
                        str(max(seqs) + 400), '--native-unlock', str(unlock), '--round', str(ROUND[args.zone])],
                       cwd=ROOT, env=dict(os.environ, TT_PROBE_SHOT_SEQS=','.join(map(str, seqs)) + ':' + str(dest)),
                       stdout=log, stderr=log, check=True, timeout=14400)
    pairs, missing, counts = [], [], []
    for p, s in zip(pick, seqs):
        retail = dest / f'seq-{s}.png'
        if not retail.exists():
            missing.append(s)
            continue
        b = read_png(retail)
        a = align(read_ppm(out / f'cc-route-{p:05d}.ppm'), b)
        d = diff(a, b)
        counts.append(d[2].count(b'\xff\x00\x00'))
        pairs.append((a, b, d))
    sheet = ROOT / 'build/frame-compare' / f'{args.zone}{args.act}{args.era}.png'
    if pairs:
        compose(pairs, sheet)
    print(f'{args.zone.upper()}{args.act}{args.era}: unlock {unlock}, seqs {seqs}, differing pixels {counts}, sheet {sheet}'
          + (f', no retail frame for {missing} (retail act ended first)' if missing else ''))
    return 0 if pairs else 1


if __name__ == '__main__':
    sys.exit(main())
