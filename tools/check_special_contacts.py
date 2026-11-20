"""Replay actual Saturn controller states through the original 68000 update."""
import ctypes as C,hashlib,json,re
from special_assets import SOURCE,parts
from special_stage_reference import StageReference,fnv_words,effects_hash
from special_sprite_reference import SpriteReference
from test_special_contacts import ContactPlayer,World,state
from test_special_sprite import Sprite

def decode(words):
    result=[];cursor=0
    for model in [ContactPlayer,Sprite,World]:
        values={}
        for name,kind in model._fields_:
            count=kind._length_ if issubclass(kind,C.Array) else 1
            values[name]=words[cursor:cursor+count] if issubclass(kind,C.Array) else words[cursor]
            cursor+=count
        result.append(values)
    assert cursor==69
    return tuple(result)

def check(log,visuals=None):
    rows=[list(map(int,row.split())) for row in re.findall(r'Special contact state:(.+)',log)]
    assert len(rows)>100,'Missing target controller contact replay'
    sr=SpriteReference();initial_sprite=state(Sprite(tilt=5))
    initial_sprite,flags,_=sr.run('set',initial_sprite,0,0,animation=10)
    initial_sprite,flags,_=sr.run('draw',initial_sprite,flags,0)
    reference=StageReference();components={id:list(parts(id)) for id in {r[1] for r in rows}};maps={}
    # Precompute original animated maps. Animation globals share source RAM
    # with the stage globals, so finish this pass before replaying updates.
    for id,part in components.items():
        maps[id]=[part[1]];reference.r.begin_animation(part)
        for _ in range(max(r[5] for r in rows if r[1]==id)):maps[id].append(reference.r.animate()[0])
    updates=0;resets=0;surfaces=set();ufo_cases=set();types=set();routines=set();sounds=set();codes=set();digest=hashlib.sha256();previous=None
    for n,row in enumerate(rows):
        assert len(row)==79 and row[0]==n+1 and row[75]==0 and row[76]<=10
        sequence,id,tick,held,tapped,delay=row[:6];actual=decode(row[6:75]);part=list(components[id]);part[1]=maps[id][delay]
        if tick==0:
            assert held==tapped==0
            start=part[4];p=state(ContactPlayer(x=int.from_bytes(start[:2],'big')<<16,y=int.from_bytes(start[2:4],'big')<<16,yaw=int.from_bytes(start[4:6],'big')<<16,sprite_y=344<<16,z=352,top_speed=0xa00,routine=1))
            w=state(World(timer=100,timer_frames=20,ufo_count=6,ring_bonus=20));kind=row[76]
            if 1<=kind<=8:
                surfaces.add(kind)
                def stamp(x,y):
                    raw=int.from_bytes(part[1][((y>>5)*128+(x>>5))*2:][:2],'big')
                    return part[2][(raw&2047)>>2] if raw!=65535 else -1
                x,y=next((x,y) for y in range(848,3264,32) for x in range(848,3264,32) if stamp(x,y)==kind)
                p.update(x=(x<<16)|0x1234,y=(y<<16)|0x5678,x_velocity=0x89ab,y_velocity=0xcdef);w['rings']=99
            elif kind==9:
                path=(SOURCE/f'Data/Stage {id}/UFO 1.bin').read_bytes();ufo_cases.add(kind)
                p.update(x=int.from_bytes(path[4:6],'big')<<16,y=int.from_bytes(path[6:8],'big')<<16,routine=2,flags=0x80,sprite_y=288<<16,z=0x240);w['rings']=99
            elif kind==10:
                ufo_cases.add(kind);w.update(timer=19,timer_frames=1,rings=99)
            reference.reset(id,p,dict(initial_sprite),w,part);resets+=1
            if kind:assert resets==kind+2,(resets,kind)
            expected_state=reference.state()
            expected=(p,dict(initial_sprite),w)
        else:
            assert previous is not None and tick==previous_tick+1 and id==previous_id and delay==previous_delay+1
            expected_state=reference.step(held,tapped,part[1]);updates+=1
            expected=(expected_state['player'],expected_state['sprite'],expected_state['world'])
            expected[2]['sound']=list(expected[2]['sound'])
        assert actual==expected,('SH-2 stage replay',sequence,tick,held,tapped,[{k:(got[k],want[k]) for k in got if got[k]!=want[k]} for got,want in zip(actual,expected)])
        assert row[77]==effects_hash(expected_state['effects']),('SH-2 effect pool',sequence,tick)
        assert row[78]==fnv_words(expected_state['words']),('SH-2 stage objects/draw list',sequence,tick,expected_state['draws'])
        assert expected_state['sprite_count']<80,('original sprite table cap reached',sequence)
        if visuals is not None:visuals[(resets,tick)]={'sat':expected_state['sat'],'log':expected_state['log'],'draws':expected_state['draws'],'sonic_art':expected_state['sprite']['art']}
        previous=expected;previous_tick=tick;previous_id=id;previous_delay=delay
        codes.update(d[7] for d in expected_state['draws'] if d[6])
        types.add(actual[0]['stamp_c']);routines.add(actual[0]['routine']);sounds.update(actual[2]['sound']);digest.update(json.dumps(actual,sort_keys=True).encode());digest.update(row[77].to_bytes(4,'big')+row[78].to_bytes(4,'big'))
    assert updates>=100 and resets==12 and surfaces==set(range(1,9)) and ufo_cases=={9,10}
    assert set(range(9))<=types and {1,2,3,4,7,19}<=routines,(types,routines)
    return {'passed':True,'updates':updates,'resets':resets,'surface_routes':sorted(surfaces),'ufo_routes':sorted(ufo_cases),'semantic_words_per_state':69,'stamp_types':sorted(types),'routines':sorted(routines),'sound_requests':sorted(sounds-{0}),'visible_draw_objects':sorted(codes),'state_sha256':digest.hexdigest(),'effect_pool_verified':True,'stage_objects_and_draw_list_verified':True,'limits':'Controller-driven original RunObjects/UpdateTimer state and DrawObject order. Requests are traced then discarded in this inspection; special-stage audio, HUD and results remain pending.'}
