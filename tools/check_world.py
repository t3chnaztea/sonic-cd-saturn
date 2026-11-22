#!/usr/bin/env python3
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'build/world-qa'
log=(folder/'results.log').read_text();assert 'Target world probe: 1; cutscene: 1; arrival: 1;' in log
assert re.search(r'Amy controller: hold=\d+ jump=1 grabs=[1-9]\d* hearts=[1-9]\d*',log)
assert 'Original finish controller routes: present=1 good=1 score=52300 music=6 replay=1' in log
assert 'Ramp backdrop/display: d8000003' in log
assert 'Monitor controller routes: five grants, power-up music and expiration passed' in log
assert 'Original platform controller routes: PASS' in log
assert 'Tag and scenery routes: two speed tags, eight era-art scenes and Sonic overlap passed' in log
assert 'Projector and animal controller routes: timed destruction, release and future presence passed' in log
assert 'Door and moving-spring routes: five fixtures, both frames and activation passed' in log
assert 'Spinning disc controller routes: all six poses, two jumps and natural release passed' in log
assert 'Tunnel controller routes: four eras, original loaded paths, visibility flags and exact exits passed' in log
assert 'Collapsing platform controller routes: four eras, intact/break/fall and rider release passed' in log
assert 'Original wall controller routes: past=1 present=1' in log
assert re.search(r'Checkpoint controller route: activation=[1-9]\d* death=[1-9]\d* respawn=[1-9]\d*',log)
assert 'Ramp route: entry=' in log and 'scroll=1' in log
captures={}
for name in ['enemy-anton','enemy-patabata','enemy-mosqui','enemy-tamabboh','enemy-tagataga','travel-cutscene','travel-arrival','ramp-entry','ramp-climb','ramp-exit','float-past','float-jump','platform-ride','platform-carried','platform-jump','float-future','float-present','float-present-jump','float-vanished','checkpoint-activate','checkpoint-death','checkpoint-respawn','checkpoint-restored','wall-past-solid','wall-past-break','wall-past-passed','wall-present-solid','wall-present-break','wall-present-passed','finish-present-sign','finish-present-spin','finish-present-tally','finish-present-done','finish-good-sign','finish-good-spin','finish-good-tally','finish-good-done','finish-replay']+[f'monitor-{n}-{state}' for n in range(5) for state in ['intact','granted']]+['monitor-3-expired','monitor-4-expired','monitor-shield-visible']+[f'collapse-{n}-{state}' for n in range(4) for state in ['intact','break','fallen']]+[f'tunnel-{n}-{state}' for n in range(4) for state in ['moving','exit']]+[f'disc-{n}-pose-{pose}' for n in range(3) for pose in range(6)]+[f'disc-{n}-release' for n in range(3)]+[f'door-spring-{n}-frame-{pose}' for n in range(5) for pose in range(2)]+[f'tag-scenery-{n}' for n in range(11)]+[f'projector-animal-{n}' for n in range(6)]+[f'amy-hold-{n}' for n in range(3)]:
    raw=(folder/f'{name}.ppm').read_bytes();header,data=raw.split(b'255\n',1)
    assert header==b'P6\n330 224\n' and len(data)==330*224*3
    if name=='tag-scenery-1':
        from terrain_pixels import verify_priority_foreground
        cameras=re.findall(r'Tag presentation: route=1 lag=(\d+) camera=(-?\d+),(-?\d+)',log);assert len(cameras)==3
        matches=set();failures=[]
        for lag,cx,cy in cameras:
            try:checked=verify_priority_foreground(data,'Present',int(cx),int(cy));matches.add((int(cx),int(cy),checked))
            except AssertionError as error:failures.append((lag,str(error)))
        assert len(matches)==1,('exact source terrain must match one recorded presentation camera',matches,failures)
        print('Vertical tag source-priority terrain pixels:',matches.pop())
    else:assert len(set(data[i:i+3] for i in range(0,len(data),3)))>=16,(name,'insufficient scene colors')
    if name in ('ramp-climb','ramp-exit'):
        scene=b''.join(data[(y*330+5)*3:(y*330+325)*3] for y in range(44,180))
        sky=sum(scene[i:i+3]==bytes((0,0,176)) for i in range(0,len(scene),3))
        assert sky>15000, (name,'original palette-32 blue sky missing',sky)
    captures[name]=hashlib.sha256(raw).hexdigest()
# Compare all opaque source result/title/number pixels to final target captures.
# Beetle adds a five-pixel border; its 5-bit RGB channels expand by left shift.
from results_pixels import draw,maps,art,colors,number_art,verify_pixels
from monitor_pixels import source_monitor,verify_monitor_overlap
monitor_pixel_counts={}
for route in range(5):
    records={int(t):(int(art),int(x),int(y)) for t,art,x,y in re.findall(rf'Monitor pixels: route={route} tick=(\d+) art=(\d+) x=(-?\d+) y=(-?\d+)',log)}
    assert set(records)==set(range(58,80)),('missing monitor motion records',route)
    sonic={int(t):list(map(int,words.split())) for t,words in re.findall(rf'^Monitor Sonic: route={route} tick=(\d+) ((?:\d+ ?)+)$',log,re.M)}
    assert set(sonic)==set(records),('missing monitor/Sonic snapshots',route)
    seen=set();checked=covered=0
    for tick in range(60,80):
        path=folder/f'monitor-{route}-pose-{tick}.ppm'
        raw=path.read_bytes();header,data=raw.split(b'255\n',1)
        assert header==b'P6\n330 224\n' and len(data)==330*224*3
        matches=set()
        for lag in range(3):
            state,x,y=records[tick-lag]
            assert state>>8==25 and state&255 in (route,8,9,10),('monitor frame',route,tick,state)
            frame=state&255
            try:count,overlap=verify_monitor_overlap(data,frame,x,y,sonic[tick-lag])
            except AssertionError:continue
            matches.add((frame,x,y,count,overlap))
        assert len(matches)==1,('monitor must match exactly one recently submitted source composition',route,tick,matches)
        frame,x,y,count,overlap=matches.pop();assert count>300
        seen.add(frame);checked+=count;covered+=overlap
        captures[path.stem]=hashlib.sha256(raw).hexdigest()
    assert route in seen and seen.intersection({8,9}),('icon and static animation coverage',route,seen)
    assert covered>0,('missing Sonic/monitor overlap coverage',route)
    monitor_pixel_counts[str(route)]={'source_pixels':checked,'sonic_overlap_pixels':covered,'frames':sorted(seen)}
print('Monitor source pixels:',monitor_pixel_counts)
for good in [False,True]:
    name='finish-good-done' if good else 'finish-present-done'
    data=(folder/f'{name}.ppm').read_bytes().split(b'255\n',1)[1]
    verified=0
    for index,width in ([(10,256),(12,224)] if good else [(0,144),(2,208)]):
        verified+=verify_pixels(data,draw(maps[index],art,colors,width),width,160,76)
    label_map=bytes([8])+maps[1][1:41]
    verified+=verify_pixels(data,draw(label_map,art,colors,256),256,112,144)
    for value,digits,x,y in [(52300,7,184,112),(0,5,200,136),(0,5,200,160)]:
        text=str(value).rjust(digits)
        for n,c in enumerate(text):
            if c==' ':continue
            texture=draw(bytes([1,0,1,0,int(c)*2,252]),number_art,colors,8)
            verified+=verify_pixels(data,texture,8,x+4+n*8,y)
    assert verified>3000
    # The ring bonus has finished by this sample, while the time bonus remains.
    tally=(folder/('finish-good-tally.ppm' if good else 'finish-present-tally.ppm')).read_bytes().split(b'255\n',1)[1]
    zero=draw(bytes([1,0,1,0,0,252]),number_art,colors,8)
    verify_pixels(tally,zero,8,236,136)
    # Time bonus is in the forty-thousands after sixty tally frames.
    four=draw(bytes([1,0,1,0,8,252]),number_art,colors,8)
    verify_pixels(tally,four,8,204,160)
# Visible tunnel paths explicitly request Sonic's rolling animation even
# when the collision flags were not already rolling at entry.
from convert_assets import sonic_frame
# The original camera frames Sonic where scroll_h/scroll_v put him. Each capture
# logs (tools/emulator_test.c) Sonic's screen position at the latest gameplay
# update and at the one before it; the picture shows the previous update's
# sprite list (VDP1 draws one update behind the mailbox), so the source pixels
# must match exactly at that drawn position.
shot_screen={n:(int(x),int(y)) for n,x,y in re.findall(r'Screen Sonic: (\S+) screen=-?\d+,-?\d+ drawn=(-?\d+),(-?\d+)',log)}
def sonic_at(data,name,frame):
    try:return verify_pixels(data,sonic_frame(frame),64,*shot_screen[name])
    except AssertionError:return 0
for route in [2,3]:
    data=(folder/f'tunnel-{route}-moving.ppm').read_bytes().split(b'255\n',1)[1]
    matched=any(sonic_at(data,f'tunnel-{route}-moving',frame)>100 for frame in range(0x2d,0x32))
    assert matched, ('visible tunnel must use original rolling pixels',route)
# Each of the six frozen rotating poses must appear as original source pixels.
for route in range(3):
    for pose,frame in enumerate([0x1a,0x1b,0x1c,0x1f,0x1d,0x1e]):
        data=(folder/f'disc-{route}-pose-{pose}.ppm').read_bytes().split(b'255\n',1)[1]
        assert sonic_at(data,f'disc-{route}-pose-{pose}',frame)>100,('disc pose pixels',route,pose)
# Natural support loss retains the disc pose on the release update, then
# ObjSonic_MdAir selects walking/falling on the NEXT update. This picture is
# three fields after release: original animation 0 still displays mapping 53
# (its first walking frame) and has advanced its script cursor to 1.
release_pose=int(re.search(r'Disc release pose: route=2 pose=(\d+)',log)[1])
assert release_pose==1
release=(folder/'disc-2-release.ppm').read_bytes().split(b'255\n',1)[1]
assert sonic_at(release,'disc-2-release',53)>100,'disc release pixels'
# The door must remain visible at original high-priority foreground locations;
# every opaque source pixel is required, including the open flap's tall extent.
from convert_objects import DATA,assembly_frames,nemesis,palette
common=palette((DATA/'_Objects/Sonic/Data/Palette.bin').read_bytes())
door_art=nemesis((DATA/'Palmtree Panic/Objects/Tunnel Door/Data/Art.nem').read_bytes())
for route in range(5):
    path=DATA/'_Objects/Spin Tunnel/Data/Mappings (Door).asm' if route<2 else DATA/'Palmtree Panic/Objects/Tunnel Door/Data/Mappings.asm' if route==2 else DATA/'_Objects/Spring/Data/Mappings (Wheel).asm'
    source_art=door_art if route<3 else nemesis((DATA/'_Objects/Spring/Data/Art (Wheel).nem').read_bytes())
    for pose,mapping in enumerate(assembly_frames(path)):
        match=re.search(rf'Door/spring pixels: route={route} pose={pose} x=(-?\d+) y=(-?\d+)',log);assert match
        x,y=map(int,match.groups());width=56 if route<2 else 88 if route==2 else 16
        canvas,shift=(96,16) if route<2 else (64,0)
        texture=draw(mapping,source_art,common,width,shift,canvas)
        data=(folder/f'door-spring-{route}-frame-{pose}.ppm').read_bytes().split(b'255\n',1)[1]
        checked=0
        for py in range(canvas):
            for px in range(width):
                value=int.from_bytes(texture[(py*width+px)*2:(py*width+px)*2+2],'big')
                if not value:continue
                dx=x-width//2+px+5;dy=y-32-shift+py
                assert 5<=dx<325 and 0<=dy<224,('door/spring outside capture',route,pose,dx,dy)
                actual=data[(dy*330+dx)*3:(dy*330+dx)*3+3]
                expected=bytes(((value&31)*8,((value>>5)&31)*8,((value>>10)&31)*8))
                assert actual==expected,('door/spring pixel',route,pose,dx,dy,actual,expected)
                checked+=1
        assert checked>32
# Verify every era-specific scenery/shadow pixel. The final fixture overlaps
# Sonic deliberately: all his source pixels must win, and exposed shadow
# pixels must remain intact underneath him.
scene_cases=[(2,'Present','Log Shadow','Art.nem',0),(3,'Past','Log Shadow','Art.nem',0),(4,'Good Future','Log Shadow','Art (Withered).nem',1),(5,'Bad Future','Log Shadow','Art (Withered).nem',1),(6,'Past','Scenery','Art (Past).nem',0),(7,'Past','Scenery','Art (Past).nem',1),(8,'Good Future','Scenery','Art (Future).nem',2),(9,'Bad Future','Scenery','Art (Future).nem',2),(10,'Present','Log Shadow','Art.nem',0)]
from terrain_pixels import foreground_pixel
scene_positions={2:(5448,136),3:(5440,136),4:(5448,136),5:(5448,136),6:(5432,85),7:(5540,92),8:(5491,88),9:(5491,88),10:(500,400)}
for route,era,folder_name,filename,pose in scene_cases:
    match=re.search(rf'Scenery pixels: route={route} x=(-?\d+) y=(-?\d+) player=(-?\d+),(-?\d+)',log);assert match
    x,y,sx,sy=map(int,match.groups());path=DATA/f'Palmtree Panic/Objects/{folder_name}/Data'
    bank=palette((DATA/f'Palmtree Panic/Data/Palette ({era}).bin').read_bytes()[32:64])
    texture=draw(assembly_frames(path/'Mappings.asm')[pose],nemesis((path/filename).read_bytes()),bank,32)
    data=(folder/f'tag-scenery-{route}.ppm').read_bytes().split(b'255\n',1)[1]
    sonic=sonic_frame(1);checked=overlap=covered=0
    if route==10:
        snapshot=list(map(int,re.search(r'^Scenery Sonic: ((?:\d+ ?)+)$',log,re.M)[1].split()))
        assert len(snapshot)==18 and snapshot[0]==0x534F4E56 and not snapshot[13]
        # This is a neutral airborne fixture, not the old renderer's forced
        # idle image. Original animation 0 selects its walking-angle artwork.
        assert snapshot[10]>>24==0 and snapshot[3] in range(51,57) and snapshot[4]&3==0
        sonic=sonic_frame(snapshot[3]);assert verify_pixels(data,sonic,64,sx,sy)>100
    for py in range(64):
        for px in range(32):
            value=int.from_bytes(texture[(py*32+px)*2:(py*32+px)*2+2],'big')
            if not value:continue
            dx=x-16+px+5;dy=y-32+py
            wx,wy=scene_positions[route];foreground=foreground_pixel(era,wx-16+px,wy-32+py)
            spx,spy=dx-5-sx+32,dy-sy+32
            if not (foreground and foreground[0]) and route==10 and 0<=spx<64 and 0<=spy<64 and any(sonic[(spy*64+spx)*2:(spy*64+spx)*2+2]):overlap+=1;continue
            assert 5<=dx<325 and 0<=dy<224,('scenery bounds',route,dx,dy)
            actual=data[(dy*330+dx)*3:(dy*330+dx)*3+3]
            expected=foreground[1] if foreground and foreground[0] else bytes(((value&31)*8,((value>>5)&31)*8,((value>>10)&31)*8))
            if foreground and foreground[0]:covered+=1
            assert actual==expected,('scenery pixel',route,dx,dy,actual,expected)
            checked+=1
    assert checked-covered>32
    print('Scenery composition:',route,'sprite pixels',checked-covered,'foreground pixels',covered,'Sonic overlap',overlap)
    if route==10:assert overlap>100,('priority fixture must overlap',overlap)
from projector_pixels import verify as verify_projector_pixels
projector_pixel_counts=verify_projector_pixels(folder,log)
assert captures['travel-cutscene']!=captures['travel-arrival']
from amy_pixels import verify as verify_amy
amy_pixel_counts=verify_amy(folder,log)
report={'amy_routes':'Original-position Amy, controller hold through idle animation, fresh jump release and source sprite/heart pixels', 'amy_pixel_counts':amy_pixel_counts,'disc_sha256':hashlib.sha256((ROOT/'dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest(),'target_semantic_probe':'pass','gameplay_triggered_travel':'past to present, controller holds right after isolated sign fixture','ramp_route':'present spawn, controller holds right; ramp entry, scrolling and exit verified','original_platform_routes':'past/present/future floating blocks and Present moving platform; rider, movement and jump-off verified','checkpoint_route':'controller activates original checkpoint position, hits a seeded Anton, respawns with two lives and exact saved position/time', 'wall_routes':'ordinary side stop, charge/rolling attack and traversal of three original Past walls and two Present walls', 'finish_routes':'Present and Good Future original signs, frozen clock, source phase timing, 52300 bonus points, extra life, audible nonrepeating results track and Start replay', 'collapse_routes':'Four isolated original-position era fixtures: intact artwork, source piece counts, timed falls and rider release', 'disc_routes':'Three original-position controller fixtures with nearby objects: all six poses, two jumps and natural radius-growth release', 'tunnel_routes':'Four original-position entry fixtures with ordinary placement streaming: control/visibility, exact segment probe and exit coordinates; hole reveal is covered by source pixel and host lifecycle tests', 'tag_scenery_routes':'Two source speed activations, eight era-specific art/palette captures and a Sonic/shadow overlap checked against source pixels', 'door_spring_routes':'Five source-position fixtures: both original frames, flap opening, vertical-door approach and attached spring launch; exact opaque source pixels', 'monitor_routes':'Five controller jump/break/item grants, invincibility and shoes music once, timer expiration and Past music restoration', 'emulator_frames':int(re.search(r'arrival: 1; frames: (\d+)',log)[1]),'captures':captures,'projector_routes':'Original-position controller jump, 12 timed explosions, completion 101 ticks after contact, two nearby animals released; original-position Good Future flight/ground movement and Bad Future suppression', 'projector_pixel_counts':projector_pixel_counts,'hardware_tested':False,'limits':'Fixtures do not prove a complete act from spawn or independent original-console equivalence.'}
from check_object_vram import verify as verify_object_vram
report['object_vram']=verify_object_vram(folder/'monitor-vdp1.bin')
amy_sources=[ROOT/'tools'/name for name in ['amy_pixels.py','sprite_composition.py','terrain_pixels.py','convert_assets.py','projector_pixels.py']]
amy_sources += [DATA/'Palmtree Panic/Objects/Amy Rose/Data'/name for name in ['Mappings.asm','Art.nem','Palette.bin']]
amy_sources += [DATA/'_Objects/Sonic/Data'/name for name in ['Mappings.asm','DPLCs.asm','Art.bin','Palette.bin']]
report['amy_verification_sources']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in amy_sources}
composition_path=ROOT/'build/sprite-composition-report.json'
composition=json.loads(composition_path.read_text())
assert composition['passed'] and composition['compositions']==403
assert composition['object_frames']==394 and composition['additional_corrected_pixels']==5032
for name,expected in (composition['source_sha256']|composition['source_input_sha256']).items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,('Stale source composition evidence',name)
for name,expected in composition['artifact_sha256'].items():
    assert hashlib.sha256((ROOT/'assets/generated'/name).read_bytes()).hexdigest()==expected,('Stale composed asset',name)
assert composition['raw_object_bytes']==report['object_vram']['bytes']
report['sprite_composition']={'report_sha256':hashlib.sha256(composition_path.read_bytes()).hexdigest(),
    'compositions':composition['compositions'],'pixels':composition['pixels'],
    'additional_corrected_frames':33,'additional_corrected_pixels':5032,
    'limit':'Independent source composition and full target VRAM readback; not exhaustive target animation/occlusion coverage.'}
report['monitor_pixel_counts']=monitor_pixel_counts
report['monitor_routes']+='; 100 frame captures match independent original monitor compositions'
order_path=ROOT/'build/sprite-order/report.json';order_proof=json.loads(order_path.read_text())
# 64 source-backed types x 256 subtypes x 16 frames, including R3 projector/animals.
assert order_proof['passed'] and order_proof['cases']==512 and order_proof['priority_cases']==278528  # 17 sprite kinds x 16384 (SIKAKE33 added)
for name,expected in (order_proof['source_sha256']|order_proof['priority_source_sha256']).items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,('Stale sprite priority proof',name)
report['sprite_order']={'report_sha256':hashlib.sha256(order_path.read_bytes()).hexdigest(),
    'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
        ['src/main.c','src/sprite_order.h','src/boss.c','src/scd_boss.h','tools/emulator_test.c',
         'tools/projector_pixels.py','tools/monitor_pixels.py','tools/check_sonic_pixels.py','tools/sprite_priority_reference.py']},
    'monitor_overlap_pixels':sum(v['sonic_overlap_pixels'] for v in monitor_pixel_counts.values()),
    'limits':'Given-submission queue order and source priorities; selected source-pixel target overlaps. Not exhaustive original allocation, effect ordering or hardware.'}
report['object_vram_capture_sha256']=hashlib.sha256((folder/'monitor-vdp1.bin').read_bytes()).hexdigest()
report['monitor_verification_sources']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'tools/check_world.py',ROOT/'tools/check_object_vram.py',ROOT/'tools/monitor_pixels.py',ROOT/'tools/convert_objects.py',ROOT/'tools/emulator_test.c',ROOT/'assets/generated/object-frames.inc',ROOT/'assets/generated/object-art.bin',DATA/'_Objects/Monitor and Time Post/Data/Mappings.asm',DATA/'_Objects/Monitor and Time Post/Data/Art.nem',DATA/'_Objects/Sonic/Data/Palette.bin']}
from camera_pixels import analyze as analyze_camera,verify_coherence,inspect_draw_mode
camera_rows=analyze_camera(folder)
report['camera_coherence']=verify_coherence(camera_rows)
report['camera_coherence']['rows']=camera_rows
report['camera_coherence']['draw_modes']={p.name:inspect_draw_mode(p) for p in sorted(folder.glob('camera-*.state'))}
assert len(report['camera_coherence']['draw_modes'])==2
report['camera_coherence']['core_sha256']=hashlib.sha256((ROOT/'.deps/beetle-saturn/mednafen_saturn_libretro.dylib').read_bytes()).hexdigest()
report['camera_coherence']['evidence_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.glob('camera-*'))}
report['camera_coherence']['log_sha256']=hashlib.sha256((folder/'results.log').read_bytes()).hexdigest()
camera_sources=[ROOT/'tools/camera_pixels.py',ROOT/'tools/terrain_pixels.py',ROOT/'tools/hud_pixels.py',ROOT/'tools/vdp2_title_cycles.py',ROOT/'tools/test_camera_pixels.py',ROOT/'tools/emulator_test.c',ROOT/'tools/check_world.py',ROOT/'src/main.c',ROOT/'src/title_view.inc',ROOT/'src/special_view.inc',DATA/'Palmtree Panic/Data/Objects (Act 1).bin',DATA/'_Objects/Spring/Data/Mappings.asm',DATA/'_Objects/Spring/Data/Art (Normal).nem',DATA/'Palmtree Panic/Data/Palette (Present).bin',DATA/'_Objects/Sonic/Data/Palette.bin']
camera_sources += [DATA/'Palmtree Panic/Data'/name for name in ['Tiles (Act 1 Present).nem','Blocks (Act 1 Present).nem','Chunks (Act 1 Present).bin','Foreground (Act 1 Present).bin']]
camera_sources += [DATA/'_Objects/HUD and Points/Data'/name for name in ['Mappings (HUD).asm','Art (HUD).nem','Art (Numbers).bin','Art (Life Icon).bin']]
camera_sources.append(ROOT/'src/gameplay_video.inc')
report['camera_coherence']['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in camera_sources}
print('Source-backed camera coherence:',{k:v for k,v in report['camera_coherence'].items() if isinstance(v,int)})
report['checkpoint_route']='Controller activates original checkpoint position, hits a seeded Anton, respawns with two lives, saved position and whole-second saved clock; exact clock/HUD proof is separate'
(ROOT/'dist/world-report.json').write_text(json.dumps(report,indent=2)+'\n');print('Target world semantics and controller-driven travel/cutscene/arrival passed')
