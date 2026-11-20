#!/usr/bin/env python3
"""Bind source arrival correction, old-code rejection and target hurt flashing."""
import hashlib,json,re,tarfile
from convert_assets import ROOT

def main():
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    evidence={}
    def retain(path):evidence[str(path.relative_to(ROOT))]=sha(path)
    baseline=ROOT/'build/hardware-candidate-v0.052-01/candidate-manifest.json'
    manifest=json.loads(baseline.read_text());retain(baseline)
    archive=ROOT/'build/visual-source-v0.052-01.tar.gz';retain(archive)
    with tarfile.open(archive) as tar:
        old_main=tar.extractfile('src/main.c').read();old_player=tar.extractfile('src/player.c').read()
    assert hashlib.sha256(old_main).hexdigest()==manifest['source_sha256']['src/main.c']
    assert hashlib.sha256(old_player).hexdigest()==manifest['source_sha256']['src/player.c']
    assert b'(player.routine==2 && player.hurt && (player.frame&4))' in old_main
    folder=ROOT/'build/player-arrival'
    old=json.loads((folder/'v052-original-report.json').read_text())
    current=json.loads((folder/'current-report.json').read_text())
    assert not old['passed'] and old['cases']==old['mismatches']==2048
    assert current['passed'] and current['cases']==2048 and current['display_cases']==2080 and not current['mismatches']
    assert old['source_sha256']['build/player-arrival/v052-source/src/player.c']==manifest['source_sha256']['src/player.c']
    for label,proof in [('v052-original',old),('current',current)]:
        for path,expected in proof['source_sha256'].items():assert sha(ROOT/path)==expected,('stale arrival proof',path)
        assert sha(folder/(label+'.log'))==proof['log_sha256']
        retain(folder/(label+'-report.json'));retain(folder/(label+'.log'))
    folder=ROOT/'build/emulator-qa';log=(folder/'results.log').read_text()
    rows={tuple(map(int,line.split()[:2])):list(map(lambda x:int(x,16),line.split()[2:]))
        for line in (folder/'player-target-trace.txt').read_text().splitlines()}
    visual={tuple(map(int,line.split()[:2])):[int(n,16) for n in line.split()[2:]]
        for line in (folder/'player-visual-trace.txt').read_text().splitlines()}
    seen=set();protected={16:set(),23:set()};hidden=0;old_flash_rejected=0;landings=0
    for line in re.findall(r'^Sonic display: ((?:\d+ ?)+)$',log,re.M):
        s=list(map(int,line.split()));assert len(s)==18 and s[0]==0x534f4e56
        test,step=s[16],s[2]-1;key=(test,step);assert test in (16,23) and key not in seen;seen.add(key)
        state=rows[key];pose=visual[key]
        assert s[5:7]==state[:2] and s[2]==state[6] and s[3]==pose[0]>>24
        assert s[4]==(pose[0]>>16)&255 and s[17]==(((state[4]>>16)&255)<<16)|((state[3]>>8)&255)
        control=(pose[1]>>8)&255;assert not control,'fixtures unexpectedly acquired object ownership'
        routine=state[9]>>24;hurt=state[8]&65535
        before=rows[test,step-1] if step else None
        if before and before[9]>>24==2:
            incoming=before[8]&65535
            expected=int(bool(incoming and not(incoming&4)))
            if incoming:
                protected[test].add(incoming)
                assert hurt==incoming-1,('target hurt countdown',key,incoming,hurt)
        elif before and before[9]>>24==8:expected=1
        else:
            expected=0 # Hurt/dead have a direct DrawObject call, without flashing.
            if before and before[9]>>24==4 and routine==2:
                assert hurt==120;landings+=1
        assert s[13]==expected,('target original display decision',key,hurt,s[13],expected)
        legacy=int(bool(routine==2 and hurt and s[2]&4))
        old_flash_rejected+=legacy!=expected;hidden+=s[13]
    assert seen=={(test,n) for test in (16,23) for n in range(600)},('missing target display states',len(seen))
    assert all(values==set(range(1,121)) for values in protected.values()) and landings==2
    assert hidden>0 and old_flash_rejected>50,(hidden,old_flash_rejected)
    for name in ['results.log','player-target-trace.txt','player-visual-trace.txt']:retain(folder/name)
    unchanged={}
    for name,path in [('main','emulator-qa/player-target-trace.txt'),('act1','sequence-qa/player-target-trace.txt'),
            ('act2','sequence-qa/act2-target-trace.txt'),('act3','sequence-qa/act3-target-trace.txt')]:
        old_path=ROOT/'build/pre-v053-qa'/path;new_path=ROOT/'build'/path
        a=[line.split() for line in old_path.read_text().splitlines()];b=[line.split() for line in new_path.read_text().splitlines()]
        assert len(a)==len(b)>0
        assert all((x if name=='main' else x[1:])==(y if name=='main' else y[1:]) for x,y in zip(a,b)),('unrelated gameplay drift',name)
        unchanged[name]=len(a);retain(old_path);retain(new_path)
    assert sum(unchanged.values())==32916
    report=dict(passed=True,disc_sha256=sha(ROOT/'dist/sonic-cd-saturn-prototype.bin'),
        rejected_v052_arrivals=2048,target_display_states=len(seen),target_hidden_states=hidden,
        rejected_v052_flash_decisions=old_flash_rejected,full_protection_countdowns=2,
        exact_unrelated_gameplay_states=unchanged,evidence_sha256=evidence,
        source_sha256={name:sha(ROOT/name) for name in ['src/player.c','src/scd_player.h','src/main.c','src/world_qa.c',
            'tools/check_arrival_regression.py','tools/player_arrival_test.c','tools/test_player_arrival.py','tools/emulator_test.c']},
        limits='Actual target renderer visibility decisions for two hurt/landing routes, not independent hidden-frame background pixels. Isolated original arrival state, not original travel save-frame/camera/terrain-relocation equivalence or hardware.')
    (ROOT/'dist/arrival-regression-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Arrival regression:',report['rejected_v052_arrivals'],'old-code failures;',len(seen),'target visibility states;',old_flash_rejected,'old flash decisions rejected;',sum(unchanged.values()),'unchanged unrelated gameplay states')

if __name__=='__main__':main()
