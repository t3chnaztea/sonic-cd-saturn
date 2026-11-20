#!/usr/bin/env python3
"""Prove a changed staged asset rebuilds the ISO without changing A.BIN.

The temporary changed asset is never packaged or executed. Restore its bytes
and rebuild the ISO in finally, including on a failed assertion.
"""
import hashlib
import json
import subprocess
from pathlib import Path

from extract_mmd import ROOT, disc_files


def main():
    stage=ROOT/'cd/ZART41.BIN';original=stage.read_bytes()
    iso=ROOT/'dist/iso/sonic-cd-saturn-prototype.iso'
    program=ROOT/'build/saturn/sonic-cd-saturn-prototype.bin'
    program_hash=hashlib.sha256(program.read_bytes()).hexdigest()
    out=ROOT/'build/disc-dependency';out.mkdir(exist_ok=True)
    def make(*args):
        return subprocess.run(['bash','-c','source tools/env.sh; gmake "$@"','disc-dependency',*args,str(iso)],
                              cwd=ROOT,capture_output=True,text=True)
    # Question mode excludes only the always-run firmware validator. Real
    # consuming builds below still validate the firmware before making the ISO.
    before=make('-q','-o','prepare-sound-driver');assert before.returncode==0,before.stdout+before.stderr
    changed=original[:-1]+bytes([original[-1]^1]);result={}
    try:
        stage.write_bytes(changed)
        pending=make('-q','-o','prepare-sound-driver');assert pending.returncode==1,'a data-only update did not invalidate the ISO'
        built=make();(out/'changed.log').write_text(built.stdout+built.stderr)
        assert built.returncode==0
        files=disc_files(iso.read_bytes())
        assert files[stage.name]==changed,'rebuilt ISO contains stale zone art'
        assert hashlib.sha256(program.read_bytes()).hexdigest()==program_hash
        result=dict(data_only_rebuilt=True,program_unchanged=True,changed_sha256=hashlib.sha256(changed).hexdigest())
    finally:
        stage.write_bytes(original)
        restored=make();(out/'restored.log').write_text(restored.stdout+restored.stderr)
        if restored.returncode:raise RuntimeError('Could not restore the original ISO')
        assert disc_files(iso.read_bytes())[stage.name]==original
    result.update(passed=True,restored_sha256=hashlib.sha256(original).hexdigest(),program_sha256=program_hash)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Staged data invalidates and rebuilds the ISO; program unchanged; original data restored')


if __name__=='__main__':main()
