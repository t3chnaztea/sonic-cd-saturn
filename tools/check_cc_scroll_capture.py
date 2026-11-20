#!/usr/bin/env python3
"""Verify original CC1 scroll captures and resolve the Bad Future fraction seed.

Research evidence, not a claim that native backgrounds match the original.
The PC reconstruction leaves lD3.w.h undefined in SCR31D.C. Original 68000
code retains the upper half of sign-extended horizontal camera motion * 8:
subsequent byte/word writes to D3 preserve it until the interpolation swaps.
"""
import hashlib
import json
import re
import struct
from pathlib import Path

from convert_assets import ROOT
from extract_mmd import disc_files
from zone_object_source import dependencies


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    folder = ROOT/'build/cc1/scroll-retail'
    disc = disc_files((ROOT/'build/retail/sonic.iso').read_bytes())
    counts = {}
    input_hashes = {}
    for era in 'ABCD':
        base = folder/('R31'+era)
        report = json.loads((base/'report.json').read_text())
        assert report['program_sha256'] == sha(disc[f'R31{era}__.MMD'])
        assert report['tool_sha256'] == sha((ROOT/'tools/capture_cc_scroll.py').read_bytes())
        assert report['dependencies'] == dependencies()
        path = ROOT/f'.deps/soniccd/src/R3/SCR31{era}.C'
        source = re.sub(r'/\*.*?\*/', '', path.read_text(), flags=re.S)
        match = re.search(r'int LineSpdTbl\[\d+\] = \{(.*?)\};', source, re.S)
        speeds = [int(v) for v in re.findall(r'\d+', match[1])]
        speeds += [32768+(i << (10 if era == 'A' else 8)) for i in range(64)]
        comparisons = 0
        directions = set()
        zero_seed_misses = 0
        for sample in report['samples']:
            index = sample['index']
            before = (base/f'{index:03}-deform-before.bin').read_bytes()
            after = (base/f'{index:03}-deform-after.bin').read_bytes()
            hscroll = (base/f'{index:03}-hscroll.bin').read_bytes()
            assert sha(before) == sample['before_sha256']
            assert sha(after) == sample['after_sha256']
            assert sha(hscroll) == sample['scroll_sha256']
            n = len(speeds)
            old = struct.unpack('>'+str(n)+'I', before[:4*n])
            new = struct.unpack('>'+str(n)+'I', after[:4*n])
            assert [(b-a)&0xffffffff for a,b in zip(old,new)] == speeds, (era,index,'accumulators')
            comparisons += n
            dx = sample['scroll_x_diff_8_8']
            directions.add((dx>0)-(dx<0))
            if era == 'D':
                cameras = sample['actual_16_16']
                x, b = [cameras[key] >> 16 for key in ('cameraX','cameraBgX')]
                delta = int((x-b)*64/24)*1024
                seed = 65535 if dx < 0 else 0
                values = [-(b+((seed+i*delta)>>16)) for i in range(3)]
                expected = [values[0]]+[values[1]]*2+[values[2]]*7
                rows = list(struct.unpack('>10h', after[316+78*2:316+88*2]))
                assert rows == expected, (era,index,dx,rows,expected)
                comparisons += 10
                zero = [-b]+[-(b+(delta>>16))]*2+[-(b+(2*delta>>16))]*7
                zero_seed_misses += rows != zero
        assert directions == {-1,0,1}, (era,directions)
        if era == 'D':
            assert zero_seed_misses > 0, 'fixtures must distinguish the retained fraction from zero'
        counts[era] = dict(fixtures=len(report['samples']), compared_values=comparisons,
                           max_waited_vblanks=max(s['waited_vblanks'] for s in report['samples']),
                           zero_seed_mismatches=zero_seed_misses)
        input_hashes[str(path.relative_to(ROOT))] = sha(path.read_bytes())
        input_hashes[str((base/'report.json').relative_to(ROOT))] = sha((base/'report.json').read_bytes())
    # Preserve the exact original instructions that explain the undefined
    # reconstructed half-word; each byte sequence must be unique in R31D.
    sequences = {
        'sign-extended camera delta to D3 (times eight)': '3838f73a48c4e5842604d683d8837c02',
        'scrollb_h only overwrites the low byte of D3': '2438f7082002d08421c0f70822004841024100101638f74cb70166160a380010f74c90826a060df8f756600652060df8f7564e75',
        'scrollb_v only overwrites the low word of D3': '3638f70c31c0f70c3200024100101438f74db50166180a380010f74d90436a0808f80000f7564e7508f80001f7564e75',
        'interpolation preserves D3 high word': '3038f7083438f700944048c27206e3a285fc001848c2720ae3a27c023638f7083003444047f900202bd27a001a33600032c051cdfffc4843d682484351ceffe2',
    }
    program = disc['R31D__.MMD']
    evidence = {}
    for label, encoded in sequences.items():
        code = bytes.fromhex(encoded)
        assert program.count(code) == 1, label
        evidence[label] = dict(address=0x200000+program.index(code), bytes=encoded)
    result = dict(passed=True, programs=counts, instructions=evidence, inputs=input_hashes,
                  tool_sha256=sha(Path(__file__).read_bytes()),
                  limits='Original CPU accumulator and Bad Future interpolation fixtures only. No native raster, tilemap, scene-phase or gameplay acceptance.')
    (folder/'checked.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(counts,indent=2))


if __name__ == '__main__':
    main()
