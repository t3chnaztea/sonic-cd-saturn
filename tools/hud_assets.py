#!/usr/bin/env python3
"""Import the retail level HUD mappings/art; emit high-priority palette-index sprites."""
import struct
from pathlib import Path
from convert_objects import DATA, OUT, assembly_frames, draw, nemesis
from generated_io import write_bytes, write_text

def build():
    source=DATA/'_Objects/HUD and Points/Data'
    maps=assembly_frames(source/'Mappings (HUD).asm')
    art=nemesis((source/'Art (HUD).nem').read_bytes())
    numbers=(source/'Art (Numbers).bin').read_bytes()
    lives=(source/'Art (Life Icon).bin').read_bytes()
    blob=bytearray();groups={}
    def piece(record,tiles,bank=0):
        y,size,hi,lo,x=record
        x=x if x<128 else x-256;y=y if y<128 else y-256
        w=((size>>2)&3)*8+8;h=(size&3)*8+8
        colors=struct.pack('>16H',0,*[0x4000+bank*16+i for i in range(1,16)])
        image=draw(bytes([1,0,size,hi,lo,0]),tiles,colors,64,-32,h)
        cropped=b''.join(image[(row*64+32)*2:(row*64+32+w)*2] for row in range(h))
        offset=len(blob);blob.extend(cropped)
        return (x,y,w,h,offset)
    # The static score/time labels and punctuation; counters use writable tiles in retail.
    groups['labels']=[piece(maps[0][1+i*5:6+i*5],art) for i in range(maps[0][0]) if maps[0][4+i*5]<27]
    for bank in (0,1):groups[f'rings{bank}']=[piece(maps[3][1+i*5:6+i*5],art,bank) for i in range(3)]
    groups['digits']=[piece([0,1,0,n*2,0],numbers) for n in range(10)]
    groups['lives']=[piece([0,5,0,0,0],lives[n*128:(n+1)*128]) for n in range(3)]
    groups['cross']=[piece([8,0,0,26,16],art)]
    time_source=DATA/'_Objects/Monitor and Time Post/Data'
    time_maps=assembly_frames(time_source/'Mappings.asm');time_art=nemesis((time_source/'Art.nem').read_bytes())
    for name,index in [('past',18),('future',19)]:
        mapping=time_maps[index]
        groups[name]=[piece(mapping[1+i*5:6+i*5],time_art) for i in range(mapping[0])]
    assert len(blob)<0x8000 and len(blob)%8==0
    write_bytes(OUT/'hud-original.bin',blob)
    lines=['/* Generated from original HUD mappings, number art and life icons. */',
           'typedef struct {int16_t x,y;uint16_t width,height,offset;} hud_piece;',f'#define HUD_ORIGINAL_BYTES {len(blob)}u']
    for name,records in groups.items():lines.append('static const hud_piece hud_'+name+'[]={'+','.join('{'+','.join(map(str,r))+'}' for r in records)+'};')
    write_text(OUT/'hud-original.inc','\n'.join(lines)+'\n')
    print(f'Original HUD: {len(blob)} bytes, {sum(map(len,groups.values()))} mapped pieces')
    return groups,blob
if __name__=='__main__':build()
