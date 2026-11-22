#!/usr/bin/env python3
"""Compile the complete upstream R11A module for SH-2; do not imply playability."""
import json
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / '.deps/soniccd'
OUT = ROOT / 'build/audit'

def main(source_only=False):
    OUT.mkdir(parents=True, exist_ok=True)
    adapted = OUT / 'source'
    for original in (UPSTREAM / 'src').rglob('*'):
        if original.suffix.upper() not in ('.C', '.H'):
            continue
        target = adapted / original.relative_to(UPSTREAM)
        target.parent.mkdir(parents=True, exist_ok=True)
        content = original.read_text()
        content = re.sub(r'(#include\s+"[^"]+)"',
                         lambda m: m[1].replace('\\', '/') + '"', content)
        # Metrowerks accepts a flattened anonymous-union initializer which GCC
        # rejects. R11A accesses only spra, so retain its exact fixed capacity.
        content = content.replace('  union {\n    sprite_data spra[20];\n    sprite_data spr[];\n  };',
                                  '  sprite_data spra[20];')
        if original.name == 'EMIE1.C':
            content = re.sub(r'\bspeedset\b', 'emie_speedset', content)
        target.write_text(content)
    if source_only:   # the adapted text only (build-time table generators read it)
        return 0
    makefile = (UPSTREAM / 'Makefile').read_text().replace('\\\n', ' ')
    variables = dict(re.findall(r'^(\w+)\s*:=\s*(.*)$', makefile, re.M))
    def expand(value):
        return re.sub(r'\$\((\w+)\)', lambda m: expand(variables[m[1]]), value)
    sources = expand(variables['R11A_SOURCES']).split()
    compiler = ROOT / '.toolchain/bin/sh-elf-gcc'
    results = []
    objects = []
    for source in sources:
        obj = OUT / (source.replace('/', '_') + '.o')
        command = [str(compiler), '-x', 'c', '-std=gnu99', '-m2', '-mb', '-Os',
                   '-fsigned-char', '-fwrapv', '-fno-strict-aliasing',
                   '-fno-builtin', '-ffreestanding', '-ffunction-sections',
                   '-fdata-sections', '-Wno-implicit-function-declaration',
                   '-DR1', '-DR11A', '-DEDIT_DATA_ENTRY_COUNT=52',
                   '-I', str(adapted / 'src'), '-I', str(adapted / 'src/R1'),
                   '-c', str(adapted / source), '-o', str(obj)]
        result = subprocess.run(command, capture_output=True, text=True)
        (OUT / (obj.name + '.log')).write_text(result.stderr)
        results.append({'source': source, 'returncode': result.returncode,
                        'diagnostics': result.stderr})
        if result.returncode == 0:
            objects.append(obj)
    report = {'commit': subprocess.check_output(['git', '-C', str(UPSTREAM),
                'rev-parse', 'HEAD'], text=True).strip(),
              'compiled': len(objects), 'total': len(sources), 'files': results,
              'runtime_validated': False,
              'hazards': ['Little-endian union member order',
                          'Raw short/int casts into sprite_status',
                          'Original asset formats differ from PC frontend',
                          'Unimplemented renderer/audio/file callbacks']}
    if len(objects) == len(sources):
        linked = OUT / 'r11a-unadapted.o'
        subprocess.run([str(ROOT / '.toolchain/bin/sh-elf-ld'), '-r',
                        *map(str, objects), '-o', str(linked)], check=True)
        report['size'] = subprocess.check_output(
            [str(ROOT / '.toolchain/bin/sh-elf-size'), str(linked)], text=True)
        report['undefined_symbols'] = subprocess.check_output(
            [str(ROOT / '.toolchain/bin/sh-elf-nm'), '-u', str(linked)], text=True)
    (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f"R11A compiled: {len(objects)}/{len(sources)}. Runtime not validated.")
    for result in results:
        if result['returncode']:
            print(result['source'], result['diagnostics'][:1200])
    print(report.get('size', ''))
    print(report.get('undefined_symbols', ''))
    return 0 if len(objects) == len(sources) else 1

if __name__ == '__main__':
    import sys
    raise SystemExit(main('--source-only' in sys.argv[1:]))
