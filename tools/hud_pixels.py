"""Independent original mapping/tile-memory oracle for the level HUD."""
import re
from convert_objects import DATA, assembly_frames, draw, nemesis, palette
SOURCE=DATA/'_Objects/HUD and Points/Data'
MAPS=assembly_frames(SOURCE/'Mappings (HUD).asm')
NUMBERS=(SOURCE/'Art (Numbers).bin').read_bytes()
COLORS=palette((DATA/'_Objects/Sonic/Data/Palette.bin').read_bytes())
TIME_ZONES=re.findall(r'^TIME_(PAST|PRESENT|FUTURE)\s+rs\.b\s+1',
    (DATA.parent/'_Include/Main CPU Variables.inc').read_text(),re.M)
assert len(TIME_ZONES)==3

def expected(score,rings,ticks,lives,era):
    art=bytearray(64*32)
    base=nemesis((SOURCE/'Art (HUD).nem').read_bytes());art[:len(base)]=base
    def number(tile,value,digits,leading=False):
        for i,c in enumerate(str(value).zfill(digits) if leading else str(value).rjust(digits)):
            art[tile*32+i*64:tile*32+(i+1)*64]=bytes(64) if c==' ' else NUMBERS[int(c)*64:(int(c)+1)*64]
    ticks=min(ticks,35999)
    number(27,score,7);number(41,ticks//3600,1,True)
    number(43,ticks//60%60,2,True);number(47,99 if ticks==35999 else ticks%60*100//60,2,True)
    number(51,rings,3);number(61,min(lives,9),1,True)
    # Level/Main.asm LoadLifeIcon indexes the source's timeZone enum, not our era enum.
    life=(SOURCE/'Art (Life Icon).bin').read_bytes();variant=TIME_ZONES.index(('PRESENT','PAST','FUTURE','FUTURE')[era])
    art[57*32:61*32]=life[variant*128:(variant+1)*128]
    pixels={}
    for mapping,x,y in [(MAPS[0],16,8),(MAPS[1],16,200),(MAPS[3],16,8)]:
        texture=draw(mapping,art,COLORS,256,-32,64)
        for py in range(64):
            for px in range(256):
                v=int.from_bytes(texture[(py*256+px)*2:(py*256+px+1)*2],'big')
                if v:pixels[x+px-128+5,y+py]=bytes(((v&31)*8,((v>>5)&31)*8,((v>>10)&31)*8))
    return pixels

def verify(image,score,rings,ticks,lives,era,check_rings=True):
    header,rgb=image.split(b'255\n',1);assert header==b'P6\n330 224\n'
    pixels=expected(score,rings,ticks,lives,era)
    checked=0
    for (x,y),color in pixels.items():
        if not check_rings and 40<=y<56 and x<61:continue
        assert rgb[(y*330+x)*3:(y*330+x+1)*3]==color,('HUD',x,y,color,rgb[(y*330+x)*3:(y*330+x+1)*3])
        checked+=1
    return checked

if __name__=='__main__':
    import re
    from pathlib import Path
    root=Path(__file__).resolve().parents[1];folder=root/'build/act-qa'
    log=(folder/'results.log').read_text();m=re.search(r'Full Present act: states=(\d+) elapsed=(\d+) score=(\d+).*lives=(\d+)',log)
    rows=(folder/'player-target-trace.txt').read_text().splitlines();rings=int(rows[-1].split()[10],16)>>16
    count=verify((folder/'act-complete.ppm').read_bytes(),int(m[3]),rings,int(m[2]),int(m[4]),0,check_rings=rings!=0)
    print(f'Original gameplay HUD: {count} source pixels verified at completed tally')
