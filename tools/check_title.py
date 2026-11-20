#!/usr/bin/env python3
"""Compare title screen runs with the retail records (tools/title_retail.py).

host: build/title-host/{route}.jsonl from tools/title_test.c must equal the retail state
after every V-INT (the last retail frame of each vintCounter value): program variables,
RAM buffers, CRAM, H-scroll, sprite table, name tables, pattern tiles, objects and the
frames the original program misses before the next V-INT.
"""
import json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RETAIL=ROOT/'build/title-retail'
FIELDS=['routine','mode','timer','exit','menu_sel','menu_options','cycle','ctrl','enable_display','gfx','cram','palette','fade',
    'hscroll_buf','hscroll','sprites_buf','sat','clouds_image','plane_a','plane_b','tiles','cloud_tiles']

def retail_rows(route):
    rows=[json.loads(l) for l in (RETAIL/f'{route}.jsonl').read_text().splitlines()]
    rows=[r for r in rows if r.get('title')];blobs=json.loads((RETAIL/f'{route}-blobs.json').read_text())
    last={};frames={}
    for r in rows:last[r['v']]=r;frames[r['v']]=frames.get(r['v'],0)+1
    return last,frames,blobs

def objects(blob):
    data=bytes.fromhex(blob);out=[]
    for i in range(10):
        o=data[i*0x40:(i+1)*0x40]
        out.append([o[2],o[3],struct.unpack('>H',o[4:6])[0],o[10],struct.unpack('>h',o[12:14])[0],struct.unpack('>h',o[16:18])[0]])
    return out

def host(route):
    last,frames,blobs=retail_rows(route)
    rows=[json.loads(l) for l in (ROOT/f'build/title-host/{route}.jsonl').read_text().splitlines()]
    mismatches={};first={};compared=0
    final=max(last)
    for r in rows:
        v=r['v']
        if v not in last:continue
        retail=last[v];compared+=1
        checks={f:(retail[f],r[f]) for f in FIELDS}
        # The Sub CPU runs ControlClouds after it takes the render command; a record can precede that by one render.
        if retail['gfx'][1]==r['gfx'][1]-2 and retail['gfx'][:1]+retail['gfx'][2:]==r['gfx'][:1]+r['gfx'][2:]:checks['gfx']=(r['gfx'],r['gfx'])
        checks['display']=(bytes.fromhex(retail['reg'])[1]>>6&1,r['display'])
        checks['objects']=(objects(blobs[retail['objects']]),r['objects'])
        # Frames without a V-INT before the next one (the final V-INT has no successor).
        if v<final:checks['lag_frames']=(frames[v]-1,r['lag_frames'])
        for name,(a,b) in checks.items():
            if a!=b:
                mismatches[name]=mismatches.get(name,0)+1
                first.setdefault(name,{'v':v,'retail':a,'host':b})
    exit_code=rows[-1]['exit_code'] if rows[-1]['done'] else None
    return {'route':route,'vints_compared':compared,'retail_last_v':final,'host_last_v':rows[-1]['v'],'exit_code':exit_code,
        'mismatches':mismatches,'first_mismatch':first}

def saturn():
    """Beetle Saturn run (tools/test-title-emulator.sh): the state after every V-INT, the pad each V-INT
    read and the frames between V-INTs equal the retail records; the picture two frames after a
    V-INT (VDP1 shows a command list one frame after VDP2) is compared with the retail picture of
    that state (the frame rendered before the next V-INT)."""
    import hashlib
    last,frames,blobs=retail_rows('newgame')
    retail_all=[json.loads(l) for l in (RETAIL/'newgame.jsonl').read_text().splitlines()]
    retail_all=[r for r in retail_all if r.get('title')]
    first_retail={}
    for r in retail_all:first_retail.setdefault(r['v'],r)
    keys=['frame','v','state','timer','routine','cam','pad','lag','exit_code','cram','hscroll','sat','palette','plane_a','plane_b','tiles','cloud_tiles','picture','valid','vint_vblanks','vint_vblanks_max','present_vblanks']
    rows=[dict(zip(keys,l.split())) for l in (ROOT/'build/title-qa/title-frames.txt').read_text().splitlines()]
    for r in rows:
        for k in ('frame','v','timer','routine','cam','pad','lag','exit_code','valid','vint_vblanks','vint_vblanks_max','present_vblanks'):r[k]=int(r[k])
        r['state']=int(r['state'],16)
    by_frame={r['frame']:r for r in rows};sat_last={};sat_first={};sat_count={}
    for r in rows:sat_last[r['v']]=r;sat_first.setdefault(r['v'],r);sat_count[r['v']]=sat_count.get(r['v'],0)+1
    final=max(last);mismatch={};first={};diagnostic={}
    def check(name,v,a,b):
        if a!=b:mismatch[name]=mismatch.get(name,0)+1;first.setdefault(name,{'v':v,'retail':a,'saturn':b})
    for v in range(1,final+1):
        if v not in sat_last:check('missing_vint',v,True,False);continue
        s=sat_last[v];r=last[v]
        check('timer',v,r['timer'],s['timer']);check('routine',v,r['routine'],s['routine'])
        check('mode',v,r['mode'],s['state']&255);check('exit',v,r['exit'],s['state']>>8&255);check('menu_sel',v,r['menu_sel'],s['state']>>16&255)
        if not (r['gfx'][1]==s['cam'] or r['gfx'][1]==s['cam']-2):check('camera_y',v,r['gfx'][1],s['cam'])
        # Memory CRCs are read while the program may already run the next V-INT; they are
        # diagnostics here (tools/test-title.sh compares the full state on the host).
        for f in ('cram','hscroll','sat','palette','plane_a','plane_b','tiles','cloud_tiles'):
            if r[f]!=s[f]:diagnostic[f]=diagnostic.get(f,0)+1
        check('pad',v,first_retail[v]['pad'],s['pad'])
        if 1<=v<final:check('frames_between_vints',v,frames[v],sat_count.get(v))
    # Frames between V-INTs are equal, so retail and Saturn frames pair one to one from V-INT 1. The
    # Saturn shows a frame's picture DELAY frames later (src/title_view.inc); pictures due after the
    # program has returned belong to the next mode and are not compared.
    DELAY=3
    r0=next(i for i,r in enumerate(retail_all) if r['v']==1);s0=sat_first[1]['frame'];count=len(retail_all)-r0
    last_title_frame=rows[-1]['frame']
    compared=[i for i in range(count) if s0+i+DELAY<=last_title_frame]
    # The native 256-pixel title fills 320 pixels using the nearest hardware
    # step, round(256*256/320) = 205. Sprites and backgrounds must use this same
    # global grid. Require exact colour, row, frame AND horizontal source texel:
    # no neighbouring-texel tolerance. Explicitly account for both former bars.
    import array,zipfile
    captures_raw=(ROOT/'build/title-qa/title-pixels.bin').open('rb')
    frame_indices={r['frame']:i for i,r in enumerate(rows)}
    archive=zipfile.ZipFile(RETAIL/'newgame-pixels.zip')
    indices=[(y*256+x*205//256,x<32 or x>=288) for y in range(224) for x in range(320)]
    different=[];exact=0;total=0;outside=0;edge_outside=0
    for i in compared:
        f=s0+i+DELAY;r=retail_all[r0+i];s=by_frame.get(f)
        if not s or not s['valid']:different.append((r['v'],f));continue
        reference=array.array('H',archive.read(r['pixels']))
        captures_raw.seek(frame_indices[f]*224*320*2);actual=array.array('H',captures_raw.read(224*320*2))
        assert len(reference)==224*256 and len(actual)==224*320
        if sys.byteorder!='little':reference.byteswap();actual.byteswap()
        misses=0
        for color,(x,edge) in zip(actual,indices):
            if color==reference[x]:exact+=1
            else:misses+=1;edge_outside+=edge
        total+=len(actual);outside+=misses
        if misses:different.append((r['v'],f,misses))
    pictures={'display_delay_frames':DELAY,'retail_frames':count,'compared':len(compared),'equal':len(compared)-len(different),
        'comparison':'Full-width presentation; exact retail pixels sampled at floor(x*205/256), no pixel tolerance',
        'source_step_numerator':205,'source_step_denominator':256,
        'exact_resample_pixels':exact,'total_pixels':total,'mismatched_pixels':outside,'former_bar_mismatched_pixels':edge_outside,
        'not_shown_after_return':count-len(compared),'different_vints_and_frames':different[:40]}
    log=(ROOT/'build/title-qa/results.log').read_text()
    import re
    handed=re.search(r'Title: handed over after (\d+) frames; Act 1 running (\d+) frames later',log)
    over=re.search(r'Game over: title screen returned (\d+) frames after the fixture',log)
    captures={}
    for path in sorted((ROOT/'build/title-qa').glob('title-*.ppm')):
        raw=path.read_bytes();header,data=raw.split(b'255\n',1)
        assert header==b'P6\n330 224\n' and len(data)==330*224*3,path.name
        captures[path.stem]=hashlib.sha256(raw).hexdigest()
    report={'disc_sha256':hashlib.sha256((ROOT/'dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest(),
        'new_game_frames':int(handed[1]) if handed else None,'act1_after_frames':int(handed[2]) if handed else None,
        'game_over_to_title_frames':int(over[1]) if over else None,'captures':captures,'hardware_tested':False,
        'route':'newgame','vints':final,'state_mismatches':mismatch,'first_mismatch':first,'memory_crc_differences':diagnostic,'pictures':pictures,
        'limits':'One NEW GAME route and the game over fixture; the time-out route, attract mode and the RAM data scene are checked on the host only or not ported. Memory CRCs on the Saturn are diagnostics because they are read while the program runs.'}
    for name,m in first.items():print('  first',name,json.dumps(m)[:300])
    from vdp2_title_cycles import inspect as inspect_cycles
    state=ROOT/'build/title-qa/title-v120.state'
    report['vdp2_cycle_schedule']=inspect_cycles(state)
    report['vdp2_state_sha256']=hashlib.sha256(state.read_bytes()).hexdigest()
    report['vdp2_check_source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'src/title_vram.h',ROOT/'src/title_view.inc',ROOT/'tools/vdp2_title_cycles.py',ROOT/'tools/check_title.py',ROOT/'tools/emulator_test.c']}
    report['emulator_core_sha256']=hashlib.sha256((ROOT/'.deps/beetle-saturn/mednafen_saturn_libretro.dylib').read_bytes()).hexdigest()
    report['passed']=not mismatch and not different and pictures['compared']>=count-4 and bool(handed) and bool(over) and not report['vdp2_cycle_schedule']['errors']
    print(json.dumps({k:v for k,v in report.items() if k not in('first_mismatch','captures')},indent=1))
    return report

def main():
    mode=sys.argv[1] if len(sys.argv)>1 else 'host'
    if mode=='saturn':
        report=saturn();(ROOT/'dist/title-report.json').write_text(json.dumps(report,indent=2)+'\n')
        if not report['passed']:sys.exit('Title screen run differs from the retail records')
        p=report['pictures'];print(f"Title state equals retail: {report['vints']} V-INTs; full-width sampling checks {p['equal']}/{p['compared']} pictures; NEW GAME, Act 1 and game over to title passed")
        return
    assert mode=='host',mode
    exits={'newgame':1,'timeout':0,'stafftimes':9}
    results=[host(route) for route in exits]
    ok=True
    for r in results:
        print(json.dumps({k:v for k,v in r.items() if k!='first_mismatch'}))
        for name,m in r['first_mismatch'].items():print('  first',name,json.dumps(m)[:400])
        # The program returns in the frame of its last V-INT, so the retail records end one vintCounter value earlier.
        ok=ok and not r['mismatches'] and r['host_last_v']==r['retail_last_v']+1 and r['exit_code']==exits[r['route']]
    (ROOT/'build/title-host/report.json').write_text(json.dumps(results,indent=2)+'\n')
    if not ok:sys.exit('Title host run differs from the retail records')
    print(f"Title host run equals retail: {sum(r['vints_compared'] for r in results)} V-INTs in 3 routes, exit codes 1, 0 and 9")

if __name__=='__main__':main()
