"""Negative controls for the full-route timing evidence parser."""
import unittest
from act_pacing import measure


def fixture(ticks=(100, 101, 103)):
    rows, timing = [], []
    for i, tick in enumerate(ticks):
        state = [65536*(i+1), 65536*9, 0, 0, 0, 0, i+1, 0, 0, 0, 0, 0, 7<<16, 0, 0, 0]
        rows.append(f'{40+i} 8 ' + ' '.join(f'{v:08x}' for v in state))
        timing.append(f'Act timing: sequence={40+i} simulation={i+1} vblank={tick} x={state[0]} y={state[1]} objects=7')
    timing.append('Act pacing: intervals=2 vblanks=3 late=1 max_gap=2')
    return '\n'.join(timing), '\n'.join(rows)


class Pacing(unittest.TestCase):
    def test_valid(self):
        result = measure(*fixture())
        self.assertEqual(result['gaps'], [dict(simulation=3, vblanks=2, x=3, y=9, active_objects=7)])

    def test_missing_and_extra_records(self):
        log, trace = fixture()
        for changed in (log.split('\n', 1)[1], log+'\n'+log.splitlines()[0]):
            with self.assertRaises(AssertionError): measure(changed, trace)

    def test_mismatched_fields(self):
        log, trace = fixture()
        for old, new in [('sequence=41', 'sequence=42'), ('simulation=2', 'simulation=3'),
                         ('x=131072', 'x=131073'), ('objects=7', 'objects=8'),
                         ('late=1', 'late=0'), ('vblanks=3', 'vblanks=2')]:
            with self.assertRaises(AssertionError): measure(log.replace(old, new), trace)

    def test_nonincreasing_tick(self):
        with self.assertRaises(AssertionError): measure(*fixture((100, 100, 103)))
        with self.assertRaises(AssertionError): measure(*fixture((100, 99, 103)))


if __name__ == '__main__': unittest.main()
