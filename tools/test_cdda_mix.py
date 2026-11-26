#!/usr/bin/env python3
"""Compare actual CDDA programs in the pinned SCSP interpreter.

Checks both channel polarities, all TEMP ring positions, fade/zero/reset and
unchanged law/MEMS/EFREG2. The actual installer mapping supplies the program.
This host proof does not grant console acceptance.
"""
from pathlib import Path
import hashlib, json, subprocess
root=Path(__file__).resolve().parents[1];out=root/'build/cdda-mix';out.mkdir(exist_ok=True);src=(root/'src/cdda_provider/cdda_envelope_shadow.c').read_text()
chunk=src[src.index('enum { MIX_BEGIN'):src.index('static void write_target')]
s='''#include "mednafen/mednafen.h"
#include "mednafen/ss/ss.h"
#include "mednafen/ss/scsp.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
bool setting_jit_scsp=false;
static INLINE void SCSP_SoundIntChanged(unsigned l){(void)l;}
static INLINE void SCSP_MainIntChanged(bool s){(void)s;}
#include "mednafen/ss/scsp.inc"
int MDFNSS_StateAction(void*sm,int l,int d,SFORMAT*sf,const char*n,bool o){(void)sm;(void)l;(void)d;(void)sf;(void)n;(void)o;return 0;}
#include "src/cdda_provider/envelope_words.h"
'''+chunk+'''
static uint64_t packed(unsigned i,int mix){uint64_t v=0;for(unsigned j=0;j<4;j++)v=(v<<16)|(mix?program_word(i,j):scd_env_program[i][j]);return v;}
static void init(SS_SCSP*z,int mix){
 memset(z,0,sizeof(*z));
 for(unsigned i=0;i<128;i++){z->DSP.MPROG[i]=packed(i,mix);z->DSP.TEMP[i]=784<<12;}
 for(unsigned i=0;i<sizeof(scd_env_data)/sizeof(scd_env_data[0]);i++)z->RAM[0xc400/2+i]=scd_env_data[i];
 for(unsigned i=0;i<sizeof(scd_env_coef)/sizeof(scd_env_coef[0]);i++)z->DSP.COEF[i]=scd_env_coef[i]>>3;
 if(mix)z->DSP.COEF[5]=MIX_COEF>>3;
 for(unsigned i=0;i<sizeof(scd_env_madrs)/sizeof(scd_env_madrs[0]);i++)z->DSP.MADRS[i]=scd_env_madrs[i];
 z->DSP.MEMS[0]=-0x800000;z->DSP.MEMS[1]=4096;z->DSP.MEMS[31]=784<<12;
 SS_SCSP_DecodeMPROG(z);
}
int main(void){
 SS_SCSP*a=calloc(1,sizeof(*a)),*b=calloc(1,sizeof(*b));assert(a&&b);
 init(a,0);init(b,1);uint32_t seed=123456789;unsigned max_error=0,checks=0,nonzero=0,witness_max=0; int low=0,high=0;
 for(unsigned n=0;n<44100;n++){
  seed=seed*1664525+1013904223;int16_t l=seed>>16;seed=seed*1664525+1013904223;int16_t r=seed>>16;
  if(n<128){l=n&1?-32768:32767;r=n&1?32767:-32768;}
  unsigned gain= n<10000?784:n<14000?(784u>(((n-10000)/147)*32)?784u-(((n-10000)/147)*32):0):n<18000?0:784;
  a->DSP.MEMS[31]=b->DSP.MEMS[31]=gain<<12;
  a->EXTS[0]=b->EXTS[0]=(uint16_t)l;a->EXTS[1]=b->EXTS[1]=(uint16_t)r;
  SS_SCSP_RunDSPInterpreter(a);SS_SCSP_RunDSPInterpreter(b);
  if(memcmp(a->DSP.MEMS,b->DSP.MEMS,sizeof(a->DSP.MEMS)) || a->DSP.EFREG[2]!=b->DSP.EFREG[2]){fprintf(stderr,"law/witness changed sample %u\\n",n);return 1;}
  if(a->DSP.EFREG[2]>witness_max)witness_max=a->DSP.EFREG[2];
  for(unsigned c=0;c<2;c++){
   int old=(int16_t)a->DSP.EFREG[c],actual=(int16_t)b->DSP.EFREG[c];
   if(old<low)low=old;if(old>high)high=old;if(old)nonzero++;
   int expect=(old*3276)>>12;unsigned error=abs(actual-expect);if(error>max_error)max_error=error;
   if(error>3){fprintf(stderr,"mix mismatch n=%u c=%u old=%d actual=%d expected=%d error=%u\\n",n,c,old,actual,expect,error);return 1;}
   checks++;
  }
 }
 assert(nonzero>40000 && low<-20000 && high>20000 && witness_max==784*16);
 printf("PASS: CDDA output mix %u channel samples; law/MEMS/EFREG2 unchanged; maximum rounding error %u\\n",checks,max_error);
 free(a);free(b);return 0;
}
'''
(out/'test.c').write_text(s)
base=root/'.deps/beetle-saturn';flags=['-O2','-DHAVE_MMAP','-D__LIBRETRO__','-DLSB_FIRST','-fno-strict-aliasing','-I'+str(root),'-I'+str(base),'-I'+str(base/'mednafen'),'-I'+str(base/'mednafen/include'),'-I'+str(base/'libretro-common/include')]
inputs=['src/cdda_provider/cdda_envelope_shadow.c','src/cdda_provider/envelope_words.h',
        '.deps/beetle-saturn/mednafen/ss/scsp.inc','.deps/beetle-saturn/mednafen/ss/scsp.h',
        '.deps/beetle-saturn/mednafen/mednafen.h','tools/test_cdda_mix.py']
report=dict(status='pending',hardware_tested=False,flags=flags,
            inputs={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in inputs})
def save(): (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
save()
try:
    with (out/'compile.log').open('w') as log:
        subprocess.run(['clang',*flags,str(out/'test.c'),'-o',str(out/'test')],stdout=log,stderr=log,check=True)
    r=subprocess.run([str(out/'test')],capture_output=True,text=True)
    (out/'results.log').write_text(r.stdout+r.stderr)
    assert r.returncode==0,r.stderr
    report.update(status='passed',channel_samples=88200,law_unchanged=True,output=r.stdout.strip())
    save();print(r.stdout,end='')
except BaseException as error:
    report.update(status='failed',error=repr(error));save();raise
