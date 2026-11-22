#!/usr/bin/env python3
"""Select Japanese CD-DA without changing the graphics or sound-effect source.

Link assets/private/sonic-cd-japan.cue to the supplied Japanese CUE, or pass
--cue. Resolve the link before reading its FILE paths. Audio starts at INDEX 01;
the next track's INDEX 00 (if present) belongs to its pregap, not this song.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from native import IS_BROWSER, runtime_inputs

ROOT = Path(__file__).resolve().parents[1]
SECTOR = 2352


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_tracks(cue):
    cue = Path(cue).resolve(strict=True)
    tracks = []
    source = None
    for line in cue.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if match := re.fullmatch(r'FILE "(.+)" BINARY', line):
            source = cue.parent / match[1]
        elif line.startswith('FILE '):
            raise ValueError('Only raw BINARY CUE files are supported')
        elif match := re.fullmatch(r'TRACK (\d+) (AUDIO|MODE1/2352)', line):
            if source is None:
                raise ValueError('TRACK without FILE')
            tracks.append(dict(number=int(match[1]), mode=match[2], path=source, indices={}))
        elif line.startswith('TRACK '):
            raise ValueError('Unsupported CUE track format')
        elif match := re.fullmatch(r'INDEX (\d+) (\d+):(\d+):(\d+)', line):
            if not tracks or int(match[3]) >= 60 or int(match[4]) >= 75:
                raise ValueError('Invalid CUE index')
            tracks[-1]['indices'][int(match[1])] = (int(match[2])*60+int(match[3]))*75+int(match[4])
    if not tracks or [t['number'] for t in tracks] != list(range(1, len(tracks)+1)):
        raise ValueError('CUE tracks must be consecutive from track 1')
    for i, track in enumerate(tracks):
        size = track['path'].stat().st_size
        if size % SECTOR or 1 not in track['indices']:
            raise ValueError('Unaligned track file or missing INDEX 01')
        track['start'] = track['indices'][1]
        track['end'] = size // SECTOR
        if i+1 < len(tracks) and tracks[i+1]['path'] == track['path']:
            following = tracks[i+1]['indices']
            track['end'] = following.get(0, following.get(1, -1))
        if not 0 <= track['indices'].get(0, track['start']) <= track['start'] < track['end'] <= size//SECTOR:
            raise ValueError('Invalid track boundaries')
    return {t['number']: t for t in tracks}


def read_track(track):
    with track['path'].open('rb') as source:
        source.seek(track['start'] * SECTOR)
        data = source.read((track['end']-track['start']) * SECTOR)
    if len(data) != (track['end']-track['start']) * SECTOR:
        raise ValueError('Truncated track')
    return data


def prepare(cue):
    from extract_mmd import disc_files
    cue = Path(cue).resolve(strict=True)
    tracks = read_tracks(cue)
    if len(tracks) != 35 or tracks[1]['mode'] != 'MODE1/2352':
        raise ValueError('Expected the 35-track Japanese Sonic CD disc')
    raw = read_track(tracks[1])
    iso = b''.join(raw[i+16:i+2064] for i in range(0, len(raw), SECTOR))
    # Validate the actual disc region, not its filename. The Sega CD boot header
    # stores the country field at $1F0, just like the other retail region builds.
    if not iso.startswith(b'SEGADISCSYSTEM') or iso[0x1f0:0x200].strip() != b'J':
        raise ValueError('The music source is not a Japanese Sega CD disc')
    past = disc_files(iso)['SNCBNK1B.BIN']
    original_past = (ROOT/'build/retail/past-driver.bin').read_bytes()
    if past != original_past:
        raise ValueError('Japanese Past driver differs; recapture it before selecting this disc')
    path = ROOT/'build/feedback-source.json'
    report = json.loads(path.read_text())
    files = disc_files(iso)
    pending = []
    selected = []
    # Logical slots 0..9 stay stable. Each later zone adds present/past/good/bad.
    specs = [(0, era, number) for era, number in enumerate((3,None,4,5,28,29,30,32,24,26))]
    for zone in range(1,7):
        first = 3+zone*3
        specs += [(zone, era, number) for era,number in enumerate((first,None,first+1,first+2))]
    # Slot 34: the final boss (Sound.inc CDDA_FINAL, LOADER2.C sub_sync(104)).
    specs.append((0, 10, 25))
    # Slots 35-40, cues 11-16 (Sound.inc CDDA_TMATK, GAMEOVER, DAGARDEN, INTRO, ENDING,
    # WARP): the sound test DA list and the modes that play them.
    specs += [(0, 11, 27), (0, 12, 31), (0, 13, 33), (0, 14, 34), (0, 15, 35), (0, 16, 2)]
    work = ROOT/'build/japanese-past'; work.mkdir(exist_ok=True)
    captures = {}
    for slot,(zone,era,number) in enumerate(specs):
        target = ROOT/f'assets/generated/music{slot}.raw'
        track = dict(era=slot,zone=zone if era<4 else None,stage_era=era if era<4 else None,
                     saturn_track=slot+2,retail_track=number,soundtrack='Japan')
        if number is None:
            round_number = (1,3,4,5,6,7,8)[zone]
            bank_name = f'SNCBNK{round_number}B.BIN'
            bank = files[bank_name]
            if zone==0:
                data = target.read_bytes()
                capture = report['past_capture']
            else:
                driver = work/f'R{round_number}-driver.bin'
                output = work/f'R{round_number}'
                cache = output.with_suffix('.json')
                fingerprint = dict(driver_sha256=sha(bank),
                    capture_tool_sha256=sha((ROOT/'tools/capture_retail_audio.py').read_bytes()),
                    host_sha256=sha((ROOT/'tools/retail_capture.py').read_bytes()),
                    core_sha256=sha((ROOT/'browser/genesis.wasm' if IS_BROWSER else ROOT/'.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib').read_bytes()),
                    conversion='s16le/44100/stereo gain=1.5 fade-out=3s sector-pad')
                if IS_BROWSER:
                    fingerprint['browser_runtime']={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in runtime_inputs(ROOT,audio=True)}
                prior = json.loads(cache.read_text()) if cache.exists() else {}
                converted = output.with_name(output.name+'-cdda.raw')
                if prior.get('inputs') != fingerprint or not converted.exists() or sha(converted.read_bytes()) != prior.get('sha256'):
                    driver.write_bytes(bank)
                    subprocess.run([sys.executable,str(ROOT/'tools/capture_retail_audio.py'),'past',str(driver),str(output)],cwd=ROOT,check=True)
                    captured_raw = output.with_suffix('.raw')
                    duration = captured_raw.stat().st_size/176400
                    subprocess.run(['ffmpeg','-v','error','-y','-f','s16le','-ar','44100','-ac','2','-i',str(captured_raw),
                                    '-af',f'volume=1.5,afade=t=out:st={duration-3}:d=3','-f','s16le',str(converted)],check=True)
                    data = converted.read_bytes(); data += bytes((-len(data))%SECTOR);converted.write_bytes(data)
                    prior=dict(inputs=fingerprint,sha256=sha(data),capture=json.loads(output.with_name(output.name+'-capture.json').read_text()))
                    cache.write_text(json.dumps(prior,indent=2)+'\n')
                data=converted.read_bytes();capture=prior['capture']
            captures[str(zone)] = dict(driver_file=bank_name,driver_sha256=sha(bank),capture=capture)
            track.update(soundtrack='Japan (original Past driver)',past_driver=bank_name,past_driver_sha256=sha(bank))
        else:
            source = tracks[number]
            if source['mode'] != 'AUDIO':
                raise ValueError(f'Track {number} is not audio')
            data = read_track(source)
            track.update(source_file=source['path'].name,source_index01=source['start'])
        pending.append((target,data))
        track.update(sectors=len(data)//SECTOR,sha256=sha(data))
        report['outputs'][str(target.relative_to(ROOT))] = sha(data)
        selected.append(track)
    report['tracks']=selected
    report['past_captures']=captures
    # All source validation precedes changes to the prepared music bank.
    for target, data in pending:
        if not target.exists() or sha(target.read_bytes()) != sha(data):
            target.write_bytes(data)
    report['music_source'] = dict(region='Japan', cue=str(cue), cue_sha256=sha(cue.read_bytes()),
                                tool_sha256=sha(Path(__file__).read_bytes()),
                                data_track_sha256=sha(raw), past_driver_sha256=sha(past))
    path.write_text(json.dumps(report, indent=2)+'\n')
    print(f'Japanese soundtrack: {len(pending)} Saturn audio tracks; all seven zones and Past drivers included')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cue', type=Path, default=ROOT/'assets/private/sonic-cd-japan.cue')
    prepare(parser.parse_args().cue)
