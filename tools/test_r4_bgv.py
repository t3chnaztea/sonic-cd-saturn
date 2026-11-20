#!/usr/bin/env python3
"""Tidal Tempest background Y (scrb_v_posit) vs the compiled original, across
the Act 2/3 vertical camera wrap.

Each SCR41B-D/42A/42C/43C/43D.C's own scrbinit(), sv_move_minus/plus/sub(),
scrv_up_ch/scrv_down_ch(), scrv_move() and scrollb_hv() are compiled unchanged
twice.  One update = one camera move (the calls scroll_v makes) then scroll()'s
`scrollb_hv(0, scra_vz << 7)`.  Copy A runs both; copy B runs only the camera
(as src/camera_v.c does on Saturn) and native src/background_r4.c
scd_r4_scrbinit/scd_r4_scroll_v do the rest on B's scrb_v_posit.  Random walks
push the camera past both limits, so the camera code moves it by 2048 and masks
scrb_v_posit mid-update.  Native background Y must equal A's scrb_v_posit.w.h.
"""
import ctypes as C
import random
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from test_cc_palette import function  # noqa: E402

SOURCE = ROOT/'build/audit/source/src/R4'
OUT = ROOT/'build/tt/bgv'
PROGRAMS = {1: 'SCR41B', 2: 'SCR41C', 3: 'SCR41D', 4: 'SCR42A', 6: 'SCR42C', 10: 'SCR43C', 11: 'SCR43D'}
HARNESS = r'''
#include <stdint.h>
typedef struct { unsigned char l, h; } short_chars;
typedef union { short w; short_chars b; } short_union;
typedef struct { short l, h; } int_shorts;
typedef struct { unsigned char l0, l, h0, h; } int_chars;
typedef union { int l; int_shorts w; int_chars b; } int_union;
typedef struct { unsigned char l, h; } ushort_uchars;
typedef union { unsigned short w; ushort_uchars b; } ushort_union;
typedef struct { unsigned short l, h; } uint_ushorts;
typedef struct { unsigned char l0, l, h0, h; } uint_uchars;
typedef union { unsigned int l; uint_ushorts w; uint_uchars b; } uint_union;
typedef struct { int_union xposi, yposi; } sprite_status;
sprite_status actwk[1];
ushort_union scrflaga, scrflagb, scrflagc, scrflagz;
int_union scra_h_posit, scra_v_posit, scrb_h_posit, scrb_v_posit, scrc_h_posit, scrc_v_posit, scrz_h_posit, scrz_v_posit;
short scra_vz, scralim_up, scralim_down;
unsigned char scra_v_count, scrb_h_count, scrb_v_count;
short hscrollwork[256];
%(body)s
void init(int y, int up, int down) {
    scralim_up = up; scralim_down = down; scra_v_count = scrb_h_count = scrb_v_count = 0;
    scra_v_posit.l = y << 16; scrb_h_posit.l = 0; actwk[0].yposi.l = y << 16; scrbinit(0);
}
/* kind 0: sv_move_minus(amount), 1: sv_move_plus(amount), 2: sv_move_sub(amount) */
int camera_only;
void update(int kind, int amount) {
    if (kind == 0) sv_move_minus((unsigned short)amount);
    else if (kind == 1) sv_move_plus((unsigned short)amount);
    else sv_move_sub((unsigned short)amount);
    if (!camera_only) %(hv)s
}
int *scrb(void) { return &scrb_v_posit.l; }
int vz(void) { return scra_vz; }
int camera(void) { return scra_v_posit.l; }
int background(void) { return scrb_v_posit.w.h; }
'''


def original(name, tag=''):
    src = (SOURCE/f'{name}.C').read_text()
    names = ('scrbinit', 'sv_move_minus', 'sv_move_plus', 'sv_move_sub', 'scrv_up_ch', 'scrv_down_ch', 'scrv_move', 'scrollb_hv')
    protos = []
    for n in names:
        m = re.search(r'void '+n+r'\(([^)]*)\)', src)
        protos.append(f'void {n}({m[1]});')
    body = '\n'.join(protos)+'\n'+'\n'.join(function(src, n) for n in names)
    pointer = 'int_union*' in re.search(r'void scrollb_hv\(([^)]*)\)', src)[1]
    hv = ('{ int_union a, b; a.l = 0; b.l = scra_vz << 7; scrollb_hv(&a, &b); }' if pointer
          else 'scrollb_hv(0, scra_vz << 7);')
    path = OUT/f'original-{name}{tag}.c'
    path.write_text(HARNESS % dict(body=body, hv=hv))
    lib = path.with_suffix('.dylib')
    subprocess.run(['clang', '-std=c11', '-O1', '-fwrapv', '-fsigned-char', '-w', '-shared', '-fPIC', str(path), '-o', str(lib)], check=True)
    dll = C.CDLL(str(lib))
    dll.init.argtypes = [C.c_int, C.c_int, C.c_int]
    dll.update.argtypes = [C.c_int, C.c_int]
    dll.scrb.restype = C.POINTER(C.c_int32)
    return dll


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    lib = OUT/'native.dylib'
    subprocess.run(['clang', '-std=c11', '-O2', '-fwrapv', '-Wall', '-Wextra', '-Werror', '-Isrc', '-dynamiclib',
                    'src/background_r4.c', '-o', str(lib)], cwd=ROOT, check=True)
    native = C.CDLL(str(lib))
    native.scd_r4_scrbinit.argtypes = [C.POINTER(C.c_int32), C.c_int]
    native.scd_r4_scroll_v.argtypes = [C.c_uint, C.POINTER(C.c_int32), C.c_int16]
    native.scd_r4_background_y.argtypes = [C.c_uint, C.c_int, C.c_int]
    rng = random.Random(42)
    updates = wraps = 0
    for pid, name in PROGRAMS.items():
        full, cam_only = original(name), original(name, '-camera')
        C.c_int.in_dll(cam_only, 'camera_only').value = 1
        scrb = cam_only.scrb()
        down = 1296 if pid < 4 else 2048
        for walk in range(40):
            up = (0, -256)[walk % 2]
            y0 = rng.randrange(0, down+1)
            full.init(y0, up, down)
            cam_only.init(y0, up, down)
            want0 = scrb[0]
            native.scd_r4_camera_v_reset()
            native.scd_r4_scrbinit(scrb, y0)
            assert scrb[0] == want0, (name, 'scrbinit', y0)
            bias = rng.choice((-1, 1))
            for _ in range(600):
                if rng.random() < 0.02:
                    bias = -bias
                kind = rng.randrange(3)
                if kind < 2:
                    kind = 0 if (bias < 0) == (rng.random() < 0.8) else 1
                    amount = rng.choice((512, 1536, 4096))
                else:
                    amount = rng.randrange(-16, 17)*bias if rng.random() < 0.8 else rng.randrange(-16, 17)
                before = full.camera()
                full.update(kind, amount & 0xffff)
                cam_only.update(kind, amount & 0xffff)
                cam = full.camera()
                assert cam == cam_only.camera()
                wraps += abs((cam >> 16) - (before >> 16)) > 1024
                native.scd_r4_scroll_v(pid, scrb, cam_only.vz())
                got = native.scd_r4_background_y(pid, 0, C.c_int16(cam >> 16).value)
                want = full.background()
                if got != want or scrb[0] != C.c_int32.in_dll(full, 'scrb_v_posit').value:
                    raise AssertionError((name, walk, updates, kind, amount, hex(before), hex(cam), got, want))
                updates += 1
    if wraps < 100:
        raise AssertionError(('too few wraps exercised', wraps))
    print(f'PASS: TT background Y: {updates} compiled-original/native scrb_v_posit updates across {wraps} camera wraps of 7 programs')


if __name__ == '__main__':
    main()
