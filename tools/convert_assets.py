#!/usr/bin/env python3
"""Convert original PPZ1 data to explicit big-endian Saturn asset packages.

Nemesis decoding follows scddisasm's Level/Functions (General).asm.
No game data is committed; inputs stay in the ignored upstream checkout.
"""
import hashlib
import json
import pathlib
import re
import struct

ROOT = pathlib.Path(__file__).resolve().parents[1]
from scd_source import SRC as SCD_SRC
DATA = SCD_SRC / 'Level'
OUT = ROOT / 'assets/generated'

def nemesis(data):
    if len(data) < 3:
        raise ValueError('truncated Nemesis header')
    header = int.from_bytes(data[:2], 'big')
    target = (header & 0x7fff) * 64
    pos, palette, table = 2, 0, {}
    while True:
        value = data[pos]
        pos += 1
        if value == 0xff:
            break
        if value & 0x80:
            palette = value & 15
            continue
        length, count = value & 15, ((value >> 4) & 7) + 1
        if not 1 <= length <= 8:
            raise ValueError('invalid Nemesis code length')
        code = data[pos]
        pos += 1
        table[length, code] = count, palette
    bitpos = pos * 8
    def read(n):
        nonlocal bitpos
        value = 0
        for _ in range(n):
            if bitpos >= len(data) * 8:
                raise ValueError('truncated Nemesis bitstream')
            value = (value << 1) | ((data[bitpos // 8] >> (7 - bitpos % 8)) & 1)
            bitpos += 1
        return value
    pixels = []
    while len(pixels) < target:
        code = 0
        for length in range(1, 9):
            code = (code << 1) | read(1)
            if length == 6 and code == 63:
                count, palette = read(3) + 1, read(4)
                break
            if (length, code) in table:
                count, palette = table[length, code]
                break
        else:
            raise ValueError('unknown Nemesis code')
        pixels.extend([palette] * count)
    if len(pixels) != target:
        raise ValueError('Nemesis output exceeds declared size')
    result = bytearray((pixels[i] << 4) | pixels[i + 1] for i in range(0, target, 2))
    if header & 0x8000:
        for i in range(4, len(result)):
            result[i] ^= result[i - 4]
    return bytes(result)

def palette(data):
    result = bytearray()
    for (word,) in struct.iter_unpack('>H', data):
        r, g, b = ((word >> shift) & 7 for shift in (1, 5, 9))
        # Preserve the original eight channel levels, expanded to RGB555.
        result += struct.pack('>H', 0x8000 | (r * 31 // 7) | ((g * 31 // 7) << 5) | ((b * 31 // 7) << 10))
    return bytes(result)

def layout(data):
    width, height = data[0] + 1, data[1] + 1
    if len(data) != 2 + width * height or width > 64 or height > 8:
        raise ValueError(f'invalid level layout {width}x{height}: {len(data)} bytes')
    result = bytearray(64 * 8)
    for row in range(height):
        result[row * 64:row * 64 + width] = data[2 + row * width:2 + (row + 1) * width]
    return bytes(result)

def assembly_frames(path, contiguous=False):
    """Read the numeric mapping/DPLC tables, without executing assembly."""
    order, blocks, current = [], {}, None
    for raw in path.read_text().splitlines():
        line = raw.split(';')[0].strip()
        ref = re.search(r'dc\.w\s+(\w+)-[.\w]', line)
        if ref:
            order.append(ref[1]); continue
        label = re.match(r'(\w+):', line)
        if label:
            current = bytearray(); blocks[label[1]] = current
        directive = re.search(r'dc\.([bw])\s+(.+)', line)
        if directive and current is not None:
            size = 1 if directive[1] == 'b' else 2
            for value in directive[2].split(','):
                value = value.strip()
                number = int(value[1:],16) if value.startswith('$') else int(value)
                current.extend((number & ((1<<(8*size))-1)).to_bytes(size,'big'))
    if contiguous:
        # A mapping pointer may span an internal label, or point into another
        # frame. Preserve assembled byte continuity for count-based readers.
        joined=b''.join(blocks.values());offsets={};offset=0
        for label,data in blocks.items():offsets[label]=offset;offset+=len(data)
        return [joined[offsets[label]:] for label in order]
    return [bytes(blocks[label]) for label in order]

def sonic_frame(frame=1):
    folder = DATA/'_Objects/Sonic/Data'
    mapping = assembly_frames(folder/'Mappings.asm')[frame]
    dplc = assembly_frames(folder/'DPLCs.asm')[frame]
    raw = (folder/'Art.bin').read_bytes()
    # PPZ data files place EVEN immediately after Art_Sonic. Its last DPLC
    # includes that single zero alignment byte (the file is 69,471 bytes).
    raw += bytes(len(raw)&1)
    tiles = bytearray()
    for i in range(int.from_bytes(dplc[:2],'big')):
        entry = int.from_bytes(dplc[2+i*2:4+i*2],'big')
        start=(entry&4095)*32; length=((entry>>12)+1)*32
        if start+length>len(raw):raise ValueError('Sonic DPLC exceeds assembled art')
        tiles.extend(raw[start:start+length])
    colors=palette((folder/'Palette.bin').read_bytes())
    output=bytearray(64*64*2)
    for i in range(mapping[0]):
        y,size,high,low,x=mapping[1+i*5:6+i*5]
        x=x if x<128 else x-256;y=y if y<128 else y-256
        width=((size>>2)&3)+1;height=(size&3)+1;word=(high<<8)|low
        for py in range(height*8):
            for px in range(width*8):
                sx=width*8-1-px if word&0x800 else px
                sy=height*8-1-py if word&0x1000 else py
                tile=(word&2047)+(sx//8)*height+sy//8
                byte=tiles[tile*32+(sy%8)*4+(sx%8)//2]
                color=(byte>>4) if sx%2==0 else byte&15
                dx,dy=32+x+px,32+y+py
                if color and 0<=dx<64 and 0<=dy<64:
                    offset=(dy*64+dx)*2
                    output[offset:offset+2]=colors[color*2:color*2+2]
    return bytes(output)

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ppz = DATA / 'Palmtree Panic/Data'
    report = []
    for key, era in enumerate(['Present', 'Past', 'Good Future', 'Bad Future']):
        def load(name):
            return (ppz / name).read_bytes()
        parts = [nemesis(load(f'Tiles (Act 1 {era}).nem')),
                 nemesis(load(f'Blocks (Act 1 {era}).nem')),
                 load(f'Chunks (Act 1 {era}).bin'),
                 layout(load(f'Foreground (Act 1 {era}).bin')),
                 layout(load(f'Background (Act 1 {era}).bin')),
                 palette((DATA / '_Objects/Sonic/Data/Palette.bin').read_bytes() + load(f'Palette ({era}).bin'))]
        if len(parts[0]) > 0x10000 or len(parts[1]) % 8 or len(parts[2]) % 512:
            raise ValueError('unexpected stage geometry size')
        if len(parts[5]) != 128:
            raise ValueError('expected 64 palette entries')
        collision = load(f'Collision (Act 1 {era}).bin')
        if len(collision) > 1024:
            raise ValueError('collision index exceeds 1024 blocks')
        collision = collision.ljust(1024, b'\0')
        collision += (DATA / '_Data/Collision Height Map.bin').read_bytes()
        collision += (DATA / '_Data/Collision Width Map.bin').read_bytes()
        collision += (DATA / '_Data/Collision Angles.bin').read_bytes()
        if len(collision) != 1024 + 4096 * 2 + 256:
            raise ValueError('unexpected collision tables')
        (OUT / f'collision{key}.bin').write_bytes(collision)
        chunks = len(parts[2]) // 512
        for chunk in parts[3] + parts[4]:
            if chunk & 127 > chunks:
                raise ValueError('layout refers to missing chunk')
        # Some unused chunks contain diagnostic/padding values. Validate only
        # chunks reachable from the actual foreground/background layouts.
        for chunk in set(parts[3] + parts[4]):
            index = chunk & 127
            if not index:
                continue
            for (block,) in struct.iter_unpack('>H', parts[2][(index-1)*512:index*512]):
                if (block & 1023) * 8 >= len(parts[1]):
                    raise ValueError('used chunk refers to missing block')
        # File header: magic, six offset/length pairs, original start X/Y.
        offset = 56
        header = b'PPZ1'
        for part in parts:
            header += struct.pack('>II', offset, len(part))
            offset += len(part)
        header += load(f'Start Position (Act 1 {era}).bin')[:4]
        assert len(header) == 56
        payload = header + b''.join(parts)
        (OUT / f'ppz{key}.bin').write_bytes(payload)
        report.append({'era': era, 'bytes': len(payload), 'parts': list(map(len, parts)),
                       'sha256': hashlib.sha256(payload).hexdigest()})
    # Original engineering test floor; separate from Sonic CD special-stage art.
    floor = bytes(1 + ((x // 16 + y // 16) & 1) for y in range(256) for x in range(512))
    (OUT / 'floor.bin').write_bytes(floor)
    runs=[]
    for word, in struct.iter_unpack('>H',floor):
        if runs and runs[-1][1]==word and runs[-1][0]<65535:runs[-1][0]+=1
        else:runs.append([1,word])
    (OUT / 'floor.rle').write_bytes(b''.join(struct.pack('>HH',*run) for run in runs))
    (OUT / 'sonic.bin').write_bytes(sonic_frame())
    frames = [1, 0x35, 0x36, 0x37, 0x38, 0x33, 0x34, 0x2d, 0x2e, 0x2f, 0x30, 0x31, 0x4b, 0x4c, 0x4d, 0x4e, 0x5d, 0x6a, 0x32, 0x60, 5]
    motion=b''.join(sonic_frame(f) for f in frames)
    (OUT / 'sonic-motion.bin').write_bytes(motion)
    runs=[]
    for word, in struct.iter_unpack('>H',motion):
        if runs and runs[-1][1]==word and runs[-1][0]<65535:runs[-1][0]+=1
        else:runs.append([1,word])
    (OUT / 'sonic-motion.rle').write_bytes(b''.join(struct.pack('>HH',*run) for run in runs))
    indexed=bytearray()
    for frame in range(21):
        colors=[0];indices=[]
        for word, in struct.iter_unpack('>H',motion[frame*8192:(frame+1)*8192]):
            if word not in colors:colors.append(word)
            indices.append(colors.index(word))
        if len(colors)>16:raise ValueError('Sonic frame exceeds 16-color CLUT')
        indexed.extend(bytes((indices[i]<<4)|indices[i+1] for i in range(0,len(indices),2)))
        indexed.extend(struct.pack('>16H',*(colors+[0]*(16-len(colors)))))
    runs=[]
    for word, in struct.iter_unpack('>H',indexed):
        if runs and runs[-1][1]==word and runs[-1][0]<65535:runs[-1][0]+=1
        else:runs.append([1,word])
    (OUT / 'sonic-motion-indexed.rle').write_bytes(b''.join(struct.pack('>HH',*run) for run in runs))
    (OUT / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
