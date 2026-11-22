#!/usr/bin/env python3
"""Copy generated stage data into cd/ as the packs listed in src/stage_packs.h.

The Saturn build reads each pack from the CD root into its own low work RAM
region at boot. Regions must not overlap and each file, rounded up to whole
2,048-byte sectors, must fit its capacity. build/stage-packs.json records the
files and regions for dist/build-report.json (tools/package.py).
"""
import hashlib,json,re
from pathlib import Path
from generated_io import write_bytes, write_text
ROOT=Path(__file__).resolve().parents[1]
LOW,END=0x00200000,0x00300000
# The zone rows live in the header tools/install_zone_packs.py generates, which
# src/stage_packs.h includes; scan both so one regex pass sees every row.
text=(ROOT/'src/stage_packs.h').read_text()+(ROOT/'src/stage_zone_packs.h').read_text()+(ROOT/'assets/generated/zone-object-packs.h').read_text()+(ROOT/'assets/generated/title-card-names.h').read_text()
table=re.findall(r'STAGE_PACK\((\w+),"([A-Z0-9_]{1,8}\.BIN)",(0x[0-9A-Fa-f]+),(0x[0-9A-Fa-f]+),"([^"]+)"\)',text)
assert table,'no STAGE_PACK entries in src/stage_packs.h'
packs=[];region_end=LOW
for ident,name,address,capacity,source in table:
    address,capacity=int(address,16),int(capacity,16);data=(ROOT/source).read_bytes()
    sectors=-(-len(data)//2048)
    assert address>=region_end and address+capacity<=END,(name,'region overlaps or leaves low work RAM')
    assert data and sectors*2048<=capacity,(name,len(data),capacity)
    (ROOT/'cd').mkdir(exist_ok=True);write_bytes(ROOT/'cd'/name,data)
    region_end=address+capacity
    packs.append({'id':ident,'file':name,'source':source,'bytes':len(data),'sectors':sectors,'address':f'0x{address:08X}','capacity':capacity,'sha256':hashlib.sha256(data).hexdigest()})
capacities={p['id']:p['capacity'] for p in packs};act_packs=[]
for ident,act,name,source in re.findall(r'STAGE_ACT_PACK\((\w+),(\d+),"([A-Z0-9_]{1,8}\.BIN)","([^"]+)"\)',text):
    data=(ROOT/source).read_bytes();sectors=-(-len(data)//2048)
    assert ident in capacities and data and sectors*2048<=capacities[ident],(name,len(data))
    write_bytes(ROOT/'cd'/name,data)
    act_packs.append({'id':ident,'act':int(act),'file':name,'source':source,'bytes':len(data),'sectors':sectors,'sha256':hashlib.sha256(data).hexdigest()})
zone_packs=[]
for ident,zone,act,name,source in re.findall(r'STAGE_ZONE_PACK\((\w+),(\d+),(\d+),"([A-Z0-9_]{1,8}\.BIN)","([^"]+)"\)',text):
    data=(ROOT/source).read_bytes();sectors=-(-len(data)//2048)
    assert ident in capacities and data and sectors*2048<=capacities[ident],(name,len(data),capacities.get(ident))
    write_bytes(ROOT/'cd'/name,data)
    zone_packs.append({'id':ident,'zone':int(zone),'act':int(act),'file':name,'source':source,'bytes':len(data),'sectors':sectors,'sha256':hashlib.sha256(data).hexdigest()})
report={'region':'low work RAM 0x00200000-0x002FFFFF','packs':packs,'act_packs':act_packs,'zone_packs':zone_packs,'loaded_bytes':sum(p['bytes'] for p in packs),'peak_region_bytes':region_end-LOW}
(ROOT/'build').mkdir(exist_ok=True);write_text(ROOT/'build/stage-packs.json',json.dumps(report,indent=2)+'\n')
print(f"{len(zone_packs)} zone packs; {len(packs)} stage packs, {report['loaded_bytes']} bytes, low work RAM through 0x{region_end:08X}")
