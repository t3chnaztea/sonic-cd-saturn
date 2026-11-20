#!/usr/bin/env python3
"""Run the retail sound test pictures (Sound Test Image.asm: NISI.MMD, DUMMY0-3.MMD;
IPX.asm SoundTest exits 2-6, RunMMD(SCMD_FUNISINF .. SCMD_CUTESONIC)) in the pinned
Sega CD core and record each one.

QA oracle only; nothing here reaches the Saturn build. As tools/visual_mode_retail.py,
the IPX Backup RAM call jumps to an injected RunMMD(SCMD_<picture>). Input, by program
frame (the first frame the picture's code runs): none until START_AT, then Start held
4 frames (the .Loop exit). Writes build/secret-images/retail.json (per picture: the
first lit, first steady and exit frames, the fade-out length) and
build/secret-images/retail-<n>.rgb565 plus .png of each steady picture (frame SHOT, after the fade in).
"""
import json, struct, sys, zlib, hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import special_retail as sr  # noqa: E402
from extract_mmd import disc_files, ISO  # noqa: E402

OUT = ROOT / 'build/secret-images'
START = 128
SCMDS = ['SCMD_FUNISINF', 'SCMD_MCSONIC', 'SCMD_TAILS', 'SCMD_BATMAN', 'SCMD_CUTESONIC']
FILES = ['NISI.MMD', 'DUMMY0.MMD', 'DUMMY1.MMD', 'DUMMY2.MMD', 'DUMMY3.MMD']
SHOT, START_AT = 112, 120


def run(n, scmd):
    r = sr.Retail()
    mmd = disc_files(ISO.read_bytes())[FILES[n - 1]]
    base = struct.unpack_from('>I', mmd, 2)[0]   # MMD header: load address
    end = base + len(mmd) - 0x100
    ipx = (sr.RETAIL / 'IPX___.MMD').read_bytes()
    origin = struct.unpack_from('>I', ipx, 2)[0]
    run_mmd, _ = sr.find(ipx[0x100:0x1100], '2f0833c000a12010', origin)
    (bram_at, bram_old, bram_new), (demo_at, demo_old, _) = r.patch
    inject = struct.pack('>HH', 0x303c, r.scmd[scmd]) + struct.pack('>HI', 0x4eb9, run_mmd) + bytes.fromhex('60fe')
    patch = [(bram_at, bram_old, bram_new), (demo_at, demo_old, inject)]
    halt = demo_at + len(inject) - 2
    core = r.core
    rows = []
    patched, begun, halted, frame = False, None, 0, 0
    while frame < 4000 and halted < 30:
        f = frame - begun if begun is not None else None
        core.pad = START if f is not None and START_AT <= f < START_AT + 4 else 0
        core.run()
        frame += 1
        if not patched and all(core.work_read(at, len(old)) == old for at, old, _ in patch):
            for at, _, new in patch:
                core.work_write(at, new)
            patched = True
        pc = core.lib.m68k_get_reg(16)
        if patched and begun is None and base <= pc < end:
            begun = frame
        if begun is None:
            continue
        f = frame - begun
        width, height, pixels = core.frame or (0, 0, b'')
        rows.append({'frame': f, 'width': width, 'height': height, 'pixels': '%08x' % zlib.crc32(pixels), 'pad': core.pad})
        if f == SHOT and core.frame:
            (OUT / f'retail-{n}.rgb565').write_bytes(struct.pack('>HH', width, height) + pixels)
            sr.png(OUT / f'retail-{n}.png', core.frame)
        halted = halted + 1 if pc == halt else 0
    assert halted >= 30, (scmd, 'did not return', frame, hex(pc))
    shown = [x for x in rows if x['width'] == 320]
    steady = next(x['pixels'] for x in shown if x['frame'] == SHOT)
    first_steady = next(x['frame'] for x in shown if x['pixels'] == steady)
    changes = [x['frame'] for i, x in enumerate(shown[1:], 1) if x['pixels'] != shown[i - 1]['pixels']]
    after = [c for c in changes if c > START_AT]
    return {'scmd': scmd, 'first_change': changes[0] if changes else None, 'first_steady_frame': first_steady,
            'steady_through': max(c for c in changes if c <= SHOT) if changes else None,
            'fade_out_first': after[0] if after else None, 'fade_out_last': after[-1] if after else None,
            'fade_out_changes': len(after), 'return_frame': rows[-1]['frame'] - 29, 'changes': changes}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {str(n): run(n, s) for n, s in enumerate(SCMDS, 1)}
    summary['inputs'] = {'secret_images_retail.py': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                         'sonic.iso.sha256.json': hashlib.sha256((sr.RETAIL / 'sonic.iso.sha256.json').read_bytes()).hexdigest()}
    (OUT / 'retail.json').write_text(json.dumps(summary, indent=1) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'inputs'}))


if __name__ == '__main__':
    main()
