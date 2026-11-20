#!/usr/bin/env python3
"""Regression checks for accepting the wrong R5 redraw frame. No emulator."""
import unittest
from check_qq_switch_margin import MAGIC, MAX_WORK, verify


def frame(sequence, vblank, marker=0, work=10000):
    row = [0]*32
    row[0], row[2], row[6], row[30] = sequence, vblank, work, marker
    row[12:21] = [vblank]*9
    return 'Frame profile: ' + ' '.join(map(str, row)) + '\n'


class Margin(unittest.TestCase):
    def test_actual_event_after_unrelated_small_frame(self):
        log = frame(1, 500) + frame(2, 501, MAGIC|1) + frame(3, 502, MAGIC|6, MAX_WORK)
        self.assertEqual(verify(log)[0]['work'], MAX_WORK)

    def test_old_threshold_only_log_rejected(self):
        with self.assertRaisesRegex(AssertionError, 'no actual R5'):
            verify('CC route: 1 500 3585 0 0 0 0 0 0 3 1 0\n' + frame(1, 501))

    def test_over_budget_redraw_not_hidden_by_small_neighbour(self):
        with self.assertRaisesRegex(AssertionError, 'work'):
            verify(frame(1, 500) + frame(2, 501, MAGIC|1) + frame(3, 502, MAGIC|6, MAX_WORK+1))

    def test_rejects_missing_pair_slave_and_frame(self):
        for log in [frame(1, 500, MAGIC|6), frame(1, 500, MAGIC|1),
                    frame(1, 500, MAGIC|1)+frame(2, 501, MAGIC|2),
                    frame(1, 500, MAGIC|1)+frame(2, 502, MAGIC|6),
                    frame(1, 500, MAGIC|1)+frame(2, 501)+frame(3, 502, MAGIC|6)]:
            with self.subTest(log=log), self.assertRaises(AssertionError): verify(log)


if __name__ == '__main__':
    unittest.main()
