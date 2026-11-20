#!/usr/bin/env python3
"""Audit a round's placements using each original era's dispatch table.

--round 3 (Collision Chaos, default) writes build/cc<act>/inventory.json;
--round 4 (Tidal Tempest) writes build/tt<act>/inventory.json, and so on.
ported_types lists which translated port types src/objects.c supports now."""
import re
import argparse
import collections
import hashlib
import json
import struct
from pathlib import Path
import object_layouts as L

PREFIX = {3: 'cc', 4: 'tt', 5: 'qq', 6: 'ww', 7: 'ss', 8: 'mm'}


def supported_types():
    """Port types src/objects.c's supported_types table lists."""
    ids = {}
    for m in re.finditer(r'(SCD_OBJ_\w+)\s*=\s*(\d+)', (L.ROOT/'src/scd_objects.h').read_text()):
        ids[m.group(1)] = int(m.group(2))
    body = re.search(r'supported_types\[[^]]*\]\s*=\s*\{(.*?)\};', (L.ROOT/'src/objects.c').read_text(), re.S).group(1)
    ported = {ids[n] for n in re.findall(r'\[(SCD_OBJ_\w+)\]\s*=\s*1', body)}
    # Zone-local types (136-254) are ported when a zone registers ops in
    # src/objects_zone_ops.inc and its <prefix>_type lists them.
    ops = (L.ROOT/'src/objects_zone_ops.inc').read_text()
    for prefix in re.findall(r'&(\w+)_zone_ops', ops):
        path = L.ROOT/f'src/objects_{prefix}.inc'
        m = path.exists() and re.search(rf'static int {prefix}_type\(unsigned t\)\{{(.*?)\n\}}', path.read_text(), re.S)
        if m:ported |= {ids[n] for n in re.findall(r'SCD_OBJ_\w+', m.group(1)) if n in ids}
    return ported


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--round', type=int, choices=sorted(PREFIX), default=3)
    parser.add_argument('--act', type=int, choices=(1, 2, 3), default=1)
    args = parser.parse_args()
    act, rnd = args.act, args.round
    tables, defs = L.act_tables(), L.definitions()
    entries, translation = L.translate(rnd, act, tables, L.port_types(tables), defs)
    records = []
    for x, y, kind, sub, eras, secondary in struct.iter_unpack('>HHBBBB', L.layout_bytes(rnd, act)):
        if x == 65535:
            break
        records.append(dict(x=x, y=y & 4095, flags=y >> 14, retail_id=kind & 127,
                            subtype=sub, eras=eras >> 5, secondary=secondary))
    variants = {}
    inputs = {'tools/object_layouts.py', 'tools/inventory_cc1.py', 'sources.lock.json'}
    for era in L.eras_of(act):
        table = L.table_for(tables, rnd, act, era)
        grouped = collections.defaultdict(list)
        for record in records:
            if record['eras'] & L.ERA_BIT[era]:
                name = L.routine(tables, table, record['retail_id'])
                grouped[name].append(record)
        objects = {}
        for name, rows in sorted(grouped.items()):
            # Some routines (togeball) have separate era implementations. Keep
            # all candidates explicit until original-program dispatch is verified.
            sources = sorted(f for f in defs.get(name, ()) if f.startswith(f'R{rnd}/'))
            if not sources:
                sources = sorted(f for f in defs.get(name, ()) if '/' not in f)
            for source in sources:
                inputs.add('build/audit/source/src/' + source)
            objects[name] = dict(source_candidates=sources, count=len(rows),
                                 subtypes=sorted({r['subtype'] for r in rows}), records=rows)
        inputs.add(f'build/audit/source/src/R{rnd}/' + table + '.C')
        inputs.add(f'build/auto-extract/{rnd}/objects{rnd}{act}{era}.bin')
        variants[era] = dict(table=table, visible_records=sum(v['count'] for v in objects.values()),
                             objects=objects, translated_placements=sum(bool(e[5] & L.ERA_BIT[era]) for e in entries))
    kinds = {e[2] for e in entries}
    ported = supported_types()
    report = dict(round=rnd, act=act, ported_types=sorted(kinds & ported), awaiting_port=sorted(kinds - ported), variants=variants, translation=translation,
                  limits='Placement/import coverage only. Behavior, artwork, routes, animation and backgrounds require separate evidence.',
                  inputs={p: hashlib.sha256((L.ROOT/p).read_bytes()).hexdigest() for p in sorted(inputs)})
    out = L.ROOT/f'build/{PREFIX[rnd]}{act}'; out.mkdir(parents=True, exist_ok=True)
    (out/'inventory.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: {n: v[n] for n in ('visible_records', 'translated_placements')} for k,v in variants.items()}, indent=2))
    print('Unimplemented routines:', ', '.join(translation['dropped_routines']))
    print('Unported round variants:', ', '.join(translation['per_round_clones']))
    print('Port types awaiting a handler:', report['awaiting_port'])


if __name__ == '__main__':
    main()
