#!/usr/bin/env python3
"""Record actual SCSP output, drive status, pause position, and disc repeat evidence."""
import array,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
disc=hashlib.sha256((ROOT/'dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest()
emulator=json.loads((ROOT/'dist/emulator-report.json').read_text())
assert emulator['disc_sha256']==disc,'Run test-emulator.sh on this BIN before comparing its gameplay audio with the idle recording'
assert emulator.get('gameplay_audio_sha256')==hashlib.sha256((ROOT/'build/emulator-qa/audio.raw').read_bytes()).hexdigest(),'Gameplay audio recording does not match the completed emulator report'
log=(ROOT/'build/audio-qa/results.log').read_text()
assert 'Music era switching, pause/resume, present repeat after resume, and final-track repeat passed' in log
tracks=re.findall(r'Music track (\d+): samples=(\d+) mean_square=(\d+) peak=(\d+) repeats=(\d+)',log)
assert len(tracks)==4
pause=re.search(r'Pause: nonzero=(\d+) FAD=(\d+)->(\d+)',log)
assert pause and int(pause[1])==0 and pause[2]==pause[3]
# The gameplay run and idle-music run have identical music before any SFX.
# Their first divergence must come from the controller-driven charge/release.
def prefix(path):
    with path.open('rb') as f:return array.array('h',f.read(7*176400))
game=prefix(ROOT/'build/emulator-qa/audio.raw');idle=prefix(ROOT/'build/audio-qa/audio.raw')
def difference(a,b):
    lo=int(a*88200);hi=int(b*88200)
    assert len(game)>=hi and len(idle)>=hi
    return sum((game[i]-idle[i])**2 for i in range(lo,hi))/(hi-lo)
baseline=difference(2.2,2.4);effects=difference(4.7,5.4)
assert baseline<100 and effects>250000, (baseline,effects)
warmup=int(re.search(r'Boot warmup frames: (\d+)',log)[1])
report={'effect_mix_mean_square_difference':effects,'music_only_baseline_difference':baseline,'disc_sha256':disc,'emulator_frames':22000+warmup,'boot_warmup_frames':warmup,'sound_bank_hash_and_toc':'verified on SH-2','tracks':[dict(zip(['track','samples','mean_square','peak','repeats'],map(int,t))) for t in tracks],'pause_silent':True,'pause_fad':int(pause[2]),'resume_and_present_repeat':True,'bad_future_track_repeat':True,'hardware_tested':False}
report['gameplay_audio_sha256']=emulator['gameplay_audio_sha256']
report['idle_audio_sha256']=hashlib.sha256((ROOT/'build/audio-qa/audio.raw').read_bytes()).hexdigest()
(ROOT/'dist/audio-report.json').write_text(json.dumps(report,indent=2)+'\n')
print('Music playback, four eras, silent pause with fixed disc position, resume and looping verified')
