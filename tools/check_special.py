#!/usr/bin/env python3
"""Check target trace, texture readback and displayed pixels against Sega CD."""
import hashlib,json,re,struct
from special_assets import ROOT,parts,sine_table
from special_reference import Reference

def fnv(data):
    h=2166136261
    for byte in data:h=((h^byte)*16777619)&0xffffffff
    return h

def main():
    folder=ROOT/'build/special-qa';log=(folder/'results.log').read_text()
    rows=re.findall(r'Special snapshot: (.+)',log)
    assert len(rows)==32
    assert re.search(r'Special inspection: captures=32 resumed_sequence=\d+',log)
    assert 'nested_returns=2' in log
    live=[list(map(int,row.split())) for row in re.findall(r'Special live animation: (.+)',log)]
    assert len(live)==8 and [row[0] for row in live]==list(range(1,9))
    assert all(row[1]>=5 and row[2]>=3 and row[3]<=120 for row in live)
    from check_special_contacts import check as check_contacts
    visuals={};contacts=check_contacts(log,visuals)
    effect_data=(ROOT/'assets/generated/special-effects.bin').read_bytes()
    effect_length,_,_,_,_,_,_,effect_palette,effect_texture=struct.unpack_from('>9I',effect_data,4)
    observed=list(map(int,re.search(r'Special effect asset:(.+)',log)[1].split()))
    assert observed==[fnv((ROOT/'cd/SFX.BIN').read_bytes()),fnv(effect_data[effect_texture:effect_length]),fnv(effect_data[effect_palette:effect_palette+128])],('effect CD/VRAM readback',observed)
    ufo_data=(ROOT/'assets/generated/special-ufo-art.bin').read_bytes();ufo_length,*_,ufo_texture=struct.unpack_from('>9I',ufo_data,4)
    observed=list(map(int,re.search(r'Special ufo asset:(.+)',log)[1].split()))
    assert observed==[fnv((ROOT/'cd/UFX.BIN').read_bytes()),fnv(ufo_data[ufo_texture:ufo_length]),fnv((ROOT/'cd/UFP.BIN').read_bytes())],('UFO CD/VRAM/path readback',observed)
    reference=Reference();table=sine_table();captures=[]
    def sine(a):return (-1 if a&256 else 1)*table[(a&127)^(127 if a&128 else 0)]
    for row in rows:
        stage,capture,*words=map(int,row.split());assert len(words)==24
        assert words[21]>0 and words[21]==words[22] and words[23]==1,('slave completion',stage,capture)
        components=parts(stage);camera=tuple(words[3:6])+ (128,words[6])
        stamp_map=components[1]
        if capture==3:
            reference.begin_animation(components)
            for _ in range(live[stage-1][1]):stamp_map,_=reference.animate()
        trace=reference.trace(camera,sine);pixels=reference.render(components[0],stamp_map,trace)
        assert words[10]==fnv(trace),('SH-2 projection',stage,capture)
        assert words[11]==fnv(pixels),('SH-2 pixels',stage,capture)
        packed=bytes((a<<4)|b for a,b in zip(pixels[::2],pixels[1::2]))
        assert words[13]==fnv(packed),('VDP1 texture readback',stage,capture)
        assert words[12]==fnv((ROOT/f'cd/SP{stage}.BIN').read_bytes()),('CD data readback',stage)
        colors=struct.unpack('>32H',components[3]);image=folder/f'special-{stage}-{capture}.ppm'
        header,raw=image.read_bytes().split(b'255\n',1);assert header==b'P6\n330 224\n'
        for y in range(96):
            for x in range(256):
                index=pixels[y*256+x];c=colors[index] if index else 0
                expected=bytes(((c&31)*8,((c>>5)&31)*8,((c>>10)&31)*8))
                pos=((y+128)*330+x+37)*3
                assert raw[pos:pos+3]==expected,('displayed source pixel',stage,capture,x,y,raw[pos:pos+3],expected)
        captures.append({'stage':stage,'capture':capture,'camera':camera,'master_rows_ticks':words[20]-words[17],'slave_generation':words[21],'frt_divisor':128,'frt_ticks':words[8],'projection_ticks':words[17],'render_ticks':words[18]-words[17],'upload_ticks':words[8]-words[18],'previous_ccr':words[16],'render_vblanks':words[9],'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest()})
    fixtures=json.loads((ROOT/'build/special-reference/fixtures.json').read_text())
    fixtures+=json.loads((ROOT/'build/special-reference/animation-fixtures.json').read_text())
    fixtures+=json.loads((ROOT/'build/special-reference/air-fixtures.json').read_text())
    sprite_fixtures=json.loads((ROOT/'build/special-reference/sprite-fixtures.json').read_text())
    base=next(f for f in fixtures if f['stage']==1 and f['camera']==[1344,1312,352,128,128])
    fixtures += [base]*len(sprite_fixtures)
    benchmark=[list(map(int,row.split())) for row in re.findall(r'Special benchmark:(.+)',log)]
    assert len(benchmark)==len(fixtures)==1632
    for n,(observed,fixture) in enumerate(zip(benchmark,fixtures)):
        sequence,stage,x,y,z,yaw,trace,pixels,texture,ticks,render,error,fan,hazard,delay,map_hash,pose,flip,sonic_texture,sonic_xy=observed
        assert sequence==n+1 and not error
        sf=sprite_fixtures[n-1328] if n>=1328 else None
        assert [pose,flip,sonic_texture,sonic_xy]==([sf['pose'],sf['flip'],sf['texture'],sf['xy']] if sf else [0xffffffff,0,0,0]),('SH-2 Sonic pose/VDP1',n)
        assert [stage,x,y,z,128,yaw]==[fixture['stage']]+fixture['camera']
        assert [trace,pixels,texture]==[fixture['trace'],fixture['pixels'],fixture['texture']],('target benchmark oracle',n)
        assert [fan,hazard,delay]==fixture.get('animation',[0,0,0]),('target animation state',n)
        assert map_hash==fixture.get('map',fnv(parts(stage)[1])),('target animated map',n)
    motion=json.loads((ROOT/'build/special-reference/player-report.json').read_text())
    assert list(map(int,re.search(r'Special motion probe: (.+)',log)[1].split()))==[motion['target_probe_hash'],motion['target_probe_states']]
    from special_sprite_reference import SpriteReference
    from convert_assets import palette,nemesis
    from special_assets import SOURCE
    from special_sonic_assets import original_art
    # One original VRAM image: Sonic tiles come from each frame's LoadArt copy.
    vram=bytearray(65536)
    for art_name,base in [('Time Stone',0x424),('UFO',0x440),('Splash',0x582),('Shadow',0x6dc),('Item',0x78f),('Explosion',0x7ae)]:
        raw=nemesis((SOURCE/f'Objects/{art_name}/Data/Art.nem').read_bytes());assert not any(vram[base*32:base*32+len(raw)]);vram[base*32:base*32+len(raw)]=raw
    sonic_art=original_art()
    def paint(sat,owner=None):
        canvas=bytearray(320*224)
        for sy,size,link,tile,sx in struct.iter_unpack('>HBBHH',sat):
            w=((size>>2)&3)+1;h=(size&3)+1;index=tile&2047;bank=((tile>>13)&3)<<4
            sonic=0x5e0<=index<0x5f8;data,first=(sonic_art[visual['sonic_art']],index-0x5e0) if sonic else (vram,index)
            assert (first+w*h)*32<=len(data)
            for tx in range(w):
                for ty in range(h):
                    offset=(first+tx*h+ty)*32
                    for y in range(8):
                        for x in range(8):
                            u=tx*8+x;v=ty*8+y
                            if tile&0x800:u=w*8-1-u
                            if tile&0x1000:v=h*8-1-v
                            dx=sx-96+u;dy=sy-128+v
                            if 32<=dx<288 and 0<=dy<224 and not canvas[dy*320+dx]:
                                value=(data[offset+y*4+x//2]>>(0 if x&1 else 4))&15
                                if value:
                                    canvas[dy*320+dx]=value|bank
                                    if owner is not None and sonic:owner[dy*320+dx]=1
        return canvas
    sr=SpriteReference();sonic_captures=[];effect_captures=[];ufo_captures=[];visible_effects=set();visible_ufo=set()
    sonic_rows=re.findall(r'Special Sonic snapshot: (.+)',log);assert len(sonic_rows)==3
    effect_rows=re.findall(r'Special effect snapshot: (.+)',log);assert len(effect_rows)==8
    ufo_rows=re.findall(r'Special UFO snapshot: (.+)',log);assert len(ufo_rows)==4
    colors64=struct.unpack('>64H',palette((SOURCE/'Data/Palette.bin').read_bytes()))
    for kind,row in [('sonic',r) for r in sonic_rows]+[('effect',r) for r in effect_rows]+[('ufo',r) for r in ufo_rows]:
        values=list(map(int,row.split()))
        if kind=='ufo':fixture,capture,values=values[0],values[1],values[2:];name=f'special-ufo-{fixture}-{capture}';resets=11+fixture
        else:capture,values=values[0],values[1:];name=f'special-{kind}-{capture}';resets=1 if kind=='sonic' else capture+2
        assert len(values)==64
        actor=values[:32];floor=values[32:]
        assert actor[0]==0x534e4943 and actor[1]==1 and actor[30]==1 and actor[2]>0
        if kind=='sonic' and capture==0:assert actor[14]==0 and actor[28]&4,('left steering capture',actor[14],actor[28])
        if kind=='sonic' and capture==1:assert actor[14]==9 and actor[28]&8,('right steering capture',actor[14],actor[28])
        if kind=='sonic' and capture==2:assert actor[12]&128 and actor[13]==2 and actor[15]==6 and actor[6]<(344<<16),('jump capture must be airborne',actor[12:16],actor[6])
        assert actor[27]==fnv((ROOT/'cd/SSONIC.BIN').read_bytes())
        sprite=dict(zip(['tilt','animation','frame','time','time_copy','art'],actor[14:20]))
        source_sprite,_,sat=sr.run('draw',sprite,actor[12]|2,actor[9]);assert source_sprite==sprite
        visual=visuals[(resets,actor[2])];assert visual['sonic_art']==actor[19],('Sonic art index',name)
        components=parts(floor[2]);reference.begin_animation(components);stamp_map=components[1]
        for _ in range(floor[24]):stamp_map,_=reference.animate()
        camera=tuple(floor[3:6])+(128,floor[6]);trace=reference.trace(camera,sine);pixels=reference.render(components[0],stamp_map,trace)
        assert [floor[10],floor[11]]==[fnv(trace),fnv(pixels)]
        colors=struct.unpack('>32H',components[3])
        image=folder/f'{name}.ppm';header,raw=image.read_bytes().split(b'255\n',1);assert header==b'P6\n330 224\n'
        owner=bytearray(320*224);canvas=paint(visual['sat'],owner);ids=set()
        for address,before,after,data in visual['log']:
            if after>before and any(paint(visual['sat'][before*8:after*8])[64*320:]):ids.add(data[0])
        (visible_effects if kind=='effect' else visible_ufo if kind=='ufo' else set()).update(ids)
        visible=0
        for y in range(64,224):
            for x in range(320):
                color=0
                if y>=128 and 32<=x<288:
                    index=pixels[(y-128)*256+x-32];color=colors[index] if index else 0
                if canvas[y*320+x]:color=colors64[canvas[y*320+x]];visible+=owner[y*320+x]
                expected=bytes(((color&31)*8,((color>>5)&31)*8,((color>>10)&31)*8));pos=(y*330+x+5)*3
                assert raw[pos:pos+3]==expected,('original SAT/floor composite',name,x,y,raw[pos:pos+3],expected)
        entry={'capture':capture,'updates':actor[2],'last_update_vblanks':actor[31],'speed':actor[9],'flags':actor[12],'animation':actor[15],'frame':actor[16],'camera':camera,'visible_sonic_pixels':visible,'sat_entries':len(visual['sat'])//8,'visible_object_ids':sorted(ids),'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest()}
        if kind=='ufo':entry['fixture']=fixture
        (sonic_captures if kind=='sonic' else effect_captures if kind=='effect' else ufo_captures).append(entry)
    assert {7,8,13}<=visible_effects,('missing visible effects',visible_effects)
    assert {2,4,5,6,12}<=visible_ufo,('missing visible UFO objects',visible_ufo)
    maximum=max(row[9] for row in benchmark)
    report={'contact_replay':contacts,'motion_probe_states':motion['target_probe_states'],'motion_probe_hash':motion['target_probe_hash'],'sonic_captures':sonic_captures,'effect_captures':effect_captures,'visible_effect_ids':sorted(visible_effects),'ufo_captures':ufo_captures,'visible_ufo_object_ids':sorted(visible_ufo),'effect_asset_readback_verified':True,'ufo_asset_readback_verified':True,'sonic_composite_pixels':15*320*160,'sonic_pose_cases':304,'benchmark_cases':1632,'air_benchmark_cases':240,'animated_benchmark_cases':192,'live_animation_cadence':live,'live_source_cadence_met':all(row[2]==3 and row[3]==3 for row in live),'benchmark_max_frt_ticks':maximum,'benchmark_source_pixels':1632*256*96,'source_update_vblanks':3,'source_updates_per_second':20,'source_floor_fixture_budget_met':maximum<=10400,'passed':True,'disc_sha256':hashlib.sha256((ROOT/'dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest(),'captures':captures,'source_pixels_compared':len(captures)*256*96,'cd_asset_hashes_verified':8,'projection_texture_readback_verified':True,'return_to_gameplay_and_music':True,'nested_diagnostic_returns':2,'hardware_tested':False,'optional_60hz_floor_budget_met':all(c['frt_ticks']<=3500 for c in captures),'render_budget_note':'The source special stage advances every 3 NTSC VBlanks (20 Hz). Conservatively allow 10400 FRT ticks at divisor 128 for floor-only fixtures. The optional_60hz_floor_budget_met field records the optional 60 Hz rendering target; neither flag proves complete special-stage gameplay performance.','limits':'Inspection route only. Sonic motion/art view is interactive; stamp contacts, splash state and timer are active. Splash/dust/lost-ring effects, UFOs, shadows, items, explosions and the time-stone win sequence are active. Special backgrounds/sound/HUD/results and big-ring entry remain pending.'}
    (ROOT/'dist/special-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Special-stage floor: 32 source-pixel captures, all CD packs and SH-2/VDP1 hashes, gameplay/music return PASS')
if __name__=='__main__':main()
