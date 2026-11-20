#!/usr/bin/env python3
"""Audit final QQ ring-loss frames and repeat cold boots of earned checkpoints.

Run under power_guard.py after required candidate gates/local packaging.
Every cold boot uses a fresh emulator process and must preserve backup bytes.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess

from power_guard import ROOT, inputs, on_ac
from test_qq_route import records, sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--cold-repeats',type=int,default=3)
    parser.add_argument('--rings-only',action='store_true')
    args=parser.parse_args()
    assert 1<=args.cold_repeats<=10
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    disc=sha(ROOT/'dist/sonic-cd-saturn-prototype.bin')
    report=dict(passed=False,status='pending',hardware_tested=False,disc_sha256=disc,
                input_sha256=inputs(),ring_loss={},cold_boots=[],checkpoint_reports={})
    def save(): (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        acceptance=ROOT/'dist/qq-acceptance.json'
        a=json.loads(acceptance.read_text())
        assert a['passed'] and a['disc_sha256']==disc, 'required candidate gates must pass first'
        report['acceptance_sha256']=sha(acceptance)
        for era in 'CD':
            folder=ROOT/f'build/qq3/controller/{era}'
            route=json.loads((folder/'report.json').read_text())
            assert route['passed'] and route['disc_sha256']==disc
            assert route['matched_positions']==route['positions']>0 and route['respawns']==0
            assert not route['late_gameplay_intervals']
            text=(folder/'results.log').read_text()
            results=records(text,'CC results')
            rows={r[0]:r for r in records(text,'CC route')}
            drops=[]
            for before,after in zip(results,results[1:]):
                if after[0]!=before[0]+1 or before[1]!=0 or after[1]!=0 or after[3]>=before[3]:continue
                left,right=rows[before[0]],rows[after[0]]
                if left[9:]!=right[9:]:continue
                assert right[1]-left[1]==1, 'late ring-loss update'
                drops.append(dict(sequence=after[0],lost=before[3]-after[3],remaining=after[3]))
            assert drops and max(d['lost'] for d in drops)>=32, ('missing large gameplay ring loss',era,drops)
            report['ring_loss'][era]=dict(drops=drops,results_sha256=sha(folder/'results.log'),
                                         route_report_sha256=sha(folder/'report.json'))
            save()
        if not args.rings_only:
            assert on_ac(), 'cold emulator boots require AC power and an external power guard'
            for name,era,checkpoint in [('tt3','D',0x000003),('qq1','A',0x000103),
                                        ('qq2','A',0x030203),('qq3','D',0x000004)]:
                folder=ROOT/f'build/{name}/controller/continue/{era}'
                route=json.loads((folder/'report.json').read_text())
                assert route['passed'] and route['disc_sha256']==disc
                source=folder/'backup-after.bin'
                source_sha=sha(source);assert source_sha==route['backup_after_sha256']
                state=route['save_after']
                packed,flags,generation=state[4],state[5],state[3]
                assert packed&0xffffff==checkpoint, ('wrong earned checkpoint',name,packed)
                report['checkpoint_reports'][name]=dict(path=str(folder/'report.json'),sha256=sha(folder/'report.json'),backup_sha256=source_sha)
                for repeat in range(args.cold_repeats):
                    assert on_ac(), 'AC unavailable before cold boot'
                    target=out/f'{name}-{repeat+1}';target.mkdir()
                    case=dict(checkpoint=name,repeat=repeat+1,status='pending',passed=False)
                    report['cold_boots'].append(case);save()
                    env={k:v for k,v in os.environ.items() if not k.startswith('SCD_')}
                    env.update(SCD_BACKUP_INPUT=str(source),SCD_SAVE_OUTPUT_DIR=str(target))
                    with (target/'command.log').open('w') as log:
                        result=subprocess.run(['bash','tools/test-save-emulator.sh','continue'],cwd=ROOT,env=env,
                                              stdout=log,stderr=subprocess.STDOUT,timeout=180)
                    case['exit_code']=result.returncode
                    assert result.returncode==0, (name,repeat,target/'command.log')
                    result=json.loads((target/'save.json').read_text());mb=result['mailbox'];trace=result['trace']
                    assert mb[:10]==[0x53415645,0,1,0,generation,packed,flags,packed,flags&0xffff,1], (name,mb)
                    assert sha(target/'backup.bin')==source_sha==sha(source), 'cold boot changed backup RAM'
                    zone,era_index=packed&255,packed>>16&255
                    track=12+(zone-1)*4+era_index
                    assert trace[23]&0xfff==0x300|track, 'wrong Japanese checkpoint track'
                    assert trace[11]==0 and trace[12]>>16==0 and trace[13]&255==3, 'bad fresh player state'
                    case.update(passed=True,status='passed',save_json_sha256=sha(target/'save.json'),backup_sha256=source_sha)
                    save();print(f'PASS: cold {name} checkpoint, repeat {repeat+1}',flush=True)
        assert sha(ROOT/'dist/sonic-cd-saturn-prototype.bin')==disc
        report.update(passed=True,status='passed',scope='Two large QQ3 gameplay ring losses; earned cold checkpoints' if not args.rings_only else 'QQ3 ring-loss evidence only; cold boots not run')
        save();print(f'PASS: QQ stress: 2 large ring-loss routes, {len(report["cold_boots"])} cold boots')
    except BaseException as error:
        report.update(status='interrupted' if isinstance(error,KeyboardInterrupt) else 'failed',error=repr(error))
        for case in report['cold_boots']:
            if case['status']=='pending':case['status']=report['status']
        save();raise


if __name__=='__main__':main()
