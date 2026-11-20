#!/usr/bin/env python3
"""The source-only release refuses disc images, BIOS, audio and private paths."""
import contextlib
import io
import os
import pathlib
import shutil
import tempfile
import unittest

import release
from release import ForbiddenFile, check_allowed


def fake_ip(product=b'T-99901G  V0.078', date=b'20261018'):
    ip = bytearray(256)
    ip[0:16] = b'SEGA SEGASATURN '
    ip[0x10:0x20] = b'SEGA TP KAISHA-A'
    ip[0x20:0x30] = product
    ip[0x30:0x38] = date
    ip[0x38:0x70] = b'CD-1/1  JTUBKAEL        J               SONIC CD SATURN'.ljust(56)[:56]
    return bytes(ip)


def raw_sector(ip):
    sector = bytearray(2352)
    sector[0:12] = b'\x00' + b'\xff' * 10 + b'\x00'
    sector[12:16] = b'\x00\x02\x00\x01'
    sector[16:16 + len(ip)] = ip
    return bytes(sector)


class ForbiddenFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, data=b'text\n'):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_disc_image_and_audio_types_refused(self):
        for name in ['game.bin', 'game.BIN', 'game.cue', 'game.iso', 'game.chd',
                     'track02.wav', 'music.ogg', 'disc.img', 'game.ccd', 'x.bin.txt']:
            with self.subTest(name=name), self.assertRaises(ForbiddenFile):
                check_allowed(self.write(name), self.root)

    def test_bios_names_refused(self):
        for name in ['bios_CD_U.dat', 'Saturn_BIOS.txt', 'mpr-17933.dat', 'sega_101.dat']:
            with self.subTest(name=name), self.assertRaises(ForbiddenFile):
                check_allowed(self.write(name), self.root)

    def test_private_and_output_dirs_refused(self):
        for rel in ['assets/private/notes.md', 'dist/README.md', 'build/hardware-v0.078/READ-ME-FIRST.md',
                    'build/release-v0.078/x.json', 'cd/0.TXT', 'audio-tracks/list.txt']:
            with self.subTest(rel=rel), self.assertRaises(ForbiddenFile):
                check_allowed(self.write(rel), self.root)

    def test_renamed_disc_or_audio_content_refused(self):
        cases = {'disc.txt': raw_sector(fake_ip()), 'ip.dat': fake_ip(),
                 'song.txt': b'RIFF\x00\x00\x00\x00WAVEfmt ', 'chd.dat': b'MComprHD' + bytes(8)}
        for name, data in cases.items():
            with self.subTest(name=name), self.assertRaises(ForbiddenFile):
                check_allowed(self.write(name, data), self.root)

    def test_symlink_into_private_refused(self):
        target = self.write('assets/private/notes.md', b'# private\n')
        link = self.root / 'docs' / 'notes.md'
        link.parent.mkdir()
        link.symlink_to(target)
        with self.assertRaises(ForbiddenFile):
            check_allowed(link, self.root)

    def test_docs_allowed(self):
        for rel, data in [('README.md', b'# hi\n'), ('CHANGELOG.md', b'# Changelog\n'),
                          ('THIRD-PARTY.md', b'# Credits\n'), ('LICENSE', b'MIT\n')]:
            with self.subTest(rel=rel):
                check_allowed(self.write(rel, data), self.root)

    def test_zip_member_names_checked(self):
        with self.assertRaises(ForbiddenFile):
            release.check_name('pkg/sonic-cd-saturn-prototype.bin')
        release.check_name('pkg/BUILDING.md')


class BuildRelease(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name) / 'repo'
        real = release.ROOT
        for rel in release.DOCS + ['Makefile']:
            dst = self.root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(real / rel, dst)
        version = release.makefile_value('IP_VERSION', real)
        shutil.copyfile(release.release_notes(version, real), self.root / f'RELEASE-NOTES-{version}.md')
        self.version = version
        self.bin = pathlib.Path(self.tmp.name) / 'tested.bin'
        self.bin.write_bytes(raw_sector(fake_ip(b'T-99901G  ' + version.encode())))
        self.out = pathlib.Path(self.tmp.name) / 'out'

    def tearDown(self):
        self.tmp.cleanup()

    def test_package_has_hash_but_no_bin(self):
        pkg, archive = release.build_release(self.bin, self.out, self.version, root=self.root)
        names = {str(p.relative_to(pkg)) for p in pkg.rglob('*') if p.is_file()}
        self.assertIn('MANIFEST.json', names)
        self.assertIn('BUILDING.md', names)
        self.assertFalse([n for n in names if n.lower().endswith(('.bin', '.cue'))])
        self.assertIn(release.sha256(self.bin), (pkg / 'VERIFY.txt').read_text())
        self.assertTrue(archive.exists())

    def test_planted_private_file_stops_the_build(self):
        target = self.root / 'assets' / 'private' / 'THIRD-PARTY.md'
        target.parent.mkdir(parents=True)
        shutil.move(self.root / 'THIRD-PARTY.md', target)
        (self.root / 'THIRD-PARTY.md').symlink_to(target)
        with self.assertRaises(ForbiddenFile):
            release.build_release(self.bin, self.out, self.version, root=self.root)
        self.assertFalse(list(self.out.glob('*.zip')))

    def test_version_mismatch_refused(self):
        with self.assertRaises(SystemExit):
            release.build_release(self.bin, self.out, 'V9.999', root=self.root)


class ReadIp(unittest.TestCase):
    def test_read_ip_from_raw_and_cooked_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = pathlib.Path(tmp) / 'a.bin'
            raw.write_bytes(raw_sector(fake_ip()))
            iso = pathlib.Path(tmp) / 'a.iso'
            iso.write_bytes(fake_ip() + bytes(1792))
            self.assertEqual(release.read_ip(raw), fake_ip())
            self.assertEqual(release.read_ip(iso), fake_ip())


class LocalSaroo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = pathlib.Path(self.tmp.name)
        self.bin = base / 'sonic-cd-saturn-prototype.bin'
        self.bin.write_bytes(raw_sector(fake_ip()))
        (base / 'sonic-cd-saturn-prototype.cue').write_text('FILE "sonic-cd-saturn-prototype.bin" BINARY\n')
        self.dest = base / 'card-copy'
        self.gate = release.bundle_warning()
        self.saved = os.environ.pop(self.gate['ENV_VAR'], None)

    def tearDown(self):
        os.environ.pop(self.gate['ENV_VAR'], None)
        if self.saved is not None:
            os.environ[self.gate['ENV_VAR']] = self.saved
        self.tmp.cleanup()

    def test_gate_uses_bundle_warning(self):
        self.assertIn('LOCAL-ONLY', self.gate['WARNING'])
        self.assertEqual(self.gate['FLAG'], '--local-only-i-will-not-share')

    def test_refuses_without_confirmation(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            release.local_saroo(self.dest, self.bin, version='V0.078')
        self.assertFalse(self.dest.exists())

    def test_writes_saroo_layout(self):
        os.environ[self.gate['ENV_VAR']] = self.gate['ENV_VALUE']
        with contextlib.redirect_stderr(io.StringIO()):
            release.local_saroo(self.dest, self.bin, version='V0.078')
        game = self.dest / 'SAROO' / 'ISO' / 'Sonic CD Saturn V0.078'
        self.assertTrue((game / self.bin.name).exists())
        self.assertTrue((game / 'sonic-cd-saturn-prototype.cue').exists())
        self.assertFalse((self.dest / 'SAROO' / 'cover.bin').exists())
        self.assertTrue((self.dest / 'SAROO' / 'READ-ME-LOCAL-ONLY.txt').exists())


if __name__ == '__main__':
    unittest.main()
