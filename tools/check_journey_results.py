#!/usr/bin/env python3
"""Source-art checks for a completed natural Good Future zone journey."""
import argparse,hashlib,json
from pathlib import Path
from ppz_journey import ROOT
from hud_pixels import expected as hud_expected,verify as verify_hud
from results_pixels import draw,maps,art,colors,number_art,verify_pixels

def main():
    parser=argparse.ArgumentParser();parser.add_argument('folder',type=Path);args=parser.parse_args()
    folder=args.folder;sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    route=json.loads((folder/'report.json').read_text());final=route['final']
    assert route['passed'] and route['zone_exit'] and final['act']==3 and final['era']==2
    assert route['good_flags']==3 and route['generators']==2 and final['phase']==6
    assert sha(ROOT/'dist/sonic-cd-saturn-prototype.bin')==route['disc_sha256']
    path=folder/'journey-end.ppm';assert sha(path)==route['captures'][path.name]
    raw=path.read_bytes();header,pixels=raw.split(b'255\n',1)
    assert header==b'P6\n330 224\n' and len(pixels)==330*224*3
    hud=verify_hud(raw,final['score'],final['rings'],final['clock'],final['lives'],2,check_rings=final['rings']!=0)
    # Original MapSpr_ResultsGood: SONIC MADE A GOOD / FUTURE IN ZONE 3.
    title=sum(verify_pixels(pixels,draw(maps[index],art,colors,width),width,160,76)
              for index,width in [(10,256),(14,224)])
    # Counter mappings also address runtime number tiles beyond static art.
    # Select source pieces whose base tile belongs to the static label art;
    # the numeric fields are independently checked below.
    pieces=[maps[1][1+n*5:6+n*5] for n in range(maps[1][0])]
    static=[p for p in pieces if ((p[2]<<8|p[3])&2047)*32<len(art)]
    assert len(static)==8
    labels=verify_pixels(pixels,draw(bytes([len(static)])+b''.join(static),art,colors,256),256,112,144)
    digits=0
    for value,count,x,y in [(final['score'],7,184,112),(0,5,200,136),(0,5,200,160)]:
        for n,char in enumerate(str(value).rjust(count)):
            if char!=' ':digits+=verify_pixels(pixels,draw(bytes([1,0,1,0,int(char)*2,252]),number_art,colors,8),8,x+4+n*8,y)
    # Verify the HUD oracle actually rejects an opaque-texel mutation.
    x,y=next(iter(hud_expected(final['score'],final['rings'],final['clock'],final['lives'],2)))
    changed=bytearray(pixels);changed[(y*330+x)*3]^=255
    try:verify_hud(header+b'255\n'+changed,final['score'],final['rings'],final['clock'],final['lives'],2)
    except AssertionError:negative=True
    else:raise AssertionError('HUD mutation was not rejected')
    sources=['tools/check_journey_results.py','tools/hud_pixels.py','tools/results_pixels.py','tools/convert_objects.py','tools/convert_assets.py']
    level=ROOT/'.deps/scddisasm/src/Level'
    for directory in ['_Objects/Results/Data','_Objects/HUD and Points/Data','_Objects/Sonic/Data']:
        sources.extend(str(p.relative_to(ROOT)) for p in (level/directory).iterdir() if p.is_file() and ('Art' in p.name or 'Mapping' in p.name or p.name=='Palette.bin'))
    sources.append('.deps/scddisasm/src/_Include/Main CPU Variables.inc')
    report=dict(passed=True,disc_sha256=route['disc_sha256'],hud_pixels=hud,title_pixels=title,label_pixels=labels,digit_pixels=digits,
        negative_hud_mutation_rejected=negative,source_sha256={name:sha(ROOT/name) for name in sources},
        evidence_sha256={str(path):sha(path),str(folder/'report.json'):sha(folder/'report.json')},
        limits='Opaque source-art texels in the completed Good Future Act 3 HUD/results only; not transparent-background, whole-scene, motion or physical-console acceptance.')
    output=folder/'source-results-report.json';assert not output.exists()
    output.write_text(json.dumps(report,indent=2)+'\n')
    print('Good Future source results:',hud,'HUD;',title,'title;',labels,'labels;',digits,'digits; altered HUD rejected')
if __name__=='__main__':main()
