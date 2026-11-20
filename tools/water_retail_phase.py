#!/usr/bin/env python3
"""Retail Tidal Tempest water sway phase (QA oracle, private disc).

Boots a TT program in the Sega CD core (stub of tools/water_retail.py), dumps work
RAM per level update, finds the byte that advances by 2 per update (the sway
angle, 0xff1955 in R41A) and prints its value at Sonic's first falling update.
R41A/R41B: 8 (the angle starts 3 updates before Sonic moves). src/water.c
water_reset reproduces this. Usage: python3 tools/water_retail_phase.py R41A
"""
import sys,struct,json
sys.path.insert(0,'tools')
import water_retail as wr, special_retail as sr
from extract_mmd import disc_files
name=sys.argv[1]
# reuse capture setup by monkeypatching: copy of capture loop, dumping RAM
main_vars,_,_,commands=sr.layout()
engine,_=sr.rs_symbols((sr.SRC/'Level/_Definitions.inc').read_text(),{'WORKRAM':0xff0000},0xffffff)
ipx=(sr.RETAIL/'IPX___.MMD').read_bytes();origin=struct.unpack_from('>I',ipx,2)[0];code=ipx[0x100:0x1100]
run_mmd,_=sr.find(code,'2f0833c000a12010',origin)
bram,_=sr.find(code,'303c(....)6100(....)4a00670808f90000%08x'%main_vars['saveDisabled'],origin)
stub_at,_=sr.find(code,'13fc000000a1201313fc000000a1201a08f9000000a1201b70..6100....4e75',origin)
program=disc_files((sr.RETAIL/'sonic.iso').read_bytes())[name+'__.MMD']
vint=struct.unpack_from('>I',program,16)[0]
act=int(name[2])-1;era,zt=wr.ERAS[name[3]]
stub=struct.pack('>HHI',0x13fc,3,main_vars['lives'])+struct.pack('>HHI',0x13fc,zt,main_vars['timeZone'])+struct.pack('>HHI',0x13fc,1 if era==2 else 0,main_vars['goodFuture'])+struct.pack('>HHI',0x33fc,2<<8|act,main_vars['zoneAct'])+struct.pack('>HII',0x23fc,5000,main_vars['nextLifeScore'])+struct.pack('>HHHIH',0x303c,commands['SCMD_'+name],0x4eb9,run_mmd,0x60fe)
patches=[(bram,code[bram-origin:bram-origin+8],struct.pack('>HIH',0x4ef9,stub_at,0x4e71)),(stub_at,code[stub_at-origin:stub_at-origin+len(stub)],stub)]
core=sr.Core();patched=False;dumps=[];info=[]
word=lambda a:struct.unpack('>h',core.work_read(a,2))[0]
for f in range(4000):
    core.pad=0;core.run();core.host.chunks.clear()
    if not patched and all(core.work_read(a,len(o))==o for a,o,_ in patches):
        for a,_,n in patches:core.work_write(a,n)
        patched=True
    if not patched or core.work_read(0xfffd08,4)!=struct.pack('>I',vint):continue
    dumps.append(core.work_read(0xff0000,0x10000))
    card=core.work_read(engine['objTtlCardSlot'],64)
    info.append((word(engine['waterHeight'])-word(engine['waterHeight2']),core.work_read(engine['ctrlLocked'],1)[0],card[0]))
    if len(dumps)>=400:break
# candidate addresses: +2 per frame over frames 300..399
cands=[a for a in range(0x10000) if all((dumps[i+1][a]-dumps[i][a])&255==2 for i in range(300,399))]
print('cands',[hex(0xff0000+a) for a in cands])
for a in cands:
    seq=[d[a] for d in dumps]
    first=next(i for i in range(len(seq)-1) if all((seq[j+1]-seq[j])&255==2 for j in range(i,399)))
    print(hex(0xff0000+a),'steady +2 from level frame',first,'value there',seq[first],'first values',seq[:8])
lock=[i for i,x in enumerate(info) if x[1]==0 and x[2]==0][:1]
print('released at level frame',lock)
o=engine['objPlayerSlot']-0xff0000
first=next(i for i,d in enumerate(dumps) if struct.unpack('>h',d[o+18:o+20])[0]!=0)
a=cands[0] if cands else None
print(name,'first yspeed frame',first,'yspeed',struct.unpack('>h',dumps[first][o+18:o+20])[0],'angle then',dumps[first][a] if a is not None else None,'angle addr',hex(0xff0000+a) if a is not None else None, 'angle start frame', next(i for i in range(len(dumps)) if dumps[i][a]))
