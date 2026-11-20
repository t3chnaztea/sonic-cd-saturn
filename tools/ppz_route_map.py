#!/usr/bin/env python3
"""Local source-terrain diagnostic for planning controller routes, not art QA."""
import argparse,json,re
from PIL import Image,ImageDraw
from terrain_pixels import foreground_pixel,source as terrain_source
from convert_assets import ROOT
def main():
    p=argparse.ArgumentParser();p.add_argument('--era',default='Past',choices=['Present','Past','Good Future','Bad Future'])
    p.add_argument('--act',type=int,choices=[1,2,3],default=1)
    p.add_argument('--left',type=int,default=4608);p.add_argument('--right',type=int,default=9728)
    p.add_argument('--bottom',type=int,default=1024);p.add_argument('--scale',type=int,default=4)
    p.add_argument('--samples');p.add_argument('--out',required=True);a=p.parse_args()
    era=['Present','Past','Good Future','Bad Future'].index(a.era);bit=1<<(1 if era==0 else 0 if era==1 else 2)
    colors=terrain_source(a.era,a.act)[4]
    image=Image.new('RGB',((a.right-a.left)//a.scale,a.bottom//a.scale),(12,18,28));pixels=image.load()
    for y in range(image.height):
        for x in range(image.width):
            source=foreground_pixel(a.era,a.left+x*a.scale,y*a.scale,act=a.act,colors_override=colors)
            if source:pixels[x,y]=tuple(source[1])
    draw=ImageDraw.Draw(image)
    for x in range((a.left+255)//256*256,a.right,256):
        px=(x-a.left)//a.scale;draw.line((px,0,px,image.height),fill=(70,70,70));draw.text((px+2,2),str(x),fill='white')
    for y in range(128,a.bottom,128):draw.text((2,y//a.scale),str(y),fill='white')
    if a.samples:
        samples=json.loads((ROOT/a.samples).read_text());points=[((s['x']-a.left)/a.scale,s['y']/a.scale) for s in samples if s['act']==a.act and s['era']==era and a.left<=s['x']<a.right]
        if len(points)>1:draw.line(points,fill=(255,80,220),width=2)
    placement_file='objects.inc' if a.act==1 else f'objects{a.act}.inc'
    placements=[list(map(int,s.split(','))) for s in re.findall(r'\{([0-9,-]+)\}',(ROOT/'assets/generated'/placement_file).read_text())]
    names={10:'S',33:'P',18:'B',45:'GEN',25:'T'}
    for x,y,kind,sub,flags,bits,secondary in placements:
        if not(bits&bit) or not(a.left<=x<a.right and 0<=y<a.bottom) or kind not in names or kind==25 and sub<8:continue
        px,py=(x-a.left)/a.scale,y/a.scale;draw.ellipse((px-2,py-2,px+2,py+2),fill='cyan')
        draw.text((px+3,py-8),names[kind]+str(sub),fill='white')
    image.save(ROOT/a.out);print(a.out)
if __name__=='__main__':main()
