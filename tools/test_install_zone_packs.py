#!/usr/bin/env python3
"""tools/install_zone_packs.py uses a zone harvest only while it is current.

A harvest from an older extract_zone_auto.py (tool fac46649) once built
different round-8 packs and broke the MM3 replay. These cases pin the check
that catches that: the recorded tool and helper digests and every retail
program digest must match, and a stale round is re-extracted before anything
is installed. No disc or harvest is needed.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install_zone_packs as izp  # noqa: E402

TOOLS = {'tools/extract_zone_auto.py': 'a'*64, 'tools/convert_assets.py': 'b'*64, 'tools/extract_mmd.py': 'c'*64}
PROGRAMS = {'R81A': '1'*64, 'R83C': '2'*64}


def report(tools=TOOLS, programs=PROGRAMS):
    return {'tools': dict(tools), 'programs': {p: {'mmd_sha256': h} for p, h in programs.items()}}


class StaleReasons(unittest.TestCase):
    def test_current_harvest_is_used(self):
        self.assertEqual(izp.stale_reasons(report(), TOOLS, PROGRAMS), [])

    def test_missing_report(self):
        self.assertEqual(izp.stale_reasons(None, TOOLS, PROGRAMS), ['no report.json'])

    def test_harvest_without_recorded_tools(self):
        old = report(); del old['tools']
        reasons = izp.stale_reasons(old, TOOLS, PROGRAMS)
        self.assertEqual(len(reasons), 3)
        self.assertTrue(all('unrecorded' in r for r in reasons))

    def test_older_extractor(self):
        reasons = izp.stale_reasons(report({**TOOLS, 'tools/extract_zone_auto.py': 'fac46649'+'0'*56}), TOOLS, PROGRAMS)
        self.assertEqual(reasons, ['tools/extract_zone_auto.py fac46649 != current aaaaaaaa'])

    def test_changed_helper(self):
        reasons = izp.stale_reasons(report({**TOOLS, 'tools/extract_mmd.py': 'd'*64}), TOOLS, PROGRAMS)
        self.assertEqual(reasons, ['tools/extract_mmd.py dddddddd != current cccccccc'])

    def test_changed_disc_program(self):
        reasons = izp.stale_reasons(report(programs={**PROGRAMS, 'R83C': '3'*64}), TOOLS, PROGRAMS)
        self.assertEqual(reasons, ['R83C__.MMD differs from the disc'])

    def test_missing_program(self):
        reasons = izp.stale_reasons(report(programs={'R81A': PROGRAMS['R81A']}), TOOLS, PROGRAMS)
        self.assertEqual(reasons, ['R83C missing'])


class Refresh(unittest.TestCase):
    """refresh_harvest re-extracts exactly the stale rounds, and stops when a
    re-extract does not make the round current."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root/'build/retail').mkdir(parents=True)
        (root/'build/retail/sonic.iso').write_bytes(b'')
        self.saved = (izp.ROOT, izp.disc_files, izp.harvest.tool_hashes, izp.harvest.programs_of, izp.subprocess.run)
        disc = {'R31A__.MMD': b'cc', 'R81A__.MMD': b'mm'}
        izp.ROOT = root
        izp.disc_files = lambda iso: disc
        izp.harvest.tool_hashes = lambda: TOOLS
        izp.harvest.programs_of = lambda rnd: [f'R{rnd}1A']
        self.digest = {rnd: izp.sha(disc[f'R{rnd}1A__.MMD']) for rnd in (3, 8)}
        self.calls = []
        self.root = root

    def tearDown(self):
        izp.ROOT, izp.disc_files, izp.harvest.tool_hashes, izp.harvest.programs_of, izp.subprocess.run = self.saved
        self.tmp.cleanup()

    def write(self, rnd, tools):
        path = self.root/f'build/auto-extract/{rnd}/report.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report(tools, {f'R{rnd}1A': self.digest[rnd]})))

    def extractor(self, heals):
        def run(cmd, **kwargs):
            rnd = int(cmd[2]); self.calls.append((rnd, cmd[3]))
            if heals: self.write(rnd, TOOLS)
            return subprocess.CompletedProcess(cmd, 0)
        return run

    def test_only_stale_round_is_reextracted(self):
        self.write(3, TOOLS)
        self.write(8, {**TOOLS, 'tools/extract_zone_auto.py': 'fac46649'+'0'*56})
        izp.subprocess.run = self.extractor(heals=True)
        reports, refreshed = izp.refresh_harvest([3, 8])
        self.assertEqual(self.calls, [(8, '--manifest')])
        self.assertEqual(refreshed, {8})
        self.assertEqual(reports[8]['tools'], TOOLS)

    def test_missing_manifest_reextracts_every_round(self):
        self.write(3, TOOLS); self.write(8, TOOLS)
        izp.subprocess.run = self.extractor(heals=True)
        _, refreshed = izp.refresh_harvest([3, 8], force=True)
        self.assertEqual(self.calls, [(3, '--manifest'), (8, '--manifest')])
        self.assertEqual(refreshed, {3, 8})

    def test_interrupted_install_still_replaces_next_run(self):
        # A run stopped after re-extracting R8 but before installing it: the
        # next run finds the harvest current, yet must still replace R8's packs.
        self.write(3, TOOLS)
        self.write(8, {**TOOLS, 'tools/extract_zone_auto.py': 'fac46649'+'0'*56})
        izp.subprocess.run = self.extractor(heals=True)
        izp.refresh_harvest([3, 8])
        self.assertEqual(json.loads(izp.pending_path().read_text()), [8])
        self.calls.clear()
        _, refreshed = izp.refresh_harvest([3, 8])
        self.assertEqual((self.calls, refreshed), ([], {8}))
        izp.save_pending(set())  # what main() does once every pack is installed
        self.assertFalse(izp.pending_path().exists())
        self.assertEqual(izp.refresh_harvest([3, 8])[1], set())

    def test_still_stale_after_reextract_stops(self):
        self.write(8, {**TOOLS, 'tools/extract_zone_auto.py': 'fac46649'+'0'*56})
        izp.subprocess.run = self.extractor(heals=False)
        with self.assertRaises(SystemExit) as stop:
            izp.refresh_harvest([8])
        self.assertIn('still stale', str(stop.exception))


class NewManifest(unittest.TestCase):
    """extract_zone_auto.update_manifest creates the manifest and its rows
    when a fresh checkout has none, and refreshes an existing row."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = izp.harvest.MANIFEST
        izp.harvest.MANIFEST = Path(self.tmp.name)/'all-zones-extract.json'

    def tearDown(self):
        izp.harvest.MANIFEST = self.saved
        self.tmp.cleanup()

    def entry(self, pack='p'*64):
        return {'mmd_sha256': '1'*64, 'chunks': 111, 'pack_bytes': 81272, 'pack_sha256': pack,
                'collision_bytes': 9472, 'collision_sha256': 'c'*64, 'objects_sha256': 'o'*64,
                'animated_tiles': [], 'pc_failed': []}

    def test_creates_manifest_then_refreshes_row(self):
        izp.harvest.update_manifest({'round': 8, 'source': 'build/retail/sonic.iso', 'programs': {'R83C': self.entry()}})
        manifest = json.loads(izp.harvest.MANIFEST.read_text())
        self.assertEqual(manifest['era_slot_bytes'], {'PPZ0': 0x18000, 'PPZ1': 0x16800, 'PPZ2': 0x16800, 'PPZ3': 0x17000})
        self.assertEqual(manifest['collision_slot_bytes'], {f'COL{i}': 0x2800 for i in range(4)})
        self.assertEqual(manifest['tool_sha256'], izp.harvest.tool_hashes()['tools/extract_zone_auto.py'])
        row = manifest['rounds']['R8']['program_data']['R83C']
        self.assertEqual((row['pack_bytes'], row['pack_headroom_bytes'], row['collision_bytes']), (81272, 0x16800-81272, 9472))  # R83C: era C loads into PPZ2
        self.assertTrue(manifest['rounds']['R8']['all_pc_checks_passed'])
        izp.harvest.update_manifest({'round': 8, 'source': 'x', 'programs': {'R83C': self.entry('q'*64)}})
        row = json.loads(izp.harvest.MANIFEST.read_text())['rounds']['R8']['program_data']['R83C']
        self.assertEqual(row['pack_sha256'], 'q'*64)


if __name__ == '__main__':
    result = unittest.main(exit=False, verbosity=0).result
    if not result.wasSuccessful():
        sys.exit(1)
    print(f'PASS: install_zone_packs harvest check: {result.testsRun} cases')
