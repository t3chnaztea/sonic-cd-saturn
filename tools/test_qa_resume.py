#!/usr/bin/env python3
"""Checkpoint recovery controls. No compiler, emulator or game execution."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

import qa_resume as resume
from zone_release_evidence import (canonical_matrix_command, matrix_command, audit,
                                   expected_windows, ZONES, GATES, SPECIAL, SPECIAL_GATE, SPECIAL_CASES)

ROOT = Path(__file__).resolve().parents[1]
BIOS_NAMES = ('assets/private/mpr-17933.bin', 'assets/private/sega_101.bin',
              'assets/private/saturn-bios.bin', 'assets/private/bios_CD_U.bin')
EMPTY_BIOS = {name: {'present': False} for name in BIOS_NAMES}
ENVIRONMENT_NAMES = ('SS_CFLAGS','MM_CFLAGS','QQ_CFLAGS','WW_CFLAGS','TT_EXTRA','SCD_DATA_ROOT',
    'TT_BG_WRITE_LIMIT','QQ_BG_WRITE_LIMIT','WW_BG_WRITE_LIMIT','SS_BG_WRITE_LIMIT','MM_BG_WRITE_LIMIT',
    'MM_ONLY','SS_ONLY','WW_ONLY','MM_ORDER_CHECK','SLOT_SYNC_CHECK','SCD_REPLAY_TRACE','MM_DEBUG',
    'SS_DEBUG','WATER_TRACE','WW_TRACE','CDPP_ACTORS','SCD_PLAYER_VISUAL_TRACE_FILE')
EMPTY_ENVIRONMENT = {name: {'present':False} for name in ENVIRONMENT_NAMES}


def synthetic_reference_profile(root, core):
    """Tiny synthetic files only. Never a real core/guard or production approval."""
    import hashlib, platform, struct
    def write(name,data):
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data if isinstance(data,bytes) else data.encode());return path
    def pin(path):return dict(path=str(path.relative_to(root)),sha256=resume.digest(path))
    def js(name,data):return write(name,json.dumps(data,sort_keys=True)+'\n')
    import ast
    source=(ROOT/'tools/extract_mmd.py').read_text()
    function=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='disc_files')
    write('tools/extract_mmd.py',ast.get_source_segment(source,function)+'\n')
    if not (root/'build/retail/sonic.iso').exists():
        image=bytearray(28*2048)
        struct.pack_into('<I',image,16*2048+156+2,17)
        struct.pack_into('<I',image,16*2048+156+10,2048)
        cursor=17*2048
        for index,name in enumerate((*resume._REFERENCE_PROGRAMS,*("R31"+e+"__.MMD" for e in "ABCD"))):
            label=(name+';1').encode();size=33+len(label)+(not len(label)%2)
            image[cursor]=size;struct.pack_into('<I',image,cursor+2,18+index)
            struct.pack_into('<I',image,cursor+10,1);image[cursor+32]=len(label)
            image[cursor+33:cursor+33+len(label)]=label;cursor+=size
            value=bytes([index+1]);image[(18+index)*2048]=index+1
            write('build/retail/'+name,value)
        write('build/retail/sonic.iso',bytes(image))
        raw=b''.join(b'\0'*16+image[i:i+2048]+b'\0'*288 for i in range(0,len(image),2048))
        write('build/retail/sonic.bin',raw+b'\0'*2352)
        write('build/retail/sonic.cue','FILE "sonic.bin" BINARY\n TRACK 01 MODE1/2352\n INDEX 01 00:00:00\n TRACK 02 AUDIO\n INDEX 00 00:00:28\n INDEX 01 00:00:28\n')
    sources={}
    for name in ('Makefile.libretro','libretro/libretro.c','core/loadrom.c','core/cd_hw/cdd.c','core/cd_hw/cd_cart.c'):
        path=write('.deps/genesis-plus-gx/'+name,'synthetic source '+name)
        sources[str(path.relative_to(root))]=resume.digest(path)
    context=dict(protocol=1,runtime=dict(platform=platform.platform(),uname=list(platform.uname()),python=platform.python_version()),
                 toolchain=dict(compiler='synthetic-cc'),source_sha256={'fixture':'only'},limits={},bin_sha256=None)
    log=write('build/synthetic-core/log.txt','synthetic only\n')
    output=dict(path=str(core.relative_to(root)),size=core.stat().st_size,sha256=resume.digest(core))
    plans=[dict(kind='compile' if i<115 else 'link',argv=['synthetic-cc',str(i)],output=output['path']) for i in range(116)]
    recipe=js('build/synthetic-core/recipe.json',dict(commands=plans))
    command=['synthetic-no-execution']
    root_identity=dict(pid=42,birth=[1,2]);child=dict(pid=43,birth=[1,3])
    guard=js('build/synthetic-core/guard.json',dict(status='passed',passed=True,changed_inputs=[],exit_code=0,command=command,
             root_identity=root_identity,cleanup_survivors=[],owned_processes=[child]))
    cleanup=js('build/synthetic-core/cleanup.json',dict(schema='guarded-core-build-cleanup-v1',status='passed',
        guard=pin(guard),root_identity=root_identity,survivors=[],uncertain_roots=[],
        coordinator_tool_and_native_binding_verified=True,audited_generations=[root_identity,child]))
    commands=[dict(kind=p['kind'],argv=p['argv'],exit_code=0,log=pin(log),output=output,
                   dependency_paths=list(sources)) for p in plans]
    build=js('build/synthetic-core/build.json',dict(schema='genesis-default-core-build-v1',profile='genesis-default-v1',
        status='passed',actual_build=True,metadata_only=False,sources=sources,runtime=context['runtime'],toolchain=context['toolchain'],
        recipe=pin(recipe),commands=commands,output=output,execution=dict(command=command,guard=pin(guard),cleanup=pin(cleanup))))
    review=js('build/synthetic-core/review.json',dict(verdict='approved_guarded_core_build',
               approved_files={str(p):resume.digest(p) for p in (build,recipe,guard,cleanup)}))
    js('build/qa-core-profiles/genesis-default.json',dict(protocol=1,build=pin(build),approval=pin(review)))
    return context


class Recovery(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {k:v for k,v in os.environ.items()
                                             if k not in ENVIRONMENT_NAMES}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'build', prefix='resume-controls-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'build').mkdir()
        self.inputs = {'src/game.c': 'game-source'}
        self.ctx = dict(protocol=1, runtime={'python': 'same'}, bin_sha256='same-bin',
                        limits={'workers': '1'}, source_sha256=self.inputs)
        self.commands = [[*matrix_command(ZONES, True), '--jobs', '1'], ['bash','tools/test-save.sh']]

    def write(self, name, value):
        p = self.root/name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(value) if not isinstance(value, str) else value)
        return p

    def checkpoint(self, count=1, legacy=False):
        # Keep the original component assertions on admitted canonical fixtures.
        # Production admission is never mocked.
        self.commands = [([*matrix_command(ZONES, True), '--jobs', '1']
            if cmd == matrix_command(('ppz',), False) else
            ['bash','tools/test-time-attack.sh'] if cmd[:1] == ['check'] else cmd)
            for cmd in self.commands]
        steps = []
        for i in range(count):
            log = self.write(f'logs/{i}.log', 'PASS: observed\n')
            steps.append(dict(command=self.commands[i], exit_code=0, seconds=1,
                              log=str(log.relative_to(self.root)), log_sha256=resume.digest(log),
                              bios_inputs=copy.deepcopy(EMPTY_BIOS),
                              execution_environment=copy.deepcopy(EMPTY_ENVIRONMENT),
                              reference_inputs=resume.preserve_reference_inputs(self.root,resume.reference_inputs(self.root))))
        data = dict(mode='fast', status='interrupted', passed=False, steps=steps,
                    source_sha256=self.inputs)
        if any(cmd[:2] == ['python3','tools/zone-gates.py'] for cmd in self.commands[:count]):
            matrix = self.write('build/zone-gates/synthetic/report.json',dict(status='passed'))
            data.update(zone_gates_report=str(matrix.relative_to(self.root)),zone_gates_report_sha256=resume.digest(matrix))
        if not legacy:
            data['checkpoint_context'] = self.ctx
        return self.write('report.json', data), data

    def choices(self, path, migration=None):
        return resume.cached_steps(self.root, 'fast', self.commands, self.ctx, [path], migration)[0]

    def test_interrupted_next_check_reuses_only_completed_work(self):
        path, data = self.checkpoint()
        data['active_step'] = 1
        path.write_text(json.dumps(data))
        choices = self.choices(path)
        self.assertEqual(set(choices), {0})
        self.assertEqual([i for i in range(2) if i not in choices], [1])
        self.assertEqual(choices[0]['reused_from']['report_sha256'], resume.digest(path))

    def test_completed_suite_has_no_work_to_repeat(self):
        path, _ = self.checkpoint(2)
        self.assertEqual(set(self.choices(path)), {0, 1})

    def test_input_integrity_is_rechecked_without_replaying_other_tests(self):
        self.commands = [['python3', 'tools/test_assets.py'], ['check', 'already-complete']]
        path, _ = self.checkpoint(2)
        self.assertEqual(set(self.choices(path)), {1})

    def test_corrupt_one_log_preserves_other_completed_check(self):
        path, _ = self.checkpoint(2)
        (self.root/'logs/0.log').write_text('truncated')
        self.assertEqual(set(self.choices(path)), {1})

    def test_failure_and_boolean_exit_are_never_passes(self):
        for code in (1, 124, False, None):
            with self.subTest(code=code):
                path, data = self.checkpoint()
                data['steps'][0]['exit_code'] = code
                path.write_text(json.dumps(data))
                self.assertEqual(self.choices(path), {})

    def test_source_change_refuses_reuse(self):
        path, _ = self.checkpoint()
        self.ctx = copy.deepcopy(self.ctx)
        self.ctx['source_sha256']['src/game.c'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'inputs/runtime/build'):
            self.choices(path)

    def test_context_build_or_runtime_change_refuses_reuse(self):
        for field in ('bin_sha256', 'runtime', 'limits'):
            path, _ = self.checkpoint()
            current = copy.deepcopy(self.ctx)
            current[field] = 'changed'
            with self.subTest(field=field), self.assertRaises(ValueError):
                resume.cached_steps(self.root, 'fast', self.commands, current, [path])

    def test_command_plan_change_refuses_reuse(self):
        path, data = self.checkpoint()
        data['steps'][0]['command'] = ['different-check']
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'command changed'):
            self.choices(path)

    def test_actual_command_cannot_hide_behind_canonical_label(self):
        path, data = self.checkpoint()
        data['steps'][0]['canonical_command'] = self.commands[0]
        data['steps'][0]['command'] = ['weaker-check']
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'actual command'):
            self.choices(path)

    def test_cross_suite_reuse_is_rejected(self):
        path, data = self.checkpoint()
        data['mode'] = 'full'
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'same complete suite'):
            self.choices(path)

    def test_legacy_report_needs_explicit_seal(self):
        path, _ = self.checkpoint(legacy=True)
        with self.assertRaises(ValueError):
            self.choices(path)
        migration = dict(protocol=1, legacy_reports={str(path): resume.digest(path)},
                         legacy_runtime=self.ctx['runtime'], legacy_bin_sha256='same-bin',
                         legacy_limits=self.ctx['limits'])
        self.assertEqual(set(self.choices(path, migration)), {0})
        migration['legacy_reports'][str(path)] = 'wrong'
        with self.assertRaises(ValueError):
            self.choices(path, migration)

    def test_migration_cannot_authorize_game_changes(self):
        before = {'src/game.c': 'old'}
        after = {'src/game.c': 'new'}
        migration = dict(protocol=1, before_inputs=before, after_inputs=after,
                         changed_paths=['src/game.c'])
        self.assertFalse(resume.same_inputs(before, after, migration))

    def test_exact_runner_upgrade_is_bounded_and_infrastructure_rechecked(self):
        before = {'src/game.c': 'same', 'tools/qa-loop.py': 'old'}
        after = {'src/game.c': 'same', 'tools/qa-loop.py': 'new'}
        migration = dict(protocol=1, before_inputs=before, after_inputs=after,
                         changed_paths=['tools/qa-loop.py'])
        self.assertTrue(resume.same_inputs(before, after, migration))
        self.assertTrue(resume.infrastructure_command(['python3', 'tools/test_qa_dispatch_cooling.py']))
        self.assertFalse(resume.infrastructure_command(['bash', 'tools/test-player.sh']))
        migration['changed_paths'] = []
        self.assertFalse(resume.same_inputs(before, after, migration))

    def window(self, child=None):
        child = child or dict(passed=True, disc_sha256='same-bin')
        base = self.root/'build/zone-gates/run'
        evidence = self.write('build/zone-gates/run/evidence/case.json', child)
        log = self.write('build/zone-gates/run/logs/case.log', 'PASS: case\n')
        entry = dict(status='pass', returncode=0, evidence=str(evidence.relative_to(self.root)),
                      bios_inputs=copy.deepcopy(EMPTY_BIOS),
                      execution_environment=copy.deepcopy(EMPTY_ENVIRONMENT),
                      reference_inputs=resume.preserve_reference_inputs(self.root,resume.reference_inputs(self.root)),
                     evidence_sha256=resume.digest(evidence), log=str(log.relative_to(self.root)),
                     log_sha256=resume.digest(log))
        window = types.SimpleNamespace(gate='routes', zone='ppz', name='PPZ1A',
            parse=lambda result, report: ('pass' if report['passed'] else 'fail', {}, ''))
        return base, window, entry

    def test_matrix_reuses_intact_case_not_tampered_case(self):
        base, window, entry = self.window()
        self.assertTrue(resume.cached_window(self.root, base, window, entry, 'same-bin'))
        (self.root/entry['evidence']).write_text('{}')
        self.assertFalse(resume.cached_window(self.root, base, window, entry, 'same-bin'))

    def test_matrix_rechecks_recorded_input_hashes(self):
        source = self.write('src/route.txt', 'original')
        base, window, entry = self.window(dict(passed=True, disc_sha256='same-bin',
            inputs={'src/route.txt': resume.digest(source)}))
        self.assertTrue(resume.cached_window(self.root, base, window, entry, 'same-bin'))
        source.write_text('changed')
        self.assertFalse(resume.cached_window(self.root, base, window, entry, 'same-bin'))

    def test_matrix_reparses_original_retail_oracle(self):
        spec = importlib.util.spec_from_file_location('resume_zone', ROOT/'tools/zone-gates.py')
        zone = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(zone)
        parity = dict(compared=10, contiguous=10, contiguous_all_fields=10,
                      native_end='Tally complete: sequence=100', retail_restart=50, retail_updates=120)
        base, window, entry = self.window({'retail_parity': parity})
        window.gate, window.parse = 'retail', zone.parse_retail
        self.assertFalse(resume.cached_window(self.root, base, window, entry, 'same-bin'))
        parity['retail_restart'] = None
        (self.root/entry['evidence']).write_text(json.dumps({'retail_parity': parity}))
        entry['evidence_sha256'] = resume.digest(self.root/entry['evidence'])
        self.assertTrue(resume.cached_window(self.root, base, window, entry, 'same-bin'))

    def test_campaign_child_with_stale_parent_is_not_reused(self):
        base, window, entry = self.window(dict(passed=True, disc_sha256='same-bin',
            entry_evidence={'sha256': 'previous-parent'}))
        window.gate, window.zone, window.name = 'campaign', 'ss', 'SS1'
        results = {'ww': {'campaign': {'WW3': {'status': 'pass', 'evidence_sha256': 'current-parent'}}}}
        self.assertFalse(resume.campaign_cache_matches(self.root, window, entry, results))
        results['ww']['campaign']['WW3']['evidence_sha256'] = 'previous-parent'
        self.assertTrue(resume.campaign_cache_matches(self.root, window, entry, results))

    def test_safe_resource_resume_flags_do_not_weaken_matrix_scope(self):
        expected = matrix_command(('ppz', 'cc'), False)
        command = expected + ['--jobs', '1', '--resume', 'build/zone-gates/run/report.json']
        self.assertEqual(canonical_matrix_command(command), expected)
        for extra in (['--jobs', '2'], ['--windows', 'PPZ1A'], ['--jobs', '1', '--jobs', '1']):
            self.assertNotEqual(canonical_matrix_command(expected + extra), expected)
        self.assertIsNone(canonical_matrix_command(expected + ['--resume', '--windows']))

    def test_nested_checkpoint_is_discovered_from_interrupted_command_log(self):
        commands = [matrix_command(('ppz',), False)]
        matrix = self.write('build/zone-gates/partial/report.json', {'status': 'interrupted'})
        source = self.write('outer/report.json', dict(mode='full', active_step=0))
        self.write('outer/00.log', 'zone-gates: 10 windows, 10 runs, 1 groups, jobs 1; build/zone-gates/partial\n')
        self.assertEqual(resume.discover_matrix(self.root, source, commands), matrix)
        self.assertIsNone(resume.discover_matrix(self.root, source, [['different-check']]))

    def test_cached_matrix_verdict_also_needs_its_matrix_evidence(self):
        self.commands = [matrix_command(('ppz',), False)]
        path, data = self.checkpoint()
        matrix = self.write('build/zone-gates/done/report.json', {'status': 'passed'})
        data['zone_gates_report'] = str(matrix.relative_to(self.root))
        data['zone_gates_report_sha256'] = resume.digest(matrix)
        path.write_text(json.dumps(data))
        self.assertEqual(self.choices(path)[0]['zone_gates_report'], data['zone_gates_report'])
        matrix.write_text('changed')
        self.assertEqual(self.choices(path), {})

    def test_legacy_matrix_needs_explicit_outer_report_relationship(self):
        source, data = self.checkpoint(legacy=True)
        data['mode'] = 'full'
        source.write_text(json.dumps(data))
        matrix = self.write('build/zone-gates/legacy/report.json', {'bin_sha256': 'same-bin'})
        migration = dict(protocol=1, legacy_reports={str(source): resume.digest(source)},
                         legacy_runtime=self.ctx['runtime'], legacy_bin_sha256='same-bin',
                         legacy_limits=self.ctx['limits'])
        self.assertFalse(resume.legacy_matrix_compatible(matrix, source, self.ctx, migration))
        migration['legacy_matrices'] = {str(matrix): dict(sha256=resume.digest(matrix),
            source_report=str(source), source_sha256=resume.digest(source))}
        outer_log = self.write('outer.log', 'zone-gates: 1 windows, 1 runs, 1 groups, jobs 1; build/zone-gates/legacy\n')
        migration['legacy_matrices'][str(matrix)].update(outer_log=str(outer_log),
            outer_log_sha256=resume.digest(outer_log))
        self.assertTrue(resume.legacy_matrix_compatible(matrix, source, self.ctx, migration))
        matrix.write_text('{}')
        self.assertFalse(resume.legacy_matrix_compatible(matrix, source, self.ctx, migration))

    def test_complete_release_audit_accepts_jobs1_but_refuses_partial_scope(self):
        self.write('Makefile', 'IP_VERSION:= V0.081\n')
        base = Path('build/zone-gates/complete')
        results = {}
        children = {}
        for zone, gates in expected_windows(ZONES, True).items():
            results[zone] = {}
            for gate, names in gates.items():
                results[zone][gate] = {}
                for name in sorted(names):
                    child = dict(status='passed', passed=True, disc_sha256='fixture-bin',
                                 respawns=0, late_gameplay_intervals=[],
                                 backup_after_sha256='backup-'+zone+'-'+name)
                    if gate == 'retail':
                        child.update(inputs={'fixture': 'metadata-only'}, retail_parity=dict(
                            compared=3, contiguous=3, contiguous_all_fields=3,
                            first_field_divergence=None, native_end='Tally complete: sequence=2',
                            retail_restart=None, retail_updates=4))
                    evidence = base/'evidence'/(zone+'-'+gate+'-'+name+'.json')
                    log = base/'logs'/(zone+'-'+gate+'-'+name+'.log')
                    self.write(evidence, child)
                    self.write(log, 'PASS: metadata fixture\n')
                    entry = dict(status='pass', returncode=0, evidence=str(evidence), log=str(log),
                                 evidence_sha256=resume.digest(self.root/evidence),
                                 log_sha256=resume.digest(self.root/log))
                    results[zone][gate][name] = entry
                    children[zone, gate, name] = child
        def update(zone, name, **fields):
            child = children[zone, 'campaign', name]
            child.update(fields)
            entry = results[zone]['campaign'][name]
            self.write(entry['evidence'], child)
            entry['evidence_sha256'] = resume.digest(self.root/entry['evidence'])
        ppz = children['ppz', 'campaign', 'PPZ3']
        update('cc', 'checkpoint', ppz3_report_sha256=results['ppz']['campaign']['PPZ3']['evidence_sha256'],
               backup_sha256=ppz['backup_after_sha256'], saved_flags=0x100)
        update('cc', 'act3-good-bad', entry_backup_sha256=ppz['backup_after_sha256'])
        for zone, name, prior_zone, prior_name in (
                ('ss', 'SS1', 'ww', 'WW3'), ('ss', 'SS2', 'ss', 'SS1'),
                ('ss', 'SS3', 'ss', 'SS2'), ('mm', 'MM1', 'ss', 'SS3'),
                ('mm', 'MM2', 'mm', 'MM1'), ('mm', 'MM3', 'mm', 'MM2')):
            update(zone, name, entry_evidence={'sha256': results[prior_zone]['campaign'][prior_name]['evidence_sha256']},
                   entry_backup_sha256=children[prior_zone, 'campaign', prior_name]['backup_after_sha256'])
        update('mm', 'MM3', completed=1, title_frame=1)
        matrix = dict(status='passed', passed=True, bin_sha256='fixture-bin', bin_sha256_end='fixture-bin',
                      failed_gates=0, zones=[*ZONES, SPECIAL], gates=[*GATES, SPECIAL_GATE],
                      hardware_tested=False, results=results)
        self.assertEqual(sum(len(cases) for gates in results.values() for cases in gates.values()), 347)
        matrix_path = self.write(base/'report.json', matrix)
        command = matrix_command(ZONES, True)+['--jobs', '1']
        qa = dict(mode='full', status='passed', passed=True, disc_sha256='fixture-bin',
                  steps=[dict(command=command, exit_code=0)], zone_gates_report=str(base/'report.json'),
                  zone_gates_report_sha256=resume.digest(matrix_path))
        checked, _ = audit(self.root, qa, 'fixture-bin')
        self.assertEqual(checked['results'], results)
        for extra in (['--windows', 'PPZ1A'], ['--jobs', '2']):
            qa['steps'][0]['command'] = matrix_command(ZONES, True)+extra
            with self.subTest(extra=extra), self.assertRaisesRegex(AssertionError, 'Missing full release zone gate'):
                audit(self.root, qa, 'fixture-bin')


class BIOSContext(unittest.TestCase):
    setUp = Recovery.setUp
    write = Recovery.write
    checkpoint = Recovery.checkpoint
    choices = Recovery.choices
    window = Recovery.window

    def test_unsealed_steps_default_deny_emulator_and_unknown(self):
        for command in (['python3', 'tools/test_ppz_route.py', '--host-only'],
                        ['python3', 'tools/test_frontend_emulator.py'], ['unknown-host']):
            self.commands = [command]
            path, data = self.checkpoint()
            self.assertTrue(resume.bios_reusable(data['steps'][0]['bios_inputs'],resume.bios_inputs(self.root),command))
            self.assertEqual(self.choices(path),{})  # Outer unknown-command policy is stricter.
            del data['steps'][0]['bios_inputs']
            path.write_text(json.dumps(data))
            with self.subTest(command=command):
                self.assertEqual(self.choices(path), {})

    def test_unsealed_matrix_retail_or_route_is_not_blessed_by_current_hash(self):
        for gate in ('retail', 'routes'):
            base, window, entry = self.window()
            window.gate = gate
            window.run = types.SimpleNamespace(cmds=[['python3', 'tools/test_ppz_route.py', '--host-only']])
            del entry['bios_inputs']
            with self.subTest(gate=gate):
                self.assertFalse(resume.cached_window(self.root, base, window, entry, 'same-bin'))

    def test_actual_files_record_all_names_missing_presence_and_same_size_bytes(self):
        before = resume.bios_inputs(self.root)
        self.assertEqual(before, EMPTY_BIOS)
        path = self.write(BIOS_NAMES[0], 'aaaa')
        sealed = resume.bios_inputs(self.root)
        self.assertEqual(sealed[BIOS_NAMES[0]], dict(present=True, size=4, sha256=resume.digest(path)))
        self.assertEqual(set(sealed), set(BIOS_NAMES))
        original_time = path.stat().st_mtime_ns
        path.write_text('bbbb')
        os.utime(path, ns=(original_time, original_time))
        with self.assertRaisesRegex(ValueError, 'BIOS inputs changed'):
            resume.verify_bios_inputs(self.root, sealed)
        self.assertNotEqual(resume.bios_inputs(self.root), sealed)
        path.unlink()
        self.assertEqual(resume.bios_inputs(self.root), before)

    def test_missing_appeared_removed_or_malformed_seals_reject(self):
        absent = resume.bios_inputs(self.root)
        path = self.write(BIOS_NAMES[1], 'fixture-only')
        with self.assertRaises(ValueError):
            resume.verify_bios_inputs(self.root, absent)
        present = resume.bios_inputs(self.root)
        path.unlink()
        with self.assertRaises(ValueError):
            resume.verify_bios_inputs(self.root, present)
        for value in ({}, {**absent, BIOS_NAMES[0]: {'present': 0}},
                      {**absent, BIOS_NAMES[0]: {'present': True, 'size': False, 'sha256': 'a'*64}}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                resume.verify_bios_inputs(self.root, value)

    def test_bios_mutation_during_hash_is_not_published(self):
        path = self.write(BIOS_NAMES[0], 'before')
        digest = resume.digest
        def changed(p):
            path.write_text('different bytes')
            return digest(p)
        with patch.object(resume,'digest',side_effect=changed),self.assertRaisesRegex(ValueError,'while hashing'):
            resume.bios_inputs(self.root)

    def test_sealed_reuse_matches_bytes_and_legacy_native_is_exact(self):
        path, data = self.checkpoint()
        self.assertEqual(set(self.choices(path)), {0})
        self.write(BIOS_NAMES[0], 'changed synthetic BIOS')
        self.assertEqual(self.choices(path), {})
        data['steps'][0]['bios_inputs'] = resume.bios_inputs(self.root)
        path.write_text(json.dumps(data))
        self.assertEqual(set(self.choices(path)),{0})
        for command in (['bash', 'tools/test-save.sh'], ['bash', 'tools/test-time-attack.sh'],
                        ['bash', 'tools/test-world.sh'], ['bash','tools/test-player.sh'],
                        ['python3','tools/test_cdpp_player.py'], ['python3','tools/test_world_restart.py'],
                        ['python3','tools/test_sprite_priority.py']):
            self.commands = [command]
            path, data = self.checkpoint()
            # This fixture's valid older all-missing seal differs from the
            # current synthetic BIOS. Independent native output is still valid.
            self.assertEqual(set(self.choices(path)),{0})
            del data['steps'][0]['bios_inputs']
            path.write_text(json.dumps(data))
            self.assertEqual(set(self.choices(path)), {0})
            data['steps'][0]['command'] = [*command, '--unreviewed-argument']
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                self.choices(path)

    def test_bios_change_cannot_leave_pass_or_mask_primary_save_error(self):
        report = dict(status='passed', passed=True, bios_inputs=resume.bios_inputs(self.root))
        self.write(BIOS_NAMES[0], 'changed')
        def failed_save():
            raise OSError('metadata save fault')
        with self.assertRaisesRegex(ValueError, 'BIOS inputs changed') as error:
            resume.checkpoint_bios_inputs(self.root, report, failed_save)
        self.assertFalse(report['passed'])
        self.assertEqual(report['status'], 'failed')
        self.assertIn('metadata save fault', str(error.exception.__notes__))

    def test_actual_matrix_executor_checks_after_cooldown_and_after_child(self):
        import ast
        import threading
        source = ast.parse((ROOT/'tools/zone-gates.py').read_text())
        function = next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='execute')
        for change_at in ('cooldown','child'):
            folder = self.root/change_at;folder.mkdir()
            expected = resume.bios_inputs(self.root)
            calls = []
            def mutate():
                self.write(BIOS_NAMES[0],change_at)
            def cool(*args,**kwargs):
                if change_at=='cooldown':mutate()
            def run(*args,**kwargs):
                calls.append(args[0]);mutate()
                return types.SimpleNamespace(returncode=0)
            namespace = dict(ROOT=self.root,os=os,time=types.SimpleNamespace(time=lambda:0,monotonic=lambda:0),
                cooldown=cool,subprocess=types.SimpleNamespace(run=run,STDOUT=-2,TimeoutExpired=TimeoutError),
                _sync_file=lambda fd:None,json=json,shutil=types.SimpleNamespace())
            exec(compile(ast.Module(body=[function],type_ignores=[]),'<actual matrix executor>','exec'),namespace)
            job = types.SimpleNamespace(key=('fixture',),out=None,cmds=[['mock-command']],env={},report=None)
            with self.subTest(change_at=change_at), self.assertRaisesRegex(ValueError,'BIOS inputs changed'):
                namespace['execute'](job,folder,10,threading.Lock(),dict(last_finished=0,seconds=120),
                    input_check=lambda:resume.verify_bios_inputs(self.root,expected))
            self.assertEqual(len(calls),0 if change_at=='cooldown' else 1)
            self.assertFalse(hasattr(job,'result'))
            (self.root/BIOS_NAMES[0]).unlink()

    def test_actual_suite_loop_fails_before_or_after_child_without_passing_row(self):
        import ast
        import contextlib
        import io
        import hashlib
        source = ast.parse((ROOT/'tools/qa-loop.py').read_text())
        loop = next(n for n in source.body if isinstance(n,ast.For) and isinstance(n.iter,ast.Call)
                    and isinstance(n.iter.func,ast.Name) and n.iter.func.id=='enumerate'
                    and n.iter.args and isinstance(n.iter.args[0],ast.Name) and n.iter.args[0].id=='selected')
        previous = source.body[source.body.index(loop)-1]
        for change_at in ('cooldown','child'):
            folder = self.root/change_at;folder.mkdir()
            report = dict(status='pending',passed=False,steps=[],bios_inputs=resume.bios_inputs(self.root),checkpoint_context=dict(protocol=1))
            calls=[]
            def mutate():self.write(BIOS_NAMES[0],change_at)
            def cool(*args,**kwargs):
                if change_at=='cooldown':mutate()
            def run(*args,**kwargs):
                calls.append(args[0]);kwargs['stdout'].write('PASS: synthetic child only\n');mutate()
                return types.SimpleNamespace(returncode=0)
            namespace=dict(ROOT=self.root,out=folder,report=report,qa_resume=resume,prefix_cache={},
                selected=[['mock-command']],start_step=0,session_limits=dict(cooldown_seconds=120),
                suite_mode='fast',time=types.SimpleNamespace(monotonic=lambda:0),cooldown=cool,
                subprocess=types.SimpleNamespace(run=run,STDOUT=-2),_sync_file=lambda fd:None,
                atomic_json=lambda p,r:p.write_text(json.dumps(r)),hashlib=hashlib,json=json)
            with self.subTest(change_at=change_at),contextlib.redirect_stdout(io.StringIO()),self.assertRaises(ValueError):
                exec(compile(ast.Module(body=[previous,loop],type_ignores=[]),'<actual suite loop>','exec'),namespace)
            saved=json.loads((folder/'report.json').read_text())
            self.assertFalse(saved['passed']);self.assertEqual(saved['status'],'failed')
            self.assertEqual(saved['steps'],[])
            self.assertEqual(len(calls),0 if change_at=='cooldown' else 1)
            (self.root/BIOS_NAMES[0]).unlink()

    def test_followup_migration_exact_parent_and_bounded_linkage(self):
        before = {'src/game.c':'same', 'tools/qa-loop.py':'old', 'tools/retail_parity.py':'retail-old'}
        middle = {**before, 'tools/qa-loop.py':'middle'}
        after = {**middle, 'tools/qa-loop.py':'new', 'tools/retail_parity.py':'retail-new'}
        parent = dict(protocol=1, before_inputs=before, after_inputs=middle,
                      changed_paths=['tools/qa-loop.py'], legacy_reports={}, legacy_matrices={},
                      legacy_runtime={}, legacy_bin_sha256='same', legacy_limits={}, legacy_toolchain={})
        parent_path = self.write('M1.json', parent)
        migration = {**parent, 'before_inputs':middle, 'after_inputs':after,
                     'changed_paths':['tools/qa-loop.py','tools/retail_parity.py'],
                     'parent_migration':dict(path=str(parent_path), sha256=resume.digest(parent_path))}
        for old in (before, middle):
            self.assertTrue(resume.same_inputs(old, after, migration))
        self.assertFalse(resume.same_inputs({'unrelated':'epoch'}, after, migration))
        for key, value in (('before_inputs', before), ('legacy_reports', {'new':'seal'}),
                           ('after_inputs', {**after, 'src/game.c':'changed'})):
            bad = copy.deepcopy(migration);bad[key] = value
            self.assertFalse(resume.same_inputs(before, bad['after_inputs'], bad))
        parent_path.write_text(json.dumps({**parent, 'legacy_limits':{'changed':True}}))
        self.assertFalse(resume.same_inputs(before, after, migration))

    def test_source_admission_and_entry_reuse_are_separate(self):
        self.commands = [['python3','tools/test_frontend_emulator.py']]
        before = {**self.inputs,'tools/qa-loop.py':'before'}
        after = {**self.inputs,'tools/qa-loop.py':'after'}
        self.inputs = before
        path,data = self.checkpoint()
        data['source_sha256'] = before
        data['checkpoint_context'] = {**self.ctx,'source_sha256':before}
        del data['steps'][0]['bios_inputs']
        path.write_text(json.dumps(data))
        self.ctx = {**self.ctx,'source_sha256':after}
        migration = dict(protocol=1,before_inputs=before,after_inputs=after,changed_paths=['tools/qa-loop.py'])
        self.assertTrue(resume.compatible(data,self.ctx,migration,path))
        self.assertEqual(self.choices(path,migration),{})

    def test_retail_inner_key_requires_actual_bios_bytes_and_rejects_mid_run_change(self):
        import ast
        source = ast.parse((ROOT/'tools/retail_parity.py').read_text())
        function = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == 'retail_parity')
        cutoff = next(i for i,n in enumerate(function.body) if isinstance(n, ast.Assign)
                      and any(isinstance(t,ast.Name) and t.id=='r' for t in n.targets))
        function.body = function.body[:cutoff]
        out = self.root/'retail';out.mkdir()
        script = self.write('pad.txt', '1 0\n')
        core = self.write('.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib','tiny synthetic core')
        for name in ('retail_probe.py','retail_parity.py','special_retail.py','retail_capture.py','qa_resume.py'):
            self.write('tools/'+name, 'fixture source '+name)
        calls = []
        change = [False]
        def run(argv, **kwargs):
            if argv[0] == 'python3':
                calls.append(argv)
                (out/'retail.rows').write_text('synthetic rows, not executed')
                if change[0] == 'environment':
                    os.environ['SCD_DATA_ROOT']='changed-during-retail'
                elif change[0] == 'reference':
                    self.write('build/audit/source/src/R1/COLI1.C','changed during retail capture')
                elif change[0] == 'core':
                    core.write_text('core changed during comparison')
                elif change[0]:
                    self.write(BIOS_NAMES[0], 'changed-during-retail')
            return types.SimpleNamespace(stderr='unlock 1\n',returncode=0)
        import re
        namespace = dict(ROOT=self.root,Path=Path,json=json,os=os,re=re,
            tempfile=tempfile,
            subprocess=types.SimpleNamespace(run=run),sha=resume.digest,
            TOOLS=('retail_probe.py','retail_parity.py','special_retail.py','retail_capture.py','qa_resume.py'),
            ZONES={1:'PPZ'},iso_sha256=lambda:'pinned-fixture-ISO',
            bios_inputs=resume.bios_inputs,verify_bios_inputs=resume.verify_bios_inputs)
        namespace.update(execution_environment=resume.execution_environment,
                         verify_execution_environment=resume.verify_execution_environment,
                         reference_inputs=resume.reference_inputs,preserve_reference_inputs=resume.preserve_reference_inputs,
                         verify_reference_inputs=resume.verify_reference_inputs,
                         reference_cache_allowed=resume.reference_cache_allowed,hashlib=__import__('hashlib'),
                         consumer_context=resume.consumer_context,consumer_spec=resume.consumer_spec,
                         consumer_inputs=resume.consumer_inputs,preserve_consumer_inputs=resume.preserve_consumer_inputs,
                         verify_consumer_inputs=resume.verify_consumer_inputs,consumer_inputs_reusable=resume.consumer_inputs_reusable)
        helpers = [n for n in source.body if isinstance(n,ast.FunctionDef)
                   and n.name in ('verify_retail_inputs','preserve_retail_cache','read_retail_cache','publish_retail_receipt')]
        exec(compile(ast.Module(body=[*helpers,function],type_ignores=[]),'<actual retail cache prefix>','exec'),namespace)
        fixture_context=synthetic_reference_profile(self.root,core)
        resume.publish_consumer_context(self.root,fixture_context)
        def invoke():
            synthetic_reference_profile(self.root,core)
            return namespace['retail_parity']('mock-host',lambda *a:['mock-native'],'PPZ_ROUTE',1,1,'A',script,out,1)
        invoke();invoke()
        self.assertEqual(len(calls),1)
        key = json.loads((out/'retail.key').read_text())
        self.assertIn('bios_inputs',key)
        self.assertEqual(key['core_sha256'],resume.digest(core))
        self.assertTrue(resume.valid_reference_input_seal(key['reference_inputs']))
        self.assertEqual(resume.read_reference_inputs(self.root,key['reference_inputs']),resume.reference_inputs(self.root))
        self.assertIn('execution_environment',key)
        self.assertEqual(key['execution_environment'],resume.execution_environment(keys=('SCD_DATA_ROOT',)))
        key.pop('bios_inputs')
        (out/'retail.key').write_text(json.dumps(key,sort_keys=True))
        legacy_key = (out/'retail.key').read_bytes()
        invoke();self.assertEqual(len(calls),2)
        self.write(BIOS_NAMES[0], 'new-fixture-BIOS')
        invoke();self.assertEqual(len(calls),3)
        core.write_text('changed tiny synthetic core')
        invoke();self.assertEqual(len(calls),4)
        self.assertTrue(any(p.read_bytes()==legacy_key for p in (out/'retail-history').glob('*/retail.key')))
        self.assertTrue(all(p.read_text()=='synthetic rows, not executed' for p in (out/'retail-history').glob('*/retail.rows')))
        count=len(calls)
        with patch.dict(os.environ,{'SCD_DATA_ROOT':'first-synthetic-source'}):
            invoke();invoke();self.assertEqual(len(calls),count+2)  # Alternate inputs are always uncached.
            os.environ['SCD_DATA_ROOT']='second-synthetic-source'
            invoke();self.assertEqual(len(calls),count+3)
            change[0]='environment';os.environ['SCD_DATA_ROOT']='third-synthetic-source'
            with self.assertRaisesRegex(ValueError,'environment changed'):invoke()
            self.assertFalse((out/'retail.key').exists())
        self.write(BIOS_NAMES[0], 'next-fixture-BIOS');change[0]=True
        with self.assertRaisesRegex(ValueError,'BIOS inputs changed'):
            invoke()
        self.assertFalse((out/'retail.key').exists())
        change[0]='core'
        with self.assertRaisesRegex(ValueError,'Retail core changed'):
            invoke()
        self.assertFalse((out/'retail.key').exists())

        change[0]=False;count=len(calls)
        invoke();invoke();self.assertEqual(len(calls),count+1)
        self.write('build/audit/source/src/R1/COLI1.C','new reference before capture')
        invoke();self.assertEqual(len(calls),count+2)
        self.write('build/audit/source/src/R1/COLI1.C','next reference before capture');change[0]='reference'
        with self.assertRaisesRegex(ValueError,'Reference inputs changed'):invoke()
        self.assertFalse((out/'retail.key').exists())


class ExecutionEnvironment(unittest.TestCase):
    setUp = Recovery.setUp
    write = Recovery.write
    checkpoint = Recovery.checkpoint
    choices = Recovery.choices
    window = Recovery.window

    def seal(self):
        import hashlib
        return {key:(dict(present=True,sha256=hashlib.sha256(os.environ[key].encode()).hexdigest())
                     if key in os.environ else dict(present=False)) for key in ENVIRONMENT_NAMES}

    def test_changed_override_rejects_modern_bios_sealed_step(self):
        cases=[('SS_CFLAGS','test-ss-actors.sh'),('MM_CFLAGS','test-mm-actors.sh'),
               ('QQ_CFLAGS','test-qq-actors.sh'),('WW_CFLAGS','test-ww-actors.sh'),
               ('TT_EXTRA','test-tt-actors.sh'),('SCD_DATA_ROOT','test-sonic-view.sh'),
               ('TT_BG_WRITE_LIMIT','test-tt-cache-replay.sh')]
        for key,script in cases:
            self.commands=[['bash','tools/'+script]]
            path,data=self.checkpoint()
            self.assertEqual(set(self.choices(path)),{0})
            with self.subTest(key=key),patch.dict(os.environ,{key:'synthetic-changed-setting'}):
                self.assertEqual(self.choices(path),{})

    def test_matched_scope_filter_cannot_bless_canonical_whole(self):
        self.commands=[['bash','tools/test-save.sh']]
        for key in ('MM_ONLY','SS_ONLY','WW_ONLY'):
            for value in ('','synthetic-filter'):
                with self.subTest(key=key,value=value),patch.dict(os.environ,{key:value}):
                    path,data=self.checkpoint()
                    data['steps'][0]['execution_environment']=self.seal()
                    path.write_text(json.dumps(data))
                    self.assertEqual(self.choices(path),{})
                    report=dict(mode='full',status='passed',passed=True,bios_inputs=copy.deepcopy(EMPTY_BIOS),
                                execution_environment=self.seal())
                    with self.assertRaisesRegex(ValueError,'scope filters'):
                        resume.checkpoint_bios_inputs(self.root,report,lambda:None)
                    self.assertFalse(report['passed'])
                    self.assertEqual(report['status'],'failed')

    def test_present_empty_and_value_are_hashed_without_raw_value(self):
        import hashlib
        self.assertEqual(resume.execution_environment(),EMPTY_ENVIRONMENT)
        for value in ('','synthetic-nonsecret-override'):
            with patch.dict(os.environ,{'SS_CFLAGS':value}):
                seal=resume.execution_environment()
                self.assertEqual(seal['SS_CFLAGS'],dict(present=True,sha256=hashlib.sha256(value.encode()).hexdigest()))
                if value:self.assertNotIn(value,json.dumps(seal))
                self.assertNotEqual(seal,EMPTY_ENVIRONMENT)
                resume.verify_execution_environment(seal)
        self.assertEqual(resume.execution_environment(),EMPTY_ENVIRONMENT)

    def test_environment_shape_is_strict(self):
        values=[None,{}, {**EMPTY_ENVIRONMENT,'unknown':dict(present=False)},
                {**EMPTY_ENVIRONMENT,'SS_CFLAGS':dict(present=0)},
                {**EMPTY_ENVIRONMENT,'SS_CFLAGS':dict(present=False,sha256='a'*64)},
                {**EMPTY_ENVIRONMENT,'SS_CFLAGS':dict(present=True,sha256=False)},
                {**EMPTY_ENVIRONMENT,'SS_CFLAGS':dict(present=True,sha256='bad')},
                {**EMPTY_ENVIRONMENT,'SS_CFLAGS':dict(present=True,sha256='a'*64,value='do-not-record')}]
        for value in values:
            with self.subTest(value=value):
                self.assertFalse(resume.valid_execution_environment(value))
                with self.assertRaises(ValueError):resume.verify_execution_environment(value)

    def test_missing_historical_flags_are_not_defaults(self):
        for command,expected in ((['bash','tools/test-ss-actors.sh'],set()),
                                 (['bash','tools/test-sonic-view.sh'],set()),
                                 (['bash','tools/test-tt-cache-replay.sh'],set()),
                                 (['unknown-host'],set()),
                                 (['bash','tools/test-save.sh'],{0}),
                                 (['python3','tools/test_title_cycles.py'],{0})):
            self.commands=[command];path,data=self.checkpoint()
            del data['steps'][0]['execution_environment']
            path.write_text(json.dumps(data))
            with self.subTest(command=command):self.assertEqual(set(self.choices(path)),expected)

    def test_known_independence_is_per_command_not_an_environment_default(self):
        recorded=copy.deepcopy(EMPTY_ENVIRONMENT)
        with patch.dict(os.environ,{'SS_CFLAGS':'synthetic-flags'}):
            current=resume.execution_environment()
            self.assertTrue(resume.execution_environment_reusable(recorded,current,['bash','tools/test-save.sh']))
            self.assertFalse(resume.execution_environment_reusable(recorded,current,['bash','tools/test-ss-actors.sh']))
            self.assertFalse(resume.execution_environment_reusable(recorded,current,['unknown-host']))
            self.assertTrue(resume.execution_environment_reusable(current,current,['unknown-host']))
        self.assertFalse(resume.execution_environment_reusable(None,recorded,['bash','tools/test-save.sh','--other']))

    def test_matrix_requires_environment_seal_and_matching_current_value(self):
        base,window,entry=self.window()
        self.assertTrue(resume.cached_window(self.root,base,window,entry,'same-bin'))
        with patch.dict(os.environ,{'SS_CFLAGS':'synthetic-flag'}):
            self.assertFalse(resume.cached_window(self.root,base,window,entry,'same-bin'))
            entry['execution_environment']=resume.execution_environment()
            self.assertTrue(resume.cached_window(self.root,base,window,entry,'same-bin'))
        del entry['execution_environment']
        with patch.object(resume,'bios_inputs',side_effect=AssertionError('unsealed firmware must not be read')):
            self.assertFalse(resume.cached_window(self.root,base,window,entry,'same-bin'))

    def test_actual_suite_loop_environment_change_fails_before_or_after_child(self):
        import ast,contextlib,io,hashlib
        source=ast.parse((ROOT/'tools/qa-loop.py').read_text())
        loop=next(n for n in source.body if isinstance(n,ast.For) and isinstance(n.iter,ast.Call)
                  and isinstance(n.iter.func,ast.Name) and n.iter.func.id=='enumerate'
                  and n.iter.args and isinstance(n.iter.args[0],ast.Name) and n.iter.args[0].id=='selected')
        previous=source.body[source.body.index(loop)-1]
        for at in ('cooldown','child'):
            folder=self.root/at;folder.mkdir();calls=[]
            report=dict(mode='fast',status='pending',passed=False,steps=[],bios_inputs=copy.deepcopy(EMPTY_BIOS),execution_environment=self.seal(),checkpoint_context=dict(protocol=1))
            def mutate():os.environ['SS_CFLAGS']='synthetic-late-change'
            def cool(*args,**kwargs):
                if at=='cooldown':mutate()
            def run(*args,**kwargs):
                calls.append(args[0]);kwargs['stdout'].write('PASS: synthetic child\n');mutate()
                return types.SimpleNamespace(returncode=0)
            namespace=dict(ROOT=self.root,out=folder,report=report,qa_resume=resume,prefix_cache={},selected=[['mock-command']],
                start_step=0,session_limits=dict(cooldown_seconds=120),suite_mode='fast',
                time=types.SimpleNamespace(monotonic=lambda:0),cooldown=cool,
                subprocess=types.SimpleNamespace(run=run,STDOUT=-2),_sync_file=lambda fd:None,
                atomic_json=lambda p,r:p.write_text(json.dumps(r)),hashlib=hashlib,json=json)
            with self.subTest(at=at),contextlib.redirect_stdout(io.StringIO()),self.assertRaisesRegex(ValueError,'environment changed'):
                exec(compile(ast.Module(body=[previous,loop],type_ignores=[]),'<actual suite environment checks>','exec'),namespace)
            saved=json.loads((folder/'report.json').read_text())
            self.assertFalse(saved['passed']);self.assertEqual(saved['status'],'failed');self.assertEqual(saved['steps'],[])
            self.assertEqual(len(calls),0 if at=='cooldown' else 1)
            os.environ.pop('SS_CFLAGS')

    def test_actual_matrix_executor_checks_environment_after_cooldown_and_child(self):
        import ast,threading
        source=ast.parse((ROOT/'tools/zone-gates.py').read_text())
        function=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='execute')
        for at in ('cooldown','child'):
            folder=self.root/at;folder.mkdir();calls=[];environment=self.seal()
            def mutate():os.environ['TT_EXTRA']='synthetic-late-change'
            def cool(*args,**kwargs):
                if at=='cooldown':mutate()
            def run(*args,**kwargs):
                calls.append(args[0]);mutate();return types.SimpleNamespace(returncode=0)
            namespace=dict(ROOT=self.root,os=os,time=types.SimpleNamespace(time=lambda:0,monotonic=lambda:0),
                cooldown=cool,subprocess=types.SimpleNamespace(run=run,STDOUT=-2,TimeoutExpired=TimeoutError),
                _sync_file=lambda fd:None,json=json,shutil=types.SimpleNamespace())
            exec(compile(ast.Module(body=[function],type_ignores=[]),'<actual matrix environment checks>','exec'),namespace)
            job=types.SimpleNamespace(key=('fixture',),out=None,cmds=[['mock-command']],env={},report=None)
            with self.subTest(at=at),self.assertRaisesRegex(ValueError,'environment changed'):
                namespace['execute'](job,folder,10,threading.Lock(),dict(last_finished=0,seconds=120),
                    input_check=lambda:resume.verify_execution_inputs(self.root,EMPTY_BIOS,environment))
            self.assertEqual(len(calls),0 if at=='cooldown' else 1)
            self.assertFalse(hasattr(job,'result'));os.environ.pop('TT_EXTRA')


class ReferenceContext(unittest.TestCase):
    setUp = Recovery.setUp
    write = Recovery.write
    checkpoint = Recovery.checkpoint
    choices = Recovery.choices
    window = Recovery.window

    def references(self):
        return resume.preserve_reference_inputs(self.root,resume.reference_inputs(self.root))

    def test_changed_ignored_reference_rejects_previously_passing_step(self):
        self.commands = [['bash','tools/test-chain-score.sh']]
        reference = self.write('build/audit/source/src/R1/COLI1.C','synthetic original scoring input')
        path,data = self.checkpoint()
        self.assertEqual(set(self.choices(path)),{0})
        reference.write_text('synthetic changed scoring input')
        self.assertEqual(self.choices(path),{})

    def test_missing_seal_denies_reference_dependent_and_unknown_commands(self):
        for command in (['bash','tools/test-chain-score.sh'],['bash','tools/test-player.sh'],
                        ['bash','tools/test-world.sh'],['unknown-host']):
            self.commands=[command];path,data=self.checkpoint()
            del data['steps'][0]['reference_inputs'];path.write_text(json.dumps(data))
            with self.subTest(command=command):self.assertEqual(self.choices(path),{})

    def test_missing_reference_seal_retains_only_exact_audited_independent_command(self):
        for command in (['bash','tools/test-save.sh'],['bash','tools/test-time-attack.sh'],
                        ['python3','tools/test_sprite_priority.py'],
                        ['python3','tools/test_world_restart.py'],['python3','tools/test_qq_switch_margin.py'],
                        ['python3','tools/test_candidate_identity.py'],['python3','tools/test_title_cycles.py']):
            self.commands=[command];path,data=self.checkpoint();del data['steps'][0]['reference_inputs']
            path.write_text(json.dumps(data));self.assertEqual(set(self.choices(path)),{0})
            self.commands=[[*command,'--other']];path,data=self.checkpoint();del data['steps'][0]['reference_inputs']
            path.write_text(json.dumps(data));self.assertEqual(self.choices(path),{})

    def test_reference_root_presence_inventory_and_all_three_root_changes(self):
        absent=resume.reference_inputs(self.root);self.assertTrue(resume.valid_reference_inputs(absent))
        for name in resume.REFERENCE_ROOTS:
            directory=self.root/name;directory.mkdir(parents=True,exist_ok=True)
            empty=self.references();self.assertNotEqual(resume.reference_input_seal(absent),empty)
            leaf=directory/'fixture.C';leaf.write_text('one');before=self.references()
            resume.verify_reference_inputs(self.root,before)
            leaf.write_text('two')
            with self.assertRaisesRegex(ValueError,'Reference inputs changed'):resume.verify_reference_inputs(self.root,before)
            after=self.references();self.assertNotEqual(before,after)
            extra=directory/'extra.h';extra.write_text('new')
            with self.assertRaises(ValueError):resume.verify_reference_inputs(self.root,after)
            extra.unlink();leaf.unlink()
            with self.assertRaises(ValueError):resume.verify_reference_inputs(self.root,after)

    def test_reference_snapshot_tamper_missing_alias_and_strict_types(self):
        seal=self.references();manifest=self.root/seal['path'];raw=manifest.read_bytes()
        self.assertEqual(resume.read_reference_inputs(self.root,seal),resume.reference_inputs(self.root))
        for bad in (None,{},dict(seal,protocol=True),dict(seal,path='../escape.json'),dict(seal,sha256='x')):
            self.assertFalse(resume.valid_reference_input_seal(bad))
            with self.assertRaises(ValueError):resume.read_reference_inputs(self.root,bad)
        value=resume.reference_inputs(self.root)
        for bad in (dict(value,protocol=True),dict(value,roots={}),dict(value,extra=True)):
            self.assertFalse(resume.valid_reference_inputs(bad))
        manifest.write_bytes(raw+b' ')
        with self.assertRaises(ValueError):resume.read_reference_inputs(self.root,seal)
        manifest.unlink()
        with self.assertRaises(FileNotFoundError):resume.read_reference_inputs(self.root,seal)
        manifest.mkdir()
        with self.assertRaisesRegex(ValueError,'not regular'):resume.read_reference_inputs(self.root,seal)
        manifest.rmdir()
        alternate=self.write('other.json',raw.decode());manifest.symlink_to(alternate)
        with self.assertRaises(ValueError):resume.read_reference_inputs(self.root,seal)

    def test_snapshot_publisher_refuses_parent_alias_before_creating_output(self):
        value=resume.reference_inputs(self.root);build=self.root/'build';build.mkdir(exist_ok=True)
        elsewhere=self.root/'elsewhere';elsewhere.mkdir();(build/'qa-reference-inputs').symlink_to(elsewhere,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'alias'):resume.preserve_reference_inputs(self.root,value)
        self.assertEqual(list(elsewhere.iterdir()),[])

    def test_selected_reference_symlinks_and_mid_hash_changes_reject(self):
        path=self.write('build/probe-source/fixture.inc','one')
        alias=path.with_name('alias.c');alias.symlink_to(path)
        with self.assertRaises(ValueError):resume.reference_inputs(self.root)
        alias.unlink();real=resume.digest
        def changing(p):
            sha=real(p)
            if Path(p)==path:path.write_text('changed while hashing')
            return sha
        with patch.object(resume,'digest',side_effect=changing),self.assertRaises(ValueError):resume.reference_inputs(self.root)

    def test_snapshot_is_saved_once_and_rows_remain_compact(self):
        first=self.references();path=self.root/first['path'];stamp=path.stat().st_mtime_ns
        self.assertEqual(self.references(),first);self.assertEqual(path.stat().st_mtime_ns,stamp)
        self.assertLess(len(json.dumps(first)),300)
        self.assertEqual(set(first),{'protocol','path','sha256'})

    def test_reference_failure_finalizes_whole_pass_and_preserves_primary(self):
        reference=self.write('build/audit/source/src/R1/COLI1.C','one');seal=self.references()
        report=dict(status='passed',passed=True,bios_inputs=resume.bios_inputs(self.root),reference_inputs=seal)
        reference.write_text('two');saved=[]
        with self.assertRaises(ValueError):resume.checkpoint_bios_inputs(self.root,report,lambda:saved.append(copy.deepcopy(report)))
        self.assertEqual(report['status'],'failed');self.assertFalse(saved[0]['passed'])
        def failed_save():raise OSError('synthetic checkpoint fault')
        with self.assertRaisesRegex(ValueError,'Reference inputs changed'):
            resume.checkpoint_bios_inputs(self.root,report,failed_save)

    def test_matrix_requires_valid_current_reference_snapshot(self):
        path=self.write('build/probe-source/fixture.c','one');base,window,entry=self.window()
        self.assertTrue(resume.cached_window(self.root,base,window,entry,'same-bin'))
        del entry['reference_inputs'];self.assertFalse(resume.cached_window(self.root,base,window,entry,'same-bin'))
        entry['reference_inputs']=self.references();path.write_text('two')
        self.assertFalse(resume.cached_window(self.root,base,window,entry,'same-bin'))

    def test_reference_checks_surround_actual_matrix_child_after_cooling(self):
        import ast,threading
        tree=ast.parse((ROOT/'tools/zone-gates.py').read_text())
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='execute')
        for at in ('cooldown','child'):
            path=self.write('build/probe-source/fixture.c','one');seal=self.references();calls=[]
            folder=self.root/('reference-'+at);folder.mkdir()
            def mutate():path.write_text('two')
            def cool(*a,**k):
                if at=='cooldown':mutate()
            def run(*a,**k):calls.append(a[0]);mutate();return types.SimpleNamespace(returncode=0)
            namespace=dict(ROOT=self.root,os=os,time=types.SimpleNamespace(time=lambda:0,monotonic=lambda:0),
                cooldown=cool,subprocess=types.SimpleNamespace(run=run,STDOUT=-2,TimeoutExpired=TimeoutError),
                _sync_file=lambda fd:None,json=json,shutil=types.SimpleNamespace())
            exec(compile(ast.Module(body=[function],type_ignores=[]),'<actual matrix reference boundaries>','exec'),namespace)
            job=types.SimpleNamespace(key=('fixture',),out=None,cmds=[['mock-command']],env={},report=None)
            with self.assertRaisesRegex(ValueError,'Reference inputs changed'):
                namespace['execute'](job,folder,10,threading.Lock(),dict(last_finished=0,seconds=120),
                    input_check=lambda:resume.verify_execution_inputs(self.root,EMPTY_BIOS,EMPTY_ENVIRONMENT,seal))
            self.assertEqual(len(calls),0 if at=='cooldown' else 1);self.assertFalse(hasattr(job,'result'))

    def test_suite_reference_boundaries_after_cooling_and_child(self):
        import ast,hashlib,contextlib,io
        tree=ast.parse((ROOT/'tools/qa-loop.py').read_text())
        loop=next(n for n in tree.body if isinstance(n,ast.For) and isinstance(n.target,ast.Tuple)
                  and [getattr(x,'id',None) for x in n.target.elts]==['n','cmd'])
        previous=ast.parse('last_job_finished=0').body[0]
        for at in ('cooldown','child'):
            path=self.write('build/probe-source/fixture.c','one');seal=self.references();calls=[]
            folder=self.root/('suite-reference-'+at);folder.mkdir()
            report=dict(mode='fast',status='pending',passed=False,steps=[],bios_inputs=resume.bios_inputs(self.root),
                        execution_environment=resume.execution_environment(),reference_inputs=seal,checkpoint_context=dict(protocol=1))
            def cool(*a,**k):
                if at=='cooldown':path.write_text('two')
            def run(*a,**k):calls.append(a[0]);path.write_text('two');return types.SimpleNamespace(returncode=0)
            namespace=dict(ROOT=self.root,out=folder,report=report,qa_resume=resume,prefix_cache={},
                selected=[['mock-command']],start_step=0,session_limits=dict(cooldown_seconds=120),
                suite_mode='fast',time=types.SimpleNamespace(monotonic=lambda:0),cooldown=cool,
                subprocess=types.SimpleNamespace(run=run,STDOUT=-2),_sync_file=lambda fd:None,
                atomic_json=lambda p,v:p.write_text(json.dumps(v)),hashlib=hashlib,json=json)
            with contextlib.redirect_stdout(io.StringIO()),self.assertRaisesRegex(ValueError,'Reference inputs changed'):
                exec(compile(ast.Module(body=[previous,loop],type_ignores=[]),'<actual suite reference boundaries>','exec'),namespace)
            saved=json.loads((folder/'report.json').read_text());self.assertFalse(saved['passed'])
            self.assertEqual(saved['status'],'failed');self.assertEqual(saved['steps'],[])
            self.assertEqual(len(calls),0 if at=='cooldown' else 1)

    def test_matrix_reuses_fresh_caller_reference_capture_without_recapturing_per_window(self):
        base,window,entry=self.window()
        seal=entry['reference_inputs']
        with patch.object(resume,'reference_inputs',side_effect=AssertionError('unexpected repeated25MB scan')):
            self.assertTrue(resume.cached_window(self.root,base,window,entry,'same-bin',current_references=seal))
        self.assertFalse(resume.cached_window(self.root,base,window,entry,'same-bin',current_references={}))

    def test_modern_and_legacy_unclassified_commands_and_feedback_always_rerun(self):
        for command in (['python3','tools/test_feedback.py'],['unknown-host'],
                        ['python3','tools/test_frontend_emulator.py'],
                        ['python3','tools/prepare_audio.py'],
                        matrix_command(('ppz',),False),
                        [*matrix_command(ZONES,True),'--jobs','1','--windows','PPZ1A'],
                        ['bash','tools/test-save.sh','--extra']):
            log=self.write('classification.log','PASS: synthetic')
            for legacy in (False,True):
                step=dict(command=command,exit_code=0,log=str(log),log_sha256=resume.digest(log),
                          bios_inputs=resume.bios_inputs(self.root),execution_environment=resume.execution_environment(),
                          reference_inputs=self.references())
                if legacy:step.pop('reference_inputs')
                data=dict(mode='fast',checkpoint_context=self.ctx,source_sha256=self.inputs,steps=[step])
                path=self.write('classification.json',data)
                with self.subTest(command=command,legacy=legacy):
                    self.assertEqual(resume.cached_steps(self.root,'fast',[command],self.ctx,[path])[0],{})
        self.assertTrue(resume.input_integrity_command(['python3','tools/test_feedback.py']))
        self.assertFalse(resume.cacheable_command(['python3','tools/test_feedback.py']))
        self.assertTrue(resume.cacheable_command(['bash','tools/test-save.sh']))
        self.assertTrue(resume.cacheable_command([*matrix_command(ZONES,True),'--jobs','1']))

    def test_expanded_native_data_and_fixed_inputs_reject_actual_file_changes(self):
        names=('assets/generated/fixture.bin','assets/generated/fixture.h',
               'assets/generated/manifest.json','.deps/scddisasm/src/fixture.asm',
               '.deps/scddisasm/src/reference.bin','build/retail/sonic.iso',
               'dist/sonic-cd-saturn-prototype.cue')
        self.commands=[['bash','tools/test-chain-score.sh']]
        for name in names:
            leaf=self.write(name,'tiny synthetic first input');path,data=self.checkpoint()
            self.assertEqual(set(self.choices(path)),{0})
            leaf.write_text('tiny synthetic second input')
            with self.subTest(path=name):
                self.assertEqual(self.choices(path),{})
                with self.assertRaises(ValueError):resume.verify_reference_inputs(self.root,data['steps'][0]['reference_inputs'])
        before=self.references();self.write('assets/generated/music1.raw','unmodelled loose audio')
        self.assertEqual(self.references(),before)  # Unclassified audio jobs cannot reuse.
        value=resume.reference_inputs(self.root)
        for bad in (dict(value,fixed_files={}),dict(value,fixed_files={**value['fixed_files'],
                'build/retail/sonic.iso':dict(present=1)})):
            self.assertFalse(resume.valid_reference_inputs(bad))
        iso=self.root/'build/retail/sonic.iso';seal=self.references();iso.unlink()
        with self.assertRaises(ValueError):resume.verify_reference_inputs(self.root,seal)
        iso.symlink_to(self.root/'classification.log')
        with self.assertRaises(ValueError):resume.reference_inputs(self.root)

    def test_missing_build_parent_cannot_be_recreated_by_snapshot_publication(self):
        value=resume.reference_inputs(self.root);build=self.root/'build';build.rmdir()
        with self.assertRaises(FileNotFoundError):resume.preserve_reference_inputs(self.root,value)
        self.assertFalse(build.exists())
        missing=self.root/'absent-repository'
        with self.assertRaises(ValueError):resume.preserve_reference_inputs(missing,value)
        self.assertFalse(missing.exists())

    def test_unchanged_alternate_selector_disables_step_window_and_retail_reuse(self):
        self.commands=[['bash','tools/test-save.sh']];path,data=self.checkpoint();base,window,entry=self.window()
        alternate=self.root/'alternate';(alternate/'src').mkdir(parents=True);leaf=alternate/'src/reference.asm';leaf.write_text('one')
        with patch.dict(os.environ,{'SCD_DATA_ROOT':str(alternate)}):
            # All current seals match. The unsupported source selector alone forbids reuse.
            data['steps'][0]['execution_environment']=resume.execution_environment();path.write_text(json.dumps(data))
            entry['execution_environment']=resume.execution_environment()
            self.assertFalse(resume.reference_cache_allowed())
            self.assertEqual(self.choices(path),{})
            self.assertFalse(resume.cached_window(self.root,base,window,entry,'same-bin'))
            leaf.write_text('two')
            self.assertEqual(self.choices(path),{})
            self.assertFalse(resume.cached_window(self.root,base,window,entry,'same-bin'))
        with patch.dict(os.environ,{'SCD_DATA_ROOT':''}):
            self.assertTrue(resume.reference_cache_allowed())
        self.assertTrue(resume.reference_cache_allowed())

    def test_third_migration_preserves_all_ancestors_and_original_seals(self):
        inherited=dict(legacy_reports={'old':'seal'},legacy_matrices={},legacy_runtime={},
                       legacy_bin_sha256='same',legacy_limits={},legacy_toolchain={})
        a={'src/game.c':'same','tools/qa-loop.py':'A'};b={**a,'tools/qa-loop.py':'B'}
        c={**b,'tools/qa-loop.py':'C'};d={**c,'tools/qa-loop.py':'D'}
        m1=dict(inherited,protocol=1,before_inputs=a,after_inputs=b,changed_paths=['tools/qa-loop.py'])
        p1=self.write('M1.json',m1)
        m2=dict(inherited,protocol=1,before_inputs=b,after_inputs=c,changed_paths=['tools/qa-loop.py'],
                parent_migration=dict(path=str(p1),sha256=resume.digest(p1)))
        p2=self.write('M2.json',m2)
        m3=dict(inherited,protocol=1,before_inputs=c,after_inputs=d,changed_paths=['tools/qa-loop.py'],
                parent_migration=dict(path=str(p2),sha256=resume.digest(p2)))
        self.assertEqual(len(resume.migration_chain(m3)),3)
        for old in (a,b,c):self.assertTrue(resume.same_inputs(old,d,m3))
        for key,value in (('before_inputs',a),('legacy_reports',{}),('protocol',True)):
            bad=copy.deepcopy(m3);bad[key]=value
            with self.assertRaises(ValueError):resume.migration_chain(bad)
        m4=dict(m3,before_inputs=d,after_inputs={**d,'tools/qa-loop.py':'E'},
                parent_migration=dict(path=str(self.write('M3.json',m3)),sha256=resume.digest(self.root/'M3.json')))
        with self.assertRaises(ValueError):resume.migration_chain(m4)
        p1.write_text(json.dumps(dict(m1,legacy_reports={'changed':'seal'})))
        with self.assertRaises(ValueError):resume.migration_chain(m3)


class ConsumerClosure(unittest.TestCase):
    setUp=Recovery.setUp
    write=Recovery.write
    checkpoint=Recovery.checkpoint

    def observation(self,command):
        return resume.consumer_inputs(self.root,resume.consumer_spec(self.root,[command]),context=self.ctx)

    def test_all_seven_native_extra_groups_detect_actual_file_changes(self):
        groups=[(['bash','tools/test-tt-platforms.sh'],'build/auto-extract/4/objects42C.bin'),
                (['bash','tools/test-act-pacing.sh'],resume._LIBRETRO_HEADER),
                (['bash','tools/test-cd-status.sh'],resume._NATIVE_EXTRA['tools/test-cd-status.sh'][0]),
                (['bash','tools/test-cc-cache-replay.sh'],'build/cc2/controller/A/results.log'),
                (['bash','tools/test-sonic-view.sh'],'build/sonic-animation/expected-frames.bin'),
                (['bash','tools/test-cc-gandair.sh'],'build/cc1/traps/original.c'),
                (['bash','tools/test-cc-pocket.sh'],'build/retail/fm-driver.bin')]
        for command,name in groups:
            with self.subTest(command=command):
                if command==['bash','tools/test-cc-pocket.sh']:
                    driver=bytes.fromhex('f3f3ed5618')+b'v'*(8192-5)
                    self.write('build/retail/sonic.iso',driver.decode('latin1'))
                    # Preserve exact tiny binary fixture bytes, never real media.
                    (self.root/'build/retail/sonic.iso').write_bytes(driver)
                    path=self.write(name,'placeholder');path.write_bytes(driver)
                else:path=self.write(name,'initial fixture bytes')
                before=self.observation(command)
                self.assertTrue(before['complete'])
                seal=resume.preserve_consumer_inputs(self.root,before)
                self.assertTrue(resume.consumer_inputs_reusable(self.root,seal,before))
                path.write_text('changed fixture bytes')
                self.assertFalse(resume.consumer_inputs_reusable(self.root,seal,self.observation(command)))
                with self.assertRaises(ValueError):resume.verify_consumer_inputs(self.root,before)

    def test_legacy_extra_identity_never_filled_with_current_bytes(self):
        self.commands=[['bash','tools/test-tt-platforms.sh']]
        self.write('build/auto-extract/4/objects42C.bin','one')
        path,_=self.checkpoint();candidate=resume.cached_steps(self.root,'fast',self.commands,self.ctx,[path])[0][0]
        self.assertIsNone(resume.consume_cached_step(self.root,'fast',self.commands,self.ctx,candidate,0))
        self.commands=[['bash','tools/test-save.sh']]
        path,_=self.checkpoint();candidate=resume.cached_steps(self.root,'fast',self.commands,self.ctx,[path])[0][0]
        self.assertIsNotNone(resume.consume_cached_step(self.root,'fast',self.commands,self.ctx,candidate,0))

    def test_candidate_is_revalidated_at_consumption_after_earlier_producer(self):
        self.commands=[['bash','tools/test-tt-platforms.sh']]
        placement=self.write('build/auto-extract/4/objects42C.bin','one')
        path,data=self.checkpoint();data['steps'][0]['consumer_inputs']=resume.preserve_consumer_inputs(self.root,self.observation(self.commands[0]));path.write_text(json.dumps(data))
        candidate=resume.cached_steps(self.root,'fast',self.commands,self.ctx,[path])[0][0]
        self.assertIsNotNone(resume.consume_cached_step(self.root,'fast',self.commands,self.ctx,candidate,0))
        placement.write_text('earlier producer changed this after preselection')
        self.assertIsNone(resume.consume_cached_step(self.root,'fast',self.commands,self.ctx,candidate,0))
        path.write_text(json.dumps(dict(data,status='changed after preselection')))
        self.assertIsNone(resume.consume_cached_step(self.root,'fast',self.commands,self.ctx,candidate,0))

    def test_unrelated_mutable_output_does_not_invalidate_other_consumer(self):
        command=['bash','tools/test-time-attack.sh'];before=self.observation(command)
        seal=resume.preserve_consumer_inputs(self.root,before)
        self.write('build/cc2/controller/A/results.log','a later producer output')
        self.assertTrue(resume.consumer_inputs_reusable(self.root,seal,self.observation(command)))

    def test_stable_final_boundary_ignores_only_scoped_dynamic_outputs(self):
        dynamic=['bash','tools/test-cc-cache-replay.sh'];stable=['bash','tools/test-tt-platforms.sh']
        self.write('build/cc2/controller/A/results.log','one')
        placement=self.write('build/auto-extract/4/objects42C.bin','one')
        seals=[resume.preserve_consumer_inputs(self.root,self.observation(c)) for c in (dynamic,stable)]
        self.write('build/cc2/controller/A/results.log','legitimate later output')
        resume.verify_stable_consumer_inputs(self.root,seals)
        placement.write_text('stable source changed')
        with self.assertRaises(ValueError):resume.verify_stable_consumer_inputs(self.root,seals)

    def test_default_profile_real_guard_schema_retained_owned_and_missing_audit(self):
        core=self.write(resume.REFERENCE_CORE,'synthetic core')
        context=synthetic_reference_profile(self.root,core)
        value=resume.default_core_profile(self.root,runtime=context['runtime'],toolchain=context['toolchain'],current_core_sha=resume.digest(core))
        self.assertEqual(value['protocol'],1)
        cleanup=self.root/'build/synthetic-core/cleanup.json';body=json.loads(cleanup.read_text());body['audited_generations']=body['audited_generations'][:1];cleanup.write_text(json.dumps(body))
        with self.assertRaises(ValueError):resume.default_core_profile(self.root,runtime=context['runtime'],toolchain=context['toolchain'],current_core_sha=resume.digest(core))

    def test_reference_boot_iso_extracted_program_and_bram_boundaries(self):
        core=self.write(resume.REFERENCE_CORE,'synthetic core');context=synthetic_reference_profile(self.root,core)
        pad=self.write('pad.txt','1 0\n')
        spec=resume.consumer_spec(self.root,[['python3','tools/retail_probe.py','1','A',str(pad),'unused.rows','500','--native-unlock','1','--round','1']],retail=True)
        before=resume.consumer_inputs(self.root,spec,context=context);self.assertTrue(before['complete'],before['unsupported'])
        self.write('assets/private/scd_U.brm','changed saved-state bytes')
        with self.assertRaises(ValueError):resume.verify_consumer_inputs(self.root,before)
        before=resume.consumer_inputs(self.root,spec,context=context)
        self.write('build/retail/IPX___.MMD','wrong extracted body')
        changed=resume.consumer_inputs(self.root,spec,context=context)
        self.assertFalse(changed['complete']);self.assertTrue(any('program differs' in x for x in changed['unsupported']))
        synthetic_reference_profile(self.root,core)
        raw=self.root/'build/retail/sonic.bin';data=bytearray(raw.read_bytes());data[16]^=1;raw.write_bytes(data)
        changed=resume.consumer_inputs(self.root,spec,context=context)
        self.assertFalse(changed['complete']);self.assertTrue(any('boot media data differs' in x for x in changed['unsupported']))

    def test_cue_tracks_file_targets_presence_sidecar_and_alias_refusal(self):
        cue=self.write('media/test.cue','FILE "one.bin" BINARY\n TRACK 01 MODE1/2352\n INDEX 01 00:00:00\nFILE "two.bin" BINARY\n TRACK 02 AUDIO\n INDEX 01 00:00:00\n')
        self.write('media/one.bin','x'*2352);second=self.write('media/two.bin','y'*2352)
        graph=resume.cue_input_graph(self.root,str(cue),loader_profile='saturn-default-v1')
        self.assertEqual(len(graph['file_occurrences']),2);self.assertFalse(graph['files']['media/test.sbi']['present'])
        second.write_text('z'*2352)
        self.assertNotEqual(resume.cue_input_graph(self.root,str(cue),loader_profile='saturn-default-v1'),graph)
        second.unlink();second.symlink_to(self.root/'media/one.bin')
        with self.assertRaises(ValueError):resume.cue_input_graph(self.root,str(cue),loader_profile='saturn-default-v1')
        for text in ('FILE "../outside.bin" BINARY','FILE "/tmp/foreign.bin" BINARY','FILE "two.wav" WAVE'):
            cue.write_text(text)
            with self.assertRaises(ValueError):resume.cue_input_graph(self.root,str(cue),loader_profile='saturn-default-v1')

    def test_cue_explicit_pregap_preserves_virtual_time_and_media_identity(self):
        prefix='FILE "one.bin" BINARY\n TRACK 01 MODE1/2352\n INDEX 01 00:00:00\nFILE "two.bin" BINARY\n TRACK 02 AUDIO\n'
        cue=self.write('media/gap.cue',prefix+' PREGAP 00:02:00\n INDEX 01 00:00:00\n')
        self.write('media/one.bin','x'*2352);audio=self.write('media/two.bin','y'*2352)
        for profile in ('genesis-default-v1','saturn-default-v1'):
            with self.subTest(profile=profile):
                cue.write_text(prefix+' PREGAP 00:02:00\n INDEX 01 00:00:00\n')
                graph=resume.cue_input_graph(self.root,str(cue),loader_profile=profile)
                self.assertEqual(graph['tracks'][1]['pregap_frames'],150)
                self.assertEqual(graph['tracks'][1]['indices'],{'01':0})
                self.assertNotIn('pregap_frames',graph['tracks'][0])
                self.assertEqual(graph['file_occurrences'],['media/one.bin','media/two.bin'])
                self.assertEqual(graph['files']['media/two.bin']['sha256'],resume.digest(audio))
                # A virtual gap can exceed the tiny FILE body. It is not a file offset.
                cue.write_text(prefix+' PREGAP 00:03:00\n INDEX 01 00:00:00\n')
                changed=resume.cue_input_graph(self.root,str(cue),loader_profile=profile)
                self.assertEqual(changed['tracks'][1]['pregap_frames'],225)
                self.assertEqual(changed['files'],graph['files'])
                self.assertNotEqual(changed['descriptor']['sha256'],graph['descriptor']['sha256'])
                cue.write_text(prefix+' PREGAP 00:00:00\n INDEX 01 00:00:00\n')
                self.assertEqual(resume.cue_input_graph(self.root,str(cue),loader_profile=profile)['tracks'][1]['pregap_frames'],0)

    def test_cue_pregap_rejects_invalid_time_and_track_boundaries(self):
        first='FILE "one.bin" BINARY\n TRACK 01 MODE1/2352\n INDEX 01 00:00:00\n'
        prefix=first+'FILE "two.bin" BINARY\n TRACK 02 AUDIO\n'
        cue=self.write('media/gap.cue','');self.write('media/one.bin','x'*2352);self.write('media/two.bin','y'*2352)
        invalid=[prefix+' PREGAP '+time+'\n INDEX 01 00:00:00\n' for time in
                 ('00:60:00','00:02:75','-1:02:00','000:02:00','00:02','00:02:00 extra')]
        invalid += [
            'PREGAP 00:02:00\n'+first,
            'FILE "one.bin" BINARY\n PREGAP 00:02:00\n TRACK 01 MODE1/2352\n INDEX 01 00:00:00\n',
            prefix+' PREGAP 00:00:00\n PREGAP 00:02:00\n INDEX 01 00:00:00\n',
            prefix+' INDEX 00 00:00:00\n PREGAP 00:02:00\n INDEX 01 00:00:00\n',
            prefix+' INDEX 01 00:00:00\n PREGAP 00:02:00\n',
            first+'FILE "two.bin" BINARY\n PREGAP 00:02:00\n TRACK 02 AUDIO\n INDEX 01 00:00:00\n',
            first+'FILE "one.bin" BINARY\n PREGAP 00:02:00\n TRACK 02 AUDIO\n INDEX 01 00:00:00\n',
            prefix+' POSTGAP 00:02:00\n INDEX 01 00:00:00\n',
        ]
        for profile in ('genesis-default-v1','saturn-default-v1'):
            for number,text in enumerate(invalid):
                with self.subTest(profile=profile,case=number),self.assertRaises(ValueError):
                    cue.write_text(text);resume.cue_input_graph(self.root,str(cue),loader_profile=profile)

    def test_strict_consumer_snapshots_and_tampering(self):
        before=self.observation(['bash','tools/test-save.sh'])
        for key,value in (('protocol',True),('complete',1),('unsupported',[False]),('files',{'x':{'present':0}})):
            with self.subTest(key=key),self.assertRaises(ValueError):resume.consumer_input_seal(dict(before,**{key:value}))
        seal=resume.preserve_consumer_inputs(self.root,before)
        (self.root/seal['path']).write_text('{}')
        with self.assertRaises(ValueError):resume.read_consumer_inputs(self.root,seal)
        unknown=self.observation(['python3','tools/unknown_consumer.py'])
        self.assertFalse(unknown['complete'])

    def test_retail_receipt_rows_log_hashes_and_exact_types(self):
        import ast,hashlib
        source=ast.parse((ROOT/'tools/retail_parity.py').read_text())
        helpers=[n for n in source.body if isinstance(n,ast.FunctionDef) and n.name in ('read_retail_cache','publish_retail_receipt')]
        namespace=dict(json=json,hashlib=hashlib)
        exec(compile(ast.Module(body=helpers,type_ignores=[]),'<actual retail receipt helpers>','exec'),namespace)
        out=self.root/'retail';out.mkdir();key='{"synthetic":true}'
        self.write('retail/retail.key',key);rows=self.write('retail/retail.rows','approved rows');log=self.write('retail/retail.log','approved log')
        seal=resume.preserve_consumer_inputs(self.root,self.observation(['bash','tools/test-save.sh']))
        namespace['publish_retail_receipt'](out,key,seal,0)
        self.assertEqual(namespace['read_retail_cache'](out,key,seal),'approved rows')
        receipt=(out/'retail.receipt.json').read_text()
        for target in (rows,log):
            saved=target.read_bytes();target.write_text('changed body')
            self.assertIsNone(namespace['read_retail_cache'](out,key,seal));target.write_bytes(saved)
        data=json.loads(receipt);data['consumer_inputs']['protocol']=True
        (out/'retail.receipt.json').write_text(json.dumps(data))
        self.assertIsNone(namespace['read_retail_cache'](out,key,seal))

    def test_all_347_default_window_recipes_are_finite_not_unsupported(self):
        import ast,threading
        source=ast.parse((ROOT/'tools/zone-gates.py').read_text())
        definitions=[n for n in source.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in
                     ('Run','Window','build_matrix','parse_retail','parse_routes','parse_generic')]
        registry=json.loads((ROOT/'tests/special/gate-cases.json').read_text())
        self.write('tests/special/gate-cases.json',registry)
        for act,eras in ((1,'ABCD'),(2,'ABCD'),(3,'CD')):
            for era in eras:self.write('tests/routes/mm/mm%d%s.txt'%(act,era),'fixture source route')
        helper=(ROOT/'tools/zone_object_assets.py').read_text();node=next(n for n in ast.parse(helper).body if isinstance(n,ast.FunctionDef) and n.name=='source_paths')
        self.write('tools/zone_object_assets.py',ast.get_source_segment(helper,node)+'\n')
        namespace=dict(ROOT=self.root,Path=Path,json=json,re=__import__('re'),threading=threading,
            SPECIAL='sp',SPECIAL_GATE='special',SPECIAL_CASES=SPECIAL_CASES,
            SPECIAL_REGISTRY=self.root/'tests/special/gate-cases.json',
            ACT_ERAS=[(1,e) for e in 'ABCD']+[(2,e) for e in 'ABCD']+[(3,e) for e in 'CD'],
            ROUND={'ppz':1,'cc':3,'tt':4,'qq':5,'ww':6,'ss':7,'mm':8})
        exec(compile(ast.Module(body=definitions,type_ignores=[]),'<original matrix builders>','exec'),namespace)
        _,windows=namespace['build_matrix']([*ZONES,'sp'],['retail','routes','art','travel','campaign','special'],self.root/'build/matrix')
        self.assertEqual(len(windows),347)
        for window in windows:
            with self.subTest(case=(window.zone,window.gate,window.name)):
                self.assertIsNotNone(window.run)
                recipe=resume.consumer_spec(self.root,window.run.cmds,window=window)
                self.assertEqual(recipe['unsupported'],[])
                self.assertTrue(recipe['key']['case'])
                self.assertLessEqual(len(recipe['setup']),1)

    def test_exact_sibling_m3_and_optional_core_epoch_preserve_original_chain(self):
        inherited=dict(legacy_reports={'frozen':'same'},legacy_matrices={},legacy_runtime={},legacy_bin_sha256='same',legacy_limits={},legacy_toolchain={})
        names=sorted(resume.REFERENCE_UPGRADE_PATHS)
        a={name:'base' for name in names};a[resume.REFERENCE_CORE]='0'*64
        b={**a,'tools/qa-loop.py':'M1'};c={**b,'tools/qa_resume.py':'M2'}
        m1=dict(inherited,protocol=1,before_inputs=a,after_inputs=b,changed_paths=['tools/qa-loop.py'])
        p1=self.write('M1.json',m1)
        m2=dict(inherited,protocol=1,before_inputs=b,after_inputs=c,changed_paths=['tools/qa_resume.py'],parent_migration=dict(path=str(p1),sha256=resume.digest(p1)))
        p2=self.write('M2.json',m2);parent=dict(path=str(p2),sha256=resume.digest(p2))
        physical={};d=dict(c)
        for name in names:
            file=self.write('physical/'+Path(name).name,'physical M3 '+name)
            physical[name]=dict(snapshot=str(file),sha256=resume.digest(file));d[name]=resume.digest(file)
        sibling=dict(inherited,protocol=1,before_inputs=c,after_inputs=d,changed_paths=names,parent_migration=parent)
        p3=self.write('old-M3.json',sibling)
        after={**d,'tools/qa_resume.py':'closure code'}
        migration=dict(inherited,protocol=1,input_closure_protocol=1,before_inputs=c,after_inputs=after,
                       changed_paths=sorted(name for name in c if c[name]!=after[name]),parent_migration=parent,
                       reference_sibling=dict(path=str(p3),sha256=resume.digest(p3)),physical_before=physical)
        self.assertEqual(len(resume.migration_chain(migration)),3)
        self.assertTrue(resume.same_inputs(d,after,migration))
        profile=self.write('profile.json',dict(protocol=1,build=dict(path='synthetic-only',sha256='a'*64),
                                              approval=dict(path='synthetic-only',sha256='b'*64)))
        changed=copy.deepcopy(migration);changed['after_inputs'][resume.REFERENCE_CORE]='1'*64
        changed['changed_paths'].append(resume.REFERENCE_CORE)
        changed['core_epoch']=dict(path=resume.REFERENCE_CORE,before_sha256='0'*64,after_sha256='1'*64,
                                   profile=dict(path=str(profile),sha256=resume.digest(profile)))
        self.assertEqual(len(resume.migration_chain(changed)),3)
        bad=copy.deepcopy(changed);bad['core_epoch']['path']='unapproved/other-core'
        with self.assertRaises(ValueError):resume.migration_chain(bad)
        bad=copy.deepcopy(migration);bad['physical_before'][names[0]]['sha256']='f'*64
        with self.assertRaises(ValueError):resume.migration_chain(bad)
        p3.write_text('{}')
        self.assertFalse(resume.same_inputs(d,after,migration))

    def test_actual_window_consumer_rejects_changed_header_and_cue_target_after_candidate(self):
        self.write('dist/sonic-cd-saturn-prototype.cue','FILE "native.bin" BINARY\n TRACK 01 MODE1/2352\n INDEX 01 00:00:00\n')
        media=self.write('dist/native.bin','n'*2352);header=self.write(resume._LIBRETRO_HEADER,'fixture header')
        base,window,entry=Recovery.window(self)
        window.run=types.SimpleNamespace(cmds=[['python3','tools/test_ppz_route.py','--act','1','--era','A','--no-retail']],out=None)
        observed=resume.consumer_inputs(self.root,resume.consumer_spec(self.root,window.run.cmds,window=window),context=self.ctx)
        self.assertTrue(observed['complete']);entry['consumer_inputs']=resume.preserve_consumer_inputs(self.root,observed)
        self.assertIsNotNone(resume.consume_cached_window(self.root,base,window,entry,'same-bin',self.ctx))
        header.write_text('changed after candidate selection')
        self.assertTrue(resume.cached_window(self.root,base,window,entry,'same-bin'))
        self.assertIsNone(resume.consume_cached_window(self.root,base,window,entry,'same-bin',self.ctx))
        header.write_text('fixture header');media.write_text('z'*2352)
        self.assertIsNone(resume.consume_cached_window(self.root,base,window,entry,'same-bin',self.ctx))

    def test_retail_hit_uses_the_same_single_rows_buffer_for_hash_and_parser(self):
        import ast,hashlib
        source=ast.parse((ROOT/'tools/retail_parity.py').read_text())
        fn=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='read_retail_cache')
        namespace=dict(json=json,hashlib=hashlib);exec(compile(ast.Module(body=[fn],type_ignores=[]),'<actual retail receipt reader>','exec'),namespace)
        key='approved key';rows=b'approved rows';log=b'approved log';seal=dict(protocol=1,path='fixture',sha256='f'*64)
        receipt=dict(protocol=1,key_sha256=hashlib.sha256(key.encode()).hexdigest(),consumer_inputs=seal,
                     rows=dict(size=len(rows),sha256=hashlib.sha256(rows).hexdigest()),
                     log=dict(size=len(log),sha256=hashlib.sha256(log).hexdigest()),exit_code=0)
        buffers={'retail.key':key.encode(),'retail.rows':rows,'retail.log':log,'retail.receipt.json':json.dumps(receipt).encode()}
        counts={name:0 for name in buffers}
        class ChangingFile:
            def __init__(self,name):self.name=name
            def read_bytes(self):
                counts[self.name]+=1
                return buffers[self.name] if counts[self.name]==1 else b'changed after approved read'
        class Output:
            def __truediv__(self,name):return ChangingFile(name)
        self.assertEqual(namespace['read_retail_cache'](Output(),key,seal),'approved rows')
        self.assertTrue(all(value==1 for value in counts.values()))

    def test_outer_reuse_precedes_cooling_but_runtime_group_still_cools_first(self):
        import ast
        loop=ast.parse((ROOT/'tools/qa-loop.py').read_text())
        outer=next(n for n in loop.body if isinstance(n,ast.For) and isinstance(n.target,ast.Tuple) and [getattr(x,'id',None) for x in n.target.elts]==['n','cmd'])
        calls=[n for n in ast.walk(outer) if isinstance(n,ast.Call)]
        cool=min(n.lineno for n in calls if isinstance(n.func,ast.Name) and n.func.id=='cooldown')
        use=min(n.lineno for n in calls if isinstance(n.func,ast.Attribute) and n.func.attr=='consume_cached_step')
        self.assertLess(use,cool)
        zone=ast.parse((ROOT/'tools/zone-gates.py').read_text())
        group=next(n for n in ast.walk(zone) if isinstance(n,ast.FunctionDef) and n.name=='run_group')
        calls=[n for n in ast.walk(group) if isinstance(n,ast.Call)]
        cool=min(n.lineno for n in calls if isinstance(n.func,ast.Name) and n.func.id=='cooldown')
        use=min(n.lineno for n in calls if isinstance(n.func,ast.Attribute) and n.func.attr=='consume_cached_window')
        execute=min(n.lineno for n in calls if isinstance(n.func,ast.Name) and n.func.id=='execute')
        self.assertLess(cool,use);self.assertLess(use,execute)

    def test_cached_producer_requires_its_actual_unchanged_output_receipt(self):
        self.commands=[['bash','tools/test-sonic-animation.sh']]
        output=self.write('build/sonic-animation/expected-frames.bin','produced frames')
        path,data=self.checkpoint();data['steps'][0]['consumer_inputs']=resume.preserve_consumer_inputs(self.root,self.observation(self.commands[0]))
        path.write_text(json.dumps(data));candidate=resume.cached_steps(self.root,'fast',self.commands,self.ctx,[path])[0][0]
        self.assertIsNone(resume.consume_cached_step(self.root,'fast',self.commands,self.ctx,candidate,0))
        data['steps'][0]['producer_outputs']=resume.producer_outputs(self.root,self.commands[0]);path.write_text(json.dumps(data))
        candidate=resume.cached_steps(self.root,'fast',self.commands,self.ctx,[path])[0][0]
        self.assertIsNotNone(resume.consume_cached_step(self.root,'fast',self.commands,self.ctx,candidate,0))
        output.write_text('stale changed generated frames')
        self.assertIsNone(resume.consume_cached_step(self.root,'fast',self.commands,self.ctx,candidate,0))

    def art_fixture(self,program='R83C-fight'):
        import ast,hashlib
        def definitions(path,functions,constants):
            source=path.read_text();nodes=[n for n in ast.parse(source).body if
                isinstance(n,ast.FunctionDef) and n.name in functions or isinstance(n,ast.Assign) and
                any(isinstance(t,ast.Name) and t.id in constants for t in n.targets)]
            return '\n\n'.join(ast.get_source_segment(source,n) for n in nodes)+'\n'
        self.write('tools/zone_object_assets.py',definitions(ROOT/'tools/zone_object_assets.py',
                   ('source_paths','packed_objects','fight_objects'),('DEFERRED','RETAIL_VRAM_EVIDENCE','FIGHT_KINDS')))
        self.write('tools/zone_object_source.py',definitions(ROOT/'tools/zone_object_source.py',('read_tiles',),('R4_ALIASES',)))
        self.write(resume._LIBRETRO_HEADER,'fixture header')
        self.write('dist/sonic-cd-saturn-prototype.cue','FILE "native.bin" BINARY\n TRACK 01 MODE1/2352\n INDEX 01 00:00:00\n')
        self.write('dist/native.bin','n'*2352)
        for name,kind in (('R83C',185),('R83C-flower',31),('R83C-boss',688),('R83C-boss-ending',187)):
            vram=('fixture '+name).encode()*4
            self.write('build/zone-object-source/'+name+'/vram.bin',vram.decode())
            self.write('build/zone-object-source/'+name+'/source.json',dict(vram_sha256=hashlib.sha256(vram).hexdigest(),objects=[dict(kind=kind,tile=0,address=0,frames=['00'])]))
        window=types.SimpleNamespace(gate='art',zone='mm',name='MM3C'+program[4:],
            run=types.SimpleNamespace(cmds=[['python3','tools/test_zone_art_emulator.py',program]],out=None))
        spec=resume.consumer_spec(self.root,window.run.cmds,window=window)
        return window,spec,resume.consumer_inputs(self.root,spec,context=self.ctx)

    def test_art_regular_program_joins_selected_source_files(self):
        _,spec,before=self.art_fixture('R83C')
        self.assertTrue(before['complete'],before['unsupported'])
        flower=self.root/'build/zone-object-source/R83C-flower/source.json'
        source=json.loads(flower.read_text())
        source['objects'][0]['frames']=['01']
        flower.write_text(json.dumps(source))
        after=resume.consumer_inputs(self.root,spec,context=self.ctx)
        self.assertTrue(after['complete'],after['unsupported'])
        self.assertNotEqual(before['joins']['source_capture_sha256'],after['joins']['source_capture_sha256'])
        with self.assertRaises(ValueError):resume.verify_consumer_inputs(self.root,before)
        flower.unlink()
        self.assertFalse(resume.consumer_inputs(self.root,spec,context=self.ctx)['complete'])

    def test_art_json_vram_join_checker_aggregate_and_fight_end_fallback(self):
        window,spec,before=self.art_fixture()
        self.assertTrue(before['complete'],before['unsupported'])
        self.assertIn('build/zone-object-source/R83C-boss/vram.bin',spec['files'])
        self.assertIn('build/zone-object-source/R83C/vram.bin',spec['files'])
        self.assertFalse(any('R83C-fight/' in name for name in spec['files']))
        child=self.write('art-evidence.json',dict(passed=True,source_capture_sha256=before['joins']['source_capture_sha256']))
        entry=dict(evidence=str(child.relative_to(self.root)),evidence_sha256=resume.digest(child))
        self.assertTrue(resume.consumer_evidence_matches(self.root,entry,before))
        child.write_text(json.dumps(dict(passed=True,source_capture_sha256='0'*64)));entry['evidence_sha256']=resume.digest(child)
        self.assertFalse(resume.consumer_evidence_matches(self.root,entry,before))
        boss=self.root/'build/zone-object-source/R83C-boss/vram.bin';boss.write_text('changed VRAM')
        changed=resume.consumer_inputs(self.root,spec,context=self.ctx)
        self.assertFalse(changed['complete']);self.assertTrue(any('Source JSON/VRAM hash differs' in x for x in changed['unsupported']))
        _,ending_spec,ending=self.art_fixture('R83C-ending')
        self.assertTrue(ending['complete'],ending['unsupported'])
        self.assertIn('build/zone-object-source/R83C-boss-ending/vram.bin',ending_spec['files'])
        self.assertIn('build/zone-object-source/R83C-boss/vram.bin',ending_spec['files'])
        boss.unlink();self.assertFalse(resume.consumer_inputs(self.root,ending_spec,context=self.ctx)['complete'])

    def test_art_optional_plc_presence_changes_the_captured_source_selection(self):
        import hashlib
        _,spec,before=self.art_fixture()
        self.assertFalse(before['files']['build/zone-object-source/R83C-plc/source.json']['present'])
        vram=b'new optional PLC bytes'
        self.write('build/zone-object-source/R83C-plc/vram.bin',vram.decode())
        self.write('build/zone-object-source/R83C-plc/source.json',dict(vram_sha256=hashlib.sha256(vram).hexdigest(),objects=[dict(kind=185,tile=0,address=0,frames=['00'])]))
        after=resume.consumer_inputs(self.root,spec,context=self.ctx)
        self.assertTrue(after['complete'],after['unsupported'])
        self.assertNotEqual(before['joins']['source_capture_sha256'],after['joins']['source_capture_sha256'])
        with self.assertRaises(ValueError):resume.verify_consumer_inputs(self.root,before)

    def palette_fixture(self):
        import ast,hashlib
        core=self.write(resume.REFERENCE_CORE,'synthetic core never executed')
        context=synthetic_reference_profile(self.root,core)
        for filename,function in (('cc_palette_source.py','generate'),('convert_assets.py','palette')):
            text=(ROOT/'tools'/filename).read_text();node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name==function)
            self.write('tools/'+filename,ast.get_source_segment(text,node)+'\n')
        compiler=self.write('build/fake-bin/clang','not executable; metadata only')
        compiler.chmod(0o700)  # Selection metadata only. No execution is permitted.
        settings=self.write('build/fake-sdk/SDKSettings.json','{}');sdk=settings.parent;info=sdk.stat()
        context['toolchain']=dict(compiler=str(compiler),compiler_sha256=resume.digest(compiler),sdk=str(sdk),sdk_device=info.st_dev,sdk_inode=info.st_ino,sdk_settings_sha256=resume.digest(settings))
        metadata={}
        for index,e in enumerate('ABCD'):
            source=self.write('.deps/soniccd/src/R3/COL3'+e+'.C','/* '+e+' */ void clchgctr(void) {}')
            metadata[e]=dict(source_sha256=resume.digest(source),program_sha256=hashlib.sha256(bytes([7+index])).hexdigest(),cycles=[])
        self.write('build/cc1/palette-source.json',metadata)
        for name in resume._palette_inputs():
            if not (self.root/name).exists():self.write(name,'synthetic input '+name)
        spec=resume.consumer_spec(self.root,[resume._PALETTE_COMMAND])
        before=resume.consumer_inputs(self.root,spec,context=context)
        self.assertTrue(before['complete'],before['unsupported'])
        for name in resume._palette_outputs():
            if not (self.root/name).exists():self.write(name,'synthetic output '+name)
        inputs={name:value['sha256'] for name,value in before['files'].items()}
        self.write('build/cc1/palette/report.json',dict(passed=True,status='passed',inputs=inputs,run_inputs=inputs,compiler='synthetic not executed',
            frames_per_era=8193,frames=4*8193,colors=4*8193*64,repeated_paused_frames=4*8193,
            palette_trace_sha256={e:hashlib.sha256(e.encode()).hexdigest() for e in 'ABCD'},
            eras={e:dict(mmd_sha256=metadata[e]['program_sha256'],pack_sha256=before['files']['assets/generated/cc31'+e+'.bin']['sha256']) for e in 'ABCD'}))
        log=self.write('palette-producer.log','synthetic actual-run substitute; metadata only')
        return context,before,dict(path=str(log.relative_to(self.root)),sha256=resume.digest(log))

    def test_palette_source_compiler_output_receipt_and_consumer_join(self):
        context,before,log=self.palette_fixture()
        with self.assertRaises(FileNotFoundError):resume.palette_producer_join(self.root,context)
        result=resume.producer_outputs(self.root,resume._PALETTE_COMMAND,context=context,consumer=before,log=log,exit_code=0)
        self.assertEqual(resume.palette_producer_join(self.root,context),result['palette_producer'])
        (self.root/'build/cc1/palette/original-D.dylib').write_text('unrelated later era output')
        self.assertEqual(resume.palette_producer_join(self.root,context,'A'),result['palette_producer'])
        output=self.root/'build/cc1/palette/original-A.dylib';original=output.read_bytes();output.write_text('changed fixture library')
        with self.assertRaises(ValueError):resume.palette_producer_join(self.root,context,'A')
        output.write_bytes(original)
        (self.root/'build/fake-bin/clang').write_text('compiler changed')
        with self.assertRaises(ValueError):resume.palette_producer_join(self.root,context)

    def test_palette_source_metadata_mismatch_and_false_exit_reject(self):
        context,before,log=self.palette_fixture()
        with self.assertRaises(ValueError):resume.producer_outputs(self.root,resume._PALETTE_COMMAND,context=context,consumer=before,log=log,exit_code=False)
        path=self.root/'build/cc1/palette-source.json';data=json.loads(path.read_text());data['A']['cycles']=[dict(index=99)];path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):resume.palette_source_join(self.root)
        self.assertFalse(resume.consumer_inputs(self.root,before['recipe'],context=context)['complete'])

    def test_palette_clean_environment_binds_existing_compiler_and_sdk_only(self):
        import sys,shutil
        context,_,_=self.palette_fixture()
        original=shutil.which
        def selected(command,**kwargs):
            return sys.executable if command=='python3' else original(command,**kwargs)
        with patch.dict(os.environ,{'CPATH':'must not reach compiler','SS_CFLAGS':'must not reach compiler'}),patch.object(resume.shutil,'which',side_effect=selected):
            env=resume.consumer_environment(context,resume._PALETTE_COMMAND)
        self.assertEqual(Path(__import__('shutil').which('clang',path=env['PATH'])).resolve(),Path(context['toolchain']['compiler']))
        self.assertEqual(env['SDKROOT'],context['toolchain']['sdk'])
        self.assertNotIn('CPATH',env);self.assertNotIn('SS_CFLAGS',env)
        self.assertIsNone(resume.consumer_environment(context,['bash','tools/test-save.sh']))
        with patch.object(resume.shutil,'which',return_value='/synthetic/other/python3'):
            with self.assertRaisesRegex(ValueError,'caller runtime'):resume.consumer_environment(context,resume._PALETTE_COMMAND)

    def test_historical_palette_metadata_validation_never_rehashes_later_mutable_output(self):
        context,before,log=self.palette_fixture()
        result=resume.producer_outputs(self.root,resume._PALETTE_COMMAND,context=context,consumer=before,log=log,exit_code=0)
        receipt=json.loads((self.root/result['palette_producer']['path']).read_text())
        report=json.loads((self.root/receipt['producer_report']['path']).read_text())
        (self.root/'build/cc1/palette/original-A.dylib').write_text('later producer output')
        resume.validate_palette_producer_metadata(receipt,before,report)
        with self.assertRaises(ValueError):resume.palette_producer_join(self.root,context)
        for key,value in (('frames',False),('frames',0),('passed',1)):
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                resume.validate_palette_producer_metadata(receipt,before,dict(report,**{key:value}))
        bad=copy.deepcopy(receipt);bad['files'].pop('build/cc1/palette/original-A.dylib')
        with self.assertRaises(ValueError):resume.validate_palette_producer_metadata(bad,before,report)
        self.assertEqual(len(resume.producer_output_paths(resume._PALETTE_COMMAND)),11)

    def test_immutable_snapshot_publication_is_atomic_and_preserves_primary_error(self):
        folder=self.root/'build';target=folder/'immutable.json'
        with patch.object(resume.os,'replace',side_effect=OSError('synthetic rename failure')):
            with self.assertRaisesRegex(OSError,'synthetic rename failure'):resume._durable_once(target,b'{"complete":true}')
        self.assertFalse(target.exists());self.assertEqual(list(folder.glob('*.pending')),[])
        resume._durable_once(target,b'{"complete":true}')
        self.assertEqual(target.read_bytes(),b'{"complete":true}')
        with self.assertRaises(ValueError):resume._durable_once(target,b'changed')
        with self.assertRaises(ValueError):resume._durable_once(folder/'missing'/'never-created.json',b'{}')
        self.assertFalse((folder/'missing').exists())

    def test_malformed_present_context_cannot_use_legacy_fallback(self):
        self.commands=[['bash','tools/test-save.sh']]
        path,data=self.checkpoint()
        for value in (False,{},dict(self.ctx,protocol=True)):
            bad=dict(data,checkpoint_context=value);path.write_text(json.dumps(bad))
            with self.subTest(value=value),self.assertRaises(ValueError):
                resume.cached_steps(self.root,'fast',self.commands,self.ctx,[path])



class FixedProducerClosure(unittest.TestCase):
    setUp=Recovery.setUp
    write=Recovery.write

    def fixture(self,producer):
        core=self.write(resume.REFERENCE_CORE,'synthetic core, never executed')
        context=synthetic_reference_profile(self.root,core)
        for name in resume.fixed_producer_source_paths(producer):
            if not (self.root/name).exists():self.write(name,'synthetic source/input: '+name)
        cue=self.write('dist/sonic-cd-saturn-prototype.cue','FILE "fixture.bin" BINARY\n TRACK 01 MODE1/2048\n INDEX 01 00:00:00\n')
        cue.with_name('fixture.bin').write_bytes(bytes(2048))
        command=resume.fixed_producer_command(producer)
        before=resume.consumer_inputs(self.root,resume.consumer_spec(self.root,[command]),context=context)
        self.assertTrue(before['complete'],before['unsupported'])
        for name in resume._FIXED_PRODUCERS[producer]['outputs']:self.write(name,'synthetic output: '+name)
        report=None
        if producer=='secret-images':report={**{str(n):{} for n in range(1,6)},'inputs':{'secret_images_retail.py':resume.digest(self.root/command[1])}}
        if producer=='visual-images':report={'summary':{'inputs':{'visual_mode_retail.py':resume.digest(self.root/command[1])},'shots':{n:{} for n in ('sel0','sel1','sel2','sel3','sel4','wrap0','up4','right3','left4')}},'rows':[]}
        if producer=='frontend-thresholds':report=dict(passed=True,status='passed',cases=[dict(name='ta-thresholds')])
        if producer=='cdpp-toggle':
            import struct,zlib
            data=b'SCDC'+bytes([1,16,1,31])+bytes(4);data+=struct.pack('>I',zlib.crc32(data))
            report=dict(status='passed',passed=True,cases=dict(toggle=dict(passed=True,slot11_before=0,slot11_after=31<<8,
                cold_boot=dict(cdpp=31,damaged=0,empty=0),file=data.hex(),backup_sha256=resume.digest(self.root/'build/cdpp-qa/backup-cdpp.bin'))))
        if report is not None:
            if producer in ('cdpp-toggle','frontend-thresholds'):
                report.update(disc_sha256=context['bin_sha256'],elf_sha256=resume.digest(self.root/'build/saturn/sonic-cd-saturn-prototype.elf'))
            if producer in ('secret-images','visual-images'):
                inputs=(report if producer=='secret-images' else report['summary'])['inputs']
                inputs['sonic.iso.sha256.json']=resume.digest(self.root/'build/retail/sonic.iso.sha256.json')
                if producer=='visual-images':inputs['IPX___.MMD']=resume.digest(self.root/'build/retail/IPX___.MMD')
            self.write(resume._FIXED_PRODUCERS[producer]['report'],report)
        log=self.write('build/synthetic-producer.log','synthetic metadata, not execution')
        return context,before,dict(path=str(log.relative_to(self.root)),sha256=resume.digest(log))

    def publish(self,producer):
        context,before,log=self.fixture(producer)
        result=resume.producer_outputs(self.root,resume.fixed_producer_command(producer),context=context,consumer=before,log=log,exit_code=0)
        receipt=json.loads((self.root/result['fixed_producer']['path']).read_text())
        report=json.loads((self.root/receipt['producer_report']['path']).read_text()) if receipt['producer_report'] else None
        return context,before,result,receipt,report

    def test_all_six_producers_require_prospective_receipts_and_current_output_identity(self):
        for producer in resume._FIXED_PRODUCERS:
            with self.subTest(producer=producer):
                context,before,log=self.fixture(producer)
                with self.assertRaises((OSError,ValueError)):resume.fixed_producer_join(self.root,context,producer)
                result=resume.producer_outputs(self.root,resume.fixed_producer_command(producer),context=context,consumer=before,log=log,exit_code=0)
                self.assertEqual(resume.fixed_producer_join(self.root,context,producer),result['fixed_producer'])
                path=self.root/resume.fixed_producer_consumed_paths(producer)[0];path.write_text('changed captured input')
                with self.assertRaises(ValueError):resume.fixed_producer_join(self.root,context,producer)

    def test_producer_receipt_rejects_bool_exit_incomplete_and_changed_source_media_bios(self):
        for value in (False,1,None):
            context,before,log=self.fixture('secret-images')
            with self.subTest(exit=value),self.assertRaises(ValueError):
                resume.producer_outputs(self.root,resume.fixed_producer_command('secret-images'),context=context,consumer=before,log=log,exit_code=value)
        for producer,path in (('secret-images','tools/secret_images_retail.py'),('secret-images','build/retail/sonic.bin'),
                              ('cdpp-toggle','assets/private/mpr-17933.bin'),('cdpp-toggle','build/saturn/sonic-cd-saturn-prototype.elf')):
            with self.subTest(producer=producer,path=path):
                context,_,_,_,_=self.publish(producer)
                (self.root/path).write_bytes(b'changed tiny fixture')
                with self.assertRaises(ValueError):resume.fixed_producer_join(self.root,context,producer)

    def test_historical_producer_validator_does_not_rehash_later_mutable_outputs(self):
        context,before,result,receipt,report=self.publish('visual-images')
        path=self.root/'build/visual-mode/retail-sel0.rgb565';path.write_text('later output')
        resume.validate_fixed_producer_metadata(receipt,before,report)
        with self.assertRaises(ValueError):resume.fixed_producer_join(self.root,context,'visual-images')
        for key,value in (('exit_code',False),('files',{}),('producer_report',None),('context',{})):
            bad=copy.deepcopy(receipt);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):resume.validate_fixed_producer_metadata(bad,before,report)
        for edit in ('media','native','key'):
            bad=copy.deepcopy(before)
            if edit=='media':bad['recipe']['media']=[];bad['media']=[];bad['core_profile']=None
            elif edit=='native':bad['recipe']['native']=True
            else:bad['recipe']['key']['extra']='unapproved'
            changed=copy.deepcopy(receipt);changed['inputs']=resume.consumer_input_seal(bad)
            with self.subTest(recipe=edit),self.assertRaises(ValueError):resume.validate_fixed_producer_metadata(changed,bad,report)
        bad=copy.deepcopy(before);bad['recipe']['files'].remove('tools/visual_mode_retail.py');bad['files'].pop('tools/visual_mode_retail.py')
        changed=copy.deepcopy(receipt);changed['inputs']=resume.consumer_input_seal(bad)
        with self.assertRaises(ValueError):resume.validate_fixed_producer_metadata(changed,bad,report)

    def test_frontend_threshold_prerequisites_invalidate_existing_fixture(self):
        for path in ('tools/frontend_emulator_test.c', 'tools/title_menu.py', 'tests/routes/ppz/p0A.seq.txt'):
            with self.subTest(path=path):
                self.write(path, 'original prerequisite')
                context,_,result,_,_=self.publish('frontend-thresholds')
                self.assertEqual(resume.fixed_producer_join(self.root,context,'frontend-thresholds'),result['fixed_producer'])
                self.write(path, 'changed prerequisite')
                with self.assertRaises(ValueError):resume.fixed_producer_join(self.root,context,'frontend-thresholds')

    def test_mutable_reports_are_retained_as_text_and_not_mislabeled_consumer_inputs(self):
        context,before,result,receipt,report=self.publish('frontend-thresholds')
        self.write('build/frontend-qa/report.json',dict(status='pending',passed=False))
        self.assertEqual(resume.fixed_producer_join(self.root,context,'frontend-thresholds'),result['fixed_producer'])
        self.assertEqual(json.loads((self.root/receipt['producer_report']['path']).read_text()),report)
        required=resume.fixed_producer_requirements([['python3','tools/test_frontend_emulator.py','visual-mode']])
        self.assertIn('frontend-thresholds',required)
        self.assertNotIn('frontend-thresholds',resume.fixed_producer_requirements([['python3','tools/test_frontend_emulator.py']]))
        self.assertNotIn('build/frontend-qa/report.json',resume.fixed_producer_consumed_paths('frontend-thresholds'))

    def test_old_image_directories_and_pad_captures_are_renamed_without_copying_or_deleting(self):
        old=self.write('build/secret-images/retail.json','old report')
        capture=self.write('build/secret-images/retail-1.rgb565','old capture')
        retained=resume.preserve_fixed_producer_outputs(self.root,resume.fixed_producer_command('secret-images'))
        self.assertEqual(len(retained),1);self.assertFalse(old.exists())
        folder=self.root/retained[0]['retained'];self.assertEqual((folder/'retail.json').read_text(),'old report')
        self.assertEqual((folder/'retail-1.rgb565').read_text(),'old capture')
        plan=self.write('build/special-retail/win-route.json','preserved selected plan')
        for name in ('win.pad','win.jsonl','win-blobs.json','win-v20.png'):self.write('build/special-retail/'+name,'old '+name)
        retained=resume.preserve_fixed_producer_outputs(self.root,resume.fixed_producer_command('special-win-pad'))
        self.assertEqual(len(retained),4);self.assertEqual(plan.read_text(),'preserved selected plan')
        for row in retained:self.assertFalse((self.root/row['before']).exists());self.assertTrue((self.root/row['retained']).is_file())

    def test_fixed_setup_is_finite_ordered_and_never_adopts_old_unsealed_outputs(self):
        self.write('build/special-retail/win.pad','unsealed previous pad')
        commands=[['bash','tools/test-bigring-emulator.sh']]
        self.assertEqual(resume.fixed_setup_commands(self.root,self.ctx,commands),[
            ['python3','tools/special_retail.py','timeout'],['python3','tools/special_route.py'],['python3','tools/special_retail.py','win']])
        context,before,result,receipt,report=self.publish('special-win-pad')
        self.assertEqual(resume.fixed_setup_commands(self.root,context,[['python3','tools/test_ending_emulator.py','--case','stones']]),[])
        self.assertEqual(resume.fixed_producer_requirements([['python3','tools/test_ending_emulator.py','--case','good']]),[])
        self.assertEqual(resume.fixed_producer_requirements([['python3','tools/test_frontend_emulator.py','sound-test']]),[])

    def test_special_default_imports_cannot_hide_behind_a_synthetic_347_recipe_count(self):
        from types import SimpleNamespace
        cases=[('FRONTEND',['python3','tools/test_frontend_emulator.py'],
                ['build/secret-images/retail.json','build/visual-mode/retail-sel0.rgb565','build/cdpp-qa/backup-cdpp.bin','cd/VISMODE.BIN']),
               ('BIGRING-PPZ',['python3','tools/test_special_entry.py','ppz'],['build/special-retail/win.pad','build/special-retail/timeout.pad']),
               ('STONES-return',['python3','tools/test_ending_emulator.py','--case','stones'],['build/special-retail/win.pad'])]
        for name,command,expected in cases:
            with self.subTest(name=name):
                run=SimpleNamespace(cmds=[command],out=self.root/'build/out')
                window=SimpleNamespace(zone='sp',gate='special',name=name,run=run)
                body=resume.consumer_spec(self.root,[command],window=window)
                self.assertTrue(set(expected)<=set(body['files']),set(expected)-set(body['files']))
                self.assertIn('build/saturn/sonic-cd-saturn-prototype.elf',body['files'])
                self.assertIn('.toolchain/bin/sh-elf-nm',body['files'])

    def test_read_atime_changes_do_not_masquerade_as_content_changes(self):
        path=self.write('build/read-stat.txt','content')
        before=path.stat()
        os.utime(path,ns=(before.st_atime_ns+1000000,before.st_mtime_ns))
        # Setting atime with utime also changes ctime: preserve that real ownership
        # signal. A pure read-atime change alone is excluded from the identity.
        after=path.stat()
        from types import SimpleNamespace
        fields={k:getattr(before,k) for k in ('st_dev','st_ino','st_mode','st_size','st_mtime_ns','st_ctime_ns')}
        synthetic=SimpleNamespace(**fields,st_atime_ns=after.st_atime_ns)
        self.assertEqual(resume._stat_identity(before),resume._stat_identity(synthetic))
        changed=SimpleNamespace(**dict(fields,st_mtime_ns=fields['st_mtime_ns']+1))
        self.assertNotEqual(resume._stat_identity(before),resume._stat_identity(changed))
        changed=SimpleNamespace(**dict(fields,st_ino=fields['st_ino']+1))
        self.assertNotEqual(resume._stat_identity(before),resume._stat_identity(changed))

    def test_setup_catalogue_is_bound_to_exact_existing_source_defined_argv(self):
        expected=[['python3','tools/secret_images_retail.py'],['python3','tools/visual_mode_retail.py'],
                  ['python3','tools/special_retail.py','win'],['python3','tools/special_retail.py','timeout'],
                  ['python3','tools/test_frontend_emulator.py','ta-thresholds'],['python3','tools/test_cdpp_routes.py','toggle']]
        self.assertEqual([resume.fixed_producer_command(p) for p in resume._FIXED_PRODUCERS],expected)
        for command in expected:
            self.assertEqual(resume.fixed_producer_requirements([command]),[])
            self.assertFalse(resume.cacheable_command(command))
        with self.assertRaises(ValueError):resume._fixed_pointer('arbitrary')


class DispatcherFixtureCorrection(unittest.TestCase):
    setUp = Recovery.setUp
    write = Recovery.write

    def migration_fixture(self):
        inherited = dict(legacy_reports={}, legacy_matrices={}, legacy_runtime={},
            legacy_bin_sha256='synthetic', legacy_limits={}, legacy_toolchain={})
        snapshots = {}
        sealed = {}
        for name in sorted(resume.REFERENCE_UPGRADE_PATHS | {resume._DISPATCHER_FIXTURE}):
            path = self.write('sealed/'+Path(name).name, 'synthetic sealed '+name)
            sealed[name] = resume.digest(path)
            snapshots[name] = dict(snapshot=str(path), sha256=sealed[name])
        a, b, c = [dict(sealed, **{'tools/qa-loop.py': value*64}) for value in 'abc']
        m1 = dict(inherited, protocol=1, before_inputs=a, after_inputs=b,
            changed_paths=['tools/qa-loop.py'])
        p1 = self.write('M1.json', m1)
        m2 = dict(inherited, protocol=1, before_inputs=b, after_inputs=c,
            changed_paths=['tools/qa-loop.py'],
            parent_migration=dict(path=str(p1), sha256=resume.digest(p1)))
        p2 = self.write('M2.json', m2)
        sibling = dict(inherited, protocol=1, before_inputs=c, after_inputs=sealed,
            changed_paths=['tools/qa-loop.py'],
            parent_migration=dict(path=str(p2), sha256=resume.digest(p2)))
        previous = self.write('old-M3.json', sibling)
        after = {**sealed, 'tools/qa-loop.py': 'e'*64,
            resume._DISPATCHER_FIXTURE: resume._DISPATCHER_FIXTURE_SHA256}
        return dict(sibling, after_inputs=after,
            changed_paths=['tools/qa-loop.py', resume._DISPATCHER_FIXTURE],
            input_closure_protocol=1, physical_before=snapshots,
            reference_sibling=dict(path=str(previous), sha256=resume.digest(previous)))

    def test_exact_sixth_fixture_path_keeps_the_sealed_sibling_link(self):
        migration = self.migration_fixture()
        self.assertEqual(len(resume.migration_chain(migration)), 3)

    def test_sixth_fixture_path_requires_sibling_and_exact_after_bytes(self):
        migration = self.migration_fixture()
        missing = copy.deepcopy(migration)
        missing.pop('reference_sibling')
        with self.assertRaises(ValueError):
            resume.migration_chain(missing)
        wrong = copy.deepcopy(migration)
        wrong['after_inputs'][resume._DISPATCHER_FIXTURE] = 'f'*64
        with self.assertRaises(ValueError):
            resume.migration_chain(wrong)

    def fixture(self):
        import ast
        temporary = tempfile.TemporaryDirectory(dir=ROOT/'build', prefix='dispatch-ast-')
        self.addCleanup(temporary.cleanup)
        folder = Path(temporary.name)
        current = (ROOT/'tools/test_qa_dispatch_cooling.py').read_text()
        old = ast.parse(current)
        old.body = [n for n in old.body if ast.unparse(n) != 'import qa_resume']
        cls = next(n for n in old.body if isinstance(n, ast.ClassDef) and n.name == 'DispatchCooling')
        for node in cls.body:
            if isinstance(node, ast.FunctionDef) and node.name in (
                    'loop_namespace', 'test_matrix_main_limits_and_global_cooling_serialize_before_pool'):
                node.body = [ast.Pass()]
        before, after = folder/'synthetic-before.py', folder/'after.py'
        before.write_text(ast.unparse(old))
        after.write_text(current)
        return before, after

    def test_exact_reviewed_fixture_methods_are_admitted(self):
        before, after = self.fixture()
        resume.verify_dispatch_fixture_sources(before, after)

    def test_changed_assertion_or_unrelated_method_is_rejected(self):
        before, after = self.fixture()
        original = after.read_text()
        for old, new in (('self.assertEqual(capacities, [expected])',
                          'self.assertEqual(capacities, [999])'),
                         ('self.assertEqual(stopped.exception.code, 130)',
                          'self.assertEqual(stopped.exception.code, 0)')):
            with self.subTest(assertion=old):
                self.assertIn(old, original)
                after.write_text(original.replace(old, new))
                with self.assertRaises(ValueError):
                    resume.verify_dispatch_fixture_sources(before, after)


class CueCorrectionSibling(unittest.TestCase):
    """Synthetic data pins only; production N5 pin is tested separately read-only."""
    setUp = Recovery.setUp
    write = Recovery.write

    def fixture(self):
        inherited=dict(legacy_reports={'historical':'unchanged'},legacy_matrices={},
            legacy_runtime={'python':'synthetic'},legacy_bin_sha256='same-bin',
            legacy_limits=dict(SCD_QA_MAX_WORKERS='1',SCD_QA_MAX_EMULATORS='1',
                SCD_QA_COOLDOWN_SECONDS='120',SCD_NICE='20'),legacy_toolchain={})
        names=sorted(resume.REFERENCE_UPGRADE_PATHS|{resume._DISPATCHER_FIXTURE})
        snapshots={}
        def snapshot(label,values):
            result={}
            for name in names:
                path=self.write(label+'/'+Path(name).name,values.get(name,label+' '+name))
                result[name]=dict(snapshot=str(path),sha256=resume.digest(path))
            return result
        initial=snapshot('base',{})
        a={name:pin['sha256'] for name,pin in initial.items()}
        a.update({'src/game.c':'a'*64,resume.REFERENCE_CORE:'0'*64})
        b={**a,'tools/qa-loop.py':'b'*64};c={**b,'tools/qa_resume.py':'c'*64}
        m1=dict(inherited,protocol=1,before_inputs=a,after_inputs=b,changed_paths=['tools/qa-loop.py'])
        p1=self.write('M1.json',m1)
        m2=dict(inherited,protocol=1,before_inputs=b,after_inputs=c,changed_paths=['tools/qa_resume.py'],parent_migration=dict(path=str(p1),sha256=resume.digest(p1)))
        p2=self.write('M2.json',m2);parent=dict(path=str(p2),sha256=resume.digest(p2))
        old_files=snapshot('old-M3',{resume._DISPATCHER_FIXTURE:(self.root/'base'/Path(resume._DISPATCHER_FIXTURE).name).read_text()})
        d={**c,**{name:pin['sha256'] for name,pin in old_files.items()}}
        old=dict(inherited,protocol=1,before_inputs=c,after_inputs=d,changed_paths=sorted(n for n in c if c[n]!=d[n]),parent_migration=parent)
        p3=self.write('old-M3.json',old)
        current_files=snapshot('N5',{})
        fixed=current_files[resume._DISPATCHER_FIXTURE]['sha256']
        self.fixture_sha_patch=patch.object(resume,'_DISPATCHER_FIXTURE_SHA256',fixed)
        self.fixture_sha_patch.start();self.addCleanup(self.fixture_sha_patch.stop)
        profile=self.write('build/qa-core-profiles/genesis-default.json',dict(protocol=1,build={'synthetic':'only'},approval={'synthetic':'only'}))
        e={**d,**{name:pin['sha256'] for name,pin in current_files.items()},resume.REFERENCE_CORE:'1'*64}
        core=dict(path=resume.REFERENCE_CORE,before_sha256='0'*64,after_sha256='1'*64,profile=dict(path=str(profile),sha256=resume.digest(profile)))
        prior=dict(inherited,protocol=1,input_closure_protocol=1,before_inputs=c,after_inputs=e,
            changed_paths=sorted(n for n in c if c[n]!=e[n]),parent_migration=parent,core_epoch=core,
            reference_sibling=dict(path=str(p3),sha256=resume.digest(p3)),physical_before=old_files)
        pp=self.write('N5.json',prior);pin=dict(path=str(pp),sha256=resume.digest(pp))
        self.prior_patch=patch.object(resume,'_CUE_CORRECTION_PRIOR',pin,create=True)
        self.prior_patch.start();self.addCleanup(self.prior_patch.stop)
        after={**e,'tools/qa_resume.py':'d'*64,'tools/test_qa_resume.py':'e'*64}
        corrected=dict(prior,qa_correction='cue-pregap-v1',after_inputs=after,
            changed_paths=sorted(n for n in c if c[n]!=after[n]),reference_sibling=pin,physical_before=current_files)
        return corrected,prior,old,m2

    def row_fixture(self,command=None):
        value,prior,old,m2=self.fixture()
        self.inputs=prior['after_inputs']
        self.ctx=dict(protocol=1,runtime=prior['legacy_runtime'],bin_sha256=prior['legacy_bin_sha256'],limits=prior['legacy_limits'],toolchain=prior['legacy_toolchain'],source_sha256=self.inputs)
        self.commands=[command or ['bash','tools/test-tt-platforms.sh']]
        self.write('build/auto-extract/4/objects42C.bin','tiny persistent placement')
        if self.commands[0]==['bash','tools/test-sonic-animation.sh']:self.write('build/sonic-animation/expected-frames.bin','tiny producer output')
        path,data=Recovery.checkpoint(self)
        observed=resume.consumer_inputs(self.root,resume.consumer_spec(self.root,self.commands),context=self.ctx)
        self.assertTrue(observed['complete'])
        row=data['steps'][0];row['consumer_inputs']=resume.preserve_consumer_inputs(self.root,observed);row['input_identity_complete']=True
        produced=resume.producer_outputs(self.root,self.commands[0])
        if produced is not None:row['producer_outputs']=produced
        path.write_text(json.dumps(data))
        current=dict(self.ctx,source_sha256=value['after_inputs'])
        return value,current,path,data,observed

    def consume(self,value,current,path):
        candidates,_=resume.cached_steps(self.root,'fast',self.commands,current,[path],value)
        if 0 not in candidates:return None
        return resume.consume_cached_step(self.root,'fast',self.commands,current,candidates[0],0,value)

    def test_complete_current_consumer_reuse_and_after_cooling_mutation(self):
        value,current,path,data,observed=self.row_fixture()
        reused=self.consume(value,current,path);self.assertIsNotNone(reused)
        self.assertTrue(reused['input_identity_complete'])
        self.assertEqual(reused['consumer_inputs_observation'],'verified_before_reuse')
        candidates,_=resume.cached_steps(self.root,'fast',self.commands,current,[path],value)
        (self.root/'build/auto-extract/4/objects42C.bin').write_text('changed after preselection')
        self.assertIsNone(resume.consume_cached_step(self.root,'fast',self.commands,current,candidates[0],0,value))

    def test_incomplete_or_tampered_row_never_becomes_a_cached_pass(self):
        value,current,path,data,observed=self.row_fixture()
        self.assertIsNotNone(self.consume(value,current,path))
        for name in ('incomplete','BIOS','environment','reference','log','CAS','nonzero','missing'):
            bad=copy.deepcopy(data)
            if name=='incomplete':
                body=copy.deepcopy(observed);body['complete']=False;body['unsupported']=['synthetic historical omission'];bad['steps'][0]['consumer_inputs']=resume.preserve_consumer_inputs(self.root,body)
            elif name=='BIOS':bad['steps'][0]['bios_inputs']=False
            elif name=='environment':bad['steps'][0]['execution_environment']=False
            elif name=='reference':bad['steps'][0]['reference_inputs']['sha256']='0'*64
            elif name=='log':bad['steps'][0]['log_sha256']='0'*64
            elif name=='CAS':bad['steps'][0]['consumer_inputs']['sha256']='0'*64
            elif name=='nonzero':bad['steps'][0]['exit_code']=3
            else:bad['steps']=[]
            path.write_text(json.dumps(bad))
            with self.subTest(case=name):self.assertIsNone(self.consume(value,current,path))
        unknown=copy.deepcopy(data);unknown['steps'][0]['command']=unknown['steps'][0]['canonical_command']=['python3','tools/cdpp_fuzz.py','--classic'];path.write_text(json.dumps(unknown));self.commands=[unknown['steps'][0]['command']]
        self.assertIsNone(self.consume(value,current,path))

    def test_native_producer_output_proof_is_still_required(self):
        value,current,path,data,observed=self.row_fixture(['bash','tools/test-sonic-animation.sh'])
        self.assertIsNotNone(self.consume(value,current,path))
        data['steps'][0]['producer_outputs']['files']['build/sonic-animation/expected-frames.bin']['sha256']='0'*64;path.write_text(json.dumps(data))
        self.assertIsNone(self.consume(value,current,path))

    def test_exact_tag_retains_three_ancestors_and_both_m3_maps(self):
        value,prior,old,m2=self.fixture()
        self.assertEqual(len(resume.migration_chain(value)),3)
        maps=resume.migration_source_maps(value)
        for accepted in (prior['after_inputs'],old['after_inputs'],m2['after_inputs']):
            self.assertIn(accepted,maps);self.assertTrue(resume.same_inputs(accepted,value['after_inputs'],value))
        intermediate={**prior['after_inputs'],'tools/qa_resume.py':'f'*64,'tools/test_qa_resume.py':'f'*64}
        self.assertFalse(resume.same_inputs(intermediate,value['after_inputs'],value))

    def test_tag_prior_and_history_negatives(self):
        value,prior,old,m2=self.fixture()
        cases=[]
        for tag in (None,False,True,1,'unknown'):
            bad=copy.deepcopy(value);bad['qa_correction']=tag;cases.append(bad)
        bad=copy.deepcopy(value);bad.pop('qa_correction');cases.append(bad)
        bad=copy.deepcopy(value);bad.pop('reference_sibling');cases.append(bad)
        bad=copy.deepcopy(value);bad['reference_sibling']['sha256']='0'*64;cases.append(bad)
        bad=copy.deepcopy(value);bad['reference_sibling']['path']=str(self.root/'foreign.json');cases.append(bad)
        for bad in cases:
            with self.subTest(bad=bad.get('qa_correction')),self.assertRaises((ValueError,OSError)):resume.migration_chain(bad)
        # The production bound is not a general recursion allowance.
        third=copy.deepcopy(old);third['reference_sibling']=prior['reference_sibling']
        path=Path(prior['reference_sibling']['path']);path.write_text(json.dumps(third))
        prior['reference_sibling']['sha256']=resume.digest(path)
        pp=Path(value['reference_sibling']['path']);pp.write_text(json.dumps(prior));value['reference_sibling']['sha256']=resume.digest(pp)
        with patch.object(resume,'_CUE_CORRECTION_PRIOR',value['reference_sibling'],create=True),self.assertRaises(ValueError):resume.migration_chain(value)

    def test_exact_immediate_two_file_and_inherited_epoch_negatives(self):
        value,prior,old,m2=self.fixture()
        cases=[]
        # Cumulative scope is still nonempty; the immediate correction is empty.
        bad=copy.deepcopy(value);bad['after_inputs']=copy.deepcopy(prior['after_inputs'])
        bad['changed_paths']=sorted(n for n in bad['before_inputs'] if bad['before_inputs'][n]!=bad['after_inputs'][n]);cases.append(bad)
        # A normal source-map shape cannot replace the exact M2.after baseline.
        bad=copy.deepcopy(value);bad['before_inputs']['tools/qa_resume.py']='f'*64
        bad['changed_paths']=sorted(n for n in bad['before_inputs'] if bad['before_inputs'][n]!=bad['after_inputs'][n]);cases.append(bad)
        # Retain the complete core shape but change the nested approved pin.
        bad=copy.deepcopy(value);bad['core_epoch']['profile']['sha256']='f'*64;cases.append(bad)
        for name in ('tools/qa_resume.py','tools/test_qa_resume.py'):
            bad=copy.deepcopy(value);bad['after_inputs'][name]=prior['after_inputs'][name];cases.append(bad)
        for name in ('src/game.c','tools/qa-loop.py',resume.REFERENCE_CORE):
            bad=copy.deepcopy(value);bad['after_inputs'][name]='f'*64
            bad['changed_paths']=sorted(n for n in bad['before_inputs'] if bad['before_inputs'][n]!=bad['after_inputs'][n]);cases.append(bad)
        bad=copy.deepcopy(value);bad['after_inputs']['extra.c']='f'*64;bad['changed_paths'].append('extra.c');cases.append(bad)
        for key in ('legacy_runtime','legacy_toolchain','legacy_limits','legacy_reports','legacy_matrices','legacy_bin_sha256','parent_migration','core_epoch'):
            bad=copy.deepcopy(value);bad[key]={'changed':'not allowed'};cases.append(bad)
        bad=copy.deepcopy(value);bad['physical_before'].pop('tools/qa-loop.py');cases.append(bad)
        bad=copy.deepcopy(value);bad['physical_before']['tools/qa_resume.py']['sha256']='f'*64;cases.append(bad)
        bad=copy.deepcopy(value);bad['physical_before'][resume._DISPATCHER_FIXTURE]['snapshot']=str(self.root/'foreign.py');cases.append(bad)
        for i,bad in enumerate(cases):
            with self.subTest(case=i),self.assertRaises((ValueError,KeyError,OSError)):resume.migration_chain(bad)
        pp=Path(value['reference_sibling']['path']);pp.write_text(pp.read_text()+' ')
        with self.assertRaises(ValueError):resume.migration_chain(value)

    def test_old_sibling_branch_still_accepts_and_untagged_recursion_still_rejects(self):
        value,prior,old,m2=self.fixture()
        self.assertEqual(len(resume.migration_chain(prior)),3)
        self.assertEqual(len(resume.migration_chain(old)),3)
        direct=dict(value,parent_migration=value['reference_sibling'])
        with self.assertRaises(ValueError):resume.migration_chain(direct)
        untagged=copy.deepcopy(value);untagged.pop('qa_correction')
        with self.assertRaises(ValueError):resume.migration_chain(untagged)

    def preparation(self,value,prior,m2):
        """Full real prepare body,existing heavy gates mocked;no migration file published."""
        import contextlib,subprocess,sys
        for name in ('tools/qa_resume.py','tools/test_qa_resume.py'):
            file=self.write(name,'synthetic candidate source '+name)
            value['after_inputs'][name]=resume.digest(file)
        self.write(resume._DISPATCHER_FIXTURE,Path(value['physical_before'][resume._DISPATCHER_FIXTURE]['snapshot']).read_text())
        compiler=self.write('synthetic-compiler','not an executable')
        self.write('build/saturn/sonic-cd-saturn-prototype.elf','synthetic text')
        sdk=self.root/'synthetic-sdk';sdk.mkdir();settings=self.write('synthetic-sdk/SDKSettings.json','{}');info=sdk.stat()
        context=dict(protocol=1,runtime=prior['legacy_runtime'],bin_sha256=prior['legacy_bin_sha256'],limits=prior['legacy_limits'],source_sha256=value['after_inputs'],
            toolchain=dict(sdk=str(sdk),sdk_device=info.st_dev,sdk_inode=info.st_ino))
        # Preserve a single matching synthetic toolchain through both parent seals.
        for path in ('M1.json','M2.json','N5.json','old-M3.json'):
            p=self.root/path;data=json.loads(p.read_text());data['legacy_toolchain']=context['toolchain'];p.write_text(json.dumps(data))
        m1p=self.root/'M1.json';m2p=self.root/'M2.json';oldp=self.root/'old-M3.json';priorp=self.root/'N5.json'
        m2data=json.loads(m2p.read_text());m2data['parent_migration']['sha256']=resume.digest(m1p);m2p.write_text(json.dumps(m2data))
        for p in (oldp,priorp):
            data=json.loads(p.read_text());data['parent_migration']['sha256']=resume.digest(m2p)
            if p==priorp:data['reference_sibling']['sha256']=resume.digest(oldp)
            p.write_text(json.dumps(data))
        prior=json.loads(priorp.read_text());value['legacy_toolchain']=context['toolchain'];value['parent_migration']['sha256']=resume.digest(m2p);value['reference_sibling']['sha256']=resume.digest(priorp)
        inventory={'modes':{mode:dict(total=n,argv=[['synthetic',str(i)] for i in range(n)]) for mode,n in [('fast',171),('full',215)]}}
        state=self.root/'state';state.mkdir();self.write('state/target-prerequisites/qa-argv-inventory.json',inventory)
        self.write('state/preflight.json',dict(runtime=context['runtime'],bin_sha256=context['bin_sha256'],compiler=dict(path=str(compiler),sha256=resume.digest(compiler)),elf_sha256=resume.digest(self.root/'build/saturn/sonic-cd-saturn-prototype.elf')))
        self.write('state/sdk-current-directory-checkpoint.json',dict(SDK_directory=dict(physical_path=str(sdk),device=info.st_dev,inode=info.st_ino),files={str(settings):resume.digest(settings)}))
        for name in ('old-fast.json','old-full.json','current-fast.json'):self.write(name,{'synthetic':'only'})
        plan=dict(qa_correction=value['qa_correction'],input_closure_protocol=1,parent_migration=value['parent_migration'],reference_sibling=value['reference_sibling'],physical_before=value['physical_before'],core_epoch=value['core_epoch'],pre_upgrade_source_sha256=value['before_inputs'],
            launch_state=dict(resume=str(state),preflight=str(state/'preflight.json'),fast_report=str(self.root/'current-fast.json')),originals={'synthetic':'oracle spy'},prior_fast_report='old-fast.json',prior_full_report='old-full.json')
        plan_path=self.write('plan.json',plan);published=[];calls=[];oracle=[]
        def run(argv,**kwargs):
            calls.append(argv)
            if argv[1:2]==['tools/qa-loop.py']:
                mode=argv[2];return types.SimpleNamespace(returncode=0,stdout=''.join(str(i)+': '+' '.join(cmd)+'\n' for i,cmd in enumerate(inventory['modes'][mode]['argv'])),stderr='')
            self.assertIn(argv[1],('tools/test_qa_resume.py','tools/test_qa_dispatch_cooling.py'))
            return types.SimpleNamespace(returncode=0,stdout='mock controls only',stderr='')
        def forbidden_fixture(*a):raise AssertionError('already-corrected dispatcher transformation must not replay')
        output=self.root/'NOT-PUBLISHED.json'
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.dict(sys.modules,{'power_guard':types.SimpleNamespace(inputs=lambda:value['after_inputs']),
                'qa_limits':types.SimpleNamespace(atomic_json=lambda p,v:published.append((p,v)))}))
            stack.enter_context(patch.object(resume,'context',lambda *a:context))
            stack.enter_context(patch.object(resume,'default_core_profile',lambda *a,**k:json.loads((self.root/'build/qa-core-profiles/genesis-default.json').read_text())))
            stack.enter_context(patch.object(resume,'_CUE_CORRECTION_PRIOR',value['reference_sibling'],create=True))
            stack.enter_context(patch.object(resume,'verify_bios_upgrade_sources',lambda *a:oracle.append(a)))
            stack.enter_context(patch.object(resume,'verify_dispatch_fixture_sources',forbidden_fixture))
            stack.enter_context(patch.object(resume,'cached_steps',lambda *a:({},[])))
            stack.enter_context(patch.object(subprocess,'run',run))
            result=resume.prepare_migration(self.root,plan_path,output)
        self.assertEqual(len(calls),4);self.assertEqual(len(oracle),1)
        self.assertEqual(len(published),1);self.assertFalse(output.exists())
        self.assertEqual(result['qa_correction'],'cue-pregap-v1');self.assertEqual(len(resume.migration_chain(result)),3)
        self.assertEqual(result['reference_sibling'],value['reference_sibling'])
        return plan,context

    def test_actual_prepare_preserves_tag_and_inherits_fixed_dispatcher(self):
        value,prior,old,m2=self.fixture();self.preparation(value,prior,m2)

    def test_prepare_rejects_invalid_tag_before_existing_heavy_gates(self):
        import sys
        value,prior,old,m2=self.fixture()
        for tag in (False,'unknown'):
            p=self.write('bad-plan.json',dict(parent_migration=value['parent_migration'],pre_upgrade_source_sha256=value['before_inputs'],qa_correction=tag))
            with patch.dict(sys.modules,{'power_guard':types.SimpleNamespace(inputs=lambda:value['after_inputs']),'qa_limits':types.SimpleNamespace(atomic_json=lambda *a:self.fail('published'))}),self.assertRaises(ValueError):
                resume.prepare_migration(self.root,p,self.root/'not-created.json')


if __name__ == '__main__':
    unittest.main()
