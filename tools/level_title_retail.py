#!/usr/bin/env python3
"""Record the real PPZ entry/card/PLC/HUD sequence in the Sega CD core.

Like title_retail.py, bypass the core's failing Backup RAM initialization using
an explicit IPX RAM stub. The stub seeds fresh-entry globals and calls RunMMD
with the requested PPZ file. The level program, interrupts, decompression and
object scheduler are untouched. This is an entry fixture, not a playthrough
from the title screen or an act-completion transition.
"""
import argparse
import hashlib
import json
import struct

import special_retail as sr
from extract_mmd import disc_files


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--act',type=int,choices=range(3),default=0)
    parser.add_argument('--label',default='entry')
    args=parser.parse_args()
    assert args.label.replace('-','').replace('_','').isalnum()
    out=sr.ROOT/'build/title-card-clock'/f'{args.label}-act{args.act+1}'
    out.mkdir(parents=True,exist_ok=False)
    main_vars,_,_,commands=sr.layout()
    engine,_=sr.rs_symbols((sr.SRC/'Level/_Definitions.inc').read_text(),{'WORKRAM':0xff0000},0xffffff)
    ipx=(sr.RETAIL/'IPX___.MMD').read_bytes()
    origin=struct.unpack_from('>I',ipx,2)[0];code=ipx[0x100:0x1100]
    run_mmd,_=sr.find(code,'2f0833c000a12010',origin)
    bram,(command,displacement)=sr.find(code,'303c(....)6100(....)4a00670808f90000%08x'%main_vars['saveDisabled'],origin)
    assert command==commands['SCMD_BURAMINIT']
    assert bram+6+(displacement-65536 if displacement&0x8000 else displacement)==run_mmd
    stub_at,_=sr.find(code,'13fc000000a1201313fc000000a1201a08f9000000a1201b70..6100....4e75',origin)
    file_name=['R11A__.MMD','R12A__.MMD','R13D__.MMD'][args.act]
    command=commands[['SCMD_R11A','SCMD_R12A','SCMD_R13D'][args.act]]
    program=disc_files((sr.RETAIL/'sonic.iso').read_bytes())[file_name]
    # Level programs run in Word RAM; RunMMD installs the MMD header vector.
    vinterrupt=struct.unpack_from('>I',program,16)[0]
    assert 0x200100<=vinterrupt<0x240000
    stub=struct.pack('>HHI',0x13fc,3,main_vars['lives'])
    stub+=struct.pack('>HHI',0x13fc,1 if args.act<2 else 2,main_vars['timeZone'])
    stub+=struct.pack('>HHI',0x33fc,args.act,main_vars['zoneAct'])
    stub+=struct.pack('>HII',0x23fc,5000,main_vars['nextLifeScore'])
    stub+=struct.pack('>HHHIH',0x303c,command,0x4eb9,run_mmd,0x60fe)
    assert len(stub)<=64
    patches=[(bram,code[bram-origin:bram-origin+8],struct.pack('>HIH',0x4ef9,stub_at,0x4e71)),
             (stub_at,code[stub_at-origin:stub_at-origin+len(stub)],stub)]
    core=sr.Core();patched=False;rows=[];seen_card=False;finished=0
    symbols=main_vars|engine
    def byte(name):return core.work_read(symbols[name],1)[0]
    def word(name):return struct.unpack('>H',core.work_read(symbols[name],2))[0]
    for frame in range(6000):
        core.pad=0;core.run()
        # The core audio callback collects PCM; no audio artifact is required.
        core.host.chunks.clear()
        if not patched and all(core.work_read(at,len(old))==old for at,old,_ in patches):
            for at,_,new in patches:core.work_write(at,new)
            patched=True
        if not patched or core.work_read(0xfffd08,4)!=struct.pack('>I',vinterrupt):continue
        card=core.work_read(engine['objTtlCardSlot'],64)
        clock=core.work_read(main_vars['time'],4)
        row=dict(frame=frame,level_frames=word('levelFrames'),vint_routine=byte('vintRoutine'),
            locked=byte('ctrlLocked'),elapsed=clock[1]*3600+clock[2]*60+clock[3],
            card=list(card),plc=core.work_read(engine['plcBuffer'],0x60).hex(),
            sonic=core.work_read(engine['objPlayerSlot'],64).hex(),pc=core.lib.m68k_get_reg(16))
        rows.append(row)
        if card[0]==0x3c:seen_card=True
        if seen_card and not row['locked'] and not card[0]:finished+=1
        if finished in [1,2,30] and core.frame:sr.png(out/f'released-{finished}.png',core.frame)
        if finished>=120:break
    raw=out/'timeline.json';raw.write_text(json.dumps(rows,separators=(',',':'))+'\n')
    assert finished>=120,('entry did not finish',len(rows),rows[-1] if rows else None)
    locked=[r for r in rows if r['locked']]
    assert locked and all(not r['elapsed'] for r in locked)
    after=[r for r in rows if r['frame']>locked[-1]['frame']]
    assert after and any(r['elapsed'] for r in after)
    milestones=dict(first_card_frame=next(r['frame'] for r in rows if r['card'][0]==0x3c),
        first_parent_routine2=next(r['level_frames'] for r in rows if r['card'][36]==2),
        first_plc_wait=next((r['level_frames'] for r in rows if r['card'][36]==10),None),
        last_locked_update=locked[-1]['level_frames'],first_unlocked_update=after[0]['level_frames'],
        first_clock_update=next(r['level_frames'] for r in after if r['elapsed']))
    sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    report=dict(passed=True,scope='retail_entry_fixture',act=args.act,file=file_name,
        limits='Fresh-entry globals and explicit IPX RAM boot stub; idle pad, no title/menu/preceding-act progression. Full retail level/PLC execution, not a native or physical-hardware comparison.',
        milestones=milestones,frames=len(rows),patches=[dict(address=at,old=old.hex(),new=new.hex()) for at,old,new in patches],
        program_sha256=hashlib.sha256(program).hexdigest(),ipx_sha256=hashlib.sha256(ipx).hexdigest(),
        core_sha256=sha(sr.ROOT/'.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib'),
        source_sha256={name:sha(sr.ROOT/name) for name in ['tools/level_title_retail.py','tools/special_retail.py','tools/retail_capture.py',
            '.deps/scddisasm/src/Level/_Definitions.inc','.deps/scddisasm/src/_Include/Main CPU Variables.inc',
            '.deps/scddisasm/src/CD Initial Program/IPX.asm','.deps/scddisasm/src/Level/Main.asm']},
        evidence_sha256={str(p.relative_to(sr.ROOT)):sha(p) for p in out.iterdir() if p.is_file()})
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(milestones,indent=2))


if __name__=='__main__':main()
