#!/usr/bin/env python3
"""Build browser hosts offline in a NEW build/ directory; never run make in .deps/."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--emsdk', required=True, type=Path)
    args = parser.parse_args()
    out, sdk = args.out.resolve(), args.emsdk.resolve()
    if not out.is_relative_to(ROOT/'build') or out.exists():
        parser.error('--out must name a new directory under build/')
    emcc = sdk/'upstream/emscripten/emcc'
    if not emcc.is_file(): parser.error('Installed emcc is required; this tool never downloads it')
    lock = json.loads((ROOT/'sources.lock.json').read_text())
    commit = subprocess.check_output(['git', '-C', str(ROOT/'.deps/genesis-plus-gx'), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != lock['genesis-plus-gx']['commit']: parser.error('Genesis source commit differs')
    out.mkdir(parents=True)
    source = out/'source'
    shutil.copytree(ROOT/'.deps/genesis-plus-gx', source,
                    ignore=shutil.ignore_patterns('.git', '*.o', '*.a', '*.so', '*.dylib', '*.bc'))
    env = dict(os.environ, EMCC_FROZEN_CACHE='1', EMCC_CORES='1')
    records = []

    def run(name, command, cwd=ROOT):
        start = time.monotonic()
        with (out/(name+'.log')).open('w') as log:
            result = subprocess.run(list(map(str, command)), cwd=cwd, env=env, stdout=log, stderr=log)
        records.append(dict(name=name, exit_code=result.returncode, wall_seconds=time.monotonic()-start))
        (out/'builds.json').write_text(json.dumps(records, indent=2)+'\n')
        if result.returncode: raise RuntimeError(name+' failed; inspect its local log')

    run('genesis-objects', ['make', '-f', 'Makefile.libretro', 'platform=emscripten', 'HAVE_CHD=0',
        'CC='+str(emcc), 'CXX='+str(emcc.parent/'em++'), 'AR='+str(emcc.parent/'emar'),
        'GIT_VERSION= '+commit[:7], '-j1'], source)
    shutil.copyfile(source/'genesis_plus_gx_libretro_emscripten.bc', source/'core.a')
    common = ['-O2', '-sMODULARIZE=1', '-sWASM_ASYNC_COMPILATION=0', '-sENVIRONMENT=node,web,worker', '-sALLOW_MEMORY_GROWTH=1',
        '-ffile-prefix-map='+str(ROOT)+'=/project']
    headers = ['core', 'core/z80', 'core/m68k', 'core/ntsc', 'core/sound', 'core/sound/minimp3',
        'core/input_hw', 'core/cd_hw', 'core/cart_hw', 'core/cart_hw/svp', 'libretro',
        'libretro/libretro-common/include', 'libretro/deps/zlib-1.2.11']
    defines = ['__LIBRETRO__', 'USE_LIBRETRO_VFS', 'USE_16BPP_RENDERING', 'FRONTEND_SUPPORTS_RGB565',
        'LSB_FIRST', 'ALIGN_LONG', 'BYTE_ORDER=LITTLE_ENDIAN', 'HAVE_ZLIB', 'M68K_OVERCLOCK_SHIFT=20',
        'Z80_OVERCLOCK_SHIFT=20', 'HAVE_YM3438_CORE', 'HAVE_OPLL_CORE', 'MAXROMSIZE=10485760', 'INLINE=static inline']
    vfs = ['streams/file_stream.c', 'streams/file_stream_transforms.c', 'compat/fopen_utf8.c',
        'compat/compat_snprintf.c', 'compat/compat_strl.c', 'compat/compat_strcasestr.c',
        'compat/compat_posix_string.c', 'encodings/encoding_utf.c', 'file/file_path.c',
        'file/retro_dirent.c', 'lists/string_list.c', 'lists/dir_list.c', 'memmap/memalign.c',
        'string/stdstring.c', 'vfs/vfs_implementation.c']
    names = {'patcher_init', 'patcher_symbol', 'malloc', 'free', 'retro_init', 'retro_deinit', 'retro_run',
        'retro_load_game', 'retro_unload_game', 'retro_set_controller_port_device', 'retro_set_environment',
        'retro_set_video_refresh', 'retro_set_audio_sample', 'retro_set_audio_sample_batch',
        'retro_set_input_poll', 'retro_set_input_state'}
    for name in ('capture_retail_audio.py', 'special_retail.py', 'retail_probe.py', 'zone_object_source.py', 'ss_flower_source.py'):
        names.update(re.findall(r'lib\.((?:retro_|m68k_|s68k_|gen_)\w+)', (ROOT/'tools'/name).read_text()))
    exports = ['_'+name for name in sorted(names)]
    run('genesis', [emcc, ROOT/'tools/patcher-wasm/genesis.c', source/'core.a',
        *[source/'libretro/libretro-common'/p for p in vfs], *common,
        *['-I'+str(source/p) for p in headers], *['-D'+d for d in defines],
        '-sINITIAL_MEMORY=67108864', '-sALLOW_TABLE_GROWTH=1', '-sEXPORT_NAME=GenesisFactory',
        '-sEXPORTED_FUNCTIONS='+json.dumps(exports),
        '-sEXPORTED_RUNTIME_METHODS='+json.dumps(['FS', 'HEAPU8', 'ccall', 'addFunction', 'removeFunction']),
        '-o', out/'genesis.js'])
    cli = ['-sEXPORTED_RUNTIME_METHODS='+json.dumps(['FS', 'callMain'])]
    run('sonic', [emcc, ROOT/'tools/patcher-wasm/sonic.c', ROOT/'src/sonic_art.c', '-Isrc',
                  *common, *cli, '-sEXPORT_NAME=SonicFactory', '-o', out/'sonic.js'])
    run('fmv', [emcc, ROOT/'tools/fmv_stm_host.c', ROOT/'src/fmv_stm.c',
                *common, *cli, '-sEXPORT_NAME=FmvFactory', '-o', out/'fmv.js'])
    beetle = ROOT/'.deps/beetle-saturn'
    run('iso', [emcc, ROOT/'tools/iso_to_raw.c', beetle/'mednafen/cdrom/lec.c',
        '-I'+str(beetle/'libretro-common/include'), '-I'+str(beetle/'mednafen/cdrom'),
        *common, *cli, '-sEXPORT_NAME=IsoFactory', '-o', out/'iso.js'])
    artifacts = [{'name':p.name, 'bytes':p.stat().st_size, 'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
                 for p in sorted(out.iterdir()) if p.suffix in ('.wasm', '.js')]
    (out/'artifacts.json').write_text(json.dumps({'genesis_commit':commit, 'files':artifacts}, indent=2)+'\n')
    print('PASS: offline browser WASM hosts built; one compiler job; frozen cache')


if __name__ == '__main__': main()
