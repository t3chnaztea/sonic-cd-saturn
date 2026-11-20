#!/usr/bin/env python3
"""Checks for tools/object_layouts.py: the act_tbl mapping, the translation, and
that no zone's record is spawned as a different object."""
import collections,re,struct,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import object_layouts as L

TABLES=L.act_tables();PORTS=L.port_types(TABLES);DEFS=L.definitions()

class ObjectLayouts(unittest.TestCase):
    def test_programs_use_the_table_their_suffix_names(self):
        """Every record a program can see resolves to a real routine in that
        program's table.  Nine record-eras do not, and each of those also lands
        on noact in retail: R42B's id 40 at X 2432, visible in the Past, and
        R81's two id 49 records at X 3743 and X 5020, visible in all four eras."""
        misses=[]
        for rnd in L.ROUNDS:
            for act in (1,2,3):
                for x,y,kind,sub,eras,secondary in struct.iter_unpack('>HHBBBB',L.layout_bytes(rnd,act)):
                    if x==65535:break
                    kind&=127
                    if not kind:continue
                    for era in L.eras_of(act):
                        if not (eras>>5)&L.ERA_BIT[era]:continue
                        if L.routine(TABLES,L.table_for(TABLES,rnd,act,era),kind)=='noact':
                            misses.append((rnd,act,era,kind,x))
        self.assertEqual(sorted(misses),sorted([(4,2,'B',40,2432)]+
            [(8,1,e,49,x) for e in 'ABCD' for x in (3743,5020)]))

    def test_palmtree_panic_act_2_reproduces(self):
        """Translating retail R12A through this pipeline gives the port's existing
        Act 2 placements.  The one difference is documented in convert_objects.py:
        it sends R12A's four eda records to a type it then drops."""
        mine,_=L.translate(1,2,TABLES,PORTS,DEFS)
        mine=[e if len(e)==7 else e+(0,) for e in mine]
        text=(ROOT/'assets/generated/objects2.inc').read_text()
        theirs=[tuple(map(int,m.group(1).split(','))) for m in re.finditer(r'\{(-?\d+(?:,-?\d+){6})\}',text)]
        extra=[e for e in mine if e not in theirs]
        self.assertEqual([e for e in theirs if e not in mine],[])
        self.assertEqual(len(extra),4)
        self.assertEqual({e[2] for e in extra},{50})
        self.assertEqual([e for e in mine if e[2]!=50],[e for e in theirs if e[2]!=50])

    def test_only_shared_definitions_reach_other_zones(self):
        """A record resolves only when its round links the same source definition
        the port's handler came from.  Per-round clones such as shooter, whose tube
        paths differ in every round that has one, never come through."""
        for (rnd,act),(entries,report) in L.all_layouts().items():
            same={PORTS[n] for n in PORTS if n in {r for r in L.routines_in(TABLES,rnd,act)}
                  and (L.linked(DEFS,rnd,n,act)==L.linked(DEFS,1,n) or (n,L.linked(DEFS,rnd,n,act)) in L.VETTED_CLONES)}
            same|={port for n,(port,origin,_,_) in L.ZONE_TYPES.items()
                   if n in L.routines_in(TABLES,rnd,act)
                   and any(L.linked(DEFS,rnd,n,act,e)==origin for e in L.eras_of(act))}
            same|={port for (n,origin),(port,_,_) in L.ZONE_CLONES.items()
                   if n in L.routines_in(TABLES,rnd,act)
                   and any(L.linked(DEFS,rnd,n,act,e)==origin for e in L.eras_of(act))}
            # R8 noact (ACT81A.C:171 frameout) still takes a slot when ACTSET loads
            # it (retail MM1A 3335), so R8 keeps its records as the placeholder
            # SCD_OBJ_R8_NOACT (189), and only where the act's table has noact.
            if rnd==8 and 'noact' in L.routines_in(TABLES,rnd,act):same|={189}
            with self.subTest(rnd=rnd,act=act):
                self.assertLessEqual({e[2] for e in entries},same)
                self.assertNotIn(PORTS['shooter'],{e[2] for e in entries})

    def test_metallic_madness_piston_is_not_a_spin_tag(self):
        """R8 id 52 is piston.  Palmtree Panic's id 52 is the spin tag, which is
        exactly the object a global id table would put there."""
        entries,_=L.all_layouts()[(8,2)]
        here=[e for e in entries if (e[0],e[1])==(432,1182)]
        self.assertTrue(here)
        self.assertEqual({e[2] for e in here},{71})

    def test_zone_objects_resolve_only_in_their_own_act(self):
        """wall73 is R7 Act 3's zone-local actor and keeps its script byte;
        R8 Act 3 links KONBEA83.C, not the KONBEA.C global actor 70: it takes
        the R8 zone-local konbea83 actor, and Acts 1-2 keep actor 70."""
        layouts=L.all_layouts()
        act3=[e for e in layouts[(7,3)][0] if e[2]==139]
        self.assertTrue(act3)
        self.assertTrue(all(not e[3]&128 for e in act3))
        self.assertTrue(any(len(e)==7 and e[6] for e in act3))
        self.assertFalse([e for a in (1,2) for e in layouts[(7,a)][0] if e[2]==139])
        self.assertNotIn(70,{e[2] for e in layouts[(8,3)][0]})
        self.assertNotIn('konbea',layouts[(8,3)][1]['per_round_clones'])
        self.assertIn(186,{e[2] for e in layouts[(8,3)][0]})
        self.assertFalse([e for a in (1,2) for e in layouts[(8,a)][0] if e[2]==186])
        self.assertTrue([e for a in (1,2) for e in layouts[(8,a)][0] if e[2]==70])

    def test_tidal_tempest_resolves_every_placed_routine(self):
        """Every R4 routine a layout places resolves to a port type, except the
        Act 3 boss actors (wall4, egg4air, egg4) and R42B's one noact record.
        SCREW_A.C serves the Present and Past, SCREW_C.C both Futures."""
        layouts=L.all_layouts()
        self.assertEqual(layouts[(4,1)][1]['dropped_routines'],{})
        self.assertEqual(layouts[(4,2)][1]['dropped_routines'],{'noact':1})
        self.assertEqual(layouts[(4,3)][1]['dropped_routines'],{})
        boss=sorted((e[0],e[1],e[3]) for e in layouts[(4,3)][0] if e[2]==66)
        self.assertEqual({sub&28 for _,_,sub in boss},{16,8,4})
        for act in (1,2):
            self.assertEqual(layouts[(4,act)][1]['per_round_clones'],{})
            by_type={}
            for e in layouts[(4,act)][0]:by_type[e[2]]=by_type.get(e[2],0)|e[5]
            self.assertEqual(by_type[98]&4,0)   # SCREW_A never in a Future
            self.assertEqual(by_type[65]&3,0)  # SCREW_C only in the Futures
        self.assertEqual(L.linked(DEFS,4,'screw',1,'B'),'R4/SCREW_A.C')
        self.assertEqual(L.linked(DEFS,4,'screw',2,'D'),'R4/SCREW_C.C')

    def test_installed_layouts_are_current(self):
        for (rnd,act),(entries,_) in L.all_layouts().items():
            prefix={3:'cc',4:'tt',5:'qq',6:'ww',7:'ss',8:'mm'}[rnd]
            with self.subTest(rnd=rnd,act=act):
                path=ROOT/f'assets/generated/{prefix}obj{rnd}{act}.bin'
                self.assertEqual(path.read_bytes(),L.encode(entries),f'{path} is stale; run tools/install_zone_packs.py')
                self.assertLessEqual(len(entries),1024)

    def test_zone_local_ids_stay_in_their_round(self):
        """136-254 are reused per round (src/scd_objects.h): CC/TT and PPZ
        layouts never carry one, a round's layout carries only its own, and
        the C header agrees on the range."""
        header=(ROOT/'src/scd_objects.h').read_text()
        self.assertIn('SCD_OBJ_ZONE_LOCAL_FIRST=136, SCD_OBJ_ZONE_LOCAL_LAST=254',header)
        self.assertEqual((L.ZONE_LOCAL.start,L.ZONE_LOCAL.stop),(136,255))
        for (rnd,act),(entries,_) in L.all_layouts().items():
            local={e[2] for e in entries if e[2] in L.ZONE_LOCAL}
            if rnd<5:self.assertFalse(local,(rnd,act))
            own={p for p,_ in L.extra_for(rnd).items() if p in L.ZONE_LOCAL}
            self.assertLessEqual(local,own,(rnd,act))
        for rnd in (5,6,7,8):
            names=L.port_names(rnd)
            for port in names:
                if port in L.ZONE_LOCAL:self.assertTrue(any(n==names[port] and L.origin_round(o)==rnd for n,(p,o,_,_) in L.ZONE_TYPES.items() if p==port)
                                                        or any(n==names[port] and L.origin_round(o)==rnd for (n,o),(p,_,_) in L.ZONE_CLONES.items() if p==port))

if __name__=='__main__':unittest.main()
