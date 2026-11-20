#!/usr/bin/env python3
"""Negative tests for fuzz evidence and cache validity; no game assets required."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

import cdpp_fuzz as fuzz


class FuzzEvidenceTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[1] / 'build'
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='fuzz-tests-', dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.exe = self.root / 'host'
        self.exe.write_bytes(b'fake host for subprocess mocks')
        self.enterContext(patch.object(fuzz, 'OUT', self.root / 'runs'))
        self.enterContext(patch.object(fuzz, 'host', return_value=self.exe))

    def replay(self, **kwargs):
        return fuzz.run('ppz1A', 0, 7000, 10, **kwargs)

    @staticmethod
    def completed(argv, **kwargs):
        Path(argv[-1]).write_text('2 128 100 100\n3 128 101 100\n')
        return types.SimpleNamespace(returncode=1, stdout='replay stdout', stderr='Route incomplete')

    def test_timeout_is_failed_and_retains_partial_logs(self):
        def timeout(argv, **kwargs):
            Path(argv[-1]).write_text('2 128 100 100\n')
            raise subprocess.TimeoutExpired(argv, 600, output=b'partial stdout', stderr=b'partial stderr')
        with patch.object(fuzz.subprocess, 'run', side_effect=timeout):
            result = self.replay()
        self.assertFalse(result['passed'])
        self.assertEqual(result['terminal'], 'timeout')
        folder = Path(result['artifacts'])
        self.assertEqual((folder / 'stdout.log').read_text(), 'partial stdout')
        self.assertEqual((folder / 'stderr.log').read_text(), 'partial stderr')
        self.assertEqual(json.loads((folder / 'report.json').read_text())['status'], 'failed')

    def test_fresh_case_cannot_reuse_previous_trace(self):
        with patch.object(fuzz.subprocess, 'run', side_effect=self.completed):
            first = self.replay()
        with patch.object(fuzz.subprocess, 'run', return_value=types.SimpleNamespace(
                returncode=1, stdout='', stderr='Route incomplete')):
            second = self.replay()
        self.assertNotEqual(first['artifacts'], second['artifacts'])
        self.assertTrue(first['passed'])
        self.assertIn('trace_error', second)
        self.assertFalse(second['passed'])
        self.assertTrue((Path(first['artifacts']) / 'trace.rows').is_file())

    def test_classic_only_crash_fails_aggregate(self):
        def replay(window, flags, seed, length, output_root):
            result = dict(window=window, flags=flags, seed=seed, death=False, warp=False, terminal='limit')
            if flags == 0:
                result['crash'] = 'injected Classic-only sanitizer failure'
            return result
        with patch.object(fuzz, 'run', side_effect=replay), contextlib.redirect_stdout(io.StringIO()):
            result = fuzz.main(['--classic', '--runs', '1', '--windows', 'ppz1A', '--seed-start', '8111'])
        report = json.loads(next(fuzz.OUT.glob('*/report.json')).read_text())
        self.assertEqual(result, 1)
        self.assertFalse(report['passed'])
        self.assertIn('ppz1A/0', report['failures'])
        self.assertEqual(report['results'][0]['seed'], 8111)

    def test_first_state_is_checked_for_out_of_bounds(self):
        def replay(argv, **kwargs):
            Path(argv[-1]).write_text('2 128 17000 100\n3 128 100 100\n')
            return types.SimpleNamespace(returncode=1, stdout='', stderr='Route incomplete')
        with patch.object(fuzz.subprocess, 'run', side_effect=replay):
            result = self.replay()
        self.assertEqual(result['oob'], (2, 17000, 100))

    def test_unknown_terminal_is_not_claimed_as_death(self):
        self.assertEqual(fuzz.terminal_kind(3, 'Route failed at 201 x=100 y=200 era=0 milestone=0'), 'unknown_stop')
        self.assertEqual(fuzz.terminal_kind(3, 'Route warped at 201 x=100 y=200'), 'unknown_stop')
        self.assertEqual(fuzz.terminal_kind(3, 'Route failed at 201 x=100 y=200 dead=2'), 'warp')
        self.assertEqual(fuzz.terminal_kind(3, 'Route died at 201 x=100 y=200'), 'death')

    def test_empty_success_trace_fails(self):
        def replay(argv, **kwargs):
            Path(argv[-1]).write_text('')
            return types.SimpleNamespace(returncode=0, stdout='', stderr='Tally complete')
        with patch.object(fuzz.subprocess, 'run', side_effect=replay):
            self.assertIn('trace_error', self.replay())

    def test_interrupted_batch_is_durable(self):
        with patch.object(fuzz, 'run', side_effect=KeyboardInterrupt), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(KeyboardInterrupt):
                fuzz.main(['--runs', '1', '--windows', 'ppz1A'])
        report = json.loads(next(fuzz.OUT.glob('*/report.json')).read_text())
        self.assertEqual(report['status'], 'interrupted')
        self.assertFalse(report['passed'])

    def test_worker_limit_is_enforced(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            fuzz.main(['--jobs', '5'])
        self.assertEqual(caught.exception.code, 2)


class CacheIdentityTests(unittest.TestCase):
    def test_included_header_and_compiler_change_invalidate_cache(self):
        scratch = Path(__file__).resolve().parents[1] / 'build'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='fuzz-cache-tests-', dir=scratch) as temporary:
            root = Path(temporary)
            for folder in ('src', 'tools', 'assets/generated', 'build/probe-source'):
                (root / folder).mkdir(parents=True, exist_ok=True)
            for file in ('tools/host.c', 'src/player_plus.c', 'src/nested.inc', 'src/scd_player.h'):
                (root / file).write_text('original text')
            def compile_host(argv, **kwargs):
                Path(argv[-1]).write_bytes(b'compiled mock executable')
                return types.SimpleNamespace(returncode=0)
            with patch.object(fuzz, 'ROOT', root), patch.object(fuzz, 'OUT', root / 'out'), \
                    patch.object(fuzz, 'HOSTS', {'test': ('tools/host.c', [], [], [])}), \
                    patch.object(fuzz, 'CORE', []), \
                    patch.object(fuzz.subprocess, 'check_output', return_value='clang v1') as version, \
                    patch.object(fuzz.subprocess, 'run', side_effect=compile_host) as compiler:
                fuzz.host('test', 0)
                fuzz.host('test', 0)
                self.assertEqual(compiler.call_count, 1)
                (root / 'src/nested.inc').write_text('changed included code')
                fuzz.host('test', 0)
                self.assertEqual(compiler.call_count, 2)
                (root / 'src/scd_player.h').write_text('changed layout')
                fuzz.host('test', 0)
                self.assertEqual(compiler.call_count, 3)
                version.return_value = 'clang v2'
                fuzz.host('test', 0)
                self.assertEqual(compiler.call_count, 4)
                self.assertEqual(compiler.call_args.kwargs['timeout'], 600)


if __name__ == '__main__':
    unittest.main()
