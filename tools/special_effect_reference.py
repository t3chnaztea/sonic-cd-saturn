"""Original dust/lost-ring RunObject and RNG, including retained D1 bits."""
import re,struct
from special_assets import SOURCE
from special_reference import Reference
from special_player_reference import object_offsets,compile_code
from special_contact_reference import span
O=object_offsets()
FIELDS={'x':('oSprX','I'),'y':('oSprY','I'),'x_velocity':('oVar3C','I'),'y_velocity':('oVar40','I'),'timer':('oTimer','H'),'id':('oID','B'),'routine':('oRoutine','B'),'flags':('oFlags','B'),'animation':('oAnim','B'),'frame':('oAnimFrame','B'),'time':('oAnimTime','B'),'time_copy':('oAnimTime2','B'),'art':('oSpriteFlag','B'),'item_type':('oVar52','B')}
def mapping(name,base,filename="Mappings.asm"):
    text=(SOURCE/f'Objects/{name}/Data/{filename}').read_text();labels={};rows=[];offset=0
    for raw in text.splitlines():
        line=raw.split(';',1)[0].strip()
        if not line:continue
        if line.endswith(':'):labels[line[:-1]]=offset;continue
        if line=='even':offset=(offset+1)&~1;continue
        match=re.fullmatch(r'dc\.([bwl])\s+(.+)',line);assert match,line
        width={'b':1,'w':2,'l':4}[match[1]]
        for value in match[2].split(','):rows.append((offset,width,value.strip()));offset+=width
    data=bytearray(offset)
    for offset,width,value in rows:
        result=0
        for term in value.split('|'):result|=labels[term]+base if term in labels else int(term.replace('$','0x'),0)
        data[offset:offset+width]=result.to_bytes(width,'big')
    return bytes(data)
def assemble(body,constants):
    lines=[];scope='Entry'
    for raw in body.splitlines():
        line=raw.split(';',1)[0].strip()
        if not line:continue
        if line=='even':lines.append('.balign 2');continue
        if re.match(r'\w+\s+EQU\s+',line):continue
        label=re.match(r'([A-Za-z_]\w*):',line)
        if label:scope=label[1]
        line=re.sub(r'(?<![\w])\.(\w+)',lambda m:scope+'__'+m[1],line)
        line=re.sub(r'\$([0-9A-Fa-f]+)',r'0x\1',line)
        line=re.sub(r'%([01]+)',lambda m:str(int(m[1],2)),line)
        for a,b in [('dc.b','.byte'),('dc.w','.word'),('dc.l','.long')]:line=line.replace(a,b)
        lines.append(line)
    return '.text\n'+''.join(f'.equ {k},{v}\n' for k,v in constants.items())+'\n'.join(lines)+'\n'
class EffectReference:
    def __init__(self,reference=None):
        self.r=reference or Reference();sub=(SOURCE/'Sub.asm').read_text();dust=(SOURCE/'Objects/Dust/Main.asm').read_text();item=(SOURCE/'Objects/Item/Main.asm').read_text()
        body=span(dust,'ObjDust','MapSpr_Dust')+span(item,'ObjLostRing','MapSpr_Item')+span((SOURCE/'Objects/Explosion/Main.asm').read_text(),'FindExplosionObjSlot','MapSpr_Explosion')
        body+=span(sub,'RunObject','InitZBuffer')+span(sub,'Fill128','WaitGfxOperation')+span(sub,'SetObjAnim','ObjectIndex')+span(sub,'PlayFMSound','Init3DSpritePos')
        body+=span((SOURCE/'Objects/Shadow/Main.asm').read_text(),'ObjSonicShadow','ObjUFOShadow')+span(sub,'Init3DSpritePos','GenGfxTraceTbl')
        body+='\nObjectIndex:\n'+''.join('dc.l '+{4:'ObjItem',7:'ObjDust',12:'ObjExplosion',13:'ObjLostRing'}.get(n,'Unused')+'\n' for n in range(1,17))+'\nUnused:\nrts\n'
        constants=O|{'oSize':128,'oDustXVel':O['oVar3C'],'oItemXVel':O['oVar3C'],'oItemYVel':O['oVar40'],'oItemType':O['oVar52'],'MapSpr_Dust':0x1b000,'MapSpr_Item':0x1c000,'rngSeed':0x6000,'lostRingXDir':0x6004,'playerCtrlData':0x6005,'subSndQueue1':0x6006,'subSndQueue2':0x6007,'subSndQueue3':0x6008,'curSpriteSlot':0x600c,'spriteCount':0x6010,'sonicObject':0x32000,'FM_RINGLOSS':0x94,'FM_RING':0x95,'FM_A3':0xa3,'oItemSpawnType':O['oVar51'],'MapSpr_Explosion':0x1e000,'explosionObjs':0x36000,'EXPLODEOBJCNT':8,'MapSpr_Shadow':0x1d000,'oShadowSprite':O['oVar52'],'gfxVars':0x34800}
        offset=0
        variables='gfxCamX'+sub.split('gfxCamX',1)[1].split('; ---',1)[0]
        for line in variables.splitlines():
            m=re.match(r'\s*(?:(\w+)\s+)?rs\.([bwl])\s+(\$[0-9A-Fa-f]+|\d+)',line)
            if m:
                if m[1]:constants[m[1]]=offset
                offset+=int(m[3].replace('$','0x'),0)*{'b':1,'w':2,'l':4}[m[2]]
        self.code={}
        body+='\nActorOnly:\nmoveq #0,d0\nmove.b (a0),d0\nbeq.w Unused\ncmpi.b #7,d0\nbeq.w ObjDust\ncmpi.b #4,d0\nbeq.w ObjItem\ncmpi.b #12,d0\nbeq.w ObjExplosion\nbra.w ObjLostRing\n'
        for kind,label in [('step','RunObject'),('actor','ActorOnly'),('random','Random'),('draw','DrawObject'),('shadow','ObjSonicShadow'),('find_explosion','FindExplosionObjSlot')]:
            entry='move.l 0x6014,d1\nbra.w '+label+'\n'
            self.code[kind]=compile_code('effect-'+kind,assemble(entry+body,constants),link_address=0x1000)
        self.r.write(self.r.prg,0x1b000,mapping('Dust',0x1b000));self.r.write(self.r.prg,0x1c000,mapping('Item',0x1c000));self.r.write(self.r.prg,0x1a000,mapping('Splash',0x1a000));self.r.write(self.r.prg,0x1d000,mapping('Shadow',0x1d000));self.r.write(self.r.prg,0x1e000,mapping('Explosion',0x1e000))
        body='lea 0x40000,a4\nbra.w NemDecToRAM\n'+span((SOURCE/'Main.asm').read_text(),'NemDec','EniDec')
        self.nemesis_code=compile_code('effect-nemesis',assemble(body,{'nemBuffer':0x7000,'VDPDATA':0xc00000}),link_address=0x1000)
    def shadow_d1(self,d1):
        # Run the original intervening Sonic shadow on the Sonic object left
        # by ContactReference. It shares Sonic's position, so distance is zero.
        r=self.r;obj=bytearray(128);obj[0]=1;r.write(r.prg,0x33000,obj)
        g=bytearray(32);struct.pack_into('>I',g,12,0x35000);struct.pack_into('>I',g,20,d1);r.write(r.prg,0x6000,g)
        gfx=bytearray(128);struct.pack_into('>HH',gfx,22,128,0xffc0);r.write(r.prg,0x34800,gfx)
        r.call(self.code['shadow'],a0=0x33000)
        return r.lib.s68k_get_reg(1)&0xffffffff
    def decompress(self,data,size):
        self.r.write(self.r.prg,0x10000,data+bytes(16));self.r.write(self.r.prg,0x40000,bytes(size+16))
        self.r.call(self.nemesis_code,a0=0x10000)
        return self.r.read(self.r.prg,0x40000,size)
    def run(self,e,context,held=0,sonic_x=256<<16,sonic_y=344<<16,operation='step',sounds=(0,0,0),map_override=None):
        r=self.r;obj=bytearray(128)
        for name,(field,fmt) in FIELDS.items():struct.pack_into('>'+fmt,obj,O[field],e[name])
        map_address,tile=(0x1e000,0x87ae) if e['id']==12 else (0x1b000,0x87ae) if e['id']==7 else (0x1a000,0x8582) if e['id']==8 else (0x1c000,0xe78f if e['id']==13 else 0x878f)
        if map_override is not None:map_address,tile=map_override
        struct.pack_into('>I',obj,O['oMap'],map_address);struct.pack_into('>H',obj,O['oTile'],tile)
        r.write(r.prg,0x33000,obj);obj=bytearray(128);struct.pack_into('>II',obj,O['oSprX'],sonic_x,sonic_y);r.write(r.prg,0x32000,obj)
        globals_=bytearray(32);struct.pack_into('>I',globals_,0,context['seed']);globals_[4:6]=bytes([context['ring_direction'],held]);globals_[6:9]=bytes(sounds);struct.pack_into('>I',globals_,12,0x35000);struct.pack_into('>I',globals_,20,context['d1']);r.write(r.prg,0x6000,globals_);r.write(r.prg,0x35000,bytes(640))
        r.call(self.code[operation],a0=0x33000)
        obj=r.read(r.prg,0x33000,128);g=r.read(r.prg,0x6000,32)
        out={name:struct.unpack_from('>'+fmt,obj,O[field])[0] for name,(field,fmt) in FIELDS.items()}
        context={'seed':int.from_bytes(g[:4],'big'),'ring_direction':g[4],'d1':r.lib.s68k_get_reg(1)&0xffffffff}
        sat=r.read(r.prg,0x35000,g[16]*8)
        return out,context,sat,list(g[6:9]),r.lib.s68k_get_reg(0)&0xffffffff

    def find_explosion(self,pool):
        data=bytearray(128*8)
        for i,(id,routine) in enumerate(pool):data[i*128:i*128+2]=bytes([id,routine])
        self.r.write(self.r.prg,0x36000,data);self.r.call(self.code['find_explosion'])
        address=self.r.lib.s68k_get_reg(9)&0xffffffff
        assert address in range(0x36000,0x36401,128),hex(address)
        available=bool(self.r.lib.s68k_get_reg(17)&4)
        assert available==(address<0x36400),(address,available)
        return (address-0x36000)//128 if available else -1
