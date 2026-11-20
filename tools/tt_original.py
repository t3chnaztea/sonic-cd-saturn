#!/usr/bin/env python3
"""Build a host-compilable copy of R4 originals for a native TT actor fixture.

usage: tt_original.py NAME FILE.C [FILE.C ...] [--replace OLD NEW ...]

Adds PLAYSUB4.C patchg, COLI4.C pcol (actors 100..127 only), SUICIDE.C
enemy/friend_suicide and the 68k Level Random (as tt_orig_random; IO.C
random differs). Scratch casts
((short*)p)[w], ((int*)p)[n], *(int*)&p->actfree[b] and ((char*)p)[b] are
rewritten to the 68-byte PC actor layout without host pointer aliasing.
"""
import re, sys
from level_random import level_random
from pathlib import Path

SRC = Path('build/audit/source/src')


def strip(text):
    text = re.sub(r'/\* Line \d+, Address: 0x[0-9a-f]+ \*/', '', text)
    text = re.sub(r'^#include .*\n', '', text, flags=re.M)
    text = re.sub(r'^(?:static )?sprite_pattern\s*\*?\s*\w+(?:\[\d*\])?\s*=\s*\{.*?\n\};', '', text, flags=re.S | re.M)
    text = re.sub(r'^(?:static )?sprite_pattern\s*\*\s*\w+\[\d*\]\s*=\s*\{[^\n]*\};\n', '', text, flags=re.M)
    text = re.sub(r'^extern sprite_pattern\*? \w+\[\];\n', '', text, flags=re.M)
    text = re.sub(r'(\w+|\([^()]*\))->patbase = [^;]+;', '(void)0;', text)
    return text


ATOM = r'(&?\w+(?:\[[^\[\]]*\])?(?:->\w+)?)'


def scratch(text):
    def word(m):
        t, p, n = m[1], m[2], int(m[3])
        size = 4 if t == 'int' else 2
        return f'(*({t}*)((char*)({p})->actfree+{size * n - 46}))'
    def byte(m):
        return f'(*({m[1]}*)((char*)({m[2]})->actfree+{int(m[3]) - 46}))'
    text = re.sub(r'\(\(char\*\*\)' + ATOM + r'\)\[12\]', r'tt_cursor[(\1) - actwk]', text)
    for _ in range(4):
        old = text
        text = re.sub(r'\(\((unsigned short|short|int)\*\)' + ATOM + r'\)\[(\d+)\]', word, text)
        text = re.sub(r'\(\((char|unsigned char)\*\)' + ATOM + r'\)\[(\d+)\]', byte, text)
        text = re.sub(r'\*\(int\*\)&' + ATOM + r'->actfree\[(\d+)\]',
                      r'((ref_unaligned_int*)(void*)&(\1)->actfree[\2])->value', text)
        text = re.sub(r'\*\(int\*\)&(\w+)\[(\w+)\]\.actfree\[(\d+)\]',
                      r'((ref_unaligned_int*)(void*)&\1[\2].actfree[\3])->value', text)
        if text == old:
            break
    return text


def section(path, start, end=None):
    t = strip((SRC / path).read_text())
    a = t.index(start)
    if end is None:
        b = t.index('\n}', a) + 2
    else:
        b = t.index(end, a)
    return t[a:b] + '\n'


def main():
    args = sys.argv[1:]
    name = args.pop(0)
    replaces = []
    files = []
    sections = []
    while args:
        a = args.pop(0)
        if a == '--replace':
            old = args.pop(0)
            replaces.append((old, args.pop(0)))
        elif a == '--section':
            f, start, end = args.pop(0), args.pop(0), args.pop(0)
            sections.append((f, start, end or None))
        else:
            files.append(a)
    body = ''
    for f in files:
        body += strip((SRC / f).read_text()) + '\n'
    for f, start, end in sections:
        t = strip((SRC / f).read_text())
        a = t.index(start)
        body += (t[a:t.index(end, a)] if end else t[a:]) + '\n'
    extra = section('R4/PLAYSUB4.C', 'void patchg(sprite_status* patchgwk')
    coli = strip((SRC / 'R4/COLI4.C').read_text())
    coli = coli[coli.index('static unsigned char bCarry;') if 'static unsigned char bCarry;' in coli else coli.index('short colitbl'):]
    coli = coli[:coli.index('short pcolitem(')] + coli[coli.index('short pcolnomal('):coli.index('short pcolplay2(')] + coli[coli.index('short pcolspecial('):]
    coli = coli.replace('&actwk[32]', '&actwk[100]').replace('i < 96', 'i < 28')
    suicide = strip((SRC / 'SUICIDE.C').read_text())
    suicide = suicide[suicide.index('short enemy_suicide('):]
    io = level_random('tt_orig_random')  # 68k Level Random, not IO.C random
    text = body + extra + coli + suicide + io
    text = re.sub(r'\brandom\(\)', 'tt_orig_random()', text).replace('int tt_orig_tt_orig_random', 'int tt_orig_random')
    text = text.replace('int tt_orig_tt_orig_random(void)', 'int tt_orig_random(void)')
    for old, new in replaces:
        if old not in text:
            raise SystemExit(f'replace target missing: {old!r}')
        text = text.replace(old, new)
    text = scratch(text)
    header = '''#include "EQU.H"
#include "scd_objects.h"
#include "DIRCOL.H"
#include "ETC.H"
typedef struct __attribute__((packed)) { int value; } ref_unaligned_int;
/* ((char**)o)[12] event cursors: the 32-bit PC kept them in actfree[2..5]. */
static char *tt_cursor[128];
void actionsub(sprite_status*); int frameout_s(sprite_status*); int frameout_s00(sprite_status*,short); void frameout(sprite_status*);
int actwkchk(sprite_status**); int actwkchk2(sprite_status*,sprite_status**); void soundset(short); void scoreup(int);
unsigned char CCset(int,int); unsigned char CSset(unsigned short,unsigned short);
short pcolplay(sprite_status*,sprite_status*); short pcolitem(sprite_status*,sprite_status*);
short hitchk(sprite_status*,sprite_status*); short ride_on_clr(sprite_status*,sprite_status*); short ridechk(sprite_status*,sprite_status*); short playdamageset(sprite_status*,sprite_status*);
void speedset2(sprite_status*); void plairset(void); void sinset(unsigned char,short*,short*);
int tt_orig_random(void); void patchg(sprite_status*,unsigned char**);
short emycol_d(sprite_status*); short emycol_l(sprite_status*,unsigned char); short emycol_r(sprite_status*,unsigned char);
short emycol_l3(sprite_status*,short,short); short emycol_r3(sprite_status*,short,short);
'''
    protos = ''.join(sorted(set(
        m + ';\n' for m in re.findall(r'^((?:static )?(?:void|short|int|unsigned char\*?) \w+\([^\n{;]*\))\s*\{', text, re.M)
        if not m.startswith(('void patchg', 'int tt_orig_random')))))
    out = Path('build/tt') / name
    out.mkdir(parents=True, exist_ok=True)
    (out / 'original.c').write_text(header + protos + text)


if __name__ == '__main__':
    main()
