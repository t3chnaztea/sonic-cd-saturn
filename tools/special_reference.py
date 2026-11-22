"""Execute unmodified source operations in the offline pinned Sega CD core.

Assembly syntax is adapted for GNU as, with absolute test RAM addresses.
No emulator or 68000 code is linked into the native Saturn build.
"""
import ctypes as C,re,struct,subprocess
from pathlib import Path
from special_assets import ROOT,SOURCE
WORK=ROOT/'build/special-reference';WORK.mkdir(exist_ok=True)

def assemble(name,start,end,constants=None):
    text=(SOURCE/'Sub.asm').read_text();body=text.split(start+':',1)[1].split(end+':',1)[0]
    # End markers include descriptive comments only; strip comments as syntax.
    body=start+':\n'+body;scope=start;lines=[]
    for line in body.splitlines():
        line=line.split(';',1)[0].strip()
        if not line:continue
        label=re.match(r'([A-Za-z_]\w*):',line)
        if label:scope=label[1]
        line=re.sub(r'(?<![\w])\.(\w+)',lambda m:scope+'__'+m[1],line)
        line=re.sub(r'\$([0-9A-Fa-f]+)',r'0x\1',line)
        lines.append(line)
    offsets={};offset=0
    variables=text.split('gfxCamX',1)[1].split('; ---',1)[0]
    variables='gfxCamX'+variables
    for line in variables.splitlines():
        m=re.match(r'\s*(?:(\w+)\s+)?rs\.([bwl])\s+(\$[0-9A-Fa-f]+|\d+)',line)
        if m:
            label,unit,count=m.groups()
            if label:offsets[label]=offset
            offset+=int(count.replace('$','0x'),0)*{'b':1,'w':2,'l':4}[unit]
    preamble='.text\n.equ WORDRAM2M,0x80000\n.equ TRACETBL,0x1c800\n.equ IMGHEIGHT,96\n.equ gfxVars,0x30000\n'
    preamble+=''.join(f'.equ {label},{value}\n' for label,value in offsets.items())
    preamble+=''.join(f'.equ {label},{value}\n' for label,value in (constants or {}).items())
    source=WORK/f'{name}.s';obj=WORK/f'{name}.o';binary=WORK/f'{name}.bin'
    source.write_text(preamble+'\n'.join(lines)+'\n')
    subprocess.run([ROOT/'.deps/build-binutils-m68k/gas/as-new','--register-prefix-optional','-m68000','-o',obj,source],check=True)
    subprocess.run([ROOT/'.deps/build-binutils-m68k/binutils/objcopy','-O','binary','-j','.text',obj,binary],check=True)
    return binary.read_bytes()

class Reference:
    def __init__(self):
        import retail_capture as host
        self.lib=host.lib;self.host=host
        path=ROOT/'build/retail/sonic.cue';game=host.Game(str(path).encode(),None,0,None)
        self.lib.retro_load_game.restype=C.c_bool
        if not self.lib.retro_load_game(C.byref(game)):raise RuntimeError('Cannot load private Sega CD reference disc')
        for _ in range(600):self.lib.retro_run()
        self.lib.m68k_pulse_halt();self.lib.gen_zreset_w(0,0)
        # Pinned 64-bit external_t CD cartridge (0x810088), boot ROM (0x20000),
        # PRG (0x80000), 1M word banks (0x40000), 2M words (0x40000), BRAM (0x2000).
        self.ext=C.addressof(C.c_uint8.in_dll(self.lib,'ext'))
        self.prg=self.ext+0x830088;self.ram=self.prg+0xc0000;self.regs=self.ram+0x42000
        self.kos=assemble('kosinski','KosDec','RunObjects')
        # The source has an unreachable JMP $500000 after RTS; keep it intact.
        self.projection=assemble('projection','GenGfxTraceTbl','InitGfxOperation')
        # Grant 2M Word RAM through the Main ASIC handler so the Sub CPU's
        # memory map is unlocked as well as the ownership register updated.
        self.lib.ctrl_io_write_byte(0xa12003,2)
        self.call(bytes.fromhex('13fc000000ff80034e75')) # MOVE.B #0,$FF8003; RTS
        self.lib.ctrl_io_write_byte(0xa12003,2)
        if C.c_uint16.from_address(self.regs+2).value&5:
            raise AssertionError('reference Word RAM was not granted in 2M mode')
        self.stamp_animation=assemble('stamp-animation','AnimateStamps','HazardAnim_SS1',{'STAMPMAP':0x20000,'fanAnimFrame':0x6000,'hazardAnimFrame':0x6002,'hazardAnimDelay':0x6004,'hazardAnimData':0x6006,'hazardAnimCount':0x600a,'fanAnimData':0x600c,'fanAnimCount':0x6010})
        self.lib.gfx_init()
    @staticmethod
    def write(base,offset,data):
        if len(data)&1:data+=b'\0'
        swapped=bytearray(data);swapped[::2],swapped[1::2]=data[1::2],data[::2]
        C.memmove(base+offset,bytes(swapped),len(data))
    @staticmethod
    def read(base,offset,n):
        b=C.string_at(base+offset,(n+1)&~1);swapped=bytearray(b);swapped[::2],swapped[1::2]=b[1::2],b[::2]
        return bytes(swapped[:n])
    def call(self,code,a0=0,a1=0):
        self.write(self.prg,0x200,bytes.fromhex('60fe'))
        self.write(self.prg,0x1000,code)
        self.write(self.prg,0x2effc,struct.pack('>I',0x200))
        self.lib.s68k_pulse_reset();self.lib.s68k_clear_halt();self.lib.s68k_clear_wait()
        self.lib.s68k_set_reg(17,0x2700);self.lib.s68k_set_reg(18,0x2effc)
        self.lib.s68k_set_reg(8,a0);self.lib.s68k_set_reg(9,a1);self.lib.s68k_set_reg(16,0x1000)
        for _ in range(120):
            self.lib.retro_run();self.host.chunks.clear()
            pc=self.lib.s68k_get_reg(16)
            if pc==0x200:return
        raise AssertionError(('original routine did not return',hex(pc)))
    def decompress(self,data,n):
        self.write(self.prg,0x10000,data);self.write(self.prg,0x40000,bytes(n+16))
        self.call(self.kos,0x10000,0x40000)
        if self.lib.s68k_get_reg(9)!=0x40000+n:raise AssertionError('original Kosinski length differs')
        return self.read(self.prg,0x40000,n)
    def trace(self,camera,sine):
        x,y,z,pitch,yaw=camera
        words=[x,y,z,pitch,sine(pitch),sine(pitch+128),yaw,sine(yaw),sine(yaw+128),sine(yaw+256),sine(yaw+384),128,-64]
        self.write(self.prg,0x30000,struct.pack('>13H',*(w&65535 for w in words))+bytes(200))
        self.call(self.projection)
        return self.read(self.ram,0x1c800,768)
    def begin_animation(self,parts,state=(0,0,0)):
        self.write(self.prg,0x6000,struct.pack('>3HIHIH',*state,0x6200,len(parts[5])//10-1,0x6400,len(parts[6])//8-1))
        self.write(self.prg,0x6200,parts[5]);self.write(self.prg,0x6400,parts[6])
        self.write(self.ram,0x20000,parts[1])
    def animate(self):
        self.call(self.stamp_animation)
        return self.read(self.ram,0x20000,32768),struct.unpack('>3H',self.read(self.prg,0x6000,6))
    def render(self,stamps,stamp_map,trace):
        C.memset(self.ram,0,0x40000);C.memset(self.regs,0,0x200)
        self.write(self.ram,0,stamps);self.write(self.ram,0x20000,stamp_map);self.write(self.ram,0x1c800,trace)
        for address,value in [(0x02,0),(0x58,6),(0x5a,0x8000),(0x5c,11),(0x5e,0x7400),(0x60,0),(0x62,256),(0x64,96)]:
            C.c_uint16.from_address(self.regs+address).value=value
        self.lib.gfx_start(0x7200,0)
        if not(C.c_uint16.from_address(self.regs+0x58).value&0x8000):raise AssertionError('pinned graphics-register ABI mismatch')
        self.lib.gfx_update(10000000)
        if C.c_uint16.from_address(self.regs+0x64).value:raise AssertionError('graphics operation incomplete')
        raw=self.read(self.ram,0x1d000,12288);pixels=bytearray(256*96)
        for y in range(96):
            for x in range(256):
                pos=(x//8*12+y//8)*32+(y%8)*4+(x%8)//2
                pixels[y*256+x]=(raw[pos]>>(0 if x&1 else 4))&15
        return bytes(pixels)
