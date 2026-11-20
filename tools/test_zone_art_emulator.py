#!/usr/bin/env python3
"""Exercise all loaded zone sprites on Saturn through the level select."""
import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

from convert_assets import ROOT
from check_zone_object_target import check


def main():
    parser=argparse.ArgumentParser();parser.add_argument('programs',nargs='*');args=parser.parse_args()
    programs=args.programs or [f'R{r}{a}{e}' for r in (3,4,5,7,8) for a in (1,2,3) for e in ('CD' if a==3 else 'ABCD')]
    exe=ROOT/'build/zoneart_test'
    subprocess.run(['clang','-std=gnu11','-Wall','-Wextra','-Werror','-I.deps/beetle-saturn/libretro-common/include',
                    'tools/emulator_test.c','-o',str(exe)],cwd=ROOT,check=True)
    symbols=subprocess.check_output([str(ROOT/'.toolchain/bin/sh-elf-nm'),
                 str(ROOT/'build/saturn/sonic-cd-saturn-prototype.elf')],text=True)
    symbols={line.split()[2]:line.split()[0] for line in symbols.splitlines() if len(line.split())==3}
    paths=['tools/test_zone_art_emulator.py','tools/emulator_test.c','tools/check_zone_object_target.py',
           'build/saturn/sonic-cd-saturn-prototype.elf','.deps/beetle-saturn/mednafen_saturn_libretro.dylib']
    report=dict(passed=False,status='pending',programs={},
                inputs={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
                disc_sha256=hashlib.sha256((ROOT/'dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest())
    parent=ROOT/'build/zone-art-qa';parent.mkdir(exist_ok=True)
    (parent/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    for name in programs:
        zone=(1,3,4,5,6,7,8).index(int(name[1]));act=int(name[2])-1;era='ABCD'.index(name[3])
        # R83C-fight/-ending: the fight and Amy banks BOSS_8.C loads (src/zone_object_view.inc 0xa8/0xa9).
        folder=parent/name;folder.mkdir(exist_ok=True)
        env=dict(os.environ,SCD_ZONE=str(zone),SCD_ZONE_ACT=str(act),SCD_ZONE_ERA=str(era),
                 SCD_WORLD_MAILBOX=symbols['_scd_world_mailbox'],SCD_ZONE_ART_MAILBOX=symbols['_scd_zone_art_mailbox'])
        if name.endswith(('-fight','-ending')):env['SCD_ZONE_ART_FIGHT']='1' if name.endswith('-fight') else '2'
        if zone==1 and act==0:
            palette=[address for symbol,address in symbols.items()
                     if symbol=='_palette_frame' or symbol.startswith('_palette_frame.lto_priv.')]
            assert len(palette)==1, ('palette frame symbol',palette)
            env['SCD_PALETTE_FRAME']=palette[0]
        command=[str(exe),str(ROOT/'.deps/beetle-saturn/mednafen_saturn_libretro.dylib'),
                 str(ROOT/'dist/sonic-cd-saturn-prototype.cue'),str(ROOT/'assets/private'),str(folder),
                 symbols['_scd_trace_mailbox'],symbols['_scd_audio_mailbox'],'zones']
        pending=dict(report,program=name,programs={})
        (folder/'report.json').write_text(json.dumps(pending,indent=2)+'\n')
        try:
            with (folder/'results.log').open('w') as stdout,(folder/'core.log').open('w') as stderr:
                subprocess.run(command,cwd=ROOT,env=env,stdout=stdout,stderr=stderr,check=True,timeout=240)
            result=check(name,folder)
            result.update(status='passed',inputs=report['inputs'],disc_sha256=report['disc_sha256'])
            (folder/'report.json').write_text(json.dumps(result,indent=2)+'\n')
            report['programs'][name]=result
        except BaseException as error:
            pending.update(status='interrupted' if isinstance(error,KeyboardInterrupt) else 'failed',
                           error=f'{type(error).__name__}: {error}')
            (folder/'report.json').write_text(json.dumps(pending,indent=2)+'\n')
            report.update(status=pending['status'],error=pending['error'],failed_program=name)
            (parent/'report.json').write_text(json.dumps(report,indent=2)+'\n')
            raise
        (parent/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(name,'PASS',flush=True)
    report.update(passed=True,status='passed');(parent/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Zone artwork target matrix passed:',len(programs),'programs')


if __name__=='__main__':main()
