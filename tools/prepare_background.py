#!/usr/bin/env python3
"""Generate palette scripts and row addressing directly from pinned PPZ1 ASM."""
import re,struct
from convert_assets import ROOT,DATA,OUT,palette
out=['/* Generated original palette cycles and BG row modes. */']
for era,name in enumerate(['Present','Past','Good Future','Bad Future']):
    text=(DATA/f'Palmtree Panic/Palette Cycle ({name}).asm').read_text();blocks={};key=None
    for raw in text.splitlines():
        line=raw.split(';')[0].strip()
        m=re.match(r'(PalCycle\w+):',line)
        if m:key=m[1];blocks[key]=[]
        m=re.search(r'dc\.[bw]\s+(.+)',line)
        if m and key:blocks[key]+=[int(v.strip().replace('$','0x'),0) for v in m[1].split(',')]
    cycles=[]
    for k,v in blocks.items():
        if 'Script' not in k:continue
        color_key=k.replace('Script','Colors')
        colors=blocks[color_key]
        index,count=v[:2];assert len(v)==2+count*2
        steps=[(v[2+j*2]+1,colors[v[3+j*2]]) for j in range(count)]
        # Script increments the frame from zero before the first write.
        steps=steps[1:]+steps[:1]
        cycles.append((index,steps))
    for k,index,hold in [('PalCycleData1',53,8),('PalCycleData2',44,6)]:
        if k in blocks:
            colors=blocks[k]
            for n in range(4):cycles.append((index+n,[(hold,colors[j*4+n]) for j in [1,2,0]]))
    for n,(index,steps) in enumerate(cycles):
        entries=','.join('{%d,%d}'%(hold,int.from_bytes(palette(struct.pack('>H',color)),'big')) for hold,color in steps)
        out.append(f'static const pal_step pal_{era}_{n}[]={{'+entries+'};')
    out.append(f'static const pal_cycle cycles_{era}[]={{'+','.join('{%d,%d,pal_%d_%d}'%(index,len(steps),era,n) for n,(index,steps) in enumerate(cycles))+'};')
    scroll=(DATA/f'Palmtree Panic/Scroll (Act 1 {name}).asm').read_text()
    rows=[]
    for length,mode in re.findall(r'BGSECT\s+(\d+),\s*BG(STATIC|DYNAMIC[123])',scroll):rows += [0 if mode=='STATIC' else int(mode[-1])]*(int(length)//16)
    rows=rows[1:];out.append(f'static const unsigned char bg_rows_{era}[]={{'+','.join(map(str,rows))+'};')
out.append('static const pal_cycle *const era_cycles[]={cycles_0,cycles_1,cycles_2,cycles_3};')
out.append('static const unsigned era_cycle_counts[]={'+','.join(f'sizeof(cycles_{i})/sizeof(*cycles_{i})' for i in range(4))+'};')
out.append('static const unsigned char *const era_bg_rows[]={bg_rows_0,bg_rows_1,bg_rows_2,bg_rows_3};')
out.append('static const unsigned era_bg_row_counts[]={'+','.join(f'sizeof(bg_rows_{i})' for i in range(4))+'};')
from cc_palette_source import generate as cc_palette_tables
out += cc_palette_tables()
(OUT/'background.inc').write_text('\n'.join(out)+'\n')
print('Original palette scripts and four era row-mode tables generated')

warp=DATA.parent/'Time Warp Cutscene/Data'
from convert_assets import nemesis
raw=nemesis((warp/'Art.nem').read_bytes())
# Compact package: 128-byte palette, 2240-byte 40x28 map, remaining tile art.
(OUT/'warp.bin').write_bytes((warp/'Palette.bin').read_bytes().ljust(128,b'\0')+(warp/'Background Mappings.bin').read_bytes()+raw)
