#!/usr/bin/env python3
"""Check real substep boundaries without running game converters."""
import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import background_tables as tables
import native

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('patcher_bootstrap', ROOT / 'web/patcher/py/bootstrap.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


class BackgroundProgressTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'build').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'build')
        self.root = Path(self.temp.name)
        (self.root / 'build').mkdir()
        (self.root / 'assets').mkdir()
        self.events = []
        self.previous = native.set_progress_reporter(lambda *args: self.events.append(args))

    def tearDown(self):
        native.set_progress_reporter(self.previous)
        self.temp.cleanup()

    def run_tables(self, arguments=(), cached=False, failure=None):
        if cached:
            (self.root / 'build/scroll-ir.stamp').write_text('matching\n')
        with patch.object(tables, 'ROOT', self.root), patch.object(tables, 'retail_iso'), \
                patch.object(tables, 'ir_inputs', return_value='matching\n'), \
                patch.object(tables.subprocess, 'run', side_effect=failure) as run, \
                patch.object(sys, 'argv', ['background_tables.py', *arguments]), \
                contextlib.redirect_stdout(io.StringIO()):
            tables.main()
        return [call.args[0][1:] for call in run.call_args_list]

    def test_cold_order_and_complete(self):
        commands = self.run_tables()
        expected = tables.STEPS + [[g] for g in tables.GENERATORS]
        self.assertEqual(commands, expected)
        self.assertEqual([event[1] for event in self.events], list(range(17)))
        self.assertTrue(all(event[2] == 16 for event in self.events))
        self.assertIn('Collision Chaos', self.events[1][0])
        self.assertIn('Metallic Madness', self.events[6][0])
        self.assertEqual(self.events[-1], ('Background tables ready', 16, 16))

    def test_verified_cache_skips_only_extractors(self):
        commands = self.run_tables(cached=True)
        self.assertEqual(commands, tables.STEPS[:1] + [[g] for g in tables.GENERATORS])
        self.assertEqual(self.events[1], ('Reusing verified scroll tables', 7, 16))
        self.assertEqual(self.events[-1][1:], (16, 16))

    def test_failure_does_not_report_complete(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_tables(failure=subprocess.CalledProcessError(1, ['converter']))
        self.assertEqual(len(self.events), 1)

    def test_terrain_reports_each_original_command(self):
        commands = self.run_tables(arguments=['--terrain'])
        self.assertEqual(commands, [[g] for g in tables.TERRAIN])
        self.assertEqual([event[1] for event in self.events], list(range(5)))

    def test_callback_survives_nested_python_and_is_restored(self):
        script = self.root / 'probe.py'
        script.write_text('from native import report_progress\nreport_progress("nested", 0, 1)\n')
        nested = []
        with patch.object(bootstrap, 'ROOT', self.root):
            bootstrap.convert(str(script), [], lambda *args: nested.append(args))
        self.assertEqual(nested, [('nested', 0, 1)])
        native.report_progress('restored', 1, 1)
        self.assertEqual(self.events, [('restored', 1, 1)])
        script.write_text('raise SystemExit(1)\n')
        with patch.object(bootstrap, 'ROOT', self.root), self.assertRaises(RuntimeError):
            bootstrap.convert(str(script), [], lambda *args: nested.append(args))
        native.report_progress('restored after failure', 1, 1)
        self.assertEqual(self.events[-1], ('restored after failure', 1, 1))


if __name__ == '__main__':
    unittest.main()
