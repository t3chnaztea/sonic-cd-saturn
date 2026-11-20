#!/usr/bin/env python3
"""Zone table overlays (src/saturn.x) must ship as built.

Host-only. For the last Saturn link (build/saturn/*.elf) it checks that every overlay
section .zone_<Z> named by the Makefile's ZONE_TABLES equals cd/ZTR<Z>.BIN (size and
SHA-256), sits at ___zone_tables_start and fits the range; that the program image
(build .bin and cd/A.BIN) is the ELF with the overlays stripped; that src/main.c loads
each ZTR<Z>.BIN; that the link script keeps its heap ASSERT and that the ASSERT's title
terms still equal their sources (TLSF control and pool overhead, BIOS library, sprite
command list with memalign slack, the title state's TLSF class bound); and, when the disc image exists, that every ZTR file's
first and last sector are on it. A stale or missing ZTR file therefore fails fast QA.
"""
import hashlib,re,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BIN=ROOT/'.toolchain/bin'
ELF=ROOT/'build/saturn/sonic-cd-saturn-prototype.elf'
PROGRAM=ROOT/'build/saturn/sonic-cd-saturn-prototype.bin'
DISC=ROOT/'dist/sonic-cd-saturn-prototype.bin'
HEAP_END=0x06100000

def fail(message):sys.exit(f'FAIL: zone tables: {message}')
def sha(data):return hashlib.sha256(data).hexdigest()

makefile=(ROOT/'Makefile').read_text()
m=re.search(r'^ZONE_TABLES:=\s*(.+)$',makefile,re.M)
if not m:fail('Makefile defines no ZONE_TABLES')
zones=m.group(1).split()
if not re.search(r'^SH_SPECS:=\s*yaul\.specs yaul-main\.specs \$\(abspath src/saturn\.specs\)\s*$',makefile,re.M):
    fail('Makefile SH_SPECS does not select src/saturn.specs after the yaul specs')
if '-T src/saturn.x' not in (ROOT/'src/saturn.specs').read_text():fail('src/saturn.specs does not link with src/saturn.x')
script=(ROOT/'src/saturn.x').read_text()
if re.search(r'^\s*MEMORY\b',script,re.M):fail('src/saturn.x has a MEMORY region (its counter ignores OVERLAY)')
a=re.search(r'ASSERT\s*\(\s*0x06100000\s*-\s*___end\s*>=\s*([0-9+ ]+),',script)
if not a:fail('src/saturn.x lost its heap ASSERT')
terms=[int(t) for t in a.group(1).split('+')]
if len(terms)!=7:fail(f'heap ASSERT has {len(terms)} terms, expected 7 (TLSF control, pool overhead, BIOS, list, commands, title class, pool alignment)')
for z in zones:
    if not re.search(rf'\.zone_{z}\s*\{{',script):fail(f'src/saturn.x has no .zone_{z} overlay')
    if f'"ZTR{z[1:]}.BIN"' not in (ROOT/'src/main.c').read_text():fail(f'src/main.c does not load ZTR{z[1:]}.BIN')

# Each ASSERT term must equal its source: the heap allocations live at the title.
tlsf=(ROOT/'.deps/libyaul/libyaul/kernel/mm/tlsf.c').read_text()
def enum(name):return int(re.findall(rf'\b{name}\s*=\s*(\d+)',tlsf)[-1])  # the 32-bit (#else) value follows the 64-bit one
sl=1<<int(re.search(r'SL_INDEX_COUNT_LOG2\s*=\s*(\d+)',tlsf).group(1))
fl=enum('FL_INDEX_MAX')-(int(re.search(r'SL_INDEX_COUNT_LOG2\s*=\s*(\d+)',tlsf).group(1))+enum('ALIGN_SIZE_LOG2'))+1
control=16+4+4*fl+4*fl*sl
b=re.search(r'uint32_t library\[(\d+)\],work\[(\d+)\+(\d+)\];\s*\}\s*bios_memory',(ROOT/'src/save_saturn.c').read_text())
if not b:fail('src/save_saturn.c bios_memory layout changed')
bios=4*(int(b.group(1))+int(b.group(2))+int(b.group(3)))
c=re.search(r'vdp1_cmdt_list_alloc\((\d+)\+SCD_OBJECT_CAPACITY\)',(ROOT/'src/main.c').read_text())
if not c:fail('src/main.c sprite_init command list size changed')
with tempfile.TemporaryDirectory() as tmp:
    probe=Path(tmp)/'size.c';inc=ROOT/'.toolchain/sh-elf/include/yaul'
    probe.write_text('#include <yaul.h>\n#include "scd_objects.h"\n#include "title.h"\n'
        'unsigned list_size=sizeof(vdp1_cmdt_list_t),cmdt_size=sizeof(vdp1_cmdt_t),capacity=SCD_OBJECT_CAPACITY,title_size=sizeof(scd_title);\n')
    asm=subprocess.run([BIN/'sh-elf-gcc','-m2','-mb','-ffreestanding','-fno-lto',f'-I{inc}',f'-I{inc}/common','-Isrc','-Iassets/generated','-S','-o','-',probe],cwd=ROOT,capture_output=True,text=True)
    sizes={k:int(v) for k,v in re.findall(r'_(list_size|cmdt_size|capacity|title_size):\s*\.long\s+(\d+)',asm.stdout)}
    if asm.returncode or len(sizes)!=4:fail(f'cannot size the heap allocations: {asm.stderr.strip()[:200]}')
# TLSF: every used block carries a 4 B size header; the pool adds two; memalign(align) may
# leave a leading gap of up to align + gap_minimum (sizeof(block_header_t), 16 B); and a
# request is served only from a free block of its class (mapping_search rounds up).
SL_LOG2=int(re.search(r'SL_INDEX_COUNT_LOG2\s*=\s*(\d+)',tlsf).group(1));ALIGN=1<<enum('ALIGN_SIZE_LOG2')
HDR=4;GAP_MIN=16
def tlsf_class(size):
    size=(size+ALIGN-1)//ALIGN*ALIGN
    if size>=1<<(SL_LOG2+enum('ALIGN_SIZE_LOG2')):
        size+=(1<<(size.bit_length()-1-SL_LOG2))-1
        size&=~((1<<(size.bit_length()-1-SL_LOG2))-1)
    return size
commands=(int(c.group(1))+sizes['capacity'])*sizes['cmdt_size']
expected=[control,2*HDR,bios+HDR,max((sizes['list_size']+ALIGN-1)//ALIGN*ALIGN,12)+HDR,
          commands+sizes['cmdt_size']+GAP_MIN+HDR,tlsf_class(sizes['title_size']),ALIGN-1]
names=['TLSF control','pool overhead','BIOS library','command list','commands (memalign)','title TLSF class bound','pool alignment']
for name,want,have in zip(names,expected,terms):
    if want!=have:fail(f'heap ASSERT {name} term is {have} B but its source gives {want} B')
if not ELF.is_file():fail(f'{ELF.relative_to(ROOT)} is missing; build first')
symbols={r.split()[2]:int(r.split()[0],16) for r in subprocess.check_output([BIN/'sh-elf-nm',ELF],text=True).splitlines() if len(r.split())==3}
start,end,program_end=symbols['___zone_tables_start'],symbols['___zone_tables_end'],symbols['___end']
headers=subprocess.check_output([BIN/'sh-elf-objdump','-h',ELF],text=True)
sections={p[1]:(int(p[2],16),int(p[3],16)) for p in (l.split() for l in headers.splitlines()) if len(p)>=7 and p[1].startswith('.zone_')}
margin=HEAP_END-program_end-sum(terms)
if margin<0:fail(f'heap short by {-margin} B')
report=[]
with tempfile.TemporaryDirectory() as tmp:
    for z in zones:
        name=f'.zone_{z}'
        if name not in sections:fail(f'the ELF has no {name}')
        size,vma=sections[name]
        if vma!=start or start+size>end:fail(f'{name} at {vma:#x}+{size} is outside {start:#x}..{end:#x}')
        out=Path(tmp)/f'{z}.bin'
        subprocess.run([BIN/'sh-elf-objcopy','-O','binary','-j',name,ELF,out],check=True)
        built=out.read_bytes();shipped=ROOT/f'cd/ZTR{z[1:]}.BIN'
        if not shipped.is_file():fail(f'{shipped.relative_to(ROOT)} is missing')
        data=shipped.read_bytes()
        if len(data)!=size or sha(data)!=sha(built):fail(f'{shipped.relative_to(ROOT)} ({len(data)} B) differs from the ELF {name} ({size} B); rebuild')
        report.append((z,data))
    stripped=Path(tmp)/'program.bin'
    subprocess.run([BIN/'sh-elf-objcopy','-O','binary',*[a for z in zones for a in ('-R',f'.zone_{z}')],ELF,stripped],check=True)
    image=stripped.read_bytes()
    for path in (PROGRAM,ROOT/'cd/A.BIN'):
        if not path.is_file() or sha(path.read_bytes())!=sha(image):fail(f'{path.relative_to(ROOT)} is not the ELF with the zone overlays stripped; rebuild')
disc_note='disc image absent, disc check skipped'
if DISC.is_file():
    disc=DISC.read_bytes()
    for z,data in report:
        for chunk in (data[:2048],data[(len(data)-1)//2048*2048:]):
            if chunk and disc.find(chunk)<0:fail(f'dist disc image lacks ZTR{z[1:]}.BIN data; rebuild the image')
    disc_note='each on the disc image'
print(f'PASS: zone tables: {len(report)} overlays equal cd/ZTR*.BIN ('+', '.join(f'{z} {len(d)} B' for z,d in report)+
      f'), {disc_note}; A.BIN is the stripped program; range {start:#x}..{end:#x}; heap margin {margin} B (title TLSF class {terms[5]} B)')
