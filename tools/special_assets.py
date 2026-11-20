#!/usr/bin/env python3
"""Decode original special-stage stamp assets into bounded, big-endian packs.

Kosinski follows Special Stage/Sub.asm, including eager descriptor refills.
The source map remains 128x128 32-pixel stamps, with all orientation bits.
"""
import hashlib,json,re,struct
from convert_assets import ROOT,DATA,OUT,palette
from generated_io import write_bytes, write_text
SOURCE=DATA.parent/'Special Stage'

def kosinski(data,limit=0x40000):
    pos=0;field=bits=0;out=bytearray()
    def byte():
        nonlocal pos
        if pos>=len(data):raise ValueError('truncated Kosinski input')
        v=data[pos];pos+=1;return v
    def refill():
        nonlocal field,bits
        field=byte()|(byte()<<8);bits=16
    def bit():
        nonlocal field,bits
        value=field&1;field>>=1;bits-=1
        if not bits:refill()
        return value
    refill()
    while True:
        if bit():out.append(byte())
        else:
            if not bit():
                count=(bit()<<1)|bit();count+=2;offset=byte()-256
            else:
                low,high=byte(),byte();offset=((high&248)<<5)|low;offset-=8192
                count=high&7
                if count:count+=2
                else:
                    count=byte()
                    if not count:return bytes(out)
                    if count==1:continue
                    count+=1
            if -offset>len(out):raise ValueError('Kosinski back-reference before output')
            for _ in range(count):out.append(out[len(out)+offset])
        if len(out)>limit:raise ValueError('Kosinski output exceeds bound')

def sine_table():
    text=(SOURCE/'Sub.asm').read_text().split('SineTable:',1)[1].split('; ---',1)[0]
    values=[int(v,16) for v in re.findall(r'\$([0-9A-Fa-f]{4})',text)]
    assert len(values)==128
    return values

def parts(stage):
    p=SOURCE/f'Data/Stage {stage}'
    if stage==3:
        first=kosinski((p/'Stamps 1.kos').read_bytes());second=kosinski((p/'Stamps 2.kos').read_bytes())
        if len(first)>0xfe00:raise ValueError('secondary stamps overlap')
        stamps=bytes(512)+first+bytes(0xfe00-len(first))+second
    else:stamps=bytes(512)+kosinski((p/'Stamps.kos').read_bytes())
    stamp_map=kosinski((p/'Stamp Map.kos').read_bytes());types=(p/'Stamp Types.bin').read_bytes()
    assert len(stamps)%512==0 and len(stamps)<=0x1c000 and len(stamp_map)==32768
    # Stages 1/8 use FFFF in the first ten map rows. It addresses
    # stamp 511 in cleared, otherwise unused Word RAM (transparent).
    indices=[(v&2047)//4 for v, in struct.iter_unpack('>H',stamp_map) if v!=65535]
    assert max(indices)<len(stamps)//512 and max(indices)<len(types)
    colors=palette((p/'Palette.bin').read_bytes());start=(p/'Start Position.bin').read_bytes()
    assert len(colors)==64 and len(start)==6
    return [stamps,stamp_map,types,colors,start,(p/'Animations (Hazard).bin').read_bytes(),(p/'Animations (Fan).bin').read_bytes()]

def pack(stage):
    sections=parts(stage);header=16+8*len(sections);result=bytearray(header);result[:4]=b'SSP1'
    struct.pack_into('>III',result,4,stage,len(sections),0)
    for n,data in enumerate(sections):
        result.extend(bytes(-len(result)%4));struct.pack_into('>II',result,16+8*n,len(result),len(data));result.extend(data)
    struct.pack_into('>I',result,12,len(result));return bytes(result)

def main():
    OUT.mkdir(exist_ok=True,parents=True);(ROOT/'cd').mkdir(exist_ok=True)
    report=[]
    for stage in range(1,9):
        data=pack(stage);write_bytes(OUT/f'special{stage}.bin',data)
        write_bytes(ROOT/f'cd/SP{stage}.BIN',data+bytes(-len(data)%2048))
        report.append({'stage':stage,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'parts':[len(p) for p in parts(stage)]})
    write_text(OUT/'special-sine.inc','/* Original special-stage quarter sine table. */\nstatic const int16_t special_sines[128]={'+','.join(map(str,sine_table()))+'};\n')
    write_text(ROOT/'build/special-source.json',json.dumps({'source':'pinned scddisasm Special Stage/Sub.asm and Data','stages':report},indent=2)+'\n')
    print(json.dumps(report))
if __name__=='__main__':main()
