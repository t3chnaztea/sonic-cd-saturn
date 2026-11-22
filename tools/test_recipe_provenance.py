#!/usr/bin/env python3
"""Asset-free regression controls for literal ownership and compiler locations."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from recipe_elf import generated_input, generated_evidence, symbol_provenance, source_aliases, syntax_unit, compiler_declarations
from recipe_provenance import FORBIDDEN_LITERAL_OWNERS, literal_owner_totals


def ledger(owner,source='src/example.c'):
    proof=dict(symbol='_example',owner=owner,evidence=[dict(source=source,line=7)])
    return dict(literal_ranges=[dict(bytes=4,owner='program',evidence=dict(provenance=[proof]))])


class Policy(unittest.TestCase):
    def test_banned_permissions_cannot_be_reused(self):
        for owner in FORBIDDEN_LITERAL_OWNERS:
            with self.subTest(owner=owner),self.assertRaisesRegex(ValueError,'Forbidden literal owner'):
                literal_owner_totals(ledger(owner))

    def test_all_source_data_objects_are_derived(self):
        for owner in ('project-source-initializer','dependency-source-initializer'):
            self.assertIn(owner,FORBIDDEN_LITERAL_OWNERS)
            with self.assertRaisesRegex(ValueError,'Forbidden literal owner'):literal_owner_totals(ledger(owner))
        evidence={'example':[dict(source='src/example.c',line=1,variable='example')]}
        self.assertEqual(symbol_provenance(Path.cwd(),dict(name='_example',type=1),evidence)['kind'],'derive')

    def test_source_proof_is_required(self):
        value=ledger('source-string')
        self.assertEqual(literal_owner_totals(value),{'source-string':4})
        value['literal_ranges'][0]['evidence']['provenance'][0]['evidence']=[dict(object='example.o')]
        with self.assertRaisesRegex(ValueError,'source-file evidence'):literal_owner_totals(value)

    def test_cc0_data_is_derived_but_function_code_is_literal(self):
        root=Path.cwd()
        for source in ('build/probe-source/example.c','src/objects_mm_remaining.inc'):
            self.assertTrue(generated_input(source,root))
            evidence={'example':[dict(source=source,line=1,variable='example')]}
            self.assertEqual(symbol_provenance(root,dict(name='_example',type=1),evidence)['kind'],'derive')
            self.assertEqual(symbol_provenance(root,dict(name='_example',type=2),evidence)['kind'],'literal')

    def test_transitive_macro_names_and_cycles(self):
        self.assertEqual(source_aliases('zone_name',{'zone_name':['adapted_name'],'adapted_name':['original_name'],
            'original_name':['zone_name']}),{'zone_name','adapted_name','original_name'})

    def test_host_query_preserves_preprocessor_locations(self):
        with tempfile.TemporaryDirectory()as temporary:
            root=Path(temporary);unit=root/'build/saturn/example.i';unit.parent.mkdir(parents=True)
            work=root/'metadata';work.mkdir()
            original=('# 1 "src/example.c"\nstatic const char message[]="asm(\\\"example\\\")";\nvoid example(void){__asm__ volatile("nop":::"mach");}\n'
                '_Static_assert(\n# 44 "src/example.c"\n1,"example");\n'
                '# 70 "src/example.c"\nstatic int example_table[2]={1,2};\n')
            unit.write_text(original);normalized=syntax_unit(unit,work).read_text()
            self.assertEqual(len(original),len(normalized))
            self.assertEqual(original.count('\n'),normalized.count('\n'))
            self.assertIn('"asm(\\\"example\\\")"',normalized)
            row=compiler_declarations(unit,'example_table',work)[0]
            self.assertEqual((row['source'],row['line'],row['ctype']),('src/example.c',70,'int[2]'))
            self.assertEqual(row['translation_unit_sha256'],hashlib.sha256(original.encode()).hexdigest())
            self.assertEqual(unit.read_text(),original)

    def test_generated_include_cannot_hide_in_project_initializer(self):
        with tempfile.TemporaryDirectory()as temporary:
            root=Path(temporary);unit=root/'build/saturn/example.i';unit.parent.mkdir(parents=True)
            work=root/'metadata';work.mkdir()
            unit.write_text('# 1 "src/example.c"\nstatic int example_table[2]={\n'
                '# 1 "assets/generated/example.inc"\n1,2\n# 4 "src/example.c"\n};\n')
            row=compiler_declarations(unit,'example_table',work)[0]
            self.assertTrue(generated_evidence(row,root))
            self.assertEqual(symbol_provenance(root,dict(name='_example_table',type=1),{'example_table':[row]})['kind'],'derive')
            value=ledger('project-source-initializer');value['literal_ranges'][0]['evidence']['provenance'][0]['evidence']=[row]
            with self.assertRaisesRegex(ValueError,'Forbidden literal owner'):literal_owner_totals(value)

    def test_automatic_locals_are_not_static_object_initializers(self):
        with tempfile.TemporaryDirectory()as temporary:
            root=Path(temporary);unit=root/'build/saturn/example.i';unit.parent.mkdir(parents=True)
            work=root/'metadata';work.mkdir()
            unit.write_text('# 1 "src/example.c"\nstatic int example=1;\nvoid example_function(void){int example=2;example=3;}\n')
            rows=compiler_declarations(unit,'example',work)
            self.assertEqual([r['static_storage']for r in rows],[True,False])


if __name__=='__main__':
    result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Policy))
    if not result.wasSuccessful():raise SystemExit(1)
    print('PASS: recipe provenance; legacy data literals rejected; compiler locations preserved')
