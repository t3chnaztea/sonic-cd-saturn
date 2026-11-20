#!/usr/bin/env python3
"""Run the retail sound drivers offline in pinned Genesis Plus GX (little-endian host)."""
import array,ctypes as C,json,struct,sys
from pathlib import Path
import retail_capture as host
lib=host.lib;chunks=host.chunks

def load(path):
    game=host.Game(str(path.resolve()).encode(),None,0,None)
    lib.retro_load_game.restype=C.c_bool
    if not lib.retro_load_game(C.byref(game)):raise RuntimeError('Cannot load capture harness/game; check Sega CD BIOS')

def frames(n):
    for _ in range(n):lib.retro_run()

if sys.argv[1]=='fm':
    rom=bytearray(0x400)
    struct.pack_into('>II',rom,0,0xffff00,0x200)
    rom[0x100:0x110]=b'SEGA GENESIS    ';rom[0x1f0]=ord('U')
    rom[0x200:0x206]=bytes.fromhex('46fc270060fe') # SR=$2700; BRA self
    path=Path('build/retail/fm.bin');path.write_bytes(rom);load(path)
    ram=(C.c_uint8*8192).in_dll(lib,'zram')
    driver=Path('build/retail/fm-driver.bin').read_bytes()
    C.memmove(ram,driver,len(driver));lib.gen_zreset_w(1,0);frames(120)
    # Special stage: B5, B8, BC, C3, SSWARP (C8), CE, D6, D9 and the timer warning DF.
    for request in [146,149,152,156,145,148,147,144,150,158,160,162,167,216,174,176,157,154,189,151,163,164,175,181,184,188,195,200,206,214,217,223,185,215,159,172,190,202,183,
                    # Tidal Tempest (R4 soundset): exit, bubble, tagameb, drown, switch.
                    161,173,179,182,191,
                    # Quartz Quadrant (R5 BOSS_5.C soundset): FM $C4 drill/catcher, $CB bomb drop.
                    196,203]:
        ram[0x1c09]=0xe0;frames(20);chunks.clear();ram[0x1c09]=request;frames(300 if request in (200,216) else 180)
        raw=b''.join(chunks);samples=array.array('h',raw)
        assert max(samples)>1000 and min(samples)<-1000
        # FM $B7 (CC's harir3) shares its number with the PCM Amy giggle captured below.
        Path(f'build/retail/fx{request}{"fm" if request==183 else ""}.raw').write_bytes(raw)
else:
    # PCM gain 30% avoids saturating the emulator's stereo output mixer.
    load(Path('build/retail/sonic.cue'));frames(600)
    lib.m68k_pulse_halt();lib.gen_zreset_w(0,0)
    # offsetof(external_t, cd_hw.prg_ram) in the pinned 64-bit, static core.
    # 0x810088 cartridge + 0x20000 boot ROM. All 68K words are host byte-swapped.
    ext=(C.c_uint8*0x900000).in_dll(lib,'ext');offset=0x830088;base=C.addressof(ext)+offset
    def write(addr,data):
        data += bytes(len(data)%2) # Odd-sized original banks need a final bus word.
        swapped=bytearray(data);swapped[0::2],swapped[1::2]=data[1::2],data[0::2]
        C.memmove(base+addr,bytes(swapped),len(swapped))
    def read(addr,n):
        return bytes(ext[offset+((addr+i)^1)] for i in range(n))
    driver_path=Path(sys.argv[2]) if len(sys.argv)>2 else Path('build/retail/past-driver.bin')
    output=Path(sys.argv[3]) if len(sys.argv)>3 else Path('build/retail/past')
    bank=driver_path.read_bytes()
    assert bank[:6]==b'SNCBNK' and bank[8:16]==b'.S28    '
    write(0x40000,bank);assert read(0x40000,16)==bank[:16]
    write(0x200,bytes.fromhex('60fe'))
    lib.s68k_pulse_reset();lib.s68k_clear_halt();lib.s68k_clear_wait();lib.s68k_set_reg(17,0x2700)
    def call(addr):
        write(0x3effc,struct.pack('>I',0x200));lib.s68k_set_reg(18,0x3effc);lib.s68k_set_reg(16,addr);frames(1)
    call(0x40014);frames(20);assert lib.s68k_get_reg(16)==0x200
    ext[offset+(0x40022^1)]=0 if sys.argv[1] in ('voices','effect') else 0x81 # PCM queue slot 0: PPZ Past
    # SPX.asm uses timer reload 255 and invokes the driver on alternate IRQ3s.
    # Reproduce that hardware cadence (50 MHz / 1536 / 255 / 2), not VBlank.
    write(0x6c,struct.pack('>I',0x1000)) # level-3 autovector
    write(0x3e000,bytes(8))
    write(0x1000,bytes.fromhex(
        '087900000003e000' # BCHG #0,$3E000
        '6714'             # BEQ to RTE
        '48e7fffe'         # MOVEM.L D0-A6,-(SP)
        '52b90003e004'     # ADDQ.L #1,$3E004 (capture tick counter)
        '4eb900040010'     # JSR retail driver update
        '4cdf7fff'         # MOVEM.L (SP)+,D0-A6
        '4e73'))          # RTE
    write(0x200,bytes.fromhex('13fc000800ff803313fc00ff00ff803146fc200060fe'))
    lib.s68k_set_reg(18,0x3effc);lib.s68k_set_reg(16,0x200)
    if sys.argv[1]=='effect':
        frames(30);chunks.clear();ext[offset+(0x40022^1)]=int(sys.argv[4]);frames(180)
        raw=b''.join(chunks);samples=array.array('h',raw)
        assert max(map(abs,samples))>1000
        output.with_suffix('.raw').write_bytes(raw)
        lib.retro_deinit();sys.exit(0)
    if sys.argv[1]=='voices':
        frames(30)
        for request in [177,178,180,183]:
            chunks.clear();ext[offset+(0x40022^1)]=request;frames(150)
            raw=b''.join(chunks);samples=array.array('h',raw)
            assert max(map(abs,samples))>1000
            Path(f'build/retail/fx{request}.raw').write_bytes(raw)
        lib.retro_deinit();sys.exit(0)
    chunks.clear();seen={};loop=None
    for n in range(60000):
        frames(1)
        state=read(0x40018,2)
        for t in range(8):
            a=0x40118+t*128
            # Stopped channels retain counters that the driver no longer updates
            # musically (Metallic Madness stops two channels). Match active
            # sequencers; keep the established PPZ capture byte-for-byte stable.
            if len(sys.argv)>2 and not (read(a,1)[0]&128):
                state+=b'\x00'
            else:
                state+=b'\x80'+read(a+4,4)+read(a+10,4)+read(a+64,2)
        if state in seen and n-seen[state]>100:
            loop=[seen[state],n];break
        seen[state]=n
    print('Past timer ticks',int.from_bytes(read(0x3e004,4),'big'),'PC',hex(lib.s68k_get_reg(16)),'state',read(0x40018,16).hex(),flush=True)
    assert loop, 'Past music sequencer did not repeat'
    raw=b''.join(chunks);samples=array.array('h',raw)
    assert 1000<max(samples)<32000 and -32000<min(samples)<-1000
    output.with_suffix('.raw').write_bytes(raw)
    output.with_name(output.name+'-capture.json').write_text(json.dumps({'sequencer_repeat_frames':loop,'captured_frames':n+1,'driver_ticks':int.from_bytes(read(0x3e004,4),'big'),'timer_hz':50000000/1536/255/2,'peak':max(map(abs,samples))})+'\n')
lib.retro_deinit()
