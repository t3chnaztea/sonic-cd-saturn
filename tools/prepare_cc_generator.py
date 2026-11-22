#!/usr/bin/env python3
"""Cache original generator art at its actual CC placements, then verify it."""
import hashlib,json
from pathlib import Path
from convert_assets import ROOT
from extract_mmd import disc_files
from cc_generator_source import verify
from zone_object_source import capture,dependencies
from test_cc_generator_art import verify as verify_art
verify()
files=disc_files((ROOT/'build/retail/sonic.iso').read_bytes())
tool=hashlib.sha256((ROOT/'tools/zone_object_source.py').read_bytes()).hexdigest()
for name in ['R31A','R31B','R32A','R32B']:
    out=ROOT/'build/cc1/generator/art-placement'/name
    old=json.loads((out/'source.json').read_text()) if (out/'source.json').exists() else {}
    camera_x,player_y=(4832,560) if name[2]=='1' else (3008,557)
    poses=[0,2] if name[-1]=='A' else [1,3,4,5,6,7]
    valid=(old.get('tool_sha256')==tool and old.get('dependencies')==dependencies() and
           old.get('program_sha256')==hashlib.sha256(files[name+'__.MMD']).hexdigest() and
           old.get('fixture',{}).get('camera_x')==camera_x and old.get('fixture',{}).get('player_y')==player_y and
           old.get('objects',[{}])[0].get('frame_ids')==poses and (out/'vram.bin').exists() and
           hashlib.sha256((out/'vram.bin').read_bytes()).hexdigest()==old.get('vram_sha256'))
    if not valid:capture(name,out,[(86,55,poses)],camera_x=camera_x,player_y=player_y)
verify_art()
