"""Optional reuse of pre-searched pad scripts in the route tests.

A route test copies DIR/<name>.script instead of running its fixed-seed host
search. DIR is the tracked tests/routes/cc (our own pad scripts, no game data)
unless SCD_STAGED_ROUTES names another directory; SCD_STAGED_ROUTES= (empty)
searches. The host replay, its tally gate and the Saturn replay still run, so a
script that no longer fits the sources fails as before.
"""
import os
import shutil
import subprocess
from pathlib import Path


def search(command, script, name, **kwargs):
    staged = os.environ.get('SCD_STAGED_ROUTES', str(Path(__file__).resolve().parents[1] / 'tests/routes/cc'))
    source = Path(staged) / f'{name}.script' if staged else None
    if source and source.is_file():
        shutil.copyfile(source, script)
        return source
    subprocess.run(command, **kwargs)
    return None
