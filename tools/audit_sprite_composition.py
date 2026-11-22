"""Capture converter inputs in an isolated output tree, never rewrite assets.

The production converter supplies its selected source mappings/art. Their
composition is verified independently by sprite_composition.source_sprite.
This is a composition oracle, not proof of mapping selection or animation.
"""
import contextlib
import hashlib
import inspect
import io
import json
from pathlib import Path
import shutil
import tempfile
from functools import lru_cache

import convert_objects as converter
from sprite_composition import source_sprite

ROOT = converter.ROOT
INPUTS = ['objects12A.bin', 'objects13C.bin', 'objects13D.bin', 'swing12A.map',
          'collapse12.map', 'boss13.map', 'boss-robotnik.tiles', 'boss-parts.tiles',
          'boss13C.pal', 'boss13D.pal', 'boss3C.pal', 'boss3D.pal', 'boss4C.pal', 'boss4D.pal',
          'boss5C.pal', 'boss5D.pal', 'boss6C.pal', 'boss6D.pal']


def capture():
    records = []
    source_inputs = {}
    original_draw, original_root, original_out = converter.draw, converter.ROOT, converter.OUT
    read_bytes, read_text = Path.read_bytes, Path.read_text

    def remember(path, raw):
        path=path.resolve()
        if path.is_relative_to(ROOT) and not path.is_relative_to(converter.ROOT):
            source_inputs[str(path.relative_to(ROOT))]=hashlib.sha256(raw).hexdigest()

    def observed_bytes(path, *args, **kwargs):
        raw=read_bytes(path, *args, **kwargs);remember(path, raw);return raw

    def observed_text(path, *args, **kwargs):
        text=read_text(path, *args, **kwargs);remember(path, read_bytes(path));return text

    def record(mapping, art, colors, width=64, y_shift=0, height=64, **options):
        caller = inspect.currentframe().f_back
        main = caller
        while main and not (main.f_code.co_name == 'main' and main.f_globals is converter.__dict__):
            main = main.f_back
        assert main is not None
        card = 'card_data' in main.f_locals
        number = len(main.f_locals['card' if card else 'frames'])
        pixels = original_draw(mapping, art, colors, width, y_shift, height, **options)
        records.append(dict(kind='title_card' if card else 'object', frame=number,
                            mapping=bytes(mapping), art=bytes(art), colors=bytes(colors),
                            width=width, y_shift=y_shift, height=height, actual=bytes(pixels),
                            caller_line=caller.f_lineno,
                            selection_context=str(main.f_locals.get('path', 'spring'))))
        return pixels

    try:
        with tempfile.TemporaryDirectory(prefix='scd-composition-', dir=ROOT / 'build') as tmp:
            converter.ROOT = Path(tmp)
            converter.OUT = Path(tmp) / 'assets'
            converter.OUT.mkdir(); (Path(tmp) / 'build').mkdir()
            for name in INPUTS:
                shutil.copyfile(original_out / name, converter.OUT / name)
                remember(original_out/name,read_bytes(original_out/name))
            Path.read_bytes, Path.read_text = observed_bytes, observed_text
            converter.draw = record
            with contextlib.redirect_stdout(io.StringIO()): converter.main()
            catalog = json.loads((Path(tmp) / 'build/object-source.json').read_text())
            artifacts = {name: (converter.OUT / name).read_bytes() for name in
                         ['object-art.bin', 'object-frames.inc', 'title-card-art.bin', 'title-card.inc']}
    finally:
        converter.draw, converter.ROOT, converter.OUT = original_draw, original_root, original_out
        Path.read_bytes, Path.read_text = read_bytes, read_text
    return records, catalog, artifacts, source_inputs


def analyze(records, catalog):
    results = []
    for r in records:
        args = [r[n] for n in ['mapping', 'art', 'colors', 'width', 'y_shift', 'height']]
        first = source_sprite(*args)
        last = source_sprite(*args, legacy_last=True)
        difference = sum(a != b for a, b in zip(
            struct_words(first), struct_words(last)))
        results.append({**{n: r[n] for n in ['kind', 'frame', 'width', 'y_shift', 'height', 'caller_line', 'selection_context']},
                        'catalog_ids':[int(k) for k,(start,count) in catalog.items() if r['kind']=='object' and start<=r['frame']<start+count],
                        'pieces': r['mapping'][0], 'changed_pixels': difference,
                        'current_matches_first': r['actual'] == first,
                        'current_matches_last': r['actual'] == last,
                        'mapping_hex': r['mapping'].hex(),
                        **{n + '_sha256': hashlib.sha256(value).hexdigest() for n, value in
                           [('art', r['art']), ('colors', r['colors']), ('first', first), ('last', last)]}})
    return results


@lru_cache(maxsize=1)
def object_records():
    """Selected source inputs, cached within one test/checker process only."""
    return {r['frame']: r for r in capture()[0] if r['kind'] == 'object'}


def struct_words(data):
    import struct
    return struct.iter_unpack('>H', data)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path)
    args = p.parse_args()
    assert not args.output.exists(), 'do not overwrite an audit'
    records, catalog, artifacts, inputs = capture()
    # Isolated conversion must exactly reproduce existing generated assets.
    for name, raw in artifacts.items(): assert raw == (converter.OUT / name).read_bytes(), name
    rows = analyze(records, catalog['frame_catalog'])
    changed = [r for r in rows if r['changed_pixels'] and not r['current_matches_first']]
    report = dict(frames=rows, remaining_changes=changed, catalog=catalog['frame_catalog'],source_input_sha256=inputs,
                  converter_sha256=hashlib.sha256(Path(converter.__file__).read_bytes()).hexdigest(),
                  artifact_sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in artifacts.items()})
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(f'{len(rows)} compositions checked; {len(changed)} retain wrong piece order')
    for r in changed: print(r['kind'], r['frame'], r['changed_pixels'], 'object types',r['catalog_ids'])
