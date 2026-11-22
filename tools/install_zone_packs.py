#!/usr/bin/env python3
"""Install the harvested stage packs for every zone and generate their pack rows.

tools/extract_zone_auto.py locates each retail program's structures on its own,
with no template program and no per-round branch, and writes the results to
build/auto-extract/<round>/.  This copies the ones the port serves from the CD
into assets/generated and writes src/stage_zone_packs.h, which src/stage_packs.h
includes and tools/stage_packs.py scans.

Palmtree Panic is zone 0 and keeps its own STAGE_PACK and STAGE_ACT_PACK rows,
so it is not installed here.  Wacky Workbench was extracted earlier by
tools/extract_zone.py; its rows are generated here with the rest so one table
describes them all.  Its packs now come from the harvest too: tools/extract_zone.py
does not write the cells UpdateAnimTiles fills when a level is set up, so its
packs differ from the harvest in exactly those cells.

Every copy is checked against the pack_sha256 the extractor recorded, and a file
already in the tree is only accepted when it is byte identical.  After a
re-harvest (tools/extract_zone_auto.py <round> --manifest), pass --replace to
overwrite installed files whose bytes the harvest has changed; the harvest copy
still has to match the manifest first.

A harvest is only used while it is current. Each round's report.json records the
digests of the extractor and its helpers (extract_zone_auto.TOOLS) and of every
retail program it read. When any of them differs from the current tools or
disc, or a round has no report, that round is re-extracted with
`extract_zone_auto.py <round> --manifest` and its packs are installed over the
old ones. A round that is still stale after that stops the build. With no
manifest at all (a fresh checkout), every round is extracted, which creates it.

A re-extracted round is recorded in build/zone-packs-pending.json before the
extractor runs and cleared only after every pack is installed, so a run
interrupted between the two still overwrites that round's packs next time
instead of refusing them.
"""
import hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
import object_layouts
import extract_zone_auto as harvest
from extract_mmd import disc_files

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'build/all-zones-extract.json'
GENERATED=ROOT/'assets/generated'
HEADER=ROOT/'src/stage_zone_packs.h'

# round -> zone index used by scd_player_zone, asset prefix, CD name prefix, name.
# The zone index is the retail round's position in GAME.C's da_tbl, which is what
# stageno.b.h carries: R1 R3 R4 R5 R6 R7 R8.
ZONES={
    3:(1,'cc','CC','COLLISION CHAOS'),
    4:(2,'tt','TT','TIDAL TEMPEST'),
    5:(3,'qq','QQ','QUARTZ QUADRANT'),
    6:(4,'ww','WW','WACKY WORKBENCH'),
    7:(5,'ss','SS','STARDUST SPEEDWAY'),
    8:(6,'mm','MM','METALLIC MADNESS'),
}
# Wacky Workbench came from tools/extract_zone.py and uses that tool's names.
LEGACY_COLLISION={6:'wwcollision'}
ERAS='ABCD'
ACTS=(1,2,3)

def sha(data):return hashlib.sha256(data).hexdigest()

def pending_path():return ROOT/'build/zone-packs-pending.json'

def load_pending():
    """Rounds re-extracted by an earlier run that did not finish installing."""
    path=pending_path()
    return set(json.loads(path.read_text())) if path.exists() else set()

def save_pending(rounds):
    """Record rounds (atomically) whose installed packs a re-harvest may replace;
    an empty set removes the record."""
    path=pending_path()
    if not rounds:
        path.unlink(missing_ok=True);return
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(sorted(rounds)))
    os.replace(tmp,path)

def install(src,dst,want,replace=False):
    data=src.read_bytes()
    got=sha(data)
    if got!=want:raise SystemExit(f'{src}: sha256 {got} but the manifest records {want}')
    if dst.exists():
        if sha(dst.read_bytes())==got:return False
        if not replace:raise SystemExit(f'{dst} already exists with different bytes; refusing to overwrite (--replace after a re-harvest)')
    shutil.copyfile(src,dst)
    return True

def stale_reasons(report,tools,programs):
    """Why one round's harvest report no longer matches the current extractor
    and disc. tools maps path -> sha256; programs maps program -> MMD sha256.
    An empty list means the harvest is current."""
    if report is None:return ['no report.json']
    reasons=[]
    recorded=report.get('tools') or {}
    for path,want in tools.items():
        got=recorded.get(path)
        if got!=want:reasons.append(f'{path} {got[:8] if got else "unrecorded"} != current {want[:8]}')
    rows=report.get('programs') or {}
    for program,want in programs.items():
        if program not in rows:reasons.append(f'{program} missing')
        elif rows[program].get('mmd_sha256')!=want:reasons.append(f'{program}__.MMD differs from the disc')
    return reasons

def refresh_harvest(rounds,force=False):
    """Re-extract every stale round (every round when force); return
    (reports, refreshed rounds)."""
    tools=harvest.tool_hashes()
    disc=disc_files((ROOT/'build/retail/sonic.iso').read_bytes())
    reports={};refreshed=load_pending()&set(rounds)
    for rnd in rounds:
        path=ROOT/f'build/auto-extract/{rnd}/report.json'
        programs={p:sha(disc[f'{p}__.MMD']) for p in harvest.programs_of(rnd)}
        load=lambda:json.loads(path.read_text()) if path.exists() else None
        reasons=['no manifest'] if force else stale_reasons(load(),tools,programs)
        if reasons:
            print(f'R{rnd} harvest is stale ({"; ".join(reasons[:3])}); re-extracting')
            save_pending(refreshed|{rnd})
            subprocess.run([sys.executable,str(ROOT/'tools/extract_zone_auto.py'),str(rnd),'--manifest'],
                           cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
            reasons=stale_reasons(load(),tools,programs)
            if reasons:raise SystemExit(f'R{rnd} harvest is still stale after re-extracting: {reasons}')
            refreshed.add(rnd)
        reports[rnd]=load()
    return reports,refreshed

def main():
    # A fresh checkout has no manifest: extracting every round creates it.
    # Every harvested round, not only the installed ones: tools/object_layouts.py
    # also reads Palmtree Panic's (round 1) records.
    reports,refreshed=refresh_harvest(harvest.ROUNDS,force=not MANIFEST.exists())
    manifest=json.loads(MANIFEST.read_text())
    slots=harvest.slot_bytes()  # per-slot capacities from src/stage_packs.h
    GENERATED.mkdir(parents=True,exist_ok=True)
    rows=[];written=0;kept=0
    # Object layouts are derived, not copied: each act's retail records are
    # translated into the port's object types by tools/object_layouts.py.
    layouts=object_layouts.all_layouts()
    none=GENERATED/'objlay-none.bin'
    none.write_bytes(object_layouts.encode([(0,0,0,0,0,0)]))
    for rnd in sorted(ZONES):
        zone,prefix,cd,name=ZONES[rnd]
        colprefix=LEGACY_COLLISION.get(rnd,prefix+'collision')
        entry=manifest['rounds'][f'R{rnd}']
        assert entry['all_pc_checks_passed'],f'R{rnd} did not pass its PC cross-checks'
        out=ROOT/f'build/auto-extract/{rnd}'
        # Line splicing runs before comment removal, so a label inside the
        # macro has to carry the continuation too.
        rows.append(f'    /* R{rnd} {name} */ \\')
        for act in ACTS:
            for index,era in enumerate(ERAS):
                # Act 3 runs in the good and bad futures only.
                if act==3 and era in 'AB':continue
                program=f'R{rnd}{act}{era}'
                data=entry['program_data'][program]
                current=reports[rnd]['programs'][program]
                for kind in ('pack_sha256','collision_sha256'):
                    if data[kind]!=current[kind]:
                        raise SystemExit(f'{program}: manifest {kind} {data[kind][:8]} but the harvest report has {current[kind][:8]}')
                assert data['pack_bytes']<=slots[f'PPZ{index}'],(program,data['pack_bytes'],slots[f'PPZ{index}'])
                assert data['collision_bytes']<=slots[f'COL{index}'],(program,data['collision_bytes'],slots[f'COL{index}'])
                pack=GENERATED/f'{prefix}{rnd}{act}{era}.bin'
                col=GENERATED/f'{colprefix}{rnd}{act}{era}.bin'
                for src,dst,want in ((out/f'ppz{rnd}{act}{era}.bin',pack,data['pack_sha256']),
                                     (out/f'collision{rnd}{act}{era}.bin',col,data['collision_sha256'])):
                    if not src.exists():raise SystemExit(f'{src} is missing from the harvest')
                    if install(src,dst,want,'--replace' in sys.argv[1:] or rnd in refreshed):written+=1
                    else:kept+=1
                rows.append(f'    STAGE_ZONE_PACK(PACK_PPZ{index},{zone},{act-1},'
                            f'"{cd}{act}A{index}.BIN","{pack.relative_to(ROOT)}") \\')
                rows.append(f'    STAGE_ZONE_PACK(PACK_COL{index},{zone},{act-1},'
                            f'"{cd}C{act}A{index}.BIN","{col.relative_to(ROOT)}") \\')
            entries,_=layouts[(rnd,act)]
            layout=GENERATED/f'{prefix}obj{rnd}{act}.bin'
            data=object_layouts.encode(entries)
            if not layout.exists() or layout.read_bytes()!=data:layout.write_bytes(data);written+=1
            else:kept+=1
            rows.append(f'    STAGE_ZONE_PACK(PACK_OBJECTS,{zone},{act-1},'
                        f'"{cd}O{act}.BIN","{layout.relative_to(ROOT)}") \\')
    rows[-1]=rows[-1].rstrip(' \\')
    HEADER.write_text(
        '/* Generated by tools/install_zone_packs.py.  Do not edit.\n'
        '   One row per retail stage program that the port serves from the CD.\n'
        '   Zone is the index scd_player_zone takes; act is zero based.\n'
        '   STAGE_ZONE_PACK(identifier, zone, act index, CD file, generated source) */\n'
        '#ifndef SCD_STAGE_ZONE_PACKS_H\n#define SCD_STAGE_ZONE_PACKS_H\n'
        '#define STAGE_ZONE_PACKS \\\n'+'\n'.join(rows)+'\n#endif\n')
    save_pending(set())  # every re-extracted round's packs are installed
    print(f'{len([r for r in rows if "STAGE_ZONE_PACK" in r])} rows over {len(ZONES)} zones; '
          f'{written} files written, {kept} already identical'
          +(f'; re-extracted R{", R".join(map(str,sorted(refreshed)))}' if refreshed else ''))

if __name__=='__main__':main()
