#!/usr/bin/env python3
"""Run the retail Visual Mode menu (VM____.MMD, IPX.asm VisualMode: RunMMD(SCMD_VISMODE))
in the pinned Sega CD core with scripted input and record every frame.

QA oracle only; nothing here reaches the Saturn build. Like tools/ss8_credits_retail.py,
the IPX Backup RAM call jumps to an injected RunMMD(SCMD_VISMODE). Input, by program
frame (the first frame the menu's code runs):
  0-39      Start held (Main.asm Start forces ctrlData $8000: a held Start never taps)
  110 ...   Down, Down, Down, Down, Down (wrap), Up (wrap), Right, Left, each held 4
            frames, 40 frames apart; the selection must move when the button is released
  430       B held 4 frames: B selects (UpdateSelection .CheckB), with selection 4
Writes build/visual-mode/retail.json (per-frame pixel CRC and menuSelection, the summary)
and build/visual-mode/retail-<name>.rgb565 plus .png screens of each selection.
"""
import json, struct, sys, zlib, hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import special_retail as sr  # noqa: E402

OUT = ROOT / 'build/visual-mode'
UP, DOWN, LEFT, RIGHT, B, START = 1, 2, 4, 8, 16, 128
PRESSES = [(110, DOWN), (150, DOWN), (190, DOWN), (230, DOWN), (270, DOWN), (310, UP), (350, RIGHT), (390, LEFT), (430, B)]
# Screens: (name, program frame, menuSelection expected there).
SHOTS = [('sel0', 105, 0), ('sel1', 140, 1), ('sel2', 180, 2), ('sel3', 220, 3), ('sel4', 260, 4),
         ('wrap0', 300, 0), ('up4', 340, 4), ('right3', 380, 3), ('left4', 420, 4)]


def labels():
    text = (sr.SRC / 'Visual Mode/Main.asm').read_text().split('; MMD header', 1)[0]
    s, _ = sr.rs_symbols(text, {'WORKRAM': 0xff0000}, 0xffffff)
    return s


def pad_at(f):
    if f < 40:
        return START
    for at, button in PRESSES:
        if at <= f < at + 4:
            return button
    return 0


def main():
    v = labels()
    r = sr.Retail()
    ipx = (sr.RETAIL / 'IPX___.MMD').read_bytes()
    origin = struct.unpack_from('>I', ipx, 2)[0]
    code = ipx[0x100:0x1100]
    run_mmd, _ = sr.find(code, '2f0833c000a12010', origin)
    (bram_at, bram_old, bram_new), (demo_at, demo_old, _) = r.patch
    inject = struct.pack('>HH', 0x303c, r.scmd['SCMD_VISMODE']) + struct.pack('>HI', 0x4eb9, run_mmd) + bytes.fromhex('60fe')
    patch = [(bram_at, bram_old, bram_new), (demo_at, demo_old, inject)]
    halt = demo_at + len(inject) - 2
    core = r.core
    rows, shots = [], {}
    patched, begun, halted, frame, exit_frame = False, None, 0, 0, None
    OUT.mkdir(parents=True, exist_ok=True)
    while frame < 4000 and halted < 30:
        core.pad = pad_at(frame - begun) if begun is not None else 0
        core.run()
        frame += 1
        if not patched and all(core.work_read(at, len(old)) == old for at, old, _ in patch):
            for at, _, new in patch:
                core.work_write(at, new)
            patched = True
        pc = core.lib.m68k_get_reg(16)
        if patched and begun is None and 0xff2000 <= pc < 0xffb000:
            begun = frame
        if begun is None:
            continue
        f = frame - begun
        width, height, pixels = core.frame or (0, 0, b'')
        sel = struct.unpack('>H', core.work_read(v['menuSelection'], 2))[0]
        flag = core.work_read(v['exitFlag'], 1)[0]
        if flag and exit_frame is None:
            exit_frame = f
        rows.append({'frame': f, 'width': width, 'height': height, 'pixels': '%08x' % zlib.crc32(pixels),
                     'sel': sel, 'exit': flag, 'pad': core.pad, 'pc': pc})
        for name, at, _ in SHOTS:
            if f == at and core.frame:
                (OUT / f'retail-{name}.rgb565').write_bytes(struct.pack('>HH', width, height) + pixels)
                sr.png(OUT / f'retail-{name}.png', core.frame)
                shots[name] = {'frame': f, 'sel': sel, 'pixels': rows[-1]['pixels'], 'width': width, 'height': height}
        halted = halted + 1 if pc == halt else 0
    assert halted >= 30, ('Visual Mode did not return', frame, hex(pc))
    shown = [x for x in rows if x['width'] == 320]
    # Fade in: distinct pictures from the first non-black one to the sel0 steady picture.
    steady = shots['sel0']['pixels']
    first_steady = next(x['frame'] for x in shown if x['pixels'] == steady)
    # Frame 0 still shows the previous program's picture; frame 1 is the cleared screen.
    black = shown[1]['pixels']
    lit = next(x['frame'] for x in shown[1:] if x['pixels'] != black)
    # Fade out: from the exit flag to the last change of picture.
    after = [x for x in shown if x['frame'] >= exit_frame]
    last_change = max(x['frame'] for i, x in enumerate(after[1:], 1) if x['pixels'] != after[i - 1]['pixels'])
    by = {x['frame']: x for x in rows}
    moves = []
    for at, button in PRESSES[:-1]:
        before = by[at - 1]['sel']
        changed = next(x for x in rows if x['frame'] >= at and x['sel'] != before)
        moves.append({'press': at, 'button': button, 'from': before, 'to': changed['sel'],
                      'frames_after_press': changed['frame'] - at})
    summary = {'frames': len(rows), 'first_lit_frame': lit, 'first_steady_frame': first_steady, 'fade_in_frames': first_steady - lit + 1,
               'start_held_exit': any(x['exit'] for x in rows if x['frame'] < 100),
               'exit_frame': exit_frame, 'exit_selection': next(x['sel'] for x in rows if x['frame'] == exit_frame),
               'fade_out_frames': last_change - exit_frame, 'moves': moves, 'shots': shots,
               'inputs': {'visual_mode_retail.py': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                          'IPX___.MMD': hashlib.sha256(ipx).hexdigest(),
                          'sonic.iso.sha256.json': hashlib.sha256((sr.RETAIL / 'sonic.iso.sha256.json').read_bytes()).hexdigest()}}
    for name, at, want in SHOTS:
        assert shots[name]['sel'] == want, (name, shots[name])
    (OUT / 'retail.json').write_text(json.dumps({'summary': summary, 'rows': rows}, separators=(',', ':')) + '\n')
    print(json.dumps({k: summary[k] for k in summary if k not in ('shots', 'inputs')}))


if __name__ == '__main__':
    main()
