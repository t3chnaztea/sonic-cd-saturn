#!/usr/bin/env python3
"""R63C/D linked boss entry fixture; full fight and console remain separate."""
import hashlib
import json
import os
import re
import struct
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/ww3-boss-entry'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def plc_art(name):
    import sys
    sys.path.insert(0,str(ROOT/'tools'))
    import zone_art_lz
    pack=(ROOT/'assets/generated/zone-art-63.bin').read_bytes()
    era='ABCD'.index(name[-1]);at=struct.unpack_from('>I',pack,4+era*4)[0]
    count,raw_size,packed_size=struct.unpack_from('>III',pack,at)
    rec_at=at+12
    raw=bytearray(zone_art_lz.unpack(pack[rec_at+count*48:rec_at+count*48+packed_size],raw_size//2))
    entry_records=[struct.unpack_from('>HHIHH',pack,rec_at+i*48) for i in range(count)
                   if 496<=struct.unpack_from('>H',pack,rec_at+i*48)[0]<=499]
    assert {r[0] for r in entry_records}=={496,497,498,499} and len(entry_records)>=22
    ranges=sorted({(offset&65535,width*height//2) for kind,frame,offset,width,height in entry_records})
    assert len(ranges)==len(entry_records) and len({x for x,_ in ranges})==len(ranges)
    patch=rec_at+count*48+packed_size
    assert pack[patch:patch+4]==b'W6PT'
    end_age=struct.unpack_from('>H',pack,patch+4)[0]
    ends=struct.unpack_from(f'>{end_age+1}I',pack,patch+8)
    body=patch+8+4*(end_age+1)
    hashes={}
    for age in range(1,end_age+1):
        pos,stop=body+ends[age-1],body+ends[age]
        while pos<stop:
            word,n=struct.unpack_from('>HH',pack,pos);pos+=4
            raw[word*2:(word+n)*2]=pack[pos:pos+n*2];pos+=n*2
        assert pos==stop
        value=14695981039346656037
        for offset,bytes_ in ranges:
            for b in raw[offset:offset+bytes_]:value=((value^b)*1099511628211)&((1<<64)-1)
        hashes[age]=f'{value:016x}'
    return ','.join(f'{offset:x}:{bytes_:x}' for offset,bytes_ in ranges),hashes

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    inputs=['tools/test_ww3_boss_entry_emulator.py','tools/emulator_test.c','src/boss.c',
            'src/boss_r6.c','build/probe-source/boss_6.c','dist/sonic-cd-saturn-prototype.bin',
            'src/zone_object_view.inc','tools/zone_object_assets.py','assets/generated/zone-art-63.bin',
            '.deps/beetle-saturn/mednafen_saturn_libretro.dylib']
    report={'status':'pending','passed':False,'inputs':{p:digest(ROOT/p) for p in inputs},'runs':{}}
    path=OUT/'report.json';path.write_text(json.dumps(report,indent=2)+'\n')
    exe=OUT/'emulator'
    subprocess.run(['clang','-std=gnu11','-Wall','-Wextra','-Werror','-I.deps/beetle-saturn/libretro-common/include',
                    'tools/emulator_test.c','-o',exe],cwd=ROOT,check=True)
    listing=subprocess.check_output([ROOT/'.toolchain/bin/sh-elf-nm',ROOT/'build/saturn/sonic-cd-saturn-prototype.elf'],text=True)
    # LTO may privatize a static as name.lto_priv.N depending on the partitioning.
    symbols={re.sub(r'\.lto_priv\.\d+$','',r.split()[2]):r.split()[0] for r in listing.splitlines() if len(r.split())==3}
    age_symbols=[v for k,v in symbols.items() if k.startswith('_boss6_art_age')]
    assert len(age_symbols)==1 and '_boss6_art_applied_age' in symbols
    for era in 'CD':
        bitmap_ranges,expected=plc_art('R63'+era)
        run=OUT/era;run.mkdir(exist_ok=True)
        env={k:v for k,v in os.environ.items() if not k.startswith('SCD_')}
        env.update(SCD_ZONE='4',SCD_ZONE_ACT='2',SCD_ZONE_ERA=str('ABCD'.index(era)),
                   SCD_WORLD_MAILBOX=symbols['_scd_world_mailbox'],
                   SCD_WW3_BOSS_ACTWK=symbols['_actwk'],SCD_WW3_BOSS_FLAG=symbols['_bossflag'],
                   SCD_WW3_PLC_AGE=age_symbols[0],SCD_WW3_PLC_APPLIED=symbols['_boss6_art_applied_age'],
                   SCD_WW3_PLC_BITMAPS=bitmap_ranges)
        command=[exe,ROOT/'.deps/beetle-saturn/mednafen_saturn_libretro.dylib',
                 ROOT/'dist/sonic-cd-saturn-prototype.cue',ROOT/'assets/private',run,
                 symbols['_scd_trace_mailbox'],symbols['_scd_audio_mailbox'],'zones']
        with (run/'results.log').open('w') as out,(run/'core.log').open('w') as err:
            result=subprocess.run(list(map(str,command)),cwd=ROOT,env=env,stdout=out,stderr=err,timeout=240)
        log=(run/'results.log').read_text();match=re.search(r'^WW3 boss probe passed: (.*)$',log,re.M)
        observed={int(age):digest for age,digest in re.findall(r'^WW3 PLC: age=(\d+) hash=([0-9a-f]{16})$',log,re.M)}
        good=result.returncode==0 and bool(match) and observed==expected
        report['runs'][era]={'passed':good,'exit_code':result.returncode,'summary':match[1] if match else None,
                             'plc_ages':len(observed),'plc_match':observed==expected,
                             'log_sha256':digest(run/'results.log'),'core_tail':(run/'core.log').read_text()[-400:]}
        path.write_text(json.dumps(report,indent=2)+'\n')
        print(f'R63{era}: '+(f'PASS {match[1]} plc_ages={len(observed)}' if good else
                           f'FAIL observed={len(observed)}/{len(expected)} '+report['runs'][era]['core_tail']),flush=True)
        if not good:report.update(status='failed',passed=False);path.write_text(json.dumps(report,indent=2)+'\n');raise SystemExit(1)
    report.update(status='passed',passed=True);path.write_text(json.dumps(report,indent=2)+'\n')
    print('PASS: WW3 boss entry emulator, both futures')

if __name__=='__main__':main()
