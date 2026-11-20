#!/usr/bin/env python3
"""Pack the original title screen data (Title Screen/Main.asm, Sub.asm) for the Saturn build.

Art is Nemesis-decoded into Mega Drive tile bytes, the cloud stamps and stamp map are
Kosinski-decoded, and sprite mappings are assembled from their .asm files in the original
binary layout. Every compressed file must occur exactly once in the retail TITLEM.MMD
(Main CPU) or TITLES.BIN (Sub CPU), so the pack is the retail USA data. Small tables
(sine, water palette cycle, planet hover, arm and arrow frames, object positions) are
read from the source into assets/generated/title-tables.inc.

TITLE.BIN: 'TTL1', part count, then (offset, size) big-endian pairs; parts in PARTS order.
"""
import hashlib,json,re,struct
from pathlib import Path
from generated_io import write_bytes, write_text
from convert_assets import nemesis
from special_assets import kosinski,sine_table
from extract_mmd import disc_files
ROOT=Path(__file__).resolve().parents[1]
from scd_source import SRC as SCD_SRC
SRC=SCD_SRC/'Title Screen'
OUT=ROOT/'assets/generated'
DATA=SRC/'Data';OBJ=SRC/'Objects'
# Mega Drive VRAM address of each art load in Main.asm (USA), for reference in the C code.
PARTS=[('palette-init','Data/Palette (Initialization).bin','raw'),('palette','Data/Palette.bin','raw'),
    ('map-emblem','Data/Emblem Mappings.bin','raw'),('map-water','Data/Water Mappings.bin','raw'),('map-mountains','Data/Moutains Mappings.bin','raw'),
    ('stamps','Data/Cloud Stamps.kos','kos'),('stamp-map','Data/Cloud Stamp Map.kos','kos'),
    ('art-water','Data/Water Art.nem','nem'),('art-mountains','Data/Moutains Art.nem','nem'),('art-emblem','Data/Emblem Art.nem','nem'),
    ('art-banner','Objects/Banner/Data/Art.nem','nem'),('art-planet','Objects/Planet/Data/Art.nem','nem'),('art-sonic','Objects/Sonic/Data/Art.nem','nem'),
    ('art-solid','Data/Solid Color Art.nem','nem'),
    ('art-new-game','Objects/Menu/Data/Art (Text, New Game).nem','nem'),('art-continue','Objects/Menu/Data/Art (Text, Continue).nem','nem'),
    ('art-time-attack','Objects/Menu/Data/Art (Text, Time Attack).nem','nem'),('art-ram-data','Objects/Menu/Data/Art (Text, RAM Data).nem','nem'),
    ('art-da-garden','Objects/Menu/Data/Art (Text, D.A. Garden).nem','nem'),('art-visual-mode','Objects/Menu/Data/Art (Text, Visual Mode).nem','nem'),
    ('art-press-start','Objects/Menu/Data/Art (Text, Press Start).nem','nem'),('art-arrow','Objects/Menu/Data/Art (Arrow).nem','nem'),
    ('art-copyright','Objects/Copyright/Data/Art (Copyright, USA).nem','nem'),('art-tm','Objects/Copyright/Data/Art (TM, USA).nem','nem'),
    ('map-sonic','Objects/Sonic/Data/Mappings.asm','asm'),('map-banner','Objects/Banner/Data/Mappings.asm','asm'),('map-planet','Objects/Planet/Data/Mappings.asm','asm'),
    ('map-menu','Objects/Menu/Data/Mappings (Menu).asm','asm'),('map-arrow','Objects/Menu/Data/Mappings (Arrow).asm','asm'),
    ('map-copyright','Objects/Copyright/Data/Mappings (Copyright, USA).asm','asm'),('map-tm','Objects/Copyright/Data/Mappings (TM).asm','asm')]

def number(token):
    token=token.strip()
    value=int(token[1:],16) if token.startswith('$') else int(token)
    return value

def mappings(text):
    """Assemble a sprite mapping file: word offsets from the table start, then frames, each padded even."""
    table=[];frames={};order=[];current=None
    for raw in text.splitlines():
        line=raw.split(';',1)[0].rstrip()
        if m:=re.match(r'^(\.\w+):',line):current=m[1];continue
        if m:=re.match(r'\s+dc\.w\s+(\.\w+)-\S+',line):table.append(m[1]);continue
        if m:=re.match(r'\s+dc\.b\s+(.+)',line):
            if current not in frames:frames[current]=bytearray();order.append(current)
            frames[current]+=bytes(number(t)&255 for t in m[1].split(','))
    out=bytearray(len(table)*2);offsets={}
    for name in order:
        offsets[name]=len(out);out+=frames[name]
        if len(out)&1:out.append(0)
    for i,name in enumerate(table):
        struct.pack_into('>H',out,i*2,offsets[name])
        frame=out[offsets[name]:];assert len(frame)>=1+frame[0]*5,(name,frame[0])
    return bytes(out),len(table)

def label_bytes(text,label):
    """dc.b/dc.w values after a local label up to the next label."""
    body=text.split(label+':',1)[1];values=[]
    for raw in body.splitlines()[1:]:
        line=raw.split(';',1)[0].rstrip()
        if re.match(r'^\S',line) or re.match(r'^\s*\.\w+:',line):break
        if m:=re.match(r'\s+dc\.([bw])\s+(.+)',line):values+=[(m[1],number(t)) for t in m[2].split(',')]
    return values

def main():
    iso=(ROOT/'build/retail/sonic.iso').read_bytes();disc=disc_files(iso)
    retail={'TITLEM.MMD':disc['TITLEM.MMD'],'TITLES.BIN':disc['TITLES.BIN']}
    blobs=[];report={'parts':[],'retail':{k:hashlib.sha256(v).hexdigest() for k,v in retail.items()}}
    for name,path,kind in PARTS:
        raw=(SRC/path).read_bytes()
        if kind in ('nem','kos','raw') and len(raw)>=24:
            program='TITLES.BIN' if kind=='kos' else 'TITLEM.MMD'
            assert retail[program].count(raw)==1,(name,program,retail[program].count(raw))
        if kind=='nem':data=nemesis(raw)
        elif kind=='kos':data=kosinski(raw)
        elif kind=='asm':data,_=mappings(raw.decode())
        else:data=raw
        if name=='stamps':data=bytes(512)+data # Stamp 0 is Word RAM $000-$1FF (cleared); LoadCloudsData decodes to $200.
        blobs.append(data);report['parts'].append({'name':name,'source':path,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    assert len(blobs[5])==512+16384 and len(blobs[6])==32768 and len(blobs[2])==26*19*2 and len(blobs[3])==32*8 and len(blobs[4])==32*9
    header=bytearray(b'TTL1'+struct.pack('>I',len(blobs)));offset=8+8*len(blobs);body=bytearray()
    for data in blobs:
        header+=struct.pack('>II',offset+len(body),len(data));body+=data
        body+=bytes(-len(body)%4)
    pack=bytes(header+body);write_bytes(OUT/'title.bin',pack)
    main_text=(SRC/'Main.asm').read_text();sub_text=(SRC/'Sub.asm').read_text()
    sines=[v for _,v in label_bytes(sub_text,'SineTable')];assert sines==list(sine_table()),'title sine table differs from the special stage table'
    water=[v for _,v in label_bytes(main_text,'.WaterPalCycle')];assert len(water)==12
    planet=[v-256 if v>127 else v for _,v in label_bytes((OBJ/'Planet/Main.asm').read_text(),'.Offsets')];assert len(planet)==32
    sonic=(OBJ/'Sonic/Main.asm').read_text();arm=[v for _,v in label_bytes(sonic,'.Frames')];assert len(arm)==16
    arrows=(OBJ/'Menu/Main.asm').read_text().split('ObjMenuArrow_Left:',1)
    right=[v for _,v in label_bytes(arrows[0].split('ObjMenuArrow_Right:',1)[1],'.Frames')];left=[v for _,v in label_bytes(arrows[1],'.Frames')]
    assert right==[4,5,6] and left==[1,2,3]
    lines=['/* Generated by tools/title_assets.py from Title Screen/Main.asm, Sub.asm and Objects. */',
        '#define TITLE_PART_COUNT %du'%len(blobs)]
    lines+=['#define TITLE_PART_%s %du'%(name.upper().replace('-','_'),i) for i,(name,_,_) in enumerate(PARTS)]
    write_text(OUT/'title-parts.inc','\n'.join(lines)+'\n')
    lines+=['static const uint16_t title_water_cycle[12]={%s};'%','.join('0x%03X'%v for v in water),
        'static const int8_t title_planet_offsets[32]={%s};'%','.join(map(str,planet)),
        'static const uint8_t title_arm_frames[16]={%s};'%','.join(map(str,arm)),
        'static const uint8_t title_arrow_frames[2][3]={{%s},{%s}};'%(','.join(map(str,left)),','.join(map(str,right)))]
    write_text(OUT/'title-tables.inc','\n'.join(lines)+'\n')
    report['pack_bytes']=len(pack);report['sha256']=hashlib.sha256(pack).hexdigest()
    write_text(ROOT/'build/title-assets.json',json.dumps(report,indent=2)+'\n')
    print(f'Title pack: {len(blobs)} parts, {len(pack)} bytes; every compressed file found once in the retail title programs')

if __name__=='__main__':main()
