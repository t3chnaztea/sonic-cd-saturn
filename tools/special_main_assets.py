#!/usr/bin/env python3
"""Special Stage Main CPU data: palettes, VRAM art, tilemaps and HUD tables.

One pack per stage (cd/SSM1-8.BIN). Values come from the pinned Special Stage Main.asm and Stage Data.asm tables;
only the layout of the Saturn pack is new. The stage 1 and 6 files carry the attract demo input
(Main.asm Stage1Demo/Stage6Demo, NTSC, decompressed) right after the pack's declared size.
"""
import hashlib,json,re,struct
from special_assets import ROOT,SOURCE,OUT,kosinski
from convert_assets import nemesis
from generated_io import write_bytes, write_text
MAIN=SOURCE/'Main.asm'
def number(text):
    text=text.strip()
    return eval(re.sub(r'\$([0-9A-Fa-f]+)',r'0x\1',text).replace('%','0b'),{})
def blocks(text):
    """Label -> tokens for dc.b/dc.w/dc.l data, incbin paths and VDPCMD longs (USA build)."""
    result={};current=None;parent=None;stack=[]
    for raw in text.splitlines():
        line=raw.split(';',1)[0].strip()
        if not line:continue
        if line.startswith('if '):stack.append(line in ('if REGION=USA','if REGION<>EUROPE'));continue
        if line=='else':stack[-1]=not stack[-1];continue
        if line=='endif':stack.pop();continue
        if not all(stack):continue
        m=re.match(r'(\.?[A-Za-z_]\w*):(.*)',line)
        if m:
            name=m[1]
            if name.startswith('.'):name=f'{parent}{name}'
            else:parent=name
            current=result.setdefault(name,[]);line=m[2].strip()
            if not line:continue
        if current is None:continue
        m=re.fullmatch(r'dc\.([bwl])\s+(.+)',line)
        if m:current.extend((m[1],value.strip()) for value in m[2].split(','));continue
        m=re.fullmatch(r'incbin\s+"([^"]+)"',line)
        if m:current.append(('incbin',m[1]));continue
        m=re.fullmatch(r'VDPCMD\s+dc\.l,\s*\$([0-9A-Fa-f]+),VRAM,WRITE',line)
        if m:current.append(('vram',int(m[1],16)))
    return result
def vdp_address(long):
    return (long>>16&0x3fff)|(long&3)<<14
def art_addresses(text):
    lines=[l.split(';',1)[0].strip() for l in text.splitlines()];found={}
    for i,line in enumerate(lines):
        m=re.fullmatch(r'VDPCMD\s+move\.l,\$([0-9A-Fa-f]+),VRAM,WRITE,VDPCTRL',line)
        if not m:continue
        art=next(l for l in lines[i+1:] if l)
        label=re.fullmatch(r'lea\s+(Art_\w+)(?:\(pc\))?,a0',art)
        if label:found.setdefault(label[1],int(m[1],16))
    return found
def map_words(tokens):
    kind=number(tokens[0][1])
    if kind:
        assert tokens[1][0]=='incbin';raw=kosinski((SOURCE.parent/tokens[1][1]).read_bytes())
        return list(struct.unpack(f'>{len(raw)//2}H',raw))
    if len(tokens)>1 and tokens[1][0]=='incbin':
        raw=(SOURCE.parent/tokens[1][1]).read_bytes();return list(struct.unpack(f'>{len(raw)//2}H',raw[:len(raw)//2*2]))
    return [number(value)&0xffff for width,value in tokens[1:] if width=='w']
# LoadSS1Data..LoadSS8Data: background art and tilemap IDs (d5 bytes).
STAGE_ART={1:['Art_SS1BG'],2:['Art_SS2BG'],3:['Art_SS3BG'],4:['Art_SS4BG'],5:['Art_SS5BG'],6:['Art_SS6BG','Art_SS6BGWater'],7:['Art_SS7BG'],8:['Art_SS8BG']}
STAGE_MAPS={1:[0x14,0x15,0x16,0x17,0x43],2:[1,2,3,4,5],3:[6,7,8,9,0xa,0xb,0x28],4:[0xc,0xd,0xe,0xf,0x10,0x11],5:[0x18,0x19,0x1a,0x1b,0x1c],6:[0x1d,0x1e,0x1f,0x20,0x4d],7:[0x21,0x22,0x23,0x24,0x25,0x26,0x27],8:[0x4e,0x4f]}
# PalCycle_SS2..SS7 tables in section 8, in this order (word counts).
CYCLES=[('PalCycle_SS2.Cycle',8),('PalCycle_SS3.Cycle1',24),('PalCycle_SS3.Cycle2',6),('PalCycle_SS4.Cycle1',16),('PalCycle_SS4.Cycle2',8),
    ('PalCycle_SS5.Cycle1',7),('PalCycle_SS5.Cycle2',26),('PalCycle_SS5.Cycle3',26),('PalCycle_SS5.Cycle4',28),('PalCycle_SS6.Cycle1',26),('PalCycle_SS6.Cycle2',12),('PalCycle_SS7.Cycle',12)]
def pack(stage=1):
    main_text=MAIN.read_text();data=blocks(main_text)|blocks((SOURCE/'Stage Data.asm').read_text())
    addresses=art_addresses(main_text)
    # Tilemap table: one 12-byte source record per ID, starting at ID 1.
    table=main_text.split('\n.Tilemaps:',1)[1].split('\nDrawTilemap:',1)[0];records=[];stack=[]
    for raw in table.splitlines():
        line=raw.split(';',1)[0].strip()
        if not line or line.startswith('; '):continue
        if line.startswith('if '):stack.append(line=='if REGION=USA');continue
        if line=='else':stack[-1]=not stack[-1];continue
        if line=='endif':stack.pop();continue
        if not all(stack):continue
        m=re.fullmatch(r'dc\.l\s+(Map_\w+)',line)
        if m:records.append({'map':m[1]});continue
        m=re.fullmatch(r'VDPCMD\s+dc\.l,\$([0-9A-Fa-f]+),VRAM,WRITE',line) or re.fullmatch(r'dc\.l\s+\$([0-9A-Fa-f]+)',line)
        if m:
            value=int(m[1],16);records[-1]['address']=value if value<0x10000 else vdp_address(value);continue
        m=re.fullmatch(r'dc\.w\s+(.+)',line)
        if m:records[-1]['width' if 'width' not in records[-1] else 'height']=number(m[1])+1
    assert len(records)==0x4f and all(len(r)==4 for r in records)
    # One pack per stage: HUD, this stage's background and the results screen.
    wanted={0x12,0x13}|set(STAGE_MAPS[stage])|set(range(0x29,0x43))|set(range(0x44,0x4d))
    words=bytearray();entries=bytearray();maps=[]
    for id,record in enumerate(records,1):
        offset=0xffffffff
        if id in wanted:
            values=map_words(data[record['map']]);assert len(values)>=record['width']*record['height'],(id,record,len(values))
            offset=len(words)//2;words.extend(struct.pack(f'>{record["width"]*record["height"]}H',*values[:record['width']*record['height']]))
        entries.extend(struct.pack('>HBBI',record['address'],record['width'],record['height'],offset));maps.append(record|{'id':id,'included':id in wanted})
    def incbin(label):
        (kind,path),=data[label];assert kind=='incbin';return (SOURCE.parent/path).read_bytes()
    palettes=incbin('Pal_Stage')+incbin('Pal_Results')+b''.join(incbin(f'Pal_SS{n}') for n in range(1,9))
    palettes+=struct.pack('>40H',*(number(v) for _,v in data['TimeStonePalettes']))
    assert len(palettes)==(64+64+8*32+40)*2
    # Tile groups: 0 loads at stage start (Start, LoadSSnData), 1 on the results screen.
    labels=[('Art_HUD',0)]+[(label,0) for label in STAGE_ART[stage]]+[('Art_Results',1),('Art_ExtraPlayersText',1)]
    tiles=bytearray(struct.pack('>H',len(labels)));arts=[]
    for label,group in labels:
        raw=nemesis(incbin(label));first=addresses[label]//32;assert addresses[label]%32==0
        tiles.extend(struct.pack('>HHH',first,len(raw)//32,group));tiles.extend(raw);arts.append({'label':label,'vram':addresses[label],'first_tile':first,'tiles':len(raw)//32,'group':group,'sha256':hashlib.sha256(raw).hexdigest()})
    hud=struct.pack('>24H',*(number(v) for label in ['NumTilesUpper','NumTilesLower'] for _,v in data[label]))
    results=struct.pack('>20H',*(number(v) for label in ['DrawResultsNum.NumTilesUpper','DrawResultsNum.NumTilesLower'] for _,v in data[label]))
    cycle=bytes(number(v) for _,v in data['PalCycle_SS1.Cycle']);assert len(cycle)==1008
    icons=bytes(number(v) for _,v in data['DrawExtraPlayers.IconMaps']);assert len(icons)==10
    cycles=bytearray()
    for label,count in CYCLES:
        values=[number(v) for w,v in data[label] if w=='w'];assert len(values)==count,(label,len(values));cycles.extend(struct.pack(f'>{count}H',*values))
    speeds=[number(v) for w,v in data['SS5BGScrollSpeeds'] if w=='l'];wave=[number(v)&255 for w,v in data['SS6BGWave'] if w=='b']
    assert len(speeds)==111 and len(wave)==128,(len(speeds),len(wave))
    scroll=struct.pack('>111I',*speeds)+bytes(wave)
    info=struct.pack('>H',stage)
    sections=[palettes,bytes(tiles),bytes(entries),bytes(words),hud,results,cycle,icons,bytes(cycles),scroll,info]
    header=bytearray(b'SSM2'+bytes(8+8*len(sections)));offset=len(header);body=bytearray()
    for i,section in enumerate(sections):
        body.extend(bytes(-len(body)%2));struct.pack_into('>II',header,12+i*8,offset+len(body),len(section));body.extend(section)
    blob=bytes(header+body);struct.pack_into('>II',header,4,len(blob),len(sections));blob=bytes(header+body)
    return blob,{'stage':stage,'arts':arts,'tilemaps':maps,'art_addresses':addresses}
def demo(stage):
    """Main.asm demoData for the stage 1 or 6 attract demo: one pad byte per ReadController call."""
    data=kosinski((SOURCE/f'Data/Stage {stage}/Demo (NTSC).kos').read_bytes())
    assert 0<len(data)<=0x700,(stage,len(data)) # demoData rs.b $700
    return data
def main():
    report={'source':'Pinned Special Stage Main.asm/Stage Data.asm palettes, HUD, stage background, palette cycle, scroll and results art and tilemaps','stages':{}}
    for stage in range(1,9):
        blob,details=pack(stage);write_bytes(OUT/f'special-main-{stage}.bin',blob)
        disc=blob+(demo(stage) if stage in (1,6) else b'');write_bytes(ROOT/f'cd/SSM{stage}.BIN',disc+bytes(-len(disc)%2048))
        report['stages'][stage]={'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest()}|details
    (ROOT/'cd/SSM.BIN').unlink(missing_ok=True)
    write_text(ROOT/'build/special-main-source.json',json.dumps(report,indent=2)+'\n')
    print(json.dumps({stage:[r['bytes'],r['sha256'][:12],[(a['label'],hex(a['first_tile']),a['tiles']) for a in r['arts']]] for stage,r in report['stages'].items()}))
if __name__=='__main__':main()
