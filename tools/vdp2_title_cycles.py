"""Independent Sega VDP2 table 3.2/3.3/3.4 checks for this title profile.

Normal resolution, 16 colors, 1x reduction allowance (enlargement is legal),
1x1 cells, no vertical cell scroll. Not a general validator for other modes.
Reference: https://www.infochunk.com/saturn/segahtml_en/hard/vdp2/hon/p03_31.htm
"""
import struct

def errors(banks):
    assert len(banks)==4 and all(len(b)==8 for b in banks)
    assert all(0<=c<16 for b in banks for c in b)
    result=[]
    # Table 3.4 normal-mode character-fetch timings by pattern-name timing.
    allowed=({0,1,2,4,5,6,7},{0,1,2,3,5,6,7},{0,1,2,3,6,7},
             {0,1,2,3,7},{0,1,2,3},{1,2,3},{2,3},{3})
    for screen,bank in [(0,0),(1,0),(3,3)]:
        names=[t for t,c in enumerate(banks[bank]) if c==screen]
        patterns=[t for t,c in enumerate(banks[bank]) if c==screen+4]
        if len(names)!=1:result.append(f'NBG{screen}: expected one PN fetch, got {names}')
        if len(patterns)!=1:result.append(f'NBG{screen}: expected one CG fetch, got {patterns}')
        for pn in names:
            legal=set(range(8)) if pn==0 and screen<2 else allowed[pn]
            for cg in patterns:
                if cg not in legal:result.append(f'NBG{screen}: PN T{pn} cannot feed CG T{cg}')
    return result

def state_sections(data):
    """Read the pinned core's named state chunks, never search payload bytes."""
    assert data[:8]==b'MDFNSVST'
    end=struct.unpack_from('<I',data,20)[0];assert 32<=end<=len(data)
    cursor=32;sections={}
    while cursor<end:
        assert cursor+36<=end
        name=data[cursor:cursor+32].split(b'\0',1)[0].decode()
        length=struct.unpack_from('<I',data,cursor+32)[0];cursor+=36
        stop=cursor+length;assert stop<=end and name not in sections
        fields={}
        while cursor<stop:
            n=data[cursor];cursor+=1;assert cursor+n+4<=stop
            field=data[cursor:cursor+n].decode();cursor+=n
            size=struct.unpack_from('<I',data,cursor)[0];cursor+=4
            assert cursor+size<=stop and field not in fields
            fields[field]=data[cursor:cursor+size];cursor+=size
        sections[name]=fields
    assert cursor==end
    return sections

def inspect(path):
    sections=state_sections(path.read_bytes())
    matches=[s for s in sections.values() if '&VCPRegs[0][0]' in s]
    assert len(matches)==1
    v=matches[0];cycles=v['&VCPRegs[0][0]'];assert len(cycles)==32
    banks=[list(cycles[n:n+8]) for n in range(0,32,8)]
    regs=struct.unpack('<256H',v['RawRegs'])
    assert v['HRes']==bytes(len(v['HRes'])),'title must use normal 320-dot mode'
    assert regs[0x98//2]&0x0303==0,'fetch counts assume 1x reduction allowance'
    assert regs[0x0e//2]&0x300==0x300,'four partitioned VRAM banks required'
    assert regs[0x28//2]==0,'title profile requires 16-color 1x1 cell layers'
    assert regs[0x30//2]&0x8000==0 and regs[0x32//2]&0x8000==0,'two-word PND profile'
    assert regs[0x9a//2]&0x0101==0,'vertical cell scroll must be disabled'
    assert (regs[0x78//2],regs[0x7a//2],regs[0x88//2],regs[0x8a//2])==(0,0xcd00,0,0xcd00),'preserve original full-width sampling'
    return {'cycles':banks,'errors':errors(banks),'zoom_limit':regs[0x98//2],
            'ram_control':regs[0x0e//2],'raw_cycle_words':list(regs[8:16])}
