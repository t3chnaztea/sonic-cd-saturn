#!/usr/bin/env python3
"""Run a retail special stage (1-8) in the pinned Sega CD core with scripted input.

QA oracle only; nothing here is linked into the Saturn build. The retail disc
boots unmodified. When the initial program (IPX___.MMD) is in Work RAM, its
Backup RAM initialization call (the core's RAM cartridge reports unformatted,
a fatal loop in BRAMINIT) jumps to a routine that sets Level/Main.asm new-game
state (three lives, next 1-UP at 5000) and calls the level loop's normal-mode
special stage entry (IPX.asm .SpecialStage) for the route's stage (curSpecStage)
without time stones. Routes named <route>-ss<n> play stage n; plain names play stage 1. Scripted pad
input is indexed by the special stage V-INT counter. Every emulated frame
records the displayed pixels, VDP state and program variables named in the
disassembly.
"""
import json,re,struct,sys,zlib
from native import IS_BROWSER
if IS_BROWSER:
    import browser_ctypes as C
else:
    import ctypes as C
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
from scd_source import SRC
OUT=ROOT/'build/special-retail'
RETAIL=ROOT/'build/retail'

def evaluate(expr,names):
    expr=re.sub(r'\$([0-9A-Fa-f]+)',r'0x\1',expr.strip())
    expr=re.sub(r'%([01]+)',r'0b\1',expr).replace('/','//')
    return eval(expr,{'__builtins__':{}},names)

def rs_symbols(text,names,mask=0xffffffff):
    """Addresses of rs labels and EQU values, in source order."""
    names=dict(names);symbols={};rs=None
    for raw in text.splitlines():
        line=raw.split(';',1)[0].rstrip()
        if not line.strip():continue
        m=re.match(r'\s+rsset\s+(.+)',line)
        if m:
            try:rs=evaluate(m[1],names|symbols)&mask
            except Exception:rs=None
            continue
        if re.match(r'\s+rsreset\b',line):rs=0;continue
        m=re.match(r'(\w+)\s+EQU\s+(.+)',line)
        if m:
            try:names[m[1]]=evaluate(m[2].replace('__rs',str(rs or 0)),names|symbols)
            except Exception:pass
            continue
        m=re.match(r'(\w+)?\s+rs\.([bwl])\s+(.+)',line)
        if m and rs is not None:
            if m[1]:symbols[m[1]]=rs
            try:rs+=evaluate(m[3].replace('__rs',str(rs)),names|symbols)*{'b':1,'w':2,'l':4}[m[2]]
            except Exception:rs=None
    return symbols,names

def layout():
    _,names=rs_symbols((SRC/'Special Stage/_Common.inc').read_text(),{})
    main,_=rs_symbols((SRC/'_Include/Main CPU Variables.inc').read_text(),{'WORKRAM':0xff0000},0xffffff)
    ss,_=rs_symbols((SRC/'Special Stage/Main.asm').read_text().split('; MMD header',1)[0],names|{'WORKRAM':0xff0000},0xffffff)
    sub_text=(SRC/'Special Stage/Sub.asm').read_text()
    gfx,_=rs_symbols(sub_text.split('; Graphics operation variable structure',1)[1].split('; Variables',1)[0],{})
    sub,_=rs_symbols(sub_text.split('; Variables',1)[1].split('; Program start',1)[0],{'PRGRAM':0,'oSize':0x80,'gfxSize':gfx['gfxSize']})
    system,_=rs_symbols((SRC/'_Include/System.inc').read_text(),{})
    return main,ss,sub,{k:v for k,v in system.items() if k.startswith('SCMD_')}

def find(data,pattern,base,count=1):
    """Unique hex-regex match in 68000 code; returns (address, groups)."""
    text=data.hex();hits=[m for m in re.finditer(pattern,text) if m.start()%2==0]
    assert len(hits)==count,(pattern,len(hits))
    m=hits[0];return base+m.start()//2,[int(g,16) for g in m.groups()]

def retail_program_labels():
    """Program data labels inside SPMM__.MMD, located by the code that uses them."""
    raw=(RETAIL/'SPMM__.MMD').read_bytes();origin,size,entry=struct.unpack_from('>IHI',raw,2)
    code=raw[0x100:0x100+(size+1)*4];labels={'origin':origin,'entry':entry}
    _,(labels['ringBonus'],labels['timeBonus'])=find(code,'303900a12024c0fc001423c0(........)203900a12026c0fc001423c0(........)',origin)
    _,(labels['scoreTallied'],)=find(code,'4a39(........)66..2039%08xd0b9%08x'%(labels['timeBonus'],labels['ringBonus']),origin)
    _,(labels['scrollDisable'],)=find(code,'0839000000a1200f66..4a39(........)66..0c39000000a12023',origin,3)
    at,(mode,shift)=find(code,'203c000800006100....d1b8....e280d1b8....41fa(....)43fa(....)',origin)
    # PC-relative LEA displacements are based at their extension words (+22, +26).
    labels['bgScrollMode']=at+22+(mode-65536 if mode&0x8000 else mode);labels['ss1BGScrollShift']=at+26+(shift-65536 if shift&0x8000 else shift)
    _,(labels['timeStonePalDelay'],)=find(code,'4a3900a1202b66..4a39(........)',origin)
    at,(index,)=find(code,'43fa(....)7a087c003e3c03e8',origin)
    labels['palCycleIndex']=at+2+(index-65536 if index&0x8000 else index)
    _,(labels['animTimer'],timer2,labels['animFrame'],frame2)=find(code,'5279(........)02790007(........)66..5279(........)02790001(........)',origin)
    assert timer2==labels['animTimer'] and frame2==labels['animFrame']
    _,(labels['gotLeadDigit'],)=find(code,'13fc0000(........)43fa....283c4a300003',origin)
    labels['VInterrupt']=struct.unpack_from('>I',code,2)[0]
    return labels,raw

def png(path,frame):
    """Diagnostic PNG from a core RGB565 frame."""
    width,height,data=frame;rows=bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            v=data[(y*width+x)*2]|data[(y*width+x)*2+1]<<8
            rows+=bytes(((v>>11)*255//31,((v>>5)&63)*255//63,(v&31)*255//31))
    chunk=lambda kind,body:struct.pack('>I',len(body))+kind+body+struct.pack('>I',zlib.crc32(kind+body))
    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(bytes(rows)))+chunk(b'IEND',b''))

class Core:
    def __init__(self):
        sys.path.insert(0,str(ROOT/'tools'))
        import retail_capture as host
        self.host=host;lib=self.lib=host.lib;self.pad=0;self.frame=None
        @host.VID
        def video(data,width,height,pitch):
            if data:self.frame=(width,height,b''.join(C.string_at(data+y*pitch,width*2) for y in range(height)))
        @host.INPUT
        def pad(port,device,index,ident):
            self.polls+=1
            if port or device!=1:return 0
            bits=[(64,1),(16,0),(32,8),(128,3),(1,4),(2,5),(4,6),(8,7)] # MD A/B/C/Start/U/D/L/R on the core's 3-button map
            if ident==256:return sum(1<<r for m,r in bits if self.pad&m)
            return int(any(self.pad&m and r==ident for m,r in bits))
        self.callbacks=(video,pad);lib.retro_set_video_refresh(video);lib.retro_set_input_state(pad)
        game=host.Game(str(RETAIL/'sonic.cue').encode(),None,0,None);lib.retro_load_game.restype=C.c_bool
        if not lib.retro_load_game(C.byref(game)):raise RuntimeError('Cannot load private Sega CD reference disc')
        lib.retro_set_controller_port_device(0,1);self.polls=0
        sym=lambda name:C.addressof(C.c_uint8.in_dll(lib,name))
        self.ext=sym('ext');self.prg=self.ext+0x830088;self.word=self.prg+0xc0000;self.regs=self.word+0x42000
        self.work=sym('work_ram');self.vram=sym('vram');self.cram=sym('cram');self.vsram=sym('vsram');self.reg=sym('reg');self.zram=sym('zram')
        lib.m68k_get_reg.restype=C.c_uint;lib.s68k_get_reg.restype=C.c_uint
    @staticmethod
    def swapped(base,offset,n):
        start=offset&~1;b=C.string_at(base+start,(offset-start+n+1)&~1);s=bytearray(b);s[::2],s[1::2]=b[1::2],b[::2]
        return bytes(s[offset-start:offset-start+n])
    @staticmethod
    def swap_write(base,offset,data):
        s=bytearray(data);s[::2],s[1::2]=data[1::2],data[::2];C.memmove(base+offset,bytes(s),len(s))
    def work_read(self,address,n):return self.swapped(self.work,address&0xffff,n)
    def work_write(self,address,data):self.swap_write(self.work,address&0xffff,data)
    def ga(self,address):return C.c_uint16.from_address(self.regs+(address&0x3e)).value
    def run(self):self.frame=None;self.lib.retro_run()

class Retail:
    """Retail boot with the special stage call; frames are stepped one at a time."""
    def __init__(self,score=0,stage=1,flags=0,demo_id=0):
        """flags: specStageFlags for an IPX mode entry (bit 0 temporary, bit 1 time attack,
        bit 2 secret), 0 for the normal .SpecialStage call. demo_id: demoID as IPX.asm Demo
        leaves it (Main.asm loads Stage6Demo when it is 5)."""
        self.main,self.ss,self.sub,self.scmd=layout();self.labels,_=retail_program_labels()
        ipx=(RETAIL/'IPX___.MMD').read_bytes();origin=struct.unpack_from('>I',ipx,2)[0];code=ipx[0x100:0x1100]
        run_mmd,_=find(code,'2f0833c000a12010',origin)
        bram_at,(bram_cmd,displacement)=find(code,'303c(....)6100(....)4a006708'+'08f90000%08x'%self.main['saveDisabled'],origin)
        assert bram_cmd==self.scmd['SCMD_BURAMINIT'] and bram_at+6+(displacement-65536 if displacement&0x8000 else displacement)==run_mmd
        special_at,(stage_cmd,)=find(code,'13f9%08x00a1201313f9%08x00a1201a08b9000000a1201b70(..)6100'%(self.main['curSpecStage'],self.main['timeStones']),origin)
        assert stage_cmd==self.scmd['SCMD_SPECSTAGE']
        demo_at,_=find(code,'13fc000000a1201313fc000000a1201a08f9000000a1201b70%02x6100....4e75'%stage_cmd,origin)
        m=self.main;inject=struct.pack('>HHI',0x13fc,stage-1,m['curSpecStage'])+struct.pack('>HHI',0x13fc,0,m['timeStones'])
        inject+=struct.pack('>HHI',0x13fc,3,m['lives'])+struct.pack('>HII',0x23fc,5000,m['nextLifeScore'])+struct.pack('>HII',0x23fc,score,m['score'])
        inject+=struct.pack('>HHI',0x13fc,0,0xa1201b)+struct.pack('>HI',0x4eb9,special_at)+bytes.fromhex('60fe')
        if flags:
            # IPX.asm SpecStage1Demo/SpecStage6Demo, TimeAttack_SS and SoundTest_SpecStg8:
            # specStageIDCmd, timeStonesCmd 0, specStageFlags, then RunMMD(SCMD_SPECSTAGE).
            inject=struct.pack('>HHI',0x13fc,stage-1,0xa12013)+struct.pack('>HHI',0x13fc,0,0xa1201a)+struct.pack('>HHI',0x13fc,flags,0xa1201b)
            inject+=struct.pack('>HHI',0x13fc,demo_id,m['demoID'])+struct.pack('>HHI',0x13fc,3,m['lives'])
            inject+=struct.pack('>BB',0x70,stage_cmd)+struct.pack('>HI',0x4eb9,run_mmd)+bytes.fromhex('60fe')
        assert len(inject)<=64
        self.patch=[(bram_at,code[bram_at-origin:bram_at-origin+8],struct.pack('>HIH',0x4ef9,demo_at,0x4e71)),(demo_at,code[demo_at-origin:demo_at-origin+64],inject)]
        self.halt=demo_at+len(inject)-2;self.core=Core();self.frames=0
    def boot(self,limit=6000):
        core=self.core;patched=False
        while self.frames<limit:
            core.pad=0;core.run();self.frames+=1
            if not patched and all(core.work_read(at,len(old))==old for at,old,_ in self.patch):
                for at,_,new in self.patch:core.work_write(at,new)
                patched=True
            if patched and 0xff2000<=core.lib.m68k_get_reg(16)<0xffb000 and core.work_read(0xfffd08,4)==struct.pack('>I',self.labels['VInterrupt']):return self.frames
        raise AssertionError('retail special stage did not start')
    def vint(self):return struct.unpack('>H',self.core.work_read(self.ss['vintCounter'],2))[0]

    def snapshot(self):
        """One frame record; large buffers become CRC references into blobs."""
        c=self.core;w=c.work_read;ss=self.ss;L=self.labels;m=self.main;blobs=self.blobs
        def blob(data):
            key='%08x'%zlib.crc32(data);blobs.setdefault(key,data.hex());return key
        word=lambda a:struct.unpack('>H',w(a,2))[0];long=lambda a:struct.unpack('>I',w(a,4))[0]
        reg=C.string_at(c.reg,24);h40=bool(reg[12]&1)
        cram=[(v>>6&7)<<9|(v>>3&7)<<5|(v&7)<<1 for v in struct.unpack('<64H',C.string_at(c.cram,128))]
        width,height,pixels=c.frame or (0,0,b'')
        record={'frame':self.frames,'v':word(ss['vintCounter']),'routine':word(ss['vintRoutine']),'pc':c.lib.m68k_get_reg(16),
            'width':width,'height':height,'pixels':'%08x'%zlib.crc32(pixels),
            'pixels_split':['%08x'%zlib.crc32(pixels[:128*width*2]),'%08x'%zlib.crc32(pixels[128*width*2:224*width*2])],
            'pixels_below_hud':'%08x'%zlib.crc32(pixels[24*width*2:224*width*2]),'reg':reg.hex(),'cram':blob(struct.pack('>64H',*cram)),'vsram':C.string_at(c.vsram,4).hex(),
            'plane_a':blob(c.swapped(c.vram,(reg[2]&0x38)<<10,0x1000)),'plane_b':blob(c.swapped(c.vram,(reg[4]&7)<<13,0x1000)),
            'hscroll':blob(c.swapped(c.vram,reg[13]<<10,0x380)),'sat':blob(c.swapped(c.vram,(reg[5]&(0x7e if h40 else 0x7f))<<9,640)),
            'palette':blob(w(ss['palette'],128)),'fade':blob(w(ss['fadePalette'],128)),'bg':blob(w(ss['bgHScroll'],0x400)),'stage_scroll':blob(w(ss['stageHScroll1'],0x200)),
            'sprites':blob(w(ss['sprites'],640)),'sonic_art':'%08x'%zlib.crc32(w(ss['sonicArtBuf'],0x300)),
            'paused':w(ss['paused'],1)[0],'faded':w(ss['fadedOut'],1)[0],'results_timer':word(ss['resultsTimer']),'extra_players':word(ss['extraPlayerCnt']),
            'scroll_flags':w(ss['scrollFlags'],1)[0],'scroll_offset':[long(ss[f'scrollOffset{i}']) for i in range(1,7)],'wave':word(L['ss1BGScrollShift']+2),
            'ring_bonus':long(L['ringBonus']),'time_bonus':long(L['timeBonus']),'score_tallied':w(L['scoreTallied'],1)[0],'scroll_disable':w(L['scrollDisable'],1)[0],
            'shift':word(L['ss1BGScrollShift']),'scroll_mode':w(L['bgScrollMode'],1)[0],'stone_delay':w(L['timeStonePalDelay'],1)[0],'cycle_index':word(L['palCycleIndex']),
            'icon_frame':word(L['animFrame']),'icon_timer':word(L['animTimer']),
            'score':long(m['score']),'lives':w(m['lives'],1)[0],'next_life':long(m['nextLifeScore']),'time_stones':w(m['timeStones'],1)[0],'lost':w(m['specStageLost'],1)[0],
            'ga_flags':c.ga(0x0e),'ga_cmd2':c.ga(0x12),'ga_cmd_a':c.ga(0x1a),'ctrl':c.ga(0x1e),'ga_stat2':c.ga(0x22),'rings':c.ga(0x24),'timer':c.ga(0x26)<<16|c.ga(0x28),'ga_stat_a':c.ga(0x2a),
            'sub_globals':c.swapped(c.prg,self.sub['gfxOpFlag'],self.sub['gfxVars']-self.sub['gfxOpFlag']).hex(),
            'sub_objects':'%08x'%zlib.crc32(c.swapped(c.prg,self.sub['sonicObject'],self.sub['zBuffer']-self.sub['sonicObject'])),
            'sonic':c.swapped(c.prg,self.sub['sonicObject'],128).hex(),'fm_queue':C.string_at(c.zram+0x1c09,3).hex()}
        return record
    def record(self,route,pad,limit=16000,checkpoints=()):
        """Run until the special stage call returns to the halt loop."""
        OUT.mkdir(parents=True,exist_ok=True);self.blobs={};rows=[];halted=0;seen=set();results=False
        while self.frames<limit and halted<30:
            v=self.vint();self.core.pad=pad(v+1,results);self.core.run();self.frames+=1
            row=self.snapshot();row['pad']=self.core.pad;rows.append(row);results=results or row['routine']==5
            halted=halted+1 if row['pc']==self.halt else 0
            if row['v'] in checkpoints and row['v'] not in seen and self.core.frame:seen.add(row['v']);png(OUT/f'{route}-v{row["v"]}.png',self.core.frame)
        assert halted>=30,('special stage did not return',self.frames,hex(row['pc']))
        (OUT/f'{route}.jsonl').write_text(''.join(json.dumps(r,separators=(',',':'))+'\n' for r in rows))
        (OUT/f'{route}-blobs.json').write_text(json.dumps(self.blobs))
        return rows

def pause_then_timeout(v,results):
    """Idle run with one pause; exits by time-out and waits out the results timer."""
    return 0x80 if not results and (900<=v<906 or 960<=v<966) else 0

def win_route(stage,path=None):
    """Planned pad per Sub CPU update (tools/special_route.py) for stage n; Start skips the tally.
    Update K reads the pad from the V-INT 0/2 one half loop earlier (V-INT 25 for K=1)."""
    path=path or (OUT/'win-route.json' if stage==1 else ROOT/f'tests/routes/special/win-ss{stage}.json');cache=[]
    def pad(v,results):
        if results:return 0x80 if 40<=v<43 else 0
        if not cache:cache.append(json.loads(path.read_text())['actions'])
        actions=cache[0];index=0 if v<26 else (v-26)//3+1
        return actions[index] if index<len(actions) else 0
    return pad
win=win_route(1)

def steer(v,results):
    """Timeout route that turns left and right, so the background scrolls."""
    if results:return 0
    turn=4 if 60<=v<400 or 1200<=v<1300 or 2400<=v<2600 else 8 if 500<=v<800 or 2000<=v<2100 or 3000<=v<3400 else 0
    return pause_then_timeout(v,results)|turn

def planned(name):
    """Planned pad per Sub CPU update from build/special-retail/<name>.json (tools/special_route.py)."""
    def pad(v,results):
        if results:return 0
        if not hasattr(pad,'actions'):
            stored=ROOT/f'tests/routes/special/{name}.json' # Stored plans win over build output.
            pad.actions=json.loads((stored if stored.exists() else OUT/f'{name}.json').read_text())['actions']
        index=0 if v<26 else (v-26)//3+1
        return pad.actions[index] if index<len(pad.actions) else 0
    return pad

def idle(v,results):
    """No input: the attract demos play their own recording."""
    return 0

def steer_hazard(v,results):
    """Steering without the pause: crosses stage 8's hazards until the time runs out."""
    return steer(v,results)&0x0f

def ta_exit(v,results):
    """Time attack: steer, pause at V-INT 900, then A exits from the pause (Sub.asm .PauseLoop)."""
    return 0x80 if 900<=v<906 else 0x40 if 960<=v<966 else steer(v,results)&0x0f

# Route: pad function (V-INT counter, results screen) and starting score.
# swin (stage 8) and tawin (time attack) replay tools/special_route.py plans for that entry.
# hazard: planned stamp-type sweep (tools/special_route.py hazard n) for stages 1-7, then a
# released pad to the time-out; stage 8 (no stored sweep) steers through its hazards.
ROUTES={'timeout':(pause_then_timeout,0),'win':(win,4000),'steer':(steer,0),'demo':(idle,0),'ta':(steer,0),'taexit':(ta_exit,0),
    'swin':(planned('win-ss8'),0),'tawin':(planned('win-route-ta'),0),'idle':(idle,0),'hazard':(steer_hazard,0)}
# specStageFlags per route family (IPX.asm): demos temporary, time attack bit 1; stage 8 temporary+secret.
FLAGS={'demo':1,'ta':2,'taexit':2,'tawin':2}
def route_spec(name):
    """(pad, score, stage) for 'route' (stage 1) or 'route-ss<n>'."""
    base,_,stage=name.partition('-ss');pad,score=ROUTES[base];stage=int(stage) if stage else 1
    if base=='win':pad=win_route(stage)
    sweep=ROOT/f'tests/routes/special/hazard-ss{stage}.json'
    if base=='hazard' and sweep.exists():pad=win_route(stage,sweep)
    return pad,score,stage
def route_mode(name):
    """(specStageFlags, demoID) for a route; 0 flags is the normal .SpecialStage entry."""
    base,_,stage=name.partition('-ss');stage=int(stage) if stage else 1
    flags=5 if stage==8 else FLAGS.get(base,0)
    # IPX.asm Demo reads demoID, then advances it: SS1 is demo 2, SS6 demo 4.
    return flags,(3 if stage==1 else 5) if base=='demo' else 0

def write_pad(route,stage_vints=16000,results_vints=1000):
    """Run-length pad script for the Saturn emulator gate: '<phase> <V-INT> <pad>' lines."""
    pad,_,_=route_spec(route);lines=[]
    for phase,count in (('stage',stage_vints),('results',results_vints)):
        previous=None
        for v in range(count):
            value=pad(v,phase=='results')
            if value!=previous:lines.append(f'{phase} {v} {value}\n');previous=value
    OUT.mkdir(parents=True,exist_ok=True);(OUT/f'{route}.pad').write_text(''.join(lines))

def main():
    route=sys.argv[1] if len(sys.argv)>1 else 'timeout'
    pad,score,stage=route_spec(route);write_pad(route)
    r=Retail(score,stage,*route_mode(route));start=r.boot()
    checkpoints=tuple(map(int,sys.argv[2].split(','))) if len(sys.argv)>2 else (1,24,25,60,300,901,930,1500,3000,4500,6000)
    rows=r.record(route,pad,checkpoints=checkpoints)
    summary={'route':route,'boot_frames':start,'frames':len(rows),'last_v':rows[-1]['v'],'routines':sorted({x['routine'] for x in rows}),'blobs':len(r.blobs),
        'results_frame':next((x['frame'] for x in rows if x['routine']==5),None),'score':rows[-1]['score'],'lives':rows[-1]['lives']}
    print(json.dumps(summary))

if __name__=='__main__':main()
