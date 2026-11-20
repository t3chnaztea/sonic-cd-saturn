#!/usr/bin/env python3
"""Special stage order (curSpecStage) and ending choice against the original.

Reference: Special Stage/Sub.asm .StageBeaten/.Exit (next stage search),
Special Stage/Main.asm Results (curSpecStage = specStageID), IPX.asm NewGame
(curSpecStage = 0) and GameDone (good ending on all good futures or all stones).
"""
import ctypes as C,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def sub_exit(stage,stones,won):
    """Sub.asm .StageBeaten (bset specStageID) then .Exit's .GetNextStage loop."""
    if won:stones|=1<<stage
    d0=stage
    while True:
        d0+=1
        if d0>=7:d0=0
        if stones==0x7f or not stones>>d0&1:return d0,stones

def game_done(good_futures,stones):
    """IPX.asm GameDone: cmpi.b #%01111111 on gameGoodFutures, then gameTimeStones."""
    return good_futures==0x7f or stones==0x7f

def main():
    (ROOT/'build').mkdir(exist_ok=True)
    subprocess.run(['clang','-std=c11','-O2','-Wall','-Wextra','-Werror','-Isrc','-dynamiclib' if sys.platform=='darwin' else '-shared','-fPIC','tools/special_progress_shim.c','-o','build/special-progress.dylib'],cwd=ROOT,check=True)
    n=C.CDLL(str(ROOT/'build/special-progress.dylib'))
    n.stage_after.argtypes=[C.c_uint,C.c_uint8];n.stage_after.restype=C.c_uint8
    n.stage_exit.argtypes=[C.c_uint,C.POINTER(C.c_uint8),C.c_int];n.stage_exit.restype=C.c_uint8
    n.stage_from_stones.argtypes=[C.c_uint8];n.stage_from_stones.restype=C.c_uint8
    n.ending_good.argtypes=[C.c_uint8,C.c_uint8];n.ending_good.restype=C.c_int
    cases=0
    for stage in range(7):
        for stones in range(128):
            for won in (0,1):
                s=C.c_uint8(stones);got=n.stage_exit(stage,C.byref(s),won)
                assert (got,s.value)==sub_exit(stage,stones,won),(stage,stones,won,got,s.value)
                cases+=1
            assert n.stage_after(stage,stones)==sub_exit(stage,stones,0)[0]
    # Playthroughs from NewGame (curSpecStage 0): every win/lose sequence of up to
    # 10 big rings. The stage entered is never one whose stone is held (until all 7).
    for pattern in range(1<<10):
        cur,stones=0,0
        for ring in range(10):
            assert stones==0x7f or not stones>>cur&1,(pattern,ring,cur,stones)
            s=C.c_uint8(stones);nxt=n.stage_exit(cur,C.byref(s),pattern>>ring&1)
            cur,stones=sub_exit(cur,stones,pattern>>ring&1);assert (nxt,s.value)==(cur,stones)
    # All-wins order is 1..7; alternating fails visit every missing stage.
    cur,stones,order=0,0,[]
    for _ in range(7):order.append(cur+1);cur,stones=sub_exit(cur,stones,1)
    assert order==[1,2,3,4,5,6,7] and stones==0x7f and cur==0
    # v1 save upgrade: a stage whose stone is not held (any stage once all are held).
    for stones in range(128):
        got=n.stage_from_stones(stones);assert got<7 and (stones==0x7f or not stones>>got&1),(stones,got)
    assert [n.stage_from_stones(v) for v in (0,1,3,0x7f,0x40,0x3f)]==[0,1,2,0,0,6]
    for gf in range(256):
        for stones in range(256):
            assert bool(n.ending_good(gf,stones))==game_done(gf,stones),(gf,stones)
    print(f'PASS: special progress: {cases} Sub.asm exits, 1024 ring sequences, v1 stage upgrade, 65536 GameDone endings')

if __name__=='__main__':main()
