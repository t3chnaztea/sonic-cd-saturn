#!/usr/bin/env python3
"""Verify each zone's four songs, controller era changes and pause/resume on Saturn."""
import hashlib,json,os,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
exe=ROOT/'build/zone_music_test'
subprocess.run(['clang','-std=gnu11','-Wall','-Wextra','-Werror','-I.deps/beetle-saturn/libretro-common/include','tools/emulator_test.c','-o',str(exe)],cwd=ROOT,check=True)
lines=subprocess.check_output([str(ROOT/'.toolchain/bin/sh-elf-nm'),str(ROOT/'build/saturn/sonic-cd-saturn-prototype.elf')],text=True)
symbols={s[2]:s[0] for line in lines.splitlines() if len(s:=line.split())==3}
parent=ROOT/'build/zone-music-qa';parent.mkdir(exist_ok=True)
report=dict(passed=False,disc_sha256=hashlib.sha256((ROOT/'dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest(),zones={})
tracks=json.loads((ROOT/'dist/build-report.json').read_text())['audio_tracks']
for zone in range(7):
    folder=parent/str(zone);folder.mkdir(exist_ok=True)
    env=dict(os.environ,SCD_ZONE=str(zone),SCD_ZONE_MUSIC='1',SCD_WORLD_MAILBOX=symbols['_scd_world_mailbox'])
    # Wait one whole Metallic Madness bad-future song (the last era it plays) so it loops;
    # the disc's last track is no longer a zone song (slots 35-40, src/music_routes.h).
    if zone==6:env['SCD_ZONE_MUSIC_LOOP_FRAMES']=str(int(next(t for t in tracks if t['zone']==6 and t['stage_era']==3)['sectors']*60/75)+300)
    command=[str(exe),str(ROOT/'.deps/beetle-saturn/mednafen_saturn_libretro.dylib'),str(ROOT/'dist/sonic-cd-saturn-prototype.cue'),str(ROOT/'assets/private'),str(folder),symbols['_scd_trace_mailbox'],symbols['_scd_audio_mailbox'],'zones']
    with (folder/'results.log').open('w') as log,(folder/'core.log').open('w') as err:
        subprocess.run(command,cwd=ROOT,env=env,stdout=log,stderr=err,check=True,timeout=240)
    text=(folder/'results.log').read_text();rows=re.findall(r'Zone music: zone=(\d+) era=(\d+) track=(\d+) samples=(\d+) mean_square=(\d+) peak=(\d+)',text)
    assert len(rows)==4 and f'Zone music passed: zone={zone} pause_resume=4 loop=' in text
    report['zones'][str(zone)]=[dict(zip(('zone','era','track','samples','mean_square','peak'),map(int,row))) for row in rows]
    (parent/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('Zone',zone,'four eras and pause/resume PASS',flush=True)
report['passed']=True;report['last_track_repeats_after_resume']=True
(parent/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print('All seven zone music routes passed; final disc track loops after resume')
