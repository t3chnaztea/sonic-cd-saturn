#!/usr/bin/env python3
"""Asset-free site ownership contracts. No private inputs are used."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import struct
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('audit_site',ROOT/'tools/audit-site.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class SiteAudit(unittest.TestCase):
    def test_generic_classes(self):
        for data,category in ((bytes(16),'fill'),(bytes([3,7])*8,'fill'),
                              (b'Compiler message','ASCII text'),(bytes(range(16)),'generic run')):
            self.assertEqual(module.classify(data)[0],category)
        self.assertEqual(module.classify(bytes([1,6,2,5,4,8,9,7,3,11,10,2,6,8,5,4]))[0],'UNEXPLAINED')

    def run_fixture(self,payload,extra=b'',upstream=False,mutate=False,patched=False,patched_mismatch=False):
        with tempfile.TemporaryDirectory(prefix='patcher-site-audit-')as name:
            root=Path(name).resolve();site=root/'build/site';patcher=site/'web/patcher';patcher.mkdir(parents=True)
            (root/'tools').mkdir()
            for filename in ('recipe_literal_scan.c','audit-site.py'):shutil.copyfile(ROOT/'tools'/filename,root/'tools'/filename)
            recipe=patcher/'recipe.scsp';recipe.write_bytes(b'SCSP082\n'+struct.pack('<I',2)+b'{}'+payload)
            source=root/'corpus.bin';source.write_bytes(extra or payload)
            audit=root/'build/audit';audit.mkdir();corpus=audit/'corpus.tsv';corpus.write_text(f'0\t{source.stat().st_size}\t{source}\n')
            (audit/'receipt.json').write_text(json.dumps(dict(status='PASS',policy='recipe-no-initialized-data-v5',
                corpus_manifest_sha256=module.digest(corpus),bundle_sha256=module.digest(recipe),corpus_definition={'test':'synthetic binary'})))
            lock=root/'web/patcher/vendor/runtime-lock.json';lock.parent.mkdir(parents=True)
            rows=[];original_files=[]
            if upstream:
                runtime=patcher/'runtime.bin';runtime.write_bytes(extra)
                rows=[dict(path='web/patcher/runtime.bin',upstream_sha256=hashlib.sha256(extra).hexdigest())]
                if mutate:runtime.write_bytes(extra+extra)
                if patched:
                    original=root/'original.bin';original.write_bytes((extra[::-1]if patched_mismatch else extra)+bytes(16))
                    runtime.write_bytes(extra+b'Compiler message')
                    rows[0].update(upstream_sha256=module.digest(original),sha256=module.digest(runtime))
                    original_files=[original]
            else:(patcher/'project.bin').write_bytes(extra)
            lock.write_text(json.dumps(dict(files=rows)))
            previous=module.ROOT;module.ROOT=root
            try:
                with contextlib.redirect_stdout(io.StringIO()):code=module.audit(site,audit,root/'build/result',original_files)
            finally:module.ROOT=previous
            return code,json.loads((root/'build/result/receipt.json').read_text())

    def test_generic_fill_in_recipe_payload_still_fails(self):
        code,receipt=self.run_fixture(bytes([255])*16)
        self.assertEqual(code,1);self.assertEqual(receipt['recipe_payload_matches'],1)
        self.assertEqual(receipt['matches_by_class']['fill'],1)

    def test_upstream_exemption_requires_exact_content(self):
        pattern=bytes([1,6,2,5,4,8,9,7,3,11,10,2,6,8,5,4])
        code,receipt=self.run_fixture(b'',pattern,upstream=True)
        self.assertEqual(code,0);self.assertEqual(receipt['upstream_identical_files'],1)
        code,receipt=self.run_fixture(b'',pattern,upstream=True,mutate=True)
        self.assertEqual(code,1);self.assertEqual(receipt['upstream_identical_files'],0)
        self.assertGreater(receipt['matches_by_class']['UNEXPLAINED'],0)

    def test_patched_runtime_is_scanned_and_each_unchanged_window_proven(self):
        pattern=bytes([1,6,2,5,4,8,9,7,3,11,10,2,6,8,5,4])
        code,receipt=self.run_fixture(b'',pattern,upstream=True,patched=True)
        self.assertEqual(code,0);self.assertEqual(receipt['upstream_identical_files'],0)
        self.assertEqual(receipt['upstream_proven_matches'],1)
        hit=receipt['match_records'][0]
        self.assertEqual(hit['classification'],'generic run')
        self.assertEqual(hit['upstream_offset'],hit['offset'])
        self.assertIn('upstream_sha256',hit)
        code,receipt=self.run_fixture(b'',pattern,upstream=True,patched=True,patched_mismatch=True)
        self.assertEqual(code,1);self.assertEqual(receipt['upstream_proven_matches'],0)
        self.assertEqual(receipt['matches_by_class']['UNEXPLAINED'],1)

    def test_all_duplicate_positions_are_reported(self):
        pattern=b'Compiler message'
        code,receipt=self.run_fixture(b'',pattern*2)
        self.assertEqual(code,0)
        hits=[r for r in receipt['match_records']if r['file'].endswith('project.bin')]
        self.assertEqual([r['offset']for r in hits],[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16])


if __name__=='__main__':
    result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(SiteAudit))
    if not result.wasSuccessful():raise SystemExit(1)
    print('PASS: site audit; whole payload, hash-bound upstream exemptions and every matching file offset')
