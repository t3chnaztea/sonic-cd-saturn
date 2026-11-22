#!/usr/bin/env python3
"""Asset-free scanner contracts: exact matching, chunk edges and run bounds."""
from pathlib import Path
import importlib.util
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class LiteralScan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory(prefix='patcher-scan-')
        cls.work=Path(cls.directory.name);cls.scanner=cls.work/'scanner'
        compiler=shutil.which('clang')or shutil.which('cc')
        if compiler is None:raise RuntimeError('A host C compiler is required')
        subprocess.run([compiler,'-O2','-Wall','-Wextra',str(ROOT/'tools/recipe_literal_scan.c'),'-o',str(cls.scanner)],check=True)

    @classmethod
    def tearDownClass(cls):cls.directory.cleanup()

    def scan(self,literal,corpus,ranges=None):
        bundle=self.work/'bundle';bundle.write_bytes(b'header'+literal)
        source=self.work/'source';source.write_bytes(corpus)
        listing=self.work/'corpus.tsv';listing.write_text(f'0\t{len(corpus)}\t{source}\n')
        args=[str(self.scanner),str(bundle),'6',str(listing)]
        if ranges is not None:
            path=self.work/'ranges.tsv';path.write_text(''.join(f'{a}\t{b}\n'for a,b in ranges));args.append(str(path))
        return subprocess.run(args,capture_output=True,text=True)

    def test_exact_sixteen_bytes_required(self):
        pattern=bytes(range(32,48))
        self.assertEqual(self.scan(pattern,pattern).returncode,1)
        self.assertEqual(self.scan(pattern,pattern[:8]+bytes(8)).returncode,0)
        self.assertEqual(self.scan(pattern[:15],pattern).returncode,0)

    def test_chunk_boundary_is_scanned(self):
        pattern=bytes(range(32,48));offset=1024*1024-8
        result=self.scan(pattern,b'\xaa'*offset+pattern)
        self.assertEqual(result.returncode,1)
        self.assertIn(f'offset={offset}',result.stdout)

    def test_separate_literal_runs_are_not_concatenated(self):
        pattern=bytes(range(32,48))
        self.assertEqual(self.scan(pattern,pattern,[(0,8),(8,8)]).returncode,0)
        self.assertEqual(self.scan(pattern,pattern,[(0,16)]).returncode,1)

    def test_invalid_literal_extent_is_rejected(self):
        self.assertEqual(self.scan(bytes(16),bytes(16),[(0,17)]).returncode,2)

    def test_ownership_seam_does_not_hide_a_match(self):
        spec=importlib.util.spec_from_file_location('audit_recipe',ROOT/'tools/audit-recipe.py')
        audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
        pattern=bytes(range(32,48))
        # The stored bytes are adjacent even if target operations are not.
        # Twelve-byte tables, other symbols and derive/zero operations cannot
        # hide a matching window in the distributed payload.
        ranges=audit.literal_scan_ranges(len(pattern))
        self.assertEqual(ranges,[(0,16)])
        self.assertEqual(self.scan(pattern,pattern,ranges).returncode,1)
        self.assertEqual(self.scan(bytes([255])*16,bytes([255])*16,ranges).returncode,1)



if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(LiteralScan))
    if not result.wasSuccessful():raise SystemExit(1)
    print('PASS: literal scanner; exact 16-byte matches, chunk boundaries and operation extents')
