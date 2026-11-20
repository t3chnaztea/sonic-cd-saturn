#!/usr/bin/env python3
"""Verify exact target route replay, preserving its actual bounded coverage."""
import argparse,hashlib,json,os,re,struct
from pathlib import Path
from ppz_journey import ROOT
from hud_pixels import verify as verify_hud
from title_card_plc import native_wait

def main():
    p=argparse.ArgumentParser();p.add_argument('explorer',type=Path);p.add_argument('target',type=Path);a=p.parse_args()
    assert not (a.target/'report.json').exists(),'Never overwrite an immutable journey report'
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    source=json.loads((a.explorer/'report.json').read_text())
    for group in ('inputs','binaries'):
        for name,value in source['build_manifest'][group].items():assert sha(ROOT/name)==value,('stale exploration build',name)
    for name,value in source['source_sha256'].items():assert sha(ROOT/name)==value,('stale exploration source',name)
    for name,value in source['evidence_sha256'].items():assert sha(a.explorer/name)==value
    reference=list(struct.iter_unpack('<i40I',(a.explorer/'states.bin').read_bytes()))
    rows=[line.split() for line in (a.target/'player-target-trace.txt').read_text().splitlines()]
    assert len(rows)==len(reference)==source['updates']
    for n,(row,ref) in enumerate(zip(rows,reference),1):
        assert not ref[0] and int(row[0])==n and int(row[1])==ref[38]
        assert list(map(lambda x:int(x,16),row[2:]))==list(ref[1:17]),('target/native state',n)
    log=(a.target/'results.log').read_text()
    m=re.search(r'Journey matched: states=(\d+) words=(\d+) frames=(\d+) warps=(\d+) arrivals=(\d+) era=(\d+) good=(\d+) act=(\d+)',log)
    assert m
    states,words,frames,warps,arrivals,era,good,act=map(int,m.groups())
    assert states==len(rows) and words==states*16 and era==source['final']['era'] and good==source['final']['good_future'] and act+1==source['final']['act']
    assert warps==sum(e['destination']>=0 for e in source['events'])
    progression=re.search(r'Journey progression: samples=(\d+) fields=6 generators=(\d+) good_flags=(\d+)',log)
    assert progression
    samples,generators,good_flags=map(int,progression.groups())
    assert samples==states and generators==sum(bool(e['generator']) for e in source['events']) and good_flags==source['final']['good_flags']
    timing=re.search(r'Journey pacing: intervals=(\d+) late=(\d+) max_gap=(\d+)',log);assert timing
    intervals,late,max_gap=map(int,timing.groups())
    expected_intervals=sum(a[17:19]==b[17:19] for a,b in zip(reference,reference[1:]))
    assert intervals==expected_intervals
    ticks=[tuple(map(int,m)) for m in re.findall(r'^Journey timing: row=(\d+) vblank=(\d+) act=(\d+) era=(\d+)$',log,re.M)]
    assert len(ticks)==states
    gaps=[];measured=0;peak=0;previous=None
    for n,(tick,ref) in enumerate(zip(ticks,reference),1):
        assert tick[0]==n and tick[2:]==ref[17:19]
        if previous:
            delta=tick[1]-previous[1];assert delta>0
            if tick[2:]==previous[2:]:
                measured+=1;peak=max(peak,delta)
                if delta>1:gaps.append(dict(row=n,vblanks=delta,act=tick[2]+1,era=tick[3],x=ref[1]/65536,y=ref[2]/65536,objects=ref[13]>>16))
        previous=tick
    assert (measured,len(gaps),peak)==(intervals,late,max_gap)
    zone_exit=None
    if source['zone_results_complete']:
        exit_match=re.search(r'Journey zone exit: next_zone=1 next_act=1 boss_fight=(\d+) boss_defeated=(\d+) capsule=(\d+)',log);assert exit_match
        fight,defeated,capsule=map(int,exit_match.groups());assert 0<fight<defeated<capsule<=states
        zone_exit=dict(next_zone=1,next_act=1,boss_fight=fight,boss_defeated=defeated,capsule=capsule)
    special_return=None
    if os.getenv('SCD_JOURNEY_SPECIAL'):
        assert source['final']['act']==2 and source['final']['era']==1 and source['final']['rings']>=50
        match=re.search(r'Journey special return: touch=(\d+) stage=(\d+) results=(\d+) zone=0 act=3 era=2 stones=1 good_flags=3 score=(\d+) lives=(\d+) rings=(\d+)',log);assert match
        touch,stage,results,score,lives,rings=map(int,match.groups())
        assert 0<touch<stage<results and score>=source['final']['score'] and lives==source['final']['lives'] and rings==0
        special_return=dict(touch=touch,stage=stage,results=results,zone=0,act=3,era=2,stones=1,good_flags=3,score=score,lives=lives,rings=rings)
    intro_rows=[tuple(map(int,m)) for m in re.findall(
        r'^Journey intro: row=(\d+) act=(\d+) tick=(\d+) elapsed=(\d+) pad=(\d+) score=(\d+) rings=(\d+) lives=(\d+) era=(\d+)$',log,re.M)]
    intro_pictures={}
    for intro_act in sorted({r[1] for r in intro_rows}):
        entry=[r for r in intro_rows if r[1]==intro_act]
        assert [r[2] for r in entry]==list(range(1,len(entry)+1))
        assert len(entry)==min(191,states-entry[0][0]+1)
        for row,act_index,tick,elapsed,pad,score,rings,lives,intro_era in entry:
            unlock=130+native_wait(0,act_index,intro_era)  # src/title_card.c PLC 2 wait
            assert elapsed==max(0,tick-unlock),('title clock',row,tick,elapsed)
            if tick<=unlock:assert not pad,('title input',row,pad)
        for tick in (120,131,191):
            if len(entry)<tick:continue
            name=f'journey-intro-act{intro_act+1}-tick{tick}.ppm'
            image=(a.target/name).read_bytes();matches={}
            # VDP output may trail coherent simulation publication by one update.
            for r in entry[max(0,tick-2):tick]:
                _,_,_,elapsed,_,score,rings,lives,intro_era=r
                try:count=verify_hud(image,score,rings,elapsed,lives,intro_era,check_rings=bool(rings))
                except AssertionError:continue
                matches[elapsed]=count
            assert len(matches)==1,('intro HUD',name,matches)
            elapsed,count=next(iter(matches.items()))
            intro_pictures[name]=dict(elapsed=elapsed,pixels=count)
    assert len(intro_rows)==sum(min(191,states-n+1) for n,r in enumerate(reference,1) if n==1 or r[35])
    captures={}
    for path in a.target.glob('*.ppm'):
        header,data=path.read_bytes().split(b'255\n',1);assert header==b'P6\n330 224\n' and len(data)==330*224*3
        captures[path.name]=sha(path)
    report=dict(passed=True,disc_sha256=sha(ROOT/'dist/sonic-cd-saturn-prototype.bin'),states=states,words=words,frames=frames,
        warps=warps,era_changes=arrivals,era=era,good_future=good,act=act+1,final=source['final'],captures=captures,
        progression_samples=samples,progression_fields=6,generators=generators,good_flags=good_flags,
        title_intro=dict(states=len(intro_rows),held_updates=130,first_clock_update=131,pictures=intro_pictures),
        pacing=dict(intervals=intervals,late=late,max_gap=max_gap,gaps=gaps,zero_late=late==0),zone_exit=zone_exit,special_return=special_return,
        instrumented_frame_profile='Journey profile:' in log,
        build_manifest=source['build_manifest'],
        source_sha256=source['source_sha256']|{name:sha(ROOT/name) for name in ['tools/journey_replay.h','tools/check_ppz_journey.py','tools/test-ppz-journey.sh']},
        evidence_sha256={str(path):sha(path) for folder in [a.explorer,a.target] for path in folder.iterdir() if path.is_file()},
        limits='Controller-only NEW GAME route with exact shared-native/sanitized/Saturn states. No independent original gameplay or pixel equivalence, full-zone completion or hardware claim. Report final state defines coverage.')
    (a.target/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('Journey verified:',states,'states;',warps,'warps;',arrivals,'arrivals; final act',act+1,'era',era,'good',good)
if __name__=='__main__':main()
