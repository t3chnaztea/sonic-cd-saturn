#!/usr/bin/env python3
"""Run the retail Special Stage 8 credits (SPEEND.MMD, IPX.asm SoundTest_SpecStg8 after a
win: RunMMD(SCMD_SS8CREDS)) in the pinned Sega CD core and record every frame.

QA oracle only. Like tools/special_retail.py, the IPX Backup RAM call jumps to an
injected command sequence; Start is held from frame <start> of the program (default
360). Writes build/special-retail/ss8-credits.jsonl (frame, pixel CRC, CRAM) and a PNG
of program frame 200 (faded in).
"""
import json,struct,sys,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import special_retail as sr

def main():
    start=int(sys.argv[1]) if len(sys.argv)>1 else 360
    r=sr.Retail()  # Patches and labels for the IPX entry; the injection is replaced below.
    ipx=(sr.RETAIL/'IPX___.MMD').read_bytes();origin=struct.unpack_from('>I',ipx,2)[0];code=ipx[0x100:0x1100]
    run_mmd,_=sr.find(code,'2f0833c000a12010',origin)
    (bram_at,bram_old,bram_new),(demo_at,demo_old,_)=r.patch
    inject=struct.pack('>HH',0x303c,r.scmd['SCMD_SS8CREDS'])+struct.pack('>HI',0x4eb9,run_mmd)+bytes.fromhex('60fe')
    patch=[(bram_at,bram_old,bram_new),(demo_at,demo_old,inject)];halt=demo_at+len(inject)-2
    core=r.core;rows=[];patched=False;begun=None;halted=0;frame=0
    while frame<6000 and halted<30:
        core.pad=0x80 if begun is not None and frame-begun>=start else 0
        core.run();frame+=1
        if not patched and all(core.work_read(at,len(old))==old for at,old,_ in patch):
            for at,_,new in patch:core.work_write(at,new)
            patched=True
        pc=core.lib.m68k_get_reg(16)
        if patched and begun is None and 0xff2000<=pc<0xffb000:begun=frame
        if begun is None:continue
        width,height,pixels=core.frame or (0,0,b'')
        cram=[(v>>6&7)<<9|(v>>3&7)<<5|(v&7)<<1 for v in struct.unpack('<64H',sr.C.string_at(core.cram,128))]
        rows.append({'frame':frame-begun,'width':width,'height':height,'pixels':'%08x'%zlib.crc32(pixels),'cram':'%08x'%zlib.crc32(struct.pack('>64H',*cram)),'pad':core.pad,'pc':pc})
        if frame-begun==200 and core.frame:sr.png(sr.OUT/'ss8-credits-200.png',core.frame)
        halted=halted+1 if pc==halt else 0
    assert halted>=30,('credits did not return',frame,hex(pc))
    sr.OUT.mkdir(parents=True,exist_ok=True)
    (sr.OUT/'ss8-credits.jsonl').write_text(''.join(json.dumps(x,separators=(',',':'))+'\n' for x in rows))
    shown=[x['pixels'] for x in rows if x['width']==320]
    steady=max(set(shown),key=shown.count)
    print(json.dumps({'frames':len(rows),'start_frame':start,'steady_pixels':steady,'steady_frames':shown.count(steady),
        'first_steady':next(x['frame'] for x in rows if x['pixels']==steady)}))

if __name__=='__main__':main()
