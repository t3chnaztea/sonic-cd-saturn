#!/usr/bin/env python3
"""Replay actual Saturn effect states through the untouched retail actor.

Player/context samples and late grant events come from target telemetry; the
separate real-player runtime test checks the pre/post-object grant boundary.
This proves target actor evolution, not original gameplay/travel equivalence.
"""
import hashlib,json
from convert_assets import ROOT
from test_powerup_visual import State,Context,retail_reference
from check_powerup_pixels import pair

def unpack(words):
    a,b,c,position,tile=words;x,y=pair(position)
    return State(x=x,y=y,tile=tile,active=a>>24,routine=(a>>16)&255,
        animation=(a>>8)&255,previous=a&255,cursor=b>>24,timer=(b>>16)&255,
        mapping=(b>>8)&255,sprite_flags=b&255,flags=c>>24,phase=(c>>16)&255,
        priority=(c>>8)&255,width=c&255)

def verify():
    path=ROOT/'build/world-qa/effect-target-trace.txt'
    rows=[list(map(int,line.split())) for line in path.read_text().splitlines()]
    assert len(rows)>23000
    original=retail_reference();previous=None;c=Context();actors=[State() for _ in range(9)]
    calls=0;late=[];resets=0;seen=set();suppressed=0;deleted=0;known=set()
    for line,row in enumerate(rows,1):
        fixture,*v=row;assert len(v)==57 and v[0]==0x504f5756
        reset=previous is None or fixture!=previous[0] or v[1]<=previous[2] or v[11]!=previous[12]
        if reset:
            assert v[1]==1 or line==1,('missing initial updates',line,v[:12])
            actors=[State() for _ in range(9)];c=Context();known=set(range(64)) if line>1 else set();resets+=1
        else:assert v[1]==previous[2]+1,('skipped simulation state',line,v[1],previous[2])
        delta=(v[3]-c.record_index)&255
        assert delta in (0,4) or line==1,('position record cadence',line,delta)
        if delta:
            slot=((v[3]-4)&255)//4;c.history[slot][:]=pair(v[6]);known.add(slot)
        c.record_index=v[3];c.x,c.y=pair(v[7])
        c.flags=v[8]>>24;c.shield=(v[8]>>16)&255;c.invincible=(v[8]>>8)&255;c.travel=v[8]&255;c.powerup&=127
        actual=[unpack(v[12+n*5:17+n*5]) for n in range(9)]
        for first,count,enabled in [(0,1,c.shield),(1,4,c.invincible),(5,4,c.travel)]:
            if enabled and not actors[first].active:
                for n in range(first,first+count):actors[n].active=3;actors[n].animation=n
        mask=0
        for n,state in enumerate(actors):
            if not state.active:continue
            if state.routine in (4,6) and not(state.routine==4 and c.travel):
                index=((c.record_index-(24*((state.animation-1)&3)+4)-state.phase)&255)//4
                assert index in known,('unobserved position history used',line,index)
            before=bytes(state);expected,powerup,submitted=original(state,c);c.powerup=powerup;actors[n]=expected;calls+=1
            suppressed+=not submitted and bytes(expected)==before
            deleted+=not expected.active
            if submitted:mask|=1<<n;seen.add((n,expected.mapping))
        # A monitor's late creation must leave the reserved actor untouched
        # except for ID/animation; initialization cannot happen until next pass.
        for first,count,flag in [(0,1,c.shield),(1,4,c.invincible)]:
            if not flag and actual[first].active and not actors[first].active:
                assert fixture==(19 if first==0 else 20),('unexpected grant fixture',line,fixture,first)
                for n in range(first,first+count):actors[n].active=3;actors[n].animation=n
                late.append(dict(line=line,fixture=fixture,update=v[1],first=first))
        for n,(expected,target) in enumerate(zip(actors,actual)):
            assert bytes(expected)==bytes(target),('retail/target actor',line,fixture,v[1],n,list(bytes(expected)),list(bytes(target)))
        assert mask==v[2] and c.powerup==v[10],('retail/target submission or art',line,mask,v[2],c.powerup,v[10])
        previous=row
    assert len(late)==2 and calls>6000 and len(seen)==47,(late,calls,len(seen))
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    report=dict(passed=True,disc_sha256=sha(ROOT/'dist/sonic-cd-saturn-prototype.bin'),rows=len(rows),
        original_cpu_calls=calls,scene_resets=resets,late_monitor_grants=late,suppressed=suppressed,deleted=deleted,
        animation_mapping_pairs=sorted(seen),trace_sha256=sha(path),
        source_sha256={name:sha(ROOT/name) for name in ['tools/check_powerup_target.py','tools/test_powerup_visual.py',
            'tools/check_powerup_pixels.py','src/main.c','src/player.c','src/powerup_visual.c','src/powerup_runtime.c','tools/emulator_test.c']},
        limits='Original actor execution with captured native player/travel context and late grants, not proof of original travel gameplay scheduling or scene-persistence behavior.')
    print('Retail CPU vs actual Saturn power-ups:',len(rows),'updates,',calls,'actor calls,',len(seen),'animation/mapping pairs')
    return report

if __name__=='__main__':
    (ROOT/'dist/powerup-target-report.json').write_text(json.dumps(verify(),indent=2)+'\n')
