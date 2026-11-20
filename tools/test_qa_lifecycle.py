#!/usr/bin/env python3
"""Negative tests for lifecycle evidence; compiler and game execution are mocked."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import qa_lifecycle as qa


class LifecycleEvidence(unittest.TestCase):
    def setUp(self):
        base=qa.ROOT/'build';base.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='lifecycle-test-',dir=base)
        self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.enterContext(patch.object(qa,'inputs',side_effect=lambda source,zone,generated:([],{str(generated):qa.sha(generated)})))

    def execute(self,behavior='pass'):
        def command(argv,**kwargs):
            if 'clang' in argv:
                Path(argv[-1]).write_bytes(b'mock executable');return
            kwargs['stdout'].write(json.dumps({'cycle':0,'respawns':1,'checkpoint_id':2,'arrival_era':1})+'\n')
            if behavior=='timeout':raise subprocess.TimeoutExpired(argv,120)
            if behavior=='crash':raise subprocess.CalledProcessError(-6,argv)
            if behavior=='short':kwargs['stdout'].truncate(0)
            if behavior=='changed':(self.root/'ppz-0/lifecycle.c').write_text('changed during execution')
        with patch.object(qa.subprocess,'run',side_effect=command):
            return qa.run_case(self.root,self.root,'ppz',0,1,'mock compiler')

    def test_complete_fixture_is_hash_bound(self):
        result=self.execute()
        self.assertTrue(result['passed'])
        self.assertEqual(result['results'][0]['respawns'],1)
        self.assertIn('API checkpoint',result['scope'])
        self.assertEqual(result['executable_sha256'],qa.sha(self.root/'ppz-0/lifecycle'))

    def test_crash_is_durable_failure(self):
        result=self.execute('crash')
        self.assertFalse(result['passed'])
        self.assertEqual(json.loads((self.root/'ppz-0/report.json').read_text())['status'],'failed')

    def test_timeout_is_durable_failure(self):
        result=self.execute('timeout')
        self.assertFalse(result['passed']);self.assertIn('TimeoutExpired',result['error'])
        self.assertTrue((self.root/'ppz-0/stdout.log').read_text())

    def test_truncated_coverage_fails(self):
        result=self.execute('short')
        self.assertFalse(result['passed']);self.assertIn('missing lifecycle coverage',result['error'])

    def test_changed_inputs_fail(self):
        result=self.execute('changed')
        self.assertFalse(result['passed']);self.assertIn('input changed',result['error'])

    def test_defaults_cover_both_modes_all_seven_zones(self):
        with patch.object(qa,'ROOT',self.root),patch.object(qa.subprocess,'check_output',return_value='mock'),patch.object(qa,'run_case',return_value={'passed':True}) as runner,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(qa.main(['--cycles','1']),0)
        self.assertEqual({call.args[2] for call in runner.call_args_list},set(qa.ZONES))
        self.assertEqual({call.args[3] for call in runner.call_args_list},{0,31})
        self.assertEqual(runner.call_count,14)

    def test_bounded_cli_rejects_excess_cycles_and_workers(self):
        for arguments in (['--cycles','21'],['--cycles','0'],['--jobs','5'],['--modes','1']):
            with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):qa.main(arguments)

    def test_runtime_assets_cover_actual_loader_inputs(self):
        self.assertEqual(len(qa.runtime_assets('ppz')),20)
        self.assertIn('cc31D.bin',qa.runtime_assets('cc'))
        for zone in qa.ZONES[2:]:
            names=qa.runtime_assets(zone)
            self.assertEqual(len(names),5)
            self.assertTrue(any(name.endswith('1B.bin') and 'collision' in name for name in names))


if __name__=='__main__':unittest.main()
