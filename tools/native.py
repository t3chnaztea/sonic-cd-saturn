"""Native-tool boundary. Desktop subprocess behavior stays with the stdlib.

The browser bootstrap installs this dispatcher in one Worker. No host commands
or arbitrary executables are exposed by the browser backend.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import subprocess as _subprocess
import sys
import types

IS_BROWSER = sys.platform == 'emscripten'
_desktop_run = _subprocess.run
_backend = None
_progress_reporter = None


def set_progress_reporter(reporter):
    """Install an optional in-process callback; desktop builds remain silent."""
    global _progress_reporter
    previous = _progress_reporter
    _progress_reporter = reporter
    return previous


def report_progress(label, completed, total):
    if _progress_reporter is not None:
        _progress_reporter(label, completed, total)


def linked_symbols(root):
    if not IS_BROWSER:raise RuntimeError('Linked manifest is browser-only')
    manifest=json.loads((Path(root)/'program/construction.json').read_text())
    symbols=manifest['linked_symbols']
    if set(symbols)!={'__sector','___end'} or any(type(v)is not int for v in symbols.values()):
        raise ValueError('Invalid pinned link contract')
    return symbols


def install(backend):
    global _backend
    if not IS_BROWSER:
        raise RuntimeError('The browser native bridge requires Pyodide')
    if _backend is not None:
        raise RuntimeError('The browser native bridge is already installed')
    _backend = backend
    # The Worker serializes tasks. There are no interprocess lock contenders.
    fcntl = types.ModuleType('fcntl')
    for name, value in [('LOCK_EX', 2), ('LOCK_SH', 1), ('LOCK_UN', 8), ('LOCK_NB', 4), ('F_FULLFSYNC', 51)]:
        setattr(fcntl, name, value)
    fcntl.flock = lambda *args: None
    fcntl.fcntl = lambda *args: 0
    sys.modules['fcntl'] = fcntl
    _subprocess.run = run
    _subprocess.check_output = check_output
    _subprocess.check_call = check_call


def _python(arguments, cwd):
    arguments = list(arguments)
    # R3's exhaustive OVERRIDE window scan writes research metadata only.
    # The table emitter does not consume it. Desktop builds retain the scan;
    # browser release payloads are independently checked against pinned hashes.
    if Path(arguments[0]).parts[-4:] == ('tools','scroll','R3','extract.py') and '--no-scan' not in arguments:
        arguments.append('--no-scan')
    previous_argv, previous_cwd = sys.argv, Path.cwd()
    previous_path = sys.path[:]
    def project_module(module):
        return str(getattr(module, '__file__', '')).startswith('/project/tools/')
    saved = {name:module for name,module in sys.modules.copy().items()
             if name not in ('native','browser_ctypes') and project_module(module)}
    for name in saved:
        sys.modules.pop(name, None)
    stdout, stderr = io.StringIO(), io.StringIO()
    code = 0
    try:
        os.chdir(cwd or previous_cwd)
        sys.argv = list(arguments)
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                runpy.run_path(os.path.abspath(arguments[0]), run_name='__main__')
            except SystemExit as error:
                code = error.code if isinstance(error.code, int) else (0 if error.code is None else 1)
    finally:
        sys.argv = previous_argv
        sys.path[:] = previous_path
        for name,module in sys.modules.copy().items():
            if name not in ('native','browser_ctypes') and project_module(module):
                sys.modules.pop(name, None)
        sys.modules.update(saved)
        os.chdir(previous_cwd)
    return code, stdout.getvalue(), stderr.getvalue()


def run(args, *, check=False, capture_output=False, text=False, encoding=None,
        stdout=None, stderr=None, cwd=None, input=None, env=None, timeout=None, **kwargs):
    if not IS_BROWSER:
        return _desktop_run(args, check=check, capture_output=capture_output, text=text,
                            encoding=encoding, stdout=stdout, stderr=stderr, cwd=cwd,
                            input=input, env=env, timeout=timeout, **kwargs)
    if kwargs or isinstance(args, (str, bytes)) or input is not None:
        raise ValueError('Unsupported browser native-tool request')
    args = [os.fspath(a) for a in args]
    if not args:
        raise ValueError('Empty native-tool request')
    if capture_output and (stdout is not None or stderr is not None):
        raise ValueError('stdout/stderr cannot be combined with capture_output')
    if len(args) > 1 and args[1].endswith('.py'):
        code, out, err = _python(args[1:], cwd)
    else:
        # The JS backend validates each tool name and every path. It cannot spawn.
        result = _backend.runTool(args, str(cwd or Path.cwd()))
        code, out, err = int(result.code), str(result.stdout), str(result.stderr)
    binary = not (text or encoding)
    out_value = out.encode(encoding or 'utf-8') if binary else out
    err_value = err.encode(encoding or 'utf-8') if binary else err
    if not capture_output and stdout != _subprocess.PIPE:
        if stdout is None:
            sys.stdout.write(out)
        elif stdout != _subprocess.DEVNULL:
            stdout.write(out if isinstance(stdout, io.TextIOBase) else out_value)
        out_value = None
    if stderr == _subprocess.STDOUT:
        if out_value is not None:
            out_value += err_value
        err_value = None
    elif not capture_output and stderr != _subprocess.PIPE:
        if stderr is None:
            sys.stderr.write(err)
        elif stderr != _subprocess.DEVNULL:
            stderr.write(err if isinstance(stderr, io.TextIOBase) else err_value)
        err_value = None
    result = _subprocess.CompletedProcess(args, code, out_value, err_value)
    if check:
        result.check_returncode()
    return result


def check_output(args, **kwargs):
    return run(args, stdout=_subprocess.PIPE, check=True, **kwargs).stdout


def check_call(args, **kwargs):
    return run(args, check=True, **kwargs).returncode


def decode_sonic(source):
    if not IS_BROWSER or _backend is None:
        raise RuntimeError('Sonic WASM decoder is not installed')
    result = bytearray(32+198*2048)
    _backend.decodeSonicInto(source, result)
    return bytes(result)


def backend():
    if not IS_BROWSER or _backend is None:
        raise RuntimeError('Browser native backend is not installed')
    return _backend


def runtime_inputs(root, audio=False):
    if not IS_BROWSER:
        return []
    names = ['tools/native.py', 'tools/browser_ctypes.py', 'browser/native.js', 'browser/pyfs.js',
             'browser/genesis.js', 'browser/genesis.wasm']
    if audio:
        names += ['browser/audio.js', 'browser/ffmpeg-core.js', 'browser/ffmpeg-core.wasm']
    return [Path(root)/name for name in names]


def sound_driver(root):
    import hashlib
    source = Path(root)/'program/ponesound.bin'
    if not source.exists():
        # prepare_feedback runs first and supplies the pinned MIT baseline.
        # Some compiled program bytes coincide with that generated copy, so
        # the literal-run rule reconstructs those bytes instead of duplicating
        # them in the recipe. No m68k compiler runs in the browser.
        from browser_package import assemble
        from recipe_tables import materialize
        manifest=json.loads((Path(root)/'program/construction.json').read_text())
        def piece(op):
            row=manifest['tables'][op['table']]
            if row['codec']=='output-slice'and row['source']!='assets/generated/sound-driver.bin':
                raise ValueError('Firmware depends on an unavailable later conversion')
            if row['codec']not in ('input-slice','output-slice'):raise ValueError('Invalid firmware source recipe')
            return materialize(row,Path(root),manifest['tables'])
        data=assemble(manifest['firmware'],(Path(root)/'program/literals.bin').read_bytes(),piece)
        source.write_bytes(data)
    data = source.read_bytes()
    expected = 'ae1f243ab3b9be9ea66dc86904111c42feb8b9817229678f5433c41b80735c6a'
    if len(data) != 8740 or hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('Approved PoneSound compiled program differs')
    output = Path(root)/'build/sound-driver'
    output.mkdir(parents=True, exist_ok=True)
    (output/'driver.bin').write_bytes(data)
    (output/'report.json').write_text(json.dumps(dict(status='passed', producer='approved compiled program literal',
        outputs={'driver.bin':dict(bytes=len(data), sha256=expected)}), indent=2)+'\n')
    print('PASS: approved compiled PoneSound program verified')
