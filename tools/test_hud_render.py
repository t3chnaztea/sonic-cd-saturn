#!/usr/bin/env python3
"""Native HUD commands vs original mappings, and ring color vs retail 68000.

The CPU fixture executes the unmodified retail .Rings code. Only its downstream
DrawObject submission is stubbed to RTS; the independent mapping renderer below
checks the artwork. This is not whole-game or hardware frame-phase acceptance.
"""
import hashlib,json,random,re,struct,subprocess
from pathlib import Path
from convert_objects import DATA,assembly_frames,draw,nemesis
from extract_mmd import disc_files,unique
from retail_span import disc_span
from special_retail import layout
from test_sonic_animation import Retail

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/hud-render'
SOURCE=DATA/'_Objects/HUD and Points/Data'

class RingOracle(Retail):
    def __init__(self):
        self.program=disc_files((ROOT/'build/retail/sonic.iso').read_bytes())['R11A__.MMD']
        self.vars=layout()[0]
        # ObjHUD_Main .Rings through .Score; absolute addresses come from the
        # original variable layout and both branch spans are checked verbatim.
        signature=bytes.fromhex('4a79')+struct.pack('>I',self.vars['rings'])+disc_span('R11A__.MMD',0xad2e,12,'b7ccce2b91a30561ab53c1c5d9dd94d440ce5adcc636467d417496d478a92ad1')+struct.pack('>I',self.vars['levelVIntCounter']+3)+disc_span('R11A__.MMD',0xad3e,14,'c8a699f5cdf9a3f6da8537e8ffee138f56f8e4829707c7a5c9eaa5fdc0440763')
        entry=0x200000+unique(self.program,signature)
        tail=self.program[entry-0x200000+len(signature):entry-0x200000+len(signature)+28]
        assert re.fullmatch(re.escape(disc_span('R11A__.MMD',0xad4c,8,'d14673d506bcd1a89932aa52a18b602a8d374b426b16c5a45e96c97f232e369f'))+b'.{4}'+re.escape(disc_span('R11A__.MMD',0xad58,10,'8ff3730d34d018953a8d76e29ad3cbd491a0a3f6a63c60ddf158fe226ccfbb6a'))+b'.{4}'+bytes.fromhex('0008'),tail,re.S)
        draw_object=struct.unpack_from('>I',tail,22)[0]
        super().__init__(entry)
        self.write(draw_object,bytes.fromhex('4e75'))
        self.red=0
        self.draw_object=draw_object
    def color(self,rings,vint,reset,step):
        if reset:self.red=0
        if not step:return self.red
        actor=bytearray(64);struct.pack_into('>H',actor,2,0x8568|self.red*0x2000)
        self.write(self.actor,actor)
        self.write(self.vars['rings'],struct.pack('>H',rings))
        self.write(self.vars['levelVIntCounter'],struct.pack('>I',vint))
        self.write(self.stack,struct.pack('>I',self.halt))
        for reg,value in [(17,0x2700),(15,self.stack),(8,self.actor),(16,self.entry)]:self.lib.m68k_set_reg(reg,value)
        self.cpu.cycles=self.cpu.refresh_cycles=0
        self.lib.m68k_run(2000)
        assert self.lib.m68k_get_reg(16)==self.halt
        result=self.read(self.actor,64)
        assert result[:2]+result[4:]==actor[:2]+actor[4:]
        tile=struct.unpack_from('>H',result,2)[0]
        assert tile&~0x2000==0x8568
        self.red=(tile>>13)&1
        return self.red

def source_pixels(row,red):
    score,rings,ticks,lives,era,frame,vint,direction,travel,reset,step=row
    maps=assembly_frames(SOURCE/'Mappings (HUD).asm')
    art=bytearray(64*32);base=nemesis((SOURCE/'Art (HUD).nem').read_bytes());art[:len(base)]=base
    numbers=(SOURCE/'Art (Numbers).bin').read_bytes()
    def digits(tile,text):
        for i,c in enumerate(text):art[(tile+i*2)*32:(tile+i*2+2)*32]=bytes(64) if c==' ' else numbers[int(c)*64:(int(c)+1)*64]
    # Retail score is stored in tens: six writable digits followed by fixed 0.
    assert score%10==0 and score<=9999990
    digits(27,(str(score//10).rjust(6) if score else ' '*6)+'0')
    ticks=min(ticks,35999)
    digits(41,str(ticks//3600));digits(43,f'{ticks//60%60:02}');digits(47,f'{99 if ticks==35999 else ticks%60*100//60:02}')
    digits(51,str(rings).rjust(3));digits(61,str(min(lives,9)))
    life=(SOURCE/'Art (Life Icon).bin').read_bytes();variant=(1,0,2,2)[era]
    art[57*32:61*32]=life[variant*128:(variant+1)*128]
    pixels={}
    def mapping(data,tiles,x,y,bank=0):
        colors=struct.pack('>16H',0,*[0x4000+16*bank+i for i in range(1,16)])
        texture=draw(data,tiles,colors,256,0,128)
        for py in range(128):
            for px in range(256):
                v=struct.unpack_from('>H',texture,(py*256+px)*2)[0]
                if v:pixels[x+px-128,y+py-32]=v
    mapping(maps[0],art,16,8);mapping(maps[1],art,16,200);mapping(maps[3],art,16,8,red)
    if direction and (travel<90 or not frame&1):
        folder=DATA/'_Objects/Monitor and Time Post/Data'
        mapping(assembly_frames(folder/'Mappings.asm')[18 if direction<0 else 19],nemesis((folder/'Art.nem').read_bytes()),68,210)
    return pixels

def main():
    OUT.mkdir(exist_ok=True)
    oracle=RingOracle();rows=[]
    # Continuous ring-color history: clear on pickup, stay clear after loss
    # until the next eligible V-INT, and freeze during repeat/paused renders.
    for frame in range(1,65):
        rings=1 if frame in (17,35) else 0
        rows.append((123450,rings,frame,3,0,frame,frame,-1,frame+60,frame==1,1))
    rng=random.Random(0x485544);vint=0xfffffff0
    for n in range(1024):
        vint=(vint+rng.choice([0,1,1,1,2,17]))&0xffffffff
        rows.append((rng.choice([0,10,100,9990,123450,9999990]),rng.choice([0,0,1,9,10,99,100,999]),
                     rng.choice([0,1,58,59,60,3599,3600,35998,35999,36000]),rng.choice([0,1,3,9,10,255]),
                     n%4,n,vint,rng.choice([-1,0,1]),rng.choice([0,89,90,91,209,210]),n%41==0,n%7!=0))
    executable=OUT/'hud_render_test'
    subprocess.run(['clang','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Isrc','-Iassets/generated',
                    '-fsanitize=address,undefined','-fno-sanitize-recover=all','tools/hud_render_test.c','-o',str(executable)],cwd=ROOT,check=True)
    input_text=''.join(' '.join(str(int(v)) for v in row)+'\n' for row in rows)
    result=subprocess.run([str(executable)],input=input_text.encode(),capture_output=True,cwd=ROOT)
    (OUT/'cases.txt').write_text(input_text);(OUT/'commands.bin').write_bytes(result.stdout)
    (OUT/'sanitized.log').write_bytes(result.stderr)
    result.check_returncode()
    blob=(ROOT/'assets/generated/hud-original.bin').read_bytes();at=0;checked=0;negative=[]
    for index,row in enumerate(rows):
        red=oracle.color(row[1],row[6],row[9],row[10])
        count=struct.unpack_from('>I',result.stdout,at)[0];at+=4
        actual={}
        for _ in range(count):
            x,y,w,h,offset=struct.unpack_from('>iiIII',result.stdout,at);at+=20
            assert 0<=x and x+w<=320 and 0<=y and y+h<=224
            for py in range(h):
                for px in range(w):
                    color=struct.unpack_from('>H',blob,offset+(py*w+px)*2)[0]
                    if color:actual[x+px,y+py]=color
        expected=source_pixels(row,red)
        assert actual==expected,{'case':index,'inputs':row,'retail_red':red,'different_pixels':sum(actual.get(p)!=expected.get(p) for p in actual.keys()|expected.keys())}
        checked+=len(expected)
        if index<64 and bool(not row[1] and row[5]&16)!=bool(red):negative.append(index+1)
    assert at==len(result.stdout)
    assert 18 in negative,'former global-frame selector must fail the ring-loss regression'
    sources=['src/hud_view.inc','src/hud_animation.h','src/main.c','tools/hud_render_test.c','tools/test_hud_render.py',
             'tools/test_sonic_animation.py','tools/special_retail.py','tools/convert_objects.py','tools/extract_mmd.py',
             'assets/generated/hud-original.bin','assets/generated/hud-original.inc']
    report={'passed':True,'cases':len(rows),'opaque_pixel_comparisons':checked,'complete_transparency_checked':True,
            'retail_program_sha256':hashlib.sha256(oracle.program).hexdigest(),'retail_ring_entry':hex(oracle.entry),
            'stubbed_draw_object':hex(oracle.draw_object),'legacy_selector_failing_frames':negative,
            'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources},
            'evidence_sha256':{name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in ['cases.txt','commands.bin','sanitized.log']},
            'core_sha256':hashlib.sha256((ROOT/'.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib').read_bytes()).hexdigest(),
            'original_art_sha256':{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in
                [SOURCE/'Mappings (HUD).asm',SOURCE/'Art (HUD).nem',SOURCE/'Art (Numbers).bin',SOURCE/'Art (Life Icon).bin',
                 DATA/'_Objects/Monitor and Time Post/Data/Mappings.asm',DATA/'_Objects/Monitor and Time Post/Data/Art.nem']},
            'sanitizers':'address and undefined behavior','hardware_tested':False,
            'limits':'Native HUD command composition and original ring-state algorithm at supplied V-INTs; not whole-game clock phase, actual VDP priority/palette, or hardware acceptance.'}
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Native HUD: {len(rows)} cases, {checked} original opaque pixels, complete transparency, retail ring-state match; old selector fails at frame 18')

if __name__=='__main__':main()
