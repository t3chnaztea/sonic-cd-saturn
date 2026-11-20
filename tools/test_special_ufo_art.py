#!/usr/bin/env python3
"""Original Nemesis/SAT proof for all UFO, shadow and explosion poses."""
import ctypes as C,hashlib,json,struct,subprocess
from special_assets import ROOT,SOURCE
from special_ufo_assets import pack,GROUPS,paths
from special_effect_reference import EffectReference,mapping
from test_special_effects import Effect,Context,state
from test_special_sprite import Art,Sprite,Pose
from test_special_player import Player
from test_special_effect_art import source_pixels
from test_special_ufo import Path

def canvas(pose,size=256,ox=128,oy=160):
    """Pose pixels on a canvas large enough for title-card sprites."""
    packed=C.string_at(pose.pixels,pose.width*pose.height//2);result=bytearray(size*size)
    for y in range(pose.height):
        for x in range(pose.width):
            u=pose.width-1-x if pose.flip&1 else x;v=pose.height-1-y if pose.flip&2 else y;at=v*pose.width+u
            dx=ox+pose.x+x;dy=oy+pose.y+y
            if 0<=dx<size and 0<=dy<size:result[dy*size+dx]=(packed[at//2]>>(0 if at&1 else 4))&15
    return bytes(result)
def main():
    subprocess.run(['python3','tools/special_ufo_assets.py'],cwd=ROOT,check=True)
    subprocess.run(['clang','-std=c11','-O2','-Wall','-Wextra','-Werror','-Isrc','-Iassets/generated','-dynamiclib','src/special_sprite.c','src/special_ufo.c','src/special.c','-o','build/special-ufo-art.dylib'],cwd=ROOT,check=True)
    subprocess.run(['clang','-std=c11','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-Isrc','tools/special_sprite_sanitize.c','src/special_sprite.c','-o','build/special-ufo-art-sanitize'],cwd=ROOT,check=True)
    subprocess.run([ROOT/'build/special-ufo-art-sanitize','assets/generated/special-ufo-art.bin'],cwd=ROOT,check=True)
    native=C.CDLL(str(ROOT/'build/special-ufo-art.dylib'));native.scd_special_art_open.argtypes=[C.POINTER(Art),C.c_void_p,C.c_size_t];native.scd_special_sprite_advance.argtypes=[C.POINTER(Sprite),C.POINTER(Player),C.POINTER(Art),C.POINTER(Pose)]
    native.scd_special_ufo_paths_open.argtypes=[C.POINTER(Path),C.c_void_p,C.c_size_t];native.scd_special_ufo_path_get.argtypes=[C.POINTER(Path),C.c_uint,C.POINTER(Path)]
    data,animations,poses,groups=pack();buf=C.create_string_buffer(data);art=Art();assert native.scd_special_art_open(C.byref(art),buf,len(data))==0
    reference=EffectReference();raws={};digest=hashlib.sha256();fixtures=[]
    for name,art_name,base,map_name,map_file in GROUPS:
        compressed=(SOURCE/f'Objects/{art_name}/Data/Art.nem').read_bytes();group=next(g for g in groups if g['name']==name)
        if art_name not in raws:
            decoded=reference.decompress(compressed,group['art_bytes']);assert hashlib.sha256(decoded).hexdigest()==group['art_sha256'];raws[art_name]=decoded;digest.update(decoded)
        reference.r.write(reference.r.prg,0x1f000,mapping(map_name,0x1f000,map_file))
        for local in range(group['animations']):
            animation=group['first_animation']+local;delay,sequence=animations[animation]
            for frame,(index,flip) in enumerate(sequence):
                s=Sprite(animation=animation,frame=frame,time=delay,time_copy=delay);pose=Pose();assert native.scd_special_sprite_advance(C.byref(s),C.byref(Player(flags=2)),C.byref(art),C.byref(pose))==0
                e=Effect(x=256<<16,y=240<<16,id=2,flags=2,animation=local,frame=frame,time=delay,time_copy=delay)
                for bank in ([0,3] if name=='UFORings' else [0] if name=='Explosion' else [3]):
                    expected,ctx,sat,sound,_=reference.run(state(e),state(Context()),operation='draw',map_override=(0x1f000,0x8000|(bank<<13)|base))
                    pixels=source_pixels(sat,raws[art_name],base,256,256,-128,-80);assert canvas(pose)==pixels,(name,local,frame,'original SAT pixels')
                    assert pose.index==index and pose.flip==flip and s.art==expected['art']
                    colored=source_pixels(sat,raws[art_name],base,256,256,-128,-80,colors=True)
                    assert colored==bytes(value|(bank<<4) if value else 0 for value in pixels),(name,bank,'original palette')
                    digest.update(colored);fixtures.append({'group':name,'animation':animation,'frame':frame,'pose':index,'flip':flip,'palette_bank':bank,'pixel_sha256':hashlib.sha256(colored).hexdigest()})
    path_data,details=paths();path_buf=C.create_string_buffer(path_data);path_pack=Path();assert native.scd_special_ufo_paths_open(C.byref(path_pack),path_buf,len(path_data))==0
    for i,detail in enumerate(details):
        path=Path();assert native.scd_special_ufo_path_get(C.byref(path_pack),i,C.byref(path))==0
        assert C.string_at(path.data,path.size)==(SOURCE/detail['path']).read_bytes()
    for i in [49,50,65535,0xffffffff]:assert native.scd_special_ufo_path_get(C.byref(path_pack),i,C.byref(Path()))==-1
    report={'passed':True,'original_nemesis_assets':len(raws),'decoded_bytes':sum(map(len,raws.values())),'original_sat_poses':len(poses),'pose_palette_cases':len(fixtures),'canvas_pixels_compared':len(fixtures)*256*256,'pack_sha256':hashlib.sha256(data).hexdigest(),'path_pack_sha256':hashlib.sha256(path_data).hexdigest(),'original_paths_read_back':49,'state_pixel_sha256':digest.hexdigest(),'limits':'Host original art/SAT and native parser; target load/VRAM/composites not integrated yet.'}
    (ROOT/'build/special-reference/ufo-art-report.json').write_text(json.dumps(report,indent=2)+'\n');(ROOT/'build/special-reference/ufo-art-fixtures.json').write_text(json.dumps(fixtures,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
