#!/usr/bin/env python3
"""Whole-window host/retail parity: a native route host against tools/retail_probe.py.

Shared by the zone route harnesses (tools/test_tt_route.py first). The host
is any route-search binary that replays a pad script, honours
<PREFIX>_TRACE (prints "unlock N"), <PREFIX>_UNLOCK_AT, <PREFIX>_LAG and
<PREFIX>_VINT_AT, and writes rows "seq pad x y ..." in the tt_route_search
column order. Evidence, not a pass gate.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from qa_resume import (bios_inputs, verify_bios_inputs, execution_environment,
                       verify_execution_environment, reference_inputs,
                       preserve_reference_inputs, verify_reference_inputs, reference_cache_allowed,
                       consumer_spec, consumer_inputs, consumer_context, preserve_consumer_inputs,
                       verify_consumer_inputs, consumer_inputs_reusable)

ROOT = Path(__file__).resolve().parents[1]
ISO = ROOT / 'build/retail/sonic.iso'
TOOLS = ('retail_probe.py', 'retail_parity.py', 'special_retail.py', 'retail_capture.py', 'qa_resume.py')
ZONES = {1: 'PPZ', 3: 'CC', 4: 'TT', 5: 'QQ', 6: 'WW', 7: 'SS', 8: 'MM'}
_iso_sha = {}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def iso_sha256(path=ISO):
    """The retail ISO's SHA-256, hashed once per process and cached on disk in
    a sidecar keyed by path, mtime and size."""
    path = Path(path)
    st = path.stat()
    stamp = dict(path=str(path.resolve()), mtime_ns=st.st_mtime_ns, size=st.st_size)
    if stamp['path'] in _iso_sha and _iso_sha[stamp['path']][0] == stamp:
        return _iso_sha[stamp['path']][1]
    side = path.with_name(path.name + '.sha256.json')
    try:
        saved = json.loads(side.read_text())
        digest = saved['sha256'] if all(saved.get(k) == v for k, v in stamp.items()) else None
    except (OSError, ValueError, KeyError):
        digest = None
    if digest is None:
        h = hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda: f.read(1 << 20), b''):
                h.update(block)
        digest = h.hexdigest()
        side.write_text(json.dumps(dict(stamp, sha256=digest), sort_keys=True) + '\n')
    _iso_sha[stamp['path']] = (stamp, digest)
    return digest


def verify_retail_inputs(root, bios, core_sha, environment, references):
    verify_bios_inputs(root, bios)
    verify_execution_environment(environment, keys=('SCD_DATA_ROOT',))
    verify_reference_inputs(root, references)
    if sha(Path(root)/'.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib') != core_sha:
        raise ValueError('Retail core changed during parity comparison')


def preserve_retail_cache(out):
    names = ('retail.rows', 'retail.key', 'retail.log', 'retail.receipt.json')
    if any((out/name).exists() for name in names):
        history = out/'retail-history'
        history.mkdir(exist_ok=True)
        saved = Path(tempfile.mkdtemp(prefix='prior-', dir=history))
        for name in names:
            path = out/name
            if path.exists():
                path.rename(saved/name)


def read_retail_cache(out, key, input_seal):
    """One read per file supplies the exact hash and parser buffer."""
    try:
        key_bytes=(out/'retail.key').read_bytes()
        receipt_bytes=(out/'retail.receipt.json').read_bytes()
        rows=(out/'retail.rows').read_bytes()
        log=(out/'retail.log').read_bytes()
        receipt=json.loads(receipt_bytes)
        if (type(receipt) is not dict or set(receipt) != {'protocol','key_sha256','consumer_inputs',
                'rows','log','exit_code'} or type(receipt['protocol']) is not int
                or receipt['protocol']!=1 or type(receipt['exit_code']) is not int
                or receipt['exit_code']!=0 or key_bytes!=key.encode()
                or receipt['key_sha256']!=hashlib.sha256(key_bytes).hexdigest()
                or json.dumps(receipt['consumer_inputs'],sort_keys=True,allow_nan=False)!=
                   json.dumps(input_seal,sort_keys=True,allow_nan=False)):
            return None
        for name,data in (('rows',rows),('log',log)):
            record=receipt[name]
            if (type(record) is not dict or set(record)!={'size','sha256'}
                    or type(record['size']) is not int or record['size']!=len(data)
                    or record['sha256']!=hashlib.sha256(data).hexdigest()):
                return None
        return rows.decode('utf-8')
    except (OSError,ValueError,TypeError,KeyError,UnicodeError):
        return None


def publish_retail_receipt(out, key, input_seal, exit_code):
    if type(exit_code) is not int or exit_code!=0:
        raise ValueError('No successful actual retail capture')
    rows=(out/'retail.rows').read_bytes()
    log=(out/'retail.log').read_bytes()
    receipt=dict(protocol=1,key_sha256=hashlib.sha256(key.encode()).hexdigest(),
        consumer_inputs=input_seal,rows=dict(size=len(rows),sha256=hashlib.sha256(rows).hexdigest()),
        log=dict(size=len(log),sha256=hashlib.sha256(log).hexdigest()),exit_code=exit_code)
    from qa_limits import atomic_json
    atomic_json(out/'retail.receipt.json',receipt)
    return rows.decode('utf-8')


def retail_parity(host, replay_argv, env_prefix, round_no, act, era, script, out, updates, lag_sync=True, vint_offset=1):
    """The same pad in the retail act program (tools/retail_probe.py, level-select
    entry), aligned on level updates.

    host: route host binary. replay_argv(host, script, rows_path) returns the
    host's replay argv (e.g. [host, 'replay', '0:A', script, '46000', rows]).
    env_prefix: the host's env prefix (e.g. 'TT_ROUTE'). act is 1-based.
    lag_sync: feed retail V-INT lag to the host (<PREFIX>_LAG; the TT water
    level advances once per V-INT frame).

    Sonic's first update is native sequence 1 and retail level frame 2
    (ObjSonic_Init runs on frame 1), so native sequence s is compared with
    retail frame s + 1. Retail keeps controls locked 15-20 updates longer (the
    native title card's early unlock is an accepted deviation): the native host
    is held locked until retail's unlock update (<PREFIX>_UNLOCK_AT) and the
    script gets that many neutral updates in front, so both builds read the
    route's first pad on the same level update. Native buffers Down + jump into
    a spin dash (PLAN.md controls, a deliberate improvement); a route that
    presses both at once from a standstill diverges there. Fields compared: x,
    y and their subpixels, x/y/ground speed, status, angle."""
    bios = bios_inputs(ROOT)
    references = preserve_reference_inputs(ROOT, reference_inputs(ROOT))
    environment = execution_environment(keys=('SCD_DATA_ROOT',))
    core_sha = sha(ROOT/'.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib')
    K = 1
    out = Path(out)
    trace = subprocess.run(replay_argv(host, script, out/'native-trace.rows'),
                           cwd=ROOT, env=dict(os.environ, **{env_prefix + '_TRACE': '1'}), capture_output=True, text=True)
    unlock = int(re.search(r'unlock (\d+)', trace.stderr)[1])
    retail = out / 'retail.rows'
    inherited_context=consumer_context(ROOT)
    consumer=None
    input_seal=None
    if inherited_context is not None:
        invocation=['python3','tools/retail_probe.py',str(act),era,str(script),str(retail),
            str(updates+400),'--native-unlock',str(unlock),'--round',str(round_no)]
        consumer=consumer_inputs(ROOT,consumer_spec(ROOT,[invocation],retail=True),context=inherited_context)
        input_seal=preserve_consumer_inputs(ROOT,consumer)
    # The retail run depends only on these inputs: reuse rows whose recorded key
    # matches (CLAUDE.md: cache by all input hashes), rerun otherwise.
    key = json.dumps(dict(round=round_no, zone=ZONES[round_no], act=act, era=era, script=sha(script),
                          updates=updates + 400, unlock=unlock,
                          tools=[sha(ROOT/'tools'/n) for n in TOOLS], iso=iso_sha256(),
                          bios_inputs=bios, core_sha256=core_sha,
                          execution_environment=environment, reference_inputs=references,
                          consumer_inputs=input_seal), sort_keys=True)
    verify_retail_inputs(ROOT, bios, core_sha, environment, references)
    retail_text=None
    if consumer is not None:
        verify_consumer_inputs(ROOT,consumer)
        if reference_cache_allowed() and consumer_inputs_reusable(ROOT,input_seal,consumer):
            retail_text=read_retail_cache(out,key,input_seal)
    if retail_text is None:
        preserve_retail_cache(out)
        with (out/'retail.log').open('w') as log:
            captured=subprocess.run(['python3', 'tools/retail_probe.py', str(act), era, str(script), str(retail), str(updates + 400),
                            '--native-unlock', str(unlock), '--round', str(round_no)],
                           cwd=ROOT, stdout=log, stderr=log, check=True, timeout=14400)
        verify_retail_inputs(ROOT, bios, core_sha, environment, references)
        if consumer is not None:verify_consumer_inputs(ROOT,consumer)
        if consumer is not None and consumer['complete']:
            (out/'retail.key').write_text(key)
            retail_text=publish_retail_receipt(out,key,input_seal,captured.returncode)
        else:
            retail_text=retail.read_bytes().decode('utf-8')
    r = [l.split() for l in retail_text.splitlines()]
    restart = next((i for i, row in enumerate(r) if int(row[0]) != i), None)  # a retail restart resets levelFrames
    r = r[:len(r) if restart is None else restart]
    first = next(i for i, row in enumerate(r) if int(row[-1]) >= 0)  # first retail update that reads the pad
    held = first - K
    aligned = out / 'parity-script.txt'
    aligned.write_text(f'{held - unlock} 0\n' + Path(script).read_text())
    # Line i: native sequence s = i + 2. Retail row j's V-INT count is the frames
    # since row j - 1, so a count above 1 means a V-INT (an extra watercnt) fell
    # inside update j - 1 after Sonic moved: that update's row is the mid-update
    # sample the comparison skips below. Retail row s + K + 1's count therefore
    # belongs to native sequence s (row s + K + 1 = native s + 1 would put the
    # extra water step one update late; TT2C left the water there at 1,289).
    native = out / 'native-lag.rows'
    env = dict(os.environ, **{env_prefix + '_TRACE': '1', env_prefix + '_UNLOCK_AT': str(held)})
    if lag_sync:
        lag = out / 'retail-lag.rows'
        # Column 10: the row's retail V-INT count (levelVIntCounter delta,
        # probe column 17), which RunTimeWarp follows; a masked interrupt can
        # make it one less than the frame count in column 9.
        vints = lambda j: (int(r[j][17]) - int(r[j - 1][17])) & 255 if len(r[j]) > 18 else int(r[j][8])
        lag.write_text(''.join(f'0 0 0 0 0 0 0 0 {r[s + K + 1][8]} {vints(s + K + 1)}\n' if s + K + 1 < len(r) else '0 0 0 0 0 0 0 0 1 1\n'
                               for s in range(2, len(r))))
        env[env_prefix + '_LAG'] = str(lag)
    # Retail levelVIntCounter's low byte (probe column 17) phases the lost-ring floor
    # checks (Ring/Main.asm:415); +1 aligns it with the native count at update `held`.
    if len(r[held + K]) > 18:
        env[env_prefix + '_VINT_AT'] = f'{held}:{(int(r[held + K][17]) + vint_offset) & 255}'
    with (out/'native-lag.log').open('w') as log:
        subprocess.run(replay_argv(host, aligned, native), cwd=ROOT, env=env, stdout=log, stderr=log)
    def s16(v): v = int(v) & 65535; return v - 65536 if v > 32767 else v
    def nf(f): return (int(f[2]), int(f[3]), int(f[10]) & 65535, int(f[11]) & 65535, s16(f[9]), s16(f[6]), s16(f[8]), int(f[7]), int(f[12]) & 255)
    def rf(f): return (int(f[2]), int(f[3]), int(f[15]), int(f[16]), s16(f[10]), s16(f[6]), s16(f[9]), int(f[7]), int(f[12]) & 255)
    names = ('x', 'y', 'xsub', 'ysub', 'xspeed', 'yspeed', 'mspeed', 'status', 'angle')
    h = {int(l.split()[0]): l.split() for l in native.read_text().splitlines()}
    # The probe samples at the end of the V-INT frame in which levelFrames
    # advanced. When that update overruns the frame (the next row took more
    # than one V-INT), the sample is taken mid-update; such rows are skipped.
    seqs = [s for s in sorted(h) if s >= held and s + K + 1 < len(r) and int(r[s + K + 1][8]) == 1]
    first_xy = next((s for s in seqs if nf(h[s])[:2] != rf(r[s + K])[:2]), None)
    first_any = next((s for s in seqs if nf(h[s]) != rf(r[s + K])), None)
    end = (out/'native-lag.log').read_text().strip().splitlines()
    result = dict(method='level-update aligned, native seq s = retail frame s+1', unlock=unlock, held_unlock=held,
                  skipped_mid_update=sum(1 for s in h if s >= held and s + K + 1 < len(r) and int(r[s + K + 1][8]) != 1),
                  compared=len(seqs), matched=sum(nf(h[s])[:2] == rf(r[s + K])[:2] for s in seqs),
                  contiguous=sum(1 for s in seqs if first_xy is None or s < first_xy),
                  contiguous_all_fields=sum(1 for s in seqs if first_any is None or s < first_any),
                  retail_updates=len(r), retail_restart=restart, native_end=end[-1] if end else None)
    for name, s in (('first_divergence', first_xy), ('first_field_divergence', first_any)):
        if s is not None:
            a, b = nf(h[s]), rf(r[s + K])
            result[name] = dict(sequence=s, fields=[n for n, x, y in zip(names, a, b) if x != y],
                                native=dict(zip(names, a)), retail=dict(zip(names, b)))
    verify_retail_inputs(ROOT, bios, core_sha, environment, references)
    if consumer is not None:verify_consumer_inputs(ROOT,consumer)
    result['retail_capture_input_identity_complete']=bool(consumer is not None and consumer['complete'])
    result['retail_capture_consumer_inputs']=input_seal
    return result
