#!/usr/bin/env python3
"""Original Sonic/post/VINT boundary regression against the real world.c."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
# Output volume: SCD_OUTPUT_VOLUME if set, else the mount point that holds the repo.
VOLUME = Path(os.environ.get('SCD_OUTPUT_VOLUME') or next(p for p in (ROOT, *ROOT.parents) if os.path.ismount(p)))
OUT = ROOT / 'build/world-post-order'


def guard():
    assert os.path.ismount(VOLUME), 'output volume unmounted'
    subprocess.run(['df', '-k', VOLUME], check=True, stdout=subprocess.DEVNULL)
    assert shutil.disk_usage(VOLUME).free >= 100 * 1024**3, 'output volume below 100 GiB'


def run(command, name):
    guard()
    with (OUT / name).open('w') as log:
        proc = subprocess.Popen(['nice', '-n', '20', *map(str, command)], cwd=ROOT,
                                env={**os.environ, 'TMPDIR': str(OUT / 'tmp')},
                                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        deadline = time.monotonic() + 180
        try:
            while proc.poll() is None:
                guard()
                assert time.monotonic() < deadline, 'world boundary test timeout'
                time.sleep(1)
        except BaseException:
            import signal
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait()
            raise
    return proc.returncode


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,default=ROOT)
    args=parser.parse_args(); source=args.source_root.resolve()
    guard(); OUT.mkdir(parents=True,exist_ok=True); (OUT/'tmp').mkdir(exist_ok=True)
    inputs=[source/'src/world.c',source/'src/world.h',source/'src/act.h',source/'src/scd_player.h',source/'src/stage.h',ROOT/'tools/world_post_order_test.c',Path(__file__).resolve()]
    inputs += [ROOT/'.deps/scddisasm/src/Level/Wacky Workbench/Objects/Sonic/Main.asm',ROOT/'.deps/scddisasm/src/Level/_Objects/Monitor and Time Post/Main.asm',ROOT/'.deps/scddisasm/src/Level/Main.asm']
    hashes={str(p):sha(p) for p in inputs}
    report=dict(status='pending',inputs=hashes,compiler=subprocess.check_output(['clang','--version'],text=True),source_root=str(source))
    report_path=OUT/'report.json'
    report_path.write_text(json.dumps(report,indent=2)+'\n')
    try:
        flags=['clang','-std=c11','-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(source/'src')]
        sources=[str(ROOT/'tools/world_post_order_test.c'),str(source/'src/world.c')]
        command=flags+sources+['-o',str(OUT/'test')]; report['command']=command
        assert run(command,'compile.log')==0,'compile.log'
        assert run([OUT/'test'],'passed.log')==0,'passed.log'
        negative=flags+['-DPOST_BEFORE_WORLD']+sources+['-o',str(OUT/'unsafe-test')]
        report['negative_command']=negative
        assert run(negative,'negative-compile.log')==0,'negative-compile.log'
        rc=run([OUT/'unsafe-test'],'negative.log')
        assert rc!=0 and 'ordered timer differs' in (OUT/'negative.log').read_text(),'negative control missed contact ordering'
        # Restore the old timer-reset behavior only in a build-owned copy.
        old=(source/'src/world.c').read_text()
        anchor='{state.direction=direction;}'
        assert old.count(anchor)==1,'contact implementation anchor changed'
        broken=OUT/'reset-world.c'
        broken.write_text(old.replace(anchor,'{state.direction=direction;state.ticks=0;state.destination=-1;}'))
        reset_command=flags+[sources[0],str(broken),'-o',str(OUT/'reset-test')]
        report['reset_negative_command']=reset_command
        assert run(reset_command,'reset-compile.log')==0,'reset-compile.log'
        reset_rc=run([OUT/'reset-test'],'reset.log')
        assert reset_rc!=0 and 'ordered timer differs' in (OUT/'reset.log').read_text(),'negative control missed recontact reset'
        assert hashes=={str(p):sha(p) for p in inputs},'inputs changed'
        report.update(status='passed',negative_returncode=rc,reset_negative_returncode=reset_rc)
        print((OUT/'passed.log').read_text().strip())
        print('PASS: old contact-order and timer-reset negative controls fail the intended timer assertions')
    except BaseException as error:
        report.update(status='interrupted' if isinstance(error,KeyboardInterrupt) else 'failed',error=str(error)); raise
    finally:
        report_path.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    main()
