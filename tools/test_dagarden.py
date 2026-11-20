#!/usr/bin/env python3
"""Host D.A. Garden check against the retail records (tools/dagarden_retail.py).

Builds tools/dagarden_test.c with src/dagarden.c under ASan/UBSan, runs every retail route's
pad script and compares the state after every V-INT with the last retail frame of that
vintCounter: Main CPU variables, objects, palettes, sprite buffer, planet image, trace table,
stamp map, Sub CPU planet object, CRAM, VSRAM, H-scroll, name tables, sprite table, pattern
tiles; and the frames the original program misses before the next V-INT.
Usage: test_dagarden.py [-v] [route ...]   (default: every route in tools/dagarden_retail.py ROUTES;
missing retail records are made first)
"""
import json,struct,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import dagarden_retail as dr
# Japanese PLANET files by default (src/dagarden.c plays the Japanese soundtrack's titles).
RETAIL=dr.OUT;HOST=ROOT/'build/dagarden-host'
FIELDS=['routine','timer','buf_count','cycle','volcano','spr_cycle','sel_flags','sel','spawn_timers','spawn','buttons','seed','zone','no_cycle',
    'ctrl','ga_flags','ga_cmd','objects','palette','fade','sprites_buf','planet_image','trace','stamp_map','planet','sub',
    'object_tiles']
# Written only by the V-INT (whose DMA holds the 68000 for frames): compared at the first retail frame of
# each vintCounter, against the host state right after the V-INT routine.
VDP_FIELDS=['cram','vsram','hscroll','plane_a','plane_b','sat','buffer1','buffer2']

def tables_base():
    from extract_mmd import disc_files
    disc=disc_files((ROOT/'build/retail/sonic.iso').read_bytes()) if dr.REGION=='us' else dr.japanese_planet();m=disc['PLANET_M.MMD']
    pack=(ROOT/'assets/generated/dagarden.bin').read_bytes();count=struct.unpack_from('>I',pack,4)[0]
    names=[l.split()[1] for l in (ROOT/'assets/generated/dagarden-parts.inc').read_text().splitlines() if l.startswith('#define DG_PART_') and l.split()[1] not in ('DG_PART_COUNT','DG_PART_TITLE_FIRST')]
    index=int([l for l in (ROOT/'assets/generated/dagarden-parts.inc').read_text().splitlines() if l.startswith('#define DG_PART_TABLES ')][0].split()[2].rstrip('u'))
    off,length=struct.unpack_from('>II',pack,8+index*8);data=pack[off:off+length]
    origin=struct.unpack_from('>I',m,2)[0];assert m.count(data)==1
    return origin+m.index(data)-0x100

def normalize_retail(r,blobs,base,objects_addr):
    out=dict(r)
    data=bytearray(bytes.fromhex(blobs[r['objects']]))
    for i in range(16):
        m=struct.unpack_from('>I',data,i*64+0x28)[0]
        if m:struct.pack_into('>I',data,i*64+0x28,m-base)
    out['objects']=data.hex()
    sel=bytearray(bytes.fromhex(r['sel']));title=struct.unpack_from('>H',sel,4)[0]
    if title:struct.pack_into('>H',sel,4,(title-(objects_addr&0xffff))//0x40)
    out['sel']=sel.hex()
    p=bytes.fromhex(r['planet']);out['planet']=(bytes(3)+p[3:4]+bytes(12)+p[0x10:0x12]+bytes(2)+p[0x14:0x16]+bytes(2)+p[0x18:0x1a]+bytes(2)+p[0x1c:0x1e]+bytes(4)).hex()
    out['sub']=[0]+r['sub'][1:]
    v=bytes.fromhex(r['vsram']);out['vsram']='%04x%04x'%(v[0]|v[1]<<8,v[2]|v[3]<<8)
    out['ga_cmd']=[0]+r['ga_cmd'][1:]
    return out

def retail_rows(route):
    rows=[json.loads(l) for l in (RETAIL/f'{route}.jsonl').read_text().splitlines()]
    rows=[r for r in rows if r['run']];blobs=json.loads((RETAIL/f'{route}-blobs.json').read_text())
    last={};frames={};first={}
    for r in rows:last[r['v']]=r;frames[r['v']]=frames.get(r['v'],0)+1;first.setdefault(r['v'],r)
    return last,frames,blobs,first

def build():
    HOST.mkdir(parents=True,exist_ok=True)
    subprocess.run(['clang','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Isrc','-Iassets/generated','-fsanitize=address,undefined',
        '-fno-sanitize-recover=all','tools/dagarden_test.c','src/dagarden.c','-o',str(HOST/'dagarden_test')],cwd=ROOT,check=True)

def check(route,base,objects_addr,verbose=False):
    last,frames,blobs,firsts=retail_rows(route)
    out=subprocess.run([str(HOST/'dagarden_test'),str(ROOT/'assets/generated/dagarden.bin'),str(RETAIL/f'{route}.pad')],capture_output=True,text=True)
    rows=[json.loads(l) for l in out.stdout.splitlines()]
    final=max(last);mismatch={};first={};compared=0;lag_ok=0;lag_bad=[]
    for r in rows:
        v=r['v']
        if v not in last or v>=final or v==0:continue
        retail=normalize_retail(last[v],blobs,base,objects_addr);compared+=1
        early=normalize_retail(firsts[v],blobs,base,objects_addr)
        for f in FIELDS+VDP_FIELDS:
            a,b=(early[f],r['vdp'][f]) if f in VDP_FIELDS else (retail[f],r[f])
            if a!=b:
                mismatch[f]=mismatch.get(f,0)+1
                if f not in first:first[f]=(v,a if len(str(a))<200 else 'blob',b if len(str(b))<200 else 'blob')
        if v>0:
            if r['lag_frames']+1==frames[v]:lag_ok+=1
            else:lag_bad.append((v,frames[v]-1,r['lag_frames']))
    host_last=rows[-1]['v'] if rows else -1
    summary={'route':route,'compared':compared,'retail_last_v':final,'host_last_v':host_last,'host_done':rows[-1]['done'] if rows else 0,
        'mismatch':mismatch,'lag_ok':lag_ok,'lag_bad':len(lag_bad)}
    if verbose:summary['first']=first;summary['lag_examples']=lag_bad[:12]
    return summary

def main():
    args=[a for a in sys.argv[1:] if not a.startswith('-')];verbose='-v' in sys.argv
    import dagarden_retail as dr
    routes=args or sorted(dr.ROUTES)
    for route in routes:
        # Retail records are made once per route (minutes each in the pinned core) and reused.
        if not (RETAIL/f'{route}.jsonl').exists() or not (RETAIL/f'{route}.pad').exists():
            subprocess.run([sys.executable,str(ROOT/'tools/dagarden_retail.py'),route],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    main_layout,_=dr.layout()
    build();base=tables_base();ok=True
    for route in routes:
        s=check(route,base,main_layout['objects'],verbose)
        print(json.dumps(s))
        ok=ok and not s["mismatch"] and s["compared"]>0 and s["host_done"] and not s["lag_bad"]
    print(('PASS' if ok else 'FAIL')+': D.A. Garden host state equals the retail record after every V-INT on %s'%','.join(routes))
    return 0 if ok else 1

if __name__=='__main__':sys.exit(main())
