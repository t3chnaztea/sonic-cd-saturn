#!/usr/bin/env python3
"""Original Splash/Dust/Item art and mappings in a compact Saturn pack."""
import hashlib,json,struct
from special_assets import ROOT,SOURCE,OUT
from special_effect_reference import mapping
from convert_assets import nemesis,palette
from generated_io import write_bytes, write_text
GROUPS=[('Splash','Splash',0x582),('Dust','Explosion',0x7ae),('Item','Item',0x78f)]
def source(groups_spec=GROUPS):
    animations=[];poses=[];groups=[]
    for group in groups_spec:
        name,art_name,base_tile=group[:3]
        map_name,map_file=group[3:] if len(group)>3 else (name,'Mappings.asm')
        blob=mapping(map_name,0,map_file);raw=nemesis((SOURCE/f'Objects/{art_name}/Data/Art.nem').read_bytes());count=int.from_bytes(blob[:4],'big')//4
        entries=[];addresses=set();first_animation=len(animations)
        for i in range(count):
            pos=int.from_bytes(blob[i*4:i*4+4],'big');frames,delay=blob[pos:pos+2];sequence=[]
            for j in range(frames):
                value=int.from_bytes(blob[pos+2+j*4:pos+6+j*4],'big');address=value&0xffffff;flip=value>>24
                assert flip<4;sequence.append((address,flip));addresses.add(address)
            entries.append((delay,sequence))
        indices={}
        for address in sorted(addresses):
            pieces=[];flag=blob[address+1]
            for i in range(blob[address]+1):
                y,size,hi,lo,x=blob[address+5+i*5:address+10+i*5];x=x if x<128 else x-256;y=y if y<128 else y-256
                width=((size>>2)&3)*8+8;height=(size&3)*8+8;tile=(hi<<8)|lo
                assert not(tile&0xe000);assert ((tile&2047)+width*height//64)*32<=len(raw)
                pieces.append((x,y,width,height,tile))
            left=min(p[0] for p in pieces);top=min(p[1] for p in pieces);width=(max(p[0]+p[2] for p in pieces)-left+7)&~7;height=max(p[1]+p[3] for p in pieces)-top
            assert width<=256 and height<=256,(name,width,height)
            pixels=bytearray(width*height)
            for x,y,w,h,tile in pieces:
                for dy in range(h):
                    for dx in range(w):
                        u=w-1-dx if tile&0x800 else dx;v=h-1-dy if tile&0x1000 else dy
                        at=((tile&2047)+(u//8)*(h//8)+v//8)*32+(v%8)*4+u%8//2
                        pixel=(raw[at]>>(0 if u&1 else 4))&15;dest=(y-top+dy)*width+x-left+dx
                        if not pixels[dest]:pixels[dest]=pixel
            indices[address]=len(poses);poses.append({'group':name,'address':address,'frame':flag,'x':left,'y':top,'width':width,'height':height,'pixels':bytes(pixels),'packed':bytes((a<<4)|b for a,b in zip(pixels[::2],pixels[1::2]))})
        for delay,sequence in entries:animations.append((delay,[(indices[a],f) for a,f in sequence]))
        groups.append({'name':name,'first_animation':first_animation,'animations':count,'art_bytes':len(raw),'art_sha256':hashlib.sha256(raw).hexdigest(),'base_tile':base_tile})
    return animations,poses,groups

def pack():
    animations,poses,groups=source();count=sum(len(e) for _,e in animations);ao=40;eo=ao+len(animations)*4;po=eo+count*4;pal=po+len(poses)*16;tex=(pal+128+7)&~7
    data=bytearray(tex);entry=0
    for i,(delay,sequence) in enumerate(animations):
        struct.pack_into('>BBH',data,ao+i*4,len(sequence),delay,entry)
        for pose,flip in sequence:struct.pack_into('>HH',data,eo+entry*4,pose,flip);entry+=1
    data[pal:pal+128]=palette((SOURCE/'Data/Palette.bin').read_bytes())
    for i,pose in enumerate(poses):
        data.extend(bytes(-len(data)%8));offset=len(data);data.extend(pose['packed']);struct.pack_into('>IhhHHI',data,po+i*16,offset,pose['x'],pose['y'],pose['width'],pose['height'],pose['frame'])
    data[:4]=b'SFX1';struct.pack_into('>9I',data,4,len(data),len(animations),len(poses),count,ao,eo,po,pal,tex)
    return bytes(data),animations,poses,groups

def main():
    data,animations,poses,groups=pack();write_bytes(OUT/'special-effects.bin',data);write_bytes(ROOT/'cd/SFX.BIN',data+bytes(-len(data)%2048))
    report={'source':'Pinned original Splash/Item/Explosion Nemesis art, Splash/Dust/Item mappings and common palette','bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'animations':len(animations),'poses':len(poses),'entries':sum(len(e) for _,e in animations),'texture_bytes':sum(len(p['packed']) for p in poses),'maximum_texture_bytes':max(len(p['packed']) for p in poses),'groups':groups,'frames':[{k:v for k,v in p.items() if k not in ['pixels','packed']}|{'pixel_sha256':hashlib.sha256(p['pixels']).hexdigest()} for p in poses]}
    write_text(ROOT/'build/special-effects-source.json',json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='frames'}))
if __name__=='__main__':main()
