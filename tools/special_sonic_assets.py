#!/usr/bin/env python3
"""Flatten original special-stage Sonic pieces, preserving animation references."""
import hashlib,json,re,struct
from special_assets import ROOT,SOURCE,OUT
from convert_assets import palette
from generated_io import write_bytes, write_text
DIRECTORY=SOURCE/'Objects/Sonic/Data'
def mappings(base=0):
    labels={};rows=[];offset=0
    for text in (DIRECTORY/'Mappings.asm').read_text().splitlines():
        line=text.split(';',1)[0].strip()
        if not line:continue
        if line.endswith(':'):labels[line[:-1]]=offset;continue
        if line=='even':offset=(offset+1)&~1;continue
        m=re.fullmatch(r'dc\.([bwl])\s+(.+)',line)
        if not m:raise ValueError(('unknown mapping directive',line))
        width={'b':1,'w':2,'l':4}[m[1]]
        for value in m[2].split(','):rows.append((offset,width,value.strip()));offset+=width
    blob=bytearray(offset)
    for offset,width,expression in rows:
        value=0
        for term in expression.split('|'):value|=labels[term]+base if term in labels else int(term.replace('$','0x'),0)
        blob[offset:offset+width]=value.to_bytes(width,'big')
    return bytes(blob)
def original_art():
    # Sub.asm ORG $10000, SonicArt aligned at PRGRAM+$30000. The
    # original LoadArt copies 0x300 bytes even across split-file boundaries.
    original=(DIRECTORY/'Frames/SPSS__.BIN').read_bytes()
    pointers=struct.unpack_from('>70I',original,0x20000);frames=[]
    for i,pointer in enumerate(pointers[:64]):
        start=pointer-0x10000;raw=(DIRECTORY/f'Frames/{i}.bin').read_bytes()
        assert start>=0 and start+768<=len(original)
        assert original[start:start+len(raw)]==raw,('original art pointer/prefix',i)
        frames.append(original[start:start+768])
    return frames

def source():
    blob=mappings();count=int.from_bytes(blob[:4],'big')//4;animations=[];addresses=set()
    for i in range(count):
        pos=int.from_bytes(blob[i*4:i*4+4],'big');n,delay=blob[pos:pos+2];entries=[]
        for j in range(n):
            raw=int.from_bytes(blob[pos+2+j*4:pos+6+j*4],'big');address=raw&0xffffff
            assert raw>>24<4;addresses.add(address);entries.append((address,raw>>24))
        animations.append((delay,entries))
    poses=[];art=original_art()
    for address in sorted(addresses):
        count=blob[address]+1;frame=blob[address+1];raw=art[frame];pieces=[]
        for i in range(count):
            y,size,hi,lo,x=blob[address+5+i*5:address+10+i*5]
            x=x if x<128 else x-256;y=y if y<128 else y-256
            w=((size>>2)&3)*8+8;h=(size&3)*8+8;tile=(hi<<8)|lo
            assert tile&0xe000==0,('piece palette/priority needs support',frame,tile)
            assert ((tile&2047)+w*h//64)*32<=len(raw),('piece outside source art',frame,tile,w,h,len(raw))
            pieces.append((x,y,w,h,tile))
        left=min(p[0] for p in pieces);top=min(p[1] for p in pieces)
        width=max(p[0]+p[2] for p in pieces)-left;height=max(p[1]+p[3] for p in pieces)-top
        width=(width+7)&~7
        assert width<=64 and height<=64
        pixels=bytearray(width*height)
        for x,y,w,h,tile in pieces:
            for dy in range(h):
                for dx in range(w):
                    u=w-1-dx if tile&0x800 else dx;v=h-1-dy if tile&0x1000 else dy
                    at=((tile&2047)+(u//8)*(h//8)+v//8)*32+(v%8)*4+u%8//2
                    pixel=(raw[at]>>(0 if u&1 else 4))&15
                    dest=(y-top+dy)*width+x-left+dx
                    if not pixels[dest]:pixels[dest]=pixel # Earlier MD sprite pieces have priority.
        packed=bytes((a<<4)|b for a,b in zip(pixels[::2],pixels[1::2]))
        poses.append({'address':address,'frame':frame,'x':left,'y':top,'width':width,'height':height,'pixels':bytes(pixels),'packed':packed,'pieces':pieces})
    return animations,poses

def pack():
    animations,poses=source();indices={p['address']:i for i,p in enumerate(poses)}
    count=sum(len(entries) for _,entries in animations);ao=40;eo=ao+len(animations)*4;po=eo+count*4;pal=po+len(poses)*16;tex=(pal+32+7)&~7
    result=bytearray(tex);entry=0
    for i,(delay,entries) in enumerate(animations):
        struct.pack_into('>BBH',result,ao+i*4,len(entries),delay,entry)
        for address,flip in entries:struct.pack_into('>HH',result,eo+entry*4,indices[address],flip);entry+=1
    result[pal:pal+32]=palette((SOURCE/'Data/Palette.bin').read_bytes())[:32]
    for i,p in enumerate(poses):
        result.extend(bytes(-len(result)%8));offset=len(result);data=p['packed'];result.extend(data)
        struct.pack_into('>IhhHHI',result,po+i*16,offset,p['x'],p['y'],p['width'],p['height'],p['frame'])
    result[:4]=b'SSA1';struct.pack_into('>9I',result,4,len(result),len(animations),len(poses),count,ao,eo,po,pal,tex)
    return bytes(result),animations,poses

def main():
    data,animations,poses=pack();write_bytes(OUT/'special-sonic.bin',data)
    write_bytes(ROOT/'cd/SSONIC.BIN',data+bytes(-len(data)%2048))
    report={'source':'pinned Special Stage/Objects/Sonic/Data and common palette','original_art_binary_sha256':hashlib.sha256((DIRECTORY/'Frames/SPSS__.BIN').read_bytes()).hexdigest(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'animations':len(animations),'entries':sum(len(e) for _,e in animations),'poses':len(poses),'texture_bytes':sum(len(p['packed']) for p in poses),'maximum_texture_bytes':max(len(p['packed']) for p in poses),'frames':[{k:v for k,v in p.items() if k not in ['pixels','packed','pieces']}|{'pixel_sha256':hashlib.sha256(p['pixels']).hexdigest()} for p in poses]}
    write_text(ROOT/'build/special-sonic-source.json',json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='frames'}))
if __name__=='__main__':main()
