#!/usr/bin/env python3
"""Pack the original D.A. Garden data (DA Garden/Main.asm, Sub.asm, Track Titles.asm) for the Saturn build.

Art is Nemesis-decoded into Mega Drive tile bytes and the stamps and background mappings
are Kosinski-decoded. The Main CPU data tables (palette cycles, sprite mappings, track
info, volcano animation) are assembled from their .asm files in the original binary
layout. Every compressed file and every assembled table must occur exactly once in the
retail PLANET_M.MMD (Main CPU), PLANET_S.BIN (Sub CPU) or PLANET_D.BIN (track title art),
so the pack is the retail data of the region the port's soundtrack comes from: Japan
(JAPANESE-MUSIC.md; the user's disc, assets/private/sonic-cd-japan.cue). The track titles and
their X offsets then name the Japanese songs (opening "You Can Do Anything", ending "Cosmic
Eternity"). SCD_DAGARDEN_REGION=us builds the US pack instead.

DAGARDEN.BIN: 'DAG1', part count, then (offset, size) big-endian pairs; parts in PARTS
order. assets/generated/dagarden-parts.inc names the parts and the table labels (byte
offsets inside their part). The pack goes to cd/DAGARDEN.BIN.
"""
import hashlib,json,re,struct,sys
from pathlib import Path
from generated_io import write_bytes, write_text
from convert_assets import nemesis
from special_assets import kosinski
from extract_mmd import disc_files
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'.deps/scddisasm/src'
DAG=SRC/'DA Garden'
OUT=ROOT/'assets/generated'
import os
REGION_USA=os.environ.get('SCD_DAGARDEN_REGION','jp')=='us'

TITLES=['PPZ','PPZG','PPZB','CCZ','CCZG','CCZB','TTZ','TTZG','TTZB','QQZ','QQZG','QQZB','WWZ','WWZG','WWZB',
    'SSZ','SSZG','SSZB','MMZ','MMZG','MMZB','Final','LittlePlanet','GameOver','ZoneClear','Boss','Invincible','SpeedUp',
    'Title','SpecStg','Opening','Ending']

def number(token,labels=None,scope=''):
    token=token.strip()
    def atom(m):
        t=m.group(0)
        if t.startswith('$'):return str(int(t[1:],16))
        if t.startswith('.'):return str(labels[scope+t])
        if re.match(r'[A-Za-z_]',t):return str(labels[t])
        return t
    expr=re.sub(r'\$[0-9A-Fa-f]+|\.?[A-Za-z_]\w*|\d+',atom,token)
    return eval(expr,{'__builtins__':{}},{})

def region(text):
    out=[];stack=[]
    for line in text.splitlines():
        code=line.split(';',1)[0]
        if m:=re.match(r'\s+if\s+(.+)',code):
            assert 'REGION' in m[1],line
            usa=REGION_USA
            stack.append((not usa) if '<>USA' in m[1].replace(' ','') else usa if '=USA' in m[1].replace(' ','') else None)
            assert stack[-1] is not None,line
            continue
        if re.match(r'\s+else\b',code):stack[-1]=not stack[-1];continue
        if re.match(r'\s+endif\b',code):stack.pop();continue
        if all(stack):out.append(line)
    assert not stack
    return out

def assemble(items):
    """items: ('label',name) | ('file',path) | ('even',) | ('text',lines). Two passes: label offsets, then bytes."""
    lines=[]
    for item in items:
        if item[0]=='label':lines.append(item[1]+':')
        elif item[0]=='even':lines.append('\teven')
        elif item[0]=='file':lines+=region(Path(item[1]).read_text())
        else:lines+=item[1]
    def run(labels,emit):
        out=bytearray();scope=''
        for raw in lines:
            line=raw.split(';',1)[0].rstrip()
            if not line.strip():continue
            if m:=re.match(r'^(\.?\w+):\s*(.*)$',line):
                name=m[1]
                if name.startswith('.'):name=scope+name
                else:scope=name
                labels[name]=len(out)
                line='\t'+m[2] if m[2] else ''
                if not line.strip():continue
            if m:=re.match(r'\s+dc\.([bwl])\s+(.+)',line):
                size={'b':1,'w':2,'l':4}[m[1]]
                for t in m[2].split(','):
                    value=number(t,labels,scope) if emit else 0
                    out+=(value&((1<<(8*size))-1)).to_bytes(size,'big')
                continue
            if m:=re.match(r'\s+incbin\s+"([^"]+)"(.*)$',line):
                data=(SRC/m[1]).read_bytes();args=[number(a) for a in m[2].split(',')[1:]]
                if args:data=data[args[0]:args[0]+args[1]] if len(args)>1 else data[args[0]:]
                out+=data;continue
            if re.match(r'\s+even\b',line):
                if len(out)&1:out.append(0)
                continue
            raise ValueError(line)
        return bytes(out)
    labels={};run(labels,False);data=run(labels,True)
    return data,labels

def tables():
    """Main.asm data from Palette.asm (after its absolute PalCycleTable) to the volcano animation."""
    palette=region((DAG/'Data/Palette.asm').read_text())
    start=next(i for i,l in enumerate(palette) if l.startswith('SprPalCycTable:'))
    items=[('text',palette[start:])]
    items+=[('file',DAG/'Objects/Flicky/Data/Mappings.asm'),('even',),('label','MapSpr_Star'),('file',DAG/'Objects/Star/Data/Mappings.asm'),('even',),
        ('file',DAG/'Objects/UFO/Data/Mappings.asm'),('even',),('label','MapSpr_Eggman'),('file',DAG/'Objects/Eggman/Data/Mappings (Normal).asm'),('even',),
        ('label','MapSpr_EggmanTurn'),('file',DAG/'Objects/Eggman/Data/Mappings (Head Turn).asm'),('even',),
        ('file',DAG/'Objects/Metal Sonic/Data/Mappings.asm'),('even',),('label','MapSpr_Tails'),('file',DAG/'Objects/Tails/Data/Mappings (Straight).asm'),('even',),
        ('label','MapSpr_TailsDown'),('file',DAG/'Objects/Tails/Data/Mappings (Down).asm'),('even',),
        ('label','MapSpr_TailsUp'),('file',DAG/'Objects/Tails/Data/Mappings (Up).asm'),('even',),
        ('text',[l for l in region((DAG/'Track Info.asm').read_text()) if 'EQU' not in l]),
        ('label','MapSpr_TrackTitle'),('file',DAG/'Objects/Track Title/Data/Mappings.asm'),
        ('file',DAG/'Data/Volcano Animation.asm')]
    return assemble(items)

def title_art_files():
    text='\n'.join(region((DAG/'Track Titles.asm').read_text()))
    return {m[1]:m[2] for m in re.finditer(r'Art_Trk(\w+):\s*\n\s*incbin\s+"([^"]+)"',text)}

PARTS=[('stamps-present','DA Garden/Data/Stamps (Present).kos','kos','s'),('stamps-good','DA Garden/Data/Stamps (Good Future).kos','kos','s'),
    ('stamps-bad','DA Garden/Data/Stamps (Bad Future).kos','kos','s'),('stamps-anim','DA Garden/Data/Stamps (Animation, Present, Good Future).kos','kos','s'),
    ('stamps-anim-bad','DA Garden/Data/Stamps (Animation, Bad Future).kos','kos','s'),
    ('stamp-map-present','DA Garden/Data/Stamp Map (Present).bin','raw','s'),('stamp-map-good','DA Garden/Data/Stamp Map (Good Future).bin','raw','s'),
    ('stamp-map-bad','DA Garden/Data/Stamp Map (Bad Future).bin','raw','s'),
    ('art-background','DA Garden/Data/Art (Background).nem','nem','m'),('map-background','DA Garden/Data/Background Mappings.kos','kos','m'),
    ('art-flicky','DA Garden/Objects/Flicky/Data/Art.nem','nem','m'),('art-star','DA Garden/Objects/Star/Data/Art.nem','nem','m'),
    ('art-ufo','DA Garden/Objects/UFO/Data/Art.nem','nem','m'),('art-eggman','DA Garden/Objects/Eggman/Data/Art.nem','nem','m'),
    ('art-metal','DA Garden/Objects/Metal Sonic/Data/Art.nem','nem','m'),('art-tails','DA Garden/Objects/Tails/Data/Art.nem','nem','m')]

def main():
    if REGION_USA:disc=disc_files((ROOT/'build/retail/sonic.iso').read_bytes())
    else:
        from dagarden_retail import japanese_planet
        disc=japanese_planet()
    retail={'m':disc['PLANET_M.MMD'],'s':disc['PLANET_S.BIN'],'d':disc['PLANET_D.BIN']}
    blobs=[];names=[];nem_sizes=[];report={'region':'us' if REGION_USA else 'jp','parts':[],'retail':{k:hashlib.sha256(disc[k]).hexdigest() for k in ('PLANET_M.MMD','PLANET_S.BIN','PLANET_D.BIN')}}
    def add(name,data,source):
        blobs.append(data);names.append(name)
        report['parts'].append({'name':name,'source':source,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    for name,path,kind,program in PARTS:
        raw=(SRC/path).read_bytes()
        assert retail[program].count(raw)==1,(name,program,retail[program].count(raw))
        add(name,nemesis(raw) if kind=='nem' else kosinski(raw) if kind=='kos' else raw,path);nem_sizes.append(len(raw) if kind=='nem' else 0)
    data,labels=tables();tables_bytes=len(data)
    assert retail['m'].count(data)==1,('tables',retail['m'].count(data))
    add('tables',data,'Palette.asm .. Volcano Animation.asm');nem_sizes.append(0)
    files=title_art_files()
    for title in TITLES:
        raw=(SRC/files[title]).read_bytes()
        assert retail['d'].count(raw)==1,(title,retail['d'].count(raw))
        add('title-'+title.lower(),nemesis(raw),files[title]);nem_sizes.append(len(raw))
    assert len(blobs[0])==25600 and len(blobs[3])==12800 and len(blobs[9])==1792
    header=bytearray(b'DAG1'+struct.pack('>I',len(blobs)));offset=8+8*len(blobs);body=bytearray()
    for data in blobs:
        header+=struct.pack('>II',offset+len(body),len(data));body+=data
        body+=bytes(-len(body)%4)
    pack=bytes(header+body)
    write_bytes(OUT/'dagarden.bin',pack);write_bytes(ROOT/'cd/DAGARDEN.BIN',pack)
    lines=['/* Generated by tools/dagarden_assets.py from DA Garden/Main.asm, Sub.asm and Track Titles.asm (%s). */'%('USA' if REGION_USA else 'Japan'),
        '#define DG_PART_COUNT %du'%len(blobs)]
    lines+=['#define DG_PART_%s %du'%(name.upper().replace('-','_'),i) for i,name in enumerate(names)]
    lines+=['#define DG_PART_TITLE_FIRST %du'%names.index('title-ppz'),'#define DG_TRACKS %du'%len(TITLES)]
    # Nemesis (compressed) bytes of each part: the LoadArt lag model (src/dagarden.c) weighs them.
    lines.append('#define DG_PART_NEM_BYTES {%s}'%','.join(map(str,nem_sizes)))
    keep=['SprPalCycTable','PalCyc_Sprites0','PalCyc_Sprites1','Pal_SelMenu','Pal_DAGarden','PalCyc_PlanetPresent','PalCyc_BgPresentGF',
        'PalCyc_PlanetGoodFut','PalCyc_PlanetBadFut','PalCyc_BgBadFuture','PalCycleTimes','MapSpr_Flicky','MapSpr_FlickySlow','MapSpr_FlickyCatchUp',
        'MapSpr_FlickyGlide','MapSpr_Star','MapSpr_UFO','MapSpr_UFODown','MapSpr_UFOUp','MapSpr_Eggman','MapSpr_EggmanTurn','MapSpr_MetalSonic',
        'MapSpr_MetalSonicBackUp','MapSpr_Tails','MapSpr_TailsDown','MapSpr_TailsUp','TrackInfo','MapSpr_TrackTitle','VolcanoAnimStamps','VolcanoAnimTimes']
    for k in keep:lines.append('#define DG_L_%s 0x%04Xu'%(k,labels[k]))
    lines.append('#define DG_TABLES_BYTES %du'%tables_bytes)
    write_text(OUT/'dagarden-parts.inc','\n'.join(lines)+'\n')
    report['pack_bytes']=len(pack);report['sha256']=hashlib.sha256(pack).hexdigest();report['labels']={k:labels[k] for k in keep}
    (ROOT/'build').mkdir(exist_ok=True);write_text(ROOT/'build/dagarden-assets.json',json.dumps(report,indent=2)+'\n')
    print(f'D.A. Garden pack: {len(blobs)} parts, {len(pack)} bytes; every compressed file and table found once in the retail programs')

if __name__=='__main__':main()
