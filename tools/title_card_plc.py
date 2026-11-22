#!/usr/bin/env python3
"""Check src/title_card.c's PLC 2 batch table against the retail programs.

_Objects/Title Card/Main.asm: once the card slides out it queues PLC 2
(LoadPLC #2, the camera section 1 art) and sets scrollLock; ObjTitleCard_WaitPLC
keeps controls locked until plcBuffer is empty. ProcessPLCs (Level/Main.asm,
once per update) starts one queue entry; VInt_Level's DecompPLCSlow (once per
update, never in a lag V-INT) decodes 18 tiles while scrollLock is set and
pops the entry when it ends. The wait is therefore sum(ceil(tiles / 18))
level updates, independent of V-INT lag. Each R<zone><act><era> program's
PLCLists is found through LoadPLC's `lea PLCLists,a1`; tile counts are the
Nemesis headers of PLC 2's art.

usage: title_card_plc.py   (prints the table, exits 1 on a mismatch)
"""
import re
import struct
import sys

from convert_assets import ROOT
from extract_mmd import disc_files

ORIGIN = 0x200000
ROUNDS = (1, 3, 4, 5, 6, 7, 8)  # native zone index -> retail round (R2 is unused)


def batches(program):
    tables = {struct.unpack_from('>I', program, m.start() + 6)[0] - ORIGIN
              for m in re.finditer(bytes.fromhex('48e7006043f9'), program)}  # movem.l a1-a2,-(sp); lea PLCLists,a1
    assert len(tables) == 1, tables
    table = tables.pop()
    plc = table + struct.unpack_from('>H', program, table + 2 * 2)[0]
    total = 0
    for k in range(struct.unpack_from('>h', program, plc)[0] + 1):
        art = struct.unpack_from('>I', program, plc + 2 + 6 * k)[0] - ORIGIN
        total += -(-(struct.unpack_from('>H', program, art)[0] & 0x7fff) // 18)
    return total


def native_wait(zone, act, era):
    """Extra locked updates src/title_card.c adds for one program (native zone,
    0-based act, era 0-3): T - 2 from its plc2_batches table."""
    body = re.search(r'plc2_batches\[7\]\[3\]\[4\]=\{(.*?)\};', (ROOT / 'src/title_card.c').read_text(), re.S)[1]
    t = [int(v) for v in re.findall(r'\d+', body)][(zone * 3 + act) * 4 + era]
    return max(0, t - 2)


def main():
    files = disc_files((ROOT / 'build/retail/sonic.iso').read_bytes())
    want = [[[batches(files[f'R{r}{a + 1}{e}__.MMD']) if a < 2 or e in 'CD' else 0 for e in 'ABCD']
             for a in range(3)] for r in ROUNDS]
    source = (ROOT / 'src/title_card.c').read_text()
    body = re.search(r'plc2_batches\[7\]\[3\]\[4\]=\{(.*?)\};', source, re.S)[1]
    have = [int(v) for v in re.findall(r'\d+', body)]
    flat = [v for zone in want for act in zone for v in act]
    for zone, rows in zip(ROUNDS, want):
        print(f'R{zone}', ' '.join(','.join(map(str, act)) for act in rows))
    if have != flat:
        print('FAIL: src/title_card.c plc2_batches differs from the retail programs')
        return 1
    print('PASS: title card PLC 2 batches match all 70 retail programs')
    return 0


if __name__ == '__main__':
    sys.exit(main())
