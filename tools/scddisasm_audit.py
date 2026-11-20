#!/usr/bin/env python3
"""Record which downloaded scddisasm files each build tool reads.

  python3 tools/scddisasm_audit.py run tools/convert_assets.py [args...]
  python3 tools/scddisasm_audit.py manifest

`run` executes one tool with a sys.addaudithook hook installed in it and in
every Python process it starts (tools/audit_site/sitecustomize.py via
PYTHONPATH). Each process writes the files it opened and the directories it
listed under .deps/scddisasm to $SCD_AUDIT_DIR (default
build/scddisasm-audit). The hook also refuses any write that resolves
outside this checkout, so a worktree whose inputs are symlinks into another
checkout cannot modify it. Non-Python subprocesses are not traced; any
whose command line names scddisasm is recorded.

`manifest` merges the records into tools/scddisasm-manifest.json: path,
size, sha256 and the tools that read it. Hashes and sizes are facts about
the files; the manifest holds no SEGA data.
"""
import atexit, hashlib, json, os, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCD = ROOT / '.deps/scddisasm'
AUDIT = Path(os.environ.get('SCD_AUDIT_DIR') or ROOT / 'build/scddisasm-audit')
MANIFEST = ROOT / 'tools/scddisasm-manifest.json'
SITE = ROOT / 'tools/audit_site'
WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC
PATHLIKE = (str, bytes, os.PathLike)


def _real(p):
    return os.path.realpath(os.fsdecode(p))


def _label():
    try:
        script = os.path.relpath(os.path.realpath(sys.argv[0]), _real(ROOT)) if sys.argv and sys.argv[0] else '-c'
    except ValueError:
        script = sys.argv[0]
    return ' '.join([script, *sys.argv[1:]])


def install():
    """Install the hook in this process; write the record at exit."""
    scd_real = _real(SCD) + os.sep
    root_real = _real(ROOT) + os.sep
    allowed = [root_real, _real(tempfile.gettempdir()) + os.sep, '/private/tmp/', '/tmp/', '/dev/',
               _real(AUDIT) + os.sep]
    opened, listed, spawned = set(), set(), []
    busy = [False]
    parent = os.environ.get('SCD_AUDIT_PARENT', '')

    def rel(p):
        r = _real(p)
        return r[len(scd_real):] if r.startswith(scd_real) else None

    def guard_write(p, what):
        r = _real(p)
        if not any((r + os.sep).startswith(a) or r.startswith(a) for a in allowed):
            raise PermissionError(f'scddisasm_audit: refused {what} outside checkout: {r}')

    def hook(event, a):
        if busy[0]:
            return
        busy[0] = True
        try:
            if event == 'open' and isinstance(a[0], PATHLIKE):
                path, mode, flags = a
                writing = (mode is not None and any(c in mode for c in 'wax+')) or \
                          (mode is None and flags is not None and flags & WRITE_FLAGS)
                if writing:
                    guard_write(path, 'write')
                elif (r := rel(path)) is not None and os.path.isfile(_real(path)):
                    opened.add(r)
            elif event in ('os.listdir', 'os.scandir') and a and isinstance(a[0], PATHLIKE):
                if (r := rel(a[0])) is not None:
                    listed.add(r.rstrip(os.sep) or '.')
            elif event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.truncate', 'os.chmod', 'os.symlink',
                           'os.link', 'shutil.rmtree') and a and isinstance(a[0], PATHLIKE):
                guard_write(a[0], event)
            elif event in ('os.rename', 'shutil.copyfile', 'shutil.move') and len(a) > 1:
                guard_write(a[1], event)
            elif event == 'subprocess.Popen':
                # Children inherit the hook through PYTHONPATH and name this
                # process as their parent.
                os.environ['SCD_AUDIT_PARENT'] = (parent + ' > ' if parent else '') + _label()
                args = a[1] if isinstance(a[1], (list, tuple)) else [a[1]]
                text = ' '.join(map(os.fsdecode, map(str, args)))
                if 'scddisasm' in text:
                    spawned.append(text)
        finally:
            busy[0] = False

    def write():
        busy[0] = True
        label = (parent + ' > ' if parent else '') + _label()
        AUDIT.mkdir(parents=True, exist_ok=True)
        (AUDIT / f'{os.getpid()}.json').write_text(json.dumps(
            {'tool': label, 'opened': sorted(opened), 'listed': sorted(listed), 'subprocess': spawned},
            indent=1) + '\n')

    atexit.register(write)
    sys.addaudithook(hook)


def run(tool, args):
    env = dict(os.environ, SCD_AUDIT_DIR=str(AUDIT),
               PYTHONPATH=os.pathsep.join(filter(None, [str(SITE), os.environ.get('PYTHONPATH')])))
    env.pop('SCD_AUDIT_PARENT', None)
    sys.exit(subprocess.call([sys.executable, tool, *args], env=env))


def manifest():
    files, tools = {}, {}
    for rec in sorted(AUDIT.glob('*.json')):
        d = json.loads(rec.read_text())
        top = d['tool'].split(' > ')[0]
        t = tools.setdefault(d['tool'], {'opened': set(), 'listed_dirs': set(), 'subprocess': []})
        t['opened'].update(d['opened'])
        t['listed_dirs'].update(d['listed'])
        t['subprocess'] += d['subprocess']
        for p in d['opened']:
            files.setdefault(p, set()).add(top)
    out = {}
    for p in sorted(files):
        b = (SCD / p).read_bytes()
        out[p] = {'size': len(b), 'sha256': hashlib.sha256(b).hexdigest(), 'tools': sorted(files[p])}
    summary = {k: {'opened': len(v['opened']), 'listed_dirs': sorted(v['listed_dirs']), 'subprocess': v['subprocess']}
               for k, v in sorted(tools.items()) if v['opened'] or v['listed_dirs'] or v['subprocess']}
    MANIFEST.write_text(json.dumps({
        'about': 'scddisasm files read by the Python steps of tools/build.sh and their prerequisites '
                 '(extract_zone_auto.py rounds, qq/cc2 terrain), recorded by tools/scddisasm_audit.py. '
                 'Paths are relative to .deps/scddisasm. No file contents.',
        'processes_traced': len(tools), 'tools': summary, 'files': out}, indent=1) + '\n')
    print(f'{len(out)} files, {len(summary)} of {len(tools)} traced processes read scddisasm -> {MANIFEST.relative_to(ROOT)}')


if __name__ == '__main__':
    if len(sys.argv) >= 3 and sys.argv[1] == 'run':
        run(sys.argv[2], sys.argv[3:])
    elif sys.argv[1:] == ['manifest']:
        manifest()
    else:
        sys.exit(__doc__)
