#!/usr/bin/env python3
"""Extract privately supplied retail music and render original drivers offline."""
import array,hashlib,json,os,re,struct,subprocess,sys
from pathlib import Path
from qa_limits import worker_limit
from native import IS_BROWSER, runtime_inputs
ROOT=Path(__file__).resolve().parents[1]
assert Path.cwd()==ROOT
OUT=ROOT/'assets/generated';WORK=ROOT/'build/retail';WORK.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(args):subprocess.run(list(map(str,args)),check=True)
def checked_core_sha(path,expected=None):
    if expected is not None and (type(expected) is not str or re.fullmatch('[0-9a-f]{64}',expected) is None):
        raise ValueError('SCD_PREPARE_AUDIO_CORE_SHA256 must be a lowercase SHA-256')
    if not path.is_file():
        if expected is not None:raise ValueError('Pinned Genesis Plus GX Core is missing')
        return None
    actual=sha(path)
    if expected is not None and actual!=expected:raise ValueError('Pinned Genesis Plus GX Core hash differs')
    return actual
core=ROOT/'.deps/genesis-plus-gx'
core_file=ROOT/'browser/genesis.wasm' if IS_BROWSER else core/'genesis_plus_gx_libretro.dylib'
expected_core=os.environ.get('SCD_BROWSER_CORE_SHA256' if IS_BROWSER else 'SCD_PREPARE_AUDIO_CORE_SHA256')
core_sha=checked_core_sha(core_file,expected_core)
actual=subprocess.check_output(['git','-C',core,'rev-parse','HEAD'],text=True).strip()
assert actual==json.loads((ROOT/'sources.lock.json').read_text())['genesis-plus-gx']['commit']
inputs=[WORK/'sonic.bin' if IS_BROWSER else ROOT/'assets/private/sonic-cd.chd',ROOT/'assets/private/bios_CD_U.bin',ROOT/'sources.lock.json']+[Path(__file__),ROOT/'tools/capture_retail_audio.py',ROOT/'tools/retail_capture.py']
inputs+=runtime_inputs(ROOT,audio=True)
for p in inputs:
    if not p.exists():raise SystemExit(f'Missing private audio input: {p}')
fingerprint={str(p.relative_to(ROOT)):sha(p) for p in inputs}
if core_sha is not None:fingerprint[str(core_file.relative_to(ROOT))]=core_sha
report_path=ROOT/'build/feedback-source.json'
if core_sha is not None and report_path.exists():
    old=json.loads(report_path.read_text())
    if old.get('inputs')==fingerprint and all((ROOT/p).exists() and sha(ROOT/p)==digest for p,digest in old.get('outputs',{}).items()) and old.get('outputs'):
        print('Retail audio cache verified');sys.exit(0)
if expected_core is None:
    with (ROOT/'build/genesis-build.log').open('w') as log:
        subprocess.run(['make','-C',core,'-f','Makefile.libretro','platform=osx',f'-j{worker_limit(8)}'],stdout=log,stderr=log,check=True)
    core_sha=checked_core_sha(core_file)
    if core_sha is None:raise ValueError('Genesis Plus GX build did not produce its Core')
    fingerprint[str(core_file.relative_to(ROOT))]=core_sha
# Extraction is cached against the complete CHD hash, never just a filename.
stamp=WORK/'chd.sha256'
if not IS_BROWSER and (not stamp.exists() or stamp.read_text()!=sha(inputs[0]) or not (WORK/'sonic.bin').exists()):
    for name in ['sonic.cue','sonic.bin']:(WORK/name).unlink(missing_ok=True)
    run(['chdman','extractcd','-i',inputs[0],'-o',WORK/'sonic.cue','-ob',WORK/'sonic.bin'])
    stamp.write_text(sha(inputs[0]))
cue=(WORK/'sonic.cue').read_text();tracks={};current=0
for line in cue.splitlines():
    if m:=re.search(r'TRACK (\d+)',line):current=int(m[1]);tracks[current]={}
    if m:=re.search(r'INDEX (\d+) (\d+):(\d+):(\d+)',line):tracks[current][int(m[1])]=(int(m[2])*60+int(m[3]))*75+int(m[4])
with (WORK/'sonic.bin').open('rb') as f:
    data=f.read(tracks[2].get(0,tracks[2][1])*2352)
iso=b''.join(data[i+16:i+2064] for i in range(0,len(data),2352))
# Unique retail Z80 driver signature; fail rather than extract an arbitrary match.
sig=bytes.fromhex('f3f3ed5618');assert iso.count(sig)==1
fm=iso.index(sig);(WORK/'fm-driver.bin').write_bytes(iso[fm:fm+8192])
def files(lba,size):
    data=iso[lba*2048:lba*2048+size];i=0
    while i<len(data):
        n=data[i]
        if not n:i=(i//2048+1)*2048;continue
        r=data[i:i+n];i+=n;name=r[33:33+r[32]]
        if name in (b'\0',b'\1'):continue
        start,length=struct.unpack_from('<I',r,2)[0],struct.unpack_from('<I',r,10)[0]
        if r[25]&2:yield from files(start,length)
        else:yield name,start,length
r=iso[16*2048+156:];entries=list(files(struct.unpack_from('<I',r,2)[0],struct.unpack_from('<I',r,10)[0]))
_,start,length=next(v for v in entries if v[0]==b'SNCBNK1B.BIN;1')
(WORK/'past-driver.bin').write_bytes(iso[start*2048:start*2048+length])
run([sys.executable,'tools/capture_retail_audio.py','fm'])
run([sys.executable,'tools/capture_retail_audio.py','past'])
run([sys.executable,'tools/capture_retail_audio.py','voices'])
# Original Collision Chaos PCM Bumper (PCMS_BUMPER=$BA), sub_sync(127).
_,start,length=next(v for v in entries if v[0]==b'SNCBNK3B.BIN;1')
(WORK/'cc-driver.bin').write_bytes(iso[start*2048:start*2048+length])
run([sys.executable,'tools/capture_retail_audio.py','effect',WORK/'cc-driver.bin',WORK/'fx127','186'])
# LOADER2.C sub_sync 118-128 play WaveRequest(ReqNo-43), PCMS $66+wave in SNCBNK3B:
# 125 (Metal Sonic, $B8); sub_sync(146) is WaveRequest(85), $BB (PLAYSP3.C bumper
# break), native request 1146 because FM effect 146 is the jump.
run([sys.executable,'tools/capture_retail_audio.py','effect',WORK/'cc-driver.bin',WORK/'fx125','184'])
run([sys.executable,'tools/capture_retail_audio.py','effect',WORK/'cc-driver.bin',WORK/'fx1146','187'])
# sub_sync(121), PLAYER.C bye_chk: WaveRequest(78), PCMS $B4 ("I'm outta here"); resident.
run([sys.executable,'tools/capture_retail_audio.py','effect',WORK/'cc-driver.bin',WORK/'fx121','180'])
checked_core_sha(core_file,core_sha) # Captures must use the same pinned Core bytes.
# Sound RAM holds the resident effects plus one swappable bank: the zone's own effects
# (Palmtree Panic, Collision Chaos) or the special stage's, loaded with the zone as the
# original loads each round's PCM bank (SNCBNK<n>B.BIN). Effects not listed are resident.
BANKS=['SFXZ0.PCM','SFXZ1.PCM','SFXSP.PCM','SFXZ2.PCM','SFXZ3.PCM']
# Request 183 differs by round (Sound Drivers/PCM/_Sound IDs.inc; retail R31A harir3
# calls the FM PlaySound at $202282): Palmtree Panic's Amy plays PCM $B7 (giggle),
# Collision Chaos's spike trap (TRAP_R3.C harir3_sub) plays FM $B7. Each lives in its
# zone's bank; src/audio.c looks in the bank before the resident effects.
# Tidal Tempest (SFXZ2, index 3) takes the FM effects its own sources soundset():
# 160 amenbo, 161/162 exit (PLAYSUB4.C), 172 boss hit, 173 bubble (AWA.C, COLI4.C),
# 179 tagameb, 182 drown (PLAYSUB4.C plawamaster), 183 harir4 (FM $B7, as CC's
# harir3), 217 ET4. 191 (switch: R4/R5/R6/R8) and 223 (air warning) are resident.
# Quartz Quadrant (SFXZ3, index 4): 160, 172 and 217 as Tidal Tempest, 183 FM $B7
# (DENDEN.C:237, as harir3), and BOSS_5.C's 196 ($C4, egg5meca2/egg5catch) and 203
# ($CB, egg5catch_wait). 158, 163, 176, 180 and 191 are resident.
BANK_OF={160:[0,3,4],162:[0,3],161:[0,3],167:[0],164:[0],183:[0],
         127:[1],185:[1],215:[1],159:[1],172:[1,3,4],190:[1],202:[1],125:[1],1146:[1],181:[1,2],217:[1,2,3,4],
         184:[2],188:[2],195:[2],206:[2],214:[2],173:[3],179:[3],182:[3],196:[4],203:[4]}
bank=bytearray();ranges=[];effects=[];banked=[[] for _ in BANKS]
for request,name in [(146,'jump'),(149,'ring'),(152,'spring'),(156,'charge'),(145,'dash-release'),(148,'ring-loss'),(147,'hurt-death'),(144,'skid'),(150,'enemy-defeat'),(158,'explosion'),(160,'enemy-projectile'),(162,'enemy-jump'),(167,'enemy-impact'),(216,'time-warp'),(177,'future-voice'),(178,'past-voice'),(174,'checkpoint'),(176,'wall-break'),(157,'signpost'),(154,'bonus-finish'),(189,'bonus-tally'),(180,'extra-life'),(151,'shield'),(163,'collapse'),(164,'tunnel-door'),(175,'big-ring'),(183,'amy-giggle'),(181,'special-b5'),(184,'special-b8'),(188,'time-ufo'),(195,'special-c3'),(200,'special-warp'),(206,'special-ce'),(214,'special-d6'),(217,'time-stone'),(223,'timer-warning'),(127,'bumper'),(185,'kama-blade'),(215,'pocket-capture'),(159,'pocket-release'),
                     (172,'boss-hit'),(190,'bumper-block'),(202,'metal-sonic'),(125,'amy-yelp'),(1146,'bumper-break'),(121,'bye-voice'),(183,'spike-fm'),
                     (161,'exit-b'),(173,'bubble'),(179,'tagameb'),(182,'drown'),(191,'switch'),
                     (196,'qq-boss-c4'),(203,'qq-boss-cb')]:
    stem=f'fx{request}fm' if name=='spike-fm' else f'fx{request}'
    converted=WORK/f'{stem}.pcm'
    run(['ffmpeg','-v','error','-y','-f','s16le','-ar','44100','-ac','2','-i',WORK/f'{stem}.raw','-af','volume=1.7','-ar','11025','-ac','1','-f','s8',converted])
    samples=array.array('b',converted.read_bytes());active=[i for i,v in enumerate(samples) if abs(v)>1]
    assert active
    begin=max(0,active[0]-55);end=min(len(samples),active[-1]+221)
    pcm=samples[begin:end].tobytes();assert len(pcm)<65536
    where=[1,3,4] if name=='spike-fm' else BANK_OF.get(request,[])
    record={'id':request,'name':name,'bytes':len(pcm),'sha256':hashlib.sha256(pcm).hexdigest(),'banks':[BANKS[b] for b in where] or ['SFX.PCM']}
    effects.append(record)
    if not where:ranges.append([len(bank),len(pcm)]);bank.extend(pcm)
    for b in where:banked[b].append((request,pcm))
ram_base,ram_end=0xe000,0x7f000
resident=[e for e in effects if e['banks']==['SFX.PCM']]
# Bank files are their sound RAM image (each effect at an even offset, even length):
# src/audio.c reads one straight after the resident bank in a single CD transfer,
# whose 16-bit copy never makes a byte access to sound RAM.
bank_base=ram_base+(len(bank)+3&~3)
bank_files=[];bank_rows=[];bank_hashes=[]
for b,items in enumerate(banked):
    data=bytearray();rows=[]
    for request,pcm in items:
        rows.append((request,len(data),len(pcm)));data.extend(pcm+bytes(len(pcm)%2))
    assert bank_base+len(data)<=ram_end,(BANKS[b],bank_base+len(data)-ram_end)
    (ROOT/'cd').mkdir(exist_ok=True);(ROOT/'cd'/BANKS[b]).write_bytes(bytes(data))
    h=2166136261
    for x in data:h=((h^x)*16777619)&0xffffffff
    bank_files.append({'file':BANKS[b],'effects':[r for r,_ in items],'ram_bytes':len(data),'file_bytes':len(data)});bank_rows.append(rows);bank_hashes.append((len(data),h))
assert len(bank)+(-len(bank)%2048)<=ram_end-ram_base # Includes the CD sector padding.

(OUT/'feedback.pcm').write_bytes(bank)
(ROOT/'cd').mkdir(exist_ok=True);(ROOT/'cd/SFX.PCM').write_bytes(bank+bytes(-len(bank)%2048))
fnv=2166136261
for b in bank:fnv=((fnv^b)*16777619)&0xffffffff
width=max(len(r) for r in bank_rows)
(OUT/'feedback.inc').write_text(f'#define SFX_RAM_BASE 0x{ram_base:x}u\n#define SFX_RAM_END 0x{ram_end:x}u\n#define EFFECT_COUNT {len(resident)}u\n#define SFX_BYTES {len(bank)}u\n#define SFX_HASH 0x{fnv:08x}u\nstatic const unsigned effect_ranges[][2]={{'+','.join('{%d,%d}'%tuple(r) for r in ranges)+'};\nstatic const short effect_requests[]={'+','.join(str(e['id']) for e in resident)+'};\n'
    +f'/* Swappable banks: 0 Palmtree Panic, 1 Collision Chaos, 2 special stage, 3 Tidal Tempest, 4 Quartz Quadrant. Rows: request, byte offset, bytes. */\n#define SFX_BANK_COUNT {len(BANKS)}u\n#define SFX_BANK_EFFECTS {width}u\n#define SFX_BANK_BASE 0x{bank_base:x}u\n'
    +f'#define SFX_BANK_MAX_BYTES {max(n for n,_ in bank_hashes)}u\n_Static_assert(SFX_BANK_BASE+SFX_BANK_MAX_BYTES<=SFX_RAM_END,"effect bank overruns sound RAM");\n'
    +'static const unsigned sfx_bank_sizes[SFX_BANK_COUNT][2]={'+','.join('{%d,0x%08xu}'%h for h in bank_hashes)+'};\n'
    +'static const char *const sfx_bank_files[SFX_BANK_COUNT]={'+','.join(f'"{b}"' for b in BANKS)+'};\n'
    +'static const unsigned char sfx_bank_counts[SFX_BANK_COUNT]={'+','.join(str(len(r)) for r in bank_rows)+'};\n'
    +'static const struct {short request;unsigned offset,bytes;} sfx_bank_effects[SFX_BANK_COUNT][SFX_BANK_EFFECTS]={'+','.join('{'+','.join('{%d,%d,%d}'%r for r in rows)+'}' for rows in bank_rows)+'};\n')
music=[]
# Track 24 is the boss music (LOADER2.C sub_sync(103): CDPlay(103-79)); track 26 is the title
# screen music (Sound.inc CDDA_TITLE, played once by SPX.asm SPCmd_LoadTitle).
for era,source in [(0,3),(1,None),(2,4),(3,5),(4,28),(5,29),(6,30),(7,32),(8,24),(9,26)]:
    path=OUT/f'music{era}.raw'
    if source:
        first=tracks[source][1];last=tracks[source+1].get(0,tracks[source+1][1])
        with (WORK/'sonic.bin').open('rb') as f:f.seek(first*2352);raw=f.read((last-first)*2352)
        path.write_bytes(raw)
    else:
        duration=(WORK/'past.raw').stat().st_size/176400
        run(['ffmpeg','-v','error','-y','-f','s16le','-ar','44100','-ac','2','-i',WORK/'past.raw','-af',f'volume=1.5,afade=t=out:st={duration-3}:d=3','-f','s16le',path])
        with path.open('ab') as f:f.write(bytes(-path.stat().st_size%2352))
    music.append({'era':era,'saturn_track':era+2,'retail_track':source,'sectors':path.stat().st_size//2352,'sha256':sha(path)})
outputs=[OUT/'feedback.pcm',OUT/'feedback.inc',ROOT/'cd/SFX.PCM']+[ROOT/'cd'/b for b in BANKS]+[OUT/f'music{i}.raw' for i in range(10)]
report={'sound':'Original retail Sonic CD FM driver, rendered offline; mono 8-bit resampling','music':True,'inputs':fingerprint,'outputs':{str(p.relative_to(ROOT)):sha(p) for p in outputs},'sample_rate':11025,'samples':effects,'bytes':len(bank),'banks':bank_files,'bank_base':bank_base,'ram_base':ram_base,'ram_end':ram_end,'driver':'pinned Yaul examples / Ponesound','fm_driver_offset':fm,'fm_driver_sha256':sha(WORK/'fm-driver.bin'),'past_driver_sha256':sha(WORK/'past-driver.bin'),'cc_driver_sha256':sha(WORK/'cc-driver.bin'),'past_capture':json.loads((WORK/'past-capture.json').read_text()),'tracks':music}
report_path.write_text(json.dumps(report,indent=2)+'\n')
print('Original audio prepared:',len(bank),'effect bytes and',len(music),'CDDA tracks')
