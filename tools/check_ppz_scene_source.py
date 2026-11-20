#!/usr/bin/env python3
"""Compare exposed PPZ boss and capsule pixels with original source art."""
import hashlib
import json
from pathlib import Path

from convert_objects import DATA, assembly_frames, draw, nemesis, palette
from hud_pixels import expected as hud_expected, verify as verify_hud

ROOT = Path(__file__).resolve().parents[1]
GOOD = ROOT / 'build/ppz-journey/v067-act3-good-results-target-03'
BAD = ROOT / 'build/sequence-qa'
SPECIAL = ROOT / 'build/ppz-journey/v067-special-return-target-02'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pixels(path):
    header, rgb = path.read_bytes().split(b'255\n', 1)
    assert header == b'P6\n330 224\n' and len(rgb) == 330 * 224 * 3
    return rgb


def compare(rgb, texture, width, left, top, clip=None):
    checked = 0
    for i in range(0, len(texture), 2):
        py, px = divmod(i // 2, width)
        if clip and not clip(px, py):
            continue
        value = int.from_bytes(texture[i:i + 2], 'big')
        if not value:
            continue
        color = bytes(((value & 31) * 8, ((value >> 5) & 31) * 8,
                       ((value >> 10) & 31) * 8))
        x, y = left + px, top + py
        assert rgb[(y * 330 + x) * 3:(y * 330 + x + 1) * 3] == color, \
            ('original source pixel', x, y, color)
        checked += 1
    return checked


def boss_tables(path):
    data = path.read_bytes()
    at, tables = 0, []
    while at < len(data):
        count = data[at]
        at += 1
        table = []
        for _ in range(count):
            mapping = data[at:at + 1 + 5 * data[at]]
            at += len(mapping)
            table.append(mapping)
        tables.append(table)
    assert at == len(data) and len(tables[0]) == 11
    return tables


def main():
    good = json.loads((GOOD / 'report.json').read_text())
    bad = json.loads((ROOT / 'dist/sequence-report.json').read_text())
    special = json.loads((SPECIAL / 'report.json').read_text())
    disc = sha(ROOT / 'dist/sonic-cd-saturn-prototype.bin')
    assert good['passed'] and bad['passed'] and special['passed']
    assert good['disc_sha256'] == bad['disc_sha256'] == special['disc_sha256'] == disc
    capsule_path = GOOD / 'journey-capsule-intact.ppm'
    good_boss_path = GOOD / 'journey-boss-defeated.ppm'
    bad_boss_path = BAD / 'act3-boss-defeated.ppm'
    assert good['captures'][capsule_path.name] == sha(capsule_path)
    assert good['captures'][good_boss_path.name] == sha(good_boss_path)
    assert bad['captures']['act3-boss-defeated'] == sha(bad_boss_path)

    end = DATA / '_Objects/Level End/Data'
    maps = assembly_frames(end / 'Mappings (Flower Capsule).asm')
    art = nemesis((end / 'Art (Flower Capsule).nem').read_bytes())
    colors = palette((end / 'Palette (Flower Capsule).bin').read_bytes())
    capsule = draw(maps[0], art, colors, 96, 0, 96)
    capsule_rgb = pixels(capsule_path)
    capsule_count = compare(capsule_rgb, capsule, 96, 134, 112)
    assert capsule_count == 3748

    boss_map = ROOT / 'assets/generated/boss13.map'
    robotnik = (ROOT / 'assets/generated/boss-robotnik.tiles').read_bytes()
    sonic_colors = palette((DATA / '_Objects/Sonic/Data/Palette.bin').read_bytes())
    frames = boss_tables(boss_map)[0]
    exposed = lambda x, y: 30 <= x < 50 and 16 <= y < 25
    good_head = draw(frames[1], robotnik, sonic_colors, 96, 8, 96)
    bad_head = draw(frames[0], robotnik, sonic_colors, 96, 8, 96)
    good_count = compare(pixels(good_boss_path), good_head, 96, 147, 61, exposed)
    bad_count = compare(pixels(bad_boss_path), bad_head, 96, 147, 61, exposed)
    assert (good_count, bad_count) == (130, 120)

    return_path = SPECIAL / 'journey-special-return.ppm'
    assert special['captures'][return_path.name] == sha(return_path)
    assert special['special_return']['act'] == 3 and special['special_return']['era'] == 2
    assert special['special_return']['stones'] == 1
    assert special['special_return']['score'] == 46000
    retail_path = ROOT / 'build/special-retail/win-route.json'
    retail = json.loads(retail_path.read_text())
    assert retail['got_time_stone'] == 1 and retail['ufo_count'] == 0
    returned = return_path.read_bytes()
    return_count = verify_hud(returned, 46000, 0, 26, 3, 2)
    assert return_count == 1876

    changed = bytearray(capsule_rgb)
    x, y = 134 + 48, 112 + 32
    changed[(y * 330 + x) * 3] ^= 255
    try:
        compare(changed, capsule, 96, 134, 112)
    except AssertionError:
        mutation_rejected = True
    else:
        raise AssertionError('capsule pixel mutation was accepted')
    header, rgb = returned.split(b'255\n', 1)
    x, y = next(iter(hud_expected(46000, 0, 26, 3, 2)))
    changed = bytearray(rgb)
    changed[(y * 330 + x) * 3] ^= 255
    try:
        verify_hud(header + b'255\n' + changed, 46000, 0, 26, 3, 2)
    except AssertionError:
        return_mutation_rejected = True
    else:
        raise AssertionError('special return HUD mutation was accepted')

    sources = [
        'tools/check_ppz_scene_source.py', 'tools/convert_objects.py',
        'tools/hud_pixels.py',
        'assets/generated/boss13.map', 'assets/generated/boss-robotnik.tiles',
        '.deps/scddisasm/src/Level/_Objects/Sonic/Data/Palette.bin',
        '.deps/scddisasm/src/Level/_Objects/Level End/Data/Mappings (Flower Capsule).asm',
        '.deps/scddisasm/src/Level/_Objects/Level End/Data/Art (Flower Capsule).nem',
        '.deps/scddisasm/src/Level/_Objects/Level End/Data/Palette (Flower Capsule).bin',
        '.deps/scddisasm/src/Level/_Objects/HUD and Points/Data/Mappings (HUD).asm',
        '.deps/scddisasm/src/Level/_Objects/HUD and Points/Data/Art (HUD).nem',
        '.deps/scddisasm/src/Level/_Objects/HUD and Points/Data/Art (Numbers).bin',
        '.deps/scddisasm/src/Level/_Objects/HUD and Points/Data/Art (Life Icon).bin',
        '.deps/scddisasm/src/Level/_Objects/Level End/Main.asm',
        '.deps/scddisasm/src/Level/_Objects/Results/Main.asm',
    ]
    evidence = [capsule_path, good_boss_path, bad_boss_path, return_path,
                GOOD / 'report.json', SPECIAL / 'report.json', retail_path,
                ROOT / 'dist/sequence-report.json']
    report = dict(
        passed=True, disc_sha256=disc, capsule_pixels=capsule_count,
        good_boss_pixels=good_count, bad_boss_pixels=bad_count,
        special_return_hud_pixels=return_count, original_retail_time_stone=1,
        capsule_mutation_rejected=mutation_rejected,
        return_hud_mutation_rejected=return_mutation_rejected,
        source_sha256={name: sha(ROOT / name) for name in sources},
        evidence_sha256={str(path.relative_to(ROOT)): sha(path) for path in evidence},
        limits='Exact original-source opaque pixels in the intact capsule, exposed Robotnik face and Act 3 return HUD; other boss parts, motion, background and console presentation are outside this check.',
    )
    out = GOOD / 'source-scenes-report-02.json'
    assert not out.exists()
    out.write_text(json.dumps(report, indent=2) + '\n')
    print(f'PPZ source scenes: capsule {capsule_count}; Good boss {good_count}; Bad boss {bad_count}; return HUD {return_count}; mutations rejected')


if __name__ == '__main__':
    main()
