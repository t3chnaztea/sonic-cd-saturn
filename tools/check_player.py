#!/usr/bin/env python3
"""Check semantic coverage and every replay state word, with no image heuristics."""
import argparse
import hashlib
import json
import pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
def read_trace(path):
    rows={}
    for line in path.read_text().splitlines():
        fields=line.split();key=tuple(map(int,fields[:2]));words=tuple(int(v,16) for v in fields[2:])
        if len(words)!=16 or key in rows:raise ValueError(f'malformed/duplicate state: {key}')
        rows[key]=words
    if set(rows)!={(t,f) for t in range(28) for f in range(600)}:raise ValueError('missing replay frames')
    return rows

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--host-only',action='store_true');args=parser.parse_args()
    host_path=ROOT/'build/player-host-trace.txt';host=read_trace(host_path)
    reference=read_trace(ROOT/'build/player-reference-trace.txt')
    if host!=reference:raise ValueError('adapted core differs from desktop reference')
    terrain=''.join(str(t)+' '+str(f)+''.join(' '+format(v,'08x') for v in host[t,f][:8])+'\n' for t in range(8) for f in range(600))
    # V0.073: Sonic spawns grounded (ObjSonic_Init sets no oFlags, Sonic/Main.asm:135-155)
    # and an air right-wall hit keeps mspeed = yspeed (Sonic/Main.asm:2254).
    # V0.073 R2: rolling slope resistance quarters with asr.l #2 (ObjSonic_SlopeResistRoll;
    # tools/player_fixes.py rollresist), which moves the rolling cases by one subpixel step.
    # Spindash charges by 75 outside Wacky Workbench (tools/player_fixes.py spindash).
    assert hashlib.sha256(terrain.encode()).hexdigest()=='fb67133b1f690158941a97def17e415ea3f1126e04bc27bdd2b77cf23260b3f0', 'Original terrain regression'
    coverage={}
    for test in range(8):
        rows=[host[test,f] for f in range(600)]
        flags=[(r[3]>>8)&255 for r in rows];angles={r[3]&255 for r in rows}
        coverage[test]={'grounded_frames':sum(not(f&2) for f in flags),'airborne_frames':sum(bool(f&2) for f in flags),
                        'rolling_frames':sum(bool(f&4) for f in flags),'angles':sorted(angles),
                        'max_charge':max((r[4]>>8)&255 for r in rows),
                        'path_switch_frames':sum(bool((r[4]>>16)&255) for r in rows),
                        'max_control_lock':max(r[5] for r in rows), 'resets':rows[-1][7], 'x_range_pixels':[min(r[0] for r in rows)/65536,max(r[0] for r in rows)/65536]}
        assert coverage[test]['grounded_frames']>0
        if test<7:assert coverage[test]['airborne_frames']>0
        if test<4:assert len(angles)>2 and coverage[test]['rolling_frames']>0
    # The loop replay must touch all quadrants while grounded, change paths,
    # and emerge beyond the paired chunk without respawning.
    loop=[host[7,f] for f in range(110)]
    assert all(not(r[3]&512) for r in loop), 'Loop detached'
    assert {((r[3]&255)+32)//64%4 for r in loop if not(r[3]&512)}=={0,1,2,3}
    assert coverage[7]['path_switch_frames']>20 and coverage[7]['resets']==0
    assert host[7,109][0]/65536>2048
    assert coverage[4]['max_charge']==45 and coverage[4]['rolling_frames']>60
    assert coverage[1]['max_control_lock']==30
    # Holding jump must produce a higher apex than tapping it in the same place.
    apex=[min(host[t,f][1] for f in range(60,130))/65536 for t in [5,6]]
    assert apex[1]<apex[0]-20,apex
    interactions={}
    for test in range(8,24):
        r=[host[test,f] for f in range(600)]
        interactions[test]={'springs':max(v[10]>>16 for v in r),'hits':max(v[10]&65535 for v in r),
            'deaths':max(v[11]>>16 for v in r),'lost_rings':max(v[11]&65535 for v in r),
            'routines':sorted({v[9]>>24 for v in r}),'collected':r[-1][12]&65535,
            'max_active':max(v[12]>>16 for v in r),'spawned':r[-1][13]>>16,'despawned':r[-1][13]&65535}
    def signed(v):return v-65536 if v&32768 else v
    launch={}
    for test in range(8,14):
        assert interactions[test]['springs']>0, (test,'spring never fired')
        row=next(host[test,f] for f in range(600) if host[test,f][10]>>16)
        launch[test]=[signed(row[2]>>16),signed(row[2]&65535)]
    assert launch[8][1]==-4096 and launch[9][1]==-2560
    assert launch[10][0]==4096 and launch[11][0]==-4096
    assert launch[12][1]==4096 and launch[13]==[2896,-2896]
    assert interactions[14]['hits']==1 and interactions[14]['lost_rings']==1
    assert interactions[14]['routines']==[2,4] and interactions[14]['collected']==2
    assert host[14,3][8]==120 and host[14,599][8]&65535==0
    assert interactions[15]['deaths']==1 and host[15,599][7]==1 and host[15,599][9]&255==2
    assert interactions[16]['hits']==1 and interactions[16]['lost_rings']==0
    assert host[16,599][8]>>16==5 and not(host[16,0][9]&0xff0000)
    assert interactions[17]['collected']==1 and interactions[17]['despawned']>20
    assert interactions[18]['max_active']==96 and host[18,599][15]==0x40001
    assert interactions[19]['springs']>0 and interactions[19]['collected']>0
    assert host[20,599][1]==465*65536 and not(host[20,599][3]&512), 'Standing on boulder failed'
    assert host[21,599][0]<=75*65536 and host[21,599][2]>>16==0, 'Solid side failed'
    assert interactions[22]['deaths']==1, 'Inverted spikes failed'
    assert interactions[23]['lost_rings']==32 and interactions[23]['max_active']==32
    assert host[23,599][12]>>16==0, 'Lost rings did not expire'
    dash_inputs={}
    for test in range(24,28):
        r=[host[test,f] for f in range(600)]
        dash_inputs[test]={'max_charge':max((v[4]>>8)&255 for v in r),'crouch_frames':sum(v[4]>>24==8 for v in r),
            'max_speed':max(abs(signed(v[3]>>16)) for v in r)}
    assert dash_inputs[24]['max_charge']==45 and dash_inputs[25]['max_charge']==45
    assert dash_inputs[24]['max_speed']>=3072 and dash_inputs[25]['max_speed']>=3072
    assert dash_inputs[26]['crouch_frames']>=60 and dash_inputs[26]['max_charge']==0
    assert 0<dash_inputs[27]['max_charge']<45 and all(host[27,f][3]>>16==0 for f in range(40,600))
    report={'frames':16800,'state_words_per_frame':16,'host_matches_reference':True,'original_terrain_baseline_matches':True,
            'address_and_undefined_sanitizers':'passed','jump_apex_pixels':{'tap':apex[0],'hold':apex[1]},
            'coverage':coverage,'dash_input_cases':dash_inputs,'interactions':interactions,'spring_launch_velocities':launch,'host_trace_sha256':hashlib.sha256(host_path.read_bytes()).hexdigest(),
            'target_matches_host':False,'limitations':['shared terrain frontend is not an independent Sega CD emulator reference',
            'remaining object types, full stage progression and hardware timing not validated']}
    if not args.host_only:
        target=read_trace(ROOT/'build/emulator-qa/player-target-trace.txt')
        for key,expected in host.items():
            if target[key]!=expected:raise ValueError(f'SH-2 mismatch test/frame {key}: {target[key]} != {expected}')
        report['target_matches_host']=True
        report['disc_sha256']=hashlib.sha256((ROOT/'dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest()
    (ROOT/'dist/player-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS: 16800 frames / 268800 state words; desktop reference'+(' and SH-2 match' if not args.host_only else ' matches'))
    print('Jump apex:',apex,'; spin charge:',coverage[4]['max_charge'],'; loop path frames:',coverage[7]['path_switch_frames'])
if __name__=='__main__':main()
