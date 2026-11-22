#!/usr/bin/env python3
"""Precompose ALL original Sonic poses, verify source pixels, compress losslessly.

DPLC composition is build-time work, not a cache-miss penalty during gameplay.
The native source decoder generates the indices; a separate source renderer
verifies every palette-expanded pixel before this pack is written.

Rounds past Palmtree Panic Acts 1-2 carry their own Sonic mappings, DPLCs and
art in the retail level programs. They render to three more pose sets, each
identical across its programs: R13 and rounds 3/5/6/7 (167 poses: Hang2
24-25, 137-138, 166), round 4 (188: Wade, Bubble, LookBack...) and round 8
(188: the mini poses 111-126, Shrink/Grow). round_packs reads each set from
its programs, normalises it to the 198-entry tables, decodes it natively and
checks it pixel by pixel against an independent renderer of the program's own
tables. Round 4's full set packs to 112,522 bytes, over the 0x18000 SONFRM
region, so its pack empties the poses no round 4 code can show (ROUND_OMIT):
the only original setters of those animations are other rounds' code
(PLAYER6.C Hang2, DAI_K.C/KDAI6.C Balance3D, R8 SHUT.C Rotate, R8 BEAM.C
Shrink/Grow, R6 SHOOT6.C Roll3D; nothing sets Run3D or Roll3D 54), and the mini
poses need chibi_flag, which only R8's beams set. Float keeps 185-186.
"""
import ctypes as C
import hashlib,json,struct,subprocess
from convert_assets import ROOT,sonic_frame
from convert_objects import pack_texture
from native import IS_BROWSER, decode_sonic

class Art(C.Structure):
    _fields_=[('part',C.c_void_p*4),('size',C.c_uint32*4)]

def native_lib(out):
    if IS_BROWSER:
        return None
    libpath=out/'frame-assets.dylib'
    subprocess.run(['clang','-std=c11','-O2','-Wall','-Wextra','-Werror','-dynamiclib','-Isrc',
        'src/sonic_art.c','-o',str(libpath)],cwd=ROOT,check=True)
    lib=C.CDLL(str(libpath));lib.scd_sonic_art_open.argtypes=[C.POINTER(Art),C.c_void_p,C.c_size_t]
    lib.scd_sonic_art_decode.argtypes=[C.POINTER(Art),C.c_uint,C.POINTER(C.c_uint16)]
    lib.scd_sonic_art_color.argtypes=[C.POINTER(Art),C.c_uint];lib.scd_sonic_art_color.restype=C.c_uint16
    return lib

def frame_pack(lib,source,reference):
    """SFR1 pack of the 198 poses the native decoder reads from a SON1 source;
    reference(n) gives each pose's RGB555 pixels from a separate renderer."""
    if IS_BROWSER:
        decoded=decode_sonic(source)
        colors=struct.unpack_from('>16H',decoded)
    else:
        data=C.create_string_buffer(source);art=Art()
        assert lib.scd_sonic_art_open(C.byref(art),data,len(source))==0
        colors=[lib.scd_sonic_art_color(C.byref(art),n) for n in range(16)]
    frame=(C.c_uint16*1024)();streams=[];checks=[]
    for n in range(198):
        if IS_BROWSER:
            frame=struct.unpack_from('>1024H',decoded,32+n*2048)
        else:
            assert lib.scd_sonic_art_decode(C.byref(art),n,frame)==0,('native decode failed',n)
        expanded=struct.pack('>4096H',*(colors[(frame[i//4]>>((3-(i%4))*4))&15] for i in range(4096)))
        assert expanded==reference(n),('native/source pixel disagreement',n)
        raw=struct.pack('>1024H',*frame);streams.append(pack_texture(raw));checks.append(hashlib.sha256(raw).hexdigest())
    offset=40+199*4;offsets=[offset]
    for stream in streams:offset+=len(stream);offsets.append(offset)
    payload=b'SFR1'+struct.pack('>I16H199I',198,*colors,*offsets)+b''.join(streams)
    assert len(payload)==offset and len(payload)<=0x18000,('pack exceeds the SONFRM region',len(payload))
    return payload,streams,checks

# Pose sets of the retail level programs (see the module comment); the first
# program of each set is the source, every other program must render the same.
ROUND_PACKS={'B':('R13C','R13D')+tuple(f'R{r}{a}{e}' for r in (3,5,6,7) for a in (1,2,3) for e in ('ABCD' if a<3 else 'CD')),
             '4':tuple(f'R4{a}{e}' for a in (1,2,3) for e in ('ABCD' if a<3 else 'CD')),
             '8':tuple(f'R8{a}{e}' for a in (1,2,3) for e in ('ABCD' if a<3 else 'CD'))}
ROUND_OMIT={'4':frozenset([*range(24,38),*range(111,127),*range(166,173),181,182,183,184,187])}

def program_tables(program):
    """Sonic's mapping and DPLC tables and art in a level program: ObjSonic's
    move.l #Map,oMap(a0) (twice) and the DPLC routine's lea DPLCs,a2 ... lea Art,a1."""
    def one(pattern):
        at=program.find(pattern);assert at>=0 and program.find(pattern,at+1)<0,('table reference',pattern.hex())
        return at
    maps=struct.unpack_from('>I',program,one(bytes.fromhex('00050017217c'))+6)[0]-0x200000
    dplc_at=one(bytes.fromhex('674e148045f9'));dplcs=struct.unpack_from('>I',program,dplc_at+6)[0]-0x200000
    assert program[dplc_at+0x34:dplc_at+0x36]==bytes.fromhex('43f9'),'DPLC art reference'
    art=struct.unpack_from('>I',program,dplc_at+0x36)[0]-0x200000
    count=struct.unpack_from('>H',program,maps)[0]//2
    assert count==struct.unpack_from('>H',program,dplcs)[0]//2 and count<=198
    return maps,dplcs,art,count

def program_source(program,palette,omit=frozenset()):
    """SON1 source (art, 198-entry mapping and DPLC tables, palette) from one
    program; poses past its table count, and omitted poses, are empty."""
    maps,dplcs,art,count=program_tables(program)
    mtable,mdata,dtable,ddata,tiles=[],bytearray(b'\0'),[],bytearray(b'\0\0'),0
    for n in range(198):
        if n>=count or n in omit:mtable.append(0);dtable.append(0);continue
        mo=maps+struct.unpack_from('>H',program,maps+n*2)[0];do=dplcs+struct.unpack_from('>H',program,dplcs+n*2)[0]
        loads=struct.unpack_from('>H',program,do)[0]
        for i in range(loads):
            w=struct.unpack_from('>H',program,do+2+i*2)[0];tiles=max(tiles,(w&4095)+(w>>12)+1)
        mtable.append(len(mdata));mdata+=program[mo:mo+1+program[mo]*5]
        dtable.append(len(ddata));ddata+=program[do:do+2+loads*2]
    blob=lambda table,data:struct.pack('>198H',*(396+t for t in table))+bytes(data)
    parts=[program[art:art+tiles*32],blob(mtable,mdata),blob(dtable,ddata),palette]
    offset=8+8*len(parts);header=b'SON1'+struct.pack('>I',len(parts))
    for part in parts:header+=struct.pack('>II',offset,len(part));offset+=len(part)
    return header+b''.join(parts)

def program_pose(program,n,colors):
    """Independent renderer of pose n from the program's own tables (Mega Drive
    order: an earlier mapping piece wins where pieces overlap)."""
    maps,dplcs,art,count=program_tables(program);out=bytearray(8192)
    if n>=count:return bytes(out)
    mo=maps+struct.unpack_from('>H',program,maps+n*2)[0];do=dplcs+struct.unpack_from('>H',program,dplcs+n*2)[0]
    tiles=bytearray()
    for i in range(struct.unpack_from('>H',program,do)[0]):
        w=struct.unpack_from('>H',program,do+2+i*2)[0];tiles+=program[art+(w&4095)*32:art+((w&4095)+(w>>12)+1)*32]
    drawn=set()
    for i in range(program[mo]):
        y,size,high,low,x=program[mo+1+i*5:mo+6+i*5]
        x=x-256 if x>127 else x;y=y-256 if y>127 else y
        w,h,word=((size>>2)&3)+1,(size&3)+1,high<<8|low
        for py in range(h*8):
            for px in range(w*8):
                sx=w*8-1-px if word&0x800 else px;sy=h*8-1-py if word&0x1000 else py
                b=tiles[((word&2047)+(sx//8)*h+sy//8)*32+(sy%8)*4+(sx%8)//2];c=b>>4 if sx%2==0 else b&15
                d=(32+y+py)*64+32+x+px
                if c and d not in drawn:drawn.add(d);struct.pack_into('>H',out,d*2,colors[c])
    return bytes(out)

def round_packs(lib,out):
    from extract_mmd import disc_files
    iso=ROOT/'build/retail/sonic.iso';files=disc_files(iso.read_bytes())
    palette=(ROOT/'assets/generated/sonic-source.bin').read_bytes()[-32:]
    reports={}
    for name,programs in ROUND_PACKS.items():
        omit=ROUND_OMIT.get(name,frozenset())
        first=files[programs[0]+'__.MMD'];source=program_source(first,palette,omit)
        if IS_BROWSER:
            colors=struct.unpack_from('>16H',decode_sonic(source))
        else:
            art=Art();buffer=C.create_string_buffer(source);assert lib.scd_sonic_art_open(C.byref(art),buffer,len(source))==0
            colors=[lib.scd_sonic_art_color(C.byref(art),n) for n in range(16)]
        for program in programs:assert files[program+'__.MMD'].find(palette)>=0,('Sonic palette',program)
        payload,streams,checks=frame_pack(lib,source,lambda n:bytes(8192) if n in omit else program_pose(first,n,colors))
        for program in programs[1:]:
            other=files[program+'__.MMD']
            assert all(program_pose(other,n,colors)==program_pose(first,n,colors) for n in range(198)),('pose set differs',program)
        (ROOT/f'assets/generated/sonic-frames-{name.lower()}.bin').write_bytes(payload)
        reports[name]={'programs':programs,'omitted_poses':sorted(omit),'bytes':len(payload),'pack_sha256':hashlib.sha256(payload).hexdigest(),
                       'raw_pose_sha256':checks,'iso_sha256':hashlib.sha256(iso.read_bytes()).hexdigest()}
        print(f'Round Sonic frame pack {name}: {len(payload)} bytes; 198 poses from {len(programs)} programs, source-exact')
    return reports

def generate():
    out=ROOT/'build/sonic-animation';out.mkdir(exist_ok=True)
    lib=native_lib(out)
    source=(ROOT/'assets/generated/sonic-source.bin').read_bytes()
    payload,streams,checks=frame_pack(lib,source,sonic_frame)
    (ROOT/'assets/generated/sonic-frames.bin').write_bytes(payload)
    report={'passed':True,'frames':198,'pixels':198*4096,'bytes':len(payload),
        'maximum_stream_bytes':max(map(len,streams)),'raw_pose_sha256':checks,
        'source_pack_sha256':hashlib.sha256(source).hexdigest(),'pack_sha256':hashlib.sha256(payload).hexdigest(),
        'source_sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in
            ['src/sonic_art.c','src/sonic_art.h','tools/sonic_frame_assets.py','tools/convert_assets.py','tools/convert_objects.py']}}
    report['round_packs']=round_packs(lib,out)
    (out/'frame-pack-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Original Sonic frame pack: {len(payload)} bytes; all 198 poses / 811008 pixels source-exact')
    return report
if __name__=='__main__':generate()
