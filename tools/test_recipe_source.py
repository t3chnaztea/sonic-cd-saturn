#!/usr/bin/env python3
"""Asset-free contracts for source expansion and SH object serialization."""
from pathlib import Path
import tempfile
import unittest
from recipe_source import definitions,expand,context,source_initializer
from recipe_values import initializer,serialize,number


class SourceObjects(unittest.TestCase):
    def test_active_branch_and_nested_function_macros(self):
        macros=definitions('#ifdef SCD_ZONE_OVERLAY\n#define TARGET program_entry\n#else\n#define TARGET 0\n#endif\n#define STEP(x) ((x)+1)\n#define PAIR(x) STEP(x),STEP(x+1)\n',{'SCD_ZONE_OVERLAY':(None,'1')})
        self.assertEqual(expand('TARGET',macros),'program_entry')
        self.assertEqual(number(expand('STEP(3)',macros)),4)
        node=source_initializer('int values[2]={PAIR(2)};','values',0,macros)
        schema=dict(kind='array',size=2,count=2,element=dict(kind='integer',size=1))
        self.assertEqual(serialize(schema,node),bytes([3,4]))

    def test_enum_spacing_and_ternary_count(self):
        self.assertEqual(number(' 0x00 '),0)
        self.assertEqual(number('((2*6+2)<=0)?1:(2*6+2)'),14)
        with tempfile.TemporaryDirectory()as name:
            p=Path(name)/'constants.h';p.write_text('enum { A = 2, B = A+1 };')
            _,constants=context(name,('constants.h',));self.assertEqual(constants['B'],3)

    def test_designators_after_last_field_and_anonymous_bitfield(self):
        integer=dict(kind='integer',size=1)
        schema=dict(kind='struct',size=3,fields=[dict(name='',offset=0,type=dict(kind='struct',size=1,fields=[
            dict(name='flag',offset=0,type=dict(kind='bits',size=1,bit=3,width=1))])),
            dict(name='array',offset=1,type=dict(kind='array',size=2,count=2,element=integer))])
        node=initializer('x={.array[1]=7,.array[0]=3,.flag=1};','x')
        self.assertEqual(serialize(schema,node),bytes([16,3,7]))

    def test_sh_debug_layout_reproduces_native_probe(self):
        from recipe_dwarf import DwarfTypes
        from recipe_elf import Elf
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='patcher-sh-layout-')as name:
            work=Path(name);unit=work/'probe.c'
            source='typedef struct {unsigned flag:1;unsigned count:3;unsigned:4;unsigned char samples[2];} record; const record object={.samples={2,4},.count=3,.flag=1};'
            unit.write_text(source);types=DwarfTypes(root,unit,work)
            elf=Elf(next(work.glob('*.sh-layout.o')))
            symbol=next(s for s in elf.symbols if s['name']=='_object')
            section=elf.sections[symbol['section']];offset=symbol['value']-section.address
            native=elf.content(section)[offset:offset+symbol['bytes']]
            node=source_initializer(source,'object',0,{})
            self.assertEqual(serialize(types.variable('object',symbol['bytes']),node),native)

    def test_numeric_function_pointer_address(self):
        self.assertEqual(number('((void (*)(void))0x0600083C)'),0x0600083c)


if __name__=='__main__':
    result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(SourceObjects))
    if not result.wasSuccessful():raise SystemExit(1)
    print('PASS: source object serializers; macros, enums, SH bits, sizeof arithmetic and late designators')
