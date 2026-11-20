"""Small synthetic packaging fixtures. No Saturn executable or game assets."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import package_reuse as reuse
import package as package

ROOT = Path(__file__).resolve().parents[1]
CORE = Path(os.environ.get("SCD_PACKAGE_TEST_CORE", ROOT / ".deps/beetle-saturn")).resolve()
LEGACY_C = "/* Host-only disc packaging helper. Links the pinned Beetle/cdrdao LEC encoder.\n * The encoder is GPL-2.0-or-later; this helper uses the same license.\n * It is not linked into the Saturn executable. */\n#include <stdio.h>\n#include <stdint.h>\n#include \"lec.h\"\n\nint main(int argc, char **argv) {\n    if (argc != 3) { fprintf(stderr, \"Usage: iso_to_raw INPUT.iso OUTPUT.bin\\n\"); return 1; }\n    FILE *in = fopen(argv[1], \"rb\");\n    if (!in) { perror(\"input\"); return 1; }\n    FILE *out = fopen(argv[2], \"wb\");\n    if (!out) { perror(\"output\"); fclose(in); return 1; }\n    uint8_t sector[2352] = {0};\n    uint32_t address = 150;\n    size_t count;\n    lec_tables_init();\n    while ((count = fread(sector + 16, 1, 2048, in)) != 0) {\n        if (count != 2048) { fprintf(stderr, \"Partial ISO sector\\n\"); return 1; }\n        lec_encode_mode1_sector(address++, sector);\n        if (fwrite(sector, 1, sizeof(sector), out) != sizeof(sector)) { perror(\"write\"); return 1; }\n    }\n    if (ferror(in)) { perror(\"read\"); return 1; }\n    fclose(in);\n    if (fclose(out)) { perror(\"close\"); return 1; }\n    return 0;\n}\n"
LEGACY_PACKAGE = "#!/usr/bin/env python3\n\"\"\"Produce raw BIN/CUE and verify every data sector against the built ISO.\"\"\"\nimport hashlib\nimport json\nimport pathlib\nimport subprocess\n\nROOT=pathlib.Path(__file__).resolve().parents[1]\nNAME='sonic-cd-saturn-prototype'\ndist=ROOT/'dist'\niso=dist/'iso'/f'{NAME}.iso'\ncue=dist/f'{NAME}.cue'\nbinary=dist/f'{NAME}.bin'\nlog=ROOT/'build/package.log'\naudio=json.loads((ROOT/'build/feedback-source.json').read_text())\nif len(audio['tracks'])!=41 or audio.get('music_source',{}).get('region')!='Japan' or any(\n        not t.get('soundtrack','').startswith('Japan') for t in audio['tracks']):\n    raise SystemExit('Japanese music is required: run tools/prepare_japanese_music.py before packaging')\nwith log.open('w') as out:\n    core=ROOT/'.deps/beetle-saturn'\n    encoder=ROOT/'build/iso_to_raw'\n    subprocess.run(['clang','-O2','-Wall','-Wextra',\n                    '-I'+str(core/'libretro-common/include'),\n                    '-I'+str(core/'mednafen/cdrom'),\n                    str(ROOT/'tools/iso_to_raw.c'),str(core/'mednafen/cdrom/lec.c'),\n                    '-o',str(encoder)],stdout=out,stderr=out,check=True)\n    subprocess.run([str(encoder),str(iso),str(binary)],stdout=out,stderr=out,check=True)\ntext=f'FILE \"{binary.name}\" BINARY\\n  TRACK 01 MODE1/2352\\n    INDEX 01 00:00:00\\n'\n\nif 'MODE1/2352' not in text:\n    raise SystemExit('Expected raw Mode 1 sectors')\noriginal=iso.read_bytes();raw=binary.read_bytes()\nif len(raw)%2352 or len(original)%2048:\n    raise SystemExit('Unaligned disc image')\nif len(raw)//2352 != len(original)//2048:\n    raise SystemExit('Disc sector count differs from ISO')\nfor sector in range(len(original)//2048):\n    offset=sector*2352\n    if raw[offset:offset+12] != b'\\x00'+b'\\xff'*10+b'\\x00' or raw[offset+15]!=1:\n        raise SystemExit(f'Bad Mode 1 sector header at {sector}')\n    if raw[offset+16:offset+16+2048] != original[sector*2048:(sector+1)*2048]:\n        raise SystemExit(f'Sector mismatch at {sector}')\nif raw[16:32] != b'SEGA SEGASATURN ':\n    # Header is exactly 16 bytes; report the observed value on mismatch.\n    raise SystemExit(f'Bad Saturn boot signature: {raw[16:32]!r}')\n# One BIN includes every track, so SAROO does not depend on external WAV paths.\ntracks=audio['tracks']\ndef msf(sector):return f'{sector//4500:02d}:{sector//75%60:02d}:{sector%75:02d}'\nsector=len(raw)//2352\nwith binary.open('ab') as output:\n    for i,track in enumerate(tracks):\n        text+=f'  TRACK {i+2:02d} AUDIO\\n'\n        if i==0:\n            text+=f'    INDEX 00 {msf(sector)}\\n'\n            output.write(bytes(150*2352));sector+=150\n        text+=f'    INDEX 01 {msf(sector)}\\n'\n        music=ROOT/f'assets/generated/music{i}.raw'\n        data=music.read_bytes()\n        assert len(data)==track['sectors']*2352\n        assert hashlib.sha256(data).hexdigest()==track['sha256']\n        track['bin_sector']=sector;output.write(data);sector+=track['sectors']\ncue.write_text(text)\nwith binary.open('rb') as image:\n    for track in tracks:\n        image.seek(track['bin_sector']*2352)\n        assert hashlib.sha256(image.read(track['sectors']*2352)).hexdigest()==track['sha256']\nelf=ROOT/'build/saturn'/f'{NAME}.elf'\nsize=subprocess.check_output([str(ROOT/'.toolchain/bin/sh-elf-size'),str(elf)],text=True)\nsymbols=subprocess.check_output([str(ROOT/'.toolchain/bin/sh-elf-nm'),'-n',str(elf)],text=True)\nends=[int(line.split()[0],16) for line in symbols.splitlines() if line.split()[-1]=='___end']\nassert len(ends)==1 and 0x06004000<=ends[0]<0x06100000\nmemory={'linked_end':f'0x{ends[0]:08X}','user_heap_capacity_bytes':0x06100000-ends[0],\n        'note':'Capacity before runtime user allocations; startup and controller tests exercise the allocated command list.'}\nreport={'memory':memory,'format':'MODE1/2352' ,'verified_data_sectors':len(original)//2048,\n        'music_source':audio['music_source'],\n        'size_report':size,'hardware_tested':False,'audio_tracks':tracks,\n        'stage_packs':json.loads((ROOT/'build/stage-packs.json').read_text()),\n        'files':{p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in (iso,cue,binary)}}\n(dist/'build-report.json').write_text(json.dumps(report,indent=2)+'\\n')\nprint(f'Verified {report[\"verified_data_sectors\"]} sectors; BIN/CUE ready in dist/.')\n"


class Packaging(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        mount = os.environ.get("SCD_QA_MOUNT") or ("/".join(str(ROOT).split("/")[:3]) if str(ROOT).startswith("/Volumes/") else "")
        if not mount or not os.path.ismount(mount):
            raise RuntimeError("Synthetic tests require the configured QA volume")
        cls.temporary = tempfile.TemporaryDirectory(prefix="package-reuse-", dir=ROOT / "build")
        cls.base = Path(cls.temporary.name)
        cls.encoder = cls.base / "encoder"
        cls.compiler = subprocess.check_output(["clang", "--version"], text=True)
        if hashlib.sha256(LEGACY_C.encode()).hexdigest() != "fd02c34d87929a894b124237f410eec5e886bcd4c25f969c1ce9d2dafc285def":
            raise AssertionError("legacy encoder snapshot changed")
        if hashlib.sha256(LEGACY_PACKAGE.encode()).hexdigest() != "d7a4d5be1cf4e19ef568686accb1e22c74c591295ec178a27858d349cbbcf143":
            raise AssertionError("legacy package snapshot changed")
        (cls.base / "legacy.c").write_text(LEGACY_C)
        (cls.base / "driver.c").write_text(
            '#define main current_main\n#include ' + json.dumps(str(ROOT / "tools/iso_to_raw.c")) +
            '\n#undef main\n#define main legacy_main\n#include ' +
            json.dumps(str(cls.base / "legacy.c")) +
            '\n#undef main\nint main(int argc,char **argv){'
            'if(argc>1 && !strcmp(argv[1],"--legacy"))return legacy_main(argc-1,argv+1);'
            'return current_main(argc,argv);}\n')
        core = CORE
        if not (core / "mednafen/cdrom/lec.c").is_file():
            raise RuntimeError("Set SCD_PACKAGE_TEST_CORE to the existing pinned Beetle source")
        command = ["nice", "-n", "20", "clang", "-O2", "-Wall", "-Wextra",
                   "-I" + str(core / "libretro-common/include"),
                   "-I" + str(core / "mednafen/cdrom"),
                   str(cls.base / "driver.c"), str(core / "mednafen/cdrom/lec.c"),
                   "-o", str(cls.encoder)]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stderr)
        cls.real_run = staticmethod(subprocess.run)
        cls.real_output = staticmethod(subprocess.check_output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=self.base)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for folder in ["build/saturn", "dist/iso", "assets/generated", "tools", ".deps"]:
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        (self.root / ".deps/beetle-saturn").symlink_to(CORE,
                                                       target_is_directory=True)
        (self.root / "tools/iso_to_raw.c").symlink_to(ROOT / "tools/iso_to_raw.c")
        self.iso = self.root / "dist/iso" / (package.NAME + ".iso")
        self.binary = self.root / "dist" / (package.NAME + ".bin")
        self.cue = self.root / "dist" / (package.NAME + ".cue")
        self.report = self.root / "dist/build-report.json"
        self.iso.write_bytes(b"SEGA SEGASATURN " + bytes(range(256)) * 15 + bytes(240))
        self.assertEqual(self.iso.stat().st_size, 4096)
        (self.root / "build/saturn" / (package.NAME + ".elf")).write_bytes(b"synthetic ELF placeholder")
        (self.root / "build/stage-packs.json").write_text("{}")
        tracks = []
        for index in range(41):
            data = bytes([index]) * 2352
            (self.root / f"assets/generated/music{index}.raw").write_bytes(data)
            tracks.append({"sectors": 1, "sha256": hashlib.sha256(data).hexdigest(),
                           "soundtrack": "Japan synthetic fixture"})
        self.feedback = self.root / "build/feedback-source.json"
        self.feedback.write_text(json.dumps({"tracks": tracks, "music_source": {"region": "Japan"}}))
        self.calls = []
        self.fail_encoder = False
        self.run_patch = patch.object(subprocess, "run", side_effect=self.run_command)
        self.output_patch = patch.object(subprocess, "check_output", side_effect=self.output_command)
        self.run_patch.start()
        self.output_patch.start()
        self.addCleanup(self.run_patch.stop)
        self.addCleanup(self.output_patch.stop)

    def run_command(self, command, **kwargs):
        command = list(map(str, command))
        self.calls.append(command)
        if command[:1] == ["clang"] and "-o" in command:
            target = Path(command[-1])
            if not target.exists():
                os.link(self.encoder, target)
            return subprocess.CompletedProcess(command, 0)
        if command[0] == str(self.root / "build/iso_to_raw"):
            if self.fail_encoder and len(command) == 3:
                Path(command[2]).write_bytes(b"partial staged image")
                raise subprocess.CalledProcessError(1, command)
            return self.real_run(command, **kwargs)
        raise AssertionError("Unexpected subprocess in package fixture: " + repr(command))

    def output_command(self, command, **kwargs):
        if Path(str(command[0])).name == "sh-elf-size":
            return "text data bss dec hex filename\n1 2 3 6 6 synthetic\n"
        if Path(str(command[0])).name == "sh-elf-nm":
            return "06008000 b ___end\n"
        if command == ["clang", "--version"]:
            return self.compiler
        raise AssertionError("Unexpected metadata subprocess: " + repr(command))

    def execute(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(package.main(self.root), 0)
        self.assertLess(self.binary.stat().st_size, 1024 * 1024)
        return json.loads(self.report.read_text())

    def state(self):
        return {str(path): (reuse.digest(path), path.stat().st_ino, path.stat().st_mtime_ns)
                for path in (self.binary, self.cue, self.report)}

    def encoder_writes(self):
        return [c for c in self.calls if c[0] == str(self.root / "build/iso_to_raw") and len(c) == 3]

    def test_encoder_and_package_preserve_legacy_bytes(self):
        old = self.root / "legacy.bin"
        current = self.root / "current.bin"
        self.real_run([str(self.encoder), "--legacy", str(self.iso), str(old)], check=True)
        self.real_run([str(self.encoder), str(self.iso), str(current)], check=True)
        self.assertEqual(old.read_bytes(), current.read_bytes())
        with contextlib.redirect_stdout(io.StringIO()):
            exec(compile(LEGACY_PACKAGE, "legacy-package.py", "exec"),
                 {"__file__": str(self.root / "tools/package.py"), "__name__": "legacy"})
        expected = self.binary.read_bytes(), self.cue.read_bytes()
        self.binary.unlink()
        self.cue.unlink()
        self.report.unlink()
        report = self.execute()
        self.assertEqual((self.binary.read_bytes(), self.cue.read_bytes()), expected)
        self.assertEqual(report["packaging"]["binary"], "rebuilt")
        self.assertFalse(report["hardware_tested"])

    def test_unchanged_bytes_reuse_despite_source_mtimes(self):
        self.execute()
        before = self.state()
        os.utime(self.iso, (1, 1))
        os.utime(self.root / "assets/generated/music0.raw", (2, 2))
        self.calls.clear()
        report = self.execute()
        after = self.state()
        self.assertEqual(before[str(self.binary)], after[str(self.binary)])
        self.assertEqual(before[str(self.cue)], after[str(self.cue)])
        self.assertEqual(self.encoder_writes(), [])
        self.assertEqual(report["packaging"]["binary"], "verified_reused")

    def test_cue_only_repair_never_rewrites_matching_bin(self):
        self.execute()
        before = self.state()[str(self.binary)]
        expected = self.cue.read_bytes()
        self.cue.write_bytes(b"broken cue")
        self.calls.clear()
        report = self.execute()
        self.assertEqual(self.state()[str(self.binary)], before)
        self.assertEqual(self.cue.read_bytes(), expected)
        self.assertEqual(self.encoder_writes(), [])
        self.assertEqual(report["packaging"]["cue"], "repaired")

    def test_changed_input_with_preserved_mtime_is_rebuilt(self):
        self.execute()
        before, timestamp = reuse.digest(self.binary), self.iso.stat().st_mtime_ns
        data = bytearray(self.iso.read_bytes())
        data[-1] ^= 1
        self.iso.write_bytes(data)
        os.utime(self.iso, ns=(timestamp, timestamp))
        report = self.execute()
        self.assertNotEqual(reuse.digest(self.binary), before)
        self.assertEqual(report["packaging"]["binary"], "rebuilt")

    def test_data_ecc_pregap_audio_and_eof_corruption_are_rejected(self):
        self.execute()
        expected = reuse.digest(self.binary)
        size = self.binary.stat().st_size
        for kind, offset in [("header", 0), ("ECC", 2340), ("pregap", 2 * 2352 + 9),
                             ("audio", (2 + 150) * 2352 + 5), ("short", None), ("tail", None)]:
            with self.subTest(kind=kind):
                with self.binary.open("r+b") as stream:
                    if kind == "short":
                        stream.truncate(size - 1)
                    elif kind == "tail":
                        stream.seek(0, 2)
                        stream.write(b"x")
                    else:
                        stream.seek(offset)
                        byte = stream.read(1)
                        stream.seek(offset)
                        stream.write(bytes([byte[0] ^ 1]))
                report = self.execute()
                self.assertEqual(reuse.digest(self.binary), expected)
                self.assertEqual(report["packaging"]["binary"], "rebuilt")

    def test_invalid_audio_or_encoder_failure_preserves_previous_package(self):
        self.execute()
        before = self.state()
        music = self.root / "assets/generated/music0.raw"
        data = music.read_bytes()
        music.write_bytes(data[:-1])
        with self.assertRaises(ValueError):
            self.execute()
        self.assertEqual(self.state(), before)
        music.write_bytes(data)
        changed = bytearray(self.iso.read_bytes())
        changed[-1] ^= 1
        self.iso.write_bytes(changed)
        self.fail_encoder = True
        with self.assertRaises(subprocess.CalledProcessError):
            self.execute()
        self.assertEqual(self.state(), before)

    def test_publication_io_failure_rolls_back_all_previous_files(self):
        self.execute()
        old = {p: p.read_bytes() for p in (self.binary, self.cue, self.report)}
        staged = [(p, reuse.stage_bytes(p, b"replacement")) for p in old]
        real_replace = os.replace
        failed_source = staged[1][1]
        def replace(source, target):
            if Path(source) == failed_source:
                raise OSError(5, "injected publication failure")
            return real_replace(source, target)
        with patch.object(reuse.os, "replace", side_effect=replace):
            with self.assertRaises(OSError):
                reuse.publish_package(staged)
        self.assertEqual({p: p.read_bytes() for p in old}, old)
        self.assertFalse(list(self.binary.parent.glob(".package-rollback-*")))


class ISOReuse(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="iso-reuse-", dir=ROOT / "build")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)

    def test_identical_iso_reuse_leaves_make_target_current(self):
        make = shutil.which("gmake")
        self.assertIsNotNone(make, "GNU Make is a required build tool")
        source, output = self.folder / "asset.bin", self.folder / "image.iso"
        source.write_bytes(b"synthetic staged asset")
        output.write_bytes(source.read_bytes())
        os.utime(output, (1, 1))
        os.utime(source, (2, 2))
        before = reuse.digest(output), output.stat().st_ino
        producer = self.folder / "producer"
        producer.write_text(
            "#!" + sys.executable + "\nimport pathlib,sys\n"
            "target=sys.argv[sys.argv.index('-o')+1]\n"
            "data=pathlib.Path(sys.argv[-1]).read_bytes()\n"
            "if target=='-':sys.stdout.buffer.write(data)\n"
            "else:pathlib.Path(target).write_bytes(data)\n")
        producer.chmod(0o755)
        recipe = shlex.join([sys.executable, str(ROOT / "tools/package_reuse.py"),
                             "iso", str(producer), "-o", "image.iso", "asset.bin"])
        (self.folder / "Makefile").write_text("image.iso: asset.bin\n\t" + recipe + "\n")
        def run(*arguments):
            return subprocess.run([make, *arguments, "image.iso"], cwd=self.folder,
                                  capture_output=True, text=True)
        self.assertEqual(run("-q").returncode, 1)
        built = run()
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        self.assertEqual((reuse.digest(output), output.stat().st_ino), before)
        current = run("-q")
        self.assertEqual(current.returncode, 0, "verified ISO is still stale: " +
                         current.stdout + current.stderr)
        self.assertGreaterEqual(output.stat().st_mtime_ns, source.stat().st_mtime_ns)
        source.write_bytes(b"changed synthetic staged asset")
        os.utime(output, (1, 1))
        os.utime(source, (2, 2))
        self.assertEqual(run("-q").returncode, 1)
        built = run()
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        self.assertEqual(output.read_bytes(), source.read_bytes())
        self.assertEqual(run("-q").returncode, 0)

    def test_identical_iso_failure_preserves_previous_image_and_timestamp(self):
        output, producer = self.folder / "image.iso", self.folder / "producer"
        for failure in ("producer", "utime", "sync"):
            with self.subTest(failure=failure):
                output.write_bytes(b"previous image")
                os.utime(output, (1, 1))
                before = output.read_bytes(), output.stat().st_ino, output.stat().st_mtime_ns
                producer.write_text(
                    "#!" + sys.executable + "\nimport sys\n"
                    "sys.stdout.buffer.write(b'previous image')\n" +
                    ("sys.exit(7)\n" if failure == "producer" else ""))
                producer.chmod(0o755)
                if failure == "producer":
                    with self.assertRaises(subprocess.CalledProcessError):
                        reuse.reuse_iso(str(producer), ["-o", str(output)])
                else:
                    owner, name = (reuse.os, "utime") if failure == "utime" else (reuse, "sync_file")
                    original, failed = getattr(owner, name), False
                    def fail_once(*args, **kwargs):
                        nonlocal failed
                        if not failed:
                            failed = True
                            raise OSError(5, "injected reused ISO " + failure + " failure")
                        return original(*args, **kwargs)
                    with patch.object(owner, name, side_effect=fail_once):
                        with self.assertRaisesRegex(OSError, "reused ISO " + failure):
                            reuse.reuse_iso(str(producer), ["-o", str(output)])
                    self.assertTrue(failed)
                self.assertEqual((output.read_bytes(), output.stat().st_ino,
                                  output.stat().st_mtime_ns), before)

    def test_full_producer_drain_preserves_late_failure_and_read_error(self):
        output = self.folder / "image.iso"
        output.write_bytes(b"previous image")
        marker = self.folder / "finished"
        code = ("import pathlib,sys;sys.stdout.buffer.write(b'x'*524305);"
                "sys.stdout.buffer.flush();pathlib.Path(sys.argv[1]).write_text('finished');"
                "sys.exit(3)")
        with output.open("rb") as existing, self.assertRaises(subprocess.CalledProcessError):
            reuse._iso_stream([sys.executable, "-c", code, str(marker)], existing)
        self.assertTrue(marker.exists())
        self.assertEqual(output.read_bytes(), b"previous image")
        marker.unlink()
        class FailingRead:
            def read(self, _):
                raise OSError(5, "injected existing ISO read failure")
        code = code.rsplit("sys.exit(3)", 1)[0] + "sys.exit(0)"
        with self.assertRaisesRegex(OSError, "existing ISO read"):
            reuse._iso_stream([sys.executable, "-c", code, str(marker)], FailingRead())
        self.assertTrue(marker.exists())

    def test_changed_iso_rebuild_failure_preserves_previous_image(self):
        output = self.folder / "image.iso"
        producer = self.folder / "producer"
        for bad_status in (1, 0):
            with self.subTest(file_exit=bad_status):
                output.write_bytes(b"previous image")
                before = output.read_bytes(), output.stat().st_ino, output.stat().st_mtime_ns
                producer.write_text(
                    "#!" + sys.executable + "\nimport pathlib,sys\n"
                    "target=sys.argv[sys.argv.index('-o')+1]\n"
                    "if target=='-':sys.stdout.buffer.write(b'expected new image')\n"
                    "else:\n pathlib.Path(target).write_bytes(b'partial or inconsistent image')\n"
                    f" sys.exit({bad_status})\n")
                producer.chmod(0o755)
                failure = subprocess.CalledProcessError if bad_status else ValueError
                with self.assertRaises(failure):
                    reuse.reuse_iso(str(producer), ["-o", str(output)])
                self.assertEqual((output.read_bytes(), output.stat().st_ino,
                                  output.stat().st_mtime_ns), before)
                self.assertFalse(list(self.folder.glob(".image.iso.*.tmp")))

    def test_iso_post_replace_sync_failure_restores_previous_image(self):
        output = self.folder / "image.iso"
        output.write_bytes(b"previous image")
        before = output.read_bytes(), output.stat().st_ino, output.stat().st_mtime_ns
        producer = self.folder / "producer"
        producer.write_text(
            "#!" + sys.executable + "\nimport pathlib,sys\n"
            "target=sys.argv[sys.argv.index('-o')+1]\n"
            "if target=='-':sys.stdout.buffer.write(b'new image')\n"
            "else:pathlib.Path(target).write_bytes(b'new image')\n")
        producer.chmod(0o755)
        original_sync, failed = reuse.sync_parent, False
        def fail_after_replace(path):
            nonlocal failed
            if Path(path) == output and not failed:
                failed = True
                raise OSError(5, "injected post-replace sync failure")
            return original_sync(path)
        with patch.object(reuse, "sync_parent", side_effect=fail_after_replace):
            with self.assertRaisesRegex(OSError, "post-replace sync failure"):
                reuse.reuse_iso(str(producer), ["-o", str(output)])
        self.assertTrue(failed)
        self.assertEqual((output.read_bytes(), output.stat().st_ino,
                          output.stat().st_mtime_ns), before)
        self.assertFalse(list(self.folder.glob(".package-rollback-*")))

    def test_missing_output_parent_cannot_launch_or_recreate_it(self):
        output = self.folder / "missing/image.iso"
        with patch.object(reuse.subprocess, "Popen", side_effect=AssertionError("unexpected producer")):
            with self.assertRaises(FileNotFoundError):
                reuse.reuse_iso("not-called", ["-o", str(output)])
        self.assertFalse(output.parent.exists())

    def test_real_xorrisofs_legacy_stdout_identity_and_unchanged_reuse(self):
        real = shutil.which("xorrisofs")
        self.assertIsNotNone(real, "xorrisofs is a required build tool")
        tree = self.folder / "cd"
        tree.mkdir()
        for name in ("ABS.TXT", "BIB.TXT", "CPY.TXT"):
            (tree / name).write_text("synthetic fixture\n")
        (tree / "A.BIN").write_bytes(b"synthetic program")
        ip = self.folder / "IP.BIN"
        ip.write_bytes(b"SEGA SEGASATURN " + bytes(32752))
        iso = self.folder / "image.iso"
        legacy = self.folder / "legacy.iso"
        epoch, stamp = "1700000000", "2023111422132000"
        args = ["--norock", "-sysid", "SEGA SEGASATURN", "-volid", "", "-volset", "",
                "-publisher", "SEGA ENTERPRISES, LTD.", "-preparer", "SEGA ENTERPRISES, LTD.",
                "-appid", "SEGA ENTERPRISES, LTD.", "-iso-level", "1",
                "-input-charset", "iso8859-1", "-no-bak", "-m", ".*",
                "-abstract", "ABS.TXT", "-biblio", "BIB.TXT", "-copyright", "CPY.TXT",
                "-generic-boot", str(ip), "-verbose", "-o", str(legacy), str(tree)]
        fixed = ["--modification-date=" + stamp, "--set_all_file_dates", "=" + epoch]
        result = subprocess.run([real, *fixed, *args], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr[-1000:])
        args[args.index("-o") + 1] = str(iso)
        env = dict(os.environ, SCD_XORRISOFS=real, SOURCE_DATE_EPOCH=epoch)
        wrapper = ["sh", str(ROOT / "tools/xorrisofs-reproducible.sh"), *args]
        result = subprocess.run(wrapper, env=env, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr[-1000:])
        self.assertEqual(legacy.read_bytes(), iso.read_bytes())
        before = reuse.digest(iso), iso.stat().st_ino
        os.utime(iso, (1, 1))
        os.utime(tree / "A.BIN", (2, 2))
        result = subprocess.run(wrapper, env=env, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr[-1000:])
        self.assertEqual((reuse.digest(iso), iso.stat().st_ino), before)
        self.assertGreaterEqual(iso.stat().st_mtime_ns, (tree / "A.BIN").stat().st_mtime_ns)
        (tree / "A.BIN").write_bytes(b"changed synthetic program")
        result = subprocess.run(wrapper, env=env, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr[-1000:])
        self.assertNotEqual(reuse.digest(iso), before[0])
        self.assertLess(iso.stat().st_size, 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
