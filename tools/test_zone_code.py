#!/usr/bin/env python3
"""Zone code overlays (src/saturn.x) keep their contract (heap plan B).

Host-only. Reads the last Saturn link (build/saturn/*.elf, linked with --emit-relocs):
1. Every symbol inside an overlay section .zone_<Z> carries one of that zone's prefixes
   (ZONE_PREFIXES). LTO can inline, clone or fold code and data: a clone keeps its
   prefix, but an identical-code/data fold can leave a resident name at an overlay
   address, and a resident caller would then reach a zone that is not loaded.
2. Resident sections may reference an overlay function only from a zone_ops table of
   the same zone (a `<prefix>zone_ops` object: src/objects_zone_ops.inc, src/boss_zone.h),
   selected by the loaded zone, or from a zone-private table: a resident object that
   only that zone's overlay refers to (act_tbl arrays, compiler switch tables). Any
   other resident->overlay code reference fails. Resident->overlay data references (the zone tables read in-zone) are listed
   in build/zone-code-refs.txt with their count.
Cross-overlay references are the linker's job (OVERLAY NOCROSSREFS).
"""
import collections,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
READELF=ROOT/'.toolchain/bin/sh-elf-readelf'
ELF=ROOT/'build/saturn/sonic-cd-saturn-prototype.elf'
REPORT=ROOT/'build/zone-code-refs.txt'
# Symbol prefixes per overlay (after the C symbol's leading underscore).
ZONE_PREFIXES={'R1':('placements','r1_','z1_'),'R3':('r3_','cc2_','z3_'),'R4':('r4_','tt_','z4_'),'R5':('r5_','qq_','z5_'),
               'R6':('r6_','ww','z6_'),'R7':('r7_','ss_','z7_'),'R8':('r8_','mm','z8_'),
               'R0':('fe_',)}  # R0: the front-end overlay (title, menus, Time Attack, sound test, ending)
# Range bounds src/main.c reads; they share addresses with the first overlay and .rodata objects.
LINKER={'___zone_tables_start','___zone_tables_end'}

def fail(message):sys.exit(f'FAIL: zone code: {message}')
if not ELF.is_file():fail(f'{ELF.relative_to(ROOT)} is missing; build first')
def readelf(*flags):return subprocess.check_output([READELF,'-W',*flags,ELF],text=True)

sections={}  # index -> (name, address, size, allocated); offsets: index -> file offset
offsets={}
for m in re.finditer(r'^\s*\[\s*(\d+)\]\s+(\S+)\s+\S+\s+([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+\S+\s+(\S*)',readelf('-S'),re.M):
    sections[int(m.group(1))]=(m.group(2),int(m.group(3),16),int(m.group(5),16),'A' in m.group(6))
    offsets[int(m.group(1))]=int(m.group(4),16)
image=ELF.read_bytes()
overlay={i:n[len('.zone_'):] for i,(n,_,_,_) in sections.items() if re.fullmatch(r'\.zone_R\d',n)}
if not overlay:fail('the ELF has no .zone_R<n> overlay sections')
lo=min(sections[i][1] for i in overlay);hi=max(sections[i][1]+sections[i][2] for i in overlay)
unknown=set(overlay.values())-set(ZONE_PREFIXES)
if unknown:fail(f'no prefix rule for overlay {sorted(unknown)}; add it to ZONE_PREFIXES')

symbols=[]  # (value, size, type, section index, name)
for line in readelf('-s').splitlines():
    p=line.split()
    if len(p)<8 or not p[0].endswith(':') or not p[6].isdigit():continue
    symbols.append((int(p[1],16),int(p[2]),p[3],int(p[6]),p[7]))

# 1. Prefixes inside the overlays.
bad=[];counts=collections.Counter();code=collections.Counter()
for value,size,kind,ndx,name in symbols:
    if ndx not in overlay or kind in('SECTION','FILE') or name in LINKER:continue
    zone=overlay[ndx];counts[zone]+=1
    if kind=='FUNC':code[zone]+=size
    if not name.lstrip('_').startswith(ZONE_PREFIXES[zone]):bad.append(f'{zone} {name} ({kind} {size} B at {value:#x})')
if bad:fail(f'{len(bad)} overlay symbol(s) lack their zone prefix: '+'; '.join(bad[:12]))
resident_sections={i for i,(n,a,s,alloc) in sections.items() if alloc and i not in overlay}
for value,size,kind,ndx,name in symbols:
    if ndx in resident_sections and kind in('FUNC','OBJECT') and lo<=value<hi:
        fail(f'resident symbol {name} lies in the overlay range {lo:#x}..{hi:#x}')

# 2. Resident -> overlay references (relocations kept by --emit-relocs).
by_section=collections.defaultdict(list)
for s in symbols:
    if s[2] in('FUNC','OBJECT') and s[1]:by_section[s[3]].append(s)
for v in by_section.values():v.sort()
def containing(ndx,address):
    best=None
    for s in by_section.get(ndx,()):
        if s[0]>address:break
        if address<s[0]+s[1]:best=s
    return best
def section_of(address):
    for i in resident_sections:
        n,a,s,_=sections[i]
        if a<=address<a+s:return i
    return None
names={sections[i][0]:i for i in sections}
symbol_section={(name,value):ndx for value,size,kind,ndx,name in symbols}
relocs=readelf('-r')
if 'Relocation section' not in relocs:fail('the ELF carries no relocations; link with -Wl,--emit-relocs (Makefile SH_LDFLAGS)')
# Every relocation: (referring section, offset, target address, target section).
refs=[];illegal=[];current=None
for line in relocs.splitlines():
    m=re.match(r"Relocation section '\.rela(\S+)'",line)
    if m:current=names.get(m.group(1));continue
    p=line.split()
    if current is None or not sections[current][3] or len(p)<5 or not re.fullmatch(r'[0-9a-f]{8}',p[0]):continue
    m=re.search(r'(R_SH_\w+)\s+([0-9a-f]{8})\s+(\S+)\s*([+-])\s*([0-9a-f]+)$',line)
    if not m:continue
    offset=int(p[0],16);sym=m.group(3);value=int(m.group(2),16)
    if sym in LINKER:continue
    if m.group(1)=='R_SH_DIR32':
        # This ld leaves section-symbol addends input-relative: read the linked word.
        at=offsets[current]+offset-sections[current][1]
        target=int.from_bytes(image[at:at+4],'big')
    else:target=value+(1 if m.group(4)=='+' else -1)*int(m.group(5),16)
    if lo<=target<hi:
        ndx=names.get(sym) if sym.startswith('.') else symbol_section.get((sym,value))
        if ndx not in overlay:
            if current not in overlay:illegal.append(f'{sym}+{target:#x} resolves into the overlay range from a non-overlay symbol')
            continue
    else:ndx=section_of(target)
    if ndx is not None:refs.append((current,offset,target,ndx))
# Who refers to each resident object: its referring zones ('resident' for resident code/data).
referrers=collections.defaultdict(set)
for current,offset,target,ndx in refs:
    if ndx in overlay:continue
    t=containing(ndx,target)
    if not t:continue
    if current in overlay:referrers[t].add(overlay[current])
    else:
        r=containing(current,offset);referrers[t].add(r if r else 'resident')
def private(obj,zone,seen=()):
    """A resident object only zone `zone`'s overlay (or objects private to it) refers to."""
    if obj[2]!='OBJECT' or obj in seen:return False
    who=referrers.get(obj,set())
    return bool(who) and all(w==zone or (isinstance(w,tuple) and private(w,zone,seen+(obj,))) for w in who)
# Compiler constants without a symbol (a function-local array initializer) are runs of
# relocated words: each run stands as one anonymous object for the private-table rule.
words=sorted({(current,offset) for current,offset,target,ndx in refs if current not in overlay and not containing(current,offset)})
# A referenced address starts a new object: neighbouring constants belong to other code.
starts={target for current,offset,target,ndx in refs if ndx not in overlay}
blobs={}
for current,offset in words:
    prev=None if offset in starts else blobs.get((current,offset-4))
    blobs[(current,offset)]=prev if prev else [offset,offset+4,current]
    blobs[(current,offset)][1]=offset+4
for (current,offset),(start,end,sec) in list(blobs.items()):
    blob=(start,end-start,'OBJECT',sec,f'{sections[sec][0]}+{start:#x}')
    blobs[(current,offset)]=blob
for current,offset,target,ndx in refs:
    if ndx in overlay or containing(ndx,target):continue
    for (sec,o),blob in blobs.items():
        if sec==ndx and blob[0]<=target<blob[0]+blob[1]:
            if current in overlay:referrers[blob].add(overlay[current])
            else:r=containing(current,offset);referrers[blob].add(r if r else 'resident')
            break
dispatch=[];tables=[];data=[]
for current,offset,target,ndx in refs:
    if current in overlay or ndx not in overlay:continue
    zone=overlay[ndx];t=containing(ndx,target);r=containing(current,offset) or blobs.get((current,offset))
    site=r[4] if r else f'{sections[current][0]}+{offset:#x}'
    what=t[4] if t else f'{sections[ndx][0]}+{target-sections[ndx][1]:#x}'
    if t and t[2]=='FUNC':
        ops=re.sub(r'\.lto_priv\.\d+$','',site.lstrip('_'))
        if ops.endswith('zone_ops') and ops.startswith(ZONE_PREFIXES[zone]):dispatch.append((zone,site,what))
        elif r and private(r,zone):tables.append((zone,site,what))
        else:illegal.append(f'{site} -> {zone} {what}')
    else:data.append((zone,site,what))
REPORT.write_text('# resident -> overlay references in the last Saturn link (tools/test_zone_code.py)\n'+
    ''.join(f'code {z} {s} -> {w}\n' for z,s,w in sorted(set(dispatch)))+
    ''.join(f'table {z} {s} -> {w}\n' for z,s,w in sorted(set(tables)))+
    ''.join(f'data {z} {s} -> {w}\n' for z,s,w in sorted(set(data))))
# 3. Resident -> overlay data references must be reviewed (tests/zone_data_refs.txt): a
# resident helper shared by several zones that reads one zone's overlay table reads
# whatever another zone's overlay holds at that address (V0.075 QQ explosion stall).
ALLOWED=ROOT/'tests/zone_data_refs.txt'
norm=lambda s:s.lstrip('_').split('.')[0]
allowed={l.strip() for l in ALLOWED.read_text().splitlines() if l.strip() and not l.startswith('#')}
unlisted=sorted({f'{z} {norm(s)} -> {norm(w)}' for z,s,w in data}-allowed)
if unlisted:fail(f'{len(unlisted)} unreviewed resident->overlay data reference(s) (not in {ALLOWED.relative_to(ROOT)}): '+'; '.join(unlisted[:16]))
if illegal:fail(f'{len(illegal)} resident->overlay code reference(s) outside zone_ops: '+'; '.join(sorted(set(illegal))[:int(__import__("os").environ.get("ZONE_CODE_SHOW","16"))]))
print(f'PASS: zone code: {sum(counts.values())} overlay symbols carry their zone prefix ('+
      ', '.join(f'{z} {counts[z]}' for z in sorted(counts))+'); overlay code '+
      ', '.join(f'{z} {code[z]} B' for z in sorted(code))+
      f'; resident->overlay: {len(set(dispatch))} code refs from zone_ops tables, '
      f'{len(set(tables))} from zone-private tables, '
      f'{len(set(data))} data refs (listed in {REPORT.relative_to(ROOT)})')
