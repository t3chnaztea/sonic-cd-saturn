#!/usr/bin/env python3
"""Bind original checkpoint protection, old-code failure and target countdown."""
import hashlib,json,re,tarfile
from convert_assets import ROOT

def main():
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    evidence={}
    def retain(path):evidence[str(path.relative_to(ROOT))]=sha(path)
    baseline=ROOT/'build/hardware-candidate-v0.053-01/candidate-manifest.json'
    manifest=json.loads(baseline.read_text());retain(baseline)
    archive=ROOT/'build/visual-source-v0.053-01.tar.gz';retain(archive)
    with tarfile.open(archive) as tar:old_player=tar.extractfile('src/player.c').read()
    assert hashlib.sha256(old_player).hexdigest()==manifest['source_sha256']['src/player.c']
    folder=ROOT/'build/player-checkpoint'
    old=json.loads((folder/'v053-original-report.json').read_text())
    current=json.loads((folder/'current-report.json').read_text())
    assert not old['passed'] and old['cases']==259 and old['mismatches']==255
    assert current['passed'] and current['cases']==259 and current['protected_updates']==30600
    assert old['source_sha256']['build/player-checkpoint/v053-source/src/player.c']==manifest['source_sha256']['src/player.c']
    for label,proof in [('v053-original',old),('current',current)]:
        for path,expected in proof['source_sha256'].items():assert sha(ROOT/path)==expected,('stale checkpoint proof',path)
        assert sha(folder/(label+'.log'))==proof['log_sha256']
        assert sha(ROOT/'.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib')==proof['core_sha256']
        retain(folder/(label+'-report.json'));retain(folder/(label+'.log'))
    path=ROOT/'build/world-qa/results.log';retain(path);log=path.read_text();states={}
    for line in re.findall(r'^Checkpoint state: ((?:\d+ ?)+)$',log,re.M):
        values=list(map(int,line.split()));assert len(values)==36
        frame,resets=values[:2];state=values[2:18];sonic=values[18:]
        assert sonic[0]==0x534f4e56 and sonic[2]==state[6] and sonic[5:7]==state[:2]
        assert resets==state[7]
        key=state[6]
        if key in states:assert states[key][1:]==(state,sonic),('inconsistent target snapshot',key)
        states[key]=(frame,state,sonic)
    assert len(states)>=800,('missing target route states',len(states))
    respawn=min(key for key,(_,s,_) in states.items() if s[7]==1)
    before=states[respawn-1][1];assert before[9]>>24==8 and not before[7]
    hidden=0
    for tick in range(121):
        frame,state,sonic=states[respawn+tick]
        assert state[7]==1 and state[9]>>24==2 and (state[9]&255)==2
        assert state[8]&65535==120-tick,('target checkpoint countdown',tick,state[8])
        expected=0 if not tick else int(not((121-tick)&4))
        assert sonic[13]==expected,('target checkpoint visibility',tick,sonic[13],expected)
        hidden+=expected
    assert hidden==60
    unchanged={}
    for name,path in [('main','emulator-qa/player-target-trace.txt'),('act1','sequence-qa/player-target-trace.txt'),
            ('act2','sequence-qa/act2-target-trace.txt'),('act3','sequence-qa/act3-target-trace.txt')]:
        old_path=ROOT/'build/pre-v054-qa'/path;new_path=ROOT/'build'/path
        a=[line.split() for line in old_path.read_text().splitlines()];b=[line.split() for line in new_path.read_text().splitlines()]
        assert len(a)==len(b)>0
        assert all((x if name=='main' else x[1:])==(y if name=='main' else y[1:]) for x,y in zip(a,b)),('unrelated gameplay drift',name)
        unchanged[name]=len(a);retain(old_path);retain(new_path)
    assert sum(unchanged.values())==32916
    report=dict(passed=True,disc_sha256=sha(ROOT/'dist/sonic-cd-saturn-prototype.bin'),
        rejected_v053_checkpoints=255,host_cases=259,host_protected_updates=30600,
        target_route_states=len(states),target_countdown_states=121,target_hidden_states=hidden,
        respawn_simulation_frame=respawn,respawn_capture_frame=states[respawn][0],
        exact_unrelated_gameplay_states=unchanged,
        source_sha256={name:sha(ROOT/name) for name in ['src/player.c','src/scd_player.h','src/main.c','src/world_qa.c',
            'tools/check_checkpoint_regression.py','tools/player_checkpoint_test.c','tools/test_player_checkpoint.py','tools/emulator_test.c']},
        evidence_sha256=evidence,
        limits='Original saved-spawn protection and complete actual Saturn target countdown/render decisions. Not hidden-background pixel proof, checkpoint clock/camera equivalence or physical-console acceptance.')
    (ROOT/'dist/checkpoint-regression-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Checkpoint regression: 255 old-code failures; 30,600 protected host updates;',len(states),'target route states; 121 complete countdown states')

if __name__=='__main__':main()
