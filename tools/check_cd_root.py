#!/usr/bin/env python3
"""Fail the build before the CD root outgrows the pool that reads it.

src/cd_root.c reads the root directory into a fixed pool. cdfs stops the read
at the pool size and reports no error, so a root larger than the pool makes the
files past it invisible: stage_packs_load() then stops on its CD STAGE DATA
ERROR screen, and the special stage and the sound effect bank simply find
nothing. Every zone adds twenty entries to the root, so this is checked on
every build rather than left to be rediscovered on hardware.
"""
import re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
header=(ROOT/'src/cd_root.h').read_text()
m=re.search(r'#define CD_ROOT_ENTRIES\s+(\d+)',header)
if not m:sys.exit('src/cd_root.h does not define CD_ROOT_ENTRIES')
pool=int(m.group(1))
files=sorted(p.name for p in (ROOT/'cd').iterdir() if p.is_file())
if len(files)>pool:
    past=files[pool:]
    sys.exit(f'cd/ holds {len(files)} files but the pool reads {pool}; '
             f'{len(past)} are invisible, starting at {past[0]}. '
             f'Raise CD_ROOT_ENTRIES in src/cd_root.h.')
print(f'CD root {len(files)} files, pool {pool}, {pool-len(files)} spare')
