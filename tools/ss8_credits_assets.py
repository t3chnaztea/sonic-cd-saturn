#!/usr/bin/env python3
"""Special Stage 8 credits screen (Title Screen/Secrets/Special Stage 8 Credits.asm).

cd/SS8CRED.BIN, from the user's disc (SPEEND.MMD): the palette, the Nemesis art,
plane B (Background Mappings (H40) at $E000) and plane A as DrawText leaves it
(Text_Staff with base tile 0, Text_CreditsLeft $2000, Text_CreditsRight $6000;
TEXTSTR codes, .TilesUpper/.TilesLower). Layout: 'S8C1', u16 tile count, 64 palette
words, the tiles (32 bytes each), then planes A and B (64x32 Mega Drive words each).
The disassembly names the data; every byte must be found in SPEEND.MMD.
"""
import hashlib,json,re,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from convert_assets import nemesis
from extract_mmd import disc_files,ISO
from generated_io import write_bytes
from scd_source import SRC as SCD_SRC
SRC=SCD_SRC/'Title Screen/Secrets'
def textstr(text):
    """_Macros.inc TEXTSTR."""
    out=[];i=0
    special={'-':0x25,',':0x26,'.':0x27,'"':0x29,'!':0x2A,'?':0x2B,'x':0x2C}
    while i<len(text):
        c=text[i]
        if c=="'":
            if i+1<len(text) and text[i+1]=="'":out.append(0x29);i+=1
            else:out.append(0x28)
        elif c in special:out.append(special[c])
        elif '0'<=c<='9':out.append(ord(c)-ord('0')+1)
        elif 'A'<=c<='Z':out.append(ord(c)-ord('A')+0xB)
        elif 'a'<=c<='z':out.append(ord(c)-ord('a')+0xB)
        else:out.append(0)
        i+=1
    return out
def main():
    asm=(SRC/'Special Stage 8 Credits.asm').read_text()
    def table(label):
        body=asm.split(f'\n.{label}:',1)[1].split('\n\n',1)[0]
        return [int(v.replace('$','0x'),16) for v in re.findall(r'dc\.b\s+(\$[0-9A-Fa-f]+)',body)]
    upper,lower=table('TilesUpper'),table('TilesLower');assert len(upper)==len(lower)==45
    strings={m[1]:m[2] for m in re.finditer(r'(TextDat_\w+):\s*\n\s*TEXTSTR\s+"([^"]*)"',asm)}
    lists={m[1]:re.findall(r'TEXTPTR\s+(\w+),\s*(\d+),\s*(\d+)',m[2]) for m in re.finditer(r'(Text_\w+):\s*\n\s*TEXTSTART\n(.*?)TEXTEND',asm,re.S)}
    disc=disc_files(ISO.read_bytes())['SPEEND.MMD']
    def from_disc(name):
        data=(SRC/'Data'/name).read_bytes();assert disc.find(data)>=0,f'{name} not in SPEEND.MMD';return data
    palette=from_disc('Palette.bin');art=nemesis(from_disc('Art.nem'));bg=from_disc('Background Mappings (H40).bin')
    assert len(palette)==128 and len(art)%32==0 and len(bg)==40*28*2
    plane_a=[0]*2048;plane_b=[0]*2048
    for y in range(28):
        for x in range(40):plane_b[y*64+x]=struct.unpack_from('>H',bg,(y*40+x)*2)[0]
    # Start: Text_Staff base 0, Text_CreditsLeft $2000, Text_CreditsRight $6000.
    for name,base in (('Text_Staff',0),('Text_CreditsLeft',0x2000),('Text_CreditsRight',0x6000)):
        for ptr,x,y in lists[name]:
            x,y=int(x),int(y)
            for c in textstr(strings[ptr]):
                plane_a[y*64+x]=(upper[c]+base)&0xffff;plane_a[(y+1)*64+x]=(lower[c]+base)&0xffff;x+=1
    blob=b'S8C1'+struct.pack('>H',len(art)//32)+palette+art+struct.pack('>2048H',*plane_a)+struct.pack('>2048H',*plane_b)
    write_bytes(ROOT/'cd/SS8CRED.BIN',blob+bytes(-len(blob)%2048))
    print(json.dumps({'bytes':len(blob),'tiles':len(art)//32,'sha256':hashlib.sha256(blob).hexdigest()[:12],
        'texts':sum(len(v) for v in lists.values())}))
if __name__=='__main__':main()
