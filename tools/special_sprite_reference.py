"""Execute original Sonic tilt/animation and complete DrawObject sprite output."""
import re,struct
from special_assets import SOURCE
from special_sonic_assets import mappings,original_art
from special_player_reference import ACTOR,object_offsets,compile_code
from special_reference import Reference
class SpriteReference:
    def __init__(self):
        self.reference=Reference();self.offsets=object_offsets();self.art=original_art()
        actor=ACTOR.read_text();sub=(SOURCE/'Sub.asm').read_text()
        body='ObjSonic_Tilt:'+actor.split('ObjSonic_Tilt:',1)[1].split('ObjSonic_LoadArt:',1)[0]
        body+='\nSetObjAnim:'+sub.split('SetObjAnim:',1)[1].split('ObjectIndex:',1)[0]
        lines=[];scope='Test'
        for raw in body.splitlines():
            line=raw.split(';',1)[0].strip()
            if not line:continue
            label=re.match(r'([A-Za-z_]\w*):',line)
            if label:scope=label[1]
            line=re.sub(r'(?<![\w])\.(\w+)',lambda m:scope+'__'+m[1],line)
            line=re.sub(r'\$([0-9A-Fa-f]+)',r'0x\1',line)
            line=re.sub(r'\bdc\.b\b','.byte',line)
            lines.append(line)
        constants=self.offsets|{'stageInactive':0x6000,'playerCtrlHold':0x6001,'curSpriteSlot':0x6004,'spriteCount':0x6008}
        preamble='.text\n'+''.join(f'.equ {k},{v}\n' for k,v in constants.items())
        self.code={}
        for name,label in [('tilt','ObjSonic_Tilt'),('choose','ObjSonic_Animate'),('draw','DrawObject'),('set','SetObjAnim'),('change','ChgObjAnim')]:
            entry='moveq #0,d0\nmove.b 0x6002,d0\nbra.w '+label+'\n'
            self.code[name]=compile_code('sprite-'+name,preamble+entry+'\n'.join(lines)+'\n')
        self.reference.write(self.reference.prg,0x18000,mappings(0x18000))
    def run(self,operation,sprite,flags=0,speed=0,held=0,inactive=0,animation=0):
        r=self.reference;o=self.offsets;data=bytearray(128)
        struct.pack_into('>I',data,o['oMap'],0x18000);struct.pack_into('>H',data,o['oTile'],0x85e0)
        struct.pack_into('>H',data,o['oSprX'],256);struct.pack_into('>H',data,o['oSprY'],344)
        struct.pack_into('>H',data,o['oPlayerSpeed'],speed);data[o['oFlags']]=flags
        names={'tilt':'oPlayerTilt','animation':'oAnim','frame':'oAnimFrame','time':'oAnimTime','time_copy':'oAnimTime2','art':'oSpriteFlag'}
        for name,label in names.items():data[o[label]]=sprite[name]
        r.write(r.prg,0x32000,data);r.write(r.prg,0x6000,struct.pack('>4BI8B',inactive,held,animation,0,0x35000,*([0]*8)))
        r.write(r.prg,0x35000,bytes(80*8));r.call(self.code[operation],a0=0x32000)
        data=r.read(r.prg,0x32000,128);out={name:data[o[label]] for name,label in names.items()}
        count=r.read(r.prg,0x6008,1)[0]
        return out,data[o['oFlags']],r.read(r.prg,0x35000,count*8)
    def pixels(self,sat,frame):
        result=bytearray(96*96);raw=self.art[frame]
        for sy,size,link,tile,sx in struct.iter_unpack('>HBBHH',sat):
            left=sx-256+48;top=sy-344+64;width=((size>>2)&3)+1;height=(size&3)+1
            # Render independently from the original SAT: each tile is
            # column-major; piece flips reverse tile order and within-tile bits.
            base=(tile&2047)-0x5e0
            assert 0<=base and (base+width*height)*32<=len(raw)
            for tx in range(width):
                for ty in range(height):
                    source=raw[(base+tx*height+ty)*32:(base+tx*height+ty+1)*32]
                    for py in range(8):
                        for px in range(8):
                            u=tx*8+px;v=ty*8+py
                            if tile&0x800:u=width*8-1-u
                            if tile&0x1000:v=height*8-1-v
                            x=left+u;y=top+v
                            value=(source[py*4+px//2]>>(4 if px%2==0 else 0))&15
                            if 0<=x<96 and 0<=y<96 and not result[y*96+x]:result[y*96+x]=value
        return bytes(result)
