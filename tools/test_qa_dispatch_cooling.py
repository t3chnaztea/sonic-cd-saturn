#!/usr/bin/env python3
"""Harmless checks of actual QA dispatch code; no native jobs or game files."""
import argparse
import ast
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

import qa_limits
import qa_resume
from test_qa_resume import Recovery as CheckpointRecovery

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get("SCD_QA_DISPATCH_SOURCE", str(ROOT)))


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.interrupt = False

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        if self.interrupt:
            raise KeyboardInterrupt
        self.now += seconds


class PoolProbe(BaseException):
    pass


class DispatchCooling(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / "build", prefix="qa-dispatch-")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.clock = FakeClock()
        self.checkpoints = []

    def checkpoint(self, path, value):
        path = Path(path)
        self.assertTrue(path.is_relative_to(self.folder))
        snapshot = json.loads(json.dumps(value))
        self.checkpoints.append((path, snapshot))
        path.write_text(json.dumps(snapshot) + "\n")

    def pause(self, last_finished, seconds):
        return qa_limits.cooldown(last_finished, seconds,
                                  clock=self.clock.monotonic, sleep=self.clock.sleep)

    def loop_nodes(self):
        tree = ast.parse((SOURCE / "tools/qa-loop.py").read_text())
        matches = [i for i, node in enumerate(tree.body)
                   if isinstance(node, ast.For) and isinstance(node.iter, ast.Call)
                   and isinstance(node.iter.func, ast.Name) and node.iter.func.id == "enumerate"
                   and node.iter.args and isinstance(node.iter.args[0], ast.Name)
                   and node.iter.args[0].id == "selected"]
        self.assertEqual(len(matches), 1)
        index = matches[0]
        previous = tree.body[index - 1]
        self.assertIsInstance(previous, ast.Assign)
        self.assertEqual(previous.targets[0].id, "last_job_finished")
        return [previous, tree.body[index]]

    def loop_namespace(self, interrupt_after_first=False):
        out = self.folder / "loop"
        out.mkdir()
        (self.folder / "build").mkdir()
        calls = []
        def run(command, **kwargs):
            self.assertEqual(kwargs["cwd"], self.folder)
            calls.append((command, self.clock.now))
            kwargs["stdout"].write("PASS: harmless mock command\n")
            self.clock.now += 7
            if interrupt_after_first:
                self.clock.interrupt = True
            return types.SimpleNamespace(returncode=0)
        namespace = dict(ROOT=self.folder, out=out,
                         selected=[["mock-first"], ["mock-second"]], start_step=0,
                         report=dict(status="pending", passed=False, steps=[],
                                     checkpoint_context=dict(protocol=1)),
                         session_limits=dict(cooldown_seconds=60), suite_mode="fast",
                         atomic_json=self.checkpoint, cooldown=self.pause,
                         time=types.SimpleNamespace(monotonic=self.clock.monotonic),
                         subprocess=types.SimpleNamespace(run=run, STDOUT=subprocess.STDOUT),
                         _sync_file=lambda descriptor: None, hashlib=hashlib, json=json,
                         qa_resume=qa_resume)
        return namespace, calls, out

    def execute_loop(self, namespace):
        namespace.setdefault("prefix_cache", {})
        namespace.setdefault("resume_cache", {})
        namespace.setdefault("args", types.SimpleNamespace(mode="fast"))
        namespace.setdefault("migration", None)
        namespace.setdefault("commands", namespace["selected"])
        with contextlib.redirect_stdout(io.StringIO()):
            exec(compile(ast.Module(body=self.loop_nodes(), type_ignores=[]),
                         "<actual qa-loop dispatch>", "exec"), namespace)

    def test_actual_loop_cools_and_checkpoints_each_log_hash(self):
        namespace, calls, out = self.loop_namespace()
        self.execute_loop(namespace)
        self.assertEqual([time for _, time in calls], [60, 127])
        self.assertEqual(len(namespace["report"]["steps"]), 2)
        for index, step in enumerate(namespace["report"]["steps"]):
            self.assertEqual(step["seconds"], 7)
            log = out / f"{index:02d}.log"
            self.assertEqual(step["log_sha256"], hashlib.sha256(log.read_bytes()).hexdigest())
            self.assertTrue(any(len(value["steps"]) == index + 1
                                and value["steps"][-1]["log_sha256"] == step["log_sha256"]
                                for _, value in self.checkpoints))
        self.assertEqual(json.loads((out / "report.json").read_text())["steps"],
                         namespace["report"]["steps"])

    def test_loop_cooling_interrupt_blocks_next_command_and_records_it(self):
        namespace, calls, out = self.loop_namespace(interrupt_after_first=True)
        with self.assertRaises(SystemExit) as stopped:
            self.execute_loop(namespace)
        self.assertEqual(stopped.exception.code, 130)
        self.assertEqual(len(calls), 1)
        report = json.loads((out / "report.json").read_text())
        self.assertEqual(report["status"], "interrupted")
        self.assertEqual(report["interrupted_step"], 1)
        self.assertFalse(report["passed"])
        self.assertEqual(len(report["steps"]), 1)
        self.assertFalse((out / "01.log").exists())

    def test_verified_cached_rows_start_no_process_and_do_not_cool(self):
        namespace, calls, out = self.loop_namespace()
        namespace["report"].update(resume_enabled=True, reused_checks=0, bios_inputs={})
        namespace["resume_cache"] = {0: {"candidate": "first"}, 1: {"candidate": "second"}}
        cooling = []
        namespace["cooldown"] = lambda *a, **k: cooling.append((a, k))
        verified = []
        def consume(root, mode, commands, context, candidate, index, migration):
            self.assertEqual(root, self.folder)
            self.assertEqual(mode, "fast")
            self.assertIs(commands, namespace["commands"])
            self.assertIs(context, namespace["report"]["checkpoint_context"])
            self.assertIs(candidate, namespace["resume_cache"][index])
            self.clock.now += 19
            row = dict(command=commands[index], exit_code=0, input_identity_complete=True,
                       consumer_inputs_observation="verified_before_reuse")
            verified.append(copy.deepcopy(row))
            return row
        with patch.object(qa_resume, "consume_cached_step", side_effect=consume) as consume_call, \
                patch.object(qa_resume, "checkpoint_bios_inputs") as bios:
            self.execute_loop(namespace)
        self.assertEqual(consume_call.call_count, 2)
        self.assertEqual(cooling, [])
        self.assertEqual(bios.call_count, 2)  # Pre-consumer BIOS validation remains for each reused row.
        self.assertEqual(calls, [])
        self.assertEqual(namespace["last_job_finished"], 0)
        self.assertEqual(namespace["report"]["steps"], verified)
        self.assertEqual(namespace["report"]["reused_checks"], 2)
        self.assertEqual(namespace["report"]["active_step"], 1)
        self.assertFalse((out / "00.log").exists())
        self.assertFalse((out / "01.log").exists())

    def test_verified_prefix_continuations_start_no_process_and_do_not_cool(self):
        namespace, calls, out = self.loop_namespace()
        namespace["report"].update(continued_prefix_checks=0, bios_inputs={})
        namespace["prefix_cache"] = {0: {"prefix": "first"}, 1: {"prefix": "second"}}
        cooling = []
        namespace["cooldown"] = lambda *a, **k: cooling.append((a, k))
        def consume(root, mode, commands, report, candidate, index):
            self.assertEqual(root, self.folder)
            self.assertEqual(mode, "fast")
            self.assertIs(commands, namespace["commands"])
            self.assertIs(report, namespace["report"])
            self.assertIs(candidate, namespace["prefix_cache"][index])
            self.clock.now += 19
            return dict(command=commands[index], exit_code=0, input_identity_complete=True,
                        consumer_inputs_observation="verified_before_prefix_continuation")
        with patch.object(qa_resume, "consume_prefix_step", side_effect=consume) as consume_call, \
                patch.object(qa_resume, "checkpoint_bios_inputs") as bios:
            self.execute_loop(namespace)
        self.assertEqual(consume_call.call_count, 2)
        self.assertEqual(cooling, [])
        self.assertEqual(bios.call_count, 2)
        self.assertEqual(calls, [])
        self.assertEqual(namespace["last_job_finished"], 0)
        self.assertEqual(namespace["report"]["continued_prefix_checks"], 2)
        self.assertEqual(namespace["report"]["active_step"], 1)
        self.assertFalse((out / "00.log").exists())

    def test_reused_middle_row_keeps_cooling_based_on_last_actual_finish(self):
        namespace, calls, _ = self.loop_namespace()
        namespace["selected"] = [["mock-first"], ["mock-cached"], ["mock-second"]]
        namespace["commands"] = namespace["selected"]
        namespace["session_limits"]["cooldown_seconds"] = 120
        namespace["report"].update(resume_enabled=True, reused_checks=0)
        namespace["resume_cache"] = {1: {"candidate": "middle"}}
        cooling = []
        def pause(last_finished, seconds):
            cooling.append((last_finished, seconds))
            return self.pause(last_finished, seconds)
        namespace["cooldown"] = pause
        def consume(*args):
            self.clock.now += 19
            return dict(command=["mock-cached"], exit_code=0, input_identity_complete=True)
        with patch.object(qa_resume, "consume_cached_step", side_effect=consume):
            self.execute_loop(namespace)
        self.assertEqual([start for _, start in calls], [120, 247])
        self.assertEqual(cooling, [(0, 120), (127, 120)])
        self.assertEqual(namespace["last_job_finished"], 254)
        self.assertEqual(namespace["report"]["reused_checks"], 1)

    def test_invalid_cache_falls_back_to_execution_with_actual_finish_cooling(self):
        namespace, calls, _ = self.loop_namespace()
        namespace["session_limits"]["cooldown_seconds"] = 120
        namespace["report"].update(resume_enabled=True, reused_checks=0)
        namespace["resume_cache"] = {1: {"candidate": "invalid"}}
        cooling = []
        def pause(last_finished, seconds):
            cooling.append((last_finished, seconds))
            return self.pause(last_finished, seconds)
        namespace["cooldown"] = pause
        def invalid(*args):
            self.clock.now += 19
            return None
        with patch.object(qa_resume, "consume_cached_step", side_effect=invalid) as consume:
            self.execute_loop(namespace)
        self.assertEqual(consume.call_count, 1)
        self.assertEqual([command for command, _ in calls], [["mock-first"], ["mock-second"]])
        self.assertEqual([start for _, start in calls], [120, 247])
        self.assertEqual(cooling, [(0, 120), (127, 120)])
        self.assertEqual(namespace["report"]["reused_checks"], 0)

    def test_invalid_prefix_stops_before_cooling_or_execution(self):
        namespace, calls, _ = self.loop_namespace()
        namespace["report"]["continued_prefix_checks"] = 0
        namespace["prefix_cache"] = {0: {"prefix": "changed"}}
        cooling = []
        namespace["cooldown"] = lambda *a, **k: cooling.append((a, k))
        with patch.object(qa_resume, "consume_prefix_step", side_effect=ValueError("Changed prefix")):
            with self.assertRaisesRegex(ValueError, "Changed prefix"):
                self.execute_loop(namespace)
        self.assertEqual(cooling, [])
        self.assertEqual(calls, [])
        self.assertEqual(namespace["report"]["status"], "failed")
        self.assertEqual(namespace["report"]["continued_prefix_checks"], 0)

    def test_actual_loop_session_defaults_and_configured_limits(self):
        tree = ast.parse((SOURCE / "tools/qa-loop.py").read_text())
        nodes = [node for node in tree.body if isinstance(node, ast.Try)
                 and any(isinstance(child, ast.Assign)
                         and any(isinstance(target, ast.Name) and target.id == "session_limits"
                                 for target in child.targets) for child in node.body)]
        self.assertEqual(len(nodes), 1)
        for env, expected in (({}, dict(host_workers=4, emulators=2, cooldown_seconds=0)),
                              (dict(SCD_QA_MAX_WORKERS="2", SCD_QA_MAX_EMULATORS="1",
                                    SCD_QA_COOLDOWN_SECONDS="60"),
                               dict(host_workers=2, emulators=1, cooldown_seconds=60))):
            namespace = dict(worker_limit=qa_limits.worker_limit,
                             emulator_limit=qa_limits.emulator_limit,
                             cooldown_seconds=qa_limits.cooldown_seconds,
                             p=argparse.ArgumentParser())
            with patch.dict(os.environ, env, clear=True):
                exec(compile(ast.Module(body=nodes, type_ignores=[]),
                             "<actual qa-loop limits>", "exec"), namespace)
            self.assertEqual(namespace["session_limits"], expected)

    def matrix(self):
        module = types.ModuleType("qa_dispatch_matrix_under_test")
        module.__file__ = str(SOURCE / "tools/zone-gates.py")
        tree = ast.parse(Path(module.__file__).read_text())
        nodes = [node for node in tree.body
                 if isinstance(node, (ast.Import, ast.ImportFrom, ast.Assign,
                                      ast.FunctionDef, ast.ClassDef))]
        # Excludes main invocation and process niceness code. Only definitions load.
        exec(compile(ast.Module(body=nodes, type_ignores=[]),
                     "<actual zone-gates definitions>", "exec"), module.__dict__)
        module.ROOT = self.folder
        module.time = types.SimpleNamespace(time=self.clock.monotonic,
                                            monotonic=self.clock.monotonic)
        module.cooldown = self.pause
        module.atomic_json = self.checkpoint
        module._sync_file = lambda descriptor: None
        return module

    def matrix_run(self, module, callback):
        module.subprocess = types.SimpleNamespace(run=callback, STDOUT=subprocess.STDOUT,
                                                 TimeoutExpired=subprocess.TimeoutExpired)
        return module.Run(("mock-matrix",), [["mock-one"], ["mock-two"]], "mock-group")

    def test_matrix_cools_each_actual_command(self):
        module = self.matrix()
        calls = []
        def run(command, **kwargs):
            calls.append((command, self.clock.now))
            kwargs["stdout"].write("PASS: mock matrix\n")
            self.clock.now += 3
            return types.SimpleNamespace(returncode=0)
        job = self.matrix_run(module, run)
        cooling = dict(last_finished=0, seconds=60)
        with contextlib.redirect_stdout(io.StringIO()):
            module.execute(job, self.folder, 5, threading.Lock(), cooling)
        self.assertEqual([time for _, time in calls], [60, 123])
        self.assertEqual(cooling["last_finished"], 126)
        self.assertEqual(job.result["returncode"], 0)
        self.assertTrue(job.done.is_set())

    def test_matrix_timeout_records_124_and_prevents_later_command(self):
        module = self.matrix()
        calls = []
        def run(command, **kwargs):
            calls.append(command)
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        job = self.matrix_run(module, run)
        with contextlib.redirect_stdout(io.StringIO()):
            module.execute(job, self.folder, 5, threading.Lock(),
                           dict(last_finished=0, seconds=60))
        self.assertEqual(calls, [["mock-one"]])
        self.assertEqual(job.result["returncode"], 124)
        self.assertIn("timeout after 5s", (self.folder / job.result["log"]).read_text())

    def test_matrix_cooling_interrupt_prevents_later_command(self):
        module = self.matrix()
        calls = []
        def run(command, **kwargs):
            calls.append(command)
            self.clock.now += 3
            self.clock.interrupt = True
            return types.SimpleNamespace(returncode=0)
        job = self.matrix_run(module, run)
        with self.assertRaises(KeyboardInterrupt):
            module.execute(job, self.folder, 5, threading.Lock(),
                           dict(last_finished=0, seconds=60))
        self.assertEqual(calls, [["mock-one"]])
        self.assertIsNone(job.result)
        self.assertFalse(job.done.is_set())

    def test_matrix_main_limits_and_global_cooling_serialize_before_pool(self):
        import power_guard
        def fixture_context(root, inputs, bin_path=None):
            return dict(protocol=1, runtime={}, toolchain={}, source_sha256=inputs,
                        limits={}, bin_sha256=qa_resume.digest(bin_path) if bin_path else None)
        settings = [({}, 4),
                    (dict(SCD_QA_MAX_WORKERS="2", SCD_QA_MAX_EMULATORS="1"), 1),
                    (dict(SCD_QA_MAX_WORKERS="2", SCD_QA_MAX_EMULATORS="3"), 2),
                    (dict(SCD_QA_MAX_WORKERS="2", SCD_QA_MAX_EMULATORS="2",
                          SCD_QA_COOLDOWN_SECONDS="60"), 1)]
        for number, (env, expected) in enumerate(settings):
            with self.subTest(environment=env):
                module = self.matrix()
                location = self.folder / f"main-{number}"
                location.mkdir()
                (location / "build").mkdir()
                (location / "dist").mkdir()
                # Patch BIN before main: only this tiny fixture may be hashed.
                fixture = location / "dist/mock.bin"
                fixture.write_bytes(b"small fixture")
                module.ROOT, module.BIN = location, fixture
                module.release_zones = lambda root: ("ppz",)
                module.release_special = lambda root: False
                module.matrix_command = lambda zones, special: [
                    "python3", "tools/zone-gates.py", "--zones", "ppz", "--gates", "retail"]
                module.git = lambda *args: ""
                job = module.Run(("never-executed",), [["never-native"]], "mock")
                window = module.Window("ppz", "retail", "MOCK", job, module.parse_generic)
                module.build_matrix = lambda *args: ({job.key: job}, [window])
                def lead(command, **kwargs):
                    self.assertEqual(command[1:], ["tools/route_unlock_lead.py", "--check"])
                    return types.SimpleNamespace(returncode=0, stdout="", stderr="")
                module.subprocess = types.SimpleNamespace(run=lead)
                capacities = []
                def pool(*args, **kwargs):
                    capacities.append(kwargs.get("max_workers", args[0] if args else None))
                    raise PoolProbe
                module.cf = types.SimpleNamespace(ThreadPoolExecutor=pool)
                with patch.dict(os.environ, env, clear=True), \
                        patch.object(sys, "argv", ["zone-gates.py"]), \
                        patch.object(power_guard, "inputs", return_value={}), \
                        patch.object(qa_resume, "context", side_effect=fixture_context), \
                        contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(PoolProbe):
                        module.main()
                self.assertEqual(capacities, [expected])
                self.assertIsNone(job.result)


if __name__ == "__main__":
    unittest.main()
