#!/usr/bin/env python3
"""Bind checkpoint clock old-code failures to Saturn reload and HUD evidence."""
import hashlib,json,re,tarfile
from pathlib import Path
from convert_assets import ROOT
from hud_pixels import verify as verify_hud

def main():
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();evidence={}
    def retain(p):evidence[str(p.relative_to(ROOT))]=sha(p)
    baseline=ROOT/'build/hardware-candidate-v0.055-01/candidate-manifest.json'
    m=json.loads(baseline.read_text());retain(baseline)
    archive=ROOT/'build/visual-source-v0.055-01.tar.gz';retain(archive)
    with tarfile.open(archive) as a:
        assert hashlib.sha256(a.extractfile('src/player.c').read()).hexdigest()==m['source_sha256']['src/player.c']
    folder=ROOT/'build/checkpoint-clock'
    for label in ['current','v055-original']:
        path=folder/(label+'-report.json');r=json.loads(path.read_text());retain(path)
        assert r['cases']==1444 and r['states']==174724
        assert r['mismatches']==(0 if label=='current' else 1180) and r['passed']==(label=='current')
        for name,want in r['source_sha256'].items():assert sha(ROOT/name)==want,('stale clock source',name)
        for suffix,key in [('.log','log_sha256'),('-test','binary_sha256')]:
            p=folder/(label+suffix);assert sha(p)==r[key];retain(p)
        assert sha(ROOT/'.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib')==r['core_sha256']
        if label=='v055-original':assert r['source_sha256']['build/checkpoint-clock/v055-source/src/player.c']==m['source_sha256']['src/player.c']
    logpath=ROOT/'build/world-qa/results.log';retain(logpath);log=logpath.read_text()
    pattern=r'^Checkpoint clock: frame=(\d+) simulation=(\d+) id=(\d+) resets=(\d+) elapsed=(\d+) score=(\d+) rings=(\d+) lives=(\d+)$'
    rows=[tuple(map(int,v)) for v in re.findall(pattern,log,re.M)];assert len(rows)>=800
    states={}
    for row in rows:
        frame,simulation,*values=row
        if simulation in states:assert states[simulation][1:]==row[1:],('incoherent clock snapshot',simulation)
        states[simulation]=row
    activation=next(r for r in rows if r[2])
    saved=activation[4];assert saved%60,'Target route must expose fractional restore error'
    respawn=next(r for r in rows if r[3]);first=respawn[1]
    assert respawn[2]==2 and respawn[7]==2
    for n in range(121):
        r=states[first+n];assert r[3]==1 and r[4]==saved//60*60+n,('target checkpoint clock',n,r,saved)
    # Pictures can lag coherent logic publication by one refresh. Require a
    # unique match from the current/previous captured update, not a wide window.
    pixels={}
    for label,offset in [('checkpoint-respawn',3),('checkpoint-restored',20)]:
        path=ROOT/'build/world-qa'/(label+'.ppm');retain(path);matches=[]
        for r in rows:
            if r[0] not in [respawn[0]+offset-1,respawn[0]+offset]:continue
            try:count=verify_hud(path.read_bytes(),r[5],r[6],r[4],r[7],0,check_rings=r[6]!=0)
            except AssertionError:continue
            matches.append(dict(simulation=r[1],elapsed=r[4],pixels=count))
        assert len(matches)==1,('checkpoint HUD match',label,matches)
        pixels[label]=matches[0]
    report=dict(passed=True,disc_sha256=sha(ROOT/'dist/sonic-cd-saturn-prototype.bin'),
        host_cases=1444,host_states=174724,rejected_v055_cases=1180,
        target_route_states=len(states),target_clock_states=121,saved_ticks=saved,
        restored_ticks=respawn[4],respawn_simulation=first,pictures=pixels,
        source_sha256={name:sha(ROOT/name) for name in ['src/player.c','src/scd_player.h','src/main.c',
            'tools/check_checkpoint_clock_target.py','tools/checkpoint_clock_test.c','tools/test_checkpoint_clock.py',
            'tools/emulator_test.c','tools/hud_pixels.py','tools/convert_objects.py']},
        evidence_sha256=evidence,
        limits='Saved-spawn whole-second restoration, next 120 ordinary ticks and two opaque HUD pictures on the measured route. Not checkpoint camera, fade, all actor fields or physical-console parity.')
    (ROOT/'dist/checkpoint-clock-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Checkpoint clock target:',saved,'->',respawn[4],'ticks;',len(states),'route states; 121 clocks;',sum(p['pixels'] for p in pixels.values()),'HUD pixels')
if __name__=='__main__':main()
