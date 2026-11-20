#!/usr/bin/env python3
"""Check CUE boundaries independently of real copyrighted audio."""
import ctypes
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from prepare_japanese_music import ROOT, SECTOR, read_track, read_tracks


class CueTracks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def cue(self, text):
        path = self.root/'disc.cue'
        path.write_text(text)
        return path

    def test_split_files_skip_stored_pregap_and_resolve_cue_symlink(self):
        (self.root/'data.bin').write_bytes(b'D'*SECTOR)
        (self.root/'music.bin').write_bytes(b'P'*SECTOR+b'M'*SECTOR*2)
        cue = self.cue('FILE "data.bin" BINARY\nTRACK 01 MODE1/2352\nINDEX 01 00:00:00\n'
                       'FILE "music.bin" BINARY\nTRACK 02 AUDIO\nINDEX 00 00:00:00\nINDEX 01 00:00:01\n')
        (self.root/'private').mkdir()
        link = self.root/'private/japan.cue'
        link.symlink_to(cue)
        tracks = read_tracks(link)
        self.assertEqual(read_track(tracks[2]), b'M'*SECTOR*2)

    def test_single_file_ends_before_next_stored_pregap(self):
        (self.root/'disc.bin').write_bytes(b'A'*SECTOR*2+b'P'*SECTOR+b'B'*SECTOR)
        tracks = read_tracks(self.cue('FILE "disc.bin" BINARY\n'
                            'TRACK 01 AUDIO\nINDEX 01 00:00:00\n'
                            'TRACK 02 AUDIO\nINDEX 00 00:00:02\nINDEX 01 00:00:03\n'))
        self.assertEqual(read_track(tracks[1]), b'A'*SECTOR*2)
        self.assertEqual(read_track(tracks[2]), b'B'*SECTOR)

    def test_missing_index_or_bad_bounds_fail(self):
        (self.root/'disc.bin').write_bytes(b'A'*SECTOR)
        for indices in ('', 'INDEX 01 00:00:02\n', 'INDEX 01 00:00:75\n',
                        'INDEX 00 00:00:01\nINDEX 01 00:00:00\n'):
            with self.subTest(indices=indices), self.assertRaises(ValueError):
                read_tracks(self.cue('FILE "disc.bin" BINARY\nTRACK 01 AUDIO\n'+indices))


class ZoneMusic(unittest.TestCase):
    def test_original_tracks_and_native_routes(self):
        report=json.loads((ROOT/'build/feedback-source.json').read_text())
        self.assertEqual(len(report['tracks']),41)
        tracks=read_tracks(ROOT/'assets/private/sonic-cd-japan.cue')
        # Independent retail Sound.inc CDDA_RnA/C/D sequence starts at track 3.
        sound=(ROOT/'.deps/scddisasm/src/_Include/Sound.inc').read_text()
        names=[line.split()[0] for line in sound.splitlines() if line.startswith('CDDA_')]
        mapping={name:i+2 for i,name in enumerate(names)}
        from extract_mmd import disc_files
        raw=read_track(tracks[1]);files=disc_files(b''.join(raw[i+16:i+2064] for i in range(0,len(raw),SECTOR)))
        expected=[[2,3,4,5],[12,13,14,15],[16,17,18,19],[20,21,22,23],[24,25,26,27],[28,29,30,31],[32,33,34,35]]
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'routes.c';lib=Path(tmp)/'routes.dylib'
            source.write_text('#include "music_routes.h"\nunsigned route(unsigned z,unsigned e){return scd_music_slot(z,e)+2;}\nint repeat(unsigned c){return scd_music_repeats(c);}\nunsigned count(void){return SCD_MUSIC_COUNT;}')
            subprocess.run(['clang','-std=c11','-Wall','-Wextra','-Werror','-shared','-Isrc',str(source),'-o',str(lib)],cwd=ROOT,check=True)
            native=ctypes.CDLL(str(lib));self.assertEqual(native.count(),41)
            for zone,round_number in enumerate((1,3,4,5,6,7,8)):
                for era,suffix in enumerate('ABCD'):
                    saturn=expected[zone][era];self.assertEqual(native.route(zone,era),saturn)
                    item=report['tracks'][saturn-2];self.assertEqual((item['zone'],item['stage_era']),(zone,era))
                    data=(ROOT/f'assets/generated/music{saturn-2}.raw').read_bytes()
                    self.assertEqual(hashlib.sha256(data).hexdigest(),item['sha256'])
                    if era!=1:
                        retail=mapping[f'CDDA_R{round_number}{suffix}'];self.assertEqual(item['retail_track'],retail)
                        self.assertEqual(data,read_track(tracks[retail]))
                    else:
                        capture=report['past_captures'][str(zone)]
                        bank=files[f'SNCBNK{round_number}B.BIN']
                        self.assertEqual(hashlib.sha256(bank).hexdigest(),capture['driver_sha256'])
                        self.assertGreater(capture['capture']['sequencer_repeat_frames'][1],1000)
                for cue in range(4,10):self.assertEqual(native.route(zone,cue),cue+2)
            self.assertEqual([native.repeat(i) for i in range(10)],[1,1,1,1,0,0,0,1,1,0])
            # Cue 10: the final boss, CDDA_FINAL, Saturn track 36, looping like the boss.
            self.assertEqual(native.route(6,10),36);self.assertEqual(native.repeat(10),1)
            item=report['tracks'][34];self.assertEqual(item['retail_track'],mapping['CDDA_FINAL'])
            self.assertEqual((ROOT/'assets/generated/music34.raw').read_bytes(),read_track(tracks[mapping['CDDA_FINAL']]))
            # Slots 35-40 (cues 11-16): sound test and mode songs.
            for slot,cue,name in ((35,11,'CDDA_TMATK'),(36,12,'CDDA_GAMEOVER'),(37,13,'CDDA_DAGARDEN'),(38,14,'CDDA_INTRO'),(39,15,'CDDA_ENDING'),(40,16,'CDDA_WARP')):
                self.assertEqual(native.route(0,cue),slot+2)
                item=report['tracks'][slot];self.assertEqual(item['retail_track'],mapping[name])
                self.assertEqual((ROOT/f'assets/generated/music{slot}.raw').read_bytes(),read_track(tracks[mapping[name]]))


if __name__ == '__main__':
    unittest.main()
