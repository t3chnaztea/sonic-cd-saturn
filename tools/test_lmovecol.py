#!/usr/bin/env python3
"""Check generated lmovecol against the retail wall-check instructions.

Sonic/Main.asm ObjSonic_CheckWallCol; confirmed R73D $20483A through $2048AA.
All angles, both travel signs, stopped motion and both wall-distance signs.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
# Output volume: SCD_OUTPUT_VOLUME if set, else the mount point that holds the repo.
VOLUME = Path(os.environ.get('SCD_OUTPUT_VOLUME') or next(p for p in (ROOT, *ROOT.parents) if os.path.ismount(p)))
OUT = ROOT / 'build/lmovecol-test'


def main():
    assert os.path.ismount(VOLUME)
    assert shutil.disk_usage(VOLUME).free >= 100 * 1024**3
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'tmp').mkdir(exist_ok=True)
    env = dict(os.environ, TMPDIR=str(OUT/'tmp'))
    paths = ['tools/prepare_player.py', 'tools/test_lmovecol.py', 'src/scd_actor.h', 'build/probe-source/player.c']
    report = dict(status='pending', passed=False, inputs={p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
                  oracle='Sonic/Main.asm ObjSonic_CheckWallCol; R73D $20483A ADDI.B #64; BMI')
    target = OUT/'report.json'
    target.write_text(json.dumps(report, indent=2)+'\n')
    try:
        source = (ROOT/'build/probe-source/player.c').read_text()
        start = source.index('void lmovecol(void)')
        end = source.index('\nvoid ', start+1)
        harness = r'''
#include <stdio.h>
#include <string.h>
#include "EQU.H"
sprite_status actwk[128];
static int calls, distance;
short dircolm(sprite_status *p,char *angle){(void)p;(void)angle;calls++;return distance;}
'''+source[start:end]+r'''
int main(void){
  unsigned checks=0;
  for(unsigned a=0;a<256;a++)for(int sign=-1;sign<=1;sign++)for(int hit=0;hit<2;hit++){
    memset(actwk,0,sizeof(actwk));calls=0;distance=hit?-4:2;
    actwk[0].direc.b.h=(signed char)a;actwk[0].mspeed.w=sign*1000;
    actwk[0].xspeed.w=101;actwk[0].yspeed.w=-203;actwk[0].cddat=4;
    lmovecol();
    /* Assembly skips the ceiling half-circle, including endpoints64,191. */
    int active=sign && !(a>=64 && a<192),x=101,y=-203,ms=sign*1000,flags=4;
    if(active && hit){
      unsigned side=(a+(sign>0?-64:64)+32)&192;
      if(side==0)y-=1024;
      else if(side==128)y+=1024;
      else {x+=side==64?1024:-1024;ms=0;flags|=32;}
    }
    if(calls!=!!active || actwk[0].xspeed.w!=x || actwk[0].yspeed.w!=y || actwk[0].mspeed.w!=ms || actwk[0].cddat!=flags){
      fprintf(stderr,"FAIL angle=%u sign=%d hit=%d calls=%d x=%d y=%d speed=%d flags=%u\n",a,sign,hit,calls,actwk[0].xspeed.w,actwk[0].yspeed.w,actwk[0].mspeed.w,actwk[0].cddat);return 1;
    }
    checks++;
  }
  printf("PASS: lmovecol %u angle/direction/distance cases\n",checks);return 0;
}
'''
        (OUT/'test.c').write_text(harness)
        flags = ['-std=gnu11', '-O1', '-g', '-fsigned-char', '-fwrapv', '-fsanitize=address,undefined', '-fno-sanitize-recover=all']
        with (OUT/'build.log').open('w') as log:
            subprocess.run(['clang', *flags, '-Isrc', '-Ibuild/probe-source', OUT/'test.c', '-o', OUT/'test'], cwd=ROOT, env=env, stdout=log, stderr=log, check=True)
        result = subprocess.check_output([OUT/'test'], cwd=ROOT, env=env, text=True)
        (OUT/'result.txt').write_text(result)
        report.update(status='passed', passed=True, result=result.strip())
    except KeyboardInterrupt:
        report.update(status='interrupted')
    except Exception as exc:
        report.update(status='failed', error=str(exc))
    finally:
        target.write_text(json.dumps(report, indent=2)+'\n')
    print(('PASS: ' if report['passed'] else 'FAIL: ')+str(target))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
