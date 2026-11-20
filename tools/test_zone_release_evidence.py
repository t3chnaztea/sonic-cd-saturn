"""Focused release-proof checks; no emulator, build, or game assets required."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from zone_release_evidence import (GATES, SPECIAL, SPECIAL_CASES, ZONES, audit, digest, expected_windows,
                                   matrix_command, release_special, release_zones)

ROOT = Path(__file__).resolve().parents[1]
DISC = 'd' * 64


class ReleaseEvidenceTests(unittest.TestCase):
    version = '0.078'
    zones = ZONES
    special = True
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='zone-proof-test-', dir=ROOT/'build')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'Makefile').write_text(f'IP_VERSION:= V{self.version}\n')
        self.path = self.root/'build/zone-gates/test/report.json'
        command = matrix_command(self.zones, self.special)
        self.matrix = dict(passed=True, status='passed', bin_sha256=DISC, bin_sha256_end=DISC,
                           failed_gates=0, zones=command[3].split(','), gates=command[5].split(','),
                           hardware_tested=False, results={})
        for zone, gates in expected_windows(self.zones, self.special).items():
            self.matrix['results'][zone] = {}
            for gate, names in gates.items():
                self.matrix['results'][zone][gate] = {}
                for name in names:
                    child = dict(passed=True, disc_sha256=DISC, respawns=0, late_gameplay_intervals=[])
                    if gate == 'retail':
                        child = dict(passed=False, disc_sha256=None, inputs={'source.c': 'a'*64},
                                     retail_parity=dict(compared=10, contiguous=10, contiguous_all_fields=10, native_end='Tally complete: sequence=20',
                                                        retail_restart=None, retail_updates=23))
                    if (zone, gate, name) == ('ppz', 'campaign', 'PPZ3'):
                        child['backup_after_sha256'] = 'b'*64
                    entry = dict(status='pass', returncode=0)
                    for field, folder in (('evidence', 'evidence'), ('log', 'logs')):
                        path = self.path.parent/folder/f'{zone}-{gate}-{name}.{ "json" if field == "evidence" else "log"}'
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(json.dumps(child) if field == 'evidence' else 'PASS\n')
                        entry[field] = str(path.relative_to(self.root))
                        entry[field+'_sha256'] = digest(path)
                    self.matrix['results'][zone][gate][name] = entry
        self.change_child('cc', 'campaign', 'checkpoint',
                          ppz3_report_sha256=self.matrix['results']['ppz']['campaign']['PPZ3']['evidence_sha256'],
                          backup_sha256='b'*64, saved_flags=0x100)
        self.change_child('cc', 'campaign', 'act3-good-bad', entry_backup_sha256='b'*64)
        links = []
        if 'ss' in self.zones:
            self.change_child('ww', 'campaign', 'WW3', backup_after_sha256='c'*64)
            links += [('ss', 1, 'ww', 'WW3'), ('ss', 2, 'ss', 'SS1'), ('ss', 3, 'ss', 'SS2')]
        if 'mm' in self.zones:
            links += [('mm', 1, 'ss', 'SS3'), ('mm', 2, 'mm', 'MM1'), ('mm', 3, 'mm', 'MM2')]
            self.change_child('mm', 'campaign', 'MM3', completed=1, title_frame=9000)
        for zone, act, prior_zone, prior_name in links:
            prior = self.matrix['results'][prior_zone]['campaign'][prior_name]
            backup = json.loads((self.root/prior['evidence']).read_text())['backup_after_sha256']
            self.change_child(zone, 'campaign', f'{zone.upper()}{act}',
                              entry_evidence=dict(sha256=prior['evidence_sha256']),
                              entry_backup_sha256=backup, backup_after_sha256=(str(act) if zone == 'ss' else 'abc'[act-1])*64)
        self.qa = dict(passed=True, status='passed', mode='full', disc_sha256=DISC,
                       steps=[dict(command=matrix_command(self.zones, self.special), exit_code=0)], zone_gates_report=str(self.path.relative_to(self.root)))
        self.save()

    def change_child(self, zone, gate, name, **changes):
        entry = self.matrix['results'][zone][gate][name]
        path = self.root/entry['evidence']
        child = json.loads(path.read_text())
        child.update(changes)
        path.write_text(json.dumps(child))
        entry['evidence_sha256'] = digest(path)

    def save(self):
        self.path.write_text(json.dumps(self.matrix))
        self.qa['zone_gates_report_sha256'] = digest(self.path)

    def test_complete_and_staged(self):
        _, artifacts = audit(self.root, self.qa, DISC)
        self.assertEqual(len(artifacts), {'0.076': 435, '0.077': 521, '0.078': 695}[self.version])
        for source, target in artifacts:
            path = self.root/'dist'/target
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, path)
        audit(self.root, self.qa, DISC, staged=True)

    def test_missing_window(self):
        del self.matrix['results']['ww']['routes']['WW2D']
        self.save()
        with self.assertRaisesRegex(AssertionError, 'Missing or extra windows'):
            audit(self.root, self.qa, DISC)

    def test_wrong_release_scope(self):
        other = ZONES[:6] if len(self.zones) != 6 else ZONES
        self.qa['steps'] = [dict(command=matrix_command(other, self.special), exit_code=0)]
        with self.assertRaisesRegex(AssertionError, 'Missing full release zone gate'):
            audit(self.root, self.qa, DISC)

    def test_position_match_with_velocity_split(self):
        entry = self.matrix['results']['ww']['retail']['WW2D']
        child = json.loads((self.root/entry['evidence']).read_text())
        parity = child['retail_parity']
        parity.update(contiguous_all_fields=9,
                      first_field_divergence=dict(sequence=19, fields=['yspeed']))
        self.change_child('ww', 'retail', 'WW2D', retail_parity=parity)
        self.save()
        with self.assertRaisesRegex(AssertionError, 'Incomplete nine-field retail match'):
            audit(self.root, self.qa, DISC)

    def test_wrong_child_bin(self):
        self.change_child('ww', 'art', 'WW2D', disc_sha256='e'*64)
        self.save()
        with self.assertRaisesRegex(AssertionError, 'Child BIN mismatch'):
            audit(self.root, self.qa, DISC)

    def test_changed_evidence(self):
        entry = self.matrix['results']['ww']['art']['WW2D']
        (self.root/entry['evidence']).write_text('{}')
        with self.assertRaisesRegex(AssertionError, 'Changed zone artifact'):
            audit(self.root, self.qa, DISC)

    def test_broken_ppz_link(self):
        self.change_child('cc', 'campaign', 'checkpoint', ppz3_report_sha256='f'*64)
        self.save()
        with self.assertRaisesRegex(AssertionError, 'not linked'):
            audit(self.root, self.qa, DISC)

    def test_ss_wrong_predecessor_report(self):
        if 'ss' not in self.zones:
            self.skipTest('V0.076 has no SS campaign')
        for act in (1, 2, 3):
            name = f'SS{act}'
            entry = self.matrix['results']['ss']['campaign'][name]
            original = json.loads((self.root/entry['evidence']).read_text())
            with self.subTest(act=act):
                self.change_child('ss', 'campaign', name, entry_evidence=dict(sha256='f'*64))
                self.save()
                with self.assertRaisesRegex(AssertionError, name+' is not linked'):
                    audit(self.root, self.qa, DISC)
                self.change_child('ss', 'campaign', name, **original)
                self.save()

    def test_ss_wrong_predecessor_backup(self):
        if 'ss' not in self.zones:
            self.skipTest('V0.076 has no SS campaign')
        for act in (1, 2, 3):
            name = f'SS{act}'
            entry = self.matrix['results']['ss']['campaign'][name]
            original = json.loads((self.root/entry['evidence']).read_text())
            with self.subTest(act=act):
                self.change_child('ss', 'campaign', name, entry_backup_sha256='f'*64)
                self.save()
                with self.assertRaisesRegex(AssertionError, name+' uses a different'):
                    audit(self.root, self.qa, DISC)
                self.change_child('ss', 'campaign', name, **original)
                self.save()

    def test_mm_link_and_game_end(self):
        if 'mm' not in self.zones:
            self.skipTest('no MM campaign before V0.078')
        entry = self.matrix['results']['mm']['campaign']['MM1']
        original = json.loads((self.root/entry['evidence']).read_text())
        self.change_child('mm', 'campaign', 'MM1', entry_backup_sha256='f'*64)
        self.save()
        with self.assertRaisesRegex(AssertionError, 'MM1 uses a different SS3 save'):
            audit(self.root, self.qa, DISC)
        self.change_child('mm', 'campaign', 'MM1', **original)
        self.change_child('mm', 'campaign', 'MM3', completed=0)
        self.save()
        with self.assertRaisesRegex(AssertionError, 'MM3 did not end the game'):
            audit(self.root, self.qa, DISC)

    def test_special_scope(self):
        if not self.special:
            self.skipTest('no special-stage gate before V0.078')
        self.qa['steps'] = [dict(command=matrix_command(self.zones), exit_code=0)]
        with self.assertRaisesRegex(AssertionError, 'Missing full release zone gate'):
            audit(self.root, self.qa, DISC)
        self.qa['steps'] = [dict(command=matrix_command(self.zones, True), exit_code=0)]
        del self.matrix['results'][SPECIAL]['special']['ENDING-good']
        self.save()
        with self.assertRaisesRegex(AssertionError, 'Missing or extra windows'):
            audit(self.root, self.qa, DISC)

    def test_late_route(self):
        self.change_child('ww', 'routes', 'WW2D', late_gameplay_intervals=[40])
        self.save()
        with self.assertRaisesRegex(AssertionError, 'Route regression'):
            audit(self.root, self.qa, DISC)


class SixZoneReleaseEvidenceTests(ReleaseEvidenceTests):
    version = '0.077'
    zones = ZONES[:6]
    special = False


class FiveZoneReleaseEvidenceTests(ReleaseEvidenceTests):
    version = '0.076'
    zones = ZONES[:5]
    special = False


class MatrixWiringTests(unittest.TestCase):
    def test_retail_parser_rejects_velocity_only_split(self):
        spec = importlib.util.spec_from_file_location('zone_gates', ROOT/'tools/zone-gates.py')
        driver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(driver)
        result = dict(returncode=0, tail=['Tally complete: sequence=20'])
        parity = dict(compared=10, contiguous=10, matched=10, contiguous_all_fields=10,
                      native_end='Tally complete: sequence=20', retail_restart=None,
                      retail_updates=23)
        self.assertEqual(driver.parse_retail(result, dict(retail_parity=parity))[0], 'pass')
        parity.update(contiguous_all_fields=9,
                      first_field_divergence=dict(sequence=19, fields=['yspeed']))
        status, _, note = driver.parse_retail(result, dict(retail_parity=parity))
        self.assertEqual(status, 'fail')
        self.assertIn('yspeed', note)
        parity.pop('contiguous_all_fields')
        parity.pop('first_field_divergence')
        self.assertEqual(driver.parse_retail(result, dict(retail_parity=parity))[0], 'fail')

    def test_campaign_links_and_coverage(self):
        spec = importlib.util.spec_from_file_location('zone_gates', ROOT/'tools/zone-gates.py')
        driver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(driver)
        folder = ROOT/'build/zone-gates/test'
        runs, windows = driver.build_matrix(ZONES, GATES, folder)
        self.assertEqual(len(windows), 305)
        actual = {}
        for w in windows:
            actual.setdefault(w.zone, {}).setdefault(w.gate, set()).add(w.name)
        self.assertEqual(actual, expected_windows())
        ss = [w for w in windows if w.zone == 'ss']
        self.assertEqual(len(ss), 43)
        for w in ss:
            if w.gate in ('retail', 'routes'):
                self.assertIn('--ss', w.run.cmds[0])
        mm = [w for w in windows if w.zone == 'mm']
        self.assertEqual(len(mm), 45)
        for w in mm:
            if w.gate in ('retail', 'routes') and w.run:
                self.assertIn('--mm', w.run.cmds[0])
            elif w.gate in ('retail', 'routes'):
                self.assertIn('no stored route', w.missing)
        self.assertIn('--to', runs['travel', 'MM2DA'].cmds[0])
        mm1 = runs['campaign', 'mm', 1].cmds[0]
        self.assertEqual(mm1[:2], ['python3', 'tools/test_mm_campaign.py'])
        self.assertIn(release_zones(ROOT), (ZONES[:5], ZONES[:6], ZONES))
        checkpoint = runs['campaign', 'cc', 'checkpoint'].cmds[0]
        self.assertEqual(checkpoint[checkpoint.index('--ppz3-report')+1], str(folder/'campaign/PPZ3/report.json'))
        cc = runs['campaign', 'cc', 'act3-good-bad'].cmds[0]
        self.assertEqual(cc[cc.index('--checkpoint-report')+1], str(ROOT/'build/cc1/generator/campaign-checkpoint-report.json'))
        _, special = driver.build_matrix([SPECIAL, 'mm'], [*GATES, 'special'], folder)
        names = {w.name for w in special if w.zone == SPECIAL}
        self.assertEqual(names, set(SPECIAL_CASES))
        self.assertTrue(all(w.gate == 'special' for w in special if w.zone == SPECIAL))
        self.assertFalse([w for w in special if w.zone == 'mm' and w.gate == 'special'])
        self.assertTrue(all(w.missing or w.run for w in special))
        subset, _ = driver.build_matrix(['cc'], ['campaign'], folder)
        self.assertNotIn('--ppz3-report', subset['campaign', 'cc', 'checkpoint'].cmds[0])


if __name__ == '__main__':
    unittest.main()
