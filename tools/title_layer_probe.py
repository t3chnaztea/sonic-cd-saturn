#!/usr/bin/env python3
"""Read-only renderer instrumentation to classify the wide-title visual mismatch.

Wrap the pinned retail core's exported background-render callback, call it once,
then read its completed background line before sprites obscure it. No emulated
RAM/registers, renderer buffers or timing are changed. Private Mach-O symbols
are resolved from nm relative to the exported bitmap symbol. Every resulting
retail frame must still equal the uninstrumented oracle. This is diagnostic
evidence, NOT a replacement passing title gate.
"""
import array,ctypes as C,json,subprocess,sys,zipfile
from pathlib import Path
import title_retail as tr

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/title-layer-probe'

def main():
    OUT.mkdir(exist_ok=True)
    retail=[json.loads(l) for l in (tr.OUT/'newgame.jsonl').read_text().splitlines()]
    baseline={r['frame']:r for r in retail};title=[r for r in retail if r['title']]
    r0=next(i for i,r in enumerate(title) if r['v']==1)
    indices={r['frame']:i-r0 for i,r in enumerate(title)}
    sat_rows=[l.split() for l in (ROOT/'build/title-qa/title-frames.txt').read_text().splitlines()]
    s0=next(int(r[0]) for r in sat_rows if r[1]=='1')
    sat_index={int(r[0]):i for i,r in enumerate(sat_rows)}
    sat_file=(ROOT/'build/title-qa/title-pixels.bin').open('rb')
    t=tr.Title();t.boot();t.blobs={}
    library=ROOT/'.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib'
    symbols={}
    for l in subprocess.check_output(['nm','-a',str(library)],text=True).splitlines():
        fields=l.split()
        if len(fields)==3 and fields[2] in ('_bitmap','_linebuf','_pixel'):
            symbols[fields[2]]=int(fields[0],16)
    assert set(symbols)=={'_bitmap','_linebuf','_pixel'},symbols
    base=C.addressof(C.c_uint8.in_dll(t.core.lib,'bitmap'))-symbols['_bitmap']
    linebuf=base+symbols['_linebuf'];palette=base+symbols['_pixel']
    slot=C.c_void_p.in_dll(t.core.lib,'render_bg');original=slot.value
    callback_type=C.CFUNCTYPE(None,C.c_int);render_bg=callback_type(original)
    backgrounds=bytearray(256*224*2);seen=set();errors=[]
    @callback_type
    def capture(line):
        render_bg(line)
        if 0<=line<224:
            try:
                codes=C.string_at(linebuf+0x20,256);colors=C.string_at(palette,512)
                backgrounds[line*512:(line+1)*512]=b''.join(colors[c*2:c*2+2] for c in codes)
                seen.add(line)
            except Exception as exc:errors.append(repr(exc))
    slot.value=C.cast(capture,C.c_void_p).value
    report={'retail_frames_unchanged':0,'compared':0,'original_misses':0,'background_disocclusion':0,
            'unexplained':0,'unexplained_right_edge':0,'examples':[],'passed_title_gate':False}
    positions=[(y*256+x*256//320,y*256+max(x*256//320-1,0),y*256+min(x*256//320+1,255),x,y)
        for y in range(224) for x in range(320)]
    archive=zipfile.ZipFile(OUT/'backgrounds.zip','w',zipfile.ZIP_DEFLATED)
    try:
        while t.frames<max(baseline):
            # VDP mode writes reselect the renderer. Wrap the new callback on the
            # next frame; partially observed frames are excluded below.
            if slot.value!=C.cast(capture,C.c_void_p).value:
                original=slot.value;render_bg=callback_type(original)
                slot.value=C.cast(capture,C.c_void_p).value
            seen.clear();t.core.pad=tr.newgame(t.word('vintCounter'));t.core.run();t.frames+=1
            row=t.snapshot();assert not errors,errors
            reference=baseline[t.frames]
            assert row['pixels']==reference['pixels'],('Instrumentation changed picture',t.frames)
            for key in tr.FIELDS if hasattr(tr,'FIELDS') else ('v','mode','timer','routine','cram','sat','tiles'):
                assert row[key]==reference[key],('Instrumentation changed state',t.frames,key)
            report['retail_frames_unchanged']+=1
            if not row['title'] or t.frames not in indices:continue
            sf=s0+indices[t.frames]+3
            if sf not in sat_index:continue
            # Blank lines were not rendered and have no independently observed background.
            if len(seen)!=224:continue
            sat_file.seek(sat_index[sf]*224*320*2)
            actual=array.array('H',sat_file.read(224*320*2));picture=array.array('H',t.core.frame[2]);bg=array.array('H',backgrounds)
            if sys.byteorder!='little':actual.byteswap();picture.byteswap();bg.byteswap()
            original_misses=explained=unexplained=edge=0
            for color,(i,left,right,x,y) in zip(actual,positions):
                if color in (picture[i],picture[left],picture[right]):continue
                original_misses+=1
                if color in (bg[i],bg[left],bg[right]):explained+=1
                else:
                    unexplained+=1;edge+=x==319
                    if len(report['examples'])<40:report['examples'].append({'v':row['v'],'x':x,'y':y,'actual':color,'retail':picture[i],'background':bg[i]})
            report['compared']+=1;report['original_misses']+=original_misses
            report['background_disocclusion']+=explained;report['unexplained']+=unexplained;report['unexplained_right_edge']+=edge
            if row['v'] in (120,203,710):archive.writestr(f'v{row["v"]}-frame{t.frames}.bin',backgrounds)
    finally:
        slot.value=original;archive.close();sat_file.close()
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='examples'},indent=2))

if __name__=='__main__':main()
