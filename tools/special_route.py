#!/usr/bin/env python3
"""Plan a special stage win route (stages 1-7) as controller input only.

The native Sub CPU update (verified against the original in
tools/test_special_stage.py) searches for pad input that destroys all six
UFOs and retrieves the time stone. Nothing is seeded: the route is one pad
value per Sub CPU update, replayed unchanged by the retail oracle and the
Saturn emulator gate. Output: build/special-retail/win-route.json for
stage 1, tests/routes/special/win-ss<n>.json for stage n
(usage: special_route.py [n [beam width]]; stages 3, 4, 6, 7 use width 64).
special_route.py <stage> <specStageFlags> <name> [width] plans an IPX.asm mode entry
into build/special-retail/<name>.json: in temporary or time attack mode the win is
the stage ending with every UFO gone.
"""
import ctypes as C,heapq,json,math,subprocess
from special_assets import ROOT,parts,pack
from special_sonic_assets import pack as sonic_pack
from special_effect_assets import pack as sfx_pack
from special_ufo_assets import pack as ufx_pack,paths as ufo_paths
from test_special_contacts import ContactPlayer,World
from test_special_sprite import Art,Sprite,Pose
from test_special import Stage
from test_special_stage import SOURCES,ufo_word
LEFT,RIGHT,JUMP=4,8,16
class Animation(C.Structure):_fields_=[('fan',C.c_uint16),('hazard',C.c_uint16),('delay',C.c_uint16)]

class NativeSub:
    """Native Sub CPU program start and updates with byte snapshots."""
    def __init__(self,library=None,build=True,stage=1,mode=0):
        library=library or ROOT/('build/special-route.dylib' if stage==1 else f'build/special-route-ss{stage}.dylib')
        if build:subprocess.run(['clang','-std=c11','-O2','-Wall','-Wextra','-Werror','-fwrapv','-Isrc','-Iassets/generated','-dynamiclib']+SOURCES+['-o',str(library)],cwd=ROOT,check=True)
        n=self.n=C.CDLL(str(library))
        n.scd_special_art_open.argtypes=[C.POINTER(Art),C.c_void_p,C.c_size_t];n.scd_special_open.argtypes=[C.POINTER(Stage),C.c_void_p,C.c_size_t]
        n.scd_special_stage_reset.argtypes=[C.c_void_p,C.POINTER(World),C.c_void_p,C.c_size_t,C.c_uint]
        n.scd_special_stage_start.argtypes=[C.c_void_p,C.POINTER(World),C.POINTER(ContactPlayer),C.POINTER(Sprite)]
        n.scd_special_stage_update.argtypes=[C.c_void_p,C.POINTER(World),C.POINTER(ContactPlayer),C.POINTER(Sprite),C.POINTER(Art),C.POINTER(Art),C.POINTER(Art),C.POINTER(Stage),C.c_uint,C.c_uint,C.c_uint,C.POINTER(Pose),C.POINTER(C.c_int)]
        n.scd_special_stage_words.argtypes=[C.c_void_p,C.POINTER(C.c_uint32)];n.scd_special_stage_words.restype=C.c_uint
        n.scd_special_sprite_set.argtypes=[C.POINTER(Sprite),C.POINTER(Art),C.c_uint,C.c_int]
        n.scd_special_cache.argtypes=[C.POINTER(Stage),C.c_void_p,C.c_size_t];n.scd_special_cache.restype=C.c_size_t
        n.scd_special_animate.argtypes=[C.POINTER(Stage),C.POINTER(Animation),C.c_void_p,C.c_void_p,C.c_void_p]
        self.keep=[];self.arts={}
        for name,data in [('sonic',sonic_pack()[0]),('sfx',sfx_pack()[0]),('ufx',ufx_pack()[0])]:
            b=C.create_string_buffer(data);self.keep.append(b);self.arts[name]=Art();assert n.scd_special_art_open(C.byref(self.arts[name]),b,len(data))==0
        self.path_data=ufo_paths()[0];self.path_buffer=C.create_string_buffer(self.path_data)
        self.components=parts(stage);self.stage_data=C.create_string_buffer(pack(stage));self.stage=Stage();assert n.scd_special_open(C.byref(self.stage),self.stage_data,len(self.stage_data))==0
        self.cache=C.create_string_buffer(0x80000);assert n.scd_special_cache(C.byref(self.stage),self.cache,0x80000)>0
        self.cached_map=C.create_string_buffer(32768);C.memmove(self.cached_map,self.cache,32768)
        start=self.components[4]
        self.p=ContactPlayer(x=int.from_bytes(start[:2],'big')<<16,y=int.from_bytes(start[2:4],'big')<<16,yaw=int.from_bytes(start[4:6],'big')<<16,sprite_y=344<<16,z=352,top_speed=0xa00,routine=1)
        self.s=Sprite(tilt=5);n.scd_special_sprite_set(C.byref(self.s),C.byref(self.arts['sonic']),10,1)
        self.w=World(timer=0 if mode&2 else 100,timer_frames=20,ufo_count=6,time_attack=mode>>1&1)
        C.memmove(C.addressof(self.w)+World.time_stone.offset+3,bytes([mode]),1) # scd_special_world.mode
        self.st=C.create_string_buffer(65536);assert n.scd_special_stage_reset(self.st,C.byref(self.w),self.path_buffer,len(self.path_data),stage-1)==0
        n.scd_special_stage_start(self.st,C.byref(self.w),C.byref(self.p),C.byref(self.s))
        self.animation=Animation();self.pose=Pose();self.visible=C.c_int();self.words=(C.c_uint32*2048)()
    def update(self,held,tapped,before=None):
        """AnimateStamps then RunObjects/UpdateTimer; before(map) sees the animated stamp map."""
        n=self.n;n.scd_special_animate(C.byref(self.stage),C.byref(self.animation),self.stage.part[1],self.cache,self.cached_map)
        if before:before(C.string_at(self.stage.part[1],32768))
        memset=C.memset(C.addressof(self.w.sound),0,3)
        return n.scd_special_stage_update(self.st,C.byref(self.w),C.byref(self.p),C.byref(self.s),C.byref(self.arts['sonic']),C.byref(self.arts['ufx']),C.byref(self.arts['sfx']),C.byref(self.stage),held,tapped,self.p.yaw>>16,C.byref(self.pose),C.byref(self.visible))
    def parts_list(self):
        return [(self.st,65536),(C.addressof(self.w),C.sizeof(self.w)),(C.addressof(self.p),C.sizeof(self.p)),(C.addressof(self.s),C.sizeof(self.s)),
            (C.addressof(self.animation),C.sizeof(self.animation)),(self.stage.part[1],32768),(self.cached_map,32768)]
    def snapshot(self):return [C.string_at(address,size) for address,size in self.parts_list()]
    def restore(self,snap):
        for (address,size),data in zip(self.parts_list(),snap):C.memmove(address,data,size)
    def ufos(self):
        count=self.n.scd_special_stage_words(self.st,self.words);words=self.words
        return [(i,ufo_word(words,i,'x')>>16,ufo_word(words,i,'y')>>16) for i in range(6) if ufo_word(words,i,'id') and ufo_word(words,i,'routine')==1]

def route_path(stage):
    """Stage 1 is planned on every run; stages 2-7 are stored routes."""
    return ROOT/'build/special-retail/win-route.json' if stage==1 else ROOT/f'tests/routes/special/win-ss{stage}.json'

class TrackDistance:
    """Distance along the track between 32-pixel stamps (Dijkstra, 8-way).
    Bumpers and unmapped stamps block; water costs `water` stamps because
    each splash speeds up the timer (Objects/Splash/Main.asm)."""
    def __init__(self,stage_parts,water):
        types=stage_parts[2];self.cost=[]
        for v, in __import__('struct').iter_unpack('>H',stage_parts[1]):
            t=-1 if v==65535 else types[(v&2047)>>2]
            self.cost.append(None if t in (-1,1) else water if t==3 else 3 if t==6 else 1)
        self.fields={}
        self.cell=lambda px,py:max(0,min(127,py>>5))*128+max(0,min(127,px>>5))
    def field(self,cell):
        if cell in self.fields:return self.fields[cell]
        dist=__import__('array').array('f',[1e9])*16384;dist[cell]=0;heap=[(0,cell)]
        while heap:
            d,c=heapq.heappop(heap)
            if d>dist[c]:continue
            x,y=c%128,c//128
            for dx,dy,step in ((1,0,1),(-1,0,1),(0,1,1),(0,-1,1),(1,1,1.414),(1,-1,1.414),(-1,1,1.414),(-1,-1,1.414)):
                if 0<=x+dx<128 and 0<=y+dy<128:
                    n=c+dx+dy*128;cost=self.cost[n]
                    if cost is not None and d+step*cost<dist[n]:dist[n]=d+step*cost;heapq.heappush(heap,(dist[n],n))
        self.fields[cell]=dist;return dist
    def stamps(self,c,target):
        dist=self.field(target)
        return min([dist[c]]+[dist[n] for n in (c-1,c+1,c-128,c+128) if 0<=n<16384])
    def __call__(self,x,y,tx,ty):return self.stamps(self.cell(x,y),self.cell(tx,ty))*32
    def tour(self,x,y,ufos):
        """Greedy nearest-UFO tour length in stamps from Sonic through every UFO left."""
        c=self.cell(x,y);left=[self.cell(u[1],u[2]) for u in ufos];total=0
        while left:
            d,u=min((self.stamps(c,u),u) for u in left);total+=d;left.remove(u);c=u
        return total

def plan_win(limit=2000,width=24,stage=1,mode=0,water=0,slack=0):
    """Beam search over held-button segments. Score: UFOs destroyed, time
    stone (or the mode's stage end), then distance to the nearest UFO and
    remaining time (elapsed time in time attack). water>0 measures distance
    along the track, with water stamps costing that many path stamps.
    slack>0 scores time left minus the greedy tour through every UFO left,
    at `slack` seconds per path stamp (stage 8: UFOs add no time, only the
    time UFO does, Objects/UFO/Main.asm)."""
    sub=NativeSub(stage=stage,mode=mode);sub.update(0,0) # Start's UpdateStage runs with released buttons.
    track=TrackDistance(sub.components,water) if water else None
    won=lambda:sub.w.got_time_stone or (mode&3 and sub.w.stage_over and not sub.w.ufo_count)
    actions=[]
    while sub.w.inactive or not sub.ufos():sub.update(0,0);actions.append(0) # Title card: input is ignored.
    segments=[(0,5),(LEFT,5),(RIGHT,5),(JUMP,17),(JUMP|LEFT,17),(JUMP|RIGHT,17)]
    def score():
        ufos=sub.ufos();x,y=sub.p.x>>16,sub.p.y>>16
        near=min(((track(x,y,u[1],u[2]) if track else math.hypot(x-u[1],y-u[2])) for u in ufos),default=0)
        # Mode entries end at the first stage end: time is worth more there (stage 8 hazards drain it).
        clock=-(sub.w.timer>>8&0xffff) if mode&2 else sub.w.timer*(2000 if mode else 20)-sub.w.speedup*(2000 if mode else 0)
        if slack:
            left=sub.w.timer-sub.w.speedup-(sub.w.timer_frames/20)-slack*track.tour(x,y,ufos)
            return bool(won())*10000000+(6-sub.w.ufo_count)*5000+left*1000,near
        return (6-sub.w.ufo_count)*100000+bool(won())*10000000-near+clock,near
    beam=[(score()[0],sub.snapshot(),tuple(actions),0)]
    for depth in range(400):
        candidates={}
        for value,snap,plan,previous in beam:
            sub.restore(snap);near=score()[1]
            for held,count in segments:
                if held&JUMP and ((near>360 and not mode) or sub.p.routine!=1):continue
                sub.restore(snap);prev=previous;steps=[]
                for i in range(count):
                    now=held if i<16 else held&~JUMP
                    sub.update(now,now&~prev&JUMP);steps.append(now);prev=now
                    if won():break
                if mode and sub.w.stage_over and not won():continue # The stage ended without a win.
                value=score()[0];key=(sub.p.x>>19,sub.p.y>>19,sub.p.yaw>>20,sub.w.ufo_count,sub.p.routine)
                if key not in candidates or candidates[key][0]<value:candidates[key]=(value,sub.snapshot(),plan+tuple(steps),prev)
        if not candidates:break # Every branch ended the stage without a win.
        beam=sorted(candidates.values(),key=lambda c:-c[0])[:width]
        best=beam[0];sub.restore(best[1])
        if depth%10==0:print('depth',depth,'updates',len(best[2]),'ufos',sub.w.ufo_count,'rings',sub.w.rings,'timer',sub.w.timer,'score',best[0],flush=True)
        if won() or len(best[2])>=limit:break
    return list(best[2]),sub

def hazard_path(stage):return ROOT/f'tests/routes/special/hazard-ss{stage}.json'

def plan_hazard(stage,limit=1700,width=32):
    """Beam search that touches every stamp type in the stage map (bumper, fan,
    water, rough, spring, hazard, both boosters; ObjSonic_StampCollide) with UFOs
    left, and gets hurt by a hazard (ObjSonic_Hazard). The route then releases the
    pad until the stage times out. Score: types covered, then distance to the
    nearest stamp of an uncovered type."""
    sub=NativeSub(stage=stage,build=False);sub.update(0,0)
    kind=sub.n.scd_special_stamp_type;kind.argtypes=[C.c_void_p,C.c_int,C.c_int,C.c_void_p]
    targets={}
    for y in range(16,4096,32):
        for x in range(16,4096,32):
            k=kind(C.byref(sub.stage),x,y,None)
            if 0<k<9:targets.setdefault(k,[]).append((x,y))
    targets[9]=targets[6] # Bit 9: hurt mode, reached on hazard stamps.
    goal=sum(1<<k for k in targets)
    actions=[]
    while sub.w.inactive or not sub.ufos():sub.update(0,0);actions.append(0)
    segments=[(0,5),(LEFT,5),(RIGHT,5),(JUMP,17),(JUMP|LEFT,17),(JUMP|RIGHT,17)]
    def covered(mask):
        if sub.w.ufo_count and 0<sub.p.stamp_c<9:mask|=1<<sub.p.stamp_c
        if sub.p.routine==7:mask|=1<<9
        return mask
    def score(mask):
        # Water drains the timer (Splash object), so it is the last target and time left counts.
        x,y=sub.p.x>>16,sub.p.y>>16;rest=goal&~mask;wanted=rest&~8 or rest
        near=min((math.hypot(x-tx,y-ty) for k in targets if wanted>>k&1 for tx,ty in targets[k]),default=0)
        return bin(mask&~8 if rest&~8 else mask).count('1')*100000-near+sub.w.timer*1000
    previous_of=lambda plan:plan[-1] if plan else 0
    beam=[(score(0),sub.snapshot(),tuple(actions),0)]
    for depth in range(400):
        candidates={}
        for value,snap,plan,mask in beam:
            for held,count in segments:
                sub.restore(snap)
                if held&JUMP and sub.p.routine!=1:continue
                steps=[];m=mask;prev=previous_of(plan)
                for i in range(count):
                    now=held if i<16 else held&~JUMP
                    sub.update(now,now&~prev&JUMP);steps.append(now);prev=now;m=covered(m)
                if not sub.w.ufo_count or sub.w.got_time_stone:continue
                value=score(m);key=(sub.p.x>>19,sub.p.y>>19,sub.p.yaw>>20,m,sub.p.routine)
                if key not in candidates or candidates[key][0]<value:candidates[key]=(value,sub.snapshot(),plan+tuple(steps),m)
        beam=sorted(candidates.values(),key=lambda c:-c[0])[:width]
        best=beam[0];sub.restore(best[1])
        if depth%10==0:print('depth',depth,'updates',len(best[2]),'mask',hex(best[3]),'goal',hex(goal),'timer',sub.w.timer,flush=True)
        if best[3]==goal or len(best[2])>=limit:break
    return list(best[2]),best[3],goal,sub

def main_hazard(stage,width):
    actions,mask,goal,sub=plan_hazard(stage,width=width)
    route={'actions':actions,'updates':len(actions)+1,'covered':mask,'goal':goal,'timer':sub.w.timer,'ufo_count':sub.w.ufo_count,'score':0,'results_start':40}
    hazard_path(stage).parent.mkdir(parents=True,exist_ok=True);hazard_path(stage).write_text(json.dumps(route)+'\n')
    print(json.dumps({k:v for k,v in route.items() if k!='actions'}))
    assert mask==goal,'planned route did not touch every stamp type'

def main():
    import sys
    if sys.argv[1:2]==['hazard']:
        subprocess.run(['clang','-std=c11','-O2','-Wall','-Wextra','-Werror','-fwrapv','-Isrc','-Iassets/generated','-dynamiclib']+SOURCES+['-o',f'build/special-route-ss{sys.argv[2]}.dylib'],cwd=ROOT,check=True)
        return main_hazard(int(sys.argv[2]),int(sys.argv[3]) if len(sys.argv)>3 else 32)
    if len(sys.argv)>3 and not sys.argv[3].isdigit():
        stage,mode,name=int(sys.argv[1]),int(sys.argv[2]),sys.argv[3]
        actions,sub=plan_win(stage=stage,mode=mode,width=int(sys.argv[4]) if len(sys.argv)>4 else 24,
            water=float(sys.argv[5]) if len(sys.argv)>5 else 0,slack=float(sys.argv[6]) if len(sys.argv)>6 else 0)
        won=sub.w.got_time_stone or (sub.w.stage_over and not sub.w.ufo_count)
        route={'actions':actions,'updates':len(actions)+1,'rings':sub.w.rings,'timer':sub.w.timer,'ufo_count':sub.w.ufo_count,'got_time_stone':sub.w.got_time_stone,'score':0,'results_start':40,'stage':stage,'mode':mode}
        (ROOT/'build/special-retail').mkdir(parents=True,exist_ok=True);(ROOT/f'build/special-retail/{name}.json').write_text(json.dumps(route)+'\n')
        print(json.dumps({k:v for k,v in route.items() if k!='actions'}))
        assert won,'planned route did not win the stage'
        return
    stage=int(sys.argv[1]) if len(sys.argv)>1 else 1
    width=int(sys.argv[2]) if len(sys.argv)>2 else 24
    actions,sub=plan_win(stage=stage,width=width)
    route={'actions':actions,'updates':len(actions)+1,'rings':sub.w.rings,'timer':sub.w.timer,'ufo_count':sub.w.ufo_count,'got_time_stone':sub.w.got_time_stone,'score':4000,'results_start':40}
    route_path(stage).parent.mkdir(parents=True,exist_ok=True)
    route_path(stage).write_text(json.dumps(route)+'\n')
    print(json.dumps({k:v for k,v in route.items() if k!='actions'}))
    assert sub.w.got_time_stone,'planned route did not retrieve the time stone'

if __name__=='__main__':main()
