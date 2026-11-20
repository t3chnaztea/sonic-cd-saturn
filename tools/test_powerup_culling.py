#!/usr/bin/env python3
"""Compare effect visibility at camera/wrap edges with retail DrawObject."""
import ctypes as C
import hashlib,json,random,struct,subprocess
from convert_assets import ROOT
from test_sonic_animation import Retail
from test_powerup_visual import State
from extract_mmd import disc_files
from retail_span import disc_span

def main():
    out=ROOT/'build/powerup-runtime';out.mkdir(exist_ok=True)
    program=disc_files((ROOT/'build/retail/sonic.iso').read_bytes())['R11A__.MMD']
    entry=0x203af2
    code=disc_span('R11A__.MMD',0x3af2,142,'46c3a5956af984f089fc87f058e4c04d42c23e99881955ab155a01a008df7dd1')
    assert program[entry-0x200000:entry-0x200000+len(code)]==code
    retail=Retail(entry)
    subprocess.run(['clang','-std=c11','-O2','-Wall','-Wextra','-Werror','-Isrc','-Iassets/generated',
        '-dynamiclib','src/powerup_visual.c','src/powerup_runtime.c','-o',str(out/'culling.dylib')],cwd=ROOT,check=True)
    native=C.CDLL(str(out/'culling.dylib'))
    native.scd_powerup_screen.argtypes=[C.POINTER(State),C.c_int,C.c_int,C.POINTER(C.c_int),C.POINTER(C.c_int)]
    cases=[];rng=random.Random(0x43554c4c)
    cameras=[-32768,-1,0,1,255,256,257,1791,1792,1793,2047,2048,32767]
    for cy in cameras:
        for y in [-32768,-1,0,1,223,224,255,256,1791,1792,2047,2048,2049,32767]+[cy+d for d in [-1,0,1,223,224]]:
            for dx in [-32768,-337,-17,-16,-15,0,319,320,334,335,336,337,32767]:cases.append((1024+dx,y,1024,cy))
    cases += [tuple(rng.randrange(-32768,32768) for _ in range(4)) for _ in range(10000)]
    visible=0;raw=[]
    for x,y,cx,cy in cases:
        x=C.c_int16(x).value;y=C.c_int16(y).value
        data=bytearray(64);data[0]=3;data[1]=4;data[24]=1;data[25]=16
        struct.pack_into('>h',data,8,x);struct.pack_into('>h',data,12,y)
        retail.write(retail.actor,data);retail.write(0xffac00,bytes(1024))
        retail.write(0xfff700,struct.pack('>hHhH',cx,0,cy,0));retail.write(retail.stack,struct.pack('>I',retail.halt))
        for reg,value in [(17,0x2700),(15,retail.stack),(8,retail.actor),(16,entry)]:retail.lib.m68k_set_reg(reg,value)
        retail.cpu.cycles=retail.cpu.refresh_cycles=0;retail.lib.m68k_run(10000)
        assert retail.lib.m68k_get_reg(16)==retail.halt,(len(raw),x,y,cx,cy,hex(retail.lib.m68k_get_reg(16)))
        size=struct.unpack('>H',retail.read(0xffac80,2))[0];assert size in (0,2)
        dx=C.c_int();dy=C.c_int();state=State(x=x,y=y,width=16)
        result=native.scd_powerup_screen(C.byref(state),cx,cy,C.byref(dx),C.byref(dy))
        assert result==bool(size),('retail camera culling',x,y,cx,cy,size,result,dx.value,dy.value)
        visible+=result;raw.append(struct.pack('>hhhhB',x,y,cx,cy,result))
    (out/'culling-retail-cases.bin').write_bytes(b''.join(raw))
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    report=dict(passed=True,cases=len(cases),visible=visible,retail_entry=entry,
        retail_program_sha256=hashlib.sha256(program).hexdigest(),
        source_sha256={name:sha(ROOT/name) for name in ['src/powerup_runtime.c','src/powerup_runtime.h',
            'tools/test_powerup_culling.py','tools/test_sonic_animation.py','tools/test_powerup_visual.py']},
        cases_sha256=sha(out/'culling-retail-cases.bin'),
        limits='Width-16, zero-Y-radius effect actors. Retail queue acceptance; actual target pixel positioning checked separately.')
    (out/'culling-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Power-up culling:',len(cases),'retail DrawObject calls;',visible,'visible')

if __name__=='__main__':main()
