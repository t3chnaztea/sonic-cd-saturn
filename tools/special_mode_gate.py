#!/usr/bin/env python3
"""Special-stage release gate cases for the IPX.asm mode entries (lane ss-modes).

One case per run: python3 tools/special_mode_gate.py <case> --output <folder>.
Each case records the retail run (tools/special_retail.py), checks the native
program against it per V-INT on the host (tools/test_special_game.py), then
boots the built disc without input in the emulator, reaches the mode from the
title (attract demos at the time-out, Stage 8 through the sound test 07/07/07,
Time Attack through the Y debug entry) and checks every V-INT
and picture against retail (tools/check_special_game.py). Writes
<folder>/report.json with passed and the tested BIN's disc_sha256; exits 0
only on a pass.
"""
import hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
# case: (routes run in the emulator, route this case checks, title hold, frame budget,
#        planner (stage, flags, name) for a planned route, extra host requirement)
CASES={
    'SP8-timeout':(['idle-ss8'],'idle-ss8','st',24000,None,None),
    'SP8-hazard':(['hazard-ss8'],'hazard-ss8','st',24000,None,'hazard'),
    'SP8-win':(['swin-ss8'],'swin-ss8','st',24000,None,'win'),
    # The won Stage 8 runs the credits (SPEEND.MMD); Start returns to the title.
    'SP8-credits':(['swin-ss8'],'swin-ss8','st',24000,None,'credits'),
    'DEMO-SS1':(['demo-ss1'],'demo-ss1',None,24000,None,None),
    'DEMO-SS6':(['demo-ss1','demo-ss6'],'demo-ss6',None,40000,None,None),
    'TA-SS1-win':(['tawin-ss1'],'tawin-ss1','y',24000,(1,2,'win-route-ta'),'win'),
    'TA-SS1-exit':(['taexit-ss1'],'taexit-ss1','y',24000,None,'aborted'),
}

def run(command,log,env=None):
    with open(log,'w') as out:return subprocess.run(command,cwd=ROOT,stdout=out,stderr=subprocess.STDOUT,env=env).returncode

def symbol(name):
    """Address of a symbol; LTO may rename a static to <name>.lto_priv.N."""
    out=subprocess.check_output([str(ROOT/'.toolchain/bin/sh-elf-nm'),str(ROOT/'build/saturn/sonic-cd-saturn-prototype.elf')],text=True)
    return next(line.split()[0] for line in out.splitlines() if line.split()[-1]==name or line.split()[-1].startswith(name+'.lto_priv.'))

def main():
    case=sys.argv[1];out=Path(sys.argv[sys.argv.index('--output')+1]);out.mkdir(parents=True,exist_ok=True)
    routes,route,hold,frames,plan,need=CASES[case]
    disc=ROOT/'dist/sonic-cd-saturn-prototype.bin'
    report={'case':case,'route':route,'disc_sha256':hashlib.sha256(disc.read_bytes()).hexdigest(),'passed':False,'failures':[]}
    def finish():
        report['passed']=not report['failures']
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(('PASS' if report['passed'] else 'FAIL')+f': {case} {out/"report.json"}')
        raise SystemExit(0 if report['passed'] else 1)
    if plan and not (ROOT/f'build/special-retail/{plan[2]}.json').exists():
        if run(['python3','tools/special_route.py',str(plan[0]),str(plan[1]),plan[2]],out/'plan.log'):
            report['failures'].append(f'no stored win route: tools/special_route.py {plan[0]} {plan[1]} {plan[2]} did not win (see plan.log)');finish()
    for name in routes:
        if run(['python3','tools/special_retail.py',name],out/f'retail-{name}.log'):report['failures'].append(f'retail run {name} failed');finish()
    retail=[json.loads(line) for line in (ROOT/f'build/special-retail/{route}.jsonl').open()]
    report['retail']={'vints':retail[-1]['v'],'lives':retail[-1]['lives'],'lost':retail[-1]['lost']}
    # Host: the native program per V-INT against retail.
    import test_special_game
    try:host=test_special_game.run(route)
    except AssertionError as error:report['failures'].append(f'host: {error}'[:400]);finish()
    report['host']=host
    if need=='hazard' and not host['hazard_updates']:report['failures'].append('no hazard contact in the route')
    if need in ('win','credits') and host['lost']:report['failures'].append(f'route left {host["lost"]} UFOs')
    if need=='aborted' and not host['lost']:report['failures'].append('time attack exit left no UFOs')
    # Saturn: the built disc from the title time-out.
    subprocess.run(['clang','-std=gnu11','-Wall','-Wextra','-Werror','-I.deps/beetle-saturn/libretro-common/include','tools/emulator_test.c','-o','build/special_game_test'],cwd=ROOT,check=True)
    env=dict(os.environ,SCD_SPECIAL_GAME=symbol('_scd_special_game_mailbox'),SCD_SPECIAL_ROUTES=str(ROOT/'build/special-retail'),
        **({'SCD_SPECIAL_AFTER':'1200,500'} if need=='credits' else {}),
        SCD_SPECIAL_ATTRACT=hold or '1',SCD_SPECIAL_ROUTE_NAMES=','.join(routes),SCD_SPECIAL_FRAMES=str(frames),
        # special_game_mode, special_game_mode_stage, special_main_pack (stage at +96) once each run starts.
        SCD_SPECIAL_READBACK=','.join([symbol('_special_game_mode'),symbol('_special_game_mode_stage'),'%x'%(int(symbol('_special_main_pack'),16)+96)]))
    log=out/'results.log'
    with open(log,'w') as stdout,open(out/'core.log','w') as stderr:
        subprocess.run(['build/special_game_test',str(ROOT/'.deps/beetle-saturn/mednafen_saturn_libretro.dylib'),str(ROOT/'dist/sonic-cd-saturn-prototype.cue'),
            str(ROOT/'assets/private'),str(out),symbol('_scd_trace_mailbox'),symbol('_scd_audio_mailbox'),'specialgame'],cwd=ROOT,env=env,stdout=stdout,stderr=stderr)
    # The run that started is the case's mode and stage (RAM, after the program wrote it).
    import re,special_retail
    flags,_=special_retail.route_mode(route);stage=special_retail.route_spec(route)[2]
    seen=[list(map(int,re.findall(r'=(\d+)',line))) for line in log.read_text().splitlines() if line.startswith('Special mode readback: ')]
    report['readback']=seen
    index=routes.index(route)
    if len(seen)<=index:report['failures'].append('the mode run never started')
    else:
        mode,mode_stage,pack=seen[index];pack>>=16
        if (mode,mode_stage,pack)!=(flags,stage,stage):report['failures'].append(f'ran flags {mode} stage {mode_stage} pack SSM{pack}, expected flags {flags} stage {stage}')
    check=run(['python3','tools/check_special_game.py','--modes',','.join(routes),'--log',str(log),'--report',str(out/'saturn.json')],out/'check.log')
    saturn=json.loads((out/'saturn.json').read_text()) if (out/'saturn.json').exists() else {}
    report['saturn']={'routes':saturn.get('routes',{}),'failures':saturn.get('failures',[])}
    # Failures of the other routes run on the way (the earlier attract demo) do not count here.
    mine=[f for f in saturn.get('failures',['no Saturn report']) if f.startswith(route+':') or not any(f.startswith(r+':') for r in routes)]
    if check and mine:report['failures']+=[f'saturn: {f}' for f in mine]
    if saturn.get('disc_sha256') not in (None,report['disc_sha256']):report['failures'].append('Saturn check used another disc')
    if need=='credits':credits(log,out,report)
    finish()

def credits(log,out,report):
    """The Saturn frames after the win against the retail SPEEND.MMD run: every retail
    fade-in picture in order, the credits picture, every fade-out picture after
    Start, then the title."""
    if run(['python3','tools/ss8_credits_retail.py'],out/'retail-credits.log'):report['failures'].append('retail credits run failed');return
    retail=[json.loads(line) for line in (ROOT/'build/special-retail/ss8-credits.jsonl').open()]
    shown=[r['pixels'] for r in retail if r['width']==320]
    steady=max(set(shown),key=shown.count)
    def distinct(seq):
        out=[]
        for x in seq:
            if not out or out[-1]!=x:out.append(x)
        return out
    first=shown.index(steady);last=len(shown)-1-shown[::-1].index(steady)
    fade_out=distinct(shown[last+1:]);black=fade_out[-1]
    # The program's first frames still show the previous picture, then black until the display.
    before=distinct(shown[:first]);fade_in=before[len(before)-1-before[::-1].index(black):] if black in before else before
    after=[line.split() for line in log.read_text().splitlines() if line.startswith('After: ')]
    pictures=[a[2] for a in after];title=next((int(a[1]) for a in after if a[5]=='5449544c'),None)
    def ordered(sub,seq):
        it=iter(seq);return all(any(x==y for y in it) for x in sub)
    report['credits']={'retail_steady':steady,'retail_fade_in':len(fade_in),'retail_fade_out':len(fade_out),
        'saturn_steady_frames':pictures.count(steady),'title_frame':title}
    if pictures.count(steady)<60:report['failures'].append(f'credits picture shown {pictures.count(steady)} frames (retail {steady})')
    missing_in=[x for x in fade_in[1:] if x not in pictures];missing_out=[x for x in fade_out if x not in pictures]
    report['credits'].update(missing_fade_in=len(missing_in),missing_fade_out=len(missing_out))
    if missing_in or not ordered([x for x in fade_in[1:]],pictures):report['failures'].append(f'{len(missing_in)} of {len(fade_in)-1} retail fade-in pictures missing or out of order')
    if missing_out or not ordered(fade_out,pictures):report['failures'].append(f'{len(missing_out)} of {len(fade_out)} retail fade-out pictures missing or out of order')
    if title is None:report['failures'].append('the title did not return after the credits')

if __name__=='__main__':main()
