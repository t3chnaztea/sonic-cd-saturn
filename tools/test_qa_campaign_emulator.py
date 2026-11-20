#!/usr/bin/env python3
"""Negative checks for the bounded emulator-prefix evidence parser."""
from pathlib import Path
import contextlib
import io
import json
import tempfile
import unittest
from unittest.mock import patch

import qa_campaign_emulator as q


class EmulatorEvidence(unittest.TestCase):
    def setUp(self):
        self.expected = [[2, 128, 10, 20], [3, 129, 11, 20]]
        self.log = ('CC route: 2 100 10 20 0 0 0 0 128 0 0 0\n'
                    'CC route: 3 101 11 20 0 0 0 0 129 0 0 0\n'
                    'Route peek: 2 00001f1f |\nRoute peek: 3 00001f1f |\n'
                    'CC route ended: updates=2 max_x=11\n')

    def check_log(self, log):
        return q.verify_output(log, self.expected, 0, 31, [2, 3])

    def test_complete_prefix_passes(self):
        self.assertEqual(self.check_log(self.log)['matched_positions'], 2)

    def test_wrong_active_preset_fails(self):
        with self.assertRaisesRegex(ValueError, 'preset'):
            self.check_log(self.log.replace('00001f1f', '00000000'))

    def test_position_divergence_fails(self):
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            self.check_log(self.log.replace('3 101 11 20', '3 101 12 20'))

    def test_controller_divergence_fails(self):
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            self.check_log(self.log.replace('129 0 0 0', '128 0 0 0'))

    def test_late_observation_fails(self):
        with self.assertRaisesRegex(ValueError, 'interval'):
            self.check_log(self.log.replace('3 101', '3 103'))

    def test_missing_preset_peek_fails(self):
        with self.assertRaisesRegex(ValueError, 'preset observations'):
            self.check_log(self.log.replace('Route peek: 3 00001f1f |\n', ''))

    def test_respawn_fails(self):
        with self.assertRaisesRegex(ValueError, 'respawn'):
            self.check_log(self.log.replace('3 101 11 20 0 0 0 0', '3 101 11 20 0 0 1 0'))

    def test_early_stage_change_fails(self):
        with self.assertRaisesRegex(ValueError, 'stage transition'):
            self.check_log(self.log.replace('129 0 0 0', '129 1 0 0'))

    def test_missing_end_fails(self):
        with self.assertRaisesRegex(ValueError, 'end not observed'):
            self.check_log(self.log.split('CC route ended:')[0])

    def test_short_or_nonconsecutive_host_prefix_fails(self):
        scratch = q.ROOT / 'build'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            path = Path(temporary) / 'trace'
            path.write_text('2 128 10 20\n')
            with self.assertRaisesRegex(ValueError, 'too short'):
                q.prefix_rows(path, 2)
            path.write_text('3 128 10 20\n')
            with self.assertRaisesRegex(ValueError, 'invalid host trace'):
                q.prefix_rows(path, 1)

    def test_retail_parity_current_sample_cannot_be_controller_oracle(self):
        # TT1A Classic seed8107, sequence432. The actor moves from x560 to559
        # during water_currents AFTER main's published player snapshot.
        scratch = q.ROOT / 'build'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            path = Path(temporary) / 'parity'
            path.write_text('2 65 559 754 642 640 1024 67 1863 0 0 0 0\n')
            with self.assertRaisesRegex(ValueError, 'invalid host trace'):
                q.prefix_rows(path, 1)
        log = ('CC route: 432 2246 560 754 67 0 0 20 65 2 0 0\n'
               'Route peek: 432 00000000 |\nCC route ended: updates=1 max_x=560\n')
        q.verify_output(log, [[432, 65, 560, 754]], 2, 0, [432])
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            q.verify_output(log, [[432, 65, 559, 754]], 2, 0, [432])

    def test_interruption_marks_aggregate_report(self):
        scratch = q.ROOT / 'build'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            out = Path(temporary)
            q.save(out / 'report.json', dict(status='pending', passed=False, snapshots={},
                                           cases={'ppz1A-0': dict(status='pending')}))
            with patch.object(q, 'sha', return_value='same'), \
                    patch.object(q, 'run_case', side_effect=KeyboardInterrupt), \
                    contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(KeyboardInterrupt):
                    q.main(['--resume', str(out), '--case', 'ppz1A-0'])
            report = json.loads((out / 'report.json').read_text())
            self.assertEqual(report['status'], 'interrupted')
            self.assertFalse(report['passed'])


if __name__ == '__main__':
    unittest.main()
