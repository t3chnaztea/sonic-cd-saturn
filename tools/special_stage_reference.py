"""Original special-stage Sub CPU object update in the offline 68000.

Persistent-RAM oracle: RunObjects, Draw3DObjects, the Sonic, shadow, UFO,
item, lost-ring, explosion, splash, dust and time-stone objects,
UpdateTimer/SpawnTimeUFO and CheckUFOPresence run as source. Changes are
syntax, absolute test addresses, an ObjSonic_LoadArt stub, a DrawObject call
log, and a mapping at address zero that draws nothing when the cleared time
UFO is drawn after CheckWin (the native runtime skips that call).
"""
import re,struct
from special_assets import SOURCE
from special_reference import Reference
from special_player_reference import object_offsets,compile_code
from special_contact_reference import span,PLAYER_LONGS,PLAYER_WORDS,PLAYER_BYTES,SPRITE
from special_effect_reference import FIELDS as EFFECT_FIELDS
from special_sonic_assets import mappings
O=object_offsets()
SONIC,SONIC_SHADOW,P1,P2,P3=0x32000,0x32080,0x32100,0x32800,0x33400
STAMP_TYPES,GFX,SAT,ZBUFFER,LOG,SONIC_MAP=0x34000,0x35000,0x36000,0x37000,0x38000,0x18000
UFO_FIELDS=[('x','oX','I'),('y','oY','I'),('x_velocity','oXVel','I'),('y_velocity','oYVel','I'),('sprite_x','oSprX','I'),('sprite_y','oSprY','I'),('path_offset',None,'H'),('path_time','oVar60','H'),('z','oZ','H'),('id','oID','B'),('flags','oFlags','B'),('player_collision','oVar4F','B'),('item','oVar62','B'),('unknown','oVar63','B'),('timer','oTimer','H'),('routine','oRoutine','B'),('animation','oAnim','B'),('ufo_animation','oVar52','B'),('explode_dir','oVar53','B'),('draw_delay','oVar64','B'),('frame','oAnimFrame','B'),('time','oAnimTime','B'),('time_copy','oAnimTime2','B'),('art','oSpriteFlag','B')]
SHADOW_FIELDS=[('x','oX','I'),('y','oY','I'),('sprite_x','oSprX','I'),('sprite_y','oSprY','I'),('z','oZ','H'),('id','oID','B'),('routine','oRoutine','B'),('flags','oFlags','B'),('animation','oAnim','B'),('shadow_animation','oVar52','B'),('frame','oAnimFrame','B'),('time','oAnimTime','B'),('time_copy','oAnimTime2','B'),('art','oSpriteFlag','B')]
GLOBALS={'ctrlData':0x6000,'playerCtrlData':0x6002,'playerCtrlHold':0x6002,'playerCtrlTap':0x6003,'stageInactive':0x6004,'timeStopped':0x6005,'specStageFlags':0x6006,'ufoCount':0x6007,'specStageRings':0x6008,'jumpTimer':0x600a,'subScrollFlags':0x600c,'subSndQueue1':0x600d,'subSndQueue2':0x600e,'subSndQueue3':0x600f,'timerFrames':0x6010,'timerSpeedUp':0x6011,'stageOver':0x6012,'gotTimeStone':0x6013,'specStageTimer':0x6014,'stampTypes':0x6018,'rngSeed':0x601c,'curSpriteSlot':0x6020,'spriteCount':0x6024,'lostRingXDir':0x6025,'ufoRingBonus':0x6026,'specStageID':0x6028,'D1SAVE':0x602c,'DRAWLOG':0x6030,'DRAWCOUNT':0x6034}
def object_code(address):
    """Native draw object code for an original slot address."""
    if address==SONIC:return 0
    if address==SONIC_SHADOW:return 1
    if P1<=address<P2:index=(address-P1)//128;return {0:2,1:44,2:45}.get(index,index)
    if P2<=address<P3:
        index=(address-P2)//128;return 14+index if index<22 else 36
    index=(address-P3)//128;return 37+index if index<6 else 43
def draw_entry(code,slot):
    """Pack/animation/palette selection for one logged DrawObject call."""
    anim=slot[O['oAnim']];tile=struct.unpack_from('>H',slot,O['oTile'])[0]
    if code==0:kind,base=0,0
    elif code in (44,45):kind,base=2,79-code
    elif code==1 or code>=37:kind,base=2,20
    elif code==2:kind,base=1,0
    elif code<=5:kind,base=2,31
    elif code<=13:kind,base=1,2
    elif code<=21:kind,base=1,3
    elif code<=29:kind,base=2,30
    else:kind,base=2,0 if code==36 or not slot[O['oVar62']] else 10
    x,y=struct.unpack_from('>HH',slot,O['oSprX'])[0],struct.unpack_from('>H',slot,O['oSprY'])[0]
    return [x,y,kind,base+anim,slot[O['oAnimFrame']],(tile>>13)&3,0 if slot[O['oFlags']]&4 else 1,code]
def convert(body,scope='Entry'):
    lines=[];enabled=True
    for raw in body.splitlines():
        line=raw.split(';',1)[0].strip()
        if not line:continue
        if line.startswith('if REGION<>EUROPE'):enabled=True;continue
        if line=='else':enabled=False;continue
        if line=='endif':enabled=True;continue
        if not enabled or re.match(r'\w+\s+EQU\s+',line):continue
        m=re.fullmatch(r'include\s+"([^"]+)"',line)
        if m:
            nested,scope=convert((SOURCE.parent/m[1]).read_text(),scope);lines+=nested;continue
        m=re.fullmatch(r'incbin\s+"([^"]+)"',line)
        if m:lines.append(f'.incbin "{SOURCE.parent/m[1]}"');continue
        if line=='even':lines.append('.balign 2');continue
        m=re.fullmatch(r'rept\s+(.+)',line)
        if m:lines.append('.rept '+m[1]);continue
        if line=='endr':lines.append('.endr');continue
        # GNU m68k treats | as a comment; this is UpdateTimer's 9'59"59 cap.
        line=line.replace('#(9<<16)|(59<<8)|59','#0x93b3b')
        label=re.match(r'([A-Za-z_]\w*):',line)
        if label:scope=label[1]
        line=re.sub(r'(?<![\w])\.(\w+)',lambda m:scope+'__'+m[1],line)
        line=re.sub(r'\$([0-9A-Fa-f]+)',r'0x\1',line)
        line=re.sub(r'%([01]+)',lambda m:str(int(m[1],2)),line)
        for a,b in [('dc.b','.byte'),('dc.w','.word'),('dc.l','.long')]:line=line.replace(a,b)
        lines.append(line)
    return lines,scope
class StageReference:
    def __init__(self,reference=None):
        self.r=reference or Reference();sub=(SOURCE/'Sub.asm').read_text()
        text={name:(SOURCE/f'Objects/{name}/Main.asm').read_text() for name in ['Sonic','UFO','Shadow','Item','Explosion','Splash','Dust','Time Stone','Title Card']}
        body='ObjSonic_Index:'+text['Sonic'].split('ObjSonic_Index:',1)[1].split('ObjSonic_LoadArt:',1)[0]+'\nObjSonic_LoadArt:\n rts\n'
        for name in ['UFO','Shadow','Item','Explosion','Splash','Dust','Time Stone','Title Card']:body+='\n'+text[name]+'\n'
        body+=span(sub,'RunObjects','ObjectIndex').replace('\nDrawObject:','\nDrawObjectOriginal:')
        index={1:'ObjSonic',2:'ObjUFO',3:'ObjTimeUFO',4:'ObjItem',5:'ObjUFOShadow',6:'ObjSonicShadow',7:'ObjDust',8:'ObjSplash',10:'ObjTitleCardText',11:'ObjTitleCardBar',12:'ObjExplosion',13:'ObjLostRing',14:'ObjTimeStone',15:'ObjSparkle1',16:'ObjSparkle2'}
        body+='\nObjectIndex:\n'+''.join('dc.l '+index.get(n,'Unsupported')+'\n' for n in range(1,17))
        for start,end in [('ObjUFO_CheckPlayerCol','ObjSonic_GetStamps'),('ObjSonic_GetStamps','StampTypes_SS1'),('DecUFOCount','GetAngle'),('GetAngle','GetTrajectory'),('GetDistance','Copy128'),('Fill128','WaitGfxOperation'),('PlayFMSound','GenGfxTraceTbl'),('GetGfxSines','RunGfxOperation'),('CheckUFOPresence','IRQ1')]:
            body+='\n'+span(sub,start,end)
        body+='\nGetCosine:'+sub.split('GetCosine:',1)[1].split('\n\tinclude',1)[0]
        for label,path in [('MapSpr_Splash','Splash/Data/Mappings.asm'),('MapSpr_Shadow','Shadow/Data/Mappings.asm'),('MapSpr_UFORings','UFO/Data/Mappings (Rings).asm'),('MapSpr_UFOShoes','UFO/Data/Mappings (Speed Shoes).asm')]:
            body+=f'\n{label}:\n\tinclude\t"Special Stage/Objects/{path}"\n\teven\n'
        # Test instrumentation: log each DrawObject call with its final slot.
        body+='\nDrawObject:\n move.b spriteCount,DRAWCOUNT\n bsr.w DrawObjectOriginal\n movem.l d0/d7/a1/a2,-(sp)\n movea.l DRAWLOG,a2\n move.w a0,(a2)+\n move.b DRAWCOUNT,(a2)+\n move.b spriteCount,(a2)+\n movea.l a0,a1\n moveq #127,d7\nDrawLogCopy:\n move.b (a1)+,(a2)+\n dbf d7,DrawLogCopy\n move.l a2,DRAWLOG\n movem.l (sp)+,d0/d7/a1/a2\n rts\n'
        body+='\nUnsupported:\n rts\nSpawn:\n bsr.w SpawnUFOs\n rts\n'
        body+='\nUpdate:\n move.l D1SAVE,d1\n bsr.w GetGfxSines\n move.b #0,spriteCount\n move.l #subSprites,curSpriteSlot\n bsr.w Init3DSpritePos\n bsr.w RunObjects\n movea.l curSpriteSlot,a0\n move.l #0,(a0)\n move.l d1,D1SAVE\n bsr.w UpdateTimer\n bsr.w CheckUFOPresence\n bne.s UpdateNotOver\n move.b specStageFlags,d0\n andi.b #3,d0\n beq.s UpdateNotOver\n move.b #1,stageOver\nUpdateNotOver:\n rts\n'
        constants=dict(O)|GLOBALS
        for name in text:
            for label,alias in re.findall(r'^(\w+)\s+EQU\s+(oVar\w+)',text[name],re.M):constants[label]=O[alias]
        offset=0
        for line in ('gfxCamX'+sub.split('gfxCamX',1)[1].split('; ---',1)[0]).splitlines():
            m=re.match(r'\s*(?:(\w+)\s+)?rs\.([bwl])\s+(\$[0-9A-Fa-f]+|\d+)',line)
            if m:
                if m[1]:constants[m[1]]=offset
                offset+=int(m[3].replace('$','0x'),0)*{'b':1,'w':2,'l':4}[m[2]]
        self.gfx={k:constants[k] for k in ['gfxCamX','gfxCamY','gfxCamZ','gfxPitch','gfxYaw','gfxFOV','gfxCenter']}
        constants|={'oSize':128,'sonicObject':SONIC,'sonicShadowObj':SONIC_SHADOW,'objPrioLevel1':P1,'OBJ1COUNT':14,'splashObject':P1,'ttlCardBarObj':P1+128,'ttlCardTextObj':P1+256,'timeStoneObject':P1+384,'sparkleObject1':P1+512,'sparkleObject2':P1+640,'dustObjects':P1+768,'DUSTOBJCOUNT':8,
            'objPrioLevel2':P2,'OBJ2COUNT':24,'itemObject':P2,'explosionObjs':P2+8*128,'EXPLODEOBJCNT':8,'ufoObjects':P2+16*128,'UFOOBJCOUNT':6,'timeUFOObject':P2+23*128,'objPrioLevel3':P3,'OBJ3COUNT':8,'timeUFOShadObj':P3+7*128,
            'ZBUFLEVELS':64,'ZBUFSLOTS':8,'zBuffer':ZBUFFER,'subSprites':SAT,'gfxVars':GFX,'SprMap3DSection':0x30000,'MapSpr_Sonic':SONIC_MAP,'WORDRAM2M':0x80000,'STAMPMAP':0x20000}
        for n in range(7):constants[f'ringObject{n+1}']=P2+(n+1)*128
        for n in range(6):constants[f'ufoObject{n+1}']=P2+(16+n)*128;constants[f'ufoShadowObj{n+1}']=P3+n*128
        sound=(SOURCE.parent/'Sound Drivers/FM/_Sound IDs.inc').read_text();value=0x90
        for raw in sound.splitlines():
            line=raw.split(';',1)[0].strip()
            if line.startswith('rsset'):value=int(line.split()[1].replace('$','0x'),0)
            m=re.fullmatch(r'(FM\w+)\s+rs\.([bw])\s+(\d+)',line)
            if m:constants[m[1]]=value;value+=int(m[3])*(1 if m[2]=='b' else 2)
        lines,_=convert(body)
        preamble='.text\n'+''.join(f'.equ {k},{v}\n' for k,v in constants.items())
        self.code={}
        for name,label in [('update','Update'),('spawn','Spawn')]:
            self.code[name]=compile_code('stage-'+name,preamble+'bra.w '+label+'\n'+'\n'.join(lines)+'\n',link_address=0x1000)
            assert 0x1000+len(self.code[name])<=0x6000,('stage oracle code overlaps globals',len(self.code[name]))
        self.constants=constants;self.skipped=0
    def write_actor(self,player,sprite,world):
        """Write Sonic and all world globals/slot markers from native dictionaries."""
        r=self.r;obj=bytearray(r.read(r.prg,SONIC,128))
        for fields,fmt in [(PLAYER_LONGS,'I'),(PLAYER_WORDS,'H'),(PLAYER_BYTES,'B')]:
            for name,label in fields.items():struct.pack_into('>'+fmt,obj,O[label],player[name])
        for name,label in SPRITE.items():obj[O[label]]=sprite[name]
        r.write(r.prg,SONIC,obj)
        g=bytearray(r.read(r.prg,0x6000,64))
        g[4]=world['inactive'];g[5]=world['stopped'];g[6]=(g[6]&~2)|(2 if world['time_attack'] else 0);g[7]=world['ufo_count']
        struct.pack_into('>HH',g,8,world['rings'],player['jump_timer']);g[12]=player['scroll']
        g[16:20]=bytes([world['timer_frames'],world['speedup'],world['stage_over'],world['got_time_stone']])
        struct.pack_into('>I',g,0x14,world['timer']);struct.pack_into('>H',g,0x26,world['ring_bonus'])
        r.write(r.prg,0x6000,g)
    def reset(self,stage,player,sprite,world,parts,start=False):
        r=self.r;g=GLOBALS
        r.write(r.prg,0x32000,bytes(0x1800));r.write(r.prg,ZBUFFER,bytes(1024));r.write(r.prg,SAT,bytes(648));r.write(r.prg,GFX,bytes(256))
        r.write(r.prg,0x6000,bytes(64));r.write(r.prg,STAMP_TYPES,parts[2]);r.write(r.ram,0x20000,parts[1])
        # Address-zero mapping: one frame with a negative piece count.
        r.write(r.prg,0,struct.pack('>I',0x7f00));r.write(r.prg,0x7f00,bytes([1,0])+struct.pack('>I',0x7f08)+bytes([0,0,0xff,0]))
        r.write(r.prg,SONIC_MAP,mappings(SONIC_MAP))
        obj=bytearray(128);obj[O['oID']]=1;struct.pack_into('>I',obj,O['oMap'],SONIC_MAP);struct.pack_into('>H',obj,O['oTile'],0x85e0)
        struct.pack_into('>H',obj,O['oSprX'],256);struct.pack_into('>H',obj,O['oPlayerPitch'],0x80);r.write(r.prg,SONIC,obj)
        r.write(r.prg,SONIC_SHADOW,bytes([6])+bytes(127))
        self.write_actor(player,sprite,world)
        # Splash, dust, ring and stone markers become slot IDs, as in the native world mirror.
        obj=bytearray(128);obj[0]=world['splash_id'];r.write(r.prg,P1,obj)
        for n,value in enumerate(world['dust']):r.write(r.prg,P1+(6+n)*128,struct.pack('>H',value)+bytes(126))
        for n,value in enumerate(world['lost_rings']):r.write(r.prg,P2+(1+n)*128,bytes([value])+bytes(127))
        for n,value in enumerate(world['time_stone']):r.write(r.prg,P1+(3+n)*128,bytes([value])+bytes(127))
        if start:r.write(r.prg,P1+128,bytes([0xa])+bytes(127));r.write(r.prg,P1+256,bytes([0xb])+bytes(127))
        globals_=bytearray(r.read(r.prg,0x6000,64));struct.pack_into('>I',globals_,g['stampTypes']-0x6000,STAMP_TYPES);globals_[g['specStageID']-0x6000]=stage-1
        r.write(r.prg,0x6000,globals_)
        gfx=bytearray(256)
        for name,value in [('gfxCamX',player['x']>>16),('gfxCamY',player['y']>>16),('gfxCamZ',player['z']),('gfxPitch',0x80),('gfxYaw',player['yaw']>>16),('gfxFOV',0x80),('gfxCenter',0xffc0)]:struct.pack_into('>H',gfx,self.gfx[name],value)
        r.write(r.prg,GFX,gfx)
        r.call(self.code['spawn'])
        # SpawnUFOs sets the count; the native reset also sets the initial ring bonus.
        globals_=bytearray(r.read(r.prg,0x6000,64));struct.pack_into('>H',globals_,0x26,world['ring_bonus']);r.write(r.prg,0x6000,globals_)
    def step(self,held,tapped,stamp_map=None):
        r=self.r
        if stamp_map is not None:r.write(r.ram,0x20000,stamp_map)
        g=bytearray(r.read(r.prg,0x6000,64));g[0]=held;g[1]=tapped;g[0xd:0x10]=bytes(3);struct.pack_into('>I',g,0x30,LOG);r.write(r.prg,0x6000,g)
        r.call(self.code['update'])
        return self.state()
    def state(self):
        r=self.r;slots=r.read(r.prg,0x32000,0x1800);g=r.read(r.prg,0x6000,64)
        def slot(address):return slots[address-0x32000:address-0x32000+128]
        sonic=slot(SONIC);player={};sprite={}
        for fields,fmt,out in [(PLAYER_LONGS,'I',player),(PLAYER_WORDS,'H',player),(PLAYER_BYTES,'B',player),(SPRITE,'B',sprite)]:
            for name,label in fields.items():out[name]=struct.unpack_from('>'+fmt,sonic,O[label])[0]
        player['jump_timer']=int.from_bytes(g[0xa:0xc],'big');player['scroll']=g[0xc]
        splash=slot(P1)
        world={'timer':int.from_bytes(g[0x14:0x18],'big'),'rings':int.from_bytes(g[8:10],'big'),'splash_timer':struct.unpack_from('>H',splash,O['oTimer'])[0],
            'dust':[int.from_bytes(slot(P1+(6+n)*128)[:1],'big')<<8|slot(P1+(6+n)*128)[O['oRoutine']] for n in range(8)],
            'timer_frames':g[0x10],'speedup':g[0x11],'inactive':g[4],'stopped':g[5],'time_attack':(g[6]>>1)&1,'stage_over':g[0x12],'ufo_count':g[7],'time_ufo':slot(P2+23*128)[0],
            'sound':list(g[0xd:0x10]),'lost_rings':[slot(P2+(1+n)*128)[0] for n in range(7)],
            'splash_id':splash[0],'splash_routine':splash[O['oRoutine']],'splash_flags':splash[O['oFlags']],'splash_animation':splash[O['oAnim']],'splash_frame':splash[O['oAnimFrame']],'splash_time':splash[O['oAnimTime']],
            'ring_bonus':int.from_bytes(g[0x26:0x28],'big'),'got_time_stone':g[0x13],'time_stone':[slot(P1+(3+n)*128)[0] for n in range(3)]}
        def effect(data):return {name:struct.unpack_from('>'+fmt,data,O[field])[0] for name,(field,fmt) in EFFECT_FIELDS.items()}
        end=int.from_bytes(g[0x30:0x34],'big');raw=r.read(r.prg,LOG,end-LOG) if end>LOG else b'';log=[]
        for n in range(0,len(raw),132):log.append((int.from_bytes(raw[n:n+2],'big')|0x30000,raw[n+2],raw[n+3],raw[n+4:n+132]))
        drawn=[effect(bytes(128)) for _ in range(16)];draws=[]
        for address,before,after,data in log:
            code=object_code(address)
            if code==2:drawn[0]=effect(data)
            elif 6<=code<=13:drawn[code-5]=effect(data)
            elif 15<=code<=21:drawn[code-6]=effect(data)
            if code==36 and not struct.unpack_from('>I',data,O['oMap'])[0]:self.skipped+=1;continue
            draws.append(draw_entry(code,data))
        effects={'seed':int.from_bytes(g[0x1c:0x20],'big'),'ring_direction':g[0x25],'previous_held':g[2],'dust':[effect(slot(P1+(6+n)*128)) for n in range(8)],'rings':[effect(slot(P2+(1+n)*128)) for n in range(7)],'drawn':drawn}
        words=[]
        for address in [P2]+[P2+(8+n)*128 for n in range(8)]+[P1+(3+n)*128 for n in range(3)]:
            e=effect(slot(address));words+=[e[name] for name in EFFECT_FIELDS]
        for address in [P2+(16+n)*128 for n in range(6)]+[P2+23*128]:
            data=slot(address)
            for name,field,fmt in UFO_FIELDS:
                if field is None:
                    current,start=struct.unpack_from('>II',data,O['oVar5C'])[0],struct.unpack_from('>I',data,O['oVar58'])[0]
                    words.append((current-start+2)&65535 if data[0] else 0)
                else:words.append(struct.unpack_from('>'+fmt,data,O[field])[0])
        for address in [P3+n*128 for n in range(6)]+[P3+7*128,SONIC_SHADOW]:
            data=slot(address);words+=[struct.unpack_from('>'+fmt,data,O[field])[0] for name,field,fmt in SHADOW_FIELDS]
        for address in [P1+128,P1+256]:
            e=effect(slot(address));words+=[e[name] for name in EFFECT_FIELDS]
        words+=[sonic[O['oVar4F']],len(draws)]
        for d in draws:words+=d
        sat=r.read(r.prg,SAT,g[0x24]*8)
        return {'player':player,'sprite':sprite,'world':world,'effects':effects,'words':words,'draws':draws,'sat':sat,'log':log,'sprite_count':g[0x24]}
def fnv_words(values,h=2166136261):
    for value in values:
        for byte in (value&0xffffffff).to_bytes(4,'big'):h=((h^byte)*16777619)&0xffffffff
    return h
def effects_hash(e):
    values=[e['seed'],e['ring_direction'],e['previous_held']]
    for actor in e['dust']+e['rings']+e['drawn']:values+=[actor[name] for name in EFFECT_FIELDS]
    return fnv_words(values)
