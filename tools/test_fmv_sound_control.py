#!/usr/bin/env python3
"""Exercise the actual movie slot startup against write-only SCSP readbacks.

Beetle stores MEM4MB but does not use it to constrain sound RAM. This host gate
checks that movie startup always retains the required 512 KB mode, even when
the control register reads as zero or open bus. No game data is needed.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/fmv-sound-control'
OUT.mkdir(exist_ok=True)
source = (ROOT / 'src/fmv_saturn.c').read_text()
start = source.index('static void slot_start(void)')
end = source.index('\nstatic void slot_stop(void)', start)
body = source[start:end]
assert not re.search(r'SCSP_REG\(0x400\)(?!\s*=)', body), 'FMV startup reads the write-only control register'
test = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
static volatile uint16_t regs[0x1000 / 2];
#define SCSP(x) (&regs[(x) / 2])
#define SCSP_REG(x) (*SCSP(x))
#define FMV_SLOT 31u
#define FMV_RING_ADDR 0x6f000u
#define PITCH_WORD ((0xfu << 11) | 497u)
static struct { unsigned frt_last,frt_ext,blocks,ca_last,pos_last,anchor,frt_prev_poll,playing; } st;
static unsigned cpu_frt_count_get(void){return 42;}
static unsigned frt_now(void){return 43;}
''' + body + r'''
int main(void){
    const unsigned readbacks[]={0,0x00f0,0x00ff,0xffff,0x0200,0x020f};
    for(unsigned i=0;i<sizeof(readbacks)/sizeof(readbacks[0]);i++){
        SCSP_REG(0x400)=readbacks[i];
        slot_start();
        assert(SCSP_REG(0x400)==0x020f);
        assert(SCSP_REG(FMV_SLOT*32)==0x1836);
        assert(SCSP_REG(FMV_SLOT*32+22)==0xe000);
        assert(st.playing==1);
    }
    puts("PASS: FMV startup writes MEM4MB and master gain for six initial register values; no control read");
}
'''
(OUT / 'test.c').write_text(test)
report = {'status': 'pending', 'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
          'readbacks': [0, 0xf0, 0xff, 0xffff, 0x200, 0x20f], 'hardware_tested': False}
(OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', str(OUT / 'test.c'), '-o', str(OUT / 'test')], check=True)
r = subprocess.run([str(OUT / 'test')], capture_output=True, text=True)
report.update(status='passed' if r.returncode == 0 else 'failed', returncode=r.returncode)
(OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(r.stdout, end='')
if r.returncode:
    raise SystemExit(r.stderr)
