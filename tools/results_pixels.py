"""Source-derived opaque-pixel checks for Saturn result captures."""
from convert_objects import DATA,draw,assembly_frames,nemesis,palette
colors=palette((DATA/'_Objects/Sonic/Data/Palette.bin').read_bytes())
source=DATA/'_Objects/Results/Data';maps=assembly_frames(source/'Mappings.asm');art=nemesis((source/'Art.nem').read_bytes())
number_art=(DATA/'_Objects/HUD and Points/Data/Art (Numbers).bin').read_bytes()
def verify_pixels(data,texture,width,x,y):
    checked=0
    for py in range(64):
        for px in range(width):
            value=int.from_bytes(texture[(py*width+px)*2:(py*width+px)*2+2],'big')
            if not value:continue
            dx=x-width//2+px+5;dy=y-32+py
            actual=data[(dy*330+dx)*3:(dy*330+dx)*3+3]
            expected=bytes(((value&31)*8,((value>>5)&31)*8,((value>>10)&31)*8))
            assert actual==expected, ('result pixel',dx,dy,actual,expected)
            checked+=1
    return checked
