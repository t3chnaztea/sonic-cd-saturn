#!/usr/bin/env python3
"""Effect pack pixels against original NemDecToRAM and DrawObject SAT output."""
import ctypes as C,hashlib,json,struct,subprocess
from special_assets import ROOT,SOURCE
from special_effect_assets import pack,GROUPS
from special_effect_reference import EffectReference
from test_special_effects import Effect,Context,state
from test_special_sprite import Art,Sprite,Pose,canvas
from test_special_player import Player

def source_pixels(sat,raw,base,width=96,height=96,x_offset=-208,y_offset=-280,colors=False):
    pixels=bytearray(width*height)
    for sy,size,link,tile,sx in struct.iter_unpack('>HBBHH',sat):
        w=((size>>2)&3)+1;h=(size&3)+1;first=(tile&2047)-base
        assert first>=0 and (first+w*h)*32<=len(raw)
        for tx in range(w):
            for ty in range(h):
                data=raw[(first+tx*h+ty)*32:(first+tx*h+ty+1)*32]
                for y in range(8):
                    for x in range(8):
                        u=tx*8+x;v=ty*8+y
                        if tile&0x800:u=w*8-1-u
                        if tile&0x1000:v=h*8-1-v
                        dx=sx+x_offset+u;dy=sy+y_offset+v
                        if 0<=dx<width and 0<=dy<height and not pixels[dy*width+dx]:
                            value=(data[y*4+x//2]>>(0 if x&1 else 4))&15
                            if value:pixels[dy*width+dx]=value|(((tile>>13)&3)*16 if colors else 0)
    return bytes(pixels)

def main():
    subprocess.run(['python3','tools/special_effect_assets.py'],cwd=ROOT,check=True)
    subprocess.run(['clang','-std=c11','-O2','-Wall','-Wextra','-Werror','-Isrc','-dynamiclib','src/special_sprite.c','-o','build/special-effect-art.dylib'],cwd=ROOT,check=True)
    subprocess.run(['clang','-std=c11','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-Isrc','tools/special_sprite_sanitize.c','src/special_sprite.c','-o','build/special-effect-art-sanitize'],cwd=ROOT,check=True)
    subprocess.run([ROOT/'build/special-effect-art-sanitize','assets/generated/special-effects.bin'],cwd=ROOT,check=True)
    native=C.CDLL(str(ROOT/'build/special-effect-art.dylib'));native.scd_special_art_open.argtypes=[C.POINTER(Art),C.c_void_p,C.c_size_t];native.scd_special_sprite_advance.argtypes=[C.POINTER(Sprite),C.POINTER(Player),C.POINTER(Art),C.POINTER(Pose)]
    data,animations,poses,groups=pack();buf=C.create_string_buffer(data);art=Art();assert native.scd_special_art_open(C.byref(art),buf,len(data))==0
    reference=EffectReference();raws={};digest=hashlib.sha256();fixtures=[]
    for name,art_name,base in GROUPS:
        compressed=(SOURCE/f'Objects/{art_name}/Data/Art.nem').read_bytes();size=next(g['art_bytes'] for g in groups if g['name']==name)
        decoded=reference.decompress(compressed,size);assert hashlib.sha256(decoded).hexdigest()==next(g['art_sha256'] for g in groups if g['name']==name),(name,'original Nemesis bytes')
        raws[name]=decoded;digest.update(decoded)
    for animation,(delay,sequence) in enumerate(animations):
        group='Splash' if animation<2 else 'Dust' if animation==2 else 'Item';local=animation if animation<2 else 0 if animation==2 else animation-3
        base=next(g['base_tile'] for g in groups if g['name']==group)
        for frame,(index,flip) in enumerate(sequence):
            s=Sprite(animation=animation,frame=frame,time=delay,time_copy=delay);pose=Pose();assert native.scd_special_sprite_advance(C.byref(s),C.byref(Player(flags=2)),C.byref(art),C.byref(pose))==0
            e=Effect(x=256<<16,y=344<<16,id=8 if group=='Splash' else 7 if group=='Dust' else 13 if local==4 else 4,flags=2,animation=local,frame=frame,time=delay,time_copy=delay)
            expected,ctx,sat,sound,_=reference.run(state(e),state(Context()),operation='draw')
            pixels=source_pixels(sat,raws[group],base);assert canvas(pose)==pixels,(animation,frame,'original SAT pixels')
            assert pose.index==index and pose.flip==flip and s.art==expected['art']
            digest.update(pixels);fixtures.append({'animation':animation,'frame':frame,'pose':index,'flip':flip,'palette_bank':3 if animation==7 else 0,'pixel_sha256':hashlib.sha256(pixels).hexdigest()})
    report={'passed':True,'original_nemesis_assets':len(raws),'decoded_bytes':sum(map(len,raws.values())),'original_sat_poses':len(fixtures),'canvas_pixels_compared':len(fixtures)*96*96,'pack_sha256':hashlib.sha256(data).hexdigest(),'state_pixel_sha256':digest.hexdigest()}
    (ROOT/'build/special-reference/effect-art-report.json').write_text(json.dumps(report,indent=2)+'\n');(ROOT/'build/special-reference/effect-art-fixtures.json').write_text(json.dumps(fixtures,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
