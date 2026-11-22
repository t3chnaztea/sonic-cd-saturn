#!/usr/bin/env python3
"""Source UFO/shadow/explosion art plus all bounded original UFO paths."""
import hashlib,json,struct
from special_assets import ROOT,SOURCE,OUT
from special_effect_assets import source
from convert_assets import palette
from generated_io import write_bytes, write_text
GROUPS=[('UFORings','UFO',0x440,'UFO','Mappings (Rings).asm'),('UFOShoes','UFO',0x440,'UFO','Mappings (Speed Shoes).asm'),('Shadow','Shadow',0x6dc,'Shadow','Mappings.asm'),('Explosion','Explosion',0x7ae,'Explosion','Mappings.asm'),('TimeStone','Time Stone',0x424,'Time Stone','Mappings.asm'),('TitleCardBar','Title Card',0x516,'Title Card','Mappings (Bar).asm'),('TitleCardText','Title Card',0x516,'Title Card','Mappings (Text).asm')]
def pack():
    animations,poses,groups=source(GROUPS);entries=sum(len(e) for _,e in animations)
    ao=40;eo=ao+len(animations)*4;po=eo+entries*4;pal=po+len(poses)*16;tex=(pal+135)&~7
    data=bytearray(tex);entry=0
    for i,(delay,sequence) in enumerate(animations):
        struct.pack_into('>BBH',data,ao+i*4,len(sequence),delay,entry)
        for pose,flip in sequence:struct.pack_into('>HH',data,eo+entry*4,pose,flip);entry+=1
    data[pal:pal+128]=palette((SOURCE/'Data/Palette.bin').read_bytes())
    for i,pose in enumerate(poses):
        data.extend(bytes(-len(data)%8));offset=len(data);data.extend(pose['packed']);struct.pack_into('>IhhHHI',data,po+i*16,offset,pose['x'],pose['y'],pose['width'],pose['height'],pose['frame'])
    data[:4]=b'UFX1';struct.pack_into('>9I',data,4,len(data),len(animations),len(poses),entries,ao,eo,po,pal,tex)
    return bytes(data),animations,poses,groups

def paths():
    files=[SOURCE/f'Data/Stage {stage}/UFO {ufo}.bin' for stage in range(1,9) for ufo in range(1,7)]+[SOURCE/'Data/Time UFO Path.bin']
    data=bytearray(16+49*8);details=[]
    for index,p in enumerate(files):
        raw=p.read_bytes();assert len(raw)>=14 and (len(raw)-4)%10==0 and raw[0]<4
        for node in range(2,len(raw)-2,10):assert 0<int.from_bytes(raw[node:node+2],'big')<32768
        assert int.from_bytes(raw[-2:],'big')>=32768
        offset=len(data);data.extend(raw);struct.pack_into('>II',data,16+index*8,offset,len(raw));details.append({'path':str(p.relative_to(SOURCE)),'offset':offset,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    data[:4]=b'UFP1';struct.pack_into('>III',data,4,len(data),49,16);return bytes(data),details

def main():
    data,animations,poses,groups=pack();path_data,details=paths()
    write_bytes(OUT/'special-ufo-art.bin',data);write_bytes(OUT/'special-ufo-paths.bin',path_data)
    write_bytes(ROOT/'cd/UFX.BIN',data+bytes(-len(data)%2048));write_bytes(ROOT/'cd/UFP.BIN',path_data+bytes(-len(path_data)%2048))
    report={'source':'Pinned UFO, Shadow and Explosion Nemesis art/mappings, common palette and all 49 original paths','art_bytes':len(data),'art_sha256':hashlib.sha256(data).hexdigest(),'animations':len(animations),'poses':len(poses),'entries':sum(len(e) for _,e in animations),'texture_bytes':sum(len(p['packed']) for p in poses),'maximum_texture_bytes':max(len(p['packed']) for p in poses),'groups':groups,'path_bytes':len(path_data),'paths_sha256':hashlib.sha256(path_data).hexdigest(),'paths':details}
    write_text(ROOT/'build/special-ufo-source.json',json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='paths'}))
if __name__=='__main__':main()
