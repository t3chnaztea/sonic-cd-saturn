#!/usr/bin/env python3
"""Object format, original placement filtering, and texture decoding checks."""
import struct,unittest
from convert_objects import placements,DATA,OUT
def unpack_texture(data):
    result=bytearray();position=0
    while position<len(data):
        code,=struct.unpack_from('>H',data,position);position+=2
        count=code&32767
        if not count:raise ValueError('empty texture command')
        length=count*2 if code&32768 else 2
        payload=data[position:position+length]
        if len(payload)!=length:raise ValueError('truncated texture command')
        result.extend(payload if code&32768 else payload*count);position+=length
    return bytes(result)
class ObjectAssets(unittest.TestCase):
    def test_monitor_composition(self):
        from monitor_pixels import source_monitor
        from convert_objects import draw,assembly_frames,nemesis,palette
        path=DATA/'_Objects/Monitor and Time Post/Data'
        maps=assembly_frames(path/'Mappings.asm');art=nemesis((path/'Art.nem').read_bytes())
        colors=palette((DATA/'_Objects/Sonic/Data/Palette.bin').read_bytes())
        changes=[]
        for frame,index in enumerate(list(range(10))+[16,17]):
            expected=source_monitor(frame)
            actual=draw(maps[index],art,colors,32,first_piece_front=True)
            self.assertEqual(actual,expected,frame)
            old=source_monitor(frame,legacy_last=True)
            changes.append(sum(old[p:p+2]!=expected[p:p+2] for p in range(0,len(old),2)))
        self.assertEqual(changes,[212,92,156,99,100,142,92,100,224,224,0,0])
        # Eight distinct item screens, not eight copies of a blank TV.
        self.assertEqual(len({source_monitor(n) for n in range(8)}),8)

    def test_amy_source_records_and_scripts(self):
        from amy_reference import animations,animate,heart,fingerprint,spawns
        items,unknown=placements((DATA/'Palmtree Panic/Data/Objects (Act 1).bin').read_bytes())
        self.assertEqual([e for e in items if e[2]==47],[(9664,488,47,0,0,2)])
        self.assertEqual(dict(unknown),{})
        self.assertEqual([sum(t+1 for _,t in a) for a in animations()],[40,48,14,10,20,140])
        self.assertEqual([fingerprint(animate([a]*600)) for a in range(6)],[573075661,3022303949,1767625934,3614301989,1650632269,401554217])
        self.assertEqual(fingerprint(animate([5]*19+[2]*43+[3]*61+[1]*91+[4]*131+[0]*29)),1329432561)
        self.assertEqual([fingerprint(heart(*f)) for f in [(0,0),(0x1234,0x5678)]],[86686320,1824742068])
        self.assertEqual(spawns(256),( [43,86,128,171,214,256],0))
        self.assertEqual(spawns(256,True),(list(range(16,257,16)),0))
        self.assertRegex((DATA/'Palmtree Panic/Data (Act 1 Present).asm').read_text(),r'dc\.l\s+Art_AmyRose\s*dc\.w\s+\$6E00')

    def test_amy_heart_and_idle_pixels(self):
        import re
        from convert_objects import assembly_frames,nemesis,draw,palette
        from convert_assets import sonic_frame
        text=(OUT/'object-frames.inc').read_text();raw=unpack_texture((OUT/'object-art.bin').read_bytes())
        def array(name):return list(map(int,re.search(name+r'\[\]=\{([^}]+)',text)[1].split(',')))
        offsets,widths,heights,tops,banks,priority=[array(n) for n in ['object_raw_offsets','object_widths','object_heights','object_tops','object_stage_palette','object_high_priority']]
        self.assertEqual(banks[286:310],[1]*17+[0]*7);self.assertEqual(priority[286:310],[0]*24)
        # Act 2 swing (stage line 2) and results act-number frames (common palette).
        # Results tiles carry the priority bit (Results/Main.asm:84 oTile $83C4).
        self.assertEqual(banks[310:315],[2,2,2,0,0]);self.assertEqual(priority[310:315],[0,0,0,1,1])
        # Act 2 collapsing platforms (ledge, single-row, pieces 1 and 2) on stage line 2.
        self.assertEqual(banks[315:327],[2]*12);self.assertEqual(priority[315:327],[0]*12)
        # Act 2 past/future springboard on Sonic's palette line.
        self.assertEqual(banks[327:333],[0]*6);self.assertEqual(priority[327:333],[0]*6)
        # Act 3 boss: Robotnik and the body's line-0 pieces on Sonic's line, the body's front
        # piece and the parts on stage line 1; capsule on line 1; seed and grown flower frames.
        self.assertEqual(banks[333:358],[0]*12+[1]*13);self.assertEqual(banks[358:367],[1]*9)
        self.assertEqual(banks[367:375],[0]*4+[1]*4);self.assertEqual(banks[375:380],[0]*5);self.assertEqual(priority[333:392],[0]*42+[1,1]+[0]*15)  # 375-376: results act 3 line (catalog 212)
        # Big ring on stage line 1; its flash on Sonic's line.
        self.assertEqual(banks[380:392],[1]*4+[0]*8)
        path=DATA/'Palmtree Panic/Objects/Amy Rose/Data';maps=assembly_frames(path/'Mappings.asm');art=nemesis((path/'Art.nem').read_bytes())
        common=palette((DATA/'_Objects/Sonic/Data/Palette.bin').read_bytes());marker=struct.pack('>16H',*(0x8000+i for i in range(16)))
        expected=[draw(m,art,marker) for m in maps]+[draw(maps[i],art,common) for i in range(8,11)]+[sonic_frame(i) for i in range(1,5)]
        self.assertEqual(len(expected),24)
        for n,want in enumerate(expected,286):
            w,h,top=widths[n],heights[n],tops[n];packed=raw[offsets[n]:offsets[n]+w*h//2+32];clut=struct.unpack('>16H',packed[-32:]);decoded=bytearray(w*64*2)
            for pos,b in enumerate(packed[:-32]):
                for sub,index in enumerate([b>>4,b&15]):struct.pack_into('>H',decoded,top*w*2+(pos*2+sub)*2,clut[index])
            self.assertEqual(decoded,want,('Amy/heart/idle source frame',n))
        self.assertNotEqual(palette((path/'Palette.bin').read_bytes()),common)

    def test_projector_and_animal_records(self):
        items,unknown=placements((DATA/'Palmtree Panic/Data/Objects (Act 1).bin').read_bytes())
        self.assertEqual([e for e in items if e[2]==46],[(5776,786,46,0,0,1)])
        self.assertEqual(sum(e[2]==36 for e in items),30)
        self.assertEqual([sum(e[2]==36 and bool(e[5]&bit) for e in items) for bit in [2,1,4]],[13,26,25])
        self.assertTrue(all(e[3] in [0,1] and e[4]==0 for e in items if e[2]==36))
        self.assertEqual(dict(unknown),{})
        import re
        source=(DATA/'Palmtree Panic/Data (Act 1 Past).asm').read_text()
        self.assertRegex(source,r'PLC_Cam2_Full:\s*dc\.w\s+0\s*dc\.l\s+Art_Animals\s*dc\.w\s+\$9EE0')
        self.assertRegex(source,r'PLC_Cam3_Full:\s*dc\.w\s+0\s*dc\.l\s+Art_ProjAnimals\s*dc\.w\s+\$9EE0')
        for era,base in [('Present','7100'),('Good Future','8C60'),('Bad Future','8C60')]:
            self.assertRegex((DATA/f'Palmtree Panic/Data (Act 1 {era}).asm').read_text(),r'dc\.l\s+Art_Animals\s*dc\.w\s+\$'+base)

    def test_projector_source_traces(self):
        from projector_reference import animations,explosions,flying,sine
        self.assertEqual(explosions(),[(1,0,0),(5,-18,-10),(10,-10,10),(15,0,-18),(20,-10,18),(22,8,23),(25,13,-10),(28,-3,-25),(30,10,20),(32,-10,2),(35,13,-10),(40,-10,10)])
        self.assertEqual([len(a) for a in animations()],[6,58,4,58,58])
        for holo,expected in [(False,[1532420965,1746721573]),(True,[1246799027,3079872635])]:
            for fractions,h in zip([(0,0),(0x1234,0x5678)],expected):
                rows,actual=flying(holo,1024,*fractions);self.assertEqual(actual,h)
                self.assertEqual(sum(not r[6] for r in rows),32 if holo else 1)
        # The PC sine table contains the same original asymmetric -117 entries.
        import re
        from convert_assets import ROOT
        text=(ROOT/'build/probe-source/etc.c').read_text().split('sintable[320]')[1].split('};')[0]
        self.assertEqual([int(n) for n in re.findall(r'\d+',text)],[n&65535 for n in sine()])

    def test_supported_type_table(self):
        """src/objects.c indexes a byte table instead of comparing every type."""
        import re
        from convert_assets import ROOT
        values=dict(re.findall(r'(SCD_OBJ_\w+)=(\d+)',(ROOT/'src/scd_objects.h').read_text()))
        source=(ROOT/'src/objects.c').read_text()
        table=re.search(r'supported_types\[(\d+)\]=\{(.*?)\};',source,re.S)
        listed=re.findall(r'\[(SCD_OBJ_\w+)\]=1',table[2])
        self.assertEqual(len(listed),len(set(listed)))
        expected={'SCD_OBJ_BIG_RING','SCD_OBJ_CAPSULE','SCD_OBJ_FLOWER','SCD_OBJ_SPRINGBOARD',
                  'SCD_OBJ_SWING','SCD_OBJ_AMY','SCD_OBJ_AMY_HEART','SCD_OBJ_ANIMAL',
                  'SCD_OBJ_PROJECTOR','SCD_OBJ_SPIN_TAG','SCD_OBJ_SCENERY','SCD_OBJ_LOG_SHADOW',
                  'SCD_OBJ_DOOR','SCD_OBJ_DOOR_V','SCD_OBJ_MOVING_SPRING','SCD_OBJ_DISC',
                  'SCD_OBJ_SONIC_HOLE','SCD_OBJ_TUNNEL','SCD_OBJ_COLLAPSE','SCD_OBJ_MONITOR_ITEM',
                  'SCD_OBJ_GOAL','SCD_OBJ_SIGN','SCD_OBJ_WALL','SCD_OBJ_CHECKPOINT',
                  'SCD_OBJ_PLATFORM','SCD_OBJ_FLOAT_BLOCK','SCD_OBJ_RAMP','SCD_OBJ_RAMP_PLANT',
                  'SCD_OBJ_TAMABBOH','SCD_OBJ_MOSQUI','SCD_OBJ_PATABATA','SCD_OBJ_ANTON',
                  'SCD_OBJ_TAGATAGA','SCD_OBJ_GENERATOR','SCD_OBJ_EXPLOSION','SCD_OBJ_TIMEPOST',
                  'SCD_OBJ_SPRING','SCD_OBJ_RING','SCD_OBJ_LOST_RING','SCD_OBJ_BOULDER',
                  'SCD_OBJ_SPIKES','SCD_OBJ_BOBIN','SCD_OBJ_FRIP','SCD_OBJ_FOR3','SCD_OBJ_HARIR3','SCD_OBJ_FRDR3','SCD_OBJ_TRAPDR3','SCD_OBJ_GETDAIR3','SCD_OBJ_GANDAIR3','SCD_OBJ_GA','SCD_OBJ_TENTOU','SCD_OBJ_KAMA','SCD_OBJ_KAMA_BLADE','SCD_OBJ_BANPA','SCD_OBJ_TOGEBALL','SCD_OBJ_POCKET','SCD_OBJ_CC_POINTS','SCD_OBJ_CC_GENERATOR','SCD_OBJ_DRUMR3','SCD_OBJ_MOVIE3','SCD_OBJ_FRIEND3','SCD_OBJ_EMIE3','SCD_OBJ_HARI3X','SCD_OBJ_MECASNC3','SCD_OBJ_SIKAKE33',
                  'SCD_OBJ_TONBO','SCD_OBJ_YAGO','SCD_OBJ_AMENBO','SCD_OBJ_TAGAMEB','SCD_OBJ_HARIR4','SCD_OBJ_HARID4','SCD_OBJ_SCREW','SCD_OBJ_SCREW_F',
                  'SCD_OBJ_OSUMIZU','SCD_OBJ_FUNSUI4','SCD_OBJ_UKIDAI','SCD_OBJ_BOU','SCD_OBJ_AWA','SCD_OBJ_FRIEND4','SCD_OBJ_MOVIE4','SCD_OBJ_ET4',
                  'SCD_OBJ_SW4','SCD_OBJ_ESCAL4','SCD_OBJ_RBLK4','SCD_OBJ_UDBLK4','SCD_OBJ_TEKKYU4','SCD_OBJ_KUZURE4','SCD_OBJ_TOBIRA4',
                  'SCD_OBJ_RENKETU4','SCD_OBJ_SWGUN4','SCD_OBJ_BRUNKO4','SCD_OBJ_LRBLK4','SCD_OBJ_SWBLKR4','SCD_OBJ_WALLS','SCD_OBJ_TEKKYU',
                  'SCD_OBJ_TEKKYU1','SCD_OBJ_TOBIRAS4','SCD_OBJ_BANEIWA','SCD_OBJ_DAID4','SCD_OBJ_WALL42',
                  # Zone objects, src/objects_*.inc.
                  'SCD_OBJ_WALL4','SCD_OBJ_WALL7','SCD_OBJ_DAIR5','SCD_OBJ_KONBEA','SCD_OBJ_PISTON'}
        self.assertEqual(set(listed),expected)
        # enemy() covers exactly the five enemy values the original chain added.
        self.assertEqual(sorted(int(values[n]) for n in
                                ['SCD_OBJ_TAMABBOH','SCD_OBJ_MOSQUI','SCD_OBJ_PATABATA',
                                 'SCD_OBJ_ANTON','SCD_OBJ_TAGATAGA']),[34,61,62,63,64])
        # SCD_OBJ_BOSS spawns through src/boss.c, never through spawn_from.
        self.assertNotIn('SCD_OBJ_BOSS',listed)
        self.assertGreater(int(table[1]),max(int(values[n]) for n in listed))

    def test_projector_animal_pixels(self):
        import re
        from convert_objects import assembly_frames,nemesis,draw,palette
        text=(OUT/'object-frames.inc').read_text();raw=unpack_texture((OUT/'object-art.bin').read_bytes())
        def array(name):return list(map(int,re.search(name+r'\[\]=\{([^}]+)',text)[1].split(',')))
        offsets,widths,heights,tops,banks,priority=[array(n) for n in ['object_raw_offsets','object_widths','object_heights','object_tops','object_stage_palette','object_high_priority']]
        self.assertEqual(banks[257:286],[0]*29)
        self.assertEqual(priority[257:286],[int(263<=n<266 or n>=279) for n in range(257,286)])
        colors=palette((DATA/'_Objects/Sonic/Data/Palette.bin').read_bytes())
        p=DATA/'Palmtree Panic/Objects/Projector/Data';a=DATA/'Palmtree Panic/Objects/Animal/Data';e=DATA/'_Objects/Explosion/Data'
        normal=nemesis((a/'Art.nem').read_bytes());holo=nemesis((p/'Art (Animals).nem').read_bytes());self.assertNotEqual(normal,holo)
        maps=assembly_frames(a/'Mappings (Flying).asm')+assembly_frames(a/'Mappings (Ground).asm')
        cases=[(m,nemesis((p/'Art.nem').read_bytes())) for m in assembly_frames(p/'Mappings.asm')]+[(m,normal) for m in maps]+[(m,holo) for m in maps]+[(m,nemesis((e/'Art.nem').read_bytes())) for m in assembly_frames(e/'Mappings.asm')]
        for n,(mapping,art) in enumerate(cases,257):
            w,h,top=widths[n],heights[n],tops[n]
            for k in range(mapping[0]):
                y,size,hi,lo,x=mapping[1+5*k:6+5*k];x=x if x<128 else x-256;y=y if y<128 else y-256
                self.assertTrue(-w//2<=x and x+(((size>>2)&3)+1)*8<=w//2)
                self.assertTrue(-32<=y and y+((size&3)+1)*8<=32)
            expected=draw(mapping,art,colors,w);packed=raw[offsets[n]:offsets[n]+w*h//2+32]
            clut=struct.unpack('>16H',packed[-32:]);decoded=bytearray(w*64*2)
            for pos,b in enumerate(packed[:-32]):
                for sub,index in enumerate([b>>4,b&15]):struct.pack_into('>H',decoded,top*w*2+(pos*2+sub)*2,clut[index])
            self.assertEqual(decoded,expected,('source frame',n))

    def test_truncation(self):
        with self.assertRaises(ValueError):placements(b'\0'*7)
        with self.assertRaises(ValueError):placements(struct.pack('>HHBBBB',10,20,10,0,224,0))
    def test_order_and_bounds(self):
        terminator=struct.pack('>HHBBBB',65535,0,0,0,0,0)
        for records in [[(30,20,10,0,224,0),(10,20,10,0,224,0)],[(10,2048,10,0,224,0)],[(0,32,16,0x92,224,0)]]:
            with self.assertRaises(ValueError):placements(b''.join(struct.pack('>HHBBBB',*r) for r in records)+terminator)
    def test_ring_group_flags_eras(self):
        data=struct.pack('>HHBBBB',100,0xc020,0x90,0x92,0x60,0)+struct.pack('>HHBBBB',65535,0,0,0,0,0)
        items,unknown=placements(data)
        self.assertEqual(items,[(100,32,16,0x92,3,3),(84,48,16,0x92,3,3),(68,64,16,0x92,3,3)])
        self.assertFalse(unknown)
    def test_original_counts(self):
        items,unknown=placements((DATA/'Palmtree Panic/Data/Objects (Act 1).bin').read_bytes())
        self.assertEqual(len(items),631)
        self.assertEqual({k:sum(e[2]==k for e in items) for k in [10,16,27,38]}, {10:82,16:194,27:15,38:17})
        self.assertEqual(sum(unknown.values()),0)
    def test_ramp_records(self):
        items,_=placements((DATA/'Palmtree Panic/Data/Objects (Act 1).bin').read_bytes())
        self.assertEqual([e for e in items if e[2]==42],[(1640,1880,42,0,0,2),(8056,608,42,0,0,2),(8120,384,42,129,0,2)])
        self.assertEqual(sum(e[2]==44 for e in items),12)
        self.assertTrue(all(e[5]==2 for e in items if e[2] in (42,44)))
    def test_tag_and_scenery_records(self):
        import re
        items,_=placements((DATA/'Palmtree Panic/Data/Objects (Act 1).bin').read_bytes())
        self.assertEqual([e for e in items if e[2]==52],[(1912,720,52,0,0,2),(3872,416,52,0,0,7),(3872,672,52,0,0,4),(4208,736,52,0,0,1),(8912,800,52,1,0,2)])
        self.assertEqual([e for e in items if e[2]==50],[(5328,152,50,2,0,4),(5432,85,50,0,0,1),(5491,88,50,2,0,4),(5491,104,50,2,0,4),(5540,92,50,1,0,1),(5624,76,50,1,0,1),(5669,152,50,2,0,4)])
        self.assertEqual([e for e in items if e[2]==51],[(5440,136,51,0,0,1),(5442,147,51,1,0,4),(5448,136,51,1,0,4),(5448,136,51,0,0,2),(5552,136,51,0,0,1),(5557,147,51,1,0,4),(5560,136,51,1,0,4),(5560,136,51,0,0,2)])
        for era,bit in [('Present',2),('Past',1),('Good Future',4),('Bad Future',4)]:
            index=(DATA/f'Palmtree Panic/Object Index (Act 1 {era}).asm').read_text()
            self.assertRegex(index,r'dc\.l\s+'+('ObjNull' if era=='Present' else 'ObjScenery')+r'\s*; 32 -')
            self.assertEqual(sum(e[2]==50 and e[5]&bit!=0 for e in items),0 if era=='Present' else 3 if era=='Past' else 4)
            self.assertEqual(sum(e[2]==51 and e[5]&bit!=0 for e in items),2 if era in ('Present','Past') else 4)
    def test_scenery_art_and_palette(self):
        import re
        from convert_objects import assembly_frames,nemesis,draw
        text=(OUT/'object-frames.inc').read_text();raw=unpack_texture((OUT/'object-art.bin').read_bytes())
        def array(name):return list(map(int,re.search(name+r'\[\]=\{([^}]+)',text)[1].split(',')))
        offsets,widths,heights,tops,banks=[array(n) for n in ['object_raw_offsets','object_widths','object_heights','object_tops','object_stage_palette']]
        self.assertIn('#define OBJECT_BASE_51 255',text);self.assertEqual(len(widths),404)
        self.assertIn('#define OBJECT_BASE_41 310',text);self.assertIn('#define OBJECT_BASE_210 313',text);self.assertIn('#define OBJECT_BASE_211 315',text);self.assertIn('#define OBJECT_BASE_40 327',text)
        for kind,base in [(66,333),(21,358),(31,367),(212,375),(213,377),(20,380),(214,384)]:self.assertIn(f'#define OBJECT_BASE_{kind} {base}',text)
        self.assertEqual(banks[252:257],[2]*5)
        self.assertEqual(array('object_high_priority')[252:257],[0]*5)
        colors=struct.pack('>16H',*(0x8000+i for i in range(16)))
        n=252
        for folder,variants in [('Scenery',[('Art (Past).nem',[0,1]),('Art (Future).nem',[2])]),('Log Shadow',[('Art.nem',[0]),('Art (Withered).nem',[1])])]:
            path=DATA/f'Palmtree Panic/Objects/{folder}/Data';maps=assembly_frames(path/'Mappings.asm')
            for name,indices in variants:
                art=nemesis((path/name).read_bytes())
                for index in indices:
                    m=maps[index];width,height,top=widths[n],heights[n],tops[n]
                    self.assertEqual(width,32)
                    for k in range(m[0]):
                        y,size,hi,lo,x=m[1+5*k:6+5*k];x=x if x<128 else x-256;y=y if y<128 else y-256
                        self.assertTrue(-16<=x and x+(((size>>2)&3)+1)*8<=16)
                        self.assertTrue(-32<=y and y+((size&3)+1)*8<=32)
                    off=offsets[n];length=width*height//2;clut=struct.unpack_from('>16H',raw,off+length)
                    actual=bytes(top*width*2)+b''.join(struct.pack('>H',clut[c]) for b in raw[off:off+length] for c in [b>>4,b&15])+bytes((64-top-height)*width*2)
                    self.assertEqual(actual,draw(m,art,colors,width),n);n+=1
        # Actual PLCs select normal log artwork in Past/Present and withered
        # artwork in both futures; scenery uses its own era-specific tile set.
        for era in ['Present','Past','Good Future','Bad Future']:
            text=(DATA/f'Palmtree Panic/Data (Act 1 {era}).asm').read_text()
            self.assertRegex(text,r'dc\.l\s+Art_LogShadow'+('Withered' if 'Future' in era else '')+r'\s+dc\.w\s+\$'+('8300' if era=='Present' else '7960' if era=='Past' else '8500'))
            if era!='Present':self.assertIn('Scenery/Data/Art ('+('Past' if era=='Past' else 'Future')+').nem',text)
    def test_foreground_reference_and_initial_cycles(self):
        from terrain_pixels import foreground_pixel,palette_at
        from convert_objects import palette
        # Source Bad Future script 3 advances before writing palette slot 34;
        # each listed state lasts five ticks. This pixel actually uses it.
        for n,color in enumerate([0x00c,0x00a,0x008,0x006,0x008,0x00a,0x00c,0x00e]):
            expected=palette(struct.pack('>H',color));value=int.from_bytes(expected,'big')
            self.assertEqual(palette_at('Bad Future',n*5)[68:70],expected)
            self.assertEqual(foreground_pixel('Bad Future',5499,73,n*5),(True,bytes(((value&31)*8,((value>>5)&31)*8,((value>>10)&31)*8))))
        self.assertIsNone(foreground_pixel('Present',-1,0))
        self.assertIsNone(foreground_pixel('Present',16384,0))
        # Source scenery art uses stable palette entries in all placed eras.
        # Its foreground occluders can use cycled entries, as above.
        self.assertNotEqual(palette_at('Bad Future',0)[68:70],palette_at('Bad Future',5)[68:70])
    def test_tunnel_tag_source_composition(self):
        from tunnel_tag_reference import trace
        for fractions,expected in [((0,0),3068042808),((0x1234,0x5678),1403366504)]:
            rows,h,contacts=trace(*fractions)
            self.assertEqual((len(rows),h,contacts),(126,expected,9))
            self.assertEqual((rows[-1][0]>>16,rows[-1][1]>>16,rows[-1][4]),(4400,456,0))
            self.assertEqual(rows[0][2],2560);self.assertEqual(rows[0][1]>>16,421)
    def test_doors_and_moving_springs(self):
        import re
        from convert_objects import assembly_frames,nemesis,palette,draw
        items,_=placements((DATA/'Palmtree Panic/Data/Objects (Act 1).bin').read_bytes())
        self.assertEqual([e for e in items if e[2]==13],[(2415,504,13,1,0,4),(2415,792,13,1,0,2),(2415,696,13,1,0,1),(4223,663,13,1,0,2),(6576,296,13,2,0,3),(6730,584,13,1,0,2),(8814,584,13,1,0,2),(8814,840,13,1,0,4)])
        self.assertEqual([e for e in items if e[2]==53],[(2108,552,53,0,0,2),(4348,496,53,0,0,4)])
        self.assertEqual([e for e in items if e[2]==15],[(7034,614,15,0,0,4),(7124,740,15,0,0,4)])
        raw=unpack_texture((OUT/'object-art.bin').read_bytes());text=(OUT/'object-frames.inc').read_text()
        def array(name):return list(map(int,re.search(name+r'\[\]=\{([^}]+)',text)[1].split(',')))
        offsets,widths,heights,tops,banks,canvases,shifts,priorities=[array(n) for n in ['object_raw_offsets','object_widths','object_heights','object_tops','object_stage_palette','object_canvases','object_y_shifts','object_high_priority']]
        self.assertEqual(priorities[:257],[int(142<=n<157 or 171<=n<176 or 246<=n<250) for n in range(257)])
        self.assertEqual(banks[246:252],[0]*6)
        colors=palette((DATA/'_Objects/Sonic/Data/Palette.bin').read_bytes())
        door_art=nemesis((DATA/'Palmtree Panic/Objects/Tunnel Door/Data/Art.nem').read_bytes())
        wheel=DATA/'_Objects/Spring/Data'
        expected=[]
        for path,art in [(DATA/'_Objects/Spin Tunnel/Data/Mappings (Door).asm',door_art),(DATA/'Palmtree Panic/Objects/Tunnel Door/Data/Mappings.asm',door_art),(wheel/'Mappings (Wheel).asm',nemesis((wheel/'Art (Wheel).nem').read_bytes()))]:
            expected.extend((m,art) for m in assembly_frames(path))
        for n,(m,art) in enumerate(expected,246):
            width,height,top,canvas,shift=widths[n],heights[n],tops[n],canvases[n],shifts[n]
            for k in range(m[0]):
                y,size,hi,lo,x=m[1+5*k:6+5*k];x=x if x<128 else x-256;y=y if y<128 else y-256
                self.assertTrue(-width//2<=x and x+(((size>>2)&3)+1)*8<=width//2)
                self.assertTrue(-32-shift<=y and y+((size&3)+1)*8<=canvas-32-shift)
            off=offsets[n];length=width*height//2;clut=struct.unpack_from('>16H',raw,off+length)
            actual=bytes(top*width*2)+b''.join(struct.pack('>H',clut[c]) for b in raw[off:off+length] for c in [b>>4,b&15])+bytes((canvas-top-height)*width*2)
            self.assertEqual(actual,draw(m,art,colors,width,shift,canvas),n)
        # Every priority-7 frame shares the source Sonic palette and must fit
        # the dedicated Saturn CRAM bank without stealing stage palette entries.
        high_colors=set()
        for n,priority in enumerate(priorities):
            if priority:
                self.assertEqual(banks[n],0)
                high_colors.update(c for c in struct.unpack_from('>16H',raw,offsets[n]+widths[n]*heights[n]//2) if c)
        self.assertLessEqual(len(high_colors),16)
    def test_disc_records_and_art(self):
        import re
        from convert_objects import assembly_frames,nemesis,palette,draw
        from convert_assets import sonic_frame
        items,_=placements((DATA/'Palmtree Panic/Data/Objects (Act 1).bin').read_bytes())
        self.assertEqual([e for e in items if e[2]==9],[(4944,904,9,0,0,6),(5008,904,9,0,0,4),(5072,904,9,0,0,6),(6576,744,9,0,0,6),(6640,743,9,0,0,4),(6704,743,9,0,0,4),(8064,360,9,0,0,4)])
        raw=unpack_texture((OUT/'object-art.bin').read_bytes());text=(OUT/'object-frames.inc').read_text()
        def array(name):return list(map(int,re.search(name+r'\[\]=\{([^}]+)',text)[1].split(',')))
        offsets,widths,heights,tops,banks=[array(n) for n in ['object_raw_offsets','object_widths','object_heights','object_tops','object_stage_palette']]
        self.assertEqual(banks[237:246],[0]*9)
        path=DATA/'Palmtree Panic/Objects/Spinning Disc/Data';colors=palette((DATA/'_Objects/Sonic/Data/Palette.bin').read_bytes())
        expected=[draw(m,nemesis((path/'Art.nem').read_bytes()),colors,32) for m in assembly_frames(path/'Mappings.asm')]
        source=DATA/'_Objects/Sonic/Data'
        # Source EVEN padding is exactly one byte; all DPLC requests end at or
        # before that assembled bound. No general zero-filling is allowed.
        self.assertEqual((source/'Art.bin').stat().st_size,69471)
        for era in ['Present','Past','Good Future','Bad Future']:
            assembly=(DATA/f'Palmtree Panic/Data (Act 1 {era}).asm').read_text()
            self.assertRegex(assembly,r'Art_Sonic:\s*incbin\s+"Level/_Objects/Sonic/Data/Art.bin"\s*even')
        for pose in [0x1a,0x1b,0x1c,0x1f,0x1d,0x1e]:
            m=assembly_frames(source/'Mappings.asm')[pose]
            for k in range(m[0]):
                y,size,hi,lo,x=m[1+5*k:6+5*k];x=x if x<128 else x-256;y=y if y<128 else y-256
                self.assertTrue(-32<=x and x+(((size>>2)&3)+1)*8<=32)
                self.assertTrue(-32<=y and y+((size&3)+1)*8<=32)
            expected.append(sonic_frame(pose))
        for n,texture in enumerate(expected,237):
            width,height,top=widths[n],heights[n],tops[n];off=offsets[n];length=width*height//2
            clut=struct.unpack_from('>16H',raw,off+length)
            actual=bytes(top*width*2)+b''.join(struct.pack('>H',clut[c]) for b in raw[off:off+length] for c in [b>>4,b&15])+bytes((64-top-height)*width*2)
            self.assertEqual(actual,texture,n)
    def test_disc_fixture_foreground_clearance(self):
        from convert_assets import sonic_frame
        raw=(OUT/'ppz3.bin').read_bytes();parts=[raw[o:o+n] for o,n in struct.iter_unpack('>II',raw[4:52])]
        def word(data,offset):return int.from_bytes(data[offset:offset+2],'big')
        def high_pixel(x,y):
            chunk=parts[3][y//256*64+x//256]&127
            if not chunk:return False
            block=word(parts[2],(chunk-1)*512+(y//16%16)*32+(x//16%16)*2)
            tx=(x//8%2)^bool(block&0x800);ty=(y//8%2)^bool(block&0x1000)
            tile=word(parts[1],(block&1023)*8+ty*4+tx*2)^(block&0x1800)
            if not tile&0x8000:return False
            px=7-x%8 if tile&0x800 else x%8;py=7-y%8 if tile&0x1000 else y%8
            byte=parts[0][(tile&2047)*32+py*4+px//2]
            return bool(byte&15 if px&1 else byte>>4)
        for pose in [0x1a,0x1b,0x1c,0x1f,0x1d,0x1e]:
            texture=sonic_frame(pose)
            for py in range(64):
                for px in range(64):
                    if not word(texture,(py*64+px)*2):continue
                    for dx in range(-25,26):
                        self.assertFalse(high_pixel(5072+dx+px-32,904-27+py-32),(pose,px,py,dx))
    def test_sonic_hole_art(self):
        import re
        from convert_objects import assembly_frames,nemesis,palette,draw
        raw=unpack_texture((OUT/'object-art.bin').read_bytes())
        text=(OUT/'object-frames.inc').read_text()
        def values(name):return list(map(int,re.search(name+r'\[\]=\{([^}]+)',text)[1].split(',')))
        n=236;offset=values('object_raw_offsets')[n];height=values('object_heights')[n];top=values('object_tops')[n]
        self.assertEqual(values('object_stage_palette')[n],0)
        source=DATA/'Palmtree Panic/Objects/Tunnel Path/Data'
        colors=palette((DATA/'_Objects/Sonic/Data/Palette.bin').read_bytes())
        expected=draw(assembly_frames(source/'Mappings (Hole).asm')[0],nemesis((source/'Art (Hole).nem').read_bytes()),colors,32)
        pixels=raw[offset:offset+32*height//2];clut=struct.unpack_from('>16H',raw,offset+32*height//2)
        actual=bytearray(32*64*2)
        for i,value in enumerate(pixels):
            struct.pack_into('>HH',actual,(top*32+i*2)*2,clut[value>>4],clut[value&15])
        self.assertEqual(bytes(actual),expected)
        items,_=placements((DATA/'Palmtree Panic/Data/Objects (Act 1).bin').read_bytes())
        self.assertEqual([e for e in items if e[2]==49],[(5872,744,49,0,0,7)])
    def test_tunnel_records_and_tables(self):
        import hashlib
        from convert_objects import tunnel_paths
        items,_=placements((DATA/'Palmtree Panic/Data/Objects (Act 1).bin').read_bytes())
        self.assertEqual([e for e in items if e[2]==7],[(3848,416,7,1,0,4,0),(5104,240,7,0,0,3,1)])
        paths=tunnel_paths()
        self.assertEqual([len(p) for p in paths],[34,17,17])
        self.assertEqual(paths[0][0],(5184,240));self.assertEqual(paths[0][-1],(5888,752))
        self.assertEqual(paths[1][0],(3848,416));self.assertEqual(paths[1][-1],(4400,456))
        self.assertEqual(paths[2][0],(5680,656));self.assertEqual(paths[2][-1],(6096,616))
        self.assertEqual(hashlib.sha256(b''.join(struct.pack('>HH',*point) for path in paths for point in path)).hexdigest(),'709101c0513840fe325146acae4b0ca01039dcb72aebefbad6c42419bdbff531')
    def test_float_and_plant_palettes(self):
        import re
        metadata=(OUT/'object-frames.inc').read_text()
        banks=list(map(int,re.search(r'object_stage_palette\[\]=\{([^}]+)',metadata)[1].split(',')))
        # Original Object Tile IDs entry 5 is 0x4334; ramp plants use 0x4424.
        self.assertEqual(banks[107:115],[2]*8)
        items,_=placements((DATA/'Palmtree Panic/Data/Objects (Act 1).bin').read_bytes())
        self.assertEqual(sum(e[2]==18 for e in items),60)
    def test_checkpoints(self):
        import re
        items,_=placements((DATA/'Palmtree Panic/Data/Objects (Act 1).bin').read_bytes())
        self.assertEqual([e for e in items if e[2]==19],[(2760,744,19,2,0,2),(5200,153,19,3,0,2),(8680,616,19,4,0,2)])
        banks=list(map(int,re.search(r'object_stage_palette\[\]=\{([^}]+)',(OUT/'object-frames.inc').read_text())[1].split(',')))
        self.assertEqual(banks[118:122],[0]*4)
    def test_ring_palette_line(self):
        """Rings draw on stage palette line 1 in every zone, as tile $A7AE does."""
        import re
        from convert_assets import palette
        # Both ring spawners (the layout ring and the lost-ring burst) use $A7AE: line 1.
        self.assertEqual(len(re.findall(r'move\.w\s+#\$A7AE,oTile\(a1\)',(DATA/'_Objects/Ring/Main.asm').read_text())),2)
        self.assertEqual((0xA7AE>>13)&3,1)
        text=(OUT/'object-frames.inc').read_text()
        banks=list(map(int,re.search(r'object_stage_palette\[\]=\{([^}]+)',text)[1].split(',')))
        indices=[list(map(int,c.split(','))) for c in re.findall(r'\{([0-9,]+)\}',text.split('object_clut_indices')[1].split(';')[0])]
        self.assertEqual(banks[18:22],[1]*4)
        sparkle_base=int(re.search(r'#define OBJECT_RING_SPARKLE_BASE (\d+)',text)[1])
        self.assertEqual(sparkle_base,394)
        self.assertEqual(banks[sparkle_base:sparkle_base+4],[1]*4)
        def array(name):return list(map(int,re.search(name+r'\[\]=\{([^}]+)',text)[1].split(',')))
        widths,heights,tops,offsets=[array(name) for name in ('object_widths','object_heights','object_tops','object_raw_offsets')]
        raw=unpack_texture((OUT/'object-art.bin').read_bytes())
        from convert_objects import draw,assembly_frames,nemesis
        ring_path=DATA/'_Objects/Ring/Data';ring_maps=assembly_frames(ring_path/'Mappings.asm');ring_art=nemesis((ring_path/'Art.nem').read_bytes())
        marker=struct.pack('>16H',*(0x8000+i for i in range(16)))
        for index in range(4):
            frame=sparkle_base+index;width=widths[frame];self.assertEqual(width,16)
            offset=offsets[frame];size=width*heights[frame]//2
            clut=raw[offset+size:offset+size+32]
            pixels=b''.join(clut[c*2:c*2+2] for b in raw[offset:offset+size] for c in (b>>4,b&15))
            actual=bytes(tops[frame]*width*2)+pixels+bytes((64-tops[frame]-heights[frame])*width*2)
            self.assertEqual(actual,draw(ring_maps[index+4],ring_art,marker,16),index)
        used=set().union(*(indices[n] for n in range(18,22)))
        self.assertEqual(used,{0,6,12,13,14})
        # Every harvested stage palette (Sonic's line 0 then the level's lines 1-3,
        # tools/extract_zone_auto.py) holds white and the gold ramp at those line 1
        # entries; line 0 holds Sonic's red there, which is what rings used to show.
        gold=struct.unpack('>4H',palette(struct.pack('>4H',0xEEE,0x0EE,0x088,0x044)))
        red=struct.unpack('>3H',palette(struct.pack('>3H',0x00E,0x008,0x004)))
        packs=[p for p in sorted(OUT.glob('*.bin')) if re.fullmatch(r'ppz[0-3]|ppz1[23][A-D]|(cc|tt|qq|ww|ss|mm)[3-8][1-3][A-D]',p.stem)]
        self.assertGreaterEqual(len(packs),4)
        for path in packs:
            data=path.read_bytes();self.assertEqual(data[:4],b'PPZ1')
            offset,length=struct.unpack_from('>II',data,4+5*8);self.assertEqual(length,128)
            colors=struct.unpack_from('>64H',data,offset)
            self.assertEqual(tuple(colors[16+i] for i in (6,12,13,14)),gold,path.name)
            self.assertEqual(tuple(colors[i] for i in (12,13,14)),red,path.name)
    def test_walls(self):
        import re
        items,_=placements((DATA/'Palmtree Panic/Data/Objects (Act 1).bin').read_bytes())
        self.assertEqual([(e[0],e[1],e[3],e[5]) for e in items if e[2]==54],[(3584,488,5,1),(3616,488,6,1),(3648,488,7,1),(8592,936,4,4),(8672,696,1,2),(8704,696,3,2),(8728,936,1,4),(8760,936,3,4)])
        banks=list(map(int,re.search(r'object_stage_palette\[\]=\{([^}]+)',(OUT/'object-frames.inc').read_text())[1].split(',')))
        self.assertEqual(banks[122:136],[2]*14)
    def test_finish_art(self):
        import re
        from convert_objects import draw,assembly_frames,nemesis,palette
        metadata=(OUT/'object-frames.inc').read_text()
        def array(name):return list(map(int,re.search(name+r'\[\]=\{([^}]+)',metadata)[1].split(',')))
        self.assertEqual(array('object_y_shifts')[136:157],[0]+[16]*5+[0]*15)
        self.assertEqual(array('object_stage_palette')[136:157],[0]*21)
        colors=palette((DATA/'_Objects/Sonic/Data/Palette.bin').read_bytes())
        source=DATA/'_Objects/Level End/Data'
        art=nemesis((source/'Art (Signpost).nem').read_bytes())
        for mapping in assembly_frames(source/'Mappings (Post).asm')[:5]:
            # Shifted 64-high target contains every nontransparent source pixel.
            target=draw(mapping,art,colors,y_shift=16)
            tall_reference=bytearray(64*96*2)
            for n in range(mapping[0]):
                piece=bytearray([1])+mapping[1+n*5:6+n*5]
                y=piece[1] if piece[1]<128 else piece[1]-256
                piece[1]=0
                rendered=draw(piece,art,colors)
                for py in range(32,64):
                    for px in range(64):
                        pixel=rendered[(py*64+px)*2:(py*64+px)*2+2]
                        if pixel!=b'\0\0':
                            dy=py+y+16
                            self.assertTrue(0<=dy<64)
                            tall_reference[(dy*64+px)*2:(dy*64+px)*2+2]=pixel
            self.assertEqual(target,tall_reference[:64*64*2])
        # Decode the packaged CLUT data independently and compare all digit pixels
        # against the two source 8x8 tiles, including the rightmost four columns.
        encoded=(OUT/'object-art.bin').read_bytes()
        raw=unpack_texture(encoded)
        offsets=array('object_raw_offsets');heights=array('object_heights');tops=array('object_tops');digits=(DATA/'_Objects/HUD and Points/Data/Art (Numbers).bin').read_bytes()
        for n in range(10):
            off=offsets[147+n];length=heights[147+n]*4;pixels=raw[off:off+length];clut=raw[off+length:off+length+32]
            for y in range(16):
                for x in range(8):
                    index=(32+y-tops[147+n])*4+x//2
                    packed=pixels[index] if 0<=index<len(pixels) else 0
                    c=packed&15 if x&1 else packed>>4
                    original=digits[n*64+y*4+x//2];source_c=original&15 if x&1 else original>>4
                    self.assertEqual(clut[c*2:c*2+2],colors[source_c*2:source_c*2+2] if source_c else b'\0\0')
    def test_finish_placements(self):
        items,_=placements((DATA/'Palmtree Panic/Data/Objects (Act 1).bin').read_bytes())
        self.assertEqual([(e[0],e[1],e[5]) for e in items if e[2]==22],[(9984,480,2),(9984,740,1),(10040,740,4)])
        self.assertEqual([(e[0],e[1],e[5]) for e in items if e[2]==23],[(10552,496,2),(10552,756,5)])
    def test_monitor_and_powerup_art(self):
        from convert_objects import DATA,assembly_frames,draw,nemesis,palette
        import re
        common=palette((DATA/'_Objects/Sonic/Data/Palette.bin').read_bytes())
        meta=(OUT/'object-frames.inc').read_text()
        shifts=list(map(int,re.search(r'object_y_shifts\[\]=\{([^}]+)',meta)[1].split(',')))
        widths=list(map(int,re.search(r'object_widths\[\]=\{([^}]+)',meta)[1].split(',')))
        self.assertEqual(shifts[68:72],[8]*4);self.assertEqual(shifts[157:159],[8]*2)
        self.assertEqual(widths[68:72],[32]*4);self.assertEqual(widths[159:176],[32]*17)
        path=DATA/'_Objects/Monitor and Time Post/Data';maps=assembly_frames(path/'Mappings.asm')
        # Original time posts occupy exactly y=-40..24, the full 64 pixels.
        for n in range(10,16):
            for j in range(maps[n][0]):
                y,size,hi,lo,x=maps[n][1+j*5:6+j*5];y=y if y<128 else y-256
                self.assertTrue(0<=40+y and 40+y+((size&3)+1)*8<=64)
        path=DATA/'_Objects/Powerup/Data';maps=assembly_frames(path/'Mappings.asm',contiguous=True)
        self.assertEqual(maps[0][0],0)
        self.assertEqual(maps[1][:21],bytes([4,232,10,0,0,232,232,10,0,9,0,0,10,16,0,232,0,10,16,9,0]))
        self.assertTrue(any(draw(maps[1],(path/'Art (Shield).bin').read_bytes(),common,48)))
        items,_=placements((DATA/'Palmtree Panic/Data/Objects (Act 1).bin').read_bytes())
        self.assertEqual(sum(e[2]==25 and e[3]<8 for e in items),35)
    def test_original_frame_pixels(self):
        import json,hashlib,re
        from sprite_composition import source_sprite,CORRECTED_FRAMES
        from audit_sprite_composition import object_records
        from pathlib import Path
        baseline=json.loads((Path(__file__).parent/'object-art-baseline.json').read_text())['frames']
        metadata=(OUT/'object-frames.inc').read_text()
        def array(name):return list(map(int,re.search(name+r'\[\]=\{([^}]+)',metadata)[1].split(',')))
        widths,heights,tops,shifts,banks,offsets=[array(name) for name in ['object_widths','object_heights','object_tops','object_y_shifts','object_stage_palette','object_raw_offsets']]
        raw=unpack_texture((OUT/'object-art.bin').read_bytes())
        self.assertEqual(len(baseline),183);self.assertGreaterEqual(len(widths),len(baseline))
        for number,old in enumerate(baseline):
            width,height,top=widths[number],heights[number],tops[number]
            self.assertTrue(height>=1 and top+height<=64)
            # Rings (18-21) moved from Sonic's line to stage line 1; see test_ring_palette_line.
            self.assertEqual((width,shifts[number],banks[number]),(old['width'],old['y_shift'],1 if 18<=number<22 else old['stage_palette']))
            offset=offsets[number];length=width*height//2;clut=raw[offset+length:offset+length+32]
            self.assertEqual(offset%32,0);self.assertEqual(length%32,0)
            cropped=b''.join(clut[c*2:c*2+2] for b in raw[offset:offset+length] for c in [b>>4,b&15])
            canonical=bytes(top*width*2)+cropped+bytes((64-top-height)*width*2)
            if 18<=number<22:
                # Keep the snapshot immutable: prove it is the old Sonic-line (red)
                # ring, then require the same pixels as stage line 1 indices.
                from convert_objects import draw,assembly_frames,nemesis,palette
                path=DATA/'_Objects/Ring/Data';mapping=assembly_frames(path/'Mappings.asm')[number-18];art=nemesis((path/'Art.nem').read_bytes())
                self.assertEqual(old['stage_palette'],0)
                self.assertEqual(hashlib.sha256(draw(mapping,art,palette((DATA/'_Objects/Sonic/Data/Palette.bin').read_bytes()))).hexdigest(),old['rgb1555_sha256'],f'legacy ring {number}')
                self.assertEqual(canonical,draw(mapping,art,struct.pack('>16H',*(0x8000+i for i in range(16)))),f'ring {number}')
            elif 159<=number<171:
                from monitor_pixels import source_monitor
                # Keep the historical snapshot immutable. Prove it describes
                # the old last-piece-wins defect, then require original-order
                # pixels from the independent pixel-first oracle instead.
                legacy=source_monitor(number-159,legacy_last=True)
                self.assertEqual(hashlib.sha256(legacy).hexdigest(),old['rgb1555_sha256'])
                self.assertEqual(canonical,source_monitor(number-159),f'monitor frame {number}')
            elif number in CORRECTED_FRAMES:
                r=object_records()[number]
                args=[r[n] for n in ['mapping','art','colors','width','y_shift','height']]
                legacy=source_sprite(*args,legacy_last=True)
                self.assertEqual(hashlib.sha256(legacy).hexdigest(),old['rgb1555_sha256'],f'legacy frame {number}')
                self.assertEqual(canonical,source_sprite(*args),f'corrected original frame {number}')
            else:self.assertEqual(hashlib.sha256(canonical).hexdigest(),old['rgb1555_sha256'],f'frame {number}')
            # Restore both VDP1 flip modes into the old 64-row coordinate box.
            for vertical in [False,True]:
                for horizontal in [False,True]:
                    rows=[cropped[y*width*2:(y+1)*width*2] for y in range(height)]
                    full=[canonical[y*width*2:(y+1)*width*2] for y in range(64)]
                    if horizontal:
                        rows=[b''.join(row[x*2:x*2+2] for x in range(width-1,-1,-1)) for row in rows]
                        full=[b''.join(row[x*2:x*2+2] for x in range(width-1,-1,-1)) for row in full]
                    if vertical:rows.reverse();full.reverse()
                    origin=64-top-height if vertical else top
                    restored=bytes(origin*width*2)+b''.join(rows)+bytes((64-origin-height)*width*2)
                    self.assertEqual(restored,b''.join(full),(number,vertical,horizontal))
    def test_collapse_art_and_geometry(self):
        import re
        from convert_objects import collapse_tables,assembly_frames,nemesis
        meta=(OUT/'object-frames.inc').read_text()
        def array(name):return list(map(int,re.search(name+r'\[\]=\{([^}]+)',meta)[1].split(',')))
        widths,heights,tops,canvases,offsets,banks=[array(n) for n in ['object_widths','object_heights','object_tops','object_canvases','object_raw_offsets','object_stage_palette']]
        self.assertEqual(len(widths),404);self.assertEqual(banks[183:236],[2]*53)
        raw=unpack_texture((OUT/'object-art.bin').read_bytes())
        art=nemesis((DATA/'Palmtree Panic/Objects/Platform/Data/Art.nem').read_bytes())
        n=183
        for era in ['Present','Past','Future']:
            for family in ['Ledge, ','','Pieces 1, ','Pieces 2, ']:
                for mapping in assembly_frames(DATA/f'Palmtree Panic/Objects/Collapsing Platform/Data/Mappings ({family}{era}).asm'):
                    width,height,top=widths[n],heights[n],tops[n]
                    self.assertEqual(canvases[n],96)
                    length=width*height//2;off=offsets[n];clut=raw[off+length:off+length+32]
                    decoded=b''.join(clut[c*2:c*2+2] for b in raw[off:off+length] for c in [b>>4,b&15])
                    actual=bytes(top*width*2)+decoded+bytes((96-top-height)*width*2)
                    expected=bytearray(width*96*2)
                    for j in range(mapping[0]):
                        y,size,hi,lo,x=mapping[1+j*5:6+j*5]
                        x=x if x<128 else x-256;y=y if y<128 else y-256
                        w,h=((size>>2)&3)+1,(size&3)+1;tile=hi*256+lo
                        for py in range(h*8):
                            for px in range(w*8):
                                sx=w*8-1-px if tile&2048 else px;sy=h*8-1-py if tile&4096 else py
                                address=((tile&2047)+(sx//8)*h+sy//8)*32+(sy%8)*4+(sx%8)//2
                                c=(art[address]>>(4 if sx%2==0 else 0))&15
                                if not c:continue
                                dx,dy=width//2+x+px,48+y+py
                                self.assertTrue(0<=dx<width and 0<=dy<96,(era,family,n,x,y))
                                expected[(dy*width+dx)*2:(dy*width+dx)*2+2]=struct.pack('>H',0x8000+c)
                    self.assertEqual(actual,expected,(era,family,n));n+=1
        tables=collapse_tables('Past')
        self.assertEqual(tables[0][1],(3,2,[1,2,3,3,5,5,5,5,6,6,6,6]))
        self.assertEqual(tables[1][2],(8,3,[1,3,3,3,3,3,3,3,2]))
        self.assertEqual(tables[1][5],(9,3,[1,3,3,3,3,3,3,3,3,2]))
        items,_=placements((DATA/'Palmtree Panic/Data/Objects (Act 1).bin').read_bytes())
        self.assertEqual([(e[0],e[1],e[3],e[5]) for e in items if e[2]==32],[(1384,544,16,1),(3200,536,17,1),(3248,784,192,2),(3320,544,0,7),(3920,161,224,7),(4016,161,193,7),(4824,288,0,7),(7743,672,194,1),(8064,353,197,1)])

    def test_literal_texture_codec(self):
        from convert_objects import pack_texture
        # Independent byte commands, runs, singleton/literal boundaries and
        # 15-bit splitting limits; the old image hashes test actual asset data.
        self.assertEqual(unpack_texture(bytes.fromhex('0003 1234 8002 abcd fedc')),bytes.fromhex('1234 1234 1234 abcd fedc'))
        for values in [[],[0],[1,2],[1,1,2,3,4,4,5],[7]*32768,list(range(32768))]:
            raw=struct.pack('>'+str(len(values))+'H',*values)
            self.assertEqual(unpack_texture(pack_texture(raw)),raw)
        for bad in ['0000 1234','8000','0001','8002 1234']:
            with self.assertRaises(ValueError):unpack_texture(bytes.fromhex(bad))

    def test_texture_runs(self):
        data=(OUT/'object-art.bin').read_bytes();decoded=unpack_texture(data)
        self.assertLessEqual(0x1AAC0+len(decoded),0x76800)
        # The encoded pack must fit its CD region (OBJART.BIN, 0x39000 bytes in src/stage_packs.h).
        from convert_assets import ROOT
        self.assertIn('"OBJART.BIN",0x00271800,0x39000',(ROOT/'src/stage_packs.h').read_text())
        self.assertLessEqual(-(-len(data)//2048)*2048,0x39000)
        import re
        metadata=(OUT/'object-frames.inc').read_text()
        widths=list(map(int,re.search(r'object_widths\[\]=\{([^}]+)',metadata)[1].split(',')))
        offsets=list(map(int,re.search(r'object_raw_offsets\[\]=\{([^}]+)',metadata)[1].split(',')))
        ends=[]
        heights=list(map(int,re.search(r'object_heights\[\]=\{([^}]+)',metadata)[1].split(',')))
        for offset,width,height in zip(offsets,widths,heights):
            length=width*height//2
            self.assertEqual(offset%32,0)
            self.assertEqual((offset+length)%32,0,('VDP1 masks CLUT low address bits',offset,width,height))
            clut=struct.unpack('>16H',decoded[offset+length:offset+length+32])
            ends.append(offset+length+32)
            self.assertEqual(clut[0],0)
            self.assertTrue(all(c==0 or c&0x8000 for c in clut))
        self.assertEqual(max(ends),len(decoded))
        segments=sorted(set(zip(offsets,ends)))
        self.assertEqual(segments[0][0],0)
        self.assertTrue(all(a[1]==b[0] for a,b in zip(segments,segments[1:])))
    def test_sikake33_translation(self):
        # ACT33C id 54 is R3/SIKAKE33.C in both eras: one kaitenban (-2)
        # at 896,1104. Its stopper and lights are children, never placed.
        # Its retail record sets the saved bit (kind&128), kept as flags 32
        # (TT_SAVED) since CC streams through the retail Object Spawner.
        import object_layouts as L,re
        tables,defs=L.act_tables(),L.definitions()
        self.assertEqual(L.ZONE_TYPES['sikake33'],(93,'R3/SIKAKE33.C',0,False))
        entries,report=L.translate(3,3,tables,L.port_types(tables),defs)
        self.assertNotIn('sikake33',report['dropped_routines'])
        self.assertEqual([tuple(e) for e in entries if e[2]==93],[(896,1104,93,254,32,4)])
        values=dict(re.findall(r'(SCD_OBJ_\w+)=(\d+)',(L.ROOT/'src/scd_objects.h').read_text()))
        self.assertEqual(values['SCD_OBJ_SIKAKE33'],'93')
        art=(L.ROOT/'src/zone_object_art.h').read_text()
        self.assertIn('if(type==93)kind=subtype&128?293:subtype?193:93;',art)
if __name__=='__main__':unittest.main()
