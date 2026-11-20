#!/usr/bin/env python3
"""Run the retail title screen (TITLEM.MMD/TITLES.BIN) in the pinned Sega CD core with scripted input.

QA oracle only; nothing here is linked into the Saturn build. The retail disc boots
unmodified. When IPX___.MMD is in Work RAM, its Backup RAM initialization call (a fatal
loop in the core) jumps to a stub in the unused SpecStage1Demo body that runs the title
file like IPX.asm .GameLoop (moveq #SCMD_TITLE,d0; RunMMD), stores d1 and halts.

Pad convention: pad(v) is the Mega Drive pad (1 up, 2 down, 4 left, 8 right, 16 B, 32 C,
64 A, 128 Start) for the emulated frame that begins with the title's vintCounter == v. That
frame's V-INT reads the controllers (routines 0-3 and 5) and then increments vintCounter to
v+1; a lag frame (VInt_Lag) reads nothing and leaves v unchanged, so the pad repeats.
Every emulated frame after the title starts is recorded (title variables named in
Title Screen/Main.asm and Sub.asm, VDP state and the displayed picture's CRC). CRC fields and
blob keys are 8-hex-digit zlib CRC32 strings of big-endian bytes: VRAM regions as the VDP holds
them, CRAM as 64 big-endian 9-bit MD words, RAM buffers as 68000 bytes; pixels is the core's
RGB565 little-endian frame. {route}.pad holds the same pad as '<v> <md-pad>' run-length lines.
"""
import hashlib,json,re,struct,sys,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import special_retail as sr
from extract_mmd import disc_files
SRC=sr.SRC;OUT=ROOT/'build/title-retail';TITLE=SRC/'Title Screen'
OBJECTS,OSIZE=10,0x40

def usa(text):
    """REGION=USA branches of if/else/endif; RSEVEN aligns the rs counter to a word."""
    names={'REGION':1,'JAPAN':0,'USA':1,'EUROPE':2};out=[];stack=[]
    for line in text.splitlines():
        code=line.split(';',1)[0]
        if m:=re.match(r'\s+if\s+(.+)',code):
            assert 'REGION' in m[1],line
            expr=re.sub(r'(?<![!<>=])=(?!=)','==',m[1].replace('<>','!='))
            stack.append(bool(eval(expr,{'__builtins__':{}},names)));continue
        if re.match(r'\s+else\b',code):stack[-1]=not stack[-1];continue
        if re.match(r'\s+endif\b',code):stack.pop();continue
        if all(stack):out.append(re.sub(r'^\s+RSEVEN\b','\trs.b\t__rs&1',line))
    assert not stack
    return '\n'.join(out)

def layout():
    common=(TITLE/'_Common.inc').read_text()
    symbols,names=sr.rs_symbols(usa(common+'\n'+(TITLE/'Main.asm').read_text().split('; MMD header',1)[0]),{'WORKRAM':0xff0000},0xffffff)
    main=names|symbols
    sub_text=(TITLE/'Sub.asm').read_text()
    gfx,_=sr.rs_symbols(sub_text.split('; Graphics operation variable structure',1)[1].split('; Variables',1)[0],{})
    sub,_=sr.rs_symbols(sub_text.split('; Variables',1)[1].split('; Program start',1)[0],{'PRGRAM':0,'gfxSize':gfx['gfxSize']})
    assert main['VARSSTART']==0xffa000 and main['oSize']==OSIZE and (main['objectsEnd']-main['objects'])//OSIZE==OBJECTS
    return main,sub,gfx

def verify(main,sub,gfx):
    """Locate title labels in the retail programs through the code that uses them."""
    disc=disc_files((sr.RETAIL/'sonic.iso').read_bytes());m=disc['TITLEM.MMD'];s=disc['TITLES.BIN']
    _,origin,_,entry=struct.unpack_from('>BxIHI',m,0);code=m[0x100:];short=lambda a:a&0xffff
    assert origin==entry==0xff2000
    labels={'origin':origin,'titlem_sha256':hashlib.sha256(m).hexdigest(),'titles_sha256':hashlib.sha256(s).hexdigest()}
    _,(labels['VInterrupt'],lag)=sr.find(code,'21fc(........)fd0821fcffffffff(....)',origin)
    _,(cycle,)=sr.find(code,'06380040(....)65024e75',origin)
    _,(timer,)=sr.find(code,'31fc03fc(....)',origin)
    _,(timer2,timer3,vint)=sr.find(code,'4a78(....)67045378(....)5278(....)',origin)
    _,(image,)=sr.find(code,'43f9....d00045f8(....)3e3c',origin)
    _,(mode,)=sr.find(code,'11fc0002(....)',origin)
    _,(exit_flag,)=sr.find(code,'4a38(....)66..',origin,2)
    checks={'lagCounter':lag,'palCycleDelay':cycle,'timer':timer,'vintCounter':vint,'cloudsImage':image,'titleMode':mode,'exitFlag':exit_flag}
    for name,value in checks.items():assert value==short(main[name]),(name,hex(value),hex(main[name]))
    assert timer2==timer3==timer
    _,(gfx_vars,)=sr.find(s,'43f9(........)337c0480%04x337c0480%04x337c0140%04x'%(gfx['gfxCamX'],gfx['gfxCamY'],gfx['gfxCamZ']),0x10000)
    assert gfx_vars==sub['gfxVars'],(hex(gfx_vars),hex(sub['gfxVars']))
    data={}
    for p in sorted(TITLE.rglob('*')):
        if p.suffix not in ('.nem','.kos') or 'Secrets' in p.parts:continue
        blob=p.read_bytes();target=s if p.suffix=='.kos' else m
        assert target.count(blob)==1,(p,target.count(blob))
        data[str(p.relative_to(SRC))]=target.index(blob)
    labels.update({k:short(v) for k,v in checks.items()},gfxVars=gfx_vars,data_offsets=data,
        variables={k:v for k,v in main.items() if v>=0xffa000},sub_variables=sub,gfx=gfx)
    return labels

class Title:
    def __init__(self):
        self.main,self.sub,self.gfx=layout();self.labels=verify(self.main,self.sub,self.gfx)
        _,_,_,self.scmd=sr.layout()
        ipx=(sr.RETAIL/'IPX___.MMD').read_bytes();origin=struct.unpack_from('>I',ipx,2)[0];code=ipx[0x100:0x1100]
        run_mmd,_=sr.find(code,'2f0833c000a12010',origin)
        bram_at,(bram_cmd,displacement)=sr.find(code,'303c(....)6100(....)4a006708'+'08f90000%08x'%sr.layout()[0]['saveDisabled'],origin)
        assert bram_cmd==self.scmd['SCMD_BURAMINIT'] and bram_at+6+(displacement-65536 if displacement&0x8000 else displacement)==run_mmd
        title_at,(title_cmd,displacement)=sr.find(code,'70(..)6100(....)4881',origin)
        assert title_cmd==self.scmd['SCMD_TITLE'] and title_at+4+(displacement-65536 if displacement&0x8000 else displacement)==run_mmd
        demo_at,_=sr.find(code,'13fc000000a1201313fc000000a1201a08f9000000a1201b70..6100....4e75',origin)
        self.exit_at=demo_at+16
        stub=struct.pack('>BBHIHIH',0x70,title_cmd,0x4eb9,run_mmd,0x13c1,self.exit_at,0x60fe)+b'\xee\x00'
        self.patch=[(bram_at,code[bram_at-origin:bram_at-origin+8],struct.pack('>HIH',0x4ef9,demo_at,0x4e71)),(demo_at,code[demo_at-origin:demo_at-origin+len(stub)],stub)]
        self.halt=demo_at+14;self.core=sr.Core();self.frames=0
        self.labels.update(run_mmd=run_mmd,title_call=title_at,stub=demo_at,halt=self.halt)
    def title_running(self):return self.core.work_read(0xfffd08,4)==struct.pack('>I',self.labels['VInterrupt'])
    def boot(self,limit=6000):
        core=self.core;patched=False
        while self.frames<limit:
            core.pad=0;core.run();self.frames+=1
            if not patched and all(core.work_read(at,len(old))==old for at,old,_ in self.patch):
                for at,_,new in self.patch:core.work_write(at,new)
                patched=True
            if patched and self.title_running():return self.frames
        raise AssertionError('retail title screen did not start')
    def word(self,name):return struct.unpack('>H',self.core.work_read(self.main[name],2))[0]
    def byte(self,name):return self.core.work_read(self.main[name],1)[0]
    def snapshot(self):
        c=self.core;w=c.work_read;m=self.main;blobs=self.blobs;crc=lambda d:'%08x'%zlib.crc32(d)
        def blob(data):
            key=crc(data);blobs.setdefault(key,data.hex());return key
        reg=sr.C.string_at(c.reg,24)
        cram=[(v>>6&7)<<9|(v>>3&7)<<5|(v&7)<<1 for v in struct.unpack('<64H',sr.C.string_at(c.cram,128))]
        width,height,pixels=c.frame or (0,0,b'')
        gfx=lambda name:struct.unpack('>H',c.swapped(c.prg,self.sub['gfxVars']+self.gfx[name],2))[0]
        return {'frame':self.frames,'title':self.title_running(),'v':self.word('vintCounter'),'routine':self.word('vintRoutine'),'mode':self.byte('titleMode'),
            'lag':struct.unpack('>I',w(m['lagCounter'],4))[0],'timer':self.word('timer'),'exit':self.byte('exitFlag'),'menu_sel':self.byte('menuSel'),
            'menu_options':w(m['menuOptions'],8).hex(),'cycle':[self.byte('palCycleFrame'),self.byte('palCycleDelay')],'ctrl':list(w(m['p1CtrlData'],2)),
            'enable_display':self.byte('enableDisplay'),'objects':blob(w(m['objects'],OBJECTS*OSIZE)),'palette':blob(w(m['palette'],128)),'fade':blob(w(m['fadePalette'],128)),
            'hscroll_buf':blob(w(m['hscroll'],0x380)),'sprites_buf':blob(w(m['sprites'],640)),'clouds_image':crc(w(m['cloudsImage'],m['IMGLENGTH'])),
            'gfx':[gfx(n) for n in ('gfxCamX','gfxCamY','gfxCamZ','gfxPitch','gfxYaw')],
            'reg':reg.hex(),'cram':blob(struct.pack('>64H',*cram)),'vsram':sr.C.string_at(c.vsram,4).hex(),
            'plane_a':blob(c.swapped(c.vram,0xc000,0x1000)),'plane_b':blob(c.swapped(c.vram,0xe000,0x1000)),'hscroll':blob(c.swapped(c.vram,0xd000,0x380)),
            'sat':blob(c.swapped(c.vram,0xd400,0x280)),'tiles':crc(c.swapped(c.vram,0,0xc000)),'cloud_tiles':crc(c.swapped(c.vram,0x20,0x6000)),
            'width':width,'height':height,'pixels':crc(pixels),'pc':c.lib.m68k_get_reg(16)}
    def record(self,route,pad,checkpoints,limit=4000):
        import zipfile
        OUT.mkdir(parents=True,exist_ok=True);self.blobs={};rows=[];halted=0;seen=set();start=self.frames
        pictures=zipfile.ZipFile(OUT/f'{route}-pixels.zip','w',zipfile.ZIP_DEFLATED);picture_keys=set()
        while self.frames-start<limit and halted<30:
            v=self.word('vintCounter');self.core.pad=pad(v);self.core.run();self.frames+=1
            row=self.snapshot();row['pad']=self.core.pad;rows.append(row)
            if row['title'] and self.core.frame and row['pixels'] not in picture_keys:
                pictures.writestr(row['pixels'],self.core.frame[2]);picture_keys.add(row['pixels'])
            halted=halted+1 if row['pc']==self.halt else 0
            if row['title'] and row['v'] in checkpoints and row['v'] not in seen and self.core.frame:
                seen.add(row['v']);sr.png(OUT/f'{route}-v{row["v"]}.png',self.core.frame);(OUT/f'{route}-v{row["v"]}.bin').write_bytes(self.core.frame[2])
        pictures.close()
        assert halted>=30,('title did not return',self.frames,hex(row['pc']))
        (OUT/f'{route}.jsonl').write_text(''.join(json.dumps(r,separators=(',',':'))+'\n' for r in rows))
        (OUT/f'{route}-blobs.json').write_text(json.dumps(self.blobs))
        return rows

def newgame(v):return 128 if 700<=v<704 else 64 if 800<=v<804 else 0
def timeout(v):return 0
def stafftimes(v):
    """ObjMenu_BestTimesCheat, on press-start without opening the menu."""
    for at,pad in ((700,8),(708,8),(716,1),(724,1),(732,2),(740,32)):
        if at<=v<at+4:return pad
    return 0
ROUTES={'newgame':newgame,'timeout':timeout,'stafftimes':stafftimes}

def write_pad(route,vints=4000):
    """Run-length pad script for replay by title vintCounter: '<v> <md-pad>' lines, each value
    applying from that v until the next line (first line at v 0)."""
    pad=ROUTES[route];lines=[];previous=None
    for v in range(vints):
        if pad(v)!=previous:lines.append(f'{v} {pad(v)}\n');previous=pad(v)
    OUT.mkdir(parents=True,exist_ok=True);(OUT/f'{route}.pad').write_text(''.join(lines))
# Retail timeline (both routes): Sonic palette fade from black V-INTs 51-72, Sonic turning 73-79,
# white flash 80-101, menu mode from 102 (Start at 700 in newgame, exit fade 804-823; the
# timeout route's press-start timer expires near 1122, fade to 1145).
CHECKPOINTS=(1,50,55,60,66,72,74,76,78,80,85,90,95,101,102,110,120,140,160,200,201,202,203,300,301,302,303,696,698,700,701,702,703,704,706,708,712,716,720,730,740,760,799,800,801,802,803,804,806,810,816,820,823,1100,1120,1124,1130,1136,1140,1145)

def main():
    routes=sys.argv[1:2] or list(ROUTES)
    checkpoints=tuple(map(int,sys.argv[2].split(','))) if len(sys.argv)>2 else CHECKPOINTS
    summaries=[]
    for route in routes:
        write_pad(route);t=Title();boot=t.boot();rows=t.record(route,ROUTES[route],set(checkpoints))
        OUT.mkdir(parents=True,exist_ok=True);(OUT/'labels.json').write_text(json.dumps(t.labels,indent=2)+'\n')
        title=[r for r in rows if r['title']];last=title[-1];exit_code=last['exit'] if last['exit']<0x80 else 0
        stub_exit=t.core.work_read(t.exit_at,1)[0]
        lags=sum(1 for a,b in zip(title,title[1:]) if b['v']==a['v'])
        order={}
        for r in title:
            if r['mode']==2:order.setdefault(r['v']%4,set()).add(r['routine'])
        if route=='newgame':
            menu=next(r for r in title if r['v']==800);slot=bytes.fromhex(t.blobs[menu['objects']])[4*OSIZE:5*OSIZE]
            assert slot[t.main['oVars']+5]==3,('menu not selectable at V-INT 800',slot.hex())
            assert exit_code==1 and next(r for r in title if r['v']==700)['mode']==2
        elif route=='stafftimes':
            assert exit_code==9 and stub_exit==9 and last['v']<900
            assert next(r for r in title if r['v']==700)['mode']==2
        else:assert exit_code==0 and last['exit']==0xff
        summaries.append({'route':route,'boot_frames':boot,'frames':len(rows),'title_frames':len(title),'last_v':last['v'],
            'first_v_mode1':next((r['v'] for r in title if r['mode']&0x7f==1),None),'first_v_mode2':next((r['v'] for r in title if r['mode']==2),None),
            'exit':exit_code,'exit_flag':last['exit'],'stub_d1':stub_exit,'repeated_v_frames':lags,'lag_counter':last['lag'],
            'routines_by_v_mod4':{k:sorted(v) for k,v in sorted(order.items())},'frame_size':[last['width'],last['height']],'blobs':len(t.blobs)})
    print(json.dumps(summaries))

if __name__=='__main__':main()
