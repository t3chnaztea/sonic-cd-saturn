#!/usr/bin/env python3
"""Exercise power/deadline transitions with harmless local worker processes."""
import datetime as dt
import contextlib
import json
import os
import signal
import subprocess
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from power_guard import run, _OwnedTree
import power_guard


class Guard(unittest.TestCase):
    def test_metadata_failure_stops_owned_worker(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);output=folder/'run';marker=folder/'continued'
            original=power_guard.atomic_json;failed=False
            def write(path,record):
                nonlocal failed
                if record['status']=='running' and not failed:
                    failed=True
                    raise OSError('injected metadata failure')
                return original(path,record)
            command=[sys.executable,'-c',f'import time;time.sleep(.5);open({str(marker)!r},"w").close()']
            with patch.object(power_guard,'atomic_json',side_effect=write):
                with self.assertRaisesRegex(OSError,'injected metadata failure'):
                    run(command,output,dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=5),
                        power=lambda:True,poll=.01,capture_inputs=False)
            record=json.loads((output/'run.json').read_text())
            self.assertEqual(record['status'],'interrupted')
            self.assertFalse(record['passed'])
            self.assertEqual(record.get('cleanup_survivors'),[])
            self.assertFalse(marker.exists())

    def check_missing_output_parent(self, vanish_at_mkdir):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);parent=folder/'parent';parent.mkdir()
            output=parent/'result';marker=folder/'launched'
            real_mkdir=Path.mkdir;removed=False
            def mkdir(path,*args,**kwargs):
                nonlocal removed
                if path==output and not removed:
                    parent.rmdir();removed=True
                return real_mkdir(path,*args,**kwargs)
            if not vanish_at_mkdir:parent.rmdir()
            error=None
            with patch('power_guard.subprocess.Popen',wraps=subprocess.Popen) as launch:
                context=patch.object(Path,'mkdir',mkdir) if vanish_at_mkdir else patch.object(Path,'mkdir',real_mkdir)
                with context:
                    try:
                        run([sys.executable,'-c',f'open({str(marker)!r},"w").close()'],output,
                            dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=1),
                            power=lambda:True,poll=.01,capture_inputs=False)
                    except FileNotFoundError as exception:error=exception
                launch.assert_not_called()
            self.assertIsInstance(error,FileNotFoundError)
            self.assertFalse(parent.exists(),'missing output ancestor was recreated')
            self.assertFalse(marker.exists(),'a worker launched without a valid output parent')

    def test_missing_output_parent_never_recreates_ancestors(self):
        self.check_missing_output_parent(False)

    def test_output_parent_vanishing_at_mkdir_never_recreates_ancestors(self):
        self.check_missing_output_parent(True)

    def test_runtime_identity_loss_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);marker=folder/'continued';real_birth=power_guard._birth
            queries=0
            def lose_identity(pid):
                nonlocal queries
                queries+=1
                return real_birth(pid) if queries<=2 else None
            code=f'import time;time.sleep(.3);open({str(marker)!r},"w").close()'
            with patch('power_guard._birth',side_effect=lose_identity):
                with self.assertRaisesRegex(RuntimeError,'live owned.*identity'):
                    run([sys.executable,'-c',code],folder/'result',
                        dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=2),
                        power=lambda:True,poll=.01,capture_inputs=False)
            time.sleep(.35)
            self.assertFalse(marker.exists())
            record=json.loads((folder/'result/run.json').read_text())
            self.assertEqual(record['status'],'interrupted')
            self.assertFalse(record['passed'])
            self.assertIn('cleanup_error',record)
            self.assertNotIn('suspended_battery',[e['status'] for e in record['events']])
            self.assertEqual(record['cleanup_survivors'],[])
        # The same uncertainty on a known child must not count as quiescence.
        tree=_OwnedTree.__new__(_OwnedTree);tree.root=42
        tree.owned={42:(100,1),43:(100,2)};tree.table={}
        records={42:dict(birth=(100,1),ppid=1,pgid=42),
                 43:dict(failure='unknown',size=0,errno=1)}
        with patch('power_guard._processes',return_value={42:(1,42,'S'),43:(42,43,'S')}), \
             self.identity_observations(records):
            with self.assertRaisesRegex(RuntimeError,'live owned.*identity'):tree.freeze()

    def test_unknown_root_identity_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);marker=folder/'continued'
            code=f'import time;time.sleep(.3);open({str(marker)!r},"w").close()'
            with patch('power_guard._birth',return_value=None):
                with self.assertRaisesRegex(RuntimeError,'root.*identity'):
                    run([sys.executable,'-c',code],folder/'result',
                        dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=2),
                        power=lambda:True,poll=.01,capture_inputs=False)
            time.sleep(.35)
            self.assertFalse(marker.exists())
            record=json.loads((folder/'result/run.json').read_text())
            self.assertEqual(record['status'],'interrupted')
            self.assertFalse(record['passed'])

    def test_recycled_pid_is_not_signalled(self):
        tree=_OwnedTree.__new__(_OwnedTree)
        tree.root=42;tree.owned={42:(100,1)};tree.table={}
        with patch('power_guard._birth',return_value=(101,1)),patch('power_guard.os.kill') as kill:
            tree.signal(signal.SIGKILL)
        kill.assert_not_called()

    def test_known_detached_child_remains_owned_after_reparenting(self):
        current={42:dict(birth=(100,1),ppid=1,pgid=42),
                 43:dict(birth=(100,2),ppid=42,pgid=43),
                 99:dict(birth=(100,3),ppid=1,pgid=43)}
        with self.identity_observations(current):
            tree=_OwnedTree(42)
            with patch('power_guard._processes',return_value={42:(1,42,'S'),43:(42,43,'S')}):
                self.assertEqual(tree.refresh(),{42,43})
            # Unrelated PID99 shares a group number but is never a descendant.
            current[43]['ppid']=1
            current.pop(42)  # The parent has exited, not merely vanished from topology.
            with patch('power_guard._processes',return_value={43:(1,43,'S'),99:(1,43,'S')}):
                self.assertEqual(tree.refresh(),{43})
            with patch('power_guard.os.kill') as kill:
                tree.signal(signal.SIGSTOP)
            self.assertIn(unittest.mock.call(43,signal.SIGSTOP),kill.call_args_list)
            self.assertNotIn(unittest.mock.call(99,signal.SIGSTOP),kill.call_args_list)

    def test_stale_snapshot_cannot_adopt_recycled_unrelated_child(self):
        current={42:dict(birth=(100,1),ppid=1,pgid=42),
                 43:dict(birth=(200,1),ppid=999,pgid=43)}
        with self.identity_observations(current):
            tree=_OwnedTree(42)
            with patch('power_guard._processes',return_value={42:(1,42,'S'),43:(42,43,'S')}):
                self.assertEqual(tree.refresh(),{42})
            self.assertNotIn(43,tree.owned)
            with patch('power_guard.os.kill') as kill:
                tree.signal(signal.SIGKILL)
            self.assertNotIn(unittest.mock.call(43,signal.SIGKILL),kill.call_args_list)

    def test_cleanup_signal_error_still_persists_terminal_record(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            real_signal=_OwnedTree.signal
            def fail_kill(tree,sig):
                if sig==signal.SIGKILL:raise OSError('simulated descendant signal failure')
                return real_signal(tree,sig)
            with patch.object(_OwnedTree,'signal',fail_kill):
                r=run([sys.executable,'-c','import time;time.sleep(10)'],folder/'result',
                      dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=.15),
                      power=lambda:True,poll=.01,capture_inputs=False)
            self.assertFalse(r['passed'])
            durable=json.loads((folder/'result/run.json').read_text())
            self.assertEqual(durable['status'],'interrupted')
            self.assertIn('simulated descendant signal failure',durable['cleanup_error'])
            self.assertIn('finished',durable)

    @staticmethod
    def detached_command(folder, nested=False):
        marker = folder/'ticks'
        child_pid = folder/'child.pid'
        grand_pid = folder/'grandchild.pid'
        worker = ('import os,time\n'
                  f'open({str(grand_pid if nested else child_pid)!r},"w").write(str(os.getpid()))\n'
                  f'f=open({str(marker)!r},"a",buffering=1)\n'
                  'for _ in range(50):\n f.write("x\\n"); time.sleep(.025)')
        if nested:
            worker = ('import os,subprocess,sys\n'
                      f'open({str(child_pid)!r},"w").write(str(os.getpid()))\n'
                      f'p=subprocess.Popen([sys.executable,"-c",{worker!r}],start_new_session=True)\n'
                      'p.wait()')
        supervisor = ('import subprocess,sys\n'
                      f'p=subprocess.Popen([sys.executable,"-c",{worker!r}],start_new_session=True)\n'
                      'p.wait()')
        return [sys.executable, '-c', supervisor]

    def test_detached_child_stops_and_resumes(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);marker=folder/'ticks';observed=[];battery_at=None
            def power():
                nonlocal battery_at
                size=marker.stat().st_size if marker.exists() else 0
                if battery_at is None and size>=4:battery_at=time.monotonic()
                age=time.monotonic()-battery_at if battery_at is not None else -1
                if .20<age<.40:observed.append(size)
                return not 0<=age<.50
            r=run(self.detached_command(folder),folder/'result',
                  dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=5),
                  power=power,poll=.01,capture_inputs=False)
            self.assertTrue(r['passed'])
            self.assertGreater(len(observed),3)
            self.assertEqual(len(set(observed)),1,'detached child worked while supervisor was stopped')
            self.assertEqual(marker.read_text().count('x'),50)
            self.assertIn('suspended_battery',[e['status'] for e in r['events']])

    def test_deadline_cleans_detached_child_and_grandchild(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);marker=folder/'ticks';began=None
            def power():
                nonlocal began
                if began is None and marker.exists():began=time.monotonic()
                return began is None or time.monotonic()-began<.10
            r=run(self.detached_command(folder,nested=True),folder/'result',
                  dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=.55),
                  power=power,poll=.01,capture_inputs=False)
            self.assertEqual(r['status'],'interrupted')
            self.assertTrue((folder/'grandchild.pid').is_file())
            before=marker.stat().st_size;time.sleep(.15)
            self.assertEqual(marker.stat().st_size,before,'detached descendant survived deadline cleanup')
            # Killing a zombie is harmless, but it cannot execute more work.
            for path in (folder/'child.pid',folder/'grandchild.pid'):
                pid=int(path.read_text())
                if sys.platform == 'darwin':
                    state=self.darwin_cleanup_state(pid)
                else:
                    state=subprocess.run(['ps','-p',str(pid),'-o','state='],capture_output=True,text=True).stdout.strip()
                self.assertTrue(not state or state.startswith('Z'),(pid,state))
            durable=json.loads((folder/'result/run.json').read_text())
            self.assertEqual(durable['status'],'interrupted')

    def test_battery_never_launches(self):
        with tempfile.TemporaryDirectory() as temp:
            marker = Path(temp)/'launched'
            r = run([sys.executable, '-c', f'open({str(marker)!r},"w").close()'], Path(temp)/'result',
                    dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=.15),
                    power=lambda: False, poll=.01, capture_inputs=False)
            self.assertEqual(r['status'], 'interrupted')
            self.assertNotIn('pid', r)
            self.assertFalse(marker.exists())

    def test_ac_loss_stops_work_until_ac_returns(self):
        with tempfile.TemporaryDirectory() as temp:
            marker = Path(temp)/'ticks'
            observations = []
            began = time.monotonic()
            def power():
                age = time.monotonic()-began
                if .35 < age < .60:
                    observations.append(marker.stat().st_size if marker.exists() else 0)
                return not .20 < age < .65
            code = f'import time\nf=open({str(marker)!r},"a",buffering=1)\nfor _ in range(35):\n f.write("x\\n"); time.sleep(.025)'
            r = run([sys.executable, '-c', code], Path(temp)/'result',
                    dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=4),
                    power=power, poll=.01, capture_inputs=False)
            self.assertTrue(r['passed'])
            self.assertGreater(len(observations), 5)
            self.assertEqual(len(set(observations)), 1)
            self.assertIn('suspended_battery', [e['status'] for e in r['events']])
            self.assertEqual(marker.read_text().count('x'), 35)

    def test_deadline_kills_a_suspended_worker(self):
        with tempfile.TemporaryDirectory() as temp:
            began = time.monotonic()
            r = run([sys.executable, '-c', 'import time; time.sleep(10)'], Path(temp)/'result',
                    dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=.3),
                    power=lambda: time.monotonic()-began < .15, poll=.01, capture_inputs=False)
            self.assertEqual(r['status'], 'interrupted')
            self.assertIn('suspended_battery', [e['status'] for e in r['events']])

    @staticmethod
    def mocked_bsd_kernel(records):
        """Run the real Darwin adapter against a mutable kernel response."""
        def decode(pid, flavor, argument, pointer, size):
            if pid not in records:
                return 0
            row = records[pid]
            # Ordinary live processes remain readable with argument 0.
            # Only the modeled exiting/reference window requires argument 1.
            if row.get('require_arg1', False) and argument == 0:
                return 0
            info = power_guard.ctypes.cast(
                pointer, power_guard.ctypes.POINTER(power_guard._BSDInfo)).contents
            info.pid = row.get('pid', pid)
            info.ppid = row['ppid']
            info.pgid = row['pgid']
            info.start_sec, info.start_usec = row['birth']
            info.status = row.get('status', 2)
            info.flags = row.get('flags', 0)
            return row.get('size', size)
        query = unittest.mock.Mock(side_effect=decode)
        library = unittest.mock.Mock(proc_pidinfo=query)
        return query, patch.object(power_guard.ctypes, 'CDLL', return_value=library)

    def test_darwin_adapter_requests_referenced_birth_and_decodes_exact_identity(self):
        birth = (2**40 + 123, 654321)
        records = {42:dict(birth=birth,ppid=7,pgid=9)}
        query, library = self.mocked_bsd_kernel(records)
        with patch.object(power_guard.sys,'platform','darwin'), library:
            self.assertEqual(power_guard._process_info(42),
                             dict(birth=birth,ppid=7,pgid=9))
            records[42].update(status=5,flags=16404,require_arg1=True)
            self.assertEqual(power_guard._process_info(42),
                             dict(birth=birth,ppid=7,pgid=9))
            args = query.call_args.args
            self.assertEqual((args[0],args[1],args[2],args[4]),(42,3,1,136))
            records[42]['size'] = 135
            self.assertIsNone(power_guard._process_info(42))
            records[42].update(size=136,pid=99)
            self.assertIsNone(power_guard._process_info(42))

    def test_exiting_and_uninterruptible_known_births_remain_live(self):
        for state in ('E','U'):
            with self.subTest(state=state):
                records = {42:dict(birth=(100,1),ppid=1,pgid=42),
                           43:dict(birth=(100,2),ppid=42,pgid=43),
                           44:dict(birth=(100,3),ppid=42,pgid=44)}
                query, library = self.mocked_bsd_kernel(records)
                table = {42:(1,42,'S'),43:(42,43,'S'),44:(42,44,'S')}
                with patch.object(power_guard.sys,'platform','darwin'), library, \
                     patch('power_guard._processes',return_value=table), \
                     patch('power_guard.os.kill') as kill:
                    tree = _OwnedTree(42)
                    self.assertEqual(tree.refresh(),{42,43,44})
                    self.assertEqual(tree.owned,{42:(100,1),43:(100,2),44:(100,3)})
                    # Identity was established before the kernel exit window.
                    for row in records.values():row['require_arg1'] = True
                    records[44]['status'] = 5
                    table.update({42:(1,42,state),43:(42,43,state),44:(42,44,'Z')})
                    self.assertEqual(set(tree.survivors()),{42,43})
                    with self.assertRaisesRegex(RuntimeError,'did not stop or quiesce'):
                        tree.freeze()
                    self.assertIn(unittest.mock.call(42,signal.SIGSTOP),kill.call_args_list)
                    self.assertIn(unittest.mock.call(43,signal.SIGSTOP),kill.call_args_list)
                    self.assertTrue(all(call.args[2] == 1 for call in query.call_args_list))

    def test_kernel_birth_change_before_signal_never_signals_replacement(self):
        records = {42:dict(birth=(100,1),ppid=1,pgid=42),
                   43:dict(birth=(100,2),ppid=42,pgid=43)}
        query, library = self.mocked_bsd_kernel(records)
        with patch.object(power_guard.sys,'platform','darwin'), library, \
             patch('power_guard._processes',return_value={42:(1,42,'S'),43:(42,43,'U')}), \
             patch('power_guard.os.kill') as kill:
            tree = _OwnedTree(42)
            self.assertEqual(tree.refresh(),{42,43})
            query.reset_mock()
            records[43]['birth'] = (200,2)
            tree.signal(signal.SIGKILL)
            self.assertEqual(kill.call_args_list,[unittest.mock.call(42,signal.SIGKILL)])
            self.assertEqual([call.args[0] for call in query.call_args_list],[43,42])

    def test_persistent_unknown_exiting_or_uninterruptible_birth_never_signals(self):
        for state in ('E','U'):
            with self.subTest(state=state):
                records = {42:dict(birth=(100,1),ppid=1,pgid=42)}
                query, library = self.mocked_bsd_kernel(records)
                with patch.object(power_guard.sys,'platform','darwin'), library, \
                     patch('power_guard._processes',return_value={42:(1,42,state)}), \
                     patch('power_guard.os.kill') as kill:
                    tree = _OwnedTree(42)
                    records.clear()
                    with self.assertRaisesRegex(RuntimeError,'live owned.*identity'):
                        tree.signal(signal.SIGKILL)
                    with self.assertRaisesRegex(RuntimeError,'live owned.*identity'):
                        tree.survivors()
                    kill.assert_not_called()
                    self.assertEqual(len(query.call_args_list),3)

    @staticmethod
    def mocked_native_library(pids, records, list_bytes=None):
        """Model raw libproc returns for the production discovery adapter."""
        def listpids(kind, extra, buffer, size):
            if (kind, extra) != (1, 0):
                raise AssertionError('wrong native PID-list request')
            for index, pid in enumerate(pids):buffer[index] = pid
            return len(pids)*4 if list_bytes is None else list_bytes
        def info(pid, flavor, argument, pointer, size):
            row = records[pid]
            if argument != 1:raise AssertionError('missing zombie/reference lookup')
            power_guard.ctypes.set_errno(row.get('errno',0))
            if flavor == 13:
                if size != 64:raise AssertionError('wrong shortBSD ABI')
                result = power_guard.ctypes.cast(
                    pointer,power_guard.ctypes.POINTER(power_guard._BSDShortInfo)).contents
                result.pid = row.get('short_pid',pid)
                result.ppid = row.get('short_ppid',row.get('ppid',7))
                result.pgid = row.get('pgid',9)
                result.status = row.get('status',2)
                return row.get('short_size',64)
            if flavor != 3 or size != 136:raise AssertionError('wrong identity request')
            if row.get('birth') is None:return 0
            result = power_guard.ctypes.cast(
                pointer,power_guard.ctypes.POINTER(power_guard._BSDInfo)).contents
            result.pid = pid
            result.ppid = row.get('identity_ppid',row.get('ppid',7))
            result.pgid = row.get('pgid',9)
            result.start_sec,result.start_usec = row['birth']
            return 136
        return unittest.mock.Mock(
            proc_listpids=unittest.mock.Mock(side_effect=listpids),
            proc_pidinfo=unittest.mock.Mock(side_effect=info))

    def test_darwin_native_discovery_never_spawns_and_maps_only_T_Z(self):
        states = (0,1,2,3,4,5,999)
        records = {pid:dict(status=state) for pid,state in enumerate(states,42)}
        lib = self.mocked_native_library([0,-1,*records],records)
        with patch.object(power_guard.sys,'platform','darwin'), \
             patch.object(power_guard.ctypes,'CDLL',return_value=lib), \
             patch('power_guard.subprocess.run',side_effect=AssertionError('Darwin discovery spawn boundary')), \
             patch('power_guard.subprocess.Popen',side_effect=AssertionError('Darwin discovery spawn boundary')):
            table = power_guard._processes()
        self.assertEqual(table,{pid:(7,9,'T' if state==4 else 'Z' if state==5 else '?')
                                for pid,state in enumerate(states,42)})
        self.assertEqual(lib.proc_listpids.call_args.args[:2],(1,0))
        self.assertEqual(lib.proc_listpids.call_args.args[3],(32768+1)*4)
        self.assertEqual(len(lib.proc_pidinfo.call_args_list),len(records))
        self.assertTrue(all(call.args[1:3]==(13,1) for call in lib.proc_pidinfo.call_args_list))

    def test_darwin_native_invalid_pid_list_fails_closed(self):
        capacity = (32768+1)*4
        for size in (-1,0,3,capacity+4,capacity):
            with self.subTest(size=size):
                lib = self.mocked_native_library([42],{42:{}},list_bytes=size)
                with patch.object(power_guard.sys,'platform','darwin'), \
                     patch.object(power_guard.ctypes,'CDLL',return_value=lib), \
                     patch('power_guard.subprocess.run',side_effect=AssertionError('unexpected subprocess')):
                    with self.assertRaises(RuntimeError):power_guard._processes()
                lib.proc_pidinfo.assert_not_called()

    def test_darwin_native_short_failure_retains_unknown_without_parent(self):
        for size,pid in ((0,43),(63,43),(64,99)):
            with self.subTest(size=size,pid=pid):
                # Even plausible returned topology cannot be used on a bad query.
                lib = self.mocked_native_library([43],{43:dict(
                    short_size=size,short_pid=pid,ppid=42,pgid=43,errno=1)})
                with patch.object(power_guard.sys,'platform','darwin'), \
                     patch.object(power_guard.ctypes,'CDLL',return_value=lib):
                    self.assertEqual(power_guard._processes(),{43:(None,None,'?')})

    def test_darwin_native_unreadable_owned_pid_remains_live_unsignalled(self):
        lib = self.mocked_native_library([42],{42:dict(
            short_size=0,ppid=1,pgid=42,errno=1,birth=None)})
        tree = _OwnedTree.__new__(_OwnedTree)
        tree.root=42;tree.owned={42:(100,1)};tree.table={}
        with patch.object(power_guard.sys,'platform','darwin'), \
             patch.object(power_guard.ctypes,'CDLL',return_value=lib), \
             patch('power_guard.os.kill') as kill:
            with self.assertRaisesRegex(RuntimeError,'live owned.*identity'):tree.survivors()
            self.assertEqual(tree.table,{42:(None,None,'?')})
            with self.assertRaisesRegex(RuntimeError,'live owned.*identity'):tree.signal(signal.SIGKILL)
            kill.assert_not_called()

    def test_darwin_native_unknown_child_never_infers_parent_or_adopts(self):
        records={42:dict(ppid=1,pgid=42,birth=(100,1)),
                 43:dict(ppid=42,pgid=43,birth=(200,2),short_size=63)}
        lib = self.mocked_native_library([42,43],records)
        with patch.object(power_guard.sys,'platform','darwin'), \
             patch.object(power_guard.ctypes,'CDLL',return_value=lib), \
             patch('power_guard.os.kill') as kill:
            tree = _OwnedTree(42)
            self.assertEqual(tree.refresh(),{42})
            self.assertEqual(tree.table[43],(None,None,'?'))
            self.assertNotIn(43,tree.owned)
            tree.signal(signal.SIGSTOP)
            self.assertEqual(kill.call_args_list,[unittest.mock.call(42,signal.SIGSTOP)])
            self.assertFalse(any(call.args[:2]==(43,3) for call in lib.proc_pidinfo.call_args_list))

    def test_darwin_native_stale_topology_and_reuse_never_signal_unrelated(self):
        records={42:dict(ppid=1,pgid=42,birth=(100,1)),
                 43:dict(short_ppid=42,identity_ppid=999,pgid=43,birth=(200,2))}
        lib = self.mocked_native_library([42,43],records)
        with patch.object(power_guard.sys,'platform','darwin'), \
             patch.object(power_guard.ctypes,'CDLL',return_value=lib), \
             patch('power_guard.os.kill') as kill:
            tree = _OwnedTree(42)
            self.assertEqual(tree.refresh(),{42})
            self.assertNotIn(43,tree.owned,'stale topology adopted unrelated process')
            records[43].update(identity_ppid=42,birth=(100,2))
            self.assertEqual(tree.refresh(),{42,43})
            lib.proc_pidinfo.reset_mock()
            records[43].update(identity_ppid=999,birth=(200,2))
            tree.signal(signal.SIGKILL)
            self.assertEqual(kill.call_args_list,[unittest.mock.call(42,signal.SIGKILL)])
            self.assertEqual([call.args[0] for call in lib.proc_pidinfo.call_args_list],[43,42])

    def test_linux_process_discovery_retains_ps_fallback(self):
        response=subprocess.CompletedProcess([],0,stdout='42 1 42 S\n43 42 43 Z\n')
        with patch.object(power_guard.sys,'platform','linux'), \
             patch.object(power_guard.ctypes,'CDLL',side_effect=AssertionError('Linux used Darwin API')), \
             patch('power_guard.subprocess.run',return_value=response) as run_ps:
            self.assertEqual(power_guard._processes(),{42:(1,42,'S'),43:(42,43,'Z')})
        run_ps.assert_called_once_with(['ps','-axo','pid=,ppid=,pgid=,state='],
                                      capture_output=True,text=True,check=True,timeout=3)

    @staticmethod
    def darwin_cleanup_state(pid):
        """Independent SDK oracle; never use the production discovery adapter."""
        import ctypes
        import errno
        lib = ctypes.CDLL('/usr/lib/libproc.dylib',use_errno=True)
        query = lib.proc_pidinfo
        query.argtypes = [ctypes.c_int,ctypes.c_int,ctypes.c_uint64,ctypes.c_void_p,ctypes.c_int]
        query.restype = ctypes.c_int
        info = ctypes.create_string_buffer(64)
        ctypes.set_errno(0)
        size = query(pid,13,1,ctypes.byref(info),64)
        error = ctypes.get_errno()
        actual_pid = int.from_bytes(info.raw[0:4],sys.byteorder)
        status = int.from_bytes(info.raw[12:16],sys.byteorder)
        if size == 64 and actual_pid == pid:
            return 'Z' if status == 5 else '?'
        if size != 0 or error != errno.ESRCH:
            raise RuntimeError('independent cleanup identity/status unavailable')
        if ctypes.sizeof(ctypes.c_int) != 4:
            raise RuntimeError('unsupported independent PID-list layout')
        pids = (ctypes.c_int*(32768+1))()
        list_pids = lib.proc_listpids
        list_pids.argtypes = [ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_int]
        list_pids.restype = ctypes.c_int
        ctypes.set_errno(0)
        size = list_pids(1,0,pids,ctypes.sizeof(pids))
        if size <= 0 or size >= ctypes.sizeof(pids) or size % 4:
            raise RuntimeError('independent cleanup PID-list incomplete')
        if pid in pids[:size//4]:
            raise RuntimeError('independent cleanup PID still listed without status')
        return ''

    def test_independent_darwin_cleanup_oracle_fails_on_ambiguous_results(self):
        import ctypes
        import errno
        capacity = (32768+1)*4
        cases = [
            (64,42,5,0,[],4,'Z'),(64,42,2,0,[],4,'?'),
            (0,0,0,errno.ESRCH,[],4,''),
            (0,0,0,errno.ESRCH,[42],4,None),
            (0,0,0,errno.EPERM,[],4,None),
            (63,42,5,0,[],4,None),(64,99,5,0,[],4,None),
        ] + [(0,0,0,errno.ESRCH,[],size,None)
             for size in (-1,0,3,capacity,capacity+4)]
        for size,actual_pid,status,error,listed,list_size,expected in cases:
            with self.subTest(size=size,actual_pid=actual_pid,status=status,
                              error=error,list_size=list_size):
                def query(pid,flavor,arg,pointer,buffer_size):
                    self.assertEqual((pid,flavor,arg,buffer_size),(42,13,1,64))
                    data = (ctypes.c_uint32*16)()
                    data[0]=actual_pid;data[3]=status
                    ctypes.memmove(pointer,ctypes.byref(data),64)
                    ctypes.set_errno(error)
                    return size
                def listpids(kind,extra,pointer,buffer_size):
                    self.assertEqual((kind,extra,buffer_size),(1,0,capacity))
                    for i,pid in enumerate(listed):pointer[i]=pid
                    return list_size
                lib = unittest.mock.Mock(proc_pidinfo=unittest.mock.Mock(side_effect=query),
                                         proc_listpids=unittest.mock.Mock(side_effect=listpids))
                with patch.object(ctypes,'CDLL',return_value=lib):
                    if expected is None:
                        with self.assertRaises(RuntimeError):self.darwin_cleanup_state(42)
                    else:self.assertEqual(self.darwin_cleanup_state(42),expected)


    @staticmethod
    @contextlib.contextmanager
    def identity_observations(records):
        """Script the same kernel boundary for old and repaired production methods."""
        def query(pid):
            row = records.get(pid)
            if row is None:
                return None, dict(kind='gone_candidate',size=0,errno=3,
                                  reported_pid=0,observed_at=time.monotonic())
            if row.get('failure'):
                return None, dict(kind=row['failure'],size=row.get('size',0),
                                  errno=row.get('errno',1),reported_pid=row.get('reported_pid',0),
                                  observed_at=time.monotonic())
            info = dict(birth=row['birth'],ppid=row['ppid'],pgid=row['pgid'])
            return info, dict(kind='readable',size=136,errno=0,
                              reported_pid=pid,observed_at=time.monotonic())
        with patch.object(power_guard,'_process_info',new=lambda pid:query(pid)[0]), \
             patch.object(power_guard,'_darwin_process_query',new=query,create=True), \
             patch.object(power_guard.sys,'platform','darwin'):
            yield

    def test_darwin_raw_identity_proof_distinguishes_gone_from_uncertainty(self):
        import errno
        cases=[(136,42,0,'readable'),(0,0,errno.ESRCH,'gone_candidate'),
               (0,0,errno.EPERM,'unknown'),(63,42,errno.ESRCH,'unknown'),
               (136,99,0,'unknown'),(-1,0,errno.ESRCH,'unknown')]
        for size,pid,error,kind in cases:
            with self.subTest(size=size,pid=pid,error=error):
                entry_errno=[]
                def query(requested,flavor,arg,pointer,buffer_size):
                    entry_errno.append(power_guard.ctypes.get_errno())
                    self.assertEqual((requested,flavor,arg,buffer_size),(42,3,1,136))
                    info=power_guard.ctypes.cast(pointer,power_guard.ctypes.POINTER(power_guard._BSDInfo)).contents
                    info.pid=pid;info.ppid=1;info.pgid=42
                    info.start_sec=100;info.start_usec=1
                    power_guard.ctypes.set_errno(error)
                    return size
                lib=unittest.mock.Mock(proc_pidinfo=unittest.mock.Mock(side_effect=query))
                with patch.object(power_guard.sys,'platform','darwin'), \
                     patch.object(power_guard.ctypes,'CDLL',return_value=lib):
                    power_guard.ctypes.set_errno(777)
                    info,proof=power_guard._darwin_process_query(42)
                    self.assertEqual(proof['kind'],kind)
                    self.assertEqual((proof['size'],proof['errno'],proof['reported_pid']),(size,error,pid))
                    legacy=power_guard._process_info(42)
                    self.assertEqual(legacy,info)
                self.assertEqual(entry_errno,[0,0])
                if kind=='readable':self.assertEqual(info,dict(birth=(100,1),ppid=1,pgid=42))
                else:self.assertIsNone(info)

    def test_reaped_health_helper_churn_exceeds_lifetime_bound_safely(self):
        table={42:(1,42,'?')};records={42:dict(birth=(100,1),ppid=1,pgid=42)}
        with self.identity_observations(records), \
             patch('power_guard._processes',side_effect=lambda:dict(table)), \
             patch('power_guard.os.kill') as kill:
            tree=_OwnedTree(42);peak=0
            for index in range(8192):
                pid=10000+index
                table.clear();table.update({42:(1,42,'?'),pid:(42,pid,'?')})
                records.clear();records.update({42:dict(birth=(100,1),ppid=1,pgid=42),
                                               pid:dict(birth=(200,index),ppid=42,pgid=pid)})
                self.assertEqual(tree.refresh(),{42,pid})
                peak=max(peak,len(tree.owned))
            self.assertEqual(peak,2)
            audit=tree.retirement_summary()
            self.assertEqual(audit['counts'],dict(gone=8191,reused=0))
            self.assertEqual(audit['recent_limit'],16)
            self.assertEqual(len(audit['recent']),16)
            self.assertEqual(audit['recent'][-1]['pid'],10000+8190)
            self.assertTrue(all(p['list_absent'] and p['errno']==3 for p in audit['recent']))
            kill.assert_not_called()

    def test_raw_esrch_requires_later_complete_snapshot_absence(self):
        records={42:dict(birth=(100,1),ppid=1,pgid=42),
                 43:dict(birth=(100,2),ppid=42,pgid=43)}
        initial={42:(1,42,'?'),43:(42,43,'?')}
        with self.identity_observations(records),patch('power_guard._processes',return_value=initial):
            tree=_OwnedTree(42);tree.refresh()
        records[43]=dict(failure='gone_candidate',size=0,errno=3)
        snapshots=[dict(initial),{42:(1,42,'?')}]
        with self.identity_observations(records), \
             patch('power_guard._processes',side_effect=lambda:snapshots.pop(0)):
            self.assertEqual(tree.refresh(),{42})
        self.assertNotIn(43,tree.owned)
        proof=tree.retirement_summary()['recent'][-1]
        self.assertEqual(proof['reason'],'gone')
        self.assertTrue(proof['list_absent'])
        self.assertGreaterEqual(proof['list_started'],proof['observed_at'])
        self.assertGreaterEqual(proof['list_finished'],proof['list_started'])
        self.assertEqual(snapshots,[])

    def test_uncertain_identity_is_retained_even_when_topology_omits_pid(self):
        for failure in (dict(size=0,errno=1),dict(size=63,errno=3),
                        dict(size=136,errno=0,reported_pid=99)):
            with self.subTest(failure=failure):
                records={42:dict(birth=(100,1),ppid=1,pgid=42),
                         43:dict(birth=(100,2),ppid=42,pgid=43)}
                table={42:(1,42,'?'),43:(42,43,'?')}
                with self.identity_observations(records), \
                     patch('power_guard._processes',side_effect=lambda:dict(table)), \
                     patch('power_guard.os.kill') as kill:
                    tree=_OwnedTree(42);tree.refresh()
                    records[43]=dict(failure='unknown',**failure);table.pop(43)
                    with self.assertRaisesRegex(RuntimeError,'live owned.*identity'):tree.survivors()
                    self.assertEqual(tree.owned[43],(100,2))
                    self.assertEqual(tree.retirement_summary()['counts'],dict(gone=0,reused=0))
                    kill.assert_not_called()

    def test_raw_esrch_with_still_listed_pid_does_not_retire(self):
        records={42:dict(birth=(100,1),ppid=1,pgid=42),
                 43:dict(birth=(100,2),ppid=42,pgid=43)}
        table={42:(1,42,'?'),43:(42,43,'?')}
        with self.identity_observations(records),patch('power_guard._processes',return_value=table):
            tree=_OwnedTree(42);tree.refresh()
            records[43]=dict(failure='gone_candidate',size=0,errno=3)
            with self.assertRaisesRegex(RuntimeError,'live owned.*identity'):tree.refresh()
            self.assertEqual(tree.owned[43],(100,2))
            self.assertEqual(tree.retirement_summary()['counts']['gone'],0)

    def test_readable_same_birth_missing_topology_remains_live(self):
        records={42:dict(birth=(100,1),ppid=1,pgid=42),
                 43:dict(birth=(100,2),ppid=42,pgid=43)}
        table={42:(1,42,'?'),43:(42,43,'?')}
        with self.identity_observations(records),patch('power_guard._processes',side_effect=lambda:dict(table)):
            tree=_OwnedTree(42);tree.refresh()
            table.pop(43);records[43]['ppid']=1
            self.assertEqual(set(tree.survivors()),{42,43})
            self.assertEqual(tree.table[43],(1,43,'?'))
            self.assertEqual(tree.owned[43],(100,2))

    def test_detached_E_U_unknown_survive_retirement_of_gone_root(self):
        for state in ('E','U','?'):
            with self.subTest(state=state):
                records={42:dict(birth=(100,1),ppid=1,pgid=42),
                         43:dict(birth=(100,2),ppid=42,pgid=43)}
                table={42:(1,42,'?'),43:(42,43,'?')}
                with self.identity_observations(records),patch('power_guard._processes',side_effect=lambda:dict(table)):
                    tree=_OwnedTree(42);tree.refresh()
                    records.pop(42);table.pop(42)
                    records[43]['ppid']=1;table[43]=(1,43,state)
                    self.assertEqual(tree.survivors(),[43])
                    self.assertEqual(tree.owned,{43:(100,2)})

    def test_reused_generation_requires_current_parent_and_cannot_be_signalled(self):
        records={42:dict(birth=(100,1),ppid=1,pgid=42),
                 43:dict(birth=(100,2),ppid=42,pgid=43)}
        table={42:(1,42,'?'),43:(42,43,'?')}
        with self.identity_observations(records),patch('power_guard._processes',side_effect=lambda:dict(table)), \
             patch('power_guard.os.kill') as kill:
            tree=_OwnedTree(42);tree.refresh()
            records[43].update(birth=(200,2),ppid=999)
            self.assertEqual(tree.refresh(),{42})
            self.assertNotIn(43,tree.owned)
            tree.signal(signal.SIGKILL)
            self.assertEqual(kill.call_args_list,[unittest.mock.call(42,signal.SIGKILL)])
            records[43]['ppid']=42
            self.assertEqual(tree.refresh(),{42,43})
            self.assertEqual(tree.owned[43],(200,2))
            self.assertEqual(tree.table[43],(42,43,'?'))
            self.assertEqual(tree.retirement_summary()['counts']['reused'],1)

    def test_new_and_rebound_births_never_inherit_stale_T_or_Z(self):
        for state in ('T','Z'):
            for rebound in (False,True):
                with self.subTest(state=state,rebound=rebound):
                    records={42:dict(birth=(100,1),ppid=1,pgid=42),
                             43:dict(birth=(100,2),ppid=42,pgid=43)}
                    table={42:(1,42,'T'),43:(42,43,'?')}
                    with self.identity_observations(records),patch('power_guard._processes',side_effect=lambda:dict(table)):
                        tree=_OwnedTree(42)
                        if rebound:tree.refresh();records[43]['birth']=(200,2)
                        table[43]=(42,43,state)
                        self.assertEqual(set(tree.survivors()),{42,43})
                        self.assertEqual(tree.table[43],(42,43,'?'))
                        self.assertEqual(tree.owned[43],(200,2) if rebound else (100,2))

    def test_freeze_requires_stable_birth_map_not_only_pid_keys(self):
        tree=_OwnedTree.__new__(_OwnedTree);tree.root=42
        tree.owned={42:(100,1),43:(100,2)};tree.table={}
        calls=0
        def refresh():
            nonlocal calls
            calls+=1
            if calls==2:tree.owned[43]=(200,2)
            tree.table={42:(1,42,'T'),43:(42,43,'T')}
            return {42,43}
        with patch.object(tree,'refresh',side_effect=refresh),patch.object(tree,'signal') as send:
            tree.freeze()
        self.assertEqual(calls,4)
        self.assertEqual(send.call_count,2)

    def test_rebound_existing_key_at_true_capacity_does_not_grow_owned(self):
        records={42:dict(birth=(100,1),ppid=1,pgid=42)}
        table={42:(1,42,'?')}
        for pid in range(10000,10000+4095):
            records[pid]=dict(birth=(200,pid),ppid=1,pgid=pid)
            table[pid]=(1,pid,'?')
        with self.identity_observations(records),patch('power_guard._processes',side_effect=lambda:dict(table)):
            tree=_OwnedTree(42)
            tree.owned.update({pid:row['birth'] for pid,row in records.items()})
            records[10000].update(birth=(300,1),ppid=42);table[10000]=(42,10000,'Z')
            self.assertIn(10000,tree.refresh())
            self.assertEqual(len(tree.owned),4096)
            self.assertEqual(tree.owned[10000],(300,1))
            self.assertEqual(tree.table[10000],(42,10000,'?'))
            self.assertEqual(tree.retirement_summary()['counts']['reused'],1)

    def test_true_concurrent_4097_retained_processes_still_fail_bound(self):
        records={42:dict(birth=(100,1),ppid=1,pgid=42)}
        table={42:(1,42,'?')}
        for pid in range(20000,20000+4096):
            records[pid]=dict(birth=(200,pid),ppid=42,pgid=pid)
            table[pid]=(42,pid,'?')
        with self.identity_observations(records),patch('power_guard._processes',return_value=table), \
             patch('power_guard.os.kill') as kill:
            tree=_OwnedTree(42)
            with self.assertRaisesRegex(RuntimeError,'owned descendant bound exceeded'):tree.refresh()
            self.assertEqual(len(tree.owned),4096)
            kill.assert_not_called()

    def test_zombie_keeps_final_child_capture_until_reaped(self):
        records={42:dict(birth=(100,1),ppid=1,pgid=42),
                 43:dict(birth=(100,2),ppid=42,pgid=43)}
        table={42:(1,42,'?'),43:(42,43,'?')}
        with self.identity_observations(records),patch('power_guard._processes',side_effect=lambda:dict(table)):
            tree=_OwnedTree(42);tree.refresh()
            table[43]=(42,43,'Z');table[44]=(43,44,'?')
            records[44]=dict(birth=(100,3),ppid=43,pgid=44)
            self.assertEqual(set(tree.survivors()),{42,44})
            self.assertIn(43,tree.owned)
            records.pop(43);table.pop(43);records[44]['ppid']=1;table[44]=(1,44,'?')
            self.assertEqual(set(tree.survivors()),{42,44})
            self.assertNotIn(43,tree.owned)
            self.assertEqual(tree.owned[44],(100,3))

    def test_legacy_tree_audit_and_signal_verification_never_retire_mid_traversal(self):
        tree=_OwnedTree.__new__(_OwnedTree);tree.root=42
        tree.owned={42:(100,1),43:(100,2)};tree.table={}
        records={42:dict(birth=(100,1),ppid=1,pgid=42),
                 43:dict(birth=(200,2),ppid=999,pgid=43)}
        table={42:(1,42,'?'),43:(999,43,'?')}
        with self.identity_observations(records),patch('power_guard._processes',return_value=table), \
             patch('power_guard.os.kill') as kill:
            before=dict(tree.owned)
            tree.signal(signal.SIGKILL)
            self.assertEqual(tree.owned,before)
            self.assertEqual(kill.call_args_list,[unittest.mock.call(42,signal.SIGKILL)])
            self.assertEqual(tree.retirement_summary()['counts'],dict(gone=0,reused=0))
            self.assertEqual(tree.refresh(),{42})
            self.assertEqual(tree.retirement_summary()['counts'],dict(gone=0,reused=1))
            self.assertEqual(tree.describe(),[dict(pid=42,birth=[100,1],pgid=42)])

    def test_linux_identity_parser_compatibility_does_not_use_darwin_proof(self):
        fields=['0']*20;fields[0]='S';fields[1]='1';fields[2]='42';fields[19]='9999'
        with patch.object(power_guard.sys,'platform','linux'), \
             patch.object(power_guard,'_darwin_process_query',side_effect=AssertionError('Linux used Darwin proof'),create=True), \
             patch.object(Path,'read_text',return_value='42 (worker) '+' '.join(fields)):
            self.assertEqual(power_guard._process_info(42),dict(birth=(9999,),ppid=1,pgid=42))
        for error in (PermissionError('denied'),ValueError('malformed')):
            with patch.object(power_guard.sys,'platform','linux'),patch.object(Path,'read_text',side_effect=error):
                self.assertIsNone(power_guard._process_info(42))

    @unittest.skipUnless(sys.platform == 'darwin','Darwin ownership retirement fixture')
    def test_immutable_root_identity_survives_reap_and_retirement(self):
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/'result'
            first_records=[]
            real_refresh=_OwnedTree.refresh
            def first_refresh(tree):
                if not first_records:
                    initial=json.loads((output/'run.json').read_text())
                    first_records.append(initial)
                    self.assertEqual(initial.get('root_identity'),
                                     dict(pid=tree.root,birth=list(tree.owned[tree.root])))
                return real_refresh(tree)
            with patch.object(_OwnedTree,'refresh',new=first_refresh):
                result=run([sys.executable,'-c','import time;time.sleep(.05)'],output,
                           dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=3),
                           power=lambda:True,poll=.01,capture_inputs=False)
            self.assertEqual(len(first_records),1)
            self.assertTrue(result['passed'])
            binding=result['root_identity']
            self.assertEqual(binding['pid'],result['pid'])
            self.assertEqual(len(binding['birth']),2)
            self.assertTrue(all(type(value) is int for value in binding['birth']))
            self.assertEqual(result['owned_processes'],[])
            retired=[p for p in result['ownership_retirement']['recent']
                     if p['pid']==binding['pid'] and p['birth']==binding['birth']]
            self.assertEqual(len(retired),1)
            self.assertEqual(retired[0]['reason'],'gone')
            self.assertTrue(retired[0]['list_absent'])
            durable=json.loads((output/'run.json').read_text())
            self.assertEqual(durable['root_identity'],binding)
            self.assertEqual(durable['owned_processes'],[])



if __name__ == '__main__': unittest.main()
