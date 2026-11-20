#!/usr/bin/env python3
"""OS-watch checks: mocks plus one harmless blocked-parent fixture."""
import contextlib
import datetime as dt
import errno
import io
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
OWNERSHIP_SOURCE = Path(os.environ.get("SCD_QA_WATCH_SOURCE", str(ROOT)))
sys.path.insert(0, str(OWNERSHIP_SOURCE / "tools"))
try:
    import power_guard
finally:
    sys.path.pop(0)
import qa_os_watch as watch

watch.MOUNT = "/Volumes/Untitled"  # fixture name; the real mount comes from the checkout path


class WatchTests(unittest.TestCase):
    def tree(self, root=1001, children=()):
        tree = Mock(spec=power_guard._OwnedTree)
        tree.root = root
        tree.owned = {pid: (pid, 1) for pid in (root, *children)}
        tree.refresh.return_value = set(tree.owned)
        tree.verified.return_value = True
        tree.survivors.return_value = []
        return tree

    def future(self):
        return dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=10)

    @contextlib.contextmanager
    def monitor(self, tree, health):
        with patch.object(watch, "_OwnedTree", return_value=tree), \
                patch.object(watch, "os_health", side_effect=health), \
                patch.object(watch, "emit") as emit, \
                patch.object(watch.os, "chdir"), \
                patch.dict(os.environ, dict(os.environ)), \
                patch.object(watch.os, "kill") as kill:
            yield emit, kill

    def test_health_uses_absolute_os_commands_only(self):
        responses = [Mock(stdout="/dev/mock on /Volumes/Untitled (apfs, local)\n"),
                     Mock(stdout="Now drawing from 'AC Power'\n")]
        with patch.object(watch.subprocess, "run", side_effect=responses) as run:
            self.assertEqual(watch.os_health(), (True, None))
        self.assertEqual([call.args[0] for call in run.call_args_list],
                         [["/sbin/mount"], ["/usr/bin/pmset", "-g", "batt"]])
        self.assertTrue(all(call.kwargs["cwd"] == "/" and call.kwargs["timeout"] == 3
                            for call in run.call_args_list))
        with patch.object(watch.subprocess, "run", return_value=Mock(
                stdout="/dev/mock on /Volumes/Untitled 2 (apfs)\n")) as run:
            self.assertEqual(watch.os_health(), (False, "mount_missing"))
            self.assertEqual(run.call_count, 1)
        with patch.object(watch.subprocess, "run", side_effect=subprocess.TimeoutExpired("mount", 3)):
            self.assertEqual(watch.os_health(), (False, "mount_unknown"))

    def test_battery_requires_explicit_allowance(self):
        responses = [Mock(stdout="/dev/mock on /Volumes/Untitled (apfs, local)\n"),
                     Mock(stdout="Now drawing from 'Battery Power'\n")]
        with patch.object(watch.subprocess, "run", side_effect=responses):
            self.assertEqual(watch.os_health(), (False, "battery"))
        with patch.object(watch.subprocess, "run", side_effect=responses):
            self.assertEqual(watch.os_health(allow_battery=True), (True, None))

    def test_normal_exit_and_no_filesystem_probe_hooks(self):
        tree = self.tree()
        forbidden = AssertionError("filesystem or primary guard was consulted")
        with self.monitor(tree, [(True, None)]) as (emit, kill), \
                patch.object(Path, "stat", side_effect=forbidden), \
                patch.object(Path, "read_text", side_effect=forbidden), \
                patch.object(Path, "read_bytes", side_effect=forbidden), \
                patch.object(shutil, "disk_usage", side_effect=forbidden), \
                patch.object(power_guard, "run", side_effect=forbidden), \
                patch.object(power_guard, "inputs", side_effect=forbidden):
            result = watch.watch([tree.root], self.future(), settle=0)
        self.assertEqual(result["status"], "exited")
        self.assertEqual(emit.call_args.args[0]["event"], "armed")
        self.assertEqual(emit.call_args.args[0]["identities"],
                         [dict(pid=1001, birth=[1001, 1])])
        kill.assert_not_called()
        tree.freeze.assert_not_called()

    def test_mount_loss_stops_verified_tree_without_waiting_for_freeze(self):
        tree = self.tree(children=(1002,))
        tree.survivors.side_effect = [[1001, 1002], []]
        with self.monitor(tree, [(True, None), (False, "mount_missing")]) as (_, kill):
            result = watch.watch([tree.root], self.future(), settle=0)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["reason"], "mount_missing")
        self.assertEqual({call.args[0] for call in kill.call_args_list}, {1001, 1002})
        self.assertTrue(any(call.args[1] == signal.SIGKILL for call in kill.call_args_list))
        tree.freeze.assert_not_called()
        tree.signal.assert_not_called()

    def test_u_parent_reports_pending_after_child_kill_attempt(self):
        tree = self.tree(children=(1002,))
        tree.survivors.return_value = [1001]
        with patch.object(watch.os, "kill") as kill:
            result = watch.stop_owned([tree], "mount_missing", settle=0)
        self.assertEqual(result["status"], "pending_termination")
        self.assertEqual(result["survivors"], [1001])
        self.assertIn(((1002, signal.SIGKILL),), [(call.args,) for call in kill.call_args_list])
        tree.freeze.assert_not_called()

    def test_uncertain_root_does_not_prevent_verified_child_kill(self):
        tree = self.tree(children=(1002,))
        tree.refresh.side_effect = RuntimeError("root identity unavailable")
        tree.survivors.side_effect = RuntimeError("root identity unavailable")
        def verified(pid):
            if pid == 1001:
                raise RuntimeError("root identity unavailable")
            return True
        tree.verified.side_effect = verified
        with patch.object(watch.os, "kill") as kill:
            result = watch.stop_owned([tree], "control_error", settle=0)
        self.assertEqual(result["status"], "pending_termination")
        self.assertEqual(result["uncertain_roots"], [1001])
        self.assertTrue(any(call.args == (1002, signal.SIGKILL) for call in kill.call_args_list))
        self.assertFalse(any(call.args[0] == 1001 for call in kill.call_args_list))

    def test_recycled_or_unrelated_pids_are_not_signalled(self):
        tree = self.tree(children=(1002,))
        tree.verified.side_effect = lambda pid: pid != 1002
        with patch.object(watch.os, "kill") as kill:
            result = watch.stop_owned([tree], "deadline", settle=0)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual({call.args[0] for call in kill.call_args_list}, {1001})

    def test_orphaned_verified_descendant_is_killed(self):
        tree = self.tree(children=(1002,))
        tree.survivors.side_effect = [[1002], []]
        with self.monitor(tree, [(True, None)]) as (_, kill):
            result = watch.watch([1001], self.future(), settle=0)
        self.assertEqual(result["reason"], "orphaned_descendants")
        self.assertEqual(result["status"], "stopped")
        self.assertTrue(any(call.args == (1002, signal.SIGKILL) for call in kill.call_args_list))

    def test_unknown_ac_deadline_and_interrupt_stop_before_arming(self):
        for reason in ("power_unknown", "deadline", "interrupt"):
            with self.subTest(reason=reason):
                tree = self.tree()
                health = [(False, "power_unknown")] if reason == "power_unknown" else []
                deadline = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)
                            if reason == "deadline" else self.future())
                requested = [signal.SIGTERM] if reason == "interrupt" else None
                with self.monitor(tree, health) as (emit, kill):
                    result = watch.watch([1001], deadline, settle=0, requested=requested)
                self.assertEqual(result["reason"], reason)
                emit.assert_not_called()
                self.assertTrue(any(call.args[1] == signal.SIGKILL for call in kill.call_args_list))

    def test_cli_repeated_roots_status_and_signal_handlers(self):
        deadline = self.future().isoformat()
        for status, expected in (("exited", 0), ("stopped", 1), ("pending_termination", 2)):
            with self.subTest(status=status), \
                    patch.object(watch, "watch", return_value={"status": status}) as monitor, \
                    patch.object(watch, "emit") as emit, \
                    patch.object(watch.signal, "signal", return_value=signal.SIG_DFL) as handlers:
                code = watch.main(["--pid", "1001", "--pid", "1002", "--deadline", deadline])
                self.assertEqual(code, expected)
                self.assertEqual(monitor.call_args.args[0], [1001, 1002])
                self.assertIsNotNone(monitor.call_args.args[1].tzinfo)
                self.assertEqual(handlers.call_count, 4)
                emit.assert_called_once_with({"status": status})

    @unittest.skipUnless(sys.platform == "darwin", "Darwin kernel birth/OS fixture")
    def test_real_blocked_parent_detached_child_and_unrelated_sentinel(self):
        parent = sentinel = None
        child = birth = None
        script = ("import subprocess,sys\n"
                  "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],"
                  "start_new_session=True,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,"
                  "stderr=subprocess.DEVNULL)\n"
                  "print(child.pid,flush=True)\n"
                  "sys.stdin.buffer.read(1)\n")
        with tempfile.TemporaryDirectory(dir=ROOT / "build", prefix="qa-os-watch-") as temporary:
            environment = dict(os.environ, TMPDIR=temporary)
            try:
                parent = subprocess.Popen([sys.executable, "-u", "-c", script], cwd="/",
                                          env=environment, stdin=subprocess.PIPE,
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                import select
                self.assertTrue(select.select([parent.stdout], [], [], 5)[0], "fixture did not start")
                child = int(parent.stdout.readline())
                birth = power_guard._birth(child)
                parent_birth = power_guard._birth(parent.pid)
                self.assertIsNotNone(birth)
                self.assertIsNotNone(parent_birth)
                sentinel = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(30)"],
                                            cwd="/", env=environment, stdin=subprocess.DEVNULL,
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                real_kill = os.kill
                with patch.object(watch, "os_health", return_value=(True, None)), \
                        patch.object(watch, "emit") as armed, \
                        patch.dict(os.environ, dict(os.environ)), \
                        patch.object(watch.os, "kill", wraps=real_kill) as kill, \
                        patch.object(watch.os, "killpg", side_effect=AssertionError("broad group kill")):
                    result = watch.watch([parent.pid],
                                         dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=0.7),
                                         poll=0.05, settle=2)
                self.assertEqual(armed.call_args.args[0]["identities"],
                                 [dict(pid=parent.pid, birth=list(parent_birth))])
                self.assertEqual(result["status"], "stopped", result)
                self.assertEqual(result["reason"], "deadline")
                parent.wait(timeout=3)
                self.assertIsNone(sentinel.poll(), "unrelated sentinel was killed")
                self.assertTrue(all(call.args[0] in (parent.pid, child)
                                    for call in kill.call_args_list))
                row = power_guard._processes().get(child)
                self.assertTrue(row is None or row[2].startswith("Z"),
                                "detached child remains active")
            finally:
                if parent is not None:
                    if parent.poll() is None:
                        parent.kill()
                    parent.wait(timeout=3)
                    for stream in (parent.stdin, parent.stdout, parent.stderr):
                        if stream:
                            stream.close()
                if child is not None and power_guard._birth(child) == birth:
                    try:
                        os.kill(child, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                if sentinel is not None:
                    if sentinel.poll() is None:
                        sentinel.terminate()
                    sentinel.wait(timeout=3)

    @unittest.skipUnless(sys.platform == 'darwin','Darwin retirement ownership model')
    def test_reused_numeric_root_is_owned_child_but_not_original_root_lifetime(self):
        # Root42/A exits; retained43/B survives; PID42/C is then its new child.
        records={42:dict(birth=(100,1),ppid=1,pgid=42),
                 43:dict(birth=(200,2),ppid=42,pgid=43)}
        table={42:(1,42,'?'),43:(42,43,'?')}
        events=[];signals=[];constructed=[];armed=[]
        real_tree=power_guard._OwnedTree
        def query(pid):
            row=records.get(pid)
            events.append(('query',pid,row['birth'] if row else None))
            if row is None:
                return None,dict(kind='gone_candidate',size=0,errno=errno.ESRCH,
                                 reported_pid=0,observed_at=time.monotonic())
            return dict(row),dict(kind='readable',size=136,errno=0,reported_pid=pid,
                                  observed_at=time.monotonic())
        def make_tree(pid):
            tree=real_tree(pid);constructed.append(tree);return tree
        def emit(event):
            armed.append(event)
            records[43]['ppid']=1;records[42]=dict(birth=(300,3),ppid=43,pgid=42)
            table.update({43:(1,43,'?'),42:(43,42,'?')})
        def kill(pid,number):
            self.assertIn(pid,records,'signal attempted on absent/unverified PID')
            birth=records[pid]['birth']
            self.assertEqual(events[-1],('query',pid,birth),'signal lacked immediate birth check')
            self.assertIn((pid,birth),((42,(300,3)),(43,(200,2))))
            signals.append((pid,number,birth))
            if number==signal.SIGSTOP:
                parent,pgid,_=table[pid];table[pid]=(parent,pgid,'T')
            elif number==signal.SIGKILL:
                records.pop(pid);table.pop(pid)
        def health():
            return (True,None) if not armed else (False,'old_numeric_root_policy_boundary')
        forbidden=AssertionError('OS watcher consulted filesystem or spawned a child')
        with patch.object(power_guard,'_process_info',new=lambda pid:query(pid)[0]), \
             patch.object(power_guard,'_darwin_process_query',new=query), \
             patch.object(power_guard,'_processes',new=lambda:dict(table)), \
             patch.object(watch,'_OwnedTree',side_effect=make_tree), \
             patch.object(watch,'emit',side_effect=emit), \
             patch.object(watch,'os_health',side_effect=health), \
             patch.object(watch.os,'kill',side_effect=kill), \
             patch.object(watch.os,'chdir'),patch.dict(os.environ,dict(os.environ)), \
             patch.object(subprocess,'run',side_effect=forbidden), \
             patch.object(subprocess,'Popen',side_effect=forbidden), \
             patch.object(Path,'stat',side_effect=forbidden), \
             patch.object(Path,'read_text',side_effect=forbidden), \
             patch.object(Path,'read_bytes',side_effect=forbidden):
            result=watch.watch([42],self.future(),poll=.001,settle=.01)
        self.assertEqual(result['reason'],'orphaned_descendants')
        self.assertEqual(result['status'],'stopped')
        self.assertEqual(result['survivor_count'],0)
        self.assertEqual(result['uncertain_roots'],[])
        self.assertEqual(result['errors'],[])
        self.assertEqual(armed[0]['identities'],[dict(pid=42,birth=[100,1])])
        killed={(pid,birth) for pid,number,birth in signals if number==signal.SIGKILL}
        self.assertEqual(killed,{(42,(300,3)),(43,(200,2))})
        self.assertEqual(constructed[0].owned,{})
        self.assertEqual(constructed[0].retirement_summary()['counts'],dict(gone=2,reused=1))

    def test_unchanged_original_root_birth_is_not_an_orphan(self):
        tree=self.tree(root=42);tree.owned={42:(100,1)}
        tree.survivors.side_effect=[{42},set()]
        with self.monitor(tree,[(True,None),(True,None)]) as (armed,kill), \
             patch.object(watch.time,'sleep'):
            result=watch.watch([42],self.future(),poll=.001,settle=0)
        self.assertEqual(result['reason'],'all_roots_exited')
        self.assertEqual(result['status'],'exited')
        self.assertEqual(armed.call_args.args[0]['identities'],[dict(pid=42,birth=[100,1])])
        kill.assert_not_called()

    def test_initial_root_birth_is_captured_before_first_refresh(self):
        tree=self.tree(root=42,children=(43,))
        tree.owned={42:(100,1),43:(200,2)}
        refreshes=0
        def refresh():
            nonlocal refreshes
            refreshes+=1
            if refreshes==1:tree.owned[42]=(300,3)
            return set(tree.owned)
        tree.refresh.side_effect=refresh
        tree.survivors.side_effect=[{42,43},set()]
        with self.monitor(tree,[(True,None),(False,'old_numeric_root_policy_boundary')]) as (armed,kill):
            result=watch.watch([42],self.future(),poll=.001,settle=0)
        self.assertEqual(armed.call_args.args[0]['identities'],[dict(pid=42,birth=[100,1])])
        self.assertEqual(result['reason'],'orphaned_descendants')
        self.assertEqual(result['status'],'stopped')
        self.assertEqual(tree.owned[42],(300,3))
        self.assertTrue(any(call.args[0]==42 and call.args[1]==signal.SIGKILL
                            for call in kill.call_args_list))



if __name__ == "__main__":
    unittest.main()
