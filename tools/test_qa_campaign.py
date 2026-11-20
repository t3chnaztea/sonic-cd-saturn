#!/usr/bin/env python3
"""Negative checks protect campaign evidence and failure detection."""
import tempfile
from pathlib import Path
import unittest
import qa_campaign as q

class Campaign(unittest.TestCase):
    def setUp(self):
        (q.ROOT / 'build/qa-campaign').mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=q.ROOT / 'build/qa-campaign')
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'rows'
        self.path.write_text('2 128 10 20 0 0 0 0 0 0 0 0 0\n3 128 11 20 0 0 0 0 0 0 0 0 0\n')
        self.log = 'CAMPAIGN 120 1 2 0 3 0 -1 12 0 0\n'
    def test_valid_trace(self):
        r = q.classify(1, self.log, [self.path])
        self.assertEqual(r['failures'], [])
        self.assertEqual(r['checkpoints'], [1])
    def test_injected_sanitizer_defect(self):
        self.assertIn('sanitizer', q.classify(1, self.log + 'runtime error: injected test defect\n', [self.path])['failures'])
    def test_classic_crash_fails(self):
        self.assertIn('host_exit', q.classify(-11, self.log, [self.path])['failures'])
    def test_empty_and_invalid_traces_fail(self):
        for text in ('', '2 128 10\n', '2 128 BAD\n'):
            self.path.write_text(text)
            self.assertIn('invalid_trace', q.classify(0, self.log, [self.path])['failures'])
    def test_observer_required(self):
        self.assertIn('missing_or_invalid_observer', q.classify(1, '', [self.path])['failures'])
    def test_short_observer_does_not_crash(self):
        for text in ('CAMPAIGN', 'CAMPAIGN 1', 'CAMPAIGN 1 2 3 4 5 6 7 8'):
            self.assertIn('missing_or_invalid_observer', q.classify(1, text + ' \n', [self.path])['failures'])
    def test_out_of_bounds_candidate(self):
        self.path.write_text('2 128 20000 20 0 0 0 0 0 0 0 0 0\n')
        self.assertIn('bounds_candidate', q.classify(1, self.log, [self.path])['failures'])
    def test_mutation_reproducible_and_changes_input(self):
        pads = [128] * 2000
        a, m = q.mutate(pads, 1)
        self.assertEqual((a, m), q.mutate(pads, 1))
        self.assertNotEqual(a, pads)
        self.assertEqual(a[:m['start']], pads[:m['start']])
        self.assertEqual(a[m['end']:], pads[m['end']:])
    def test_pad_roundtrip(self):
        pads, _ = q.mutate([128] * 2000, 123)
        q.write_pad(self.path, pads)
        self.assertEqual(q.load_pad(self.path), pads)
    def test_instrumentation_fails_closed(self):
        with self.assertRaises(ValueError): q.instrument('int main(){return 0;}')

if __name__ == '__main__': unittest.main()
