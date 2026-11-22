#!/usr/bin/env python3
"""Verify Collision Chaos pocket and point-popup instructions in all ten MMDs.

The reconstructed PC POCKET.C decrements the capture timer immediately. The
console tail-calls soundset instead. SCORE.C also omits the console tile base
and moves an already-deleted popup. Keep those differences explicit before
using either reconstructed source as a native behavior oracle.
"""
import hashlib
import json
import re
import struct
from pathlib import Path

from convert_assets import ROOT
from extract_mmd import ORIGIN, disc_files
from retail_span import disc_span


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inspect(program):
    signature = bytes.fromhex('317c03af0002')
    assert program.count(signature) == 1
    # Offset origin is four bytes after the subtype test, matching the saved
    # disassembly. Cover the subtype test too in the normalized whole block.
    base = program.index(signature)-100
    block = bytearray(program[base-4:base+0x354])
    absolute = [28,34,84,112,310,342,390,610,786,808,818,824,830]
    addresses = [struct.unpack_from('>I', block, at)[0] for at in absolute]
    assert all(ORIGIN <= a < ORIGIN+len(program) for a in addresses)
    for at in absolute:
        block[at:at+4] = bytes(4)
    relative = [0x1e0,0x1e6,0x20c,0x212]
    targets = [base+at+struct.unpack_from('>h',program,base+at)[0] for at in relative]
    assert targets[0] == targets[2] and targets[1] == targets[3]
    for at in relative:
        block[at+4:at+6] = bytes(2)
    # This covers every instruction, branch, timer, capture bound, flag,
    # mapping piece and animation byte, with only linked addresses removed.
    assert sha(block) == '8eb3f0e423f1123ed25561273e1c6bce08d3f19c493fece5f3dfb350947a2d54'
    draw, frameout_s, remove, parent_map, sound, allocator, remove2, sound2, child_map, remove3, animate, draw2, remove4 = addresses
    assert draw == draw2 and remove == remove2 == remove3 == remove4 and sound == sound2
    assert parent_map == ORIGIN+base+0x2ac and child_map == ORIGIN+base+0x344
    # Do not permit a different allocation search hidden behind a relocation.
    allocator_bytes = disc_span('R31A__.MMD',0x7afc,22,'6667fa7be16cecae589929eb06827cf21a34ca97c4d48375f8fa5fb36d0018f7')
    assert program[allocator-ORIGIN:allocator-ORIGIN+len(allocator_bytes)] == allocator_bytes
    spawn = targets[1]
    expected_spawn = bytes.fromhex('000100804eb9')+struct.pack('>I',allocator)
    expected_spawn += disc_span('R31A__.MMD',0x5fbc,26,'c3114b12e4e4b7333b1abfceb532f44f52c4a7a176ec87a935605df109734c9f')
    assert program[spawn:spawn+len(expected_spawn)] == expected_spawn
    # Capture ends with JMP soundset, not JSR soundset followed by timer work.
    capture = disc_span('R31A__.MMD',0xb6f0,22,'238b41ccbdef5adb62bf5ffd221ac70ae1b9ca751fe9a21823c853cff8542f91')+struct.pack('>I',sound)
    assert program[base+0x11c:base+0x136] == capture
    # Popup initializer and motion: preserve OR flags, exact tile base, and
    # tail-return on expiry before subtracting two from integer Y.
    popup_signature = disc_span('R31A__.MMD',0xa736,14,'089db5316726c8d5d3aa8d4111141871f4110c580ade9d5de8ef43f987fceca0')
    assert program.count(popup_signature) == 1
    popup = program.index(popup_signature)-36
    expected = disc_span('R31A__.MMD',0xa712,18,'da2a507bf5ca1e1f08cda948e4ff1e152bcbf1b35ad0c2b7a59d72abbb5e98fd')
    assert program[popup:popup+len(expected)] == expected
    popup_map = struct.unpack_from('>I',program,popup+18)[0]
    assert popup_map == ORIGIN+popup+60
    expected += struct.pack('>I',popup_map)+disc_span('R31A__.MMD',0xa728,28,'d547166fbfa696337b02881629d07e62b1f1e8f0af30cfe8955c20cc3f5dbc1b')
    expected += struct.pack('>I',remove)+bytes.fromhex('5568000c4e75')
    assert program[popup:popup+len(expected)] == expected and len(expected) == 60

    def mappings(address, count):
        offset = address-ORIGIN
        frames = []
        for n in range(count):
            at = offset+struct.unpack_from('>H',program,offset+2*n)[0]
            size = 1+program[at]*5
            frames.append(program[at:at+size].hex())
        return frames

    parent_frames = mappings(parent_map,4)
    child_frames = mappings(child_map,2)
    popup_frames = mappings(popup_map,6)
    assert parent_frames[0] == child_frames[1] == '00'
    assert [bytes.fromhex(f)[0] for f in parent_frames] == [0,2,2,2]
    assert [bytes.fromhex(f)[0] for f in child_frames] == [2,0]
    return dict(entry=ORIGIN+base-4, parent=ORIGIN+base+8,
        allocator=allocator, allocator_bytes=allocator_bytes.hex(),
        draw=draw, frameout_s=frameout_s, remove=remove, sound=sound, animate=animate,
        score=ORIGIN+targets[0], popup_spawn=ORIGIN+spawn, popup_init=ORIGIN+popup,
        parent_mapping=parent_map, child_mapping=child_map, popup_mapping=popup_map,
        frames=dict(parent=parent_frames,child=child_frames,points=popup_frames),
        capture_timer_decrement_on_entry=False, score_grants=7, points_per_grant=100,
        parent_tile=943, child_tile=17327, popup_tile=1734,
        parent_timer_offset=42, parent_child_pointer_offset=44,
        child_parent_pointer_offset=46, score_grants_offset=48, capture_flag_offset=62,
        popup_moves_on_expiry=False, normalized_block_sha256=sha(block),
        capture_instructions=capture.hex(), popup_instructions=expected.hex())


def verify():
    files = disc_files((ROOT/'build/retail/sonic.iso').read_bytes())
    programs = {}
    for act in (1,2,3):
        for era in ('CD' if act == 3 else 'ABCD'):
            name = f'R3{act}{era}'
            program = files[name+'__.MMD']
            programs[name] = dict(program_sha256=sha(program), **inspect(program))
    # FM6 is entirely owned by D7. The equal-priority 9F release replaces it
    # with FM5/FM6; retaining the full D7 PCM tail would add an extra sound.
    data_path=ROOT/'.deps/scddisasm/src/Sound Drivers/FM/Data.asm'
    data=data_path.read_text()
    entries=re.findall(r'^\s*dw\s+SFX_([0-9A-F]+)',data,re.M)
    priorities=bytes(int(v,16) for v in re.findall(r'^\s*db\s+([0-9A-F]+)h',data.split('SFXPriorities:')[1],re.M))
    driver_path=ROOT/'build/retail/fm-driver.bin';driver=driver_path.read_bytes()
    assert entries==[f'{n:02X}' for n in range(144,224)] and driver.count(priorities)==1
    index=driver.index(priorities)-2*len(entries)
    capture,release=[struct.unpack_from('<H',driver,index+2*(n-144))[0] for n in (215,159)]
    assert driver[capture+2:capture+6]==bytes.fromhex('01018006')
    assert driver[release+2:release+6]==bytes.fromhex('01028005') and driver[release+10:release+12]==bytes.fromhex('8006')
    assert priorities[215-144]==priorities[159-144]==109
    result = dict(passed=True, programs=programs,
        audio=dict(capture_request=215,release_request=159,capture_channels=[6],release_channels=[5,6],
                   priority=109,release_replaces_capture=True,driver_sha256=sha(driver),data_sha256=sha(data_path.read_bytes())),
        tool_sha256=sha(Path(__file__).read_bytes()),
        limits='Original pocket block, allocator, point spawn/init/motion and mappings. No native implementation, audio capture, loaded VRAM or gameplay acceptance.')
    out = ROOT/'build/cc1/pocket'
    out.mkdir(parents=True,exist_ok=True)
    (out/'retail.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__ == '__main__':
    print('Verified original pocket and score popups in',len(verify()['programs']),'programs')
