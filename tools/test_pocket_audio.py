#!/usr/bin/env python3
"""Check compiled native request routing against the pocket's retail FM channels.

The real audio.c request function is compiled with recorded command-buffer
writes. Saturn driver playback and sound RAM are covered by target audio QA.
"""
import ctypes as C
import hashlib
import json
import subprocess
from pathlib import Path

from convert_assets import ROOT
from cc_pocket_source import verify


def main():
    proof=verify()['audio']
    source=(ROOT/'src/audio.c').read_text()
    start=source.index('void scd_audio_request(')
    function=source[start:source.index('\n}',start)+2]
    out=ROOT/'build/cc1/pocket/audio';out.mkdir(parents=True,exist_ok=True)
    wrapper='''#include "feedback.inc"
enum { PCM_FWD_LOOP=1, PCM_SEMI=2 };
typedef struct { unsigned sh2_permit; } command;
static command controls[EFFECT_COUNT+SFX_BANK_EFFECTS];
/* Collision Chaos: its effect bank (SFXZ1.PCM) is loaded. */
static int sfx_bank=1;
static struct { command *pcmCtrl; } state={controls},*m68k_com=&state;
static int initialized=1,copy_ok=1,is_paused;
static unsigned scd_audio_test_mute;
static unsigned plays;
static void ponesound_pcm_play(short n,char type,char volume){(void)type;(void)volume;controls[n].sh2_permit=1;plays++;}
void reset(void){for(unsigned i=0;i<EFFECT_COUNT+SFX_BANK_EFFECTS;i++)controls[i].sh2_permit=0;plays=0;}
unsigned permitted(short request){for(unsigned i=0;i<sfx_bank_counts[sfx_bank];i++)if(sfx_bank_effects[sfx_bank][i].request==request)return controls[EFFECT_COUNT+i].sh2_permit;
    for(unsigned i=0;i<EFFECT_COUNT;i++)if(effect_requests[i]==request)return controls[i].sh2_permit;return 0;}
unsigned played(void){return plays;}
'''+function
    (out/'native.c').write_text(wrapper)
    subprocess.run(['clang','-std=c11','-O2','-Wall','-Wextra','-Werror','-shared',
                    '-Iassets/generated',str(out/'native.c'),'-o',str(out/'native.dylib')],cwd=ROOT,check=True)
    native=C.CDLL(str(out/'native.dylib'));native.scd_audio_request.argtypes=[C.c_short];native.permitted.argtypes=[C.c_short]
    effects=json.loads((ROOT/'build/feedback-source.json').read_text())['samples']
    capture,release=proof['capture_request'],proof['release_request']
    cases=0
    for effect in effects:
        request=effect['id']
        # Only effects Collision Chaos can play: resident or in its bank.
        if request in (capture,release) or not {'SFX.PCM','SFXZ1.PCM'}&set(effect['banks']):continue
        native.reset()
        for n in (capture,request):native.scd_audio_request(n)
        assert native.permitted(capture) and native.permitted(request)
        native.scd_audio_request(release)
        assert not native.permitted(capture) and native.permitted(release) and native.permitted(request)
        assert native.played()==3;cases+=1
    inputs=['src/audio.c','tools/test_pocket_audio.py','tools/cc_pocket_source.py',
            'build/cc1/pocket/retail.json','assets/generated/feedback.inc','build/feedback-source.json']
    result=dict(passed=True,cases=cases,proof=proof,
        inputs={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in inputs},
        limits='Actual compiled SH-side request routine with a command-buffer recorder; excludes PCM playback, other original FM channel conflicts and driver scheduling latency.')
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Pocket release replaces capture and preserves',cases,'other effect requests')


if __name__=='__main__':main()
