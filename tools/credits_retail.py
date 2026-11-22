#!/usr/bin/env python3
"""Run the retail "Thank You" screen (THANKS_M.MMD; IPX.asm VisualMode_GoodEnd runs
RunMMD(SCMD_THANKYOU) after the good ending, IPX.asm:1176-1186) in the pinned Sega CD
core and record every frame.

QA oracle only. Like tools/ss8_credits_retail.py, the IPX Backup RAM call jumps to an
injected RunMMD(SCMD_THANKYOU). Optional pad presses: --press FRAME (Start held for 4
frames from that program frame). Writes build/credits/retail/thanks.jsonl (frame, pixel
CRC, CRAM, VDP registers, plane and sprite table CRCs), blobs.json (the buffers by CRC),
vram-<frame>.bin dumps for --vram frames, and PNGs for --png frames.
"""
import argparse,json,struct,sys,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import special_retail as sr
OUT=ROOT/'build/credits/retail'

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--frames',type=int,default=4000,help='program frames to record')
    ap.add_argument('--press',type=int,action='append',default=[],help='program frame to press Start')
    ap.add_argument('--png',type=int,action='append',default=[])
    ap.add_argument('--vram',type=int,action='append',default=[])
    ap.add_argument('--ram',type=int,action='append',default=[],help='program frame to dump Main CPU work RAM')
    ap.add_argument('--tag',default='thanks')
    args=ap.parse_args()
    # No RAM cartridge. With none fitted the core leaves $400001 unmapped, and the open bus
    # reads as a cartridge ID with bit 7 clear, so BRAMINIT and THANKS_M.MMD both find an
    # unformatted RAM cart (BRAMINIT stops on "RAM cartridge is not initialized"). An ID
    # register reading $80 (bit 7 set, no "RAM_CARTRIDGE" signature) is a console with
    # nothing in the slot to both programs.
    import retail_capture
    sr.C.c_uint8.in_dll(retail_capture.lib,'cart_size').value=0x80
    r=sr.Retail()
    ipx=(sr.RETAIL/'IPX___.MMD').read_bytes();origin=struct.unpack_from('>I',ipx,2)[0];code=ipx[0x100:0x1100]
    run_mmd,_=sr.find(code,'2f0833c000a12010',origin)
    (bram_at,bram_old,bram_new),(demo_at,demo_old,_)=r.patch
    # IPX boots through RunMMD(SCMD_BURAMINIT) (the call replaced here) first: the screen
    # reads the save file from Backup RAM.
    inject=struct.pack('>HH',0x303c,r.scmd['SCMD_BURAMINIT'])+struct.pack('>HI',0x4eb9,run_mmd)
    inject+=struct.pack('>HH',0x303c,r.scmd['SCMD_THANKYOU'])+struct.pack('>HI',0x4eb9,run_mmd)+bytes.fromhex('60fe')
    patch=[(bram_at,bram_old,bram_new),(demo_at,demo_old,inject)];halt=demo_at+len(inject)-2
    core=r.core;rows=[];blobs={};patched=False;begun=None;halted=0;frame=0
    OUT.mkdir(parents=True,exist_ok=True)
    def blob(data):
        key='%08x'%zlib.crc32(data);blobs.setdefault(key,data.hex());return key
    while frame<args.frames+3000 and halted<30 and (begun is None or frame-begun<args.frames):
        t=frame-begun if begun is not None else -1
        core.pad=0x80 if begun is not None and any(0<=t-p<4 for p in args.press) else 0
        core.run();frame+=1
        if not patched and all(core.work_read(at,len(old))==old for at,old,_ in patch):
            for at,_,new in patch:core.work_write(at,new)
            patched=True
        pc=core.lib.m68k_get_reg(16)
        if patched and begun is None and 0xff2000<=pc<0xffb000 and core.work_read(0xff2000,6)==bytes.fromhex('21fc00ff3a40'):begun=frame
        if begun is None:continue
        t=frame-begun
        width,height,pixels=core.frame or (0,0,b'')
        reg=sr.C.string_at(core.reg,24)
        cram=[(v>>6&7)<<9|(v>>3&7)<<5|(v&7)<<1 for v in struct.unpack('<64H',sr.C.string_at(core.cram,128))]
        h40=bool(reg[12]&1)
        rows.append({'frame':t,'width':width,'height':height,'pixels':'%08x'%zlib.crc32(pixels),
            'cram':blob(struct.pack('>64H',*cram)),'reg':reg.hex(),'vsram':sr.C.string_at(core.vsram,4).hex(),
            'plane_a':blob(core.swapped(core.vram,(reg[2]&0x38)<<10,0x1000)),'plane_b':blob(core.swapped(core.vram,(reg[4]&7)<<13,0x1000)),
            'hscroll':blob(core.swapped(core.vram,reg[13]<<10,0x380)),'sat':blob(core.swapped(core.vram,(reg[5]&(0x7e if h40 else 0x7f))<<9,640)),
            'tiles':'%08x'%zlib.crc32(core.swapped(core.vram,0,0x10000)),'pad':core.pad,'pc':pc,
            # THANKS_M.MMD work RAM: the 64 actors (64 bytes each, $FF9200) and ranum ($FFBA52).
            'actors':blob(core.work_read(0xff9200,64*64)),'ranum':core.work_read(0xffba52,4).hex(),
            # $FFBA40-$FFBA87: quit flag, V-int request, palette cycles, timers (ba78 posetimer, ba80 end timer).
            'globals':core.work_read(0xffba40,0x48).hex()})
        if t in args.png and core.frame:sr.png(OUT/f'{args.tag}-{t}.png',core.frame)
        if t in args.vram:(OUT/f'{args.tag}-vram-{t}.bin').write_bytes(core.swapped(core.vram,0,0x10000))
        if t in args.ram:(OUT/f'{args.tag}-ram-{t}.bin').write_bytes(core.work_read(0xff0000,0x10000))
        halted=halted+1 if pc==halt else 0
    (OUT/f'{args.tag}.jsonl').write_text(''.join(json.dumps(x,separators=(',',':'))+'\n' for x in rows))
    (OUT/f'{args.tag}-blobs.json').write_text(json.dumps(blobs))
    shown=[x['pixels'] for x in rows if x['width']]
    print(json.dumps({'frames':len(rows),'returned':halted>=30,'distinct_pictures':len(set(shown)),'press':args.press}))

if __name__=='__main__':main()
