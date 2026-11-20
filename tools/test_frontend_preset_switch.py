#!/usr/bin/env python3
"""Controller regression: live preset switches refresh Time Attack records.

Run after building the game: python3 tools/test_frontend_preset_switch.py.
Writes fresh build/frontend-preset-switch/<timestamp>/ evidence. Both directions
check the selected bank,time,unlock flags,and unchanged TA/progress records.
"""
import ast
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import struct
import subprocess
import sys
import time
import zlib

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'build/frontend-preset-switch'
BASE.mkdir(parents=True, exist_ok=True)
OUT = BASE / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
OUT.mkdir(exist_ok=False)
sys.path.insert(0, str(ROOT / 'tools'))
import power_guard
from qa_limits import atomic_json, cooldown, cooldown_seconds, worker_limit, emulator_limit
import title_menu

report = dict(status='pending', passed=False, cases=[], hardware_accepted=False,
              started=datetime.now().astimezone().isoformat(),
              source_defect_reproduced=False, wrong_file_write_claimed=False)
def save():
    atomic_json(OUT / 'report.json', report)

last_finished = None
def cool():
    global last_finished
    report['phase'] = 'cooling'
    save()
    cooldown(last_finished)

def add_file(image, name, data, cursor):
    # Sega BIOS BUP directory and chain format, as existing ta-full fixture helper.
    blocks = 1
    while 30 + 60 * (blocks - 1) < len(data) + 2 * (blocks - 1) + 2:
        blocks += 1
    chain = list(range(cursor, cursor + blocks))
    assert chain[-1] < 512 and len(name) == 11
    stream = b''.join(struct.pack('>H', b) for b in chain[1:]) + b'\0\0' + data
    first = chain[0] * 64
    image[first:first+4] = b'\x80\0\0\0'
    image[first+4:first+15] = name.encode()
    image[first+16:first+26] = b'QA PRESET\0'
    image[first+30:first+34] = struct.pack('>I', len(data))
    position = 0
    for i, block in enumerate(chain):
        start = 34 if i == 0 else 4
        chunk = stream[position:position + 64 - start]
        image[block*64+start:block*64+start+len(chunk)] = chunk
        position += len(chunk)
    assert position == len(stream)
    return cursor + blocks

def settings(preset):
    data = b'SCDC\x01\x10' + bytes([preset, 31 if preset else 0]) + bytes(4)
    return data + struct.pack('>I', zlib.crc32(data))

def records(preset, generation):
    data = bytearray(692)
    data[:4] = b'SCDT'; data[4] = 2; data[6:8] = struct.pack('>H', 692)
    data[8] = 3 if preset else 21; data[9] = 0 if preset else 2
    data[10:13] = bytes([0x23, 0x19, 0x1f]); data[13:16] = generation.to_bytes(3, 'big')
    for entry in range(84):
        value = (4321 if preset else 1234) + (100 if generation == 1 else 0) if entry == 0 else 18000
        data[16+entry*4:20+entry*4] = struct.pack('>I', value)
        data[352+entry*4:355+entry*4] = bytes([0x0b])*3
    data[688:] = struct.pack('>I', zlib.crc32(data[:688]))
    return bytes(data)

save()
try:
    allowed = {'SCD_QA_MAX_WORKERS', 'SCD_QA_MAX_EMULATORS', 'SCD_QA_COOLDOWN_SECONDS',
               'SCD_NICE', 'SCD_QA_POLICY_MANIFEST'}
    for name in list(os.environ):
        if name.startswith(('SCD_', 'PPZ_', 'CC_', 'TT_', 'QQ_', 'WW_', 'SS_', 'MM_')) and name not in allowed:
            os.environ.pop(name)
    report['resource_policy'] = dict(host_workers=worker_limit(1),emulators=emulator_limit(1),
                                   cooldown_seconds=cooldown_seconds(),nice=20)
    inputs = ['src/frontend.c','src/save_view.inc','src/title_view.inc','src/main.c',
              'src/time_attack.c','src/time_attack.h','tools/test_frontend_emulator.py',
              'tools/frontend_emulator_test.c','tools/title_menu.py']
    report['inputs'] = {name: power_guard.digest(ROOT/name) for name in inputs}
    report['script_sha256'] = power_guard.digest(Path(__file__))
    report['runtime'] = dict(platform=platform.platform(),uname=list(platform.uname()),python=platform.python_version())
    report['core_sha256'] = power_guard.digest(ROOT/'.deps/beetle-saturn/mednafen_saturn_libretro.dylib')
    report['disc_sha256'] = power_guard.digest(ROOT/'dist/sonic-cd-saturn-prototype.bin')
    report['elf_sha256'] = power_guard.digest(ROOT/'build/saturn/sonic-cd-saturn-prototype.elf')
    compiler = Path(subprocess.check_output(['/usr/bin/xcrun','--find','clang'],text=True).strip())
    report['compiler'] = dict(path=str(compiler),sha256=power_guard.digest(compiler))
    source = (ROOT/'tools/test_frontend_emulator.py').read_text()
    functions = ['run','progress_record','file_blocks','file_spans','read_file','ta_decode']
    tree = ast.parse(source)
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in functions]
    assert {n.name for n in nodes} == set(functions)
    namespace = dict(globals(), ROOT=ROOT, OUT=OUT, TA_FILE=692)
    exec(compile(ast.Module(body=nodes,type_ignores=[]), str(ROOT/'tools/test_frontend_emulator.py'), 'exec'), namespace)
    report['reused_function_ast_sha256'] = {n.name:hashlib.sha256(ast.dump(n).encode()).hexdigest() for n in nodes}
    harness = OUT/'frontend_emulator_test'; namespace['HARNESS'] = harness
    report['phase'] = 'compile_harness'; save()
    sdk = Path(subprocess.check_output(['/usr/bin/xcrun','--sdk','macosx','--show-sdk-path'],text=True).strip())
    assert (sdk/'usr/include/dlfcn.h').is_file()
    report['sdk'] = dict(path=str(sdk),dlfcn_header_sha256=power_guard.digest(sdk/'usr/include/dlfcn.h'))
    compile_command = ['nice','-n','20',str(compiler),'-isysroot',str(sdk),'-std=gnu11','-Wall','-Wextra','-Werror',
                       '-I'+str(ROOT/'.deps/beetle-saturn/libretro-common/include'),
                       str(ROOT/'tools/frontend_emulator_test.c'),'-o',str(harness)]
    with (OUT/'compile.log').open('w') as log:
        subprocess.run(compile_command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
    last_finished = time.monotonic()
    report['harness_sha256'] = power_guard.digest(harness)
    nm = subprocess.check_output([str(ROOT/'.toolchain/bin/sh-elf-nm'),str(ROOT/'build/saturn/sonic-cd-saturn-prototype.elf')],text=True)
    symbols = {}
    for row in nm.splitlines():
        parts = row.split()
        if len(parts)==3: symbols[re.sub(r'\.lto_priv\.\d+$','',parts[2])] = parts[0]
    names = dict(trace='_scd_trace_mailbox',rec='_fe_ta_rec',save='_scd_save_mailbox',bank='_fe_ta_preset',state='_fe_ta_state')
    namespace['SYMS'] = ','.join(k+'='+symbols[v] for k,v in names.items())
    report['symbols'] = {k:symbols[v] for k,v in names.items()}
    pairs = [('SCDSATURNTA',0,2),('SCDSATURNTB',0,1),('SCDSATURNTP',1,2),('SCDSATURNTQ',1,1)]
    def run(name, script, fixture):
        global last_finished
        cool(); report.update(phase='emulator',active_case=name); save()
        result = namespace['run'](name,script,fixture,timeout=900)
        last_finished = time.monotonic()
        return result
    # Produce the BIOS format header in a fresh emulator; do not depend on a prior QA fixture.
    bootstrap = 'run 200\nuntil TITL 3000\nrun 240\nhold START 4\nrun 90\ntap A\nuntil SCD2 3000\nrun 240\n'
    rc,output,_,template = run('format-template',bootstrap,None)
    assert rc==0,('format-template',rc)
    raw = template.read_bytes(); assert len(raw)==32768
    report['format_template'] = dict(path=str(template),sha256=power_guard.digest(template),used_bytes='fresh formatted first128;all case file blocks freshly generated')
    for initial in (0,1):
        target = 1-initial
        name = 'classic-to-cdpp' if initial==0 else 'cdpp-to-classic'
        image = bytearray(32768); image[:128] = raw[:128]; cursor = 2
        cursor = add_file(image,'SCDSATURN00',namespace['progress_record'](zone=1),cursor)
        cursor = add_file(image,'SCDSATURNCF',settings(initial),cursor)
        for filename,preset,generation in pairs:
            payload = records(preset,generation)
            namespace['ta_decode'](payload)
            cursor = add_file(image,filename,payload,cursor)
        fixture = OUT/(name+'-input.bin'); fixture.write_bytes(image)
        for filename,preset,generation in pairs:
            assert namespace['read_file'](image,filename)==records(preset,generation)
        rc,output,probe,_ = run(name+'-probe',title_menu.PROBE,fixture)
        assert rc==0, (name,'probe',rc)
        ram_walk,_ = title_menu.route(probe,title_menu.RAM_DATA)
        ta_walk,_ = title_menu.route(probe,title_menu.TIME_ATTACK)
        title = 'run 200\nuntil TITL 3000\nrun 240\n'
        menu = 'hold START 4\nrun 90\n'
        script = (title+'peek initial rec 0 3\npeekb initial_bank bank 0 1\n'+menu+ram_walk+
                  'tap A\nrun 30\npeek panel save 40 1\ntap RIGHT\nrun 30\npeek setting save 44 1\n'+
                  'tap B\nuntil TITL 900\nrun 240\n'+menu+ta_walk+
                  'tap A\nuntil FEND 600\nrun 30\npeek screen trace 0 4\n'+
                  'peek after rec 0 3\npeekb after_bank bank 0 1\npeek meta rec 588 2\n')
        rc,output,peeks,backup = run(name,script,fixture)
        assert rc==0, (name,'switch',rc)
        assert peeks['initial'][0] == (4321 if initial else 1234)
        assert peeks['initial_bank']==[initial]
        assert peeks['panel']==[1]
        assert peeks['setting'][0]>>8&255 == (31 if target else 0)
        assert peeks['screen'][0]==0x46454e44 and peeks['screen'][2]&255==1
        after = backup.read_bytes(); assert len(after)==32768
        files = {}
        for filename,_,_ in pairs:
            before_file = namespace['read_file'](image,filename)
            after_file = namespace['read_file'](after,filename)
            assert before_file==after_file,(name,filename,'changed during menu-only toggle')
            files[filename] = hashlib.sha256(after_file).hexdigest()
        assert namespace['read_file'](after,'SCDSATURN00')==namespace['read_file'](image,'SCDSATURN00')
        assert namespace['read_file'](after,'SCDSATURNCF')==settings(target)
        expected = dict(bank=target,time=4321 if target else 1234,unlock=3 if target else 21,flags=32 if target else 34)
        actual = dict(bank=peeks['after_bank'][0],time=peeks['after'][0],unlock=peeks['meta'][0]&255,flags=peeks['meta'][1]>>24)
        case = dict(name=name,setup_and_settings_verified=True,expected=expected,actual=actual,
                    passed=actual==expected,record_files_unchanged=files,
                    input_backup_sha256=power_guard.digest(fixture),output_backup_sha256=power_guard.digest(backup),
                    script_sha256=power_guard.digest(OUT/name/'script.txt'),results_sha256=power_guard.digest(OUT/name/'results.log'))
        report['cases'].append(case);save()
    assert all(power_guard.digest(ROOT/n)==sha for n,sha in report['inputs'].items())
    report['source_defect_reproduced'] = any(not c['passed'] for c in report['cases'])
    report['passed'] = all(c['passed'] for c in report['cases'])
    report['status'] = 'passed' if report['passed'] else 'failed'
    report['phase'] = 'complete';save()
    print(('PASS: ' if report['passed'] else 'FAIL: ')+'live preset switch '+str(sum(c['passed'] for c in report['cases']))+'/2',flush=True)
    raise SystemExit(0 if report['passed'] else 1)
except BaseException as error:
    if report['status']=='pending':
        report.update(status='interrupted' if isinstance(error,KeyboardInterrupt) else 'failed',error=repr(error))
        save()
    raise
