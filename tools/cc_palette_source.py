"""Extract CC palette scripts; require identical script/color bytes in retail."""
import hashlib
import json
import re
import struct
from pathlib import Path
from convert_assets import ROOT, palette
from extract_mmd import disc_files


def generate():
    files=disc_files((ROOT/'build/retail/sonic.iso').read_bytes())
    out=['/* CC palette scripts: PC source cross-checked against Sega CD data. */']
    report={}
    for era,letter in enumerate('ABCD'):
        path=ROOT/f'.deps/soniccd/src/R3/COL3{letter}.C'; source=path.read_text()
        data=files[f'R31{letter}__.MMD']; cycles=[];proof=[]
        tables={m[1]:bytes(int(v) for v in re.findall(r'\d+',m[2])) for m in
                re.finditer(r'unsigned char (col3\w+cnt)\[\d+\] = \{(.*?)\};',source,re.S)}
        for name,table in tables.items():
            color_name=name[:-3]+'col'
            body=re.search(r'PALETTEENTRY '+color_name+r'\[\d+\] = \{(.*?)\};',source,re.S)[1]
            values=list(map(int,re.findall(r'\d+',body)))
            assert len(values)%4==0 and all(v%32==0 for i,v in enumerate(values) if i%4!=3)
            colors=b''.join(struct.pack('>H',values[i]//16 | values[i+1]//16<<4 | values[i+2]//16<<8)
                            for i in range(0,len(values),4))
            assert table in data and colors in data,(letter,name)
            assert re.search(r'clchg_sub0\(&clchgtim\[\d+\], &clchgcnt\[\d+\], '+name+', '+color_name+r'\)',source)
            index,count=table[:2];assert len(table)==count*2+2
            converted=struct.unpack('>'+str(len(colors)//2)+'H',palette(colors))
            steps=[(table[2+i*2]+1,converted[table[3+i*2]]) for i in range(count)]
            steps=steps[1:]+steps[:1] # first dispatch increments the zero counter
            n=len(cycles)
            out.append(f'static const pal_step cc_pal_{era}_{n}[]={{'+','.join('{%d,%d}'%s for s in steps)+'};')
            cycles.append('{%d,%d,cc_pal_%d_%d}'%(index,count,era,n))
            proof.append(dict(name=name,index=index,script_offset=data.index(table),color_offset=data.index(colors),
                              script_sha256=hashlib.sha256(table).hexdigest(),colors_sha256=hashlib.sha256(colors).hexdigest()))
        if not cycles:
            assert re.search(r'void clchgctr\(void\) \{\}',source)
        else:
            out.append(f'static const pal_cycle cc_cycles_{era}[]={{'+','.join(cycles)+'};')
        report[letter]=dict(source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                           program_sha256=hashlib.sha256(data).hexdigest(),cycles=proof)
    out.append('static const pal_cycle *const cc_cycles[]={cc_cycles_0,0,cc_cycles_2,cc_cycles_3};')
    out.append('static const unsigned cc_cycle_counts[]={4,0,2,3};')
    folder=ROOT/'build/cc1';folder.mkdir(exist_ok=True)
    (folder/'palette-source.json').write_text(json.dumps(report,indent=2)+'\n')
    return out


if __name__=='__main__':
    print('\n'.join(generate()))
