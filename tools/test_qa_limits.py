"""Harmless QA policy checks. No game, compiler, or emulator may start."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import qa_limits as policy

ROOT = Path(__file__).resolve().parents[1]


class EnvLimits(unittest.TestCase):
    def test_unset_keeps_requested_defaults(self):
        self.assertEqual(policy.worker_limit(4, environ={}), 4)
        self.assertEqual(policy.emulator_limit(2, environ={}), 2)

    def test_caps_never_increase_requested_workers(self):
        env = {"SCD_QA_MAX_WORKERS": "2", "SCD_QA_MAX_EMULATORS": "1"}
        self.assertEqual(policy.worker_limit(4, environ=env), 2)
        self.assertEqual(policy.worker_limit(1, environ=env), 1)
        self.assertEqual(policy.emulator_limit(2, environ=env), 1)
        self.assertEqual(policy.emulator_limit(1, environ=env), 1)
        self.assertEqual(policy.emulator_limit(2, environ={"SCD_QA_MAX_WORKERS": "1"}), 2)

    def test_invalid_caps_fail_before_execution(self):
        for name, function in (("SCD_QA_MAX_WORKERS", policy.worker_limit),
                               ("SCD_QA_MAX_EMULATORS", policy.emulator_limit)):
            for value in ("", "0", "-1", "1.5", "nan", "inf", "two"):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    function(4, environ={name: value})
        for requested in (0, -1, True, 2.0):
            with self.subTest(requested=requested), self.assertRaises(ValueError):
                policy.worker_limit(requested, environ={})


class Cooldowns(unittest.TestCase):
    def test_default_and_invalid_cooldown(self):
        self.assertEqual(policy.cooldown_seconds(environ={}), 0)
        self.assertEqual(policy.cooldown_seconds(
            environ={"SCD_QA_COOLDOWN_SECONDS": "60"}), 60)
        for value in ("", "-1", "nan", "inf"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                policy.cooldown_seconds(environ={"SCD_QA_COOLDOWN_SECONDS": value})

    def test_waits_from_previous_completion(self):
        now, sleeps = [100.0], []
        def sleep(seconds):
            sleeps.append(seconds)
            now[0] += seconds
        waited = policy.cooldown(95, 60, clock=lambda: now[0], sleep=sleep)
        self.assertEqual(waited, 55)
        self.assertEqual(now[0], 155)
        self.assertTrue(all(0 < seconds <= 1 for seconds in sleeps))
        with patch.object(policy.time, "sleep", side_effect=AssertionError("unneeded sleep")):
            self.assertEqual(policy.cooldown(None, 60), 0)
            self.assertEqual(policy.cooldown(95, 60, clock=lambda: 155), 0)

    def test_interruption_propagates(self):
        def interrupt(_):
            raise KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            policy.cooldown(100, 60, clock=lambda: 100, sleep=interrupt)


class Metadata(unittest.TestCase):
    def setUp(self):
        base = ROOT / "build"
        self.temporary = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)

    def test_atomic_replacement_and_no_temp_residue(self):
        path = self.folder / "run.json"
        policy.atomic_json(path, {"status": "pending", "passed": False})
        policy.atomic_json(path, {"status": "failed", "passed": False, "reason": "interrupted"})
        self.assertEqual(json.loads(path.read_text())["status"], "failed")
        self.assertEqual(list(self.folder.iterdir()), [path])

    def test_missing_parent_is_not_created(self):
        path = self.folder / "missing" / "run.json"
        with self.assertRaises(FileNotFoundError):
            policy.atomic_json(path, {"status": "pending"})
        self.assertFalse(path.parent.exists())

    def test_interrupted_commit_cannot_replace_pending_with_pass(self):
        path = self.folder / "run.json"
        policy.atomic_json(path, {"status": "pending", "passed": False})
        with patch.object(policy.os, "replace", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                policy.atomic_json(path, {"status": "passed", "passed": True})
        self.assertEqual(json.loads(path.read_text()), {"status": "pending", "passed": False})
        self.assertEqual(list(self.folder.iterdir()), [path])

    def test_failed_sync_propagates_and_keeps_pending(self):
        path = self.folder / "run.json"
        policy.atomic_json(path, {"status": "pending", "passed": False})
        with patch.object(policy, "_sync_file", side_effect=OSError("injected sync failure")):
            with self.assertRaisesRegex(OSError, "injected sync failure"):
                policy.atomic_json(path, {"status": "passed", "passed": True})
        self.assertFalse(json.loads(path.read_text())["passed"])
        self.assertEqual(list(self.folder.iterdir()), [path])

    def test_invalid_payload_does_not_replace_previous_report(self):
        path = self.folder / "run.json"
        policy.atomic_json(path, {"status": "pending"})
        with self.assertRaises(ValueError):
            policy.atomic_json(path, {"seconds": float("nan")})
        self.assertEqual(json.loads(path.read_text()), {"status": "pending"})
        self.assertEqual(list(self.folder.iterdir()), [path])



class AtomicCleanup(unittest.TestCase):
    def primary_cleanup_failure(self, primary):
        for stage in ("sync", "replace"):
            with self.subTest(stage=stage):
                stream = MagicMock()
                stream.fileno.return_value = 42
                opened = MagicMock()
                opened.__enter__.return_value = stream
                with patch.object(policy.tempfile, "mkstemp", return_value=(42, "unopened.tmp")), \
                        patch.object(policy.os, "fdopen", return_value=opened), \
                        patch.object(policy, "_sync_file", side_effect=primary if stage == "sync" else None), \
                        patch.object(policy.os, "replace", side_effect=primary if stage == "replace" else None), \
                        patch.object(policy.os, "unlink", side_effect=OSError(6, "Device not configured")):
                    try:
                        policy.atomic_json("/not-opened/run.json", {"passed": False})
                    except BaseException as caught:
                        self.assertIs(caught, primary)
                    else:
                        self.fail("primary exception was swallowed")

    def test_cleanup_preserves_keyboard_interrupt_identity(self):
        self.primary_cleanup_failure(KeyboardInterrupt("primary interrupt"))

    def test_cleanup_preserves_primary_oserror_identity(self):
        self.primary_cleanup_failure(OSError(5, "primary I/O failure"))

    def test_successful_publication_never_unlinks_old_temporary_path(self):
        stream = MagicMock()
        stream.fileno.return_value = 42
        opened = MagicMock()
        opened.__enter__.return_value = stream
        with patch.object(policy.tempfile, "mkstemp", return_value=(42, "unopened.tmp")), \
                patch.object(policy.os, "fdopen", return_value=opened), \
                patch.object(policy, "_sync_file"), \
                patch.object(policy.os, "replace") as replace, \
                patch.object(policy.os, "open", return_value=84), \
                patch.object(policy.os, "fsync"), \
                patch.object(policy.os, "close"), \
                patch.object(policy.os, "unlink", side_effect=OSError(6, "Device not configured")) as unlink:
            policy.atomic_json("/not-opened/run.json", {"passed": False})
            replace.assert_called_once()
            unlink.assert_not_called()

class ProbeStop(Exception):
    pass


class DispatchCaps(unittest.TestCase):
    def test_fuzz_pool_uses_effective_cap_without_starting_host(self):
        import cdpp_fuzz as fuzz
        base = ROOT / "build"
        with tempfile.TemporaryDirectory(dir=base) as folder, \
                patch.object(fuzz, "OUT", Path(folder)), \
                patch.dict(os.environ, {"SCD_QA_MAX_WORKERS": "2"}), \
                patch("concurrent.futures.ThreadPoolExecutor", side_effect=ProbeStop) as pool, \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(ProbeStop):
                fuzz.main(["--windows", "ppz1A", "--runs", "1", "--length", "10"])
            pool.assert_called_once_with(max_workers=2)
            reports = list(Path(folder).glob("*/report.json"))
            self.assertEqual(len(reports), 1)
            report = json.loads(reports[0].read_text())
            self.assertEqual(report["jobs"], 2)
            self.assertFalse(report["passed"])

    def test_art_pool_respects_emulator_cap_without_starting_route(self):
        import test_art_misses as art
        with patch.object(sys, "argv", ["test_art_misses.py", "--zones", "ppz", "--jobs", "2"]), \
                patch.dict(os.environ, {"SCD_QA_MAX_WORKERS": "2", "SCD_QA_MAX_EMULATORS": "1"}), \
                patch.object(art, "symbols", return_value=("0", "0")), \
                patch.object(art, "ThreadPoolExecutor", side_effect=ProbeStop) as pool:
            with self.assertRaises(ProbeStop):
                art.main()
            pool.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()
