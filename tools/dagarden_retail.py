#!/usr/bin/env python3
"""Run the retail D.A. Garden (PLANET_M.MMD, PLANET_S.BIN, PLANET_D.BIN) in the pinned Sega CD core.

QA oracle only; nothing here is linked into the Saturn build. The retail disc boots
unmodified. When IPX___.MMD is in Work RAM, its Backup RAM initialization call (a fatal
loop in the core) jumps to a stub in the unused SpecStage1Demo body that runs D.A. Garden
like IPX.asm DAGarden (move.w #SCMD_DAGARDEN,d0; RunMMD), stores d1 and halts.

Pad convention (as tools/title_retail.py): pad(v) is the Mega Drive pad (1 up, 2 down,
4 left, 8 right, 16 B, 32 C, 64 A, 128 Start) for the emulated frame that begins with
vintCounter == v. Every emulated frame after the program starts is recorded: variables
named in DA Garden/Main.asm and Sub.asm, VDP state and the displayed picture's CRC.
CRC fields are 8-hex-digit zlib CRC32 strings of big-endian bytes.
"""
import hashlib,json,os,struct,sys,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import special_retail as sr
from extract_mmd import disc_files
SRC=sr.SRC;DAG=SRC/'DA Garden'
# The port plays the Japanese soundtrack, so the oracle runs D.A. Garden with the Japanese
# disc's PLANET_M.MMD and PLANET_D.BIN (track titles and offsets for that soundtrack) on the
# US retail boot: SCD_DAGARDEN_REGION=us keeps the unmodified US files.
REGION=os.environ.get('SCD_DAGARDEN_REGION','jp')
OUT=ROOT/('build/dagarden-retail' if REGION=='us' else 'build/dagarden-retail-jp')

def japanese_planet():
    """PLANET_* files of the user's Japanese disc (assets/private/sonic-cd-japan.cue, JAPANESE-MUSIC.md)."""
    import prepare_japanese_music as pj
    tracks=pj.read_tracks(ROOT/'assets/private/sonic-cd-japan.cue');raw=pj.read_track(tracks[1])
    iso=b''.join(raw[i+16:i+2064] for i in range(0,len(raw),2352))
    assert iso.startswith(b'SEGADISCSYSTEM') and iso[0x1f0:0x200].strip()==b'J','not the Japanese Sega CD disc'
    files=disc_files(iso)
    return {k:files[k] for k in ('PLANET_M.MMD','PLANET_S.BIN','PLANET_D.BIN')}
OBJECTS,OSIZE=16,0x40
IMGLENGTH=32*22*32

def layout():
    common=(DAG/'_Common.inc').read_text()
    main,names=sr.rs_symbols(common+'\n'+(DAG/'Main.asm').read_text().split('; MMD header',1)[0],{'WORKRAM':0xff0000},0xffffff)
    sub_text=(DAG/'Sub.asm').read_text().split('; Program start',1)[0]
    sub,_=sr.rs_symbols(common+'\n'+sub_text,{'PRGRAM':0},0xffffff)
    assert main['VARSSTART']==0xff9000 and main['oSize']==OSIZE and (main['trackSelData']-main['objects'])==OBJECTS*OSIZE+0x40,hex(main['VARSSTART'])
    return main,sub

def verify(main,sub):
    """Locate D.A. Garden labels in the retail programs through the code that uses them."""
    disc=disc_files((sr.RETAIL/'sonic.iso').read_bytes());m=disc['PLANET_M.MMD'];s=disc['PLANET_S.BIN']
    _,origin,_,entry=struct.unpack_from('>BxIHI',m,0);code=m[0x100:];short=lambda a:a&0xffff
    labels={'origin':origin,'entry':entry,'planet_m_sha256':hashlib.sha256(m).hexdigest(),'planet_s_sha256':hashlib.sha256(s).hexdigest(),
        'planet_d_sha256':hashlib.sha256(disc['PLANET_D.BIN']).hexdigest()}
    _,(labels['VInterrupt'],)=sr.find(code,'21fc(........)fd08',origin)
    _,(timer,timer2,vint)=sr.find(code,'4a78(....)67045378(....)5278(....)',origin)
    assert timer==timer2==short(main['timer']) and vint==short(main['vintCounter'])
    _,(lag,routine)=sr.find(code,'52b8(....)11f8(....)',origin)
    assert lag==short(main['lagCounter']) and routine==short(main['vintRoutine'])+1
    _,(seed,)=sr.find(code,'2f012238(....)6606223c2a6d365a',origin)
    assert seed==short(main['rngSeed'])
    # Sub CPU: GACOMCMD2 loop, then bsr ObjPlanet; RunGfxOperation copies planetObj into gfxParams.
    _,(params,angle)=sr.find(s,'4df9(........)3d79(........)0006',0x10000)
    assert params==sub['gfxParams'] and angle==sub['planetObj']+sub['oAngle'],(hex(params),hex(sub['gfxParams']),hex(angle))
    labels.update(variables={k:v for k,v in main.items() if v>=0xff9000},sub_variables={k:v for k,v in sub.items() if 0x1c000<=v<0x20000})
    return labels

class Garden:
    def __init__(self):
        self.main,self.sub=layout();self.labels=verify(self.main,self.sub)
        _,_,_,scmd=sr.layout()
        ipx=(sr.RETAIL/'IPX___.MMD').read_bytes();origin=struct.unpack_from('>I',ipx,2)[0];code=ipx[0x100:0x1100]
        run_mmd,_=sr.find(code,'2f0833c000a12010',origin)
        bram_at,(bram_cmd,displacement)=sr.find(code,'303c(....)6100(....)4a006708'+'08f90000%08x'%sr.layout()[0]['saveDisabled'],origin)
        assert bram_cmd==scmd['SCMD_BURAMINIT'] and bram_at+6+(displacement-65536 if displacement&0x8000 else displacement)==run_mmd
        dag_cmd=scmd['SCMD_DAGARDEN']
        demo_at,_=sr.find(code,'13fc000000a1201313fc000000a1201a08f9000000a1201b70..6100....4e75',origin)
        # move.w #SCMD_DAGARDEN,d0; jsr RunMMD; move.b d1,exit; bra.s *; exit byte.
        self.exit_at=demo_at+18
        stub=struct.pack('>HHHIHIH',0x303c,dag_cmd,0x4eb9,run_mmd,0x13c1,self.exit_at,0x60fe)+b'\xee\x00'
        self.patch=[(bram_at,code[bram_at-origin:bram_at-origin+8],struct.pack('>HIH',0x4ef9,demo_at,0x4e71)),(demo_at,code[demo_at-origin:demo_at-origin+len(stub)],stub)]
        self.halt=demo_at+16;self.core=sr.Core();self.frames=0
        self.labels.update(run_mmd=run_mmd,stub=demo_at,halt=self.halt,scmd=dag_cmd)
    def running(self):return self.core.work_read(0xfffd08,4)==struct.pack('>I',self.labels['VInterrupt'])
    def boot(self,limit=8000):
        core=self.core;patched=False
        while self.frames<limit:
            core.pad=0;core.run();self.frames+=1
            if not patched and all(core.work_read(at,len(old))==old for at,old,_ in self.patch):
                for at,_,new in self.patch:core.work_write(at,new)
                patched=True
            if patched and self.running():
                if REGION!='us':self.load_japanese()
                return self.frames
        raise AssertionError('retail D.A. Garden did not start')
    def load_japanese(self):
        """Japanese program image and track title art over the US ones as the program starts. The
        code is the same (only REGION data differ: track title mappings, TrackInfo, the opening and
        ending title art); the data after the mappings move, so the whole image is replaced."""
        jp=japanese_planet();c=self.core
        _,origin,_,_=struct.unpack_from('>BxIHI',jp['PLANET_M.MMD'],0)
        assert origin==self.labels['origin'] and jp['PLANET_S.BIN']==disc_files((sr.RETAIL/'sonic.iso').read_bytes())['PLANET_S.BIN']
        body=jp['PLANET_M.MMD'][0x100:];assert origin+len(body)<=0xff9000
        c.work_write(origin,body if len(body)%2==0 else body+b'\0')
        d=jp['PLANET_D.BIN'];c.swap_write(c.word,0x12c00,d if len(d)%2==0 else d+b'\0')
        self.labels.update(region='jp',planet_m_jp_sha256=hashlib.sha256(jp['PLANET_M.MMD']).hexdigest(),planet_d_jp_sha256=hashlib.sha256(d).hexdigest())
    def word(self,name):return struct.unpack('>H',self.core.work_read(self.main[name],2))[0]
    def byte(self,name):return self.core.work_read(self.main[name],1)[0]
    def sub_read(self,name,n):return self.core.swapped(self.core.prg,self.sub[name],n)
    def snapshot(self):
        c=self.core;w=c.work_read;m=self.main;blobs=self.blobs;crc=lambda d:'%08x'%zlib.crc32(d)
        def blob(data):
            key=crc(data);blobs.setdefault(key,data.hex());return key
        reg=sr.C.string_at(c.reg,24)
        cram=[(v>>6&7)<<9|(v>>3&7)<<5|(v&7)<<1 for v in struct.unpack('<64H',sr.C.string_at(c.cram,128))]
        width,height,pixels=c.frame or (0,0,b'')
        word=lambda a:struct.unpack('>H',w(a,2))[0];long=lambda a:struct.unpack('>I',w(a,4))[0]
        planet=self.sub_read('planetObj',0x22)
        return {'frame':self.frames,'run':self.running(),'v':self.word('vintCounter'),'routine':self.word('vintRoutine'),
            'lag':long(m['lagCounter']),'timer':self.word('timer'),'buf_count':self.word('bufRenderCnt'),
            'cycle':[self.word('palCycleTimer'),self.word('palCycleIndex')],'volcano':[self.word('volcanoTimer'),self.word('volcanoIndex')],
            'spr_cycle':[self.word('sprPalCycTimer'),self.word('sprPalCycIndex')],'sel_flags':self.byte('trackSelFlags'),
            'sel':w(m['trackSelData'],8).hex(),'spawn_timers':w(m['objSpawnTimers'],12).hex(),'spawn':[self.byte('objSpawnFlags'),self.byte('objSpawnID')],
            'buttons':self.byte('buttonFlags'),'seed':'%08x'%long(m['rngSeed']),'zone':self.word('trackTimeZone'),'no_cycle':self.byte('disablePalCycle'),
            'ctrl':[c.ga(0x1e)>>8&255,c.ga(0x1e)&255],
            'ga_flags':c.ga(0x0e),'ga_cmd':[c.ga(0x12),c.ga(0x18),c.ga(0x1a)],'ga_stat2':c.ga(0x22),'memmode':c.ga(0x02),
            'objects':blob(w(m['objects'],OBJECTS*OSIZE)),'palette':blob(w(m['palette'],128)),'fade':blob(w(m['fadePalette'],128)),
            'sprites_buf':blob(w(m['sprites'],640)),'planet_image':crc(w(m['planetImage'],IMGLENGTH)),
            'image':crc(c.swapped(c.word,0x1a000,IMGLENGTH)),'trace':crc(c.swapped(c.word,0x19a00,176*8)),
            'stamp_map':blob(b''.join(c.swapped(c.word,0x20000+r*0x100,16) for r in range(7))),
            'stamps':crc(c.swapped(c.word,0,0x12c00)),
            'planet':planet.hex(),'sub':[self.sub_read('gfxOpFlag',1)[0],struct.unpack('>h',self.sub_read('scaleDirection',2))[0],
                struct.unpack('>h',self.sub_read('angleDirection',2))[0],'%08x'%struct.unpack('>I',self.sub_read('angleSpeed',4))[0],self.sub_read('planetFlags',1)[0]],
            'reg':reg.hex(),'cram':blob(struct.pack('>64H',*cram)),'vsram':sr.C.string_at(c.vsram,4).hex(),
            'plane_a':blob(c.swapped(c.vram,0xc000,0x1000)),'plane_b':blob(c.swapped(c.vram,0xe000,0x1000)),'hscroll':c.swapped(c.vram,0xd000,4).hex(),
            'sat':blob(c.swapped(c.vram,0xec00,0x280)),'tiles':crc(c.swapped(c.vram,0,0xc000)),
            'buffer1':crc(c.swapped(c.vram,0,IMGLENGTH)),'buffer2':crc(c.swapped(c.vram,IMGLENGTH,IMGLENGTH)),'object_tiles':crc(c.swapped(c.vram,0xb000,0x1000)),
            'width':width,'height':height,'pixels':crc(pixels),'pc':c.lib.m68k_get_reg(16)}
    def record(self,route,pad,checkpoints,limit=12000):
        import zipfile
        OUT.mkdir(parents=True,exist_ok=True);self.blobs={};rows=[];halted=0;seen=set();start=self.frames
        pictures=zipfile.ZipFile(OUT/f'{route}-pixels.zip','w',zipfile.ZIP_DEFLATED);picture_keys=set()
        while self.frames-start<limit and halted<30:
            v=self.word('vintCounter');self.core.pad=pad(v);self.core.run();self.frames+=1
            row=self.snapshot();row['pad']=self.core.pad;rows.append(row)
            if row['run'] and self.core.frame and row['pixels'] not in picture_keys:
                pictures.writestr(row['pixels'],self.core.frame[2]);picture_keys.add(row['pixels'])
            halted=halted+1 if row['pc']==self.halt else 0
            if row['run'] and row['v'] in checkpoints and row['v'] not in seen and self.core.frame:
                seen.add(row['v']);sr.png(OUT/f'{route}-v{row["v"]}.png',self.core.frame)
        pictures.close()
        assert halted>=30,('D.A. Garden did not return',self.frames,hex(row['pc']))
        (OUT/f'{route}.jsonl').write_text(''.join(json.dumps(r,separators=(',',':'))+'\n' for r in rows))
        (OUT/f'{route}-blobs.json').write_text(json.dumps(self.blobs))
        return rows

UP,DOWN,LEFT,RIGHT,B,C,A,START=1,2,4,8,16,32,64,128
def span(v,ranges):
    for lo,hi,value in ranges:
        if lo<=v<hi:return value
    return 0
# idle: the planet, palette cycle and spawned objects with no input; Start exits.
def idle(v):return span(v,[(2400,2404,START)])
# controls: B accelerates the rotation, C zooms, the pad moves the planet; then Start.
def controls(v):return span(v,[(200,260,B),(300,340,C),(360,420,LEFT),(430,470,UP),(480,520,RIGHT|DOWN),(560,600,C),(640,700,B),(900,904,START)])
# tracks: A opens the track selection (title flies in), Right/Left step tracks, C plays the
# track shown (Good Future: the planet art changes), later B plays a Bad Future track.
def tracks(v):return span(v,[(120,124,A),(220,224,RIGHT),(300,304,C),(700,704,A),(800,804,RIGHT),(880,884,RIGHT),(960,964,B),(1500,1504,A),(1600,1604,LEFT),(1680,1684,C),(2200,2204,START)])
# zones: plays a Good Future track (PPZ 'G' mix: the good future planet), then a Bad Future one
# (PPZ 'B' mix), moving and zooming the planet in between; Start exits.
def zones(v):return span(v,[(120,124,A),(400,404,LEFT),(600,604,C),(900,1000,B|LEFT),(1100,1160,C),(1300,1304,A),(1600,1604,LEFT),(1800,1804,B),(2100,2180,C|UP),(2600,2604,START)])
# refreshexit: Start pressed while the screen refreshes after a track change.
def refreshexit(v):return span(v,[(120,124,A),(300,304,C),(320,340,START)])
# long: the planet idles through a day and night cycle (stars at night), with Eggman and the others.
def long(v):return span(v,[(3000,3100,B),(5000,5040,C),(7400,7404,START)])
ROUTES={'idle':idle,'controls':controls,'tracks':tracks,'zones':zones,'refreshexit':refreshexit,'long':long}
ROUTE_VINTS={'idle':2600,'controls':1100,'tracks':2400,'zones':2800,'refreshexit':600,'long':7600}

def write_pad(route):
    pad=ROUTES[route];lines=[];previous=None
    for v in range(ROUTE_VINTS[route]):
        if pad(v)!=previous:lines.append(f'{v} {pad(v)}\n');previous=pad(v)
    OUT.mkdir(parents=True,exist_ok=True);(OUT/f'{route}.pad').write_text(''.join(lines))

CHECKPOINTS=(2,10,20,30,40,60,100,200,300,400,500,600,700,800,900,1000,1200,1400,1600,1800,2000,2200,2400)

def main():
    routes=sys.argv[1:2] or list(ROUTES)
    checkpoints=tuple(map(int,sys.argv[2].split(','))) if len(sys.argv)>2 else CHECKPOINTS
    summaries=[]
    for route in routes:
        write_pad(route);g=Garden();boot=g.boot();rows=g.record(route,ROUTES[route],set(checkpoints),limit=ROUTE_VINTS[route]*3)
        (OUT/'labels.json').write_text(json.dumps(g.labels,indent=2)+'\n')
        run=[r for r in rows if r['run']];last=run[-1]
        lags=sum(1 for a,b in zip(run,run[1:]) if b['v']==a['v'])
        summaries.append({'route':route,'boot_frames':boot,'frames':len(rows),'run_frames':len(run),'last_v':last['v'],
            'stub_d1':g.core.work_read(g.exit_at,1)[0],'repeated_v_frames':lags,'lag_counter':last['lag'],'frame_size':[last['width'],last['height']],'blobs':len(g.blobs)})
    print(json.dumps(summaries))

if __name__=='__main__':main()
