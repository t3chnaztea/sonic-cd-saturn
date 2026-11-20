import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from check_sequence_replay import check
from test_act_pacing import fixture


class SequenceReplay(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name) / 'run'
        self.reference = Path(self.tmp.name) / 'reference'
        self.folder.mkdir(); self.reference.mkdir()
        log, trace = fixture()
        self.names = ['player-target-trace.txt', 'act2-target-trace.txt', 'act3-target-trace.txt']
        for name in self.names:
            (self.folder / name).write_text(trace)
            (self.reference / name).write_text(trace)
        (self.folder / 'results.log').write_text('\n'.join([log] * 3) +
            '\nAct 3 end: prototype screen shown, Start returned to the title screen after 184 frames\n')
        self.disc = Path(self.tmp.name) / 'disc.bin'
        self.disc.write_bytes(b'diagnostic fixture')
        (self.folder / 'input-hashes.txt').write_text(
            hashlib.sha256(self.disc.read_bytes()).hexdigest() + '  ' + str(self.disc) + '\n')

    def test_valid_measurement_is_not_release_acceptance(self):
        check(self.folder, self.reference)
        report = json.loads((self.folder / 'pacing-report.json').read_text())
        self.assertTrue(report['measurement_complete'])
        self.assertFalse(report['release_gate'])
        self.assertFalse(report['zero_missed_refreshes'])
        self.assertEqual(report['pacing']['2']['late'], 1)

    def test_each_act_must_match(self):
        for name in self.names:
            path = self.reference / name
            original = path.read_text()
            path.write_text(original.replace(' 8 ', ' 0 ', 1))
            with self.assertRaises(AssertionError): check(self.folder, self.reference)
            path.write_text(original)

    def test_changed_build_rejected(self):
        self.disc.write_bytes(b'another build')
        with self.assertRaises(AssertionError): check(self.folder, self.reference)

    def test_incomplete_sequence_rejected(self):
        path = self.folder / 'results.log'
        path.write_text(path.read_text().split('Act 3 end:')[0])
        with self.assertRaises(AssertionError): check(self.folder, self.reference)


if __name__ == '__main__': unittest.main()
