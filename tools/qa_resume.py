"""Verified QA checkpoints. Cache execution evidence, never a suite verdict."""
import copy
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import struct
import subprocess

PROTOCOL = 1
UPGRADE_PATHS = frozenset(('tools/qa-loop.py', 'tools/zone-gates.py',
    'tools/zone_release_evidence.py', 'tools/qa_resume.py', 'tools/test_qa_resume.py',
    'tools/test_qa_dispatch_cooling.py'))
BIOS_PATHS = ('assets/private/mpr-17933.bin', 'assets/private/sega_101.bin',
              'assets/private/saturn-bios.bin', 'assets/private/bios_CD_U.bin')
BIOS_UPGRADE_PATHS = UPGRADE_PATHS | {'tools/retail_parity.py'}
REFERENCE_UPGRADE_PATHS = frozenset(('tools/qa_resume.py', 'tools/qa-loop.py',
    'tools/zone-gates.py', 'tools/test_qa_resume.py', 'tools/retail_parity.py'))
_DISPATCHER_FIXTURE = 'tools/test_qa_dispatch_cooling.py'
_DISPATCHER_FIXTURE_SHA256 = '6a2b5aa11a406e040ef4d56f27b078b1eb224c6c24ad5c8293fd353463b22ef1'
_CUE_CORRECTION = 'cue-pregap-v1'
_CUE_CORRECTION_PATHS = frozenset(('tools/qa_resume.py', 'tools/test_qa_resume.py'))
# This historical exception grants no other three-deep M3 a new sibling edge.
_CUE_CORRECTION_PRIOR = dict(
    path=str(Path(__file__).resolve().parents[1]/'build/qa-campaign/validation-resume-20261107-185625/migration-verified.json'),
    sha256='626a1816262aaea7ffe48fc7ae722056e615e56a0b84291d91b543099d47e40f')
REFERENCE_ROOTS = {
    'build/audit/source/src': ('.c', '.h'),
    'build/probe-source': ('.c', '.h', '.inc'),
    '.deps/soniccd/src': ('.c', '.h'),
    'assets/generated': None,
    # Default scd_source.SRC only. Nonempty alternate selectors cannot reuse.
    '.deps/scddisasm/src': None,
}
REFERENCE_FILES = ('build/retail/sonic.iso', 'dist/sonic-cd-saturn-prototype.cue')
REFERENCE_CORE = '.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib'
LEGACY_REFERENCE_INDEPENDENT = frozenset((
    ('bash', 'tools/test-save.sh'), ('bash', 'tools/test-time-attack.sh'),
    ('python3', 'tools/test_sprite_priority.py'),
    ('python3', 'tools/test_world_restart.py'), ('python3', 'tools/test_qq_switch_margin.py'),
    ('python3', 'tools/test_candidate_identity.py'), ('python3', 'tools/test_title_cycles.py'),
))
# Exact audited entrypoints and their source-consumed mutable overrides.
# Empty dependency lists are affirmative source audits, never a filename rule.
EXECUTION_ENV_KEYS = ('SS_CFLAGS', 'MM_CFLAGS', 'QQ_CFLAGS', 'WW_CFLAGS',
    'TT_EXTRA', 'SCD_DATA_ROOT', 'TT_BG_WRITE_LIMIT', 'QQ_BG_WRITE_LIMIT',
    'WW_BG_WRITE_LIMIT', 'SS_BG_WRITE_LIMIT', 'MM_BG_WRITE_LIMIT',
    'MM_ONLY', 'SS_ONLY', 'WW_ONLY', 'MM_ORDER_CHECK', 'SLOT_SYNC_CHECK',
    'SCD_REPLAY_TRACE', 'MM_DEBUG', 'SS_DEBUG', 'WATER_TRACE', 'WW_TRACE',
    'CDPP_ACTORS', 'SCD_PLAYER_VISUAL_TRACE_FILE')
SCOPE_ENV_KEYS = ('MM_ONLY', 'SS_ONLY', 'WW_ONLY')
NATIVE_ENV_DEPENDENCIES = {
    ('bash', 'tools/test-act-pacing.sh'): (),
    ('bash', 'tools/test-arrival-camera.sh'): (),
    ('bash', 'tools/test-background-cache.sh'): (),
    ('bash', 'tools/test-boss.sh'): (),
    ('bash', 'tools/test-boss6-full.sh'): (),
    ('bash', 'tools/test-camera-bounds.sh'): (),
    ('bash', 'tools/test-cc-bobin.sh'): (),
    ('bash', 'tools/test-cc-cache-replay.sh'): ('SCD_REPLAY_TRACE',),
    ('bash', 'tools/test-cc-drum.sh'): (),
    ('bash', 'tools/test-cc-friend.sh'): (),
    ('bash', 'tools/test-cc-ga.sh'): (),
    ('bash', 'tools/test-cc-gandair.sh'): (),
    ('bash', 'tools/test-cc-generator.sh'): (),
    ('bash', 'tools/test-cc-hari3x-mask.sh'): (),
    ('bash', 'tools/test-cc-kama.sh'): (),
    ('bash', 'tools/test-cc-mecasnc-original.sh'): (),
    ('bash', 'tools/test-cc-mecasnc.sh'): (),
    ('bash', 'tools/test-cc-movie.sh'): (),
    ('bash', 'tools/test-cc-platform.sh'): (),
    ('bash', 'tools/test-cc-pocket.sh'): (),
    ('bash', 'tools/test-cc-sikake33.sh'): (),
    ('bash', 'tools/test-cc-tentou.sh'): (),
    ('bash', 'tools/test-cc-togeball.sh'): (),
    ('bash', 'tools/test-cc-traps.sh'): (),
    ('bash', 'tools/test-cd-status.sh'): (),
    ('bash', 'tools/test-chain-score.sh'): (),
    ('bash', 'tools/test-collapse-spawn.sh'): (),
    ('bash', 'tools/test-foreground-cache.sh'): (),
    ('bash', 'tools/test-limit.sh'): (),
    ('bash', 'tools/test-mm-actors.sh'): ('MM_CFLAGS', 'MM_DEBUG', 'MM_ONLY', 'MM_ORDER_CHECK'),
    ('bash', 'tools/test-mm-cache-replay.sh'): ('MM_BG_WRITE_LIMIT', 'SCD_REPLAY_TRACE'),
    ('bash', 'tools/test-object-stream.sh'): (),
    ('bash', 'tools/test-player.sh'): (),
    ('bash', 'tools/test-playsp3.sh'): (),
    ('bash', 'tools/test-playsp5.sh'): (),
    ('bash', 'tools/test-powerup-runtime.sh'): ('SCD_DATA_ROOT',),
    ('bash', 'tools/test-qq-actors.sh'): ('QQ_CFLAGS',),
    ('bash', 'tools/test-qq-cache-replay.sh'): ('QQ_BG_WRITE_LIMIT', 'SCD_REPLAY_TRACE'),
    ('bash', 'tools/test-save.sh'): (),
    ('bash', 'tools/test-sonic-animation.sh'): ('SCD_DATA_ROOT',),
    ('bash', 'tools/test-sonic-view.sh'): ('SCD_DATA_ROOT',),
    ('bash', 'tools/test-sound-bus.sh'): (),
    ('bash', 'tools/test-spring-contacts.sh'): (),
    ('bash', 'tools/test-spring-side.sh'): (),
    ('bash', 'tools/test-ss-actors.sh'): ('SS_CFLAGS', 'SS_DEBUG', 'SS_ONLY'),
    ('bash', 'tools/test-ss-cache-replay.sh'): ('SCD_REPLAY_TRACE', 'SS_BG_WRITE_LIMIT'),
    ('bash', 'tools/test-swing.sh'): (),
    ('bash', 'tools/test-time-attack.sh'): (),
    ('bash', 'tools/test-title-scale.sh'): (),
    ('bash', 'tools/test-tt-actors.sh'): ('TT_EXTRA',),
    ('bash', 'tools/test-tt-cache-replay.sh'): ('SCD_REPLAY_TRACE', 'TT_BG_WRITE_LIMIT'),
    ('bash', 'tools/test-tt-platforms.sh'): (),
    ('bash', 'tools/test-water-player.sh'): (),
    ('bash', 'tools/test-water.sh'): ('WATER_TRACE',),
    ('bash', 'tools/test-world.sh'): (),
    ('bash', 'tools/test-ww-actors.sh'): ('WW_CFLAGS', 'WW_ONLY', 'WW_TRACE'),
    ('bash', 'tools/test-ww-cache-replay.sh'): ('SCD_REPLAY_TRACE', 'WW_BG_WRITE_LIMIT'),
    ('bash', 'tools/test-zone-objects.sh'): (),
    ('python3', 'tools/test_candidate_identity.py'): (),
    ('python3', 'tools/test_cdpp_player.py'): ('CDPP_ACTORS', 'SCD_PLAYER_VISUAL_TRACE_FILE'),
    ('python3', 'tools/test_feedback.py'): (),
    ('python3', 'tools/test_qq_switch_margin.py'): (),
    ('python3', 'tools/test_sprite_priority.py'): (),
    ('python3', 'tools/test_title_cycles.py'): (),
    ('python3', 'tools/test_world_restart.py'): (),
}
LEGACY_BIOS_INDEPENDENT = frozenset(NATIVE_ENV_DEPENDENCIES)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _sha256(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def _same_json(left, right):
    return json.dumps(left, sort_keys=True, allow_nan=False, separators=(',', ':')) == json.dumps(
        right, sort_keys=True, allow_nan=False, separators=(',', ':'))


def _bound_json(root, pin):
    if (type(pin) is not dict or set(pin) != {'path', 'sha256'}
            or type(pin['path']) is not str or not _sha256(pin['sha256'])):
        raise ValueError('Invalid bound JSON link')
    path = local_path(root, pin['path'])
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != pin['sha256']:
        raise ValueError('Bound JSON changed: ' + str(path))
    return json.loads(raw)


def _native_identity(value):
    return (type(value) is dict and set(value) == {'pid', 'birth'}
        and type(value['pid']) is int and 0 < value['pid'] < 2**31
        and type(value['birth']) is list and len(value['birth']) == 2
        and all(type(n) is int for n in value['birth'])
        and value['birth'][0] > 0 and 0 <= value['birth'][1] < 1000000)


def default_core_profile(root, *, runtime, toolchain, current_core_sha):
    """Read an independently admitted actual build; never query or build a core.

    The coordinator/independent review owns actual tool/native cleanup validation.
    This reader checks its exact pinned receipt, not a second retirement protocol.
    """
    if not _sha256(current_core_sha):
        raise ValueError('Invalid current reference core SHA')
    envelope = json.loads((Path(root)/'build/qa-core-profiles/genesis-default.json').read_bytes())
    if type(envelope) is not dict or set(envelope) != {'protocol', 'build', 'approval'}:
        raise ValueError('Invalid core profile envelope')
    if type(envelope['protocol']) is not int or envelope['protocol'] != 1:
        raise ValueError('Invalid core profile protocol')
    build = _bound_json(root, envelope['build'])
    review = _bound_json(root, envelope['approval'])
    if (review.get('verdict') != 'approved_guarded_core_build'
            or type(review.get('approved_files')) is not dict):
        raise ValueError('Core build lacks independent actual-build approval')
    def approved(pin):
        path = str(local_path(root, pin['path']))
        if review['approved_files'].get(path) != pin['sha256']:
            raise ValueError('Core review does not bind: ' + path)
    approved(envelope['build'])
    required = {'schema', 'profile', 'status', 'actual_build', 'metadata_only',
                'sources', 'runtime', 'toolchain', 'recipe', 'commands', 'output', 'execution'}
    if (type(build) is not dict or set(build) != required
            or build['schema'] != 'genesis-default-core-build-v1'
            or build['profile'] != 'genesis-default-v1' or build['status'] != 'passed'
            or build['actual_build'] is not True or build['metadata_only'] is not False
            or not _same_json(build['runtime'], runtime)
            or not _same_json(build['toolchain'], toolchain)):
        raise ValueError('Core build profile/runtime differs')
    sources = build['sources']
    required_sources = {'.deps/genesis-plus-gx/' + p for p in (
        'Makefile.libretro', 'libretro/libretro.c', 'core/loadrom.c',
        'core/cd_hw/cdd.c', 'core/cd_hw/cd_cart.c')}
    if type(sources) is not dict or not required_sources <= set(sources):
        raise ValueError('Incomplete core build source set')
    for name, value in sources.items():
        if (type(name) is not str or not name.startswith('.deps/genesis-plus-gx/')
                or '..' in Path(name).parts or not _sha256(value)
                or digest(local_path(root, name)) != value):
            raise ValueError('Core build source/dependency changed: ' + str(name))
    recipe = _bound_json(root, build['recipe'])
    approved(build['recipe'])
    planned, commands = recipe.get('commands'), build['commands']
    if (type(planned) is not list or type(commands) is not list
            or len(planned) != 116 or len(commands) != len(planned)):
        raise ValueError('Incomplete actual core compile/link commands')
    for index, (plan, command) in enumerate(zip(planned, commands)):
        expected_kind = 'compile' if index < 115 else 'link'
        if (type(command) is not dict
                or set(command) != {'kind', 'argv', 'exit_code', 'log', 'output', 'dependency_paths'}
                or command['kind'] != expected_kind or plan.get('kind') != expected_kind
                or not _same_json(command['argv'], plan.get('argv'))
                or type(command['exit_code']) is not int or command['exit_code'] != 0
                or type(command['argv']) is not list or not command['argv']
                or any(type(a) is not str for a in command['argv'])
                or command['argv'][0] != toolchain.get('compiler')
                or type(command['dependency_paths']) is not list
                or any(type(p) is not str or p not in sources for p in command['dependency_paths'])):
            raise ValueError('Core command differs from reviewed recipe')
        for key in ('log',):
            pin = command[key]
            if digest(local_path(root, pin['path'])) != pin['sha256']:
                raise ValueError('Core command log changed')
        output = command['output']
        if (type(output) is not dict or set(output) != {'path', 'size', 'sha256'}
                or output['path'] != plan.get('output') or not _sha256(output['sha256'])
                or type(output['size']) is not int or output['size'] < 1):
            raise ValueError('Invalid core command output')
        path = local_path(root, output['path'])
        if path.stat().st_size != output['size'] or digest(path) != output['sha256']:
            raise ValueError('Core command output changed')
    if not _same_json(build['output'], commands[-1]['output']):
        raise ValueError('Core final output does not bind actual link')
    if build['output']['sha256'] != current_core_sha:
        raise ValueError('Current core does not match actual source build')
    execution = build['execution']
    if type(execution) is not dict or set(execution) != {'command', 'guard', 'cleanup'}:
        raise ValueError('Invalid core execution binding')
    guard = _bound_json(root, execution['guard'])
    cleanup = _bound_json(root, execution['cleanup'])
    approved(execution['guard']); approved(execution['cleanup'])
    if (guard.get('status') != 'passed' or guard.get('passed') is not True
            or guard.get('changed_inputs')!=[] or type(guard.get('exit_code')) is not int
            or guard['exit_code'] != 0 or not _same_json(guard.get('command'), execution['command'])
            or not _native_identity(guard.get('root_identity'))
            or guard.get('cleanup_survivors') != [] or guard.get('cleanup_error')
            or type(guard.get('owned_processes')) is not list):
        raise ValueError('Core guard is not terminal clean')
    if (cleanup.get('schema') != 'guarded-core-build-cleanup-v1'
            or cleanup.get('status') != 'passed'
            or not _same_json(cleanup.get('guard'), execution['guard'])
            or not _same_json(cleanup.get('root_identity'), guard['root_identity'])
            or cleanup.get('survivors') != [] or cleanup.get('uncertain_roots') != []
            or cleanup.get('coordinator_tool_and_native_binding_verified') is not True):
        raise ValueError('Core cleanup binding is not admitted')
    audited = cleanup.get('audited_generations')
    if (type(audited) is not list or any(not _native_identity(row) for row in audited)
            or len({(row['pid'], tuple(row['birth'])) for row in audited}) != len(audited)):
        raise ValueError('Invalid independently audited core generations')
    declared = [guard['root_identity']]
    for row in guard['owned_processes']:
        identity = dict(pid=row.get('pid'), birth=row.get('birth')) if type(row) is dict else None
        if not _native_identity(identity):
            raise ValueError('Malformed raw guard owned generation')
        declared.append(identity)
    if any(row not in audited for row in declared):
        raise ValueError('Core cleanup omits a raw declared generation')
    return envelope


CONSUMER_PROTOCOL = 1
_NATIVE_EXTRA = {
    'tools/test-act-pacing.sh': ('.deps/beetle-saturn/libretro-common/include/libretro.h',),
    'tools/test-cd-status.sh': tuple('.deps/libyaul/libyaul/scu/bus/a/cs2/cd-block/' + p for p in
        ('cd-block_cmds.c', 'cd-block-internal.h', 'cd-block/cmd.h', 'cd-block_init.c')),
    'tools/test-cc-cache-replay.sh': ('build/cc2/controller/A/results.log',),
    'tools/test-sonic-view.sh': ('build/sonic-animation/expected-frames.bin',),
    'tools/test-cc-gandair.sh': ('build/cc1/traps/original.c', 'build/cc1/gandair/retail-animation.json'),
    'tools/test-cc-pocket.sh': ('build/retail/fm-driver.bin',),
}
_REFERENCE_PROGRAMS = ('IPX___.MMD', 'SPMM__.MMD', 'SPSS__.BIN', 'SPX___.BIN',
                       'BRAMINIT.MMD', 'MDINIT.MMD')
_REFERENCE_FIRMWARE = tuple('assets/private/' + name for name in
    ('bios_CD_U.bin', 'bios_CD_E.bin', 'bios_CD_J.bin', 'scd_U.brm', 'scd_E.brm', 'scd_J.brm'))
_LIBRETRO_HEADER = '.deps/beetle-saturn/libretro-common/include/libretro.h'
_INPUT_DIRECTORY = 'build/qa-input-bindings'
_PALETTE_COMMAND = ['python3','tools/test_cc_palette.py']
_PALETTE_POINTER = _INPUT_DIRECTORY+'/cc-palette-current.json'
_ALTERNATE_SOURCE_LIMIT = 'Alternate SCD_DATA_ROOT is outside the default cache input recipe'


def _durable_once(path,raw):
    """Publish immutable bytes in an existing directory with durable linkage."""
    from qa_limits import _sync_file
    import tempfile
    path=Path(path)
    if not path.parent.is_dir() or path.parent!=path.parent.resolve() or path.is_symlink():
        raise ValueError('Missing or aliased immutable output parent')
    if path.exists():
        if path.read_bytes()!=raw:raise ValueError('Immutable output bytes differ')
        descriptor=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)
        return
    descriptor,temporary=tempfile.mkstemp(prefix='.'+path.name+'.',suffix='.pending',dir=path.parent)
    published=False
    try:
        with os.fdopen(descriptor,'wb') as stream:
            stream.write(raw);stream.flush();_sync_file(stream.fileno())
            if path.exists() or path.is_symlink():
                if path.is_symlink() or path.read_bytes()!=raw:raise ValueError('Immutable publication race')
            else:
                os.replace(temporary,path);published=True
                parent=os.open(path.parent,os.O_RDONLY)
                try:os.fsync(parent)
                finally:os.close(parent)
                ancestor=os.open(path.parent.parent,os.O_RDONLY)
                try:os.fsync(ancestor)
                finally:os.close(ancestor)
                _sync_file(stream.fileno())
    finally:
        if not published:
            import sys
            primary=sys.exc_info()[1]
            try:os.unlink(temporary)
            except BaseException as error:
                if primary is None:raise
                primary.add_note('Immutable temporary cleanup failed: '+repr(error))


def consumer_environment(context,command):
    """Only the palette oracle producer needs a pinned compiler dispatch."""
    if command!=_PALETTE_COMMAND:return None
    import sys
    toolchain=context['toolchain']
    interpreter=shutil.which('python3')
    if interpreter is None or Path(interpreter).resolve()!=Path(sys.executable).resolve():
        raise ValueError('Palette python3 dispatch differs from the actual caller runtime')
    path=None
    python_dir,compiler_dir=str(Path(interpreter).parent),str(Path(toolchain['compiler']).parent)
    for first,second in ((python_dir,compiler_dir),(compiler_dir,python_dir)):
        candidate=first+':'+second+':/usr/bin:/bin:/usr/sbin:/sbin'
        selected=shutil.which('clang',path=candidate);python=shutil.which('python3',path=candidate)
        if (selected is not None and Path(selected).resolve()==Path(toolchain['compiler'])
                and python is not None and Path(python).resolve()==Path(sys.executable).resolve()):
            path=candidate;break
    if path is None:
        raise ValueError('Palette clang dispatch differs from the pinned physical compiler')
    result=dict(PATH=path,
                SDKROOT=toolchain['sdk'],LC_ALL='C',PYTHONDONTWRITEBYTECODE='1')
    for name in ('TMPDIR','SCD_QA_CONSUMER_CONTEXT','SCD_QA_MAX_WORKERS','SCD_QA_MAX_EMULATORS',
                 'SCD_QA_COOLDOWN_SECONDS','SCD_NICE'):
        if name in os.environ:result[name]=os.environ[name]
    return result


def _palette_inputs():
    names=['src/background.c','src/background.h','src/background_r3.c','src/background_r3.h',
           'src/background_r3_tables.inc','assets/generated/background.inc','build/auto-extract/3/report.json',
           'build/cc1/palette-source.json','tools/test_cc_palette.py','tools/cc_palette_source.py',
           'tools/prepare_background.py','tools/extract_zone_auto.py','tools/convert_assets.py','tools/extract_mmd.py',
           'build/retail/sonic.iso']
    names += ['.deps/soniccd/src/R3/'+prefix+e+'.C' for prefix in ('COL3','DEV31') for e in 'ABCD']
    names += ['assets/generated/cc31'+e+'.bin' for e in 'ABCD']
    return names


def _palette_outputs():
    return tuple('build/cc1/palette/original-'+e+suffix for e in 'ABCD' for suffix in ('.c','.dylib'))+(
        'build/cc1/palette-source.json','build/cc1/palette/report.json','build/cc1/palette/native.dylib')


def _palette_toolchain(context):
    toolchain=context['toolchain'];compiler=Path(toolchain['compiler']);sdk=Path(toolchain['sdk'])
    if (not compiler.is_absolute() or compiler!=compiler.resolve()
            or (compiler.parent/'clang').resolve()!=compiler
            or digest(compiler)!=toolchain['compiler_sha256']
            or sdk.stat().st_dev!=toolchain['sdk_device'] or sdk.stat().st_ino!=toolchain['sdk_inode']
            or digest(sdk/'SDKSettings.json')!=toolchain['sdk_settings_sha256']):
        raise ValueError('Palette physical compiler/SDK changed')


def palette_source_join(root):
    """Rederive original source/retail script proof without publishing files."""
    import ast
    def function(path,name):
        return next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name==name)
    generator=copy.deepcopy(function(Path(root)/'tools/cc_palette_source.py','generate'))
    class OutputOnly(ast.NodeTransformer):
        mkdir=0;write=0
        def visit_Expr(self,node):
            if isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Attribute):
                call=node.value
                if call.func.attr=='mkdir':self.mkdir+=1;return None
                if call.func.attr=='write_text':
                    self.write+=1
                    return ast.copy_location(ast.Expr(value=ast.Call(func=ast.Attribute(value=ast.Name(id='captured',ctx=ast.Load()),attr='append',ctx=ast.Load()),args=call.args,keywords=[])),node)
            return self.generic_visit(node)
    transform=OutputOnly();generator=transform.visit(generator)
    if (transform.mkdir,transform.write)!=(1,1):raise ValueError('Palette generator output shape changed')
    namespace=dict(ROOT=Path(root),hashlib=hashlib,json=json,re=re,struct=struct,captured=[])
    definitions=[function(Path(root)/'tools/extract_mmd.py','disc_files'),function(Path(root)/'tools/convert_assets.py','palette'),generator]
    exec(compile(ast.fix_missing_locations(ast.Module(body=definitions,type_ignores=[])),'<original palette proof without output>','exec'),namespace)
    namespace['generate']()
    _,actual=_input_json(root,'build/cc1/palette-source.json')
    expected=json.loads(namespace['captured'][0])
    if not _same_json(actual,expected):raise ValueError('Palette source metadata differs from original source/retail proof')
    return hashlib.sha256(json.dumps(expected,sort_keys=True).encode()).hexdigest()


def palette_producer_join(root,context,era=None):
    if era is not None and (type(era) is not str or era not in 'ABCD' or len(era)!=1):
        raise ValueError('Invalid palette consumer era')
    _palette_toolchain(context)
    pointer=json.loads(_input_path(root,_PALETTE_POINTER).read_bytes())
    receipt=_bound_json(root,pointer)
    before=read_consumer_inputs(root,receipt['inputs'])
    report=_bound_json(root,receipt['producer_report'])
    validate_palette_producer_metadata(receipt,before,report)
    if not _same_json(receipt['context'],context):raise ValueError('Palette producer epoch differs')
    if (not _same_json(before['context'],context) or
            not _same_json(before['recipe'],consumer_spec(root,[_PALETTE_COMMAND]))):
        raise ValueError('Palette input recipe/epoch differs')
    verify_consumer_inputs(root,before)
    for name,value in receipt['files'].items():
        if era is not None and name not in ('build/cc1/palette/original-'+era+'.dylib','build/cc1/palette-source.json'):
            continue
        if not _same_json(_input_file(root,name),value):raise ValueError('Palette producer output changed: '+name)
    if digest(local_path(root,receipt['log']['path']))!=receipt['log']['sha256']:
        raise ValueError('Palette producer actual log changed')
    if palette_source_join(root)!=receipt['palette_source_sha256']:
        raise ValueError('Palette source proof changed')
    return pointer


def validate_palette_producer_metadata(receipt,before,report):
    """Immutable historical facts only. Caller pins report/CAS/log bytes via IO."""
    _consumer_bytes(before)
    if (type(report) is not dict or type(receipt) is not dict or set(receipt)!={'protocol','kind','command','exit_code','context','inputs','files','log',
                                                 'palette_source_sha256','palette_source','producer_report'}
            or type(receipt['protocol']) is not int or receipt['protocol']!=1
            or receipt['kind']!='cc-palette-producer-v1' or receipt['command']!=_PALETTE_COMMAND
            or type(receipt['exit_code']) is not int or receipt['exit_code']!=0
            or not _same_json(receipt['context'],before['context'])
            or before['recipe']['key']!={'kind':'step','commands':[_PALETTE_COMMAND]}
            or set(before['files'])!=set(_palette_inputs()) or not before['complete']):
        raise ValueError('Palette producer epoch/receipt differs')
    if not _same_json(receipt['inputs'],consumer_input_seal(before)):
        raise ValueError('Palette producer input CAS binding differs')
    if type(receipt['files']) is not dict or set(receipt['files'])!=set(_palette_outputs()):
        raise ValueError('Palette output receipt is incomplete')
    for name,value in receipt['files'].items():
        if (type(value) is not dict or set(value)!={'present','size','sha256'} or value['present'] is not True
                or type(value['size']) is not int or value['size']<1 or not _sha256(value['sha256'])):
            raise ValueError('Malformed palette output record')
    for field in ('log','producer_report'):
        pin=receipt[field]
        if type(pin) is not dict or set(pin)!={'path','sha256'} or type(pin['path']) is not str or not _sha256(pin['sha256']):
            raise ValueError('Invalid palette producer artifact pin')
    if (receipt['producer_report']['sha256']!=receipt['files']['build/cc1/palette/report.json']['sha256']
            or report.get('passed') is not True or report.get('status')!='passed'):
        raise ValueError('Palette producer report is not bound/passed')
    for key,wanted in (('frames_per_era',8193),('frames',4*8193),('colors',4*8193*64),('repeated_paused_frames',4*8193)):
        if type(report.get(key)) is not int or report[key]!=wanted:raise ValueError('Palette producer functional counts differ')
    traces=report.get('palette_trace_sha256')
    if type(traces) is not dict or set(traces)!=set('ABCD') or any(not _sha256(v) for v in traces.values()) or len(set(traces.values()))!=4:
        raise ValueError('Palette producer era traces differ')
    for field in ('inputs','run_inputs'):
        if type(report.get(field)) is not dict or not report[field]:raise ValueError('Palette source inputs absent')
        for name,sha in report[field].items():
            if before['files'].get(name,{}).get('sha256')!=sha:raise ValueError('Palette source input is not captured')
    source=receipt['palette_source']
    if (type(source) is not dict or set(source)!=set('ABCD') or not _sha256(receipt['palette_source_sha256'])
            or hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest()!=receipt['palette_source_sha256']
            or before['joins'].get('palette_source_sha256')!=receipt['palette_source_sha256']):
        raise ValueError('Palette source proof is not bound')
    for era in 'ABCD':
        if (source[era]['source_sha256']!=before['files']['.deps/soniccd/src/R3/COL3'+era+'.C']['sha256']
                or report['eras'][era]['mmd_sha256']!=source[era]['program_sha256']
                or report['eras'][era]['pack_sha256']!=before['files']['assets/generated/cc31'+era+'.bin']['sha256']):
            raise ValueError('Palette source/retail/pack join differs')


def _input_path(root, name):
    root = Path(root).resolve()
    if type(name) is not str or not name or '..' in Path(name).parts:
        raise ValueError('Invalid consumer input path')
    path = Path(name)
    if not path.is_absolute():
        path = root/path
    if path != path.resolve() or not path.is_relative_to(root):
        raise ValueError('Consumer input alias/outside repository')
    return path


def _stat_identity(info):
    # Reads may update atime. Content/ownership changes must still fail closed.
    return tuple(getattr(info,k) for k in ('st_dev','st_ino','st_mode','st_size','st_mtime_ns','st_ctime_ns'))


def _input_file(root, name):
    path = _input_path(root, name)
    if not path.exists():
        return dict(present=False)
    before = path.stat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError('Consumer input is not regular')
    value = dict(present=True, size=before.st_size, sha256=digest(path))
    after = path.stat()
    if tuple(getattr(before, k) for k in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')) != tuple(
            getattr(after, k) for k in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')):
        raise ValueError('Consumer input changed while hashing')
    return value


def _input_json(root, name):
    path = _input_path(root, name)
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > 32*1024*1024:
        raise ValueError('Invalid consumer JSON file')
    raw = path.read_bytes()
    after = path.stat()
    if _stat_identity(before) != _stat_identity(after):
        raise ValueError('Consumer JSON changed while reading')
    return dict(present=True, size=len(raw), sha256=hashlib.sha256(raw).hexdigest()), json.loads(raw)


def cue_input_graph(root, cue, *, loader_profile):
    """Strict local BINARY CUE subset emitted by the reviewed default producers.

    Unsupported core syntaxes are cache misses, never rewritten CUEs. No payload
    is copied. Hash every FILE body, even when many tracks share one FILE.
    """
    if loader_profile not in ('saturn-default-v1', 'genesis-default-v1'):
        raise ValueError('Unsupported media loader profile')
    path = _input_path(root, cue)
    before = path.stat()
    raw = path.read_bytes()
    if _stat_identity(before) != _stat_identity(path.stat()):
        raise ValueError('CUE changed while reading')
    descriptor = dict(present=True, size=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    files, tracks, current, index, graph = {}, [], None, None, []
    for line in raw.decode('utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('REM '):
            continue
        match = re.fullmatch(r'FILE\s+(?:"([^"\r\n]+)"|(\S+))\s+BINARY', line)
        if match:
            name = match[1] or match[2]
            if '://' in name or '\\' in name or Path(name).is_absolute():
                raise ValueError('Unsupported CUE FILE scheme')
            target = _input_path(root, str(path.parent/name))
            # The two loaders agree for canonical absolute/local relative paths.
            current = str(target.relative_to(Path(root).resolve()))
            index = None
            files[current] = _input_file(root, current)
            if not files[current]['present']:
                raise ValueError('Missing CUE FILE target')
            graph.append(current)
            continue
        match = re.fullmatch(r'TRACK\s+(\d{2})\s+(MODE1/2352|MODE1/2048|AUDIO)', line)
        if match:
            if current is None or int(match[1]) != len(tracks)+1:
                raise ValueError('Invalid CUE track order')
            index = dict(number=int(match[1]), type=match[2], file=current, indices={})
            tracks.append(index)
            continue
        match = re.fullmatch(r'PREGAP\s+([0-9]{2}):([0-9]{2}):([0-9]{2})', line)
        if match:
            if (index is None or index['indices'] or 'pregap_frames' in index
                    or int(match[2]) >= 60 or int(match[3]) >= 75):
                raise ValueError('Invalid CUE pregap')
            # Keep the explicit gap separate from positions in the FILE body.
            index['pregap_frames'] = int(match[1])*4500+int(match[2])*75+int(match[3])
            continue
        match = re.fullmatch(r'INDEX\s+(00|01)\s+(\d+):(\d{2}):(\d{2})', line)
        if match:
            if index is None or match[1] in index['indices'] or int(match[3]) >= 60 or int(match[4]) >= 75:
                raise ValueError('Invalid CUE index')
            index['indices'][match[1]] = int(match[2])*4500+int(match[3])*75+int(match[4])
            continue
        raise ValueError('Unsupported CUE statement: ' + line[:80])
    if not tracks or not graph:
        raise ValueError('Empty CUE graph')
    for i, track in enumerate(tracks):
        positions = track['indices']
        sector = 2048 if track['type'] == 'MODE1/2048' else 2352
        if ('01' not in positions or positions.get('00', positions['01']) > positions['01']
                or files[track['file']]['size'] % sector
                or positions['01']*sector >= files[track['file']]['size']):
            raise ValueError('CUE index/FILE size differs')
        if i and track['file'] == tracks[i-1]['file'] and positions['01'] <= tracks[i-1]['indices']['01']:
            raise ValueError('CUE indices are not ordered')
    sidecar = None
    if loader_profile == 'saturn-default-v1':
        extension = ''.join(c.upper() if x.isupper() else c for c, x in zip('sbi', path.suffix[1:]))
        if len(extension) != 3:
            raise ValueError('Unsupported native CUE extension')
        side = path.with_suffix('.'+extension)
        name = str(side.relative_to(Path(root).resolve()))
        files[name] = _input_file(root, name)
        sidecar = name
    return dict(profile=loader_profile, cue=str(path.relative_to(Path(root).resolve())),
                descriptor=descriptor, file_occurrences=graph, files=files,
                tracks=tracks, sidecar=sidecar)


def _placement_paths(rounds):
    return ['build/auto-extract/%d/objects%d%d%s.bin' % (r, r, a, e)
            for r in rounds for a in (1, 2, 3) for e in ('CD' if a == 3 else 'ABCD')]


def reference_program_join(root, graph):
    """Join actual boot data and path-loaded programs to the sealed ISO.

    Uses the unchanged extractor's disc_files definition. This does not infer
    anything from an extraction stamp or a prior missing-file shortcut.
    """
    import ast
    iso_path = _input_path(root, 'build/retail/sonic.iso')
    raw = iso_path.read_bytes()
    if not raw or len(raw) % 2048:
        raise ValueError('Invalid reference ISO size')
    first = graph['tracks'][0]
    if first['type'] not in ('MODE1/2352','MODE1/2048') or first['indices']['01'] != 0:
        raise ValueError('Unsupported default reference data track')
    sector = 2352 if first['type'] == 'MODE1/2352' else 2048
    offset = 16 if sector == 2352 else 0
    target = _input_path(root,first['file'])
    with target.open('rb') as stream:
        for pos in range(0,len(raw),2048):
            block = stream.read(sector)
            if len(block) != sector or block[offset:offset+2048] != raw[pos:pos+2048]:
                raise ValueError('Reference boot media data differs from ISO')
    if len(graph['tracks']) > 1 and graph['tracks'][1]['file'] == first['file']:
        following = graph['tracks'][1]['indices']
        if following.get('00',following['01']) != len(raw)//2048:
            raise ValueError('Reference ISO does not cover the default data track')
    tree = ast.parse((Path(root)/'tools/extract_mmd.py').read_text())
    function = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='disc_files')
    namespace = {'struct':struct}
    exec(compile(ast.Module(body=[function],type_ignores=[]),'<original disc_files>','exec'),namespace)
    disc = namespace['disc_files'](raw)
    for name in _REFERENCE_PROGRAMS:
        if _input_path(root,'build/retail/'+name).read_bytes() != disc[name]:
            raise ValueError('Extracted reference program differs from ISO: '+name)
    return dict(iso_sha256=hashlib.sha256(raw).hexdigest(),
                programs={name:hashlib.sha256(disc[name]).hexdigest() for name in _REFERENCE_PROGRAMS})



# Source-defined, finite prospective producers. Existing captures are never
# adopted from their script-only stamps. A new receipt needs an actual exit0.
_FIXED_PRODUCERS = {
    'secret-images': dict(command=['python3','tools/secret_images_retail.py'],
        directory='build/secret-images', report='build/secret-images/retail.json',
        outputs=tuple('build/secret-images/retail-'+str(n)+'.rgb565' for n in range(1,6))+('build/secret-images/retail.json',)),
    'visual-images': dict(command=['python3','tools/visual_mode_retail.py'],
        directory='build/visual-mode', report='build/visual-mode/retail.json',
        outputs=tuple('build/visual-mode/retail-'+n+'.rgb565' for n in
            ('sel0','sel1','sel2','sel3','sel4','wrap0','up4','right3','left4'))+('build/visual-mode/retail.json',)),
    'special-win-pad': dict(command=['python3','tools/special_retail.py','win'],
        directory=None,report=None,outputs=('build/special-retail/win.pad','build/special-retail/win.jsonl','build/special-retail/win-blobs.json')),
    'special-timeout-pad': dict(command=['python3','tools/special_retail.py','timeout'],
        directory=None,report=None,outputs=('build/special-retail/timeout.pad','build/special-retail/timeout.jsonl','build/special-retail/timeout-blobs.json')),
    'frontend-thresholds': dict(command=['python3','tools/test_frontend_emulator.py','ta-thresholds'],
        directory='build/frontend-qa',report='build/frontend-qa/report.json',
        outputs=('build/frontend-qa/fixture-total154611.bin','build/frontend-qa/report.json')),
    'cdpp-toggle': dict(command=['python3','tools/test_cdpp_routes.py','toggle'],
        directory='build/cdpp-qa',report='build/cdpp-qa/report.json',
        outputs=('build/cdpp-qa/backup-cdpp.bin','build/cdpp-qa/report.json')),
}
_SATURN_CONSUMER_FILES = (_LIBRETRO_HEADER,'build/saturn/sonic-cd-saturn-prototype.elf',
    '.toolchain/bin/sh-elf-nm','.deps/beetle-saturn/mednafen_saturn_libretro.dylib',*BIOS_PATHS)



def fixed_producer_source_paths(producer):
    definition=_FIXED_PRODUCERS[producer]
    files=[definition['command'][1]]
    if producer=='frontend-thresholds':
        files += ['tools/frontend_emulator_test.c','tools/title_menu.py','tests/routes/ppz/p0A.seq.txt']
    if producer in ('cdpp-toggle','frontend-thresholds'):return sorted(set(files+list(_SATURN_CONSUMER_FILES)))
    files += list(_REFERENCE_FIRMWARE)+['build/retail/'+p for p in _REFERENCE_PROGRAMS]
    files += ['build/retail/sonic.iso.sha256.json']
    files += ['.deps/scddisasm/src/'+n for n in ('Special Stage/_Common.inc',
        '_Include/Main CPU Variables.inc','Special Stage/Main.asm','Special Stage/Sub.asm','_Include/System.inc')]
    if producer=='visual-images':files.append('.deps/scddisasm/src/Visual Mode/Main.asm')
    if producer=='special-win-pad':files.append('build/special-retail/win-route.json')
    return sorted(set(files))


def fixed_producer_requirements(commands):
    """Only imported persistent inputs of the unchanged default call chains."""
    required=[]
    for command in commands:
        if len(command)<2:continue
        tool=command[1]
        if tool=='tools/visual_mode_pixels.py':required.append('visual-images')
        if tool=='tools/test_frontend_emulator.py':
            cases=command[2:]
            if not cases or 'sound-test-images' in cases:required.append('secret-images')
            if not cases or any(c in cases for c in ('visual-mode','visual-mode-movies')):
                required.append('visual-images')
                if cases and 'ta-thresholds' not in cases:required.append('frontend-thresholds')
            if not cases or 'attract-demos-cdpp' in cases:required.append('cdpp-toggle')
        if tool=='tools/test-bigring-emulator.sh' or (tool=='tools/test_special_entry.py' and command[2:3]==['ppz']):
            required += ['special-timeout-pad','special-win-pad']
        if tool=='tools/test_ending_emulator.py':
            # --case good/bad excludes the STONES return-ring fixture.
            if '--case' not in command or command[command.index('--case')+1]=='stones':required.append('special-win-pad')
    return list(dict.fromkeys(required))


def fixed_producer_command(producer):
    return list(_FIXED_PRODUCERS[producer]['command'])


def fixed_producer_consumed_paths(producer):
    paths=_FIXED_PRODUCERS[producer]['outputs']
    if producer in ('cdpp-toggle','frontend-thresholds') or producer.endswith('-pad'):return paths[:1]
    return paths


def _fixed_pointer(producer):
    if producer not in _FIXED_PRODUCERS:raise ValueError('Unknown fixed producer')
    return _INPUT_DIRECTORY+'/'+producer+'-current.json'


def validate_fixed_producer_metadata(receipt, before, report):
    """Historical IO-only validation. No current mutable output is read here."""
    if (type(receipt) is not dict or set(receipt)!={'protocol','kind','producer','command','exit_code','context','inputs','files','log','producer_report'}
            or type(receipt['protocol']) is not int or receipt['protocol']!=1
            or receipt['kind']!='fixed-input-producer-v1' or type(receipt['producer']) is not str or receipt['producer'] not in _FIXED_PRODUCERS):
        raise ValueError('Invalid fixed producer receipt')
    producer=receipt['producer']; definition=_FIXED_PRODUCERS[producer]
    _consumer_bytes(before)
    if (receipt['command']!=definition['command'] or type(receipt['exit_code']) is not int or receipt['exit_code']!=0
            or not _same_json(receipt['context'],before['context']) or before['complete'] is not True
            or not _same_json(before['recipe']['key'],dict(kind='step',commands=[definition['command']],fixed_producer=producer))
            or before['recipe']['native'] is not False
            or not _same_json(before['recipe']['media'],[('dist/sonic-cd-saturn-prototype.cue','saturn-default-v1')]
                if producer in ('cdpp-toggle','frontend-thresholds') else [('build/retail/sonic.cue','genesis-default-v1')])
            or before['recipe']['files']!=fixed_producer_source_paths(producer)
            or not _same_json(receipt['inputs'],consumer_input_seal(before))):
        raise ValueError('Fixed producer lacks successful complete bound execution')
    if type(receipt['files']) is not dict or set(receipt['files'])!=set(definition['outputs']):
        raise ValueError('Fixed producer output set differs')
    for value in receipt['files'].values():
        if (type(value) is not dict or set(value)!={'present','size','sha256'} or value['present'] is not True
                or type(value['size']) is not int or value['size']<=0 or not _sha256(value['sha256'])):
            raise ValueError('Malformed fixed producer output')
    for pin in (receipt['log'],receipt['producer_report']):
        if pin is not None and (type(pin) is not dict or set(pin)!={'path','sha256'}
                or type(pin['path']) is not str or not _sha256(pin['sha256'])):
            raise ValueError('Malformed fixed producer text pin')
    if receipt['log'] is None:raise ValueError('Fixed producer log absent')
    if definition['report'] is None:
        if report is not None or receipt['producer_report'] is not None:raise ValueError('Unexpected pad producer report')
    elif (type(report) is not dict or receipt['producer_report'] is None
            or receipt['producer_report']['sha256']!=receipt['files'][definition['report']]['sha256']):
        raise ValueError('Fixed producer report pin absent')
    if producer in ('cdpp-toggle','frontend-thresholds'):
        if (report.get('disc_sha256')!=before['context']['bin_sha256']
                or report.get('elf_sha256')!=before['files']['build/saturn/sonic-cd-saturn-prototype.elf'].get('sha256')):
            raise ValueError('Saturn fixture producer image binding differs')
    if producer=='frontend-thresholds':
        cases=report.get('cases',[])
        if (report.get('passed') is not True or report.get('status')!='passed'
                or not any(type(c) is dict and c.get('name')=='ta-thresholds' for c in cases)):
            raise ValueError('Threshold fixture producer assertions absent')
    if producer=='cdpp-toggle':
        case=report.get('cases',{}).get('toggle',{})
        import zlib
        settings=b'SCDC'+bytes([1,16,1,31])+bytes(4)
        settings+=struct.pack('>I',zlib.crc32(settings))
        if (report.get('passed') is not True or report.get('status')!='passed' or case.get('passed') is not True
                or type(case.get('slot11_before')) is not int or (case['slot11_before']>>8&255)!=0
                or type(case.get('slot11_after')) is not int or (case['slot11_after']>>8&255)!=31
                or not _same_json(case.get('cold_boot'),dict(cdpp=31,damaged=0,empty=0))
                or case.get('file')!=settings.hex()
                or case.get('backup_sha256')!=receipt['files']['build/cdpp-qa/backup-cdpp.bin']['sha256']):
            raise ValueError('CD++ toggle producer assertions absent')
    if producer in ('secret-images','visual-images'):
        summary=report if producer=='secret-images' else report.get('summary',{})
        tool=definition['command'][1]; inputs=summary.get('inputs',{})
        pins={Path(tool).name:tool,'sonic.iso.sha256.json':'build/retail/sonic.iso.sha256.json'}
        if producer=='visual-images':pins['IPX___.MMD']='build/retail/IPX___.MMD'
        if any(inputs.get(k)!=before['files'].get(p,{}).get('sha256') for k,p in pins.items()):
            raise ValueError('Image producer source report differs')
        if producer=='secret-images' and any(type(summary.get(str(n))) is not dict for n in range(1,6)):
            raise ValueError('Secret image producer cases absent')
        if producer=='visual-images' and (type(summary.get('shots')) is not dict or set(summary['shots'])!=
                {'sel0','sel1','sel2','sel3','sel4','wrap0','up4','right3','left4'}):
            raise ValueError('Visual image producer shots absent')
    return receipt


def fixed_producer_join(root,context,producer):
    _,link=_input_json(root,_fixed_pointer(producer))
    receipt=_bound_json(root,link)
    before=read_consumer_inputs(root,receipt['inputs'])
    report=_bound_json(root,receipt['producer_report']) if receipt['producer_report'] else None
    validate_fixed_producer_metadata(receipt,before,report)
    if (not _same_json(context,receipt['context']) or not _same_json(before['recipe'],consumer_spec(root,[fixed_producer_command(producer)]))):
        raise ValueError('Fixed producer context/recipe differs')
    verify_consumer_inputs(root,before)
    for name in fixed_producer_consumed_paths(producer):
        if not _same_json(_input_file(root,name),receipt['files'][name]):raise ValueError('Fixed producer output changed: '+name)
    if digest(local_path(root,receipt['log']['path']))!=receipt['log']['sha256']:raise ValueError('Fixed producer log changed')
    return link


def fixed_setup_commands(root,context,commands):
    requested=[]
    for producer in fixed_producer_requirements(commands):
        try:fixed_producer_join(root,context,producer)
        except (OSError,ValueError,TypeError,KeyError):
            if producer=='special-win-pad' and not (Path(root)/'build/special-retail/win-route.json').is_file():
                requested.append(['python3','tools/special_route.py'])
            requested.append(fixed_producer_command(producer))
    return requested


def preserve_fixed_producer_outputs(root,command):
    """Rename old outputs before a fresh producer. No bulk copy or old receipt."""
    import datetime
    producer=next((p for p,d in _FIXED_PRODUCERS.items() if d['command']==command),None)
    if producer is None:return []
    definition=_FIXED_PRODUCERS[producer]; root=Path(root).resolve()
    suffix='.before-input-producer-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    if definition['directory']:
        paths=[root/definition['directory']]
    else:
        route=command[-1]; folder=root/'build/special-retail'
        paths=[root/n for n in definition['outputs']]
        if folder.is_dir():paths+=list(folder.glob(route+'-v*.png'))
    retained=[]
    for path in paths:
        if path.is_symlink() or path.parent!=path.parent.resolve():raise ValueError('Aliased producer output')
        if path.exists():
            target=path.with_name(path.name+suffix)
            path.rename(target);retained.append(dict(before=str(path.relative_to(root)),retained=str(target.relative_to(root))))
    return retained


def publish_fixed_producer(root,command,context,consumer,log,exit_code):
    producer=next((p for p,d in _FIXED_PRODUCERS.items() if d['command']==command),None)
    if producer is None:return None
    if type(exit_code) is not int or exit_code!=0:raise ValueError('Fixed producer did not exit0')
    verify_consumer_inputs(root,consumer)
    preserve_consumer_inputs(root,consumer)
    definition=_FIXED_PRODUCERS[producer]
    files={p:_input_file(root,p) for p in definition['outputs']}
    report=None; report_link=None
    if definition['report']:
        path=_input_path(root,definition['report']); raw=path.read_bytes();report=json.loads(raw)
        observed=dict(present=True,size=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        if not _same_json(observed,files[definition['report']]):raise ValueError('Producer report changed during capture')
        report_link=dict(path=_INPUT_DIRECTORY+'/fixed-report-'+observed['sha256']+'.json',sha256=observed['sha256'])
        _durable_once(Path(root)/report_link['path'],raw)
    if digest(local_path(root,log['path']))!=log['sha256']:raise ValueError('Fixed producer log changed')
    receipt=dict(protocol=1,kind='fixed-input-producer-v1',producer=producer,command=list(command),exit_code=exit_code,
        context=copy.deepcopy(context),inputs=preserve_consumer_inputs(root,consumer),files=files,log=log,producer_report=report_link)
    validate_fixed_producer_metadata(receipt,consumer,report)
    raw=(json.dumps(receipt,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    link=dict(path=_INPUT_DIRECTORY+'/fixed-'+hashlib.sha256(raw).hexdigest()+'.json',sha256=hashlib.sha256(raw).hexdigest())
    _durable_once(Path(root)/link['path'],raw)
    from qa_limits import atomic_json
    atomic_json(Path(root)/_fixed_pointer(producer),link)
    return dict(command=command,files=files,fixed_producer=link)


_TEST_ASSETS_COMMAND = ['python3', 'tools/test_assets.py']
PREFIX_PROTOCOL = 1


def test_assets_inputs(root):
    """Exact test_assets.py reads; glob membership is part of the recipe."""
    fixed = ['tools/test_assets.py', 'tools/convert_assets.py', 'tools/scd_source.py',
             'src/stage.c', 'src/stage.h', 'assets/generated/floor.bin',
             'assets/generated/floor.rle', 'assets/generated/sonic-motion.bin',
             'assets/generated/sonic-motion.rle', 'assets/generated/sonic-motion-indexed.rle']
    packages = sorted(str(p.relative_to(root)) for p in (Path(root)/'assets/generated').glob('ppz*.bin'))
    return sorted(set(fixed + packages))


def consumer_spec(root, commands, *, window=None, retail=False):
    """Exact current consumer recipe. Unknowns cannot inherit broad M3 seals."""
    if (type(commands) is not list or not commands or any(type(c) is not list or not c
            or any(type(a) is not str for a in c) for c in commands)):
        raise ValueError('Invalid lossless consumer command arrays')
    files, media, setup, unsupported = [], [], [], []
    key = dict(kind='retail' if retail else 'window' if window else 'step', commands=commands)
    if window is not None:
        key['case'] = [window.zone, window.gate, window.name]
        declared_output = getattr(getattr(window, 'run', None), 'out', None)
        if declared_output is not None:
            key['commands'] = [[('{consumer_output}' if a == str(declared_output) else a)
                                for a in command] for command in commands]
    native = all(tuple(c) in NATIVE_ENV_DEPENDENCIES and c != ['python3', 'tools/test_feedback.py'] for c in commands)
    if commands == [_TEST_ASSETS_COMMAND]:
        files += test_assets_inputs(root)
        if not any(Path(p).name.startswith('ppz') for p in files):
            unsupported.append('test_assets requires its generated ppz package set')
    elif native:
        for command in commands:
            tool = command[1]
            files += list(_NATIVE_EXTRA.get(tool, ()))
            if tool == 'tools/test-tt-platforms.sh':
                files += _placement_paths((3, 4, 5, 6, 7, 8))
            for name, round_no in (('qq', 5), ('ww', 6), ('ss', 7), ('mm', 8)):
                if tool == 'tools/test-'+name+'-actors.sh':
                    files += _placement_paths((round_no,))
            if tool == 'tools/test-zone-objects.sh':
                paths = {4: ('42A','42B','42C','42D'), 7: ('73C','73D'),
                         5: ('51A','52A','53C','51C','51D','53D'),
                         8: ('81A','81B','81C','81D','82A','82C','82D')}
                files += ['build/auto-extract/%d/objects%s.bin' % (r, p) for r, rows in paths.items() for p in rows]
    elif any(commands==[d['command']] for d in _FIXED_PRODUCERS.values()):
        producer=next(p for p,d in _FIXED_PRODUCERS.items() if commands==[d['command']])
        key['fixed_producer']=producer
        files += fixed_producer_source_paths(producer)
        media=[('dist/sonic-cd-saturn-prototype.cue','saturn-default-v1')] if producer in ('cdpp-toggle','frontend-thresholds') else [('build/retail/sonic.cue','genesis-default-v1')]
        if producer=='special-win-pad' and not (Path(root)/'build/special-retail/win-route.json').is_file():
            setup.append(['python3','tools/special_route.py'])
    elif commands==[_PALETTE_COMMAND]:
        files += _palette_inputs()
    elif retail:
        media = [('build/retail/sonic.cue', 'genesis-default-v1')]
        files += list(_REFERENCE_FIRMWARE)+['build/retail/'+p for p in _REFERENCE_PROGRAMS]
        command=commands[-1]
        if (len(command)!=11 or command[:2]!=['python3','tools/retail_probe.py']
                or command[7]!='--native-unlock' or command[9]!='--round'):
            # Retain unknown calls as fresh work; never a guessed inner-cache key.
            unsupported.append('unknown retail capture argv')
        else:
            files.append(str(_input_path(root,command[4]).relative_to(root)))
    elif window is not None:
        files += list(_SATURN_CONSUMER_FILES)
        media = [('dist/sonic-cd-saturn-prototype.cue', 'saturn-default-v1')]
        if window.gate == 'retail' or window.gate == 'special':
            media.append(('build/retail/sonic.cue', 'genesis-default-v1'))
            files += list(_REFERENCE_FIRMWARE)+['build/retail/'+p for p in _REFERENCE_PROGRAMS]
        if window.gate == 'art' and window.zone != 'ppz':
            import ast
            source = (Path(root)/'tools/zone_object_assets.py').read_text()
            function = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'source_paths')
            namespace = {'SOURCE': Path(root)/'build/zone-object-source'}
            exec(compile(ast.Module(body=[function], type_ignores=[]), '<pinned source_paths>', 'exec'), namespace)
            program = commands[-1][2]
            fight=('-boss-ending' if program.endswith('-ending') else '-boss' if program.endswith('-fight') else None)
            base=program[:4] if fight else program
            paths = namespace['source_paths'](base)
            # Optional PLC presence selects a different oracle input set.
            optional = Path(root)/'build/zone-object-source'/(base+'-plc')
            if base.startswith(('R4','R5','R7','R8')) and optional not in paths:
                paths.append(optional)
            if fight:
                paths.append(Path(root)/'build/zone-object-source'/(base+fight))
                if fight=='-boss-ending':paths.append(Path(root)/'build/zone-object-source'/(base+'-boss'))
            key['art_program']=program
            files += [str(p.relative_to(root)/f) for p in paths for f in ('source.json','vram.bin')]
            if program.startswith('R31'):
                files += ['build/cc1/palette/original-'+program[3]+'.dylib','build/cc1/palette-source.json']
                key['palette_producer']=True
                if not (Path(root)/files[-2]).is_file() or not (Path(root)/_PALETTE_POINTER).is_file():
                    setup.append(['python3', 'tools/test_cc_palette.py'])
        if window.gate == 'special':
            if window.name == 'SP1-win':
                files.append('build/special-retail/win-route.json')
                if not (Path(root)/files[-1]).is_file():
                    setup.append(['python3','tools/special_route.py'])
            if window.name == 'TA-SS1-win':
                files.append('build/special-retail/win-route-ta.json')
                if not (Path(root)/files[-1]).is_file():
                    setup.append(['python3','tools/special_route.py','1','2','win-route-ta'])
            # Other routes regenerate pads/saves before use in the same run.
            files += ['tests/routes/special/win-route-ta.json'] if window.name == 'TA-SS1-win' else []
        if window.gate == 'campaign':
            out = getattr(window.run, 'out', None)
            if window.zone != 'cc':
                act = int(window.name[-1])
                if act > 1:
                    previous = Path(out).parent/(window.zone.upper()+str(act-1))
                elif window.zone == 'ppz':
                    previous = None
                elif window.zone == 'tt':
                    previous = Path(root)/'build/cc3/controller/continue/C'
                else:
                    previous = Path(out).parent/({'qq':'TT3','ww':'QQ3','ss':'WW3','mm':'SS3'}[window.zone])
                if previous is not None:
                    files.append(str((previous/'backup-after.bin').relative_to(root)))
                    if window.zone in ('ss','mm'):
                        files.append(str((previous/'report.json').relative_to(root)))
            elif window.name == 'checkpoint' and '--ppz3-report' in commands[-1]:
                source = _input_path(root, commands[-1][commands[-1].index('--ppz3-report')+1])
                files += [str((source.parent.parent/('PPZ'+str(a))/p).relative_to(root))
                          for a in (1,2,3) for p in ('report.json','backup-after.bin')]
            elif window.name == 'act3-good-bad' and '--checkpoint-report' in commands[-1]:
                source = commands[-1][commands[-1].index('--checkpoint-report')+1]
                files.append(str(_input_path(root,source).relative_to(root)))
                if _input_path(root,source).is_file():
                    _, record = _input_json(root,source)
                    files.append(str(_input_path(root,record['backup_path']).relative_to(root)))
            elif window.name.startswith('cc3-continue-'):
                files += ['build/cc2/campaign/report.json','build/cc2/campaign/'+
                          ('good' if window.name.endswith('C') else 'bad')+'-act3/backup-after.bin']
    elif any(c[1:2]==['tools/visual_mode_pixels.py'] or c[1:2]==['tools/test_frontend_emulator.py']
             or c[1:2]==['tools/test-bigring-emulator.sh'] or c[1:2]==['tools/test_ending_emulator.py'] for c in commands):
        if commands[0][1]!='tools/visual_mode_pixels.py':
            files += list(_SATURN_CONSUMER_FILES)
            media=[('dist/sonic-cd-saturn-prototype.cue','saturn-default-v1')]
    else:
        unsupported.append('fresh dispatcher/unsupported argv; no whole-matrix cache shortcut')
    required=fixed_producer_requirements(commands)
    if required:
        key['fixed_producers']=required
        files += [name for producer in required for name in fixed_producer_consumed_paths(producer)]
    if 'visual-images' in required:
        files.append('cd/VISMODE.BIN')
    if any(c[1:2]==['tools/test_ending_emulator.py'] for c in commands):
        files += ['cd/GOODEND.FMV','cd/BADEND.FMV']
    return dict(protocol=CONSUMER_PROTOCOL, key=key, native=native,
                files=sorted(set(files)), media=media, setup=setup, unsupported=unsupported)


def art_source_join(root,spec,files):
    """Run only the original source selectors over one captured buffer per file."""
    import ast
    captured={};initial={}
    selected=[n for n in spec['files'] if n.startswith('build/zone-object-source/')]
    for name in selected:
        path=_input_path(root,name)
        if not path.exists():captured[name]=None;continue
        before=path.stat();raw=path.read_bytes()
        if not stat.S_ISREG(before.st_mode) or _stat_identity(before)!=_stat_identity(path.stat()):raise ValueError('Art input changed while reading')
        captured[name]=raw;initial[name]=before
        files[name]=dict(present=True,size=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    for name,raw in captured.items():
        if not name.endswith('/source.json') or raw is None:continue
        vram_name=name[:-len('source.json')]+'vram.bin';vram=captured.get(vram_name)
        source=json.loads(raw)
        if (vram is None or type(source) is not dict or not _sha256(source.get('vram_sha256'))
                or source['vram_sha256']!=hashlib.sha256(vram).hexdigest()):
            raise ValueError('Source JSON/VRAM hash differs: '+name)
    class ReadPath:
        def __init__(self,path):self.path=Path(path)
        def __truediv__(self,name):return ReadPath(self.path/name)
        @property
        def name(self):return self.path.name
        def value(self):
            name=str(self.path.relative_to(root))
            if name not in captured:raise ValueError('Undeclared art selector input: '+name)
            return captured[name]
        def exists(self):return self.value() is not None
        def read_bytes(self):
            value=self.value()
            if value is None:raise FileNotFoundError(str(self.path))
            return value
        def read_text(self):return self.read_bytes().decode()
    class Imports(ast.NodeTransformer):
        def visit_ImportFrom(self,node):
            if node.module!='zone_object_source' or [a.name for a in node.names] not in (['R4_ALIASES'],['read_tiles']):
                raise ValueError('Unsupported art selector import')
            return None
    asset=ast.parse((Path(root)/'tools/zone_object_assets.py').read_text())
    source=ast.parse((Path(root)/'tools/zone_object_source.py').read_text())
    definitions=[Imports().visit(copy.deepcopy(n)) for n in asset.body if
        isinstance(n,ast.FunctionDef) and n.name in ('source_paths','packed_objects','fight_objects') or
        isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('DEFERRED','RETAIL_VRAM_EVIDENCE','FIGHT_KINDS') for t in n.targets)]
    definitions += [n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='read_tiles' or
                    isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='R4_ALIASES' for t in n.targets)]
    namespace=dict(SOURCE=ReadPath(Path(root)/'build/zone-object-source'),json=json,hashlib=hashlib,struct=struct)
    exec(compile(ast.Module(body=definitions,type_ignores=[]),'<original read-only art selectors>','exec'),namespace)
    program=spec['key']['art_program'];bank='-boss-ending' if program.endswith('-ending') else '-boss' if program.endswith('-fight') else None
    if bank:
        sources=[]
        for _,_,_,record in namespace['fight_objects'](program[:4],bank):
            if record not in sources:sources.append(record)
    else:
        sources=[json.loads((path/'source.json').read_text()) for path in namespace['source_paths'](program)]
    for name,before in initial.items():
        if _stat_identity(_input_path(root,name).stat())!=_stat_identity(before):raise ValueError('Art pair changed during source selection')
    return hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest()


def consumer_inputs(root, spec, *, context):
    files = {name: _input_file(root, name) for name in spec['files']}
    graphs, unsupported = [], list(spec['unsupported'])
    if not reference_cache_allowed() and spec['key']['commands']!=[_PALETTE_COMMAND]:
        unsupported.append(_ALTERNATE_SOURCE_LIMIT)
    joins={}
    if spec['key']['commands']==[['bash','tools/test-cc-pocket.sh']]:
        try:
            iso=_input_path(root,'build/retail/sonic.iso').read_bytes();signature=bytes.fromhex('f3f3ed5618')
            if iso.count(signature)!=1:raise ValueError('FM driver signature is not unique')
            expected=iso[iso.index(signature):iso.index(signature)+8192]
            driver=_input_path(root,'build/retail/fm-driver.bin').read_bytes()
            if len(expected)!=8192 or driver!=expected:raise ValueError('FM driver differs from the sealed ISO extraction')
            joins['fm_driver_sha256']=hashlib.sha256(driver).hexdigest()
        except (OSError,ValueError) as error:unsupported.append('FM driver join: '+str(error))
    if spec['key'].get('art_program'):
        try:
            joins['source_capture_sha256']=art_source_join(root,spec,files)
        except (OSError,ValueError,TypeError,KeyError,AssertionError) as error:
            unsupported.append('art source join: '+str(error))
    if spec['key'].get('fixed_producers'):
        joins['fixed_producers']={}
        for producer in spec['key']['fixed_producers']:
            try:joins['fixed_producers'][producer]=fixed_producer_join(root,context,producer)
            except (OSError,ValueError,TypeError,KeyError) as error:unsupported.append('fixed producer join: '+producer+': '+str(error))
    if spec['key'].get('palette_producer'):
        try:joins['palette_producer']=palette_producer_join(root,context,spec['key']['art_program'][3])
        except (OSError,ValueError,TypeError,KeyError,AssertionError) as error:
            unsupported.append('palette producer join: '+str(error))
    if spec['key']['commands']==[_PALETTE_COMMAND]:
        try:
            _palette_toolchain(context)
            joins['palette_source_sha256']=palette_source_join(root)
        except (OSError,ValueError,TypeError,KeyError,AssertionError) as error:
            unsupported.append('palette source join: '+str(error))
    for cue, profile in spec['media']:
        try:
            graph=cue_input_graph(root, cue, loader_profile=profile)
            if profile == 'genesis-default-v1':
                graph['iso_program_join']=reference_program_join(root,graph)
            graphs.append(graph)
        except (OSError, ValueError, TypeError, KeyError, IndexError, struct.error) as error:
            unsupported.append(str(error))
    if spec['key']['commands'] == [_TEST_ASSETS_COMMAND] and any(not v['present'] for v in files.values()):
        unsupported.append('test_assets input missing')
    profile = None
    if any(p == 'genesis-default-v1' for _, p in spec['media']):
        try:
            core = '.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib'
            profile = default_core_profile(root, runtime=context['runtime'],
                toolchain=context.get('toolchain', {}), current_core_sha=digest(Path(root)/core))
        except (OSError, ValueError, TypeError, KeyError) as error:
            unsupported.append('default reference profile: '+str(error))
    if spec['setup']:
        unsupported.append('fixed guarded setup required before consumer')
    return dict(protocol=CONSUMER_PROTOCOL, recipe=spec, context=copy.deepcopy(context),
                files=files, media=graphs, core_profile=profile, joins=joins,
                complete=not unsupported, unsupported=unsupported)


def _consumer_bytes(body):
    if (type(body) is not dict or set(body) != {'protocol','recipe','context','files','media',
            'core_profile','joins','complete','unsupported'} or type(body['protocol']) is not int
            or body['protocol'] != CONSUMER_PROTOCOL or type(body['complete']) is not bool
            or type(body['unsupported']) is not list or type(body['recipe']) is not dict
            or type(body['files']) is not dict or type(body['media']) is not list
            or type(body['context']) is not dict or type(body['joins']) is not dict):
        raise ValueError('Invalid consumer input snapshot')
    spec=body['recipe']
    if (set(spec)!={'protocol','key','native','files','media','setup','unsupported'}
            or type(spec['protocol']) is not int or spec['protocol']!=CONSUMER_PROTOCOL
            or type(spec['native']) is not bool or type(spec['key']) is not dict
            or spec['key'].get('kind') not in ('step','window','retail')
            or type(spec['key'].get('commands')) is not list
            or any(type(c) is not list or not c or any(type(a) is not str for a in c) for c in spec['key']['commands'])
            or type(spec['files']) is not list or any(type(n) is not str for n in spec['files'])
            or any(Path(n).is_absolute() or '..' in Path(n).parts or n!=Path(n).as_posix() for n in spec['files'])
            or spec['files']!=sorted(set(spec['files'])) or set(body['files'])!=set(spec['files'])
            or type(spec['media']) is not list or type(spec['setup']) is not list
            or type(spec['unsupported']) is not list or any(type(n) is not str for n in body['unsupported'])
            or any(type(n) is not str for n in spec['unsupported'])
            or body['complete'] and (spec['setup'] or spec['unsupported'])
            or body['complete'] != (not body['unsupported'])):
        raise ValueError('Invalid consumer recipe/schema')
    if not set(body['joins'])<={'source_capture_sha256','palette_source_sha256','palette_producer','fm_driver_sha256','fixed_producers'}:
        raise ValueError('Unknown consumer provenance join')
    if 'fixed_producers' in body['joins']:
        value=body['joins']['fixed_producers']
        if type(value) is not dict or not set(value)<=set(_FIXED_PRODUCERS):raise ValueError('Unknown fixed producer join')
        for pin in value.values():
            if (type(pin) is not dict or set(pin)!={'path','sha256'} or type(pin['path']) is not str
                    or not _sha256(pin['sha256']) or pin['path']!=_INPUT_DIRECTORY+'/fixed-'+pin['sha256']+'.json'):
                raise ValueError('Malformed fixed producer join')
    for name in ('source_capture_sha256','palette_source_sha256','fm_driver_sha256'):
        if name in body['joins'] and not _sha256(body['joins'][name]):raise ValueError('Invalid consumer source join')
    if body['complete']:
        if spec['key'].get('art_program') and 'source_capture_sha256' not in body['joins']:
            raise ValueError('Complete art consumer lacks source capture join')
        if spec['key'].get('fixed_producers') and set(body['joins'].get('fixed_producers',{}))!=set(spec['key']['fixed_producers']):
            raise ValueError('Complete consumer lacks fixed producer joins')
        if spec['key'].get('palette_producer') and 'palette_producer' not in body['joins']:
            raise ValueError('Complete palette consumer lacks producer join')
        if spec['key']['commands']==[_PALETTE_COMMAND] and 'palette_source_sha256' not in body['joins']:
            raise ValueError('Complete palette producer lacks source proof')
        if spec['key']['commands']==[['bash','tools/test-cc-pocket.sh']] and 'fm_driver_sha256' not in body['joins']:
            raise ValueError('Complete pocket consumer lacks driver extraction proof')
    for name, value in body['files'].items():
        if type(name) is not str or type(value) is not dict or type(value.get('present')) is not bool:
            raise ValueError('Invalid consumer file record')
        if value['present']:
            if (set(value) != {'present','size','sha256'} or type(value['size']) is not int
                    or value['size'] < 0 or not _sha256(value['sha256'])):
                raise ValueError('Invalid consumer file hash')
        elif set(value) != {'present'}:
            raise ValueError('Invalid absent consumer file')
    expected=spec['media']
    if any(not isinstance(pair,(list,tuple)) or len(pair)!=2 or any(type(v) is not str for v in pair) for pair in expected):
        raise ValueError('Invalid consumer media recipe')
    observed=[]
    for graph in body['media']:
        if type(graph) is not dict:raise ValueError('Invalid consumer media graph')
        profile=graph.get('profile');keys={'profile','cue','descriptor','file_occurrences','files','tracks','sidecar'}
        if profile=='genesis-default-v1':keys.add('iso_program_join')
        pair=[graph.get('cue'),profile]
        if set(graph)!=keys or pair not in [list(v) for v in expected] or pair in observed:
            raise ValueError('Consumer media graph differs from its recipe')
        observed.append(pair)
        descriptor=graph['descriptor']
        if (type(descriptor) is not dict or set(descriptor)!={'present','size','sha256'}
                or descriptor['present'] is not True or type(descriptor['size']) is not int
                or descriptor['size']<1 or not _sha256(descriptor['sha256'])
                or type(graph['files']) is not dict or type(graph['tracks']) is not list
                or type(graph['file_occurrences']) is not list or not graph['file_occurrences']):
            raise ValueError('Malformed consumer media records')
    if body['complete'] and observed!=[list(v) for v in expected]:
        raise ValueError('Complete consumer lacks its media graph')
    return (json.dumps(body,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()


def consumer_input_seal(body):
    value = hashlib.sha256(_consumer_bytes(body)).hexdigest()
    return dict(protocol=CONSUMER_PROTOCOL,path=_INPUT_DIRECTORY+'/'+value+'.json',sha256=value)


def preserve_consumer_inputs(root, body):
    seal = consumer_input_seal(body)
    root = Path(root)
    build = root/'build'
    if not build.is_dir() or build.is_symlink() or root != root.resolve():
        raise ValueError('Existing nonaliased build directory required')
    folder = root/_INPUT_DIRECTORY
    folder.mkdir(exist_ok=True)
    if folder.is_symlink():
        raise ValueError('Consumer snapshot directory alias')
    path = root/seal['path']; raw = _consumer_bytes(body)
    if path.exists():
        if path.is_symlink() or path.read_bytes() != raw:
            raise ValueError('Consumer snapshot differs')
    _durable_once(path,raw)
    return seal


def read_consumer_inputs(root, seal):
    if (type(seal) is not dict or set(seal) != {'protocol','path','sha256'}
            or type(seal['protocol']) is not int or seal['protocol'] != CONSUMER_PROTOCOL
            or not _sha256(seal['sha256'])
            or seal['path'] != _INPUT_DIRECTORY+'/'+seal['sha256']+'.json'):
        raise ValueError('Invalid consumer input seal')
    body = _bound_json(root, dict(path=seal['path'],sha256=seal['sha256']))
    if consumer_input_seal(body) != seal:
        raise ValueError('Consumer snapshot is not canonical')
    return body


def verify_consumer_inputs(root, body):
    current = consumer_inputs(root, body['recipe'], context=body['context'])
    if not _same_json(current, body):
        raise ValueError('Consumer inputs changed during command')
    return current


def verify_stable_consumer_inputs(root, seals):
    """Final stable-facet check. Cross-command output epochs stay per consumer."""
    stable,media,profiles={},{},{}
    for seal in seals:
        body=read_consumer_inputs(root,seal)
        for name,value in body['files'].items():
            if (re.fullmatch(r'build/auto-extract/[345678]/objects[345678][123][ABCD]\.bin',name)
                    or name.startswith('.deps/libyaul/') or name==_LIBRETRO_HEADER
                    or name in _REFERENCE_FIRMWARE and name.endswith('.bin')):
                if name in stable and not _same_json(stable[name],value):
                    raise ValueError('Stable consumer facet changed between commands')
                stable[name]=value
        for graph in body['media']:
            key=(graph['cue'],graph['profile'])
            if key in media and not _same_json(media[key],graph):
                raise ValueError('Media inputs changed between commands')
            media[key]=graph
        if body['core_profile'] is not None:
            profiles[json.dumps(body['core_profile'],sort_keys=True)]=body['context']
    for name,value in stable.items():
        if not _same_json(_input_file(root,name),value):raise ValueError('Stable consumer input changed: '+name)
    for (cue,profile),expected in media.items():
        actual=cue_input_graph(root,cue,loader_profile=profile)
        if profile=='genesis-default-v1':actual['iso_program_join']=reference_program_join(root,actual)
        if not _same_json(actual,expected):raise ValueError('Media input changed before whole acceptance')
    for expected,context_value in profiles.items():
        actual=default_core_profile(root,runtime=context_value['runtime'],toolchain=context_value.get('toolchain',{}),
                                    current_core_sha=digest(Path(root)/REFERENCE_CORE))
        if not _same_json(actual,json.loads(expected)):raise ValueError('Reference core profile changed')


def consumer_inputs_reusable(root, recorded, current, migration=None):
    try:
        old = read_consumer_inputs(root, recorded)
        if not _same_json(old['context'], current['context']):
            previous, present = old['context'], current['context']
            if (set(previous) != set(present) or type(previous.get('protocol')) is not int
                    or previous['protocol'] != PROTOCOL
                    or not all(_same_json(previous[k], present[k]) for k in present if k != 'source_sha256')
                    or not same_inputs(previous.get('source_sha256'), present.get('source_sha256'), migration)):
                return False
            old = copy.deepcopy(old)
            old['context'] = present
        return current['complete'] is True and old['complete'] is True and _same_json(old, current)
    except (OSError, ValueError, TypeError, KeyError):
        return False


def producer_output_paths(command):
    """Pure exact producer table. No reads, hashes or publication."""
    return {
        ('python3','tools/test_assets.py'): ('build/stage-test.dylib',),
        ('bash','tools/test-cc-traps.sh'): ('build/cc1/traps/original.c',
            'build/cc1/gandair/retail-animation.json'),
        ('python3','tools/test_cc_palette.py'): _palette_outputs(),
        ('bash','tools/test-sonic-animation.sh'): ('build/sonic-animation/expected-frames.bin',),
        ('bash','tools/build.sh'): tuple('build/retail/'+p for p in _REFERENCE_PROGRAMS),
    }.get(tuple(command), ())


def producer_outputs(root, command, *, context=None, consumer=None, log=None, exit_code=None):
    """Post-success outputs of fixed existing producers, never extra QA cases."""
    if context is not None and any(d['command']==command for d in _FIXED_PRODUCERS.values()):
        return publish_fixed_producer(root,command,context,consumer,log,exit_code)
    paths=producer_output_paths(command)
    result=dict(command=command,files={p:_input_file(root,p) for p in paths}) if paths else None
    if command==_PALETTE_COMMAND and context is not None:
        if (type(exit_code) is not int or exit_code!=0 or consumer is None or not consumer['complete']
                or not log or any(not item['present'] for item in result['files'].values())):
            raise ValueError('No successful complete actual palette producer')
        verify_consumer_inputs(root,consumer)
        report_path=_input_path(root,'build/cc1/palette/report.json')
        report_raw=report_path.read_bytes();child=json.loads(report_raw)
        result['files']['build/cc1/palette/report.json']=dict(present=True,size=len(report_raw),sha256=hashlib.sha256(report_raw).hexdigest())
        if child.get('passed') is not True or child.get('status')!='passed':
            raise ValueError('Palette producer report is not passed')
        for field in ('inputs','run_inputs'):
            if type(child.get(field)) is not dict or not child[field]:raise ValueError('Palette source inputs absent')
            for name,sha in child[field].items():
                if consumer['files'].get(name,{}).get('sha256')!=sha:
                    raise ValueError('Palette producer source input was not captured: '+name)
        if digest(local_path(root,log['path']))!=log['sha256']:raise ValueError('Palette producer log changed')
        folder=Path(root)/_INPUT_DIRECTORY
        preserve_consumer_inputs(root,consumer)
        report_link=dict(path=_INPUT_DIRECTORY+'/palette-report-'+hashlib.sha256(report_raw).hexdigest()+'.json',sha256=hashlib.sha256(report_raw).hexdigest())
        path=Path(root)/report_link['path']
        if path.exists():
            if path.is_symlink() or path.read_bytes()!=report_raw:raise ValueError('Retained palette report differs')
        _durable_once(path,report_raw)
        _,source=_input_json(root,'build/cc1/palette-source.json')
        receipt=dict(protocol=1,kind='cc-palette-producer-v1',command=command,exit_code=exit_code,
                     context=copy.deepcopy(context),inputs=preserve_consumer_inputs(root,consumer),
                     files=result['files'],log=log,palette_source_sha256=palette_source_join(root),
                     palette_source=source,producer_report=report_link)
        validate_palette_producer_metadata(receipt,consumer,child)
        raw=(json.dumps(receipt,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
        name='palette-'+hashlib.sha256(raw).hexdigest()+'.json'
        folder=Path(root)/_INPUT_DIRECTORY
        if not folder.is_dir() or folder.is_symlink():raise ValueError('Missing physical producer receipt directory')
        path=folder/name
        if path.exists():
            if path.is_symlink() or path.read_bytes()!=raw:raise ValueError('Palette producer receipt differs')
        _durable_once(path,raw)
        link=dict(path=str(path.relative_to(root)),sha256=hashlib.sha256(raw).hexdigest())
        from qa_limits import atomic_json
        atomic_json(Path(root)/_PALETTE_POINTER,link)
        result['palette_producer']=link
    return result


def publish_consumer_context(root, context):
    """Owned runner -> helper channel. Not an independent admission authority."""
    if type(context) is not dict or type(context.get('protocol')) is not int or context['protocol'] != PROTOCOL:
        raise ValueError('Invalid caller consumer context')
    raw = (json.dumps(context,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    sha = hashlib.sha256(raw).hexdigest()
    root = Path(root)
    if root != root.resolve() or not (root/'build').is_dir() or (root/'build').is_symlink():
        raise ValueError('Existing context build directory required')
    folder=root/_INPUT_DIRECTORY
    folder.mkdir(exist_ok=True)
    if folder.is_symlink():
        raise ValueError('Consumer context directory alias')
    path=folder/('context-'+sha+'.json')
    if path.exists():
        if path.is_symlink() or path.read_bytes()!=raw:
            raise ValueError('Consumer context changed')
    _durable_once(path,raw)
    pin=dict(path=str(path.relative_to(root)),sha256=sha)
    os.environ['SCD_QA_CONSUMER_CONTEXT']=json.dumps(pin,sort_keys=True)
    return pin


def consumer_context(root):
    """Use the existing runner context; never rehash BIN/compiler per window."""
    value=os.environ.get('SCD_QA_CONSUMER_CONTEXT')
    if not value:
        return None
    pin=json.loads(value)
    context=_bound_json(root,pin)
    if (type(context) is not dict or type(context.get('protocol')) is not int
            or context['protocol']!=PROTOCOL):
        raise ValueError('Invalid inherited consumer context')
    actual=dict(platform=platform.platform(),uname=list(platform.uname()),python=platform.python_version())
    if not _same_json(context.get('runtime'),actual):
        raise ValueError('Inherited consumer runtime changed')
    return context


def _reference_selected(name, key):
    suffix = Path(key).suffix.lower()
    if name == 'assets/generated' and suffix == '.raw':
        return False
    return REFERENCE_ROOTS[name] is None or suffix in REFERENCE_ROOTS[name]


def _reference_inventory(root):
    result = {}
    for name, suffixes in REFERENCE_ROOTS.items():
        base = Path(root)/name
        # No parent alias may redirect this declared source root.
        for parent in [base, *list(base.parents)[:len(Path(name).parts)-1]]:
            if parent.is_symlink():
                raise ValueError('Reference source alias: ' + str(parent))
        try:
            mode = base.lstat().st_mode
        except FileNotFoundError:
            result[name] = None
            continue
        if not stat.S_ISDIR(mode):
            raise ValueError('Reference root is not a directory: ' + name)
        files = {}
        for path in sorted(base.rglob('*')):
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                raise ValueError('Reference source alias: ' + str(path))
            if stat.S_ISDIR(info.st_mode):
                continue
            if not _reference_selected(name, path.name):
                continue
            if not stat.S_ISREG(info.st_mode):
                raise ValueError('Reference source is not regular: ' + str(path))
            files[path.relative_to(base).as_posix()] = tuple(getattr(info, k) for k in
                ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns'))
            if len(files) > 32768:
                raise ValueError('Reference inventory bound exceeded')
        result[name] = files
    for name in REFERENCE_FILES:
        path = Path(root)/name
        if any(p.is_symlink() for p in [path, *list(path.parents)[:len(Path(name).parts)-1]]):
            raise ValueError('Fixed reference alias: ' + name)
        try:
            info = path.lstat()
        except FileNotFoundError:
            result[name] = None
            continue
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('Fixed reference is not regular: ' + name)
        result[name] = tuple(getattr(info, k) for k in
            ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns'))
    return result


def reference_inputs(root):
    """Declared native source/data/reference inputs; not a global all-input claim."""
    before = _reference_inventory(root)
    roots = {}
    for name in REFERENCE_ROOTS:
        files = before[name]
        roots[name] = dict(present=files is not None, files={} if files is None else {
            key: dict(size=identity[2], sha256=digest(Path(root)/name/key))
            for key, identity in files.items()})
    fixed = {name: (dict(present=False) if before[name] is None else
        dict(present=True, size=before[name][2], sha256=digest(Path(root)/name)))
        for name in REFERENCE_FILES}
    if _reference_inventory(root) != before:
        raise ValueError('Reference inputs changed while hashing')
    return dict(protocol=1, roots=roots, fixed_files=fixed)


def valid_reference_inputs(value):
    if (type(value) is not dict or set(value) != {'protocol', 'roots', 'fixed_files'}
            or type(value['protocol']) is not int or value['protocol'] != 1
            or type(value['roots']) is not dict or set(value['roots']) != set(REFERENCE_ROOTS)
            or type(value['fixed_files']) is not dict or set(value['fixed_files']) != set(REFERENCE_FILES)):
        return False
    for name, row in value['roots'].items():
        if (type(row) is not dict or set(row) != {'present', 'files'}
                or type(row['present']) is not bool or type(row['files']) is not dict
                or len(row['files']) > 32768 or (not row['present'] and row['files'])):
            return False
        for key, item in row['files'].items():
            if (type(key) is not str or not key or Path(key).is_absolute()
                    or '..' in Path(key).parts or Path(key).as_posix() != key
                    or not _reference_selected(name, key)
                    or type(item) is not dict or set(item) != {'size', 'sha256'}
                    or type(item['size']) is not int or item['size'] < 0
                    or type(item['sha256']) is not str
                    or re.fullmatch('[0-9a-f]{64}', item['sha256']) is None):
                return False
    for item in value['fixed_files'].values():
        if type(item) is not dict or type(item.get('present')) is not bool:
            return False
        if not item['present']:
            if set(item) != {'present'}:
                return False
        elif (set(item) != {'present', 'size', 'sha256'}
              or type(item['size']) is not int or item['size'] < 0
              or type(item['sha256']) is not str
              or re.fullmatch('[0-9a-f]{64}', item['sha256']) is None):
            return False
    return True


def _reference_bytes(value):
    if not valid_reference_inputs(value):
        raise ValueError('Invalid reference input snapshot')
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()


def reference_input_seal(value):
    sha = hashlib.sha256(_reference_bytes(value)).hexdigest()
    return dict(protocol=1, path='build/qa-reference-inputs/'+sha+'.json', sha256=sha)


def valid_reference_input_seal(value):
    return (type(value) is dict and set(value) == {'protocol', 'path', 'sha256'}
            and type(value['protocol']) is int and value['protocol'] == 1
            and type(value['sha256']) is str
            and re.fullmatch('[0-9a-f]{64}', value['sha256']) is not None
            and value['path'] == 'build/qa-reference-inputs/'+value['sha256']+'.json')


def read_reference_inputs(root, seal):
    if not valid_reference_input_seal(seal):
        raise ValueError('Invalid reference input seal')
    path = Path(root)/seal['path']
    if any(p.is_symlink() for p in (path, path.parent, path.parent.parent)):
        raise ValueError('Reference snapshot alias')
    if not path.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError('Reference snapshot outside repository')
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError('Reference snapshot is not regular')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != seal['sha256']:
        raise ValueError('Reference snapshot hash differs')
    value = json.loads(raw)
    if _reference_bytes(value) != raw or reference_input_seal(value) != seal:
        raise ValueError('Reference snapshot is not canonical')
    return value


def preserve_reference_inputs(root, value):
    from qa_limits import atomic_json
    root = Path(root)
    build = root/'build'
    if root.is_symlink() or not root.is_dir() or root.resolve() != root.absolute():
        raise ValueError('Reference repository root is missing or aliased')
    if build.is_symlink() or not stat.S_ISDIR(build.lstat().st_mode):
        raise ValueError('Reference build parent is not an existing physical directory')
    seal = reference_input_seal(value)
    path = root/seal['path']
    if path.exists() or path.is_symlink():
        read_reference_inputs(root, seal)
    else:
        if any(p.is_symlink() for p in (path.parent, path.parent.parent)):
            raise ValueError('Reference snapshot alias')
        path.parent.mkdir(parents=False, exist_ok=True)
        if any(p.is_symlink() for p in (path.parent, path.parent.parent)):
            raise ValueError('Reference snapshot alias')
        atomic_json(path, json.loads(_reference_bytes(value)))
        read_reference_inputs(root, seal)
    return seal


def verify_reference_inputs(root, seal):
    expected = read_reference_inputs(root, seal)
    if reference_inputs(root) != expected:
        raise ValueError('Reference inputs changed')


def reference_cache_allowed():
    """scd_source uses empty/unset as default; alternate trees stay uncached."""
    return not bool(os.environ.get('SCD_DATA_ROOT'))


def reference_inputs_reusable(recorded, current, command=None):
    if not reference_cache_allowed() or not valid_reference_input_seal(current):
        return False
    if recorded is None:
        return tuple(command or ()) in LEGACY_REFERENCE_INDEPENDENT
    return valid_reference_input_seal(recorded) and recorded == current


def bios_inputs(root):
    """Record bytes or explicit absence; never infer a historical BIOS value."""
    result = {}
    for name in BIOS_PATHS:
        path = Path(root)/name
        try:
            before = path.stat()
        except FileNotFoundError:
            # A dangling symlink is not a missing optional BIOS.
            if path.is_symlink():
                raise ValueError('Dangling BIOS path: ' + name)
            result[name] = dict(present=False)
            continue
        if not stat.S_ISREG(before.st_mode):
            raise ValueError('BIOS path is not a regular file: ' + name)
        sha = digest(path)
        after = path.stat()
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        if any(getattr(before, k) != getattr(after, k) for k in fields):
            raise ValueError('BIOS changed while hashing: ' + name)
        result[name] = dict(present=True, size=after.st_size, sha256=sha)
    return result


def valid_bios_inputs(value):
    if type(value) is not dict or set(value) != set(BIOS_PATHS):
        return False
    for row in value.values():
        if type(row) is not dict or type(row.get('present')) is not bool:
            return False
        if not row['present']:
            if set(row) != {'present'}:
                return False
        elif (set(row) != {'present', 'size', 'sha256'}
              or type(row['size']) is not int or row['size'] < 0
              or not isinstance(row['sha256'], str)
              or re.fullmatch('[0-9a-f]{64}', row['sha256']) is None):
            return False
    return True


def verify_bios_inputs(root, expected):
    if not valid_bios_inputs(expected) or bios_inputs(root) != expected:
        raise ValueError('BIOS inputs changed or BIOS seal is invalid')


def execution_environment(keys=EXECUTION_ENV_KEYS):
    """Hash only declared nonsecret settings; absence is an explicit value."""
    if not set(keys) <= set(EXECUTION_ENV_KEYS):
        raise ValueError('Unsupported execution environment keys')
    return {key: (dict(present=True, sha256=hashlib.sha256(
        os.environ[key].encode('utf-8', 'surrogateescape')).hexdigest())
        if key in os.environ else dict(present=False)) for key in keys}


def valid_execution_environment(value, keys=EXECUTION_ENV_KEYS):
    if type(value) is not dict or set(value) != set(keys) or not set(keys) <= set(EXECUTION_ENV_KEYS):
        return False
    for row in value.values():
        if type(row) is not dict or type(row.get('present')) is not bool:
            return False
        if not row['present']:
            if set(row) != {'present'}:
                return False
        elif (set(row) != {'present', 'sha256'} or type(row['sha256']) is not str
              or re.fullmatch('[0-9a-f]{64}', row['sha256']) is None):
            return False
    return True


def verify_execution_environment(expected, keys=EXECUTION_ENV_KEYS):
    if not valid_execution_environment(expected, keys) or expected != execution_environment(keys):
        raise ValueError('Execution environment changed or seal is invalid')


def verify_canonical_environment(seal):
    if not valid_execution_environment(seal) or any(seal[key]['present'] for key in SCOPE_ENV_KEYS):
        raise ValueError('Canonical QA forbids ambient scope filters')


def execution_environment_reusable(recorded, current, command=None):
    if not valid_execution_environment(current):
        return False
    try:
        verify_canonical_environment(current)
    except ValueError:
        return False
    dependencies = NATIVE_ENV_DEPENDENCIES.get(tuple(command or ()))
    if recorded is None:
        return dependencies == ()
    if not valid_execution_environment(recorded):
        return False
    if dependencies is None:
        return recorded == current
    return all(recorded[key] == current[key] for key in dependencies)


def verify_execution_inputs(root, bios, environment, references=None):
    verify_bios_inputs(root, bios)
    verify_execution_environment(environment)
    if references is not None:
        verify_reference_inputs(root, references)


def checkpoint_bios_inputs(root, report, save):
    """A failed boundary check cannot leave a passing checkpoint."""
    try:
        verify_bios_inputs(root, report['bios_inputs'])
        if 'reference_inputs' in report:
            verify_reference_inputs(root, report['reference_inputs'])
        if 'execution_environment' in report:
            verify_execution_environment(report['execution_environment'])
            if report.get('mode') in ('fast', 'full'):
                verify_canonical_environment(report['execution_environment'])
    except Exception as error:
        report.update(passed=False, status='failed', error=str(error))
        try:
            save()
        except BaseException as secondary:
            error.add_note('Input failure checkpoint could not be saved: ' + repr(secondary))
        raise


def bios_reusable(recorded, current, command=None):
    independent = tuple(command or ()) in LEGACY_BIOS_INDEPENDENT
    if recorded is None:
        return independent
    return valid_bios_inputs(recorded) and (independent or recorded == current)


def validate_disc_dependency_migration(record):
    """One reviewed Source18 question-mode correction, not a general upgrade."""
    import ast
    def need(ok, message):
        if not ok: raise ValueError('Disc question migration: '+message)
    need(type(record) is dict and record.get('disc_dependency_correction') == 'disc-question-validator-v1', 'wrong tag')
    need(type(record.get('protocol')) is int and record['protocol'] == PROTOCOL, 'wrong protocol')
    need(not any(k in record for k in ('parent_migration','reference_sibling','qa_correction','core_epoch')), 'ancestry forbidden')
    before, after = record.get('before_inputs'), record.get('after_inputs')
    need(type(before) is dict and type(after) is dict and set(before) == set(after), 'source maps differ in membership')
    changed = {'tools/test_disc_dependency.py','tools/qa_resume.py'}
    need({k for k in before if before[k] != after[k]} == changed
         and type(record.get('changed_paths')) is list and len(record['changed_paths']) == 2
         and set(record['changed_paths']) == changed, 'unrelated source change')
    need(before.get('tools/test_disc_dependency.py') == '445337fb15478f8b03c6bad7c61b35e100047379bca190d1f21fe073d15817bf'
         and after.get('tools/test_disc_dependency.py') == '888f9da698108e878bd491bd907516b3b66436712325147fbf6058347b47cc8e', 'wrong test correction')
    need(before.get('tools/qa_resume.py') == '14a733537cf33e6df4ce82058b4c8bf269477027898363afa291cd3c2315f2b3', 'wrong infrastructure origin')
    need(after.get('tools/qa_resume.py') == digest(Path(__file__)), 'wrong current infrastructure')
    proof = _migration_pin(record['infrastructure_proof'])
    need(proof.get('status') == 'approved_disc_question_migration_source_and_controls', 'unapproved infrastructure proof')
    need(proof.get('after_qa_resume_sha256') == after['tools/qa_resume.py'], 'proof infrastructure differs')
    original = proof['before_qa_resume']
    need(Path(original['path']).is_absolute() and Path(original['path']) == Path(original['path']).resolve(), 'original snapshot aliases')
    need(original['sha256'] == before['tools/qa_resume.py'] and digest(original['path']) == original['sha256'], 'original infrastructure snapshot differs')
    # Remove only the two new helpers and two exact dispatch branches. Every
    # old function, allowlist, consumer check and command selector must match.
    old = ast.parse(Path(original['path']).read_text())
    current = ast.parse(Path(__file__).read_text())
    additions = {'validate_disc_dependency_migration','_prepare_disc_dependency_migration'}
    found = {n.name for n in current.body if isinstance(n,ast.FunctionDef) and n.name in additions}
    need(found == additions, 'missing correction helpers')
    current.body = [n for n in current.body if not (isinstance(n,ast.FunctionDef) and n.name in additions)]
    branches = {
        'migration_chain': "if type(migration) is dict and 'disc_dependency_correction' in migration:\n    return [validate_disc_dependency_migration(migration)]",
        'prepare_migration': "if 'disc_dependency_correction' in plan:\n    return _prepare_disc_dependency_migration(root, plan, output)"}
    for name, text in branches.items():
        function = next(n for n in current.body if isinstance(n,ast.FunctionDef) and n.name == name)
        target = ast.dump(ast.parse(text).body[0],include_attributes=False)
        matches = [n for n in function.body if ast.dump(n,include_attributes=False) == target]
        need(len(matches) == 1, 'unexpected correction dispatch')
        function.body.remove(matches[0])
    need(ast.dump(old,include_attributes=False) == ast.dump(current,include_attributes=False), 'unreviewed infrastructure changes')
    controls = _migration_pin(proof['controls_result'])
    need(digest(proof['controls_source']['path']) == proof['controls_source']['sha256'], 'controls source changed')
    need(controls.get('status') == 'passed' and controls.get('qa_resume_sha256') == after['tools/qa_resume.py']
         and controls.get('controls_source_sha256') == proof['controls_source']['sha256']
         and type(controls.get('checks')) is list and len(controls['checks']) >= 16
         and all(type(c) is dict and c.get('passed') is True for c in controls['checks']), 'controls unproved')
    need(record.get('legacy_matrices') == {}, 'matrix migration forbidden')
    need(record.get('legacy_limits') == dict(SCD_QA_MAX_WORKERS='1',SCD_QA_MAX_EMULATORS='1',SCD_QA_COOLDOWN_SECONDS='120',SCD_NICE='20'), 'limits differ')
    inventory = _migration_pin(record['inventory'])
    need(record['inventory']['sha256'] == 'd3a1b49f8d1ee6b0b54783ef06a794f288b52b3fe3ff0313d50faebf2e3fd2b4'
         and len(inventory['fast']) == 171 and len(inventory['full']) == 215, 'canonical inventory differs')
    origins = {}
    for mode, expected_review in (
        ('fast','a9ad17e6e45cd6d90766f6561d5d49812c516281a8155ec177cf0f2a8f679ecf'),
        ('full','691d9d3153fc79707133641484f163aff31e3fe2599af8b76335252d773b7404')):
        pin = record[mode+'_review']; need(pin['sha256'] == expected_review, 'wrong '+mode+' origin')
        review = _migration_pin(pin)
        need(type(review.get('distinct_generations')) is int and review['distinct_generations'] == 4
             and review['retirement']['all_retired'] is True, 'origin retirement unproved')
        need(digest(Path(pin['path']).parent/'state.json') == review['state_sha256'], 'origin state changed')
        report_pin = review['original_report']; report = _migration_pin(dict(path=report_pin['path'],sha256=report_pin['sha256']))
        origins[report_pin['path']] = report_pin['sha256']
        need(report['mode'] == mode and report['source_sha256'] == before and not report.get('partial_passed'), 'origin source/mode differs')
        context = report['checkpoint_context']
        need(all(context[k] == record['legacy_'+k] for k in ('runtime','bin_sha256','limits','toolchain')), 'origin runtime/build/toolchain differs')
        rows = report['steps']
        need(all(r.get('canonical_command',r['command']) == inventory[mode][i] for i,r in enumerate(rows)), 'origin command changed')
        if mode == 'fast':
            need(review['whole_fast_accepted'] is True and report['status'] == 'passed' and report['passed'] is True
                 and len(rows) == 171 and all(type(r['exit_code']) is int and r['exit_code'] == 0 for r in rows), 'fast origin incomplete')
        else:
            need(review['whole_full_accepted'] is False and report['status'] == 'failed' and report['passed'] is False
                 and len(rows) == 172 and all(type(r['exit_code']) is int and r['exit_code'] == 0 for r in rows[:171])
                 and type(rows[171]['exit_code']) is int and rows[171]['exit_code'] == 1
                 and rows[171]['command'] == ['python3','tools/test_disc_dependency.py']
                 and not report.get('zone_gates_report'), 'full failure is not the exact pre-matrix test failure')
    need(record.get('legacy_reports') == origins, 'origin report pins differ')
    accepted = _migration_pin(record['affected_acceptance'])
    need(record['affected_acceptance']['sha256'] == '487e324f6bba23fc704ed4fe54193c9ab1274db9f42389112cee0d6d1fd84c71'
         and accepted['status'] == 'affected_disc_dependency_regression_accepted_final_suites_pending'
         and accepted['source_after']['sha256'] == after['tools/test_disc_dependency.py'], 'affected regression unproved')
    for key in ('root_review','independent_review'):
        _migration_pin(accepted[key])
    return record


def _prepare_disc_dependency_migration(root, plan, output):
    """Prepare only this two-file correction; do not run QA or fabricate a matrix."""
    from power_guard import inputs
    from qa_limits import atomic_json
    before, after = plan['pre_upgrade_source_sha256'], inputs()
    current = context(root,after)
    origins = {}
    for mode in ('fast','full'):
        review = _migration_pin(plan[mode+'_review'])
        item = review['original_report']; origins[item['path']] = item['sha256']
    record = dict(protocol=PROTOCOL,disc_dependency_correction=plan['disc_dependency_correction'],
        before_inputs=before,after_inputs=after,
        changed_paths=sorted(k for k in set(before)|set(after) if before.get(k) != after.get(k)),
        legacy_runtime=current['runtime'],legacy_bin_sha256=current['bin_sha256'],
        legacy_limits=current['limits'],legacy_toolchain=current['toolchain'],
        legacy_reports=origins,legacy_matrices={},
        **{key:copy.deepcopy(plan[key]) for key in ('infrastructure_proof','fast_review','full_review','affected_acceptance','inventory')})
    validate_disc_dependency_migration(record)
    inventory = _migration_pin(record['inventory'])
    preview = {}
    for mode in ('fast','full'):
        review = _migration_pin(record[mode+'_review'])
        selected,_ = cached_steps(root,mode,inventory[mode],current,[review['original_report']['path']],record)
        preview[mode] = dict(candidates=len(selected),reusable=None,total=len(inventory[mode]),
            scope='Candidates only; unchanged consumption-time checks remain mandatory.')
    record['verified_reuse_preview'] = preview
    if inputs() != after: raise ValueError('Inputs changed while preparing disc question correction')
    if output.exists(): raise ValueError('Preserve existing migration output')
    atomic_json(output,record)
    return record


def migration_chain(migration):
    """M1 orchestration -> M2 BIOS/env -> M3 reference inputs, all hash-linked."""
    if type(migration) is dict and 'disc_dependency_correction' in migration:
        return [validate_disc_dependency_migration(migration)]
    if not migration:
        return []
    records, seen = [], set()
    record = migration
    inherited = ('legacy_reports', 'legacy_matrices', 'legacy_runtime',
                 'legacy_bin_sha256', 'legacy_limits', 'legacy_toolchain')
    while True:
        if (type(record) is not dict or type(record.get('protocol')) is not int
                or record['protocol'] != PROTOCOL):
            raise ValueError('Invalid orchestration migration protocol')
        records.append(record)
        pin = record.get('parent_migration')
        if pin is None:
            break
        if len(records) >= 3:
            raise ValueError('At most three QA migrations are permitted')
        path = str(Path(pin['path']).resolve())
        if path in seen:
            raise ValueError('Repeated migration ancestor')
        seen.add(path)
        raw = Path(path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != pin['sha256']:
            raise ValueError('Parent orchestration migration changed')
        parent = json.loads(raw)
        if record.get('before_inputs') != parent.get('after_inputs'):
            raise ValueError('Migration before/after chain differs')
        if any(record.get(k) != parent.get(k) for k in inherited):
            raise ValueError('Follow-up migration changed original seals: ancestry')
        record = parent
    for index, record in enumerate(records):
        if 'qa_correction' in record and (index != 0 or len(records) != 3 or
                type(record['qa_correction']) is not str or record['qa_correction'] != _CUE_CORRECTION):
            raise ValueError('Invalid bounded QA correction tag')
        if 'input_closure_protocol' in record and (type(record['input_closure_protocol']) is not int or
                                                  record['input_closure_protocol']!=1):
            raise ValueError('Invalid input closure migration protocol')
        before, after = record.get('before_inputs'), record.get('after_inputs')
        if not isinstance(before, dict) or not isinstance(after, dict):
            raise ValueError('Migration lacks source maps')
        changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
        allowed = (UPGRADE_PATHS if index == len(records)-1 else
                   REFERENCE_UPGRADE_PATHS if len(records) == 3 and index == 0 else BIOS_UPGRADE_PATHS)
        if len(records) == 3 and index == 0 and record.get('input_closure_protocol') == 1:
            allowed = allowed | {_DISPATCHER_FIXTURE}
            if _DISPATCHER_FIXTURE in changed and not record.get('reference_sibling'):
                raise ValueError('Dispatcher fixture correction requires the sealed M3 sibling')
            if (_DISPATCHER_FIXTURE in changed and
                    after.get(_DISPATCHER_FIXTURE) != _DISPATCHER_FIXTURE_SHA256):
                raise ValueError('Closure dispatcher fixture differs from the exact reviewed correction')
        core = record.get('core_epoch')
        if core is not None:
            if (len(records) != 3 or index != 0 or record.get('input_closure_protocol') != 1
                    or type(record.get('input_closure_protocol')) is not int
                    or type(core) is not dict or set(core) != {'path','before_sha256','after_sha256','profile'}
                    or core['path'] != REFERENCE_CORE or not _sha256(core['before_sha256'])
                    or not _sha256(core['after_sha256']) or core['before_sha256']==core['after_sha256']
                    or before.get(REFERENCE_CORE)!=core['before_sha256']
                    or after.get(REFERENCE_CORE)!=core['after_sha256']
                    or type(core['profile']) is not dict or set(core['profile']) != {'path','sha256'}
                    or not _sha256(core['profile']['sha256'])):
                raise ValueError('Invalid narrowly bound reference core epoch')
            profile=_migration_pin(core['profile'])
            if (type(profile) is not dict or set(profile)!={'protocol','build','approval'}
                    or type(profile['protocol']) is not int or profile['protocol']!=1):
                raise ValueError('Reference core epoch does not pin the default profile envelope')
            allowed=allowed|{REFERENCE_CORE}
        if not changed or not changed <= allowed or changed != set(record.get('changed_paths', [])):
            raise ValueError('Migration exceeds the permitted orchestration changes')
    sibling_pin=migration.get('reference_sibling')
    if sibling_pin is not None:
        if len(records)!=3 or migration.get('input_closure_protocol')!=1:
            raise ValueError('Reference sibling requires an M3 closure migration')
        if 'qa_correction' in migration:
            sibling=_cue_correction_prior(migration)
        else:
            sibling=_migration_pin(sibling_pin)
            if sibling.get('reference_sibling') is not None:
                raise ValueError('Recursive reference siblings are not supported')
        other=migration_chain(sibling)
        if (len(other)!=3 or not _same_json(sibling['parent_migration'],migration['parent_migration'])
                or not _same_json(sibling['before_inputs'],migration['before_inputs'])
                or any(not _same_json(sibling.get(k),migration.get(k)) for k in inherited)):
            raise ValueError('Reference sibling does not share exact M2/original seals')
        physical=migration.get('physical_before')
        required = REFERENCE_UPGRADE_PATHS
        if _DISPATCHER_FIXTURE in migration.get('changed_paths', []) or 'qa_correction' in migration:
            required = required | {_DISPATCHER_FIXTURE}
        if type(physical) is not dict or set(physical)!=required:
            raise ValueError('Missing exact closure physical-before snapshots')
        for name,pin in physical.items():
            if (type(pin) is not dict or set(pin)!={'snapshot','sha256'} or not _sha256(pin['sha256'])
                    or pin['sha256']!=sibling['after_inputs'].get(name)
                    or digest(Path(pin['snapshot']))!=pin['sha256']):
                raise ValueError('Physical-before source differs from verified sibling: '+name)
    if 'qa_correction' in migration and sibling_pin is None:
        raise ValueError('QA correction requires its exact prior M3')
    return records


def _migration_pin(pin):
    if (type(pin) is not dict or set(pin)!={'path','sha256'} or type(pin['path']) is not str
            or not _sha256(pin['sha256'])):raise ValueError('Invalid immutable migration pin')
    path=Path(pin['path'])
    if not path.is_absolute() or path!=path.resolve():raise ValueError('Migration pin path aliases')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=pin['sha256']:raise ValueError('Migration pinned bytes changed')
    return json.loads(raw)


def _cue_correction_prior(record):
    """Validate only the immediate reviewed PREGAP correction, never generic recursion."""
    if (type(record.get('qa_correction')) is not str or record['qa_correction'] != _CUE_CORRECTION
            or type(record.get('input_closure_protocol')) is not int or record['input_closure_protocol'] != 1
            or not _same_json(record.get('reference_sibling'), _CUE_CORRECTION_PRIOR)):
        raise ValueError('QA correction does not pin the exact reviewed N5 migration')
    prior = _migration_pin(record['reference_sibling'])
    old_pin = prior.get('reference_sibling')
    if ('qa_correction' in prior or type(prior.get('input_closure_protocol')) is not int
            or prior['input_closure_protocol'] != 1 or type(old_pin) is not dict
            or old_pin.get('path') == record['reference_sibling']['path']):
        raise ValueError('QA correction requires exactly two bounded sibling edges')
    older = _migration_pin(old_pin)
    if older.get('reference_sibling') is not None or 'qa_correction' in older:
        raise ValueError('QA correction older sibling must be terminal')
    before, after = prior.get('after_inputs'), record.get('after_inputs')
    if (type(before) is not dict or type(after) is not dict or set(before) != set(after)
            or {name for name in before if before[name] != after[name]} != _CUE_CORRECTION_PATHS
            or any(not _sha256(after[name]) for name in _CUE_CORRECTION_PATHS)
            or not _same_json(record.get('core_epoch'), prior.get('core_epoch'))):
        raise ValueError('QA correction immediate source/core delta differs')
    physical = record.get('physical_before')
    if type(physical) is not dict or set(physical) != REFERENCE_UPGRADE_PATHS | {_DISPATCHER_FIXTURE}:
        raise ValueError('QA correction requires all six prior physical snapshots')
    for name, pin in physical.items():
        if (type(pin) is not dict or set(pin) != {'snapshot', 'sha256'}
                or type(pin['snapshot']) is not str or not Path(pin['snapshot']).is_absolute()
                or Path(pin['snapshot']) != Path(pin['snapshot']).resolve()
                or not _sha256(pin['sha256']) or pin['sha256'] != before.get(name)
                or digest(Path(pin['snapshot'])) != pin['sha256']):
            raise ValueError('QA correction physical-before snapshot differs: ' + name)
    if (before.get(_DISPATCHER_FIXTURE) != _DISPATCHER_FIXTURE_SHA256
            or after.get(_DISPATCHER_FIXTURE) != _DISPATCHER_FIXTURE_SHA256):
        raise ValueError('QA correction changed the inherited dispatcher fixture')
    return prior


def migration_source_maps(migration):
    """Verified ancestry plus the bounded pinned M3 history, never a fourth epoch."""
    records=migration_chain(migration)
    maps=[value for record in records for value in (record['before_inputs'],record['after_inputs'])]
    if migration and migration.get('reference_sibling') is not None:
        sibling = _migration_pin(migration['reference_sibling'])
        maps.append(sibling['after_inputs'])
        if 'qa_correction' in migration:
            maps.append(_migration_pin(sibling['reference_sibling'])['after_inputs'])
    return maps


def context(root, inputs, bin_path=None):
    root = Path(root)
    binary = Path(bin_path) if bin_path else root/'dist/sonic-cd-saturn-prototype.bin'
    toolchain = {}
    if platform.system() == 'Darwin':
        compiler = Path(subprocess.check_output(['/usr/bin/xcrun', '--find', 'clang'], text=True).strip()).resolve()
        sdk = Path(subprocess.check_output(['/usr/bin/xcrun', '--show-sdk-path'], text=True).strip()).resolve()
        info = sdk.stat()
        toolchain = dict(compiler=str(compiler), compiler_sha256=digest(compiler),
                         sdk=str(sdk), sdk_device=info.st_dev, sdk_inode=info.st_ino,
                         sdk_settings_sha256=digest(sdk/'SDKSettings.json'))
    elif shutil.which('cc'):
        compiler = Path(shutil.which('cc')).resolve()
        toolchain = dict(compiler=str(compiler), compiler_sha256=digest(compiler))
    return dict(protocol=PROTOCOL, runtime=dict(platform=platform.platform(),
        uname=list(platform.uname()), python=platform.python_version()),
        toolchain=toolchain,
        bin_sha256=digest(binary) if binary.is_file() else None,
        limits={k: os.environ.get(k) for k in ('SCD_QA_MAX_WORKERS',
            'SCD_QA_MAX_EMULATORS', 'SCD_QA_COOLDOWN_SECONDS', 'SCD_NICE')},
        source_sha256=inputs)


def same_inputs(old, new, migration=None):
    """An initial runner upgrade requires an exact, bounded migration record."""
    if not isinstance(old, dict) or not isinstance(new, dict):
        return False
    if old == new:
        return True
    if not migration:
        return False
    try:
        maps = migration_source_maps(migration)
    except (OSError, ValueError, KeyError, TypeError):
        return False
    return migration.get('after_inputs') == new and any(old == value for value in maps)


def compatible(report, current, migration=None, report_path=None):
    if migration and migration.get('parent_migration') is not None:
        try:
            migration_chain(migration)
        except (OSError, ValueError, KeyError, TypeError):
            return False
    if not same_inputs(report.get('source_sha256'), current['source_sha256'], migration):
        return False
    previous = report.get('checkpoint_context')
    if 'checkpoint_context' in report:
        if (type(previous) is not dict or type(previous.get('protocol')) is not int
                or previous['protocol']!=PROTOCOL or type(current.get('protocol')) is not int
                or current['protocol']!=PROTOCOL):return False
        return all(previous.get(k) == current.get(k)
                   for k in ('protocol', 'runtime', 'bin_sha256', 'limits', 'toolchain'))
    # Legacy reports lack a complete context. Admit only explicitly sealed
    # reports from the upgrade, whose runtime/build were checked separately.
    if not migration or report_path is None:
        return False
    sealed = migration.get('legacy_reports', {}).get(str(Path(report_path).resolve()))
    return (sealed == digest(report_path)
            and migration.get('legacy_runtime') == current['runtime']
            and migration.get('legacy_bin_sha256') == current['bin_sha256']
            and migration.get('legacy_limits') == current['limits']
            and migration.get('legacy_toolchain') == current.get('toolchain')
            and report.get('disc_sha256', current['bin_sha256']) == current['bin_sha256'])


def local_path(root, value):
    p = Path(value)
    root = Path(root).resolve()
    if not p.is_absolute():
        p = root/p
    p = p.resolve()
    if not p.is_relative_to(root):
        raise ValueError('Checkpoint artifact outside repository')
    return p


def infrastructure_command(command):
    # These checks inspect the changed dispatch/audit/packaging machinery.
    return any(Path(a).name.startswith(('test_qa_', 'test_power_guard',
        'test_zone_release_evidence', 'test_package', 'test_iso_dependencies',
        'test_release', 'test_export')) for a in command if isinstance(a, str))


def input_integrity_command(command):
    # Older checkpoints did not hash every extracted asset body individually.
    # Recheck these inputs rather than guessing that a mount event preserved them.
    names = {'tools/test_assets.py', 'tools/test_install_zone_packs.py', 'tools/test_zone_tables.py',
             'tools/test_feedback.py'}
    return any(a in names for a in command if isinstance(a, str))


def cacheable_command(command):
    """Only the audited native/data class and exact complete canonical matrix."""
    if type(command) is not list or any(type(a) is not str for a in command):
        return False
    if tuple(command) in NATIVE_ENV_DEPENDENCIES and command != ['python3', 'tools/test_feedback.py']:
        return True
    from zone_release_evidence import matrix_command, ZONES
    return command == [*matrix_command(ZONES, True), '--jobs', '1']


def cached_steps(root, mode, commands, current, reports, migration=None, *, index=None):
    """Candidate prefilter only; consume_cached_step is mandatory at consumption."""
    result, sources = {}, []
    current_bios = bios_inputs(root)
    current_environment = execution_environment()
    current_references = (reference_input_seal(reference_inputs(root))
                          if reference_cache_allowed() else None)
    for source in reports:
        source = local_path(root, source)
        report = json.loads(source.read_text())
        if report.get('mode') != mode or report.get('partial_passed'):
            raise ValueError('Resume requires a report for the same complete suite')
        if not compatible(report, current, migration, source):
            raise ValueError('Resume inputs/runtime/build differ: ' + str(source))
        steps = report.get('steps')
        if not isinstance(steps, list) or len(steps) > len(commands):
            raise ValueError('Invalid checkpoint command range')
        source_hash = digest(source)
        for i, step in enumerate(steps):
            canonical = step.get('canonical_command', step.get('command'))
            if canonical != commands[i]:
                raise ValueError('Checkpoint command changed at index ' + str(i))
            if index is not None and i != index:
                continue
            if input_integrity_command(commands[i]):
                continue
            if step.get('command') != canonical:
                from zone_release_evidence import canonical_matrix_command
                actual = canonical_matrix_command(step.get('command', []))
                if actual is None or actual != canonical_matrix_command(canonical):
                    raise ValueError('Checkpoint actual command differs from its declared plan')
            if not cacheable_command(commands[i]):
                continue
            if migration and report.get('source_sha256') != current['source_sha256'] and infrastructure_command(commands[i]):
                continue
            if type(step.get('exit_code')) is not int or step['exit_code'] != 0:
                continue
            references = step.get('reference_inputs')
            if not reference_inputs_reusable(references, current_references, commands[i]):
                continue
            if references is not None:
                try:
                    read_reference_inputs(root, references)
                except (OSError, ValueError, TypeError, KeyError):
                    continue
            if not bios_reusable(step.get('bios_inputs'), current_bios, commands[i]):
                continue
            if not execution_environment_reusable(step.get('execution_environment'), current_environment, commands[i]):
                continue
            try:
                if digest(local_path(root, step['log'])) != step['log_sha256']:
                    continue
                origin = step.get('reused_from')
                if origin and digest(local_path(root, origin['report'])) != origin['report_sha256']:
                    continue
            except (OSError, ValueError, KeyError):
                continue
            row = copy.deepcopy(step)
            if commands[i][:2] == ['python3', 'tools/zone-gates.py']:
                matrix = report.get('zone_gates_report')
                matrix_hash = report.get('zone_gates_report_sha256')
                try:
                    if not matrix or digest(local_path(root, matrix)) != matrix_hash:
                        continue
                except (OSError, ValueError):
                    continue
                row['zone_gates_report'] = matrix
                row['zone_gates_report_sha256'] = matrix_hash
            row['reused_from'] = dict(report=str(source), report_sha256=source_hash, index=i)
            row['cache_candidate_only'] = True
            result[i] = row
        sources.append(dict(path=str(source), sha256=source_hash))
    return result, sources


def consume_cached_step(root, mode, commands, current, candidate, index, migration=None):
    """Re-read candidate evidence and actual consumer inputs at the reuse point."""
    try:
        origin = candidate['reused_from']
        if digest(local_path(root, origin['report'])) != origin['report_sha256']:
            return None
        # The matrix dispatcher must reach each actual run_group, including
        # current producer/backup joins. Never shortcut a whole matrix verdict.
        if commands[index][:2] == ['python3', 'tools/zone-gates.py']:
            return None
        selected, _ = cached_steps(root, mode, commands, current, [origin['report']], migration, index=index)
        row = selected.get(index)
        if row is None:
            return None
        spec = consumer_spec(root, [commands[index]])
        observed = consumer_inputs(root, spec, context=current)
        produced=producer_outputs(root,commands[index])
        if produced is not None and not _same_json(row.get('producer_outputs'),produced):
            return None
        recorded = row.get('consumer_inputs')
        if recorded is None:
            # Historical base seals cover only the audited native forms with
            # no newly omitted dependency. Never invent historical extra hashes.
            if not spec['native'] or spec['files'] or spec['media'] or spec['unsupported']:
                return None
        elif not consumer_inputs_reusable(root, recorded, observed, migration):
            return None
        if not observed['complete']:
            return None
        row.pop('cache_candidate_only', None)
        row['consumer_inputs'] = preserve_consumer_inputs(root, observed)
        row['input_identity_complete'] = True
        row['consumer_inputs_observation'] = 'verified_before_reuse'
        return row
    except (OSError, ValueError, TypeError, KeyError):
        return None


def prefix_supported(command):
    """A same-run prefix is separate from cross-run cacheability."""
    return command == _TEST_ASSETS_COMMAND or (
        cacheable_command(command) and command[:2] != ['python3', 'tools/zone-gates.py'])


def completed_prefix(root, mode, commands, current, source):
    """Future protocol-marked terminal reports only; never migrate legacy rows."""
    source = local_path(root, source)
    report = json.loads(source.read_text())
    if (type(report.get('prefix_continuation_protocol')) is not int
            or report['prefix_continuation_protocol'] != PREFIX_PROTOCOL
            or report.get('mode') != mode or mode not in ('fast', 'full')
            or report.get('status') not in ('failed', 'interrupted')
            or report.get('passed') is not False or report.get('partial_passed')
            or not compatible(report, current['checkpoint_context'])):
        raise ValueError('Prefix requires a fresh terminal same-epoch suite report')
    steps = report.get('steps')
    if type(steps) is not list or len(steps) > len(commands):
        raise ValueError('Invalid completed prefix range')
    prefix = {}
    for i, row in enumerate(steps):
        if row.get('command') != commands[i] or row.get('canonical_command', row.get('command')) != commands[i]:
            raise ValueError('Prefix command differs at ' + str(i))
        if type(row.get('exit_code')) is not int or row['exit_code'] != 0:
            if i != len(steps)-1:
                raise ValueError('Prefix contains a nonterminal failure')
            break
        if not prefix_supported(commands[i]):
            break  # Unsupported argv is executed again, never declared reusable.
        before = read_consumer_inputs(root, row.get('consumer_inputs'))
        if before['complete'] is not True or row.get('input_identity_complete') is not True:
            raise ValueError('Prefix consumer is incomplete at ' + str(i))
        if before['recipe'] != consumer_spec(root, [commands[i]]):
            raise ValueError('Prefix consumer recipe changed at ' + str(i))
        if (not bios_reusable(row.get('bios_inputs'), current['bios_inputs'], commands[i])
                or not execution_environment_reusable(row.get('execution_environment'), current['execution_environment'], commands[i])
                or not reference_inputs_reusable(row.get('reference_inputs'), current['reference_inputs'], commands[i])):
            raise ValueError('Prefix BIOS/environment/reference identity changed')
        prefix[i] = dict(source=str(source), sha256=digest(source), index=i)
    return prefix


def consume_prefix_step(root, mode, commands, current, candidate, index):
    """Revalidate log, actual inputs and declared side effects before continuation."""
    source = local_path(root, candidate['source'])
    if digest(source) != candidate['sha256']:
        raise ValueError('Prefix source report changed')
    selected = completed_prefix(root, mode, commands, current, source)
    if selected.get(index) != candidate:
        raise ValueError('Prefix row is no longer admitted')
    row = copy.deepcopy(json.loads(source.read_text())['steps'][index])
    if digest(local_path(root, row['log'])) != row['log_sha256']:
        raise ValueError('Prefix successful log changed')
    observed = consumer_inputs(root, consumer_spec(root, [commands[index]]), context=current['checkpoint_context'])
    if not consumer_inputs_reusable(root, row['consumer_inputs'], observed):
        raise ValueError('Prefix actual consumer inputs changed')
    produced = producer_outputs(root, commands[index])
    if produced is not None and (any(not v['present'] for v in produced['files'].values())
                                or not _same_json(row.get('producer_outputs'), produced)):
        raise ValueError('Prefix required producer outputs changed')
    row.update(prefix_from=candidate, consumer_inputs=preserve_consumer_inputs(root, observed),
               input_identity_complete=True, consumer_inputs_observation='verified_before_prefix_continuation')
    return row


def discover_matrix(root, source, commands):
    """Locate the inner checkpoint from the actual outer report/log."""
    source = Path(source).resolve()
    report = json.loads(source.read_text())
    if report.get('zone_gates_report'):
        candidate = local_path(root, report['zone_gates_report'])
    else:
        index = report.get('active_step')
        if type(index) is not int or not 0 <= index < len(commands):
            return None
        if commands[index][:2] != ['python3', 'tools/zone-gates.py']:
            return None
        log = source.parent/(str(index).zfill(2)+'.log')
        if not log.is_file():
            return None
        matches = re.findall(r'^zone-gates: [^\n]*; (build/zone-gates/[^\s;]+)\s*$',
                             log.read_text(errors='replace'), re.M)
        if len(matches) != 1:
            return None
        candidate = local_path(root, matches[0])/'report.json'
    if candidate.name != 'report.json' or not candidate.is_relative_to((Path(root)/'build/zone-gates').resolve()):
        raise ValueError('Invalid nested matrix checkpoint')
    return candidate if candidate.is_file() else None


def legacy_matrix_compatible(matrix_path, source_path, current, migration):
    """A legacy matrix needs a sealed relationship to its outer QA epoch."""
    if not migration or source_path is None:
        return False
    matrix_path, source_path = Path(matrix_path).resolve(), Path(source_path).resolve()
    seal = migration.get('legacy_matrices', {}).get(str(matrix_path), {})
    if (seal.get('sha256') != digest(matrix_path)
            or seal.get('source_report') != str(source_path)
            or seal.get('source_sha256') != digest(source_path)):
        return False
    outer_log = seal.get('outer_log')
    if not outer_log or digest(outer_log) != seal.get('outer_log_sha256'):
        return False
    expected = 'build/zone-gates/' + matrix_path.parent.name
    matches = re.findall(r'^zone-gates: [^\n]*; (build/zone-gates/[^\s;]+)\s*$',
                         Path(outer_log).read_text(errors='replace'), re.M)
    if matches != [expected]:
        return False
    source = json.loads(source_path.read_text())
    matrix = json.loads(matrix_path.read_text())
    return (source.get('mode') == 'full'
            and matrix.get('bin_sha256') == current['bin_sha256']
            and compatible(source, current, migration, source_path))


def evidence_inputs_match(root, child, migration=None):
    """Check concrete hashed child inputs where the producer records paths."""
    for name, sha in (child.get('inputs') or {}).items():
        if not isinstance(sha, str) or len(sha) != 64:
            continue
        p = Path(name)
        if not p.is_absolute():
            p = Path(root)/p
        if not p.is_file():
            return False
        actual = digest(p)
        if actual != sha:
            try:
                relative = str(p.relative_to(root))
            except ValueError:
                return False
            try:
                maps = migration_source_maps(migration)
            except (OSError, ValueError, KeyError, TypeError):
                return False
            if not (relative in BIOS_UPGRADE_PATHS and maps
                    and migration['after_inputs'].get(relative) == actual
                    and any(value.get(relative) == sha for value in maps)):
                return False
    return True


def cached_window(root, run_dir, window, entry, bin_sha, migration=None, current_references=None):
    """Evidence candidate check; consume_cached_window is mandatory at run_group."""
    try:
        if not reference_cache_allowed():
            return False
        if entry.get('status') != 'pass' or type(entry.get('returncode')) is not int or entry['returncode'] != 0:
            return False
        # The audited native argv class matches no existing matrix run. Even
        # --host-only retail boots the Sega CD reference through retail_capture.
        # Missing seals cannot reuse; reject before reading any firmware bytes.
        if (not valid_bios_inputs(entry.get('bios_inputs'))
                or not valid_execution_environment(entry.get('execution_environment'))):
            return False
        if not bios_reusable(entry.get('bios_inputs'), bios_inputs(root)):
            return False
        if not execution_environment_reusable(entry.get('execution_environment'), execution_environment()):
            return False
        references = entry.get('reference_inputs')
        if current_references is None:
            current_references = reference_input_seal(reference_inputs(root))
        if not reference_inputs_reusable(references, current_references):
            return False
        read_reference_inputs(root, references)
        paths = {}
        for key in ('evidence', 'log'):
            path = local_path(root, entry[key])
            if not path.is_relative_to(Path(run_dir).resolve()) or digest(path) != entry[key + '_sha256']:
                return False
            paths[key] = path
        child = json.loads(paths['evidence'].read_text())
        if window.gate != 'retail' and child.get('disc_sha256') != bin_sha:
            return False
        lines = paths['log'].read_text(errors='replace').splitlines()
        res = dict(returncode=0, tail=lines[-3:],
                   pass_line=next((x for x in reversed(lines) if x.startswith('PASS')), ''))
        status, _, _ = window.parse(res, child)
        return status == 'pass' and evidence_inputs_match(root, child, migration)
    except (OSError, ValueError, KeyError, TypeError):
        return False


def consume_cached_window(root, run_dir, window, entry, bin_sha, context, migration=None):
    """Actual current-window admission, after cooling and prior producers."""
    try:
        if not cached_window(root, run_dir, window, entry, bin_sha, migration):
            return None
        spec = consumer_spec(root, window.run.cmds, window=window)
        current = consumer_inputs(root, spec, context=context)
        if not consumer_inputs_reusable(root, entry.get('consumer_inputs'), current, migration):
            return None
        if not consumer_evidence_matches(root,entry,current):return None
        return current
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return None


def consumer_evidence_matches(root,entry,observation,expected_child=None):
    try:
        raw=local_path(root,entry['evidence']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=entry['evidence_sha256']:return False
        child=json.loads(raw)
        if expected_child is not None and not _same_json(child,expected_child):return False
        expected=observation['joins'].get('source_capture_sha256')
        return expected is None or child.get('source_capture_sha256')==expected
    except (OSError,ValueError,TypeError,KeyError):return False


def campaign_parent(zone, name):
    special = {('cc', 'checkpoint'): ('ppz', 'PPZ3'),
               ('cc', 'act3-good-bad'): ('cc', 'checkpoint')}
    if (zone, name) in special:
        return special[zone, name]
    if zone in ('ppz', 'tt', 'qq', 'ww', 'ss', 'mm') and name[-1:] in ('1', '2', '3'):
        act = int(name[-1])
        if act > 1:
            return zone, zone.upper() + str(act - 1)
        prior = {'tt': ('cc', 'act3-good-bad'), 'qq': ('tt', 'TT3'),
                 'ww': ('qq', 'QQ3'), 'ss': ('ww', 'WW3'), 'mm': ('ss', 'SS3')}
        return prior.get(zone)
    return None


def campaign_cache_matches(root, window, entry, results):
    if window.gate != 'campaign':
        return True
    parent = campaign_parent(window.zone, window.name)
    if not parent:
        return True
    try:
        parent_entry = results[parent[0]]['campaign'][parent[1]]
        if parent_entry.get('status') != 'pass':
            return False
        child = json.loads(local_path(root, entry['evidence']).read_text())
        if window.zone == 'cc' and window.name == 'checkpoint':
            return child.get('ppz3_report_sha256') == parent_entry['evidence_sha256']
        if child.get('entry_evidence'):
            return child['entry_evidence'].get('sha256') == parent_entry['evidence_sha256']
        # Some early campaign tools record only an earned backup hash.
        previous = json.loads(local_path(root, parent_entry['evidence']).read_text())
        expected = child.get('entry_backup_sha256')
        return bool(expected) and expected == previous.get('backup_after_sha256', previous.get('backup_sha256'))
    except (KeyError, OSError, ValueError, TypeError):
        return False


def verify_dispatch_fixture_sources(before_path, after_path):
    """Admit only the reviewed metadata namespace and pool-fixture correction.

    The two changed methods have exact reviewed ASTs. Every other node must
    equal the sealed sibling, apart from the required qa_resume import.
    """
    import ast
    before = ast.parse(Path(before_path).read_text())
    after = ast.parse(Path(after_path).read_text())
    expected = {
        'loop_namespace': 'fd961ac95f610128b2117b6d412925e5bc5f5799b98a9d8192ed9c4ef7a06f4c',
        'test_matrix_main_limits_and_global_cooling_serialize_before_pool':
            'a1f35fc1672773d0e68434e76934380ddb2de7dcb73b092c78ba9503ff36d382',
    }
    def dump(node):
        return ast.dump(node, include_attributes=False)
    old_class = next(n for n in before.body if isinstance(n, ast.ClassDef) and n.name == 'DispatchCooling')
    new_class = next(n for n in after.body if isinstance(n, ast.ClassDef) and n.name == 'DispatchCooling')
    old_methods = {n.name: n for n in old_class.body if isinstance(n, ast.FunctionDef)}
    found = set()
    for index, node in enumerate(new_class.body):
        if isinstance(node, ast.FunctionDef) and node.name in expected:
            if hashlib.sha256(dump(node).encode()).hexdigest() != expected[node.name]:
                raise ValueError('Dispatcher fixture method exceeds reviewed correction: '+node.name)
            new_class.body[index] = copy.deepcopy(old_methods[node.name])
            found.add(node.name)
    imports = [n for n in after.body if dump(n) == dump(ast.parse('import qa_resume').body[0])]
    if found != set(expected) or len(imports) != 1:
        raise ValueError('Dispatcher fixture correction is incomplete')
    after.body.remove(imports[0])
    if dump(before) != dump(after):
        raise ValueError('Dispatcher fixture changed outside reviewed metadata correction')


def verify_bios_upgrade_sources(root, originals):
    """Permit only BIOS boundary checks around original execution/oracles."""
    import ast
    def tree(path):
        return ast.parse(Path(path).read_text())
    def dump(node):
        return ast.dump(node, include_attributes=False)
    def functions(module):
        return {n.name: n for n in module.body if isinstance(n, ast.FunctionDef)}
    old = functions(tree(originals['tools/zone-gates.py']['snapshot']))
    new = functions(tree(Path(root)/'tools/zone-gates.py'))
    for name in ('parse_retail', 'parse_routes', 'parse_generic', 'build_matrix'):
        if dump(old[name]) != dump(new[name]):
            raise ValueError('Existing zone oracle/command builder changed: ' + name)
    executor = copy.deepcopy(old['execute'])
    executor.args.args.append(ast.arg(arg='input_check'))
    executor.args.defaults.append(ast.Constant(value=None))
    check = ast.parse('if input_check is not None:input_check()').body[0]
    command_loop = next(n for n in ast.walk(executor) if isinstance(n, ast.For)
                        and isinstance(n.target, ast.Name) and n.target.id == 'cmd')
    command_loop.body.insert(1, copy.deepcopy(check))
    after_run = next(i for i, n in enumerate(command_loop.body) if isinstance(n, ast.Try)) + 1
    command_loop.body.insert(after_run, copy.deepcopy(check))
    if dump(executor) != dump(new['execute']):
        raise ValueError('Original executor changed beyond exact BIOS boundary callbacks')
    old_retail = tree(originals['tools/retail_parity.py']['snapshot'])
    retail = tree(Path(root)/'tools/retail_parity.py')
    if any(isinstance(n,ast.FunctionDef) and n.name=='read_retail_cache' for n in retail.body):
        verify_closure_retail_sources(old_retail,retail)
        return
    allowed_import = ast.parse('from qa_resume import bios_inputs, verify_bios_inputs, execution_environment, verify_execution_environment, reference_inputs, preserve_reference_inputs, verify_reference_inputs, reference_cache_allowed').body[0]
    allowed_capture = ast.parse('bios = bios_inputs(ROOT)').body[0]
    allowed_references = ast.parse('references = preserve_reference_inputs(ROOT, reference_inputs(ROOT))').body[0]
    allowed_environment = ast.parse("environment = execution_environment(keys=('SCD_DATA_ROOT',))").body[0]
    allowed_core = ast.parse("core_sha = sha(ROOT/'.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib')").body[0]
    allowed_check = ast.parse('verify_retail_inputs(ROOT, bios, core_sha, environment, references)').body[0]
    allowed_archive = ast.parse('preserve_retail_cache(out)').body[0]
    old_unlink = ast.parse("(out/'retail.key').unlink(missing_ok=True)").body[0]
    helpers = functions(ast.parse('''
def verify_retail_inputs(root, bios, core_sha, environment, references):
    verify_bios_inputs(root, bios)
    verify_execution_environment(environment, keys=('SCD_DATA_ROOT',))
    verify_reference_inputs(root, references)
    if sha(Path(root)/'.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib') != core_sha:
        raise ValueError('Retail core changed during parity comparison')
def preserve_retail_cache(out):
    names = ('retail.rows', 'retail.key', 'retail.log')
    if any((out/name).exists() for name in names):
        history = out/'retail-history'
        history.mkdir(exist_ok=True)
        saved = Path(tempfile.mkdtemp(prefix='prior-', dir=history))
        for name in names:
            path = out/name
            if path.exists():
                path.rename(saved/name)
'''))
    class StripRetail(ast.NodeTransformer):
        imports = captures = checks = keys = helper_key = core = archives = definitions = temp_imports = environment = references = selector = 0
        def visit_FunctionDef(self, node):
            if node.name in helpers:
                if dump(node) != dump(helpers[node.name]):
                    raise ValueError('Retail input/retention helper changed')
                self.definitions += 1
                return None
            return self.generic_visit(node)
        def visit_Import(self, node):
            if dump(node) == dump(ast.parse('import tempfile').body[0]):
                self.temp_imports += 1
                return None
            return node
        def visit_ImportFrom(self, node):
            if dump(node) == dump(allowed_import):
                self.imports += 1
                return None
            return node
        def visit_Assign(self, node):
            if (len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id == 'TOOLS' and isinstance(node.value, ast.Tuple)
                    and node.value.elts and dump(node.value.elts[-1]) == "Constant(value='qa_resume.py')"):
                self.helper_key += 1
                node.value.elts.pop()
            if dump(node) == dump(allowed_references):
                self.references += 1
                return None
            if dump(node) == dump(allowed_capture):
                self.captures += 1
                return None
            if dump(node) == dump(allowed_core):
                self.core += 1
                return None
            if dump(node) == dump(allowed_environment):
                self.environment += 1
                return None
            return self.generic_visit(node)
        def visit_Expr(self, node):
            if dump(node) == dump(allowed_check):
                self.checks += 1
                return None
            if dump(node) == dump(allowed_archive):
                self.archives += 1
                return copy.deepcopy(old_unlink)
            return self.generic_visit(node)
        def visit_If(self, node):
            if (isinstance(node.test, ast.BoolOp) and isinstance(node.test.op, ast.Or)
                    and len(node.test.values) == 2 and dump(node.test.values[0]) ==
                    dump(ast.parse('not reference_cache_allowed()', mode='eval').body)):
                self.selector += 1
                node.test = node.test.values[1]
            return self.generic_visit(node)
        def visit_Call(self, node):
            for key in list(node.keywords):
                if ((key.arg == 'bios_inputs' and dump(key.value) == "Name(id='bios', ctx=Load())")
                        or (key.arg == 'core_sha256' and dump(key.value) == "Name(id='core_sha', ctx=Load())")
                        or (key.arg == 'execution_environment' and dump(key.value) == "Name(id='environment', ctx=Load())")
                        or (key.arg == 'reference_inputs' and dump(key.value) == "Name(id='references', ctx=Load())")):
                    self.keys += 1
                    node.keywords.remove(key)
            return self.generic_visit(node)
    strip = StripRetail()
    retail = strip.visit(retail)
    if ((strip.imports, strip.captures, strip.checks, strip.keys, strip.helper_key,
         strip.core, strip.archives, strip.definitions, strip.temp_imports, strip.environment, strip.references, strip.selector) != (1, 1, 3, 4, 1, 1, 1, 2, 1, 1, 1, 1)
            or dump(retail) != dump(old_retail)):
        raise ValueError('Retail parity changed beyond BIOS key/boundary checks')


def verify_closure_retail_sources(old, new):
    """Protect the original trace/alignment/comparison ASTs around cache IO."""
    import ast
    dump=lambda n:ast.dump(n,include_attributes=False)
    functions=lambda t:{n.name:n for n in t.body if isinstance(n,ast.FunctionDef)}
    a,b=functions(old),functions(new)
    for name in ('sha','iso_sha256'):
        if dump(a[name])!=dump(b[name]):raise ValueError('Original retail utility changed: '+name)
    x,y=a['retail_parity'],b['retail_parity']
    if dump(x.args)!=dump(y.args):raise ValueError('Original retail API changed')
    def assignment(body,name):
        return next(n for n in body if isinstance(n,ast.Assign) and
            any(isinstance(t,ast.Name) and t.id==name for t in n.targets))
    for name in ('K','out','trace','unlock','retail'):
        if dump(assignment(x.body,name))!=dump(assignment(y.body,name)):
            raise ValueError('Original retail trace setup changed: '+name)
    def oracle(body):
        start=body.index(assignment(body,'restart'))
        finish=next(i for i,n in enumerate(body) if isinstance(n,ast.For) and
                    isinstance(n.target,ast.Tuple) and any(isinstance(t,ast.Name) and t.id=='s' for t in n.target.elts))
        return ast.Module(body=body[start:finish+1],type_ignores=[])
    if dump(oracle(x.body))!=dump(oracle(y.body)):
        raise ValueError('Original retail comparison/alignment oracle changed')
    # Only the buffer source changes. Tokenization stays byte-for-byte AST equal.
    wanted=copy.deepcopy(assignment(x.body,'r'))
    wanted.value.generators[0].iter=ast.parse('retail_text.splitlines()',mode='eval').body
    if dump(wanted)!=dump(assignment(y.body,'r')):
        raise ValueError('Original retail row tokenizer changed')
    if dump(x.body[-1])!=dump(y.body[-1]):raise ValueError('Original retail verdict return changed')


def prepare_migration(root, plan_path, output):
    """Seal one known runner upgrade after controls and command-plan checks."""
    import ast
    import subprocess
    import sys
    from power_guard import inputs
    from qa_limits import atomic_json
    root, plan_path, output = Path(root).resolve(), Path(plan_path).resolve(), Path(output).resolve()
    plan = json.loads(plan_path.read_text())
    if 'disc_dependency_correction' in plan:
        return _prepare_disc_dependency_migration(root, plan, output)
    parent_pin = plan.get('parent_migration')
    parent = None
    if parent_pin is not None:
        parent_path = local_path(root, parent_pin['path'])
        raw = parent_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != parent_pin['sha256']:
            raise ValueError('Parent migration pin differs')
        parent = json.loads(raw)
        migration_chain(parent)
        parent_pin = dict(path=str(parent_path), sha256=parent_pin['sha256'])
    before, after = plan['pre_upgrade_source_sha256'], inputs()
    correction_prior = None
    if 'qa_correction' in plan:
        if parent is None or len(migration_chain(parent)) != 2:
            raise ValueError('QA correction preparation requires the exact M2 parent')
        correction_prior = _cue_correction_prior(dict(plan, after_inputs=after))
        migration_chain(correction_prior)
        if not _same_json(correction_prior['parent_migration'], parent_pin):
            raise ValueError('QA correction preparation changed its M2 parent')
    changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    allowed_upgrade = (REFERENCE_UPGRADE_PATHS if parent and len(migration_chain(parent)) == 2
                       else BIOS_UPGRADE_PATHS if parent else UPGRADE_PATHS)
    if parent and len(migration_chain(parent)) == 2 and plan.get('input_closure_protocol') == 1:
        allowed_upgrade = allowed_upgrade | {_DISPATCHER_FIXTURE}
        if _DISPATCHER_FIXTURE in changed:
            if not plan.get('reference_sibling'):
                raise ValueError('Dispatcher fixture preparation requires the sealed M3 sibling')
            physical = plan['physical_before'][_DISPATCHER_FIXTURE]
            if correction_prior is None:
                verify_dispatch_fixture_sources(physical['snapshot'], root/_DISPATCHER_FIXTURE)
            elif (after.get(_DISPATCHER_FIXTURE) != _DISPATCHER_FIXTURE_SHA256
                    or physical['sha256'] != after[_DISPATCHER_FIXTURE]):
                raise ValueError('QA correction did not inherit the exact dispatcher fixture')
    core_epoch=plan.get('core_epoch')
    if core_epoch is not None:
        if not parent or len(migration_chain(parent))!=2 or plan.get('input_closure_protocol')!=1:
            raise ValueError('Core epoch requires sibling M3 closure migration from M2')
        # The actual independently admitted source build is mandatory here.
        current_profile=default_core_profile(root,runtime=parent['legacy_runtime'],
            toolchain=parent['legacy_toolchain'],current_core_sha=after[REFERENCE_CORE])
        pin=core_epoch['profile'];profile_raw=Path(pin['path']).read_bytes()
        if (pin['path']!=str(root/'build/qa-core-profiles/genesis-default.json')
                or hashlib.sha256(profile_raw).hexdigest()!=pin['sha256'] or not _same_json(json.loads(profile_raw),current_profile)):
            raise ValueError('Core epoch does not pin current actual build profile')
        allowed_upgrade=allowed_upgrade|{REFERENCE_CORE}
    if not changed or not set(changed) <= allowed_upgrade:
        raise ValueError('Upgrade changes game/test inputs outside the permitted orchestration files')
    if parent and before != parent['after_inputs']:
        raise ValueError('Follow-up migration does not begin at exact parent after_inputs')
    state = plan['launch_state']
    preflight = json.loads(Path(state['preflight']).read_text())
    current = context(root, after)
    expected_limits = dict(SCD_QA_MAX_WORKERS='1', SCD_QA_MAX_EMULATORS='1',
                           SCD_QA_COOLDOWN_SECONDS='120', SCD_NICE='20')
    if (current['runtime'] != preflight['runtime'] or current['bin_sha256'] != preflight['bin_sha256']
            or current['limits'] != expected_limits
            or digest(preflight['compiler']['path']) != preflight['compiler']['sha256']
            or digest(root/'build/saturn/sonic-cd-saturn-prototype.elf') != preflight['elf_sha256']):
        raise ValueError('Runtime, compiler, build or resource policy differs from the retained epoch')
    sdk_record_path = Path(state['resume'])/'sdk-current-directory-checkpoint.json'
    sdk_record = json.loads(sdk_record_path.read_text())
    sdk_identity = sdk_record['SDK_directory']
    if (current['toolchain'].get('sdk') != sdk_identity['physical_path']
            or current['toolchain'].get('sdk_device') != sdk_identity['device']
            or current['toolchain'].get('sdk_inode') != sdk_identity['inode']):
        raise ValueError('SDK physical directory differs from the pre-upgrade checkpoint')
    sdk_settings = Path(sdk_identity['physical_path'])/'SDKSettings.json'
    if digest(sdk_settings) != sdk_record['files'][str(sdk_settings)]:
        raise ValueError('SDK metadata differs from the pre-upgrade checkpoint')
    def functions(path):
        return {n.name: ast.dump(n, include_attributes=False)
                for n in ast.parse(Path(path).read_text()).body if isinstance(n, ast.FunctionDef)}
    if parent:
        verify_bios_upgrade_sources(root, plan['originals'])
    else:
        old_zone = functions(plan['originals']['tools/zone-gates.py']['snapshot'])
        new_zone = functions(root/'tools/zone-gates.py')
        for name in ('parse_retail', 'parse_routes', 'parse_generic', 'build_matrix', 'execute'):
            if old_zone[name] != new_zone[name]:
                raise ValueError('Existing zone command construction/execution/oracle changed: ' + name)
    inventory_path = Path(state['resume'])/'target-prerequisites/qa-argv-inventory.json'
    inventory = json.loads(inventory_path.read_text())
    for mode in ('fast', 'full'):
        listing = subprocess.run([sys.executable, 'tools/qa-loop.py', mode, '--list'], cwd=root,
                                 capture_output=True, text=True, check=True, timeout=30)
        expected = ''.join(str(i)+': '+' '.join(cmd)+'\n'
                           for i, cmd in enumerate(inventory['modes'][mode]['argv']))
        if listing.stdout != expected:
            raise ValueError('Complete QA command plan changed: ' + mode)
    controls = []
    for script in ('tools/test_qa_resume.py', 'tools/test_qa_dispatch_cooling.py'):
        result = subprocess.run([sys.executable, script], cwd=root, capture_output=True,
                                text=True, timeout=120)
        controls.append(dict(command=[sys.executable, script], exit_code=result.returncode,
                             stdout=result.stdout, stderr=result.stderr, source_sha256=digest(root/script)))
        if result.returncode:
            raise ValueError('Recovery controls failed: '+script+'\n'+result.stderr[-4000:])
    legacy = [root/plan['prior_fast_report'], root/plan['prior_full_report'], Path(state['fast_report'])]
    seal = dict(protocol=PROTOCOL, before_inputs=before, after_inputs=after, changed_paths=changed,
                legacy_runtime=current['runtime'], legacy_bin_sha256=current['bin_sha256'],
                legacy_limits=current['limits'], legacy_toolchain=current['toolchain'],
                legacy_reports={str(p.resolve()): digest(p) for p in legacy},
                legacy_matrices={}, controls=controls, command_inventory_sha256=digest(inventory_path),
                zone_oracles_and_command_builder_unchanged=True, hardware_accepted=False)
    if plan.get('input_closure_protocol') is not None:
        if type(plan['input_closure_protocol']) is not int or plan['input_closure_protocol']!=1:
            raise ValueError('Invalid closure migration protocol')
        seal['input_closure_protocol']=1
    if core_epoch is not None:seal['core_epoch']=copy.deepcopy(core_epoch)
    if 'qa_correction' in plan:seal['qa_correction']=plan['qa_correction']
    if plan.get('reference_sibling') is not None:
        seal['reference_sibling']=copy.deepcopy(plan['reference_sibling'])
        seal['physical_before']=copy.deepcopy(plan['physical_before'])
    if parent:
        seal['parent_migration'] = parent_pin
        for key in ('legacy_reports', 'legacy_matrices', 'legacy_runtime',
                    'legacy_bin_sha256', 'legacy_limits', 'legacy_toolchain'):
            seal[key] = copy.deepcopy(parent[key])
        migration_chain(seal)
        if any(seal[k] != current[v] for k, v in (
                ('legacy_runtime','runtime'), ('legacy_bin_sha256','bin_sha256'),
                ('legacy_limits','limits'), ('legacy_toolchain','toolchain'))):
            raise ValueError('Follow-up migration changed runtime/build/toolchain/policy')
    else:
        matrix = (root/plan['prior_zone_report']).resolve()
        outer = (root/plan['prior_full_report']).resolve()
        outer_log = outer.parent/'214.log'
        seal['legacy_matrices'][str(matrix)] = dict(sha256=digest(matrix), source_report=str(outer),
            source_sha256=digest(outer), outer_log=str(outer_log), outer_log_sha256=digest(outer_log))
        if not legacy_matrix_compatible(matrix, outer, current, seal):
            raise ValueError('Legacy matrix is not bound to the verified outer QA epoch')
    preview = {}
    for mode, paths in [('fast', [legacy[0], legacy[2]]), ('full', [legacy[1]])]:
        selected, _ = cached_steps(root, mode, inventory['modes'][mode]['argv'], current, paths, seal)
        preview[mode] = dict(candidates=len(selected),reusable=None,
            total=inventory['modes'][mode]['total'],
            scope='Candidates only. Each entry must pass consumption-time checks after cooling.')
    seal['verified_reuse_preview'] = preview
    if inputs() != after:
        raise ValueError('Inputs changed while preparing the migration')
    migration_chain(seal)
    if output.exists():
        raise ValueError('Migration output already exists;preserve the earlier record')
    atomic_json(output, seal)
    return seal


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-migration', type=Path, required=True, metavar='PLAN')
    parser.add_argument('--output', type=Path, required=True)
    options = parser.parse_args()
    result = prepare_migration(Path(__file__).resolve().parents[1], options.prepare_migration, options.output)
    print(json.dumps(dict(migration=str(options.output), preview=result['verified_reuse_preview'],
                          hardware_accepted=False)))
