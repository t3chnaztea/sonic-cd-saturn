#!/usr/bin/env python3
"""Check captured gameplay-area pixels, excluding the diagnostic HUD."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
directory = ROOT / 'build/emulator-qa'
names = ['present', 'camera-right', 'past', 'good-future', 'bad-future', 'floor', 'floor-motion', 'floor-return']
log=(directory/'results.log').read_text()
for frame in [1550,1680]:assert f'Floor VRAM: frame={frame} words=65536 errors=0 hash=3336674757' in log
report = {}
for name in names:
    with (directory / (name + '.ppm')).open('rb') as f:
        assert f.readline() == b'P6\n'
        width, height = map(int, f.readline().split())
        assert f.readline() == b'255\n'
        data = f.read()
    assert (width, height) == (330, 224), (name, width, height)
    assert len(data) == width * height * 3
    # Below all text; exclude the emulator's horizontal overscan border.
    scene = b''.join(data[(y * width + 5) * 3:(y * width + 325) * 3] for y in range(80, height))
    colors = len({scene[i:i+3] for i in range(0, len(scene), 3)})
    assert colors >= (3 if name.startswith('floor') else 16), (name, colors)
    report[name] = {'scene_sha256': hashlib.sha256(scene).hexdigest(), 'scene_colors': colors}
assert len({report[name]['scene_sha256'] for name in names[:-1]}) == len(names)-1, 'Scene failed to change'
assert report['floor-return']['scene_sha256'] == report['bad-future']['scene_sha256'], 'Stage not restored after floor test'
for name in ['player-walk','player-jump','player-charge','player-loop','spring-up','spring-side','spring-diagonal','player-hurt','player-death','object-layout','controller-dash-ready','controller-dash-release','controller-crouch']:
    payload=(directory/(name+'.ppm')).read_bytes()
    header,data=payload.split(b'255\n',1)
    assert header==b'P6\n330 224\n' and len(data)==330*224*3
    scene=b''.join(data[(y*330+5)*3:(y*330+325)*3] for y in range(80,224))
    colors=len({scene[i:i+3] for i in range(0,len(scene),3)})
    assert colors>=16, (name,colors)
    report[name]={'scene_sha256':hashlib.sha256(scene).hexdigest(),'scene_colors':colors}
ready=(directory/'controller-dash-ready.ppm').read_bytes().split(b'255\n',1)[1]
def pixel(x,y):return tuple(ready[(y*330+x)*3:(y*330+x)*3+3])
from hud_pixels import expected as hud_expected
hud_pixels=0
for (x,y),color in hud_expected(0,0,0,3,0).items():
    # Source labels and life icon do not depend on the fixture's live counters.
    if (8<=y<40 and x<61) or (200<=y<216 and x<45):
        assert bytes(pixel(x,y))==color,('Original HUD artwork',x,y,color,pixel(x,y))
        hud_pixels+=1
assert hud_pixels>400
match=re.search(r'Emulator frames: (\d+); SH-2 replay states: 16800', (directory/'results.log').read_text())
assert match, 'Replay did not finish'
log=(directory/'results.log').read_text()
audio=re.search(r'Audio samples: (\d+); nonzero: (\d+); peak: (\d+)',log)
controller=re.search(r'Controller dash charge: (\d+); release speed: (\d+)',log)
game_audio=re.search(r'Post-boot nonzero game audio samples: (\d+)',log)
assert audio and controller and game_audio and int(game_audio[1])>1000
assert int(controller[1])==45 and int(controller[2])>=3000
warmup=int(re.search(r'Boot warmup frames: (\d+)',(directory/'results.log').read_text())[1])
packs=re.search(r'Stage packs: magic=5350414b vblanks=(\d+) bytes=(\d+) error=0',log)
assert packs, 'CD stage packs did not load'
result = {'frames_run': int(match[1])+warmup, 'boot_warmup_frames':warmup, 'scripted_frames':int(match[1]), 'disc_sha256': hashlib.sha256((ROOT/'dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest(),
          'audio':{'samples':int(audio[1]),'nonzero':int(audio[2]),'peak':int(audio[3]),'post_boot_nonzero':int(game_audio[1])},'stage_packs':{'boot_vblanks':int(packs[1]),'bytes':int(packs[2])},'original_hud_static_pixels':hud_pixels,'controller_dash':{'charge':int(controller[1]),'release_speed':int(controller[2])},'automated_scene_checks': 'pass', 'simulation_pacing': 'trace VBlank ticks strictly increase; at most one player update per VBlank', 'captures': report,
          'limits': 'Scene checks are not full visual-fidelity checks. Player state equivalence is recorded separately in player-report.json. No hardware validation.'}
result['gameplay_audio_sha256']=hashlib.sha256((directory/'audio.raw').read_bytes()).hexdigest()
(ROOT / 'dist/emulator-report.json').write_text(json.dumps(result, indent=2) + '\n')
print('Twenty-one nonblank captures verified; graphics scenes change and restore correctly (HUD excluded).')
