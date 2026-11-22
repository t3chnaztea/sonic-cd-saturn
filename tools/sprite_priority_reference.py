"""Extract PPZ draw priorities independently of the native renderer table."""
import hashlib,re
from convert_assets import ROOT,DATA

sources={}
def section(folder,label):
    path=DATA/folder/'Main.asm';text=path.read_text()
    sources[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    assert label+':' in text,(folder,label)
    start=text.index(label+':')+len(label)+1
    end=re.search(r'^\w[\w]*:',text[start:],re.M)
    return text[start:start+end.start()] if end else text[start:]
def byte(folder,label,actor='a0'):
    text=section(folder,label)
    m=re.search(r'move\.b\s+#(\$[0-9A-Fa-f]+|\d+),oPriority\('+actor+r'\)',text)
    assert m,(folder,label,actor)
    return int(m[1][1:],16) if m[1].startswith('$') else int(m[1])
def zero(folder,label):
    text=section(folder,label)
    assert 'oPriority' not in text and not re.search(r'move\.l.*oYRadius',text),(folder,label)
    return 0

def priorities():
    common='_Objects/';ppz='Palmtree Panic/Objects/'
    specs={
        9:(ppz+'Spinning Disc','ObjSpinningDisc_Init'),10:(common+'Spring','ObjSpring_Init'),
        13:(common+'Spin Tunnel','ObjTunnelDoor_Init'),
        15:(common+'Spring','ObjMovingSpring_Init'),18:(common+'Floating Block','ObjFloatBlock_Init'),
        21:(common+'Level End','ObjCapsule_Init'),22:(common+'Level End','ObjGoalPost_Init'),
        23:(common+'Level End','ObjSignpost_Init'),24:(common+'Explosion','ObjExplosion_Init'),
        25:(common+'Monitor and Time Post','ObjMonitor_Init'),26:(common+'Monitor and Time Post','ObjMonitorItem_Init'),
        27:(common+'Boulder','ObjBoulder_Init'),31:(common+'Flower','ObjFlower_Init'),
        32:(ppz+'Collapsing Platform','ObjCollapsePlatform_Init'),33:(ppz+'Platform','ObjPlatform_Init'),
        34:(ppz+'Tamabboh','ObjTamabboh_Init'),38:(common+'Spikes','ObjSpikes_Init'),
        40:(ppz+'Springboard','ObjSpringBoard_Init'),42:(ppz+'3D Ramp','Obj3DRamp_Init'),
        45:(common+'Robot Generator','ObjRobotGenerator_Init'),46:(ppz+'Projector','ObjProjector_Init'),
        47:(ppz+'Amy Rose','ObjAmyRose_Init'),48:(ppz+'Amy Rose','ObjAmyHeart_Init'),
        49:(ppz+'Tunnel Path','ObjSonicHole_Init'),51:(ppz+'Log Shadow','ObjLogShadow_Init'),
        53:(ppz+'Tunnel Door','ObjTunnelDoorV_Init'),54:(ppz+'Breakable Wall','ObjBreakableWall_Init'),
        61:(ppz+'Mosqui','ObjMosqui_Init'),62:(ppz+'Pata-Bata','ObjPataBata'),
        63:(ppz+'Anton','ObjAnton_Init'),64:(ppz+'Taga-Taga','ObTagaTaga_Init')}
    # Spin Tunnel's shared door file uses a descriptive filename.
    result={}
    for kind,(folder,label) in specs.items():
        if kind==13:
            path=DATA/folder/'Main (Door).asm';text=path.read_text()
            sources[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
            values=re.findall(r'move\.b\s+#(\d+),oPriority\(a0\)',text)
            assert values and set(values)=={'1'};value=1
        else:value=byte(folder,label)
        result[kind]=value
    # Ring initializers operate on newly allocated a1, including a MMZ-only
    # priority override. PPZ takes the first initialization value.
    ring=(DATA/common/'Ring/Main.asm').read_text();path=DATA/common/'Ring/Main.asm'
    sources[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    assert 'move.b\t#2,oPriority(a1)' in ring and 'move.b\t#3,oPriority(a1)' in ring
    result[16]=2;result[17]=3
    result[19]=byte(common+'Checkpoint','ObjCheckpoint_Init')
    orb=byte(common+'Checkpoint','ObjCheckpoint_Init','a1')
    result[20]=zero(common+'Level End','ObjBigRing_Init')
    assert zero(common+'Level End','ObjBigRingFlash_Init')==result[20]
    seed=zero(common+'Level End','ObjCapsule_SpawnSeeds')
    result[50]=zero(ppz+'Scenery','ObjScenery_Init')
    result[85]=zero(common+'HUD and Points','ObjPoints_Init')
    plant=section(ppz+'3D Ramp','Obj3DPlant_Init')
    assert 'oPriority' not in plant.split('.Loop2:')[0]
    assert re.search(r'move\.b\s+#4,oPriority\(a1\)',plant)
    result[44]=0
    animal=section(ppz+'Animal','ObjFlyingAnimal_Init')
    assert re.search(r'move\.l\s+#\$8080408,oYRadius\(a0\)',animal)
    assert re.search(r'move\.b\s+#3,oPriority\(a0\)',animal)
    assert re.search(r'tst\.b\s+oSubtype\(a0\)\s*\n\s*bmi\.s\s+\.Holographic',animal)
    ground=section(ppz+'Animal','ObjGroundAnimal_Init')
    assert re.search(r'move\.l\s+#\$8080408,oYRadius\(a0\)',ground) and 'oPriority' not in ground
    result[36]=4
    path=ROOT/'.deps/soniccd/src/BRANKO1.C';text=path.read_text();sources[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    values=re.findall(r'->sprpri = (\d+)',text);assert values==['3'];result[41]=3
    # Zone objects past Palmtree Panic (src/objects_*.inc), each from every
    # sprpri assignment in the retail file(s) its port type covers.
    for kind,files in {86:('R3/ET3.C',),84:('R3/POCKET.C',),83:('R3/TOGEBL3A.C','R3/TOGEBL3B.C','R3/TOGEBL3D.C'),82:('R3/BANPA.C',),78:('R3/GA3.C',),29:('R3/BOBIN.C',),30:('R3/BOBIN.C',),67:('R4/WALL1.C',),68:('R7/WALL7.C','R7/WALL73.C'),69:('R5/DAI_RD5.C',),
                       70:('R8/KONBEA.C','R8/KONBEA83.C'),71:('R8/PISTON.C',)}.items():
        values=set()
        for name in files:
            path=ROOT/'.deps/soniccd/src'/name;text=path.read_text(errors='replace')
            sources[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
            found=re.findall(r'->sprpri = (\d+)',text);assert found,(name,);values|=set(found)
        assert len(values)==1,(kind,values);result[kind]=int(values.pop())
    path=ROOT/'.deps/soniccd/src/R3/TRAP_R3.C'
    text=path.read_text();sources[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    for kind,routine in [(72,'for3'),(73,'harir3'),(74,'frdr3'),(75,'trapdr3'),(76,'getdair3')]:
        found=re.findall(r'->sprpri = (\d+)',text.split('void '+routine+'_init(')[1].split('void '+routine+'_move(')[0])
        assert found==['3'];result[kind]=int(found[0])
    gnd=[]
    for name in ('gandair3_daii','gandair3_init','gandair3_tami'):
        body=text.split('void '+name+'(')[1].split('\nvoid ')[0]
        values=re.findall(r'->sprpri = (\d+)',body);assert len(values)==1
        gnd.append(int(values[0]))
    result[77]=gnd[0]
    drum_body=text.split('void drumr3_priset(')[1].split('\nvoid ')[0]
    drum=[int(n) for n in re.search(r'tbl\[12\]\s*=\s*\{([^}]+)\}',drum_body)[1].split(',')]
    assert len(drum)==12 and re.findall(r'->sprpri = (\d+)',text.split('void drumr3_init(')[1].split('\nvoid ')[0])==['3']
    result[87]=drum[0]
    for kind,name in [(88,'R3/MOVIE3.C'),(89,'R3/FRIEND3.C')]:
        path=ROOT/'.deps/soniccd/src'/name;text=path.read_text()
        sources[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
        values=set(map(int,re.findall(r'->sprpri = (\d+)',text)))
        assert values==({4} if kind==88 else {1,3,4}),(kind,values)
        result[kind]=4 if kind==88 else 1
    path=ROOT/'.deps/soniccd/src/R3/MECASNC.C';text=path.read_text()
    sources[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    for kind,routine,value in [(90,'emie3_init',1),(91,'hari3x_init',3),(92,'mecasnc3_init',2)]:
        body=text.split('void '+routine+'(')[1].split('\nvoid ')[0]
        assert re.findall(r'->sprpri = (\d+)',body)==[str(value)];result[kind]=value
    assert re.findall(r'->sprpri = (\d+)',text.split('void heart3_init(')[1].split('\nvoid ')[0])==['3']
    assert re.findall(r'->sprpri = (\d+)',text.split('void msnc3fire_init(')[1].split('\nvoid ')[0])==['3']
    # SIKAKE33: kaitenban, light and stopper each set sprpri once, to 3.
    for name in ('ROLLPLAT','LIGHT','STOPPER'):
        path=ROOT/'.deps/soniccd/src/R3'/(name+'.C');text=path.read_text()
        sources[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
        assert re.findall(r'->sprpri = (\d+)',text)==['3'],(name,)
    result[93]=3
    path=ROOT/'.deps/soniccd/src/R3/TENTOU.C';text=path.read_text()
    sources[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    ten=[int(re.search(r'->sprpri = (\d+)',text.split('void '+name+'(')[1])[1]) for name in ('ten_a_init','ten_b_init')]
    result[79]=ten[0]
    path=ROOT/'.deps/soniccd/src/R3/KAMA.C';text=path.read_text()
    sources[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    for kind,name in [(80,'kama_init'),(81,'wpkama_init')]:
        result[kind]=int(re.search(r'->sprpri = (\d+)',text.split('void '+name+'(')[1])[1])
    # The missile copies the parent priority and increments it.
    text=(DATA/ppz/'Tamabboh/Main.asm').read_text()
    assert re.search(r'move\.b\s+oPriority\(a0\),oPriority\(a1\)\s*\n\s*addq\.b\s+#1,oPriority\(a1\)',text)
    def priority(kind,subtype,frame):
        if kind==89:return 4 if subtype&1 else 3 if subtype&128 else 1
        if kind==90:return 3 if subtype else 1
        if kind==92:return 3 if subtype else 2
        if kind==87:return drum[frame] if frame<12 else 3
        if kind==79:return ten[1] if 0<subtype<128 else ten[0]
        if kind==77:return gnd[2] if subtype==2 else gnd[1] if subtype==1 else gnd[0]
        if kind==19 and frame:return orb
        if kind==21 and subtype:return seed
        if kind==34 and subtype==1:return result[kind]+1
        if kind==36 and subtype&128 and not subtype&1:return 3
        if kind==44 and frame:return 4
        return result[kind]
    return result,priority
