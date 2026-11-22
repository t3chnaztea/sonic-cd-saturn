"""Named CI allowance for exact, reviewed patcher runtime files only."""
import hashlib
import json
import re
from pathlib import Path


def verified(root,names=None):
    root=Path(root);path=root/'web/patcher/vendor/runtime-lock.json'
    if not path.exists():return set()
    lock=json.loads(path.read_text())
    if lock.get('schema')!=1:raise ValueError('Unsupported runtime lock')
    allowed=set()
    for row in lock['files']:
        name=row['path']
        if name in allowed or not name.startswith('web/patcher/vendor/')or '..'in Path(name).parts:raise ValueError('Unsafe runtime allowance')
        relative=name.removeprefix('web/patcher/vendor/')
        if not re.fullmatch(r'pyodide/(?:pyodide\.(?:js|mjs|asm\.js|asm\.wasm)|pyodide-lock\.json|python_stdlib\.zip|pillow-10\.2\.0-cp312-cp312-pyodide_2024_0_wasm32\.whl)|ffmpeg/ffmpeg-core\.(?:js|wasm)|native/(?:genesis|sonic|fmv|iso)\.(?:js|wasm)|licenses/[A-Za-z0-9.-]+\.txt',relative):
            raise ValueError('Unapproved runtime filename: '+name)
        data=(root/name).read_bytes()
        if len(data)!=row['bytes']or hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('Pinned runtime differs: '+name)
        allowed.add(name)
    if names is not None:
        extras={name for name in names if name.startswith('web/patcher/vendor/')}-allowed-{'web/patcher/vendor/runtime-lock.json'}
        if extras:raise ValueError('Unpinned vendor files: '+', '.join(sorted(extras)))
    return allowed


if __name__=='__main__':
    import subprocess
    root=Path(__file__).resolve().parents[1]
    names=subprocess.check_output(['git','ls-files'],cwd=root,text=True).splitlines()
    allowed=verified(root,names)
    print(f'PASS: pinned vendor allowance; {len(allowed)} files')
