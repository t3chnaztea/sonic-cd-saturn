#!/usr/bin/env python3
"""Bounded future retail StaffTimes capture, private QA only; inert on import.

Uses existing special_retail core and its exact-byte guarded RunMMD injection.
This isolates DUMMY4, not title routing or Saturn acceptance. Requires root's
resource window. Native H32 framing must be reviewed from full saved frames.
"""
import argparse
import hashlib
import json
import os
import re
import struct
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIOS_NAMES = ('bios_CD_J.bin', 'bios_CD_U.bin', 'bios_CD_E.bin')
LAYOUT_INPUTS = ('Special Stage/_Common.inc', '_Include/Main CPU Variables.inc',
                 'Special Stage/Main.asm', 'Special Stage/Sub.asm', '_Include/System.inc')


def scroll_address(program):
    """Require ADDQ.W#2,scrollPos immediately followed by CMPI.W#$200,same."""
    origin = struct.unpack_from('>I', program, 2)[0]
    end = origin+len(program)-0x100
    candidates = []
    for at in range(0x100, len(program)-16, 2):
        if program[at:at+2] == b'\x54\x78':
            raw = program[at+2:at+4]
            addr = struct.unpack('>h', raw)[0] & 0xffffff
            expected = b'\x0c\x78\x02\x00'+raw
            sub = b'\x55\x78'+raw
            following = at+4
        elif program[at:at+2] == b'\x54\x79':
            raw = program[at+2:at+6]; addr = struct.unpack('>I', raw)[0]
            expected = b'\x0c\x79\x02\x00'+raw
            sub = b'\x55\x79'+raw
            following = at+6
        else: continue
        if program[following:following+len(expected)] == expected and sub in program[following:following+64] and origin <= addr < end-1:
            candidates.append(addr)
    if len(candidates) != 1: raise ValueError('unresolved/ambiguous original scrollPos')
    return candidates[0]


def file_sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''): digest.update(chunk)
    return digest.hexdigest()


def private_system(system):
    """A caller-staged BIOS-only directory prevents unsealed BRAM input."""
    system = Path(system)
    if not system.is_absolute() or system != system.resolve() or not system.is_relative_to(ROOT/'build') or not system.is_dir():
        raise ValueError('require an actual private system directory under repository build')
    entries = list(system.iterdir())
    if not entries or any(p.name not in BIOS_NAMES or p.is_symlink() or not p.is_file() for p in entries):
        raise ValueError('private system directory must contain only regular BIOS candidates; no BRAM/other files')
    return system


def selection(sr, source, system):
    system = private_system(system)
    if source.resolve() != (sr.SRC/'Title Screen/Secrets/Best Staff Times.asm').resolve():
        raise ValueError('source selector differs from Retail constructor')
    return dict(source_root=str(sr.SRC.resolve()), requested_source=os.environ.get('SCD_DATA_ROOT'),
                system=str(system), bios_presence={name: (system/name).is_file() for name in BIOS_NAMES},
                other_initial_files=[])


def disc_binding(cue, iso, expected_iso=None):
    """Read-only counterpart of background_tables.retail_iso's Mode1 extraction."""
    text = cue.read_text()
    files = re.findall(r'^\s*FILE\s+"([^"]+)"\s+(\S+)', text, re.M | re.I)
    payloads = [(cue.parent/name).resolve() for name, _ in files]
    if not payloads: raise ValueError('unresolved CUE payloads')
    if iso.resolve() in payloads:
        return dict(kind='direct_iso', payloads=[str(p) for p in payloads], user_data_sha256=expected_iso)
    if len(files) != 1 or files[0][1].upper() != 'BINARY':
        raise ValueError('require direct ISO or one raw BINARY CUE')
    tracks = {}; current = None
    for line in text.splitlines():
        match = re.match(r'^\s*TRACK\s+(\d+)\s+(\S+)\s*$', line, re.I)
        if match:
            current = int(match[1])
            if current in tracks: raise ValueError('duplicate CUE track')
            tracks[current] = dict(mode=match[2].upper(), indexes={})
        match = re.match(r'^\s*INDEX\s+(\d+)\s+(\d+):(\d+):(\d+)\s*$', line, re.I)
        if match:
            index, minutes, seconds, frame = map(int, match.groups())
            if current is None or index in tracks[current]['indexes'] or seconds >= 60 or frame >= 75:
                raise ValueError('invalid/duplicate CUE index')
            tracks[current]['indexes'][index] = (minutes*60+seconds)*75+frame
    if tracks.get(1) != dict(mode='MODE1/2352', indexes={1: 0}) or tracks.get(2, {}).get('mode') != 'AUDIO':
        raise ValueError('unsupported raw data-track layout')
    indexes = tracks[2]['indexes']
    if 1 not in indexes: raise ValueError('missing audio INDEX01 boundary')
    sectors = indexes.get(0, indexes[1]); raw = payloads[0]
    if sectors <= 0 or iso.stat().st_size != sectors*2048 or raw.stat().st_size < sectors*2352:
        raise ValueError('raw/ISO data-track lengths differ')
    result = dict(kind='raw_MODE1_2352', payloads=[str(raw)], data_sectors=sectors,
                  sector_bytes=2352, user_offset=16, user_bytes=2048)
    if expected_iso is not None:
        digest = hashlib.sha256()
        with raw.open('rb') as stream:
            for _ in range(sectors):
                sector = stream.read(2352)
                if len(sector) != 2352: raise ValueError('truncated raw data track')
                digest.update(sector[16:2064])
        if digest.hexdigest() != expected_iso: raise ValueError('raw data-track user bytes differ from sealed ISO')
        result['user_data_sha256'] = digest.hexdigest()
    return result


def runtime_inputs(sr, iso, source, system):
    # Existing retail_capture resolves core/system paths from cwd.
    if Path.cwd().resolve() != ROOT: raise ValueError('run from integrating repository root')
    cue = sr.RETAIL/'sonic.cue'
    system = private_system(system)
    paths = [iso, cue, sr.RETAIL/'IPX___.MMD', sr.RETAIL/'SPMM__.MMD', source, Path(__file__),
             ROOT/'tools/staff_times_assets.py', ROOT/'tools/special_retail.py',
             ROOT/'tools/retail_capture.py', ROOT/'tools/extract_mmd.py',
             ROOT/'tools/convert_assets.py', ROOT/'tools/scd_source.py',
             ROOT/'.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib']
    paths += [source.parent/name for name in ('_Macros.inc', '_Variables.inc', 'Functions.asm')]
    paths += [sr.SRC/name for name in LAYOUT_INPUTS]
    bios = [system/name for name in BIOS_NAMES]
    bios = [path for path in bios if path.is_file()]
    if not bios: raise ValueError('no bound retail BIOS candidate')
    payloads = [Path(p) for p in disc_binding(cue, iso)['payloads']]
    paths += bios+payloads
    return {str(path.resolve()): file_sha(path) for path in paths}


def verify_inputs(inputs, sr, source, system, initial):
    if selection(sr, source, system) != initial:
        raise ValueError('runtime source/BIOS presence changed')
    if any(file_sha(Path(path)) != digest for path, digest in inputs.items()):
        raise ValueError('runtime inputs changed')


def run(output, timeout=180, *, system):
    # All core/disc/retail reads start here, never on import.
    import special_retail as sr
    from extract_mmd import disc_files, ISO
    from staff_times_assets import bind_program, parse_source
    from scd_source import SRC
    system = private_system(system)
    if output.resolve().is_relative_to(system) or system.is_relative_to(output.resolve()):
        raise ValueError('capture output and private system directory must be separate')
    output.mkdir(parents=True, exist_ok=False)
    report = {'status': 'pending', 'scope': 'retail DUMMY4 modal; no Saturn/physical acceptance'}
    def save(): (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    save(); began_time = time.monotonic()
    try:
        source = SRC/'Title Screen/Secrets/Best Staff Times.asm'
        initial = selection(sr, source, system)
        inputs = runtime_inputs(sr, ISO, source, system)
        binding = disc_binding(sr.RETAIL/'sonic.cue', ISO, inputs[str(ISO.resolve())])
        report.update(inputs=inputs, initial_selection=initial, disc_binding=binding); save()
        disc = disc_files(ISO.read_bytes())
        program = disc['DUMMY4.MMD']
        if disc['IPX___.MMD'] != (sr.RETAIL/'IPX___.MMD').read_bytes():
            raise ValueError('retail IPX receipt differs from boot disc')
        bind_program(program, parse_source(source.read_text()))
        base = struct.unpack_from('>I', program, 2)[0]; end = base+len(program)-0x100
        scroll = scroll_address(program)
        # Core source queries system/save folders in retro_load_game, not retro_init.
        # Keep the bytes alive in this module-global callback for the fresh process.
        if selection(sr, source, system) != initial or any(file_sha(system/name) != inputs[str((system/name).resolve())] for name, present in initial['bios_presence'].items() if present):
            raise ValueError('private initial BIOS state changed before core load')
        import retail_capture as host
        host.folder = str(system).encode()
        r = sr.Retail(); core = r.core
        ipx = (sr.RETAIL/'IPX___.MMD').read_bytes(); origin = struct.unpack_from('>I', ipx, 2)[0]
        run_mmd, _ = sr.find(ipx[0x100:0x1100], '2f0833c000a12010', origin)
        bram, demo = r.patch
        inject = struct.pack('>HHHIH', 0x303c, r.scmd['SCMD_STAFFTIMES'], 0x4eb9, run_mmd, 0x60fe)
        patch = [bram, (demo[0], demo[1], inject)]; halt = demo[0]+len(inject)-2
        report.update(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                      program_sha256=hashlib.sha256(program).hexdigest(), scroll_address=scroll,
                      run_mmd=run_mmd, patch=[{'address': at, 'old_sha256': hashlib.sha256(old).hexdigest(),
                                            'new_hex': new.hex()} for at, old, new in patch])
        rows, captures, patched, begun, halted = [], {}, False, None, 0
        for frame in range(6000):
            if time.monotonic()-began_time > timeout: raise TimeoutError('retail capture deadline')
            f = frame-begun if begun is not None else -1
            # Stable top; down beyond bottom; both at bottom; up beyond top;
            # both at top; new Start+Down. Capture actual held timing, not delay2.
            core.pad = (2 if 90 <= f < 360 else 3 if 360 <= f < 364 else
                        1 if 380 <= f < 650 else 3 if 650 <= f < 654 else
                        130 if 680 <= f < 684 else 0)
            core.run()
            if not patched and all(core.work_read(at, len(old)) == old for at, old, _ in patch):
                for at, _, new in patch: core.work_write(at, new)
                patched = True
            pc = core.lib.m68k_get_reg(16)
            if patched and begun is None and base <= pc < end: begun = frame
            if begun is None: continue
            f = frame-begun; value = struct.unpack('>H', core.work_read(scroll, 2))[0]
            if f > 900: raise ValueError('StaffTimes modal exceeded900-frame capture bound')
            width, height, pixels = core.frame or (0, 0, b'')
            rows.append({'frame': f, 'pad': core.pad, 'scroll': value, 'width': width, 'height': height,
                         'pixels_crc32': f'{zlib.crc32(pixels):08x}'})
            # Preserve each observed frame for one later fixed-phase comparison.
            # Sparse checkpoints omit fade steps and near-edge scroll positions.
            if core.frame:
                path = output/f'frame-{f}.rgb565'
                path.write_bytes(struct.pack('>HH', width, height)+pixels)
                captures[str(f)] = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                    'width': width, 'height': height, 'scroll': value}
            halted = halted+1 if pc == halt else 0
            if halted >= 30: break
        (output/'trace.json').write_text(json.dumps(rows)+'\n')
        if begun is None or halted < 30 or not captures: raise ValueError('missing entry/return/captures')
        if not any(row['scroll'] == 511 for row in rows): raise ValueError('bottom scroll not observed')
        if not any(row['frame'] > 640 and row['scroll'] == 0 for row in rows): raise ValueError('top return not observed')
        try:
            verify_inputs(inputs, sr, source, system, initial)
        except (ValueError, OSError):
            report['status'] = 'invalidated'; raise
        report.update(status='captured', captures=captures, trace_sha256=hashlib.sha256((output/'trace.json').read_bytes()).hexdigest(),
                      return_frame=rows[-1]['frame']-29, geometry_accepted=False,
                      pending=['independent frame-phase/fade/input comparison', 'full-screen geometry review', 'Saturn journey/audio gates'])
        save(); print('CAPTURED: retail StaffTimes modal; comparison pending')
    except BaseException as e:
        status = 'interrupted' if isinstance(e, KeyboardInterrupt) else ('invalidated' if report['status'] == 'invalidated' else 'failed')
        report.update(status=status, error=repr(e)); save(); raise


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('output', type=Path)
    p.add_argument('--system', type=Path, required=True, help='fresh caller-staged BIOS-only directory under build')
    p.add_argument('--timeout', type=int, default=180); a = p.parse_args()
    if not 1 <= a.timeout <= 600: p.error('timeout must be1..600')
    run(a.output, a.timeout, system=a.system)


if __name__ == '__main__': main()
