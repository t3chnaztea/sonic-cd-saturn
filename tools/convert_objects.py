#!/usr/bin/env python3
"""Decode Sega CD placement records and original object art into bounded assets."""
import collections,json,struct
from convert_assets import ROOT,DATA,OUT,nemesis,palette,assembly_frames
LEGACY={10,16,27,38}
V7={25,34,45,61,62,63,64}
SUPPORTED=LEGACY|V7|{42,44,18,33,19,54,22,23,32,7,49,9,13,53,15,50,51,52,36,46,47,41,40,21,66,20}
DELTAS=[(16,0),(24,0),(32,0),(0,16),(0,24),(0,32),(16,16),(24,24),(32,32),(-16,16),(-24,24),(-32,32),(16,8),(24,16),(-16,8),(-24,16)]
def placements(data,ordered=True,extra=None,retail_order=False,keep_order=True,saved_kind=False):
    # keep_order (default): the retail x-sorted record order, which Object
    # Spawner.asm walks and slot order follows. False restores the old
    # by-type grouping (no caller uses it).
    # extra: zone object types beyond Palmtree Panic's, from tools/object_layouts.py,
    # as {type: keeps its secondary byte}. They sort after every existing group,
    # so a Palmtree Panic layout, which has none, comes out exactly as before.
    extra=extra or {}
    if len(data)%8:raise ValueError('truncated object record')
    result=[];unsupported=collections.Counter();last=-1;terminated=False
    for x,y,kind,sub,eras,secondary in struct.iter_unpack('>HHBBBB',data):
        if x==65535:
            terminated=True;break
        if ordered and x<last:raise ValueError('unsorted layout')
        # Retail records use bit 7 as a flag. Translated zone layouts
        # (extra) carry port ids, whose zone-local range reaches 254.
        saved=kind&128
        last=x;kind&=255 if extra else 127
        if (kind not in SUPPORTED and kind not in extra) or (kind==25 and sub not in (0,1,2,3,4,5,6,7,8,9)):unsupported[kind]+=1;continue
        if secondary and not ((kind in (7,42) and secondary==1) or extra.get(kind)):raise ValueError('unsupported secondary subtype')
        if kind==42 and secondary:sub|=128
        flags=y>>14
        # retail_order (Tidal Tempest): bit 12 of Y carries the retail ID's bit 7
        # (the record has a saved-flags entry, Object Spawner.asm SpawnObject),
        # kept as flags bit 5; expanded ring-group members after the first get
        # flags bit 4 (ObjRing_Init spawns them, Ring/Main.asm).
        if retail_order and y&4096:flags|=32
        # saved_kind (Palmtree Panic retail layouts): the ID's bit 7 itself.
        if retail_order and saved_kind and saved:flags|=32
        y&=4095
        if x>=16384 or y>=2048:raise ValueError('object outside stage')
        if kind==44:
            offsets=[64,128,-64,-128,0,96,-96]
            # retail_order: one layout record spawns the whole plant group, so
            # the pieces after the first are group members (flags bit 4).
            for k,n in enumerate([0,1,4,5,6] if sub&1 else range(7)):
                result.append((x+offsets[n],y,kind,n,flags|(16 if retail_order and k else 0),eras>>5))
            continue
        count=min(sub&7,6)+1 if kind==16 else 1
        dx,dy=DELTAS[sub>>4] if kind==16 else (0,0)
        for i in range(count):
            rx,ry=x+dx*i,y+dy*i
            if not(0<=rx<16384 and 0<=ry<2048):raise ValueError('expanded ring outside stage')
            result.append((rx,ry,kind,sub,flags|(16 if retail_order and i else 0),eras>>5)+((secondary,) if kind==7 or extra.get(kind) else ()))
    if not terminated:raise ValueError('missing object terminator')
    if len(result)>1024:raise ValueError('placement capacity exceeded')
    if retail_order or keep_order:return result,unsupported
    return [e for e in result if e[2] in LEGACY]+[e for e in result if e[2] in V7 and not(e[2]==25 and e[3]<8)]+[e for e in result if e[2] in {42,44}]+[e for e in result if e[2]==18]+[e for e in result if e[2]==33]+[e for e in result if e[2]==19]+[e for e in result if e[2]==54]+[e for e in result if e[2] in (22,23)]+[e for e in result if e[2]==25 and e[3]<8]+[e for e in result if e[2]==32]+[e for e in result if e[2]==7]+[e for e in result if e[2]==49]+[e for e in result if e[2]==9]+[e for e in result if e[2] in (13,53)]+[e for e in result if e[2]==15]+[e for e in result if e[2]==52]+[e for e in result if e[2] in (50,51)]+[e for e in result if e[2] in (36,46)]+[e for e in result if e[2]==47]+[e for e in result if e[2]==41]+[e for e in result if e[2]==40]+[e for e in result if e[2] in (21,66)]+[e for e in result if e[2]==20]+[e for e in result if e[2] in extra],unsupported

def tunnel_paths():
    import re
    source=(DATA/'Palmtree Panic/Objects/Tunnel Path/Main.asm').read_text()
    paths=[]
    for index in range(3):
        block=source.split(f'ObjTunnelPath_Path{index}:',1)[1]
        if index<2:block=block.split(f'ObjTunnelPath_Path{index+1}:',1)[0]
        words=[]
        for line in block.splitlines():
            match=re.match(r'\s*dc\.w\s+([^;]+)',line)
            if match:words.extend(int(v.strip().replace('$','0x'),0) for v in match[1].split(','))
        count=words.pop(0)
        if count!=len(words)*2 or count%4 or count>255:raise ValueError('invalid tunnel path length')
        paths.append(list(zip(words[::2],words[1::2])))
    return paths

def draw(mapping,tiles,colors,width=64,y_shift=0,height=64,*,first_piece_front=True):
    output=bytearray(width*height*2)
    # DrawSprite emits mapping pieces in link order: the first opaque piece
    # wins on Mega CD. Reverse painter order when flattening those pieces.
    # All callers use the source order; False exists only for legacy audits.
    pieces=range(mapping[0]-1,-1,-1) if first_piece_front else range(mapping[0])
    for i in pieces:
        y,size,high,low,x=mapping[1+i*5:6+i*5]
        x=x if x<128 else x-256;y=y if y<128 else y-256
        w=((size>>2)&3)+1;h=(size&3)+1;word=high*256+low
        for py in range(h*8):
            for px in range(w*8):
                sx=w*8-1-px if word&2048 else px;sy=h*8-1-py if word&4096 else py
                tile=(word&2047)+(sx//8)*h+sy//8
                offset=tile*32+(sy%8)*4+(sx%8)//2
                if offset>=len(tiles):raise ValueError('object mapping exceeds art')
                value=tiles[offset];c=(value>>4) if sx%2==0 else value&15
                dx,dy=width//2+x+px,32+y+py+y_shift
                if c and 0<=dx<width and 0<=dy<height:output[(dy*width+dx)*2:(dy*width+dx)*2+2]=colors[c*2:c*2+2]
    return output

def pack_texture(data):
    """Big-endian words: high-bit count is literal, plain count repeats a word."""
    values=[v for v, in struct.iter_unpack('>H',data)];out=bytearray();i=0
    while i<len(values):
        run=1
        while i+run<len(values) and values[i+run]==values[i] and run<32767:run+=1
        if run>=2:
            out.extend(struct.pack('>HH',run,values[i]));i+=run
        else:
            start=i;i+=1
            while i<len(values) and i-start<32767:
                if i+1<len(values) and values[i]==values[i+1]:break
                i+=1
            out.extend(struct.pack('>H',0x8000|i-start));out.extend(struct.pack('>'+str(i-start)+'H',*values[start:i]))
    return out

def collapse_tables(era):
    """Resolve the source size-table pointers and bounded breakup byte arrays."""
    import re
    text=(DATA/f'Palmtree Panic/Objects/Collapsing Platform/Data ({era}).asm').read_text()
    families=[]
    for family in [1,2]:
        body=text.split(f'ObjCollapsePlatform_Sizes{family}:',1)[1].split('MapSpr_',1)[0]
        pointers=re.findall(r'dc\.w\s+(\w+)-ObjCollapsePlatform_Sizes',body)
        tables=[]
        for label in pointers:
            block=re.split(r'\n\w+:',body.split(label+':',1)[1],maxsplit=1)[0]
            data=[]
            for line in block.splitlines():
                m=re.search(r'dc\.b\s+(.+)',line.split(';')[0])
                if m:data.extend(int(v.strip().replace('$','0x'),0)&255 for v in m[1].split(','))
            cols,rows=data[:2];rows=rows if rows<128 else rows-256
            count=(cols+1)*(rows+1) if family==1 else cols+1
            assert 0<count<=20 and len(data)>=count+2
            tables.append((cols,rows,[v if v<128 else v-256 for v in data[2:2+count]]))
        families.append(tables)
    return families

def main():
    from projector_reference import animations,explosions
    scripts=animations();events=explosions()
    (OUT/'projector.inc').write_text('/* Pinned PPZ projector/animal animation and explosion bytes. */\nstatic const uint8_t projector_animations[5][58]={'+','.join('{'+','.join(map(str,a))+'}' for a in scripts)+'};\nstatic const int16_t projector_explosions[12][3]={'+','.join('{'+','.join(map(str,a))+'}' for a in events)+'};\n')
    from amy_reference import animations as amy_animations
    amy_scripts=[sum(([frame,timer] for frame,timer in a),[])+[255,0] for a in amy_animations()]
    amy_colors=struct.unpack('>16H',palette((DATA/'Palmtree Panic/Objects/Amy Rose/Data/Palette.bin').read_bytes()))
    (OUT/'amy.inc').write_text('/* Original Amy animation bytes and stage palette bank 1. */\nstatic const uint8_t amy_animations[6][10]={'+','.join('{'+','.join(map(str,a))+'}' for a in amy_scripts)+'};\nstatic const uint16_t amy_palette[16]={'+','.join(map(str,amy_colors))+'};\n')
    paths=tunnel_paths()
    (OUT/'tunnels.inc').write_text('/* Original PPZ path coordinate words; generated from pinned disassembly. */\nstatic const unsigned char tunnel_lengths[]={'+','.join(str(len(p)) for p in paths)+'};\nstatic const int16_t tunnel_paths[3][34][2]={'+','.join('{'+','.join('{'+str(x)+','+str(y)+'}' for x,y in p)+'}' for p in paths)+'};\n')
    # Palmtree Panic streams through the retail Object Spawner (src/objects.c
    # tt_stream): retail record order and saved-flag bits.
    entries,unsupported=placements((DATA/'Palmtree Panic/Data/Objects (Act 1).bin').read_bytes(),retail_order=True,saved_kind=True)
    (OUT/'objects.inc').write_text('/* Generated Sega CD placements: x,y,type,subtype,flags,era bits,secondary. */\nstatic const scd_placement placements[]={\n'+''.join('    {'+','.join(map(str,e if len(e)==7 else e+(0,)))+'},\n' for e in entries)+'};\n')
    # Act 2 layout from the retail R12A program (tools/extract_mmd.py). Its object
    # index sends ID 0x32 to eda (SHOOT1.C) instead of scenery; native type 57.
    # One ring record lies at Y 3392, below the 1,024-pixel Act 2 layout.
    act2=bytearray();act2_outside=0
    for x,y,kind,sub,eras,secondary in struct.iter_unpack('>HHBBBB',(OUT/'objects12A.bin').read_bytes()):
        if x!=65535 and (y&4095)>=2048:act2_outside+=1;continue
        if x!=65535 and kind&127==50:kind=(kind&128)|57
        act2+=struct.pack('>HHBBBB',x,y,kind,sub,eras,secondary)
    entries2,unsupported2=placements(bytes(act2),retail_order=True,saved_kind=True)
    (OUT/'objects2.inc').write_text('/* Generated retail R12A placements: x,y,type,subtype,flags,era bits,secondary. */\nstatic const scd_placement placements_act2[]={\n'+''.join('    {'+','.join(map(str,e if len(e)==7 else e+(0,)))+'},\n' for e in entries2)+'};\n')
    # Act 3 layout from the retail R13C program (R13D is identical). Its object index
    # sends ID 0x2A to the boss (egg1, BOSS_1.C) instead of the 3D ramp; native type 66.
    act3=bytearray()
    for x,y,kind,sub,eras,secondary in struct.iter_unpack('>HHBBBB',(OUT/'objects13C.bin').read_bytes()):
        if x!=65535 and kind&127==42:kind=(kind&128)|66
        act3+=struct.pack('>HHBBBB',x,y,kind,sub,eras,secondary)
    if (OUT/'objects13C.bin').read_bytes()!=(OUT/'objects13D.bin').read_bytes():raise ValueError('Act 3 futures have different layouts')
    # R13C lists the boss (X 3088) before three monitors at X 3056; native streaming
    # spawns by distance from Sonic, so record order only sets slot order.
    entries3,unsupported3=placements(bytes(act3),ordered=False,retail_order=True,saved_kind=True)
    (OUT/'objects3.inc').write_text('/* Generated retail R13C placements: x,y,type,subtype,flags,era bits,secondary. */\nstatic const scd_placement placements_act3[]={\n'+''.join('    {'+','.join(map(str,e if len(e)==7 else e+(0,)))+'},\n' for e in entries3)+'};\n')
    # Common object palette uses Sonic's line; yellow springs use stage line 1.
    common=palette((DATA/'_Objects/Sonic/Data/Palette.bin').read_bytes())
    yellow=palette((DATA/'Palmtree Panic/Data/Palette (Present).bin').read_bytes()[:32])
    frames=[]
    marker=struct.pack('>16H',*(0x8000+i for i in range(16)))
    spring=DATA/'_Objects/Spring/Data';maps=assembly_frames(spring/'Mappings.asm')
    for colors in [common,marker]:
        for i in range(9):
            art=nemesis((spring/('Art (Diagonal).nem' if i>=6 else 'Art (Normal).nem')).read_bytes())
            frames.append(draw(maps[i],art,colors))
    # Rings are tile $A7AE (Ring/Main.asm:157 and :361; RING.C:228 and :407, one
    # file linked by every round), so they draw on palette line 1, the stage line,
    # not on Sonic's line 0. The ring art uses only entries 6, 12, 13 and 14; every
    # round's level palette holds the white and gold ramp there ($EEE,$0EE,$088,$044)
    # while Sonic's line holds his red shoes. src/main.c draws them as frames 18-21.
    rings=(len(frames),len(frames)+4)
    assert rings[0]==18
    for folder,indices in [('Ring',range(4)),('Spikes',[0]),('Boulder',[0])]:
        path=DATA/f'_Objects/{folder}/Data';maps=assembly_frames(path/'Mappings.asm');art=nemesis((path/'Art.nem').read_bytes())
        frames.extend(draw(maps[i],art,marker if folder=='Ring' else common) for i in indices)
    catalog={}
    for kind,name,files in [(63,'Anton',['Mappings.asm']),(61,'Mosqui',['Mappings (Normal).asm','Mappings (Damaged).asm']),(62,'Pata-Bata',['Mappings (Normal).asm','Mappings (Damaged).asm']),(64,'Taga-Taga',['Mappings.asm']),(34,'Tamabboh',['Mappings.asm','Mappings (Missile).asm'])]:
        path=DATA/f'Palmtree Panic/Objects/{name}/Data';art=nemesis((path/'Art.nem').read_bytes())
        maps=[m for f in files for m in assembly_frames(path/f)]
        catalog[kind]=(len(frames),len(maps))
        for mapping in maps:frames.append(draw(mapping,art,marker))
    path=DATA/'_Objects/Monitor and Time Post/Data'
    catalog[25]=(len(frames),4)
    art=nemesis((path/'Art.nem').read_bytes());maps=assembly_frames(path/'Mappings.asm')
    for i in [10,11,12,13]:frames.append(draw(maps[i],art,common,32,y_shift=8))
    path=DATA/'_Objects/Explosion/Data';catalog[24]=(len(frames),7)
    art=nemesis((path/'Art.nem').read_bytes())
    for mapping in assembly_frames(path/'Mappings.asm'):frames.append(draw(mapping,art,common))
    path=DATA/'_Objects/Robot Generator/Data';catalog[45]=(len(frames),8)
    art=nemesis((path/'Art.nem').read_bytes())
    for mapping in assembly_frames(path/'Mappings.asm'):frames.append(draw(mapping,art,common,80))
    path=DATA/'_Objects/Powerup/Data';catalog[3]=(len(frames),5)
    art=(path/'Art (Time Warp Stars).bin').read_bytes();maps=assembly_frames(path/'Mappings.asm')
    for i in range(8,13):frames.append(draw(maps[i],art,common))
    path=DATA.parent/'Time Warp Cutscene';catalog[200]=(len(frames),5)
    art=nemesis((path/'Data/Art.nem').read_bytes());colors=palette((path/'Data/Palette.bin').read_bytes()[:32])
    import re
    text=(path/'Objects/Sonic/Data/Mappings.asm').read_text()
    for i in range(5):
        body=text.split(f'.Sonic{i}:',1)[1].split('\n.Sonic',1)[0];values=[]
        for raw in body.splitlines():
            m=re.search(r'dc\.b\s+(.+)',raw.split(';')[0])
            if m:values.extend(int(v.strip().replace('$','0x'),0)&255 for v in m[1].split(','))
        values[0]+=1;frames.append(draw(bytes(values),art,colors))
    path=DATA/'Palmtree Panic/Objects/3D Ramp/Data'
    for kind,name,width,colors in [(42,'Booster',96,common),(44,'Plant',64,marker)]:
        maps=assembly_frames(path/f'Mappings ({name}).asm');art=nemesis((path/f'Art ({name}).nem').read_bytes())
        catalog[kind]=(len(frames),len(maps))
        frames.extend(draw(m,art,colors,width) for m in maps)
    path=DATA/'_Objects/Floating Block/Data';maps=assembly_frames(path/'Mappings.asm')
    catalog[18]=(len(frames),len(maps));art=nemesis((path/'Art.nem').read_bytes())
    frames.extend(draw(m,art,marker) for m in maps)
    path=DATA/'Palmtree Panic/Objects/Platform/Data';maps=assembly_frames(path/'Mappings (Platform 1).asm')
    catalog[33]=(len(frames),len(maps));art=nemesis((path/'Art.nem').read_bytes())
    frames.extend(draw(m,art,marker,96) for m in maps)
    path=DATA/'_Objects/Checkpoint/Data';maps=assembly_frames(path/'Mappings.asm')
    catalog[19]=(len(frames),len(maps));art=nemesis((path/'Art.nem').read_bytes())
    frames.extend(draw(m,art,common) for m in maps)
    path=DATA/'Palmtree Panic/Objects/Breakable Wall/Data';maps=assembly_frames(path/'Mappings.asm')
    catalog[54]=(len(frames),len(maps));art=nemesis((DATA/'Palmtree Panic/Objects/Platform/Data/Art.nem').read_bytes())
    frames.extend(draw(m,art,marker) for m in maps)
    shifts=[0]*len(frames)
    shifts[catalog[25][0]:catalog[25][0]+4]=[8]*4
    path=DATA/'_Objects/Level End/Data';maps=assembly_frames(path/'Mappings (Post).asm')
    catalog[22]=(len(frames),1)
    frames.append(draw(maps[5],nemesis((path/'Art (Goal Post).nem').read_bytes()),common));shifts.append(0)
    catalog[23]=(len(frames),5);art=nemesis((path/'Art (Signpost).nem').read_bytes())
    frames.extend(draw(m,art,common,y_shift=16) for m in maps[:5]);shifts.extend([16]*5)
    path=DATA/'_Objects/Results/Data';maps=assembly_frames(path/'Mappings.asm');art=nemesis((path/'Art.nem').read_bytes())
    catalog[201]=(len(frames),5)
    for index,width in [(0,144),(2,208),(1,256),(10,256),(12,224)]:
        mapping=maps[index]
        if index==1:
            # Numeric tiles are filled dynamically by the source HUD code.
            mapping=bytes([8])+mapping[1:41]
        frames.append(draw(mapping,art,common,width));shifts.append(0)
    catalog[202]=(len(frames),10)
    art=(DATA/'_Objects/HUD and Points/Data/Art (Numbers).bin').read_bytes()
    for n in range(10):
        mapping=bytes([1,0,1,0,n*2,252])
        frames.append(draw(mapping,art,common,8));shifts.append(0)
    path=DATA/'_Objects/Monitor and Time Post/Data';maps=assembly_frames(path/'Mappings.asm');art=nemesis((path/'Art.nem').read_bytes())
    catalog[203]=(len(frames),2)
    for n in [14,15]:frames.append(draw(maps[n],art,common,32,y_shift=8));shifts.append(8)
    catalog[204]=(len(frames),12)
    for n in list(range(10))+[16,17]:frames.append(draw(maps[n],art,common,32,first_piece_front=True));shifts.append(0)
    catalog[26]=(len(frames),5)
    for n in range(5):frames.append(draw(bytes([1])+maps[n][1:6],art,common,32));shifts.append(0)
    path=DATA/'_Objects/Powerup/Data';maps=assembly_frames(path/'Mappings.asm',contiguous=True)
    catalog[205]=(len(frames),7)
    for n in range(1,8):
        art=(path/('Art (Shield).bin' if n<4 else 'Art (Invincibility Stars).bin')).read_bytes()
        frames.append(draw(maps[n],art,common,48));shifts.append(0)
    widths=[len(f)//128 for f in frames];canvases=[64]*len(frames)
    collapse_bases=[];collapse_shapes=[]
    path=DATA/'Palmtree Panic/Objects/Collapsing Platform/Data'
    art=nemesis((DATA/'Palmtree Panic/Objects/Platform/Data/Art.nem').read_bytes())
    catalog[32]=(len(frames),0)
    for era in ['Present','Past','Future']:
        bases=[];collapse_shapes.append(collapse_tables(era))
        for family in ['Ledge, ','','Pieces 1, ','Pieces 2, ']:
            bases.append(len(frames))
            for m in assembly_frames(path/f'Mappings ({family}{era}).asm'):
                xs=[]
                for j in range(m[0]):
                    y,size,hi,lo,x=m[1+j*5:6+j*5];x=x if x<128 else x-256
                    xs.extend([abs(x),abs(x+(((size>>2)&3)+1)*8)])
                width=((max(xs)*2+7)//8)*8
                frames.append(draw(m,art,marker,width,16,96));widths.append(width);shifts.append(16);canvases.append(96)
        collapse_bases.append(bases)
    catalog[32]=(catalog[32][0],len(frames)-catalog[32][0])
    shape_text='/* Generated original collapsing platform geometry and global frames. */\n'
    shape_text+='typedef struct {unsigned char columns; signed char rows,pieces[20];} scd_collapse_shape;\n'
    shape_text+='static const unsigned char collapse_bases[3][4]={'+','.join('{'+','.join(map(str,a))+'}' for a in collapse_bases)+'};\n'
    shape_text+='static const unsigned char collapse_counts[3][2]={'+','.join('{'+','.join(str(len(a)) for a in e)+'}' for e in collapse_shapes)+'};\n'
    shape_text+='static const scd_collapse_shape collapse_shapes[3][2][6]={'+','.join('{'+','.join('{'+','.join('{'+str(c)+','+str(r)+',{'+','.join(map(str,v))+'}}' for c,r,v in a)+'}' for a in e)+'}' for e in collapse_shapes)+'};\n'
    path=DATA/'Palmtree Panic/Objects/Tunnel Path/Data'
    catalog[49]=(len(frames),1)
    frames.append(draw(assembly_frames(path/'Mappings (Hole).asm')[0],nemesis((path/'Art (Hole).nem').read_bytes()),common,32))
    widths.append(32);shifts.append(0);canvases.append(64)
    path=DATA/'Palmtree Panic/Objects/Spinning Disc/Data'
    catalog[9]=(len(frames),3)
    for m in assembly_frames(path/'Mappings.asm'):
        frames.append(draw(m,nemesis((path/'Art.nem').read_bytes()),common,32))
        widths.append(32);shifts.append(0);canvases.append(64)
    from convert_assets import sonic_frame
    catalog[206]=(len(frames),6)
    for pose in [0x1a,0x1b,0x1c,0x1f,0x1d,0x1e]:
        frames.append(sonic_frame(pose));widths.append(64);shifts.append(0);canvases.append(64)
    door_art=nemesis((DATA/'Palmtree Panic/Objects/Tunnel Door/Data/Art.nem').read_bytes())
    for kind,path,canvas,shift in [(13,DATA/'_Objects/Spin Tunnel/Data/Mappings (Door).asm',96,16),(53,DATA/'Palmtree Panic/Objects/Tunnel Door/Data/Mappings.asm',64,0)]:
        maps=assembly_frames(path);catalog[kind]=(len(frames),len(maps))
        for m in maps:
            bounds=[]
            for i in range(m[0]):
                y,size,hi,lo,x=m[1+i*5:6+i*5];x=x if x<128 else x-256
                bounds.extend([abs(x),abs(x+(((size>>2)&3)+1)*8)])
            width=((max(bounds)*2+7)//8)*8
            frames.append(draw(m,door_art,common,width,shift,canvas));widths.append(width);shifts.append(shift);canvases.append(canvas)
    path=DATA/'_Objects/Spring/Data';catalog[15]=(len(frames),2)
    for m in assembly_frames(path/'Mappings (Wheel).asm'):
        frames.append(draw(m,nemesis((path/'Art (Wheel).nem').read_bytes()),common,16));widths.append(16);shifts.append(0);canvases.append(64)
    # Only source-valid era/subtype pairs: Past scenery 0/1, future 2;
    # Present/Past full shadow 0 and future withered shadow 1.
    for kind,folder,variants in [(50,'Scenery',[('Art (Past).nem',[0,1]),('Art (Future).nem',[2])]),(51,'Log Shadow',[('Art.nem',[0]),('Art (Withered).nem',[1])])]:
        path=DATA/f'Palmtree Panic/Objects/{folder}/Data';maps=assembly_frames(path/'Mappings.asm');catalog[kind]=(len(frames),sum(len(v[1]) for v in variants))
        for filename,indices in variants:
            art=nemesis((path/filename).read_bytes())
            for index in indices:
                frames.append(draw(maps[index],art,marker,32));widths.append(32);shifts.append(0);canvases.append(64)
    # Projector uses a temporary animal PLC at the same source tile base.
    # Keep both variants resident; normal flying animals alone have high tiles.
    path=DATA/'Palmtree Panic/Objects/Projector/Data'
    maps=assembly_frames(path/'Mappings.asm');catalog[46]=(len(frames),len(maps))
    art=nemesis((path/'Art.nem').read_bytes())
    for m in maps:
        frames.append(draw(m,art,common,48));widths.append(48);shifts.append(0);canvases.append(64)
    path=DATA/'Palmtree Panic/Objects/Animal/Data'
    maps=assembly_frames(path/'Mappings (Flying).asm')+assembly_frames(path/'Mappings (Ground).asm')
    for kind,artpath in [(36,path/'Art.nem'),(208,DATA/'Palmtree Panic/Objects/Projector/Data/Art (Animals).nem')]:
        art=nemesis(artpath.read_bytes());catalog[kind]=(len(frames),len(maps))
        for m in maps:
            frames.append(draw(m,art,common,32));widths.append(32);shifts.append(0);canvases.append(64)
    # Source projector explosions suppress points/flowers, use the default
    # animation and high tile priority. Earlier native explosion art is stable.
    path=DATA/'_Objects/Explosion/Data';maps=assembly_frames(path/'Mappings.asm')
    catalog[207]=(len(frames),len(maps));art=nemesis((path/'Art.nem').read_bytes())
    for m in maps:
        frames.append(draw(m,art,common));widths.append(64);shifts.append(0);canvases.append(64)
    path=DATA/'Palmtree Panic/Objects/Amy Rose/Data';maps=assembly_frames(path/'Mappings.asm');art=nemesis((path/'Art.nem').read_bytes())
    for kind,indices,colors in [(47,range(17),marker),(48,range(8,11),common)]:
        catalog[kind]=(len(frames),len(indices))
        for index in indices:
            frames.append(draw(maps[index],art,colors,64));widths.append(64);shifts.append(0);canvases.append(64)
    catalog[209]=(len(frames),4)
    for pose in [1,2,3,4]:
        frames.append(sonic_frame(pose));widths.append(64);shifts.append(0);canvases.append(64)
    # Act 2 swing: pivot, platform and chain link from the retail R12A mappings
    # (tools/extract_mmd.py) on the platform art sheet, stage palette line 2.
    swing=(OUT/'swing12A.map').read_bytes();catalog[41]=(len(frames),3)
    art=nemesis((DATA/'Palmtree Panic/Objects/Platform/Data/Art.nem').read_bytes());at=0
    for _ in range(3):
        mapping=swing[at:at+1+5*swing[at]];at+=len(mapping)
        frames.append(draw(mapping,art,marker,48));widths.append(48);shifts.append(0);canvases.append(64)
    # Results/Main.asm adds the act number to line 2's frame: Act 2 uses
    # "THROUGH Zone 2" (mapping 3) and "FUTURE IN Zone 2" (mapping 13).
    path=DATA/'_Objects/Results/Data';maps=assembly_frames(path/'Mappings.asm');art=nemesis((path/'Art.nem').read_bytes())
    catalog[210]=(len(frames),2)
    for index,width in [(3,208),(13,224)]:
        frames.append(draw(maps[index],art,common,width));widths.append(width);shifts.append(0);canvases.append(64)
    # Appended after every Act 1 frame so earlier frame indices stay fixed.
    # Act 2 (all eras): ledge, single-row platform, pieces 1 and pieces 2 frames from
    # the retail R12A program on the same platform art; single-row sizes from
    # KUZUR12A-D.C (checked on the disc by tools/extract_mmd.py).
    act2=(OUT/'collapse12.map').read_bytes();at=0;act2_bases=[]
    art=nemesis((DATA/'Palmtree Panic/Objects/Platform/Data/Art.nem').read_bytes())
    catalog[211]=(len(frames),0)
    for family in range(4):
        # Relative to OBJECT_BASE_211: global frame numbers above 255 do not fit the byte tables.
        count=act2[at];at+=1;act2_bases.append(len(frames)-catalog[211][0])
        for _ in range(count):
            m=act2[at:at+1+5*act2[at]];at+=len(m)
            xs=[]
            for j in range(m[0]):
                y,size,hi,lo,x=m[1+j*5:6+j*5];x=x if x<128 else x-256
                xs.extend([abs(x),abs(x+(((size>>2)&3)+1)*8)])
            width=((max(xs)*2+7)//8)*8
            frames.append(draw(m,art,marker,width,16,96));widths.append(width);shifts.append(16);canvases.append(96)
    catalog[211]=(catalog[211][0],len(frames)-catalog[211][0])
    act2_shapes=[collapse_shapes[0][0],[(7,2,[0]*8),(7,1,[1]*8)]]
    shape_text+='static const unsigned char collapse_bases_act2[4]={'+','.join(map(str,act2_bases))+'};\n'
    shape_text+='static const unsigned char collapse_counts_act2[2]={'+','.join(str(len(a)) for a in act2_shapes)+'};\n'
    shape_text+='static const scd_collapse_shape collapse_shapes_act2[2][6]={'+','.join('{'+','.join('{'+str(c)+','+str(r)+',{'+','.join(map(str,v))+'}}' for c,r,v in a)+'}' for a in act2_shapes)+'};\n'
    (OUT/'collapse.inc').write_text(shape_text)
    # Act 2 past/future springboard (Palmtree Panic/Objects/Springboard); ObjectTileIDs
    # entry 7 in R12B-D is $41E/$3DC/$3EC, all on Sonic's palette line.
    path=DATA/'Palmtree Panic/Objects/Springboard/Data';maps=assembly_frames(path/'Mappings.asm');art=nemesis((path/'Art.nem').read_bytes())
    catalog[40]=(len(frames),len(maps))
    for m in maps:frames.append(draw(m,art,common,64));widths.append(64);shifts.append(0);canvases.append(64)
    def centered(m,colors,art,shift=0,canvas=64):
        xs=[]
        for j in range(m[0]):
            y,size,hi,lo,x=m[1+j*5:6+j*5];x=x if x<128 else x-256
            xs.extend([abs(x),abs(x+(((size>>2)&3)+1)*8)])
        width=((max(xs)*2+7)//8)*8
        frames.append(draw(m,art,colors,width,shift,canvas));widths.append(width);shifts.append(shift);canvases.append(canvas)
    # Act 3 boss (tools/extract_mmd.py, retail R13C). Robotnik (tile $3FD) is on
    # Sonic's line. The parts (tile $2359) are on line 1, where the boss palette is
    # loaded (colorset2(5)); the body (tile $359) has one line-1 piece in front of its
    # line-0 pieces, so it is split into a line-0 frame and a line-1 frame.
    boss=(OUT/'boss13.map').read_bytes();at=0;boss_tables=[]
    while at<len(boss):
        count=boss[at];at+=1;table=[]
        for _ in range(count):table.append(boss[at:at+1+5*boss[at]]);at+=len(table[-1])
        boss_tables.append(table)
    robotnik=(OUT/'boss-robotnik.tiles').read_bytes();parts=(OUT/'boss-parts.tiles').read_bytes()
    catalog[66]=(len(frames),25)
    for m in boss_tables[0]:centered(m,common,robotnik,8,96)
    body=boss_tables[1][0];pieces=[body[1+j*5:6+j*5] for j in range(body[0])]
    front=[q for q in pieces if q[2]&0x20];back=[q for q in pieces if not q[2]&0x20]
    if len(front)!=1:raise ValueError('boss body palette pieces changed')
    centered(bytes([len(back)])+b''.join(back),common,parts);centered(bytes([1])+front[0],marker,parts)
    for table in boss_tables[2:]:
        for m in table:centered(m,marker,parts)
    # Flower capsule and its seeds (Level End): line 1 holds the capsule palette while
    # the capsule stands and the level palette once the seeds spawn.
    path=DATA/'_Objects/Level End/Data';art=nemesis((path/'Art (Flower Capsule).nem').read_bytes())
    maps=assembly_frames(path/'Mappings (Flower Capsule).asm');catalog[21]=(len(frames),len(maps))
    for m in maps:centered(m,marker,art,0,96)
    # Flowers (Palmtree Panic/Objects/Flower): seed frames 0-3 on line 0 ($6D7),
    # growing and grown frames 4-7 on line 1 ($26D7). The grown poses 6-7 reach
    # Y -48 (three pieces from $D0): a 96-row canvas, origin row 48 (shift 16).
    path=DATA/'Palmtree Panic/Objects/Flower/Data';art=nemesis((path/'Art.nem').read_bytes())
    maps=assembly_frames(path/'Mappings.asm');catalog[31]=(len(frames),len(maps))
    for n,m in enumerate(maps):centered(m,common if n<4 else marker,art,16,96)
    # Results line 2 for Act 3: "THROUGH Zone 3" (mapping 4) and "FUTURE IN Zone 3" (14).
    path=DATA/'_Objects/Results/Data';maps=assembly_frames(path/'Mappings.asm');art=nemesis((path/'Art.nem').read_bytes())
    catalog[212]=(len(frames),2)
    for index,width in [(4,208),(14,224)]:
        frames.append(draw(maps[index],art,common,width));widths.append(width);shifts.append(0);canvases.append(64)
    # Line 1 overrides during the Act 3 boss (PaletteTable entry 5 of R13C/R13D) and the
    # flower capsule (Palette (Flower Capsule).bin, GOAL.C genecolor), as RGB555.
    rgb=lambda data:','.join(map(str,struct.unpack('>16H',palette(data))))
    (OUT/'act3-palettes.inc').write_text('/* Generated Act 3 palette line 1 overrides: boss (good, bad future), capsule. */\nstatic const uint16_t boss_palettes[2][16]={{'+rgb((OUT/'boss13C.pal').read_bytes())+'},{'+rgb((OUT/'boss13D.pal').read_bytes())+'}};\nstatic const uint16_t capsule_palette[16]={'+rgb((DATA/'_Objects/Level End/Data/Palette (Flower Capsule).bin').read_bytes())+'};\n'
        # Collision Chaos (tools/extract_mmd.py, COL3C/COL3D.C): [future][colorset2 6 boss, 5 flash].
        +'static const uint16_t boss3_palettes[2][2][16]={'+','.join('{{'+rgb(data[:32])+'},{'+rgb(data[32:])+'}}' for data in ((OUT/f'boss3{e}.pal').read_bytes() for e in 'CD'))+'};\n'
        # Tidal Tempest (tools/extract_mmd.py, COL4C/COL4D.C boss4color): [future].
        +'static const uint16_t boss4_palettes[2][16]={'+','.join('{'+rgb((OUT/f'boss4{e}.pal').read_bytes())+'}' for e in 'CD')+'};\n'
        # Quartz Quadrant (tools/extract_mmd.py, COL5C/COL5D.C zone5colboss0, colorset2 6): [future].
        +'static const uint16_t boss5_palettes[2][16]={'+','.join('{'+rgb((OUT/f'boss5{e}.pal').read_bytes())+'}' for e in 'CD')+'};\n'
        +'static const uint16_t boss6_palettes[2][16]={'+','.join('{'+rgb((OUT/f'boss6{e}.pal').read_bytes())+'}' for e in 'CD')+'};\n')
    # Monitor item icons 5-7 (time stop, combine ring, S) rise from Act 3 monitors.
    path=DATA/'_Objects/Monitor and Time Post/Data';maps=assembly_frames(path/'Mappings.asm');art=nemesis((path/'Art.nem').read_bytes())
    catalog[213]=(len(frames),3)
    for n in range(5,8):frames.append(draw(bytes([1])+maps[n][1:6],art,common,32));widths.append(32);shifts.append(0);canvases.append(64)
    # Big ring (tile $2488, stage line 1) and its flash (tile $3EF, Sonic's line), Level End/Main.asm.
    path=DATA/'_Objects/Level End/Data'
    maps=assembly_frames(path/'Mappings (Big Ring).asm');art=nemesis((path/'Art (Big Ring).nem').read_bytes());catalog[20]=(len(frames),len(maps))
    for m in maps:centered(m,marker,art,0,96)
    maps=assembly_frames(path/'Mappings (Big Ring Flash).asm');art=nemesis((path/'Art (Big Ring Flash).nem').read_bytes());catalog[214]=(len(frames),len(maps))
    for m in maps:centered(m,common,art,0,96)
    # CC's Present generator uses the original withered bank; its Past uses
    # the normal generator frames already in catalog 45. Keep the two actual
    # Present poses separate rather than displaying the normal-bank flowers.
    path=DATA/'_Objects/Robot Generator/Data'
    maps=assembly_frames(path/'Mappings.asm');art=nemesis((path/'Art (Withered).nem').read_bytes())
    catalog[86]=(len(frames),2)
    for index in (0,2):
        frames.append(draw(maps[index],art,common,80));widths.append(80);shifts.append(0);canvases.append(64)
    # Collected placed/lost rings use mapping poses 4-7 (Ani_Ring). Append
    # them so the established indices of every other object remain stable.
    path=DATA/'_Objects/Ring/Data';maps=assembly_frames(path/'Mappings.asm');art=nemesis((path/'Art.nem').read_bytes())
    ring_sparkle_base=len(frames)
    for index in range(4,8):
        frames.append(draw(maps[index],art,marker,16));widths.append(16);shifts.append(0);canvases.append(64)
    # HUD and Points/Main.asm ObjPoints: tile $6C6 (Sonic's line), MapSpr_Points
    # frame = subtype & $7F (100, 200, 500, 1000, 10000 ...). Appended so every
    # other object keeps its index.
    path=DATA/'_Objects/HUD and Points/Data'
    maps=assembly_frames(path/'Mappings (Points).asm');art=nemesis((path/'Art (Points).nem').read_bytes());catalog[28]=(len(frames),len(maps))
    # Canvas just wide enough for each frame (8 px glyphs at -12..+12): OBJART.BIN is full.
    for m in maps:
        w=24 if m[0]==3 else 8 if m[0]==1 else 16
        frames.append(draw(m,art,common,w));widths.append(w);shifts.append(0);canvases.append(64)
    packed=[];clut_indices=[];stage_palettes=[];heights=[];tops=[]
    for number,frame in enumerate(frames):
        colors=[0];indices=[]
        for value, in struct.iter_unpack('>H',frame):
            if value not in colors:colors.append(value)
            indices.append(colors.index(value))
        if len(colors)>16:raise ValueError('object exceeds 16-color CLUT')
        wall=catalog[54][0]<=number<catalog[22][0]
        scenery=catalog[50][0]<=number<catalog[46][0]
        swing=catalog[211][0]<=number<catalog[211][0]+catalog[211][1] or catalog[41][0]<=number<catalog[41][0]+catalog[41][1]
        act3_line1=catalog[66][0]+12<=number<catalog[66][0]+25 or catalog[21][0]<=number<catalog[21][0]+9 or catalog[31][0]+4<=number<catalog[31][0]+8 or catalog[20][0]<=number<catalog[20][0]+catalog[20][1]
        use_stage=act3_line1 or catalog[47][0]<=number<catalog[48][0] or scenery or catalog[32][0]<=number<catalog[49][0] or wall or 9<=number<18 or rings[0]<=number<rings[1] or ring_sparkle_base<=number<ring_sparkle_base+4 or 24<=number<68 or catalog[44][0]<=number<catalog[19][0]
        stage_palettes.append(2 if swing or scenery or catalog[32][0]<=number<catalog[49][0] or wall or catalog[44][0]<=number<catalog[19][0] else int(use_stage))
        clut_indices.append([c&15 for c in colors]+[0]*(16-len(colors)))
        width=widths[number]
        occupied=[y for y in range(canvases[number]) if any(indices[y*width:(y+1)*width])]
        # VDP1 heights are in rows, but CLUT addresses ignore their low two
        # address units: the palette MUST be 32-byte aligned, not merely 8.
        # Choose the smallest row quantum whose 4bpp byte count is /32.
        import math
        rows=32//math.gcd(32,width//2)
        top=(min(occupied)//rows)*rows if occupied else 0
        bottom=((max(occupied)+rows)//rows)*rows if occupied else rows
        tops.append(top);heights.append(bottom-top)
        cropped=indices[top*width:bottom*width]
        packed.append(bytes((cropped[i]<<4)|cropped[i+1] for i in range(0,len(cropped),2))+struct.pack('>16H',*(colors+[0]*(16-len(colors)))))
    # Share byte-identical textures only when palette update semantics also match.
    unique=[];seen={};raw_offsets=[];priorities=[];total=0
    for n,data in enumerate(packed):
        # Results/Main.asm tiles $83C4/$82F2 carry the priority bit, including the
        # act 2/3 "Zone N" lines (210, 212) drawn over PPZ Past's high plants.
        priority=catalog[201][0]<=n<catalog[203][0] or catalog[26][0]<=n<catalog[205][0] or catalog[13][0]<=n<catalog[15][0] or catalog[36][0]<=n<catalog[36][0]+3 or catalog[207][0]<=n<catalog[207][0]+catalog[207][1] or any(catalog[k][0]<=n<catalog[k][0]+catalog[k][1] for k in (210,212))
        priorities.append(int(priority))
        key=(data,stage_palettes[n],tuple(clut_indices[n]),priority)
        if key not in seen:
            assert total%32==0 and len(data)%32==0
            seen[key]=total;unique.append(data);total+=len(data)
        raw_offsets.append(seen[key])
    encoded=b''.join(pack_texture(frame) for frame in unique)
    if 0x1AAC0+total>0x76800:raise ValueError('object textures overlap special-stage UFO VRAM')
    (OUT/'object-art.bin').write_bytes(encoded)
    (OUT/'object-frames.inc').write_text('/* Generated CLUT texture layout. */\n#define OBJECT_FRAME_COUNT '+str(len(frames))+'\n#define OBJECT_ART_BYTES '+str(total)+'\n#define OBJECT_RING_SPARKLE_BASE '+str(ring_sparkle_base)+'\nstatic const unsigned object_raw_offsets[]={'+','.join(map(str,raw_offsets))+'};\nstatic const unsigned object_widths[]={'+','.join(map(str,widths))+'};\nstatic const unsigned char object_high_priority[]={'+','.join(map(str,priorities))+'};\nstatic const unsigned char object_y_shifts[]={'+','.join(map(str,shifts))+'};\n'+'static const unsigned char object_canvases[]={'+','.join(map(str,canvases))+'};\nstatic const unsigned char object_heights[]={'+','.join(map(str,heights))+'};\nstatic const unsigned char object_tops[]={'+','.join(map(str,tops))+'};\nstatic const unsigned char object_stage_palette[]={'+','.join(map(str,stage_palettes))+'};\nstatic const unsigned char object_clut_indices[][16]={'+','.join('{'+','.join(map(str,c))+'}' for c in clut_indices)+'};\n'+''.join(f'#define OBJECT_BASE_{k} {base}\n' for k,(base,count) in catalog.items()))
    report={'placements':len(entries),'placements_act3':len(entries3),'unsupported_act3':dict(sorted(unsupported3.items())),'supported_ids':sorted(SUPPORTED),'unsupported_source_records':dict(sorted(unsupported.items())),
            'era_counts':{era:sum(bool(e[5]&(1<<bit)) for e in entries) for era,bit in [('present',1),('past',0),('good_future',2),('bad_future',2)]},
            'art_frames':len(frames),'art_uncropped_bytes':sum(w*h//2+32 for w,h in zip(widths,canvases)),'art_saved_bytes':sum(w*h//2+32 for w,h in zip(widths,canvases))-sum(map(len,packed)),'art_raw_bytes':total,'art_deduplicated_bytes':sum(map(len,packed))-total,'unique_textures':len(unique),'art_rle_bytes':len(encoded),'texture_encoding':'word RLE with high-bit literal counts','frame_catalog':catalog,'limitations':['unsupported objects omitted','native enemy behavior translated from Sega CD source; original-console parity pending']}
    # PPZ title card (_Objects/Title Card, Title Card Data.asm): Art_TitleCard at
    # tile $360 and Art_TitleCardText at $3D0 share one tile space from $360;
    # tile $8360 uses Sonic's palette line. Nine frames, drawn at VDP1 0x4600.
    sheet=nemesis((DATA/'_Objects/Title Card/Data/Art.nem').read_bytes())
    sheet=sheet.ljust(0x70*32,b'\0')+nemesis((DATA/'Palmtree Panic/Objects/Title Card/Art.nem').read_bytes())
    card=[];card_bytes=0;card_data=bytearray()
    for mapping in assembly_frames(DATA/'Palmtree Panic/Objects/Title Card/Mappings.asm'):
        xs=[];ys=[]
        for j in range(mapping[0]):
            y,size,hi,lo,x=mapping[1+j*5:6+j*5];x=x-256 if x>127 else x;y=y-256 if y>127 else y
            xs+=[x,x+(((size>>2)&3)+1)*8];ys+=[y,y+((size&3)+1)*8]
        left,top=min(xs),min(ys);width,height=max(xs)-left,max(ys)-top
        shifted=bytearray(mapping[:1+5*mapping[0]])
        for j in range(mapping[0]):
            shifted[5+j*5]=(shifted[5+j*5]-left-width//2)&255
        pixels=draw(bytes(shifted),sheet,common,width,-top-32,height)
        colors=[0];indices=[]
        for value, in struct.iter_unpack('>H',pixels):
            if value not in colors:colors.append(value)
            indices.append(colors.index(value))
        if len(colors)>16:raise ValueError('title card frame exceeds 16-color CLUT')
        data=bytes((indices[i]<<4)|indices[i+1] for i in range(0,len(indices),2))+struct.pack('>16H',*(colors+[0]*(16-len(colors))))
        # Frames 7 and 8 (the zone name) get fixed slots sized for the widest round (R1 104x56,
        # R5/R6 112x56): src/main.c title_card_name_load() replaces them (tools/title_card_names.py).
        if len(card)>=7:slot=(2944,3168)[len(card)-7];assert len(data)<=slot;data=data.ljust(slot,b'\0')
        card.append((card_bytes,width,height,left,top));card_bytes+=len(data);card_data.extend(data)
    if card_bytes>0x8000-0x4600:raise ValueError('title card textures exceed VDP1 0x4600-0x7FFF')
    (OUT/'title-card-art.bin').write_bytes(pack_texture(bytes(card_data)))
    (OUT/'title-card.inc').write_text('/* Generated PPZ title card textures: offset, width, height, left, top. */\n#define TITLE_CARD_BYTES '+str(card_bytes)+'\nstatic struct {uint16_t offset,width,height;int16_t left,top;} title_card_frames['+str(len(card))+']={'+','.join('{%d,%d,%d,%d,%d}'%f for f in card)+'};\n')
    report['title_card']={'frames':len(card),'raw_bytes':card_bytes}
    (ROOT/'build/object-source.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
if __name__=='__main__':main()
