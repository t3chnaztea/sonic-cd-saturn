"""Original 68000 UFO path, projection, distance and collision primitives.

Only syntax and test addresses change. Move stops at the source .Draw label;
actor animation, bonuses, pool dispatch and completion are separate work.
"""
import re,struct
from special_assets import SOURCE
from special_reference import Reference
from special_player_reference import object_offsets,compile_code
from special_contact_reference import span
from special_effect_reference import assemble
O=object_offsets()
FIELDS={'x':('oX','I'),'y':('oY','I'),'x_velocity':('oXVel','I'),'y_velocity':('oYVel','I'),'sprite_x':('oSprX','I'),'sprite_y':('oSprY','I'),'path_offset':('oVar5C','I'),'path_time':('oVar60','H'),'z':('oZ','H'),'id':('oID','B'),'flags':('oFlags','B'),'player_collision':('oVar4F','B'),'item':('oVar62','B'),'unknown':('oVar63','B')}
class UFOReference:
    def __init__(self,reference=None):
        self.r=reference or Reference();sub=(SOURCE/'Sub.asm').read_text();ufo=(SOURCE/'Objects/UFO/Main.asm').read_text()
        constants=O|{'sonicObject':0x32000,'gfxVars':0x34800,'oUFOPath':O['oVar5C'],'oUFOPathStart':O['oVar58'],'oUFOPathTime':O['oVar60'],'oUFOPlayerCol':O['oVar4F']}
        self.gfx={};offset=0
        for line in ('gfxCamX'+sub.split('gfxCamX',1)[1].split('; ---',1)[0]).splitlines():
            m=re.match(r'\s*(?:(\w+)\s+)?rs\.([bwl])\s+(\$[0-9A-Fa-f]+|\d+)',line)
            if m:
                if m[1]:self.gfx[m[1]]=offset
                offset+=int(m[3].replace('$','0x'),0)*{'b':1,'w':2,'l':4}[m[2]]
        constants|=self.gfx
        move='ObjUFO_Main:'+ufo.split('ObjUFO_Main:',1)[1].split('.Draw:',1)[0]+'.Draw:\nrts\n'
        body=span(ufo,'ObjUFO_FollowPath','ObjUFO_Draw')+move
        body+=span(sub,'ObjUFO_CheckPlayerCol','ObjSonic_GetStamps')+span(sub,'Init3DSpritePos','GenGfxTraceTbl')
        body+=span(sub,'GetAngle','GetTrajectory')+span(sub,'GetDistance','Copy128')
        body+='\nDistance:\nlea sonicObject,a6\nmove.w oX(a6),d4\nmove.w oY(a6),d5\nmove.w oX(a0),d0\nmove.w oY(a0),d1\nbsr.w GetAngle\nmove.w oX(a6),d5\nmove.w oY(a6),d6\nmove.w oX(a0),d3\nmove.w oY(a0),d4\nbra.w GetDistance\n'
        self.code={}
        for kind,label in [('follow','ObjUFO_FollowPath'),('move','ObjUFO_Main'),('screen','ObjUFO_ChkOnScreen'),('collision','ObjUFO_CheckPlayerCol'),('distance','Distance'),('project','Set3DSpritePos')]:
            entry=('bsr.w Init3DSpritePos\n' if kind=='project' else '')+'bra.w '+label+'\n'
            self.code[kind]=compile_code('ufo-'+kind,assemble(entry+body,constants),link_address=0x1000)
    def run(self,kind,u,path=b'',sx=2048,sy=2048,sz=352,sid=1,collision=0,ys=0,yc=256):
        r=self.r;obj=bytearray(128)
        for name,(field,fmt) in FIELDS.items():struct.pack_into('>'+fmt,obj,O[field],u[name]+(0x18000 if name=='path_offset' else 0))
        struct.pack_into('>I',obj,O['oVar58'],0x18002);r.write(r.prg,0x33000,obj)
        obj=bytearray(128);obj[O['oID']]=sid;obj[O['oPlayerUFOCol']]=collision
        for field,value in [('oX',sx),('oY',sy),('oZ',sz)]:struct.pack_into('>H',obj,O[field],value)
        r.write(r.prg,0x32000,obj);r.write(r.prg,0x18000,path)
        gfx=bytearray(128)
        for field,value in [('gfxFOV',128),('gfxCenter',-64),('gfxYawSin',ys),('gfxYawCos',yc)]:struct.pack_into('>H',gfx,self.gfx[field],value&65535)
        r.write(r.prg,0x34800,gfx);r.call(self.code[kind],a0=0x33000)
        obj=r.read(r.prg,0x33000,128)
        out={name:struct.unpack_from('>'+fmt,obj,O[field])[0]-(0x18000 if name=='path_offset' else 0) for name,(field,fmt) in FIELDS.items()}
        return out,r.read(r.prg,0x32000,128)[O['oPlayerUFOCol']],r.lib.s68k_get_reg(0)&0xffffffff
