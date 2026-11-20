#!/usr/bin/env python3
"""Translate every zone's retail object layout into the port's object types.

The port's SCD_OBJ_* values are Palmtree Panic's retail object ids, and until now
they were treated as global.  They are not: each retail program dispatches a
record through its own act_tbl (ACTION.C: act_tbl[actno-1]), and the same id
names a different routine in another round, another act, and sometimes another
era.  Spawning another zone's records with Palmtree Panic's ids would put the
wrong object at thousands of placements.

So each record is resolved the way the retail program resolves it:

  record id --(the program's own act_tbl)--> retail routine name
            --(the routine behind each port type)--> port type

Both maps come from build/audit/source.  The port type of a routine is read from
Palmtree Panic's Act 1 and Act 2 tables, whose ids the port adopted; nothing here
is typed in by hand.  A routine the port does not implement resolves to nothing
and the record is dropped, never spawned as something else.

Which act_tbl a program uses follows the file suffix: A is the Present, B the
Past, C both Futures, and an act or round with fewer tables shares the one it
has.  That rule is not assumed: tools/test_object_layouts.py checks that every
record a program can see resolves to a real routine in that program's table,
and 17,923 of 17,932 visible record-eras do.  The nine that do not land on noact
in retail as well, so dropping them is what the original does.

The four era files of an act are byte identical, so there is one layout per act
and the era mask carries the rest.  When a record resolves to different port
types in different eras, it is split into one record per type with a narrowed
era mask.  The translated records then go through convert_objects.placements(),
the expander already proven on Palmtree Panic, so ring runs and ordering follow
the same rules.
"""
import collections,glob,re,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from convert_objects import SUPPORTED,placements

SOURCE=ROOT/'build/audit/source/src'
HARVEST=ROOT/'build/auto-extract'
ROUNDS=(1,3,4,5,6,7,8)
# Era mask bits, as src/objects.c tests them: Past bit 0, Present bit 1,
# both Futures bit 2.
ERA_BIT={'A':2,'B':1,'C':4,'D':4}

def act_tables():
    tables={}
    for path in glob.glob(str(SOURCE/'R*/ACT*.C')):
        text=Path(path).read_text(errors='replace')
        m=re.search(r'act_tbl\[\d*\][^=]*=\s*\{(.*?)\};',text,re.S)
        if not m:raise SystemExit(f'{path}: no act_tbl')
        body=re.sub(r'/\*.*?\*/','',m.group(1),flags=re.S)
        # Entries are "&name" or "(void(*)(sprite_status*))&name".
        tables[Path(path).stem]=[re.sub(r'^\(.*?\)\s*&?','',s.strip()).lstrip('&')
                                 for s in body.split(',') if s.strip()]
    return tables

def table_for(tables,rnd,act,era):
    for key in (f'ACT{rnd}{act}{era}',
                f'ACT{rnd}{act}C' if era in 'CD' else None,
                f'ACT{rnd}{act}B' if era in 'BCD' else None,
                f'ACT{rnd}{act}A',f'ACT{rnd}{act}',f'ACT{rnd}1A'):
        if key and key in tables:return key
    raise SystemExit(f'no act_tbl for R{rnd}{act}{era}')

def routine(tables,key,kind):
    table=tables[key]
    return table[kind-1] if 0<kind<=len(table) else 'noact'

def definitions():
    """Routine name -> the source files that define it with the object signature."""
    found=collections.defaultdict(set)
    for path in glob.glob(str(SOURCE/'**/*.C'),recursive=True):
        text=Path(path).read_text(errors='replace')
        for m in re.finditer(r'^void\s+(\w+)\s*\(\s*sprite_status\s*\*',text,re.M):
            found[m.group(1)].add(Path(path).relative_to(SOURCE).as_posix())
    return found

def linked(defs,rnd,name,act=None,era=None):
    """The definition a round's program links: its own directory's, else the one
    shared file.  None when the routine is not defined anywhere we can see.

    A round can define a routine twice, once for its Act 3 (R8 has KONBEA.C and
    KONBEA83.C).  Then the file named for this round and act wins, and the other
    acts take the file that names no act."""
    files=defs.get(name,set())
    own=sorted(f for f in files if f.startswith(f'R{rnd}/'))
    # TOGEBALL has an explicitly supported era family, independently checked
    # against all ten Sega CD programs. Native selection is 3/2/4/4 balls.
    if name=='togeball' and len(own)>1:
        # R6 has its own family; returning it keeps that clone excluded.
        return tuple(own)
    # SCREW_A.C is built into the Present and Past programs (its #if names
    # R41A R41B R42A R42B), SCREW_C.C into both Futures (R41C R41D ...).
    # HOTA8C.C is built into the Good Future program and HOTA8D.C into the Bad
    # Future (R83C/R83D); the port runs both through one actor (objects_mm_hota8.inc).
    if name=='hotaru8' and len(own)>1:
        if era is None:return tuple(own)
        return next(f for f in own if f.endswith('C.C' if era=='C' else 'D.C'))
    # R8 act_tbl entry 29 is bobin (ACT81A/ACT82A/ACT83.C) but the PC R8 build
    # links no BOBIN.C. The retail R8 programs carry R3/BOBIN.C's routine: R83C
    # bobin ($20999C) matches R31A's ($20AD9E) in 242 of its first 256 words,
    # the others being absolute addresses.
    if name=='bobin' and rnd==8 and not own:return 'R3/BOBIN.C'
    if name=='screw' and len(own)>1:
        if era is None:return tuple(own)
        return next(f for f in own if f.endswith('_C.C' if era in 'CD' else '_A.C'))
    if len(own)>1:
        tagged=lambda f,a:re.search(rf'(?<!\d){rnd}{a}(?!\d)',Path(f).stem) is not None
        pick=[f for f in own if act is not None and tagged(f,act)] or [f for f in own if not any(tagged(f,a) for a in (1,2,3))]
        if len(pick)!=1:raise SystemExit(f'R{rnd} act {act} defines {name} in {own}')
        return pick[0]
    if own:return own[0]
    common=[f for f in files if '/' not in f]
    if len(common)>1:raise SystemExit(f'{name} is defined in several shared files: {common}')
    return common[0] if common else None

def port_types(tables):
    """Retail routine name -> port type, from Palmtree Panic's Act 1 and 2 tables."""
    result={}
    for kind in sorted(SUPPORTED):
        names={routine(tables,k,kind) for k in ('ACT11A','ACT11B','ACT12A')}-{'noact'}
        if len(names)>1:raise SystemExit(f'port type {kind} names {names} in Palmtree Panic')
        for name in names:
            if name in result:raise SystemExit(f'{name} backs port types {result[name]} and {kind}')
            result[name]=kind
    return result

def eras_of(act):return 'CD' if act==3 else 'ABCD'

def routines_in(tables,rnd,act):
    """Every routine name some era of this act can dispatch to."""
    return {name for era in eras_of(act) for name in tables[table_for(tables,rnd,act,era)]}

def layout_bytes(rnd,act):
    files=[HARVEST/f'{rnd}/objects{rnd}{act}{e}.bin' for e in eras_of(act)]
    data={f.read_bytes() for f in files}
    if len(data)!=1:raise SystemExit(f'R{rnd}{act}: era object files differ')
    return data.pop()

# Per-round clones that have been read side by side with the definition the port
# was ported from and found to behave the same for everything the port models.
# Each entry names the clone's file and says what differs.  Anything not listed
# here is dropped until someone does the same reading for it.
VETTED_CLONES={
    # R4/PLAYSUB4.C marker has a body identical to PLAYSUB.C's. marker_init
    # differs in one line: the star-ball child keeps its parent pointer at
    # ((sprite_status**)wk)[13] instead of actfree[6]. Only R4's own child
    # routine reads it back, and the port's checkpoint does not model the child's
    # parent link, so the difference cannot reach the port.
    ('marker','R4/PLAYSUB4.C'),
}

# Zone objects the port implements from a round's own source (src/objects_*.inc).
# routine: (port type, the file its handler was ported from, subtype flag, keeps
# the secondary byte).  A routine resolves only when this round and act link that
# same file. wall73 uses its R7 zone-local actor; wall7 keeps the shared wall
# actor. Both routines occur in ACT73.C. The secondary byte is userflag.b.l.
ZONE_TYPES={
    'bobin':(29,'R3/BOBIN.C',0,False),
    'frip':(30,'R3/BOBIN.C',0,False),
    'for3':(72,'R3/TRAP_R3.C',0,False),
    'harir3':(73,'R3/TRAP_R3.C',0,False),
    'frdr3':(74,'R3/TRAP_R3.C',0,False),
    'trapdr3':(75,'R3/TRAP_R3.C',0,False),
    'getdair3':(76,'R3/TRAP_R3.C',0,False),
    'gandair3':(77,'R3/TRAP_R3.C',0,False),
    'ga':(78,'R3/GA3.C',0,False),
    'tentou':(79,'R3/TENTOU.C',0,False),
    'ene_kama':(80,'R3/KAMA.C',0,False),
    'banpa':(82,'R3/BANPA.C',0,False),
    'pocket':(84,'R3/POCKET.C',0,False),
    'et':(86,'R3/ET3.C',0,False),
    'togeball':(83,('R3/TOGEBL3A.C','R3/TOGEBL3B.C','R3/TOGEBL3D.C'),0,False),
    'drumr3':(87,'R3/TRAP_R3.C',0,False),
    'movie':(88,'R3/MOVIE3.C',0,False),
    'friend':(89,'R3/FRIEND3.C',0,False),
    'emie3':(90,'R3/MECASNC.C',0,False),
    'hari3x':(91,'R3/MECASNC.C',0,False),
    'sikake33':(93,'R3/SIKAKE33.C',0,False),
    # BOSS_3.C: both boss actors spawn through SCD_OBJ_BOSS (src/boss.c
    # scd_boss_create_sub); subtype bit 6 is egg3dai_l, bit 5 egg3dai_s.
    'egg3dai_l':(66,'R3/BOSS_3.C',64,False),
    'egg3dai_s':(66,'R3/BOSS_3.C',32,False),
    # BOSS_4.C/BOSS_4_2.C/WALL4.C: src/boss.c scd_boss_create_sub picks the
    # actor from subtype bit 4 (egg4air), 3 (egg4), 2 (wall4) and strips it.
    'egg4air':(66,'R4/BOSS_4.C',16,False),
    'egg4':(66,'R4/BOSS_4_2.C',8,False),
    'wall4':(66,'R4/WALL4.C',4,False),
    # src/boss.c scd_boss_create_sub with the explicit round: R5 bit 0
    # egg5hari, bit 1 egg5meca1; R6/R7 have one layout boss each.
    'egg5hari':(66,'R5/BOSS_5.C',1,False),
    'egg5meca1':(66,'R5/BOSS_5.C',2,False),
    'egg6boss':(66,'R6/BOSS_6.C',0,False),
    'egg7':(66,'R7/BOSS_7.C',0,False),
    # R6 zone-local: objects.c hands both userflag bytes to scd_boss6_door.
    'egg6door':(136,'R6/BOSS_6.C',0,True),
    # Wacky Workbench (R6) actors, zone-local (src/scd_objects.h SCD_OBJ_R6_*).
    'dair6':(137,'R6/DAIR6.C',0,True),
    'beem6':(138,'R6/BEEM6.C',0,True),
    'kdai6':(139,'R6/KDAI6.C',0,True),
    'tobidai6':(140,'R6/TOBIDAI6.C',0,True),
    'block6':(141,'R6/BLOCK6.C',0,True),
    'batta':(142,'R6/BATTA.C',0,True),
    'hachi6':(143,'R6/HACHI6.C',0,True),
    'semi':(144,'R6/SEMI.C',0,True),
    'minomusi':(145,'R6/MINOMUSI.C',0,True),
    'optbr6':(146,'R6/TRAP_R6.C',0,True),
    'seesaw6':(147,'R6/SEESAW6.C',0,True),
    'tobira6':(148,'R6/TOBIRA6.C',0,True),
    'piston6':(149,'R6/PISTON6.C',0,True),
    'sw6':(150,'R6/SW6.C',0,True),
    'udblk6':(151,'R6/UDBLK6.C',0,True),
    'eggz6':(152,'R6/EGG6.C',0,True),
    'gas':(153,'R6/SHOOT6.C',0,True),
    'catapalt':(154,'R6/SHOOT6.C',0,True),
    'megami':(155,'R6/SHOOT6.C',0,True),
    'wall1':(67,'R4/WALL1.C',0,False),
    'wall7':(68,'R7/WALL7.C',0,False),
    'wall73':(139,'R7/WALL73.C',0,True),
    'dair5':(69,'R5/DAI_RD5.C',0,False),
    'konbea':(70,'R8/KONBEA.C',0,True),
    'piston':(71,'R8/PISTON.C',0,False),
    # Tidal Tempest (R4). SCREW_A/C, KUZURE4 read userflag.b.l (switch/flag).
    'friend4':(94,'R4/FRIEND4.C',0,False),
    'awa':(95,'R4/AWA.C',0,False),
    'tonbo':(96,'R4/TONBO.C',0,False),
    'tagameb':(97,'R4/TAGAMEB4.C',0,False),
    'screw':(98,'R4/SCREW_A.C',0,True),
    'sw4':(99,'R4/SW4.C',0,False),
    'harir4':(100,'R4/HARIR4.C',0,False),
    'yago':(101,'R4/YAGO.C',0,False),
    'escal4':(102,'R4/ESCAL4.C',0,False),
    'rblk4':(103,'R4/RBLK4.C',0,False),
    'harid4':(104,'R4/HARID4.C',0,False),
    'amenbo':(105,'R4/AMENBO.C',0,False),
    'udblk4':(106,'R4/UDBLK4.C',0,False),
    'tekkyu4':(107,'R4/TEKKYU4.C',0,False),
    'kuzure4':(108,'R4/KUZURE4.C',0,True),
    'tobira4':(109,'R4/TOBIRA4.C',0,False),
    'renketu4':(110,'R4/RENKETU4.C',0,False),
    'swgun4':(111,'R4/SWGUN4.C',0,False),
    'brunko4':(112,'R4/BRUNKO4.C',0,False),
    'lrblk4':(113,'R4/LRBLK4.C',0,False),
    'movie4':(114,'R4/MOVIE4.C',0,False),
    'swblkr4':(115,'R4/SWBLK4.C',0,False),
    'walls':(116,'R4/WALLS.C',0,False),
    'tekkyu':(117,'R4/TEKKYU.C',0,False),
    'tekkyu1':(118,'R4/TEKKYU1.C',0,False),
    'funsui4':(119,'R4/FUNSUI4.C',0,False),
    'bou':(120,'R4/PLAYSUB4.C',0,False),
    'tobiras4':(121,'R4/TOBIRAS4.C',0,False),
    'osumizu':(122,'R4/OSUMIZU.C',0,False),
    'baneiwa':(123,'R4/BANEIWA.C',0,False),
    'daid4':(124,'R4/DAID4.C',0,False),
    'wall42':(125,'R4/WALL42.C',0,False),
    'ukidai':(126,'R4/UKIDAI.C',0,False),
    # R7 ACTSET loads both userflag bytes (ACTSET.C); retain both for every actor.
    'emie7':(136,'R7/EMIE7.C',0,True),
    'hari73':(138,'R7/HARI73.C',0,True),
    'gaitou73':(140,'R7/GAITOU73.C',0,True),
    'chgban':(141,'R7/CHGBAN.C',0,True),
    'spring_r':(142,'R7/CHGBAN.C',0,True),
    'gun7':(143,'R7/CHGBAN.C',0,True),
    'slight7':(145,'R7/SLIGHT7.C',0,True),
    'tekkyu7':(146,'R7/TEKKYU7.C',0,True),
    'tekkyu7j':(147,'R7/TEKKYU7J.C',0,True),
    'chgwall7':(148,'R7/CHGWALL7.C',0,True),
    'hotaru7':(149,'R7/HOTARU7.C',0,True),
    'kabasira':(150,'R7/KABASIRA.C',0,True),
    'kanabun':(151,'R7/KANABUN.C',0,True),
    'dango':(152,'R7/DANGO7.C',0,True),
    'branko7':(153,'R7/BRANKO7.C',0,True),
    # Quartz Quadrant (R5), zone-local ids (src/scd_objects.h SCD_OBJ_R5_*).
    # The original always loads userflag.b.l, so every R5 row keeps it.
    'denden':(136,'R5/DENDEN.C',0,True),
    'sasori':(137,'R5/SASORI.C',0,True),
    'kemusi':(138,'R5/KEMUSI.C',0,True),
    'kumo':(139,'R5/KUMO.C',0,True),
    'iwa5':(140,'R5/IWA5.C',0,True),
    'hari5f':(141,'R5/HARI5F.C',0,True),
    'harir5':(142,'R5/HARIR5.C',0,True),
    'iwa5roll':(143,'R5/IWA5ROLL.C',0,True),
    'kuzure5':(144,'R5/KUZURE5.C',0,True),
    'iwa5wave':(145,'R5/IWA5WAVE.C',0,True),
    'buranko5':(146,'R5/BURANKO5.C',0,True),
    'hasira5':(147,'R5/HASIRA5.C',0,True),
    'hashi5':(148,'R5/HASHI5.C',0,True),
    'beltsw5':(149,'R5/BELTSW5.C',0,True),
}
# A routine name a round defines again, ported separately: (name, the file this
# round links) -> (port type, subtype flag, keeps the secondary byte).
ZONE_CLONES={
    # Metallic Madness (R8), zone-local ids from 157 (SS uses 136-156):
    # src/scd_objects.h SCD_OBJ_R8_*. ACT81A/ACT82A/ACT83 each serve all eras
    # of their act; ACTSET loads both userflag bytes, so every row keeps them.
    # A routine an act links from its own TRAP_R8x.C maps to the one native
    # actor (src/objects_mm.inc) that the actor fixtures test for every act.
    **{('togedair8',f'R8/TRAP_R8{a}.C'):(157,0,True) for a in (1,2,3)},
    ('dai8','R8/DAI8.C'):(158,0,True),
    ('nokogiri','R8/NOKOGIRI.C'):(159,0,True),
    ('kuzure8','R8/KUZURE8.C'):(160,0,True),
    ('propera','R8/PROPERA8.C'):(161,0,True),
    ('koma8','R8/KOMA8.C'):(162,0,True),
    ('futagor8','R8/TRAP_R81.C'):(163,0,True),
    ('scarab','R8/SCARAB.C'):(164,0,True),
    ('kabuto','R8/KABUTO8.C'):(165,0,True),
    ('okusieso','R8/OKUSIESO.C'):(166,0,True),
    ('hachi8','R8/HACHI8.C'):(167,0,True),
    ('friend','R8/FRIEND8.C'):(168,0,True),
    ('et','R8/ET8.C'):(169,0,True),
    ('shooter','R8/SHOOT.C'):(170,0,True),
    ('beam','R8/BEAM.C'):(171,0,True),
    ('pipe8','R8/PIPE8.C'):(172,0,True),
    ('haguruma','R8/HAGURUMA.C'):(173,0,True),
    ('bigbom','R8/BIGBOM8.C'):(174,0,True),
    ('legmeca','R8/LEGMECA8.C'):(175,0,True),
    ('tobira','R8/TOBIRA.C'):(176,0,True),
    ('dango','R8/DANGO8.C'):(177,0,True),
    ('kaiten','R8/SHUT.C'):(178,0,True),
    ('sw','R8/SW8.C'):(179,0,True),
    **{('togeita',f'R8/TRAP_R8{a}.C'):(180,0,True) for a in (2,3)},
    ('gater8','R8/TRAP_R82.C'):(181,0,True),
    ('chibi_coli','R8/PLAYSP8.C'):(182,0,True),
    **{('hotaru8',f):(183,0,True) for f in ('R8/HOTA8C.C','R8/HOTA8D.C')},
    ('jettoge','R8/JETTOGE8.C'):(184,0,True),
    ('shut','R8/SHUT.C'):(185,0,True),
    ('konbea','R8/KONBEA83.C'):(186,0,True),
    ('anar8','R8/TRAP_R81.C'):(187,0,True),
    # Registers the R8 noact placeholder id (translate maps noact to it); the
    # key names no routine, so no other round's lookup reaches it.
    ('r8_noact','R8/ACT81A.C'):(189,0,False),
    ('friend','R7/FRIEND7.C'):(154,0,True),
    ('et','R7/ET7.C'):(155,0,True),
    ('movie','R7/MOVIE7.C'):(156,0,True),
    ('et','R4/ET4.C'):(127,0,False),
    ('screw','R4/SCREW_C.C'):(65,0,True),
    ('shooter','R5/SHOOT5.C'):(150,0,True),
    ('movie','R5/MOVIE5.C'):(151,0,True),
    ('friend','R5/FRIEND5.C'):(152,0,True),
    ('et','R5/ET5.C'):(153,0,True),
    ('kowasi','R5/KOWASI5.C'):(154,0,True),
    ('shooter','R6/SHOOT6.C'):(156,0,True),
    ('friend','R6/FRIEND6.C'):(157,0,True),
    ('et','R6/ET6.C'):(158,0,True),
    ('movie','R6/MOVIE6.C'):(159,0,True),
    # One native type; TOGEBL6A/B/D.C are the Present/Past/Bad Future builds.
    ('togeball',('R6/TOGEBL6A.C','R6/TOGEBL6B.C','R6/TOGEBL6D.C')):(160,0,True),
}
# Port ids 1-135 are global. 136-254 are zone-local (src/scd_objects.h
# SCD_OBJ_ZONE_LOCAL_FIRST): rounds 5-8 each reuse them, so a local port is
# unique within its round only and resolves only in the round its file is from.
ZONE_LOCAL=range(136,255)
def origin_round(origin):
    return int((origin if isinstance(origin,str) else origin[0])[1])
def _zone_rows():
    for name,(port,origin,_,keep) in ZONE_TYPES.items():yield name,port,origin_round(origin),keep
    for (name,origin),(port,_,keep) in ZONE_CLONES.items():yield name,port,origin_round(origin),keep
def _check_zone_ids():
    seen={}
    for name,port,rnd,keep in _zone_rows():
        assert 1<=port<=254,(name,port)
        assert not (rnd==8 and port in ZONE_LOCAL and port<157),(name,port,'R8 local ids avoid the SS range 136-156')
        # MM production ids are 157-188; 189 is only the noact slot placeholder.
        assert not (rnd==8 and port in ZONE_LOCAL and port>188 and (port,name)!=(189,'r8_noact')),(name,port,'R8 local ids are 157-188, plus 189 for r8_noact')
        # Global ports may be shared on purpose (the boss 66).
        if port in ZONE_LOCAL:
            assert rnd>=5,(name,port,'zone-local ids are for rounds 5-8')
            assert seen.get((rnd,port),name)==name,(name,port,seen.get((rnd,port)),'zone-local id reused within a round')
            seen[(rnd,port)]=name
_check_zone_ids()
def extra_for(rnd):
    """{port: keeps secondary byte} of every zone type this round can place.
    Type 66 (the boss) is already a Palmtree Panic type."""
    return {port:keep for _,port,r,keep in _zone_rows() if port!=66 and (port not in ZONE_LOCAL or r==rnd)}
def port_names(rnd):
    """{port: routine} for this round (global ports plus its own local ones)."""
    return {port:name for name,port,r,_ in _zone_rows() if port!=66 and (port not in ZONE_LOCAL or r==rnd)}
EXTRA={port:keep for _,port,_,keep in _zone_rows() if port!=66 and port not in ZONE_LOCAL}
CLONE_NAMES={name for name,_ in ZONE_CLONES}

def translate(rnd,act,tables,ports,defs):
    """Returns (placements, report) for one act of one round.

    A routine resolves to a port type only when this round links the SAME source
    definition that the port's handler was ported from.  Six routines are
    defined again per round (shooter, friend, et, marker, futa, kowasi); a tube
    handler built on Palmtree Panic's paths would send Sonic along the wrong
    route in R5, so those clones are dropped here and listed in the report
    until each one is checked on its own."""
    extra=extra_for(rnd)
    # MM: ITEM.C (monitors and time posts, port 25) reads userflag.b.l as the
    # layer when stageno is 6 (ITEM.C:239,274,338-342,390), so R8 keeps it.
    if rnd==8:extra={**extra,25:True}
    out=bytearray();dropped=collections.Counter();clones=collections.Counter()
    split=0;kept=collections.Counter();outside=0
    for x,y,kind,sub,eras,secondary in struct.iter_unpack('>HHBBBB',layout_bytes(rnd,act)):
        if x==65535:break
        saved=kind&128
        kind&=127
        if not kind:continue
        # No stage is taller than 2048 lines. R12A carries one ring at Y 3392.
        if (y&4095)>=2048:outside+=1;continue
        by_type=collections.defaultdict(int)
        for era in eras_of(act):
            bit=ERA_BIT[era]
            if not (eras>>5)&bit:continue
            name=routine(tables,table_for(tables,rnd,act,era),kind)
            flag=0
            # A round-specific implementation can share a routine name with
            # PPZ (notably et). Keep the original shared handler in PPZ while
            # selecting the independently implemented clone in its own round.
            # R8 noact (ACT81A.C:171, ACT82A/ACT83.C: frameout) still takes a slot
            # when ACTSET loads it and frees it in its first update (retail MM1A
            # 3335: a propera loads into 64 though 32 is free before and after).
            if rnd==8 and name=='noact':
                port,flag=189,0
            elif name in CLONE_NAMES and (name,linked(defs,rnd,name,act,era)) in ZONE_CLONES:
                port,flag,_=ZONE_CLONES[(name,linked(defs,rnd,name,act,era))]
            elif name in ZONE_TYPES and not (name in ports and linked(defs,rnd,name,act)==linked(defs,1,name)):
                port,origin,flag,_=ZONE_TYPES[name]
                if linked(defs,rnd,name,act,era)!=origin:clones[name]+=1;continue
            else:
                port=ports.get(name)
                if port is None:dropped[name]+=1;continue
                source=linked(defs,rnd,name,act)
                if source!=linked(defs,1,name) and (name,source) not in VETTED_CLONES:clones[name]+=1;continue
            by_type[(port,flag)]|=bit
        if len(by_type)>1:split+=1
        for (port,flag),mask in by_type.items():
            kept[port]+=1
            # Tunnels and the script-driven zone objects keep their secondary byte;
            # placements() rejects it elsewhere, and no other routine reads it.
            keep=port==7 or extra.get(port,False)
            # The implemented rounds keep retail record order (Object Spawner.asm walks
            # the x-sorted layout) and the saved-flags bit (Y bit 12, see placements).
            out+=struct.pack('>HHBBBB',x,(y|(4096 if saved and rnd in (1,3,4,5,6,7,8) else 0)),port,sub|flag,(eras&31)|(mask<<5),secondary if keep else 0)
    out+=struct.pack('>HHBBBB',65535,0,0,0,0,0)
    # Every round keeps the x-sorted record order (Object Spawner.asm walks the
    # layout in order, so slot order follows it). Palmtree Panic (only checked
    # here against tools/convert_objects.py), Collision Chaos, Tidal Tempest
    # Quartz Quadrant, Wacky Workbench and Stardust Speedway use the spawner (src/objects.c
    # tt_stream) and keep the saved-flag and ring-member bits too: R33D's
    # monitor at X=528 runs before the spring under it; R51A's iwa5 takes slot
    # 32 before the side spring in 33 (Object Solid.asm StandOnObject).
    entries,unsupported=placements(bytes(out),ordered=False,extra=extra,retail_order=rnd in (1,3,4,5,6,7,8))
    return entries,{'kept_records':dict(sorted(kept.items())),'dropped_routines':dict(dropped.most_common()),
                    'per_round_clones':dict(clones.most_common()),'split_records':split,
                    'outside_stage':outside,'placements':len(entries)}

# scd_placement is {int16 x,y; uint8 type,subtype,flags,eras,secondary}: nine
# bytes, padded to ten.  src/objects.c asserts the size.
RECORD=struct.Struct('>hhBBBBBx')

def encode(entries):
    return b''.join(RECORD.pack(*(e if len(e)==7 else e+(0,))) for e in entries)

def all_layouts():
    tables=act_tables();ports=port_types(tables);defs=definitions()
    return {(rnd,act):translate(rnd,act,tables,ports,defs) for rnd in ROUNDS if rnd!=1 for act in (1,2,3)}

if __name__=='__main__':
    for (rnd,act),(entries,report) in all_layouts().items():
        print(f"R{rnd}{act}: {report['placements']:4} placements, {sum(report['kept_records'].values()):4} records kept, "
              f"{sum(report['dropped_routines'].values()):4} unimplemented, "
              f"clones {report['per_round_clones'] or '-'}")
