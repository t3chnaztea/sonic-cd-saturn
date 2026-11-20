#!/usr/bin/env python3
"""Compare actor selection and hashes with original code, Classic and CD++."""
import argparse,hashlib,json,os,subprocess
from datetime import datetime
from pathlib import Path
import cdpp_fuzz as cf
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/ss-order-check'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument("--zone",choices=("ss","mm"),default="ss")
 args=parser.parse_args();zone=args.zone
 OUT.mkdir(parents=True,exist_ok=False)
 report={'status':'pending','passed':False,'cases':{},'zone':zone,'inputs':{},'compiler':subprocess.check_output(['clang','--version'],text=True).splitlines()[0]}
 def save():(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 save()
 try:
  reference=ROOT/'build/cdpp-reference-objects.c'
  original=subprocess.check_output(['git','show','d0f1c85:src/objects.c'],cwd=ROOT)
  assert hashlib.sha256(original).hexdigest()==sha(reference),'reference is not original main source'
  reference_boss=OUT/'reference-boss.c'
  reference_boss.write_bytes(subprocess.check_output(['git','show','d0f1c85:src/boss.c'],cwd=ROOT))
  source,native,original_names,extra=cf.HOSTS[zone]
  inputs=[ROOT/source,reference,reference_boss,Path(__file__).resolve(),ROOT/'tools/cdpp_fuzz.py',*[ROOT/s for s in native],ROOT/'src/player_plus.c',*[ROOT/f'build/probe-source/{n}.c' for n in cf.CORE+original_names]]
  inputs += [p for folder in ('src','assets/generated','build/probe-source') for p in (ROOT/folder).iterdir() if p.is_file() and p.suffix in ('.h','.H','.inc','.bin')]
  inputs += [ROOT/f'tests/routes/{"cdpp/completion" if flags else zone}/{zone}3{era}.txt' for flags in (0,31) for era in ('C','D')]
  report['inputs']={str(p.relative_to(ROOT)):sha(p) for p in sorted(set(inputs))};save()
  for flags in (0,31):
   for variant in ('reference','optimized'):
    sources=[source,*[('build/cdpp-reference-objects.c' if p=='src/objects.c' and variant=='reference' else str(reference_boss) if p=='src/boss.c' and variant=='reference' else p) for p in native],'src/player_plus.c',*[f'build/probe-source/{n}.c' for n in cf.CORE+original_names]]
    with (OUT/f'compile-{variant}-{flags}.log').open('w') as log:
     subprocess.run(['nice','-n','20','clang','-std=gnu11','-O1','-fsigned-char','-fwrapv','-fno-strict-aliasing','-Wno-parentheses','-Wno-unused-value','-fsanitize=address,undefined','-fno-sanitize-recover=all','-Isrc','-Iassets/generated','-Ibuild/probe-source','-DR1','-DR11A',f'-DSCD_PLUS_HOST_FLAGS={flags}',*extra,*sources,'-o',str(OUT/f'{variant}-{flags}')],cwd=ROOT,stdout=log,stderr=log,check=True)
   for era in ('C','D'):
    name=f'{flags}-{era}';report['cases'][name]={'status':'pending'};save()
    route=ROOT/f'tests/routes/{"cdpp/completion" if flags else zone}/{zone}3{era}.txt';results={}
    for variant in ('reference','optimized'):
     env={k:v for k,v in os.environ.items() if not k.startswith(('SCD_','QQ_','PPZ_','CC_','TT_'))};env.update(QQ_ROUTE_TRACE='1',ASAN_OPTIONS='detect_leaks=0')
     if variant=='optimized':env['MM_ORDER_CHECK']='1'
     rows=OUT/f'{variant}-{name}.rows'
     with (OUT/f'{variant}-{name}.log').open('w') as log:
      subprocess.run([str(OUT/f'{variant}-{flags}'),'replay',f'2:{era}',str(route),'46000',str(rows)],cwd=ROOT,env=env,stdout=log,stderr=log,check=True,timeout=600)
     log_text=(OUT/f'{variant}-{name}.log').read_text()
     assert 'Tally complete:' in log_text,('route did not finish',variant,name)
     if zone=='ss':assert 'SS race complete: seen=1 race=1 result=1 escaped=1 stationary=1' in log_text,('race incomplete',variant,name)
     else:assert 'MM ending complete: seen=1 hits=4 escaped=1 amy=1 game_end=1' in log_text,('ending incomplete',variant,name)
     results[variant]=rows.read_bytes()
    assert results['reference']==results['optimized'],('trace mismatch',name)
    report['cases'][name]={'status':'passed','states':len(results['reference'].splitlines()),'trace_sha256':hashlib.sha256(results['reference']).hexdigest()};save()
  assert all(sha(ROOT/p)==v for p,v in report['inputs'].items()),'inputs changed'
  report.update(status='passed',passed=True);save()
 except BaseException as error:
  status='interrupted' if isinstance(error,KeyboardInterrupt) else 'failed'
  for case in report['cases'].values():
   if case['status']=='pending':case['status']=status
  report.update(status=status,error=repr(error));save();raise
 print('PASS: '+zone.upper()+'3 cache and hashes match every original-code state in Classic/CD++ C/D; '+str(OUT/'report.json'),flush=True)
if __name__=='__main__':main()
