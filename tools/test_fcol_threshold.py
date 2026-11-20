#!/usr/bin/env python3
"""Exercise generated floor/wall/ceiling penetration boundaries.

Retail R72D $200C8E/$200DBE/$200E60/$200F02 compare #-14 then BLT.
Collision Floor.asm also permits positive distances through 14, or further
when the player stick flag is set. Sensors here supply exact distances.
"""
from pathlib import Path
import os
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
out = ROOT / 'build/fcol-threshold'
out.mkdir(parents=True, exist_ok=True)
source = Path('build/probe-source/fcol.c').read_text()
bodies = []
for name in ('fcol_d', 'fcol_r', 'fcol_u', 'fcol_l'):
    start = re.search(r'short ' + name + r'\(sprite_status\* pActwk\)\s*\{', source)
    assert start, name
    depth, end = 1, start.end()
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    bodies.append(source[start.start():end])
driver = r'''
#include "EQU.H"
#include <stdio.h>
#include <string.h>
char dirstk[4];
static short distance;
short dirchk(sprite_status *p,short a,short b){(void)p;(void)b;return a;}
short scdchk(sprite_status*p,short x,short y,short o,short m,short r,char*d){
 (void)p;(void)x;(void)y;(void)o;(void)m;(void)r;(void)d;return distance;
}
#define scdchk_r scdchk
'''
driver += '\n'.join(bodies)
driver += r'''
int main(void){
 short (*f[4])(sprite_status*)={fcol_d,fcol_r,fcol_u,fcol_l};
 short ds[]={-16,-15,-14,-13,-1,0,1,13,14,15,16};unsigned checks=0;
 for(unsigned side=0;side<4;side++)for(unsigned stick=0;stick<2;stick++)
 for(unsigned n=0;n<sizeof(ds)/sizeof(*ds);n++){
  sprite_status p;memset(&p,0,sizeof(p));p.xposi.w.h=p.yposi.w.h=500;
  p.sprhs=9;p.sprvsize=19;p.actfree[14]=stick;distance=ds[n];
  int move=distance>=-14 && (distance<=14 || stick)?distance:0;
  int expected=500+(side<2?move:-move);f[side](&p);
  int actual=side&1?p.xposi.w.h:p.yposi.w.h;
  int airborne=distance>14 && !stick;
  if(actual!=expected || !!(p.cddat&2)!=airborne){
   fprintf(stderr,"FAIL: surface%u stick%u distance%d position%d expected%d\n",side,stick,distance,actual,expected);return 1;
  }checks++;
 }
 printf("PASS: retail floor/wall/ceiling penetration boundaries %u cases\n",checks);return 0;
}
'''
(out / 'test.c').write_text(driver)
inputs = ['tools/prepare_player.py', 'tools/test_fcol_threshold.py', 'build/probe-source/fcol.c']
report = dict(status='pending', passed=False, inputs={p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in inputs})
report_path = out / 'report.json'
report_path.write_text(json.dumps(report, indent=2) + '\n')
try:
    subprocess.run(['clang', '-std=gnu11', '-O1', '-fsigned-char', '-fwrapv',
                    '-Ibuild/probe-source', '-fsanitize=address,undefined',
                    '-fno-sanitize-recover=all', str(out / 'test.c'), '-o', str(out / 'test')], check=True)
    result = subprocess.check_output([str(out / 'test')], text=True)
    report.update(status='passed', passed=True, result=result.strip())
    print(result, end='')
except BaseException as error:
    report.update(status='failed', error=str(error))
    raise
finally:
    report_path.write_text(json.dumps(report, indent=2) + '\n')
