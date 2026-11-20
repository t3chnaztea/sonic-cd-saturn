"""Original USA Sonic motion routines in the offline 68000 reference.

Only assembler syntax/absolute test addresses change. Sound/splash calls are
RTS stubs: this oracle checks motion and controller state, not those effects.
"""
import re,struct,subprocess
from special_assets import ROOT,SOURCE
from special_reference import Reference,WORK
ACTOR=SOURCE/'Objects/Sonic/Main.asm'
PAIRS={
 'speed':('ObjSonic_HandleSpeed','ObjSonic_Move'),
 'rotate':('ObjSonic_Rotate','ObjSonic_RotateSlow'),
 'move':('ObjSonic_Move','ObjSonic_BumpUp'),
 'jump':('ObjSonic_CheckJump','ObjSonic_Rotate'),
 'air':('ObjSonic_Jump','ObjSonic_Bumped'),
 'spring':('ObjSonic_Spring','ObjSonic_Hazard'),
 'fan':('ObjSonic_Fan','ObjSonic_Water'),
}
def object_offsets():
    text=(SOURCE/'Sub.asm').read_text().split('\trsreset',1)[1].split('; Graphics operation variable structure',1)[0]
    offset=0;result={f'oVar{i:X}':i for i in range(128)}
    for line in text.splitlines():
        m=re.match(r'\s*(?:(\w+)\s+)?rs\.([bwl])\s+(\$[0-9A-Fa-f]+|\d+)',line)
        if m:
            label,unit,count=m.groups()
            if label:result[label]=offset
            offset+=int(count.replace('$','0x'),0)*{'b':1,'w':2,'l':4}[unit]
    for name,alias in re.findall(r'^(\w+)\s+EQU\s+(oVar\w+)',ACTOR.read_text(),re.M):result[name]=result[alias]
    return result

def assemble_player(operation):
    source=ACTOR.read_text();start,end=PAIRS[operation]
    body=start+':\n'+source.split(start+':',1)[1].split(end+':',1)[0]
    if operation=='air':body='bra.w '+start+'\n'+body
    if operation in ['air']:
        a,b=PAIRS['rotate'];body+='\n'+a+':\n'+source.split(a+':',1)[1].split(b+':',1)[0]
    if operation=='move':
        text=(SOURCE/'Sub.asm').read_text();body+='\nGetCosine:'+text.split('GetCosine:',1)[1].split('\n\tinclude',1)[0]
    lines=[];scope=start;enabled=True
    for line in body.splitlines():
        line=line.split(';',1)[0].strip()
        if not line:continue
        if line.startswith('if REGION<>EUROPE'):enabled=True;continue
        if line=='else':enabled=False;continue
        if line=='endif':enabled=True;continue
        if not enabled:continue
        label=re.match(r'([A-Za-z_]\w*):',line)
        if label:scope=label[1]
        line=re.sub(r'(?<![\w])\.(\w+)',lambda m:scope+'__'+m[1],line)
        line=re.sub(r'\$([0-9A-Fa-f]+)',r'0x\1',line)
        line=re.sub(r'\bdc\.w\b','.word',line)
        lines.append(line)
    constants=object_offsets()|{'stageInactive':0x6000,'playerCtrlHold':0x6001,'playerCtrlTap':0x6002,'subScrollFlags':0x6003,'jumpTimer':0x6004,'FM_JUMP':1,'FM_SPRING':2,'FM_B8':3}
    preamble='.text\n'+''.join(f'.equ {k},{v}\n' for k,v in constants.items())
    # Float begins at its own original entry in the assembled air block.
    if operation=='air':
        float_body=preamble+'bra.w ObjSonic_Float\n'+'\n'.join(lines[1:])+'\nPlayFMSound:\nDeleteSplash:\n rts\n'
        compile_code('motion-float',float_body)
    return compile_code('motion-'+operation,preamble+'\n'.join(lines)+'\nPlayFMSound:\nDeleteSplash:\n rts\n')

def compile_code(name,body,link_address=None):
    source=WORK/f'{name}.s';obj=WORK/f'{name}.o';binary=WORK/f'{name}.bin';source.write_text(body)
    subprocess.run([ROOT/'.deps/build-binutils-m68k/gas/as-new','--register-prefix-optional','-m68000','-o',obj,source],check=True)
    if link_address is not None:
        linked=WORK/f'{name}.elf'
        subprocess.run([ROOT/'.deps/build-binutils-m68k/ld/ld-new','-Ttext',hex(link_address),'-e',hex(link_address),'-o',linked,obj],check=True)
        obj=linked
    subprocess.run([ROOT/'.deps/build-binutils-m68k/binutils/objcopy','-O','binary','-j','.text',obj,binary],check=True)
    return binary.read_bytes()

class PlayerReference:
    def __init__(self):
        self.reference=Reference();self.offsets=object_offsets()
        self.code={name:assemble_player(name) for name in PAIRS}
        self.code['float']=(WORK/'motion-float.bin').read_bytes()
    def run(self,operation,state,held=0,tapped=0,inactive=0):
        reference=self.reference;data=bytearray(128)
        longs={'x':'oX','y':'oY','yaw':'oPlayerYaw','sprite_y':'oSprY','sprite_velocity':'oPlayerSprYVel'}
        words={'z':'oZ','speed':'oPlayerSpeed','top_speed':'oPlayerTopSpeed','shoes':'oPlayerShoes','bump_time':'oPlayerBumpTime'}
        bytes_={'routine':'oRoutine','flags':'oFlags'}
        for names,fmt in [(longs,'I'),(words,'H'),(bytes_,'B')]:
            for name,field in names.items():struct.pack_into('>'+fmt,data,self.offsets[field],state[name])
        reference.write(reference.prg,0x32000,data)
        reference.write(reference.prg,0x6000,struct.pack('>4BH',inactive,held,tapped,state['scroll'],state['jump_timer']))
        reference.call(self.code['float' if operation=='air' and state['routine']==3 else operation],a0=0x32000)
        data=reference.read(reference.prg,0x32000,128);out=dict(state)
        for names,fmt in [(longs,'I'),(words,'H'),(bytes_,'B')]:
            for name,field in names.items():out[name]=struct.unpack_from('>'+fmt,data,self.offsets[field])[0]
        _,_,_,out['scroll'],out['jump_timer']=struct.unpack('>4BH',reference.read(reference.prg,0x6000,6))
        return out
