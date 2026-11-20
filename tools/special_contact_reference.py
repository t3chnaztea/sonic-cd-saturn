"""Original active Sonic/contact/splash/timer routines in the offline 68000.

CheckWin is a stub until UFO completion is integrated. Time-UFO spawn executes
its original routine; this phase compares its ID marker, not UFO motion.
"""
import re,struct
from special_assets import SOURCE
from special_reference import Reference
from special_player_reference import object_offsets,compile_code,ACTOR
from special_sonic_assets import mappings
O=object_offsets()
PLAYER_LONGS={'x':'oX','y':'oY','yaw':'oPlayerYaw','sprite_y':'oSprY','sprite_velocity':'oPlayerSprYVel','x_velocity':'oXVel','y_velocity':'oYVel'}
PLAYER_WORDS={'z':'oZ','speed':'oPlayerSpeed','top_speed':'oPlayerTopSpeed','shoes':'oPlayerShoes','bump_time':'oPlayerBumpTime'}
PLAYER_BYTES={'routine':'oRoutine','flags':'oFlags','hurt':'oPlayerTimer','stamp_c':'oPlayerStampC','stamp_tl':'oPlayerStampTL','stamp_tr':'oPlayerStampTR','stamp_br':'oPlayerStampBR','stamp_bl':'oPlayerStampBL','orientation':'oPlayerStampOri'}
SPRITE={'tilt':'oPlayerTilt','animation':'oAnim','frame':'oAnimFrame','time':'oAnimTime','time_copy':'oAnimTime2','art':'oSpriteFlag'}
def span(text,start,end):return start+':'+text.split(start+':',1)[1].split(end+':',1)[0]
def splash_mappings():
    # This source table only uses local labels, byte/long data and alignment.
    text=(SOURCE/'Objects/Splash/Data/Mappings.asm').read_text();labels={};rows=[];offset=0
    for raw in text.splitlines():
        line=raw.split(';',1)[0].strip()
        if not line:continue
        if line.endswith(':'):labels[line[:-1]]=offset;continue
        if line=='even':offset=(offset+1)&~1;continue
        m=re.fullmatch(r'dc\.([bl])\s+(.+)',line);assert m,line
        width=1 if m[1]=='b' else 4
        for value in m[2].split(','):rows.append((offset,width,value.strip()));offset+=width
    result=bytearray(offset)
    for at,width,value in rows:result[at:at+width]=(labels[value]+0x1a000 if value in labels else int(value.replace('$','0x'),0)).to_bytes(width,'big')
    return bytes(result)
class ContactReference:
    def __init__(self):
        self.r=Reference();actor=ACTOR.read_text();sub=(SOURCE/'Sub.asm').read_text();splash=(SOURCE/'Objects/Splash/Main.asm').read_text();ufo=(SOURCE/'Objects/UFO/Main.asm').read_text()
        targets={1:'ObjSonic_Ground',2:'ObjSonic_Jump',3:'ObjSonic_Float',4:'ObjSonic_Bumped',5:'ObjSonic_Sink',6:'ObjSonic_Sink2',7:'ObjSonic_Hurt',19:'ObjSonic_Boosted'}
        targets|={8+n:f'ObjSonic_TimeStone{n+1}' for n in range(11)}|{20+n:f'ObjSonic_Start{n+1}' for n in range(4)}
        body='ObjSonic_Index:\n'+''.join('dc.w '+targets.get(n,'Unsupported')+'-ObjSonic_Index\n' for n in range(24))
        body+=span(actor,'ObjSonic','ObjSonic_Init')+span(actor,'ObjSonic_Start1','ObjSonic_GetStartPos')
        body+=span(actor,'ObjSonic_StampCollide','ObjSonic_RotateSlow')+span(actor,'ObjSonic_HandleSpeed','ObjSonic_BumpUp')+span(actor,'ObjSonic_Tilt','ObjSonic_LoadArt')
        body+=span(sub,'ObjSonic_GetStamps','StampTypes_SS1')+span(sub,'SetObjAnim','ObjectIndex')+span(sub,'PlayFMSound','Random')+span(sub,'UpdateTimer','GetAngle')
        body+='GetCosine:'+sub.split('GetCosine:',1)[1].split('\n\tinclude',1)[0]
        body+='\nObjectIndex:\n'+''.join('dc.l '+('ObjSplash' if n==8 else 'Unsupported')+'\n' for n in range(1,17))
        body+=span(sub,'RunObject','InitZBuffer')
        body+=span(sub,'Fill128','WaitGfxOperation')
        body+='\n'+splash+'\n'+span(ufo,'SpawnTimeUFO','TimeUFOPath')
        path=(SOURCE/'Data/Time UFO Path.bin').read_bytes();body+='\nTimeUFOPath:\n dc.b '+','.join(map(str,path))+'\n even\n'
        body+='\nUnsupported:\nObjSonic_CheckWin:\nObjSonic_LoadArt:\n rts\n'
        constants=O|{'oSize':128,'DUSTOBJCOUNT':8,'ctrlData':0x6000,'playerCtrlData':0x6002,'playerCtrlHold':0x6002,'playerCtrlTap':0x6003,'stageInactive':0x6004,'timeStopped':0x6005,'specStageFlags':0x6006,'ufoCount':0x6007,'specStageRings':0x6008,'jumpTimer':0x600a,'subScrollFlags':0x600c,'subSndQueue1':0x600d,'subSndQueue2':0x600e,'subSndQueue3':0x600f,'timerFrames':0x6010,'timerSpeedUp':0x6011,'stageOver':0x6012,'specStageTimer':0x6014,'stampTypes':0x6018,'curSpriteSlot':0x6020,'spriteCount':0x6024,'sonicObject':0x32000,'splashObject':0x33000,'dustObjects':0x33200,'timeUFOObject':0x34400,'ufoObject1':0x34400,'ufoShadowObj1':0x34480,'timeStoneObject':0x34600,'sparkleObject1':0x34680,'sparkleObject2':0x34700,'gfxVars':0x35000,'WORDRAM2M':0x80000,'STAMPMAP':0x20000,'MapSpr_Sonic':0x18000,'MapSpr_Splash':0x1a000}
        for name,alias in re.findall(r'^(\w+)\s+EQU\s+(oVar\w+)',ufo,re.M):constants[name]=O[alias]
        shadow=(SOURCE/'Objects/Shadow/Main.asm').read_text();m=re.search(r'^oShadowParent\s+EQU\s+(oVar\w+)',shadow,re.M);assert m;constants['oShadowParent']=O[m[1]]
        for n in range(1,8):constants['ringObject'+str(n)]=0x33800+(n-1)*128
        for i,name in enumerate(['gfxCamX','gfxCamY','gfxCamZ','gfxPitch']):constants[name]=i*2
        constants['gfxYaw']=12
        sound=(SOURCE.parent/'Sound Drivers/FM/_Sound IDs.inc').read_text();value=0x90
        for raw in sound.splitlines():
            line=raw.split(';',1)[0].strip()
            if line.startswith('rsset'):value=int(line.split()[1].replace('$','0x'),0)
            m=re.fullmatch(r'(FM\w+)\s+rs\.([bw])\s+(\d+)',line)
            if m:constants[m[1]]=value;value+=int(m[3])*(1 if m[2]=='b' else 2)
        lines=[];scope='Entry';enabled=True
        for raw in body.splitlines():
            line=raw.split(';',1)[0].strip()
            if not line:continue
            if line.startswith('if REGION<>EUROPE'):enabled=True;continue
            if line=='else':enabled=False;continue
            if line=='endif':enabled=True;continue
            if not enabled:continue
            if line=='even':lines.append('.balign 2');continue
            label=re.match(r'([A-Za-z_]\w*):',line)
            if label:scope=label[1]
            line=re.sub(r'(?<![\w])\.(\w+)',lambda m:scope+'__'+m[1],line)
            line=line.replace('#(9<<16)|(59<<8)|59','#0x93b3b')
            line=re.sub(r'\$([0-9A-Fa-f]+)',r'0x\1',line)
            for a,b in [('dc.b','.byte'),('dc.w','.word'),('dc.l','.long')]:line=line.replace(a,b)
            lines.append(line)
        preamble='.text\n'+''.join(f'.equ {k},{v}\n' for k,v in constants.items());self.code={}
        for operation,label in [('contacts','ObjSonic_StampCollide'),('bumper','ObjSonic_CheckBumper'),('sample','ObjSonic_GetStamps'),('step','ObjSonic'),('timer','UpdateTimer'),('splash','RunObject'),('splash_actor','ObjSplash'),('state','State')]:
            entry='bra.w '+label+'\n'
            state='\nState:\nmoveq #0,d0\nmove.b oRoutine(a0),d0\nadd.w d0,d0\nlea ObjSonic_Index(pc),a1\nmove.w (a1,d0.w),d0\njmp (a1,d0.w)\n'
            self.code[operation]=compile_code('contact-'+operation,preamble+entry+'\n'.join(lines)+state,link_address=0x1000)
        self.r.write(self.r.prg,0x18000,mappings(0x18000));self.r.write(self.r.prg,0x1a000,splash_mappings())
    def run(self,operation,p,s,w,parts,held=0,tapped=0):
        r=self.r;obj=bytearray(128)
        struct.pack_into('>I',obj,O['oMap'],0x18000);struct.pack_into('>H',obj,O['oTile'],0x85e0);struct.pack_into('>H',obj,O['oSprX'],256)
        for fields,fmt in [(PLAYER_LONGS,'I'),(PLAYER_WORDS,'H'),(PLAYER_BYTES,'B'),(SPRITE,'B')]:
            for name,label in fields.items():struct.pack_into('>'+fmt,obj,O[label],(s if fields is SPRITE else p)[name])
        r.write(r.prg,0x32000,obj);globals_=bytearray(40)
        globals_[:8]=bytes([held,tapped,held,tapped,w['inactive'],w['stopped'],w['time_attack']*2,w['ufo_count']])
        struct.pack_into('>HH',globals_,8,w['rings'],p['jump_timer']);globals_[12]=p['scroll'];globals_[13:16]=bytes(w['sound'])
        globals_[16:19]=bytes([w['timer_frames'],w['speedup'],w['stage_over']]);struct.pack_into('>II',globals_,20,w['timer'],0x34000);struct.pack_into('>I',globals_,32,0x36000)
        r.write(r.prg,0x6000,globals_);r.write(r.prg,0x34000,parts[2]);r.write(r.ram,0x20000,parts[1]);r.write(r.prg,0x36000,bytes(640))
        obj=bytearray(128);obj[0]=w['splash_id'];obj[O['oRoutine']]=w['splash_routine'];obj[O['oFlags']]=w['splash_flags'];obj[O['oAnim']]=w['splash_animation'];obj[O['oAnimFrame']]=w['splash_frame'];obj[O['oAnimTime']]=w['splash_time'];obj[O['oAnimTime2']]=0 if w['splash_animation'] else 1;struct.pack_into('>H',obj,O['oTimer'],w['splash_timer']);struct.pack_into('>I',obj,O['oMap'],0x1a000);struct.pack_into('>H',obj,O['oTile'],0x8582);struct.pack_into('>H',obj,O['oSprX'],256);struct.pack_into('>H',obj,O['oSprY'],344);r.write(r.prg,0x33000,obj)
        for n,value in enumerate(w['dust']):r.write(r.prg,0x33200+n*128,struct.pack('>H',value)+bytes(126))
        for n,value in enumerate(w['lost_rings']):r.write(r.prg,0x33800+n*128,bytes([value])+bytes(127))
        r.write(r.prg,0x34400,bytes([w['time_ufo']])+bytes(255))
        for n,value in enumerate(w.get('time_stone',[0,0,0])):r.write(r.prg,0x34600+n*128,bytes([value])+bytes(127))
        r.call(self.code[operation],a0=0x33000 if operation in ['splash','splash_actor'] else 0x32000)
        pdata=r.read(r.prg,0x32000,128);outp=dict(p);outs=dict(s);outw=dict(w)
        for fields,fmt in [(PLAYER_LONGS,'I'),(PLAYER_WORDS,'H'),(PLAYER_BYTES,'B'),(SPRITE,'B')]:
            for name,label in fields.items():(outs if fields is SPRITE else outp)[name]=struct.unpack_from('>'+fmt,pdata,O[label])[0]
        g=r.read(r.prg,0x6000,40);outp['jump_timer']=int.from_bytes(g[10:12],'big');outp['scroll']=g[12]
        outw.update(rings=int.from_bytes(g[8:10],'big'),sound=list(g[13:16]),timer_frames=g[16],speedup=g[17],stage_over=g[18],timer=int.from_bytes(g[20:24],'big'),inactive=g[4])
        if 'time_stone' in w:outw['time_stone']=[r.read(r.prg,0x34600+n*128,1)[0] for n in range(3)]
        outw['dust']=[int.from_bytes(r.read(r.prg,0x33200+n*128,2),'big') for n in range(8)];outw['lost_rings']=[r.read(r.prg,0x33800+n*128,1)[0] for n in range(7)];outw['time_ufo']=r.read(r.prg,0x34400,1)[0]
        obj=r.read(r.prg,0x33000,128)
        outw.update(splash_id=obj[0],splash_routine=obj[O['oRoutine']],splash_flags=obj[O['oFlags']],splash_animation=obj[O['oAnim']],splash_frame=obj[O['oAnimFrame']],splash_time=obj[O['oAnimTime']],splash_timer=int.from_bytes(obj[O['oTimer']:O['oTimer']+2],'big'))
        return outp,outs,outw
